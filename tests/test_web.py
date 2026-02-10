"""Tests for the CRM Extender web UI."""

from __future__ import annotations

from datetime import datetime, timezone

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
    return db_file


@pytest.fixture()
def client(tmp_db):
    from poc.web.app import create_app
    app = create_app()
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_NOW = datetime.now(timezone.utc).isoformat()


def _insert_account(conn, account_id="acct-1", email="test@example.com"):
    conn.execute(
        "INSERT OR IGNORE INTO provider_accounts "
        "(id, provider, account_type, email_address, created_at, updated_at) "
        "VALUES (?, 'gmail', 'email', ?, ?, ?)",
        (account_id, email, _NOW, _NOW),
    )


def _insert_conversation(conn, conv_id, title="Test subject", topic_id=None,
                          triage_result=None, status="active",
                          communication_count=1, dismissed=0):
    conn.execute(
        "INSERT OR IGNORE INTO conversations "
        "(id, topic_id, title, status, triage_result, dismissed, "
        "communication_count, participant_count, last_activity_at, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?)",
        (conv_id, topic_id, title, status, triage_result, dismissed,
         communication_count, _NOW, _NOW, _NOW),
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
                     company_id=None):
    conn.execute(
        "INSERT OR IGNORE INTO contacts "
        "(id, name, company_id, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
        (contact_id, name, company_id, _NOW, _NOW),
    )
    conn.execute(
        "INSERT OR IGNORE INTO contact_identifiers "
        "(id, contact_id, type, value, created_at, updated_at) "
        "VALUES (?, ?, 'email', ?, ?, ?)",
        (f"ci-{contact_id}", contact_id, email, _NOW, _NOW),
    )


def _insert_company(conn, company_id, name="Acme Corp", domain="acme.com"):
    conn.execute(
        "INSERT OR IGNORE INTO companies "
        "(id, name, domain, status, created_at, updated_at) "
        "VALUES (?, ?, ?, 'active', ?, ?)",
        (company_id, name, domain, _NOW, _NOW),
    )


def _insert_project(conn, project_id, name="My Project"):
    conn.execute(
        "INSERT OR IGNORE INTO projects "
        "(id, name, status, created_at, updated_at) VALUES (?, ?, 'active', ?, ?)",
        (project_id, name, _NOW, _NOW),
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
