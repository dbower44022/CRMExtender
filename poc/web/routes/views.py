"""Views routes — dashboard, grid rendering, CRUD, search."""

from __future__ import annotations

import json

from fastapi import APIRouter, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from ...database import get_connection
from ...views.crud import (
    create_view,
    delete_view,
    duplicate_view,
    ensure_default_views,
    get_all_views_for_user,
    get_data_sources_for_customer,
    get_view,
    get_view_with_config,
    get_views_for_entity,
    update_view,
    update_view_columns,
    update_view_filters,
)
from ...views.engine import execute_view
from ...views.registry import ENTITY_TYPES

router = APIRouter()


def _templates(request: Request):
    return request.app.state.templates


def _user(request: Request) -> dict:
    return getattr(request.state, "user", {}) or {}


def _is_htmx(request: Request) -> bool:
    return request.headers.get("HX-Request") == "true"


# -----------------------------------------------------------------------
# Dashboard — all views grouped by entity type
# -----------------------------------------------------------------------

@router.get("")
def views_index(request: Request, entity_type: str = ""):
    user = _user(request)
    customer_id = user.get("customer_id", "")
    user_id = user.get("id", "")
    templates = _templates(request)

    with get_connection() as conn:
        ensure_default_views(conn, customer_id, user_id)
        all_views = get_all_views_for_user(conn, customer_id, user_id)

    # Group by entity type
    grouped: dict[str, list[dict]] = {}
    for v in all_views:
        et = v.get("entity_type", "")
        grouped.setdefault(et, []).append(v)

    # Filter to specific entity type if requested
    if entity_type and entity_type in ENTITY_TYPES:
        grouped = {entity_type: grouped.get(entity_type, [])}

    return templates.TemplateResponse(request, "views/index.html", {
        "active_nav": "views",
        "grouped_views": grouped,
        "entity_types": ENTITY_TYPES,
        "filter_entity_type": entity_type,
    })


# -----------------------------------------------------------------------
# Create view
# -----------------------------------------------------------------------

@router.get("/new")
def new_view_form(request: Request, entity_type: str = ""):
    user = _user(request)
    customer_id = user.get("customer_id", "")
    templates = _templates(request)

    with get_connection() as conn:
        data_sources = get_data_sources_for_customer(conn, customer_id)

    return templates.TemplateResponse(request, "views/new.html", {
        "active_nav": "views",
        "data_sources": data_sources,
        "entity_types": ENTITY_TYPES,
        "selected_entity_type": entity_type,
    })


@router.post("/new")
def create_new_view(
    request: Request,
    name: str = Form(""),
    entity_type: str = Form(""),
):
    user = _user(request)
    customer_id = user.get("customer_id", "")
    user_id = user.get("id", "")

    if not name or not entity_type:
        return RedirectResponse("/views/new", status_code=303)

    with get_connection() as conn:
        # Find data source for this entity type
        ds_id = f"ds-{entity_type}-{customer_id}"
        from ...views.crud import ensure_system_data_sources, get_data_source
        ensure_system_data_sources(conn, customer_id)
        ds = get_data_source(conn, ds_id)
        if not ds:
            return RedirectResponse("/views/new", status_code=303)

        view_id = create_view(
            conn,
            customer_id=customer_id,
            user_id=user_id,
            data_source_id=ds_id,
            name=name,
        )

    return RedirectResponse(f"/views/{view_id}", status_code=303)


# -----------------------------------------------------------------------
# View grid (main view page)
# -----------------------------------------------------------------------

@router.get("/{view_id}")
def view_grid(
    request: Request,
    view_id: str,
    q: str = "",
    page: int = 1,
    sort: str = "",
):
    user = _user(request)
    customer_id = user.get("customer_id", "")
    user_id = user.get("id", "")
    templates = _templates(request)

    with get_connection() as conn:
        view = get_view_with_config(conn, view_id)
        if not view or view.get("customer_id") != customer_id:
            return HTMLResponse("View not found", status_code=404)

        entity_type = view["entity_type"]

        # Parse sort from URL (overrides view default)
        sort_field = view.get("sort_field")
        sort_direction = view.get("sort_direction", "asc")
        if sort:
            if sort.startswith("-"):
                sort_field = sort[1:]
                sort_direction = "desc"
            else:
                sort_field = sort
                sort_direction = "asc"

        rows, total = execute_view(
            conn,
            entity_type=entity_type,
            columns=view["columns"],
            filters=view["filters"],
            sort_field=sort_field,
            sort_direction=sort_direction,
            search=q,
            page=page,
            per_page=view.get("per_page", 50),
            customer_id=customer_id,
            user_id=user_id,
        )

        # Sibling views for tab bar
        sibling_views = get_views_for_entity(
            conn, customer_id, user_id, entity_type,
        )

    per_page = view.get("per_page", 50)
    total_pages = max(1, (total + per_page - 1) // per_page)
    entity_def = ENTITY_TYPES.get(entity_type)

    return templates.TemplateResponse(request, "views/grid.html", {
        "active_nav": "views",
        "view": view,
        "entity_def": entity_def,
        "entity_type": entity_type,
        "rows": rows,
        "total": total,
        "page": page,
        "total_pages": total_pages,
        "q": q,
        "sort": sort or (
            ("-" + sort_field if sort_direction == "desc" else sort_field)
            if sort_field else ""
        ),
        "sort_field": sort_field,
        "sort_direction": sort_direction,
        "sibling_views": sibling_views,
    })


# -----------------------------------------------------------------------
# HTMX search partial
# -----------------------------------------------------------------------

@router.get("/{view_id}/search")
def view_search(
    request: Request,
    view_id: str,
    q: str = "",
    page: int = 1,
    sort: str = "",
):
    user = _user(request)
    customer_id = user.get("customer_id", "")
    user_id = user.get("id", "")
    templates = _templates(request)

    with get_connection() as conn:
        view = get_view_with_config(conn, view_id)
        if not view or view.get("customer_id") != customer_id:
            return HTMLResponse("View not found", status_code=404)

        entity_type = view["entity_type"]

        sort_field = view.get("sort_field")
        sort_direction = view.get("sort_direction", "asc")
        if sort:
            if sort.startswith("-"):
                sort_field = sort[1:]
                sort_direction = "desc"
            else:
                sort_field = sort
                sort_direction = "asc"

        rows, total = execute_view(
            conn,
            entity_type=entity_type,
            columns=view["columns"],
            filters=view["filters"],
            sort_field=sort_field,
            sort_direction=sort_direction,
            search=q,
            page=page,
            per_page=view.get("per_page", 50),
            customer_id=customer_id,
            user_id=user_id,
        )

    per_page = view.get("per_page", 50)
    total_pages = max(1, (total + per_page - 1) // per_page)
    entity_def = ENTITY_TYPES.get(entity_type)

    return templates.TemplateResponse(request, "views/_rows.html", {
        "view": view,
        "entity_def": entity_def,
        "entity_type": entity_type,
        "rows": rows,
        "total": total,
        "page": page,
        "total_pages": total_pages,
        "q": q,
        "sort": sort or (
            ("-" + sort_field if sort_direction == "desc" else sort_field)
            if sort_field else ""
        ),
        "sort_field": sort_field,
        "sort_direction": sort_direction,
    })


# -----------------------------------------------------------------------
# Edit view
# -----------------------------------------------------------------------

@router.get("/{view_id}/edit")
def edit_view_form(request: Request, view_id: str):
    user = _user(request)
    customer_id = user.get("customer_id", "")
    templates = _templates(request)

    with get_connection() as conn:
        view = get_view_with_config(conn, view_id)
        if not view or view.get("customer_id") != customer_id:
            return HTMLResponse("View not found", status_code=404)

    entity_type = view["entity_type"]
    entity_def = ENTITY_TYPES.get(entity_type)
    active_column_keys = [c["field_key"] for c in view.get("columns", [])]

    return templates.TemplateResponse(request, "views/edit.html", {
        "active_nav": "views",
        "view": view,
        "entity_def": entity_def,
        "entity_type": entity_type,
        "active_column_keys": active_column_keys,
    })


@router.post("/{view_id}/edit")
def save_view(
    request: Request,
    view_id: str,
    name: str = Form(""),
    sort_field: str = Form(""),
    sort_direction: str = Form("asc"),
    per_page: int = Form(50),
    columns: list[str] = Form(None),
    filters_json: str = Form("[]"),
):
    """Save view settings from form data."""
    user = _user(request)
    customer_id = user.get("customer_id", "")

    try:
        filters = json.loads(filters_json)
    except (json.JSONDecodeError, TypeError):
        filters = []

    with get_connection() as conn:
        view = get_view(conn, view_id)
        if not view or view.get("customer_id") != customer_id:
            return HTMLResponse("View not found", status_code=404)

        update_view(
            conn, view_id,
            name=name,
            sort_field=sort_field,
            sort_direction=sort_direction,
            per_page=per_page,
        )
        if columns:
            update_view_columns(conn, view_id, columns)
        if filters is not None:
            update_view_filters(conn, view_id, filters)

    return RedirectResponse(f"/views/{view_id}", status_code=303)


# -----------------------------------------------------------------------
# Duplicate view
# -----------------------------------------------------------------------

@router.post("/{view_id}/duplicate")
def duplicate_view_route(request: Request, view_id: str):
    user = _user(request)
    customer_id = user.get("customer_id", "")
    user_id = user.get("id", "")

    with get_connection() as conn:
        view = get_view(conn, view_id)
        if not view or view.get("customer_id") != customer_id:
            return HTMLResponse("View not found", status_code=404)

        new_name = f"{view['name']} (copy)"
        new_id = duplicate_view(conn, view_id, new_name, user_id)

    if new_id:
        return RedirectResponse(f"/views/{new_id}", status_code=303)
    return RedirectResponse(f"/views/{view_id}", status_code=303)


# -----------------------------------------------------------------------
# Delete view
# -----------------------------------------------------------------------

@router.post("/{view_id}/delete")
def delete_view_route(request: Request, view_id: str):
    user = _user(request)
    customer_id = user.get("customer_id", "")

    with get_connection() as conn:
        view = get_view(conn, view_id)
        if not view or view.get("customer_id") != customer_id:
            return HTMLResponse("View not found", status_code=404)

        deleted = delete_view(conn, view_id)

    if deleted:
        return RedirectResponse("/views", status_code=303)
    # Can't delete default — redirect back
    return RedirectResponse(f"/views/{view_id}", status_code=303)
