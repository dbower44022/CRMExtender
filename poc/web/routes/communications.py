"""Communications routes — list, search, detail modal, bulk actions."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Form, Query, Request
from fastapi.responses import HTMLResponse

from ...database import get_connection

router = APIRouter()

_COMM_SORT_ALIASES = {"date": "timestamp", "from": "sender"}


def _parse_sort(url_sort, view):
    """Return (sort_field, sort_direction) — URL param overrides view default."""
    if url_sort:
        desc = url_sort.startswith("-")
        key = url_sort.lstrip("-")
        key = _COMM_SORT_ALIASES.get(key, key)
        return (key, "desc" if desc else "asc")
    if view:
        sf = view.get("sort_field")
        if sf:
            return (sf, view.get("sort_direction", "asc"))
    return (None, "asc")


def _query_communications(
    *,
    search: str = "",
    channel: str = "",
    direction: str = "",
    sort: str = "-date",
    page: int = 1,
    per_page: int = 50,
    customer_id: str = "",
    user_id: str = "",
) -> tuple[list[dict], int, dict | None]:
    from ...views.crud import get_default_view_for_entity
    from ...views.engine import execute_view

    with get_connection() as conn:
        view = get_default_view_for_entity(conn, customer_id, user_id, "communication")
        columns = view["columns"] if view else []
        filters = list(view["filters"]) if view and view.get("filters") else []
        sort_field, sort_direction = _parse_sort(sort, view)

        # Route-level filters (channel/direction dropdowns)
        if channel:
            filters.append({"field_key": "channel", "operator": "equals", "value": channel})
        if direction:
            filters.append({"field_key": "direction", "operator": "equals", "value": direction})

        rows, total = execute_view(
            conn,
            entity_type="communication",
            columns=columns,
            filters=filters,
            sort_field=sort_field,
            sort_direction=sort_direction,
            search=search,
            page=page,
            per_page=per_page,
            customer_id=customer_id,
            user_id=user_id,
        )

    return rows, total, view


@router.get("", response_class=HTMLResponse)
def communication_list(
    request: Request,
    q: str = "",
    channel: str = "",
    direction: str = "",
    sort: str = "-date",
    page: int = 1,
):
    from ...views.registry import ENTITY_TYPES

    templates = request.app.state.templates
    user = request.state.user
    cid = request.state.customer_id

    communications, total, view = _query_communications(
        search=q, channel=channel, direction=direction,
        sort=sort, page=page,
        customer_id=cid, user_id=user["id"],
    )
    total_pages = max(1, (total + 49) // 50)

    return templates.TemplateResponse(request, "communications/list.html", {
        "active_nav": "communications",
        "rows": communications,
        "total": total,
        "page": page,
        "total_pages": total_pages,
        "q": q,
        "channel": channel,
        "direction": direction,
        "sort": sort,
        "view": view,
        "entity_def": ENTITY_TYPES["communication"],
    })


@router.get("/search", response_class=HTMLResponse)
def communication_search(
    request: Request,
    q: str = "",
    channel: str = "",
    direction: str = "",
    sort: str = "-date",
    page: int = 1,
):
    """HTMX partial — returns just the table rows."""
    from ...views.registry import ENTITY_TYPES

    templates = request.app.state.templates
    user = request.state.user
    cid = request.state.customer_id

    communications, total, view = _query_communications(
        search=q, channel=channel, direction=direction,
        sort=sort, page=page,
        customer_id=cid, user_id=user["id"],
    )
    total_pages = max(1, (total + 49) // 50)

    return templates.TemplateResponse(request, "communications/_rows.html", {
        "rows": communications,
        "total": total,
        "page": page,
        "total_pages": total_pages,
        "q": q,
        "channel": channel,
        "direction": direction,
        "sort": sort,
        "view": view,
        "entity_def": ENTITY_TYPES["communication"],
    })


@router.get("/{comm_id}/detail", response_class=HTMLResponse)
def communication_detail(request: Request, comm_id: str):
    """HTMX modal content — full communication details."""
    templates = request.app.state.templates
    cid = request.state.customer_id

    with get_connection() as conn:
        comm = conn.execute(
            "SELECT * FROM communications WHERE id = ?", (comm_id,)
        ).fetchone()
        if not comm:
            return HTMLResponse("Communication not found", status_code=404)
        comm = dict(comm)

        # Cross-tenant check via provider_account
        if cid:
            acct = conn.execute(
                "SELECT customer_id FROM provider_accounts WHERE id = ?",
                (comm.get("account_id"),),
            ).fetchone()
            if acct and acct["customer_id"] != cid:
                return HTMLResponse("Communication not found", status_code=404)

        # Recipients
        recips = conn.execute(
            "SELECT * FROM communication_participants WHERE communication_id = ?",
            (comm_id,),
        ).fetchall()
        comm["recipients"] = [dict(r) for r in recips]

        # Linked conversation
        conv_link = conn.execute(
            """SELECT conv.id, conv.title
               FROM conversations conv
               JOIN conversation_communications cc ON cc.conversation_id = conv.id
               WHERE cc.communication_id = ?
               LIMIT 1""",
            (comm_id,),
        ).fetchone()
        comm["conversation"] = dict(conv_link) if conv_link else None

    return templates.TemplateResponse(
        request, "communications/_detail_modal.html", {"comm": comm}
    )


@router.post("/archive", response_class=HTMLResponse)
def bulk_archive(
    request: Request,
    ids: list[str] = Form(default=[]),
    q: str = Form(default=""),
    channel: str = Form(default=""),
    direction: str = Form(default=""),
    sort: str = Form(default="-date"),
    page: int = Form(default=1),
):
    """Archive selected communications."""
    user = request.state.user
    cid = request.state.customer_id
    templates = request.app.state.templates
    now = datetime.now(timezone.utc).isoformat()

    with get_connection() as conn:
        for comm_id in ids:
            # Mark archived
            conn.execute(
                "UPDATE communications SET is_archived = 1, updated_at = ? "
                "WHERE id = ?",
                (now, comm_id),
            )
            # Find and unlink conversations
            conv_rows = conn.execute(
                "SELECT conversation_id FROM conversation_communications "
                "WHERE communication_id = ?",
                (comm_id,),
            ).fetchall()
            conn.execute(
                "DELETE FROM conversation_communications WHERE communication_id = ?",
                (comm_id,),
            )
            # Dismiss empty conversations
            for cr in conv_rows:
                conv_id = cr["conversation_id"]
                remaining = conn.execute(
                    "SELECT COUNT(*) AS cnt FROM conversation_communications "
                    "WHERE conversation_id = ?",
                    (conv_id,),
                ).fetchone()["cnt"]
                if remaining == 0:
                    conn.execute(
                        "UPDATE conversations SET dismissed = 1, "
                        "dismissed_reason = 'archived', dismissed_at = ? "
                        "WHERE id = ?",
                        (now, conv_id),
                    )

    # Return updated rows
    from ...views.registry import ENTITY_TYPES

    communications, total, view = _query_communications(
        search=q, channel=channel, direction=direction,
        sort=sort, page=page,
        customer_id=cid, user_id=user["id"],
    )
    total_pages = max(1, (total + 49) // 50)

    return templates.TemplateResponse(request, "communications/_rows.html", {
        "rows": communications,
        "total": total,
        "page": page,
        "total_pages": total_pages,
        "q": q,
        "channel": channel,
        "direction": direction,
        "sort": sort,
        "view": view,
        "entity_def": ENTITY_TYPES["communication"],
    })


@router.get("/conversations/search", response_class=HTMLResponse)
def conversation_search_for_assign(
    request: Request,
    q: str = "",
):
    """HTMX partial — search conversations for the assign modal."""
    templates = request.app.state.templates
    cid = request.state.customer_id

    with get_connection() as conn:
        if q:
            rows = conn.execute(
                """SELECT id, title, last_activity_at
                   FROM conversations
                   WHERE customer_id = ? AND title LIKE ? AND dismissed = 0
                   ORDER BY last_activity_at DESC
                   LIMIT 20""",
                (cid, f"%{q}%"),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT id, title, last_activity_at
                   FROM conversations
                   WHERE customer_id = ? AND dismissed = 0
                   ORDER BY last_activity_at DESC
                   LIMIT 20""",
                (cid,),
            ).fetchall()

    conversations = [dict(r) for r in rows]
    return templates.TemplateResponse(
        request, "communications/_assign_modal.html",
        {"conversations": conversations},
    )


@router.post("/assign", response_class=HTMLResponse)
def bulk_assign(
    request: Request,
    ids: list[str] = Form(default=[]),
    conversation_id: str = Form(...),
    q: str = Form(default=""),
    channel: str = Form(default=""),
    direction: str = Form(default=""),
    sort: str = Form(default="-date"),
    page: int = Form(default=1),
):
    """Assign selected communications to a conversation."""
    user = request.state.user
    cid = request.state.customer_id
    templates = request.app.state.templates
    now = datetime.now(timezone.utc).isoformat()

    with get_connection() as conn:
        for comm_id in ids:
            conn.execute(
                "INSERT OR IGNORE INTO conversation_communications "
                "(conversation_id, communication_id, assignment_source, "
                "confidence, created_at) VALUES (?, ?, 'manual', 1.0, ?)",
                (conversation_id, comm_id, now),
            )

    # Return updated rows
    from ...views.registry import ENTITY_TYPES

    communications, total, view = _query_communications(
        search=q, channel=channel, direction=direction,
        sort=sort, page=page,
        customer_id=cid, user_id=user["id"],
    )
    total_pages = max(1, (total + 49) // 50)

    return templates.TemplateResponse(request, "communications/_rows.html", {
        "rows": communications,
        "total": total,
        "page": page,
        "total_pages": total_pages,
        "q": q,
        "channel": channel,
        "direction": direction,
        "sort": sort,
        "view": view,
        "entity_def": ENTITY_TYPES["communication"],
    })


@router.post("/delete-conversation", response_class=HTMLResponse)
def delete_conversation(
    request: Request,
    ids: list[str] = Form(default=[]),
    delete_comms: bool = Form(default=False),
    q: str = Form(default=""),
    channel: str = Form(default=""),
    direction: str = Form(default=""),
    sort: str = Form(default="-date"),
    page: int = Form(default=1),
):
    """Delete conversations linked to selected communications."""
    user = request.state.user
    cid = request.state.customer_id
    templates = request.app.state.templates

    with get_connection() as conn:
        # Collect all conversation IDs linked to these communications
        conv_ids = set()
        for comm_id in ids:
            rows = conn.execute(
                "SELECT conversation_id FROM conversation_communications "
                "WHERE communication_id = ?",
                (comm_id,),
            ).fetchall()
            for r in rows:
                conv_ids.add(r["conversation_id"])

        # Delete conversations (CASCADE will clean up join tables)
        for conv_id in conv_ids:
            conn.execute("DELETE FROM conversations WHERE id = ?", (conv_id,))

        # Optionally delete the communications too
        if delete_comms:
            for comm_id in ids:
                conn.execute(
                    "DELETE FROM communications WHERE id = ?", (comm_id,)
                )

    # Return updated rows
    from ...views.registry import ENTITY_TYPES

    communications, total, view = _query_communications(
        search=q, channel=channel, direction=direction,
        sort=sort, page=page,
        customer_id=cid, user_id=user["id"],
    )
    total_pages = max(1, (total + 49) // 50)

    return templates.TemplateResponse(request, "communications/_rows.html", {
        "rows": communications,
        "total": total,
        "page": page,
        "total_pages": total_pages,
        "q": q,
        "channel": channel,
        "direction": direction,
        "sort": sort,
        "view": view,
        "entity_def": ENTITY_TYPES["communication"],
    })
