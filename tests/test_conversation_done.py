"""Conversation Done state (Base PRD §6.4, §8.9–8.11; TDD §9.8–9.13).

Covers CONV-DNT-02 … CONV-DNT-10 from the Base PRD §12.2 test plan.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from poc.conversation_links import link_communications, mark_done, reopen
from poc.database import get_connection, init_db
from poc.views.engine import execute_view

_NOW = datetime.now(timezone.utc).isoformat()

CUST_ID = "cust-done-test"
USER_ID = "user-done-admin"


@pytest.fixture()
def tmp_db(tmp_path, monkeypatch):
    db_file = tmp_path / "test.db"
    monkeypatch.setattr("poc.config.DB_PATH", db_file)
    monkeypatch.setattr("poc.config.CRM_AUTH_ENABLED", False)
    init_db(db_file)
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO customers (id, name, slug, is_active, created_at, updated_at) "
            "VALUES (?, 'Done Org', 'done', 1, ?, ?)", (CUST_ID, _NOW, _NOW))
        conn.execute(
            "INSERT INTO users "
            "(id, customer_id, email, name, role, is_active, created_at, updated_at) "
            "VALUES (?, ?, 'admin@done.com', 'Done Admin', 'admin', 1, ?, ?)",
            (USER_ID, CUST_ID, _NOW, _NOW))
    return db_file


@pytest.fixture()
def client(tmp_db, monkeypatch):
    monkeypatch.setattr(
        "poc.hierarchy.get_current_user",
        lambda: {"id": USER_ID, "email": "admin@done.com", "name": "Done Admin",
                 "role": "admin", "customer_id": CUST_ID})
    from poc.web.app import create_app
    return TestClient(create_app(), raise_server_exceptions=False)


def _conversation(conn, conv_id="conv-1", *, status="active", customer_id=CUST_ID,
                  ai_status="open"):
    conn.execute(
        "INSERT INTO conversations (id, customer_id, title, status, ai_status, "
        "ai_summarized_at, communication_count, last_activity_at, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?, ?)",
        (conv_id, customer_id, f"Conversation {conv_id}", status, ai_status,
         _NOW, "2026-01-01T00:00:00+00:00", _NOW, _NOW))


def _communication(conn, comm_id, *, direction="inbound", timestamp="2026-02-01T00:00:00+00:00"):
    conn.execute(
        "INSERT INTO communications (id, channel, direction, timestamp, created_at, updated_at) "
        "VALUES (?, 'email', ?, ?, ?, ?)", (comm_id, direction, timestamp, _NOW, _NOW))


def _row(conv_id="conv-1"):
    with get_connection() as conn:
        return dict(conn.execute("SELECT * FROM conversations WHERE id = ?", (conv_id,)).fetchone())


# ---------------------------------------------------------------------------
# Helper-level behavior
# ---------------------------------------------------------------------------

class TestLinkHelper:
    def test_inbound_reopens_done_conversation(self, tmp_db):
        """CONV-DNT-04."""
        with get_connection() as conn:
            _conversation(conn, status="done")
            conn.execute("UPDATE conversations SET done_at = ?, done_by = ? WHERE id = 'conv-1'",
                         (_NOW, USER_ID))
            _communication(conn, "in-1", direction="inbound")
            result = link_communications(conn, "conv-1", ["in-1"], assignment_source="sync")
        assert result == {"linked": 1, "reopened": True}
        row = _row()
        assert row["status"] == "active"
        assert row["reopened_reason"] == "inbound"
        assert row["reopened_at"] is not None
        assert row["done_at"] is None and row["done_by"] is None
        assert row["ai_summarized_at"] is None
        assert row["communication_count"] == 1
        assert row["last_activity_at"] == "2026-02-01T00:00:00+00:00"

    def test_outbound_updates_activity_but_stays_done(self, tmp_db):
        """CONV-DNT-05."""
        with get_connection() as conn:
            _conversation(conn, status="done")
            _communication(conn, "out-1", direction="outbound", timestamp="2026-03-01T00:00:00+00:00")
            result = link_communications(conn, "conv-1", ["out-1"], assignment_source="composed")
        assert result == {"linked": 1, "reopened": False}
        row = _row()
        assert row["status"] == "done"
        assert row["reopened_reason"] is None
        assert row["communication_count"] == 1
        assert row["last_activity_at"] == "2026-03-01T00:00:00+00:00"
        assert row["ai_summarized_at"] is None  # summary still re-queued

    def test_relinking_existing_rows_is_a_no_op(self, tmp_db):
        with get_connection() as conn:
            _conversation(conn, status="done")
            _communication(conn, "in-1")
            link_communications(conn, "conv-1", ["in-1"], assignment_source="sync")
            reopen(conn, ["conv-1"], user_id=USER_ID)
            mark_done(conn, ["conv-1"], user_id=USER_ID)
            result = link_communications(conn, "conv-1", ["in-1"], assignment_source="sync")
        assert result == {"linked": 0, "reopened": False}
        assert _row()["status"] == "done"

    def test_mark_done_and_reopen_helpers(self, tmp_db):
        """CONV-DNT-02 / CONV-DNT-03 at helper level."""
        with get_connection() as conn:
            _conversation(conn)
            assert mark_done(conn, ["conv-1"], user_id=USER_ID) == ["conv-1"]
            assert mark_done(conn, ["conv-1"], user_id=USER_ID) == []
        row = _row()
        assert row["status"] == "done" and row["done_by"] == USER_ID
        assert row["done_at"] is not None and row["updated_by"] == USER_ID
        with get_connection() as conn:
            assert reopen(conn, ["conv-1"], user_id=USER_ID) == ["conv-1"]
            assert reopen(conn, ["conv-1"], user_id=USER_ID) == []
        row = _row()
        assert row["status"] == "active" and row["reopened_reason"] == "user"
        assert row["done_at"] is None and row["done_by"] is None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

class TestDoneEndpoints:
    def test_mark_done_records_audit_and_skips_repeat(self, client, tmp_db):
        """CONV-DNT-02."""
        with get_connection() as conn:
            _conversation(conn, "conv-1")
            _conversation(conn, "conv-2")
        r = client.post("/api/v1/conversations/done", json={"ids": ["conv-1", "conv-2"]})
        assert r.status_code == 200
        assert r.json() == {"done": 2, "ids": ["conv-1", "conv-2"], "skipped_unchanged": 0, "skipped_foreign": 0}
        row = _row("conv-1")
        assert row["status"] == "done"
        assert row["done_by"] == USER_ID and row["updated_by"] == USER_ID
        assert row["done_at"] is not None
        r = client.post("/api/v1/conversations/done", json={"ids": ["conv-1"]})
        assert r.json() == {"done": 0, "ids": [], "skipped_unchanged": 1, "skipped_foreign": 0}

    def test_reopen_by_user(self, client, tmp_db):
        """CONV-DNT-03."""
        with get_connection() as conn:
            _conversation(conn, status="done")
            conn.execute("UPDATE conversations SET done_at = ?, done_by = ? WHERE id = 'conv-1'",
                         (_NOW, USER_ID))
        r = client.post("/api/v1/conversations/reopen", json={"ids": ["conv-1"]})
        assert r.json() == {"reopened": 1, "ids": ["conv-1"], "skipped_unchanged": 0, "skipped_foreign": 0}
        row = _row()
        assert row["status"] == "active"
        assert row["reopened_reason"] == "user" and row["reopened_at"] is not None
        assert row["done_at"] is None and row["done_by"] is None
        r = client.post("/api/v1/conversations/reopen", json={"ids": ["conv-1"]})
        assert r.json()["skipped_unchanged"] == 1

    def test_foreign_tenant_is_skipped(self, client, tmp_db):
        """CONV-DNT-08."""
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO customers (id, name, slug, is_active, created_at, updated_at) "
                "VALUES ('cust-other', 'Other', 'other', 1, ?, ?)", (_NOW, _NOW))
            _conversation(conn, "conv-mine")
            _conversation(conn, "conv-theirs", customer_id="cust-other")
        r = client.post("/api/v1/conversations/done", json={"ids": ["conv-mine", "conv-theirs", "nope"]})
        assert r.json() == {"done": 1, "ids": ["conv-mine"], "skipped_unchanged": 0, "skipped_foreign": 2}
        assert _row("conv-theirs")["status"] == "active"

    def test_ids_required(self, client, tmp_db):
        assert client.post("/api/v1/conversations/done", json={}).status_code == 400
        assert client.post("/api/v1/conversations/reopen", json={"ids": []}).status_code == 400

    def test_done_leaves_ai_status_and_dismissed_alone(self, client, tmp_db):
        """CONV-DNT-10."""
        with get_connection() as conn:
            _conversation(conn, ai_status="open")
            conn.execute("UPDATE conversations SET dismissed = 1, dismissed_reason = 'archived' "
                         "WHERE id = 'conv-1'")
        client.post("/api/v1/conversations/done", json={"ids": ["conv-1"]})
        row = _row()
        assert row["status"] == "done"
        assert row["ai_status"] == "open"
        assert row["dismissed"] == 1 and row["dismissed_reason"] == "archived"

    def test_manual_assign_recomputes_activity(self, client, tmp_db):
        """CONV-DNT-06 — and an inbound manual link reopens a done conversation."""
        with get_connection() as conn:
            _conversation(conn, status="done")
            _communication(conn, "in-9", direction="inbound", timestamp="2026-04-01T00:00:00+00:00")
            conn.execute("UPDATE communications SET account_id = NULL WHERE id = 'in-9'")
        r = client.post("/api/v1/communications/assign",
                        json={"ids": ["in-9"], "conversation_id": "conv-1"})
        assert r.json() == {"assigned": 1, "skipped_existing": 0, "skipped_foreign": 0,
                            "reopened": True}
        row = _row()
        assert row["communication_count"] == 1
        assert row["last_activity_at"] == "2026-04-01T00:00:00+00:00"
        assert row["status"] == "active" and row["reopened_reason"] == "inbound"

    def test_payloads_carry_done_fields(self, client, tmp_db):
        """CONV-DNT-09."""
        with get_connection() as conn:
            _conversation(conn)
            mark_done(conn, ["conv-1"], user_id=USER_ID, now="2026-10-22T10:00:00+00:00")
        full = client.get("/api/v1/conversations/conv-1/full").json()
        assert full["status"] == "done"
        assert full["done_at"] == "2026-10-22T10:00:00+00:00"
        assert full["done_by_name"] == "Done Admin"
        assert full["reopened_at"] is None and full["reopened_reason"] is None
        preview = client.get("/api/v1/conversations/conv-1/preview").json()
        assert preview["status"] == "done"
        assert preview["done_at"] == "2026-10-22T10:00:00+00:00"
        assert "reopened_reason" in preview


# ---------------------------------------------------------------------------
# Grid default exclusion
# ---------------------------------------------------------------------------

class TestGridExclusion:
    COLUMNS = [{"field_key": "title"}, {"field_key": "status"}]

    def _seed(self):
        with get_connection() as conn:
            _conversation(conn, "conv-a", status="active")
            _conversation(conn, "conv-d", status="done")
            _conversation(conn, "conv-n", status="active")
            conn.execute("UPDATE conversations SET status = NULL WHERE id = 'conv-n'")

    def _ids(self, filters):
        with get_connection() as conn:
            rows, total = execute_view(
                conn, entity_type="conversation", columns=self.COLUMNS, filters=filters,
                sort_field="title", sort_direction="asc",
            )
        return [r["id"] for r in rows], total

    def test_done_hidden_by_default(self, tmp_db):
        """CONV-DNT-07."""
        self._seed()
        ids, total = self._ids([])
        assert ids == ["conv-a", "conv-n"] and total == 2

    def test_status_filter_overrides_the_rule(self, tmp_db):
        """CONV-DNT-07."""
        self._seed()
        ids, total = self._ids([{"field_key": "status", "operator": "equals", "value": "done"}])
        assert ids == ["conv-d"] and total == 1
        ids, _ = self._ids([{"field_key": "status", "operator": "is_not_empty", "value": None}])
        assert ids == ["conv-a", "conv-d"]

    def test_other_filters_keep_the_rule(self, tmp_db):
        self._seed()
        ids, _ = self._ids([{"field_key": "title", "operator": "contains", "value": "Conversation"}])
        assert ids == ["conv-a", "conv-n"]
