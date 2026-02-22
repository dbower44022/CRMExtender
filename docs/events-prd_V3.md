# Product Requirements Document: Event Management

## CRMExtender — Calendar Events, Participant Intelligence & Provider Sync

**Version:** 3.0
**Date:** 2026-02-17
**Status:** Draft — Fully reconciled with Custom Objects PRD
**Parent Document:** [CRMExtender PRD v1.1](PRD.md)

> **V3.0 (2026-02-22):**
> Terminology standardization pass: Mojibake encoding cleanup. Cross-PRD links updated to current versions (Custom Objects V2, Views & Grid V5, Contact Management V5). Field groups description updated to reference Attribute Cards and Detail Panel (GUI PRD Section 15.7, Custom Objects PRD Section 11). Master Glossary V3 cross-reference added to glossary section.
>
> **V2.0 Rewrite (2026-02-17):**
> This document is a full rewrite of the Events PRD v1.0 (2026-02-09), which documented the PoC-era SQLite implementation. All content has been reconciled with the [Custom Objects PRD](custom-objects-prd_v2.md) Unified Object Model:
> - Event is a **system object type** (`is_system = true`, prefix `evt_`) in the unified framework. Core fields are protected from deletion; specialized behaviors (attendee resolution, birthday auto-generation, recurrence defaulting) are registered per Custom Objects PRD Section 22.
> - Entity IDs use **prefixed ULIDs** (`evt_` prefix, e.g., `evt_01HX8A...`) per the platform-wide convention (Data Sources PRD, Custom Objects PRD Section 6).
> - Event participants are modeled as **two system Relation Types**: Event→Contact (`event_contact_participation`) and Event→Company (`event_company_participation`), with metadata fields for role and RSVP status. This replaces the PoC-era polymorphic `event_participants` table.
> - Event→Conversation linking is a **system Relation Type** (`event_conversations`), replacing the PoC-era dedicated join table.
> - `event_type` is a **Select field with protected system options**, enabling user-defined event types alongside the six system values.
> - The event store uses a **per-entity-type event table** (`events_events`) per Custom Objects PRD Section 19.
> - `events` is the dedicated **read model table** within the tenant schema, managed through the object type framework.
> - All SQL uses **PostgreSQL** syntax with `TIMESTAMPTZ` timestamps and `DATE` types, replacing the PoC-era SQLite schemas.
> - The PoC implementation details (CLI commands, file paths, test counts, web routes) are preserved in [Appendix A](#appendix-a-poc-implementation-reference) for historical reference.

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Problem Statement](#2-problem-statement)
3. [Goals & Success Metrics](#3-goals--success-metrics)
4. [Event Data Model](#4-event-data-model)
5. [Event Types](#5-event-types)
6. [Recurrence Model](#6-recurrence-model)
7. [Event Participants](#7-event-participants)
8. [Conversation Linking](#8-conversation-linking)
9. [Provider Integration](#9-provider-integration)
10. [Calendar Sync Pipeline](#10-calendar-sync-pipeline)
11. [Event Sourcing & Temporal History](#11-event-sourcing--temporal-history)
12. [Virtual Schema & Data Sources](#12-virtual-schema--data-sources)
13. [API Design](#13-api-design)
14. [Design Decisions](#14-design-decisions)
15. [Phasing & Roadmap](#15-phasing--roadmap)
16. [Dependencies & Related PRDs](#16-dependencies--related-prds)
17. [Open Questions](#17-open-questions)
18. [Future Work](#18-future-work)
19. [Glossary](#19-glossary)
20. [Appendix A: PoC Implementation Reference](#appendix-a-poc-implementation-reference)

---

## 1. Executive Summary

The Event Management subsystem is the calendar and scheduling intelligence layer of CRMExtender. While the Communication subsystem tracks asynchronous exchanges (emails, messages), the Event subsystem answers **"When did people meet, and what context surrounded those meetings?"** Events provide the temporal scaffolding that connects calendar activity to relationship intelligence — a meeting produces follow-up emails, a conference introduces new contacts, and a birthday reminder sustains a dormant relationship.

Unlike traditional CRMs where calendar events are siloed in external tools or treated as flat log entries, CRMExtender treats events as **first-class relationship signals** that are automatically synced from calendar providers, linked to contacts and companies through the Relation Type framework, correlated with conversation threads, and incorporated into relationship intelligence scoring. The system doesn't just record that a meeting happened — it knows who attended, what conversations followed, and how the event fits into the broader relationship timeline.

**Core principles:**

- **System object type** — Event is a system object type (`is_system = true`, prefix `evt_`) in the Custom Objects unified framework. Core fields are protected; specialized behaviors (attendee resolution, birthday auto-generation) are registered. Users can add custom fields to Events through the standard field registry.
- **Two-relation participant model** — Event participants are modeled as two system Relation Types (Event→Contact and Event→Company) with metadata for role and RSVP status. This enables automatic traversal in Views, Data Sources, and Neo4j graph intelligence — meeting co-attendance becomes a relationship signal alongside email co-occurrence.
- **Provider-first sync** — Events flow primarily from external calendar providers (Google Calendar, Outlook, Apple Calendar) through incremental sync with deduplication. Manual event creation supplements synced data. The sync pipeline reuses existing provider account infrastructure.
- **Extensible event types** — Six system event types (meeting, birthday, anniversary, conference, deadline, other) are protected and drive behaviors. Users can add custom types (site inspection, webinar, training) that work fully in views, filters, and data sources.
- **Conversation correlation** — Events link to conversations through a system Relation Type, enabling bidirectional navigation: "what conversations followed this meeting?" and "what meetings are linked to this email thread?"
- **Event-sourced history** — All event mutations are stored as immutable events in `events_events`, enabling full audit trails, point-in-time reconstruction, and compliance support.

**Current state:** The PoC implements the full events data model in SQLite, Google Calendar sync with incremental token-based updates, attendee-to-contact matching, a web UI with list/detail/create views, and 85 tests across the events and calendar sync modules. See [Appendix A](#appendix-a-poc-implementation-reference) for details.

**Relationship to other PRDs:**

- **[Custom Objects PRD](custom-objects-prd_v2.md)** — The Event entity type is a **system object type** in the unified framework. Its table structure, field registry, event sourcing, and relation model are governed by the Custom Objects PRD. This PRD defines the Event-specific behaviors (attendee resolution, birthday auto-generation, recurrence defaulting) that are registered with the object type framework.
- **[Contact Management PRD](contact-management-prd_V5.md)** — Contacts participate in events through the Event→Contact Relation Type. Calendar sync resolves attendee emails to contact records via `contact_identifiers`. Event co-attendance feeds relationship strength scoring alongside email co-occurrence.
- **[Company Management PRD](company-management-prd_V1.md)** — Companies participate in events through the Event→Company Relation Type (conference hosts, sponsors). The Company PRD's dependency table already references Events as a participant entity type.
- **[Communication & Conversation Intelligence PRD](email-conversations-prd.md)** — Events link to conversations through the Event→Conversation Relation Type. Meeting follow-up emails, pre-meeting coordination threads, and conference debrief discussions are correlated with their triggering events.
- **[Data Sources PRD](data-sources-prd_V1.md)** — The Event virtual schema table is derived from the Event object type's field registry. The prefixed entity ID convention (`evt_`) enables automatic entity detection in data source queries.
- **[Views & Grid PRD](views-grid-prd_V5.md)** — Event views, filters, sorts, and inline editing operate on fields defined in the Event field registry. Calendar View and Timeline View types are natural fits for event data.
- **[Permissions & Sharing PRD](permissions-sharing-prd_V2.md)** — Event record access, sync permissions, and calendar integration management follow the standard role-based access model.

---

## 2. Problem Statement

CRMExtender tracks communications (emails, messages) and relationships between contacts and companies, but has limited calendar event intelligence. This creates several gaps:

**No meeting context** — Conversations reference meetings ("as we discussed in our call"), but without structured event records there is no way to know when a meeting occurred, who attended, or what was discussed. The meeting is a ghost in the relationship timeline.

**No life events** — Birthdays and anniversaries are powerful relationship maintenance tools, but they have no native home in the CRM data model. Users who track these in external calendars lose the connection between the reminder and the contact record.

**No cross-channel correlation** — A meeting on Tuesday produces a follow-up email on Wednesday, but without event-conversation linking these appear as unrelated activities. The relationship intelligence system sees the email but misses the meeting that caused it.

**No calendar provider integration** — Users manage calendars in Google Calendar, Outlook, and Apple Calendar. This data is siloed away from CRM context, requiring manual re-entry or losing the intelligence entirely.

**No co-attendance intelligence** — Meeting co-attendance is a strong relationship signal. Two people who meet weekly have a stronger working relationship than two people who exchange monthly emails. Without event data, this signal is invisible to the relationship intelligence engine.

---

## 3. Goals & Success Metrics

### Goals

1. **Calendar event storage** — A first-class `events` table as a system object type that stores meetings, birthdays, anniversaries, conferences, deadlines, and user-defined event types with full timing, location, and recurrence data.
2. **Multi-source import** — Events can be imported from Google Calendar, Outlook/Exchange, Apple Calendar, and .ics files, using the existing `provider_accounts` infrastructure.
3. **Participant intelligence** — Events link to contacts and companies via two system Relation Types with role and RSVP metadata, enabling traversal in Views, Data Sources, and Neo4j graph queries.
4. **Conversation correlation** — Events link to conversations via a system Relation Type, enabling bidirectional "this meeting produced this email thread" navigation.
5. **Recurrence support** — Recurring events store iCalendar RRULE strings for provider fidelity, plus a simple `recurrence_type` Select field for easy querying of common patterns.
6. **Provider deduplication** — The `UNIQUE(provider_account_id, provider_event_id)` constraint prevents duplicate events during repeated syncs.
7. **Extensible event types** — Protected system event types drive behaviors; user-defined types enable domain-specific modeling.
8. **Co-attendance signals** — Event participation data feeds relationship strength scoring, complementing email co-occurrence with in-person/meeting co-attendance signals.

### Non-Goals

- **Task/todo tracking** — Tasks are explicitly out of scope and will be a separate object type in a future iteration.
- **Reminders/notifications** — Reminder scheduling and delivery are deferred to a future version.
- **Recurring event instance materialization** — The system stores RRULE definitions and individual modified instances, but does not auto-generate concrete rows for every occurrence. Instance expansion is an application-layer concern handled at query time.
- **Conflict detection** — No overlapping-event detection or scheduling logic.
- **Calendar write-back** — Events synced from providers are read-only in the CRM. Creating events in the CRM does not push them to external calendars (future work).
- **Video conferencing integration** — Meeting links (Zoom, Teams, Meet) are stored as text in the location field but are not parsed, validated, or used for automatic join functionality.

### Success Metrics

| Metric | Target | Measurement |
|---|---|---|
| Calendar sync adoption | >80% of users with connected Google accounts enable calendar sync | Users with `cal_sync_calendars_{account_id}` settings / total users with Google accounts |
| Attendee match rate | >70% of synced event attendees resolve to existing contacts | `events_contacts_participation` rows / total attendee emails processed |
| Event-conversation linking | >30% of meeting events have at least one linked conversation within 7 days | Events with conversation relation / total meeting events |
| Sync latency | <30 seconds for incremental sync of a single calendar | APM monitoring on sync pipeline |
| Event detail page load | <200ms p95 | APM monitoring on `/events/{id}` |
| Co-attendance score impact | Measurable correlation between meeting frequency and relationship strength score | Analytics: Pearson correlation between co-attendance count and engagement score |

---

## 4. Event Data Model

### 4.1 Object Type Registration

> Event is a **system object type** (`is_system = true`, prefix `evt_`). The `events` table is its dedicated read model table within the tenant schema, managed through the object type framework.

| Property | Value |
|---|---|
| `name` | Event |
| `slug` | `events` |
| `type_prefix` | `evt_` |
| `is_system` | `true` |
| `display_name_field` | `title` |
| `icon` | `calendar` |

### 4.2 Event Record — Read Model Table

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | TEXT | **PK** | Prefixed ULID: `evt_` prefix (e.g., `evt_01HX8A...`). Platform-wide convention. |
| `tenant_id` | TEXT | NOT NULL | Tenant identifier. Denormalized from schema context for cross-schema queries. |
| `title` | TEXT | NOT NULL | Event name/summary. **Display name field** for this object type. |
| `description` | TEXT | | Extended description, notes, or agenda. |
| `event_type` | TEXT | NOT NULL, DEFAULT `'meeting'` | Select field with protected system options. See [Section 5](#5-event-types). |
| `start_date` | DATE | | ISO 8601 date for all-day events (birthdays, anniversaries, multi-day conferences). |
| `start_datetime` | TIMESTAMPTZ | | Full timestamp for timed events (meetings, calls). |
| `end_date` | DATE | | End date for multi-day all-day events. |
| `end_datetime` | TIMESTAMPTZ | | End timestamp for timed events. |
| `is_all_day` | BOOLEAN | DEFAULT false | `true` for all-day events (use `start_date`/`end_date`); `false` for timed events (use `start_datetime`/`end_datetime`). |
| `timezone` | TEXT | | IANA timezone identifier (e.g., `America/New_York`). Stored for display; `start_datetime`/`end_datetime` are UTC. |
| `recurrence_rule` | TEXT | | iCalendar RFC 5545 RRULE string (e.g., `RRULE:FREQ=YEARLY;BYMONTH=3;BYMONTHDAY=15`). |
| `recurrence_type` | TEXT | DEFAULT `'none'` | Select field: `none`, `daily`, `weekly`, `monthly`, `yearly`. Denormalized for easy querying. |
| `recurring_event_id` | TEXT | FK → `events(id)` ON DELETE SET NULL | Self-reference to parent recurring event (for modified instances). See [Section 6.3](#63-recurring-event-instances). |
| `location` | TEXT | | Event location (free text, address, room name, or video meeting URL). |
| `status` | TEXT | NOT NULL, DEFAULT `'confirmed'` | Select field: `confirmed`, `tentative`, `cancelled`. |
| `source` | TEXT | DEFAULT `'manual'` | Select field identifying event origin. See [Section 9.2](#92-source-values). |
| `provider_event_id` | TEXT | | Provider-specific event ID (e.g., Google Calendar event ID). |
| `provider_calendar_id` | TEXT | | Provider-specific calendar ID (e.g., `primary`, shared calendar ID). |
| `provider_account_id` | TEXT | FK → `provider_accounts(id)` ON DELETE SET NULL | Which synced account this came from. |
| `created_at` | TIMESTAMPTZ | NOT NULL | Record creation timestamp. |
| `updated_at` | TIMESTAMPTZ | NOT NULL | Last modification timestamp. |
| `created_by` | TEXT | | User or system process that created this record. |
| `updated_by` | TEXT | | User or system process that last modified this record. |
| `archived_at` | TIMESTAMPTZ | | Timestamp of archival (NULL if active). Universal field per Custom Objects PRD Section 7. |

**Constraints:**

- `UNIQUE(provider_account_id, provider_event_id)` — Prevents duplicate synced events from the same provider account. SQLite treated NULLs as distinct; PostgreSQL does the same, so manual events (NULL/NULL) coexist without violating the constraint.
- `recurring_event_id` FK with `ON DELETE SET NULL` — Deleting a recurring series does not cascade-delete modified instances; they become standalone events.
- `provider_account_id` FK with `ON DELETE SET NULL` — Removing a provider account preserves events but clears the link.

### 4.3 Indexes

```sql
-- Temporal queries
CREATE INDEX idx_events_start_dt      ON events(start_datetime);
CREATE INDEX idx_events_start_date    ON events(start_date);

-- Filter queries
CREATE INDEX idx_events_type          ON events(event_type);
CREATE INDEX idx_events_status        ON events(status);
CREATE INDEX idx_events_source        ON events(source);

-- Provider sync
CREATE INDEX idx_events_provider      ON events(provider_account_id, provider_event_id);
CREATE INDEX idx_events_account       ON events(provider_account_id);

-- Recurrence
CREATE INDEX idx_events_recurring     ON events(recurring_event_id);

-- Soft delete
CREATE INDEX idx_events_archived      ON events(archived_at) WHERE archived_at IS NULL;

-- Tenant isolation
CREATE INDEX idx_events_tenant        ON events(tenant_id);
```

Index rationale:

- `idx_events_start_dt` / `idx_events_start_date` — Powers "upcoming events" and date-range queries. Separate indexes because all-day and timed events use different columns.
- `idx_events_type` — Filters by event type (e.g., "show all birthdays"). Important for Calendar View and Board View grouped by type.
- `idx_events_provider` — Composite index for provider sync dedup lookups (`WHERE provider_account_id = ? AND provider_event_id = ?`).
- `idx_events_archived` — Partial index for the common case: queries that exclude archived records.
- `idx_events_tenant` — Required by schema-per-tenant architecture for cross-schema queries.

### 4.4 Registered Behaviors

Per Custom Objects PRD Section 22, the Event system object type registers the following specialized behaviors:

| Behavior | Trigger | Description |
|---|---|---|
| Attendee resolution | On sync, on manual participant add | Resolve attendee email addresses to existing contact records via `contact_identifiers`. Create `event_contact_participation` relation instances. |
| Birthday auto-generation | On contact birthday field update | When a contact's birthday field is set, auto-create a recurring yearly all-day event with `event_type = 'birthday'`, `source = 'inferred'`, and an `event_contact_participation` link with `role = 'honoree'`. |
| Recurrence defaulting | On creation with type `birthday` or `anniversary` | Auto-set `is_all_day = true`, `recurrence_type = 'yearly'`, and generate appropriate RRULE if not provided. |
| Co-attendance scoring | On participant change | Update relationship strength scores between co-attendees. Feed meeting frequency data to the engagement scoring engine. |

### 4.5 Field Groups

Event fields are organized into Field Groups, each rendered as an Attribute Card in the Detail Panel (GUI PRD Section 15.7, Custom Objects PRD Section 11):

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

## 5. Event Types

### 5.1 Select Field with Protected System Options

`event_type` is a Select field in the Event field registry. It ships with six system options (`is_system = true`) that are protected from deletion and slug changes. Users can add unlimited custom options.

### 5.2 System Options

| Slug | Display Name | Description | Behaviors |
|---|---|---|---|
| `meeting` | Meeting | Scheduled meetings with other people. Default type. 1:1s, team meetings, client calls. | None (default). |
| `birthday` | Birthday | A person's date of birth. Linked to a contact with `role = 'honoree'`. | Recurrence defaulting: auto-set `is_all_day`, `recurrence_type = 'yearly'`, generate RRULE. |
| `anniversary` | Anniversary | Recurring annual milestone: work anniversaries, company founding dates, relationship milestones. | Recurrence defaulting: auto-set `is_all_day`, `recurrence_type = 'yearly'`, generate RRULE. |
| `conference` | Conference | Multi-day conferences or trade shows. Often linked to a company with `role = 'host'`. May span multiple days. | None. |
| `deadline` | Deadline | Non-task deadline date: contract renewals, filing deadlines, subscription expirations. Not a to-do item. | None. |
| `other` | Other | Catch-all for uncategorized events that don't fit system or custom types. | None. |

System option slugs are immutable. Display names can be renamed by tenants (e.g., "Meeting" → "Reunión"). System options cannot be archived or deleted.

### 5.3 Custom Options

Users with appropriate permissions can add custom event type options through the standard Select option management UI (Custom Objects PRD Section 13). Custom options:

- Have user-defined slugs and display names.
- Can be archived (hidden from new event creation but preserved on existing records).
- Can be reordered relative to system options.
- Work fully in Views filters, sorts, Board View grouping, and Data Source queries.
- Do not trigger any system behaviors.

**Examples of user-defined event types:**

| Use Case | Custom Options |
|---|---|
| Sam's gutter business | `site_inspection`, `estimate_walkthrough`, `seasonal_checkup`, `crew_dispatch` |
| Venture capital firm | `pitch_meeting`, `board_meeting`, `due_diligence`, `portfolio_review` |
| Real estate agency | `open_house`, `showing`, `closing`, `inspection` |

### 5.4 Event Type Resolution from Providers

When syncing from calendar providers, the system maps provider event types to the internal type system:

| Google Calendar `eventType` | Mapped Event Type |
|---|---|
| `default` (or missing) | `meeting` |
| `birthday` | `birthday` |
| `outOfOffice` | `other` |
| `focusTime` | `other` |
| `workingLocation` | `other` |

If the resolved type is `meeting` but the title contains "birthday" (case-insensitive), it is reclassified as `birthday` (title heuristic fallback).

Custom event types are never auto-assigned by the sync pipeline. Synced events always receive a system type; users can manually reclassify to custom types.

---

## 6. Recurrence Model

Events support two complementary recurrence representations.

### 6.1 `recurrence_rule` (RRULE)

An iCalendar RFC 5545 RRULE string that encodes the full recurrence pattern. This is the native format used by Google Calendar, Outlook, and Apple Calendar, making import/export lossless.

Examples:

- `RRULE:FREQ=YEARLY;BYMONTH=3;BYMONTHDAY=15` — Birthday on March 15.
- `RRULE:FREQ=WEEKLY;BYDAY=MO,WE,FR` — MWF standup.
- `RRULE:FREQ=MONTHLY;BYDAY=1TU` — First Tuesday of each month.
- `RRULE:FREQ=DAILY;COUNT=5` — Daily for 5 days.

Python's `dateutil.rrule.rrulestr()` can parse these for occurrence expansion at query time.

### 6.2 `recurrence_type` (Simple Select)

A denormalized Select field for easy querying without RRULE parsing:

| Slug | Description |
|---|---|
| `none` | One-time event (default). |
| `daily` | Repeats every day. |
| `weekly` | Repeats every week. |
| `monthly` | Repeats every month. |
| `yearly` | Repeats every year. |

This enables queries like `SELECT * FROM events WHERE recurrence_type = 'yearly' AND event_type = 'birthday'` without application-layer RRULE parsing. The `recurrence_type` options are system-protected and not user-extensible — the set of basic recurrence patterns is closed.

### 6.3 Recurring Event Instances

When a provider (e.g., Google Calendar) modifies a single occurrence of a recurring event, the modified instance is stored as a separate row with `recurring_event_id` pointing to the parent event.

- **Parent event** — Has the RRULE, `recurrence_type` set to the pattern, `recurring_event_id = NULL`.
- **Modified instance** — `recurring_event_id` points to the parent, `recurrence_type = 'none'`, with instance-specific times/title/etc.
- **Unmodified instances** — Are NOT stored as rows. They are computed at query time by expanding the parent's RRULE.
- **Deleting a parent** — Sets `recurring_event_id = NULL` on all instances (`ON DELETE SET NULL`). Instances survive as standalone events.

### 6.4 Google Calendar `singleEvents=True`

When syncing from Google Calendar, the API is called with `singleEvents=True`, which expands recurring events into individual instances. This avoids the complexity of RRULE expansion at query time and matches how users think about their calendar (individual meetings, not abstract recurrence patterns). Each instance gets its own `provider_event_id` and can be independently updated or cancelled.

---

## 7. Event Participants

Event participants are modeled as two system Relation Types within the Custom Objects framework, replacing the PoC-era polymorphic `event_participants` table. This enables automatic traversal in Views, Data Sources, and Neo4j graph intelligence.

### 7.1 Event→Contact Participation

| Property | Value |
|---|---|
| `slug` | `event_contact_participation` |
| `source_object_type` | `events` |
| `target_object_type` | `contacts` |
| `cardinality` | `many_to_many` |
| `directionality` | `bidirectional` |
| `source_field_label` | Attendees |
| `target_field_label` | Events |
| `has_metadata` | `true` |
| `neo4j_sync` | `true` |
| `is_system` | `true` |
| `cascade_behavior` | `cascade` (delete event → remove participation links) |

**Junction table: `events__contacts_participation`**

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | TEXT | **PK** | Relation instance ID (prefixed ULID). |
| `source_id` | TEXT | NOT NULL, FK → `events(id)` ON DELETE CASCADE | The event. |
| `target_id` | TEXT | NOT NULL, FK → `contacts(id)` ON DELETE CASCADE | The contact. |
| `role` | TEXT | DEFAULT `'attendee'` | Participant role. Free-text to accommodate provider vocabularies. See [Section 7.3](#73-participant-roles). |
| `rsvp_status` | TEXT | | RSVP response. See [Section 7.4](#74-rsvp-status). |
| `created_by` | TEXT | FK → `users(id)` ON DELETE SET NULL | |
| `updated_by` | TEXT | FK → `users(id)` ON DELETE SET NULL | |
| `created_at` | TIMESTAMPTZ | NOT NULL | |
| `updated_at` | TIMESTAMPTZ | NOT NULL | |

**Constraints:**

- `UNIQUE(source_id, target_id)` — A contact can participate in an event only once.
- Index on `(source_id)` for "list this event's attendees."
- Index on `(target_id)` for "list this contact's events."

### 7.2 Event→Company Participation

| Property | Value |
|---|---|
| `slug` | `event_company_participation` |
| `source_object_type` | `events` |
| `target_object_type` | `companies` |
| `cardinality` | `many_to_many` |
| `directionality` | `bidirectional` |
| `source_field_label` | Companies |
| `target_field_label` | Events |
| `has_metadata` | `true` |
| `neo4j_sync` | `true` |
| `is_system` | `true` |
| `cascade_behavior` | `cascade` (delete event → remove participation links) |

**Junction table: `events__companies_participation`**

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | TEXT | **PK** | Relation instance ID (prefixed ULID). |
| `source_id` | TEXT | NOT NULL, FK → `events(id)` ON DELETE CASCADE | The event. |
| `target_id` | TEXT | NOT NULL, FK → `companies(id)` ON DELETE CASCADE | The company. |
| `role` | TEXT | DEFAULT `'host'` | Participant role (typically `host`, `sponsor`, `venue`). |
| `created_by` | TEXT | FK → `users(id)` ON DELETE SET NULL | |
| `updated_by` | TEXT | FK → `users(id)` ON DELETE SET NULL | |
| `created_at` | TIMESTAMPTZ | NOT NULL | |
| `updated_at` | TIMESTAMPTZ | NOT NULL | |

**Constraints:**

- `UNIQUE(source_id, target_id)` — A company can participate in an event only once.
- Index on `(source_id)` for "list this event's companies."
- Index on `(target_id)` for "list this company's events."

Note: Company participation does not have `rsvp_status` — RSVP is a person-level concept, not an organization-level one.

### 7.3 Participant Roles

Roles are free-text on both Relation Types, allowing flexibility. Common conventions:

| Role | Usage | Typical Relation |
|---|---|---|
| `attendee` | Default role. A person invited to a meeting. | Event→Contact |
| `organizer` | The person who created/owns the event. | Event→Contact |
| `honoree` | The person whose birthday/anniversary it is. | Event→Contact |
| `speaker` | A presenter at a conference. | Event→Contact |
| `optional` | An optional attendee. | Event→Contact |
| `host` | A company hosting a conference or event. | Event→Company |
| `sponsor` | A company sponsoring an event. | Event→Company |
| `venue` | A company providing the event venue. | Event→Company |

Roles are not enforced by a CHECK constraint, allowing providers to pass through their own role values without breaking sync.

### 7.4 RSVP Status

Maps to the iCalendar `PARTSTAT` parameter. Only present on Event→Contact participation:

| Value | Description |
|---|---|
| `accepted` | Participant confirmed attendance. |
| `declined` | Participant declined. |
| `tentative` | Participant tentatively accepted. |
| `needs_action` | No response yet. |
| NULL | RSVP not applicable or not available. |

### 7.5 All-Participants Convenience View

For the common "who's in this meeting?" query, a PostgreSQL VIEW unions both participant Relation Types:

```sql
CREATE VIEW event_all_participants AS
SELECT
    ecp.source_id  AS event_id,
    'contact'       AS entity_type,
    ecp.target_id   AS entity_id,
    c.first_name || ' ' || c.last_name AS entity_name,
    ecp.role,
    ecp.rsvp_status,
    ecp.created_at
FROM events__contacts_participation ecp
JOIN contacts c ON c.id = ecp.target_id

UNION ALL

SELECT
    ecmp.source_id  AS event_id,
    'company'        AS entity_type,
    ecmp.target_id   AS entity_id,
    cmp.name         AS entity_name,
    ecmp.role,
    NULL             AS rsvp_status,
    ecmp.created_at
FROM events__companies_participation ecmp
JOIN companies cmp ON cmp.id = ecmp.target_id;
```

This view is used by the Event detail page and the sync pipeline's attendee matching. It does not replace the Relation Type tables — it's a read-only convenience layer.

### 7.6 Examples

**Birthday:**

```
events:
  id: evt_01HX8A...
  title: "Alice's Birthday"
  event_type: birthday
  start_date: 1990-03-15
  is_all_day: true
  recurrence_type: yearly
  recurrence_rule: "RRULE:FREQ=YEARLY;BYMONTH=3;BYMONTHDAY=15"
  source: inferred

events__contacts_participation:
  source_id: evt_01HX8A...
  target_id: con_8f3a2b...  (Alice)
  role: honoree
  rsvp_status: NULL
```

**Team meeting:**

```
events:
  id: evt_01HX9B...
  title: "Sprint Planning"
  event_type: meeting
  start_datetime: 2026-02-10T14:00:00Z
  end_datetime: 2026-02-10T15:00:00Z
  timezone: America/New_York
  location: Conference Room A
  status: confirmed

events__contacts_participation:
  - source_id: evt_01HX9B..., target_id: con_8f3a2b... (Alice)
    role: organizer, rsvp_status: accepted
  - source_id: evt_01HX9B..., target_id: con_91bc4d... (Bob)
    role: attendee, rsvp_status: accepted
```

**Conference:**

```
events:
  id: evt_01HXAC...
  title: "CRM Summit 2026"
  event_type: conference
  start_date: 2026-06-01
  end_date: 2026-06-03
  is_all_day: true
  location: Convention Center, Austin TX

events__contacts_participation:
  - source_id: evt_01HXAC..., target_id: con_8f3a2b... (Alice)
    role: speaker, rsvp_status: accepted
  - source_id: evt_01HXAC..., target_id: con_91bc4d... (Bob)
    role: attendee, rsvp_status: accepted

events__companies_participation:
  - source_id: evt_01HXAC..., target_id: cmp_55fg7h... (Acme Corp)
    role: host
```

---

## 8. Conversation Linking

Events link to conversations through a system Relation Type, enabling bidirectional navigation between calendar events and communication threads.

### 8.1 Event→Conversation Relation Type

| Property | Value |
|---|---|
| `slug` | `event_conversations` |
| `source_object_type` | `events` |
| `target_object_type` | `conversations` |
| `cardinality` | `many_to_many` |
| `directionality` | `bidirectional` |
| `source_field_label` | Conversations |
| `target_field_label` | Events |
| `has_metadata` | `false` |
| `neo4j_sync` | `false` |
| `is_system` | `true` |
| `cascade_behavior` | `cascade` |

**Junction table: `events__conversations_link`**

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | TEXT | **PK** | Relation instance ID (prefixed ULID). |
| `source_id` | TEXT | NOT NULL, FK → `events(id)` ON DELETE CASCADE | The event. |
| `target_id` | TEXT | NOT NULL, FK → `conversations(id)` ON DELETE CASCADE | The conversation. |
| `created_by` | TEXT | FK → `users(id)` ON DELETE SET NULL | |
| `created_at` | TIMESTAMPTZ | NOT NULL | |

**Constraints:**

- `UNIQUE(source_id, target_id)` — An event-conversation pair can only be linked once.
- Index on `(source_id)` for "list this event's conversations."
- Index on `(target_id)` for "list this conversation's events" (reverse lookup from conversation detail page).

### 8.2 Use Cases

- **Meeting follow-up** — A meeting event links to the email thread that followed up on action items.
- **Pre-meeting context** — A calendar invite links to the conversation thread that arranged the meeting.
- **Conference debrief** — A conference event links to multiple conversation threads discussing outcomes.

### 8.3 Cascade Behavior

- Deleting an event removes all `events__conversations_link` rows for that event (CASCADE on `source_id`).
- Deleting a conversation removes all `events__conversations_link` rows for that conversation (CASCADE on `target_id`).
- Neither cascade deletes the entity on the other side of the link.

### 8.4 Future: Automatic Linking

Phase 2 will introduce automatic event-conversation linking based on temporal proximity and participant overlap:

- If a conversation thread starts within 24 hours after a meeting, and the conversation participants overlap with the meeting attendees, the system suggests linking them.
- The user confirms or dismisses the suggestion (human-in-the-loop).
- Confirmed links are created as `events__conversations_link` rows with `created_by` set to the confirming user.

---

## 9. Provider Integration

### 9.1 Provider Account Reuse

Events reuse the existing `provider_accounts` table. Google Calendar sync uses the same Gmail provider accounts (`provider = 'gmail'`) with the OAuth scope extended to include `calendar.readonly`. No separate calendar account type is needed — the same OAuth token that grants Gmail and Contacts access also grants Calendar read access after re-authorization.

This means the sync infrastructure requires no new account registration. Existing accounts work once the user re-authorizes to grant the calendar scope.

### 9.2 Source Values

The `source` field is a Select with protected system options identifying where the event originated:

| Slug | Display Name | Description |
|---|---|---|
| `manual` | Manually Created | Created directly by the user in CRMExtender. Default value. |
| `google_calendar` | Google Calendar | Imported from Google Calendar API. |
| `outlook` | Outlook | Imported from Outlook/Exchange (future). |
| `apple_calendar` | Apple Calendar | Imported from Apple Calendar (future). |
| `import` | File Import | Imported from an .ics file. |
| `inferred` | System Generated | Auto-generated from CRM data (e.g., birthday from contact record). |

Source options are system-protected and not user-extensible — the set of event origins is controlled by the platform's integration capabilities.

### 9.3 Deduplication

The `UNIQUE(provider_account_id, provider_event_id)` constraint ensures that re-syncing from a provider does not create duplicate events. The sync client uses an UPSERT pattern:

```sql
INSERT INTO events (id, tenant_id, title, start_datetime, ..., provider_account_id, provider_event_id)
VALUES ($1, $2, $3, $4, ..., $n-1, $n)
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

### 9.4 Provider-Specific Field Mapping

| Field | Google Calendar | Outlook | Apple Calendar |
|---|---|---|---|
| `provider_event_id` | `event.id` | `event.id` | `calendarItemIdentifier` |
| `provider_calendar_id` | `calendarId` (e.g., `primary`) | `calendar.id` | `calendar.calendarIdentifier` |
| `status` | `event.status` | `event.showAs` | `event.status` |
| `recurrence_rule` | `event.recurrence[0]` | `event.recurrence.pattern` | `event.recurrenceRules` |
| `timezone` | `event.start.timeZone` | `event.originalStartTimeZone` | `event.timeZone` |

### 9.5 Google Calendar Field Mapping

Google Calendar API events map to the `events` table as follows:

| Google Calendar Field | Events Column |
|---|---|
| `summary` | `title` (default: `"(no title)"` if missing) |
| `description` | `description` |
| `start.date` (all-day) | `start_date`, `is_all_day = true` |
| `start.dateTime` (timed) | `start_datetime`, `is_all_day = false` |
| `end.date` | `end_date` |
| `end.dateTime` | `end_datetime` |
| `start.timeZone` | `timezone` |
| `location` | `location` |
| `recurrence` | `recurrence_rule` (first element) |
| `status` | `status` (`confirmed`/`tentative`/`cancelled`) |
| `id` | `provider_event_id` |
| `eventType` | `event_type` (see [Section 5.4](#54-event-type-resolution-from-providers)) |
| `attendees[].email` | Resolved to contact via `contact_identifiers`, then inserted into `events__contacts_participation` |
| `attendees[].responseStatus` | `rsvp_status` on the participation relation instance |
| `organizer.email` | Participation relation instance with `role = 'organizer'` |
| `recurringEventId` | `recurring_event_id` (resolved via `provider_event_id` lookup) |

---

## 10. Calendar Sync Pipeline

### 10.1 Architecture Overview

The sync pipeline has four layers:

```
User clicks "Sync Events"
    → POST /api/v1/events/sync (API route)
        → sync_all_calendars() (orchestration)
            → sync_calendar_events() per calendar
                → fetch_events() (Google Calendar API client)
                → upsert_event() (database)
                → match_attendees() (contact resolution + relation creation)
```

### 10.2 Google Cloud Console Setup

The Calendar API must be enabled in Google Cloud Console before sync will work. This is in addition to the Gmail API and People API that are already required for email and contact sync.

1. Go to Google Cloud Console.
2. Select the project used for CRMExtender OAuth credentials.
3. Navigate to **APIs & Services > Library**.
4. Search for **Google Calendar API** and click **Enable**.

The same OAuth client (`credentials/client_secret.json`) is used for all three APIs. No additional credentials are needed.

After enabling the API, existing accounts must re-authorize to grant the new `calendar.readonly` scope.

### 10.3 OAuth Scopes

The application requests three Google OAuth scopes:

| Scope | Purpose |
|---|---|
| `gmail.readonly` | Email sync |
| `contacts.readonly` | Contact sync |
| `calendar.readonly` | Calendar event sync |

Adding `calendar.readonly` to existing tokens requires re-authorization. The system detects missing scopes and prompts the user.

### 10.4 Calendar API Client

Wrapper around the Google Calendar API v3, following the same patterns as the contacts and Gmail clients.

**`list_calendars(creds) → list[dict]`**

Fetches the user's calendar list via `calendarList().list()` with pagination. Returns calendar metadata including ID, name, access role, and primary flag.

**`fetch_events(creds, calendar_id, *, time_min=None, sync_token=None) → tuple[list[dict], str | None]`**

Fetches events from a single calendar with pagination. Two modes:

- **Initial sync** — Pass `time_min` (ISO timestamp). Fetches all events from that date forward. Uses `singleEvents=True` to expand recurring events into individual instances.
- **Incremental sync** — Pass `sync_token` (opaque string from previous sync). Fetches only changes since last sync.

Returns `(parsed_events, next_sync_token)`.

**`_parse_google_event(raw) → dict`**

Maps a raw Google Calendar API event dict to the internal format. Handles all-day vs. timed events, attendee extraction, event type mapping, and title heuristic fallback for birthdays.

**Error types:**

- **`CalendarScopeError`** — Raised when credentials lack the `calendar.readonly` scope. Detected by checking `creds.scopes` before making API calls.
- **`SyncTokenExpiredError`** — Raised when the Google API returns HTTP 410 (Gone), meaning the sync token is no longer valid. The caller discards the token and does a full re-sync.

### 10.5 Sync Orchestration

**`sync_calendar_events(account_id, creds, calendar_id, *, tenant_id, user_id) → dict`**

Syncs events from a single calendar:

1. **Load sync token** from settings table (key: `cal_sync_token_{account_id}_{calendar_id}`, scope: user).
2. **Fetch events**:
   - If no token: initial sync with `time_min = now - 90 days` (configurable via `CALENDAR_SYNC_DAYS`).
   - If token exists: incremental sync. On `SyncTokenExpiredError`, falls back to full sync.
3. **Upsert events** — For each parsed event, insert or update via the UPSERT pattern. Existing events matched by `(provider_account_id, provider_event_id)`.
4. **Match attendees** — For created/updated events with attendees, resolve email addresses to CRM contacts and create `events__contacts_participation` relation instances.
5. **Save sync token** — Persist the new sync token to settings.

Returns stats: `{"events_created": 5, "events_updated": 2, "events_cancelled": 1, "attendees_matched": 8}`.

**`sync_all_calendars(account_id, creds, *, tenant_id, user_id) → dict`**

Reads the user's selected calendars from settings (`cal_sync_calendars_{account_id}`, JSON list) and calls `sync_calendar_events()` for each. Returns aggregate totals with `calendars_synced` count and any `errors` list.

### 10.6 Attendee Resolution

For each attendee in a synced event:

1. Look up `contact_identifiers` where `type = 'email'` and `value = attendee_email` (lowercased), filtered by `tenant_id`.
2. If a match is found, create an `events__contacts_participation` relation instance:
   - `role = 'organizer'` if the attendee is the organizer, else `'attendee'`.
   - `rsvp_status` mapped from Google's values:

     | Google `responseStatus` | CRM `rsvp_status` |
     |---|---|
     | `accepted` | `accepted` |
     | `declined` | `declined` |
     | `tentative` | `tentative` |
     | `needsAction` | `needs_action` |

3. Existing auto-matched participation instances are cleared before re-matching on update. The clearing targets only system-created instances (`created_by = 'system:calendar_sync'`); manually-added participation links are preserved.

### 10.7 Sync Token Lifecycle

Sync tokens are the key to efficient incremental sync:

1. **Initial sync** — No token exists. All events from the past 90 days are fetched. The provider returns a sync token with the response.
2. **Save token** — Stored in the `settings` table: `set_setting(tenant_id, "cal_sync_token_{acct}_{cal}", token, scope="user", user_id=uid)`.
3. **Incremental sync** — Pass the saved token to `fetch_events(sync_token=...)`. The provider returns only events that changed since the token was issued, plus a new token.
4. **Token expiry** — The provider may invalidate old tokens (HTTP 410). The client catches `SyncTokenExpiredError`, discards the token, and falls back to a full initial sync.

### 10.8 Calendar Selection Settings

Users choose which calendars to sync via **Settings > Calendars**.

**API endpoints:**

| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/settings/calendars` | List user's connected calendar accounts and their calendars. |
| POST | `/api/v1/settings/calendars/{account_id}/fetch` | Fetch available calendars for a provider account. |
| POST | `/api/v1/settings/calendars/{account_id}/save` | Save selected calendar IDs for sync. |

Calendar selections are stored as JSON in the settings table: `cal_sync_calendars_{account_id}` (scope: user).

### 10.9 Configuration

| Constant | Value | Description |
|---|---|---|
| `GOOGLE_SCOPES` | `[gmail.readonly, contacts.readonly, calendar.readonly]` | OAuth scopes requested during authorization. |
| `CALENDAR_SYNC_DAYS` | `90` | Number of days to backfill on initial sync. |

---

## 11. Event Sourcing & Temporal History

### 11.1 Event Store

Per Custom Objects PRD Section 19, the Event entity type has a dedicated event table: `events_events`. Every mutation to an event record is stored as an immutable event, enabling full audit trails, point-in-time reconstruction, and compliance support.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | TEXT | **PK** | Event ID (prefixed ULID). |
| `entity_id` | TEXT | NOT NULL | The event this audit event applies to. |
| `event_type` | TEXT | NOT NULL | See event types below. |
| `field_name` | TEXT | | The field that changed (NULL for non-field events). |
| `old_value` | JSONB | | Previous value (NULL for creation). |
| `new_value` | JSONB | | New value (NULL for deletion). |
| `metadata` | JSONB | | Additional context (sync details, provider info, etc.). |
| `actor_id` | TEXT | | User or system process that caused this event. |
| `actor_type` | TEXT | | `'user'`, `'system'`, `'sync'`. |
| `created_at` | TIMESTAMPTZ | NOT NULL | Event timestamp. |

**Event types:**

| Event Type | Description |
|---|---|
| `EventCreated` | New event record created. |
| `FieldUpdated` | A field value changed. |
| `EventArchived` | Event record archived. |
| `EventUnarchived` | Event record restored from archive. |
| `EventSynced` | Event upserted from calendar provider sync (metadata includes provider, calendar ID). |
| `ParticipantAdded` | A contact or company participation relation created. |
| `ParticipantRemoved` | A contact or company participation relation removed. |
| `ConversationLinked` | A conversation linked to this event. |
| `ConversationUnlinked` | A conversation unlinked from this event. |

**Indexes:**

- Index on `(entity_id, created_at)` for per-event audit timeline.
- Index on `(event_type)` for event-type queries.

### 11.2 Point-in-Time Reconstruction

The event stream enables reconstructing any event record's state at any historical timestamp by replaying events from creation up to the target timestamp. For performance, periodic snapshots are stored (per Custom Objects PRD Section 19) to avoid replaying the full event stream for records with long histories.

---

## 12. Virtual Schema & Data Sources

### 12.1 Virtual Table

Per the Data Sources PRD, the Event object type's field registry generates a virtual schema table that users write SQL against:

```sql
-- Virtual schema (what users see)
SELECT evt.id, evt.title, evt.event_type, evt.start_datetime,
       evt.location, evt.status
FROM events evt
WHERE evt.event_type = 'meeting'
  AND evt.start_datetime > NOW() - INTERVAL '30 days'
ORDER BY evt.start_datetime DESC;
```

The `evt_` prefix on IDs enables automatic entity detection — the Data Sources query engine recognizes `evt_01HX8A...` as an Event entity and enables clickable links in result sets.

### 12.2 Relation Traversal

The Event→Contact and Event→Company Relation Types enable JOIN-based traversal in data source queries:

```sql
-- Find contacts who attended the most meetings this quarter
SELECT c.first_name, c.last_name, COUNT(*) as meeting_count
FROM contacts c
JOIN events__contacts_participation ecp ON ecp.target_id = c.id
JOIN events e ON e.id = ecp.source_id
WHERE e.event_type = 'meeting'
  AND e.start_datetime >= '2026-01-01'
GROUP BY c.id, c.first_name, c.last_name
ORDER BY meeting_count DESC;
```

### 12.3 Views Integration

Event fields participate fully in the Views system:

- **Grid View** — Event list with sortable columns for title, type, date, location, status, source.
- **Calendar View** — Month/week/day visualization using `start_datetime`/`start_date` and `end_datetime`/`end_date` fields. Natural fit for Event data.
- **Board View** — Events grouped by `event_type` or `status` columns.
- **Timeline View** — Events plotted on a temporal axis using `start_datetime`.
- **Filters** — All Select fields (event_type, status, source, recurrence_type) support standard filter operators. Date/datetime fields support range filters.
- **Traversal columns** — "Attendees" column traverses Event→Contact relation to show participant names. "Companies" column traverses Event→Company relation.

---

## 13. API Design

### 13.1 Event Record API

Event records use the uniform record CRUD pattern defined in Custom Objects PRD Section 23.4:

| Endpoint | Method | Description |
|---|---|---|
| `/api/v1/events` | GET | List events (paginated, filterable, sortable). |
| `/api/v1/events` | POST | Create an event. |
| `/api/v1/events/{id}` | GET | Get a single event with participants and linked conversations. |
| `/api/v1/events/{id}` | PATCH | Update event fields. |
| `/api/v1/events/{id}/archive` | POST | Archive an event. |
| `/api/v1/events/{id}/unarchive` | POST | Unarchive an event. |

### 13.2 Participant API

Participant management uses the standard relation instance API:

| Endpoint | Method | Description |
|---|---|---|
| `/api/v1/events/{id}/participants` | GET | List all participants (contacts and companies). Uses the `event_all_participants` view. |
| `/api/v1/events/{id}/contacts` | POST | Add a contact participant (creates `events__contacts_participation` instance). |
| `/api/v1/events/{id}/contacts/{contact_id}` | DELETE | Remove a contact participant. |
| `/api/v1/events/{id}/companies` | POST | Add a company participant (creates `events__companies_participation` instance). |
| `/api/v1/events/{id}/companies/{company_id}` | DELETE | Remove a company participant. |

### 13.3 Conversation Linking API

| Endpoint | Method | Description |
|---|---|---|
| `/api/v1/events/{id}/conversations` | GET | List linked conversations. |
| `/api/v1/events/{id}/conversations` | POST | Link a conversation to this event. |
| `/api/v1/events/{id}/conversations/{conversation_id}` | DELETE | Unlink a conversation from this event. |

### 13.4 Sync API

| Endpoint | Method | Description |
|---|---|---|
| `/api/v1/events/sync` | POST | Trigger calendar sync for the current user's connected accounts. Returns sync stats. |

---

## 14. Design Decisions

### Why a system object type instead of a standalone table?

Making Event a system object type in the Custom Objects framework gives it automatic participation in every platform capability: Views, Data Sources, event sourcing, field registry, permissions, audit trails, and the API surface. A standalone table would require hand-building each of these integrations. The marginal cost of fitting Events into the framework is low (it already has the right shape — fields, relations, lifecycle), and the benefit is that every future framework enhancement automatically applies to Events.

### Why two Relation Types for participants instead of one polymorphic table?

The Custom Objects framework's Relation Type model connects specific object type pairs. A polymorphic `entity_type`/`entity_id` table would live outside the framework, losing automatic View traversal, Data Source JOIN support, and Neo4j graph sync. Two Relation Types (Event→Contact and Event→Company) are fully integrated with the framework. The cost — a UNION for the "all participants" query — is mitigated by a convenience VIEW. And practically, the sync pipeline only writes to Event→Contact (email→contact resolution); Event→Company is manual-only and low-volume.

### Why keep `recurring_event_id` as a simple FK instead of a Relation Type?

The recurring event parent→instance link is strictly structural plumbing for calendar provider fidelity. It's one:many, carries no metadata, has no temporal bounds, and is not user-navigable. Company hierarchy, by contrast, is genuinely user-facing (tree views, hierarchy browsing), many:many, temporal, and metadata-rich. A Relation Type adds indirection to what should be a simple column assignment during sync. The FK column is proportional to the complexity and keeps the sync pipeline efficient.

### Why separate `start_date`/`start_datetime` columns instead of one?

All-day events (birthdays, anniversaries, multi-day conferences) have dates but not times. Timed events (meetings) have datetimes. Mixing both into a single column would require parsing to distinguish `2026-03-15` from `2026-03-15T14:00:00Z`. Separate columns make the distinction explicit, enable type-appropriate indexing (DATE vs. TIMESTAMPTZ), and avoid timezone ambiguity for all-day events (a birthday is March 15 everywhere, not March 15 UTC).

### Why both `recurrence_rule` (RRULE) and `recurrence_type` (Select)?

RRULE provides lossless fidelity with calendar providers — Google Calendar exports can be imported and re-exported without information loss. But querying "show all yearly recurring events" requires parsing every RRULE string. The denormalized `recurrence_type` Select field enables simple SQL filtering for common patterns. The two are complementary: RRULE for precision, `recurrence_type` for queryability.

### Why `ON DELETE SET NULL` for `recurring_event_id` instead of CASCADE?

Deleting a recurring series should not destroy all its modified instances. A user may want to delete the recurring pattern while preserving records of meetings that actually occurred. SET NULL converts orphaned instances into standalone events.

### Why reuse `provider_accounts` instead of a new `calendar_sources` table?

The `provider_accounts` table already has account type support, OAuth token management, and sync state tracking. A new table would duplicate this infrastructure. Google OAuth tokens can hold multiple scopes, so adding `calendar.readonly` to the existing Gmail account's token avoids a second OAuth flow and a second account row.

### Why `singleEvents=True` for Google Calendar sync?

When `singleEvents=True`, Google expands recurring events into individual instances. This avoids the complexity of RRULE expansion at query time and matches how users think about their calendar (individual meetings, not abstract recurrence patterns). Each instance gets its own `provider_event_id` and can be independently updated or cancelled.

### Why a Select field with protected options for `event_type` instead of a CHECK constraint?

The Custom Objects framework's core promise is domain fidelity — users can model their specific business domain. A CHECK constraint locks event types to six system values, forcing everything else into `other`. A Select field with protected system options preserves behavior reliability (system behaviors key off immutable slugs) while enabling user-defined types (site_inspection, webinar, board_meeting) that work fully in views, filters, and data sources. This mirrors the pattern for protected system fields on system object types.

### Why clear and re-match attendees on sync update?

When a synced event is updated, the attendee list may have changed. Rather than computing diffs, the simpler approach is to delete existing system-created participation instances (`created_by = 'system:calendar_sync'`) and re-insert. This preserves manually-added participant links while keeping synced participants in sync with the provider. The `UNIQUE(source_id, target_id)` constraint prevents duplicates.

### Why store sync tokens in the settings table?

Sync tokens are per-user, per-account, per-calendar. The settings table already supports scoped key-value storage with user isolation. A dedicated column would require schema changes and would be less flexible for multi-calendar support.

### Why 90 days for initial backfill?

Balances having useful historical context against the API quota cost of fetching years of events. The `CALENDAR_SYNC_DAYS` configuration constant can be adjusted per deployment.

---

## 15. Phasing & Roadmap

### Phase 1 — Core Event Framework (MVP)

**Goal:** Events are a system object type with calendar sync and participant intelligence.

**Scope:**

- Event system object type registration with field registry and protected core fields
- Read model table (`events`) in tenant schema with all system fields
- Event type Select field with six protected system options and user-extensible custom options
- Recurrence model (RRULE + recurrence_type)
- Event→Contact participation Relation Type with role and RSVP metadata
- Event→Company participation Relation Type with role metadata
- Event→Conversation linking Relation Type
- `event_all_participants` convenience VIEW
- Google Calendar sync pipeline (incremental, token-based)
- Attendee resolution (email → contact via `contact_identifiers`)
- Calendar selection settings UI
- Provider deduplication (UPSERT on provider_account_id + provider_event_id)
- Event sourcing (`events_events` audit table)
- Uniform CRUD API
- Events in Views (Grid View, filters, sorts)
- Events in Data Sources (virtual schema, relation traversal)
- Permissions integration (standard role-based access)

**Not in Phase 1:** Birthday auto-generation, automatic event-conversation linking, co-attendance scoring, Outlook/Apple Calendar sync, Calendar View, .ics import.

### Phase 2 — Intelligence & Automation

**Goal:** Events feed relationship intelligence and automate common workflows.

**Scope:**

- Birthday auto-generation behavior (contact birthday → recurring event)
- Co-attendance scoring (meeting frequency as relationship strength signal)
- Automatic event-conversation linking suggestions (temporal proximity + participant overlap)
- Neo4j graph sync for Event→Contact and Event→Company relations
- Calendar View (month/week/day visualization)
- Timeline View for events
- Outlook/Exchange sync (Microsoft Graph API client)
- .ics file import

### Phase 3 — Advanced Calendar

**Goal:** Full calendar intelligence with write-back and multi-provider sync.

**Scope:**

- Apple Calendar sync (CalDAV or EventKit bridge)
- Calendar write-back (CRM events → external calendars)
- Reminder/notification scheduling
- Event-based relationship inference in Neo4j graph queries
- Conflict detection (overlapping events)

---

## 16. Dependencies & Related PRDs

| PRD | Relationship | Dependency Direction |
|---|---|---|
| **[Custom Objects PRD](custom-objects-prd_v2.md)** | Event is a system object type. Table structure, field registry, event sourcing, Select option management, and relation model are governed by Custom Objects. This PRD defines Event-specific behaviors. | **Bidirectional.** Custom Objects provides the entity framework; this PRD defines behaviors. |
| **[Contact Management PRD](contact-management-prd_V5.md)** | Event→Contact participation Relation Type. Attendee resolution uses `contact_identifiers`. Co-attendance feeds engagement scoring. Birthday field on contacts triggers birthday event auto-generation. | **Bidirectional.** Contact PRD provides contact records; this PRD creates participation relations and event records. |
| **[Company Management PRD](company-management-prd_V1.md)** | Event→Company participation Relation Type. Company PRD already lists Events as a dependency in its Section 19. | **Events depend on Company** as a participant entity type. |
| **[Communication & Conversation Intelligence PRD](email-conversations-prd.md)** | Event→Conversation linking Relation Type. Meetings correlate with follow-up emails. | **Bidirectional.** Communication PRD provides conversations; this PRD links events to them. |
| **[Data Sources PRD](data-sources-prd_V1.md)** | Event virtual schema table is derived from the Event field registry. `evt_` prefix enables entity detection. Relation traversal enables cross-entity queries. | **Data Sources depend on Events** for entity definitions. |
| **[Views & Grid PRD](views-grid-prd_V5.md)** | Event views, filters, sorts use fields from the Event field registry. Calendar View and Timeline View are natural fits. | **Views depend on Events** for field definitions. |
| **[Permissions & Sharing PRD](permissions-sharing-prd_V2.md)** | Event record access, calendar sync permissions, integration management. | **Events depend on Permissions** for access control. |

---

## 17. Open Questions

1. **Should cancelled events be auto-archived?** When a Google Calendar event is cancelled, the sync currently sets `status = 'cancelled'`. Should it also set `archived_at` to hide cancelled events from default views? Pro: cleaner default views. Con: loses visibility into meeting cancellation patterns.

2. **Should the system create unmatched attendees as contact stubs?** Currently, if an event attendee's email doesn't match an existing contact, the attendee is skipped. Should the system auto-create a minimal contact record (`source = 'calendar_sync'`, email only) to ensure complete participant data? This mirrors the email sync behavior where unknown senders create contact stubs.

3. **How should multi-tenant calendar sharing work?** If two users in the same tenant both sync the same shared Google Calendar, the `UNIQUE(provider_account_id, provider_event_id)` constraint prevents duplicates per account — but the same event would appear twice under different accounts. Should the system detect and merge cross-account duplicates?

4. **Should `recurrence_type` be user-extensible?** Currently it's a closed set (none, daily, weekly, monthly, yearly). Should users be able to add custom recurrence patterns like `biweekly` or `quarterly`? The RRULE field handles the actual recurrence logic, so the Select field is purely for filtering convenience.

5. **Event type prefix for IDs:** This PRD proposes `evt_`. However, the Data Sources PRD prefix registry does not yet include Events. The prefix must be registered and validated for global uniqueness before implementation.

---

## 18. Future Work

### 18.1 Calendar Write-Back

Create events in CRMExtender and push them to external calendars (Google Calendar, Outlook). Requires upgrading from `calendar.readonly` to `calendar.events` OAuth scope.

### 18.2 Reminders & Notifications

Reminder scheduling per event (e.g., "remind me 1 day before"). Notification delivery via the platform's notification infrastructure.

### 18.3 Event-Based Relationship Inference

Meeting co-attendance as a signal for relationship inference in Neo4j, complementing email co-occurrence. Two contacts who attend 5+ meetings together have a strong inferred relationship even if they never email each other directly.

### 18.4 Smart Event-Conversation Linking

AI-powered automatic linking of events to conversations based on temporal proximity, participant overlap, and content similarity (e.g., meeting title matches email subject line).

### 18.5 Video Conferencing Integration

Parse meeting URLs (Zoom, Teams, Meet) from the location field. Display join buttons on the event detail page. Track meeting duration from conferencing provider APIs.

### 18.6 Calendar Analytics

Dashboards showing meeting time allocation, most-met contacts, busiest days, meeting-to-email ratios, and relationship maintenance gaps (contacts not met in X days).

---

## 19. Glossary

General platform terms (Entity Bar, Detail Panel, Card-Based Architecture, Attribute Card, etc.) are defined in the **[Master Glossary V3](glossary_V3.md)**. The following terms are specific to this subsystem:

| Term | Definition |
|---|---|
| **Event** | A calendar event record (meeting, birthday, conference, etc.) stored as a system object type in the unified framework. |
| **Participant** | A contact or company linked to an event through a Relation Type, with role and optional RSVP metadata. |
| **RRULE** | An iCalendar RFC 5545 recurrence rule string encoding a repeating pattern. |
| **Sync Token** | An opaque string returned by a calendar provider that enables incremental sync (fetching only changes since last sync). |
| **Modified Instance** | A single occurrence of a recurring event that has been individually edited. Stored as a separate event record with `recurring_event_id` pointing to the parent. |
| **Provider Account** | An entry in the `provider_accounts` table representing a connected external service (e.g., a Gmail/Google Calendar account). |
| **UPSERT** | INSERT with ON CONFLICT UPDATE — inserts a new row or updates the existing row if a uniqueness constraint is violated. Used for provider deduplication. |
| **Attendee Resolution** | The process of matching an event attendee's email address to an existing contact record via `contact_identifiers`. |
| **Display Name Field** | The field designated as the record's human-readable title. For Events, this is `title`. |
| **Protected System Option** | A Select field option marked `is_system = true` that cannot be archived, deleted, or have its slug changed. Behaviors key off the slug. |

---

## Appendix A: PoC Implementation Reference

> **Note:** This appendix preserves the implementation details from the Events PRD v1.0 (PoC era) for historical reference. The PoC uses SQLite, direct CRUD (no event sourcing), plain UUIDs (no prefixed IDs), a polymorphic `event_participants` table (not Relation Types), and a monolithic `poc/` codebase. The production architecture described in Sections 1–18 supersedes this implementation.

### A.1 PoC Status

**Implemented (v6 schema, 2026-02-12):**

- SQLite `events` table with all columns, constraints, and CHECK rules.
- SQLite `event_participants` table with polymorphic `entity_type`/`entity_id` pattern.
- SQLite `event_conversations` join table.
- v5→v6 migration script (`poc/migrate_to_v6.py`), idempotent with backup and dry-run.
- `Event` dataclass in `poc/models.py` with `to_row()` and `from_row()` methods.
- Google Calendar sync pipeline: API client, sync orchestration, attendee matching.
- Web UI: list page (search, type filter, pagination), detail page (participants, conversations, sidebar), create form, delete, sync button.
- Dashboard events count card.
- Source icon SVG filter for grid and detail views.
- Calendar selection settings UI (Settings > Calendars).
- `reauth` CLI command for re-authorizing OAuth with new scopes.

### A.2 PoC File Inventory

| File | Purpose |
|---|---|
| `poc/calendar_client.py` | Google Calendar API v3 wrapper |
| `poc/calendar_sync.py` | Sync orchestration, upsert, attendee matching |
| `poc/models.py` | `Event` dataclass |
| `poc/migrate_to_v6.py` | v5→v6 migration script |
| `poc/web/routes/events.py` | Event web routes (list, detail, create, delete, sync) |
| `poc/web/routes/settings_routes.py` | Calendar settings routes |
| `poc/web/templates/events/list.html` | Event list page |
| `poc/web/templates/events/_rows.html` | Event table partial |
| `poc/web/templates/events/detail.html` | Event detail page |
| `poc/web/templates/events/_form.html` | Event create form |
| `poc/web/templates/settings/calendars.html` | Calendar selection settings |
| `poc/web/templates/settings/_calendar_list.html` | Calendar checkboxes partial |
| `poc/web/filters.py` | `source_icon` Jinja filter |
| `poc/config.py` | `GOOGLE_SCOPES`, `CALENDAR_SYNC_DAYS` |
| `poc/auth.py` | `reauthorize_account()` |

### A.3 PoC Test Coverage

85 tests across two test files:

**`tests/test_events.py` — 39 tests:**

| Test Class | Count | Coverage |
|---|---|---|
| `TestEventModel` | 10 | `to_row()` defaults, explicit ID, birthday, timed meeting, provider fields, audit fields, empty-to-None conversion, `from_row()` roundtrip, missing fields, `is_all_day` bool conversion |
| `TestEventsSchema` | 4 | Table existence verification, column verification for all three tables |
| `TestEventsInsert` | 6 | Basic insert, birthday insert, CHECK constraints for `event_type` / `recurrence_type` / `status`, provider uniqueness constraint |
| `TestEventParticipants` | 8 | Contact participant, company participant, RSVP status, RSVP CHECK constraint, entity type CHECK constraint, multiple participants, CASCADE delete, honoree role |
| `TestEventConversations` | 5 | Basic link, multiple conversations per event, multiple events per conversation, CASCADE delete (both directions) |
| `TestRecurringEvents` | 2 | Parent-instance linking, ON DELETE SET NULL behavior |
| `TestMigration` | 4 | Fresh v5 DB migration, idempotency, backup creation, dry-run behavior |

**`tests/test_calendar_sync.py` — 46 tests:**

| Test Class | Count | Coverage |
|---|---|---|
| `TestParseGoogleEvent` | 13 | Timed event, all-day event, cancelled event, no title fallback, attendees, RSVP status mapping, missing ID, description, birthday eventType, birthday from title, outOfOffice mapping, default event type |
| `TestUpsertEvent` | 4 | Create new, update existing, event_type updated on resync, cancelled status |
| `TestMatchAttendees` | 3 | Contact matching via email, unmatched attendee skipped, RSVP status passthrough |
| `TestSyncCalendarEvents` | 4 | Initial sync, incremental sync, sync token persistence, expired token fallback |
| `TestSyncAllCalendars` | 2 | Multi-calendar aggregation, no calendars selected error |
| `TestCalendarSettings` | 4 | Settings page renders, calendar selection save, fetch calendars list, scope error display |
| `TestEventsSyncRoute` | 4 | Sync button rendered, sync endpoint works, no accounts handling, no calendars message |
| `TestSourceIconFilter` | 7 | Google icon, with account name, with account + calendar, primary omitted, manual icon, None defaults, unknown fallback |
| `TestEventsSourceIcon` | 5 | Grid Google icon, grid manual icon, detail Google provenance, detail manual source, detail hides "primary" calendar |

### A.4 PoC CLI Commands

```bash
# Migrate v5 database to v6 (adds events tables)
python3 -m poc migrate-to-v6 [--db PATH] [--dry-run]

# Re-authorize Google account for calendar scope
python3 -m poc reauth user@example.com
```

### A.5 PoC Web Routes

| Method | Path | Description |
|---|---|---|
| GET | `/events` | List page with search, type filter, pagination (50/page) |
| GET | `/events/search` | HTMX partial returning `_rows.html` |
| POST | `/events/sync` | Sync Google Calendar events |
| POST | `/events` | Create a new event (redirects to detail page) |
| GET | `/events/{event_id}` | Detail page |
| DELETE | `/events/{event_id}` | Delete an event |
