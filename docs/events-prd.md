# Events PRD

## CRMExtender — Calendar Event Tracking

**Version:** 1.0
**Date:** 2026-02-09
**Status:** Implemented (v6 schema)
**Parent Documents:** [CRMExtender PRD v1.1](PRD.md), [Data Layer PRD](data-layer-prd.md)

---

## Table of Contents

1. [Problem Statement](#1-problem-statement)
2. [Goals & Non-Goals](#2-goals--non-goals)
3. [Data Model](#3-data-model)
4. [Event Types](#4-event-types)
5. [Recurrence Model](#5-recurrence-model)
6. [Entity Linking](#6-entity-linking)
7. [Conversation Linking](#7-conversation-linking)
8. [Provider Integration](#8-provider-integration)
9. [Data Model (Python)](#9-data-model-python)
10. [Migration Path](#10-migration-path)
11. [CLI Commands](#11-cli-commands)
12. [Test Coverage](#12-test-coverage)
13. [Future Work](#13-future-work)
14. [Web UI](#14-web-ui)
15. [Design Decisions](#15-design-decisions)
16. [Google Calendar Sync](#16-google-calendar-sync)

---

## 1. Problem Statement

CRMExtender tracks communications (emails) and relationships between
contacts and companies, but has no concept of calendar events.  This
creates several gaps:

- **No meeting context** — conversations reference meetings, but there
  is no structured record of when a meeting occurred, who attended, or
  where it was held.
- **No life events** — birthdays and anniversaries are important CRM
  data points for maintaining relationships, but have no place in the
  data model.
- **No external calendar integration** — users manage calendars in
  Google Calendar, Outlook, Apple Calendar, and other tools, but this
  data is siloed away from their CRM context.
- **No event-conversation correlation** — a meeting often produces
  follow-up emails, but there is no way to link the calendar event to
  the resulting conversation thread.

---

## 2. Goals & Non-Goals

### Goals

1. **Calendar event storage** — a first-class `events` table that
   stores meetings, birthdays, anniversaries, conferences, deadlines,
   and other calendar items with full timing, location, and recurrence
   data.
2. **Multi-source import** — events can be imported from Google
   Calendar, Outlook/Exchange, Apple Calendar, CRM tools, and .ics
   files, using the existing `provider_accounts` infrastructure.
3. **Entity linking** — events link to contacts and companies via a
   polymorphic `event_participants` join table, supporting roles like
   attendee, organizer, honoree, and host.
4. **Conversation linking** — events link to conversations via an
   `event_conversations` join table, enabling "this meeting produced
   this email thread" correlations.
5. **Recurrence support** — recurring events store iCalendar RRULE
   strings for provider fidelity, plus a simple `recurrence_type` enum
   for easy querying of common patterns.
6. **Provider deduplication** — the `UNIQUE(account_id,
   provider_event_id)` constraint prevents duplicate events during
   repeated syncs.
7. **Recurring event instances** — modified instances of a recurring
   series link back to the parent via `recurring_event_id`.

### Non-Goals

- **Task/todo tracking** — tasks are explicitly out of scope and will
  be a separate object in a future iteration.
- **Reminders/notifications** — reminder scheduling and delivery are
  deferred to a future version.
- ~~**Calendar sync implementation** — this PRD defines the data model
  and provider integration points.  The actual Google Calendar API
  client, Outlook sync, etc. are future implementation work.~~
  **Implemented** — Google Calendar sync is live.  See
  [Google Calendar Sync](#16-google-calendar-sync) section below.
  Outlook and Apple Calendar remain future work.
- **Web UI for events** — ~~the events browser, creation form, and
  detail pages will be added in a subsequent iteration.~~
  **Implemented** — see [Web UI](#web-ui) section below.
- **Recurring event instance materialization** — the system stores
  RRULE definitions and individual modified instances, but does not
  auto-generate concrete rows for every occurrence.  Instance expansion
  is an application-layer concern handled at query time.
- **Conflict detection** — no overlapping-event detection or
  scheduling logic.

---

## 3. Data Model

### 3.1 `events` Table

```sql
CREATE TABLE events (
    id                   TEXT PRIMARY KEY,
    title                TEXT NOT NULL,
    description          TEXT,
    event_type           TEXT NOT NULL DEFAULT 'meeting',
    start_date           TEXT,
    start_datetime       TEXT,
    end_date             TEXT,
    end_datetime         TEXT,
    is_all_day           INTEGER DEFAULT 0,
    timezone             TEXT,
    recurrence_rule      TEXT,
    recurrence_type      TEXT DEFAULT 'none',
    recurring_event_id   TEXT REFERENCES events(id) ON DELETE SET NULL,
    location             TEXT,
    provider_event_id    TEXT,
    provider_calendar_id TEXT,
    account_id           TEXT REFERENCES provider_accounts(id) ON DELETE SET NULL,
    source               TEXT DEFAULT 'manual',
    status               TEXT DEFAULT 'confirmed',
    created_by           TEXT REFERENCES users(id) ON DELETE SET NULL,
    updated_by           TEXT REFERENCES users(id) ON DELETE SET NULL,
    created_at           TEXT NOT NULL,
    updated_at           TEXT NOT NULL,
    UNIQUE(account_id, provider_event_id),
    CHECK (event_type IN ('meeting','birthday','anniversary',
                          'conference','deadline','other')),
    CHECK (recurrence_type IN ('none','daily','weekly','monthly','yearly')),
    CHECK (status IN ('confirmed','tentative','cancelled'))
);
```

Key constraints:
- `title` is NOT NULL — every event must have a name.
- `event_type` is restricted to six values via CHECK constraint.
- `recurrence_type` is restricted to five values via CHECK constraint.
- `status` is restricted to three values via CHECK constraint.
- `UNIQUE(account_id, provider_event_id)` prevents duplicate synced
  events from the same provider account.
- `recurring_event_id` is a self-referencing FK that links modified
  instances back to their parent recurring event.  `ON DELETE SET NULL`
  ensures deleting the parent does not cascade-delete all instances.
- `account_id` references `provider_accounts(id)` with `ON DELETE SET
  NULL` — removing a provider account preserves events but clears the
  link.

#### Column Reference

| Column | Type | Description |
|---|---|---|
| `id` | TEXT PK | UUID, generated by application |
| `title` | TEXT NOT NULL | Event name/summary |
| `description` | TEXT | Extended description or notes |
| `event_type` | TEXT | One of: `meeting`, `birthday`, `anniversary`, `conference`, `deadline`, `other` |
| `start_date` | TEXT | ISO 8601 date (`YYYY-MM-DD`) for all-day events |
| `start_datetime` | TEXT | ISO 8601 datetime for timed events |
| `end_date` | TEXT | ISO 8601 date for all-day event end |
| `end_datetime` | TEXT | ISO 8601 datetime for timed event end |
| `is_all_day` | INTEGER | `1` for all-day events (birthdays, anniversaries), `0` for timed events |
| `timezone` | TEXT | IANA timezone identifier (e.g., `America/New_York`) |
| `recurrence_rule` | TEXT | iCalendar RRULE string (e.g., `RRULE:FREQ=YEARLY;BYMONTH=3;BYMONTHDAY=15`) |
| `recurrence_type` | TEXT | Simple enum: `none`, `daily`, `weekly`, `monthly`, `yearly` |
| `recurring_event_id` | TEXT FK | Self-reference to parent recurring event (for modified instances) |
| `location` | TEXT | Event location (free text, address, or room name) |
| `provider_event_id` | TEXT | Provider-specific event ID (e.g., Google Calendar event ID) |
| `provider_calendar_id` | TEXT | Provider-specific calendar ID (e.g., `primary`, shared calendar ID) |
| `account_id` | TEXT FK | References `provider_accounts(id)` — which synced account this came from |
| `source` | TEXT | Origin of the event (see [Provider Integration](#8-provider-integration)) |
| `status` | TEXT | Event status: `confirmed`, `tentative`, `cancelled` |
| `created_by` | TEXT FK | References `users(id)` — audit column |
| `updated_by` | TEXT FK | References `users(id)` — audit column |
| `created_at` | TEXT | ISO 8601 timestamp, set on creation |
| `updated_at` | TEXT | ISO 8601 timestamp, set on every update |

### 3.2 `event_participants` Table

```sql
CREATE TABLE event_participants (
    event_id    TEXT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    entity_type TEXT NOT NULL,
    entity_id   TEXT NOT NULL,
    role        TEXT DEFAULT 'attendee',
    rsvp_status TEXT,
    PRIMARY KEY (event_id, entity_type, entity_id),
    CHECK (entity_type IN ('contact', 'company')),
    CHECK (rsvp_status IS NULL OR rsvp_status IN
           ('accepted','declined','tentative','needs_action'))
);
```

Key constraints:
- Composite primary key `(event_id, entity_type, entity_id)` prevents
  duplicate participant entries.
- `entity_type` is restricted to `'contact'` or `'company'` — reuses
  the same polymorphic pattern as the `relationships` table.
- `rsvp_status` allows NULL (for entities where RSVP is not
  applicable, such as companies) or one of four iCalendar-standard
  values.
- `ON DELETE CASCADE` — deleting an event removes all its participant
  links.

#### Column Reference

| Column | Type | Description |
|---|---|---|
| `event_id` | TEXT FK | References `events(id)` |
| `entity_type` | TEXT | `'contact'` or `'company'` |
| `entity_id` | TEXT | UUID of the contact or company |
| `role` | TEXT | Participant role (see [Entity Linking](#6-entity-linking)) |
| `rsvp_status` | TEXT | `accepted`, `declined`, `tentative`, `needs_action`, or NULL |

### 3.3 `event_conversations` Table

```sql
CREATE TABLE event_conversations (
    event_id        TEXT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    created_at      TEXT NOT NULL,
    PRIMARY KEY (event_id, conversation_id)
);
```

Key constraints:
- M:N join — an event can link to multiple conversations and a
  conversation can link to multiple events.
- Both FKs use `ON DELETE CASCADE` — deleting either side removes the
  link row.
- `created_at` records when the link was established.

### 3.4 Indexes

```sql
-- Events
CREATE INDEX idx_events_type          ON events(event_type);
CREATE INDEX idx_events_start_dt      ON events(start_datetime);
CREATE INDEX idx_events_start_date    ON events(start_date);
CREATE INDEX idx_events_status        ON events(status);
CREATE INDEX idx_events_account       ON events(account_id);
CREATE INDEX idx_events_recurring     ON events(recurring_event_id);
CREATE INDEX idx_events_source        ON events(source);
CREATE INDEX idx_events_provider      ON events(account_id, provider_event_id);

-- Event participants
CREATE INDEX idx_ep_entity            ON event_participants(entity_type, entity_id);

-- Event conversations
CREATE INDEX idx_ec_conversation      ON event_conversations(conversation_id);
```

Index rationale:
- `idx_events_start_dt` / `idx_events_start_date` — powers "upcoming
  events" and date-range queries.
- `idx_events_type` — filters by event type (e.g., "show all
  birthdays").
- `idx_events_provider` — composite index for provider sync dedup
  lookups (`WHERE account_id = ? AND provider_event_id = ?`).
- `idx_ep_entity` — powers "show all events for contact X" or
  "show all events for company Y" queries.
- `idx_ec_conversation` — powers reverse lookup from conversation
  detail page ("events linked to this conversation").

---

## 4. Event Types

Six event types are supported, enforced by a CHECK constraint:

| Type | Description | Typical Usage |
|---|---|---|
| `meeting` | Scheduled meetings with other people | Default type. 1:1s, team meetings, client calls. |
| `birthday` | A person's date of birth | Linked to a contact with `role='honoree'`. Always all-day, yearly recurrence. |
| `anniversary` | Recurring annual milestone | Work anniversaries, company founding dates, relationship milestones. |
| `conference` | Multi-day conferences or trade shows | Linked to a company with `role='host'`. May span multiple days. |
| `deadline` | Non-task deadline date | Contract renewals, filing deadlines, subscription expirations. Not a to-do item. |
| `other` | Catch-all for uncategorized events | Events that don't fit other categories. |

The CHECK constraint can be extended via migration if additional types
are needed in the future.

---

## 5. Recurrence Model

Events support two complementary recurrence representations:

### 5.1 `recurrence_rule` (RRULE)

An iCalendar RFC 5545 RRULE string that encodes the full recurrence
pattern.  This is the native format used by Google Calendar, Outlook,
and Apple Calendar, making import/export lossless.

Examples:
- `RRULE:FREQ=YEARLY;BYMONTH=3;BYMONTHDAY=15` — birthday on March 15
- `RRULE:FREQ=WEEKLY;BYDAY=MO,WE,FR` — MWF standup
- `RRULE:FREQ=MONTHLY;BYDAY=1TU` — first Tuesday of each month
- `RRULE:FREQ=DAILY;COUNT=5` — daily for 5 days

Python's `dateutil.rrule.rrulestr()` can parse these for occurrence
expansion.

### 5.2 `recurrence_type` (Simple Enum)

A denormalized enum column for easy querying without RRULE parsing:

| Value | Description |
|---|---|
| `none` | One-time event (default) |
| `daily` | Repeats every day |
| `weekly` | Repeats every week |
| `monthly` | Repeats every month |
| `yearly` | Repeats every year |

This enables queries like `SELECT * FROM events WHERE recurrence_type
= 'yearly' AND event_type = 'birthday'` without application-layer
RRULE parsing.

### 5.3 Recurring Event Instances

When a provider (e.g., Google Calendar) modifies a single occurrence
of a recurring event, the modified instance is stored as a separate
row with `recurring_event_id` pointing to the parent event.  The
instance has `recurrence_type = 'none'` (it is not itself recurring)
and carries its own specific `start_datetime` / `end_datetime`.

- **Parent event** — has the RRULE, `recurrence_type` set to the
  pattern, `recurring_event_id = NULL`.
- **Modified instance** — `recurring_event_id` points to the parent,
  `recurrence_type = 'none'`, with instance-specific times/title/etc.
- **Unmodified instances** — are NOT stored as rows.  They are
  computed at query time by expanding the parent's RRULE.
- **Deleting a parent** — sets `recurring_event_id = NULL` on all
  instances (`ON DELETE SET NULL`).  Instances survive as standalone
  events.

---

## 6. Entity Linking

The `event_participants` table links events to contacts and companies
using the same `entity_type` / `entity_id` polymorphic pattern as the
`relationships` table.

### 6.1 Participant Roles

Roles are free-text, allowing flexibility.  Common conventions:

| Role | Usage |
|---|---|
| `attendee` | Default role. A person invited to a meeting. |
| `organizer` | The person who created/owns the event. |
| `honoree` | The person whose birthday/anniversary it is. |
| `host` | A company hosting a conference or event. |
| `speaker` | A presenter at a conference. |
| `optional` | An optional attendee. |

Roles are not enforced by a CHECK constraint, allowing providers to
pass through their own role values.

### 6.2 RSVP Status

Maps to the iCalendar `PARTSTAT` parameter:

| Value | Description |
|---|---|
| `accepted` | Participant confirmed attendance |
| `declined` | Participant declined |
| `tentative` | Participant tentatively accepted |
| `needs_action` | No response yet |
| NULL | RSVP not applicable (e.g., company entities) |

### 6.3 Birthday Example

A birthday for contact "Alice" is stored as:

```
events:
  id: evt-alice-bday
  title: "Alice's Birthday"
  event_type: birthday
  start_date: "1990-03-15"
  is_all_day: 1
  recurrence_type: yearly
  recurrence_rule: "RRULE:FREQ=YEARLY;BYMONTH=3;BYMONTHDAY=15"
  source: manual

event_participants:
  event_id: evt-alice-bday
  entity_type: contact
  entity_id: <alice-contact-id>
  role: honoree
  rsvp_status: NULL
```

### 6.4 Meeting Example

A team meeting with two contacts:

```
events:
  id: evt-sprint
  title: "Sprint Planning"
  event_type: meeting
  start_datetime: "2026-02-10T09:00:00-05:00"
  end_datetime: "2026-02-10T10:00:00-05:00"
  timezone: "America/New_York"
  location: "Conference Room A"
  status: confirmed

event_participants:
  - event_id: evt-sprint, entity_type: contact,
    entity_id: <alice-id>, role: organizer, rsvp_status: accepted
  - event_id: evt-sprint, entity_type: contact,
    entity_id: <bob-id>, role: attendee, rsvp_status: accepted
```

### 6.5 Conference Example

A multi-day conference hosted by a company:

```
events:
  id: evt-conf
  title: "CRM Summit 2026"
  event_type: conference
  start_date: "2026-06-01"
  end_date: "2026-06-03"
  is_all_day: 1
  location: "Convention Center, Austin TX"

event_participants:
  - event_id: evt-conf, entity_type: company,
    entity_id: <acme-id>, role: host
  - event_id: evt-conf, entity_type: contact,
    entity_id: <alice-id>, role: speaker
  - event_id: evt-conf, entity_type: contact,
    entity_id: <bob-id>, role: attendee
```

---

## 7. Conversation Linking

The `event_conversations` M:N join table enables bidirectional
correlation between events and conversations.

### 7.1 Use Cases

- **Meeting follow-up** — a meeting event links to the email thread
  that followed up on action items.
- **Pre-meeting context** — a calendar invite links to the
  conversation thread that arranged the meeting.
- **Conference debrief** — a conference event links to multiple
  conversation threads discussing outcomes.

### 7.2 Cascade Behavior

- Deleting an event removes all `event_conversations` rows for that
  event (CASCADE on `event_id`).
- Deleting a conversation removes all `event_conversations` rows for
  that conversation (CASCADE on `conversation_id`).
- Neither cascade deletes the entity on the other side of the link.

---

## 8. Provider Integration

### 8.1 Provider Account Reuse

Events reuse the existing `provider_accounts` table.  Google Calendar
sync uses the same Gmail provider accounts (`provider = 'gmail'`)
with the OAuth scope extended to include `calendar.readonly`.  No
separate calendar account type is needed — the same OAuth token that
grants Gmail and Contacts access also grants Calendar read access
after re-authorization.

This means the sync infrastructure requires no new account
registration.  Existing accounts work once the user re-authorizes
to grant the calendar scope (see `reauth` CLI command).

### 8.2 Source Values

The `source` column on `events` identifies where the event originated:

| Source | Description |
|---|---|
| `manual` | Created directly by the user in CRMExtender |
| `google_calendar` | Imported from Google Calendar API |
| `outlook` | Imported from Outlook/Exchange |
| `apple_calendar` | Imported from Apple Calendar |
| `import` | Imported from an .ics file |
| `inferred` | Auto-generated from CRM data (e.g., birthday from contact record) |

### 8.3 Deduplication

The `UNIQUE(account_id, provider_event_id)` constraint ensures that
re-syncing from a provider does not create duplicate events.  The sync
client should use an UPSERT pattern:

```sql
INSERT INTO events (...) VALUES (...)
ON CONFLICT(account_id, provider_event_id)
DO UPDATE SET title=excluded.title, start_datetime=excluded.start_datetime, ...
```

### 8.4 Provider-Specific Fields

| Field | Google Calendar | Outlook | Apple Calendar |
|---|---|---|---|
| `provider_event_id` | `event.id` | `event.id` | `calendarItemIdentifier` |
| `provider_calendar_id` | `calendarId` (e.g., `primary`) | `calendar.id` | `calendar.calendarIdentifier` |
| `status` | `event.status` | `event.showAs` | `event.status` |
| `recurrence_rule` | `event.recurrence[0]` | `event.recurrence.pattern` | `event.recurrenceRules` |
| `timezone` | `event.start.timeZone` | `event.originalStartTimeZone` | `event.timeZone` |

### 8.5 Google Calendar Mapping

Google Calendar API events map to the `events` table as follows:

| Google Calendar Field | Events Column |
|---|---|
| `summary` | `title` |
| `description` | `description` |
| `start.date` (all-day) | `start_date`, `is_all_day = 1` |
| `start.dateTime` (timed) | `start_datetime`, `is_all_day = 0` |
| `end.date` | `end_date` |
| `end.dateTime` | `end_datetime` |
| `start.timeZone` | `timezone` |
| `location` | `location` |
| `recurrence` | `recurrence_rule` (first element) |
| `status` | `status` (`confirmed`/`tentative`/`cancelled`) |
| `id` | `provider_event_id` |
| `attendees[].email` | Resolved to contact via `contact_identifiers`, then inserted into `event_participants` |
| `attendees[].responseStatus` | `rsvp_status` |
| `organizer.email` | Participant with `role='organizer'` |
| `recurringEventId` | `recurring_event_id` (resolved via `provider_event_id` lookup) |

---

## 9. Data Model (Python)

### 9.1 `Event` Dataclass (`poc/models.py`)

```python
@dataclass
class Event:
    title: str
    event_type: str = "meeting"
    description: str = ""
    start_date: str = ""
    start_datetime: str = ""
    end_date: str = ""
    end_datetime: str = ""
    is_all_day: bool = False
    timezone: str = ""
    recurrence_rule: str = ""
    recurrence_type: str = "none"
    recurring_event_id: str | None = None
    location: str = ""
    provider_event_id: str = ""
    provider_calendar_id: str = ""
    account_id: str | None = None
    source: str = "manual"
    status: str = "confirmed"
```

Methods:
- `to_row(*, event_id, created_by, updated_by) -> dict` — serializes
  to a dict suitable for `INSERT INTO events`.  Generates a UUID if
  `event_id` is not provided.  Empty strings are converted to NULL for
  optional columns.
- `from_row(row) -> Event` — constructs from a `sqlite3.Row` or dict.
  Missing keys default to sensible values.  `is_all_day` is converted
  from integer (0/1) to bool.

---

## 10. Migration Path

### 10.1 v5 to v6

The v5 to v6 migration (`poc/migrate_to_v6.py`) adds the events
system to an existing database:

1. **Backup** — copies the database to
   `{name}.v5-backup-{timestamp}.db`.

2. **Create `events` table** — with all columns, constraints, and
   CHECK rules.  Skipped if the table already exists.

3. **Create `event_participants` table** — with composite PK and
   CHECK constraints.  Skipped if the table already exists.

4. **Create `event_conversations` table** — with composite PK and
   dual CASCADE FKs.  Skipped if the table already exists.

5. **Create indexes** — all 11 indexes using `CREATE INDEX IF NOT
   EXISTS`.

6. **Validate** — re-enables foreign keys, verifies all three tables
   exist, and checks that the `events` table has the expected columns.

The migration is idempotent — running it twice has no effect.  The
`--dry-run` flag applies the migration to the backup copy instead of
the production database.

### 10.2 Fresh Databases

`init_db()` in `poc/database.py` includes the events tables in
`_SCHEMA_SQL` and the indexes in `_INDEX_SQL`, so new databases are
created with events support from the start.

---

## 11. CLI Commands

### `migrate-to-v6`

```bash
python3 -m poc migrate-to-v6 [--db PATH] [--dry-run]
```

Migrates a v5 database to v6 schema.  Options:
- `--db PATH` — path to the SQLite database (defaults to
  `data/crm_extender.db`).
- `--dry-run` — applies migration to a backup copy, leaving the
  production database untouched.

---

## 12. Test Coverage

39 tests in `tests/test_events.py` + 28 tests in `tests/test_calendar_sync.py`:

### 12.1 Events Schema & Model Tests (`test_events.py`)

| Test Class | Count | Coverage |
|---|---|---|
| `TestEventModel` | 10 | `to_row()` defaults, explicit ID, birthday, timed meeting, provider fields, audit fields, empty-to-None conversion, `from_row()` roundtrip, missing fields, `is_all_day` bool conversion |
| `TestEventsSchema` | 4 | Table existence verification, column verification for all three tables |
| `TestEventsInsert` | 6 | Basic insert, birthday insert, CHECK constraints for `event_type` / `recurrence_type` / `status`, provider uniqueness constraint |
| `TestEventParticipants` | 8 | Contact participant, company participant, RSVP status, RSVP CHECK constraint, entity type CHECK constraint, multiple participants, CASCADE delete, honoree role |
| `TestEventConversations` | 5 | Basic link, multiple conversations per event, multiple events per conversation, CASCADE delete (both directions) |
| `TestRecurringEvents` | 2 | Parent-instance linking, ON DELETE SET NULL behavior |
| `TestMigration` | 4 | Fresh v5 DB migration, idempotency, backup creation, dry-run behavior |

### 12.2 Calendar Sync Tests (`test_calendar_sync.py`)

28 tests covering the Google Calendar sync pipeline:

| Test Class | Count | Coverage |
|---|---|---|
| `TestParseGoogleEvent` | 8 | Timed event, all-day event, cancelled event, no title fallback, attendees, RSVP status mapping, missing ID, description |
| `TestUpsertEvent` | 3 | Create new event, update existing event, cancelled status handling |
| `TestMatchAttendees` | 3 | Contact matching via email, unmatched attendee skipped, RSVP status passthrough |
| `TestSyncCalendarEvents` | 4 | Initial sync (creates events), incremental sync (uses token), sync token persistence, expired token fallback to full sync |
| `TestSyncAllCalendars` | 2 | Multi-calendar sync aggregation, no calendars selected error |
| `TestCalendarSettings` | 4 | Settings page renders, calendar selection save, fetch calendars list, scope error display |
| `TestEventsSyncRoute` | 4 | Sync button rendered in list, sync endpoint works, no accounts graceful handling, no calendars selected message |

All Google API calls are mocked via `@patch("poc.calendar_client.build")`.

---

## 13. Future Work

The following items are planned for subsequent iterations:

### 13.1 Calendar Sync Clients

- ~~**Google Calendar sync** — API client to fetch events, map to
  `Event` model, UPSERT into database, resolve attendees to contacts.~~
  **Done.** See [Google Calendar Sync](#16-google-calendar-sync).
- **Outlook/Exchange sync** — Microsoft Graph API client.
- **Apple Calendar sync** — CalDAV or EventKit bridge.
- **.ics import** — parse iCalendar files and bulk-import events.

### 13.2 Web UI

- ~~**Events browser** — list/filter events by type, date range,
  contact, company.~~ **Done.**
- ~~**Event detail page** — show event details, participants, linked
  conversations.~~ **Done.**
- ~~**Create/edit forms** — manual event creation with participant
  selection.~~ **Done** (create form; edit and participant selection
  are future work).
- **Calendar view** — month/week/day calendar visualization.
- ~~**Dashboard integration** — "upcoming events" widget on the
  dashboard.~~ **Done** (events count on dashboard).

### 13.3 Birthday Auto-Generation

- Scan contacts for birthday data (from Google People API or manual
  entry) and auto-create recurring birthday events with
  `source='inferred'`.

### 13.4 Reminders & Notifications

- Reminder scheduling per event (e.g., "remind me 1 day before").
- Notification delivery via the existing `alerts` infrastructure.

### 13.5 Event-Based Relationship Inference

- Meeting co-attendance as a signal for relationship inference,
  complementing the existing email co-occurrence engine.

### 13.6 CRUD API Surface

- `create_event()`, `update_event()`, `delete_event()`
- `add_event_participant()`, `remove_event_participant()`
- `link_event_conversation()`, `unlink_event_conversation()`
- `list_events()` with filters (type, date range, contact, company)
- `get_events_for_contact()`, `get_events_for_company()`
- `get_upcoming_events()` with RRULE expansion

---

## 14. Web UI

The events web UI was added following the existing patterns used by
contacts, companies, and relationships.

### Routes (`poc/web/routes/events.py`)

| Method | Path | Description |
|---|---|---|
| GET | `/events` | List page with search, type filter, pagination (50/page) |
| GET | `/events/search` | HTMX partial returning `_rows.html` |
| POST | `/events/sync` | Sync Google Calendar events for the current user's accounts |
| POST | `/events` | Create a new event (redirects to detail page) |
| GET | `/events/{event_id}` | Detail page (info sidebar, participants, linked conversations) |
| DELETE | `/events/{event_id}` | Delete an event and its participant/conversation links |

### Templates (`poc/web/templates/events/`)

| Template | Description |
|---|---|
| `list.html` | 2-column grid: search/filter/results + "New Event" form |
| `_rows.html` | Table partial with title, type, date, location, status, source, delete button |
| `detail.html` | Grid layout: participants + linked conversations (left), event info sidebar (right) |
| `_form.html` | Create form with title, type, datetime, location, description, recurrence, status |

### Features

- **Search** — filters events by title or location (HTMX live search
  with 300ms debounce).
- **Type filter** — dropdown to filter by event type (meeting,
  birthday, anniversary, conference, deadline, other).
- **Pagination** — 50 events per page with previous/next navigation.
- **Create form** — creates events with `source='manual'`.  Supports
  all-day toggle, recurrence type, and status selection.
- **Detail page** — shows event metadata in a sidebar, participants
  with entity links and roles, and linked conversations.
- **Sync Events** — button in the list header triggers Google Calendar
  sync for the current user's accounts.  Spinner shown during sync,
  results displayed as a summary.  Event list auto-refreshes via HTMX
  `refreshEvents` trigger.
- **Delete** — HTMX delete with confirmation dialog.
- **Dashboard** — events count card added to the dashboard.
- **Navigation** — "Events" link added to the global nav bar.

### Test Coverage

10 tests in `tests/test_web.py::TestEvents`:

| Test | Coverage |
|---|---|
| `test_list_loads` | GET /events returns 200 |
| `test_list_shows_events` | Inserted events appear in list |
| `test_search_events` | Search filter works |
| `test_type_filter` | Event type filter works |
| `test_create_event` | POST /events creates and redirects |
| `test_detail_page` | GET /events/{id} shows event info |
| `test_detail_not_found` | 404 for missing event |
| `test_detail_shows_participants` | Participants appear on detail |
| `test_detail_shows_conversations` | Linked conversations appear |
| `test_delete_event` | DELETE removes event |

---

## 15. Design Decisions

### Why a simple `event_type` text column instead of an `event_types` table?

Event types don't have the complexity of relationship types (no
directionality, no bidirectional semantics, no forward/reverse labels).
A CHECK constraint enforces valid values at the database level. If
custom types become necessary, the CHECK constraint can be dropped and
replaced with an FK to a types table in a future migration.

### Why both `recurrence_rule` (RRULE) and `recurrence_type` (enum)?

RRULE provides lossless fidelity with calendar providers — Google
Calendar exports can be imported and re-exported without information
loss.  But querying "show all yearly recurring events" requires
parsing every RRULE string.  The denormalized `recurrence_type` column
enables simple SQL filtering for common patterns.  The two are
complementary: RRULE for precision, `recurrence_type` for queryability.

### Why separate `start_date` / `start_datetime` columns instead of one?

All-day events (birthdays, anniversaries, multi-day conferences) have
dates but not times.  Timed events (meetings) have datetimes.  Mixing
both into a single column would require parsing to distinguish
`2026-03-15` from `2026-03-15T09:00:00-05:00`.  Separate columns make
the distinction explicit and enable type-appropriate indexing.

### Why `ON DELETE SET NULL` for `recurring_event_id` instead of CASCADE?

Deleting a recurring series should not destroy all its modified
instances.  A user may want to delete the recurring pattern while
preserving records of meetings that actually occurred.  SET NULL
converts orphaned instances into standalone events.

### Why reuse `provider_accounts` instead of a new `calendar_sources` table?

The `provider_accounts` table already has `account_type` (supporting
`'email'` and `'calendar'`), OAuth token management, and sync state
tracking.  A new table would duplicate this infrastructure.  Calendar
accounts can coexist with email accounts under the same provider.

### Why `entity_type` / `entity_id` polymorphism instead of separate `contact_id` / `company_id` FKs?

This is the same pattern used in the `relationships` table.
Polymorphic entity references are more extensible (new entity types
don't require schema changes) and keep the join table compact.  The
CHECK constraint ensures only valid entity types are used.

### Why are participant roles free-text instead of a CHECK constraint?

Different providers use different role vocabularies.  Google Calendar
has `organizer`, `attendee`, `optional`.  Outlook has `required`,
`optional`, `resource`.  CRM-specific roles like `honoree`, `host`,
and `speaker` are conventions, not provider values.  A CHECK constraint
would break on new provider imports.

### Why no foreign key enforcement on `entity_id` in `event_participants`?

The `entity_id` can reference either `contacts(id)` or
`companies(id)` depending on `entity_type`.  SQLite does not support
conditional FK constraints.  Application-layer validation ensures
referential integrity.  This is the same tradeoff made in the
`relationships` table.

### Why `UNIQUE(account_id, provider_event_id)` allows NULL account_id?

SQLite treats each NULL as distinct for UNIQUE constraints.  This
means manual events (where `account_id` is NULL and
`provider_event_id` is NULL) can coexist without violating the
constraint.  Only synced events (with non-NULL values for both
columns) are subject to uniqueness checking.

---

## 16. Google Calendar Sync

**Status:** Implemented (2026-02-12)

Google Calendar sync pulls events from the user's connected Google
accounts into the CRM, matching attendees to existing contacts and
supporting both initial backfill and incremental updates.

### 16.1 Architecture Overview

The sync pipeline has four layers:

```
User clicks "Sync Events"
    → POST /events/sync (web route)
        → sync_all_calendars() (orchestration)
            → sync_calendar_events() per calendar
                → fetch_events() (Google Calendar API client)
                → _upsert_event() (database)
                → _match_attendees() (contact resolution)
```

### 16.2 Google Cloud Console Setup

The Calendar API must be enabled in Google Cloud Console before sync
will work.  This is in addition to the Gmail API and People API that
are already required for email and contact sync.

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Select the project used for CRMExtender OAuth credentials
3. Navigate to **APIs & Services > Library**
4. Search for **Google Calendar API**
5. Click **Enable**

The same OAuth client (`credentials/client_secret.json`) is used for
all three APIs.  No additional credentials are needed.

After enabling the API, existing accounts must re-authorize to grant
the new `calendar.readonly` scope:

```bash
python3 -m poc reauth user@example.com
```

This deletes the existing token and opens a browser for fresh OAuth
consent.  The user must approve the new Calendar scope.

### 16.3 OAuth Scopes

The application requests three Google OAuth scopes:

| Scope | Purpose |
|---|---|
| `gmail.readonly` | Email sync |
| `contacts.readonly` | Contact sync |
| `calendar.readonly` | Calendar event sync |

All three are defined in `poc/config.py` as `GOOGLE_SCOPES`.  Adding
`calendar.readonly` to existing tokens requires re-authorization via
the `reauth` CLI command.

### 16.4 Calendar API Client (`poc/calendar_client.py`)

Wrapper around the Google Calendar API v3, following the same patterns
as `poc/contacts_client.py` and `poc/gmail_client.py`.

#### Functions

**`list_calendars(creds, *, rate_limiter=None) -> list[dict]`**

Fetches the user's calendar list via `calendarList().list()` with
pagination.  Returns a list of dicts:

```python
{"id": "primary", "summary": "My Calendar", "primary": True,
 "accessRole": "owner", "backgroundColor": "#4285f4"}
```

**`fetch_events(creds, calendar_id, *, time_min=None, sync_token=None, rate_limiter=None) -> tuple[list[dict], str | None]`**

Fetches events from a single calendar with pagination.  Two modes:

- **Initial sync** — pass `time_min` (ISO timestamp).  Fetches all
  events from that date forward.  Uses `singleEvents=True` to expand
  recurring events into individual instances.
- **Incremental sync** — pass `sync_token` (opaque string from
  previous sync).  Fetches only changes since last sync.

Returns `(parsed_events, next_sync_token)`.

**`_parse_google_event(raw) -> dict`**

Maps a raw Google Calendar API event dict to the internal format:

| Google Field | Internal Field |
|---|---|
| `id` | `provider_event_id` |
| `summary` | `title` (default: `"(no title)"`) |
| `description` | `description` |
| `start.dateTime` | `start_datetime`, `is_all_day = 0` |
| `start.date` | `start_date`, `is_all_day = 1` |
| `end.dateTime` | `end_datetime` |
| `end.date` | `end_date` |
| `location` | `location` |
| `status` | `status` |
| `attendees` | list of `{email, displayName, organizer, responseStatus}` |

All parsed events have `event_type = "meeting"` and
`source = "google_calendar"`.

#### Error Types

- **`CalendarScopeError`** — raised when credentials lack the
  `calendar.readonly` scope.  Detected by checking
  `creds.scopes` before making API calls.  The error message
  directs users to run `python3 -m poc reauth EMAIL`.
- **`SyncTokenExpiredError`** — raised when the Google API returns
  HTTP 410 (Gone), meaning the sync token is no longer valid.
  The caller should discard the token and do a full re-sync.

### 16.5 Sync Orchestration (`poc/calendar_sync.py`)

#### `sync_calendar_events(account_id, creds, calendar_id, *, rate_limiter, customer_id, user_id) -> dict`

Syncs events from a single calendar:

1. **Load sync token** from settings table (key:
   `cal_sync_token_{account_id}_{calendar_id}`, scope: user).
2. **Fetch events**:
   - If no token: initial sync with `time_min = now - 90 days`
     (configurable via `config.CALENDAR_SYNC_DAYS`).
   - If token exists: incremental sync.  On `SyncTokenExpiredError`,
     falls back to full sync.
3. **Upsert events** — for each parsed event, insert or update via
   `_upsert_event()`.  Existing events matched by
   `(account_id, provider_event_id)`.
4. **Match attendees** — for created/updated events with attendees,
   resolve email addresses to CRM contacts and insert
   `event_participants` rows.
5. **Save sync token** — persist the new sync token to settings.

Returns stats:

```python
{"events_created": 5, "events_updated": 2,
 "events_cancelled": 1, "attendees_matched": 8}
```

#### `sync_all_calendars(account_id, creds, *, rate_limiter, customer_id, user_id) -> dict`

Reads the user's selected calendars from settings
(`cal_sync_calendars_{account_id}`, JSON list) and calls
`sync_calendar_events()` for each.  Returns aggregate totals with
`calendars_synced` count and any `errors` list.

#### `_upsert_event(conn, event, account_id, calendar_id, *, customer_id, user_id, now)`

Checks if an event already exists by `(account_id, provider_event_id)`.
If yes, updates all mutable fields (title, description, times,
location, status).  If no, inserts a new row with a generated UUID.
Returns `"created"` or `"updated"`.

#### `_match_attendees(conn, event_id, attendees, customer_id) -> int`

For each attendee:

1. Look up `contact_identifiers` where `type = 'email'` and
   `value = attendee_email` (lowercased), filtered by `customer_id`.
2. If a match is found, insert into `event_participants`:
   - `entity_type = 'contact'`
   - `role = 'organizer'` if the attendee is the organizer, else
     `'attendee'`
   - `rsvp_status` mapped from Google's values:

     | Google `responseStatus` | CRM `rsvp_status` |
     |---|---|
     | `accepted` | `accepted` |
     | `declined` | `declined` |
     | `tentative` | `tentative` |
     | `needsAction` | `needs_action` |

3. Uses `INSERT OR IGNORE` to avoid duplicates (composite PK on
   `event_participants`).

Existing auto-matched participants are cleared before re-matching
(`DELETE FROM event_participants WHERE event_id = ? AND
entity_type = 'contact'`).

### 16.6 Sync Token Lifecycle

Sync tokens are the key to efficient incremental sync:

1. **Initial sync** — no token exists.  All events from the past 90
   days are fetched.  Google returns a `nextSyncToken` with the
   response.
2. **Save token** — stored in the `settings` table:
   `set_setting(cid, "cal_sync_token_{acct}_{cal}", token, scope="user", user_id=uid)`.
3. **Incremental sync** — pass the saved token to
   `fetch_events(sync_token=...)`.  Google returns only events that
   changed since the token was issued, plus a new token.
4. **Token expiry** — Google may invalidate old tokens (HTTP 410).
   The client catches `SyncTokenExpiredError`, discards the token,
   and falls back to a full initial sync.

### 16.7 Calendar Selection Settings UI

Users choose which calendars to sync via **Settings > Calendars**.

#### Routes (`poc/web/routes/settings_routes.py`)

| Method | Path | Description |
|---|---|---|
| GET | `/settings/calendars` | Calendar selection page listing user's Google accounts |
| POST | `/settings/calendars/{account_id}/fetch` | HTMX partial: load available calendars for an account |
| POST | `/settings/calendars/{account_id}/save` | Save selected calendar IDs |

#### Templates

| Template | Description |
|---|---|
| `settings/calendars.html` | Per-account articles with "Load Calendars" HTMX button |
| `settings/_calendar_list.html` | HTMX partial with checkboxes for each calendar, Save button |

Calendar selections are stored as JSON in the settings table:
`cal_sync_calendars_{account_id}` (scope: user).

#### Settings Nav

The "Calendars" tab appears in `settings/_nav.html` between Profile
and the admin-only tabs.  It is visible to all users (not
admin-restricted).

### 16.8 Events Sync Route

**`POST /events/sync`** (`poc/web/routes/events.py`)

Triggered by the "Sync Events" button on the Events list page:

1. Gets the current user's Google provider accounts via
   `user_provider_accounts` join.
2. For each account, loads credentials and calls
   `sync_all_calendars()`.
3. Returns an HTML summary showing counts (events created/updated,
   attendees matched, calendars synced) or error messages.
4. Sets the `HX-Trigger: refreshEvents` response header, which
   causes the event list `#results` div to auto-refresh via
   `hx-trigger="refreshEvents from:body"`.

### 16.9 CLI Commands

#### `reauth`

```bash
python3 -m poc reauth user@example.com
```

Forces re-authorization of a Google account to pick up new OAuth
scopes (e.g., `calendar.readonly`).  Deletes the existing token file
and runs a fresh browser-based OAuth flow.  The new token is saved to
the same per-account path.

### 16.10 Configuration

| Constant | Value | Location | Description |
|---|---|---|---|
| `GOOGLE_SCOPES` | `[gmail.readonly, contacts.readonly, calendar.readonly]` | `poc/config.py` | OAuth scopes requested during authorization |
| `CALENDAR_SYNC_DAYS` | `90` | `poc/config.py` | Number of days to backfill on initial sync |

### 16.11 Files

| File | Purpose |
|---|---|
| `poc/calendar_client.py` | Google Calendar API v3 wrapper |
| `poc/calendar_sync.py` | Sync orchestration, upsert, attendee matching |
| `poc/web/templates/settings/calendars.html` | Calendar selection settings page |
| `poc/web/templates/settings/_calendar_list.html` | HTMX partial for calendar checkboxes |
| `tests/test_calendar_sync.py` | 28 tests covering the full sync pipeline |

Modified files:

| File | Change |
|---|---|
| `poc/config.py` | Added `calendar.readonly` scope, `CALENDAR_SYNC_DAYS` |
| `poc/auth.py` | Added `reauthorize_account()` |
| `poc/__main__.py` | Added `reauth` CLI command |
| `poc/web/routes/events.py` | Added `POST /events/sync` route |
| `poc/web/routes/settings_routes.py` | Added 3 calendar settings routes |
| `poc/web/templates/events/list.html` | Added sync button + result area |
| `poc/web/templates/settings/_nav.html` | Added "Calendars" tab |

### 16.12 Design Decisions

#### Why reuse Gmail provider accounts instead of separate calendar accounts?

Google OAuth tokens can hold multiple scopes.  Since the user already
has a `provider_accounts` row for their Gmail account, adding
`calendar.readonly` to the same token avoids a second OAuth flow and
a second account row.  The calendar selection is stored per-account
in the settings table.

#### Why `singleEvents=True` instead of storing recurring event parents?

When `singleEvents=True`, Google expands recurring events into
individual instances.  This avoids the complexity of RRULE expansion
at query time and matches how users think about their calendar
(individual meetings, not abstract recurrence patterns).  Each
instance gets its own `provider_event_id` and can be independently
updated or cancelled.

#### Why store sync tokens in the settings table instead of a dedicated column?

Sync tokens are per-user, per-account, per-calendar.  The settings
table already supports scoped key-value storage with user isolation.
A dedicated column would require schema changes and would be less
flexible for multi-calendar support.

#### Why 90 days for initial backfill?

Balances having useful historical context against the API quota cost
of fetching years of events.  The constant `CALENDAR_SYNC_DAYS` in
`config.py` can be adjusted if needed.

#### Why clear and re-match attendees on update?

When an event is updated, the attendee list may have changed.
Rather than computing diffs, the simpler approach is to delete
existing auto-matched participants and re-insert.  `INSERT OR IGNORE`
and the composite PK prevent duplicates.  Manual participant links
(if added in the future) would use a different `entity_type` and
would not be affected.
