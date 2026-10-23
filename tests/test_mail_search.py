"""Full-text mail search (MAIL-12; MAIL-T06): parser, SQL, index triggers, API."""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from poc.database import get_connection, init_db
from poc.mail_search import build_sql, parse_query, search
from poc.migrate_to_v25 import migrate
from poc.models import ParsedEmail
from poc.sync import _store_thread, load_contact_index

_NOW = datetime.now(timezone.utc).isoformat()
CUST_ID = "cust-fts"
USER_ID = "user-fts"
OTHER_USER = "user-fts-other"
ACCT_A = "acct-fts-a"
ACCT_B = "acct-fts-b"
OWNER_A = "owner@a.com"
OWNER_B = "owner@b.com"


@pytest.fixture()
def tmp_db(tmp_path, monkeypatch):
    db_file = tmp_path / "test.db"
    monkeypatch.setattr("poc.config.DB_PATH", db_file)
    monkeypatch.setattr("poc.config.CRM_AUTH_ENABLED", False)
    init_db(db_file)
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO customers (id, name, slug, is_active, created_at, updated_at) "
            "VALUES (?, 'F Org', 'f', 1, ?, ?)", (CUST_ID, _NOW, _NOW))
        for uid, email in ((USER_ID, OWNER_A), (OTHER_USER, "other@f.com")):
            conn.execute(
                "INSERT INTO users (id, customer_id, email, name, role, is_active, created_at, updated_at) "
                "VALUES (?, ?, ?, 'U', 'admin', 1, ?, ?)", (uid, CUST_ID, email, _NOW, _NOW))
        for acct, email, name in ((ACCT_A, OWNER_A, "Main"), (ACCT_B, OWNER_B, "Side")):
            conn.execute(
                "INSERT INTO provider_accounts (id, customer_id, provider, email_address, display_name, "
                "auth_token_path, sync_cursor, initial_sync_done, is_active, created_at, updated_at) "
                "VALUES (?, ?, 'gmail', ?, ?, '/tmp/t.json', 'c', 1, 1, ?, ?)",
                (acct, CUST_ID, email, name, _NOW, _NOW))
        conn.execute(
            "INSERT INTO user_provider_accounts (id, user_id, account_id, role, created_at) "
            "VALUES (?, ?, ?, 'owner', ?)", (str(uuid.uuid4()), USER_ID, ACCT_A, _NOW))
        conn.execute(
            "INSERT INTO user_provider_accounts (id, user_id, account_id, role, created_at) "
            "VALUES (?, ?, ?, 'shared', ?)", (str(uuid.uuid4()), USER_ID, ACCT_B, _NOW))
    return db_file


def _store(account, owner, *, subject, body, sender="ada@example.com", sender_name="Ada Lovelace",
           to=None, cc=(), names=None, labels=("INBOX",), is_read=True, is_starred=False, when=None) -> str:
    em = ParsedEmail(
        message_id=f"pm-{uuid.uuid4().hex[:8]}", thread_id=f"t-{uuid.uuid4().hex[:6]}",
        subject=subject, sender=f"{sender_name} <{sender}>", sender_email=sender,
        recipients=list(to or [owner]), cc=list(cc), participant_names=dict(names or {}),
        date=when or datetime(2026, 6, 1, tzinfo=timezone.utc), body_plain=body, snippet=body[:40],
        label_ids=list(labels), is_read=is_read, is_starred=is_starred,
    )
    with get_connection() as conn:
        _store_thread(conn, account, owner, [em], load_contact_index(), customer_id=CUST_ID, created_by=USER_ID)
        return conn.execute("SELECT id FROM communications WHERE provider_message_id = ?",
                            (em.message_id,)).fetchone()[0]


def _ids(q, accounts=(ACCT_A, ACCT_B), **kw):
    with get_connection() as conn:
        return [it["id"] for it in search(conn, q, account_ids=list(accounts), **kw)["items"]]


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

class TestParser:
    def test_every_operator(self):
        now = datetime(2026, 10, 9, tzinfo=timezone.utc)
        sq = parse_query(
            'budget "quarterly review" from:ada to:bob cc:dan subject:invoice has:attachment '
            'in:inbox label:Clients/Acme account:main is:unread is:starred '
            'before:2026-07-01 after:2026/01/15 newer_than:7d', now=now)
        assert sq.terms == ["budget", "quarterly review"]
        assert sq.from_ == ["ada"] and sq.to == ["bob"] and sq.cc == ["dan"]
        assert sq.subject == ["invoice"] and sq.has_attachment is True
        assert sq.in_ == "inbox" and sq.labels == ["Clients/Acme"] and sq.account == "main"
        assert sq.is_unread is True and sq.is_starred is True
        assert sq.before == datetime(2026, 7, 1, tzinfo=timezone.utc)
        # newer_than overrides the earlier after: (last one wins)
        assert sq.after == datetime(2026, 10, 2, tzinfo=timezone.utc)

    def test_quoted_operator_value_and_spaced_operator(self):
        sq = parse_query('from:"Ada Lovelace" to: bob is:read')
        assert sq.from_ == ["Ada Lovelace"] and sq.to == ["bob"] and sq.is_unread is False

    def test_unknown_operator_is_free_text(self):
        sq = parse_query("http://x.test/path is:bogus has:wings")
        assert sq.terms == ["http://x.test/path"]
        assert sq.unknown == ["is:bogus", "has:wings"]

    def test_empty(self):
        assert parse_query("").is_empty()


# ---------------------------------------------------------------------------
# Search end to end
# ---------------------------------------------------------------------------

class TestSearch:
    def test_free_text_matches_body_subject_and_names(self, tmp_db):
        a = _store(ACCT_A, OWNER_A, subject="Lunch", body="Shall we meet at the bistro on Thursday?")
        b = _store(ACCT_A, OWNER_A, subject="Bistro invoice", body="Attached.")
        c = _store(ACCT_A, OWNER_A, subject="Hello", body="nothing", sender="grace@hopper.test",
                   sender_name="Grace Hopper")
        assert set(_ids("bistro")) == {a, b}
        assert _ids("bistros") == [a, b] or set(_ids("bistros")) == {a, b}   # porter stem
        assert _ids('"meet at the bistro"') == [a]
        assert _ids("hopper") == [c]
        assert _ids("grace@hopper.test") == [c]

    def test_participant_operators(self, tmp_db):
        a = _store(ACCT_A, OWNER_A, subject="x", body="x", to=["bob@example.com"], cc=["dan@example.com"],
                   names={"bob@example.com": "Bob Builder"})
        _store(ACCT_A, OWNER_A, subject="y", body="y", to=[OWNER_A])
        assert _ids("to:bob") == [a]
        assert _ids("to:builder") == [a]
        assert _ids("cc:dan@example.com") == [a]
        assert _ids("from:lovelace") and len(_ids("from:lovelace")) == 2
        assert _ids("from:nobody") == []

    def test_flags_dates_account_subject(self, tmp_db):
        unread = _store(ACCT_A, OWNER_A, subject="Report Q2", body="r", is_read=False,
                        when=datetime(2026, 4, 1, tzinfo=timezone.utc))
        starred = _store(ACCT_B, OWNER_B, subject="Report Q3", body="r", is_starred=True,
                         when=datetime(2026, 8, 1, tzinfo=timezone.utc))
        assert _ids("is:unread") == [unread]
        assert _ids("is:starred") == [starred]
        assert _ids("after:2026-06-01") == [starred]
        assert _ids("before:2026-06-01") == [unread]
        assert _ids("account:side") == [starred]
        assert _ids("account:owner@a") == [unread]
        assert _ids("subject:report") == [starred, unread]          # newest first
        assert _ids("subject:q2") == [unread]

    def test_folders_labels_and_trash_exclusion(self, tmp_db):
        inbox = _store(ACCT_A, OWNER_A, subject="in", body="x", labels=("INBOX",))
        archived = _store(ACCT_A, OWNER_A, subject="arch", body="x", labels=("Label_7",))
        sent = _store(ACCT_A, OWNER_A, subject="sent", body="x", labels=("SENT",))
        trashed = _store(ACCT_A, OWNER_A, subject="gone", body="x", labels=("TRASH",))
        with get_connection() as conn:
            conn.execute("UPDATE mailbox_labels SET name = 'Clients/Acme' WHERE provider_label_id = 'Label_7'")
        assert set(_ids("")) == {inbox, archived, sent}             # trash hidden by default
        assert _ids("in:trash") == [trashed]
        assert set(_ids("in:anywhere")) == {inbox, archived, sent, trashed}
        assert _ids("in:inbox") == [inbox]
        assert _ids("in:sent") == [sent]
        # "archive" = mail that is in no inbox, trash, or spam folder (sent mail included, as at the provider)
        assert set(_ids("in:archive")) == {archived, sent}
        assert _ids("label:clients/acme") == [archived]
        assert _ids('in:"Clients/Acme"') == [archived]
        assert _ids("label:Label_7") == [archived]

    def test_has_attachment_and_pagination(self, tmp_db):
        ids = [_store(ACCT_A, OWNER_A, subject=f"m{i}", body="paginate me",
                      when=datetime(2026, 1, i + 1, tzinfo=timezone.utc)) for i in range(5)]
        with get_connection() as conn:
            conn.execute("INSERT INTO attachments (id, communication_id, filename, created_at) "
                         "VALUES ('att1', ?, 'f.pdf', ?)", (ids[2], _NOW))
        assert _ids("has:attachment") == [ids[2]]
        with get_connection() as conn:
            page = search(conn, "paginate", account_ids=[ACCT_A], limit=2, offset=2)
        assert page["total"] == 5 and [it["id"] for it in page["items"]] == [ids[2], ids[1]]
        assert page["items"][0]["account_email"] == OWNER_A and page["items"][0]["labels"] == ["INBOX"]

    def test_account_scope_is_enforced(self, tmp_db):
        a = _store(ACCT_A, OWNER_A, subject="secret", body="x")
        _store(ACCT_B, OWNER_B, subject="secret", body="x")
        assert _ids("secret", accounts=(ACCT_A,)) == [a]
        assert _ids("secret", accounts=()) == []

    def test_index_follows_updates_and_deletes(self, tmp_db):
        a = _store(ACCT_A, OWNER_A, subject="first", body="alpha")
        with get_connection() as conn:
            conn.execute("UPDATE communications SET search_text = 'omega' WHERE id = ?", (a,))
        assert _ids("omega") == [a] and _ids("alpha") == []
        with get_connection() as conn:
            conn.execute("INSERT INTO communication_participants (communication_id, address, name, role) "
                         "VALUES (?, 'zed@example.com', 'Zed Zeta', 'to')", (a,))
        assert _ids("zeta") == [a]
        with get_connection() as conn:
            conn.execute("DELETE FROM communications WHERE id = ?", (a,))
        assert _ids("omega") == []

    def test_special_characters_do_not_break_match(self, tmp_db):
        a = _store(ACCT_A, OWNER_A, subject="Re: [JIRA] (ACME-12) 50% off!", body="x")
        assert _ids("ACME-12") == [a]
        assert _ids('"50% off"') == [a]
        assert _ids("NOT AND OR") == []                               # keywords are literal


# ---------------------------------------------------------------------------
# Migration
# ---------------------------------------------------------------------------

class TestMigrationV25:
    def test_backfills_existing_rows_and_is_idempotent(self, tmp_path, tmp_db):
        a = _store(ACCT_A, OWNER_A, subject="legacy", body="needle in haystack")
        # Simulate a v24 database: drop the index and triggers
        conn = sqlite3.connect(tmp_db)
        for t in ("trg_comm_fts_insert", "trg_comm_fts_update", "trg_comm_fts_delete",
                  "trg_comm_fts_part_insert", "trg_comm_fts_part_update", "trg_comm_fts_part_delete"):
            conn.execute(f"DROP TRIGGER {t}")
        conn.execute("DROP TABLE communications_fts")
        conn.execute("PRAGMA user_version = 24")
        conn.commit(); conn.close()

        migrate(tmp_db); migrate(tmp_db)
        conn = sqlite3.connect(tmp_db)
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 25
        conn.close()
        assert _ids("haystack") == [a]


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------

class TestApi:
    def _client(self, monkeypatch, user_id):
        monkeypatch.setattr(
            "poc.hierarchy.get_current_user",
            lambda: {"id": user_id, "email": "x@f.com", "name": "U", "role": "admin", "customer_id": CUST_ID},
        )
        from poc.web.app import create_app
        return TestClient(create_app(), raise_server_exceptions=False)

    def test_search_route_scopes_to_visible_accounts(self, tmp_db, monkeypatch):
        a = _store(ACCT_A, OWNER_A, subject="shared word", body="x")
        b = _store(ACCT_B, OWNER_B, subject="shared word", body="x")
        client = self._client(monkeypatch, USER_ID)
        resp = client.get("/api/v1/mail/search", params={"q": "shared"})
        assert resp.status_code == 200
        assert {it["id"] for it in resp.json()["items"]} == {a, b}     # owner of A, shared on B
        other = self._client(monkeypatch, OTHER_USER)
        assert other.get("/api/v1/mail/search", params={"q": "shared"}).json()["items"] == []

    def test_global_search_reaches_bodies(self, tmp_db, monkeypatch):
        a = _store(ACCT_A, OWNER_A, subject="plain", body="the word xylophone appears only here")
        client = self._client(monkeypatch, USER_ID)
        resp = client.get("/api/v1/search", params={"q": "xylophone"})
        assert resp.status_code == 200, resp.text
        groups = {g["entity_type"]: g for g in resp.json()["groups"]}
        assert [r["id"] for r in groups["communication"]["results"]] == [a]
