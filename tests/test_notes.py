"""Tests for the Notes system — Phase 17 + Phase 18 (multi-entity notes).

Covers: CRUD, revisions, pins, FTS search, mentions, file upload,
sanitization, web routes, entity integration, multi-entity junction,
and edge cases.
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from poc.database import get_connection, init_db
from poc.notes import (
    _extract_mentions_from_doc,
    _extract_plain_text,
    add_note_entity,
    create_attachment,
    create_note,
    delete_note,
    get_note,
    get_note_entities,
    get_notes_for_entity,
    get_revision,
    get_revisions,
    remove_note_entity,
    search_mentionables,
    search_notes,
    toggle_pin,
    update_note,
)


_NOW = datetime.now(timezone.utc).isoformat()

CUST_ID = "cust-test"
USER_ID = "user-admin"
USER_EMAIL = "admin@test.com"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def tmp_db(tmp_path, monkeypatch):
    db_file = tmp_path / "test.db"
    monkeypatch.setattr("poc.config.DB_PATH", db_file)
    monkeypatch.setattr("poc.config.CRM_AUTH_ENABLED", False)
    monkeypatch.setattr("poc.config.UPLOAD_DIR", tmp_path / "uploads")
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
            "VALUES (?, ?, ?, 'Admin User', 'admin', 1, ?, ?)",
            (USER_ID, CUST_ID, USER_EMAIL, _NOW, _NOW),
        )
        # Create a test contact, company, conversation
        conn.execute(
            "INSERT INTO contacts (id, customer_id, name, source, created_at, updated_at) "
            "VALUES ('ct-1', ?, 'Alice', 'test', ?, ?)",
            (CUST_ID, _NOW, _NOW),
        )
        conn.execute(
            "INSERT INTO companies (id, customer_id, name, created_at, updated_at) "
            "VALUES ('co-1', ?, 'Acme Inc', ?, ?)",
            (CUST_ID, _NOW, _NOW),
        )
        conn.execute(
            "INSERT INTO conversations (id, customer_id, title, created_at, updated_at) "
            "VALUES ('conv-1', ?, 'Test Thread', ?, ?)",
            (CUST_ID, _NOW, _NOW),
        )
        conn.execute(
            "INSERT INTO projects (id, customer_id, name, created_at, updated_at) "
            "VALUES ('proj-1', ?, 'Test Project', ?, ?)",
            (CUST_ID, _NOW, _NOW),
        )
        # Event needs a valid event_type
        conn.execute(
            "INSERT INTO events (id, title, event_type, created_at, updated_at) "
            "VALUES ('ev-1', 'Test Event', 'meeting', ?, ?)",
            (_NOW, _NOW),
        )

    return db_file


@pytest.fixture()
def client(tmp_db, monkeypatch):
    monkeypatch.setattr(
        "poc.hierarchy.get_current_user",
        lambda: {"id": USER_ID, "email": USER_EMAIL, "name": "Admin User",
                 "role": "admin", "customer_id": CUST_ID},
    )
    from poc.web.app import create_app
    app = create_app()
    return TestClient(app, raise_server_exceptions=False)


# ===================================================================
# CRUD — Unit layer
# ===================================================================

class TestCreateNote:
    def test_basic_create(self, tmp_db):
        note = create_note(CUST_ID, "contact", "ct-1",
                           title="First note", content_html="<p>Hello</p>",
                           created_by=USER_ID)
        assert note["id"]
        assert note["title"] == "First note"
        assert note["entity_type"] == "contact"
        assert note["entity_id"] == "ct-1"
        assert note["revision_number"] == 1
        assert note["is_pinned"] == 0

    def test_create_without_title(self, tmp_db):
        note = create_note(CUST_ID, "contact", "ct-1",
                           content_html="<p>No title</p>", created_by=USER_ID)
        assert note["title"] is None

    def test_create_with_json_content(self, tmp_db):
        doc = {"type": "doc", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Hello"}]}]}
        note = create_note(CUST_ID, "contact", "ct-1",
                           content_json=json.dumps(doc), content_html="<p>Hello</p>",
                           created_by=USER_ID)
        assert note["content_json"]

    def test_invalid_entity_type(self, tmp_db):
        with pytest.raises(ValueError, match="Invalid entity_type"):
            create_note(CUST_ID, "bogus", "x")

    def test_create_for_each_entity_type(self, tmp_db):
        for et in ("contact", "company", "conversation", "event", "project"):
            note = create_note(CUST_ID, et, "test-id",
                               content_html="<p>test</p>", created_by=USER_ID)
            assert note["entity_type"] == et


class TestGetNote:
    def test_get_existing(self, tmp_db):
        created = create_note(CUST_ID, "contact", "ct-1",
                              title="Fetch me", content_html="<p>body</p>",
                              created_by=USER_ID)
        note = get_note(created["id"])
        assert note is not None
        assert note["title"] == "Fetch me"
        assert note["content_html"] == "<p>body</p>"
        # Backward compat fields
        assert note["entity_type"] == "contact"
        assert note["entity_id"] == "ct-1"
        # New entities list
        assert len(note["entities"]) == 1
        assert note["entities"][0]["entity_type"] == "contact"

    def test_get_nonexistent(self, tmp_db):
        assert get_note("no-such-id") is None


class TestGetNotesForEntity:
    def test_list_returns_notes(self, tmp_db):
        create_note(CUST_ID, "contact", "ct-1", title="A", content_html="a", created_by=USER_ID)
        create_note(CUST_ID, "contact", "ct-1", title="B", content_html="b", created_by=USER_ID)
        notes = get_notes_for_entity("contact", "ct-1", customer_id=CUST_ID)
        assert len(notes) == 2

    def test_list_filtered_by_entity(self, tmp_db):
        create_note(CUST_ID, "contact", "ct-1", content_html="for contact", created_by=USER_ID)
        create_note(CUST_ID, "company", "co-1", content_html="for company", created_by=USER_ID)
        assert len(get_notes_for_entity("contact", "ct-1", customer_id=CUST_ID)) == 1
        assert len(get_notes_for_entity("company", "co-1", customer_id=CUST_ID)) == 1

    def test_pinned_first(self, tmp_db):
        n1 = create_note(CUST_ID, "contact", "ct-1", title="Unpinned", content_html="a", created_by=USER_ID)
        n2 = create_note(CUST_ID, "contact", "ct-1", title="Pinned", content_html="b", created_by=USER_ID)
        toggle_pin(n2["id"], "contact", "ct-1")
        notes = get_notes_for_entity("contact", "ct-1", customer_id=CUST_ID)
        assert notes[0]["title"] == "Pinned"
        assert notes[0]["is_pinned"] == 1

    def test_includes_author_name(self, tmp_db):
        create_note(CUST_ID, "contact", "ct-1", content_html="a", created_by=USER_ID)
        notes = get_notes_for_entity("contact", "ct-1", customer_id=CUST_ID)
        assert notes[0]["author_name"] == "Admin User"


class TestUpdateNote:
    def test_basic_update(self, tmp_db):
        note = create_note(CUST_ID, "contact", "ct-1", title="V1",
                           content_html="<p>V1</p>", created_by=USER_ID)
        result = update_note(note["id"], title="V2",
                             content_html="<p>V2</p>", updated_by=USER_ID)
        assert result is not None
        assert result["title"] == "V2"
        assert result["revision_number"] == 2

    def test_update_creates_revision(self, tmp_db):
        note = create_note(CUST_ID, "contact", "ct-1",
                           content_html="<p>r1</p>", created_by=USER_ID)
        update_note(note["id"], content_html="<p>r2</p>", updated_by=USER_ID)
        update_note(note["id"], content_html="<p>r3</p>", updated_by=USER_ID)
        revs = get_revisions(note["id"])
        assert len(revs) == 3
        assert revs[0]["revision_number"] == 3

    def test_update_nonexistent(self, tmp_db):
        assert update_note("no-such-id", title="X") is None

    def test_update_preserves_title_when_none(self, tmp_db):
        note = create_note(CUST_ID, "contact", "ct-1", title="Keep Me",
                           content_html="<p>X</p>", created_by=USER_ID)
        result = update_note(note["id"], content_html="<p>Y</p>", updated_by=USER_ID)
        assert result["title"] == "Keep Me"


class TestDeleteNote:
    def test_delete_existing(self, tmp_db):
        note = create_note(CUST_ID, "contact", "ct-1",
                           content_html="<p>bye</p>", created_by=USER_ID)
        assert delete_note(note["id"]) is True
        assert get_note(note["id"]) is None

    def test_delete_nonexistent(self, tmp_db):
        assert delete_note("no-such-id") is False

    def test_delete_cascades_revisions(self, tmp_db):
        note = create_note(CUST_ID, "contact", "ct-1",
                           content_html="<p>r1</p>", created_by=USER_ID)
        update_note(note["id"], content_html="<p>r2</p>", updated_by=USER_ID)
        delete_note(note["id"])
        assert get_revisions(note["id"]) == []


class TestTogglePin:
    def test_pin_unpin(self, tmp_db):
        note = create_note(CUST_ID, "contact", "ct-1",
                           content_html="<p>pin me</p>", created_by=USER_ID)
        # With explicit entity params
        result = toggle_pin(note["id"], "contact", "ct-1")
        assert result["is_pinned"] == 1
        result = toggle_pin(note["id"], "contact", "ct-1")
        assert result["is_pinned"] == 0

    def test_pin_fallback_to_first_entity(self, tmp_db):
        note = create_note(CUST_ID, "contact", "ct-1",
                           content_html="<p>pin me</p>", created_by=USER_ID)
        # Without entity params — falls back to first entity
        result = toggle_pin(note["id"])
        assert result["is_pinned"] == 1

    def test_pin_nonexistent(self, tmp_db):
        assert toggle_pin("no-such-id") is None


# ===================================================================
# Revisions
# ===================================================================

class TestRevisions:
    def test_get_revisions(self, tmp_db):
        note = create_note(CUST_ID, "contact", "ct-1",
                           content_html="<p>r1</p>", created_by=USER_ID)
        update_note(note["id"], content_html="<p>r2</p>", updated_by=USER_ID)
        revs = get_revisions(note["id"])
        assert len(revs) == 2
        assert revs[0]["revision_number"] == 2
        assert revs[1]["revision_number"] == 1

    def test_get_single_revision(self, tmp_db):
        note = create_note(CUST_ID, "contact", "ct-1",
                           content_html="<p>r1</p>", created_by=USER_ID)
        rev = get_revision(note["current_revision_id"])
        assert rev is not None
        assert rev["content_html"] == "<p>r1</p>"

    def test_revision_nonexistent(self, tmp_db):
        assert get_revision("no-such-id") is None


# ===================================================================
# FTS Search
# ===================================================================

class TestSearch:
    def test_basic_search(self, tmp_db):
        create_note(CUST_ID, "contact", "ct-1", title="Meeting notes",
                    content_html="<p>Discussed quarterly budget</p>", created_by=USER_ID)
        create_note(CUST_ID, "contact", "ct-1", title="Lunch",
                    content_html="<p>Had lunch at noon</p>", created_by=USER_ID)

        results = search_notes("budget", customer_id=CUST_ID)
        assert len(results) == 1
        assert results[0]["title"] == "Meeting notes"

    def test_search_by_title(self, tmp_db):
        create_note(CUST_ID, "contact", "ct-1", title="Important meeting",
                    content_html="<p>Nothing special</p>", created_by=USER_ID)
        results = search_notes("important", customer_id=CUST_ID)
        assert len(results) == 1

    def test_search_empty_query(self, tmp_db):
        assert search_notes("") == []
        assert search_notes("   ") == []

    def test_search_no_results(self, tmp_db):
        create_note(CUST_ID, "contact", "ct-1",
                    content_html="<p>hello</p>", created_by=USER_ID)
        assert search_notes("xyznonexistent", customer_id=CUST_ID) == []

    def test_search_updated_after_edit(self, tmp_db):
        note = create_note(CUST_ID, "contact", "ct-1",
                           content_html="<p>alpha</p>", created_by=USER_ID)
        assert len(search_notes("alpha", customer_id=CUST_ID)) == 1
        update_note(note["id"], content_html="<p>beta</p>", updated_by=USER_ID)
        assert len(search_notes("alpha", customer_id=CUST_ID)) == 0
        assert len(search_notes("beta", customer_id=CUST_ID)) == 1

    def test_search_deleted_note(self, tmp_db):
        note = create_note(CUST_ID, "contact", "ct-1",
                           content_html="<p>remove me</p>", created_by=USER_ID)
        assert len(search_notes("remove", customer_id=CUST_ID)) == 1
        delete_note(note["id"])
        assert len(search_notes("remove", customer_id=CUST_ID)) == 0


# ===================================================================
# Plain text extraction
# ===================================================================

class TestExtractPlainText:
    def test_simple_html(self):
        assert "Hello world" in _extract_plain_text("<p>Hello world</p>")

    def test_nested_tags(self):
        text = _extract_plain_text("<div><p>A <strong>bold</strong> word</p></div>")
        assert "bold" in text
        assert "<" not in text

    def test_empty_input(self):
        assert _extract_plain_text("") == ""
        assert _extract_plain_text(None) == ""


# ===================================================================
# Mentions
# ===================================================================

class TestMentions:
    def test_extract_mentions_from_doc(self):
        doc = {
            "type": "doc",
            "content": [{
                "type": "paragraph",
                "content": [
                    {"type": "text", "text": "Hello "},
                    {"type": "mention", "attrs": {"id": "u-1", "mentionType": "user", "label": "Alice"}},
                    {"type": "text", "text": " and "},
                    {"type": "mention", "attrs": {"id": "ct-1", "mentionType": "contact", "label": "Bob"}},
                ],
            }],
        }
        mentions = _extract_mentions_from_doc(doc)
        assert len(mentions) == 2
        assert ("user", "u-1") in mentions
        assert ("contact", "ct-1") in mentions

    def test_no_mentions(self):
        doc = {"type": "doc", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "no mentions"}]}]}
        assert _extract_mentions_from_doc(doc) == []

    def test_mentions_synced_on_create(self, tmp_db):
        doc = {
            "type": "doc",
            "content": [{
                "type": "paragraph",
                "content": [
                    {"type": "mention", "attrs": {"id": USER_ID, "mentionType": "user", "label": "Admin"}},
                ],
            }],
        }
        note = create_note(CUST_ID, "contact", "ct-1",
                           content_json=json.dumps(doc), content_html="<p>@Admin</p>",
                           created_by=USER_ID)
        with get_connection() as conn:
            mentions = conn.execute(
                "SELECT * FROM note_mentions WHERE note_id = ?", (note["id"],)
            ).fetchall()
        assert len(mentions) == 1
        assert mentions[0]["mention_type"] == "user"
        assert mentions[0]["mentioned_id"] == USER_ID

    def test_mentions_synced_on_update(self, tmp_db):
        note = create_note(CUST_ID, "contact", "ct-1",
                           content_html="<p>no mentions</p>", created_by=USER_ID)
        doc = {
            "type": "doc",
            "content": [{
                "type": "paragraph",
                "content": [
                    {"type": "mention", "attrs": {"id": "ct-1", "mentionType": "contact", "label": "Alice"}},
                ],
            }],
        }
        update_note(note["id"], content_json=json.dumps(doc),
                    content_html="<p>@Alice</p>", updated_by=USER_ID)
        with get_connection() as conn:
            mentions = conn.execute(
                "SELECT * FROM note_mentions WHERE note_id = ?", (note["id"],)
            ).fetchall()
        assert len(mentions) == 1
        assert mentions[0]["mention_type"] == "contact"


class TestSearchMentionables:
    def test_search_users(self, tmp_db):
        results = search_mentionables("Admin", "user", customer_id=CUST_ID)
        assert len(results) >= 1
        assert results[0]["name"] == "Admin User"

    def test_search_contacts(self, tmp_db):
        results = search_mentionables("Ali", "contact", customer_id=CUST_ID)
        assert len(results) >= 1

    def test_search_companies(self, tmp_db):
        results = search_mentionables("Acme", "company", customer_id=CUST_ID)
        assert len(results) >= 1

    def test_empty_query(self, tmp_db):
        assert search_mentionables("", "user") == []


# ===================================================================
# Attachments
# ===================================================================

class TestAttachments:
    def test_create_attachment(self, tmp_db):
        att = create_attachment(
            filename="abc.jpg", original_name="photo.jpg",
            mime_type="image/jpeg", size_bytes=1024,
            storage_path="/tmp/test.jpg", uploaded_by=USER_ID,
        )
        assert att["id"]
        assert att["note_id"] is None  # orphan

    def test_create_attachment_with_note(self, tmp_db):
        note = create_note(CUST_ID, "contact", "ct-1",
                           content_html="<p>x</p>", created_by=USER_ID)
        att = create_attachment(
            note_id=note["id"],
            filename="abc.jpg", original_name="photo.jpg",
            mime_type="image/jpeg", size_bytes=1024,
            storage_path="/tmp/test.jpg", uploaded_by=USER_ID,
        )
        assert att["note_id"] == note["id"]


# ===================================================================
# Web routes
# ===================================================================

class TestNotesWebList:
    def test_list_notes_for_entity(self, client, tmp_db):
        create_note(CUST_ID, "contact", "ct-1", title="Web Note",
                    content_html="<p>body</p>", created_by=USER_ID)
        resp = client.get("/notes?entity_type=contact&entity_id=ct-1")
        assert resp.status_code == 200
        assert "Web Note" in resp.text

    def test_list_empty(self, client, tmp_db):
        resp = client.get("/notes?entity_type=contact&entity_id=ct-1")
        assert resp.status_code == 200
        assert "No notes yet" in resp.text


class TestNotesWebCreate:
    def test_create_note_via_post(self, client, tmp_db):
        resp = client.post("/notes", data={
            "entity_type": "contact",
            "entity_id": "ct-1",
            "title": "New Note",
            "content_html": "<p>Created via web</p>",
        })
        assert resp.status_code == 200
        assert "New Note" in resp.text

    def test_create_note_missing_entity(self, client, tmp_db):
        resp = client.post("/notes", data={"title": "Bad"})
        assert resp.status_code == 400


class TestNotesWebEdit:
    def test_get_edit_form(self, client, tmp_db):
        note = create_note(CUST_ID, "contact", "ct-1", title="Edit Me",
                           content_html="<p>original</p>", created_by=USER_ID)
        resp = client.get(f"/notes/{note['id']}/edit")
        assert resp.status_code == 200
        assert "Edit Me" in resp.text

    def test_edit_nonexistent(self, client, tmp_db):
        resp = client.get("/notes/no-such-id/edit")
        assert resp.status_code == 404


class TestNotesWebUpdate:
    def test_update_note(self, client, tmp_db):
        note = create_note(CUST_ID, "contact", "ct-1", title="V1",
                           content_html="<p>V1</p>", created_by=USER_ID)
        resp = client.put(f"/notes/{note['id']}", data={
            "title": "V2",
            "content_html": "<p>V2</p>",
        })
        assert resp.status_code == 200
        assert "V2" in resp.text

    def test_update_nonexistent(self, client, tmp_db):
        resp = client.put("/notes/no-such-id", data={"title": "X"})
        assert resp.status_code == 404


class TestNotesWebDelete:
    def test_delete_note(self, client, tmp_db):
        note = create_note(CUST_ID, "contact", "ct-1",
                           content_html="<p>bye</p>", created_by=USER_ID)
        resp = client.delete(f"/notes/{note['id']}")
        assert resp.status_code == 200
        assert get_note(note["id"]) is None

    def test_delete_nonexistent(self, client, tmp_db):
        resp = client.delete("/notes/no-such-id")
        assert resp.status_code == 404


class TestNotesWebPin:
    def test_pin_toggle(self, client, tmp_db):
        note = create_note(CUST_ID, "contact", "ct-1",
                           content_html="<p>pin</p>", created_by=USER_ID)
        resp = client.post(f"/notes/{note['id']}/pin?entity_type=contact&entity_id=ct-1")
        assert resp.status_code == 200
        assert "Unpin" in resp.text

    def test_pin_toggle_without_entity_params(self, client, tmp_db):
        """Falls back to first entity when no entity params given."""
        note = create_note(CUST_ID, "contact", "ct-1",
                           content_html="<p>pin</p>", created_by=USER_ID)
        resp = client.post(f"/notes/{note['id']}/pin")
        assert resp.status_code == 200
        assert "Unpin" in resp.text

    def test_pin_nonexistent(self, client, tmp_db):
        resp = client.post("/notes/no-such-id/pin")
        assert resp.status_code == 404


class TestNotesWebRevisions:
    def test_revisions_list(self, client, tmp_db):
        note = create_note(CUST_ID, "contact", "ct-1",
                           content_html="<p>r1</p>", created_by=USER_ID)
        update_note(note["id"], content_html="<p>r2</p>", updated_by=USER_ID)
        resp = client.get(f"/notes/{note['id']}/revisions")
        assert resp.status_code == 200
        assert "v2" in resp.text
        assert "v1" in resp.text

    def test_revision_detail(self, client, tmp_db):
        note = create_note(CUST_ID, "contact", "ct-1",
                           content_html="<p>original</p>", created_by=USER_ID)
        rev_id = note["current_revision_id"]
        resp = client.get(f"/notes/{note['id']}/revisions/{rev_id}")
        assert resp.status_code == 200
        assert "original" in resp.text

    def test_revision_nonexistent(self, client, tmp_db):
        note = create_note(CUST_ID, "contact", "ct-1",
                           content_html="<p>x</p>", created_by=USER_ID)
        resp = client.get(f"/notes/{note['id']}/revisions/no-such-rev")
        assert resp.status_code == 404


class TestNotesWebUpload:
    def test_upload_image(self, client, tmp_db):
        data = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        resp = client.post("/notes/upload",
                           files={"file": ("test.png", data, "image/png")})
        assert resp.status_code == 200
        body = resp.json()
        assert "url" in body
        assert body["original_name"] == "test.png"

    def test_upload_disallowed_type(self, client, tmp_db):
        resp = client.post("/notes/upload",
                           files={"file": ("test.exe", b"MZ", "application/x-msdownload")})
        assert resp.status_code == 400

    def test_upload_too_large(self, client, tmp_db, monkeypatch):
        monkeypatch.setattr("poc.config.MAX_UPLOAD_SIZE_MB", 0)  # 0 MB limit
        data = b"\x00" * 1024
        resp = client.post("/notes/upload",
                           files={"file": ("big.png", data, "image/png")})
        assert resp.status_code == 400

    def test_serve_uploaded_file(self, client, tmp_db):
        data = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        resp = client.post("/notes/upload",
                           files={"file": ("serve.png", data, "image/png")})
        assert resp.status_code == 200
        url = resp.json()["url"]
        resp2 = client.get(url)
        assert resp2.status_code == 200


class TestNotesWebMentions:
    def test_mention_autocomplete(self, client, tmp_db):
        resp = client.get("/notes/mentions?q=Admin&type=user")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert any("Admin" in item.get("name", "") for item in data)

    def test_mention_empty_query(self, client, tmp_db):
        resp = client.get("/notes/mentions?q=&type=user")
        assert resp.status_code == 200
        assert resp.json() == []


class TestNotesWebSearch:
    def test_search_page(self, client, tmp_db):
        create_note(CUST_ID, "contact", "ct-1", title="Searchable",
                    content_html="<p>Find this text</p>", created_by=USER_ID)
        resp = client.get("/notes/search?q=searchable")
        assert resp.status_code == 200
        assert "Searchable" in resp.text

    def test_search_empty(self, client, tmp_db):
        resp = client.get("/notes/search")
        assert resp.status_code == 200
        assert "Search notes" in resp.text


# ===================================================================
# Entity detail page integration
# ===================================================================

class TestEntityIntegration:
    def test_contact_detail_shows_notes(self, client, tmp_db):
        create_note(CUST_ID, "contact", "ct-1", title="Contact Note",
                    content_html="<p>body</p>", created_by=USER_ID)
        # Need user_contacts visibility row
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO user_contacts (id, user_id, contact_id, visibility, is_owner, created_at, updated_at) "
                "VALUES (?, ?, 'ct-1', 'public', 1, ?, ?)",
                (str(uuid.uuid4()), USER_ID, _NOW, _NOW),
            )
        resp = client.get("/contacts/ct-1")
        assert resp.status_code == 200
        assert "Contact Note" in resp.text
        assert "Notes" in resp.text

    def test_company_detail_shows_notes(self, client, tmp_db):
        create_note(CUST_ID, "company", "co-1", title="Company Note",
                    content_html="<p>body</p>", created_by=USER_ID)
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO user_companies (id, user_id, company_id, visibility, is_owner, created_at, updated_at) "
                "VALUES (?, ?, 'co-1', 'public', 1, ?, ?)",
                (str(uuid.uuid4()), USER_ID, _NOW, _NOW),
            )
        resp = client.get("/companies/co-1")
        assert resp.status_code == 200
        assert "Company Note" in resp.text

    def test_conversation_detail_shows_notes(self, client, tmp_db):
        create_note(CUST_ID, "conversation", "conv-1", title="Conv Note",
                    content_html="<p>body</p>", created_by=USER_ID)
        resp = client.get("/conversations/conv-1")
        assert resp.status_code == 200
        assert "Conv Note" in resp.text


class TestSanitization:
    def test_script_tag_stripped(self, client, tmp_db):
        resp = client.post("/notes", data={
            "entity_type": "contact",
            "entity_id": "ct-1",
            "content_html": '<p>Hello</p><script>alert("xss")</script>',
        })
        assert resp.status_code == 200
        # Script should be stripped
        note = get_notes_for_entity("contact", "ct-1", customer_id=CUST_ID)[0]
        assert "<script>" not in (note["content_html"] or "")

    def test_allowed_tags_preserved(self, client, tmp_db):
        html = "<p>A <strong>bold</strong> <em>italic</em> word</p>"
        resp = client.post("/notes", data={
            "entity_type": "contact",
            "entity_id": "ct-1",
            "content_html": html,
        })
        assert resp.status_code == 200
        note = get_notes_for_entity("contact", "ct-1", customer_id=CUST_ID)[0]
        assert "<strong>bold</strong>" in (note["content_html"] or "")


# ===================================================================
# Migration
# ===================================================================

class TestMigrationV12:
    def test_migration_creates_tables(self, tmp_path):
        """Verify migrate_to_v12 creates all 5 tables."""
        from poc.migrate_to_v12 import migrate

        db_path = tmp_path / "test.db"
        import sqlite3
        conn = sqlite3.connect(str(db_path))
        conn.execute("PRAGMA user_version = 11")
        # Need minimal schema for FK refs
        conn.execute("CREATE TABLE customers (id TEXT PRIMARY KEY, name TEXT, slug TEXT, is_active INTEGER, created_at TEXT, updated_at TEXT)")
        conn.execute("CREATE TABLE users (id TEXT PRIMARY KEY, customer_id TEXT, email TEXT, name TEXT, role TEXT, is_active INTEGER, password_hash TEXT, google_sub TEXT, created_at TEXT, updated_at TEXT)")
        conn.commit()
        conn.close()

        migrate(db_path, dry_run=False)

        conn = sqlite3.connect(str(db_path))
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
        conn.close()

        assert "notes" in tables
        assert "note_revisions" in tables
        assert "note_attachments" in tables
        assert "note_mentions" in tables
        assert "notes_fts" in tables


# ===================================================================
# Multi-entity junction — Phase 18
# ===================================================================

class TestNoteEntities:
    def test_create_note_creates_junction_row(self, tmp_db):
        note = create_note(CUST_ID, "contact", "ct-1",
                           content_html="<p>body</p>", created_by=USER_ID)
        entities = get_note_entities(note["id"])
        assert len(entities) == 1
        assert entities[0]["entity_type"] == "contact"
        assert entities[0]["entity_id"] == "ct-1"
        assert entities[0]["is_pinned"] == 0

    def test_get_note_returns_entities_list(self, tmp_db):
        note = create_note(CUST_ID, "contact", "ct-1",
                           content_html="<p>x</p>", created_by=USER_ID)
        fetched = get_note(note["id"])
        assert "entities" in fetched
        assert len(fetched["entities"]) == 1
        assert fetched["entities"][0]["entity_type"] == "contact"

    def test_add_note_entity_links_second_entity(self, tmp_db):
        note = create_note(CUST_ID, "contact", "ct-1",
                           content_html="<p>x</p>", created_by=USER_ID)
        result = add_note_entity(note["id"], "company", "co-1")
        assert result is True
        entities = get_note_entities(note["id"])
        assert len(entities) == 2
        types = {e["entity_type"] for e in entities}
        assert types == {"contact", "company"}

    def test_add_note_entity_duplicate_is_idempotent(self, tmp_db):
        note = create_note(CUST_ID, "contact", "ct-1",
                           content_html="<p>x</p>", created_by=USER_ID)
        result = add_note_entity(note["id"], "contact", "ct-1")
        assert result is False  # already linked
        entities = get_note_entities(note["id"])
        assert len(entities) == 1

    def test_add_note_entity_invalid_type(self, tmp_db):
        note = create_note(CUST_ID, "contact", "ct-1",
                           content_html="<p>x</p>", created_by=USER_ID)
        with pytest.raises(ValueError, match="Invalid entity_type"):
            add_note_entity(note["id"], "bogus", "x")

    def test_add_note_entity_nonexistent_note(self, tmp_db):
        with pytest.raises(ValueError, match="Note not found"):
            add_note_entity("no-such-id", "contact", "ct-1")

    def test_remove_note_entity_unlinks(self, tmp_db):
        note = create_note(CUST_ID, "contact", "ct-1",
                           content_html="<p>x</p>", created_by=USER_ID)
        add_note_entity(note["id"], "company", "co-1")
        assert len(get_note_entities(note["id"])) == 2
        result = remove_note_entity(note["id"], "contact", "ct-1")
        assert result is True
        entities = get_note_entities(note["id"])
        assert len(entities) == 1
        assert entities[0]["entity_type"] == "company"

    def test_remove_note_entity_raises_on_last_link(self, tmp_db):
        note = create_note(CUST_ID, "contact", "ct-1",
                           content_html="<p>x</p>", created_by=USER_ID)
        with pytest.raises(ValueError, match="Cannot remove the last entity link"):
            remove_note_entity(note["id"], "contact", "ct-1")

    def test_note_appears_in_both_entity_lists(self, tmp_db):
        note = create_note(CUST_ID, "contact", "ct-1",
                           title="Shared Note", content_html="<p>x</p>",
                           created_by=USER_ID)
        add_note_entity(note["id"], "company", "co-1")

        contact_notes = get_notes_for_entity("contact", "ct-1", customer_id=CUST_ID)
        company_notes = get_notes_for_entity("company", "co-1", customer_id=CUST_ID)
        assert any(n["id"] == note["id"] for n in contact_notes)
        assert any(n["id"] == note["id"] for n in company_notes)

    def test_pin_scoped_per_entity(self, tmp_db):
        note = create_note(CUST_ID, "contact", "ct-1",
                           content_html="<p>x</p>", created_by=USER_ID)
        add_note_entity(note["id"], "company", "co-1")

        # Pin on contact entity
        toggle_pin(note["id"], "contact", "ct-1")

        # Check pin status per entity
        contact_notes = get_notes_for_entity("contact", "ct-1", customer_id=CUST_ID)
        company_notes = get_notes_for_entity("company", "co-1", customer_id=CUST_ID)
        assert contact_notes[0]["is_pinned"] == 1
        assert company_notes[0]["is_pinned"] == 0

    def test_delete_note_cascades_junction(self, tmp_db):
        note = create_note(CUST_ID, "contact", "ct-1",
                           content_html="<p>x</p>", created_by=USER_ID)
        add_note_entity(note["id"], "company", "co-1")
        delete_note(note["id"])
        assert get_note_entities(note["id"]) == []

    def test_web_pin_with_entity_params(self, client, tmp_db):
        note = create_note(CUST_ID, "contact", "ct-1",
                           content_html="<p>x</p>", created_by=USER_ID)
        resp = client.post(f"/notes/{note['id']}/pin?entity_type=contact&entity_id=ct-1")
        assert resp.status_code == 200
        assert "Unpin" in resp.text

    def test_web_edit_with_entity_params(self, client, tmp_db):
        note = create_note(CUST_ID, "contact", "ct-1",
                           title="Edit Me", content_html="<p>x</p>",
                           created_by=USER_ID)
        resp = client.get(f"/notes/{note['id']}/edit?entity_type=contact&entity_id=ct-1")
        assert resp.status_code == 200
        assert "Edit Me" in resp.text

    def test_web_add_entity(self, client, tmp_db):
        note = create_note(CUST_ID, "contact", "ct-1",
                           content_html="<p>x</p>", created_by=USER_ID)
        resp = client.post(f"/notes/{note['id']}/entities", data={
            "entity_type": "company",
            "entity_id": "co-1",
        })
        assert resp.status_code == 200
        entities = get_note_entities(note["id"])
        assert len(entities) == 2

    def test_web_remove_entity(self, client, tmp_db):
        note = create_note(CUST_ID, "contact", "ct-1",
                           content_html="<p>x</p>", created_by=USER_ID)
        add_note_entity(note["id"], "company", "co-1")
        resp = client.delete(f"/notes/{note['id']}/entities/contact/ct-1")
        assert resp.status_code == 200
        entities = get_note_entities(note["id"])
        assert len(entities) == 1

    def test_web_remove_last_entity_rejected(self, client, tmp_db):
        note = create_note(CUST_ID, "contact", "ct-1",
                           content_html="<p>x</p>", created_by=USER_ID)
        resp = client.delete(f"/notes/{note['id']}/entities/contact/ct-1")
        assert resp.status_code == 400


# ===================================================================
# Migration v13
# ===================================================================

class TestMigrationV13:
    def _create_v12_db(self, db_path):
        """Create a minimal v12 database with notes for migration testing."""
        import sqlite3 as _sqlite3
        conn = _sqlite3.connect(str(db_path))
        conn.execute("PRAGMA user_version = 12")
        conn.execute("CREATE TABLE customers (id TEXT PRIMARY KEY, name TEXT, slug TEXT, is_active INTEGER, created_at TEXT, updated_at TEXT)")
        conn.execute("CREATE TABLE users (id TEXT PRIMARY KEY, customer_id TEXT, email TEXT, name TEXT, role TEXT, is_active INTEGER, password_hash TEXT, google_sub TEXT, created_at TEXT, updated_at TEXT)")
        conn.execute("INSERT INTO customers VALUES ('c1','Test','test',1,'2026-01-01','2026-01-01')")
        conn.execute("INSERT INTO users VALUES ('u1','c1','a@b.com','User','admin',1,NULL,NULL,'2026-01-01','2026-01-01')")
        # v12 notes table (with entity_type, entity_id, is_pinned)
        conn.execute("""\
            CREATE TABLE notes (
                id TEXT PRIMARY KEY,
                customer_id TEXT NOT NULL REFERENCES customers(id),
                entity_type TEXT NOT NULL,
                entity_id TEXT NOT NULL,
                title TEXT,
                is_pinned INTEGER NOT NULL DEFAULT 0,
                current_revision_id TEXT,
                created_by TEXT,
                updated_by TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        conn.execute("CREATE TABLE note_revisions (id TEXT PRIMARY KEY, note_id TEXT, revision_number INTEGER, content_json TEXT, content_html TEXT, revised_by TEXT, created_at TEXT)")
        conn.execute("CREATE TABLE note_attachments (id TEXT PRIMARY KEY, note_id TEXT, filename TEXT, original_name TEXT, mime_type TEXT, size_bytes INTEGER, storage_path TEXT, uploaded_by TEXT, created_at TEXT)")
        conn.execute("CREATE TABLE note_mentions (id TEXT PRIMARY KEY, note_id TEXT, mention_type TEXT, mentioned_id TEXT, created_at TEXT)")
        conn.execute("CREATE INDEX idx_notes_entity ON notes(entity_type, entity_id)")
        conn.execute("CREATE INDEX idx_notes_pinned ON notes(entity_type, entity_id, is_pinned DESC, updated_at DESC)")
        # Insert test notes
        conn.execute(
            "INSERT INTO notes VALUES ('n1','c1','contact','ct-1','Note A',1,'r1','u1','u1','2026-01-01','2026-01-01')"
        )
        conn.execute(
            "INSERT INTO notes VALUES ('n2','c1','company','co-1','Note B',0,'r2','u1','u1','2026-01-02','2026-01-02')"
        )
        conn.execute(
            "INSERT INTO note_revisions VALUES ('r1','n1',1,NULL,'<p>A</p>','u1','2026-01-01')"
        )
        conn.execute(
            "INSERT INTO note_revisions VALUES ('r2','n2',1,NULL,'<p>B</p>','u1','2026-01-02')"
        )
        conn.commit()
        conn.close()

    def test_migration_creates_junction_and_populates(self, tmp_path):
        import sqlite3 as _sqlite3
        from poc.migrate_to_v13 import migrate

        db_path = tmp_path / "test.db"
        self._create_v12_db(db_path)

        migrate(db_path, dry_run=False)

        conn = _sqlite3.connect(str(db_path))
        conn.row_factory = _sqlite3.Row
        # Junction table exists and has data
        rows = conn.execute("SELECT * FROM note_entities ORDER BY note_id").fetchall()
        assert len(rows) == 2
        assert rows[0]["note_id"] == "n1"
        assert rows[0]["entity_type"] == "contact"
        assert rows[0]["entity_id"] == "ct-1"
        assert rows[0]["is_pinned"] == 1
        assert rows[1]["note_id"] == "n2"
        assert rows[1]["entity_type"] == "company"
        assert rows[1]["is_pinned"] == 0
        conn.close()

    def test_migration_removes_entity_columns_from_notes(self, tmp_path):
        import sqlite3 as _sqlite3
        from poc.migrate_to_v13 import migrate

        db_path = tmp_path / "test.db"
        self._create_v12_db(db_path)

        migrate(db_path, dry_run=False)

        conn = _sqlite3.connect(str(db_path))
        cols = {r[1] for r in conn.execute("PRAGMA table_info(notes)").fetchall()}
        assert "entity_type" not in cols
        assert "entity_id" not in cols
        assert "is_pinned" not in cols
        # Remaining columns still there
        assert "id" in cols
        assert "customer_id" in cols
        assert "title" in cols
        assert "current_revision_id" in cols
        conn.close()

    def test_migration_bumps_version(self, tmp_path):
        import sqlite3 as _sqlite3
        from poc.migrate_to_v13 import migrate

        db_path = tmp_path / "test.db"
        self._create_v12_db(db_path)

        migrate(db_path, dry_run=False)

        conn = _sqlite3.connect(str(db_path))
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        assert version == 13
        conn.close()


# ===================================================================
# Notes Browser — master-detail layout
# ===================================================================

class TestNotesBrowser:
    """Tests for the global notes browser (master-detail layout)."""

    def test_browser_layout_renders(self, client, tmp_db):
        resp = client.get("/notes/search")
        assert resp.status_code == 200
        assert "notes-browser" in resp.text
        assert "notes-list" in resp.text
        assert "notes-viewer" in resp.text
        assert "Select a note to view" in resp.text

    def test_recent_notes_in_list(self, client, tmp_db):
        create_note(CUST_ID, "contact", "ct-1", title="Alpha Note",
                    content_html="<p>alpha body</p>", created_by=USER_ID)
        resp = client.get("/notes/search")
        assert resp.status_code == 200
        assert "Alpha Note" in resp.text
        assert "notes-grid" in resp.text

    def test_search_list_partial(self, client, tmp_db):
        create_note(CUST_ID, "contact", "ct-1", title="Gamma",
                    content_html="<p>gamma</p>", created_by=USER_ID)
        resp = client.get("/notes/search/list")
        assert resp.status_code == 200
        assert "Gamma" in resp.text
        assert "notes-grid" in resp.text

    def test_search_list_has_table_headers(self, client, tmp_db):
        resp = client.get("/notes/search/list")
        assert resp.status_code == 200
        assert "<th>" in resp.text
        assert "Name" in resp.text
        assert "Created" in resp.text
        assert "Updated" in resp.text
        assert "Author" in resp.text
        assert "Entity" in resp.text

    def test_search_list_filters(self, client, tmp_db):
        create_note(CUST_ID, "contact", "ct-1", title="Alpha",
                    content_html="<p>alpha body</p>", created_by=USER_ID)
        create_note(CUST_ID, "company", "co-1", title="Beta",
                    content_html="<p>beta body</p>", created_by=USER_ID)
        resp = client.get("/notes/search/list?q=alpha")
        assert resp.status_code == 200
        assert "Alpha" in resp.text
        assert "Beta" not in resp.text

    def test_view_note(self, client, tmp_db):
        note = create_note(CUST_ID, "contact", "ct-1", title="View Me",
                           content_html="<p>full content here</p>",
                           created_by=USER_ID)
        resp = client.get(f"/notes/{note['id']}/view")
        assert resp.status_code == 200
        assert "View Me" in resp.text
        assert "full content here" in resp.text
        assert "notes-viewer-header" in resp.text

    def test_view_shows_entity_names(self, client, tmp_db):
        note = create_note(CUST_ID, "contact", "ct-1", title="Entity Test",
                           content_html="<p>x</p>", created_by=USER_ID)
        resp = client.get(f"/notes/{note['id']}/view")
        assert resp.status_code == 200
        assert "Alice" in resp.text  # contact name from fixture

    def test_view_nonexistent_note(self, client, tmp_db):
        resp = client.get("/notes/no-such-id/view")
        assert resp.status_code == 404

    def test_edit_with_source_browser(self, client, tmp_db):
        note = create_note(CUST_ID, "contact", "ct-1", title="Edit Browser",
                           content_html="<p>x</p>", created_by=USER_ID)
        resp = client.get(f"/notes/{note['id']}/edit?source=browser")
        assert resp.status_code == 200
        assert "Edit Browser" in resp.text
        assert "source=browser" in resp.text  # form action contains source

    def test_update_with_source_browser(self, client, tmp_db):
        note = create_note(CUST_ID, "contact", "ct-1", title="Old Title",
                           content_html="<p>old</p>", created_by=USER_ID)
        resp = client.put(f"/notes/{note['id']}?source=browser", data={
            "title": "New Title",
            "content_html": "<p>new</p>",
        })
        assert resp.status_code == 200
        assert "New Title" in resp.text
        assert "notes-viewer-header" in resp.text
        assert resp.headers.get("HX-Trigger") == "noteUpdated"

    def test_delete_with_source_browser(self, client, tmp_db):
        note = create_note(CUST_ID, "contact", "ct-1", title="Delete Me",
                           content_html="<p>x</p>", created_by=USER_ID)
        resp = client.delete(f"/notes/{note['id']}?source=browser")
        assert resp.status_code == 200
        assert "Note deleted" in resp.text
        assert resp.headers.get("HX-Trigger") == "noteDeleted"

    def test_pin_with_source_browser(self, client, tmp_db):
        note = create_note(CUST_ID, "contact", "ct-1", title="Pin Me",
                           content_html="<p>x</p>", created_by=USER_ID)
        resp = client.post(f"/notes/{note['id']}/pin?source=browser")
        assert resp.status_code == 200
        assert "notes-viewer-header" in resp.text
        assert resp.headers.get("HX-Trigger") == "notePinned"

    def test_list_shows_entity_names(self, client, tmp_db):
        create_note(CUST_ID, "contact", "ct-1", title="Contact Note",
                    content_html="<p>x</p>", created_by=USER_ID)
        create_note(CUST_ID, "company", "co-1", title="Company Note",
                    content_html="<p>x</p>", created_by=USER_ID)
        resp = client.get("/notes/search/list")
        assert resp.status_code == 200
        assert "Alice" in resp.text
        assert "Acme Inc" in resp.text

    def test_list_shows_author_name(self, client, tmp_db):
        create_note(CUST_ID, "contact", "ct-1", title="Authored Note",
                    content_html="<p>x</p>", created_by=USER_ID)
        resp = client.get("/notes/search/list")
        assert resp.status_code == 200
        assert "Admin User" in resp.text

    def test_default_sort_is_updated_desc(self, client, tmp_db):
        """Default sort is -updated (most recently updated first)."""
        import time
        n1 = create_note(CUST_ID, "contact", "ct-1", title="Older Note",
                         content_html="<p>old</p>", created_by=USER_ID)
        time.sleep(0.05)
        n2 = create_note(CUST_ID, "contact", "ct-1", title="Newer Note",
                         content_html="<p>new</p>", created_by=USER_ID)
        resp = client.get("/notes/search/list")
        assert resp.status_code == 200
        text = resp.text
        # Newer should appear before older
        assert text.index("Newer Note") < text.index("Older Note")

    def test_sort_by_name_ascending(self, client, tmp_db):
        create_note(CUST_ID, "contact", "ct-1", title="Zebra",
                    content_html="<p>z</p>", created_by=USER_ID)
        create_note(CUST_ID, "contact", "ct-1", title="Alpha",
                    content_html="<p>a</p>", created_by=USER_ID)
        resp = client.get("/notes/search/list?sort=name")
        assert resp.status_code == 200
        text = resp.text
        assert text.index("Alpha") < text.index("Zebra")

    def test_sort_by_name_descending(self, client, tmp_db):
        create_note(CUST_ID, "contact", "ct-1", title="Zebra",
                    content_html="<p>z</p>", created_by=USER_ID)
        create_note(CUST_ID, "contact", "ct-1", title="Alpha",
                    content_html="<p>a</p>", created_by=USER_ID)
        resp = client.get("/notes/search/list?sort=-name")
        assert resp.status_code == 200
        text = resp.text
        assert text.index("Zebra") < text.index("Alpha")

    def test_sort_by_created(self, client, tmp_db):
        import time
        create_note(CUST_ID, "contact", "ct-1", title="First Created",
                    content_html="<p>x</p>", created_by=USER_ID)
        time.sleep(0.05)
        create_note(CUST_ID, "contact", "ct-1", title="Second Created",
                    content_html="<p>x</p>", created_by=USER_ID)
        resp = client.get("/notes/search/list?sort=created")
        assert resp.status_code == 200
        text = resp.text
        assert text.index("First Created") < text.index("Second Created")
