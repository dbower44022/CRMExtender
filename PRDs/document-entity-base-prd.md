# Document — Entity Base PRD

**Version:** 1.0
**Last Updated:** 2026-02-23
**Status:** Draft
**Product PRD:** [CRMExtender Product PRD]

---

## 1. Entity Definition

### 1.1 Purpose

Document is the file management layer of CRMExtender. While Communications capture message text, Notes store observations, and Events track meetings, Documents answer "What files exist, what versions have been shared, and how do they relate to the people and entities in this CRM?"

Documents are first-class entities with automatic version control, hash-based deduplication, folder organization, metadata extraction, full-text search, thumbnail previews, and universal entity attachment. The system unifies three previously separate file storage concerns: communication attachments, profile assets (logos, headshots, banners), and user-uploaded documents.

### 1.2 Design Goals

- **Universal attachment** — Documents attach to any entity type (system or custom) through the Universal Attachment Relation pattern. When a custom object type is created, documents are immediately attachable without configuration.
- **Folders as entities** — Folders are Document entities with `is_folder = true`, participating in the same attachment, event sourcing, and views model. Many-to-many membership — a document can exist in multiple folders.
- **Hash-based version control** — Every upload is SHA-256 hashed. Different hash → new version. Same hash → no-op. Matching existing blob → deduplication. Users see clean version history; the system never stores duplicate content.
- **Private by default** — Documents visible only to creator unless explicitly shared. Folder sharing cascades to contained documents.
- **No artificial restrictions** — Any file type accepted (except dangerous executables blocklist). No size limits. Chunked uploads handle large files.
- **Automatic processing** — Upload triggers metadata extraction, text extraction for FTS, thumbnail generation, and duplicate detection — all async and non-blocking.
- **Unified file storage** — Communication attachments, profile assets, and user uploads all become Document entities through a single storage pipeline.

### 1.3 Performance Targets

| Metric | Target |
|---|---|
| Document list load (default view, 50 rows) | < 200ms |
| Document upload (< 10MB) | < 2s end-to-end |
| Full-text search (95th percentile) | < 200ms |
| Thumbnail serve | < 50ms |
| Version history load | < 100ms |

### 1.4 Core Fields

| Field | Description | Required | Editable | Sortable | Filterable | Valid Values / Rules |
|---|---|---|---|---|---|---|
| ID | Unique identifier. Prefixed ULID with `doc_` prefix. | Yes | System | No | Yes | Prefixed ULID |
| Name | Display name. Defaults to original filename for uploads. | Yes | Direct | Yes | Yes | Free text |
| Description | Optional description or notes about the document. | No | Direct | No | Yes (search) | Free text |
| Is Folder | Whether this is a folder (container) or a file. **Immutable after creation.** | Yes | System (set on creation) | No | Yes | Boolean. Default: false. |
| Visibility | Access control level. | Yes | Direct | No | Yes | `private`, `shared`. Default: private. |
| Category | Auto-detected from MIME type. User-overridable. | No | Direct | Yes | Yes | `document`, `spreadsheet`, `presentation`, `image`, `video`, `audio`, `archive`, `code`, `other` |
| Source | How the document entered the system. | No | System | No | Yes | `uploaded`, `synced`, `profile_asset`, `system`. Default: uploaded. |
| Asset Type | For profile assets only. | No | System | No | Yes | `logo`, `headshot`, `banner`, NULL |
| MIME Type | MIME type of current version. NULL for folders. | No | System | No | Yes | Standard MIME types |
| File Extension | Extension without dot. NULL for folders. | No | System | No | Yes | e.g., `pdf`, `jpg` |
| Size Bytes | Size of current version. NULL for folders. | No | Computed | Yes | Yes | Non-negative integer |
| Current Version ID | Points to latest document_versions row. | No | System | No | No | Reference to version |
| Version Count | Count of versions. | No | Computed | Yes | Yes | Positive integer. Default: 1. |
| Content Hash | SHA-256 of current version content. NULL for folders. | No | System | No | No | SHA-256 hex string |
| Extracted Author | Author from file metadata (PDF, Office). | No | Computed | Yes | Yes | Free text |
| Extracted Title | Title from file metadata. | No | Computed | No | Yes | Free text |
| Page Count | Pages from PDFs and Office docs. | No | Computed | Yes | Yes | Positive integer |
| Width Px | Width in pixels for images and videos. | No | Computed | Yes | Yes | Positive integer |
| Height Px | Height in pixels for images and videos. | No | Computed | Yes | Yes | Positive integer |
| Duration Seconds | Duration for audio and video. | No | Computed | Yes | Yes | Positive decimal |
| Has Thumbnail | Whether a thumbnail has been generated. | No | Computed | No | Yes | Boolean. Default: false. |
| Content Text | Extracted text for FTS. Not exposed in views. | No | Computed | No | No (use FTS endpoint) | Plain text |
| Status | Record lifecycle. | Yes, defaults to active | System | Yes | Yes | `active`, `archived` |
| Created By | User who created/uploaded the record. | Yes | System | No | Yes | Reference to User |
| Created At | Record creation timestamp. | Yes | System | Yes | Yes | Timestamp |
| Updated At | Last modification timestamp. | Yes | System | Yes | Yes | Timestamp |

### 1.5 Registered Behaviors

| Behavior | Trigger | Description |
|---|---|---|
| Thumbnail generation | On upload / new version | Generates preview image. See Content Processing Sub-PRD. |
| Metadata extraction | On upload / new version | Reads embedded file metadata. See Content Processing Sub-PRD. |
| Text extraction | On upload / new version | Extracts text for FTS indexing. See Content Processing Sub-PRD. |
| Duplicate detection | On upload | Progressive hashing for deduplication. See Upload & Storage Sub-PRD. |
| FTS sync | On text extraction complete | Updates search_vector column from extracted text. |
| Visibility cascade | On folder share change | Recalculates effective visibility for contained documents. |
| Orphan cleanup | Scheduled background job | Removes stored blobs with zero references. |

---

## 2. Entity Relationships

### 2.1 Any Entity (Universal Attachment)

**Nature:** Many-to-many, via `document_entities` polymorphic junction table
**Ownership:** This entity
**Description:** Documents attach to any registered object type through the Universal Attachment Relation pattern. The junction table uses `entity_type` + `entity_id` columns to support attachment to system and custom object types without per-type relation definitions. Includes `is_pinned` metadata for prioritized display.

### 2.2 Folders (Membership)

**Nature:** Many-to-many, via `document_folder_members` junction table
**Ownership:** This entity
**Description:** Documents belong to folders through a many-to-many relationship. A document can exist in multiple folders simultaneously. Folder-to-folder nesting creates hierarchical structures. Acyclic enforcement prevents circular references.

### 2.3 Versions

**Nature:** One-to-many, owned
**Ownership:** This entity
**Description:** Each document has an append-only version history in `document_versions`. Each version stores its own metadata snapshot and references content via content-addressable storage. Current version tracked by `current_version_id` on the document.

### 2.4 Communications (Attachment)

**Nature:** Many-to-many, via `communication_documents` junction table
**Ownership:** This entity (integration)
**Description:** Documents linked to communications as email attachments. Includes `version_id` for precise version tracking ("which version was attached to that email"). See Integration Sub-PRD.

### 2.5 Thumbnails

**Nature:** One-to-one, via `thumbnail_for_id` FK
**Ownership:** This entity
**Description:** Thumbnail documents reference their source document. Stored in the system `_thumbnails` folder.

### 2.6 Notes

**Nature:** Many-to-many, via Notes universal attachment
**Ownership:** Notes PRD
**Description:** Notes can attach to Documents for commentary on file records.

---

## 3. Universal Attachment Relation

### 3.1 Pattern

Documents reuse the Universal Attachment Relation pattern from the Notes PRD. The pattern enables linking to records of any type (`target = *`) through a polymorphic junction table.

| Attribute | Value |
|---|---|
| Relation type slug | `document_entities` |
| Source | `documents` |
| Target | `*` (any registered object type) |
| Cardinality | Many-to-many |
| Metadata | `is_pinned` (Boolean) |

### 3.2 Behavior

When a new custom object type is registered, documents are immediately attachable — no migration or configuration needed. When a custom object type is archived, document links are retained. Documents remain accessible through other links, folders, or search.

### 3.3 Folder Attachment

Folders participate in Universal Attachment identically to files. Attaching a folder to an entity makes the folder and its contents discoverable from that entity's detail page: a "Contracts" folder on a Company, a "Site Photos" folder on a Job.

---

## 4. Folder Model

### 4.1 Folders as Document Entities

Folders are Document entities with `is_folder = true`. This enables folders to participate in Universal Attachment, event sourcing, custom fields, Views, and Data Sources. The `is_folder` flag is immutable after creation.

### 4.2 Folder Membership

File-to-folder membership is many-to-many via `document_folder_members`. A document can exist in multiple folders simultaneously — this is a link, not a move. Folder-to-folder nesting is supported through the same table, creating hierarchical structures.

### 4.3 Root Documents

Documents with no folder membership are "root" documents at the top level, accessible via search, entity attachment, or direct link. Folder membership is never required.

### 4.4 Folder Display

When viewing folder contents: sub-folders first (alphabetically), then files (by updated_at descending or user-selected sort). Breadcrumb navigation for nested folders. Item count per sub-folder.

### 4.5 System Folders

| Folder | Source | Purpose |
|---|---|---|
| `_thumbnails` | `system` | Generated thumbnail images. Hidden from default views. |
| `_profile_assets` | `system` | Logos, headshots, banners. Hidden from default views. |

System folders have `source = 'system'` and are excluded from user-facing listings by default.

### 4.6 Folder Operations

| Operation | Behavior |
|---|---|
| Create folder | Document entity with is_folder = true |
| Rename folder | Standard field update. Event sourced. |
| Add document to folder | Insert in document_folder_members |
| Remove from folder | Delete membership row. Document not archived. |
| Archive folder | Soft-delete folder. Contained documents NOT archived — they keep other memberships and entity links. |
| Move document | Atomic add-to-destination + remove-from-source |
| Copy to folder | Add to destination (many-to-many, document appears in both) |

### 4.7 Acyclic Enforcement

Before adding folder B to folder A, walk A's ancestry chain. If B appears, reject (circular reference). Same algorithm as Conversation aggregate nesting and Document folder nesting in Documents PRD.

---

## 5. Visibility

### 5.1 Visibility Model

| Level | Behavior |
|---|---|
| `private` (default) | Only the creator can see the document |
| `shared` | Inherits visibility from linked entities and containing shared folders |

### 5.2 Folder Visibility Cascade

When a folder's visibility is `shared`, all contained documents become accessible to users who can see the folder, regardless of individual document visibility.

**Effective visibility:** A document is accessible if its own visibility is `shared` OR any containing folder has `shared` visibility and the user can see that folder.

### 5.3 Permission Rules

| Action | Who Can Perform |
|---|---|
| View / Download | Creator, OR users who see a linked entity (shared), OR users with access to a containing shared folder |
| Upload new version | Creator, OR users with edit access to a linked entity |
| Edit metadata | Creator, OR users with edit access to a linked entity |
| Change visibility | Creator and workspace admins |
| Archive | Creator and workspace admins |
| Add/remove from folder | Users with edit access to the folder |

---

## 6. Lifecycle

| Status | Description |
|---|---|
| `active` | Normal operating state. Visible in views and search. |
| `archived` | Soft-deleted. All versions and blobs retained. Excluded from default queries. Recoverable. |

---

## 7. Key Processes

### KP-1: Uploading a Document

**Trigger:** User uploads a file or email sync delivers an attachment.

**Step 1 — Validation:** Check against dangerous file blocklist. No size limit.

**Step 2 — Hashing:** Progressive hash (quick hash → candidate check → full SHA-256 if needed). See Upload & Storage Sub-PRD.

**Step 3 — Deduplication:** If hash matches existing blob, link to existing storage. Otherwise store content.

**Step 4 — Record creation:** Create Document entity + first document_versions row. Set file property fields.

**Step 5 — Async behaviors:** Thumbnail generation, metadata extraction, text extraction queued (non-blocking).

**Step 6 — Response:** Document entity returned with version info and download URL.

### KP-2: Browsing Documents

**Trigger:** User navigates to Documents in Entity Bar, or views documents panel on an entity detail page.

**Step 1 — List loads:** Grid shows documents filtered by context (all documents, entity-linked, folder contents). Default sort: updated_at descending.

**Step 2 — Filtering:** By category, source, visibility, entity links, folder membership, creation date.

**Step 3 — Thumbnails:** Where available, thumbnail previews display alongside metadata.

### KP-3: Viewing a Document

**Trigger:** User selects a document from list.

**Step 1 — Detail panel:** Shows name, description, metadata, entity links, version history summary.

**Step 2 — Preview:** Inline preview for supported types (images, PDFs, video, audio, text/code). Download prompt for others.

**Step 3 — Version history:** Shows version list with number, name, date, uploader, size. Current version highlighted.

**Step 4 — Entity links:** Shows all linked entities as chips. Add/remove links.

### KP-4: Managing Folders

**Trigger:** User creates, organizes, or navigates folders.

**Step 1 — Create folder:** User provides name, optional description, optional parent folder, visibility.

**Step 2 — Add documents:** Drag-and-drop or "Add to folder" action. Many-to-many — document can be in multiple folders.

**Step 3 — Navigate:** Breadcrumb-based navigation through nested folders. Sub-folders first, then files.

**Step 4 — Reorganize:** Move documents between folders, copy to additional folders, remove from folders.

### KP-5: Linking Documents to Entities

**Trigger:** User links a document to an entity from either the document detail or entity detail page.

**Step 1 — Select target:** User picks entity type and record.

**Step 2 — Link created:** Row inserted in document_entities. Document appears on entity's documents panel.

**Step 3 — Pin (optional):** User pins important documents to appear first on the entity's documents panel.

### KP-6: Archiving and Restoring

**Trigger:** User archives from detail page or list view.

**Step 1 — Archive:** Document archived_at set. All versions and blobs retained. Removed from default views.

**Step 2 — Folder membership:** Membership rows retained but excluded from queries. Document no longer appears in folder contents.

**Step 3 — Restore:** User unarchives. archived_at cleared. Folder memberships restored.

---

## 8. Action Catalog

### 8.1 Upload Document

**Supports processes:** KP-1
**Trigger:** User upload or email sync.
**Outcome:** Document entity with first version. Async behaviors queued.
**Business Rules:** Blocklist validation. Hash-based deduplication.

### 8.2 View / Download Document

**Supports processes:** KP-2, KP-3
**Trigger:** User navigation.
**Outcome:** Document detail with preview, metadata, versions, entity links.

### 8.3 Edit Document Metadata

**Supports processes:** KP-3
**Trigger:** User edits name, description, category, visibility, or custom fields.
**Outcome:** Record updated. Event emitted.

### 8.4 Manage Folders

**Supports processes:** KP-4
**Trigger:** User creates, renames, or reorganizes folders.
**Outcome:** Folder structure updated. Acyclic enforcement. Visibility cascade if shared.

### 8.5 Link / Unlink Entity

**Supports processes:** KP-5
**Trigger:** User adds or removes entity link.
**Outcome:** Junction table updated. Pin state manageable.

### 8.6 Archive / Restore

**Supports processes:** KP-6
**Trigger:** User archives or restores.
**Outcome:** Soft-delete or recovery.

### 8.7 Upload, Versioning & Storage

**Summary:** The core file handling pipeline: upload flow, download flow, hash-based version control, content-addressable storage (CAS layout, StorageBackend protocol, reference counting), progressive hashing & duplicate detection, chunked uploads, dangerous file blocklist, preview delivery.
**Sub-PRD:** [document-upload-storage-prd.md]

### 8.8 Content Processing Pipeline

**Summary:** Post-upload processing behaviors: metadata extraction (PDF, Office, images, video, audio), text extraction for full-text search, PostgreSQL tsvector indexing with three-tier weighting, search with ranked results and snippets, thumbnail generation and serving.
**Sub-PRD:** [document-content-processing-prd.md]

### 8.9 Communication & Profile Asset Integration

**Summary:** Cross-PRD migration: email attachment promotion to Document entities during sync, communication_documents relation with version tracking, profile asset migration from entity_assets, and reconciliation with Communications and Company Management PRDs.
**Sub-PRD:** [document-integration-prd.md]

---

## 9. Open Questions

1. **Folder membership event volume** — Should folder_added/folder_removed events be tracked or only stored in junction table? Trade-off: event table size vs. audit completeness.
2. **File type changes between versions** — Word doc v1 → PDF v2 changes category, MIME, extension. Valid?
3. **Maximum folder membership** — Should a document have a cap on folder count? UX and performance consideration.
4. **Global cross-entity search** — How should Document FTS integrate with a future unified search spanning all entity types?
5. **Email body indexing** — Should email body text be indexed alongside promoted attachment documents?
6. **Storage quota model** — No size limits + deduplication implies unbounded growth. Per-tenant quotas?
7. **Download/view event tracking** — "Who viewed this contract?" is a compliance need. Separate access log vs. event sourcing?
8. **Thumbnail lifecycle** — If source document is archived, should thumbnail also be archived?

---

## 10. Design Decisions

### Why system object type?

Full participation in Views, Data Sources, event sourcing, and Custom Objects framework. Version control, folder hierarchy, and 7 registered behaviors require system entity status.

### Why Universal Attachment (target = *)?

Enables attachment to all entity types without per-type relation definitions. Consistent with Notes and Tasks. Custom object types get document support automatically.

### Why folders as entities?

Enables folders to participate in Universal Attachment, event sourcing, Views, and custom fields. Eliminates a separate folder table.

### Why many-to-many folder membership?

A document can exist in multiple folders — this is a link, not containment. Consistent with entity linking. A contract PDF can be in both "Acme Contracts" and "Q1 2026 Legal Review."

### Why hash-based version control?

Eliminates manual "create new version" workflows. Hash comparison is deterministic. Same hash = no-op (no wasted storage). Different hash = automatic new version.

### Why content-addressable storage?

Automatic deduplication. Integrity verification. Consistent with Company Management PRD asset storage pattern.

### Why private by default?

Privacy-first, consistent with Notes. Folder cascade adds a document-specific extension.

### Why no size/type restrictions?

A document management system should accept any business file. Dangerous executables blocklisted. Chunked uploads handle large files.

### Why Note inline attachments unchanged?

Pasted images are part of the note's content, not standalone documents. Avoids double-indexing and confusing UX.

---

## Related Documents

| Document | Relationship |
|---|---|
| [Document Entity TDD](document-entity-tdd.md) | Technical decisions for document implementation |
| [Upload, Versioning & Storage Sub-PRD](document-upload-storage-prd.md) | File handling pipeline |
| [Content Processing Pipeline Sub-PRD](document-content-processing-prd.md) | Metadata extraction, FTS, thumbnails |
| [Communication & Profile Asset Integration Sub-PRD](document-integration-prd.md) | Cross-PRD migration |
| [Custom Objects PRD](custom-objects-prd.md) | Unified object model |
| [Notes PRD](notes-prd.md) | Universal Attachment pattern origin |
| [Communications PRD](communications-prd.md) | Attachment integration source |
| [Company Management PRD](company-management-prd.md) | Profile asset migration source |
| [Master Glossary](glossary.md) | Term definitions |
