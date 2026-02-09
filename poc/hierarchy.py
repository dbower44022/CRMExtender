"""Data access for the organizational hierarchy: users, projects, topics."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from .database import get_connection
from .models import Project, Topic, User


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

def bootstrap_user() -> dict:
    """Auto-create a user from the first provider_accounts email.

    Idempotent — returns the existing user if one already exists.
    Returns a dict with 'id', 'email', 'name', 'created' (bool).
    """
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT * FROM users WHERE is_active = 1 ORDER BY created_at LIMIT 1"
        ).fetchone()
        if existing:
            return {"id": existing["id"], "email": existing["email"],
                    "name": existing["name"], "created": False}

        account = conn.execute(
            "SELECT email_address, display_name FROM provider_accounts "
            "ORDER BY created_at LIMIT 1"
        ).fetchone()
        if not account:
            raise ValueError("No provider accounts found. Add an account first.")

        user = User(
            email=account["email_address"],
            name=account["display_name"] or "",
        )
        row = user.to_row()
        conn.execute(
            "INSERT INTO users (id, email, name, role, is_active, created_at, updated_at) "
            "VALUES (:id, :email, :name, :role, :is_active, :created_at, :updated_at)",
            row,
        )
        return {"id": row["id"], "email": row["email"],
                "name": row["name"], "created": True}


def get_current_user() -> dict | None:
    """Return the first active user row, or None."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE is_active = 1 ORDER BY created_at LIMIT 1"
        ).fetchone()
    return dict(row) if row else None


# ---------------------------------------------------------------------------
# Projects
# ---------------------------------------------------------------------------

def create_project(
    name: str,
    description: str = "",
    parent_name: str | None = None,
    owner_id: str | None = None,
) -> dict:
    """Create a project. Returns the new row as a dict.

    Raises ValueError on duplicate name or nonexistent parent.
    """
    with get_connection() as conn:
        # Check duplicate name
        dup = conn.execute(
            "SELECT id FROM projects WHERE name = ? AND status = 'active'", (name,)
        ).fetchone()
        if dup:
            raise ValueError(f"Project '{name}' already exists.")

        parent_id = None
        if parent_name:
            parent = conn.execute(
                "SELECT id FROM projects WHERE name = ? AND status = 'active'",
                (parent_name,),
            ).fetchone()
            if not parent:
                raise ValueError(f"Parent project '{parent_name}' not found.")
            parent_id = parent["id"]

        proj = Project(name=name, description=description,
                       parent_id=parent_id, owner_id=owner_id)
        row = proj.to_row()
        conn.execute(
            "INSERT INTO projects (id, parent_id, name, description, status, "
            "owner_id, created_at, updated_at) "
            "VALUES (:id, :parent_id, :name, :description, :status, "
            ":owner_id, :created_at, :updated_at)",
            row,
        )
        return row


def list_projects() -> list[dict]:
    """Return all active projects ordered by name."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM projects WHERE status = 'active' ORDER BY name"
        ).fetchall()
    return [dict(r) for r in rows]


def get_project(project_id: str) -> dict | None:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
    return dict(row) if row else None


def find_project_by_name(name: str) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM projects WHERE name = ? AND status = 'active'", (name,)
        ).fetchone()
    return dict(row) if row else None


def delete_project(project_id: str) -> dict:
    """Delete a project. Returns impact summary.

    CASCADE deletes topics; conversations get topic_id SET NULL.
    """
    with get_connection() as conn:
        # Count impact
        topic_count = conn.execute(
            "SELECT COUNT(*) AS cnt FROM topics WHERE project_id = ?", (project_id,)
        ).fetchone()["cnt"]
        conv_count = conn.execute(
            "SELECT COUNT(*) AS cnt FROM conversations c "
            "JOIN topics t ON c.topic_id = t.id WHERE t.project_id = ?",
            (project_id,),
        ).fetchone()["cnt"]

        # FK CASCADE handles topics; conversations.topic_id ON DELETE SET NULL
        conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))

    return {"topics_removed": topic_count, "conversations_unassigned": conv_count}


# ---------------------------------------------------------------------------
# Topics
# ---------------------------------------------------------------------------

def create_topic(project_id: str, name: str, description: str = "") -> dict:
    """Create a topic within a project. Returns the new row as a dict.

    Raises ValueError on duplicate name within the project or nonexistent project.
    """
    with get_connection() as conn:
        proj = conn.execute(
            "SELECT id FROM projects WHERE id = ? AND status = 'active'", (project_id,)
        ).fetchone()
        if not proj:
            raise ValueError(f"Project not found (id={project_id}).")

        dup = conn.execute(
            "SELECT id FROM topics WHERE project_id = ? AND name = ?",
            (project_id, name),
        ).fetchone()
        if dup:
            raise ValueError(f"Topic '{name}' already exists in this project.")

        topic = Topic(project_id=project_id, name=name, description=description)
        row = topic.to_row()
        conn.execute(
            "INSERT INTO topics (id, project_id, name, description, source, "
            "created_at, updated_at) "
            "VALUES (:id, :project_id, :name, :description, :source, "
            ":created_at, :updated_at)",
            row,
        )
        return row


def list_topics(project_id: str) -> list[dict]:
    """Return all topics in a project ordered by name."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM topics WHERE project_id = ? ORDER BY name", (project_id,)
        ).fetchall()
    return [dict(r) for r in rows]


def get_topic(topic_id: str) -> dict | None:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM topics WHERE id = ?", (topic_id,)).fetchone()
    return dict(row) if row else None


def find_topic_by_name(project_id: str, name: str) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM topics WHERE project_id = ? AND name = ?",
            (project_id, name),
        ).fetchone()
    return dict(row) if row else None


def delete_topic(topic_id: str) -> dict:
    """Delete a topic. Conversations get topic_id SET NULL. Returns impact summary."""
    with get_connection() as conn:
        conv_count = conn.execute(
            "SELECT COUNT(*) AS cnt FROM conversations WHERE topic_id = ?", (topic_id,)
        ).fetchone()["cnt"]
        conn.execute("DELETE FROM topics WHERE id = ?", (topic_id,))
    return {"conversations_unassigned": conv_count}


# ---------------------------------------------------------------------------
# Assignment
# ---------------------------------------------------------------------------

def resolve_conversation_by_prefix(prefix: str) -> str:
    """Resolve a conversation ID prefix to a full ID.

    Raises ValueError if zero or multiple matches.
    """
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id FROM conversations WHERE id LIKE ?", (prefix + "%",)
        ).fetchall()
    if not rows:
        raise ValueError(f"No conversation matching prefix '{prefix}'.")
    if len(rows) > 1:
        raise ValueError(
            f"Ambiguous prefix '{prefix}' — matches {len(rows)} conversations."
        )
    return rows[0]["id"]


def assign_conversation_to_topic(conversation_id: str, topic_id: str) -> None:
    """Assign a conversation to a topic. Validates both exist."""
    with get_connection() as conn:
        conv = conn.execute(
            "SELECT id FROM conversations WHERE id = ?", (conversation_id,)
        ).fetchone()
        if not conv:
            raise ValueError(f"Conversation not found (id={conversation_id}).")

        topic = conn.execute(
            "SELECT id FROM topics WHERE id = ?", (topic_id,)
        ).fetchone()
        if not topic:
            raise ValueError(f"Topic not found (id={topic_id}).")

        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "UPDATE conversations SET topic_id = ?, updated_at = ? WHERE id = ?",
            (topic_id, now, conversation_id),
        )


def unassign_conversation(conversation_id: str) -> None:
    """Clear topic_id on a conversation."""
    with get_connection() as conn:
        conv = conn.execute(
            "SELECT id FROM conversations WHERE id = ?", (conversation_id,)
        ).fetchone()
        if not conv:
            raise ValueError(f"Conversation not found (id={conversation_id}).")

        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "UPDATE conversations SET topic_id = NULL, updated_at = ? WHERE id = ?",
            (now, conversation_id),
        )


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

def get_hierarchy_stats() -> list[dict]:
    """Return projects with topic and conversation counts for tree view.

    Each dict: {id, name, parent_id, description, topic_count, conversation_count}
    """
    with get_connection() as conn:
        rows = conn.execute("""\
            SELECT p.id, p.name, p.parent_id, p.description,
                   COUNT(DISTINCT t.id) AS topic_count,
                   COUNT(DISTINCT c.id) AS conversation_count
            FROM projects p
            LEFT JOIN topics t ON t.project_id = p.id
            LEFT JOIN conversations c ON c.topic_id = t.id
            WHERE p.status = 'active'
            GROUP BY p.id
            ORDER BY p.name
        """).fetchall()
    return [dict(r) for r in rows]


def get_topic_stats(project_id: str) -> list[dict]:
    """Return topics in a project with conversation counts.

    Each dict: {id, name, description, conversation_count}
    """
    with get_connection() as conn:
        rows = conn.execute("""\
            SELECT t.id, t.name, t.description,
                   COUNT(c.id) AS conversation_count
            FROM topics t
            LEFT JOIN conversations c ON c.topic_id = t.id
            WHERE t.project_id = ?
            GROUP BY t.id
            ORDER BY t.name
        """, (project_id,)).fetchall()
    return [dict(r) for r in rows]
