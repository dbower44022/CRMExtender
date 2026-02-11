"""Tenant-scoped query helpers for data visibility."""

from __future__ import annotations

import sqlite3


def visible_contacts_query(
    customer_id: str,
    user_id: str,
) -> tuple[str, list]:
    """Return (WHERE clause, params) for contacts visible to a user.

    Visible = any user in the customer has visibility='public' for this contact,
    OR the current user has any user_contacts row for this contact.
    """
    where = (
        "c.customer_id = ? AND ("
        "  EXISTS (SELECT 1 FROM user_contacts uc "
        "          WHERE uc.contact_id = c.id AND uc.visibility = 'public') "
        "  OR EXISTS (SELECT 1 FROM user_contacts uc "
        "             WHERE uc.contact_id = c.id AND uc.user_id = ?)"
        ")"
    )
    return where, [customer_id, user_id]


def my_contacts_query(
    customer_id: str,
    user_id: str,
) -> tuple[str, list]:
    """Return (JOIN + WHERE clause, params) for a user's own contacts."""
    # Caller should JOIN user_contacts uc ON uc.contact_id = c.id
    where = "c.customer_id = ? AND uc.user_id = ?"
    return where, [customer_id, user_id]


def visible_companies_query(
    customer_id: str,
    user_id: str,
) -> tuple[str, list]:
    """Return (WHERE clause, params) for companies visible to a user."""
    where = (
        "co.customer_id = ? AND ("
        "  EXISTS (SELECT 1 FROM user_companies uco "
        "          WHERE uco.company_id = co.id AND uco.visibility = 'public') "
        "  OR EXISTS (SELECT 1 FROM user_companies uco "
        "             WHERE uco.company_id = co.id AND uco.user_id = ?)"
        ")"
    )
    return where, [customer_id, user_id]


def my_companies_query(
    customer_id: str,
    user_id: str,
) -> tuple[str, list]:
    """Return (WHERE clause, params) for a user's own companies."""
    where = "co.customer_id = ? AND uco.user_id = ?"
    return where, [customer_id, user_id]


def visible_conversations_query(
    customer_id: str,
    user_id: str,
) -> tuple[str, list]:
    """Return (WHERE clause, params) for conversations visible to a user.

    Visible = user has access to a provider_account that produced a communication
    in this conversation, OR the conversation was explicitly shared.
    """
    where = (
        "conv.customer_id = ? AND ("
        "  EXISTS ("
        "    SELECT 1 FROM conversation_communications cc "
        "    JOIN communications comm ON comm.id = cc.communication_id "
        "    JOIN user_provider_accounts upa ON upa.account_id = comm.account_id "
        "    WHERE cc.conversation_id = conv.id AND upa.user_id = ?"
        "  ) OR EXISTS ("
        "    SELECT 1 FROM conversation_shares cs "
        "    WHERE cs.conversation_id = conv.id AND cs.user_id = ?"
        "  )"
        ")"
    )
    return where, [customer_id, user_id, user_id]


def get_visible_contacts(
    conn: sqlite3.Connection,
    customer_id: str,
    user_id: str,
) -> list[dict]:
    """Fetch all contacts visible to a user."""
    where, params = visible_contacts_query(customer_id, user_id)
    rows = conn.execute(
        f"SELECT c.* FROM contacts c WHERE {where} ORDER BY c.name",
        params,
    ).fetchall()
    return [dict(r) for r in rows]


def get_my_contacts(
    conn: sqlite3.Connection,
    customer_id: str,
    user_id: str,
) -> list[dict]:
    """Fetch contacts owned/linked to a user."""
    where, params = my_contacts_query(customer_id, user_id)
    rows = conn.execute(
        f"SELECT c.* FROM contacts c "
        f"JOIN user_contacts uc ON uc.contact_id = c.id "
        f"WHERE {where} ORDER BY c.name",
        params,
    ).fetchall()
    return [dict(r) for r in rows]


def get_visible_companies(
    conn: sqlite3.Connection,
    customer_id: str,
    user_id: str,
) -> list[dict]:
    """Fetch all companies visible to a user."""
    where, params = visible_companies_query(customer_id, user_id)
    rows = conn.execute(
        f"SELECT co.* FROM companies co WHERE {where} ORDER BY co.name",
        params,
    ).fetchall()
    return [dict(r) for r in rows]


def get_my_companies(
    conn: sqlite3.Connection,
    customer_id: str,
    user_id: str,
) -> list[dict]:
    """Fetch companies owned/linked to a user."""
    where, params = my_companies_query(customer_id, user_id)
    rows = conn.execute(
        f"SELECT co.* FROM companies co "
        f"JOIN user_companies uco ON uco.company_id = co.id "
        f"WHERE {where} ORDER BY co.name",
        params,
    ).fetchall()
    return [dict(r) for r in rows]


def get_visible_conversations(
    conn: sqlite3.Connection,
    customer_id: str,
    user_id: str,
) -> list[dict]:
    """Fetch all conversations visible to a user."""
    where, params = visible_conversations_query(customer_id, user_id)
    rows = conn.execute(
        f"SELECT conv.* FROM conversations conv WHERE {where} "
        f"ORDER BY conv.last_activity_at DESC",
        params,
    ).fetchall()
    return [dict(r) for r in rows]
