"""Enrichment pipeline — orchestration, CRUD for enrichment_runs/field_values,
conflict resolution, and entity updates."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from .database import get_connection
from .enrichment_provider import FieldValue, SourceTier, get_provider, list_providers
from .hierarchy import (
    add_address,
    add_company_social_profile,
    add_email_address,
    add_phone_number,
    get_addresses,
    get_company,
    get_company_social_profiles,
    get_email_addresses,
    get_phone_numbers,
    update_company,
)

log = logging.getLogger(__name__)

# Confidence threshold for auto-accepting field values
AUTO_ACCEPT_THRESHOLD = 0.7

# Direct company fields that map straight to update_company()
DIRECT_FIELDS = {
    "description", "industry", "website", "stock_symbol", "size_range",
    "employee_count", "founded_year", "revenue_range", "funding_total",
    "funding_stage", "headquarters_location",
}


# ---------------------------------------------------------------------------
# Enrichment run CRUD
# ---------------------------------------------------------------------------

def create_enrichment_run(
    entity_type: str,
    entity_id: str,
    provider: str,
) -> dict:
    """Create a new enrichment run record. Returns the row as a dict."""
    now = datetime.now(timezone.utc).isoformat()
    run_id = str(uuid.uuid4())
    row = {
        "id": run_id,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "provider": provider,
        "status": "pending",
        "started_at": None,
        "completed_at": None,
        "error_message": None,
        "created_at": now,
    }
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO enrichment_runs "
            "(id, entity_type, entity_id, provider, status, started_at, "
            "completed_at, error_message, created_at) "
            "VALUES (:id, :entity_type, :entity_id, :provider, :status, "
            ":started_at, :completed_at, :error_message, :created_at)",
            row,
        )
    return row


def get_enrichment_run(run_id: str) -> dict | None:
    """Fetch a single enrichment run by ID."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM enrichment_runs WHERE id = ?", (run_id,)
        ).fetchone()
    return dict(row) if row else None


def get_enrichment_runs(
    entity_type: str | None = None,
    entity_id: str | None = None,
) -> list[dict]:
    """List enrichment runs, optionally filtered by entity."""
    clauses, params = [], []
    if entity_type:
        clauses.append("entity_type = ?")
        params.append(entity_type)
    if entity_id:
        clauses.append("entity_id = ?")
        params.append(entity_id)
    where = " AND ".join(clauses)
    sql = "SELECT * FROM enrichment_runs"
    if where:
        sql += " WHERE " + where
    sql += " ORDER BY created_at DESC"
    with get_connection() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


def get_enrichment_field_values(run_id: str) -> list[dict]:
    """List field values for a given enrichment run."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM enrichment_field_values WHERE enrichment_run_id = ? "
            "ORDER BY field_name",
            (run_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def _update_run_status(run_id: str, status: str, error_message: str | None = None) -> None:
    """Update an enrichment run's status."""
    now = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        if status == "running":
            conn.execute(
                "UPDATE enrichment_runs SET status = ?, started_at = ? WHERE id = ?",
                (status, now, run_id),
            )
        elif status in ("completed", "failed"):
            conn.execute(
                "UPDATE enrichment_runs SET status = ?, completed_at = ?, error_message = ? "
                "WHERE id = ?",
                (status, now, error_message, run_id),
            )


def _store_field_values(run_id: str, field_values: list[FieldValue]) -> list[dict]:
    """Persist FieldValues to the enrichment_field_values table."""
    now = datetime.now(timezone.utc).isoformat()
    rows = []
    with get_connection() as conn:
        for fv in field_values:
            row_id = str(uuid.uuid4())
            row = {
                "id": row_id,
                "enrichment_run_id": run_id,
                "field_name": fv.field_name,
                "field_value": fv.field_value,
                "confidence": fv.confidence,
                "is_accepted": 0,
                "created_at": now,
            }
            conn.execute(
                "INSERT INTO enrichment_field_values "
                "(id, enrichment_run_id, field_name, field_value, confidence, "
                "is_accepted, created_at) "
                "VALUES (:id, :enrichment_run_id, :field_name, :field_value, "
                ":confidence, :is_accepted, :created_at)",
                row,
            )
            rows.append(row)
    return rows


# ---------------------------------------------------------------------------
# Conflict resolution
# ---------------------------------------------------------------------------

def _should_accept(
    field_name: str,
    new_value: str,
    new_tier: SourceTier,
    new_confidence: float,
    entity: dict,
) -> bool:
    """Decide whether a new field value should overwrite the existing one.

    Rules:
    - If the existing field is empty/null, accept any value with sufficient confidence.
    - Higher-tier sources always overwrite lower-tier sources.
    - Same-tier: accept if confidence >= AUTO_ACCEPT_THRESHOLD.
    """
    if new_confidence < AUTO_ACCEPT_THRESHOLD:
        return False

    current = entity.get(field_name)
    if not current:
        return True

    # For now we accept if the field is a direct field and confidence is high enough
    # In future, we'd look up the previous enrichment source tier
    return True


# ---------------------------------------------------------------------------
# Apply logic
# ---------------------------------------------------------------------------

def _apply_direct_fields(
    entity_id: str,
    field_values: list[FieldValue],
    provider_tier: SourceTier,
    entity: dict,
) -> int:
    """Apply direct company fields (description, industry, etc.). Returns count applied."""
    updates = {}
    accepted_ids = []
    for fv in field_values:
        if fv.field_name in DIRECT_FIELDS:
            if _should_accept(fv.field_name, fv.field_value, provider_tier,
                              fv.confidence, entity):
                # Convert to int for integer fields
                if fv.field_name in ("employee_count", "founded_year"):
                    try:
                        updates[fv.field_name] = int(fv.field_value)
                    except (ValueError, TypeError):
                        continue
                else:
                    updates[fv.field_name] = fv.field_value
                accepted_ids.append(fv)

    if updates:
        update_company(entity_id, **updates)

    return len(updates)


def _apply_phone_numbers(
    entity_id: str,
    field_values: list[FieldValue],
    provider_tier: SourceTier,
) -> int:
    """Add phone numbers avoiding duplicates. Returns count added."""
    existing = {p["number"] for p in get_phone_numbers("company", entity_id)}
    count = 0
    for fv in field_values:
        if fv.field_name == "phone" and fv.confidence >= AUTO_ACCEPT_THRESHOLD:
            if fv.field_value not in existing:
                add_phone_number("company", entity_id, fv.field_value, phone_type="main")
                existing.add(fv.field_value)
                count += 1
    return count


def _apply_email_addresses(
    entity_id: str,
    field_values: list[FieldValue],
    provider_tier: SourceTier,
) -> int:
    """Add email addresses avoiding duplicates. Returns count added."""
    existing = {e["address"] for e in get_email_addresses("company", entity_id)}
    count = 0
    for fv in field_values:
        if fv.field_name == "email" and fv.confidence >= AUTO_ACCEPT_THRESHOLD:
            if fv.field_value not in existing:
                add_email_address("company", entity_id, fv.field_value, email_type="general")
                existing.add(fv.field_value)
                count += 1
    return count


def _apply_addresses(
    entity_id: str,
    field_values: list[FieldValue],
    provider_tier: SourceTier,
) -> int:
    """Add addresses avoiding duplicates. Returns count added."""
    existing_streets = {
        a["street"] for a in get_addresses("company", entity_id) if a.get("street")
    }
    count = 0
    for fv in field_values:
        if fv.field_name == "address" and fv.confidence >= AUTO_ACCEPT_THRESHOLD:
            if fv.field_value not in existing_streets:
                add_address("company", entity_id, street=fv.field_value, address_type="work")
                existing_streets.add(fv.field_value)
                count += 1
    return count


def _apply_social_profiles(
    entity_id: str,
    field_values: list[FieldValue],
    provider_tier: SourceTier,
) -> int:
    """Add social profiles avoiding duplicates. Returns count added."""
    existing = {
        (sp["platform"], sp["profile_url"])
        for sp in get_company_social_profiles(entity_id)
    }
    count = 0
    for fv in field_values:
        if fv.field_name.startswith("social_"):
            platform = fv.field_name[len("social_"):]  # e.g. social_linkedin -> linkedin
            if (platform, fv.field_value) not in existing:
                add_company_social_profile(
                    entity_id, platform, fv.field_value,
                    source="website_scraper",
                    confidence=fv.confidence,
                )
                existing.add((platform, fv.field_value))
                count += 1
    return count


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def execute_enrichment(
    entity_type: str,
    entity_id: str,
    provider_name: str | None = None,
) -> dict:
    """Run enrichment pipeline for an entity.

    Returns a summary dict with keys: run_id, status, fields_discovered,
    fields_applied, error.
    """
    # Resolve provider
    if provider_name:
        provider = get_provider(provider_name)
        if not provider:
            return {"run_id": None, "status": "failed",
                    "fields_discovered": 0, "fields_applied": 0,
                    "error": f"Provider '{provider_name}' not found"}
        providers = [provider]
    else:
        providers = [p for p in list_providers() if entity_type in p.entity_types]
        if not providers:
            return {"run_id": None, "status": "failed",
                    "fields_discovered": 0, "fields_applied": 0,
                    "error": "No providers available"}

    # For now, run each provider. Return result from last one.
    last_result = None
    for provider in providers:
        last_result = _run_single_provider(entity_type, entity_id, provider)
    return last_result


def _run_single_provider(
    entity_type: str,
    entity_id: str,
    provider,
) -> dict:
    """Execute a single provider against an entity."""
    run = create_enrichment_run(entity_type, entity_id, provider.name)
    run_id = run["id"]

    # Load entity
    if entity_type == "company":
        entity = get_company(entity_id)
    else:
        entity = None  # Contact enrichment not yet implemented

    if not entity:
        _update_run_status(run_id, "failed", "Entity not found")
        return {"run_id": run_id, "status": "failed",
                "fields_discovered": 0, "fields_applied": 0,
                "error": "Entity not found"}

    _update_run_status(run_id, "running")

    try:
        field_values = provider.enrich(entity)
    except Exception as exc:
        log.exception("Provider %s failed for %s/%s", provider.name, entity_type, entity_id)
        _update_run_status(run_id, "failed", str(exc))
        return {"run_id": run_id, "status": "failed",
                "fields_discovered": 0, "fields_applied": 0,
                "error": str(exc)}

    # Store raw field values
    _store_field_values(run_id, field_values)

    # Apply to entity
    applied = 0
    if entity_type == "company":
        applied += _apply_direct_fields(entity_id, field_values, provider.tier, entity)
        applied += _apply_phone_numbers(entity_id, field_values, provider.tier)
        applied += _apply_email_addresses(entity_id, field_values, provider.tier)
        applied += _apply_addresses(entity_id, field_values, provider.tier)
        applied += _apply_social_profiles(entity_id, field_values, provider.tier)

    # Mark accepted in DB
    with get_connection() as conn:
        for fv in field_values:
            if fv.confidence >= AUTO_ACCEPT_THRESHOLD:
                conn.execute(
                    "UPDATE enrichment_field_values SET is_accepted = 1 "
                    "WHERE enrichment_run_id = ? AND field_name = ? AND field_value = ?",
                    (run_id, fv.field_name, fv.field_value),
                )

    _update_run_status(run_id, "completed")

    return {
        "run_id": run_id,
        "status": "completed",
        "fields_discovered": len(field_values),
        "fields_applied": applied,
        "error": None,
    }
