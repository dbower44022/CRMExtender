#!/usr/bin/env python3
"""Migrate the CRMExtender database from v16 to v17.

Adds the Adaptive Grid Intelligence tables and columns:
- New table: user_view_layout_overrides (per-user, per-view, per-display-tier)
- New columns on views: preview_panel_size, auto_density,
  column_auto_sizing, column_demotion, primary_identifier_field

Usage:
    python3 -m poc.migrate_to_v17 [--db PATH] [--dry-run]
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
    """Run the full v16 -> v17 migration."""
    if not db_path.exists():
        print(f"Error: Database not found at {db_path}")
        sys.exit(1)

    backup_path = db_path.with_suffix(
        f".v16-backup-{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
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
    # Step 1: Create user_view_layout_overrides table
    # -------------------------------------------------------------------
    print("\nStep 1: Creating user_view_layout_overrides table...")
    conn.execute("""\
        CREATE TABLE IF NOT EXISTS user_view_layout_overrides (
            id               TEXT PRIMARY KEY,
            user_id          TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            view_id          TEXT NOT NULL REFERENCES views(id) ON DELETE CASCADE,
            display_tier     TEXT NOT NULL CHECK(display_tier IN (
                'ultra_wide','spacious','standard','constrained','minimal')),
            splitter_pct     REAL,
            density          TEXT CHECK(density IN ('compact','standard','comfortable')),
            column_overrides TEXT NOT NULL DEFAULT '{}',
            created_at       TEXT NOT NULL,
            updated_at       TEXT NOT NULL,
            UNIQUE(user_id, view_id, display_tier)
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_ulo_user_view "
        "ON user_view_layout_overrides(user_id, view_id)"
    )
    print("  user_view_layout_overrides table created.")

    # -------------------------------------------------------------------
    # Step 2: Add new columns to views table
    # -------------------------------------------------------------------
    print("\nStep 2: Adding new columns to views table...")
    views_cols = {r[1] for r in conn.execute("PRAGMA table_info(views)")}

    new_cols = [
        ("preview_panel_size", "TEXT DEFAULT 'medium'"),
        ("auto_density", "INTEGER DEFAULT 1"),
        ("column_auto_sizing", "INTEGER DEFAULT 1"),
        ("column_demotion", "INTEGER DEFAULT 1"),
        ("primary_identifier_field", "TEXT"),
    ]
    for col_name, col_def in new_cols:
        if col_name not in views_cols:
            conn.execute(f"ALTER TABLE views ADD COLUMN {col_name} {col_def}")
            print(f"  Added views.{col_name}")
        else:
            print(f"  views.{col_name} already exists, skipping.")

    # -------------------------------------------------------------------
    # Step 3: Bump schema version
    # -------------------------------------------------------------------
    print("\nStep 3: Bumping schema version to 17...")
    conn.execute("PRAGMA user_version = 17")
    print("  Schema version set to 17.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Migrate CRMExtender database from v16 to v17.",
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
