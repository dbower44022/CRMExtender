# Note Entity — TDD

**Version:** 1.0
**Last Updated:** 2026-02-23
**Status:** Draft
**Scope:** Entity
**Parent Document:** [note-entity-base-prd.md]
**Product TDD:** [product-tdd.md]

---

## 1. Overview

The Note entity requires entity-specific technical decisions beyond the Product TDD's global defaults. Key areas include: the read model table DDL with FTS generated column, universal attachment junction table, revision history table, attachment and mention tables, event sourcing with the content_revised pattern, virtual schema, and API design.

---

## 2. Notes Read Model Table

### 2.1 Table Definition

```sql
CREATE TABLE notes (
    id                  TEXT PRIMARY KEY,        -- not_ prefixed ULID
    tenant_id           TEXT NOT NULL,
    title               TEXT,                    -- Optional; NULL shows content preview
    visibility          TEXT NOT NULL DEFAULT 'private'
                            CHECK (visibility IN ('private', 'shared')),

    -- Behavior-managed content (not in field registry)
    content_json        JSONB NOT NULL,          -- Editor-native document format
    content_html        TEXT NOT NULL,           -- Pre-rendered, sanitized HTML
    content_text        TEXT NOT NULL DEFAULT '', -- Plain text for FTS and previews

    -- Revision tracking
    current_revision_id TEXT,
    revision_count      INTEGER NOT NULL DEFAULT 1,

    -- Full-text search (stored generated column)
    search_vector       TSVECTOR GENERATED ALWAYS AS (
        setweight(to_tsvector('english', coalesce(title, '')), 'A') ||
        setweight(to_tsvector('english', coalesce(content_text, '')), 'B')
    ) STORED,

    -- Universal fields
    created_by          TEXT NOT NULL,
    updated_by          TEXT NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    archived_at         TIMESTAMPTZ
);
```

### 2.2 Indexes

```sql
CREATE INDEX idx_notes_search ON notes USING GIN (search_vector);
CREATE INDEX idx_notes_visibility ON notes (visibility, created_by);
CREATE INDEX idx_notes_archived ON notes (archived_at) WHERE archived_at IS NULL;
CREATE INDEX idx_notes_current_rev ON notes (current_revision_id);
```

**Rationale:** GIN index for tsvector FTS. Composite visibility + created_by supports the common "private notes for current user OR shared notes" query. Partial archived index for active-only queries.

---

## 3. Universal Attachment Junction Table

### 3.1 Table Definition

```sql
CREATE TABLE note_entities (
    note_id         TEXT NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
    entity_type     TEXT NOT NULL,             -- Object type slug
    entity_id       TEXT NOT NULL,             -- Prefixed ULID of linked entity
    is_pinned       BOOLEAN NOT NULL DEFAULT false,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    PRIMARY KEY (note_id, entity_type, entity_id)
);

CREATE INDEX idx_ne_entity ON note_entities (entity_type, entity_id);
CREATE INDEX idx_ne_note ON note_entities (note_id);
CREATE INDEX idx_ne_pinned ON note_entities (entity_type, entity_id, is_pinned DESC);
```

**Rationale:** Composite PK prevents duplicate links. Polymorphic target via entity_type + entity_id (no database FK — application-level integrity). Pinned index supports "pinned first" sort on entity detail pages.

---

## 4. Revision History Table

### 4.1 Table Definition

```sql
CREATE TABLE note_revisions (
    id              TEXT PRIMARY KEY,          -- rev_ prefixed ULID
    note_id         TEXT NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
    revision_number INTEGER NOT NULL,
    content_json    JSONB NOT NULL,            -- Full document at this revision
    content_html    TEXT NOT NULL,             -- Rendered HTML at this revision
    revised_by      TEXT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE (note_id, revision_number)
);

CREATE INDEX idx_note_revisions_note ON note_revisions (note_id, revision_number DESC);
```

**Rationale:** Append-only, full snapshots. UNIQUE constraint ensures sequential numbering. CASCADE delete cleans up when parent note deleted. Descending index for "newest first" revision list.

---

## 5. Attachments Table

### 5.1 Table Definition

```sql
CREATE TABLE note_attachments (
    id              TEXT PRIMARY KEY,          -- att_ prefixed ULID
    note_id         TEXT REFERENCES notes(id) ON DELETE CASCADE,  -- Nullable for orphans
    filename        TEXT NOT NULL,             -- ULID-based filename on disk
    original_name   TEXT NOT NULL,             -- User-facing filename
    mime_type       TEXT NOT NULL,
    size_bytes      INTEGER NOT NULL,
    storage_path    TEXT NOT NULL,             -- Backend-relative path
    uploaded_by     TEXT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_note_attachments_note ON note_attachments (note_id);
CREATE INDEX idx_note_attachments_orphan ON note_attachments (created_at)
    WHERE note_id IS NULL;
```

**Rationale:** Nullable note_id supports the orphan upload pattern (images uploaded mid-editing before note saved). Partial orphan index enables efficient cleanup queries.

---

## 6. Mentions Table

### 6.1 Table Definition

```sql
CREATE TABLE note_mentions (
    id              TEXT PRIMARY KEY,          -- men_ prefixed ULID
    note_id         TEXT NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
    mention_type    TEXT NOT NULL,             -- Object type slug or 'user'
    mentioned_id    TEXT NOT NULL,             -- Prefixed ULID
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_note_mentions_note ON note_mentions (note_id);
CREATE INDEX idx_note_mentions_target ON note_mentions (mention_type, mentioned_id);
```

**Rationale:** mention_type + mentioned_id is polymorphic (like note_entities). Target index enables "notes mentioning contact X" reverse lookups.

---

## 7. Event Sourcing

### 7.1 Notes Events Table

```sql
CREATE TABLE notes_events (
    event_id    TEXT PRIMARY KEY,
    record_id   TEXT NOT NULL,
    event_type  TEXT NOT NULL,
    field_slug  TEXT,
    old_value   TEXT,
    new_value   TEXT,
    metadata    JSONB,
    user_id     TEXT,
    source      TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_notes_events_record ON notes_events (record_id, created_at);
CREATE INDEX idx_notes_events_type ON notes_events (event_type);
```

### 7.2 Event Types

| Event Type | Description |
|---|---|
| `record_created` | Note created |
| `field_updated` | Metadata field changed (title, visibility) |
| `content_revised` | Content changed. new_value has revision_id + revision_number. Does NOT store full content. |
| `entity_linked` | Note linked to entity |
| `entity_unlinked` | Note unlinked from entity |
| `pin_toggled` | Pin state changed on entity link |
| `visibility_changed` | Visibility changed (private ↔ shared) |
| `record_archived` | Soft-deleted |
| `record_unarchived` | Restored |
| `attachment_uploaded` | File attached to note |

### 7.3 Content Revised Event Pattern

Content changes emit a `content_revised` event that references the revision rather than storing multi-KB content inline:

```json
{
  "event_type": "content_revised",
  "record_id": "not_01HX8A...",
  "new_value": "{\"revision_id\": \"rev_01HX8B...\", \"revision_number\": 7}",
  "metadata": {"content_length_chars": 2450, "word_count": 380}
}
```

This keeps the event table lightweight while maintaining a complete audit trail.

---

## 8. Virtual Schema & Data Sources

### 8.1 Virtual Schema

Only metadata fields exposed (content is behavior-managed):

| Virtual Column | Source | Type |
|---|---|---|
| id | notes.id | Text (prefixed ULID) |
| title | notes.title | Text |
| visibility | notes.visibility | Select |
| revision_count | notes.revision_count | Number |
| created_by | notes.created_by | User |
| updated_by | notes.updated_by | User |
| created_at | notes.created_at | Datetime |
| updated_at | notes.updated_at | Datetime |
| User-added custom fields | As defined | As defined |

Content not exposed — use dedicated FTS search endpoint.

### 8.2 Linked Entities Column

New Views column type introduced by Universal Attachment: displays linked entities as mixed-type entity chips. Filter support: `has_link_to_type`, `has_link_to`, `link_count`.

### 8.3 Cross-Entity Query Examples

```sql
-- Notes linked to a contact
SELECT n.id, n.title, n.visibility, n.created_at
FROM notes n
JOIN note_entities ne ON ne.note_id = n.id
    AND ne.entity_type = 'contacts'
WHERE ne.entity_id = $contact_id
  AND n.archived_at IS NULL
  AND (n.visibility = 'shared' OR n.created_by = $current_user)
ORDER BY ne.is_pinned DESC, n.updated_at DESC;

-- Notes mentioning a specific contact
SELECT n.id, n.title, n.created_at
FROM notes n
JOIN note_mentions nm ON nm.note_id = n.id
WHERE nm.mention_type = 'contacts' AND nm.mentioned_id = $contact_id
  AND n.archived_at IS NULL;

-- Most active note authors
SELECT n.created_by, COUNT(*) AS note_count
FROM notes n
WHERE n.archived_at IS NULL AND n.visibility = 'shared'
GROUP BY n.created_by
ORDER BY note_count DESC;
```

---

## 9. API Design

### 9.1 Notes CRUD

| Endpoint | Method | Description |
|---|---|---|
| `/api/v1/notes` | GET | List notes (filterable by entity, created_by, visibility) |
| `/api/v1/notes` | POST | Create note with first revision |
| `/api/v1/notes/{id}` | GET | Get note with current revision content |
| `/api/v1/notes/{id}` | PATCH | Update (content → new revision; metadata → event only) |
| `/api/v1/notes/{id}` | DELETE | Archive |
| `/api/v1/notes/{id}/unarchive` | POST | Restore |

### 9.2 Entity Linking

| Endpoint | Method | Description |
|---|---|---|
| `/api/v1/notes/{id}/entities` | GET | List linked entities |
| `/api/v1/notes/{id}/entities` | POST | Link to entity (409 if duplicate) |
| `/api/v1/notes/{id}/entities/{type}/{entity_id}` | DELETE | Unlink (400 if last link) |
| `/api/v1/notes/{id}/entities/{type}/{entity_id}/pin` | POST | Toggle pin |

### 9.3 Revisions

| Endpoint | Method | Description |
|---|---|---|
| `/api/v1/notes/{id}/revisions` | GET | List revisions (newest first) |
| `/api/v1/notes/{id}/revisions/{revision_id}` | GET | Get specific revision content |

### 9.4 Attachments

| Endpoint | Method | Description |
|---|---|---|
| `/api/v1/notes/attachments/upload` | POST | Upload file (multipart, returns id + url) |
| `/api/v1/notes/attachments/{id}/{filename}` | GET | Serve file with tenant + visibility checks |

### 9.5 Mentions

| Endpoint | Method | Description |
|---|---|---|
| `/api/v1/notes/mentions` | GET | Autocomplete (q, optional type filter) |

### 9.6 Search

| Endpoint | Method | Description |
|---|---|---|
| `/api/v1/notes/search` | GET | FTS with ranked results, snippets, visibility filtering |

### 9.7 Pagination

Cursor-based with `updated_at`: `?limit=20&after={cursor}`. Response includes `next_cursor`.

---

## 10. Decisions to Be Added by Claude Code

- **Rich text editor choice:** flutter_quill, appflowy_editor, super_editor, or other.
- **Mention label refresh strategy:** Eager vs. lazy resolution on note load.
- **Stale entity link cleanup frequency:** Background job schedule and batch size.
- **Revision retention policy:** Whether to cap revisions per note or retain all indefinitely.
- **Content text extraction method:** HTML-to-text library choice for content_text generation.
