# Project Entity — TDD

**Version:** 1.0
**Last Updated:** 2026-02-23
**Status:** Draft
**Scope:** Entity
**Parent Document:** [project-entity-base-prd.md]
**Product TDD:** [product-tdd.md]

---

## 1. Overview

The Project entity requires entity-specific technical decisions beyond the Product TDD's global defaults. Key areas include: the read model table DDL with denormalized counts, four junction tables for system Relation Types, event sourcing with 16 event types, virtual schema, and API design.

---

## 2. Projects Read Model Table

### 2.1 Table Definition

```sql
CREATE TABLE projects (
    id                  TEXT PRIMARY KEY,        -- prj_ prefixed ULID
    tenant_id           TEXT NOT NULL,
    name                TEXT NOT NULL,
    description         TEXT,
    user_status         TEXT,                    -- User-defined select value
    owner_id            TEXT,                    -- FK → platform.users
    parent_project_id   TEXT REFERENCES projects(id),
    last_activity_at    TIMESTAMPTZ,

    -- Denormalized counts (managed by entity aggregation behavior)
    conversation_count  INTEGER NOT NULL DEFAULT 0,
    contact_count       INTEGER NOT NULL DEFAULT 0,
    company_count       INTEGER NOT NULL DEFAULT 0,
    event_count         INTEGER NOT NULL DEFAULT 0,
    note_count          INTEGER NOT NULL DEFAULT 0,
    sub_project_count   INTEGER NOT NULL DEFAULT 0,

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
CREATE INDEX idx_prj_owner ON projects (owner_id) WHERE owner_id IS NOT NULL;
CREATE INDEX idx_prj_parent ON projects (parent_project_id) WHERE parent_project_id IS NOT NULL;
CREATE INDEX idx_prj_user_status ON projects (user_status) WHERE user_status IS NOT NULL;
CREATE INDEX idx_prj_last_activity ON projects (last_activity_at DESC);
CREATE INDEX idx_prj_archived ON projects (archived_at) WHERE archived_at IS NULL;
CREATE INDEX idx_prj_tenant ON projects (tenant_id);
```

**Rationale:** Partial indexes on nullable columns (owner, parent, status) reduce index size. Last activity descending for "most recently active" sort. Archived partial index for active-only queries.

---

## 3. Junction Tables

### 3.1 Project ↔ Conversation

```sql
CREATE TABLE project_conversations (
    project_id      TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by      TEXT,

    PRIMARY KEY (project_id, conversation_id)
);

CREATE INDEX idx_prc_project ON project_conversations (project_id);
CREATE INDEX idx_prc_conversation ON project_conversations (conversation_id);
```

**Rationale:** No metadata columns — simple link. Composite PK prevents duplicates. Bidirectional CASCADE removes link when either side deleted.

### 3.2 Project ↔ Contact

```sql
CREATE TABLE project_contacts (
    id              TEXT PRIMARY KEY,          -- pcn_ prefixed ULID
    project_id      TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    contact_id      TEXT NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
    role            TEXT,                      -- "stakeholder", "decision-maker", "vendor", etc.
    notes           TEXT,                      -- Context about involvement
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by      TEXT,

    UNIQUE (project_id, contact_id)
);

CREATE INDEX idx_pcn_project ON project_contacts (project_id);
CREATE INDEX idx_pcn_contact ON project_contacts (contact_id);
```

**Rationale:** Separate PK (id) because metadata columns (role, notes) require update capability. UNIQUE prevents duplicate links. Role and notes enable user-curated stakeholder context.

### 3.3 Project ↔ Company

```sql
CREATE TABLE project_companies (
    id              TEXT PRIMARY KEY,          -- pco_ prefixed ULID
    project_id      TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    company_id      TEXT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    role            TEXT,                      -- "client", "vendor", "partner", etc.
    notes           TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by      TEXT,

    UNIQUE (project_id, company_id)
);

CREATE INDEX idx_pco_project ON project_companies (project_id);
CREATE INDEX idx_pco_company ON project_companies (company_id);
```

### 3.4 Project ↔ Event

```sql
CREATE TABLE project_events (
    id              TEXT PRIMARY KEY,          -- pev_ prefixed ULID
    project_id      TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    event_id        TEXT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by      TEXT,

    UNIQUE (project_id, event_id)
);

CREATE INDEX idx_pev_project ON project_events (project_id);
CREATE INDEX idx_pev_event ON project_events (event_id);
```

### 3.5 Notes & Tasks Attachment

Notes and Tasks attach to Projects through their own Universal Attachment junction tables (note_entities and task_entities). No project-specific junction tables needed — the polymorphic entity_type + entity_id columns in those tables handle the link with entity_type = 'projects'.

---

## 4. Event Sourcing

### 4.1 Projects Events Table

```sql
CREATE TABLE projects_events (
    id              TEXT PRIMARY KEY,
    entity_id       TEXT NOT NULL,
    event_type      TEXT NOT NULL,
    field_name      TEXT,
    old_value       JSONB,
    new_value       JSONB,
    metadata        JSONB,
    actor_id        TEXT,
    actor_type      TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_prjev_entity ON projects_events (entity_id, created_at);
CREATE INDEX idx_prjev_type ON projects_events (event_type);
```

### 4.2 Event Types

| Event Type | Description |
|---|---|
| `ProjectCreated` | New project created |
| `FieldUpdated` | Field changed (name, description, owner, etc.) |
| `StatusChanged` | user_status transitioned. Old/new values. |
| `ConversationLinked` | Conversation associated. Metadata: conversation_id. |
| `ConversationUnlinked` | Conversation removed. |
| `ContactLinked` | Contact associated. Metadata: contact_id, role. |
| `ContactUnlinked` | Contact removed. |
| `CompanyLinked` | Company associated. Metadata: company_id, role. |
| `CompanyUnlinked` | Company removed. |
| `EventLinked` | Event associated. Metadata: event_id. |
| `EventUnlinked` | Event removed. |
| `NoteAttached` | Note attached. Metadata: note_id. |
| `NoteDetached` | Note removed. |
| `SubProjectAdded` | Child project created or reparented under this project. |
| `SubProjectRemoved` | Child project reparented away. |
| `ProjectArchived` | Soft-deleted. |
| `ProjectUnarchived` | Restored. |

---

## 5. Virtual Schema & Data Sources

### 5.1 Virtual Schema

All Project metadata fields from field registry exposed as virtual columns. `prj_` prefix enables entity detection. Denormalized counts queryable for filtering and sorting.

### 5.2 Cross-Entity Query Examples

```sql
-- All conversations in a project
SELECT c.id, c.subject, c.is_aggregate, c.last_activity_at
FROM conversations c
JOIN project_conversations pc ON c.id = pc.conversation_id
WHERE pc.project_id = $project_id
ORDER BY c.last_activity_at DESC;

-- Explicit contacts + derived participants from conversations
SELECT con.id, con.display_name, pc.role, 'explicit' AS source
FROM project_contacts pc
JOIN contacts con ON con.id = pc.contact_id
WHERE pc.project_id = $project_id

UNION

SELECT DISTINCT con.id, con.display_name, NULL AS role, 'derived' AS source
FROM project_conversations prc
JOIN communications comm ON comm.conversation_id = prc.conversation_id
JOIN communication_participants cp ON cp.communication_id = comm.id
JOIN contacts con ON con.id = cp.contact_id
WHERE prc.project_id = $project_id
  AND con.id NOT IN (
      SELECT contact_id FROM project_contacts WHERE project_id = $project_id
  );

-- Events linked to a project
SELECT e.title, e.start_time, e.end_time, e.event_type
FROM project_events pe
JOIN events e ON e.id = pe.event_id
WHERE pe.project_id = $project_id
ORDER BY e.start_time DESC;

-- Sub-project tree (recursive)
WITH RECURSIVE project_tree AS (
    SELECT id, name, parent_project_id, 0 AS depth
    FROM projects WHERE id = $root_project_id AND archived_at IS NULL
    UNION ALL
    SELECT p.id, p.name, p.parent_project_id, pt.depth + 1
    FROM projects p
    JOIN project_tree pt ON p.parent_project_id = pt.id
    WHERE p.archived_at IS NULL
)
SELECT * FROM project_tree ORDER BY depth, name;
```

---

## 6. API Design

### 6.1 Project CRUD

| Endpoint | Method | Description |
|---|---|---|
| `/api/v1/projects` | GET | List projects (paginated, filterable by status, owner) |
| `/api/v1/projects` | POST | Create project |
| `/api/v1/projects/{id}` | GET | Get project with counts and linked entity previews |
| `/api/v1/projects/{id}` | PATCH | Update fields |
| `/api/v1/projects/{id}/archive` | POST | Archive (cascades to sub-projects) |
| `/api/v1/projects/{id}/unarchive` | POST | Unarchive (this project only) |
| `/api/v1/projects/{id}/history` | GET | Event history |

### 6.2 Sub-Project Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/api/v1/projects/{id}/sub-projects` | GET | List child projects |
| `/api/v1/projects/{id}/sub-projects` | POST | Create sub-project |
| `/api/v1/projects/{id}/tree` | GET | Full sub-project tree (recursive) |

### 6.3 Relation Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/api/v1/projects/{id}/conversations` | GET | List linked conversations |
| `/api/v1/projects/{id}/conversations` | POST | Link conversation |
| `/api/v1/projects/{id}/conversations/{cvr_id}` | DELETE | Unlink conversation |
| `/api/v1/projects/{id}/contacts` | GET | List linked contacts (with role/notes) |
| `/api/v1/projects/{id}/contacts` | POST | Link contact (with optional role/notes) |
| `/api/v1/projects/{id}/contacts/{con_id}` | PATCH | Update role/notes |
| `/api/v1/projects/{id}/contacts/{con_id}` | DELETE | Unlink contact |
| `/api/v1/projects/{id}/companies` | GET | List linked companies |
| `/api/v1/projects/{id}/companies` | POST | Link company |
| `/api/v1/projects/{id}/companies/{cmp_id}` | DELETE | Unlink company |
| `/api/v1/projects/{id}/events` | GET | List linked events |
| `/api/v1/projects/{id}/events` | POST | Link event |
| `/api/v1/projects/{id}/events/{evt_id}` | DELETE | Unlink event |

### 6.4 Status Workflow

| Endpoint | Method | Description |
|---|---|---|
| `/api/v1/projects/{id}/status` | PATCH | Update user_status (validates transitions if defined) |
| `/api/v1/projects/status-config` | GET | Get status options and transitions |
| `/api/v1/projects/status-config` | PUT | Update status configuration |

---

## 7. Decisions to Be Added by Claude Code

- **Derived participant caching:** Whether to cache derived participants or compute on demand.
- **Last activity computation scope:** Which linked entity events update last_activity_at (all vs. subset).
- **Sub-project count recursive vs. direct:** Whether sub_project_count includes all descendants or only direct children.
- **Status transition storage:** Whether to store transitions in Select field metadata or a separate configuration table.
- **Cascade archive depth limit:** Whether to impose a safety limit on recursive cascade depth.
