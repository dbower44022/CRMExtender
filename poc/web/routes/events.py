"""Event routes — list, search, create, detail, delete, sync."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from ...database import get_connection

log = logging.getLogger(__name__)
router = APIRouter()


def _list_events(*, search: str = "", event_type: str = "",
                 page: int = 1, per_page: int = 50,
                 customer_id: str = ""):
    clauses = []
    params: list = []

    # Scope events: synced events via provider_accounts.customer_id,
    # manual events (account_id IS NULL) are visible to all.
    if customer_id:
        clauses.append(
            "(e.account_id IS NULL OR e.account_id IN "
            "(SELECT id FROM provider_accounts WHERE customer_id = ?))"
        )
        params.append(customer_id)

    if search:
        clauses.append("(e.title LIKE ? OR e.location LIKE ?)")
        params.extend([f"%{search}%", f"%{search}%"])
    if event_type:
        clauses.append("e.event_type = ?")
        params.append(event_type)

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""

    with get_connection() as conn:
        total = conn.execute(
            f"SELECT COUNT(*) AS cnt FROM events e {where}",
            params,
        ).fetchone()["cnt"]

        offset = (page - 1) * per_page
        rows = conn.execute(
            f"""SELECT e.*,
                       COALESCE(pa.display_name, pa.email_address) AS account_name
                FROM events e
                LEFT JOIN provider_accounts pa ON pa.id = e.account_id
                {where}
                ORDER BY COALESCE(e.start_datetime, e.start_date) DESC
                LIMIT ? OFFSET ?""",
            params + [per_page, offset],
        ).fetchall()

    return [dict(r) for r in rows], total


@router.get("", response_class=HTMLResponse)
def event_list(request: Request, q: str = "", event_type: str = "",
               page: int = 1):
    templates = request.app.state.templates
    cid = request.state.customer_id
    events, total = _list_events(
        search=q, event_type=event_type, page=page, customer_id=cid,
    )
    total_pages = max(1, (total + 49) // 50)

    return templates.TemplateResponse(request, "events/list.html", {
        "active_nav": "events",
        "events": events,
        "total": total,
        "page": page,
        "total_pages": total_pages,
        "q": q,
        "event_type": event_type,
    })


@router.get("/search", response_class=HTMLResponse)
def event_search(request: Request, q: str = "", event_type: str = "",
                 page: int = 1):
    templates = request.app.state.templates
    cid = request.state.customer_id
    events, total = _list_events(
        search=q, event_type=event_type, page=page, customer_id=cid,
    )
    total_pages = max(1, (total + 49) // 50)

    return templates.TemplateResponse(request, "events/_rows.html", {
        "events": events,
        "total": total,
        "page": page,
        "total_pages": total_pages,
        "q": q,
        "event_type": event_type,
    })


@router.post("/sync", response_class=HTMLResponse)
def sync_events(request: Request):
    """Sync calendar events from the user's Google accounts."""
    from ...auth import get_credentials_for_account
    from ...calendar_client import CalendarScopeError
    from ...calendar_sync import sync_all_calendars
    from ...rate_limiter import RateLimiter
    from ... import config

    user = request.state.user
    uid = user["id"]
    cid = request.state.customer_id

    # Get user's Google provider accounts
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT pa.* FROM provider_accounts pa
               JOIN user_provider_accounts upa ON upa.account_id = pa.id
               WHERE upa.user_id = ?
               ORDER BY pa.created_at""",
            (uid,),
        ).fetchall()
        accounts = [dict(a) for a in rows]

    if not accounts:
        # Fallback to customer's accounts
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM provider_accounts WHERE customer_id = ? ORDER BY created_at",
                (cid,),
            ).fetchall()
            accounts = [dict(a) for a in rows]

    if not accounts:
        return HTMLResponse("<strong>No accounts registered.</strong>")

    rate_limiter = RateLimiter(rate=config.GMAIL_RATE_LIMIT)
    total_created = 0
    total_updated = 0
    total_matched = 0
    errors: list[str] = []

    for account in accounts:
        account_id = account["id"]
        email_addr = account["email_address"]

        token_path = Path(account["auth_token_path"])
        try:
            creds = get_credentials_for_account(token_path)
        except Exception as exc:
            log.warning("Auth failed for %s: %s", email_addr, exc)
            errors.append(f"{email_addr}: auth failed ({exc})")
            continue

        try:
            result = sync_all_calendars(
                account_id, creds,
                rate_limiter=rate_limiter,
                customer_id=cid,
                user_id=uid,
            )
        except CalendarScopeError as exc:
            errors.append(f"{email_addr}: {exc}")
            continue
        except Exception as exc:
            log.warning("Calendar sync failed for %s: %s", email_addr, exc)
            errors.append(f"{email_addr}: sync failed ({exc})")
            continue

        if result.get("error"):
            errors.append(f"{email_addr}: {result['error']}")
            continue

        total_created += result.get("events_created", 0)
        total_updated += result.get("events_updated", 0)
        total_matched += result.get("attendees_matched", 0)

    parts = [
        f"{total_created} events created,",
        f"{total_updated} updated,",
        f"{total_matched} attendees matched.",
    ]
    summary = " ".join(parts)

    if errors:
        error_html = "<br>".join(f"Error: {e}" for e in errors)
        html = f"<strong>{summary}</strong><br>{error_html}"
    else:
        html = f"<strong>{summary}</strong>"

    return HTMLResponse(html, headers={"HX-Trigger": "refreshEvents"})


@router.post("", response_class=HTMLResponse)
def event_create(
    request: Request,
    title: str = Form(...),
    event_type: str = Form("meeting"),
    start_date: str = Form(""),
    start_datetime: str = Form(""),
    end_date: str = Form(""),
    end_datetime: str = Form(""),
    is_all_day: str = Form(""),
    location: str = Form(""),
    description: str = Form(""),
    recurrence_type: str = Form("none"),
    status: str = Form("confirmed"),
):
    user = request.state.user
    now = datetime.now(timezone.utc).isoformat()
    event_id = str(uuid.uuid4())
    all_day = 1 if is_all_day else 0

    with get_connection() as conn:
        conn.execute(
            """INSERT INTO events
               (id, title, description, event_type,
                start_date, start_datetime, end_date, end_datetime,
                is_all_day, location, recurrence_type, status,
                source, created_by, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'manual', ?, ?, ?)""",
            (
                event_id, title, description or None, event_type,
                start_date or None, start_datetime or None,
                end_date or None, end_datetime or None,
                all_day, location or None, recurrence_type, status,
                user["id"], now, now,
            ),
        )

    if request.headers.get("HX-Request") == "true":
        return HTMLResponse("", headers={"HX-Redirect": f"/events/{event_id}"})
    return RedirectResponse(f"/events/{event_id}", status_code=303)


@router.delete("/{event_id}", response_class=HTMLResponse)
def event_delete(request: Request, event_id: str):
    with get_connection() as conn:
        conn.execute("DELETE FROM event_participants WHERE event_id = ?",
                     (event_id,))
        conn.execute("DELETE FROM event_conversations WHERE event_id = ?",
                     (event_id,))
        conn.execute("DELETE FROM events WHERE id = ?", (event_id,))
    return HTMLResponse("")


@router.get("/{event_id}", response_class=HTMLResponse)
def event_detail(request: Request, event_id: str):
    templates = request.app.state.templates

    with get_connection() as conn:
        event = conn.execute(
            """SELECT e.*,
                      COALESCE(pa.display_name, pa.email_address) AS account_name
               FROM events e
               LEFT JOIN provider_accounts pa ON pa.id = e.account_id
               WHERE e.id = ?""",
            (event_id,),
        ).fetchone()
        if not event:
            return HTMLResponse("Event not found", status_code=404)
        event = dict(event)

        # Participants with entity names
        raw_parts = conn.execute(
            "SELECT * FROM event_participants WHERE event_id = ?",
            (event_id,),
        ).fetchall()
        participants = []
        for p in raw_parts:
            pd = dict(p)
            if pd["entity_type"] == "contact":
                ct = conn.execute(
                    "SELECT name FROM contacts WHERE id = ?",
                    (pd["entity_id"],),
                ).fetchone()
                pd["entity_name"] = ct["name"] if ct else pd["entity_id"][:8]
            else:
                co = conn.execute(
                    "SELECT name FROM companies WHERE id = ?",
                    (pd["entity_id"],),
                ).fetchone()
                pd["entity_name"] = co["name"] if co else pd["entity_id"][:8]
            participants.append(pd)

        # Linked conversations
        convs = conn.execute(
            """SELECT c.* FROM conversations c
               JOIN event_conversations ec ON ec.conversation_id = c.id
               WHERE ec.event_id = ?
               ORDER BY c.last_activity_at DESC""",
            (event_id,),
        ).fetchall()
        conversations = [dict(r) for r in convs]

    return templates.TemplateResponse(request, "events/detail.html", {
        "active_nav": "events",
        "event": event,
        "participants": participants,
        "conversations": conversations,
    })
