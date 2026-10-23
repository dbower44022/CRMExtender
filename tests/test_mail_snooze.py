"""Snooze (MAIL-17; MAIL-T11): hides at once, labels at the provider, returns unread when due."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from poc import events
from poc.database import get_connection, init_db
from poc.mail_actions import MailActionError, enqueue, push_pending
from poc.mail_snooze import SnoozeError, parse_return_at, return_due
from poc.mail_threads import folders, thread_list
from poc.models import ParsedEmail
from poc.providers import ActionKind, ActionResult, ActionStatus
from poc.sync import _store_thread, load_contact_index

_NOW = datetime.now(timezone.utc).isoformat()
CUST_ID = "cust-snz"
USER_ID = "user-snz"
ACCOUNT_ID = "acct-snz"
OWNER = "owner@snz.com"


@pytest.fixture()
def tmp_db(tmp_path, monkeypatch):
    db_file = tmp_path / "test.db"
    monkeypatch.setattr("poc.config.DB_PATH", db_file)
    monkeypatch.setattr("poc.config.CRM_AUTH_ENABLED", False)
    init_db(db_file)
    with get_connection() as conn:
        conn.execute("INSERT INTO customers (id, name, slug, is_active, created_at, updated_at) "
                     "VALUES (?, 'Z', 'z', 1, ?, ?)", (CUST_ID, _NOW, _NOW))
        conn.execute("INSERT INTO users (id, customer_id, email, name, role, is_active, created_at, updated_at) "
                     "VALUES (?, ?, ?, 'U', 'admin', 1, ?, ?)", (USER_ID, CUST_ID, OWNER, _NOW, _NOW))
        conn.execute("INSERT INTO provider_accounts (id, customer_id, provider, email_address, auth_token_path, "
                     "sync_cursor, initial_sync_done, is_active, created_at, updated_at) "
                     "VALUES (?, ?, 'gmail', ?, '/tmp/t.json', 'c', 1, 1, ?, ?)", (ACCOUNT_ID, CUST_ID, OWNER, _NOW, _NOW))
        conn.execute("INSERT INTO user_provider_accounts (id, user_id, account_id, role, created_at) "
                     "VALUES (?, ?, ?, 'owner', ?)", (str(uuid.uuid4()), USER_ID, ACCOUNT_ID, _NOW))
    return db_file


def _store(thread="t-1", n=2) -> list[dict]:
    emails = [ParsedEmail(
        message_id=f"pm-{uuid.uuid4().hex[:8]}", thread_id=thread, subject="Lunch?",
        sender="A <a@x.com>", sender_email="a@x.com", recipients=[OWNER],
        date=datetime(2026, 3, 1, 12 + i, tzinfo=timezone.utc), body_plain="b", snippet="bistro?",
        label_ids=["INBOX", "UNREAD"], is_read=True,
    ) for i in range(n)]
    with get_connection() as conn:
        _store_thread(conn, ACCOUNT_ID, OWNER, emails, load_contact_index(), customer_id=CUST_ID, created_by=USER_ID)
        return [dict(r) for r in conn.execute(
            "SELECT * FROM communications WHERE account_id = ? ORDER BY timestamp", (ACCOUNT_ID,))]


def _labels(comm_id: str) -> list[str]:
    with get_connection() as conn:
        return sorted(r[0] for r in conn.execute(
            "SELECT ml.provider_label_id FROM communication_labels cl JOIN mailbox_labels ml ON ml.id = cl.label_id "
            "WHERE cl.communication_id = ?", (comm_id,)))


def _inbox_threads() -> list[str]:
    with get_connection() as conn:
        return [t["thread_id"] for t in thread_list(conn, account_ids=[ACCOUNT_ID], folder="inbox")["items"]]


def _snoozed() -> list[dict]:
    with get_connection() as conn:
        return thread_list(conn, account_ids=[ACCOUNT_ID], folder="snoozed")["items"]


class TestReturnAt:
    def test_requires_future_iso(self):
        now = datetime(2026, 10, 11, 12, tzinfo=timezone.utc)
        assert parse_return_at("2026-10-12T09:00:00Z", now=now) == "2026-10-12T09:00:00+00:00"
        with pytest.raises(SnoozeError):
            parse_return_at("2026-10-11T11:00:00Z", now=now)
        with pytest.raises(SnoozeError):
            parse_return_at("tomorrow", now=now)
        with pytest.raises(SnoozeError):
            parse_return_at(None, now=now)


class TestSnoozeLifecycle:
    def test_hides_labels_and_returns_unread(self, tmp_db):
        rows = _store()
        ids = [r["id"] for r in rows]
        due = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()

        with get_connection() as conn:
            action = enqueue(conn, account_id=ACCOUNT_ID, kind="snooze", communication_ids=ids,
                             payload={"return_at": due}, created_by=USER_ID)
        assert action["action"] == "snooze" and action["status"] == "pending"
        # Hidden at once: no Inbox label locally, thread in the Snoozed folder with its return time.
        assert all("INBOX" not in _labels(i) for i in ids)
        assert _inbox_threads() == []
        snoozed = _snoozed()
        assert [t["thread_id"] for t in snoozed] == ["t-1"]
        assert snoozed[0]["snoozed_until"].startswith(due[:16])
        with get_connection() as conn:
            f = folders(conn, account_ids=[ACCOUNT_ID])
        assert f["unified"]["snoozed"]["total"] == 1

        # At the provider: archive + CRMExtender/Snoozed label (the adapter finds or creates it).
        provider = _recording_provider()
        push_pending({"id": ACCOUNT_ID}, None, provider)
        kinds = [a.kind for a in provider.seen]
        assert kinds == [ActionKind.SNOOZE]
        assert provider.seen[0].payload["return_at"] == parse_return_at(due)

        # Not due yet: nothing returns.
        assert return_due() == []
        assert _snoozed() and _inbox_threads() == []

        # Due: back in the inbox, unread, unsnooze queued, pop-up event published.
        q = events.subscribe()
        try:
            returned = return_due(now_iso=(datetime.now(timezone.utc) + timedelta(hours=3)).isoformat())
        finally:
            events.unsubscribe(q)
        assert [r["thread_id"] for r in returned] == ["t-1"]
        assert _inbox_threads() == ["t-1"] and _snoozed() == []
        with get_connection() as conn:
            unread = [r[0] for r in conn.execute(
                "SELECT is_read FROM communications WHERE account_id = ?", (ACCOUNT_ID,))]
            pending = [r[0] for r in conn.execute(
                "SELECT action FROM mail_actions WHERE account_id = ? AND status = 'pending'", (ACCOUNT_ID,))]
        assert unread == [0, 0] and pending == ["unsnooze"]
        evt = q.get(timeout=1)
        assert evt["type"] == "mail.new" and evt["reason"] == "snooze_returned"
        assert evt["items"][0]["thread_id"] == "t-1" and evt["items"][0]["known_contact"] is True
        push_pending({"id": ACCOUNT_ID}, None, provider)
        assert [a.kind for a in provider.seen] == [ActionKind.SNOOZE, ActionKind.UNSNOOZE]
        # Idempotent: a second pass finds nothing due.
        assert return_due(now_iso=(datetime.now(timezone.utc) + timedelta(days=1)).isoformat()) == []

    def test_snooze_requires_return_time(self, tmp_db):
        ids = [r["id"] for r in _store()]
        with get_connection() as conn, pytest.raises(MailActionError):
            enqueue(conn, account_id=ACCOUNT_ID, kind="snooze", communication_ids=ids, created_by=USER_ID)

    def test_resnooze_replaces_earlier_time(self, tmp_db):
        ids = [r["id"] for r in _store()]
        t1 = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        t2 = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
        with get_connection() as conn:
            enqueue(conn, account_id=ACCOUNT_ID, kind="snooze", communication_ids=ids, payload={"return_at": t1}, created_by=USER_ID)
            enqueue(conn, account_id=ACCOUNT_ID, kind="snooze", communication_ids=ids, payload={"return_at": t2}, created_by=USER_ID)
            n_open = conn.execute("SELECT COUNT(*) FROM mail_snoozes WHERE status = 'snoozed'").fetchone()[0]
        assert n_open == 1
        assert return_due(now_iso=(datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()) == []
        assert _snoozed()[0]["snoozed_until"].startswith(t2[:16])


class TestApi:
    def test_snooze_through_actions_endpoint(self, tmp_db, monkeypatch):
        from poc.web.app import create_app
        rows = _store()
        monkeypatch.setattr("poc.config.CRM_AUTH_ENABLED", False)
        client = TestClient(create_app())
        due = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
        r = client.post("/api/v1/mail/actions", json={
            "action": "snooze", "threads": [{"account_id": ACCOUNT_ID, "thread_id": "t-1"}],
            "payload": {"return_at": due}})
        assert r.status_code == 201, r.text
        r = client.get("/api/v1/mail/threads", params={"folder": "snoozed"})
        assert r.status_code == 200 and [t["thread_id"] for t in r.json()["items"]] == ["t-1"]
        bad = client.post("/api/v1/mail/actions", json={
            "action": "snooze", "communication_ids": [rows[0]["id"]], "payload": {"return_at": "2001-01-01T00:00:00Z"}})
        assert bad.status_code == 400 and "future" in bad.text


def _recording_provider():
    class P:
        seen: list = []

        def apply_action(self, session, action, *, rate_limiter=None):
            self.seen.append(action)
            return ActionResult(ActionStatus.PUSHED)
    p = P(); p.seen = []
    return p
