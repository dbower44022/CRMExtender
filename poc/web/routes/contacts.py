"""Contact routes — list, search, detail, edit, sub-entity CRUD."""

from __future__ import annotations

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from ...access import my_contacts_query, visible_contacts_query
from ...database import get_connection
from ...hierarchy import (
    update_contact, list_companies,
    add_contact_identifier, get_contact_identifiers, remove_contact_identifier,
    add_phone_number, get_phone_numbers, remove_phone_number,
    add_address, get_addresses, remove_address,
    add_email_address, get_email_addresses, remove_email_address,
)

router = APIRouter()


def _is_htmx(request: Request) -> bool:
    return request.headers.get("HX-Request") == "true"


_CONTACT_SORT_MAP = {
    "name": "c.name", "email": "ci.value",
    "company": "co.name", "score": "es.score_value",
}


def _list_contacts(*, search: str = "", page: int = 1, per_page: int = 50,
                   sort: str = "name",
                   customer_id: str = "", user_id: str = "",
                   scope: str = "all"):
    clauses: list[str] = []
    params: list = []

    # Visibility scoping
    if scope == "mine" and customer_id and user_id:
        my_where, my_params = my_contacts_query(customer_id, user_id)
        clauses.append(my_where)
        params.extend(my_params)
    elif customer_id and user_id:
        vis_where, vis_params = visible_contacts_query(customer_id, user_id)
        clauses.append(vis_where)
        params.extend(vis_params)

    if search:
        clauses.append("(c.name LIKE ? OR ci.value LIKE ? OR co.name LIKE ?)")
        params.extend([f"%{search}%", f"%{search}%", f"%{search}%"])

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""

    desc = sort.startswith("-")
    key = sort.lstrip("-")
    col = _CONTACT_SORT_MAP.get(key, "c.name")
    direction = "DESC" if desc else "ASC"
    order = f"{col} IS NULL, {col} {direction}" if key == "score" else f"{col} {direction}"

    # Extra JOIN for "mine" scope
    mine_join = ""
    if scope == "mine" and customer_id and user_id:
        mine_join = "JOIN user_contacts uc ON uc.contact_id = c.id"

    with get_connection() as conn:
        total = conn.execute(
            f"""SELECT COUNT(DISTINCT c.id) AS cnt
                FROM contacts c
                {mine_join}
                LEFT JOIN contact_identifiers ci ON ci.contact_id = c.id AND ci.type = 'email'
                LEFT JOIN companies co ON co.id = c.company_id
                {where}""",
            params,
        ).fetchone()["cnt"]

        offset = (page - 1) * per_page
        rows = conn.execute(
            f"""SELECT c.*, ci.value AS email, co.name AS company_name,
                       es.score_value AS score
                FROM contacts c
                {mine_join}
                LEFT JOIN contact_identifiers ci ON ci.contact_id = c.id AND ci.type = 'email'
                LEFT JOIN companies co ON co.id = c.company_id
                LEFT JOIN entity_scores es
                  ON es.entity_type = 'contact'
                 AND es.entity_id = c.id
                 AND es.score_type = 'relationship_strength'
                {where}
                ORDER BY {order}
                LIMIT ? OFFSET ?""",
            params + [per_page, offset],
        ).fetchall()

    return [dict(r) for r in rows], total


@router.get("", response_class=HTMLResponse)
def contact_list(request: Request, q: str = "", page: int = 1,
                 sort: str = "name", scope: str = "all"):
    templates = request.app.state.templates
    user = request.state.user
    cid = request.state.customer_id
    contacts, total = _list_contacts(
        search=q, page=page, sort=sort,
        customer_id=cid, user_id=user["id"], scope=scope,
    )
    total_pages = max(1, (total + 49) // 50)

    return templates.TemplateResponse(request, "contacts/list.html", {
        "active_nav": "contacts",
        "contacts": contacts,
        "total": total,
        "page": page,
        "total_pages": total_pages,
        "q": q,
        "sort": sort,
        "scope": scope,
    })


@router.get("/search", response_class=HTMLResponse)
def contact_search(request: Request, q: str = "", page: int = 1,
                   sort: str = "name", scope: str = "all"):
    templates = request.app.state.templates
    user = request.state.user
    cid = request.state.customer_id
    contacts, total = _list_contacts(
        search=q, page=page, sort=sort,
        customer_id=cid, user_id=user["id"], scope=scope,
    )
    total_pages = max(1, (total + 49) // 50)

    return templates.TemplateResponse(request, "contacts/_rows.html", {
        "contacts": contacts,
        "total": total,
        "page": page,
        "total_pages": total_pages,
        "q": q,
        "sort": sort,
        "scope": scope,
    })


@router.get("/{contact_id}", response_class=HTMLResponse)
def contact_detail(request: Request, contact_id: str):
    templates = request.app.state.templates
    cid = request.state.customer_id

    with get_connection() as conn:
        contact = conn.execute(
            "SELECT * FROM contacts WHERE id = ?", (contact_id,)
        ).fetchone()
        if not contact:
            return HTMLResponse("Contact not found", status_code=404)
        contact = dict(contact)

        # Cross-customer access check
        if contact.get("customer_id") and contact["customer_id"] != cid:
            return HTMLResponse("Contact not found", status_code=404)

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

        # Relationships (bidirectional pairs stored as two rows, so from_entity_id suffices)
        import json
        rels = conn.execute(
            """SELECT r.*, rt.name AS type_name,
                      rt.forward_label, rt.reverse_label,
                      c.name AS other_name, ci.value AS other_email
               FROM relationships r
               JOIN relationship_types rt ON rt.id = r.relationship_type_id
               LEFT JOIN contacts c ON c.id = r.to_entity_id
               LEFT JOIN contact_identifiers ci ON ci.contact_id = c.id AND ci.type = 'email'
               WHERE r.from_entity_id = ?
               ORDER BY r.updated_at DESC""",
            (contact_id,),
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
            rd["other_id"] = rd["to_entity_id"]
            rd["other_entity_type"] = rd["to_entity_type"]
            rd["label"] = rd["forward_label"]
            # Try to resolve company names for non-contact other entities
            if rd["other_entity_type"] == "company" and not rd.get("other_name"):
                co = conn.execute(
                    "SELECT name FROM companies WHERE id = ?", (rd["other_id"],)
                ).fetchone()
                if co:
                    rd["other_name"] = co["name"]
            relationships.append(rd)

        # Social profiles
        social_profiles = [dict(r) for r in conn.execute(
            "SELECT * FROM contact_social_profiles WHERE contact_id = ? ORDER BY platform",
            (contact_id,),
        ).fetchall()]

    phones = get_phone_numbers("contact", contact_id)
    addresses = get_addresses("contact", contact_id)
    emails = get_email_addresses("contact", contact_id)
    all_companies = list_companies(customer_id=cid)

    from ...phone_utils import resolve_country_code
    display_country = resolve_country_code("contact", contact_id, customer_id=cid)

    from ...scoring import get_entity_score
    score_data = get_entity_score("contact", contact_id)

    return templates.TemplateResponse(request, "contacts/detail.html", {
        "active_nav": "contacts",
        "contact": contact,
        "company": company,
        "conversations": conversations,
        "relationships": relationships,
        "identifiers": contact["identifiers"],
        "phones": phones,
        "addresses": addresses,
        "emails": emails,
        "social_profiles": social_profiles,
        "all_companies": all_companies,
        "score_data": score_data,
        "display_country": display_country,
    })


@router.post("/{contact_id}/score", response_class=HTMLResponse)
def contact_score(request: Request, contact_id: str):
    from ...scoring import SCORE_TYPE, compute_contact_score, get_entity_score, upsert_entity_score
    templates = request.app.state.templates

    with get_connection() as conn:
        contact = conn.execute(
            "SELECT * FROM contacts WHERE id = ?", (contact_id,)
        ).fetchone()
        if not contact:
            return HTMLResponse("Contact not found", status_code=404)
        contact = dict(contact)

        result = compute_contact_score(conn, contact_id)
        if result:
            upsert_entity_score(
                conn, "contact", contact_id, SCORE_TYPE,
                result["score"], result["factors"], triggered_by="web",
            )

    score_data = get_entity_score("contact", contact_id)

    return templates.TemplateResponse(request, "contacts/_score.html", {
        "contact": contact,
        "score_data": score_data,
    })


@router.get("/{contact_id}/edit", response_class=HTMLResponse)
def contact_edit_form(request: Request, contact_id: str):
    templates = request.app.state.templates
    cid = request.state.customer_id

    with get_connection() as conn:
        contact = conn.execute(
            "SELECT * FROM contacts WHERE id = ?", (contact_id,)
        ).fetchone()
        if not contact:
            return HTMLResponse("Contact not found", status_code=404)
        contact = dict(contact)

    all_companies = list_companies(customer_id=cid)

    return templates.TemplateResponse(request, "contacts/edit.html", {
        "active_nav": "contacts",
        "contact": contact,
        "all_companies": all_companies,
    })


@router.post("/{contact_id}/edit", response_class=HTMLResponse)
def contact_edit(
    request: Request,
    contact_id: str,
    name: str = Form(...),
    company_id: str = Form(""),
    source: str = Form(""),
    status: str = Form("active"),
):
    update_contact(
        contact_id,
        name=name,
        company_id=company_id if company_id else None,
        source=source,
        status=status,
    )
    if _is_htmx(request):
        return HTMLResponse("", headers={"HX-Redirect": f"/contacts/{contact_id}"})
    return RedirectResponse(f"/contacts/{contact_id}", status_code=303)


# ---------------------------------------------------------------------------
# Contact Identifiers
# ---------------------------------------------------------------------------

@router.post("/{contact_id}/identifiers", response_class=HTMLResponse)
def contact_add_identifier(
    request: Request,
    contact_id: str,
    type: str = Form("email"),
    value: str = Form(...),
):
    templates = request.app.state.templates
    add_contact_identifier(contact_id, type, value)
    identifiers = get_contact_identifiers(contact_id)

    return templates.TemplateResponse(request, "contacts/_identifiers.html", {
        "contact": {"id": contact_id},
        "identifiers": identifiers,
    })


@router.delete("/{contact_id}/identifiers/{identifier_id}", response_class=HTMLResponse)
def contact_remove_identifier(
    request: Request, contact_id: str, identifier_id: str,
):
    templates = request.app.state.templates
    remove_contact_identifier(identifier_id)
    identifiers = get_contact_identifiers(contact_id)

    return templates.TemplateResponse(request, "contacts/_identifiers.html", {
        "contact": {"id": contact_id},
        "identifiers": identifiers,
    })


# ---------------------------------------------------------------------------
# Phone Numbers
# ---------------------------------------------------------------------------

@router.post("/{contact_id}/phones", response_class=HTMLResponse)
def contact_add_phone(
    request: Request,
    contact_id: str,
    phone_type: str = Form("mobile"),
    number: str = Form(...),
):
    templates = request.app.state.templates
    cid = request.state.customer_id
    result = add_phone_number("contact", contact_id, number,
                              phone_type=phone_type, customer_id=cid)
    phones = get_phone_numbers("contact", contact_id)

    from ...phone_utils import resolve_country_code
    display_country = resolve_country_code("contact", contact_id, customer_id=cid)

    ctx = {
        "contact": {"id": contact_id},
        "phones": phones,
        "display_country": display_country,
    }
    if result is None:
        ctx["phone_error"] = "Invalid phone number."
    return templates.TemplateResponse(request, "contacts/_phones.html", ctx)


@router.delete("/{contact_id}/phones/{phone_id}", response_class=HTMLResponse)
def contact_remove_phone(
    request: Request, contact_id: str, phone_id: str,
):
    templates = request.app.state.templates
    cid = request.state.customer_id
    remove_phone_number(phone_id)
    phones = get_phone_numbers("contact", contact_id)

    from ...phone_utils import resolve_country_code
    display_country = resolve_country_code("contact", contact_id, customer_id=cid)

    return templates.TemplateResponse(request, "contacts/_phones.html", {
        "contact": {"id": contact_id},
        "phones": phones,
        "display_country": display_country,
    })


# ---------------------------------------------------------------------------
# Addresses
# ---------------------------------------------------------------------------

@router.post("/{contact_id}/addresses", response_class=HTMLResponse)
def contact_add_address(
    request: Request,
    contact_id: str,
    address_type: str = Form("work"),
    street: str = Form(""),
    city: str = Form(""),
    state: str = Form(""),
    postal_code: str = Form(""),
    country: str = Form(""),
):
    templates = request.app.state.templates
    add_address(
        "contact", contact_id,
        address_type=address_type, street=street, city=city,
        state=state, postal_code=postal_code, country=country,
    )
    addresses = get_addresses("contact", contact_id)

    return templates.TemplateResponse(request, "contacts/_addresses.html", {
        "contact": {"id": contact_id},
        "addresses": addresses,
    })


@router.delete("/{contact_id}/addresses/{address_id}", response_class=HTMLResponse)
def contact_remove_address(
    request: Request, contact_id: str, address_id: str,
):
    templates = request.app.state.templates
    remove_address(address_id)
    addresses = get_addresses("contact", contact_id)

    return templates.TemplateResponse(request, "contacts/_addresses.html", {
        "contact": {"id": contact_id},
        "addresses": addresses,
    })


# ---------------------------------------------------------------------------
# Email Addresses
# ---------------------------------------------------------------------------

@router.post("/{contact_id}/emails", response_class=HTMLResponse)
def contact_add_email(
    request: Request,
    contact_id: str,
    email_type: str = Form("general"),
    address: str = Form(...),
):
    templates = request.app.state.templates
    add_email_address("contact", contact_id, address, email_type=email_type)
    emails = get_email_addresses("contact", contact_id)

    return templates.TemplateResponse(request, "contacts/_emails.html", {
        "contact": {"id": contact_id},
        "emails": emails,
    })


@router.delete("/{contact_id}/emails/{email_id}", response_class=HTMLResponse)
def contact_remove_email(
    request: Request, contact_id: str, email_id: str,
):
    templates = request.app.state.templates
    remove_email_address(email_id)
    emails = get_email_addresses("contact", contact_id)

    return templates.TemplateResponse(request, "contacts/_emails.html", {
        "contact": {"id": contact_id},
        "emails": emails,
    })
