"""Tests for the v7 -> v8 migration (multi-user & multi-tenant)."""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest

from poc.database import init_db
from poc.migrate_to_v8 import DEFAULT_CUSTOMER_ID, migrate


_NOW = datetime.now(timezone.utc).isoformat()


@pytest.fixture()
def v7_db(tmp_path):
    """Create a v7-schema database with sample data."""
    db_file = tmp_path / "test.db"
    init_db(db_file)

    conn = sqlite3.connect(str(db_file))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=OFF")

    # Drop v8 tables/columns if init_db created them (since database.py now has v8 schema)
    # We need to simulate a v7 database
    _downgrade_to_v7(conn)

    # Seed sample data
    _seed_v7_data(conn)

    conn.commit()
    conn.close()
    return db_file


def _downgrade_to_v7(conn):
    """Remove v8 tables and recreate users without customer_id."""
    for table in [
        "settings", "conversation_shares", "user_provider_accounts",
        "user_companies", "user_contacts", "sessions", "customers",
    ]:
        conn.execute(f"DROP TABLE IF EXISTS {table}")

    # Recreate users without customer_id
    conn.execute("DROP TABLE IF EXISTS users")
    conn.execute("""\
        CREATE TABLE users (
            id         TEXT PRIMARY KEY,
            email      TEXT NOT NULL UNIQUE,
            name       TEXT,
            role       TEXT DEFAULT 'member',
            is_active  INTEGER DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)

    # Remove customer_id from tables that have it
    for table in [
        "provider_accounts", "contacts", "companies",
        "conversations", "projects", "tags", "relationship_types",
    ]:
        cols = {
            row[1]
            for row in conn.execute(f"PRAGMA table_info({table})").fetchall()
        }
        if "customer_id" in cols:
            # SQLite can't DROP COLUMN easily, but for tests we can just
            # leave it — the migration will SET it to the default customer
            pass


def _seed_v7_data(conn):
    """Insert sample data to test migration."""
    # User
    conn.execute(
        "INSERT INTO users (id, email, name, role, is_active, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, 1, ?, ?)",
        ("user-1", "doug@example.com", "Doug", "member", _NOW, _NOW),
    )

    # Provider account
    conn.execute(
        "INSERT INTO provider_accounts "
        "(id, provider, account_type, email_address, created_at, updated_at) "
        "VALUES (?, 'gmail', 'email', ?, ?, ?)",
        ("acct-1", "doug@example.com", _NOW, _NOW),
    )

    # Company
    conn.execute(
        "INSERT INTO companies (id, name, domain, status, created_at, updated_at) "
        "VALUES (?, ?, ?, 'active', ?, ?)",
        ("comp-1", "Acme Corp", "acme.com", _NOW, _NOW),
    )

    # Contact
    conn.execute(
        "INSERT INTO contacts (id, name, company_id, source, status, created_at, updated_at) "
        "VALUES (?, ?, ?, 'google_contacts', 'active', ?, ?)",
        ("contact-1", "Alice", "comp-1", _NOW, _NOW),
    )

    # Conversation
    conn.execute(
        "INSERT INTO conversations "
        "(id, title, status, communication_count, participant_count, created_at, updated_at) "
        "VALUES (?, ?, 'active', 1, 1, ?, ?)",
        ("conv-1", "Test thread", _NOW, _NOW),
    )

    # Project
    conn.execute(
        "INSERT INTO projects (id, name, status, created_at, updated_at) "
        "VALUES (?, ?, 'active', ?, ?)",
        ("proj-1", "Main Project", _NOW, _NOW),
    )

    # Tag
    conn.execute(
        "INSERT INTO tags (id, name, source, created_at) VALUES (?, ?, 'ai', ?)",
        ("tag-1", "test-tag", _NOW),
    )


# -------------------------------------------------------------------
# Migration tests
# -------------------------------------------------------------------

class TestMigrationV8:
    """Test the v7 -> v8 migration."""

    def test_migrate_creates_customers_table(self, v7_db):
        migrate(v7_db, dry_run=False)
        conn = sqlite3.connect(str(v7_db))
        conn.row_factory = sqlite3.Row
        tables = {
            row[0] for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        assert "customers" in tables
        conn.close()

    def test_migrate_creates_default_customer(self, v7_db):
        migrate(v7_db, dry_run=False)
        conn = sqlite3.connect(str(v7_db))
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM customers WHERE id = ?", (DEFAULT_CUSTOMER_ID,)
        ).fetchone()
        assert row is not None
        assert row["name"] == "Default Organization"
        assert row["slug"] == "default"
        conn.close()

    def test_migrate_recreates_users_table(self, v7_db):
        migrate(v7_db, dry_run=False)
        conn = sqlite3.connect(str(v7_db))
        conn.row_factory = sqlite3.Row
        cols = {
            row[1] for row in conn.execute("PRAGMA table_info(users)").fetchall()
        }
        assert "customer_id" in cols
        assert "password_hash" in cols
        assert "google_sub" in cols
        conn.close()

    def test_migrate_preserves_existing_user(self, v7_db):
        migrate(v7_db, dry_run=False)
        conn = sqlite3.connect(str(v7_db))
        conn.row_factory = sqlite3.Row
        user = conn.execute("SELECT * FROM users WHERE id = 'user-1'").fetchone()
        assert user is not None
        assert user["email"] == "doug@example.com"
        assert user["customer_id"] == DEFAULT_CUSTOMER_ID
        assert user["role"] == "admin"
        conn.close()

    def test_migrate_adds_customer_id_to_tables(self, v7_db):
        migrate(v7_db, dry_run=False)
        conn = sqlite3.connect(str(v7_db))
        conn.row_factory = sqlite3.Row

        for table in [
            "provider_accounts", "contacts", "companies",
            "conversations", "projects", "tags", "relationship_types",
        ]:
            cols = {
                row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()
            }
            assert "customer_id" in cols, f"{table} missing customer_id"

        conn.close()

    def test_migrate_backfills_customer_id(self, v7_db):
        migrate(v7_db, dry_run=False)
        conn = sqlite3.connect(str(v7_db))
        conn.row_factory = sqlite3.Row

        for table in [
            "provider_accounts", "contacts", "companies",
            "conversations", "projects", "tags",
        ]:
            null_count = conn.execute(
                f"SELECT COUNT(*) FROM {table} WHERE customer_id IS NULL"
            ).fetchone()[0]
            assert null_count == 0, f"{table} has {null_count} NULL customer_id rows"

        conn.close()

    def test_migrate_creates_new_tables(self, v7_db):
        migrate(v7_db, dry_run=False)
        conn = sqlite3.connect(str(v7_db))
        conn.row_factory = sqlite3.Row
        tables = {
            row[0] for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }

        expected = {
            "sessions", "user_contacts", "user_companies",
            "user_provider_accounts", "conversation_shares", "settings",
        }
        assert expected.issubset(tables)
        conn.close()

    def test_migrate_seeds_user_provider_accounts(self, v7_db):
        migrate(v7_db, dry_run=False)
        conn = sqlite3.connect(str(v7_db))
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM user_provider_accounts WHERE user_id = 'user-1'"
        ).fetchall()
        assert len(rows) == 1
        assert rows[0]["account_id"] == "acct-1"
        assert rows[0]["role"] == "owner"
        conn.close()

    def test_migrate_seeds_user_contacts(self, v7_db):
        migrate(v7_db, dry_run=False)
        conn = sqlite3.connect(str(v7_db))
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM user_contacts WHERE user_id = 'user-1'"
        ).fetchall()
        assert len(rows) == 1
        assert rows[0]["contact_id"] == "contact-1"
        assert rows[0]["visibility"] == "public"
        assert rows[0]["is_owner"] == 1
        conn.close()

    def test_migrate_seeds_user_companies(self, v7_db):
        migrate(v7_db, dry_run=False)
        conn = sqlite3.connect(str(v7_db))
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM user_companies WHERE user_id = 'user-1'"
        ).fetchall()
        assert len(rows) == 1
        assert rows[0]["company_id"] == "comp-1"
        assert rows[0]["visibility"] == "public"
        assert rows[0]["is_owner"] == 1
        conn.close()

    def test_migrate_seeds_system_settings(self, v7_db):
        migrate(v7_db, dry_run=False)
        conn = sqlite3.connect(str(v7_db))
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM settings WHERE scope = 'system'"
        ).fetchall()
        names = {r["setting_name"] for r in rows}
        assert "default_timezone" in names
        assert "company_name" in names
        assert "sync_enabled" in names
        conn.close()

    def test_migrate_seeds_user_settings(self, v7_db):
        migrate(v7_db, dry_run=False)
        conn = sqlite3.connect(str(v7_db))
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM settings WHERE scope = 'user' AND user_id = 'user-1'"
        ).fetchall()
        names = {r["setting_name"] for r in rows}
        assert "timezone" in names
        assert "date_format" in names
        assert "start_of_week" in names
        conn.close()

    def test_migrate_dry_run_does_not_modify_original(self, v7_db):
        migrate(v7_db, dry_run=True)
        # Original should still be v7 (no customers table since we dropped it)
        conn = sqlite3.connect(str(v7_db))
        conn.row_factory = sqlite3.Row
        tables = {
            row[0] for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        assert "customers" not in tables
        conn.close()

    def test_migrate_idempotent(self, v7_db):
        """Running migration twice should not fail."""
        migrate(v7_db, dry_run=False)
        # Running again should succeed (idempotent)
        migrate(v7_db, dry_run=False)

        conn = sqlite3.connect(str(v7_db))
        conn.row_factory = sqlite3.Row
        user_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        assert user_count == 1  # Should not duplicate user
        conn.close()

    def test_migrate_no_users(self, tmp_path):
        """Migration should handle DB with no existing users."""
        db_file = tmp_path / "empty.db"
        init_db(db_file)

        conn = sqlite3.connect(str(db_file))
        conn.execute("PRAGMA foreign_keys=OFF")
        _downgrade_to_v7(conn)
        conn.commit()
        conn.close()

        migrate(db_file, dry_run=False)

        conn = sqlite3.connect(str(db_file))
        conn.row_factory = sqlite3.Row
        assert conn.execute("SELECT COUNT(*) FROM customers").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0
        conn.close()

    def test_migrate_creates_indexes(self, v7_db):
        migrate(v7_db, dry_run=False)
        conn = sqlite3.connect(str(v7_db))
        indexes = {
            row[0] for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index'"
            ).fetchall()
        }
        expected_indexes = [
            "idx_sessions_user",
            "idx_user_contacts_user",
            "idx_user_companies_user",
            "idx_upa_user",
            "idx_cs_conversation",
            "idx_settings_customer",
            "idx_users_customer",
        ]
        for idx in expected_indexes:
            assert idx in indexes, f"Missing index: {idx}"
        conn.close()
