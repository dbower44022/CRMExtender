"""Attachment metadata, cache, and routes (MAIL-15; MAIL-T09)."""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from poc.database import get_connection, init_db
from poc.mail_attachments import cached_path, prune_cache, store_attachment_rows
from poc.migrate_to_v26 import migrate
from poc.models import ParsedEmail
from poc.sync import _store_thread, load_contact_index

_NOW = datetime.now(timezone.utc).isoformat()
CUST_ID = "cust-att"
USER_ID = "user-att"
OTHER_USER = "user-att-other"
ACCOUNT_ID = "acct-att"
OWNER = "owner@att.com"


@pytest.fixture()
def tmp_db(tmp_path, monkeypatch):
    db_file = tmp_path / "test.db"
    monkeypatch.setattr("poc.config.DB_PATH", db_file)
    monkeypatch.setattr("poc.config.CRM_AUTH_ENABLED", False)
    monkeypatch.setattr("poc.config.ATTACHMENT_CACHE_DIR", tmp_path / "cache")
    init_db(db_file)
    with get_connection() as conn:
        conn.execute("INSERT INTO customers (id, name, slug, is_active, created_at, updated_at) "
                     "VALUES (?, 'A Org', 'a', 1, ?, ?)", (CUST_ID, _NOW, _NOW))
        for uid, email in ((USER_ID, OWNER), ("user-att-other", "o@att.com")):
            conn.execute("INSERT INTO users (id, customer_id, email, name, role, is_active, created_at, updated_at) "
                         "VALUES (?, ?, ?, 'U', 'admin', 1, ?, ?)", (uid, CUST_ID, email, _NOW, _NOW))
        conn.execute("INSERT INTO provider_accounts (id, customer_id, provider, email_address, auth_token_path, "
                     "sync_cursor, initial_sync_done, is_active, created_at, updated_at) "
                     "VALUES (?, ?, 'gmail', ?, '/tmp/t.json', 'c', 1, 1, ?, ?)", (ACCOUNT_ID, CUST_ID, OWNER, _NOW, _NOW))
        conn.execute("INSERT INTO user_provider_accounts (id, user_id, account_id, role, created_at) "
                     "VALUES (?, ?, ?, 'owner', ?)", (str(uuid.uuid4()), USER_ID, ACCOUNT_ID, _NOW))
    return db_file


def _email(attachments) -> ParsedEmail:
    return ParsedEmail(
        message_id=f"pm-{uuid.uuid4().hex[:8]}", thread_id="t1", subject="With files",
        sender="A <a@x.com>", sender_email="a@x.com", recipients=[OWNER],
        date=datetime(2026, 5, 1, tzinfo=timezone.utc), body_plain="see attached", snippet="see",
        label_ids=["INBOX"], is_read=True, attachments=attachments,
    )


def _store(em: ParsedEmail) -> str:
    with get_connection() as conn:
        _store_thread(conn, ACCOUNT_ID, OWNER, [em], load_contact_index(), customer_id=CUST_ID, created_by=USER_ID)
        return conn.execute("SELECT id FROM communications WHERE provider_message_id = ?", (em.message_id,)).fetchone()[0]


PARTS = [
    {"attachment_id": "att-1", "filename": "deck.pdf", "mime_type": "application/pdf", "size": 1234, "content_id": None, "is_inline": False},
    {"attachment_id": "att-2", "filename": "logo.png", "mime_type": "image/png", "size": 99, "content_id": "logo123", "is_inline": True},
]


class TestStore:
    def test_sync_writes_rows_and_upserts(self, tmp_db):
        em = _email(PARTS)
        cid = _store(em)
        with get_connection() as conn:
            rows = [dict(r) for r in conn.execute("SELECT * FROM attachments WHERE communication_id = ? ORDER BY filename", (cid,))]
        assert [r["filename"] for r in rows] == ["deck.pdf", "logo.png"]
        assert rows[1]["content_id"] == "logo123" and rows[1]["is_inline"] == 1
        assert rows[0]["provider_attachment_id"] == "att-1"
        # re-seen message: same parts, no duplicates, renamed file updates
        again = _email([dict(PARTS[0], filename="deck-v2.pdf"), PARTS[1]])
        again.message_id = em.message_id
        with get_connection() as conn:
            _store_thread(conn, ACCOUNT_ID, OWNER, [again], load_contact_index(), customer_id=CUST_ID, created_by=USER_ID)
        with get_connection() as conn:
            names = [r[0] for r in conn.execute("SELECT filename FROM attachments WHERE communication_id = ? ORDER BY filename", (cid,))]
        assert names == ["deck-v2.pdf", "logo.png"]
        with get_connection() as conn:
            assert store_attachment_rows(conn, cid, _email([{"attachment_id": None, "filename": "x"}])) == 0


class TestCache:
    def test_fetches_once_then_serves_from_disk_and_prunes(self, tmp_db, tmp_path):
        cid = _store(_email(PARTS))
        with get_connection() as conn:
            row = dict(conn.execute(
                "SELECT a.*, c.provider_message_id FROM attachments a JOIN communications c ON c.id = a.communication_id "
                "WHERE a.provider_attachment_id = 'att-1'").fetchone())
        provider = MagicMock()
        provider.fetch_attachment.return_value = b"%PDF-1.4 hello"
        account = {"id": ACCOUNT_ID}
        with get_connection() as conn:
            p1 = cached_path(conn, row, account=account, session=object(), provider=provider)
            p2 = cached_path(conn, row, account=account, session=object(), provider=provider)
        assert p1 == p2 and p1.read_bytes() == b"%PDF-1.4 hello"
        assert provider.fetch_attachment.call_count == 1
        args = provider.fetch_attachment.call_args
        assert args.args[1:] == (row["provider_message_id"], "att-1") and args.kwargs == {"rate_limiter": None}
        with get_connection() as conn:
            assert conn.execute("SELECT size_bytes FROM attachments WHERE id = ?", (row["id"],)).fetchone()[0] == len(b"%PDF-1.4 hello")
        # budget of 0 MB (floored to 1 MB) keeps this tiny file; a synthetic big file is pruned first
        big = tmp_path / "cache" / ACCOUNT_ID / "big.bin"
        big.write_bytes(b"x" * (2 * 1024 * 1024))
        import os, time
        os.utime(big, (time.time() - 3600, time.time() - 3600))   # least recently used
        freed = prune_cache(1)
        assert freed >= 2 * 1024 * 1024 and not big.exists() and p1.exists()


class TestRoutes:
    def _client(self, monkeypatch, user_id):
        monkeypatch.setattr("poc.hierarchy.get_current_user",
                            lambda: {"id": user_id, "email": "x", "name": "U", "role": "admin", "customer_id": CUST_ID})
        from poc.web.app import create_app
        return TestClient(create_app(), raise_server_exceptions=False)

    def test_stream_inline_download_and_cid(self, tmp_db, monkeypatch):
        cid = _store(_email(PARTS))
        provider = MagicMock()
        provider.fetch_attachment.side_effect = lambda s, mid, aid, rate_limiter=None: b"PNGDATA" if aid == "att-2" else b"%PDF"
        monkeypatch.setattr("poc.auth.get_credentials_for_account", lambda p: object())
        monkeypatch.setattr("poc.providers.get_provider", lambda name: provider)
        client = self._client(monkeypatch, USER_ID)
        with get_connection() as conn:
            pdf_id = conn.execute("SELECT id FROM attachments WHERE provider_attachment_id = 'att-1'").fetchone()[0]

        r = client.get(f"/api/v1/mail/attachments/{pdf_id}")
        assert r.status_code == 200 and r.content == b"%PDF"
        assert r.headers["content-type"].startswith("application/pdf")
        assert r.headers["content-disposition"].startswith("inline")
        assert r.headers["x-content-type-options"] == "nosniff"

        r = client.get(f"/api/v1/mail/attachments/{pdf_id}", params={"download": 1})
        assert r.headers["content-disposition"].startswith("attachment") and "deck.pdf" in r.headers["content-disposition"]

        r = client.get(f"/api/v1/mail/attachments/cid/{cid}/logo123")
        assert r.status_code == 200 and r.content == b"PNGDATA" and r.headers["content-type"].startswith("image/png")
        assert client.get(f"/api/v1/mail/attachments/cid/{cid}/nope").status_code == 404
        assert client.get("/api/v1/mail/attachments/nope").status_code == 404
        assert provider.fetch_attachment.call_count == 2          # pdf once, png once

    def test_other_user_cannot_fetch(self, tmp_db, monkeypatch):
        _store(_email(PARTS))
        client = self._client(monkeypatch, OTHER_USER)
        with get_connection() as conn:
            pdf_id = conn.execute("SELECT id FROM attachments WHERE provider_attachment_id = 'att-1'").fetchone()[0]
        assert client.get(f"/api/v1/mail/attachments/{pdf_id}").status_code == 404

    def test_html_attachment_is_forced_to_download(self, tmp_db, monkeypatch):
        _store(_email([{"attachment_id": "att-h", "filename": "page.html", "mime_type": "text/html", "size": 5}]))
        provider = MagicMock(); provider.fetch_attachment.return_value = b"<html>"
        monkeypatch.setattr("poc.auth.get_credentials_for_account", lambda p: object())
        monkeypatch.setattr("poc.providers.get_provider", lambda name: provider)
        client = self._client(monkeypatch, USER_ID)
        with get_connection() as conn:
            aid = conn.execute("SELECT id FROM attachments WHERE provider_attachment_id = 'att-h'").fetchone()[0]
        r = client.get(f"/api/v1/mail/attachments/{aid}")
        assert r.headers["content-disposition"].startswith("attachment")


class TestMigrationV26:
    def test_adds_columns_and_index(self, tmp_path):
        db = tmp_path / "v25.db"
        init_db(db)
        conn = sqlite3.connect(db)
        conn.execute("DROP INDEX IF EXISTS idx_attachments_provider")
        for col in ("provider_attachment_id", "content_id", "is_inline"):
            conn.execute(f"ALTER TABLE attachments DROP COLUMN {col}")
        conn.execute("PRAGMA user_version = 25"); conn.commit(); conn.close()
        migrate(db); migrate(db)
        conn = sqlite3.connect(db)
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 26
        cols = {r[1] for r in conn.execute("PRAGMA table_info(attachments)")}
        assert {"provider_attachment_id", "content_id", "is_inline"} <= cols
        assert conn.execute("SELECT name FROM sqlite_master WHERE name = 'idx_attachments_provider'").fetchone()
        conn.close()
