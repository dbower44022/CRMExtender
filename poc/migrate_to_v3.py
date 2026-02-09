#!/usr/bin/env python3
"""Migrate the CRMExtender database from v2 to v3.

Adds:
- companies table
- company_id FK on contacts
- created_by / updated_by audit columns on contacts, contact_identifiers,
  conversations, projects, topics, and companies
- Backfills companies from existing contacts.company values
- New indexes

Usage:
    python3 -m poc.migrate_to_v3 [--db PATH] [--dry-run]
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
    """Run the full v2 -> v3 migration."""
    if not db_path.exists():
        print(f"Error: Database not found at {db_path}")
        sys.exit(1)

    # 1. Backup
    backup_path = db_path.with_suffix(
        f".v2-backup-{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
    )
    print(f"Backing up to {backup_path}...")
    shutil.copy2(str(db_path), str(backup_path))
    print(f"  Backup created ({backup_path.stat().st_size:,} bytes)")

    if dry_run:
        db_path = backup_path

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")

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
    pre = {}
    pre["contacts"] = conn.execute("SELECT COUNT(*) FROM contacts").fetchone()[0]
    pre["conversations"] = conn.execute("SELECT COUNT(*) FROM conversations").fetchone()[0]
    pre["projects"] = conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
    pre["topics"] = conn.execute("SELECT COUNT(*) FROM topics").fetchone()[0]

    print(f"\nPre-migration counts:")
    for k, v in pre.items():
        print(f"  {k}: {v}")

    # -------------------------------------------------------------------
    # Step 1: Create companies table
    # -------------------------------------------------------------------
    print("\nStep 1: Creating companies table...")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS companies (
            id          TEXT PRIMARY KEY,
            name        TEXT NOT NULL,
            domain      TEXT,
            industry    TEXT,
            description TEXT,
            status      TEXT DEFAULT 'active',
            created_by  TEXT,
            updated_by  TEXT,
            created_at  TEXT NOT NULL,
            updated_at  TEXT NOT NULL
        )
    """)
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_companies_name ON companies(name)"
    )
    print("  Created companies table.")

    # -------------------------------------------------------------------
    # Step 2: Add columns to contacts
    # -------------------------------------------------------------------
    print("\nStep 2: Adding columns to contacts...")
    _add_column(conn, "contacts", "company_id", "TEXT")
    _add_column(conn, "contacts", "created_by", "TEXT")
    _add_column(conn, "contacts", "updated_by", "TEXT")
    print("  Added company_id, created_by, updated_by to contacts.")

    # -------------------------------------------------------------------
    # Step 3: Add audit columns to contact_identifiers
    # -------------------------------------------------------------------
    print("\nStep 3: Adding audit columns to contact_identifiers...")
    _add_column(conn, "contact_identifiers", "created_by", "TEXT")
    _add_column(conn, "contact_identifiers", "updated_by", "TEXT")
    print("  Added created_by, updated_by to contact_identifiers.")

    # -------------------------------------------------------------------
    # Step 4: Add audit columns to conversations
    # -------------------------------------------------------------------
    print("\nStep 4: Adding audit columns to conversations...")
    _add_column(conn, "conversations", "created_by", "TEXT")
    _add_column(conn, "conversations", "updated_by", "TEXT")
    print("  Added created_by, updated_by to conversations.")

    # -------------------------------------------------------------------
    # Step 5: Add audit columns to projects
    # -------------------------------------------------------------------
    print("\nStep 5: Adding audit columns to projects...")
    _add_column(conn, "projects", "created_by", "TEXT")
    _add_column(conn, "projects", "updated_by", "TEXT")
    print("  Added created_by, updated_by to projects.")

    # -------------------------------------------------------------------
    # Step 6: Add audit columns to topics
    # -------------------------------------------------------------------
    print("\nStep 6: Adding audit columns to topics...")
    _add_column(conn, "topics", "created_by", "TEXT")
    _add_column(conn, "topics", "updated_by", "TEXT")
    print("  Added created_by, updated_by to topics.")

    # -------------------------------------------------------------------
    # Step 7: Backfill companies from contacts.company
    # -------------------------------------------------------------------
    print("\nStep 7: Backfilling companies from contacts.company...")
    distinct_companies = conn.execute(
        "SELECT DISTINCT company FROM contacts WHERE company IS NOT NULL AND company != ''"
    ).fetchall()

    for row in distinct_companies:
        company_name = row[0]
        company_id = str(uuid.uuid4())
        conn.execute(
            """INSERT OR IGNORE INTO companies (id, name, status, created_at, updated_at)
               VALUES (?, ?, 'active', ?, ?)""",
            (company_id, company_name, now, now),
        )
    print(f"  Created {len(distinct_companies)} company record(s).")

    # -------------------------------------------------------------------
    # Step 8: Backfill contacts.company_id
    # -------------------------------------------------------------------
    print("\nStep 8: Linking contacts to companies...")
    conn.execute("""
        UPDATE contacts SET company_id = (
            SELECT id FROM companies WHERE name = contacts.company
        )
        WHERE company IS NOT NULL AND company != ''
    """)
    linked = conn.execute(
        "SELECT COUNT(*) FROM contacts WHERE company_id IS NOT NULL"
    ).fetchone()[0]
    print(f"  Linked {linked} contact(s) to companies.")

    # -------------------------------------------------------------------
    # Step 9: Create new indexes
    # -------------------------------------------------------------------
    print("\nStep 9: Creating new indexes...")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_companies_domain ON companies(domain)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_contacts_company ON contacts(company_id)"
    )
    print("  Created 2 new indexes.")

    # -------------------------------------------------------------------
    # Step 10: Validation
    # -------------------------------------------------------------------
    print("\nStep 10: Validation...")

    post = {}
    post["contacts"] = conn.execute("SELECT COUNT(*) FROM contacts").fetchone()[0]
    post["conversations"] = conn.execute("SELECT COUNT(*) FROM conversations").fetchone()[0]
    post["companies"] = conn.execute("SELECT COUNT(*) FROM companies").fetchone()[0]

    print(f"\nPost-migration counts:")
    for k, v in post.items():
        print(f"  {k}: {v}")

    errors = []
    if post["contacts"] != pre["contacts"]:
        errors.append(
            f"Contact count changed: {post['contacts']} != {pre['contacts']}"
        )
    if post["conversations"] != pre["conversations"]:
        errors.append(
            f"Conversation count changed: {post['conversations']} != {pre['conversations']}"
        )

    # Verify companies count matches distinct company values
    if post["companies"] != len(distinct_companies):
        errors.append(
            f"Companies count mismatch: {post['companies']} != {len(distinct_companies)}"
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


def _add_column(conn: sqlite3.Connection, table: str, column: str, col_type: str) -> None:
    """Add a column to a table if it doesn't already exist."""
    try:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e).lower():
            pass  # Already exists
        else:
            raise


def main():
    parser = argparse.ArgumentParser(
        description="Migrate CRMExtender database from v2 to v3 schema"
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
