"""Tests for the v30 -> v31 migration (backfill checkpoint, mail_snoozes, one HTML body)."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from poc.database import init_db
from poc.migrate_to_v31 import migrate

_NOW = datetime.now(timezone.utc).isoformat()


def _v30_db(tmp_path):
    db = tmp_path / "v30.db"
    init_db(db)
    conn = sqlite3.connect(db)
    conn.execute("DROP TABLE mail_snoozes")
    for col in ("backfill_cursor", "backfill_done", "backfill_messages", "backfill_updated_at"):
        conn.execute(f"ALTER TABLE provider_accounts DROP COLUMN {col}")
    conn.execute(
        "INSERT INTO customers (id, name, slug, is_active, created_at, updated_at) "
        "VALUES ('c', 'C', 'c', 1, ?, ?)", (_NOW, _NOW))
    conn.execute(
        "INSERT INTO provider_accounts (id, customer_id, provider, email_address, "
        "auth_token_path, created_at, updated_at) VALUES ('acct', 'c', 'gmail', "
        "'me@x.com', '/tmp/t.json', ?, ?)", (_NOW, _NOW))
    for cid, orig, cleaned in (("cm1", "<p>same</p>", "<p>same</p>"),
                               ("cm2", "<p>raw</p>", "<p>clean</p>"),
                               ("cm3", "<p>only</p>", None)):
        conn.execute(
            "INSERT INTO communications (id, account_id, channel, timestamp, provider_message_id, "
            "original_html, cleaned_html, created_at, updated_at) VALUES (?, 'acct', 'email', ?, ?, ?, ?, ?, ?)",
            (cid, _NOW, "pm-" + cid, orig, cleaned, _NOW, _NOW))
    conn.execute("PRAGMA user_version = 30")
    conn.commit()
    conn.close()
    return db


def test_adds_schema_and_drops_duplicate_html(tmp_path):
    db = _v30_db(tmp_path)
    migrate(db, do_vacuum=False)
    conn = sqlite3.connect(db)
    assert conn.execute("PRAGMA user_version").fetchone()[0] == 31
    cols = {r[1] for r in conn.execute("PRAGMA table_info(provider_accounts)")}
    assert {"backfill_cursor", "backfill_done", "backfill_messages", "backfill_updated_at"} <= cols
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "mail_snoozes" in tables
    rows = dict(conn.execute("SELECT id, cleaned_html FROM communications").fetchall())
    assert rows == {"cm1": None, "cm2": "<p>clean</p>", "cm3": None}
    assert conn.execute("SELECT original_html FROM communications WHERE id='cm1'").fetchone()[0] == "<p>same</p>"
    conn.close()


def test_idempotent_and_vacuum_runs(tmp_path):
    db = _v30_db(tmp_path)
    migrate(db, do_vacuum=False)
    migrate(db, do_vacuum=True)  # second run: columns exist, VACUUM on an idle file succeeds
    conn = sqlite3.connect(db)
    assert conn.execute("PRAGMA user_version").fetchone()[0] == 31
    conn.close()
