"""Tests for the CRM Extender web UI."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch as _patch

import pytest
from fastapi.testclient import TestClient

from poc.database import get_connection, init_db


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def tmp_db(tmp_path, monkeypatch):
    """Create a temporary database and point config at it."""
    db_file = tmp_path / "test.db"
    monkeypatch.setattr("poc.config.DB_PATH", db_file)
    init_db(db_file)

    # Seed customer + user so auth bypass mode has a valid user
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO customers (id, name, slug, is_active, created_at, updated_at) "
            "VALUES ('cust-test', 'Test Org', 'test', 1, ?, ?)",
            (_NOW, _NOW),
        )
        conn.execute(
            "INSERT INTO users "
            "(id, customer_id, email, name, role, is_active, created_at, updated_at) "
            "VALUES ('user-test', 'cust-test', 'test@example.com', 'Test User', "
            "'admin', 1, ?, ?)",
            (_NOW, _NOW),
        )

    return db_file


@pytest.fixture()
def client(tmp_db, monkeypatch):
    monkeypatch.setattr("poc.config.CRM_AUTH_ENABLED", False)
    from poc.web.app import create_app
    app = create_app()
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_NOW = datetime.now(timezone.utc).isoformat()


def _insert_account(conn, account_id="acct-1", email="test@example.com",
                    customer_id="cust-test"):
    conn.execute(
        "INSERT OR IGNORE INTO provider_accounts "
        "(id, provider, account_type, email_address, customer_id, created_at, updated_at) "
        "VALUES (?, 'gmail', 'email', ?, ?, ?, ?)",
        (account_id, email, customer_id, _NOW, _NOW),
    )
    # Link to test user for visibility
    conn.execute(
        "INSERT OR IGNORE INTO user_provider_accounts "
        "(id, user_id, account_id, role, created_at) "
        "VALUES (?, 'user-test', ?, 'owner', ?)",
        (f"upa-{account_id}", account_id, _NOW),
    )


def _insert_conversation(conn, conv_id, title="Test subject", topic_id=None,
                          triage_result=None, status="active",
                          communication_count=1, dismissed=0,
                          customer_id="cust-test"):
    conn.execute(
        "INSERT OR IGNORE INTO conversations "
        "(id, topic_id, title, status, triage_result, dismissed, "
        "communication_count, participant_count, last_activity_at, "
        "customer_id, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?)",
        (conv_id, topic_id, title, status, triage_result, dismissed,
         communication_count, _NOW, customer_id, _NOW, _NOW),
    )
    # Share with test user for visibility
    conn.execute(
        "INSERT OR IGNORE INTO conversation_shares "
        "(id, conversation_id, user_id, shared_by, created_at) "
        "VALUES (?, ?, 'user-test', 'user-test', ?)",
        (f"cs-{conv_id}", conv_id, _NOW),
    )


def _insert_communication(conn, comm_id, account_id="acct-1",
                           sender="alice@example.com", content="Hello",
                           subject="Test", timestamp=None):
    conn.execute(
        "INSERT OR IGNORE INTO communications "
        "(id, account_id, channel, timestamp, content, sender_address, subject, "
        "created_at, updated_at) "
        "VALUES (?, ?, 'email', ?, ?, ?, ?, ?, ?)",
        (comm_id, account_id, timestamp or _NOW, content, sender, subject,
         _NOW, _NOW),
    )


def _link_comm_to_conv(conn, conv_id, comm_id):
    conn.execute(
        "INSERT OR IGNORE INTO conversation_communications "
        "(conversation_id, communication_id, created_at) VALUES (?, ?, ?)",
        (conv_id, comm_id, _NOW),
    )


def _insert_contact(conn, contact_id, name="Alice", email="alice@example.com",
                     company_id=None, customer_id="cust-test"):
    conn.execute(
        "INSERT OR IGNORE INTO contacts "
        "(id, name, company_id, customer_id, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (contact_id, name, company_id, customer_id, _NOW, _NOW),
    )
    conn.execute(
        "INSERT OR IGNORE INTO contact_identifiers "
        "(id, contact_id, type, value, created_at, updated_at) "
        "VALUES (?, ?, 'email', ?, ?, ?)",
        (f"ci-{contact_id}", contact_id, email, _NOW, _NOW),
    )
    # Create user_contacts for visibility
    conn.execute(
        "INSERT OR IGNORE INTO user_contacts "
        "(id, user_id, contact_id, visibility, is_owner, created_at, updated_at) "
        "VALUES (?, 'user-test', ?, 'public', 1, ?, ?)",
        (f"uc-{contact_id}", contact_id, _NOW, _NOW),
    )


def _insert_company(conn, company_id, name="Acme Corp", domain="acme.com",
                    customer_id="cust-test"):
    conn.execute(
        "INSERT OR IGNORE INTO companies "
        "(id, name, domain, status, customer_id, created_at, updated_at) "
        "VALUES (?, ?, ?, 'active', ?, ?, ?)",
        (company_id, name, domain, customer_id, _NOW, _NOW),
    )
    # Create user_companies for visibility
    conn.execute(
        "INSERT OR IGNORE INTO user_companies "
        "(id, user_id, company_id, visibility, is_owner, created_at, updated_at) "
        "VALUES (?, 'user-test', ?, 'public', 1, ?, ?)",
        (f"uco-{company_id}", company_id, _NOW, _NOW),
    )


def _insert_project(conn, project_id, name="My Project",
                    customer_id="cust-test"):
    conn.execute(
        "INSERT OR IGNORE INTO projects "
        "(id, name, status, customer_id, created_at, updated_at) "
        "VALUES (?, ?, 'active', ?, ?, ?)",
        (project_id, name, customer_id, _NOW, _NOW),
    )


def _insert_topic(conn, topic_id, project_id, name="Design"):
    conn.execute(
        "INSERT OR IGNORE INTO topics "
        "(id, project_id, name, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
        (topic_id, project_id, name, _NOW, _NOW),
    )


def _insert_tag(conn, tag_id, name):
    conn.execute(
        "INSERT OR IGNORE INTO tags (id, name, created_at) VALUES (?, ?, ?)",
        (tag_id, name, _NOW),
    )


def _link_tag_to_conv(conn, conv_id, tag_id):
    conn.execute(
        "INSERT OR IGNORE INTO conversation_tags "
        "(conversation_id, tag_id, created_at) VALUES (?, ?, ?)",
        (conv_id, tag_id, _NOW),
    )


def _insert_participant(conn, conv_id, address, contact_id=None,
                         communication_count=1):
    conn.execute(
        "INSERT OR IGNORE INTO conversation_participants "
        "(conversation_id, address, contact_id, communication_count, "
        "first_seen_at, last_seen_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (conv_id, address, contact_id, communication_count, _NOW, _NOW),
    )


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

class TestDashboard:
    def test_dashboard_loads(self, client, tmp_db):
        resp = client.get("/")
        assert resp.status_code == 200
        assert "Dashboard" in resp.text

    def test_dashboard_shows_counts(self, client, tmp_db):
        with get_connection() as conn:
            _insert_conversation(conn, "conv-1", "Test Thread")
            _insert_conversation(conn, "conv-2", "Another Thread")
            _insert_contact(conn, "ct-1", "Alice")
            _insert_company(conn, "co-1", "Acme")

        resp = client.get("/")
        assert resp.status_code == 200
        assert ">2<" in resp.text.replace(" ", "").replace("\n", "")  # 2 conversations
        assert "Acme" not in resp.text  # company name not on dashboard, just count

    def test_dashboard_recent_conversations(self, client, tmp_db):
        with get_connection() as conn:
            _insert_conversation(conn, "conv-1", "Important Email")

        resp = client.get("/")
        assert "Important Email" in resp.text


# ---------------------------------------------------------------------------
# Conversations
# ---------------------------------------------------------------------------

class TestConversations:
    def test_list_loads(self, client, tmp_db):
        resp = client.get("/conversations")
        assert resp.status_code == 200
        assert "Conversations" in resp.text

    def test_list_shows_conversations(self, client, tmp_db):
        with get_connection() as conn:
            _insert_conversation(conn, "conv-1", "Budget Planning")
            _insert_conversation(conn, "conv-2", "Team Standup")

        resp = client.get("/conversations")
        assert "Budget Planning" in resp.text
        assert "Team Standup" in resp.text

    def test_search_filters(self, client, tmp_db):
        with get_connection() as conn:
            _insert_conversation(conn, "conv-1", "Budget Planning")
            _insert_conversation(conn, "conv-2", "Team Standup")

        resp = client.get("/conversations/search?q=Budget")
        assert resp.status_code == 200
        assert "Budget Planning" in resp.text
        assert "Team Standup" not in resp.text

    def test_status_filter_triaged(self, client, tmp_db):
        with get_connection() as conn:
            _insert_conversation(conn, "conv-1", "Open Thread")
            _insert_conversation(conn, "conv-2", "Triaged", triage_result="automated")

        resp = client.get("/conversations?status=triaged")
        assert "Triaged" in resp.text
        assert "Open Thread" not in resp.text

    def test_detail_page(self, client, tmp_db):
        with get_connection() as conn:
            _insert_account(conn)
            _insert_conversation(conn, "conv-1", "Important Discussion")
            _insert_communication(conn, "msg-1", content="Hello team")
            _link_comm_to_conv(conn, "conv-1", "msg-1")

        resp = client.get("/conversations/conv-1")
        assert resp.status_code == 200
        assert "Important Discussion" in resp.text
        assert "Hello team" in resp.text

    def test_detail_shows_participants(self, client, tmp_db):
        with get_connection() as conn:
            _insert_conversation(conn, "conv-1", "Thread")
            _insert_contact(conn, "ct-1", "Alice", "alice@example.com")
            _insert_participant(conn, "conv-1", "alice@example.com",
                                contact_id="ct-1")

        resp = client.get("/conversations/conv-1")
        assert "Alice" in resp.text

    def test_detail_shows_tags(self, client, tmp_db):
        with get_connection() as conn:
            _insert_conversation(conn, "conv-1", "Thread")
            _insert_tag(conn, "tag-1", "quarterly-review")
            _link_tag_to_conv(conn, "conv-1", "tag-1")

        resp = client.get("/conversations/conv-1")
        assert "quarterly-review" in resp.text

    def test_detail_not_found(self, client, tmp_db):
        resp = client.get("/conversations/nonexistent")
        assert resp.status_code == 404

    def test_topic_filter(self, client, tmp_db):
        with get_connection() as conn:
            _insert_project(conn, "proj-1", "Project A")
            _insert_topic(conn, "topic-1", "proj-1", "Design")
            _insert_conversation(conn, "conv-1", "On topic", topic_id="topic-1")
            _insert_conversation(conn, "conv-2", "Off topic")

        resp = client.get("/conversations?topic_id=topic-1")
        assert "On topic" in resp.text
        assert "Off topic" not in resp.text


# ---------------------------------------------------------------------------
# Contacts
# ---------------------------------------------------------------------------

class TestContacts:
    def test_list_loads(self, client, tmp_db):
        resp = client.get("/contacts")
        assert resp.status_code == 200
        assert "Contacts" in resp.text

    def test_list_shows_contacts(self, client, tmp_db):
        with get_connection() as conn:
            _insert_contact(conn, "ct-1", "Alice", "alice@a.com")
            _insert_contact(conn, "ct-2", "Bob", "bob@b.com")

        resp = client.get("/contacts")
        assert "Alice" in resp.text
        assert "Bob" in resp.text

    def test_search_contacts(self, client, tmp_db):
        with get_connection() as conn:
            _insert_contact(conn, "ct-1", "Alice", "alice@a.com")
            _insert_contact(conn, "ct-2", "Bob", "bob@b.com")

        resp = client.get("/contacts/search?q=Alice")
        assert "Alice" in resp.text
        assert "Bob" not in resp.text

    def test_detail_page(self, client, tmp_db):
        with get_connection() as conn:
            _insert_company(conn, "co-1", "Acme")
            _insert_contact(conn, "ct-1", "Alice", "alice@acme.com",
                            company_id="co-1")

        resp = client.get("/contacts/ct-1")
        assert resp.status_code == 200
        assert "Alice" in resp.text
        assert "Acme" in resp.text

    def test_detail_not_found(self, client, tmp_db):
        resp = client.get("/contacts/nonexistent")
        assert resp.status_code == 404

    def test_detail_shows_conversations(self, client, tmp_db):
        with get_connection() as conn:
            _insert_contact(conn, "ct-1", "Alice", "alice@a.com")
            _insert_conversation(conn, "conv-1", "With Alice")
            _insert_participant(conn, "conv-1", "alice@a.com",
                                contact_id="ct-1")

        resp = client.get("/contacts/ct-1")
        assert "With Alice" in resp.text


# ---------------------------------------------------------------------------
# Companies
# ---------------------------------------------------------------------------

class TestCompanies:
    def test_list_loads(self, client, tmp_db):
        resp = client.get("/companies")
        assert resp.status_code == 200
        assert "Companies" in resp.text

    def test_list_shows_companies(self, client, tmp_db):
        with get_connection() as conn:
            _insert_company(conn, "co-1", "Acme Corp")
            _insert_company(conn, "co-2", "Globex Inc")

        resp = client.get("/companies")
        assert "Acme Corp" in resp.text
        assert "Globex Inc" in resp.text

    def test_create_company(self, client, tmp_db):
        resp = client.post("/companies", data={
            "name": "New Corp",
            "domain": "newcorp.com",
            "industry": "Tech",
            "description": "A new company",
        })
        assert resp.status_code == 200  # redirect followed

        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM companies WHERE name = 'New Corp'"
            ).fetchone()
        assert row is not None
        assert row["domain"] == "newcorp.com"

    def test_delete_company(self, client, tmp_db):
        with get_connection() as conn:
            _insert_company(conn, "co-1", "Doomed Corp")

        resp = client.delete("/companies/co-1")
        assert resp.status_code == 200

        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM companies WHERE id = 'co-1'"
            ).fetchone()
        assert row is None

    def test_search_companies(self, client, tmp_db):
        with get_connection() as conn:
            _insert_company(conn, "co-1", "Acme Corp", "acme.com")
            _insert_company(conn, "co-2", "Globex Inc", "globex.com")

        resp = client.get("/companies/search?q=Acme")
        assert "Acme Corp" in resp.text
        assert "Globex Inc" not in resp.text

    def test_detail_page(self, client, tmp_db):
        with get_connection() as conn:
            _insert_company(conn, "co-1", "Acme Corp", "acme.com")
            _insert_contact(conn, "ct-1", "Alice", "alice@acme.com",
                            company_id="co-1")

        resp = client.get("/companies/co-1")
        assert resp.status_code == 200
        assert "Acme Corp" in resp.text
        assert "Alice" in resp.text

    def test_detail_not_found(self, client, tmp_db):
        resp = client.get("/companies/nonexistent")
        assert resp.status_code == 404

    def test_create_shows_preview_for_matching_domain(self, client, tmp_db):
        with get_connection() as conn:
            _insert_contact(conn, "ct-1", "Alice", "alice@acme.com")
            _insert_contact(conn, "ct-2", "Bob", "bob@acme.com")

        resp = client.post("/companies", data={
            "name": "Acme Corp",
            "domain": "acme.com",
            "industry": "",
            "description": "",
        })
        assert resp.status_code == 200
        assert "alice@acme.com" in resp.text
        assert "bob@acme.com" in resp.text
        assert "Confirm" in resp.text

        # Company should NOT be created yet
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM companies WHERE name = 'Acme Corp'"
            ).fetchone()
        assert row is None

    def test_confirm_with_link_creates_and_links(self, client, tmp_db):
        with get_connection() as conn:
            _insert_contact(conn, "ct-1", "Alice", "alice@acme.com")
            _insert_contact(conn, "ct-2", "Bob", "bob@acme.com")

        resp = client.post("/companies/confirm", data={
            "name": "Acme Corp",
            "domain": "acme.com",
            "industry": "Tech",
            "description": "",
            "link": "true",
        })
        assert resp.status_code == 200

        with get_connection() as conn:
            company = conn.execute(
                "SELECT * FROM companies WHERE name = 'Acme Corp'"
            ).fetchone()
            assert company is not None

            linked = conn.execute(
                "SELECT id FROM contacts WHERE company_id = ?",
                (company["id"],),
            ).fetchall()
        assert len(linked) == 2

    def test_confirm_without_link_creates_only(self, client, tmp_db):
        with get_connection() as conn:
            _insert_contact(conn, "ct-1", "Alice", "alice@acme.com")

        resp = client.post("/companies/confirm", data={
            "name": "Acme Corp",
            "domain": "acme.com",
            "industry": "",
            "description": "",
            "link": "false",
        })
        assert resp.status_code == 200

        with get_connection() as conn:
            company = conn.execute(
                "SELECT * FROM companies WHERE name = 'Acme Corp'"
            ).fetchone()
            assert company is not None

            linked = conn.execute(
                "SELECT id FROM contacts WHERE company_id = ?",
                (company["id"],),
            ).fetchall()
        assert len(linked) == 0

    def test_public_domain_creates_directly(self, client, tmp_db):
        with get_connection() as conn:
            _insert_contact(conn, "ct-1", "Alice", "alice@gmail.com")

        resp = client.post("/companies", data={
            "name": "Gmail Fan Club",
            "domain": "gmail.com",
            "industry": "",
            "description": "",
        })
        assert resp.status_code == 200
        # Should NOT show preview — company created directly
        assert "Confirm" not in resp.text

        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM companies WHERE name = 'Gmail Fan Club'"
            ).fetchone()
        assert row is not None

    def test_no_matching_contacts_creates_directly(self, client, tmp_db):
        resp = client.post("/companies", data={
            "name": "Newco",
            "domain": "newco.com",
            "industry": "",
            "description": "",
        })
        assert resp.status_code == 200
        assert "Confirm" not in resp.text

        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM companies WHERE name = 'Newco'"
            ).fetchone()
        assert row is not None


# ---------------------------------------------------------------------------
# Company Detail (Phase 2)
# ---------------------------------------------------------------------------

def _insert_company_full(conn, company_id, name="Acme Corp", domain="acme.com",
                          **kwargs):
    """Insert a company with optional v7 fields."""
    defaults = {
        "website": None, "stock_symbol": None, "size_range": None,
        "employee_count": None, "founded_year": None, "revenue_range": None,
        "funding_total": None, "funding_stage": None,
        "headquarters_location": None,
    }
    defaults.update(kwargs)
    conn.execute(
        "INSERT OR IGNORE INTO companies "
        "(id, name, domain, status, website, stock_symbol, size_range, "
        "employee_count, founded_year, revenue_range, funding_total, "
        "funding_stage, headquarters_location, created_at, updated_at) "
        "VALUES (?, ?, ?, 'active', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (company_id, name, domain,
         defaults["website"], defaults["stock_symbol"], defaults["size_range"],
         defaults["employee_count"], defaults["founded_year"],
         defaults["revenue_range"], defaults["funding_total"],
         defaults["funding_stage"], defaults["headquarters_location"],
         _NOW, _NOW),
    )


def _insert_company_identifier(conn, ident_id, company_id, type="domain",
                                 value="acme.com", is_primary=0):
    conn.execute(
        "INSERT OR IGNORE INTO company_identifiers "
        "(id, company_id, type, value, is_primary, source, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, '', ?, ?)",
        (ident_id, company_id, type, value, is_primary, _NOW, _NOW),
    )


def _insert_company_hierarchy(conn, hier_id, parent_id, child_id,
                                hierarchy_type="subsidiary"):
    conn.execute(
        "INSERT OR IGNORE INTO company_hierarchy "
        "(id, parent_company_id, child_company_id, hierarchy_type, "
        "effective_date, end_date, metadata, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, '', '', '', ?, ?)",
        (hier_id, parent_id, child_id, hierarchy_type, _NOW, _NOW),
    )


class TestCompanyDetail:
    def test_detail_shows_new_fields(self, client, tmp_db):
        with get_connection() as conn:
            _insert_company_full(
                conn, "co-1", "Acme Corp", "acme.com",
                website="https://acme.com", stock_symbol="ACME",
                headquarters_location="New York, NY",
                size_range="201-500", employee_count=350,
                founded_year=1999, revenue_range="$10M-$50M",
                funding_total="$25M", funding_stage="series-b",
            )

        resp = client.get("/companies/co-1")
        assert resp.status_code == 200
        assert "https://acme.com" in resp.text
        assert "ACME" in resp.text
        assert "New York, NY" in resp.text
        assert "201-500" in resp.text
        assert "350" in resp.text
        assert "1999" in resp.text
        assert "$10M-$50M" in resp.text
        assert "$25M" in resp.text
        assert "series-b" in resp.text

    def test_detail_shows_identifiers(self, client, tmp_db):
        with get_connection() as conn:
            _insert_company(conn, "co-1", "Acme Corp")
            _insert_company_identifier(conn, "ci-1", "co-1", "domain", "acme.com")
            _insert_company_identifier(conn, "ci-2", "co-1", "ticker", "ACME")

        resp = client.get("/companies/co-1")
        assert resp.status_code == 200
        assert "Identifiers (2)" in resp.text
        assert "acme.com" in resp.text
        assert "ACME" in resp.text

    def test_detail_shows_hierarchy(self, client, tmp_db):
        with get_connection() as conn:
            _insert_company(conn, "co-parent", "MegaCorp", "megacorp.com")
            _insert_company(conn, "co-1", "Acme Corp", "acme.com")
            _insert_company(conn, "co-child", "Sub Inc", "sub.com")
            _insert_company_hierarchy(conn, "h-1", "co-parent", "co-1")
            _insert_company_hierarchy(conn, "h-2", "co-1", "co-child")

        resp = client.get("/companies/co-1")
        assert resp.status_code == 200
        assert "MegaCorp" in resp.text
        assert "Sub Inc" in resp.text
        assert "Parent Companies" in resp.text
        assert "Subsidiaries" in resp.text

    def test_edit_page_renders(self, client, tmp_db):
        with get_connection() as conn:
            _insert_company_full(
                conn, "co-1", "Acme Corp", "acme.com",
                website="https://acme.com", industry="Tech",
            )

        resp = client.get("/companies/co-1/edit")
        assert resp.status_code == 200
        assert "Edit Acme Corp" in resp.text
        assert "https://acme.com" in resp.text

    def test_edit_updates_fields(self, client, tmp_db):
        with get_connection() as conn:
            _insert_company(conn, "co-1", "Acme Corp")

        resp = client.post("/companies/co-1/edit", data={
            "name": "Acme Renamed",
            "domain": "acme.com",
            "industry": "Finance",
            "description": "Updated desc",
            "website": "https://new.acme.com",
            "stock_symbol": "ACMR",
            "size_range": "51-200",
            "employee_count": "150",
            "founded_year": "2001",
            "revenue_range": "$5M-$10M",
            "funding_total": "$10M",
            "funding_stage": "series-a",
            "headquarters_location": "Boston, MA",
            "status": "active",
        })
        assert resp.status_code in (200, 303)

        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM companies WHERE id = 'co-1'"
            ).fetchone()
        assert row["name"] == "Acme Renamed"
        assert row["industry"] == "Finance"
        assert row["website"] == "https://new.acme.com"
        assert row["stock_symbol"] == "ACMR"
        assert row["employee_count"] == 150
        assert row["founded_year"] == 2001
        assert row["headquarters_location"] == "Boston, MA"

    def test_edit_integer_fields_empty(self, client, tmp_db):
        """Empty employee_count and founded_year should store as NULL."""
        with get_connection() as conn:
            _insert_company_full(conn, "co-1", "Acme Corp", employee_count=100,
                                  founded_year=2000)

        resp = client.post("/companies/co-1/edit", data={
            "name": "Acme Corp",
            "domain": "",
            "industry": "",
            "description": "",
            "website": "",
            "stock_symbol": "",
            "size_range": "",
            "employee_count": "",
            "founded_year": "",
            "revenue_range": "",
            "funding_total": "",
            "funding_stage": "",
            "headquarters_location": "",
            "status": "active",
        })
        assert resp.status_code in (200, 303)

        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM companies WHERE id = 'co-1'"
            ).fetchone()
        assert row["employee_count"] is None
        assert row["founded_year"] is None

    def test_add_identifier_via_web(self, client, tmp_db):
        with get_connection() as conn:
            _insert_company(conn, "co-1", "Acme Corp")

        resp = client.post("/companies/co-1/identifiers", data={
            "type": "domain",
            "value": "acme.org",
        })
        assert resp.status_code == 200
        assert "acme.org" in resp.text

        with get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM company_identifiers WHERE company_id = 'co-1'"
            ).fetchall()
        assert len(rows) == 1
        assert rows[0]["value"] == "acme.org"

    def test_remove_identifier_via_web(self, client, tmp_db):
        with get_connection() as conn:
            _insert_company(conn, "co-1", "Acme Corp")
            _insert_company_identifier(conn, "ci-1", "co-1", "domain", "acme.com")

        resp = client.delete("/companies/co-1/identifiers/ci-1")
        assert resp.status_code == 200

        with get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM company_identifiers WHERE company_id = 'co-1'"
            ).fetchall()
        assert len(rows) == 0

    def test_add_hierarchy_via_web(self, client, tmp_db):
        with get_connection() as conn:
            _insert_company(conn, "co-1", "Acme Corp")
            _insert_company(conn, "co-2", "ParentCo", "parentco.com")

        resp = client.post("/companies/co-1/hierarchy", data={
            "related_company_id": "co-2",
            "direction": "parent",
            "hierarchy_type": "subsidiary",
        })
        assert resp.status_code == 200
        assert "ParentCo" in resp.text

        with get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM company_hierarchy WHERE child_company_id = 'co-1'"
            ).fetchall()
        assert len(rows) == 1
        assert rows[0]["parent_company_id"] == "co-2"

    def test_remove_hierarchy_via_web(self, client, tmp_db):
        with get_connection() as conn:
            _insert_company(conn, "co-1", "Acme Corp")
            _insert_company(conn, "co-2", "ParentCo", "parentco.com")
            _insert_company_hierarchy(conn, "h-1", "co-2", "co-1")

        resp = client.delete("/companies/co-1/hierarchy/h-1")
        assert resp.status_code == 200

        with get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM company_hierarchy WHERE child_company_id = 'co-1'"
            ).fetchall()
        assert len(rows) == 0

    def test_detail_shows_phones(self, client, tmp_db):
        with get_connection() as conn:
            _insert_company(conn, "co-1", "Acme Corp")
            _insert_phone_number(conn, "ph-1", "company", "co-1",
                                  "+12015550100", phone_type="main")

        resp = client.get("/companies/co-1")
        assert resp.status_code == 200
        assert "Phone Numbers (1)" in resp.text
        assert "(201) 555-0100" in resp.text

    def test_detail_shows_addresses(self, client, tmp_db):
        with get_connection() as conn:
            _insert_company(conn, "co-1", "Acme Corp")
            _insert_address(conn, "ad-1", "company", "co-1",
                            city="New York", state="NY", country="US",
                            address_type="headquarters")

        resp = client.get("/companies/co-1")
        assert resp.status_code == 200
        assert "Addresses (1)" in resp.text
        assert "New York" in resp.text
        assert "headquarters" in resp.text

    def test_detail_shows_social_profiles(self, client, tmp_db):
        with get_connection() as conn:
            _insert_company(conn, "co-1", "Acme Corp")
            _insert_company_social_profile(
                conn, "sp-1", "co-1", "linkedin",
                "https://linkedin.com/company/acme", username="acme",
            )

        resp = client.get("/companies/co-1")
        assert resp.status_code == 200
        assert "Social Profiles" in resp.text
        assert "linkedin" in resp.text
        assert "https://linkedin.com/company/acme" in resp.text

    def test_detail_no_social_profiles(self, client, tmp_db):
        with get_connection() as conn:
            _insert_company(conn, "co-1", "Acme Corp")

        resp = client.get("/companies/co-1")
        assert resp.status_code == 200
        assert "Social Profiles" not in resp.text

    def test_add_phone_via_web(self, client, tmp_db):
        with get_connection() as conn:
            _insert_company(conn, "co-1", "Acme Corp")

        resp = client.post("/companies/co-1/phones", data={
            "phone_type": "main",
            "number": "(201) 555-0200",
        })
        assert resp.status_code == 200
        assert "(201) 555-0200" in resp.text

        with get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM phone_numbers "
                "WHERE entity_type = 'company' AND entity_id = 'co-1'"
            ).fetchall()
        assert len(rows) == 1
        assert rows[0]["number"] == "+12015550200"

    def test_remove_phone_via_web(self, client, tmp_db):
        with get_connection() as conn:
            _insert_company(conn, "co-1", "Acme Corp")
            _insert_phone_number(conn, "ph-1", "company", "co-1", "+1-555-0100")

        resp = client.delete("/companies/co-1/phones/ph-1")
        assert resp.status_code == 200

        with get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM phone_numbers "
                "WHERE entity_type = 'company' AND entity_id = 'co-1'"
            ).fetchall()
        assert len(rows) == 0

    def test_add_address_via_web(self, client, tmp_db):
        with get_connection() as conn:
            _insert_company(conn, "co-1", "Acme Corp")

        resp = client.post("/companies/co-1/addresses", data={
            "address_type": "headquarters",
            "street": "100 Tech Blvd",
            "city": "San Francisco",
            "state": "CA",
            "postal_code": "94105",
            "country": "US",
        })
        assert resp.status_code == 200
        assert "San Francisco" in resp.text

        with get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM addresses "
                "WHERE entity_type = 'company' AND entity_id = 'co-1'"
            ).fetchall()
        assert len(rows) == 1
        assert rows[0]["city"] == "San Francisco"

    def test_remove_address_via_web(self, client, tmp_db):
        with get_connection() as conn:
            _insert_company(conn, "co-1", "Acme Corp")
            _insert_address(conn, "ad-1", "company", "co-1", city="Boston")

        resp = client.delete("/companies/co-1/addresses/ad-1")
        assert resp.status_code == 200

        with get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM addresses "
                "WHERE entity_type = 'company' AND entity_id = 'co-1'"
            ).fetchall()
        assert len(rows) == 0

    def test_detail_shows_emails(self, client, tmp_db):
        with get_connection() as conn:
            _insert_company(conn, "co-1", "Acme Corp")
            _insert_email_address(conn, "em-1", "company", "co-1",
                                  "info@acme.com", email_type="general")

        resp = client.get("/companies/co-1")
        assert resp.status_code == 200
        assert "info@acme.com" in resp.text
        assert "Email Addresses" in resp.text

    def test_add_email_via_web(self, client, tmp_db):
        with get_connection() as conn:
            _insert_company(conn, "co-1", "Acme Corp")

        resp = client.post("/companies/co-1/emails", data={
            "email_type": "support",
            "address": "support@acme.com",
        })
        assert resp.status_code == 200
        assert "support@acme.com" in resp.text

        with get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM email_addresses "
                "WHERE entity_type = 'company' AND entity_id = 'co-1'"
            ).fetchall()
        assert len(rows) == 1
        assert rows[0]["address"] == "support@acme.com"

    def test_remove_email_via_web(self, client, tmp_db):
        with get_connection() as conn:
            _insert_company(conn, "co-1", "Acme Corp")
            _insert_email_address(conn, "em-1", "company", "co-1",
                                  "info@acme.com")

        resp = client.delete("/companies/co-1/emails/em-1")
        assert resp.status_code == 200

        with get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM email_addresses "
                "WHERE entity_type = 'company' AND entity_id = 'co-1'"
            ).fetchall()
        assert len(rows) == 0


# ---------------------------------------------------------------------------
# Projects & Topics
# ---------------------------------------------------------------------------

class TestProjects:
    def test_list_loads(self, client, tmp_db):
        resp = client.get("/projects")
        assert resp.status_code == 200
        assert "Projects" in resp.text

    def test_list_shows_projects(self, client, tmp_db):
        with get_connection() as conn:
            _insert_project(conn, "proj-1", "Alpha")

        resp = client.get("/projects")
        assert "Alpha" in resp.text

    def test_create_project(self, client, tmp_db):
        resp = client.post("/projects", data={
            "name": "Beta",
            "description": "Beta project",
        })
        assert resp.status_code == 200

        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM projects WHERE name = 'Beta'"
            ).fetchone()
        assert row is not None

    def test_delete_project(self, client, tmp_db):
        with get_connection() as conn:
            _insert_project(conn, "proj-1", "Doomed")

        resp = client.delete("/projects/proj-1")
        assert resp.status_code == 200

        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM projects WHERE id = 'proj-1'"
            ).fetchone()
        assert row is None

    def test_detail_page(self, client, tmp_db):
        with get_connection() as conn:
            _insert_project(conn, "proj-1", "Alpha")
            _insert_topic(conn, "topic-1", "proj-1", "Design")

        resp = client.get("/projects/proj-1")
        assert resp.status_code == 200
        assert "Alpha" in resp.text
        assert "Design" in resp.text

    def test_detail_not_found(self, client, tmp_db):
        resp = client.get("/projects/nonexistent")
        assert resp.status_code == 404

    def test_create_topic(self, client, tmp_db):
        with get_connection() as conn:
            _insert_project(conn, "proj-1", "Alpha")

        resp = client.post("/projects/proj-1/topics", data={
            "name": "Research",
            "description": "Research tasks",
        })
        assert resp.status_code == 200

        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM topics WHERE name = 'Research'"
            ).fetchone()
        assert row is not None
        assert row["project_id"] == "proj-1"

    def test_delete_topic(self, client, tmp_db):
        with get_connection() as conn:
            _insert_project(conn, "proj-1", "Alpha")
            _insert_topic(conn, "topic-1", "proj-1", "Doomed")

        resp = client.delete("/projects/topics/topic-1")
        assert resp.status_code == 200

        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM topics WHERE id = 'topic-1'"
            ).fetchone()
        assert row is None

    def test_auto_assign_preview(self, client, tmp_db):
        with get_connection() as conn:
            _insert_project(conn, "proj-1", "Alpha")
            _insert_topic(conn, "topic-1", "proj-1", "Design")
            _insert_conversation(conn, "conv-1", "Design meeting")
            _insert_tag(conn, "tag-1", "design-review")
            _link_tag_to_conv(conn, "conv-1", "tag-1")

        resp = client.post("/projects/proj-1/auto-assign")
        assert resp.status_code == 200
        assert "Design" in resp.text

    def test_auto_assign_apply(self, client, tmp_db):
        with get_connection() as conn:
            _insert_project(conn, "proj-1", "Alpha")
            _insert_topic(conn, "topic-1", "proj-1", "Design")
            _insert_conversation(conn, "conv-1", "Design meeting")
            _insert_tag(conn, "tag-1", "design-review")
            _link_tag_to_conv(conn, "conv-1", "tag-1")

        resp = client.post("/projects/proj-1/auto-assign/apply")
        assert resp.status_code == 200

        with get_connection() as conn:
            row = conn.execute(
                "SELECT topic_id FROM conversations WHERE id = 'conv-1'"
            ).fetchone()
        assert row["topic_id"] == "topic-1"


# ---------------------------------------------------------------------------
# Relationships
# ---------------------------------------------------------------------------

class TestRelationships:
    def test_list_loads(self, client, tmp_db):
        resp = client.get("/relationships")
        assert resp.status_code == 200
        assert "Relationships" in resp.text

    def test_list_empty(self, client, tmp_db):
        resp = client.get("/relationships")
        assert "No relationships found" in resp.text

    def test_infer_relationships(self, client, tmp_db):
        with get_connection() as conn:
            _insert_account(conn)
            _insert_contact(conn, "ct-1", "Alice", "alice@a.com")
            _insert_contact(conn, "ct-2", "Bob", "bob@b.com")
            _insert_conversation(conn, "conv-1", "Chat")
            _insert_participant(conn, "conv-1", "alice@a.com", contact_id="ct-1")
            _insert_participant(conn, "conv-1", "bob@b.com", contact_id="ct-2")

        resp = client.post("/relationships/infer")
        assert resp.status_code == 200
        assert "relationship(s) inferred" in resp.text

    def test_search_partial(self, client, tmp_db):
        resp = client.get("/relationships/search")
        assert resp.status_code == 200

    def test_list_shows_type_and_source(self, client, tmp_db):
        with get_connection() as conn:
            _insert_account(conn)
            _insert_contact(conn, "ct-1", "Alice", "alice@a.com")
            _insert_contact(conn, "ct-2", "Bob", "bob@b.com")
            _insert_conversation(conn, "conv-1", "Chat")
            _insert_participant(conn, "conv-1", "alice@a.com", contact_id="ct-1")
            _insert_participant(conn, "conv-1", "bob@b.com", contact_id="ct-2")

        client.post("/relationships/infer")
        resp = client.get("/relationships")
        assert "KNOWS" in resp.text
        assert "inferred" in resp.text

    def test_filter_by_type(self, client, tmp_db):
        resp = client.get("/relationships?type_id=rt-knows")
        assert resp.status_code == 200

    def test_filter_by_source(self, client, tmp_db):
        resp = client.get("/relationships?source=manual")
        assert resp.status_code == 200

    def test_create_manual_relationship(self, client, tmp_db):
        """Creating a bidirectional type (WORKS_WITH) should create two linked rows."""
        with get_connection() as conn:
            _insert_contact(conn, "ct-1", "Alice", "alice@a.com")
            _insert_contact(conn, "ct-2", "Bob", "bob@b.com")

        resp = client.post("/relationships", data={
            "relationship_type_id": "rt-works-with",
            "from_entity_id": "ct-1",
            "to_entity_id": "ct-2",
        })
        assert resp.status_code == 200

        with get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM relationships WHERE source = 'manual' ORDER BY from_entity_id"
            ).fetchall()
        assert len(rows) == 2
        r1, r2 = dict(rows[0]), dict(rows[1])
        assert r1["relationship_type_id"] == "rt-works-with"
        assert r1["paired_relationship_id"] == r2["id"]
        assert r2["paired_relationship_id"] == r1["id"]
        assert r1["from_entity_id"] == "ct-1"
        assert r2["from_entity_id"] == "ct-2"

    def test_delete_manual_relationship(self, client, tmp_db):
        """Deleting a bidirectional manual relationship should delete both rows."""
        with get_connection() as conn:
            _insert_contact(conn, "ct-1", "Alice", "alice@a.com")
            _insert_contact(conn, "ct-2", "Bob", "bob@b.com")
            # Insert both rows first with NULL paired_relationship_id
            conn.execute(
                """INSERT INTO relationships
                   (id, relationship_type_id, from_entity_type, from_entity_id,
                    to_entity_type, to_entity_id,
                    source, created_at, updated_at)
                   VALUES ('rel-1', 'rt-works-with', 'contact', 'ct-1',
                           'contact', 'ct-2', 'manual', ?, ?)""",
                (_NOW, _NOW),
            )
            conn.execute(
                """INSERT INTO relationships
                   (id, relationship_type_id, from_entity_type, from_entity_id,
                    to_entity_type, to_entity_id,
                    source, created_at, updated_at)
                   VALUES ('rel-2', 'rt-works-with', 'contact', 'ct-2',
                           'contact', 'ct-1', 'manual', ?, ?)""",
                (_NOW, _NOW),
            )
            # Then link them
            conn.execute(
                "UPDATE relationships SET paired_relationship_id = 'rel-2' WHERE id = 'rel-1'"
            )
            conn.execute(
                "UPDATE relationships SET paired_relationship_id = 'rel-1' WHERE id = 'rel-2'"
            )

        resp = client.delete("/relationships/rel-1")
        assert resp.status_code == 200

        with get_connection() as conn:
            row1 = conn.execute(
                "SELECT * FROM relationships WHERE id = 'rel-1'"
            ).fetchone()
            row2 = conn.execute(
                "SELECT * FROM relationships WHERE id = 'rel-2'"
            ).fetchone()
        assert row1 is None
        assert row2 is None

    def test_cannot_delete_inferred_relationship(self, client, tmp_db):
        with get_connection() as conn:
            _insert_contact(conn, "ct-1", "Alice", "alice@a.com")
            _insert_contact(conn, "ct-2", "Bob", "bob@b.com")
            conn.execute(
                """INSERT INTO relationships
                   (id, relationship_type_id, from_entity_type, from_entity_id,
                    to_entity_type, to_entity_id, source, created_at, updated_at)
                   VALUES ('rel-1', 'rt-knows', 'contact', 'ct-1',
                           'contact', 'ct-2', 'inferred', ?, ?)""",
                (_NOW, _NOW),
            )

        resp = client.delete("/relationships/rel-1")
        assert resp.status_code == 400

    def test_create_unidirectional_relationship(self, client, tmp_db):
        """Creating a unidirectional type (REPORTS_TO) should create only one row."""
        with get_connection() as conn:
            _insert_contact(conn, "ct-1", "Alice", "alice@a.com")
            _insert_contact(conn, "ct-2", "Bob", "bob@b.com")

        resp = client.post("/relationships", data={
            "relationship_type_id": "rt-reports-to",
            "from_entity_id": "ct-1",
            "to_entity_id": "ct-2",
        })
        assert resp.status_code == 200

        with get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM relationships WHERE source = 'manual'"
            ).fetchall()
        assert len(rows) == 1
        row = dict(rows[0])
        assert row["paired_relationship_id"] is None
        assert row["from_entity_id"] == "ct-1"
        assert row["to_entity_id"] == "ct-2"


# ---------------------------------------------------------------------------
# Relationship Types Admin
# ---------------------------------------------------------------------------

class TestRelationshipTypes:
    def test_type_list_loads(self, client, tmp_db):
        resp = client.get("/relationships/types")
        assert resp.status_code == 200
        assert "KNOWS" in resp.text

    def test_create_type(self, client, tmp_db):
        resp = client.post("/relationships/types", data={
            "name": "MENTOR",
            "from_entity_type": "contact",
            "to_entity_type": "contact",
            "forward_label": "Mentors",
            "reverse_label": "Mentored by",
            "description": "Mentorship",
        })
        assert resp.status_code == 200

        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM relationship_types WHERE name = 'MENTOR'"
            ).fetchone()
        assert row is not None
        assert row["forward_label"] == "Mentors"

    def test_delete_user_type(self, client, tmp_db):
        with get_connection() as conn:
            conn.execute(
                """INSERT INTO relationship_types
                   (id, name, from_entity_type, to_entity_type,
                    forward_label, reverse_label, is_system,
                    created_at, updated_at)
                   VALUES ('rt-test', 'TEST_TYPE', 'contact', 'contact',
                           'A', 'B', 0, ?, ?)""",
                (_NOW, _NOW),
            )

        resp = client.delete("/relationships/types/rt-test")
        assert resp.status_code == 200

    def test_cannot_delete_system_type(self, client, tmp_db):
        resp = client.delete("/relationships/types/rt-knows")
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Assign / Unassign conversations
# ---------------------------------------------------------------------------

class TestAssignment:
    def test_assign_conversation(self, client, tmp_db):
        with get_connection() as conn:
            _insert_project(conn, "proj-1", "Alpha")
            _insert_topic(conn, "topic-1", "proj-1", "Design")
            _insert_conversation(conn, "conv-1", "Thread")

        resp = client.post("/conversations/conv-1/assign",
                           data={"topic_id": "topic-1"})
        assert resp.status_code == 200

        with get_connection() as conn:
            row = conn.execute(
                "SELECT topic_id FROM conversations WHERE id = 'conv-1'"
            ).fetchone()
        assert row["topic_id"] == "topic-1"

    def test_unassign_conversation(self, client, tmp_db):
        with get_connection() as conn:
            _insert_project(conn, "proj-1", "Alpha")
            _insert_topic(conn, "topic-1", "proj-1", "Design")
            _insert_conversation(conn, "conv-1", "Thread", topic_id="topic-1")

        resp = client.post("/conversations/conv-1/unassign")
        assert resp.status_code == 200

        with get_connection() as conn:
            row = conn.execute(
                "SELECT topic_id FROM conversations WHERE id = 'conv-1'"
            ).fetchone()
        assert row["topic_id"] is None


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------

def _insert_event(conn, event_id, title="Team Standup", event_type="meeting",
                  start_datetime="2026-03-01T10:00:00", location=None,
                  status="confirmed", source="manual"):
    conn.execute(
        "INSERT OR IGNORE INTO events "
        "(id, title, event_type, start_datetime, location, status, source, "
        "created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (event_id, title, event_type, start_datetime, location, status,
         source, _NOW, _NOW),
    )


class TestEvents:
    def test_list_loads(self, client, tmp_db):
        resp = client.get("/events")
        assert resp.status_code == 200
        assert "Events" in resp.text

    def test_list_shows_events(self, client, tmp_db):
        with get_connection() as conn:
            _insert_event(conn, "ev-1", "Team Standup")
            _insert_event(conn, "ev-2", "Board Meeting", event_type="meeting")

        resp = client.get("/events")
        assert "Team Standup" in resp.text
        assert "Board Meeting" in resp.text

    def test_search_events(self, client, tmp_db):
        with get_connection() as conn:
            _insert_event(conn, "ev-1", "Team Standup")
            _insert_event(conn, "ev-2", "Board Meeting")

        resp = client.get("/events/search?q=Board")
        assert resp.status_code == 200
        assert "Board Meeting" in resp.text
        assert "Team Standup" not in resp.text

    def test_type_filter(self, client, tmp_db):
        with get_connection() as conn:
            _insert_event(conn, "ev-1", "Team Standup", event_type="meeting")
            _insert_event(conn, "ev-2", "Jane Birthday", event_type="birthday")

        resp = client.get("/events/search?event_type=birthday")
        assert "Jane Birthday" in resp.text
        assert "Team Standup" not in resp.text

    def test_create_event(self, client, tmp_db):
        resp = client.post("/events", data={
            "title": "New Standup",
            "event_type": "meeting",
            "start_datetime": "2026-03-15T09:00",
            "end_datetime": "",
            "start_date": "",
            "end_date": "",
            "is_all_day": "",
            "location": "Room 42",
            "description": "Daily standup",
            "recurrence_type": "daily",
            "status": "confirmed",
        })
        assert resp.status_code == 200

        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM events WHERE title = 'New Standup'"
            ).fetchone()
        assert row is not None
        assert row["location"] == "Room 42"
        assert row["recurrence_type"] == "daily"

    def test_detail_page(self, client, tmp_db):
        with get_connection() as conn:
            _insert_event(conn, "ev-1", "Design Review",
                          location="Conference Room A")

        resp = client.get("/events/ev-1")
        assert resp.status_code == 200
        assert "Design Review" in resp.text
        assert "Conference Room A" in resp.text

    def test_detail_not_found(self, client, tmp_db):
        resp = client.get("/events/nonexistent")
        assert resp.status_code == 404

    def test_detail_shows_participants(self, client, tmp_db):
        with get_connection() as conn:
            _insert_event(conn, "ev-1", "Design Review")
            _insert_contact(conn, "ct-1", "Alice", "alice@a.com")
            conn.execute(
                "INSERT INTO event_participants (event_id, entity_type, entity_id, role) "
                "VALUES ('ev-1', 'contact', 'ct-1', 'organizer')",
            )

        resp = client.get("/events/ev-1")
        assert "Alice" in resp.text
        assert "organizer" in resp.text

    def test_detail_shows_conversations(self, client, tmp_db):
        with get_connection() as conn:
            _insert_event(conn, "ev-1", "Sprint Planning")
            _insert_conversation(conn, "conv-1", "Planning Notes")
            conn.execute(
                "INSERT INTO event_conversations (event_id, conversation_id, created_at) "
                "VALUES ('ev-1', 'conv-1', ?)",
                (_NOW,),
            )

        resp = client.get("/events/ev-1")
        assert "Planning Notes" in resp.text

    def test_delete_event(self, client, tmp_db):
        with get_connection() as conn:
            _insert_event(conn, "ev-1", "Doomed Event")

        resp = client.delete("/events/ev-1")
        assert resp.status_code == 200

        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM events WHERE id = 'ev-1'"
            ).fetchone()
        assert row is None


# ---------------------------------------------------------------------------
# Contact Detail
# ---------------------------------------------------------------------------

def _insert_phone_number(conn, phone_id, entity_type, entity_id, number,
                          phone_type="mobile"):
    conn.execute(
        "INSERT OR IGNORE INTO phone_numbers "
        "(id, entity_type, entity_id, phone_type, number, is_primary, source, "
        "created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, 0, '', ?, ?)",
        (phone_id, entity_type, entity_id, phone_type, number, _NOW, _NOW),
    )


def _insert_address(conn, address_id, entity_type, entity_id, city="",
                     state="", country="", address_type="work",
                     street="", postal_code=""):
    conn.execute(
        "INSERT OR IGNORE INTO addresses "
        "(id, entity_type, entity_id, address_type, street, city, state, "
        "postal_code, country, is_primary, source, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, '', ?, ?)",
        (address_id, entity_type, entity_id, address_type, street, city,
         state, postal_code, country, _NOW, _NOW),
    )


def _insert_email_address(conn, email_id, entity_type, entity_id, address,
                          email_type="general"):
    conn.execute(
        "INSERT OR IGNORE INTO email_addresses "
        "(id, entity_type, entity_id, email_type, address, is_primary, source, "
        "created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, 0, '', ?, ?)",
        (email_id, entity_type, entity_id, email_type, address, _NOW, _NOW),
    )


def _insert_social_profile(conn, profile_id, contact_id, platform, profile_url,
                             username=""):
    conn.execute(
        "INSERT OR IGNORE INTO contact_social_profiles "
        "(id, contact_id, platform, profile_url, username, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (profile_id, contact_id, platform, profile_url, username, _NOW, _NOW),
    )


def _insert_company_social_profile(conn, profile_id, company_id, platform,
                                    profile_url, username=""):
    conn.execute(
        "INSERT OR IGNORE INTO company_social_profiles "
        "(id, company_id, platform, profile_url, username, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (profile_id, company_id, platform, profile_url, username, _NOW, _NOW),
    )


class TestContactDetail:
    def test_detail_shows_identifiers(self, client, tmp_db):
        with get_connection() as conn:
            _insert_contact(conn, "ct-1", "Alice", "alice@example.com")
            conn.execute(
                "INSERT OR IGNORE INTO contact_identifiers "
                "(id, contact_id, type, value, created_at, updated_at) "
                "VALUES ('ci-extra', 'ct-1', 'linkedin', 'linkedin.com/alice', ?, ?)",
                (_NOW, _NOW),
            )

        resp = client.get("/contacts/ct-1")
        assert resp.status_code == 200
        assert "Identifiers (2)" in resp.text
        assert "alice@example.com" in resp.text
        assert "linkedin.com/alice" in resp.text

    def test_detail_shows_phones(self, client, tmp_db):
        with get_connection() as conn:
            _insert_contact(conn, "ct-1", "Alice", "alice@example.com")
            _insert_phone_number(conn, "ph-1", "contact", "ct-1", "+12015550100",
                                  phone_type="mobile")

        resp = client.get("/contacts/ct-1")
        assert resp.status_code == 200
        assert "Phone Numbers (1)" in resp.text
        assert "(201) 555-0100" in resp.text

    def test_detail_shows_addresses(self, client, tmp_db):
        with get_connection() as conn:
            _insert_contact(conn, "ct-1", "Alice", "alice@example.com")
            _insert_address(conn, "addr-1", "contact", "ct-1",
                            city="Boston", state="MA", country="US")

        resp = client.get("/contacts/ct-1")
        assert resp.status_code == 200
        assert "Addresses (1)" in resp.text
        assert "Boston" in resp.text

    def test_detail_shows_social_profiles(self, client, tmp_db):
        with get_connection() as conn:
            _insert_contact(conn, "ct-1", "Alice", "alice@example.com")
            _insert_social_profile(conn, "sp-1", "ct-1", "linkedin",
                                    "https://linkedin.com/in/alice",
                                    username="alice")

        resp = client.get("/contacts/ct-1")
        assert resp.status_code == 200
        assert "linkedin.com/in/alice" in resp.text
        assert "alice" in resp.text

    def test_edit_page_renders(self, client, tmp_db):
        with get_connection() as conn:
            _insert_contact(conn, "ct-1", "Alice", "alice@example.com")

        resp = client.get("/contacts/ct-1/edit")
        assert resp.status_code == 200
        assert "Edit Alice" in resp.text

    def test_edit_updates_fields(self, client, tmp_db):
        with get_connection() as conn:
            _insert_contact(conn, "ct-1", "Alice", "alice@example.com")
            _insert_company(conn, "co-1", "Acme Corp")

        resp = client.post("/contacts/ct-1/edit", data={
            "name": "Alice Smith",
            "company_id": "co-1",
            "source": "google",
            "status": "inactive",
        })
        assert resp.status_code in (200, 303)

        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM contacts WHERE id = 'ct-1'"
            ).fetchone()
        assert row["name"] == "Alice Smith"
        assert row["company_id"] == "co-1"
        assert row["status"] == "inactive"

    def test_add_identifier_via_web(self, client, tmp_db):
        with get_connection() as conn:
            _insert_contact(conn, "ct-1", "Alice", "alice@example.com")

        resp = client.post("/contacts/ct-1/identifiers", data={
            "type": "linkedin",
            "value": "linkedin.com/in/alice",
        })
        assert resp.status_code == 200
        assert "linkedin.com/in/alice" in resp.text

        with get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM contact_identifiers WHERE contact_id = 'ct-1'"
            ).fetchall()
        assert len(rows) == 2  # original email + new linkedin

    def test_remove_identifier_via_web(self, client, tmp_db):
        with get_connection() as conn:
            _insert_contact(conn, "ct-1", "Alice", "alice@example.com")

        resp = client.delete("/contacts/ct-1/identifiers/ci-ct-1")
        assert resp.status_code == 200

        with get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM contact_identifiers WHERE contact_id = 'ct-1'"
            ).fetchall()
        assert len(rows) == 0

    def test_add_phone_via_web(self, client, tmp_db):
        with get_connection() as conn:
            _insert_contact(conn, "ct-1", "Alice", "alice@example.com")

        resp = client.post("/contacts/ct-1/phones", data={
            "phone_type": "work",
            "number": "(201) 555-0200",
        })
        assert resp.status_code == 200
        assert "(201) 555-0200" in resp.text

        with get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM phone_numbers WHERE entity_id = 'ct-1'"
            ).fetchall()
        assert len(rows) == 1
        assert rows[0]["number"] == "+12015550200"

    def test_remove_phone_via_web(self, client, tmp_db):
        with get_connection() as conn:
            _insert_contact(conn, "ct-1", "Alice", "alice@example.com")
            _insert_phone_number(conn, "ph-1", "contact", "ct-1", "+1-555-0100")

        resp = client.delete("/contacts/ct-1/phones/ph-1")
        assert resp.status_code == 200

        with get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM phone_numbers WHERE entity_id = 'ct-1'"
            ).fetchall()
        assert len(rows) == 0

    def test_add_address_via_web(self, client, tmp_db):
        with get_connection() as conn:
            _insert_contact(conn, "ct-1", "Alice", "alice@example.com")

        resp = client.post("/contacts/ct-1/addresses", data={
            "address_type": "home",
            "street": "123 Elm St",
            "city": "Springfield",
            "state": "IL",
            "postal_code": "62701",
            "country": "US",
        })
        assert resp.status_code == 200
        assert "Springfield" in resp.text

        with get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM addresses WHERE entity_id = 'ct-1'"
            ).fetchall()
        assert len(rows) == 1
        assert rows[0]["city"] == "Springfield"

    def test_remove_address_via_web(self, client, tmp_db):
        with get_connection() as conn:
            _insert_contact(conn, "ct-1", "Alice", "alice@example.com")
            _insert_address(conn, "addr-1", "contact", "ct-1",
                            city="Boston", state="MA")

        resp = client.delete("/contacts/ct-1/addresses/addr-1")
        assert resp.status_code == 200

        with get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM addresses WHERE entity_id = 'ct-1'"
            ).fetchall()
        assert len(rows) == 0

    def test_detail_shows_emails(self, client, tmp_db):
        with get_connection() as conn:
            _insert_contact(conn, "ct-1", "Alice", "alice@example.com")
            _insert_email_address(conn, "em-1", "contact", "ct-1",
                                  "alice@work.com", email_type="work")

        resp = client.get("/contacts/ct-1")
        assert resp.status_code == 200
        assert "alice@work.com" in resp.text
        assert "Email Addresses" in resp.text

    def test_add_email_via_web(self, client, tmp_db):
        with get_connection() as conn:
            _insert_contact(conn, "ct-1", "Alice", "alice@example.com")

        resp = client.post("/contacts/ct-1/emails", data={
            "email_type": "work",
            "address": "alice@corp.com",
        })
        assert resp.status_code == 200
        assert "alice@corp.com" in resp.text

        with get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM email_addresses WHERE entity_id = 'ct-1'"
            ).fetchall()
        assert len(rows) == 1
        assert rows[0]["address"] == "alice@corp.com"

    def test_remove_email_via_web(self, client, tmp_db):
        with get_connection() as conn:
            _insert_contact(conn, "ct-1", "Alice", "alice@example.com")
            _insert_email_address(conn, "em-1", "contact", "ct-1",
                                  "alice@work.com")

        resp = client.delete("/contacts/ct-1/emails/em-1")
        assert resp.status_code == 200

        with get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM email_addresses WHERE entity_id = 'ct-1'"
            ).fetchall()
        assert len(rows) == 0


# ---------------------------------------------------------------------------
# Sync Now
# ---------------------------------------------------------------------------

class TestSync:
    """Tests for POST /sync endpoint."""

    def _insert_account_with_token(self, conn, account_id="acct-1",
                                   email="test@example.com",
                                   token_path="/tmp/token.json",
                                   initial_sync_done=1):
        conn.execute(
            "INSERT OR IGNORE INTO provider_accounts "
            "(id, provider, account_type, email_address, auth_token_path, "
            "initial_sync_done, customer_id, created_at, updated_at) "
            "VALUES (?, 'gmail', 'email', ?, ?, ?, 'cust-test', ?, ?)",
            (account_id, email, token_path, initial_sync_done, _NOW, _NOW),
        )
        conn.execute(
            "INSERT OR IGNORE INTO user_provider_accounts "
            "(id, user_id, account_id, role, created_at) "
            "VALUES (?, 'user-test', ?, 'owner', ?)",
            (f"upa-{account_id}", account_id, _NOW),
        )

    def test_sync_no_accounts(self, client, tmp_db):
        resp = client.post("/sync")
        assert resp.status_code == 200
        assert "No accounts registered" in resp.text

    def test_sync_success(self, client, tmp_db):
        with get_connection() as conn:
            self._insert_account_with_token(conn)

        with (
            _patch("poc.auth.get_credentials_for_account") as mock_creds,
            _patch("poc.gmail_client.get_user_email", return_value="test@example.com"),
            _patch("poc.sync.sync_contacts", return_value=42),
            _patch("poc.sync.incremental_sync",
                   return_value={"messages_fetched": 10, "messages_stored": 8,
                                 "conversations_created": 3, "conversations_updated": 5}),
            _patch("poc.sync.process_conversations",
                   return_value=(4, 2, 6)),
        ):
            mock_creds.return_value = "fake-creds"
            resp = client.post("/sync")

        assert resp.status_code == 200
        assert "Synced 1 account(s)" in resp.text
        assert "42 contacts" in resp.text
        assert "10 emails fetched" in resp.text
        assert "4 triaged" in resp.text
        assert "2 summarized" in resp.text

    def test_sync_initial_sync_path(self, client, tmp_db):
        """Account with initial_sync_done=0 takes the initial_sync path."""
        with get_connection() as conn:
            self._insert_account_with_token(conn, initial_sync_done=0)

        with (
            _patch("poc.auth.get_credentials_for_account",
                   return_value="fake-creds"),
            _patch("poc.gmail_client.get_user_email", return_value="test@example.com"),
            _patch("poc.sync.sync_contacts", return_value=5),
            _patch("poc.sync.initial_sync",
                   return_value={"messages_fetched": 20, "messages_stored": 18,
                                 "conversations_created": 10}) as mock_initial,
            _patch("poc.sync.process_conversations",
                   return_value=(0, 0, 0)),
        ):
            resp = client.post("/sync")

        assert resp.status_code == 200
        mock_initial.assert_called_once()
        assert "20 emails fetched" in resp.text

    def test_sync_partial_failure(self, client, tmp_db):
        with get_connection() as conn:
            self._insert_account_with_token(conn)

        with (
            _patch("poc.auth.get_credentials_for_account",
                   return_value="fake-creds"),
            _patch("poc.gmail_client.get_user_email", return_value="test@example.com"),
            _patch("poc.sync.sync_contacts",
                   side_effect=RuntimeError("API error")),
            _patch("poc.sync.incremental_sync",
                   return_value={"messages_fetched": 5, "messages_stored": 5,
                                 "conversations_created": 1, "conversations_updated": 2}),
            _patch("poc.sync.process_conversations",
                   return_value=(1, 0, 0)),
        ):
            resp = client.post("/sync")

        assert resp.status_code == 200
        assert "Synced 1 account(s)" in resp.text
        assert "contact sync failed" in resp.text

    def test_sync_auth_failure(self, client, tmp_db):
        with get_connection() as conn:
            self._insert_account_with_token(conn)

        with _patch("poc.auth.get_credentials_for_account",
                     side_effect=RuntimeError("bad token")):
            resp = client.post("/sync")

        assert resp.status_code == 200
        assert "auth failed" in resp.text


# ---------------------------------------------------------------------------
# Date Display
# ---------------------------------------------------------------------------

class TestDateDisplay:
    """Verify that <time> elements and timezone infrastructure are rendered."""

    def test_dashboard_has_timezone_meta(self, client, tmp_db):
        resp = client.get("/")
        assert '<meta name="crm-timezone"' in resp.text

    def test_dashboard_has_dates_js(self, client, tmp_db):
        resp = client.get("/")
        assert 'src="/static/dates.js"' in resp.text

    def test_dashboard_recent_has_time_element(self, client, tmp_db):
        with get_connection() as conn:
            _insert_conversation(conn, "conv-1", "Thread")

        resp = client.get("/")
        assert "<time " in resp.text
        assert 'data-format="datetime"' in resp.text

    def test_conversation_list_has_time_element(self, client, tmp_db):
        with get_connection() as conn:
            _insert_conversation(conn, "conv-1", "Thread")

        resp = client.get("/conversations")
        assert "<time " in resp.text
        assert 'data-format="datetime"' in resp.text

    def test_conversation_search_partial_has_time_element(self, client, tmp_db):
        with get_connection() as conn:
            _insert_conversation(conn, "conv-1", "Thread")

        resp = client.get("/conversations/search?q=Thread")
        assert "<time " in resp.text

    def test_conversation_detail_has_time_elements(self, client, tmp_db):
        with get_connection() as conn:
            _insert_account(conn)
            _insert_conversation(conn, "conv-1", "Thread")
            _insert_communication(conn, "msg-1", content="Hello")
            _link_comm_to_conv(conn, "conv-1", "msg-1")

        resp = client.get("/conversations/conv-1")
        # Should have time elements for last_activity and message timestamp
        assert resp.text.count("<time ") >= 2

    def test_contact_detail_has_time_element(self, client, tmp_db):
        with get_connection() as conn:
            _insert_contact(conn, "ct-1", "Alice", "alice@a.com")
            _insert_conversation(conn, "conv-1", "With Alice")
            _insert_participant(conn, "conv-1", "alice@a.com", contact_id="ct-1")

        resp = client.get("/contacts/ct-1")
        assert "<time " in resp.text

    def test_event_list_has_time_element(self, client, tmp_db):
        with get_connection() as conn:
            _insert_event(conn, "ev-1", "Standup")

        resp = client.get("/events")
        assert "<time " in resp.text
        assert 'data-format="datetime"' in resp.text

    def test_event_detail_has_time_elements(self, client, tmp_db):
        with get_connection() as conn:
            _insert_event(conn, "ev-1", "Standup")

        resp = client.get("/events/ev-1")
        assert "<time " in resp.text

    def test_event_date_only_uses_date_format(self, client, tmp_db):
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO events "
                "(id, title, event_type, start_date, status, source, "
                "created_at, updated_at) "
                "VALUES ('ev-d', 'All Day', 'meeting', '2026-03-01', "
                "'confirmed', 'manual', ?, ?)",
                (_NOW, _NOW),
            )

        resp = client.get("/events/ev-d")
        assert 'data-format="date"' in resp.text

    def test_dates_js_is_served(self, client, tmp_db):
        resp = client.get("/static/dates.js")
        assert resp.status_code == 200
        assert "Intl.DateTimeFormat" in resp.text
