"""Cross-account duplicate detection (MAIL-44; MAIL-T21): the same Message-ID in
two accounts is one thread in the unified views, with both account chips,
merged detail, deduplicated unified counts, and per-account views unchanged."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from poc.database import get_connection, init_db
from poc.mail_links import group_members, link_thread, rebuild_links
from poc.mail_threads import folders, thread_detail, thread_list
from poc.models import ParsedEmail
from poc.sync import _store_thread, load_contact_index

_NOW = datetime.now(timezone.utc).isoformat()
CUST_ID = "cust-lnk"
USER_ID = "user-lnk"
ACCT_A, ACCT_B = "acct-lnk-a", "acct-lnk-b"
OWNER_A, OWNER_B = "doug@a.com", "doug@b.org"


@pytest.fixture()
def tmp_db(tmp_path, monkeypatch):
    db_file = tmp_path / "test.db"
    monkeypatch.setattr("poc.config.DB_PATH", db_file)
    monkeypatch.setattr("poc.config.CRM_AUTH_ENABLED", False)
    init_db(db_file)
    with get_connection() as conn:
        conn.execute("INSERT INTO customers (id, name, slug, is_active, created_at, updated_at) VALUES (?, 'L', 'l', 1, ?, ?)", (CUST_ID, _NOW, _NOW))
        conn.execute("INSERT INTO users (id, customer_id, email, name, role, is_active, created_at, updated_at) VALUES (?, ?, ?, 'U', 'admin', 1, ?, ?)", (USER_ID, CUST_ID, OWNER_A, _NOW, _NOW))
        for acct, email, color in ((ACCT_A, OWNER_A, "#112233"), (ACCT_B, OWNER_B, "#445566")):
            conn.execute("INSERT INTO provider_accounts (id, customer_id, provider, email_address, auth_token_path, sync_cursor, "
                         "initial_sync_done, is_active, color, created_at, updated_at) VALUES (?, ?, 'gmail', ?, '/tmp/t.json', 'c', 1, 1, ?, ?, ?)",
                         (acct, CUST_ID, email, color, _NOW, _NOW))
            conn.execute("INSERT INTO user_provider_accounts (id, user_id, account_id, role, created_at) VALUES (?, ?, ?, 'owner', ?)",
                         (str(uuid.uuid4()), USER_ID, acct, _NOW))
    return db_file


def _d(day, hour=12):
    return datetime(2026, 5, day, hour, tzinfo=timezone.utc)


def _msg(thread, when, mid, *, subject="Board agenda", sender="ada@example.com", to=(OWNER_A, OWNER_B), is_read=False):
    return ParsedEmail(
        message_id=f"pm-{uuid.uuid4().hex[:8]}", thread_id=thread, subject=subject,
        sender=f"Ada <{sender}>", sender_email=sender, recipients=list(to), date=when,
        body_plain="b", body_html="<p>b</p>", snippet="b", label_ids=["INBOX", "UNREAD"], is_read=is_read,
        header_message_id=mid,
    )


def _store(account, owner, emails):
    with get_connection() as conn:
        _store_thread(conn, account, owner, list(emails), load_contact_index(), customer_id=CUST_ID, created_by=USER_ID)


@pytest.fixture()
def mirrored(tmp_db):
    """Ada writes to both of Doug's addresses: thread ta in A and tb in B hold the
    same two messages; B also has a third message A never got. A has an
    unrelated thread tx."""
    _store(ACCT_A, OWNER_A, [_msg("ta", _d(1), "<m1@x>"), _msg("ta", _d(2), "<m2@x>")])
    _store(ACCT_B, OWNER_B, [_msg("tb", _d(1), "<m1@x>"), _msg("tb", _d(2), "<m2@x>"), _msg("tb", _d(3), "<m3@x>", subject="Re: Board agenda")])
    _store(ACCT_A, OWNER_A, [_msg("tx", _d(4), "<other@x>", subject="Lunch")])
    return tmp_db


def test_store_links_threads_across_accounts(mirrored):
    with get_connection() as conn:
        members = group_members(conn, ACCT_A, "ta")
        assert {(m["account_id"], m["thread_id"]) for m in members} == {(ACCT_A, "ta"), (ACCT_B, "tb")}
        assert group_members(conn, ACCT_A, "tx") == [{"account_id": ACCT_A, "thread_id": "tx"}]
        # linking is idempotent and survives a rebuild
        assert link_thread(conn, ACCT_A, "ta", ["<m1@x>"]) == link_thread(conn, ACCT_B, "tb", ["<m2@x>"])
        stats = rebuild_links(conn)
        assert stats == {"message_ids": 2, "groups": 1, "threads": 2}


def test_unified_list_shows_one_thread_with_both_chips(mirrored):
    with get_connection() as conn:
        page = thread_list(conn, account_ids=[ACCT_A, ACCT_B], folder="inbox")
    assert page["total"] == 2
    merged = next(t for t in page["items"] if t["subject"].endswith("Board agenda"))
    assert merged["message_count"] == 3                       # m1, m2 once each, plus B's m3
    assert {a["id"] for a in merged["accounts"]} == {ACCT_A, ACCT_B}
    assert {(m["account_id"], m["thread_id"]) for m in merged["members"]} == {(ACCT_A, "ta"), (ACCT_B, "tb")}
    assert merged["account_id"] == ACCT_B and merged["thread_id"] == "tb"   # newest message lives in B
    lunch = next(t for t in page["items"] if t["subject"] == "Lunch")
    assert lunch["accounts"] == [{"id": ACCT_A, "email": OWNER_A, "color": "#112233"}]


def test_per_account_lists_and_counts_are_unchanged(mirrored):
    with get_connection() as conn:
        a = thread_list(conn, account_ids=[ACCT_A], folder="inbox")
        b = thread_list(conn, account_ids=[ACCT_B], folder="inbox")
        f = folders(conn, account_ids=[ACCT_A, ACCT_B])
    assert [t["thread_id"] for t in a["items"]] == ["tx", "ta"] and [t["message_count"] for t in a["items"]] == [1, 2]
    assert [t["thread_id"] for t in b["items"]] == ["tb"] and b["items"][0]["message_count"] == 3
    by_id = {acc["id"]: acc for acc in f["accounts"]}
    assert by_id[ACCT_A]["system"]["inbox"] == {"total": 3, "unread": 3}
    assert by_id[ACCT_B]["system"]["inbox"] == {"total": 3, "unread": 3}
    # unified: 6 rows, but m1 and m2 are each held twice -> 4 distinct messages
    assert f["unified"]["inbox"] == {"total": 4, "unread": 4}


def test_detail_merges_the_group_and_tags_each_message(mirrored):
    with get_connection() as conn:
        d = thread_detail(conn, account_id=ACCT_A, thread_id="ta", account_ids=[ACCT_A, ACCT_B])
        only_a = thread_detail(conn, account_id=ACCT_A, thread_id="ta", account_ids=[ACCT_A])
    assert [m["header_message_id"] for m in d["messages"]] == ["<m1@x>", "<m2@x>", "<m3@x>"]
    assert [m["account_id"] for m in d["messages"]] == [ACCT_A, ACCT_A, ACCT_B]   # A's copies win where both exist
    assert d["account_id"] == ACCT_A and {a["id"] for a in d["accounts"]} == {ACCT_A, ACCT_B}
    assert [m["header_message_id"] for m in only_a["messages"]] == ["<m1@x>", "<m2@x>"]


def test_actions_over_members_reach_both_accounts(mirrored, monkeypatch):
    monkeypatch.setattr("poc.hierarchy.get_current_user",
                        lambda: {"id": USER_ID, "email": "x", "name": "U", "role": "admin", "customer_id": CUST_ID})
    from poc.web.app import create_app
    client = TestClient(create_app(), raise_server_exceptions=False)
    r = client.post("/api/v1/mail/actions", json={"action": "archive", "threads": [
        {"account_id": ACCT_A, "thread_id": "ta"}, {"account_id": ACCT_B, "thread_id": "tb"}]})
    assert r.status_code == 201 and len(r.json()["items"]) == 2
    with get_connection() as conn:
        assert thread_list(conn, account_ids=[ACCT_A, ACCT_B], folder="inbox")["total"] == 1
    d = client.get(f"/api/v1/mail/threads/{ACCT_A}/ta").json()
    assert d["message_count"] == 3 and len(d["accounts"]) == 2
