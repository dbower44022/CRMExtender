"""Calendar sync orchestration — upsert events + match attendees."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timedelta, timezone

from . import config
from .calendar_client import SyncTokenExpiredError, fetch_events
from .database import get_connection
from .rate_limiter import RateLimiter
from .settings import get_setting, set_setting

log = logging.getLogger(__name__)

RSVP_MAP = {
    "accepted": "accepted",
    "declined": "declined",
    "tentative": "tentative",
    "needsAction": "needs_action",
}


def sync_calendar_events(
    account_id: str,
    creds,
    calendar_id: str,
    *,
    rate_limiter: RateLimiter | None = None,
    customer_id: str,
    user_id: str,
) -> dict:
    """Sync events from a single calendar. Returns stats dict."""
    token_key = f"cal_sync_token_{account_id}_{calendar_id}"
    sync_token = get_setting(customer_id, token_key, user_id=user_id)

    events_created = 0
    events_updated = 0
    events_cancelled = 0
    attendees_matched = 0

    try:
        if sync_token:
            # Incremental sync
            try:
                parsed_events, next_token = fetch_events(
                    creds, calendar_id,
                    sync_token=sync_token,
                    rate_limiter=rate_limiter,
                )
            except SyncTokenExpiredError:
                log.info("Sync token expired for %s, doing full re-sync", calendar_id)
                sync_token = None
                time_min = _time_min_for_backfill()
                parsed_events, next_token = fetch_events(
                    creds, calendar_id,
                    time_min=time_min,
                    rate_limiter=rate_limiter,
                )
        else:
            # Initial sync
            time_min = _time_min_for_backfill()
            parsed_events, next_token = fetch_events(
                creds, calendar_id,
                time_min=time_min,
                rate_limiter=rate_limiter,
            )

        now = datetime.now(timezone.utc).isoformat()

        with get_connection() as conn:
            for event in parsed_events:
                result = _upsert_event(
                    conn, event, account_id, calendar_id,
                    customer_id=customer_id, user_id=user_id, now=now,
                )
                if result == "created":
                    events_created += 1
                elif result == "updated":
                    events_updated += 1

                if event["status"] == "cancelled":
                    events_cancelled += 1

                # Match attendees
                if result in ("created", "updated") and event.get("attendees"):
                    event_id = _get_event_id(
                        conn, account_id, event["provider_event_id"],
                    )
                    if event_id:
                        matched = _match_attendees(
                            conn, event_id, event["attendees"], customer_id,
                        )
                        attendees_matched += matched

        # Save sync token
        if next_token:
            set_setting(
                customer_id, token_key, next_token,
                scope="user", user_id=user_id,
            )

    except Exception:
        log.exception("Failed to sync calendar %s", calendar_id)
        raise

    return {
        "events_created": events_created,
        "events_updated": events_updated,
        "events_cancelled": events_cancelled,
        "attendees_matched": attendees_matched,
    }


def sync_all_calendars(
    account_id: str,
    creds,
    *,
    rate_limiter: RateLimiter | None = None,
    customer_id: str,
    user_id: str,
) -> dict:
    """Sync all selected calendars for an account. Returns aggregate stats."""
    cal_key = f"cal_sync_calendars_{account_id}"
    cal_json = get_setting(customer_id, cal_key, user_id=user_id)

    if not cal_json:
        return {"error": "No calendars selected"}

    try:
        calendar_ids = json.loads(cal_json)
    except (json.JSONDecodeError, TypeError):
        return {"error": "Invalid calendar selection"}

    if not calendar_ids:
        return {"error": "No calendars selected"}

    totals = {
        "events_created": 0,
        "events_updated": 0,
        "events_cancelled": 0,
        "attendees_matched": 0,
        "calendars_synced": 0,
        "errors": [],
    }

    for cal_id in calendar_ids:
        try:
            result = sync_calendar_events(
                account_id, creds, cal_id,
                rate_limiter=rate_limiter,
                customer_id=customer_id,
                user_id=user_id,
            )
            totals["events_created"] += result["events_created"]
            totals["events_updated"] += result["events_updated"]
            totals["events_cancelled"] += result["events_cancelled"]
            totals["attendees_matched"] += result["attendees_matched"]
            totals["calendars_synced"] += 1
        except Exception as exc:
            log.warning("Calendar sync failed for %s: %s", cal_id, exc)
            totals["errors"].append(f"{cal_id}: {exc}")

    return totals


def _time_min_for_backfill() -> str:
    """Return ISO timestamp for N days ago (initial sync window)."""
    dt = datetime.now(timezone.utc) - timedelta(days=config.CALENDAR_SYNC_DAYS)
    return dt.isoformat()


def _upsert_event(
    conn, event: dict, account_id: str, calendar_id: str,
    *, customer_id: str, user_id: str, now: str,
) -> str:
    """Insert or update an event. Returns 'created' or 'updated'."""
    existing = conn.execute(
        "SELECT id FROM events WHERE account_id = ? AND provider_event_id = ?",
        (account_id, event["provider_event_id"]),
    ).fetchone()

    if existing:
        conn.execute(
            """UPDATE events SET
                title = ?, description = ?,
                start_datetime = ?, start_date = ?,
                end_datetime = ?, end_date = ?,
                is_all_day = ?, location = ?,
                status = ?, event_type = ?,
                provider_calendar_id = ?,
                updated_by = ?, updated_at = ?
               WHERE id = ?""",
            (
                event["title"], event.get("description"),
                event.get("start_datetime"), event.get("start_date"),
                event.get("end_datetime"), event.get("end_date"),
                event["is_all_day"], event.get("location"),
                event["status"], event["event_type"],
                calendar_id,
                user_id, now,
                existing["id"],
            ),
        )
        return "updated"
    else:
        event_id = str(uuid.uuid4())
        conn.execute(
            """INSERT INTO events
               (id, title, description, event_type,
                start_date, start_datetime, end_date, end_datetime,
                is_all_day, location, status, source,
                provider_event_id, provider_calendar_id, account_id,
                created_by, updated_by, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                event_id, event["title"], event.get("description"),
                event["event_type"],
                event.get("start_date"), event.get("start_datetime"),
                event.get("end_date"), event.get("end_datetime"),
                event["is_all_day"], event.get("location"),
                event["status"], event["source"],
                event["provider_event_id"], calendar_id, account_id,
                user_id, user_id, now, now,
            ),
        )
        return "created"


def _get_event_id(conn, account_id: str, provider_event_id: str) -> str | None:
    """Look up internal event ID by provider event ID."""
    row = conn.execute(
        "SELECT id FROM events WHERE account_id = ? AND provider_event_id = ?",
        (account_id, provider_event_id),
    ).fetchone()
    return row["id"] if row else None


def _match_attendees(
    conn, event_id: str, attendees: list[dict], customer_id: str,
) -> int:
    """Match attendees to CRM contacts and insert event_participants. Returns count matched."""
    matched = 0

    # Clear existing auto-matched participants for this event
    conn.execute(
        "DELETE FROM event_participants WHERE event_id = ? AND entity_type = 'contact'",
        (event_id,),
    )

    for att in attendees:
        email = att.get("email", "").strip().lower()
        if not email:
            continue

        # Look up contact by email identifier
        row = conn.execute(
            """SELECT c.id FROM contacts c
               JOIN contact_identifiers ci ON ci.contact_id = c.id
               WHERE ci.type = 'email' AND ci.value = ? AND c.customer_id = ?""",
            (email, customer_id),
        ).fetchone()

        if not row:
            continue

        contact_id = row["id"]
        role = "organizer" if att.get("organizer") else "attendee"
        rsvp = RSVP_MAP.get(att.get("responseStatus", ""), "needs_action")

        conn.execute(
            """INSERT OR IGNORE INTO event_participants
               (event_id, entity_type, entity_id, role, rsvp_status)
               VALUES (?, 'contact', ?, ?, ?)""",
            (event_id, contact_id, role, rsvp),
        )
        matched += 1

    return matched
