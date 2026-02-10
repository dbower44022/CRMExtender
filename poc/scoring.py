"""Relationship strength scoring — 5-factor composite score per entity.

Factors (each 0.0–1.0, weighted sum → final score):
  - recency:     linear decay from last communication (1.0 at day 0, 0.0 at 365+)
  - frequency:   direction-weighted comm count over 90 days, log-scaled
  - reciprocity: balance between outbound and inbound (1.0 = balanced)
  - breadth:     distinct contacts (company) or conversations (contact), log-scaled
  - duration:    span from first to last communication, capped at 2 years
"""

from __future__ import annotations

import json
import logging
import math
from datetime import datetime, timezone
from typing import Any

from .database import get_connection

log = logging.getLogger(__name__)

SCORE_TYPE = "relationship_strength"

DEFAULT_WEIGHTS: dict[str, float] = {
    "recency": 0.35,
    "frequency": 0.25,
    "reciprocity": 0.20,
    "breadth": 0.12,
    "duration": 0.08,
}

# Direction multipliers for frequency scoring
OUTBOUND_WEIGHT = 1.0
INBOUND_WEIGHT = 0.6

# Normalization caps (log-scaled, not global-max)
FREQUENCY_CAP = 200
BREADTH_CAP = 15
DURATION_CAP_DAYS = 730
FREQUENCY_WINDOW_DAYS = 90
RECENCY_WINDOW_DAYS = 365


# ---------------------------------------------------------------------------
# Factor functions (each returns 0.0–1.0)
# ---------------------------------------------------------------------------

def _recency_score(days_since_last: float | None) -> float:
    """Linear decay: 1.0 at day 0, 0.0 at RECENCY_WINDOW_DAYS+."""
    if days_since_last is None:
        return 0.0
    if days_since_last <= 0:
        return 1.0
    if days_since_last >= RECENCY_WINDOW_DAYS:
        return 0.0
    return 1.0 - (days_since_last / RECENCY_WINDOW_DAYS)


def _frequency_score(recent_outbound: int, recent_inbound: int) -> float:
    """Direction-weighted count, log-scaled against FREQUENCY_CAP."""
    weighted = recent_outbound * OUTBOUND_WEIGHT + recent_inbound * INBOUND_WEIGHT
    if weighted <= 0:
        return 0.0
    return min(1.0, math.log1p(weighted) / math.log1p(FREQUENCY_CAP))


def _reciprocity_score(outbound_count: int, inbound_count: int) -> float:
    """Balanced = 1.0, completely one-sided = 0.0."""
    total = outbound_count + inbound_count
    if total == 0:
        return 0.0
    ratio = outbound_count / total
    return 1.0 - abs(ratio - 0.5) * 2


def _breadth_score(distinct_count: int) -> float:
    """Log-scaled distinct contacts (company) or conversations (contact)."""
    if distinct_count <= 0:
        return 0.0
    return min(1.0, math.log1p(distinct_count) / math.log1p(BREADTH_CAP))


def _duration_score(first_ts: str | None, last_ts: str | None) -> float:
    """Span in days between first and last communication, capped at 2 years."""
    if not first_ts or not last_ts:
        return 0.0
    try:
        first = datetime.fromisoformat(first_ts)
        last = datetime.fromisoformat(last_ts)
    except (ValueError, TypeError):
        return 0.0
    span_days = (last - first).total_seconds() / 86400
    if span_days <= 0:
        return 0.0
    return min(1.0, span_days / DURATION_CAP_DAYS)


# ---------------------------------------------------------------------------
# Data gathering SQL
# ---------------------------------------------------------------------------

_COMPANY_STATS_SQL = """\
SELECT
    COUNT(*) AS total_comms,
    SUM(CASE WHEN c.direction = 'outbound' THEN 1 ELSE 0 END) AS outbound_count,
    SUM(CASE WHEN c.direction = 'inbound' THEN 1 ELSE 0 END) AS inbound_count,
    SUM(CASE WHEN c.direction = 'outbound'
              AND c.timestamp >= :window_start THEN 1 ELSE 0 END) AS recent_outbound,
    SUM(CASE WHEN c.direction = 'inbound'
              AND c.timestamp >= :window_start THEN 1 ELSE 0 END) AS recent_inbound,
    MIN(c.timestamp) AS first_ts,
    MAX(c.timestamp) AS last_ts,
    COUNT(DISTINCT ct.id) AS distinct_contacts
FROM contacts ct
JOIN contact_identifiers ci ON ci.contact_id = ct.id AND ci.type = 'email'
LEFT JOIN communication_participants cp ON LOWER(cp.address) = LOWER(ci.value)
LEFT JOIN communications c ON c.id = cp.communication_id
WHERE ct.company_id = :company_id
  AND c.id IS NOT NULL
"""

_COMPANY_SENDER_STATS_SQL = """\
SELECT
    COUNT(*) AS total_comms,
    SUM(CASE WHEN c.direction = 'outbound' THEN 1 ELSE 0 END) AS outbound_count,
    SUM(CASE WHEN c.direction = 'inbound' THEN 1 ELSE 0 END) AS inbound_count,
    SUM(CASE WHEN c.direction = 'outbound'
              AND c.timestamp >= :window_start THEN 1 ELSE 0 END) AS recent_outbound,
    SUM(CASE WHEN c.direction = 'inbound'
              AND c.timestamp >= :window_start THEN 1 ELSE 0 END) AS recent_inbound,
    MIN(c.timestamp) AS first_ts,
    MAX(c.timestamp) AS last_ts,
    COUNT(DISTINCT ct.id) AS distinct_contacts
FROM contacts ct
JOIN contact_identifiers ci ON ci.contact_id = ct.id AND ci.type = 'email'
JOIN communications c ON LOWER(c.sender_address) = LOWER(ci.value)
WHERE ct.company_id = :company_id
"""

_CONTACT_STATS_SQL = """\
SELECT
    COUNT(*) AS total_comms,
    SUM(CASE WHEN c.direction = 'outbound' THEN 1 ELSE 0 END) AS outbound_count,
    SUM(CASE WHEN c.direction = 'inbound' THEN 1 ELSE 0 END) AS inbound_count,
    SUM(CASE WHEN c.direction = 'outbound'
              AND c.timestamp >= :window_start THEN 1 ELSE 0 END) AS recent_outbound,
    SUM(CASE WHEN c.direction = 'inbound'
              AND c.timestamp >= :window_start THEN 1 ELSE 0 END) AS recent_inbound,
    MIN(c.timestamp) AS first_ts,
    MAX(c.timestamp) AS last_ts
FROM contact_identifiers ci
LEFT JOIN communication_participants cp ON LOWER(cp.address) = LOWER(ci.value)
LEFT JOIN communications c ON c.id = cp.communication_id
WHERE ci.contact_id = :contact_id
  AND ci.type = 'email'
  AND c.id IS NOT NULL
"""

_CONTACT_SENDER_STATS_SQL = """\
SELECT
    COUNT(*) AS total_comms,
    SUM(CASE WHEN c.direction = 'outbound' THEN 1 ELSE 0 END) AS outbound_count,
    SUM(CASE WHEN c.direction = 'inbound' THEN 1 ELSE 0 END) AS inbound_count,
    SUM(CASE WHEN c.direction = 'outbound'
              AND c.timestamp >= :window_start THEN 1 ELSE 0 END) AS recent_outbound,
    SUM(CASE WHEN c.direction = 'inbound'
              AND c.timestamp >= :window_start THEN 1 ELSE 0 END) AS recent_inbound,
    MIN(c.timestamp) AS first_ts,
    MAX(c.timestamp) AS last_ts
FROM contact_identifiers ci
JOIN communications c ON LOWER(c.sender_address) = LOWER(ci.value)
WHERE ci.contact_id = :contact_id
  AND ci.type = 'email'
"""

_CONTACT_BREADTH_SQL = """\
SELECT COUNT(DISTINCT cp2.conversation_id) AS distinct_conversations
FROM contact_identifiers ci
JOIN communication_participants cpart ON LOWER(cpart.address) = LOWER(ci.value)
JOIN conversation_communications cc ON cc.communication_id = cpart.communication_id
JOIN conversation_participants cp2 ON cp2.conversation_id = cc.conversation_id
                                   AND cp2.contact_id = :contact_id
WHERE ci.contact_id = :contact_id
  AND ci.type = 'email'
"""


def _merge_stats(row_a: dict, row_b: dict) -> dict:
    """Merge two stats rows (participants path + sender path), avoiding double-counting."""
    # For counts, sum them (the sender path catches communications not in participants)
    total = (row_a.get("total_comms") or 0) + (row_b.get("total_comms") or 0)
    outbound = (row_a.get("outbound_count") or 0) + (row_b.get("outbound_count") or 0)
    inbound = (row_a.get("inbound_count") or 0) + (row_b.get("inbound_count") or 0)
    recent_out = (row_a.get("recent_outbound") or 0) + (row_b.get("recent_outbound") or 0)
    recent_in = (row_a.get("recent_inbound") or 0) + (row_b.get("recent_inbound") or 0)

    # For timestamps, take min/max
    first_a = row_a.get("first_ts")
    first_b = row_b.get("first_ts")
    first_ts = min(filter(None, [first_a, first_b]), default=None)

    last_a = row_a.get("last_ts")
    last_b = row_b.get("last_ts")
    last_ts = max(filter(None, [last_a, last_b]), default=None)

    # For distinct contacts, take max (both paths count the same contacts)
    distinct = max(
        row_a.get("distinct_contacts") or 0,
        row_b.get("distinct_contacts") or 0,
    )

    return {
        "total_comms": total,
        "outbound_count": outbound,
        "inbound_count": inbound,
        "recent_outbound": recent_out,
        "recent_inbound": recent_in,
        "first_ts": first_ts,
        "last_ts": last_ts,
        "distinct_contacts": distinct,
    }


# ---------------------------------------------------------------------------
# Compute functions
# ---------------------------------------------------------------------------

def compute_company_score(
    conn,
    company_id: str,
    weights: dict[str, float] | None = None,
) -> dict[str, Any] | None:
    """Compute relationship strength score for a company.

    Returns {"score": float, "factors": dict, "raw": dict} or None if no data.
    """
    w = weights or DEFAULT_WEIGHTS
    now = datetime.now(timezone.utc)
    window_start = (
        now.replace(hour=0, minute=0, second=0, microsecond=0)
    )
    from datetime import timedelta
    window_start = (now - timedelta(days=FREQUENCY_WINDOW_DAYS)).isoformat()

    params = {"company_id": company_id, "window_start": window_start}

    row_a = dict(conn.execute(_COMPANY_STATS_SQL, params).fetchone())
    row_b = dict(conn.execute(_COMPANY_SENDER_STATS_SQL, params).fetchone())
    stats = _merge_stats(row_a, row_b)

    if stats["total_comms"] == 0:
        return None

    # Recency
    last_ts = stats["last_ts"]
    if last_ts:
        try:
            last_dt = datetime.fromisoformat(last_ts)
            if last_dt.tzinfo is None:
                last_dt = last_dt.replace(tzinfo=timezone.utc)
            days_since = (now - last_dt).total_seconds() / 86400
        except (ValueError, TypeError):
            days_since = None
    else:
        days_since = None

    factors = {
        "recency": _recency_score(days_since),
        "frequency": _frequency_score(
            stats["recent_outbound"], stats["recent_inbound"],
        ),
        "reciprocity": _reciprocity_score(
            stats["outbound_count"], stats["inbound_count"],
        ),
        "breadth": _breadth_score(stats["distinct_contacts"]),
        "duration": _duration_score(stats["first_ts"], stats["last_ts"]),
    }

    score = sum(factors[k] * w.get(k, 0) for k in factors)

    return {
        "score": round(score, 4),
        "factors": {k: round(v, 4) for k, v in factors.items()},
        "raw": stats,
    }


def compute_contact_score(
    conn,
    contact_id: str,
    weights: dict[str, float] | None = None,
) -> dict[str, Any] | None:
    """Compute relationship strength score for a contact.

    Returns {"score": float, "factors": dict, "raw": dict} or None if no data.
    """
    w = weights or DEFAULT_WEIGHTS
    now = datetime.now(timezone.utc)
    from datetime import timedelta
    window_start = (now - timedelta(days=FREQUENCY_WINDOW_DAYS)).isoformat()

    params = {"contact_id": contact_id, "window_start": window_start}

    row_a = dict(conn.execute(_CONTACT_STATS_SQL, params).fetchone())
    row_b = dict(conn.execute(_CONTACT_SENDER_STATS_SQL, params).fetchone())

    # Merge counts
    total = (row_a.get("total_comms") or 0) + (row_b.get("total_comms") or 0)
    outbound = (row_a.get("outbound_count") or 0) + (row_b.get("outbound_count") or 0)
    inbound = (row_a.get("inbound_count") or 0) + (row_b.get("inbound_count") or 0)
    recent_out = (row_a.get("recent_outbound") or 0) + (row_b.get("recent_outbound") or 0)
    recent_in = (row_a.get("recent_inbound") or 0) + (row_b.get("recent_inbound") or 0)
    first_a, first_b = row_a.get("first_ts"), row_b.get("first_ts")
    first_ts = min(filter(None, [first_a, first_b]), default=None)
    last_a, last_b = row_a.get("last_ts"), row_b.get("last_ts")
    last_ts = max(filter(None, [last_a, last_b]), default=None)

    if total == 0:
        return None

    # Breadth for contact = distinct conversations
    breadth_row = conn.execute(
        _CONTACT_BREADTH_SQL, {"contact_id": contact_id},
    ).fetchone()
    distinct_conversations = (breadth_row["distinct_conversations"] or 0) if breadth_row else 0

    # Recency
    if last_ts:
        try:
            last_dt = datetime.fromisoformat(last_ts)
            if last_dt.tzinfo is None:
                last_dt = last_dt.replace(tzinfo=timezone.utc)
            days_since = (now - last_dt).total_seconds() / 86400
        except (ValueError, TypeError):
            days_since = None
    else:
        days_since = None

    factors = {
        "recency": _recency_score(days_since),
        "frequency": _frequency_score(recent_out, recent_in),
        "reciprocity": _reciprocity_score(outbound, inbound),
        "breadth": _breadth_score(distinct_conversations),
        "duration": _duration_score(first_ts, last_ts),
    }

    score = sum(factors[k] * w.get(k, 0) for k in factors)

    raw = {
        "total_comms": total,
        "outbound_count": outbound,
        "inbound_count": inbound,
        "recent_outbound": recent_out,
        "recent_inbound": recent_in,
        "first_ts": first_ts,
        "last_ts": last_ts,
        "distinct_conversations": distinct_conversations,
    }

    return {
        "score": round(score, 4),
        "factors": {k: round(v, 4) for k, v in factors.items()},
        "raw": raw,
    }


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def upsert_entity_score(
    conn,
    entity_type: str,
    entity_id: str,
    score_type: str,
    score_value: float,
    factors: dict,
    triggered_by: str = "manual",
) -> None:
    """Insert or update an entity score row."""
    import uuid
    now = datetime.now(timezone.utc).isoformat()
    factors_json = json.dumps(factors)

    conn.execute(
        """INSERT INTO entity_scores (id, entity_type, entity_id, score_type,
                                      score_value, factors, computed_at, triggered_by)
           VALUES (:id, :entity_type, :entity_id, :score_type,
                   :score_value, :factors, :computed_at, :triggered_by)
           ON CONFLICT(entity_type, entity_id, score_type)
           DO UPDATE SET score_value = :score_value,
                         factors = :factors,
                         computed_at = :computed_at,
                         triggered_by = :triggered_by""",
        {
            "id": str(uuid.uuid4()),
            "entity_type": entity_type,
            "entity_id": entity_id,
            "score_type": score_type,
            "score_value": score_value,
            "factors": factors_json,
            "computed_at": now,
            "triggered_by": triggered_by,
        },
    )


def get_entity_score(
    entity_type: str,
    entity_id: str,
    score_type: str = SCORE_TYPE,
) -> dict[str, Any] | None:
    """Read a persisted entity score, parsing the factors JSON."""
    with get_connection() as conn:
        row = conn.execute(
            """SELECT * FROM entity_scores
               WHERE entity_type = ? AND entity_id = ? AND score_type = ?""",
            (entity_type, entity_id, score_type),
        ).fetchone()

    if not row:
        return None

    result = dict(row)
    if result.get("factors"):
        try:
            result["factors"] = json.loads(result["factors"])
        except (json.JSONDecodeError, TypeError):
            result["factors"] = {}
    else:
        result["factors"] = {}

    return result


# ---------------------------------------------------------------------------
# Batch operations
# ---------------------------------------------------------------------------

def score_all_companies(
    triggered_by: str = "batch",
) -> dict[str, int]:
    """Score all active companies. Returns {"scored": int, "skipped": int}."""
    scored = 0
    skipped = 0

    with get_connection() as conn:
        companies = conn.execute(
            "SELECT id, name FROM companies WHERE status = 'active' ORDER BY name",
        ).fetchall()

        for c in companies:
            result = compute_company_score(conn, c["id"])
            if result is None:
                skipped += 1
                continue
            upsert_entity_score(
                conn, "company", c["id"], SCORE_TYPE,
                result["score"], result["factors"],
                triggered_by=triggered_by,
            )
            scored += 1

    return {"scored": scored, "skipped": skipped}


def score_all_contacts(
    triggered_by: str = "batch",
) -> dict[str, int]:
    """Score all active contacts. Returns {"scored": int, "skipped": int}."""
    scored = 0
    skipped = 0

    with get_connection() as conn:
        contacts = conn.execute(
            "SELECT id, name FROM contacts WHERE status = 'active' ORDER BY name",
        ).fetchall()

        for c in contacts:
            result = compute_contact_score(conn, c["id"])
            if result is None:
                skipped += 1
                continue
            upsert_entity_score(
                conn, "contact", c["id"], SCORE_TYPE,
                result["score"], result["factors"],
                triggered_by=triggered_by,
            )
            scored += 1

    return {"scored": scored, "skipped": skipped}
