#!/usr/bin/env python3
"""Migrate the CRMExtender database from v4 to v5.

Adds:
- is_bidirectional column to relationship_types
- paired_relationship_id column to relationships
- Creates reverse rows for existing bidirectional relationships

Usage:
    python3 -m poc.migrate_to_v5 [--db PATH] [--dry-run]
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

BIDIRECTIONAL_TYPE_IDS = {"rt-knows", "rt-works-with", "rt-partner"}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def migrate(db_path: Path, *, dry_run: bool = False) -> None:
    """Run the full v4 -> v5 migration."""
    if not db_path.exists():
        print(f"Error: Database not found at {db_path}")
        sys.exit(1)

    # 1. Backup
    backup_path = db_path.with_suffix(
        f".v4-backup-{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
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
    now = _now_iso()

    # -------------------------------------------------------------------
    # Pre-migration counts
    # -------------------------------------------------------------------
    pre_relationships = conn.execute(
        "SELECT COUNT(*) FROM relationships"
    ).fetchone()[0]
    pre_types = conn.execute(
        "SELECT COUNT(*) FROM relationship_types"
    ).fetchone()[0]

    print(f"\nPre-migration counts:")
    print(f"  relationship_types: {pre_types}")
    print(f"  relationships: {pre_relationships}")

    # -------------------------------------------------------------------
    # Step 1: Add is_bidirectional column to relationship_types
    # -------------------------------------------------------------------
    print("\nStep 1: Adding is_bidirectional column to relationship_types...")
    cols = {
        row[1]
        for row in conn.execute("PRAGMA table_info(relationship_types)").fetchall()
    }
    if "is_bidirectional" in cols:
        print("  Column already exists — skipping.")
    else:
        conn.execute(
            "ALTER TABLE relationship_types ADD COLUMN is_bidirectional INTEGER NOT NULL DEFAULT 0"
        )
        print("  Added is_bidirectional column.")

    # Set bidirectional flag for seed types
    for type_id in BIDIRECTIONAL_TYPE_IDS:
        conn.execute(
            "UPDATE relationship_types SET is_bidirectional = 1 WHERE id = ?",
            (type_id,),
        )
    bidi_count = conn.execute(
        "SELECT COUNT(*) FROM relationship_types WHERE is_bidirectional = 1"
    ).fetchone()[0]
    print(f"  Marked {bidi_count} type(s) as bidirectional.")

    # -------------------------------------------------------------------
    # Step 2: Add paired_relationship_id column to relationships
    # -------------------------------------------------------------------
    print("\nStep 2: Adding paired_relationship_id column to relationships...")
    cols = {
        row[1]
        for row in conn.execute("PRAGMA table_info(relationships)").fetchall()
    }
    if "paired_relationship_id" in cols:
        print("  Column already exists — skipping.")
    else:
        conn.execute(
            "ALTER TABLE relationships ADD COLUMN paired_relationship_id TEXT "
            "REFERENCES relationships(id) ON DELETE SET NULL"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_relationships_paired "
            "ON relationships(paired_relationship_id)"
        )
        print("  Added paired_relationship_id column and index.")

    # -------------------------------------------------------------------
    # Step 3: Create reverse rows for existing bidirectional relationships
    # -------------------------------------------------------------------
    print("\nStep 3: Creating reverse rows for bidirectional relationships...")

    # Find all bidirectional type IDs (seed + any user-created)
    bidi_types = conn.execute(
        "SELECT id FROM relationship_types WHERE is_bidirectional = 1"
    ).fetchall()
    bidi_type_ids = {row["id"] for row in bidi_types}

    if not bidi_type_ids:
        print("  No bidirectional types found — skipping.")
    else:
        placeholders = ",".join("?" for _ in bidi_type_ids)
        existing = conn.execute(
            f"""SELECT * FROM relationships
                WHERE relationship_type_id IN ({placeholders})
                  AND paired_relationship_id IS NULL""",
            list(bidi_type_ids),
        ).fetchall()

        created = 0
        for row in existing:
            row = dict(row)
            fwd_id = row["id"]
            rev_id = str(uuid.uuid4())

            # Check if reverse already exists
            rev_exists = conn.execute(
                """SELECT id FROM relationships
                   WHERE from_entity_id = ? AND to_entity_id = ?
                     AND relationship_type_id = ?""",
                (row["to_entity_id"], row["from_entity_id"],
                 row["relationship_type_id"]),
            ).fetchone()

            if rev_exists:
                # Link existing pair
                rev_existing_id = rev_exists["id"]
                conn.execute(
                    "UPDATE relationships SET paired_relationship_id = ? WHERE id = ?",
                    (rev_existing_id, fwd_id),
                )
                conn.execute(
                    "UPDATE relationships SET paired_relationship_id = ? WHERE id = ?",
                    (fwd_id, rev_existing_id),
                )
            else:
                # Create reverse row
                conn.execute(
                    """INSERT INTO relationships
                       (id, relationship_type_id, from_entity_type, from_entity_id,
                        to_entity_type, to_entity_id, paired_relationship_id,
                        source, properties, created_by, updated_by,
                        created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        rev_id,
                        row["relationship_type_id"],
                        row["to_entity_type"],
                        row["to_entity_id"],
                        row["from_entity_type"],
                        row["from_entity_id"],
                        fwd_id,
                        row["source"],
                        row.get("properties"),
                        row.get("created_by"),
                        row.get("updated_by"),
                        now,
                        now,
                    ),
                )
                # Link forward row to reverse
                conn.execute(
                    "UPDATE relationships SET paired_relationship_id = ? WHERE id = ?",
                    (rev_id, fwd_id),
                )
                created += 1

        print(f"  Created {created} reverse row(s), linked existing pairs.")

    # -------------------------------------------------------------------
    # Step 4: Re-enable foreign keys and validate
    # -------------------------------------------------------------------
    print("\nStep 4: Validation...")
    conn.execute("PRAGMA foreign_keys=ON")

    post_relationships = conn.execute(
        "SELECT COUNT(*) FROM relationships"
    ).fetchone()[0]
    post_types = conn.execute(
        "SELECT COUNT(*) FROM relationship_types"
    ).fetchone()[0]

    # Verify paired_relationship_id integrity
    orphaned = conn.execute(
        """SELECT COUNT(*) FROM relationships
           WHERE paired_relationship_id IS NOT NULL
             AND paired_relationship_id NOT IN (SELECT id FROM relationships)"""
    ).fetchone()[0]

    # Verify all bidirectional rels have pairs
    unpaired_bidi = 0
    if bidi_type_ids:
        placeholders = ",".join("?" for _ in bidi_type_ids)
        unpaired_bidi = conn.execute(
            f"""SELECT COUNT(*) FROM relationships
                WHERE relationship_type_id IN ({placeholders})
                  AND paired_relationship_id IS NULL""",
            list(bidi_type_ids),
        ).fetchone()[0]

    print(f"\nPost-migration counts:")
    print(f"  relationship_types: {post_types}")
    print(f"  relationships: {post_relationships}")

    errors = []
    if orphaned:
        errors.append(f"{orphaned} orphaned paired_relationship_id reference(s)")
    if unpaired_bidi:
        errors.append(f"{unpaired_bidi} unpaired bidirectional relationship(s)")

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
        description="Migrate CRMExtender database from v4 to v5 schema (bidirectional relationships)"
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
