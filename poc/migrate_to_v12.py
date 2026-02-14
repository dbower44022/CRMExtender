#!/usr/bin/env python3
"""Migrate the CRMExtender database from v11 to v12.

Adds the Notes system tables: ``notes``, ``note_revisions``,
``note_attachments``, ``note_mentions``, and ``notes_fts`` (FTS5).

Usage:
    python3 -m poc.migrate_to_v12 [--db PATH] [--dry-run]
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
    """Run the full v11 -> v12 migration."""
    if not db_path.exists():
        print(f"Error: Database not found at {db_path}")
        sys.exit(1)

    # 1. Backup
    backup_path = db_path.with_suffix(
        f".v11-backup-{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
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
    # Step 1: Create notes table
    # -------------------------------------------------------------------
    print("\nStep 1: Creating notes table...")
    conn.execute("""\
        CREATE TABLE IF NOT EXISTS notes (
            id                  TEXT PRIMARY KEY,
            customer_id         TEXT NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
            entity_type         TEXT NOT NULL CHECK (entity_type IN ('contact','company','conversation','event','project')),
            entity_id           TEXT NOT NULL,
            title               TEXT,
            is_pinned           INTEGER NOT NULL DEFAULT 0,
            current_revision_id TEXT,
            created_by          TEXT REFERENCES users(id) ON DELETE SET NULL,
            updated_by          TEXT REFERENCES users(id) ON DELETE SET NULL,
            created_at          TEXT NOT NULL,
            updated_at          TEXT NOT NULL
        )
    """)
    print("  notes table created.")

    # -------------------------------------------------------------------
    # Step 2: Create note_revisions table
    # -------------------------------------------------------------------
    print("\nStep 2: Creating note_revisions table...")
    conn.execute("""\
        CREATE TABLE IF NOT EXISTS note_revisions (
            id              TEXT PRIMARY KEY,
            note_id         TEXT NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
            revision_number INTEGER NOT NULL,
            content_json    TEXT,
            content_html    TEXT,
            revised_by      TEXT REFERENCES users(id) ON DELETE SET NULL,
            created_at      TEXT NOT NULL,
            UNIQUE(note_id, revision_number)
        )
    """)
    print("  note_revisions table created.")

    # -------------------------------------------------------------------
    # Step 3: Create note_attachments table
    # -------------------------------------------------------------------
    print("\nStep 3: Creating note_attachments table...")
    conn.execute("""\
        CREATE TABLE IF NOT EXISTS note_attachments (
            id            TEXT PRIMARY KEY,
            note_id       TEXT REFERENCES notes(id) ON DELETE CASCADE,
            filename      TEXT NOT NULL,
            original_name TEXT NOT NULL,
            mime_type     TEXT NOT NULL,
            size_bytes    INTEGER NOT NULL,
            storage_path  TEXT NOT NULL,
            uploaded_by   TEXT REFERENCES users(id) ON DELETE SET NULL,
            created_at    TEXT NOT NULL
        )
    """)
    print("  note_attachments table created.")

    # -------------------------------------------------------------------
    # Step 4: Create note_mentions table
    # -------------------------------------------------------------------
    print("\nStep 4: Creating note_mentions table...")
    conn.execute("""\
        CREATE TABLE IF NOT EXISTS note_mentions (
            id           TEXT PRIMARY KEY,
            note_id      TEXT NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
            mention_type TEXT NOT NULL CHECK (mention_type IN ('user','contact','company','conversation','event','project')),
            mentioned_id TEXT NOT NULL,
            created_at   TEXT NOT NULL
        )
    """)
    print("  note_mentions table created.")

    # -------------------------------------------------------------------
    # Step 5: Create notes_fts FTS5 virtual table
    # -------------------------------------------------------------------
    print("\nStep 5: Creating notes_fts FTS5 virtual table...")
    conn.execute("""\
        CREATE VIRTUAL TABLE IF NOT EXISTS notes_fts USING fts5(
            note_id UNINDEXED,
            title,
            content_text,
            tokenize='porter unicode61'
        )
    """)
    print("  notes_fts virtual table created.")

    # -------------------------------------------------------------------
    # Step 6: Create indexes
    # -------------------------------------------------------------------
    print("\nStep 6: Creating indexes...")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_notes_entity ON notes(entity_type, entity_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_notes_customer ON notes(customer_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_notes_pinned ON notes(entity_type, entity_id, is_pinned DESC, updated_at DESC)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_note_revisions_note ON note_revisions(note_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_note_attachments_note ON note_attachments(note_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_note_mentions_note ON note_mentions(note_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_note_mentions_target ON note_mentions(mention_type, mentioned_id)")
    print("  All indexes created.")

    # -------------------------------------------------------------------
    # Step 7: Bump schema version
    # -------------------------------------------------------------------
    print("\nStep 7: Bumping schema version to 12...")
    conn.execute("PRAGMA user_version = 12")
    print("  Schema version set to 12.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Migrate CRMExtender database from v11 to v12.",
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
