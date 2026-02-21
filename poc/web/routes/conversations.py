"""Conversation routes — list, search, detail, assign/unassign."""

from __future__ import annotations

from fastapi import APIRouter, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from ...database import get_connection
from ...hierarchy import get_addresses, add_address, remove_address

router = APIRouter()


def _parse_sort(url_sort, view):
    """Return (sort_field, sort_direction) — URL param overrides view default."""
    if url_sort:
        desc = url_sort.startswith("-")
        key = url_sort.lstrip("-")
        return (key, "desc" if desc else "asc")
    if view:
        sf = view.get("sort_field")
        if sf:
            return (sf, view.get("sort_direction", "asc"))
    return (None, "asc")


def _query_conversations(
    *,
    status_filter: str = "open",
    topic_id: str = "",
    search: str = "",
    sort: str = "",
    page: int = 1,
    per_page: int = 50,
    customer_id: str = "",
    user_id: str = "",
) -> tuple[list[dict], int, dict | None]:
    from ...views.crud import get_default_view_for_entity
    from ...views.engine import execute_view

    extra_where: list[tuple[str, list]] = []

    if status_filter == "open":
        extra_where.append(("conv.triage_result IS NULL AND conv.dismissed = 0", []))
    elif status_filter == "closed":
        extra_where.append(("conv.dismissed = 1", []))
    elif status_filter == "triaged":
        extra_where.append(("conv.triage_result IS NOT NULL", []))

    if topic_id:
        extra_where.append(("conv.topic_id = ?", [topic_id]))

    with get_connection() as conn:
        view = get_default_view_for_entity(conn, customer_id, user_id, "conversation")
        columns = view["columns"] if view else []
        filters = list(view["filters"]) if view and view.get("filters") else []
        sort_field, sort_direction = _parse_sort(sort, view)

        rows, total = execute_view(
            conn,
            entity_type="conversation",
            columns=columns,
            filters=filters,
            sort_field=sort_field,
            sort_direction=sort_direction,
            search=search,
            page=page,
            per_page=per_page,
            customer_id=customer_id,
            user_id=user_id,
            extra_where=extra_where or None,
        )

    return rows, total, view


def _get_topics_for_filter() -> list[dict]:
    """All topics for the filter dropdown."""
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT t.id, t.name, p.name AS project_name
               FROM topics t
               JOIN projects p ON p.id = t.project_id
               ORDER BY p.name COLLATE NOCASE, t.name COLLATE NOCASE"""
        ).fetchall()
    return [dict(r) for r in rows]


@router.get("", response_class=HTMLResponse)
def conversation_list(
    request: Request,
    status: str = "open",
    topic_id: str = "",
    q: str = "",
    page: int = 1,
    sort: str = "",
):
    from ...views.registry import ENTITY_TYPES

    templates = request.app.state.templates
    user = request.state.user
    cid = request.state.customer_id
    conversations, total, view = _query_conversations(
        status_filter=status, topic_id=topic_id, search=q, sort=sort, page=page,
        customer_id=cid, user_id=user["id"],
    )
    topics = _get_topics_for_filter()
    total_pages = max(1, (total + 49) // 50)

    return templates.TemplateResponse(request, "conversations/list.html", {
        "active_nav": "conversations",
        "rows": conversations,
        "topics": topics,
        "total": total,
        "page": page,
        "total_pages": total_pages,
        "status": status,
        "topic_id": topic_id,
        "q": q,
        "sort": sort,
        "view": view,
        "entity_def": ENTITY_TYPES["conversation"],
    })


@router.get("/search", response_class=HTMLResponse)
def conversation_search(
    request: Request,
    status: str = "open",
    topic_id: str = "",
    q: str = "",
    page: int = 1,
    sort: str = "",
):
    """HTMX partial — returns just the table rows."""
    from ...views.registry import ENTITY_TYPES

    templates = request.app.state.templates
    user = request.state.user
    cid = request.state.customer_id
    conversations, total, view = _query_conversations(
        status_filter=status, topic_id=topic_id, search=q, sort=sort, page=page,
        customer_id=cid, user_id=user["id"],
    )
    total_pages = max(1, (total + 49) // 50)

    return templates.TemplateResponse(request, "conversations/_rows.html", {
        "rows": conversations,
        "total": total,
        "page": page,
        "total_pages": total_pages,
        "status": status,
        "topic_id": topic_id,
        "q": q,
        "sort": sort,
        "view": view,
        "entity_def": ENTITY_TYPES["conversation"],
    })


@router.get("/{conversation_id}", response_class=HTMLResponse)
def conversation_detail(request: Request, conversation_id: str):
    templates = request.app.state.templates
    cid = request.state.customer_id

    with get_connection() as conn:
        conv = conn.execute(
            "SELECT * FROM conversations WHERE id = ?", (conversation_id,)
        ).fetchone()
        if not conv:
            return HTMLResponse("Conversation not found", status_code=404)
        conv = dict(conv)

        # Cross-customer access check
        if conv.get("customer_id") and conv["customer_id"] != cid:
            return HTMLResponse("Conversation not found", status_code=404)

        # Topic info
        topic = None
        if conv.get("topic_id"):
            t = conn.execute(
                """SELECT t.*, p.name AS project_name
                   FROM topics t JOIN projects p ON p.id = t.project_id
                   WHERE t.id = ?""",
                (conv["topic_id"],),
            ).fetchone()
            if t:
                topic = dict(t)

        # Communications (the email thread)
        comms = conn.execute(
            """SELECT comm.* FROM communications comm
               JOIN conversation_communications cc ON cc.communication_id = comm.id
               WHERE cc.conversation_id = ?
               ORDER BY comm.timestamp""",
            (conversation_id,),
        ).fetchall()
        communications = []
        for c in comms:
            cd = dict(c)
            # Load recipients
            recips = conn.execute(
                "SELECT * FROM communication_participants WHERE communication_id = ?",
                (cd["id"],),
            ).fetchall()
            cd["recipients"] = [dict(r) for r in recips]
            communications.append(cd)

        # Participants
        parts = conn.execute(
            """SELECT cp.*, c.name AS contact_name
               FROM conversation_participants cp
               LEFT JOIN contacts c ON c.id = cp.contact_id
               WHERE cp.conversation_id = ?
               ORDER BY cp.communication_count DESC""",
            (conversation_id,),
        ).fetchall()
        participants = [dict(p) for p in parts]

        # Tags
        tags = conn.execute(
            """SELECT t.name FROM tags t
               JOIN conversation_tags ct ON ct.tag_id = t.id
               WHERE ct.conversation_id = ?
               ORDER BY t.name COLLATE NOCASE""",
            (conversation_id,),
        ).fetchall()
        tag_names = [t["name"] for t in tags]

        # All topics for assignment dropdown
        all_topics = conn.execute(
            """SELECT t.id, t.name, p.name AS project_name
               FROM topics t JOIN projects p ON p.id = t.project_id
               ORDER BY p.name COLLATE NOCASE, t.name COLLATE NOCASE"""
        ).fetchall()
        all_topics = [dict(t) for t in all_topics]

    addresses = get_addresses("conversation", conversation_id)

    from ...notes import get_notes_for_entity
    cid = request.state.customer_id
    notes = get_notes_for_entity("conversation", conversation_id, customer_id=cid)

    return templates.TemplateResponse(request, "conversations/detail.html", {
        "active_nav": "conversations",
        "conv": conv,
        "topic": topic,
        "communications": communications,
        "participants": participants,
        "tags": tag_names,
        "all_topics": all_topics,
        "addresses": addresses,
        "notes": notes,
        "entity_type": "conversation",
        "entity_id": conversation_id,
    })


@router.post("/{conversation_id}/assign")
def assign_conversation(request: Request, conversation_id: str, topic_id: str = Form(...)):
    from ...hierarchy import assign_conversation_to_topic
    try:
        assign_conversation_to_topic(conversation_id, topic_id)
    except ValueError:
        pass
    return RedirectResponse(f"/conversations/{conversation_id}", status_code=303)


@router.post("/{conversation_id}/unassign")
def unassign_conversation(request: Request, conversation_id: str):
    from ...hierarchy import unassign_conversation
    try:
        unassign_conversation(conversation_id)
    except ValueError:
        pass
    return RedirectResponse(f"/conversations/{conversation_id}", status_code=303)


# ---------------------------------------------------------------------------
# Addresses
# ---------------------------------------------------------------------------

@router.post("/{conversation_id}/addresses", response_class=HTMLResponse)
def conversation_add_address(
    request: Request,
    conversation_id: str,
    address_type: str = Form("work"),
    street: str = Form(""),
    city: str = Form(""),
    state: str = Form(""),
    postal_code: str = Form(""),
    country: str = Form(""),
):
    templates = request.app.state.templates
    add_address(
        "conversation", conversation_id,
        address_type=address_type, street=street, city=city,
        state=state, postal_code=postal_code, country=country,
    )
    addresses = get_addresses("conversation", conversation_id)

    return templates.TemplateResponse(request, "conversations/_addresses.html", {
        "conv": {"id": conversation_id},
        "addresses": addresses,
    })


@router.delete("/{conversation_id}/addresses/{address_id}", response_class=HTMLResponse)
def conversation_remove_address(
    request: Request, conversation_id: str, address_id: str,
):
    templates = request.app.state.templates
    remove_address(address_id)
    addresses = get_addresses("conversation", conversation_id)

    return templates.TemplateResponse(request, "conversations/_addresses.html", {
        "conv": {"id": conversation_id},
        "addresses": addresses,
    })
