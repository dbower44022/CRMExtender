"""Tests for Phase 21: Temporal Tracking for Sub-Entity Tables.

Covers: migration, CRUD add/update/get ordering, web contact routes,
web company routes, and sync caller.
"""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from poc.database import get_connection, init_db


_NOW = datetime.now(timezone.utc).isoformat()

CUST_ID = "cust-test"
USER_ID = "user-admin"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def tmp_db(tmp_path, monkeypatch):
    """Create a DB with one customer and one admin user."""
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
        # Seed a contact
        conn.execute(
            "INSERT INTO contacts (id, customer_id, name, source, status, created_at, updated_at) "
            "VALUES ('ct-1', ?, 'Alice', 'test', 'active', ?, ?)",
            (CUST_ID, _NOW, _NOW),
        )
        conn.execute(
            "INSERT INTO user_contacts (id, user_id, contact_id, visibility, is_owner, created_at, updated_at) "
            "VALUES (?, ?, 'ct-1', 'public', 1, ?, ?)",
            (str(uuid.uuid4()), USER_ID, _NOW, _NOW),
        )
        # Seed a company
        conn.execute(
            "INSERT INTO companies (id, customer_id, name, domain, status, created_at, updated_at) "
            "VALUES ('co-1', ?, 'Acme Corp', 'acme.com', 'active', ?, ?)",
            (CUST_ID, _NOW, _NOW),
        )
        conn.execute(
            "INSERT INTO user_companies (id, user_id, company_id, visibility, is_owner, created_at, updated_at) "
            "VALUES (?, ?, 'co-1', 'public', 1, ?, ?)",
            (str(uuid.uuid4()), USER_ID, _NOW, _NOW),
        )

    return db_file


@pytest.fixture()
def client(tmp_db, monkeypatch):
    """FastAPI test client with auth bypass."""
    def _mock_user(request):
        request.state.user = {
            "id": USER_ID, "customer_id": CUST_ID,
            "email": "admin@test.com", "name": "Admin", "role": "admin",
        }
        request.state.customer_id = CUST_ID

    from poc.web.app import create_app
    app = create_app()

    @app.middleware("http")
    async def inject_user(request, call_next):
        _mock_user(request)
        return await call_next(request)

    return TestClient(app)


# ---------------------------------------------------------------------------
# Migration tests
# ---------------------------------------------------------------------------

class TestMigration:
    """Verify migrate_to_v15 works correctly."""

    def test_migration_adds_columns_and_maps_status(self, tmp_path):
        """Migration adds is_current to all 4 tables and maps status→is_current."""
        db_file = tmp_path / "migrate_test.db"

        # Create a v14 database with old schema
        conn = sqlite3.connect(str(db_file))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=OFF")

        # Minimal schema for migration test
        conn.execute("""CREATE TABLE customers (id TEXT PRIMARY KEY, name TEXT, slug TEXT, is_active INTEGER, created_at TEXT, updated_at TEXT)""")
        conn.execute("""CREATE TABLE users (id TEXT PRIMARY KEY, customer_id TEXT, email TEXT, name TEXT, role TEXT, is_active INTEGER, password_hash TEXT, google_sub TEXT, created_at TEXT, updated_at TEXT)""")
        conn.execute("""CREATE TABLE contacts (id TEXT PRIMARY KEY, customer_id TEXT, name TEXT, source TEXT, status TEXT, created_by TEXT, updated_by TEXT, created_at TEXT, updated_at TEXT)""")

        conn.execute("""CREATE TABLE contact_identifiers (
            id TEXT PRIMARY KEY, contact_id TEXT, type TEXT, value TEXT,
            label TEXT, is_primary INTEGER DEFAULT 0, status TEXT DEFAULT 'active',
            source TEXT, verified INTEGER DEFAULT 0,
            created_by TEXT, updated_by TEXT, created_at TEXT, updated_at TEXT,
            UNIQUE(type, value))""")
        conn.execute("CREATE INDEX idx_ci_status ON contact_identifiers(status)")
        conn.execute("CREATE INDEX idx_ci_contact ON contact_identifiers(contact_id)")

        conn.execute("""CREATE TABLE phone_numbers (
            id TEXT PRIMARY KEY, entity_type TEXT, entity_id TEXT,
            phone_type TEXT, number TEXT, is_primary INTEGER DEFAULT 0,
            source TEXT, confidence REAL, created_at TEXT, updated_at TEXT)""")

        conn.execute("""CREATE TABLE addresses (
            id TEXT PRIMARY KEY, entity_type TEXT, entity_id TEXT,
            address_type TEXT, street TEXT, city TEXT, state TEXT,
            postal_code TEXT, country TEXT, is_primary INTEGER DEFAULT 0,
            source TEXT, confidence REAL, created_at TEXT, updated_at TEXT)""")

        conn.execute("""CREATE TABLE email_addresses (
            id TEXT PRIMARY KEY, entity_type TEXT, entity_id TEXT,
            email_type TEXT, address TEXT, is_primary INTEGER DEFAULT 0,
            source TEXT, confidence REAL, created_at TEXT, updated_at TEXT)""")

        # Insert test data
        now = _NOW
        conn.execute("INSERT INTO contacts VALUES ('c1', 'cust', 'Test', 'test', 'active', NULL, NULL, ?, ?)", (now, now))
        conn.execute("INSERT INTO contact_identifiers VALUES ('ci1', 'c1', 'email', 'test@example.com', NULL, 1, 'active', 'test', 0, NULL, NULL, ?, ?)", (now, now))
        conn.execute("INSERT INTO contact_identifiers VALUES ('ci2', 'c1', 'email', 'old@example.com', NULL, 0, 'inactive', 'test', 0, NULL, NULL, ?, ?)", (now, now))
        conn.execute("INSERT INTO phone_numbers VALUES ('p1', 'contact', 'c1', 'mobile', '+15551234', 1, NULL, NULL, ?, ?)", (now, now))
        conn.execute("INSERT INTO addresses VALUES ('a1', 'contact', 'c1', 'work', '123 Main', 'NYC', 'NY', '10001', 'US', 1, NULL, NULL, ?, ?)", (now, now))
        conn.execute("INSERT INTO email_addresses VALUES ('e1', 'company', 'co1', 'general', 'info@acme.com', 0, NULL, NULL, ?, ?)", (now, now))

        conn.execute("PRAGMA user_version = 14")
        conn.commit()
        conn.close()

        # Run migration
        from poc.migrate_to_v15 import migrate
        migrate(db_file, dry_run=False)

        # Verify
        conn = sqlite3.connect(str(db_file))
        conn.row_factory = sqlite3.Row

        # contact_identifiers: status mapped correctly
        ci1 = conn.execute("SELECT * FROM contact_identifiers WHERE id = 'ci1'").fetchone()
        assert ci1["is_current"] == 1
        ci2 = conn.execute("SELECT * FROM contact_identifiers WHERE id = 'ci2'").fetchone()
        assert ci2["is_current"] == 0
        # status column should be gone
        cols = {r[1] for r in conn.execute("PRAGMA table_info(contact_identifiers)")}
        assert "status" not in cols
        assert "is_current" in cols
        assert "started_at" in cols
        assert "ended_at" in cols

        # phone_numbers: new columns with defaults
        p1 = conn.execute("SELECT * FROM phone_numbers WHERE id = 'p1'").fetchone()
        assert p1["is_current"] == 1
        assert p1["started_at"] is None

        # addresses: new columns
        a1 = conn.execute("SELECT * FROM addresses WHERE id = 'a1'").fetchone()
        assert a1["is_current"] == 1

        # email_addresses: new columns
        e1 = conn.execute("SELECT * FROM email_addresses WHERE id = 'e1'").fetchone()
        assert e1["is_current"] == 1

        # Version bumped
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        assert version == 15

        conn.close()

    def test_migration_creates_indexes(self, tmp_path):
        """Migration creates the expected indexes."""
        db_file = tmp_path / "migrate_idx.db"
        conn = sqlite3.connect(str(db_file))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=OFF")

        conn.execute("""CREATE TABLE customers (id TEXT PRIMARY KEY, name TEXT, slug TEXT, is_active INTEGER, created_at TEXT, updated_at TEXT)""")
        conn.execute("""CREATE TABLE users (id TEXT PRIMARY KEY, customer_id TEXT, email TEXT, name TEXT, role TEXT, is_active INTEGER, password_hash TEXT, google_sub TEXT, created_at TEXT, updated_at TEXT)""")
        conn.execute("""CREATE TABLE contacts (id TEXT PRIMARY KEY, customer_id TEXT, name TEXT, source TEXT, status TEXT, created_by TEXT, updated_by TEXT, created_at TEXT, updated_at TEXT)""")
        conn.execute("""CREATE TABLE contact_identifiers (
            id TEXT PRIMARY KEY, contact_id TEXT, type TEXT, value TEXT,
            label TEXT, is_primary INTEGER DEFAULT 0, status TEXT DEFAULT 'active',
            source TEXT, verified INTEGER DEFAULT 0,
            created_by TEXT, updated_by TEXT, created_at TEXT, updated_at TEXT,
            UNIQUE(type, value))""")
        conn.execute("CREATE INDEX idx_ci_status ON contact_identifiers(status)")
        conn.execute("CREATE INDEX idx_ci_contact ON contact_identifiers(contact_id)")
        conn.execute("""CREATE TABLE phone_numbers (id TEXT PRIMARY KEY, entity_type TEXT, entity_id TEXT, phone_type TEXT, number TEXT, is_primary INTEGER DEFAULT 0, source TEXT, confidence REAL, created_at TEXT, updated_at TEXT)""")
        conn.execute("""CREATE TABLE addresses (id TEXT PRIMARY KEY, entity_type TEXT, entity_id TEXT, address_type TEXT, street TEXT, city TEXT, state TEXT, postal_code TEXT, country TEXT, is_primary INTEGER DEFAULT 0, source TEXT, confidence REAL, created_at TEXT, updated_at TEXT)""")
        conn.execute("""CREATE TABLE email_addresses (id TEXT PRIMARY KEY, entity_type TEXT, entity_id TEXT, email_type TEXT, address TEXT, is_primary INTEGER DEFAULT 0, source TEXT, confidence REAL, created_at TEXT, updated_at TEXT)""")

        conn.execute("PRAGMA user_version = 14")
        conn.commit()
        conn.close()

        from poc.migrate_to_v15 import migrate
        migrate(db_file, dry_run=False)

        conn = sqlite3.connect(str(db_file))
        indexes = {r[1] for r in conn.execute("SELECT * FROM sqlite_master WHERE type='index'").fetchall()}
        assert "idx_ci_current" in indexes
        assert "idx_ci_contact" in indexes
        assert "idx_phone_current" in indexes
        assert "idx_addr_current" in indexes
        assert "idx_email_current" in indexes
        # old index should not exist
        assert "idx_ci_status" not in indexes
        conn.close()

    def test_migration_dry_run(self, tmp_path):
        """Dry run doesn't modify the original database."""
        db_file = tmp_path / "migrate_dry.db"
        conn = sqlite3.connect(str(db_file))
        conn.execute("PRAGMA foreign_keys=OFF")
        conn.execute("""CREATE TABLE customers (id TEXT PRIMARY KEY, name TEXT, slug TEXT, is_active INTEGER, created_at TEXT, updated_at TEXT)""")
        conn.execute("""CREATE TABLE users (id TEXT PRIMARY KEY, customer_id TEXT, email TEXT, name TEXT, role TEXT, is_active INTEGER, password_hash TEXT, google_sub TEXT, created_at TEXT, updated_at TEXT)""")
        conn.execute("""CREATE TABLE contacts (id TEXT PRIMARY KEY, customer_id TEXT, name TEXT, source TEXT, status TEXT, created_by TEXT, updated_by TEXT, created_at TEXT, updated_at TEXT)""")
        conn.execute("""CREATE TABLE contact_identifiers (
            id TEXT PRIMARY KEY, contact_id TEXT, type TEXT, value TEXT,
            label TEXT, is_primary INTEGER DEFAULT 0, status TEXT DEFAULT 'active',
            source TEXT, verified INTEGER DEFAULT 0,
            created_by TEXT, updated_by TEXT, created_at TEXT, updated_at TEXT,
            UNIQUE(type, value))""")
        conn.execute("CREATE INDEX idx_ci_status ON contact_identifiers(status)")
        conn.execute("CREATE INDEX idx_ci_contact ON contact_identifiers(contact_id)")
        conn.execute("""CREATE TABLE phone_numbers (id TEXT PRIMARY KEY, entity_type TEXT, entity_id TEXT, phone_type TEXT, number TEXT, is_primary INTEGER DEFAULT 0, source TEXT, confidence REAL, created_at TEXT, updated_at TEXT)""")
        conn.execute("""CREATE TABLE addresses (id TEXT PRIMARY KEY, entity_type TEXT, entity_id TEXT, address_type TEXT, street TEXT, city TEXT, state TEXT, postal_code TEXT, country TEXT, is_primary INTEGER DEFAULT 0, source TEXT, confidence REAL, created_at TEXT, updated_at TEXT)""")
        conn.execute("""CREATE TABLE email_addresses (id TEXT PRIMARY KEY, entity_type TEXT, entity_id TEXT, email_type TEXT, address TEXT, is_primary INTEGER DEFAULT 0, source TEXT, confidence REAL, created_at TEXT, updated_at TEXT)""")
        conn.execute("PRAGMA user_version = 14")
        conn.commit()
        conn.close()

        from poc.migrate_to_v15 import migrate
        migrate(db_file, dry_run=True)

        # Original should still be v14
        conn = sqlite3.connect(str(db_file))
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        assert version == 14
        conn.close()


# ---------------------------------------------------------------------------
# CRUD add tests
# ---------------------------------------------------------------------------

class TestCrudAdd:
    """Verify add functions default is_current=1 and accept overrides."""

    def test_add_phone_defaults_current(self, tmp_db):
        from poc.hierarchy import add_phone_number
        row = add_phone_number("contact", "ct-1", "+15551234567", phone_type="mobile", customer_id=CUST_ID)
        assert row is not None
        assert row["is_current"] == 1
        assert row["started_at"] is None
        assert row["ended_at"] is None

    def test_add_phone_override_not_current(self, tmp_db):
        from poc.hierarchy import add_phone_number
        row = add_phone_number("contact", "ct-1", "+15559876543", phone_type="work",
                               is_current=0, started_at="2020-01-01", ended_at="2024-12-31",
                               customer_id=CUST_ID)
        assert row is not None
        assert row["is_current"] == 0
        assert row["started_at"] == "2020-01-01"
        assert row["ended_at"] == "2024-12-31"

    def test_add_address_defaults_current(self, tmp_db):
        from poc.hierarchy import add_address
        row = add_address("contact", "ct-1", street="123 Main St", city="NYC")
        assert row["is_current"] == 1
        assert row["started_at"] is None

    def test_add_address_override_not_current(self, tmp_db):
        from poc.hierarchy import add_address
        row = add_address("contact", "ct-1", street="456 Old St",
                          is_current=0, started_at="2019-06-01")
        assert row["is_current"] == 0
        assert row["started_at"] == "2019-06-01"

    def test_add_email_address_defaults_current(self, tmp_db):
        from poc.hierarchy import add_email_address
        row = add_email_address("company", "co-1", "info@acme.com")
        assert row["is_current"] == 1

    def test_add_email_address_override(self, tmp_db):
        from poc.hierarchy import add_email_address
        row = add_email_address("company", "co-1", "old@acme.com",
                                is_current=0, ended_at="2023-01-01")
        assert row["is_current"] == 0
        assert row["ended_at"] == "2023-01-01"

    def test_add_contact_identifier_defaults_current(self, tmp_db):
        from poc.hierarchy import add_contact_identifier
        row = add_contact_identifier("ct-1", "email", "alice@test.com")
        assert row["is_current"] == 1

    def test_add_contact_identifier_override(self, tmp_db):
        from poc.hierarchy import add_contact_identifier
        row = add_contact_identifier("ct-1", "email", "old@test.com",
                                     is_current=0, started_at="2018-01-01")
        assert row["is_current"] == 0
        assert row["started_at"] == "2018-01-01"


# ---------------------------------------------------------------------------
# CRUD update tests
# ---------------------------------------------------------------------------

class TestCrudUpdate:
    """Verify update functions set temporal fields correctly."""

    def test_update_phone_number(self, tmp_db):
        from poc.hierarchy import add_phone_number, update_phone_number
        row = add_phone_number("contact", "ct-1", "+15551111111", customer_id=CUST_ID)
        updated = update_phone_number(row["id"], is_current=0, ended_at="2025-12-31")
        assert updated["is_current"] == 0
        assert updated["ended_at"] == "2025-12-31"

    def test_update_phone_rejects_unknown(self, tmp_db):
        from poc.hierarchy import add_phone_number, update_phone_number
        row = add_phone_number("contact", "ct-1", "+15552222222", customer_id=CUST_ID)
        result = update_phone_number(row["id"], bogus_field="nope")
        assert result is None

    def test_update_address(self, tmp_db):
        from poc.hierarchy import add_address, update_address
        row = add_address("contact", "ct-1", street="100 Old Rd")
        updated = update_address(row["id"], is_current=0, started_at="2020-01-01", ended_at="2024-06-30")
        assert updated["is_current"] == 0
        assert updated["started_at"] == "2020-01-01"
        assert updated["ended_at"] == "2024-06-30"

    def test_update_address_rejects_unknown(self, tmp_db):
        from poc.hierarchy import add_address, update_address
        row = add_address("contact", "ct-1", street="200 New Rd")
        result = update_address(row["id"], bad_field="nope")
        assert result is None

    def test_update_email_address(self, tmp_db):
        from poc.hierarchy import add_email_address, update_email_address
        row = add_email_address("company", "co-1", "support@acme.com")
        updated = update_email_address(row["id"], is_current=0)
        assert updated["is_current"] == 0

    def test_update_email_rejects_unknown(self, tmp_db):
        from poc.hierarchy import add_email_address, update_email_address
        row = add_email_address("company", "co-1", "sales@acme.com")
        result = update_email_address(row["id"], unknown="x")
        assert result is None

    def test_update_contact_identifier(self, tmp_db):
        from poc.hierarchy import add_contact_identifier, update_contact_identifier
        row = add_contact_identifier("ct-1", "linkedin", "https://linkedin.com/in/alice")
        updated = update_contact_identifier(row["id"], is_current=0, ended_at="2025-01-15")
        assert updated["is_current"] == 0
        assert updated["ended_at"] == "2025-01-15"

    def test_update_contact_identifier_rejects_unknown(self, tmp_db):
        from poc.hierarchy import add_contact_identifier, update_contact_identifier
        row = add_contact_identifier("ct-1", "other", "some-id")
        result = update_contact_identifier(row["id"], unknown_field="bad")
        assert result is None


# ---------------------------------------------------------------------------
# CRUD get ordering tests
# ---------------------------------------------------------------------------

class TestCrudGetOrdering:
    """Verify non-current records sort after current ones."""

    def test_phone_ordering(self, tmp_db):
        from poc.hierarchy import add_phone_number, get_phone_numbers, update_phone_number
        p1 = add_phone_number("contact", "ct-1", "+15551000001", phone_type="mobile", customer_id=CUST_ID)
        p2 = add_phone_number("contact", "ct-1", "+15551000002", phone_type="work", customer_id=CUST_ID)
        # Mark p1 as non-current
        update_phone_number(p1["id"], is_current=0)
        phones = get_phone_numbers("contact", "ct-1")
        assert len(phones) == 2
        # Current phone should come first
        assert phones[0]["id"] == p2["id"]
        assert phones[1]["id"] == p1["id"]

    def test_address_ordering(self, tmp_db):
        from poc.hierarchy import add_address, get_addresses, update_address
        a1 = add_address("contact", "ct-1", street="Old St")
        a2 = add_address("contact", "ct-1", street="New St")
        update_address(a1["id"], is_current=0)
        addresses = get_addresses("contact", "ct-1")
        assert addresses[0]["id"] == a2["id"]
        assert addresses[1]["id"] == a1["id"]

    def test_email_ordering(self, tmp_db):
        from poc.hierarchy import add_email_address, get_email_addresses, update_email_address
        e1 = add_email_address("company", "co-1", "old@acme.com")
        e2 = add_email_address("company", "co-1", "new@acme.com")
        update_email_address(e1["id"], is_current=0)
        emails = get_email_addresses("company", "co-1")
        assert emails[0]["id"] == e2["id"]
        assert emails[1]["id"] == e1["id"]

    def test_identifier_ordering(self, tmp_db):
        from poc.hierarchy import add_contact_identifier, get_contact_identifiers, update_contact_identifier
        i1 = add_contact_identifier("ct-1", "email", "old@example.com")
        i2 = add_contact_identifier("ct-1", "email", "new@example.com")
        update_contact_identifier(i1["id"], is_current=0)
        identifiers = get_contact_identifiers("ct-1")
        assert identifiers[0]["id"] == i2["id"]
        assert identifiers[1]["id"] == i1["id"]


# ---------------------------------------------------------------------------
# Web contact route tests
# ---------------------------------------------------------------------------

class TestWebContactRoutes:
    """Verify edit endpoints toggle is_current for contact sub-entities."""

    def test_edit_phone_toggle_off(self, client, tmp_db):
        from poc.hierarchy import add_phone_number
        p = add_phone_number("contact", "ct-1", "+15553334444", customer_id=CUST_ID)
        resp = client.post(
            f"/contacts/ct-1/phones/{p['id']}/edit",
            data={"is_current": "0"},
        )
        assert resp.status_code == 200
        assert "(former)" in resp.text

    def test_edit_phone_toggle_on(self, client, tmp_db):
        from poc.hierarchy import add_phone_number, update_phone_number
        p = add_phone_number("contact", "ct-1", "+15555556666", customer_id=CUST_ID)
        update_phone_number(p["id"], is_current=0)
        resp = client.post(
            f"/contacts/ct-1/phones/{p['id']}/edit",
            data={"is_current": "1"},
        )
        assert resp.status_code == 200
        assert "opacity:0.6" not in resp.text or "(former)" not in resp.text

    def test_edit_address_toggle(self, client, tmp_db):
        from poc.hierarchy import add_address
        a = add_address("contact", "ct-1", street="999 Test Ave")
        resp = client.post(
            f"/contacts/ct-1/addresses/{a['id']}/edit",
            data={"is_current": "0"},
        )
        assert resp.status_code == 200
        assert "(former)" in resp.text

    def test_edit_email_toggle(self, client, tmp_db):
        from poc.hierarchy import add_contact_identifier
        i = add_contact_identifier("ct-1", "email", "toggle@example.com")
        resp = client.post(
            f"/contacts/ct-1/emails/{i['id']}/edit",
            data={"is_current": "0"},
        )
        assert resp.status_code == 200
        assert "(former)" in resp.text

    def test_edit_identifier_toggle(self, client, tmp_db):
        from poc.hierarchy import add_contact_identifier
        i = add_contact_identifier("ct-1", "linkedin", "https://linkedin.com/in/test")
        resp = client.post(
            f"/contacts/ct-1/identifiers/{i['id']}/edit",
            data={"is_current": "0"},
        )
        assert resp.status_code == 200
        assert "(former)" in resp.text

    def test_dimmed_row_in_phones(self, client, tmp_db):
        from poc.hierarchy import add_phone_number, update_phone_number
        p = add_phone_number("contact", "ct-1", "+15557778888", customer_id=CUST_ID)
        update_phone_number(p["id"], is_current=0)
        # Trigger a re-render by editing again (reactivate)
        resp = client.post(
            f"/contacts/ct-1/phones/{p['id']}/edit",
            data={"is_current": "0"},
        )
        assert resp.status_code == 200
        assert "opacity:0.6" in resp.text

    def test_period_display_in_address(self, client, tmp_db):
        from poc.hierarchy import add_address, update_address
        a = add_address("contact", "ct-1", street="123 Period St")
        update_address(a["id"], started_at="2020-01-01", ended_at="2024-12-31")
        resp = client.post(
            f"/contacts/ct-1/addresses/{a['id']}/edit",
            data={"is_current": "1"},
        )
        assert resp.status_code == 200

    def test_reactivate_button_present(self, client, tmp_db):
        from poc.hierarchy import add_phone_number, update_phone_number
        p = add_phone_number("contact", "ct-1", "+15559990000", customer_id=CUST_ID)
        update_phone_number(p["id"], is_current=0)
        resp = client.post(
            f"/contacts/ct-1/phones/{p['id']}/edit",
            data={"is_current": "0"},
        )
        assert resp.status_code == 200
        # Reactivate button should be present (checkmark)
        assert "&#8635;" in resp.text


# ---------------------------------------------------------------------------
# Web company route tests
# ---------------------------------------------------------------------------

class TestWebCompanyRoutes:
    """Verify edit endpoints work for company sub-entities."""

    def test_edit_company_phone(self, client, tmp_db):
        from poc.hierarchy import add_phone_number
        p = add_phone_number("company", "co-1", "+15551112233", phone_type="main", customer_id=CUST_ID)
        resp = client.post(
            f"/companies/co-1/phones/{p['id']}/edit",
            data={"is_current": "0"},
        )
        assert resp.status_code == 200
        assert "(former)" in resp.text

    def test_edit_company_address(self, client, tmp_db):
        from poc.hierarchy import add_address
        a = add_address("company", "co-1", street="1 Corp Plaza")
        resp = client.post(
            f"/companies/co-1/addresses/{a['id']}/edit",
            data={"is_current": "0"},
        )
        assert resp.status_code == 200
        assert "(former)" in resp.text

    def test_edit_company_email(self, client, tmp_db):
        from poc.hierarchy import add_email_address
        e = add_email_address("company", "co-1", "contact@acme.com")
        resp = client.post(
            f"/companies/co-1/emails/{e['id']}/edit",
            data={"is_current": "0"},
        )
        assert resp.status_code == 200
        assert "(former)" in resp.text

    def test_reactivate_company_phone(self, client, tmp_db):
        from poc.hierarchy import add_phone_number, update_phone_number
        p = add_phone_number("company", "co-1", "+15554445566", phone_type="main", customer_id=CUST_ID)
        update_phone_number(p["id"], is_current=0)
        resp = client.post(
            f"/companies/co-1/phones/{p['id']}/edit",
            data={"is_current": "1"},
        )
        assert resp.status_code == 200
        # Should no longer show "(former)"
        assert "&#128340;" in resp.text  # mark-as-former button for active rows

    def test_company_dimmed_email(self, client, tmp_db):
        from poc.hierarchy import add_email_address, update_email_address
        e = add_email_address("company", "co-1", "old@acme.com")
        update_email_address(e["id"], is_current=0)
        resp = client.post(
            f"/companies/co-1/emails/{e['id']}/edit",
            data={"is_current": "0"},
        )
        assert resp.status_code == 200
        assert "opacity:0.6" in resp.text

    def test_company_address_period(self, client, tmp_db):
        from poc.hierarchy import add_address, update_address
        a = add_address("company", "co-1", street="Old HQ")
        update_address(a["id"], started_at="2015-01-01", ended_at="2023-06-30", is_current=0)
        resp = client.post(
            f"/companies/co-1/addresses/{a['id']}/edit",
            data={"is_current": "0"},
        )
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Sync caller tests
# ---------------------------------------------------------------------------

class TestSyncCaller:
    """Verify sync INSERT uses is_current instead of status."""

    def test_sync_insert_uses_is_current(self, tmp_db):
        """The contact_identifiers table should have is_current column, not status."""
        with get_connection() as conn:
            cols = {r[1] for r in conn.execute("PRAGMA table_info(contact_identifiers)")}
        assert "is_current" in cols
        assert "status" not in cols

    def test_direct_insert_with_is_current(self, tmp_db):
        """Simulate what sync.py does — INSERT with is_current=1."""
        now = _NOW
        with get_connection() as conn:
            conn.execute(
                """INSERT INTO contact_identifiers
                   (id, contact_id, type, value, is_primary, is_current, source, verified, created_at, updated_at)
                   VALUES (?, 'ct-1', 'email', 'sync@example.com', 1, 1, 'google_contacts', 1, ?, ?)""",
                (str(uuid.uuid4()), now, now),
            )
            row = conn.execute(
                "SELECT * FROM contact_identifiers WHERE value = 'sync@example.com'"
            ).fetchone()
        assert row["is_current"] == 1


# ---------------------------------------------------------------------------
# Schema DDL tests
# ---------------------------------------------------------------------------

class TestSchemaDDL:
    """Verify init_db creates tables with temporal columns."""

    def test_phone_numbers_has_temporal_columns(self, tmp_db):
        with get_connection() as conn:
            cols = {r[1] for r in conn.execute("PRAGMA table_info(phone_numbers)")}
        assert "is_current" in cols
        assert "started_at" in cols
        assert "ended_at" in cols

    def test_addresses_has_temporal_columns(self, tmp_db):
        with get_connection() as conn:
            cols = {r[1] for r in conn.execute("PRAGMA table_info(addresses)")}
        assert "is_current" in cols
        assert "started_at" in cols
        assert "ended_at" in cols

    def test_email_addresses_has_temporal_columns(self, tmp_db):
        with get_connection() as conn:
            cols = {r[1] for r in conn.execute("PRAGMA table_info(email_addresses)")}
        assert "is_current" in cols
        assert "started_at" in cols
        assert "ended_at" in cols

    def test_contact_identifiers_has_temporal_columns(self, tmp_db):
        with get_connection() as conn:
            cols = {r[1] for r in conn.execute("PRAGMA table_info(contact_identifiers)")}
        assert "is_current" in cols
        assert "started_at" in cols
        assert "ended_at" in cols
        assert "status" not in cols
