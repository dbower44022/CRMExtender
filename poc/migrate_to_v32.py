#!/usr/bin/env python3
"""Migrate the CRMExtender database from v31 to v32.

Mail Client MAIL-47 (release v10.39): ``mail_awaiting_dismissed`` — threads
the owner told the awaiting-reply list to stop tracking. The list itself is
computed from the mirror on each read; this table only holds the opt-outs.

Usage:
    python3 -m poc.migrate_to_v32 [--db PATH] [--dry-run]
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

_DDL = """
CREATE TABLE IF NOT EXISTS mail_awaiting_dismissed (
    account_id   TEXT NOT NULL REFERENCES provider_accounts(id) ON DELETE CASCADE,
    thread_id    TEXT NOT NULL,
    dismissed_at TEXT NOT NULL,
    created_by   TEXT REFERENCES users(id) ON DELETE SET NULL,
    PRIMARY KEY (account_id, thread_id)
);
"""


def migrate(db_path: Path, *, dry_run: bool = False) -> None:
    if not db_path.exists():
        print(f"Error: Database not found at {db_path}")
        sys.exit(1)

    backup_path = db_path.with_suffix(
        f".v31-backup-{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
    )
    print(f"Backing up to {backup_path}...")
    shutil.copy2(str(db_path), str(backup_path))

    if dry_run:
        db_path = backup_path

    conn = sqlite3.connect(str(db_path), timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    try:
        print("Step: creating mail_awaiting_dismissed (if missing)...")
        conn.executescript(_DDL)
        print("Step: bumping schema version to 32...")
        conn.execute("PRAGMA user_version = 32")
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
