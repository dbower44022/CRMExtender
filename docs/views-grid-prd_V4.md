# Product Requirements Document: Views & Grid System

## CRMExtender — Polymorphic View & Grid Subsystem

**Version:** 1.2
**Date:** 2026-02-20
**Status:** Draft
**Parent Document:** [CRMExtender PRD v1.1](PRD.md)

> **V1.2 (2026-02-20):**
> Added cross-references to the new [Adaptive Grid Intelligence PRD](adaptive-grid-intelligence-prd_V1.md) in the Column System section (Section 8.3, 8.4), Field Type Registry (Section 9.1), and Dependencies (Section 21). Updated Open Question #5 (conditional formatting). No behavioral changes — this revision adds references only.

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Problem Statement](#2-problem-statement)
3. [Goals & Success Metrics](#3-goals--success-metrics)
4. [User Personas & Stories](#4-user-personas--stories)
5. [Core Concepts & Terminology](#5-core-concepts--terminology)
6. [Data Sources](#6-data-sources)
7. [View Types](#7-view-types)
8. [The Column System](#8-the-column-system)
9. [Field Type Registry](#9-field-type-registry)
10. [Relation Traversal & Lookup Columns](#10-relation-traversal--lookup-columns)
11. [Filtering & Query Builder](#11-filtering--query-builder)
12. [Sorting & Grouping](#12-sorting--grouping)
13. [Grid Interactions](#13-grid-interactions)
14. [Calendar View Specifics](#14-calendar-view-specifics)
15. [Board View Specifics](#15-board-view-specifics)
16. [Timeline View Specifics](#16-timeline-view-specifics)
17. [View Persistence & Sharing](#17-view-persistence--sharing)
18. [View-as-Alert Integration](#18-view-as-alert-integration)
19. [Performance & Pagination](#19-performance--pagination)
20. [Phasing & Roadmap](#20-phasing--roadmap)
21. [Dependencies & Related PRDs](#21-dependencies--related-prds)
22. [Open Questions](#22-open-questions)
23. [Implementation Notes: Infinite Scrolling](#23-implementation-notes-infinite-scrolling-gui-phase-3)
24. [Glossary](#24-glossary)

---

## 1. Executive Summary

The Views & Grid System is the primary data interaction layer of CRMExtender. It provides users with a polymorphic, entity-agnostic framework for displaying, filtering, sorting, grouping, and editing any entity type in the system — whether system-defined (Contacts, Conversations, Communications, Projects, Topics) or user-defined custom objects (Properties, Vehicles, Service Agreements, or anything else a user creates).

The system draws inspiration from tools like ClickUp and Attio, where the same underlying dataset can be rendered through multiple view types — a tabular list/grid, a calendar, or a timeline — each offering a different lens into the same data. Users create as many views as they need, each with its own configuration of visible columns, filters, sort orders, and groupings.

**Core principles:**

- **Entity-agnostic** — The view system does not know or care what entity type it is rendering. It reads from a universal field registry provided by the object model (defined in the Custom Objects PRD). A view of Contacts works identically to a view of a user-defined "Properties" object — same column system, same filters, same interactions.
- **Data Source separation** — The "what data" layer (Data Source) is separated from the "how to render" layer (View). A Data Source is a reusable, named query — built via visual query builder or raw SQL — that defines the columns, joins, and base filters. Multiple views can share one Data Source, each rendering the same dataset as a List, Board, Calendar, or Timeline with its own configuration.
- **Cross-entity queries** — Data Sources can JOIN across entity types, producing denormalized result sets that combine data from Conversations, Contacts, Companies, Projects, and any custom entities. Views render these cross-entity results seamlessly, with inline editing tracing back to the source entity.
- **Polymorphic columns** — Columns adapt based on the entity type being displayed. Each entity type has its own set of fields (system-defined core fields + user-added custom fields), and the column system renders the appropriate editor and display format for each field type.
- **Multiple view types, one dataset** — A single entity collection can be viewed as a List/Grid, Board/Kanban, Calendar, or Timeline. Switching view types preserves filters and sort orders where applicable. Each view type is a rendering strategy, not a different data model.
- **User-owned configuration** — Every aspect of a view (columns, filters, sorts, groups, column widths, column order) is user-configurable and persisted. Views are personal by default and optionally shareable.
- **Relation-aware** — Views can display fields from related entities, not just the primary entity. A Conversations view can show the related Contact's company name, a Project view can show the count of open Conversations — traversing the object graph to surface contextual information.
- **Performance-first for real-world scale** — Designed for datasets in the low thousands of records, with server-side pagination, virtual scrolling, and query optimization ensuring responsive interaction at scale.

**Relationship to other PRDs:** This PRD defines how data is displayed and interacted with. It depends on the Custom Objects PRD (which defines what entities and fields exist) and is consumed by the Communication & Conversation Intelligence PRD (which defines the system entities that are the primary data sources). The alert system defined in the Conversations PRD is built on top of views — an alert is a view with a trigger attached.

---

## 2. Problem Statement

### The Display & Interaction Gap

CRM data is only useful if users can find, view, and act on it efficiently. Yet most CRM tools offer rigid, prescriptive interfaces that force users into a one-size-fits-all display model.

**The consequences for CRM users:**

| Pain Point                          | Impact                                                                                                                                                                                |
| ----------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Fixed views per entity type**     | Each entity type (Contacts, Deals, etc.) has a single hardcoded list view. Users who need different lenses on the same data must export to spreadsheets.                              |
| **No cross-entity context**         | Viewing a Contact doesn't show their Conversations, Projects, or Action Items inline. Users navigate between screens to assemble the full picture.                                    |
| **Rigid column sets**               | Users cannot add, remove, or reorder columns. The CRM decides what's important, not the user.                                                                                         |
| **Primitive filtering**             | Basic filters exist but lack compound logic (AND/OR groups), cross-field conditions, or the ability to filter by related entity fields.                                               |
| **No alternative renderings**       | The same data that works as a list might be far more useful as a calendar (for date-driven entities) or a timeline (for project planning). Users get one rendering.                   |
| **No saved views**                  | Users rebuild the same filters and sorts every session. There's no way to save a "Stale VIP Conversations" view and return to it daily.                                               |
| **Custom objects are second-class** | If the CRM supports custom objects at all, they get a bare-bones list with no filtering, sorting, or grouping. Custom objects deserve the same rich interaction as Contacts or Deals. |
| **No view sharing**                 | Managers who create useful filtered views cannot share them with their team. Everyone builds their own.                                                                               |

### Why Existing Solutions Fall Short

- **Salesforce** — Powerful but complex. List views exist but custom objects require significant configuration. No calendar or timeline views without third-party apps. Views are org-wide, not personal-first.
- **HubSpot** — Clean UI but rigid. Custom objects are limited. No relation-traversal columns. Views are basic filtered lists without grouping or aggregation.
- **Attio** — Closest to the vision. Flexible object model with rich views. But Attio's view types are limited, and relation columns are somewhat constrained. Strong inspiration, but CRMExtender extends the model.
- **ClickUp** — Excellent multi-view paradigm (List, Board, Calendar, Timeline, Gantt). However, ClickUp is task-management-first, not CRM-first. Its data model doesn't support the relationship intelligence and communication hierarchy that CRMExtender requires.

CRMExtender's view system combines Attio's object-model flexibility with ClickUp's multi-view rendering, applied to a communication-intelligence-first CRM.

---

## 3. Goals & Success Metrics

### Primary Goals

1. **Entity-agnostic rendering** — Any entity type (system or custom) can be displayed in any supported view type using the same underlying column, filter, sort, and group infrastructure.
2. **Rich column system** — Users control which columns are visible, their order, width, and pinning. Columns adapt display and editing behavior based on field type. Relation-traversal columns surface cross-entity context.
3. **Powerful filtering** — Users build compound filters with AND/OR logic, using operators appropriate to each field type. Filters can reference fields on related entities.
4. **Flexible sorting & grouping** — Multi-level sorting, group-by with collapsible sections, and summary aggregation rows for grouped data.
5. **Multiple view types** — The same data renders as a List/Grid (tabular), Calendar (date-plotted), or Timeline (date-range bars). Each view type has type-specific configuration while sharing the common filter/sort infrastructure.
6. **Inline editing** — Users edit field values directly in the grid without opening a detail view, for field types that support inline editing.
7. **Persistent, shareable views** — Views are saved with all configuration. Personal views are private by default. Shared views are available to team members (with data permissions enforced).
8. **Alert foundation** — Views serve as the query definition layer for the alert system. Any view can be promoted to an alert with a trigger, frequency, and delivery method.

### Success Metrics

| Metric                                | Target                                                                       | Measurement                                                         |
| ------------------------------------- | ---------------------------------------------------------------------------- | ------------------------------------------------------------------- |
| View creation rate                    | >3 views per user within first 14 days                                       | Analytics: view creation events                                     |
| View type distribution                | All four view types used by >25% of active users                             | Analytics: view type usage                                          |
| Data source creation rate             | >2 custom data sources per user within first 30 days                         | Analytics: data source creation events (excluding system-generated) |
| Cross-entity data source adoption     | >30% of custom data sources include at least one JOIN                        | Analytics: JOIN count per data source                               |
| Data source reuse                     | >20% of data sources are referenced by 2+ views                              | Analytics: view-to-data-source ratio                                |
| Raw SQL adoption                      | >10% of data sources use raw SQL mode                                        | Analytics: query mode distribution                                  |
| Filter complexity                     | >40% of saved views use compound filters (2+ conditions)                     | Analytics: filter condition count                                   |
| Column customization rate             | >60% of users modify default column set within first week                    | Analytics: column add/remove/reorder events                         |
| Inline edit adoption                  | >50% of field edits happen inline (vs. opening detail view)                  | Analytics: edit source tracking                                     |
| Cross-entity inline edit success      | >95% of inline edits on cross-entity data sources succeed                    | Analytics: edit trace-back success/failure                          |
| View load time (List, <1000 rows)     | <500ms to first render                                                       | Instrumented frontend measurement                                   |
| View load time (List, 1000-5000 rows) | <1.5s to first render                                                        | Instrumented frontend measurement                                   |
| Data source query time                | <2s for 95th percentile of data source executions                            | Instrumented backend measurement                                    |
| View sharing adoption                 | >20% of teams have at least one shared view within 30 days                   | Analytics: shared view count per team                               |
| Data source sharing adoption          | >15% of teams have at least one shared data source within 30 days            | Analytics: shared data source count per team                        |
| Relation column usage                 | >25% of saved views include at least one relation-traversal column           | Analytics: column type tracking                                     |
| Preview detection accuracy            | >95% of auto-detected preview entities are correct (not overridden by users) | Analytics: manual override rate as inverse proxy                    |
| User satisfaction with data access    | >80% agree "I can find the data I need quickly"                              | Survey at 30 and 90 days                                            |

---

## 4. User Personas & Stories

### Personas

| Persona                                         | View Needs                                                                                                                               | Key Scenarios                                                                                                                                                                                                    |
| ----------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Alex — Sales Rep**                     | Track active deals, see stale conversations, prep for calls with full context. Uses 2 email accounts, SMS, 30 active deal conversations. | "Show me all Conversations where AI status is Open, grouped by Project, sorted by last activity. Include Contact Company as a column."                                                                           |
| **Maria — Consultant**                   | Monitor client relationships, surface action items, manage 50+ client relationships across channels.                                     | "Calendar view of all Communications this week. Timeline view of all Projects with start/end dates. List view of Contacts with no activity in 30+ days."                                                         |
| **Jordan — Team Lead**                   | Oversee team's client conversations, spot escalation needs, weekly reporting. Manages shared inbox.                                      | "Shared view: all Conversations assigned to my team, grouped by owner, with AI Status and Action Item Count columns. Alert me daily on anything Stale + Open."                                                   |
| **Sam — Gutter Cleaning Business Owner** | Track jobs across multiple cities, manage customer relationships, schedule follow-ups. Custom objects for service areas and jobs.        | "Board view of my custom 'Jobs' object grouped by job status (Scheduled → In Progress → Complete → Invoiced). Calendar view of upcoming jobs. List view filtered by city and service area." |

### User Stories

#### View Creation & Configuration

- **US-V1:** As a user, I want to create a new view for any entity type so that I can see my data the way I need it.
- **US-V2:** As a user, I want to choose a view type (List/Grid, Board/Kanban, Calendar, Timeline) when creating a view so that the rendering matches my use case.
- **US-V3:** As a user, I want to switch a view's type (e.g., from List to Calendar) and have my filters preserved where applicable.
- **US-V4:** As a user, I want to create multiple views of the same entity type, each with different filters and configurations.

#### Data Sources

> Data Source user stories (US-DS1 through US-DS15) are defined in the [Data Sources PRD, Section 4](data-sources-prd.md#4-user-personas--stories).

#### Column Management

- **US-V5:** As a user, I want to add, remove, and reorder columns in a List/Grid view so that I see only the fields I care about.
- **US-V6:** As a user, I want to resize column widths by dragging column borders so that I can allocate screen space to the most important fields.
- **US-V7:** As a user, I want to pin columns to the left side of the grid so they remain visible when I scroll horizontally.
- **US-V8:** As a user, I want to add columns from related entities (e.g., show the Contact's Company on a Conversations view) so that I have cross-entity context without navigating away.
- **US-V9:** As a user, I want the system to provide sensible default columns when I create a view, based on the entity type, that I can then customize.
- **US-V10:** As a user, I want to see columns automatically adapt their display format based on the field type (e.g., dates render as formatted dates, statuses render as colored badges, relations render as clickable links).

#### Filtering

- **US-V11:** As a user, I want to add filter conditions to a view so that I see only records matching my criteria.
- **US-V12:** As a user, I want to build compound filters with AND/OR logic so that I can express complex queries (e.g., "Status is Active AND (Priority is High OR Assignee is Me)").
- **US-V13:** As a user, I want filter operators that match the field type (e.g., "contains" for text, "greater than" for numbers, "is before" for dates, "is any of" for select fields).
- **US-V14:** As a user, I want to filter by fields on related entities (e.g., "Contact → Company = Acme Corp" on a Conversations view).
- **US-V15:** As a user, I want quick filter shortcuts for common conditions (e.g., "Created this week", "Assigned to me", "Status is Open").
- **US-V16:** As a user, I want to save filter configurations as part of the view so they persist between sessions.

#### Sorting & Grouping

- **US-V17:** As a user, I want to sort a view by any visible column (ascending or descending) so that I can order data meaningfully.
- **US-V18:** As a user, I want multi-level sorting (e.g., sort by Status, then by Last Activity within each status) for fine-grained ordering.
- **US-V19:** As a user, I want to group rows by any field so that related records are visually clustered (e.g., group Conversations by Project).
- **US-V20:** As a user, I want collapsible group headers so that I can focus on specific groups while hiding others.
- **US-V21:** As a user, I want summary rows on group headers showing aggregations (count of records, sum/average of numeric fields) for quick insights.

#### Grid Interactions

- **US-V22:** As a user, I want to edit field values directly in the grid cell (inline editing) for field types that support it, so that I don't have to open a detail view for simple changes.
- **US-V23:** As a user, I want to expand a row to see a detail panel (slide-out or inline expansion) for the full record, including fields not shown in the grid columns.
- **US-V24:** As a user, I want to select multiple rows and perform bulk actions (change status, assign to project, delete, export) for efficient batch operations.
- **US-V25:** As a user, I want to click on a row to navigate to the entity's full detail page when I need the complete context.
- **US-V26:** As a user, I want keyboard navigation within the grid (arrow keys, Tab to move between cells, Enter to edit, Escape to cancel) for power-user efficiency.

#### Board / Kanban Interactions

- **US-V27:** As a user, I want to create a Board view grouped by any single-select field so that I can visualize my workflow as a pipeline.
- **US-V28:** As a user, I want to drag cards between Board columns to update the record's status/stage field, so that I can manage workflow progression visually.
- **US-V29:** As a user, I want optional confirmation dialogs on specific column transitions (e.g., moving to "Closed Won") so that significant changes aren't made accidentally.
- **US-V30:** As a user, I want to configure which fields appear on Board cards so that I see the most relevant information at a glance.
- **US-V31:** As a user, I want to see summary aggregations (count, total value) on each Board column so that I can assess pipeline health at a glance.
- **US-V32:** As a user, I want to collapse Board columns I don't need to see (e.g., completed/archived stages) so that I can focus on active work.
- **US-V33:** As a user, I want to add swimlanes to my Board view (e.g., group by Owner across status columns) to create a matrix view of my workflow.

#### View Persistence & Sharing

- **US-V34:** As a user, I want my views to be automatically saved (columns, filters, sorts, groups, scroll position) so that I return to exactly where I left off.
- **US-V35:** As a user, I want to share a view with my team so that everyone benefits from a well-configured data lens.
- **US-V36:** As a user, I want shared views to respect data permissions — sharing the view definition doesn't grant access to records the viewer wouldn't otherwise see.
- **US-V37:** As a user, I want to duplicate a shared view to create my own copy that I can customize without affecting the shared version.
- **US-V38:** As a user, I want to set a view as my default for a specific entity type so that it opens automatically when I navigate to that entity.

#### Alerts (View-to-Alert Promotion)

- **US-V39:** As a user, I want to promote any view to an alert so that I'm notified when new records match the view's filter criteria.
- **US-V40:** As a user, I want to configure alert frequency (immediate, hourly, daily, weekly) and delivery method (in-app, push, email) when promoting a view to an alert.

---

## 5. Core Concepts & Terminology

### 5.1 Conceptual Model

```
Entity Types (from Object Model)
  ├── Contacts (con_)     ── Field Registry: [Name, Email, Phone, Company, ...]
  ├── Conversations (cvr_) ── Field Registry: [Subject, AI Status, Last Activity, ...]
  ├── Companies (cmp_)     ── Field Registry: [Name, Industry, Revenue, ...]
  ├── Projects (prj_)      ── Field Registry: [Name, Status, Owner, ...]
  └── Custom: Jobs (job_)  ── Field Registry: [Address, Service Type, Price, ...]

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

Views (rendering configurations, each referencing a Data Source)
  ├── View: "Pipeline Board" (Board) → references "Deal Pipeline" data source
  │     ├── Board grouping: AI Status
  │     ├── Card fields: [Subject, Contact Name, Company]
  │     └── Additional filters: Owner = Me
  │
  ├── View: "Pipeline List" (List/Grid) → references "Deal Pipeline" data source
  │     ├── Visible columns: [Subject, AI Status, Contact Name, Company, Last Activity]
  │     ├── Sort override: Company ASC
  │     └── Group by: AI Status
  │
  ├── View: "Expected Closes" (Calendar) → references "Deal Pipeline" data source
  │     ├── Date field: Expected Close Date
  │     └── Card fields: [Subject, Contact Name]
  │
  └── View: "Contact Report" (List/Grid) → references "Contact Activity Report" data source
        ├── Visible columns: [Name, Company, Conversation Count, Last Activity]
        └── Sort: Conversation Count DESC
```

### 5.2 Key Concepts

| Concept                | Definition                                                                                                                                                                                                                                                                                                |
| ---------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Entity Type**        | A class of objects in the system. Can be system-defined (Contact, Conversation, Communication, Project, Topic) or user-defined (via the Custom Objects system). Each entity type has a field registry and a type-prefixed ID convention (e.g., `con_` for Contacts).                                      |
| **Field**              | A named, typed attribute of an entity type. Fields have a data type (text, number, date, select, relation, formula, etc.) that determines how they are displayed, edited, filtered, and sorted. Fields are either system-defined (core, locked) or user-defined (custom, added by the user).              |
| **Field Registry**     | The complete set of fields available for an entity type. The view system reads from this registry to know what columns can be displayed, what filter operators apply, and what editors to render. Defined by the Custom Objects PRD.                                                                      |
| **Data Source**        | A reusable, named query definition — built via visual query builder or raw SQL — that produces a structured result set. Defines the entities involved (FROM + JOINs), available columns, default filters, default sort, and previewable entities. Multiple views can share one data source. |
| **Column Registry**    | The schema of a data source's result set. Lists every column with its name, data type, source entity, source field, editability, and aggregation context. The contract between the data source and the views that consume it.                                                                             |
| **View**               | A named, saved configuration that defines how to render the results of a data source. Includes: view type, visible columns (with order, width, pinning), additional filter conditions, sort overrides, and group-by configuration. Each view references exactly one data source.                          |
| **View Type**          | The rendering strategy for a view: List/Grid (tabular rows and columns), Board/Kanban (cards in status columns), Calendar (records plotted on a date grid), or Timeline (records as horizontal bars across a time axis).                                                                                  |
| **Column**             | A single vertical data display slot in a List/Grid view. Maps to a field (either on the primary entity or on a related entity via relation traversal). Has configuration: width, position, pinned state, and sort direction.                                                                              |
| **Relation Traversal** | The ability of a column to display a field from a related entity by following a relation field. Example: a Conversation has a relation field "Primary Contact" pointing to a Contact entity; a column can traverse this relation to display "Primary Contact → Company Name".                      |
| **Filter Condition**   | A single predicate applied to a field: `field` `operator` `value`. Example: `Status equals Active`.                                                                                                                                                                                                       |
| **Filter Group**       | A set of filter conditions combined with AND or OR logic. Filter groups can be nested for compound expressions.                                                                                                                                                                                           |
| **Sort Rule**          | A field + direction (ascending/descending) pair. Multiple sort rules create a multi-level sort.                                                                                                                                                                                                           |
| **Group-By**           | A field used to partition rows into collapsible visual sections. Rows with the same value in the group-by field are clustered together under a group header.                                                                                                                                              |
| **Aggregation**        | A summary computation displayed on a group header or view footer: COUNT, SUM, AVG, MIN, MAX applied to a numeric or date column within a group.                                                                                                                                                           |
| **Default View**       | A system-generated view provided for every entity type when no user views exist. Uses sensible default columns, no filters, sorted by creation date descending.                                                                                                                                           |

### 5.3 View System Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                        VIEW CONFIGURATION                         │
│  (visible columns, additional filters, sorts, groups, view type)  │
└──────────────────────┬───────────────────────────────────────────┘
                       │ references
                       ▼
┌──────────────────────────────────────────────────────────────────┐
│                         DATA SOURCE                               │
│  Reusable query definition (visual builder or raw SQL):           │
│  - Defines entity types involved (FROM + JOINs)                   │
│  - Defines available columns (result set schema)                  │
│  - Defines default filters and sort order                         │
│  - Declares previewable entities (auto-detected + optional        │
│    manual override for priority and exclusions)                    │
│  - Multiple views can share one data source                       │
└──────────────────────┬───────────────────────────────────────────┘
                       │ executes via
                       ▼
┌──────────────────────────────────────────────────────────────────┐
│                         QUERY ENGINE                              │
│  Translates data source + view overrides into executable queries: │
│  - Reads field registry from Object Model                         │
│  - Resolves relation traversals to JOINs                          │
│  - Merges data source defaults with view-level overrides          │
│  - Handles pagination (cursor-based)                              │
│  - Enforces row-level security and tenant isolation               │
└──────────────────────┬───────────────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────────────────┐
│                        RENDERING LAYER                            │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐         │
│  │ List/Grid │  │  Board   │  │ Calendar │  │ Timeline │         │
│  │ Renderer  │  │ Renderer │  │ Renderer │  │ Renderer │         │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘         │
│  Each renderer reads the same query results and renders           │
│  according to its view-type-specific rules.                       │
└──────────────────────────────────────────────────────────────────┘
```

---

## 6. Data Sources

> **This section is a summary.** The complete Data Source specification — including the definition model, visual query builder, raw SQL environment, column registry, entity detection & preview system, inline editing trace-back, query engine, caching & invalidation, schema evolution, API design, permissions, and examples — is defined in the **[Data Sources PRD](data-sources-prd.md)**.

### 6.1 Summary

A **Data Source** is a reusable, named query definition that produces a structured result set for one or more views to render. It is the "what data" layer of the system — separate from the "how to render it" layer (the View). Data Sources are first-class entities (`dts_` prefix) that encapsulate query definitions, column registries, preview configurations, and caching policies.

**Key capabilities relevant to the Views system:**

- **Reusability** — Multiple views reference a single data source. Change the query once, all views reflect the update.
- **Cross-entity queries** — Data sources JOIN across entity types, producing denormalized result sets combining data from any combination of system and custom entities.
- **Column registry contract** — Every data source exposes a column registry that tells views exactly what columns are available, their types, source entities, and editability. Views select from this registry; they cannot add columns not in the data source.
- **Dual authoring** — Visual query builder for most users; raw SQL for power users. Both produce the same artifact.
- **View-level overrides** — Views can add filters (AND'd with data source defaults) and override sort order, but cannot remove data source filters or add columns.
- **Inline editing trace-back** — The column registry maps each column to its source entity and field, enabling views to trace inline edits back to the correct entity API endpoint.
- **Preview detection** — The system auto-detects which entities in a data source result set can be previewed, using the prefixed entity ID convention and inference rules.
- **Cache & refresh** — Data sources specify a refresh policy (`live`, `cached`, `manual`) that governs how results are cached and when they're refreshed.

### 6.2 Data Source ↔ View Relationship Summary

The relationship is **many-to-one**: multiple views can reference the same data source, but each view references exactly one data source.

| Aspect                    | Data Source Defines                              | View Can Do                                                                                      |
| ------------------------- | ------------------------------------------------ | ------------------------------------------------------------------------------------------------ |
| **Available columns**     | The complete column registry                     | Choose which to display, their order, width, pinning. Cannot add columns not in the data source. |
| **Default filters**       | Base filter conditions (the data source's scope) | Add additional filters (AND'd). Cannot remove data source filters.                               |
| **Default sort**          | Base sort order                                  | Override with a different sort, or accept the default.                                           |
| **Parameters**            | Named parameters with optional defaults          | Supply parameter values (e.g., date range picker).                                               |
| **Preview configuration** | Previewable entities with priority               | Accept as-is. Views do not override preview config.                                              |

### 6.3 User Stories

Data Source user stories (US-DS1 through US-DS15) are defined in the [Data Sources PRD, Section 4](data-sources-prd.md#4-user-personas--stories).

---

## 7. View Types

### 7.1 List / Grid View

The primary and most versatile view type. Displays records as rows in a tabular grid with configurable columns.

| Aspect                     | Detail                                                              |
| -------------------------- | ------------------------------------------------------------------- |
| **Rendering**              | Tabular: rows = records, columns = fields                           |
| **Required entity fields** | None — any entity type can be displayed in a grid            |
| **Column support**         | Full: all field types, relation traversal columns, computed columns |
| **Sorting**                | Full: multi-level sort on any column                                |
| **Grouping**               | Full: group-by any field, collapsible sections, aggregation rows    |
| **Filtering**              | Full: all operators, compound logic, relation-field filters         |
| **Inline editing**         | Supported for editable field types                                  |
| **Pagination**             | Server-side cursor-based pagination with virtual scrolling          |
| **Row actions**            | Click to open detail, expand row, select for bulk actions           |

**When to use:** The default for any data exploration, management, or bulk operation task. Suitable for all entity types.

### 7.2 Calendar View

Displays records plotted on a date-based grid (day, week, month views). Each record appears as a card or marker on the date corresponding to its mapped date field.

| Aspect                     | Detail                                                                                                                  |
| -------------------------- | ----------------------------------------------------------------------------------------------------------------------- |
| **Rendering**              | Calendar grid: records as cards on date cells                                                                           |
| **Required entity fields** | At least one date or datetime field to map as the calendar position                                                     |
| **Column support**         | Limited: the calendar card displays a configurable set of fields (title + 1-3 summary fields), not full tabular columns |
| **Sorting**                | N/A — position is determined by date field value                                                                 |
| **Grouping**               | N/A within date cells; optional color-coding by a select/status field                                                   |
| **Filtering**              | Full: same filter engine as List/Grid, applied before rendering                                                         |
| **Inline editing**         | Drag-to-reschedule (changes the date field value)                                                                       |
| **Pagination**             | Date-window-based: load the current month + adjacent months                                                             |
| **Zoom levels**            | Day, Week, Month                                                                                                        |

**Configuration:**

- **Date field mapping** — User selects which date field determines calendar position. If the entity has multiple date fields, the user chooses one (e.g., "Due Date" vs. "Created Date").
- **Duration mapping** (optional) — If the entity has a start date AND end date (or a duration field), records can span multiple days on the calendar.
- **Card display fields** — User selects which fields appear on the calendar card (limited to 1 title field + up to 3 additional fields for space reasons).
- **Color-coding** — User selects an optional select/status field to color-code calendar cards.

**When to use:** Date-driven entities where temporal position matters — Communications (by timestamp), Tasks/Action Items (by due date), custom objects with date fields (Jobs by scheduled date, Events by event date).

### 7.3 Timeline View

Displays records as horizontal bars on a time axis, showing duration and temporal relationships. Useful for project planning, tracking entity lifecycles, and visualizing overlapping time periods.

| Aspect                     | Detail                                                                                    |
| -------------------------- | ----------------------------------------------------------------------------------------- |
| **Rendering**              | Horizontal bars on a scrollable time axis                                                 |
| **Required entity fields** | A start date field. End date field optional (defaults to point-in-time marker if absent). |
| **Column support**         | Left sidebar shows configurable entity fields; the main area is the timeline              |
| **Sorting**                | By start date (default) or any sidebar field                                              |
| **Grouping**               | Full: group rows by any field, creating swimlanes                                         |
| **Filtering**              | Full: same filter engine as List/Grid                                                     |
| **Inline editing**         | Drag bar edges to change start/end dates; drag bar to reposition                          |
| **Pagination**             | Time-window-based: load the current range + buffer                                        |
| **Zoom levels**            | Day, Week, Month, Quarter, Year                                                           |

**Configuration:**

- **Start date field mapping** — Required. Determines the left edge of the bar.
- **End date field mapping** — Optional. Determines the right edge. If not set, records render as point markers (milestones).
- **Sidebar fields** — User selects which fields appear in the left sidebar alongside each bar.
- **Color-coding** — Same as Calendar: optional select/status field for bar coloring.
- **Swimlane grouping** — User selects a group-by field; each unique value gets its own horizontal lane.

**When to use:** Projects (start → end), Conversations (first activity → last activity), custom objects with lifecycle dates, any entity where temporal extent and overlap matter.

### 7.4 Board / Kanban View

Displays records as cards organized into columns, where each column represents a value of a user-selected select/status field. Cards can be dragged between columns to update the underlying field value.

| Aspect                     | Detail                                                                                                          |
| -------------------------- | --------------------------------------------------------------------------------------------------------------- |
| **Rendering**              | Horizontal columns (one per select option), each containing vertically stacked cards                            |
| **Required entity fields** | At least one single-select field to serve as the column grouping field                                          |
| **Column support**         | Limited: each card displays a configurable set of fields (title + 1-4 summary fields), not full tabular columns |
| **Sorting**                | Within each Kanban column: user-defined sort order, or manual drag-to-reorder                                   |
| **Grouping**               | The Kanban columns themselves ARE the grouping. Optional swimlane rows via a second group-by field.             |
| **Filtering**              | Full: same filter engine as List/Grid, applied before rendering                                                 |
| **Inline editing**         | Drag card between columns (updates the grouping field value). Click card to open detail panel for full editing. |
| **Pagination**             | Per-column virtual scrolling: loads first N cards per column, with "Load more" at bottom                        |

**Configuration:**

- **Grouping field** — The user selects any single-select field on the entity type. Each option value in the select field becomes a Kanban column. The column order matches the option order defined on the field.
- **Card title field** — Which field displays as the card's primary text (defaults to name/subject).
- **Card detail fields** — Up to 4 additional fields shown on the card beneath the title.
- **Color-coding** — Optional: a second select/status field to color-code card borders or backgrounds. If not set, cards inherit the color of the Kanban column they're in (from the select field's option colors).
- **Swimlane field** (optional) — A second group-by field that creates horizontal rows across all columns. Example: group Kanban columns by Deal Stage, swimlanes by Owner — creating a matrix of Owner × Stage.
- **Card size** — Compact (title only), Standard (title + 2 fields), or Expanded (title + 4 fields).

**When to use:** Status-driven workflows where progression through stages is the primary interaction — deal pipelines, project phases, task workflows, approval processes. Any entity with a single-select field representing a lifecycle or status.

### 7.5 View Type Compatibility Matrix

Not all entity types are equally suited to all view types. The view system allows any combination but guides users:

| View Type    | Works Best With                            | Requires                                              |
| ------------ | ------------------------------------------ | ----------------------------------------------------- |
| List/Grid    | Any entity type                            | No specific field requirements                        |
| Board/Kanban | Entities with status/stage/phase workflows | At least one single-select field                      |
| Calendar     | Entities with meaningful date fields       | At least one date/datetime field                      |
| Timeline     | Entities with start/end lifecycle dates    | At least one date field (start); end date recommended |

If a user attempts to create a Calendar or Timeline view for an entity type that has no date fields, the system displays a message: "This entity type has no date fields. Add a date field to use Calendar/Timeline views, or choose List/Grid."

If a user attempts to create a Board view for an entity type that has no single-select fields, the system displays a message: "This entity type has no select fields. Add a select field to use Board view, or choose List/Grid."

---

## 8. The Column System

### 8.1 Column Types

Columns in the List/Grid view are the primary mechanism for displaying entity data. There are three column categories:

#### Direct Field Columns

Map directly to a field on the primary entity type. The column displays and edits the field's value using the appropriate renderer for the field's data type.

Example: On a Contacts view, a "Name" column maps directly to the Contact entity's `name` field.

#### Relation Traversal Columns (Lookup Columns)

Display a field from a related entity by following a relation field on the primary entity. These columns are read-only in the grid (the value belongs to the related entity, not the primary).

Example: On a Conversations view, a "Contact → Company" column follows the `primary_contact` relation field to the Contact entity, then displays that Contact's `company` field.

Traversal depth is limited to **one hop** in Phase 1 (primary entity → related entity). Multi-hop traversal (primary → related → related-of-related) is deferred to Phase 2.

#### Computed Columns

Display a value calculated from other fields or from aggregation of related records. Computed columns are always read-only.

Examples:

- **Record count:** "Open Conversation Count" on a Contacts view — counts the number of Conversations with `ai_status = open` related to this Contact.
- **Formula field:** "Days Since Last Activity" — calculates the difference between today and the `last_activity` timestamp.
- **Rollup:** "Total Deal Value" on a Project view — sums the `value` field across all related Deal records.

Computed columns are defined through the formula field type in the Custom Objects PRD. The view system renders them as read-only columns.

### 8.2 Default Column Sets

When a user creates a new view, the system provides a default set of columns based on the entity type. Users can immediately customize this default.

**Default column logic:**

1. **System entities** have curated default columns (see below).
2. **Custom entities** default to: Name/Title field (first text field), Status field (if exists), Created Date, Last Modified Date — plus the first 2-3 custom fields in the order they were defined.

**System entity default columns:**

| Entity Type    | Default Columns                                                               |
| -------------- | ----------------------------------------------------------------------------- |
| Contacts       | Name, Company, Email, Phone, Last Activity, Status                            |
| Conversations  | Subject, Participants, Channel, AI Status, Last Activity, Communication Count |
| Communications | Timestamp, Channel, From, To, Content Preview, Conversation                   |
| Projects       | Name, Status, Owner, Topic Count, Last Activity                               |
| Topics         | Name, Project, Conversation Count, Last Activity                              |

### 8.3 Column Configuration

Each column in a view has the following user-configurable properties:

| Property           | Description                                                                                                                                                                                                                                                                                                                                                                                                  | Default                                                       |
| ------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------- |
| **Field mapping**  | Which field (or relation→field) this column displays                                                                                                                                                                                                                                                                                                                                                  | Set at column creation                                        |
| **Position**       | Left-to-right order in the grid                                                                                                                                                                                                                                                                                                                                                                              | Append to end                                                 |
| **Width**          | Pixel width of the column. When the [Adaptive Grid Intelligence](adaptive-grid-intelligence-prd_V1.md) system is active (`column_auto_sizing = true`), this value is computed by the content analysis engine based on actual data in the result set. The static defaults below serve as fallbacks when auto-sizing is disabled. User manual resize creates a proportional override (see AGI PRD Section 17). | Auto-sized based on field type (see below) or computed by AGI |
| **Pinned**         | Whether the column is pinned to the left and stays visible during horizontal scroll                                                                                                                                                                                                                                                                                                                          | First column pinned by default                                |
| **Visible**        | Whether the column is rendered (allows hiding without removing)                                                                                                                                                                                                                                                                                                                                              | True                                                          |
| **Sort direction** | If this column is part of the active sort: ASC, DESC, or none                                                                                                                                                                                                                                                                                                                                                | None                                                          |
| **Label override** | Optional display name that overrides the field's default label                                                                                                                                                                                                                                                                                                                                               | Field's default label                                         |

**Default column widths by field type:**

| Field Type      | Default Width (px) | Rationale                      |
| --------------- | ------------------ | ------------------------------ |
| Text (short)    | 200                | Names, titles                  |
| Text (long)     | 300                | Descriptions, content previews |
| Number          | 120                | Compact numeric display        |
| Currency        | 140                | Number + currency symbol       |
| Date            | 140                | Formatted date string          |
| Datetime        | 180                | Date + time                    |
| Select (single) | 160                | Badge/tag display              |
| Select (multi)  | 220                | Multiple badges                |
| Checkbox        | 80                 | Minimal width                  |
| Relation        | 200                | Linked entity name             |
| Formula         | 150                | Computed value                 |
| Email           | 220                | Full email address             |
| Phone           | 160                | Formatted phone number         |
| URL             | 200                | Truncated with hover           |

> **Adaptive Grid Intelligence:** When the AGI system is active (default), the static widths above are superseded by content-aware column allocation that analyzes actual data values to determine optimal widths. The AGI system also provides content-aware cell alignment, value diversity analysis (automatic demotion of uniform columns), and format adaptation for constrained widths. See the [Adaptive Grid Intelligence PRD](adaptive-grid-intelligence-prd_V1.md) for complete specification.

### 8.4 Column Operations

| Operation         | Behavior                                                                                                                                                                                                                                                                                                                              |
| ----------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Add column**    | Opens a field picker showing all available fields (direct + relation traversal). Adds the column to the rightmost position.                                                                                                                                                                                                           |
| **Remove column** | Removes the column from the view. Does not delete the field from the entity.                                                                                                                                                                                                                                                          |
| **Reorder**       | Drag-and-drop column headers to change position.                                                                                                                                                                                                                                                                                      |
| **Resize**        | Drag the right edge of a column header to adjust width. Double-click to auto-fit content (when AGI is active, uses content analysis P90 width — see [AGI PRD Section 10](adaptive-grid-intelligence-prd_V1.md#10-intelligent-column-width-allocation)). Manual resize creates a proportional override for future auto-configurations. |
| **Pin/Unpin**     | Toggle column pinning via column header context menu. Pinned columns move to the leftmost positions.                                                                                                                                                                                                                                  |
| **Hide/Show**     | Toggle visibility without removing the column from the view configuration.                                                                                                                                                                                                                                                            |
| **Sort**          | Click column header to toggle sort (none → ASC → DESC → none). Shift+click to add as secondary sort.                                                                                                                                                                                                             |
| **Rename**        | Set a label override via column header context menu.                                                                                                                                                                                                                                                                                  |

---

## 9. Field Type Registry

The view system renders columns, filters, and editors based on field types. Each field type defines its display renderer, edit widget, and applicable filter operators. The field types themselves are defined by the Custom Objects PRD — this section specifies how the view system handles each type.

> **Adaptive Grid Intelligence:** When the [AGI system](adaptive-grid-intelligence-prd_V1.md) is active, display renderers support **format adaptation** — producing compressed output when column width is constrained (e.g., dates as "2/15/26" instead of "Feb 15, 2026"). Cell alignment is also determined dynamically by content rather than statically by field type. See [AGI PRD Sections 10.5](adaptive-grid-intelligence-prd_V1.md#105-content-driven-format-adaptation) and [11](adaptive-grid-intelligence-prd_V1.md#11-content-aware-cell-alignment).

### 9.1 Field Types and View Behavior

| Field Type             | Display Renderer                                             | Inline Editor                         | Supports Sort?                          | Supports Group-By?                                                |
| ---------------------- | ------------------------------------------------------------ | ------------------------------------- | --------------------------------------- | ----------------------------------------------------------------- |
| **Text (single-line)** | Plain text, truncated with ellipsis                          | Text input                            | Yes (alphabetical)                      | Yes                                                               |
| **Text (multi-line)**  | First line + "..." indicator                                 | Expandable textarea (opens in popup)  | Yes (alphabetical)                      | No — too many unique values                                |
| **Number**             | Formatted number (locale-aware, decimal places configurable) | Number input with increment/decrement | Yes (numeric)                           | Yes (with binning option)                                         |
| **Currency**           | Number + currency symbol (e.g., "$1,234.56")                 | Number input with currency prefix     | Yes (numeric)                           | Yes                                                               |
| **Date**               | Formatted date (user's locale, e.g., "Feb 15, 2026")         | Date picker                           | Yes (chronological)                     | Yes (by day, week, month, quarter, year)                          |
| **Datetime**           | Formatted date + time (e.g., "Feb 15, 2026 3:30 PM")         | Datetime picker                       | Yes (chronological)                     | Yes (same as Date)                                                |
| **Select (single)**    | Colored badge/tag                                            | Dropdown select                       | Yes (option order)                      | Yes                                                               |
| **Select (multi)**     | Multiple colored badges                                      | Multi-select dropdown                 | Yes (first option)                      | Yes (one group per option, records can appear in multiple groups) |
| **Checkbox**           | Checked/unchecked icon                                       | Toggle on click                       | Yes (unchecked first or checked first)  | Yes (two groups: checked, unchecked)                              |
| **Relation (single)**  | Linked entity name (clickable)                               | Relation picker (search + select)     | Yes (by display name of related entity) | Yes                                                               |
| **Relation (multi)**   | Comma-separated linked names                                 | Multi-relation picker                 | Yes (first related entity name)         | Yes (one group per related entity)                                |
| **Email**              | Email address (clickable `mailto:`)                          | Email input with validation           | Yes (alphabetical)                      | No                                                                |
| **Phone**              | Formatted phone number (clickable `tel:`)                    | Phone input with formatting           | Yes (alphabetical)                      | No                                                                |
| **URL**                | Truncated URL (clickable, opens in new tab)                  | URL input with validation             | Yes (alphabetical)                      | No                                                                |
| **Formula**            | Computed value (renders based on output type)                | Read-only — not editable       | Yes (based on output type)              | Yes (based on output type)                                        |
| **Rollup**             | Aggregated value from related records                        | Read-only — not editable       | Yes (numeric)                           | Yes                                                               |
| **Rating**             | Star icons (1-5 or configurable range)                       | Click to set stars                    | Yes (numeric)                           | Yes                                                               |
| **Duration**           | Human-readable duration (e.g., "2h 30m")                     | Duration input                        | Yes (numeric, in seconds)               | Yes (with binning option)                                         |
| **User**               | User avatar + name                                           | User picker dropdown                  | Yes (by name)                           | Yes                                                               |

### 9.2 Field Types and Filter Operators

Each field type supports a specific set of filter operators:

| Field Type                       | Available Operators                                                                                                                                                                                                                                      |
| -------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Text**                         | `equals`, `not_equals`, `contains`, `not_contains`, `starts_with`, `ends_with`, `is_empty`, `is_not_empty`                                                                                                                                               |
| **Number / Currency / Duration** | `equals`, `not_equals`, `greater_than`, `less_than`, `greater_than_or_equal`, `less_than_or_equal`, `between`, `is_empty`, `is_not_empty`                                                                                                                |
| **Date / Datetime**              | `equals`, `not_equals`, `is_before`, `is_after`, `is_on_or_before`, `is_on_or_after`, `between`, `is_empty`, `is_not_empty`, `is_within_last` (N days/weeks/months), `is_within_next` (N days/weeks/months), `is_today`, `is_this_week`, `is_this_month` |
| **Select (single)**              | `equals`, `not_equals`, `is_any_of`, `is_none_of`, `is_empty`, `is_not_empty`                                                                                                                                                                            |
| **Select (multi)**               | `contains_any_of`, `contains_all_of`, `contains_none_of`, `is_empty`, `is_not_empty`                                                                                                                                                                     |
| **Checkbox**                     | `is_checked`, `is_not_checked`                                                                                                                                                                                                                           |
| **Relation**                     | `equals` (specific record), `is_any_of` (set of records), `is_empty` (no relation), `is_not_empty` (has relation)                                                                                                                                        |
| **Email / Phone / URL**          | `equals`, `not_equals`, `contains`, `is_empty`, `is_not_empty`                                                                                                                                                                                           |
| **Formula / Rollup**             | Operators based on the output type (e.g., numeric formula gets number operators)                                                                                                                                                                         |
| **Rating**                       | Same as Number                                                                                                                                                                                                                                           |
| **User**                         | `equals`, `not_equals`, `is_any_of`, `is_me` (current user shortcut), `is_empty`, `is_not_empty`                                                                                                                                                         |

### 9.3 Relative Date Operators

Date filters support both absolute values ("is after 2026-01-15") and **relative values** that dynamically resolve:

| Relative Operator         | Resolves To                             |
| ------------------------- | --------------------------------------- |
| `is_today`                | Current date                            |
| `is_this_week`            | Monday through Sunday of current week   |
| `is_this_month`           | First through last day of current month |
| `is_within_last N days`   | Today minus N days through today        |
| `is_within_last N weeks`  | Today minus N×7 days through today  |
| `is_within_last N months` | Today minus N months through today      |
| `is_within_next N days`   | Today through today plus N days         |
| `is_within_next N weeks`  | Today through today plus N×7 days   |
| `is_within_next N months` | Today through today plus N months       |

Relative dates are critical for saved views and alerts — a "Stale Conversations" view filtered by "Last Activity is_within_last 14 days = false" stays current without manual adjustment.

---

## 10. Relation Traversal & Lookup Columns

### 10.1 The Concept

Relation traversal allows a view to display fields that don't belong to the primary entity type but to a related entity. This is one of the most powerful features of the view system — it surfaces cross-entity context without requiring the user to navigate between screens.

### 10.2 How It Works

```
Primary Entity: Conversation
  └── Field: primary_contact (Relation → Contact)

Related Entity: Contact
  ├── Field: company (Text)
  ├── Field: email (Email)
  └── Field: last_activity (Datetime)

Lookup Column: "Primary Contact → Company"
  Step 1: Read the Conversation's primary_contact relation field → get Contact ID
  Step 2: Read the referenced Contact's company field → get "Acme Corp"
  Step 3: Display "Acme Corp" in the column
```

### 10.3 Traversal Rules

| Rule               | Detail                                                                                                                                                                                                                             |
| ------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Depth limit**    | One hop in Phase 1 (A → B). Multi-hop (A → B → C) deferred to Phase 2.                                                                                                                                        |
| **Editability**    | Lookup columns are read-only. The value belongs to the related entity. To edit, the user must open the related entity.                                                                                                             |
| **Null handling**  | If the relation field is empty (no related entity), the lookup column displays "—" (em-dash).                                                                                                                               |
| **Multi-relation** | If the relation field allows multiple related entities, the lookup column displays the field value from the **first** related entity, with a "+N" indicator (e.g., "Acme Corp +2"). Full list available on hover or row expansion. |
| **Filtering**      | Users can filter by lookup column values. The query engine translates this to a JOIN-based filter.                                                                                                                                 |
| **Sorting**        | Users can sort by lookup column values. The query engine translates this to a JOIN-based sort.                                                                                                                                     |

### 10.4 Relation Traversal in the Column Picker

When adding a column, the field picker displays:

```
Add Column
├── Direct Fields
│     ├── Subject
│     ├── AI Status
│     ├── Last Activity
│     └── ...
│
└── Related Entity Fields
      ├── Primary Contact →
      │     ├── Name
      │     ├── Company
      │     ├── Email
      │     └── ...
      │
      └── Project →
            ├── Name
            ├── Status
            └── ...
```

The picker shows all relation fields on the primary entity, and under each, the fields available on the related entity type. This makes it discoverable without requiring users to understand the data model.

### 10.5 Performance Considerations

Relation traversal columns add JOINs to the underlying query. The system:

- Limits the number of relation traversal columns per view to **10** to bound query complexity.
- Uses LEFT JOINs (not INNER) so that records without a related entity still appear in results.
- Caches related entity field values for the current page of results to avoid N+1 queries.
- Displays a performance warning if a view has >5 relation traversal columns: "This view has many lookup columns, which may affect load time."

---

## 11. Filtering & Query Builder

### 11.1 Filter Architecture

The filter system uses a tree structure to represent compound filter logic:

```
Filter Root (AND)
├── Condition: Status = "Active"
├── Condition: Last Activity > "2026-01-01"
└── Group (OR)
      ├── Condition: Priority = "High"
      └── Condition: Assignee = Me
```

This translates to: `Status = Active AND Last Activity > Jan 1 AND (Priority = High OR Assignee = Me)`

### 11.2 Filter Components

#### Filter Condition

A single predicate:

| Component    | Description                                                  | Example                                       |
| ------------ | ------------------------------------------------------------ | --------------------------------------------- |
| **Field**    | The field to filter on (direct or relation traversal)        | `ai_status`, `primary_contact→company` |
| **Operator** | The comparison operator (from the field type's operator set) | `equals`, `contains`, `is_after`              |
| **Value**    | The comparison value (type matches the field)                | `"Open"`, `"Acme"`, `"2026-01-01"`            |

#### Filter Group

A logical combination of conditions and/or nested groups:

| Component    | Description                                                          |
| ------------ | -------------------------------------------------------------------- |
| **Logic**    | `AND` (all conditions must match) or `OR` (any condition must match) |
| **Children** | One or more filter conditions and/or nested filter groups            |

#### Nesting Depth

Filter groups can be nested up to **3 levels deep**. This provides sufficient expressiveness for complex queries without creating an incomprehensible UI:

```
Level 0: Root group (AND/OR)
  Level 1: Nested group
    Level 2: Nested group
      Level 3: Deepest allowed nesting — conditions only, no further groups
```

### 11.3 Quick Filters

For common, frequently used filter patterns, the view provides quick filter controls above the grid — single-click shortcuts that add pre-configured filter conditions:

| Quick Filter             | Adds Condition                                 |
| ------------------------ | ---------------------------------------------- |
| "Assigned to Me"         | `owner/assignee = current_user`                |
| "Created Today"          | `created_at is_today`                          |
| "Created This Week"      | `created_at is_this_week`                      |
| "Created This Month"     | `created_at is_this_month`                     |
| "Has Activity"           | `last_activity is_not_empty`                   |
| "No Activity in 14 Days" | `last_activity is_within_last 14 days = false` |

Quick filters are additive — they add to existing filter conditions (AND logic). They can be toggled on/off without opening the full filter builder.

Entity types can define their own quick filters based on their most commonly filtered fields. System entities have built-in quick filters; custom entities can have user-defined quick filters.

### 11.4 Filter Persistence

Filter configurations are saved as part of the view definition. When a user modifies filters:

- **On a saved view:** Changes are auto-saved to the view.
- **Temporary filter override:** A "Modified" indicator appears. User can save or revert.
- **On a shared view:** Changes create a personal override (fork-on-write). The shared view's filters are unchanged for other users.

### 11.5 Relation-Field Filters

Users can filter by fields on related entities. The UI presents this as:

```
Filter: Primary Contact → Company  equals  "Acme Corp"
```

Under the hood, the query engine translates this to a JOIN + WHERE clause. The same field picker used for columns (Section 9.4) is used for filter field selection.

---

## 12. Sorting & Grouping

### 12.1 Sorting

#### Sort Model

A view's sort configuration is an ordered list of sort rules:

```
Sort Rules:
  1. AI Status ASC (Open first, then Closed, then Uncertain)
  2. Last Activity DESC (most recent first)
```

Records are sorted by the first rule. Ties in the first rule are broken by the second rule, and so on.

#### Sort Configuration

| Property                       | Description                                                                                    |
| ------------------------------ | ---------------------------------------------------------------------------------------------- |
| **Maximum sort levels**        | 5 (sufficient for any practical ordering)                                                      |
| **Default sort**               | Created date descending (most recent first) unless the entity type defines a different default |
| **Sort on any visible column** | Including relation traversal and formula columns                                               |
| **Sort on hidden fields**      | Users can sort by fields not currently displayed as columns                                    |
| **Null handling**              | NULL values sort last (regardless of ASC/DESC)                                                 |

#### Sort Interaction

- **Click column header:** Toggle between ASC → DESC → Remove sort.
- **Shift + click column header:** Add as next-level sort (preserves existing sort rules).
- **Sort panel:** Open a dedicated sort configuration panel to see and reorder all active sort rules.

### 12.2 Grouping

#### Group-By Model

Grouping partitions rows into visual sections based on a field's value. Each unique value creates a group header row with the grouped records beneath it.

```
▼ Project: Acme Acquisition (3 conversations)
    Conversation: Contract Review    Open     Feb 14
    Conversation: Due Diligence      Open     Feb 12
    Conversation: Pricing Discussion Closed   Feb 10

▼ Project: Office Relocation (2 conversations)
    Conversation: Lease Negotiation  Open     Feb 15
    Conversation: Moving Logistics   Closed   Feb 8

▶ Project: (Unassigned) (5 conversations)  [collapsed]
```

#### Group Configuration

| Property                 | Description                                                                                                          |
| ------------------------ | -------------------------------------------------------------------------------------------------------------------- |
| **Maximum group levels** | 2 (group, then sub-group). Example: group by Project, sub-group by AI Status.                                        |
| **Group by any field**   | Including relation fields (group by related entity), select fields, dates (group by month/week), and user fields     |
| **Collapsible groups**   | Each group section can be expanded or collapsed. State is persisted per view.                                        |
| **Group order**          | Groups are sorted alphabetically by default. User can sort groups by aggregation value (e.g., "most records first"). |
| **Empty group**          | Records with null/empty values in the group-by field are collected in an "(Unassigned)" group, displayed last.       |
| **Date grouping bins**   | When grouping by a date field, the user selects the bin size: Day, Week, Month, Quarter, Year.                       |

#### Aggregation Rows

Group headers can display summary aggregations for the records in that group:

| Aggregation   | Applies To                         | Display                 |
| ------------- | ---------------------------------- | ----------------------- |
| **Count**     | Any field (counts non-null values) | "3 conversations"       |
| **Sum**       | Number, Currency fields            | "$45,000"               |
| **Average**   | Number, Currency fields            | "Avg: $15,000"          |
| **Min / Max** | Number, Currency, Date fields      | "Earliest: Feb 8"       |
| **Range**     | Date fields                        | "Feb 8 – Feb 15" |

Aggregations are configured per column in the group header. By default, only Count is shown. Users can add aggregations via the column header context menu.

A **view footer** can also display the same aggregations across all records (ungrouped). This is useful for totals: "Showing 42 records. Total value: $1.2M."

---

## 13. Grid Interactions

### 13.1 Inline Editing

Users can edit field values directly in grid cells for field types that support inline editing. This is the primary editing mechanism for quick updates.

#### Editable vs. Read-Only Fields

| Editable                       | Read-Only                                       |
| ------------------------------ | ----------------------------------------------- |
| Text (single-line, multi-line) | Formula fields                                  |
| Number, Currency, Duration     | Rollup fields                                   |
| Date, Datetime                 | Relation traversal (lookup) columns             |
| Select (single, multi)         | System-computed fields (created_at, updated_at) |
| Checkbox                       | Auto-generated fields (ID, communication count) |
| Rating                         |                                                 |
| Relation (single, multi)       |                                                 |
| Email, Phone, URL              |                                                 |
| User                           |                                                 |

#### Edit Behavior

| Trigger                         | Action                                                                                                    |
| ------------------------------- | --------------------------------------------------------------------------------------------------------- |
| **Double-click cell**           | Activate inline editor for that cell                                                                      |
| **Enter key (cell focused)**    | Activate inline editor                                                                                    |
| **Start typing (cell focused)** | Activate inline editor, pre-fill with typed characters                                                    |
| **Tab key**                     | Save current edit, move to next editable cell in the row                                                  |
| **Shift+Tab**                   | Save current edit, move to previous editable cell                                                         |
| **Escape**                      | Cancel edit, revert to original value                                                                     |
| **Enter (while editing)**       | Save edit, deactivate editor (for single-line text, number, select). For multi-line text, insert newline. |
| **Click outside cell**          | Save edit, deactivate editor                                                                              |

#### Edit Validation

Edits are validated client-side before saving:

- **Type validation:** Number fields reject non-numeric input. Date fields require valid dates.
- **Required field validation:** If a field is marked required, empty values are rejected with an inline error message.
- **Custom validation rules** (from the Custom Objects PRD): If the field has validation constraints (min/max, regex pattern, etc.), they are enforced inline.

Failed validation displays an inline error indicator (red border + tooltip with error message). The cell remains in edit mode until the user corrects the value or presses Escape to cancel.

#### Edit Persistence

Edits are saved immediately (on blur/Tab/Enter) via an API call. The cell displays a brief saving indicator (subtle spinner or checkmark) to confirm the save. If the save fails (network error, validation error from the server), the cell reverts to its previous value with an error notification.

### 13.2 Row Expansion / Detail Panel

When a user needs to see more information than the grid columns show, they can expand a row to display a detail panel:

| Property       | Description                                                                                                                                                      |
| -------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Trigger**    | Click an expand icon on the row, or keyboard shortcut (Space bar with row focused)                                                                               |
| **Rendering**  | A slide-out panel on the right side of the screen, or an inline expansion below the row (user preference)                                                        |
| **Content**    | All fields of the entity, including those not in the grid columns. Rich rendering: multi-line text, full relation lists, attachment previews, activity timeline. |
| **Editing**    | Full editing capability within the detail panel. All field types editable (including multi-line text with full editor).                                          |
| **Navigation** | Up/Down arrows in the detail panel move to the previous/next row's detail, without closing the panel.                                                            |
| **Closing**    | Escape key, click outside panel, or click the close button.                                                                                                      |

### 13.3 Bulk Actions

Users can select multiple rows and perform actions on the entire selection:

#### Selection Mechanics

| Action                    | Behavior                                                                             |
| ------------------------- | ------------------------------------------------------------------------------------ |
| **Click row checkbox**    | Toggle selection for that row                                                        |
| **Shift+click**           | Select range: all rows between last selection and this click                         |
| **Ctrl/Cmd+click**        | Add/remove individual row from selection                                             |
| **"Select All" checkbox** | Select all rows on the current page (with option to "Select all N matching records") |
| **Ctrl/Cmd+A**            | Select all rows on the current page                                                  |

#### Available Bulk Actions

| Action              | Description                                                                                      |
| ------------------- | ------------------------------------------------------------------------------------------------ |
| **Bulk edit field** | Set a field value across all selected records (e.g., change Status to "Archived" for 20 records) |
| **Bulk assign**     | Assign selected records to a project, topic, or user                                             |
| **Bulk delete**     | Delete selected records (with confirmation dialog showing count)                                 |
| **Bulk export**     | Export selected records to CSV or other format                                                   |
| **Bulk tag**        | Add/remove tags or select-field values                                                           |

Bulk actions display a floating action bar at the bottom of the screen when records are selected: "15 records selected — [Edit] [Assign] [Delete] [Export]".

### 13.4 Row Actions (Context Menu)

Right-clicking a row (or clicking a "..." menu on the row) displays a context menu:

| Action        | Description                               |
| ------------- | ----------------------------------------- |
| Open detail   | Navigate to the entity's full detail page |
| Open in panel | Open the row expansion/detail panel       |
| Edit          | Focus the first editable cell in the row  |
| Duplicate     | Create a copy of the record               |
| Delete        | Delete the record (with confirmation)     |
| Copy link     | Copy a direct URL to this record          |
| Assign to...  | Quick-assign to project, topic, or user   |

### 13.5 Keyboard Navigation

| Key                  | Action                                                                |
| -------------------- | --------------------------------------------------------------------- |
| Arrow keys           | Move focus between cells                                              |
| Enter                | Open inline editor on focused cell (or save and move down if editing) |
| Escape               | Cancel editing / deselect                                             |
| Tab / Shift+Tab      | Move to next/previous editable cell                                   |
| Space                | Toggle row expansion (detail panel)                                   |
| Ctrl/Cmd+A           | Select all rows                                                       |
| Delete / Backspace   | Clear cell value (if editable and focused)                            |
| Home / End           | Jump to first/last column in row                                      |
| Ctrl+Home / Ctrl+End | Jump to first/last row                                                |
| Page Up / Page Down  | Scroll by one page (virtual scroll)                                   |

---

## 14. Calendar View Specifics

### 14.1 Calendar Rendering Model

The Calendar view maps records to date cells on a visual calendar grid. Each record appears as a **card** within the cell corresponding to its date field value.

```
┌─────────┬─────────┬─────────┬─────────┬─────────┬─────────┬─────────┐
│   Mon   │   Tue   │   Wed   │   Thu   │   Fri   │   Sat   │   Sun   │
│  Feb 9  │  Feb 10 │  Feb 11 │  Feb 12 │  Feb 13 │  Feb 14 │  Feb 15 │
├─────────┼─────────┼─────────┼─────────┼─────────┼─────────┼─────────┤
│         │ ┌─────┐ │         │ ┌─────┐ │ ┌─────┐ │         │         │
│         │ │ Bob │ │         │ │Due  │ │ │Call │ │         │         │
│         │ │mtg  │ │         │ │Dili │ │ │w/   │ │         │         │
│         │ │ 🟢  │ │         │ │ 🟡  │ │ │Sara │ │         │         │
│         │ └─────┘ │         │ └─────┘ │ │ 🔴  │ │         │         │
│         │         │         │         │ └─────┘ │         │         │
├─────────┼─────────┼─────────┼─────────┼─────────┼─────────┼─────────┤
```

### 14.2 Configuration

| Setting                | Description                                                                        | Required?                      |
| ---------------------- | ---------------------------------------------------------------------------------- | ------------------------------ |
| **Date field**         | Which date/datetime field determines the card's position on the calendar           | Yes                            |
| **End date field**     | Optional second date field for multi-day events (card spans from date to end_date) | No                             |
| **Card title field**   | Which field displays as the card's primary text                                    | Yes (defaults to name/subject) |
| **Card detail fields** | Up to 3 additional fields shown on the card                                        | No                             |
| **Color field**        | A select/status field used to color-code cards                                     | No                             |
| **Default zoom**       | Day, Week, or Month                                                                | Month                          |

### 14.3 Calendar-Specific Interactions

| Interaction                     | Behavior                                                                                                   |
| ------------------------------- | ---------------------------------------------------------------------------------------------------------- |
| **Click card**                  | Open the entity's detail panel                                                                             |
| **Drag card to different date** | Update the date field value (reschedule). Confirmation required if the record has downstream dependencies. |
| **Drag card edges** (multi-day) | Extend or shrink the duration by changing start/end dates                                                  |
| **Click empty date cell**       | Create a new record with the date field pre-filled to that date                                            |
| **Zoom controls**               | Switch between Day / Week / Month views                                                                    |
| **Navigate**                    | Previous/Next buttons and Today button for date navigation                                                 |

### 14.4 Multi-Day Events

When both a start date field and end date field are configured, records can span multiple calendar cells. The card renders as a horizontal bar across the relevant date cells (similar to Google Calendar's multi-day events).

If only a single date field is configured, all records appear as point-in-time cards within a single cell.

### 14.5 Calendar Card Density

When a date cell contains more records than can be visually displayed:

- The cell shows the first N cards (where N depends on the zoom level and cell height).
- A "+X more" indicator appears at the bottom of the cell.
- Clicking "+X more" opens a popover showing all records for that date.

---

## 15. Board View Specifics

### 15.1 Board Rendering Model

The Board view organizes records into vertical columns, where each column corresponds to a value of the user-selected grouping field (a single-select field). Records appear as cards stacked vertically within their column.

```
┌─────────────┬─────────────┬─────────────┬─────────────┐
│  Prospect   │ Negotiation │  Proposal   │   Closed    │
│  (4 cards)  │  (2 cards)  │  (3 cards)  │  (6 cards)  │
├─────────────┼─────────────┼─────────────┼─────────────┤
│ ┌─────────┐ │ ┌─────────┐ │ ┌─────────┐ │ ┌─────────┐ │
│ │ Acme    │ │ │ Beta Co │ │ │ Delta   │ │ │ Epsilon │ │
│ │ $50K    │ │ │ $120K   │ │ │ $80K    │ │ │ $200K   │ │
│ │ Alex    │ │ │ Maria   │ │ │ Alex    │ │ │ Jordan  │ │
│ │ 🟢 Hot  │ │ │ 🟡 Warm │ │ │ 🟢 Hot  │ │ │ 🟢 Won  │ │
│ └─────────┘ │ └─────────┘ │ └─────────┘ │ └─────────┘ │
│ ┌─────────┐ │ ┌─────────┐ │ ┌─────────┐ │ ┌─────────┐ │
│ │ Gamma   │ │ │ Zeta    │ │ │ Theta   │ │ │ Iota    │ │
│ │ $30K    │ │ │ $75K    │ │ │ $45K    │ │ │ $150K   │ │
│ │ Maria   │ │ │ Alex    │ │ │ Jordan  │ │ │ Alex    │ │
│ └─────────┘ │ └─────────┘ │ └─────────┘ │ └─────────┘ │
│   ...       │             │ ┌─────────┐ │   ...       │
│             │             │ │ Kappa   │ │             │
│             │             │ │ $60K    │ │             │
│             │             │ └─────────┘ │             │
├─────────────┼─────────────┼─────────────┼─────────────┤
│ Sum: $145K  │ Sum: $195K  │ Sum: $185K  │ Sum: $890K  │
└─────────────┴─────────────┴─────────────┴─────────────┘
```

### 15.2 Configuration

| Setting                | Description                                                                                                                         | Required?                      |
| ---------------------- | ----------------------------------------------------------------------------------------------------------------------------------- | ------------------------------ |
| **Grouping field**     | Which single-select field determines the Kanban columns. Each option value becomes a column.                                        | Yes                            |
| **Card title field**   | Which field displays as the card's primary text                                                                                     | Yes (defaults to name/subject) |
| **Card detail fields** | Up to 4 additional fields shown on the card                                                                                         | No                             |
| **Color field**        | A select/status field to color-code card borders/backgrounds. If not set, cards use the grouping field's option colors.             | No                             |
| **Swimlane field**     | A second group-by field creating horizontal rows across all columns                                                                 | No                             |
| **Card size**          | Compact, Standard, or Expanded                                                                                                      | Standard (default)             |
| **Column order**       | Matches the option order defined on the select field. Can be overridden by the user via drag-and-drop of column headers.            | Auto from field options        |
| **Sort within column** | How cards are ordered within each column: by a field (any sortable field, ascending or descending) or manual (user drag-to-reorder) | Manual (default)               |

### 15.3 Board-Specific Interactions

| Interaction                       | Behavior                                                                                                                                                           |
| --------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Drag card between columns**     | Updates the grouping field's value on the record. Example: dragging a deal from "Prospect" to "Negotiation" sets `deal_stage = Negotiation`.                       |
| **Drag card within column**       | Reorders the card within its column. If sort-within-column is set to "Manual", the position is persisted. If set to a field sort, manual reorder is not available. |
| **Click card**                    | Opens the entity's detail panel (same as row expansion in List view).                                                                                              |
| **Click "+" at bottom of column** | Creates a new record with the grouping field pre-set to that column's value.                                                                                       |
| **Drag column header**            | Reorder columns (persisted as a view-level override of the field's option order).                                                                                  |
| **Collapse column**               | Collapse a column to a narrow bar showing only the column name and card count. Useful for hiding completed/archived stages. State persisted per view.              |

### 15.4 Drag-to-Column Confirmation

Certain field value transitions may be significant enough to warrant confirmation before the change is applied. The confirmation dialog is **optional and configurable per transition**:

**Configuration model:**

- By default, all drag transitions execute immediately (no confirmation).
- The user (or workspace admin) can mark specific transitions as "confirm before moving" on the grouping field's configuration (defined in the Custom Objects PRD).
- Example: Moving a deal from "Proposal" to "Closed Won" might require confirmation ("Are you sure you want to mark this deal as Closed Won?"), while moving from "Prospect" to "Negotiation" executes silently.

**Confirmation dialog:**

- Displays the card name, the source column, and the target column.
- Optional: if the transition has associated required fields (e.g., "Closed Won" requires a `close_date`), the dialog includes those fields for the user to fill before confirming.
- "Cancel" returns the card to its original column. "Confirm" applies the update.

**Implementation note:** The transition confirmation rules are defined on the field, not on the view. This means the same confirmation rules apply regardless of which Board view the user is in. The rules are configured in the Custom Objects PRD's field definition for select fields.

### 15.5 Column Summaries

Each Kanban column displays a summary footer (or header) with aggregations:

| Aggregation    | Display                                 | Example        |
| -------------- | --------------------------------------- | -------------- |
| **Card count** | Always shown in column header           | "Prospect (4)" |
| **Sum**        | Optional, user-selectable numeric field | "Sum: $145K"   |
| **Average**    | Optional, user-selectable numeric field | "Avg: $36.25K" |

The user configures which aggregations appear via the column header context menu. Count is always visible. Sum and Average require the user to select which numeric field to aggregate.

### 15.6 Swimlanes

When a swimlane field is configured, the board is divided into horizontal rows — one per unique value in the swimlane field. Each swimlane contains its own set of columns, creating a matrix:

```
                 Prospect    Negotiation    Closed
               ┌───────────┬────────────┬──────────┐
  Owner: Alex  │ [Acme]    │ [Zeta]     │ [Iota]   │
               │ [Gamma]   │            │          │
               ├───────────┼────────────┼──────────┤
  Owner: Maria │ [Beta]    │            │ [Kappa]  │
               ├───────────┼────────────┼──────────┤
  Owner: Jordan│           │ [Delta]    │ [Epsilon]│
               └───────────┴────────────┴──────────┘
```

Swimlanes are collapsible. Drag-and-drop between columns within a swimlane updates only the grouping field. Dragging between swimlanes updates the swimlane field (e.g., reassigning ownership).

### 15.7 Empty Columns

If a select field option has no matching records (after filters are applied), the column still renders — but as an empty column with a "+" button to create a new record in that state. This ensures the full workflow pipeline is always visible, even when some stages are empty.

### 15.8 Unset / Null Handling

Records where the grouping field has no value (null/empty) are collected in a special "(No Status)" column, displayed as the first or last column (user-configurable). This column behaves identically to named columns — cards can be dragged out of it to assign a status, or into it to clear the status.

---

## 16. Timeline View Specifics

### 16.1 Timeline Rendering Model

The Timeline view displays records as horizontal bars on a scrollable time axis, with an optional left sidebar showing entity fields.

```
                     Feb 2026
Sidebar          │ W1  │ W2  │ W3  │ W4  │ Mar │
─────────────────┼─────┼─────┼─────┼─────┼─────┤
Acme Acquisition │ ████████████████████░░ │     │
                 │     │     │     │     │     │
Office Relo.     │     │ ███████████████████████│
                 │     │     │     │     │     │
Q1 Hiring        │████████████│     │     │     │
─────────────────┼─────┼─────┼─────┼─────┼─────┤
```

### 16.2 Configuration

| Setting              | Description                                                 | Required?                                 |
| -------------------- | ----------------------------------------------------------- | ----------------------------------------- |
| **Start date field** | Which date field determines the left edge of the bar        | Yes                                       |
| **End date field**   | Which date field determines the right edge of the bar       | No (renders as milestone/point if absent) |
| **Sidebar fields**   | Which fields display in the left sidebar alongside each bar | At least one (defaults to name/subject)   |
| **Color field**      | A select/status field used to color-code bars               | No                                        |
| **Default zoom**     | Day, Week, Month, Quarter, Year                             | Month                                     |
| **Swimlane field**   | Group-by field for horizontal swimlanes                     | No                                        |

### 16.3 Timeline-Specific Interactions

| Interaction             | Behavior                                                                                    |
| ----------------------- | ------------------------------------------------------------------------------------------- |
| **Click bar**           | Open the entity's detail panel                                                              |
| **Drag bar**            | Move the entire bar (updates both start and end dates, preserving duration)                 |
| **Drag left edge**      | Change start date                                                                           |
| **Drag right edge**     | Change end date                                                                             |
| **Click empty area**    | Create a new record with start/end dates pre-filled based on click position and drag extent |
| **Scroll horizontally** | Pan the time axis                                                                           |
| **Zoom controls**       | Switch between Day / Week / Month / Quarter / Year                                          |
| **Mouse wheel + Ctrl**  | Zoom in/out on the time axis                                                                |

### 16.4 Swimlanes

When a swimlane field is configured, the timeline is divided into horizontal lanes — one per unique value in the group-by field. This is the Timeline equivalent of grouping in the List view.

```
                         Feb 2026
                    │ W1  │ W2  │ W3  │ W4  │

▼ Owner: Alex      │     │     │     │     │
  Acme Acquisition  │ ████████████████████░░ │
  Q1 Hiring         │████████████│     │     │

▼ Owner: Maria     │     │     │     │     │
  Office Relo.      │     │ ███████████████████│
```

### 16.5 Milestones

When a record has a start date field but no end date field (or the end date is the same as the start), it renders as a **diamond-shaped milestone** marker on the timeline rather than a bar. This is useful for single-event entities like Communications or Action Items with due dates.

### 16.6 Today Marker

The timeline always displays a vertical "today" line to orient the user in time. Records whose bars cross the today line can be visually distinguished (e.g., a slightly different shade or a pulsing indicator).

---

## 17. View Persistence & Sharing

### 17.1 View Data Model

A view is a first-class entity in the system with the following attributes:

| Attribute                     | Description                                                                                                                                                                                                                                                    |
| ----------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **ID**                        | Prefixed unique identifier (`viw_...`)                                                                                                                                                                                                                         |
| **Name**                      | User-defined view name (e.g., "My Open Conversations")                                                                                                                                                                                                         |
| **Data source**               | Reference to the data source this view renders (`dts_...`). Every view must reference exactly one data source.                                                                                                                                                 |
| **View type**                 | List, Board, Calendar, or Timeline                                                                                                                                                                                                                             |
| **Owner**                     | The user who created the view                                                                                                                                                                                                                                  |
| **Visibility**                | `personal` (only the owner can see it) or `shared` (visible to the team/workspace)                                                                                                                                                                             |
| **Is default**                | Whether this is the default view for its data source for the owner                                                                                                                                                                                             |
| **Column configuration**      | Ordered list of columns from the data source's column registry, with visibility, width, pinned state, and label overrides. Can only reference columns that exist in the data source.                                                                           |
| **Filter configuration**      | Additional filter tree (conditions + groups with AND/OR logic), AND'd with the data source's default filters                                                                                                                                                   |
| **Sort configuration**        | Ordered list of sort rules (field + direction). Overrides the data source's default sort.                                                                                                                                                                      |
| **Group configuration**       | Group-by field, sub-group field, collapsed group states, aggregation settings                                                                                                                                                                                  |
| **Parameter values**          | Values for the data source's parameters (e.g., date range start/end), overriding the data source's defaults                                                                                                                                                    |
| **View-type-specific config** | Calendar: date field mapping, card fields, color field, zoom level. Board: grouping field, card fields, color field, card size, swimlane field, column order, sort-within-column. Timeline: start/end date fields, sidebar fields, swimlane field, zoom level. |
| **Scroll position**           | Last scroll position (restored when returning to the view)                                                                                                                                                                                                     |
| **Created / Updated**         | Timestamps                                                                                                                                                                                                                                                     |

### 17.2 View Lifecycle

| Operation          | Behavior                                                                                                                                                       |
| ------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Create**         | User creates a view, specifying entity type and view type. Default columns, no filters, default sort.                                                          |
| **Auto-save**      | All configuration changes (column moves, filter edits, sort changes, scroll position) are auto-saved as the user makes them. No explicit "Save" button needed. |
| **Rename**         | User can rename a view at any time.                                                                                                                            |
| **Duplicate**      | Creates a copy of the view (including all configuration) as a new personal view.                                                                               |
| **Delete**         | Removes the view. If the view was the user's default for its entity type, the system falls back to the system default view.                                    |
| **Set as default** | Marks this view as the default for its entity type. When the user navigates to that entity type, this view opens automatically.                                |

### 17.3 System Default Views

For every entity type, the system provides a default view that cannot be deleted (but can be customized per user):

- **Data source:** The system-generated data source for the entity type (Section 6.14)
- **Type:** List/Grid
- **Columns:** The entity type's default column set (Section 8.2)
- **Filters:** None (beyond data source defaults)
- **Sort:** Created date descending
- **Groups:** None

When a user customizes the system default view, their changes are stored as a personal override. Other users see the unmodified system default.

### 17.4 Shared Views

| Aspect                   | Behavior                                                                                                                                                                                                                                       |
| ------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Sharing**              | The view owner sets visibility to `shared`. The view appears in the team's view list for the data source's entity scope.                                                                                                                       |
| **Data source access**   | Users creating views on a shared data source can see the data source's column registry and preview configuration but cannot modify the data source itself. They can duplicate it to create their own.                                          |
| **Data permissions**     | Sharing a view shares the rendering configuration, not data access. Each viewer sees only records they have permission to view. A shared "All Conversations" view shows different results for different users based on their data permissions. |
| **Editing shared views** | Only the owner can edit the shared view's definition (columns, filters, sorts). Other users see the owner's configuration.                                                                                                                     |
| **Personal overrides**   | When a non-owner modifies a shared view (changes a filter, reorders columns), the modifications are saved as a personal override. The shared view is unchanged for others.                                                                     |
| **Fork / Duplicate**     | Any user can duplicate a shared view to create their own personal copy, which they can then freely customize.                                                                                                                                  |
| **Unshare**              | The owner can revert a shared view to personal. It disappears from other users' view lists, but their personal overrides and duplicates are preserved.                                                                                         |

### 17.5 View Organization

Views are organized per entity type. When a user navigates to an entity type (e.g., "Conversations"), they see a tab bar or sidebar showing all available views for that entity type:

```
Conversations
  ┌───────────────────────────────────────────────────────────────┐
  │ [My Open Convos ▼] [All Convos] [Stale VIPs] [Team Review*] │ + New View
  └───────────────────────────────────────────────────────────────┘
  * = shared view (indicated by icon)
```

Views are ordered: personal views first (alphabetical), then shared views (alphabetical). The default view is always first.

---

## 18. View-as-Alert Integration

### 18.1 Architecture

The alert system (defined in the Communication & Conversation Intelligence PRD, Section 18) is built on top of views. An alert is a view's filter configuration with a trigger, frequency, and delivery method attached.

```
View: "Stale VIP Conversations"
  Entity type: Conversation
  Filters: Contact→Tag contains "VIP" AND Last Activity is_within_last 14 days = false
  Sort: Last Activity ASC
  │
  └── Alert (optional attachment)
        ├── Trigger: "New records match" (when a Conversation newly matches the filter)
        ├── Frequency: Daily
        ├── Aggregation: Batched (digest)
        └── Delivery: Email
```

### 18.2 Alert Promotion Workflow

1. User creates and configures a view with filters.
2. User clicks "Create Alert from View" (or a bell icon on the view header).
3. System presents alert configuration:
   - **Trigger type:** "New records match" (default) or "Any change to matching records"
   - **Frequency:** Immediate, Hourly, Daily, Weekly
   - **Aggregation:** Individual (one notification per record) or Batched (digest)
   - **Delivery:** In-app notification, Push notification, Email, SMS
4. Alert is saved and begins monitoring.

### 18.3 Alert-View Synchronization

If the user changes the view's filters after creating an alert, the alert's filter criteria update to match. The alert always reflects the current state of its source view's filters.

If the view is deleted, the associated alert is also deleted (with a warning to the user during view deletion).

### 18.4 No Default Alerts

Consistent with the Conversations PRD philosophy: the system sends zero notifications unless the user explicitly creates them. No default alerts are created for any view.

---

## 19. Performance & Pagination

### 19.1 Design Targets

| Scenario                                               | Target Response Time                                                |
| ------------------------------------------------------ | ------------------------------------------------------------------- |
| List view load, <500 records, 0-2 relation columns     | <500ms                                                              |
| List view load, <500 records, 3-5 relation columns     | <800ms                                                              |
| List view load, 500-2000 records, 0-2 relation columns | <1s                                                                 |
| List view load, 500-2000 records, 3-5 relation columns | <1.5s                                                               |
| List view load, 2000-5000 records                      | <2s (with virtual scroll, initial page)                             |
| Calendar view load (month view)                        | <1s                                                                 |
| Timeline view load (month view, <200 records)          | <1s                                                                 |
| Board view load (<200 cards across all columns)        | <800ms                                                              |
| Board view load (200-500 cards)                        | <1.5s                                                               |
| Inline edit save                                       | <300ms                                                              |
| Filter change re-query                                 | <1s                                                                 |
| Sort change                                            | <500ms (client-side for loaded records), <1s (server-side re-query) |

### 19.2 Pagination Strategy

#### Server-Side Cursor-Based Pagination

All views use server-side, cursor-based pagination to handle datasets that exceed the initial page size:

| Parameter        | Value                                                                                                      |
| ---------------- | ---------------------------------------------------------------------------------------------------------- |
| **Page size**    | 50 records (default) — configurable: 25, 50, 100                                                    |
| **Cursor type**  | Opaque token encoding the last record's sort key + ID                                                      |
| **Pre-fetching** | When the user scrolls to within 80% of loaded records, the next page is pre-fetched                        |
| **Total count**  | Returned as a separate, potentially estimated count (exact for <10,000 records; estimated for larger sets) |

#### Virtual Scrolling (List View)

For datasets exceeding one page, the List view uses virtual scrolling:

- Only rows visible in the viewport + a buffer (e.g., 20 rows above and below) are rendered in the DOM.
- As the user scrolls, rows entering the viewport are rendered and rows leaving are removed.
- This ensures consistent DOM performance regardless of total record count.

#### Date-Window Loading (Calendar & Timeline)

Calendar and Timeline views load records within the visible date window plus a buffer:

- **Calendar:** Current month + previous and next month.
- **Timeline:** Current visible range + 50% buffer on each side.
- As the user navigates to new date ranges, additional records are loaded on demand.

#### Per-Column Loading (Board)

Board views load records per Kanban column:

- Each column initially loads the first N cards (default: 20).
- A "Load more" button at the bottom of each column fetches the next batch.
- Columns are loaded in parallel on initial view load.
- Column card counts are fetched as a lightweight summary query before full card data loads, enabling the column headers to display counts immediately.

### 19.3 Query Optimization

| Technique                 | Application                                                                                                         |
| ------------------------- | ------------------------------------------------------------------------------------------------------------------- |
| **Index-aligned sorting** | Ensure that frequently sorted fields (created_at, updated_at, status) are indexed                                   |
| **Relation pre-loading**  | When a view has relation traversal columns, batch-load related entities for the current page (avoiding N+1 queries) |
| **Filter push-down**      | All filter conditions are translated to SQL WHERE clauses and executed server-side, not client-side                 |
| **Aggregation queries**   | Group-by aggregations (count, sum, avg) are computed server-side via SQL GROUP BY, not by loading all records       |
| **Count estimation**      | For large result sets, use `EXPLAIN`-based estimation rather than exact COUNT(*)                                    |

### 19.4 Caching

| Cache Layer                   | What's Cached                                                                        | TTL                                                                                                               |
| ----------------------------- | ------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------- |
| **View configuration**        | Column visibility, filter, sort, group settings                                      | Until modified                                                                                                    |
| **Data source configuration** | Column registry, preview config, default filters/sort                                | Until data source version changes                                                                                 |
| **Field registry**            | Entity type field definitions                                                        | Until schema change                                                                                               |
| **Data source results**       | Query result set for a given parameter combination                                   | Per refresh policy: `live` = no cache, `cached` = configurable TTL (default 60s), `manual` = until user refreshes |
| **Query results (view page)** | Current page of records from data source results                                     | Until data mutation or 60 seconds (whichever is first)                                                            |
| **Relation lookups**          | Related entity field values for current page                                         | Same as query results                                                                                             |
| **Aggregation results**       | Group counts, sums, averages                                                         | Same as query results                                                                                             |
| **Concurrent query dedup**    | Multiple views loading the same data source simultaneously share one query execution | Duration of the query execution                                                                                   |

---

## 20. Phasing & Roadmap

### Phase 1: List/Grid + Single-Entity Data Sources

**Goal:** Deliver a functional List/Grid view backed by data sources for system entities.

- Universal prefixed entity ID convention (all system entities)
- System-generated data sources for all system entity types (Section 6.14)
- Data source CRUD (create, read, update, delete) for single-entity queries
- Visual query builder: primary entity selection, column selection, default filters, default sort (no JOINs yet)
- Column registry auto-generation from visual builder
- View CRUD (create, read, update, delete) referencing a data source
- Column system: select columns from data source's column registry, reorder/resize/pin
- Default column sets for all system entities
- Filter engine: single conditions and AND groups (no nested OR groups yet)
- Quick filters for common patterns
- Single-level sorting (click column header)
- Basic inline editing with entity trace-back (single-entity data sources only)
- Row click to open detail page (single entity type → auto-primary preview)
- Server-side pagination with virtual scrolling
- View persistence (auto-save)
- System default views for all entity types

### Phase 2: Advanced List/Grid + Sharing + Cross-Entity Data Sources

**Goal:** Full filter power, grouping, bulk actions, shared views and data sources, cross-entity JOINs.

- Visual query builder: JOIN support (add related entities via relation fields)
- Column registry with multi-entity source tracking
- Entity auto-detection for preview (Layer 1 + Layer 2 inference rules)
- Multi-entity preview resolution at runtime
- Inline editing trace-back across multiple entities in a single view row
- Data source sharing (shared/personal visibility)
- Data source schema versioning and breaking change detection
- Raw SQL data source editor (with virtual schema, validation, dry-run)
- SQL parameters (system parameters: current_user, current_date)
- Compound filters with AND/OR groups (up to 3 levels)
- Multi-level sorting (up to 5 levels)
- Group-by with collapsible sections
- Aggregation rows (count, sum, avg on group headers and view footer)
- Bulk actions (bulk edit, assign, delete, export)
- Row expansion / detail panel (slide-out)
- Keyboard navigation
- Shared views with data permissions
- Personal overrides on shared views
- View duplication

### Phase 3: Calendar + Board Views + Data Source Polish

**Goal:** Calendar and Board view types; advanced data source features.

- Calendar view rendering (month/week/day)
- Calendar card configuration (title, detail fields, color)
- Drag-to-reschedule on calendar
- Multi-day event support
- Calendar-specific interactions (click empty cell to create)
- Board/Kanban view rendering
- Board configuration (grouping field, card fields, color, card size)
- Drag-to-column with field value update
- Transition confirmation dialog (configurable per field transition)
- Board column summaries (count, sum, avg)
- Board column collapse
- Board swimlanes
- Optional manual preview declaration (Layer 3 overrides)
- Custom SQL parameters (user-defined, view-supplied)
- Data source refresh policies (live, cached, manual)
- Visual builder → SQL "eject" workflow
- Data source concurrent query deduplication

### Phase 4: Timeline View + Alerts + Polish

**Goal:** Timeline view type; view-to-alert promotion; performance optimization.

- Timeline view rendering with horizontal bars
- Timeline configuration (start/end date, sidebar, swimlanes)
- Timeline interactions (drag to reschedule, drag edges, zoom)
- Milestone rendering (point-in-time entities)
- Today marker
- View-to-alert promotion workflow
- Alert configuration (frequency, aggregation, delivery)
- Performance optimization for views with >5 relation columns
- Computed/formula column support in views
- Multi-hop relation traversal (Phase 2 of relation system)

---

## 21. Dependencies & Related PRDs

| PRD                                                                        | Relationship                                                                                                                                                                                                                                                                                                                                              | Dependency Direction                                                                                                                                                                          |
| -------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Data Sources PRD**                                                       | Defines the complete data source and query abstraction layer that views consume. Includes the data source definition model, query engine, column registry, preview system, inline editing trace-back, caching, schema evolution, and API. Section 6 of this document is a summary; the Data Sources PRD is the authoritative source.                      | **Views depend on Data Sources** for query definitions and result sets. Data Sources are independent of specific view types.                                                                  |
| **Custom Objects PRD**                                                     | Defines the entity types, field registry, field types, and relation model that data sources query and views render. The prefixed entity ID convention (Section 6.2) must be adopted as a platform-wide standard in this PRD. Select field transition confirmation rules (Section 15.4) are defined on the field in this PRD.                              | **Bidirectional.** View/Data Source system depends on Object Model for field registry and entity definitions. Object Model must adopt prefixed IDs and transition confirmation configuration. |
| **Communication & Conversation Intelligence PRD**                          | Defines system entities (Conversations, Communications, Projects, Topics, Contacts) that are the primary entities queried by data sources. Also defines the alert system architecture that views feed into.                                                                                                                                               | **Bidirectional.** Data sources query Conversation entities; Conversations PRD's alert system consumes view filter definitions.                                                               |
| **Contact Intelligence PRD**                                               | Defines the Contact entity and identity resolution system. Contact-related data sources and views depend on this. Cross-entity data sources frequently JOIN to the Contact entity.                                                                                                                                                                        | **View/Data Source system depends on Contact model** for Contact entity fields and relation resolution.                                                                                       |
| **Permissions & Sharing PRD**                                              | Defines data access controls that determine which records a user can see in data source results. Row-level security in the query engine (Section 6.12) depends on this. Shared data source and view visibility is governed by these permissions.                                                                                                          | **View/Data Source system depends on Permissions** for row-level security, data filtering, and shared access control.                                                                         |
| **[Adaptive Grid Intelligence PRD](adaptive-grid-intelligence-prd_V1.md)** | Defines the intelligent layout engine that automatically optimizes column widths, cell alignment, panel proportions, and row density based on display characteristics, content analysis, and user preferences. Extends the column system (Section 8), field type registry (Section 9), view persistence (Section 17), and the GUI PRD's four-zone layout. | **Bidirectional.** AGI extends the column and view system defined here; this PRD defines the column and view foundations that AGI optimizes.                                                  |
| **AI Learning & Classification PRD**                                       | AI-generated fields (AI Status, AI Summary, Action Items, Key Topics) are exposed as queryable fields in data sources and displayable columns in views. The AI system may also use view configurations as context for learning user preferences.                                                                                                          | **View system consumes AI fields** as queryable and displayable columns.                                                                                                                      |

---

## 22. Open Questions

> **Note:** Open questions #2, #6, #10, #11, #13, #14, and #15 from the original version of this document have been migrated to the [Data Sources PRD, Section 26](data-sources-prd.md#26-open-questions) as they pertain to data source functionality rather than view rendering.

1. **Multi-entity views vs. cross-entity data sources** — With Data Sources now supporting JOINs across entity types, the original "multi-entity view" question is partially addressed. A data source joining Conversations + Contacts + Companies produces a cross-entity result set. However, this is still a flattened/denormalized view. Should there also be a "unified activity feed" view type that displays heterogeneous entity types (a Conversation row, then a Communication row, then a Project row) in a single chronological stream? This would require a fundamentally different rendering model where each row can have a different column schema.

2. **Formula field computation** — Where are formula fields computed? Client-side (fast but limited to loaded records) or server-side (complete but adds query complexity)? Server-side is more correct but makes formulas dependent on the query engine's expression capabilities. With raw SQL data sources, users can compute formulas in the query itself (CASE expressions, window functions) — does this reduce the need for a separate formula field type?

3. **View templates** — Should the system provide pre-built view templates that include both a data source and a view configuration (e.g., a "Sales Pipeline" template that creates a cross-entity data source + Board view)? Could accelerate onboarding.

4. **Export formats** — Beyond CSV, should views support export to Excel (.xlsx), PDF, or direct integration with reporting tools? What about scheduled exports (e.g., "email me this view as a CSV every Monday")?

5. **Conditional formatting** (partially addressed by [Adaptive Grid Intelligence PRD](adaptive-grid-intelligence-prd_V1.md)) — Should cells/rows support conditional formatting rules (e.g., "if AI Status = Open, highlight row in yellow", "if Days Since Last Activity > 30, make cell red")? This is powerful but adds significant UI complexity. **Note:** The [Adaptive Grid Intelligence PRD](adaptive-grid-intelligence-prd_V1.md) addresses content-aware column optimization (auto-sizing, alignment, value diversity demotion) but does not cover rule-based conditional formatting (user-defined color/style rules). Conditional formatting remains a future PRD that can build on the AGI content analysis engine.

6. **Column formulas vs. field formulas** — Should the view system support view-level computed columns (like spreadsheet formulas that exist only in the view) in addition to entity-level formula fields (which exist on the object and are available across all views)? With raw SQL data sources, users can already create computed columns via SQL expressions — is a UI-based formula builder additionally needed?

7. **Saved filter presets** — Should filter configurations be saveable independently of views, so that the same filter preset can be applied to multiple views? Or is the Data Source's default filter + view-level filter composition sufficient?

8. **Collaborative real-time editing** — If two users are viewing the same shared view and one edits a record inline, should the other see the change in real-time (like Google Sheets)? Or is refresh-on-demand sufficient? This is particularly complex with cross-entity data sources where an edit to a Company record should propagate to all rows referencing that Company.

9. **Print / presentation mode** — Should views have a "print-friendly" rendering that removes interactive controls and optimizes for paper or screen sharing? Relevant for managers presenting data in meetings.

10. **Custom entity scope implications** — With per-user custom entities, if User A shares a data source that queries their custom "Jobs" entity, can User B (who doesn't have a "Jobs" entity) use a view on that data source? The data source defines the schema — does the viewer need the entity type in their own schema, or does the data source's virtual schema suffice?

11. **Relation traversal vs. data source JOINs** — The Relation Traversal system (Section 10) and Data Source JOINs both achieve cross-entity column display. Should relation traversal remain as a convenience feature within single-entity data sources (auto-generating the JOIN under the hood), or should it be deprecated in favor of explicit data source JOINs? Recommendation: keep both — relation traversal is simpler for common cases; data source JOINs are more powerful for complex cases.

12. **Mobile rendering** — How do List/Grid, Board, Calendar, and Timeline views render on mobile devices? The List view likely needs a card-based responsive rendering. Board may need a single-column swipeable layout. Calendar and Timeline may need simplified mobile-specific layouts.

13. **Data source marketplace** — Should there be a community or organization-level library of shared data source templates? Power users create useful queries; other users browse and adopt them for their own views.

14. **SQL guardrails** — What limits should be placed on raw SQL complexity? Maximum number of JOINs? Maximum query cost estimate? Should the system prevent queries that would scan entire large tables without index-aligned filters?

15. **Data source lineage & impact analysis** — When a data source is about to be edited, should the system show which views depend on it and what the impact of the change will be? A visual dependency graph could help authors understand the blast radius of their changes.

---

## 23. Implementation Notes: Infinite Scrolling (GUI Phase 3)

> For detailed implementation reference including code patterns and failed approaches, see [`features.md`](../memory/features.md) under "Infinite Scrolling — GUI Phase 3".

### 23.1 Overview

The React frontend grid replaces page-based Prev/Next pagination (Section 19.2) with automatic infinite scrolling. As the user scrolls toward the bottom of the loaded data, the next page of records is fetched and appended seamlessly. This combines server-side page-based loading with client-side row accumulation and virtual scrolling.

### 23.2 Architecture

```
 User scrolls down
       |
       v
 Scroll-bottom detection (< 300px from end)
       |
       v
 fetchNextPage()  -->  GET /api/v1/views/{id}/data?page=N
       |                         |
       v                         v
 useInfiniteQuery           Server returns:
 accumulates pages          { rows, total, page, per_page, has_more }
       |
       v
 rows = pages.flatMap(p => p.rows)   // flatten all pages
       |
       v
 useVirtualizer renders visible rows in viewport
```

### 23.3 API Changes

The `/api/v1/views/{view_id}/data` endpoint now returns a `has_more` boolean alongside the existing pagination fields:

```json
{
  "rows": [...],
  "total": 512,
  "page": 1,
  "per_page": 50,
  "has_more": true
}
```

The `has_more` field is computed as `page * per_page < total`. The existing `page` query parameter continues to work unchanged, maintaining backward compatibility with the HTMX web UI.

### 23.4 Frontend Data Flow

| Component                            | Role                                                                                         |
| ------------------------------------ | -------------------------------------------------------------------------------------------- |
| `useInfiniteViewData()` (`views.ts`) | `useInfiniteQuery` wrapper — manages page accumulation, determines next page from `has_more` |
| `DataGrid.tsx`                       | Flattens all pages into a single row array, detects scroll-near-bottom to trigger next fetch |
| `useVirtualizer`                     | Renders only visible rows + 10-row overscan buffer in the DOM                                |
| Navigation store                     | No longer tracks `page` — query resets are handled by `useInfiniteQuery`'s query key         |

### 23.5 Status Bar

The pagination bar (Prev / Page N / Next) is replaced with a compact status bar:

- **Left:** `"{loaded count} of {total}"` — e.g., "150 of 512"
- **Right:** Loading spinner + "Loading more..." during `isFetchingNextPage`
- **Right:** "Updating..." during background refetch (sort/filter change)

### 23.6 Scroll Container & Known Workaround

The scroll container uses `calc(100vh - 130px)` for its `maxHeight`, which accounts for the top header bar, grid toolbar, and status bar.

**Critical workaround:** Inside `react-resizable-panels`, `overflowY: 'auto'` does not engage on initial render — the browser does not recognize that content overflows until a reflow is triggered. The fix toggles the overflow style after data loads:

```tsx
useEffect(() => {
  const el = tableContainerRef.current
  if (!el || !rows.length) return
  requestAnimationFrame(() => {
    el.style.overflowY = 'scroll'
    requestAnimationFrame(() => {
      el.style.overflowY = 'auto'
    })
  })
}, [rows.length])
```

This forces the browser to recalculate overflow, enabling the scrollbar and scroll events that drive infinite loading.

### 23.7 Behavior on Sort / Search / Filter Change

When the user changes sort, search text, or quick filters, the `useInfiniteQuery` query key changes, which automatically:

1. Discards all accumulated pages
2. Fetches page 1 with the new parameters
3. Resets the scroll position to the top

No explicit `page` reset is needed — this is handled by React Query's cache invalidation.

---

## 24. Glossary

| Term                                          | Definition                                                                                                                                                                                                                                         |
| --------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Data Source**                               | A reusable, named query definition that produces a structured result set for one or more views to render. Defines entities involved, available columns, default filters/sort, and previewable entities. Built via visual query builder or raw SQL. |
| **Column Registry**                           | The schema of a data source's result set. Lists every column with its name, data type, source entity, source field, and editability. The contract between the data source and the views that consume it.                                           |
| **Visual Query Builder**                      | A UI-based tool for constructing data source queries by selecting entities, joins, columns, and filters without writing SQL. Generates a structured query configuration that the query engine executes.                                            |
| **Virtual Schema**                            | The logical representation of entity types and fields that raw SQL queries execute against. Users never see the physical database schema — only entity types as tables and fields as columns.                                               |
| **Prefixed Entity ID**                        | A globally unique identifier for any entity in the system, composed of a type prefix + underscore + ULID (e.g., `con_8f3a2b91c4d7` for a Contact). Enables automatic entity type detection from any ID value.                                      |
| **Type Prefix**                               | A 3-4 character code identifying an entity type (e.g., `con_` for Contact, `cvr_` for Conversation). Registered globally; immutable once assigned. Custom entity types receive auto-generated prefixes.                                            |
| **Preview Configuration**                     | The metadata on a data source that determines which entities can be previewed from a result row and in what priority order. Auto-detected from prefixed IDs with optional manual overrides.                                                        |
| **Entity Reference Column**                   | A column in a data source result set whose values contain prefixed entity IDs, enabling the system to identify it as a navigable reference to a specific entity record.                                                                            |
| **Edit Trace-Back**                           | The mechanism by which an inline edit in a view traces back through the column registry to identify the source entity and field, then issues an update API call to the correct entity endpoint.                                                    |
| **Query Eject**                               | A one-way operation that converts a visual builder data source to raw SQL by copying the generated SQL into the SQL editor. The data source cannot be converted back to visual builder mode.                                                       |
| **Schema Version**                            | A counter on the data source that increments when the column registry changes in ways that could break dependent views (column removed, renamed, or type changed).                                                                                 |
| **View**                                      | A named, saved configuration defining how to render the results of a data source. Includes view type, visible columns, additional filters, sort overrides, and grouping. Each view references exactly one data source.                             |
| **View type**                                 | The rendering strategy: List/Grid (tabular), Board/Kanban (cards in status columns), Calendar (date-plotted cards), or Timeline (horizontal bars on time axis).                                                                                    |
| **Entity type**                               | A class of objects (system-defined like Contact/Conversation, or user-defined custom objects). Defined by the Custom Objects PRD.                                                                                                                  |
| **Field**                                     | A named, typed attribute on an entity type. Has a data type that determines display, editing, filtering, and sorting behavior.                                                                                                                     |
| **Field registry**                            | The complete set of fields available on an entity type, including system fields and user-defined custom fields.                                                                                                                                    |
| **Column**                                    | A vertical display slot in a List/Grid view, mapped to a field (direct or relation traversal).                                                                                                                                                     |
| **Kanban column**                             | A vertical lane in a Board view, representing a single value of the grouping field (a select/status field). Not to be confused with grid columns.                                                                                                  |
| **Direct field column**                       | A column that maps to a field on the primary entity type.                                                                                                                                                                                          |
| **Relation traversal column (lookup column)** | A column that displays a field from a related entity by following a relation field. Read-only.                                                                                                                                                     |
| **Computed column**                           | A column displaying a value calculated from other fields or aggregated from related records. Read-only.                                                                                                                                            |
| **Filter condition**                          | A single predicate: field + operator + value.                                                                                                                                                                                                      |
| **Filter group**                              | A set of conditions combined with AND or OR logic. Can be nested.                                                                                                                                                                                  |
| **Quick filter**                              | A pre-configured, single-click filter shortcut for common conditions.                                                                                                                                                                              |
| **Sort rule**                                 | A field + direction (ASC/DESC) pair. Multiple rules create a multi-level sort.                                                                                                                                                                     |
| **Group-by**                                  | A field used to partition view rows into collapsible visual sections.                                                                                                                                                                              |
| **Grouping field**                            | In a Board view, the single-select field whose option values define the Kanban columns.                                                                                                                                                            |
| **Aggregation**                               | A summary computation (COUNT, SUM, AVG, MIN, MAX) displayed on group headers or view footers.                                                                                                                                                      |
| **Inline editing**                            | Editing a field value directly in a grid cell without opening a detail view.                                                                                                                                                                       |
| **Row expansion**                             | Opening a detail panel for a row to see all fields and rich content.                                                                                                                                                                               |
| **Bulk action**                               | An operation performed on multiple selected records simultaneously.                                                                                                                                                                                |
| **Virtual scrolling**                         | A rendering technique where only visible rows are in the DOM, enabling smooth scrolling for large datasets.                                                                                                                                        |
| **Cursor-based pagination**                   | A pagination strategy using an opaque token (cursor) that encodes the position of the last loaded record, enabling efficient page-by-page loading.                                                                                                 |
| **Personal override**                         | A user's local modifications to a shared view, stored separately from the shared view definition.                                                                                                                                                  |
| **Swimlane**                                  | A horizontal lane in a Timeline or Board view, created by grouping records by a field value. In Board views, swimlanes create a matrix of group-by × status.                                                                                   |
| **Milestone**                                 | A point-in-time marker on a Timeline view, used for records with a single date field (no duration).                                                                                                                                                |
| **Card**                                      | A compact visual representation of a record, used in Calendar and Board views. Shows title and configurable summary fields.                                                                                                                        |
| **Date-window loading**                       | A data loading strategy for Calendar and Timeline views that fetches records within the visible time range plus a buffer.                                                                                                                          |
| **Fork-on-write**                             | The behavior where modifying a shared view creates a personal copy of the modifications without affecting the shared definition.                                                                                                                   |
| **Transition confirmation**                   | An optional dialog shown when dragging a Board card between columns, configurable per field transition. Prevents accidental status changes for significant transitions.                                                                            |
| **Column collapse**                           | In a Board view, reducing a Kanban column to a narrow bar showing only the name and count, useful for hiding completed stages.                                                                                                                     |

---

*This document is a living specification. As the Custom Objects PRD is developed and as implementation progresses, sections will be updated to reflect design decisions, scope adjustments, and lessons learned. The phasing roadmap will be synchronized with the Custom Objects PRD to ensure dependencies are resolved in the correct order.*
