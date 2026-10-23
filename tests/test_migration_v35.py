"""Tests for the v34 -> v35 migration (done_reason; thresholds become overrides). CONV-DNT-13."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from poc.database import init_db
from poc.migrate_to_v35 import migrate

_NOW = datetime.now(timezone.utc).isoformat()


def _v34_db(tmp_path):
    db = tmp_path / "v34.db"
    init_db(db)
    conn = sqlite3.connect(db)
    conn.execute("ALTER TABLE conversations DROP COLUMN done_reason")
    conn.execute("INSERT INTO customers (id, name, slug, is_active, created_at, updated_at) VALUES ('c', 'C', 'c', 1, ?, ?)", (_NOW, _NOW))
    conn.execute("INSERT INTO users (id, customer_id, email, name, role, is_active, created_at, updated_at) "
                 "VALUES ('u', 'c', 'u@c.com', 'U', 'admin', 1, ?, ?)", (_NOW, _NOW))
    rows = [
        ("default", "active", None, 14, 30),      # old column defaults → blanked
        ("override", "active", None, 21, 45),     # a genuine override → kept
        ("user-done", "done", "u", 14, 30),       # user close → stamped 'user'
        ("mixed", "active", None, 14, 60),        # one default, one override
    ]
    for cid, status, done_by, stale, closed in rows:
        conn.execute(
            "INSERT INTO conversations (id, customer_id, title, status, done_by, done_at, "
            "stale_after_days, closed_after_days, created_at, updated_at) VALUES (?, 'c', ?, ?, ?, ?, ?, ?, ?, ?)",
            (cid, cid, status, done_by, _NOW if done_by else None, stale, closed, _NOW, _NOW))
    conn.execute("PRAGMA user_version = 34")
    conn.commit()
    conn.close()
    return db


def test_adds_reason_and_blanks_default_thresholds(tmp_path):
    db = _v34_db(tmp_path)
    migrate(db)
    migrate(db)  # idempotent
    conn = sqlite3.connect(db)
    assert conn.execute("PRAGMA user_version").fetchone()[0] == 35
    got = {r[0]: r[1:] for r in conn.execute(
        "SELECT id, done_reason, stale_after_days, closed_after_days FROM conversations")}
    assert got["default"] == (None, None, None)
    assert got["override"] == (None, 21, 45)
    assert got["user-done"] == ("user", None, None)
    assert got["mixed"] == (None, None, 60)
    conn.close()


def test_dry_run_leaves_source_untouched(tmp_path):
    db = _v34_db(tmp_path)
    migrate(db, dry_run=True)
    conn = sqlite3.connect(db)
    assert conn.execute("PRAGMA user_version").fetchone()[0] == 34
    assert conn.execute("SELECT stale_after_days FROM conversations WHERE id = 'default'").fetchone()[0] == 14
    conn.close()
