# Communication Entity — TDD

**Version:** 1.0
**Last Updated:** 2026-02-23
**Status:** Draft
**Scope:** Entity
**Parent Document:** [communication-entity-base-prd.md]
**Product TDD:** [product-tdd.md]

---

## 1. Overview

The Communication entity requires entity-specific technical decisions beyond the Product TDD's global defaults. Key areas include: the read model table DDL with indexes, the summary revisions table, event sourcing, the attachment model, the sync audit trail, virtual schema mapping, full-text search implementation, and storage estimates.

This is a living document. Decisions are recorded here as they are made.

---

## 2. Communications Read Model Table

### 2.1 Table Definition

**Decision:** The `communications` table is the dedicated read model for the Communication system object type. Core fields are `is_system = true`.

```sql
-- Within tenant schema: tenant_abc.communications
CREATE TABLE communications (
    -- Universal fields
    id              TEXT PRIMARY KEY,        -- com_01HX8A...
    tenant_id       TEXT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by      TEXT REFERENCES platform.users(id),
    updated_by      TEXT REFERENCES platform.users(id),
    archived_at     TIMESTAMPTZ,

    -- Core system fields
    channel         TEXT NOT NULL,
    direction       TEXT NOT NULL,
    timestamp       TIMESTAMPTZ NOT NULL,
    subject         TEXT,
    body_preview    TEXT,
    content_raw     TEXT,
    content_html    TEXT,
    content_clean   TEXT,
    source          TEXT NOT NULL,
    provider_account_id TEXT,
    provider_message_id TEXT,
    provider_thread_id  TEXT,
    conversation_id TEXT,
    triage_result   TEXT,
    triage_reason   TEXT,
    duration_seconds INTEGER,
    has_attachments BOOLEAN DEFAULT FALSE,
    attachment_count INTEGER DEFAULT 0,

    -- Behavior-managed summary fields
    summary_json    JSONB,
    summary_html    TEXT,
    summary_text    TEXT,
    summary_source  TEXT,
    current_summary_revision_id TEXT,
    summary_revision_count INTEGER DEFAULT 0,

    -- Deduplication constraint
    CONSTRAINT uq_provider_message UNIQUE (provider_account_id, provider_message_id)
);
```

### 2.2 Indexes

```sql
CREATE INDEX idx_comm_timestamp ON communications (timestamp DESC);
CREATE INDEX idx_comm_conversation ON communications (conversation_id)
    WHERE conversation_id IS NOT NULL;
CREATE INDEX idx_comm_channel ON communications (channel);
CREATE INDEX idx_comm_triage ON communications (triage_result)
    WHERE triage_result IS NOT NULL;
CREATE INDEX idx_comm_provider_thread ON communications (provider_account_id, provider_thread_id)
    WHERE provider_thread_id IS NOT NULL;
CREATE INDEX idx_comm_archived ON communications (archived_at)
    WHERE archived_at IS NULL;
CREATE INDEX idx_comm_summary_fts ON communications
    USING GIN (to_tsvector('english', COALESCE(summary_text, '')));
```

**Rationale:** Partial indexes (WHERE clauses) reduce index size for sparse columns. The timestamp DESC index supports the default sort order. The provider_thread index enables fast conversation formation lookups.

---

## 3. Summary Revisions Table

### 3.1 Table Definition

**Decision:** Append-only, full-snapshot revision history for Published Summaries. Mirrors the Notes revision model.

```sql
CREATE TABLE communication_summary_revisions (
    id                  TEXT PRIMARY KEY,          -- svr_ prefixed ULID
    communication_id    TEXT NOT NULL REFERENCES communications(id) ON DELETE CASCADE,
    revision_number     INTEGER NOT NULL,
    summary_json        JSONB NOT NULL,
    summary_html        TEXT NOT NULL,
    summary_text        TEXT NOT NULL,
    summary_source      TEXT NOT NULL,             -- 'ai_generated', 'user_authored', 'pass_through'
    revised_by          TEXT,                      -- FK → platform.users (NULL for AI)
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (communication_id, revision_number)
);

CREATE INDEX idx_svr_communication ON communication_summary_revisions
    (communication_id, revision_number DESC);
```

**Rationale:** Full snapshots (not diffs) simplify temporal reconstruction — any revision can be rendered independently. The UNIQUE constraint on (communication_id, revision_number) prevents revision number collisions. CASCADE delete ensures revisions are cleaned up with their parent communication.

---

## 4. Event Sourcing

### 4.1 Communications Events Table

**Decision:** Per Custom Objects PRD, the Communication entity has a dedicated event table.

```sql
CREATE TABLE communications_events (
    id              TEXT PRIMARY KEY,        -- evt_01HX8B...
    entity_id       TEXT NOT NULL,           -- com_01HX8A...
    tenant_id       TEXT NOT NULL,
    event_type      TEXT NOT NULL,
    field_slug      TEXT,
    old_value       TEXT,                    -- JSON-encoded
    new_value       TEXT,                    -- JSON-encoded
    changed_by      TEXT,
    changed_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata        JSONB
);

CREATE INDEX idx_comm_events_entity ON communications_events (entity_id, changed_at);
CREATE INDEX idx_comm_events_type ON communications_events (event_type);
```

### 4.2 Event Types

| Event Type                | Trigger                                                     | Description                                |
| ------------------------- | ----------------------------------------------------------- | ------------------------------------------ |
| `created`                 | New communication synced or manually entered                | Full record snapshot in new_value          |
| `field_updated`           | Any field change                                            | Old and new values for the specific field  |
| `conversation_assigned`   | Communication assigned to a conversation                    | conversation_id change                     |
| `conversation_unassigned` | Communication removed from a conversation                   | conversation_id set to NULL                |
| `triage_overridden`       | User overrides a triage decision                            | triage_result change                       |
| `participant_added`       | New participant linked                                      | Participant details in metadata            |
| `participant_resolved`    | Unknown participant identified                              | Contact resolution details in metadata     |
| `archived`                | Communication soft-deleted                                  |                                            |
| `unarchived`              | Communication restored                                      |                                            |
| `summary_generated`       | Summary generation produces initial or re-generated summary | Summary revision ID and source in metadata |
| `summary_revised`         | User edits a summary                                        | New revision ID in metadata                |

### 4.3 Sync Operation Events

Sync operations are logged separately from entity events for operational monitoring. The entity-level `created` event on each Communication includes sync metadata (sync_id, provider_account_id) in its `metadata` JSONB, linking the communication to the sync operation that captured it.

---

## 5. Attachment Model

### 5.1 Table Definition

**Decision:** Attachments are behavior-managed records, not a separate object type.

| Column             | Type        | Constraints                                           | Description                                     |
| ------------------ | ----------- | ----------------------------------------------------- | ----------------------------------------------- |
| `id`               | TEXT        | **PK**                                                | Prefixed ULID: `att_` prefix                    |
| `communication_id` | TEXT        | NOT NULL, FK → `communications(id)` ON DELETE CASCADE | Parent communication                            |
| `filename`         | TEXT        | NOT NULL                                              | Original filename                               |
| `mime_type`        | TEXT        | NOT NULL                                              | MIME type                                       |
| `size_bytes`       | BIGINT      |                                                       | File size                                       |
| `storage_key`      | TEXT        |                                                       | Reference in object storage (S3/MinIO)          |
| `source`           | TEXT        |                                                       | `synced`, `uploaded`, `recording`, `transcript` |
| `created_at`       | TIMESTAMPTZ | NOT NULL                                              |                                                 |

**Indexes:** `(communication_id)` for listing attachments per communication.

### 5.2 Storage Strategy

| Attachment Type       | Phase 1                                  | Phase 2+                  |
| --------------------- | ---------------------------------------- | ------------------------- |
| Email attachments     | On-demand download from provider         | Object storage (S3/MinIO) |
| Call/video recordings | Object storage                           | Object storage            |
| User-uploaded files   | Object storage                           | Object storage            |
| Transcripts           | Stored as content_clean on Communication | Same                      |

**Rationale:** On-demand download for email attachments reduces initial sync time and storage cost. Provider access is retained through OAuth tokens. Migration to object storage planned for Phase 2+ when provider-independent access is needed.

### 5.3 Recording-Transcript Relationship

For recorded calls and video meetings, the transcript becomes the `content_clean` (for AI and search), while the original recording is an attachment (for playback and verification).

---

## 6. Sync Audit Trail

### 6.1 Table Definition

**Decision:** Every sync operation is logged for operational monitoring.

| Column                  | Type        | Description                               |
| ----------------------- | ----------- | ----------------------------------------- |
| `sync_id`               | TEXT        | Unique identifier for this sync operation |
| `provider_account_id`   | TEXT        | Which account was synced                  |
| `sync_type`             | TEXT        | `initial`, `incremental`, `manual`        |
| `started_at`            | TIMESTAMPTZ |                                           |
| `completed_at`          | TIMESTAMPTZ |                                           |
| `messages_fetched`      | INTEGER     | Total messages from provider              |
| `messages_stored`       | INTEGER     | New Communications created                |
| `messages_skipped`      | INTEGER     | Duplicates or filtered                    |
| `conversations_created` | INTEGER     | New conversations formed                  |
| `conversations_updated` | INTEGER     | Existing conversations updated            |
| `cursor_before`         | TEXT        | Sync position before                      |
| `cursor_after`          | TEXT        | Sync position after                       |
| `status`                | TEXT        | `success`, `partial_failure`, `failed`    |
| `error_details`         | TEXT        | Error information if applicable           |

**Retention:** 90 days by default (configurable).

---

## 7. Virtual Schema & Data Sources

### 7.1 Communication Virtual Schema Table

**Decision:** Per Data Sources PRD, the Communication field registry generates a virtual schema table for SQL queries.

```sql
SELECT
    c.id, c.channel, c.direction, c.timestamp, c.subject,
    c.body_preview, c.content_clean, c.source, c.conversation_id,
    c.triage_result, c.duration_seconds, c.has_attachments,
    c.created_at, c.updated_at
FROM communications c
WHERE c.archived_at IS NULL;
```

### 7.2 Relation Traversal

Data Source queries can traverse the Communication Participants relation:

```sql
SELECT c.timestamp, c.channel, c.subject, c.body_preview
FROM communications c
JOIN communication_participants cp ON cp.communication_id = c.id
WHERE cp.contact_id = 'con_01HX7...'
ORDER BY c.timestamp DESC;
```

### 7.3 Entity ID Convention

The `com_` prefix enables automatic entity type detection in Data Source queries, search results, and deep links.

---

## 8. Full-Text Search

### 8.1 Implementation

**Decision:** PostgreSQL native `tsvector`/`tsquery` with weighted fields.

```sql
ALTER TABLE communications ADD COLUMN search_vector tsvector
    GENERATED ALWAYS AS (
        setweight(to_tsvector('english', COALESCE(subject, '')), 'A') ||
        setweight(to_tsvector('english', COALESCE(content_clean, '')), 'B')
    ) STORED;

CREATE INDEX idx_comm_search ON communications USING GIN (search_vector);
```

**Rationale:** Subject text weighted higher ('A') than body content ('B') for relevance ranking. Generated column means indexing is automatic and synchronous — no async lag. Communications are re-indexed automatically when content_clean is regenerated.

---

## 9. Storage Estimates

| Data Type                    | Per Communication | 10,000 Communications |
| ---------------------------- | ----------------- | --------------------- |
| Record fields + metadata     | ~1 KB avg         | ~10 MB                |
| content_clean (text)         | ~2 KB avg         | ~20 MB                |
| content_html (email only)    | ~8 KB avg         | ~80 MB                |
| Event history                | ~0.5 KB per event | ~5 MB (10K events)    |
| Audio recordings (if stored) | ~1 MB/min         | Highly variable       |

---

## 10. Decisions to Be Added by Claude Code

The following areas will require technical decisions during implementation:

- **body_preview generation:** Truncation strategy for the 200-character preview (word boundary vs. hard cut, HTML entity handling).
- **has_attachments / attachment_count sync:** Application trigger vs. database trigger for keeping denormalized counts in sync.
- **Summary FTS vs. content FTS:** Whether to create a combined FTS index across summary_text and content_clean, or keep them separate for scoped search.
- **Provider thread ID normalization:** Whether different providers' thread IDs need normalization for cross-provider conversation matching.
- **Archive cascade to conversation:** When archiving a communication, whether and how conversation metadata (message count, last activity) is recomputed.
- **Migration from PoC:** How existing SQLite data (UUID v4 IDs, no event sourcing, no prefixed ULIDs) migrates to the target schema.
