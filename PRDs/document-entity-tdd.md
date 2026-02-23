# Document Entity — TDD

**Version:** 1.0
**Last Updated:** 2026-02-23
**Status:** Draft
**Scope:** Entity
**Parent Document:** [document-entity-base-prd.md]
**Product TDD:** [product-tdd.md]

---

## 1. Overview

The Document entity requires entity-specific technical decisions beyond the Product TDD's global defaults. Key areas include: the read model table DDL with full-text search, the version history table, content-addressable blob storage, universal attachment and folder membership junction tables, communication-document relation, event sourcing, virtual schema, and API design.

---

## 2. Documents Read Model Table

### 2.1 Table Definition

```sql
CREATE TABLE documents (
    id              TEXT PRIMARY KEY,          -- doc_ prefixed ULID
    tenant_id       TEXT NOT NULL,
    name            TEXT NOT NULL,
    description     TEXT,
    is_folder       BOOLEAN NOT NULL DEFAULT false,
    visibility      TEXT NOT NULL DEFAULT 'private'
                        CHECK (visibility IN ('private', 'shared')),
    category        TEXT CHECK (category IN (
                        'document', 'spreadsheet', 'presentation',
                        'image', 'video', 'audio', 'archive',
                        'code', 'other'
                    )),
    source          TEXT NOT NULL DEFAULT 'uploaded'
                        CHECK (source IN ('uploaded', 'synced', 'profile_asset', 'system')),
    asset_type      TEXT CHECK (asset_type IN ('logo', 'headshot', 'banner')),

    -- File properties (NULL for folders)
    mime_type       TEXT,
    file_extension  TEXT,
    size_bytes      BIGINT,
    content_hash    TEXT,                      -- SHA-256 of current version

    -- Version tracking
    current_version_id TEXT,
    version_count   INTEGER NOT NULL DEFAULT 1,

    -- Extracted metadata
    extracted_author    TEXT,
    extracted_title     TEXT,
    page_count          INTEGER,
    width_px            INTEGER,
    height_px           INTEGER,
    duration_seconds    NUMERIC,
    has_thumbnail       BOOLEAN NOT NULL DEFAULT false,

    -- Extracted text for FTS
    content_text    TEXT,

    -- Full-text search (stored generated column)
    search_vector   TSVECTOR GENERATED ALWAYS AS (
        setweight(to_tsvector('english', coalesce(name, '')), 'A') ||
        setweight(to_tsvector('english', coalesce(description, '')), 'B') ||
        setweight(to_tsvector('english', coalesce(content_text, '')), 'C')
    ) STORED,

    -- Thumbnail reference
    thumbnail_for_id TEXT REFERENCES documents(id) ON DELETE SET NULL,

    -- Universal fields
    created_by      TEXT NOT NULL,
    updated_by      TEXT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    archived_at     TIMESTAMPTZ
);
```

### 2.2 Indexes

```sql
CREATE INDEX idx_documents_search ON documents USING GIN (search_vector);
CREATE INDEX idx_documents_visibility ON documents (visibility, created_by);
CREATE INDEX idx_documents_archived ON documents (archived_at) WHERE archived_at IS NULL;
CREATE INDEX idx_documents_current_ver ON documents (current_version_id);
CREATE INDEX idx_documents_category ON documents (category);
CREATE INDEX idx_documents_source ON documents (source);
CREATE INDEX idx_documents_hash ON documents (content_hash);
CREATE INDEX idx_documents_is_folder ON documents (is_folder);
CREATE INDEX idx_documents_asset_type ON documents (asset_type)
    WHERE asset_type IS NOT NULL;
```

**Rationale:** GIN index for tsvector FTS. Partial index on asset_type reduces index size for the common non-asset case. content_hash index supports deduplication lookups.

---

## 3. Document Versions Table

### 3.1 Table Definition

**Decision:** Append-only version history with per-version metadata snapshots.

```sql
CREATE TABLE document_versions (
    id              TEXT PRIMARY KEY,          -- ver_ prefixed ULID
    document_id     TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    version_number  INTEGER NOT NULL,
    name            TEXT,                      -- Optional version name
    description     TEXT,                      -- Optional version note

    -- File properties for this version
    mime_type       TEXT NOT NULL,
    file_extension  TEXT NOT NULL,
    size_bytes      BIGINT NOT NULL,
    content_hash    TEXT NOT NULL,
    storage_path    TEXT NOT NULL,

    -- Metadata snapshot for this version
    extracted_author    TEXT,
    extracted_title     TEXT,
    page_count          INTEGER,
    width_px            INTEGER,
    height_px           INTEGER,
    duration_seconds    NUMERIC,
    metadata_json       JSONB,                 -- Extended metadata

    -- Provenance
    uploaded_by     TEXT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE (document_id, version_number)
);

CREATE INDEX idx_doc_versions_document ON document_versions (document_id, version_number DESC);
CREATE INDEX idx_doc_versions_hash ON document_versions (content_hash);
```

**Rationale:** Each version stores full metadata snapshot, enabling tracking across versions ("v1 had 12 pages, v2 has 15"). UNIQUE constraint ensures sequential numbering per document. CASCADE delete cleans up when parent is deleted.

---

## 4. Document Blobs Table

### 4.1 Table Definition

**Decision:** Content-addressable storage with reference counting.

```sql
CREATE TABLE document_blobs (
    content_hash    TEXT PRIMARY KEY,          -- SHA-256
    storage_path    TEXT NOT NULL,
    size_bytes      BIGINT NOT NULL,
    mime_type       TEXT NOT NULL,
    reference_count INTEGER NOT NULL DEFAULT 1,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

**Rationale:** SHA-256 as primary key ensures content uniqueness. Reference counting tracks how many versions reference each blob. Orphan cleanup removes blobs with reference_count = 0.

---

## 5. Universal Attachment Junction Table

### 5.1 Table Definition

```sql
CREATE TABLE document_entities (
    document_id     TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    entity_type     TEXT NOT NULL,
    entity_id       TEXT NOT NULL,
    is_pinned       BOOLEAN NOT NULL DEFAULT false,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    PRIMARY KEY (document_id, entity_type, entity_id)
);

CREATE INDEX idx_de_entity ON document_entities (entity_type, entity_id);
CREATE INDEX idx_de_document ON document_entities (document_id);
CREATE INDEX idx_de_pinned ON document_entities (entity_type, entity_id, is_pinned DESC);
```

**Rationale:** Composite PK prevents duplicate links. Polymorphic target via entity_type + entity_id. Pinned index supports "pinned first" display on entity detail pages.

---

## 6. Folder Membership Junction Table

### 6.1 Table Definition

```sql
CREATE TABLE document_folder_members (
    folder_id       TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    document_id     TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    added_by        TEXT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    PRIMARY KEY (folder_id, document_id),
    CHECK (folder_id != document_id)
);

CREATE INDEX idx_dfm_folder ON document_folder_members (folder_id);
CREATE INDEX idx_dfm_document ON document_folder_members (document_id);
```

**Rationale:** CHECK prevents self-membership. CASCADE from both sides. Bidirectional indexes for "contents of folder" and "folders containing document" queries. Acyclic enforcement is application-level (ancestry walk before folder-in-folder insert).

---

## 7. Communication-Document Relation Table

### 7.1 Table Definition

**Decision:** Version-tracked attachment relation for email attachment promotion.

```sql
CREATE TABLE communication_documents (
    communication_id TEXT NOT NULL,
    document_id      TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    version_id       TEXT NOT NULL REFERENCES document_versions(id),
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),

    PRIMARY KEY (communication_id, document_id)
);

CREATE INDEX idx_cd_communication ON communication_documents (communication_id);
CREATE INDEX idx_cd_document ON communication_documents (document_id);
```

**Rationale:** `version_id` records the exact version attached to each communication, enabling "which version was sent in that email." See Integration Sub-PRD for sync flow.

---

## 8. Event Sourcing

### 8.1 Documents Events Table

```sql
CREATE TABLE documents_events (
    event_id    TEXT PRIMARY KEY,
    record_id   TEXT NOT NULL,
    event_type  TEXT NOT NULL,
    field_slug  TEXT,
    old_value   TEXT,
    new_value   TEXT,
    metadata    JSONB,
    user_id     TEXT,
    source      TEXT,                          -- 'api', 'ui', 'sync', 'automation'
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_documents_events_record ON documents_events (record_id, created_at);
CREATE INDEX idx_documents_events_type ON documents_events (event_type);
```

### 8.2 Event Types

| Event Type | Description |
|---|---|
| `record_created` | Document created. metadata includes source. |
| `field_updated` | Metadata field changed. |
| `version_created` | New version uploaded. new_value has version_id, version_number, content_hash. |
| `entity_linked` | Document linked to entity. |
| `entity_unlinked` | Document unlinked from entity. |
| `pin_toggled` | Pin state changed on entity link. |
| `folder_added` | Document added to folder. |
| `folder_removed` | Document removed from folder. |
| `visibility_changed` | Visibility changed. |
| `record_archived` | Soft-deleted. |
| `record_unarchived` | Restored. |
| `thumbnail_generated` | Thumbnail created. |
| `metadata_extracted` | File metadata extracted. |
| `text_extracted` | Text content extracted for FTS. |
| `duplicate_detected` | Upload matched existing content. |

---

## 9. Virtual Schema & Data Sources

### 9.1 Virtual Schema Table

All Document fields from the field registry are exposed as virtual columns except `content_text` (use FTS endpoint).

### 9.2 Cross-Entity Query Examples

```sql
-- Documents linked to a contact
SELECT d.id, d.name, d.category, c.first_name, c.last_name
FROM documents d
JOIN document_entities de ON de.document_id = d.id AND de.entity_type = 'contacts'
JOIN contacts c ON c.id = de.entity_id
WHERE d.archived_at IS NULL AND d.is_folder = false
  AND (d.visibility = 'shared' OR d.created_by = $current_user);

-- Folder contents
SELECT d.id, d.name, d.is_folder, d.category, d.size_bytes, d.updated_at
FROM documents d
JOIN document_folder_members dfm ON dfm.document_id = d.id
WHERE dfm.folder_id = $folder_id AND d.archived_at IS NULL
ORDER BY d.is_folder DESC, d.name ASC;

-- Profile assets for an entity
SELECT d.id, d.name, d.asset_type, d.content_hash, d.mime_type
FROM documents d
JOIN document_entities de ON de.document_id = d.id
WHERE de.entity_type = $1 AND de.entity_id = $2
  AND d.asset_type IS NOT NULL AND d.archived_at IS NULL
ORDER BY d.asset_type, d.updated_at DESC;
```

---

## 10. API Design

### 10.1 Documents CRUD

| Endpoint | Method | Description |
|---|---|---|
| `/api/v1/documents` | GET | List documents (filterable, paginated) |
| `/api/v1/documents` | POST | Upload document (multipart form data) |
| `/api/v1/documents/{id}` | GET | Get document with current version and entity links |
| `/api/v1/documents/{id}` | PATCH | Update metadata |
| `/api/v1/documents/{id}` | DELETE | Archive |
| `/api/v1/documents/{id}/unarchive` | POST | Restore |
| `/api/v1/documents/{id}/download` | GET | Download current version |
| `/api/v1/documents/{id}/preview` | GET | Get thumbnail URL |

### 10.2 Folder Operations

| Endpoint | Method | Description |
|---|---|---|
| `/api/v1/documents/folders` | POST | Create folder |
| `/api/v1/documents/{folder_id}/members` | GET | List folder contents |
| `/api/v1/documents/{folder_id}/members` | POST | Add document to folder |
| `/api/v1/documents/{folder_id}/members/{document_id}` | DELETE | Remove from folder |

### 10.3 Version Management

| Endpoint | Method | Description |
|---|---|---|
| `/api/v1/documents/{id}/versions` | GET | List versions |
| `/api/v1/documents/{id}/versions` | POST | Upload new version (204 if same hash) |
| `/api/v1/documents/{id}/versions/{version_id}` | GET | Get version metadata |
| `/api/v1/documents/{id}/versions/{version_id}` | PATCH | Update version name/description |
| `/api/v1/documents/{id}/versions/{version_id}/download` | GET | Download specific version |

### 10.4 Entity Linking

| Endpoint | Method | Description |
|---|---|---|
| `/api/v1/documents/{id}/entities` | GET | List linked entities |
| `/api/v1/documents/{id}/entities` | POST | Link to entity |
| `/api/v1/documents/{id}/entities/{type}/{entity_id}` | DELETE | Unlink |
| `/api/v1/documents/{id}/entities/{type}/{entity_id}/pin` | POST | Toggle pin |

### 10.5 Search

| Endpoint | Method | Description |
|---|---|---|
| `/api/v1/documents/search` | GET | FTS with ranked results, snippets, visibility filtering |

### 10.6 Chunked Uploads

| Endpoint | Method | Description |
|---|---|---|
| `/api/v1/documents/uploads` | POST | Initiate session |
| `/api/v1/documents/uploads/{session_id}` | PATCH | Upload chunk |
| `/api/v1/documents/uploads/{session_id}` | POST | Complete upload |
| `/api/v1/documents/uploads/{session_id}` | DELETE | Cancel session |

### 10.7 Pagination

Cursor-based with `updated_at`: `?limit=20&after={cursor}`. Response includes `next_cursor`.

---

## 11. Decisions to Be Added by Claude Code

- **Storage backend selection:** Local disk path structure and S3 migration strategy.
- **Progressive hash threshold:** File size threshold for skipping quick hash (small files → full hash directly).
- **content_text truncation limit:** Default 1MB, but optimal value depends on FTS performance testing.
- **Thumbnail generation library:** Pillow for images, pdf2image for PDFs, ffmpeg for video.
- **Orphan cleanup schedule:** Frequency and batch size for blob garbage collection.
- **Chunked upload temp storage:** Location and cleanup strategy for incomplete uploads.
- **Effective visibility caching:** Whether to cache computed visibility or evaluate on every access.
