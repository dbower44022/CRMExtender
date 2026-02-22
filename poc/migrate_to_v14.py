#!/usr/bin/env python3
"""Migrate the CRMExtender database from v13 to v14.

Adds the ``contact_tags`` junction table so that tags can be associated
with individual contacts (in addition to conversations).

Usage:
    python3 -m poc.migrate_to_v14 [--db PATH] [--dry-run]
"""

from __future__ import annotations

import argparse
import shutil
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

DEFAULT_DB = Path("data/crm_extender.db")


def migrate(db_path: Path, *, dry_run: bool = False) -> None:
    """Run the full v13 -> v14 migration."""
    if not db_path.exists():
        print(f"Error: Database not found at {db_path}")
        sys.exit(1)

    # 1. Backup
    backup_path = db_path.with_suffix(
        f".v13-backup-{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
    )
    print(f"Backing up to {backup_path}...")
    shutil.copy2(str(db_path), str(backup_path))
    print(f"  Backup created ({backup_path.stat().st_size:,} bytes)")

    if dry_run:
        db_path = backup_path

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=OFF")

    try:
        _run_migration(conn)
        conn.commit()
        print("\nMigration committed successfully.")
    except Exception:
        conn.rollback()
        print("\nMigration FAILED — rolled back.")
        raise
    finally:
        conn.close()

    if dry_run:
        print(f"\nDry run complete. Changes applied to backup: {backup_path}")
        print("Production database was NOT modified.")
    else:
        print(f"\nProduction database migrated. Backup at: {backup_path}")


def _run_migration(conn: sqlite3.Connection) -> None:
    """Execute all migration steps in order."""

    # -------------------------------------------------------------------
    # Step 1: Create contact_tags junction table
    # -------------------------------------------------------------------
    print("\nStep 1: Creating contact_tags table...")
    conn.execute("""\
        CREATE TABLE IF NOT EXISTS contact_tags (
            contact_id TEXT NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
            tag_id     TEXT NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
            source     TEXT DEFAULT 'manual',
            confidence REAL DEFAULT 1.0,
            created_at TEXT NOT NULL,
            PRIMARY KEY (contact_id, tag_id)
        )
    """)
    print("  contact_tags table created.")

    # -------------------------------------------------------------------
    # Step 2: Create indexes
    # -------------------------------------------------------------------
    print("\nStep 2: Creating indexes...")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_contact_tags_contact ON contact_tags(contact_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_contact_tags_tag ON contact_tags(tag_id)")
    print("  Indexes created.")

    # -------------------------------------------------------------------
    # Step 3: Bump schema version
    # -------------------------------------------------------------------
    print("\nStep 3: Bumping schema version to 14...")
    conn.execute("PRAGMA user_version = 14")
    print("  Schema version set to 14.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Migrate CRMExtender database from v13 to v14.",
    )
    parser.add_argument(
        "--db", type=Path, default=DEFAULT_DB,
        help=f"Path to database (default: {DEFAULT_DB})",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Run on a backup copy; do not modify production database.",
    )
    args = parser.parse_args()
    migrate(args.db, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
