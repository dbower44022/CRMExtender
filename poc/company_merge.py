"""Company duplicate detection, merge preview, and merge execution."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from urllib.parse import urlparse

from .database import get_connection
from .domain_resolver import PUBLIC_DOMAINS

# Two-part country-code TLDs that need special handling when extracting
# the root domain.  "mail.acme.co.uk" → "acme.co.uk", not "co.uk".
_COMPOUND_TLDS = frozenset({
    "co.uk", "org.uk", "ac.uk", "gov.uk",
    "co.jp", "co.kr", "co.nz", "co.za", "co.in",
    "com.au", "com.br", "com.cn", "com.mx", "com.sg", "com.tw",
    "org.au", "net.au",
})


# ---------------------------------------------------------------------------
# Domain normalisation
# ---------------------------------------------------------------------------

def normalize_domain(raw: str | None) -> str:
    """Normalise a domain string to its root form.

    * Strips protocol, path, query, www. prefix
    * Lowercases
    * Extracts root domain (handles compound TLDs like .co.uk)
    * Returns empty string for None / blank / unparseable input
    """
    if not raw:
        return ""
    raw = raw.strip().lower()

    # Strip protocol if present
    if "://" in raw:
        try:
            parsed = urlparse(raw)
            raw = parsed.hostname or ""
        except Exception:
            return ""
    else:
        # Remove path/query even without protocol
        raw = raw.split("/", 1)[0].split("?", 1)[0]

    if not raw:
        return ""

    # Strip www.
    if raw.startswith("www."):
        raw = raw[4:]

    # Extract root domain
    parts = raw.split(".")
    if len(parts) <= 2:
        return raw

    # Check for compound TLD
    last_two = f"{parts[-2]}.{parts[-1]}"
    if last_two in _COMPOUND_TLDS:
        # Keep last 3 segments: "acme.co.uk"
        return ".".join(parts[-3:]) if len(parts) >= 3 else raw

    # Standard TLD: keep last 2 segments
    return ".".join(parts[-2:])


# ---------------------------------------------------------------------------
# Duplicate finding
# ---------------------------------------------------------------------------

def find_duplicates_for_domain(domain: str) -> list[dict]:
    """Find all active companies matching *domain* (normalised).

    Returns an empty list for public domains or when no matches exist.
    """
    norm = normalize_domain(domain)
    if not norm or norm in PUBLIC_DOMAINS:
        return []

    with get_connection() as conn:
        # Companies whose primary domain matches
        rows = conn.execute(
            """SELECT DISTINCT c.*
               FROM companies c
               LEFT JOIN company_identifiers ci
                 ON ci.company_id = c.id AND ci.type = 'domain'
               WHERE c.status = 'active'
                 AND (c.domain = ? OR ci.value = ?)""",
            (norm, norm),
        ).fetchall()

    return [dict(r) for r in rows]


def detect_all_duplicates() -> list[dict]:
    """Scan all companies for domain-based duplicates.

    Returns a list of ``{"domain": str, "companies": [dict, ...]}`` sorted
    by group size (largest first).  Public domains and singleton groups are
    excluded.
    """
    with get_connection() as conn:
        # Collect every domain value (companies.domain + company_identifiers)
        rows = conn.execute(
            """SELECT c.id, c.name, c.domain AS raw_domain, c.industry,
                      ci.value AS ci_domain
               FROM companies c
               LEFT JOIN company_identifiers ci
                 ON ci.company_id = c.id AND ci.type = 'domain'
               WHERE c.status = 'active'"""
        ).fetchall()

    # Map normalised domain → set of company dicts (keyed by id)
    domain_map: dict[str, dict[str, dict]] = {}
    for row in rows:
        rd = dict(row)
        for raw in (rd.get("raw_domain"), rd.get("ci_domain")):
            norm = normalize_domain(raw)
            if not norm or norm in PUBLIC_DOMAINS:
                continue
            domain_map.setdefault(norm, {})[rd["id"]] = {
                "id": rd["id"],
                "name": rd["name"],
                "domain": rd.get("raw_domain") or "",
                "industry": rd.get("industry") or "",
            }

    groups = []
    for domain, company_map in domain_map.items():
        if len(company_map) >= 2:
            groups.append({
                "domain": domain,
                "companies": list(company_map.values()),
            })

    groups.sort(key=lambda g: len(g["companies"]), reverse=True)
    return groups


# ---------------------------------------------------------------------------
# Merge preview
# ---------------------------------------------------------------------------

def get_merge_preview(surviving_id: str, absorbed_id: str) -> dict:
    """Compute what will happen when *absorbed* is merged into *surviving*.

    Returns a dict with both company dicts, entity counts, and duplicate
    relationship info.
    """
    with get_connection() as conn:
        surviving = conn.execute(
            "SELECT * FROM companies WHERE id = ?", (surviving_id,)
        ).fetchone()
        absorbed = conn.execute(
            "SELECT * FROM companies WHERE id = ?", (absorbed_id,)
        ).fetchone()
        if not surviving or not absorbed:
            raise ValueError("Both companies must exist.")

        contacts = conn.execute(
            "SELECT COUNT(*) AS cnt FROM contact_companies WHERE company_id = ?",
            (absorbed_id,),
        ).fetchone()["cnt"]

        relationships = conn.execute(
            """SELECT COUNT(*) AS cnt FROM relationships
               WHERE (from_entity_type = 'company' AND from_entity_id = ?)
                  OR (to_entity_type = 'company' AND to_entity_id = ?)""",
            (absorbed_id, absorbed_id),
        ).fetchone()["cnt"]

        events = conn.execute(
            """SELECT COUNT(*) AS cnt FROM event_participants
               WHERE entity_type = 'company' AND entity_id = ?""",
            (absorbed_id,),
        ).fetchone()["cnt"]

        identifiers = conn.execute(
            "SELECT COUNT(*) AS cnt FROM company_identifiers WHERE company_id = ?",
            (absorbed_id,),
        ).fetchone()["cnt"]

        hierarchy = conn.execute(
            """SELECT COUNT(*) AS cnt FROM company_hierarchy
               WHERE parent_company_id = ? OR child_company_id = ?""",
            (absorbed_id, absorbed_id),
        ).fetchone()["cnt"]

        phones = conn.execute(
            "SELECT COUNT(*) AS cnt FROM phone_numbers WHERE entity_type='company' AND entity_id=?",
            (absorbed_id,),
        ).fetchone()["cnt"]

        addresses = conn.execute(
            "SELECT COUNT(*) AS cnt FROM addresses WHERE entity_type='company' AND entity_id=?",
            (absorbed_id,),
        ).fetchone()["cnt"]

        emails = conn.execute(
            "SELECT COUNT(*) AS cnt FROM email_addresses WHERE entity_type='company' AND entity_id=?",
            (absorbed_id,),
        ).fetchone()["cnt"]

        social_profiles = conn.execute(
            "SELECT COUNT(*) AS cnt FROM company_social_profiles WHERE company_id = ?",
            (absorbed_id,),
        ).fetchone()["cnt"]

        # Identify relationship duplicates: both companies related to same
        # third entity with same relationship type
        dup_rels = conn.execute(
            """SELECT COUNT(*) AS cnt
               FROM relationships r1
               JOIN relationships r2 ON r2.relationship_type_id = r1.relationship_type_id
               WHERE r1.from_entity_id = ?
                 AND r2.from_entity_id = ?
                 AND r1.to_entity_id = r2.to_entity_id
                 AND r1.to_entity_type = r2.to_entity_type""",
            (surviving_id, absorbed_id),
        ).fetchone()["cnt"]

        surviving_dict = dict(surviving)
        absorbed_dict = dict(absorbed)

        # Resolve domain from company_identifiers if not set on the company row
        for d in (surviving_dict, absorbed_dict):
            if not d.get("domain"):
                ident = conn.execute(
                    """SELECT value FROM company_identifiers
                       WHERE company_id = ? AND type = 'domain'
                       ORDER BY is_primary DESC LIMIT 1""",
                    (d["id"],),
                ).fetchone()
                if ident:
                    d["domain"] = ident["value"]

    return {
        "surviving": surviving_dict,
        "absorbed": absorbed_dict,
        "contacts": contacts,
        "relationships": relationships,
        "events": events,
        "identifiers": identifiers,
        "hierarchy": hierarchy,
        "phones": phones,
        "addresses": addresses,
        "emails": emails,
        "social_profiles": social_profiles,
        "duplicate_relationships": dup_rels,
    }


# ---------------------------------------------------------------------------
# Merge execution
# ---------------------------------------------------------------------------

def _snapshot_company(conn, company_id: str) -> dict:
    """Build a full JSON-serialisable snapshot of the company."""
    company = dict(conn.execute(
        "SELECT * FROM companies WHERE id = ?", (company_id,)
    ).fetchone())
    company["identifiers"] = [
        dict(r) for r in conn.execute(
            "SELECT * FROM company_identifiers WHERE company_id = ?", (company_id,)
        ).fetchall()
    ]
    company["hierarchy_parent"] = [
        dict(r) for r in conn.execute(
            "SELECT * FROM company_hierarchy WHERE child_company_id = ?", (company_id,)
        ).fetchall()
    ]
    company["hierarchy_child"] = [
        dict(r) for r in conn.execute(
            "SELECT * FROM company_hierarchy WHERE parent_company_id = ?", (company_id,)
        ).fetchall()
    ]
    company["phones"] = [
        dict(r) for r in conn.execute(
            "SELECT * FROM phone_numbers WHERE entity_type='company' AND entity_id=?",
            (company_id,),
        ).fetchall()
    ]
    company["addresses"] = [
        dict(r) for r in conn.execute(
            "SELECT * FROM addresses WHERE entity_type='company' AND entity_id=?",
            (company_id,),
        ).fetchall()
    ]
    company["emails"] = [
        dict(r) for r in conn.execute(
            "SELECT * FROM email_addresses WHERE entity_type='company' AND entity_id=?",
            (company_id,),
        ).fetchall()
    ]
    company["social_profiles"] = [
        dict(r) for r in conn.execute(
            "SELECT * FROM company_social_profiles WHERE company_id = ?", (company_id,)
        ).fetchall()
    ]
    return company


# Nullable company fields eligible for backfill
_BACKFILL_FIELDS = [
    "domain", "industry", "description", "website", "stock_symbol",
    "size_range", "employee_count", "founded_year", "revenue_range",
    "funding_total", "funding_stage", "headquarters_location",
]


def merge_companies(
    surviving_id: str,
    absorbed_id: str,
    *,
    merged_by: str | None = None,
) -> dict:
    """Merge *absorbed* company into *surviving* company.

    All child entities (contacts, relationships, events, identifiers, etc.)
    are reassigned to the surviving company.  The absorbed company is then
    deleted.  An audit row is written to ``company_merges``.

    Returns a summary dict with counts and the merge ID.
    """
    with get_connection() as conn:
        # --- Validate ---
        surviving = conn.execute(
            "SELECT * FROM companies WHERE id = ? AND status = 'active'",
            (surviving_id,),
        ).fetchone()
        absorbed = conn.execute(
            "SELECT * FROM companies WHERE id = ? AND status = 'active'",
            (absorbed_id,),
        ).fetchone()
        if not surviving:
            raise ValueError(f"Surviving company not found: {surviving_id}")
        if not absorbed:
            raise ValueError(f"Absorbed company not found: {absorbed_id}")
        if surviving_id == absorbed_id:
            raise ValueError("Cannot merge a company with itself.")

        # --- Snapshot ---
        snapshot = _snapshot_company(conn, absorbed_id)

        now = datetime.now(timezone.utc).isoformat()

        # --- Reassign contact affiliations ---
        # Delete absorbed affiliations that would conflict (same contact+company+role+started_at)
        conn.execute(
            """DELETE FROM contact_companies
               WHERE company_id = ?
                 AND (contact_id, role_id, started_at) IN (
                     SELECT contact_id, role_id, started_at
                     FROM contact_companies WHERE company_id = ?
                 )""",
            (absorbed_id, surviving_id),
        )
        cur = conn.execute(
            "UPDATE contact_companies SET company_id = ?, updated_at = ? WHERE company_id = ?",
            (surviving_id, now, absorbed_id),
        )
        contacts_reassigned = cur.rowcount

        # --- Reassign relationships ---
        # First, delete absorbed relationships that would create UNIQUE
        # constraint violations (same from_entity_id, to_entity_id,
        # relationship_type_id triple already exists on surviving).
        # Handle from_entity_id reassignment conflicts:
        conn.execute(
            """DELETE FROM relationships
               WHERE id IN (
                   SELECT r_abs.id
                   FROM relationships r_abs
                   JOIN relationships r_surv
                     ON r_surv.from_entity_id = ?
                    AND r_surv.to_entity_id = r_abs.to_entity_id
                    AND r_surv.relationship_type_id = r_abs.relationship_type_id
                   WHERE r_abs.from_entity_type = 'company'
                     AND r_abs.from_entity_id = ?
               )""",
            (surviving_id, absorbed_id),
        )
        # Handle to_entity_id reassignment conflicts:
        conn.execute(
            """DELETE FROM relationships
               WHERE id IN (
                   SELECT r_abs.id
                   FROM relationships r_abs
                   JOIN relationships r_surv
                     ON r_surv.to_entity_id = ?
                    AND r_surv.from_entity_id = r_abs.from_entity_id
                    AND r_surv.relationship_type_id = r_abs.relationship_type_id
                   WHERE r_abs.to_entity_type = 'company'
                     AND r_abs.to_entity_id = ?
               )""",
            (surviving_id, absorbed_id),
        )
        # Fix paired_relationship_id pointers for deleted rows
        conn.execute(
            """UPDATE relationships SET paired_relationship_id = NULL
               WHERE paired_relationship_id NOT IN (SELECT id FROM relationships)
                 AND paired_relationship_id IS NOT NULL"""
        )

        r1 = conn.execute(
            """UPDATE relationships
               SET from_entity_id = ?, updated_at = ?
               WHERE from_entity_type = 'company' AND from_entity_id = ?""",
            (surviving_id, now, absorbed_id),
        ).rowcount
        r2 = conn.execute(
            """UPDATE relationships
               SET to_entity_id = ?, updated_at = ?
               WHERE to_entity_type = 'company' AND to_entity_id = ?""",
            (surviving_id, now, absorbed_id),
        ).rowcount
        relationships_reassigned = r1 + r2

        # --- Reassign event participants ---
        events_reassigned = conn.execute(
            """UPDATE event_participants
               SET entity_id = ?
               WHERE entity_type = 'company' AND entity_id = ?""",
            (surviving_id, absorbed_id),
        ).rowcount

        # --- Reassign entity-agnostic tables ---
        for table in ("phone_numbers", "addresses", "email_addresses"):
            conn.execute(
                f"UPDATE {table} SET entity_id = ?, updated_at = ? "
                f"WHERE entity_type = 'company' AND entity_id = ?",
                (surviving_id, now, absorbed_id),
            )

        # --- Dedup phone numbers after merge (keep earliest per number) ---
        dup_phones = conn.execute(
            """SELECT id, number, created_at,
                      ROW_NUMBER() OVER (PARTITION BY number ORDER BY created_at) AS rn
               FROM phone_numbers
               WHERE entity_type = 'company' AND entity_id = ?""",
            (surviving_id,),
        ).fetchall()
        for row in dup_phones:
            if row["rn"] > 1:
                conn.execute("DELETE FROM phone_numbers WHERE id = ?", (row["id"],))

        # --- Delete absorbed entity scores (will be recomputed) ---
        conn.execute(
            "DELETE FROM entity_scores WHERE entity_type = 'company' AND entity_id = ?",
            (absorbed_id,),
        )

        # --- Transfer enrichment runs ---
        conn.execute(
            "UPDATE enrichment_runs SET entity_id = ? WHERE entity_type = 'company' AND entity_id = ?",
            (surviving_id, absorbed_id),
        )

        # --- Transfer identifiers ---
        # First delete absorbed identifiers that would conflict (same type+value
        # already exists on surviving), then UPDATE the rest to surviving.
        conn.execute(
            """DELETE FROM company_identifiers
               WHERE company_id = ?
                 AND (type, value) IN (
                     SELECT type, value FROM company_identifiers
                     WHERE company_id = ?
                 )""",
            (absorbed_id, surviving_id),
        )
        conn.execute(
            """UPDATE company_identifiers SET company_id = ?, is_primary = 0, updated_at = ?
               WHERE company_id = ?""",
            (surviving_id, now, absorbed_id),
        )

        # --- Transfer hierarchy (skip self-referential) ---
        conn.execute(
            """UPDATE company_hierarchy SET parent_company_id = ?
               WHERE parent_company_id = ? AND child_company_id != ?""",
            (surviving_id, absorbed_id, surviving_id),
        )
        conn.execute(
            """UPDATE company_hierarchy SET child_company_id = ?
               WHERE child_company_id = ? AND parent_company_id != ?""",
            (surviving_id, absorbed_id, surviving_id),
        )
        # Remove any now-self-referential rows
        conn.execute(
            "DELETE FROM company_hierarchy WHERE parent_company_id = child_company_id"
        )

        # --- Count deduplicated relationships ---
        # Deduplication was done before reassignment above; also clean up
        # any remaining self-referential relationships.
        relationships_deduplicated = conn.execute(
            """SELECT COUNT(*) AS cnt FROM relationships
               WHERE from_entity_id = to_entity_id
                 AND from_entity_type = 'company'
                 AND from_entity_id = ?""",
            (surviving_id,),
        ).fetchone()["cnt"]
        if relationships_deduplicated:
            conn.execute(
                """DELETE FROM relationships
                   WHERE from_entity_id = to_entity_id
                     AND from_entity_type = 'company'
                     AND from_entity_id = ?""",
                (surviving_id,),
            )

        # --- Backfill empty fields ---
        surviving_row = dict(conn.execute(
            "SELECT * FROM companies WHERE id = ?", (surviving_id,)
        ).fetchone())
        absorbed_row = dict(absorbed)

        backfill_updates = {}
        for field in _BACKFILL_FIELDS:
            if not surviving_row.get(field) and absorbed_row.get(field):
                backfill_updates[field] = absorbed_row[field]

        if backfill_updates:
            backfill_updates["updated_at"] = now
            set_clause = ", ".join(f"{k} = ?" for k in backfill_updates)
            vals = list(backfill_updates.values()) + [surviving_id]
            conn.execute(
                f"UPDATE companies SET {set_clause} WHERE id = ?", vals
            )

        # --- Transfer social profiles ---
        # Delete absorbed profiles that would conflict with surviving
        conn.execute(
            """DELETE FROM company_social_profiles
               WHERE company_id = ?
                 AND (platform, profile_url) IN (
                     SELECT platform, profile_url FROM company_social_profiles
                     WHERE company_id = ?
                 )""",
            (absorbed_id, surviving_id),
        )
        conn.execute(
            """UPDATE company_social_profiles SET company_id = ?, updated_at = ?
               WHERE company_id = ?""",
            (surviving_id, now, absorbed_id),
        )

        # --- Transfer user_companies visibility rows ---
        # Insert visibility for surviving where absorbed had it but surviving didn't
        conn.execute(
            """INSERT OR IGNORE INTO user_companies (id, user_id, company_id, visibility, is_owner, created_at, updated_at)
               SELECT lower(hex(randomblob(4)) || '-' || hex(randomblob(2)) || '-4' ||
                      substr(hex(randomblob(2)),2) || '-' || substr('89ab',abs(random())%4+1,1) ||
                      substr(hex(randomblob(2)),2) || '-' || hex(randomblob(6))),
                      uc.user_id, ?, uc.visibility, uc.is_owner, ?, ?
               FROM user_companies uc
               WHERE uc.company_id = ?
                 AND uc.user_id NOT IN (
                     SELECT user_id FROM user_companies WHERE company_id = ?
                 )""",
            (surviving_id, now, now, absorbed_id, surviving_id),
        )

        # --- Re-point prior merge audit records ---
        # If the absorbed company was the surviving company of earlier merges,
        # update those records to reference the new surviving company so the
        # FK constraint (NO ACTION) does not block the DELETE.
        conn.execute(
            "UPDATE company_merges SET surviving_company_id = ? WHERE surviving_company_id = ?",
            (surviving_id, absorbed_id),
        )

        # --- Delete absorbed company ---
        conn.execute("DELETE FROM companies WHERE id = ?", (absorbed_id,))

        # --- Audit log ---
        merge_id = str(uuid.uuid4())
        conn.execute(
            """INSERT INTO company_merges
               (id, surviving_company_id, absorbed_company_id,
                absorbed_company_snapshot, contacts_reassigned,
                relationships_reassigned, events_reassigned,
                relationships_deduplicated, merged_by, merged_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (merge_id, surviving_id, absorbed_id,
             json.dumps(snapshot), contacts_reassigned,
             relationships_reassigned, events_reassigned,
             relationships_deduplicated, merged_by, now),
        )

    return {
        "merge_id": merge_id,
        "surviving_id": surviving_id,
        "absorbed_id": absorbed_id,
        "contacts_reassigned": contacts_reassigned,
        "relationships_reassigned": relationships_reassigned,
        "events_reassigned": events_reassigned,
        "relationships_deduplicated": relationships_deduplicated,
    }
