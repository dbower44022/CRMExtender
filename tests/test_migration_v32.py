"""Tests for the v31 -> v32 migration (mail_awaiting_dismissed)."""

from __future__ import annotations

import sqlite3

from poc.database import init_db
from poc.migrate_to_v32 import migrate


def _v31_db(tmp_path):
    db = tmp_path / "v31.db"
    init_db(db)
    conn = sqlite3.connect(db)
    conn.execute("DROP TABLE mail_awaiting_dismissed")
    conn.execute("PRAGMA user_version = 31")
    conn.commit(); conn.close()
    return db


def test_creates_table_and_is_idempotent(tmp_path):
    db = _v31_db(tmp_path)
    migrate(db); migrate(db)
    conn = sqlite3.connect(db)
    assert conn.execute("PRAGMA user_version").fetchone()[0] == 32
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "mail_awaiting_dismissed" in tables
    conn.close()
