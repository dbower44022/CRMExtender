"""Per-account sync scheduler (MAIL-13; MAIL-T07).

The scheduler's tick is driven directly so nothing depends on wall-clock
timing; account syncs and the post pass are stubbed with instrumented
fakes that run on the scheduler's worker threads.
"""

from __future__ import annotations

import threading
import time
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from poc.database import get_connection, init_db
from poc.scheduler import MIN_INTERVAL_SECONDS, SyncScheduler

_NOW = datetime.now(timezone.utc).isoformat()
CUST_ID = "cust-sched"
USER_ID = "user-sched"
ACCT_A = "acct-sched-a"
ACCT_B = "acct-sched-b"


@pytest.fixture()
def tmp_db(tmp_path, monkeypatch):
    db_file = tmp_path / "test.db"
    monkeypatch.setattr("poc.config.DB_PATH", db_file)
    monkeypatch.setattr("poc.config.CRM_AUTH_ENABLED", False)
    init_db(db_file)
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO customers (id, name, slug, is_active, created_at, updated_at) "
            "VALUES (?, 'S Org', 's', 1, ?, ?)", (CUST_ID, _NOW, _NOW))
        conn.execute(
            "INSERT INTO users (id, customer_id, email, name, role, is_active, created_at, updated_at) "
            "VALUES (?, ?, 'a@s.com', 'A', 'admin', 1, ?, ?)", (USER_ID, CUST_ID, _NOW, _NOW))
        for acct, email in ((ACCT_A, "a@s.com"), (ACCT_B, "b@s.com")):
            conn.execute(
                "INSERT INTO provider_accounts (id, customer_id, provider, email_address, auth_token_path, "
                "sync_cursor, initial_sync_done, is_active, created_at, updated_at) "
                "VALUES (?, ?, 'gmail', ?, '/tmp/t.json', 'c', 1, 1, ?, ?)", (acct, CUST_ID, email, _NOW, _NOW))
            conn.execute(
                "INSERT INTO user_provider_accounts (id, user_id, account_id, role, created_at) "
                "VALUES (?, ?, ?, 'owner', ?)", (str(uuid.uuid4()), USER_ID, acct, _NOW))
    return db_file


class Fakes:
    """Instrumented stand-ins for sync_account and post_sync_pass."""

    def __init__(self, monkeypatch, *, delay: float = 0.0, fail_account: str | None = None):
        self.events: list = []
        self.active: set[str] = set()
        self.overlap = False
        self.lock = threading.Lock()
        self.delay = delay
        self.fail_account = fail_account

        def sync_account(account, *, customer_id, user_id, gmail_limiter):
            aid = account["id"]
            with self.lock:
                if aid in self.active:
                    self.overlap = True
                self.active.add(aid)
                self.events.append(("sync", aid, user_id))
            time.sleep(self.delay)
            with self.lock:
                self.active.discard(aid)
            if aid == self.fail_account:
                raise RuntimeError("boom")
            return {"contacts": 1, "emails_fetched": 2, "actions_pushed": 0,
                    "actions_failed": 0, "errors": []}

        def post_sync_pass(*, customer_id, since_iso, gmail_limiter=None, claude_limiter=None):
            with self.lock:
                self.events.append(("post", customer_id))
            return {"triaged": 0, "summarized": 3, "enriched": 0,
                    "duplicate_candidates": 0, "errors": []}

        monkeypatch.setattr("poc.sync_service.sync_account", sync_account)
        monkeypatch.setattr("poc.sync_service.post_sync_pass", post_sync_pass)

    def syncs(self):
        return [e[1] for e in self.events if e[0] == "sync"]


def _settle(s: SyncScheduler, fakes: Fakes, rounds: int = 5):
    """Drive ticks until the post pass has run or rounds expire."""
    for _ in range(rounds):
        assert s.wait_idle(5)
        s.tick()
        assert s.wait_idle(5)
        if any(e[0] == "post" for e in fakes.events):
            return


class TestTiming:
    def test_first_tick_runs_every_account_then_post_pass(self, tmp_db, monkeypatch):
        fakes = Fakes(monkeypatch)
        s = SyncScheduler()
        started = s.tick()
        assert set(started) == {ACCT_A, ACCT_B}
        _settle(s, fakes)
        assert sorted(fakes.syncs()) == [ACCT_A, ACCT_B]
        assert fakes.events[-1] == ("post", CUST_ID)
        # the owner is resolved for created_by
        assert all(e[2] == USER_ID for e in fakes.events if e[0] == "sync")

    def test_not_due_until_interval_elapses(self, tmp_db, monkeypatch):
        fakes = Fakes(monkeypatch)
        s = SyncScheduler()
        t0 = datetime.now(timezone.utc)
        s.tick(t0); _settle(s, fakes)
        assert len(fakes.syncs()) == 2
        assert s.tick(t0 + timedelta(seconds=30)) == []
        later = datetime.now(timezone.utc) + timedelta(seconds=MIN_INTERVAL_SECONDS * 3)
        assert set(s.tick(later)) == {ACCT_A, ACCT_B}
        assert s.wait_idle(5)

    def test_interval_setting_is_honored_and_floored(self, tmp_db, monkeypatch):
        from poc.settings import set_setting
        set_setting(CUST_ID, "mail_sync_interval_seconds", "10", scope="system")
        s = SyncScheduler()
        assert s.interval_seconds(CUST_ID) == MIN_INTERVAL_SECONDS
        set_setting(CUST_ID, "mail_sync_interval_seconds", "600", scope="system")
        assert s.interval_seconds(CUST_ID) == 600

    def test_same_account_never_overlaps(self, tmp_db, monkeypatch):
        fakes = Fakes(monkeypatch, delay=0.3)
        s = SyncScheduler()
        s.tick()
        s.request_run(ACCT_A)
        s.tick()                      # A still running: must not start again
        assert s.wait_idle(5)
        assert fakes.overlap is False
        _settle(s, fakes)
        # the request survives and runs once A is free
        assert fakes.syncs().count(ACCT_A) == 2

    def test_pause_blocks_timed_runs_but_not_requests(self, tmp_db, monkeypatch):
        fakes = Fakes(monkeypatch)
        s = SyncScheduler()
        s.pause()
        assert s.tick() == []
        s.request_run(ACCT_B)
        assert s.tick() == [ACCT_B]
        assert s.wait_idle(5)
        s.resume()
        assert set(s.tick()) == {ACCT_A}  # B just ran and is not due; A is
        assert s.wait_idle(5)

    def test_sync_enabled_false_stops_timers(self, tmp_db, monkeypatch):
        from poc.settings import set_setting
        set_setting(CUST_ID, "sync_enabled", "false", scope="system")
        fakes = Fakes(monkeypatch)
        s = SyncScheduler()
        assert s.tick() == []
        assert s.request_run() is True
        assert set(s.tick()) == {ACCT_A, ACCT_B}
        _settle(s, fakes)

    def test_account_failure_is_recorded_not_raised(self, tmp_db, monkeypatch):
        fakes = Fakes(monkeypatch, fail_account=ACCT_B)
        s = SyncScheduler()
        s.tick(); _settle(s, fakes)
        st = s.status()["accounts"]
        assert st[ACCT_B]["last_error"] == "boom" and st[ACCT_B]["running"] is False
        assert st[ACCT_A]["last_error"] is None and st[ACCT_A]["last_result"]["emails_fetched"] == 2


class TestManualRun:
    def test_manual_run_aggregates_into_legacy_status(self, tmp_db, monkeypatch):
        fakes = Fakes(monkeypatch)
        s = SyncScheduler()
        assert s.request_run() is True
        assert s.request_run() is False          # already running → 409 contract
        assert s.legacy_status()["running"] is True
        _settle(s, fakes)
        legacy = s.legacy_status()
        assert legacy["running"] is False and legacy["completed_at"]
        assert legacy["result"]["accounts"] == 2
        assert legacy["result"]["emails_fetched"] == 4 and legacy["result"]["summarized"] == 3
        assert legacy["result"]["errors"] == []
        assert s.request_run() is True           # free again

    def test_manual_run_with_no_accounts_completes(self, tmp_db, monkeypatch):
        Fakes(monkeypatch)
        with get_connection() as conn:
            conn.execute("UPDATE provider_accounts SET is_active = 0")
        s = SyncScheduler()
        assert s.request_run() is True
        legacy = s.legacy_status()
        assert legacy["running"] is False and "No accounts registered." in legacy["result"]["errors"]


class TestApi:
    def _client(self, monkeypatch, role="admin"):
        monkeypatch.setattr(
            "poc.hierarchy.get_current_user",
            lambda: {"id": USER_ID, "email": "a@s.com", "name": "A", "role": role, "customer_id": CUST_ID},
        )
        from poc.web.app import create_app
        return TestClient(create_app(), raise_server_exceptions=False)

    def test_sync_routes_use_running_scheduler(self, tmp_db, monkeypatch):
        fakes = Fakes(monkeypatch)
        import poc.scheduler as sched_mod
        s = SyncScheduler(tick_seconds=3600)
        s.start()
        monkeypatch.setattr(sched_mod, "_scheduler", s)
        try:
            client = self._client(monkeypatch)
            assert client.post("/api/v1/sync").status_code == 200
            assert client.post("/api/v1/sync").status_code == 409
            status = client.get("/api/v1/sync/status").json()
            assert status["running"] is True and status["scheduler"]["enabled"] is True
            assert set(status["scheduler"]["accounts"]) <= {ACCT_A, ACCT_B} or status["scheduler"]["accounts"] == {}
            assert client.post("/api/v1/sync/pause").json() == {"paused": True}
            assert client.post("/api/v1/sync/resume").json() == {"paused": False}
            resp = client.post(f"/api/v1/settings/accounts/{ACCT_A}/sync")
            assert resp.status_code == 200 and resp.json()["status"] == "requested"
            assert client.post("/api/v1/settings/accounts/nope/sync").status_code == 404
            # drive the requested work to completion on the scheduler
            _settle(s, fakes)
        finally:
            s.stop()

    def test_pause_is_admin_only_and_409_without_scheduler(self, tmp_db, monkeypatch):
        import poc.scheduler as sched_mod
        monkeypatch.setattr(sched_mod, "_scheduler", None)
        client = self._client(monkeypatch, role="user")
        assert client.post("/api/v1/sync/pause").status_code == 403
        admin = self._client(monkeypatch, role="admin")
        assert admin.post("/api/v1/sync/pause").status_code == 409
        assert admin.get("/api/v1/sync/status").json()["scheduler"] == {"enabled": False}
