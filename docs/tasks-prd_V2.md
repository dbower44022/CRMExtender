# Product Requirements Document: Tasks

## CRMExtender — Task Management, Dependencies, Recurrence & AI Action-Item Extraction

**Version:** 2.0
**Date:** 2026-02-18
**Status:** Draft — Fully reconciled with Custom Objects PRD
**Parent Document:** [CRMExtender PRD v1.1](PRD.md)

> **V2.0 (2026-02-22):**
> Terminology standardization pass: Mojibake encoding cleanup. Cross-PRD links updated to current versions (Custom Objects V2, Views & Grid V5, Contact Management V5, Conversations V4, Projects V3). "Activity timeline" reference updated to Activity Card. Master Glossary V3 cross-reference added to glossary section.
>
> **V1.0 (2026-02-18):**
> This document defines the Task system object type for CRMExtender. Tasks represent actionable items — follow-ups, to-dos, assignments, and deliverables — that drive CRM workflows forward. The design draws on patterns from ClickUp, Wrike, Asana, and Monday.com, adapted for CRM relationship intelligence.
>
> All content is reconciled with the [Custom Objects PRD](custom-objects-prd_v2.md) Unified Object Model:
> - Task is a **system object type** (`is_system = true`, prefix `tsk_`) in the unified framework. Core fields are protected from deletion; specialized behaviors (status category enforcement, subtask cascade, recurrence generation, AI action-item extraction, due date reminders, overdue detection) are registered per Custom Objects PRD Section 22.
> - Entity IDs use **prefixed ULIDs** (`tsk_` prefix, e.g., `tsk_01HX8A...`) per the platform-wide convention (Data Sources PRD, Custom Objects PRD Section 6).
> - Task-to-entity linking uses the **Universal Attachment Relation** pattern (`target = *`), enabling tasks to attach to any entity type — system or custom — without requiring individual relation type definitions per entity type. This reuses the pattern introduced by the Notes PRD.
> - Task assignees are modeled as a **system Relation Type**: Task→User (`task_user_participation`), with metadata fields for role (assignee, reviewer, watcher).
> - Task dependencies are modeled as a **self-referential many:many Relation Type**: Task→Task (`task_dependencies`), with metadata for dependency type (`blocked_by`).
> - Task hierarchy (subtasks) uses a **self-referential one:many** pattern via a `parent_task_id` FK column, supporting unlimited nesting depth.
> - Task status uses a **Select field with protected system options** mapped to **status categories** (`not_started`, `active`, `done`, `cancelled`). Users can add custom statuses and assign them to categories.
> - Task priority uses a **Select field with fixed system options** (`urgent`, `high`, `medium`, `low`, `none`) that cannot be extended by users.
> - Rich text description uses the **behavior-managed content** pattern from the Notes PRD: `description_json`, `description_html`, `description_text` stored as columns but not registered in the field registry.
> - Recurrence follows the **Events-aligned model**: `recurrence_type`, `recurrence_rule` (RRULE), and `recurring_task_id` FK linking generated instances back to the template.
> - The task store uses a **per-entity-type event table** (`tasks_events`) per Custom Objects PRD Section 19.
> - `tasks` is the dedicated **read model table** within the tenant schema, managed through the object type framework.
> - All SQL uses **PostgreSQL** syntax with `TIMESTAMPTZ` timestamps and schema-per-tenant isolation.

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Problem Statement](#2-problem-statement)
3. [Goals & Success Metrics](#3-goals--success-metrics)
4. [User Personas & Stories](#4-user-personas--stories)
5. [Task as System Object Type](#5-task-as-system-object-type)
6. [Data Model](#6-data-model)
7. [Status Model & Categories](#7-status-model--categories)
8. [Priority Model](#8-priority-model)
9. [Task Hierarchy (Subtasks)](#9-task-hierarchy-subtasks)
10. [Universal Attachment Relation](#10-universal-attachment-relation)
11. [Task Assignees](#11-task-assignees)
12. [Task Dependencies](#12-task-dependencies)
13. [Description Content Architecture](#13-description-content-architecture)
14. [Recurrence Model](#14-recurrence-model)
15. [Event Sourcing & Temporal History](#15-event-sourcing--temporal-history)
16. [Virtual Schema & Data Sources](#16-virtual-schema--data-sources)
17. [API Design](#17-api-design)
18. [Design Decisions](#18-design-decisions)
19. [Phasing & Roadmap](#19-phasing--roadmap)
20. [Dependencies & Related PRDs](#20-dependencies--related-prds)
21. [Open Questions](#21-open-questions)
22. [Future Work](#22-future-work)
23. [Glossary](#23-glossary)

---

## 1. Executive Summary

The Task subsystem is the **action management layer** of CRMExtender. While Communications capture what was said, Conversations organize threads, Events track meetings, and Notes store observations, Tasks answer **"What needs to be done, by whom, and by when?"** Tasks are the bridge between relationship intelligence and business execution — they translate insights from conversations and meetings into trackable, assignable, completable work items.

Unlike standalone task managers, CRMExtender tasks are deeply embedded in the CRM entity graph. A task can be attached to a Contact ("follow up with Jane about the proposal"), a Company ("prepare pitch deck for Acme Corp"), a custom Job entity ("schedule crew for 123 Oak St gutter cleaning"), or any combination of entities. Tasks spawned from AI action-item extraction automatically link back to the originating Conversation, preserving the full context chain from communication to action.

**Core principles:**

- **System object type** — Task is a system object type (`is_system = true`, prefix `tsk_`) in the Custom Objects unified framework. Core fields (title, status, priority, dates, durations) are registered in the field registry. Specialized behaviors (status enforcement, subtask cascade, recurrence, AI extraction, reminders, overdue detection) are registered per Custom Objects PRD Section 22. Users can extend Tasks with custom fields through the standard field registry.
- **Universal attachment** — Tasks attach to any entity type (system or custom) through the Universal Attachment Relation pattern. When Sam creates a "Properties" custom object type, tasks are immediately attachable to Property records without any additional configuration. A single task can be linked to multiple entities across different types.
- **Status categories** — Task statuses are user-extensible (add "QA Review", "Awaiting Client", etc.) but each status maps to a system category (`not_started`, `active`, `done`, `cancelled`). Categories drive system behavior: completion tracking, subtask cascade warnings, recurrence triggers, and "show all open tasks" filters.
- **Multiple assignees** — Tasks support multiple participants through a Task→User relation type with role metadata (assignee, reviewer, watcher). This accommodates collaborative work while preserving clear accountability through role differentiation.
- **Unlimited subtask hierarchy** — Tasks can have subtasks via a self-referential `parent_task_id` FK, with unlimited nesting depth. Parent tasks can roll up completion percentages and duration estimates from children.
- **Simple blocking dependencies** — Tasks can declare `blocked_by` / `blocks` relationships through a self-referential many:many relation type, surfacing warnings when starting work on blocked tasks.
- **Recurrence** — Recurring tasks use the Events-aligned model (RRULE-based recurrence with instance generation on completion), enabling scheduled repetitive work like "monthly invoice review" or "quarterly client check-in."
- **AI action-item extraction** — The Conversations PRD's intelligence layer can auto-create tasks from extracted action items in communications, linking them back to the originating conversation.
- **Rich text descriptions** — Task descriptions use the behavior-managed content pattern from Notes (JSONB + HTML + plain text), supporting formatted instructions, checklists, embedded images, and @mentions.
- **Visible to all workspace members** — Tasks follow a workspace-visible model where any member can see any task, subject to standard role-based permissions. Filters and views handle scoping.

**Relationship to other PRDs:**

- **[Custom Objects PRD](custom-objects-prd_v2.md)** — The Task entity type is a system object type in the unified framework. Its table structure, field registry, event sourcing, and relation model are governed by the Custom Objects PRD. The Universal Attachment Relation pattern (introduced by the Notes PRD) is reused for task-to-entity linking. This PRD defines the Task-specific behaviors registered with the object type framework.
- **[Notes PRD](notes-prd_V3.md)** — Tasks reuse the Universal Attachment Relation pattern and the behavior-managed content architecture established by Notes. Notes can also attach to Tasks via Notes' own universal attachment, enabling commentary and context on task records.
- **[Projects PRD](projects-prd_V3.md)** — Tasks link to Projects through the Universal Attachment pattern. A project's task list provides the action-oriented complement to its conversation, event, and note associations.
- **[Contact Management PRD](contact-management-prd_V5.md)** — Tasks attach to Contacts for follow-up actions, outreach tracking, and relationship maintenance activities.
- **[Company Management PRD](company-management-prd_V1.md)** — Tasks attach to Companies for account-level actions.
- **[Conversations PRD](conversations-prd_V4.md)** — The AI action-item extraction behavior on Conversations can auto-create Tasks linked to the originating Conversation. Tasks also attach to Conversations manually for follow-up tracking.
- **[Event Management PRD](events-prd_V3.md)** — Tasks attach to Events for pre-meeting preparation and post-meeting follow-ups.
- **[Data Sources PRD](data-sources-prd_V1.md)** — The Task virtual schema table is derived from the Task object type's field registry. The `tsk_` prefix enables automatic entity detection in data source queries.
- **[Views & Grid PRD](views-grid-prd_V5.md)** — Task views support Grid, Board/Kanban (grouped by status), Calendar (by due date), and Timeline (start-to-due date bars). Inline editing, filtering, and sorting operate on fields from the Task field registry.
- **[Permissions & Sharing PRD](permissions-sharing-prd_V2.md)** — Task record access follows the standard workspace-visible role-based access model.

---

## 2. Problem Statement

CRM users constantly generate action items from their relationship activities: follow up after a meeting, send a proposal to a prospect, schedule a service crew, review an invoice, prepare for a pitch. Without integrated task management, these actions scatter across external tools (personal to-do lists, project management apps, sticky notes, email flags), creating several problems:

- **Broken context chains** — An action item noted during an email thread lives in a separate system from the email. When returning to the task, the user must manually re-find the conversation context.
- **No entity association** — External task tools don't know about CRM contacts, companies, or custom entities. "Follow up with Jane" in Todoist has no link to Jane's contact record, communication history, or engagement score.
- **Manual extraction** — AI conversation intelligence identifies action items in emails, but without an integrated task system, those extracted items have nowhere to land. Users must manually transcribe AI-identified action items into external tools.
- **Fragmented visibility** — Team members can't see each other's follow-up commitments within the CRM context. A manager reviewing a contact's detail page sees communications and notes but not the outstanding actions.
- **No recurrence** — Recurring relationship maintenance tasks ("quarterly check-in with top 20 clients") require manual recreation or external scheduling.

The Task subsystem embeds action management directly in the entity graph, maintaining context chains, enabling AI-driven extraction, providing team-wide visibility, and supporting recurrence for systematic relationship maintenance.

---

## 3. Goals & Success Metrics

| Goal | Metric | Target |
|---|---|---|
| Attach tasks to any entity | Tasks available on all system entity detail pages + all custom object detail pages | 100% entity type coverage |
| Status workflow flexibility | Users can define custom statuses mapped to system categories | Unlimited custom statuses per tenant |
| Subtask hierarchy | Parent tasks display child tasks with completion rollup | Unlimited nesting depth |
| Multiple assignees | Tasks support assignee, reviewer, and watcher roles | All three roles functional |
| Dependencies | Blocked-by relationships with visual warnings | Dependency warnings displayed |
| Rich descriptions | Formatted text with checklists, images, @mentions | Full rich text support |
| Recurrence | Tasks auto-generate next instance on completion | RRULE-based recurrence |
| AI extraction | Action items from conversations auto-create linked tasks | End-to-end pipeline functional |
| Cross-entity search | Tasks searchable by title and description content | <200ms for 95th percentile |
| Views integration | Grid, Board, Calendar, Timeline views for tasks | All four view types functional |

---

## 4. User Personas & Stories

| ID | Story | Acceptance Criteria |
|---|---|---|
| TSK-01 | As a salesperson, I want to create follow-up tasks linked to a Contact after a meeting, so I don't lose track of commitments. | Task created with contact attachment, due date, and assignee. Visible on Contact detail page. |
| TSK-02 | As Sam (gutter cleaning business owner), I want tasks linked to my custom "Jobs" and "Properties" entities, so my crew knows what work is pending at each property. | Task attachable to any custom object type via Universal Attachment. Visible on custom entity detail pages. |
| TSK-03 | As a team lead, I want to see all open tasks assigned to my team, sorted by due date, so I can manage workload. | Grid View filtered by assignee role, sorted by due_date, filtered to open status categories. |
| TSK-04 | As a user, I want AI-identified action items from my email conversations to automatically become tasks, so I don't have to manually transcribe them. | AI action-item extraction behavior creates task records linked to the originating Conversation. |
| TSK-05 | As a user, I want recurring tasks for periodic relationship maintenance (quarterly check-ins), so I systematically maintain important relationships. | Recurring task with `recurrence_type = 'quarterly'` generates next instance on completion. |
| TSK-06 | As a user, I want to break large tasks into subtasks with completion tracking, so I can manage complex multi-step work. | Parent task shows subtask count and completion percentage. Subtask cascade warns on parent completion. |
| TSK-07 | As a user, I want to mark a task as "blocked by" another task, so I know when dependencies are resolved. | Dependency relation created. Blocked task displays warning with link to blocker. |
| TSK-08 | As a user, I want to see tasks on a Kanban board grouped by status, so I can visualize my workflow pipeline. | Board View grouped by `status` field, cards draggable between columns. |
| TSK-09 | As a user, I want to see tasks on a Timeline view showing start-to-due date bars, so I can visualize scheduling and overlap. | Timeline View renders horizontal bars from `start_date` to `due_date`. |
| TSK-10 | As a user, I want to compare estimated vs actual duration on completed tasks, so I can improve future planning. | Both `estimated_duration` and `actual_duration` visible in Grid View. Delta calculation available in Data Sources. |

---

## 5. Task as System Object Type

### 5.1 Object Type Registration

Task is registered as a system object type in `platform.object_types`:

| Attribute | Value |
|---|---|
| `slug` | `tasks` |
| `name` | `Task` |
| `type_prefix` | `tsk_` |
| `is_system` | `true` |
| `description` | Actionable work items with status workflow, priority, assignees, dependencies, and recurrence |
| `display_name_field` | `title` |
| `icon` | `check-square` (or equivalent) |

### 5.2 Field Registry

| Field Slug | Field Type | System | Required | Default | Description |
|---|---|---|---|---|---|
| `title` | Text | Yes | Yes | — | Task title; display_name_field. |
| `status` | Select | Yes | Yes | `'to_do'` | Current status. Maps to a status category (Section 7). Protected system options + user-extensible. |
| `priority` | Select | Yes | No | `'none'` | Fixed system options: `urgent`, `high`, `medium`, `low`, `none`. Not user-extensible. |
| `start_date` | DateTime | Yes | No | `NULL` | When work should begin. Enables Timeline View rendering. |
| `due_date` | DateTime | Yes | No | `NULL` | When work should be complete. Drives overdue detection and reminder behaviors. |
| `completed_at` | DateTime | Yes | No | `NULL` | Timestamp when status category transitioned to `done`. Managed by status category enforcement behavior. |
| `estimated_duration` | Number (integer) | Yes | No | `NULL` | Estimated effort in minutes. Supports rollup from subtasks. |
| `actual_duration` | Number (integer) | Yes | No | `NULL` | Actual effort in minutes. Manually set by user on completion. |
| `parent_task_id` | Text (FK) | Yes | No | `NULL` | FK → tasks(id). Parent task for subtask hierarchy. |
| `recurring_task_id` | Text (FK) | Yes | No | `NULL` | FK → tasks(id). Points to the recurring template task that generated this instance. |
| `recurrence_type` | Select | Yes | No | `'none'` | `none`, `daily`, `weekly`, `monthly`, `yearly`, `custom`. Fixed system options. |
| `recurrence_rule` | Text | Yes | No | `NULL` | RRULE string for custom recurrence patterns (RFC 5545). |
| `source` | Select | Yes | No | `'manual'` | How the task was created: `manual`, `ai_extracted`, `recurrence_generated`, `api`. Protected system options. |
| `subtask_count` | Number (integer) | Yes | No | `0` | Denormalized count of direct child tasks. Managed by behavior. |
| `subtask_done_count` | Number (integer) | Yes | No | `0` | Denormalized count of direct children with status category `done`. Managed by behavior. |
| `is_overdue` | Boolean | Yes | No | `false` | Whether the task is past `due_date` with open status category. Managed by overdue detection behavior. |

Universal fields (`id`, `tenant_id`, `created_at`, `updated_at`, `created_by`, `updated_by`, `archived_at`) are inherited from the object type framework per Custom Objects PRD Section 7.

Users can add custom fields to Tasks through the standard field registry (e.g., a "Category" select field, an "Effort Points" number field, a "Client Approved" checkbox).

### 5.3 Registered Behaviors

Per Custom Objects PRD Section 22, the Task system object type registers the following specialized behaviors:

| Behavior | Trigger | Description |
|---|---|---|
| Status category enforcement | On status change | Validates that the new status maps to a valid status category. When category transitions to `done`: sets `completed_at` to current timestamp. When category transitions away from `done`: clears `completed_at`. |
| Subtask cascade (warn) | On parent status → `done` category | When a parent task's status transitions to a `done` category, checks for child tasks with open status categories (`not_started`, `active`). If found, emits a warning to the UI ("3 subtasks are still open") but does **not** block the transition. Does not auto-complete children. |
| Subtask count sync | On child task create, archive, status change | Maintains `subtask_count` and `subtask_done_count` denormalized fields on the parent task. Handles multi-level rollup: when a child's counts change, propagate up to grandparent if applicable. |
| Recurrence generation | On task completion (status → `done` category) | If the completed task has `recurrence_type != 'none'`, generates the next task instance: copies title, priority, assignees, entity attachments, and description from the completed task; shifts `start_date` and `due_date` by the recurrence interval; sets `source = 'recurrence_generated'` and `recurring_task_id` pointing to the original template; sets status to the default `not_started` status. |
| AI action-item extraction | On Conversation intelligence event | When the Conversations PRD's AI intelligence layer extracts action items from a communication, creates Task records with: `source = 'ai_extracted'`, title from the extracted action text, entity attachment to the originating Conversation, and optional assignee inference from the action item context. Tasks await user review/confirmation before being treated as committed work. |
| Due date reminder scheduling | On task create, on due_date change | Schedules reminder notification events at configurable intervals before `due_date` (default: 24 hours before, 1 hour before). Depends on a Notifications subsystem (see Open Questions). Clears scheduled reminders if `due_date` is removed or task is completed. |
| Overdue detection | Periodic (background job) | Runs on schedule (e.g., every 15 minutes). Finds tasks where `due_date < NOW()` and status category is `not_started` or `active`. Sets `is_overdue = true`. Clears `is_overdue` when the task is completed or `due_date` is extended. Also clears `is_overdue` if the task was overdue but is now archived. |

---

## 6. Data Model

### 6.1 Tables

All tables reside in the tenant schema (e.g., `tenant_abc.tasks`). The `search_path` is set per request, so queries reference tables without schema qualification.

#### `tasks` — Read model (system object type table)

```sql
CREATE TABLE tasks (
    -- Universal fields (Custom Objects framework)
    id                  TEXT PRIMARY KEY,          -- tsk_ prefixed ULID
    tenant_id           TEXT NOT NULL,             -- FK → platform.tenants
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by          TEXT NOT NULL,             -- FK → platform.users
    updated_by          TEXT NOT NULL,             -- FK → platform.users
    archived_at         TIMESTAMPTZ,              -- Soft delete

    -- Core fields
    title               TEXT NOT NULL,            -- display_name_field
    status              TEXT NOT NULL DEFAULT 'to_do',
    status_category     TEXT NOT NULL DEFAULT 'not_started'
                            CHECK (status_category IN ('not_started', 'active', 'done', 'cancelled')),
    priority            TEXT NOT NULL DEFAULT 'none'
                            CHECK (priority IN ('urgent', 'high', 'medium', 'low', 'none')),
    priority_sort       INTEGER NOT NULL DEFAULT 5,  -- urgent=1, high=2, medium=3, low=4, none=5
    start_date          TIMESTAMPTZ,
    due_date            TIMESTAMPTZ,
    completed_at        TIMESTAMPTZ,              -- Set by status category enforcement behavior

    -- Duration tracking
    estimated_duration  INTEGER,                  -- Minutes
    actual_duration     INTEGER,                  -- Minutes

    -- Hierarchy
    parent_task_id      TEXT REFERENCES tasks(id) ON DELETE SET NULL,

    -- Recurrence
    recurring_task_id   TEXT REFERENCES tasks(id) ON DELETE SET NULL,
    recurrence_type     TEXT NOT NULL DEFAULT 'none'
                            CHECK (recurrence_type IN ('none', 'daily', 'weekly', 'monthly', 'yearly', 'custom')),
    recurrence_rule     TEXT,                     -- RRULE string (RFC 5545)

    -- Source tracking
    source              TEXT NOT NULL DEFAULT 'manual'
                            CHECK (source IN ('manual', 'ai_extracted', 'recurrence_generated', 'api')),

    -- Behavior-managed description content (not in field registry)
    description_json    JSONB,                    -- Editor-native document format
    description_html    TEXT,                     -- Pre-rendered HTML for display
    description_text    TEXT,                     -- Plain text extracted for FTS

    -- Denormalized subtask counts (managed by behavior)
    subtask_count       INTEGER NOT NULL DEFAULT 0,
    subtask_done_count  INTEGER NOT NULL DEFAULT 0,

    -- Overdue flag (managed by behavior)
    is_overdue          BOOLEAN NOT NULL DEFAULT false,

    -- Full-text search (stored generated column)
    search_vector       TSVECTOR GENERATED ALWAYS AS (
        setweight(to_tsvector('english', coalesce(title, '')), 'A') ||
        setweight(to_tsvector('english', coalesce(description_text, '')), 'B')
    ) STORED
);
```

### 6.2 Indexes

```sql
-- Full-text search
CREATE INDEX idx_tasks_search ON tasks USING GIN (search_vector);

-- Status and priority filtering (most common query patterns)
CREATE INDEX idx_tasks_status ON tasks (status);
CREATE INDEX idx_tasks_status_cat ON tasks (status_category);
CREATE INDEX idx_tasks_priority ON tasks (priority_sort, due_date);

-- Date-based queries
CREATE INDEX idx_tasks_due_date ON tasks (due_date) WHERE due_date IS NOT NULL;
CREATE INDEX idx_tasks_start_date ON tasks (start_date) WHERE start_date IS NOT NULL;
CREATE INDEX idx_tasks_completed ON tasks (completed_at) WHERE completed_at IS NOT NULL;

-- Overdue detection (background job query)
CREATE INDEX idx_tasks_overdue_candidates ON tasks (due_date, status_category)
    WHERE status_category IN ('not_started', 'active') AND due_date IS NOT NULL;

-- Hierarchy traversal
CREATE INDEX idx_tasks_parent ON tasks (parent_task_id) WHERE parent_task_id IS NOT NULL;

-- Recurrence
CREATE INDEX idx_tasks_recurring ON tasks (recurring_task_id) WHERE recurring_task_id IS NOT NULL;
CREATE INDEX idx_tasks_recurrence_type ON tasks (recurrence_type) WHERE recurrence_type != 'none';

-- Source filtering (e.g., "show all AI-extracted tasks for review")
CREATE INDEX idx_tasks_source ON tasks (source);

-- Soft delete filter
CREATE INDEX idx_tasks_archived ON tasks (archived_at) WHERE archived_at IS NULL;

-- Tenant isolation
CREATE INDEX idx_tasks_tenant ON tasks (tenant_id);
```

### 6.3 Entity Relationship Diagram

```
tasks 1──* task_entities         (CASCADE delete; universal attachment junction)
tasks 1──* task_user_roles       (CASCADE delete; assignee/reviewer/watcher junction)
tasks 1──* task_dependencies     (CASCADE delete; blocked_by/blocks junction)
tasks 1──* tasks                 (parent_task_id FK; subtask hierarchy)
tasks 1──* tasks                 (recurring_task_id FK; recurrence instances)
tasks ···> tasks_events          (event sourcing; all mutations)

tasks ──> platform.tenants       (tenant_id FK)
tasks ──> platform.users         (created_by, updated_by)

task_entities ··> {any entity type table}  (entity_id; application-level, no DB FK)
task_user_roles ──> platform.users          (user_id FK)
```

---

## 7. Status Model & Categories

### 7.1 Concept

Every task status maps to one of four system categories. Categories are immutable and drive system behavior. Statuses are the user-facing labels and are extensible.

```
Status Categories (system, immutable):
  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐
  │  not_started    │  │     active      │  │      done       │  │   cancelled    │
  │                 │  │                 │  │                 │  │                │
  │  • To Do        │  │  • In Progress  │  │  • Done         │  │  • Cancelled   │
  │  • Backlog      │  │  • In Review    │  │  • Verified     │  │  • Won't Do    │
  │  • Waiting      │  │  • Blocked      │  │                 │  │                │
  │  (user-defined) │  │  (user-defined) │  │  (user-defined) │  │  (user-defined)│
  └────────────────┘  └────────────────┘  └────────────────┘  └────────────────┘
```

### 7.2 Default System Statuses

These are the protected system options on the `status` Select field, pre-mapped to categories:

| Status Slug | Display Name | Category | Sort Order | Protected |
|---|---|---|---|---|
| `to_do` | To Do | `not_started` | 1 | Yes |
| `in_progress` | In Progress | `active` | 2 | Yes |
| `in_review` | In Review | `active` | 3 | Yes |
| `done` | Done | `done` | 4 | Yes |
| `cancelled` | Cancelled | `cancelled` | 5 | Yes |

### 7.3 User-Defined Statuses

Users can add custom statuses through the Select field option management mechanism (Custom Objects PRD Section 13). Each custom status must be assigned to exactly one status category. Examples:

| Custom Status | Assigned Category | Use Case |
|---|---|---|
| Backlog | `not_started` | Low-priority items not yet scheduled |
| Awaiting Client | `active` | Blocked on external input |
| QA Review | `active` | Quality check before completion |
| Verified | `done` | Done and validated |
| Won't Do | `cancelled` | Intentionally abandoned |

### 7.4 Status Category Storage

The `status_category` column is a denormalized field maintained by the status category enforcement behavior. When the `status` field changes, the behavior looks up the new status's category mapping and writes `status_category` accordingly. This enables efficient queries like "all open tasks" without JOINing to a status mapping table.

The status-to-category mapping is stored in the Select field's option metadata:

```json
{
  "slug": "in_review",
  "label": "In Review",
  "color": "#F59E0B",
  "sort_order": 3,
  "is_system": true,
  "metadata": {
    "status_category": "active"
  }
}
```

### 7.5 Behavioral Implications

| Category Transition | System Behavior |
|---|---|
| Any → `done` | Set `completed_at = NOW()`. Trigger recurrence generation if applicable. Clear `is_overdue`. |
| `done` → any other | Clear `completed_at`. Resume overdue detection if `due_date` is past. |
| Any → `cancelled` | Clear `is_overdue`. Do not trigger recurrence generation. |
| Any → `not_started` or `active` | Resume normal overdue detection. |

---

## 8. Priority Model

### 8.1 Fixed Options

Priority is a Select field with **fixed, non-extensible** system options:

| Priority Slug | Display Name | Sort Weight | Color |
|---|---|---|---|
| `urgent` | Urgent | 1 | `#EF4444` (red) |
| `high` | High | 2 | `#F97316` (orange) |
| `medium` | Medium | 3 | `#EAB308` (yellow) |
| `low` | Low | 4 | `#3B82F6` (blue) |
| `none` | None | 5 | `#9CA3AF` (gray) |

### 8.2 Sort Weight

The `priority_sort` column stores the numeric weight for efficient ORDER BY operations. Lower values = higher priority. This avoids CASE expressions in sort queries.

The sort weight is managed by the application layer — when `priority` changes, the corresponding `priority_sort` is written.

---

## 9. Task Hierarchy (Subtasks)

### 9.1 Self-Referential Relation

Subtasks use a **self-referential one:many** pattern on the Task object type:

| Attribute | Value |
|---|---|
| Relation Type Name | Task Hierarchy |
| Relation Type Slug | `task_hierarchy` |
| Source Object Type | Task (`tsk_`) |
| Target Object Type | Task (`tsk_`) |
| Cardinality | One-to-many (parent has many children) |
| Directionality | Bidirectional |
| `is_system` | `true` |
| Cascade (source archived) | Cascade archive children |

Implementation: The `parent_task_id` FK column on the `tasks` table. No junction table needed for 1:many.

### 9.2 Unlimited Nesting

Subtask nesting depth is **unlimited**. The self-referential FK naturally supports any depth. In practice, users rarely go beyond 2–3 levels. No artificial depth limit is imposed.

### 9.3 Subtask Count Rollup

The `subtask_count` and `subtask_done_count` denormalized fields on the parent task enable:

- **Completion percentage**: `subtask_done_count / subtask_count * 100` (computed in views or data sources, not stored)
- **Progress bar rendering** in list and detail views
- **Efficient filtering**: "show tasks with incomplete subtasks" without recursive queries

These counts are **direct children only** (not recursive). Recursive rollup (grandchildren, etc.) is available through Data Source queries using recursive CTEs but is not denormalized due to update cascade complexity.

### 9.4 Cascade Behavior

When a parent task is archived, all direct child tasks are cascaded to archived status (recursive — archiving propagates down the full tree). Unarchiving a parent does **not** automatically unarchive children — the user must explicitly restore each subtask.

### 9.5 Example Hierarchy

```
Task: Prepare Acme Corp Proposal
  ├── Subtask: Research Acme's recent projects
  ├── Subtask: Draft pricing section
  │     ├── Sub-subtask: Get material costs from supplier
  │     └── Sub-subtask: Calculate labor estimates
  ├── Subtask: Create presentation deck
  └── Subtask: Internal review before sending
```

### 9.6 Recursive Queries

For UI scenarios that need the full subtask tree (e.g., task detail page, indented subtask list), a recursive CTE retrieves all descendants:

```sql
WITH RECURSIVE task_tree AS (
    -- Base case: the parent task
    SELECT id, title, status, status_category, parent_task_id, 0 AS depth
    FROM tasks
    WHERE id = $1 AND archived_at IS NULL

    UNION ALL

    -- Recursive case: children
    SELECT t.id, t.title, t.status, t.status_category, t.parent_task_id, tt.depth + 1
    FROM tasks t
    JOIN task_tree tt ON t.parent_task_id = tt.id
    WHERE t.archived_at IS NULL
)
SELECT * FROM task_tree ORDER BY depth, title;
```

---

## 10. Universal Attachment Relation

### 10.1 Reuse of Notes Pattern

Tasks reuse the **Universal Attachment Relation** pattern introduced by the Notes PRD. This is registered in `platform.relation_types`:

| Attribute | Value |
|---|---|
| `id` | `rel_task_attachment` |
| `slug` | `task_entity_attachment` |
| `source_object_type` | `tasks` |
| `target_object_type` | `*` (wildcard — any registered object type) |
| `cardinality` | `many-to-many` |
| `directionality` | `bidirectional` |
| `has_metadata` | `true` |
| `metadata_fields` | `is_primary (boolean)` |
| `cascade_behavior` | See Section 10.3 |

### 10.2 Junction Table

```sql
CREATE TABLE task_entities (
    task_id         TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    entity_type     TEXT NOT NULL,             -- Object type slug (e.g., 'contacts', 'jobs')
    entity_id       TEXT NOT NULL,             -- Prefixed ULID of the linked entity
    is_primary      BOOLEAN NOT NULL DEFAULT false,  -- Primary entity association
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    PRIMARY KEY (task_id, entity_type, entity_id)
);

-- List tasks for an entity (most common query path)
CREATE INDEX idx_te_entity ON task_entities (entity_type, entity_id);

-- Find entities for a task
CREATE INDEX idx_te_task ON task_entities (task_id);
```

### 10.3 Cascade & Consistency

**When a task is deleted (archived):** All `task_entities` rows for that task remain (soft delete preserves links). On hard delete, rows CASCADE delete.

**When a linked entity is deleted (archived):** The `task_entities` row remains — the task still exists but has a stale link. The same background consistency job described in the Notes PRD (Section 6.3) handles stale link detection for both notes and tasks.

**Orphan tasks:** Unlike notes, tasks are **not required** to have at least one entity link. A task can exist as a standalone item (e.g., "Set up new laptop") with no entity attachments. This reflects the reality that not every task relates to a CRM entity.

### 10.4 `is_primary` Metadata

The `is_primary` flag indicates which entity attachment is the "main" association for the task. This affects:

- **Detail page context**: When viewing a task, the primary entity provides the header context ("Task for: Jane Smith")
- **Board View grouping**: Tasks can be grouped by their primary entity
- **Activity timeline**: The primary entity's Activity Card shows the task prominently

At most one `task_entities` row per task can have `is_primary = true`. If no row is flagged, the first-attached entity is treated as primary for display purposes.

---

## 11. Task Assignees

### 11.1 Relation Type

Task assignees are modeled as a **system Relation Type**: Task→User with role metadata.

| Attribute | Value |
|---|---|
| Relation Type Name | Task User Participation |
| Relation Type Slug | `task_user_participation` |
| Source Object Type | Task (`tsk_`) |
| Target Object Type | User (`usr_`) |
| Cardinality | Many-to-many |
| Directionality | Bidirectional |
| `is_system` | `true` |
| `has_metadata` | `true` |

### 11.2 Junction Table

```sql
CREATE TABLE task_user_roles (
    id              TEXT PRIMARY KEY,          -- tur_ prefixed ULID
    task_id         TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    user_id         TEXT NOT NULL,             -- FK → platform.users
    role            TEXT NOT NULL DEFAULT 'assignee'
                        CHECK (role IN ('assignee', 'reviewer', 'watcher')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (task_id, user_id, role)            -- A user can have one of each role per task
);

-- Find all tasks assigned to a user (with role filtering)
CREATE INDEX idx_tur_user ON task_user_roles (user_id, role);

-- Find all participants for a task
CREATE INDEX idx_tur_task ON task_user_roles (task_id);
```

### 11.3 Role Definitions

| Role | Description | Notification Behavior |
|---|---|---|
| `assignee` | Responsible for completing the task. Multiple assignees allowed. | Notified on: task creation, status changes, due date changes, comments. |
| `reviewer` | Responsible for reviewing/approving the task before it's marked done. | Notified on: status transitions to review-category statuses, completion. |
| `watcher` | Wants visibility into task progress without responsibility. | Notified on: status changes, completion. |

### 11.4 Uniqueness

A user can hold each role once per task (UNIQUE constraint on `task_id, user_id, role`). A user can hold **multiple roles** on the same task (e.g., both `assignee` and `reviewer` on a self-reviewed task), resulting in multiple rows.

---

## 12. Task Dependencies

### 12.1 Relation Type

Task dependencies are modeled as a **self-referential many:many Relation Type**:

| Attribute | Value |
|---|---|
| Relation Type Name | Task Dependencies |
| Relation Type Slug | `task_dependencies` |
| Source Object Type | Task (`tsk_`) |
| Target Object Type | Task (`tsk_`) |
| Cardinality | Many-to-many |
| Directionality | Unidirectional |
| `is_system` | `true` |
| `has_metadata` | `true` |

### 12.2 Junction Table

```sql
CREATE TABLE task_dependencies (
    id                  TEXT PRIMARY KEY,        -- dep_ prefixed ULID
    blocking_task_id    TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    blocked_task_id     TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    dependency_type     TEXT NOT NULL DEFAULT 'blocked_by'
                            CHECK (dependency_type IN ('blocked_by')),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (blocking_task_id, blocked_task_id),
    CHECK (blocking_task_id != blocked_task_id)  -- No self-dependency
);

-- Find what blocks a task
CREATE INDEX idx_dep_blocked ON task_dependencies (blocked_task_id);

-- Find what a task blocks
CREATE INDEX idx_dep_blocking ON task_dependencies (blocking_task_id);
```

### 12.3 Semantics

The junction table reads as: "`blocked_task_id` is blocked by `blocking_task_id`."

From the **blocked task's** perspective: "This task is blocked by [blocking_task]."
From the **blocking task's** perspective: "This task blocks [blocked_task]."

### 12.4 Circular Dependency Prevention

Before creating a dependency, the system checks for circular references using a recursive CTE:

```sql
WITH RECURSIVE dep_chain AS (
    SELECT blocking_task_id FROM task_dependencies WHERE blocked_task_id = $blocking_task_id
    UNION
    SELECT td.blocking_task_id FROM task_dependencies td
    JOIN dep_chain dc ON td.blocked_task_id = dc.blocking_task_id
)
SELECT 1 FROM dep_chain WHERE blocking_task_id = $blocked_task_id LIMIT 1;
```

If this returns a row, the dependency would create a cycle and is rejected.

### 12.5 Dependency Warnings

Dependencies generate **warnings, not blocks**. A user can start work on a blocked task — the system surfaces:

- A visual indicator on the task card/row ("⚠ Blocked by 2 tasks")
- The blocking task titles with links
- Whether the blockers are completed (resolved) or still open (unresolved)

This aligns with the warn-but-allow philosophy applied to subtask cascade.

---

## 13. Description Content Architecture

### 13.1 Reuse of Notes Content Pattern

Task descriptions reuse the **behavior-managed content** architecture from the Notes PRD (Section 7). Description content is stored as columns on the `tasks` table but is **not registered in the field registry**.

| Column | Type | Purpose |
|---|---|---|
| `description_json` | `JSONB` | Editor-native document format. Source of truth for re-editing. |
| `description_html` | `TEXT` | Pre-rendered HTML for display contexts. Sanitized before storage. |
| `description_text` | `TEXT` | Plain text extracted from HTML. Used for FTS indexing. |

### 13.2 Differences from Notes

| Aspect | Notes | Task Descriptions |
|---|---|---|
| Revision history | Full revision tracking (append-only `note_revisions` table) | **No revision tracking.** Description changes are captured by standard event sourcing (`field_updated` events in `tasks_events` with `field_name = 'description'`). |
| @Mentions | Extracted and synced to `note_mentions` table | Supported in the editor, but **no separate mention tracking table.** Mentions are stored inline in the JSON document. |
| Multi-entity attachment | Notes can attach to multiple entities | Not applicable — descriptions are part of the task record, not a separate entity. |
| Standalone existence | Notes exist as independent entities | Descriptions are a property of a task, not a standalone entity. |

The rationale for omitting revision tracking: task descriptions are typically shorter and change less frequently than notes. Event sourcing captures the full before/after delta. If revision tracking becomes needed, it can be added in a later phase.

### 13.3 Editor Requirements

The same Flutter rich text editor used for Notes can render task descriptions. Required capabilities are identical: inline formatting, block elements, tables, links, images, @mentions, checklists, and image paste/drop upload.

### 13.4 Content Sanitization

Task description HTML is sanitized using the same allowlist-based sanitizer defined in the Notes PRD Section 15, stripping script tags and unsafe attributes before storage.

---

## 14. Recurrence Model

### 14.1 Events-Aligned Design

Task recurrence mirrors the Events PRD recurrence model (Events PRD Section 6), adapted for completion-triggered generation rather than time-triggered:

| Aspect | Events | Tasks |
|---|---|---|
| Trigger for next instance | Time-based (next occurrence date arrives) | **Completion-based** (current instance marked done) |
| Instance linkage | `recurring_event_id` FK | `recurring_task_id` FK |
| RRULE support | Yes | Yes |
| Recurrence types | `none`, `daily`, `weekly`, `monthly`, `yearly`, `custom` | Same |

### 14.2 Generation Logic

When a recurring task is completed (status category → `done`):

1. **Calculate next dates:** Shift `start_date` and `due_date` forward by the recurrence interval, preserving the original duration between them. For RRULE-based custom recurrence, compute the next occurrence per RFC 5545.
2. **Create new task instance:**
   - Copy: `title`, `priority`, `description_json/html/text`, `recurrence_type`, `recurrence_rule`, `estimated_duration`
   - Set: `source = 'recurrence_generated'`, `recurring_task_id` = completed task's `recurring_task_id` (or the completed task's own ID if it's the original template)
   - Set: `status` = default `to_do`, `status_category` = `not_started`
   - Clear: `actual_duration`, `completed_at`, `is_overdue`
3. **Copy assignees:** Duplicate `task_user_roles` entries from the completed task.
4. **Copy entity attachments:** Duplicate `task_entities` entries from the completed task.
5. **Do not copy:** subtasks, dependencies, or subtask counts.

### 14.3 Cancelling Recurrence

To stop a recurring task from generating future instances:

- Set `recurrence_type = 'none'` on the current pending instance before completing it.
- Or cancel the task (status category → `cancelled`) — the recurrence behavior does not trigger on cancellation.

### 14.4 Viewing Recurrence History

The `recurring_task_id` FK enables querying all instances of a recurring task:

```sql
SELECT * FROM tasks
WHERE recurring_task_id = $template_id
ORDER BY created_at DESC;
```

---

## 15. Event Sourcing & Temporal History

### 15.1 Event Table

Per Custom Objects PRD Section 19, the Task entity type has its own event table:

```sql
CREATE TABLE tasks_events (
    id              TEXT PRIMARY KEY,          -- tev_ prefixed ULID
    entity_id       TEXT NOT NULL,             -- tsk_ prefixed ULID (FK → tasks conceptually)
    event_type      TEXT NOT NULL,
    field_name      TEXT,                      -- The field that changed (NULL for non-field events)
    old_value       JSONB,                     -- Previous value (NULL for creation)
    new_value       JSONB,                     -- New value (NULL for deletion)
    metadata        JSONB,                     -- Additional context
    actor_id        TEXT,                      -- User or system process
    actor_type      TEXT,                      -- 'user', 'system', 'ai', 'sync'
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_tev_entity ON tasks_events (entity_id, created_at);
CREATE INDEX idx_tev_type ON tasks_events (event_type);
```

### 15.2 Event Types

| Event Type | Description |
|---|---|
| `TaskCreated` | New task record created. |
| `FieldUpdated` | A field value changed (title, status, priority, dates, duration, etc.). |
| `DescriptionUpdised` | Task description content changed. `metadata` includes content size but not full content (stored inline on task). |
| `TaskArchived` | Task record archived (soft deleted). |
| `TaskUnarchived` | Task record restored from archive. |
| `AssigneeAdded` | A user added as assignee/reviewer/watcher. `metadata` includes user_id and role. |
| `AssigneeRemoved` | A user removed from task participation. |
| `EntityLinked` | An entity attached to this task via universal attachment. |
| `EntityUnlinked` | An entity detached from this task. |
| `DependencyAdded` | A blocking dependency created. `metadata` includes blocking_task_id or blocked_task_id. |
| `DependencyRemoved` | A blocking dependency removed. |
| `SubtaskAdded` | A child task created (parent_task_id set to this task). |
| `SubtaskRemoved` | A child task unlinked (parent_task_id cleared). |
| `RecurrenceGenerated` | A new task instance generated from this recurring task. `metadata` includes new task ID. |
| `OverdueDetected` | Task flagged as overdue by background job. |
| `OverdueCleared` | Task overdue flag cleared (completed, extended, or archived). |

### 15.3 Point-in-Time Reconstruction

The event stream enables reconstructing any task record's state at any historical timestamp by replaying events from creation up to the target timestamp. Periodic snapshots are stored per Custom Objects PRD Section 19 for performance.

---

## 16. Virtual Schema & Data Sources

### 16.1 Virtual Table

Per the Data Sources PRD, the Task object type's field registry generates a virtual schema table:

```sql
-- Virtual schema (what users see)
SELECT tsk.id, tsk.title, tsk.status, tsk.status_category,
       tsk.priority, tsk.due_date, tsk.start_date,
       tsk.estimated_duration, tsk.actual_duration,
       tsk.is_overdue, tsk.subtask_count, tsk.subtask_done_count
FROM tasks tsk
WHERE tsk.status_category IN ('not_started', 'active')
  AND tsk.due_date < NOW()
ORDER BY tsk.priority_sort ASC, tsk.due_date ASC;
```

The `tsk_` prefix on IDs enables automatic entity detection — the Data Sources query engine recognizes `tsk_01HX8A...` as a Task entity and enables clickable links in result sets.

### 16.2 Relation Traversal

Task→User and Task→Entity relations enable JOIN-based traversal:

```sql
-- Find all open tasks assigned to a specific user
SELECT t.title, t.status, t.priority, t.due_date
FROM tasks t
JOIN task_user_roles tur ON tur.task_id = t.id
WHERE tur.user_id = $user_id
  AND tur.role = 'assignee'
  AND t.status_category IN ('not_started', 'active')
ORDER BY t.priority_sort ASC, t.due_date ASC;

-- Find all tasks linked to a specific contact
SELECT t.title, t.status, t.due_date
FROM tasks t
JOIN task_entities te ON te.task_id = t.id
WHERE te.entity_type = 'contacts' AND te.entity_id = $contact_id
  AND t.archived_at IS NULL
ORDER BY t.due_date ASC;

-- Planned vs actual duration analysis
SELECT t.title, t.estimated_duration, t.actual_duration,
       (t.actual_duration - t.estimated_duration) AS variance_minutes
FROM tasks t
WHERE t.status_category = 'done'
  AND t.estimated_duration IS NOT NULL
  AND t.actual_duration IS NOT NULL
ORDER BY variance_minutes DESC;
```

### 16.3 Views Integration

Task fields participate fully in the Views system:

- **Grid View** — Task list with sortable columns for title, status, priority, due date, assignees, entity attachments, estimated/actual duration.
- **Board/Kanban View** — Cards grouped by `status` field. Drag-and-drop between status columns updates the status and triggers the status category enforcement behavior. Columns ordered by status sort order. Swim lanes can optionally subdivide by priority or assignee.
- **Calendar View** — Tasks plotted on calendar dates by `due_date`. Overdue tasks highlighted. Tasks with `start_date` can optionally show duration spans.
- **Timeline View** — Horizontal bars from `start_date` to `due_date`. Tasks without `start_date` render as point markers on `due_date`. Dependencies can render as arrows between bars (if dependency visualization is enabled).

---

## 17. API Design

### 17.1 Record CRUD (Standard Object Type Pattern)

Task records use the uniform CRUD API pattern from Custom Objects PRD Section 23.4:

| Endpoint | Method | Description |
|---|---|---|
| `/api/v1/tasks` | GET | List tasks (paginated, filterable by status, priority, assignee, due date, entity attachment, overdue flag) |
| `/api/v1/tasks` | POST | Create a task |
| `/api/v1/tasks/{id}` | GET | Get task detail with field values, assignees, entities, dependencies, subtasks |
| `/api/v1/tasks/{id}` | PATCH | Update task fields |
| `/api/v1/tasks/{id}/archive` | POST | Archive (soft delete) |
| `/api/v1/tasks/{id}/unarchive` | POST | Restore from archive |

### 17.2 Subtask Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/api/v1/tasks/{id}/subtasks` | GET | List direct children of a task |
| `/api/v1/tasks/{id}/subtasks` | POST | Create a subtask (sets `parent_task_id`) |
| `/api/v1/tasks/{id}/subtask-tree` | GET | Recursive full subtask tree with depth |

### 17.3 Assignee Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/api/v1/tasks/{id}/assignees` | GET | List all participants with roles |
| `/api/v1/tasks/{id}/assignees` | POST | Add a user with a role |
| `/api/v1/tasks/{id}/assignees/{user_id}/{role}` | DELETE | Remove a user's role |

### 17.4 Entity Attachment Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/api/v1/tasks/{id}/entities` | GET | List attached entities |
| `/api/v1/tasks/{id}/entities` | POST | Attach an entity (entity_type + entity_id) |
| `/api/v1/tasks/{id}/entities/{entity_type}/{entity_id}` | DELETE | Detach an entity |

### 17.5 Dependency Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/api/v1/tasks/{id}/dependencies` | GET | List blocking and blocked-by relationships |
| `/api/v1/tasks/{id}/dependencies` | POST | Create a dependency (specify blocking_task_id or blocked_task_id) |
| `/api/v1/tasks/{id}/dependencies/{dep_id}` | DELETE | Remove a dependency |

### 17.6 Convenience Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/api/v1/tasks/my-tasks` | GET | Tasks assigned to current user (shortcut for assignee filter) |
| `/api/v1/tasks/overdue` | GET | Overdue tasks (shortcut for `is_overdue = true` filter) |
| `/api/v1/tasks/search` | GET | Full-text search across task titles and descriptions |

---

## 18. Design Decisions

### 18.1 Why System Object Type, Not Custom?

Tasks benefit from six registered behaviors (status category enforcement, subtask cascade, recurrence, AI extraction, reminders, overdue detection). Custom object types cannot have behaviors. Additionally, Task is a universal CRM concept that every tenant needs — shipping it as a system type eliminates setup friction.

### 18.2 Why Status Categories Instead of Simple Status?

A flat status Select field works for basic tracking but breaks down when the system needs to answer "is this task complete?" for behavioral logic (recurrence triggers, subtask cascade, overdue detection). With user-extensible statuses, the system can't know that "QA Review" means "still active" or that "Verified" means "done" without a category mapping layer.

### 18.3 Why Fixed Priority?

Priority is one of those fields where consistency matters more than customization. Sortable priority requires a total ordering, which breaks down when users add custom values without defined sort positions. The five-level system (urgent/high/medium/low/none) covers virtually all use cases. Users who want domain-specific prioritization can create custom fields.

### 18.4 Why Multiple Assignees via Relation, Not Single FK?

A single `assigned_to` FK is simpler but doesn't accommodate collaborative work. The relation type pattern with role metadata (assignee, reviewer, watcher) provides flexibility while maintaining accountability through role differentiation. It also enables views like "tasks I'm reviewing" and notification routing by role.

### 18.5 Why Universal Attachment Instead of Explicit Relations?

Tasks need to attach to every entity type — Contact, Company, Event, Conversation, Project, and every custom entity type the user creates. Defining individual relation types for each would require O(n) relation type definitions and wouldn't automatically extend to new custom entity types. The Universal Attachment pattern provides O(1) coverage with automatic extensibility.

### 18.6 Why Warn-But-Allow for Subtask Cascade?

Blocking parent completion until all subtasks are done creates friction in real-world workflows where some subtasks are abandoned or deferred. Auto-completing children loses information ("was this actually done?"). Warning provides awareness while preserving user agency.

### 18.7 Why No Revision Tracking on Descriptions?

Notes require revision tracking because they're the primary content — the note's value is in its text, and tracking how that text evolved is important. Task descriptions are supplementary context — the task's value is in its status, dates, and assignments. Event sourcing captures description changes in the audit trail, which is sufficient.

### 18.8 Why Completion-Triggered Recurrence?

Events use time-triggered recurrence because meetings happen at scheduled times regardless of previous meeting outcomes. Tasks use completion-triggered recurrence because the next instance should only appear after the current one is done — otherwise, recurring tasks pile up if the user falls behind. This matches the model used by Todoist, Asana, and ClickUp for recurring tasks.

### 18.9 Why Standalone Tasks Allowed (No Required Entity Link)?

Unlike notes, which are contextual observations that need an entity anchor, tasks can be purely personal or organizational ("set up new laptop", "review quarterly goals"). Requiring an entity link would force users to create artificial entity associations or maintain a separate personal task tool.

---

## 19. Phasing & Roadmap

### Phase 1: Core Task Management

- Task CRUD with status, priority, dates, duration fields
- Status category model with default system statuses
- Single-level subtasks (parent_task_id FK, subtask count sync)
- Universal Attachment to existing system entity types
- Single assignee (simplified: `assigned_to` FK on task table as shortcut, relation table for multi-assignee deferred)
- Plain text descriptions (rich text deferred)
- Grid View and Board View integration
- Full-text search on title
- Event sourcing

**Note:** Phase 1 uses a simplified single-assignee model via an `assigned_to` FK column on the tasks table. The full Task→User relation type (Section 11) replaces this in Phase 2. The FK column is retained but deprecated as a denormalized "primary assignee" shortcut.

### Phase 2: Full Feature Set

- Multiple assignees via Task→User relation type (Section 11)
- Rich text descriptions (Notes-aligned content architecture)
- Task dependencies (Section 12)
- Unlimited subtask nesting with recursive CTE queries
- Recurrence model (Section 14)
- Calendar View and Timeline View integration
- Overdue detection behavior
- Due date reminder scheduling
- Universal Attachment to custom entity types

### Phase 3: AI Integration

- AI action-item extraction from Conversations → auto-create Tasks
- AI-suggested assignees based on conversation participants
- AI-suggested due dates based on urgency signals in communications
- User review/confirmation workflow for AI-extracted tasks

### Phase 4: Advanced Features

- Dependency visualization (arrows in Timeline View)
- Gantt chart view (dedicated view type or Timeline enhancement)
- Task templates (reusable task structures with subtasks)
- Time logging subsystem (separate entity, linked to tasks)
- Automation triggers (e.g., "when Contact status changes, create task")
- Estimated vs actual duration analytics dashboard

---

## 20. Dependencies & Related PRDs

| PRD | Relationship | Dependency Direction |
|---|---|---|
| **[Custom Objects PRD](custom-objects-prd_v2.md)** | Task is a system object type. Table structure, field registry, event sourcing, Select option management, and relation model are governed by Custom Objects. This PRD defines Task-specific behaviors. | **Bidirectional.** Custom Objects provides the entity framework; this PRD defines behaviors. |
| **[Notes PRD](notes-prd_V3.md)** | Tasks reuse the Universal Attachment Relation pattern and behavior-managed content architecture introduced by Notes. Notes can attach to Tasks via Notes' own universal attachment. | **Tasks depend on Notes** for the Universal Attachment pattern definition. |
| **[Projects PRD](projects-prd_V3.md)** | Tasks attach to Projects through Universal Attachment. Projects gain a task-oriented action layer. | **Bidirectional.** Projects provide organizational context; Tasks provide action tracking. |
| **[Contact Management PRD](contact-management-prd_V5.md)** | Tasks attach to Contacts for follow-up actions and relationship maintenance. | **Tasks depend on Contacts** as an attachment target entity type. |
| **[Company Management PRD](company-management-prd_V1.md)** | Tasks attach to Companies for account-level actions. | **Tasks depend on Companies** as an attachment target entity type. |
| **[Conversations PRD](conversations-prd_V4.md)** | AI action-item extraction creates Tasks linked to Conversations. Tasks also manually attach to Conversations. | **Bidirectional.** Conversations provide extraction triggers; Tasks provide action tracking. |
| **[Event Management PRD](events-prd_V3.md)** | Tasks attach to Events for meeting prep and follow-up tracking. | **Tasks depend on Events** as an attachment target entity type. |
| **[Communications PRD](communications-prd_V1.md)** | AI action-item extraction operates on individual Communications within Conversations. | **Tasks depend on Communications** indirectly via Conversations. |
| **[Data Sources PRD](data-sources-prd_V1.md)** | Task virtual schema table is derived from the Task field registry. `tsk_` prefix enables entity detection. Relation traversal enables cross-entity queries. | **Data Sources depend on Tasks** for entity definitions. |
| **[Views & Grid PRD](views-grid-prd_V5.md)** | Task views (Grid, Board, Calendar, Timeline) use fields from the Task field registry. Status category enables Kanban column mapping. | **Views depend on Tasks** for field definitions. |
| **[Permissions & Sharing PRD](permissions-sharing-prd_V2.md)** | Task record access follows workspace-visible role-based access model. | **Tasks depend on Permissions** for access control. |

---

## 21. Open Questions

1. **Notification subsystem dependency** — Due date reminders and assignee notifications require a Notifications subsystem that does not yet have a PRD. Should the Tasks PRD define a minimal notification contract, or should notifications be deferred entirely until the Notifications PRD is written? The current approach registers the reminder behavior but notes the dependency.

2. **AI-extracted task confidence thresholds** — When the AI intelligence layer extracts action items from conversations, should low-confidence extractions create tasks in a "draft" or "needs review" state, or should they be presented as suggestions in the UI without creating task records? The current approach creates tasks with `source = 'ai_extracted'` but doesn't define a confidence threshold.

3. **Subtask completion rollup scope** — Should `subtask_done_count` count only direct children, or recursively include all descendants? Direct children is simpler and less expensive to maintain. Recursive rollup provides more accurate completion percentages for deeply nested hierarchies but requires cascade updates on every status change.

4. **Due date vs deadline semantics** — Should `due_date` represent a hard deadline (must be done by this date) or a target date (aim to finish by this date)? This affects how aggressively overdue detection and reminders behave. The current model treats `due_date` as a hard deadline for overdue flagging.

5. **Task ordering within a parent** — Should subtasks have a `sort_order` field for manual drag-and-drop reordering within a parent task's subtask list? The current model sorts subtasks by `created_at` or `title`. Manual ordering adds complexity but matches user expectations from task management tools.

6. **Board View column mapping** — Should the Board/Kanban view columns map to individual statuses or to status categories? Individual statuses give more granularity (a column for each custom status), while categories give a simpler 4-column board. Both options should probably be supported.

---

## 22. Future Work

**Scope:** The following items are explicitly out of scope for the current PRD but are anticipated for future development.

- **Task comments / activity feed** — A threaded comment system on tasks, separate from Notes attachment. Would likely be its own system object type or a cross-cutting subsystem similar to Universal Attachment.
- **Time logging** — A dedicated time entry subsystem linked to tasks, enabling detailed time tracking beyond the manual `actual_duration` field. Would include timer functionality, billable/non-billable classification, and timesheet views.
- **Task templates** — Reusable task structures (with predefined subtasks, assignee patterns, and entity attachments) that can be instantiated manually or via automation.
- **Automation triggers** — Rule-based task creation (e.g., "when a Contact's lead status changes to 'qualified', create a follow-up task"). Depends on a broader Automation/Workflow engine PRD.
- **Dependency visualization** — Rendering dependency arrows between tasks in Timeline View, with critical path highlighting.
- **Gantt chart** — Either a dedicated view type or a Timeline View enhancement with dependency arrows, critical path, and resource leveling.
- **Workload balancing** — Dashboard showing task distribution across team members by assignee, with capacity indicators based on estimated duration.
- **Task email integration** — Creating tasks from emails (forward-to-task), emailing task updates to assignees, and syncing tasks with external task tools.
- **Mobile task quick-capture** — Optimized mobile UI for rapid task creation with voice input, location-aware entity suggestion, and photo attachment.

---

## 23. Glossary

General platform terms (Entity Bar, Detail Panel, Card-Based Architecture, Attribute Card, etc.) are defined in the **[Master Glossary V3](glossary_V3.md)**. The following terms are specific to this subsystem:

| Term | Definition |
|---|---|
| **Task** | An actionable work item with status, priority, dates, assignees, and entity attachments. System object type with prefix `tsk_`. |
| **Status** | A user-facing label for the task's workflow position (e.g., "In Review", "Awaiting Client"). Each status maps to exactly one status category. |
| **Status Category** | One of four system categories (`not_started`, `active`, `done`, `cancelled`) that drive system behavior. Immutable — users cannot create new categories. |
| **Priority** | A fixed five-level scale (urgent, high, medium, low, none) with sort weights for ordering. Not user-extensible. |
| **Subtask** | A task whose `parent_task_id` points to another task. Subtasks can themselves have subtasks (unlimited nesting). |
| **Dependency** | A `blocked_by` / `blocks` relationship between two tasks, indicating that one task should be completed before another can begin. Generates warnings, not hard blocks. |
| **Recurrence** | A task configuration that auto-generates a new task instance when the current instance is completed. Uses RRULE (RFC 5545) for complex schedules. |
| **Universal Attachment** | The relation pattern that enables tasks to link to any entity type (system or custom) without per-entity-type relation definitions. Uses `entity_type` + `entity_id` polymorphic columns. |
| **Assignee** | A user with the `assignee` role on a task, responsible for completing the work. |
| **Reviewer** | A user with the `reviewer` role on a task, responsible for reviewing/approving the work. |
| **Watcher** | A user with the `watcher` role on a task, observing progress without responsibility. |
| **Completion Percentage** | `subtask_done_count / subtask_count * 100`. Computed, not stored. Represents the fraction of direct child tasks in a `done` status category. |
| **Overdue** | A task whose `due_date` is past and whose status category is `not_started` or `active`. Detected by a periodic background job. |
| **AI-Extracted Task** | A task auto-created by the AI action-item extraction behavior from conversation intelligence. Has `source = 'ai_extracted'`. |
