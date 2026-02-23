# Event — Entity Base PRD

**Version:** 1.0
**Last Updated:** 2026-02-23
**Status:** Draft
**Product PRD:** [CRMExtender Product PRD]

---

## 1. Entity Definition

### 1.1 Purpose

Event is the calendar and scheduling intelligence layer of CRMExtender. While Communications track asynchronous exchanges and Conversations group them, Events answer "When did people meet, and what context surrounded those meetings?" Events provide the temporal scaffolding connecting calendar activity to relationship intelligence — a meeting produces follow-up emails, a conference introduces new contacts, a birthday reminder sustains a dormant relationship.

Events are first-class relationship signals automatically synced from calendar providers, linked to contacts and companies through the Relation Type framework, correlated with conversation threads, and incorporated into relationship intelligence scoring.

### 1.2 Design Goals

- **System object type** — Full participation in Views, Data Sources, event sourcing, field registry, permissions, and API. Specialized behaviors (attendee resolution, birthday auto-generation) registered with the framework.
- **Two-relation participant model** — Event→Contact and Event→Company as separate system Relation Types with metadata (role, RSVP). Enables automatic View traversal, Data Source JOINs, and Neo4j graph sync.
- **Provider-first sync** — Events flow primarily from Google Calendar (future: Outlook, Apple) through incremental sync with deduplication. Manual creation supplements synced data.
- **Extensible event types** — Six protected system types drive behaviors. Users add custom types that work fully in views and filters.
- **Conversation correlation** — Events link to conversations via system Relation Type, enabling bidirectional navigation.
- **Event-sourced history** — All mutations stored as immutable events for audit and compliance.

### 1.3 Performance Targets

| Metric | Target |
|---|---|
| Event list load (default view, 50 rows) | < 200ms |
| Calendar sync (incremental, single calendar) | < 5s |
| Attendee resolution per event | < 100ms |
| All-participants query | < 50ms |

### 1.4 Core Fields

| Field | Description | Required | Editable | Sortable | Filterable | Valid Values / Rules |
|---|---|---|---|---|---|---|
| ID | Unique identifier. Prefixed ULID with `evt_` prefix. | Yes | System | No | Yes | Prefixed ULID |
| Title | Event name/summary. | Yes | Direct | Yes | Yes | Free text. Default: "(no title)" |
| Description | Detailed description or notes. | No | Direct | No | Yes (search) | Free text |
| Event Type | Categorization. Protected system options + user-defined. | Yes | Direct | Yes | Yes | Select field. Default: meeting. |
| Start Date | Date for all-day events. | Conditional | Direct | Yes | Yes | DATE. Required when is_all_day = true. |
| Start Datetime | Timestamp for timed events. | Conditional | Direct | Yes | Yes | TIMESTAMPTZ. Required when is_all_day = false. |
| End Date | End date for multi-day all-day events. | No | Direct | Yes | Yes | DATE |
| End Datetime | End timestamp for timed events. | No | Direct | Yes | Yes | TIMESTAMPTZ |
| Is All Day | Whether this is an all-day event. | Yes | Direct | No | Yes | Boolean. Default: false. |
| Timezone | IANA timezone identifier. Display-only; datetimes stored as UTC. | No | Direct | No | Yes | e.g., America/New_York |
| Recurrence Rule | iCalendar RFC 5545 RRULE string. | No | Direct | No | No | RRULE string |
| Recurrence Type | Denormalized for querying. System-protected, not user-extensible. | No | System (derived) | No | Yes | `none`, `daily`, `weekly`, `monthly`, `yearly`. Default: none. |
| Recurring Event ID | Self-reference to parent recurring event. | No | System | No | Yes | FK to events(id), ON DELETE SET NULL |
| Location | Free text location, address, or video URL. | No | Direct | No | Yes | Free text |
| Status | Event confirmation status. | Yes | Direct | Yes | Yes | `confirmed`, `tentative`, `cancelled`. Default: confirmed. |
| Source | How event entered the system. System-protected. | No | System | No | Yes | `manual`, `google_calendar`, `outlook`, `apple_calendar`, `import`, `inferred` |
| Provider Event ID | Provider-specific event identifier. | No | System | No | No | Text |
| Provider Calendar ID | Provider-specific calendar identifier. | No | System | No | No | Text |
| Provider Account ID | Which synced account this came from. | No | System | No | Yes | FK to provider_accounts, ON DELETE SET NULL |
| Status (Record) | Record lifecycle. | Yes, defaults to active | System | Yes | Yes | `active`, `archived` |
| Created By | User or system process that created. | Yes | System | No | Yes | Reference to User |
| Created At | Record creation timestamp. | Yes | System | Yes | Yes | Timestamp |
| Updated At | Last modification timestamp. | Yes | System | Yes | Yes | Timestamp |

### 1.5 Registered Behaviors

| Behavior | Trigger | Description |
|---|---|---|
| Attendee resolution | On sync, on manual participant add | Resolve attendee emails to contacts via contact_identifiers. See Participants Sub-PRD. |
| Birthday auto-generation | On contact birthday field update | Auto-create recurring yearly all-day event. See Participants Sub-PRD. |
| Recurrence defaulting | On creation with type birthday/anniversary | Auto-set is_all_day, recurrence_type = yearly, generate RRULE. |
| Co-attendance scoring | On participant change | Update relationship strength scores between co-attendees. See Participants Sub-PRD. |

### 1.6 Field Groups

Event fields organized as Attribute Cards in the Detail Panel:

```
── Event Details ──────────────────────────────────
  Title          | Event Type      | Status

── Scheduling ─────────────────────────────────────
  Start Date/Time | End Date/Time  | All Day
  Timezone        | Recurrence     | Location

── Source & Sync ──────────────────────────────────
  Source          | Provider Account | Provider Event ID
  Provider Calendar ID

── Record Info (system) ───────────────────────────
  Created: Feb 17, 2026 by Sam  |  Updated: Feb 17, 2026
```

---

## 2. Entity Relationships

### 2.1 Contacts (Participation)

**Nature:** Many-to-many, via `events__contacts_participation` junction table
**Ownership:** This entity (Relation Type: `event_contact_participation`)
**Description:** Contacts participate in events with role and RSVP metadata. Synced attendees resolved via email. See Participants Sub-PRD.

### 2.2 Companies (Participation)

**Nature:** Many-to-many, via `events__companies_participation` junction table
**Ownership:** This entity (Relation Type: `event_company_participation`)
**Description:** Companies participate as hosts, sponsors, venues. No RSVP (organization-level concept). See Participants Sub-PRD.

### 2.3 Conversations (Linking)

**Nature:** Many-to-many, via `events__conversations_link` junction table
**Ownership:** This entity (Relation Type: `event_conversations`)
**Description:** Events link to conversations for bidirectional navigation: meeting follow-ups, pre-meeting coordination, conference debriefs.

### 2.4 Recurring Event Parent

**Nature:** Many-to-one, via `recurring_event_id` FK
**Ownership:** This entity (self-reference)
**Description:** Modified instances of recurring events reference their parent. ON DELETE SET NULL preserves instances as standalone events.

### 2.5 Documents

**Nature:** Many-to-many, via Documents universal attachment
**Ownership:** Documents PRD
**Description:** Documents attach to Events (meeting agendas, presentation decks, contracts).

### 2.6 Notes

**Nature:** Many-to-many, via Notes universal attachment
**Ownership:** Notes PRD
**Description:** Notes attach to Events (meeting minutes, action items, observations).

---

## 3. Event Types

### 3.1 System Options

`event_type` is a Select field with six protected system options (`is_system = true`):

| Slug | Display Name | Behaviors |
|---|---|---|
| `meeting` | Meeting | Default type. No special behaviors. |
| `birthday` | Birthday | Recurrence defaulting: auto-set is_all_day, yearly RRULE. |
| `anniversary` | Anniversary | Recurrence defaulting: auto-set is_all_day, yearly RRULE. |
| `conference` | Conference | None. Often multi-day, linked to company host. |
| `deadline` | Deadline | None. Non-task deadline (contract renewal, filing). |
| `other` | Other | Catch-all. |

System slugs are immutable. Display names can be tenant-renamed. Cannot be archived or deleted.

### 3.2 Custom Options

Users add custom event type options through standard Select management. Custom options work fully in Views, filters, Board View grouping, and Data Sources. They do not trigger system behaviors.

Examples: `site_inspection`, `pitch_meeting`, `open_house`, `board_meeting`.

### 3.3 Provider Type Resolution

| Google Calendar eventType | Mapped Event Type |
|---|---|
| `default` (or missing) | `meeting` |
| `birthday` | `birthday` |
| `outOfOffice` | `other` |
| `focusTime` | `other` |
| `workingLocation` | `other` |

Title heuristic fallback: if mapped to `meeting` but title contains "birthday" (case-insensitive), reclassify as `birthday`.

Custom types are never auto-assigned by sync. Users manually reclassify if needed.

---

## 4. Recurrence Model

### 4.1 RRULE (Full Fidelity)

iCalendar RFC 5545 RRULE string for lossless provider import/export:

- `RRULE:FREQ=YEARLY;BYMONTH=3;BYMONTHDAY=15` — Birthday
- `RRULE:FREQ=WEEKLY;BYDAY=MO,WE,FR` — MWF standup
- `RRULE:FREQ=MONTHLY;BYDAY=1TU` — First Tuesday monthly

Parsed by `dateutil.rrule.rrulestr()` for occurrence expansion.

### 4.2 Recurrence Type (Queryable Select)

Denormalized for easy SQL filtering:

| Value | Description |
|---|---|
| `none` | One-time event (default) |
| `daily` | Repeats daily |
| `weekly` | Repeats weekly |
| `monthly` | Repeats monthly |
| `yearly` | Repeats yearly |

System-protected, not user-extensible. Enables `WHERE recurrence_type = 'yearly' AND event_type = 'birthday'` without RRULE parsing.

### 4.3 Recurring Event Instances

- **Parent event:** Has RRULE, recurrence_type set, recurring_event_id = NULL.
- **Modified instance:** recurring_event_id points to parent, recurrence_type = 'none', instance-specific data.
- **Unmodified instances:** NOT stored. Computed at query time by expanding parent's RRULE.
- **Deleting parent:** SET NULL on instances. They survive as standalone events.

### 4.4 Google Calendar singleEvents=True

API called with `singleEvents=True`, expanding recurring events into individual instances. Avoids RRULE expansion complexity. Each instance gets its own provider_event_id.

---

## 5. Conversation Linking

### 5.1 Event→Conversation Relation Type

| Property | Value |
|---|---|
| Slug | `event_conversations` |
| Source | `events` |
| Target | `conversations` |
| Cardinality | Many-to-many |
| Has Metadata | false |
| Neo4j Sync | false |
| Cascade | CASCADE (delete either side removes link) |

### 5.2 Use Cases

- **Meeting follow-up:** Event links to the email thread that followed up on action items.
- **Pre-meeting context:** Calendar invite links to the conversation that arranged the meeting.
- **Conference debrief:** Conference event links to multiple debrief threads.

### 5.3 Future: Automatic Linking

Phase 2: system suggests links based on temporal proximity (conversation starts within 24h after meeting) and participant overlap. User confirms (human-in-the-loop).

---

## 6. Lifecycle

| Status | Description |
|---|---|
| `active` | Normal operating state. Visible in views and search. |
| `archived` | Soft-deleted. Excluded from default queries. Recoverable. |

Event `status` field (`confirmed`, `tentative`, `cancelled`) is orthogonal to record lifecycle.

---

## 7. Key Processes

### KP-1: Calendar Sync Delivers Events

**Trigger:** User initiates sync or scheduled background sync.

**Step 1 — Fetch:** Calendar sync pipeline fetches events from provider (incremental or initial). See Calendar Sync Sub-PRD.

**Step 2 — UPSERT:** Each event inserted or updated via deduplication on (provider_account_id, provider_event_id).

**Step 3 — Attendee resolution:** Email addresses resolved to contacts. Participation relations created. See Participants Sub-PRD.

**Step 4 — Type resolution:** Provider event type mapped to internal type system.

### KP-2: User Creates Event Manually

**Trigger:** User creates event from UI.

**Step 1 — Data entry:** Title, type, dates/times, location, description.

**Step 2 — Recurrence defaulting:** If type is birthday/anniversary, auto-set all-day, yearly recurrence.

**Step 3 — Participants:** User adds contact and company participants manually.

**Step 4 — Entity links:** User optionally links to conversations.

### KP-3: Browsing Events

**Trigger:** User navigates to Events in Entity Bar.

**Step 1 — View loads:** Grid, Calendar, or Timeline view. Default sort: start_datetime descending (upcoming first).

**Step 2 — Filtering:** By event_type, status, source, recurrence_type, date ranges, participant contacts/companies.

**Step 3 — Traversal columns:** "Attendees" column shows participant names via Relation Type traversal.

### KP-4: Viewing Event Detail

**Trigger:** User selects an event.

**Step 1 — Detail panel:** Title, type, dates, location, description in Attribute Cards.

**Step 2 — Participants panel:** Contacts with roles and RSVP. Companies with roles.

**Step 3 — Conversations panel:** Linked conversations with summaries.

**Step 4 — Documents and Notes:** Attached files and meeting notes.

### KP-5: Linking Event to Conversation

**Trigger:** User links from event detail or conversation detail.

**Step 1 — Select target:** User picks conversation (or event, from conversation side).

**Step 2 — Link created:** events__conversations_link row inserted.

**Step 3 — Bidirectional display:** Link visible from both event and conversation detail pages.

---

## 8. Action Catalog

### 8.1 Create Event

**Supports processes:** KP-1, KP-2
**Trigger:** Calendar sync or manual creation.
**Outcome:** Event record with type, dates, participants, entity links.
**Business Rules:** Recurrence defaulting for birthday/anniversary types.

### 8.2 View / Browse Events

**Supports processes:** KP-3, KP-4
**Trigger:** User navigation.
**Outcome:** Grid, Calendar, or Timeline view. Detail panel with participants and conversations.

### 8.3 Edit Event

**Supports processes:** KP-4
**Trigger:** User modifies fields.
**Outcome:** Record updated. Event sourced.

### 8.4 Link Conversation

**Supports processes:** KP-5
**Trigger:** User links event to conversation.
**Outcome:** Relation created. Bidirectional navigation.

### 8.5 Archive / Restore

**Trigger:** User archives or restores.
**Outcome:** Soft-delete or recovery.

### 8.6 Participants & Attendance Intelligence

**Summary:** Two system Relation Types (Event→Contact with role/RSVP, Event→Company with role), attendee resolution from provider email addresses, RSVP mapping, birthday auto-generation behavior, co-attendance scoring feed to engagement engine.
**Sub-PRD:** [event-participants-prd.md]

### 8.7 Calendar Sync Pipeline

**Summary:** Provider account reuse, OAuth scope management, Google Calendar API client, sync orchestration with incremental tokens, UPSERT deduplication, provider field mapping, attendee matching during sync, calendar selection settings, error handling.
**Sub-PRD:** [event-calendar-sync-prd.md]

---

## 9. Open Questions

1. **Cancelled events auto-archive?** When sync sets status = cancelled, should archived_at also be set? Cleaner views vs. losing cancellation pattern visibility.
2. **Unmatched attendees as contact stubs?** Create minimal contact records for unknown attendee emails? Mirrors email sync behavior.
3. **Multi-tenant calendar sharing?** Two users syncing same shared calendar creates duplicate events under different accounts. Cross-account merge detection?
4. **recurrence_type extensibility?** Currently closed set. Should users add custom patterns (biweekly, quarterly)? RRULE handles actual logic.
5. **evt_ prefix registration:** Must be registered in Data Sources prefix registry for global uniqueness.

---

## 10. Design Decisions

### Why system object type?

Automatic participation in Views, Data Sources, event sourcing, field registry, permissions. A standalone table would require hand-building each integration.

### Why two Relation Types instead of polymorphic table?

Custom Objects framework connects specific type pairs. A polymorphic table loses automatic View traversal, Data Source JOINs, Neo4j sync. The UNION convenience VIEW mitigates the "all participants" query cost.

### Why recurring_event_id as FK instead of Relation Type?

Structural plumbing for provider fidelity. One:many, no metadata, not user-navigable. A Relation Type adds unnecessary indirection for sync pipeline.

### Why separate start_date/start_datetime?

All-day events have dates without times. Mixing both in one column requires parsing to distinguish. Separate columns: explicit, type-appropriate indexing, no timezone ambiguity for all-day events.

### Why both RRULE and recurrence_type?

RRULE for lossless provider fidelity. recurrence_type for simple SQL filtering. Complementary.

### Why ON DELETE SET NULL for recurring_event_id?

Deleting a recurring series shouldn't destroy all instances. Modified instances preserve records of meetings that actually occurred.

### Why reuse provider_accounts?

Same OAuth token holds multiple scopes. Adding calendar.readonly to existing Gmail account avoids second OAuth flow and second account row.

### Why singleEvents=True?

Avoids RRULE expansion complexity. Matches how users think about calendars. Each instance gets own provider_event_id.

### Why Select with protected options for event_type?

CHECK constraint would block user-defined types. Select field enables system types (with behaviors) + unlimited custom types (for views/filters).

### Why clear and re-match attendees on sync update?

Avoids complex diff logic. System-created instances cleared; manually-added links preserved via created_by filtering.

### Why 90 days for initial backfill?

Balances historical context with sync speed. Configurable via CALENDAR_SYNC_DAYS.

---

## Related Documents

| Document | Relationship |
|---|---|
| [Event Entity TDD](event-entity-tdd.md) | Technical decisions for event implementation |
| [Participants & Attendance Intelligence Sub-PRD](event-participants-prd.md) | Participant Relation Types, attendee resolution, co-attendance |
| [Calendar Sync Pipeline Sub-PRD](event-calendar-sync-prd.md) | Provider sync, Google Calendar API, deduplication |
| [Custom Objects PRD](custom-objects-prd.md) | Unified object model |
| [Contact Management PRD](contact-management-prd.md) | Contact participant records, contact_identifiers |
| [Company Management PRD](company-management-prd.md) | Company participant records |
| [Conversation Entity Base PRD](conversation-entity-base-prd.md) | Event→Conversation linking |
| [Master Glossary](glossary.md) | Term definitions |
