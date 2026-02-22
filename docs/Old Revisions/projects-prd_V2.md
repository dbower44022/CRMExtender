# Product Requirements Document: Projects

## CRMExtender — Central Organizational Hub

**Version:** 2.0
**Date:** 2026-02-19
**Status:** Draft — Reconciled with Custom Objects PRD
**Parent Document:** [CRMExtender PRD v1.1](PRD.md)

> **V2.0 (2026-02-19):**
> Reconciled with Conversations PRD V3 architectural restructuring:
> - **Topic entity eliminated.** All Topic references updated to aggregate Conversations. The `top_` prefix is retired. Aggregate Conversations (Conversations with `is_aggregate = true`) replace Topics as the grouping mechanism.
> - **Project↔Conversation Relation Type is now many-to-many** via junction table, matching the Conversations PRD Section 8.2 definition. The `project_id` FK column on the Conversations table is removed.
> - **Project↔Topic Relation Type removed.** Topics no longer exist as a separate entity.
> - **Flexible Hierarchy rewritten.** No FK columns, no Topic intermediary. Conversations link to Projects exclusively via the Conversation↔Project system Relation Type.
> - **`topic_count` field removed** from field registry. `conversation_count` updated to count via Relation Type.
> - Dependencies updated to reference Conversations PRD V3 and Communications PRD V2.
>
> **V1.0 (2026-02-18):**
> This document was extracted from the Conversations PRD v1.0, which previously defined Project, Topic, and Conversation as co-resident system object types. During extraction, the Project entity was significantly rethought:
> - **Projects are the central organizational hub** — not just a conversation container. Events, Notes, Contacts, Companies, and Custom Objects all link directly to Projects.
> - **Flexible hierarchy** — Conversations can belong to a Project directly OR via a Topic. Topics can exist independently (no longer required to belong to a Project). All levels are optional.
> - **User-defined status workflow** — No system-imposed status states. Users define their own status options and transitions. The only system-managed state is `archived_at` (the universal field).
> - **Explicit Contact and Company associations** — Project↔Contact and Project↔Company are first-class relations, not derived from communication participants.
> - **System Relation Types** ship out of the box for all core entity connections, eliminating setup friction.
>
> All content is reconciled with the [Custom Objects PRD](custom-objects-prd.md) Unified Object Model:
> - Project is a **system object type** (`is_system = true`, prefix `prj_`) with registered behavior for entity aggregation.
> - Entity IDs use **prefixed ULIDs** per the platform-wide convention.
> - Sub-project hierarchy uses a **self-referential Relation Type** on Project (parent_project→child_project).
> - All entity stores use **per-entity-type event tables** per Custom Objects PRD Section 19.
> - All SQL uses **PostgreSQL** syntax with `TIMESTAMPTZ` timestamps and schema-per-tenant isolation.

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Problem Statement](#2-problem-statement)
3. [Goals & Success Metrics](#3-goals--success-metrics)
4. [User Personas & Stories](#4-user-personas--stories)
5. [Project as System Object Type](#5-project-as-system-object-type)
6. [Sub-Project Hierarchy](#6-sub-project-hierarchy)
7. [Flexible Hierarchy Model](#7-flexible-hierarchy-model)
8. [System Relation Types](#8-system-relation-types)
9. [User-Defined Status Workflow](#9-user-defined-status-workflow)
10. [Project Creation Model](#10-project-creation-model)
11. [Event Sourcing & Temporal History](#11-event-sourcing--temporal-history)
12. [Virtual Schema & Data Sources](#12-virtual-schema--data-sources)
13. [API Design](#13-api-design)
14. [Design Decisions](#14-design-decisions)
15. [Phasing & Roadmap](#15-phasing--roadmap)
16. [Dependencies & Related PRDs](#16-dependencies--related-prds)
17. [Open Questions](#17-open-questions)
18. [Future Work](#18-future-work)
19. [Glossary](#19-glossary)

---

## 1. Executive Summary

The Project subsystem is the **central organizational hub** of CRMExtender. A Project represents a business initiative, engagement, deal, campaign, or any purposeful body of work. While other entities capture specific types of data — Communications capture messages, Conversations group threads, Events track meetings, Contacts represent people — the Project ties them all together into a coherent picture of "what is this work, who is involved, and what has happened."

Projects are the highest-level user-created organizational container. They can contain sub-projects for complex multi-workstream initiatives. They connect to every major entity type in the platform through system-defined Relation Types: Conversations (standard and aggregate), Events, Notes, Contacts, and Companies all link directly to Projects.

**Core principles:**

- **Central hub, not conversation container** — Projects organize all work, not just communications. A project links to contacts who may never send a message, events that have no associated emails, and notes capturing strategic context that exists outside any conversation.
- **User-defined workflow** — The platform imposes no status states or transitions. Users define their own project lifecycle that matches their business reality. A gutter cleaning company and a venture capital fund have fundamentally different project workflows — the platform accommodates both without opinion.
- **Flexible hierarchy** — Conversations link to Projects via the Conversation↔Project system Relation Type (many-to-many). Aggregate Conversations provide organizational grouping within or outside of Projects. Sub-projects can nest to any depth. Every connection is optional — the hierarchy helps users organize, it never forces structure.
- **Explicit relationships** — Contacts and Companies are intentionally associated with Projects, not derived from communication patterns. A project's stakeholder list represents who matters, not just who has emailed.
- **System Relation Types ship out of the box** — The most common entity connections are pre-defined, eliminating setup friction while preserving user extensibility through Custom Objects.
- **Event-sourced history** — All mutations to Projects are stored as immutable events, enabling full audit trails and point-in-time reconstruction.

**Relationship to other PRDs:**

- **[Custom Objects PRD](custom-objects-prd.md)** — Project is a system object type. Table structure, field registry, event sourcing, and relation model are governed by the Custom Objects framework. This PRD defines the entity-specific behaviors and relations.
- **[Conversations PRD](conversations-prd_V3.md)** — Conversations link to Projects via the Conversation↔Project system Relation Type (many-to-many). The Conversations PRD defines the Conversation entity (standard and aggregate); this PRD defines the Project side of those relationships. Aggregate Conversations replace the former Topic entity.
- **[Communications PRD](communications-prd_V2.md)** — Communications belong to Conversations, which may belong to Projects. There is no direct Project→Communication relation.
- **[Contact Management PRD](contact-management-prd_V4.md)** — Contacts link to Projects through an explicit system Relation Type. Project association is independent of communication participation.
- **[Company Management PRD](company-management-prd.md)** — Companies link to Projects through an explicit system Relation Type.
- **[Event Management PRD](events-prd_V2.md)** — Events link to Projects through a system Relation Type.
- **[Notes PRD](notes-prd_V2.md)** — Notes attach to Projects through the Universal Attachment Relation pattern.
- **[Data Sources PRD](data-sources-prd.md)** — Virtual schema table for Projects is derived from the Project field registry.
- **[Views & Grid PRD](views-grid-prd_V3.md)** — Project views, filters, sorts, dashboards, and inline editing operate on fields from the Project field registry.
- **[Permissions & Sharing PRD](permissions-sharing-prd_V1.md)** — Project record access follows the standard role-based access model.

---

## 2. Problem Statement

CRM tools provide no meaningful concept of "project" as an organizing principle. Users face several challenges:

| Pain Point | Impact |
|---|---|
| **No work-level organization** | Communications, contacts, events, and notes exist as disconnected records. A complex initiative involving 15 contacts, 40 conversations, 10 meetings, and dozens of notes has no single container that ties them together. |
| **Contact association limited to communication** | CRMs only know about relationships where communication has occurred. A project stakeholder who hasn't emailed you — a zoning attorney, a general contractor, a silent investor — is invisible in the project context. |
| **Rigid project models** | Tools that do offer "projects" or "deals" impose fixed status workflows (Lead → Qualified → Proposal → Closed) that don't match every business. A gutter cleaning company's project lifecycle differs fundamentally from a consulting engagement or a real estate transaction. |
| **No hierarchical organization** | Complex initiatives with multiple workstreams — an expansion with NYC, London, and Infrastructure sub-projects — cannot be modeled as a hierarchy. Users resort to naming conventions or separate tools. |
| **Cross-entity fragmentation** | Even when individual entities are well-managed, there's no unified view that answers "show me everything related to this initiative." Users mentally reconstruct project context from scattered records. |

The Project subsystem addresses this by providing a flexible, extensible organizational hub that connects all entity types, supports user-defined workflows, and enables hierarchical structuring of complex work.

---

## 3. Goals & Success Metrics

### Goals

1. **Central organizational hub** — Every major entity type can be linked to a Project, providing a single place to see all related work.
2. **User-defined workflow** — Users define their own project status states and transitions, matching their actual business processes.
3. **Flexible hierarchy** — Sub-projects, Conversation↔Project Relation Type links, and explicit contact/company associations all coexist.
4. **Zero-friction setup** — System Relation Types for core entity connections ship out of the box. Users don't need to configure anything to start organizing work around Projects.
5. **Extensible** — Users can add custom fields to Projects and create relations to Custom Object Types, making Projects work for any domain.

### Success Metrics

| Metric | Target | Measurement |
|---|---|---|
| Project adoption | >60% of active users create at least one project within 30 days | Analytics: project creation rate |
| Entity linking breadth | Average project has links to ≥3 entity types | DB query: distinct relation types per project |
| User-defined status adoption | >80% of tenants customize project status options | DB query: tenants with non-default status configurations |
| Sub-project usage | >20% of projects use at least one sub-project | DB query: projects with `parent_project_id IS NOT NULL` |
| Cross-entity navigation | >50% of project detail views result in navigation to a linked entity | Analytics: click-through from project detail |

---

## 4. User Personas & Stories

### Personas

| Persona | Project Context | Key Needs |
|---|---|---|
| **Sam — Gutter Business Owner** | Multiple expansion projects across cities. Each involves properties, jobs, contractors, permits, and supplier relationships. | Organize work by city expansion. Link contacts (contractors, inspectors) to projects before any communication occurs. Track project status through his custom workflow (scoping → scheduled → in_progress → invoiced → closed). |
| **Alex — Sales Rep** | 30 active deals, each involving multiple stakeholders, conversations, meetings, and proposal documents. | Link all conversations for a deal to one project. Associate key decision-makers even if they haven't communicated directly. Track deal stage through a custom sales pipeline. |
| **Maria — Consultant** | Long-running client engagements with multiple workstreams. Each workstream has its own conversations, deliverables, and meetings. | Sub-projects for each workstream. Link events (client meetings) directly to the engagement project. Notes capturing strategic context attached to the project. |

### User Stories

#### Core Project Management

- **US-1:** As a user, I want to create projects to organize my work so that all related entities are grouped under a single initiative.
- **US-2:** As a user, I want to create sub-projects within a project so that I can organize complex initiatives with multiple workstreams.
- **US-3:** As a user, I want to define my own project status options and transitions so that my project workflow matches my business process.
- **US-4:** As a user, I want to add custom fields to projects so that I can capture domain-specific information (budget, deadline, region, etc.).

#### Entity Linking

- **US-5:** As a user, I want to associate contacts with a project so that I can see all stakeholders, including those I haven't communicated with through the platform.
- **US-6:** As a user, I want to associate companies with a project so that I can track which organizations are involved in an initiative.
- **US-7:** As a user, I want to link conversations to a project via Relation Types.
- **US-8:** As a user, I want to link events (meetings, calls) to a project so that I can see all scheduled and past activities for the initiative.
- **US-9:** As a user, I want to attach notes to a project to capture strategic context, decisions, and observations that exist outside any conversation.
- **US-10:** As a user, I want to link custom object records (Jobs, Properties, Estimates) to a project so that my domain-specific entities are organized under the same initiative.

#### Views & Navigation

- **US-11:** As a user, I want a project detail view that shows all linked entities — conversations, contacts, events, notes — in one place.
- **US-12:** As a user, I want to create custom views filtered by project, so that I can build project-specific dashboards.
- **US-13:** As a user, I want to filter and sort projects by my custom status field, owner, last activity, and other fields.

---

## 5. Project as System Object Type

### 5.1 Object Type Registration

| Attribute | Value |
|---|---|
| `name` | Project |
| `slug` | `projects` |
| `type_prefix` | `prj_` |
| `is_system` | `true` |
| `display_name_field_id` | → `name` field |
| `description` | The central organizational hub representing a business initiative, engagement, deal, or purposeful body of work. Connects to all major entity types. |

### 5.2 Registered Behaviors

| Behavior | Source PRD | Trigger |
|---|---|---|
| Entity aggregation | This PRD | On linked entity change (conversation, event, note, contact, company added/removed) |
| Last activity computation | This PRD | On any linked entity activity (new communication in linked conversation, event completed, note added) |
| Sub-project cascade | This PRD | On project archive (cascade to children per Relation Type configuration) |

### 5.3 Project Field Registry

**Universal fields** (per Custom Objects PRD Section 7): `id`, `tenant_id`, `created_at`, `updated_at`, `created_by`, `updated_by`, `archived_at`.

**Core system fields** (`is_system = true`, protected):

| Field | Column | Type | Required | Description |
|---|---|---|---|---|
| Name | `name` | Text (single-line) | YES | Project name. Display name field. |
| Description | `description` | Text (multi-line) | NO | Optional description of the project's purpose and scope. |
| User Status | `user_status` | Select | NO | User-defined workflow status. Options and transitions configured by the user (see Section 9). No default options — user populates their own. |
| Owner ID | `owner_id` | Relation (→ users) | NO | The user who manages the project. |
| Parent Project ID | `parent_project_id` | Relation (→ projects) | NO | Self-referential FK for sub-project nesting. NULL for top-level projects. |
| Last Activity At | `last_activity_at` | Datetime | NO | Most recent activity timestamp across all linked entities (conversations, events, notes). Computed by the entity aggregation behavior. |

**Note:** There is no system-managed status field. The `archived_at` universal field (present on all entity types) serves as the sole system lifecycle state — a project is either active (`archived_at IS NULL`) or archived (`archived_at IS NOT NULL`). All workflow-level status management is delegated to the user-defined `user_status` select field.

### 5.4 Denormalized Count Fields

Count fields are maintained by the entity aggregation behavior and updated when linked entities are added or removed:

| Field | Column | Type | Description |
|---|---|---|---|
| Conversation Count | `conversation_count` | Number (integer) | Count of conversations linked via the Conversation↔Project Relation Type. |
| Contact Count | `contact_count` | Number (integer) | Count of explicitly associated contacts. |
| Company Count | `company_count` | Number (integer) | Count of explicitly associated companies. |
| Event Count | `event_count` | Number (integer) | Count of linked events. |
| Note Count | `note_count` | Number (integer) | Count of attached notes. |
| Sub-Project Count | `sub_project_count` | Number (integer) | Count of direct child projects. |

### 5.5 Read Model Table

```sql
-- Within tenant schema: tenant_abc.projects
CREATE TABLE projects (
    -- Universal fields
    id                  TEXT PRIMARY KEY,        -- prj_01HX8A...
    tenant_id           TEXT NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by          TEXT REFERENCES platform.users(id),
    updated_by          TEXT REFERENCES platform.users(id),
    archived_at         TIMESTAMPTZ,

    -- Core system fields
    name                TEXT NOT NULL,
    description         TEXT,
    user_status         TEXT,                   -- User-defined select value
    owner_id            TEXT REFERENCES platform.users(id),
    parent_project_id   TEXT REFERENCES projects(id),
    last_activity_at    TIMESTAMPTZ,

    -- Denormalized counts
    conversation_count  INTEGER DEFAULT 0,
    contact_count       INTEGER DEFAULT 0,
    company_count       INTEGER DEFAULT 0,
    event_count         INTEGER DEFAULT 0,
    note_count          INTEGER DEFAULT 0,
    sub_project_count   INTEGER DEFAULT 0
);

-- Indexes
CREATE INDEX idx_prj_owner ON projects (owner_id) WHERE owner_id IS NOT NULL;
CREATE INDEX idx_prj_parent ON projects (parent_project_id) WHERE parent_project_id IS NOT NULL;
CREATE INDEX idx_prj_user_status ON projects (user_status) WHERE user_status IS NOT NULL;
CREATE INDEX idx_prj_last_activity ON projects (last_activity_at DESC);
CREATE INDEX idx_prj_archived ON projects (archived_at) WHERE archived_at IS NULL;
```

---

## 6. Sub-Project Hierarchy

### 6.1 Self-Referential Relation Type

Sub-projects use a **self-referential Relation Type** on the Project object type:

| Attribute | Value |
|---|---|
| Relation Type Name | Project Hierarchy |
| Relation Type Slug | `project_hierarchy` |
| Source Object Type | Project (`prj_`) |
| Target Object Type | Project (`prj_`) |
| Cardinality | One-to-many (parent has many children) |
| Directionality | Bidirectional |
| `is_system` | `true` |
| Cascade (source archived) | Cascade archive children |

Implementation: The `parent_project_id` FK column on the `projects` table. No junction table needed for 1:many.

### 6.2 Example Hierarchy

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

### 6.3 Depth

Sub-project nesting depth is **unlimited**. The self-referential Relation Type naturally supports any depth. In practice, users rarely go beyond 2–3 levels. No artificial depth limit is imposed — if a user wants "Expansion → NYC → Legal → Contract Review," that is their organizational choice.

### 6.4 Cascade Behavior

When a project is archived, all child sub-projects are cascaded to archived status. This follows the Relation Type's cascade configuration. Unarchiving a parent does **not** automatically unarchive children — the user must explicitly restore each sub-project they want active.

---

## 7. Flexible Hierarchy Model

### 7.1 The Relaxed Hierarchy

The hierarchy is a flexible graph where every connection is optional. Conversations link to Projects via the Conversation↔Project system Relation Type (many-to-many). Aggregate Conversations (Conversations with `is_aggregate = true`, defined in the Conversations PRD) serve as organizational groupings — replacing the former Topic entity.

```
Flexible attachment model:

  Project ↔ Conversation     (many-to-many, via Relation Type)
  Project ↔ Sub-project      (one-to-many, self-referential)
  Conversation ↔ Aggregate   (many-to-many, via conversation_members)

All combinations are valid:
  ✓ Conversation with no aggregate, no Project
  ✓ Conversation → Aggregate Conversation (standalone, no Project)
  ✓ Conversation → Project (direct association via Relation Type)
  ✓ Conversation → Aggregate → Project (aggregate associated with Project)
  ✓ Project with direct Conversations AND aggregate Conversations
```

### 7.2 Conversation–Project Association

Conversations associate with Projects exclusively through the **Conversation↔Project system Relation Type** (Section 8.1). This is a many-to-many junction table — a Conversation can be associated with multiple Projects, and a Project can have many associated Conversations.

There are no FK columns (`project_id`, `topic_id`) on the Conversations table. All entity attachment uses Relation Types as defined in the Conversations PRD Section 8.

**No inheritance:** If an aggregate Conversation is associated with a Project, its child Conversations do NOT automatically inherit that association. Each Conversation's Project associations are independent (Conversations PRD Section 8.4).

### 7.3 Aggregate Conversations as Organizational Grouping

Aggregate Conversations (defined in Conversations PRD Section 6) serve the organizational grouping role previously played by Topics:

- An aggregate Conversation "Lease Negotiation" can group child Conversations with the lawyer, accountant, and lessor.
- The aggregate can itself be associated with a Project via the Conversation↔Project Relation Type.
- Aggregates can also exist independently — not everything needs a Project parent.

Use cases for standalone aggregate Conversations (no Project association):
- A "Vendor Negotiations" aggregate grouping conversations with multiple suppliers, not part of any specific project.
- A "Hiring" aggregate grouping interview conversations across the organization.
- Temporary groupings that may later be associated with a project.

### 7.4 Entity Hierarchy Summary

| Entity | Must belong to a parent? | Can exist independently? |
|---|---|---|
| Communication | No — can be unassigned | Yes — marketing emails, unknown senders, one-offs |
| Conversation (standard) | No — doesn't need an aggregate or project | Yes — ongoing exchange not part of any project |
| Conversation (aggregate) | No — can exist without a project | Yes — standalone organizational grouping |
| Project | No — top-level entity | Yes — always independent |

---

## 8. System Relation Types

The following system Relation Types ship with every tenant, pre-configured and ready to use. Users do not need to create these manually.

### 8.1 Project ↔ Conversation

| Attribute | Value |
|---|---|
| Relation Type Name | Project Conversations |
| Relation Type Slug | `project_conversations` |
| Source Object Type | Project (`prj_`) |
| Target Object Type | Conversation (`cvr_`) |
| Cardinality | Many-to-many |
| Directionality | Bidirectional |
| `is_system` | `true` |
| Cascade (source archived) | No cascade — conversations persist independently |

Implementation: Junction table `project_conversations`. This mirrors the Conversation↔Project Relation Type defined in the Conversations PRD Section 8.2 (same junction table, defined once).

```sql
CREATE TABLE project_conversations (
    project_id      TEXT NOT NULL REFERENCES projects(id),
    conversation_id TEXT NOT NULL REFERENCES conversations(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by      TEXT REFERENCES platform.users(id),

    PRIMARY KEY (project_id, conversation_id)
);

CREATE INDEX idx_prc_project ON project_conversations (project_id);
CREATE INDEX idx_prc_conversation ON project_conversations (conversation_id);
```

**Note:** Both standard and aggregate Conversations can be associated with Projects. There is no restriction on the Conversation's `is_aggregate` value.

### 8.2 Project ↔ Contact

 ↔ Contact

| Attribute | Value |
|---|---|
| Relation Type Name | Project Contacts |
| Relation Type Slug | `project_contacts` |
| Source Object Type | Project (`prj_`) |
| Target Object Type | Contact (`con_`) |
| Cardinality | Many-to-many |
| Directionality | Bidirectional |
| `is_system` | `true` |
| Cascade (source archived) | No cascade |

Implementation: Junction table `project_contacts`.

```sql
CREATE TABLE project_contacts (
    id              TEXT PRIMARY KEY,        -- pcn_01HX8A...
    project_id      TEXT NOT NULL REFERENCES projects(id),
    contact_id      TEXT NOT NULL REFERENCES contacts(id),
    role            TEXT,                    -- Optional: "stakeholder", "decision-maker", "vendor", etc.
    notes           TEXT,                    -- Optional context about this contact's involvement
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by      TEXT REFERENCES platform.users(id),

    UNIQUE (project_id, contact_id)
);

CREATE INDEX idx_pcn_project ON project_contacts (project_id);
CREATE INDEX idx_pcn_contact ON project_contacts (contact_id);
```

**Note:** This is an explicit, user-curated association. It is independent of whether the contact has participated in any communications linked to the project. The project detail view may additionally show derived participants (from linked conversations) as a supplementary list, but that is a presentation concern, not a data model concern.

### 8.3 Project ↔ Company

| Attribute | Value |
|---|---|
| Relation Type Name | Project Companies |
| Relation Type Slug | `project_companies` |
| Source Object Type | Project (`prj_`) |
| Target Object Type | Company (`cmp_`) |
| Cardinality | Many-to-many |
| Directionality | Bidirectional |
| `is_system` | `true` |
| Cascade (source archived) | No cascade |

Implementation: Junction table `project_companies`.

```sql
CREATE TABLE project_companies (
    id              TEXT PRIMARY KEY,        -- pco_01HX8A...
    project_id      TEXT NOT NULL REFERENCES projects(id),
    company_id      TEXT NOT NULL REFERENCES companies(id),
    role            TEXT,                    -- Optional: "client", "vendor", "partner", etc.
    notes           TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by      TEXT REFERENCES platform.users(id),

    UNIQUE (project_id, company_id)
);

CREATE INDEX idx_pco_project ON project_companies (project_id);
CREATE INDEX idx_pco_company ON project_companies (company_id);
```

### 8.4 Project ↔ Event

| Attribute | Value |
|---|---|
| Relation Type Name | Project Events |
| Relation Type Slug | `project_events` |
| Source Object Type | Project (`prj_`) |
| Target Object Type | Event (`evt_`) |
| Cardinality | Many-to-many |
| Directionality | Bidirectional |
| `is_system` | `true` |
| Cascade (source archived) | No cascade |

Implementation: Junction table `project_events`.

```sql
CREATE TABLE project_events (
    id              TEXT PRIMARY KEY,        -- pev_01HX8A...
    project_id      TEXT NOT NULL REFERENCES projects(id),
    event_id        TEXT NOT NULL REFERENCES events(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by      TEXT REFERENCES platform.users(id),

    UNIQUE (project_id, event_id)
);

CREATE INDEX idx_pev_project ON project_events (project_id);
CREATE INDEX idx_pev_event ON project_events (event_id);
```

### 8.5 Project ↔ Note

| Attribute | Value |
|---|---|
| Relation Type Name | Project Notes |
| Relation Type Slug | `project_notes` |
| Source Object Type | Project (`prj_`) |
| Target Object Type | Note (`nte_`) |
| Cardinality | Many-to-many |
| Directionality | Bidirectional |
| `is_system` | `true` |
| Cascade (source archived) | No cascade |

Notes attach to Projects through the **Universal Attachment Relation** pattern defined in the Notes PRD. The Notes PRD's universal attachment model already supports attachment to any entity type; this Relation Type formalizes the Project-specific instance.

### 8.6 Project ↔ Project (Sub-Project Hierarchy)

Defined in Section 6.1. Self-referential, one-to-many via `parent_project_id` FK.

### 8.7 Custom Object Type Relations

Custom Object Types (Jobs, Properties, Estimates, Service Areas, etc.) are user-created and therefore do not have pre-defined system Relation Types to Projects. Users create these relations through the standard Custom Objects relation framework during the custom object type definition process.

The Custom Objects creation UX surfaces relationship definition as part of the setup flow, allowing users to easily establish Project ↔ Custom Object relations at creation time.

---

## 9. User-Defined Status Workflow

### 9.1 Design Philosophy

The platform imposes no opinions on what project status states look like. Different businesses have fundamentally different project lifecycles:

| Business | Example Status Workflow |
|---|---|
| Gutter cleaning | `scoping` → `scheduled` → `in_progress` → `invoiced` → `closed` |
| Real estate investing | `due_diligence` → `under_contract` → `closing` → `post_closing` |
| Consulting | `proposal` → `active` → `review` → `completed` |
| Sales pipeline | `qualified` → `demo` → `negotiation` → `won` / `lost` |

### 9.2 Configuration Model

The `user_status` field is a Select field on the Project field registry. Its configuration follows the standard Select field model from the Custom Objects PRD:

- **Options:** User defines the list of available status values. No pre-populated defaults.
- **Transitions:** User defines which transitions are allowed between states. Transitions are enforced by the platform when configured. If no transitions are defined, any status can be set at any time.
- **Default value:** User can optionally designate a default status for new projects.
- **Colors/icons:** Each status option can have an associated color for visual distinction in views.

### 9.3 Transition Enforcement

When the user defines transitions, the platform enforces them:

- A PATCH request attempting a disallowed transition returns a validation error.
- The UI only presents valid next-state options based on the current state and defined transitions.
- If no transitions are defined for the tenant, all state changes are allowed (fully flexible mode).

### 9.4 Status and Archiving

The `user_status` field and the `archived_at` universal field are independent:

- Archiving a project does not change its `user_status`. A project archived in `invoiced` status retains that status if unarchived later.
- Setting a "terminal" user status (e.g., `closed`, `completed`) does not automatically archive the project. The user must explicitly archive if they want the project hidden from default views.
- This separation means users can filter by `user_status = 'completed'` to see finished-but-still-visible projects, or by `archived_at IS NULL` to see all non-archived projects regardless of workflow state.

---

## 10. Project Creation Model

### 10.1 Creation Patterns

- **Proactive** — User creates a project before any communications occur, in anticipation of future work. May create aggregate Conversations, associate contacts and companies. Example: "2026 Cleveland Expansion" project created with stakeholder contacts and sub-projects before any emails are exchanged.
- **Reactive** — User creates a project in response to an incoming communication that introduces a new initiative. Existing conversations and contacts are linked retroactively.

### 10.2 User-Created

Projects are **always user-created**. They represent an intentional decision to organize work around an initiative. Unlike Conversations (which can be auto-created from email threads), Projects require deliberate human action to establish.

AI may suggest creating a project when it detects a cluster of related conversations that don't belong to any existing project. This is always presented as a suggestion for user confirmation, never automatic.

---

## 11. Event Sourcing & Temporal History

### 11.1 Event Table

Per Custom Objects PRD Section 19, the Project entity type has a companion event table:

- `projects_events` — All mutations to Project records

Event table schema follows the standard pattern from Custom Objects PRD.

### 11.2 Key Event Types

| Event Type | Trigger | Description |
|---|---|---|
| `created` | New project created | Full record snapshot |
| `updated` | Project fields changed | Changed fields with old/new values |
| `status_changed` | `user_status` transitioned | Old and new status values |
| `conversation_linked` | Conversation associated with project | Conversation ID in metadata |
| `conversation_unlinked` | Conversation removed from project | Conversation ID in metadata |
| `contact_linked` | Contact associated with project | Contact ID and role in metadata |
| `contact_unlinked` | Contact removed from project | Contact ID in metadata |
| `company_linked` | Company associated with project | Company ID and role in metadata |
| `company_unlinked` | Company removed from project | Company ID in metadata |
| `event_linked` | Event associated with project | Event ID in metadata |
| `event_unlinked` | Event removed from project | Event ID in metadata |
| `note_attached` | Note attached to project | Note ID in metadata |
| `note_detached` | Note removed from project | Note ID in metadata |
| `sub_project_added` | Child project created or reparented under this project | Child project ID in metadata |
| `sub_project_removed` | Child project reparented away from this project | Child project ID in metadata |
| `archived` / `unarchived` | Soft-delete or restore | |

---

## 12. Virtual Schema & Data Sources

### 12.1 Virtual Schema Table

Per Data Sources PRD, the Project field registry generates a virtual schema table:

- `projects` — All project fields (universal + core system + user-defined custom fields)

### 12.2 Cross-Entity Queries

Data Source queries can traverse Project relationships:

```sql
-- All conversations in a specific project (via Relation Type)
SELECT c.subject, c.ai_status, c.ai_summary, c.is_aggregate
FROM conversations c
JOIN project_conversations pc ON c.id = pc.conversation_id
WHERE pc.project_id = 'prj_01HX7...'
   OR t.project_id = 'prj_01HX7...'
ORDER BY c.last_activity_at DESC;
```

```sql
-- All contacts associated with a project (explicit + derived from conversations)
-- Explicit associations:
SELECT con.display_name, pc.role, 'explicit' AS source
FROM project_contacts pc
JOIN contacts con ON con.id = pc.contact_id
WHERE ppc.project_id = 'prj_01HX7...'

UNION

-- Derived from conversation participants:
SELECT DISTINCT con.display_name, NULL AS role, 'derived' AS source
FROM conversations c
JOIN communications comm ON comm.conversation_id = c.id
JOIN communication_participants cp ON cp.communication_id = comm.id
JOIN contacts con ON con.id = cp.contact_id
WHERE (pc.project_id = 'prj_01HX7...'
  AND cp.contact_id NOT IN (
      SELECT contact_id FROM project_contacts WHERE project_id = 'prj_01HX7...'
  );
```

```sql
-- All events linked to a project
SELECT e.title, e.start_time, e.end_time, e.event_type
FROM project_events pe
JOIN events e ON e.id = pe.event_id
WHERE pe.project_id = 'prj_01HX7...'
ORDER BY e.start_time DESC;
```

---

## 13. API Design

### 13.1 Project CRUD API

| Endpoint | Method | Description |
|---|---|---|
| `/api/v1/projects` | GET | List projects (paginated, filterable by status, owner, archived state) |
| `/api/v1/projects` | POST | Create a project |
| `/api/v1/projects/{id}` | GET | Get project with summary counts and linked entity previews |
| `/api/v1/projects/{id}` | PATCH | Update project fields (name, description, status, owner, etc.) |
| `/api/v1/projects/{id}/archive` | POST | Archive a project (cascades to sub-projects) |
| `/api/v1/projects/{id}/unarchive` | POST | Unarchive a project (does not cascade) |
| `/api/v1/projects/{id}/history` | GET | Get event history |

### 13.2 Sub-Project API

| Endpoint | Method | Description |
|---|---|---|
| `/api/v1/projects/{id}/sub-projects` | GET | List child projects |
| `/api/v1/projects/{id}/sub-projects` | POST | Create a sub-project (sets `parent_project_id`) |

### 13.3 Project Relation APIs

| Endpoint | Method | Description |
|---|---|---|
| `/api/v1/projects/{id}/conversations` | GET | List conversations associated with this project (via Relation Type) |
| `/api/v1/projects/{id}/conversations` | POST | Link a conversation directly to this project |
| `/api/v1/projects/{id}/conversations/{cvr_id}` | DELETE | Unlink a conversation from this project |
| `/api/v1/projects/{id}/contacts` | GET | List explicitly associated contacts |
| `/api/v1/projects/{id}/contacts` | POST | Associate a contact with this project (with optional role) |
| `/api/v1/projects/{id}/contacts/{con_id}` | PATCH | Update contact role/notes on this project |
| `/api/v1/projects/{id}/contacts/{con_id}` | DELETE | Remove contact association |
| `/api/v1/projects/{id}/companies` | GET | List explicitly associated companies |
| `/api/v1/projects/{id}/companies` | POST | Associate a company with this project (with optional role) |
| `/api/v1/projects/{id}/companies/{cmp_id}` | PATCH | Update company role/notes on this project |
| `/api/v1/projects/{id}/companies/{cmp_id}` | DELETE | Remove company association |
| `/api/v1/projects/{id}/events` | GET | List linked events |
| `/api/v1/projects/{id}/events` | POST | Link an event to this project |
| `/api/v1/projects/{id}/events/{evt_id}` | DELETE | Unlink an event |
| `/api/v1/projects/{id}/notes` | GET | List attached notes |

### 13.4 Status Workflow API

| Endpoint | Method | Description |
|---|---|---|
| `/api/v1/projects/status-config` | GET | Get the tenant's project status configuration (options + transitions) |
| `/api/v1/projects/status-config` | PUT | Update the tenant's project status configuration |
| `/api/v1/projects/{id}/transition` | POST | Transition a project's user_status (validates against defined transitions) |

---

## 14. Design Decisions

### Why split Project into its own PRD?

The original Conversations PRD treated Projects as a conversation container — the top of the conversation hierarchy. But Projects are fundamentally broader. A project links to contacts who have never communicated, events with no email thread, and notes capturing strategic context outside any conversation. Elevating Projects to their own PRD reflects their role as the central organizational hub of the platform.

### Why no system-managed status field?

Every business has a different project lifecycle. A 4-state system status (`active`, `on_hold`, `completed`, `archived`) is either too rigid (doesn't match the user's workflow) or too generic (provides no actionable information). The `archived_at` universal field handles the only state the system truly needs to know — whether to include this project in default views. Everything else is the user's domain.

### Why explicit Contact and Company associations instead of derived?

Derived participant lists (from communication participants) miss stakeholders who haven't communicated through the platform. A project's zoning attorney, general contractor, or silent investor may be critical stakeholders with zero emails. Explicit associations let users curate the people who matter, independent of communication history.

### Why system Relation Types instead of user-configured?

Project→Conversation, Project→Contact, Project→Event are near-universal relationships. Requiring users to manually create these through the Custom Objects framework adds friction without benefit. System Relation Types make Projects immediately useful as an organizational hub while preserving user extensibility for Custom Object Types.

### Why many-to-many for Conversation↔Project?

A Conversation may be relevant to multiple Projects simultaneously (e.g., a vendor negotiation email thread relevant to both "NYC Office" and "Infrastructure" projects). Many-to-many via Relation Type provides this flexibility without requiring the user to duplicate conversations.

### Why do aggregate Conversations exist independently of Projects?

Aggregate Conversations as pure conversation groupings have value outside of projects. A "Vendor Negotiations" aggregate can group supplier conversations across the organization regardless of which project (if any) they relate to. This independence preserves organizational grouping as a general-purpose tool, not a project-specific one.

### Why unlimited sub-project depth?

Same rationale as the original Conversations PRD: the self-referential Relation Type naturally supports any depth. In practice, users rarely go beyond 2–3 levels. Adding an artificial depth limit requires enforcement logic without meaningful benefit.

### Why user-defined transitions instead of platform-enforced?

Users understand their workflow better than the platform does. Some businesses have strict process requirements (can't skip from "proposal" to "closed"); others need full flexibility. Letting users define both states and transitions serves both cases.

---

## 15. Phasing & Roadmap

### Phase 1: Core Entity & Hierarchy

**Goal:** Establish Project as a system object type with sub-project hierarchy and basic entity linking.

- Project as system object type with field registry
- Event sourcing for Project entity
- Sub-project hierarchy (self-referential relation)
- Project ↔ Conversation direct link (new `project_id` on conversations)
- Project ↔ Contact explicit association (junction table)
- Project ↔ Company explicit association (junction table)
- Project CRUD API endpoints
- Project relation API endpoints
- Basic project views and filtering

### Phase 2: Status Workflow & Event/Note Linking

**Goal:** User-defined status workflow and complete entity linking.

- User-defined status options and transitions
- Status transition enforcement and API
- Project ↔ Event link (junction table)
- Project ↔ Note link (universal attachment pattern)
- Denormalized count field maintenance
- Last activity computation across linked entities
- Project detail view with all linked entities

### Phase 3: Intelligence & Custom Object Integration

**Goal:** AI suggestions and seamless Custom Object integration.

- AI project suggestion (detect related unorganized conversations, suggest project creation)
- Custom Object Type → Project relation creation in the object type setup flow
- Cross-entity queries in Data Sources
- Advanced project views (grouped by status, filtered by entity counts, etc.)

---

## 16. Dependencies & Related PRDs

| PRD | Relationship | Dependency Direction |
|---|---|---|
| **Custom Objects PRD** | Project is a system object type. Framework governs table structure, field registry, event sourcing, and relation model. | **Bidirectional.** This PRD defines Project-specific behaviors and relations; Custom Objects provides the framework. |
| **Conversations PRD** | Conversations link to Projects via the Conversation↔Project system Relation Type (many-to-many). Aggregate Conversations serve as organizational groupings, replacing Topics. | **Bidirectional.** This PRD defines the Project side; Conversations PRD defines Conversation entity (standard and aggregate). |
| **Communications PRD** | Communications belong to Conversations, which may belong to Projects. No direct Project→Communication relation. | **Indirect.** Projects access communications through conversations. |
| **Contact Management PRD** | Contacts link to Projects through explicit system Relation Type (junction table). | **Bidirectional.** Projects consume contact data; project context enriches contact relationship intelligence. |
| **Company Management PRD** | Companies link to Projects through explicit system Relation Type (junction table). | **Bidirectional.** |
| **Event Management PRD** | Events link to Projects through system Relation Type (junction table). | **Bidirectional.** Projects provide initiative context for events; events provide activity history for projects. |
| **Notes PRD** | Notes attach to Projects through Universal Attachment Relation pattern. | **Notes depend on Projects** as attachment targets. |
| **Data Sources PRD** | Virtual schema for Projects derived from field registry. | **Data Sources depend on Custom Objects** (which governs Projects). |
| **Views & Grid PRD** | Project views, filters, dashboards. | **Views depend on Custom Objects** (which governs Projects). |
| **Permissions & Sharing PRD** | Access control on project records. | **Projects depend on Permissions.** |

---

## 17. Open Questions

1. **Sub-project depth soft warning** — Should the UI display a soft warning when sub-project nesting exceeds 3–4 levels? No enforcement, just a "this is getting deep" indicator.

2. **Archive cascade to linked entities** — When a project is archived, sub-projects are cascaded. Should any other linked entities be affected? Current decision: no — conversations, contacts, events, notes persist independently. 

3. **Project templates** — Should the system support pre-defined project structures (status states, aggregate Conversations, sub-projects) that users can instantiate? Example: a "New City Expansion" template with pre-configured sub-projects and aggregate Conversations.

4. **Bulk entity linking** — Should the API support batch operations for linking multiple conversations, contacts, or events to a project in a single request?

5. **Derived participant display** — The project detail view should show both explicitly associated contacts and derived participants from linked conversations. Should derived participants be visually distinguished? Should there be a one-click action to promote a derived participant to an explicit association?

6. **Project merge/split** — Can two projects be merged? Can a project be split into sub-projects? What happens to linked entities during these operations?

7. **Cross-tenant project sharing** — Future consideration for multi-tenant scenarios: can a project be shared across tenant boundaries?

---

## 18. Future Work

- **Project templates** — Pre-defined project structures for common workflows, instantiable with one click.
- **Project analytics** — Activity metrics, communication frequency, entity linkage density, timeline visualization.
- **AI project health signals** — User-configurable AI analysis of linked conversation sentiment, stale conversations, and unresolved action items at the project level.
- **Project cloning** — Duplicate a project's structure (sub-projects, aggregate Conversation structures, status configuration) without data for repeatable workflows.
- **Timeline view** — Chronological visualization of all activity across a project's linked entities.
- **Project-level permissions** — Fine-grained access control at the project level (who can see which projects and their linked entities).
- **Automation triggers** — User-defined automations triggered by project status transitions (e.g., "when status changes to 'invoiced', create a Job record").

---

## 19. Glossary

| Term | Definition |
|---|---|
| **Project** | The central organizational hub representing a business initiative, engagement, deal, or purposeful body of work. Connects to all major entity types. A system object type with prefix `prj_`. |
| **Sub-project** | A child project nested within a parent project via the self-referential Project Hierarchy Relation Type. Same structure as a project; supports unlimited nesting depth. |
| **User Status** | A user-defined Select field on the Project entity representing the project's workflow state. Options and transitions are configured by the user — the platform imposes no default states. |
| **System Relation Type** | A pre-defined Relation Type that ships with every tenant, connecting Projects to core entity types (Conversations, Contacts, Companies, Events, Notes). Eliminates setup friction for common relationships. |
| **Explicit Association** | A user-curated link between a Project and a Contact or Company, independent of communication participation. Represents intentional stakeholder identification. |
| **Derived Participant** | A Contact who appears in communications linked to a project's conversations, but is not explicitly associated with the project. Supplementary to explicit associations; a presentation concern. |
| **Flexible Hierarchy** | The relaxed organizational model where Conversations link to Projects via Relation Types (many-to-many), aggregate Conversations provide organizational grouping, and all connections are optional. |
| **Entity Aggregation** | The registered behavior that maintains denormalized counts and last activity timestamps on Project records as linked entities change. |

---

*This document is a living specification. As the Custom Objects framework evolves, as the Views PRD adds dashboard capabilities, and as domain-specific implementations (gutter business, sales pipeline, consulting) provide feedback, sections will be updated to reflect design decisions, scope adjustments, and lessons learned.*
