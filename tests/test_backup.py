"""Database backup command (v10.41): verified copy, timestamped name, pruning."""

from __future__ import annotations

import sqlite3
from datetime import datetime

import pytest

from poc.backup import BackupError, list_backups, make_backup, prune
from poc.database import init_db


def _db(tmp_path):
    db = tmp_path / "live.db"
    init_db(db)
    conn = sqlite3.connect(db)
    conn.execute("INSERT INTO customers (id, name, slug, is_active, created_at, updated_at) VALUES ('c', 'C', 'c', 1, 'x', 'x')")
    conn.commit(); conn.close()
    return db


def test_backup_writes_verified_copy_and_prunes(tmp_path):
    db = _db(tmp_path)
    archive = tmp_path / "archive"
    stamps = [datetime(2026, 10, d, 3, 0) for d in range(1, 10)]
    results = [make_backup(db, archive, keep=7, now=t) for t in stamps]
    assert results[-1]["path"].name == "crm_extender.20261009_0300.db"
    kept = [p.name for p in list_backups(archive)]
    assert len(kept) == 7 and kept[0] == "crm_extender.20261003_0300.db"
    assert [p.name for p in results[-1]["removed"]] == ["crm_extender.20261002_0300.db"]
    copy = sqlite3.connect(f"file:{results[-1]['path']}?mode=ro", uri=True)
    assert copy.execute("SELECT COUNT(*) FROM customers").fetchone()[0] == 1
    assert copy.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    copy.close()


def test_other_files_in_archive_are_left_alone(tmp_path):
    db = _db(tmp_path)
    archive = tmp_path / "archive"; archive.mkdir()
    (archive / "crm_extender.v9-backup-pre-fk-fix.db").write_bytes(b"old style")
    (archive / "notes.txt").write_text("keep me")
    make_backup(db, archive, keep=1, now=datetime(2026, 10, 1, 3))
    make_backup(db, archive, keep=1, now=datetime(2026, 10, 2, 3))
    assert (archive / "crm_extender.v9-backup-pre-fk-fix.db").exists() and (archive / "notes.txt").exists()
    assert [p.name for p in list_backups(archive)] == ["crm_extender.20261002_0300.db"]
    assert prune(archive, 0) == []


def test_missing_database_is_an_error(tmp_path):
    with pytest.raises(BackupError):
        make_backup(tmp_path / "nope.db", tmp_path / "archive")
