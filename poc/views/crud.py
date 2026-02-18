"""View CRUD — create, read, update, delete views and data sources."""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone

from .registry import ENTITY_TYPES


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _uuid() -> str:
    return str(uuid.uuid4())


# -----------------------------------------------------------------------
# Data sources
# -----------------------------------------------------------------------

_ENTITY_LABELS = {
    "contact": "Contacts",
    "company": "Companies",
    "conversation": "Conversations",
    "communication": "Communications",
    "event": "Events",
}


def ensure_system_data_sources(conn: sqlite3.Connection, customer_id: str) -> None:
    """Create system data sources for all entity types if missing."""
    now = _now()
    for et, label in _ENTITY_LABELS.items():
        ds_id = f"ds-{et}-{customer_id}"
        conn.execute(
            "INSERT OR IGNORE INTO data_sources "
            "(id, customer_id, entity_type, name, is_system, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, 1, ?, ?)",
            (ds_id, customer_id, et, label, now, now),
        )


def get_data_source(conn: sqlite3.Connection, ds_id: str) -> dict | None:
    row = conn.execute(
        "SELECT * FROM data_sources WHERE id = ?", (ds_id,)
    ).fetchone()
    return dict(row) if row else None


def get_data_sources_for_customer(
    conn: sqlite3.Connection, customer_id: str,
) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM data_sources WHERE customer_id = ? ORDER BY entity_type",
        (customer_id,),
    ).fetchall()
    return [dict(r) for r in rows]


# -----------------------------------------------------------------------
# Default columns per entity type
# -----------------------------------------------------------------------

_DEFAULT_COLUMNS = {
    "contact": ["name", "email", "company_name", "score", "source"],
    "company": ["name", "domain", "industry", "score", "status"],
    "conversation": ["title", "status", "message_count", "last_activity_at"],
    "communication": ["channel", "sender", "subject", "timestamp"],
    "event": ["title", "event_type", "start", "location", "status"],
}

_DEFAULT_SORT = {
    "contact": ("name", "asc"),
    "company": ("name", "asc"),
    "conversation": ("last_activity_at", "desc"),
    "communication": ("timestamp", "desc"),
    "event": ("start", "desc"),
}


# -----------------------------------------------------------------------
# Views
# -----------------------------------------------------------------------

def ensure_default_views(
    conn: sqlite3.Connection, customer_id: str, user_id: str,
) -> None:
    """Create default views per data source if user has none for that source."""
    ensure_system_data_sources(conn, customer_id)
    now = _now()
    sources = conn.execute(
        "SELECT id, entity_type FROM data_sources "
        "WHERE customer_id = ? AND is_system = 1",
        (customer_id,),
    ).fetchall()
    for src in sources:
        ds_id = src["id"]
        et = src["entity_type"]
        existing = conn.execute(
            "SELECT 1 FROM views WHERE data_source_id = ? AND owner_id = ? LIMIT 1",
            (ds_id, user_id),
        ).fetchone()
        if existing:
            continue
        sort_field, sort_dir = _DEFAULT_SORT.get(et, ("created_at", "desc"))
        view_id = _uuid()
        conn.execute(
            "INSERT INTO views "
            "(id, customer_id, data_source_id, name, view_type, owner_id, "
            " visibility, is_default, sort_field, sort_direction, per_page, "
            " created_at, updated_at) "
            "VALUES (?, ?, ?, ?, 'list', ?, 'personal', 1, ?, ?, 50, ?, ?)",
            (view_id, customer_id, ds_id,
             f"All {_ENTITY_LABELS.get(et, et)}",
             user_id, sort_field, sort_dir, now, now),
        )
        for pos, fk in enumerate(_DEFAULT_COLUMNS.get(et, [])):
            conn.execute(
                "INSERT INTO view_columns (id, view_id, field_key, position) "
                "VALUES (?, ?, ?, ?)",
                (_uuid(), view_id, fk, pos),
            )


def get_views_for_entity(
    conn: sqlite3.Connection,
    customer_id: str,
    user_id: str,
    entity_type: str,
) -> list[dict]:
    """Return views for an entity type visible to the user (personal + shared)."""
    rows = conn.execute(
        "SELECT v.*, ds.entity_type "
        "FROM views v JOIN data_sources ds ON ds.id = v.data_source_id "
        "WHERE v.customer_id = ? AND ds.entity_type = ? "
        "AND (v.owner_id = ? OR v.visibility = 'shared') "
        "ORDER BY v.is_default DESC, v.name",
        (customer_id, entity_type, user_id),
    ).fetchall()
    return [dict(r) for r in rows]


def get_all_views_for_user(
    conn: sqlite3.Connection,
    customer_id: str,
    user_id: str,
) -> list[dict]:
    """Return all views visible to the user, grouped by entity type."""
    rows = conn.execute(
        "SELECT v.*, ds.entity_type "
        "FROM views v JOIN data_sources ds ON ds.id = v.data_source_id "
        "WHERE v.customer_id = ? "
        "AND (v.owner_id = ? OR v.visibility = 'shared') "
        "ORDER BY ds.entity_type, v.is_default DESC, v.name",
        (customer_id, user_id),
    ).fetchall()
    return [dict(r) for r in rows]


def get_view(conn: sqlite3.Connection, view_id: str) -> dict | None:
    """Load a view row (no columns/filters)."""
    row = conn.execute(
        "SELECT v.*, ds.entity_type "
        "FROM views v JOIN data_sources ds ON ds.id = v.data_source_id "
        "WHERE v.id = ?",
        (view_id,),
    ).fetchone()
    return dict(row) if row else None


def get_view_with_config(conn: sqlite3.Connection, view_id: str) -> dict | None:
    """Load a view with its columns and filters."""
    view = get_view(conn, view_id)
    if not view:
        return None
    view["columns"] = _get_columns(conn, view_id)
    view["filters"] = _get_filters(conn, view_id)
    return view


def _get_columns(conn: sqlite3.Connection, view_id: str) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM view_columns WHERE view_id = ? ORDER BY position",
        (view_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def _get_filters(conn: sqlite3.Connection, view_id: str) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM view_filters WHERE view_id = ? ORDER BY position",
        (view_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def create_view(
    conn: sqlite3.Connection,
    *,
    customer_id: str,
    user_id: str,
    data_source_id: str,
    name: str,
    columns: list[str] | None = None,
    filters: list[dict] | None = None,
    sort_field: str | None = None,
    sort_direction: str = "asc",
    per_page: int = 50,
) -> str:
    """Create a new view and return its ID."""
    now = _now()
    view_id = _uuid()
    ds = get_data_source(conn, data_source_id)
    if not ds:
        raise ValueError(f"Data source not found: {data_source_id}")
    et = ds["entity_type"]

    if not sort_field:
        sort_field, sort_direction = _DEFAULT_SORT.get(et, ("created_at", "desc"))
    if not columns:
        columns = _DEFAULT_COLUMNS.get(et, [])

    conn.execute(
        "INSERT INTO views "
        "(id, customer_id, data_source_id, name, view_type, owner_id, "
        " visibility, is_default, sort_field, sort_direction, per_page, "
        " created_at, updated_at) "
        "VALUES (?, ?, ?, ?, 'list', ?, 'personal', 0, ?, ?, ?, ?, ?)",
        (view_id, customer_id, data_source_id, name,
         user_id, sort_field, sort_direction, per_page, now, now),
    )
    for pos, fk in enumerate(columns):
        conn.execute(
            "INSERT INTO view_columns (id, view_id, field_key, position) "
            "VALUES (?, ?, ?, ?)",
            (_uuid(), view_id, fk, pos),
        )
    if filters:
        for pos, f in enumerate(filters):
            conn.execute(
                "INSERT INTO view_filters "
                "(id, view_id, field_key, operator, value, position) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (_uuid(), view_id, f["field_key"], f["operator"],
                 f.get("value"), pos),
            )
    return view_id


def update_view(
    conn: sqlite3.Connection, view_id: str, **kwargs,
) -> None:
    """Update view-level fields (name, sort_field, sort_direction, per_page)."""
    allowed = {"name", "sort_field", "sort_direction", "per_page", "visibility"}
    updates = {k: v for k, v in kwargs.items() if k in allowed}
    if not updates:
        return
    updates["updated_at"] = _now()
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    conn.execute(
        f"UPDATE views SET {set_clause} WHERE id = ?",
        list(updates.values()) + [view_id],
    )


def update_view_columns(
    conn: sqlite3.Connection, view_id: str, columns: list[str],
) -> None:
    """Replace all columns for a view."""
    conn.execute("DELETE FROM view_columns WHERE view_id = ?", (view_id,))
    for pos, fk in enumerate(columns):
        conn.execute(
            "INSERT INTO view_columns (id, view_id, field_key, position) "
            "VALUES (?, ?, ?, ?)",
            (_uuid(), view_id, fk, pos),
        )
    conn.execute(
        "UPDATE views SET updated_at = ? WHERE id = ?", (_now(), view_id),
    )


def update_view_filters(
    conn: sqlite3.Connection, view_id: str, filters: list[dict],
) -> None:
    """Replace all filters for a view."""
    conn.execute("DELETE FROM view_filters WHERE view_id = ?", (view_id,))
    for pos, f in enumerate(filters):
        conn.execute(
            "INSERT INTO view_filters "
            "(id, view_id, field_key, operator, value, position) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (_uuid(), view_id, f["field_key"], f["operator"],
             f.get("value"), pos),
        )
    conn.execute(
        "UPDATE views SET updated_at = ? WHERE id = ?", (_now(), view_id),
    )


def delete_view(conn: sqlite3.Connection, view_id: str) -> bool:
    """Delete a view. Returns False if it's a system default."""
    view = get_view(conn, view_id)
    if not view:
        return False
    if view.get("is_default"):
        return False
    conn.execute("DELETE FROM views WHERE id = ?", (view_id,))
    return True


def duplicate_view(
    conn: sqlite3.Connection, view_id: str, new_name: str, owner_id: str,
) -> str | None:
    """Duplicate a view with all columns and filters. Returns new view_id."""
    view = get_view_with_config(conn, view_id)
    if not view:
        return None
    now = _now()
    new_id = _uuid()
    conn.execute(
        "INSERT INTO views "
        "(id, customer_id, data_source_id, name, view_type, owner_id, "
        " visibility, is_default, sort_field, sort_direction, per_page, "
        " created_at, updated_at) "
        "VALUES (?, ?, ?, ?, 'list', ?, 'personal', 0, ?, ?, ?, ?, ?)",
        (new_id, view["customer_id"], view["data_source_id"], new_name,
         owner_id, view["sort_field"], view["sort_direction"],
         view["per_page"], now, now),
    )
    for col in view["columns"]:
        conn.execute(
            "INSERT INTO view_columns (id, view_id, field_key, position, "
            "width_px, label_override) VALUES (?, ?, ?, ?, ?, ?)",
            (_uuid(), new_id, col["field_key"], col["position"],
             col.get("width_px"), col.get("label_override")),
        )
    for flt in view["filters"]:
        conn.execute(
            "INSERT INTO view_filters "
            "(id, view_id, field_key, operator, value, position) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (_uuid(), new_id, flt["field_key"], flt["operator"],
             flt.get("value"), flt["position"]),
        )
    return new_id
