"""Tests for Google OAuth ("Sign in with Google").

Covers: config loading, data layer (get_user_by_google_sub, set_google_sub),
OAuth initiate route, OAuth callback route, login page button.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from poc.database import get_connection, init_db

_NOW = datetime.now(timezone.utc).isoformat()

CUST_ID = "cust-test"
USER_ID = "user-admin"
USER_EMAIL = "admin@test.com"
GOOGLE_SUB = "google-sub-12345"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def tmp_db(tmp_path, monkeypatch):
    """Create a DB with one customer and one admin user."""
    db_file = tmp_path / "test.db"
    monkeypatch.setattr("poc.config.DB_PATH", db_file)
    monkeypatch.setattr("poc.config.CRM_AUTH_ENABLED", True)
    init_db(db_file)

    with get_connection() as conn:
        conn.execute(
            "INSERT INTO customers (id, name, slug, is_active, created_at, updated_at) "
            "VALUES (?, 'Test Org', 'test', 1, ?, ?)",
            (CUST_ID, _NOW, _NOW),
        )
        conn.execute(
            "INSERT INTO users "
            "(id, customer_id, email, name, role, is_active, password_hash, created_at, updated_at) "
            "VALUES (?, ?, ?, 'Admin User', 'admin', 1, '', ?, ?)",
            (USER_ID, CUST_ID, USER_EMAIL, _NOW, _NOW),
        )

    return db_file


@pytest.fixture()
def auth_client(tmp_db, monkeypatch):
    """Client with CRM_AUTH_ENABLED=true and Google OAuth configured."""
    monkeypatch.setattr("poc.config.GOOGLE_OAUTH_CLIENT_ID", "test-client-id")
    monkeypatch.setattr("poc.config.GOOGLE_OAUTH_CLIENT_SECRET", "test-client-secret")
    from poc.web.app import create_app
    app = create_app()
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture()
def no_google_client(tmp_db, monkeypatch):
    """Client with Google OAuth NOT configured."""
    monkeypatch.setattr("poc.config.GOOGLE_OAUTH_CLIENT_ID", "")
    monkeypatch.setattr("poc.config.GOOGLE_OAUTH_CLIENT_SECRET", "")
    from poc.web.app import create_app
    app = create_app()
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

class TestConfig:

    def test_google_oauth_config_loads_from_file(self, tmp_path, monkeypatch):
        """Config loads client_id and client_secret from client_secret.json."""
        secret_file = tmp_path / "client_secret.json"
        secret_file.write_text(json.dumps({
            "installed": {
                "client_id": "my-client-id.apps.googleusercontent.com",
                "client_secret": "my-secret",
            }
        }))
        monkeypatch.setattr("poc.config.CLIENT_SECRET_PATH", secret_file)
        from poc.config import _load_google_oauth_config
        cid, csec = _load_google_oauth_config()
        assert cid == "my-client-id.apps.googleusercontent.com"
        assert csec == "my-secret"

    def test_google_oauth_config_missing_file(self, tmp_path, monkeypatch):
        """Returns empty strings when file doesn't exist."""
        monkeypatch.setattr("poc.config.CLIENT_SECRET_PATH", tmp_path / "missing.json")
        from poc.config import _load_google_oauth_config
        cid, csec = _load_google_oauth_config()
        assert cid == ""
        assert csec == ""


# ---------------------------------------------------------------------------
# Data Layer
# ---------------------------------------------------------------------------

class TestDataLayer:

    def test_get_user_by_google_sub_found(self, tmp_db):
        """Look up user by google_sub after linking."""
        from poc.hierarchy import get_user_by_google_sub, set_google_sub
        set_google_sub(USER_ID, GOOGLE_SUB)
        user = get_user_by_google_sub(GOOGLE_SUB)
        assert user is not None
        assert user["id"] == USER_ID
        assert user["google_sub"] == GOOGLE_SUB

    def test_get_user_by_google_sub_not_found(self, tmp_db):
        """Returns None for unknown google_sub."""
        from poc.hierarchy import get_user_by_google_sub
        assert get_user_by_google_sub("nonexistent-sub") is None

    def test_set_google_sub(self, tmp_db):
        """set_google_sub links a Google ID to an existing user."""
        from poc.hierarchy import set_google_sub, get_user_by_id
        result = set_google_sub(USER_ID, GOOGLE_SUB)
        assert result is True
        user = get_user_by_id(USER_ID)
        assert user["google_sub"] == GOOGLE_SUB

    def test_set_google_sub_nonexistent_user(self, tmp_db):
        """set_google_sub returns False for nonexistent user."""
        from poc.hierarchy import set_google_sub
        result = set_google_sub("nonexistent-user", GOOGLE_SUB)
        assert result is False


# ---------------------------------------------------------------------------
# Google Auth Initiate
# ---------------------------------------------------------------------------

class TestGoogleAuthInitiate:

    def test_redirects_to_google(self, auth_client):
        """GET /auth/google redirects to accounts.google.com."""
        resp = auth_client.get("/auth/google", follow_redirects=False)
        assert resp.status_code == 302
        location = resp.headers["location"]
        assert "accounts.google.com" in location
        assert "test-client-id" in location
        assert "openid" in location

    def test_sets_state_cookie(self, auth_client):
        """GET /auth/google sets an oauth_state cookie."""
        resp = auth_client.get("/auth/google", follow_redirects=False)
        assert "oauth_state" in resp.cookies

    def test_state_in_url_matches_cookie(self, auth_client):
        """The state param in the redirect URL matches the cookie."""
        resp = auth_client.get("/auth/google", follow_redirects=False)
        cookie_state = resp.cookies["oauth_state"]
        location = resp.headers["location"]
        assert f"state={cookie_state}" in location

    def test_not_configured_redirects_to_login(self, no_google_client):
        """GET /auth/google redirects to login with error when not configured."""
        resp = no_google_client.get("/auth/google", follow_redirects=False)
        assert resp.status_code == 302
        assert "/login" in resp.headers["location"]
        assert "not+configured" in resp.headers["location"]


# ---------------------------------------------------------------------------
# Google Auth Callback
# ---------------------------------------------------------------------------

def _mock_token_exchange(id_token_payload):
    """Create a mock for httpx.AsyncClient.post that returns a fake token response."""
    import httpx

    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"id_token": "fake-jwt-token"}
    mock_resp.raise_for_status = MagicMock()
    return mock_resp


class TestGoogleAuthCallback:

    def test_state_mismatch(self, auth_client):
        """Callback with mismatched state returns error."""
        resp = auth_client.get(
            "/auth/google/callback?state=bad&code=fake",
            cookies={"oauth_state": "good"},
            follow_redirects=False,
        )
        assert resp.status_code == 302
        assert "Invalid+OAuth+state" in resp.headers["location"]

    def test_missing_state(self, auth_client):
        """Callback with no state returns error."""
        resp = auth_client.get(
            "/auth/google/callback?code=fake",
            follow_redirects=False,
        )
        assert resp.status_code == 302
        assert "Invalid+OAuth+state" in resp.headers["location"]

    def test_error_param(self, auth_client):
        """Callback with error param (user denied) returns error."""
        resp = auth_client.get(
            "/auth/google/callback?error=access_denied",
            follow_redirects=False,
        )
        assert resp.status_code == 302
        assert "cancelled" in resp.headers["location"]

    def test_success_existing_user(self, auth_client, tmp_db):
        """Successful callback with matching email creates session."""
        state = str(uuid.uuid4())

        with patch("poc.web.routes.auth_routes.httpx.AsyncClient") as mock_client_cls, \
             patch("poc.web.routes.auth_routes.google_id_token.verify_oauth2_token") as mock_verify:

            # Mock token exchange
            mock_client = MagicMock()
            mock_client_cls.return_value.__aenter__ = lambda self: _async_return(mock_client)
            mock_client_cls.return_value.__aexit__ = lambda self, *a: _async_return(None)
            mock_resp = MagicMock()
            mock_resp.json.return_value = {"id_token": "fake-jwt"}
            mock_resp.raise_for_status = MagicMock()
            mock_client.post = lambda *a, **kw: _async_return(mock_resp)

            # Mock ID token verification
            mock_verify.return_value = {
                "sub": GOOGLE_SUB,
                "email": USER_EMAIL,
                "name": "Admin User",
            }

            resp = auth_client.get(
                f"/auth/google/callback?state={state}&code=authcode123",
                cookies={"oauth_state": state},
                follow_redirects=False,
            )

        assert resp.status_code == 302
        location = resp.headers["location"]
        # Should redirect to home, not login
        assert location.rstrip("/") == "" or location == "/" or "testserver/" in location
        # Session cookie should be set
        assert "crm_session" in resp.cookies

    def test_callback_links_google_sub(self, auth_client, tmp_db):
        """First Google login links google_sub to user matched by email."""
        state = str(uuid.uuid4())

        with patch("poc.web.routes.auth_routes.httpx.AsyncClient") as mock_client_cls, \
             patch("poc.web.routes.auth_routes.google_id_token.verify_oauth2_token") as mock_verify:

            mock_client = MagicMock()
            mock_client_cls.return_value.__aenter__ = lambda self: _async_return(mock_client)
            mock_client_cls.return_value.__aexit__ = lambda self, *a: _async_return(None)
            mock_resp = MagicMock()
            mock_resp.json.return_value = {"id_token": "fake-jwt"}
            mock_resp.raise_for_status = MagicMock()
            mock_client.post = lambda *a, **kw: _async_return(mock_resp)

            mock_verify.return_value = {
                "sub": GOOGLE_SUB,
                "email": USER_EMAIL,
                "name": "Admin User",
            }

            resp = auth_client.get(
                f"/auth/google/callback?state={state}&code=authcode123",
                cookies={"oauth_state": state},
                follow_redirects=False,
            )

        assert resp.status_code == 302
        # Verify google_sub was linked
        from poc.hierarchy import get_user_by_id
        user = get_user_by_id(USER_ID)
        assert user["google_sub"] == GOOGLE_SUB

    def test_callback_matches_by_google_sub(self, auth_client, tmp_db):
        """User with existing google_sub is found directly."""
        from poc.hierarchy import set_google_sub
        set_google_sub(USER_ID, GOOGLE_SUB)

        state = str(uuid.uuid4())

        with patch("poc.web.routes.auth_routes.httpx.AsyncClient") as mock_client_cls, \
             patch("poc.web.routes.auth_routes.google_id_token.verify_oauth2_token") as mock_verify:

            mock_client = MagicMock()
            mock_client_cls.return_value.__aenter__ = lambda self: _async_return(mock_client)
            mock_client_cls.return_value.__aexit__ = lambda self, *a: _async_return(None)
            mock_resp = MagicMock()
            mock_resp.json.return_value = {"id_token": "fake-jwt"}
            mock_resp.raise_for_status = MagicMock()
            mock_client.post = lambda *a, **kw: _async_return(mock_resp)

            mock_verify.return_value = {
                "sub": GOOGLE_SUB,
                "email": USER_EMAIL,
                "name": "Admin User",
            }

            resp = auth_client.get(
                f"/auth/google/callback?state={state}&code=authcode123",
                cookies={"oauth_state": state},
                follow_redirects=False,
            )

        assert resp.status_code == 302
        assert "crm_session" in resp.cookies

    def test_callback_no_matching_user(self, auth_client, tmp_db):
        """Callback with unknown email redirects with error."""
        state = str(uuid.uuid4())

        with patch("poc.web.routes.auth_routes.httpx.AsyncClient") as mock_client_cls, \
             patch("poc.web.routes.auth_routes.google_id_token.verify_oauth2_token") as mock_verify:

            mock_client = MagicMock()
            mock_client_cls.return_value.__aenter__ = lambda self: _async_return(mock_client)
            mock_client_cls.return_value.__aexit__ = lambda self, *a: _async_return(None)
            mock_resp = MagicMock()
            mock_resp.json.return_value = {"id_token": "fake-jwt"}
            mock_resp.raise_for_status = MagicMock()
            mock_client.post = lambda *a, **kw: _async_return(mock_resp)

            mock_verify.return_value = {
                "sub": "unknown-sub",
                "email": "unknown@example.com",
                "name": "Unknown",
            }

            resp = auth_client.get(
                f"/auth/google/callback?state={state}&code=authcode123",
                cookies={"oauth_state": state},
                follow_redirects=False,
            )

        assert resp.status_code == 302
        assert "No+account+found" in resp.headers["location"]


# ---------------------------------------------------------------------------
# Login Page
# ---------------------------------------------------------------------------

class TestLoginPage:

    def test_shows_google_button_when_configured(self, auth_client):
        """Login page shows 'Sign in with Google' when OAuth is configured."""
        resp = auth_client.get("/login")
        assert resp.status_code == 200
        assert "Sign in with Google" in resp.text

    def test_hides_google_button_when_not_configured(self, no_google_client):
        """Login page hides Google button when no client_id."""
        resp = no_google_client.get("/login")
        assert resp.status_code == 200
        assert "Sign in with Google" not in resp.text

    def test_login_page_shows_oauth_error(self, auth_client):
        """Login page displays error from query param."""
        resp = auth_client.get("/login?error=No+account+found+for+this+email")
        assert resp.status_code == 200
        assert "No account found for this email" in resp.text


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _async_return(value):
    """Helper to make a coroutine that returns a value."""
    return value
