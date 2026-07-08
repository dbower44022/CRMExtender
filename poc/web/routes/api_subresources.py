"""JSON API for entity sub-resources (Legacy UI Migration PRD, Phase 2).

Replaces the legacy HTMX sub-resource routes with /api/v1 endpoints over
the same web-independent helpers (poc/hierarchy.py, poc/contact_companies.py,
poc/scoring.py). Deliberate improvements over the legacy routes, recorded
in the PRD:

- Ownership checks: the parent entity must belong to the caller's
  customer, and a child row must belong to the parent in the path.
- "Set primary" is exclusive for every sub-resource type (legacy only
  did this for affiliations).
- Company hierarchy gains self-link (422), duplicate (409), and cycle
  (422) protection.
- Contact email values are normalized (strip + lowercase) before the
  case-sensitive UNIQUE(type, value) dedup.
"""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from ...contact_companies import (
    add_affiliation,
    list_affiliations_for_contact,
    remove_affiliation,
    update_affiliation,
)
from ...database import get_connection
from ...hierarchy import (
    add_address,
    add_company_hierarchy,
    add_company_identifier,
    add_contact_identifier,
    add_email_address,
    add_phone_number,
    delete_company,
    get_addresses,
    get_child_companies,
    get_company_identifiers,
    get_contact_identifiers,
    get_email_addresses,
    get_parent_companies,
    get_phone_numbers,
    remove_address,
    remove_company_hierarchy,
    remove_company_identifier,
    remove_contact_identifier,
    remove_email_address,
    remove_phone_number,
    update_address,
    update_contact_identifier,
    update_email_address,
    update_phone_number,
)
from ...phone_utils import format_phone, resolve_country_code

router = APIRouter()

_ENTITY_TABLE = {"contact": "contacts", "company": "companies"}


def _affiliation_with_names(affiliation_id: str) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            """SELECT cc.*, co.name AS company_name, ccr.name AS role_name
               FROM contact_companies cc
               JOIN companies co ON co.id = cc.company_id
               LEFT JOIN contact_company_roles ccr ON ccr.id = cc.role_id
               WHERE cc.id = ?""",
            (affiliation_id,),
        ).fetchone()
    return dict(row) if row else None


def _err(message: str, status: int = 400, **extra) -> JSONResponse:
    return JSONResponse({"error": message, **extra}, status_code=status)


def _owned_entity(request: Request, entity_type: str, entity_id: str) -> bool:
    """The parent entity exists and belongs to the caller's customer."""
    cid = request.state.customer_id
    table = _ENTITY_TABLE[entity_type]
    with get_connection() as conn:
        row = conn.execute(
            f"SELECT customer_id FROM {table} WHERE id = ?", (entity_id,)
        ).fetchone()
    if not row:
        return False
    return not row["customer_id"] or row["customer_id"] == cid


def _child_of(table: str, child_id: str, where: str, params: tuple) -> bool:
    """The child row exists and belongs to the parent in the path."""
    with get_connection() as conn:
        row = conn.execute(
            f"SELECT 1 FROM {table} WHERE id = ? AND {where}",
            (child_id, *params),
        ).fetchone()
    return row is not None


def _set_exclusive_primary(table: str, row_id: str, scope_where: str, scope_params: tuple) -> None:
    """Make row_id the only primary row within its scope."""
    with get_connection() as conn:
        conn.execute(
            f"UPDATE {table} SET is_primary = 0 WHERE {scope_where}", scope_params
        )
        conn.execute(
            f"UPDATE {table} SET is_primary = 1 WHERE id = ?", (row_id,)
        )


def _bool_int(value, default: int = 0) -> int:
    if value is None:
        return default
    return 1 if value in (True, 1, "1", "true") else 0


# ---------------------------------------------------------------------------
# Combined read shape for the editing UI
# ---------------------------------------------------------------------------

@router.get("/{entity_plural}/{entity_id}/subresources")
def subresources_api(request: Request, entity_plural: str, entity_id: str):
    entity_type = {"contacts": "contact", "companies": "company"}.get(entity_plural)
    if not entity_type:
        return _err("Unknown entity type", 404)
    if not _owned_entity(request, entity_type, entity_id):
        return _err("Not found", 404)

    country = resolve_country_code(
        entity_type, entity_id, customer_id=request.state.customer_id
    )
    phones = get_phone_numbers(entity_type, entity_id)
    for p in phones:
        p["display"] = format_phone(p["number"], country)

    out: dict = {
        "phones": phones,
        "addresses": get_addresses(entity_type, entity_id),
    }
    if entity_type == "contact":
        out["identifiers"] = get_contact_identifiers(entity_id)
        out["affiliations"] = list_affiliations_for_contact(entity_id)
    else:
        out["identifiers"] = get_company_identifiers(entity_id)
        out["emails"] = get_email_addresses("company", entity_id)
        out["hierarchy"] = {
            "parents": get_parent_companies(entity_id),
            "children": get_child_companies(entity_id),
        }
    return out


# ---------------------------------------------------------------------------
# Contact identifiers (emails are identifiers with type='email')
# ---------------------------------------------------------------------------

@router.post("/contacts/{contact_id}/identifiers")
async def contact_identifier_add(request: Request, contact_id: str):
    if not _owned_entity(request, "contact", contact_id):
        return _err("Not found", 404)
    body = await request.json()
    id_type = (body.get("type") or "email").strip()
    value = (body.get("value") or "").strip()
    if not value:
        return _err("value is required")
    if id_type == "email":
        value = value.lower()
    try:
        row = add_contact_identifier(
            contact_id, id_type, value,
            label=body.get("label") or "",
            is_primary=bool(body.get("is_primary")),
        )
    except sqlite3.IntegrityError:
        with get_connection() as conn:
            other = conn.execute(
                "SELECT ci.contact_id, c.name FROM contact_identifiers ci "
                "JOIN contacts c ON c.id = ci.contact_id "
                "WHERE ci.type = ? AND ci.value = ?",
                (id_type, value),
            ).fetchone()
        return _err(
            "This identifier already belongs to another contact", 409,
            other_contact_id=other["contact_id"] if other else None,
            other_contact_name=other["name"] if other else None,
        )
    if row.get("is_primary"):
        _set_exclusive_primary(
            "contact_identifiers", row["id"],
            "contact_id = ? AND type = ?", (contact_id, id_type),
        )
    return row


@router.put("/contacts/{contact_id}/identifiers/{identifier_id}")
async def contact_identifier_update(request: Request, contact_id: str, identifier_id: str):
    if not _owned_entity(request, "contact", contact_id):
        return _err("Not found", 404)
    if not _child_of("contact_identifiers", identifier_id, "contact_id = ?", (contact_id,)):
        return _err("Not found", 404)
    body = await request.json()
    fields = {k: body[k] for k in ("label", "started_at", "ended_at") if k in body}
    if "is_current" in body:
        fields["is_current"] = _bool_int(body["is_current"], 1)
    row = update_contact_identifier(identifier_id, **fields) if fields else None
    if body.get("is_primary"):
        with get_connection() as conn:
            id_type = conn.execute(
                "SELECT type FROM contact_identifiers WHERE id = ?", (identifier_id,)
            ).fetchone()["type"]
        _set_exclusive_primary(
            "contact_identifiers", identifier_id,
            "contact_id = ? AND type = ?", (contact_id, id_type),
        )
        with get_connection() as conn:
            row = dict(conn.execute(
                "SELECT * FROM contact_identifiers WHERE id = ?", (identifier_id,)
            ).fetchone())
    return row or {"ok": True}


@router.delete("/contacts/{contact_id}/identifiers/{identifier_id}")
def contact_identifier_delete(request: Request, contact_id: str, identifier_id: str):
    if not _owned_entity(request, "contact", contact_id):
        return _err("Not found", 404)
    if not _child_of("contact_identifiers", identifier_id, "contact_id = ?", (contact_id,)):
        return _err("Not found", 404)
    remove_contact_identifier(identifier_id)
    return {"ok": True}


# ---------------------------------------------------------------------------
# Phones (contacts + companies)
# ---------------------------------------------------------------------------

def _phone_routes(entity_type: str, entity_plural: str):
    @router.post(f"/{entity_plural}/{{entity_id}}/phones")
    async def phone_add(request: Request, entity_id: str):
        if not _owned_entity(request, entity_type, entity_id):
            return _err("Not found", 404)
        body = await request.json()
        number = (body.get("number") or "").strip()
        if not number:
            return _err("number is required")
        row = add_phone_number(
            entity_type, entity_id, number,
            phone_type=body.get("phone_type") or ("mobile" if entity_type == "contact" else "main"),
            customer_id=request.state.customer_id,
        )
        if row is None:
            return _err("Invalid phone number", 400)
        country = resolve_country_code(
            entity_type, entity_id, customer_id=request.state.customer_id
        )
        row["display"] = format_phone(row["number"], country)
        return row

    @router.put(f"/{entity_plural}/{{entity_id}}/phones/{{phone_id}}")
    async def phone_update(request: Request, entity_id: str, phone_id: str):
        if not _owned_entity(request, entity_type, entity_id):
            return _err("Not found", 404)
        if not _child_of("phone_numbers", phone_id,
                         "entity_type = ? AND entity_id = ?", (entity_type, entity_id)):
            return _err("Not found", 404)
        body = await request.json()
        fields = {k: body[k] for k in ("phone_type", "started_at", "ended_at") if k in body}
        if "is_current" in body:
            fields["is_current"] = _bool_int(body["is_current"], 1)
        row = update_phone_number(phone_id, **fields) if fields else None
        if body.get("is_primary"):
            _set_exclusive_primary(
                "phone_numbers", phone_id,
                "entity_type = ? AND entity_id = ?", (entity_type, entity_id),
            )
            with get_connection() as conn:
                row = dict(conn.execute(
                    "SELECT * FROM phone_numbers WHERE id = ?", (phone_id,)
                ).fetchone())
        return row or {"ok": True}

    @router.delete(f"/{entity_plural}/{{entity_id}}/phones/{{phone_id}}")
    def phone_delete(request: Request, entity_id: str, phone_id: str):
        if not _owned_entity(request, entity_type, entity_id):
            return _err("Not found", 404)
        if not _child_of("phone_numbers", phone_id,
                         "entity_type = ? AND entity_id = ?", (entity_type, entity_id)):
            return _err("Not found", 404)
        remove_phone_number(phone_id)
        return {"ok": True}


_phone_routes("contact", "contacts")
_phone_routes("company", "companies")


# ---------------------------------------------------------------------------
# Addresses (contacts + companies)
# ---------------------------------------------------------------------------

_ADDRESS_FIELDS = ("address_type", "street", "city", "state", "postal_code", "country")


def _address_routes(entity_type: str, entity_plural: str):
    @router.post(f"/{entity_plural}/{{entity_id}}/addresses")
    async def address_add(request: Request, entity_id: str):
        if not _owned_entity(request, entity_type, entity_id):
            return _err("Not found", 404)
        body = await request.json()
        if not any((body.get(f) or "").strip() for f in _ADDRESS_FIELDS[1:]):
            return _err("At least one address field is required")
        return add_address(
            entity_type, entity_id,
            **{f: (body.get(f) or "").strip() for f in _ADDRESS_FIELDS},
        )

    @router.put(f"/{entity_plural}/{{entity_id}}/addresses/{{address_id}}")
    async def address_update(request: Request, entity_id: str, address_id: str):
        if not _owned_entity(request, entity_type, entity_id):
            return _err("Not found", 404)
        if not _child_of("addresses", address_id,
                         "entity_type = ? AND entity_id = ?", (entity_type, entity_id)):
            return _err("Not found", 404)
        body = await request.json()
        fields = {k: body[k] for k in (*_ADDRESS_FIELDS, "started_at", "ended_at") if k in body}
        if "is_current" in body:
            fields["is_current"] = _bool_int(body["is_current"], 1)
        row = update_address(address_id, **fields) if fields else None
        if body.get("is_primary"):
            _set_exclusive_primary(
                "addresses", address_id,
                "entity_type = ? AND entity_id = ?", (entity_type, entity_id),
            )
            with get_connection() as conn:
                row = dict(conn.execute(
                    "SELECT * FROM addresses WHERE id = ?", (address_id,)
                ).fetchone())
        return row or {"ok": True}

    @router.delete(f"/{entity_plural}/{{entity_id}}/addresses/{{address_id}}")
    def address_delete(request: Request, entity_id: str, address_id: str):
        if not _owned_entity(request, entity_type, entity_id):
            return _err("Not found", 404)
        if not _child_of("addresses", address_id,
                         "entity_type = ? AND entity_id = ?", (entity_type, entity_id)):
            return _err("Not found", 404)
        remove_address(address_id)
        return {"ok": True}


_address_routes("contact", "contacts")
_address_routes("company", "companies")


# ---------------------------------------------------------------------------
# Company emails (email_addresses table)
# ---------------------------------------------------------------------------

@router.post("/companies/{company_id}/emails")
async def company_email_add(request: Request, company_id: str):
    if not _owned_entity(request, "company", company_id):
        return _err("Not found", 404)
    body = await request.json()
    address = (body.get("address") or "").strip().lower()
    if not address:
        return _err("address is required")
    return add_email_address(
        "company", company_id, address,
        email_type=body.get("email_type") or "general",
    )


@router.put("/companies/{company_id}/emails/{email_id}")
async def company_email_update(request: Request, company_id: str, email_id: str):
    if not _owned_entity(request, "company", company_id):
        return _err("Not found", 404)
    if not _child_of("email_addresses", email_id,
                     "entity_type = 'company' AND entity_id = ?", (company_id,)):
        return _err("Not found", 404)
    body = await request.json()
    fields = {k: body[k] for k in ("email_type", "started_at", "ended_at") if k in body}
    if "is_current" in body:
        fields["is_current"] = _bool_int(body["is_current"], 1)
    row = update_email_address(email_id, **fields) if fields else None
    if body.get("is_primary"):
        _set_exclusive_primary(
            "email_addresses", email_id,
            "entity_type = 'company' AND entity_id = ?", (company_id,),
        )
        with get_connection() as conn:
            row = dict(conn.execute(
                "SELECT * FROM email_addresses WHERE id = ?", (email_id,)
            ).fetchone())
    return row or {"ok": True}


@router.delete("/companies/{company_id}/emails/{email_id}")
def company_email_delete(request: Request, company_id: str, email_id: str):
    if not _owned_entity(request, "company", company_id):
        return _err("Not found", 404)
    if not _child_of("email_addresses", email_id,
                     "entity_type = 'company' AND entity_id = ?", (company_id,)):
        return _err("Not found", 404)
    remove_email_address(email_id)
    return {"ok": True}


# ---------------------------------------------------------------------------
# Company identifiers
# ---------------------------------------------------------------------------

@router.post("/companies/{company_id}/identifiers")
async def company_identifier_add(request: Request, company_id: str):
    if not _owned_entity(request, "company", company_id):
        return _err("Not found", 404)
    body = await request.json()
    id_type = (body.get("type") or "domain").strip()
    value = (body.get("value") or "").strip()
    if not value:
        return _err("value is required")
    if id_type == "domain":
        value = value.lower()
    try:
        return add_company_identifier(company_id, id_type, value)
    except sqlite3.IntegrityError:
        with get_connection() as conn:
            other = conn.execute(
                "SELECT ci.company_id, c.name FROM company_identifiers ci "
                "JOIN companies c ON c.id = ci.company_id "
                "WHERE ci.type = ? AND ci.value = ?",
                (id_type, value),
            ).fetchone()
        return _err(
            "This identifier already belongs to another company", 409,
            other_company_id=other["company_id"] if other else None,
            other_company_name=other["name"] if other else None,
        )


@router.delete("/companies/{company_id}/identifiers/{identifier_id}")
def company_identifier_delete(request: Request, company_id: str, identifier_id: str):
    if not _owned_entity(request, "company", company_id):
        return _err("Not found", 404)
    if not _child_of("company_identifiers", identifier_id, "company_id = ?", (company_id,)):
        return _err("Not found", 404)
    remove_company_identifier(identifier_id)
    return {"ok": True}


# ---------------------------------------------------------------------------
# Affiliations (contacts)
# ---------------------------------------------------------------------------

@router.post("/contacts/{contact_id}/affiliations")
async def affiliation_add(request: Request, contact_id: str):
    if not _owned_entity(request, "contact", contact_id):
        return _err("Not found", 404)
    body = await request.json()
    company_id = body.get("company_id")
    if not company_id:
        return _err("company_id is required")
    if not _owned_entity(request, "company", company_id):
        return _err("Company not found", 404)
    uid = request.state.user["id"] if request.state.user else None
    row = add_affiliation(
        contact_id, company_id,
        role_id=body.get("role_id") or None,
        title=body.get("title") or "",
        department=body.get("department") or "",
        is_primary=bool(body.get("is_primary")),
        is_current=_bool_int(body.get("is_current"), 1) == 1,
        notes=body.get("notes") or "",
        created_by=uid,
    )
    return _affiliation_with_names(row["id"]) or row


@router.put("/contacts/{contact_id}/affiliations/{affiliation_id}")
async def affiliation_update(request: Request, contact_id: str, affiliation_id: str):
    if not _owned_entity(request, "contact", contact_id):
        return _err("Not found", 404)
    if not _child_of("contact_companies", affiliation_id, "contact_id = ?", (contact_id,)):
        return _err("Not found", 404)
    body = await request.json()
    uid = request.state.user["id"] if request.state.user else None
    fields = {
        k: body[k] for k in ("role_id", "title", "department", "notes",
                             "started_at", "ended_at") if k in body
    }
    if "is_primary" in body:
        fields["is_primary"] = _bool_int(body["is_primary"])
    if "is_current" in body:
        fields["is_current"] = _bool_int(body["is_current"], 1)
    fields["updated_by"] = uid
    update_affiliation(affiliation_id, **fields)
    return _affiliation_with_names(affiliation_id) or {"ok": True}


@router.delete("/contacts/{contact_id}/affiliations/{affiliation_id}")
def affiliation_delete(request: Request, contact_id: str, affiliation_id: str):
    if not _owned_entity(request, "contact", contact_id):
        return _err("Not found", 404)
    if not _child_of("contact_companies", affiliation_id, "contact_id = ?", (contact_id,)):
        return _err("Not found", 404)
    remove_affiliation(affiliation_id)
    return {"ok": True}


# ---------------------------------------------------------------------------
# Company hierarchy
# ---------------------------------------------------------------------------

def _hierarchy_would_cycle(parent_id: str, child_id: str) -> bool:
    """True if making parent_id a parent of child_id creates a cycle
    (i.e. child_id is already an ancestor of parent_id)."""
    with get_connection() as conn:
        seen = set()
        frontier = [parent_id]
        while frontier:
            current = frontier.pop()
            if current == child_id:
                return True
            if current in seen:
                continue
            seen.add(current)
            frontier.extend(
                r["parent_company_id"] for r in conn.execute(
                    "SELECT parent_company_id FROM company_hierarchy "
                    "WHERE child_company_id = ?", (current,),
                ).fetchall()
            )
    return False


@router.post("/companies/{company_id}/hierarchy")
async def hierarchy_add(request: Request, company_id: str):
    if not _owned_entity(request, "company", company_id):
        return _err("Not found", 404)
    body = await request.json()
    related_id = body.get("related_company_id")
    if not related_id:
        return _err("related_company_id is required")
    if related_id == company_id:
        return _err("A company cannot be related to itself", 422)
    if not _owned_entity(request, "company", related_id):
        return _err("Related company not found", 404)

    direction = body.get("direction") or "parent"
    hierarchy_type = body.get("hierarchy_type") or "subsidiary"
    if hierarchy_type not in ("subsidiary", "division", "acquisition", "spinoff"):
        return _err("Invalid hierarchy type", 422)

    if direction == "parent":
        parent_id, child_id = related_id, company_id
    else:
        parent_id, child_id = company_id, related_id

    with get_connection() as conn:
        dup = conn.execute(
            "SELECT 1 FROM company_hierarchy "
            "WHERE parent_company_id = ? AND child_company_id = ?",
            (parent_id, child_id),
        ).fetchone()
    if dup:
        return _err("This relationship already exists", 409)
    if _hierarchy_would_cycle(parent_id, child_id):
        return _err("This relationship would create a cycle", 422)

    uid = request.state.user["id"] if request.state.user else None
    return add_company_hierarchy(parent_id, child_id, hierarchy_type, created_by=uid)


@router.delete("/companies/{company_id}/hierarchy/{hierarchy_id}")
def hierarchy_delete(request: Request, company_id: str, hierarchy_id: str):
    if not _owned_entity(request, "company", company_id):
        return _err("Not found", 404)
    if not _child_of(
        "company_hierarchy", hierarchy_id,
        "(parent_company_id = ? OR child_company_id = ?)", (company_id, company_id),
    ):
        return _err("Not found", 404)
    remove_company_hierarchy(hierarchy_id)
    return {"ok": True}


# ---------------------------------------------------------------------------
# Entity deletes
# ---------------------------------------------------------------------------

@router.delete("/companies/{company_id}")
def company_delete_api(request: Request, company_id: str):
    if not _owned_entity(request, "company", company_id):
        return _err("Not found", 404)
    result = delete_company(company_id)
    # Legacy left polymorphic rows orphaned; clean them up here
    with get_connection() as conn:
        for table in ("phone_numbers", "addresses", "email_addresses"):
            conn.execute(
                f"DELETE FROM {table} WHERE entity_type = 'company' AND entity_id = ?",
                (company_id,),
            )
    return {"ok": True, **result}


@router.delete("/contacts/{contact_id}")
def contact_delete_api(request: Request, contact_id: str):
    """New capability — the legacy UI never offered contact deletion.
    FK cascades remove identifiers/affiliations/visibility rows;
    conversation participants keep their rows with contact_id nulled."""
    if not _owned_entity(request, "contact", contact_id):
        return _err("Not found", 404)
    with get_connection() as conn:
        conn.execute("DELETE FROM contacts WHERE id = ?", (contact_id,))
        for table in ("phone_numbers", "addresses"):
            conn.execute(
                f"DELETE FROM {table} WHERE entity_type = 'contact' AND entity_id = ?",
                (contact_id,),
            )
    return {"ok": True}


# ---------------------------------------------------------------------------
# Score recompute
# ---------------------------------------------------------------------------

@router.post("/contacts/{contact_id}/score")
def contact_score_api(request: Request, contact_id: str):
    from ...scoring import (
        SCORE_TYPE, compute_contact_score, get_entity_score, upsert_entity_score,
    )

    if not _owned_entity(request, "contact", contact_id):
        return _err("Not found", 404)
    with get_connection() as conn:
        result = compute_contact_score(conn, contact_id)
        if result:
            upsert_entity_score(
                conn, "contact", contact_id, SCORE_TYPE,
                result["score"], result["factors"], triggered_by="web",
            )
    return {"score": get_entity_score("contact", contact_id)}


@router.post("/companies/{company_id}/score")
def company_score_api(request: Request, company_id: str):
    from ...scoring import (
        SCORE_TYPE, compute_company_score, get_entity_score, upsert_entity_score,
    )

    if not _owned_entity(request, "company", company_id):
        return _err("Not found", 404)
    with get_connection() as conn:
        result = compute_company_score(conn, company_id)
        if result:
            upsert_entity_score(
                conn, "company", company_id, SCORE_TYPE,
                result["score"], result["factors"], triggered_by="web",
            )
    return {"score": get_entity_score("company", company_id)}


# ---------------------------------------------------------------------------
# Contact core fields + duplicate pre-check (Contact Entity Base PRD KP-1)
# ---------------------------------------------------------------------------

@router.put("/contacts/{contact_id}")
async def contact_update_api(request: Request, contact_id: str):
    """Update core contact fields (name, status, source)."""
    from ...hierarchy import update_contact

    if not _owned_entity(request, "contact", contact_id):
        return _err("Not found", 404)
    body = await request.json()
    fields = {}
    if "name" in body:
        name = (body.get("name") or "").strip()
        if not name:
            return _err("name cannot be empty")
        fields["name"] = name
    if "status" in body:
        if body["status"] not in ("active", "incomplete", "archived"):
            return _err("Invalid status")
        fields["status"] = body["status"]
    if "source" in body:
        fields["source"] = (body.get("source") or "").strip()
    if not fields:
        return _err("No editable fields provided")
    row = update_contact(contact_id, **fields)
    return row or {"ok": True}


@router.post("/contacts/check")
async def contacts_check_api(request: Request):
    """Inline duplicate detection for the create form (KP-1 step 2).

    Matches by exact email identifier, normalized phone number, or
    case-insensitive exact name within the customer. Returns matches
    with what they matched on.
    """
    from ...phone_utils import normalize_phone

    cid = request.state.customer_id
    body = await request.json()
    email = (body.get("email") or "").strip().lower()
    phone = (body.get("phone") or "").strip()
    name = (body.get("name") or "").strip()

    matches: dict[str, dict] = {}

    with get_connection() as conn:
        if email:
            for r in conn.execute(
                """SELECT c.id, c.name, ci.value AS email FROM contact_identifiers ci
                   JOIN contacts c ON c.id = ci.contact_id
                   WHERE ci.type = 'email' AND ci.value = ?""",
                (email,),
            ).fetchall():
                matches.setdefault(r["id"], {
                    "id": r["id"], "name": r["name"], "email": r["email"],
                    "match_on": [],
                })["match_on"].append("email")

        if phone:
            normalized = normalize_phone(phone)
            if normalized:
                for r in conn.execute(
                    """SELECT c.id, c.name,
                              (SELECT ci.value FROM contact_identifiers ci
                               WHERE ci.contact_id = c.id AND ci.type = 'email'
                               LIMIT 1) AS email
                       FROM phone_numbers pn
                       JOIN contacts c ON c.id = pn.entity_id
                       WHERE pn.entity_type = 'contact' AND pn.number = ?
                         AND (c.customer_id IS NULL OR c.customer_id = ?)""",
                    (normalized, cid),
                ).fetchall():
                    matches.setdefault(r["id"], {
                        "id": r["id"], "name": r["name"], "email": r["email"],
                        "match_on": [],
                    })["match_on"].append("phone")

        if name:
            for r in conn.execute(
                """SELECT c.id, c.name,
                          (SELECT ci.value FROM contact_identifiers ci
                           WHERE ci.contact_id = c.id AND ci.type = 'email'
                           LIMIT 1) AS email
                   FROM contacts c
                   WHERE c.name = ? COLLATE NOCASE
                     AND (c.customer_id IS NULL OR c.customer_id = ?)
                     AND c.status != 'merged'""",
                (name, cid),
            ).fetchall():
                matches.setdefault(r["id"], {
                    "id": r["id"], "name": r["name"], "email": r["email"],
                    "match_on": [],
                })["match_on"].append("name")

    return {"matches": list(matches.values())}
