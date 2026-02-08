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
    SUM(cp1.message_count + cp2.message_count) AS shared_messages,
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


def _compute_strength(
    shared_conversations: int,
    shared_messages: int,
    last_interaction: str | None,
    *,
    max_conversations: int = 50,
    max_messages: int = 200,
) -> float:
    """Score relationship strength on a 0.0–1.0 scale.

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


def infer_relationships() -> int:
    """Mine conversation participants for co-occurrence and upsert relationships.

    Returns the number of relationships upserted.
    """
    with get_connection() as conn:
        rows = conn.execute(_CO_OCCURRENCE_SQL).fetchall()

        if not rows:
            log.info("No co-occurring contact pairs found.")
            return 0

        # Determine max values for normalization
        max_convos = max(r["shared_conversations"] for r in rows)
        max_msgs = max(r["shared_messages"] for r in rows)

        count = 0
        for row in rows:
            strength = _compute_strength(
                row["shared_conversations"],
                row["shared_messages"],
                row["last_interaction"],
                max_conversations=max(max_convos, 2),
                max_messages=max(max_msgs, 2),
            )

            rel = Relationship(
                from_contact_id=row["contact_a"],
                to_contact_id=row["contact_b"],
                strength=strength,
                shared_conversations=row["shared_conversations"],
                shared_messages=row["shared_messages"],
                last_interaction=row["last_interaction"],
                first_interaction=row["first_interaction"],
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
        INSERT INTO relationships (id, from_entity_type, from_entity_id,
                                   to_entity_type, to_entity_id,
                                   relationship_type, properties,
                                   created_at, updated_at)
        VALUES (?, 'contact', ?, 'contact', ?, 'KNOWS', ?, ?, ?)
        ON CONFLICT(from_entity_id, to_entity_id, relationship_type) DO UPDATE SET
            properties = excluded.properties,
            updated_at = excluded.updated_at
        """,
        (
            str(uuid.uuid4()),
            rel.from_contact_id,
            rel.to_contact_id,
            properties,
            now,
            now,
        ),
    )


def load_relationships(
    *,
    contact_id: str | None = None,
    min_strength: float = 0.0,
) -> list[Relationship]:
    """Load relationships from the database, optionally filtered."""
    clauses = []
    params: list = []

    if contact_id:
        clauses.append("(from_entity_id = ? OR to_entity_id = ?)")
        params.extend([contact_id, contact_id])

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""

    with get_connection() as conn:
        rows = conn.execute(
            f"SELECT * FROM relationships {where} ORDER BY updated_at DESC",
            params,
        ).fetchall()

    results = []
    for row in rows:
        rel = Relationship.from_row(row)
        if rel.strength >= min_strength:
            results.append(rel)

    results.sort(key=lambda r: r.strength, reverse=True)
    return results
