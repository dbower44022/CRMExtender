#!/usr/bin/env python3
"""Migrate the CRMExtender database from v14 to v15.

Adds temporal tracking columns (is_current, started_at, ended_at) to
phone_numbers, addresses, email_addresses, and contact_identifiers.
Replaces ``contact_identifiers.status`` with ``is_current`` INTEGER.

Usage:
    python3 -m poc.migrate_to_v15 [--db PATH] [--dry-run]
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
    """Run the full v14 -> v15 migration."""
    if not db_path.exists():
        print(f"Error: Database not found at {db_path}")
        sys.exit(1)

    # 1. Backup
    backup_path = db_path.with_suffix(
        f".v14-backup-{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
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
    # Step 1: Add temporal columns to phone_numbers
    # -------------------------------------------------------------------
    print("\nStep 1: Adding temporal columns to phone_numbers...")
    _add_column_if_missing(conn, "phone_numbers", "is_current", "INTEGER NOT NULL DEFAULT 1")
    _add_column_if_missing(conn, "phone_numbers", "started_at", "TEXT")
    _add_column_if_missing(conn, "phone_numbers", "ended_at", "TEXT")
    print("  phone_numbers columns added.")

    # -------------------------------------------------------------------
    # Step 2: Add temporal columns to addresses
    # -------------------------------------------------------------------
    print("\nStep 2: Adding temporal columns to addresses...")
    _add_column_if_missing(conn, "addresses", "is_current", "INTEGER NOT NULL DEFAULT 1")
    _add_column_if_missing(conn, "addresses", "started_at", "TEXT")
    _add_column_if_missing(conn, "addresses", "ended_at", "TEXT")
    print("  addresses columns added.")

    # -------------------------------------------------------------------
    # Step 3: Add temporal columns to email_addresses
    # -------------------------------------------------------------------
    print("\nStep 3: Adding temporal columns to email_addresses...")
    _add_column_if_missing(conn, "email_addresses", "is_current", "INTEGER NOT NULL DEFAULT 1")
    _add_column_if_missing(conn, "email_addresses", "started_at", "TEXT")
    _add_column_if_missing(conn, "email_addresses", "ended_at", "TEXT")
    print("  email_addresses columns added.")

    # -------------------------------------------------------------------
    # Step 4: Rebuild contact_identifiers (status -> is_current)
    # -------------------------------------------------------------------
    print("\nStep 4: Rebuilding contact_identifiers (status -> is_current)...")
    conn.execute("PRAGMA legacy_alter_table = ON")

    conn.execute("ALTER TABLE contact_identifiers RENAME TO contact_identifiers_old")

    conn.execute("""\
        CREATE TABLE contact_identifiers (
            id         TEXT PRIMARY KEY,
            contact_id TEXT NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
            type       TEXT NOT NULL,
            value      TEXT NOT NULL,
            label      TEXT,
            is_primary INTEGER DEFAULT 0,
            is_current INTEGER NOT NULL DEFAULT 1,
            source     TEXT,
            verified   INTEGER DEFAULT 0,
            started_at TEXT,
            ended_at   TEXT,
            created_by TEXT REFERENCES users(id) ON DELETE SET NULL,
            updated_by TEXT REFERENCES users(id) ON DELETE SET NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(type, value)
        )
    """)

    conn.execute("""\
        INSERT INTO contact_identifiers
            (id, contact_id, type, value, label, is_primary,
             is_current, source, verified, created_by, updated_by,
             created_at, updated_at)
        SELECT id, contact_id, type, value, label, is_primary,
            CASE WHEN COALESCE(status, 'active') = 'active' THEN 1 ELSE 0 END,
            source, verified, created_by, updated_by,
            created_at, updated_at
        FROM contact_identifiers_old
    """)

    row_count = conn.execute("SELECT COUNT(*) AS cnt FROM contact_identifiers").fetchone()["cnt"]
    print(f"  Migrated {row_count} contact_identifiers rows.")

    conn.execute("DROP TABLE contact_identifiers_old")
    conn.execute("PRAGMA legacy_alter_table = OFF")
    print("  contact_identifiers rebuilt.")

    # -------------------------------------------------------------------
    # Step 5: Create indexes
    # -------------------------------------------------------------------
    print("\nStep 5: Creating indexes...")
    # Recreate indexes lost during rebuild
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ci_contact ON contact_identifiers(contact_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ci_current ON contact_identifiers(is_current)")

    # New composite indexes for entity-agnostic tables
    conn.execute("CREATE INDEX IF NOT EXISTS idx_phone_current ON phone_numbers(entity_type, entity_id, is_current)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_addr_current ON addresses(entity_type, entity_id, is_current)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_email_current ON email_addresses(entity_type, entity_id, is_current)")
    print("  Indexes created.")

    # -------------------------------------------------------------------
    # Step 6: Bump schema version
    # -------------------------------------------------------------------
    print("\nStep 6: Bumping schema version to 15...")
    conn.execute("PRAGMA user_version = 15")
    print("  Schema version set to 15.")


def _add_column_if_missing(
    conn: sqlite3.Connection, table: str, column: str, col_type: str,
) -> None:
    """Add a column to a table if it doesn't already exist."""
    cols = {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
    if column not in cols:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Migrate CRMExtender database from v14 to v15.",
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
