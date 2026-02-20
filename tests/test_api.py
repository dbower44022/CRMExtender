"""Tests for the JSON API (/api/v1/) that powers the React frontend."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from poc.database import get_connection, init_db

_NOW = datetime.now(timezone.utc).isoformat()

CUST_ID = "cust-api-test"
USER_ID = "user-api-admin"


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
            "VALUES (?, ?, 'admin@test.com', 'Admin', 'admin', 1, ?, ?)",
            (USER_ID, CUST_ID, _NOW, _NOW),
        )
    return db_file


def _make_client(monkeypatch):
    monkeypatch.setattr(
        "poc.hierarchy.get_current_user",
        lambda: {"id": USER_ID, "email": "admin@test.com", "name": "Admin",
                 "role": "admin", "customer_id": CUST_ID},
    )
    from poc.web.app import create_app
    app = create_app()
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture()
def client(tmp_db, monkeypatch):
    return _make_client(monkeypatch)


def _seed_contacts(n=5):
    with get_connection() as conn:
        for i in range(n):
            cid = f"contact-{i}"
            conn.execute(
                "INSERT INTO contacts (id, customer_id, name, source, status, created_at, updated_at) "
                "VALUES (?, ?, ?, 'test', 'active', ?, ?)",
                (cid, CUST_ID, f"Contact {i}", _NOW, _NOW),
            )
            conn.execute(
                "INSERT INTO user_contacts (id, user_id, contact_id, visibility, is_owner, created_at, updated_at) "
                "VALUES (?, ?, ?, 'public', 1, ?, ?)",
                (str(uuid.uuid4()), USER_ID, cid, _NOW, _NOW),
            )
            conn.execute(
                "INSERT INTO contact_identifiers (id, contact_id, type, value, is_primary, is_current, created_at, updated_at) "
                "VALUES (?, ?, 'email', ?, 1, 1, ?, ?)",
                (str(uuid.uuid4()), cid, f"contact{i}@test.com", _NOW, _NOW),
            )


def _seed_companies(n=3):
    with get_connection() as conn:
        for i in range(n):
            co_id = f"company-{i}"
            conn.execute(
                "INSERT INTO companies (id, customer_id, name, domain, industry, status, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, 'active', ?, ?)",
                (co_id, CUST_ID, f"Company {i}", f"company{i}.com", "Tech", _NOW, _NOW),
            )
            conn.execute(
                "INSERT INTO user_companies (id, user_id, company_id, visibility, is_owner, created_at, updated_at) "
                "VALUES (?, ?, ?, 'public', 1, ?, ?)",
                (str(uuid.uuid4()), USER_ID, co_id, _NOW, _NOW),
            )


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

class TestHealth:
    def test_health(self, client):
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"


# ---------------------------------------------------------------------------
# Entity Registry
# ---------------------------------------------------------------------------

class TestEntityRegistry:
    def test_entity_types(self, client):
        resp = client.get("/api/v1/entity-types")
        assert resp.status_code == 200
        data = resp.json()
        assert "contact" in data
        assert "company" in data
        assert "conversation" in data
        assert "event" in data
        assert "communication" in data

    def test_entity_type_fields(self, client):
        resp = client.get("/api/v1/entity-types")
        data = resp.json()
        contact = data["contact"]
        assert contact["label"] == "Contacts"
        assert "name" in contact["fields"]
        assert "email" in contact["fields"]
        name_field = contact["fields"]["name"]
        assert name_field["type"] == "text"
        assert name_field["sortable"] is True
        assert name_field["editable"] is True
        assert "sql" not in name_field  # sql should not be exposed

    def test_default_columns_present(self, client):
        data = client.get("/api/v1/entity-types").json()
        assert "name" in data["contact"]["default_columns"]
        assert "email" in data["contact"]["default_columns"]


# ---------------------------------------------------------------------------
# Views
# ---------------------------------------------------------------------------

class TestViews:
    def test_list_views_creates_defaults(self, client):
        resp = client.get("/api/v1/views?entity_type=contact")
        assert resp.status_code == 200
        views = resp.json()
        assert len(views) >= 1
        assert views[0]["name"] == "All Contacts"

    def test_view_detail(self, client):
        views = client.get("/api/v1/views?entity_type=contact").json()
        view_id = views[0]["id"]
        resp = client.get(f"/api/v1/views/{view_id}")
        assert resp.status_code == 200
        view = resp.json()
        assert view["id"] == view_id
        assert "columns" in view
        assert len(view["columns"]) > 0

    def test_view_not_found(self, client):
        resp = client.get("/api/v1/views/nonexistent")
        assert resp.status_code == 404

    def test_view_data_empty(self, client):
        views = client.get("/api/v1/views?entity_type=contact").json()
        view_id = views[0]["id"]
        resp = client.get(f"/api/v1/views/{view_id}/data")
        assert resp.status_code == 200
        data = resp.json()
        assert data["rows"] == []
        assert data["total"] == 0
        assert data["page"] == 1

    def test_view_data_with_rows(self, client):
        _seed_contacts(5)
        views = client.get("/api/v1/views?entity_type=contact").json()
        view_id = views[0]["id"]
        resp = client.get(f"/api/v1/views/{view_id}/data")
        data = resp.json()
        assert data["total"] == 5
        assert len(data["rows"]) == 5
        # Each row should have an id
        assert all("id" in r for r in data["rows"])
        # Each row should have a name field
        assert all("name" in r for r in data["rows"])

    def test_view_data_search(self, client):
        _seed_contacts(5)
        views = client.get("/api/v1/views?entity_type=contact").json()
        view_id = views[0]["id"]
        resp = client.get(f"/api/v1/views/{view_id}/data?search=Contact 2")
        data = resp.json()
        assert data["total"] == 1
        assert data["rows"][0]["name"] == "Contact 2"

    def test_view_data_sort(self, client):
        _seed_contacts(5)
        views = client.get("/api/v1/views?entity_type=contact").json()
        view_id = views[0]["id"]
        resp = client.get(f"/api/v1/views/{view_id}/data?sort=name&sort_direction=desc")
        data = resp.json()
        names = [r["name"] for r in data["rows"]]
        assert names == sorted(names, reverse=True)

    def test_view_data_pagination(self, client):
        _seed_contacts(5)
        views = client.get("/api/v1/views?entity_type=contact").json()
        view_id = views[0]["id"]
        # Get with per_page=2 by using page parameter
        resp = client.get(f"/api/v1/views/{view_id}/data?page=1")
        data = resp.json()
        assert data["per_page"] == 50  # default
        assert data["total"] == 5

    def test_company_view(self, client):
        _seed_companies(3)
        views = client.get("/api/v1/views?entity_type=company").json()
        view_id = views[0]["id"]
        resp = client.get(f"/api/v1/views/{view_id}/data")
        data = resp.json()
        assert data["total"] == 3


# ---------------------------------------------------------------------------
# Contact Detail
# ---------------------------------------------------------------------------

class TestContactDetail:
    def test_contact_detail(self, client):
        _seed_contacts(1)
        resp = client.get("/api/v1/contacts/contact-0")
        assert resp.status_code == 200
        data = resp.json()
        assert data["identity"]["name"] == "Contact 0"
        assert "contact0@test.com" in data["identity"]["emails"]
        assert "context" in data
        assert "timeline" in data

    def test_contact_not_found(self, client):
        resp = client.get("/api/v1/contacts/nonexistent")
        assert resp.status_code == 404

    def test_contact_detail_identity_structure(self, client):
        _seed_contacts(1)
        data = client.get("/api/v1/contacts/contact-0").json()
        identity = data["identity"]
        assert "name" in identity
        assert "emails" in identity
        assert "phones" in identity
        assert "addresses" in identity

    def test_contact_detail_context_structure(self, client):
        _seed_contacts(1)
        data = client.get("/api/v1/contacts/contact-0").json()
        context = data["context"]
        assert "affiliations" in context
        assert "relationships" in context


# ---------------------------------------------------------------------------
# Company Detail
# ---------------------------------------------------------------------------

class TestCompanyDetail:
    def test_company_detail(self, client):
        _seed_companies(1)
        resp = client.get("/api/v1/companies/company-0")
        assert resp.status_code == 200
        data = resp.json()
        assert data["identity"]["name"] == "Company 0"

    def test_company_not_found(self, client):
        resp = client.get("/api/v1/companies/nonexistent")
        assert resp.status_code == 404

    def test_company_detail_structure(self, client):
        _seed_companies(1)
        data = client.get("/api/v1/companies/company-0").json()
        assert "identity" in data
        assert "context" in data
        assert "timeline" in data
        assert data["identity"]["domain"] == "company0.com"


# ---------------------------------------------------------------------------
# Conversation Detail
# ---------------------------------------------------------------------------

class TestConversationDetail:
    def test_conversation_not_found(self, client):
        resp = client.get("/api/v1/conversations/nonexistent")
        assert resp.status_code == 404

    def test_conversation_detail(self, client):
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO conversations (id, customer_id, title, status, created_at, updated_at) "
                "VALUES ('conv-1', ?, 'Test Thread', 'open', ?, ?)",
                (CUST_ID, _NOW, _NOW),
            )
        resp = client.get("/api/v1/conversations/conv-1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["identity"]["name"] == "Test Thread"


# ---------------------------------------------------------------------------
# Event Detail
# ---------------------------------------------------------------------------

class TestEventDetail:
    def test_event_not_found(self, client):
        resp = client.get("/api/v1/events/nonexistent")
        assert resp.status_code == 404

    def test_event_detail(self, client):
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO events (id, title, event_type, start_datetime, status, source, created_at, updated_at) "
                "VALUES ('evt-1', 'Team Standup', 'meeting', ?, 'confirmed', 'google', ?, ?)",
                (_NOW, _NOW, _NOW),
            )
        resp = client.get("/api/v1/events/evt-1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["identity"]["name"] == "Team Standup"


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

class TestSearch:
    def test_search_contacts(self, client):
        _seed_contacts(3)
        resp = client.get("/api/v1/search?q=Contact 1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        names = [r["name"] for r in data["results"]]
        assert "Contact 1" in names

    def test_search_companies(self, client):
        _seed_companies(3)
        resp = client.get("/api/v1/search?q=Company")
        data = resp.json()
        co_results = [r for r in data["results"] if r["entity_type"] == "company"]
        assert len(co_results) == 3

    def test_search_minimum_length(self, client):
        resp = client.get("/api/v1/search?q=a")
        assert resp.status_code == 422  # FastAPI validation error

    def test_search_by_email(self, client):
        _seed_contacts(3)
        resp = client.get("/api/v1/search?q=contact1@test.com")
        data = resp.json()
        assert data["total"] >= 1
        assert any(r["id"] == "contact-1" for r in data["results"])

    def test_search_empty_results(self, client):
        resp = client.get("/api/v1/search?q=zzzznonexistent")
        data = resp.json()
        assert data["total"] == 0
        assert data["results"] == []
