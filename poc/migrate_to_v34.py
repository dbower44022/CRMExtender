#!/usr/bin/env python3
"""Migrate the CRMExtender database from v33 to v34.

Conversation Done state (release v10.44, Conversation Entity TDD §9.8):
four audit columns on ``conversations`` — ``done_at``, ``done_by``,
``reopened_at``, ``reopened_reason``. The ``status`` column gains the value
``done``; no existing row changes.

Usage:
    python3 -m poc.migrate_to_v34 [--db PATH] [--dry-run]
"""

from __future__ import annotations

import argparse
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

DEFAULT_DB = Path("data/crm_extender.db")

_CONVERSATION_COLUMNS = (
    ("done_at", "TEXT"),
    ("done_by", "TEXT REFERENCES users(id) ON DELETE SET NULL"),
    ("reopened_at", "TEXT"),
    ("reopened_reason", "TEXT"),
)


def migrate(db_path: Path, *, dry_run: bool = False) -> None:
    if not db_path.exists():
        print(f"Error: Database not found at {db_path}")
        sys.exit(1)

    backup_path = db_path.with_suffix(
        f".v33-backup-{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
    )
    print(f"Backing up to {backup_path}...")
    shutil.copy2(str(db_path), str(backup_path))

    if dry_run:
        db_path = backup_path

    conn = sqlite3.connect(str(db_path), timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    try:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(conversations)")}
        for name, decl in _CONVERSATION_COLUMNS:
            if name in cols:
                print(f"Step: conversations.{name} already exists, skipping.")
                continue
            print(f"Step: adding conversations.{name}...")
            conn.execute(f"ALTER TABLE conversations ADD COLUMN {name} {decl}")
        print("Step: indexing conversations.status (if missing)...")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_conv_status ON conversations(status)")
        print("Step: bumping schema version to 34...")
        conn.execute("PRAGMA user_version = 34")
        conn.commit()
        print("Migration committed successfully.")
    except Exception:
        conn.rollback()
        print("Migration FAILED — rolled back.")
        raise
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    migrate(args.db, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
