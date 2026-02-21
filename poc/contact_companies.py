"""CRUD for contact_companies — multi-company affiliation junction table."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from .database import get_connection


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def add_affiliation(
    contact_id: str,
    company_id: str,
    *,
    role_id: str | None = None,
    title: str = "",
    department: str = "",
    is_primary: bool = False,
    is_current: bool = True,
    started_at: str = "",
    ended_at: str = "",
    notes: str = "",
    source: str = "manual",
    created_by: str | None = None,
) -> dict:
    """Add an affiliation between a contact and a company.

    Returns the new row as a dict.
    Uses INSERT OR IGNORE to avoid duplicating existing affiliations on re-sync.
    """
    now = _now_iso()
    aff_id = str(uuid.uuid4())
    with get_connection() as conn:
        # If setting as primary, clear other primaries for this contact
        if is_primary:
            conn.execute(
                "UPDATE contact_companies SET is_primary = 0 "
                "WHERE contact_id = ? AND is_primary = 1",
                (contact_id,),
            )

        conn.execute(
            """INSERT OR IGNORE INTO contact_companies
               (id, contact_id, company_id, role_id, title, department,
                is_primary, is_current, started_at, ended_at, notes, source,
                created_by, updated_by, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (aff_id, contact_id, company_id, role_id or None,
             title or None, department or None,
             int(is_primary), int(is_current),
             started_at or None, ended_at or None,
             notes or None, source,
             created_by, created_by, now, now),
        )

        # If the INSERT was ignored (duplicate), find existing row
        row = conn.execute(
            "SELECT * FROM contact_companies WHERE id = ?", (aff_id,)
        ).fetchone()
        if not row:
            # UNIQUE conflict — return existing
            row = conn.execute(
                "SELECT * FROM contact_companies "
                "WHERE contact_id = ? AND company_id = ? AND role_id IS ? AND started_at IS ?",
                (contact_id, company_id, role_id or None, started_at or None),
            ).fetchone()
    return dict(row) if row else {}


def update_affiliation(affiliation_id: str, **fields) -> dict | None:
    """Update an affiliation's fields. Returns updated row dict or None."""
    allowed = {
        "role_id", "title", "department", "is_primary", "is_current",
        "started_at", "ended_at", "notes", "source", "updated_by",
    }
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return None

    now = _now_iso()
    updates["updated_at"] = now

    with get_connection() as conn:
        # If setting as primary, clear other primaries for this contact
        if updates.get("is_primary"):
            existing = conn.execute(
                "SELECT contact_id FROM contact_companies WHERE id = ?",
                (affiliation_id,),
            ).fetchone()
            if existing:
                conn.execute(
                    "UPDATE contact_companies SET is_primary = 0 "
                    "WHERE contact_id = ? AND is_primary = 1 AND id != ?",
                    (existing["contact_id"], affiliation_id),
                )

        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [affiliation_id]
        conn.execute(
            f"UPDATE contact_companies SET {set_clause} WHERE id = ?",
            values,
        )
        row = conn.execute(
            "SELECT * FROM contact_companies WHERE id = ?",
            (affiliation_id,),
        ).fetchone()
    return dict(row) if row else None


def remove_affiliation(affiliation_id: str) -> None:
    """Delete an affiliation by its ID."""
    with get_connection() as conn:
        conn.execute(
            "DELETE FROM contact_companies WHERE id = ?", (affiliation_id,)
        )


def get_affiliation(affiliation_id: str) -> dict | None:
    """Look up an affiliation by ID. Returns dict or None."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM contact_companies WHERE id = ?", (affiliation_id,)
        ).fetchone()
    return dict(row) if row else None


def list_affiliations_for_contact(contact_id: str) -> list[dict]:
    """List all affiliations for a contact, with role name and company name.

    Returns current affiliations first, then historical, each sorted by company name.
    """
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT cc.*, co.name AS company_name,
                      ccr.name AS role_name
               FROM contact_companies cc
               JOIN companies co ON co.id = cc.company_id
               LEFT JOIN contact_company_roles ccr ON ccr.id = cc.role_id
               WHERE cc.contact_id = ?
               ORDER BY cc.is_current DESC, cc.is_primary DESC, co.name COLLATE NOCASE""",
            (contact_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def list_affiliations_for_company(company_id: str) -> list[dict]:
    """List all affiliations for a company, with role name and contact info.

    Returns current affiliations first, then historical.
    """
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT cc.*, c.name AS contact_name,
                      ccr.name AS role_name,
                      ci.value AS email
               FROM contact_companies cc
               JOIN contacts c ON c.id = cc.contact_id
               LEFT JOIN contact_company_roles ccr ON ccr.id = cc.role_id
               LEFT JOIN contact_identifiers ci
                 ON ci.contact_id = c.id AND ci.type = 'email' AND ci.is_primary = 1
               WHERE cc.company_id = ?
               ORDER BY cc.is_current DESC, cc.is_primary DESC, c.name COLLATE NOCASE""",
            (company_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_primary_company(contact_id: str) -> dict | None:
    """Get the primary current company for a contact. Returns dict or None."""
    with get_connection() as conn:
        row = conn.execute(
            """SELECT cc.*, co.name AS company_name
               FROM contact_companies cc
               JOIN companies co ON co.id = cc.company_id
               WHERE cc.contact_id = ? AND cc.is_primary = 1 AND cc.is_current = 1
               LIMIT 1""",
            (contact_id,),
        ).fetchone()
        if row:
            return dict(row)

        # Fallback: any current affiliation
        row = conn.execute(
            """SELECT cc.*, co.name AS company_name
               FROM contact_companies cc
               JOIN companies co ON co.id = cc.company_id
               WHERE cc.contact_id = ? AND cc.is_current = 1
               ORDER BY cc.created_at
               LIMIT 1""",
            (contact_id,),
        ).fetchone()
    return dict(row) if row else None


def set_primary(affiliation_id: str) -> None:
    """Set an affiliation as the primary for its contact.

    Clears is_primary on all other affiliations for the same contact.
    """
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT contact_id FROM contact_companies WHERE id = ?",
            (affiliation_id,),
        ).fetchone()
        if not existing:
            return
        conn.execute(
            "UPDATE contact_companies SET is_primary = 0 "
            "WHERE contact_id = ? AND is_primary = 1",
            (existing["contact_id"],),
        )
        conn.execute(
            "UPDATE contact_companies SET is_primary = 1 WHERE id = ?",
            (affiliation_id,),
        )
