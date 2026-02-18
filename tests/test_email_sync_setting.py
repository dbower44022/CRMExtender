"""Tests for email history window system setting and contact-level email sync."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from poc.database import get_connection, init_db
from poc.settings import get_setting, set_setting
from poc.sync import (
    EMAIL_HISTORY_OPTIONS,
    _VALID_WINDOWS,
    _history_window_to_query,
    sync_contact_email,
)

_NOW = datetime.now(timezone.utc).isoformat()

CUST_ID = "cust-test"
USER_ID = "user-admin"
ACCOUNT_ID = "acct-test"
ACCOUNT_EMAIL = "me@mycompany.com"


def _uid() -> str:
    return str(uuid.uuid4())


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
            "VALUES (?, ?, ?, 'Admin', 'admin', 1, ?, ?)",
            (USER_ID, CUST_ID, ACCOUNT_EMAIL, _NOW, _NOW),
        )
    return db_file


def _make_client(monkeypatch):
    monkeypatch.setattr(
        "poc.hierarchy.get_current_user",
        lambda: {"id": USER_ID, "email": ACCOUNT_EMAIL, "name": "Admin",
                 "role": "admin", "customer_id": CUST_ID},
    )
    from poc.web.app import create_app
    app = create_app()
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture()
def client(tmp_db, monkeypatch):
    return _make_client(monkeypatch)


def _create_contact(name: str, email: str) -> str:
    """Insert a contact + email identifier and return contact_id."""
    cid = _uid()
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO contacts "
            "(id, customer_id, name, source, status, created_at, updated_at) "
            "VALUES (?, ?, ?, 'test', 'active', ?, ?)",
            (cid, CUST_ID, name, _NOW, _NOW),
        )
        conn.execute(
            "INSERT INTO contact_identifiers "
            "(id, contact_id, type, value, is_primary, created_at, updated_at) "
            "VALUES (?, ?, 'email', ?, 1, ?, ?)",
            (_uid(), cid, email.lower(), _NOW, _NOW),
        )
        conn.execute(
            "INSERT INTO user_contacts "
            "(id, user_id, contact_id, visibility, is_owner, created_at, updated_at) "
            "VALUES (?, ?, ?, 'public', 1, ?, ?)",
            (_uid(), USER_ID, cid, _NOW, _NOW),
        )
    return cid


def _insert_account(account_id=ACCOUNT_ID, email=ACCOUNT_EMAIL):
    """Insert a provider_accounts row and user_provider_accounts link."""
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO provider_accounts
               (id, customer_id, provider, account_type, email_address,
                auth_token_path, is_active, created_at, updated_at)
               VALUES (?, ?, 'gmail', 'email', ?, '/tmp/token.json', 1, ?, ?)""",
            (account_id, CUST_ID, email, _NOW, _NOW),
        )
        conn.execute(
            """INSERT INTO user_provider_accounts
               (id, user_id, account_id, role, created_at)
               VALUES (?, ?, ?, 'owner', ?)""",
            (_uid(), USER_ID, account_id, _NOW),
        )


# ===========================================================================
# Part 1: System Setting Tests
# ===========================================================================

class TestEmailHistoryWindowSetting:
    def test_default_resolves_to_90d(self, tmp_db):
        """Hardcoded default for email_history_window is 90d."""
        val = get_setting(CUST_ID, "email_history_window")
        assert val == "90d"

    def test_set_and_get(self, tmp_db):
        """Setting persists and retrieves correctly."""
        set_setting(CUST_ID, "email_history_window", "365d", scope="system")
        val = get_setting(CUST_ID, "email_history_window")
        assert val == "365d"

    def test_set_all(self, tmp_db):
        """Setting 'all' persists correctly."""
        set_setting(CUST_ID, "email_history_window", "all", scope="system")
        val = get_setting(CUST_ID, "email_history_window")
        assert val == "all"


class TestHistoryWindowToQuery:
    def test_30d(self):
        assert _history_window_to_query("30d") == "newer_than:30d"

    def test_90d(self):
        assert _history_window_to_query("90d") == "newer_than:90d"

    def test_180d(self):
        assert _history_window_to_query("180d") == "newer_than:180d"

    def test_365d(self):
        assert _history_window_to_query("365d") == "newer_than:365d"

    def test_730d(self):
        assert _history_window_to_query("730d") == "newer_than:730d"

    def test_all_returns_none(self):
        assert _history_window_to_query("all") is None

    def test_all_options_valid(self):
        """All options in EMAIL_HISTORY_OPTIONS are in _VALID_WINDOWS."""
        for value, _label in EMAIL_HISTORY_OPTIONS:
            assert value in _VALID_WINDOWS


class TestSystemSettingsPage:
    def test_system_page_shows_email_history_dropdown(self, client):
        """System settings GET includes the email history dropdown."""
        resp = client.get("/settings/system")
        assert resp.status_code == 200
        assert "email_history_window" in resp.text
        assert "Email history to retrieve" in resp.text
        assert "90 Days" in resp.text
        assert "All Time" in resp.text

    def test_system_page_post_saves_email_history(self, client):
        """System settings POST saves the email_history_window value."""
        resp = client.post("/settings/system", data={
            "company_name": "Test",
            "default_timezone": "UTC",
            "default_phone_country": "US",
            "sync_enabled": "true",
            "email_history_window": "365d",
        }, follow_redirects=False)
        assert resp.status_code == 303

        val = get_setting(CUST_ID, "email_history_window")
        assert val == "365d"

    def test_system_page_post_saves_all(self, client):
        """System settings POST saves 'all' correctly."""
        resp = client.post("/settings/system", data={
            "company_name": "Test",
            "default_timezone": "UTC",
            "default_phone_country": "US",
            "email_history_window": "all",
        }, follow_redirects=False)
        assert resp.status_code == 303

        val = get_setting(CUST_ID, "email_history_window")
        assert val == "all"

    def test_system_page_selected_option(self, tmp_db, monkeypatch):
        """Dropdown shows the current saved value as selected."""
        set_setting(CUST_ID, "email_history_window", "730d", scope="system")
        client = _make_client(monkeypatch)
        resp = client.get("/settings/system")
        assert resp.status_code == 200
        # The 730d option should be selected
        assert 'value="730d" selected' in resp.text


# ===========================================================================
# Part 2: Contact Sync Tests
# ===========================================================================

class TestSyncContactEmail:
    def test_no_email_addresses_returns_empty(self, tmp_db):
        """Contact with no email addresses returns zero counts."""
        cid = _uid()
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO contacts "
                "(id, customer_id, name, source, status, created_at, updated_at) "
                "VALUES (?, ?, 'No Email', 'test', 'active', ?, ?)",
                (cid, CUST_ID, _NOW, _NOW),
            )
        result = sync_contact_email(
            cid, "90d", customer_id=CUST_ID, user_id=USER_ID,
        )
        assert result["messages_fetched"] == 0
        assert result["conversations_created"] == 0

    def test_invalid_window_raises(self, tmp_db):
        """Invalid window value raises ValueError."""
        cid = _create_contact("Test", "test@example.com")
        with pytest.raises(ValueError, match="Invalid window"):
            sync_contact_email(cid, "invalid", customer_id=CUST_ID)

    def test_builds_correct_query_single_email(self, tmp_db):
        """Correct Gmail query is built for a contact with one email."""
        cid = _create_contact("Alice", "alice@example.com")
        _insert_account()

        mock_creds = MagicMock()
        with patch("poc.sync.fetch_threads", return_value=([], None)) as mock_fetch, \
             patch("poc.auth.get_credentials_for_account", return_value=mock_creds):
            sync_contact_email(
                cid, "90d", customer_id=CUST_ID, user_id=USER_ID,
            )

        mock_fetch.assert_called_once()
        call_kwargs = mock_fetch.call_args
        query = call_kwargs[1]["query"] if "query" in call_kwargs[1] else call_kwargs[0][1]
        assert "from:alice@example.com" in query
        assert "to:alice@example.com" in query
        assert "newer_than:90d" in query

    def test_builds_correct_query_multiple_emails(self, tmp_db):
        """Correct Gmail query for contact with multiple emails."""
        cid = _create_contact("Bob", "bob@example.com")
        # Add a second email
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO contact_identifiers "
                "(id, contact_id, type, value, is_primary, created_at, updated_at) "
                "VALUES (?, ?, 'email', ?, 0, ?, ?)",
                (_uid(), cid, "bob@work.com", _NOW, _NOW),
            )
        _insert_account()

        mock_creds = MagicMock()
        with patch("poc.sync.fetch_threads", return_value=([], None)) as mock_fetch, \
             patch("poc.auth.get_credentials_for_account", return_value=mock_creds):
            sync_contact_email(
                cid, "180d", customer_id=CUST_ID, user_id=USER_ID,
            )

        mock_fetch.assert_called_once()
        call_kwargs = mock_fetch.call_args
        query = call_kwargs[1]["query"] if "query" in call_kwargs[1] else call_kwargs[0][1]
        assert "from:bob@example.com" in query
        assert "to:bob@example.com" in query
        assert "from:bob@work.com" in query
        assert "to:bob@work.com" in query
        assert "newer_than:180d" in query

    def test_all_window_no_time_filter(self, tmp_db):
        """Window 'all' results in no time filter in the query."""
        cid = _create_contact("Carol", "carol@example.com")
        _insert_account()

        mock_creds = MagicMock()
        with patch("poc.sync.fetch_threads", return_value=([], None)) as mock_fetch, \
             patch("poc.auth.get_credentials_for_account", return_value=mock_creds):
            sync_contact_email(
                cid, "all", customer_id=CUST_ID, user_id=USER_ID,
            )

        call_kwargs = mock_fetch.call_args
        query = call_kwargs[1]["query"] if "query" in call_kwargs[1] else call_kwargs[0][1]
        assert "newer_than" not in query
        assert "from:carol@example.com" in query

    def test_no_accounts_returns_empty(self, tmp_db):
        """No provider accounts returns zero counts."""
        cid = _create_contact("Dave", "dave@example.com")
        result = sync_contact_email(
            cid, "90d", customer_id=CUST_ID, user_id=USER_ID,
        )
        assert result["messages_fetched"] == 0
        assert result["conversations_created"] == 0


class TestContactSyncRoute:
    def test_sync_email_returns_conversations(self, client):
        """POST /contacts/{id}/sync-email returns updated conversations."""
        cid = _create_contact("Test User", "test@example.com")
        _insert_account()

        mock_creds = MagicMock()
        with patch("poc.sync.fetch_threads", return_value=([], None)), \
             patch("poc.auth.get_credentials_for_account", return_value=mock_creds):
            resp = client.post(
                f"/contacts/{cid}/sync-email",
                data={"window": "90d"},
            )

        assert resp.status_code == 200
        assert "Sync complete" in resp.text
        assert "0 messages fetched" in resp.text

    def test_sync_email_invalid_window(self, client):
        """POST with invalid window returns 400."""
        cid = _create_contact("Test", "test@example.com")
        resp = client.post(
            f"/contacts/{cid}/sync-email",
            data={"window": "invalid"},
        )
        assert resp.status_code == 400

    def test_sync_email_contact_not_found(self, client):
        """POST for nonexistent contact returns 404."""
        resp = client.post(
            "/contacts/nonexistent-id/sync-email",
            data={"window": "90d"},
        )
        assert resp.status_code == 404

    def test_sync_email_form_visible_on_detail(self, client):
        """Contact detail page shows the sync email form."""
        cid = _create_contact("Test User", "test@example.com")
        resp = client.get(f"/contacts/{cid}")
        assert resp.status_code == 200
        assert "sync-email" in resp.text
        assert "Sync Email" in resp.text
        assert "email_history_options" not in resp.text  # template variable, not literal
        # Check that the dropdown options are rendered
        assert "90 Days" in resp.text
        assert "All Time" in resp.text
