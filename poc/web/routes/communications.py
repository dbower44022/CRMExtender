"""Communications routes — list, search, detail modal, bulk actions."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Form, Query, Request
from fastapi.responses import HTMLResponse

from ...access import visible_communications_query
from ...database import get_connection

router = APIRouter()
log = logging.getLogger(__name__)

# Sort whitelist to prevent SQL injection
_SORT_MAP = {
    "channel": "comm.channel",
    "from": "comm.sender_address",
    "to": "to_addresses",
    "subject": "comm.subject",
    "date": "comm.timestamp",
}
_DEFAULT_SORT = "date"
_DEFAULT_DIR = "DESC"


def _ensure_schema():
    """Ensure is_archived column exists (for existing DBs without migration)."""
    with get_connection() as conn:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(communications)")}
        if "is_archived" not in cols:
            conn.execute(
                "ALTER TABLE communications ADD COLUMN is_archived INTEGER DEFAULT 0"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_comm_archived "
                "ON communications(is_archived)"
            )


_schema_checked = False


def _check_schema_once():
    global _schema_checked
    if not _schema_checked:
        try:
            _ensure_schema()
        except Exception:
            log.debug("Schema check skipped", exc_info=True)
        _schema_checked = True


def _parse_sort(sort_param: str) -> tuple[str, str]:
    """Parse sort parameter (e.g. '-date') into (column, direction)."""
    if sort_param.startswith("-"):
        key = sort_param[1:]
        direction = "DESC"
    else:
        key = sort_param
        direction = "ASC"
    column = _SORT_MAP.get(key, _SORT_MAP[_DEFAULT_SORT])
    return column, direction


def _list_communications(
    *,
    search: str = "",
    channel: str = "",
    direction: str = "",
    show_archived: bool = False,
    sort: str = "-date",
    page: int = 1,
    per_page: int = 50,
    customer_id: str = "",
    user_id: str = "",
) -> tuple[list[dict], int]:
    """Query communications with filters. Returns (rows, total_count)."""
    _check_schema_once()

    clauses: list[str] = []
    params: list = []

    # Visibility scoping
    if customer_id and user_id:
        vis_where, vis_params = visible_communications_query(customer_id, user_id)
        clauses.append(vis_where)
        params.extend(vis_params)

    # Only current revisions
    clauses.append("comm.is_current = 1")

    # Archive filter
    if not show_archived:
        clauses.append("comm.is_archived = 0")

    # Search
    if search:
        clauses.append(
            "(comm.subject LIKE ? OR comm.sender_address LIKE ? "
            "OR comm.sender_name LIKE ?)"
        )
        like = f"%{search}%"
        params.extend([like, like, like])

    # Channel filter
    if channel:
        clauses.append("comm.channel = ?")
        params.append(channel)

    # Direction filter
    if direction:
        clauses.append("comm.direction = ?")
        params.append(direction)

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    sort_col, sort_dir = _parse_sort(sort)

    with get_connection() as conn:
        total = conn.execute(
            f"SELECT COUNT(*) AS cnt FROM communications comm {where}",
            params,
        ).fetchone()["cnt"]

        offset = (page - 1) * per_page
        rows = conn.execute(
            f"""SELECT comm.id, comm.channel, comm.sender_address,
                       comm.sender_name, comm.subject, comm.timestamp,
                       comm.direction, comm.snippet,
                       (SELECT GROUP_CONCAT(cp.address, ', ')
                        FROM communication_participants cp
                        WHERE cp.communication_id = comm.id AND cp.role = 'to'
                       ) AS to_addresses,
                       (SELECT cc.conversation_id
                        FROM conversation_communications cc
                        WHERE cc.communication_id = comm.id
                        LIMIT 1
                       ) AS conversation_id,
                       (SELECT conv.title
                        FROM conversations conv
                        JOIN conversation_communications cc ON cc.conversation_id = conv.id
                        WHERE cc.communication_id = comm.id
                        LIMIT 1
                       ) AS conversation_title
                FROM communications comm
                {where}
                ORDER BY {sort_col} {sort_dir}
                LIMIT ? OFFSET ?""",
            params + [per_page, offset],
        ).fetchall()

    return [dict(r) for r in rows], total


@router.get("", response_class=HTMLResponse)
def communication_list(
    request: Request,
    q: str = "",
    channel: str = "",
    direction: str = "",
    sort: str = "-date",
    page: int = 1,
):
    templates = request.app.state.templates
    user = request.state.user
    cid = request.state.customer_id

    communications, total = _list_communications(
        search=q, channel=channel, direction=direction,
        sort=sort, page=page,
        customer_id=cid, user_id=user["id"],
    )
    total_pages = max(1, (total + 49) // 50)

    return templates.TemplateResponse(request, "communications/list.html", {
        "active_nav": "communications",
        "communications": communications,
        "total": total,
        "page": page,
        "total_pages": total_pages,
        "q": q,
        "channel": channel,
        "direction": direction,
        "sort": sort,
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
    templates = request.app.state.templates
    user = request.state.user
    cid = request.state.customer_id

    communications, total = _list_communications(
        search=q, channel=channel, direction=direction,
        sort=sort, page=page,
        customer_id=cid, user_id=user["id"],
    )
    total_pages = max(1, (total + 49) // 50)

    return templates.TemplateResponse(request, "communications/_rows.html", {
        "communications": communications,
        "total": total,
        "page": page,
        "total_pages": total_pages,
        "q": q,
        "channel": channel,
        "direction": direction,
        "sort": sort,
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
    communications, total = _list_communications(
        search=q, channel=channel, direction=direction,
        sort=sort, page=page,
        customer_id=cid, user_id=user["id"],
    )
    total_pages = max(1, (total + 49) // 50)

    return templates.TemplateResponse(request, "communications/_rows.html", {
        "communications": communications,
        "total": total,
        "page": page,
        "total_pages": total_pages,
        "q": q,
        "channel": channel,
        "direction": direction,
        "sort": sort,
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
    communications, total = _list_communications(
        search=q, channel=channel, direction=direction,
        sort=sort, page=page,
        customer_id=cid, user_id=user["id"],
    )
    total_pages = max(1, (total + 49) // 50)

    return templates.TemplateResponse(request, "communications/_rows.html", {
        "communications": communications,
        "total": total,
        "page": page,
        "total_pages": total_pages,
        "q": q,
        "channel": channel,
        "direction": direction,
        "sort": sort,
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
    communications, total = _list_communications(
        search=q, channel=channel, direction=direction,
        sort=sort, page=page,
        customer_id=cid, user_id=user["id"],
    )
    total_pages = max(1, (total + 49) // 50)

    return templates.TemplateResponse(request, "communications/_rows.html", {
        "communications": communications,
        "total": total,
        "page": page,
        "total_pages": total_pages,
        "q": q,
        "channel": channel,
        "direction": direction,
        "sort": sort,
    })
