# Product Requirements Document: Data Sources

## CRMExtender — Data Source & Query Abstraction Layer

**Version:** 1.0
**Date:** 2026-02-16
**Status:** Draft
**Parent Document:** [CRMExtender PRD v1.1](PRD.md)

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Problem Statement](#2-problem-statement)
3. [Goals & Success Metrics](#3-goals--success-metrics)
4. [User Personas & Stories](#4-user-personas--stories)
5. [Core Concepts & Terminology](#5-core-concepts--terminology)
6. [Universal Entity ID Convention](#6-universal-entity-id-convention)
7. [Data Source Definition Model](#7-data-source-definition-model)
8. [Query Definition: Visual Builder](#8-query-definition-visual-builder)
9. [Query Definition: Raw SQL](#9-query-definition-raw-sql)
10. [Column Registry](#10-column-registry)
11. [Entity Detection & Preview System](#11-entity-detection--preview-system)
12. [Preview Resolution at Runtime](#12-preview-resolution-at-runtime)
13. [Data Source ↔ View Relationship](#13-data-source--view-relationship)
14. [Inline Editing Trace-Back](#14-inline-editing-trace-back)
15. [Query Engine](#15-query-engine)
16. [Cache, Refresh & Invalidation](#16-cache-refresh--invalidation)
17. [Data Source Lifecycle & Versioning](#17-data-source-lifecycle--versioning)
18. [Schema Evolution & Migration](#18-schema-evolution--migration)
19. [Data Source API](#19-data-source-api)
20. [Data Source Permissions & Security](#20-data-source-permissions--security)
21. [System-Generated Data Sources](#21-system-generated-data-sources)
22. [Data Source Examples](#22-data-source-examples)
23. [Performance Considerations](#23-performance-considerations)
24. [Phasing & Roadmap](#24-phasing--roadmap)
25. [Dependencies & Related PRDs](#25-dependencies--related-prds)
26. [Open Questions](#26-open-questions)
27. [Glossary](#27-glossary)

---

## 1. Executive Summary

The Data Source layer is the query abstraction foundation of CRMExtender. It sits between the physical data storage and the rendering layer (Views), providing a reusable, named, composable query definition that answers the question: **"What data should I see?"**

A Data Source is a first-class entity in the system. It encapsulates a query — built visually or written as raw SQL — that defines which entity types are involved, how they relate to each other via JOINs, which columns are available, what base filters and sort orders apply, and which entities in the result set can be previewed and navigated to. Multiple Views can share a single Data Source, each rendering the same underlying result set as a List/Grid, Board, Calendar, Timeline, or Tree — with its own view-level configuration layered on top.

This separation is the architectural cornerstone that enables CRMExtender's polymorphic view system. Without it, every view would independently define its own query — duplicating logic, diverging over time, and making cross-entity analysis impractical.

**Core design principles:**

- **Reusability** — One query, many renderings. A "Deal Pipeline" data source powers a Board view, a List view, a Calendar view, and a Timeline view simultaneously. Change the data source once, all four views reflect the update.
- **Separation of concerns** — Data source authors think about *what data to fetch*. View authors think about *how to present it*. Different skills, different workflows, composable results.
- **Cross-entity queries** — Data sources JOIN across entity types, producing denormalized result sets that combine data from Conversations, Contacts, Companies, Projects, and any custom entities. This is the key to answering questions like "show me all conversations with their contact's company and industry."
- **Dual authoring modes** — The visual query builder serves most users; raw SQL serves power users and analysts. Both produce the same Data Source artifact with the same column registry, preview configuration, and view compatibility.
- **Entity-agnostic** — The data source system doesn't privilege system entities over custom entities. A data source querying a user-created "Jobs" entity works identically to one querying Contacts or Conversations.
- **Security by design** — Data sources are query *definitions*, not query *results*. The same shared data source returns different results for different users based on their tenant, permissions, and row-level access controls. Sharing a data source is always safe.

**Relationship to other subsystems:** This PRD defines the data retrieval and query abstraction layer. It is consumed by the [Views & Grid PRD](views-grid-prd_V5.md) (which defines how data source results are rendered and interacted with), depends on the Custom Objects PRD (which defines what entity types and fields exist to query), and is referenced by the Communication & Conversation Intelligence PRD (whose alert system uses data source queries as triggers).

---

## 2. Problem Statement

### The Query Gap

CRM systems generate enormous amounts of structured data — contacts, conversations, deals, projects, communications, custom records — but accessing that data in flexible, composable, reusable ways is surprisingly hard.

**The consequences for CRM users:**

| Pain Point | Impact |
|---|---|
| **Queries are locked inside views** | Each view defines its own data retrieval logic. Want the same dataset as a list AND a board? Build the query twice. If the query changes, update both. |
| **No cross-entity queries** | Viewing Contacts doesn't show their Conversation counts, Project involvement, or Communication frequency without navigating to each record. Answering "which contacts have open conversations at companies in the tech industry?" requires manual cross-referencing. |
| **Power users have no escape hatch** | Visual query builders handle common cases but cannot express complex analytics: CTEs, window functions, conditional aggregations. Power users export to spreadsheets or BI tools. |
| **No query reuse or governance** | A team of 10 people builds 30 slightly different versions of "Active Deal Pipeline." There's no way to create a single, well-optimized query definition and share it across the team. |
| **Query changes break things silently** | When the underlying data model changes (a field is renamed, an entity gains new fields), every view's embedded query may silently break or return stale schemas. There's no versioning, no impact detection, no migration path. |

### Why a Separate Data Source Layer

The data source exists as a distinct architectural layer — not embedded in views, not a database concept, not a report builder — because it serves a unique role:

- **More than a database view** — Data sources include column metadata, preview configuration, parameter definitions, editability rules, and version tracking. A database view has none of these.
- **More than a report query** — Data sources feed interactive views with inline editing, entity navigation, and real-time filtering. Reports are read-only snapshots.
- **Less than a full ETL pipeline** — Data sources query the existing entity model in real-time. They don't transform, load, or materialize data into new structures. The boundary is clear: data sources *read* and *shape*; entity APIs *write*.

---

## 3. Goals & Success Metrics

### Primary Goals

1. **Reusable query definitions** — Users create a data source once and power multiple views from it. Changes to the data source propagate to all dependent views automatically.
2. **Cross-entity query capability** — Data sources JOIN across any combination of system and custom entity types, producing rich, denormalized result sets.
3. **Dual authoring modes** — A visual query builder for most users and raw SQL for power users, both producing identical Data Source artifacts.
4. **Automatic column and preview detection** — The system infers column types, source entity mappings, and previewable entities from the query structure, requiring minimal manual configuration.
5. **Inline editing trace-back** — Edits made in views powered by cross-entity data sources trace back to the correct source entity and field, enabling writes through the read layer.
6. **Safe sharing** — Data sources can be shared with teams without exposing data the viewer shouldn't see. The query definition is shared; the results are always filtered by the viewer's permissions.
7. **Schema resilience** — When entity types or fields change, data sources detect the impact, warn owners, and degrade gracefully rather than failing silently.
8. **Performant execution** — The query engine executes data source queries within strict time and result-size boundaries, with caching and deduplication to minimize redundant computation.

### Success Metrics

| Metric | Target | Measurement |
|---|---|---|
| Data source creation rate | >2 custom data sources per user within first 30 days | Analytics: data source creation events (excluding system-generated) |
| Cross-entity data source adoption | >30% of custom data sources include at least one JOIN | Analytics: JOIN count per data source |
| Data source reuse | >20% of data sources are referenced by 2+ views | Analytics: view-to-data-source ratio |
| Raw SQL adoption | >10% of data sources use raw SQL mode | Analytics: query mode distribution |
| Preview detection accuracy | >95% of auto-detected preview entities are correct (not overridden by users) | Analytics: manual override rate as inverse proxy |
| Data source query time | <2s for 95th percentile of data source executions | Instrumented backend measurement |
| Data source sharing adoption | >15% of teams have at least one shared data source within 30 days | Analytics: shared data source count per team |
| Schema change recovery | >90% of data sources affected by schema changes are repaired within 24 hours | Analytics: time from schema version warning to resolution |

---

## 4. User Personas & Stories

### Personas

| Persona | Data Source Needs | Key Scenarios |
|---|---|---|
| **Alex — Sales Rep** | Cross-entity views of deals with contact and company context. Needs data sources that join Conversations + Contacts + Companies without writing SQL. | "I want a data source that shows all my open conversations with the contact's company and industry so I can build a Board view, a List view, and a Calendar view from the same query." |
| **Maria — Consultant** | Activity reports and relationship summaries. Needs aggregate data sources showing communication frequency, staleness indicators, and relationship health. | "I need a data source that counts each Contact's conversations and shows their last activity date, so I can build a 'Stale Relationships' view filtered to >30 days inactive." |
| **Jordan — Team Lead** | Team-wide dashboards. Needs shared data sources that the whole team uses, with row-level security ensuring each person sees only their data. | "I want to create one 'Team Pipeline' data source and share it. When Alex opens a view on it, he sees his deals. When I open the same view, I see everyone's deals." |
| **Sam — Gutter Cleaning Business Owner** | Custom entity queries. Needs data sources for user-created "Jobs," "Service Areas," and "Properties" entities, with joins to Contacts and Companies. | "I created a Jobs entity with fields for city, price, and status. I want a data source that joins Jobs to Contacts so I can see which customer each job belongs to." |
| **Taylor — Data Analyst** | Complex analytical queries. Needs raw SQL with CTEs, window functions, and conditional aggregations to produce insights the visual builder can't express. | "I need a data source that ranks each Contact by their conversation recency using ROW_NUMBER(), shows a staleness indicator via CASE WHEN, and filters to only the most recent conversation per contact." |

### User Stories

#### Data Source Creation

- **US-DS1:** As a user, I want to create a data source using a visual query builder so that I can define what data my views display without writing SQL.
- **US-DS2:** As a power user, I want to write raw SQL data sources so that I can express complex queries with CTEs, window functions, and aggregations.
- **US-DS3:** As a user, I want to create a data source that JOINs across multiple entity types (e.g., Conversations + Contacts + Companies) so that I can see cross-entity context in a single view.

#### Reuse & Sharing

- **US-DS4:** As a user, I want multiple views to share the same data source so that I can render the same dataset as a List, Board, and Calendar without duplicating the query.
- **US-DS5:** As a user, I want to share data sources with my team so that others can build views on well-crafted queries without needing to understand the underlying data model.
- **US-DS6:** As a team member, I want shared data sources to respect my data permissions — I should only see records I'm authorized to access, regardless of who created the data source.

#### Configuration & Intelligence

- **US-DS7:** As a user, I want the system to auto-detect which entity types are in my data source results so that I can preview any entity from a row click.
- **US-DS8:** As a user, I want to optionally override the preview priority when the auto-detection doesn't match my intent (e.g., prioritize Company over Contact).
- **US-DS9:** As a user, I want data sources with parameters (e.g., date range, current user) so that the same query adapts to different contexts.
- **US-DS10:** As a user, I want inline editing in views powered by cross-entity data sources to trace back and update the correct source entity.

#### View Integration

- **US-DS11:** As a user, I want to add view-level filters on top of the data source's base filters so that different views of the same data source can show different subsets.
- **US-DS12:** As a user, I want the data source's column registry to tell views exactly what columns are available, what types they are, and whether they're editable — so views can render correctly without guessing.

#### Lifecycle & Governance

- **US-DS13:** As a user, I want to be warned when a data source I depend on has a schema change that might affect my views, so I can review and adjust before things break.
- **US-DS14:** As a user, I want to duplicate an existing data source to create a variation, rather than building a new query from scratch.
- **US-DS15:** As a visual builder user, I want to "eject" my query to raw SQL when I outgrow the builder's capabilities, preserving all my current configuration.

---

## 5. Core Concepts & Terminology

### 5.1 Conceptual Model

```
Entity Types (from Object Model)
  ├── Contacts (con_)     — Field Registry: [Name, Email, Phone, Company, ...]
  ├── Conversations (cvr_) — Field Registry: [Subject, AI Status, Last Activity, ...]
  ├── Companies (cmp_)     — Field Registry: [Name, Industry, Revenue, ...]
  ├── Projects (prj_)      — Field Registry: [Name, Status, Owner, ...]
  └── Custom: Jobs (job_)  — Field Registry: [Address, Service Type, Price, ...]

Data Sources (reusable query definitions)
  ├── Data Source: "Deal Pipeline" (dts_9a2b...)
  │     ├── Query: Conversations JOIN Contacts JOIN Companies
  │     ├── Columns: [Subject, AI Status, Contact Name, Company, Industry]
  │     ├── Default Filter: AI Status ≠ Closed
  │     ├── Default Sort: Last Activity DESC
  │     └── Preview: [Conversation (primary), Contact, Company]
  │
  ├── Data Source: "All Contacts" (system-generated)
  │     └── Query: SELECT * FROM Contacts
  │
  └── Data Source: "Contact Activity Report" (dts_55fg...)
        ├── Query (raw SQL): Contacts LEFT JOIN Conversations (aggregated)
        ├── Columns: [Name, Company, Conversation Count, Last Activity]
        └── Preview: [Contact (primary), Company]

Views (rendering configurations — defined in the Views & Grid PRD)
  Each view references exactly one data source and adds its own
  rendering configuration: view type, visible columns, additional
  filters, sort overrides, grouping, and card/calendar/timeline mappings.
```

### 5.2 Key Terminology

| Term | Definition |
|---|---|
| **Data Source** | A reusable, named query definition that produces a structured result set for one or more views to render. Defines entities involved, available columns, default filters/sort, and previewable entities. Built via visual query builder or raw SQL. The "what data" layer. |
| **Column Registry** | The schema of a data source's result set. Lists every column with its name, data type, source entity, source field, and editability. The contract between the data source and the views that consume it. |
| **Visual Query Builder** | A UI-based tool for constructing data source queries by selecting entities, joins, columns, and filters without writing SQL. Generates a structured query configuration that the query engine executes. |
| **Virtual Schema** | The logical representation of entity types and fields that raw SQL queries execute against. Users never see the physical database schema — only entity types as tables and fields as columns. |
| **Query Engine** | The system component that translates data source definitions (visual builder or raw SQL) into executable queries against the physical data store. Handles security injection, parameter resolution, pagination, and caching. |
| **Prefixed Entity ID** | A globally unique identifier for any entity in the system, composed of a type prefix + underscore + ULID (e.g., `con_8f3a2b91c4d7` for a Contact). Enables automatic entity type detection from any ID value. |
| **Preview Configuration** | The metadata on a data source that determines which entities can be previewed from a result row and in what priority order. Auto-detected from prefixed IDs with optional manual overrides. |
| **Entity Reference Column** | A column in a data source result set whose values contain prefixed entity IDs, enabling the system to identify it as a navigable reference to a specific entity record. |
| **Edit Trace-Back** | The mechanism by which an inline edit in a view traces back through the column registry to identify the source entity and field, then issues an update API call to the correct entity endpoint. |
| **Query Eject** | A one-way operation that converts a visual builder data source to raw SQL by copying the generated SQL into the SQL editor. The data source cannot be converted back to visual builder mode. |
| **Schema Version** | A counter on the data source that increments when the column registry changes in ways that could break dependent views (column removed, renamed, or type changed). |
| **Refresh Policy** | How a data source's result set is refreshed: `live` (re-execute on every load), `cached` (TTL-based), or `manual` (user-triggered). |

### 5.3 Data Source Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                        DATA SOURCE DEFINITION                        │
│  ┌──────────────────┐  ┌──────────────────┐                         │
│  │  Visual Builder   │  │   Raw SQL Editor  │                        │
│  │  (Step-by-step    │  │  (Virtual schema,  │                       │
│  │   entity/join/    │  │   full SQL power)  │                       │
│  │   column/filter   │  │                    │                       │
│  │   selection)      │  │         ─────►     │  "Eject" (one-way)   │
│  └────────┬─────────┘  └─────────┬──────────┘                       │
│           │                      │                                   │
│           └──────────┬───────────┘                                   │
│                      ▼                                               │
│           ┌──────────────────────┐                                   │
│           │   Column Registry    │ ◄─ Auto-generated + overrides     │
│           │   Preview Config     │ ◄─ Auto-detected + overrides      │
│           │   Default Filters    │                                   │
│           │   Default Sort       │                                   │
│           │   Parameters         │                                   │
│           │   Refresh Policy     │                                   │
│           └──────────┬───────────┘                                   │
└──────────────────────┼───────────────────────────────────────────────┘
                       │
                       ▼ (execution request from View)
┌──────────────────────────────────────────────────────────────────────┐
│                          QUERY ENGINE                                │
│                                                                      │
│  1. Parse & Validate ─► 2. Merge View Overrides ─► 3. Resolve       │
│     (syntax, access,       (additional filters,       Parameters     │
│      forbidden ops)         sort overrides)           ({current_user}│
│                                                        {date_range}) │
│  4. Inject Security ──► 5. Translate to Physical ──► 6. Execute      │
│     (tenant isolation,     (virtual schema →            & Paginate   │
│      row-level access)      physical store)                          │
│                                                                      │
│  7. Cache Management ─► 8. Format Result Set ──────► Return to View  │
│     (TTL, invalidation,    (column metadata +                        │
│      deduplication)         typed rows + cursors)                    │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 6. Universal Entity ID Convention

### 6.1 The Convention

Every entity — system-defined or user-created — is assigned an ID with a short, unique prefix identifying its entity type, followed by an underscore and a globally unique identifier:

```
Format: {type_prefix}_{unique_id}

Examples:
  con_8f3a2b91c4d7          Contact
  cvr_91bc4de6f823          Conversation
  com_47de6f9a2b15          Communication
  prj_23ab8c55fg7h          Project
  top_bb91c4d78f3a          Topic
  seg_12de6f47ab9c          Segment
  cmp_55fg7h23ab8c          Company
  usr_7h23ab8c55fg          User
```

### 6.2 Prefix Registry

System entity type prefixes are reserved and immutable:

| Entity Type | Prefix | Example ID |
|---|---|---|
| Contact | `con_` | `con_8f3a2b91c4d7` |
| Conversation | `cvr_` | `cvr_91bc4de6f823` |
| Communication | `com_` | `com_47de6f9a2b15` |
| Project | `prj_` | `prj_23ab8c55fg7h` |
| Topic | `top_` | `top_bb91c4d78f3a` |
| Segment | `seg_` | `seg_12de6f47ab9c` |
| Company | `cmp_` | `cmp_55fg7h23ab8c` |
| User | `usr_` | `usr_7h23ab8c55fg` |
| Data Source | `dts_` | `dts_9a2b1547de6f` |
| View | `viw_` | `viw_6f9a2b1547de` |

**Custom entity type prefixes** are auto-generated when a user creates a custom entity type. The system generates a unique 3-4 character prefix derived from the entity name, checking for collisions against all existing prefixes (system and user-defined):

```
User creates "Jobs" entity → prefix: job_
User creates "Properties" entity → prefix: prop_
User creates "Service Agreements" entity → prefix: svca_
```

If the natural abbreviation collides with an existing prefix, the system appends or modifies characters until unique. The prefix is immutable once assigned — renaming the entity type does not change the prefix.

### 6.3 Rationale

This convention provides four critical capabilities:

**1. Automatic entity detection in data source results.** When a data source query returns result rows, the system can scan any column's values and immediately determine which entity type it references — without any metadata declaration. A column containing `con_8f3a2b91c4d7` is unambiguously a Contact reference.

**2. System-wide type safety.** Any component in the system that receives an entity ID can determine its type without additional context. API endpoints can accept any entity ID and route to the correct handler. Log entries containing entity IDs are self-documenting. Error messages referencing an entity ID immediately communicate what kind of entity is involved.

**3. Cross-entity collision avoidance.** Even though each entity type's IDs are stored in separate database tables, the prefix ensures that no two entities anywhere in the system — regardless of type — share the same ID string. This is critical for data source result sets that combine IDs from multiple entity types in a single row.

**4. Preview and navigation resolution.** The view system can examine any cell value in a data source result set and determine whether it's an entity reference, what type of entity it is, and therefore whether it can be previewed, linked, or navigated to. This powers the multi-entity preview system (Section 11) without requiring per-data-source configuration in the common case.

### 6.4 External ID Mapping

External system IDs (Gmail `threadId`, Outlook `conversationId`, Twilio message SIDs, etc.) are stored as metadata on the entity record but are never used as the entity's primary ID. The mapping is:

```
Entity: Communication (com_47de6f9a2b15)
  └── External IDs:
        ├── gmail_thread_id: "18d5a3b2c4e6f7"
        ├── gmail_message_id: "msg-a1b2c3d4e5f6"
        └── provider: "gmail"
```

This ensures that all internal references, queries, and data source results use prefixed IDs consistently, regardless of the original source.

### 6.5 ID Generation

The unique portion of the ID (after the prefix) is generated using a **ULID** (Universally Unique Lexicographically Sortable Identifier) algorithm, which provides:

- Global uniqueness without coordination
- Lexicographic sortability (IDs generated later sort after earlier ones, which is useful for cursor-based pagination)
- 128-bit randomness (collision probability is negligible)
- URL-safe characters (no encoding needed in API paths)

---

## 7. Data Source Definition Model

A Data Source is a first-class entity in the system with the following attributes:

| Attribute | Description |
|---|---|
| **ID** | Prefixed unique identifier (`dts_...`) |
| **Name** | User-defined name (e.g., "Deal Pipeline", "Contact Activity Report") |
| **Description** | Optional description of what this data source provides and when to use it |
| **Owner** | The user who created the data source |
| **Visibility** | `personal` (only owner) or `shared` (available to team/workspace) |
| **Query mode** | `visual` (built via visual query builder) or `sql` (raw SQL) |
| **Query definition** | The query itself — either a visual builder configuration object or a raw SQL string |
| **Column registry** | The result set schema: column names, data types, source entity/field mappings, editability flags |
| **Preview configuration** | Auto-detected previewable entities + optional manual overrides (priority, exclusions) |
| **Default filters** | Base filter conditions applied before any view-level overrides |
| **Default sort** | Base sort order applied when a view doesn't specify its own |
| **Parameters** | Optional named parameters that can be supplied at query time (e.g., `{current_user}`, `{date_range_start}`) |
| **Refresh policy** | How the result set is refreshed: `live` (re-execute on every load), `cached` (TTL-based), or `manual` (user-triggered) |
| **Created / Updated** | Timestamps |
| **Version** | Schema version counter, incremented when column registry changes (used to detect breaking changes for dependent views) |

---

## 8. Query Definition: Visual Builder

The visual query builder allows users to construct data source queries without writing SQL. It translates user selections into a structured query configuration that the query engine executes.

### 8.1 Builder Components

**Step 1 — Primary Entity Selection**

The user selects the primary entity type — the "FROM" table. This is the entity that defines the base result set. Every row in the result corresponds to one record of this entity type.

```
Primary Entity: Conversations
```

**Step 2 — Related Entity Joins**

The user adds related entities by selecting relation fields on the primary entity (or on previously joined entities). Each addition creates a JOIN in the underlying query.

```
Primary Entity: Conversations
  └── Join: Primary Contact → Contacts (via primary_contact_id)
        └── Join: Company → Companies (via company_id)
```

Each join is configured with:

| Setting | Options | Default |
|---|---|---|
| **Join type** | Inner (only rows with matches) or Left (include rows without matches) | Left |
| **Relation field** | The relation field used to connect the entities | Required |
| **Alias** (optional) | A display name for this join, used in column labels (e.g., "Primary Contact" vs. "Contact") | Derived from relation field name |

**Why Left Join is the default:** In CRM data, relations are frequently optional — a Conversation might not have a primary contact yet, a Contact might not have a Company. Left Join ensures that records with missing relations still appear in the result set, showing null values for the joined entity's columns. An Inner Join default would silently hide records with incomplete data, which is dangerous in a CRM context where data completeness varies.

**Step 3 — Column Selection**

The user selects which fields from each entity to include in the result set. The builder presents a field picker organized by entity:

```
Available Columns:
├── Conversation
│     ├── ☑ ID (auto-included, hidden by default)
│     ├── ☑ Subject
│     ├── ☑ AI Status
│     ├── ☐ System Status
│     ├── ☑ Last Activity
│     └── ☐ Created At
│
├── Contact (via Primary Contact)
│     ├── ☑ ID (auto-included, hidden by default)
│     ├── ☑ Name
│     ├── ☑ Email
│     └── ☐ Phone
│
└── Company (via Primary Contact → Company)
      ├── ☑ ID (auto-included, hidden by default)
      ├── ☑ Name
      ├── ☑ Industry
      └── ☐ Revenue
```

**Auto-included ID columns:** For every entity type involved in the data source (primary + all joined entities), the entity's ID column is automatically included in the result set. These ID columns are **hidden by default** — they don't appear as visible columns in views unless the user explicitly shows them. But they are always present in the underlying data, because the system needs them for:

- Entity preview and navigation (click a row → open the entity)
- Inline editing (trace an edit back to the source entity and field)
- Relation rendering (display entity names as clickable links)

**Step 4 — Default Filters**

The user optionally defines filter conditions that apply to every view using this data source. These are the base-level constraints that define the data source's scope.

```
Default Filters:
  AND: Conversation.AI Status ≠ "Closed"
  AND: Conversation.Last Activity within last 90 days
```

Views can add additional filters on top of these but cannot remove or override them. This ensures the data source author's intent is preserved — if a data source is scoped to "active conversations from the last 90 days," no view can circumvent that scope.

**Step 5 — Default Sort**

The user optionally defines a default sort order. Views can override this with their own sort, but if a view doesn't specify a sort, the data source default applies.

```
Default Sort:
  1. Conversation.Last Activity DESC
  2. Contact.Name ASC
```

### 8.2 Visual Builder ↔ SQL Equivalence

Every visual builder configuration has an exact SQL equivalent. The system can display the generated SQL for any visual builder query (read-only, for transparency and debugging). Advanced users who outgrow the visual builder can "eject" to raw SQL mode, which copies the generated SQL into the raw SQL editor for further customization. This is a **one-way operation** — once ejected, the data source cannot be converted back to visual builder mode because raw SQL can express constructs the visual builder cannot represent.

---

## 9. Query Definition: Raw SQL

Power users and analysts can write raw SQL queries directly. Raw SQL provides capabilities that the visual builder cannot express:

- Subqueries and CTEs (Common Table Expressions)
- UNION / INTERSECT / EXCEPT set operations
- Window functions (ROW_NUMBER, RANK, LAG, LEAD)
- Complex aggregations with HAVING clauses
- Conditional expressions (CASE WHEN)
- Custom column aliases with transformations
- Self-joins (an entity joined to itself)

### 9.1 SQL Environment

Raw SQL queries execute against a **virtual schema** that exposes entity types as tables and fields as columns. The user never sees or interacts with the physical database schema — only the logical entity model.

```sql
-- Virtual schema (what the user sees):
-- conversations (id, subject, ai_status, system_status, last_activity, ...)
-- contacts (id, name, email, phone, company_id, ...)
-- companies (id, name, industry, revenue, ...)
-- communications (id, timestamp, channel, content_preview, conversation_id, ...)

-- Example: Contact activity summary
SELECT 
  ct.id AS contact_id,
  ct.name AS contact_name,
  cmp.name AS company_name,
  COUNT(cvr.id) AS conversation_count,
  COUNT(CASE WHEN cvr.ai_status = 'open' THEN 1 END) AS open_conversations,
  MAX(cvr.last_activity) AS latest_activity,
  SUM(CASE WHEN com.channel = 'email' THEN 1 ELSE 0 END) AS email_count,
  SUM(CASE WHEN com.channel = 'sms' THEN 1 ELSE 0 END) AS sms_count
FROM contacts ct
LEFT JOIN companies cmp ON ct.company_id = cmp.id
LEFT JOIN conversations cvr ON cvr.primary_contact_id = ct.id
LEFT JOIN communications com ON com.conversation_id = cvr.id
WHERE ct.status = 'active'
GROUP BY ct.id, ct.name, cmp.name
HAVING COUNT(cvr.id) > 0
ORDER BY latest_activity DESC
```

### 9.2 Virtual Schema Access Rules

| Rule | Detail | Rationale |
|---|---|---|
| **SELECT only** | INSERT, UPDATE, DELETE, DDL statements are rejected at parse time | Data sources are read-only query definitions. Write operations happen through inline editing, which uses the entity API, not direct SQL. |
| **Tenant-scoped** | All queries are implicitly filtered to the current user's tenant. The `WHERE tenant_id = ?` clause is injected by the query engine and cannot be overridden. | Data isolation is non-negotiable. |
| **Row-level security** | Queries respect the user's data access permissions. Records the user cannot access are filtered out even if the SQL would otherwise return them. | A shared data source must not leak data to users who lack permission. |
| **Entity-type access** | Users can only query entity types they have read access to. Attempting to SELECT from an entity type the user cannot access results in a permission error. | Prevents data source authors from exposing restricted entity types. |
| **Execution timeout** | Queries are terminated after a configurable timeout (default: 30 seconds). | Prevents runaway queries from consuming resources. |
| **Result set limit** | Queries return a maximum of 10,000 rows (before view-level pagination). Data sources expected to exceed this should use appropriate WHERE clauses or the query engine's pagination integration. | Memory and performance guardrails. |

### 9.3 SQL Validation

When a user saves a raw SQL data source, the system:

1. **Parses** the SQL to verify syntax and detect forbidden operations (INSERT, UPDATE, DELETE, DDL).
2. **Resolves** table and column references against the virtual schema. Unknown table/column names produce clear error messages: "Entity type 'dealz' not found. Did you mean 'deals'?"
3. **Type-checks** column expressions to infer result column types (needed for the column registry).
4. **Dry-runs** the query with a `LIMIT 0` to verify it executes without error.
5. **Extracts** the column registry (column names, inferred types, source entity mappings) from the query plan.

Validation errors are displayed inline in the SQL editor with line/column references.

### 9.4 SQL Parameters

Raw SQL queries can include named parameters that are resolved at execution time:

```sql
SELECT ct.id, ct.name, COUNT(cvr.id) AS convo_count
FROM contacts ct
LEFT JOIN conversations cvr ON cvr.primary_contact_id = ct.id
WHERE cvr.last_activity > {date_range_start}
  AND cvr.last_activity < {date_range_end}
  AND cvr.owner_id = {current_user_id}
GROUP BY ct.id, ct.name
```

| Parameter | Resolution |
|---|---|
| `{current_user_id}` | The ID of the user executing the query |
| `{current_date}` | Today's date |
| `{current_timestamp}` | Current timestamp |
| `{date_range_start}`, `{date_range_end}` | User-supplied via a date range picker in the view UI |
| Custom parameters | Defined by the data source author, supplied via the view UI or alert configuration |

Parameters use curly-brace syntax and are resolved via parameterized queries (never string interpolation) to prevent SQL injection.

---

## 10. Column Registry

Every data source has a **column registry** — the schema of its result set. The column registry is the contract between the data source and the views that consume it. Views read the column registry to know what columns are available, what types they are, and how to render and edit them.

### 10.1 Column Registry Entry

Each column in the result set has the following metadata:

| Attribute | Description | Source |
|---|---|---|
| **Column name** | The name of the column in the result set (e.g., `contact_name`, `conversation_count`) | From SQL alias or visual builder field selection |
| **Display label** | Human-readable label (e.g., "Contact Name", "Conversation Count") | Auto-generated from column name, overridable by author |
| **Data type** | The field type: text, number, currency, date, datetime, select, checkbox, email, phone, url, etc. | Inferred from source field type (visual builder) or from SQL type-checking (raw SQL) |
| **Source entity** | Which entity type this column originates from (e.g., `Contact`, `Company`, `null` for computed columns) | Auto-detected from query structure |
| **Source field** | Which field on the source entity this column maps to (e.g., `name`, `industry`, `null` for computed) | Auto-detected from query structure |
| **Entity ID column** | Which column in the result set contains the ID of this column's source entity (e.g., `contact_id` for a column sourced from Contact) | Auto-detected from JOIN structure |
| **Editable** | Whether this column supports inline editing (see Section 14) | Derived from editability rules |
| **Hidden** | Whether this column is hidden by default in views (e.g., auto-included ID columns) | Auto-set for ID columns; manual for others |
| **Aggregation context** | Whether this column is an aggregate (COUNT, SUM, etc.) — affects preview detection and editability | Inferred from SQL or visual builder config |

### 10.2 Automatic Column Registry Generation

**Visual builder:** The column registry is generated directly from the field selections. Each selected field has a known entity, field name, and data type from the object model's field registry. The mapping is unambiguous.

**Raw SQL:** The column registry is inferred from the query plan:

1. **Direct column references** (`ct.name`, `cvr.ai_status`) — the system traces the column back to its source entity and field through the FROM/JOIN structure. Entity, field, and data type are all known.
2. **Aliased columns** (`ct.name AS contact_name`) — same tracing, with the alias used as the column name.
3. **Computed expressions** (`COUNT(cvr.id) AS conversation_count`) — the system recognizes the aggregate function, infers the output type (number for COUNT/SUM, same type for MIN/MAX), and marks the column as non-editable and aggregated. Source entity is set to `null`.
4. **CASE expressions** (`CASE WHEN ... THEN 'High' ELSE 'Low' END AS priority_label`) — the system infers the output type from the THEN/ELSE values. Source entity is `null` (computed).
5. **Unresolvable columns** — if the system cannot infer a column's source entity or data type (e.g., complex nested subqueries), it defaults to `text` type, `null` source entity, and non-editable. The author can manually override these in the column registry editor.

### 10.3 Manual Registry Overrides

After automatic generation, the data source author can manually override any column registry entry:

- Change the display label
- Correct or specify the data type (e.g., override `text` to `currency` for a formatted column)
- Mark a column as hidden or visible by default
- Override editability (e.g., force a column to read-only even if it would otherwise be editable)
- Specify the source entity and field for computed columns that the system couldn't resolve

These overrides are stored as part of the data source definition and survive query modifications (unless the column is removed from the query entirely).

---

## 11. Entity Detection & Preview System

The preview system determines which entities a data source result row can navigate to. It uses a three-layer approach: automatic detection, automatic inference rules, and optional manual declaration.

### 11.1 Layer 1: Automatic Detection via Prefixed IDs

The system scans all columns in the data source's column registry. Any column whose values contain prefixed entity IDs is registered as a potential **entity reference column**:

```
Result row:
  conversation_id: cvr_91bc4de6f823    ← Entity reference: Conversation
  contact_name: "Alice Smith"           ← Not an entity reference (text)
  contact_id: con_8f3a2b91c4d7         ← Entity reference: Contact
  company_id: cmp_55fg7h23ab8c         ← Entity reference: Company
  open_conversations: 5                 ← Not an entity reference (number)
```

Detection mechanism: During column registry generation (Section 10), the system identifies columns whose source field is an entity ID field (type = `id` or `relation`). For raw SQL, a dry-run query fetches a sample row and checks column values against the prefix registry.

### 11.2 Layer 2: Automatic Inference Rules

Not all detected entity reference columns should be previewable. The system applies inference rules to determine which detections are valid preview targets and what their priority should be:

**Rule 1 — Exclude aggregated entity IDs.**
If a column is within an aggregate function (`COUNT(cvr.id)`, `MAX(com.id)`), the ID values are not meaningful for preview — they represent aggregated sets, not individual records. These columns are excluded from preview.

**Rationale:** A data source that counts conversations per contact returns `conversation_count: 5`. The individual conversation IDs used in the COUNT are not in the result set. Even if a `MAX(cvr.id)` column were present, previewing the "maximum ID conversation" is meaningless to the user.

**Rule 2 — Exclude junction/intermediate entity IDs.**
If a column's source entity is a junction table (identified by the object model as a many-to-many connector entity), it is excluded from preview by default. Junction records are structural, not user-facing.

**Rationale:** A query that joins `conversations` → `conversation_contacts` → `contacts` may include `conversation_contacts.id` in the result. This is a junction table ID that is meaningless to preview.

**Rule 3 — Primary entity gets highest priority.**
The entity from the `FROM` clause (visual builder: primary entity) is assigned the highest preview priority. This entity represents "what each row is about."

**Rationale:** A data source with `FROM contacts JOIN conversations` is "about" Contacts — each row represents a Contact. When the user clicks a row, the most natural action is to preview the Contact, not one of their Conversations.

**Rule 4 — Joined entities are ordered by JOIN sequence.**
Entities added via JOIN are ordered by their position in the query — the first JOIN has higher preview priority than the second, and so on. This reflects the author's implicit priority: the first JOIN is typically the most closely related entity.

**Rule 5 — Detect duplicate entity types.**
If the same entity type appears more than once (e.g., two Contact joins — "Primary Contact" and "Secondary Contact"), both are previewable with their alias as a distinguishing label.

### 11.3 Layer 3: Optional Manual Declaration (Override)

For the majority of data sources, Layers 1 and 2 produce correct preview behavior with zero configuration. The manual declaration layer exists for cases where the automatic inference is wrong or insufficient.

The data source author can open the **Preview Configuration** panel and:

| Override | Effect | Use Case |
|---|---|---|
| **Reorder priorities** | Change which entity previews on primary click vs. secondary access | A "Company Report" data source where the Contact JOIN is first but Company should be the primary preview |
| **Exclude an entity** | Remove an entity from the previewable set | A query returns a `tag_id` column for filtering purposes, but Tag preview is meaningless |
| **Include a computed entity** | Manually declare that a computed column maps to a previewable entity | A subquery returns an entity ID in a column the system couldn't auto-detect |
| **Set labels** | Override the display name used in the preview UI (e.g., "Billing Contact" vs. "Contact") | Multiple joins to the same entity type, or joins with aliases that differ from the entity name |

**Override persistence:** Manual overrides are stored in the data source's `preview_configuration` attribute. They take precedence over automatic detection — if the author excludes an entity, it stays excluded even if the query is modified to add more references to that entity type.

**Override invalidation:** If the data source query is modified such that a declared preview entity is no longer present in the result set (the ID column is removed), the system warns the author: "Preview entity 'Company' references column 'company_id' which is no longer in the result set. Remove this preview declaration or update the column reference."

---

## 12. Preview Resolution at Runtime

When a user interacts with a row in a view (click, expand, context menu), the system resolves which entities are previewable and in what order:

```
User clicks row in "Deal Pipeline" view
  │
  ├── System reads the data source's preview configuration:
  │     Priority: [Conversation, Contact, Company]
  │
  ├── System reads the row's entity ID values:
  │     conversation_id: cvr_91bc4de6f823
  │     contact_id: con_8f3a2b91c4d7
  │     company_id: cmp_55fg7h23ab8c
  │
  ├── Primary preview (single-click default): Conversation cvr_91bc4de6f823
  │     → Opens Detail Panel for this Conversation
  │
  └── Secondary previews (available via UI affordance):
        ├── Contact: con_8f3a2b91c4d7 → "Alice Smith"
        └── Company: cmp_55fg7h23ab8c → "Acme Corp"
```

**Null handling:** If a row has a null value for an entity ID (e.g., the Contact has no Company), that entity is omitted from the previewable set for that specific row. The preview UI dynamically adjusts per row.

**Permission handling:** If the current user doesn't have read access to a particular entity record, that preview option is hidden for that row. The data source result may include the ID, but the preview system respects access controls.

---

## 13. Data Source ↔ View Relationship

The relationship between Data Sources and Views is **many-to-one**: multiple views can reference the same data source, but each view references exactly one data source.

```
Data Source: "Active Deal Pipeline" (dts_9a2b1547de6f)
│
├── View: "Pipeline Board" (Board)
│     ├── Visible columns: Subject, Contact Name, Company Name, Deal Value
│     ├── Board grouping field: AI Status
│     ├── Additional filters: Owner = Me
│     └── Sort: Deal Value DESC
│
├── View: "Pipeline List" (List/Grid)
│     ├── Visible columns: Subject, Contact Name, Company, AI Status, Last Activity, Deal Value
│     ├── Additional filters: none
│     ├── Sort: Last Activity DESC
│     └── Group by: AI Status
│
├── View: "Expected Closes" (Calendar)
│     ├── Date field: Expected Close Date
│     ├── Card fields: Subject, Contact Name, Deal Value
│     ├── Additional filters: AI Status ≠ Closed
│     └── Color: AI Status
│
└── View: "Deal Timeline" (Timeline)
      ├── Start: Created Date
      ├── End: Expected Close Date
      ├── Sidebar: Subject, Contact Name, Deal Value
      ├── Additional filters: none
      └── Swimlanes: Owner
```

### 13.1 How View-Level Overrides Compose with Data Source Defaults

| Aspect | Data Source Defines | View Can Do |
|---|---|---|
| **Available columns** | The complete column registry (all columns the query returns) | Choose which columns to display, their order, width, and pinning. Cannot add columns not in the data source. |
| **Default filters** | Base filter conditions that scope the data source | Add additional filter conditions (AND'd with data source filters). Cannot remove or negate data source filters. |
| **Default sort** | Base sort order | Override with a different sort order, or accept the data source default if no sort is specified. |
| **Parameters** | Named parameters with optional default values | Supply parameter values (e.g., a date range picker in the view's header). If a parameter has no default and the view doesn't supply a value, the query fails with a clear error. |
| **Preview configuration** | Previewable entities with priority | Accept the data source's preview configuration as-is. Views do not override preview config. |

**Why views cannot remove data source filters:** The data source's filters define the data source's **scope** — the universe of data it operates on. A "Last 90 Days Active Conversations" data source should always return data from the last 90 days, regardless of how views render it. If a view could remove this filter, it would change the data source's fundamental meaning. If a user needs unfiltered data, they should create or use a different data source.

**Why views cannot add columns:** The data source's column registry is the contract. Views select from what's available. If a user needs a column that doesn't exist in the data source, they modify the data source (or create a new one). This preserves the data source as the single definition of "what data is available" and prevents views from independently making expensive query modifications.

---

## 14. Inline Editing Trace-Back

When a user edits a cell value inline in a view, the system must trace the edit back to the source entity and field to persist the change. The column registry provides this mapping.

### 14.1 Editability Rules

A column is editable inline if and only if ALL of the following conditions are met:

| Condition | Rationale |
|---|---|
| **Source entity is identified** | The column registry maps this column to a specific entity type and field. Computed columns (`source_entity = null`) cannot be edited. |
| **Source field is a direct field** (not a formula or rollup) | Formula and rollup fields are derived values — editing them is meaningless. |
| **The field type supports inline editing** | Multi-line text, for example, opens a popup rather than editing in the cell. Some field types (like auto-generated timestamps) are inherently read-only. |
| **The entity ID column is present in the result set** | The system needs the entity's ID to issue an update API call. If the data source doesn't include the source entity's ID column, the edit has no target. (This is why ID columns are auto-included.) |
| **The user has write permission on the entity record** | Row-level security applies — the user must be able to edit this specific record of this entity type. |
| **The data source author hasn't forced read-only** | The author can override editability in the column registry to prevent edits on specific columns. |
| **The column is not aggregated** | Aggregated values (COUNT, SUM, etc.) represent multiple records and cannot be edited. |

### 14.2 Edit Trace-Back Flow

```
User edits "Company Name" cell in a Conversations List view
  │
  ├── View identifies the column: "company_name"
  │
  ├── Column registry lookup:
  │     column: company_name
  │     source_entity: Company
  │     source_field: name
  │     entity_id_column: company_id
  │
  ├── Read the row's company_id value: cmp_55fg7h23ab8c
  │
  ├── Issue API call: PATCH /entities/companies/cmp_55fg7h23ab8c
  │     body: { "name": "New Company Name" }
  │
  ├── API validates permissions, field constraints, and saves
  │
  ├── On success: update the cell in the view, show save indicator
  │
  └── On failure: revert cell value, show error notification
```

**Cross-entity edit implications:** Because a data source can join multiple entity types, a single view row may contain editable columns from different entities. Editing "Subject" updates the Conversation record; editing "Contact Name" in the same row updates the Contact record; editing "Company Name" updates the Company record. Each edit is an independent API call to the respective entity's endpoint. The view handles each edit in isolation — there is no transaction spanning multiple entity edits from the same row.

**Cascade visibility:** If editing a Company's name in one row, other rows in the same view that reference the same Company will show the old name until the view is refreshed or the query cache expires. Real-time propagation of cross-row changes is addressed in the Cache, Refresh & Invalidation section (Section 16).

---

## 15. Query Engine

The query engine is the system component that transforms data source definitions into executable queries, runs them securely, and returns structured results. This section defines the query engine's conceptual responsibilities and behavioral contracts.

### 15.1 Responsibilities

The query engine is responsible for:

1. **Virtual-to-physical translation** — Mapping the virtual schema (entity types as tables, fields as columns) to the physical data store, whatever its structure. The translation is opaque to data source authors and view consumers.
2. **Security injection** — Applying tenant isolation and row-level access controls to every query, regardless of whether the data source was built visually or in raw SQL. Security conditions are injected by the engine and cannot be overridden by the query author.
3. **Parameter resolution** — Replacing named parameters (`{current_user_id}`, `{date_range_start}`, custom parameters) with their runtime values before execution. Parameters are always bound via parameterized queries, never string-interpolated.
4. **View override merging** — Composing the data source's default filters and sort with the requesting view's additional filters and sort overrides into a single executable query.
5. **Pagination** — Implementing cursor-based pagination so that views can load data incrementally. The engine generates cursors and accepts them on subsequent requests.
6. **Result formatting** — Returning structured results that include both the typed row data and the column registry metadata, so views can render correctly without re-reading the data source definition.
7. **Cache management** — Executing, storing, and serving cached results according to the data source's refresh policy, with appropriate invalidation.

### 15.2 Query Execution Lifecycle

Every data source execution — whether triggered by a view load, a filter change, a pagination request, or a manual refresh — follows this lifecycle:

```
1. REQUEST
   View sends: data source ID, view-level filters, sort overrides,
   parameter values, pagination cursor, requesting user context

2. RESOLVE DEFINITION
   Load the data source definition: query, column registry,
   default filters/sort, parameters, refresh policy

3. CHECK CACHE
   If refresh policy = cached and a valid cache entry exists
   for this data source + parameters + user context → return cached result
   If refresh policy = manual and result exists → return stored result
   Otherwise → proceed to execution

4. MERGE OVERRIDES
   Compose: data source default filters AND view-level additional filters
   Apply: view-level sort override (or data source default if none)
   Resolve: parameter values from view, alert config, or defaults

5. INJECT SECURITY
   Add: tenant isolation (WHERE tenant_id = ?)
   Add: row-level access filters based on requesting user's permissions
   Add: entity-type access check (user can read all referenced entity types?)

6. TRANSLATE
   Map virtual schema references to physical storage
   (This step is implementation-dependent — see Section 15.3)

7. EXECUTE
   Run the query with timeout enforcement
   Apply result set limit (10,000 rows max)
   Generate pagination cursor for next page

8. FORMAT
   Package result: column metadata + typed rows + pagination info + cache metadata
   Return to requesting view
```

### 15.3 Virtual Schema Translation

The virtual schema is the abstraction that lets data source authors think in terms of entity types and fields, while the physical storage may be organized differently (event-sourced projections, denormalized read models, JSONB stores, or any other structure).

**Conceptual contract:** The query engine guarantees that `SELECT ct.name FROM contacts ct WHERE ct.status = 'active'` returns the same logical result regardless of how Contact records are physically stored. The virtual schema is a stable API — changes to the physical storage model do not affect existing data sources.

**Virtual schema composition:** The virtual schema is dynamically composed from the object model's entity type registry. When a new entity type is created (system or custom), it automatically appears as a queryable table in the virtual schema. When fields are added to or removed from an entity type, the virtual schema reflects the change immediately.

**Custom entity parity:** Custom entities appear in the virtual schema identically to system entities. A raw SQL query that joins `contacts` (system entity) to `jobs` (custom entity) should behave as if both are regular tables. Any performance differences between system and custom entity queries are an implementation concern, not a conceptual one — the virtual schema promises uniform behavior.

### 15.4 Security Model

Security is enforced at the query engine level, not at the data source definition level. This is a critical architectural principle: **data source authors cannot bypass security, intentionally or accidentally.**

**Tenant isolation:** Every query is scoped to the requesting user's tenant. The tenant filter is injected by the engine after the query is fully composed. It cannot be overridden, removed, or referenced by the data source query. Even raw SQL queries that attempt to reference a `tenant_id` column directly will have the engine's tenant filter applied on top.

**Row-level security:** The permissions system defines which records of which entity types a user can access. The query engine applies these restrictions as additional WHERE clauses, transparently. A shared data source returns different result sets for different users based on their permissions — this is expected and by design.

**Entity-type access:** Before executing a query, the engine verifies that the requesting user has read access to every entity type referenced in the query (FROM clause + all JOINs). If the user lacks access to any entity type, the query fails with a permission error rather than returning partial results.

### 15.5 Pagination Contract

Data sources produce potentially large result sets. The query engine implements **cursor-based pagination** to enable efficient, incremental loading.

**How cursors work:** After executing a query with a page size limit, the engine returns a pagination cursor — an opaque token encoding the position of the last returned record. The next request includes this cursor, and the engine resumes from that position.

**Cursor properties:**
- Opaque to clients — views and data source consumers never parse cursor contents
- Stable across identical queries — the same cursor on the same query returns the same next page
- Invalidated by query changes — if the data source's filters, sort, or parameters change, existing cursors are invalid (the view resets to page 1)
- Encode sort position, not offset — cursors use keyset pagination (WHERE + ORDER BY) rather than OFFSET-based pagination, ensuring consistent performance regardless of page depth

**Page size:** Determined by the requesting view. List/Grid views typically request 50-100 rows per page. Board views request per-column batches. Calendar and Timeline views use date-window-based loading rather than row-count pagination.

---

## 16. Cache, Refresh & Invalidation

Data source results can be expensive to compute, especially for cross-entity JOINs with aggregations. The cache layer balances freshness against performance.

### 16.1 Refresh Policies

Each data source specifies a refresh policy that governs how its results are cached and refreshed:

| Policy | Behavior | Best For |
|---|---|---|
| **Live** | Re-execute the query on every view load, filter change, and pagination request. No caching of result sets. | Small, fast queries where real-time accuracy is critical (e.g., "My Open Conversations" — low row count, frequently changing). |
| **Cached** | Store the result set after execution. Serve from cache until the TTL expires, then re-execute. | Medium-complexity queries where slight staleness is acceptable (e.g., "Contact Activity Report" — aggregation query, updated every few minutes is fine). |
| **Manual** | Execute only when the user explicitly clicks "Refresh." Results persist until manually refreshed. | Expensive analytical queries that users run intentionally (e.g., complex CTE-based reports, quarterly analysis). |

**Default policy:** `live` for system-generated data sources and visual builder data sources with no JOINs. `cached` (60-second TTL) for visual builder data sources with JOINs. `cached` (60-second TTL) for raw SQL data sources. Users can change the policy on any data source they own.

### 16.2 Cache Key Composition

The cache key for a data source result set is composed of:

1. **Data source ID** — identifies the query definition
2. **Data source version** — ensures cache invalidation when the query changes
3. **Parameter values** — different parameter values produce different result sets
4. **Requesting user ID** — because row-level security means different users get different results from the same data source
5. **View-level filter hash** — because different views may apply different additional filters

This means the same data source may have multiple cache entries simultaneously — one per unique combination of parameters, users, and view-level filters.

### 16.3 Invalidation Strategies

Cache entries can be invalidated through multiple mechanisms:

**TTL expiration:** The simplest mechanism. Cached results expire after a configurable duration (default: 60 seconds). After expiration, the next request triggers a fresh execution. No coordination required.

**Version-based invalidation:** When a data source definition is edited (query modified, filters changed, etc.), its version counter increments. All cache entries for the old version are invalidated immediately, regardless of TTL. This ensures that data source edits take effect instantly.

**Event-driven invalidation (future consideration):** When a record is created, updated, or deleted, cached data sources that include that record's entity type *could* be invalidated. This provides faster freshness than TTL alone but requires the cache layer to track which entity types each data source references. This is noted as a future optimization — TTL + version-based invalidation is sufficient for the initial implementation.

### 16.4 Concurrent Query Deduplication

When multiple views reference the same data source and load simultaneously (e.g., a dashboard with four views on the same data source), the query engine deduplicates the execution:

- The first request triggers execution.
- Subsequent requests for the same cache key (while the first is in flight) are **held** rather than triggering parallel executions.
- When the first execution completes, its result is distributed to all waiting requests.

This prevents a dashboard with four views on the same data source from executing the same expensive query four times.

**Deduplication scope:** Same cache key (data source + version + parameters + user + view-level filters). If two views have different view-level filters, they are separate queries and execute independently.

### 16.5 Staleness Indicators

When a view displays cached results, the UI can optionally indicate staleness:

- **Cached, fresh:** No indicator. The result is within its TTL.
- **Cached, nearing expiration:** Subtle indicator (e.g., a small clock icon) showing "Last refreshed X seconds ago."
- **Manual, stale:** Clear indicator showing "Refreshed at [timestamp]" with a visible refresh button.
- **Refreshing:** When a cache entry is being refreshed (either via TTL expiration or manual refresh), the view can show the stale data with a "Refreshing..." indicator, then seamlessly swap in the fresh data. This avoids showing a loading spinner for cached data sources.

---

## 17. Data Source Lifecycle & Versioning

### 17.1 Lifecycle Operations

| Operation | Behavior |
|---|---|
| **Create** | User creates a data source via visual builder or raw SQL editor. System generates column registry, validates query, detects preview entities. |
| **Edit** | Author modifies the query. System re-generates column registry, validates, re-detects previews. If column registry changes (columns added/removed/type changed), the version counter increments. |
| **Duplicate** | Creates a copy of the data source with a new ID. Useful for creating variations of a common query. |
| **Delete** | Removes the data source. All views referencing this data source are orphaned and display a "Data source deleted" error until the user selects a new data source or deletes the view. |
| **Share / Unshare** | Toggle visibility from personal to shared or back. Sharing follows the same model as shared views (see Views & Grid PRD, Section 17). |

### 17.2 Schema Versioning

The data source maintains a **version counter** that increments whenever the column registry changes in a way that could break dependent views:

| Change Type | Version Increment? | Impact on Views |
|---|---|---|
| Column added | No | Views don't show new columns by default; no breakage |
| Column removed | **Yes** | Views referencing the removed column show a "Column unavailable" indicator. The column configuration is preserved (in case the column is re-added) but the column renders as empty. |
| Column type changed | **Yes** | Views may have incompatible filters or sorts on the changed column. The system warns and disables affected filters/sorts. |
| Column renamed | **Yes** | Views reference columns by name. A rename is functionally a remove + add. |
| Filter/sort defaults changed | No | Views that override the defaults are unaffected. Views using the defaults see the new behavior. |

When a breaking version change occurs, the system:

1. Identifies all views referencing this data source.
2. Checks each view for references to changed/removed columns.
3. Flags affected views with a "data source schema changed" warning visible to the view owner.
4. Does **not** automatically modify the view — the view owner must review and adjust.

---

## 18. Schema Evolution & Migration

While Section 17 addresses versioning of the *data source definition itself*, this section addresses what happens when the *underlying entity model* changes — the entities and fields that data sources query against.

### 18.1 Field Changes

| Change | Impact on Data Sources | System Response |
|---|---|---|
| **Field added to entity type** | No impact on existing data sources. The new field is available in the virtual schema but not included in any existing query unless added by the author. | Virtual schema updated immediately. System-generated data sources (Section 21) are automatically updated to include the new field. |
| **Field removed from entity type** | Data sources referencing the removed field will fail validation. Visual builder queries lose the column. Raw SQL queries reference a column that no longer exists. | System flags affected data sources with a "field removed" warning. The column remains in the column registry as "unavailable." The data source continues to execute with the affected column returning NULL values, degrading gracefully rather than failing entirely. Owner is notified. |
| **Field renamed** | Functionally equivalent to remove + add. Visual builder queries can auto-update (the builder references field IDs, not names). Raw SQL queries reference the old name and break. | Visual builder: automatic migration (field ID preserved, display name updated). Raw SQL: flagged for manual update. The system suggests the rename in the warning: "Column 'old_name' not found. Did you mean 'new_name'?" |
| **Field type changed** | Columns referencing the field may have incompatible filters, sorts, or display configurations. A text field changing to a number field breaks "contains" filters. | System re-validates all affected data sources. Incompatible filters and sorts are disabled with a warning. Column registry entry is updated with the new type. View owners are notified of the type change and any disabled configurations. |

### 18.2 Entity Type Changes

| Change | Impact on Data Sources | System Response |
|---|---|---|
| **Entity type created** | No impact on existing data sources. New entity type is immediately available in the virtual schema. A system-generated data source is created for it. | Virtual schema updated. System-generated data source and default view created. |
| **Entity type deleted** | Data sources that reference the deleted entity type cannot execute. This is a severe, breaking change. | System flags all affected data sources. For visual builder data sources, the deleted entity's JOIN and columns are marked as "unavailable" — the rest of the query can still execute if the JOIN is optional (LEFT). For raw SQL, the entire data source is flagged as broken. Owner is notified immediately. Dependent views show a "data source error" state. |
| **Entity type renamed** | Virtual schema tables are referenced by internal entity type IDs, not display names. Visual builder queries are unaffected. Raw SQL queries that use table aliases are unaffected. Raw SQL that references the entity by its old virtual table name will break. | Virtual schema updated with new name. Visual builder: transparent (references by ID). Raw SQL: flagged for manual update with suggestion. |

### 18.3 Relation Changes

| Change | Impact on Data Sources | System Response |
|---|---|---|
| **Relation added** | No impact. New relation is available for JOINs in new or edited data sources. | Virtual schema updated. |
| **Relation removed** | Data sources using this relation for JOINs lose the JOIN path. The joined entity's columns become unavailable. | Visual builder: the JOIN is flagged as "broken" — the author must remove it or select an alternative relation. Raw SQL: the JOIN condition references a column that no longer exists — flagged for manual update. |
| **Relation cardinality changed** | A one-to-one relation becoming one-to-many could multiply result rows in existing data sources. | System warns the data source owner that a relation change may affect result set size. No automatic modification. |

### 18.4 Graceful Degradation Principle

Across all schema evolution scenarios, the system follows a consistent principle: **degrade gracefully, never fail silently.**

- When a field or entity is removed, affected data sources continue to execute with missing columns returning NULL — rather than refusing to execute entirely.
- All schema-related issues produce visible, actionable warnings to the data source owner and dependent view owners.
- The system never automatically modifies a user's data source query to accommodate schema changes (except for visual builder field ID remapping on renames). The owner always reviews and approves changes.
- Schema warnings persist until resolved. They don't disappear after being dismissed — the underlying issue must be fixed.

---

## 19. Data Source API

This section defines the conceptual API surface for data source operations. The API separates **definition management** (CRUD on data source configurations) from **query execution** (running the data source and returning results).

### 19.1 Definition Management Endpoints

| Operation | Endpoint Pattern | Description |
|---|---|---|
| **Create** | `POST /data-sources` | Create a new data source. Body includes query definition (visual builder config or raw SQL), name, description, visibility, parameters. Returns the created data source with auto-generated column registry and preview configuration. |
| **Read** | `GET /data-sources/{id}` | Retrieve a data source definition including column registry, preview config, and metadata. Does not execute the query — returns the definition only. |
| **Update** | `PATCH /data-sources/{id}` | Modify a data source. Triggers re-validation, column registry regeneration, and version increment if schema changes. Returns updated definition with any validation warnings. |
| **Delete** | `DELETE /data-sources/{id}` | Delete a data source. Returns a list of affected views (orphaned) for confirmation. Requires ownership or admin permission. |
| **Duplicate** | `POST /data-sources/{id}/duplicate` | Create a copy with a new ID and "(Copy)" appended to the name. The copy is always personal regardless of the original's visibility. |
| **List** | `GET /data-sources` | List data sources visible to the current user (personal + shared). Supports filtering by query mode, entity type, and search by name/description. |
| **Validate** | `POST /data-sources/validate` | Validate a query without saving. Returns column registry, preview detection results, and any warnings/errors. Used by the UI for real-time feedback during editing. |

### 19.2 Query Execution Endpoint

| Operation | Endpoint Pattern | Description |
|---|---|---|
| **Execute** | `POST /data-sources/{id}/execute` | Execute the data source query and return results. |

**Execution request body:**

| Field | Type | Description |
|---|---|---|
| `parameters` | Object | Parameter values keyed by parameter name. Overrides data source defaults. |
| `additional_filters` | Array | View-level filter conditions to AND with data source defaults. |
| `sort_override` | Array | View-level sort rules to replace data source default sort. |
| `page_size` | Integer | Number of rows to return (default: 50, max: 500). |
| `cursor` | String | Pagination cursor from a previous response. Null for first page. |

**Execution response body:**

| Field | Type | Description |
|---|---|---|
| `columns` | Array | Column metadata from the column registry (name, display label, type, editable, source entity). |
| `rows` | Array | Typed row objects. Each row is a key-value map of column name → value. |
| `total_estimate` | Integer | Estimated total row count (approximate for large sets, exact for small sets). |
| `cursor` | String | Pagination cursor for the next page. Null if this is the last page. |
| `cache_metadata` | Object | Cache status: `hit` or `miss`, TTL remaining if cached, last refresh timestamp. |
| `warnings` | Array | Any schema warnings, performance warnings, or approximate-result indicators. |

### 19.3 Batch Execution

For dashboards and multi-view screens that load multiple data sources simultaneously, the API supports batch execution:

| Operation | Endpoint Pattern | Description |
|---|---|---|
| **Batch Execute** | `POST /data-sources/execute-batch` | Execute multiple data source queries in a single request. |

**Batch request body:** An array of execution requests (each identical to the single execute request body, plus a `data_source_id` field).

**Batch response body:** An array of execution responses, in the same order as the requests. Each entry includes the data source ID for correlation.

**Batch behavior:**
- The engine deduplicates identical cache keys across the batch (same data source + parameters + user + filters → single execution).
- Each query in the batch is executed independently — a failure in one does not abort others.
- Individual entries in the response may have `error` fields if their query failed.

### 19.4 WebSocket / Server-Sent Events (Future)

For data sources with `live` refresh policy, a future enhancement could provide push-based updates:

- The client subscribes to a data source execution result.
- When the underlying data changes (detected via event sourcing change stream), the server re-executes the query and pushes the delta or full result set to subscribed clients.
- This eliminates polling for live data sources and enables real-time dashboards.

This is noted as a future consideration. The initial implementation relies on client-initiated requests (load, filter change, manual refresh, TTL expiration).

---

## 20. Data Source Permissions & Security

### 20.1 Access Control

| Actor | Can Do |
|---|---|
| **Owner** | Full CRUD on the data source. Edit query, modify column registry, manage preview config, share/unshare. |
| **Team member (shared data source)** | Read the data source definition. Create views referencing it. Cannot edit the data source itself. Can duplicate it to create their own copy. |
| **Team member (personal data source)** | Cannot see or access the data source. |

### 20.2 Row-Level Security

Data source queries always execute within the requesting user's security context:

- Tenant isolation is enforced at the query engine level.
- Row-level access controls filter results before they reach the view.
- A shared data source may return different result sets for different users based on their data permissions.

**This means sharing a data source is safe** — the query definition is shared, not the data. User A and User B can use the same "All Conversations" data source, but User A sees only their conversations while User B sees only theirs (unless broader permissions apply).

### 20.3 SQL Injection Prevention

Raw SQL queries are parameterized. User-supplied values (parameters, filter values from views) are never interpolated into the SQL string. The query engine uses prepared statements with bound parameters for all dynamic values.

The virtual schema layer adds a second line of defense: raw SQL operates against a logical schema, not the physical database. Even if a malicious query were somehow injected, it could not reference physical tables, system catalogs, or cross-tenant data.

---

## 21. System-Generated Data Sources

For each entity type in the system (both system-defined and user-created custom entities), the system automatically generates a **default data source** that provides simple, unfiltered access to all records of that entity type.

```
Auto-generated Data Source: "All Contacts"
  Query: SELECT * FROM contacts
  Columns: All fields on the Contact entity
  Default Filter: none
  Default Sort: created_at DESC
  Preview: Contact (only entity, auto-primary)
```

These system-generated data sources serve as the default data source for the system default views (see Views & Grid PRD). They ensure that every entity type is immediately viewable without requiring the user to create a data source first.

**Properties of system-generated data sources:**

- Cannot be deleted or modified by users (but can be duplicated to create a custom variation).
- Automatically updated when fields are added to or removed from the entity type.
- Named with the pattern "All {Entity Type Plural}" (e.g., "All Contacts", "All Conversations", "All Jobs").
- One per entity type per user (custom entity) or per tenant (system entity).

---

## 22. Data Source Examples

The following examples illustrate the range of data sources from simple to complex, demonstrating how the architecture handles each case.

### Example 1: Simple Single-Entity Data Source

**Use case:** "Show me all my Contacts."

**Visual builder configuration:**
```
Primary Entity: Contacts
Joins: none
Columns: [ID, Name, Email, Phone, Company, Last Activity, Status]
Default Filter: none
Default Sort: Name ASC
```

**Generated SQL:**
```sql
SELECT 
  ct.id, ct.name, ct.email, ct.phone, 
  ct.company, ct.last_activity, ct.status
FROM contacts ct
ORDER BY ct.name ASC
```

**Column registry:** 7 columns, all from Contact entity, all editable (except `id` and `last_activity` which are system-generated).

**Preview detection:** One entity type (Contact) detected. Auto-priority: Contact is primary and only preview target.

**Views using this data source:**
- "Contact List" (List/Grid) — all columns visible, no additional filters
- "Contact Board" (Board) — grouped by Status field
- "Follow-Up Calendar" (Calendar) — date field = Last Activity

This example demonstrates the simplest case: zero configuration beyond selecting the entity and columns. Preview, editability, and column types are all automatic.

### Example 2: Multi-Entity Join with Relation Traversal

**Use case:** "Show me all Conversations with their Contact and Company details."

**Visual builder configuration:**
```
Primary Entity: Conversations
Joins:
  └── Primary Contact → Contacts (LEFT JOIN)
        └── Company → Companies (LEFT JOIN)
Columns: 
  Conversation: [ID, Subject, AI Status, Last Activity, Channel]
  Contact: [ID, Name, Email]
  Company: [ID, Name, Industry]
Default Filter: Conversation.AI Status ≠ "Closed"
Default Sort: Conversation.Last Activity DESC
```

**Generated SQL:**
```sql
SELECT 
  cvr.id AS conversation_id, cvr.subject, cvr.ai_status, 
  cvr.last_activity, cvr.channel,
  ct.id AS contact_id, ct.name AS contact_name, ct.email AS contact_email,
  cmp.id AS company_id, cmp.name AS company_name, cmp.industry
FROM conversations cvr
LEFT JOIN contacts ct ON cvr.primary_contact_id = ct.id
LEFT JOIN companies cmp ON ct.company_id = cmp.id
WHERE cvr.ai_status != 'closed'
ORDER BY cvr.last_activity DESC
```

**Column registry:** 11 columns across 3 entity types. Conversation columns trace to Conversation entity, Contact columns trace to Contact, Company columns trace to Company. All non-ID, non-computed columns are editable (editing `contact_name` updates the Contact record, editing `company_name` updates the Company record).

**Preview detection:** Three entity types detected. Auto-priority: Conversation (FROM entity) → Contact (first JOIN) → Company (second JOIN).

**Inline editing trace-back:**
- User edits `subject` → PATCH `/entities/conversations/cvr_91bc4de6f823` with `{ "subject": "New Subject" }`
- User edits `contact_name` → PATCH `/entities/contacts/con_8f3a2b91c4d7` with `{ "name": "New Name" }`
- User edits `company_name` → PATCH `/entities/companies/cmp_55fg7h23ab8c` with `{ "name": "New Co Name" }`

Three different entity updates from the same view row, each traced back to its source entity via the column registry.

### Example 3: Aggregated Report Data Source (Raw SQL)

**Use case:** "For each Contact, show me a summary of their communication activity."

**Raw SQL:**
```sql
SELECT 
  ct.id AS contact_id,
  ct.name AS contact_name,
  cmp.id AS company_id,
  cmp.name AS company_name,
  COUNT(DISTINCT cvr.id) AS conversation_count,
  COUNT(DISTINCT CASE WHEN cvr.ai_status = 'open' THEN cvr.id END) AS open_conversations,
  COUNT(com.id) AS total_communications,
  MAX(com.timestamp) AS last_communication,
  SUM(CASE WHEN com.channel = 'email' THEN 1 ELSE 0 END) AS email_count,
  SUM(CASE WHEN com.channel = 'sms' THEN 1 ELSE 0 END) AS sms_count,
  SUM(CASE WHEN com.channel = 'phone' THEN 1 ELSE 0 END) AS call_count
FROM contacts ct
LEFT JOIN companies cmp ON ct.company_id = cmp.id
LEFT JOIN conversations cvr ON cvr.primary_contact_id = ct.id
LEFT JOIN communications com ON com.conversation_id = cvr.id
GROUP BY ct.id, ct.name, cmp.id, cmp.name
HAVING COUNT(DISTINCT cvr.id) > 0
ORDER BY last_communication DESC
```

**Column registry:** 11 columns. `contact_id`, `contact_name` traced to Contact (editable). `company_id`, `company_name` traced to Company (editable). All other columns are aggregates — marked as computed, non-editable, source entity = null.

**Preview detection:**
- `contact_id` (`con_` prefix) → **Contact: previewable** (FROM entity, primary)
- `company_id` (`cmp_` prefix) → **Company: previewable** (first JOIN)
- `cvr.id` inside `COUNT(DISTINCT cvr.id)` → **Conversation: excluded** (Rule 1: aggregated)
- `com.id` inside `COUNT(com.id)` → **Communication: excluded** (Rule 1: aggregated)

Auto-priority: Contact → Company. The user clicks a row and previews the Contact. Company is available as secondary preview. Conversation and Communication IDs were detected but correctly excluded because they only appear inside aggregate functions.

### Example 4: Complex Raw SQL with CTE and Window Functions

**Use case:** "Show me each Contact's most recent Conversation, ranked by recency, with a staleness indicator."

**Raw SQL:**
```sql
WITH ranked_conversations AS (
  SELECT 
    cvr.id AS conversation_id,
    cvr.subject,
    cvr.ai_status,
    cvr.last_activity,
    cvr.primary_contact_id,
    ROW_NUMBER() OVER (
      PARTITION BY cvr.primary_contact_id 
      ORDER BY cvr.last_activity DESC
    ) AS recency_rank
  FROM conversations cvr
  WHERE cvr.ai_status != 'closed'
)
SELECT 
  ct.id AS contact_id,
  ct.name AS contact_name,
  ct.email,
  cmp.id AS company_id,
  cmp.name AS company_name,
  rc.conversation_id,
  rc.subject AS latest_conversation_subject,
  rc.ai_status,
  rc.last_activity,
  CASE 
    WHEN rc.last_activity > CURRENT_DATE - INTERVAL '7 days' THEN 'Active'
    WHEN rc.last_activity > CURRENT_DATE - INTERVAL '30 days' THEN 'Stale'
    ELSE 'Dormant'
  END AS engagement_status
FROM contacts ct
LEFT JOIN companies cmp ON ct.company_id = cmp.id
LEFT JOIN ranked_conversations rc 
  ON rc.primary_contact_id = ct.id AND rc.recency_rank = 1
ORDER BY rc.last_activity DESC NULLS LAST
```

**Column registry:** `contact_id`, `contact_name`, `email` → Contact (editable). `company_id`, `company_name` → Company (editable). `conversation_id`, `latest_conversation_subject`, `ai_status`, `last_activity` → Conversation (editable — these are direct field references from the CTE, not aggregates). `engagement_status` → computed (CASE expression, non-editable, type = text).

**Preview detection:**
- `contact_id` → **Contact: previewable** (primary, FROM entity)
- `company_id` → **Company: previewable**
- `conversation_id` → **Conversation: previewable** (this is a specific conversation ID, not aggregated)

Auto-priority: Contact → Company → Conversation. The author might override this to: Contact → Conversation → Company, since the data source is specifically about the most recent conversation. This is where the optional manual declaration adds value.

**Manual override:**
```
Preview Priority: [Contact, Conversation, Company]
Labels: { Conversation: "Most Recent Conversation" }
```

### Example 5: Data Source with Parameters

**Use case:** "Configurable date-range activity report that views can parameterize."

**Raw SQL:**
```sql
SELECT 
  ct.id AS contact_id,
  ct.name AS contact_name,
  COUNT(com.id) AS communication_count,
  MAX(com.timestamp) AS latest_communication
FROM contacts ct
LEFT JOIN conversations cvr ON cvr.primary_contact_id = ct.id
LEFT JOIN communications com ON com.conversation_id = cvr.id
  AND com.timestamp BETWEEN {date_range_start} AND {date_range_end}
WHERE ct.owner_id = {current_user_id}
GROUP BY ct.id, ct.name
ORDER BY communication_count DESC
```

**Parameters:**
| Name | Type | Default | Description |
|---|---|---|---|
| `current_user_id` | System | Auto-resolved | Current user's ID |
| `date_range_start` | Date | 90 days ago | Start of analysis window |
| `date_range_end` | Date | Today | End of analysis window |

**View usage:** A view using this data source displays a date range picker in its header. The user adjusts the range, and the data source re-executes with the new parameter values. Multiple views can use the same data source with different default parameter values — a "Last 30 Days" view and a "Last Quarter" view both reference the same data source but supply different `date_range_start` values.

---

## 23. Performance Considerations

| Concern | Mitigation |
|---|---|
| **Complex JOINs across many entities** | The query engine analyzes JOIN complexity before execution. Queries with >5 JOINs display a performance warning to the author. The execution timeout (30s) prevents runaway queries. |
| **Large result sets** | The 10,000-row result set limit prevents memory exhaustion. View-level pagination further limits what's loaded into the client. Data sources returning >5,000 rows display a recommendation to add filters. |
| **Expensive aggregations** | Aggregation queries (GROUP BY with COUNT/SUM/etc.) are executed server-side. The query engine uses appropriate indexes. For very large base tables, the system may use approximate aggregations (e.g., HyperLogLog for distinct counts) with an "approximate" indicator. |
| **Cached vs. live execution** | The refresh policy (`live`, `cached`, `manual`) controls re-execution frequency. `Cached` data sources store the result set with a configurable TTL (default: 60 seconds). `Manual` data sources re-execute only when the user clicks a refresh button. `Live` re-executes on every view load and filter change. |
| **Concurrent view loads** | When multiple views reference the same data source and are loaded simultaneously (e.g., a dashboard with four views on the same data source), the query engine deduplicates the query — it executes once and distributes the result set to all requesting views. |
| **Parameter variation** | Views with different parameter values cannot share cached results. Each unique parameter combination is a separate cache entry. |

---

## 24. Phasing & Roadmap

### Phase 1: Single-Entity Data Sources

**Goal:** Deliver functional data sources for single-entity queries with visual builder.

- Universal prefixed entity ID convention (all system entities)
- System-generated data sources for all system entity types
- Data source CRUD (create, read, update, delete) for single-entity queries
- Visual query builder: primary entity selection, column selection, default filters, default sort (no JOINs yet)
- Column registry auto-generation from visual builder
- Data source ↔ View referencing
- Data Source API: definition management + single execution endpoint
- Basic cache layer (TTL-based for cached policy)
- Query engine: virtual schema for system entities, tenant isolation, basic pagination

### Phase 2: Cross-Entity Data Sources + Sharing

**Goal:** JOINs across entity types, raw SQL, sharing, versioning.

- Visual query builder: JOIN support (add related entities via relation fields)
- Column registry with multi-entity source tracking
- Entity auto-detection for preview (Layer 1 + Layer 2 inference rules)
- Inline editing trace-back across multiple entities
- Data source sharing (shared/personal visibility)
- Data source schema versioning and breaking change detection
- Raw SQL data source editor (with virtual schema, validation, dry-run)
- SQL parameters (system parameters: current_user, current_date)
- Data source permissions and row-level security
- Batch execution endpoint

### Phase 3: Advanced Query Features + Schema Evolution

**Goal:** Full query power, custom entity support, resilience.

- Custom entity support in virtual schema
- Custom SQL parameters (user-defined, view-supplied)
- Data source refresh policies (live, cached, manual)
- Visual builder → SQL "eject" workflow
- Concurrent query deduplication
- Schema evolution: field change detection and graceful degradation
- Schema evolution: entity type change handling
- Optional manual preview declaration (Layer 3 overrides)
- Staleness indicators in UI
- Performance warnings for complex queries

### Phase 4: Optimization + Future Features

**Goal:** Performance optimization, advanced caching, real-time capabilities.

- Event-driven cache invalidation (optional upgrade from TTL-only)
- Query cost estimation and explain-plan visibility
- Data source templates and pre-built library
- WebSocket/SSE for live data source subscriptions
- Data source lineage and dependency visualization
- SQL guardrails (JOIN limits, cost thresholds)

---

## 25. Dependencies & Related PRDs

| PRD | Relationship | Dependency Direction |
|---|---|---|
| **Views & Grid PRD** | Views consume data sources for rendering. The view system reads the column registry, preview configuration, and query results produced by data sources. View-level filters and sort overrides are composed with data source defaults by the query engine. | **Views depend on Data Sources** for query definitions and result sets. Data Sources are independent of specific view types. |
| **Custom Objects PRD** | Defines the entity types, field registry, field types, and relation model that data sources query against. The prefixed entity ID convention (Section 6) must be adopted as a platform-wide standard. | **Data Sources depend on Custom Objects** for entity type definitions, field registries, and relation metadata. |
| **Communication & Conversation Intelligence PRD** | Defines system entities (Conversations, Communications, Projects, Topics) that are primary entities in many data sources. The alert system uses data source queries as triggers. | **Bidirectional.** Data sources query Communication entities; the alert system consumes data source definitions. |
| **Contact Intelligence PRD** | Defines the Contact entity and identity resolution system. Contact-related data sources and cross-entity JOINs depend on the Contact model. | **Data Sources depend on Contact model** for Contact entity fields and relation resolution. |
| **Permissions & Sharing PRD** | Defines data access controls that determine which records a user can see in data source results. Row-level security (Section 20) and shared data source visibility depend on this. | **Data Sources depend on Permissions** for row-level security, tenant isolation, and shared access control. |

---

## 26. Open Questions

### Migrated from Views & Grid PRD

1. **Formula field computation** — Where are formula fields computed? Client-side (fast but limited to loaded records) or server-side (complete but adds query complexity)? Server-side is more correct but makes formulas dependent on the query engine's expression capabilities. With raw SQL data sources, users can compute formulas in the query itself (CASE expressions, window functions) — does this reduce the need for a separate formula field type?

2. **Column formulas vs. field formulas** — Should the view system support view-level computed columns (like spreadsheet formulas that exist only in the view) in addition to entity-level formula fields (which exist on the object and are available across all views)? With raw SQL data sources, users can already create computed columns via SQL expressions — is a UI-based formula builder additionally needed?

3. **Custom entity scope implications** — With per-user custom entities, if User A shares a data source that queries their custom "Jobs" entity, can User B (who doesn't have a "Jobs" entity) use a view on that data source? The data source defines the schema — does the viewer need the entity type in their own schema, or does the data source's virtual schema suffice?

4. **Relation traversal vs. data source JOINs** — The Relation Traversal system (Views & Grid PRD, Section 10) and Data Source JOINs both achieve cross-entity column display. Should relation traversal remain as a convenience feature within single-entity data sources (auto-generating the JOIN under the hood), or should it be deprecated in favor of explicit data source JOINs? Recommendation: keep both — relation traversal is simpler for common cases; data source JOINs are more powerful for complex cases.

5. **Data source marketplace** — Should there be a community or organization-level library of shared data source templates? Power users create useful queries; other users browse and adopt them for their own views.

6. **SQL guardrails** — What limits should be placed on raw SQL complexity? Maximum number of JOINs? Maximum query cost estimate? Should the system prevent queries that would scan entire large tables without index-aligned filters?

7. **Data source lineage & impact analysis** — When a data source is about to be edited, should the system show which views depend on it and what the impact of the change will be? A visual dependency graph could help authors understand the blast radius of their changes.

### New Open Questions

8. **Query engine physical translation strategy** — The query engine must translate the virtual schema to the physical data store. The optimal translation strategy depends on the physical storage model (dedicated read-model tables, JSONB stores, event-sourced projections, or a hybrid). This decision is deferred to implementation and will be documented in a separate architecture decision record.

9. **Event-driven cache invalidation granularity** — If event-driven invalidation is implemented (Phase 4), what is the granularity? Invalidate all data sources that reference a changed entity type? Or track which specific records a cached result set contains and invalidate only when those specific records change? The former is simpler but causes more cache churn; the latter is more precise but significantly more complex.

10. **Data source execution quotas** — Should there be per-user or per-tenant execution quotas to prevent abuse of expensive queries? If so, how are quotas structured — by execution count, total query time, or result set size? How does the system communicate quota limits to users?

11. **Data source change auditing** — Should changes to data source definitions be tracked in a change log (who changed what, when)? For shared data sources used by a team, this provides accountability and the ability to revert problematic changes.

12. **Cross-tenant data sources** — In future multi-tenant scenarios, should there be a concept of "global" data sources created by platform administrators that are available across all tenants? Use case: pre-built analytical templates that every tenant can use.

---

## 27. Glossary

General platform terms (Entity Bar, Detail Panel, Card-Based Architecture, Attribute Card, etc.) are defined in the **[Master Glossary V3](glossary_V3.md)**. The following terms are specific to this subsystem:

| Term | Definition |
|---|---|
| **Data Source** | A reusable, named query definition that produces a structured result set for one or more views to render. Defines entities involved, available columns, default filters/sort, and previewable entities. Built via visual query builder or raw SQL. |
| **Column Registry** | The schema of a data source's result set. Lists every column with its name, data type, source entity, source field, and editability. The contract between the data source and the views that consume it. |
| **Visual Query Builder** | A UI-based tool for constructing data source queries by selecting entities, joins, columns, and filters without writing SQL. Generates a structured query configuration that the query engine executes. |
| **Virtual Schema** | The logical representation of entity types and fields that raw SQL queries execute against. Users never see the physical database schema — only entity types as tables and fields as columns. |
| **Query Engine** | The system component that translates data source definitions into executable queries against the physical data store. Handles security injection, parameter resolution, pagination, and caching. |
| **Prefixed Entity ID** | A globally unique identifier for any entity in the system, composed of a type prefix + underscore + ULID (e.g., `con_8f3a2b91c4d7` for a Contact). Enables automatic entity type detection from any ID value. |
| **Type Prefix** | A 3-4 character code identifying an entity type (e.g., `con_` for Contact, `cvr_` for Conversation). Registered globally; immutable once assigned. Custom entity types receive auto-generated prefixes. |
| **Preview Configuration** | The metadata on a data source that determines which entities can be previewed from a result row and in what priority order. Auto-detected from prefixed IDs with optional manual overrides. |
| **Entity Reference Column** | A column in a data source result set whose values contain prefixed entity IDs, enabling the system to identify it as a navigable reference to a specific entity record. |
| **Edit Trace-Back** | The mechanism by which an inline edit in a view traces back through the column registry to identify the source entity and field, then issues an update API call to the correct entity endpoint. |
| **Query Eject** | A one-way operation that converts a visual builder data source to raw SQL by copying the generated SQL into the SQL editor. The data source cannot be converted back to visual builder mode. |
| **Schema Version** | A counter on the data source that increments when the column registry changes in ways that could break dependent views (column removed, renamed, or type changed). |
| **Refresh Policy** | How a data source's result set is refreshed: `live` (re-execute on every load), `cached` (TTL-based), or `manual` (user-triggered). |
| **Cache Key** | The composite identifier for a cached result set: data source ID + version + parameter values + user ID + view-level filter hash. Different cache keys produce separate cache entries. |
| **Concurrent Query Deduplication** | When multiple views request the same data source with the same cache key simultaneously, the engine executes the query once and distributes the result to all waiting requests. |
| **Graceful Degradation** | The principle that schema changes (field removal, entity deletion, type changes) cause data sources to produce warnings and partial results rather than failing entirely. |
| **System-Generated Data Source** | An automatically created data source for each entity type that provides unfiltered access to all records. Cannot be modified by users but can be duplicated. |
| **Batch Execution** | A single API call that executes multiple data source queries, with deduplication across identical cache keys. Used for dashboards and multi-view screens. |

---

*This document is a living specification. As the Custom Objects PRD is developed and as implementation progresses, sections will be updated to reflect design decisions, scope adjustments, and lessons learned. Implementation-level decisions (physical storage translation, specific caching infrastructure, API framework details) are documented separately in architecture decision records and the codebase.*
