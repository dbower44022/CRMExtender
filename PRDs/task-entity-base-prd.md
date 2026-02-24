# Task — Entity Base PRD

**Version:** 1.0
**Last Updated:** 2026-02-23
**Status:** Draft
**Product PRD:** [CRMExtender Product PRD]

---

## 1. Entity Definition

### 1.1 Purpose

Task is the action management layer of CRMExtender. While Communications capture what was said, Conversations organize threads, Events track meetings, and Notes store observations, Tasks answer "What needs to be done, by whom, and by when?" Tasks bridge relationship intelligence and business execution — translating insights from conversations and meetings into trackable, assignable, completable work items.

Unlike standalone task managers, CRMExtender tasks are deeply embedded in the CRM entity graph. A task can attach to a Contact, Company, custom Job entity, or any combination. Tasks spawned from AI action-item extraction auto-link to originating Conversations, preserving the full context chain.

### 1.2 Design Goals

- **System object type** — Full participation in Views, Data Sources, event sourcing, field registry, permissions. Specialized behaviors (status enforcement, subtask cascade, recurrence, AI extraction, reminders, overdue detection) registered with the framework.
- **Universal attachment** — Tasks attach to any entity type through the Universal Attachment Relation pattern. Standalone tasks (no entity link) are also permitted.
- **Status categories** — User-extensible statuses mapped to four immutable system categories that drive completion tracking, recurrence triggers, and overdue detection.
- **Multiple assignees** — Task→User relation type with role metadata (assignee, reviewer, watcher).
- **Unlimited subtask hierarchy** — Self-referential parent_task_id FK with subtask count rollup.
- **Simple blocking dependencies** — Self-referential M:M with warn-but-allow philosophy.
- **Completion-triggered recurrence** — RRULE-based, generates next instance on completion.
- **AI action-item extraction** — Conversation intelligence auto-creates tasks with source tracking.

### 1.3 Performance Targets

| Metric | Target |
|---|---|
| Task list load (default view, 50 rows) | < 200ms |
| Subtask tree load (recursive CTE, 3 levels) | < 100ms |
| Overdue detection batch (background job) | < 5s |
| Dependency cycle check | < 50ms |
| Full-text search (95th percentile) | < 200ms |

### 1.4 Core Fields

| Field | Description | Required | Editable | Sortable | Filterable | Valid Values / Rules |
|---|---|---|---|---|---|---|
| ID | Unique identifier. Prefixed ULID with `tsk_` prefix. | Yes | System | No | Yes | Prefixed ULID |
| Title | Task name. Display name field. | Yes | Direct | Yes | Yes | Free text |
| Status | Workflow position. Select with protected + user-extensible options. | Yes | Direct | Yes | Yes | Default: to_do |
| Status Category | System category. Denormalized from status mapping. | Yes | System (derived) | No | Yes | `not_started`, `active`, `done`, `cancelled` |
| Priority | Importance level. Fixed, non-extensible. | Yes | Direct | Yes | Yes | `urgent`, `high`, `medium`, `low`, `none`. Default: none. |
| Priority Sort | Numeric sort weight. | Yes | System (derived) | Yes | No | 1–5 (urgent=1, none=5) |
| Start Date | When work should begin. | No | Direct | Yes | Yes | TIMESTAMPTZ |
| Due Date | When work should be complete. | No | Direct | Yes | Yes | TIMESTAMPTZ |
| Completed At | When status transitioned to done category. | No | System | Yes | Yes | TIMESTAMPTZ. Set/cleared by behavior. |
| Estimated Duration | Planned effort in minutes. | No | Direct | Yes | Yes | Integer (minutes) |
| Actual Duration | Recorded effort in minutes. | No | Direct | Yes | Yes | Integer (minutes) |
| Parent Task ID | Self-reference for subtask hierarchy. | No | Direct | No | Yes | FK to tasks(id), ON DELETE SET NULL |
| Recurring Task ID | Reference to recurrence template. | No | System | No | Yes | FK to tasks(id), ON DELETE SET NULL |
| Recurrence Type | Recurrence schedule. | Yes | Direct | No | Yes | `none`, `daily`, `weekly`, `monthly`, `yearly`, `custom`. Default: none. |
| Recurrence Rule | RFC 5545 RRULE string. | No | Direct | No | No | RRULE string |
| Source | How task entered the system. | Yes | System | No | Yes | `manual`, `ai_extracted`, `recurrence_generated`, `api`. Default: manual. |
| Description JSON | Editor-native document. **Behavior-managed.** | No | Via content pipeline | No | No | JSONB |
| Description HTML | Pre-rendered HTML. **Behavior-managed.** | No | Via content pipeline | No | No | Sanitized HTML |
| Description Text | Plain text for FTS. **Behavior-managed.** | No | Computed | No | No (use FTS) | Plain text |
| Subtask Count | Direct child count. Denormalized. | No | System | Yes | Yes | Non-negative integer |
| Subtask Done Count | Direct children in done category. Denormalized. | No | System | Yes | Yes | Non-negative integer |
| Is Overdue | Due date past and status open. | No | System | No | Yes | Boolean. Default: false. |
| Status (Record) | Record lifecycle. | Yes, defaults to active | System | Yes | Yes | `active`, `archived` |
| Created By | User or system that created. | Yes | System | No | Yes | Reference to User |
| Created At | Record creation timestamp. | Yes | System | Yes | Yes | Timestamp |
| Updated At | Last modification timestamp. | Yes | System | Yes | Yes | Timestamp |

### 1.5 Registered Behaviors

| Behavior | Trigger | Description |
|---|---|---|
| Status category enforcement | On status change | Validates category mapping. Sets/clears completed_at on done transitions. |
| Subtask cascade (warn) | On parent → done category | Warns about open children but does not block transition. |
| Subtask count sync | On child create/archive/status change | Maintains subtask_count and subtask_done_count. Propagates up tree. |
| Recurrence generation | On task → done category | Generates next instance if recurrence_type != 'none'. See Hierarchy Sub-PRD. |
| AI action-item extraction | On Conversation intelligence event | Auto-creates tasks from extracted action items. See Assignees & AI Sub-PRD. |
| Due date reminder scheduling | On create, on due_date change | Schedules notifications before due_date. See Assignees & AI Sub-PRD. |
| Overdue detection | Periodic background job | Sets/clears is_overdue based on due_date vs. status category. See Assignees & AI Sub-PRD. |

### 1.6 Field Groups

```
── Task Details ───────────────────────────────────
  Title          | Status         | Priority

── Scheduling ─────────────────────────────────────
  Start Date     | Due Date       | Completed At
  Estimated Dur. | Actual Dur.    | Is Overdue

── Hierarchy & Recurrence ─────────────────────────
  Parent Task    | Subtasks (count/done)
  Recurrence     | Source

── Record Info (system) ───────────────────────────
  Created: Feb 17, 2026 by Sam  |  Updated: Feb 17, 2026
```

---

## 2. Entity Relationships

### 2.1 Any Entity (Universal Attachment)

**Nature:** Many-to-many, via `task_entities` polymorphic junction table
**Ownership:** This entity
**Description:** Tasks attach to any registered object type. Reuses Universal Attachment pattern from Notes. Includes `is_primary` metadata for primary entity association. Unlike Notes, standalone tasks (no entity link) are permitted.

### 2.2 Users (Assignees)

**Nature:** Many-to-many, via `task_user_roles` junction table
**Ownership:** This entity (Relation Type: `task_user_participation`)
**Description:** Users participate as assignee, reviewer, or watcher. Multiple assignees allowed. See Assignees & AI Sub-PRD.

### 2.3 Tasks (Subtask Hierarchy)

**Nature:** One-to-many, self-referential via `parent_task_id` FK
**Ownership:** This entity (Relation Type: `task_hierarchy`)
**Description:** Unlimited nesting. Subtask count rollup. Cascade archive. See Hierarchy Sub-PRD.

### 2.4 Tasks (Dependencies)

**Nature:** Many-to-many, self-referential via `task_dependencies` junction
**Ownership:** This entity (Relation Type: `task_dependencies`)
**Description:** blocked_by/blocks relationships. Warn-but-allow. Circular prevention. See Hierarchy Sub-PRD.

### 2.5 Tasks (Recurrence)

**Nature:** Many-to-one, self-referential via `recurring_task_id` FK
**Ownership:** This entity
**Description:** Generated instances reference their template. ON DELETE SET NULL preserves instances.

### 2.6 Notes

**Nature:** Many-to-many, via Notes universal attachment
**Ownership:** Notes PRD
**Description:** Notes attach to tasks for commentary, context, meeting minutes.

### 2.7 Documents

**Nature:** Many-to-many, via Documents universal attachment
**Ownership:** Documents PRD
**Description:** Documents attach to tasks for supporting files, deliverables.

---

## 3. Status Model & Categories

### 3.1 Concept

Every task status maps to one of four immutable system categories. Categories drive system behavior. Statuses are user-facing labels and are extensible.

```
Status Categories (system, immutable):
  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐
  │  not_started    │  │     active      │  │      done       │  │   cancelled    │
  │  • To Do        │  │  • In Progress  │  │  • Done         │  │  • Cancelled   │
  │  • Backlog      │  │  • In Review    │  │  • Verified     │  │  • Won't Do    │
  │  (user-defined) │  │  (user-defined) │  │  (user-defined) │  │  (user-defined)│
  └────────────────┘  └────────────────┘  └────────────────┘  └────────────────┘
```

### 3.2 Default System Statuses

| Status Slug | Display Name | Category | Sort Order | Protected |
|---|---|---|---|---|
| `to_do` | To Do | `not_started` | 1 | Yes |
| `in_progress` | In Progress | `active` | 2 | Yes |
| `in_review` | In Review | `active` | 3 | Yes |
| `done` | Done | `done` | 4 | Yes |
| `cancelled` | Cancelled | `cancelled` | 5 | Yes |

### 3.3 User-Defined Statuses

Users add custom statuses through Select field option management. Each must be assigned to exactly one category. Examples: Backlog (not_started), Awaiting Client (active), QA Review (active), Verified (done), Won't Do (cancelled).

### 3.4 Status Category Storage

`status_category` is denormalized — maintained by the status category enforcement behavior. When `status` changes, the behavior looks up the category mapping from the Select field's option metadata and writes `status_category`. Enables efficient queries without JOINs.

### 3.5 Behavioral Implications

| Category Transition | System Behavior |
|---|---|
| Any → `done` | Set completed_at. Trigger recurrence generation. Clear is_overdue. |
| `done` → any other | Clear completed_at. Resume overdue detection. |
| Any → `cancelled` | Clear is_overdue. Do NOT trigger recurrence. |
| Any → `not_started` or `active` | Resume normal overdue detection. |

---

## 4. Priority Model

### 4.1 Fixed Options

Priority is a Select field with fixed, non-extensible system options:

| Slug | Display Name | Sort Weight | Color |
|---|---|---|---|
| `urgent` | Urgent | 1 | #EF4444 (red) |
| `high` | High | 2 | #F97316 (orange) |
| `medium` | Medium | 3 | #EAB308 (yellow) |
| `low` | Low | 4 | #3B82F6 (blue) |
| `none` | None | 5 | #9CA3AF (gray) |

### 4.2 Sort Weight

`priority_sort` stores numeric weight for ORDER BY. Lower = higher priority. Application layer sets weight when priority changes. Avoids CASE expressions in queries.

---

## 5. Universal Attachment Relation

### 5.1 Reuse of Notes Pattern

| Attribute | Value |
|---|---|
| Slug | `task_entity_attachment` |
| Source | `tasks` |
| Target | `*` (any registered object type) |
| Cardinality | Many-to-many |
| Metadata | `is_primary` (Boolean) |

### 5.2 is_primary Metadata

Indicates the "main" entity association for the task. Affects detail page header context, Board View grouping, and Activity Card prominence. At most one task_entities row per task has is_primary = true. If none flagged, first-attached entity is treated as primary for display.

### 5.3 Standalone Tasks

Unlike Notes (which require at least one entity link), tasks are NOT required to have entity links. A task can exist standalone (e.g., "Set up new laptop"). API does not prevent removing the last entity link.

---

## 6. Description Content Architecture

### 6.1 Behavior-Managed Content

Task descriptions reuse the behavior-managed content pattern from Notes. Three columns on the tasks table, NOT in the field registry:

| Column | Type | Purpose |
|---|---|---|
| description_json | JSONB | Editor-native document for re-editing |
| description_html | TEXT | Pre-rendered sanitized HTML for display |
| description_text | TEXT | Plain text for FTS indexing |

### 6.2 Differences from Notes

| Aspect | Notes | Task Descriptions |
|---|---|---|
| Revision history | Full revision tracking | No revisions. Event sourcing captures deltas. |
| @Mentions | Extracted to note_mentions table | Stored inline in JSON only. No separate table. |
| Multi-entity attachment | Notes are separate entities | Description is a property of the task record. |
| Standalone existence | Notes are independent entities | Description embedded in task. |

### 6.3 Editor & Sanitization

Same Flutter rich text editor and server-side HTML sanitization allowlists as Notes. Same capabilities: inline formatting, blocks, tables, links, images, @mentions, checklists.

---

## 7. Lifecycle

| Status | Description |
|---|---|
| `active` | Normal operating state. Visible in views and search. |
| `archived` | Soft-deleted. Excluded from default queries. Recoverable. Cascade archives children. |

Task `status` field (to_do, in_progress, etc.) is orthogonal to record lifecycle.

---

## 8. Key Processes

### KP-1: Creating a Task

**Trigger:** User creates task from UI, API, recurrence generation, or AI extraction.

**Step 1 — Data entry:** Title (required), status, priority, dates, description.

**Step 2 — Entity links:** Optionally attach to entities. Set is_primary.

**Step 3 — Assignees:** Add users with roles (assignee, reviewer, watcher).

**Step 4 — Parent:** Optionally set parent_task_id for subtask.

**Step 5 — Behaviors fire:** Status category enforcement, subtask count sync on parent, due date reminder scheduling.

### KP-2: Working a Task Through Workflow

**Trigger:** User changes task status.

**Step 1 — Status change:** User selects new status.

**Step 2 — Category enforcement:** Behavior resolves status → category. Updates status_category, manages completed_at.

**Step 3 — Subtask warning:** If parent → done, check for open children. Warn but don't block.

**Step 4 — Recurrence:** If → done and recurrence_type != 'none', generate next instance.

**Step 5 — Overdue:** Clear is_overdue if transitioning to done/cancelled.

### KP-3: Browsing Tasks

**Trigger:** User navigates to Tasks in Entity Bar or views entity's task list.

**Step 1 — View loads:** Grid, Board (grouped by status/category), Calendar, or Timeline.

**Step 2 — Filtering:** By status, status_category, priority, assignee, due date range, source, is_overdue, entity attachment.

**Step 3 — Sorting:** Priority sort weight, due date, created_at.

### KP-4: Viewing Task Detail

**Trigger:** User selects a task.

**Step 1 — Detail panel:** Title, status, priority, dates, description in Attribute Cards.

**Step 2 — Subtasks panel:** Direct children with completion progress.

**Step 3 — Assignees panel:** Users with roles.

**Step 4 — Entity links panel:** Attached entities with primary indicator.

**Step 5 — Dependencies panel:** Blocking/blocked tasks with resolution status.

---

## 9. Action Catalog

### 9.1 Create Task

**Supports processes:** KP-1
**Trigger:** Manual, API, AI extraction, recurrence.
**Outcome:** Task with status, priority, optional entity links, assignees, subtask relationship.

### 9.2 Edit Task

**Supports processes:** KP-2
**Trigger:** User modifies fields.
**Outcome:** Field updated. Status category enforced. Behaviors triggered.

### 9.3 Browse / Search Tasks

**Supports processes:** KP-3, KP-4
**Trigger:** User navigation.
**Outcome:** Filtered, sorted task views with Board, Grid, Calendar, Timeline options.

### 9.4 Archive / Restore

**Trigger:** User archives or restores.
**Outcome:** Cascade archive to children. Restore is per-task (not cascaded).

### 9.5 Hierarchy, Dependencies & Recurrence

**Summary:** Subtask hierarchy (unlimited nesting, count rollup, cascade archive, recursive CTE), task dependencies (blocked_by/blocks, circular prevention, warn-but-allow), completion-triggered recurrence (RRULE-based, instance generation copying assignees/attachments, cancellation).
**Sub-PRD:** [task-hierarchy-dependencies-prd.md]

### 9.6 Assignees, Behaviors & AI Intelligence

**Summary:** Task→User relation with roles (assignee/reviewer/watcher), role-based notifications. Overdue detection background job. Due date reminder scheduling. AI action-item extraction from Conversations (auto-create tasks, source tracking, review workflow).
**Sub-PRD:** [task-assignees-ai-prd.md]

---

## 10. Open Questions

1. **Notification subsystem dependency:** Reminders and assignee notifications require a Notifications PRD. Define minimal contract here or defer?
2. **AI-extracted task confidence:** Low-confidence extractions as draft tasks or UI suggestions without records?
3. **Subtask rollup scope:** Direct children only (current) or recursive descendants?
4. **Due date semantics:** Hard deadline or target date? Affects overdue aggressiveness.
5. **Subtask ordering:** Manual sort_order for drag-and-drop? Currently by created_at/title.
6. **Board View columns:** Map to individual statuses or status categories? Probably both.

---

## 11. Design Decisions

### Why system object type?

Full participation in Views, Data Sources, event sourcing. Task management is core CRM functionality, not a custom extension.

### Why status categories instead of simple status?

Users need custom workflows (QA Review, Awaiting Client) but the system needs reliable completion detection, recurrence triggers, and overdue logic. Categories provide the stable layer; statuses provide the flexible layer.

### Why fixed priority?

Priority semantics must be consistent for sorting, filtering, and cross-project comparison. User-defined priorities create ambiguity ("is my 'Critical' the same as your 'Urgent'?").

### Why multiple assignees via relation, not single FK?

Real tasks involve multiple people: primary assignee, reviewer, watchers. Single FK forces "one owner" which doesn't match collaborative workflows.

### Why Universal Attachment instead of explicit relations?

Same rationale as Notes: tasks need to attach to any entity type including future custom objects. Per-type relations would require provisioning for each entity type.

### Why warn-but-allow for subtask cascade and dependencies?

Blocking completion or work-start on open subtasks/blockers is too rigid. Real workflows have exceptions. Warnings provide awareness without friction.

### Why no revision tracking on descriptions?

Task descriptions are shorter and change less frequently than notes. Event sourcing captures deltas. Revision tracking can be added later if needed.

### Why completion-triggered recurrence?

Tasks complete on different schedules. Time-triggered generation would create unfinished instances piling up. Completion-triggered ensures one active instance at a time.

### Why standalone tasks allowed (no required entity link)?

Not every task relates to a CRM entity. "Set up new laptop", "Update team wiki", "Review quarterly numbers" are valid standalone tasks.

---

## Related Documents

| Document | Relationship |
|---|---|
| [Task Entity TDD](task-entity-tdd.md) | Technical decisions for task implementation |
| [Hierarchy, Dependencies & Recurrence Sub-PRD](task-hierarchy-dependencies-prd.md) | Subtasks, dependencies, recurrence |
| [Assignees, Behaviors & AI Intelligence Sub-PRD](task-assignees-ai-prd.md) | Assignees, overdue, reminders, AI extraction |
| [Custom Objects PRD](custom-objects-prd.md) | Unified object model |
| [Note Entity Base PRD](note-entity-base-prd.md) | Universal Attachment pattern origin, content architecture |
| [Conversation Entity Base PRD](conversation-entity-base-prd.md) | AI extraction source |
| [Projects PRD](projects-prd.md) | Tasks attach to projects |
| [Master Glossary](glossary.md) | Term definitions |
