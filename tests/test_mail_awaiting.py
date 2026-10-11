"""Awaiting-reply tracking (MAIL-47): the folder lists the owner's unanswered
sent threads after the threshold; a reply, a dismissal, a draft, or trash
removes them; the API dismiss/restore endpoints are owner-only."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from poc.database import get_connection, init_db
from poc.mail_awaiting import counts, dismiss, restore
from poc.mail_threads import folders, thread_list
from poc.models import ParsedEmail
from poc.settings import set_setting
from poc.sync import _store_thread, load_contact_index

_NOW = datetime.now(timezone.utc).isoformat()
CUST_ID = "cust-aw"
USER_ID = "user-aw"
OTHER_USER = "user-aw-other"
ACCOUNT_ID = "acct-aw"
OWNER = "owner@aw.com"
NOW = datetime.now(timezone.utc)


@pytest.fixture()
def tmp_db(tmp_path, monkeypatch):
    db_file = tmp_path / "test.db"
    monkeypatch.setattr("poc.config.DB_PATH", db_file)
    monkeypatch.setattr("poc.config.CRM_AUTH_ENABLED", False)
    init_db(db_file)
    with get_connection() as conn:
        conn.execute("INSERT INTO customers (id, name, slug, is_active, created_at, updated_at) "
                     "VALUES (?, 'AW', 'aw', 1, ?, ?)", (CUST_ID, _NOW, _NOW))
        for uid, email in ((USER_ID, OWNER), (OTHER_USER, "o@aw.com")):
            conn.execute("INSERT INTO users (id, customer_id, email, name, role, is_active, created_at, updated_at) "
                         "VALUES (?, ?, ?, 'U', 'admin', 1, ?, ?)", (uid, CUST_ID, email, _NOW, _NOW))
        conn.execute("INSERT INTO provider_accounts (id, customer_id, provider, email_address, auth_token_path, "
                     "sync_cursor, initial_sync_done, is_active, created_at, updated_at) "
                     "VALUES (?, ?, 'gmail', ?, '/tmp/t.json', 'c', 1, 1, ?, ?)", (ACCOUNT_ID, CUST_ID, OWNER, _NOW, _NOW))
        conn.execute("INSERT INTO user_provider_accounts (id, user_id, account_id, role, created_at) "
                     "VALUES (?, ?, ?, 'owner', ?)", (str(uuid.uuid4()), USER_ID, ACCOUNT_ID, _NOW))
        conn.execute("INSERT INTO user_provider_accounts (id, user_id, account_id, role, created_at) "
                     "VALUES (?, ?, ?, 'shared', ?)", (str(uuid.uuid4()), OTHER_USER, ACCOUNT_ID, _NOW))
    return db_file


def _msg(thread, when, *, mine=False, to=("ada@example.com",), labels=None, subject="S"):
    sender = OWNER if mine else "ada@example.com"
    return ParsedEmail(
        message_id=f"pm-{uuid.uuid4().hex[:8]}", thread_id=thread, subject=subject,
        sender=f"{'Me' if mine else 'Ada'} <{sender}>", sender_email=sender,
        recipients=list(to) if mine else [OWNER],
        date=when, body_plain="b", snippet="b",
        label_ids=list(labels if labels is not None else (["SENT"] if mine else ["INBOX"])), is_read=True,
    )


def _store(emails):
    with get_connection() as conn:
        _store_thread(conn, ACCOUNT_ID, OWNER, list(emails), load_contact_index(), customer_id=CUST_ID, created_by=USER_ID)


def _awaiting(days=3):
    with get_connection() as conn:
        return thread_list(conn, account_ids=[ACCOUNT_ID], folder="awaiting", awaiting_days=days)


def test_lists_unanswered_sent_threads_after_the_threshold(tmp_db):
    old = NOW - timedelta(days=5)
    _store([_msg("t-wait", old, mine=True)])                                   # unanswered, 5 days: listed
    _store([_msg("t-fresh", NOW - timedelta(hours=5), mine=True)])              # unanswered but recent: not yet
    _store([_msg("t-answered", old, mine=True), _msg("t-answered", NOW - timedelta(days=1))])  # replied: no
    _store([_msg("t-inbound", old)])                                             # their message, not mine: no
    _store([_msg("t-noto", old, mine=True, to=())])                              # sent to nobody: no
    _store([_msg("t-draft", old, mine=True, labels=["DRAFT"])])                  # a draft: no
    _store([_msg("t-trash", old, mine=True, labels=["SENT", "TRASH"])])         # trashed: no
    _store([_msg("t-ancient", NOW - timedelta(days=200), mine=True)])          # outside the window: no

    page = _awaiting()
    assert [t["thread_id"] for t in page["items"]] == ["t-wait"]
    it = page["items"][0]
    assert it["awaiting_days"] == 5 and it["awaiting_since"].startswith(old.isoformat()[:16])
    with get_connection() as conn:
        assert counts(conn, [ACCOUNT_ID], 3) == {ACCOUNT_ID: 1}
        f = folders(conn, account_ids=[ACCOUNT_ID], awaiting_days=3)
    assert f["unified"]["awaiting"]["total"] == 1 and f["accounts"][0]["system"]["awaiting"]["total"] == 1

    # A lower threshold brings the recent one in; a wider window the ancient one; a reply clears a thread.
    assert {t["thread_id"] for t in _awaiting(days=1)["items"]} == {"t-wait"}
    with get_connection() as conn:
        wide = thread_list(conn, account_ids=[ACCOUNT_ID], folder="awaiting", awaiting_days=3, awaiting_window=365)
    assert {t["thread_id"] for t in wide["items"]} == {"t-wait", "t-ancient"}
    _store([_msg("t-wait", NOW)])
    assert _awaiting()["items"] == []


def test_dismiss_and_restore(tmp_db):
    _store([_msg("t-wait", NOW - timedelta(days=4), mine=True)])
    with get_connection() as conn:
        dismiss(conn, ACCOUNT_ID, "t-wait", USER_ID)
    assert _awaiting()["items"] == []
    with get_connection() as conn:
        assert restore(conn, ACCOUNT_ID, "t-wait") == 1
    assert [t["thread_id"] for t in _awaiting()["items"]] == ["t-wait"]


def test_threshold_setting_and_api(tmp_db, monkeypatch):
    _store([_msg("t-wait", NOW - timedelta(days=2), mine=True)])
    monkeypatch.setattr("poc.hierarchy.get_current_user",
                        lambda: {"id": USER_ID, "email": "x", "name": "U", "role": "admin", "customer_id": CUST_ID})
    from poc.web.app import create_app
    client = TestClient(create_app(), raise_server_exceptions=False)
    assert client.get("/api/v1/mail/threads", params={"folder": "awaiting"}).json()["total"] == 0
    set_setting(CUST_ID, "mail_awaiting_reply_days", "1", scope="system")
    assert client.get("/api/v1/mail/threads", params={"folder": "awaiting"}).json()["total"] == 1
    assert client.get("/api/v1/mail/folders").json()["unified"]["awaiting"]["total"] == 1

    r = client.post(f"/api/v1/mail/awaiting/{ACCOUNT_ID}/t-wait/dismiss")
    assert r.status_code == 200 and r.json()["dismissed"] is True
    assert client.get("/api/v1/mail/threads", params={"folder": "awaiting"}).json()["total"] == 0
    r = client.post(f"/api/v1/mail/awaiting/{ACCOUNT_ID}/t-wait/restore")
    assert r.status_code == 200 and r.json()["restored"] == 1
    assert client.get("/api/v1/mail/threads", params={"folder": "awaiting"}).json()["total"] == 1

    monkeypatch.setattr("poc.hierarchy.get_current_user",
                        lambda: {"id": OTHER_USER, "email": "o", "name": "O", "role": "admin", "customer_id": CUST_ID})
    client = TestClient(create_app(), raise_server_exceptions=False)
    assert client.post(f"/api/v1/mail/awaiting/{ACCOUNT_ID}/t-wait/dismiss").status_code == 403
