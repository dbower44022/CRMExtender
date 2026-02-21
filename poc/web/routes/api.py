"""JSON API routes for the React frontend (/api/v1/)."""

from __future__ import annotations

import json
import re
from dataclasses import asdict

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
from ...views.registry import ENTITY_TYPES

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
def search_entities(request: Request, q: str = Query("", min_length=2)):
    cid = request.state.customer_id
    results = []
    pattern = f"%{q}%"

    with get_connection() as conn:
        # Contacts
        for r in conn.execute(
            "SELECT c.id, c.name FROM contacts c "
            "WHERE c.customer_id = ? AND c.name LIKE ? LIMIT 10",
            (cid, pattern),
        ).fetchall():
            results.append({
                "entity_type": "contact",
                "id": r["id"],
                "name": r["name"],
            })

        # Contact by email
        for r in conn.execute(
            "SELECT ci.contact_id, ci.value, c.name "
            "FROM contact_identifiers ci "
            "JOIN contacts c ON c.id = ci.contact_id "
            "WHERE c.customer_id = ? AND ci.type = 'email' AND ci.value LIKE ? LIMIT 5",
            (cid, pattern),
        ).fetchall():
            if not any(x["id"] == r["contact_id"] for x in results):
                results.append({
                    "entity_type": "contact",
                    "id": r["contact_id"],
                    "name": r["name"],
                    "subtitle": r["value"],
                })

        # Companies
        for r in conn.execute(
            "SELECT id, name, domain FROM companies "
            "WHERE customer_id = ? AND (name LIKE ? OR domain LIKE ?) LIMIT 10",
            (cid, pattern, pattern),
        ).fetchall():
            results.append({
                "entity_type": "company",
                "id": r["id"],
                "name": r["name"],
                "subtitle": r["domain"],
            })

        # Conversations
        for r in conn.execute(
            "SELECT id, title FROM conversations "
            "WHERE customer_id = ? AND title LIKE ? LIMIT 10",
            (cid, pattern),
        ).fetchall():
            results.append({
                "entity_type": "conversation",
                "id": r["id"],
                "name": r["title"],
            })

    return {"results": results, "total": len(results)}


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
