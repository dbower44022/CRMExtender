"""Tests for the session management module."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from poc.database import get_connection, init_db
from poc.session import (
    cleanup_expired_sessions,
    create_session,
    delete_session,
    delete_user_sessions,
    get_session,
)

_NOW = datetime.now(timezone.utc).isoformat()


@pytest.fixture()
def tmp_db(tmp_path, monkeypatch):
    """Create a temporary database with a customer and user."""
    db_file = tmp_path / "test.db"
    monkeypatch.setattr("poc.config.DB_PATH", db_file)
    init_db(db_file)

    with get_connection(db_file) as conn:
        conn.execute(
            "INSERT INTO customers (id, name, slug, is_active, created_at, updated_at) "
            "VALUES (?, ?, ?, 1, ?, ?)",
            ("cust-1", "Test Org", "test", _NOW, _NOW),
        )
        conn.execute(
            "INSERT INTO users "
            "(id, customer_id, email, name, role, is_active, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, 'admin', 1, ?, ?)",
            ("user-1", "cust-1", "test@example.com", "Test User", _NOW, _NOW),
        )
        conn.execute(
            "INSERT INTO users "
            "(id, customer_id, email, name, role, is_active, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, 'user', 0, ?, ?)",
            ("user-inactive", "cust-1", "inactive@example.com", "Inactive", _NOW, _NOW),
        )

    return db_file


class TestCreateSession:
    def test_create_session_returns_dict(self, tmp_db):
        session = create_session("user-1", "cust-1", db_path=tmp_db)
        assert session["user_id"] == "user-1"
        assert session["customer_id"] == "cust-1"
        assert "id" in session
        assert "expires_at" in session

    def test_create_session_persists(self, tmp_db):
        session = create_session("user-1", "cust-1", db_path=tmp_db)
        with get_connection(tmp_db) as conn:
            row = conn.execute(
                "SELECT * FROM sessions WHERE id = ?", (session["id"],)
            ).fetchone()
        assert row is not None
        assert row["user_id"] == "user-1"

    def test_create_session_custom_ttl(self, tmp_db):
        session = create_session("user-1", "cust-1", ttl_hours=1, db_path=tmp_db)
        expires = datetime.fromisoformat(session["expires_at"])
        created = datetime.fromisoformat(session["created_at"])
        diff = expires - created
        assert abs(diff.total_seconds() - 3600) < 2

    def test_create_session_with_metadata(self, tmp_db):
        session = create_session(
            "user-1", "cust-1",
            ip_address="127.0.0.1",
            user_agent="TestBrowser/1.0",
            db_path=tmp_db,
        )
        assert session["ip_address"] == "127.0.0.1"
        assert session["user_agent"] == "TestBrowser/1.0"


class TestGetSession:
    def test_get_valid_session(self, tmp_db):
        session = create_session("user-1", "cust-1", db_path=tmp_db)
        retrieved = get_session(session["id"], db_path=tmp_db)
        assert retrieved is not None
        assert retrieved["user_id"] == "user-1"
        assert retrieved["email"] == "test@example.com"
        assert retrieved["role"] == "admin"

    def test_get_nonexistent_session(self, tmp_db):
        result = get_session("nonexistent", db_path=tmp_db)
        assert result is None

    def test_get_expired_session(self, tmp_db):
        session = create_session("user-1", "cust-1", ttl_hours=0, db_path=tmp_db)
        # Manually backdate the expires_at
        past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        with get_connection(tmp_db) as conn:
            conn.execute(
                "UPDATE sessions SET expires_at = ? WHERE id = ?",
                (past, session["id"]),
            )
        result = get_session(session["id"], db_path=tmp_db)
        assert result is None
        # Expired session should be cleaned up
        with get_connection(tmp_db) as conn:
            row = conn.execute(
                "SELECT id FROM sessions WHERE id = ?", (session["id"],)
            ).fetchone()
        assert row is None

    def test_get_session_inactive_user(self, tmp_db):
        session = create_session("user-inactive", "cust-1", db_path=tmp_db)
        result = get_session(session["id"], db_path=tmp_db)
        assert result is None


class TestDeleteSession:
    def test_delete_existing_session(self, tmp_db):
        session = create_session("user-1", "cust-1", db_path=tmp_db)
        assert delete_session(session["id"], db_path=tmp_db) is True
        assert get_session(session["id"], db_path=tmp_db) is None

    def test_delete_nonexistent_session(self, tmp_db):
        assert delete_session("nonexistent", db_path=tmp_db) is False


class TestDeleteUserSessions:
    def test_delete_all_user_sessions(self, tmp_db):
        create_session("user-1", "cust-1", db_path=tmp_db)
        create_session("user-1", "cust-1", db_path=tmp_db)
        count = delete_user_sessions("user-1", db_path=tmp_db)
        assert count == 2


class TestCleanupExpiredSessions:
    def test_cleanup_expired(self, tmp_db):
        # Create 2 sessions, expire one
        s1 = create_session("user-1", "cust-1", db_path=tmp_db)
        s2 = create_session("user-1", "cust-1", db_path=tmp_db)
        past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        with get_connection(tmp_db) as conn:
            conn.execute(
                "UPDATE sessions SET expires_at = ? WHERE id = ?",
                (past, s1["id"]),
            )
        count = cleanup_expired_sessions(db_path=tmp_db)
        assert count == 1
        # s2 should still exist
        assert get_session(s2["id"], db_path=tmp_db) is not None
