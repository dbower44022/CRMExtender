# Note — Attachments, Mentions & Search Sub-PRD

**Version:** 1.0
**Last Updated:** 2026-02-23
**Status:** Draft
**Entity Base PRD:** [note-entity-base-prd.md]
**Referenced Entity PRDs:** [note-content-revisions-prd.md] (mention node contract, content save triggers)

---

## 1. Overview

### 1.1 Purpose

This sub-PRD defines three features that extend the core note: file attachments (images and documents uploaded into the editor), @mentions (inline references to users and entities), and full-text search (PostgreSQL tsvector with ranked results). Each integrates with the content pipeline — attachments provide URLs for editor content, mentions are extracted from content_json on save, and search indexes content_text.

### 1.2 Preconditions

- Note entity and revision pipeline operational.
- StorageBackend implementation available.
- PostgreSQL tsvector/tsquery infrastructure operational.
- note_attachments and note_mentions tables provisioned.

---

## 2. Context

### 2.1 Relevant Fields

| Field | Role in This Action |
|---|---|
| content_json | Source for mention extraction (walk document tree for mention nodes). |
| content_text | Plain text indexed by search_vector for FTS. |
| search_vector | Stored generated tsvector column. Auto-updates from title + content_text. |

### 2.2 Cross-Entity Context

- **Content & Revisions Sub-PRD:** Content save triggers mention extraction. content_text feeds FTS.
- **Document Entity Base PRD:** Documents have their own Universal Attachment to Notes. Note inline attachments (pasted images) are NOT Document entities — they remain tightly coupled to the Notes subsystem.

---

## 3. Key Processes

### KP-1: Upload Attachment

**Trigger:** User pastes/drops a file into the editor or uses toolbar upload.

**Step 1 — Upload:** Client POSTs file as multipart form data.

**Step 2 — Validate:** Check MIME type against allowlist. Check file size against limit.

**Step 3 — Store:** File written to disk via StorageBackend at `{upload_root}/{tenant_id}/{YYYY}/{MM}/{ulid}.{ext}`.

**Step 4 — Create orphan record:** note_attachments row with note_id = NULL.

**Step 5 — Return URL:** Server returns `{id, url, original_name, mime_type, size_bytes}`. Editor inserts URL in content.

**Step 6 — Link on save:** When note is saved, client includes attachment IDs. Server updates note_id on matching rows.

### KP-2: Serve Attachment

**Trigger:** User or client requests an attachment file.

**Step 1 — Lookup:** Find note_attachments row by ID.

**Step 2 — Tenant check:** Verify attachment's note belongs to requesting tenant.

**Step 3 — Visibility check:** If note is private, only creator can access. If shared, entity visibility rules apply.

**Step 4 — Serve:** Stream file with Content-Type (mime_type), Content-Disposition (original_name), Content-Length (size_bytes).

### KP-3: Mention Extraction

**Trigger:** Note content saved (every content save).

**Step 1 — Clear existing:** Delete all note_mentions rows for the note.

**Step 2 — Walk content_json:** Recursively traverse document tree.

**Step 3 — Extract mentions:** Find all nodes matching mention contract (`type: "mention"`, with `id`, `mentionType`, `label`).

**Step 4 — Insert:** Create note_mentions row for each unique (mention_type, mentioned_id) pair.

### KP-4: Mention Autocomplete

**Trigger:** User types `@` in editor.

**Step 1 — Query:** Search users and entity records matching the query text.

**Step 2 — Group results:** If no type filter, group by mention type (users, contacts, companies, etc.).

**Step 3 — Return:** Up to 10 results with id, mentionType, label, and optional metadata (e.g., email for contacts).

### KP-5: Full-Text Search

**Trigger:** User searches from global notes search or entity-scoped search.

**Step 1 — Parse query:** Convert search text to tsquery using plainto_tsquery.

**Step 2 — Execute:** Query notes using search_vector @@ query with visibility filtering.

**Step 3 — Rank:** Order by ts_rank with two-tier weighting (title A > content B).

**Step 4 — Snippets:** Generate ts_headline with <mark> highlighting.

**Step 5 — Return:** Ranked results with snippets, entity links, metadata.

---

## 4. File Attachments

**Supports processes:** KP-1, KP-2

### 4.1 Upload Flow

The orphan pattern handles the timing gap between file upload (mid-editing) and note save:

1. File uploaded → note_attachments row created with note_id = NULL (orphan).
2. URL returned → editor inserts in content.
3. Note saved → client sends attachment IDs → server sets note_id.

### 4.2 StorageBackend Protocol

Reuses protocol from Notes PRD (also used by Documents):

```python
class StorageBackend(Protocol):
    async def store(tenant_id, filename, data) -> str   # Returns storage_path
    async def retrieve(storage_path) -> bytes
    async def delete(storage_path) -> None
    def get_url(storage_path) -> str
```

Initial: LocalStorageBackend. Future: S3StorageBackend via protocol swap.

### 4.3 Storage Layout

```
{upload_root}/
  {tenant_id}/
    2026/
      02/
        01HX8A3B....png
        01HX8A4C....pdf
```

- Configurable upload_root (default: `data/uploads/`)
- Tenant isolation via directory nesting
- ULID-based filenames (no user-controlled paths)
- Year/month subdirectories prevent scaling issues

### 4.4 Orphan Cleanup

Background job: `cleanup_orphan_attachments(max_age_hours=24)`

1. Query note_attachments WHERE note_id IS NULL AND created_at < (now - interval).
2. Delete file from storage.
3. Delete database row.

Handles abandoned uploads from users who started editing but never saved.

### 4.5 Allowed Upload Types

| Category | MIME Types |
|---|---|
| Images | image/jpeg, image/png, image/gif, image/webp, image/svg+xml |
| Documents | application/pdf, application/msword, application/vnd.openxmlformats-officedocument.wordprocessingml.document, application/vnd.ms-excel, application/vnd.openxmlformats-officedocument.spreadsheetml.sheet, text/plain, text/csv |

### 4.6 Configuration

| Setting | Default |
|---|---|
| Upload root | data/uploads/ |
| Max file size | 10 MB |
| Orphan cleanup interval | Every 6 hours |
| Orphan max age | 24 hours |

**Tasks:**

- [ ] NAMS-01: Implement attachment upload endpoint (multipart, orphan creation)
- [ ] NAMS-02: Implement MIME type validation against allowlist
- [ ] NAMS-03: Implement file size validation
- [ ] NAMS-04: Implement StorageBackend (LocalStorageBackend)
- [ ] NAMS-05: Implement storage layout with tenant isolation and ULID filenames
- [ ] NAMS-06: Implement attachment linking on note save (set note_id)
- [ ] NAMS-07: Implement attachment serving with tenant and visibility checks
- [ ] NAMS-08: Implement orphan cleanup background job

**Tests:**

- [ ] NAMS-T01: Test upload creates orphan attachment (note_id = NULL)
- [ ] NAMS-T02: Test MIME type validation rejects disallowed types
- [ ] NAMS-T03: Test file size validation rejects oversized files
- [ ] NAMS-T04: Test file stored at correct path with ULID filename
- [ ] NAMS-T05: Test attachment linked to note on save
- [ ] NAMS-T06: Test attachment serving respects visibility (private note → creator only)
- [ ] NAMS-T07: Test orphan cleanup removes old unlinked attachments
- [ ] NAMS-T08: Test orphan cleanup preserves recent unlinked attachments

---

## 5. @Mentions

**Supports processes:** KP-3, KP-4

### 5.1 Mention Types

Notes can mention any entity type and workspace users:

| Mention Type | Search Scope | Display |
|---|---|---|
| `user` | platform.users (workspace members) | User's display name |
| Any object type slug | Records of that type in tenant schema | Entity's display_name_field value |

### 5.2 Mention Sync (Extraction)

On every content save:

1. Delete all existing note_mentions rows for the note.
2. Walk content_json document tree recursively.
3. Extract mention nodes matching the contract.
4. Insert note_mentions row for each unique (mention_type, mentioned_id) pair.

Full clear-and-rebuild avoids complex diff logic.

### 5.3 Stale Mention Handling

- Labels in content_json may become stale if entity renamed. The `id` is authoritative.
- Editor can optionally refresh labels on load by resolving IDs.
- Deleted/archived entities: mention node remains as unresolvable reference. UI renders dimmed chip. note_mentions row cleaned up by background consistency job.

**Tasks:**

- [ ] NAMS-09: Implement mention extraction from content_json (document tree walk)
- [ ] NAMS-10: Implement mention sync (clear + rebuild on save)
- [ ] NAMS-11: Implement mention autocomplete API (search users + entities)
- [ ] NAMS-12: Implement mention autocomplete type grouping
- [ ] NAMS-13: Implement stale mention detection for archived entities

**Tests:**

- [ ] NAMS-T09: Test mention extraction finds all mention nodes
- [ ] NAMS-T10: Test mention sync clears old and inserts new mentions
- [ ] NAMS-T11: Test duplicate mentions deduplicated (same entity mentioned twice)
- [ ] NAMS-T12: Test autocomplete returns results grouped by type
- [ ] NAMS-T13: Test autocomplete respects tenant isolation
- [ ] NAMS-T14: Test reverse lookup "notes mentioning contact X" works

---

## 6. Full-Text Search

**Supports processes:** KP-5

### 6.1 tsvector Configuration

Two-tier weighted search via stored generated column:

- **Weight A** (title): Title matches rank highest.
- **Weight B** (content_text): Plain text content matches rank second.
- English dictionary: stemming, stop words, normalization.
- GIN index for fast queries.

The search_vector updates automatically when title or content_text changes — no manual sync.

### 6.2 Search Query

```sql
SELECT id, title, visibility, created_by, created_at,
       ts_rank(search_vector, query) AS rank,
       ts_headline('english', content_text, query,
                   'StartSel=<mark>, StopSel=</mark>, MaxWords=35, MinWords=15') AS snippet
FROM notes,
     plainto_tsquery('english', $1) AS query
WHERE search_vector @@ query
  AND archived_at IS NULL
  AND (visibility = 'shared' OR created_by = $2)
ORDER BY rank DESC
LIMIT $3;
```

### 6.3 Search Features

| Feature | Implementation |
|---|---|
| Stemming | English dictionary: "budget" matches "budgets" |
| Ranking | ts_rank with weight differentiation (title > content) |
| Snippets | ts_headline with <mark> highlighting |
| Visibility filtering | Private excluded unless created_by = current_user |
| Tenant isolation | Implicit via search_path |

**Tasks:**

- [ ] NAMS-14: Implement FTS search endpoint with ranked results
- [ ] NAMS-15: Implement FTS snippets with ts_headline highlighting
- [ ] NAMS-16: Implement FTS visibility filtering
- [ ] NAMS-17: Implement FTS entity-scoped search (notes for specific entity)

**Tests:**

- [ ] NAMS-T15: Test FTS returns results ranked by relevance
- [ ] NAMS-T16: Test title matches rank higher than content matches
- [ ] NAMS-T17: Test snippets highlight matching terms
- [ ] NAMS-T18: Test private notes excluded from other users' search
- [ ] NAMS-T19: Test stemming works (search "meeting" finds "meetings")
- [ ] NAMS-T20: Test entity-scoped search limits results to entity's notes
