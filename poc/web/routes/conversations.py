"""Conversation routes — list, search, detail, assign/unassign."""

from __future__ import annotations

from fastapi import APIRouter, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from ...database import get_connection

router = APIRouter()


def _list_conversations(
    *,
    status_filter: str = "open",
    topic_id: str = "",
    search: str = "",
    page: int = 1,
    per_page: int = 50,
) -> tuple[list[dict], int]:
    """Query conversations with filters. Returns (rows, total_count)."""
    clauses = []
    params: list = []

    if status_filter == "open":
        clauses.append("c.triage_result IS NULL AND c.dismissed = 0")
    elif status_filter == "closed":
        clauses.append("c.dismissed = 1")
    elif status_filter == "triaged":
        clauses.append("c.triage_result IS NOT NULL")

    if topic_id:
        clauses.append("c.topic_id = ?")
        params.append(topic_id)

    if search:
        clauses.append("c.title LIKE ?")
        params.append(f"%{search}%")

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""

    with get_connection() as conn:
        total = conn.execute(
            f"SELECT COUNT(*) AS c FROM conversations c {where}", params
        ).fetchone()["c"]

        offset = (page - 1) * per_page
        rows = conn.execute(
            f"""SELECT c.*, t.name AS topic_name
                FROM conversations c
                LEFT JOIN topics t ON t.id = c.topic_id
                {where}
                ORDER BY c.last_activity_at DESC
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
    conversations, total = _list_conversations(
        status_filter=status, topic_id=topic_id, search=q, page=page,
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
    conversations, total = _list_conversations(
        status_filter=status, topic_id=topic_id, search=q, page=page,
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

    with get_connection() as conn:
        conv = conn.execute(
            "SELECT * FROM conversations WHERE id = ?", (conversation_id,)
        ).fetchone()
        if not conv:
            return HTMLResponse("Conversation not found", status_code=404)
        conv = dict(conv)

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
