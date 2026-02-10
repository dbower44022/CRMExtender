"""Domain-to-company resolution: match contacts to companies by email domain."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from .database import get_connection

# Common public email providers — contacts with these domains are never
# auto-linked to a company.
PUBLIC_DOMAINS: frozenset[str] = frozenset({
    "gmail.com", "googlemail.com", "yahoo.com", "yahoo.co.uk",
    "hotmail.com", "outlook.com", "live.com", "msn.com", "aol.com",
    "icloud.com", "me.com", "mac.com", "mail.com",
    "protonmail.com", "pm.me", "zoho.com", "yandex.com",
    "gmx.com", "fastmail.com", "tutanota.com", "hey.com",
    "comcast.net", "att.net", "verizon.net", "sbcglobal.net",
    "cox.net", "charter.net", "earthlink.net",
})


def extract_domain(email: str) -> str | None:
    """Extract the domain from an email address, lowercased.

    Returns None if the address has no '@' sign.
    """
    if not email or "@" not in email:
        return None
    parts = email.rsplit("@", 1)
    if len(parts) != 2 or not parts[1]:
        return None
    return parts[1].lower()


def is_public_domain(domain: str) -> bool:
    """Return True if *domain* is a known public email provider."""
    return domain.lower() in PUBLIC_DOMAINS


def resolve_company_by_domain(conn, domain: str) -> dict | None:
    """Look up an active company by domain.

    1. Check ``companies.domain`` directly.
    2. Fallback: check ``company_identifiers`` with ``type='domain'``.

    Returns the company row as a dict, or None.
    """
    domain = domain.lower()

    # Direct match on companies.domain
    row = conn.execute(
        "SELECT * FROM companies WHERE domain = ? AND status = 'active'",
        (domain,),
    ).fetchone()
    if row:
        return dict(row)

    # Fallback: company_identifiers
    row = conn.execute(
        "SELECT c.* FROM companies c "
        "JOIN company_identifiers ci ON ci.company_id = c.id "
        "WHERE ci.type = 'domain' AND ci.value = ? AND c.status = 'active'",
        (domain,),
    ).fetchone()
    if row:
        return dict(row)

    return None


def ensure_domain_identifier(conn, company_id: str, domain: str) -> bool:
    """Add a domain identifier for a company if it doesn't already exist.

    Uses INSERT OR IGNORE so it's safe to call multiple times.
    Returns True if a new row was inserted, False if it already existed.
    """
    now = datetime.now(timezone.utc).isoformat()
    cursor = conn.execute(
        "INSERT OR IGNORE INTO company_identifiers "
        "(id, company_id, type, value, is_primary, source, created_at, updated_at) "
        "VALUES (?, ?, 'domain', ?, 0, 'auto', ?, ?)",
        (str(uuid.uuid4()), company_id, domain.lower(), now, now),
    )
    return cursor.rowcount > 0


def resolve_company_for_email(conn, email: str) -> dict | None:
    """Resolve a company for an email address by its domain.

    Skips public domains. Returns the company dict or None.
    """
    domain = extract_domain(email)
    if not domain:
        return None
    if is_public_domain(domain):
        return None
    return resolve_company_by_domain(conn, domain)


@dataclass
class DomainResolveResult:
    """Statistics from a bulk domain-resolution run."""

    contacts_checked: int = 0
    contacts_linked: int = 0
    contacts_skipped_public: int = 0
    contacts_skipped_no_match: int = 0
    details: list[dict] = field(default_factory=list)


def resolve_unlinked_contacts(*, dry_run: bool = False) -> DomainResolveResult:
    """Bulk backfill: link unlinked contacts to companies by email domain.

    Contacts with ``company_id IS NULL`` are checked against known company
    domains (both ``companies.domain`` and ``company_identifiers``).

    Args:
        dry_run: If True, compute results without writing to the database.

    Returns:
        A :class:`DomainResolveResult` with statistics and per-contact details.
    """
    result = DomainResolveResult()

    with get_connection() as conn:
        rows = conn.execute(
            "SELECT c.id AS contact_id, c.name AS contact_name, ci.value AS email "
            "FROM contacts c "
            "JOIN contact_identifiers ci ON ci.contact_id = c.id AND ci.type = 'email' "
            "WHERE c.company_id IS NULL "
            "ORDER BY c.name",
        ).fetchall()

        result.contacts_checked = len(rows)
        now = datetime.now(timezone.utc).isoformat()

        for row in rows:
            email = row["email"]
            domain = extract_domain(email)
            if not domain:
                result.contacts_skipped_no_match += 1
                continue

            if is_public_domain(domain):
                result.contacts_skipped_public += 1
                continue

            company = resolve_company_by_domain(conn, domain)
            if not company:
                result.contacts_skipped_no_match += 1
                continue

            result.contacts_linked += 1
            result.details.append({
                "contact_id": row["contact_id"],
                "contact_name": row["contact_name"],
                "email": email,
                "company_id": company["id"],
                "company_name": company["name"],
            })

            if not dry_run:
                conn.execute(
                    "UPDATE contacts SET company_id = ?, updated_at = ? WHERE id = ?",
                    (company["id"], now, row["contact_id"]),
                )

    return result
