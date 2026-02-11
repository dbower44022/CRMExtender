"""Tests for organizational hierarchy: users, projects, topics."""

import sqlite3
import uuid
from datetime import datetime, timezone

import pytest

from poc.database import init_db, get_connection
from poc.models import Project, Topic, User
from poc.hierarchy import (
    assign_conversation_to_topic,
    bootstrap_user,
    create_project,
    create_topic,
    delete_project,
    delete_topic,
    find_project_by_name,
    find_topic_by_name,
    get_current_user,
    get_hierarchy_stats,
    get_project,
    get_topic,
    get_topic_stats,
    list_projects,
    list_topics,
    resolve_conversation_by_prefix,
    unassign_conversation,
)


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


def _insert_account(conn, account_id="acct-1", email="test@example.com"):
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT OR IGNORE INTO provider_accounts "
        "(id, provider, account_type, email_address, created_at, updated_at) "
        "VALUES (?, 'gmail', 'email', ?, ?, ?)",
        (account_id, email, now, now),
    )


def _insert_conversation(conn, conv_id, topic_id=None):
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT OR IGNORE INTO conversations "
        "(id, topic_id, title, dismissed, created_at, updated_at) "
        "VALUES (?, ?, 'Test subject', 0, ?, ?)",
        (conv_id, topic_id, now, now),
    )


# ---------------------------------------------------------------------------
# Model round-trip tests
# ---------------------------------------------------------------------------

class TestUserModel:

    def test_to_row_from_row_roundtrip(self):
        user = User(email="alice@example.com", name="Alice", role="admin", is_active=True)
        row = user.to_row(user_id="u-123")
        assert row["id"] == "u-123"
        assert row["email"] == "alice@example.com"
        assert row["is_active"] == 1

        rebuilt = User.from_row(row)
        assert rebuilt.email == "alice@example.com"
        assert rebuilt.name == "Alice"
        assert rebuilt.role == "admin"
        assert rebuilt.is_active is True

    def test_defaults(self):
        user = User(email="bob@example.com")
        assert user.name == ""
        assert user.role == "user"
        assert user.is_active is True


class TestProjectModel:

    def test_to_row_from_row_roundtrip(self):
        proj = Project(name="Alpha", description="First project", parent_id="p-0",
                       owner_id="u-1", status="active")
        row = proj.to_row(project_id="p-123")
        assert row["id"] == "p-123"
        assert row["name"] == "Alpha"

        rebuilt = Project.from_row(row)
        assert rebuilt.name == "Alpha"
        assert rebuilt.description == "First project"
        assert rebuilt.parent_id == "p-0"
        assert rebuilt.owner_id == "u-1"

    def test_defaults(self):
        proj = Project(name="Beta")
        assert proj.description == ""
        assert proj.parent_id is None
        assert proj.status == "active"


class TestTopicModel:

    def test_to_row_from_row_roundtrip(self):
        topic = Topic(project_id="p-1", name="Board Meetings", description="Monthly meetings")
        row = topic.to_row(topic_id="t-123")
        assert row["id"] == "t-123"
        assert row["project_id"] == "p-1"

        rebuilt = Topic.from_row(row)
        assert rebuilt.project_id == "p-1"
        assert rebuilt.name == "Board Meetings"
        assert rebuilt.description == "Monthly meetings"
        assert rebuilt.source == "user"

    def test_defaults(self):
        topic = Topic(project_id="p-1", name="General")
        assert topic.description == ""
        assert topic.source == "user"


# ---------------------------------------------------------------------------
# Bootstrap user
# ---------------------------------------------------------------------------

class TestBootstrapUser:

    def test_bootstrap_creates_user(self, tmp_db):
        with get_connection() as conn:
            _insert_account(conn, email="alice@example.com")

        result = bootstrap_user()
        assert result["created"] is True
        assert result["email"] == "alice@example.com"

    def test_bootstrap_idempotent(self, tmp_db):
        with get_connection() as conn:
            _insert_account(conn, email="alice@example.com")

        r1 = bootstrap_user()
        r2 = bootstrap_user()
        assert r1["id"] == r2["id"]
        assert r2["created"] is False

    def test_bootstrap_no_accounts_raises(self, tmp_db):
        with pytest.raises(ValueError, match="No provider accounts"):
            bootstrap_user()

    def test_get_current_user(self, tmp_db):
        assert get_current_user() is None

        with get_connection() as conn:
            _insert_account(conn)
        bootstrap_user()

        user = get_current_user()
        assert user is not None
        assert user["email"] == "test@example.com"


# ---------------------------------------------------------------------------
# Project CRUD
# ---------------------------------------------------------------------------

class TestProjectCRUD:

    def test_create_and_list(self, tmp_db):
        row = create_project("Alpha", description="First project")
        assert row["name"] == "Alpha"

        projects = list_projects()
        assert len(projects) == 1
        assert projects[0]["name"] == "Alpha"

    def test_get_and_find(self, tmp_db):
        row = create_project("Beta")

        found = get_project(row["id"])
        assert found is not None
        assert found["name"] == "Beta"

        by_name = find_project_by_name("Beta")
        assert by_name is not None
        assert by_name["id"] == row["id"]

        assert find_project_by_name("Nonexistent") is None

    def test_duplicate_name_raises(self, tmp_db):
        create_project("Alpha")
        with pytest.raises(ValueError, match="already exists"):
            create_project("Alpha")

    def test_nested_project(self, tmp_db):
        parent = create_project("Parent")
        child = create_project("Child", parent_name="Parent")
        assert child["parent_id"] == parent["id"]

    def test_nonexistent_parent_raises(self, tmp_db):
        with pytest.raises(ValueError, match="Parent project .* not found"):
            create_project("Orphan", parent_name="Ghost")

    def test_delete_project(self, tmp_db):
        proj = create_project("Doomed")
        # Add a topic and assign a conversation
        topic = create_topic(proj["id"], "Sub-topic")
        with get_connection() as conn:
            _insert_conversation(conn, "conv-1", topic_id=topic["id"])

        impact = delete_project(proj["id"])
        assert impact["topics_removed"] == 1
        assert impact["conversations_unassigned"] == 1

        # Project and topic gone
        assert get_project(proj["id"]) is None
        assert get_topic(topic["id"]) is None

        # Conversation still exists, topic_id set to NULL
        with get_connection() as conn:
            conv = conn.execute(
                "SELECT topic_id FROM conversations WHERE id = 'conv-1'"
            ).fetchone()
        assert conv["topic_id"] is None


# ---------------------------------------------------------------------------
# Topic CRUD
# ---------------------------------------------------------------------------

class TestTopicCRUD:

    def test_create_and_list(self, tmp_db):
        proj = create_project("Proj")
        topic = create_topic(proj["id"], "Meetings", description="Weekly sync")
        assert topic["name"] == "Meetings"

        topics = list_topics(proj["id"])
        assert len(topics) == 1
        assert topics[0]["name"] == "Meetings"

    def test_get_and_find(self, tmp_db):
        proj = create_project("Proj")
        topic = create_topic(proj["id"], "Reports")

        found = get_topic(topic["id"])
        assert found is not None
        assert found["name"] == "Reports"

        by_name = find_topic_by_name(proj["id"], "Reports")
        assert by_name is not None
        assert by_name["id"] == topic["id"]

        assert find_topic_by_name(proj["id"], "Nonexistent") is None

    def test_duplicate_topic_in_project_raises(self, tmp_db):
        proj = create_project("Proj")
        create_topic(proj["id"], "Alpha")
        with pytest.raises(ValueError, match="already exists"):
            create_topic(proj["id"], "Alpha")

    def test_same_name_different_projects(self, tmp_db):
        p1 = create_project("Proj1")
        p2 = create_project("Proj2")
        t1 = create_topic(p1["id"], "General")
        t2 = create_topic(p2["id"], "General")
        assert t1["id"] != t2["id"]

    def test_nonexistent_project_raises(self, tmp_db):
        with pytest.raises(ValueError, match="Project not found"):
            create_topic("fake-id", "Topic")

    def test_delete_topic(self, tmp_db):
        proj = create_project("Proj")
        topic = create_topic(proj["id"], "Doomed")
        with get_connection() as conn:
            _insert_conversation(conn, "conv-1", topic_id=topic["id"])

        impact = delete_topic(topic["id"])
        assert impact["conversations_unassigned"] == 1

        assert get_topic(topic["id"]) is None

        with get_connection() as conn:
            conv = conn.execute(
                "SELECT topic_id FROM conversations WHERE id = 'conv-1'"
            ).fetchone()
        assert conv["topic_id"] is None


# ---------------------------------------------------------------------------
# Conversation assignment
# ---------------------------------------------------------------------------

class TestConversationAssignment:

    def test_assign_and_unassign(self, tmp_db):
        proj = create_project("Proj")
        topic = create_topic(proj["id"], "Board")
        with get_connection() as conn:
            _insert_conversation(conn, "conv-abc123")

        assign_conversation_to_topic("conv-abc123", topic["id"])

        with get_connection() as conn:
            row = conn.execute(
                "SELECT topic_id FROM conversations WHERE id = 'conv-abc123'"
            ).fetchone()
        assert row["topic_id"] == topic["id"]

        unassign_conversation("conv-abc123")

        with get_connection() as conn:
            row = conn.execute(
                "SELECT topic_id FROM conversations WHERE id = 'conv-abc123'"
            ).fetchone()
        assert row["topic_id"] is None

    def test_assign_nonexistent_conversation_raises(self, tmp_db):
        proj = create_project("Proj")
        topic = create_topic(proj["id"], "Board")
        with pytest.raises(ValueError, match="Conversation not found"):
            assign_conversation_to_topic("fake-id", topic["id"])

    def test_assign_nonexistent_topic_raises(self, tmp_db):
        with get_connection() as conn:
            _insert_conversation(conn, "conv-1")
        with pytest.raises(ValueError, match="Topic not found"):
            assign_conversation_to_topic("conv-1", "fake-id")

    def test_unassign_nonexistent_raises(self, tmp_db):
        with pytest.raises(ValueError, match="Conversation not found"):
            unassign_conversation("fake-id")


# ---------------------------------------------------------------------------
# Conversation prefix resolution
# ---------------------------------------------------------------------------

class TestResolveConversationByPrefix:

    def test_exact_match(self, tmp_db):
        with get_connection() as conn:
            _insert_conversation(conn, "conv-abc12345")

        result = resolve_conversation_by_prefix("conv-abc12345")
        assert result == "conv-abc12345"

    def test_prefix_match(self, tmp_db):
        with get_connection() as conn:
            _insert_conversation(conn, "conv-abc12345")

        result = resolve_conversation_by_prefix("conv-abc")
        assert result == "conv-abc12345"

    def test_no_match_raises(self, tmp_db):
        with pytest.raises(ValueError, match="No conversation matching"):
            resolve_conversation_by_prefix("nonexistent")

    def test_ambiguous_prefix_raises(self, tmp_db):
        with get_connection() as conn:
            _insert_conversation(conn, "conv-aa1")
            _insert_conversation(conn, "conv-aa2")

        with pytest.raises(ValueError, match="Ambiguous prefix"):
            resolve_conversation_by_prefix("conv-aa")


# ---------------------------------------------------------------------------
# Stats queries
# ---------------------------------------------------------------------------

class TestStats:

    def test_hierarchy_stats(self, tmp_db):
        proj = create_project("Proj")
        topic = create_topic(proj["id"], "Board")
        with get_connection() as conn:
            _insert_conversation(conn, "conv-1", topic_id=topic["id"])
            _insert_conversation(conn, "conv-2", topic_id=topic["id"])

        stats = get_hierarchy_stats()
        assert len(stats) == 1
        assert stats[0]["name"] == "Proj"
        assert stats[0]["topic_count"] == 1
        assert stats[0]["conversation_count"] == 2

    def test_topic_stats(self, tmp_db):
        proj = create_project("Proj")
        t1 = create_topic(proj["id"], "Alpha")
        t2 = create_topic(proj["id"], "Beta")
        with get_connection() as conn:
            _insert_conversation(conn, "conv-1", topic_id=t1["id"])
            _insert_conversation(conn, "conv-2", topic_id=t1["id"])
            _insert_conversation(conn, "conv-3", topic_id=t2["id"])

        stats = get_topic_stats(proj["id"])
        assert len(stats) == 2

        by_name = {s["name"]: s for s in stats}
        assert by_name["Alpha"]["conversation_count"] == 2
        assert by_name["Beta"]["conversation_count"] == 1

    def test_empty_hierarchy(self, tmp_db):
        stats = get_hierarchy_stats()
        assert stats == []

    def test_project_with_no_topics(self, tmp_db):
        create_project("Empty")
        stats = get_hierarchy_stats()
        assert len(stats) == 1
        assert stats[0]["topic_count"] == 0
        assert stats[0]["conversation_count"] == 0
