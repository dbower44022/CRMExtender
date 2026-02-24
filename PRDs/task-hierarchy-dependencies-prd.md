# Task — Hierarchy, Dependencies & Recurrence Sub-PRD

**Version:** 1.0
**Last Updated:** 2026-02-23
**Status:** Draft
**Entity Base PRD:** [task-entity-base-prd.md]

---

## 1. Overview

### 1.1 Purpose

This sub-PRD defines the structural relationships between tasks: the subtask hierarchy (self-referential 1:many with unlimited nesting and rollup counts), task dependencies (self-referential M:M with blocked_by semantics and circular prevention), and completion-triggered recurrence (RRULE-based instance generation). These three features share the theme of "tasks relating to other tasks."

### 1.2 Preconditions

- Task entity operational with parent_task_id, recurring_task_id FK columns.
- task_dependencies junction table provisioned.
- Status category enforcement behavior operational (done transitions trigger recurrence).

---

## 2. Context

### 2.1 Relevant Fields

| Field | Role in This Action |
|---|---|
| parent_task_id | FK for subtask hierarchy. ON DELETE SET NULL. |
| subtask_count | Denormalized direct child count. |
| subtask_done_count | Denormalized direct children in done category. |
| recurring_task_id | FK linking generated instances to template. ON DELETE SET NULL. |
| recurrence_type | Schedule type (none/daily/weekly/monthly/yearly/custom). |
| recurrence_rule | RFC 5545 RRULE string for custom recurrence. |
| status_category | Drives recurrence trigger (done) and cascade warnings. |

### 2.2 Cross-Entity Context

- **Event Entity Base PRD:** Recurrence model mirrors Events (RRULE, recurrence_type), adapted for completion-triggered generation instead of time-triggered.
- **Assignees & AI Sub-PRD:** Recurrence generation copies assignees from completed instance.

---

## 3. Key Processes

### KP-1: Creating a Subtask

**Trigger:** User creates task with parent_task_id set, or creates subtask from parent's detail page.

**Step 1 — Create child:** Task created with parent_task_id = parent's ID.

**Step 2 — Update parent counts:** Increment parent's subtask_count. If child starts in done category, also increment subtask_done_count.

**Step 3 — Propagate:** If parent itself has a parent, propagate count update up the tree.

### KP-2: Completing a Parent Task

**Trigger:** Parent task's status transitions to done category.

**Step 1 — Check children:** Query direct children with status_category IN ('not_started', 'active').

**Step 2 — Warn if open:** If open children exist, emit warning to UI ("3 subtasks are still open"). Do NOT block the transition.

**Step 3 — Continue:** Status transition completes regardless of warning.

### KP-3: Archiving a Parent Task

**Trigger:** User archives a parent task.

**Step 1 — Cascade archive:** Recursively archive all descendant tasks.

**Step 2 — Event sourcing:** Each archived descendant gets its own TaskArchived event.

**Step 3 — Unarchive is not cascaded:** Restoring the parent does NOT auto-restore children.

### KP-4: Adding a Dependency

**Trigger:** User adds a blocked_by relationship between two tasks.

**Step 1 — Self-check:** Reject if blocking_task_id == blocked_task_id.

**Step 2 — Cycle check:** Run recursive CTE to verify adding this dependency doesn't create a circular chain.

**Step 3 — Create:** Insert task_dependencies row if no cycle detected. Reject with error if cycle.

**Step 4 — Event:** DependencyAdded event on both tasks.

### KP-5: Recurring Task Completion

**Trigger:** Task with recurrence_type != 'none' transitions to done category.

**Step 1 — Calculate dates:** Shift start_date and due_date by recurrence interval, preserving original duration. For custom RRULE, compute next occurrence per RFC 5545.

**Step 2 — Create instance:** New task with copied fields and fresh status.

**Step 3 — Copy relations:** Duplicate assignees and entity attachments from completed task.

**Step 4 — Link:** Set recurring_task_id on new instance.

---

## 4. Subtask Hierarchy

**Supports processes:** KP-1, KP-2, KP-3

### 4.1 Relation Type

| Property | Value |
|---|---|
| Slug | `task_hierarchy` |
| Source/Target | Task → Task (self-referential) |
| Cardinality | One-to-many (parent has many children) |
| Implementation | parent_task_id FK (no junction table) |
| Cascade | Archive cascades down. Unarchive does not. |
| ON DELETE | SET NULL (parent deleted → children become root tasks) |

### 4.2 Unlimited Nesting

No artificial depth limit. Self-referential FK naturally supports any depth. Users rarely exceed 2–3 levels.

### 4.3 Subtask Count Rollup

`subtask_count` and `subtask_done_count` on the parent:
- **Direct children only** (not recursive). Recursive rollup available via CTE but not denormalized.
- Enables completion percentage: `subtask_done_count / subtask_count * 100` (computed, not stored).
- Enables progress bar rendering and "tasks with incomplete subtasks" filtering.

### 4.4 Recursive CTE for Full Tree

```sql
WITH RECURSIVE task_tree AS (
    SELECT id, title, status, status_category, parent_task_id, 0 AS depth
    FROM tasks WHERE id = $root_task_id AND archived_at IS NULL

    UNION ALL

    SELECT t.id, t.title, t.status, t.status_category, t.parent_task_id, tt.depth + 1
    FROM tasks t
    JOIN task_tree tt ON t.parent_task_id = tt.id
    WHERE t.archived_at IS NULL
)
SELECT * FROM task_tree ORDER BY depth, title;
```

**Tasks:**

- [ ] THDR-01: Implement subtask creation with parent_task_id assignment
- [ ] THDR-02: Implement subtask_count increment on child creation
- [ ] THDR-03: Implement subtask_done_count update on child status change
- [ ] THDR-04: Implement count propagation up tree (multi-level)
- [ ] THDR-05: Implement cascade archive of descendant tasks
- [ ] THDR-06: Implement subtask cascade warning on parent → done (warn, don't block)
- [ ] THDR-07: Implement recursive CTE for full subtask tree retrieval

**Tests:**

- [ ] THDR-T01: Test subtask creation increments parent subtask_count
- [ ] THDR-T02: Test subtask completion increments parent subtask_done_count
- [ ] THDR-T03: Test subtask archive decrements parent subtask_count
- [ ] THDR-T04: Test cascade archive propagates to all descendants
- [ ] THDR-T05: Test unarchive does NOT cascade to children
- [ ] THDR-T06: Test parent deletion sets children parent_task_id to NULL
- [ ] THDR-T07: Test completion warning fires when parent → done with open children
- [ ] THDR-T08: Test parent → done NOT blocked by open children
- [ ] THDR-T09: Test recursive CTE returns correct tree structure

---

## 5. Task Dependencies

**Supports processes:** KP-4

### 5.1 Relation Type

| Property | Value |
|---|---|
| Slug | `task_dependencies` |
| Source/Target | Task → Task (self-referential) |
| Cardinality | Many-to-many |
| Directionality | Unidirectional |
| Implementation | task_dependencies junction table |
| Semantics | blocking_task_id blocks blocked_task_id |

### 5.2 Dependency Semantics

- From blocked task: "This task is blocked by [blocking_task]."
- From blocking task: "This task blocks [blocked_task]."
- Single type: `blocked_by`. Extensible later if needed (finish-to-start, start-to-start, etc.).

### 5.3 Circular Dependency Prevention

Before creating a dependency, check for cycles:

```sql
WITH RECURSIVE dep_chain AS (
    SELECT blocking_task_id FROM task_dependencies
    WHERE blocked_task_id = $blocking_task_id
    UNION
    SELECT td.blocking_task_id FROM task_dependencies td
    JOIN dep_chain dc ON td.blocked_task_id = dc.blocking_task_id
)
SELECT 1 FROM dep_chain WHERE blocking_task_id = $blocked_task_id LIMIT 1;
```

If result found, dependency creates a cycle — reject with error.

### 5.4 Warn-But-Allow

Dependencies generate warnings, not hard blocks. Users CAN start work on blocked tasks. UI surfaces:
- Visual indicator: "⚠ Blocked by 2 tasks"
- Blocking task titles with links
- Resolution status (blocker completed or still open)

**Tasks:**

- [ ] THDR-08: Implement dependency creation with self-check
- [ ] THDR-09: Implement circular dependency detection via recursive CTE
- [ ] THDR-10: Implement dependency removal
- [ ] THDR-11: Implement blocked/blocking query (both directions)
- [ ] THDR-12: Implement dependency resolution status (blocker completed vs. open)

**Tests:**

- [ ] THDR-T10: Test self-dependency rejected
- [ ] THDR-T11: Test direct circular dependency rejected (A blocks B, B blocks A)
- [ ] THDR-T12: Test transitive circular dependency rejected (A→B→C→A)
- [ ] THDR-T13: Test valid dependency created successfully
- [ ] THDR-T14: Test CASCADE removes dependencies when task deleted
- [ ] THDR-T15: Test UNIQUE prevents duplicate dependency
- [ ] THDR-T16: Test dependency resolution status reflects blocking task completion

---

## 6. Recurrence Model

**Supports processes:** KP-5

### 6.1 Events-Aligned Design

| Aspect | Events | Tasks |
|---|---|---|
| Trigger | Time-based | Completion-based (status → done) |
| Instance linkage | recurring_event_id FK | recurring_task_id FK |
| RRULE | Yes | Yes |
| Recurrence types | none/daily/weekly/monthly/yearly/custom | Same |

### 6.2 Generation Logic

When a recurring task completes (status_category → `done`):

1. **Calculate next dates:** Shift start_date and due_date by interval, preserving duration. Custom RRULE computed per RFC 5545.
2. **Create new instance:**
   - Copy: title, priority, description (json/html/text), recurrence_type, recurrence_rule, estimated_duration
   - Set: source = 'recurrence_generated', recurring_task_id = template ID, status = to_do, status_category = not_started
   - Clear: actual_duration, completed_at, is_overdue
3. **Copy assignees:** Duplicate task_user_roles entries.
4. **Copy entity attachments:** Duplicate task_entities entries.
5. **Do NOT copy:** subtasks, dependencies, subtask counts.

### 6.3 Cancelling Recurrence

- Set recurrence_type = 'none' before completing → no next instance.
- Cancel task (→ cancelled category) → recurrence does NOT trigger.

### 6.4 Recurrence History

```sql
SELECT * FROM tasks
WHERE recurring_task_id = $template_id
ORDER BY created_at DESC;
```

**Tasks:**

- [ ] THDR-13: Implement recurrence generation on task completion
- [ ] THDR-14: Implement date shifting with duration preservation
- [ ] THDR-15: Implement RRULE-based next occurrence calculation
- [ ] THDR-16: Implement field copying for new instance
- [ ] THDR-17: Implement assignee copying for new instance
- [ ] THDR-18: Implement entity attachment copying for new instance
- [ ] THDR-19: Implement recurrence cancellation (set type to none)
- [ ] THDR-20: Implement recurrence skip on cancelled status

**Tests:**

- [ ] THDR-T17: Test completing recurring task creates next instance
- [ ] THDR-T18: Test next instance has correct shifted dates
- [ ] THDR-T19: Test next instance copies title, priority, description
- [ ] THDR-T20: Test next instance copies assignees
- [ ] THDR-T21: Test next instance copies entity attachments
- [ ] THDR-T22: Test next instance does NOT copy subtasks
- [ ] THDR-T23: Test cancelled task does NOT trigger recurrence
- [ ] THDR-T24: Test setting recurrence_type = 'none' prevents generation
- [ ] THDR-T25: Test recurring_task_id links all instances to template
