"""Tests for the version endpoint."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from poc.database import get_connection, init_db

_NOW = datetime.now(timezone.utc).isoformat()


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_file = tmp_path / "test.db"
    monkeypatch.setattr("poc.config.DB_PATH", db_file)
    monkeypatch.setattr("poc.config.CRM_AUTH_ENABLED", False)
    init_db(db_file)
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO customers (id, name, slug, is_active, created_at, updated_at) "
            "VALUES ('c', 'Org', 'org', 1, ?, ?)", (_NOW, _NOW))
        conn.execute(
            "INSERT INTO users (id, customer_id, email, name, role, is_active, "
            "created_at, updated_at) VALUES ('u', 'c', 'a@x.com', 'A', 'admin', 1, ?, ?)",
            (_NOW, _NOW))
    monkeypatch.setattr(
        "poc.hierarchy.get_current_user",
        lambda: {"id": "u", "email": "a@x.com", "name": "A", "role": "admin",
                 "customer_id": "c"})
    from poc.web.app import create_app
    return TestClient(create_app(), raise_server_exceptions=False)


def test_version_shape(client):
    r = client.get("/api/v1/version")
    assert r.status_code == 200
    data = r.json()
    assert set(data) >= {"sha", "short_sha", "committed_at", "message", "source"}
    # In the repo working tree, this resolves to a real git sha
    assert data["source"] == "git"
    assert len(data["short_sha"]) == 7


def test_health_reports_version(client):
    data = client.get("/api/v1/health").json()
    assert data["status"] == "ok"
    assert data["version"] != "1.0.0"  # now the real short sha


def test_version_fallback_to_file(monkeypatch, tmp_path):
    import poc.version as ver
    ver.get_version.cache_clear()
    monkeypatch.setattr(ver, "_git", lambda *a: None)
    monkeypatch.setattr(ver, "_ROOT", tmp_path)
    (tmp_path / "VERSION").write_text("release-2026-07\n")
    v = ver.get_version()
    assert v["source"] == "file"
    assert v["sha"] == "release-2026-07"
    ver.get_version.cache_clear()
