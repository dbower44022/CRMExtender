# Product Requirements Document: Notes System

## CRMExtender — Entity-Agnostic Notes with Rich Text, Revisions & Universal Attachment

**Version:** 2.0
**Date:** 2026-02-17
**Status:** Draft — Fully reconciled with Custom Objects PRD
**Parent Document:** [CRMExtender PRD v1.1](PRD.md)

> **V2.0 Rewrite (2026-02-17):**
> This document is a full rewrite of the Notes PRD v1.0 (2026-02-14), which documented the PoC-era SQLite implementation (Phases 17–18). All content has been reconciled with the [Custom Objects PRD](custom-objects-prd.md) Unified Object Model:
> - Note is a **system object type** (`is_system = true`, prefix `not_`) in the unified framework. Metadata fields are registered in the field registry; specialized behaviors (revision management, FTS sync, mention extraction, orphan attachment cleanup) are registered per Custom Objects PRD Section 22.
> - Entity IDs use **prefixed ULIDs** (`not_` prefix, e.g., `not_01HX8A...`) per the platform-wide convention (Data Sources PRD, Custom Objects PRD Section 6).
> - Note-to-entity linking uses a new **Universal Attachment Relation** pattern (`target = *`), enabling notes to attach to any entity type — system or custom — without requiring individual relation type definitions per entity type. This replaces the PoC-era hardcoded `entity_type` CHECK constraint.
> - Rich text content (`content_json`, `content_html`) is **behavior-managed** — stored as columns on the `notes` table but not registered in the field registry. Content is managed by the Notes revision behavior, not by the standard field update pipeline.
> - **Revision history** coexists with event sourcing: `notes_events` tracks metadata changes (title, visibility, entity links, pins), while `note_revisions` stores full content snapshots. Content changes generate a `content_revised` event that points to the revision rather than storing the full document.
> - Full-text search uses **PostgreSQL native `tsvector`/`tsquery`** with a stored generated column, replacing the PoC-era SQLite FTS5 virtual table.
> - Notes have an **own visibility model**: Private (creator only, default) or Shared (inherits visibility from linked entities). This is independent of entity-level permissions.
> - The editor is specified as **editor-agnostic** — the PRD defines the content storage contract and required capabilities, deferring the specific Flutter rich text editor choice to implementation.
> - All SQL uses **PostgreSQL** syntax with `TIMESTAMPTZ` timestamps, `JSONB` content, and schema-per-tenant isolation, replacing the PoC-era SQLite schemas.
> - The PoC implementation details (file paths, test counts, HTMX routes, Tiptap configuration) are preserved in [Appendix A](#appendix-a-poc-implementation-reference) for historical reference.

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Problem Statement](#2-problem-statement)
3. [Goals & Success Metrics](#3-goals--success-metrics)
4. [Note as System Object Type](#4-note-as-system-object-type)
5. [Data Model](#5-data-model)
6. [Universal Attachment Relation](#6-universal-attachment-relation)
7. [Content Architecture](#7-content-architecture)
8. [Revision History](#8-revision-history)
9. [Event Sourcing](#9-event-sourcing)
10. [Full-Text Search](#10-full-text-search)
11. [File Attachments](#11-file-attachments)
12. [@Mentions](#12-mentions)
13. [Pinning](#13-pinning)
14. [Note Visibility](#14-note-visibility)
15. [Content Sanitization](#15-content-sanitization)
16. [API Design](#16-api-design)
17. [Virtual Schema & Data Sources](#17-virtual-schema--data-sources)
18. [Design Decisions](#18-design-decisions)
19. [Phasing & Roadmap](#19-phasing--roadmap)
20. [Dependencies & Related PRDs](#20-dependencies--related-prds)
21. [Open Questions](#21-open-questions)
22. [Future Work](#22-future-work)
23. [Glossary](#23-glossary)
24. [Appendix A: PoC Implementation Reference](#appendix-a-poc-implementation-reference)

---

## 1. Executive Summary

The Notes subsystem is the free-form knowledge capture layer of CRMExtender. While structured fields capture typed data (names, dates, amounts) and communication intelligence tracks message-level interactions, Notes answer **"What did the user observe, decide, or want to remember about this entity?"** Notes provide the unstructured counterpart to structured CRM data — meeting observations, strategic context, internal commentary, and shared knowledge that doesn't fit into predefined fields.

Unlike CRMs where notes are simple text blobs buried in activity timelines, CRMExtender treats notes as **first-class entities** with rich text formatting, full revision history, multi-entity attachment, @mentions for cross-referencing, file attachments for supporting documents, and full-text search across the entire workspace. A single note can be attached to multiple entities simultaneously — a meeting note linked to both a Contact and a Company, or a strategy note attached to a Job and its related Property.

**Core principles:**

- **System object type** — Note is a system object type (`is_system = true`, prefix `not_`) in the Custom Objects unified framework. Metadata fields (title, visibility, timestamps) are registered in the field registry. Specialized behaviors (revision management, FTS sync, mention extraction) are registered per Custom Objects PRD Section 22. Users can extend Notes with custom fields through the standard field registry.
- **Universal attachment** — Notes attach to any entity type (system or custom) through the Universal Attachment Relation pattern. When Sam creates a "Jobs" custom object type, notes are immediately attachable to Job records without any additional configuration. A single note can be linked to multiple entities across different types.
- **Behavior-managed content** — Rich text content is stored as JSONB (editor-native format) with pre-rendered HTML, managed by the Notes revision behavior rather than the standard field update pipeline. This preserves the append-only revision model where every content edit creates a full snapshot, while metadata changes flow through standard event sourcing.
- **Private by default** — Notes are visible only to their creator by default. Authors can explicitly share notes, at which point visibility inherits from the linked entity's permission model. This ensures that personal observations, draft thoughts, and sensitive commentary remain private unless intentionally shared.
- **Editor-agnostic** — The content storage contract (JSONB + HTML + plain text) is defined independently of the rich text editor. The Flutter frontend will use a native rich text editor (implementation choice), and the backend accepts any JSON document format that satisfies the content contract.

**Current state:** The PoC implements the full notes data model in SQLite, Tiptap-based rich text editing via HTMX, multi-entity attachment (Phase 18), revision history, @mentions, file attachments, FTS5 search, and 71 tests. See [Appendix A](#appendix-a-poc-implementation-reference) for details.

**Relationship to other PRDs:**

- **[Custom Objects PRD](custom-objects-prd.md)** — The Note entity type is a system object type in the unified framework. Its table structure, field registry, and event sourcing are governed by the Custom Objects PRD. The Universal Attachment Relation pattern introduced by this PRD extends the Custom Objects relation type model with a new polymorphic target capability. This PRD defines the Note-specific behaviors registered with the object type framework.
- **[Contact Management PRD](contact-management-prd_V4.md)** — Notes attach to contacts as contextual observations. Contact detail views display notes with visibility filtering. The @mention system enables referencing contacts within note content.
- **[Company Management PRD](company-management-prd.md)** — Notes attach to companies for research observations, relationship strategy, and competitive intelligence. Companies are mentionable within note content.
- **[Communication & Conversation Intelligence PRD](email-conversations-prd.md)** — Notes attach to conversations for internal commentary, meeting summaries, and follow-up action items that supplement the automated conversation intelligence.
- **[Event Management PRD](events-prd_V2.md)** — Notes attach to events for meeting preparation, post-meeting observations, and action items.
- **[Data Sources PRD](data-sources-prd.md)** — The Note virtual schema table is derived from the Note object type's field registry (metadata fields only; content is not queryable through standard Data Source filters — use the dedicated FTS search endpoint).
- **[Permissions & Sharing PRD](permissions-sharing-prd_V1.md)** — Notes integrate with the permissions model through the visibility field. Shared notes inherit visibility from linked entities; private notes are visible only to their creator regardless of entity-level permissions.

---

## 2. Problem Statement

CRM users accumulate knowledge about their relationships that doesn't fit into structured fields. A salesperson notices a prospect's communication style preferences. A service provider records site-specific instructions. A team lead captures strategic context about an account that shapes how colleagues should engage.

Without a notes system, this knowledge lives in external tools (personal documents, sticky notes, email drafts), creating several problems: it's not searchable across the CRM, it's not linked to the entities it's about, it's not shared with team members who need it, and it's lost when people leave or change roles.

The Notes subsystem addresses this by embedding free-form knowledge capture directly into the entity model, with rich formatting for readability, revision history for accountability, multi-entity linking for cross-referencing, and visibility controls for privacy.

---

## 3. Goals & Success Metrics

| Goal | Metric | Target |
|---|---|---|
| Attach notes to any entity | Notes available on all system entity detail pages + all custom object detail pages | 100% entity type coverage |
| Rich formatting | Bold, italic, headings, lists, blockquotes, code blocks, tables, images, links | All formatting types functional |
| Revision history | Every content edit creates a new revision; any version viewable | 100% edit coverage |
| File attachments | Paste/drop images into editor; upload documents | Image + document support |
| Cross-entity search | Full-text search across all notes with ranked results | <200ms for 95th percentile |
| @Mentions | Reference users, contacts, companies in note content | Autocomplete + rendered chips |
| Multi-entity linking | Single note attachable to 2+ entities of any type | No entity type restrictions |
| Privacy by default | Notes visible only to creator unless explicitly shared | Default visibility = private |
| Custom object support | Notes attachable to user-created entity types without configuration | Automatic via universal attachment |

---

## 4. Note as System Object Type

### 4.1 Object Type Registration

Note is registered as a system object type in `platform.object_types`:

| Attribute | Value |
|---|---|
| `slug` | `notes` |
| `name` | `Note` |
| `type_prefix` | `not_` |
| `is_system` | `true` |
| `description` | Free-form rich text notes with revision history, attachable to any entity |
| `display_name_field` | `title` |
| `icon` | `note-text` (or equivalent) |

### 4.2 Field Registry (Metadata Fields Only)

Only metadata fields are registered in the field registry. Rich text content (`content_json`, `content_html`) is behavior-managed — see [Section 7](#7-content-architecture).

| Field Slug | Field Type | System | Required | Default | Description |
|---|---|---|---|---|---|
| `title` | Text | Yes | No | `NULL` | Optional short title; short notes use first line of content as display |
| `visibility` | Select | Yes | Yes | `'private'` | `private` (creator only) or `shared` (inherits entity visibility) |
| `current_revision_id` | Text | Yes | No | — | Points to the latest `note_revisions` row. Managed by revision behavior. |
| `revision_count` | Number | Yes | No | `1` | Count of revisions. Managed by revision behavior. Useful in Views for "most edited notes." |

Universal fields (`id`, `tenant_id`, `created_at`, `updated_at`, `created_by`, `updated_by`, `archived_at`) are inherited from the object type framework per Custom Objects PRD Section 8.

Users can add custom fields to Notes through the standard field registry (e.g., a "Category" select field, a "Priority" rating field).

### 4.3 Registered Behaviors

Per Custom Objects PRD Section 22, the Note system object type registers the following specialized behaviors:

| Behavior | Trigger | Description |
|---|---|---|
| Revision management | On content save | Creates a new `note_revisions` row with incremented `revision_number`. Updates `current_revision_id` and `revision_count` on the note. Emits a `content_revised` event to `notes_events`. |
| FTS sync | On content save, on delete | Updates the `search_vector` stored generated column's source text. On delete, the row is removed (CASCADE or explicit). |
| Mention extraction | On content save | Walks the content JSON document tree, extracts `@mention` nodes, and syncs the `note_mentions` table (delete-and-reinsert). |
| Orphan attachment cleanup | On schedule (background job) | Deletes `note_attachments` rows with `note_id IS NULL` older than 24 hours, removes corresponding files from disk. |
| Visibility enforcement | On query | Filters notes based on `visibility` field: private notes return only for `created_by = current_user`; shared notes apply entity-level permission checks via linked entities. |

---

## 5. Data Model

### 5.1 Tables

All tables reside in the tenant schema (e.g., `tenant_abc.notes`). The `search_path` is set per request, so queries reference tables without schema qualification.

#### `notes` — Read model (system object type table)

```sql
CREATE TABLE notes (
    id              TEXT PRIMARY KEY,          -- not_ prefixed ULID
    tenant_id       TEXT NOT NULL,             -- FK → platform.tenants
    title           TEXT,                      -- Optional; display_name_field
    visibility      TEXT NOT NULL DEFAULT 'private'
                        CHECK (visibility IN ('private', 'shared')),
    current_revision_id TEXT,                  -- FK → note_revisions(id)
    revision_count  INTEGER NOT NULL DEFAULT 1,

    -- Behavior-managed content columns (not in field registry)
    content_json    JSONB,                     -- Editor-native document format
    content_html    TEXT,                      -- Pre-rendered HTML for display
    content_text    TEXT,                      -- Plain text extracted for FTS

    -- Full-text search (stored generated column)
    search_vector   TSVECTOR GENERATED ALWAYS AS (
        setweight(to_tsvector('english', coalesce(title, '')), 'A') ||
        setweight(to_tsvector('english', coalesce(content_text, '')), 'B')
    ) STORED,

    -- Universal fields (Custom Objects framework)
    created_by      TEXT NOT NULL,             -- FK → platform.users
    updated_by      TEXT NOT NULL,             -- FK → platform.users
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    archived_at     TIMESTAMPTZ               -- Soft delete
);

-- GIN index for full-text search
CREATE INDEX idx_notes_search ON notes USING GIN (search_vector);

-- Visibility + creator for private note filtering
CREATE INDEX idx_notes_visibility ON notes (visibility, created_by);

-- Soft delete filter (common query: non-archived notes)
CREATE INDEX idx_notes_archived ON notes (archived_at) WHERE archived_at IS NULL;

-- Current revision lookup
CREATE INDEX idx_notes_current_rev ON notes (current_revision_id);
```

#### `note_entities` — Universal Attachment junction

```sql
CREATE TABLE note_entities (
    note_id         TEXT NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
    entity_type     TEXT NOT NULL,             -- Object type slug (e.g., 'contacts', 'jobs')
    entity_id       TEXT NOT NULL,             -- Prefixed ULID of the linked entity
    is_pinned       BOOLEAN NOT NULL DEFAULT false,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    PRIMARY KEY (note_id, entity_type, entity_id)
);

-- List notes for an entity (most common query path)
CREATE INDEX idx_ne_entity ON note_entities (entity_type, entity_id);

-- Find entities for a note
CREATE INDEX idx_ne_note ON note_entities (note_id);

-- Sort pinned first within entity note lists
CREATE INDEX idx_ne_pinned ON note_entities (entity_type, entity_id, is_pinned DESC);
```

#### `note_revisions` — Append-only content history

```sql
CREATE TABLE note_revisions (
    id              TEXT PRIMARY KEY,          -- rev_ prefixed ULID
    note_id         TEXT NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
    revision_number INTEGER NOT NULL,
    content_json    JSONB NOT NULL,            -- Full editor document at this revision
    content_html    TEXT NOT NULL,             -- Rendered HTML at this revision
    revised_by      TEXT NOT NULL,             -- FK → platform.users
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE (note_id, revision_number)
);

CREATE INDEX idx_note_revisions_note ON note_revisions (note_id, revision_number DESC);
```

#### `note_attachments` — Uploaded files

```sql
CREATE TABLE note_attachments (
    id              TEXT PRIMARY KEY,          -- att_ prefixed ULID
    note_id         TEXT REFERENCES notes(id) ON DELETE CASCADE,  -- Nullable for orphan uploads
    filename        TEXT NOT NULL,             -- ULID-based filename on disk
    original_name   TEXT NOT NULL,             -- User-facing filename
    mime_type       TEXT NOT NULL,             -- Validated against allowlist
    size_bytes      INTEGER NOT NULL,
    storage_path    TEXT NOT NULL,             -- Relative path within upload directory
    uploaded_by     TEXT NOT NULL,             -- FK → platform.users
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_note_attachments_note ON note_attachments (note_id);
CREATE INDEX idx_note_attachments_orphan ON note_attachments (created_at)
    WHERE note_id IS NULL;  -- Orphan cleanup query
```

#### `note_mentions` — Extracted @mentions

```sql
CREATE TABLE note_mentions (
    id              TEXT PRIMARY KEY,          -- men_ prefixed ULID
    note_id         TEXT NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
    mention_type    TEXT NOT NULL,             -- Object type slug or 'user'
    mentioned_id    TEXT NOT NULL,             -- Prefixed ULID of the mentioned entity/user
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_note_mentions_note ON note_mentions (note_id);
CREATE INDEX idx_note_mentions_target ON note_mentions (mention_type, mentioned_id);
```

### 5.2 Entity Relationship Diagram

```
notes 1──* note_entities      (CASCADE delete; universal attachment junction)
notes 1──* note_revisions     (CASCADE delete; append-only content history)
notes 1──* note_attachments   (CASCADE delete; nullable note_id for orphans)
notes 1──* note_mentions      (CASCADE delete; extracted @mentions)
notes ···> notes_events       (event sourcing; metadata changes only)

notes ──> platform.tenants    (tenant_id FK)
notes ──> platform.users      (created_by, updated_by)
note_revisions ──> platform.users (revised_by)
note_attachments ──> platform.users (uploaded_by)

note_entities ··> {any entity type table}  (entity_id; application-level, no DB FK)
note_mentions ··> {any entity type table}  (mentioned_id; application-level, no DB FK)
```

---

## 6. Universal Attachment Relation

### 6.1 Concept

The Universal Attachment Relation is a new relation pattern introduced to support cross-cutting subsystems that need to link to any entity type. Unlike standard relation types (which connect two specific object types), a universal attachment relation has `target = '*'`, meaning the target side accepts any registered object type.

This pattern is registered in `platform.relation_types`:

| Attribute | Value |
|---|---|
| `id` | `rel_note_attachment` |
| `slug` | `note_entity_attachment` |
| `source_object_type` | `notes` |
| `target_object_type` | `*` (wildcard — any registered object type) |
| `cardinality` | `many-to-many` |
| `directionality` | `bidirectional` |
| `has_metadata` | `true` |
| `metadata_fields` | `is_pinned (boolean)` |
| `cascade_behavior` | See Section 6.3 |

### 6.2 How It Differs from Standard Relations

| Aspect | Standard Relation | Universal Attachment |
|---|---|---|
| Target object type | Specific (e.g., `contacts`) | Wildcard (`*`) |
| Junction table | Typed FKs to both sides | `entity_type` + `entity_id` polymorphic columns |
| Referential integrity | Database-level FK constraints | Application-level consistency checks |
| Views traversal | Standard relation column | Special "linked entities" column type (see Section 17) |
| Auto-provisioning | Manual or system-defined | Automatically works for new custom object types |
| Neo4j sync | Typed edge (e.g., `EMPLOYED_AT`) | Generic edge (`HAS_NOTE`) with `entity_type` property |

### 6.3 Cascade & Consistency

**When a note is deleted (archived):** All `note_entities` rows for that note remain (soft delete preserves links). On hard delete (if implemented), rows CASCADE delete.

**When a linked entity is deleted (archived):** The `note_entities` row remains — the note still exists but has a stale link. A background consistency job periodically checks for `note_entities` rows where the `entity_id` no longer resolves to an active record, and either removes the stale link or flags it for user review.

**When the last entity link is removed:** A note must always have at least one entity link (otherwise it's orphaned). The API prevents removing the last `note_entities` row — the user must delete the note instead. (Exception: notes in the process of being moved between entities go through an atomic "remove + add" operation.)

**When a custom object type is archived:** Notes linked to archived entity types retain their links. The notes remain accessible through other linked entities or through global search. If a note's only link is to an archived entity type, the note is still accessible to its creator through the "My Notes" view.

### 6.4 Framework Impact

The Universal Attachment pattern requires the following extensions to the Custom Objects relation type framework:

1. **Relation type validation**: Accept `target_object_type = '*'` as a valid value for system-defined relation types (user-created relation types cannot use wildcards).
2. **Junction table schema**: Universal attachment junction tables use `entity_type TEXT` + `entity_id TEXT` columns instead of a typed FK column.
3. **Views integration**: A new "Linked Entities" column type that renders as a list of entity chips with mixed types (see Section 17).
4. **Data Sources integration**: Universal attachment JOINs use `entity_type` filtering to target a specific entity type in queries (see Section 17).
5. **Neo4j sync**: Universal attachment links sync as `HAS_NOTE` edges with an `entity_type` property for graph queries.

### 6.5 Future Subsystems

The Universal Attachment pattern is designed to be reusable. Future cross-cutting subsystems that may use the same pattern:

- **Tags** — Freeform or taxonomy-based labels attachable to any entity
- **Activity Log** — User activity events (viewed, commented, shared) on any entity
- **Bookmarks / Favorites** — User-specific entity bookmarks
- **Tasks / Action Items** — Trackable items linked to any entity

Each would register its own universal attachment relation type with `target = '*'`.

---

## 7. Content Architecture

### 7.1 Design Decision: Behavior-Managed Content

Rich text content (`content_json`, `content_html`, `content_text`) is stored as columns on the `notes` table but is **not registered in the field registry**. This means:

- Content is not queryable through standard Data Source filters or View filter builders. Users search note content through the dedicated FTS search endpoint (Section 10).
- Content changes do not generate standard `field_updated` events. Instead, the revision behavior emits a `content_revised` event that points to the new revision (Section 9).
- Content editing uses the Notes-specific rich text editor, not a standard field edit widget.

This was chosen because: (a) rich text documents are fundamentally different from typed field values — they're variable-length, deeply nested JSON structures that don't map to column-level comparison operators like `equals`, `contains`, `greater_than`; (b) the revision model (full-snapshot append-only history) is incompatible with field-level event sourcing delta tracking; and (c) full-text search with ranking and snippets provides a better content discovery experience than field-level filters.

### 7.2 Content Storage Contract

The content storage model is editor-agnostic. The backend stores three representations of the same content:

| Column | Type | Purpose |
|---|---|---|
| `content_json` | `JSONB` | Editor-native document format. Source of truth for re-editing. The specific JSON schema depends on the chosen Flutter rich text editor (e.g., Quill Delta, AppFlowy block tree). The backend treats this as an opaque JSONB blob. |
| `content_html` | `TEXT` | Pre-rendered HTML. Generated by the editor on save. Used for display contexts that don't have the editor loaded (notifications, API responses, web embeds, exports). Sanitized before storage (Section 15). |
| `content_text` | `TEXT` | Plain text extracted from HTML (all tags stripped). Used for FTS indexing via the `search_vector` generated column. Also used for note preview snippets in lists. |

On create/update, the client sends `content_json` and `content_html`. The server extracts `content_text` from `content_html` using an HTML-to-text utility.

### 7.3 Editor Requirements

The Flutter rich text editor must support the following capabilities. The specific editor choice (flutter_quill, appflowy_editor, super_editor, or other) is an implementation decision.

**Required formatting:**
- Inline: Bold, italic, strikethrough, code, underline
- Block: Paragraphs, headings (H1–H3), bullet lists, ordered lists, blockquotes, code blocks, horizontal rules
- Tables: Basic table creation and editing
- Links: URL insertion with display text
- Images: Inline image display with URL source

**Required interactions:**
- Image paste/drop: Intercept clipboard and drag events, upload to attachment endpoint, insert returned URL
- @Mention autocomplete: Trigger on `@` character, search users and entities, insert mention node with type + ID + display label
- Content sync: On every edit, update `content_json` and `content_html` in the form state

**Required output:**
- Export `content_json` in the editor's native document format (JSONB-serializable)
- Export `content_html` as sanitizable HTML string
- Re-hydrate editor state from `content_json` for editing existing notes

**Graceful degradation:**
- If the rich text editor fails to load, fall back to a plain `<textarea>` (content stored as HTML-escaped plain text in `content_json` and `content_html`)

### 7.4 Mention Node Contract

Regardless of editor choice, @mention nodes in `content_json` must include:

```json
{
  "type": "mention",
  "attrs": {
    "id": "con_01HX8A...",
    "mentionType": "contacts",
    "label": "Jane Smith"
  }
}
```

The `mentionType` is the object type slug (or `"user"` for workspace users). The `id` is the prefixed ULID. The `label` is the display name at mention time (may become stale if the entity is renamed — acceptable, as the `id` is the authoritative reference).

---

## 8. Revision History

### 8.1 Model

Every content save creates a new `note_revisions` row. Revisions are:

- **Append-only**: Never updated or deleted individually. Removed only via CASCADE when the parent note is deleted.
- **Numbered**: `revision_number` starts at 1 and increments per note.
- **Unique**: `UNIQUE(note_id, revision_number)` constraint.
- **Full snapshots**: Each revision stores the complete `content_json` and `content_html` at that point in time. No diffs.

### 8.2 Revision Lifecycle

| Action | Behavior |
|---|---|
| **Create note** | First revision created (revision_number = 1). `current_revision_id` and `revision_count` set on the note. |
| **Update content** | New revision created (revision_number incremented). Note's `current_revision_id` updated. Note's `revision_count` incremented. Note's `content_json`, `content_html`, `content_text` updated to match new revision. |
| **Update metadata only** | Title, visibility, or custom field changes do NOT create a new revision. These are metadata changes tracked by event sourcing (Section 9). |
| **View old revision** | Client requests a specific revision by ID. Server returns the revision's `content_html` for display. |
| **Delete note** | All revisions CASCADE delete. |

### 8.3 Design: Full Snapshots, Not Diffs

The system stores and displays complete content versions, not diffs. Rationale:

- Each version is independently renderable without reconstructing from a chain of deltas
- Simpler implementation with no risk of delta chain corruption
- Storage cost is acceptable for text content (a 10KB note with 50 revisions = ~500KB — trivial at database scale)
- Diff computation can be added as a view-layer feature (client-side diff between two revision HTML snapshots) without schema changes

---

## 9. Event Sourcing

### 9.1 Event Table

Per Custom Objects PRD Section 19, the Note object type has a companion event table:

```sql
CREATE TABLE notes_events (
    event_id    TEXT PRIMARY KEY,              -- evt_ prefixed ULID
    record_id   TEXT NOT NULL,                 -- FK → notes(id)
    event_type  TEXT NOT NULL,
    field_slug  TEXT,                          -- Which field changed (NULL for record-level events)
    old_value   TEXT,                          -- Previous value (serialized)
    new_value   TEXT,                          -- New value (serialized)
    metadata    JSONB,                         -- Additional context
    user_id     TEXT,                          -- Who triggered the change
    source      TEXT,                          -- 'api', 'ui', 'automation'
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_notes_events_record ON notes_events (record_id, created_at);
CREATE INDEX idx_notes_events_type ON notes_events (event_type);
```

### 9.2 Event Types

| Event Type | Field Slug | Description |
|---|---|---|
| `record_created` | `NULL` | Note was created. `new_value` contains initial metadata as JSON. |
| `field_updated` | The changed field | A metadata field was updated (title, visibility, custom fields). Standard event sourcing. |
| `content_revised` | `NULL` | Content was edited. `new_value` contains `{"revision_id": "rev_...", "revision_number": N}`. Does NOT contain the actual content — that's in `note_revisions`. |
| `entity_linked` | `NULL` | Note was linked to an entity. `metadata` contains `{"entity_type": "...", "entity_id": "..."}`. |
| `entity_unlinked` | `NULL` | Note was unlinked from an entity. `metadata` contains `{"entity_type": "...", "entity_id": "..."}`. |
| `pin_toggled` | `NULL` | Pin state changed on an entity link. `metadata` contains `{"entity_type": "...", "entity_id": "...", "is_pinned": true/false}`. |
| `record_archived` | `NULL` | Note was soft-deleted. |
| `record_unarchived` | `NULL` | Note was restored from archive. |
| `visibility_changed` | `visibility` | Visibility changed. `old_value`/`new_value` contain the previous/new visibility level. Also emitted as a `field_updated` event. This dedicated type enables efficient auditing of visibility changes. |

### 9.3 Content Events vs. Revisions

The `content_revised` event is a pointer, not a full snapshot:

```json
{
  "event_type": "content_revised",
  "record_id": "not_01HX8A...",
  "new_value": "{\"revision_id\": \"rev_01HX8B...\", \"revision_number\": 7}",
  "metadata": {"content_length_chars": 2450, "word_count": 380},
  "user_id": "usr_01HX...",
  "source": "ui"
}
```

This avoids storing multi-KB content documents in the event table while maintaining a complete audit trail of when content changed, who changed it, and how to find the full content (via `revision_id`).

---

## 10. Full-Text Search

### 10.1 PostgreSQL tsvector Configuration

Full-text search uses PostgreSQL's built-in `tsvector`/`tsquery` with a stored generated column on the `notes` table (defined in Section 5.1):

```sql
search_vector TSVECTOR GENERATED ALWAYS AS (
    setweight(to_tsvector('english', coalesce(title, '')), 'A') ||
    setweight(to_tsvector('english', coalesce(content_text, '')), 'B')
) STORED
```

- **Weight A** (title): Title matches rank higher than content matches.
- **Weight B** (content): Plain text extracted from HTML.
- **English dictionary**: Provides stemming ("meeting" matches "meetings"), stop word removal, and normalization.
- **GIN index**: `idx_notes_search` enables fast full-text queries.

The `search_vector` column updates automatically when `title` or `content_text` changes — no manual sync required (unlike the PoC-era FTS5 approach).

### 10.2 Search Query

```sql
SELECT id, title, visibility, created_by, created_at,
       ts_rank(search_vector, query) AS rank,
       ts_headline('english', content_text, query,
                   'StartSel=<mark>, StopSel=</mark>, MaxWords=35, MinWords=15') AS snippet
FROM notes,
     plainto_tsquery('english', $1) AS query
WHERE search_vector @@ query
  AND archived_at IS NULL
  AND (visibility = 'shared' OR created_by = $2)  -- Visibility filter
ORDER BY rank DESC
LIMIT $3;
```

### 10.3 Search Features

| Feature | Implementation |
|---|---|
| Stemming | PostgreSQL English dictionary: "budget" matches "budgets", "budgeting" |
| Ranking | `ts_rank()` with weight differentiation (title matches > content matches) |
| Snippets | `ts_headline()` with `<mark>` highlighting for result display |
| Visibility filtering | Private notes excluded unless `created_by = current_user` |
| Tenant isolation | Implicit via `search_path` (query runs against tenant's `notes` table) |

### 10.4 Global Notes Search Endpoint

The API provides a dedicated search endpoint (Section 16) that returns ranked results with snippets. This is the primary mechanism for content-based note discovery, complementing the metadata-based Views/Data Sources integration.

---

## 11. File Attachments

### 11.1 Upload Flow

1. User pastes/drops a file into the editor, or uses a toolbar upload button
2. Client POSTs the file to the attachment upload endpoint as multipart form data
3. Server validates MIME type against allowlist and file size against limit
4. File is stored on disk at `{upload_root}/{tenant_id}/{YYYY}/{MM}/{ulid}.{ext}`
5. A `note_attachments` row is created with `note_id = NULL` (orphan)
6. Server returns `{"id": "att_...", "url": "/api/v1/notes/attachments/{id}/{filename}"}`
7. Editor inserts the URL as an image or link in the content

When the note is saved, the client includes attachment IDs in the save payload. The server updates `note_id` on matching `note_attachments` rows to link them to the note.

### 11.2 Storage Layout

```
{upload_root}/
  {tenant_id}/
    2026/
      02/
        01HX8A3B....png
        01HX8A4C....pdf
```

- `{upload_root}` is configurable (default: `data/uploads/`)
- Tenant isolation via directory nesting (tenant A cannot access tenant B's files)
- ULID-based filenames (no user-controlled paths)
- Year/month subdirectories prevent single-directory scaling issues

### 11.3 Cloud Migration Path

The initial implementation uses local disk storage. The storage interface is abstracted behind a `StorageBackend` protocol:

```python
class StorageBackend(Protocol):
    async def store(self, tenant_id: str, filename: str, data: bytes) -> str:
        """Store a file, return the storage path."""
        ...

    async def retrieve(self, storage_path: str) -> bytes:
        """Retrieve file contents by storage path."""
        ...

    async def delete(self, storage_path: str) -> None:
        """Delete a file by storage path."""
        ...

    def get_url(self, storage_path: str) -> str:
        """Get a serving URL for a file."""
        ...
```

The local implementation (`LocalStorageBackend`) stores files on disk. A future `S3StorageBackend` (or GCS equivalent) can be swapped in without changing the Notes subsystem. The `storage_path` column on `note_attachments` stores the backend-relative path, not an absolute filesystem path.

### 11.4 Serving

Attachment serving goes through the API (not direct file access):
- MIME type from the `note_attachments` record
- `Content-Disposition` with original filename
- Tenant isolation check (attachment's note must belong to the requesting tenant)
- Visibility check (if the note is private, only the creator can access attachments)

### 11.5 Orphan Cleanup

`cleanup_orphan_attachments(max_age_hours=24)` runs as a scheduled background job:
1. Queries `note_attachments WHERE note_id IS NULL AND created_at < (now() - interval)`
2. Deletes the file from storage
3. Deletes the database row

This handles abandoned uploads from users who started writing a note, pasted an image, but never saved.

### 11.6 Allowed Upload Types

| Category | MIME Types |
|---|---|
| Images | `image/jpeg`, `image/png`, `image/gif`, `image/webp`, `image/svg+xml` |
| Documents | `application/pdf`, `application/msword`, `application/vnd.openxmlformats-officedocument.wordprocessingml.document`, `application/vnd.ms-excel`, `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`, `text/plain`, `text/csv` |

### 11.7 Configuration

| Setting | Default | Description |
|---|---|---|
| Upload root directory | `data/uploads/` | Root directory for stored files |
| Maximum file size | 10 MB | Per-file upload size limit |
| Orphan cleanup interval | Every 6 hours | Background job frequency |
| Orphan max age | 24 hours | How old an orphan must be before deletion |

---

## 12. @Mentions

### 12.1 Mention Types

Notes can mention any entity type (via the entity's display name) and workspace users:

| Mention Type | Search Scope | Display |
|---|---|---|
| `user` | `platform.users` (workspace members) | User's display name |
| Any object type slug | Records of that entity type in the tenant schema | Entity's `display_name_field` value |

### 12.2 Autocomplete API

`GET /api/v1/notes/mentions?q={query}&type={mention_type}`

Returns up to 10 matching results. If `type` is omitted, searches across users and all entity types with results grouped by type.

### 12.3 Mention Sync

On every content save, the mention extraction behavior:

1. Deletes all existing `note_mentions` rows for the note
2. Walks the `content_json` document tree recursively
3. Extracts all nodes matching the mention contract (Section 7.4)
4. Inserts a `note_mentions` row for each unique `(mention_type, mentioned_id)` pair

This enables queries like "show all notes that mention contact X" and "show all notes that mention user Y" through the `note_mentions` index.

### 12.4 Stale Mention Handling

Mention labels in `content_json` may become stale if the mentioned entity is renamed. The `label` attribute is a display convenience — the `id` attribute is authoritative. The editor can optionally refresh labels when loading a note for editing by resolving `id` values against current entity names.

If a mentioned entity is deleted (archived), the mention node remains in the content as an unresolvable reference. The UI renders it as a dimmed chip with the original label text. The `note_mentions` row is cleaned up by the consistency job that handles stale entity links (Section 6.3).

---

## 13. Pinning

### 13.1 Model

Pinning is **per-entity-link**, not per-note. A note attached to both a Contact and a Company can be pinned on the Contact's note list without affecting its position on the Company's note list.

The `is_pinned` column on `note_entities` controls this:

- `toggle_pin(note_id, entity_type, entity_id)` flips `is_pinned` for the specific entity link.
- Pinned notes sort before unpinned in entity note lists (index: `idx_ne_pinned`).
- A `pin_toggled` event is emitted to `notes_events` (Section 9).

### 13.2 UI Behavior

- Pin icon on the note card header; filled when pinned, outlined when unpinned.
- Clicking the pin toggles state via API call.
- Pinned notes group at the top of the entity's note list, sorted by `created_at DESC` within the pinned group.
- Unpinned notes sort by `updated_at DESC` below the pinned group.

---

## 14. Note Visibility

### 14.1 Visibility Levels

| Level | Who Can See | When to Use |
|---|---|---|
| **Private** (default) | Creator only | Personal observations, draft thoughts, sensitive commentary, meeting prep notes |
| **Shared** | Anyone who can see at least one linked entity (per Permissions PRD visibility rules) | Team knowledge, meeting summaries, account strategy, shared context |

### 14.2 Visibility Rules

**Private notes:**
- Only the `created_by` user can view, edit, or delete the note.
- Private notes are excluded from other users' entity note lists, search results, and API responses.
- Private notes DO appear in the creator's "My Notes" view and search results.
- Admins cannot see other users' private notes (this is a hard privacy boundary).

**Shared notes:**
- Visibility inherits from linked entities via the Permissions PRD visibility model.
- If a note is linked to multiple entities, a user can see the note if they can see **any** of the linked entities (union visibility).
- Edit permissions: Only the creator and users with "edit" access to at least one linked entity can update the note's content or metadata.
- Delete permissions: Only the creator and workspace admins can delete a note.

### 14.3 Visibility Transitions

| Transition | Behavior |
|---|---|
| Private → Shared | The note becomes visible to other users who can see linked entities. A `visibility_changed` event is emitted. This is an intentional publication action. |
| Shared → Private | The note becomes hidden from other users. A `visibility_changed` event is emitted. Users who had the note open receive a "this note is no longer available" message. |

### 14.4 Visibility in Multi-Entity Context

When a shared note is linked to entities with different visibility scopes:

- User A can see Contact X but not Company Y. The note is linked to both.
- User A can see the note (because they can see Contact X).
- When User A views the note, the entity link to Company Y is visible but not clickable (they can see the link exists but cannot navigate to the Company detail page).

### 14.5 Default Visibility

New notes are created with `visibility = 'private'`. The author must explicitly set `visibility = 'shared'` to make the note visible to others. The creation UI includes a visibility toggle (lock icon for private, people icon for shared) with "Private" as the default selection.

---

## 15. Content Sanitization

All `content_html` is sanitized on save before storage to prevent XSS attacks.

### 15.1 Sanitization Library

The backend uses a server-side HTML sanitization library (e.g., `bleach`, `nh3`, or equivalent) to strip dangerous tags and attributes.

### 15.2 Allowlists

**Allowed tags:** `p`, `br`, `strong`, `em`, `u`, `s`, `code`, `pre`, `blockquote`, `h1`–`h6`, `ul`, `ol`, `li`, `a`, `img`, `table`, `thead`, `tbody`, `tr`, `th`, `td`, `span`, `div`, `hr`, `sub`, `sup`, `mark`

**Allowed attributes:** `href`, `target`, `rel` on `a`; `src`, `alt`, `title`, `width`, `height` on `img`; `class`, `data-*` on `span` (for mention rendering); `colspan`, `rowspan` on `td`/`th`

**Stripped:** All other tags including `<script>`, `<iframe>`, `<style>`, `<form>`, `<object>`, `<embed>`. Event handler attributes (`onclick`, `onerror`, etc.) are always stripped.

---

## 16. API Design

### 16.1 Notes CRUD

| Endpoint | Method | Description |
|---|---|---|
| `/api/v1/notes` | GET | List notes. Supports filters: `entity_type` + `entity_id` (notes for an entity), `created_by` (my notes), `visibility`. Paginated. |
| `/api/v1/notes` | POST | Create a note. Body: `title`, `content_json`, `content_html`, `entity_type`, `entity_id`, `visibility`. Returns note with first revision. |
| `/api/v1/notes/{id}` | GET | Get a note with current revision content. |
| `/api/v1/notes/{id}` | PATCH | Update note. Content changes create a new revision. Metadata-only changes (title, visibility) do not. |
| `/api/v1/notes/{id}` | DELETE | Soft-delete (archive) the note. |
| `/api/v1/notes/{id}/unarchive` | POST | Restore an archived note. |

### 16.2 Entity Linking

| Endpoint | Method | Description |
|---|---|---|
| `/api/v1/notes/{id}/entities` | GET | List all entities linked to a note (with entity type, ID, display name, is_pinned). |
| `/api/v1/notes/{id}/entities` | POST | Link note to an additional entity. Body: `entity_type`, `entity_id`. Returns 409 if duplicate. |
| `/api/v1/notes/{id}/entities/{entity_type}/{entity_id}` | DELETE | Unlink note from entity. Returns 400 if it's the last link. |
| `/api/v1/notes/{id}/entities/{entity_type}/{entity_id}/pin` | POST | Toggle pin state for this entity link. |

### 16.3 Revisions

| Endpoint | Method | Description |
|---|---|---|
| `/api/v1/notes/{id}/revisions` | GET | List all revisions (id, revision_number, revised_by, created_at). Newest first. |
| `/api/v1/notes/{id}/revisions/{revision_id}` | GET | Get a specific revision's content (content_json, content_html). |

### 16.4 Attachments

| Endpoint | Method | Description |
|---|---|---|
| `/api/v1/notes/attachments/upload` | POST | Upload a file (multipart). Returns `{id, url, original_name, mime_type, size_bytes}`. |
| `/api/v1/notes/attachments/{id}/{filename}` | GET | Serve an uploaded file with tenant + visibility checks. |

### 16.5 Mentions

| Endpoint | Method | Description |
|---|---|---|
| `/api/v1/notes/mentions` | GET | Mention autocomplete. Params: `q` (search text), `type` (optional mention type filter). |

### 16.6 Search

| Endpoint | Method | Description |
|---|---|---|
| `/api/v1/notes/search` | GET | Full-text search. Params: `q` (search text), `limit`. Returns ranked results with snippets and entity links. Respects visibility. |

### 16.7 Pagination

List endpoints use cursor-based pagination with `updated_at` as the cursor field:
- `?limit=20&after={cursor}` for forward pagination
- Response includes `next_cursor` when more results exist

---

## 17. Virtual Schema & Data Sources

### 17.1 Virtual Schema Table

The Note object type exposes a virtual schema table for Data Sources queries. Only metadata fields are exposed (content is behavior-managed and not in the field registry):

| Virtual Column | Source | Type |
|---|---|---|
| `id` | `notes.id` | Text (prefixed ULID) |
| `title` | `notes.title` | Text |
| `visibility` | `notes.visibility` | Select |
| `revision_count` | `notes.revision_count` | Number |
| `created_by` | `notes.created_by` → `platform.users` | User |
| `updated_by` | `notes.updated_by` → `platform.users` | User |
| `created_at` | `notes.created_at` | Datetime |
| `updated_at` | `notes.updated_at` | Datetime |
| User-added custom fields | As defined | As defined |

### 17.2 Linked Entities Column

The universal attachment relation introduces a new column type in the Views system: **Linked Entities**.

This column displays the entities linked to each note as a list of entity chips (icon + display name). Clicking a chip navigates to that entity's detail page.

In the filter builder, the Linked Entities column supports:
- `has_link_to_type` — Filter notes by linked entity type (e.g., "notes linked to at least one Contact")
- `has_link_to` — Filter notes by specific linked entity (e.g., "notes linked to Contact con_01HX...")
- `link_count` — Filter by number of entity links (e.g., "notes linked to 2+ entities")

### 17.3 Data Source JOINs

Data Sources can JOIN notes to specific entity types through the universal attachment junction:

```sql
-- Notes linked to contacts (via note_entities junction)
SELECT n.id, n.title, c.first_name, c.last_name
FROM notes n
JOIN note_entities ne ON ne.note_id = n.id AND ne.entity_type = 'contacts'
JOIN contacts c ON c.id = ne.entity_id
WHERE n.archived_at IS NULL
  AND (n.visibility = 'shared' OR n.created_by = $current_user);
```

The Data Source query builder surfaces this as: "Notes → linked Contacts" in the JOIN configuration.

---

## 18. Design Decisions

| Decision | Choice | Rationale |
|---|---|---|
| **Framework position** | System object type (`not_` prefix) | Full participation in Views, Data Sources, event sourcing, and the Custom Objects framework. Consistent with how all entities are modeled. |
| **Entity linking** | Universal attachment relation (`target = *`) | Enables attachment to all entity types (system + custom) without per-type relation definitions. No provisioning coupling. Pattern reusable for Tags, Activity Log. |
| **Content in field registry** | Behavior-managed internal | Rich text content doesn't map to typed field values. Revision model is incompatible with field-level deltas. FTS provides better content discovery than field filters. |
| **Revisions + event sourcing** | Both coexist | Events for metadata audit trail (title, visibility, links, pins). Revisions for full content snapshots. Content events point to revisions rather than storing content inline. |
| **FTS approach** | PostgreSQL `tsvector`/`tsquery` with stored generated column | No manual sync needed (auto-updates on column change). Built-in ranking, stemming, snippets. No external infrastructure. |
| **Title field** | Optional | Short notes (quick observations) don't need titles; first line of content suffices in list display. |
| **Content storage** | JSON + HTML + plain text triple | JSON preserves editor state for re-editing. HTML provides pre-rendered display without editor. Plain text enables FTS indexing. |
| **Revision model** | Full snapshots (not diffs) | Each version independently renderable. Simpler, more reliable. Diff display can be layered on as a view concern. |
| **Default visibility** | Private | Privacy-first. Users share intentionally. Prevents accidental exposure of sensitive observations. Matches user expectation for personal notes. |
| **Visibility model** | Two levels (private/shared) | Simple and sufficient. Private = creator only. Shared = inherits entity visibility. Avoids complexity of granular per-user sharing. |
| **Editor** | Editor-agnostic (specify contract) | Flutter ecosystem has multiple viable rich text editors. Decoupling from a specific editor preserves flexibility and prevents PoC-era technology lock-in. |
| **File storage** | Local disk + `StorageBackend` protocol | Minimizes infrastructure for initial deployment. Cloud migration via protocol swap. |
| **Orphan uploads** | `note_id = NULL` until note saves | Images uploaded mid-editing before the note exists. Background cleanup handles abandoned uploads. |
| **Attachment scope** | Note-level (not revision-level) | Files are stable references; only text content changes between revisions. |
| **Entity-agnostic design** | Polymorphic `entity_type`/`entity_id` | One set of tables, API endpoints, and UI components serves all entity types. |
| **Sanitization** | Server-side HTML allowlist | Prevents XSS when rendering `content_html`. Applied before storage, not on display. |

---

## 19. Phasing & Roadmap

### Phase 1 — Core Notes (MVP)

**Goal:** Notes system operational as a system object type with single-entity attachment.

**Scope:**
- Object type registered in framework (`not_` prefix, field registry, event sourcing)
- Notes CRUD API
- Single-entity attachment (create note on an entity)
- Rich text editor integration (Flutter)
- Revision history (append-only, full snapshots)
- Content sanitization
- PostgreSQL FTS with stored generated column
- File attachments with local storage
- Private/shared visibility with private default
- @Mention autocomplete and extraction
- Pinning per entity link
- Entity detail page integration (notes panel on all system entity types)

**Not in Phase 1:** Multi-entity linking, universal attachment for custom objects, Views/Data Sources integration, cloud storage, mention navigation.

### Phase 2 — Multi-Entity & Custom Object Support

**Goal:** Full universal attachment model and custom object integration.

**Scope:**
- Multi-entity linking (add/remove entity links on existing notes)
- Universal attachment relation type registration
- Automatic note support for custom object types
- Custom object detail page integration
- Stale entity link cleanup job
- "My Notes" view (all notes created by current user, across all entities)
- Global notes search page

### Phase 3 — Views & Data Sources

**Goal:** Notes queryable through the standard Views and Data Sources ecosystem.

**Scope:**
- Note virtual schema table in Data Sources
- Linked Entities column type in Views
- Note-to-entity JOIN support in Data Source query builder
- Note list view type (grid of notes with metadata columns)
- Filter support: visibility, created_by, linked entity type/count, date ranges

### Phase 4 — Advanced Features

**Goal:** Cloud storage, graph integration, and collaboration.

**Scope:**
- Cloud storage backend (S3/GCS) via `StorageBackend` protocol swap
- Neo4j sync for note-entity links (`HAS_NOTE` edges)
- Revision diff display (client-side diff between HTML snapshots)
- Note templates (pre-defined content structures for common note types)
- Collaborative editing considerations (real-time or last-write-wins)

---

## 20. Dependencies & Related PRDs

| Dependency | Nature | Details |
|---|---|---|
| **[Custom Objects PRD](custom-objects-prd.md)** | **Structural** | Provides the object type framework, field registry, event sourcing, and tenant schema provisioning that Notes uses. The Universal Attachment Relation extends the relation type model. |
| **[Permissions & Sharing PRD](permissions-sharing-prd_V1.md)** | **Behavioral** | Defines the entity-level visibility rules that shared notes inherit. The Notes visibility model (Section 14) integrates with but does not replace entity permissions. |
| **[Data Sources PRD](data-sources-prd.md)** | **Integration** | The Note virtual schema table (Phase 3) follows the Data Sources convention. The prefixed ULID convention (`not_`) enables automatic entity detection. |
| **[Views & Grid PRD](views-grid-prd_V3.md)** | **Integration** | The Linked Entities column type (Phase 3) is a new column type in the Views system, introduced by the universal attachment pattern. |
| **[Contact Management PRD](contact-management-prd_V4.md)** | **Consumer** | Contact detail pages display notes. Contacts are mentionable. |
| **[Company Management PRD](company-management-prd.md)** | **Consumer** | Company detail pages display notes. Companies are mentionable. |
| **[Communication PRD](email-conversations-prd.md)** | **Consumer** | Conversation detail pages display notes. |
| **[Event Management PRD](events-prd_V2.md)** | **Consumer** | Event detail pages display notes. |

---

## 21. Open Questions

| # | Question | Context | Impact |
|---|---|---|---|
| 1 | Should the Universal Attachment Relation pattern be formalized in the Custom Objects PRD, or remain documented only in the Notes PRD? | If Tags and other subsystems will use the same pattern, it should be a first-class Custom Objects concept. | Custom Objects PRD may need a new section on universal relations. |
| 2 | Should admin override of private note visibility be supported for compliance/legal discovery scenarios? | Current design has a hard privacy boundary — even admins can't see private notes. Some industries require full audit access. | May need a third visibility level or an admin escape hatch with audit logging. |
| 3 | How should notes behave when an entity is transferred between owners (Permissions PRD offboarding flow)? | Shared notes on a transferred entity should remain accessible to the new owner. Private notes of the departing user may need review. | Integration point with Permissions PRD offboarding workflow. |
| 4 | Should the `rich_text` field type be added to Custom Objects Phase 2 for use on custom entities? | Users may want rich text description fields on custom objects (e.g., "Job Description" on Jobs entity). | Depends on whether content architecture decisions here generalize. |
| 5 | Should note FTS participate in a future global search that spans all entity types? | Currently notes have a dedicated search endpoint. A unified search bar that returns contacts, companies, notes, etc. would need to federate across multiple FTS indexes. | Architecture consideration for future global search feature. |
| 6 | How should note content versioning interact with AI-generated notes (e.g., auto-generated meeting summaries)? | If AI generates a meeting note from calendar + conversation data, should the AI generation be a "revision" or a distinct `source` type? | May need a `source` field on revisions (`manual`, `ai_generated`, `template`). |
| 7 | Should mention resolution be eager (resolve IDs on display) or lazy (use cached labels, refresh periodically)? | Eager resolution ensures labels are always current but adds N+1 query cost. Lazy resolution is faster but shows stale names. | Performance vs. accuracy trade-off for mention display. |
| 8 | What is the maximum number of entity links per note? | Unbounded linking could create confusing notes attached to dozens of entities. A reasonable limit (e.g., 20) keeps things manageable. | UX and performance consideration. |

---

## 22. Future Work

### 22.1 Note Templates

Pre-defined content structures for common note types: meeting summary (attendees, discussion points, action items), site visit report, sales call debrief, onboarding checklist. Templates populate the editor with structured headings and placeholder text.

### 22.2 AI-Generated Notes

Integration with conversation intelligence to auto-generate meeting summaries, extract action items, and create follow-up notes. AI-generated notes would have `source = 'ai'` and link to the triggering event/conversation.

### 22.3 Collaborative Editing

Real-time collaborative editing (multiple users editing the same note simultaneously) using operational transform or CRDT. This is a significant architectural addition — the current model is single-writer with revision history.

### 22.4 Note Sharing via Link

Generate a shareable URL for a specific note that can be sent to external parties (non-CRM-users). The shared view would be read-only, time-limited, and would not reveal other entity data.

### 22.5 Rich Media Embeds

Support for embedding rich media beyond images: video thumbnails, tweet embeds, map pins, code snippets with syntax highlighting, and file previews.

### 22.6 Note Export

Export a note (or set of notes for an entity) as PDF, Word, or Markdown for external sharing or archival.

---

## 23. Glossary

| Term | Definition |
|---|---|
| **Note** | A free-form rich text record stored as a system object type in the unified framework. Contains a title, formatted content, revision history, and entity links. |
| **Universal Attachment Relation** | A relation type where the target side is `*` (any registered object type), enabling a source entity type to link to records of any type without requiring individual relation definitions. |
| **Revision** | A full content snapshot stored in `note_revisions`. Every content edit creates a new revision. Revisions are append-only and numbered sequentially per note. |
| **Content Contract** | The agreement between the editor and the backend: the editor produces `content_json` (native format) and `content_html` (rendered); the backend stores both and extracts `content_text` (plain text for FTS). |
| **Visibility** | The access control level on a note: `private` (creator only) or `shared` (inherits entity-level visibility from linked entities). |
| **Pinning** | Per-entity-link flag that sorts a note to the top of an entity's note list. Pinning on entity A does not affect the note's position on entity B. |
| **Orphan Attachment** | A file uploaded during note editing (`note_id = NULL`) that has not yet been linked to a saved note. Cleaned up by a background job after 24 hours. |
| **Mention** | An inline reference to a user or entity within note content, stored as a typed node in `content_json` with an `id`, `mentionType`, and `label`. Extracted to `note_mentions` for reverse lookups. |
| **Display Name Field** | The field designated as the record's human-readable title. For Notes, this is `title`. When `title` is NULL, the UI shows a truncated preview of `content_text`. |
| **Behavior-Managed Content** | Columns on the entity table (`content_json`, `content_html`, `content_text`) that are not registered in the field registry and are managed by a specialized behavior rather than the standard field update pipeline. |
| **Linked Entities Column** | A new column type in the Views system that displays the entities linked to a record through a universal attachment relation, rendered as entity chips with mixed types. |

---

## Appendix A: PoC Implementation Reference

> **Note:** This appendix preserves the implementation details from the Notes PRD v1.0 (PoC era, Phases 17–18) for historical reference. The PoC uses SQLite, FTS5, plain UUIDs (no prefixed IDs), Tiptap via ESM import map (not Flutter), HTMX-driven interactions (not REST API), `customer_id` column-based tenant isolation (not schema-per-tenant), and a monolithic `poc/` codebase. The production architecture described in Sections 1–22 supersedes this implementation.

### A.1 PoC Status

**Implemented (Schema v13, 2026-02-14):**

- SQLite `notes` table with `customer_id` tenant isolation.
- SQLite `note_entities` junction table (Phase 18) with hardcoded entity type CHECK constraint (`contact`, `company`, `conversation`, `event`, `project`).
- SQLite `note_revisions` table with append-only revision history.
- SQLite `note_attachments` table with orphan upload support.
- SQLite `note_mentions` table with mention extraction.
- SQLite FTS5 virtual table `notes_fts` with porter stemming and manual sync.
- v11→v12 migration script (`poc/migrate_to_v12.py`) — initial notes tables.
- v12→v13 migration script (`poc/migrate_to_v13.py`) — multi-entity `note_entities` junction.
- Core CRUD in `poc/notes.py` (~580 lines): create, update, get, list, delete, toggle_pin, add/remove entity, get entities, revisions, search, mentions, attachments.
- Tiptap v2.11.5 rich text editor loaded via ESM import map from `esm.sh` CDN.
- HTMX-driven web UI: note cards, inline editing, revision history, search page.
- 14 FastAPI web routes under `/notes` prefix returning HTML partials.
- HTML sanitization via `bleach` library.
- 71 tests in `tests/test_notes.py`.

### A.2 PoC Data Model

#### Schema v12 (Phase 17): Initial notes

| Table | Columns | Notes |
|---|---|---|
| `notes` | `id`, `customer_id`, `entity_type`, `entity_id`, `title`, `current_revision_id`, `is_pinned`, `created_by`, `updated_by`, `created_at`, `updated_at` | Single-entity attachment via `entity_type`/`entity_id` columns directly on the note. |
| `note_revisions` | `id`, `note_id`, `revision_number`, `content_json`, `content_html`, `revised_by`, `created_at` | Append-only, numbered, CASCADE delete. |
| `note_attachments` | `id`, `note_id`, `filename`, `original_name`, `mime_type`, `size_bytes`, `storage_path`, `uploaded_by`, `created_at` | Nullable `note_id` for orphan uploads. |
| `note_mentions` | `id`, `note_id`, `mention_type`, `mentioned_id`, `created_at` | Extracted from Tiptap JSON. |
| `notes_fts` | `note_id (UNINDEXED)`, `title`, `content_text` | FTS5 virtual table, porter unicode61 tokenizer. |

#### Schema v13 (Phase 18): Multi-entity attachment

- `entity_type`, `entity_id`, `is_pinned` moved from `notes` to new `note_entities` junction table.
- `note_entities` PK: `(note_id, entity_type, entity_id)`.
- Entity type CHECK constraint: `contact`, `company`, `conversation`, `event`, `project`.

### A.3 PoC File Inventory

#### New Files (11)

| File | Lines | Purpose |
|---|---|---|
| `poc/notes.py` | ~580 | Core CRUD, FTS, mentions, attachments, search, multi-entity |
| `poc/migrate_to_v12.py` | ~155 | Schema migration v11→v12 |
| `poc/migrate_to_v13.py` | ~130 | Schema migration v12→v13 (note_entities) |
| `poc/web/routes/notes.py` | ~380 | FastAPI router (14 endpoints, HTML partial responses) |
| `poc/web/static/notes.js` | ~220 | Tiptap editor ES module |
| `poc/web/static/notes.css` | ~110 | Editor and note card styles |
| `poc/web/templates/notes/_notes.html` | ~30 | Note list + add form partial |
| `poc/web/templates/notes/_note_card.html` | ~40 | Single note display partial |
| `poc/web/templates/notes/_note_editor.html` | ~25 | Edit form partial |
| `poc/web/templates/notes/_note_revisions.html` | ~30 | Revision history partial |
| `poc/web/templates/notes/search.html` | ~48 | Global notes search page |
| `tests/test_notes.py` | ~470 | 71 tests (see A.4) |

#### Modified Files (15)

| File | Change |
|---|---|
| `poc/database.py` | 5 table DDLs + 7 indexes + FTS5 virtual table in `init_db` |
| `poc/config.py` | `UPLOAD_DIR`, `MAX_UPLOAD_SIZE_MB`, `ALLOWED_UPLOAD_TYPES` |
| `poc/web/app.py` | Import + register `notes.router` with `prefix="/notes"` |
| `poc/web/templates/base.html` | Tiptap import map, `notes.css` link, `notes.js` script, "Notes" nav link |
| `poc/web/templates/contacts/detail.html` | `{% include "notes/_notes.html" %}` |
| `poc/web/templates/companies/detail.html` | `{% include "notes/_notes.html" %}` |
| `poc/web/templates/conversations/detail.html` | `{% include "notes/_notes.html" %}` |
| `poc/web/templates/events/detail.html` | `{% include "notes/_notes.html" %}` |
| `poc/web/templates/projects/detail.html` | `{% include "notes/_notes.html" %}` |
| `poc/web/routes/contacts.py` | `notes` + `entity_type` + `entity_id` in detail context |
| `poc/web/routes/companies.py` | Same |
| `poc/web/routes/conversations.py` | Same |
| `poc/web/routes/events.py` | Same |
| `poc/web/routes/projects.py` | Same |
| `pyproject.toml` | Added `bleach>=6.0.0` |

### A.4 PoC Test Suite

71 tests in `tests/test_notes.py`:

| Test Class | Count | Covers |
|---|---|---|
| `TestCreateNote` | 5 | Basic create, no title, JSON content, invalid entity type, all entity types |
| `TestGetNote` | 2 | Existing, nonexistent |
| `TestGetNotesForEntity` | 4 | List, filtering, pinned-first sort, author name |
| `TestUpdateNote` | 4 | Basic update, revision creation, nonexistent, title preservation |
| `TestDeleteNote` | 3 | Existing, nonexistent, cascade |
| `TestTogglePin` | 2 | Pin/unpin, nonexistent |
| `TestRevisions` | 3 | List, single, nonexistent |
| `TestSearch` | 6 | Basic, by title, empty query, no results, after edit, after delete |
| `TestExtractPlainText` | 3 | Simple, nested, empty |
| `TestMentions` | 4 | Extract from doc, no mentions, sync on create, sync on update |
| `TestSearchMentionables` | 4 | Users, contacts, companies, empty query |
| `TestAttachments` | 2 | Orphan, with note |
| `TestNotesWebList` | 2 | With notes, empty |
| `TestNotesWebCreate` | 2 | Success, missing entity |
| `TestNotesWebEdit` | 2 | Form, nonexistent |
| `TestNotesWebUpdate` | 2 | Success, nonexistent |
| `TestNotesWebDelete` | 2 | Success, nonexistent |
| `TestNotesWebPin` | 2 | Toggle, nonexistent |
| `TestNotesWebRevisions` | 3 | List, detail, nonexistent |
| `TestNotesWebUpload` | 4 | Image, disallowed type, too large, serve file |
| `TestNotesWebMentions` | 2 | Autocomplete, empty query |
| `TestNotesWebSearch` | 2 | With results, empty |
| `TestEntityIntegration` | 3 | Contact, company, conversation detail pages show notes |
| `TestSanitization` | 2 | Script stripped, allowed tags preserved |
| `TestMigration` | 1 | All 5 tables created |

Full suite at time of implementation: 1147 tests, 0 failures, 0 regressions.

### A.5 PoC Tiptap Configuration

**Version:** Tiptap v2.11.5

**Delivery:** ESM import map via `esm.sh` CDN (no bundler):

```json
{
  "imports": {
    "@tiptap/core": "https://esm.sh/@tiptap/core@2.11.5",
    "@tiptap/starter-kit": "https://esm.sh/@tiptap/starter-kit@2.11.5",
    "@tiptap/extension-image": "https://esm.sh/@tiptap/extension-image@2.11.5",
    "@tiptap/extension-link": "https://esm.sh/@tiptap/extension-link@2.11.5",
    "@tiptap/extension-placeholder": "https://esm.sh/@tiptap/extension-placeholder@2.11.5",
    "@tiptap/extension-mention": "https://esm.sh/@tiptap/extension-mention@2.11.5"
  }
}
```

**Editor Module** (`notes.js`): Lazy-loads Tiptap, builds toolbar (Bold, Italic, Strikethrough, Code, H1/H2/H3, Bullet/Ordered list, Blockquote, Horizontal rule, Image URL, Link), syncs content to hidden form fields, re-initializes after HTMX swaps, handles image paste/drop upload.

### A.6 PoC Web Routes

14 endpoints under `/notes` prefix, returning HTML partials for HTMX swap:

| Method | Path | Purpose |
|---|---|---|
| GET | `/notes?entity_type=X&entity_id=Y` | List notes for entity |
| POST | `/notes` | Create note |
| GET | `/notes/{id}/edit` | Get editor for existing note |
| PUT | `/notes/{id}` | Update note (new revision) |
| DELETE | `/notes/{id}` | Delete note + revisions |
| POST | `/notes/{id}/pin` | Toggle pin |
| GET | `/notes/{id}/revisions` | Revision list |
| GET | `/notes/{id}/revisions/{rev_id}` | View old revision |
| POST | `/notes/upload` | Upload file (multipart) |
| GET | `/notes/files/{id}/{filename}` | Serve uploaded file |
| GET | `/notes/mentions?q=X&type=Y` | Mention autocomplete |
| GET | `/notes/search?q=X` | Global search |
| POST | `/notes/{id}/entities` | Link to additional entity |
| DELETE | `/notes/{id}/entities/{et}/{eid}` | Unlink from entity |
