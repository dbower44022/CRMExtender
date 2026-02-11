"""Server-side session management."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from .database import get_connection


def create_session(
    user_id: str,
    customer_id: str,
    *,
    ttl_hours: int = 720,
    ip_address: str = "",
    user_agent: str = "",
    db_path=None,
) -> dict:
    """Create a new session. Returns the session row as a dict."""
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(hours=ttl_hours)
    session_id = str(uuid.uuid4())

    with get_connection(db_path) as conn:
        conn.execute(
            "INSERT INTO sessions "
            "(id, user_id, customer_id, created_at, expires_at, ip_address, user_agent) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (session_id, user_id, customer_id,
             now.isoformat(), expires_at.isoformat(),
             ip_address or None, user_agent or None),
        )

    return {
        "id": session_id,
        "user_id": user_id,
        "customer_id": customer_id,
        "created_at": now.isoformat(),
        "expires_at": expires_at.isoformat(),
        "ip_address": ip_address,
        "user_agent": user_agent,
    }


def get_session(session_id: str, *, db_path=None) -> dict | None:
    """Look up a session by ID. Returns None if not found or expired."""
    with get_connection(db_path) as conn:
        row = conn.execute(
            "SELECT s.*, u.email, u.name AS user_name, u.role, u.is_active "
            "FROM sessions s "
            "JOIN users u ON u.id = s.user_id "
            "WHERE s.id = ?",
            (session_id,),
        ).fetchone()

    if not row:
        return None

    r = dict(row)

    # Check expiry
    expires = datetime.fromisoformat(r["expires_at"])
    if expires < datetime.now(timezone.utc):
        delete_session(session_id, db_path=db_path)
        return None

    # Check user is active
    if not r["is_active"]:
        return None

    return r


def delete_session(session_id: str, *, db_path=None) -> bool:
    """Delete a session. Returns True if a session was deleted."""
    with get_connection(db_path) as conn:
        conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        deleted = conn.execute("SELECT changes()").fetchone()[0]
    return deleted > 0


def delete_user_sessions(user_id: str, *, db_path=None) -> int:
    """Delete all sessions for a user. Returns count deleted."""
    with get_connection(db_path) as conn:
        conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
        count = conn.execute("SELECT changes()").fetchone()[0]
    return count


def cleanup_expired_sessions(*, db_path=None) -> int:
    """Delete all expired sessions. Returns count deleted."""
    now = datetime.now(timezone.utc).isoformat()
    with get_connection(db_path) as conn:
        conn.execute("DELETE FROM sessions WHERE expires_at < ?", (now,))
        count = conn.execute("SELECT changes()").fetchone()[0]
    return count
