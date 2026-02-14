"""Contact merge preview and execution."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from .database import get_connection


# ---------------------------------------------------------------------------
# Snapshot
# ---------------------------------------------------------------------------

def _snapshot_contact(conn, contact_id: str) -> dict:
    """Build a full JSON-serialisable snapshot of the contact."""
    contact = dict(conn.execute(
        "SELECT * FROM contacts WHERE id = ?", (contact_id,)
    ).fetchone())
    contact["identifiers"] = [
        dict(r) for r in conn.execute(
            "SELECT * FROM contact_identifiers WHERE contact_id = ?", (contact_id,)
        ).fetchall()
    ]
    contact["affiliations"] = [
        dict(r) for r in conn.execute(
            "SELECT * FROM contact_companies WHERE contact_id = ?", (contact_id,)
        ).fetchall()
    ]
    contact["social_profiles"] = [
        dict(r) for r in conn.execute(
            "SELECT * FROM contact_social_profiles WHERE contact_id = ?", (contact_id,)
        ).fetchall()
    ]
    contact["phones"] = [
        dict(r) for r in conn.execute(
            "SELECT * FROM phone_numbers WHERE entity_type='contact' AND entity_id=?",
            (contact_id,),
        ).fetchall()
    ]
    contact["addresses"] = [
        dict(r) for r in conn.execute(
            "SELECT * FROM addresses WHERE entity_type='contact' AND entity_id=?",
            (contact_id,),
        ).fetchall()
    ]
    contact["emails"] = [
        dict(r) for r in conn.execute(
            "SELECT * FROM email_addresses WHERE entity_type='contact' AND entity_id=?",
            (contact_id,),
        ).fetchall()
    ]
    return contact


# ---------------------------------------------------------------------------
# Merge preview
# ---------------------------------------------------------------------------

def get_contact_merge_preview(contact_ids: list[str]) -> dict:
    """Compute what will happen when contacts are merged.

    Returns a dict with contact dicts, per-contact sub-entity counts,
    combined totals, and conflicts for scalar fields.
    """
    if len(contact_ids) < 2:
        raise ValueError("At least two contacts are required for a merge.")
    if len(set(contact_ids)) != len(contact_ids):
        raise ValueError("Duplicate contact IDs are not allowed.")

    with get_connection() as conn:
        contacts = []
        for cid in contact_ids:
            row = conn.execute(
                "SELECT * FROM contacts WHERE id = ?", (cid,)
            ).fetchone()
            if not row:
                raise ValueError(f"Contact not found: {cid}")
            c = dict(row)

            # Per-contact counts
            c["identifier_count"] = conn.execute(
                "SELECT COUNT(*) AS cnt FROM contact_identifiers WHERE contact_id = ?",
                (cid,),
            ).fetchone()["cnt"]
            c["affiliation_count"] = conn.execute(
                "SELECT COUNT(*) AS cnt FROM contact_companies WHERE contact_id = ?",
                (cid,),
            ).fetchone()["cnt"]
            c["conversation_count"] = conn.execute(
                "SELECT COUNT(*) AS cnt FROM conversation_participants WHERE contact_id = ?",
                (cid,),
            ).fetchone()["cnt"]
            c["relationship_count"] = conn.execute(
                """SELECT COUNT(*) AS cnt FROM relationships
                   WHERE (from_entity_type = 'contact' AND from_entity_id = ?)
                      OR (to_entity_type = 'contact' AND to_entity_id = ?)""",
                (cid, cid),
            ).fetchone()["cnt"]
            c["event_count"] = conn.execute(
                """SELECT COUNT(*) AS cnt FROM event_participants
                   WHERE entity_type = 'contact' AND entity_id = ?""",
                (cid,),
            ).fetchone()["cnt"]
            c["phone_count"] = conn.execute(
                "SELECT COUNT(*) AS cnt FROM phone_numbers WHERE entity_type='contact' AND entity_id=?",
                (cid,),
            ).fetchone()["cnt"]
            c["address_count"] = conn.execute(
                "SELECT COUNT(*) AS cnt FROM addresses WHERE entity_type='contact' AND entity_id=?",
                (cid,),
            ).fetchone()["cnt"]
            c["email_count"] = conn.execute(
                "SELECT COUNT(*) AS cnt FROM email_addresses WHERE entity_type='contact' AND entity_id=?",
                (cid,),
            ).fetchone()["cnt"]
            c["social_profile_count"] = conn.execute(
                "SELECT COUNT(*) AS cnt FROM contact_social_profiles WHERE contact_id = ?",
                (cid,),
            ).fetchone()["cnt"]

            # Identifiers for display
            c["identifiers"] = [dict(r) for r in conn.execute(
                "SELECT * FROM contact_identifiers WHERE contact_id = ? ORDER BY is_primary DESC",
                (cid,),
            ).fetchall()]

            # Affiliations for display
            c["affiliations"] = [dict(r) for r in conn.execute(
                """SELECT cc.*, co.name AS company_name, ccr.name AS role_name
                   FROM contact_companies cc
                   JOIN companies co ON co.id = cc.company_id
                   LEFT JOIN contact_company_roles ccr ON ccr.id = cc.role_id
                   WHERE cc.contact_id = ?
                   ORDER BY cc.is_primary DESC""",
                (cid,),
            ).fetchall()]

            contacts.append(c)

        # Conflicts: distinct values for scalar fields
        names = list({c["name"] for c in contacts if c.get("name")})
        sources = list({c["source"] for c in contacts if c.get("source")})

        # Combined identifier count (deduplicated by type+value)
        placeholders = ",".join("?" * len(contact_ids))
        combined_identifiers = conn.execute(
            f"SELECT COUNT(DISTINCT type || '|' || value) AS cnt "
            f"FROM contact_identifiers WHERE contact_id IN ({placeholders})",
            contact_ids,
        ).fetchone()["cnt"]

        # Combined affiliation count (deduplicated by company_id+role_id)
        combined_affiliations = conn.execute(
            f"SELECT COUNT(DISTINCT company_id || '|' || COALESCE(role_id, '')) AS cnt "
            f"FROM contact_companies WHERE contact_id IN ({placeholders})",
            contact_ids,
        ).fetchone()["cnt"]

    # Totals
    totals = {
        "identifiers": sum(c["identifier_count"] for c in contacts),
        "combined_identifiers": combined_identifiers,
        "affiliations": sum(c["affiliation_count"] for c in contacts),
        "combined_affiliations": combined_affiliations,
        "conversations": sum(c["conversation_count"] for c in contacts),
        "relationships": sum(c["relationship_count"] for c in contacts),
        "events": sum(c["event_count"] for c in contacts),
        "phones": sum(c["phone_count"] for c in contacts),
        "addresses": sum(c["address_count"] for c in contacts),
        "emails": sum(c["email_count"] for c in contacts),
        "social_profiles": sum(c["social_profile_count"] for c in contacts),
    }

    return {
        "contacts": contacts,
        "conflicts": {
            "name": names,
            "source": sources,
        },
        "totals": totals,
    }


# ---------------------------------------------------------------------------
# Merge execution
# ---------------------------------------------------------------------------

def merge_contacts(
    surviving_id: str,
    absorbed_ids: list[str],
    *,
    merged_by: str | None = None,
    chosen_name: str | None = None,
    chosen_source: str | None = None,
) -> dict:
    """Merge *absorbed* contacts into *surviving* contact.

    All child entities are reassigned to the surviving contact.  The absorbed
    contacts are deleted.  An audit row is written to ``contact_merges`` for
    each absorbed contact.

    Returns a summary dict with counts and merge IDs.
    """
    if not absorbed_ids:
        raise ValueError("At least one absorbed contact ID is required.")
    if surviving_id in absorbed_ids:
        raise ValueError("Cannot merge a contact with itself.")

    with get_connection() as conn:
        # --- Validate ---
        surviving = conn.execute(
            "SELECT * FROM contacts WHERE id = ?", (surviving_id,)
        ).fetchone()
        if not surviving:
            raise ValueError(f"Surviving contact not found: {surviving_id}")

        for aid in absorbed_ids:
            absorbed = conn.execute(
                "SELECT * FROM contacts WHERE id = ?", (aid,)
            ).fetchone()
            if not absorbed:
                raise ValueError(f"Absorbed contact not found: {aid}")

        now = datetime.now(timezone.utc).isoformat()
        merge_ids = []

        total_identifiers = 0
        total_affiliations = 0
        total_conversations = 0
        total_relationships = 0
        total_events = 0
        total_relationships_deduped = 0

        for absorbed_id in absorbed_ids:
            # --- Snapshot ---
            snapshot = _snapshot_contact(conn, absorbed_id)

            # --- Transfer & dedup contact_identifiers ---
            conn.execute(
                """DELETE FROM contact_identifiers
                   WHERE contact_id = ?
                     AND (type, value) IN (
                         SELECT type, value FROM contact_identifiers
                         WHERE contact_id = ?
                     )""",
                (absorbed_id, surviving_id),
            )
            identifiers_transferred = conn.execute(
                "UPDATE contact_identifiers SET contact_id = ?, is_primary = 0, updated_at = ? WHERE contact_id = ?",
                (surviving_id, now, absorbed_id),
            ).rowcount
            total_identifiers += identifiers_transferred

            # --- Transfer & dedup contact_companies (affiliations) ---
            conn.execute(
                """DELETE FROM contact_companies
                   WHERE contact_id = ?
                     AND (company_id, COALESCE(role_id, ''), COALESCE(started_at, '')) IN (
                         SELECT company_id, COALESCE(role_id, ''), COALESCE(started_at, '')
                         FROM contact_companies WHERE contact_id = ?
                     )""",
                (absorbed_id, surviving_id),
            )
            affiliations_transferred = conn.execute(
                "UPDATE contact_companies SET contact_id = ?, updated_at = ? WHERE contact_id = ?",
                (surviving_id, now, absorbed_id),
            ).rowcount
            total_affiliations += affiliations_transferred

            # --- Transfer & dedup contact_social_profiles ---
            conn.execute(
                """DELETE FROM contact_social_profiles
                   WHERE contact_id = ?
                     AND (platform, profile_url) IN (
                         SELECT platform, profile_url FROM contact_social_profiles
                         WHERE contact_id = ?
                     )""",
                (absorbed_id, surviving_id),
            )
            conn.execute(
                "UPDATE contact_social_profiles SET contact_id = ?, updated_at = ? WHERE contact_id = ?",
                (surviving_id, now, absorbed_id),
            )

            # --- Reassign conversation_participants ---
            # Delete duplicates first (same conversation_id already has surviving)
            conn.execute(
                """DELETE FROM conversation_participants
                   WHERE contact_id = ?
                     AND conversation_id IN (
                         SELECT conversation_id FROM conversation_participants
                         WHERE contact_id = ?
                     )""",
                (absorbed_id, surviving_id),
            )
            conversations_reassigned = conn.execute(
                "UPDATE conversation_participants SET contact_id = ? WHERE contact_id = ?",
                (surviving_id, absorbed_id),
            ).rowcount
            total_conversations += conversations_reassigned

            # --- Reassign communication_participants ---
            conn.execute(
                """DELETE FROM communication_participants
                   WHERE contact_id = ?
                     AND communication_id IN (
                         SELECT communication_id FROM communication_participants
                         WHERE contact_id = ?
                     )""",
                (absorbed_id, surviving_id),
            )
            conn.execute(
                "UPDATE communication_participants SET contact_id = ? WHERE contact_id = ?",
                (surviving_id, absorbed_id),
            )

            # --- Reassign relationships ---
            # Delete from_entity conflicts
            conn.execute(
                """DELETE FROM relationships
                   WHERE id IN (
                       SELECT r_abs.id
                       FROM relationships r_abs
                       JOIN relationships r_surv
                         ON r_surv.from_entity_id = ?
                        AND r_surv.to_entity_id = r_abs.to_entity_id
                        AND r_surv.to_entity_type = r_abs.to_entity_type
                        AND r_surv.relationship_type_id = r_abs.relationship_type_id
                       WHERE r_abs.from_entity_type = 'contact'
                         AND r_abs.from_entity_id = ?
                   )""",
                (surviving_id, absorbed_id),
            )
            # Delete to_entity conflicts
            conn.execute(
                """DELETE FROM relationships
                   WHERE id IN (
                       SELECT r_abs.id
                       FROM relationships r_abs
                       JOIN relationships r_surv
                         ON r_surv.to_entity_id = ?
                        AND r_surv.from_entity_id = r_abs.from_entity_id
                        AND r_surv.from_entity_type = r_abs.from_entity_type
                        AND r_surv.relationship_type_id = r_abs.relationship_type_id
                       WHERE r_abs.to_entity_type = 'contact'
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
                   WHERE from_entity_type = 'contact' AND from_entity_id = ?""",
                (surviving_id, now, absorbed_id),
            ).rowcount
            r2 = conn.execute(
                """UPDATE relationships
                   SET to_entity_id = ?, updated_at = ?
                   WHERE to_entity_type = 'contact' AND to_entity_id = ?""",
                (surviving_id, now, absorbed_id),
            ).rowcount
            relationships_reassigned = r1 + r2
            total_relationships += relationships_reassigned

            # Delete self-referential relationships
            relationships_deduped = conn.execute(
                """SELECT COUNT(*) AS cnt FROM relationships
                   WHERE from_entity_id = to_entity_id
                     AND from_entity_type = 'contact'
                     AND from_entity_id = ?""",
                (surviving_id,),
            ).fetchone()["cnt"]
            if relationships_deduped:
                conn.execute(
                    """DELETE FROM relationships
                       WHERE from_entity_id = to_entity_id
                         AND from_entity_type = 'contact'
                         AND from_entity_id = ?""",
                    (surviving_id,),
                )
            total_relationships_deduped += relationships_deduped

            # --- Reassign event_participants ---
            # Delete duplicates (same event already has surviving)
            conn.execute(
                """DELETE FROM event_participants
                   WHERE entity_type = 'contact' AND entity_id = ?
                     AND event_id IN (
                         SELECT event_id FROM event_participants
                         WHERE entity_type = 'contact' AND entity_id = ?
                     )""",
                (absorbed_id, surviving_id),
            )
            events_reassigned = conn.execute(
                """UPDATE event_participants
                   SET entity_id = ?
                   WHERE entity_type = 'contact' AND entity_id = ?""",
                (surviving_id, absorbed_id),
            ).rowcount
            total_events += events_reassigned

            # --- Transfer entity-agnostic tables ---
            for table in ("phone_numbers", "addresses", "email_addresses"):
                conn.execute(
                    f"UPDATE {table} SET entity_id = ?, updated_at = ? "
                    f"WHERE entity_type = 'contact' AND entity_id = ?",
                    (surviving_id, now, absorbed_id),
                )

            # Dedup phone numbers (keep earliest per number)
            dup_phones = conn.execute(
                """SELECT id, number, created_at,
                          ROW_NUMBER() OVER (PARTITION BY number ORDER BY created_at) AS rn
                   FROM phone_numbers
                   WHERE entity_type = 'contact' AND entity_id = ?""",
                (surviving_id,),
            ).fetchall()
            for row in dup_phones:
                if row["rn"] > 1:
                    conn.execute("DELETE FROM phone_numbers WHERE id = ?", (row["id"],))

            # --- Transfer user_contacts visibility ---
            conn.execute(
                """INSERT OR IGNORE INTO user_contacts
                   (id, user_id, contact_id, visibility, is_owner, created_at, updated_at)
                   SELECT lower(hex(randomblob(4)) || '-' || hex(randomblob(2)) || '-4' ||
                          substr(hex(randomblob(2)),2) || '-' || substr('89ab',abs(random())%4+1,1) ||
                          substr(hex(randomblob(2)),2) || '-' || hex(randomblob(6))),
                          uc.user_id, ?, uc.visibility, uc.is_owner, ?, ?
                   FROM user_contacts uc
                   WHERE uc.contact_id = ?
                     AND uc.user_id NOT IN (
                         SELECT user_id FROM user_contacts WHERE contact_id = ?
                     )""",
                (surviving_id, now, now, absorbed_id, surviving_id),
            )

            # --- Transfer enrichment runs ---
            conn.execute(
                "UPDATE enrichment_runs SET entity_id = ? WHERE entity_type = 'contact' AND entity_id = ?",
                (surviving_id, absorbed_id),
            )

            # --- Delete absorbed entity scores ---
            conn.execute(
                "DELETE FROM entity_scores WHERE entity_type = 'contact' AND entity_id = ?",
                (absorbed_id,),
            )

            # --- Re-point prior contact_merges audit records ---
            conn.execute(
                "UPDATE contact_merges SET surviving_contact_id = ? WHERE surviving_contact_id = ?",
                (surviving_id, absorbed_id),
            )

            # --- Delete absorbed contact ---
            conn.execute("DELETE FROM contacts WHERE id = ?", (absorbed_id,))

            # --- Audit log ---
            merge_id = str(uuid.uuid4())
            merge_ids.append(merge_id)
            conn.execute(
                """INSERT INTO contact_merges
                   (id, surviving_contact_id, absorbed_contact_id,
                    absorbed_contact_snapshot, identifiers_transferred,
                    affiliations_transferred, conversations_reassigned,
                    relationships_reassigned, events_reassigned,
                    relationships_deduplicated, merged_by, merged_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (merge_id, surviving_id, absorbed_id,
                 json.dumps(snapshot), identifiers_transferred,
                 affiliations_transferred, conversations_reassigned,
                 relationships_reassigned, events_reassigned,
                 relationships_deduped, merged_by, now),
            )

        # --- Apply chosen field values on surviving ---
        updates = {}
        if chosen_name:
            updates["name"] = chosen_name
        if chosen_source:
            updates["source"] = chosen_source
        if updates:
            updates["updated_at"] = now
            set_clause = ", ".join(f"{k} = ?" for k in updates)
            vals = list(updates.values()) + [surviving_id]
            conn.execute(
                f"UPDATE contacts SET {set_clause} WHERE id = ?", vals
            )

        # --- Post-merge: create affiliations from email domains ---
        # After identifiers have been merged, resolve each email domain
        # and create missing affiliations so the surviving contact is
        # linked to every company implied by their email addresses.
        from .domain_resolver import extract_domain, is_public_domain, resolve_company_by_domain

        emails = conn.execute(
            "SELECT value FROM contact_identifiers "
            "WHERE contact_id = ? AND type = 'email'",
            (surviving_id,),
        ).fetchall()

        existing_company_ids = {
            r["company_id"] for r in conn.execute(
                "SELECT company_id FROM contact_companies WHERE contact_id = ?",
                (surviving_id,),
            ).fetchall()
        }

        affiliations_created = 0
        for row in emails:
            domain = extract_domain(row["value"])
            if not domain or is_public_domain(domain):
                continue
            company = resolve_company_by_domain(conn, domain)
            if not company or company["id"] in existing_company_ids:
                continue
            conn.execute(
                """INSERT OR IGNORE INTO contact_companies
                   (id, contact_id, company_id, is_primary, is_current,
                    source, created_at, updated_at)
                   VALUES (?, ?, ?, 0, 1, 'merge', ?, ?)""",
                (str(uuid.uuid4()), surviving_id, company["id"], now, now),
            )
            existing_company_ids.add(company["id"])
            affiliations_created += 1

    return {
        "merge_ids": merge_ids,
        "surviving_id": surviving_id,
        "absorbed_ids": absorbed_ids,
        "identifiers_transferred": total_identifiers,
        "affiliations_transferred": total_affiliations,
        "affiliations_created": affiliations_created,
        "conversations_reassigned": total_conversations,
        "relationships_reassigned": total_relationships,
        "events_reassigned": total_events,
        "relationships_deduplicated": total_relationships_deduped,
    }
