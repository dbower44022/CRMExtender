"""Layout override CRUD — per-user, per-view, per-display-tier overrides."""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone

_VALID_TIERS = {"ultra_wide", "spacious", "standard", "constrained", "minimal"}
_VALID_DENSITIES = {"compact", "standard", "comfortable"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _uuid() -> str:
    return str(uuid.uuid4())


def get_layout_overrides(
    conn: sqlite3.Connection, user_id: str, view_id: str,
) -> list[dict]:
    """Return all layout overrides for a user+view (all tiers)."""
    rows = conn.execute(
        "SELECT * FROM user_view_layout_overrides "
        "WHERE user_id = ? AND view_id = ? ORDER BY display_tier",
        (user_id, view_id),
    ).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        d["column_overrides"] = json.loads(d.get("column_overrides") or "{}")
        result.append(d)
    return result


def get_layout_override(
    conn: sqlite3.Connection, user_id: str, view_id: str, display_tier: str,
) -> dict | None:
    """Return a single layout override for a specific tier."""
    row = conn.execute(
        "SELECT * FROM user_view_layout_overrides "
        "WHERE user_id = ? AND view_id = ? AND display_tier = ?",
        (user_id, view_id, display_tier),
    ).fetchone()
    if not row:
        return None
    d = dict(row)
    d["column_overrides"] = json.loads(d.get("column_overrides") or "{}")
    return d


def upsert_layout_override(
    conn: sqlite3.Connection,
    *,
    user_id: str,
    view_id: str,
    display_tier: str,
    splitter_pct: float | None = None,
    density: str | None = None,
    column_overrides: dict | None = None,
) -> dict:
    """Create or update a layout override for a specific tier."""
    if display_tier not in _VALID_TIERS:
        raise ValueError(f"Invalid display_tier: {display_tier}")
    if density is not None and density not in _VALID_DENSITIES:
        raise ValueError(f"Invalid density: {density}")

    now = _now()
    col_json = json.dumps(column_overrides or {})

    existing = conn.execute(
        "SELECT id FROM user_view_layout_overrides "
        "WHERE user_id = ? AND view_id = ? AND display_tier = ?",
        (user_id, view_id, display_tier),
    ).fetchone()

    if existing:
        override_id = existing["id"]
        conn.execute(
            "UPDATE user_view_layout_overrides "
            "SET splitter_pct = ?, density = ?, column_overrides = ?, updated_at = ? "
            "WHERE id = ?",
            (splitter_pct, density, col_json, now, override_id),
        )
    else:
        override_id = _uuid()
        conn.execute(
            "INSERT INTO user_view_layout_overrides "
            "(id, user_id, view_id, display_tier, splitter_pct, density, "
            " column_overrides, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (override_id, user_id, view_id, display_tier,
             splitter_pct, density, col_json, now, now),
        )

    return get_layout_override(conn, user_id, view_id, display_tier)


def delete_layout_override(
    conn: sqlite3.Connection, user_id: str, view_id: str, display_tier: str,
) -> bool:
    """Delete a single tier override. Returns True if deleted."""
    cursor = conn.execute(
        "DELETE FROM user_view_layout_overrides "
        "WHERE user_id = ? AND view_id = ? AND display_tier = ?",
        (user_id, view_id, display_tier),
    )
    return cursor.rowcount > 0


def delete_all_layout_overrides(
    conn: sqlite3.Connection, user_id: str, view_id: str,
) -> int:
    """Delete all overrides for a user+view. Returns count deleted."""
    cursor = conn.execute(
        "DELETE FROM user_view_layout_overrides "
        "WHERE user_id = ? AND view_id = ?",
        (user_id, view_id),
    )
    return cursor.rowcount
