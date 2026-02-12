"""Conversation routes — list, search, detail, assign/unassign."""

from __future__ import annotations

from fastapi import APIRouter, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from ...access import visible_conversations_query
from ...database import get_connection

router = APIRouter()


def _list_conversations(
    *,
    status_filter: str = "open",
    topic_id: str = "",
    search: str = "",
    page: int = 1,
    per_page: int = 50,
    customer_id: str = "",
    user_id: str = "",
) -> tuple[list[dict], int]:
    """Query conversations with filters. Returns (rows, total_count)."""
    clauses: list[str] = []
    params: list = []

    # Visibility scoping
    if customer_id and user_id:
        vis_where, vis_params = visible_conversations_query(customer_id, user_id)
        clauses.append(vis_where)
        params.extend(vis_params)

    if status_filter == "open":
        clauses.append("conv.triage_result IS NULL AND conv.dismissed = 0")
    elif status_filter == "closed":
        clauses.append("conv.dismissed = 1")
    elif status_filter == "triaged":
        clauses.append("conv.triage_result IS NOT NULL")

    if topic_id:
        clauses.append("conv.topic_id = ?")
        params.append(topic_id)

    if search:
        clauses.append("conv.title LIKE ?")
        params.append(f"%{search}%")

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""

    with get_connection() as conn:
        total = conn.execute(
            f"SELECT COUNT(*) AS cnt FROM conversations conv {where}", params
        ).fetchone()["cnt"]

        offset = (page - 1) * per_page
        rows = conn.execute(
            f"""SELECT conv.*, t.name AS topic_name,
                       (SELECT COALESCE(pa.display_name, pa.email_address, pa.phone_number)
                        FROM conversation_communications cc2
                        JOIN communications comm2 ON comm2.id = cc2.communication_id
                        JOIN provider_accounts pa ON pa.id = comm2.account_id
                        WHERE cc2.conversation_id = conv.id
                        LIMIT 1
                       ) AS account_name
                FROM conversations conv
                LEFT JOIN topics t ON t.id = conv.topic_id
                {where}
                ORDER BY conv.last_activity_at DESC
                LIMIT ? OFFSET ?""",
            params + [per_page, offset],
        ).fetchall()

    return [dict(r) for r in rows], total


def _get_topics_for_filter() -> list[dict]:
    """All topics for the filter dropdown."""
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT t.id, t.name, p.name AS project_name
               FROM topics t
               JOIN projects p ON p.id = t.project_id
               ORDER BY p.name, t.name"""
        ).fetchall()
    return [dict(r) for r in rows]


@router.get("", response_class=HTMLResponse)
def conversation_list(
    request: Request,
    status: str = "open",
    topic_id: str = "",
    q: str = "",
    page: int = 1,
):
    templates = request.app.state.templates
    user = request.state.user
    cid = request.state.customer_id
    conversations, total = _list_conversations(
        status_filter=status, topic_id=topic_id, search=q, page=page,
        customer_id=cid, user_id=user["id"],
    )
    topics = _get_topics_for_filter()
    total_pages = max(1, (total + 49) // 50)

    return templates.TemplateResponse(request, "conversations/list.html", {
        "active_nav": "conversations",
        "conversations": conversations,
        "topics": topics,
        "total": total,
        "page": page,
        "total_pages": total_pages,
        "status": status,
        "topic_id": topic_id,
        "q": q,
    })


@router.get("/search", response_class=HTMLResponse)
def conversation_search(
    request: Request,
    status: str = "open",
    topic_id: str = "",
    q: str = "",
    page: int = 1,
):
    """HTMX partial — returns just the table rows."""
    templates = request.app.state.templates
    user = request.state.user
    cid = request.state.customer_id
    conversations, total = _list_conversations(
        status_filter=status, topic_id=topic_id, search=q, page=page,
        customer_id=cid, user_id=user["id"],
    )
    total_pages = max(1, (total + 49) // 50)

    return templates.TemplateResponse(request, "conversations/_rows.html", {
        "conversations": conversations,
        "total": total,
        "page": page,
        "total_pages": total_pages,
        "status": status,
        "topic_id": topic_id,
        "q": q,
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
            """SELECT cp.*, c.name AS contact_name, ci.value AS contact_email
               FROM conversation_participants cp
               LEFT JOIN contacts c ON c.id = cp.contact_id
               LEFT JOIN contact_identifiers ci ON ci.contact_id = c.id AND ci.type = 'email'
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
               ORDER BY t.name""",
            (conversation_id,),
        ).fetchall()
        tag_names = [t["name"] for t in tags]

        # All topics for assignment dropdown
        all_topics = conn.execute(
            """SELECT t.id, t.name, p.name AS project_name
               FROM topics t JOIN projects p ON p.id = t.project_id
               ORDER BY p.name, t.name"""
        ).fetchall()
        all_topics = [dict(t) for t in all_topics]

    return templates.TemplateResponse(request, "conversations/detail.html", {
        "active_nav": "conversations",
        "conv": conv,
        "topic": topic,
        "communications": communications,
        "participants": participants,
        "tags": tag_names,
        "all_topics": all_topics,
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
