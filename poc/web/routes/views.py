"""Views routes — dashboard, grid rendering, CRUD, search."""

from __future__ import annotations

import json
import re

from fastapi import APIRouter, Form, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

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


_OPERATOR_LABELS = {
    "equals": "Equals",
    "not_equals": "Does Not Equal",
    "contains": "Contains",
    "not_contains": "Does Not Contain",
    "starts_with": "Starts With",
    "is_empty": "Is Empty",
    "is_not_empty": "Is Not Empty",
    "gt": "Greater Than",
    "lt": "Less Than",
    "gte": "Greater Than or Equal",
    "lte": "Less Than or Equal",
    "is_before": "Is Before",
    "is_after": "Is After",
}


def _extract_link_deps(entity_def):
    """Map visible fields to hidden fields required by their link templates."""
    deps = {}
    hidden_keys = {k for k, f in entity_def.fields.items() if f.type == "hidden"}
    for fk, fdef in entity_def.fields.items():
        if fdef.link:
            refs = set(re.findall(r'\{(\w+)\}', fdef.link))
            needed = [r for r in refs if r in hidden_keys and r != "id"]
            if needed:
                deps[fk] = needed
    return deps


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
# Inline cell edit
# -----------------------------------------------------------------------

@router.post("/cell-edit")
async def cell_edit(request: Request):
    """Update a single field on a contact or company via inline edit."""
    from ...hierarchy import update_company, update_contact

    _UPDATE_DISPATCHERS = {
        "contact": ("contacts", update_contact),
        "company": ("companies", update_company),
    }

    user = _user(request)
    customer_id = user.get("customer_id", "")

    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"ok": False, "error": "Invalid JSON"}, status_code=400)

    entity_type = body.get("entity_type", "")
    entity_id = body.get("entity_id", "")
    field_key = body.get("field_key", "")
    value = body.get("value", "")

    if entity_type not in _UPDATE_DISPATCHERS:
        return JSONResponse(
            {"ok": False, "error": f"Entity type '{entity_type}' is not editable"},
            status_code=400,
        )

    entity_def = ENTITY_TYPES.get(entity_type)
    if not entity_def:
        return JSONResponse({"ok": False, "error": "Unknown entity type"}, status_code=400)

    # Find the editable field by db_column
    fdef = None
    for fk, fd in entity_def.fields.items():
        if fd.db_column == field_key and fd.editable:
            fdef = fd
            break

    if not fdef:
        return JSONResponse(
            {"ok": False, "error": f"Field '{field_key}' is not editable"},
            status_code=400,
        )

    # Validate select options
    if fdef.select_options and value and value not in fdef.select_options:
        return JSONResponse(
            {"ok": False, "error": f"Invalid option '{value}'. Must be one of: {', '.join(fdef.select_options)}"},
            status_code=400,
        )

    # Verify entity belongs to this customer
    table_name, update_fn = _UPDATE_DISPATCHERS[entity_type]
    with get_connection() as conn:
        row = conn.execute(
            f"SELECT id FROM {table_name} WHERE id = ? AND customer_id = ?",
            (entity_id, customer_id),
        ).fetchone()

    if not row:
        return JSONResponse({"ok": False, "error": "Entity not found"}, status_code=404)

    # Perform the update
    updated = update_fn(entity_id, **{field_key: value})
    if not updated:
        return JSONResponse({"ok": False, "error": "Update failed"}, status_code=500)

    return JSONResponse({"ok": True, "value": updated.get(field_key, value)})


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
def edit_view_form(request: Request, view_id: str, saved: str = ""):
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

    # Build ordered selected columns list
    selected_columns = [
        {
            "key": c["field_key"],
            "label": entity_def.fields[c["field_key"]].label,
            "label_override": c.get("label_override") or "",
            "width_px": c.get("width_px") or "",
        }
        for c in view.get("columns", [])
        if c["field_key"] in entity_def.fields and entity_def.fields[c["field_key"]].type != "hidden"
    ]

    # Build available (non-selected, non-hidden) columns
    selected_keys = {sc["key"] for sc in selected_columns}
    available_columns = [
        {"key": fk, "label": fdef.label}
        for fk, fdef in entity_def.fields.items()
        if fdef.type != "hidden" and fk not in selected_keys
    ]

    field_deps = _extract_link_deps(entity_def)

    return templates.TemplateResponse(request, "views/edit.html", {
        "active_nav": "views",
        "view": view,
        "entity_def": entity_def,
        "entity_type": entity_type,
        "active_column_keys": active_column_keys,
        "selected_columns": selected_columns,
        "available_columns": available_columns,
        "field_deps": field_deps,
        "field_deps_json": json.dumps(field_deps),
        "saved": saved == "1",
        "operator_labels": _OPERATOR_LABELS,
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
    columns_json: str = Form(""),
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

        entity_type = view.get("entity_type", "")
        entity_def = ENTITY_TYPES.get(entity_type)

        update_view(
            conn, view_id,
            name=name,
            sort_field=sort_field,
            sort_direction=sort_direction,
            per_page=per_page,
        )

        # Prefer columns_json (ordered list) over legacy columns checkboxes
        col_list = None
        if columns_json:
            try:
                col_list = json.loads(columns_json)
            except (json.JSONDecodeError, TypeError):
                col_list = None

        if col_list is None and columns:
            col_list = columns

        if col_list and entity_def:
            # Normalise: could be list of strings or list of dicts
            is_object_format = col_list and isinstance(col_list[0], dict)

            def _col_key(item):
                return item["key"] if isinstance(item, dict) else item

            # Validate keys exist in entity_def
            valid_keys = set(entity_def.fields.keys())
            col_list = [c for c in col_list if _col_key(c) in valid_keys]

            # Auto-append hidden dependency fields
            field_deps = _extract_link_deps(entity_def)
            col_set = {_col_key(c) for c in col_list}
            for item in list(col_list):
                for dep_key in field_deps.get(_col_key(item), []):
                    if dep_key not in col_set:
                        col_list.append({"key": dep_key} if is_object_format else dep_key)
                        col_set.add(dep_key)

            update_view_columns(conn, view_id, col_list)

        if filters is not None:
            update_view_filters(conn, view_id, filters)

    return RedirectResponse(f"/views/{view_id}/edit?saved=1", status_code=303)


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
