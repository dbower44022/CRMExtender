"""Tests for Views & Grid system (Phase 1)."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from poc.database import get_connection, init_db

_NOW = datetime.now(timezone.utc).isoformat()

CUST_ID = "cust-test"
USER_ID = "user-admin"
USER2_ID = "user-other"


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
        conn.execute(
            "INSERT INTO users "
            "(id, customer_id, email, name, role, is_active, created_at, updated_at) "
            "VALUES (?, ?, 'other@test.com', 'Other User', 'user', 1, ?, ?)",
            (USER2_ID, CUST_ID, _NOW, _NOW),
        )
    return db_file


def _make_client(monkeypatch, user_id=USER_ID):
    monkeypatch.setattr(
        "poc.hierarchy.get_current_user",
        lambda: {"id": user_id, "email": "admin@test.com", "name": "Admin User",
                 "role": "admin", "customer_id": CUST_ID},
    )
    from poc.web.app import create_app
    app = create_app()
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture()
def client(tmp_db, monkeypatch):
    return _make_client(monkeypatch)


def _seed_contacts(n=5):
    """Insert sample contacts with visibility rows."""
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
                (str(uuid.uuid4()), cid, f"contact{i}@example.com", _NOW, _NOW),
            )


def _seed_companies(n=3):
    """Insert sample companies with visibility rows."""
    with get_connection() as conn:
        for i in range(n):
            coid = f"company-{i}"
            conn.execute(
                "INSERT INTO companies (id, customer_id, name, domain, industry, status, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, 'active', ?, ?)",
                (coid, CUST_ID, f"Company {i}", f"company{i}.com", "Tech", _NOW, _NOW),
            )
            conn.execute(
                "INSERT INTO user_companies (id, user_id, company_id, visibility, is_owner, created_at, updated_at) "
                "VALUES (?, ?, ?, 'public', 1, ?, ?)",
                (str(uuid.uuid4()), USER_ID, coid, _NOW, _NOW),
            )


# ===========================================================================
# Filter Tests
# ===========================================================================

class TestResolveLink:
    def test_resolve_link_basic(self):
        from poc.web.filters import resolve_link_filter
        assert resolve_link_filter("/contacts/{id}", {"id": "abc"}) == "/contacts/abc"

    def test_resolve_link_multiple_placeholders(self):
        from poc.web.filters import resolve_link_filter
        assert resolve_link_filter(
            "/contacts/{contact_id}/emails/{email_id}",
            {"contact_id": "c1", "email_id": "e1"},
        ) == "/contacts/c1/emails/e1"

    def test_resolve_link_returns_none_on_unresolved(self):
        from poc.web.filters import resolve_link_filter
        assert resolve_link_filter("/contacts/{id}", {"name": "abc"}) is None

    def test_resolve_link_returns_none_on_null_value(self):
        from poc.web.filters import resolve_link_filter
        assert resolve_link_filter("/contacts/{id}", {"id": None}) is None


# ===========================================================================
# Registry Tests
# ===========================================================================

class TestRegistry:
    def test_all_entity_types_registered(self):
        from poc.views.registry import ENTITY_TYPES
        assert set(ENTITY_TYPES.keys()) == {
            "contact", "company", "conversation", "communication", "event",
            "project", "relationship", "note",
        }

    def test_default_columns_are_valid(self):
        from poc.views.registry import ENTITY_TYPES
        for et_key, et_def in ENTITY_TYPES.items():
            for col in et_def.default_columns:
                assert col in et_def.fields, (
                    f"{et_key}: default column '{col}' not in fields"
                )

    def test_field_sql_non_empty(self):
        from poc.views.registry import ENTITY_TYPES
        for et_key, et_def in ENTITY_TYPES.items():
            for fk, fdef in et_def.fields.items():
                assert fdef.sql, f"{et_key}.{fk}: sql is empty"

    def test_default_sort_is_valid(self):
        from poc.views.registry import ENTITY_TYPES
        for et_key, et_def in ENTITY_TYPES.items():
            field, direction = et_def.default_sort
            assert field in et_def.fields, (
                f"{et_key}: default sort field '{field}' not in fields"
            )
            assert direction in ("asc", "desc")


# ===========================================================================
# CRUD Tests
# ===========================================================================

class TestCRUD:
    def test_ensure_system_data_sources(self, tmp_db):
        from poc.views.crud import ensure_system_data_sources
        with get_connection() as conn:
            ensure_system_data_sources(conn, CUST_ID)
            rows = conn.execute(
                "SELECT * FROM data_sources WHERE customer_id = ?",
                (CUST_ID,),
            ).fetchall()
        assert len(rows) == 8
        entity_types = {r["entity_type"] for r in rows}
        assert entity_types == {
            "contact", "company", "conversation", "communication", "event",
            "project", "relationship", "note",
        }

    def test_ensure_default_views(self, tmp_db):
        from poc.views.crud import ensure_default_views
        with get_connection() as conn:
            ensure_default_views(conn, CUST_ID, USER_ID)
            views = conn.execute(
                "SELECT * FROM views WHERE owner_id = ?", (USER_ID,),
            ).fetchall()
        assert len(views) == 8
        # Each view should have columns
        with get_connection() as conn:
            for v in views:
                cols = conn.execute(
                    "SELECT * FROM view_columns WHERE view_id = ?", (v["id"],),
                ).fetchall()
                assert len(cols) > 0

    def test_ensure_default_views_idempotent(self, tmp_db):
        from poc.views.crud import ensure_default_views
        with get_connection() as conn:
            ensure_default_views(conn, CUST_ID, USER_ID)
        with get_connection() as conn:
            ensure_default_views(conn, CUST_ID, USER_ID)
            views = conn.execute(
                "SELECT * FROM views WHERE owner_id = ?", (USER_ID,),
            ).fetchall()
        assert len(views) == 8

    def test_create_view(self, tmp_db):
        from poc.views.crud import create_view, ensure_system_data_sources, get_view_with_config
        with get_connection() as conn:
            ensure_system_data_sources(conn, CUST_ID)
            ds_id = f"ds-contact-{CUST_ID}"
            view_id = create_view(
                conn,
                customer_id=CUST_ID,
                user_id=USER_ID,
                data_source_id=ds_id,
                name="My Contacts",
                columns=["name", "email"],
            )
            view = get_view_with_config(conn, view_id)
        assert view is not None
        assert view["name"] == "My Contacts"
        assert len(view["columns"]) == 2
        assert view["columns"][0]["field_key"] == "name"

    def test_create_view_with_filters(self, tmp_db):
        from poc.views.crud import create_view, ensure_system_data_sources, get_view_with_config
        with get_connection() as conn:
            ensure_system_data_sources(conn, CUST_ID)
            ds_id = f"ds-contact-{CUST_ID}"
            view_id = create_view(
                conn,
                customer_id=CUST_ID,
                user_id=USER_ID,
                data_source_id=ds_id,
                name="Filtered",
                filters=[
                    {"field_key": "source", "operator": "equals", "value": "gmail"},
                ],
            )
            view = get_view_with_config(conn, view_id)
        assert len(view["filters"]) == 1
        assert view["filters"][0]["operator"] == "equals"

    def test_update_view(self, tmp_db):
        from poc.views.crud import (
            create_view, ensure_system_data_sources, get_view, update_view,
        )
        with get_connection() as conn:
            ensure_system_data_sources(conn, CUST_ID)
            view_id = create_view(
                conn, customer_id=CUST_ID, user_id=USER_ID,
                data_source_id=f"ds-contact-{CUST_ID}", name="Original",
            )
            update_view(conn, view_id, name="Updated", sort_field="email", sort_direction="desc")
            view = get_view(conn, view_id)
        assert view["name"] == "Updated"
        assert view["sort_field"] == "email"
        assert view["sort_direction"] == "desc"

    def test_update_view_columns(self, tmp_db):
        from poc.views.crud import (
            create_view, ensure_system_data_sources, get_view_with_config,
            update_view_columns,
        )
        with get_connection() as conn:
            ensure_system_data_sources(conn, CUST_ID)
            view_id = create_view(
                conn, customer_id=CUST_ID, user_id=USER_ID,
                data_source_id=f"ds-contact-{CUST_ID}", name="Test",
                columns=["name", "email"],
            )
            update_view_columns(conn, view_id, ["name", "company_name", "score"])
            view = get_view_with_config(conn, view_id)
        assert len(view["columns"]) == 3
        assert [c["field_key"] for c in view["columns"]] == ["name", "company_name", "score"]

    def test_update_view_filters(self, tmp_db):
        from poc.views.crud import (
            create_view, ensure_system_data_sources, get_view_with_config,
            update_view_filters,
        )
        with get_connection() as conn:
            ensure_system_data_sources(conn, CUST_ID)
            view_id = create_view(
                conn, customer_id=CUST_ID, user_id=USER_ID,
                data_source_id=f"ds-contact-{CUST_ID}", name="Test",
            )
            update_view_filters(conn, view_id, [
                {"field_key": "name", "operator": "contains", "value": "alice"},
            ])
            view = get_view_with_config(conn, view_id)
        assert len(view["filters"]) == 1
        assert view["filters"][0]["field_key"] == "name"

    def test_delete_view(self, tmp_db):
        from poc.views.crud import (
            create_view, delete_view, ensure_system_data_sources, get_view,
        )
        with get_connection() as conn:
            ensure_system_data_sources(conn, CUST_ID)
            view_id = create_view(
                conn, customer_id=CUST_ID, user_id=USER_ID,
                data_source_id=f"ds-contact-{CUST_ID}", name="Temp",
            )
            assert delete_view(conn, view_id) is True
            assert get_view(conn, view_id) is None

    def test_cannot_delete_default_view(self, tmp_db):
        from poc.views.crud import delete_view, ensure_default_views
        with get_connection() as conn:
            ensure_default_views(conn, CUST_ID, USER_ID)
            views = conn.execute(
                "SELECT id FROM views WHERE owner_id = ? AND is_default = 1",
                (USER_ID,),
            ).fetchall()
            assert len(views) > 0
            result = delete_view(conn, views[0]["id"])
        assert result is False

    def test_duplicate_view(self, tmp_db):
        from poc.views.crud import (
            create_view, duplicate_view, ensure_system_data_sources,
            get_view_with_config,
        )
        with get_connection() as conn:
            ensure_system_data_sources(conn, CUST_ID)
            view_id = create_view(
                conn, customer_id=CUST_ID, user_id=USER_ID,
                data_source_id=f"ds-contact-{CUST_ID}", name="Original",
                columns=["name", "email"],
                filters=[
                    {"field_key": "source", "operator": "equals", "value": "test"},
                ],
            )
            new_id = duplicate_view(conn, view_id, "Copy", USER_ID)
            original = get_view_with_config(conn, view_id)
            copy = get_view_with_config(conn, new_id)
        assert copy["name"] == "Copy"
        assert len(copy["columns"]) == len(original["columns"])
        assert len(copy["filters"]) == len(original["filters"])
        assert copy["is_default"] == 0

    def test_get_views_for_entity(self, tmp_db):
        from poc.views.crud import ensure_default_views, get_views_for_entity
        with get_connection() as conn:
            ensure_default_views(conn, CUST_ID, USER_ID)
            views = get_views_for_entity(conn, CUST_ID, USER_ID, "contact")
        assert len(views) >= 1
        assert all(v["entity_type"] == "contact" for v in views)

    def test_get_default_view_for_entity(self, tmp_db):
        from poc.views.crud import get_default_view_for_entity
        with get_connection() as conn:
            view = get_default_view_for_entity(conn, CUST_ID, USER_ID, "contact")
        assert view is not None
        assert view["entity_type"] == "contact"
        assert "columns" in view
        assert "filters" in view
        assert len(view["columns"]) > 0

    def test_get_default_view_creates_if_missing(self, tmp_db):
        """Auto-creates views if none exist for the user."""
        from poc.views.crud import get_default_view_for_entity
        # No views exist yet — should auto-create
        with get_connection() as conn:
            view = get_default_view_for_entity(conn, CUST_ID, USER_ID, "company")
        assert view is not None
        assert view["entity_type"] == "company"
        assert len(view["columns"]) > 0

    def test_default_columns_match_registry(self, tmp_db):
        """_DEFAULT_COLUMNS keys match ENTITY_TYPES default_columns."""
        from poc.views.crud import _DEFAULT_COLUMNS
        from poc.views.registry import ENTITY_TYPES
        for et in ENTITY_TYPES:
            assert et in _DEFAULT_COLUMNS, f"Missing {et} in _DEFAULT_COLUMNS"
            assert _DEFAULT_COLUMNS[et] == ENTITY_TYPES[et].default_columns, (
                f"{et}: _DEFAULT_COLUMNS doesn't match registry default_columns"
            )

    def test_get_default_view_returns_all_entity_types(self, tmp_db):
        """All 5 entity types return a default view."""
        from poc.views.crud import get_default_view_for_entity
        for et in ("contact", "company", "conversation", "communication", "event"):
            with get_connection() as conn:
                view = get_default_view_for_entity(conn, CUST_ID, USER_ID, et)
            assert view is not None, f"No default view for {et}"
            assert view["entity_type"] == et


# ===========================================================================
# Query Engine Tests
# ===========================================================================

class TestQueryEngine:
    def test_basic_contact_query(self, tmp_db):
        _seed_contacts(3)
        from poc.views.engine import execute_view
        columns = [{"field_key": "name"}, {"field_key": "email"}]
        with get_connection() as conn:
            rows, total = execute_view(
                conn, entity_type="contact", columns=columns, filters=[],
                customer_id=CUST_ID, user_id=USER_ID,
            )
        assert total == 3
        assert len(rows) == 3
        assert "name" in rows[0]

    def test_company_query(self, tmp_db):
        _seed_companies(3)
        from poc.views.engine import execute_view
        columns = [{"field_key": "name"}, {"field_key": "domain"}]
        with get_connection() as conn:
            rows, total = execute_view(
                conn, entity_type="company", columns=columns, filters=[],
                customer_id=CUST_ID, user_id=USER_ID,
            )
        assert total == 3

    def test_filter_equals(self, tmp_db):
        _seed_contacts(5)
        from poc.views.engine import execute_view
        columns = [{"field_key": "name"}]
        filters = [{"field_key": "name", "operator": "equals", "value": "Contact 2"}]
        with get_connection() as conn:
            rows, total = execute_view(
                conn, entity_type="contact", columns=columns, filters=filters,
                customer_id=CUST_ID, user_id=USER_ID,
            )
        assert total == 1
        assert rows[0]["name"] == "Contact 2"

    def test_filter_contains(self, tmp_db):
        _seed_contacts(5)
        from poc.views.engine import execute_view
        columns = [{"field_key": "name"}]
        filters = [{"field_key": "name", "operator": "contains", "value": "Contact"}]
        with get_connection() as conn:
            rows, total = execute_view(
                conn, entity_type="contact", columns=columns, filters=filters,
                customer_id=CUST_ID, user_id=USER_ID,
            )
        assert total == 5

    def test_filter_is_empty(self, tmp_db):
        _seed_contacts(2)
        # Insert a contact with no source
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO contacts (id, customer_id, name, source, status, created_at, updated_at) "
                "VALUES ('c-nosrc', ?, 'No Source', NULL, 'active', ?, ?)",
                (CUST_ID, _NOW, _NOW),
            )
            conn.execute(
                "INSERT INTO user_contacts (id, user_id, contact_id, visibility, is_owner, created_at, updated_at) "
                "VALUES (?, ?, 'c-nosrc', 'public', 1, ?, ?)",
                (str(uuid.uuid4()), USER_ID, _NOW, _NOW),
            )
        from poc.views.engine import execute_view
        columns = [{"field_key": "name"}, {"field_key": "source"}]
        filters = [{"field_key": "source", "operator": "is_empty"}]
        with get_connection() as conn:
            rows, total = execute_view(
                conn, entity_type="contact", columns=columns, filters=filters,
                customer_id=CUST_ID, user_id=USER_ID,
            )
        assert total >= 1
        # All results should have empty source
        for r in rows:
            assert r["source"] is None or r["source"] == ""

    def test_multiple_filters_and(self, tmp_db):
        _seed_contacts(5)
        from poc.views.engine import execute_view
        columns = [{"field_key": "name"}]
        filters = [
            {"field_key": "name", "operator": "contains", "value": "Contact"},
            {"field_key": "name", "operator": "contains", "value": "3"},
        ]
        with get_connection() as conn:
            rows, total = execute_view(
                conn, entity_type="contact", columns=columns, filters=filters,
                customer_id=CUST_ID, user_id=USER_ID,
            )
        assert total == 1
        assert rows[0]["name"] == "Contact 3"

    def test_sort_ascending(self, tmp_db):
        _seed_contacts(3)
        from poc.views.engine import execute_view
        columns = [{"field_key": "name"}]
        with get_connection() as conn:
            rows, _ = execute_view(
                conn, entity_type="contact", columns=columns, filters=[],
                sort_field="name", sort_direction="asc",
                customer_id=CUST_ID, user_id=USER_ID,
            )
        names = [r["name"] for r in rows]
        assert names == sorted(names)

    def test_sort_descending(self, tmp_db):
        _seed_contacts(3)
        from poc.views.engine import execute_view
        columns = [{"field_key": "name"}]
        with get_connection() as conn:
            rows, _ = execute_view(
                conn, entity_type="contact", columns=columns, filters=[],
                sort_field="name", sort_direction="desc",
                customer_id=CUST_ID, user_id=USER_ID,
            )
        names = [r["name"] for r in rows]
        assert names == sorted(names, reverse=True)

    def test_pagination(self, tmp_db):
        _seed_contacts(5)
        from poc.views.engine import execute_view
        columns = [{"field_key": "name"}]
        with get_connection() as conn:
            rows_p1, total = execute_view(
                conn, entity_type="contact", columns=columns, filters=[],
                page=1, per_page=2,
                customer_id=CUST_ID, user_id=USER_ID,
            )
            rows_p2, _ = execute_view(
                conn, entity_type="contact", columns=columns, filters=[],
                page=2, per_page=2,
                customer_id=CUST_ID, user_id=USER_ID,
            )
        assert total == 5
        assert len(rows_p1) == 2
        assert len(rows_p2) == 2
        # Pages should be different
        ids_p1 = {r["id"] for r in rows_p1}
        ids_p2 = {r["id"] for r in rows_p2}
        assert ids_p1.isdisjoint(ids_p2)

    def test_search(self, tmp_db):
        _seed_contacts(5)
        from poc.views.engine import execute_view
        columns = [{"field_key": "name"}]
        with get_connection() as conn:
            rows, total = execute_view(
                conn, entity_type="contact", columns=columns, filters=[],
                search="Contact 1",
                customer_id=CUST_ID, user_id=USER_ID,
            )
        assert total >= 1
        assert any("Contact 1" in r["name"] for r in rows)

    def test_search_by_email(self, tmp_db):
        _seed_contacts(5)
        from poc.views.engine import execute_view
        columns = [{"field_key": "name"}, {"field_key": "email"}]
        with get_connection() as conn:
            rows, total = execute_view(
                conn, entity_type="contact", columns=columns, filters=[],
                search="contact2@example",
                customer_id=CUST_ID, user_id=USER_ID,
            )
        assert total >= 1

    def test_unknown_entity_type(self, tmp_db):
        from poc.views.engine import execute_view
        with get_connection() as conn:
            with pytest.raises(ValueError, match="Unknown entity type"):
                execute_view(conn, entity_type="bogus", columns=[], filters=[])

    def test_invalid_sort_falls_back(self, tmp_db):
        _seed_contacts(2)
        from poc.views.engine import execute_view
        columns = [{"field_key": "name"}]
        with get_connection() as conn:
            rows, total = execute_view(
                conn, entity_type="contact", columns=columns, filters=[],
                sort_field="nonexistent", sort_direction="asc",
                customer_id=CUST_ID, user_id=USER_ID,
            )
        assert total == 2  # Falls back to default sort, no error

    def test_scope_mine_contacts(self, tmp_db):
        """scope='mine' returns only the user's own contacts."""
        _seed_contacts(3)
        # Seed a contact owned by another user (no user_contacts row for USER_ID)
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO contacts (id, customer_id, name, source, status, created_at, updated_at) "
                "VALUES ('c-other', ?, 'Other Contact', 'test', 'active', ?, ?)",
                (CUST_ID, _NOW, _NOW),
            )
            conn.execute(
                "INSERT INTO user_contacts (id, user_id, contact_id, visibility, is_owner, created_at, updated_at) "
                "VALUES (?, ?, 'c-other', 'public', 1, ?, ?)",
                (str(uuid.uuid4()), USER2_ID, _NOW, _NOW),
            )

        from poc.views.engine import execute_view
        columns = [{"field_key": "name"}]
        with get_connection() as conn:
            # scope=all should see all 4
            rows_all, total_all = execute_view(
                conn, entity_type="contact", columns=columns, filters=[],
                customer_id=CUST_ID, user_id=USER_ID, scope="all",
            )
            # scope=mine should see only 3
            rows_mine, total_mine = execute_view(
                conn, entity_type="contact", columns=columns, filters=[],
                customer_id=CUST_ID, user_id=USER_ID, scope="mine",
            )
        assert total_all == 4
        assert total_mine == 3
        mine_ids = {r["id"] for r in rows_mine}
        assert "c-other" not in mine_ids

    def test_scope_mine_companies(self, tmp_db):
        """scope='mine' returns only the user's own companies."""
        _seed_companies(2)
        # Seed a company owned by another user
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO companies (id, customer_id, name, domain, status, created_at, updated_at) "
                "VALUES ('co-other', ?, 'Other Co', 'other.com', 'active', ?, ?)",
                (CUST_ID, _NOW, _NOW),
            )
            conn.execute(
                "INSERT INTO user_companies (id, user_id, company_id, visibility, is_owner, created_at, updated_at) "
                "VALUES (?, ?, 'co-other', 'public', 1, ?, ?)",
                (str(uuid.uuid4()), USER2_ID, _NOW, _NOW),
            )

        from poc.views.engine import execute_view
        columns = [{"field_key": "name"}]
        with get_connection() as conn:
            rows_all, total_all = execute_view(
                conn, entity_type="company", columns=columns, filters=[],
                customer_id=CUST_ID, user_id=USER_ID, scope="all",
            )
            rows_mine, total_mine = execute_view(
                conn, entity_type="company", columns=columns, filters=[],
                customer_id=CUST_ID, user_id=USER_ID, scope="mine",
            )
        assert total_all == 3
        assert total_mine == 2
        mine_ids = {r["id"] for r in rows_mine}
        assert "co-other" not in mine_ids

    def test_extra_where(self, tmp_db):
        """extra_where filters are applied correctly."""
        _seed_contacts(5)
        from poc.views.engine import execute_view
        columns = [{"field_key": "name"}, {"field_key": "source"}]
        with get_connection() as conn:
            rows, total = execute_view(
                conn, entity_type="contact", columns=columns, filters=[],
                customer_id=CUST_ID, user_id=USER_ID,
                extra_where=[("c.source = 'test'", [])],
            )
        assert total == 5  # all seeded contacts have source='test'

    def test_extra_where_with_params(self, tmp_db):
        """extra_where with bound parameters works correctly."""
        _seed_contacts(5)
        from poc.views.engine import execute_view
        columns = [{"field_key": "name"}]
        with get_connection() as conn:
            rows, total = execute_view(
                conn, entity_type="contact", columns=columns, filters=[],
                customer_id=CUST_ID, user_id=USER_ID,
                extra_where=[("c.name = ?", ["Contact 2"])],
            )
        assert total == 1
        assert rows[0]["name"] == "Contact 2"


# ===========================================================================
# Migration Tests
# ===========================================================================

class TestMigration:
    def test_migration_creates_tables(self, tmp_path):
        """Test that v16 migration creates all expected tables."""
        import sqlite3
        db_file = tmp_path / "migrate_test.db"
        conn = sqlite3.connect(str(db_file))
        conn.row_factory = sqlite3.Row
        # Create minimal v15 schema
        conn.execute("CREATE TABLE customers (id TEXT PRIMARY KEY, name TEXT, slug TEXT UNIQUE, is_active INTEGER, created_at TEXT, updated_at TEXT)")
        conn.execute("CREATE TABLE users (id TEXT PRIMARY KEY, customer_id TEXT, email TEXT, name TEXT, role TEXT, is_active INTEGER, password_hash TEXT, google_sub TEXT, created_at TEXT, updated_at TEXT)")
        conn.execute("CREATE TABLE views (id TEXT PRIMARY KEY, owner_id TEXT, name TEXT, description TEXT, query_def TEXT, is_shared INTEGER, created_at TEXT, updated_at TEXT)")
        conn.execute("CREATE TABLE alerts (id TEXT PRIMARY KEY, view_id TEXT, owner_id TEXT, is_active INTEGER, frequency TEXT, aggregation TEXT, delivery_method TEXT, last_triggered TEXT, created_at TEXT, updated_at TEXT)")
        conn.execute("INSERT INTO customers VALUES ('cust-1', 'Test', 'test', 1, '2026-01-01', '2026-01-01')")
        conn.execute("INSERT INTO users VALUES ('user-1', 'cust-1', 'a@b.com', 'A', 'admin', 1, NULL, NULL, '2026-01-01', '2026-01-01')")
        conn.execute("PRAGMA user_version = 15")
        conn.commit()
        conn.close()

        from poc.migrate_to_v16 import migrate
        migrate(db_file, dry_run=False)

        conn = sqlite3.connect(str(db_file))
        conn.row_factory = sqlite3.Row
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        assert "data_sources" in tables
        assert "views" in tables
        assert "view_columns" in tables
        assert "view_filters" in tables
        assert "alerts" not in tables  # old table dropped

        # Check data sources created
        ds = conn.execute("SELECT * FROM data_sources").fetchall()
        assert len(ds) == 5

        # Check views created
        views = conn.execute("SELECT * FROM views").fetchall()
        assert len(views) == 5

        # Check schema version
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        assert version == 16
        conn.close()


# ===========================================================================
# Web Route Tests
# ===========================================================================

class TestWebRoutes:
    def test_views_dashboard(self, client):
        resp = client.get("/views")
        assert resp.status_code == 200
        assert "Views" in resp.text

    def test_views_dashboard_creates_defaults(self, client):
        resp = client.get("/views")
        assert resp.status_code == 200
        # Should have default views for all entity types
        assert "Contacts" in resp.text

    def test_new_view_form(self, client):
        resp = client.get("/views/new")
        assert resp.status_code == 200
        assert "Create New View" in resp.text

    def test_new_view_form_preselected(self, client):
        resp = client.get("/views/new?entity_type=contact")
        assert resp.status_code == 200
        assert "selected" in resp.text

    def test_create_view(self, client):
        resp = client.post("/views/new", data={
            "name": "Test View",
            "entity_type": "contact",
        })
        assert resp.status_code == 200  # redirect followed
        assert "Test View" in resp.text

    def test_view_grid(self, client, tmp_db):
        _seed_contacts(3)
        # Get the default contact view
        with get_connection() as conn:
            from poc.views.crud import ensure_default_views
            ensure_default_views(conn, CUST_ID, USER_ID)
            views = conn.execute(
                "SELECT v.id FROM views v JOIN data_sources ds ON ds.id = v.data_source_id "
                "WHERE v.owner_id = ? AND ds.entity_type = 'contact'",
                (USER_ID,),
            ).fetchall()
        view_id = views[0]["id"]
        resp = client.get(f"/views/{view_id}")
        assert resp.status_code == 200
        assert "Contact 0" in resp.text

    def test_view_grid_with_search(self, client, tmp_db):
        _seed_contacts(5)
        with get_connection() as conn:
            from poc.views.crud import ensure_default_views
            ensure_default_views(conn, CUST_ID, USER_ID)
            views = conn.execute(
                "SELECT v.id FROM views v JOIN data_sources ds ON ds.id = v.data_source_id "
                "WHERE v.owner_id = ? AND ds.entity_type = 'contact'",
                (USER_ID,),
            ).fetchall()
        view_id = views[0]["id"]
        resp = client.get(f"/views/{view_id}?q=Contact 2")
        assert resp.status_code == 200
        assert "Contact 2" in resp.text

    def test_view_search_partial(self, client, tmp_db):
        _seed_contacts(3)
        with get_connection() as conn:
            from poc.views.crud import ensure_default_views
            ensure_default_views(conn, CUST_ID, USER_ID)
            views = conn.execute(
                "SELECT v.id FROM views v JOIN data_sources ds ON ds.id = v.data_source_id "
                "WHERE v.owner_id = ? AND ds.entity_type = 'contact'",
                (USER_ID,),
            ).fetchall()
        view_id = views[0]["id"]
        resp = client.get(f"/views/{view_id}/search",
                         headers={"HX-Request": "true"})
        assert resp.status_code == 200
        # Should be a partial (no full HTML doc)
        assert "Contact 0" in resp.text

    def test_view_sort(self, client, tmp_db):
        _seed_contacts(3)
        with get_connection() as conn:
            from poc.views.crud import ensure_default_views
            ensure_default_views(conn, CUST_ID, USER_ID)
            views = conn.execute(
                "SELECT v.id FROM views v JOIN data_sources ds ON ds.id = v.data_source_id "
                "WHERE v.owner_id = ? AND ds.entity_type = 'contact'",
                (USER_ID,),
            ).fetchall()
        view_id = views[0]["id"]
        resp = client.get(f"/views/{view_id}?sort=-name")
        assert resp.status_code == 200

    def test_edit_view_form(self, client, tmp_db):
        with get_connection() as conn:
            from poc.views.crud import ensure_default_views
            ensure_default_views(conn, CUST_ID, USER_ID)
            views = conn.execute(
                "SELECT v.id FROM views v WHERE v.owner_id = ? LIMIT 1",
                (USER_ID,),
            ).fetchall()
        view_id = views[0]["id"]
        resp = client.get(f"/views/{view_id}/edit")
        assert resp.status_code == 200
        assert "Edit View" in resp.text

    def test_save_view(self, client, tmp_db):
        with get_connection() as conn:
            from poc.views.crud import ensure_default_views
            ensure_default_views(conn, CUST_ID, USER_ID)
            views = conn.execute(
                "SELECT v.id FROM views v "
                "JOIN data_sources ds ON ds.id = v.data_source_id "
                "WHERE v.owner_id = ? AND ds.entity_type = 'contact' LIMIT 1",
                (USER_ID,),
            ).fetchall()
        view_id = views[0]["id"]
        resp = client.post(f"/views/{view_id}/edit", data={
            "name": "Renamed View",
            "sort_field": "name",
            "sort_direction": "desc",
            "per_page": "25",
            "columns_json": json.dumps(["name", "email"]),
            "filters_json": json.dumps([]),
        })
        assert resp.status_code == 200  # redirect followed
        # Verify the update
        with get_connection() as conn:
            from poc.views.crud import get_view
            view = get_view(conn, view_id)
        assert view["name"] == "Renamed View"
        assert view["sort_direction"] == "desc"

    def test_duplicate_view(self, client, tmp_db):
        with get_connection() as conn:
            from poc.views.crud import ensure_default_views
            ensure_default_views(conn, CUST_ID, USER_ID)
            views = conn.execute(
                "SELECT v.id FROM views v WHERE v.owner_id = ? LIMIT 1",
                (USER_ID,),
            ).fetchall()
        view_id = views[0]["id"]
        resp = client.post(f"/views/{view_id}/duplicate")
        assert resp.status_code == 200  # redirect followed
        assert "(copy)" in resp.text

    def test_delete_non_default_view(self, client, tmp_db):
        # Create a non-default view then delete it
        resp = client.post("/views/new", data={
            "name": "Temporary",
            "entity_type": "contact",
        })
        assert resp.status_code == 200
        # Find the view
        with get_connection() as conn:
            view = conn.execute(
                "SELECT id FROM views WHERE name = 'Temporary' AND owner_id = ?",
                (USER_ID,),
            ).fetchone()
        assert view is not None
        view_id = view["id"]
        resp = client.post(f"/views/{view_id}/delete")
        assert resp.status_code == 200  # redirect to /views
        with get_connection() as conn:
            gone = conn.execute(
                "SELECT id FROM views WHERE id = ?", (view_id,),
            ).fetchone()
        assert gone is None

    def test_delete_default_view_fails(self, client, tmp_db):
        with get_connection() as conn:
            from poc.views.crud import ensure_default_views
            ensure_default_views(conn, CUST_ID, USER_ID)
            view = conn.execute(
                "SELECT id FROM views WHERE owner_id = ? AND is_default = 1 LIMIT 1",
                (USER_ID,),
            ).fetchone()
        view_id = view["id"]
        resp = client.post(f"/views/{view_id}/delete")
        # Should redirect back to the view (not deleted)
        assert resp.status_code == 200
        with get_connection() as conn:
            still_there = conn.execute(
                "SELECT id FROM views WHERE id = ?", (view_id,),
            ).fetchone()
        assert still_there is not None

    def test_404_for_missing_view(self, client):
        resp = client.get("/views/nonexistent-id")
        assert resp.status_code == 404

    def test_access_check_wrong_customer(self, client, tmp_db):
        # Create a view under a different customer
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO customers (id, name, slug, is_active, created_at, updated_at) "
                "VALUES ('cust-other', 'Other Org', 'other', 1, ?, ?)",
                (_NOW, _NOW),
            )
            conn.execute(
                "INSERT INTO users (id, customer_id, email, name, role, is_active, created_at, updated_at) "
                "VALUES ('user-other2', 'cust-other', 'x@test.com', 'X', 'admin', 1, ?, ?)",
                (_NOW, _NOW),
            )
            from poc.views.crud import ensure_system_data_sources
            ensure_system_data_sources(conn, "cust-other")
            from poc.views.crud import create_view
            view_id = create_view(
                conn, customer_id="cust-other", user_id="user-other2",
                data_source_id="ds-contact-cust-other", name="Other View",
            )
        resp = client.get(f"/views/{view_id}")
        assert resp.status_code == 404

    def test_company_view(self, client, tmp_db):
        _seed_companies(3)
        with get_connection() as conn:
            from poc.views.crud import ensure_default_views
            ensure_default_views(conn, CUST_ID, USER_ID)
            views = conn.execute(
                "SELECT v.id FROM views v JOIN data_sources ds ON ds.id = v.data_source_id "
                "WHERE v.owner_id = ? AND ds.entity_type = 'company'",
                (USER_ID,),
            ).fetchall()
        view_id = views[0]["id"]
        resp = client.get(f"/views/{view_id}")
        assert resp.status_code == 200
        assert "Company 0" in resp.text

    def test_views_filtered_by_entity_type(self, client):
        resp = client.get("/views?entity_type=contact")
        assert resp.status_code == 200
        assert "Contact" in resp.text

    def test_edit_view_shows_ordered_columns(self, client, tmp_db):
        """GET edit page lists selected columns in view column order."""
        from poc.views.crud import (
            create_view, ensure_system_data_sources, update_view_columns,
        )
        with get_connection() as conn:
            ensure_system_data_sources(conn, CUST_ID)
            view_id = create_view(
                conn, customer_id=CUST_ID, user_id=USER_ID,
                data_source_id=f"ds-contact-{CUST_ID}", name="Ordered Test",
                columns=["email", "name", "source"],
            )
        resp = client.get(f"/views/{view_id}/edit")
        assert resp.status_code == 200
        html = resp.text
        # Columns should appear in order: Email, Name, Source
        email_pos = html.index('data-key="email"')
        name_pos = html.index('data-key="name"')
        source_pos = html.index('data-key="source"')
        assert email_pos < name_pos < source_pos

    def test_save_view_preserves_column_order(self, client, tmp_db):
        """POST with columns_json preserves the specified order."""
        from poc.views.crud import (
            create_view, ensure_system_data_sources, get_view_with_config,
        )
        with get_connection() as conn:
            ensure_system_data_sources(conn, CUST_ID)
            view_id = create_view(
                conn, customer_id=CUST_ID, user_id=USER_ID,
                data_source_id=f"ds-contact-{CUST_ID}", name="Order Save",
                columns=["name", "email"],
            )
        resp = client.post(f"/views/{view_id}/edit", data={
            "name": "Order Save",
            "sort_field": "name",
            "sort_direction": "asc",
            "per_page": "50",
            "columns_json": json.dumps(["email", "name", "score"]),
            "filters_json": json.dumps([]),
        })
        assert resp.status_code == 200
        with get_connection() as conn:
            view = get_view_with_config(conn, view_id)
        col_keys = [c["field_key"] for c in view["columns"]]
        assert col_keys == ["email", "name", "score"]

    def test_save_view_auto_includes_hidden_deps(self, client, tmp_db):
        """POST with company_name auto-adds company_id hidden dep."""
        from poc.views.crud import (
            create_view, ensure_system_data_sources, get_view_with_config,
        )
        with get_connection() as conn:
            ensure_system_data_sources(conn, CUST_ID)
            view_id = create_view(
                conn, customer_id=CUST_ID, user_id=USER_ID,
                data_source_id=f"ds-contact-{CUST_ID}", name="Dep Test",
                columns=["name"],
            )
        # Submit with company_name but NOT company_id
        resp = client.post(f"/views/{view_id}/edit", data={
            "name": "Dep Test",
            "sort_field": "name",
            "sort_direction": "asc",
            "per_page": "50",
            "columns_json": json.dumps(["name", "company_name"]),
            "filters_json": json.dumps([]),
        })
        assert resp.status_code == 200
        with get_connection() as conn:
            view = get_view_with_config(conn, view_id)
        col_keys = [c["field_key"] for c in view["columns"]]
        assert "company_name" in col_keys
        assert "company_id" in col_keys  # auto-added

    def test_save_view_redirects_with_saved(self, client, tmp_db):
        """POST save redirects to edit page with ?saved=1."""
        from poc.views.crud import create_view, ensure_system_data_sources
        with get_connection() as conn:
            ensure_system_data_sources(conn, CUST_ID)
            view_id = create_view(
                conn, customer_id=CUST_ID, user_id=USER_ID,
                data_source_id=f"ds-contact-{CUST_ID}", name="Redirect Test",
                columns=["name"],
            )
        resp = client.post(f"/views/{view_id}/edit", data={
            "name": "Redirect Test",
            "sort_field": "name",
            "sort_direction": "asc",
            "per_page": "50",
            "columns_json": json.dumps(["name"]),
            "filters_json": json.dumps([]),
        }, follow_redirects=False)
        assert resp.status_code == 303
        assert f"/views/{view_id}/edit?saved=1" in resp.headers["location"]

    def test_edit_view_available_columns(self, client, tmp_db):
        """GET edit page shows non-selected, non-hidden fields as available."""
        from poc.views.crud import create_view, ensure_system_data_sources
        with get_connection() as conn:
            ensure_system_data_sources(conn, CUST_ID)
            view_id = create_view(
                conn, customer_id=CUST_ID, user_id=USER_ID,
                data_source_id=f"ds-contact-{CUST_ID}", name="Available Test",
                columns=["name"],
            )
        resp = client.get(f"/views/{view_id}/edit")
        assert resp.status_code == 200
        html = resp.text
        # "email" should be in the available dropdown (not selected)
        assert 'id="add-column-select"' in html
        assert '<option value="email">' in html
        # "name" should NOT be in the available dropdown (already selected)
        # It should be in the selected list instead
        assert 'data-key="name"' in html


# ===========================================================================
# Column Config Tests (Phase 5)
# ===========================================================================

class TestColumnConfig:
    def test_update_view_columns_with_label_and_width(self, tmp_db):
        """CRUD saves and loads label_override + width_px."""
        from poc.views.crud import (
            create_view, ensure_system_data_sources, get_view_with_config,
            update_view_columns,
        )
        with get_connection() as conn:
            ensure_system_data_sources(conn, CUST_ID)
            view_id = create_view(
                conn, customer_id=CUST_ID, user_id=USER_ID,
                data_source_id=f"ds-contact-{CUST_ID}", name="Label Width Test",
                columns=["name"],
            )
            update_view_columns(conn, view_id, [
                {"key": "name", "label": "Full Name", "width": 250},
                {"key": "email"},
            ])
            view = get_view_with_config(conn, view_id)
        assert len(view["columns"]) == 2
        assert view["columns"][0]["field_key"] == "name"
        assert view["columns"][0]["label_override"] == "Full Name"
        assert view["columns"][0]["width_px"] == 250
        assert view["columns"][1]["field_key"] == "email"
        assert view["columns"][1]["label_override"] is None
        assert view["columns"][1]["width_px"] is None

    def test_update_view_columns_backward_compat(self, tmp_db):
        """Plain string list still works with update_view_columns."""
        from poc.views.crud import (
            create_view, ensure_system_data_sources, get_view_with_config,
            update_view_columns,
        )
        with get_connection() as conn:
            ensure_system_data_sources(conn, CUST_ID)
            view_id = create_view(
                conn, customer_id=CUST_ID, user_id=USER_ID,
                data_source_id=f"ds-contact-{CUST_ID}", name="Compat Test",
                columns=["name"],
            )
            update_view_columns(conn, view_id, ["name", "email", "score"])
            view = get_view_with_config(conn, view_id)
        assert len(view["columns"]) == 3
        assert [c["field_key"] for c in view["columns"]] == ["name", "email", "score"]
        assert all(c["label_override"] is None for c in view["columns"])
        assert all(c["width_px"] is None for c in view["columns"])

    def test_save_view_with_column_objects(self, client, tmp_db):
        """POST with object-format columns_json persists label + width."""
        from poc.views.crud import create_view, ensure_system_data_sources, get_view_with_config
        with get_connection() as conn:
            ensure_system_data_sources(conn, CUST_ID)
            view_id = create_view(
                conn, customer_id=CUST_ID, user_id=USER_ID,
                data_source_id=f"ds-contact-{CUST_ID}", name="Obj Save",
                columns=["name"],
            )
        resp = client.post(f"/views/{view_id}/edit", data={
            "name": "Obj Save",
            "sort_field": "name",
            "sort_direction": "asc",
            "per_page": "50",
            "columns_json": json.dumps([
                {"key": "name", "label": "Contact Name", "width": 300},
                {"key": "email"},
            ]),
            "filters_json": json.dumps([]),
        })
        assert resp.status_code == 200
        with get_connection() as conn:
            view = get_view_with_config(conn, view_id)
        assert view["columns"][0]["label_override"] == "Contact Name"
        assert view["columns"][0]["width_px"] == 300
        assert view["columns"][1]["label_override"] is None


# ===========================================================================
# Inline Cell Edit Tests (Phase 5)
# ===========================================================================

class TestInlineCellEdit:
    def test_cell_edit_contact_name(self, client, tmp_db):
        """Updates contact name, returns ok."""
        _seed_contacts(1)
        resp = client.post(
            "/views/cell-edit",
            json={"entity_type": "contact", "entity_id": "contact-0",
                  "field_key": "name", "value": "New Name"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["value"] == "New Name"

    def test_cell_edit_company_industry(self, client, tmp_db):
        """Updates company field."""
        _seed_companies(1)
        resp = client.post(
            "/views/cell-edit",
            json={"entity_type": "company", "entity_id": "company-0",
                  "field_key": "industry", "value": "Finance"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["value"] == "Finance"

    def test_cell_edit_non_editable_field(self, client, tmp_db):
        """Rejects non-editable field with 400."""
        _seed_contacts(1)
        resp = client.post(
            "/views/cell-edit",
            json={"entity_type": "contact", "entity_id": "contact-0",
                  "field_key": "email", "value": "nope@example.com"},
        )
        assert resp.status_code == 400
        assert resp.json()["ok"] is False

    def test_cell_edit_unknown_entity_type(self, client, tmp_db):
        """Rejects bogus entity type with 400."""
        resp = client.post(
            "/views/cell-edit",
            json={"entity_type": "bogus", "entity_id": "x",
                  "field_key": "name", "value": "test"},
        )
        assert resp.status_code == 400

    def test_cell_edit_wrong_customer(self, client, tmp_db):
        """Rejects cross-customer access with 404."""
        # Insert a contact under a different customer
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO customers (id, name, slug, is_active, created_at, updated_at) "
                "VALUES ('cust-other2', 'Other', 'other2', 1, ?, ?)",
                (_NOW, _NOW),
            )
            conn.execute(
                "INSERT INTO contacts (id, customer_id, name, source, status, created_at, updated_at) "
                "VALUES ('c-foreign', 'cust-other2', 'Foreign', 'test', 'active', ?, ?)",
                (_NOW, _NOW),
            )
        resp = client.post(
            "/views/cell-edit",
            json={"entity_type": "contact", "entity_id": "c-foreign",
                  "field_key": "name", "value": "Hacked"},
        )
        assert resp.status_code == 404

    def test_cell_edit_select_validation(self, client, tmp_db):
        """Rejects invalid select option with 400."""
        _seed_contacts(1)
        resp = client.post(
            "/views/cell-edit",
            json={"entity_type": "contact", "entity_id": "contact-0",
                  "field_key": "status", "value": "bogus_status"},
        )
        assert resp.status_code == 400
        assert "Invalid option" in resp.json()["error"]

    def test_cell_edit_valid_select(self, client, tmp_db):
        """Accepts valid select value."""
        _seed_contacts(1)
        resp = client.post(
            "/views/cell-edit",
            json={"entity_type": "contact", "entity_id": "contact-0",
                  "field_key": "status", "value": "archived"},
        )
        assert resp.status_code == 200
        assert resp.json()["ok"] is True
        assert resp.json()["value"] == "archived"


# ===========================================================================
# Registry Validation Tests (Phase 5)
# ===========================================================================

class TestRegistryEditable:
    def test_editable_fields_have_db_column(self):
        """Every editable field must have db_column set."""
        from poc.views.registry import ENTITY_TYPES
        for et_key, et_def in ENTITY_TYPES.items():
            for fk, fdef in et_def.fields.items():
                if fdef.editable:
                    assert fdef.db_column, (
                        f"{et_key}.{fk}: editable=True but no db_column"
                    )

    def test_editable_fields_not_subqueries(self):
        """Editable fields should have simple SQL (not subqueries)."""
        from poc.views.registry import ENTITY_TYPES
        for et_key, et_def in ENTITY_TYPES.items():
            for fk, fdef in et_def.fields.items():
                if fdef.editable:
                    assert "SELECT" not in fdef.sql.upper(), (
                        f"{et_key}.{fk}: editable field has subquery SQL"
                    )
