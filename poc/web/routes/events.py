"""Event routes — list, search, create, detail, delete, sync."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from ...database import get_connection
from ...hierarchy import get_addresses, add_address, remove_address

log = logging.getLogger(__name__)
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


def _query_events(*, search: str = "", event_type: str = "",
                  sort: str = "",
                  page: int = 1, per_page: int = 50,
                  customer_id: str = "", user_id: str = ""):
    from ...views.crud import get_default_view_for_entity
    from ...views.engine import execute_view

    with get_connection() as conn:
        view = get_default_view_for_entity(conn, customer_id, user_id, "event")
        columns = view["columns"] if view else []
        filters = list(view["filters"]) if view and view.get("filters") else []
        sort_field, sort_direction = _parse_sort(sort, view)

        if event_type:
            filters.append({"field_key": "event_type", "operator": "equals", "value": event_type})

        rows, total = execute_view(
            conn,
            entity_type="event",
            columns=columns,
            filters=filters,
            sort_field=sort_field,
            sort_direction=sort_direction,
            search=search,
            page=page,
            per_page=per_page,
            customer_id=customer_id,
        )

    return rows, total, view


@router.get("", response_class=HTMLResponse)
def event_list(request: Request, q: str = "", event_type: str = "",
               sort: str = "", page: int = 1):
    from ...views.registry import ENTITY_TYPES

    templates = request.app.state.templates
    user = request.state.user
    cid = request.state.customer_id
    events, total, view = _query_events(
        search=q, event_type=event_type, sort=sort, page=page,
        customer_id=cid, user_id=user["id"],
    )
    total_pages = max(1, (total + 49) // 50)

    return templates.TemplateResponse(request, "events/list.html", {
        "active_nav": "events",
        "rows": events,
        "total": total,
        "page": page,
        "total_pages": total_pages,
        "q": q,
        "sort": sort,
        "event_type": event_type,
        "view": view,
        "entity_def": ENTITY_TYPES["event"],
    })


@router.get("/search", response_class=HTMLResponse)
def event_search(request: Request, q: str = "", event_type: str = "",
                 sort: str = "", page: int = 1):
    from ...views.registry import ENTITY_TYPES

    templates = request.app.state.templates
    user = request.state.user
    cid = request.state.customer_id
    events, total, view = _query_events(
        search=q, event_type=event_type, sort=sort, page=page,
        customer_id=cid, user_id=user["id"],
    )
    total_pages = max(1, (total + 49) // 50)

    return templates.TemplateResponse(request, "events/_rows.html", {
        "rows": events,
        "total": total,
        "page": page,
        "total_pages": total_pages,
        "q": q,
        "sort": sort,
        "event_type": event_type,
        "view": view,
        "entity_def": ENTITY_TYPES["event"],
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
               WHERE upa.user_id = ? AND pa.is_active = 1
               ORDER BY pa.created_at""",
            (uid,),
        ).fetchall()
        accounts = [dict(a) for a in rows]

    if not accounts:
        # Fallback to customer's accounts
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM provider_accounts WHERE customer_id = ? AND is_active = 1 ORDER BY created_at",
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

    addresses = get_addresses("event", event_id)

    from ...notes import get_notes_for_entity
    cid = request.state.customer_id
    notes = get_notes_for_entity("event", event_id, customer_id=cid)

    return templates.TemplateResponse(request, "events/detail.html", {
        "active_nav": "events",
        "event": event,
        "participants": participants,
        "conversations": conversations,
        "addresses": addresses,
        "notes": notes,
        "entity_type": "event",
        "entity_id": event_id,
    })


# ---------------------------------------------------------------------------
# Addresses
# ---------------------------------------------------------------------------

@router.post("/{event_id}/addresses", response_class=HTMLResponse)
def event_add_address(
    request: Request,
    event_id: str,
    address_type: str = Form("venue"),
    street: str = Form(""),
    city: str = Form(""),
    state: str = Form(""),
    postal_code: str = Form(""),
    country: str = Form(""),
):
    templates = request.app.state.templates
    add_address(
        "event", event_id,
        address_type=address_type, street=street, city=city,
        state=state, postal_code=postal_code, country=country,
    )
    addresses = get_addresses("event", event_id)

    return templates.TemplateResponse(request, "events/_addresses.html", {
        "event": {"id": event_id},
        "addresses": addresses,
    })


@router.delete("/{event_id}/addresses/{address_id}", response_class=HTMLResponse)
def event_remove_address(
    request: Request, event_id: str, address_id: str,
):
    templates = request.app.state.templates
    remove_address(address_id)
    addresses = get_addresses("event", event_id)

    return templates.TemplateResponse(request, "events/_addresses.html", {
        "event": {"id": event_id},
        "addresses": addresses,
    })
