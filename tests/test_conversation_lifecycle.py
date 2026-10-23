"""Conversation timers (Base PRD §6.4 Timers; TDD §9.15–9.18). CONV-DNT-14 … CONV-DNT-17."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from poc.conversation_lifecycle import run_lifecycle_pass, thresholds_for
from poc.conversation_links import link_communications, mark_done
from poc.database import get_connection, init_db
from poc.scheduler import LIFECYCLE_INTERVAL_SECONDS, SyncScheduler
from poc.settings import set_setting

NOW = datetime(2026, 10, 23, 12, 0, tzinfo=timezone.utc)
NOW_ISO = NOW.isoformat()
CUST_ID = "cust-life"
USER_ID = "user-life"


def _days_ago(n: float) -> str:
    return (NOW - timedelta(days=n)).isoformat()


@pytest.fixture()
def tmp_db(tmp_path, monkeypatch):
    db_file = tmp_path / "test.db"
    monkeypatch.setattr("poc.config.DB_PATH", db_file)
    monkeypatch.setattr("poc.config.CRM_AUTH_ENABLED", False)
    init_db(db_file)
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO customers (id, name, slug, is_active, created_at, updated_at) "
            "VALUES (?, 'Life Org', 'life', 1, ?, ?)", (CUST_ID, NOW_ISO, NOW_ISO))
        conn.execute(
            "INSERT INTO users (id, customer_id, email, name, role, is_active, created_at, updated_at) "
            "VALUES (?, ?, 'admin@life.com', 'Life Admin', 'admin', 1, ?, ?)",
            (USER_ID, CUST_ID, NOW_ISO, NOW_ISO))
    return db_file


@pytest.fixture()
def client(tmp_db, monkeypatch):
    monkeypatch.setattr(
        "poc.hierarchy.get_current_user",
        lambda: {"id": USER_ID, "email": "admin@life.com", "name": "Life Admin",
                 "role": "admin", "customer_id": CUST_ID})
    from poc.web.app import create_app
    return TestClient(create_app(), raise_server_exceptions=False)


def _conv(conn, conv_id, *, silent_days: float, status="active", customer_id=CUST_ID,
          stale_override=None, done_override=None, dismissed=0):
    conn.execute(
        "INSERT INTO conversations (id, customer_id, title, status, last_activity_at, "
        "stale_after_days, closed_after_days, dismissed, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (conv_id, customer_id, conv_id, status, _days_ago(silent_days),
         stale_override, done_override, dismissed, NOW_ISO, NOW_ISO))


def _row(conv_id):
    with get_connection() as conn:
        return dict(conn.execute("SELECT * FROM conversations WHERE id = ?", (conv_id,)).fetchone())


class TestPass:
    def test_moves_by_silence(self, tmp_db):
        """CONV-DNT-14."""
        with get_connection() as conn:
            _conv(conn, "fresh", silent_days=3)
            _conv(conn, "quiet", silent_days=20)
            _conv(conn, "silent", silent_days=45)
            _conv(conn, "edge-stale", silent_days=14)
            _conv(conn, "edge-done", silent_days=30, status="stale")
        stats = run_lifecycle_pass(now_iso=NOW_ISO)
        assert stats == {"checked": 5, "stale": 2, "reactivated": 0, "done": 2}
        assert _row("fresh")["status"] == "active"
        assert _row("quiet")["status"] == "stale"
        assert _row("edge-stale")["status"] == "stale"
        silent = _row("silent")
        assert silent["status"] == "done"
        assert silent["done_reason"] == "timer"
        assert silent["done_by"] is None
        assert silent["done_at"] == NOW_ISO
        assert _row("edge-done")["status"] == "done"
        # A second pass changes nothing.
        assert run_lifecycle_pass(now_iso=NOW_ISO) == {"checked": 3, "stale": 0, "reactivated": 0, "done": 0}

    def test_leaves_done_and_dismissed_alone_and_reactivates_stale(self, tmp_db):
        """CONV-DNT-15."""
        with get_connection() as conn:
            _conv(conn, "user-done", silent_days=100, status="done")
            conn.execute("UPDATE conversations SET done_by = ?, done_reason = 'user' WHERE id = 'user-done'",
                         (USER_ID,))
            _conv(conn, "tomb", silent_days=100, dismissed=1)
            _conv(conn, "woke", silent_days=2, status="stale")
            _conv(conn, "no-activity", silent_days=0)
            conn.execute("UPDATE conversations SET last_activity_at = NULL WHERE id = 'no-activity'")
        stats = run_lifecycle_pass(now_iso=NOW_ISO)
        assert stats == {"checked": 1, "stale": 0, "reactivated": 1, "done": 0}
        assert _row("user-done")["status"] == "done" and _row("user-done")["done_reason"] == "user"
        assert _row("tomb")["status"] == "active"
        assert _row("woke")["status"] == "active"
        assert _row("no-activity")["status"] == "active"

    def test_silence_clock_restarts_at_user_reopen(self, tmp_db):
        """CONV-DNT-15 — a reopened conversation is not closed again on the next pass."""
        with get_connection() as conn:
            _conv(conn, "old", silent_days=90)
            conn.execute(
                "UPDATE conversations SET status = 'active', reopened_at = ?, reopened_reason = 'user' "
                "WHERE id = 'old'", (_days_ago(1),))
            _conv(conn, "old-inbound", silent_days=90)
            conn.execute(
                "UPDATE conversations SET reopened_at = ?, reopened_reason = 'inbound' "
                "WHERE id = 'old-inbound'", (_days_ago(1),))
        run_lifecycle_pass(now_iso=NOW_ISO)
        assert _row("old")["status"] == "active"
        # An inbound reopen also refreshed last_activity_at in real life; here the
        # stale activity stamp stands alone, so the clock runs from it.
        assert _row("old-inbound")["status"] == "done"
        # Fifteen days after the user reopen the clock reaches stale.
        later = (NOW + timedelta(days=15)).isoformat()
        run_lifecycle_pass(now_iso=later)
        assert _row("old")["status"] == "stale"

    def test_override_and_kill_switch(self, tmp_db):
        """CONV-DNT-16."""
        with get_connection() as conn:
            _conv(conn, "patient", silent_days=45, stale_override=60, done_override=90)
            _conv(conn, "hasty", silent_days=5, stale_override=2, done_override=4)
            _conv(conn, "low-done", silent_days=10, stale_override=20, done_override=5)
        run_lifecycle_pass(now_iso=NOW_ISO)
        assert _row("patient")["status"] == "active"
        assert _row("hasty")["status"] == "done"
        # done override below the stale override is raised to it: 10 days < 20 → active
        assert _row("low-done")["status"] == "active"

        set_setting(CUST_ID, "conversation_timers_enabled", "false", scope="system")
        with get_connection() as conn:
            _conv(conn, "frozen", silent_days=400)
        stats = run_lifecycle_pass(now_iso=NOW_ISO)
        assert stats["done"] == 0 and _row("frozen")["status"] == "active"

    def test_tenant_settings_govern_and_are_clamped(self, tmp_db):
        """CONV-DNT-16."""
        set_setting(CUST_ID, "conversation_stale_days", "7", scope="system")
        set_setting(CUST_ID, "conversation_done_days", "3", scope="system")  # below stale → raised
        assert thresholds_for(CUST_ID) == {"stale_days": 7, "done_days": 7, "enabled": True}
        assert thresholds_for(None) == {"stale_days": 14, "done_days": 30, "enabled": True}
        with get_connection() as conn:
            _conv(conn, "week", silent_days=8)
        run_lifecycle_pass(now_iso=NOW_ISO)
        assert _row("week")["status"] == "done"

    def test_timed_done_reopens_on_inbound_and_stale_clears_on_any_link(self, tmp_db):
        """TDD §9.18."""
        with get_connection() as conn:
            _conv(conn, "silent", silent_days=45)
            _conv(conn, "quiet", silent_days=20)
        run_lifecycle_pass(now_iso=NOW_ISO)
        with get_connection() as conn:
            for cid, direction in (("in-1", "inbound"), ("out-1", "outbound")):
                conn.execute(
                    "INSERT INTO communications (id, channel, direction, timestamp, created_at, updated_at) "
                    "VALUES (?, 'email', ?, ?, ?, ?)", (cid, direction, NOW_ISO, NOW_ISO, NOW_ISO))
            assert link_communications(conn, "silent", ["in-1"], assignment_source="sync")["reopened"]
            link_communications(conn, "quiet", ["out-1"], assignment_source="composed")
        silent = _row("silent")
        assert silent["status"] == "active" and silent["done_reason"] is None
        assert silent["reopened_reason"] == "inbound"
        quiet = _row("quiet")
        assert quiet["status"] == "active" and quiet["reopened_reason"] is None

    def test_mark_done_records_user_reason(self, tmp_db):
        with get_connection() as conn:
            _conv(conn, "c", silent_days=1)
            mark_done(conn, ["c"], user_id=USER_ID)
        assert _row("c")["done_reason"] == "user"


class TestSettingsApi:
    def test_thresholds_clamped_and_ordered(self, client, tmp_db):
        """CONV-DNT-17."""
        r = client.put("/api/v1/settings/system",
                       json={"conversation_stale_days": "40", "conversation_done_days": "10",
                             "conversation_timers_enabled": "no"})
        assert r.status_code == 200
        s = client.get("/api/v1/settings/system").json()
        assert s["conversation_stale_days"] == "40"
        assert s["conversation_done_days"] == "40"
        assert s["conversation_timers_enabled"] == "false"
        r = client.put("/api/v1/settings/system", json={"conversation_done_days": "9999"})
        assert r.status_code == 200
        assert client.get("/api/v1/settings/system").json()["conversation_done_days"] == "365"
        r = client.put("/api/v1/settings/system", json={"conversation_stale_days": "soon"})
        assert r.status_code == 400

    def test_full_payload_reports_defaults(self, client, tmp_db):
        with get_connection() as conn:
            _conv(conn, "c", silent_days=1)
            _conv(conn, "o", silent_days=1, stale_override=5)
        c = client.get("/api/v1/conversations/c/full").json()
        assert c["stale_after_days"] is None and c["stale_after_days_default"] == 14
        assert c["closed_after_days"] is None and c["closed_after_days_default"] == 30
        assert c["done_reason"] is None
        o = client.get("/api/v1/conversations/o/full").json()
        assert o["stale_after_days"] == 5


class TestSchedulerHook:
    def test_pass_runs_on_first_tick_then_once_per_interval(self, tmp_db, monkeypatch):
        """CONV-DNT-17."""
        calls: list[str] = []
        monkeypatch.setattr("poc.conversation_lifecycle.run_lifecycle_pass",
                            lambda *, now_iso=None: calls.append(now_iso) or {})
        s = SyncScheduler()
        s.tick(NOW)
        s.tick(NOW + timedelta(seconds=LIFECYCLE_INTERVAL_SECONDS - 1))
        assert len(calls) == 1
        s.tick(NOW + timedelta(seconds=LIFECYCLE_INTERVAL_SECONDS))
        assert len(calls) == 2
