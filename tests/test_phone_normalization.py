"""Tests for phone number normalization, formatting, and deduplication."""

from __future__ import annotations

import shutil
import sqlite3
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from poc.database import get_connection, init_db
from poc.phone_utils import format_phone, normalize_phone, resolve_country_code, validate_phone


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_NOW = datetime.now(timezone.utc).isoformat()


@pytest.fixture()
def tmp_db(tmp_path, monkeypatch):
    """Create a temporary database and point config at it."""
    db_file = tmp_path / "test.db"
    monkeypatch.setattr("poc.config.DB_PATH", db_file)
    init_db(db_file)

    # Seed customer + user for auth bypass mode
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO customers (id, name, slug, is_active, created_at, updated_at) "
            "VALUES ('cust-test', 'Test Org', 'test', 1, ?, ?)",
            (_NOW, _NOW),
        )
        conn.execute(
            "INSERT INTO users "
            "(id, customer_id, email, name, role, is_active, created_at, updated_at) "
            "VALUES ('user-test', 'cust-test', 'test@example.com', 'Test User', "
            "'admin', 1, ?, ?)",
            (_NOW, _NOW),
        )

    return db_file


@pytest.fixture()
def client(tmp_db, monkeypatch):
    monkeypatch.setattr("poc.config.CRM_AUTH_ENABLED", False)
    from poc.web.app import create_app
    app = create_app()
    return TestClient(app, raise_server_exceptions=False)


def _insert_company(conn, company_id, name="Acme Corp", domain="acme.com",
                    customer_id="cust-test"):
    conn.execute(
        "INSERT OR IGNORE INTO companies "
        "(id, name, domain, status, customer_id, created_at, updated_at) "
        "VALUES (?, ?, ?, 'active', ?, ?, ?)",
        (company_id, name, domain, customer_id, _NOW, _NOW),
    )
    conn.execute(
        "INSERT OR IGNORE INTO user_companies "
        "(id, user_id, company_id, visibility, is_owner, created_at, updated_at) "
        "VALUES (?, 'user-test', ?, 'public', 1, ?, ?)",
        (f"uc-{company_id}", company_id, _NOW, _NOW),
    )


def _insert_contact(conn, contact_id, name="Alice", email="alice@example.com",
                    customer_id="cust-test"):
    conn.execute(
        "INSERT OR IGNORE INTO contacts "
        "(id, name, status, customer_id, created_at, updated_at) "
        "VALUES (?, ?, 'active', ?, ?, ?)",
        (contact_id, name, customer_id, _NOW, _NOW),
    )
    conn.execute(
        "INSERT OR IGNORE INTO contact_identifiers "
        "(id, contact_id, type, value, is_primary, source, created_at, updated_at) "
        "VALUES (?, ?, 'email', ?, 1, 'test', ?, ?)",
        (f"ci-{contact_id}", contact_id, email, _NOW, _NOW),
    )
    conn.execute(
        "INSERT OR IGNORE INTO user_contacts "
        "(id, user_id, contact_id, visibility, is_owner, created_at, updated_at) "
        "VALUES (?, 'user-test', ?, 'public', 1, ?, ?)",
        (f"ucont-{contact_id}", contact_id, _NOW, _NOW),
    )


def _insert_address(conn, addr_id, entity_type, entity_id, country="US"):
    conn.execute(
        "INSERT OR IGNORE INTO addresses "
        "(id, entity_type, entity_id, address_type, country, is_primary, source, "
        "created_at, updated_at) "
        "VALUES (?, ?, ?, 'headquarters', ?, 1, '', ?, ?)",
        (addr_id, entity_type, entity_id, country, _NOW, _NOW),
    )


def _insert_phone_number(conn, phone_id, entity_type, entity_id, number,
                          phone_type="mobile"):
    conn.execute(
        "INSERT OR IGNORE INTO phone_numbers "
        "(id, entity_type, entity_id, phone_type, number, is_primary, source, "
        "created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, 0, '', ?, ?)",
        (phone_id, entity_type, entity_id, phone_type, number, _NOW, _NOW),
    )


# ===========================================================================
# Unit tests: normalize_phone
# ===========================================================================

class TestNormalizePhone:
    def test_us_number_with_dashes(self):
        assert normalize_phone("440-462-6500") == "+14404626500"

    def test_us_number_with_parens(self):
        assert normalize_phone("(440) 462-6500") == "+14404626500"

    def test_us_number_with_country_code(self):
        assert normalize_phone("+1-440-462-6500") == "+14404626500"

    def test_us_toll_free(self):
        assert normalize_phone("800-555-9999") == "+18005559999"

    def test_already_e164(self):
        assert normalize_phone("+14404626500") == "+14404626500"

    def test_uk_number(self):
        result = normalize_phone("020 7946 0958", "GB")
        assert result == "+442079460958"

    def test_invalid_too_short(self):
        assert normalize_phone("123") is None

    def test_invalid_letters(self):
        assert normalize_phone("not-a-number") is None

    def test_empty_string(self):
        assert normalize_phone("") is None

    def test_us_number_spaces(self):
        assert normalize_phone("440 462 6500") == "+14404626500"

    def test_us_number_dots(self):
        assert normalize_phone("440.462.6500") == "+14404626500"


# ===========================================================================
# Unit tests: format_phone
# ===========================================================================

class TestFormatPhone:
    def test_national_format_us(self):
        result = format_phone("+14404626500", "US")
        assert result == "(440) 462-6500"

    def test_international_for_foreign(self):
        result = format_phone("+442079460958", "US")
        assert result == "+44 20 7946 0958"

    def test_national_format_gb(self):
        result = format_phone("+442079460958", "GB")
        assert result == "020 7946 0958"

    def test_unparseable_fallback(self):
        assert format_phone("garbage", "US") == "garbage"

    def test_e164_input(self):
        result = format_phone("+18005559999", "US")
        assert result == "(800) 555-9999"


# ===========================================================================
# Unit tests: validate_phone
# ===========================================================================

class TestValidatePhone:
    def test_valid_us(self):
        assert validate_phone("(201) 555-0123") is True

    def test_invalid(self):
        assert validate_phone("abc") is False

    def test_empty(self):
        assert validate_phone("") is False


# ===========================================================================
# Unit tests: resolve_country_code
# ===========================================================================

class TestResolveCountryCode:
    def test_from_address(self, tmp_db):
        with get_connection() as conn:
            _insert_company(conn, "co-1", "Acme Corp")
            _insert_address(conn, "a-1", "company", "co-1", "GB")

        result = resolve_country_code("company", "co-1", customer_id="cust-test")
        assert result == "GB"

    def test_fallback_to_setting(self, tmp_db):
        from poc.settings import set_setting
        set_setting("cust-test", "default_phone_country", "DE", scope="system")

        with get_connection() as conn:
            _insert_company(conn, "co-2", "Beta Corp")

        result = resolve_country_code("company", "co-2", customer_id="cust-test")
        assert result == "DE"

    def test_fallback_to_us(self, tmp_db):
        with get_connection() as conn:
            _insert_company(conn, "co-3", "Gamma Corp")

        result = resolve_country_code("company", "co-3")
        assert result == "US"

    def test_primary_address_preferred(self, tmp_db):
        with get_connection() as conn:
            _insert_company(conn, "co-4", "Delta Corp")
            # Non-primary address first
            conn.execute(
                "INSERT INTO addresses "
                "(id, entity_type, entity_id, address_type, country, is_primary, "
                "source, created_at, updated_at) "
                "VALUES ('a-np', 'company', 'co-4', 'branch', 'FR', 0, '', ?, ?)",
                (_NOW, _NOW),
            )
            # Primary address
            conn.execute(
                "INSERT INTO addresses "
                "(id, entity_type, entity_id, address_type, country, is_primary, "
                "source, created_at, updated_at) "
                "VALUES ('a-p', 'company', 'co-4', 'headquarters', 'JP', 1, '', ?, ?)",
                (_NOW, _NOW),
            )

        result = resolve_country_code("company", "co-4", customer_id="cust-test")
        assert result == "JP"


# ===========================================================================
# Integration tests: add_phone_number normalization and dedup
# ===========================================================================

class TestAddPhoneNormalization:
    def test_normalizes_to_e164(self, tmp_db):
        from poc.hierarchy import add_phone_number
        with get_connection() as conn:
            _insert_company(conn, "co-1", "Acme Corp")

        result = add_phone_number("company", "co-1", "(201) 555-0123",
                                  phone_type="main", customer_id="cust-test")
        assert result is not None
        assert result["number"] == "+12015550123"

    def test_dedup_same_format(self, tmp_db):
        from poc.hierarchy import add_phone_number, get_phone_numbers
        with get_connection() as conn:
            _insert_company(conn, "co-1", "Acme Corp")

        add_phone_number("company", "co-1", "(201) 555-0123",
                         phone_type="main", customer_id="cust-test")
        add_phone_number("company", "co-1", "(201) 555-0123",
                         phone_type="work", customer_id="cust-test")

        phones = get_phone_numbers("company", "co-1")
        assert len(phones) == 1

    def test_dedup_different_formats(self, tmp_db):
        from poc.hierarchy import add_phone_number, get_phone_numbers
        with get_connection() as conn:
            _insert_company(conn, "co-1", "Acme Corp")

        add_phone_number("company", "co-1", "(201) 555-0123",
                         phone_type="main", customer_id="cust-test")
        add_phone_number("company", "co-1", "201-555-0123",
                         phone_type="work", customer_id="cust-test")
        add_phone_number("company", "co-1", "+12015550123",
                         phone_type="work", customer_id="cust-test")

        phones = get_phone_numbers("company", "co-1")
        assert len(phones) == 1

    def test_invalid_returns_none(self, tmp_db):
        from poc.hierarchy import add_phone_number
        with get_connection() as conn:
            _insert_company(conn, "co-1", "Acme Corp")

        result = add_phone_number("company", "co-1", "not-a-number",
                                  customer_id="cust-test")
        assert result is None

    def test_uses_address_country(self, tmp_db):
        from poc.hierarchy import add_phone_number
        with get_connection() as conn:
            _insert_company(conn, "co-1", "Acme Corp")
            _insert_address(conn, "a-1", "company", "co-1", "GB")

        result = add_phone_number("company", "co-1", "020 7946 0958",
                                  phone_type="main", customer_id="cust-test")
        assert result is not None
        assert result["number"] == "+442079460958"


# ===========================================================================
# Web route tests
# ===========================================================================

class TestWebPhoneRoutes:
    def test_add_phone_valid(self, client, tmp_db):
        with get_connection() as conn:
            _insert_company(conn, "co-1", "Acme Corp")

        resp = client.post("/companies/co-1/phones", data={
            "phone_type": "main",
            "number": "(201) 555-0123",
        })
        assert resp.status_code == 200
        assert "(201) 555-0123" in resp.text  # formatted national

        with get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM phone_numbers "
                "WHERE entity_type = 'company' AND entity_id = 'co-1'"
            ).fetchall()
        assert len(rows) == 1
        assert rows[0]["number"] == "+12015550123"

    def test_add_phone_invalid(self, client, tmp_db):
        with get_connection() as conn:
            _insert_company(conn, "co-1", "Acme Corp")

        resp = client.post("/companies/co-1/phones", data={
            "phone_type": "main",
            "number": "abc",
        })
        assert resp.status_code == 200
        assert "Invalid phone number" in resp.text

        with get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM phone_numbers "
                "WHERE entity_type = 'company' AND entity_id = 'co-1'"
            ).fetchall()
        assert len(rows) == 0

    def test_add_contact_phone_valid(self, client, tmp_db):
        with get_connection() as conn:
            _insert_contact(conn, "ct-1", "Alice", "alice@example.com")

        resp = client.post("/contacts/ct-1/phones", data={
            "phone_type": "work",
            "number": "(201) 555-0123",
        })
        assert resp.status_code == 200
        assert "(201) 555-0123" in resp.text

        with get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM phone_numbers WHERE entity_id = 'ct-1'"
            ).fetchall()
        assert len(rows) == 1
        assert rows[0]["number"] == "+12015550123"

    def test_display_formatting(self, client, tmp_db):
        with get_connection() as conn:
            _insert_company(conn, "co-1", "Acme Corp")
            _insert_phone_number(conn, "ph-1", "company", "co-1",
                                 "+12015550123", phone_type="main")

        resp = client.get("/companies/co-1")
        assert resp.status_code == 200
        assert "(201) 555-0123" in resp.text


# ===========================================================================
# Settings UI test
# ===========================================================================

class TestPhoneCountrySetting:
    def test_system_settings_shows_country_dropdown(self, client, tmp_db):
        resp = client.get("/settings/system")
        assert resp.status_code == 200
        assert "default_phone_country" in resp.text
        assert "United States" in resp.text

    def test_save_country_setting(self, client, tmp_db):
        resp = client.post("/settings/system", data={
            "company_name": "Test Org",
            "default_timezone": "UTC",
            "sync_enabled": "true",
            "default_phone_country": "GB",
        })
        assert resp.status_code == 200  # 303 redirect followed by TestClient

        from poc.settings import get_setting
        val = get_setting("cust-test", "default_phone_country")
        assert val == "GB"


# ===========================================================================
# Migration tests
# ===========================================================================

class TestMigration:
    def test_normalize_and_dedup(self, tmp_path):
        """Test that migration normalizes phones and deduplicates."""
        db_file = tmp_path / "migrate_test.db"
        init_db(db_file)

        conn = sqlite3.connect(str(db_file))
        conn.row_factory = sqlite3.Row
        now = _NOW

        # Seed customer
        conn.execute(
            "INSERT INTO customers (id, name, slug, is_active, created_at, updated_at) "
            "VALUES ('cust-test', 'Test', 'test', 1, ?, ?)",
            (now, now),
        )

        # Insert phone numbers in different formats for the same entity
        conn.execute(
            "INSERT INTO phone_numbers "
            "(id, entity_type, entity_id, phone_type, number, is_primary, source, "
            "created_at, updated_at) "
            "VALUES ('p1', 'company', 'co-1', 'main', '440-462-6500', 0, '', ?, ?)",
            (now, now),
        )
        conn.execute(
            "INSERT INTO phone_numbers "
            "(id, entity_type, entity_id, phone_type, number, is_primary, source, "
            "created_at, updated_at) "
            "VALUES ('p2', 'company', 'co-1', 'work', '(440) 462-6500', 0, '', ?, ?)",
            (now, now),
        )
        # A different number
        conn.execute(
            "INSERT INTO phone_numbers "
            "(id, entity_type, entity_id, phone_type, number, is_primary, source, "
            "created_at, updated_at) "
            "VALUES ('p3', 'company', 'co-1', 'main', '800-555-1234', 0, '', ?, ?)",
            (now, now),
        )
        conn.commit()
        conn.close()

        from poc.migrate_to_v9 import migrate
        migrate(db_file, dry_run=False)

        conn = sqlite3.connect(str(db_file))
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM phone_numbers ORDER BY number"
        ).fetchall()
        conn.close()

        numbers = [r["number"] for r in rows]
        assert "+14404626500" in numbers
        assert "+18005551234" in numbers
        # The two equivalent numbers should be deduped to one
        assert len(rows) == 2

    def test_invalid_preserved(self, tmp_path):
        """Invalid phone numbers are left as-is by migration."""
        db_file = tmp_path / "migrate_test2.db"
        init_db(db_file)

        conn = sqlite3.connect(str(db_file))
        conn.row_factory = sqlite3.Row
        now = _NOW

        conn.execute(
            "INSERT INTO customers (id, name, slug, is_active, created_at, updated_at) "
            "VALUES ('cust-test', 'Test', 'test', 1, ?, ?)",
            (now, now),
        )
        conn.execute(
            "INSERT INTO phone_numbers "
            "(id, entity_type, entity_id, phone_type, number, is_primary, source, "
            "created_at, updated_at) "
            "VALUES ('p1', 'company', 'co-1', 'main', 'ext-123', 0, '', ?, ?)",
            (now, now),
        )
        conn.commit()
        conn.close()

        from poc.migrate_to_v9 import migrate
        migrate(db_file, dry_run=False)

        conn = sqlite3.connect(str(db_file))
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT number FROM phone_numbers WHERE id = 'p1'"
        ).fetchone()
        conn.close()

        assert row["number"] == "ext-123"

    def test_seeds_country_setting(self, tmp_path):
        """Migration seeds default_phone_country for existing customers."""
        db_file = tmp_path / "migrate_test3.db"
        init_db(db_file)

        conn = sqlite3.connect(str(db_file))
        conn.row_factory = sqlite3.Row
        now = _NOW

        conn.execute(
            "INSERT INTO customers (id, name, slug, is_active, created_at, updated_at) "
            "VALUES ('cust-test', 'Test', 'test', 1, ?, ?)",
            (now, now),
        )
        conn.commit()
        conn.close()

        from poc.migrate_to_v9 import migrate
        migrate(db_file, dry_run=False)

        conn = sqlite3.connect(str(db_file))
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT setting_value FROM settings "
            "WHERE customer_id = 'cust-test' AND setting_name = 'default_phone_country'"
        ).fetchone()
        conn.close()

        assert row is not None
        assert row["setting_value"] == "US"
