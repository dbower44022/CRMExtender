"""Tests for the v32 -> v33 migration (mail_thread_links created and filled)."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from poc.database import init_db
from poc.migrate_to_v33 import migrate

_NOW = datetime.now(timezone.utc).isoformat()


def _v32_db(tmp_path):
    db = tmp_path / "v32.db"
    init_db(db)
    conn = sqlite3.connect(db)
    conn.execute("DROP TABLE mail_thread_links")
    conn.execute("INSERT INTO customers (id, name, slug, is_active, created_at, updated_at) VALUES ('c', 'C', 'c', 1, ?, ?)", (_NOW, _NOW))
    for acct in ("a", "b"):
        conn.execute("INSERT INTO provider_accounts (id, customer_id, provider, email_address, auth_token_path, created_at, updated_at) "
                     "VALUES (?, 'c', 'gmail', ?, '/tmp/t.json', ?, ?)", (acct, f"me@{acct}.com", _NOW, _NOW))
    for cid, acct, tid, mid in (("c1", "a", "ta", "<m1@x>"), ("c2", "b", "tb", "<m1@x>"), ("c3", "a", "tz", "<z@x>")):
        conn.execute("INSERT INTO communications (id, account_id, channel, timestamp, provider_message_id, provider_thread_id, "
                     "header_message_id, is_current, created_at, updated_at) VALUES (?, ?, 'email', ?, ?, ?, ?, 1, ?, ?)",
                     (cid, acct, _NOW, "pm-" + cid, tid, mid, _NOW, _NOW))
    conn.execute("PRAGMA user_version = 32")
    conn.commit(); conn.close()
    return db


def test_creates_and_fills_links(tmp_path):
    db = _v32_db(tmp_path)
    migrate(db); migrate(db)
    conn = sqlite3.connect(db)
    assert conn.execute("PRAGMA user_version").fetchone()[0] == 33
    rows = conn.execute("SELECT account_id, thread_id, group_id FROM mail_thread_links ORDER BY account_id").fetchall()
    assert [(r[0], r[1]) for r in rows] == [("a", "ta"), ("b", "tb")] and rows[0][2] == rows[1][2]
    conn.close()
