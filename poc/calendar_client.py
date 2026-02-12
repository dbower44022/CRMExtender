"""Google Calendar API wrapper for fetching calendars and events."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from .rate_limiter import RateLimiter

log = logging.getLogger(__name__)

CALENDAR_SCOPE = "https://www.googleapis.com/auth/calendar.readonly"


class CalendarScopeError(Exception):
    """Raised when credentials lack calendar.readonly scope."""


class SyncTokenExpiredError(Exception):
    """Raised when a sync token returns HTTP 410 (Gone)."""


def _check_calendar_scope(creds: Credentials) -> None:
    """Raise CalendarScopeError if credentials lack calendar scope."""
    if hasattr(creds, "scopes") and creds.scopes:
        if CALENDAR_SCOPE not in creds.scopes:
            raise CalendarScopeError(
                "Calendar scope not granted. "
                "Run: python3 -m poc reauth EMAIL to re-authorize with calendar access."
            )


def list_calendars(
    creds: Credentials, rate_limiter: RateLimiter | None = None
) -> list[dict]:
    """Fetch all calendars the user has access to."""
    _check_calendar_scope(creds)
    service = build("calendar", "v3", credentials=creds)
    calendars: list[dict] = []
    page_token: str | None = None

    while True:
        if rate_limiter:
            rate_limiter.acquire()

        result = service.calendarList().list(
            pageToken=page_token or "",
        ).execute()

        for cal in result.get("items", []):
            calendars.append({
                "id": cal["id"],
                "summary": cal.get("summary", cal["id"]),
                "primary": cal.get("primary", False),
                "accessRole": cal.get("accessRole", "reader"),
                "backgroundColor": cal.get("backgroundColor", ""),
            })

        page_token = result.get("nextPageToken")
        if not page_token:
            break

    log.info("Fetched %d calendars", len(calendars))
    return calendars


def fetch_events(
    creds: Credentials,
    calendar_id: str,
    *,
    time_min: str | None = None,
    sync_token: str | None = None,
    rate_limiter: RateLimiter | None = None,
) -> tuple[list[dict], str | None]:
    """Fetch events from a calendar, returning (parsed_events, next_sync_token).

    If sync_token is provided, performs incremental sync (ignores time_min).
    If sync_token returns HTTP 410, raises SyncTokenExpiredError.
    """
    _check_calendar_scope(creds)
    service = build("calendar", "v3", credentials=creds)
    events: list[dict] = []
    page_token: str | None = None
    next_sync_token: str | None = None

    while True:
        if rate_limiter:
            rate_limiter.acquire()

        kwargs: dict = {
            "calendarId": calendar_id,
            "singleEvents": True,
            "orderBy": "startTime",
            "maxResults": 250,
        }

        if sync_token and not page_token:
            kwargs["syncToken"] = sync_token
            # Don't use timeMin/timeMax with syncToken
            kwargs.pop("orderBy", None)
            kwargs.pop("singleEvents", None)
        elif time_min:
            kwargs["timeMin"] = time_min

        if page_token:
            kwargs["pageToken"] = page_token

        try:
            result = service.events().list(**kwargs).execute()
        except HttpError as exc:
            if exc.resp.status == 410:
                raise SyncTokenExpiredError(
                    f"Sync token expired for calendar {calendar_id}"
                ) from exc
            raise

        for raw in result.get("items", []):
            parsed = _parse_google_event(raw)
            if parsed:
                events.append(parsed)

        page_token = result.get("nextPageToken")
        next_sync_token = result.get("nextSyncToken")
        if not page_token:
            break

    log.info(
        "Fetched %d events from calendar %s (incremental=%s)",
        len(events), calendar_id, sync_token is not None,
    )
    return events, next_sync_token


def _parse_google_event(raw: dict) -> dict | None:
    """Parse a raw Google Calendar event into our internal format."""
    event_id = raw.get("id")
    if not event_id:
        return None

    title = raw.get("summary", "(no title)")
    status = raw.get("status", "confirmed")

    # Start time
    start = raw.get("start", {})
    start_datetime = start.get("dateTime")
    start_date = start.get("date")
    is_all_day = 1 if start_date and not start_datetime else 0

    # End time
    end = raw.get("end", {})
    end_datetime = end.get("dateTime")
    end_date = end.get("date")

    # Location
    location = raw.get("location")

    # Description
    description = raw.get("description")

    # Attendees
    attendees = []
    for att in raw.get("attendees", []):
        attendees.append({
            "email": att.get("email", ""),
            "displayName": att.get("displayName", ""),
            "organizer": att.get("organizer", False),
            "responseStatus": att.get("responseStatus", "needsAction"),
        })

    # Organizer (if not in attendees)
    organizer = raw.get("organizer", {})

    return {
        "provider_event_id": event_id,
        "title": title,
        "description": description,
        "start_datetime": start_datetime,
        "start_date": start_date,
        "end_datetime": end_datetime,
        "end_date": end_date,
        "is_all_day": is_all_day,
        "location": location,
        "status": status,
        "event_type": "meeting",
        "source": "google_calendar",
        "attendees": attendees,
        "organizer_email": organizer.get("email", ""),
    }
