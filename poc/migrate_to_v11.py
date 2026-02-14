#!/usr/bin/env python3
"""Migrate the CRMExtender database from v10 to v11.

Deduplicates ``contact_companies`` rows that were created because SQLite's
UNIQUE constraint treats NULL values as distinct.  Adds a NULL-safe unique
index using COALESCE so that ``INSERT OR IGNORE`` correctly prevents
duplicates when ``role_id`` and ``started_at`` are NULL.

Usage:
    python3 -m poc.migrate_to_v11 [--db PATH] [--dry-run]
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


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def migrate(db_path: Path, *, dry_run: bool = False) -> None:
    """Run the full v10 -> v11 migration."""
    if not db_path.exists():
        print(f"Error: Database not found at {db_path}")
        sys.exit(1)

    # 1. Backup
    backup_path = db_path.with_suffix(
        f".v10-backup-{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
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
    # Step 1: Deduplicate contact_companies rows
    # -------------------------------------------------------------------
    print("\nStep 1: Deduplicating contact_companies rows...")

    # Find duplicate groups (same contact + company + role + started_at,
    # treating NULLs as equal).
    dupes = conn.execute("""\
        SELECT contact_id, company_id,
               COALESCE(role_id, '') AS role_key,
               COALESCE(started_at, '') AS start_key,
               COUNT(*) AS cnt,
               MIN(created_at) AS earliest
        FROM contact_companies
        GROUP BY contact_id, company_id,
                 COALESCE(role_id, ''), COALESCE(started_at, '')
        HAVING COUNT(*) > 1
    """).fetchall()

    total_deleted = 0
    for d in dupes:
        # Keep the earliest row, delete the rest.
        rows_in_group = conn.execute("""\
            SELECT id FROM contact_companies
            WHERE contact_id = ?
              AND company_id = ?
              AND COALESCE(role_id, '') = ?
              AND COALESCE(started_at, '') = ?
            ORDER BY created_at ASC
        """, (d["contact_id"], d["company_id"],
              d["role_key"], d["start_key"])).fetchall()

        keep_id = rows_in_group[0]["id"]
        delete_ids = [r["id"] for r in rows_in_group[1:]]
        if delete_ids:
            placeholders = ",".join("?" * len(delete_ids))
            conn.execute(
                f"DELETE FROM contact_companies WHERE id IN ({placeholders})",
                delete_ids,
            )
            total_deleted += len(delete_ids)

    print(f"  Found {len(dupes)} duplicate groups, deleted {total_deleted} rows.")

    # -------------------------------------------------------------------
    # Step 1b: Remove NULL-role affiliations that duplicate explicit-role ones
    # -------------------------------------------------------------------
    print("\nStep 1b: Removing redundant NULL-role affiliations...")
    null_deleted = conn.execute("""\
        DELETE FROM contact_companies
        WHERE id IN (
            SELECT cc_null.id
            FROM contact_companies cc_null
            JOIN contact_companies cc_role
              ON cc_null.contact_id = cc_role.contact_id
             AND cc_null.company_id = cc_role.company_id
             AND cc_null.id != cc_role.id
            WHERE cc_null.role_id IS NULL
              AND cc_role.role_id IS NOT NULL
        )
    """).rowcount
    print(f"  Deleted {null_deleted} redundant NULL-role affiliations.")

    # -------------------------------------------------------------------
    # Step 2: Create NULL-safe unique index
    # -------------------------------------------------------------------
    print("\nStep 2: Creating NULL-safe unique index on contact_companies...")
    conn.execute("""\
        CREATE UNIQUE INDEX IF NOT EXISTS idx_cc_dedup
        ON contact_companies(
            contact_id, company_id,
            COALESCE(role_id, ''), COALESCE(started_at, '')
        )
    """)
    print("  Index idx_cc_dedup created.")

    # -------------------------------------------------------------------
    # Step 3: Bump schema version
    # -------------------------------------------------------------------
    print("\nStep 3: Bumping schema version to 11...")
    conn.execute("PRAGMA user_version = 11")
    print("  Schema version set to 11.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Migrate CRMExtender database from v10 to v11.",
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
