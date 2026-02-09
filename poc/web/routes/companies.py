"""Company routes — list, search, create, delete, detail."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from ...database import get_connection
from ...hierarchy import create_company, delete_company, list_companies

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
                "contacts": matches,
            }
            template = ("companies/_confirm_link.html" if _is_htmx(request)
                        else "companies/confirm_link.html")
            return templates.TemplateResponse(request, template, ctx)

    # No preview needed — create directly
    try:
        create_company(name, domain=domain, industry=industry, description=description)
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
    link: str = Form("false"),
):
    try:
        row = create_company(
            name, domain=domain, industry=industry, description=description,
        )
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

        # Relationships involving this company
        import json
        rels = conn.execute(
            """SELECT r.*, rt.name AS type_name,
                      rt.forward_label, rt.reverse_label
               FROM relationships r
               JOIN relationship_types rt ON rt.id = r.relationship_type_id
               WHERE r.from_entity_id = ? OR r.to_entity_id = ?
               ORDER BY r.updated_at DESC""",
            (company_id, company_id),
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
            is_from = rd["from_entity_id"] == company_id
            rd["other_id"] = rd["to_entity_id"] if is_from else rd["from_entity_id"]
            rd["other_entity_type"] = rd["to_entity_type"] if is_from else rd["from_entity_type"]
            rd["label"] = rd["forward_label"] if is_from else rd["reverse_label"]
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

    return templates.TemplateResponse(request, "companies/detail.html", {
        "active_nav": "companies",
        "company": company,
        "contacts": contacts,
        "relationships": relationships,
    })
