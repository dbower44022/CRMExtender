# Conversation Entity — TDD

**Version:** 1.0
**Last Updated:** 2026-02-23
**Status:** Draft
**Scope:** Entity
**Parent Document:** [conversation-entity-base-prd.md]
**Product TDD:** [product-tdd.md]

---

## 1. Overview

The Conversation entity requires entity-specific technical decisions beyond the Product TDD's global defaults. Key areas include: the read model table DDL with indexes, the conversation_members junction table, the segment data model, event sourcing, virtual schema mapping, and API design.

---

## 2. Conversations Read Model Table

### 2.1 Table Definition

```sql
-- Within tenant schema: tenant_abc.conversations
CREATE TABLE conversations (
    -- Universal fields
    id                  TEXT PRIMARY KEY,        -- cvr_01HX8A...
    tenant_id           TEXT NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by          TEXT REFERENCES platform.users(id),
    updated_by          TEXT REFERENCES platform.users(id),
    archived_at         TIMESTAMPTZ,

    -- Core system fields
    subject             TEXT,
    is_aggregate        BOOLEAN NOT NULL DEFAULT FALSE,
    description         TEXT,
    system_status       TEXT NOT NULL DEFAULT 'active',
    ai_status           TEXT,
    ai_summary          TEXT,
    ai_action_items     TEXT,                   -- JSON
    ai_key_topics       TEXT,                   -- JSON
    ai_confidence       NUMERIC(3,2),
    ai_last_processed_at TIMESTAMPTZ,
    communication_count INTEGER DEFAULT 0,
    channel_breakdown   TEXT,                   -- JSON
    first_activity_at   TIMESTAMPTZ,
    last_activity_at    TIMESTAMPTZ,
    stale_after_days    INTEGER DEFAULT 14,
    closed_after_days   INTEGER DEFAULT 30
);
```

### 2.2 Indexes

```sql
CREATE INDEX idx_cvr_aggregate ON conversations (is_aggregate)
    WHERE is_aggregate = TRUE;
CREATE INDEX idx_cvr_system_status ON conversations (system_status);
CREATE INDEX idx_cvr_ai_status ON conversations (ai_status)
    WHERE ai_status IS NOT NULL;
CREATE INDEX idx_cvr_last_activity ON conversations (last_activity_at DESC);
CREATE INDEX idx_cvr_archived ON conversations (archived_at)
    WHERE archived_at IS NULL;
```

**Rationale:** Partial indexes on is_aggregate and ai_status reduce index size. The last_activity DESC index supports the default sort order.

---

## 3. Conversation Members Junction Table

### 3.1 Table Definition

**Decision:** Many-to-many membership between aggregate and child Conversations.

```sql
CREATE TABLE conversation_members (
    parent_conversation_id  TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    child_conversation_id   TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    added_by                TEXT REFERENCES platform.users(id),
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    PRIMARY KEY (parent_conversation_id, child_conversation_id),
    CHECK (parent_conversation_id != child_conversation_id)
);

CREATE INDEX idx_cvr_members_child ON conversation_members (child_conversation_id);
CREATE INDEX idx_cvr_members_parent ON conversation_members (parent_conversation_id);
```

**Rationale:** Composite PK prevents duplicate membership. CHECK constraint prevents self-membership. CASCADE delete cleans up when either conversation is deleted. Bidirectional indexes support both "children of X" and "parents of X" queries. Acyclic enforcement is application-level (ancestry walk before insert).

---

## 4. Segment Data Model

### 4.1 Table Definition

**Decision:** Segments are behavior-managed records for cross-conversation content references.

```sql
CREATE TABLE communication_segments (
    id                      TEXT PRIMARY KEY,       -- seg_ prefixed ULID
    communication_id        TEXT NOT NULL REFERENCES communications(id) ON DELETE CASCADE,
    source_conversation_id  TEXT NOT NULL REFERENCES conversations(id),
    target_conversation_id  TEXT NOT NULL REFERENCES conversations(id),
    content_start           INTEGER NOT NULL,       -- Character offset start
    content_end             INTEGER NOT NULL,       -- Character offset end
    selected_text           TEXT NOT NULL,           -- Denormalized for display
    created_by              TEXT REFERENCES platform.users(id),
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_seg_communication ON communication_segments (communication_id);
CREATE INDEX idx_seg_target ON communication_segments (target_conversation_id);
CREATE INDEX idx_seg_source ON communication_segments (source_conversation_id);
```

**Rationale:** Denormalized `selected_text` avoids re-extracting from content on every render. Character offsets enable highlighting in the source communication. CASCADE from communication ensures segments are cleaned up when the source is deleted.

---

## 5. Event Sourcing

### 5.1 Conversations Events Table

```sql
CREATE TABLE conversations_events (
    id              TEXT PRIMARY KEY,        -- evt_01HX8B...
    entity_id       TEXT NOT NULL,           -- cvr_01HX8A...
    tenant_id       TEXT NOT NULL,
    event_type      TEXT NOT NULL,
    field_slug      TEXT,
    old_value       TEXT,                    -- JSON-encoded
    new_value       TEXT,                    -- JSON-encoded
    changed_by      TEXT,
    changed_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata        JSONB
);

CREATE INDEX idx_cvr_events_entity ON conversations_events (entity_id, changed_at);
CREATE INDEX idx_cvr_events_type ON conversations_events (event_type);
```

### 5.2 Event Types

| Event Type | Trigger | Description |
|---|---|---|
| `created` | New conversation formed (auto or manual) | Full record snapshot in new_value |
| `field_updated` | Any field change | Old and new values for specific field |
| `communication_added` | Communication assigned to this conversation | Communication ID in metadata |
| `communication_removed` | Communication unassigned | Communication ID in metadata |
| `member_added` | Child Conversation added to aggregate | Parent and child IDs in metadata |
| `member_removed` | Child Conversation removed from aggregate | Parent and child IDs in metadata |
| `ai_processed` | AI generated summary/status/action items | AI output snapshot in metadata |
| `status_transition` | system_status changed | Old and new status |
| `merged` | Two conversations merged | Source conversation ID in metadata |
| `archived` | Soft-delete | |
| `unarchived` | Restore | |

---

## 6. Virtual Schema & Data Sources

### 6.1 Virtual Schema Table

Per Data Sources PRD, the Conversation field registry generates a virtual schema:

```sql
SELECT
    c.id, c.subject, c.is_aggregate, c.description,
    c.system_status, c.ai_status, c.ai_summary,
    c.ai_action_items, c.ai_key_topics, c.ai_confidence,
    c.communication_count, c.channel_breakdown,
    c.first_activity_at, c.last_activity_at,
    c.created_at, c.updated_at
FROM conversations c
WHERE c.archived_at IS NULL;
```

### 6.2 Cross-Entity Query Examples

```sql
-- All conversations associated with a specific project
SELECT c.subject, c.ai_status, c.ai_summary, c.is_aggregate
FROM conversations c
JOIN conversation_projects cp ON c.id = cp.conversation_id
WHERE cp.project_id = 'prj_01HX7...'
ORDER BY c.last_activity_at DESC;

-- All child conversations within an aggregate
SELECT child.subject, child.ai_status, child.last_activity_at
FROM conversations child
JOIN conversation_members cm ON child.id = cm.child_conversation_id
WHERE cm.parent_conversation_id = 'cvr_01HX7...'
ORDER BY child.last_activity_at DESC;

-- Derived participant list for a conversation
SELECT DISTINCT cp.contact_id, con.display_name
FROM communications c
JOIN communication_participants cp ON cp.communication_id = c.id
JOIN contacts con ON con.id = cp.contact_id
WHERE c.conversation_id = 'cvr_01HX8A...'
  AND c.archived_at IS NULL;

-- All communications in a project's conversations
SELECT comm.timestamp, comm.channel, comm.subject, comm.body_preview
FROM communications comm
JOIN conversations c ON comm.conversation_id = c.id
JOIN conversation_projects cp ON c.id = cp.conversation_id
WHERE cp.project_id = 'prj_01HX7...'
ORDER BY comm.timestamp DESC;
```

---

## 7. API Design

### 7.1 Conversation CRUD API

| Endpoint | Method | Description |
|---|---|---|
| `/api/v1/conversations` | GET | List conversations (paginated, filterable, sortable) |
| `/api/v1/conversations` | POST | Create a conversation |
| `/api/v1/conversations/{id}` | GET | Get conversation with communications and participants |
| `/api/v1/conversations/{id}` | PATCH | Update conversation fields |
| `/api/v1/conversations/{id}/archive` | POST | Archive a conversation |
| `/api/v1/conversations/{id}/history` | GET | Get event history |

### 7.2 Conversation Intelligence API

| Endpoint | Method | Description |
|---|---|---|
| `/api/v1/conversations/{id}/summarize` | POST | Trigger AI summarization refresh |
| `/api/v1/conversations/{id}/communications` | GET | List communications in chronological timeline |
| `/api/v1/conversations/{id}/participants` | GET | Derived participant list |
| `/api/v1/conversations/{id}/segments` | GET | List segments referencing this conversation |

### 7.3 Conversation Membership API

| Endpoint | Method | Description |
|---|---|---|
| `/api/v1/conversations/{id}/members` | GET | List child Conversations (aggregate only) |
| `/api/v1/conversations/{id}/members` | POST | Add child to aggregate (acyclic check) |
| `/api/v1/conversations/{id}/members/{child_id}` | DELETE | Remove child from aggregate |
| `/api/v1/conversations/{id}/parents` | GET | List aggregates this conversation belongs to |

### 7.4 Conversation Entity Association API

| Endpoint | Method | Description |
|---|---|---|
| `/api/v1/conversations/{id}/relations` | GET | List all entity associations |
| `/api/v1/conversations/{id}/relations/{slug}` | GET | List associations for a specific Relation Type |
| `/api/v1/conversations/{id}/relations/{slug}` | POST | Add an entity association |
| `/api/v1/conversations/{id}/relations/{slug}/{target_id}` | DELETE | Remove an entity association |

### 7.5 Review Workflow API

| Endpoint | Method | Description |
|---|---|---|
| `/api/v1/review/pending` | GET | Get pending items (unassigned + low confidence) |
| `/api/v1/review/assign` | POST | Batch assign communications to conversations |
| `/api/v1/review/stats` | GET | Get review statistics (pending count, correction rate) |

---

## 8. Decisions to Be Added by Claude Code

- **Denormalized count update strategy:** Application-level cascade vs. database trigger for aggregate roll-up computation.
- **Acyclic check performance:** For deeply nested aggregates, whether to cache ancestry or walk on every insert.
- **AI summary fan-out batching:** Whether to batch fan-out re-summarization or process immediately on child change.
- **system_status transition mechanism:** Scheduled job vs. on-access lazy evaluation for stale/closed detection.
- **Segment offset stability:** How character offsets are handled when content_clean is re-processed (offsets may shift).
- **conversation_members vs. Relation Type:** Whether to migrate the junction table to a standard Relation Type in a future refactor.
