#!/usr/bin/env python3
"""Migrate the CRMExtender database from v17 to v18.

Renames communications columns for clarity and adds new display/search columns:
- content     → original_text  (plain text body as received)
- body_html   → original_html  (HTML body as received)
- NEW: cleaned_html            (HTML with noise removed — what users see)
- NEW: search_text             (plain text with noise removed — what AI/search consume)

Usage:
    python3 -m poc.migrate_to_v18 [--db PATH] [--dry-run]
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
    """Run the full v17 -> v18 migration."""
    if not db_path.exists():
        print(f"Error: Database not found at {db_path}")
        sys.exit(1)

    backup_path = db_path.with_suffix(
        f".v17-backup-{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
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
    # Check current columns to make this idempotent
    cols = {r[1] for r in conn.execute("PRAGMA table_info(communications)")}

    # -------------------------------------------------------------------
    # Step 1: Rename content → original_text
    # -------------------------------------------------------------------
    if "content" in cols and "original_text" not in cols:
        print("\nStep 1a: Renaming content → original_text...")
        conn.execute("PRAGMA legacy_alter_table = ON")
        conn.execute("ALTER TABLE communications RENAME COLUMN content TO original_text")
        conn.execute("PRAGMA legacy_alter_table = OFF")
        print("  Done.")
    else:
        print("\nStep 1a: content → original_text already done, skipping.")

    # -------------------------------------------------------------------
    # Step 2: Rename body_html → original_html
    # -------------------------------------------------------------------
    if "body_html" in cols and "original_html" not in cols:
        print("\nStep 1b: Renaming body_html → original_html...")
        conn.execute("PRAGMA legacy_alter_table = ON")
        conn.execute("ALTER TABLE communications RENAME COLUMN body_html TO original_html")
        conn.execute("PRAGMA legacy_alter_table = OFF")
        print("  Done.")
    else:
        print("\nStep 1b: body_html → original_html already done, skipping.")

    # Refresh column list after renames
    cols = {r[1] for r in conn.execute("PRAGMA table_info(communications)")}

    # -------------------------------------------------------------------
    # Step 3: Add cleaned_html column
    # -------------------------------------------------------------------
    if "cleaned_html" not in cols:
        print("\nStep 2a: Adding cleaned_html column...")
        conn.execute("ALTER TABLE communications ADD COLUMN cleaned_html TEXT")
        print("  Done.")
    else:
        print("\nStep 2a: cleaned_html already exists, skipping.")

    # -------------------------------------------------------------------
    # Step 4: Add search_text column
    # -------------------------------------------------------------------
    if "search_text" not in cols:
        print("\nStep 2b: Adding search_text column...")
        conn.execute("ALTER TABLE communications ADD COLUMN search_text TEXT")
        print("  Done.")
    else:
        print("\nStep 2b: search_text already exists, skipping.")

    # -------------------------------------------------------------------
    # Step 5: Populate new columns from existing data
    # -------------------------------------------------------------------
    print("\nStep 3: Populating new columns from existing data...")
    result = conn.execute(
        "UPDATE communications SET "
        "cleaned_html = original_html, "
        "search_text = original_text "
        "WHERE cleaned_html IS NULL OR search_text IS NULL"
    )
    print(f"  Updated {result.rowcount} rows.")

    # -------------------------------------------------------------------
    # Step 6: Bump schema version
    # -------------------------------------------------------------------
    print("\nStep 4: Bumping schema version to 18...")
    conn.execute("PRAGMA user_version = 18")
    print("  Schema version set to 18.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Migrate CRMExtender database from v17 to v18.",
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
