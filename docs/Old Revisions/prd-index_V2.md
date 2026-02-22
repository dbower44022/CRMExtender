# CRMExtender — PRD Index

**Last Updated:** 2026-02-17
**Purpose:** Living index of all Product Requirements Documents for CRMExtender. Reference this at the start of any PRD development session for orientation.

---

## Platform Overview

CRMExtender (also called Contact Intelligence Manager) is a comprehensive CRM platform providing deep relationship intelligence and unified communication tracking. The system targets sales professionals, entrepreneurs, and service providers. Key differentiators include unified multi-channel inbox, AI conversation intelligence, cross-channel conversation stitching, and sophisticated relationship tracking.

**Tech Stack:** Flutter frontend (cross-platform), Python FastAPI backend, PostgreSQL (event-sourced), Neo4j (relationship graph), SQLite (offline read), Meilisearch (search).

---

## PRD Status Summary

| PRD | Version | Date | Status | Lines | Chat |
|---|---|---|---|---|---|
| Communication & Conversation Intelligence | 2.0 | 2026-02-07 | Draft — Complete | ~2,800 | Dedicated |
| Contact Management & Intelligence | 1.0 | 2026-02-08 | Draft — Complete | ~4,000 | Dedicated |
| Views & Grid System | 1.1 | 2026-02-16 | Draft — Complete | ~1,600 | Dedicated |
| Data Sources | 1.0 | 2026-02-16 | Draft — Complete | ~1,500 | Dedicated |
| Custom Objects | 1.0 | 2026-02-17 | Draft — Complete | ~1,500 | Dedicated |
| Email Parsing & Content Extraction | — | — | Technical Spec | ~700 | — |
| AI Learning & Classification | — | — | **Not Started** | — | — |
| Permissions & Sharing | — | — | **Not Started** | — | — |
| CRMExtender Platform (Parent) | 1.1 | — | Exists (not in project) | — | — |

---

## Completed PRDs

### 1. Communication & Conversation Intelligence
**File:** `email-conversations-prd.md`
**Scope:** The primary relationship signal layer. Captures communications across email, SMS, phone, video, in-person, and notes. Organizes them into a Project → Topic → Conversation → Communication hierarchy.

**Key sections:**
- Organizational hierarchy (Projects, Topics, Conversations, Communications)
- Unified communication record model across all channels
- Communication segmentation & cross-conversation references
- AI intelligence layer (summarization, status detection, action items)
- Contact association & identity resolution
- Email provider integration (Gmail Tier 1, Outlook Tier 2, IMAP Tier 3)
- Email sync pipeline (initial, incremental, manual)
- Email parsing & content extraction (dual-track: HTML + plain text)
- Triage & intelligent filtering
- Conversation lifecycle & status management (3 independent dimensions)
- Multi-account management
- 4-phase roadmap

**Key decisions made:**
- Direct provider API integration (no Nylas/third-party aggregation)
- Provider adapter pattern normalizes all sources to common Communication schema
- Event sourcing provides audit trails naturally
- iMessage excluded from cross-platform sync (Apple restrictions)
- SMS provider selection still open
- Triage uses heuristic junk detection + known-contact gate

**Reconciliation required by Custom Objects PRD:** Conversation, Communication, Project, and Topic entities need reframing as system object types in the unified framework. Specialized AI behaviors registered per Custom Objects PRD Section 22.

**Open questions:** 12 (SMS provider, speech-to-text service, Slack/Teams model, calendar linking, cross-account merging, attachment storage, and more)

---

### 2. Contact Management & Intelligence
**File:** `contact-management-prd.md`
**Scope:** The foundational entity layer. Defines contacts and companies as living intelligence objects with event-sourced history, multi-identifier identity model, enrichment, OSINT, and relationship intelligence.

**Key sections:**
- Contact data model (materialized view pattern with denormalized fields)
- Company data model
- Identity resolution & entity matching (multi-identifier: email, phone, social)
- Contact lifecycle management (lead status, engagement scoring)
- Contact intelligence & enrichment (Apollo, Clearbit, People Data Labs adapters)
- Relationship intelligence (Neo4j graph, relationship types, influence mapping)
- Behavioral signal tracking (engagement score computation)
- Groups, tags & segmentation
- Contact import & export (CSV, Google Contacts sync)
- AI-powered contact intelligence (briefings, tag suggestions, NL search)
- Event sourcing & temporal history
- API design
- Client-side offline support (SQLite)
- 4-phase roadmap

**Key decisions made:**
- Contacts use UUID v4 (**migration to prefixed ULID queued** — see Reconciliation Items)
- Employment history tracked as separate table with temporal records (**reframe as relation type with metadata queued** — see Reconciliation Items)
- Intelligence items are discrete sourced data points with confidence scores
- Engagement score is a composite behavioral metric (0.0–1.0)
- Intelligence score measures data completeness (0.0–1.0)
- Google People API for bidirectional contact sync (Phase 1)
- Browser extension for LinkedIn/Twitter capture (Phase 2)

**Reconciliation required by Custom Objects PRD:**
- Remove `custom_fields` JSONB column — custom fields on Contacts managed through unified field registry
- Migrate entity IDs from UUID v4 to `con_` prefixed ULIDs
- Reframe `contacts_current` as the Contact object type's dedicated table managed by the object type framework
- Reframe `employment_history` as a system relation type (Contact→Company) with temporal metadata (start_date, end_date, title, department)
- See Custom Objects PRD Section 26.1 for full details

**Open questions:** See PRD Section 23

---

### 3. Views & Grid System
**File:** `views-grid-prd_V2.md` → updated to `views-grid-prd_V3.md`
**Scope:** The primary data interaction layer. Polymorphic, entity-agnostic framework for displaying, filtering, sorting, grouping, and editing any entity type through multiple view types.

**Key sections:**
- Core concepts (Data Source separation, entity-agnostic rendering)
- Data Sources (summary — full spec in Data Sources PRD)
- View types: List/Grid, Calendar, Timeline, Board/Kanban
- Column system (direct, relation traversal, computed)
- Field type registry
- Relation traversal & lookup columns
- Filtering & query builder (compound AND/OR, cross-entity filters)
- Sorting & grouping (multi-level, collapsible, aggregation rows)
- Grid interactions (inline editing, row expansion, bulk actions, keyboard nav)
- Calendar, Board, Timeline view-specific configurations
- View persistence & sharing (personal, shared, fork-on-write)
- View-as-alert integration
- Performance & pagination (virtual scrolling, cursor-based)
- 4-phase roadmap

**Key decisions made:**
- Data Source is a separate layer from View (extracted to own PRD)
- Entity-agnostic: custom objects get same view capabilities as system entities
- View-level filters AND with data source filters (cannot remove/override)
- Shared views enforce row-level security (sharing definition ≠ sharing data)
- Board view supports swimlanes (matrix of group-by × status)
- Tree view capability added (hierarchical rendering)
- Inspired by ClickUp multi-view + Attio object model

**Alignment with Custom Objects PRD:** Views PRD Section 9 (field type rendering) is the presentation layer counterpart to Custom Objects PRD Section 9 (field type data layer). Relation traversal (Views Section 10) operates on Relation Types defined in Custom Objects PRD Section 14. No reconciliation required — both PRDs were designed for alignment.

**Open questions:** 15 (with 7 migrated to Data Sources PRD)

---

### 4. Data Sources
**File:** `data-sources-prd.md` (new, extracted from Views PRD Section 6)
**Scope:** The query abstraction layer. Reusable, named query definitions that sit between physical storage and views, providing cross-entity queries, dual authoring modes, column registries, and preview detection.

**Key sections:**
- Universal entity ID convention (prefixed IDs: `con_`, `cvr_`, `com_`, etc.)
- Data source definition model (ID, query, column registry, preview config, parameters, refresh policy)
- Visual query builder (5-step: entity → joins → columns → filters → sort)
- Raw SQL environment (virtual schema, access rules, validation, parameters)
- Column registry (auto-generated + manual overrides, editability rules)
- Entity detection & preview system (3-layer: auto-detect → inference rules → manual override)
- Data source ↔ view relationship (many-to-one, composition rules)
- Inline editing trace-back (column registry → source entity → API call)
- System-generated data sources (auto-created per entity type)
- Performance (cursor pagination, EXPLAIN plan analysis)
- 4-phase roadmap

**Key decisions made:**
- Prefixed entity IDs (`con_`, `cvr_`, `com_`, etc.) with ULID — adopted platform-wide
- Data sources are reusable across multiple views
- Dual authoring: visual query builder for simple, raw SQL for complex
- Virtual schema mirrors physical schema for query simplicity
- Column registry enables inline editing from any joined query
- System-generated data sources auto-created per entity type
- Schema versioning for breaking change detection

**Alignment with Custom Objects PRD:** Virtual schema composition is resolved — virtual schema tables = object type slugs, virtual schema columns = field slugs. The 1:1 mapping (Custom Objects PRD Section 17.3) means query engine translation is trivial. Schema version counter (Custom Objects PRD Section 6.1) aligns with Data Sources PRD schema versioning for dependent data source notification.

**Open questions:** See PRD Section 21

---

### 5. Custom Objects
**File:** `custom-objects-prd.md`
**Scope:** The entity model foundation. Defines the Unified Object Model where system entities (Contact, Conversation, Company, etc.) and user-created entities are instances of the same framework. Covers object type definition, field registry, field type system, relation model, physical storage architecture, DDL management, and event sourcing.

**Key sections:**
- Unified Object Model (system and custom entities as instances of the same ObjectType framework)
- Object type definition model (identity, slug, type prefix, schema version, lifecycle)
- Universal fields (id, tenant_id, created_at/by, updated_at/by, archived_at)
- Field registry (field definitions, slugs as column names, ordering, limits)
- Field type system (15 Phase 1 types, 2 Phase 2: Formula, Rollup)
- Field type conversion matrix (safe conversions only, with preview wizard)
- Field groups (detail view layout organization)
- Field validation (type-specific constraints, required fields, unique constraints)
- Select & multi-select option management (add, rename, reorder, archive)
- Relation Types as first-class definitions (cardinality, directionality, cascade behavior)
- Relation metadata (additional attributes on relationship instances)
- Neo4j graph sync (optional per relation type, bridging relational and graph models)
- Physical storage: dedicated typed tables per entity type (DDL at runtime)
- DDL Management System (queued execution, locking, validation, rollback, audit)
- Full event sourcing for all entity types (per-entity-type event tables)
- Schema-per-tenant architecture
- System entity specialization (behaviors, protected core fields, extensibility)
- Uniform Record CRUD API and Relation Instance API
- Cross-PRD reconciliation (Contact Management, Data Sources, Views, Communication)
- 4-phase roadmap

**Key decisions made:**
- **Unified Object Model** — system entities are pre-installed object types with is_system flag, protected core fields, and registered behaviors. Custom entities are equal citizens at the storage, query, and rendering layers.
- **Dedicated typed tables per entity type** — every entity type gets its own PostgreSQL table with native typed columns. Fields map to columns. DDL at runtime via ALTER TABLE.
- **Schema-per-tenant** — each tenant gets its own PostgreSQL schema with entity tables, event tables, and junction tables.
- **Full event sourcing for all entity types** — per-entity-type event tables (e.g., `jobs_events`). Same audit trail and point-in-time reconstruction for custom and system entities.
- **First-class Relation Types** — all three cardinalities (1:1, 1:many, many:many) from Phase 1. Bidirectional or unidirectional per relation type. Self-referential supported. Configurable cascade (nullify default, restrict, cascade archive).
- **Relation metadata** — additional attributes on relationship instances (role, strength, start date, notes). Stored on junction tables or companion instance tables.
- **Neo4j graph sync** — optional flag per relation type. Relation instances synced as graph edges. System relations synced Phase 1; custom relation sync Phase 2.
- **Permission-gated entity type creation** — Object Creator permission (not admin-only).
- **50 custom entity types per tenant** limit (system types don't count).
- **200 fields per entity type** limit.
- **Soft delete only** for entity types (archive, never hard delete). System types cannot be archived.
- **Limited safe field type conversions** — conversion matrix with preview wizard. Immutable slug/prefix.
- **Field groups** for detail view organization (purely presentational).
- **Display name field** designation required per entity type (for previews, cards, pickers).

**Gutter business test cases:** Jobs, Properties, Service Areas, Estimates — used as running examples throughout the PRD.

**Open questions:** 12 (DDL timing, field slug reserved words, record limits, field templates, entity type import/export, relation type limits, event retention, multi-line storage, offline SQLite sync, computed defaults, relation type modification, Neo4j selective fields)

---

### 6. Email Parsing & Content Extraction
**File:** `email_stripping.md`
**Scope:** Technical specification for the dual-track email parsing pipeline. Covers HTML structural removal and plain-text regex-based extraction.

**Key sections:**
- HTML cleaning pipeline (quote removal, signature detection, disclaimer stripping)
- Plain-text pipeline (reply pattern detection, valediction-based truncation, standalone signature detection)
- Promotional content detection
- Line unwrapping algorithm
- Provider-specific patterns (Gmail, Outlook, Apple Mail)

**Notes:** This is a technical spec, not a conceptual PRD. More appropriate for Claude Code reference than PRD development sessions.

---

## Planned PRDs (Not Yet Started)

### 7. Permissions & Sharing
**Scope:** Team access controls, role-based permissions, row-level security, shared vs. private data, data visibility rules.

**Referenced by:** Data Sources PRD (row-level security), Views PRD (shared view permissions), Communication PRD (conversation access), Contact Management PRD (contact access), Custom Objects PRD (Object Creator permission, field-level permissions Phase 4)
**Critical dependency for:** Data Sources (query engine security injection), Views (shared view behavior), Custom Objects (entity type creation gating, record-level access)

**Inputs from Custom Objects PRD:**
- Object Creator permission established as a specific permission to be modeled
- Field-level permissions identified as Phase 4 scope
- Schema-per-tenant architecture confirmed as the multi-tenant isolation model
- Record-level access control needed for entity records of all types (system and custom)

**Key questions to resolve:**
- What permission model? (RBAC, ABAC, or hybrid)
- How granular is row-level security? (Entity type level? Record level? Field level?)
- How do shared data sources and views interact with permissions?
- Multi-tenant isolation model (schema-per-tenant confirmed in Communication PRD and Custom Objects PRD)
- How does Object Creator permission integrate with the role/permission model?

---

### 8. AI Learning & Classification
**Scope:** How the system learns from user corrections, classification algorithms, embedding/similarity approaches, model training, confidence scoring.

**Referenced by:** Communication PRD (establishes that learning happens), Views PRD (AI fields as queryable columns), Custom Objects PRD (auto-classification of custom entity select fields as future Phase 3+)
**Depends on:** Communication PRD (correction signals), Contact Management PRD (entity context), Custom Objects PRD (entity type awareness, field type system)

**Key questions to resolve:**
- What ML models power auto-classification of conversations to topics/projects?
- How are user corrections fed back into the model?
- What confidence thresholds trigger auto-assignment vs. human review?
- How is training data managed per tenant?
- Can auto-classification extend to custom entity select fields? (Custom Objects PRD Phase 3+ consideration)

---

## Dependency Map

```
                    ┌─────────────────────┐
                    │  CRMExtender PRD    │
                    │  (Parent v1.1)      │
                    └─────────┬───────────┘
                              │
          ┌───────────────────┼───────────────────┐
          │                   │                   │
          ▼                   ▼                   ▼
┌─────────────────────┐ ┌─────────────────────┐ ┌─────────────────────┐
│  Communication      │ │  Contact            │ │  Custom Objects     │
│  & Conversation     │ │  Management &       │ │  ★ FOUNDATION       │
│  Intelligence       │ │  Intelligence       │ │                     │
│                     │ │                     │ │  Entity types,      │
│  System entity      │ │  System entity      │ │  field registry,    │
│  types: Conversation│ │  types: Contact,    │ │  relations, storage,│
│  Communication,     │ │  Company            │ │  event sourcing     │
│  Project, Topic     │ │                     │ │                     │
└────────┬────────────┘ └────────┬────────────┘ └────────┬────────────┘
         │                       │                       │
         │  ┌────────────────────┤                       │
         │  │                    │                       │
         ▼  ▼                    │                       │
┌─────────────────────┐         │                       │
│  Data Sources        │◄────────┼───────────────────────┘
│                      │         │   Virtual schema from object type
│  Virtual schema,     │         │   field registries, relation model
│  query engine,       │         │
│  column registries   │         │
└────────┬─────────────┘         │
         │                       │
         ▼                       │
┌─────────────────────┐         │
│  Views & Grid        │         │
│  System              │         │
│                      │         │
│  Field rendering,    │         │
│  relation traversal  │         │
└────────┬─────────────┘         │
         │                       │
         │    ┌──────────────────┘
         ▼    ▼
┌─────────────────────┐         ┌─────────────────────┐
│  Permissions &       │         │  AI Learning &       │
│  Sharing             │         │  Classification      │
│  (PLANNED — #1       │         │  (PLANNED — #2       │
│   priority)          │         │   priority)          │
└─────────────────────┘         └─────────────────────┘
```

**Reading the arrows:** An arrow from A to B means "A depends on B" or "A references B."

**★ Custom Objects as foundation:** The Custom Objects PRD defines the entity model that Data Sources, Views, Contact Management, and Communication all build upon. It is the most cross-cutting completed PRD — all entity types (system and custom) are defined through its framework.

---

## Cross-PRD Decisions & Reconciliation Items

### Resolved Items

| Item | PRDs Involved | Resolution |
|---|---|---|
| **Prefixed entity IDs** | Data Sources, Custom Objects, Contact Management | **Resolved by Custom Objects PRD.** Section 6.2–6.3 establishes type prefix registry, generation algorithm, and collision handling. All entity types use `{prefix}_{ULID}` format. Contact Management PRD update queued to migrate from UUID v4 to `con_` prefixed ULIDs. |
| **Event sourcing read model** | Data Sources, Contact Management, Communication, Custom Objects | **Resolved by Custom Objects PRD.** Section 17 establishes dedicated typed tables as read models. Section 19 establishes per-entity-type event tables. Unified pattern for all entity types (system and custom). |
| **Custom entity storage** | Data Sources, Custom Objects | **Resolved by Custom Objects PRD.** Dedicated typed tables per entity type with DDL-at-runtime (Section 17–18). Virtual schema maps 1:1 to physical schema (Section 17.3). |
| **Virtual schema composition** | Data Sources, Custom Objects | **Resolved by Custom Objects PRD.** Virtual schema tables = object type slugs. Virtual schema columns = field slugs. Query engine translation is trivial. |

### Queued Reconciliation (requires PRD updates)

| Item | PRDs Involved | Status | Details |
|---|---|---|---|
| **Contact Management `custom_fields` removal** | Contact Management, Custom Objects | **Queued** | Remove `custom_fields` JSONB column from contacts table. Custom fields on Contacts managed through unified field registry. See Custom Objects PRD Section 26.1. |
| **Contact entity ID migration** | Contact Management, Custom Objects, Data Sources | **Queued** | Migrate Contact IDs from UUID v4 to `con_` prefixed ULIDs. Migration path: add `con_` prefix to existing UUIDs or re-generate. |
| **Employment history → Relation Type** | Contact Management, Custom Objects | **Queued** | Reframe `employment_history` table as a system relation type (Contact→Company) with temporal metadata (start_date, end_date, title, department). Relation type has `has_metadata = true`. |
| **`contacts_current` → Object Type table** | Contact Management, Custom Objects | **Queued** | Reframe `contacts_current` as the Contact object type's dedicated table, created by tenant schema provisioning through the object type framework. Core columns become system fields (`is_system = true`). |
| **Communication entities → System Object Types** | Communication, Custom Objects | **Queued** | Conversation, Communication, Project, Topic entities need reframing as system object types in the unified framework. Tables created by tenant schema provisioning. Specialized behaviors registered per Custom Objects PRD Section 22. |

### Open Items

| Item | PRDs Involved | Status | Notes |
|---|---|---|---|
| **Alert system ownership** | Communication, Views, Data Sources | **Needs clarification** | Communication PRD defines alerts. Views PRD defines view-to-alert promotion. Data Sources PRD defines queries that alerts execute. The alert execution engine's home PRD should be clarified. |
| **Permissions model** | All PRDs | **Blocked on Permissions PRD** | Every PRD references permissions. Custom Objects PRD introduces Object Creator permission (Section 6.4) and identifies field-level permissions as Phase 4. The full permission model awaits the Permissions PRD. |

---

## Suggested PRD Development Order

Based on dependency analysis (Custom Objects now complete):

1. **Permissions & Sharing** — Most cross-cutting remaining dependency. Every PRD references it. Custom Objects PRD provides specific inputs: Object Creator permission, field-level permissions (Phase 4), schema-per-tenant architecture, record-level access control for all entity types.
2. **AI Learning & Classification** — Depends on Communication PRD signals, Contact Management context, and Custom Objects entity type awareness. Can be written once the permission model is stable.
3. **Contact Management PRD v2** — Update to align with Custom Objects unified framework (queued reconciliation items above). Not a new PRD, but a significant revision.

---

## Workflow Notes

**PRD Development:** Use dedicated Claude.ai chats (this project) for conceptual PRD development. One chat per PRD for clean context.

**Implementation Planning:** Use Claude Code for implementation plans against the actual codebase. Claude Code reads PRDs and maps concepts to real code.

**Decision Flow:** When Claude Code makes architectural decisions that resolve PRD open questions or affect PRD assumptions, capture them as updates to this index (Cross-PRD Decisions table) or as memory edits.

---

*This index is updated after each PRD development session. It serves as the starting context for any new PRD chat.*
