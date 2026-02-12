#!/usr/bin/env python3
"""Migrate the CRMExtender database from v9 to v10.

Creates the ``contact_company_roles`` and ``contact_companies`` tables,
migrates existing ``contacts.company_id`` relationships into affiliation
rows, rebuilds the ``contacts`` table without the ``company_id`` and
``company`` columns, and removes the ``rt-employee`` relationship type.

Usage:
    python3 -m poc.migrate_to_v10 [--db PATH] [--dry-run]
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

DEFAULT_CUSTOMER_ID = "cust-default"

_SYSTEM_ROLES = [
    ("ccr-employee", "Employee", 0),
    ("ccr-contractor", "Contractor", 1),
    ("ccr-volunteer", "Volunteer", 2),
    ("ccr-advisor", "Advisor", 3),
    ("ccr-board-member", "Board Member", 4),
    ("ccr-investor", "Investor", 5),
    ("ccr-founder", "Founder", 6),
    ("ccr-intern", "Intern", 7),
]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def migrate(db_path: Path, *, dry_run: bool = False) -> None:
    """Run the full v9 -> v10 migration."""
    if not db_path.exists():
        print(f"Error: Database not found at {db_path}")
        sys.exit(1)

    # 1. Backup
    backup_path = db_path.with_suffix(
        f".v9-backup-{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
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
    # Step 1: Create contact_company_roles table + seed system roles
    # -------------------------------------------------------------------
    print("\nStep 1: Creating contact_company_roles table...")
    conn.execute("""\
        CREATE TABLE IF NOT EXISTS contact_company_roles (
            id          TEXT PRIMARY KEY,
            customer_id TEXT REFERENCES customers(id) ON DELETE CASCADE,
            name        TEXT NOT NULL,
            sort_order  INTEGER NOT NULL DEFAULT 0,
            is_system   INTEGER NOT NULL DEFAULT 0,
            created_by  TEXT REFERENCES users(id) ON DELETE SET NULL,
            updated_by  TEXT REFERENCES users(id) ON DELETE SET NULL,
            created_at  TEXT NOT NULL,
            updated_at  TEXT NOT NULL,
            UNIQUE(customer_id, name)
        )
    """)

    # Seed system roles for each customer
    customers = conn.execute("SELECT id FROM customers").fetchall()
    for cust in customers:
        for role_id, role_name, sort_order in _SYSTEM_ROLES:
            full_id = f"{role_id}-{cust['id']}"
            conn.execute(
                """INSERT OR IGNORE INTO contact_company_roles
                   (id, customer_id, name, sort_order, is_system, created_at, updated_at)
                   VALUES (?, ?, ?, ?, 1, ?, ?)""",
                (full_id, cust["id"], role_name, sort_order, now, now),
            )
    print(f"  Seeded {len(_SYSTEM_ROLES)} system roles for {len(customers)} customer(s).")

    # -------------------------------------------------------------------
    # Step 2: Create contact_companies junction table
    # -------------------------------------------------------------------
    print("\nStep 2: Creating contact_companies table...")
    conn.execute("""\
        CREATE TABLE IF NOT EXISTS contact_companies (
            id         TEXT PRIMARY KEY,
            contact_id TEXT NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
            company_id TEXT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
            role_id    TEXT REFERENCES contact_company_roles(id) ON DELETE SET NULL,
            title      TEXT,
            department TEXT,
            is_primary INTEGER NOT NULL DEFAULT 0,
            is_current INTEGER NOT NULL DEFAULT 1,
            started_at TEXT,
            ended_at   TEXT,
            notes      TEXT,
            source     TEXT NOT NULL DEFAULT 'manual',
            created_by TEXT REFERENCES users(id) ON DELETE SET NULL,
            updated_by TEXT REFERENCES users(id) ON DELETE SET NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(contact_id, company_id, role_id, started_at)
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_cc_contact ON contact_companies(contact_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_cc_company ON contact_companies(company_id)")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_cc_primary ON contact_companies(contact_id, is_primary, is_current)"
    )
    print("  Done.")

    # -------------------------------------------------------------------
    # Step 3: Migrate existing contacts.company_id to contact_companies
    # -------------------------------------------------------------------
    print("\nStep 3: Migrating existing company links to contact_companies...")

    # Check if contacts table still has company_id
    cols = {r[1] for r in conn.execute("PRAGMA table_info(contacts)")}
    if "company_id" not in cols:
        print("  contacts.company_id already removed — skipping data migration.")
    else:
        linked = conn.execute(
            "SELECT id, company_id, customer_id FROM contacts WHERE company_id IS NOT NULL"
        ).fetchall()
        print(f"  Found {len(linked)} contact(s) with company_id to migrate.")

        migrated = 0
        for row in linked:
            # Find Employee role for this customer
            cust_id = row["customer_id"] or DEFAULT_CUSTOMER_ID
            role_row = conn.execute(
                "SELECT id FROM contact_company_roles "
                "WHERE customer_id = ? AND name = 'Employee' AND is_system = 1",
                (cust_id,),
            ).fetchone()
            role_id = role_row["id"] if role_row else None

            conn.execute(
                """INSERT OR IGNORE INTO contact_companies
                   (id, contact_id, company_id, role_id, is_primary, is_current,
                    source, created_at, updated_at)
                   VALUES (?, ?, ?, ?, 1, 1, 'migration', ?, ?)""",
                (str(uuid.uuid4()), row["id"], row["company_id"],
                 role_id, now, now),
            )
            migrated += 1
        print(f"  Migrated {migrated} affiliation(s).")

    # -------------------------------------------------------------------
    # Step 4: Rebuild contacts table without company_id and company
    # -------------------------------------------------------------------
    print("\nStep 4: Rebuilding contacts table without company_id/company...")

    if "company_id" not in cols:
        print("  Already rebuilt — skipping.")
    else:
        conn.execute("PRAGMA legacy_alter_table = ON")

        conn.execute("ALTER TABLE contacts RENAME TO _contacts_old")
        conn.execute("""\
            CREATE TABLE contacts (
                id         TEXT PRIMARY KEY,
                customer_id TEXT REFERENCES customers(id) ON DELETE CASCADE,
                name       TEXT,
                source     TEXT,
                status     TEXT DEFAULT 'active',
                created_by TEXT REFERENCES users(id) ON DELETE SET NULL,
                updated_by TEXT REFERENCES users(id) ON DELETE SET NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        conn.execute("""\
            INSERT INTO contacts (id, customer_id, name, source, status,
                                  created_by, updated_by, created_at, updated_at)
            SELECT id, customer_id, name, source, status,
                   created_by, updated_by, created_at, updated_at
            FROM _contacts_old
        """)

        count = conn.execute("SELECT COUNT(*) AS cnt FROM contacts").fetchone()["cnt"]
        old_count = conn.execute("SELECT COUNT(*) AS cnt FROM _contacts_old").fetchone()["cnt"]
        assert count == old_count, f"Row count mismatch: {count} != {old_count}"

        conn.execute("DROP TABLE _contacts_old")
        # Recreate indexes that were on the old table
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_contacts_customer ON contacts(customer_id)"
        )

        conn.execute("PRAGMA legacy_alter_table = OFF")
        print(f"  Rebuilt with {count} row(s).")

    # -------------------------------------------------------------------
    # Step 5: Remove rt-employee from relationship_types
    # -------------------------------------------------------------------
    print("\nStep 5: Removing rt-employee from relationship_types...")
    # Delete any relationships using this type first
    deleted_rels = conn.execute(
        "DELETE FROM relationships WHERE relationship_type_id = 'rt-employee'"
    ).rowcount
    deleted_type = conn.execute(
        "DELETE FROM relationship_types WHERE id = 'rt-employee'"
    ).rowcount
    print(f"  Removed {deleted_type} type(s) and {deleted_rels} relationship(s).")

    # -------------------------------------------------------------------
    # Step 6: Update schema version
    # -------------------------------------------------------------------
    print("\nStep 6: Updating schema version to 10...")
    conn.execute(
        "UPDATE settings SET setting_value = '10', updated_at = ? "
        "WHERE setting_name = 'schema_version'",
        (now,),
    )
    print("  Done.")


def main():
    parser = argparse.ArgumentParser(
        description="Migrate CRMExtender database from v9 to v10 schema "
                    "(multi-company contact affiliations)"
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
