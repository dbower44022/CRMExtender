"""Company routes — list, search, create, delete, detail."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from ...database import get_connection
from ...hierarchy import (
    create_company, delete_company, list_companies, update_company,
    get_company_identifiers, add_company_identifier, remove_company_identifier,
    get_parent_companies, get_child_companies, add_company_hierarchy,
    remove_company_hierarchy,
)

router = APIRouter()

PUBLIC_DOMAINS = {
    "gmail.com", "googlemail.com", "yahoo.com", "yahoo.co.uk",
    "hotmail.com", "outlook.com", "live.com", "msn.com", "aol.com",
    "icloud.com", "me.com", "mac.com", "mail.com",
    "protonmail.com", "pm.me", "zoho.com", "yandex.com",
    "gmx.com", "fastmail.com", "tutanota.com", "hey.com",
    "comcast.net", "att.net", "verizon.net", "sbcglobal.net",
    "cox.net", "charter.net", "earthlink.net",
}


def _find_contacts_by_domain(domain: str) -> list[dict]:
    """Return unlinked contacts whose email matches *@domain*."""
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT c.id, c.name, ci.value AS email
               FROM contacts c
               JOIN contact_identifiers ci ON ci.contact_id = c.id AND ci.type = 'email'
               WHERE ci.value LIKE ?
                 AND c.company_id IS NULL
               ORDER BY c.name""",
            (f"%@{domain}",),
        ).fetchall()
    return [dict(r) for r in rows]


@router.get("", response_class=HTMLResponse)
def company_list(request: Request, q: str = ""):
    templates = request.app.state.templates

    if q:
        with get_connection() as conn:
            rows = conn.execute(
                """SELECT * FROM companies
                   WHERE status = 'active' AND (name LIKE ? OR domain LIKE ?)
                   ORDER BY name""",
                (f"%{q}%", f"%{q}%"),
            ).fetchall()
        companies = [dict(r) for r in rows]
    else:
        companies = list_companies()

    return templates.TemplateResponse(request, "companies/list.html", {
        "active_nav": "companies",
        "companies": companies,
        "q": q,
    })


@router.get("/search", response_class=HTMLResponse)
def company_search(request: Request, q: str = ""):
    templates = request.app.state.templates

    if q:
        with get_connection() as conn:
            rows = conn.execute(
                """SELECT * FROM companies
                   WHERE status = 'active' AND (name LIKE ? OR domain LIKE ?)
                   ORDER BY name""",
                (f"%{q}%", f"%{q}%"),
            ).fetchall()
        companies = [dict(r) for r in rows]
    else:
        companies = list_companies()

    return templates.TemplateResponse(request, "companies/_rows.html", {
        "companies": companies,
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

    # Check if we should show a confirmation preview
    if domain_clean and domain_clean not in PUBLIC_DOMAINS:
        matches = _find_contacts_by_domain(domain_clean)
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
        row = create_company(name, domain=domain, industry=industry,
                             description=description)
        if website or headquarters_location:
            update_company(row["id"], website=website,
                           headquarters_location=headquarters_location)
    except ValueError:
        pass
    if _is_htmx(request):
        return HTMLResponse("", headers={"HX-Redirect": "/companies"})
    return RedirectResponse("/companies", status_code=303)


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
    try:
        row = create_company(
            name, domain=domain, industry=industry, description=description,
        )
        if website or headquarters_location:
            update_company(row["id"], website=website,
                           headquarters_location=headquarters_location)
    except ValueError:
        if _is_htmx(request):
            return HTMLResponse("", headers={"HX-Redirect": "/companies"})
        return RedirectResponse("/companies", status_code=303)

    if link == "true" and domain.strip():
        domain_clean = domain.strip().lower()
        contacts = _find_contacts_by_domain(domain_clean)
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


@router.delete("/{company_id}", response_class=HTMLResponse)
def company_delete(request: Request, company_id: str):
    delete_company(company_id)
    return HTMLResponse("")


@router.get("/{company_id}", response_class=HTMLResponse)
def company_detail(request: Request, company_id: str):
    templates = request.app.state.templates

    with get_connection() as conn:
        company = conn.execute(
            "SELECT * FROM companies WHERE id = ?", (company_id,)
        ).fetchone()
        if not company:
            return HTMLResponse("Company not found", status_code=404)
        company = dict(company)

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
    all_companies = list_companies()

    return templates.TemplateResponse(request, "companies/detail.html", {
        "active_nav": "companies",
        "company": company,
        "contacts": contacts,
        "relationships": relationships,
        "identifiers": identifiers,
        "parents": parents,
        "children": children,
        "all_companies": all_companies,
    })


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
    if direction == "parent":
        add_company_hierarchy(related_company_id, company_id, hierarchy_type)
    else:
        add_company_hierarchy(company_id, related_company_id, hierarchy_type)

    parents = get_parent_companies(company_id)
    children = get_child_companies(company_id)
    all_companies = list_companies()

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
    remove_company_hierarchy(hierarchy_id)

    parents = get_parent_companies(company_id)
    children = get_child_companies(company_id)
    all_companies = list_companies()

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
