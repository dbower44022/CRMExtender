"""Notes CRUD — entity-agnostic notes with revisions, FTS, and mentions."""

from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import Any

from .database import get_connection

log = logging.getLogger(__name__)

VALID_ENTITY_TYPES = ("contact", "company", "conversation", "event", "project")
VALID_MENTION_TYPES = ("user", "contact", "company", "conversation", "event", "project")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _uuid() -> str:
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Plain-text extraction (for FTS indexing)
# ---------------------------------------------------------------------------

class _HTMLStripper(HTMLParser):
    """Simple HTML tag stripper for FTS indexing."""

    def __init__(self):
        super().__init__()
        self._parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self._parts.append(data)

    def get_text(self) -> str:
        return " ".join(self._parts)


def _extract_plain_text(content_html: str | None) -> str:
    """Extract plain text from HTML content for FTS indexing."""
    if not content_html:
        return ""
    stripper = _HTMLStripper()
    try:
        stripper.feed(content_html)
        return stripper.get_text().strip()
    except Exception:
        # Fallback: crude tag removal
        return re.sub(r"<[^>]+>", " ", content_html).strip()


# ---------------------------------------------------------------------------
# FTS management
# ---------------------------------------------------------------------------

def _update_fts(conn, note_id: str, title: str | None, content_html: str | None) -> None:
    """Upsert the FTS5 index entry for a note."""
    plain = _extract_plain_text(content_html)
    # Delete existing entry (FTS5 external content — manual sync)
    conn.execute("DELETE FROM notes_fts WHERE note_id = ?", (note_id,))
    conn.execute(
        "INSERT INTO notes_fts (note_id, title, content_text) VALUES (?, ?, ?)",
        (note_id, title or "", plain),
    )


def _delete_fts(conn, note_id: str) -> None:
    """Remove the FTS5 index entry for a note."""
    conn.execute("DELETE FROM notes_fts WHERE note_id = ?", (note_id,))


# ---------------------------------------------------------------------------
# Mention sync
# ---------------------------------------------------------------------------

def _sync_mentions(conn, note_id: str, content_json: str | None) -> None:
    """Parse content_json for mention nodes and sync note_mentions table."""
    conn.execute("DELETE FROM note_mentions WHERE note_id = ?", (note_id,))

    if not content_json:
        return

    try:
        doc = json.loads(content_json)
    except (json.JSONDecodeError, TypeError):
        return

    now = _now()
    mentions = _extract_mentions_from_doc(doc)
    for mention_type, mentioned_id in mentions:
        if mention_type in VALID_MENTION_TYPES:
            conn.execute(
                "INSERT INTO note_mentions (id, note_id, mention_type, mentioned_id, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (_uuid(), note_id, mention_type, mentioned_id, now),
            )


def _extract_mentions_from_doc(node: dict | list) -> list[tuple[str, str]]:
    """Recursively extract (mention_type, mentioned_id) from Tiptap JSON."""
    results: list[tuple[str, str]] = []
    if isinstance(node, list):
        for item in node:
            results.extend(_extract_mentions_from_doc(item))
    elif isinstance(node, dict):
        if node.get("type") == "mention":
            attrs = node.get("attrs", {})
            m_type = attrs.get("mentionType", "")
            m_id = attrs.get("id", "")
            if m_type and m_id:
                results.append((m_type, m_id))
        for child in node.get("content", []):
            results.extend(_extract_mentions_from_doc(child))
    return results


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

def create_note(
    customer_id: str,
    entity_type: str,
    entity_id: str,
    *,
    title: str | None = None,
    content_json: str | None = None,
    content_html: str | None = None,
    created_by: str | None = None,
) -> dict[str, Any]:
    """Create a new note with its first revision. Returns the note dict."""
    if entity_type not in VALID_ENTITY_TYPES:
        raise ValueError(f"Invalid entity_type: {entity_type}")

    now = _now()
    note_id = _uuid()
    rev_id = _uuid()

    with get_connection() as conn:
        conn.execute(
            "INSERT INTO notes "
            "(id, customer_id, title, current_revision_id, "
            " created_by, updated_by, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (note_id, customer_id, title, rev_id, created_by, created_by, now, now),
        )
        conn.execute(
            "INSERT INTO note_entities "
            "(note_id, entity_type, entity_id, is_pinned, created_at) "
            "VALUES (?, ?, ?, 0, ?)",
            (note_id, entity_type, entity_id, now),
        )
        conn.execute(
            "INSERT INTO note_revisions "
            "(id, note_id, revision_number, content_json, content_html, revised_by, created_at) "
            "VALUES (?, ?, 1, ?, ?, ?, ?)",
            (rev_id, note_id, content_json, content_html, created_by, now),
        )
        _update_fts(conn, note_id, title, content_html)
        _sync_mentions(conn, note_id, content_json)

    return {
        "id": note_id,
        "customer_id": customer_id,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "title": title,
        "is_pinned": 0,
        "current_revision_id": rev_id,
        "created_by": created_by,
        "updated_by": created_by,
        "created_at": now,
        "updated_at": now,
        "content_json": content_json,
        "content_html": content_html,
        "revision_number": 1,
    }


def update_note(
    note_id: str,
    *,
    title: str | None = None,
    content_json: str | None = None,
    content_html: str | None = None,
    updated_by: str | None = None,
) -> dict[str, Any] | None:
    """Update a note by creating a new revision. Returns updated note or None."""
    now = _now()
    rev_id = _uuid()

    with get_connection() as conn:
        note = conn.execute(
            "SELECT * FROM notes WHERE id = ?", (note_id,)
        ).fetchone()
        if not note:
            return None

        # Get current max revision number
        max_rev = conn.execute(
            "SELECT MAX(revision_number) AS m FROM note_revisions WHERE note_id = ?",
            (note_id,),
        ).fetchone()["m"] or 0

        new_rev_num = max_rev + 1

        conn.execute(
            "INSERT INTO note_revisions "
            "(id, note_id, revision_number, content_json, content_html, revised_by, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (rev_id, note_id, new_rev_num, content_json, content_html, updated_by, now),
        )

        # Update the note record
        update_title = title if title is not None else note["title"]
        conn.execute(
            "UPDATE notes SET title = ?, current_revision_id = ?, "
            "updated_by = ?, updated_at = ? WHERE id = ?",
            (update_title, rev_id, updated_by, now, note_id),
        )
        _update_fts(conn, note_id, update_title, content_html)
        _sync_mentions(conn, note_id, content_json)

    return {
        "id": note_id,
        "title": update_title,
        "current_revision_id": rev_id,
        "revision_number": new_rev_num,
        "updated_by": updated_by,
        "updated_at": now,
    }


def get_note(note_id: str) -> dict[str, Any] | None:
    """Get a single note with its current revision content and linked entities."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT n.*, nr.content_json, nr.content_html, nr.revision_number "
            "FROM notes n "
            "LEFT JOIN note_revisions nr ON nr.id = n.current_revision_id "
            "WHERE n.id = ?",
            (note_id,),
        ).fetchone()
        if not row:
            return None
        result = dict(row)
        entities = conn.execute(
            "SELECT entity_type, entity_id, is_pinned, created_at "
            "FROM note_entities WHERE note_id = ? "
            "ORDER BY created_at ASC",
            (note_id,),
        ).fetchall()
        result["entities"] = [dict(e) for e in entities]
        # Backward compat: expose first entity's fields at top level
        if entities:
            result["entity_type"] = entities[0]["entity_type"]
            result["entity_id"] = entities[0]["entity_id"]
            result["is_pinned"] = entities[0]["is_pinned"]
        else:
            result["entity_type"] = None
            result["entity_id"] = None
            result["is_pinned"] = 0
    return result


def get_notes_for_entity(
    entity_type: str, entity_id: str, *, customer_id: str | None = None,
) -> list[dict[str, Any]]:
    """List notes for a given entity, pinned first then by updated_at DESC."""
    with get_connection() as conn:
        params: list = [entity_type, entity_id]
        cust_clause = ""
        if customer_id:
            cust_clause = "AND n.customer_id = ?"
            params.append(customer_id)

        rows = conn.execute(
            f"SELECT n.*, ne.entity_type, ne.entity_id, ne.is_pinned, "
            f"       nr.content_json, nr.content_html, nr.revision_number, "
            f"       u.name AS author_name "
            f"FROM note_entities ne "
            f"JOIN notes n ON n.id = ne.note_id "
            f"LEFT JOIN note_revisions nr ON nr.id = n.current_revision_id "
            f"LEFT JOIN users u ON u.id = n.created_by "
            f"WHERE ne.entity_type = ? AND ne.entity_id = ? {cust_clause} "
            f"ORDER BY ne.is_pinned DESC, n.updated_at DESC",
            params,
        ).fetchall()
    return [dict(r) for r in rows]


def get_recent_notes(
    *, customer_id: str | None = None, limit: int = 50,
) -> list[dict[str, Any]]:
    """List the most recently updated notes across all entities."""
    with get_connection() as conn:
        params: list = []
        cust_clause = ""
        if customer_id:
            cust_clause = "WHERE n.customer_id = ?"
            params.append(customer_id)
        params.append(limit)

        rows = conn.execute(
            f"SELECT n.*, "
            f"       (SELECT ne.entity_type FROM note_entities ne WHERE ne.note_id = n.id LIMIT 1) AS entity_type, "
            f"       (SELECT ne.entity_id FROM note_entities ne WHERE ne.note_id = n.id LIMIT 1) AS entity_id, "
            f"       (SELECT ne.is_pinned FROM note_entities ne WHERE ne.note_id = n.id LIMIT 1) AS is_pinned, "
            f"       nr.content_html, nr.revision_number, "
            f"       u.name AS author_name "
            f"FROM notes n "
            f"LEFT JOIN note_revisions nr ON nr.id = n.current_revision_id "
            f"LEFT JOIN users u ON u.id = n.created_by "
            f"{cust_clause} "
            f"ORDER BY n.updated_at DESC "
            f"LIMIT ?",
            params,
        ).fetchall()
    return [dict(r) for r in rows]


def delete_note(note_id: str) -> bool:
    """Delete a note and its revisions/mentions (CASCADE). Returns True if deleted."""
    with get_connection() as conn:
        _delete_fts(conn, note_id)
        count = conn.execute("DELETE FROM notes WHERE id = ?", (note_id,)).rowcount
    return count > 0


def toggle_pin(
    note_id: str,
    entity_type: str | None = None,
    entity_id: str | None = None,
) -> dict[str, Any] | None:
    """Toggle the pinned state of a note for a specific entity link.

    If entity_type/entity_id are not provided, falls back to the first
    linked entity (backward compatibility).
    """
    now = _now()
    with get_connection() as conn:
        note = conn.execute(
            "SELECT * FROM notes WHERE id = ?", (note_id,)
        ).fetchone()
        if not note:
            return None

        # Resolve entity context
        if not entity_type or not entity_id:
            first = conn.execute(
                "SELECT entity_type, entity_id FROM note_entities "
                "WHERE note_id = ? ORDER BY created_at ASC LIMIT 1",
                (note_id,),
            ).fetchone()
            if not first:
                return None
            entity_type = first["entity_type"]
            entity_id = first["entity_id"]

        row = conn.execute(
            "SELECT is_pinned FROM note_entities "
            "WHERE note_id = ? AND entity_type = ? AND entity_id = ?",
            (note_id, entity_type, entity_id),
        ).fetchone()
        if not row:
            return None
        new_pin = 0 if row["is_pinned"] else 1
        conn.execute(
            "UPDATE note_entities SET is_pinned = ? "
            "WHERE note_id = ? AND entity_type = ? AND entity_id = ?",
            (new_pin, note_id, entity_type, entity_id),
        )
        conn.execute(
            "UPDATE notes SET updated_at = ? WHERE id = ?",
            (now, note_id),
        )
    return get_note(note_id)


def add_note_entity(note_id: str, entity_type: str, entity_id: str) -> bool:
    """Link a note to an additional entity. Returns True if a new link was created."""
    if entity_type not in VALID_ENTITY_TYPES:
        raise ValueError(f"Invalid entity_type: {entity_type}")
    now = _now()
    with get_connection() as conn:
        note = conn.execute("SELECT id FROM notes WHERE id = ?", (note_id,)).fetchone()
        if not note:
            raise ValueError(f"Note not found: {note_id}")
        try:
            conn.execute(
                "INSERT INTO note_entities (note_id, entity_type, entity_id, is_pinned, created_at) "
                "VALUES (?, ?, ?, 0, ?)",
                (note_id, entity_type, entity_id, now),
            )
            return True
        except Exception:
            # Duplicate — already linked (INSERT OR IGNORE semantics)
            return False


def remove_note_entity(note_id: str, entity_type: str, entity_id: str) -> bool:
    """Unlink a note from an entity. Raises ValueError if it's the last link."""
    with get_connection() as conn:
        count = conn.execute(
            "SELECT COUNT(*) AS c FROM note_entities WHERE note_id = ?",
            (note_id,),
        ).fetchone()["c"]
        if count <= 1:
            raise ValueError("Cannot remove the last entity link from a note")
        deleted = conn.execute(
            "DELETE FROM note_entities WHERE note_id = ? AND entity_type = ? AND entity_id = ?",
            (note_id, entity_type, entity_id),
        ).rowcount
        return deleted > 0


def get_note_entities(note_id: str) -> list[dict[str, Any]]:
    """List all entities linked to a note."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT entity_type, entity_id, is_pinned, created_at "
            "FROM note_entities WHERE note_id = ? ORDER BY created_at ASC",
            (note_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_revisions(note_id: str) -> list[dict[str, Any]]:
    """List all revisions for a note, newest first."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT nr.*, u.name AS revised_by_name "
            "FROM note_revisions nr "
            "LEFT JOIN users u ON u.id = nr.revised_by "
            "WHERE nr.note_id = ? "
            "ORDER BY nr.revision_number DESC",
            (note_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_revision(revision_id: str) -> dict[str, Any] | None:
    """Get a single revision by ID."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM note_revisions WHERE id = ?", (revision_id,)
        ).fetchone()
    return dict(row) if row else None


def search_notes(
    query: str, *, customer_id: str | None = None, limit: int = 50,
) -> list[dict[str, Any]]:
    """Full-text search across notes. Returns notes with snippets."""
    if not query.strip():
        return []

    with get_connection() as conn:
        # FTS5 search
        fts_query = query.strip()
        params: list = [fts_query]
        cust_clause = ""
        if customer_id:
            cust_clause = "AND n.customer_id = ?"
            params.append(customer_id)
        params.append(limit)

        rows = conn.execute(
            f"SELECT n.*, "
            f"       (SELECT ne.entity_type FROM note_entities ne WHERE ne.note_id = n.id LIMIT 1) AS entity_type, "
            f"       (SELECT ne.entity_id FROM note_entities ne WHERE ne.note_id = n.id LIMIT 1) AS entity_id, "
            f"       (SELECT ne.is_pinned FROM note_entities ne WHERE ne.note_id = n.id LIMIT 1) AS is_pinned, "
            f"       nr.content_html, nr.revision_number, "
            f"       u.name AS author_name, "
            f"       snippet(notes_fts, 2, '<mark>', '</mark>', '...', 40) AS snippet "
            f"FROM notes_fts fts "
            f"JOIN notes n ON n.id = fts.note_id "
            f"LEFT JOIN note_revisions nr ON nr.id = n.current_revision_id "
            f"LEFT JOIN users u ON u.id = n.created_by "
            f"WHERE notes_fts MATCH ? {cust_clause} "
            f"ORDER BY rank "
            f"LIMIT ?",
            params,
        ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Attachment helpers
# ---------------------------------------------------------------------------

def create_attachment(
    *,
    note_id: str | None = None,
    filename: str,
    original_name: str,
    mime_type: str,
    size_bytes: int,
    storage_path: str,
    uploaded_by: str | None = None,
) -> dict[str, Any]:
    """Record an uploaded file attachment."""
    now = _now()
    att_id = _uuid()
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO note_attachments "
            "(id, note_id, filename, original_name, mime_type, size_bytes, "
            " storage_path, uploaded_by, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (att_id, note_id, filename, original_name, mime_type, size_bytes,
             storage_path, uploaded_by, now),
        )
    return {
        "id": att_id, "note_id": note_id, "filename": filename,
        "original_name": original_name, "mime_type": mime_type,
        "size_bytes": size_bytes, "storage_path": storage_path,
        "uploaded_by": uploaded_by, "created_at": now,
    }


def get_attachment(attachment_id: str) -> dict[str, Any] | None:
    """Get an attachment record by ID."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM note_attachments WHERE id = ?", (attachment_id,)
        ).fetchone()
    return dict(row) if row else None


def link_attachment_to_note(attachment_id: str, note_id: str) -> None:
    """Link an orphan attachment to a note."""
    with get_connection() as conn:
        conn.execute(
            "UPDATE note_attachments SET note_id = ? WHERE id = ?",
            (note_id, attachment_id),
        )


def cleanup_orphan_attachments(max_age_hours: int = 24) -> int:
    """Delete attachment records with no note_id older than max_age_hours."""
    import os
    cutoff = datetime.now(timezone.utc)
    count = 0
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM note_attachments WHERE note_id IS NULL"
        ).fetchall()
        for row in rows:
            created = datetime.fromisoformat(row["created_at"])
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            age_hours = (cutoff - created).total_seconds() / 3600
            if age_hours > max_age_hours:
                # Delete file
                try:
                    os.remove(row["storage_path"])
                except OSError:
                    pass
                conn.execute(
                    "DELETE FROM note_attachments WHERE id = ?", (row["id"],)
                )
                count += 1
    return count


# ---------------------------------------------------------------------------
# Mention autocomplete
# ---------------------------------------------------------------------------

def search_mentionables(
    query: str, mention_type: str = "user", *, customer_id: str | None = None,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Search for entities to mention."""
    results: list[dict[str, Any]] = []
    if not query.strip():
        return results

    pattern = f"%{query.strip()}%"
    with get_connection() as conn:
        if mention_type == "user":
            cust_clause = "AND customer_id = ?" if customer_id else ""
            params: list = [pattern]
            if customer_id:
                params.append(customer_id)
            params.append(limit)
            rows = conn.execute(
                f"SELECT id, name, email FROM users "
                f"WHERE (name LIKE ? OR email LIKE ?) AND is_active = 1 "
                f"{cust_clause} LIMIT ?",
                [pattern] + params,
            ).fetchall()
            results = [{"id": r["id"], "name": r["name"] or r["email"],
                        "detail": r["email"]} for r in rows]
        elif mention_type == "contact":
            cust_clause = "AND customer_id = ?" if customer_id else ""
            params = [pattern]
            if customer_id:
                params.append(customer_id)
            params.append(limit)
            rows = conn.execute(
                f"SELECT id, name FROM contacts WHERE name LIKE ? {cust_clause} LIMIT ?",
                params,
            ).fetchall()
            results = [{"id": r["id"], "name": r["name"] or r["id"][:8]} for r in rows]
        elif mention_type == "company":
            cust_clause = "AND customer_id = ?" if customer_id else ""
            params = [pattern]
            if customer_id:
                params.append(customer_id)
            params.append(limit)
            rows = conn.execute(
                f"SELECT id, name FROM companies WHERE name LIKE ? {cust_clause} LIMIT ?",
                params,
            ).fetchall()
            results = [{"id": r["id"], "name": r["name"]} for r in rows]

    return results
