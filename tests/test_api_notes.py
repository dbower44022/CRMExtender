"""Tests for the Phase 3 notes JSON API (Legacy UI Migration PRD)."""

from __future__ import annotations

import io
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from poc.database import get_connection, init_db

_NOW = datetime.now(timezone.utc).isoformat()

CUST_ID = "cust-notes-test"
USER_ID = "user-notes-admin"


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
            "VALUES (?, 'Test Org', 'notes', 1, ?, ?)",
            (CUST_ID, _NOW, _NOW),
        )
        conn.execute(
            "INSERT INTO users "
            "(id, customer_id, email, name, role, is_active, created_at, updated_at) "
            "VALUES (?, ?, 'admin@notes.com', 'Note Admin', 'admin', 1, ?, ?)",
            (USER_ID, CUST_ID, _NOW, _NOW),
        )
        conn.execute(
            "INSERT INTO contacts (id, customer_id, name, created_at, updated_at) "
            "VALUES ('ct-1', ?, 'Note Target', ?, ?)",
            (CUST_ID, _NOW, _NOW),
        )
        conn.execute(
            "INSERT INTO companies (id, customer_id, name, status, created_at, updated_at) "
            "VALUES ('co-1', ?, 'Note Co', 'active', ?, ?)",
            (CUST_ID, _NOW, _NOW),
        )
    return db_file


@pytest.fixture()
def client(tmp_db, monkeypatch):
    monkeypatch.setattr(
        "poc.hierarchy.get_current_user",
        lambda: {"id": USER_ID, "email": "admin@notes.com", "name": "Note Admin",
                 "role": "admin", "customer_id": CUST_ID},
    )
    from poc.web.app import create_app
    return TestClient(create_app(), raise_server_exceptions=False)


def _create(client, **overrides):
    body = {
        "entity_type": "contact",
        "entity_id": "ct-1",
        "title": "Test Note",
        "content_html": "<p>Hello <strong>world</strong></p>",
        "content_json": '{"type":"doc","content":[{"type":"paragraph"}]}',
    }
    body.update(overrides)
    r = client.post("/api/v1/notes", json=body)
    assert r.status_code == 201, r.text
    return r.json()


class TestNotesCrud:
    def test_create_and_list(self, client, tmp_db):
        note = _create(client)
        assert note["title"] == "Test Note"
        assert note["author_name"] == "Note Admin"
        assert note["entities"][0]["entity_name"] == "Note Target"
        listing = client.get(
            "/api/v1/notes?entity_type=contact&entity_id=ct-1").json()
        assert [n["id"] for n in listing["notes"]] == [note["id"]]

    def test_create_sanitizes_html(self, client, tmp_db):
        note = _create(
            client,
            content_html='<p>ok</p><script>alert(1)</script>'
                         '<span class="mention" data-id="u1">@x</span>',
        )
        assert "<script>" not in note["content_html"]
        assert "alert(1)" in note["content_html"]  # bleach strips tags, keeps text
        assert 'data-id="u1"' in note["content_html"]

    def test_invalid_entity_type_400(self, client, tmp_db):
        r = client.post("/api/v1/notes", json={
            "entity_type": "widget", "entity_id": "x"})
        assert r.status_code == 400

    def test_update_creates_revision(self, client, tmp_db):
        note = _create(client)
        r = client.put(f"/api/v1/notes/{note['id']}",
                       json={"title": "Renamed", "content_html": "<p>v2</p>"})
        assert r.json()["title"] == "Renamed"
        revs = client.get(f"/api/v1/notes/{note['id']}/revisions").json()
        assert len(revs["revisions"]) == 2
        assert revs["revisions"][0]["revision_number"] == 2
        assert revs["current_revision_id"] == revs["revisions"][0]["id"]
        # List is trimmed; single revision has content
        assert "content_html" not in revs["revisions"][0]
        rev = client.get(
            f"/api/v1/notes/{note['id']}/revisions/{revs['revisions'][1]['id']}"
        ).json()
        assert rev["content_html"] == "<p>Hello <strong>world</strong></p>"

    def test_delete(self, client, tmp_db):
        note = _create(client)
        assert client.delete(f"/api/v1/notes/{note['id']}").json()["ok"] is True
        r = client.get(f"/api/v1/notes/{note['id']}/full")
        assert r.status_code == 404

    def test_cross_tenant_404(self, client, tmp_db):
        note = _create(client)
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO customers (id, name, slug, is_active, created_at, updated_at) "
                "VALUES ('cust-other', 'Other', 'other', 1, ?, ?)", (_NOW, _NOW))
            conn.execute(
                "UPDATE notes SET customer_id = 'cust-other' WHERE id = ?",
                (note["id"],))
        assert client.get(f"/api/v1/notes/{note['id']}/full").status_code == 404


class TestPinAndEntities:
    def test_pin_toggle_per_link(self, client, tmp_db):
        note = _create(client)
        r = client.post(f"/api/v1/notes/{note['id']}/pin",
                        json={"entity_type": "contact", "entity_id": "ct-1"})
        assert r.json()["is_pinned"] is True
        r = client.post(f"/api/v1/notes/{note['id']}/pin",
                        json={"entity_type": "contact", "entity_id": "ct-1"})
        assert r.json()["is_pinned"] is False

    def test_pinned_notes_list_first(self, client, tmp_db):
        a = _create(client, title="First")
        b = _create(client, title="Second")
        client.post(f"/api/v1/notes/{a['id']}/pin",
                    json={"entity_type": "contact", "entity_id": "ct-1"})
        listing = client.get(
            "/api/v1/notes?entity_type=contact&entity_id=ct-1").json()
        assert listing["notes"][0]["id"] == a["id"]
        assert b["id"] == listing["notes"][1]["id"]

    def test_link_and_unlink_entities(self, client, tmp_db):
        note = _create(client)
        r = client.post(f"/api/v1/notes/{note['id']}/entities",
                        json={"entity_type": "company", "entity_id": "co-1"})
        assert r.json()["created"] is True
        assert len(r.json()["entities"]) == 2
        r = client.delete(
            f"/api/v1/notes/{note['id']}/entities/company/co-1")
        assert len(r.json()["entities"]) == 1
        # Removing the last link is blocked
        r = client.delete(
            f"/api/v1/notes/{note['id']}/entities/contact/ct-1")
        assert r.status_code == 409


class TestAttachments:
    def _upload(self, client, name="pic.png", mime="image/png", data=b"\x89PNG fake"):
        return client.post(
            "/api/v1/notes/upload",
            files={"file": (name, io.BytesIO(data), mime)},
        )

    def test_upload_and_serve(self, client, tmp_db):
        r = self._upload(client)
        assert r.status_code == 200, r.text
        up = r.json()
        assert up["original_name"] == "pic.png"
        assert up["url"].startswith("/notes/files/")
        # Serve via the API path
        serve = client.get(f"/api/v1/notes/files/{up['id']}/{up['url'].split('/')[-1]}")
        assert serve.status_code == 200
        assert serve.content == b"\x89PNG fake"

    def test_disallowed_type_400(self, client, tmp_db):
        r = self._upload(client, name="x.exe", mime="application/x-msdownload")
        assert r.status_code == 400

    def test_adoption_and_file_cleanup_on_delete(self, client, tmp_db):
        up = self._upload(client).json()
        note = _create(client, attachment_ids=[up["id"]])
        with get_connection() as conn:
            row = conn.execute(
                "SELECT note_id, storage_path FROM note_attachments WHERE id = ?",
                (up["id"],)).fetchone()
        assert row["note_id"] == note["id"]
        from pathlib import Path
        assert Path(row["storage_path"]).exists()
        client.delete(f"/api/v1/notes/{note['id']}")
        assert not Path(row["storage_path"]).exists()


class TestMentionsAndSearch:
    def test_mentions_autocomplete_users(self, client, tmp_db):
        r = client.get("/api/v1/notes/mentions?q=Note&type=user")
        assert r.status_code == 200
        hits = r.json()
        assert hits[0]["name"] == "Note Admin"
        assert hits[0]["detail"] == "admin@notes.com"

    def test_mentions_recorded_from_content_json(self, client, tmp_db):
        note = _create(
            client,
            content_json='{"type":"doc","content":[{"type":"mention",'
                         '"attrs":{"id":"user-x","label":"X"}}]}',
        )
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT mention_type, mentioned_id FROM note_mentions "
                "WHERE note_id = ?", (note["id"],)).fetchall()
        assert [(r["mention_type"], r["mentioned_id"]) for r in rows] == [
            ("user", "user-x")]

    def test_search_fts_and_recent(self, client, tmp_db):
        _create(client, title="Alpha", content_html="<p>quarterly budget</p>")
        _create(client, title="Beta", content_html="<p>vacation plans</p>")
        r = client.get("/api/v1/notes/search?q=budget")
        results = r.json()["results"]
        assert len(results) == 1 and results[0]["title"] == "Alpha"
        assert "<mark>" in results[0]["snippet"]
        # Empty query returns recents
        r = client.get("/api/v1/notes/search")
        assert len(r.json()["results"]) == 2

    def test_search_bad_fts_syntax_400(self, client, tmp_db):
        _create(client)
        r = client.get('/api/v1/notes/search?q="unbalanced')
        assert r.status_code == 400
