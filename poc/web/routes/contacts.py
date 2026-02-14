"""Contact routes — list, search, detail, edit, relate, sub-entity CRUD."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from ...access import my_contacts_query, visible_contacts_query
from ...contact_companies import (
    add_affiliation, list_affiliations_for_contact, remove_affiliation,
    set_primary, update_affiliation,
)
from ...contact_company_roles import list_roles
from ...database import get_connection
from ...hierarchy import (
    update_contact, list_companies,
    add_contact_identifier, get_contact_identifiers, remove_contact_identifier,
    add_phone_number, get_phone_numbers, remove_phone_number,
    add_address, get_addresses, remove_address,
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
                LEFT JOIN contact_companies ccx ON ccx.contact_id = c.id AND ccx.is_primary = 1 AND ccx.is_current = 1
                LEFT JOIN companies co ON co.id = ccx.company_id
                {where}""",
            params,
        ).fetchone()["cnt"]

        offset = (page - 1) * per_page
        rows = conn.execute(
            f"""SELECT c.*,
                       (SELECT ci2.value FROM contact_identifiers ci2
                        WHERE ci2.contact_id = c.id AND ci2.type = 'email'
                        ORDER BY ci2.is_primary DESC, ci2.created_at ASC
                        LIMIT 1) AS email,
                       co.name AS company_name, co.id AS company_id,
                       es.score_value AS score
                FROM contacts c
                {mine_join}
                LEFT JOIN contact_identifiers ci ON ci.contact_id = c.id AND ci.type = 'email'
                LEFT JOIN contact_companies ccx ON ccx.contact_id = c.id AND ccx.is_primary = 1 AND ccx.is_current = 1
                LEFT JOIN companies co ON co.id = ccx.company_id
                LEFT JOIN entity_scores es
                  ON es.entity_type = 'contact'
                 AND es.entity_id = c.id
                 AND es.score_type = 'relationship_strength'
                {where}
                GROUP BY c.id
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


# ---------------------------------------------------------------------------
# Merge
# ---------------------------------------------------------------------------

@router.get("/merge", response_class=HTMLResponse)
def contact_merge_preview(request: Request, ids: list[str] = Query(default=[])):
    from ...contact_merge import get_contact_merge_preview
    templates = request.app.state.templates

    if len(ids) < 2:
        return RedirectResponse("/contacts", status_code=303)

    try:
        preview = get_contact_merge_preview(ids)
    except ValueError as exc:
        return RedirectResponse(f"/contacts?error={exc}", status_code=303)

    return templates.TemplateResponse(request, "contacts/merge.html", {
        "active_nav": "contacts",
        "preview": preview,
    })


@router.post("/merge/confirm", response_class=HTMLResponse)
async def contact_merge_confirm(request: Request):
    from ...contact_merge import merge_contacts

    form_data = await request.form()
    surviving_id = form_data.get("surviving_id", "")
    chosen_name = form_data.get("chosen_name", "")
    chosen_source = form_data.get("chosen_source", "")
    all_ids = form_data.getlist("contact_ids")

    if not surviving_id or not all_ids or surviving_id not in all_ids:
        return RedirectResponse("/contacts", status_code=303)

    absorbed_ids = [cid for cid in all_ids if cid != surviving_id]
    user = request.state.user

    try:
        result = merge_contacts(
            surviving_id, absorbed_ids,
            merged_by=user["id"],
            chosen_name=chosen_name or None,
            chosen_source=chosen_source or None,
        )
    except ValueError as exc:
        return RedirectResponse(f"/contacts?error={exc}", status_code=303)

    if _is_htmx(request):
        return HTMLResponse("", headers={"HX-Redirect": f"/contacts/{surviving_id}"})
    return RedirectResponse(f"/contacts/{surviving_id}", status_code=303)


# ---------------------------------------------------------------------------
# vCard Import
# ---------------------------------------------------------------------------

@router.get("/import", response_class=HTMLResponse)
def contact_import_form(request: Request):
    templates = request.app.state.templates
    return templates.TemplateResponse(request, "contacts/import.html", {
        "active_nav": "contacts",
    })


@router.post("/import", response_class=HTMLResponse)
async def contact_import(request: Request):
    from ...vcard_import import import_vcards

    templates = request.app.state.templates
    form_data = await request.form()
    path = form_data.get("path", "").strip()
    recursive = form_data.get("recursive") == "1"

    if not path:
        return templates.TemplateResponse(request, "contacts/import.html", {
            "active_nav": "contacts",
            "error": "Please enter a file or directory path.",
        })

    user = request.state.user
    cid = request.state.customer_id

    try:
        result = import_vcards(
            path, recursive=recursive,
            customer_id=cid, user_id=user["id"],
        )
    except (FileNotFoundError, ValueError) as exc:
        return templates.TemplateResponse(request, "contacts/import.html", {
            "active_nav": "contacts",
            "error": str(exc),
        })

    return templates.TemplateResponse(request, "contacts/import.html", {
        "active_nav": "contacts",
        "result": result,
    })


# ---------------------------------------------------------------------------
# Relate (batch create relationships)
# ---------------------------------------------------------------------------

def _entity_name_lookup(conn, entity_ids: set[str]) -> dict[str, str]:
    if not entity_ids:
        return {}
    names: dict[str, str] = {}
    placeholders = ",".join("?" for _ in entity_ids)
    id_list = list(entity_ids)
    for row in conn.execute(
        f"SELECT id, name FROM contacts WHERE id IN ({placeholders})", id_list,
    ).fetchall():
        names[row["id"]] = row["name"] or row["id"][:8]
    for row in conn.execute(
        f"SELECT id, name FROM companies WHERE id IN ({placeholders})", id_list,
    ).fetchall():
        names[row["id"]] = row["name"] or row["id"][:8]
    return names


@router.get("/relate", response_class=HTMLResponse)
def contact_relate_form(request: Request, ids: list[str] = Query(default=[])):
    templates = request.app.state.templates

    if not ids:
        return RedirectResponse("/contacts", status_code=303)

    with get_connection() as conn:
        placeholders = ",".join("?" for _ in ids)
        rows = conn.execute(
            f"SELECT id, name FROM contacts WHERE id IN ({placeholders})", ids,
        ).fetchall()
        contacts = [dict(r) for r in rows]

    if not contacts:
        return RedirectResponse("/contacts", status_code=303)

    # Pre-load default (contact→contact) relationship types
    with get_connection() as conn:
        type_rows = conn.execute(
            "SELECT * FROM relationship_types "
            "WHERE from_entity_type = 'contact' AND to_entity_type = 'contact' "
            "ORDER BY name",
        ).fetchall()
        default_types = [dict(r) for r in type_rows]

    return templates.TemplateResponse(request, "contacts/relate.html", {
        "active_nav": "contacts",
        "contacts": contacts,
        "default_types": default_types,
    })


@router.get("/relate/types", response_class=HTMLResponse)
def contact_relate_types(request: Request, to_entity_type: str = "contact"):
    templates = request.app.state.templates

    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM relationship_types "
            "WHERE from_entity_type = 'contact' AND to_entity_type = ? "
            "ORDER BY name",
            (to_entity_type,),
        ).fetchall()
        types = [dict(r) for r in rows]

    return templates.TemplateResponse(request, "contacts/_relate_type_options.html", {
        "types": types,
    })


@router.get("/relate/search", response_class=HTMLResponse)
def contact_relate_search(
    request: Request,
    q: str = "",
    target_entity_type: str = "contact",
    contact_ids: list[str] = Query(default=[]),
):
    templates = request.app.state.templates
    cid = request.state.customer_id
    entities: list[dict] = []

    if q.strip():
        with get_connection() as conn:
            if target_entity_type == "contact":
                exclude_placeholders = ",".join("?" for _ in contact_ids) if contact_ids else "''"
                rows = conn.execute(
                    f"""SELECT c.id, c.name,
                               (SELECT ci.value FROM contact_identifiers ci
                                WHERE ci.contact_id = c.id AND ci.type = 'email'
                                ORDER BY ci.is_primary DESC LIMIT 1) AS email
                        FROM contacts c
                        WHERE c.name LIKE ?
                          AND c.customer_id = ?
                          AND c.id NOT IN ({exclude_placeholders})
                        ORDER BY c.name LIMIT 20""",
                    [f"%{q.strip()}%", cid] + list(contact_ids),
                ).fetchall()
                entities = [{"id": r["id"], "name": r["name"], "detail": r["email"] or ""} for r in rows]
            else:
                rows = conn.execute(
                    """SELECT id, name, domain FROM companies
                       WHERE name LIKE ? AND customer_id = ?
                       ORDER BY name LIMIT 20""",
                    (f"%{q.strip()}%", cid),
                ).fetchall()
                entities = [{"id": r["id"], "name": r["name"], "detail": r["domain"] or ""} for r in rows]

    return templates.TemplateResponse(request, "contacts/_relate_search_results.html", {
        "entities": entities,
        "query": q.strip(),
    })


@router.post("/relate", response_class=HTMLResponse)
async def contact_relate_confirm(request: Request):
    templates = request.app.state.templates
    form_data = await request.form()

    contact_ids = form_data.getlist("contact_ids")
    relationship_type_id = form_data.get("relationship_type_id", "")
    target_entity_id = form_data.get("target_entity_id", "")
    target_entity_type = form_data.get("target_entity_type", "contact")

    if not contact_ids or not relationship_type_id or not target_entity_id:
        return RedirectResponse("/contacts", status_code=303)

    now = datetime.now(timezone.utc).isoformat()
    results = []

    with get_connection() as conn:
        # Look up relationship type
        rt = conn.execute(
            "SELECT * FROM relationship_types WHERE id = ?",
            (relationship_type_id,),
        ).fetchone()
        if not rt:
            return RedirectResponse("/contacts", status_code=303)

        is_bidi = bool(rt["is_bidirectional"])

        # Look up names for display
        all_ids = set(contact_ids) | {target_entity_id}
        names = _entity_name_lookup(conn, all_ids)
        target_name = names.get(target_entity_id, target_entity_id[:8])

        for cid in contact_ids:
            contact_name = names.get(cid, cid[:8])

            # Skip self-relationships
            if cid == target_entity_id:
                results.append({
                    "contact_name": contact_name,
                    "type_label": rt["forward_label"] or rt["name"],
                    "target_name": target_name,
                    "status": "skipped",
                    "reason": "Self-relationship",
                })
                continue

            # Check existing (either direction)
            existing = conn.execute(
                """SELECT id FROM relationships
                   WHERE relationship_type_id = ?
                     AND ((from_entity_id = ? AND to_entity_id = ?)
                       OR (from_entity_id = ? AND to_entity_id = ?))""",
                (relationship_type_id, cid, target_entity_id,
                 target_entity_id, cid),
            ).fetchone()
            if existing:
                results.append({
                    "contact_name": contact_name,
                    "type_label": rt["forward_label"] or rt["name"],
                    "target_name": target_name,
                    "status": "skipped",
                    "reason": "Already exists",
                })
                continue

            try:
                rel_id_1 = str(uuid.uuid4())
                conn.execute(
                    """INSERT INTO relationships
                       (id, relationship_type_id, from_entity_type, from_entity_id,
                        to_entity_type, to_entity_id, paired_relationship_id,
                        source, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, NULL, 'manual', ?, ?)""",
                    (rel_id_1, relationship_type_id,
                     rt["from_entity_type"], cid,
                     rt["to_entity_type"], target_entity_id,
                     now, now),
                )

                if is_bidi:
                    rel_id_2 = str(uuid.uuid4())
                    conn.execute(
                        """INSERT INTO relationships
                           (id, relationship_type_id, from_entity_type, from_entity_id,
                            to_entity_type, to_entity_id, paired_relationship_id,
                            source, created_at, updated_at)
                           VALUES (?, ?, ?, ?, ?, ?, NULL, 'manual', ?, ?)""",
                        (rel_id_2, relationship_type_id,
                         rt["to_entity_type"], target_entity_id,
                         rt["from_entity_type"], cid,
                         now, now),
                    )
                    conn.execute(
                        "UPDATE relationships SET paired_relationship_id = ? WHERE id = ?",
                        (rel_id_2, rel_id_1),
                    )
                    conn.execute(
                        "UPDATE relationships SET paired_relationship_id = ? WHERE id = ?",
                        (rel_id_1, rel_id_2),
                    )

                results.append({
                    "contact_name": contact_name,
                    "type_label": rt["forward_label"] or rt["name"],
                    "target_name": target_name,
                    "status": "created",
                    "reason": "",
                })
            except Exception as exc:
                results.append({
                    "contact_name": contact_name,
                    "type_label": rt["forward_label"] or rt["name"],
                    "target_name": target_name,
                    "status": "error",
                    "reason": str(exc),
                })

    return templates.TemplateResponse(request, "contacts/relate.html", {
        "active_nav": "contacts",
        "results": results,
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

    # Affiliations
    affiliations = list_affiliations_for_contact(contact_id)
    all_roles = list_roles(customer_id=cid)
    phones = get_phone_numbers("contact", contact_id)
    addresses = get_addresses("contact", contact_id)
    email_identifiers = [i for i in contact["identifiers"] if i["type"] == "email"]
    all_companies = list_companies(customer_id=cid)

    from ...phone_utils import resolve_country_code
    display_country = resolve_country_code("contact", contact_id, customer_id=cid)

    from ...scoring import get_entity_score
    score_data = get_entity_score("contact", contact_id)

    from ...notes import get_notes_for_entity
    notes = get_notes_for_entity("contact", contact_id, customer_id=cid)

    return templates.TemplateResponse(request, "contacts/detail.html", {
        "active_nav": "contacts",
        "contact": contact,
        "affiliations": affiliations,
        "all_roles": all_roles,
        "conversations": conversations,
        "relationships": relationships,
        "email_identifiers": email_identifiers,
        "phones": phones,
        "addresses": addresses,
        "social_profiles": social_profiles,
        "all_companies": all_companies,
        "score_data": score_data,
        "display_country": display_country,
        "notes": notes,
        "entity_type": "contact",
        "entity_id": contact_id,
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

    with get_connection() as conn:
        contact = conn.execute(
            "SELECT * FROM contacts WHERE id = ?", (contact_id,)
        ).fetchone()
        if not contact:
            return HTMLResponse("Contact not found", status_code=404)
        contact = dict(contact)

    return templates.TemplateResponse(request, "contacts/edit.html", {
        "active_nav": "contacts",
        "contact": contact,
    })


@router.post("/{contact_id}/edit", response_class=HTMLResponse)
def contact_edit(
    request: Request,
    contact_id: str,
    name: str = Form(...),
    source: str = Form(""),
    status: str = Form("active"),
):
    update_contact(
        contact_id,
        name=name,
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
    import sqlite3
    templates = request.app.state.templates
    try:
        add_contact_identifier(contact_id, type, value)
    except sqlite3.IntegrityError:
        # Identifier already belongs to another contact — find who
        with get_connection() as conn:
            existing = conn.execute(
                "SELECT ci.contact_id, c.name FROM contact_identifiers ci "
                "JOIN contacts c ON c.id = ci.contact_id "
                "WHERE ci.type = ? AND ci.value = ?",
                (type, value),
            ).fetchone()
        identifiers = get_contact_identifiers(contact_id)
        error = f"That {type} is already assigned to "
        if existing:
            other_id = existing["contact_id"]
            error += f'<a href="/contacts/{other_id}">{existing["name"]}</a>'
            error += f' &mdash; <a href="/contacts/merge?ids={contact_id}&ids={other_id}">Merge these contacts?</a>'
        else:
            error += "another contact"
        return templates.TemplateResponse(request, "contacts/_identifiers.html", {
            "contact": {"id": contact_id},
            "identifiers": identifiers,
            "error": error,
        })
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
    import sqlite3
    templates = request.app.state.templates
    error = None
    try:
        add_contact_identifier(contact_id, "email", address, label=email_type)
    except sqlite3.IntegrityError:
        with get_connection() as conn:
            existing = conn.execute(
                "SELECT ci.contact_id, c.name FROM contact_identifiers ci "
                "JOIN contacts c ON c.id = ci.contact_id "
                "WHERE ci.type = 'email' AND ci.value = ?",
                (address,),
            ).fetchone()
        error = "That email is already assigned to "
        if existing:
            other_id = existing["contact_id"]
            error += f'<a href="/contacts/{other_id}">{existing["name"]}</a>'
            error += f' &mdash; <a href="/contacts/merge?ids={contact_id}&ids={other_id}">Merge these contacts?</a>'
        else:
            error += "another contact"
    email_identifiers = [i for i in get_contact_identifiers(contact_id) if i["type"] == "email"]

    ctx = {"contact": {"id": contact_id}, "email_identifiers": email_identifiers}
    if error:
        ctx["email_error"] = error
    return templates.TemplateResponse(request, "contacts/_emails.html", ctx)


@router.delete("/{contact_id}/emails/{email_id}", response_class=HTMLResponse)
def contact_remove_email(
    request: Request, contact_id: str, email_id: str,
):
    templates = request.app.state.templates
    remove_contact_identifier(email_id)
    email_identifiers = [i for i in get_contact_identifiers(contact_id) if i["type"] == "email"]

    return templates.TemplateResponse(request, "contacts/_emails.html", {
        "contact": {"id": contact_id},
        "email_identifiers": email_identifiers,
    })


# ---------------------------------------------------------------------------
# Affiliations (Contact ↔ Company)
# ---------------------------------------------------------------------------

def _affiliation_context(request, contact_id):
    cid = request.state.customer_id
    return {
        "contact": {"id": contact_id},
        "affiliations": list_affiliations_for_contact(contact_id),
        "all_roles": list_roles(customer_id=cid),
        "all_companies": list_companies(customer_id=cid),
    }


@router.post("/{contact_id}/affiliations", response_class=HTMLResponse)
def contact_add_affiliation(
    request: Request,
    contact_id: str,
    company_id: str = Form(...),
    role_id: str = Form(""),
    title: str = Form(""),
    department: str = Form(""),
    is_primary: str = Form(""),
    is_current: str = Form("1"),
    started_at: str = Form(""),
    ended_at: str = Form(""),
    notes: str = Form(""),
):
    templates = request.app.state.templates
    user = request.state.user
    add_affiliation(
        contact_id, company_id,
        role_id=role_id or None,
        title=title, department=department,
        is_primary=bool(is_primary),
        is_current=is_current == "1",
        started_at=started_at, ended_at=ended_at,
        notes=notes,
        created_by=user["id"],
    )
    return templates.TemplateResponse(
        request, "contacts/_affiliations.html", _affiliation_context(request, contact_id),
    )


@router.post("/{contact_id}/affiliations/{aff_id}/edit", response_class=HTMLResponse)
def contact_edit_affiliation(
    request: Request,
    contact_id: str,
    aff_id: str,
    role_id: str = Form(""),
    title: str = Form(""),
    department: str = Form(""),
    is_primary: str = Form(""),
    is_current: str = Form("1"),
    started_at: str = Form(""),
    ended_at: str = Form(""),
    notes: str = Form(""),
):
    templates = request.app.state.templates
    user = request.state.user
    update_affiliation(
        aff_id,
        role_id=role_id or None,
        title=title or None, department=department or None,
        is_primary=int(bool(is_primary)),
        is_current=int(is_current == "1"),
        started_at=started_at or None, ended_at=ended_at or None,
        notes=notes or None,
        updated_by=user["id"],
    )
    return templates.TemplateResponse(
        request, "contacts/_affiliations.html", _affiliation_context(request, contact_id),
    )


@router.delete("/{contact_id}/affiliations/{aff_id}", response_class=HTMLResponse)
def contact_remove_affiliation(
    request: Request, contact_id: str, aff_id: str,
):
    templates = request.app.state.templates
    remove_affiliation(aff_id)
    return templates.TemplateResponse(
        request, "contacts/_affiliations.html", _affiliation_context(request, contact_id),
    )


@router.post("/{contact_id}/affiliations/{aff_id}/primary", response_class=HTMLResponse)
def contact_set_primary_affiliation(
    request: Request, contact_id: str, aff_id: str,
):
    templates = request.app.state.templates
    set_primary(aff_id)
    return templates.TemplateResponse(
        request, "contacts/_affiliations.html", _affiliation_context(request, contact_id),
    )
