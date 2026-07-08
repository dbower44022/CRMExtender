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
        "(id, account_id, channel, timestamp, original_text, sender_address, subject, "
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
                     customer_id="cust-test"):
    conn.execute(
        "INSERT OR IGNORE INTO contacts "
        "(id, name, customer_id, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (contact_id, name, customer_id, _NOW, _NOW),
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


def _insert_affiliation(conn, contact_id, company_id, is_primary=1, is_current=1):
    """Link a contact to a company via contact_companies junction table."""
    import uuid as _uuid
    conn.execute(
        "INSERT OR IGNORE INTO contact_companies "
        "(id, contact_id, company_id, is_primary, is_current, source, "
        "created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, 'test', ?, ?)",
        (str(_uuid.uuid4()), contact_id, company_id, is_primary, is_current,
         _NOW, _NOW),
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
        "(conversation_id, email_address, address, contact_id, communication_count, "
        "first_seen_at, last_seen_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (conv_id, address, address, contact_id, communication_count, _NOW, _NOW),
    )


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Conversations
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Contacts
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Companies
# ---------------------------------------------------------------------------


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


    def test_detail_no_social_profiles(self, client, tmp_db):
        with get_connection() as conn:
            _insert_company(conn, "co-1", "Acme Corp")

        resp = client.get("/companies/co-1")
        assert resp.status_code == 200
        assert "Social Profiles" not in resp.text


# ---------------------------------------------------------------------------
# Projects & Topics
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Relationships
# ---------------------------------------------------------------------------

class TestRelationships:


    def test_search_partial(self, client, tmp_db):
        resp = client.get("/relationships/search")
        assert resp.status_code == 200


    def test_filter_by_type(self, client, tmp_db):
        resp = client.get("/relationships?type_id=rt-knows")
        assert resp.status_code == 200

    def test_filter_by_source(self, client, tmp_db):
        resp = client.get("/relationships?source=manual")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Relationship Types Admin
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Assign / Unassign conversations
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Sync Now
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Date Display
# ---------------------------------------------------------------------------

