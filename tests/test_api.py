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
        groups = data["groups"]
        contact_group = next(g for g in groups if g["entity_type"] == "contact")
        names = [r["name"] for r in contact_group["results"]]
        assert "Contact 1" in names

    def test_search_companies(self, client):
        _seed_companies(3)
        resp = client.get("/api/v1/search?q=Company")
        data = resp.json()
        co_group = next(g for g in data["groups"] if g["entity_type"] == "company")
        assert co_group["total"] == 3
        assert len(co_group["results"]) == 3

    def test_search_minimum_length(self, client):
        resp = client.get("/api/v1/search?q=a")
        assert resp.status_code == 422  # FastAPI validation error

    def test_search_by_email(self, client):
        _seed_contacts(3)
        resp = client.get("/api/v1/search?q=contact1@test.com")
        data = resp.json()
        assert data["total"] >= 1
        contact_group = next(g for g in data["groups"] if g["entity_type"] == "contact")
        assert any(r["id"] == "contact-1" for r in contact_group["results"])

    def test_search_empty_results(self, client):
        resp = client.get("/api/v1/search?q=zzzznonexistent")
        data = resp.json()
        assert data["total"] == 0
        assert data["groups"] == []

    def test_search_grouped_response_format(self, client):
        """Verify grouped response structure with groups/total."""
        _seed_contacts(2)
        _seed_companies(2)
        resp = client.get("/api/v1/search?q=Contact")
        data = resp.json()
        assert "groups" in data
        assert "total" in data
        for group in data["groups"]:
            assert "entity_type" in group
            assert "label" in group
            assert "total" in group
            assert "results" in group
            for item in group["results"]:
                assert "id" in item
                assert "name" in item

    def test_search_limit_param(self, client):
        """Limit controls max results per group."""
        _seed_contacts(5)
        resp = client.get("/api/v1/search?q=Contact&limit=2")
        data = resp.json()
        contact_group = next(g for g in data["groups"] if g["entity_type"] == "contact")
        assert len(contact_group["results"]) == 2
        assert contact_group["total"] == 5

    def test_search_entity_type_filter(self, client):
        """entity_type param filters to single entity type."""
        _seed_contacts(3)
        _seed_companies(3)
        resp = client.get("/api/v1/search?q=Co&entity_type=company")
        data = resp.json()
        assert all(g["entity_type"] == "company" for g in data["groups"])

    def test_search_empty_groups_omitted(self, client):
        """Groups with zero results are not included."""
        _seed_contacts(2)
        resp = client.get("/api/v1/search?q=Contact")
        data = resp.json()
        for group in data["groups"]:
            assert group["total"] > 0
            assert len(group["results"]) > 0

    def test_search_conversations(self, client):
        """Search finds conversations by title."""
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO conversations (id, customer_id, title, status, created_at, updated_at) "
                "VALUES (?, ?, 'Budget Planning Q3', 'active', ?, ?)",
                ("conv-search-1", CUST_ID, _NOW, _NOW),
            )
        resp = client.get("/api/v1/search?q=Budget")
        data = resp.json()
        conv_group = next(g for g in data["groups"] if g["entity_type"] == "conversation")
        assert conv_group["total"] == 1
        assert conv_group["results"][0]["name"] == "Budget Planning Q3"

    def test_search_events(self, client):
        """Search finds events by title."""
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO provider_accounts (id, customer_id, provider, email_address, is_active, created_at, updated_at) "
                "VALUES (?, ?, 'google', 'test@test.com', 1, ?, ?)",
                ("pa-search-1", CUST_ID, _NOW, _NOW),
            )
            conn.execute(
                "INSERT INTO events (id, title, location, start_datetime, end_datetime, "
                "event_type, source, account_id, created_at, updated_at) "
                "VALUES (?, 'Team Standup', 'Room 42', ?, ?, 'meeting', 'manual', ?, ?, ?)",
                ("evt-search-1", _NOW, _NOW, "pa-search-1", _NOW, _NOW),
            )
        resp = client.get("/api/v1/search?q=Standup")
        data = resp.json()
        evt_group = next(g for g in data["groups"] if g["entity_type"] == "event")
        assert evt_group["total"] == 1
        assert evt_group["results"][0]["subtitle"] == "Room 42"

    def test_search_projects(self, client):
        """Search finds projects by name."""
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO projects (id, customer_id, name, status, created_at, updated_at) "
                "VALUES (?, ?, 'Website Redesign', 'active', ?, ?)",
                ("proj-search-1", CUST_ID, _NOW, _NOW),
            )
        resp = client.get("/api/v1/search?q=Redesign")
        data = resp.json()
        proj_group = next(g for g in data["groups"] if g["entity_type"] == "project")
        assert proj_group["total"] == 1
        assert proj_group["results"][0]["name"] == "Website Redesign"

    def test_search_notes(self, client):
        """Search finds notes by title."""
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO notes (id, customer_id, title, created_by, updated_by, created_at, updated_at) "
                "VALUES (?, ?, 'Meeting Notes Jan', ?, ?, ?, ?)",
                ("note-search-1", CUST_ID, USER_ID, USER_ID, _NOW, _NOW),
            )
        resp = client.get("/api/v1/search?q=Meeting Notes")
        data = resp.json()
        note_group = next(g for g in data["groups"] if g["entity_type"] == "note")
        assert note_group["total"] == 1
        assert note_group["results"][0]["name"] == "Meeting Notes Jan"


# ---------------------------------------------------------------------------
# View CRUD Mutations
# ---------------------------------------------------------------------------

class TestViewCRUD:
    def test_create_view(self, client):
        resp = client.post("/api/v1/views", json={
            "entity_type": "contact",
            "name": "My Custom View",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "My Custom View"
        assert data["is_default"] == 0
        assert "columns" in data
        assert len(data["columns"]) > 0

    def test_create_view_missing_fields(self, client):
        resp = client.post("/api/v1/views", json={"entity_type": "contact"})
        assert resp.status_code == 400

    def test_update_view(self, client):
        # Create a view first
        create_resp = client.post("/api/v1/views", json={
            "entity_type": "contact",
            "name": "Before Rename",
        })
        view_id = create_resp.json()["id"]

        resp = client.put(f"/api/v1/views/{view_id}", json={
            "name": "After Rename",
            "per_page": 25,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "After Rename"
        assert data["per_page"] == 25

    def test_update_view_columns(self, client):
        create_resp = client.post("/api/v1/views", json={
            "entity_type": "contact",
            "name": "Column Test",
        })
        view_id = create_resp.json()["id"]

        resp = client.put(f"/api/v1/views/{view_id}/columns", json={
            "columns": ["name", "email"],
        })
        assert resp.status_code == 200
        data = resp.json()
        keys = [c["field_key"] for c in data["columns"]]
        assert "name" in keys
        assert "email" in keys

    def test_update_view_columns_with_deps(self, client):
        """company_name field has link /companies/{company_id}, so company_id should auto-append."""
        create_resp = client.post("/api/v1/views", json={
            "entity_type": "contact",
            "name": "Deps Test",
        })
        view_id = create_resp.json()["id"]

        resp = client.put(f"/api/v1/views/{view_id}/columns", json={
            "columns": ["name", "company_name"],
        })
        assert resp.status_code == 200
        keys = [c["field_key"] for c in resp.json()["columns"]]
        assert "company_id" in keys  # auto-appended hidden dep

    def test_update_view_columns_dict_format(self, client):
        create_resp = client.post("/api/v1/views", json={
            "entity_type": "contact",
            "name": "Dict Format",
        })
        view_id = create_resp.json()["id"]

        resp = client.put(f"/api/v1/views/{view_id}/columns", json={
            "columns": [
                {"key": "name", "label": "Full Name", "width": 200},
                {"key": "email"},
            ],
        })
        assert resp.status_code == 200
        cols = resp.json()["columns"]
        name_col = next(c for c in cols if c["field_key"] == "name")
        assert name_col["label_override"] == "Full Name"
        assert name_col["width_px"] == 200

    def test_update_view_filters(self, client):
        create_resp = client.post("/api/v1/views", json={
            "entity_type": "contact",
            "name": "Filter Test",
        })
        view_id = create_resp.json()["id"]

        resp = client.put(f"/api/v1/views/{view_id}/filters", json={
            "filters": [
                {"field_key": "status", "operator": "equals", "value": "active"},
            ],
        })
        assert resp.status_code == 200
        filters = resp.json()["filters"]
        assert len(filters) == 1
        assert filters[0]["field_key"] == "status"
        assert filters[0]["operator"] == "equals"
        assert filters[0]["value"] == "active"

    def test_delete_view(self, client):
        create_resp = client.post("/api/v1/views", json={
            "entity_type": "contact",
            "name": "To Delete",
        })
        view_id = create_resp.json()["id"]

        resp = client.delete(f"/api/v1/views/{view_id}")
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

        # Verify it's gone
        resp = client.get(f"/api/v1/views/{view_id}")
        assert resp.status_code == 404

    def test_delete_default_view_fails(self, client):
        # List views to create defaults
        views = client.get("/api/v1/views?entity_type=contact").json()
        default_view = next(v for v in views if v["is_default"])

        resp = client.delete(f"/api/v1/views/{default_view['id']}")
        assert resp.status_code == 400
        assert "default" in resp.json()["error"].lower()

    def test_duplicate_view(self, client):
        create_resp = client.post("/api/v1/views", json={
            "entity_type": "contact",
            "name": "Original",
        })
        view_id = create_resp.json()["id"]

        resp = client.post(f"/api/v1/views/{view_id}/duplicate", json={
            "name": "My Copy",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "My Copy"
        assert data["id"] != view_id
        # Should have same columns
        orig_cols = create_resp.json()["columns"]
        assert len(data["columns"]) == len(orig_cols)

    def test_cell_edit_success(self, client):
        _seed_contacts(1)
        resp = client.post("/api/v1/cell-edit", json={
            "entity_type": "contact",
            "entity_id": "contact-0",
            "field_key": "name",
            "value": "New Name",
        })
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

    def test_cell_edit_invalid_field(self, client):
        _seed_contacts(1)
        resp = client.post("/api/v1/cell-edit", json={
            "entity_type": "contact",
            "entity_id": "contact-0",
            "field_key": "nonexistent",
            "value": "test",
        })
        assert resp.status_code == 400
        assert resp.json()["ok"] is False

    def test_view_data_with_extra_filters(self, client):
        _seed_contacts(5)
        views = client.get("/api/v1/views?entity_type=contact").json()
        view_id = views[0]["id"]

        import json as _json
        extra = _json.dumps([{"field_key": "status", "operator": "equals", "value": "active"}])
        resp = client.get(f"/api/v1/views/{view_id}/data?filters={extra}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 5  # all seeded contacts are 'active'


# ---------------------------------------------------------------------------
# Layout Overrides
# ---------------------------------------------------------------------------

class TestLayoutOverrides:
    def _get_view_id(self, client):
        views = client.get("/api/v1/views?entity_type=contact").json()
        return views[0]["id"]

    def test_list_overrides_empty(self, client):
        view_id = self._get_view_id(client)
        resp = client.get(f"/api/v1/views/{view_id}/layout-overrides")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_create_override(self, client):
        view_id = self._get_view_id(client)
        resp = client.put(
            f"/api/v1/views/{view_id}/layout-overrides/standard",
            json={
                "splitter_pct": 35.0,
                "density": "compact",
                "column_overrides": {"name": {"width_pct": 25}},
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["display_tier"] == "standard"
        assert data["splitter_pct"] == 35.0
        assert data["density"] == "compact"
        assert data["column_overrides"] == {"name": {"width_pct": 25}}

    def test_update_override(self, client):
        view_id = self._get_view_id(client)
        # Create
        client.put(
            f"/api/v1/views/{view_id}/layout-overrides/spacious",
            json={"splitter_pct": 30.0},
        )
        # Update
        resp = client.put(
            f"/api/v1/views/{view_id}/layout-overrides/spacious",
            json={"splitter_pct": 45.0, "density": "comfortable"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["splitter_pct"] == 45.0
        assert data["density"] == "comfortable"

    def test_list_overrides_after_create(self, client):
        view_id = self._get_view_id(client)
        client.put(
            f"/api/v1/views/{view_id}/layout-overrides/standard",
            json={"splitter_pct": 30.0},
        )
        client.put(
            f"/api/v1/views/{view_id}/layout-overrides/spacious",
            json={"splitter_pct": 40.0},
        )
        resp = client.get(f"/api/v1/views/{view_id}/layout-overrides")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        tiers = {d["display_tier"] for d in data}
        assert tiers == {"spacious", "standard"}

    def test_delete_single_override(self, client):
        view_id = self._get_view_id(client)
        client.put(
            f"/api/v1/views/{view_id}/layout-overrides/standard",
            json={"splitter_pct": 30.0},
        )
        resp = client.delete(f"/api/v1/views/{view_id}/layout-overrides/standard")
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

        # Verify it's gone
        overrides = client.get(f"/api/v1/views/{view_id}/layout-overrides").json()
        assert len(overrides) == 0

    def test_delete_nonexistent_override(self, client):
        view_id = self._get_view_id(client)
        resp = client.delete(f"/api/v1/views/{view_id}/layout-overrides/ultra_wide")
        assert resp.status_code == 404

    def test_delete_all_overrides(self, client):
        view_id = self._get_view_id(client)
        client.put(
            f"/api/v1/views/{view_id}/layout-overrides/standard",
            json={"splitter_pct": 30.0},
        )
        client.put(
            f"/api/v1/views/{view_id}/layout-overrides/spacious",
            json={"splitter_pct": 40.0},
        )
        resp = client.delete(f"/api/v1/views/{view_id}/layout-overrides")
        assert resp.status_code == 200
        assert resp.json()["ok"] is True
        assert resp.json()["deleted"] == 2

        # Verify all gone
        overrides = client.get(f"/api/v1/views/{view_id}/layout-overrides").json()
        assert len(overrides) == 0

    def test_invalid_display_tier(self, client):
        view_id = self._get_view_id(client)
        resp = client.put(
            f"/api/v1/views/{view_id}/layout-overrides/invalid_tier",
            json={"splitter_pct": 30.0},
        )
        assert resp.status_code == 400
        assert "Invalid display_tier" in resp.json()["error"]

    def test_column_overrides_json_roundtrip(self, client):
        view_id = self._get_view_id(client)
        overrides = {
            "name": {"width_pct": 25, "alignment": "left"},
            "email": {"width_pct": 20},
            "status": {"hidden": True},
        }
        client.put(
            f"/api/v1/views/{view_id}/layout-overrides/standard",
            json={"column_overrides": overrides},
        )
        resp = client.get(f"/api/v1/views/{view_id}/layout-overrides")
        data = resp.json()
        assert len(data) == 1
        assert data[0]["column_overrides"] == overrides

    def test_view_not_found(self, client):
        resp = client.get("/api/v1/views/nonexistent/layout-overrides")
        assert resp.status_code == 404

    def test_view_settings_agi_fields(self, client):
        """Test that AGI view settings can be updated via the view update endpoint."""
        create_resp = client.post("/api/v1/views", json={
            "entity_type": "contact",
            "name": "AGI Test View",
        })
        view_id = create_resp.json()["id"]

        resp = client.put(f"/api/v1/views/{view_id}", json={
            "preview_panel_size": "large",
            "auto_density": 0,
            "column_auto_sizing": 1,
            "column_demotion": 0,
            "primary_identifier_field": "name",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["preview_panel_size"] == "large"
        assert data["auto_density"] == 0
        assert data["column_auto_sizing"] == 1
        assert data["column_demotion"] == 0
        assert data["primary_identifier_field"] == "name"

    def test_view_settings_defaults(self, client):
        """New views should have AGI defaults."""
        views = client.get("/api/v1/views?entity_type=contact").json()
        view_id = views[0]["id"]
        resp = client.get(f"/api/v1/views/{view_id}")
        data = resp.json()
        assert data["preview_panel_size"] == "medium"
        assert data["auto_density"] == 1
        assert data["column_auto_sizing"] == 1
        assert data["column_demotion"] == 1


# ---------------------------------------------------------------------------
# Contact Merge
# ---------------------------------------------------------------------------

class TestContactMerge:
    def test_merge_preview(self, client):
        _seed_contacts(2)
        resp = client.post("/api/v1/contacts/merge-preview", json={
            "contact_ids": ["contact-0", "contact-1"],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "contacts" in data
        assert len(data["contacts"]) == 2
        assert "conflicts" in data
        assert "totals" in data
        assert data["totals"]["identifiers"] == 2

    def test_merge_preview_insufficient(self, client):
        _seed_contacts(1)
        resp = client.post("/api/v1/contacts/merge-preview", json={
            "contact_ids": ["contact-0"],
        })
        assert resp.status_code == 400
        assert "At least two" in resp.json()["error"]

    def test_merge_confirm(self, client):
        _seed_contacts(2)
        resp = client.post("/api/v1/contacts/merge", json={
            "surviving_id": "contact-0",
            "absorbed_ids": ["contact-1"],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["surviving_id"] == "contact-0"
        assert data["absorbed_ids"] == ["contact-1"]
        assert "identifiers_transferred" in data
        # Absorbed contact should be deleted
        detail_resp = client.get("/api/v1/contacts/contact-1")
        assert detail_resp.status_code == 404

    def test_merge_confirm_invalid(self, client):
        _seed_contacts(1)
        resp = client.post("/api/v1/contacts/merge", json={
            "surviving_id": "nonexistent",
            "absorbed_ids": ["contact-0"],
        })
        assert resp.status_code == 400
        assert "not found" in resp.json()["error"].lower()


# ---------------------------------------------------------------------------
# Company Merge
# ---------------------------------------------------------------------------

class TestCompanyMerge:
    def test_merge_preview(self, client):
        _seed_companies(2)
        resp = client.post("/api/v1/companies/merge-preview", json={
            "company_ids": ["company-0", "company-1"],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "companies" in data
        assert len(data["companies"]) == 2
        assert "conflicts" in data
        assert "totals" in data
        assert data["companies"][0]["name"] == "Company 0"

    def test_merge_preview_insufficient(self, client):
        _seed_companies(1)
        resp = client.post("/api/v1/companies/merge-preview", json={
            "company_ids": ["company-0"],
        })
        assert resp.status_code == 400
        assert "At least two" in resp.json()["error"]

    def test_merge_confirm(self, client):
        _seed_companies(2)
        resp = client.post("/api/v1/companies/merge", json={
            "surviving_id": "company-0",
            "absorbed_ids": ["company-1"],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["surviving_id"] == "company-0"
        assert data["absorbed_ids"] == ["company-1"]
        assert "contacts_reassigned" in data
        # Absorbed company should be deleted
        detail_resp = client.get("/api/v1/companies/company-1")
        assert detail_resp.status_code == 404

    def test_merge_confirm_invalid(self, client):
        _seed_companies(1)
        resp = client.post("/api/v1/companies/merge", json={
            "surviving_id": "nonexistent",
            "absorbed_ids": ["company-0"],
        })
        assert resp.status_code == 400
        assert "not found" in resp.json()["error"].lower()


# ---------------------------------------------------------------------------
# Create Contact
# ---------------------------------------------------------------------------

class TestCreateContact:
    def test_create_contact(self, client):
        resp = client.post("/api/v1/contacts", json={
            "name": "Jane Doe",
            "email": "jane@example.com",
            "source": "manual",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Jane Doe"
        assert data["source"] == "manual"
        assert "id" in data

        # Verify the contact is visible via detail endpoint
        detail = client.get(f"/api/v1/contacts/{data['id']}")
        assert detail.status_code == 200
        assert detail.json()["identity"]["name"] == "Jane Doe"
        assert "jane@example.com" in detail.json()["identity"]["emails"]

    def test_create_contact_missing_name(self, client):
        resp = client.post("/api/v1/contacts", json={"email": "no-name@test.com"})
        assert resp.status_code == 400
        assert "name" in resp.json()["error"].lower()


# ---------------------------------------------------------------------------
# Create Company
# ---------------------------------------------------------------------------

class TestCreateCompany:
    def test_create_company(self, client):
        resp = client.post("/api/v1/companies", json={
            "name": "Acme Corp",
            "domain": "acme.com",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Acme Corp"
        assert data["domain"] == "acme.com"
        assert "id" in data

        # Verify the company is visible via detail endpoint
        detail = client.get(f"/api/v1/companies/{data['id']}")
        assert detail.status_code == 200
        assert detail.json()["identity"]["name"] == "Acme Corp"

    def test_create_company_duplicate_name(self, client):
        client.post("/api/v1/companies", json={"name": "DupeCorp"})
        resp = client.post("/api/v1/companies", json={"name": "DupeCorp"})
        assert resp.status_code == 400
        assert "already exists" in resp.json()["error"]


# ---------------------------------------------------------------------------
# Settings: Profile
# ---------------------------------------------------------------------------

class TestSettingsProfile:
    def test_get_profile(self, client):
        resp = client.get("/api/v1/settings/profile")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == USER_ID
        assert data["email"] == "admin@test.com"
        assert data["role"] == "admin"
        assert "timezone" in data

    def test_update_profile(self, client):
        resp = client.put("/api/v1/settings/profile", json={
            "name": "New Name",
            "timezone": "US/Pacific",
            "start_of_week": "sunday",
            "date_format": "US",
        })
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

        # Verify the change
        resp2 = client.get("/api/v1/settings/profile")
        assert resp2.json()["name"] == "New Name"
        assert resp2.json()["timezone"] == "US/Pacific"
        assert resp2.json()["start_of_week"] == "sunday"
        assert resp2.json()["date_format"] == "US"

    def test_change_password_too_short(self, client):
        resp = client.put("/api/v1/settings/password", json={
            "current_password": "",
            "new_password": "short",
            "confirm_password": "short",
        })
        assert resp.status_code == 400
        assert "8 characters" in resp.json()["error"]

    def test_change_password_mismatch(self, client):
        resp = client.put("/api/v1/settings/password", json={
            "current_password": "",
            "new_password": "longenough",
            "confirm_password": "different1",
        })
        assert resp.status_code == 400
        assert "match" in resp.json()["error"].lower()

    def test_change_password_success(self, client):
        resp = client.put("/api/v1/settings/password", json={
            "current_password": "",
            "new_password": "newpassword1",
            "confirm_password": "newpassword1",
        })
        assert resp.status_code == 200
        assert resp.json()["ok"] is True


# ---------------------------------------------------------------------------
# Settings: System
# ---------------------------------------------------------------------------

class TestSettingsSystem:
    def test_get_system(self, client):
        resp = client.get("/api/v1/settings/system")
        assert resp.status_code == 200
        data = resp.json()
        assert "company_name" in data
        assert "sync_enabled" in data

    def test_update_system(self, client):
        resp = client.put("/api/v1/settings/system", json={
            "company_name": "Test Corp",
            "sync_enabled": "false",
        })
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

        resp2 = client.get("/api/v1/settings/system")
        assert resp2.json()["company_name"] == "Test Corp"
        assert resp2.json()["sync_enabled"] == "false"

    def test_system_admin_only(self, tmp_db, monkeypatch):
        """Non-admin users get 403 for system settings."""
        user_id = "user-nonadmin"
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO users "
                "(id, customer_id, email, name, role, is_active, created_at, updated_at) "
                "VALUES (?, ?, 'user@test.com', 'User', 'user', 1, ?, ?)",
                (user_id, CUST_ID, _NOW, _NOW),
            )
        monkeypatch.setattr(
            "poc.hierarchy.get_current_user",
            lambda: {"id": user_id, "email": "user@test.com", "name": "User",
                     "role": "user", "customer_id": CUST_ID},
        )
        from poc.web.app import create_app
        app = create_app()
        nonadmin = TestClient(app, raise_server_exceptions=False)

        assert nonadmin.get("/api/v1/settings/system").status_code == 403
        assert nonadmin.put("/api/v1/settings/system", json={}).status_code == 403
        assert nonadmin.get("/api/v1/settings/users").status_code == 403
        assert nonadmin.post("/api/v1/settings/users", json={}).status_code == 403


# ---------------------------------------------------------------------------
# Settings: Users
# ---------------------------------------------------------------------------

class TestSettingsUsers:
    def test_list_users(self, client):
        resp = client.get("/api/v1/settings/users")
        assert resp.status_code == 200
        users = resp.json()
        assert isinstance(users, list)
        assert len(users) >= 1
        # Ensure password_hash is stripped
        for u in users:
            assert "password_hash" not in u

    def test_create_user(self, client):
        resp = client.post("/api/v1/settings/users", json={
            "email": "new@test.com",
            "name": "New User",
            "role": "user",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == "new@test.com"
        assert data["name"] == "New User"
        assert "password_hash" not in data

    def test_create_user_duplicate(self, client):
        client.post("/api/v1/settings/users", json={
            "email": "dup@test.com", "name": "Dup", "role": "user",
        })
        resp = client.post("/api/v1/settings/users", json={
            "email": "dup@test.com", "name": "Dup 2", "role": "user",
        })
        assert resp.status_code == 400
        assert "already exists" in resp.json()["error"]

    def test_create_user_missing_email(self, client):
        resp = client.post("/api/v1/settings/users", json={
            "name": "No Email", "role": "user",
        })
        assert resp.status_code == 400

    def test_update_user(self, client):
        # Create a user first
        create_resp = client.post("/api/v1/settings/users", json={
            "email": "edit@test.com", "name": "Before", "role": "user",
        })
        user_id = create_resp.json()["id"]

        resp = client.put(f"/api/v1/settings/users/{user_id}", json={
            "name": "After", "role": "admin",
        })
        assert resp.status_code == 200
        assert resp.json()["name"] == "After"
        assert resp.json()["role"] == "admin"

    def test_toggle_user_active(self, client):
        create_resp = client.post("/api/v1/settings/users", json={
            "email": "toggle@test.com", "name": "Toggle", "role": "user",
        })
        user_id = create_resp.json()["id"]

        resp = client.post(f"/api/v1/settings/users/{user_id}/toggle-active")
        assert resp.status_code == 200
        assert resp.json()["is_active"] == 0

    def test_toggle_self_rejected(self, client):
        resp = client.post(f"/api/v1/settings/users/{USER_ID}/toggle-active")
        assert resp.status_code == 400
        assert "yourself" in resp.json()["error"].lower()

    def test_set_user_password(self, client):
        create_resp = client.post("/api/v1/settings/users", json={
            "email": "pwset@test.com", "name": "PW", "role": "user",
        })
        user_id = create_resp.json()["id"]

        resp = client.put(
            f"/api/v1/settings/users/{user_id}/password",
            json={"new_password": "longenough"},
        )
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

    def test_set_user_password_too_short(self, client):
        resp = client.put(
            f"/api/v1/settings/users/{USER_ID}/password",
            json={"new_password": "short"},
        )
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Settings: Accounts
# ---------------------------------------------------------------------------

class TestSettingsAccounts:
    def _seed_account(self):
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO provider_accounts "
                "(id, customer_id, provider, email_address, display_name, "
                "auth_token_path, is_active, created_at, updated_at) "
                "VALUES (?, ?, 'gmail', 'acct@test.com', NULL, '/tmp/token', 1, ?, ?)",
                ("acct-1", CUST_ID, _NOW, _NOW),
            )

    def test_list_accounts(self, client):
        self._seed_account()
        resp = client.get("/api/v1/settings/accounts")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        # Ensure sensitive fields stripped
        for a in data:
            assert "auth_token_path" not in a
            assert "refresh_token" not in a

    def test_update_account(self, client):
        self._seed_account()
        resp = client.put("/api/v1/settings/accounts/acct-1", json={
            "display_name": "My Account",
        })
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

    def test_toggle_account(self, client):
        self._seed_account()
        resp = client.post("/api/v1/settings/accounts/acct-1/toggle-active")
        assert resp.status_code == 200
        assert resp.json()["is_active"] == 0

        # Toggle back
        resp2 = client.post("/api/v1/settings/accounts/acct-1/toggle-active")
        assert resp2.json()["is_active"] == 1

    def test_update_nonexistent(self, client):
        resp = client.put("/api/v1/settings/accounts/fake-id", json={
            "display_name": "X",
        })
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Settings: Calendars
# ---------------------------------------------------------------------------

class TestSettingsCalendars:
    def _seed_account(self):
        """Insert a gmail provider_account + user_provider_accounts row."""
        with get_connection() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO provider_accounts "
                "(id, customer_id, provider, email_address, "
                "auth_token_path, is_active, created_at, updated_at) "
                "VALUES (?, ?, 'gmail', 'cal@test.com', '/tmp/token', 1, ?, ?)",
                ("cal-acct-1", CUST_ID, _NOW, _NOW),
            )
            conn.execute(
                "INSERT OR IGNORE INTO user_provider_accounts "
                "(user_id, account_id) VALUES (?, ?)",
                (USER_ID, "cal-acct-1"),
            )

    def test_list_calendars_empty(self, client):
        resp = client.get("/api/v1/settings/calendars")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_save_calendars_rich_format(self, client):
        self._seed_account()
        entries = [
            {"id": "cal-1", "summary": "Work Calendar"},
            {"id": "cal-2", "summary": "Personal"},
        ]
        resp = client.put("/api/v1/settings/calendars/cal-acct-1", json={
            "calendar_entries": entries,
        })
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

        # Verify list returns normalized {id, summary} entries
        resp = client.get("/api/v1/settings/calendars")
        assert resp.status_code == 200
        accounts = resp.json()
        acct = [a for a in accounts if a["id"] == "cal-acct-1"][0]
        assert len(acct["selected_calendars"]) == 2
        assert acct["selected_calendars"][0] == {"id": "cal-1", "summary": "Work Calendar"}
        assert acct["selected_calendars"][1] == {"id": "cal-2", "summary": "Personal"}

    def test_save_calendars_legacy_format_normalizes(self, client):
        """Old format (list of strings) is normalized to {id, summary} on read."""
        self._seed_account()
        resp = client.put("/api/v1/settings/calendars/cal-acct-1", json={
            "calendar_ids": ["cal-A", "cal-B"],
        })
        assert resp.status_code == 200

        resp = client.get("/api/v1/settings/calendars")
        acct = [a for a in resp.json() if a["id"] == "cal-acct-1"][0]
        # Legacy strings should get ID as fallback summary
        assert acct["selected_calendars"][0] == {"id": "cal-A", "summary": "cal-A"}
        assert acct["selected_calendars"][1] == {"id": "cal-B", "summary": "cal-B"}

    def test_remove_calendar(self, client):
        """Saving a subset of entries effectively removes calendars."""
        self._seed_account()
        # Save two calendars
        entries = [
            {"id": "cal-1", "summary": "Work"},
            {"id": "cal-2", "summary": "Personal"},
        ]
        client.put("/api/v1/settings/calendars/cal-acct-1", json={
            "calendar_entries": entries,
        })

        # Remove one by saving only the other
        resp = client.put("/api/v1/settings/calendars/cal-acct-1", json={
            "calendar_entries": [{"id": "cal-2", "summary": "Personal"}],
        })
        assert resp.status_code == 200

        resp = client.get("/api/v1/settings/calendars")
        acct = [a for a in resp.json() if a["id"] == "cal-acct-1"][0]
        assert len(acct["selected_calendars"]) == 1
        assert acct["selected_calendars"][0]["id"] == "cal-2"


# ---------------------------------------------------------------------------
# Settings: Roles
# ---------------------------------------------------------------------------

class TestSettingsRoles:
    def _seed_system_role(self):
        """Insert a system role for tests that need one."""
        with get_connection() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO contact_company_roles "
                "(id, customer_id, name, sort_order, is_system, "
                "created_by, updated_by, created_at, updated_at) "
                "VALUES (?, ?, 'Employee', 0, 1, NULL, NULL, ?, ?)",
                ("sys-role-employee", CUST_ID, _NOW, _NOW),
            )

    def test_list_roles(self, client):
        resp = client.get("/api/v1/settings/roles")
        assert resp.status_code == 200
        roles = resp.json()
        assert isinstance(roles, list)

    def test_create_role(self, client):
        resp = client.post("/api/v1/settings/roles", json={
            "name": "Consultant",
            "sort_order": 10,
        })
        assert resp.status_code == 200
        role = resp.json()
        assert role["name"] == "Consultant"
        assert role["sort_order"] == 10
        assert role["is_system"] == 0

        # Verify it shows in list
        resp = client.get("/api/v1/settings/roles")
        names = [r["name"] for r in resp.json()]
        assert "Consultant" in names

    def test_create_role_empty_name(self, client):
        resp = client.post("/api/v1/settings/roles", json={"name": "  "})
        assert resp.status_code == 400
        assert "required" in resp.json()["error"].lower()

    def test_create_role_duplicate(self, client):
        client.post("/api/v1/settings/roles", json={"name": "Temp Role"})
        resp = client.post("/api/v1/settings/roles", json={"name": "Temp Role"})
        assert resp.status_code == 409
        assert "already exists" in resp.json()["error"]

    def test_update_role(self, client):
        resp = client.post("/api/v1/settings/roles", json={
            "name": "OldName", "sort_order": 5,
        })
        role_id = resp.json()["id"]

        resp = client.put(f"/api/v1/settings/roles/{role_id}", json={
            "name": "NewName", "sort_order": 99,
        })
        assert resp.status_code == 200
        assert resp.json()["name"] == "NewName"
        assert resp.json()["sort_order"] == 99

    def test_update_system_role_rejected(self, client):
        self._seed_system_role()
        resp = client.put("/api/v1/settings/roles/sys-role-employee", json={
            "name": "Hacked",
        })
        assert resp.status_code == 400
        assert "system role" in resp.json()["error"].lower()

    def test_update_nonexistent_role(self, client):
        resp = client.put("/api/v1/settings/roles/no-such-id", json={
            "name": "X",
        })
        assert resp.status_code == 404

    def test_delete_role(self, client):
        resp = client.post("/api/v1/settings/roles", json={"name": "Deletable"})
        role_id = resp.json()["id"]

        resp = client.delete(f"/api/v1/settings/roles/{role_id}")
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

        # Verify it's gone
        resp = client.get("/api/v1/settings/roles")
        ids = [r["id"] for r in resp.json()]
        assert role_id not in ids

    def test_delete_system_role_rejected(self, client):
        self._seed_system_role()
        resp = client.delete("/api/v1/settings/roles/sys-role-employee")
        assert resp.status_code == 400
        assert "system role" in resp.json()["error"].lower()


# ---------------------------------------------------------------------------
# Settings: Reference Data
# ---------------------------------------------------------------------------

class TestSettingsReferenceData:
    def test_get_reference_data(self, client):
        resp = client.get("/api/v1/settings/reference-data")
        assert resp.status_code == 200
        data = resp.json()
        assert "timezones" in data
        assert isinstance(data["timezones"], list)
        assert len(data["timezones"]) > 0
        assert "countries" in data
        assert isinstance(data["countries"], list)
        assert data["countries"][0]["code"] == "US"
        assert "email_history_options" in data
        assert "roles" in data
        assert "google_oauth_configured" in data
        assert isinstance(data["google_oauth_configured"], bool)


# ---------------------------------------------------------------------------
# Communication Preview
# ---------------------------------------------------------------------------

def _seed_communication(
    comm_id="comm-1",
    channel="email",
    subject="Test Subject",
    cleaned_html="Hello world",
    search_text="Hello world",
    snippet="Hello world preview",
    sender_name="Alice",
    sender_address="alice@example.com",
    direction="inbound",
    is_read=0,
    is_archived=0,
    triage_result=None,
    duration_seconds=None,
    phone_number_from=None,
    phone_number_to=None,
):
    """Seed a communication row + provider_account (required FK)."""
    with get_connection() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO provider_accounts "
            "(id, customer_id, provider, email_address, is_active, created_at, updated_at) "
            "VALUES (?, ?, 'gmail', 'test@test.com', 1, ?, ?)",
            ("pa-comm", CUST_ID, _NOW, _NOW),
        )
        conn.execute(
            "INSERT INTO communications "
            "(id, account_id, channel, timestamp, cleaned_html, search_text, "
            "direction, source, "
            "sender_address, sender_name, subject, snippet, is_read, is_archived, "
            "triage_result, duration_seconds, phone_number_from, phone_number_to, "
            "created_at, updated_at) "
            "VALUES (?, 'pa-comm', ?, ?, ?, ?, ?, 'test', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (comm_id, channel, _NOW, cleaned_html, search_text, direction,
             sender_address,
             sender_name, subject, snippet, is_read, is_archived,
             triage_result, duration_seconds, phone_number_from, phone_number_to,
             _NOW, _NOW),
        )


class TestCommunicationPreview:
    def test_preview_not_found(self, client):
        resp = client.get("/api/v1/communications/nonexistent/preview")
        assert resp.status_code == 404

    def test_preview_email_basic(self, client):
        _seed_communication()
        resp = client.get("/api/v1/communications/comm-1/preview")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "comm-1"
        assert data["channel"] == "email"
        assert data["direction"] == "inbound"
        assert data["subject"] == "Test Subject"
        assert data["sender_name"] == "Alice"
        assert data["sender_address"] == "alice@example.com"
        assert data["cleaned_html"] == "Hello world"
        assert data["search_text"] == "Hello world"
        assert data["snippet"] == "Hello world preview"
        assert data["timestamp"] is not None

    def test_preview_participants_grouped_by_role(self, client):
        _seed_communication()
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO contacts (id, customer_id, name, source, status, created_at, updated_at) "
                "VALUES ('contact-bob', ?, 'Bob Contact', 'test', 'active', ?, ?)",
                (CUST_ID, _NOW, _NOW),
            )
            conn.execute(
                "INSERT INTO communication_participants (communication_id, address, name, contact_id, role) "
                "VALUES ('comm-1', 'alice@example.com', 'Alice', NULL, 'from')",
            )
            conn.execute(
                "INSERT INTO communication_participants (communication_id, address, name, contact_id, role) "
                "VALUES ('comm-1', 'bob@example.com', 'Bob', 'contact-bob', 'to')",
            )
            conn.execute(
                "INSERT INTO communication_participants (communication_id, address, name, contact_id, role) "
                "VALUES ('comm-1', 'carol@example.com', 'Carol', NULL, 'cc')",
            )
            conn.execute(
                "INSERT INTO communication_participants (communication_id, address, name, contact_id, role) "
                "VALUES ('comm-1', 'dave@example.com', NULL, NULL, 'bcc')",
            )
        resp = client.get("/api/v1/communications/comm-1/preview")
        data = resp.json()
        assert len(data["participants"]["from"]) == 1
        assert data["participants"]["from"][0]["name"] == "Alice"
        assert len(data["participants"]["to"]) == 1
        assert data["participants"]["to"][0]["contact_id"] == "contact-bob"
        assert len(data["participants"]["cc"]) == 1
        assert data["participants"]["cc"][0]["address"] == "carol@example.com"
        assert len(data["participants"]["bcc"]) == 1
        assert data["participants"]["bcc"][0]["address"] == "dave@example.com"

    def test_preview_no_participants(self, client):
        _seed_communication()
        resp = client.get("/api/v1/communications/comm-1/preview")
        data = resp.json()
        assert data["participants"]["from"] == []
        assert data["participants"]["to"] == []
        assert data["participants"]["cc"] == []
        assert data["participants"]["bcc"] == []

    def test_preview_with_attachments(self, client):
        _seed_communication()
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO attachments (id, communication_id, filename, mime_type, size_bytes, created_at) "
                "VALUES ('att-1', 'comm-1', 'report.pdf', 'application/pdf', 12345, ?)",
                (_NOW,),
            )
        resp = client.get("/api/v1/communications/comm-1/preview")
        data = resp.json()
        assert len(data["attachments"]) == 1
        att = data["attachments"][0]
        assert att["id"] == "att-1"
        assert att["filename"] == "report.pdf"
        assert att["mime_type"] == "application/pdf"
        assert att["size_bytes"] == 12345

    def test_preview_no_attachments(self, client):
        _seed_communication()
        data = client.get("/api/v1/communications/comm-1/preview").json()
        assert data["attachments"] == []

    def test_preview_triage_result(self, client):
        _seed_communication(triage_result="action_required")
        data = client.get("/api/v1/communications/comm-1/preview").json()
        assert data["triage_result"] == "action_required"

    def test_preview_triage_null(self, client):
        _seed_communication(triage_result=None)
        data = client.get("/api/v1/communications/comm-1/preview").json()
        assert data["triage_result"] is None

    def test_preview_boolean_fields(self, client):
        _seed_communication(is_read=1, is_archived=1)
        data = client.get("/api/v1/communications/comm-1/preview").json()
        assert data["is_read"] is True
        assert data["is_archived"] is True

    def test_preview_sms_channel(self, client):
        _seed_communication(
            channel="sms", subject=None, cleaned_html="Hey there",
            search_text="Hey there",
            phone_number_from="+15551234567",
        )
        data = client.get("/api/v1/communications/comm-1/preview").json()
        assert data["channel"] == "sms"
        assert data["subject"] is None
        assert data["cleaned_html"] == "Hey there"
        assert data["phone_number_from"] == "+15551234567"

    def test_preview_null_content(self, client):
        _seed_communication(cleaned_html=None, search_text=None, snippet="Just a snippet")
        data = client.get("/api/v1/communications/comm-1/preview").json()
        assert data["cleaned_html"] is None
        assert data["snippet"] == "Just a snippet"

    def test_preview_phone_with_duration(self, client):
        _seed_communication(
            channel="phone", subject=None, cleaned_html=None, search_text=None,
            duration_seconds=300,
            phone_number_from="+15551111111",
            phone_number_to="+15552222222",
        )
        data = client.get("/api/v1/communications/comm-1/preview").json()
        assert data["channel"] == "phone"
        assert data["duration_seconds"] == 300
        assert data["phone_number_from"] == "+15551111111"
        assert data["phone_number_to"] == "+15552222222"


# ---------------------------------------------------------------------------
# Communication Full View
# ---------------------------------------------------------------------------

def _seed_full_communication(
    comm_id="comm-full-1",
    channel="email",
    subject="Full View Subject",
    cleaned_html="<p>Full body</p>",
    search_text="Full body",
    original_text="Full body\n-- \nSignature",
    snippet="Full body preview",
    sender_name="Alice Sender",
    sender_address="alice@example.com",
    direction="inbound",
    source="synced",
    triage_result=None,
    ai_summary=None,
    ai_summarized_at=None,
    duration_seconds=None,
    phone_number_from=None,
    phone_number_to=None,
    provider_message_id=None,
    provider_thread_id=None,
    header_message_id=None,
):
    """Seed a communication for full view tests."""
    with get_connection() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO provider_accounts "
            "(id, customer_id, provider, email_address, is_active, created_at, updated_at) "
            "VALUES (?, ?, 'gmail', 'test@test.com', 1, ?, ?)",
            ("pa-full", CUST_ID, _NOW, _NOW),
        )
        conn.execute(
            "INSERT INTO communications "
            "(id, account_id, channel, timestamp, cleaned_html, search_text, original_text, "
            "direction, source, "
            "sender_address, sender_name, subject, snippet, is_read, is_archived, "
            "triage_result, ai_summary, ai_summarized_at, "
            "duration_seconds, phone_number_from, phone_number_to, "
            "provider_message_id, provider_thread_id, header_message_id, "
            "created_at, updated_at) "
            "VALUES (?, 'pa-full', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, "
            "?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (comm_id, channel, _NOW, cleaned_html, search_text, original_text,
             direction, source,
             sender_address, sender_name, subject, snippet,
             triage_result, ai_summary, ai_summarized_at,
             duration_seconds, phone_number_from, phone_number_to,
             provider_message_id, provider_thread_id, header_message_id,
             _NOW, _NOW),
        )


class TestCommunicationFullView:
    def test_full_not_found(self, client):
        resp = client.get("/api/v1/communications/nonexistent/full")
        assert resp.status_code == 404

    def test_full_email_basic(self, client):
        _seed_full_communication()
        resp = client.get("/api/v1/communications/comm-full-1/full")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "comm-full-1"
        assert data["channel"] == "email"
        assert data["direction"] == "inbound"
        assert data["subject"] == "Full View Subject"
        assert data["sender_name"] == "Alice Sender"
        assert data["sender_address"] == "alice@example.com"
        assert data["cleaned_html"] == "<p>Full body</p>"
        assert data["search_text"] == "Full body"
        assert data["snippet"] == "Full body preview"
        assert data["source"] == "synced"
        assert data["is_read"] is False
        assert data["is_archived"] is False
        assert data["timestamp"] is not None
        assert isinstance(data["participants"], list)
        assert isinstance(data["attachments"], list)
        assert isinstance(data["notes"], list)

    def test_full_participants_enriched(self, client):
        _seed_full_communication()
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO contacts (id, customer_id, name, source, status, created_at, updated_at) "
                "VALUES ('ct-enrich', ?, 'Bob Enriched', 'test', 'active', ?, ?)",
                (CUST_ID, _NOW, _NOW),
            )
            conn.execute(
                "INSERT INTO companies (id, customer_id, name, domain, created_at, updated_at) "
                "VALUES ('co-enrich', ?, 'Acme Corp', 'acme.com', ?, ?)",
                (CUST_ID, _NOW, _NOW),
            )
            conn.execute(
                "INSERT INTO contact_companies "
                "(id, contact_id, company_id, is_primary, is_current, title, created_at, updated_at) "
                "VALUES ('cc-enrich', 'ct-enrich', 'co-enrich', 1, 1, 'VP Engineering', ?, ?)",
                (_NOW, _NOW),
            )
            conn.execute(
                "INSERT INTO communication_participants "
                "(communication_id, address, name, contact_id, role) "
                "VALUES ('comm-full-1', 'bob@acme.com', 'Bob', 'ct-enrich', 'from')",
            )
        data = client.get("/api/v1/communications/comm-full-1/full").json()
        p = data["participants"][0]
        assert p["contact_name"] == "Bob Enriched"
        assert p["company_name"] == "Acme Corp"
        assert p["title"] == "VP Engineering"
        assert p["contact_id"] == "ct-enrich"
        assert p["is_account_owner"] is False  # NULL treated as False

    def test_full_participants_unresolved(self, client):
        _seed_full_communication()
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO communication_participants "
                "(communication_id, address, name, contact_id, role) "
                "VALUES ('comm-full-1', 'unknown@ext.com', 'Unknown Person', NULL, 'to')",
            )
        data = client.get("/api/v1/communications/comm-full-1/full").json()
        p = data["participants"][0]
        assert p["contact_name"] is None
        assert p["company_name"] is None
        assert p["title"] is None
        assert p["contact_id"] is None

    def test_full_conversation_assigned(self, client):
        _seed_full_communication()
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO conversations (id, customer_id, title, status, created_at, updated_at) "
                "VALUES ('conv-assign', ?, 'Lease Negotiation', 'active', ?, ?)",
                (CUST_ID, _NOW, _NOW),
            )
            conn.execute(
                "INSERT INTO conversation_communications (conversation_id, communication_id, created_at) "
                "VALUES ('conv-assign', 'comm-full-1', ?)",
                (_NOW,),
            )
        data = client.get("/api/v1/communications/comm-full-1/full").json()
        conv = data["conversation"]
        assert conv is not None
        assert conv["id"] == "conv-assign"
        assert conv["title"] == "Lease Negotiation"
        assert conv["status"] == "active"
        assert conv["communication_count"] == 1

    def test_full_conversation_none(self, client):
        _seed_full_communication()
        data = client.get("/api/v1/communications/comm-full-1/full").json()
        assert data["conversation"] is None

    def test_full_provider_account(self, client):
        _seed_full_communication()
        data = client.get("/api/v1/communications/comm-full-1/full").json()
        pa = data["provider_account"]
        assert pa is not None
        assert pa["id"] == "pa-full"
        assert pa["provider"] == "gmail"
        assert pa["email_address"] == "test@test.com"

    def test_full_ai_summary_present(self, client):
        _seed_full_communication(
            ai_summary="Key points discussed",
            ai_summarized_at=_NOW,
        )
        data = client.get("/api/v1/communications/comm-full-1/full").json()
        assert data["ai_summary"] == "Key points discussed"
        assert data["ai_summarized_at"] == _NOW

    def test_full_ai_summary_null(self, client):
        _seed_full_communication()
        data = client.get("/api/v1/communications/comm-full-1/full").json()
        assert data["ai_summary"] is None
        assert data["ai_summarized_at"] is None

    def test_full_attachments(self, client):
        _seed_full_communication()
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO attachments (id, communication_id, filename, mime_type, size_bytes, created_at) "
                "VALUES ('att-full-1', 'comm-full-1', 'contract.pdf', 'application/pdf', 54321, ?)",
                (_NOW,),
            )
            conn.execute(
                "INSERT INTO attachments (id, communication_id, filename, mime_type, size_bytes, created_at) "
                "VALUES ('att-full-2', 'comm-full-1', 'notes.txt', 'text/plain', 1024, ?)",
                (_NOW,),
            )
        data = client.get("/api/v1/communications/comm-full-1/full").json()
        assert len(data["attachments"]) == 2
        filenames = {a["filename"] for a in data["attachments"]}
        assert "contract.pdf" in filenames
        assert "notes.txt" in filenames

    def test_full_original_text(self, client):
        _seed_full_communication(original_text="Original content\n-- \nMy Signature")
        data = client.get("/api/v1/communications/comm-full-1/full").json()
        assert data["original_text"] == "Original content\n-- \nMy Signature"

    def test_full_provider_ids(self, client):
        _seed_full_communication(
            provider_message_id="msg-abc123",
            provider_thread_id="thread-xyz789",
            header_message_id="<abc@mail.gmail.com>",
        )
        data = client.get("/api/v1/communications/comm-full-1/full").json()
        assert data["provider_message_id"] == "msg-abc123"
        assert data["provider_thread_id"] == "thread-xyz789"
        assert data["header_message_id"] == "<abc@mail.gmail.com>"

    def test_full_timestamps(self, client):
        _seed_full_communication()
        data = client.get("/api/v1/communications/comm-full-1/full").json()
        assert data["created_at"] is not None
        assert data["updated_at"] is not None

    def test_full_notes_empty(self, client):
        _seed_full_communication()
        data = client.get("/api/v1/communications/comm-full-1/full").json()
        assert data["notes"] == []

    def test_full_triage_result(self, client):
        _seed_full_communication(triage_result="no_known_contacts")
        data = client.get("/api/v1/communications/comm-full-1/full").json()
        assert data["triage_result"] == "no_known_contacts"


# ===========================================================================
# Outbound Email API Tests
# ===========================================================================

ACCT_ID = "acct-api-test"


def _seed_provider_account():
    """Seed a provider account + user linkage for outbound tests."""
    with get_connection() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO provider_accounts "
            "(id, customer_id, provider, account_type, email_address, "
            "auth_token_path, is_active, created_at, updated_at) "
            "VALUES (?, ?, 'gmail', 'email', 'admin@test.com', '/tmp/token.json', 1, ?, ?)",
            (ACCT_ID, CUST_ID, _NOW, _NOW),
        )
        conn.execute(
            "INSERT OR IGNORE INTO user_provider_accounts "
            "(id, user_id, account_id, role, created_at) "
            "VALUES (?, ?, ?, 'owner', ?)",
            (str(uuid.uuid4()), USER_ID, ACCT_ID, _NOW),
        )


def _seed_outbound_communication():
    """Seed a communication for compose context tests."""
    comm_id = "comm-outbound-test"
    conv_id = "conv-outbound-test"
    _seed_provider_account()
    with get_connection() as conn:
        conn.execute(
            """INSERT OR IGNORE INTO communications
               (id, account_id, channel, timestamp, original_text, original_html,
                cleaned_html, search_text, direction, source,
                sender_address, sender_name, subject, snippet,
                provider_message_id, provider_thread_id,
                header_message_id, is_read, is_current, created_at, updated_at)
               VALUES (?, ?, 'email', ?, 'Hello', '<p>Hello</p>',
                       '<p>Hello</p>', 'Hello', 'inbound', 'auto_sync',
                       'alice@other.com', 'Alice', 'Test Thread', 'Hello...',
                       'gmail-msg-1', 'gmail-thread-1',
                       '<msg-1@mail.com>', 1, 1, ?, ?)""",
            (comm_id, ACCT_ID, _NOW, _NOW, _NOW),
        )
        conn.execute(
            "INSERT OR IGNORE INTO communication_participants "
            "(communication_id, address, name, role) VALUES (?, 'admin@test.com', 'Admin', 'to')",
            (comm_id,),
        )
        conn.execute(
            """INSERT OR IGNORE INTO conversations
               (id, customer_id, account_id, title, subject, status,
                communication_count, message_count, participant_count,
                first_activity_at, last_activity_at, created_at, updated_at)
               VALUES (?, ?, ?, 'Test Thread', 'Test Thread', 'active',
                       1, 1, 2, ?, ?, ?, ?)""",
            (conv_id, CUST_ID, ACCT_ID, _NOW, _NOW, _NOW, _NOW),
        )
        conn.execute(
            """INSERT OR IGNORE INTO conversation_communications
               (conversation_id, communication_id, assignment_source, confidence, reviewed, created_at)
               VALUES (?, ?, 'sync', 1.0, 1, ?)""",
            (conv_id, comm_id, _NOW),
        )
    return comm_id, conv_id


class TestOutboundEmailAPI:
    def test_create_draft(self, client):
        _seed_provider_account()
        resp = client.post("/api/v1/outbound-emails", json={
            "from_account_id": ACCT_ID,
            "to_addresses": [{"email": "bob@test.com", "name": "Bob"}],
            "subject": "API Draft Test",
            "body_json": "{}",
            "body_html": "<p>Hello</p>",
            "body_text": "Hello",
            "source_type": "manual",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "draft"
        assert data["subject"] == "API Draft Test"

    def test_create_draft_missing_fields(self, client):
        resp = client.post("/api/v1/outbound-emails", json={
            "subject": "Test",
        })
        assert resp.status_code == 400

    def test_list_drafts(self, client):
        _seed_provider_account()
        # Create two drafts
        for i in range(2):
            client.post("/api/v1/outbound-emails", json={
                "from_account_id": ACCT_ID,
                "to_addresses": [{"email": f"test{i}@test.com"}],
                "subject": f"Draft {i}",
                "body_json": "{}",
                "body_html": "",
                "body_text": "",
            })
        resp = client.get("/api/v1/outbound-emails/drafts")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_get_draft(self, client):
        _seed_provider_account()
        create_resp = client.post("/api/v1/outbound-emails", json={
            "from_account_id": ACCT_ID,
            "to_addresses": [{"email": "bob@test.com"}],
            "subject": "Get Test",
            "body_json": "{}",
            "body_html": "",
            "body_text": "",
        })
        draft_id = create_resp.json()["id"]
        resp = client.get(f"/api/v1/outbound-emails/{draft_id}")
        assert resp.status_code == 200
        assert resp.json()["subject"] == "Get Test"

    def test_update_draft(self, client):
        _seed_provider_account()
        create_resp = client.post("/api/v1/outbound-emails", json={
            "from_account_id": ACCT_ID,
            "to_addresses": [{"email": "bob@test.com"}],
            "subject": "Original",
            "body_json": "{}",
            "body_html": "",
            "body_text": "",
        })
        draft_id = create_resp.json()["id"]
        resp = client.patch(f"/api/v1/outbound-emails/{draft_id}", json={
            "subject": "Updated",
        })
        assert resp.status_code == 200
        assert resp.json()["subject"] == "Updated"

    def test_cancel_draft(self, client):
        _seed_provider_account()
        create_resp = client.post("/api/v1/outbound-emails", json={
            "from_account_id": ACCT_ID,
            "to_addresses": [{"email": "bob@test.com"}],
            "subject": "Cancel Me",
            "body_json": "{}",
            "body_html": "",
            "body_text": "",
        })
        draft_id = create_resp.json()["id"]
        resp = client.post(f"/api/v1/outbound-emails/{draft_id}/cancel")
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

        # Verify cancelled
        get_resp = client.get(f"/api/v1/outbound-emails/{draft_id}")
        assert get_resp.json()["status"] == "cancelled"

    def test_compose_context_reply(self, client):
        comm_id, conv_id = _seed_outbound_communication()
        resp = client.get(
            f"/api/v1/outbound-emails/compose-context"
            f"?communication_id={comm_id}&action=reply"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["to_addresses"]) > 0
        assert data["subject"].startswith("Re:")
        assert data["conversation_id"] == conv_id

    def test_compose_context_forward(self, client):
        comm_id, conv_id = _seed_outbound_communication()
        resp = client.get(
            f"/api/v1/outbound-emails/compose-context"
            f"?communication_id={comm_id}&action=forward"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["subject"].startswith("Fwd:")
        assert data["to_addresses"] == []

    def test_compose_context_invalid_action(self, client):
        resp = client.get(
            "/api/v1/outbound-emails/compose-context"
            "?communication_id=x&action=invalid"
        )
        assert resp.status_code == 400

    def test_resolve_sender(self, client):
        _seed_provider_account()
        resp = client.post("/api/v1/outbound-emails/resolve-sender", json={})
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == ACCT_ID

    def test_get_nonexistent_draft(self, client):
        resp = client.get("/api/v1/outbound-emails/nonexistent-id")
        assert resp.status_code == 404


class TestSignatureAPI:
    def test_create_signature(self, client):
        resp = client.post("/api/v1/signatures", json={
            "name": "My Sig",
            "body_json": '{"type":"doc"}',
            "body_html": "<p>Regards</p>",
            "is_default": True,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "My Sig"
        assert data["is_default"] == 1

    def test_list_signatures(self, client):
        client.post("/api/v1/signatures", json={
            "name": "Sig 1",
            "body_json": "{}",
            "body_html": "<p>1</p>",
        })
        client.post("/api/v1/signatures", json={
            "name": "Sig 2",
            "body_json": "{}",
            "body_html": "<p>2</p>",
        })
        resp = client.get("/api/v1/signatures")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_update_signature(self, client):
        create_resp = client.post("/api/v1/signatures", json={
            "name": "Original",
            "body_json": "{}",
            "body_html": "<p>Old</p>",
        })
        sig_id = create_resp.json()["id"]
        resp = client.patch(f"/api/v1/signatures/{sig_id}", json={
            "name": "Updated",
        })
        assert resp.status_code == 200
        assert resp.json()["name"] == "Updated"

    def test_delete_signature(self, client):
        create_resp = client.post("/api/v1/signatures", json={
            "name": "To Delete",
            "body_json": "{}",
            "body_html": "<p>X</p>",
        })
        sig_id = create_resp.json()["id"]
        resp = client.delete(f"/api/v1/signatures/{sig_id}")
        assert resp.status_code == 200

        get_resp = client.get(f"/api/v1/signatures/{sig_id}")
        assert get_resp.status_code == 404

    def test_create_signature_no_name(self, client):
        resp = client.post("/api/v1/signatures", json={
            "body_json": "{}",
            "body_html": "",
        })
        assert resp.status_code == 400
