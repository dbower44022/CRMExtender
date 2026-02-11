"""Data access for the organizational hierarchy: users, projects, topics."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from .database import get_connection
from .models import Company, CompanyHierarchy, CompanyIdentifier, Project, Topic, User


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

DEFAULT_CUSTOMER_ID = "cust-default"


def _ensure_default_customer(conn) -> str:
    """Ensure the default customer exists. Returns the customer_id."""
    existing = conn.execute(
        "SELECT id FROM customers WHERE id = ?", (DEFAULT_CUSTOMER_ID,)
    ).fetchone()
    if existing:
        return DEFAULT_CUSTOMER_ID
    from .models import Customer
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT INTO customers (id, name, slug, is_active, created_at, updated_at) "
        "VALUES (?, ?, ?, 1, ?, ?)",
        (DEFAULT_CUSTOMER_ID, "Default Organization", "default", now, now),
    )
    return DEFAULT_CUSTOMER_ID


def bootstrap_user() -> dict:
    """Auto-create a user from the first provider_accounts email.

    Idempotent — returns the existing user if one already exists.
    Returns a dict with 'id', 'email', 'name', 'customer_id', 'created' (bool).
    """
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT * FROM users WHERE is_active = 1 ORDER BY created_at LIMIT 1"
        ).fetchone()
        if existing:
            return {"id": existing["id"], "email": existing["email"],
                    "name": existing["name"],
                    "customer_id": existing["customer_id"],
                    "created": False}

        account = conn.execute(
            "SELECT email_address, display_name FROM provider_accounts "
            "ORDER BY created_at LIMIT 1"
        ).fetchone()
        if not account:
            raise ValueError("No provider accounts found. Add an account first.")

        customer_id = _ensure_default_customer(conn)

        user = User(
            email=account["email_address"],
            name=account["display_name"] or "",
            customer_id=customer_id,
            role="admin",
        )
        row = user.to_row()
        conn.execute(
            "INSERT INTO users "
            "(id, customer_id, email, name, role, is_active, "
            "password_hash, google_sub, created_at, updated_at) "
            "VALUES (:id, :customer_id, :email, :name, :role, :is_active, "
            ":password_hash, :google_sub, :created_at, :updated_at)",
            row,
        )
        return {"id": row["id"], "email": row["email"],
                "name": row["name"], "customer_id": row["customer_id"],
                "created": True}


def get_current_user() -> dict | None:
    """Return the first active user row, or None.

    For CLI usage where there's no session context.
    """
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE is_active = 1 ORDER BY created_at LIMIT 1"
        ).fetchone()
    return dict(row) if row else None


# ---------------------------------------------------------------------------
# Companies
# ---------------------------------------------------------------------------

def create_company(
    name: str,
    *,
    domain: str = "",
    industry: str = "",
    description: str = "",
    created_by: str | None = None,
) -> dict:
    """Create a company. Returns the new row as a dict.

    Raises ValueError on duplicate name.
    """
    with get_connection() as conn:
        dup = conn.execute(
            "SELECT id FROM companies WHERE name = ?", (name,)
        ).fetchone()
        if dup:
            raise ValueError(f"Company '{name}' already exists.")

        company = Company(name=name, domain=domain, industry=industry,
                          description=description)
        row = company.to_row(created_by=created_by, updated_by=created_by)
        conn.execute(
            "INSERT INTO companies (id, name, domain, industry, description, "
            "status, created_by, updated_by, created_at, updated_at) "
            "VALUES (:id, :name, :domain, :industry, :description, "
            ":status, :created_by, :updated_by, :created_at, :updated_at)",
            row,
        )

        # Auto-add domain to company_identifiers if it's a non-public domain
        if row.get("domain"):
            d = row["domain"].strip().lower()
            if d:
                from .domain_resolver import ensure_domain_identifier, is_public_domain
                if not is_public_domain(d):
                    ensure_domain_identifier(conn, row["id"], d)

        return row


def list_companies() -> list[dict]:
    """Return all active companies ordered by name."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM companies WHERE status = 'active' ORDER BY name"
        ).fetchall()
    return [dict(r) for r in rows]


def get_company(company_id: str) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM companies WHERE id = ?", (company_id,)
        ).fetchone()
    return dict(row) if row else None


def update_company(company_id: str, **fields) -> dict | None:
    """Update a company's fields. Returns updated row dict or None."""
    allowed = {
        "name", "domain", "industry", "description", "status",
        "website", "stock_symbol", "size_range", "employee_count",
        "founded_year", "revenue_range", "funding_total", "funding_stage",
        "headquarters_location",
    }
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return None
    now = datetime.now(timezone.utc).isoformat()
    updates["updated_at"] = now
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [company_id]
    with get_connection() as conn:
        conn.execute(f"UPDATE companies SET {set_clause} WHERE id = ?", values)
        row = conn.execute(
            "SELECT * FROM companies WHERE id = ?", (company_id,)
        ).fetchone()
    return dict(row) if row else None


def find_company_by_name(name: str) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM companies WHERE name = ? AND status = 'active'", (name,)
        ).fetchone()
    return dict(row) if row else None


def find_company_by_domain(domain: str) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM companies WHERE domain = ? AND status = 'active'",
            (domain,),
        ).fetchone()
        if row:
            return dict(row)

        # Fallback: check company_identifiers
        row = conn.execute(
            "SELECT c.* FROM companies c "
            "JOIN company_identifiers ci ON ci.company_id = c.id "
            "WHERE ci.type = 'domain' AND ci.value = ? AND c.status = 'active'",
            (domain,),
        ).fetchone()
    return dict(row) if row else None


def delete_company(company_id: str) -> dict:
    """Delete a company. Contacts get company_id SET NULL. Returns impact summary."""
    with get_connection() as conn:
        contact_count = conn.execute(
            "SELECT COUNT(*) AS cnt FROM contacts WHERE company_id = ?",
            (company_id,),
        ).fetchone()["cnt"]
        conn.execute("DELETE FROM companies WHERE id = ?", (company_id,))
    return {"contacts_unlinked": contact_count}


# ---------------------------------------------------------------------------
# Company Identifiers
# ---------------------------------------------------------------------------

def add_company_identifier(
    company_id: str,
    type: str,
    value: str,
    *,
    is_primary: bool = False,
    source: str = "",
) -> dict:
    """Add an identifier (domain, etc.) to a company. Returns the new row as a dict."""
    ci = CompanyIdentifier(
        company_id=company_id, type=type, value=value,
        is_primary=is_primary, source=source,
    )
    row = ci.to_row()
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO company_identifiers "
            "(id, company_id, type, value, is_primary, source, created_at, updated_at) "
            "VALUES (:id, :company_id, :type, :value, :is_primary, :source, "
            ":created_at, :updated_at)",
            row,
        )
    return row


def get_company_identifiers(company_id: str) -> list[dict]:
    """List all identifiers for a company."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM company_identifiers WHERE company_id = ? ORDER BY is_primary DESC, type",
            (company_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def find_company_by_identifier(type: str, value: str) -> dict | None:
    """Look up a company by identifier type and value. Returns company dict or None."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT c.* FROM companies c "
            "JOIN company_identifiers ci ON ci.company_id = c.id "
            "WHERE ci.type = ? AND ci.value = ? AND c.status = 'active'",
            (type, value),
        ).fetchone()
    return dict(row) if row else None


def remove_company_identifier(identifier_id: str) -> None:
    """Delete a company identifier by its ID."""
    with get_connection() as conn:
        conn.execute(
            "DELETE FROM company_identifiers WHERE id = ?", (identifier_id,)
        )


# ---------------------------------------------------------------------------
# Company Hierarchy
# ---------------------------------------------------------------------------

def add_company_hierarchy(
    parent_company_id: str,
    child_company_id: str,
    hierarchy_type: str,
    *,
    effective_date: str = "",
    metadata: str = "",
    created_by: str | None = None,
) -> dict:
    """Create a parent/child hierarchy relationship. Returns the new row as a dict."""
    ch = CompanyHierarchy(
        parent_company_id=parent_company_id,
        child_company_id=child_company_id,
        hierarchy_type=hierarchy_type,
        effective_date=effective_date,
        metadata=metadata,
    )
    row = ch.to_row(created_by=created_by, updated_by=created_by)
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO company_hierarchy "
            "(id, parent_company_id, child_company_id, hierarchy_type, "
            "effective_date, end_date, metadata, "
            "created_by, updated_by, created_at, updated_at) "
            "VALUES (:id, :parent_company_id, :child_company_id, :hierarchy_type, "
            ":effective_date, :end_date, :metadata, "
            ":created_by, :updated_by, :created_at, :updated_at)",
            row,
        )
    return row


def get_parent_companies(company_id: str) -> list[dict]:
    """Get parent companies for a given child company."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT ch.*, c.name AS parent_name "
            "FROM company_hierarchy ch "
            "JOIN companies c ON c.id = ch.parent_company_id "
            "WHERE ch.child_company_id = ? "
            "ORDER BY ch.effective_date DESC",
            (company_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_child_companies(company_id: str) -> list[dict]:
    """Get child/subsidiary companies for a given parent company."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT ch.*, c.name AS child_name "
            "FROM company_hierarchy ch "
            "JOIN companies c ON c.id = ch.child_company_id "
            "WHERE ch.parent_company_id = ? "
            "ORDER BY ch.effective_date DESC",
            (company_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def remove_company_hierarchy(hierarchy_id: str) -> None:
    """Delete a company hierarchy relationship by its ID."""
    with get_connection() as conn:
        conn.execute(
            "DELETE FROM company_hierarchy WHERE id = ?", (hierarchy_id,)
        )


# ---------------------------------------------------------------------------
# Contacts
# ---------------------------------------------------------------------------

def update_contact(contact_id: str, **fields) -> dict | None:
    """Update a contact's fields. Returns updated row dict or None."""
    allowed = {"name", "company", "company_id", "source", "status"}
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return None
    now = datetime.now(timezone.utc).isoformat()
    updates["updated_at"] = now
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [contact_id]
    with get_connection() as conn:
        conn.execute(f"UPDATE contacts SET {set_clause} WHERE id = ?", values)
        row = conn.execute(
            "SELECT * FROM contacts WHERE id = ?", (contact_id,)
        ).fetchone()
    return dict(row) if row else None


def add_contact_identifier(
    contact_id: str,
    type: str,
    value: str,
    *,
    label: str = "",
    is_primary: bool = False,
    source: str = "",
) -> dict:
    """Add an identifier to a contact. Returns the new row as a dict."""
    now = datetime.now(timezone.utc).isoformat()
    row = {
        "id": str(uuid.uuid4()),
        "contact_id": contact_id,
        "type": type,
        "value": value,
        "label": label,
        "is_primary": int(is_primary),
        "source": source,
        "created_at": now,
        "updated_at": now,
    }
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO contact_identifiers "
            "(id, contact_id, type, value, label, is_primary, source, created_at, updated_at) "
            "VALUES (:id, :contact_id, :type, :value, :label, :is_primary, :source, "
            ":created_at, :updated_at)",
            row,
        )
    return row


def get_contact_identifiers(contact_id: str) -> list[dict]:
    """List all identifiers for a contact."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM contact_identifiers WHERE contact_id = ? "
            "ORDER BY is_primary DESC, type",
            (contact_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def remove_contact_identifier(identifier_id: str) -> None:
    """Delete a contact identifier by its ID."""
    with get_connection() as conn:
        conn.execute(
            "DELETE FROM contact_identifiers WHERE id = ?", (identifier_id,)
        )


# ---------------------------------------------------------------------------
# Phone Numbers (entity-agnostic)
# ---------------------------------------------------------------------------

def add_phone_number(
    entity_type: str,
    entity_id: str,
    number: str,
    *,
    phone_type: str = "mobile",
) -> dict:
    """Add a phone number. Returns the new row as a dict."""
    now = datetime.now(timezone.utc).isoformat()
    row = {
        "id": str(uuid.uuid4()),
        "entity_type": entity_type,
        "entity_id": entity_id,
        "phone_type": phone_type,
        "number": number,
        "is_primary": 0,
        "source": "",
        "created_at": now,
        "updated_at": now,
    }
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO phone_numbers "
            "(id, entity_type, entity_id, phone_type, number, is_primary, source, "
            "created_at, updated_at) "
            "VALUES (:id, :entity_type, :entity_id, :phone_type, :number, :is_primary, "
            ":source, :created_at, :updated_at)",
            row,
        )
    return row


def get_phone_numbers(entity_type: str, entity_id: str) -> list[dict]:
    """List all phone numbers for an entity."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM phone_numbers WHERE entity_type = ? AND entity_id = ? "
            "ORDER BY is_primary DESC, phone_type",
            (entity_type, entity_id),
        ).fetchall()
    return [dict(r) for r in rows]


def remove_phone_number(phone_id: str) -> None:
    """Delete a phone number by its ID."""
    with get_connection() as conn:
        conn.execute("DELETE FROM phone_numbers WHERE id = ?", (phone_id,))


# ---------------------------------------------------------------------------
# Addresses (entity-agnostic)
# ---------------------------------------------------------------------------

def add_address(
    entity_type: str,
    entity_id: str,
    *,
    address_type: str = "work",
    street: str = "",
    city: str = "",
    state: str = "",
    postal_code: str = "",
    country: str = "",
) -> dict:
    """Add an address. Returns the new row as a dict."""
    now = datetime.now(timezone.utc).isoformat()
    row = {
        "id": str(uuid.uuid4()),
        "entity_type": entity_type,
        "entity_id": entity_id,
        "address_type": address_type,
        "street": street,
        "city": city,
        "state": state,
        "postal_code": postal_code,
        "country": country,
        "is_primary": 0,
        "source": "",
        "created_at": now,
        "updated_at": now,
    }
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO addresses "
            "(id, entity_type, entity_id, address_type, street, city, state, "
            "postal_code, country, is_primary, source, created_at, updated_at) "
            "VALUES (:id, :entity_type, :entity_id, :address_type, :street, :city, "
            ":state, :postal_code, :country, :is_primary, :source, "
            ":created_at, :updated_at)",
            row,
        )
    return row


def get_addresses(entity_type: str, entity_id: str) -> list[dict]:
    """List all addresses for an entity."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM addresses WHERE entity_type = ? AND entity_id = ? "
            "ORDER BY is_primary DESC, address_type",
            (entity_type, entity_id),
        ).fetchall()
    return [dict(r) for r in rows]


def remove_address(address_id: str) -> None:
    """Delete an address by its ID."""
    with get_connection() as conn:
        conn.execute("DELETE FROM addresses WHERE id = ?", (address_id,))


# ---------------------------------------------------------------------------
# Email Addresses (entity-agnostic)
# ---------------------------------------------------------------------------

def add_email_address(
    entity_type: str,
    entity_id: str,
    address: str,
    *,
    email_type: str = "general",
) -> dict:
    """Add an email address. Returns the new row as a dict."""
    now = datetime.now(timezone.utc).isoformat()
    row = {
        "id": str(uuid.uuid4()),
        "entity_type": entity_type,
        "entity_id": entity_id,
        "email_type": email_type,
        "address": address,
        "is_primary": 0,
        "source": "",
        "created_at": now,
        "updated_at": now,
    }
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO email_addresses "
            "(id, entity_type, entity_id, email_type, address, is_primary, source, "
            "created_at, updated_at) "
            "VALUES (:id, :entity_type, :entity_id, :email_type, :address, :is_primary, "
            ":source, :created_at, :updated_at)",
            row,
        )
    return row


def get_email_addresses(entity_type: str, entity_id: str) -> list[dict]:
    """List all email addresses for an entity."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM email_addresses WHERE entity_type = ? AND entity_id = ? "
            "ORDER BY is_primary DESC, email_type",
            (entity_type, entity_id),
        ).fetchall()
    return [dict(r) for r in rows]


def remove_email_address(email_id: str) -> None:
    """Delete an email address by its ID."""
    with get_connection() as conn:
        conn.execute("DELETE FROM email_addresses WHERE id = ?", (email_id,))


# ---------------------------------------------------------------------------
# Company Social Profiles
# ---------------------------------------------------------------------------

def add_company_social_profile(
    company_id: str,
    platform: str,
    profile_url: str,
    *,
    username: str = "",
    source: str = "",
    confidence: float | None = None,
) -> dict:
    """Add or update a social profile for a company. Returns the row as a dict."""
    now = datetime.now(timezone.utc).isoformat()
    row_id = str(uuid.uuid4())
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO company_social_profiles "
            "(id, company_id, platform, profile_url, username, source, confidence, "
            "created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(company_id, platform, profile_url) DO UPDATE SET "
            "username = excluded.username, source = excluded.source, "
            "confidence = excluded.confidence, updated_at = excluded.updated_at",
            (row_id, company_id, platform, profile_url, username, source,
             confidence, now, now),
        )
        row = conn.execute(
            "SELECT * FROM company_social_profiles "
            "WHERE company_id = ? AND platform = ? AND profile_url = ?",
            (company_id, platform, profile_url),
        ).fetchone()
    return dict(row) if row else {}


def get_company_social_profiles(company_id: str) -> list[dict]:
    """List all social profiles for a company."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM company_social_profiles WHERE company_id = ? ORDER BY platform",
            (company_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def remove_company_social_profile(profile_id: str) -> None:
    """Delete a company social profile by its ID."""
    with get_connection() as conn:
        conn.execute(
            "DELETE FROM company_social_profiles WHERE id = ?", (profile_id,)
        )


# ---------------------------------------------------------------------------
# Projects
# ---------------------------------------------------------------------------

def create_project(
    name: str,
    description: str = "",
    parent_name: str | None = None,
    owner_id: str | None = None,
    created_by: str | None = None,
) -> dict:
    """Create a project. Returns the new row as a dict.

    Raises ValueError on duplicate name or nonexistent parent.
    """
    with get_connection() as conn:
        # Check duplicate name
        dup = conn.execute(
            "SELECT id FROM projects WHERE name = ? AND status = 'active'", (name,)
        ).fetchone()
        if dup:
            raise ValueError(f"Project '{name}' already exists.")

        parent_id = None
        if parent_name:
            parent = conn.execute(
                "SELECT id FROM projects WHERE name = ? AND status = 'active'",
                (parent_name,),
            ).fetchone()
            if not parent:
                raise ValueError(f"Parent project '{parent_name}' not found.")
            parent_id = parent["id"]

        proj = Project(name=name, description=description,
                       parent_id=parent_id, owner_id=owner_id)
        row = proj.to_row(created_by=created_by, updated_by=created_by)
        conn.execute(
            "INSERT INTO projects (id, parent_id, name, description, status, "
            "owner_id, created_by, updated_by, created_at, updated_at) "
            "VALUES (:id, :parent_id, :name, :description, :status, "
            ":owner_id, :created_by, :updated_by, :created_at, :updated_at)",
            row,
        )
        return row


def list_projects() -> list[dict]:
    """Return all active projects ordered by name."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM projects WHERE status = 'active' ORDER BY name"
        ).fetchall()
    return [dict(r) for r in rows]


def get_project(project_id: str) -> dict | None:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
    return dict(row) if row else None


def find_project_by_name(name: str) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM projects WHERE name = ? AND status = 'active'", (name,)
        ).fetchone()
    return dict(row) if row else None


def delete_project(project_id: str) -> dict:
    """Delete a project. Returns impact summary.

    CASCADE deletes topics; conversations get topic_id SET NULL.
    """
    with get_connection() as conn:
        # Count impact
        topic_count = conn.execute(
            "SELECT COUNT(*) AS cnt FROM topics WHERE project_id = ?", (project_id,)
        ).fetchone()["cnt"]
        conv_count = conn.execute(
            "SELECT COUNT(*) AS cnt FROM conversations c "
            "JOIN topics t ON c.topic_id = t.id WHERE t.project_id = ?",
            (project_id,),
        ).fetchone()["cnt"]

        # FK CASCADE handles topics; conversations.topic_id ON DELETE SET NULL
        conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))

    return {"topics_removed": topic_count, "conversations_unassigned": conv_count}


# ---------------------------------------------------------------------------
# Topics
# ---------------------------------------------------------------------------

def create_topic(
    project_id: str,
    name: str,
    description: str = "",
    created_by: str | None = None,
) -> dict:
    """Create a topic within a project. Returns the new row as a dict.

    Raises ValueError on duplicate name within the project or nonexistent project.
    """
    with get_connection() as conn:
        proj = conn.execute(
            "SELECT id FROM projects WHERE id = ? AND status = 'active'", (project_id,)
        ).fetchone()
        if not proj:
            raise ValueError(f"Project not found (id={project_id}).")

        dup = conn.execute(
            "SELECT id FROM topics WHERE project_id = ? AND name = ?",
            (project_id, name),
        ).fetchone()
        if dup:
            raise ValueError(f"Topic '{name}' already exists in this project.")

        topic = Topic(project_id=project_id, name=name, description=description)
        row = topic.to_row(created_by=created_by, updated_by=created_by)
        conn.execute(
            "INSERT INTO topics (id, project_id, name, description, source, "
            "created_by, updated_by, created_at, updated_at) "
            "VALUES (:id, :project_id, :name, :description, :source, "
            ":created_by, :updated_by, :created_at, :updated_at)",
            row,
        )
        return row


def list_topics(project_id: str) -> list[dict]:
    """Return all topics in a project ordered by name."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM topics WHERE project_id = ? ORDER BY name", (project_id,)
        ).fetchall()
    return [dict(r) for r in rows]


def get_topic(topic_id: str) -> dict | None:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM topics WHERE id = ?", (topic_id,)).fetchone()
    return dict(row) if row else None


def find_topic_by_name(project_id: str, name: str) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM topics WHERE project_id = ? AND name = ?",
            (project_id, name),
        ).fetchone()
    return dict(row) if row else None


def delete_topic(topic_id: str) -> dict:
    """Delete a topic. Conversations get topic_id SET NULL. Returns impact summary."""
    with get_connection() as conn:
        conv_count = conn.execute(
            "SELECT COUNT(*) AS cnt FROM conversations WHERE topic_id = ?", (topic_id,)
        ).fetchone()["cnt"]
        conn.execute("DELETE FROM topics WHERE id = ?", (topic_id,))
    return {"conversations_unassigned": conv_count}


# ---------------------------------------------------------------------------
# Assignment
# ---------------------------------------------------------------------------

def resolve_conversation_by_prefix(prefix: str) -> str:
    """Resolve a conversation ID prefix to a full ID.

    Raises ValueError if zero or multiple matches.
    """
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id FROM conversations WHERE id LIKE ?", (prefix + "%",)
        ).fetchall()
    if not rows:
        raise ValueError(f"No conversation matching prefix '{prefix}'.")
    if len(rows) > 1:
        raise ValueError(
            f"Ambiguous prefix '{prefix}' — matches {len(rows)} conversations."
        )
    return rows[0]["id"]


def assign_conversation_to_topic(conversation_id: str, topic_id: str) -> None:
    """Assign a conversation to a topic. Validates both exist."""
    with get_connection() as conn:
        conv = conn.execute(
            "SELECT id FROM conversations WHERE id = ?", (conversation_id,)
        ).fetchone()
        if not conv:
            raise ValueError(f"Conversation not found (id={conversation_id}).")

        topic = conn.execute(
            "SELECT id FROM topics WHERE id = ?", (topic_id,)
        ).fetchone()
        if not topic:
            raise ValueError(f"Topic not found (id={topic_id}).")

        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "UPDATE conversations SET topic_id = ?, updated_at = ? WHERE id = ?",
            (topic_id, now, conversation_id),
        )


def unassign_conversation(conversation_id: str) -> None:
    """Clear topic_id on a conversation."""
    with get_connection() as conn:
        conv = conn.execute(
            "SELECT id FROM conversations WHERE id = ?", (conversation_id,)
        ).fetchone()
        if not conv:
            raise ValueError(f"Conversation not found (id={conversation_id}).")

        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "UPDATE conversations SET topic_id = NULL, updated_at = ? WHERE id = ?",
            (now, conversation_id),
        )


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

def get_hierarchy_stats() -> list[dict]:
    """Return projects with topic and conversation counts for tree view.

    Each dict: {id, name, parent_id, description, topic_count, conversation_count}
    """
    with get_connection() as conn:
        rows = conn.execute("""\
            SELECT p.id, p.name, p.parent_id, p.description,
                   COUNT(DISTINCT t.id) AS topic_count,
                   COUNT(DISTINCT c.id) AS conversation_count
            FROM projects p
            LEFT JOIN topics t ON t.project_id = p.id
            LEFT JOIN conversations c ON c.topic_id = t.id
            WHERE p.status = 'active'
            GROUP BY p.id
            ORDER BY p.name
        """).fetchall()
    return [dict(r) for r in rows]


def get_topic_stats(project_id: str) -> list[dict]:
    """Return topics in a project with conversation counts.

    Each dict: {id, name, description, conversation_count}
    """
    with get_connection() as conn:
        rows = conn.execute("""\
            SELECT t.id, t.name, t.description,
                   COUNT(c.id) AS conversation_count
            FROM topics t
            LEFT JOIN conversations c ON c.topic_id = t.id
            WHERE t.project_id = ?
            GROUP BY t.id
            ORDER BY t.name
        """, (project_id,)).fetchall()
    return [dict(r) for r in rows]
