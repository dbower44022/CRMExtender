"""CRUD operations for relationship type definitions."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from .database import get_connection
from .models import RelationshipType


def create_relationship_type(
    name: str,
    from_entity_type: str = "contact",
    to_entity_type: str = "contact",
    forward_label: str = "",
    reverse_label: str = "",
    *,
    is_bidirectional: bool = False,
    description: str = "",
    created_by: str | None = None,
) -> dict:
    """Create a relationship type. Returns the new row as a dict.

    Raises ValueError on duplicate name or invalid entity types.
    """
    if from_entity_type not in ("contact", "company"):
        raise ValueError(f"Invalid from_entity_type: {from_entity_type}")
    if to_entity_type not in ("contact", "company"):
        raise ValueError(f"Invalid to_entity_type: {to_entity_type}")

    with get_connection() as conn:
        dup = conn.execute(
            "SELECT id FROM relationship_types WHERE name = ?", (name,)
        ).fetchone()
        if dup:
            raise ValueError(f"Relationship type '{name}' already exists.")

        rt = RelationshipType(
            name=name,
            from_entity_type=from_entity_type,
            to_entity_type=to_entity_type,
            forward_label=forward_label,
            reverse_label=reverse_label,
            is_bidirectional=is_bidirectional,
            description=description,
        )
        row = rt.to_row(created_by=created_by, updated_by=created_by)
        conn.execute(
            "INSERT INTO relationship_types "
            "(id, name, from_entity_type, to_entity_type, forward_label, "
            "reverse_label, is_system, is_bidirectional, description, "
            "created_by, updated_by, created_at, updated_at) "
            "VALUES (:id, :name, :from_entity_type, :to_entity_type, "
            ":forward_label, :reverse_label, :is_system, :is_bidirectional, "
            ":description, :created_by, :updated_by, :created_at, :updated_at)",
            row,
        )
        return row


def list_relationship_types(
    *,
    from_entity_type: str | None = None,
    to_entity_type: str | None = None,
    customer_id: str | None = None,
) -> list[dict]:
    """Return relationship types, optionally filtered by entity types.

    When *customer_id* is given, returns types belonging to that customer
    plus system types (``customer_id IS NULL``).
    """
    clauses = []
    params: list = []

    if from_entity_type:
        clauses.append("from_entity_type = ?")
        params.append(from_entity_type)
    if to_entity_type:
        clauses.append("to_entity_type = ?")
        params.append(to_entity_type)
    if customer_id:
        clauses.append("(customer_id = ? OR customer_id IS NULL)")
        params.append(customer_id)

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""

    with get_connection() as conn:
        rows = conn.execute(
            f"SELECT * FROM relationship_types {where} ORDER BY name",
            params,
        ).fetchall()
    return [dict(r) for r in rows]


def get_relationship_type(type_id: str) -> dict | None:
    """Get a relationship type by ID."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM relationship_types WHERE id = ?", (type_id,)
        ).fetchone()
    return dict(row) if row else None


def get_relationship_type_by_name(name: str) -> dict | None:
    """Get a relationship type by name."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM relationship_types WHERE name = ?", (name,)
        ).fetchone()
    return dict(row) if row else None


def update_relationship_type(
    type_id: str,
    *,
    forward_label: str | None = None,
    reverse_label: str | None = None,
    description: str | None = None,
    updated_by: str | None = None,
) -> dict | None:
    """Update a relationship type. Returns updated row or None if not found."""
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT * FROM relationship_types WHERE id = ?", (type_id,)
        ).fetchone()
        if not existing:
            return None

        now = datetime.now(timezone.utc).isoformat()
        updates = {"updated_at": now}
        if updated_by is not None:
            updates["updated_by"] = updated_by
        if forward_label is not None:
            updates["forward_label"] = forward_label
        if reverse_label is not None:
            updates["reverse_label"] = reverse_label
        if description is not None:
            updates["description"] = description

        set_clause = ", ".join(f"{k} = ?" for k in updates)
        params = list(updates.values()) + [type_id]
        conn.execute(
            f"UPDATE relationship_types SET {set_clause} WHERE id = ?",
            params,
        )

        row = conn.execute(
            "SELECT * FROM relationship_types WHERE id = ?", (type_id,)
        ).fetchone()
        return dict(row) if row else None


def delete_relationship_type(type_id: str) -> None:
    """Delete a relationship type.

    Raises ValueError if the type is a system type or is currently in use.
    """
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM relationship_types WHERE id = ?", (type_id,)
        ).fetchone()
        if not row:
            raise ValueError("Relationship type not found.")

        if row["is_system"]:
            raise ValueError(
                f"Cannot delete system relationship type '{row['name']}'."
            )

        in_use = conn.execute(
            "SELECT COUNT(*) AS cnt FROM relationships WHERE relationship_type_id = ?",
            (type_id,),
        ).fetchone()["cnt"]
        if in_use:
            raise ValueError(
                f"Cannot delete relationship type '{row['name']}' — "
                f"{in_use} relationship(s) still reference it."
            )

        conn.execute("DELETE FROM relationship_types WHERE id = ?", (type_id,))
