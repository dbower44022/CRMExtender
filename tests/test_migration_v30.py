"""Tests for the v29 -> v30 migration (HTML-unescape stored Gmail snippets)."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from poc.database import init_db
from poc.migrate_to_v30 import migrate

_NOW = datetime.now(timezone.utc).isoformat()


def _v29_db(tmp_path):
    db = tmp_path / "v29.db"
    init_db(db)
    conn = sqlite3.connect(db)
    conn.execute(
        "INSERT INTO customers (id, name, slug, is_active, created_at, updated_at) "
        "VALUES ('c', 'C', 'c', 1, ?, ?)", (_NOW, _NOW))
    conn.execute(
        "INSERT INTO provider_accounts (id, customer_id, provider, email_address, "
        "auth_token_path, created_at, updated_at) VALUES ('acct', 'c', 'gmail', "
        "'me@x.com', '/tmp/t.json', ?, ?)", (_NOW, _NOW))
    for cid, snippet in (
        ("cm1", "I&#39;ll need permission &amp; a budget"),
        ("cm2", "Already plain text"),
        ("cm3", "Tom &amp; Jerry &quot;cartoon&quot;"),
    ):
        conn.execute(
            "INSERT INTO communications (id, account_id, channel, timestamp, provider_message_id, "
            "snippet, created_at, updated_at) VALUES (?, 'acct', 'email', ?, ?, ?, ?, ?)",
            (cid, _NOW, "pm-" + cid, snippet, _NOW, _NOW))
    conn.execute("PRAGMA user_version = 29")
    conn.commit()
    conn.close()
    return db


def test_unescapes_snippets_and_bumps_version(tmp_path):
    db = _v29_db(tmp_path)
    migrate(db)
    conn = sqlite3.connect(db)
    assert conn.execute("PRAGMA user_version").fetchone()[0] == 30
    rows = dict(conn.execute("SELECT id, snippet FROM communications").fetchall())
    assert rows == {
        "cm1": "I'll need permission & a budget",
        "cm2": "Already plain text",
        "cm3": 'Tom & Jerry "cartoon"',
    }
    conn.close()


def test_idempotent(tmp_path):
    db = _v29_db(tmp_path)
    migrate(db)
    migrate(db)
    conn = sqlite3.connect(db)
    assert conn.execute("SELECT snippet FROM communications WHERE id='cm1'").fetchone()[0] == "I'll need permission & a budget"
    conn.close()
