"""Contact routes — list, search, detail."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from ...database import get_connection

router = APIRouter()


def _list_contacts(*, search: str = "", page: int = 1, per_page: int = 50):
    clauses = []
    params: list = []

    if search:
        clauses.append("(c.name LIKE ? OR ci.value LIKE ? OR co.name LIKE ?)")
        params.extend([f"%{search}%", f"%{search}%", f"%{search}%"])

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""

    with get_connection() as conn:
        total = conn.execute(
            f"""SELECT COUNT(DISTINCT c.id) AS cnt
                FROM contacts c
                LEFT JOIN contact_identifiers ci ON ci.contact_id = c.id AND ci.type = 'email'
                LEFT JOIN companies co ON co.id = c.company_id
                {where}""",
            params,
        ).fetchone()["cnt"]

        offset = (page - 1) * per_page
        rows = conn.execute(
            f"""SELECT c.*, ci.value AS email, co.name AS company_name
                FROM contacts c
                LEFT JOIN contact_identifiers ci ON ci.contact_id = c.id AND ci.type = 'email'
                LEFT JOIN companies co ON co.id = c.company_id
                {where}
                ORDER BY c.name
                LIMIT ? OFFSET ?""",
            params + [per_page, offset],
        ).fetchall()

    return [dict(r) for r in rows], total


@router.get("", response_class=HTMLResponse)
def contact_list(request: Request, q: str = "", page: int = 1):
    templates = request.app.state.templates
    contacts, total = _list_contacts(search=q, page=page)
    total_pages = max(1, (total + 49) // 50)

    return templates.TemplateResponse(request, "contacts/list.html", {
        "active_nav": "contacts",
        "contacts": contacts,
        "total": total,
        "page": page,
        "total_pages": total_pages,
        "q": q,
    })


@router.get("/search", response_class=HTMLResponse)
def contact_search(request: Request, q: str = "", page: int = 1):
    templates = request.app.state.templates
    contacts, total = _list_contacts(search=q, page=page)
    total_pages = max(1, (total + 49) // 50)

    return templates.TemplateResponse(request, "contacts/_rows.html", {
        "contacts": contacts,
        "total": total,
        "page": page,
        "total_pages": total_pages,
        "q": q,
    })


@router.get("/{contact_id}", response_class=HTMLResponse)
def contact_detail(request: Request, contact_id: str):
    templates = request.app.state.templates

    with get_connection() as conn:
        contact = conn.execute(
            "SELECT * FROM contacts WHERE id = ?", (contact_id,)
        ).fetchone()
        if not contact:
            return HTMLResponse("Contact not found", status_code=404)
        contact = dict(contact)

        # Identifiers
        identifiers = conn.execute(
            "SELECT * FROM contact_identifiers WHERE contact_id = ? ORDER BY is_primary DESC",
            (contact_id,),
        ).fetchall()
        contact["identifiers"] = [dict(i) for i in identifiers]

        # Company
        company = None
        if contact.get("company_id"):
            c = conn.execute(
                "SELECT * FROM companies WHERE id = ?", (contact["company_id"],)
            ).fetchone()
            if c:
                company = dict(c)

        # Conversations this contact participates in
        convs = conn.execute(
            """SELECT conv.* FROM conversations conv
               JOIN conversation_participants cp ON cp.conversation_id = conv.id
               WHERE cp.contact_id = ?
               ORDER BY conv.last_activity_at DESC
               LIMIT 50""",
            (contact_id,),
        ).fetchall()
        conversations = [dict(r) for r in convs]

        # Relationships
        import json
        rels = conn.execute(
            """SELECT r.*, c.name AS other_name, ci.value AS other_email
               FROM relationships r
               LEFT JOIN contacts c ON c.id = CASE
                   WHEN r.from_entity_id = ? THEN r.to_entity_id
                   ELSE r.from_entity_id END
               LEFT JOIN contact_identifiers ci ON ci.contact_id = c.id AND ci.type = 'email'
               WHERE r.from_entity_id = ? OR r.to_entity_id = ?
               ORDER BY r.updated_at DESC""",
            (contact_id, contact_id, contact_id),
        ).fetchall()
        relationships = []
        for r in rels:
            rd = dict(r)
            if rd.get("properties"):
                try:
                    rd["props"] = json.loads(rd["properties"])
                except (json.JSONDecodeError, TypeError):
                    rd["props"] = {}
            else:
                rd["props"] = {}
            # Figure out the other contact's id
            rd["other_id"] = (
                rd["to_entity_id"] if rd["from_entity_id"] == contact_id
                else rd["from_entity_id"]
            )
            relationships.append(rd)

    return templates.TemplateResponse(request, "contacts/detail.html", {
        "active_nav": "contacts",
        "contact": contact,
        "company": company,
        "conversations": conversations,
        "relationships": relationships,
    })
