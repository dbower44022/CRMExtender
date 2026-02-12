"""Tests for poc.domain_resolver — domain-to-company resolution."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from starlette.testclient import TestClient

from poc.database import get_connection, init_db
from poc.domain_resolver import (
    PUBLIC_DOMAINS,
    DomainResolveResult,
    ensure_domain_identifier,
    extract_domain,
    is_public_domain,
    resolve_company_by_domain,
    resolve_company_for_email,
    resolve_unlinked_contacts,
)


@pytest.fixture()
def tmp_db(tmp_path, monkeypatch):
    """Create a temporary database and point config at it."""
    db_file = tmp_path / "test.db"
    monkeypatch.setattr("poc.config.DB_PATH", db_file)
    init_db(db_file)
    return db_file


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _insert_company(conn, company_id="co-1", name="Acme Corp", domain=None, status="active"):
    now = _now_iso()
    conn.execute(
        "INSERT INTO companies (id, name, domain, industry, description, status, "
        "created_at, updated_at) VALUES (?, ?, ?, '', '', ?, ?, ?)",
        (company_id, name, domain, status, now, now),
    )


def _insert_company_identifier(conn, company_id, domain, identifier_id=None):
    now = _now_iso()
    conn.execute(
        "INSERT INTO company_identifiers (id, company_id, type, value, is_primary, source, "
        "created_at, updated_at) VALUES (?, ?, 'domain', ?, 0, 'test', ?, ?)",
        (identifier_id or str(uuid.uuid4()), company_id, domain, now, now),
    )


def _insert_contact(conn, contact_id, name, email):
    now = _now_iso()
    conn.execute(
        "INSERT INTO contacts (id, name, source, status, "
        "created_at, updated_at) VALUES (?, ?, 'test', 'active', ?, ?)",
        (contact_id, name, now, now),
    )
    conn.execute(
        "INSERT INTO contact_identifiers (id, contact_id, type, value, is_primary, "
        "status, source, verified, created_at, updated_at) "
        "VALUES (?, ?, 'email', ?, 1, 'active', 'test', 1, ?, ?)",
        (str(uuid.uuid4()), contact_id, email, now, now),
    )


def _link_contact(conn, contact_id, company_id):
    """Create a contact_companies affiliation row."""
    conn.execute(
        "INSERT OR IGNORE INTO contact_companies "
        "(id, contact_id, company_id, is_primary, is_current, source, "
        "created_at, updated_at) "
        "VALUES (?, ?, ?, 1, 1, 'test', ?, ?)",
        (str(uuid.uuid4()), contact_id, company_id, _now_iso(), _now_iso()),
    )


# ---------------------------------------------------------------------------
# extract_domain
# ---------------------------------------------------------------------------

class TestExtractDomain:
    def test_normal_email(self):
        assert extract_domain("alice@acme.com") == "acme.com"

    def test_uppercase(self):
        assert extract_domain("Alice@ACME.COM") == "acme.com"

    def test_no_at(self):
        assert extract_domain("not-an-email") is None

    def test_empty_string(self):
        assert extract_domain("") is None

    def test_multiple_at(self):
        assert extract_domain("user@sub@domain.com") == "domain.com"


# ---------------------------------------------------------------------------
# is_public_domain
# ---------------------------------------------------------------------------

class TestIsPublicDomain:
    def test_gmail(self):
        assert is_public_domain("gmail.com") is True

    def test_business_domain(self):
        assert is_public_domain("acme.com") is False

    def test_case_insensitive(self):
        assert is_public_domain("Gmail.COM") is True


# ---------------------------------------------------------------------------
# resolve_company_by_domain
# ---------------------------------------------------------------------------

class TestResolveCompanyByDomain:
    def test_via_companies_domain(self, tmp_db):
        with get_connection() as conn:
            _insert_company(conn, "co-1", "Acme Corp", domain="acme.com")
            result = resolve_company_by_domain(conn, "acme.com")
        assert result is not None
        assert result["name"] == "Acme Corp"

    def test_via_company_identifiers(self, tmp_db):
        with get_connection() as conn:
            _insert_company(conn, "co-1", "Acme Corp", domain=None)
            _insert_company_identifier(conn, "co-1", "acme.com")
            result = resolve_company_by_domain(conn, "acme.com")
        assert result is not None
        assert result["name"] == "Acme Corp"

    def test_no_match(self, tmp_db):
        with get_connection() as conn:
            _insert_company(conn, "co-1", "Acme Corp", domain="acme.com")
            result = resolve_company_by_domain(conn, "unknown.com")
        assert result is None

    def test_inactive_ignored(self, tmp_db):
        with get_connection() as conn:
            _insert_company(conn, "co-1", "Dead Corp", domain="dead.com", status="inactive")
            result = resolve_company_by_domain(conn, "dead.com")
        assert result is None


# ---------------------------------------------------------------------------
# ensure_domain_identifier
# ---------------------------------------------------------------------------

class TestEnsureDomainIdentifier:
    def test_creates_new(self, tmp_db):
        with get_connection() as conn:
            _insert_company(conn, "co-1", "Acme Corp")
            inserted = ensure_domain_identifier(conn, "co-1", "acme.com")
        assert inserted is True
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM company_identifiers WHERE company_id = 'co-1'"
            ).fetchone()
        assert row is not None
        assert row["value"] == "acme.com"

    def test_idempotent(self, tmp_db):
        with get_connection() as conn:
            _insert_company(conn, "co-1", "Acme Corp")
            ensure_domain_identifier(conn, "co-1", "acme.com")
            inserted = ensure_domain_identifier(conn, "co-1", "acme.com")
        assert inserted is False

    def test_different_company_blocked(self, tmp_db):
        """UNIQUE(type, value) means a second company can't claim the same domain."""
        with get_connection() as conn:
            _insert_company(conn, "co-1", "Acme Corp")
            _insert_company(conn, "co-2", "Beta Corp")
            ensure_domain_identifier(conn, "co-1", "acme.com")
            inserted = ensure_domain_identifier(conn, "co-2", "acme.com")
        assert inserted is False


# ---------------------------------------------------------------------------
# resolve_company_for_email
# ---------------------------------------------------------------------------

class TestResolveCompanyForEmail:
    def test_business_match(self, tmp_db):
        with get_connection() as conn:
            _insert_company(conn, "co-1", "Acme Corp", domain="acme.com")
            result = resolve_company_for_email(conn, "alice@acme.com")
        assert result is not None
        assert result["id"] == "co-1"

    def test_public_skip(self, tmp_db):
        with get_connection() as conn:
            result = resolve_company_for_email(conn, "user@gmail.com")
        assert result is None

    def test_unknown_domain_skip(self, tmp_db):
        with get_connection() as conn:
            result = resolve_company_for_email(conn, "alice@unknown.com")
        assert result is None


# ---------------------------------------------------------------------------
# resolve_unlinked_contacts
# ---------------------------------------------------------------------------

class TestResolveUnlinkedContacts:
    def test_links_contacts(self, tmp_db):
        with get_connection() as conn:
            _insert_company(conn, "co-1", "Acme Corp", domain="acme.com")
            _insert_contact(conn, "ct-1", "Alice", "alice@acme.com")
            _insert_contact(conn, "ct-2", "Bob", "bob@acme.com")

        result = resolve_unlinked_contacts()

        assert result.contacts_linked == 2
        with get_connection() as conn:
            row = conn.execute(
                "SELECT company_id FROM contact_companies WHERE contact_id = 'ct-1'"
            ).fetchone()
        assert row["company_id"] == "co-1"

    def test_dry_run(self, tmp_db):
        with get_connection() as conn:
            _insert_company(conn, "co-1", "Acme Corp", domain="acme.com")
            _insert_contact(conn, "ct-1", "Alice", "alice@acme.com")

        result = resolve_unlinked_contacts(dry_run=True)

        assert result.contacts_linked == 1
        with get_connection() as conn:
            row = conn.execute(
                "SELECT id FROM contact_companies WHERE contact_id = 'ct-1'"
            ).fetchone()
        assert row is None

    def test_skips_public(self, tmp_db):
        with get_connection() as conn:
            _insert_contact(conn, "ct-1", "Gmail User", "user@gmail.com")

        result = resolve_unlinked_contacts()

        assert result.contacts_skipped_public == 1
        assert result.contacts_linked == 0

    def test_skips_already_linked(self, tmp_db):
        with get_connection() as conn:
            _insert_company(conn, "co-1", "Acme Corp", domain="acme.com")
            _insert_contact(conn, "ct-1", "Alice", "alice@acme.com")
            _link_contact(conn, "ct-1", "co-1")

        result = resolve_unlinked_contacts()

        # Already linked contacts aren't even in the query results
        assert result.contacts_checked == 0
        assert result.contacts_linked == 0

    def test_counts_correct(self, tmp_db):
        with get_connection() as conn:
            _insert_company(conn, "co-1", "Acme Corp", domain="acme.com")
            _insert_contact(conn, "ct-1", "Alice", "alice@acme.com")
            _insert_contact(conn, "ct-2", "Gmail User", "user@gmail.com")
            _insert_contact(conn, "ct-3", "Unknown", "unknown@nope.com")

        result = resolve_unlinked_contacts()

        assert result.contacts_checked == 3
        assert result.contacts_linked == 1
        assert result.contacts_skipped_public == 1
        assert result.contacts_skipped_no_match == 1


# ---------------------------------------------------------------------------
# Web route
# ---------------------------------------------------------------------------

@pytest.fixture()
def client(tmp_db):
    from poc.web.app import create_app
    app = create_app()
    return TestClient(app, raise_server_exceptions=False)


class TestWebRoute:
    def test_resolve_domains_returns_200(self, client, tmp_db):
        with get_connection() as conn:
            _insert_company(conn, "co-1", "Acme Corp", domain="acme.com")
            _insert_contact(conn, "ct-1", "Alice", "alice@acme.com")

        resp = client.post("/companies/resolve-domains")
        assert resp.status_code == 200
        assert "1" in resp.text  # contacts_linked

    def test_resolve_domains_returns_count(self, client, tmp_db):
        resp = client.post("/companies/resolve-domains")
        assert resp.status_code == 200
        assert "0" in resp.text  # no contacts linked
