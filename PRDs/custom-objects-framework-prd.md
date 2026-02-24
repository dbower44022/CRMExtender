# Custom Objects — Framework PRD

**Version:** 1.0
**Last Updated:** 2026-02-23
**Status:** Draft
**Product PRD:** [CRMExtender Product PRD]

---

## 1. Purpose

The Custom Objects framework is the entity model foundation of CRMExtender. It defines what things exist in the system — Contacts, Conversations, Companies, and any user-created entity type — and what attributes they have. Every other subsystem depends on this: Views renders entity fields, Data Sources queries across entity types, Communications resolves participants to entity records, and the relationship intelligence layer models graph connections.

This PRD establishes a **Unified Object Model** where system entities and user-created entities are instances of the same framework. A Contact is not a special snowflake with hand-crafted storage — it is an object type that happens to be pre-installed, with core fields protected from deletion and specialized behaviors that custom entities don't have. A user-created "Jobs" entity type works identically to Contacts at the storage, query, field, and relation layers.

### 1.1 Core Principles

- **Unified Object Model** — System and custom entities are instances of the same ObjectType framework. No first-class vs. second-class distinction at storage, query, or rendering layers.
- **Dedicated typed tables** — Every entity type gets its own PostgreSQL table with native typed columns. Maximum query performance, full type safety, native indexing.
- **Full event sourcing** — Every entity type has a companion event table recording all field-level mutations as immutable events. Audit trails, point-in-time reconstruction, undo/revert — uniformly.
- **First-class Relation Types** — Relationships are explicitly defined with cardinality, directionality, cascade behavior, optional metadata, and optional Neo4j graph sync.
- **Schema-per-tenant isolation** — Each tenant gets its own PostgreSQL schema. Custom fields added by one tenant don't affect another.
- **DDL-as-a-service** — Adding fields, creating entity types, and defining relations trigger safe, queued DDL operations with locking, validation, and rollback.

### 1.2 Performance Targets

| Metric | Target |
|---|---|
| Object type list load | < 100ms |
| Field registry load | < 100ms |
| Record CRUD (any entity type) | < 200ms |
| DDL operation (add column) | < 2s |
| Event history load (50 events) | < 200ms |

---

## 2. Architecture Overview

```
┌──────────────────────────────────────────────────────────────────────────┐
│                    OBJECT TYPE FRAMEWORK (this PRD)                      │
│                                                                          │
│  ┌─────────────────────┐  ┌──────────────────────┐                      │
│  │  Object Type        │  │   Relation Type       │                      │
│  │  Registry           │  │   Registry            │                      │
│  │  ─────────────────  │  │  ──────────────────── │                      │
│  │  System types       │  │  Cardinality          │                      │
│  │  Custom types       │  │  Directionality       │                      │
│  │  Field registries   │  │  Cascade behavior     │                      │
│  │  Field groups       │  │  Metadata attributes  │                      │
│  │  Behaviors          │  │  Neo4j sync flag      │                      │
│  └────────┬────────────┘  └──────────┬───────────┘                      │
│           │                          │                                   │
│           ▼                          ▼                                   │
│  ┌──────────────────────────────────────────────┐                       │
│  │           DDL Management System               │                       │
│  │  CREATE TABLE, ALTER TABLE ADD COLUMN,         │                       │
│  │  CREATE junction tables, manage indexes         │                       │
│  │  Queued execution, locking, validation          │                       │
│  └────────────────────┬─────────────────────────┘                       │
│                       │                                                  │
│                       ▼                                                  │
│  ┌──────────────────────────────────────────────┐                       │
│  │        Physical Storage (per tenant schema)   │                       │
│  │  tenant_abc.contacts       (read model)       │                       │
│  │  tenant_abc.contacts_events (event store)     │                       │
│  │  tenant_abc.jobs           (custom read model) │                       │
│  │  tenant_abc.jobs_events    (custom event store)│                       │
│  │  tenant_abc.jobs__contacts (junction table)   │                       │
│  └──────────────────────────────────────────────┘                       │
└──────────────────────────────────────────────────────────────────────────┘
         │                          │                        │
         ▼                          ▼                        ▼
┌─────────────────┐  ┌──────────────────────┐  ┌──────────────────────┐
│  Data Sources   │  │    Views & Grid      │  │  Entity PRDs         │
│  PRD            │  │    PRD               │  │  (Contact, Company,  │
│  Virtual schema │  │  Field type          │  │   Conversation, etc.)│
│  from field     │  │  rendering from      │  │  Behaviors registered│
│  registries     │  │  field registry      │  │  with framework      │
└─────────────────┘  └──────────────────────┘  └──────────────────────┘
```

---

## 3. Object Type Definition Model

An Object Type is a first-class meta-entity stored in a platform-level registry table outside tenant schemas.

### 3.1 Object Type Attributes

| Attribute | Type | Constraints | Description |
|---|---|---|---|
| `id` | TEXT | PK | `oty_` prefixed ULID. Immutable. |
| `tenant_id` | TEXT | NOT NULL, FK | Owning tenant. System types have platform tenant ID. |
| `name` | TEXT | NOT NULL | Display name, renamable. |
| `slug` | TEXT | NOT NULL, UNIQUE per tenant | Machine name, immutable after creation. Used in API paths and virtual schema. |
| `type_prefix` | TEXT | NOT NULL, UNIQUE globally | 3–4 character prefix for entity IDs. Immutable. |
| `description` | TEXT | | Optional description |
| `icon` | TEXT | | Optional icon identifier |
| `display_name_field_id` | TEXT | FK → fields | Which field serves as record title. Required. |
| `is_system` | BOOLEAN | NOT NULL, DEFAULT false | Pre-installed system entity type |
| `is_archived` | BOOLEAN | NOT NULL, DEFAULT false | Soft-delete. System types cannot be archived. |
| `schema_version` | INTEGER | NOT NULL, DEFAULT 1 | Incremented on field registry changes |
| `field_limit` | INTEGER | DEFAULT 200 | Max user-defined fields |
| `created_by` | TEXT | FK → users | |
| `created_at` | TIMESTAMPTZ | NOT NULL | |
| `updated_at` | TIMESTAMPTZ | NOT NULL | |

### 3.2 Type Prefix Generation

1. Take first 3–4 characters of slug (e.g., `jobs` → `job`, `properties` → `prop`)
2. Check for collisions against all existing prefixes (system and custom, all tenants)
3. If collision, modify until unique (e.g., `job_` → `jobs_`, `jbs_`)
4. Prefix is immutable once assigned — renaming object type doesn't change it

### 3.3 System Object Type Prefix Registry

| Object Type | Prefix | Slug |
|---|---|---|
| Contact | `con_` | `contacts` |
| Company | `cmp_` | `companies` |
| Conversation | `cvr_` | `conversations` |
| Communication | `com_` | `communications` |
| Project | `prj_` | `projects` |
| Event | `evt_` | `events` |
| Note | `nte_` | `notes` |
| Task | `tsk_` | `tasks` |
| Document | `doc_` | `documents` |
| Data Source | `dts_` | `data_sources` |
| View | `viw_` | `views` |
| User | `usr_` | `users` |
| Segment | `seg_` | `segments` |

### 3.4 Permissions

Creating custom object types requires the **Object Creator** permission — a discrete permission grantable to any role. Administrators have it by default. Rationale: creating entity types triggers DDL and allocates schema resources — should be intentional.

### 3.5 Limits

Each tenant may have a maximum of **50 custom object types** (system types don't count). At 50 × 200 fields × dedicated tables with indexes, the per-tenant schema contains ~100 tables plus junction tables. PostgreSQL handles this comfortably. Limit is adjustable per tenant for enterprise plans.

---

## 4. Universal Fields

Every object type — system and custom — has universal fields managed automatically by the framework. Cannot be removed, renamed, or have types changed.

| Field | Column | Type | Description |
|---|---|---|---|
| ID | `id` | TEXT, PK | Prefixed ULID. Immutable. |
| Tenant | `tenant_id` | TEXT, NOT NULL | Tenant isolation. Immutable. |
| Created At | `created_at` | TIMESTAMPTZ, NOT NULL | Record creation. Immutable. |
| Updated At | `updated_at` | TIMESTAMPTZ, NOT NULL | Last modification. Auto-updated. |
| Created By | `created_by` | TEXT, FK → users | Creator. NULL for system-generated. |
| Updated By | `updated_by` | TEXT, FK → users | Last modifier. |
| Archived At | `archived_at` | TIMESTAMPTZ, NULL | Soft-delete. NULL = active. |

### 4.1 Display Name Field

Every object type must designate exactly one user-defined field as the **display name field** — the record's human-readable title used throughout the platform (view rows, relation pickers, card headers, search results, calendar labels).

On custom object type creation, the system creates a default `name` field (Text, single-line, required) and designates it. The user can change which field serves as display name, but the designation cannot be empty.

---

## 5. System Entity Specialization

System object types are unified framework instances with two additional capabilities:

### 5.1 Behaviors

A behavior is registered specialized logic that the platform executes in response to events on a specific system entity type. Behaviors are defined in their respective entity PRDs and registered with this framework.

| System Entity | Behaviors | Source PRD |
|---|---|---|
| Contact | Identity resolution, auto-enrichment, engagement score, intelligence score | Contact Entity Base PRD |
| Company | Firmographic enrichment | Company Entity Base PRD |
| Conversation | AI status detection, summarization, action item extraction | Conversation Entity Base PRD |
| Communication | Email parsing, content extraction, segmentation | Communication Entity Base PRD |
| Project | Entity aggregation, last activity computation, sub-project cascade | Project Entity Base PRD |
| Event | Attendee resolution, birthday auto-generation, recurrence defaulting | Event Entity Base PRD |
| Note | Revision management, FTS sync, mention extraction, orphan cleanup, visibility enforcement | Note Entity Base PRD |
| Task | Status category enforcement, subtask cascade, subtask count sync, recurrence generation, AI extraction, due date reminders, overdue detection | Task Entity Base PRD |

Custom object types do NOT have behaviors.

### 5.2 Protected Core Fields

System entity types have core fields marked `is_system = true`:
- Cannot be archived or deleted
- Cannot have type converted
- Cannot have slug changed
- CAN have display name changed and validation rules adjusted

### 5.3 Extensibility

Users can add custom fields to system entity types through the standard field registry mechanism. User-added fields store as additional columns and participate fully in views, data sources, filters, and event sourcing.

---

## 6. Object Type Lifecycle

### 6.1 Creation

1. User with Object Creator permission defines: name, description, icon
2. System generates slug (from name, lowercased, underscored) and type prefix
3. System validates: slug uniqueness within tenant, prefix uniqueness globally
4. DDL Management System creates: read model table, event table, system indexes
5. System creates default `name` field and designates as display name
6. System creates auto-generated Data Source for the new entity type
7. Object type appears in entity type pickers throughout the platform

### 6.2 Modification

- **Rename (display name):** Immediate metadata update. No DDL.
- **Change description/icon:** Immediate. No DDL.
- **Add field:** DDL operation. Schema version incremented.
- **Archive field:** Field hidden from UI. Column preserved. Schema version incremented.
- **Add/modify/remove field group:** Metadata update only. No DDL.
- **Change display name field:** Metadata update. No DDL.

### 6.3 Archiving

Custom entity types can be archived. System types cannot.

1. `is_archived` set to true
2. Hidden from: entity type pickers, Data Source selectors, View creation, record creation forms
3. Existing views/data sources show warning badge: "This entity type is archived"
4. Database tables and data preserved intact
5. New records cannot be created; existing records viewable and searchable
6. Counts against per-tenant limit (prevents archive/create cycling)

### 6.4 Unarchiving

1. `is_archived` set to false
2. Reappears in all pickers and selectors
3. Warning badges removed
4. Record creation re-enabled

---

## 7. Key Processes

### KP-1: Creating a Custom Object Type

**Trigger:** User with Object Creator permission initiates creation.

**Step 1 — Define:** Name, description, icon.

**Step 2 — Generate:** System creates slug and prefix.

**Step 3 — Validate:** Uniqueness checks.

**Step 4 — DDL:** Create read model table, event table, indexes.

**Step 5 — Default field:** Create `name` field as display name.

**Step 6 — Data Source:** Auto-generate entity Data Source.

### KP-2: Adding Fields to an Object Type

**Trigger:** User adds a field via object type settings.

**Step 1 — Define:** Display name, field type, config, validation.

**Step 2 — Generate slug:** From display name.

**Step 3 — DDL:** ALTER TABLE ADD COLUMN.

**Step 4 — Schema version:** Increment.

**Step 5 — Notify dependents:** Views and Data Sources detect schema change.

### KP-3: Creating a Relation Type

**Trigger:** User defines a relationship between two object types.

**Step 1 — Define:** Source, target, cardinality, directionality, cascade.

**Step 2 — DDL:** Create junction table (M:M) or add FK column (1:1, 1:M).

**Step 3 — Create fields:** Relation fields on source (and target if bidirectional).

**Step 4 — Optional:** Configure metadata fields, Neo4j sync.

### KP-4: CRUD Operations on Records

**Trigger:** User creates, reads, updates, or archives a record of any entity type.

**Step 1 — Validate:** Required fields, type constraints, validation rules.

**Step 2 — Write:** Update read model table.

**Step 3 — Event:** Write immutable event to entity's event table.

**Step 4 — Behaviors:** Fire registered behaviors (system types only).

**Step 5 — Sync:** Neo4j sync if applicable, Data Source cache invalidation.

---

## 8. Action Catalog

### 8.1 Object Type Management

**Supports processes:** KP-1
**Trigger:** User creates, modifies, archives, or restores object types.
**Outcome:** Entity type registered, tables provisioned, available in platform.

### 8.2 Field System

**Summary:** Field registry, field types (Phase 1 & 2), type conversions, field groups, validation, Select/Multi-Select options, field lifecycle.
**Sub-PRD:** [custom-objects-field-system-prd.md]

### 8.3 Relation System

**Summary:** Relation Type definitions (cardinality, directionality, cascade), physical implementation (FK vs. junction), self-referential relations, relation metadata, Neo4j graph sync.
**Sub-PRD:** [custom-objects-relation-system-prd.md]

### 8.4 Record CRUD

**Supports processes:** KP-4
**Trigger:** Any record operation on any entity type.
**Outcome:** Uniform create/read/update/archive with event sourcing and behavior dispatch.

---

## 9. Open Questions

1. **DDL during high-traffic:** Defer non-urgent DDL to off-peak hours? PostgreSQL 11+ instant ADD COLUMN mitigates, but type conversions are heavier.
2. **Field slug reserved words:** Validate against PostgreSQL reserved words. Also reserve application-level keywords (`type`, `class`, `status`)?
3. **Custom entity record limits:** Per-entity-type or per-tenant record count limit? Low-thousands unlikely to be an issue.
4. **Cross-entity field templates:** Define once, apply to many entity types? Or is copy-paste sufficient?
5. **Entity type import/export:** Export definitions as JSON for template sharing and environment replication?
6. **Relation type limits:** Cap on relation types per entity type or per tenant?
7. **Event store retention:** Configurable retention policy for high-volume entities?
8. **Multi-line text storage:** TOAST-optimized strategy or standard TEXT?
9. **Offline SQLite sync:** Custom entities sync to SQLite for mobile/desktop?
10. **Computed default values:** Support expressions (TODAY(), CURRENT_USER()) beyond static values?
11. **Relation Type modification:** Block cardinality changes after creation? Recommend new relation + migration.
12. **Neo4j selective field sync:** All fields, display name only, or user-configurable subset?

---

## 10. Design Decisions

### Why Unified Object Model?

Dual code paths for system vs. custom entities would double maintenance. Every platform capability — views, data sources, filters, event sourcing — works uniformly because all entities are ObjectType instances.

### Why dedicated typed tables instead of EAV?

Entity-Attribute-Value stores sacrifice query performance, type safety, and indexing. Dedicated tables with native columns enable standard SQL, native PostgreSQL indexes, and the simplest virtual-to-physical schema translation.

### Why schema-per-tenant?

Custom fields by one tenant must not affect another's schema. Schema isolation provides the strongest guarantee without row-level filtering overhead.

### Why DDL-as-a-service?

User actions (add field, create entity type) trigger ALTER TABLE/CREATE TABLE. Safe queued execution with locking prevents concurrent DDL conflicts and provides rollback on failure.

### Why no behaviors for custom entities?

Behaviors are specialized logic requiring engineering effort per entity type. Custom entities are user-defined and unpredictable. Behaviors are reserved for system entities where the platform understands the domain semantics.

### Why 200 field limit?

PostgreSQL can handle wider tables, but 200 fields per entity type provides ample room while preventing schema bloat. Archived fields don't count against the limit.

### Why field archiving instead of deletion?

Event sourcing requires field slugs to remain meaningful in the historical event stream. Archived fields preserve data and history while hiding from UI.

### Why immutable slugs and prefixes?

Slugs map to physical column names and API paths. Prefixes are embedded in entity IDs. Changing either would break stored data, URLs, and integrations.

---

## Related Documents

| Document | Relationship |
|---|---|
| [Custom Objects TDD](custom-objects-tdd.md) | Physical storage, DDL system, event sourcing, schema-per-tenant, API |
| [Field System Sub-PRD](custom-objects-field-system-prd.md) | Field registry, types, validation, groups, Select options |
| [Relation System Sub-PRD](custom-objects-relation-system-prd.md) | Relation Types, metadata, Neo4j sync |
| [Views & Grid PRD](views-grid-prd.md) | Consumes field registry for rendering |
| [Data Sources PRD](data-sources-prd.md) | Consumes entity types for virtual schema |
| [All Entity Base PRDs] | System object types registered with this framework |
| [Master Glossary](glossary.md) | Term definitions |
