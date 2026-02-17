"""Tests for Provider Accounts CRUD (Settings > Accounts)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

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


def _make_client(monkeypatch):
    monkeypatch.setattr(
        "poc.hierarchy.get_current_user",
        lambda: {"id": USER_ID, "email": "admin@test.com", "name": "Admin User",
                 "role": "admin", "customer_id": CUST_ID},
    )
    from poc.web.app import create_app
    app = create_app()
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture()
def client(tmp_db, monkeypatch):
    return _make_client(monkeypatch)


def _insert_account(account_id="acct-1", email="sync@example.com",
                    is_active=1, customer_id=CUST_ID):
    """Insert a provider_accounts row and user_provider_accounts link."""
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO provider_accounts
               (id, customer_id, provider, account_type, email_address,
                auth_token_path, is_active, created_at, updated_at)
               VALUES (?, ?, 'gmail', 'email', ?, '/tmp/token.json', ?, ?, ?)""",
            (account_id, customer_id, email, is_active, _NOW, _NOW),
        )
        conn.execute(
            """INSERT INTO user_provider_accounts
               (id, user_id, account_id, role, created_at)
               VALUES (?, ?, ?, 'owner', ?)""",
            (str(uuid.uuid4()), USER_ID, account_id, _NOW),
        )


# ---------------------------------------------------------------------------
# Accounts list
# ---------------------------------------------------------------------------

class TestAccountsList:
    def test_accounts_page_loads(self, client):
        resp = client.get("/settings/accounts")
        assert resp.status_code == 200
        assert "Connected Accounts" in resp.text

    def test_accounts_page_shows_accounts(self, client):
        _insert_account()
        resp = client.get("/settings/accounts")
        assert resp.status_code == 200
        assert "sync@example.com" in resp.text
        assert "Active" in resp.text

    def test_accounts_page_empty(self, client):
        resp = client.get("/settings/accounts")
        assert resp.status_code == 200
        assert "No accounts connected" in resp.text

    def test_accounts_connect_redirects_to_google(self, client, monkeypatch):
        monkeypatch.setattr("poc.config.GOOGLE_OAUTH_CLIENT_ID", "test-client-id")
        resp = client.get("/settings/accounts/connect", follow_redirects=False)
        assert resp.status_code == 302
        location = resp.headers["location"]
        assert "accounts.google.com" in location
        assert "gmail.readonly" in location
        assert "calendar.readonly" in location
        assert "contacts.readonly" in location
        assert "openid" in location
        assert "email" in location
        assert "access_type=offline" in location
        assert "prompt=consent" in location
        # Should set oauth_purpose cookie
        assert resp.cookies.get("oauth_purpose") == "add-account"

    def test_accounts_connect_no_oauth_configured(self, client, monkeypatch):
        monkeypatch.setattr("poc.config.GOOGLE_OAUTH_CLIENT_ID", "")
        resp = client.get("/settings/accounts/connect", follow_redirects=False)
        assert resp.status_code == 302
        assert "/settings/accounts" in resp.headers["location"]
        assert "not+configured" in resp.headers["location"]


# ---------------------------------------------------------------------------
# Edit
# ---------------------------------------------------------------------------

class TestAccountsEdit:
    def test_edit_form_loads(self, client):
        _insert_account()
        resp = client.get("/settings/accounts/acct-1/edit")
        assert resp.status_code == 200
        assert "Edit Account" in resp.text
        assert "sync@example.com" in resp.text

    def test_edit_saves_display_name(self, client):
        _insert_account()
        resp = client.post(
            "/settings/accounts/acct-1/edit",
            data={"display_name": "My Gmail"},
            follow_redirects=False,
        )
        assert resp.status_code == 303
        assert "/settings/accounts" in resp.headers["location"]

        # Verify in DB
        with get_connection() as conn:
            row = conn.execute(
                "SELECT display_name FROM provider_accounts WHERE id = 'acct-1'",
            ).fetchone()
        assert row["display_name"] == "My Gmail"

    def test_edit_nonexistent_redirects(self, client):
        resp = client.get("/settings/accounts/nonexistent/edit", follow_redirects=False)
        assert resp.status_code == 303
        assert "/settings/accounts" in resp.headers["location"]


# ---------------------------------------------------------------------------
# Toggle active
# ---------------------------------------------------------------------------

class TestAccountsToggleActive:
    def test_toggle_deactivates_account(self, client):
        _insert_account()
        resp = client.post(
            "/settings/accounts/acct-1/toggle-active",
            follow_redirects=False,
        )
        assert resp.status_code == 303

        with get_connection() as conn:
            row = conn.execute(
                "SELECT is_active FROM provider_accounts WHERE id = 'acct-1'",
            ).fetchone()
        assert row["is_active"] == 0

    def test_toggle_reactivates_account(self, client):
        _insert_account(is_active=0)
        resp = client.post(
            "/settings/accounts/acct-1/toggle-active",
            follow_redirects=False,
        )
        assert resp.status_code == 303

        with get_connection() as conn:
            row = conn.execute(
                "SELECT is_active FROM provider_accounts WHERE id = 'acct-1'",
            ).fetchone()
        assert row["is_active"] == 1

    def test_toggle_nonexistent_redirects(self, client):
        resp = client.post(
            "/settings/accounts/nonexistent/toggle-active",
            follow_redirects=False,
        )
        assert resp.status_code == 303


# ---------------------------------------------------------------------------
# OAuth callback (add-account flow)
# ---------------------------------------------------------------------------

class TestAccountsCallback:
    def test_callback_add_account_creates_provider(self, tmp_db, monkeypatch, tmp_path):
        """Full flow: oauth_purpose=add-account cookie + code exchange creates account."""
        monkeypatch.setattr("poc.config.GOOGLE_OAUTH_CLIENT_ID", "test-client-id")
        monkeypatch.setattr("poc.config.GOOGLE_OAUTH_CLIENT_SECRET", "test-secret")
        monkeypatch.setattr("poc.config.CREDENTIALS_DIR", tmp_path / "creds")
        (tmp_path / "creds").mkdir()

        client = _make_client(monkeypatch)

        state = "test-state-123"

        # Mock the token exchange and ID token verification
        mock_token_resp = MagicMock()
        mock_token_resp.json.return_value = {
            "access_token": "access-token-123",
            "refresh_token": "refresh-token-123",
            "id_token": "fake-id-token",
        }
        mock_token_resp.raise_for_status = MagicMock()

        mock_idinfo = {
            "sub": "google-sub-123",
            "email": "newaccount@example.com",
        }

        with patch("poc.web.routes.auth_routes.httpx.AsyncClient") as mock_httpx, \
             patch("poc.web.routes.auth_routes.google_id_token.verify_oauth2_token",
                   return_value=mock_idinfo):
            mock_client_instance = AsyncMock()
            mock_client_instance.post.return_value = mock_token_resp
            mock_httpx.return_value.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_httpx.return_value.__aexit__ = AsyncMock(return_value=False)

            # Set cookies: session (for auth) + oauth_state + oauth_purpose
            client.cookies.set("oauth_state", state)
            client.cookies.set("oauth_purpose", "add-account")

            resp = client.get(
                f"/auth/google/callback?code=auth-code-123&state={state}",
                follow_redirects=False,
            )

        assert resp.status_code == 302
        assert "/settings/accounts" in resp.headers["location"]
        assert "saved=1" in resp.headers["location"]

        # Verify account was created
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM provider_accounts WHERE email_address = 'newaccount@example.com'",
            ).fetchone()
            assert row is not None
            assert row["provider"] == "gmail"
            assert row["customer_id"] == CUST_ID
            assert row["is_active"] == 1

            # Verify user_provider_accounts link
            upa = conn.execute(
                "SELECT * FROM user_provider_accounts WHERE account_id = ?",
                (row["id"],),
            ).fetchone()
            assert upa is not None
            assert upa["user_id"] == USER_ID
            assert upa["role"] == "owner"

    def test_callback_add_account_duplicate_email(self, tmp_db, monkeypatch, tmp_path):
        """Shows error for duplicate email."""
        monkeypatch.setattr("poc.config.GOOGLE_OAUTH_CLIENT_ID", "test-client-id")
        monkeypatch.setattr("poc.config.GOOGLE_OAUTH_CLIENT_SECRET", "test-secret")
        monkeypatch.setattr("poc.config.CREDENTIALS_DIR", tmp_path / "creds")
        (tmp_path / "creds").mkdir()

        # Insert existing account
        _insert_account(email="existing@example.com")

        client = _make_client(monkeypatch)
        state = "test-state-456"

        mock_token_resp = MagicMock()
        mock_token_resp.json.return_value = {
            "access_token": "access-token",
            "refresh_token": "refresh-token",
            "id_token": "fake-id-token",
        }
        mock_token_resp.raise_for_status = MagicMock()

        mock_idinfo = {
            "sub": "google-sub-456",
            "email": "existing@example.com",
        }

        with patch("poc.web.routes.auth_routes.httpx.AsyncClient") as mock_httpx, \
             patch("poc.web.routes.auth_routes.google_id_token.verify_oauth2_token",
                   return_value=mock_idinfo):
            mock_client_instance = AsyncMock()
            mock_client_instance.post.return_value = mock_token_resp
            mock_httpx.return_value.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_httpx.return_value.__aexit__ = AsyncMock(return_value=False)

            client.cookies.set("oauth_state", state)
            client.cookies.set("oauth_purpose", "add-account")

            resp = client.get(
                f"/auth/google/callback?code=auth-code&state={state}",
                follow_redirects=False,
            )

        assert resp.status_code == 302
        assert "/settings/accounts" in resp.headers["location"]
        assert "already+connected" in resp.headers["location"]

    def test_callback_without_purpose_is_login(self, tmp_db, monkeypatch):
        """Default behavior (no oauth_purpose cookie) attempts login."""
        monkeypatch.setattr("poc.config.GOOGLE_OAUTH_CLIENT_ID", "test-client-id")
        monkeypatch.setattr("poc.config.GOOGLE_OAUTH_CLIENT_SECRET", "test-secret")

        client = _make_client(monkeypatch)
        state = "test-state-789"

        mock_token_resp = MagicMock()
        mock_token_resp.json.return_value = {
            "access_token": "access-token",
            "id_token": "fake-id-token",
        }
        mock_token_resp.raise_for_status = MagicMock()

        mock_idinfo = {
            "sub": "google-sub-789",
            "email": "admin@test.com",
        }

        with patch("poc.web.routes.auth_routes.httpx.AsyncClient") as mock_httpx, \
             patch("poc.web.routes.auth_routes.google_id_token.verify_oauth2_token",
                   return_value=mock_idinfo):
            mock_client_instance = AsyncMock()
            mock_client_instance.post.return_value = mock_token_resp
            mock_httpx.return_value.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_httpx.return_value.__aexit__ = AsyncMock(return_value=False)

            client.cookies.set("oauth_state", state)
            # No oauth_purpose cookie — should follow login flow

            resp = client.get(
                f"/auth/google/callback?code=auth-code&state={state}",
                follow_redirects=False,
            )

        # Login flow redirects to / (dashboard)
        assert resp.status_code == 302
        assert resp.headers["location"] == "/"


# ---------------------------------------------------------------------------
# is_active filtering in sync queries
# ---------------------------------------------------------------------------

class TestActiveFiltering:
    def test_inactive_account_excluded_from_calendar_settings(self, client):
        """Inactive accounts should not appear in calendar settings."""
        _insert_account(is_active=0)
        resp = client.get("/settings/calendars")
        assert resp.status_code == 200
        # Inactive account should not be listed
        assert "sync@example.com" not in resp.text

    def test_active_account_shown_in_calendar_settings(self, client):
        """Active accounts should appear in calendar settings."""
        _insert_account(is_active=1)
        resp = client.get("/settings/calendars")
        assert resp.status_code == 200
        assert "sync@example.com" in resp.text
