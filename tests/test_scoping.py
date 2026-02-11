"""Tests for multi-user data scoping (Phase 3).

Verifies that contacts, companies, conversations, and dashboard data are
correctly scoped to the authenticated user's customer and visibility settings.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from poc.database import get_connection, init_db


_NOW = datetime.now(timezone.utc).isoformat()

# Tenant / user IDs
CUST_A = "cust-a"
USER_A1 = "user-a1"
USER_A2 = "user-a2"
CUST_B = "cust-b"
USER_B1 = "user-b1"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def scoped_db(tmp_path, monkeypatch):
    """Create a DB with two customers and three users."""
    db_file = tmp_path / "test.db"
    monkeypatch.setattr("poc.config.DB_PATH", db_file)
    monkeypatch.setattr("poc.config.CRM_AUTH_ENABLED", False)
    init_db(db_file)

    with get_connection() as conn:
        # Customer A
        conn.execute(
            "INSERT INTO customers (id, name, slug, is_active, created_at, updated_at) "
            "VALUES (?, 'Org A', 'org-a', 1, ?, ?)",
            (CUST_A, _NOW, _NOW),
        )
        conn.execute(
            "INSERT INTO users "
            "(id, customer_id, email, name, role, is_active, created_at, updated_at) "
            "VALUES (?, ?, 'a1@example.com', 'User A1', 'admin', 1, ?, ?)",
            (USER_A1, CUST_A, _NOW, _NOW),
        )
        conn.execute(
            "INSERT INTO users "
            "(id, customer_id, email, name, role, is_active, created_at, updated_at) "
            "VALUES (?, ?, 'a2@example.com', 'User A2', 'user', 1, ?, ?)",
            (USER_A2, CUST_A, _NOW, _NOW),
        )

        # Customer B
        conn.execute(
            "INSERT INTO customers (id, name, slug, is_active, created_at, updated_at) "
            "VALUES (?, 'Org B', 'org-b', 1, ?, ?)",
            (CUST_B, _NOW, _NOW),
        )
        conn.execute(
            "INSERT INTO users "
            "(id, customer_id, email, name, role, is_active, created_at, updated_at) "
            "VALUES (?, ?, 'b1@example.com', 'User B1', 'admin', 1, ?, ?)",
            (USER_B1, CUST_B, _NOW, _NOW),
        )

    return db_file


@pytest.fixture()
def client_a(scoped_db, monkeypatch):
    """Client authenticated as User A1 (customer A)."""
    # Bypass mode picks the first active user; make sure it's User A1
    monkeypatch.setattr(
        "poc.hierarchy.get_current_user",
        lambda: {"id": USER_A1, "email": "a1@example.com", "name": "User A1",
                 "role": "admin", "customer_id": CUST_A},
    )
    from poc.web.app import create_app
    app = create_app()
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture()
def client_b(scoped_db, monkeypatch):
    """Client authenticated as User B1 (customer B)."""
    monkeypatch.setattr(
        "poc.hierarchy.get_current_user",
        lambda: {"id": USER_B1, "email": "b1@example.com", "name": "User B1",
                 "role": "admin", "customer_id": CUST_B},
    )
    from poc.web.app import create_app
    app = create_app()
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _uid():
    return str(uuid.uuid4())


def _add_contact(conn, name, email, customer_id, owner_user_id,
                 visibility="public", company_id=None):
    cid = _uid()
    conn.execute(
        "INSERT INTO contacts "
        "(id, name, company_id, customer_id, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (cid, name, company_id, customer_id, _NOW, _NOW),
    )
    conn.execute(
        "INSERT INTO contact_identifiers "
        "(id, contact_id, type, value, created_at, updated_at) "
        "VALUES (?, ?, 'email', ?, ?, ?)",
        (_uid(), cid, email, _NOW, _NOW),
    )
    conn.execute(
        "INSERT INTO user_contacts "
        "(id, user_id, contact_id, visibility, is_owner, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, 1, ?, ?)",
        (_uid(), owner_user_id, cid, visibility, _NOW, _NOW),
    )
    return cid


def _add_company(conn, name, customer_id, owner_user_id,
                 visibility="public", domain=""):
    coid = _uid()
    conn.execute(
        "INSERT INTO companies "
        "(id, name, domain, status, customer_id, created_at, updated_at) "
        "VALUES (?, ?, ?, 'active', ?, ?, ?)",
        (coid, name, domain, customer_id, _NOW, _NOW),
    )
    conn.execute(
        "INSERT INTO user_companies "
        "(id, user_id, company_id, visibility, is_owner, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, 1, ?, ?)",
        (_uid(), owner_user_id, coid, visibility, _NOW, _NOW),
    )
    return coid


def _add_conversation(conn, title, customer_id, *, share_with=None,
                      account_id=None):
    conv_id = _uid()
    conn.execute(
        "INSERT INTO conversations "
        "(id, title, status, communication_count, participant_count, "
        "last_activity_at, customer_id, created_at, updated_at) "
        "VALUES (?, ?, 'active', 1, 0, ?, ?, ?, ?)",
        (conv_id, title, _NOW, customer_id, _NOW, _NOW),
    )
    if share_with:
        conn.execute(
            "INSERT INTO conversation_shares "
            "(id, conversation_id, user_id, shared_by, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (_uid(), conv_id, share_with, share_with, _NOW),
        )
    return conv_id


def _add_account(conn, email, customer_id, owner_user_id):
    acct_id = _uid()
    conn.execute(
        "INSERT INTO provider_accounts "
        "(id, provider, account_type, email_address, customer_id, "
        "created_at, updated_at) "
        "VALUES (?, 'gmail', 'email', ?, ?, ?, ?)",
        (acct_id, email, customer_id, _NOW, _NOW),
    )
    conn.execute(
        "INSERT INTO user_provider_accounts "
        "(id, user_id, account_id, role, created_at) "
        "VALUES (?, ?, ?, 'owner', ?)",
        (_uid(), owner_user_id, acct_id, _NOW),
    )
    return acct_id


def _add_comm_and_link(conn, conv_id, account_id, sender="x@test.com"):
    """Add a communication linked to a conversation and account."""
    comm_id = _uid()
    conn.execute(
        "INSERT INTO communications "
        "(id, account_id, channel, timestamp, content, sender_address, "
        "created_at, updated_at) "
        "VALUES (?, ?, 'email', ?, 'test', ?, ?, ?)",
        (comm_id, account_id, _NOW, sender, _NOW, _NOW),
    )
    conn.execute(
        "INSERT INTO conversation_communications "
        "(conversation_id, communication_id, created_at) "
        "VALUES (?, ?, ?)",
        (conv_id, comm_id, _NOW),
    )
    return comm_id


# ---------------------------------------------------------------------------
# Contact Scoping
# ---------------------------------------------------------------------------

class TestContactScoping:
    """Contacts visible to user A1 should not include customer B data."""

    def test_contact_list_shows_own_customer(self, client_a, scoped_db):
        with get_connection() as conn:
            _add_contact(conn, "Alice", "alice@a.com", CUST_A, USER_A1)
            _add_contact(conn, "Bob", "bob@b.com", CUST_B, USER_B1)

        resp = client_a.get("/contacts")
        assert resp.status_code == 200
        assert "Alice" in resp.text
        assert "Bob" not in resp.text

    def test_contact_mine_scope(self, client_a, scoped_db):
        """scope=mine shows only user's own contacts."""
        with get_connection() as conn:
            _add_contact(conn, "Alice", "alice@a.com", CUST_A, USER_A1)
            _add_contact(conn, "Carol", "carol@a.com", CUST_A, USER_A2)

        resp = client_a.get("/contacts?scope=mine")
        assert "Alice" in resp.text
        assert "Carol" not in resp.text

    def test_contact_all_scope_shows_public(self, client_a, scoped_db):
        """scope=all shows contacts from same customer with public visibility."""
        with get_connection() as conn:
            _add_contact(conn, "Alice", "alice@a.com", CUST_A, USER_A1)
            _add_contact(conn, "Carol", "carol@a.com", CUST_A, USER_A2,
                         visibility="public")

        resp = client_a.get("/contacts?scope=all")
        assert "Alice" in resp.text
        assert "Carol" in resp.text

    def test_contact_private_not_visible_to_others(self, client_a, scoped_db):
        """Private contacts from another user are not visible."""
        with get_connection() as conn:
            _add_contact(conn, "Secret", "secret@a.com", CUST_A, USER_A2,
                         visibility="private")

        resp = client_a.get("/contacts?scope=all")
        assert "Secret" not in resp.text

    def test_contact_detail_cross_customer_404(self, client_a, scoped_db):
        """Detail page returns 404 for contacts in another customer."""
        with get_connection() as conn:
            cid = _add_contact(conn, "Bob", "bob@b.com", CUST_B, USER_B1)

        resp = client_a.get(f"/contacts/{cid}")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Company Scoping
# ---------------------------------------------------------------------------

class TestCompanyScoping:
    """Companies visible to user A1 should not include customer B data."""

    def test_company_list_shows_own_customer(self, client_a, scoped_db):
        with get_connection() as conn:
            _add_company(conn, "Alpha Inc", CUST_A, USER_A1, domain="alpha.com")
            _add_company(conn, "Beta LLC", CUST_B, USER_B1, domain="beta.com")

        resp = client_a.get("/companies")
        assert resp.status_code == 200
        assert "Alpha Inc" in resp.text
        assert "Beta LLC" not in resp.text

    def test_company_mine_scope(self, client_a, scoped_db):
        with get_connection() as conn:
            _add_company(conn, "Alpha Inc", CUST_A, USER_A1)
            _add_company(conn, "Gamma Ltd", CUST_A, USER_A2)

        resp = client_a.get("/companies?scope=mine")
        assert "Alpha Inc" in resp.text
        assert "Gamma Ltd" not in resp.text

    def test_company_all_scope_shows_public(self, client_a, scoped_db):
        with get_connection() as conn:
            _add_company(conn, "Alpha Inc", CUST_A, USER_A1)
            _add_company(conn, "Gamma Ltd", CUST_A, USER_A2,
                         visibility="public")

        resp = client_a.get("/companies?scope=all")
        assert "Alpha Inc" in resp.text
        assert "Gamma Ltd" in resp.text

    def test_company_detail_cross_customer_404(self, client_a, scoped_db):
        with get_connection() as conn:
            coid = _add_company(conn, "Beta LLC", CUST_B, USER_B1)

        resp = client_a.get(f"/companies/{coid}")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Conversation Scoping
# ---------------------------------------------------------------------------

class TestConversationScoping:
    """Conversations visible via account access or explicit share."""

    def test_conversation_via_account_access(self, client_a, scoped_db):
        """Conversations are visible when user has account access."""
        with get_connection() as conn:
            acct_id = _add_account(conn, "a1@test.com", CUST_A, USER_A1)
            conv_id = _add_conversation(conn, "Thread A", CUST_A)
            _add_comm_and_link(conn, conv_id, acct_id)

        resp = client_a.get("/conversations")
        assert "Thread A" in resp.text

    def test_conversation_via_share(self, client_a, scoped_db):
        """Explicitly shared conversations are visible."""
        with get_connection() as conn:
            conv_id = _add_conversation(conn, "Shared Thread", CUST_A,
                                        share_with=USER_A1)

        resp = client_a.get("/conversations")
        assert "Shared Thread" in resp.text

    def test_conversation_not_visible_without_access(self, client_a, scoped_db):
        """Conversations without account access or share are invisible."""
        with get_connection() as conn:
            # Create a conversation for cust A but without any shares or
            # account links for USER_A1
            acct_id = _add_account(conn, "a2@test.com", CUST_A, USER_A2)
            conv_id = _add_conversation(conn, "Hidden Thread", CUST_A)
            _add_comm_and_link(conn, conv_id, acct_id)

        resp = client_a.get("/conversations")
        assert "Hidden Thread" not in resp.text

    def test_conversation_cross_customer_invisible(self, client_a, scoped_db):
        """Conversations from another customer are invisible."""
        with get_connection() as conn:
            conv_id = _add_conversation(conn, "Other Org Thread", CUST_B,
                                        share_with=USER_B1)

        resp = client_a.get("/conversations")
        assert "Other Org Thread" not in resp.text

    def test_conversation_detail_cross_customer_404(self, client_a, scoped_db):
        with get_connection() as conn:
            conv_id = _add_conversation(conn, "B Thread", CUST_B,
                                        share_with=USER_B1)

        resp = client_a.get(f"/conversations/{conv_id}")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Dashboard Scoping
# ---------------------------------------------------------------------------

class TestDashboardScoping:
    """Dashboard counts reflect only the user's customer data."""

    def test_dashboard_counts_scoped(self, client_a, scoped_db):
        with get_connection() as conn:
            # Customer A data
            _add_contact(conn, "Alice", "alice@a.com", CUST_A, USER_A1)
            _add_company(conn, "Alpha Inc", CUST_A, USER_A1)
            _add_conversation(conn, "Thread A", CUST_A, share_with=USER_A1)

            # Customer B data — should not appear
            _add_contact(conn, "Bob", "bob@b.com", CUST_B, USER_B1)
            _add_company(conn, "Beta LLC", CUST_B, USER_B1)
            _add_conversation(conn, "Thread B", CUST_B, share_with=USER_B1)

        resp = client_a.get("/")
        assert resp.status_code == 200
        text = resp.text.replace(" ", "").replace("\n", "")
        # Dashboard should show 1 contact, 1 company, 1 conversation for cust A
        # (not 2 of each)
        assert "Bob" not in resp.text
        assert "Beta" not in resp.text

    def test_dashboard_shows_recent_conversations(self, client_a, scoped_db):
        with get_connection() as conn:
            _add_conversation(conn, "My Thread", CUST_A, share_with=USER_A1)
            _add_conversation(conn, "Other Thread", CUST_B, share_with=USER_B1)

        resp = client_a.get("/")
        assert "My Thread" in resp.text
        assert "Other Thread" not in resp.text


# ---------------------------------------------------------------------------
# Detail Access Check
# ---------------------------------------------------------------------------

class TestDetailAccessCheck:
    """Detail pages return 404 for entities in another customer."""

    def test_contact_detail_other_customer(self, client_a, scoped_db):
        with get_connection() as conn:
            cid = _add_contact(conn, "Stranger", "s@b.com", CUST_B, USER_B1)
        resp = client_a.get(f"/contacts/{cid}")
        assert resp.status_code == 404

    def test_company_detail_other_customer(self, client_a, scoped_db):
        with get_connection() as conn:
            coid = _add_company(conn, "Other Corp", CUST_B, USER_B1)
        resp = client_a.get(f"/companies/{coid}")
        assert resp.status_code == 404

    def test_conversation_detail_other_customer(self, client_a, scoped_db):
        with get_connection() as conn:
            conv_id = _add_conversation(conn, "Secret", CUST_B,
                                        share_with=USER_B1)
        resp = client_a.get(f"/conversations/{conv_id}")
        assert resp.status_code == 404

    def test_client_b_sees_own_data(self, client_b, scoped_db):
        """Sanity check: client B can see customer B's data."""
        with get_connection() as conn:
            cid = _add_contact(conn, "Bob", "bob@b.com", CUST_B, USER_B1)
            coid = _add_company(conn, "Beta LLC", CUST_B, USER_B1)

        resp = client_b.get("/contacts")
        assert "Bob" in resp.text

        resp = client_b.get("/companies")
        assert "Beta LLC" in resp.text

        resp = client_b.get(f"/contacts/{cid}")
        assert resp.status_code == 200

        resp = client_b.get(f"/companies/{coid}")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Sync Scoping
# ---------------------------------------------------------------------------

class TestSyncScoping:
    """Verify sync creates proper user linkage rows."""

    def test_sync_contacts_creates_user_contacts(self, scoped_db):
        """sync_contacts should create user_contacts rows for new contacts."""
        from unittest.mock import patch, MagicMock
        from poc.models import KnownContact
        from poc.sync import sync_contacts

        mock_contacts = [
            KnownContact(email="new@test.com", name="New Contact",
                         company="", status="active"),
        ]

        with patch("poc.sync.fetch_contacts", return_value=mock_contacts):
            mock_creds = MagicMock()
            count = sync_contacts(
                mock_creds, customer_id=CUST_A, user_id=USER_A1,
            )

        assert count == 1

        with get_connection() as conn:
            # Contact should have customer_id
            contact = conn.execute(
                "SELECT * FROM contacts WHERE customer_id = ?", (CUST_A,)
            ).fetchone()
            assert contact is not None
            assert contact["created_by"] == USER_A1

            # user_contacts row should exist
            uc = conn.execute(
                "SELECT * FROM user_contacts WHERE user_id = ? AND contact_id = ?",
                (USER_A1, contact["id"]),
            ).fetchone()
            assert uc is not None
            assert uc["visibility"] == "public"
            assert uc["is_owner"] == 1

    def test_sync_auto_creates_company_with_customer_id(self, scoped_db):
        """Auto-created companies get customer_id and user_companies rows."""
        from unittest.mock import patch, MagicMock
        from poc.models import KnownContact
        from poc.sync import sync_contacts

        mock_contacts = [
            KnownContact(email="emp@newcorp.com", name="Employee",
                         company="New Corp", status="active"),
        ]

        with patch("poc.sync.fetch_contacts", return_value=mock_contacts):
            mock_creds = MagicMock()
            sync_contacts(mock_creds, customer_id=CUST_A, user_id=USER_A1)

        with get_connection() as conn:
            company = conn.execute(
                "SELECT * FROM companies WHERE name = 'New Corp'"
            ).fetchone()
            assert company is not None
            assert company["customer_id"] == CUST_A

            uco = conn.execute(
                "SELECT * FROM user_companies WHERE user_id = ? AND company_id = ?",
                (USER_A1, company["id"]),
            ).fetchone()
            assert uco is not None


# ---------------------------------------------------------------------------
# Project Scoping
# ---------------------------------------------------------------------------

class TestProjectScoping:
    """Projects are scoped by customer_id."""

    def test_project_create_sets_customer_id(self, client_a, scoped_db):
        resp = client_a.post("/projects", data={
            "name": "Test Project", "description": "",
        })
        assert resp.status_code in (200, 303)

        with get_connection() as conn:
            proj = conn.execute(
                "SELECT * FROM projects WHERE name = 'Test Project'"
            ).fetchone()
            assert proj is not None
            assert proj["customer_id"] == CUST_A
            assert proj["created_by"] == USER_A1

    def test_project_list_shows_own_customer(self, client_a, scoped_db):
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO projects (id, name, status, customer_id, "
                "created_at, updated_at) VALUES (?, ?, 'active', ?, ?, ?)",
                ("p-a", "Project A", CUST_A, _NOW, _NOW),
            )
            conn.execute(
                "INSERT INTO projects (id, name, status, customer_id, "
                "created_at, updated_at) VALUES (?, ?, 'active', ?, ?, ?)",
                ("p-b", "Project B", CUST_B, _NOW, _NOW),
            )

        resp = client_a.get("/projects")
        assert "Project A" in resp.text
        assert "Project B" not in resp.text
