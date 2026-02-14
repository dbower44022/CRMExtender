"""Tests for batch relationship creation from contacts list.

Covers: page load, type filtering, entity search, batch creation,
skip scenarios (self, duplicate), bidirectional pairing, results display,
edge cases (invalid type, missing target), and list page button.
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _uid():
    return str(uuid.uuid4())


def _create_contact(name="Alice", source="test", customer_id=CUST_ID):
    cid = _uid()
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO contacts "
            "(id, customer_id, name, source, status, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, 'active', ?, ?)",
            (cid, customer_id, name, source, _NOW, _NOW),
        )
        conn.execute(
            "INSERT INTO user_contacts "
            "(id, user_id, contact_id, visibility, is_owner, created_at, updated_at) "
            "VALUES (?, ?, ?, 'public', 1, ?, ?)",
            (_uid(), USER_ID, cid, _NOW, _NOW),
        )
    return cid


def _create_company(name="Acme Corp", customer_id=CUST_ID, domain=None):
    coid = _uid()
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO companies "
            "(id, customer_id, name, domain, status, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, 'active', ?, ?)",
            (coid, customer_id, name, domain, _NOW, _NOW),
        )
        conn.execute(
            "INSERT INTO user_companies "
            "(id, user_id, company_id, visibility, is_owner, created_at, updated_at) "
            "VALUES (?, ?, ?, 'public', 1, ?, ?)",
            (_uid(), USER_ID, coid, _NOW, _NOW),
        )
    return coid


def _add_email(contact_id, email):
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO contact_identifiers "
            "(id, contact_id, type, value, is_primary, created_at, updated_at) "
            "VALUES (?, ?, 'email', ?, 1, ?, ?)",
            (_uid(), contact_id, email, _NOW, _NOW),
        )


# ---------------------------------------------------------------------------
# Page load tests
# ---------------------------------------------------------------------------

class TestRelatePageLoad:
    def test_relate_page_loads_with_contacts(self, client, tmp_db):
        c1 = _create_contact("Alice")
        c2 = _create_contact("Bob")
        resp = client.get(f"/contacts/relate?ids={c1}&ids={c2}")
        assert resp.status_code == 200
        assert "Alice" in resp.text
        assert "Bob" in resp.text
        assert "Create Relationship" in resp.text

    def test_relate_redirects_on_no_ids(self, client, tmp_db):
        resp = client.get("/contacts/relate", follow_redirects=False)
        assert resp.status_code == 303
        assert "/contacts" in resp.headers["location"]

    def test_relate_redirects_on_invalid_ids(self, client, tmp_db):
        resp = client.get("/contacts/relate?ids=nonexistent", follow_redirects=False)
        assert resp.status_code == 303

    def test_relate_page_loads_default_types(self, client, tmp_db):
        c1 = _create_contact("Alice")
        resp = client.get(f"/contacts/relate?ids={c1}")
        assert resp.status_code == 200
        # Default contact→contact types should be pre-loaded (not "Select a target type above")
        assert "Knows" in resp.text
        assert "Select a target type above" not in resp.text

    def test_relate_search_input_has_name_q(self, client, tmp_db):
        c1 = _create_contact("Alice")
        resp = client.get(f"/contacts/relate?ids={c1}")
        assert 'name="q"' in resp.text


# ---------------------------------------------------------------------------
# Type filtering tests
# ---------------------------------------------------------------------------

class TestRelateTypeFiltering:
    def test_contact_to_contact_types(self, client, tmp_db):
        resp = client.get("/contacts/relate/types?to_entity_type=contact")
        assert resp.status_code == 200
        assert "Knows" in resp.text

    def test_contact_to_company_types(self, client, tmp_db):
        resp = client.get("/contacts/relate/types?to_entity_type=company")
        assert resp.status_code == 200
        assert "Affiliated with" in resp.text

    def test_no_types_for_invalid_entity(self, client, tmp_db):
        resp = client.get("/contacts/relate/types?to_entity_type=widget")
        assert resp.status_code == 200
        assert "No relationship types available" in resp.text


# ---------------------------------------------------------------------------
# Entity search tests
# ---------------------------------------------------------------------------

class TestRelateEntitySearch:
    def test_search_contacts(self, client, tmp_db):
        c1 = _create_contact("Alice")
        _add_email(c1, "alice@test.com")
        resp = client.get("/contacts/relate/search?q=Alice&target_entity_type=contact")
        assert resp.status_code == 200
        assert "Alice" in resp.text
        assert "alice@test.com" in resp.text

    def test_search_companies(self, client, tmp_db):
        _create_company("Acme Corp", domain="acme.com")
        resp = client.get("/contacts/relate/search?q=Acme&target_entity_type=company")
        assert resp.status_code == 200
        assert "Acme Corp" in resp.text
        assert "acme.com" in resp.text

    def test_search_excludes_selected_contacts(self, client, tmp_db):
        c1 = _create_contact("Alice")
        c2 = _create_contact("Bob")
        resp = client.get(
            f"/contacts/relate/search?q=Alice&target_entity_type=contact&contact_ids={c1}&contact_ids={c2}"
        )
        assert resp.status_code == 200
        assert "Alice" not in resp.text

    def test_search_empty_query(self, client, tmp_db):
        resp = client.get("/contacts/relate/search?q=&target_entity_type=contact")
        assert resp.status_code == 200

    def test_search_no_results(self, client, tmp_db):
        resp = client.get("/contacts/relate/search?q=nonexistent&target_entity_type=contact")
        assert resp.status_code == 200
        assert "No results found" in resp.text


# ---------------------------------------------------------------------------
# Batch creation tests
# ---------------------------------------------------------------------------

class TestRelateBatchCreation:
    def test_create_single_relationship(self, client, tmp_db):
        c1 = _create_contact("Alice")
        c2 = _create_contact("Bob")
        resp = client.post("/contacts/relate", data={
            "contact_ids": [c1],
            "relationship_type_id": "rt-knows",
            "target_entity_id": c2,
            "target_entity_type": "contact",
        })
        assert resp.status_code == 200
        assert "Created" in resp.text

        # Verify in database
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM relationships WHERE from_entity_id = ? AND to_entity_id = ?",
                (c1, c2),
            ).fetchall()
            assert len(rows) == 1

    def test_create_multiple_relationships(self, client, tmp_db):
        c1 = _create_contact("Alice")
        c2 = _create_contact("Bob")
        target = _create_contact("Charlie")
        resp = client.post("/contacts/relate", data={
            "contact_ids": [c1, c2],
            "relationship_type_id": "rt-knows",
            "target_entity_id": target,
            "target_entity_type": "contact",
        })
        assert resp.status_code == 200
        assert resp.text.count("Created") == 2

    def test_bidirectional_creates_paired_rows(self, client, tmp_db):
        c1 = _create_contact("Alice")
        c2 = _create_contact("Bob")
        resp = client.post("/contacts/relate", data={
            "contact_ids": [c1],
            "relationship_type_id": "rt-knows",
            "target_entity_id": c2,
            "target_entity_type": "contact",
        })
        assert resp.status_code == 200

        with get_connection() as conn:
            fwd = conn.execute(
                "SELECT * FROM relationships WHERE from_entity_id = ? AND to_entity_id = ?",
                (c1, c2),
            ).fetchone()
            rev = conn.execute(
                "SELECT * FROM relationships WHERE from_entity_id = ? AND to_entity_id = ?",
                (c2, c1),
            ).fetchone()
            assert fwd is not None
            assert rev is not None
            assert fwd["paired_relationship_id"] == rev["id"]
            assert rev["paired_relationship_id"] == fwd["id"]

    def test_contact_to_company_relationship(self, client, tmp_db):
        c1 = _create_contact("Alice")
        co = _create_company("Acme Corp")
        resp = client.post("/contacts/relate", data={
            "contact_ids": [c1],
            "relationship_type_id": "rt-affiliated",
            "target_entity_id": co,
            "target_entity_type": "company",
        })
        assert resp.status_code == 200
        assert "Created" in resp.text

        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM relationships WHERE from_entity_id = ? AND to_entity_id = ?",
                (c1, co),
            ).fetchone()
            assert row is not None
            assert row["to_entity_type"] == "company"


# ---------------------------------------------------------------------------
# Skip scenarios
# ---------------------------------------------------------------------------

class TestRelateSkipScenarios:
    def test_skip_self_relationship(self, client, tmp_db):
        c1 = _create_contact("Alice")
        resp = client.post("/contacts/relate", data={
            "contact_ids": [c1],
            "relationship_type_id": "rt-knows",
            "target_entity_id": c1,
            "target_entity_type": "contact",
        })
        assert resp.status_code == 200
        assert "Self-relationship" in resp.text

    def test_skip_duplicate_relationship(self, client, tmp_db):
        c1 = _create_contact("Alice")
        c2 = _create_contact("Bob")
        # Create first
        client.post("/contacts/relate", data={
            "contact_ids": [c1],
            "relationship_type_id": "rt-knows",
            "target_entity_id": c2,
            "target_entity_type": "contact",
        })
        # Attempt duplicate
        resp = client.post("/contacts/relate", data={
            "contact_ids": [c1],
            "relationship_type_id": "rt-knows",
            "target_entity_id": c2,
            "target_entity_type": "contact",
        })
        assert resp.status_code == 200
        assert "Already exists" in resp.text

    def test_mixed_results(self, client, tmp_db):
        c1 = _create_contact("Alice")
        c2 = _create_contact("Bob")
        target = _create_contact("Charlie")
        # Pre-create c1->target
        client.post("/contacts/relate", data={
            "contact_ids": [c1],
            "relationship_type_id": "rt-knows",
            "target_entity_id": target,
            "target_entity_type": "contact",
        })
        # Batch: c1 (dup) + c2 (new) + target (self)
        resp = client.post("/contacts/relate", data={
            "contact_ids": [c1, c2, target],
            "relationship_type_id": "rt-knows",
            "target_entity_id": target,
            "target_entity_type": "contact",
        })
        assert resp.status_code == 200
        assert "Already exists" in resp.text
        assert "Created" in resp.text
        assert "Self-relationship" in resp.text


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestRelateEdgeCases:
    def test_missing_relationship_type(self, client, tmp_db):
        c1 = _create_contact("Alice")
        c2 = _create_contact("Bob")
        resp = client.post("/contacts/relate", data={
            "contact_ids": [c1],
            "relationship_type_id": "nonexistent",
            "target_entity_id": c2,
            "target_entity_type": "contact",
        }, follow_redirects=False)
        assert resp.status_code == 303

    def test_missing_target(self, client, tmp_db):
        c1 = _create_contact("Alice")
        resp = client.post("/contacts/relate", data={
            "contact_ids": [c1],
            "relationship_type_id": "rt-knows",
            "target_entity_id": "",
            "target_entity_type": "contact",
        }, follow_redirects=False)
        assert resp.status_code == 303

    def test_missing_contact_ids(self, client, tmp_db):
        resp = client.post("/contacts/relate", data={
            "contact_ids": [],
            "relationship_type_id": "rt-knows",
            "target_entity_id": "some-id",
            "target_entity_type": "contact",
        }, follow_redirects=False)
        assert resp.status_code == 303


# ---------------------------------------------------------------------------
# List page
# ---------------------------------------------------------------------------

class TestRelateListButton:
    def test_relate_button_present(self, client, tmp_db):
        _create_contact("Alice")
        resp = client.get("/contacts")
        assert resp.status_code == 200
        assert "relate-btn" in resp.text
        assert "relateSelected" in resp.text

    def test_merge_button_present(self, client, tmp_db):
        _create_contact("Alice")
        resp = client.get("/contacts")
        assert resp.status_code == 200
        assert "merge-btn" in resp.text
