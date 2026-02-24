# Project — Entity Relations & Aggregation Sub-PRD

**Version:** 1.0
**Last Updated:** 2026-02-23
**Status:** Draft
**Entity Base PRD:** [project-entity-base-prd.md]

---

## 1. Overview

### 1.1 Purpose

This sub-PRD defines the five system Relation Types that ship with Projects (Conversation, Contact, Company, Event, Note), the entity aggregation behavior that maintains denormalized counts and last_activity_at, the Custom Object Type relation guidance, and the derived participant display concept. Projects are defined by their connections — the relations and aggregation behavior are the substance of what makes a Project useful as an organizational hub.

### 1.2 Preconditions

- Project entity operational with read model table and denormalized count columns.
- Junction tables provisioned (project_conversations, project_contacts, project_companies, project_events).
- Notes and Tasks Universal Attachment operational.
- Entity types operational: Conversation, Contact, Company, Event, Note.

---

## 2. Context

### 2.1 Relevant Fields

| Field | Role in This Action |
|---|---|
| conversation_count | Denormalized count maintained on link/unlink. |
| contact_count | Denormalized count maintained on link/unlink. |
| company_count | Denormalized count maintained on link/unlink. |
| event_count | Denormalized count maintained on link/unlink. |
| note_count | Denormalized count maintained on link/unlink. |
| sub_project_count | Denormalized count maintained on child add/remove. |
| last_activity_at | Most recent activity across all linked entities. |

### 2.2 Cross-Entity Context

- **Conversation Entity Base PRD:** Defines Conversation↔Project Relation Type from the Conversation side. Same junction table (project_conversations), defined once.
- **Note Entity Base PRD:** Notes attach via Universal Attachment (note_entities with entity_type = 'projects'). No project-specific junction.
- **Task Entity Base PRD:** Tasks attach via Universal Attachment (task_entities with entity_type = 'projects').

---

## 3. Key Processes

### KP-1: Linking an Entity to a Project

**Trigger:** User adds a conversation, contact, company, or event to a project.

**Step 1 — Select entity:** User searches for the entity to link.

**Step 2 — Metadata (if applicable):** For contacts and companies, optionally set role and notes.

**Step 3 — Create link:** Insert junction table row.

**Step 4 — Update count:** Increment the corresponding denormalized count.

**Step 5 — Update last activity:** Recompute last_activity_at if the linked entity's most recent activity is newer.

**Step 6 — Event sourcing:** Emit EntityLinked event (ConversationLinked, ContactLinked, etc.).

### KP-2: Unlinking an Entity from a Project

**Trigger:** User removes an entity link.

**Step 1 — Remove link:** Delete junction table row.

**Step 2 — Update count:** Decrement the corresponding denormalized count.

**Step 3 — Recompute last activity:** May need to recalculate last_activity_at if the removed entity was the most recent.

**Step 4 — Event sourcing:** Emit EntityUnlinked event.

### KP-3: Entity Aggregation on External Activity

**Trigger:** Activity occurs on a linked entity (new communication in linked conversation, event completed, note added).

**Step 1 — Identify projects:** Find all projects linked to the entity.

**Step 2 — Update last_activity_at:** Set to MAX of current last_activity_at and the new activity timestamp.

---

## 4. System Relation Types

**Supports processes:** KP-1, KP-2

### 4.1 Project ↔ Conversation

| Property | Value |
|---|---|
| Slug | `project_conversations` |
| Source | Project (`prj_`) |
| Target | Conversation (`cvr_`) |
| Cardinality | Many-to-many |
| Cascade | No cascade — conversations persist independently |
| Metadata | None |
| Neo4j Sync | true |

Both standard and aggregate Conversations can associate. No restriction on is_aggregate value. No inheritance — aggregate's children don't auto-inherit project association.

### 4.2 Project ↔ Contact

| Property | Value |
|---|---|
| Slug | `project_contacts` |
| Source | Project (`prj_`) |
| Target | Contact (`con_`) |
| Cardinality | Many-to-many |
| Cascade | No cascade |
| Metadata | role (Text, optional), notes (Text, optional) |
| Neo4j Sync | true |

Explicit, user-curated associations independent of communication participation. Role enables stakeholder classification (decision-maker, vendor, advisor). Notes provide context about involvement.

### 4.3 Project ↔ Company

| Property | Value |
|---|---|
| Slug | `project_companies` |
| Source | Project (`prj_`) |
| Target | Company (`cmp_`) |
| Cardinality | Many-to-many |
| Cascade | No cascade |
| Metadata | role (Text, optional), notes (Text, optional) |
| Neo4j Sync | true |

Same pattern as Contact with role/notes metadata.

### 4.4 Project ↔ Event

| Property | Value |
|---|---|
| Slug | `project_events` |
| Source | Project (`prj_`) |
| Target | Event (`evt_`) |
| Cardinality | Many-to-many |
| Cascade | No cascade |
| Metadata | None |
| Neo4j Sync | true |

### 4.5 Project ↔ Note (via Universal Attachment)

Notes attach through their own universal attachment (note_entities junction with entity_type = 'projects'). No dedicated project junction table. The Notes PRD's note_entities table handles the link. note_count on projects is maintained by the entity aggregation behavior reacting to NoteAttached/NoteDetached events.

### 4.6 Custom Object Type Relations

Custom Object Types (Jobs, Properties, Estimates, etc.) are user-created. They do NOT have pre-defined system Relation Types to Projects. Users create these through the Custom Objects relation framework during object type definition. The setup UX surfaces relationship definition, making it easy to establish Project ↔ Custom Object relations at creation time.

**Tasks:**

- [ ] PREA-01: Register project_conversations system Relation Type
- [ ] PREA-02: Register project_contacts system Relation Type (with role/notes metadata)
- [ ] PREA-03: Register project_companies system Relation Type (with role/notes metadata)
- [ ] PREA-04: Register project_events system Relation Type
- [ ] PREA-05: Implement conversation link/unlink with count update
- [ ] PREA-06: Implement contact link/unlink with role/notes metadata
- [ ] PREA-07: Implement contact role/notes update
- [ ] PREA-08: Implement company link/unlink with role/notes metadata
- [ ] PREA-09: Implement event link/unlink with count update
- [ ] PREA-10: Implement note count tracking via Universal Attachment events
- [ ] PREA-11: Implement sub-project count tracking on child add/remove
- [ ] PREA-12: Implement cascade archive for sub-projects (recursive)

**Tests:**

- [ ] PREA-T01: Test conversation linked increments conversation_count
- [ ] PREA-T02: Test conversation unlinked decrements conversation_count
- [ ] PREA-T03: Test contact linked with role/notes metadata stored
- [ ] PREA-T04: Test contact role/notes updatable after link
- [ ] PREA-T05: Test company linked increments company_count
- [ ] PREA-T06: Test event linked increments event_count
- [ ] PREA-T07: Test note attachment increments note_count
- [ ] PREA-T08: Test sub-project creation increments parent sub_project_count
- [ ] PREA-T09: Test duplicate link prevented (UNIQUE constraint)
- [ ] PREA-T10: Test CASCADE removes links when project archived/deleted
- [ ] PREA-T11: Test CASCADE removes links when linked entity deleted
- [ ] PREA-T12: Test cascade archive propagates to all descendants

---

## 5. Entity Aggregation Behavior

**Supports processes:** KP-1, KP-2, KP-3

### 5.1 Count Maintenance

On every link/unlink event, the aggregation behavior updates the corresponding denormalized count:

| Event | Count Field | Action |
|---|---|---|
| ConversationLinked | conversation_count | +1 |
| ConversationUnlinked | conversation_count | -1 |
| ContactLinked | contact_count | +1 |
| ContactUnlinked | contact_count | -1 |
| CompanyLinked | company_count | +1 |
| CompanyUnlinked | company_count | -1 |
| EventLinked | event_count | +1 |
| EventUnlinked | event_count | -1 |
| NoteAttached | note_count | +1 |
| NoteDetached | note_count | -1 |
| SubProjectAdded | sub_project_count | +1 |
| SubProjectRemoved | sub_project_count | -1 |

### 5.2 Last Activity Computation

`last_activity_at` represents the most recent activity across all linked entities. Updated when:
- New communication arrives in a linked conversation
- Linked event starts or ends
- Note attached or updated on the project
- Task status changes on a linked task

Implementation: On relevant events, set `last_activity_at = GREATEST(last_activity_at, $event_timestamp)`. On entity unlink, recompute from remaining linked entities if the removed entity was the most recent.

**Tasks:**

- [ ] PREA-13: Implement count increment on entity link
- [ ] PREA-14: Implement count decrement on entity unlink
- [ ] PREA-15: Implement last_activity_at update on linked entity activity
- [ ] PREA-16: Implement last_activity_at recomputation on entity unlink
- [ ] PREA-17: Implement count consistency check (background job to reconcile counts)

**Tests:**

- [ ] PREA-T13: Test count never goes negative on rapid unlink
- [ ] PREA-T14: Test last_activity_at updates on new communication in linked conversation
- [ ] PREA-T15: Test last_activity_at recomputed correctly after unlinking most-recent entity
- [ ] PREA-T16: Test count consistency between denormalized value and actual junction row count

---

## 6. Derived Participant Display

### 6.1 Concept

The project detail view shows two categories of contacts:

- **Explicit:** Contacts in project_contacts with user-assigned roles and notes.
- **Derived:** Contacts who appear as participants in communications within linked conversations, but are NOT in project_contacts.

Derived participants are a presentation concern — they are computed at display time from the communication_participants → conversations → project_conversations join path. They are NOT stored in a separate table.

### 6.2 UI Behavior

- Explicit contacts shown with role badges and full interaction options.
- Derived contacts shown in a separate "Also involved" section, visually distinguished (lighter weight, no role).
- Optional one-click "Add to project" action to promote a derived contact to explicit association.

**Tasks:**

- [ ] PREA-18: Implement derived participant query (explicit + derived UNION)
- [ ] PREA-19: Implement promote-to-explicit action (create project_contacts row)

**Tests:**

- [ ] PREA-T17: Test derived participants found from linked conversation communications
- [ ] PREA-T18: Test derived list excludes already-explicit contacts
- [ ] PREA-T19: Test promote action creates project_contacts row with default empty role
