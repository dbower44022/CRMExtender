#!/usr/bin/env python3
"""Migrate the CRMExtender database from v7 to v8.

Adds multi-user & multi-tenant support:
- customers table (tenant)
- Recreated users table with customer_id, password_hash, google_sub
- customer_id column on provider_accounts, contacts, companies,
  conversations, projects, tags, relationship_types
- sessions table (server-side session store)
- user_contacts table (per-user contact visibility)
- user_companies table (per-user company visibility)
- user_provider_accounts table (shared account access)
- conversation_shares table (explicit sharing)
- settings table (unified key-value, system + user)
- Seeds default customer, links existing user + data
- Associated indexes

Usage:
    python3 -m poc.migrate_to_v8 [--db PATH] [--dry-run]
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
DEFAULT_CUSTOMER_NAME = "Default Organization"
DEFAULT_CUSTOMER_SLUG = "default"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def migrate(db_path: Path, *, dry_run: bool = False) -> None:
    """Run the full v7 -> v8 migration."""
    if not db_path.exists():
        print(f"Error: Database not found at {db_path}")
        sys.exit(1)

    # 1. Backup
    backup_path = db_path.with_suffix(
        f".v7-backup-{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
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

    existing_tables = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }

    # -------------------------------------------------------------------
    # Step 1: Create customers table
    # -------------------------------------------------------------------
    print("\nStep 1: Creating customers table...")
    if "customers" in existing_tables:
        print("  Table already exists — skipping.")
    else:
        conn.execute("""\
            CREATE TABLE customers (
                id         TEXT PRIMARY KEY,
                name       TEXT NOT NULL,
                slug       TEXT NOT NULL UNIQUE,
                is_active  INTEGER DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        print("  Created customers table.")

    # -------------------------------------------------------------------
    # Step 2: Bootstrap default customer
    # -------------------------------------------------------------------
    print("\nStep 2: Bootstrapping default customer...")
    existing_customer = conn.execute(
        "SELECT id FROM customers WHERE id = ?", (DEFAULT_CUSTOMER_ID,)
    ).fetchone()
    if existing_customer:
        print("  Default customer already exists — skipping.")
    else:
        conn.execute(
            "INSERT INTO customers (id, name, slug, is_active, created_at, updated_at) "
            "VALUES (?, ?, ?, 1, ?, ?)",
            (DEFAULT_CUSTOMER_ID, DEFAULT_CUSTOMER_NAME, DEFAULT_CUSTOMER_SLUG, now, now),
        )
        print(f"  Created default customer: {DEFAULT_CUSTOMER_NAME}")

    # -------------------------------------------------------------------
    # Step 3: Recreate users table with new schema
    # -------------------------------------------------------------------
    print("\nStep 3: Recreating users table with new schema...")
    user_cols = {
        row[1]
        for row in conn.execute("PRAGMA table_info(users)").fetchall()
    }
    if "customer_id" in user_cols:
        print("  Users table already has customer_id — skipping recreation.")
    else:
        # Save existing users
        old_users = conn.execute("SELECT * FROM users").fetchall()
        print(f"  Found {len(old_users)} existing user(s) to migrate.")

        # Rename old table (disable legacy_alter_table to prevent SQLite
        # from rewriting FK references in other tables to _users_old)
        conn.execute("PRAGMA legacy_alter_table = ON")
        conn.execute("ALTER TABLE users RENAME TO _users_old")
        conn.execute("PRAGMA legacy_alter_table = OFF")

        # Create new users table
        conn.execute("""\
            CREATE TABLE users (
                id            TEXT PRIMARY KEY,
                customer_id   TEXT NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
                email         TEXT NOT NULL,
                name          TEXT,
                role          TEXT DEFAULT 'user' CHECK (role IN ('admin', 'user')),
                is_active     INTEGER DEFAULT 1,
                password_hash TEXT,
                google_sub    TEXT,
                created_at    TEXT NOT NULL,
                updated_at    TEXT NOT NULL,
                UNIQUE(customer_id, email)
            )
        """)

        # Copy existing users with customer_id and upgraded role
        for user in old_users:
            u = dict(user)
            old_role = u.get("role", "member")
            new_role = "admin" if old_role == "admin" else "admin"  # First user becomes admin
            conn.execute(
                "INSERT INTO users "
                "(id, customer_id, email, name, role, is_active, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (u["id"], DEFAULT_CUSTOMER_ID, u["email"], u.get("name"),
                 new_role, u.get("is_active", 1), u["created_at"], u["updated_at"]),
            )

        # Drop old table
        conn.execute("DROP TABLE _users_old")
        print(f"  Recreated users table; migrated {len(old_users)} user(s) as admin.")

    # -------------------------------------------------------------------
    # Step 4: Add customer_id column to existing tables
    # -------------------------------------------------------------------
    tables_needing_customer_id = [
        "provider_accounts",
        "contacts",
        "companies",
        "conversations",
        "projects",
        "tags",
        "relationship_types",
    ]

    print("\nStep 4: Adding customer_id column to existing tables...")
    for table_name in tables_needing_customer_id:
        table_cols = {
            row[1]
            for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()
        }
        if "customer_id" in table_cols:
            print(f"  {table_name}: customer_id already exists — skipping.")
            continue
        conn.execute(f"ALTER TABLE {table_name} ADD COLUMN customer_id TEXT")
        print(f"  {table_name}: added customer_id column.")

    # -------------------------------------------------------------------
    # Step 5: Backfill customer_id on all existing rows
    # -------------------------------------------------------------------
    print("\nStep 5: Backfilling customer_id on existing rows...")
    for table_name in tables_needing_customer_id:
        result = conn.execute(
            f"UPDATE {table_name} SET customer_id = ? WHERE customer_id IS NULL",
            (DEFAULT_CUSTOMER_ID,),
        )
        count = result.rowcount
        if count > 0:
            print(f"  {table_name}: backfilled {count} row(s).")
        else:
            print(f"  {table_name}: no rows to backfill.")

    # -------------------------------------------------------------------
    # Step 6: Create sessions table
    # -------------------------------------------------------------------
    print("\nStep 6: Creating sessions table...")
    if "sessions" in existing_tables:
        print("  Table already exists — skipping.")
    else:
        conn.execute("""\
            CREATE TABLE sessions (
                id          TEXT PRIMARY KEY,
                user_id     TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                customer_id TEXT NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
                created_at  TEXT NOT NULL,
                expires_at  TEXT NOT NULL,
                ip_address  TEXT,
                user_agent  TEXT
            )
        """)
        print("  Created sessions table.")

    # -------------------------------------------------------------------
    # Step 7: Create user_contacts table
    # -------------------------------------------------------------------
    print("\nStep 7: Creating user_contacts table...")
    if "user_contacts" in existing_tables:
        print("  Table already exists — skipping.")
    else:
        conn.execute("""\
            CREATE TABLE user_contacts (
                id         TEXT PRIMARY KEY,
                user_id    TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                contact_id TEXT NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
                visibility TEXT NOT NULL DEFAULT 'public'
                    CHECK (visibility IN ('public', 'private')),
                is_owner   INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(user_id, contact_id)
            )
        """)
        print("  Created user_contacts table.")

    # -------------------------------------------------------------------
    # Step 8: Create user_companies table
    # -------------------------------------------------------------------
    print("\nStep 8: Creating user_companies table...")
    if "user_companies" in existing_tables:
        print("  Table already exists — skipping.")
    else:
        conn.execute("""\
            CREATE TABLE user_companies (
                id         TEXT PRIMARY KEY,
                user_id    TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                company_id TEXT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
                visibility TEXT NOT NULL DEFAULT 'public'
                    CHECK (visibility IN ('public', 'private')),
                is_owner   INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(user_id, company_id)
            )
        """)
        print("  Created user_companies table.")

    # -------------------------------------------------------------------
    # Step 9: Create user_provider_accounts table
    # -------------------------------------------------------------------
    print("\nStep 9: Creating user_provider_accounts table...")
    if "user_provider_accounts" in existing_tables:
        print("  Table already exists — skipping.")
    else:
        conn.execute("""\
            CREATE TABLE user_provider_accounts (
                id         TEXT PRIMARY KEY,
                user_id    TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                account_id TEXT NOT NULL REFERENCES provider_accounts(id) ON DELETE CASCADE,
                role       TEXT NOT NULL DEFAULT 'owner'
                    CHECK (role IN ('owner', 'shared')),
                created_at TEXT NOT NULL,
                UNIQUE(user_id, account_id)
            )
        """)
        print("  Created user_provider_accounts table.")

    # -------------------------------------------------------------------
    # Step 10: Create conversation_shares table
    # -------------------------------------------------------------------
    print("\nStep 10: Creating conversation_shares table...")
    if "conversation_shares" in existing_tables:
        print("  Table already exists — skipping.")
    else:
        conn.execute("""\
            CREATE TABLE conversation_shares (
                id              TEXT PRIMARY KEY,
                conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
                user_id         TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                shared_by       TEXT REFERENCES users(id) ON DELETE SET NULL,
                created_at      TEXT NOT NULL,
                UNIQUE(conversation_id, user_id)
            )
        """)
        print("  Created conversation_shares table.")

    # -------------------------------------------------------------------
    # Step 11: Create settings table
    # -------------------------------------------------------------------
    print("\nStep 11: Creating settings table...")
    if "settings" in existing_tables:
        print("  Table already exists — skipping.")
    else:
        conn.execute("""\
            CREATE TABLE settings (
                id                  TEXT PRIMARY KEY,
                customer_id         TEXT NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
                user_id             TEXT REFERENCES users(id) ON DELETE CASCADE,
                scope               TEXT NOT NULL CHECK (scope IN ('system', 'user')),
                setting_name        TEXT NOT NULL,
                setting_value       TEXT,
                setting_description TEXT,
                setting_default     TEXT,
                created_at          TEXT NOT NULL,
                updated_at          TEXT NOT NULL
            )
        """)
        # Partial unique indexes for NULL-safe uniqueness
        conn.execute("""\
            CREATE UNIQUE INDEX IF NOT EXISTS idx_settings_system_unique
                ON settings(customer_id, setting_name) WHERE scope = 'system'
        """)
        conn.execute("""\
            CREATE UNIQUE INDEX IF NOT EXISTS idx_settings_user_unique
                ON settings(customer_id, user_id, setting_name) WHERE scope = 'user'
        """)
        print("  Created settings table with partial unique indexes.")

    # -------------------------------------------------------------------
    # Step 12: Seed user_provider_accounts
    # -------------------------------------------------------------------
    print("\nStep 12: Seeding user_provider_accounts...")
    user_row = conn.execute(
        "SELECT id FROM users WHERE customer_id = ? AND is_active = 1 ORDER BY created_at LIMIT 1",
        (DEFAULT_CUSTOMER_ID,),
    ).fetchone()

    if user_row:
        user_id = user_row[0]
        accounts = conn.execute("SELECT id FROM provider_accounts").fetchall()
        seeded = 0
        for acct in accounts:
            try:
                conn.execute(
                    "INSERT OR IGNORE INTO user_provider_accounts "
                    "(id, user_id, account_id, role, created_at) "
                    "VALUES (?, ?, ?, 'owner', ?)",
                    (str(uuid.uuid4()), user_id, acct[0], now),
                )
                if conn.execute("SELECT changes()").fetchone()[0] > 0:
                    seeded += 1
            except sqlite3.IntegrityError:
                pass
        print(f"  Linked {seeded} provider account(s) to user as 'owner'.")
    else:
        print("  No active user found — skipping provider account seeding.")

    # -------------------------------------------------------------------
    # Step 13: Seed user_contacts
    # -------------------------------------------------------------------
    print("\nStep 13: Seeding user_contacts...")
    if user_row:
        contacts = conn.execute("SELECT id FROM contacts").fetchall()
        seeded = 0
        for contact in contacts:
            try:
                conn.execute(
                    "INSERT OR IGNORE INTO user_contacts "
                    "(id, user_id, contact_id, visibility, is_owner, created_at, updated_at) "
                    "VALUES (?, ?, ?, 'public', 1, ?, ?)",
                    (str(uuid.uuid4()), user_id, contact[0], now, now),
                )
                if conn.execute("SELECT changes()").fetchone()[0] > 0:
                    seeded += 1
            except sqlite3.IntegrityError:
                pass
        print(f"  Linked {seeded} contact(s) to user as public/owner.")
    else:
        print("  No active user found — skipping contact seeding.")

    # -------------------------------------------------------------------
    # Step 14: Seed user_companies
    # -------------------------------------------------------------------
    print("\nStep 14: Seeding user_companies...")
    if user_row:
        companies = conn.execute("SELECT id FROM companies").fetchall()
        seeded = 0
        for company in companies:
            try:
                conn.execute(
                    "INSERT OR IGNORE INTO user_companies "
                    "(id, user_id, company_id, visibility, is_owner, created_at, updated_at) "
                    "VALUES (?, ?, ?, 'public', 1, ?, ?)",
                    (str(uuid.uuid4()), user_id, company[0], now, now),
                )
                if conn.execute("SELECT changes()").fetchone()[0] > 0:
                    seeded += 1
            except sqlite3.IntegrityError:
                pass
        print(f"  Linked {seeded} company(ies) to user as public/owner.")
    else:
        print("  No active user found — skipping company seeding.")

    # -------------------------------------------------------------------
    # Step 15: Seed default settings
    # -------------------------------------------------------------------
    print("\nStep 15: Seeding default settings...")
    _seed_default_settings(conn, DEFAULT_CUSTOMER_ID, user_row[0] if user_row else None, now)

    # -------------------------------------------------------------------
    # Step 16: Create indexes
    # -------------------------------------------------------------------
    print("\nStep 16: Creating indexes...")
    _create_indexes(conn)
    print("  Indexes created.")

    # -------------------------------------------------------------------
    # Step 17: Validation
    # -------------------------------------------------------------------
    print("\nStep 17: Validation...")
    conn.execute("PRAGMA foreign_keys=ON")
    _validate(conn)


def _seed_default_settings(
    conn: sqlite3.Connection,
    customer_id: str,
    user_id: str | None,
    now: str,
) -> None:
    """Seed system and user default settings."""
    system_settings = [
        ("default_timezone", "UTC", "Default timezone for new users"),
        ("company_name", DEFAULT_CUSTOMER_NAME, "Organization display name"),
        ("sync_enabled", "true", "Enable/disable automatic sync"),
    ]

    for name, default, description in system_settings:
        try:
            conn.execute(
                "INSERT OR IGNORE INTO settings "
                "(id, customer_id, user_id, scope, setting_name, setting_value, "
                "setting_description, setting_default, created_at, updated_at) "
                "VALUES (?, ?, NULL, 'system', ?, ?, ?, ?, ?, ?)",
                (str(uuid.uuid4()), customer_id, name, default,
                 description, default, now, now),
            )
        except sqlite3.IntegrityError:
            pass
    print(f"  Seeded {len(system_settings)} system setting(s).")

    if user_id:
        user_settings = [
            ("timezone", None, "Preferred timezone (e.g. America/New_York)"),
            ("start_of_week", "monday", "First day of week (monday/sunday/saturday)"),
            ("date_format", "ISO", "Date display: US (MM/DD/YYYY), ISO (YYYY-MM-DD), EU (DD/MM/YYYY)"),
            ("profile_photo", None, "Profile photo path or URL"),
            ("contact_id", None, "Link to user's own contact record"),
        ]

        for name, default, description in user_settings:
            try:
                conn.execute(
                    "INSERT OR IGNORE INTO settings "
                    "(id, customer_id, user_id, scope, setting_name, setting_value, "
                    "setting_description, setting_default, created_at, updated_at) "
                    "VALUES (?, ?, ?, 'user', ?, ?, ?, ?, ?, ?)",
                    (str(uuid.uuid4()), customer_id, user_id, name, default,
                     description, default, now, now),
                )
            except sqlite3.IntegrityError:
                pass
        print(f"  Seeded {len(user_settings)} user setting(s).")


def _create_indexes(conn: sqlite3.Connection) -> None:
    """Create all new indexes for v8 tables."""
    index_sql = """\
        CREATE INDEX IF NOT EXISTS idx_sessions_user
            ON sessions(user_id);
        CREATE INDEX IF NOT EXISTS idx_sessions_customer
            ON sessions(customer_id);
        CREATE INDEX IF NOT EXISTS idx_sessions_expires
            ON sessions(expires_at);

        CREATE INDEX IF NOT EXISTS idx_user_contacts_user
            ON user_contacts(user_id);
        CREATE INDEX IF NOT EXISTS idx_user_contacts_contact
            ON user_contacts(contact_id);
        CREATE INDEX IF NOT EXISTS idx_user_contacts_visibility
            ON user_contacts(visibility);

        CREATE INDEX IF NOT EXISTS idx_user_companies_user
            ON user_companies(user_id);
        CREATE INDEX IF NOT EXISTS idx_user_companies_company
            ON user_companies(company_id);
        CREATE INDEX IF NOT EXISTS idx_user_companies_visibility
            ON user_companies(visibility);

        CREATE INDEX IF NOT EXISTS idx_upa_user
            ON user_provider_accounts(user_id);
        CREATE INDEX IF NOT EXISTS idx_upa_account
            ON user_provider_accounts(account_id);

        CREATE INDEX IF NOT EXISTS idx_cs_conversation
            ON conversation_shares(conversation_id);
        CREATE INDEX IF NOT EXISTS idx_cs_user
            ON conversation_shares(user_id);

        CREATE INDEX IF NOT EXISTS idx_settings_customer
            ON settings(customer_id);
        CREATE INDEX IF NOT EXISTS idx_settings_user
            ON settings(user_id);
        CREATE INDEX IF NOT EXISTS idx_settings_name
            ON settings(setting_name);

        CREATE INDEX IF NOT EXISTS idx_users_customer
            ON users(customer_id);

        CREATE INDEX IF NOT EXISTS idx_provider_accounts_customer
            ON provider_accounts(customer_id);
        CREATE INDEX IF NOT EXISTS idx_contacts_customer
            ON contacts(customer_id);
        CREATE INDEX IF NOT EXISTS idx_companies_customer
            ON companies(customer_id);
        CREATE INDEX IF NOT EXISTS idx_conversations_customer
            ON conversations(customer_id);
        CREATE INDEX IF NOT EXISTS idx_projects_customer
            ON projects(customer_id);
        CREATE INDEX IF NOT EXISTS idx_tags_customer
            ON tags(customer_id);
    """
    conn.executescript(index_sql)


def _validate(conn: sqlite3.Connection) -> None:
    """Validate migration results."""
    post_tables = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }

    errors = []

    # Check new tables exist
    required_tables = [
        "customers", "sessions", "user_contacts", "user_companies",
        "user_provider_accounts", "conversation_shares", "settings",
    ]
    for table_name in required_tables:
        if table_name not in post_tables:
            errors.append(f"Table {table_name} was not created")

    # Check users table has new columns
    user_cols = {
        row[1]
        for row in conn.execute("PRAGMA table_info(users)").fetchall()
    }
    expected_user_cols = {"customer_id", "password_hash", "google_sub"}
    missing = expected_user_cols - user_cols
    if missing:
        errors.append(f"Missing columns on users: {missing}")

    # Check customer_id on existing tables
    for table_name in [
        "provider_accounts", "contacts", "companies",
        "conversations", "projects", "tags", "relationship_types",
    ]:
        table_cols = {
            row[1]
            for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()
        }
        if "customer_id" not in table_cols:
            errors.append(f"Missing customer_id on {table_name}")

    # Check default customer exists
    cust = conn.execute(
        "SELECT id FROM customers WHERE id = ?", (DEFAULT_CUSTOMER_ID,)
    ).fetchone()
    if not cust:
        errors.append("Default customer was not created")

    # Check row count integrity for customer_id backfill
    for table_name in [
        "provider_accounts", "contacts", "companies",
        "conversations", "projects", "tags",
    ]:
        null_count = conn.execute(
            f"SELECT COUNT(*) FROM {table_name} WHERE customer_id IS NULL"
        ).fetchone()[0]
        if null_count > 0:
            errors.append(f"{table_name}: {null_count} row(s) still have NULL customer_id")

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
        description="Migrate CRMExtender database from v7 to v8 schema (multi-user)"
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
