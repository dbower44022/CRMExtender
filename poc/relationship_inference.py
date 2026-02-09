"""Infer relationships between contacts from conversation co-occurrence."""

from __future__ import annotations

import json
import logging
import math
import uuid
from datetime import datetime, timezone

from .database import get_connection
from .models import Relationship

log = logging.getLogger(__name__)

_CO_OCCURRENCE_SQL = """\
SELECT
    cp1.contact_id  AS contact_a,
    cp2.contact_id  AS contact_b,
    COUNT(DISTINCT cp1.conversation_id) AS shared_conversations,
    SUM(cp1.communication_count + cp2.communication_count) AS shared_messages,
    MAX(cp1.last_seen_at, cp2.last_seen_at) AS last_interaction,
    MIN(cp1.first_seen_at, cp2.first_seen_at) AS first_interaction
FROM conversation_participants cp1
JOIN conversation_participants cp2
    ON cp1.conversation_id = cp2.conversation_id
    AND cp1.contact_id < cp2.contact_id
WHERE cp1.contact_id IS NOT NULL
  AND cp2.contact_id IS NOT NULL
GROUP BY cp1.contact_id, cp2.contact_id
HAVING shared_conversations >= 1
"""

KNOWS_TYPE_ID = "rt-knows"


def _compute_strength(
    shared_conversations: int,
    shared_messages: int,
    last_interaction: str | None,
    *,
    max_conversations: int = 50,
    max_messages: int = 200,
) -> float:
    """Score relationship strength on a 0.0-1.0 scale.

    Formula weights:
    - 40% conversation co-occurrence (log-scaled)
    - 30% shared message volume (log-scaled)
    - 30% recency of last interaction
    """
    conv_score = math.log2(1 + shared_conversations) / math.log2(1 + max_conversations)
    msg_score = math.log2(1 + shared_messages) / math.log2(1 + max_messages)

    recency = _recency_factor(last_interaction)

    return min(1.0, 0.4 * conv_score + 0.3 * msg_score + 0.3 * recency)


def _recency_factor(last_interaction: str | None) -> float:
    """Return 1.0 for very recent interactions, decaying to 0.1 at 365+ days."""
    if not last_interaction:
        return 0.1

    try:
        last_dt = datetime.fromisoformat(last_interaction)
    except (ValueError, TypeError):
        return 0.1

    now = datetime.now(timezone.utc)
    if last_dt.tzinfo is None:
        last_dt = last_dt.replace(tzinfo=timezone.utc)

    days_ago = (now - last_dt).days

    if days_ago <= 30:
        return 1.0
    if days_ago >= 365:
        return 0.1

    # Linear decay from 1.0 at 30 days to 0.1 at 365 days
    return 1.0 - 0.9 * (days_ago - 30) / (365 - 30)


def _build_canonical_map(conn) -> dict[str, str]:
    """Build a mapping from contact_id -> canonical_id for same-name groups.

    Contacts sharing the same name are grouped together.  The canonical ID
    is the one that appears most often in conversation_participants (i.e.
    the most-used email address for that person).
    """
    rows = conn.execute(
        """\
        SELECT c.id, c.name, COALESCE(p.cnt, 0) AS participant_count
        FROM contacts c
        LEFT JOIN (
            SELECT contact_id, COUNT(*) AS cnt
            FROM conversation_participants
            WHERE contact_id IS NOT NULL
            GROUP BY contact_id
        ) p ON p.contact_id = c.id
        WHERE c.name IS NOT NULL AND c.name != ''
        ORDER BY c.name, participant_count DESC
        """
    ).fetchall()

    # Group by lowered name; first row per group is the canonical (most used)
    name_to_canonical: dict[str, str] = {}
    canonical: dict[str, str] = {}
    for row in rows:
        key = row["name"].strip().lower()
        if key not in name_to_canonical:
            name_to_canonical[key] = row["id"]
        canonical[row["id"]] = name_to_canonical[key]

    return canonical


def infer_relationships() -> int:
    """Mine conversation participants for co-occurrence and upsert relationships.

    Contacts with the same name are merged into a single canonical identity
    so that the same real person using multiple email addresses does not
    produce duplicate or self-referencing relationship pairs.

    Returns the number of relationships upserted.
    """
    with get_connection() as conn:
        canonical = _build_canonical_map(conn)

        rows = conn.execute(_CO_OCCURRENCE_SQL).fetchall()

        if not rows:
            log.info("No co-occurring contact pairs found.")
            return 0

        # Aggregate co-occurrence data after mapping to canonical IDs
        merged: dict[tuple[str, str], dict] = {}
        for row in rows:
            cid_a = canonical.get(row["contact_a"], row["contact_a"])
            cid_b = canonical.get(row["contact_b"], row["contact_b"])

            # Skip self-relationships (same person, different emails)
            if cid_a == cid_b:
                continue

            # Normalize ordering
            if cid_a > cid_b:
                cid_a, cid_b = cid_b, cid_a

            key = (cid_a, cid_b)
            if key not in merged:
                merged[key] = {
                    "shared_conversations": 0,
                    "shared_messages": 0,
                    "last_interaction": None,
                    "first_interaction": None,
                }

            entry = merged[key]
            entry["shared_conversations"] += row["shared_conversations"]
            entry["shared_messages"] += row["shared_messages"]

            last = row["last_interaction"]
            if last and (entry["last_interaction"] is None or last > entry["last_interaction"]):
                entry["last_interaction"] = last

            first = row["first_interaction"]
            if first and (entry["first_interaction"] is None or first < entry["first_interaction"]):
                entry["first_interaction"] = first

        if not merged:
            log.info("No relationships after deduplication.")
            return 0

        # Determine max values for normalization
        max_convos = max(e["shared_conversations"] for e in merged.values())
        max_msgs = max(e["shared_messages"] for e in merged.values())

        # Clear only inferred relationships before full rewrite
        conn.execute("DELETE FROM relationships WHERE source = 'inferred'")

        count = 0
        for (cid_a, cid_b), entry in merged.items():
            strength = _compute_strength(
                entry["shared_conversations"],
                entry["shared_messages"],
                entry["last_interaction"],
                max_conversations=max(max_convos, 2),
                max_messages=max(max_msgs, 2),
            )

            rel = Relationship(
                from_entity_id=cid_a,
                to_entity_id=cid_b,
                relationship_type_id=KNOWS_TYPE_ID,
                source="inferred",
                strength=strength,
                shared_conversations=entry["shared_conversations"],
                shared_messages=entry["shared_messages"],
                last_interaction=entry["last_interaction"],
                first_interaction=entry["first_interaction"],
            )

            _upsert_relationship(conn, rel)
            count += 1

        log.info("Upserted %d relationships.", count)
        return count


def _upsert_relationship(conn, rel: Relationship) -> None:
    """Insert or update a relationship row."""
    now = datetime.now(timezone.utc).isoformat()
    properties = json.dumps({
        "strength": rel.strength,
        "shared_conversations": rel.shared_conversations,
        "shared_messages": rel.shared_messages,
        "last_interaction": rel.last_interaction,
        "first_interaction": rel.first_interaction,
    })

    conn.execute(
        """\
        INSERT INTO relationships (id, relationship_type_id, from_entity_type,
                                   from_entity_id, to_entity_type, to_entity_id,
                                   source, properties,
                                   created_at, updated_at)
        VALUES (?, ?, 'contact', ?, 'contact', ?, 'inferred', ?, ?, ?)
        ON CONFLICT(from_entity_id, to_entity_id, relationship_type_id) DO UPDATE SET
            properties = excluded.properties,
            updated_at = excluded.updated_at
        """,
        (
            str(uuid.uuid4()),
            KNOWS_TYPE_ID,
            rel.from_entity_id,
            rel.to_entity_id,
            properties,
            now,
            now,
        ),
    )


def load_relationships(
    *,
    contact_id: str | None = None,
    min_strength: float = 0.0,
    relationship_type_id: str | None = None,
    source: str | None = None,
) -> list[Relationship]:
    """Load relationships from the database, optionally filtered.

    When contact_id is given, the filter matches relationships where
    the canonical ID for that contact appears on either side.
    """
    with get_connection() as conn:
        # Resolve contact_id to its canonical ID
        lookup_id = contact_id
        if contact_id:
            canonical = _build_canonical_map(conn)
            lookup_id = canonical.get(contact_id, contact_id)

        clauses = []
        params: list = []

        if lookup_id:
            clauses.append("(r.from_entity_id = ? OR r.to_entity_id = ?)")
            params.extend([lookup_id, lookup_id])

        if relationship_type_id:
            clauses.append("r.relationship_type_id = ?")
            params.append(relationship_type_id)

        if source:
            clauses.append("r.source = ?")
            params.append(source)

        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""

        rows = conn.execute(
            f"""SELECT r.*, rt.name AS type_name,
                       rt.forward_label, rt.reverse_label
                FROM relationships r
                JOIN relationship_types rt ON rt.id = r.relationship_type_id
                {where}
                ORDER BY r.updated_at DESC""",
            params,
        ).fetchall()

    results = []
    for row in rows:
        rel = Relationship.from_row(row)
        if rel.strength >= min_strength:
            results.append(rel)

    results.sort(key=lambda r: r.strength, reverse=True)
    return results
