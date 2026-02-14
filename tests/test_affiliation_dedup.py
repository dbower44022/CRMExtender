"""Tests for contact_companies affiliation deduplication fix.

Covers:
- NULL-safe unique index prevents duplicate affiliations via INSERT OR IGNORE
- Contacts list query returns one row per contact despite multiple affiliations
- Migration v11 dedup logic
"""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from poc.database import get_connection, init_db


_NOW = datetime.now(timezone.utc).isoformat()

CUST_ID = "cust-test"
USER_ID = "user-admin"

_SYSTEM_ROLES = [
    ("ccr-employee", "Employee", 0),
    ("ccr-contractor", "Contractor", 1),
]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def tmp_db(tmp_path, monkeypatch):
    db_file = tmp_path / "test.db"
    monkeypatch.setattr("poc.config.DB_PATH", db_file)
    monkeypatch.setattr("poc.config.CRM_AUTH_ENABLED", False)
    init_db(db_file)

    with get_connection() as conn:
        conn.execute(
            "INSERT INTO customers (id, name, slug, is_active, created_at, updated_at) "
            "VALUES (?, 'Test Org', 'test', 1, ?, ?)",
            (CUST_ID, _NOW, _NOW),
        )
        conn.execute(
            "INSERT INTO users "
            "(id, customer_id, email, name, role, is_active, created_at, updated_at) "
            "VALUES (?, ?, 'admin@test.com', 'Admin User', 'admin', 1, ?, ?)",
            (USER_ID, CUST_ID, _NOW, _NOW),
        )
        for role_id, role_name, sort_order in _SYSTEM_ROLES:
            full_id = f"{role_id}-{CUST_ID}"
            conn.execute(
                "INSERT OR IGNORE INTO contact_company_roles "
                "(id, customer_id, name, sort_order, is_system, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, 1, ?, ?)",
                (full_id, CUST_ID, role_name, sort_order, _NOW, _NOW),
            )

    return db_file


@pytest.fixture()
def client(tmp_db, monkeypatch):
    monkeypatch.setattr(
        "poc.hierarchy.get_current_user",
        lambda: {"id": USER_ID, "email": "admin@test.com", "name": "Admin User",
                 "role": "admin", "customer_id": CUST_ID},
    )
    from poc.web.app import create_app
    app = create_app()
    return TestClient(app, raise_server_exceptions=False)


def _create_contact(name="Alice", email=None):
    cid = str(uuid.uuid4())
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO contacts "
            "(id, customer_id, name, source, status, created_at, updated_at) "
            "VALUES (?, ?, ?, 'test', 'active', ?, ?)",
            (cid, CUST_ID, name, _NOW, _NOW),
        )
        if email:
            conn.execute(
                "INSERT INTO contact_identifiers "
                "(id, contact_id, type, value, is_primary, created_at, updated_at) "
                "VALUES (?, ?, 'email', ?, 1, ?, ?)",
                (str(uuid.uuid4()), cid, email, _NOW, _NOW),
            )
        conn.execute(
            "INSERT INTO user_contacts "
            "(id, user_id, contact_id, visibility, is_owner, created_at, updated_at) "
            "VALUES (?, ?, ?, 'public', 1, ?, ?)",
            (str(uuid.uuid4()), USER_ID, cid, _NOW, _NOW),
        )
    return cid


def _create_company(name="Acme Corp"):
    co_id = str(uuid.uuid4())
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO companies "
            "(id, customer_id, name, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (co_id, CUST_ID, name, _NOW, _NOW),
        )
        conn.execute(
            "INSERT INTO user_companies "
            "(id, user_id, company_id, visibility, is_owner, created_at, updated_at) "
            "VALUES (?, ?, ?, 'public', 1, ?, ?)",
            (str(uuid.uuid4()), USER_ID, co_id, _NOW, _NOW),
        )
    return co_id


# ---------------------------------------------------------------------------
# Tests: NULL-safe unique index
# ---------------------------------------------------------------------------

class TestNullSafeUniqueIndex:
    """INSERT OR IGNORE should prevent duplicates even when role_id/started_at are NULL."""

    def test_duplicate_null_role_ignored(self, tmp_db):
        cid = _create_contact("Alice", "alice@acme.com")
        co_id = _create_company("Acme")

        with get_connection() as conn:
            # First insert succeeds
            conn.execute(
                "INSERT OR IGNORE INTO contact_companies "
                "(id, contact_id, company_id, is_primary, is_current, source, created_at, updated_at) "
                "VALUES (?, ?, ?, 1, 1, 'sync', ?, ?)",
                (str(uuid.uuid4()), cid, co_id, _NOW, _NOW),
            )
            # Second insert with same NULL role_id and NULL started_at should be ignored
            conn.execute(
                "INSERT OR IGNORE INTO contact_companies "
                "(id, contact_id, company_id, is_primary, is_current, source, created_at, updated_at) "
                "VALUES (?, ?, ?, 1, 1, 'sync', ?, ?)",
                (str(uuid.uuid4()), cid, co_id, _NOW, _NOW),
            )

            count = conn.execute(
                "SELECT COUNT(*) AS cnt FROM contact_companies "
                "WHERE contact_id = ? AND company_id = ?",
                (cid, co_id),
            ).fetchone()["cnt"]

        assert count == 1

    def test_duplicate_null_started_at_ignored(self, tmp_db):
        cid = _create_contact("Bob")
        co_id = _create_company("Beta Corp")
        role_id = f"ccr-employee-{CUST_ID}"

        with get_connection() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO contact_companies "
                "(id, contact_id, company_id, role_id, is_primary, is_current, source, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, 1, 1, 'sync', ?, ?)",
                (str(uuid.uuid4()), cid, co_id, role_id, _NOW, _NOW),
            )
            conn.execute(
                "INSERT OR IGNORE INTO contact_companies "
                "(id, contact_id, company_id, role_id, is_primary, is_current, source, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, 1, 1, 'sync', ?, ?)",
                (str(uuid.uuid4()), cid, co_id, role_id, _NOW, _NOW),
            )

            count = conn.execute(
                "SELECT COUNT(*) AS cnt FROM contact_companies "
                "WHERE contact_id = ? AND company_id = ?",
                (cid, co_id),
            ).fetchone()["cnt"]

        assert count == 1

    def test_different_roles_allowed(self, tmp_db):
        cid = _create_contact("Carol")
        co_id = _create_company("Gamma Inc")

        with get_connection() as conn:
            # NULL role
            conn.execute(
                "INSERT OR IGNORE INTO contact_companies "
                "(id, contact_id, company_id, is_primary, is_current, source, created_at, updated_at) "
                "VALUES (?, ?, ?, 1, 1, 'sync', ?, ?)",
                (str(uuid.uuid4()), cid, co_id, _NOW, _NOW),
            )
            # Explicit role
            conn.execute(
                "INSERT OR IGNORE INTO contact_companies "
                "(id, contact_id, company_id, role_id, is_primary, is_current, source, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, 0, 1, 'manual', ?, ?)",
                (str(uuid.uuid4()), cid, co_id, f"ccr-employee-{CUST_ID}", _NOW, _NOW),
            )

            count = conn.execute(
                "SELECT COUNT(*) AS cnt FROM contact_companies "
                "WHERE contact_id = ? AND company_id = ?",
                (cid, co_id),
            ).fetchone()["cnt"]

        assert count == 2

    def test_different_started_at_allowed(self, tmp_db):
        cid = _create_contact("Dave")
        co_id = _create_company("Delta LLC")

        with get_connection() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO contact_companies "
                "(id, contact_id, company_id, is_primary, is_current, source, created_at, updated_at) "
                "VALUES (?, ?, ?, 1, 1, 'sync', ?, ?)",
                (str(uuid.uuid4()), cid, co_id, _NOW, _NOW),
            )
            conn.execute(
                "INSERT OR IGNORE INTO contact_companies "
                "(id, contact_id, company_id, started_at, is_primary, is_current, source, created_at, updated_at) "
                "VALUES (?, ?, ?, '2025-01-01', 0, 1, 'manual', ?, ?)",
                (str(uuid.uuid4()), cid, co_id, _NOW, _NOW),
            )

            count = conn.execute(
                "SELECT COUNT(*) AS cnt FROM contact_companies "
                "WHERE contact_id = ? AND company_id = ?",
                (cid, co_id),
            ).fetchone()["cnt"]

        assert count == 2

    def test_hard_insert_raises_integrity_error(self, tmp_db):
        """Plain INSERT (not OR IGNORE) should raise on duplicate."""
        cid = _create_contact("Eve")
        co_id = _create_company("Echo")

        with get_connection() as conn:
            conn.execute(
                "INSERT INTO contact_companies "
                "(id, contact_id, company_id, is_primary, is_current, source, created_at, updated_at) "
                "VALUES (?, ?, ?, 1, 1, 'sync', ?, ?)",
                (str(uuid.uuid4()), cid, co_id, _NOW, _NOW),
            )

            with pytest.raises(sqlite3.IntegrityError):
                conn.execute(
                    "INSERT INTO contact_companies "
                    "(id, contact_id, company_id, is_primary, is_current, source, created_at, updated_at) "
                    "VALUES (?, ?, ?, 1, 1, 'sync', ?, ?)",
                    (str(uuid.uuid4()), cid, co_id, _NOW, _NOW),
                )


# ---------------------------------------------------------------------------
# Tests: Contacts list query returns unique rows
# ---------------------------------------------------------------------------

class TestContactsListDedup:
    """Contacts list should show each contact once even with multiple affiliations."""

    def test_contact_with_multiple_affiliations_appears_once(self, client, tmp_db):
        cid = _create_contact("Multi-Aff Alice", "alice@test.com")
        co1 = _create_company("Company A")
        co2 = _create_company("Company B")

        with get_connection() as conn:
            for co_id in (co1, co2):
                conn.execute(
                    "INSERT INTO contact_companies "
                    "(id, contact_id, company_id, is_primary, is_current, source, created_at, updated_at) "
                    "VALUES (?, ?, ?, 1, 1, 'test', ?, ?)",
                    (str(uuid.uuid4()), cid, co_id, _NOW, _NOW),
                )

        resp = client.get("/contacts?q=Multi-Aff")
        assert resp.status_code == 200
        # The contact name should appear exactly once in the table
        assert resp.text.count("Multi-Aff Alice") == 1

    def test_search_returns_unique_rows(self, client, tmp_db):
        cid = _create_contact("Search Dedup Bob", "bob@test.com")
        co1 = _create_company("Corp X")
        co2 = _create_company("Corp Y")
        co3 = _create_company("Corp Z")

        with get_connection() as conn:
            for co_id in (co1, co2, co3):
                conn.execute(
                    "INSERT INTO contact_companies "
                    "(id, contact_id, company_id, is_primary, is_current, source, created_at, updated_at) "
                    "VALUES (?, ?, ?, 1, 1, 'test', ?, ?)",
                    (str(uuid.uuid4()), cid, co_id, _NOW, _NOW),
                )

        resp = client.get("/contacts/search?q=Search+Dedup")
        assert resp.status_code == 200
        assert resp.text.count("Search Dedup Bob") == 1

    def test_total_count_correct_with_multiple_affiliations(self, client, tmp_db):
        cid = _create_contact("Count Test Carol", "carol@test.com")
        co1 = _create_company("CountCo 1")
        co2 = _create_company("CountCo 2")

        with get_connection() as conn:
            for co_id in (co1, co2):
                conn.execute(
                    "INSERT INTO contact_companies "
                    "(id, contact_id, company_id, is_primary, is_current, source, created_at, updated_at) "
                    "VALUES (?, ?, ?, 1, 1, 'test', ?, ?)",
                    (str(uuid.uuid4()), cid, co_id, _NOW, _NOW),
                )

        resp = client.get("/contacts?q=Count+Test")
        assert resp.status_code == 200
        # Total should be 1, not 2
        assert "(1)" in resp.text


# ---------------------------------------------------------------------------
# Tests: Migration v11 dedup logic
# ---------------------------------------------------------------------------

class TestMigrationV11:
    """Test the v10 -> v11 migration dedup logic."""

    def test_migration_removes_duplicates(self, tmp_path, monkeypatch):
        """Create a DB with duplicate affiliations, run migration, verify dedup."""
        db_file = tmp_path / "migrate_test.db"
        monkeypatch.setattr("poc.config.DB_PATH", db_file)
        init_db(db_file)

        conn = sqlite3.connect(str(db_file))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=OFF")

        # Seed minimal data
        conn.execute(
            "INSERT INTO customers (id, name, slug, is_active, created_at, updated_at) "
            "VALUES ('cust-1', 'Test', 'test', 1, ?, ?)", (_NOW, _NOW),
        )
        conn.execute(
            "INSERT INTO contacts (id, customer_id, name, source, status, created_at, updated_at) "
            "VALUES ('ct-1', 'cust-1', 'Alice', 'test', 'active', ?, ?)", (_NOW, _NOW),
        )
        conn.execute(
            "INSERT INTO companies (id, customer_id, name, created_at, updated_at) "
            "VALUES ('co-1', 'cust-1', 'Acme', ?, ?)", (_NOW, _NOW),
        )

        # Drop the COALESCE index so we can insert duplicates (init_db creates it)
        conn.execute("DROP INDEX IF EXISTS idx_cc_dedup")

        # Insert 4 duplicate affiliations (same contact+company, NULL role+started_at)
        for i in range(4):
            conn.execute(
                "INSERT INTO contact_companies "
                "(id, contact_id, company_id, is_primary, is_current, source, created_at, updated_at) "
                "VALUES (?, 'ct-1', 'co-1', 1, 1, 'sync', ?, ?)",
                (f"aff-{i}", f"2026-01-0{i+1}T00:00:00", _NOW),
            )

        count_before = conn.execute(
            "SELECT COUNT(*) AS cnt FROM contact_companies WHERE contact_id = 'ct-1'"
        ).fetchone()["cnt"]
        assert count_before == 4

        conn.execute("PRAGMA user_version = 10")
        conn.commit()
        conn.close()

        # Run migration
        from poc.migrate_to_v11 import migrate
        migrate(db_file, dry_run=False)

        # Verify
        conn = sqlite3.connect(str(db_file))
        conn.row_factory = sqlite3.Row

        count_after = conn.execute(
            "SELECT COUNT(*) AS cnt FROM contact_companies WHERE contact_id = 'ct-1'"
        ).fetchone()["cnt"]
        assert count_after == 1

        # Verify the earliest row was kept
        kept = conn.execute(
            "SELECT created_at FROM contact_companies WHERE contact_id = 'ct-1'"
        ).fetchone()
        assert kept["created_at"] == "2026-01-01T00:00:00"

        # Verify schema version bumped
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        assert version == 11

        # Verify the unique index exists
        idx = conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'index' AND name = 'idx_cc_dedup'"
        ).fetchone()
        assert idx is not None

        conn.close()

    def test_migration_removes_null_role_when_explicit_exists(self, tmp_path, monkeypatch):
        """NULL-role affiliation is removed when an explicit-role one exists for same company."""
        db_file = tmp_path / "migrate_roles.db"
        monkeypatch.setattr("poc.config.DB_PATH", db_file)
        init_db(db_file)

        conn = sqlite3.connect(str(db_file))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=OFF")

        conn.execute(
            "INSERT INTO customers (id, name, slug, is_active, created_at, updated_at) "
            "VALUES ('cust-1', 'Test', 'test', 1, ?, ?)", (_NOW, _NOW),
        )
        conn.execute(
            "INSERT INTO contacts (id, customer_id, name, source, status, created_at, updated_at) "
            "VALUES ('ct-1', 'cust-1', 'Bob', 'test', 'active', ?, ?)", (_NOW, _NOW),
        )
        conn.execute(
            "INSERT INTO companies (id, customer_id, name, created_at, updated_at) "
            "VALUES ('co-1', 'cust-1', 'Beta', ?, ?)", (_NOW, _NOW),
        )
        conn.execute(
            "INSERT INTO contact_company_roles (id, name, sort_order, is_system, created_at, updated_at) "
            "VALUES ('role-emp', 'Employee', 0, 1, ?, ?)", (_NOW, _NOW),
        )

        # Drop the index so we can insert freely
        conn.execute("DROP INDEX IF EXISTS idx_cc_dedup")

        # NULL role (from sync)
        conn.execute(
            "INSERT INTO contact_companies "
            "(id, contact_id, company_id, is_primary, is_current, source, created_at, updated_at) "
            "VALUES ('aff-1', 'ct-1', 'co-1', 1, 1, 'sync', ?, ?)", (_NOW, _NOW),
        )
        # Explicit role (from migration)
        conn.execute(
            "INSERT INTO contact_companies "
            "(id, contact_id, company_id, role_id, is_primary, is_current, source, created_at, updated_at) "
            "VALUES ('aff-2', 'ct-1', 'co-1', 'role-emp', 0, 1, 'manual', ?, ?)", (_NOW, _NOW),
        )

        conn.execute("PRAGMA user_version = 10")
        conn.commit()
        conn.close()

        from poc.migrate_to_v11 import migrate
        migrate(db_file, dry_run=False)

        conn = sqlite3.connect(str(db_file))
        conn.row_factory = sqlite3.Row
        count = conn.execute(
            "SELECT COUNT(*) AS cnt FROM contact_companies WHERE contact_id = 'ct-1'"
        ).fetchone()["cnt"]
        # NULL-role removed, only the explicit-role affiliation remains
        assert count == 1

        # The surviving row should be the one with the explicit role
        kept = conn.execute(
            "SELECT role_id FROM contact_companies WHERE contact_id = 'ct-1'"
        ).fetchone()
        assert kept["role_id"] == "role-emp"
        conn.close()

    def test_migration_keeps_distinct_explicit_roles(self, tmp_path, monkeypatch):
        """Two different explicit roles for the same company should both survive."""
        db_file = tmp_path / "migrate_two_roles.db"
        monkeypatch.setattr("poc.config.DB_PATH", db_file)
        init_db(db_file)

        conn = sqlite3.connect(str(db_file))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=OFF")

        conn.execute(
            "INSERT INTO customers (id, name, slug, is_active, created_at, updated_at) "
            "VALUES ('cust-1', 'Test', 'test', 1, ?, ?)", (_NOW, _NOW),
        )
        conn.execute(
            "INSERT INTO contacts (id, customer_id, name, source, status, created_at, updated_at) "
            "VALUES ('ct-1', 'cust-1', 'Bob', 'test', 'active', ?, ?)", (_NOW, _NOW),
        )
        conn.execute(
            "INSERT INTO companies (id, customer_id, name, created_at, updated_at) "
            "VALUES ('co-1', 'cust-1', 'Beta', ?, ?)", (_NOW, _NOW),
        )
        conn.execute(
            "INSERT INTO contact_company_roles (id, name, sort_order, is_system, created_at, updated_at) "
            "VALUES ('role-emp', 'Employee', 0, 1, ?, ?)", (_NOW, _NOW),
        )
        conn.execute(
            "INSERT INTO contact_company_roles (id, name, sort_order, is_system, created_at, updated_at) "
            "VALUES ('role-adv', 'Advisor', 3, 1, ?, ?)", (_NOW, _NOW),
        )

        conn.execute("DROP INDEX IF EXISTS idx_cc_dedup")

        # Employee role
        conn.execute(
            "INSERT INTO contact_companies "
            "(id, contact_id, company_id, role_id, is_primary, is_current, source, created_at, updated_at) "
            "VALUES ('aff-1', 'ct-1', 'co-1', 'role-emp', 1, 1, 'migration', ?, ?)", (_NOW, _NOW),
        )
        # Advisor role
        conn.execute(
            "INSERT INTO contact_companies "
            "(id, contact_id, company_id, role_id, is_primary, is_current, source, created_at, updated_at) "
            "VALUES ('aff-2', 'ct-1', 'co-1', 'role-adv', 0, 1, 'manual', ?, ?)", (_NOW, _NOW),
        )

        conn.execute("PRAGMA user_version = 10")
        conn.commit()
        conn.close()

        from poc.migrate_to_v11 import migrate
        migrate(db_file, dry_run=False)

        conn = sqlite3.connect(str(db_file))
        conn.row_factory = sqlite3.Row
        count = conn.execute(
            "SELECT COUNT(*) AS cnt FROM contact_companies WHERE contact_id = 'ct-1'"
        ).fetchone()["cnt"]
        assert count == 2
        conn.close()

    def test_migration_dry_run_leaves_original_intact(self, tmp_path, monkeypatch):
        """Dry run should not modify the original database."""
        db_file = tmp_path / "migrate_dry.db"
        monkeypatch.setattr("poc.config.DB_PATH", db_file)
        init_db(db_file)

        conn = sqlite3.connect(str(db_file))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=OFF")

        conn.execute(
            "INSERT INTO customers (id, name, slug, is_active, created_at, updated_at) "
            "VALUES ('cust-1', 'Test', 'test', 1, ?, ?)", (_NOW, _NOW),
        )
        conn.execute(
            "INSERT INTO contacts (id, customer_id, name, source, status, created_at, updated_at) "
            "VALUES ('ct-1', 'cust-1', 'Carol', 'test', 'active', ?, ?)", (_NOW, _NOW),
        )
        conn.execute(
            "INSERT INTO companies (id, customer_id, name, created_at, updated_at) "
            "VALUES ('co-1', 'cust-1', 'Gamma', ?, ?)", (_NOW, _NOW),
        )

        conn.execute("DROP INDEX IF EXISTS idx_cc_dedup")

        for i in range(3):
            conn.execute(
                "INSERT INTO contact_companies "
                "(id, contact_id, company_id, is_primary, is_current, source, created_at, updated_at) "
                "VALUES (?, 'ct-1', 'co-1', 1, 1, 'sync', ?, ?)",
                (f"aff-{i}", _NOW, _NOW),
            )

        conn.execute("PRAGMA user_version = 10")
        conn.commit()
        conn.close()

        from poc.migrate_to_v11 import migrate
        migrate(db_file, dry_run=True)

        # Original should still have 3 duplicates
        conn = sqlite3.connect(str(db_file))
        conn.row_factory = sqlite3.Row
        count = conn.execute(
            "SELECT COUNT(*) AS cnt FROM contact_companies WHERE contact_id = 'ct-1'"
        ).fetchone()["cnt"]
        assert count == 3

        version = conn.execute("PRAGMA user_version").fetchone()[0]
        assert version == 10
        conn.close()
