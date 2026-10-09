"""Folders, thread list, thread detail (MAIL-16; MAIL-T10 read half)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from poc.database import get_connection, init_db
from poc.mail_threads import folders, thread_detail, thread_list
from poc.models import ParsedEmail
from poc.sync import _store_thread, load_contact_index

_NOW = datetime.now(timezone.utc).isoformat()
CUST_ID = "cust-thr"
USER_ID = "user-thr"
OTHER_USER = "user-thr-other"
ACCT_A = "acct-thr-a"
ACCT_B = "acct-thr-b"
OWNER_A = "owner@a.com"
OWNER_B = "owner@b.com"


@pytest.fixture()
def tmp_db(tmp_path, monkeypatch):
    db_file = tmp_path / "test.db"
    monkeypatch.setattr("poc.config.DB_PATH", db_file)
    monkeypatch.setattr("poc.config.CRM_AUTH_ENABLED", False)
    init_db(db_file)
    with get_connection() as conn:
        conn.execute("INSERT INTO customers (id, name, slug, is_active, created_at, updated_at) "
                     "VALUES (?, 'T Org', 't', 1, ?, ?)", (CUST_ID, _NOW, _NOW))
        for uid, email in ((USER_ID, OWNER_A), (OTHER_USER, "o@t.com")):
            conn.execute("INSERT INTO users (id, customer_id, email, name, role, is_active, created_at, updated_at) "
                         "VALUES (?, ?, ?, 'U', 'admin', 1, ?, ?)", (uid, CUST_ID, email, _NOW, _NOW))
        for acct, email in ((ACCT_A, OWNER_A), (ACCT_B, OWNER_B)):
            conn.execute("INSERT INTO provider_accounts (id, customer_id, provider, email_address, auth_token_path, "
                         "sync_cursor, initial_sync_done, is_active, created_at, updated_at) "
                         "VALUES (?, ?, 'gmail', ?, '/tmp/t.json', 'c', 1, 1, ?, ?)", (acct, CUST_ID, email, _NOW, _NOW))
            conn.execute("INSERT INTO user_provider_accounts (id, user_id, account_id, role, created_at) "
                         "VALUES (?, ?, ?, 'owner', ?)", (str(uuid.uuid4()), USER_ID, acct, _NOW))
        # a known contact for the sender
        conn.execute("INSERT INTO contacts (id, customer_id, name, status, created_at, updated_at) "
                     "VALUES ('ct-ada', ?, 'Ada Lovelace', 'active', ?, ?)", (CUST_ID, _NOW, _NOW))
        conn.execute("INSERT INTO contact_identifiers (id, contact_id, type, value, is_primary, is_current, created_at, updated_at) "
                     "VALUES ('ci-ada', 'ct-ada', 'email', 'ada@example.com', 1, 1, ?, ?)", (_NOW, _NOW))
    return db_file


def _msg(thread, when, *, subject="S", body="b", sender="ada@example.com", sender_name="Ada Lovelace",
         labels=("INBOX", "UNREAD"), is_read=False, is_starred=False, to=None, owner=OWNER_A):
    return ParsedEmail(
        message_id=f"pm-{uuid.uuid4().hex[:8]}", thread_id=thread, subject=subject,
        sender=f"{sender_name} <{sender}>", sender_email=sender, recipients=list(to or [owner]),
        date=when, body_plain=body, body_html=f"<p>{body}</p>", snippet=body[:40],
        label_ids=list(labels), is_read=is_read, is_starred=is_starred,
        header_message_id=f"<{uuid.uuid4().hex[:6]}@x>",
    )


def _store(account, owner, emails):
    with get_connection() as conn:
        _store_thread(conn, account, owner, list(emails), load_contact_index(),
                      customer_id=CUST_ID, created_by=USER_ID)


def _d(day, hour=12):
    return datetime(2026, 5, day, hour, tzinfo=timezone.utc)


@pytest.fixture()
def mailbox(tmp_db):
    """Two accounts: A has an inbox thread of 3 (2 unread, one reply by me),
    an archived starred thread, a sent thread, a trashed thread; B has one inbox thread."""
    _store(ACCT_A, OWNER_A, [
        _msg("t1", _d(1), subject="Lunch?", body="bistro?"),
        _msg("t1", _d(2), subject="Re: Lunch?", body="sure", sender=OWNER_A, sender_name="Me",
             labels=("SENT",), is_read=True, to=["ada@example.com"]),
        _msg("t1", _d(3), subject="Re: Lunch?", body="thursday then", labels=("INBOX", "UNREAD")),
    ])
    _store(ACCT_A, OWNER_A, [_msg("t2", _d(4), subject="Archived note", labels=("Label_7",), is_read=True, is_starred=True)])
    _store(ACCT_A, OWNER_A, [_msg("t3", _d(5), subject="I wrote", sender=OWNER_A, sender_name="Me",
                                  labels=("SENT",), is_read=True, to=["bob@example.com"])])
    _store(ACCT_A, OWNER_A, [_msg("t4", _d(6), subject="Junk", labels=("TRASH",), is_read=True)])
    _store(ACCT_B, OWNER_B, [_msg("u1", _d(7), subject="Side account", owner=OWNER_B)])
    with get_connection() as conn:
        conn.execute("UPDATE mailbox_labels SET name = 'Clients/Acme' WHERE provider_label_id = 'Label_7'")
    return tmp_db


class TestFolders:
    def test_counts_per_account_and_unified(self, mailbox):
        with get_connection() as conn:
            out = folders(conn, account_ids=[ACCT_A, ACCT_B])
        a = next(x for x in out["accounts"] if x["id"] == ACCT_A)
        assert a["system"]["inbox"] == {"total": 2, "unread": 2}
        assert a["system"]["sent"] == {"total": 2, "unread": 0}
        assert a["system"]["starred"] == {"total": 1, "unread": 0}
        assert a["system"]["trash"] == {"total": 1, "unread": 0}
        assert a["system"]["archive"]["total"] == 3            # 2 sent + 1 labelled, none in inbox/trash
        acme = next(l for l in a["labels"] if l["name"] == "Clients/Acme")
        assert acme["kind"] == "user" and acme["total"] == 1
        assert out["unified"]["inbox"] == {"total": 3, "unread": 3}
        assert out["unified"]["sent"]["total"] == 2


class TestThreadList:
    def test_inbox_groups_by_thread_newest_first(self, mailbox):
        with get_connection() as conn:
            out = thread_list(conn, account_ids=[ACCT_A, ACCT_B], folder="inbox")
        assert out["total"] == 2
        assert [t["thread_id"] for t in out["items"]] == ["u1", "t1"]
        t1 = out["items"][1]
        assert t1["message_count"] == 3 and t1["unread_count"] == 2
        assert t1["subject"] == "Re: Lunch?" and t1["snippet"] == "thursday then"
        assert t1["account_email"] == OWNER_A and t1["labels"] == ["INBOX", "SENT"]
        assert [p["is_me"] for p in t1["participants"]] == [False, True]

    def test_folders_and_labels_and_scope(self, mailbox):
        with get_connection() as conn:
            assert [t["thread_id"] for t in thread_list(conn, account_ids=[ACCT_A], folder="sent")["items"]] == ["t3", "t1"]
            assert [t["thread_id"] for t in thread_list(conn, account_ids=[ACCT_A], folder="starred")["items"]] == ["t2"]
            assert [t["thread_id"] for t in thread_list(conn, account_ids=[ACCT_A], folder="trash")["items"]] == ["t4"]
            assert {t["thread_id"] for t in thread_list(conn, account_ids=[ACCT_A], folder="all")["items"]} == {"t1", "t2", "t3", "t4"}
            acme = conn.execute("SELECT id FROM mailbox_labels WHERE name = 'Clients/Acme'").fetchone()[0]
            assert [t["thread_id"] for t in thread_list(conn, account_ids=[ACCT_A], folder=None, label_row_id=acme)["items"]] == ["t2"]
            assert thread_list(conn, account_ids=[ACCT_B], folder="inbox")["items"][0]["thread_id"] == "u1"
            assert thread_list(conn, account_ids=[], folder="inbox")["total"] == 0
            with pytest.raises(ValueError):
                thread_list(conn, account_ids=[ACCT_A], folder="attic")

    def test_search_within_folder_and_pagination(self, mailbox):
        with get_connection() as conn:
            assert [t["thread_id"] for t in thread_list(conn, account_ids=[ACCT_A, ACCT_B], folder="inbox", q="bistro")["items"]] == ["t1"]
            page = thread_list(conn, account_ids=[ACCT_A, ACCT_B], folder="all", limit=2, offset=2)
        assert page["total"] == 5 and len(page["items"]) == 2


class TestThreadDetail:
    def test_messages_oldest_first_with_context(self, mailbox):
        with get_connection() as conn:
            d = thread_detail(conn, account_id=ACCT_A, thread_id="t1")
        assert d["subject"] == "Lunch?" and d["message_count"] == 3 and d["unread_count"] == 2
        assert [m["timestamp"][:10] for m in d["messages"]] == ["2026-05-01", "2026-05-02", "2026-05-03"]
        first = d["messages"][0]
        assert first["sender"]["contact_id"] == "ct-ada" and first["sender"]["contact_name"] == "Ada Lovelace"
        assert first["sender"]["is_me"] is False and d["messages"][1]["sender"]["is_me"] is True
        assert first["body_html"] == "<p>bistro?</p>" and first["body_text"] == "bistro?"
        assert [l["name"] for l in first["labels"]] == ["INBOX"]
        assert first["participants"][0]["address"] == OWNER_A and first["header_message_id"]
        assert d["conversation"] is not None and d["conversation"]["id"]

    def test_missing_thread(self, mailbox):
        with get_connection() as conn:
            assert thread_detail(conn, account_id=ACCT_A, thread_id="nope") is None


class TestApi:
    def _client(self, monkeypatch, user_id):
        monkeypatch.setattr("poc.hierarchy.get_current_user",
                            lambda: {"id": user_id, "email": "x", "name": "U", "role": "admin", "customer_id": CUST_ID})
        from poc.web.app import create_app
        return TestClient(create_app(), raise_server_exceptions=False)

    def test_routes(self, mailbox, monkeypatch):
        client = self._client(monkeypatch, USER_ID)
        f = client.get("/api/v1/mail/folders").json()
        assert {a["id"] for a in f["accounts"]} == {ACCT_A, ACCT_B} and f["unified"]["inbox"]["unread"] == 3
        assert f["accounts"][0]["sync"] is None or "running" in f["accounts"][0]["sync"]
        t = client.get("/api/v1/mail/threads", params={"folder": "inbox"}).json()
        assert t["total"] == 2
        t = client.get("/api/v1/mail/threads", params={"folder": "inbox", "account_id": ACCT_B}).json()
        assert [x["thread_id"] for x in t["items"]] == ["u1"]
        assert client.get("/api/v1/mail/threads", params={"folder": "attic"}).status_code == 400
        d = client.get(f"/api/v1/mail/threads/{ACCT_A}/t1").json()
        assert d["message_count"] == 3
        assert client.get(f"/api/v1/mail/threads/{ACCT_A}/none").status_code == 404

    def test_other_user_sees_nothing(self, mailbox, monkeypatch):
        client = self._client(monkeypatch, OTHER_USER)
        assert client.get("/api/v1/mail/folders").json()["accounts"] == []
        assert client.get("/api/v1/mail/threads").json()["total"] == 0
        assert client.get(f"/api/v1/mail/threads/{ACCT_A}/t1").status_code == 404
