"""New-mail notifications (Mail Client MAIL-39)."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from poc import events
from poc.database import get_connection
from poc.mail_notify import new_inbox_messages, notification_mode, set_notification_mode
from poc.scheduler import SyncScheduler

from tests.test_scheduler import ACCT_A, ACCT_B, CUST_ID, USER_ID, Fakes, _settle, tmp_db  # noqa: F401


def _iso(dt):
    return dt.isoformat()


def _inbox_label(conn, aid):
    lid = str(uuid.uuid4())
    now = _iso(datetime.now(timezone.utc))
    conn.execute("INSERT INTO mailbox_labels (id, account_id, provider_label_id, name, kind, created_at, updated_at) "
                 "VALUES (?, ?, 'INBOX', 'INBOX', 'inbox', ?, ?)", (lid, aid, now, now))
    return lid


def _message(conn, aid, lid, *, sender, created, is_read=0, inbox=True, direction="inbound", subject="Hello"):
    cid = str(uuid.uuid4())
    conn.execute(
        """INSERT INTO communications (id, account_id, channel, timestamp, original_text, direction, source,
           sender_address, sender_name, subject, snippet, provider_message_id, provider_thread_id, is_read, is_current,
           created_at, updated_at)
           VALUES (?, ?, 'email', ?, 'hi', ?, 'auto_sync', ?, ?, ?, 'snip &#39;x&#39;', ?, ?, ?, 1, ?, ?)""",
        (cid, aid, _iso(created), direction, sender, f"{sender} <{sender}>", subject, f"pm-{cid}", f"t-{cid}",
         is_read, _iso(created), _iso(created)))
    if inbox:
        conn.execute("INSERT INTO communication_labels (communication_id, label_id) VALUES (?, ?)", (cid, lid))
    return cid


def _contact(conn, email, name):
    ct = str(uuid.uuid4())
    now = _iso(datetime.now(timezone.utc))
    conn.execute("INSERT INTO contacts (id, customer_id, name, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                 (ct, CUST_ID, name, now, now))
    conn.execute("INSERT INTO contact_identifiers (id, contact_id, type, value, created_at, updated_at) "
                 "VALUES (?, ?, 'email', ?, ?, ?)", (str(uuid.uuid4()), ct, email, now, now))
    return ct


class TestNewInboxMessages:
    def test_only_unread_inbound_inbox_mail_since_the_run(self, tmp_db):
        t0 = datetime.now(timezone.utc)
        with get_connection() as conn:
            lid = _inbox_label(conn, ACCT_A)
            _contact(conn, "ada@example.com", "Ada Lovelace")
            new_known = _message(conn, ACCT_A, lid, sender="ada@example.com", created=t0 + timedelta(seconds=2), subject="Lunch?")
            new_unknown = _message(conn, ACCT_A, lid, sender="spam@example.net", created=t0 + timedelta(seconds=1))
            _message(conn, ACCT_A, lid, sender="old@example.com", created=t0 - timedelta(minutes=5))       # before the run
            _message(conn, ACCT_A, lid, sender="read@example.com", created=t0 + timedelta(seconds=3), is_read=1)
            _message(conn, ACCT_A, lid, sender="arch@example.com", created=t0 + timedelta(seconds=3), inbox=False)
            _message(conn, ACCT_A, lid, sender="me@s.com", created=t0 + timedelta(seconds=3), direction="outbound")
        with get_connection() as conn:
            out = new_inbox_messages(conn, ACCT_A, _iso(t0))
        assert out["count"] == 2
        assert [i["communication_id"] for i in out["items"]] == [new_known, new_unknown]
        first = out["items"][0]
        assert first["known_contact"] is True and first["sender_name"] == "Ada Lovelace"
        assert first["subject"] == "Lunch?" and first["snippet"] == "snip 'x'" and first["thread_id"].startswith("t-")
        assert out["items"][1]["known_contact"] is False

    def test_cap_keeps_count(self, tmp_db):
        t0 = datetime.now(timezone.utc)
        with get_connection() as conn:
            lid = _inbox_label(conn, ACCT_A)
            for i in range(12):
                _message(conn, ACCT_A, lid, sender=f"p{i}@example.com", created=t0 + timedelta(seconds=i + 1))
        with get_connection() as conn:
            out = new_inbox_messages(conn, ACCT_A, _iso(t0))
        assert out["count"] == 12 and len(out["items"]) == 10


class TestSchedulerPublishesMailNew:
    def test_mail_new_after_sync_not_on_first_sync(self, tmp_db, monkeypatch):
        with get_connection() as conn:
            conn.execute("UPDATE provider_accounts SET initial_sync_done = 0 WHERE id = ?", (ACCT_B,))
        inserted: dict = {}

        def fake_sync(account, *, customer_id, user_id, gmail_limiter):
            with get_connection() as conn:
                lid = _inbox_label(conn, account["id"])
                inserted[account["id"]] = _message(conn, account["id"], lid, sender="x@example.com",
                                                   created=datetime.now(timezone.utc) + timedelta(seconds=1))
            return {"contacts": 0, "emails_fetched": 1, "actions_pushed": 0, "actions_failed": 0, "errors": []}

        fakes = Fakes(monkeypatch)
        monkeypatch.setattr("poc.sync_service.sync_account", fake_sync)
        q = events.subscribe()
        s = SyncScheduler(tick_seconds=3600)
        try:
            s.start()
            _settle(s, fakes, rounds=3)
            assert s.wait_idle(5)
        finally:
            s.stop()
            events.unsubscribe(q)
        got = []
        while not q.empty():
            got.append(q.get_nowait())
        new = [e for e in got if e["type"] == "mail.new"]
        assert [e["account_id"] for e in new] == [ACCT_A]          # B's first sync is history, not news
        assert new[0]["count"] == 1 and new[0]["items"][0]["communication_id"] == inserted[ACCT_A]


class TestNotificationSetting:
    def _client(self, monkeypatch):
        monkeypatch.setattr(
            "poc.hierarchy.get_current_user",
            lambda: {"id": USER_ID, "email": "a@s.com", "name": "A", "role": "admin", "customer_id": CUST_ID},
        )
        from poc.web.app import create_app
        return TestClient(create_app(), raise_server_exceptions=False)

    def test_default_set_and_listed(self, tmp_db, monkeypatch):
        assert notification_mode(CUST_ID, USER_ID, ACCT_A) == "known_contacts"
        client = self._client(monkeypatch)
        r = client.put(f"/api/v1/settings/accounts/{ACCT_A}/notifications", json={"mode": "all"})
        assert r.status_code == 200 and r.json()["mode"] == "all"
        assert client.put(f"/api/v1/settings/accounts/{ACCT_A}/notifications", json={"mode": "loud"}).status_code == 400
        assert client.put("/api/v1/settings/accounts/nope/notifications", json={"mode": "all"}).status_code == 404
        listed = {a["id"]: a for a in client.get("/api/v1/settings/accounts").json()}
        assert listed[ACCT_A]["notifications"] == "all" and listed[ACCT_B]["notifications"] == "known_contacts"
        set_notification_mode(CUST_ID, USER_ID, ACCT_B, "none")
        assert notification_mode(CUST_ID, USER_ID, ACCT_B) == "none"
