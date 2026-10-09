"""Tests for the v22 -> v23 migration (MAIL-07/08: mailbox state + labels)."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from poc.database import init_db
from poc.migrate_to_v23 import migrate

_NOW = datetime.now(timezone.utc).isoformat()


def _v22_db(tmp_path):
    """Build a latest-schema DB, then strip the v23 additions."""
    db = tmp_path / "v22.db"
    init_db(db)
    conn = sqlite3.connect(db)
    conn.execute("DROP TABLE communication_labels")
    conn.execute("DROP TABLE mailbox_labels")
    conn.execute("DROP INDEX IF EXISTS idx_comm_mail_state")
    for col in ("header_reply_to", "is_starred", "mail_state_synced_at"):
        conn.execute(f"ALTER TABLE communications DROP COLUMN {col}")
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
    conn.execute("PRAGMA user_version = 22")
    conn.commit()
    conn.close()
    return db


def test_migrates_columns_tables_and_version(tmp_path):
    db = _v22_db(tmp_path)
    migrate(db)
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    assert conn.execute("PRAGMA user_version").fetchone()[0] == 23
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(communications)")}
    assert {"header_reply_to", "is_starred", "mail_state_synced_at"} <= cols
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"mailbox_labels", "communication_labels"} <= tables
    row = conn.execute("SELECT is_starred, mail_state_synced_at FROM communications WHERE id='cm1'").fetchone()
    # Existing rows: not starred, and flagged as awaiting the provider backfill.
    assert row["is_starred"] == 0 and row["mail_state_synced_at"] is None
    conn.close()


def test_idempotent(tmp_path):
    db = _v22_db(tmp_path)
    migrate(db)
    migrate(db)
    conn = sqlite3.connect(db)
    assert conn.execute("PRAGMA user_version").fetchone()[0] == 23
    conn.close()


def test_fresh_schema_matches_migrated_schema(tmp_path):
    """init_db and the migration must agree on the v23 shape."""
    fresh = tmp_path / "fresh.db"
    init_db(fresh)
    migrated = _v22_db(tmp_path)
    migrate(migrated)

    def shape(path):
        conn = sqlite3.connect(path)
        comm = [(r[1], r[2].upper()) for r in conn.execute("PRAGMA table_info(communications)")]
        labels = [(r[1], r[2].upper()) for r in conn.execute("PRAGMA table_info(mailbox_labels)")]
        cl = [(r[1], r[2].upper()) for r in conn.execute("PRAGMA table_info(communication_labels)")]
        conn.close()
        return sorted(comm), sorted(labels), sorted(cl)

    assert shape(fresh) == shape(migrated)
