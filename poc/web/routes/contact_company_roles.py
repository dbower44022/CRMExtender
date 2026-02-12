"""Settings routes for managing contact-company affiliation roles."""

from __future__ import annotations

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from ..dependencies import require_admin
from ...contact_company_roles import (
    create_role,
    delete_role,
    list_roles,
    update_role,
)

router = APIRouter()


@router.get("/settings/roles", response_class=HTMLResponse)
def roles_list(request: Request):
    require_admin(request)
    templates = request.app.state.templates
    cid = request.state.customer_id
    roles = list_roles(customer_id=cid)
    return templates.TemplateResponse(request, "settings/roles.html", {
        "settings_tab": "roles",
        "roles": roles,
    })


@router.post("/settings/roles", response_class=HTMLResponse)
def roles_create(
    request: Request,
    name: str = Form(...),
    sort_order: int = Form(0),
):
    require_admin(request)
    cid = request.state.customer_id
    user = request.state.user
    error = None
    try:
        create_role(name, customer_id=cid, sort_order=sort_order,
                     created_by=user["id"])
    except ValueError as exc:
        error = str(exc)

    templates = request.app.state.templates
    roles = list_roles(customer_id=cid)
    return templates.TemplateResponse(request, "settings/roles.html", {
        "settings_tab": "roles",
        "roles": roles,
        "error": error,
    })


@router.post("/settings/roles/{role_id}/edit", response_class=HTMLResponse)
def roles_update(
    request: Request,
    role_id: str,
    name: str = Form(...),
    sort_order: int = Form(0),
):
    require_admin(request)
    user = request.state.user
    cid = request.state.customer_id
    error = None
    try:
        update_role(role_id, name=name, sort_order=sort_order,
                     updated_by=user["id"])
    except ValueError as exc:
        error = str(exc)

    templates = request.app.state.templates
    roles = list_roles(customer_id=cid)
    return templates.TemplateResponse(request, "settings/roles.html", {
        "settings_tab": "roles",
        "roles": roles,
        "error": error,
    })


@router.delete("/settings/roles/{role_id}", response_class=HTMLResponse)
def roles_delete(request: Request, role_id: str):
    require_admin(request)
    cid = request.state.customer_id
    error = None
    try:
        delete_role(role_id)
    except ValueError as exc:
        error = str(exc)

    templates = request.app.state.templates
    roles = list_roles(customer_id=cid)
    return templates.TemplateResponse(request, "settings/roles.html", {
        "settings_tab": "roles",
        "roles": roles,
        "error": error,
    })
