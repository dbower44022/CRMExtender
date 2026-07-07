#!/usr/bin/env python3
"""Migrate the CRMExtender database from v19 to v20.

Adds conversation view infrastructure:
- conversations gains is_aggregate, description, stale_after_days,
  closed_after_days, ai_confidence columns
- conversation_members junction table for aggregate parent-child relationships
- relationship_types CHECK constraints expanded to include conversation/event/project
- System relationship types seeded for conversation entity associations

Usage:
    python3 -m poc.migrate_to_v20 [--db PATH] [--dry-run]
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
    """Run the full v19 -> v20 migration."""
    if not db_path.exists():
        print(f"Error: Database not found at {db_path}")
        sys.exit(1)

    backup_path = db_path.with_suffix(
        f".v19-backup-{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
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
    existing_tables = {
        r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
    }

    # -------------------------------------------------------------------
    # Step 1: Add new columns to conversations table
    # -------------------------------------------------------------------
    conv_cols = {r[1] for r in conn.execute("PRAGMA table_info(conversations)")}

    if "is_aggregate" not in conv_cols:
        print("\nStep 1a: Adding is_aggregate to conversations...")
        conn.execute(
            "ALTER TABLE conversations ADD COLUMN is_aggregate INTEGER NOT NULL DEFAULT 0"
        )
        print("  Done.")
    else:
        print("\nStep 1a: is_aggregate already exists, skipping.")

    if "description" not in conv_cols:
        print("\nStep 1b: Adding description to conversations...")
        conn.execute(
            "ALTER TABLE conversations ADD COLUMN description TEXT"
        )
        print("  Done.")
    else:
        print("\nStep 1b: description already exists, skipping.")

    if "stale_after_days" not in conv_cols:
        print("\nStep 1c: Adding stale_after_days to conversations...")
        conn.execute(
            "ALTER TABLE conversations ADD COLUMN stale_after_days INTEGER DEFAULT 14"
        )
        print("  Done.")
    else:
        print("\nStep 1c: stale_after_days already exists, skipping.")

    if "closed_after_days" not in conv_cols:
        print("\nStep 1d: Adding closed_after_days to conversations...")
        conn.execute(
            "ALTER TABLE conversations ADD COLUMN closed_after_days INTEGER DEFAULT 30"
        )
        print("  Done.")
    else:
        print("\nStep 1d: closed_after_days already exists, skipping.")

    if "ai_confidence" not in conv_cols:
        print("\nStep 1e: Adding ai_confidence to conversations...")
        conn.execute(
            "ALTER TABLE conversations ADD COLUMN ai_confidence REAL"
        )
        print("  Done.")
    else:
        print("\nStep 1e: ai_confidence already exists, skipping.")

    # -------------------------------------------------------------------
    # Step 2: Create conversation_members junction table
    # -------------------------------------------------------------------
    if "conversation_members" not in existing_tables:
        print("\nStep 2: Creating conversation_members table...")
        conn.execute("""
            CREATE TABLE conversation_members (
                parent_conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
                child_conversation_id  TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
                position               INTEGER NOT NULL DEFAULT 0,
                created_at             TEXT NOT NULL,
                PRIMARY KEY (parent_conversation_id, child_conversation_id),
                CHECK (parent_conversation_id != child_conversation_id)
            )
        """)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_cm_child "
            "ON conversation_members(child_conversation_id)"
        )
        print("  Done.")
    else:
        print("\nStep 2: conversation_members already exists, skipping.")

    # -------------------------------------------------------------------
    # Step 3: Rebuild relationship_types to expand CHECK constraints
    # -------------------------------------------------------------------
    # SQLite doesn't support ALTER CHECK constraints directly.
    # We need to rebuild the table to include conversation/event/project.
    print("\nStep 3: Expanding relationship_types CHECK constraints...")
    conn.execute("PRAGMA legacy_alter_table = ON")

    # Check if constraints already expanded by trying an insert
    needs_rebuild = True
    try:
        conn.execute(
            "INSERT INTO relationship_types "
            "(id, name, from_entity_type, to_entity_type, forward_label, reverse_label, "
            "is_system, created_at, updated_at) "
            "VALUES ('__test__', '__test__', 'conversation', 'project', 'test', 'test', "
            "0, '2026-01-01', '2026-01-01')"
        )
        # If it succeeded, constraints are already expanded
        conn.execute("DELETE FROM relationship_types WHERE id = '__test__'")
        needs_rebuild = False
        print("  CHECK constraints already expanded, skipping rebuild.")
    except sqlite3.IntegrityError:
        pass

    if needs_rebuild:
        # Get existing data
        existing_rts = conn.execute("SELECT * FROM relationship_types").fetchall()
        existing_rels = conn.execute("SELECT * FROM relationships").fetchall()

        # Drop dependent table first (relationships references relationship_types)
        conn.execute("ALTER TABLE relationships RENAME TO _relationships_old")
        conn.execute("ALTER TABLE relationship_types RENAME TO _relationship_types_old")

        # Recreate with expanded CHECK constraints
        conn.execute("""
            CREATE TABLE relationship_types (
                id               TEXT PRIMARY KEY,
                customer_id      TEXT REFERENCES customers(id) ON DELETE CASCADE,
                name             TEXT NOT NULL UNIQUE,
                from_entity_type TEXT NOT NULL DEFAULT 'contact',
                to_entity_type   TEXT NOT NULL DEFAULT 'contact',
                forward_label    TEXT NOT NULL,
                reverse_label    TEXT NOT NULL,
                is_system        INTEGER NOT NULL DEFAULT 0,
                is_bidirectional INTEGER NOT NULL DEFAULT 0,
                description      TEXT,
                created_by       TEXT REFERENCES users(id) ON DELETE SET NULL,
                updated_by       TEXT REFERENCES users(id) ON DELETE SET NULL,
                created_at       TEXT NOT NULL,
                updated_at       TEXT NOT NULL,
                CHECK (from_entity_type IN ('contact', 'company', 'conversation')),
                CHECK (to_entity_type IN ('contact', 'company', 'conversation', 'project', 'event'))
            )
        """)

        # Recreate relationships table
        conn.execute("""
            CREATE TABLE relationships (
                id                      TEXT PRIMARY KEY,
                relationship_type_id    TEXT NOT NULL REFERENCES relationship_types(id) ON DELETE RESTRICT,
                from_entity_type        TEXT NOT NULL DEFAULT 'contact',
                from_entity_id          TEXT NOT NULL,
                to_entity_type          TEXT NOT NULL DEFAULT 'contact',
                to_entity_id            TEXT NOT NULL,
                paired_relationship_id  TEXT REFERENCES relationships(id) ON DELETE SET NULL,
                source                  TEXT NOT NULL DEFAULT 'manual',
                properties              TEXT,
                created_by              TEXT REFERENCES users(id) ON DELETE SET NULL,
                updated_by              TEXT REFERENCES users(id) ON DELETE SET NULL,
                created_at              TEXT NOT NULL,
                updated_at              TEXT NOT NULL,
                UNIQUE(from_entity_id, to_entity_id, relationship_type_id)
            )
        """)

        # Restore data
        for rt in existing_rts:
            rt = dict(rt)
            conn.execute(
                "INSERT INTO relationship_types "
                "(id, customer_id, name, from_entity_type, to_entity_type, "
                "forward_label, reverse_label, is_system, is_bidirectional, "
                "description, created_by, updated_by, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (rt["id"], rt["customer_id"], rt["name"],
                 rt["from_entity_type"], rt["to_entity_type"],
                 rt["forward_label"], rt["reverse_label"],
                 rt["is_system"], rt["is_bidirectional"],
                 rt["description"], rt["created_by"], rt["updated_by"],
                 rt["created_at"], rt["updated_at"]),
            )

        for rel in existing_rels:
            rel = dict(rel)
            conn.execute(
                "INSERT INTO relationships "
                "(id, relationship_type_id, from_entity_type, from_entity_id, "
                "to_entity_type, to_entity_id, paired_relationship_id, "
                "source, properties, created_by, updated_by, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (rel["id"], rel["relationship_type_id"],
                 rel["from_entity_type"], rel["from_entity_id"],
                 rel["to_entity_type"], rel["to_entity_id"],
                 rel["paired_relationship_id"], rel["source"],
                 rel["properties"], rel["created_by"], rel["updated_by"],
                 rel["created_at"], rel["updated_at"]),
            )

        # Drop old tables
        conn.execute("DROP TABLE _relationships_old")
        conn.execute("DROP TABLE _relationship_types_old")

        print("  Rebuilt relationship_types and relationships tables.")

    conn.execute("PRAGMA legacy_alter_table = OFF")

    # -------------------------------------------------------------------
    # Step 4: Seed conversation entity association relationship types
    # -------------------------------------------------------------------
    now = datetime.now(timezone.utc).isoformat()

    conv_rts = [
        ("rt-conv-project", "CONVERSATION_PROJECT", "conversation", "project",
         "Related to project", "Has conversations"),
        ("rt-conv-company", "CONVERSATION_COMPANY", "conversation", "company",
         "Related to company", "Has conversations"),
        ("rt-conv-contact", "CONVERSATION_CONTACT", "conversation", "contact",
         "Associated with contact", "Associated with conversation"),
        ("rt-conv-event", "CONVERSATION_EVENT", "conversation", "event",
         "Related to event", "Has conversations"),
    ]

    for rt_id, name, from_et, to_et, fwd, rev in conv_rts:
        existing = conn.execute(
            "SELECT id FROM relationship_types WHERE id = ?", (rt_id,)
        ).fetchone()
        if not existing:
            print(f"\nStep 4: Seeding relationship type {name}...")
            conn.execute(
                "INSERT INTO relationship_types "
                "(id, name, from_entity_type, to_entity_type, forward_label, "
                "reverse_label, is_system, is_bidirectional, description, "
                "created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, 1, 0, ?, ?, ?)",
                (rt_id, name, from_et, to_et, fwd, rev,
                 f"System: {fwd.lower()}", now, now),
            )
        else:
            print(f"\nStep 4: Relationship type {name} already exists, skipping.")

    # -------------------------------------------------------------------
    # Step 5: Bump schema version
    # -------------------------------------------------------------------
    print("\nStep 5: Bumping schema version to 20...")
    conn.execute("PRAGMA user_version = 20")
    print("  Schema version set to 20.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Migrate CRMExtender database from v19 to v20.",
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
