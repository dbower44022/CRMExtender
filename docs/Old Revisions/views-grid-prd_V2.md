# Product Requirements Document: Views & Grid System

## CRMExtender — Polymorphic View & Grid Subsystem

**Version:** 1.0
**Date:** 2026-02-15
**Status:** Draft
**Parent Document:** [CRMExtender PRD v1.1](PRD.md)

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
23. [Glossary](#23-glossary)

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

| Persona                                  | View Needs                                                                                                                               | Key Scenarios                                                                                                                                                                               |
| ---------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Alex — Sales Rep**                     | Track active deals, see stale conversations, prep for calls with full context. Uses 2 email accounts, SMS, 30 active deal conversations. | "Show me all Conversations where AI status is Open, grouped by Project, sorted by last activity. Include Contact Company as a column."                                                      |
| **Maria — Consultant**                   | Monitor client relationships, surface action items, manage 50+ client relationships across channels.                                     | "Calendar view of all Communications this week. Timeline view of all Projects with start/end dates. List view of Contacts with no activity in 30+ days."                                    |
| **Jordan — Team Lead**                   | Oversee team's client conversations, spot escalation needs, weekly reporting. Manages shared inbox.                                      | "Shared view: all Conversations assigned to my team, grouped by owner, with AI Status and Action Item Count columns. Alert me daily on anything Stale + Open."                              |
| **Sam — Gutter Cleaning Business Owner** | Track jobs across multiple cities, manage customer relationships, schedule follow-ups. Custom objects for service areas and jobs.        | "Board view of my custom 'Jobs' object grouped by job status (Scheduled → In Progress → Complete → Invoiced). Calendar view of upcoming jobs. List view filtered by city and service area." |

### User Stories

#### View Creation & Configuration

- **US-V1:** As a user, I want to create a new view for any entity type so that I can see my data the way I need it.
- **US-V2:** As a user, I want to choose a view type (List/Grid, Board/Kanban, Calendar, Timeline) when creating a view so that the rendering matches my use case.
- **US-V3:** As a user, I want to switch a view's type (e.g., from List to Calendar) and have my filters preserved where applicable.
- **US-V4:** As a user, I want to create multiple views of the same entity type, each with different filters and configurations.

#### Data Sources

- **US-DS1:** As a user, I want to create a data source using a visual query builder so that I can define what data my views display without writing SQL.
- **US-DS2:** As a power user, I want to write raw SQL data sources so that I can express complex queries with CTEs, window functions, and aggregations.
- **US-DS3:** As a user, I want to create a data source that JOINs across multiple entity types (e.g., Conversations + Contacts + Companies) so that I can see cross-entity context in a single view.
- **US-DS4:** As a user, I want multiple views to share the same data source so that I can render the same dataset as a List, Board, and Calendar without duplicating the query.
- **US-DS5:** As a user, I want the system to auto-detect which entity types are in my data source results so that I can preview any entity from a row click.
- **US-DS6:** As a user, I want to optionally override the preview priority when the auto-detection doesn't match my intent (e.g., prioritize Company over Contact).
- **US-DS7:** As a user, I want to share data sources with my team so that others can build views on well-crafted queries without needing to understand the underlying data model.
- **US-DS8:** As a user, I want to add view-level filters on top of the data source's base filters so that different views of the same data source can show different subsets.
- **US-DS9:** As a user, I want data sources with parameters (e.g., date range, current user) so that the same query adapts to different contexts.
- **US-DS10:** As a user, I want inline editing in views powered by cross-entity data sources to trace back and update the correct source entity.

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

| Concept                | Definition                                                                                                                                                                                                                                                                                   |
| ---------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Entity Type**        | A class of objects in the system. Can be system-defined (Contact, Conversation, Communication, Project, Topic) or user-defined (via the Custom Objects system). Each entity type has a field registry and a type-prefixed ID convention (e.g., `con_` for Contacts).                         |
| **Field**              | A named, typed attribute of an entity type. Fields have a data type (text, number, date, select, relation, formula, etc.) that determines how they are displayed, edited, filtered, and sorted. Fields are either system-defined (core, locked) or user-defined (custom, added by the user). |
| **Field Registry**     | The complete set of fields available for an entity type. The view system reads from this registry to know what columns can be displayed, what filter operators apply, and what editors to render. Defined by the Custom Objects PRD.                                                         |
| **Data Source**        | A reusable, named query definition — built via visual query builder or raw SQL — that produces a structured result set. Defines the entities involved (FROM + JOINs), available columns, default filters, default sort, and previewable entities. Multiple views can share one data source.  |
| **Column Registry**    | The schema of a data source's result set. Lists every column with its name, data type, source entity, source field, editability, and aggregation context. The contract between the data source and the views that consume it.                                                                |
| **View**               | A named, saved configuration that defines how to render the results of a data source. Includes: view type, visible columns (with order, width, pinning), additional filter conditions, sort overrides, and group-by configuration. Each view references exactly one data source.             |
| **View Type**          | The rendering strategy for a view: List/Grid (tabular rows and columns), Board/Kanban (cards in status columns), Calendar (records plotted on a date grid), or Timeline (records as horizontal bars across a time axis).                                                                     |
| **Column**             | A single vertical data display slot in a List/Grid view. Maps to a field (either on the primary entity or on a related entity via relation traversal). Has configuration: width, position, pinned state, and sort direction.                                                                 |
| **Relation Traversal** | The ability of a column to display a field from a related entity by following a relation field. Example: a Conversation has a relation field "Primary Contact" pointing to a Contact entity; a column can traverse this relation to display "Primary Contact → Company Name".                |
| **Filter Condition**   | A single predicate applied to a field: `field` `operator` `value`. Example: `Status equals Active`.                                                                                                                                                                                          |
| **Filter Group**       | A set of filter conditions combined with AND or OR logic. Filter groups can be nested for compound expressions.                                                                                                                                                                              |
| **Sort Rule**          | A field + direction (ascending/descending) pair. Multiple sort rules create a multi-level sort.                                                                                                                                                                                              |
| **Group-By**           | A field used to partition rows into collapsible visual sections. Rows with the same value in the group-by field are clustered together under a group header.                                                                                                                                 |
| **Aggregation**        | A summary computation displayed on a group header or view footer: COUNT, SUM, AVG, MIN, MAX applied to a numeric or date column within a group.                                                                                                                                              |
| **Default View**       | A system-generated view provided for every entity type when no user views exist. Uses sensible default columns, no filters, sorted by creation date descending.                                                                                                                              |

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

### 6.1 Overview & Purpose

A **Data Source** is a reusable, named query definition that produces a structured result set for one or more views to render. It is the "what data" layer of the system — separate from the "how to render it" layer (the View).

**Why Data Sources exist as a separate concept from Views:**

Traditional CRM views tightly couple "what data to fetch" with "how to display it." This creates a fundamental limitation: if a user wants to see the same dataset as a List/Grid, a Board, and a Calendar, they must define the query three times — once per view. If the query changes (e.g., adding a new JOIN or filter), all three views must be updated independently.

By separating the Data Source from the View, CRMExtender achieves:

- **Reusability** — A single well-crafted query powers multiple views. A "Deal Pipeline" data source can be rendered simultaneously as a Board (grouped by stage), a List (sorted by value), and a Calendar (plotted by close date). Change the data source once, all three views reflect the update.
- **Separation of concerns** — Data source authors focus on *what data to fetch* (entities, joins, columns, base filters). View authors focus on *how to present it* (view type, visible columns, grouping, card layout). Different skills, different workflows.
- **Cross-entity queries** — A data source can JOIN across entity types (Conversations + Contacts + Companies), producing a denormalized result set that no single-entity view could achieve. This is the key to answering questions like "show me all conversations with their contact's company and industry."
- **Dual authoring modes** — The visual query builder serves most users; raw SQL serves power users and analysts. Both produce the same Data Source artifact.
- **Governance** — In a team context, a data-savvy user creates a well-optimized data source. Other team members create views on top of it without needing to understand the query. The data source is the single source of truth.

### 6.2 Universal Entity ID Convention

Before defining the data source model, this section establishes a foundational architectural decision that affects the entire CRMExtender platform: **every entity ID in the system uses a type prefix**.

#### The Convention

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

#### Prefix Registry

System entity type prefixes are reserved and immutable:

| Entity Type   | Prefix | Example ID         |
| ------------- | ------ | ------------------ |
| Contact       | `con_` | `con_8f3a2b91c4d7` |
| Conversation  | `cvr_` | `cvr_91bc4de6f823` |
| Communication | `com_` | `com_47de6f9a2b15` |
| Project       | `prj_` | `prj_23ab8c55fg7h` |
| Topic         | `top_` | `top_bb91c4d78f3a` |
| Segment       | `seg_` | `seg_12de6f47ab9c` |
| Company       | `cmp_` | `cmp_55fg7h23ab8c` |
| User          | `usr_` | `usr_7h23ab8c55fg` |
| Data Source   | `dts_` | `dts_9a2b1547de6f` |
| View          | `viw_` | `viw_6f9a2b1547de` |

**Custom entity type prefixes** are auto-generated when a user creates a custom entity type. The system generates a unique 3-4 character prefix derived from the entity name, checking for collisions against all existing prefixes (system and user-defined):

```
User creates "Jobs" entity → prefix: job_
User creates "Properties" entity → prefix: prop_
User creates "Service Agreements" entity → prefix: svca_
```

If the natural abbreviation collides with an existing prefix, the system appends or modifies characters until unique. The prefix is immutable once assigned — renaming the entity type does not change the prefix.

#### Rationale

This convention provides four critical capabilities:

**1. Automatic entity detection in data source results.** When a data source query returns result rows, the system can scan any column's values and immediately determine which entity type it references — without any metadata declaration. A column containing `con_8f3a2b91c4d7` is unambiguously a Contact reference.

**2. System-wide type safety.** Any component in the system that receives an entity ID can determine its type without additional context. API endpoints can accept any entity ID and route to the correct handler. Log entries containing entity IDs are self-documenting. Error messages referencing an entity ID immediately communicate what kind of entity is involved.

**3. Cross-entity collision avoidance.** Even though each entity type's IDs are stored in separate database tables, the prefix ensures that no two entities anywhere in the system — regardless of type — share the same ID string. This is critical for data source result sets that combine IDs from multiple entity types in a single row.

**4. Preview and navigation resolution.** The view system can examine any cell value in a data source result set and determine whether it's an entity reference, what type of entity it is, and therefore whether it can be previewed, linked, or navigated to. This powers the multi-entity preview system (Section 6.7) without requiring per-data-source configuration in the common case.

#### External ID Mapping

External system IDs (Gmail `threadId`, Outlook `conversationId`, Twilio message SIDs, etc.) are stored as metadata on the entity record but are never used as the entity's primary ID. The mapping is:

```
Entity: Communication (com_47de6f9a2b15)
  └── External IDs:
        ├── gmail_thread_id: "18d5a3b2c4e6f7"
        ├── gmail_message_id: "msg-a1b2c3d4e5f6"
        └── provider: "gmail"
```

This ensures that all internal references, queries, and data source results use prefixed IDs consistently, regardless of the original source.

#### ID Generation

The unique portion of the ID (after the prefix) is generated using a **ULID** (Universally Unique Lexicographically Sortable Identifier) algorithm, which provides:

- Global uniqueness without coordination
- Lexicographic sortability (IDs generated later sort after earlier ones, which is useful for cursor-based pagination)
- 128-bit randomness (collision probability is negligible)
- URL-safe characters (no encoding needed in API paths)

### 6.3 Data Source Definition Model

A Data Source is a first-class entity in the system with the following attributes:

| Attribute                 | Description                                                                                                            |
| ------------------------- | ---------------------------------------------------------------------------------------------------------------------- |
| **ID**                    | Prefixed unique identifier (`dts_...`)                                                                                 |
| **Name**                  | User-defined name (e.g., "Deal Pipeline", "Contact Activity Report")                                                   |
| **Description**           | Optional description of what this data source provides and when to use it                                              |
| **Owner**                 | The user who created the data source                                                                                   |
| **Visibility**            | `personal` (only owner) or `shared` (available to team/workspace)                                                      |
| **Query mode**            | `visual` (built via visual query builder) or `sql` (raw SQL)                                                           |
| **Query definition**      | The query itself — either a visual builder configuration object or a raw SQL string                                    |
| **Column registry**       | The result set schema: column names, data types, source entity/field mappings, editability flags                       |
| **Preview configuration** | Auto-detected previewable entities + optional manual overrides (priority, exclusions)                                  |
| **Default filters**       | Base filter conditions applied before any view-level overrides                                                         |
| **Default sort**          | Base sort order applied when a view doesn't specify its own                                                            |
| **Parameters**            | Optional named parameters that can be supplied at query time (e.g., `{current_user}`, `{date_range_start}`)            |
| **Refresh policy**        | How the result set is refreshed: `live` (re-execute on every load), `cached` (TTL-based), or `manual` (user-triggered) |
| **Created / Updated**     | Timestamps                                                                                                             |
| **Version**               | Schema version counter, incremented when column registry changes (used to detect breaking changes for dependent views) |

### 6.4 Query Definition: Visual Builder

The visual query builder allows users to construct data source queries without writing SQL. It translates user selections into a structured query configuration that the query engine executes.

#### Builder Components

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

| Setting              | Options                                                                                     | Default                          |
| -------------------- | ------------------------------------------------------------------------------------------- | -------------------------------- |
| **Join type**        | Inner (only rows with matches) or Left (include rows without matches)                       | Left                             |
| **Relation field**   | The relation field used to connect the entities                                             | Required                         |
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

#### Visual Builder ↔ SQL Equivalence

Every visual builder configuration has an exact SQL equivalent. The system can display the generated SQL for any visual builder query (read-only, for transparency and debugging). Advanced users who outgrow the visual builder can "eject" to raw SQL mode, which copies the generated SQL into the raw SQL editor for further customization. This is a **one-way operation** — once ejected, the data source cannot be converted back to visual builder mode because raw SQL can express constructs the visual builder cannot represent.

### 6.5 Query Definition: Raw SQL

Power users and analysts can write raw SQL queries directly. Raw SQL provides capabilities that the visual builder cannot express:

- Subqueries and CTEs (Common Table Expressions)
- UNION / INTERSECT / EXCEPT set operations
- Window functions (ROW_NUMBER, RANK, LAG, LEAD)
- Complex aggregations with HAVING clauses
- Conditional expressions (CASE WHEN)
- Custom column aliases with transformations
- Self-joins (an entity joined to itself)

#### SQL Environment

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

#### Virtual Schema Access Rules

| Rule                   | Detail                                                                                                                                                                                          | Rationale                                                                                                                                               |
| ---------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **SELECT only**        | INSERT, UPDATE, DELETE, DDL statements are rejected at parse time                                                                                                                               | Data sources are read-only query definitions. Write operations happen through inline editing (Section 6.10), which uses the entity API, not direct SQL. |
| **Tenant-scoped**      | All queries are implicitly filtered to the current user's tenant. The `WHERE tenant_id = ?` clause is injected by the query engine and cannot be overridden.                                    | Data isolation is non-negotiable.                                                                                                                       |
| **Row-level security** | Queries respect the user's data access permissions. Records the user cannot access are filtered out even if the SQL would otherwise return them.                                                | A shared data source must not leak data to users who lack permission.                                                                                   |
| **Entity-type access** | Users can only query entity types they have read access to. Attempting to SELECT from an entity type the user cannot access results in a permission error.                                      | Prevents data source authors from exposing restricted entity types.                                                                                     |
| **Execution timeout**  | Queries are terminated after a configurable timeout (default: 30 seconds).                                                                                                                      | Prevents runaway queries from consuming resources.                                                                                                      |
| **Result set limit**   | Queries return a maximum of 10,000 rows (before view-level pagination). Data sources expected to exceed this should use appropriate WHERE clauses or the query engine's pagination integration. | Memory and performance guardrails.                                                                                                                      |

#### SQL Validation

When a user saves a raw SQL data source, the system:

1. **Parses** the SQL to verify syntax and detect forbidden operations (INSERT, UPDATE, DELETE, DDL).
2. **Resolves** table and column references against the virtual schema. Unknown table/column names produce clear error messages: "Entity type 'dealz' not found. Did you mean 'deals'?"
3. **Type-checks** column expressions to infer result column types (needed for the column registry).
4. **Dry-runs** the query with a `LIMIT 0` to verify it executes without error.
5. **Extracts** the column registry (column names, inferred types, source entity mappings) from the query plan.

Validation errors are displayed inline in the SQL editor with line/column references.

#### SQL Parameters

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

| Parameter                                | Resolution                                                                         |
| ---------------------------------------- | ---------------------------------------------------------------------------------- |
| `{current_user_id}`                      | The ID of the user executing the query                                             |
| `{current_date}`                         | Today's date                                                                       |
| `{current_timestamp}`                    | Current timestamp                                                                  |
| `{date_range_start}`, `{date_range_end}` | User-supplied via a date range picker in the view UI                               |
| Custom parameters                        | Defined by the data source author, supplied via the view UI or alert configuration |

Parameters use curly-brace syntax and are resolved via parameterized queries (never string interpolation) to prevent SQL injection.

### 6.6 Column Registry

Every data source has a **column registry** — the schema of its result set. The column registry is the contract between the data source and the views that consume it. Views read the column registry to know what columns are available, what types they are, and how to render and edit them.

#### Column Registry Entry

Each column in the result set has the following metadata:

| Attribute               | Description                                                                                                                          | Source                                                                               |
| ----------------------- | ------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------ |
| **Column name**         | The name of the column in the result set (e.g., `contact_name`, `conversation_count`)                                                | From SQL alias or visual builder field selection                                     |
| **Display label**       | Human-readable label (e.g., "Contact Name", "Conversation Count")                                                                    | Auto-generated from column name, overridable by author                               |
| **Data type**           | The field type: text, number, currency, date, datetime, select, checkbox, email, phone, url, etc.                                    | Inferred from source field type (visual builder) or from SQL type-checking (raw SQL) |
| **Source entity**       | Which entity type this column originates from (e.g., `Contact`, `Company`, `null` for computed columns)                              | Auto-detected from query structure                                                   |
| **Source field**        | Which field on the source entity this column maps to (e.g., `name`, `industry`, `null` for computed)                                 | Auto-detected from query structure                                                   |
| **Entity ID column**    | Which column in the result set contains the ID of this column's source entity (e.g., `contact_id` for a column sourced from Contact) | Auto-detected from JOIN structure                                                    |
| **Editable**            | Whether this column supports inline editing (see Section 6.10)                                                                       | Derived from editability rules                                                       |
| **Hidden**              | Whether this column is hidden by default in views (e.g., auto-included ID columns)                                                   | Auto-set for ID columns; manual for others                                           |
| **Aggregation context** | Whether this column is an aggregate (COUNT, SUM, etc.) — affects preview detection and editability                                   | Inferred from SQL or visual builder config                                           |

#### Automatic Column Registry Generation

**Visual builder:** The column registry is generated directly from the field selections. Each selected field has a known entity, field name, and data type from the object model's field registry. The mapping is unambiguous.

**Raw SQL:** The column registry is inferred from the query plan:

1. **Direct column references** (`ct.name`, `cvr.ai_status`) — the system traces the column back to its source entity and field through the FROM/JOIN structure. Entity, field, and data type are all known.
2. **Aliased columns** (`ct.name AS contact_name`) — same tracing, with the alias used as the column name.
3. **Computed expressions** (`COUNT(cvr.id) AS conversation_count`) — the system recognizes the aggregate function, infers the output type (number for COUNT/SUM, same type for MIN/MAX), and marks the column as non-editable and aggregated. Source entity is set to `null`.
4. **CASE expressions** (`CASE WHEN ... THEN 'High' ELSE 'Low' END AS priority_label`) — the system infers the output type from the THEN/ELSE values. Source entity is `null` (computed).
5. **Unresolvable columns** — if the system cannot infer a column's source entity or data type (e.g., complex nested subqueries), it defaults to `text` type, `null` source entity, and non-editable. The author can manually override these in the column registry editor.

#### Manual Registry Overrides

After automatic generation, the data source author can manually override any column registry entry:

- Change the display label
- Correct or specify the data type (e.g., override `text` to `currency` for a formatted column)
- Mark a column as hidden or visible by default
- Override editability (e.g., force a column to read-only even if it would otherwise be editable)
- Specify the source entity and field for computed columns that the system couldn't resolve

These overrides are stored as part of the data source definition and survive query modifications (unless the column is removed from the query entirely).

### 6.7 Entity Detection & Preview System

The preview system determines which entities a data source result row can navigate to. It uses a three-layer approach: automatic detection, automatic inference rules, and optional manual declaration.

#### Layer 1: Automatic Detection via Prefixed IDs

The system scans all columns in the data source's column registry. Any column whose values contain prefixed entity IDs is registered as a potential **entity reference column**:

```
Result row:
  conversation_id: cvr_91bc4de6f823    ← Entity reference: Conversation
  contact_name: "Alice Smith"           ← Not an entity reference (text)
  contact_id: con_8f3a2b91c4d7         ← Entity reference: Contact
  company_id: cmp_55fg7h23ab8c         ← Entity reference: Company
  open_conversations: 5                 ← Not an entity reference (number)
```

Detection mechanism: During column registry generation (Section 6.6), the system identifies columns whose source field is an entity ID field (type = `id` or `relation`). For raw SQL, a dry-run query fetches a sample row and checks column values against the prefix registry.

#### Layer 2: Automatic Inference Rules

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

#### Layer 3: Optional Manual Declaration (Override)

For the majority of data sources, Layers 1 and 2 produce correct preview behavior with zero configuration. The manual declaration layer exists for cases where the automatic inference is wrong or insufficient.

The data source author can open the **Preview Configuration** panel and:

| Override                      | Effect                                                                                   | Use Case                                                                                                 |
| ----------------------------- | ---------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------- |
| **Reorder priorities**        | Change which entity previews on primary click vs. secondary access                       | A "Company Report" data source where the Contact JOIN is first but Company should be the primary preview |
| **Exclude an entity**         | Remove an entity from the previewable set                                                | A query returns a `tag_id` column for filtering purposes, but Tag preview is meaningless                 |
| **Include a computed entity** | Manually declare that a computed column maps to a previewable entity                     | A subquery returns an entity ID in a column the system couldn't auto-detect                              |
| **Set labels**                | Override the display name used in the preview UI (e.g., "Billing Contact" vs. "Contact") | Multiple joins to the same entity type, or joins with aliases that differ from the entity name           |

**Override persistence:** Manual overrides are stored in the data source's `preview_configuration` attribute. They take precedence over automatic detection — if the author excludes an entity, it stays excluded even if the query is modified to add more references to that entity type.

**Override invalidation:** If the data source query is modified such that a declared preview entity is no longer present in the result set (the ID column is removed), the system warns the author: "Preview entity 'Company' references column 'company_id' which is no longer in the result set. Remove this preview declaration or update the column reference."

### 6.8 Preview Resolution at Runtime

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
  │     → Opens detail panel for this Conversation
  │
  └── Secondary previews (available via UI affordance):
        ├── Contact: con_8f3a2b91c4d7 → "Alice Smith"
        └── Company: cmp_55fg7h23ab8c → "Acme Corp"
```

**Null handling:** If a row has a null value for an entity ID (e.g., the Contact has no Company), that entity is omitted from the previewable set for that specific row. The preview UI dynamically adjusts per row.

**Permission handling:** If the current user doesn't have read access to a particular entity record, that preview option is hidden for that row. The data source result may include the ID, but the preview system respects access controls.

### 6.9 Data Source ↔ View Relationship

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

#### How View-Level Overrides Compose with Data Source Defaults

| Aspect                    | Data Source Defines                                          | View Can Do                                                                                                                                                                      |
| ------------------------- | ------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Available columns**     | The complete column registry (all columns the query returns) | Choose which columns to display, their order, width, and pinning. Cannot add columns not in the data source.                                                                     |
| **Default filters**       | Base filter conditions that scope the data source            | Add additional filter conditions (AND'd with data source filters). Cannot remove or negate data source filters.                                                                  |
| **Default sort**          | Base sort order                                              | Override with a different sort order, or accept the data source default if no sort is specified.                                                                                 |
| **Parameters**            | Named parameters with optional default values                | Supply parameter values (e.g., a date range picker in the view's header). If a parameter has no default and the view doesn't supply a value, the query fails with a clear error. |
| **Preview configuration** | Previewable entities with priority                           | Accept the data source's preview configuration as-is. Views do not override preview config.                                                                                      |

**Why views cannot remove data source filters:** The data source's filters define the data source's **scope** — the universe of data it operates on. A "Last 90 Days Active Conversations" data source should always return data from the last 90 days, regardless of how views render it. If a view could remove this filter, it would change the data source's fundamental meaning. If a user needs unfiltered data, they should create or use a different data source.

**Why views cannot add columns:** The data source's column registry is the contract. Views select from what's available. If a user needs a column that doesn't exist in the data source, they modify the data source (or create a new one). This preserves the data source as the single definition of "what data is available" and prevents views from independently making expensive query modifications.

### 6.10 Inline Editing Trace-Back

When a user edits a cell value inline in a view, the system must trace the edit back to the source entity and field to persist the change. The column registry provides this mapping.

#### Editability Rules

A column is editable inline if and only if ALL of the following conditions are met:

| Condition                                                    | Rationale                                                                                                                                                                                           |
| ------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Source entity is identified**                              | The column registry maps this column to a specific entity type and field. Computed columns (`source_entity = null`) cannot be edited.                                                               |
| **Source field is a direct field** (not a formula or rollup) | Formula and rollup fields are derived values — editing them is meaningless.                                                                                                                         |
| **The field type supports inline editing**                   | Multi-line text, for example, opens a popup rather than editing in the cell. Some field types (like auto-generated timestamps) are inherently read-only.                                            |
| **The entity ID column is present in the result set**        | The system needs the entity's ID to issue an update API call. If the data source doesn't include the source entity's ID column, the edit has no target. (This is why ID columns are auto-included.) |
| **The user has write permission on the entity record**       | Row-level security applies — the user must be able to edit this specific record of this entity type.                                                                                                |
| **The data source author hasn't forced read-only**           | The author can override editability in the column registry to prevent edits on specific columns.                                                                                                    |
| **The column is not aggregated**                             | Aggregated values (COUNT, SUM, etc.) represent multiple records and cannot be edited.                                                                                                               |

#### Edit Trace-Back Flow

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

**Cascade visibility:** If editing a Company's name in one row, other rows in the same view that reference the same Company will show the old name until the view is refreshed or the query cache expires. Real-time propagation of cross-row changes is addressed in the Performance section (cache invalidation).

### 6.11 Data Source Lifecycle & Versioning

#### Lifecycle Operations

| Operation           | Behavior                                                                                                                                                                                         |
| ------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Create**          | User creates a data source via visual builder or raw SQL editor. System generates column registry, validates query, detects preview entities.                                                    |
| **Edit**            | Author modifies the query. System re-generates column registry, validates, re-detects previews. If column registry changes (columns added/removed/type changed), the version counter increments. |
| **Duplicate**       | Creates a copy of the data source with a new ID. Useful for creating variations of a common query.                                                                                               |
| **Delete**          | Removes the data source. All views referencing this data source are orphaned and display a "Data source deleted" error until the user selects a new data source or deletes the view.             |
| **Share / Unshare** | Toggle visibility from personal to shared or back. Sharing follows the same model as shared views (Section 17).                                                                                  |

#### Schema Versioning

The data source maintains a **version counter** that increments whenever the column registry changes in a way that could break dependent views:

| Change Type                  | Version Increment? | Impact on Views                                                                                                                                                                     |
| ---------------------------- | ------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Column added                 | No                 | Views don't show new columns by default; no breakage                                                                                                                                |
| Column removed               | **Yes**            | Views referencing the removed column show a "Column unavailable" indicator. The column configuration is preserved (in case the column is re-added) but the column renders as empty. |
| Column type changed          | **Yes**            | Views may have incompatible filters or sorts on the changed column. The system warns and disables affected filters/sorts.                                                           |
| Column renamed               | **Yes**            | Views reference columns by name. A rename is functionally a remove + add.                                                                                                           |
| Filter/sort defaults changed | No                 | Views that override the defaults are unaffected. Views using the defaults see the new behavior.                                                                                     |

When a breaking version change occurs, the system:

1. Identifies all views referencing this data source.
2. Checks each view for references to changed/removed columns.
3. Flags affected views with a "data source schema changed" warning visible to the view owner.
4. Does **not** automatically modify the view — the view owner must review and adjust.

### 6.12 Data Source Permissions & Security

#### Access Control

| Actor                                  | Can Do                                                                                                                                       |
| -------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------- |
| **Owner**                              | Full CRUD on the data source. Edit query, modify column registry, manage preview config, share/unshare.                                      |
| **Team member (shared data source)**   | Read the data source definition. Create views referencing it. Cannot edit the data source itself. Can duplicate it to create their own copy. |
| **Team member (personal data source)** | Cannot see or access the data source.                                                                                                        |

#### Row-Level Security

Data source queries always execute within the requesting user's security context:

- Tenant isolation is enforced at the query engine level.
- Row-level access controls filter results before they reach the view.
- A shared data source may return different result sets for different users based on their data permissions.

**This means sharing a data source is safe** — the query definition is shared, not the data. User A and User B can use the same "All Conversations" data source, but User A sees only their conversations while User B sees only theirs (unless broader permissions apply).

#### SQL Injection Prevention

Raw SQL queries are parameterized. User-supplied values (parameters, filter values from views) are never interpolated into the SQL string. The query engine uses prepared statements with bound parameters for all dynamic values.

The virtual schema layer adds a second line of defense: raw SQL operates against a logical schema, not the physical database. Even if a malicious query were somehow injected, it could not reference physical tables, system catalogs, or cross-tenant data.

### 6.13 Data Source Examples

The following examples illustrate the range of data sources from simple to complex, demonstrating how the architecture handles each case.

#### Example 1: Simple Single-Entity Data Source

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

#### Example 2: Multi-Entity Join with Relation Traversal

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

#### Example 3: Aggregated Report Data Source (Raw SQL)

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

#### Example 4: Complex Raw SQL with CTE and Window Functions

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

#### Example 5: Data Source with Parameters

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

### 6.14 System-Generated Data Sources

For each entity type in the system (both system-defined and user-created custom entities), the system automatically generates a **default data source** that provides simple, unfiltered access to all records of that entity type.

```
Auto-generated Data Source: "All Contacts"
  Query: SELECT * FROM contacts
  Columns: All fields on the Contact entity
  Default Filter: none
  Default Sort: created_at DESC
  Preview: Contact (only entity, auto-primary)
```

These system-generated data sources serve as the default data source for the system default views (Section 17.3). They ensure that every entity type is immediately viewable without requiring the user to create a data source first.

**Properties of system-generated data sources:**

- Cannot be deleted or modified by users (but can be duplicated to create a custom variation).
- Automatically updated when fields are added to or removed from the entity type.
- Named with the pattern "All {Entity Type Plural}" (e.g., "All Contacts", "All Conversations", "All Jobs").
- One per entity type per user (custom entity) or per tenant (system entity).

### 6.15 Data Source Performance Considerations

| Concern                                | Mitigation                                                                                                                                                                                                                                                                                                       |
| -------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Complex JOINs across many entities** | The query engine analyzes JOIN complexity before execution. Queries with >5 JOINs display a performance warning to the author. The execution timeout (30s) prevents runaway queries.                                                                                                                             |
| **Large result sets**                  | The 10,000-row result set limit prevents memory exhaustion. View-level pagination further limits what's loaded into the client. Data sources returning >5,000 rows display a recommendation to add filters.                                                                                                      |
| **Expensive aggregations**             | Aggregation queries (GROUP BY with COUNT/SUM/etc.) are executed server-side. The query engine uses appropriate indexes. For very large base tables, the system may use approximate aggregations (e.g., HyperLogLog for distinct counts) with a "approximate" indicator.                                          |
| **Cached vs. live execution**          | The refresh policy (`live`, `cached`, `manual`) controls re-execution frequency. `Cached` data sources store the result set with a configurable TTL (default: 60 seconds). `Manual` data sources re-execute only when the user clicks a refresh button. `Live` re-executes on every view load and filter change. |
| **Concurrent view loads**              | When multiple views reference the same data source and are loaded simultaneously (e.g., a dashboard with four views on the same data source), the query engine deduplicates the query — it executes once and distributes the result set to all requesting views.                                                 |
| **Parameter variation**                | Views with different parameter values cannot share cached results. Each unique parameter combination is a separate cache entry.                                                                                                                                                                                  |

---

## 7. View Types

### 7.1 List / Grid View

The primary and most versatile view type. Displays records as rows in a tabular grid with configurable columns.

| Aspect                     | Detail                                                              |
| -------------------------- | ------------------------------------------------------------------- |
| **Rendering**              | Tabular: rows = records, columns = fields                           |
| **Required entity fields** | None — any entity type can be displayed in a grid                   |
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
| **Sorting**                | N/A — position is determined by date field value                                                                        |
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

| Property           | Description                                                                         | Default                                    |
| ------------------ | ----------------------------------------------------------------------------------- | ------------------------------------------ |
| **Field mapping**  | Which field (or relation→field) this column displays                                | Set at column creation                     |
| **Position**       | Left-to-right order in the grid                                                     | Append to end                              |
| **Width**          | Pixel width of the column                                                           | Auto-sized based on field type (see below) |
| **Pinned**         | Whether the column is pinned to the left and stays visible during horizontal scroll | First column pinned by default             |
| **Visible**        | Whether the column is rendered (allows hiding without removing)                     | True                                       |
| **Sort direction** | If this column is part of the active sort: ASC, DESC, or none                       | None                                       |
| **Label override** | Optional display name that overrides the field's default label                      | Field's default label                      |

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

### 8.4 Column Operations

| Operation         | Behavior                                                                                                                    |
| ----------------- | --------------------------------------------------------------------------------------------------------------------------- |
| **Add column**    | Opens a field picker showing all available fields (direct + relation traversal). Adds the column to the rightmost position. |
| **Remove column** | Removes the column from the view. Does not delete the field from the entity.                                                |
| **Reorder**       | Drag-and-drop column headers to change position.                                                                            |
| **Resize**        | Drag the right edge of a column header to adjust width. Double-click to auto-fit content.                                   |
| **Pin/Unpin**     | Toggle column pinning via column header context menu. Pinned columns move to the leftmost positions.                        |
| **Hide/Show**     | Toggle visibility without removing the column from the view configuration.                                                  |
| **Sort**          | Click column header to toggle sort (none → ASC → DESC → none). Shift+click to add as secondary sort.                        |
| **Rename**        | Set a label override via column header context menu.                                                                        |

---

## 9. Field Type Registry

The view system renders columns, filters, and editors based on field types. Each field type defines its display renderer, edit widget, and applicable filter operators. The field types themselves are defined by the Custom Objects PRD — this section specifies how the view system handles each type.

### 9.1 Field Types and View Behavior

| Field Type             | Display Renderer                                             | Inline Editor                         | Supports Sort?                          | Supports Group-By?                                                |
| ---------------------- | ------------------------------------------------------------ | ------------------------------------- | --------------------------------------- | ----------------------------------------------------------------- |
| **Text (single-line)** | Plain text, truncated with ellipsis                          | Text input                            | Yes (alphabetical)                      | Yes                                                               |
| **Text (multi-line)**  | First line + "..." indicator                                 | Expandable textarea (opens in popup)  | Yes (alphabetical)                      | No — too many unique values                                       |
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
| **Formula**            | Computed value (renders based on output type)                | Read-only — not editable              | Yes (based on output type)              | Yes (based on output type)                                        |
| **Rollup**             | Aggregated value from related records                        | Read-only — not editable              | Yes (numeric)                           | Yes                                                               |
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
| `is_within_last N weeks`  | Today minus N×7 days through today      |
| `is_within_last N months` | Today minus N months through today      |
| `is_within_next N days`   | Today through today plus N days         |
| `is_within_next N weeks`  | Today through today plus N×7 days       |
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
| **Depth limit**    | One hop in Phase 1 (A → B). Multi-hop (A → B → C) deferred to Phase 2.                                                                                                                                                             |
| **Editability**    | Lookup columns are read-only. The value belongs to the related entity. To edit, the user must open the related entity.                                                                                                             |
| **Null handling**  | If the relation field is empty (no related entity), the lookup column displays "—" (em-dash).                                                                                                                                      |
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

| Component    | Description                                                  | Example                                |
| ------------ | ------------------------------------------------------------ | -------------------------------------- |
| **Field**    | The field to filter on (direct or relation traversal)        | `ai_status`, `primary_contact→company` |
| **Operator** | The comparison operator (from the field type's operator set) | `equals`, `contains`, `is_after`       |
| **Value**    | The comparison value (type matches the field)                | `"Open"`, `"Acme"`, `"2026-01-01"`     |

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

| Aggregation   | Applies To                         | Display           |
| ------------- | ---------------------------------- | ----------------- |
| **Count**     | Any field (counts non-null values) | "3 conversations" |
| **Sum**       | Number, Currency fields            | "$45,000"         |
| **Average**   | Number, Currency fields            | "Avg: $15,000"    |
| **Min / Max** | Number, Currency, Date fields      | "Earliest: Feb 8" |
| **Range**     | Date fields                        | "Feb 8 – Feb 15"  |

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
| **Page size**    | 50 records (default) — configurable: 25, 50, 100                                                           |
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

| PRD                                               | Relationship                                                                                                                                                                                                                                                                                                                 | Dependency Direction                                                                                                                                                                          |
| ------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Custom Objects PRD**                            | Defines the entity types, field registry, field types, and relation model that data sources query and views render. The prefixed entity ID convention (Section 6.2) must be adopted as a platform-wide standard in this PRD. Select field transition confirmation rules (Section 15.4) are defined on the field in this PRD. | **Bidirectional.** View/Data Source system depends on Object Model for field registry and entity definitions. Object Model must adopt prefixed IDs and transition confirmation configuration. |
| **Communication & Conversation Intelligence PRD** | Defines system entities (Conversations, Communications, Projects, Topics, Contacts) that are the primary entities queried by data sources. Also defines the alert system architecture that views feed into.                                                                                                                  | **Bidirectional.** Data sources query Conversation entities; Conversations PRD's alert system consumes view filter definitions.                                                               |
| **Contact Intelligence PRD**                      | Defines the Contact entity and identity resolution system. Contact-related data sources and views depend on this. Cross-entity data sources frequently JOIN to the Contact entity.                                                                                                                                           | **View/Data Source system depends on Contact model** for Contact entity fields and relation resolution.                                                                                       |
| **Permissions & Sharing PRD**                     | Defines data access controls that determine which records a user can see in data source results. Row-level security in the query engine (Section 6.12) depends on this. Shared data source and view visibility is governed by these permissions.                                                                             | **View/Data Source system depends on Permissions** for row-level security, data filtering, and shared access control.                                                                         |
| **AI Learning & Classification PRD**              | AI-generated fields (AI Status, AI Summary, Action Items, Key Topics) are exposed as queryable fields in data sources and displayable columns in views. The AI system may also use view configurations as context for learning user preferences.                                                                             | **View system consumes AI fields** as queryable and displayable columns.                                                                                                                      |

---

## 22. Open Questions

1. **Multi-entity views vs. cross-entity data sources** — With Data Sources now supporting JOINs across entity types, the original "multi-entity view" question is partially addressed. A data source joining Conversations + Contacts + Companies produces a cross-entity result set. However, this is still a flattened/denormalized view. Should there also be a "unified activity feed" view type that displays heterogeneous entity types (a Conversation row, then a Communication row, then a Project row) in a single chronological stream? This would require a fundamentally different rendering model where each row can have a different column schema.

2. **Formula field computation** — Where are formula fields computed? Client-side (fast but limited to loaded records) or server-side (complete but adds query complexity)? Server-side is more correct but makes formulas dependent on the query engine's expression capabilities. With raw SQL data sources, users can compute formulas in the query itself (CASE expressions, window functions) — does this reduce the need for a separate formula field type?

3. **View templates** — Should the system provide pre-built view templates that include both a data source and a view configuration (e.g., a "Sales Pipeline" template that creates a cross-entity data source + Board view)? Could accelerate onboarding.

4. **Export formats** — Beyond CSV, should views support export to Excel (.xlsx), PDF, or direct integration with reporting tools? What about scheduled exports (e.g., "email me this view as a CSV every Monday")?

5. **Conditional formatting** — Should cells/rows support conditional formatting rules (e.g., "if AI Status = Open, highlight row in yellow", "if Days Since Last Activity > 30, make cell red")? This is powerful but adds significant UI complexity.

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

## 23. Glossary

| Term                                          | Definition                                                                                                                                                                                                                                         |
| --------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Data Source**                               | A reusable, named query definition that produces a structured result set for one or more views to render. Defines entities involved, available columns, default filters/sort, and previewable entities. Built via visual query builder or raw SQL. |
| **Column Registry**                           | The schema of a data source's result set. Lists every column with its name, data type, source entity, source field, and editability. The contract between the data source and the views that consume it.                                           |
| **Visual Query Builder**                      | A UI-based tool for constructing data source queries by selecting entities, joins, columns, and filters without writing SQL. Generates a structured query configuration that the query engine executes.                                            |
| **Virtual Schema**                            | The logical representation of entity types and fields that raw SQL queries execute against. Users never see the physical database schema — only entity types as tables and fields as columns.                                                      |
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
| **Swimlane**                                  | A horizontal lane in a Timeline or Board view, created by grouping records by a field value. In Board views, swimlanes create a matrix of group-by × status.                                                                                       |
| **Milestone**                                 | A point-in-time marker on a Timeline view, used for records with a single date field (no duration).                                                                                                                                                |
| **Card**                                      | A compact visual representation of a record, used in Calendar and Board views. Shows title and configurable summary fields.                                                                                                                        |
| **Date-window loading**                       | A data loading strategy for Calendar and Timeline views that fetches records within the visible time range plus a buffer.                                                                                                                          |
| **Fork-on-write**                             | The behavior where modifying a shared view creates a personal copy of the modifications without affecting the shared definition.                                                                                                                   |
| **Transition confirmation**                   | An optional dialog shown when dragging a Board card between columns, configurable per field transition. Prevents accidental status changes for significant transitions.                                                                            |
| **Column collapse**                           | In a Board view, reducing a Kanban column to a narrow bar showing only the name and count, useful for hiding completed stages.                                                                                                                     |

---

*This document is a living specification. As the Custom Objects PRD is developed and as implementation progresses, sections will be updated to reflect design decisions, scope adjustments, and lessons learned. The phasing roadmap will be synchronized with the Custom Objects PRD to ensure dependencies are resolved in the correct order.*
