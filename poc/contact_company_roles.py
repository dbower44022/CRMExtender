"""CRUD for contact_company_roles — user-editable affiliation role types."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from .database import get_connection


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_role(
    name: str,
    *,
    customer_id: str,
    sort_order: int = 0,
    created_by: str | None = None,
) -> dict:
    """Create a new affiliation role. Returns the new row as a dict.

    Raises ValueError on duplicate name within the customer.
    """
    now = _now_iso()
    role_id = str(uuid.uuid4())
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT id FROM contact_company_roles "
            "WHERE customer_id = ? AND name = ?",
            (customer_id, name),
        ).fetchone()
        if existing:
            raise ValueError(f"Role '{name}' already exists.")

        conn.execute(
            "INSERT INTO contact_company_roles "
            "(id, customer_id, name, sort_order, is_system, "
            "created_by, updated_by, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, 0, ?, ?, ?, ?)",
            (role_id, customer_id, name, sort_order,
             created_by, created_by, now, now),
        )
        row = conn.execute(
            "SELECT * FROM contact_company_roles WHERE id = ?", (role_id,)
        ).fetchone()
    return dict(row)


def list_roles(*, customer_id: str) -> list[dict]:
    """Return all roles for a customer, ordered by sort_order then name."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM contact_company_roles "
            "WHERE customer_id = ? ORDER BY sort_order, name",
            (customer_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_role(role_id: str) -> dict | None:
    """Look up a role by ID. Returns dict or None."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM contact_company_roles WHERE id = ?", (role_id,)
        ).fetchone()
    return dict(row) if row else None


def get_role_by_name(name: str, *, customer_id: str) -> dict | None:
    """Look up a role by name within a customer. Returns dict or None."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM contact_company_roles "
            "WHERE customer_id = ? AND name = ?",
            (customer_id, name),
        ).fetchone()
    return dict(row) if row else None


def update_role(
    role_id: str,
    *,
    name: str | None = None,
    sort_order: int | None = None,
    updated_by: str | None = None,
) -> dict | None:
    """Update a role's name and/or sort_order. Returns updated row or None.

    Raises ValueError if the role is a system role.
    """
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT * FROM contact_company_roles WHERE id = ?", (role_id,)
        ).fetchone()
        if not existing:
            return None
        if existing["is_system"]:
            raise ValueError("Cannot modify a system role.")

        updates: dict = {}
        if name is not None:
            updates["name"] = name
        if sort_order is not None:
            updates["sort_order"] = sort_order
        if not updates:
            return dict(existing)

        now = _now_iso()
        updates["updated_at"] = now
        if updated_by:
            updates["updated_by"] = updated_by

        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [role_id]
        conn.execute(
            f"UPDATE contact_company_roles SET {set_clause} WHERE id = ?",
            values,
        )
        row = conn.execute(
            "SELECT * FROM contact_company_roles WHERE id = ?", (role_id,)
        ).fetchone()
    return dict(row) if row else None


def delete_role(role_id: str) -> None:
    """Delete a role. Raises ValueError if it's a system role or in use."""
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT * FROM contact_company_roles WHERE id = ?", (role_id,)
        ).fetchone()
        if not existing:
            raise ValueError("Role not found.")
        if existing["is_system"]:
            raise ValueError("Cannot delete a system role.")

        in_use = conn.execute(
            "SELECT COUNT(*) AS cnt FROM contact_companies WHERE role_id = ?",
            (role_id,),
        ).fetchone()["cnt"]
        if in_use:
            raise ValueError(
                f"Cannot delete: role is used by {in_use} affiliation(s)."
            )

        conn.execute(
            "DELETE FROM contact_company_roles WHERE id = ?", (role_id,)
        )
