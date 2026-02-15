# Product Requirements Document: Notes System

## CRMExtender — Entity-Agnostic Notes with Rich Text, Revisions & Search

**Version:** 1.0
**Date:** 2026-02-14
**Status:** Implemented (Phase 17)
**Schema Version:** v12

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Problem Statement](#2-problem-statement)
3. [Goals & Success Metrics](#3-goals--success-metrics)
4. [Data Model](#4-data-model)
5. [CRUD Operations](#5-crud-operations)
6. [Rich Text Editor](#6-rich-text-editor)
7. [File Attachments](#7-file-attachments)
8. [Revision History](#8-revision-history)
9. [@Mentions](#9-mentions)
10. [Full-Text Search](#10-full-text-search)
11. [Pinning](#11-pinning)
12. [HTML Sanitization](#12-html-sanitization)
13. [Web Routes & API](#13-web-routes--api)
14. [Templates & UI](#14-templates--ui)
15. [Entity Integration](#15-entity-integration)
16. [Configuration](#16-configuration)
17. [Security & Tenant Isolation](#17-security--tenant-isolation)
18. [File Inventory](#18-file-inventory)
19. [Testing](#19-testing)
20. [Migration](#20-migration)
21. [Design Decisions](#21-design-decisions)

---

## 1. Executive Summary

The Notes system adds free-form, rich-text notes to every entity type in CRMExtender: contacts, companies, conversations, events, and projects. Notes are entity-agnostic (polymorphic via `entity_type`/`entity_id`), following the same pattern used by `addresses`, `phone_numbers`, and `email_addresses`. Each note maintains a full append-only revision history, supports file attachments (images, documents), @mentions of users and entities, pinning, and global full-text search via SQLite FTS5.

The editor uses Tiptap (a ProseMirror-based rich-text framework) loaded via ESM import map from `esm.sh`, consistent with the project's CDN-only approach (no build tooling). Content is dual-stored as Tiptap JSON (source of truth for editing) and pre-rendered HTML (for display without server-side rendering).

---

## 2. Problem Statement

Before Phase 17, CRMExtender had no way to attach free-form observations to entities. Users needed to record:

- Meeting summaries and action items on contacts
- Research notes on companies
- Internal commentary on conversations
- Planning notes on projects and events
- Shared context with uploaded screenshots or documents

The only text field available was the `notes` column on `contact_companies` (affiliations), which was narrow in scope and lacked formatting, history, or searchability.

---

## 3. Goals & Success Metrics

| Goal                       | Metric                                                                  |
| -------------------------- | ----------------------------------------------------------------------- |
| Attach notes to any entity | Notes available on all 5 entity detail pages                            |
| Rich formatting            | Bold, italic, headings, lists, blockquotes, code, tables, images, links |
| Revision history           | Every edit creates a new revision; any version viewable                 |
| File attachments           | Paste/drop images into editor; upload documents                         |
| Cross-entity search        | Global FTS5 search across all notes from nav bar                        |
| @Mentions                  | Reference users, contacts, companies in note content                    |
| No regressions             | Full test suite passes (1147 tests)                                     |

---

## 4. Data Model

### 4.1 Tables (5 new, schema v12)

#### `notes` — Entity-agnostic note header

| Column                | Type    | Description                                                                |
| --------------------- | ------- | -------------------------------------------------------------------------- |
| `id`                  | TEXT PK | UUID                                                                       |
| `customer_id`         | TEXT FK | Tenant isolation (direct column avoids entity-table joins)                 |
| `entity_type`         | TEXT    | CHECK constraint: `contact`, `company`, `conversation`, `event`, `project` |
| `entity_id`           | TEXT    | ID of the parent entity                                                    |
| `title`               | TEXT    | Optional; short notes don't need one                                       |
| `is_pinned`           | INTEGER | 0 or 1; pinned notes sort first                                            |
| `current_revision_id` | TEXT    | Points to the latest `note_revisions` row                                  |
| `created_by`          | TEXT FK | `users.id`                                                                 |
| `updated_by`          | TEXT FK | `users.id`                                                                 |
| `created_at`          | TEXT    | ISO 8601 UTC                                                               |
| `updated_at`          | TEXT    | ISO 8601 UTC                                                               |

#### `note_revisions` — Append-only revision history

| Column            | Type            | Description                                                         |
| ----------------- | --------------- | ------------------------------------------------------------------- |
| `id`              | TEXT PK         | UUID                                                                |
| `note_id`         | TEXT FK CASCADE | Parent note                                                         |
| `revision_number` | INTEGER         | Monotonically increasing per note; UNIQUE(note_id, revision_number) |
| `content_json`    | TEXT            | Tiptap JSON document (source of truth for editing)                  |
| `content_html`    | TEXT            | Pre-rendered HTML (source of truth for display)                     |
| `revised_by`      | TEXT FK         | `users.id`                                                          |
| `created_at`      | TEXT            | ISO 8601 UTC                                                        |

#### `note_attachments` — Uploaded files

| Column          | Type            | Description                                          |
| --------------- | --------------- | ---------------------------------------------------- |
| `id`            | TEXT PK         | UUID                                                 |
| `note_id`       | TEXT FK CASCADE | Nullable for orphan uploads (linked when note saves) |
| `filename`      | TEXT            | UUID-based filename on disk                          |
| `original_name` | TEXT            | User-facing filename                                 |
| `mime_type`     | TEXT            | Validated against allowlist                          |
| `size_bytes`    | INTEGER         | File size                                            |
| `storage_path`  | TEXT            | Absolute path on disk                                |
| `uploaded_by`   | TEXT FK         | `users.id`                                           |
| `created_at`    | TEXT            | ISO 8601 UTC                                         |

#### `note_mentions` — Extracted @mentions

| Column         | Type            | Description                                                             |
| -------------- | --------------- | ----------------------------------------------------------------------- |
| `id`           | TEXT PK         | UUID                                                                    |
| `note_id`      | TEXT FK CASCADE | Parent note                                                             |
| `mention_type` | TEXT            | CHECK: `user`, `contact`, `company`, `conversation`, `event`, `project` |
| `mentioned_id` | TEXT            | ID of the mentioned entity                                              |
| `created_at`   | TEXT            | ISO 8601 UTC                                                            |

#### `notes_fts` — FTS5 virtual table

| Column         | Type           | Description                               |
| -------------- | -------------- | ----------------------------------------- |
| `note_id`      | TEXT UNINDEXED | Join key (not searchable)                 |
| `title`        | TEXT           | Note title, tokenized                     |
| `content_text` | TEXT           | Plain text extracted from HTML, tokenized |

Tokenizer: `porter unicode61` (stemming + Unicode normalization).

### 4.2 Indexes

| Index                       | Columns                                                     | Purpose                  |
| --------------------------- | ----------------------------------------------------------- | ------------------------ |
| `idx_notes_entity`          | `(entity_type, entity_id)`                                  | List notes for an entity |
| `idx_notes_customer`        | `(customer_id)`                                             | Tenant-scoped queries    |
| `idx_notes_pinned`          | `(entity_type, entity_id, is_pinned DESC, updated_at DESC)` | Sort pinned first        |
| `idx_note_revisions_note`   | `(note_id)`                                                 | Revision lookup          |
| `idx_note_attachments_note` | `(note_id)`                                                 | Attachment lookup        |
| `idx_note_mentions_note`    | `(note_id)`                                                 | Mentions for a note      |
| `idx_note_mentions_target`  | `(mention_type, mentioned_id)`                              | "Where am I mentioned?"  |

### 4.3 Entity Relationship Diagram

```
notes 1──* note_revisions    (CASCADE delete)
notes 1──* note_attachments   (CASCADE delete; nullable note_id for orphans)
notes 1──* note_mentions      (CASCADE delete)
notes ···> notes_fts          (manual sync; not FK-linked)

notes ──> customers           (customer_id FK)
notes ──> users               (created_by, updated_by)
note_revisions ──> users      (revised_by)
note_attachments ──> users    (uploaded_by)
```

---

## 5. CRUD Operations

All CRUD lives in `poc/notes.py`. Functions follow the same patterns as `poc/hierarchy.py`.

| Function               | Signature                                                                                         | Description                                                        |
| ---------------------- | ------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------ |
| `create_note`          | `(customer_id, entity_type, entity_id, *, title, content_json, content_html, created_by) -> dict` | Creates note + first revision + FTS + mentions                     |
| `update_note`          | `(note_id, *, title, content_json, content_html, updated_by) -> dict \| None`                     | Creates new revision, updates note header, re-syncs FTS + mentions |
| `get_note`             | `(note_id) -> dict \| None`                                                                       | Note with current revision content                                 |
| `get_notes_for_entity` | `(entity_type, entity_id, *, customer_id) -> list[dict]`                                          | All notes for an entity, pinned first                              |
| `get_recent_notes`     | `(*, customer_id, limit) -> list[dict]`                                                           | Most recent notes across all entities                              |
| `delete_note`          | `(note_id) -> bool`                                                                               | Deletes note + cascades revisions/mentions + removes FTS entry     |
| `toggle_pin`           | `(note_id) -> dict \| None`                                                                       | Flips `is_pinned` between 0 and 1                                  |
| `get_revisions`        | `(note_id) -> list[dict]`                                                                         | All revisions, newest first                                        |
| `get_revision`         | `(revision_id) -> dict \| None`                                                                   | Single revision by ID                                              |
| `search_notes`         | `(query, *, customer_id, limit) -> list[dict]`                                                    | FTS5 MATCH with ranked results and snippets                        |

### Update semantics

Updates are **non-destructive**: every edit creates a new `note_revisions` row with an incremented `revision_number`. The note header's `current_revision_id` pointer is advanced to the new revision. Old revisions remain queryable. If `title` is not provided on update, the existing title is preserved.

---

## 6. Rich Text Editor

### 6.1 Technology

- **Tiptap** v2.11.5 — ProseMirror-based, modular rich-text editor
- **Delivery**: ESM import map via `esm.sh` CDN (no bundler, no node_modules)
- **Extensions**: StarterKit, Image, Link, Placeholder, Mention

### 6.2 Import Map (in `base.html`)

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

### 6.3 Editor Module (`notes.js`)

The `notes.js` ES module:

1. **Lazy-loads** Tiptap on first page load (fails gracefully to `<textarea>` fallback)
2. **Initializes** editors on all `.note-editor` elements
3. **Builds a toolbar** with: Bold, Italic, Strikethrough, Code, H1/H2/H3, Bullet/Ordered list, Blockquote, Horizontal rule, Image URL, Link
4. **Syncs** editor content to hidden `content_json` and `content_html` form fields on every keystroke
5. **Re-initializes** after HTMX swaps (listens to `htmx:afterSwap` and `htmx:afterSettle`)
6. **Handles image paste/drop**: intercepts clipboard/drag events, POSTs to `/notes/upload`, inserts returned URL

### 6.4 Dual Content Storage

| Field          | Format                  | Purpose                                                                |
| -------------- | ----------------------- | ---------------------------------------------------------------------- |
| `content_json` | Tiptap/ProseMirror JSON | Source of truth for re-editing; preserves structure, mentions, etc.    |
| `content_html` | Rendered HTML string    | Display without server-side rendering; indexed for FTS after stripping |

On create/update, the editor populates both fields. On edit, the editor rehydrates from `content_json` (passed via `data-content` attribute).

---

## 7. File Attachments

### 7.1 Upload Flow

1. User pastes/drops an image into the editor, or uses the toolbar button
2. `notes.js` POSTs the file to `/notes/upload` as multipart form data
3. Server validates MIME type against allowlist and file size against limit
4. File is stored at `data/uploads/{customer_id}/{YYYY}/{MM}/{uuid}.{ext}`
5. A `note_attachments` row is created with `note_id=NULL` (orphan)
6. Server returns `{"id": "...", "url": "/notes/files/{id}/{filename}"}`
7. Editor inserts the URL as an `<img>` tag

### 7.2 Storage Layout

```
data/uploads/
  cust-default/
    2026/
      02/
        a1b2c3d4-....png
        e5f6a7b8-....pdf
```

### 7.3 Serving

`GET /notes/files/{attachment_id}/{filename}` serves files via `FileResponse` with:

- MIME type from the `note_attachments` record
- `Content-Disposition` with original filename
- Tenant isolation check (`customer_id` must appear in storage path)

### 7.4 Orphan Cleanup

`cleanup_orphan_attachments(max_age_hours=24)` deletes `note_attachments` rows with `note_id IS NULL` older than the specified age, and removes the corresponding files from disk.

### 7.5 Allowed Upload Types

Images: JPEG, PNG, GIF, WebP, SVG. Documents: PDF, Word (.doc/.docx), Excel (.xls/.xlsx), plain text, CSV.

---

## 8. Revision History

### 8.1 Model

Every save creates a new `note_revisions` row. Revisions are:

- **Append-only**: never updated or deleted individually (only via CASCADE when parent note is deleted)
- **Numbered**: `revision_number` starts at 1 and increments per note
- **Unique**: `UNIQUE(note_id, revision_number)` constraint

### 8.2 UI

- The note card footer shows "v{N}" as a clickable link when `revision_number > 1`
- Clicking loads `_note_revisions.html` inline via HTMX — a table of all versions
- Each past revision has a "View" link that loads its `content_html` inline
- The current revision is labeled "(current)"

### 8.3 Design: Versions Not Diffs

The system stores and displays complete versions, not diffs. This was chosen because:

- Simpler implementation and display
- Each version is independently renderable
- Diff computation can be added later as a view layer concern without schema changes

---

## 9. @Mentions

### 9.1 Autocomplete

The Tiptap Mention extension is configured with a `suggestion` object that:

1. Calls `GET /notes/mentions?q={query}&type=user` on each keystroke after `@`
2. Renders a positioned popup with matching results
3. On selection, inserts a mention node into the document

### 9.2 Mention Node Structure (Tiptap JSON)

```json
{
  "type": "mention",
  "attrs": {
    "id": "user-admin",
    "mentionType": "user",
    "label": "Admin User"
  }
}
```

### 9.3 Mention Sync

On every create/update, `_sync_mentions()`:

1. Deletes all existing `note_mentions` rows for the note
2. Recursively walks the Tiptap JSON document tree
3. Extracts all nodes with `type == "mention"`
4. Inserts a `note_mentions` row for each `(mentionType, id)` pair

This enables future queries like "show all notes that mention contact X".

### 9.4 Rendering

Mention nodes render as styled `<span class="mention">` chips with the label text, styled via `notes.css`.

---

## 10. Full-Text Search

### 10.1 FTS5 Configuration

```sql
CREATE VIRTUAL TABLE notes_fts USING fts5(
    note_id UNINDEXED,
    title,
    content_text,
    tokenize='porter unicode61'
);
```

- **Porter stemming**: "meeting" matches "meetings", "met"
- **Unicode normalization**: handles accented characters
- **Manual sync**: the FTS table is updated explicitly (not via triggers) to avoid WAL-mode issues

### 10.2 Index Lifecycle

| Event         | Action                              |
| ------------- | ----------------------------------- |
| `create_note` | Insert into `notes_fts`             |
| `update_note` | Delete + re-insert into `notes_fts` |
| `delete_note` | Delete from `notes_fts`             |

### 10.3 Plain Text Extraction

`_extract_plain_text(content_html)` uses Python's `HTMLParser` to strip all tags, producing plain text for FTS indexing. Falls back to regex tag removal on parse errors.

### 10.4 Search Results

`search_notes()` uses `FTS5 MATCH` with `ORDER BY rank` and returns `snippet()` with `<mark>` highlighting for context display.

### 10.5 Notes Page

The "Notes" nav link goes to `/notes/search`, which:

- Shows **recent notes** (most recently updated, all entities) when no query is entered
- Shows **FTS search results** with highlighted snippets when a query is provided
- Each result links to the parent entity's detail page

---

## 11. Pinning

- Any note can be pinned via the "Pin" button on the note card
- `toggle_pin()` flips `is_pinned` between 0 and 1
- Pinned notes sort before unpinned in entity note lists (index: `is_pinned DESC, updated_at DESC`)
- Pin state is indicated by a pushpin icon in the card header
- Button label toggles between "Pin" and "Unpin"

---

## 12. HTML Sanitization

All `content_html` is sanitized on save via `bleach.clean()` before storage:

**Allowed tags**: `p`, `br`, `strong`, `em`, `u`, `s`, `code`, `pre`, `blockquote`, `h1`-`h6`, `ul`, `ol`, `li`, `a`, `img`, `table`, `thead`, `tbody`, `tr`, `th`, `td`, `span`, `div`, `hr`, `sub`, `sup`, `mark`

**Allowed attributes**: `href`/`target`/`rel` on `a`, `src`/`alt`/`title`/`width`/`height` on `img`, `class`/`data-*` on `span` (for mentions), `colspan`/`rowspan` on `td`/`th`

All other tags (including `<script>`, `<iframe>`, `<style>`, `<form>`) are stripped. Templates render with `|safe` since content has been pre-sanitized.

---

## 13. Web Routes & API

All routes are registered under the `/notes` prefix.

| Method | Path                               | Purpose                      | Returns                               |
| ------ | ---------------------------------- | ---------------------------- | ------------------------------------- |
| GET    | `/notes?entity_type=X&entity_id=Y` | List notes for entity        | `_notes.html` partial                 |
| POST   | `/notes`                           | Create note                  | `_notes.html` partial (full refresh)  |
| GET    | `/notes/{id}/edit`                 | Get editor for existing note | `_note_editor.html` partial           |
| PUT    | `/notes/{id}`                      | Update note (new revision)   | `_note_card.html` partial             |
| DELETE | `/notes/{id}`                      | Delete note + revisions      | Empty 200                             |
| POST   | `/notes/{id}/pin`                  | Toggle pin                   | `_note_card.html` partial             |
| GET    | `/notes/{id}/revisions`            | Revision list                | `_note_revisions.html` partial        |
| GET    | `/notes/{id}/revisions/{rev_id}`   | View old revision            | HTML content                          |
| POST   | `/notes/upload`                    | Upload file (multipart)      | JSON `{"id", "url", "original_name"}` |
| GET    | `/notes/files/{id}/{filename}`     | Serve uploaded file          | FileResponse                          |
| GET    | `/notes/mentions?q=X&type=Y`       | Mention autocomplete         | JSON array                            |
| GET    | `/notes/search?q=X`                | Notes page / global search   | `search.html`                         |

All mutating routes check `customer_id` for tenant isolation. Edit/update/delete/pin routes return 404 if the note doesn't belong to the current customer.

---

## 14. Templates & UI

### 14.1 Template Files

| Template                     | Purpose                                                                                                                         |
| ---------------------------- | ------------------------------------------------------------------------------------------------------------------------------- |
| `notes/_notes.html`          | Reusable partial: "Add Note" form + note list. Included in all entity detail pages via `{% include "notes/_notes.html" %}`      |
| `notes/_note_card.html`      | Single note display with pin/edit/delete buttons, content, author, timestamp, revision link. HTMX-swappable by `id="note-{id}"` |
| `notes/_note_editor.html`    | Edit form with title input + Tiptap editor + Save/Cancel buttons. Replaces the card via HTMX swap                               |
| `notes/_note_revisions.html` | Expandable revision history table, loaded inline below a note card                                                              |
| `notes/search.html`          | Full page: search input + recent notes or search results with snippets                                                          |

### 14.2 HTMX Interactions

All note interactions are HTMX-driven (no full page reloads):

- **Create**: form `hx-post="/notes"` replaces `#notes-section`
- **Edit**: "Edit" button `hx-get` swaps the card for the editor form
- **Save**: editor form `hx-put` swaps back to the updated card
- **Cancel**: button `hx-get` reloads the full notes section
- **Delete**: button `hx-delete` with `hx-confirm` removes the card
- **Pin**: button `hx-post` swaps the card with updated pin state
- **Revisions**: link `hx-get` loads history inline below the card

### 14.3 Styling

`notes.css` provides styles for:

- Note cards (border, padding, header layout)
- Editor wrapper, toolbar buttons (with active state), separator
- Contenteditable area (min-height, focus outline)
- Placeholder text (via `::before` pseudo-element)
- Mention chips (background pill)
- Content display (images, blockquotes, code, tables)
- Search result highlights (`<mark>`)

---

## 15. Entity Integration

Notes are integrated into all 5 entity detail pages:

| Entity       | Route File                        | Template                    | Context Variables Added             |
| ------------ | --------------------------------- | --------------------------- | ----------------------------------- |
| Contact      | `poc/web/routes/contacts.py`      | `contacts/detail.html`      | `notes`, `entity_type`, `entity_id` |
| Company      | `poc/web/routes/companies.py`     | `companies/detail.html`     | `notes`, `entity_type`, `entity_id` |
| Conversation | `poc/web/routes/conversations.py` | `conversations/detail.html` | `notes`, `entity_type`, `entity_id` |
| Event        | `poc/web/routes/events.py`        | `events/detail.html`        | `notes`, `entity_type`, `entity_id` |
| Project      | `poc/web/routes/projects.py`      | `projects/detail.html`      | `notes`, `entity_type`, `entity_id` |

Each detail route calls `get_notes_for_entity(entity_type, entity_id, customer_id=cid)` and passes the result to the template, which includes `notes/_notes.html` in the main content column.

---

## 16. Configuration

Three new settings in `poc/config.py`:

| Setting                | Env Variable             | Default             | Description                        |
| ---------------------- | ------------------------ | ------------------- | ---------------------------------- |
| `UPLOAD_DIR`           | `CRM_UPLOAD_DIR`         | `data/uploads/`     | Root directory for uploaded files  |
| `MAX_UPLOAD_SIZE_MB`   | `CRM_MAX_UPLOAD_SIZE_MB` | `10`                | Maximum file upload size in MB     |
| `ALLOWED_UPLOAD_TYPES` | —                        | Set of MIME strings | Allowlist of uploadable MIME types |

---

## 17. Security & Tenant Isolation

| Concern                | Mechanism                                                                                                                       |
| ---------------------- | ------------------------------------------------------------------------------------------------------------------------------- |
| Cross-tenant access    | `customer_id` column on `notes`; all routes check `note.customer_id == request.state.customer_id`                               |
| XSS via note content   | `bleach.clean()` strips dangerous tags/attributes before storage; `content_html\|safe` is safe because content is pre-sanitized |
| File upload attacks    | MIME type validated against allowlist; filenames are UUID-generated (no user-controlled paths); size limit enforced             |
| File serving isolation | `/notes/files/` route verifies `customer_id` appears in storage path                                                            |
| Authenticated access   | All routes go through the existing `AuthMiddleware`; auth bypass mode respects `CRM_AUTH_ENABLED`                               |

---

## 18. File Inventory

### New Files (11)

| File                                           | Lines | Purpose                                       |
| ---------------------------------------------- | ----- | --------------------------------------------- |
| `poc/notes.py`                                 | ~510  | Core CRUD, FTS, mentions, attachments, search |
| `poc/migrate_to_v12.py`                        | ~155  | Schema migration v11 to v12                   |
| `poc/web/routes/notes.py`                      | ~340  | FastAPI router (12 endpoints)                 |
| `poc/web/static/notes.js`                      | ~220  | Tiptap editor ES module                       |
| `poc/web/static/notes.css`                     | ~110  | Editor and note card styles                   |
| `poc/web/templates/notes/_notes.html`          | ~30   | Note list + add form partial                  |
| `poc/web/templates/notes/_note_card.html`      | ~40   | Single note display partial                   |
| `poc/web/templates/notes/_note_editor.html`    | ~25   | Edit form partial                             |
| `poc/web/templates/notes/_note_revisions.html` | ~30   | Revision history partial                      |
| `poc/web/templates/notes/search.html`          | ~48   | Global notes page                             |
| `tests/test_notes.py`                          | ~470  | 71 tests                                      |

### Modified Files (15)

| File                                          | Change                                                                   |
| --------------------------------------------- | ------------------------------------------------------------------------ |
| `poc/database.py`                             | 5 table DDLs + 7 indexes + FTS5 virtual table in `init_db`               |
| `poc/config.py`                               | `UPLOAD_DIR`, `MAX_UPLOAD_SIZE_MB`, `ALLOWED_UPLOAD_TYPES`               |
| `poc/web/app.py`                              | Import + register `notes.router` with `prefix="/notes"`                  |
| `poc/web/templates/base.html`                 | Tiptap import map, `notes.css` link, `notes.js` script, "Notes" nav link |
| `poc/web/templates/contacts/detail.html`      | `{% include "notes/_notes.html" %}`                                      |
| `poc/web/templates/companies/detail.html`     | `{% include "notes/_notes.html" %}`                                      |
| `poc/web/templates/conversations/detail.html` | `{% include "notes/_notes.html" %}`                                      |
| `poc/web/templates/events/detail.html`        | `{% include "notes/_notes.html" %}`                                      |
| `poc/web/templates/projects/detail.html`      | `{% include "notes/_notes.html" %}`                                      |
| `poc/web/routes/contacts.py`                  | `notes` + `entity_type` + `entity_id` in detail context                  |
| `poc/web/routes/companies.py`                 | Same                                                                     |
| `poc/web/routes/conversations.py`             | Same                                                                     |
| `poc/web/routes/events.py`                    | Same                                                                     |
| `poc/web/routes/projects.py`                  | Same                                                                     |
| `pyproject.toml`                              | Added `bleach>=6.0.0`                                                    |

---

## 19. Testing

**71 tests** in `tests/test_notes.py`, organized by feature:

| Test Class               | Count | Covers                                                                      |
| ------------------------ | ----- | --------------------------------------------------------------------------- |
| `TestCreateNote`         | 5     | Basic create, no title, JSON content, invalid entity type, all entity types |
| `TestGetNote`            | 2     | Existing, nonexistent                                                       |
| `TestGetNotesForEntity`  | 4     | List, filtering, pinned-first sort, author name                             |
| `TestUpdateNote`         | 4     | Basic update, revision creation, nonexistent, title preservation            |
| `TestDeleteNote`         | 3     | Existing, nonexistent, cascade                                              |
| `TestTogglePin`          | 2     | Pin/unpin, nonexistent                                                      |
| `TestRevisions`          | 3     | List, single, nonexistent                                                   |
| `TestSearch`             | 6     | Basic, by title, empty query, no results, after edit, after delete          |
| `TestExtractPlainText`   | 3     | Simple, nested, empty                                                       |
| `TestMentions`           | 4     | Extract from doc, no mentions, sync on create, sync on update               |
| `TestSearchMentionables` | 4     | Users, contacts, companies, empty query                                     |
| `TestAttachments`        | 2     | Orphan, with note                                                           |
| `TestNotesWebList`       | 2     | With notes, empty                                                           |
| `TestNotesWebCreate`     | 2     | Success, missing entity                                                     |
| `TestNotesWebEdit`       | 2     | Form, nonexistent                                                           |
| `TestNotesWebUpdate`     | 2     | Success, nonexistent                                                        |
| `TestNotesWebDelete`     | 2     | Success, nonexistent                                                        |
| `TestNotesWebPin`        | 2     | Toggle, nonexistent                                                         |
| `TestNotesWebRevisions`  | 3     | List, detail, nonexistent                                                   |
| `TestNotesWebUpload`     | 4     | Image, disallowed type, too large, serve file                               |
| `TestNotesWebMentions`   | 2     | Autocomplete, empty query                                                   |
| `TestNotesWebSearch`     | 2     | With results, empty                                                         |
| `TestEntityIntegration`  | 3     | Contact, company, conversation detail pages show notes                      |
| `TestSanitization`       | 2     | Script stripped, allowed tags preserved                                     |
| `TestMigration`          | 1     | All 5 tables created                                                        |

**Full suite**: 1147 tests, 0 failures, 0 regressions.

---

## 20. Migration

### `poc/migrate_to_v12.py`

Migrates from v11 to v12 in 7 steps:

1. Create `notes` table
2. Create `note_revisions` table
3. Create `note_attachments` table
4. Create `note_mentions` table
5. Create `notes_fts` FTS5 virtual table
6. Create 7 indexes
7. Bump `PRAGMA user_version = 12`

**Usage**:

```bash
# Dry run (applies to backup copy)
python3 -m poc.migrate_to_v12 --dry-run --db data/crm_extender.db

# Production
python3 -m poc.migrate_to_v12 --db data/crm_extender.db
```

The migration is additive (new tables only), so it's safe and fast. Backup is automatically created before any changes.

---

## 21. Design Decisions

| Decision                   | Choice                                  | Rationale                                                                                                              |
| -------------------------- | --------------------------------------- | ---------------------------------------------------------------------------------------------------------------------- |
| **Title field**            | Optional                                | Short notes (quick observations) don't need titles; the first line of content suffices in the card display             |
| **Content storage**        | JSON + HTML dual                        | JSON preserves Tiptap document structure for editing; HTML allows display without server-side rendering                |
| **FTS approach**           | FTS5 with manual sync                   | Avoids trigger-based sync issues with WAL mode; explicit sync on CRUD is reliable and predictable                      |
| **Attachment scope**       | Note-level (not revision-level)         | Files are stable references; only text content changes between revisions                                               |
| **Revision display**       | Full versions (not diffs)               | Simpler UX; each version is independently viewable; diff rendering can be added later as a view concern                |
| **`customer_id` on notes** | Direct column (not derived from entity) | Enables scoped queries without joining 5 different entity tables                                                       |
| **Sanitization**           | `bleach` library                        | Battle-tested HTML sanitizer; prevents XSS when rendering `content_html\|safe`                                         |
| **Editor delivery**        | ESM import map via `esm.sh`             | Consistent with existing CDN approach (PicoCSS, HTMX); no build tooling needed                                         |
| **Entity-agnostic design** | Polymorphic `entity_type`/`entity_id`   | Same pattern as `addresses`, `phone_numbers`, `email_addresses`; one set of routes/templates serves all 5 entity types |
| **Orphan uploads**         | `note_id=NULL` until note saves         | Images are uploaded mid-editing before the note exists; cleanup job handles abandoned uploads                          |
