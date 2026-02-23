# Event — Calendar Sync Pipeline Sub-PRD

**Version:** 1.0
**Last Updated:** 2026-02-23
**Status:** Draft
**Entity Base PRD:** [event-entity-base-prd.md]
**Referenced Entity PRDs:** [event-participants-prd.md] (attendee resolution post-sync), [communication-provider-sync-prd.md] (provider_accounts reuse)

---

## 1. Overview

### 1.1 Purpose

This sub-PRD defines how events flow from external calendar providers into CRMExtender: the Google Calendar API client, sync orchestration with incremental token-based updates, UPSERT deduplication, provider field mapping, OAuth scope management, calendar selection settings, and error handling. The pipeline reuses existing provider account infrastructure — no new account types needed.

### 1.2 Preconditions

- Event entity operational with UPSERT deduplication constraint.
- provider_accounts table available with OAuth token management.
- Google Calendar API enabled in Google Cloud Console.
- User has authorized calendar.readonly OAuth scope.

---

## 2. Context

### 2.1 Relevant Fields

| Field | Role in This Action |
|---|---|
| source | Set to 'google_calendar' (or provider-specific value) during sync |
| provider_event_id | Provider's event identifier. Part of UNIQUE dedup constraint. |
| provider_calendar_id | Provider's calendar identifier. |
| provider_account_id | Which synced account. Part of UNIQUE dedup constraint. |

### 2.2 Cross-Entity Context

- **Communication Provider & Sync Framework Sub-PRD:** Sync pipeline reuses same provider_accounts infrastructure, OAuth token management, and sync pattern (initial + incremental with tokens).
- **Participants Sub-PRD:** After UPSERT, attendee resolution matches emails to contacts and creates participation relations.

---

## 3. Key Processes

### KP-1: Initial Calendar Sync

**Trigger:** User connects a calendar account or first sync for a calendar.

**Step 1 — Check scope:** Verify credentials include calendar.readonly. If missing, raise CalendarScopeError prompting re-authorization.

**Step 2 — Fetch calendars:** List user's calendars via calendarList API. Present for selection.

**Step 3 — Fetch events:** For each selected calendar, fetch all events from past 90 days (configurable). singleEvents=True expands recurring events.

**Step 4 — UPSERT:** Insert each event, deduplicating on (provider_account_id, provider_event_id). Set source = 'google_calendar'.

**Step 5 — Resolve attendees:** For each created/updated event, run attendee resolution (Participants Sub-PRD).

**Step 6 — Save sync token:** Persist returned sync token for future incremental sync.

### KP-2: Incremental Calendar Sync

**Trigger:** User clicks "Sync Events" or scheduled background sync.

**Step 1 — Load sync token:** Retrieve from settings table.

**Step 2 — Fetch changes:** Call API with sync_token. Returns only events changed since last sync.

**Step 3 — Handle token expiry:** If HTTP 410 (Gone), discard token and fall back to full initial sync (KP-1).

**Step 4 — UPSERT changes:** Insert/update events via dedup constraint. Handle cancelled events (set status = 'cancelled').

**Step 5 — Resolve attendees:** For changed events, re-run attendee resolution.

**Step 6 — Save new sync token.**

### KP-3: Calendar Selection

**Trigger:** User configures which calendars to sync.

**Step 1 — Fetch available:** API call to list all calendars for the provider account.

**Step 2 — User selects:** User checks/unchecks calendars to sync.

**Step 3 — Save selection:** Stored as JSON in settings table.

**Step 4 — Sync:** Selected calendars synced; unselected calendars ignored.

---

## 4. Provider Account Reuse

**Supports processes:** KP-1, KP-2

### 4.1 Requirements

Events reuse the existing provider_accounts table. Google Calendar uses the same Gmail provider accounts (provider = 'gmail') with OAuth scope extended to include calendar.readonly.

- Same OAuth token grants Gmail, Contacts, and Calendar access.
- No separate calendar account type needed.
- Adding calendar.readonly to existing tokens requires re-authorization.
- System detects missing scopes and prompts user.

### 4.2 OAuth Scopes

| Scope | Purpose |
|---|---|
| `gmail.readonly` | Email sync |
| `contacts.readonly` | Contact sync |
| `calendar.readonly` | Calendar event sync |

**Tasks:**

- [ ] ESYN-01: Implement OAuth scope detection for calendar.readonly
- [ ] ESYN-02: Implement re-authorization prompt when scope missing

**Tests:**

- [ ] ESYN-T01: Test CalendarScopeError raised when calendar scope missing
- [ ] ESYN-T02: Test sync works after re-authorization with calendar scope

---

## 5. Google Calendar API Client

**Supports processes:** KP-1, KP-2, KP-3

### 5.1 API Functions

**`list_calendars(creds) → list[dict]`**

Fetches user's calendar list via calendarList().list() with pagination. Returns calendar metadata: ID, name, access role, primary flag.

**`fetch_events(creds, calendar_id, *, time_min=None, sync_token=None) → tuple[list[dict], str | None]`**

Two modes:
- **Initial:** Pass time_min (ISO timestamp). Fetches events from that date. singleEvents=True.
- **Incremental:** Pass sync_token. Fetches only changes.

Returns (parsed_events, next_sync_token).

**`_parse_google_event(raw) → dict`**

Maps raw Google Calendar API event dict to internal format. Handles: all-day vs. timed events, attendee extraction, event type mapping, title heuristic for birthdays.

### 5.2 Error Types

| Error | Cause | Recovery |
|---|---|---|
| `CalendarScopeError` | Credentials lack calendar.readonly | Prompt re-authorization |
| `SyncTokenExpiredError` | HTTP 410 from Google | Discard token, full re-sync |

### 5.3 Google Calendar Field Mapping

| Google Calendar Field | Events Column |
|---|---|
| summary | title (default: "(no title)") |
| description | description |
| start.date (all-day) | start_date, is_all_day = true |
| start.dateTime (timed) | start_datetime, is_all_day = false |
| end.date | end_date |
| end.dateTime | end_datetime |
| start.timeZone | timezone |
| location | location |
| recurrence | recurrence_rule (first element) |
| status | status (confirmed/tentative/cancelled) |
| id | provider_event_id |
| eventType | event_type (via type resolution) |
| attendees[].email | → attendee resolution pipeline |
| attendees[].responseStatus | → rsvp_status mapping |
| organizer.email | → participation with role = 'organizer' |
| recurringEventId | recurring_event_id (via provider_event_id lookup) |

**Tasks:**

- [ ] ESYN-03: Implement list_calendars API wrapper
- [ ] ESYN-04: Implement fetch_events with initial and incremental modes
- [ ] ESYN-05: Implement _parse_google_event with field mapping
- [ ] ESYN-06: Implement all-day vs. timed event detection
- [ ] ESYN-07: Implement event type resolution from provider (Section mapping + title heuristic)
- [ ] ESYN-08: Implement attendee extraction from raw event
- [ ] ESYN-09: Implement SyncTokenExpiredError detection (HTTP 410)

**Tests:**

- [ ] ESYN-T03: Test list_calendars returns calendar metadata
- [ ] ESYN-T04: Test fetch_events initial mode with time_min
- [ ] ESYN-T05: Test fetch_events incremental mode with sync_token
- [ ] ESYN-T06: Test _parse_google_event maps all-day event correctly
- [ ] ESYN-T07: Test _parse_google_event maps timed event correctly
- [ ] ESYN-T08: Test event type resolution (default → meeting, birthday → birthday)
- [ ] ESYN-T09: Test title heuristic reclassifies "birthday" meetings
- [ ] ESYN-T10: Test SyncTokenExpiredError on HTTP 410

---

## 6. Sync Orchestration

**Supports processes:** KP-1, KP-2

### 6.1 sync_calendar_events()

Syncs events from a single calendar:

1. Load sync token from settings (key: `cal_sync_token_{account_id}_{calendar_id}`, scope: user).
2. Fetch events: if no token → initial (time_min = now - 90 days); if token → incremental. On SyncTokenExpiredError → full re-sync.
3. UPSERT each event via dedup constraint.
4. Resolve attendees for created/updated events.
5. Save new sync token.

Returns stats: `{events_created, events_updated, events_cancelled, attendees_matched}`.

### 6.2 sync_all_calendars()

Reads selected calendars from settings (`cal_sync_calendars_{account_id}`, JSON list). Calls sync_calendar_events() for each. Returns aggregate totals with calendars_synced count and errors list.

### 6.3 UPSERT Deduplication

```sql
INSERT INTO events (id, tenant_id, title, ..., provider_account_id, provider_event_id)
VALUES ($1, $2, $3, ..., $n-1, $n)
ON CONFLICT(provider_account_id, provider_event_id)
DO UPDATE SET
    title = EXCLUDED.title,
    start_datetime = EXCLUDED.start_datetime,
    end_datetime = EXCLUDED.end_datetime,
    location = EXCLUDED.location,
    status = EXCLUDED.status,
    event_type = EXCLUDED.event_type,
    updated_at = NOW(),
    updated_by = 'system:calendar_sync';
```

**Tasks:**

- [ ] ESYN-10: Implement sync_calendar_events orchestration
- [ ] ESYN-11: Implement sync_all_calendars multi-calendar orchestration
- [ ] ESYN-12: Implement UPSERT with ON CONFLICT deduplication
- [ ] ESYN-13: Implement sync token load/save in settings table
- [ ] ESYN-14: Implement fallback to full sync on token expiry
- [ ] ESYN-15: Implement sync stats return value

**Tests:**

- [ ] ESYN-T11: Test initial sync creates events from past 90 days
- [ ] ESYN-T12: Test incremental sync fetches only changes
- [ ] ESYN-T13: Test UPSERT updates existing event (no duplicate)
- [ ] ESYN-T14: Test token expiry triggers full re-sync
- [ ] ESYN-T15: Test sync token persisted after successful sync
- [ ] ESYN-T16: Test sync stats reflect correct counts

---

## 7. Calendar Selection Settings

**Supports processes:** KP-3

### 7.1 Settings Storage

Calendar selections stored as JSON in settings table:
- Key: `cal_sync_calendars_{account_id}`
- Value: JSON array of calendar IDs
- Scope: user

### 7.2 API Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/settings/calendars` | List connected accounts and their calendars |
| POST | `/api/v1/settings/calendars/{account_id}/fetch` | Fetch available calendars for account |
| POST | `/api/v1/settings/calendars/{account_id}/save` | Save selected calendar IDs |

### 7.3 Configuration

| Constant | Value | Description |
|---|---|---|
| GOOGLE_SCOPES | [gmail.readonly, contacts.readonly, calendar.readonly] | OAuth scopes |
| CALENDAR_SYNC_DAYS | 90 | Initial backfill days |

**Tasks:**

- [ ] ESYN-16: Implement calendar selection settings storage
- [ ] ESYN-17: Implement fetch available calendars API
- [ ] ESYN-18: Implement save selected calendars API
- [ ] ESYN-19: Implement calendar selection UI integration

**Tests:**

- [ ] ESYN-T17: Test calendar selection persisted correctly
- [ ] ESYN-T18: Test only selected calendars synced
- [ ] ESYN-T19: Test unselected calendar events not synced
