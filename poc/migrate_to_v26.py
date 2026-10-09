#!/usr/bin/env python3
"""Migrate the CRMExtender database from v25 to v26.

Mail Client PRD MAIL-15: attachment metadata from the provider on the
``attachments`` table (``provider_attachment_id``, ``content_id``,
``is_inline``) and a unique index per message/part. Bytes are fetched on
demand into the attachment cache; nothing is downloaded here.

Usage:
    python3 -m poc.migrate_to_v26 [--db PATH] [--dry-run]
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

_NEW_COLUMNS = (
    ("provider_attachment_id", "TEXT"),
    ("content_id", "TEXT"),
    ("is_inline", "INTEGER NOT NULL DEFAULT 0"),
)


def migrate(db_path: Path, *, dry_run: bool = False) -> None:
    if not db_path.exists():
        print(f"Error: Database not found at {db_path}")
        sys.exit(1)

    backup_path = db_path.with_suffix(
        f".v25-backup-{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
    )
    print(f"Backing up to {backup_path}...")
    shutil.copy2(str(db_path), str(backup_path))

    if dry_run:
        db_path = backup_path

    conn = sqlite3.connect(str(db_path), timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    try:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(attachments)")}
        for name, decl in _NEW_COLUMNS:
            if name in cols:
                print(f"Step: attachments.{name} already exists, skipping.")
                continue
            print(f"Step: adding attachments.{name}...")
            conn.execute(f"ALTER TABLE attachments ADD COLUMN {name} {decl}")
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_attachments_provider "
                     "ON attachments(communication_id, provider_attachment_id)")
        print("Step: bumping schema version to 26...")
        conn.execute("PRAGMA user_version = 26")
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
