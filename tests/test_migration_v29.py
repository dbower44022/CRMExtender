"""Tests for the v28 -> v29 migration (conversation customer_id repair + account column)."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from poc.database import init_db
from poc.migrate_to_v29 import migrate

_NOW = datetime.now(timezone.utc).isoformat()


def _v28_db(tmp_path):
    db = tmp_path / "v28.db"
    init_db(db)
    conn = sqlite3.connect(db)
    conn.execute(
        "INSERT INTO customers (id, name, slug, is_active, created_at, updated_at) "
        "VALUES ('c', 'C', 'c', 1, ?, ?)", (_NOW, _NOW))
    conn.execute(
        "INSERT INTO provider_accounts (id, customer_id, provider, email_address, "
        "auth_token_path, created_at, updated_at) VALUES ('acct', 'c', 'gmail', "
        "'me@x.com', '/tmp/t.json', ?, ?)", (_NOW, _NOW))
    conn.execute(
        "INSERT INTO communications (id, account_id, channel, timestamp, provider_message_id, "
        "created_at, updated_at) VALUES ('cm1', 'acct', 'email', ?, 'pm1', ?, ?)",
        (_NOW, _NOW, _NOW))
    # cv1: NULL customer, owning account set.  cv2: NULL customer, no account,
    # reachable only through its linked communication.  cv3: already filled.
    for cid, acct, cust in (("cv1", "acct", None), ("cv2", None, None), ("cv3", "acct", "c")):
        conn.execute(
            "INSERT INTO conversations (id, account_id, title, status, customer_id, created_at, updated_at) "
            "VALUES (?, ?, 'T', 'active', ?, ?, ?)", (cid, acct, cust, _NOW, _NOW))
    conn.execute(
        "INSERT INTO conversation_communications (conversation_id, communication_id, created_at) "
        "VALUES ('cv2', 'cm1', ?)", (_NOW,))
    conn.execute(
        "INSERT INTO data_sources (id, customer_id, entity_type, name, is_system, created_at, updated_at) "
        "VALUES ('ds', 'c', 'conversation', 'Conversations', 1, ?, ?)", (_NOW, _NOW))
    conn.execute(
        "INSERT INTO views (id, customer_id, data_source_id, name, view_type, owner_id, visibility, "
        "is_default, sort_field, sort_direction, per_page, created_at, updated_at) "
        "VALUES ('v1', 'c', 'ds', 'All', 'list', 'u', 'personal', 1, 'last_activity_at', 'desc', 50, ?, ?)",
        (_NOW, _NOW))
    for pos, fk in enumerate(["title", "status", "message_count", "last_activity_at"]):
        conn.execute(
            "INSERT INTO view_columns (id, view_id, field_key, position) VALUES (?, 'v1', ?, ?)",
            (f"vc{pos}", fk, pos))
    conn.execute("PRAGMA user_version = 28")
    conn.commit()
    conn.close()
    return db


def _columns(conn, view_id):
    return [r[0] for r in conn.execute(
        "SELECT field_key FROM view_columns WHERE view_id = ? ORDER BY position", (view_id,))]


def test_repairs_customer_ids_and_adds_account_column(tmp_path):
    db = _v28_db(tmp_path)
    migrate(db)
    conn = sqlite3.connect(db)
    assert conn.execute("PRAGMA user_version").fetchone()[0] == 29
    rows = dict(conn.execute("SELECT id, customer_id FROM conversations").fetchall())
    assert rows == {"cv1": "c", "cv2": "c", "cv3": "c"}
    assert _columns(conn, "v1") == ["title", "status", "account_name", "message_count", "last_activity_at"]
    conn.close()


def test_idempotent(tmp_path):
    db = _v28_db(tmp_path)
    migrate(db)
    migrate(db)
    conn = sqlite3.connect(db)
    assert _columns(conn, "v1").count("account_name") == 1
    conn.close()


def test_view_without_status_column_appends(tmp_path):
    db = _v28_db(tmp_path)
    conn = sqlite3.connect(db)
    conn.execute("DELETE FROM view_columns WHERE field_key = 'status'")
    conn.commit()
    conn.close()
    migrate(db)
    conn = sqlite3.connect(db)
    assert _columns(conn, "v1")[-1] == "account_name"
    conn.close()
