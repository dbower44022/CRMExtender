"""Company routes — list, search, create, delete, detail, merge, duplicates."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from ...access import my_companies_query, visible_companies_query
from ...company_merge import (
    detect_all_duplicates,
    find_duplicates_for_domain,
    get_merge_preview,
    merge_companies,
)
from ...database import get_connection
from ...domain_resolver import PUBLIC_DOMAINS
from ...hierarchy import (
    create_company, delete_company, list_companies, update_company,
    get_company_identifiers, add_company_identifier, remove_company_identifier,
    get_parent_companies, get_child_companies, add_company_hierarchy,
    remove_company_hierarchy,
    get_phone_numbers, add_phone_number, remove_phone_number,
    get_addresses, add_address, remove_address,
    add_email_address, get_email_addresses, remove_email_address,
)

router = APIRouter()


def _find_contacts_by_domain(domain: str, *, customer_id: str | None = None) -> list[dict]:
    """Return unlinked contacts whose email matches *@domain*."""
    clauses = ["ci.value LIKE ?", "c.company_id IS NULL"]
    params: list = [f"%@{domain}"]
    if customer_id:
        clauses.append("c.customer_id = ?")
        params.append(customer_id)
    where = " AND ".join(clauses)
    with get_connection() as conn:
        rows = conn.execute(
            f"""SELECT c.id, c.name, ci.value AS email
               FROM contacts c
               JOIN contact_identifiers ci ON ci.contact_id = c.id AND ci.type = 'email'
               WHERE {where}
               ORDER BY c.name""",
            params,
        ).fetchall()
    return [dict(r) for r in rows]


_COMPANY_SORT_MAP = {
    "name": "co.name", "domain": "co.domain",
    "industry": "co.industry", "score": "es.score_value",
}


def _list_companies_with_scores(
    q: str = "", sort: str = "name",
    *, customer_id: str = "", user_id: str = "", scope: str = "all",
) -> list[dict]:
    """Return companies with their relationship strength scores."""
    desc = sort.startswith("-")
    key = sort.lstrip("-")
    col = _COMPANY_SORT_MAP.get(key, "co.name")
    direction = "DESC" if desc else "ASC"
    order = f"{col} IS NULL, {col} {direction}" if key == "score" else f"{col} {direction}"

    clauses: list[str] = ["co.status = 'active'"]
    params: list = []

    # Visibility scoping
    if scope == "mine" and customer_id and user_id:
        my_where, my_params = my_companies_query(customer_id, user_id)
        clauses.append(my_where)
        params.extend(my_params)
    elif customer_id and user_id:
        vis_where, vis_params = visible_companies_query(customer_id, user_id)
        clauses.append(vis_where)
        params.extend(vis_params)

    if q:
        clauses.append("(co.name LIKE ? OR co.domain LIKE ?)")
        params.extend([f"%{q}%", f"%{q}%"])

    where = f"WHERE {' AND '.join(clauses)}"

    # Extra JOIN for "mine" scope
    mine_join = ""
    if scope == "mine" and customer_id and user_id:
        mine_join = "JOIN user_companies uco ON uco.company_id = co.id"

    with get_connection() as conn:
        rows = conn.execute(
            f"""SELECT co.*, es.score_value AS score
               FROM companies co
               {mine_join}
               LEFT JOIN entity_scores es
                 ON es.entity_type = 'company'
                AND es.entity_id = co.id
                AND es.score_type = 'relationship_strength'
               {where}
               ORDER BY {order}""",
            params,
        ).fetchall()
    return [dict(r) for r in rows]


@router.get("", response_class=HTMLResponse)
def company_list(request: Request, q: str = "", sort: str = "name",
                 scope: str = "all"):
    templates = request.app.state.templates
    user = request.state.user
    cid = request.state.customer_id
    companies = _list_companies_with_scores(
        q, sort, customer_id=cid, user_id=user["id"], scope=scope,
    )

    return templates.TemplateResponse(request, "companies/list.html", {
        "active_nav": "companies",
        "companies": companies,
        "q": q,
        "sort": sort,
        "scope": scope,
    })


@router.get("/search", response_class=HTMLResponse)
def company_search(request: Request, q: str = "", sort: str = "name",
                   scope: str = "all"):
    templates = request.app.state.templates
    user = request.state.user
    cid = request.state.customer_id
    companies = _list_companies_with_scores(
        q, sort, customer_id=cid, user_id=user["id"], scope=scope,
    )

    return templates.TemplateResponse(request, "companies/_rows.html", {
        "companies": companies,
        "q": q,
        "sort": sort,
        "scope": scope,
    })


def _is_htmx(request: Request) -> bool:
    return request.headers.get("HX-Request") == "true"


@router.post("", response_class=HTMLResponse)
def company_create(
    request: Request,
    name: str = Form(...),
    domain: str = Form(""),
    industry: str = Form(""),
    description: str = Form(""),
    website: str = Form(""),
    headquarters_location: str = Form(""),
):
    templates = request.app.state.templates
    domain_clean = domain.strip().lower()
    user = request.state.user
    cid = request.state.customer_id

    # Check for existing companies with the same domain (duplicate warning)
    if domain_clean and domain_clean not in PUBLIC_DOMAINS:
        existing = find_duplicates_for_domain(domain_clean)
        if existing:
            ctx = {
                "active_nav": "companies",
                "name": name,
                "domain": domain,
                "industry": industry,
                "description": description,
                "website": website,
                "headquarters_location": headquarters_location,
                "existing_companies": existing,
            }
            template = ("companies/_duplicate_warning.html" if _is_htmx(request)
                        else "companies/duplicate_warning.html")
            return templates.TemplateResponse(request, template, ctx)

    # Check if we should show a confirmation preview
    if domain_clean and domain_clean not in PUBLIC_DOMAINS:
        matches = _find_contacts_by_domain(domain_clean, customer_id=cid)
        if matches:
            ctx = {
                "active_nav": "companies",
                "name": name,
                "domain": domain,
                "industry": industry,
                "description": description,
                "website": website,
                "headquarters_location": headquarters_location,
                "contacts": matches,
            }
            template = ("companies/_confirm_link.html" if _is_htmx(request)
                        else "companies/confirm_link.html")
            return templates.TemplateResponse(request, template, ctx)

    # No preview needed — create directly
    try:
        row = create_company(
            name, domain=domain, industry=industry,
            description=description,
            customer_id=cid, created_by=user["id"],
        )
        if website or headquarters_location:
            update_company(row["id"], website=website,
                           headquarters_location=headquarters_location)
        # Link user to company
        _link_user_to_company(user["id"], row["id"])
    except ValueError:
        pass
    if _is_htmx(request):
        return HTMLResponse("", headers={"HX-Redirect": "/companies"})
    return RedirectResponse("/companies", status_code=303)


def _link_user_to_company(user_id: str, company_id: str) -> None:
    """Create a user_companies row linking the user to the company."""
    now = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        conn.execute(
            """INSERT OR IGNORE INTO user_companies
               (id, user_id, company_id, visibility, is_owner, created_at, updated_at)
               VALUES (?, ?, ?, 'public', 1, ?, ?)""",
            (str(uuid.uuid4()), user_id, company_id, now, now),
        )


@router.post("/confirm", response_class=HTMLResponse)
def company_confirm(
    request: Request,
    name: str = Form(...),
    domain: str = Form(""),
    industry: str = Form(""),
    description: str = Form(""),
    website: str = Form(""),
    headquarters_location: str = Form(""),
    link: str = Form("false"),
):
    user = request.state.user
    cid = request.state.customer_id

    try:
        row = create_company(
            name, domain=domain, industry=industry, description=description,
            customer_id=cid, created_by=user["id"],
        )
        if website or headquarters_location:
            update_company(row["id"], website=website,
                           headquarters_location=headquarters_location)
        _link_user_to_company(user["id"], row["id"])
    except ValueError:
        if _is_htmx(request):
            return HTMLResponse("", headers={"HX-Redirect": "/companies"})
        return RedirectResponse("/companies", status_code=303)

    if link == "true" and domain.strip():
        domain_clean = domain.strip().lower()
        contacts = _find_contacts_by_domain(domain_clean, customer_id=cid)
        if contacts:
            now = datetime.now(timezone.utc).isoformat()
            with get_connection() as conn:
                conn.executemany(
                    "UPDATE contacts SET company_id = ?, updated_at = ? WHERE id = ?",
                    [(row["id"], now, c["id"]) for c in contacts],
                )

    if _is_htmx(request):
        return HTMLResponse("", headers={"HX-Redirect": "/companies"})
    return RedirectResponse("/companies", status_code=303)


@router.post("/resolve-domains", response_class=HTMLResponse)
def company_resolve_domains(request: Request):
    from ...domain_resolver import resolve_unlinked_contacts

    result = resolve_unlinked_contacts()
    return HTMLResponse(
        f"<p><strong>{result.contacts_linked}</strong> contact(s) linked. "
        f"({result.contacts_skipped_public} public, "
        f"{result.contacts_skipped_no_match} no match)</p>"
    )


@router.get("/duplicates", response_class=HTMLResponse)
def company_duplicates(request: Request):
    templates = request.app.state.templates
    groups = detect_all_duplicates()
    return templates.TemplateResponse(request, "companies/duplicates.html", {
        "active_nav": "companies",
        "groups": groups,
    })


@router.delete("/{company_id}", response_class=HTMLResponse)
def company_delete(request: Request, company_id: str):
    delete_company(company_id)
    return HTMLResponse("")


@router.get("/{company_id}", response_class=HTMLResponse)
def company_detail(request: Request, company_id: str):
    templates = request.app.state.templates
    cid = request.state.customer_id

    with get_connection() as conn:
        company = conn.execute(
            "SELECT * FROM companies WHERE id = ?", (company_id,)
        ).fetchone()
        if not company:
            return HTMLResponse("Company not found", status_code=404)
        company = dict(company)

        # Cross-customer access check
        if company.get("customer_id") and company["customer_id"] != cid:
            return HTMLResponse("Company not found", status_code=404)

        contacts = conn.execute(
            """SELECT c.*, ci.value AS email
               FROM contacts c
               LEFT JOIN contact_identifiers ci ON ci.contact_id = c.id AND ci.type = 'email'
               WHERE c.company_id = ?
               ORDER BY c.name""",
            (company_id,),
        ).fetchall()
        contacts = [dict(r) for r in contacts]

        # Relationships involving this company (bidirectional pairs stored as two rows)
        import json
        rels = conn.execute(
            """SELECT r.*, rt.name AS type_name,
                      rt.forward_label, rt.reverse_label
               FROM relationships r
               JOIN relationship_types rt ON rt.id = r.relationship_type_id
               WHERE r.from_entity_id = ?
               ORDER BY r.updated_at DESC""",
            (company_id,),
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
            # Resolve other entity name
            if rd["other_entity_type"] == "contact":
                ct = conn.execute(
                    """SELECT c.name, ci.value AS email FROM contacts c
                       LEFT JOIN contact_identifiers ci ON ci.contact_id = c.id AND ci.type = 'email'
                       WHERE c.id = ?""",
                    (rd["other_id"],),
                ).fetchone()
                rd["other_name"] = (ct["name"] or ct["email"]) if ct else rd["other_id"][:8]
            else:
                co = conn.execute(
                    "SELECT name FROM companies WHERE id = ?", (rd["other_id"],)
                ).fetchone()
                rd["other_name"] = co["name"] if co else rd["other_id"][:8]
            relationships.append(rd)

    identifiers = get_company_identifiers(company_id)
    parents = get_parent_companies(company_id)
    children = get_child_companies(company_id)
    all_companies = list_companies(customer_id=cid)
    phones = get_phone_numbers("company", company_id)
    addresses = get_addresses("company", company_id)
    emails = get_email_addresses("company", company_id)

    with get_connection() as conn:
        social_profiles = [
            dict(r) for r in conn.execute(
                "SELECT * FROM company_social_profiles WHERE company_id = ? ORDER BY platform",
                (company_id,),
            ).fetchall()
        ]

    from ...phone_utils import resolve_country_code
    display_country = resolve_country_code("company", company_id, customer_id=cid)

    from ...scoring import get_entity_score
    score_data = get_entity_score("company", company_id)

    return templates.TemplateResponse(request, "companies/detail.html", {
        "active_nav": "companies",
        "company": company,
        "contacts": contacts,
        "relationships": relationships,
        "identifiers": identifiers,
        "parents": parents,
        "children": children,
        "all_companies": all_companies,
        "phones": phones,
        "addresses": addresses,
        "emails": emails,
        "social_profiles": social_profiles,
        "score_data": score_data,
        "display_country": display_country,
    })


@router.post("/{company_id}/score", response_class=HTMLResponse)
def company_score(request: Request, company_id: str):
    from ...scoring import SCORE_TYPE, compute_company_score, get_entity_score, upsert_entity_score
    templates = request.app.state.templates

    with get_connection() as conn:
        company = conn.execute(
            "SELECT * FROM companies WHERE id = ?", (company_id,)
        ).fetchone()
        if not company:
            return HTMLResponse("Company not found", status_code=404)
        company = dict(company)

        result = compute_company_score(conn, company_id)
        if result:
            upsert_entity_score(
                conn, "company", company_id, SCORE_TYPE,
                result["score"], result["factors"], triggered_by="web",
            )

    score_data = get_entity_score("company", company_id)

    return templates.TemplateResponse(request, "companies/_score.html", {
        "company": company,
        "score_data": score_data,
    })


@router.post("/{company_id}/enrich", response_class=HTMLResponse)
def company_enrich(request: Request, company_id: str):
    # Import triggers provider registration
    from ...website_scraper import _provider  # noqa: F401
    from ...enrichment_pipeline import execute_enrichment

    result = execute_enrichment("company", company_id, "website_scraper")
    if _is_htmx(request):
        return HTMLResponse("", headers={"HX-Redirect": f"/companies/{company_id}"})
    return RedirectResponse(f"/companies/{company_id}", status_code=303)


@router.get("/{company_id}/merge", response_class=HTMLResponse)
def company_merge_page(request: Request, company_id: str):
    templates = request.app.state.templates
    cid = request.state.customer_id
    with get_connection() as conn:
        company = conn.execute(
            "SELECT * FROM companies WHERE id = ?", (company_id,)
        ).fetchone()
        if not company:
            return HTMLResponse("Company not found", status_code=404)
        company = dict(company)

    all_companies = list_companies(customer_id=cid)
    return templates.TemplateResponse(request, "companies/merge.html", {
        "active_nav": "companies",
        "company": company,
        "all_companies": all_companies,
    })


@router.post("/{company_id}/merge", response_class=HTMLResponse)
def company_merge_preview(
    request: Request,
    company_id: str,
    target_id: str = Form(...),
):
    templates = request.app.state.templates
    cid = request.state.customer_id
    with get_connection() as conn:
        company = conn.execute(
            "SELECT * FROM companies WHERE id = ?", (company_id,)
        ).fetchone()
        if not company:
            return HTMLResponse("Company not found", status_code=404)
        company = dict(company)

    try:
        preview = get_merge_preview(company_id, target_id)
    except ValueError as exc:
        all_companies = list_companies(customer_id=cid)
        return templates.TemplateResponse(request, "companies/merge.html", {
            "active_nav": "companies",
            "company": company,
            "all_companies": all_companies,
            "error": str(exc),
        })

    all_companies = list_companies(customer_id=cid)
    return templates.TemplateResponse(request, "companies/merge.html", {
        "active_nav": "companies",
        "company": company,
        "all_companies": all_companies,
        "preview": preview,
    })


@router.post("/{company_id}/merge/confirm", response_class=HTMLResponse)
def company_merge_execute(
    request: Request,
    company_id: str,
    surviving_id: str = Form(...),
    company_a: str = Form(...),
    company_b: str = Form(...),
):
    cid = request.state.customer_id
    # Determine which is absorbed based on surviving_id choice
    absorbed_id = company_b if surviving_id == company_a else company_a

    try:
        merge_companies(surviving_id, absorbed_id)
    except ValueError as exc:
        templates = request.app.state.templates
        with get_connection() as conn:
            company = conn.execute(
                "SELECT * FROM companies WHERE id = ?", (company_id,)
            ).fetchone()
            company = dict(company) if company else {"id": company_id, "name": "Unknown"}
        all_companies = list_companies(customer_id=cid)
        return templates.TemplateResponse(request, "companies/merge.html", {
            "active_nav": "companies",
            "company": company,
            "all_companies": all_companies,
            "error": str(exc),
        })

    if _is_htmx(request):
        return HTMLResponse("", headers={"HX-Redirect": f"/companies/{surviving_id}"})
    return RedirectResponse(f"/companies/{surviving_id}", status_code=303)


@router.get("/{company_id}/edit", response_class=HTMLResponse)
def company_edit_form(request: Request, company_id: str):
    templates = request.app.state.templates

    with get_connection() as conn:
        company = conn.execute(
            "SELECT * FROM companies WHERE id = ?", (company_id,)
        ).fetchone()
        if not company:
            return HTMLResponse("Company not found", status_code=404)
        company = dict(company)

    return templates.TemplateResponse(request, "companies/edit.html", {
        "active_nav": "companies",
        "company": company,
    })


@router.post("/{company_id}/edit", response_class=HTMLResponse)
def company_edit(
    request: Request,
    company_id: str,
    name: str = Form(...),
    domain: str = Form(""),
    industry: str = Form(""),
    description: str = Form(""),
    website: str = Form(""),
    stock_symbol: str = Form(""),
    size_range: str = Form(""),
    employee_count: str = Form(""),
    founded_year: str = Form(""),
    revenue_range: str = Form(""),
    funding_total: str = Form(""),
    funding_stage: str = Form(""),
    headquarters_location: str = Form(""),
    status: str = Form("active"),
):
    fields = dict(
        name=name, domain=domain, industry=industry, description=description,
        website=website, stock_symbol=stock_symbol, size_range=size_range,
        employee_count=int(employee_count) if employee_count else None,
        founded_year=int(founded_year) if founded_year else None,
        revenue_range=revenue_range, funding_total=funding_total,
        funding_stage=funding_stage, headquarters_location=headquarters_location,
        status=status,
    )
    update_company(company_id, **fields)
    if _is_htmx(request):
        return HTMLResponse("", headers={"HX-Redirect": f"/companies/{company_id}"})
    return RedirectResponse(f"/companies/{company_id}", status_code=303)


@router.post("/{company_id}/identifiers", response_class=HTMLResponse)
def company_add_identifier(
    request: Request,
    company_id: str,
    type: str = Form("domain"),
    value: str = Form(...),
):
    templates = request.app.state.templates
    add_company_identifier(company_id, type, value)
    identifiers = get_company_identifiers(company_id)

    with get_connection() as conn:
        company = conn.execute(
            "SELECT * FROM companies WHERE id = ?", (company_id,)
        ).fetchone()
        company = dict(company)

    return templates.TemplateResponse(request, "companies/_identifiers.html", {
        "company": company,
        "identifiers": identifiers,
    })


@router.delete("/{company_id}/identifiers/{identifier_id}", response_class=HTMLResponse)
def company_remove_identifier(
    request: Request, company_id: str, identifier_id: str,
):
    templates = request.app.state.templates
    remove_company_identifier(identifier_id)
    identifiers = get_company_identifiers(company_id)

    with get_connection() as conn:
        company = conn.execute(
            "SELECT * FROM companies WHERE id = ?", (company_id,)
        ).fetchone()
        company = dict(company)

    return templates.TemplateResponse(request, "companies/_identifiers.html", {
        "company": company,
        "identifiers": identifiers,
    })


@router.post("/{company_id}/hierarchy", response_class=HTMLResponse)
def company_add_hierarchy(
    request: Request,
    company_id: str,
    related_company_id: str = Form(...),
    direction: str = Form("parent"),
    hierarchy_type: str = Form("subsidiary"),
):
    templates = request.app.state.templates
    cid = request.state.customer_id
    if direction == "parent":
        add_company_hierarchy(related_company_id, company_id, hierarchy_type)
    else:
        add_company_hierarchy(company_id, related_company_id, hierarchy_type)

    parents = get_parent_companies(company_id)
    children = get_child_companies(company_id)
    all_companies = list_companies(customer_id=cid)

    with get_connection() as conn:
        company = conn.execute(
            "SELECT * FROM companies WHERE id = ?", (company_id,)
        ).fetchone()
        company = dict(company)

    return templates.TemplateResponse(request, "companies/_hierarchy.html", {
        "company": company,
        "parents": parents,
        "children": children,
        "all_companies": all_companies,
    })


@router.delete("/{company_id}/hierarchy/{hierarchy_id}", response_class=HTMLResponse)
def company_remove_hierarchy(
    request: Request, company_id: str, hierarchy_id: str,
):
    templates = request.app.state.templates
    cid = request.state.customer_id
    remove_company_hierarchy(hierarchy_id)

    parents = get_parent_companies(company_id)
    children = get_child_companies(company_id)
    all_companies = list_companies(customer_id=cid)

    with get_connection() as conn:
        company = conn.execute(
            "SELECT * FROM companies WHERE id = ?", (company_id,)
        ).fetchone()
        company = dict(company)

    return templates.TemplateResponse(request, "companies/_hierarchy.html", {
        "company": company,
        "parents": parents,
        "children": children,
        "all_companies": all_companies,
    })


# ---------------------------------------------------------------------------
# Phone numbers
# ---------------------------------------------------------------------------

@router.post("/{company_id}/phones", response_class=HTMLResponse)
def company_add_phone(
    request: Request,
    company_id: str,
    phone_type: str = Form("main"),
    number: str = Form(...),
):
    templates = request.app.state.templates
    cid = request.state.customer_id
    result = add_phone_number("company", company_id, number,
                              phone_type=phone_type, customer_id=cid)
    phones = get_phone_numbers("company", company_id)

    from ...phone_utils import resolve_country_code
    display_country = resolve_country_code("company", company_id, customer_id=cid)

    ctx = {
        "company": {"id": company_id},
        "phones": phones,
        "display_country": display_country,
    }
    if result is None:
        ctx["phone_error"] = "Invalid phone number."
    return templates.TemplateResponse(request, "companies/_phones.html", ctx)


@router.delete("/{company_id}/phones/{phone_id}", response_class=HTMLResponse)
def company_remove_phone(
    request: Request, company_id: str, phone_id: str,
):
    templates = request.app.state.templates
    cid = request.state.customer_id
    remove_phone_number(phone_id)
    phones = get_phone_numbers("company", company_id)

    from ...phone_utils import resolve_country_code
    display_country = resolve_country_code("company", company_id, customer_id=cid)

    return templates.TemplateResponse(request, "companies/_phones.html", {
        "company": {"id": company_id},
        "phones": phones,
        "display_country": display_country,
    })


# ---------------------------------------------------------------------------
# Addresses
# ---------------------------------------------------------------------------

@router.post("/{company_id}/addresses", response_class=HTMLResponse)
def company_add_address(
    request: Request,
    company_id: str,
    address_type: str = Form("work"),
    street: str = Form(""),
    city: str = Form(""),
    state: str = Form(""),
    postal_code: str = Form(""),
    country: str = Form(""),
):
    templates = request.app.state.templates
    add_address(
        "company", company_id,
        address_type=address_type, street=street, city=city,
        state=state, postal_code=postal_code, country=country,
    )
    addresses = get_addresses("company", company_id)

    return templates.TemplateResponse(request, "companies/_addresses.html", {
        "company": {"id": company_id},
        "addresses": addresses,
    })


@router.delete("/{company_id}/addresses/{address_id}", response_class=HTMLResponse)
def company_remove_address(
    request: Request, company_id: str, address_id: str,
):
    templates = request.app.state.templates
    remove_address(address_id)
    addresses = get_addresses("company", company_id)

    return templates.TemplateResponse(request, "companies/_addresses.html", {
        "company": {"id": company_id},
        "addresses": addresses,
    })


# ---------------------------------------------------------------------------
# Email Addresses
# ---------------------------------------------------------------------------

@router.post("/{company_id}/emails", response_class=HTMLResponse)
def company_add_email(
    request: Request,
    company_id: str,
    email_type: str = Form("general"),
    address: str = Form(...),
):
    templates = request.app.state.templates
    add_email_address("company", company_id, address, email_type=email_type)
    emails = get_email_addresses("company", company_id)

    return templates.TemplateResponse(request, "companies/_emails.html", {
        "company": {"id": company_id},
        "emails": emails,
    })


@router.delete("/{company_id}/emails/{email_id}", response_class=HTMLResponse)
def company_remove_email(
    request: Request, company_id: str, email_id: str,
):
    templates = request.app.state.templates
    remove_email_address(email_id)
    emails = get_email_addresses("company", company_id)

    return templates.TemplateResponse(request, "companies/_emails.html", {
        "company": {"id": company_id},
        "emails": emails,
    })
