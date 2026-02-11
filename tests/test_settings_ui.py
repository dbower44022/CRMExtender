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

class TestProfilePage:
    """Test profile settings page."""

    def test_profile_renders(self, client):
        resp = client.get("/settings/profile")
        assert resp.status_code == 200
        assert "Profile" in resp.text

    def test_profile_save_name(self, client):
        resp = client.post("/settings/profile", data={
            "name": "New Name",
            "timezone": "UTC",
            "start_of_week": "monday",
            "date_format": "ISO",
        })
        assert resp.status_code == 200  # followed redirect
        # Verify name was updated
        from poc.hierarchy import get_user_by_id
        user = get_user_by_id(USER_ID)
        assert user["name"] == "New Name"

    def test_profile_save_timezone(self, client):
        resp = client.post("/settings/profile", data={
            "name": "Admin User",
            "timezone": "US/Eastern",
            "start_of_week": "monday",
            "date_format": "ISO",
        })
        assert resp.status_code == 200
        from poc.settings import get_setting
        tz = get_setting(CUST_ID, "timezone", user_id=USER_ID)
        assert tz == "US/Eastern"

    def test_profile_save_start_of_week(self, client):
        resp = client.post("/settings/profile", data={
            "name": "Admin User",
            "timezone": "UTC",
            "start_of_week": "sunday",
            "date_format": "ISO",
        })
        assert resp.status_code == 200
        from poc.settings import get_setting
        sow = get_setting(CUST_ID, "start_of_week", user_id=USER_ID)
        assert sow == "sunday"

    def test_profile_save_date_format(self, client):
        resp = client.post("/settings/profile", data={
            "name": "Admin User",
            "timezone": "UTC",
            "start_of_week": "monday",
            "date_format": "US",
        })
        assert resp.status_code == 200
        from poc.settings import get_setting
        df = get_setting(CUST_ID, "date_format", user_id=USER_ID)
        assert df == "US"

    def test_password_change_success(self, client, tmp_db):
        # First set an initial password
        from poc.hierarchy import set_user_password
        set_user_password(USER_ID, "oldpass123")

        # Now need to re-monkeypatch to include the password_hash
        # The bypass middleware re-fetches user on each request, so updating
        # the DB is sufficient. But the middleware only gets basic user fields.
        # For password verification, the route reads user from request.state.user
        # which in bypass mode doesn't include password_hash.
        # Actually the route reads user.get("password_hash") which won't be set
        # in bypass mode, so it skips current password check. That's fine for testing.
        resp = client.post("/settings/profile/password", data={
            "current_password": "",
            "new_password": "newpass123",
            "confirm_password": "newpass123",
        })
        assert resp.status_code == 200
        assert "pw_changed" in str(resp.url) or "Password changed" in resp.text

    def test_password_change_mismatch(self, client):
        resp = client.post("/settings/profile/password", data={
            "current_password": "",
            "new_password": "newpass123",
            "confirm_password": "different1",
        })
        assert resp.status_code == 200
        assert "do+not+match" in str(resp.url) or "do not match" in resp.text

    def test_password_change_too_short(self, client):
        resp = client.post("/settings/profile/password", data={
            "current_password": "",
            "new_password": "short",
            "confirm_password": "short",
        })
        assert resp.status_code == 200
        assert "8+characters" in str(resp.url) or "8 characters" in resp.text


# ---------------------------------------------------------------------------
# System Settings
# ---------------------------------------------------------------------------

class TestSystemSettings:
    """Test system settings page (admin only)."""

    def test_system_renders_for_admin(self, client):
        resp = client.get("/settings/system")
        assert resp.status_code == 200
        assert "System Settings" in resp.text

    def test_system_403_for_non_admin(self, regular_client):
        resp = regular_client.get("/settings/system")
        assert resp.status_code == 403

    def test_system_save_company_name(self, client):
        resp = client.post("/settings/system", data={
            "company_name": "Acme Corp",
            "default_timezone": "UTC",
            "sync_enabled": "true",
        })
        assert resp.status_code == 200
        from poc.settings import get_setting
        name = get_setting(CUST_ID, "company_name")
        assert name == "Acme Corp"

    def test_system_save_default_timezone(self, client):
        resp = client.post("/settings/system", data={
            "company_name": "Test Org",
            "default_timezone": "US/Pacific",
            "sync_enabled": "true",
        })
        assert resp.status_code == 200
        from poc.settings import get_setting
        tz = get_setting(CUST_ID, "default_timezone")
        assert tz == "US/Pacific"

    def test_system_save_sync_enabled(self, client):
        resp = client.post("/settings/system", data={
            "company_name": "Test Org",
            "default_timezone": "UTC",
            # sync_enabled checkbox not included = unchecked
        })
        assert resp.status_code == 200
        from poc.settings import get_setting
        sync = get_setting(CUST_ID, "sync_enabled")
        assert sync == "false"


# ---------------------------------------------------------------------------
# User Management
# ---------------------------------------------------------------------------

class TestUserManagement:
    """Test user management pages (admin only)."""

    def test_users_list_renders(self, client):
        resp = client.get("/settings/users")
        assert resp.status_code == 200
        assert "admin@test.com" in resp.text
        assert "regular@test.com" in resp.text

    def test_users_list_403_for_non_admin(self, regular_client):
        resp = regular_client.get("/settings/users")
        assert resp.status_code == 403

    def test_create_user_success(self, client):
        resp = client.post("/settings/users", data={
            "email": "created@test.com",
            "name": "Created User",
            "role": "user",
            "password": "password123",
        })
        assert resp.status_code == 200  # followed redirect to users list

        from poc.hierarchy import get_user_by_id, list_users
        users = list_users(CUST_ID)
        emails = [u["email"] for u in users]
        assert "created@test.com" in emails

    def test_create_user_duplicate_email(self, client):
        resp = client.post("/settings/users", data={
            "email": "admin@test.com",
            "name": "Dup",
            "role": "user",
        })
        assert resp.status_code == 200
        assert "already+exists" in str(resp.url) or "already exists" in resp.text

    def test_edit_user_renders(self, client):
        resp = client.get(f"/settings/users/{USER_REGULAR_ID}/edit")
        assert resp.status_code == 200
        assert "regular@test.com" in resp.text

    def test_edit_user_save(self, client):
        resp = client.post(f"/settings/users/{USER_REGULAR_ID}/edit", data={
            "name": "Edited Regular",
            "role": "admin",
        })
        assert resp.status_code == 200

        from poc.hierarchy import get_user_by_id
        user = get_user_by_id(USER_REGULAR_ID)
        assert user["name"] == "Edited Regular"
        assert user["role"] == "admin"

    def test_set_user_password(self, client):
        resp = client.post(f"/settings/users/{USER_REGULAR_ID}/password", data={
            "new_password": "newpass123",
            "confirm_password": "newpass123",
        })
        assert resp.status_code == 200

        from poc.hierarchy import get_user_by_id
        user = get_user_by_id(USER_REGULAR_ID)
        assert user["password_hash"]  # should be set

    def test_toggle_user_active(self, client):
        resp = client.post(f"/settings/users/{USER_REGULAR_ID}/toggle-active")
        assert resp.status_code == 200

        from poc.hierarchy import get_user_by_id
        user = get_user_by_id(USER_REGULAR_ID)
        assert not user["is_active"]

    def test_cannot_deactivate_self(self, client):
        resp = client.post(f"/settings/users/{USER_ID}/toggle-active")
        assert resp.status_code == 200
        # Should still be active
        from poc.hierarchy import get_user_by_id
        user = get_user_by_id(USER_ID)
        assert user["is_active"]


# ---------------------------------------------------------------------------
# Per-User Timezone
# ---------------------------------------------------------------------------

class TestPerUserTimezone:
    """Test that per-user timezone overrides the default meta tag."""

    def test_default_timezone_meta_tag(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        # Default timezone from config should be in meta tag
        assert 'content="' in resp.text
        assert 'crm-timezone' in resp.text

    def test_user_timezone_overrides_meta(self, client):
        # Set a user-specific timezone
        from poc.settings import set_setting
        set_setting(CUST_ID, "timezone", "US/Eastern",
                    scope="user", user_id=USER_ID)

        resp = client.get("/")
        assert resp.status_code == 200
        assert 'content="US/Eastern"' in resp.text

    def test_system_timezone_cascade(self, client):
        # Set system-level timezone (no user override)
        from poc.settings import set_setting
        set_setting(CUST_ID, "timezone", "Europe/London", scope="system")

        resp = client.get("/")
        assert resp.status_code == 200
        # System timezone cascades when no user-level override
        assert 'content="Europe/London"' in resp.text
