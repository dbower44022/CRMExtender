#!/usr/bin/env python3
"""Migrate the CRMExtender database from v3 to v4.

Adds:
- relationship_types table with seed data
- Rebuilds relationships table with FK to relationship_types,
  source column, and audit columns
- Migrates existing KNOWS relationships to reference the seed type

Usage:
    python3 -m poc.migrate_to_v4 [--db PATH] [--dry-run]
"""

from __future__ import annotations

import argparse
import shutil
import sqlite3
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def migrate(db_path: Path, *, dry_run: bool = False) -> None:
    """Run the full v3 -> v4 migration."""
    if not db_path.exists():
        print(f"Error: Database not found at {db_path}")
        sys.exit(1)

    # 1. Backup
    backup_path = db_path.with_suffix(
        f".v3-backup-{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
    )
    print(f"Backing up to {backup_path}...")
    shutil.copy2(str(db_path), str(backup_path))
    print(f"  Backup created ({backup_path.stat().st_size:,} bytes)")

    if dry_run:
        db_path = backup_path

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=OFF")  # OFF during table rebuild

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
    now = _now_iso()

    # -------------------------------------------------------------------
    # Pre-migration counts
    # -------------------------------------------------------------------
    pre_relationships = conn.execute(
        "SELECT COUNT(*) FROM relationships"
    ).fetchone()[0]

    print(f"\nPre-migration counts:")
    print(f"  relationships: {pre_relationships}")

    # -------------------------------------------------------------------
    # Step 1: Create relationship_types table
    # -------------------------------------------------------------------
    print("\nStep 1: Creating relationship_types table...")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS relationship_types (
            id               TEXT PRIMARY KEY,
            name             TEXT NOT NULL UNIQUE,
            from_entity_type TEXT NOT NULL DEFAULT 'contact',
            to_entity_type   TEXT NOT NULL DEFAULT 'contact',
            forward_label    TEXT NOT NULL,
            reverse_label    TEXT NOT NULL,
            is_system        INTEGER NOT NULL DEFAULT 0,
            description      TEXT,
            created_by       TEXT,
            updated_by       TEXT,
            created_at       TEXT NOT NULL,
            updated_at       TEXT NOT NULL,
            CHECK (from_entity_type IN ('contact', 'company')),
            CHECK (to_entity_type IN ('contact', 'company'))
        )
    """)
    print("  Created relationship_types table.")

    # -------------------------------------------------------------------
    # Step 2: Seed default relationship types
    # -------------------------------------------------------------------
    print("\nStep 2: Seeding default relationship types...")
    seed_types = [
        ("rt-knows",      "KNOWS",      "contact", "contact", "Knows",             "Knows",          1, "Auto-inferred co-occurrence"),
        ("rt-employee",   "EMPLOYEE",   "company", "contact", "Employs",           "Works at",       0, "Employment relationship"),
        ("rt-reports-to", "REPORTS_TO", "contact", "contact", "Has direct report", "Reports to",     0, "Reporting chain"),
        ("rt-works-with", "WORKS_WITH", "contact", "contact", "Works with",        "Works with",     0, "Peer / collaborator"),
        ("rt-partner",    "PARTNER",    "company", "company", "Partners with",     "Partners with",  0, "Business partnership"),
        ("rt-vendor",     "VENDOR",     "company", "company", "Is a vendor of",    "Is a client of", 0, "Vendor / client relationship"),
    ]
    for t in seed_types:
        conn.execute(
            """INSERT OR IGNORE INTO relationship_types
               (id, name, from_entity_type, to_entity_type, forward_label,
                reverse_label, is_system, description, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            t + (now, now),
        )
    type_count = conn.execute(
        "SELECT COUNT(*) FROM relationship_types"
    ).fetchone()[0]
    print(f"  Seeded {type_count} relationship type(s).")

    # -------------------------------------------------------------------
    # Step 3: Rebuild relationships table
    # -------------------------------------------------------------------
    print("\nStep 3: Rebuilding relationships table...")

    # Check if already migrated (has relationship_type_id column)
    cols = {
        row[1]
        for row in conn.execute("PRAGMA table_info(relationships)").fetchall()
    }
    if "relationship_type_id" in cols:
        print("  relationships table already has v4 schema — skipping rebuild.")
        post_relationships = conn.execute(
            "SELECT COUNT(*) FROM relationships"
        ).fetchone()[0]
    else:
        # Create new table
        conn.execute("""
            CREATE TABLE relationships_new (
                id                   TEXT PRIMARY KEY,
                relationship_type_id TEXT NOT NULL REFERENCES relationship_types(id) ON DELETE RESTRICT,
                from_entity_type     TEXT NOT NULL DEFAULT 'contact',
                from_entity_id       TEXT NOT NULL,
                to_entity_type       TEXT NOT NULL DEFAULT 'contact',
                to_entity_id         TEXT NOT NULL,
                source               TEXT NOT NULL DEFAULT 'manual',
                properties           TEXT,
                created_by           TEXT,
                updated_by           TEXT,
                created_at           TEXT NOT NULL,
                updated_at           TEXT NOT NULL,
                UNIQUE(from_entity_id, to_entity_id, relationship_type_id)
            )
        """)

        # Copy existing rows — map relationship_type='KNOWS' to rt-knows
        conn.execute("""
            INSERT INTO relationships_new
                (id, relationship_type_id, from_entity_type, from_entity_id,
                 to_entity_type, to_entity_id, source, properties,
                 created_at, updated_at)
            SELECT
                id, 'rt-knows', from_entity_type, from_entity_id,
                to_entity_type, to_entity_id, 'inferred', properties,
                created_at, updated_at
            FROM relationships
        """)

        post_relationships = conn.execute(
            "SELECT COUNT(*) FROM relationships_new"
        ).fetchone()[0]

        # Swap tables
        conn.execute("DROP TABLE relationships")
        conn.execute("ALTER TABLE relationships_new RENAME TO relationships")
        print(f"  Rebuilt relationships table ({post_relationships} rows migrated).")

    # -------------------------------------------------------------------
    # Step 4: Recreate indexes
    # -------------------------------------------------------------------
    print("\nStep 4: Creating indexes...")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_relationships_from ON relationships(from_entity_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_relationships_to ON relationships(to_entity_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_relationships_type ON relationships(relationship_type_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_relationships_source ON relationships(source)"
    )
    print("  Created 4 indexes.")

    # -------------------------------------------------------------------
    # Step 5: Re-enable foreign keys and validate
    # -------------------------------------------------------------------
    print("\nStep 5: Validation...")
    conn.execute("PRAGMA foreign_keys=ON")

    # Verify FK integrity
    fk_issues = conn.execute("PRAGMA foreign_key_check(relationships)").fetchall()
    if fk_issues:
        print(f"  WARNING: {len(fk_issues)} FK violation(s) in relationships table")
        for issue in fk_issues[:5]:
            print(f"    {issue}")

    print(f"\nPost-migration counts:")
    print(f"  relationship_types: {type_count}")
    print(f"  relationships: {post_relationships}")

    errors = []
    if post_relationships != pre_relationships:
        errors.append(
            f"Relationship count changed: {post_relationships} != {pre_relationships}"
        )

    if errors:
        print("\nVALIDATION ERRORS:")
        for e in errors:
            print(f"  ERROR: {e}")
        raise RuntimeError(
            f"Migration validation failed with {len(errors)} error(s)"
        )
    else:
        print("\nAll validations passed!")


def main():
    parser = argparse.ArgumentParser(
        description="Migrate CRMExtender database from v3 to v4 schema"
    )
    parser.add_argument(
        "--db", type=Path,
        help="Path to the SQLite database file",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Apply migration to a backup copy instead of the real database",
    )
    args = parser.parse_args()

    if args.db:
        db_path = args.db
    else:
        from poc import config
        db_path = config.DB_PATH

    migrate(db_path, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
