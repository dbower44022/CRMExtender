"""Tests for Settings UI (Phase 4).

Covers: data layer functions, profile page, system settings,
user management, and per-user timezone.
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


# ---------------------------------------------------------------------------
# Data Layer
# ---------------------------------------------------------------------------

class TestDataLayer:
    """Test user management functions in hierarchy.py."""

    def test_list_users(self, tmp_db):
        from poc.hierarchy import list_users
        users = list_users(CUST_ID)
        assert len(users) == 2
        emails = {u["email"] for u in users}
        assert "admin@test.com" in emails
        assert "regular@test.com" in emails

    def test_get_user_by_id(self, tmp_db):
        from poc.hierarchy import get_user_by_id
        user = get_user_by_id(USER_ID)
        assert user is not None
        assert user["email"] == "admin@test.com"

    def test_get_user_by_id_not_found(self, tmp_db):
        from poc.hierarchy import get_user_by_id
        user = get_user_by_id("nonexistent")
        assert user is None

    def test_create_user(self, tmp_db):
        from poc.hierarchy import create_user
        row = create_user(CUST_ID, "new@test.com", "New User", "user",
                          password="testpass123")
        assert row["email"] == "new@test.com"
        assert row["role"] == "user"
        assert row["password_hash"]  # should be set

    def test_create_user_duplicate_email(self, tmp_db):
        from poc.hierarchy import create_user
        with pytest.raises(ValueError, match="already exists"):
            create_user(CUST_ID, "admin@test.com", "Dup", "user")

    def test_update_user(self, tmp_db):
        from poc.hierarchy import update_user, get_user_by_id
        result = update_user(USER_ID, name="Updated Name", role="user")
        assert result is not None
        assert result["name"] == "Updated Name"
        assert result["role"] == "user"
        # Verify via get
        user = get_user_by_id(USER_ID)
        assert user["name"] == "Updated Name"


# ---------------------------------------------------------------------------
# Profile Page
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# System Settings
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# User Management
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Per-User Timezone
# ---------------------------------------------------------------------------

