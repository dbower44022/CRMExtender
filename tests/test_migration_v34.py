"""Tests for the v33 -> v34 migration (conversation Done audit columns). CONV-DNT-01."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from poc.database import init_db
from poc.migrate_to_v34 import migrate

_NOW = datetime.now(timezone.utc).isoformat()
_COLUMNS = ("done_at", "done_by", "reopened_at", "reopened_reason")


def _v33_db(tmp_path):
    db = tmp_path / "v33.db"
    init_db(db)
    conn = sqlite3.connect(db)
    for col in _COLUMNS:
        conn.execute(f"ALTER TABLE conversations DROP COLUMN {col}")
    conn.execute("INSERT INTO conversations (id, title, status, created_at, updated_at) "
                 "VALUES ('c1', 'Kept', 'active', ?, ?)", (_NOW, _NOW))
    conn.execute("PRAGMA user_version = 33")
    conn.commit()
    conn.close()
    return db


def test_adds_columns_idempotently(tmp_path):
    db = _v33_db(tmp_path)
    migrate(db)
    migrate(db)  # second run must skip every column
    conn = sqlite3.connect(db)
    assert conn.execute("PRAGMA user_version").fetchone()[0] == 34
    cols = {r[1] for r in conn.execute("PRAGMA table_info(conversations)")}
    assert set(_COLUMNS) <= cols
    row = conn.execute("SELECT status, done_at, reopened_reason FROM conversations WHERE id = 'c1'").fetchone()
    assert row == ("active", None, None)
    conn.close()


def test_dry_run_leaves_source_untouched(tmp_path):
    db = _v33_db(tmp_path)
    migrate(db, dry_run=True)
    conn = sqlite3.connect(db)
    assert conn.execute("PRAGMA user_version").fetchone()[0] == 33
    cols = {r[1] for r in conn.execute("PRAGMA table_info(conversations)")}
    assert "done_at" not in cols
    conn.close()
