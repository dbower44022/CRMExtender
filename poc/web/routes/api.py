"""JSON API routes for the React frontend (/api/v1/)."""

from __future__ import annotations

import json
import re
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse

from ...database import get_connection
from ...views.crud import (
    create_view,
    delete_view,
    duplicate_view,
    ensure_system_data_sources,
    get_data_source,
    get_default_view_for_entity,
    get_view,
    get_view_with_config,
    get_views_for_entity,
    update_view,
    update_view_columns,
    update_view_filters,
)
from ...views.engine import execute_view
from ...views.layout_overrides import (
    delete_all_layout_overrides,
    delete_layout_override,
    get_layout_overrides,
    upsert_layout_override,
)
from ...views.registry import ENTITY_TYPES
from ...contact_merge import get_contact_merge_preview, merge_contacts
from ...company_merge import merge_companies
from ... import config

router = APIRouter()


# ------------------------------------------------------------------
# Health
# ------------------------------------------------------------------

@router.get("/health")
def health():
    return {"status": "ok", "version": "1.0.0"}


# ------------------------------------------------------------------
# Entity Registry
# ------------------------------------------------------------------

@router.get("/entity-types")
def entity_types():
    """Serialize the ENTITY_TYPES registry as JSON for the frontend."""
    result = {}
    for key, edef in ENTITY_TYPES.items():
        fields = {}
        for fk, fdef in edef.fields.items():
            fd = asdict(fdef)
            # Remove the sql expression — frontend doesn't need it
            fd.pop("sql", None)
            fields[fk] = fd
        result[key] = {
            "label": edef.label,
            "detail_url": edef.detail_url,
            "fields": fields,
            "default_columns": list(edef.default_columns),
            "default_sort": list(edef.default_sort),
            "search_fields": [],  # don't expose raw SQL field refs
        }
    return result


# ------------------------------------------------------------------
# Views
# ------------------------------------------------------------------

@router.get("/views")
def list_views(request: Request, entity_type: str = Query(...)):
    cid = request.state.customer_id
    uid = request.state.user["id"] if request.state.user else ""
    with get_connection() as conn:
        # Ensure default views exist before listing
        from ...views.crud import ensure_default_views
        ensure_default_views(conn, cid, uid)
        conn.commit()
        views = get_views_for_entity(conn, cid, uid, entity_type)
    return views


@router.get("/views/{view_id}")
def view_detail(request: Request, view_id: str):
    with get_connection() as conn:
        view = get_view_with_config(conn, view_id)
    if not view:
        return JSONResponse({"error": "View not found"}, status_code=404)
    return view


@router.get("/views/{view_id}/data")
def view_data(
    request: Request,
    view_id: str,
    page: int = Query(1, ge=1),
    sort: str | None = Query(None),
    sort_direction: str = Query("asc"),
    search: str = Query(""),
    scope: str = Query("all"),
    filters: str = Query(""),
):
    cid = request.state.customer_id
    uid = request.state.user["id"] if request.state.user else ""

    # Parse extra_filters from query param (JSON array of filter dicts)
    extra_filters: list[dict] = []
    if filters:
        try:
            extra_filters = json.loads(filters)
        except (json.JSONDecodeError, TypeError):
            extra_filters = []

    with get_connection() as conn:
        view = get_view_with_config(conn, view_id)
        if not view:
            return JSONResponse({"error": "View not found"}, status_code=404)

        # Merge view filters with any extra (quick) filters
        all_filters = list(view["filters"])
        for ef in extra_filters:
            all_filters.append({
                "field_key": ef.get("field_key", ""),
                "operator": ef.get("operator", "equals"),
                "value": ef.get("value"),
            })

        rows, total = execute_view(
            conn,
            entity_type=view["entity_type"],
            columns=view["columns"],
            filters=all_filters,
            sort_field=sort or view.get("sort_field"),
            sort_direction=sort_direction if sort else view.get("sort_direction", "asc"),
            search=search,
            page=page,
            per_page=view.get("per_page", 50),
            customer_id=cid,
            user_id=uid,
            scope=scope,
        )

    per_page = view.get("per_page", 50)
    return {
        "rows": rows,
        "total": total,
        "page": page,
        "per_page": per_page,
        "has_more": page * per_page < total,
    }


# ------------------------------------------------------------------
# View Mutations
# ------------------------------------------------------------------

def _extract_link_deps(entity_def):
    """Map visible fields to hidden fields required by their link templates."""
    deps = {}
    hidden_keys = {k for k, f in entity_def.fields.items() if f.type == "hidden"}
    for fk, fdef in entity_def.fields.items():
        if fdef.link:
            refs = set(re.findall(r'\{(\w+)\}', fdef.link))
            needed = [r for r in refs if r in hidden_keys and r != "id"]
            if needed:
                deps[fk] = needed
    return deps


@router.post("/views")
async def create_view_api(request: Request):
    """Create a new view for an entity type."""
    cid = request.state.customer_id
    uid = request.state.user["id"] if request.state.user else ""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)

    entity_type = body.get("entity_type", "")
    name = body.get("name", "").strip()
    if not entity_type or not name:
        return JSONResponse(
            {"error": "entity_type and name are required"}, status_code=400,
        )
    if entity_type not in ENTITY_TYPES:
        return JSONResponse({"error": "Unknown entity type"}, status_code=400)

    with get_connection() as conn:
        ensure_system_data_sources(conn, cid)
        ds_id = f"ds-{entity_type}-{cid}"
        ds = get_data_source(conn, ds_id)
        if not ds:
            return JSONResponse({"error": "Data source not found"}, status_code=400)

        view_id = create_view(
            conn,
            customer_id=cid,
            user_id=uid,
            data_source_id=ds_id,
            name=name,
        )
        conn.commit()
        view = get_view_with_config(conn, view_id)
    return view


@router.put("/views/{view_id}")
async def update_view_api(request: Request, view_id: str):
    """Update view settings (name, sort, per_page, visibility)."""
    cid = request.state.customer_id
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)

    with get_connection() as conn:
        view = get_view(conn, view_id)
        if not view or view.get("customer_id") != cid:
            return JSONResponse({"error": "View not found"}, status_code=404)

        update_view(conn, view_id, **body)
        conn.commit()
        return get_view_with_config(conn, view_id)


@router.put("/views/{view_id}/columns")
async def update_view_columns_api(request: Request, view_id: str):
    """Replace columns for a view."""
    cid = request.state.customer_id
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)

    columns = body.get("columns", [])
    if not columns:
        return JSONResponse({"error": "columns list is required"}, status_code=400)

    with get_connection() as conn:
        view = get_view(conn, view_id)
        if not view or view.get("customer_id") != cid:
            return JSONResponse({"error": "View not found"}, status_code=404)

        entity_type = view.get("entity_type", "")
        entity_def = ENTITY_TYPES.get(entity_type)

        if entity_def:
            # Normalize column format
            def _col_key(item):
                return item["key"] if isinstance(item, dict) else item

            is_object_format = columns and isinstance(columns[0], dict)
            valid_keys = set(entity_def.fields.keys())
            columns = [c for c in columns if _col_key(c) in valid_keys]

            # Auto-append hidden dependency fields
            field_deps = _extract_link_deps(entity_def)
            col_set = {_col_key(c) for c in columns}
            for item in list(columns):
                for dep_key in field_deps.get(_col_key(item), []):
                    if dep_key not in col_set:
                        columns.append({"key": dep_key} if is_object_format else dep_key)
                        col_set.add(dep_key)

        update_view_columns(conn, view_id, columns)
        conn.commit()
        return get_view_with_config(conn, view_id)


@router.put("/views/{view_id}/filters")
async def update_view_filters_api(request: Request, view_id: str):
    """Replace filters for a view."""
    cid = request.state.customer_id
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)

    filters = body.get("filters", [])

    with get_connection() as conn:
        view = get_view(conn, view_id)
        if not view or view.get("customer_id") != cid:
            return JSONResponse({"error": "View not found"}, status_code=404)

        update_view_filters(conn, view_id, filters)
        conn.commit()
        return get_view_with_config(conn, view_id)


@router.delete("/views/{view_id}")
def delete_view_api(request: Request, view_id: str):
    """Delete a view (fails for default views)."""
    cid = request.state.customer_id

    with get_connection() as conn:
        view = get_view(conn, view_id)
        if not view or view.get("customer_id") != cid:
            return JSONResponse({"error": "View not found"}, status_code=404)

        deleted = delete_view(conn, view_id)
        if not deleted:
            return JSONResponse(
                {"error": "Cannot delete a default view"}, status_code=400,
            )
        conn.commit()
    return {"ok": True}


@router.post("/views/{view_id}/duplicate")
async def duplicate_view_api(request: Request, view_id: str):
    """Duplicate a view."""
    cid = request.state.customer_id
    uid = request.state.user["id"] if request.state.user else ""

    try:
        body = await request.json()
    except Exception:
        body = {}

    with get_connection() as conn:
        view = get_view(conn, view_id)
        if not view or view.get("customer_id") != cid:
            return JSONResponse({"error": "View not found"}, status_code=404)

        new_name = (body.get("name") or f"{view['name']} (copy)").strip()
        new_id = duplicate_view(conn, view_id, new_name, uid)
        if not new_id:
            return JSONResponse({"error": "Duplicate failed"}, status_code=500)
        conn.commit()
        return get_view_with_config(conn, new_id)


# ------------------------------------------------------------------
# Layout Overrides
# ------------------------------------------------------------------

_VALID_DISPLAY_TIERS = {"ultra_wide", "spacious", "standard", "constrained", "minimal"}


@router.get("/views/{view_id}/layout-overrides")
def list_layout_overrides(request: Request, view_id: str):
    """Get all layout overrides for a view (current user)."""
    uid = request.state.user["id"] if request.state.user else ""
    cid = request.state.customer_id

    with get_connection() as conn:
        view = get_view(conn, view_id)
        if not view or view.get("customer_id") != cid:
            return JSONResponse({"error": "View not found"}, status_code=404)
        overrides = get_layout_overrides(conn, uid, view_id)
    return overrides


@router.put("/views/{view_id}/layout-overrides/{display_tier}")
async def upsert_layout_override_api(
    request: Request, view_id: str, display_tier: str,
):
    """Create or update a layout override for a specific display tier."""
    uid = request.state.user["id"] if request.state.user else ""
    cid = request.state.customer_id

    if display_tier not in _VALID_DISPLAY_TIERS:
        return JSONResponse(
            {"error": f"Invalid display_tier: {display_tier}. "
             f"Must be one of: {', '.join(sorted(_VALID_DISPLAY_TIERS))}"},
            status_code=400,
        )

    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)

    with get_connection() as conn:
        view = get_view(conn, view_id)
        if not view or view.get("customer_id") != cid:
            return JSONResponse({"error": "View not found"}, status_code=404)

        try:
            result = upsert_layout_override(
                conn,
                user_id=uid,
                view_id=view_id,
                display_tier=display_tier,
                splitter_pct=body.get("splitter_pct"),
                density=body.get("density"),
                column_overrides=body.get("column_overrides"),
            )
        except ValueError as e:
            return JSONResponse({"error": str(e)}, status_code=400)
        conn.commit()
    return result


@router.delete("/views/{view_id}/layout-overrides/{display_tier}")
def delete_layout_override_api(
    request: Request, view_id: str, display_tier: str,
):
    """Delete a layout override for a specific display tier."""
    uid = request.state.user["id"] if request.state.user else ""
    cid = request.state.customer_id

    with get_connection() as conn:
        view = get_view(conn, view_id)
        if not view or view.get("customer_id") != cid:
            return JSONResponse({"error": "View not found"}, status_code=404)
        deleted = delete_layout_override(conn, uid, view_id, display_tier)
        if not deleted:
            return JSONResponse({"error": "Override not found"}, status_code=404)
        conn.commit()
    return {"ok": True}


@router.delete("/views/{view_id}/layout-overrides")
def delete_all_layout_overrides_api(request: Request, view_id: str):
    """Delete all layout overrides for a view (reset)."""
    uid = request.state.user["id"] if request.state.user else ""
    cid = request.state.customer_id

    with get_connection() as conn:
        view = get_view(conn, view_id)
        if not view or view.get("customer_id") != cid:
            return JSONResponse({"error": "View not found"}, status_code=404)
        count = delete_all_layout_overrides(conn, uid, view_id)
        conn.commit()
    return {"ok": True, "deleted": count}


@router.post("/cell-edit")
async def cell_edit_api(request: Request):
    """Update a single field on a contact or company via inline edit."""
    from ...hierarchy import update_company, update_contact

    _UPDATE_DISPATCHERS = {
        "contact": ("contacts", update_contact),
        "company": ("companies", update_company),
    }

    cid = request.state.customer_id

    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"ok": False, "error": "Invalid JSON"}, status_code=400)

    entity_type = body.get("entity_type", "")
    entity_id = body.get("entity_id", "")
    field_key = body.get("field_key", "")
    value = body.get("value", "")

    if entity_type not in _UPDATE_DISPATCHERS:
        return JSONResponse(
            {"ok": False, "error": f"Entity type '{entity_type}' is not editable"},
            status_code=400,
        )

    entity_def = ENTITY_TYPES.get(entity_type)
    if not entity_def:
        return JSONResponse({"ok": False, "error": "Unknown entity type"}, status_code=400)

    # Find the editable field by db_column
    fdef = None
    for fk, fd in entity_def.fields.items():
        if fd.db_column == field_key and fd.editable:
            fdef = fd
            break

    if not fdef:
        return JSONResponse(
            {"ok": False, "error": f"Field '{field_key}' is not editable"},
            status_code=400,
        )

    # Validate select options
    if fdef.select_options and value and value not in fdef.select_options:
        return JSONResponse(
            {"ok": False, "error": f"Invalid option '{value}'. Must be one of: {', '.join(fdef.select_options)}"},
            status_code=400,
        )

    # Verify entity belongs to this customer
    table_name, update_fn = _UPDATE_DISPATCHERS[entity_type]
    with get_connection() as conn:
        row = conn.execute(
            f"SELECT id FROM {table_name} WHERE id = ? AND customer_id = ?",
            (entity_id, cid),
        ).fetchone()

    if not row:
        return JSONResponse({"ok": False, "error": "Entity not found"}, status_code=404)

    updated = update_fn(entity_id, **{field_key: value})
    if not updated:
        return JSONResponse({"ok": False, "error": "Update failed"}, status_code=500)

    return JSONResponse({"ok": True, "value": updated.get(field_key, value)})


# ------------------------------------------------------------------
# Contact Merge
# ------------------------------------------------------------------

@router.post("/contacts/merge-preview")
async def merge_preview_api(request: Request):
    """Return a merge preview for the given contact IDs."""
    cid = request.state.customer_id
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)

    contact_ids = body.get("contact_ids", [])

    # Validate ownership
    with get_connection() as conn:
        for contact_id in contact_ids:
            row = conn.execute(
                "SELECT id FROM contacts WHERE id = ? AND customer_id = ?",
                (contact_id, cid),
            ).fetchone()
            if not row:
                return JSONResponse(
                    {"error": f"Contact not found: {contact_id}"}, status_code=404,
                )

    try:
        preview = get_contact_merge_preview(contact_ids)
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)

    return preview


@router.post("/contacts/merge")
async def merge_contacts_api(request: Request):
    """Execute a contact merge."""
    cid = request.state.customer_id
    uid = request.state.user["id"] if request.state.user else None
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)

    surviving_id = body.get("surviving_id", "")
    absorbed_ids = body.get("absorbed_ids", [])
    chosen_name = body.get("chosen_name")
    chosen_source = body.get("chosen_source")

    # Validate ownership
    all_ids = [surviving_id] + absorbed_ids
    with get_connection() as conn:
        for contact_id in all_ids:
            row = conn.execute(
                "SELECT id FROM contacts WHERE id = ? AND customer_id = ?",
                (contact_id, cid),
            ).fetchone()
            if not row:
                return JSONResponse(
                    {"error": f"Contact not found: {contact_id}"}, status_code=400,
                )

    try:
        result = merge_contacts(
            surviving_id,
            absorbed_ids,
            merged_by=uid,
            chosen_name=chosen_name,
            chosen_source=chosen_source,
        )
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)

    return result


# ------------------------------------------------------------------
# Company Merge
# ------------------------------------------------------------------

@router.post("/companies/merge-preview")
async def company_merge_preview_api(request: Request):
    """Return a merge preview for the given company IDs."""
    cid = request.state.customer_id
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)

    company_ids = body.get("company_ids", [])
    if len(company_ids) < 2:
        return JSONResponse(
            {"error": "At least two companies are required for a merge."},
            status_code=400,
        )

    with get_connection() as conn:
        companies = []
        for co_id in company_ids:
            row = conn.execute(
                "SELECT * FROM companies WHERE id = ? AND customer_id = ?",
                (co_id, cid),
            ).fetchone()
            if not row:
                return JSONResponse(
                    {"error": f"Company not found: {co_id}"}, status_code=404,
                )
            c = dict(row)

            c["contact_count"] = conn.execute(
                "SELECT COUNT(*) AS cnt FROM contact_companies WHERE company_id = ?",
                (co_id,),
            ).fetchone()["cnt"]
            c["relationship_count"] = conn.execute(
                """SELECT COUNT(*) AS cnt FROM relationships
                   WHERE (from_entity_type = 'company' AND from_entity_id = ?)
                      OR (to_entity_type = 'company' AND to_entity_id = ?)""",
                (co_id, co_id),
            ).fetchone()["cnt"]
            c["event_count"] = conn.execute(
                """SELECT COUNT(*) AS cnt FROM event_participants
                   WHERE entity_type = 'company' AND entity_id = ?""",
                (co_id,),
            ).fetchone()["cnt"]
            c["identifier_count"] = conn.execute(
                "SELECT COUNT(*) AS cnt FROM company_identifiers WHERE company_id = ?",
                (co_id,),
            ).fetchone()["cnt"]
            c["phone_count"] = conn.execute(
                "SELECT COUNT(*) AS cnt FROM phone_numbers WHERE entity_type='company' AND entity_id=?",
                (co_id,),
            ).fetchone()["cnt"]
            c["address_count"] = conn.execute(
                "SELECT COUNT(*) AS cnt FROM addresses WHERE entity_type='company' AND entity_id=?",
                (co_id,),
            ).fetchone()["cnt"]
            c["email_count"] = conn.execute(
                "SELECT COUNT(*) AS cnt FROM email_addresses WHERE entity_type='company' AND entity_id=?",
                (co_id,),
            ).fetchone()["cnt"]
            c["social_profile_count"] = conn.execute(
                "SELECT COUNT(*) AS cnt FROM company_social_profiles WHERE company_id = ?",
                (co_id,),
            ).fetchone()["cnt"]

            companies.append(c)

        # Conflicts: distinct values for key fields
        names = list({c["name"] for c in companies if c.get("name")})
        domains = list({c["domain"] for c in companies if c.get("domain")})
        industries = list({c["industry"] for c in companies if c.get("industry")})

    totals = {
        "contacts": sum(c["contact_count"] for c in companies),
        "relationships": sum(c["relationship_count"] for c in companies),
        "events": sum(c["event_count"] for c in companies),
        "identifiers": sum(c["identifier_count"] for c in companies),
        "phones": sum(c["phone_count"] for c in companies),
        "addresses": sum(c["address_count"] for c in companies),
        "emails": sum(c["email_count"] for c in companies),
        "social_profiles": sum(c["social_profile_count"] for c in companies),
    }

    return {
        "companies": companies,
        "conflicts": {
            "name": names,
            "domain": domains,
            "industry": industries,
        },
        "totals": totals,
    }


@router.post("/companies/merge")
async def company_merge_api(request: Request):
    """Execute a company merge (one surviving, one or more absorbed)."""
    cid = request.state.customer_id
    uid = request.state.user["id"] if request.state.user else None
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)

    surviving_id = body.get("surviving_id", "")
    absorbed_ids = body.get("absorbed_ids", [])

    # Validate ownership
    all_ids = [surviving_id] + absorbed_ids
    with get_connection() as conn:
        for co_id in all_ids:
            row = conn.execute(
                "SELECT id FROM companies WHERE id = ? AND customer_id = ?",
                (co_id, cid),
            ).fetchone()
            if not row:
                return JSONResponse(
                    {"error": f"Company not found: {co_id}"}, status_code=400,
                )

    # Execute merges sequentially (backend is pairwise)
    total_contacts = 0
    total_relationships = 0
    total_events = 0
    merge_ids = []
    try:
        for absorbed_id in absorbed_ids:
            result = merge_companies(
                surviving_id,
                absorbed_id,
                merged_by=uid,
            )
            merge_ids.append(result["merge_id"])
            total_contacts += result["contacts_reassigned"]
            total_relationships += result["relationships_reassigned"]
            total_events += result["events_reassigned"]
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)

    return {
        "merge_ids": merge_ids,
        "surviving_id": surviving_id,
        "absorbed_ids": absorbed_ids,
        "contacts_reassigned": total_contacts,
        "relationships_reassigned": total_relationships,
        "events_reassigned": total_events,
    }


# ------------------------------------------------------------------
# Create Contact / Company
# ------------------------------------------------------------------

@router.post("/contacts")
async def create_contact_api(request: Request):
    """Create a new contact."""
    from ...hierarchy import add_contact_identifier, create_contact

    cid = request.state.customer_id
    uid = request.state.user["id"] if request.state.user else None

    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)

    name = (body.get("name") or "").strip()
    if not name:
        return JSONResponse({"error": "name is required"}, status_code=400)

    email = (body.get("email") or "").strip()
    source = (body.get("source") or "manual").strip()

    contact = create_contact(
        name, source=source, created_by=uid, customer_id=cid,
    )
    contact_id = contact["id"]

    # Add email identifier if provided
    if email:
        add_contact_identifier(contact_id, "email", email, is_primary=True, source=source)

    # Create visibility row
    now = contact["created_at"]
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO user_contacts "
            "(id, user_id, contact_id, visibility, is_owner, created_at, updated_at) "
            "VALUES (?, ?, ?, 'public', 1, ?, ?)",
            (str(__import__("uuid").uuid4()), uid, contact_id, now, now),
        )

    return contact


@router.post("/companies")
async def create_company_api(request: Request):
    """Create a new company."""
    from ...hierarchy import create_company, update_company

    cid = request.state.customer_id
    uid = request.state.user["id"] if request.state.user else None

    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)

    name = (body.get("name") or "").strip()
    if not name:
        return JSONResponse({"error": "name is required"}, status_code=400)

    domain = (body.get("domain") or "").strip()
    industry = (body.get("industry") or "").strip()

    try:
        company = create_company(
            name, domain=domain, industry=industry,
            created_by=uid, customer_id=cid,
        )
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)

    company_id = company["id"]

    # Apply optional extra fields
    extra = {}
    for key in ("website", "headquarters_location"):
        val = (body.get(key) or "").strip()
        if val:
            extra[key] = val
    if extra:
        update_company(company_id, **extra)

    # Create visibility row
    now = company["created_at"]
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO user_companies "
            "(id, user_id, company_id, visibility, is_owner, created_at, updated_at) "
            "VALUES (?, ?, ?, 'public', 1, ?, ?)",
            (str(__import__("uuid").uuid4()), uid, company_id, now, now),
        )

    return company


# ------------------------------------------------------------------
# Entity Detail
# ------------------------------------------------------------------

@router.get("/contacts/{contact_id}")
def contact_detail_api(request: Request, contact_id: str):
    cid = request.state.customer_id

    with get_connection() as conn:
        contact = conn.execute(
            "SELECT * FROM contacts WHERE id = ?", (contact_id,)
        ).fetchone()
        if not contact:
            return JSONResponse({"error": "Not found"}, status_code=404)
        contact = dict(contact)
        if contact.get("customer_id") and contact["customer_id"] != cid:
            return JSONResponse({"error": "Not found"}, status_code=404)

        # Identifiers
        identifiers = [
            dict(r) for r in conn.execute(
                "SELECT * FROM contact_identifiers WHERE contact_id = ? "
                "ORDER BY is_primary DESC, created_at ASC",
                (contact_id,),
            ).fetchall()
        ]

        # Primary email & all emails
        emails = [i["value"] for i in identifiers if i["type"] == "email"]

        # Phones
        phones_raw = conn.execute(
            "SELECT number FROM phone_numbers "
            "WHERE entity_type = 'contact' AND entity_id = ? AND is_current = 1 "
            "ORDER BY is_primary DESC, created_at ASC",
            (contact_id,),
        ).fetchall()
        phones = [r["number"] for r in phones_raw]

        # Addresses
        addrs_raw = conn.execute(
            "SELECT street, city, state, country, postal_code "
            "FROM addresses WHERE entity_type = 'contact' AND entity_id = ? AND is_current = 1",
            (contact_id,),
        ).fetchall()
        addresses = [_format_address(dict(a)) for a in addrs_raw]

        # Primary company
        company = None
        co_row = conn.execute(
            "SELECT co.id, co.name FROM contact_companies cc "
            "JOIN companies co ON co.id = cc.company_id "
            "WHERE cc.contact_id = ? AND cc.is_primary = 1 AND cc.is_current = 1 "
            "LIMIT 1",
            (contact_id,),
        ).fetchone()
        if co_row:
            company = {"id": co_row["id"], "name": co_row["name"]}

        # Affiliations
        affs = conn.execute(
            "SELECT cc.*, co.name AS company_name, ccr.name AS role_name "
            "FROM contact_companies cc "
            "JOIN companies co ON co.id = cc.company_id "
            "LEFT JOIN contact_company_roles ccr ON ccr.id = cc.role_id "
            "WHERE cc.contact_id = ? ORDER BY cc.is_current DESC, co.name COLLATE NOCASE",
            (contact_id,),
        ).fetchall()
        affiliations = [
            {
                "company_name": a["company_name"],
                "company_id": a["company_id"],
                "role_name": a["role_name"],
                "title": a["title"],
                "is_current": bool(a["is_current"]),
            }
            for a in affs
        ]

        # Relationships
        rels = conn.execute(
            "SELECT r.*, rt.forward_label, "
            "       COALESCE(c.name, co2.name) AS other_name "
            "FROM relationships r "
            "JOIN relationship_types rt ON rt.id = r.relationship_type_id "
            "LEFT JOIN contacts c ON c.id = r.to_entity_id AND r.to_entity_type = 'contact' "
            "LEFT JOIN companies co2 ON co2.id = r.to_entity_id AND r.to_entity_type = 'company' "
            "WHERE r.from_entity_id = ? ORDER BY r.updated_at DESC",
            (contact_id,),
        ).fetchall()
        relationships = [
            {
                "other_name": r["other_name"] or "Unknown",
                "other_id": r["to_entity_id"],
                "other_entity_type": r["to_entity_type"],
                "label": r["forward_label"],
            }
            for r in rels
        ]

        # Timeline: conversations + events + notes
        timeline = []

        convs = conn.execute(
            "SELECT conv.id, conv.title, conv.last_activity_at, conv.ai_summary "
            "FROM conversations conv "
            "JOIN conversation_participants cp ON cp.conversation_id = conv.id "
            "WHERE cp.contact_id = ? ORDER BY conv.last_activity_at DESC LIMIT 30",
            (contact_id,),
        ).fetchall()
        for c in convs:
            timeline.append({
                "type": "conversation",
                "id": c["id"],
                "title": c["title"] or "Untitled",
                "date": c["last_activity_at"] or "",
                "summary": c["ai_summary"],
            })

        events = conn.execute(
            "SELECT e.id, e.title, COALESCE(e.start_datetime, e.start_date) AS start_dt "
            "FROM events e "
            "JOIN event_participants ep ON ep.event_id = e.id "
            "WHERE ep.entity_type = 'contact' AND ep.entity_id = ? "
            "ORDER BY start_dt DESC LIMIT 20",
            (contact_id,),
        ).fetchall()
        for ev in events:
            timeline.append({
                "type": "event",
                "id": ev["id"],
                "title": ev["title"] or "Untitled",
                "date": ev["start_dt"] or "",
            })

        notes = conn.execute(
            "SELECT n.id, n.title, n.updated_at, nr.content_html "
            "FROM notes n "
            "JOIN note_entities ne ON ne.note_id = n.id "
            "LEFT JOIN note_revisions nr ON nr.id = n.current_revision_id "
            "WHERE ne.entity_type = 'contact' AND ne.entity_id = ? "
            "ORDER BY n.updated_at DESC LIMIT 20",
            (contact_id,),
        ).fetchall()
        for note in notes:
            content = note["content_html"] or ""
            summary = _strip_html(content)[:120]
            timeline.append({
                "type": "note",
                "id": note["id"],
                "title": note["title"] or "Note",
                "date": note["updated_at"] or "",
                "summary": summary,
            })

    # Sort timeline by date descending
    timeline.sort(key=lambda x: x.get("date") or "", reverse=True)

    # Score
    from ...scoring import get_entity_score
    score_data = get_entity_score("contact", contact_id)

    return {
        "identity": {
            "name": contact["name"],
            "subtitle": affiliations[0]["title"] if affiliations and affiliations[0].get("title") else None,
            "emails": emails,
            "phones": phones,
            "addresses": addresses,
            "company": company,
            "source": contact.get("source"),
            "status": contact.get("status"),
            "score": score_data.get("score_value") if score_data else None,
        },
        "context": {
            "affiliations": affiliations,
            "relationships": relationships,
        },
        "timeline": timeline,
    }


@router.get("/companies/{company_id}")
def company_detail_api(request: Request, company_id: str):
    cid = request.state.customer_id

    with get_connection() as conn:
        company = conn.execute(
            "SELECT * FROM companies WHERE id = ?", (company_id,)
        ).fetchone()
        if not company:
            return JSONResponse({"error": "Not found"}, status_code=404)
        company = dict(company)
        if company.get("customer_id") and company["customer_id"] != cid:
            return JSONResponse({"error": "Not found"}, status_code=404)

        # Contacts
        contacts = conn.execute(
            "SELECT c.name, c.id, ci.value AS email, ccr.name AS role_name, "
            "       cc.title AS job_title, cc.is_current "
            "FROM contact_companies cc "
            "JOIN contacts c ON c.id = cc.contact_id "
            "LEFT JOIN contact_identifiers ci ON ci.contact_id = c.id AND ci.type = 'email' AND ci.is_primary = 1 "
            "LEFT JOIN contact_company_roles ccr ON ccr.id = cc.role_id "
            "WHERE cc.company_id = ? ORDER BY cc.is_current DESC, c.name COLLATE NOCASE",
            (company_id,),
        ).fetchall()

        # Phones
        phones_raw = conn.execute(
            "SELECT number FROM phone_numbers "
            "WHERE entity_type = 'company' AND entity_id = ? AND is_current = 1 "
            "ORDER BY is_primary DESC",
            (company_id,),
        ).fetchall()
        phones = [r["number"] for r in phones_raw]

        # Emails
        emails_raw = conn.execute(
            "SELECT address FROM email_addresses "
            "WHERE entity_type = 'company' AND entity_id = ? AND is_current = 1 "
            "ORDER BY is_primary DESC",
            (company_id,),
        ).fetchall()
        emails = [r["address"] for r in emails_raw]

        # Addresses
        addrs_raw = conn.execute(
            "SELECT street, city, state, country, postal_code "
            "FROM addresses WHERE entity_type = 'company' AND entity_id = ? AND is_current = 1",
            (company_id,),
        ).fetchall()
        addresses = [_format_address(dict(a)) for a in addrs_raw]

        # Relationships
        rels = conn.execute(
            "SELECT r.*, rt.forward_label, "
            "       COALESCE(c.name, co2.name) AS other_name "
            "FROM relationships r "
            "JOIN relationship_types rt ON rt.id = r.relationship_type_id "
            "LEFT JOIN contacts c ON c.id = r.to_entity_id AND r.to_entity_type = 'contact' "
            "LEFT JOIN companies co2 ON co2.id = r.to_entity_id AND r.to_entity_type = 'company' "
            "WHERE r.from_entity_id = ? ORDER BY r.updated_at DESC",
            (company_id,),
        ).fetchall()
        relationships = [
            {
                "other_name": r["other_name"] or "Unknown",
                "other_id": r["to_entity_id"],
                "other_entity_type": r["to_entity_type"],
                "label": r["forward_label"],
            }
            for r in rels
        ]

        # Timeline: notes
        timeline = []
        notes = conn.execute(
            "SELECT n.id, n.title, n.updated_at, nr.content_html "
            "FROM notes n "
            "JOIN note_entities ne ON ne.note_id = n.id "
            "LEFT JOIN note_revisions nr ON nr.id = n.current_revision_id "
            "WHERE ne.entity_type = 'company' AND ne.entity_id = ? "
            "ORDER BY n.updated_at DESC LIMIT 20",
            (company_id,),
        ).fetchall()
        for note in notes:
            summary = _strip_html(note["content_html"] or "")[:120]
            timeline.append({
                "type": "note",
                "id": note["id"],
                "title": note["title"] or "Note",
                "date": note["updated_at"] or "",
                "summary": summary,
            })

    from ...scoring import get_entity_score
    score_data = get_entity_score("company", company_id)

    return {
        "identity": {
            "name": company["name"],
            "subtitle": company.get("industry"),
            "emails": emails,
            "phones": phones,
            "addresses": addresses,
            "domain": company.get("domain"),
            "website": company.get("website"),
            "status": company.get("status"),
            "score": score_data.get("score_value") if score_data else None,
        },
        "context": {
            "contacts": [
                {
                    "name": c["name"],
                    "id": c["id"],
                    "email": c["email"],
                    "role_name": c["role_name"],
                    "job_title": c["job_title"],
                    "is_current": bool(c["is_current"]),
                }
                for c in contacts
            ],
            "relationships": relationships,
        },
        "timeline": timeline,
    }


@router.get("/conversations/{conversation_id}")
def conversation_detail_api(request: Request, conversation_id: str):
    cid = request.state.customer_id

    with get_connection() as conn:
        conv = conn.execute(
            "SELECT * FROM conversations WHERE id = ?", (conversation_id,)
        ).fetchone()
        if not conv:
            return JSONResponse({"error": "Not found"}, status_code=404)
        conv = dict(conv)
        if conv.get("customer_id") and conv["customer_id"] != cid:
            return JSONResponse({"error": "Not found"}, status_code=404)

        # Participants
        parts = conn.execute(
            "SELECT cp.email_address, cp.contact_id, cp.name AS participant_name, "
            "       c.name AS contact_name "
            "FROM conversation_participants cp "
            "LEFT JOIN contacts c ON c.id = cp.contact_id "
            "WHERE cp.conversation_id = ?",
            (conversation_id,),
        ).fetchall()

        # Communications
        comms = conn.execute(
            "SELECT comm.id, comm.subject, comm.sender_name, comm.sender_address, "
            "       comm.timestamp, comm.channel, comm.direction, comm.snippet "
            "FROM communications comm "
            "JOIN conversation_communications cc ON cc.communication_id = comm.id "
            "WHERE cc.conversation_id = ? "
            "ORDER BY comm.timestamp DESC LIMIT 50",
            (conversation_id,),
        ).fetchall()

        timeline = []
        for c in comms:
            timeline.append({
                "type": "communication",
                "id": c["id"],
                "title": c["subject"] or "(no subject)",
                "date": c["timestamp"] or "",
                "summary": c["snippet"],
            })

    return {
        "identity": {
            "name": conv.get("title") or "Untitled",
            "subtitle": conv.get("ai_summary"),
            "status": conv.get("status"),
        },
        "context": {
            "participants": [
                {
                    "name": p["contact_name"] or p["participant_name"] or p["email_address"],
                    "contact_id": p["contact_id"],
                }
                for p in parts
            ],
        },
        "timeline": timeline,
    }


# ------------------------------------------------------------------
# Conversation preview / full
# ------------------------------------------------------------------

@router.get("/conversations/{conversation_id}/preview")
def conversation_preview_api(request: Request, conversation_id: str):
    """Rich preview data for the conversation preview card."""
    cid = request.state.customer_id

    with get_connection() as conn:
        conv = conn.execute(
            "SELECT * FROM conversations WHERE id = ?", (conversation_id,)
        ).fetchone()
        if not conv:
            return JSONResponse({"error": "Not found"}, status_code=404)
        conv = dict(conv)
        if conv.get("customer_id") and conv["customer_id"] != cid:
            return JSONResponse({"error": "Not found"}, status_code=404)

        # Participants with optional contact enrichment
        parts = conn.execute(
            "SELECT cp.address, cp.name, cp.contact_id, cp.communication_count, "
            "       cp.last_seen_at, c.name AS contact_name "
            "FROM conversation_participants cp "
            "LEFT JOIN contacts c ON c.id = cp.contact_id "
            "WHERE cp.conversation_id = ? "
            "ORDER BY cp.communication_count DESC, cp.name COLLATE NOCASE",
            (conversation_id,),
        ).fetchall()

        participants = [
            {
                "address": p["address"],
                "name": p["name"],
                "contact_id": p["contact_id"],
                "contact_name": p["contact_name"],
                "communication_count": p["communication_count"] or 0,
                "last_seen_at": p["last_seen_at"],
            }
            for p in parts
        ]

        # Recent communications (last 5, DESC)
        recent_comms = conn.execute(
            "SELECT comm.id, comm.channel, comm.subject, comm.sender_name, "
            "       comm.sender_address, comm.timestamp, comm.snippet, comm.direction "
            "FROM communications comm "
            "JOIN conversation_communications cc ON cc.communication_id = comm.id "
            "WHERE cc.conversation_id = ? "
            "ORDER BY comm.timestamp DESC LIMIT 5",
            (conversation_id,),
        ).fetchall()

        recent_communications = [
            {
                "id": c["id"],
                "channel": c["channel"],
                "subject": c["subject"],
                "sender_name": c["sender_name"],
                "sender_address": c["sender_address"],
                "timestamp": c["timestamp"],
                "snippet": c["snippet"],
                "direction": c["direction"],
            }
            for c in recent_comms
        ]

        # Tags
        tags = [
            {
                "id": t["id"],
                "name": t["name"],
                "source": t["source"],
            }
            for t in conn.execute(
                "SELECT t.id, t.name, ct.source "
                "FROM conversation_tags ct "
                "JOIN tags t ON t.id = ct.tag_id "
                "WHERE ct.conversation_id = ? "
                "ORDER BY t.name COLLATE NOCASE",
                (conversation_id,),
            ).fetchall()
        ]

    return {
        "id": conv["id"],
        "title": conv.get("title"),
        "status": conv.get("status"),
        "communication_count": conv.get("communication_count") or 0,
        "participant_count": conv.get("participant_count") or 0,
        "first_activity_at": conv.get("first_activity_at"),
        "last_activity_at": conv.get("last_activity_at"),
        "ai_summary": conv.get("ai_summary"),
        "ai_status": conv.get("ai_status"),
        "triage_result": conv.get("triage_result"),
        "dismissed": bool(conv.get("dismissed")),
        "participants": participants,
        "recent_communications": recent_communications,
        "tags": tags,
    }


@router.get("/conversations/{conversation_id}/full")
def conversation_full_api(request: Request, conversation_id: str):
    """Full view data for the conversation — enriched participants,
    all communications, events, notes, topic/project, and metadata."""
    cid = request.state.customer_id

    with get_connection() as conn:
        conv = conn.execute(
            "SELECT * FROM conversations WHERE id = ?", (conversation_id,)
        ).fetchone()
        if not conv:
            return JSONResponse({"error": "Not found"}, status_code=404)
        conv = dict(conv)
        if conv.get("customer_id") and conv["customer_id"] != cid:
            return JSONResponse({"error": "Not found"}, status_code=404)

        # Enriched participants (company_name, title from primary affiliation)
        parts = conn.execute(
            "SELECT cp.address, cp.name, cp.contact_id, cp.communication_count, "
            "       cp.first_seen_at, cp.last_seen_at, "
            "       c.name AS contact_name, "
            "       (SELECT co.name FROM companies co "
            "        JOIN contact_companies cc ON cc.company_id = co.id "
            "        WHERE cc.contact_id = cp.contact_id "
            "          AND cc.is_primary = 1 AND cc.is_current = 1 "
            "        LIMIT 1) AS company_name, "
            "       (SELECT cc2.title FROM contact_companies cc2 "
            "        WHERE cc2.contact_id = cp.contact_id "
            "          AND cc2.is_primary = 1 AND cc2.is_current = 1 "
            "        LIMIT 1) AS title "
            "FROM conversation_participants cp "
            "LEFT JOIN contacts c ON c.id = cp.contact_id "
            "WHERE cp.conversation_id = ? "
            "ORDER BY cp.communication_count DESC, cp.name COLLATE NOCASE",
            (conversation_id,),
        ).fetchall()

        participants = [
            {
                "address": p["address"],
                "name": p["name"],
                "contact_id": p["contact_id"],
                "contact_name": p["contact_name"],
                "communication_count": p["communication_count"] or 0,
                "first_seen_at": p["first_seen_at"],
                "last_seen_at": p["last_seen_at"],
                "company_name": p["company_name"],
                "title": p["title"],
            }
            for p in parts
        ]

        # ALL communications, chronological ASC
        # Subqueries: sender contact_id, primary recipient name/count, attachment count
        comms = conn.execute(
            "SELECT comm.id, comm.channel, comm.direction, comm.subject, "
            "       comm.sender_name, comm.sender_address, comm.timestamp, "
            "       comm.snippet, comm.ai_summary, "
            "       cc.is_primary, cc.assignment_source, "
            "       (SELECT cp.contact_id FROM communication_participants cp "
            "        WHERE cp.communication_id = comm.id AND cp.role = 'from' "
            "        LIMIT 1) AS sender_contact_id, "
            "       (SELECT COALESCE(cp.name, cp.address) "
            "        FROM communication_participants cp "
            "        WHERE cp.communication_id = comm.id AND cp.role = 'to' "
            "        ORDER BY cp.name COLLATE NOCASE LIMIT 1) AS recipient_name, "
            "       (SELECT COUNT(*) FROM communication_participants cp "
            "        WHERE cp.communication_id = comm.id "
            "        AND cp.role IN ('to', 'participant')) AS recipient_count, "
            "       (SELECT COUNT(*) FROM attachments a "
            "        WHERE a.communication_id = comm.id) AS attachment_count "
            "FROM communications comm "
            "JOIN conversation_communications cc ON cc.communication_id = comm.id "
            "WHERE cc.conversation_id = ? "
            "ORDER BY comm.timestamp ASC",
            (conversation_id,),
        ).fetchall()

        communications = [
            {
                "id": c["id"],
                "channel": c["channel"],
                "direction": c["direction"],
                "subject": c["subject"],
                "sender_name": c["sender_name"],
                "sender_address": c["sender_address"],
                "timestamp": c["timestamp"],
                "snippet": c["snippet"],
                "ai_summary": c["ai_summary"],
                "is_primary": bool(c["is_primary"]),
                "assignment_source": c["assignment_source"],
                "sender_contact_id": c["sender_contact_id"],
                "recipient_name": c["recipient_name"],
                "recipient_count": c["recipient_count"] or 0,
                "attachment_count": c["attachment_count"] or 0,
            }
            for c in comms
        ]

        # Tags with confidence
        tags = [
            {
                "id": t["id"],
                "name": t["name"],
                "source": t["source"],
                "confidence": t["confidence"],
            }
            for t in conn.execute(
                "SELECT t.id, t.name, ct.source, ct.confidence "
                "FROM conversation_tags ct "
                "JOIN tags t ON t.id = ct.tag_id "
                "WHERE ct.conversation_id = ? "
                "ORDER BY t.name COLLATE NOCASE",
                (conversation_id,),
            ).fetchall()
        ]

        # Events linked via event_conversations
        events = [
            {
                "id": e["id"],
                "title": e["title"],
                "event_type": e["event_type"],
                "start_datetime": e["start_datetime"],
                "status": e["status"],
            }
            for e in conn.execute(
                "SELECT e.id, e.title, e.event_type, e.start_datetime, e.status "
                "FROM event_conversations ec "
                "JOIN events e ON e.id = ec.event_id "
                "WHERE ec.conversation_id = ? "
                "ORDER BY e.start_datetime DESC",
                (conversation_id,),
            ).fetchall()
        ]

        # Notes linked via note_entities
        notes_rows = conn.execute(
            "SELECT n.id, n.title, n.updated_at, ne.is_pinned, "
            "       (SELECT nr.content_html FROM note_revisions nr "
            "        WHERE nr.note_id = n.id "
            "        ORDER BY nr.revision_number DESC LIMIT 1) AS content_html "
            "FROM note_entities ne "
            "JOIN notes n ON n.id = ne.note_id "
            "WHERE ne.entity_type = 'conversation' AND ne.entity_id = ? "
            "ORDER BY ne.is_pinned DESC, n.updated_at DESC",
            (conversation_id,),
        ).fetchall()

        notes = []
        for nr in notes_rows:
            content_html = nr["content_html"] or ""
            # Strip HTML tags for preview, truncate to 200 chars
            preview = re.sub(r"<[^>]+>", "", content_html)[:200]
            notes.append({
                "id": nr["id"],
                "title": nr["title"],
                "content_preview": preview,
                "updated_at": nr["updated_at"],
                "is_pinned": bool(nr["is_pinned"]),
            })

        # Provider account
        provider_account = None
        if conv.get("account_id"):
            pa_row = conn.execute(
                "SELECT id, provider, email_address FROM provider_accounts WHERE id = ?",
                (conv["account_id"],),
            ).fetchone()
            if pa_row:
                provider_account = {
                    "id": pa_row["id"],
                    "provider": pa_row["provider"],
                    "email_address": pa_row["email_address"],
                }

        # Topic / project
        topic = None
        if conv.get("topic_id"):
            topic_row = conn.execute(
                "SELECT t.id, t.name, t.project_id, p.name AS project_name "
                "FROM topics t "
                "LEFT JOIN projects p ON p.id = t.project_id "
                "WHERE t.id = ?",
                (conv["topic_id"],),
            ).fetchone()
            if topic_row:
                topic = {
                    "id": topic_row["id"],
                    "name": topic_row["name"],
                    "project_id": topic_row["project_id"],
                    "project_name": topic_row["project_name"],
                }

        # Created/updated by names
        created_by_name = None
        if conv.get("created_by"):
            u = conn.execute(
                "SELECT name FROM users WHERE id = ?", (conv["created_by"],)
            ).fetchone()
            if u:
                created_by_name = u["name"]

        updated_by_name = None
        if conv.get("updated_by"):
            u = conn.execute(
                "SELECT name FROM users WHERE id = ?", (conv["updated_by"],)
            ).fetchone()
            if u:
                updated_by_name = u["name"]

    return {
        "id": conv["id"],
        "title": conv.get("title"),
        "status": conv.get("status"),
        "communication_count": conv.get("communication_count") or 0,
        "participant_count": conv.get("participant_count") or 0,
        "message_count": conv.get("message_count") or 0,
        "first_activity_at": conv.get("first_activity_at"),
        "last_activity_at": conv.get("last_activity_at"),
        "first_message_at": conv.get("first_message_at"),
        "last_message_at": conv.get("last_message_at"),
        "ai_summary": conv.get("ai_summary"),
        "ai_status": conv.get("ai_status"),
        "ai_action_items": conv.get("ai_action_items"),
        "ai_topics": conv.get("ai_topics"),
        "ai_summarized_at": conv.get("ai_summarized_at"),
        "triage_result": conv.get("triage_result"),
        "dismissed": bool(conv.get("dismissed")),
        "dismissed_reason": conv.get("dismissed_reason"),
        "dismissed_at": conv.get("dismissed_at"),
        "participants": participants,
        "communications": communications,
        "tags": tags,
        "events": events,
        "notes": notes,
        "provider_account": provider_account,
        "topic": topic,
        "created_at": conv.get("created_at"),
        "updated_at": conv.get("updated_at"),
        "created_by_name": created_by_name,
        "updated_by_name": updated_by_name,
    }


@router.get("/events/{event_id}")
def event_detail_api(request: Request, event_id: str):
    with get_connection() as conn:
        event = conn.execute(
            "SELECT * FROM events WHERE id = ?", (event_id,)
        ).fetchone()
        if not event:
            return JSONResponse({"error": "Not found"}, status_code=404)
        event = dict(event)

        parts = conn.execute(
            "SELECT ep.entity_type, ep.entity_id, ep.role, ep.rsvp_status, "
            "       c.name AS contact_name "
            "FROM event_participants ep "
            "LEFT JOIN contacts c ON c.id = ep.entity_id AND ep.entity_type = 'contact' "
            "WHERE ep.event_id = ?",
            (event_id,),
        ).fetchall()

    return {
        "identity": {
            "name": event.get("title") or "Untitled",
            "subtitle": event.get("location"),
            "start": event.get("start_datetime") or event.get("start_date"),
            "end": event.get("end_datetime") or event.get("end_date"),
            "status": event.get("status"),
            "event_type": event.get("event_type"),
        },
        "context": {
            "participants": [
                {
                    "name": p["contact_name"] or p["entity_id"][:8],
                    "contact_id": p["entity_id"] if p["entity_type"] == "contact" else None,
                    "status": p["rsvp_status"],
                }
                for p in parts
            ],
        },
        "timeline": [],
    }


# ------------------------------------------------------------------
# Communication detail
# ------------------------------------------------------------------

@router.get("/communications/{comm_id}")
def communication_detail_api(request: Request, comm_id: str):
    with get_connection() as conn:
        comm = conn.execute(
            "SELECT * FROM communications WHERE id = ?", (comm_id,)
        ).fetchone()
        if not comm:
            return JSONResponse({"error": "Not found"}, status_code=404)
        comm = dict(comm)

    return {
        "identity": {
            "name": comm.get("subject") or "No Subject",
            "subtitle": comm.get("sender_name") or comm.get("sender_address"),
            "channel": comm.get("channel"),
            "direction": comm.get("direction"),
            "timestamp": comm.get("timestamp"),
        },
        "context": {
            "sender": comm.get("sender_address"),
            "snippet": comm.get("snippet"),
            "is_read": comm.get("is_read"),
            "is_archived": comm.get("is_archived"),
        },
        "timeline": [],
    }


@router.get("/communications/{comm_id}/full")
def communication_full_api(request: Request, comm_id: str):
    """Full view data for the communication modal — enriched participants,
    conversation assignment, provider account, notes, and all content fields."""
    with get_connection() as conn:
        comm = conn.execute(
            "SELECT * FROM communications WHERE id = ?", (comm_id,)
        ).fetchone()
        if not comm:
            return JSONResponse({"error": "Not found"}, status_code=404)
        comm = dict(comm)

        # Participants with contact enrichment
        # Detect whether is_account_owner column exists (added post-v17)
        _cp_cols = {
            row[1] for row in conn.execute("PRAGMA table_info(communication_participants)")
        }
        _has_owner_col = "is_account_owner" in _cp_cols
        _owner_select = "cp.is_account_owner" if _has_owner_col else "NULL AS is_account_owner"

        parts = conn.execute(
            f"SELECT cp.address, cp.name, cp.contact_id, cp.role, "
            f"       {_owner_select}, "
            "       c.name AS contact_name, "
            "       (SELECT co.name FROM companies co "
            "        JOIN contact_companies cc ON cc.company_id = co.id "
            "        WHERE cc.contact_id = cp.contact_id "
            "          AND cc.is_primary = 1 AND cc.is_current = 1 "
            "        LIMIT 1) AS company_name, "
            "       (SELECT cc2.title FROM contact_companies cc2 "
            "        WHERE cc2.contact_id = cp.contact_id "
            "          AND cc2.is_primary = 1 AND cc2.is_current = 1 "
            "        LIMIT 1) AS title "
            "FROM communication_participants cp "
            "LEFT JOIN contacts c ON c.id = cp.contact_id "
            "WHERE cp.communication_id = ? "
            "ORDER BY cp.role, cp.name COLLATE NOCASE",
            (comm_id,),
        ).fetchall()

        participants = []
        for p in parts:
            participants.append({
                "address": p["address"],
                "name": p["name"],
                "contact_id": p["contact_id"],
                "role": p["role"],
                "is_account_owner": bool(p["is_account_owner"]) if p["is_account_owner"] is not None else False,
                "contact_name": p["contact_name"],
                "company_name": p["company_name"],
                "title": p["title"],
            })

        # Attachments
        attachments = [
            {
                "id": a["id"],
                "filename": a["filename"],
                "mime_type": a["mime_type"],
                "size_bytes": a["size_bytes"],
            }
            for a in conn.execute(
                "SELECT id, filename, mime_type, size_bytes "
                "FROM attachments WHERE communication_id = ?",
                (comm_id,),
            ).fetchall()
        ]

        # Conversation assignment
        conversation = None
        conv_row = conn.execute(
            "SELECT conv.id, conv.title, conv.status, "
            "       (SELECT COUNT(*) FROM conversation_communications cc2 "
            "        WHERE cc2.conversation_id = conv.id) AS communication_count "
            "FROM conversation_communications cc "
            "JOIN conversations conv ON conv.id = cc.conversation_id "
            "WHERE cc.communication_id = ? LIMIT 1",
            (comm_id,),
        ).fetchone()
        if conv_row:
            conversation = {
                "id": conv_row["id"],
                "title": conv_row["title"],
                "status": conv_row["status"],
                "communication_count": conv_row["communication_count"],
            }

        # Provider account
        provider_account = None
        if comm.get("account_id"):
            pa_row = conn.execute(
                "SELECT id, provider, email_address FROM provider_accounts WHERE id = ?",
                (comm["account_id"],),
            ).fetchone()
            if pa_row:
                provider_account = {
                    "id": pa_row["id"],
                    "provider": pa_row["provider"],
                    "email_address": pa_row["email_address"],
                }

        # Notes — always empty list (note_entities CHECK constraint excludes 'communication')
        notes: list = []

    return {
        "id": comm["id"],
        "channel": comm["channel"],
        "direction": comm.get("direction"),
        "timestamp": comm.get("timestamp"),
        "subject": comm.get("subject"),
        "sender_name": comm.get("sender_name"),
        "sender_address": comm.get("sender_address"),
        "cleaned_html": comm.get("cleaned_html") or comm.get("body_html"),
        "search_text": comm.get("search_text") or comm.get("content"),
        "original_text": comm.get("original_text"),
        "snippet": comm.get("snippet"),
        "source": comm.get("source"),
        "triage_result": comm.get("triage_result"),
        "triage_reason": comm.get("triage_reason"),
        "is_read": bool(comm.get("is_read")),
        "is_archived": bool(comm.get("is_archived")),
        "duration_seconds": comm.get("duration_seconds"),
        "phone_number_from": comm.get("phone_number_from"),
        "phone_number_to": comm.get("phone_number_to"),
        "ai_summary": comm.get("ai_summary"),
        "ai_summarized_at": comm.get("ai_summarized_at"),
        "provider_message_id": comm.get("provider_message_id"),
        "provider_thread_id": comm.get("provider_thread_id"),
        "header_message_id": comm.get("header_message_id"),
        "created_at": comm.get("created_at"),
        "updated_at": comm.get("updated_at"),
        "participants": participants,
        "attachments": attachments,
        "conversation": conversation,
        "provider_account": provider_account,
        "notes": notes,
    }


@router.get("/communications/{comm_id}/preview")
def communication_preview_api(request: Request, comm_id: str):
    """Rich preview data for the communication preview card."""
    with get_connection() as conn:
        comm = conn.execute(
            "SELECT * FROM communications WHERE id = ?", (comm_id,)
        ).fetchone()
        if not comm:
            return JSONResponse({"error": "Not found"}, status_code=404)
        comm = dict(comm)

        # Participants grouped by role
        parts = conn.execute(
            "SELECT address, name, contact_id, role "
            "FROM communication_participants WHERE communication_id = ? "
            "ORDER BY role, name COLLATE NOCASE",
            (comm_id,),
        ).fetchall()

        participants: dict[str, list] = {"from": [], "to": [], "cc": [], "bcc": []}
        for p in parts:
            role = p["role"] if p["role"] in participants else "to"
            participants[role].append({
                "address": p["address"],
                "name": p["name"],
                "contact_id": p["contact_id"],
            })

        # Attachments
        attachments = [
            {
                "id": a["id"],
                "filename": a["filename"],
                "mime_type": a["mime_type"],
                "size_bytes": a["size_bytes"],
            }
            for a in conn.execute(
                "SELECT id, filename, mime_type, size_bytes "
                "FROM attachments WHERE communication_id = ?",
                (comm_id,),
            ).fetchall()
        ]

    return {
        "id": comm["id"],
        "channel": comm["channel"],
        "direction": comm.get("direction"),
        "timestamp": comm.get("timestamp"),
        "subject": comm.get("subject"),
        "sender_name": comm.get("sender_name"),
        "sender_address": comm.get("sender_address"),
        "cleaned_html": comm.get("cleaned_html") or comm.get("body_html"),
        "search_text": comm.get("search_text") or comm.get("content"),
        "snippet": comm.get("snippet"),
        "triage_result": comm.get("triage_result"),
        "is_read": bool(comm.get("is_read")),
        "is_archived": bool(comm.get("is_archived")),
        "duration_seconds": comm.get("duration_seconds"),
        "phone_number_from": comm.get("phone_number_from"),
        "phone_number_to": comm.get("phone_number_to"),
        "participants": participants,
        "attachments": attachments,
    }


# ------------------------------------------------------------------
# Project detail
# ------------------------------------------------------------------

@router.get("/projects/{project_id}")
def project_detail_api(request: Request, project_id: str):
    cid = request.state.customer_id

    with get_connection() as conn:
        project = conn.execute(
            "SELECT * FROM projects WHERE id = ?", (project_id,)
        ).fetchone()
        if not project:
            return JSONResponse({"error": "Not found"}, status_code=404)
        project = dict(project)
        if project.get("customer_id") and project["customer_id"] != cid:
            return JSONResponse({"error": "Not found"}, status_code=404)

        # Owner name
        owner_name = None
        if project.get("owner_id"):
            owner = conn.execute(
                "SELECT name FROM users WHERE id = ?",
                (project["owner_id"],),
            ).fetchone()
            if owner:
                owner_name = owner["name"]

        # Notes linked to this project
        timeline = []
        notes = conn.execute(
            "SELECT n.id, n.title, n.updated_at, nr.content_html "
            "FROM notes n "
            "JOIN note_entities ne ON ne.note_id = n.id "
            "LEFT JOIN note_revisions nr ON nr.id = n.current_revision_id "
            "WHERE ne.entity_type = 'project' AND ne.entity_id = ? "
            "ORDER BY n.updated_at DESC LIMIT 20",
            (project_id,),
        ).fetchall()
        for note in notes:
            summary = _strip_html(note["content_html"] or "")[:120]
            timeline.append({
                "type": "note",
                "id": note["id"],
                "title": note["title"] or "Note",
                "date": note["updated_at"] or "",
                "summary": summary,
            })

    return {
        "identity": {
            "name": project.get("name") or "Untitled",
            "subtitle": project.get("description"),
            "status": project.get("status"),
            "owner": owner_name,
        },
        "context": {},
        "timeline": timeline,
    }


# ------------------------------------------------------------------
# Relationship detail
# ------------------------------------------------------------------

@router.get("/relationships/{relationship_id}")
def relationship_detail_api(request: Request, relationship_id: str):
    with get_connection() as conn:
        rel = conn.execute(
            "SELECT r.*, rt.name AS type_name, rt.forward_label, rt.reverse_label "
            "FROM relationships r "
            "JOIN relationship_types rt ON rt.id = r.relationship_type_id "
            "WHERE r.id = ?",
            (relationship_id,),
        ).fetchone()
        if not rel:
            return JSONResponse({"error": "Not found"}, status_code=404)
        rel = dict(rel)

        # Resolve from entity name
        from_name = _resolve_entity_name(
            conn, rel["from_entity_type"], rel["from_entity_id"],
        )
        to_name = _resolve_entity_name(
            conn, rel["to_entity_type"], rel["to_entity_id"],
        )

    return {
        "identity": {
            "name": f"{from_name} \u2192 {to_name}",
            "subtitle": rel["forward_label"],
            "relationship_type": rel["type_name"],
            "source": rel.get("source"),
        },
        "context": {
            "from": {
                "entity_type": rel["from_entity_type"],
                "entity_id": rel["from_entity_id"],
                "name": from_name,
            },
            "to": {
                "entity_type": rel["to_entity_type"],
                "entity_id": rel["to_entity_id"],
                "name": to_name,
            },
        },
        "timeline": [],
    }


# ------------------------------------------------------------------
# Note detail
# ------------------------------------------------------------------

@router.get("/notes/{note_id}")
def note_detail_api(request: Request, note_id: str):
    cid = request.state.customer_id

    with get_connection() as conn:
        note = conn.execute(
            "SELECT * FROM notes WHERE id = ?", (note_id,)
        ).fetchone()
        if not note:
            return JSONResponse({"error": "Not found"}, status_code=404)
        note = dict(note)
        if note.get("customer_id") and note["customer_id"] != cid:
            return JSONResponse({"error": "Not found"}, status_code=404)

        # Current revision content
        content_html = None
        if note.get("current_revision_id"):
            rev = conn.execute(
                "SELECT content_html FROM note_revisions WHERE id = ?",
                (note["current_revision_id"],),
            ).fetchone()
            if rev:
                content_html = rev["content_html"]

        # Linked entities
        entities = []
        for ne in conn.execute(
            "SELECT entity_type, entity_id, is_pinned FROM note_entities "
            "WHERE note_id = ?",
            (note_id,),
        ).fetchall():
            ename = _resolve_entity_name(conn, ne["entity_type"], ne["entity_id"])
            entities.append({
                "entity_type": ne["entity_type"],
                "entity_id": ne["entity_id"],
                "name": ename,
                "is_pinned": bool(ne["is_pinned"]),
            })

        # Creator name
        creator_name = None
        if note.get("created_by"):
            creator = conn.execute(
                "SELECT name FROM users WHERE id = ?",
                (note["created_by"],),
            ).fetchone()
            if creator:
                creator_name = creator["name"]

    return {
        "identity": {
            "name": note.get("title") or "Untitled Note",
            "subtitle": _strip_html(content_html or "")[:120] if content_html else None,
            "created_by": creator_name,
        },
        "context": {
            "entities": entities,
            "content_html": content_html,
        },
        "timeline": [],
    }


# ------------------------------------------------------------------
# Cross-entity search
# ------------------------------------------------------------------

@router.get("/search")
def search_entities(
    request: Request,
    q: str = Query("", min_length=2),
    limit: int = Query(5, ge=1, le=50),
    entity_type: str | None = Query(None),
):
    cid = request.state.customer_id
    pattern = f"%{q}%"

    # Config per entity type: (label, count_sql, results_sql, params_fn)
    # params_fn returns tuple of params for count and results queries
    _SEARCH_CONFIG: list[dict] = [
        {
            "entity_type": "contact",
            "label": "Contacts",
            "count_sql": (
                "SELECT COUNT(DISTINCT c.id) FROM contacts c "
                "LEFT JOIN contact_identifiers ci ON ci.contact_id = c.id AND ci.type = 'email' "
                "WHERE c.customer_id = ? AND (c.name LIKE ? COLLATE NOCASE OR ci.value LIKE ? COLLATE NOCASE)"
            ),
            "results_sql": (
                "SELECT DISTINCT c.id, c.name, "
                "  (SELECT ci2.value FROM contact_identifiers ci2 "
                "   WHERE ci2.contact_id = c.id AND ci2.type = 'email' "
                "   ORDER BY ci2.is_primary DESC, ci2.created_at ASC LIMIT 1) AS subtitle, "
                "  (SELECT co.name FROM companies co "
                "   JOIN contact_companies cc ON cc.company_id = co.id "
                "   WHERE cc.contact_id = c.id AND cc.is_primary = 1 LIMIT 1) AS secondary "
                "FROM contacts c "
                "LEFT JOIN contact_identifiers ci ON ci.contact_id = c.id AND ci.type = 'email' "
                "WHERE c.customer_id = ? AND (c.name LIKE ? COLLATE NOCASE OR ci.value LIKE ? COLLATE NOCASE) "
                "ORDER BY c.name COLLATE NOCASE LIMIT ?"
            ),
            "count_params": lambda cid, pat: (cid, pat, pat),
            "results_params": lambda cid, pat, lim: (cid, pat, pat, lim),
        },
        {
            "entity_type": "company",
            "label": "Companies",
            "count_sql": (
                "SELECT COUNT(*) FROM companies "
                "WHERE customer_id = ? AND (name LIKE ? COLLATE NOCASE OR domain LIKE ? COLLATE NOCASE)"
            ),
            "results_sql": (
                "SELECT id, name, domain AS subtitle, industry AS secondary "
                "FROM companies "
                "WHERE customer_id = ? AND (name LIKE ? COLLATE NOCASE OR domain LIKE ? COLLATE NOCASE) "
                "ORDER BY name COLLATE NOCASE LIMIT ?"
            ),
            "count_params": lambda cid, pat: (cid, pat, pat),
            "results_params": lambda cid, pat, lim: (cid, pat, pat, lim),
        },
        {
            "entity_type": "conversation",
            "label": "Conversations",
            "count_sql": (
                "SELECT COUNT(*) FROM conversations "
                "WHERE customer_id = ? AND title LIKE ? COLLATE NOCASE"
            ),
            "results_sql": (
                "SELECT id, title AS name, status AS subtitle, last_activity_at AS secondary "
                "FROM conversations "
                "WHERE customer_id = ? AND title LIKE ? COLLATE NOCASE "
                "ORDER BY title COLLATE NOCASE LIMIT ?"
            ),
            "count_params": lambda cid, pat: (cid, pat),
            "results_params": lambda cid, pat, lim: (cid, pat, lim),
        },
        {
            "entity_type": "event",
            "label": "Events",
            "count_sql": (
                "SELECT COUNT(*) FROM events e "
                "JOIN provider_accounts pa ON pa.id = e.account_id "
                "WHERE pa.customer_id = ? AND (e.title LIKE ? COLLATE NOCASE OR e.location LIKE ? COLLATE NOCASE)"
            ),
            "results_sql": (
                "SELECT e.id, e.title AS name, e.location AS subtitle, "
                "  COALESCE(e.start_datetime, e.start_date) AS secondary "
                "FROM events e "
                "JOIN provider_accounts pa ON pa.id = e.account_id "
                "WHERE pa.customer_id = ? AND (e.title LIKE ? COLLATE NOCASE OR e.location LIKE ? COLLATE NOCASE) "
                "ORDER BY e.title COLLATE NOCASE LIMIT ?"
            ),
            "count_params": lambda cid, pat: (cid, pat, pat),
            "results_params": lambda cid, pat, lim: (cid, pat, pat, lim),
        },
        {
            "entity_type": "project",
            "label": "Projects",
            "count_sql": (
                "SELECT COUNT(*) FROM projects "
                "WHERE customer_id = ? AND name LIKE ? COLLATE NOCASE"
            ),
            "results_sql": (
                "SELECT id, name, status AS subtitle, NULL AS secondary "
                "FROM projects "
                "WHERE customer_id = ? AND name LIKE ? COLLATE NOCASE "
                "ORDER BY name COLLATE NOCASE LIMIT ?"
            ),
            "count_params": lambda cid, pat: (cid, pat),
            "results_params": lambda cid, pat, lim: (cid, pat, lim),
        },
        {
            "entity_type": "note",
            "label": "Notes",
            "count_sql": (
                "SELECT COUNT(*) FROM notes "
                "WHERE customer_id = ? AND title LIKE ? COLLATE NOCASE"
            ),
            "results_sql": (
                "SELECT n.id, n.title AS name, "
                "  (SELECT u.name FROM users u WHERE u.id = n.created_by LIMIT 1) AS subtitle, "
                "  n.created_at AS secondary "
                "FROM notes n "
                "WHERE n.customer_id = ? AND n.title LIKE ? COLLATE NOCASE "
                "ORDER BY n.title COLLATE NOCASE LIMIT ?"
            ),
            "count_params": lambda cid, pat: (cid, pat),
            "results_params": lambda cid, pat, lim: (cid, pat, lim),
        },
        {
            "entity_type": "communication",
            "label": "Communications",
            "count_sql": (
                "SELECT COUNT(*) FROM communications comm "
                "JOIN provider_accounts pa ON pa.id = comm.account_id "
                "WHERE pa.customer_id = ? AND (comm.subject LIKE ? COLLATE NOCASE "
                "  OR comm.sender_address LIKE ? COLLATE NOCASE)"
            ),
            "results_sql": (
                "SELECT comm.id, comm.subject AS name, "
                "  COALESCE(comm.sender_name, comm.sender_address) AS subtitle, "
                "  comm.timestamp AS secondary "
                "FROM communications comm "
                "JOIN provider_accounts pa ON pa.id = comm.account_id "
                "WHERE pa.customer_id = ? AND (comm.subject LIKE ? COLLATE NOCASE "
                "  OR comm.sender_address LIKE ? COLLATE NOCASE) "
                "ORDER BY comm.subject COLLATE NOCASE LIMIT ?"
            ),
            "count_params": lambda cid, pat: (cid, pat, pat),
            "results_params": lambda cid, pat, lim: (cid, pat, pat, lim),
        },
    ]

    groups = []
    grand_total = 0

    with get_connection() as conn:
        for cfg in _SEARCH_CONFIG:
            if entity_type and cfg["entity_type"] != entity_type:
                continue

            total = conn.execute(
                cfg["count_sql"], cfg["count_params"](cid, pattern)
            ).fetchone()[0]

            if total == 0:
                continue

            rows = conn.execute(
                cfg["results_sql"], cfg["results_params"](cid, pattern, limit)
            ).fetchall()

            results = []
            for r in rows:
                item = {"id": r["id"], "name": r["name"]}
                if r["subtitle"]:
                    item["subtitle"] = r["subtitle"]
                if r["secondary"]:
                    item["secondary"] = r["secondary"]
                results.append(item)

            groups.append({
                "entity_type": cfg["entity_type"],
                "label": cfg["label"],
                "total": total,
                "results": results,
            })
            grand_total += total

    return {"groups": groups, "total": grand_total}


# ------------------------------------------------------------------
# Settings: Profile
# ------------------------------------------------------------------

@router.get("/settings/profile")
def settings_profile(request: Request):
    """Return current user's profile and preferences."""
    from ...hierarchy import get_user_by_id
    from ...settings import get_setting

    user = request.state.user
    cid = user["customer_id"]
    uid = user["id"]

    # Read fresh from DB so updates are reflected immediately
    fresh = get_user_by_id(uid) or user

    return {
        "id": uid,
        "name": fresh.get("name", ""),
        "email": fresh.get("email", ""),
        "role": fresh.get("role", "user"),
        "timezone": get_setting(cid, "timezone", user_id=uid) or "UTC",
        "start_of_week": get_setting(cid, "start_of_week", user_id=uid) or "monday",
        "date_format": get_setting(cid, "date_format", user_id=uid) or "ISO",
    }


@router.put("/settings/profile")
async def settings_profile_update(request: Request):
    """Update current user's profile and preferences."""
    from ...hierarchy import update_user
    from ...settings import set_setting

    user = request.state.user
    cid = user["customer_id"]
    uid = user["id"]

    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)

    name = body.get("name", "").strip()
    if name:
        update_user(uid, name=name)

    tz = body.get("timezone")
    if tz is not None:
        set_setting(cid, "timezone", tz, scope="user", user_id=uid)

    sow = body.get("start_of_week")
    if sow is not None:
        set_setting(cid, "start_of_week", sow, scope="user", user_id=uid)

    df = body.get("date_format")
    if df is not None:
        set_setting(cid, "date_format", df, scope="user", user_id=uid)

    return {"ok": True}


@router.put("/settings/password")
async def settings_password(request: Request):
    """Change the current user's password."""
    from ...hierarchy import set_user_password
    from ...passwords import verify_password

    user = request.state.user

    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)

    current_pw = body.get("current_password", "")
    new_pw = body.get("new_password", "")
    confirm_pw = body.get("confirm_password", "")

    if new_pw != confirm_pw:
        return JSONResponse({"error": "Passwords do not match"}, status_code=400)
    if len(new_pw) < 8:
        return JSONResponse(
            {"error": "Password must be at least 8 characters"}, status_code=400,
        )

    if user.get("password_hash"):
        if not verify_password(current_pw, user["password_hash"]):
            return JSONResponse(
                {"error": "Current password is incorrect"}, status_code=400,
            )

    set_user_password(user["id"], new_pw)
    return {"ok": True}


# ------------------------------------------------------------------
# Settings: System (admin only)
# ------------------------------------------------------------------

@router.get("/settings/system")
def settings_system(request: Request):
    """Return system settings (admin only)."""
    if request.state.user["role"] != "admin":
        return JSONResponse({"error": "Forbidden"}, status_code=403)

    from ...settings import get_setting

    cid = request.state.customer_id

    return {
        "company_name": get_setting(cid, "company_name") or "",
        "default_timezone": get_setting(cid, "default_timezone") or "UTC",
        "sync_enabled": get_setting(cid, "sync_enabled") or "true",
        "default_phone_country": get_setting(cid, "default_phone_country") or "US",
        "allow_self_registration": get_setting(cid, "allow_self_registration") or "false",
        "email_history_window": get_setting(cid, "email_history_window") or "90d",
    }


@router.put("/settings/system")
async def settings_system_update(request: Request):
    """Update system settings (admin only)."""
    if request.state.user["role"] != "admin":
        return JSONResponse({"error": "Forbidden"}, status_code=403)

    from ...settings import set_setting

    cid = request.state.customer_id

    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)

    _SYSTEM_KEYS = [
        "company_name", "default_timezone", "sync_enabled",
        "default_phone_country", "allow_self_registration", "email_history_window",
    ]
    for key in _SYSTEM_KEYS:
        val = body.get(key)
        if val is not None:
            set_setting(cid, key, str(val), scope="system")

    return {"ok": True}


# ------------------------------------------------------------------
# Settings: Users (admin only)
# ------------------------------------------------------------------

@router.get("/settings/users")
def settings_users(request: Request):
    """List all users (admin only)."""
    if request.state.user["role"] != "admin":
        return JSONResponse({"error": "Forbidden"}, status_code=403)

    from ...hierarchy import list_users

    cid = request.state.customer_id
    users = list_users(cid)
    # Strip password hashes from output
    for u in users:
        u.pop("password_hash", None)
        u.pop("google_sub", None)
    return users


@router.post("/settings/users")
async def settings_user_create(request: Request):
    """Create a new user (admin only)."""
    if request.state.user["role"] != "admin":
        return JSONResponse({"error": "Forbidden"}, status_code=403)

    from ...hierarchy import create_user

    cid = request.state.customer_id

    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)

    email = (body.get("email") or "").strip()
    name = (body.get("name") or "").strip()
    role = body.get("role", "user")
    password = body.get("password", "")

    if not email:
        return JSONResponse({"error": "Email is required"}, status_code=400)
    if password and len(password) < 8:
        return JSONResponse(
            {"error": "Password must be at least 8 characters"}, status_code=400,
        )

    try:
        user_row = create_user(cid, email, name, role, password=password or None)
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)

    user_row.pop("password_hash", None)
    user_row.pop("google_sub", None)
    return user_row


@router.put("/settings/users/{user_id}")
async def settings_user_update(request: Request, user_id: str):
    """Update a user (admin only)."""
    if request.state.user["role"] != "admin":
        return JSONResponse({"error": "Forbidden"}, status_code=403)

    from ...hierarchy import update_user

    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)

    kwargs = {}
    if "name" in body:
        kwargs["name"] = body["name"]
    if "role" in body:
        kwargs["role"] = body["role"]

    result = update_user(user_id, **kwargs)
    if not result:
        return JSONResponse({"error": "User not found or no changes"}, status_code=404)

    result.pop("password_hash", None)
    result.pop("google_sub", None)
    return result


@router.put("/settings/users/{user_id}/password")
async def settings_user_password(request: Request, user_id: str):
    """Set a user's password (admin only)."""
    if request.state.user["role"] != "admin":
        return JSONResponse({"error": "Forbidden"}, status_code=403)

    from ...hierarchy import set_user_password

    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)

    new_pw = body.get("new_password", "")
    if len(new_pw) < 8:
        return JSONResponse(
            {"error": "Password must be at least 8 characters"}, status_code=400,
        )

    set_user_password(user_id, new_pw)
    return {"ok": True}


@router.post("/settings/users/{user_id}/toggle-active")
def settings_user_toggle_active(request: Request, user_id: str):
    """Toggle a user's active status (admin only)."""
    if request.state.user["role"] != "admin":
        return JSONResponse({"error": "Forbidden"}, status_code=403)

    from ...hierarchy import get_user_by_id, update_user
    from ...session import delete_user_sessions

    current_user = request.state.user
    if user_id == current_user["id"]:
        return JSONResponse(
            {"error": "Cannot deactivate yourself"}, status_code=400,
        )

    target = get_user_by_id(user_id)
    if not target:
        return JSONResponse({"error": "User not found"}, status_code=404)

    new_active = 0 if target["is_active"] else 1
    update_user(user_id, is_active=new_active)

    if not new_active:
        delete_user_sessions(user_id)

    return {"ok": True, "is_active": new_active}


# ------------------------------------------------------------------
# Settings: Provider Accounts
# ------------------------------------------------------------------

@router.get("/settings/accounts")
def settings_accounts(request: Request):
    """List provider accounts for the current user."""
    uid = request.state.user["id"]
    cid = request.state.customer_id

    with get_connection() as conn:
        rows = conn.execute(
            """SELECT pa.* FROM provider_accounts pa
               JOIN user_provider_accounts upa ON upa.account_id = pa.id
               WHERE upa.user_id = ?
               ORDER BY pa.created_at""",
            (uid,),
        ).fetchall()
        accounts = [dict(r) for r in rows]

    if not accounts:
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM provider_accounts WHERE customer_id = ? ORDER BY created_at",
                (cid,),
            ).fetchall()
            accounts = [dict(r) for r in rows]

    # Strip sensitive fields
    for a in accounts:
        a.pop("auth_token_path", None)
        a.pop("refresh_token", None)

    return accounts


@router.put("/settings/accounts/{account_id}")
async def settings_account_update(request: Request, account_id: str):
    """Update a provider account's display name."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)

    display_name = (body.get("display_name") or "").strip()
    now = datetime.now(timezone.utc).isoformat()

    with get_connection() as conn:
        account = conn.execute(
            "SELECT id FROM provider_accounts WHERE id = ?",
            (account_id,),
        ).fetchone()
        if not account:
            return JSONResponse({"error": "Account not found"}, status_code=404)

        conn.execute(
            "UPDATE provider_accounts SET display_name = ?, updated_at = ? WHERE id = ?",
            (display_name or None, now, account_id),
        )

    return {"ok": True}


@router.post("/settings/accounts/{account_id}/toggle-active")
def settings_account_toggle(request: Request, account_id: str):
    """Toggle a provider account's active status."""
    now = datetime.now(timezone.utc).isoformat()

    with get_connection() as conn:
        account = conn.execute(
            "SELECT * FROM provider_accounts WHERE id = ?",
            (account_id,),
        ).fetchone()
        if not account:
            return JSONResponse({"error": "Account not found"}, status_code=404)

        new_active = 0 if account["is_active"] else 1
        conn.execute(
            "UPDATE provider_accounts SET is_active = ?, updated_at = ? WHERE id = ?",
            (new_active, now, account_id),
        )

    return {"ok": True, "is_active": new_active}


# ------------------------------------------------------------------
# Settings: Calendars
# ------------------------------------------------------------------

@router.get("/settings/calendars")
def settings_calendars(request: Request):
    """List calendar accounts with selected calendars."""
    uid = request.state.user["id"]
    cid = request.state.customer_id

    from ...settings import get_setting

    with get_connection() as conn:
        rows = conn.execute(
            """SELECT pa.* FROM provider_accounts pa
               JOIN user_provider_accounts upa ON upa.account_id = pa.id
               WHERE upa.user_id = ? AND pa.provider = 'gmail' AND pa.is_active = 1
               ORDER BY pa.created_at""",
            (uid,),
        ).fetchall()

    def _normalize_calendars(raw):
        """Normalize stored calendar entries to [{id, summary}] format."""
        result = []
        for entry in raw:
            if isinstance(entry, dict):
                result.append({"id": entry["id"], "summary": entry.get("summary", entry["id"])})
            else:
                result.append({"id": entry, "summary": entry})
        return result

    def _build_account(row):
        account = dict(row)
        cal_key = f"cal_sync_calendars_{account['id']}"
        cal_json = get_setting(cid, cal_key, user_id=uid)
        try:
            raw = json.loads(cal_json) if cal_json else []
        except (json.JSONDecodeError, TypeError):
            raw = []
        account["selected_calendars"] = _normalize_calendars(raw)
        account.pop("auth_token_path", None)
        account.pop("refresh_token", None)
        return account

    accounts = [_build_account(row) for row in rows]

    if not accounts:
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM provider_accounts WHERE customer_id = ? AND provider = 'gmail' AND is_active = 1 ORDER BY created_at",
                (cid,),
            ).fetchall()
        accounts = [_build_account(row) for row in rows]

    return accounts


@router.post("/settings/calendars/{account_id}/fetch")
def settings_calendars_fetch(request: Request, account_id: str):
    """Fetch available calendars for an account (requires Google credentials)."""
    with get_connection() as conn:
        account = conn.execute(
            "SELECT * FROM provider_accounts WHERE id = ?",
            (account_id,),
        ).fetchone()

    if not account:
        return JSONResponse({"error": "Account not found"}, status_code=404)

    try:
        from ...auth import get_credentials_for_account
        from ...calendar_client import list_calendars
        from pathlib import Path

        token_path = Path(account["auth_token_path"])
        creds = get_credentials_for_account(token_path)
        calendars = list_calendars(creds)
    except Exception as exc:
        return JSONResponse(
            {"error": f"Failed to load calendars: {exc}"}, status_code=500,
        )

    return {"calendars": [dict(c) if hasattr(c, "__getitem__") else c for c in calendars]}


@router.put("/settings/calendars/{account_id}")
async def settings_calendars_save(request: Request, account_id: str):
    """Save selected calendar IDs for an account."""
    from ...settings import set_setting

    uid = request.state.user["id"]
    cid = request.state.customer_id

    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)

    # Accept rich format (list of {id, summary} dicts) or legacy (list of strings)
    calendar_entries = body.get("calendar_entries")
    if calendar_entries is not None:
        value = calendar_entries
    else:
        value = body.get("calendar_ids", [])

    cal_key = f"cal_sync_calendars_{account_id}"
    set_setting(cid, cal_key, json.dumps(value), scope="user", user_id=uid)
<<<<<<< Updated upstream
<<<<<<< Updated upstream

    return {"ok": True}


# ------------------------------------------------------------------
# Settings: Roles
# ------------------------------------------------------------------

@router.get("/settings/roles")
def settings_roles_list(request: Request):
    """List all contact-company roles for the customer."""
    from ...contact_company_roles import list_roles
    cid = request.state.customer_id
    return list_roles(customer_id=cid)


@router.post("/settings/roles")
async def settings_roles_create(request: Request):
    """Create a new custom role."""
    if request.state.user["role"] != "admin":
        return JSONResponse({"error": "Forbidden"}, status_code=403)

    from ...contact_company_roles import create_role

    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)

    name = (body.get("name") or "").strip()
    if not name:
        return JSONResponse({"error": "Name is required"}, status_code=400)

    sort_order = body.get("sort_order", 0)
    cid = request.state.customer_id
    uid = request.state.user["id"]

    try:
        role = create_role(name, customer_id=cid, sort_order=sort_order, created_by=uid)
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=409)

    return role


@router.put("/settings/roles/{role_id}")
async def settings_roles_update(request: Request, role_id: str):
    """Update a custom role's name or sort_order."""
    if request.state.user["role"] != "admin":
        return JSONResponse({"error": "Forbidden"}, status_code=403)

    from ...contact_company_roles import update_role

    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)

    name = body.get("name")
    if name is not None:
        name = name.strip()
        if not name:
            return JSONResponse({"error": "Name cannot be empty"}, status_code=400)

    sort_order = body.get("sort_order")
    uid = request.state.user["id"]

    try:
        role = update_role(role_id, name=name, sort_order=sort_order, updated_by=uid)
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)

    if role is None:
        return JSONResponse({"error": "Role not found"}, status_code=404)

    return role


@router.delete("/settings/roles/{role_id}")
def settings_roles_delete(request: Request, role_id: str):
    """Delete a custom role."""
    if request.state.user["role"] != "admin":
        return JSONResponse({"error": "Forbidden"}, status_code=403)

    from ...contact_company_roles import delete_role

    try:
        delete_role(role_id)
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
=======
>>>>>>> Stashed changes
=======
>>>>>>> Stashed changes

    return {"ok": True}


# ------------------------------------------------------------------
# Settings: Reference Data
# ------------------------------------------------------------------

@router.get("/settings/reference-data")
def settings_reference_data(request: Request):
    """Return shared reference data for settings forms."""
    from ..routes.settings_routes import COMMON_COUNTRIES, COMMON_TIMEZONES
    from ...sync import EMAIL_HISTORY_OPTIONS

    with get_connection() as conn:
        roles = conn.execute(
            "SELECT * FROM contact_company_roles ORDER BY name COLLATE NOCASE",
        ).fetchall()

    return {
        "timezones": COMMON_TIMEZONES,
        "countries": [{"code": c, "name": n} for c, n in COMMON_COUNTRIES],
        "email_history_options": [{"value": v, "label": l} for v, l in EMAIL_HISTORY_OPTIONS],
        "roles": [dict(r) for r in roles],
        "google_oauth_configured": bool(config.GOOGLE_OAUTH_CLIENT_ID),
    }


# ------------------------------------------------------------------
# Outbound Email
# ------------------------------------------------------------------

@router.post("/outbound-emails")
async def outbound_create(request: Request):
    """Create a draft or send immediately."""
    from ...outbound import create_draft, send_email

    cid = request.state.customer_id
    uid = request.state.user["id"]
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)

    to_addresses = body.get("to_addresses", [])
    if not to_addresses:
        return JSONResponse({"error": "to_addresses is required"}, status_code=400)
    if not body.get("subject"):
        return JSONResponse({"error": "subject is required"}, status_code=400)
    if not body.get("from_account_id"):
        return JSONResponse({"error": "from_account_id is required"}, status_code=400)

    with get_connection() as conn:
        draft = create_draft(
            conn,
            customer_id=cid,
            user_id=uid,
            from_account_id=body["from_account_id"],
            to_addresses=to_addresses,
            cc_addresses=body.get("cc_addresses"),
            bcc_addresses=body.get("bcc_addresses"),
            subject=body["subject"],
            body_json=body.get("body_json", "{}"),
            body_html=body.get("body_html", ""),
            body_text=body.get("body_text", ""),
            source_type=body.get("source_type", "manual"),
            reply_to_communication_id=body.get("reply_to_communication_id"),
            forward_of_communication_id=body.get("forward_of_communication_id"),
            conversation_id=body.get("conversation_id"),
            signature_id=body.get("signature_id"),
        )

        # If send_immediately, send right away
        if body.get("send_immediately"):
            try:
                result = send_email(conn, queue_id=draft["id"], user_id=uid)
                if result.get("status") == "failed":
                    return JSONResponse(result, status_code=502)
                return result
            except Exception as exc:
                return JSONResponse(
                    {"error": str(exc), "draft_id": draft["id"]},
                    status_code=500,
                )

        return draft


@router.get("/outbound-emails/drafts")
def outbound_list_drafts(request: Request):
    """List user's drafts."""
    from ...outbound import list_drafts

    cid = request.state.customer_id
    uid = request.state.user["id"]
    with get_connection() as conn:
        return list_drafts(conn, user_id=uid, customer_id=cid)


@router.get("/outbound-emails/compose-context")
def outbound_compose_context(
    request: Request,
    communication_id: str = Query(...),
    action: str = Query(...),
):
    """Get reply/forward context for a communication."""
    from ...outbound import get_compose_context

    if action not in ("reply", "reply_all", "forward"):
        return JSONResponse({"error": "action must be reply, reply_all, or forward"}, status_code=400)

    cid = request.state.customer_id
    uid = request.state.user["id"]
    with get_connection() as conn:
        ctx = get_compose_context(
            conn,
            communication_id=communication_id,
            action=action,
            user_id=uid,
            customer_id=cid,
        )
    if ctx.get("error"):
        return JSONResponse(ctx, status_code=404)
    return ctx


@router.post("/outbound-emails/resolve-sender")
async def outbound_resolve_sender(request: Request):
    """Get smart default sending account."""
    from ...outbound import resolve_sending_account

    cid = request.state.customer_id
    uid = request.state.user["id"]
    try:
        body = await request.json()
    except Exception:
        body = {}

    with get_connection() as conn:
        account_id = resolve_sending_account(
            conn,
            user_id=uid,
            customer_id=cid,
            reply_to_comm_id=body.get("reply_to_communication_id"),
            to_email=body.get("to_email"),
        )
    if not account_id:
        return JSONResponse({"error": "No sending account available"}, status_code=404)

    with get_connection() as conn:
        acct = conn.execute(
            "SELECT id, email_address, display_name FROM provider_accounts WHERE id = ?",
            (account_id,),
        ).fetchone()

    return dict(acct) if acct else {"id": account_id}


@router.get("/outbound-emails/{email_id}")
def outbound_get(request: Request, email_id: str):
    """Get draft/sent detail."""
    from ...outbound import get_queue_record

    uid = request.state.user["id"]
    with get_connection() as conn:
        record = get_queue_record(conn, queue_id=email_id)
    if not record:
        return JSONResponse({"error": "Not found"}, status_code=404)
    if record["created_by"] != uid:
        return JSONResponse({"error": "Forbidden"}, status_code=403)
    return record


@router.patch("/outbound-emails/{email_id}")
async def outbound_update(request: Request, email_id: str):
    """Update draft fields."""
    from ...outbound import update_draft

    uid = request.state.user["id"]
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)

    with get_connection() as conn:
        result = update_draft(conn, draft_id=email_id, user_id=uid, **body)
    if not result:
        return JSONResponse({"error": "Not found or not editable"}, status_code=404)
    return result


@router.post("/outbound-emails/{email_id}/send")
def outbound_send(request: Request, email_id: str):
    """Send a draft."""
    from ...outbound import send_email

    uid = request.state.user["id"]
    with get_connection() as conn:
        try:
            result = send_email(conn, queue_id=email_id, user_id=uid)
            if result.get("status") == "failed":
                return JSONResponse(result, status_code=502)
            return result
        except ValueError as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)
        except Exception as exc:
            return JSONResponse({"error": str(exc)}, status_code=500)


@router.post("/outbound-emails/{email_id}/cancel")
def outbound_cancel(request: Request, email_id: str):
    """Cancel a draft."""
    from ...outbound import cancel_draft

    uid = request.state.user["id"]
    with get_connection() as conn:
        ok = cancel_draft(conn, queue_id=email_id, user_id=uid)
    if not ok:
        return JSONResponse({"error": "Not found or cannot cancel"}, status_code=400)
    return {"ok": True}


# ------------------------------------------------------------------
# Signatures
# ------------------------------------------------------------------

@router.get("/signatures")
def signatures_list(request: Request):
    """List user's signatures."""
    from ...outbound import list_signatures

    uid = request.state.user["id"]
    with get_connection() as conn:
        return list_signatures(conn, user_id=uid)


@router.post("/signatures")
async def signatures_create(request: Request):
    """Create a signature."""
    from ...outbound import create_signature

    cid = request.state.customer_id
    uid = request.state.user["id"]
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)

    name = (body.get("name") or "").strip()
    if not name:
        return JSONResponse({"error": "name is required"}, status_code=400)

    with get_connection() as conn:
        sig = create_signature(
            conn,
            customer_id=cid,
            user_id=uid,
            name=name,
            body_json=body.get("body_json", "{}"),
            body_html=body.get("body_html", ""),
            provider_account_id=body.get("provider_account_id"),
            is_default=bool(body.get("is_default")),
        )
    return sig


@router.get("/signatures/{sig_id}")
def signatures_get(request: Request, sig_id: str):
    """Get signature detail."""
    from ...outbound import get_signature

    uid = request.state.user["id"]
    with get_connection() as conn:
        sig = get_signature(conn, signature_id=sig_id)
    if not sig or sig["user_id"] != uid:
        return JSONResponse({"error": "Not found"}, status_code=404)
    return sig


@router.patch("/signatures/{sig_id}")
async def signatures_update(request: Request, sig_id: str):
    """Update a signature."""
    from ...outbound import update_signature

    uid = request.state.user["id"]
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)

    with get_connection() as conn:
        result = update_signature(conn, signature_id=sig_id, user_id=uid, **body)
    if not result:
        return JSONResponse({"error": "Not found"}, status_code=404)
    return result


@router.delete("/signatures/{sig_id}")
def signatures_delete(request: Request, sig_id: str):
    """Delete a signature."""
    from ...outbound import delete_signature

    uid = request.state.user["id"]
    with get_connection() as conn:
        ok = delete_signature(conn, signature_id=sig_id, user_id=uid)
    if not ok:
        return JSONResponse({"error": "Not found"}, status_code=404)
    return {"ok": True}


# ------------------------------------------------------------------
# Provider Account Reauthorization
# ------------------------------------------------------------------

@router.post("/settings/accounts/{account_id}/reauthorize")
def settings_account_reauthorize(request: Request, account_id: str):
    """Check if account needs reauthorization for send scope."""
    uid = request.state.user["id"]

    with get_connection() as conn:
        acct = conn.execute(
            """SELECT pa.* FROM provider_accounts pa
               JOIN user_provider_accounts upa ON upa.account_id = pa.id
               WHERE pa.id = ? AND upa.user_id = ?""",
            (account_id, uid),
        ).fetchone()

    if not acct:
        return JSONResponse({"error": "Account not found"}, status_code=404)

    acct = dict(acct)

    # Check if token already has send scope
    token_path = Path(acct["auth_token_path"]) if acct.get("auth_token_path") else None
    has_send_scope = False

    if token_path and token_path.exists():
        try:
            import json as json_mod
            token_data = json_mod.loads(token_path.read_text())
            scopes = token_data.get("scopes", [])
            has_send_scope = any("gmail.send" in s for s in scopes)
        except Exception:
            pass

    if has_send_scope:
        return {"needs_reauth": False, "has_send_scope": True}

    # Build OAuth URL for reauthorization
    if not config.CLIENT_SECRET_PATH.exists():
        return JSONResponse(
            {"error": "OAuth client secret not configured"}, status_code=500,
        )

    try:
        import json as json_mod
        client_data = json_mod.loads(config.CLIENT_SECRET_PATH.read_text())
        installed = client_data.get("installed", {})
        client_id = installed.get("client_id", "")

        # Build consent URL with all scopes including gmail.send
        from urllib.parse import urlencode
        params = urlencode({
            "client_id": client_id,
            "redirect_uri": "urn:ietf:wg:oauth:2.0:oob",
            "scope": " ".join(config.GOOGLE_SCOPES),
            "response_type": "code",
            "access_type": "offline",
            "prompt": "consent",
        })
        auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?{params}"

        return {
            "needs_reauth": True,
            "has_send_scope": False,
            "auth_url": auth_url,
            "email": acct.get("email_address"),
        }
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _format_address(addr: dict) -> str:
    """Format an address dict as a compact multi-line string."""
    parts = []
    street = addr.get("street", "")
    if street:
        parts.append(street)
    city_state = []
    if addr.get("city"):
        city_state.append(addr["city"])
    if addr.get("state"):
        city_state.append(addr["state"])
    csz = ", ".join(city_state)
    if addr.get("postal_code"):
        csz += " " + addr["postal_code"]
    if csz.strip():
        parts.append(csz.strip())
    if addr.get("country") and addr["country"] not in ("US", "USA", "United States"):
        parts.append(addr["country"])
    return "\n".join(parts)


import re
_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(html: str) -> str:
    """Strip HTML tags for plain-text summaries."""
    return _TAG_RE.sub("", html).strip()


def _resolve_entity_name(
    conn, entity_type: str, entity_id: str,
) -> str:
    """Look up a human-readable name for any entity type."""
    _TABLE_MAP = {
        "contact": ("contacts", "name"),
        "company": ("companies", "name"),
        "conversation": ("conversations", "title"),
        "event": ("events", "title"),
        "project": ("projects", "name"),
    }
    spec = _TABLE_MAP.get(entity_type)
    if not spec:
        return entity_id[:8]
    table, col = spec
    row = conn.execute(
        f"SELECT {col} FROM {table} WHERE id = ?", (entity_id,)
    ).fetchone()
    return row[col] if row else entity_id[:8]
