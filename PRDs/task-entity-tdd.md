# Task Entity — TDD

**Version:** 1.0
**Last Updated:** 2026-02-23
**Status:** Draft
**Scope:** Entity
**Parent Document:** [task-entity-base-prd.md]
**Product TDD:** [product-tdd.md]

---

## 1. Overview

The Task entity requires entity-specific technical decisions beyond the Product TDD's global defaults. Key areas include: the read model table DDL with 13 specialized indexes, universal attachment junction table with is_primary, assignee junction table, dependency junction table with circular prevention, event sourcing, virtual schema, and API design.

---

## 2. Tasks Read Model Table

### 2.1 Table Definition

```sql
CREATE TABLE tasks (
    id                  TEXT PRIMARY KEY,          -- tsk_ prefixed ULID
    tenant_id           TEXT NOT NULL,
    title               TEXT NOT NULL,
    status              TEXT NOT NULL DEFAULT 'to_do',
    status_category     TEXT NOT NULL DEFAULT 'not_started'
                            CHECK (status_category IN ('not_started', 'active', 'done', 'cancelled')),
    priority            TEXT NOT NULL DEFAULT 'none'
                            CHECK (priority IN ('urgent', 'high', 'medium', 'low', 'none')),
    priority_sort       INTEGER NOT NULL DEFAULT 5,
    start_date          TIMESTAMPTZ,
    due_date            TIMESTAMPTZ,
    completed_at        TIMESTAMPTZ,

    -- Duration tracking
    estimated_duration  INTEGER,                  -- Minutes
    actual_duration     INTEGER,                  -- Minutes

    -- Hierarchy
    parent_task_id      TEXT REFERENCES tasks(id) ON DELETE SET NULL,

    -- Recurrence
    recurring_task_id   TEXT REFERENCES tasks(id) ON DELETE SET NULL,
    recurrence_type     TEXT NOT NULL DEFAULT 'none'
                            CHECK (recurrence_type IN ('none', 'daily', 'weekly', 'monthly', 'yearly', 'custom')),
    recurrence_rule     TEXT,

    -- Source tracking
    source              TEXT NOT NULL DEFAULT 'manual'
                            CHECK (source IN ('manual', 'ai_extracted', 'recurrence_generated', 'api')),

    -- Behavior-managed description (not in field registry)
    description_json    JSONB,
    description_html    TEXT,
    description_text    TEXT,

    -- Denormalized counts (managed by behavior)
    subtask_count       INTEGER NOT NULL DEFAULT 0,
    subtask_done_count  INTEGER NOT NULL DEFAULT 0,

    -- Overdue flag (managed by behavior)
    is_overdue          BOOLEAN NOT NULL DEFAULT false,

    -- Full-text search
    search_vector       TSVECTOR GENERATED ALWAYS AS (
        setweight(to_tsvector('english', coalesce(title, '')), 'A') ||
        setweight(to_tsvector('english', coalesce(description_text, '')), 'B')
    ) STORED,

    -- Universal fields
    created_by          TEXT NOT NULL,
    updated_by          TEXT NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    archived_at         TIMESTAMPTZ
);
```

### 2.2 Indexes

```sql
CREATE INDEX idx_tasks_search ON tasks USING GIN (search_vector);
CREATE INDEX idx_tasks_status ON tasks (status);
CREATE INDEX idx_tasks_status_cat ON tasks (status_category);
CREATE INDEX idx_tasks_priority ON tasks (priority_sort, due_date);
CREATE INDEX idx_tasks_due_date ON tasks (due_date) WHERE due_date IS NOT NULL;
CREATE INDEX idx_tasks_start_date ON tasks (start_date) WHERE start_date IS NOT NULL;
CREATE INDEX idx_tasks_completed ON tasks (completed_at) WHERE completed_at IS NOT NULL;
CREATE INDEX idx_tasks_overdue_candidates ON tasks (due_date, status_category)
    WHERE status_category IN ('not_started', 'active') AND due_date IS NOT NULL;
CREATE INDEX idx_tasks_parent ON tasks (parent_task_id) WHERE parent_task_id IS NOT NULL;
CREATE INDEX idx_tasks_recurring ON tasks (recurring_task_id) WHERE recurring_task_id IS NOT NULL;
CREATE INDEX idx_tasks_recurrence_type ON tasks (recurrence_type) WHERE recurrence_type != 'none';
CREATE INDEX idx_tasks_source ON tasks (source);
CREATE INDEX idx_tasks_archived ON tasks (archived_at) WHERE archived_at IS NULL;
CREATE INDEX idx_tasks_tenant ON tasks (tenant_id);
```

**Rationale:** Overdue candidates index supports background job query without full table scan. Partial indexes on nullable date columns and hierarchy FKs reduce index size. Priority + due_date composite for "most urgent first, soonest due within priority" sort.

---

## 3. Universal Attachment Junction Table

### 3.1 Table Definition

```sql
CREATE TABLE task_entities (
    task_id         TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    entity_type     TEXT NOT NULL,
    entity_id       TEXT NOT NULL,
    is_primary      BOOLEAN NOT NULL DEFAULT false,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    PRIMARY KEY (task_id, entity_type, entity_id)
);

CREATE INDEX idx_te_entity ON task_entities (entity_type, entity_id);
CREATE INDEX idx_te_task ON task_entities (task_id);
```

**Rationale:** Same polymorphic pattern as Notes. is_primary at most one per task (enforced application-side). No FK to entity tables — application-level integrity.

---

## 4. Assignee Junction Table

### 4.1 Table Definition

```sql
CREATE TABLE task_user_roles (
    id              TEXT PRIMARY KEY,          -- tur_ prefixed ULID
    task_id         TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    user_id         TEXT NOT NULL,
    role            TEXT NOT NULL DEFAULT 'assignee'
                        CHECK (role IN ('assignee', 'reviewer', 'watcher')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (task_id, user_id, role)
);

CREATE INDEX idx_tur_user ON task_user_roles (user_id, role);
CREATE INDEX idx_tur_task ON task_user_roles (task_id);
```

**Rationale:** UNIQUE per (task, user, role) allows a user to hold multiple roles on the same task (e.g., assignee + reviewer) via separate rows, while preventing duplicate role assignments. CASCADE from task deletion.

---

## 5. Dependency Junction Table

### 5.1 Table Definition

```sql
CREATE TABLE task_dependencies (
    id                  TEXT PRIMARY KEY,        -- dep_ prefixed ULID
    blocking_task_id    TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    blocked_task_id     TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    dependency_type     TEXT NOT NULL DEFAULT 'blocked_by'
                            CHECK (dependency_type IN ('blocked_by')),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (blocking_task_id, blocked_task_id),
    CHECK (blocking_task_id != blocked_task_id)
);

CREATE INDEX idx_dep_blocked ON task_dependencies (blocked_task_id);
CREATE INDEX idx_dep_blocking ON task_dependencies (blocking_task_id);
```

**Rationale:** Self-referential M:M. CHECK prevents self-dependency. UNIQUE prevents duplicate dependencies. Single dependency_type ('blocked_by') keeps semantics simple — extensible later if needed. Bidirectional indexes for "what blocks me" and "what do I block" queries.

---

## 6. Event Sourcing

### 6.1 Tasks Events Table

```sql
CREATE TABLE tasks_events (
    id              TEXT PRIMARY KEY,          -- tev_ prefixed ULID
    entity_id       TEXT NOT NULL,
    event_type      TEXT NOT NULL,
    field_name      TEXT,
    old_value       JSONB,
    new_value       JSONB,
    metadata        JSONB,
    actor_id        TEXT,
    actor_type      TEXT,                      -- 'user', 'system', 'ai', 'sync'
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_tev_entity ON tasks_events (entity_id, created_at);
CREATE INDEX idx_tev_type ON tasks_events (event_type);
```

### 6.2 Event Types

| Event Type | Description |
|---|---|
| `TaskCreated` | New task created |
| `FieldUpdated` | Field value changed (title, status, priority, dates, duration) |
| `DescriptionUpdated` | Description content changed. Metadata has size, not full content. |
| `TaskArchived` | Task archived |
| `TaskUnarchived` | Task restored |
| `AssigneeAdded` | User added with role. Metadata: user_id, role. |
| `AssigneeRemoved` | User removed from role. Metadata: user_id, role. |
| `EntityLinked` | Task linked to entity. Metadata: entity_type, entity_id. |
| `EntityUnlinked` | Task unlinked from entity. |
| `DependencyAdded` | Dependency created. Metadata: blocking/blocked IDs. |
| `DependencyRemoved` | Dependency removed. |
| `RecurrenceGenerated` | New instance created from completed recurring task. Metadata: source_task_id. |

---

## 7. Virtual Schema & Data Sources

### 7.1 Virtual Schema

All Task metadata fields from field registry exposed as virtual columns. `tsk_` prefix enables entity detection. Description content not exposed — use FTS endpoint.

### 7.2 Cross-Entity Query Examples

```sql
-- Overdue tasks assigned to a specific user
SELECT t.title, t.priority, t.due_date
FROM tasks t
JOIN task_user_roles tur ON tur.task_id = t.id
WHERE tur.user_id = $user_id AND tur.role = 'assignee'
  AND t.is_overdue = true AND t.archived_at IS NULL
ORDER BY t.priority_sort, t.due_date;

-- Tasks linked to a contact with open status
SELECT t.title, t.status, t.due_date, t.priority
FROM tasks t
JOIN task_entities te ON te.task_id = t.id
WHERE te.entity_type = 'contacts' AND te.entity_id = $contact_id
  AND t.status_category IN ('not_started', 'active')
  AND t.archived_at IS NULL
ORDER BY t.priority_sort, t.due_date;

-- Task completion rate by assignee this month
SELECT tur.user_id, COUNT(*) FILTER (WHERE t.status_category = 'done') AS completed,
       COUNT(*) AS total
FROM tasks t
JOIN task_user_roles tur ON tur.task_id = t.id AND tur.role = 'assignee'
WHERE t.created_at >= date_trunc('month', NOW())
GROUP BY tur.user_id;
```

### 7.3 Views Integration

- **Grid View:** Sortable columns for title, status, priority, due date, assignees, source.
- **Board View:** Grouped by status_category (4 columns) or individual status (N columns). Kanban drag changes status.
- **Calendar View:** Due dates plotted on month/week/day.
- **Timeline View:** Start date → due date bars. Dependencies as arrows (Phase 4).
- **Traversal columns:** "Assignees" via Task→User, "Linked Entities" via Universal Attachment.

---

## 8. API Design

### 8.1 Record CRUD

| Endpoint | Method | Description |
|---|---|---|
| `/api/v1/tasks` | GET | List tasks (paginated, filterable, sortable) |
| `/api/v1/tasks` | POST | Create task |
| `/api/v1/tasks/{id}` | GET | Get task with subtasks, assignees, entities, dependencies |
| `/api/v1/tasks/{id}` | PATCH | Update task fields |
| `/api/v1/tasks/{id}/archive` | POST | Archive (cascades to children) |
| `/api/v1/tasks/{id}/unarchive` | POST | Unarchive (this task only) |

### 8.2 Subtask Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/api/v1/tasks/{id}/subtasks` | GET | List direct children |
| `/api/v1/tasks/{id}/subtasks` | POST | Create child task |
| `/api/v1/tasks/{id}/tree` | GET | Full subtask tree (recursive CTE) |

### 8.3 Assignee Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/api/v1/tasks/{id}/assignees` | GET | List all users with roles |
| `/api/v1/tasks/{id}/assignees` | POST | Add user with role |
| `/api/v1/tasks/{id}/assignees/{user_id}/{role}` | DELETE | Remove user from role |

### 8.4 Entity Attachment Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/api/v1/tasks/{id}/entities` | GET | List linked entities |
| `/api/v1/tasks/{id}/entities` | POST | Link to entity |
| `/api/v1/tasks/{id}/entities/{type}/{entity_id}` | DELETE | Unlink from entity |

### 8.5 Dependency Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/api/v1/tasks/{id}/dependencies` | GET | List blocking and blocked tasks |
| `/api/v1/tasks/{id}/dependencies` | POST | Add dependency (with cycle check) |
| `/api/v1/tasks/{id}/dependencies/{dep_id}` | DELETE | Remove dependency |

### 8.6 Convenience Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/api/v1/tasks/my` | GET | Tasks assigned to current user |
| `/api/v1/tasks/overdue` | GET | All overdue tasks |
| `/api/v1/tasks/search` | GET | FTS with ranked results |

---

## 9. Decisions to Be Added by Claude Code

- **Subtask sort_order:** Whether to add a manual ordering field for drag-and-drop.
- **Board View default columns:** Status categories vs. individual statuses.
- **Overdue detection job frequency:** Every 15 minutes, every hour, or event-driven.
- **Description content in event sourcing:** Full delta vs. size-only metadata in DescriptionUpdated events.
- **Reminder notification contract:** Minimal interface for due date reminders pending Notifications PRD.
