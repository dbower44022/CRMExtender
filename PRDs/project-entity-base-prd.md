# Project — Entity Base PRD

**Version:** 1.0
**Last Updated:** 2026-02-23
**Status:** Draft
**Product PRD:** [CRMExtender Product PRD]

---

## 1. Entity Definition

### 1.1 Purpose

Project is the central organizational hub of CRMExtender. A Project represents a business initiative, engagement, deal, campaign, or any purposeful body of work. While other entities capture specific types of data — Communications capture messages, Conversations group threads, Events track meetings, Contacts represent people — the Project ties them all together into a coherent picture of "what is this work, who is involved, and what has happened."

Projects are the highest-level user-created organizational container. They connect to every major entity type through system-defined Relation Types: Conversations, Events, Notes, Contacts, and Companies all link directly to Projects. Sub-projects support complex multi-workstream initiatives.

### 1.2 Design Goals

- **Central hub, not conversation container** — Projects organize all work. A project links to contacts who may never send a message, events with no associated emails, and notes capturing strategic context outside any conversation.
- **User-defined workflow** — No system-imposed status states or transitions. Users define their own project lifecycle. A gutter cleaning company and a venture capital fund have fundamentally different workflows.
- **Flexible hierarchy** — Conversations link to Projects via many-to-many Relation Types. Aggregate Conversations provide organizational grouping. Sub-projects nest to any depth. Every connection is optional.
- **Explicit relationships** — Contacts and Companies are intentionally associated with Projects, not derived from communication patterns. A project's stakeholder list represents who matters, not just who has emailed.
- **System Relation Types ship out of the box** — Common entity connections are pre-defined, eliminating setup friction while preserving extensibility.
- **Always user-created** — Projects require deliberate human action. AI may suggest but never auto-creates.

### 1.3 Performance Targets

| Metric | Target |
|---|---|
| Project list load (default view, 50 rows) | < 200ms |
| Project detail with linked entity counts | < 200ms |
| Sub-project tree load (recursive CTE) | < 100ms |
| Cross-entity query (conversations for project) | < 200ms |

### 1.4 Core Fields

| Field | Description | Required | Editable | Sortable | Filterable | Valid Values / Rules |
|---|---|---|---|---|---|---|
| ID | Unique identifier. Prefixed ULID with `prj_` prefix. | Yes | System | No | Yes | Prefixed ULID |
| Name | Project name. Display name field. | Yes | Direct | Yes | Yes | Free text |
| Description | Purpose and scope. | No | Direct | No | Yes | Multi-line text |
| User Status | User-defined workflow status. Select field with user-configured options. | No | Direct | Yes | Yes | User-defined. No defaults. |
| Owner ID | User who manages the project. | No | Direct | No | Yes | Reference to User |
| Parent Project ID | Self-reference for sub-project nesting. | No | Direct | No | Yes | FK to projects(id) |
| Last Activity At | Most recent activity across all linked entities. Computed by aggregation behavior. | No | System | Yes | Yes | TIMESTAMPTZ |
| Status (Record) | Record lifecycle. | Yes, defaults to active | System | Yes | Yes | `active`, `archived` |
| Created By | User who created the project. | Yes | System | No | Yes | Reference to User |
| Created At | Record creation timestamp. | Yes | System | Yes | Yes | Timestamp |
| Updated At | Last modification timestamp. | Yes | System | Yes | Yes | Timestamp |

### 1.5 Denormalized Count Fields

Maintained by the entity aggregation behavior on link/unlink:

| Field | Description | Sortable | Filterable |
|---|---|---|---|
| Conversation Count | Conversations linked via Relation Type | Yes | Yes |
| Contact Count | Explicitly associated contacts | Yes | Yes |
| Company Count | Explicitly associated companies | Yes | Yes |
| Event Count | Linked events | Yes | Yes |
| Note Count | Attached notes | Yes | Yes |
| Sub-Project Count | Direct child projects | Yes | Yes |

### 1.6 Registered Behaviors

| Behavior | Trigger | Description |
|---|---|---|
| Entity aggregation | On linked entity add/remove | Maintains denormalized counts. See Relations Sub-PRD. |
| Last activity computation | On linked entity activity | Updates last_activity_at from most recent activity. See Relations Sub-PRD. |
| Sub-project cascade | On project archive | Cascades archive to child projects. |

---

## 2. Entity Relationships

### 2.1 Conversations

**Nature:** Many-to-many, via `project_conversations` junction table
**Ownership:** Shared (Relation Type: `project_conversations`)
**Description:** Both standard and aggregate Conversations can associate with Projects. No inheritance — child conversations of an aggregate don't auto-inherit project association. See Relations Sub-PRD.

### 2.2 Contacts

**Nature:** Many-to-many, via `project_contacts` junction table
**Ownership:** Shared (Relation Type: `project_contacts`)
**Description:** Explicit, user-curated associations with role and notes metadata. Independent of communication participation. See Relations Sub-PRD.

### 2.3 Companies

**Nature:** Many-to-many, via `project_companies` junction table
**Ownership:** Shared (Relation Type: `project_companies`)
**Description:** Explicit associations with role and notes metadata. See Relations Sub-PRD.

### 2.4 Events

**Nature:** Many-to-many, via `project_events` junction table
**Ownership:** Shared (Relation Type: `project_events`)
**Description:** Events linked to projects for meeting and activity tracking. See Relations Sub-PRD.

### 2.5 Notes

**Nature:** Many-to-many, via Notes Universal Attachment
**Ownership:** Notes PRD
**Description:** Notes attach to Projects through the Universal Attachment pattern (note_entities). No separate project-specific junction table.

### 2.6 Tasks

**Nature:** Many-to-many, via Tasks Universal Attachment
**Ownership:** Tasks PRD
**Description:** Tasks attach to Projects through the Universal Attachment pattern (task_entities).

### 2.7 Documents

**Nature:** Many-to-many, via Documents Universal Attachment
**Ownership:** Documents PRD
**Description:** Documents attach to Projects through the Universal Attachment pattern.

### 2.8 Projects (Sub-Project Hierarchy)

**Nature:** One-to-many, self-referential via `parent_project_id` FK
**Ownership:** This entity (Relation Type: `project_hierarchy`)
**Description:** Unlimited nesting. Cascade archive. See Section 4.

---

## 3. User-Defined Status Workflow

### 3.1 Design Philosophy

The platform imposes no opinions on project status states. Different businesses have fundamentally different lifecycles:

| Business | Example Workflow |
|---|---|
| Gutter cleaning | scoping → scheduled → in_progress → invoiced → closed |
| Real estate | due_diligence → under_contract → closing → post_closing |
| Consulting | proposal → active → review → completed |
| Sales pipeline | qualified → demo → negotiation → won / lost |

### 3.2 Configuration Model

`user_status` is a Select field on the Project field registry:

- **Options:** User defines the list. No pre-populated defaults.
- **Transitions:** User optionally defines allowed state changes. If none defined, any change is allowed.
- **Default value:** User can designate a default for new projects.
- **Colors/icons:** Each option can have an associated color.

### 3.3 Transition Enforcement

When transitions are defined: PATCH attempting a disallowed transition returns validation error. UI presents only valid next-state options. If no transitions defined, fully flexible mode.

### 3.4 Status and Archiving

`user_status` and `archived_at` are independent:
- Archiving does not change user_status. Unarchiving retains the status.
- Setting a "terminal" status (completed, closed) does not auto-archive. User must explicitly archive.
- Users can filter by user_status = 'completed' (finished but visible) or archived_at IS NULL (all non-archived).

---

## 4. Sub-Project Hierarchy

### 4.1 Relation Type

| Property | Value |
|---|---|
| Slug | `project_hierarchy` |
| Source/Target | Project → Project (self-referential) |
| Cardinality | One-to-many |
| Implementation | parent_project_id FK (no junction table) |
| Cascade | Archive cascades down. Unarchive does not. |

### 4.2 Unlimited Depth

No artificial depth limit. Self-referential FK supports any depth. Users rarely exceed 2–3 levels.

### 4.3 Example Hierarchy

```
Project: 2026 Expansion
  ├── Sub-project: NYC Office
  │     ├── Aggregate: Real Estate
  │     ├── Aggregate: Hiring
  │     └── Aggregate: Regulatory
  ├── Sub-project: London Office
  │     ├── Aggregate: Real Estate
  │     └── Aggregate: Visa Sponsorship
  └── Sub-project: Infrastructure
        ├── Aggregate: Cloud Migration
        └── Aggregate: Security Audit
```

### 4.4 Cascade Behavior

Archive cascades to all child sub-projects (recursive). Unarchive does NOT cascade — user must explicitly restore each sub-project.

---

## 5. Flexible Hierarchy Model

### 5.1 The Relaxed Graph

Every connection is optional. Conversations link to Projects via many-to-many Relation Types. Aggregate Conversations (is_aggregate = true, defined in Conversations PRD) serve as organizational groupings.

```
Flexible attachment model:

  Project ↔ Conversation     (many-to-many, via Relation Type)
  Project ↔ Sub-project      (one-to-many, self-referential)
  Conversation ↔ Aggregate   (many-to-many, via conversation_members)

All combinations valid:
  ✓ Conversation with no aggregate, no Project
  ✓ Conversation → Aggregate (standalone, no Project)
  ✓ Conversation → Project (direct via Relation Type)
  ✓ Conversation → Aggregate → Project
  ✓ Project with direct Conversations AND aggregate Conversations
```

### 5.2 No Inheritance

If an aggregate Conversation is associated with a Project, its child Conversations do NOT automatically inherit that association. Each Conversation's Project associations are independent.

### 5.3 Entity Hierarchy Summary

| Entity | Must belong to a parent? | Can exist independently? |
|---|---|---|
| Communication | No | Yes — marketing emails, unknown senders |
| Conversation (standard) | No | Yes — ongoing exchange not part of any project |
| Conversation (aggregate) | No | Yes — standalone organizational grouping |
| Project | No — top-level entity | Yes — always independent |

---

## 6. Project Creation Model

### 6.1 Creation Patterns

- **Proactive** — User creates project before communications occur, in anticipation of future work.
- **Reactive** — User creates project in response to incoming communication introducing a new initiative. Existing conversations and contacts linked retroactively.

### 6.2 Always User-Created

Projects require deliberate human action. Unlike Conversations (auto-created from email threads), Projects are never auto-created. AI may suggest creating a project when it detects related unorganized conversations — always presented as a suggestion for user confirmation.

---

## 7. Lifecycle

| Status | Description |
|---|---|
| `active` | Normal operating state. Visible in views. |
| `archived` | Soft-deleted. Cascade archives sub-projects. Linked entities (conversations, contacts, events, notes) persist independently. Recoverable. |

---

## 8. Key Processes

### KP-1: Creating a Project

**Trigger:** User creates project from Entity Bar or context menu.

**Step 1 — Core fields:** Name (required), description, user_status, owner.

**Step 2 — Parent (optional):** Set parent_project_id for sub-project.

**Step 3 — Entity links:** Associate conversations, contacts, companies, events.

**Step 4 — Behaviors fire:** Entity aggregation updates counts. Sub-project count on parent.

### KP-2: Managing Entity Links

**Trigger:** User adds or removes linked entities from project detail.

**Step 1 — Select entity type and record:** Conversation, contact, company, or event.

**Step 2 — Create/remove link:** Junction table row inserted or deleted.

**Step 3 — Counts update:** Entity aggregation behavior maintains denormalized counts.

**Step 4 — Last activity:** Recomputed if relevant.

### KP-3: Browsing a Project

**Trigger:** User views project detail page.

**Step 1 — Summary:** Name, status, owner, counts.

**Step 2 — Linked entities:** Tabbed panels for conversations, contacts, companies, events, notes, tasks, sub-projects.

**Step 3 — Derived participants:** Contacts from linked conversation communications shown separately from explicit associations.

### KP-4: Working the Status Workflow

**Trigger:** User changes user_status.

**Step 1 — Transition check:** If transitions defined, validate allowed. If not, any change allowed.

**Step 2 — Update:** user_status field updated. status_changed event emitted.

**Step 3 — No side effects:** Status change does not cascade or trigger other behaviors.

---

## 9. Action Catalog

### 9.1 Create Project

**Supports processes:** KP-1
**Trigger:** User creation.
**Outcome:** Project with name, optional status/owner/parent, optional entity links.

### 9.2 Manage Entity Links

**Supports processes:** KP-2
**Trigger:** User adds/removes linked entities.
**Outcome:** Junction table updated, counts maintained, last activity recomputed.

### 9.3 Browse Project

**Supports processes:** KP-3
**Trigger:** User navigation.
**Outcome:** Detail view with all linked entities, counts, derived participants.

### 9.4 Status Workflow

**Supports processes:** KP-4
**Trigger:** User changes status.
**Outcome:** Validated transition, event emitted.

### 9.5 Archive / Restore

**Trigger:** User archives or restores.
**Outcome:** Cascade archive to sub-projects. Linked entities persist independently.

### 9.6 Entity Relations & Aggregation

**Summary:** 5 system Relation Types (Conversation, Contact with role/notes, Company with role/notes, Event, Note via Universal Attachment). Entity aggregation behavior maintaining 6 denormalized counts and last_activity_at. Custom Object Type relation guidance. Derived participant display concept.
**Sub-PRD:** [project-relations-prd.md]

---

## 10. Open Questions

1. **Sub-project depth warning:** Soft UI warning when nesting exceeds 3–4 levels?
2. **Archive cascade scope:** Only sub-projects cascade. Should any other linked entities be affected?
3. **Project templates:** Pre-defined structures (status states, sub-projects, aggregates) that users can instantiate?
4. **Bulk entity linking:** Batch API for linking multiple conversations/contacts/events in one request?
5. **Derived participant display:** Visual distinction from explicit associations? One-click promote to explicit?
6. **Project merge/split:** Merge two projects? Split into sub-projects? Entity link handling?
7. **Cross-tenant sharing:** Future multi-tenant project sharing?

---

## 11. Design Decisions

### Why central hub, not conversation container?

Projects organize all work — contacts who never email, events with no threads, strategic notes. Limiting to conversation container misses the full picture.

### Why no system-managed status field?

Businesses have fundamentally different workflows. System-imposed states (Lead → Qualified → Closed) don't fit every domain. user_status Select field with user-configured options and transitions serves all cases.

### Why explicit Contact and Company associations?

Derived participant lists miss stakeholders who haven't communicated through the platform — zoning attorneys, silent investors, general contractors. Explicit associations capture who matters, not just who has emailed.

### Why system Relation Types instead of user-configured?

Project→Conversation, Project→Contact, Project→Event are near-universal. Requiring manual creation adds friction without benefit. System types make Projects immediately useful.

### Why many-to-many for Conversation↔Project?

A conversation may be relevant to multiple projects simultaneously. Many-to-many provides flexibility without duplication.

### Why aggregate Conversations exist independently?

Organizational grouping has value outside projects. "Vendor Negotiations" aggregate across the organization regardless of project. Independence preserves grouping as a general-purpose tool.

### Why unlimited sub-project depth?

Self-referential FK naturally supports any depth. Artificial limits require enforcement logic without benefit. Users rarely exceed 2–3 levels.

### Why always user-created?

Projects represent intentional organizational decisions. Auto-creation would generate noise. AI suggestion with user confirmation preserves signal quality.

---

## Related Documents

| Document | Relationship |
|---|---|
| [Project Entity TDD](project-entity-tdd.md) | Technical decisions for project implementation |
| [Entity Relations & Aggregation Sub-PRD](project-relations-prd.md) | System Relation Types, aggregation behavior |
| [Custom Objects PRD](custom-objects-prd.md) | Unified object model |
| [Conversation Entity Base PRD](conversation-entity-base-prd.md) | Conversation↔Project relationship, aggregate Conversations |
| [Note Entity Base PRD](note-entity-base-prd.md) | Universal Attachment for notes |
| [Task Entity Base PRD](task-entity-base-prd.md) | Universal Attachment for tasks |
| [Master Glossary](glossary.md) | Term definitions |
