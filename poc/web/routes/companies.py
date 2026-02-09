"""Company routes — list, search, create, delete, detail."""

from __future__ import annotations

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from ...database import get_connection
from ...hierarchy import create_company, delete_company, list_companies

router = APIRouter()


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


@router.post("", response_class=HTMLResponse)
def company_create(
    request: Request,
    name: str = Form(...),
    domain: str = Form(""),
    industry: str = Form(""),
    description: str = Form(""),
):
    try:
        create_company(name, domain=domain, industry=industry, description=description)
    except ValueError:
        pass
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

    return templates.TemplateResponse(request, "companies/detail.html", {
        "active_nav": "companies",
        "company": company,
        "contacts": contacts,
    })
