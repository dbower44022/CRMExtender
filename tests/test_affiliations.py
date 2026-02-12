"""Tests for Multi-Company Contact Affiliations (Phase 10).

Covers: role CRUD, affiliation CRUD, settings UI, contact routes,
company routes, contact detail/edit templates, and company detail.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from poc.database import get_connection, init_db


_NOW = datetime.now(timezone.utc).isoformat()

CUST_ID = "cust-test"
USER_ID = "user-admin"
USER_REGULAR_ID = "user-regular"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

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


@pytest.fixture()
def tmp_db(tmp_path, monkeypatch):
    """Create a DB with one customer, one admin user, one regular user."""
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
        conn.execute(
            "INSERT INTO users "
            "(id, customer_id, email, name, role, is_active, created_at, updated_at) "
            "VALUES (?, ?, 'regular@test.com', 'Regular User', 'user', 1, ?, ?)",
            (USER_REGULAR_ID, CUST_ID, _NOW, _NOW),
        )
        # Seed system roles for the test customer (init_db seeds per existing customer)
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
    """TestClient authenticated as admin user."""
    monkeypatch.setattr(
        "poc.hierarchy.get_current_user",
        lambda: {"id": USER_ID, "email": "admin@test.com", "name": "Admin User",
                 "role": "admin", "customer_id": CUST_ID},
    )
    from poc.web.app import create_app
    app = create_app()
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture()
def regular_client(tmp_db, monkeypatch):
    """TestClient authenticated as regular (non-admin) user."""
    monkeypatch.setattr(
        "poc.hierarchy.get_current_user",
        lambda: {"id": USER_REGULAR_ID, "email": "regular@test.com",
                 "name": "Regular User", "role": "user",
                 "customer_id": CUST_ID},
    )
    from poc.web.app import create_app
    app = create_app()
    return TestClient(app, raise_server_exceptions=False)


def _create_contact(name="Alice", customer_id=CUST_ID, email=None):
    """Helper: insert a contact and return its id."""
    cid = str(uuid.uuid4())
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO contacts "
            "(id, customer_id, name, source, status, created_at, updated_at) "
            "VALUES (?, ?, ?, 'test', 'active', ?, ?)",
            (cid, customer_id, name, _NOW, _NOW),
        )
        if email:
            conn.execute(
                "INSERT INTO contact_identifiers "
                "(id, contact_id, type, value, is_primary, created_at, updated_at) "
                "VALUES (?, ?, 'email', ?, 1, ?, ?)",
                (str(uuid.uuid4()), cid, email, _NOW, _NOW),
            )
        # visibility row
        conn.execute(
            "INSERT INTO user_contacts "
            "(id, user_id, contact_id, visibility, is_owner, created_at, updated_at) "
            "VALUES (?, ?, ?, 'public', 1, ?, ?)",
            (str(uuid.uuid4()), USER_ID, cid, _NOW, _NOW),
        )
    return cid


def _create_company(name="Acme Corp", domain="acme.com", customer_id=CUST_ID):
    """Helper: insert a company and return its id."""
    co_id = str(uuid.uuid4())
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO companies "
            "(id, customer_id, name, domain, status, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, 'active', ?, ?)",
            (co_id, customer_id, name, domain, _NOW, _NOW),
        )
        conn.execute(
            "INSERT INTO user_companies "
            "(id, user_id, company_id, visibility, is_owner, created_at, updated_at) "
            "VALUES (?, ?, ?, 'public', 1, ?, ?)",
            (str(uuid.uuid4()), USER_ID, co_id, _NOW, _NOW),
        )
    return co_id


# ======================================================================
# Data Layer: contact_company_roles CRUD
# ======================================================================


class TestRoleCRUD:

    def test_system_roles_seeded(self, tmp_db):
        from poc.contact_company_roles import list_roles
        roles = list_roles(customer_id=CUST_ID)
        names = {r["name"] for r in roles}
        assert "Employee" in names
        assert "Founder" in names
        assert len(roles) == 8
        assert all(r["is_system"] for r in roles)

    def test_create_custom_role(self, tmp_db):
        from poc.contact_company_roles import create_role, list_roles
        role = create_role("Consultant", customer_id=CUST_ID, created_by=USER_ID)
        assert role["name"] == "Consultant"
        assert role["is_system"] == 0
        assert role["customer_id"] == CUST_ID
        roles = list_roles(customer_id=CUST_ID)
        assert any(r["name"] == "Consultant" for r in roles)

    def test_create_duplicate_role_raises(self, tmp_db):
        from poc.contact_company_roles import create_role
        create_role("Specialist", customer_id=CUST_ID)
        with pytest.raises(ValueError, match="already exists"):
            create_role("Specialist", customer_id=CUST_ID)

    def test_get_role(self, tmp_db):
        from poc.contact_company_roles import create_role, get_role
        role = create_role("Analyst", customer_id=CUST_ID)
        fetched = get_role(role["id"])
        assert fetched is not None
        assert fetched["name"] == "Analyst"

    def test_get_role_by_name(self, tmp_db):
        from poc.contact_company_roles import create_role, get_role_by_name
        create_role("Partner", customer_id=CUST_ID)
        found = get_role_by_name("Partner", customer_id=CUST_ID)
        assert found is not None
        assert found["name"] == "Partner"

    def test_update_role(self, tmp_db):
        from poc.contact_company_roles import create_role, update_role
        role = create_role("OldName", customer_id=CUST_ID)
        updated = update_role(role["id"], name="NewName", sort_order=50)
        assert updated["name"] == "NewName"
        assert updated["sort_order"] == 50

    def test_update_system_role_raises(self, tmp_db):
        """System roles cannot be modified."""
        from poc.contact_company_roles import list_roles, update_role
        roles = list_roles(customer_id=CUST_ID)
        system_role = next(r for r in roles if r["is_system"])
        with pytest.raises(ValueError, match="system role"):
            update_role(system_role["id"], name="Changed")

    def test_delete_role(self, tmp_db):
        from poc.contact_company_roles import create_role, delete_role, get_role
        role = create_role("Temp", customer_id=CUST_ID)
        delete_role(role["id"])
        assert get_role(role["id"]) is None

    def test_delete_system_role_raises(self, tmp_db):
        from poc.contact_company_roles import delete_role, list_roles
        roles = list_roles(customer_id=CUST_ID)
        system_role = next(r for r in roles if r["is_system"])
        with pytest.raises(ValueError, match="system role"):
            delete_role(system_role["id"])

    def test_delete_role_in_use_raises(self, tmp_db):
        from poc.contact_company_roles import create_role, delete_role
        from poc.contact_companies import add_affiliation
        role = create_role("InUse", customer_id=CUST_ID)
        cid = _create_contact()
        co_id = _create_company()
        add_affiliation(cid, co_id, role_id=role["id"])
        with pytest.raises(ValueError, match="used by"):
            delete_role(role["id"])


# ======================================================================
# Data Layer: contact_companies (affiliation) CRUD
# ======================================================================


class TestAffiliationCRUD:

    def test_add_affiliation(self, tmp_db):
        from poc.contact_companies import add_affiliation, list_affiliations_for_contact
        cid = _create_contact()
        co_id = _create_company()
        aff = add_affiliation(cid, co_id, is_primary=True, source="test")
        assert aff["contact_id"] == cid
        assert aff["company_id"] == co_id
        assert aff["is_primary"] == 1
        affs = list_affiliations_for_contact(cid)
        assert len(affs) == 1

    def test_add_affiliation_idempotent_with_role(self, tmp_db):
        """INSERT OR IGNORE prevents duplicating when UNIQUE columns are non-NULL."""
        from poc.contact_company_roles import list_roles
        from poc.contact_companies import add_affiliation, list_affiliations_for_contact
        cid = _create_contact()
        co_id = _create_company()
        roles = list_roles(customer_id=CUST_ID)
        role_id = roles[0]["id"]
        add_affiliation(cid, co_id, role_id=role_id, started_at="2025-01-01", source="sync")
        add_affiliation(cid, co_id, role_id=role_id, started_at="2025-01-01", source="sync")
        affs = list_affiliations_for_contact(cid)
        assert len(affs) == 1

    def test_multiple_affiliations(self, tmp_db):
        from poc.contact_companies import add_affiliation, list_affiliations_for_contact
        cid = _create_contact()
        co1 = _create_company("Company A", "a.com")
        co2 = _create_company("Company B", "b.com")
        add_affiliation(cid, co1, is_primary=True)
        add_affiliation(cid, co2, is_primary=False)
        affs = list_affiliations_for_contact(cid)
        assert len(affs) == 2

    def test_update_affiliation(self, tmp_db):
        from poc.contact_companies import add_affiliation, update_affiliation
        cid = _create_contact()
        co_id = _create_company()
        aff = add_affiliation(cid, co_id, title="Engineer")
        updated = update_affiliation(aff["id"], title="Sr Engineer")
        assert updated["title"] == "Sr Engineer"

    def test_remove_affiliation(self, tmp_db):
        from poc.contact_companies import add_affiliation, list_affiliations_for_contact, remove_affiliation
        cid = _create_contact()
        co_id = _create_company()
        aff = add_affiliation(cid, co_id)
        remove_affiliation(aff["id"])
        assert list_affiliations_for_contact(cid) == []

    def test_get_affiliation(self, tmp_db):
        from poc.contact_companies import add_affiliation, get_affiliation
        cid = _create_contact()
        co_id = _create_company()
        aff = add_affiliation(cid, co_id, title="CEO")
        fetched = get_affiliation(aff["id"])
        assert fetched is not None
        assert fetched["title"] == "CEO"

    def test_get_primary_company(self, tmp_db):
        from poc.contact_companies import add_affiliation, get_primary_company
        cid = _create_contact()
        co1 = _create_company("Primary Co", "primary.com")
        co2 = _create_company("Other Co", "other.com")
        add_affiliation(cid, co1, is_primary=True)
        add_affiliation(cid, co2, is_primary=False)
        primary = get_primary_company(cid)
        assert primary is not None
        assert primary["company_name"] == "Primary Co"

    def test_get_primary_company_fallback(self, tmp_db):
        """If no primary set, returns any current affiliation."""
        from poc.contact_companies import add_affiliation, get_primary_company
        cid = _create_contact()
        co_id = _create_company()
        add_affiliation(cid, co_id, is_primary=False, is_current=True)
        primary = get_primary_company(cid)
        assert primary is not None

    def test_get_primary_company_none(self, tmp_db):
        from poc.contact_companies import get_primary_company
        cid = _create_contact()
        assert get_primary_company(cid) is None

    def test_set_primary(self, tmp_db):
        from poc.contact_companies import add_affiliation, get_affiliation, set_primary
        cid = _create_contact()
        co1 = _create_company("A", "a.com")
        co2 = _create_company("B", "b.com")
        aff1 = add_affiliation(cid, co1, is_primary=True)
        aff2 = add_affiliation(cid, co2, is_primary=False)
        set_primary(aff2["id"])
        assert get_affiliation(aff1["id"])["is_primary"] == 0
        assert get_affiliation(aff2["id"])["is_primary"] == 1

    def test_list_affiliations_for_company(self, tmp_db):
        from poc.contact_companies import add_affiliation, list_affiliations_for_company
        c1 = _create_contact("Alice")
        c2 = _create_contact("Bob")
        co_id = _create_company()
        add_affiliation(c1, co_id)
        add_affiliation(c2, co_id)
        affs = list_affiliations_for_company(co_id)
        assert len(affs) == 2

    def test_affiliation_with_role(self, tmp_db):
        from poc.contact_company_roles import create_role
        from poc.contact_companies import add_affiliation, list_affiliations_for_contact
        role = create_role("Engineer", customer_id=CUST_ID)
        cid = _create_contact()
        co_id = _create_company()
        add_affiliation(cid, co_id, role_id=role["id"], title="Lead")
        affs = list_affiliations_for_contact(cid)
        assert affs[0]["role_name"] == "Engineer"
        assert affs[0]["title"] == "Lead"


# ======================================================================
# Settings UI: Roles Management
# ======================================================================


class TestRolesSettingsUI:

    def test_roles_page_loads(self, client, tmp_db):
        resp = client.get("/settings/roles")
        assert resp.status_code == 200
        assert "Affiliation Roles" in resp.text

    def test_roles_page_requires_admin(self, regular_client, tmp_db):
        resp = regular_client.get("/settings/roles")
        assert resp.status_code == 403

    def test_create_role_via_ui(self, client, tmp_db):
        resp = client.post("/settings/roles", data={
            "name": "Consultant", "sort_order": "50",
        })
        assert resp.status_code == 200
        assert "Consultant" in resp.text

    def test_create_duplicate_role_shows_error(self, client, tmp_db):
        client.post("/settings/roles", data={"name": "X", "sort_order": "0"})
        resp = client.post("/settings/roles", data={"name": "X", "sort_order": "0"})
        assert resp.status_code == 200
        assert "already exists" in resp.text

    def test_edit_role_via_ui(self, client, tmp_db):
        from poc.contact_company_roles import create_role
        role = create_role("EditMe", customer_id=CUST_ID)
        resp = client.post(f"/settings/roles/{role['id']}/edit", data={
            "name": "Edited", "sort_order": "10",
        })
        assert resp.status_code == 200
        assert "Edited" in resp.text

    def test_delete_role_via_ui(self, client, tmp_db):
        from poc.contact_company_roles import create_role, get_role
        role = create_role("DeleteMe", customer_id=CUST_ID)
        resp = client.delete(f"/settings/roles/{role['id']}")
        assert resp.status_code == 200
        assert get_role(role["id"]) is None


# ======================================================================
# Web Routes: Contact list shows primary company
# ======================================================================


class TestContactListCompanyColumn:

    def test_contact_list_shows_primary_company(self, client, tmp_db):
        from poc.contact_companies import add_affiliation
        cid = _create_contact("Jane")
        co_id = _create_company("Widgets Inc", "widgets.com")
        add_affiliation(cid, co_id, is_primary=True)
        resp = client.get("/contacts")
        assert resp.status_code == 200
        assert "Widgets Inc" in resp.text

    def test_contact_list_no_company(self, client, tmp_db):
        _create_contact("Loner")
        resp = client.get("/contacts")
        assert resp.status_code == 200
        assert "Loner" in resp.text


# ======================================================================
# Web Routes: Contact detail — affiliations section
# ======================================================================


class TestContactDetailAffiliations:

    def test_detail_shows_affiliations(self, client, tmp_db):
        from poc.contact_companies import add_affiliation
        cid = _create_contact("Alice")
        co_id = _create_company("BigCo", "big.com")
        add_affiliation(cid, co_id, is_primary=True, title="VP")
        resp = client.get(f"/contacts/{cid}")
        assert resp.status_code == 200
        assert "BigCo" in resp.text
        assert "Company Affiliations" in resp.text

    def test_detail_shows_no_affiliations_message(self, client, tmp_db):
        cid = _create_contact("Alone")
        resp = client.get(f"/contacts/{cid}")
        assert resp.status_code == 200
        assert "No company affiliations" in resp.text

    def test_add_affiliation_via_route(self, client, tmp_db):
        cid = _create_contact("Bob")
        co_id = _create_company("NewCo", "newco.com")
        resp = client.post(
            f"/contacts/{cid}/affiliations",
            data={
                "company_id": co_id,
                "role_id": "",
                "title": "Dev",
                "department": "Eng",
                "is_primary": "1",
                "is_current": "1",
                "started_at": "",
                "ended_at": "",
                "notes": "",
            },
        )
        assert resp.status_code == 200
        assert "NewCo" in resp.text

    def test_delete_affiliation_via_route(self, client, tmp_db):
        from poc.contact_companies import add_affiliation
        cid = _create_contact("Carol")
        co_id = _create_company("TmpCo", "tmp.com")
        aff = add_affiliation(cid, co_id)
        resp = client.delete(f"/contacts/{cid}/affiliations/{aff['id']}")
        assert resp.status_code == 200
        assert "No company affiliations" in resp.text

    def test_set_primary_via_route(self, client, tmp_db):
        from poc.contact_companies import add_affiliation, get_affiliation
        cid = _create_contact("Dan")
        co1 = _create_company("Co1", "co1.com")
        co2 = _create_company("Co2", "co2.com")
        aff1 = add_affiliation(cid, co1, is_primary=True)
        aff2 = add_affiliation(cid, co2, is_primary=False)
        resp = client.post(f"/contacts/{cid}/affiliations/{aff2['id']}/primary")
        assert resp.status_code == 200
        assert get_affiliation(aff1["id"])["is_primary"] == 0
        assert get_affiliation(aff2["id"])["is_primary"] == 1

    def test_edit_affiliation_via_route(self, client, tmp_db):
        from poc.contact_companies import add_affiliation, get_affiliation
        cid = _create_contact("Eve")
        co_id = _create_company("EveCo", "eveco.com")
        aff = add_affiliation(cid, co_id, title="Junior")
        resp = client.post(
            f"/contacts/{cid}/affiliations/{aff['id']}/edit",
            data={
                "role_id": "",
                "title": "Senior",
                "department": "",
                "is_primary": "",
                "is_current": "1",
                "started_at": "",
                "ended_at": "",
                "notes": "",
            },
        )
        assert resp.status_code == 200
        updated = get_affiliation(aff["id"])
        assert updated["title"] == "Senior"


# ======================================================================
# Web Routes: Contact edit — no company dropdown
# ======================================================================


class TestContactEdit:

    def test_edit_form_no_company_dropdown(self, client, tmp_db):
        cid = _create_contact("Editable")
        resp = client.get(f"/contacts/{cid}/edit")
        assert resp.status_code == 200
        assert "company_id" not in resp.text

    def test_edit_post_no_company(self, client, tmp_db):
        cid = _create_contact("Updatable")
        resp = client.post(
            f"/contacts/{cid}/edit",
            data={"name": "Updated", "source": "manual", "status": "active"},
        )
        assert resp.status_code in (200, 303, 307)


# ======================================================================
# Web Routes: Company detail shows contacts with role/title
# ======================================================================


class TestCompanyDetailContacts:

    def test_company_detail_shows_affiliated_contacts(self, client, tmp_db):
        from poc.contact_company_roles import get_role_by_name
        from poc.contact_companies import add_affiliation
        co_id = _create_company("DetailCo", "detailco.com")
        cid = _create_contact("Frank")
        role = get_role_by_name("Advisor", customer_id=CUST_ID)
        add_affiliation(cid, co_id, role_id=role["id"], title="Chief Advisor", is_primary=True)
        resp = client.get(f"/companies/{co_id}")
        assert resp.status_code == 200
        assert "Frank" in resp.text
        assert "Advisor" in resp.text
        assert "Chief Advisor" in resp.text

    def test_company_detail_shows_current_and_former(self, client, tmp_db):
        from poc.contact_companies import add_affiliation
        co_id = _create_company("HistoryCo", "history.com")
        c1 = _create_contact("Current")
        c2 = _create_contact("Former")
        add_affiliation(c1, co_id, is_current=True)
        add_affiliation(c2, co_id, is_current=False)
        resp = client.get(f"/companies/{co_id}")
        assert resp.status_code == 200
        assert "Current" in resp.text
        assert "Former" in resp.text

    def test_company_detail_no_contacts(self, client, tmp_db):
        co_id = _create_company("EmptyCo", "empty.com")
        resp = client.get(f"/companies/{co_id}")
        assert resp.status_code == 200
        assert "No contacts linked" in resp.text


# ======================================================================
# Web Routes: Company confirm auto-link creates affiliations
# ======================================================================


class TestCompanyConfirmAutoLink:

    def test_confirm_creates_affiliations(self, client, tmp_db):
        """Creating a company with auto-link should create affiliations, not set company_id."""
        from poc.contact_companies import list_affiliations_for_contact
        cid = _create_contact("Linkable", email="linkable@autolink.com")
        resp = client.post("/companies/confirm", data={
            "name": "AutoLink Corp",
            "domain": "autolink.com",
            "industry": "",
            "description": "",
            "website": "",
            "headquarters_location": "",
            "link": "true",
        })
        assert resp.status_code in (200, 303, 307)
        affs = list_affiliations_for_contact(cid)
        assert len(affs) == 1
        assert affs[0]["source"] == "domain_link"


# ======================================================================
# Schema: contacts table has no company_id column
# ======================================================================


class TestSchemaNoCompanyId:

    def test_contacts_table_no_company_id(self, tmp_db):
        """Verify that the contacts table does not have company_id or company columns."""
        with get_connection() as conn:
            info = conn.execute("PRAGMA table_info(contacts)").fetchall()
        col_names = {row["name"] for row in info}
        assert "company_id" not in col_names
        assert "company" not in col_names

    def test_contact_company_roles_table_exists(self, tmp_db):
        with get_connection() as conn:
            info = conn.execute("PRAGMA table_info(contact_company_roles)").fetchall()
        col_names = {row["name"] for row in info}
        assert "name" in col_names
        assert "is_system" in col_names

    def test_contact_companies_table_exists(self, tmp_db):
        with get_connection() as conn:
            info = conn.execute("PRAGMA table_info(contact_companies)").fetchall()
        col_names = {row["name"] for row in info}
        assert "contact_id" in col_names
        assert "company_id" in col_names
        assert "role_id" in col_names
        assert "title" in col_names
        assert "is_primary" in col_names

    def test_relationship_types_no_employee(self, tmp_db):
        """The rt-employee relationship type should not be seeded."""
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM relationship_types WHERE id = 'rt-employee'"
            ).fetchone()
        assert row is None
