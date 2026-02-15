#!/usr/bin/env python3
"""Migrate the CRMExtender database from v12 to v13.

Introduces the ``note_entities`` junction table so that a single note can
be linked to multiple entities.  Moves ``entity_type``, ``entity_id``,
and ``is_pinned`` out of the ``notes`` table and into ``note_entities``.

Usage:
    python3 -m poc.migrate_to_v13 [--db PATH] [--dry-run]
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
    """Run the full v12 -> v13 migration."""
    if not db_path.exists():
        print(f"Error: Database not found at {db_path}")
        sys.exit(1)

    # 1. Backup
    backup_path = db_path.with_suffix(
        f".v12-backup-{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
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
    # Step 1: Create note_entities junction table
    # -------------------------------------------------------------------
    print("\nStep 1: Creating note_entities table...")
    conn.execute("""\
        CREATE TABLE IF NOT EXISTS note_entities (
            note_id     TEXT NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
            entity_type TEXT NOT NULL CHECK (entity_type IN ('contact','company','conversation','event','project')),
            entity_id   TEXT NOT NULL,
            is_pinned   INTEGER NOT NULL DEFAULT 0,
            created_at  TEXT NOT NULL,
            PRIMARY KEY (note_id, entity_type, entity_id)
        )
    """)
    print("  note_entities table created.")

    # -------------------------------------------------------------------
    # Step 2: Populate from existing notes data
    # -------------------------------------------------------------------
    print("\nStep 2: Populating note_entities from notes...")
    count = conn.execute(
        "INSERT INTO note_entities (note_id, entity_type, entity_id, is_pinned, created_at) "
        "SELECT id, entity_type, entity_id, is_pinned, created_at FROM notes"
    ).rowcount
    print(f"  {count} rows inserted into note_entities.")

    # -------------------------------------------------------------------
    # Step 3: Rebuild notes table without entity_type, entity_id, is_pinned
    # -------------------------------------------------------------------
    print("\nStep 3: Rebuilding notes table...")

    # Prevent FK auto-rewrite when renaming
    conn.execute("PRAGMA legacy_alter_table = ON")

    conn.execute("ALTER TABLE notes RENAME TO notes_old")

    conn.execute("""\
        CREATE TABLE notes (
            id                  TEXT PRIMARY KEY,
            customer_id         TEXT NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
            title               TEXT,
            current_revision_id TEXT,
            created_by          TEXT REFERENCES users(id) ON DELETE SET NULL,
            updated_by          TEXT REFERENCES users(id) ON DELETE SET NULL,
            created_at          TEXT NOT NULL,
            updated_at          TEXT NOT NULL
        )
    """)

    conn.execute("""\
        INSERT INTO notes (id, customer_id, title, current_revision_id,
                           created_by, updated_by, created_at, updated_at)
        SELECT id, customer_id, title, current_revision_id,
               created_by, updated_by, created_at, updated_at
        FROM notes_old
    """)

    conn.execute("DROP TABLE notes_old")
    conn.execute("PRAGMA legacy_alter_table = OFF")
    print("  notes table rebuilt (entity_type, entity_id, is_pinned removed).")

    # -------------------------------------------------------------------
    # Step 4: Create indexes on note_entities
    # -------------------------------------------------------------------
    print("\nStep 4: Creating indexes...")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ne_entity ON note_entities(entity_type, entity_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ne_note ON note_entities(note_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ne_pinned ON note_entities(entity_type, entity_id, is_pinned DESC)")

    # Recreate notes indexes (the old idx_notes_entity and idx_notes_pinned
    # were dropped with notes_old; recreate customer index)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_notes_customer ON notes(customer_id)")
    print("  All indexes created.")

    # -------------------------------------------------------------------
    # Step 5: Bump schema version
    # -------------------------------------------------------------------
    print("\nStep 5: Bumping schema version to 13...")
    conn.execute("PRAGMA user_version = 13")
    print("  Schema version set to 13.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Migrate CRMExtender database from v12 to v13.",
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
