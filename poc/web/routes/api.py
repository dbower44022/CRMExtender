"""JSON API routes for the React frontend (/api/v1/)."""

from __future__ import annotations

import json
from dataclasses import asdict

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse

from ...database import get_connection
from ...views.crud import (
    get_default_view_for_entity,
    get_view_with_config,
    get_views_for_entity,
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
            fd.pop("db_column", None)
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
):
    cid = request.state.customer_id
    uid = request.state.user["id"] if request.state.user else ""

    with get_connection() as conn:
        view = get_view_with_config(conn, view_id)
        if not view:
            return JSONResponse({"error": "View not found"}, status_code=404)

        rows, total = execute_view(
            conn,
            entity_type=view["entity_type"],
            columns=view["columns"],
            filters=view["filters"],
            sort_field=sort or view.get("sort_field"),
            sort_direction=sort_direction if sort else view.get("sort_direction", "asc"),
            search=search,
            page=page,
            per_page=view.get("per_page", 50),
            customer_id=cid,
            user_id=uid,
            scope=scope,
        )

    return {
        "rows": rows,
        "total": total,
        "page": page,
        "per_page": view.get("per_page", 50),
    }


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
            "WHERE cc.contact_id = ? ORDER BY cc.is_current DESC, co.name",
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
            "WHERE cc.company_id = ? ORDER BY cc.is_current DESC, c.name",
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
