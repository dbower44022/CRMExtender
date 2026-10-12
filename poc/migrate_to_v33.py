#!/usr/bin/env python3
"""Migrate the CRMExtender database from v32 to v33.

Mail Client MAIL-44 (release v10.42): ``mail_thread_links`` — which provider
threads in different accounts are the same conversation (same RFC 5322
Message-ID). The table is created and then filled from the stored mail.

Usage:
    python3 -m poc.migrate_to_v33 [--db PATH] [--dry-run]
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
CREATE TABLE IF NOT EXISTS mail_thread_links (
    account_id  TEXT NOT NULL REFERENCES provider_accounts(id) ON DELETE CASCADE,
    thread_id   TEXT NOT NULL,
    group_id    TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    PRIMARY KEY (account_id, thread_id)
);
CREATE INDEX IF NOT EXISTS idx_mail_thread_links_group ON mail_thread_links(group_id);
"""


def migrate(db_path: Path, *, dry_run: bool = False) -> None:
    if not db_path.exists():
        print(f"Error: Database not found at {db_path}")
        sys.exit(1)

    backup_path = db_path.with_suffix(
        f".v32-backup-{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
    )
    print(f"Backing up to {backup_path}...")
    shutil.copy2(str(db_path), str(backup_path))

    if dry_run:
        db_path = backup_path

    conn = sqlite3.connect(str(db_path), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    try:
        print("Step: creating mail_thread_links (if missing)...")
        conn.executescript(_DDL)
        print("Step: linking threads that share a Message-ID across accounts...")
        from poc.mail_links import rebuild_links
        stats = rebuild_links(conn)
        print(f"  {stats['message_ids']} shared Message-IDs -> {stats['groups']} groups over {stats['threads']} threads.")
        print("Step: bumping schema version to 33...")
        conn.execute("PRAGMA user_version = 33")
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
