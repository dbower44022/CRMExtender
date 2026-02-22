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
