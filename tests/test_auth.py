"""Tests for authentication: passwords, login, logout, middleware, bypass."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from poc.database import get_connection, init_db
from poc.passwords import hash_password, verify_password

_NOW = datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _seed_users(db_file):
    """Insert customer + two users (admin with password, regular without)."""
    with get_connection(db_file) as conn:
        conn.execute(
            "INSERT INTO customers (id, name, slug, is_active, created_at, updated_at) "
            "VALUES ('cust-test', 'Test Org', 'test', 1, ?, ?)",
            (_NOW, _NOW),
        )
        conn.execute(
            "INSERT INTO users "
            "(id, customer_id, email, name, role, is_active, password_hash, "
            "created_at, updated_at) "
            "VALUES ('user-admin', 'cust-test', 'admin@example.com', 'Admin', "
            "'admin', 1, ?, ?, ?)",
            (hash_password("secret123"), _NOW, _NOW),
        )
        conn.execute(
            "INSERT INTO users "
            "(id, customer_id, email, name, role, is_active, password_hash, "
            "created_at, updated_at) "
            "VALUES ('user-regular', 'cust-test', 'user@example.com', 'Regular', "
            "'user', 1, ?, ?, ?)",
            (hash_password("userpass"), _NOW, _NOW),
        )


@pytest.fixture()
def tmp_db(tmp_path, monkeypatch):
    db_file = tmp_path / "test.db"
    monkeypatch.setattr("poc.config.DB_PATH", db_file)
    init_db(db_file)
    _seed_users(db_file)
    return db_file


@pytest.fixture()
def auth_client(tmp_db, monkeypatch):
    """Client with CRM_AUTH_ENABLED=true."""
    monkeypatch.setattr("poc.config.CRM_AUTH_ENABLED", True)
    from poc.web.app import create_app
    app = create_app()
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture()
def bypass_client(tmp_db, monkeypatch):
    """Client with CRM_AUTH_ENABLED=false."""
    monkeypatch.setattr("poc.config.CRM_AUTH_ENABLED", False)
    from poc.web.app import create_app
    app = create_app()
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Passwords
# ---------------------------------------------------------------------------

class TestPasswords:
    def test_hash_and_verify(self):
        hashed = hash_password("my-password")
        assert verify_password("my-password", hashed)

    def test_wrong_password_fails(self):
        hashed = hash_password("correct")
        assert not verify_password("wrong", hashed)

    def test_different_hashes(self):
        h1 = hash_password("same")
        h2 = hash_password("same")
        assert h1 != h2  # different salts
        assert verify_password("same", h1)
        assert verify_password("same", h2)


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------

class TestLogin:
    def test_login_page_renders(self, auth_client):
        resp = auth_client.get("/login", follow_redirects=False)
        assert resp.status_code == 200
        assert "Sign in" in resp.text

    def test_login_success(self, auth_client):
        resp = auth_client.post("/login", data={
            "email": "admin@example.com",
            "password": "secret123",
        }, follow_redirects=False)
        assert resp.status_code == 303
        assert resp.headers["location"] == "/"
        assert "crm_session" in resp.cookies

    def test_login_wrong_password(self, auth_client):
        resp = auth_client.post("/login", data={
            "email": "admin@example.com",
            "password": "wrong",
        })
        assert resp.status_code == 401
        assert "Invalid email or password" in resp.text

    def test_login_unknown_email(self, auth_client):
        resp = auth_client.post("/login", data={
            "email": "nobody@example.com",
            "password": "whatever",
        })
        assert resp.status_code == 401
        assert "Invalid email or password" in resp.text

    def test_login_no_password_hash(self, auth_client, tmp_db):
        """User without password_hash cannot log in."""
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO users "
                "(id, customer_id, email, name, role, is_active, "
                "created_at, updated_at) "
                "VALUES ('user-nopw', 'cust-test', 'nopw@example.com', 'NoPW', "
                "'user', 1, ?, ?)",
                (_NOW, _NOW),
            )

        resp = auth_client.post("/login", data={
            "email": "nopw@example.com",
            "password": "anything",
        })
        assert resp.status_code == 401

    def test_login_redirects_if_already_authed(self, auth_client):
        """GET /login when already authenticated redirects to /."""
        # First log in
        auth_client.post("/login", data={
            "email": "admin@example.com",
            "password": "secret123",
        })
        # Now visit login page
        resp = auth_client.get("/login", follow_redirects=False)
        assert resp.status_code == 302
        assert resp.headers["location"] == "/"


# ---------------------------------------------------------------------------
# Logout
# ---------------------------------------------------------------------------

class TestLogout:
    def test_logout_clears_session(self, auth_client):
        # Login first
        auth_client.post("/login", data={
            "email": "admin@example.com",
            "password": "secret123",
        })

        resp = auth_client.post("/logout", follow_redirects=False)
        assert resp.status_code == 303
        assert resp.headers["location"] == "/login"
        # Cookie should be cleared
        assert resp.cookies.get("crm_session") is None or resp.cookies["crm_session"] == ""

        # Subsequent requests should redirect to login
        resp2 = auth_client.get("/", follow_redirects=False)
        assert resp2.status_code == 302


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------

class TestMiddleware:
    def test_unauthenticated_redirects_to_login(self, auth_client):
        resp = auth_client.get("/", follow_redirects=False)
        assert resp.status_code == 302
        assert "/login" in resp.headers["location"]

    def test_static_files_are_public(self, auth_client):
        resp = auth_client.get("/static/style.css")
        assert resp.status_code == 200

    def test_valid_session_allows_access(self, auth_client):
        # Login
        auth_client.post("/login", data={
            "email": "admin@example.com",
            "password": "secret123",
        })
        resp = auth_client.get("/")
        assert resp.status_code == 200
        assert "Dashboard" in resp.text

    def test_invalid_cookie_redirects(self, auth_client):
        auth_client.cookies.set("crm_session", "bogus-session-id")
        resp = auth_client.get("/", follow_redirects=False)
        assert resp.status_code == 302

    def test_user_name_in_nav(self, auth_client):
        auth_client.post("/login", data={
            "email": "admin@example.com",
            "password": "secret123",
        })
        resp = auth_client.get("/")
        assert "Admin" in resp.text
        assert "Logout" in resp.text


# ---------------------------------------------------------------------------
# Auth Bypass
# ---------------------------------------------------------------------------

class TestAuthBypass:
    def test_bypass_allows_access_without_login(self, bypass_client):
        resp = bypass_client.get("/")
        assert resp.status_code == 200
        assert "Dashboard" in resp.text

    def test_bypass_sets_user_context(self, bypass_client):
        resp = bypass_client.get("/")
        assert resp.status_code == 200
        # User name should appear in nav
        assert "Logout" in resp.text


# ---------------------------------------------------------------------------
# Admin dependency
# ---------------------------------------------------------------------------

class TestAdminDependency:
    def test_dependency_functions(self):
        """Test get_current_user and require_admin as plain functions."""
        from unittest.mock import MagicMock
        from fastapi import HTTPException
        from poc.web.dependencies import get_current_user, require_admin

        # No user
        req = MagicMock()
        req.state.user = None
        with pytest.raises(HTTPException) as exc_info:
            get_current_user(req)
        assert exc_info.value.status_code == 401

        # Admin user
        req.state.user = {"id": "u1", "role": "admin"}
        assert require_admin(req)["id"] == "u1"

        # Non-admin user
        req.state.user = {"id": "u2", "role": "user"}
        with pytest.raises(HTTPException) as exc_info:
            require_admin(req)
        assert exc_info.value.status_code == 403
