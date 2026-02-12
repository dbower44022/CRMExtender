"""Tests for companies, audit columns, and contact-company linkage."""

from datetime import datetime, timezone

import pytest

from poc.database import get_connection, init_db
from poc.models import Company, Project, Topic, KnownContact
from poc.hierarchy import (
    create_company,
    create_project,
    create_topic,
    delete_company,
    find_company_by_domain,
    find_company_by_name,
    get_company,
    list_companies,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def tmp_db(tmp_path, monkeypatch):
    """Create a temporary database and point config at it."""
    db_file = tmp_path / "test.db"
    monkeypatch.setattr("poc.config.DB_PATH", db_file)
    init_db(db_file)
    return db_file


def _insert_user(conn, user_id="user-1", email="admin@example.com"):
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT OR IGNORE INTO customers (id, name, slug, is_active, created_at, updated_at) "
        "VALUES ('cust-test', 'Test', 'test', 1, ?, ?)",
        (now, now),
    )
    conn.execute(
        "INSERT OR IGNORE INTO users "
        "(id, customer_id, email, name, role, is_active, created_at, updated_at) "
        "VALUES (?, 'cust-test', ?, 'Admin', 'admin', 1, ?, ?)",
        (user_id, email, now, now),
    )


# ---------------------------------------------------------------------------
# Company model tests
# ---------------------------------------------------------------------------

class TestCompanyModel:

    def test_to_row_defaults(self):
        c = Company(name="Acme Corp")
        row = c.to_row(company_id="c-1")
        assert row["id"] == "c-1"
        assert row["name"] == "Acme Corp"
        assert row["domain"] is None
        assert row["industry"] is None
        assert row["status"] == "active"
        assert row["created_by"] is None
        assert row["updated_by"] is None
        assert row["created_at"] is not None

    def test_to_row_with_all_fields(self):
        c = Company(
            name="Big Co",
            domain="bigco.com",
            industry="Tech",
            description="A big company",
        )
        row = c.to_row(
            company_id="c-2",
            created_by="user-1",
            updated_by="user-1",
        )
        assert row["domain"] == "bigco.com"
        assert row["industry"] == "Tech"
        assert row["description"] == "A big company"
        assert row["created_by"] == "user-1"
        assert row["updated_by"] == "user-1"

    def test_from_row_roundtrip(self):
        c = Company(name="Test", domain="test.com", industry="Finance")
        row = c.to_row()
        rebuilt = Company.from_row(row)
        assert rebuilt.name == "Test"
        assert rebuilt.domain == "test.com"
        assert rebuilt.industry == "Finance"
        assert rebuilt.status == "active"

    def test_from_row_missing_fields(self):
        row = {"name": "Minimal", "status": "active"}
        c = Company.from_row(row)
        assert c.name == "Minimal"
        assert c.domain == ""
        assert c.industry == ""


# ---------------------------------------------------------------------------
# Company CRUD tests
# ---------------------------------------------------------------------------

class TestCompanyCRUD:

    def test_create_and_list(self, tmp_db):
        row = create_company("Acme Corp", domain="acme.com")
        assert row["name"] == "Acme Corp"
        assert row["domain"] == "acme.com"

        companies = list_companies()
        assert len(companies) == 1
        assert companies[0]["name"] == "Acme Corp"

    def test_get_company(self, tmp_db):
        row = create_company("TestCo")
        found = get_company(row["id"])
        assert found is not None
        assert found["name"] == "TestCo"

    def test_find_by_name(self, tmp_db):
        create_company("FindMe")
        found = find_company_by_name("FindMe")
        assert found is not None
        assert found["name"] == "FindMe"
        assert find_company_by_name("NotHere") is None

    def test_find_by_domain(self, tmp_db):
        create_company("DomainCo", domain="domain.co")
        found = find_company_by_domain("domain.co")
        assert found is not None
        assert found["name"] == "DomainCo"
        assert find_company_by_domain("other.co") is None

    def test_duplicate_name_raises(self, tmp_db):
        create_company("UniqueInc")
        with pytest.raises(ValueError, match="already exists"):
            create_company("UniqueInc")

    def test_delete_company(self, tmp_db):
        row = create_company("Doomed Inc")
        impact = delete_company(row["id"])
        assert impact["contacts_unlinked"] == 0
        assert get_company(row["id"]) is None

    def test_list_multiple_sorted(self, tmp_db):
        create_company("Zeta")
        create_company("Alpha")
        create_company("Mu")
        companies = list_companies()
        names = [c["name"] for c in companies]
        assert names == ["Alpha", "Mu", "Zeta"]

    def test_create_with_audit(self, tmp_db):
        with get_connection() as conn:
            _insert_user(conn, user_id="u-1")
        row = create_company("AuditCo", created_by="u-1")
        assert row["created_by"] == "u-1"
        assert row["updated_by"] == "u-1"


# ---------------------------------------------------------------------------
# Audit column tests
# ---------------------------------------------------------------------------

class TestAuditColumns:

    def test_project_audit_fields(self, tmp_db):
        with get_connection() as conn:
            _insert_user(conn, user_id="u-1")
        row = create_project("AuditProj", created_by="u-1")
        assert row["created_by"] == "u-1"
        assert row["updated_by"] == "u-1"

    def test_topic_audit_fields(self, tmp_db):
        with get_connection() as conn:
            _insert_user(conn, user_id="u-1")
        proj = create_project("Proj")
        row = create_topic(proj["id"], "AuditTopic", created_by="u-1")
        assert row["created_by"] == "u-1"
        assert row["updated_by"] == "u-1"

    def test_audit_defaults_to_none(self, tmp_db):
        proj = create_project("NoAudit")
        assert proj["created_by"] is None
        assert proj["updated_by"] is None

    def test_known_contact_audit_fields(self):
        kc = KnownContact(email="test@x.com", name="Test")
        contact, identifier = kc.to_row(
            created_by="u-1", updated_by="u-1",
        )
        assert contact["created_by"] == "u-1"
        assert identifier["created_by"] == "u-1"

    def test_known_contact_no_company_id(self):
        """KnownContact.to_row() should not include company_id."""
        kc = KnownContact(email="test@x.com", name="Test")
        contact, _ = kc.to_row()
        assert "company_id" not in contact


# ---------------------------------------------------------------------------
# Contact-company linkage tests (via contact_companies junction table)
# ---------------------------------------------------------------------------

class TestContactCompanyLink:

    def test_link_contact_to_company(self, tmp_db):
        from poc.contact_companies import add_affiliation, list_affiliations_for_contact
        company = create_company("LinkCo")
        now = datetime.now(timezone.utc).isoformat()

        with get_connection() as conn:
            conn.execute(
                "INSERT INTO contacts (id, name, source, status, created_at, updated_at) "
                "VALUES (?, ?, 'test', 'active', ?, ?)",
                ("ct-1", "Alice", now, now),
            )

        add_affiliation("ct-1", company["id"], is_primary=True)
        affs = list_affiliations_for_contact("ct-1")
        assert len(affs) == 1
        assert affs[0]["company_id"] == company["id"]

    def test_company_deletion_cascades_affiliations(self, tmp_db):
        from poc.contact_companies import add_affiliation, list_affiliations_for_contact
        company = create_company("GoneCo")
        now = datetime.now(timezone.utc).isoformat()

        with get_connection() as conn:
            conn.execute(
                "INSERT INTO contacts (id, name, source, status, created_at, updated_at) "
                "VALUES (?, ?, 'test', 'active', ?, ?)",
                ("ct-2", "Bob", now, now),
            )

        add_affiliation("ct-2", company["id"], is_primary=True)
        impact = delete_company(company["id"])
        assert impact["contacts_unlinked"] == 1

        affs = list_affiliations_for_contact("ct-2")
        assert len(affs) == 0

    def test_multiple_contacts_same_company(self, tmp_db):
        from poc.contact_companies import add_affiliation
        company = create_company("SharedCo")
        now = datetime.now(timezone.utc).isoformat()

        with get_connection() as conn:
            for i in range(3):
                conn.execute(
                    "INSERT INTO contacts (id, name, source, status, created_at, updated_at) "
                    "VALUES (?, ?, 'test', 'active', ?, ?)",
                    (f"ct-{i}", f"Person {i}", now, now),
                )

        for i in range(3):
            add_affiliation(f"ct-{i}", company["id"])

        impact = delete_company(company["id"])
        assert impact["contacts_unlinked"] == 3
