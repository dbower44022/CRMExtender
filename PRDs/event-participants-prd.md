# Event — Participants & Attendance Intelligence Sub-PRD

**Version:** 1.0
**Last Updated:** 2026-02-23
**Status:** Draft
**Entity Base PRD:** [event-entity-base-prd.md]
**Referenced Entity PRDs:** [contact-entity-base-prd.md] (contact_identifiers for resolution), [company-entity-base-prd.md] (company participants)

---

## 1. Overview

### 1.1 Purpose

This sub-PRD defines the participant model for events: two system Relation Types (Event→Contact and Event→Company) with role and RSVP metadata, the attendee resolution pipeline that matches provider email addresses to CRM contacts, birthday auto-generation from contact records, and co-attendance scoring that feeds the relationship intelligence engine.

### 1.2 Preconditions

- Event entity operational.
- Contact entity with contact_identifiers table available for email resolution.
- Company entity available for company participation.

---

## 2. Context

### 2.1 Relevant Fields

| Field | Role in This Action |
|---|---|
| role (on participation) | Participant role: attendee, organizer, honoree, speaker, optional (contacts); host, sponsor, venue (companies). Free-text. |
| rsvp_status (on contact participation) | RSVP response: accepted, declined, tentative, needs_action. NULL if N/A. |
| event_type (on Event) | Birthday/anniversary types trigger auto-generation behaviors. |

### 2.2 Cross-Entity Context

- **Contact Entity Base PRD:** contact_identifiers table provides email → contact resolution for attendee matching.
- **Calendar Sync Sub-PRD:** Sync pipeline calls attendee resolution after UPSERT. Provides raw attendee emails and RSVP statuses.
- **Contact Relationship Intelligence Sub-PRD:** Co-attendance data feeds relationship strength scoring alongside email co-occurrence.

---

## 3. Key Processes

### KP-1: Resolve Synced Attendees to Contacts

**Trigger:** Calendar sync delivers an event with attendees.

**Step 1 — Extract attendee list:** Provider event includes email addresses with roles and RSVP.

**Step 2 — Clear existing auto-matched:** Remove participation instances where created_by = 'system:calendar_sync'. Manually-added links preserved.

**Step 3 — Resolve each attendee:** For each attendee email, query contact_identifiers WHERE type = 'email' AND value = lower(email) AND tenant_id = $tenant.

**Step 4a — Match found:** Create events__contacts_participation instance with role and rsvp_status.

**Step 4b — No match:** Attendee skipped (or contact stub created, per open question).

**Step 5 — Organizer handling:** If attendee is the organizer, set role = 'organizer'.

### KP-2: User Adds Participant Manually

**Trigger:** User adds contact or company to event from detail page.

**Step 1 — Select entity:** User searches for contact or company.

**Step 2 — Set role:** User optionally specifies role (defaults: 'attendee' for contacts, 'host' for companies).

**Step 3 — Create relation:** Participation instance created with created_by = current user.

### KP-3: Birthday Auto-Generation

**Trigger:** Contact's birthday field is set or updated.

**Step 1 — Check existing:** Look for existing birthday event linked to this contact with event_type = 'birthday' and source = 'inferred'.

**Step 2a — No existing event:** Create new Event with title = "{Contact Name}'s Birthday", event_type = 'birthday', start_date = birthday, is_all_day = true, recurrence_type = 'yearly', source = 'inferred'. Create participation with role = 'honoree'.

**Step 2b — Existing event:** Update start_date if birthday changed. No duplicate created.

**Step 3 — Birthday removed:** If birthday field cleared, archive the auto-generated event.

### KP-4: Co-Attendance Scoring

**Trigger:** Participant added to or removed from an event.

**Step 1 — Identify co-attendees:** For the changed event, list all contact participants.

**Step 2 — Update pairs:** For each pair of co-attendees, update their relationship strength score based on meeting frequency and recency.

**Step 3 — Feed engine:** Co-attendance data sent to the engagement scoring engine as a relationship signal, complementing email co-occurrence.

---

## 4. Event→Contact Participation Relation Type

**Supports processes:** KP-1, KP-2

### 4.1 Relation Type Definition

| Property | Value |
|---|---|
| Slug | `event_contact_participation` |
| Source | `events` |
| Target | `contacts` |
| Cardinality | Many-to-many |
| Directionality | Bidirectional |
| Source Field Label | Attendees |
| Target Field Label | Events |
| Has Metadata | true (role, rsvp_status) |
| Neo4j Sync | true |
| Cascade | CASCADE (delete event → remove links) |

### 4.2 Participant Roles

Free-text to accommodate provider vocabularies:

| Role | Usage |
|---|---|
| `attendee` | Default. Person invited to meeting. |
| `organizer` | Person who created/owns the event. |
| `honoree` | Person whose birthday/anniversary. |
| `speaker` | Presenter at conference. |
| `optional` | Optional attendee. |

### 4.3 RSVP Status

Maps to iCalendar PARTSTAT:

| Value | Description |
|---|---|
| `accepted` | Confirmed attendance |
| `declined` | Declined |
| `tentative` | Tentatively accepted |
| `needs_action` | No response yet |
| NULL | Not applicable or unavailable |

### 4.4 RSVP Mapping from Google

| Google responseStatus | CRM rsvp_status |
|---|---|
| `accepted` | `accepted` |
| `declined` | `declined` |
| `tentative` | `tentative` |
| `needsAction` | `needs_action` |

**Tasks:**

- [ ] EPAR-01: Implement events__contacts_participation relation type registration
- [ ] EPAR-02: Implement attendee email → contact resolution via contact_identifiers
- [ ] EPAR-03: Implement clear-and-rematch for system-created participation on sync update
- [ ] EPAR-04: Implement organizer detection and role assignment
- [ ] EPAR-05: Implement RSVP status mapping from Google Calendar
- [ ] EPAR-06: Implement manual contact participant add/remove

**Tests:**

- [ ] EPAR-T01: Test attendee email resolves to correct contact
- [ ] EPAR-T02: Test unmatched email skipped (no participation created)
- [ ] EPAR-T03: Test clear-and-rematch preserves manually-added links
- [ ] EPAR-T04: Test organizer gets role = 'organizer'
- [ ] EPAR-T05: Test RSVP mapping from Google values
- [ ] EPAR-T06: Test UNIQUE constraint prevents duplicate participation
- [ ] EPAR-T07: Test CASCADE removes participation when event deleted

---

## 5. Event→Company Participation Relation Type

**Supports processes:** KP-2

### 5.1 Relation Type Definition

| Property | Value |
|---|---|
| Slug | `event_company_participation` |
| Source | `events` |
| Target | `companies` |
| Cardinality | Many-to-many |
| Directionality | Bidirectional |
| Source Field Label | Companies |
| Target Field Label | Events |
| Has Metadata | true (role only, no RSVP) |
| Neo4j Sync | true |
| Cascade | CASCADE |

### 5.2 Company Roles

| Role | Usage |
|---|---|
| `host` | Company hosting a conference or event (default) |
| `sponsor` | Company sponsoring an event |
| `venue` | Company providing event venue |

**Tasks:**

- [ ] EPAR-07: Implement events__companies_participation relation type registration
- [ ] EPAR-08: Implement manual company participant add/remove

**Tests:**

- [ ] EPAR-T08: Test company participation with role = 'host'
- [ ] EPAR-T09: Test CASCADE removes company participation when event deleted

---

## 6. Birthday Auto-Generation

**Supports processes:** KP-3

### 6.1 Requirements

When a contact's birthday field is set, the system auto-creates a recurring yearly all-day event:

- title: "{Contact Name}'s Birthday"
- event_type: birthday
- start_date: the birthday date
- is_all_day: true
- recurrence_type: yearly
- recurrence_rule: RRULE:FREQ=YEARLY;BYMONTH={M};BYMONTHDAY={D}
- source: inferred
- Participation: role = 'honoree'

Update if birthday changes. Archive if birthday cleared. Idempotent — no duplicates.

**Tasks:**

- [ ] EPAR-09: Implement birthday event auto-creation on contact birthday set
- [ ] EPAR-10: Implement birthday event update on birthday change
- [ ] EPAR-11: Implement birthday event archive on birthday clear
- [ ] EPAR-12: Implement idempotency check (no duplicate birthday events)

**Tests:**

- [ ] EPAR-T10: Test birthday set creates recurring yearly event
- [ ] EPAR-T11: Test birthday change updates existing event date
- [ ] EPAR-T12: Test birthday clear archives auto-generated event
- [ ] EPAR-T13: Test no duplicate created on repeated birthday set

---

## 7. Co-Attendance Scoring

**Supports processes:** KP-4

### 7.1 Requirements

Meeting co-attendance is a relationship strength signal alongside email co-occurrence. When participants change on an event:

- Identify all contact pairs who co-attend.
- Update relationship scores based on meeting frequency and recency.
- Two contacts meeting weekly have stronger signal than monthly emailers.

### 7.2 Deferred Details

The scoring algorithm, weight configuration, and integration with the engagement scoring engine are defined in the Contact Relationship Intelligence Sub-PRD. This sub-PRD establishes the product requirement: co-attendance feeds relationship scoring.

**Tasks:**

- [ ] EPAR-13: Implement co-attendance pair identification on participant change
- [ ] EPAR-14: Implement co-attendance signal dispatch to scoring engine

**Tests:**

- [ ] EPAR-T14: Test co-attendance pairs computed correctly for multi-attendee event
- [ ] EPAR-T15: Test scoring signal dispatched on participant add
- [ ] EPAR-T16: Test scoring signal dispatched on participant remove

---

## 8. All-Participants Convenience View

**Supports processes:** KP-1, KP-2

### 8.1 Requirements

The `event_all_participants` PostgreSQL VIEW unions both participation Relation Types for the common "who's in this meeting?" query. Read-only. Used by Event detail page and all-participants API endpoint.

**Tasks:**

- [ ] EPAR-15: Implement event_all_participants VIEW (UNION of contacts + companies)

**Tests:**

- [ ] EPAR-T17: Test VIEW returns both contact and company participants
- [ ] EPAR-T18: Test VIEW shows correct roles and RSVP for contacts
- [ ] EPAR-T19: Test VIEW shows NULL rsvp_status for companies
