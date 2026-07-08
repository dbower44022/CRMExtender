"""Phase 5 decommission tests: legacy page URLs redirect into the SPA,
kept compatibility routes still work, and legacy action routes are gone."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from poc.database import get_connection, init_db

_NOW = datetime.now(timezone.utc).isoformat()

CUST_ID = "cust-redir-test"
USER_ID = "user-redir-admin"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_file = tmp_path / "test.db"
    monkeypatch.setattr("poc.config.DB_PATH", db_file)
    monkeypatch.setattr("poc.config.CRM_AUTH_ENABLED", False)
    monkeypatch.setattr("poc.config.UPLOAD_DIR", tmp_path / "uploads")
    init_db(db_file)
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO customers (id, name, slug, is_active, created_at, updated_at) "
            "VALUES (?, 'R Org', 'redir', 1, ?, ?)", (CUST_ID, _NOW, _NOW))
        conn.execute(
            "INSERT INTO users "
            "(id, customer_id, email, name, role, is_active, created_at, updated_at) "
            "VALUES (?, ?, 'a@redir.com', 'R Admin', 'admin', 1, ?, ?)",
            (USER_ID, CUST_ID, _NOW, _NOW))
    monkeypatch.setattr(
        "poc.hierarchy.get_current_user",
        lambda: {"id": USER_ID, "email": "a@redir.com", "name": "R Admin",
                 "role": "admin", "customer_id": CUST_ID})
    from poc.web.app import create_app
    return TestClient(create_app(), raise_server_exceptions=False)


class TestRedirects:
    def test_root_redirects_to_dashboard(self, client):
        r = client.get("/", follow_redirects=False)
        assert r.status_code == 308
        assert r.headers["location"] == "/app/dashboard"

    @pytest.mark.parametrize("plural", [
        "contacts", "companies", "conversations", "communications",
        "events", "projects", "relationships",
    ])
    def test_entity_pages_redirect(self, client, plural):
        r = client.get(f"/{plural}", follow_redirects=False)
        assert (r.status_code, r.headers["location"]) == (308, f"/app/{plural}")
        r = client.get(f"/{plural}/some-id", follow_redirects=False)
        assert (r.status_code, r.headers["location"]) == (
            308, f"/app/{plural}/some-id")

    def test_settings_pages_redirect(self, client):
        r = client.get("/settings/profile", follow_redirects=False)
        assert (r.status_code, r.headers["location"]) == (308, "/app/")

    def test_views_redirect(self, client):
        r = client.get("/views", follow_redirects=False)
        assert r.status_code == 308

    def test_notes_search_redirects(self, client):
        r = client.get("/notes/search", follow_redirects=False)
        assert (r.status_code, r.headers["location"]) == (308, "/app/notes")


class TestKeptRoutes:
    def test_login_page_still_served(self, client):
        assert client.get("/login").status_code == 200

    def test_oauth_connect_still_exists(self, client):
        # Not a 404/redirect-to-app: either starts OAuth (302 to Google)
        # or 302s with a not-configured error
        r = client.get("/settings/accounts/connect", follow_redirects=False)
        assert r.status_code == 302

    def test_legacy_notes_file_path_serves(self, client, tmp_path):
        import io
        up = client.post(
            "/api/v1/notes/upload",
            files={"file": ("a.png", io.BytesIO(b"data"), "image/png")},
        ).json()
        r = client.get(up["url"])  # /notes/files/{id}/{name}
        assert r.status_code == 200
        assert r.content == b"data"


class TestGoneActions:
    def test_legacy_action_routes_404(self, client):
        assert client.post("/sync").status_code in (404, 405)
        assert client.post(
            "/communications/archive", data={"ids": ["x"]}).status_code in (404, 405)
        assert client.post(
            "/contacts/x/phones", data={"number": "1"}).status_code in (404, 405)
