# Product Requirements Document: Documents

## CRMExtender — Document Management, Version Control, Folder Organization & Universal Attachment

**Version:** 2.0
**Date:** 2026-02-18
**Status:** Draft — Fully reconciled with Custom Objects PRD
**Parent Document:** [CRMExtender PRD v1.1](PRD.md)

> **V2.0 (2026-02-22):**
> Terminology standardization pass: Mojibake encoding cleanup. Cross-PRD links updated to current versions (Custom Objects V2, Views & Grid V5, Contact Management V5, Conversations V4, Projects V3). Master Glossary V3 cross-reference added to glossary section.
>
> **V1.0 (2026-02-18):**
> This document defines the Document system object type for CRMExtender. Documents represent files — proposals, contracts, brochures, photos, recordings, and any other binary content — managed as first-class entities with version control, folder organization, and universal entity attachment. The design enables full relationship intelligence over files: "which version of the brochure was sent to Contact X in response to email Y."
>
> All content is reconciled with the [Custom Objects PRD](custom-objects-prd_v2.md) Unified Object Model:
> - Document is a **system object type** (`is_system = true`, prefix `doc_`) in the unified framework. Metadata fields (name, description, category, dimensions, etc.) are registered in the field registry. Specialized behaviors (thumbnail generation, metadata extraction, text extraction, duplicate detection, FTS sync, visibility cascade, orphan cleanup) are registered per Custom Objects PRD Section 22.
> - Entity IDs use **prefixed ULIDs** (`doc_` prefix, e.g., `doc_01HX8A...`) per the platform-wide convention (Data Sources PRD, Custom Objects PRD Section 6).
> - Document-to-entity linking uses the **Universal Attachment Relation** pattern (`target = *`), reusing the pattern introduced by the Notes PRD and adopted by Tasks. Documents and folders attach to any entity type — system or custom — without requiring individual relation type definitions.
> - Folders are Document entities with `is_folder = true`. File-to-folder membership is a many-to-many relation, enabling a single document to exist in multiple folders. Folder visibility cascades to contained documents.
> - Version control is **hash-based**: every upload with a different SHA-256 hash creates a new version. Content-addressable storage provides automatic deduplication — identical file content is stored once regardless of how many Document entities reference it.
> - Communication attachments (email files, etc.) are automatically promoted to Document entities during sync, replacing the Communications PRD's standalone attachment table.
> - Company/Contact profile assets (logos, headshots, banners) are stored as Document entities, replacing the Company Management PRD's `entity_assets` table.
> - All SQL uses **PostgreSQL** syntax with `TIMESTAMPTZ` timestamps and schema-per-tenant isolation.

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Problem Statement](#2-problem-statement)
3. [Goals & Success Metrics](#3-goals--success-metrics)
4. [Document as System Object Type](#4-document-as-system-object-type)
5. [Data Model](#5-data-model)
6. [Universal Attachment Relation](#6-universal-attachment-relation)
7. [Folder Model](#7-folder-model)
8. [Version Control](#8-version-control)
9. [Content-Addressable Storage](#9-content-addressable-storage)
10. [Duplicate Detection](#10-duplicate-detection)
11. [Metadata Extraction](#11-metadata-extraction)
12. [Full-Text Search](#12-full-text-search)
13. [Thumbnail Generation](#13-thumbnail-generation)
14. [Document Visibility](#14-document-visibility)
15. [Communication Attachment Integration](#15-communication-attachment-integration)
16. [Profile Asset Integration](#16-profile-asset-integration)
17. [Upload & Download](#17-upload--download)
18. [Event Sourcing](#18-event-sourcing)
19. [Virtual Schema & Data Sources](#19-virtual-schema--data-sources)
20. [API Design](#20-api-design)
21. [Design Decisions](#21-design-decisions)
22. [Phasing & Roadmap](#22-phasing--roadmap)
23. [Dependencies & Related PRDs](#23-dependencies--related-prds)
24. [Open Questions](#24-open-questions)
25. [Future Work](#25-future-work)
26. [Glossary](#26-glossary)

---

## 1. Executive Summary

The Documents subsystem is the **file management layer** of CRMExtender. While Communications capture message text, Notes store free-form observations, and Events track meetings, Documents answer **"What files exist, what versions have been shared, and how do they relate to the people and entities in this CRM?"** Documents provide the binary content counterpart to the platform's text-based knowledge systems — enabling users to manage, version, organize, search, and trace every file across their business relationships.

Unlike CRMs where files are opaque blobs buried in activity timelines or bolted-on storage widgets, CRMExtender treats documents as **first-class entities** with automatic version control, hash-based deduplication, folder organization, metadata extraction, full-text search, thumbnail previews, and universal entity attachment. A single document can live in multiple folders and be linked to any number of entities — a proposal PDF attached to both a Contact and a Project, a brochure linked to a Company and referenced from an email communication.

The system unifies three previously separate file storage concerns: communication attachments (email files synced from providers), profile assets (logos, headshots, banners), and user-uploaded documents. All files flow through the same version-controlled, hash-deduplicated, searchable Document entity model.

**Core principles:**

- **System object type** — Document is a system object type (`is_system = true`, prefix `doc_`) in the Custom Objects unified framework. Metadata fields (name, description, category, file properties, extracted metadata) are registered in the field registry. Specialized behaviors (thumbnail generation, metadata extraction, text extraction, duplicate detection, FTS sync, visibility cascade, orphan cleanup) are registered per Custom Objects PRD Section 22. Users can extend Documents with custom fields through the standard field registry.
- **Universal attachment** — Documents attach to any entity type (system or custom) through the Universal Attachment Relation pattern. When Sam creates a "Jobs" custom object type, documents are immediately attachable to Job records without any additional configuration. A single document can be linked to multiple entities across different types.
- **Folders as entities** — Folders are Document entities with `is_folder = true`, enabling them to participate in the same Universal Attachment model. A folder of contracts can be attached to a Company, a folder of project photos to a Job. File-to-folder membership is many-to-many — a document can exist in multiple folders simultaneously.
- **Hash-based version control** — Every upload is SHA-256 hashed. If the hash matches the current version, the upload is a no-op. If the hash differs from the current version, a new version is created. If the hash matches an existing stored blob, the version points to the existing content (deduplication). Users see a clean version history; the system never stores duplicate file content.
- **Private by default** — Documents are visible only to their creator by default. Authors can explicitly share documents, at which point visibility inherits from the linked entity's permission model. Folder sharing cascades to all contained documents.
- **No file type or size restrictions** — The system accepts any file type except a blocklist of dangerous executables. No artificial size limits are imposed. Chunked uploads handle large files.
- **Automatic metadata extraction** — On upload, the system extracts embedded metadata from files (PDF author, page count; image dimensions, EXIF; video duration; Office document properties) and populates searchable fields.
- **Full-text content search** — Embedded text is extracted from documents (PDFs, Word docs, spreadsheets, text files) and indexed with PostgreSQL tsvector for content-based discovery.
- **Unified file storage** — Communication attachments, profile assets, and user-uploaded files all become Document entities. Three separate storage systems consolidate into one.

**Relationship to other PRDs:**

- **[Custom Objects PRD](custom-objects-prd_v2.md)** — The Document entity type is a system object type in the unified framework. Its table structure, field registry, event sourcing, and relation model are governed by the Custom Objects PRD. The Universal Attachment Relation pattern (introduced by the Notes PRD) is reused for document-to-entity linking. This PRD defines the Document-specific behaviors registered with the object type framework.
- **[Notes PRD](notes-prd_V3.md)** — Documents reuse the Universal Attachment Relation pattern and the `StorageBackend` protocol established by Notes. Note inline attachments (images pasted into the editor) remain tightly coupled to Notes and are NOT Document entities. Notes can attach to Documents via Notes' own universal attachment, enabling commentary on document records.
- **[Tasks PRD](tasks-prd_V2.md)** — Tasks can attach to Documents for file-related action items ("review and approve contract", "update brochure pricing"). Documents can attach to Tasks for deliverable tracking.
- **[Communications PRD](communications-prd_V1.md)** — Email attachments are automatically promoted to Document entities during sync. The Communications PRD's standalone `communication_attachments` table is replaced by Communication→Document relations. This enables "which version of this file was sent in that email" tracking.
- **[Company Management PRD](company-management-prd_V1.md)** — Company logos, banners, and contact headshots are stored as Document entities, replacing the `entity_assets` table. This brings version control to profile assets and eliminates a separate storage system.
- **[Projects PRD](projects-prd_V3.md)** — Documents attach to Projects for project-level file organization. Project folders provide a natural grouping for deliverables, references, and working files.
- **[Contact Management PRD](contact-management-prd_V5.md)** — Documents attach to Contacts for relationship-specific files (proposals sent, contracts signed, photos).
- **[Event Management PRD](events-prd_V3.md)** — Documents attach to Events for meeting materials, presentation decks, and post-meeting deliverables.
- **[Conversations PRD](conversations-prd_V4.md)** — Documents attach to Conversations for file context within communication threads.
- **[Data Sources PRD](data-sources-prd_V1.md)** — The Document virtual schema table is derived from the Document object type's field registry. The `doc_` prefix enables automatic entity detection in data source queries.
- **[Views & Grid PRD](views-grid-prd_V5.md)** — Document views support Grid (metadata columns), Gallery (thumbnail grid), and list views. Inline editing, filtering, and sorting operate on fields from the Document field registry.
- **[Permissions & Sharing PRD](permissions-sharing-prd_V2.md)** — Document visibility follows the Notes-style private-by-default model with folder-level cascade sharing.

---

## 2. Problem Statement

CRM users work with files constantly: proposals are sent to prospects, contracts are signed with clients, brochures are shared in marketing emails, photos document job sites, and presentation decks are prepared for meetings. In typical CRM systems, these files exist in disconnected silos:

- **Email attachments** are visible on individual email records but not searchable, version-tracked, or linked to the broader entity graph. When a user updates a brochure and re-sends it, there's no connection between the old and new versions.
- **Profile images** (logos, headshots) are stored in their own tables with no version history. When a company rebrands, the old logo is overwritten with no record of the change.
- **User-uploaded files** land in generic attachment widgets with no organization, no version control, and no way to find "all PDFs related to this project."
- **Cross-entity file discovery** is impossible. A user cannot answer "show me all files related to this Contact" because files are scattered across email attachments, note inline images, and ad-hoc upload widgets.

The Documents subsystem solves these problems by treating every file as a first-class entity in the CRM graph — version-controlled, hash-deduplicated, metadata-enriched, full-text searchable, folder-organized, and linked to any number of entities through the Universal Attachment pattern.

---

## 3. Goals & Success Metrics

| Goal | Metric | Target |
|---|---|---|
| Attach documents to any entity | Documents available on all system entity detail pages + all custom object detail pages | 100% entity type coverage |
| Version control | Every distinct file upload creates a traceable version with SHA-256 hash | 100% upload coverage |
| Deduplication | Identical file content stored once regardless of upload count | 0 duplicate blobs |
| Folder organization | Users can create nested folder hierarchies and place documents in multiple folders | Unlimited nesting, many-to-many |
| Metadata extraction | File metadata auto-populated on upload (author, dimensions, page count, EXIF, etc.) | Coverage for PDF, Office, images, video |
| Full-text search | Search document content (embedded text in PDFs, Word docs, etc.) | <200ms for 95th percentile |
| Thumbnail generation | Visual previews for images, PDFs, and video files | Coverage for common file types |
| Communication integration | Email attachments auto-created as Document entities | 100% real attachment coverage |
| Profile asset integration | Logos, headshots, banners stored as Documents with version history | Full migration from entity_assets |
| No file restrictions | Any file type accepted (except blocklist); no size limit | Zero artificial constraints |
| Custom object support | Documents attachable to user-created entity types without configuration | Automatic via universal attachment |

---

## 4. Document as System Object Type

### 4.1 Object Type Registration

Document is registered as a system object type in `platform.object_types`:

| Attribute | Value |
|---|---|
| `slug` | `documents` |
| `name` | `Document` |
| `type_prefix` | `doc_` |
| `is_system` | `true` |
| `description` | Version-controlled file management with folder organization, metadata extraction, and universal entity attachment |
| `display_name_field` | `name` |
| `icon` | `file` (or equivalent) |

### 4.2 Field Registry

| Field Slug | Field Type | System | Required | Default | Description |
|---|---|---|---|---|---|
| `name` | Text | Yes | Yes | — | Display name of the document or folder. For uploaded files, defaults to the original filename. User-editable. |
| `description` | Text (multi-line) | Yes | No | `NULL` | Optional description or notes about the document. |
| `is_folder` | Checkbox | Yes | Yes | `false` | `true` for folders, `false` for files. Immutable after creation. |
| `visibility` | Select | Yes | Yes | `'private'` | `private` (creator only) or `shared` (inherits entity visibility). |
| `category` | Select | Yes | No | Auto-detected | Auto-detected from MIME type: `document`, `spreadsheet`, `presentation`, `image`, `video`, `audio`, `archive`, `code`, `other`. User-overridable. |
| `source` | Select | Yes | No | `'uploaded'` | How the document entered the system: `uploaded` (user upload), `synced` (from email attachment), `profile_asset` (logo/headshot/banner), `system` (generated thumbnail, etc.). |
| `asset_type` | Select | Yes | No | `NULL` | For profile assets: `logo`, `headshot`, `banner`. `NULL` for non-asset documents. |
| `mime_type` | Text | Yes | No | `NULL` | MIME type of the current version (e.g., `application/pdf`, `image/jpeg`). `NULL` for folders. |
| `file_extension` | Text | Yes | No | `NULL` | File extension without dot (e.g., `pdf`, `jpg`). `NULL` for folders. |
| `size_bytes` | Number | Yes | No | `NULL` | Size of the current version in bytes. `NULL` for folders. |
| `current_version_id` | Text | Yes | No | — | Points to the latest `document_versions` row. Managed by version behavior. |
| `version_count` | Number | Yes | No | `1` | Count of versions. Managed by version behavior. |
| `content_hash` | Text | Yes | No | — | SHA-256 hash of the current version's content. Used for deduplication. `NULL` for folders. |
| `extracted_author` | Text | Yes | No | `NULL` | Author extracted from file metadata (PDF, Office). |
| `extracted_title` | Text | Yes | No | `NULL` | Title extracted from file metadata. |
| `page_count` | Number | Yes | No | `NULL` | Page count extracted from PDFs and Office documents. |
| `width_px` | Number | Yes | No | `NULL` | Width in pixels for images and videos. |
| `height_px` | Number | Yes | No | `NULL` | Height in pixels for images and videos. |
| `duration_seconds` | Number | Yes | No | `NULL` | Duration for audio and video files. |
| `has_thumbnail` | Checkbox | Yes | No | `false` | Whether a thumbnail has been generated for this document. |

Universal fields (`id`, `tenant_id`, `created_at`, `updated_at`, `created_by`, `updated_by`, `archived_at`) are inherited from the object type framework per Custom Objects PRD Section 8.

Users can add custom fields to Documents through the standard field registry (e.g., a "Status" select field for approval workflows, a "Client Facing" checkbox, a "Expiration Date" date field for contracts).

### 4.3 Registered Behaviors

Per Custom Objects PRD Section 22, the Document system object type registers the following specialized behaviors:

| Behavior | Trigger | Description |
|---|---|---|
| Thumbnail generation | On upload / new version | Generates a thumbnail image for the document and stores it in the system thumbnails folder. Supports images (resize), PDFs (first page render), and video (frame extraction). |
| Metadata extraction | On upload / new version | Reads embedded file metadata (PDF info dict, EXIF, Office document properties, ID3 tags) and populates corresponding fields on the Document record. |
| Text extraction | On upload / new version | Extracts embedded text content from supported file types (PDF text layer, Office document text, plain text files, CSV content) for full-text search indexing. No OCR. |
| Duplicate detection | On upload | Progressive hashing: quick partial hash to narrow candidates, full SHA-256 on match. If content matches an existing blob, links to existing storage rather than storing again. Notifies user that an existing copy was found (no action required). |
| FTS sync | On text extraction complete | Updates the `search_vector` stored generated column on the `documents` table from extracted text content. |
| Visibility cascade | On folder share change | When a folder's visibility changes, recalculates effective visibility for all documents linked to that folder. A document is accessible if its own visibility is `shared` OR any folder containing it has `shared` visibility. |
| Orphan cleanup | On schedule (background job) | Cleans up stored blobs that are not referenced by any `document_versions` row. Handles abandoned uploads and version garbage collection. |

---

## 5. Data Model

### 5.1 Tables

All tables reside in the tenant schema (e.g., `tenant_abc.documents`). The `search_path` is set per request, so queries reference tables without schema qualification.

#### `documents` — Read model (system object type table)

```sql
CREATE TABLE documents (
    id              TEXT PRIMARY KEY,          -- doc_ prefixed ULID
    tenant_id       TEXT NOT NULL,             -- FK → platform.tenants
    name            TEXT NOT NULL,             -- Display name (filename or user-specified)
    description     TEXT,                      -- Optional description
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
    content_hash    TEXT,                      -- SHA-256 of current version content

    -- Version tracking
    current_version_id TEXT,                   -- FK → document_versions(id)
    version_count   INTEGER NOT NULL DEFAULT 1,

    -- Extracted metadata (populated by metadata extraction behavior)
    extracted_author    TEXT,
    extracted_title     TEXT,
    page_count          INTEGER,
    width_px            INTEGER,
    height_px           INTEGER,
    duration_seconds    NUMERIC,
    has_thumbnail       BOOLEAN NOT NULL DEFAULT false,

    -- Extracted text content for FTS (populated by text extraction behavior)
    content_text    TEXT,                      -- Plain text extracted from file content

    -- Full-text search (stored generated column)
    search_vector   TSVECTOR GENERATED ALWAYS AS (
        setweight(to_tsvector('english', coalesce(name, '')), 'A') ||
        setweight(to_tsvector('english', coalesce(description, '')), 'B') ||
        setweight(to_tsvector('english', coalesce(content_text, '')), 'C')
    ) STORED,

    -- Universal fields (Custom Objects framework)
    created_by      TEXT NOT NULL,             -- FK → platform.users
    updated_by      TEXT NOT NULL,             -- FK → platform.users
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    archived_at     TIMESTAMPTZ               -- Soft delete
);

-- GIN index for full-text search
CREATE INDEX idx_documents_search ON documents USING GIN (search_vector);

-- Visibility + creator for private document filtering
CREATE INDEX idx_documents_visibility ON documents (visibility, created_by);

-- Soft delete filter
CREATE INDEX idx_documents_archived ON documents (archived_at) WHERE archived_at IS NULL;

-- Current version lookup
CREATE INDEX idx_documents_current_ver ON documents (current_version_id);

-- Category filter (common: "show all images", "show all PDFs")
CREATE INDEX idx_documents_category ON documents (category);

-- Source filter (common: "show synced attachments", "show user uploads")
CREATE INDEX idx_documents_source ON documents (source);

-- Content hash for deduplication lookups
CREATE INDEX idx_documents_hash ON documents (content_hash);

-- Folder filter
CREATE INDEX idx_documents_is_folder ON documents (is_folder);

-- Asset type filter (for profile asset queries)
CREATE INDEX idx_documents_asset_type ON documents (asset_type) WHERE asset_type IS NOT NULL;
```

#### `document_entities` — Universal Attachment junction

```sql
CREATE TABLE document_entities (
    document_id     TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    entity_type     TEXT NOT NULL,             -- Object type slug (e.g., 'contacts', 'jobs')
    entity_id       TEXT NOT NULL,             -- Prefixed ULID of the linked entity
    is_pinned       BOOLEAN NOT NULL DEFAULT false,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    PRIMARY KEY (document_id, entity_type, entity_id)
);

-- List documents for an entity (most common query path)
CREATE INDEX idx_de_entity ON document_entities (entity_type, entity_id);

-- Find entities for a document
CREATE INDEX idx_de_document ON document_entities (document_id);

-- Sort pinned first within entity document lists
CREATE INDEX idx_de_pinned ON document_entities (entity_type, entity_id, is_pinned DESC);
```

#### `document_versions` — Append-only version history

```sql
CREATE TABLE document_versions (
    id              TEXT PRIMARY KEY,          -- ver_ prefixed ULID
    document_id     TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    version_number  INTEGER NOT NULL,
    name            TEXT,                      -- Optional version name (e.g., "Final Draft")
    description     TEXT,                      -- Optional version note (e.g., "Updated Q2 pricing")

    -- File properties for this version
    mime_type       TEXT NOT NULL,
    file_extension  TEXT NOT NULL,
    size_bytes      BIGINT NOT NULL,
    content_hash    TEXT NOT NULL,             -- SHA-256 hash of file content
    storage_path    TEXT NOT NULL,             -- Path in StorageBackend

    -- Extracted metadata snapshot for this version
    extracted_author    TEXT,
    extracted_title     TEXT,
    page_count          INTEGER,
    width_px            INTEGER,
    height_px           INTEGER,
    duration_seconds    NUMERIC,

    -- Provenance
    uploaded_by     TEXT NOT NULL,             -- FK → platform.users
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE (document_id, version_number)
);

CREATE INDEX idx_doc_versions_document ON document_versions (document_id, version_number DESC);
CREATE INDEX idx_doc_versions_hash ON document_versions (content_hash);
```

#### `document_folder_members` — Many-to-many folder membership

```sql
CREATE TABLE document_folder_members (
    folder_id       TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    document_id     TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    added_by        TEXT NOT NULL,             -- FK → platform.users
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    PRIMARY KEY (folder_id, document_id),
    -- Prevent self-membership
    CHECK (folder_id != document_id)
);

-- List documents in a folder
CREATE INDEX idx_dfm_folder ON document_folder_members (folder_id);

-- List folders containing a document
CREATE INDEX idx_dfm_document ON document_folder_members (document_id);
```

#### `document_blobs` — Content-addressable storage registry

```sql
CREATE TABLE document_blobs (
    content_hash    TEXT PRIMARY KEY,          -- SHA-256 hash (unique content identifier)
    storage_path    TEXT NOT NULL,             -- Path in StorageBackend
    size_bytes      BIGINT NOT NULL,
    mime_type       TEXT NOT NULL,
    reference_count INTEGER NOT NULL DEFAULT 1,  -- Number of document_versions pointing here
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### 5.2 Constraint: Folder Integrity

Folders cannot be placed inside themselves (direct or indirect circular reference). The application layer enforces acyclic folder membership by checking the ancestry chain before adding a folder to another folder. Since files (non-folders) cannot contain other documents, circular references are only possible with folder-in-folder placement.

```sql
-- Application-level check (not a DB constraint due to recursive nature):
-- Before adding folder B to folder A:
-- 1. Walk up from A through document_folder_members to find all ancestors of A
-- 2. If B appears in the ancestor chain, reject (would create cycle)
-- 3. If A == B, reject (self-reference blocked by CHECK constraint)
```

---

## 6. Universal Attachment Relation

### 6.1 Pattern

Documents reuse the Universal Attachment Relation pattern introduced by the [Notes PRD](notes-prd_V3.md) Section 6. The pattern enables a source entity type to link to records of any type (`target = *`) through a polymorphic junction table.

The Document entity type registers its own universal attachment relation type:

| Attribute | Value |
|---|---|
| Relation type slug | `document_entities` |
| Source | `documents` |
| Target | `*` (any registered object type) |
| Junction table | `document_entities` |
| Cardinality | Many-to-many |
| Metadata | `is_pinned` (Boolean) |

### 6.2 Behavior

When a new custom object type is registered (e.g., "Properties"), documents are immediately attachable to Property records — no migration, configuration, or relation type creation needed. The `entity_type` column in `document_entities` accepts any valid object type slug.

When a custom object type is archived, documents linked to archived entity types retain their links. The documents remain accessible through other linked entities, through folder membership, or through global search.

### 6.3 Folder Attachment

Folders are Document entities with `is_folder = true`. They participate in the Universal Attachment pattern identically to files. Attaching a folder to an entity makes the folder — and by extension its contents — discoverable from that entity's detail page. This enables patterns like:

- A "Contracts" folder attached to a Company
- A "Site Photos" folder attached to a custom Job entity
- A "Pitch Deck Versions" folder attached to a Project

### 6.4 Framework Impact

The Universal Attachment pattern extensions defined in the Notes PRD (Section 6.4) apply equally to Documents:

1. **Relation type validation**: `target_object_type = '*'` accepted for system-defined relation types.
2. **Junction table schema**: `entity_type TEXT` + `entity_id TEXT` columns (polymorphic target).
3. **Views integration**: "Linked Entities" column type renders as entity chips with mixed types.
4. **Data Sources integration**: Universal attachment JOINs use `entity_type` filtering.
5. **Neo4j sync**: Universal attachment links sync as `HAS_DOCUMENT` edges with an `entity_type` property.

---

## 7. Folder Model

### 7.1 Folders as Document Entities

Folders are Document entities with `is_folder = true`. This design decision enables folders to:

- Participate in Universal Attachment (attach a folder to any entity)
- Have event sourcing (audit trail for folder creation, renaming, sharing)
- Have custom fields (e.g., a "Department" select on folders)
- Appear in Views and Data Sources
- Be linked to Notes and Tasks

The `is_folder` flag is immutable after creation — a folder cannot become a file or vice versa.

### 7.2 Folder Membership

File-to-folder membership is a **many-to-many** relationship via `document_folder_members`. A single document can exist in multiple folders simultaneously. This is a link, not a move — the document exists independently of any folder.

Folder-to-folder nesting is also supported: a folder can be a member of another folder, creating hierarchical structures. The `document_folder_members` table handles both file→folder and folder→folder relationships identically.

### 7.3 Root Documents

Documents with no folder membership are "root" documents — they exist at the top level and are accessible via global search, entity attachment, or direct link. There is no requirement for a document to belong to a folder.

### 7.4 Folder Display

When viewing a folder's contents, the UI displays:

1. Sub-folders first (alphabetically)
2. Files second (by `updated_at` descending, or user-selected sort)
3. Breadcrumb navigation showing the current path (for nested folders)
4. The count of items in each sub-folder

### 7.5 System Folders

Certain folders are created by the system for internal use:

| Folder | `source` | Purpose |
|---|---|---|
| `_thumbnails` | `system` | Generated thumbnail images. Hidden from default views. |
| `_profile_assets` | `system` | Logos, headshots, banners migrated from entity_assets. Hidden from default views. |

System folders have `source = 'system'` and are excluded from user-facing folder listings by default. They are accessible to admins and through direct queries.

### 7.6 Folder Operations

| Operation | Behavior |
|---|---|
| **Create folder** | Creates a Document entity with `is_folder = true`. |
| **Rename folder** | Standard field update on `name`. Event sourced. |
| **Add document to folder** | Inserts row in `document_folder_members`. |
| **Remove document from folder** | Deletes row from `document_folder_members`. The document is not archived — only the folder membership is removed. |
| **Archive folder** | Soft-deletes the folder. Documents within the folder are NOT archived — they retain their other folder memberships and entity links. Folder membership rows to the archived folder remain in the table but are excluded from queries. |
| **Move document between folders** | Atomic "add to destination + remove from source" operation. |
| **Copy document to folder** | Add to destination folder (many-to-many, so the same document now appears in both). |

---

## 8. Version Control

### 8.1 Model

Every file upload is hashed. If the hash differs from the document's current version, a new `document_versions` row is created. Versions are:

- **Append-only**: Never updated or deleted individually. Removed only via CASCADE when the parent document is deleted.
- **Numbered**: `version_number` starts at 1 and increments per document.
- **Unique**: `UNIQUE(document_id, version_number)` constraint.
- **Full snapshots**: Each version stores a reference to the complete file content (via `content_hash` → `document_blobs`). No diffs.
- **Named**: Each version has optional `name` and `description` fields for human-readable context.

### 8.2 Version Lifecycle

| Action | Behavior |
|---|---|
| **Initial upload** | First version created (version_number = 1). `current_version_id`, `version_count`, `content_hash`, `size_bytes`, `mime_type`, `file_extension` set on the document. |
| **Re-upload (different hash)** | New version created (version_number incremented). Document's `current_version_id` updated. Document's `version_count` incremented. File property fields on document updated to match new version. Metadata extraction and text extraction behaviors triggered. |
| **Re-upload (same hash)** | No-op. Upload is acknowledged but no new version is created. The file content is identical. |
| **Update version metadata** | `name` and `description` on a `document_versions` row can be updated without creating a new version. |
| **View old version** | Client requests a specific version by ID. Server returns download URL for that version's content. |
| **Download current version** | Server resolves `current_version_id` → `document_versions` → `document_blobs` → storage path. |
| **Archive document** | All versions retained. The document is soft-deleted but versions and blobs persist. |

### 8.3 Version Metadata Snapshots

Each version stores its own metadata snapshot (`extracted_author`, `page_count`, `width_px`, etc.) independent of the Document record. This enables tracking metadata changes across versions — "version 1 had 12 pages, version 2 has 15 pages."

The Document record's metadata fields always reflect the current version. When a new version is created, the document's metadata is overwritten with the new version's values.

### 8.4 Relationship to Communication Tracking

When an email is sent with a document as an attachment, the Communication→Document relation captures which Document entity was referenced. The `document_versions` table captures which version existed at that point in time. Combined, this enables the core use case: "version 3 of the brochure was the current version when it was attached to the email sent to John Smith on January 15th."

For precise version tracking on communications, the `communication_documents` relation table (Section 15) includes a `version_id` column that records the exact version attached to each communication.

---

## 9. Content-Addressable Storage

### 9.1 Design

File content is stored using content-addressable storage (CAS). The SHA-256 hash of the file content determines its identity. The `document_blobs` table maps hashes to storage paths and tracks reference counts.

Multiple `document_versions` rows (across different documents and tenants) can point to the same `content_hash`. The file content is stored once.

### 9.2 Storage Layout

```
{storage_root}/
  {tenant_id}/
    {hash[0:2]}/
      {hash[2:4]}/
        {full_hash}.{extension}
```

- `{storage_root}` is configurable (default: `data/documents/`)
- Tenant isolation via directory nesting
- Two-level directory sharding by hash prefix prevents single-directory scaling issues
- SHA-256 hash as filename provides deduplication and integrity verification

This layout matches the pattern established in the Company Management PRD for entity assets.

### 9.3 StorageBackend Protocol

The Documents system reuses the `StorageBackend` protocol from the Notes PRD (Section 11.3):

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

Initial implementation uses `LocalStorageBackend` (local disk). Future migration to `S3StorageBackend` via protocol swap.

### 9.4 Reference Counting

The `reference_count` on `document_blobs` tracks how many `document_versions` rows reference each blob. When a version is deleted (via CASCADE from parent document archive), the reference count is decremented. The orphan cleanup behavior periodically removes blobs with `reference_count = 0`.

### 9.5 Integrity Verification

On retrieval, the system can optionally verify file integrity by re-hashing the stored content and comparing to the `content_hash`. This detects storage corruption. Verification is configurable — enabled by default for downloads, disabled for thumbnail serving (performance).

---

## 10. Duplicate Detection

### 10.1 Progressive Hashing

To avoid computing full SHA-256 hashes for every upload (which is expensive for large files), the system uses progressive hashing:

1. **Quick hash** (Phase 1): Compute SHA-256 of the first 64KB + last 64KB + file size. This produces a "quick hash" that eliminates most non-duplicates instantly.
2. **Candidate check**: Query `document_blobs` for any rows matching the quick hash pattern. If no candidates, the file is unique — proceed to full hash and store.
3. **Full hash** (Phase 2, only if candidates found): Compute full SHA-256. Compare against candidate hashes.
4. **Match found**: Link the new `document_versions` row to the existing blob. Increment `reference_count`. Do not store the file content again.
5. **No match**: Store the file content normally.

### 10.2 User Notification

When a duplicate is detected, the system silently links to the existing content. A subtle notification is displayed to the user: "An identical copy of this file already exists in the system." No user action is required — the upload completes normally from the user's perspective.

### 10.3 Cross-Document Deduplication

Deduplication operates at the content level, not the document level. Two different Document entities (different names, different entity links, different folders) can share the same underlying blob if their content is identical. Each document maintains its own metadata, version history, and relationships — only the binary storage is shared.

---

## 11. Metadata Extraction

### 11.1 Extraction Pipeline

On upload (or new version), the metadata extraction behavior reads embedded metadata from the file and populates fields on the Document record and the `document_versions` row.

### 11.2 Supported Formats

| File Type | Extracted Fields | Library / Method |
|---|---|---|
| PDF | `extracted_author`, `extracted_title`, `page_count` | PDF metadata dictionary |
| Word (.docx) | `extracted_author`, `extracted_title`, `page_count` | Office Open XML core properties |
| Excel (.xlsx) | `extracted_author`, `extracted_title` | Office Open XML core properties |
| PowerPoint (.pptx) | `extracted_author`, `extracted_title`, `page_count` (slide count) | Office Open XML core properties |
| Images (JPEG, PNG, TIFF) | `width_px`, `height_px`, EXIF data (camera model, GPS, date taken stored in metadata JSONB) | Image header parsing, EXIF extraction |
| Video (MP4, MOV, WebM) | `width_px`, `height_px`, `duration_seconds` | Video container metadata |
| Audio (MP3, WAV, FLAC) | `duration_seconds`, artist/title (stored in metadata JSONB) | ID3 / audio container metadata |
| Plain text (.txt, .csv, .md) | — | No metadata extraction (content goes to text extraction) |

### 11.3 Extended Metadata

Metadata that doesn't map to a dedicated field (EXIF camera model, GPS coordinates, Office document keywords, custom document properties) is stored in a `metadata_json JSONB` column on `document_versions`. This enables future field promotion — if GPS coordinates become important, a dedicated field can be added and backfilled from the JSONB column.

```sql
-- Added to document_versions table:
metadata_json   JSONB,                     -- Extended metadata not in dedicated fields
```

### 11.4 Extraction Failure

If metadata extraction fails for a file (unsupported format, corrupted metadata), the document is still created successfully. Metadata fields remain `NULL`. An event is logged with the failure reason for diagnostic purposes.

---

## 12. Full-Text Search

### 12.1 Text Extraction

The text extraction behavior reads embedded text from supported file types:

| File Type | Extraction Method |
|---|---|
| PDF | Text layer extraction (no OCR) |
| Word (.docx) | XML text content extraction |
| Excel (.xlsx) | Cell value text extraction |
| PowerPoint (.pptx) | Slide text content extraction |
| Plain text (.txt, .md, .csv) | Direct content (file is already text) |
| HTML (.html) | Tag-stripped text content |
| Code files (.py, .js, .ts, etc.) | Direct content |

Extracted text is stored in `content_text` on the Document record.

### 12.2 PostgreSQL tsvector Configuration

Full-text search uses PostgreSQL's built-in `tsvector`/`tsquery` with a stored generated column on the `documents` table (defined in Section 5.1):

```sql
search_vector TSVECTOR GENERATED ALWAYS AS (
    setweight(to_tsvector('english', coalesce(name, '')), 'A') ||
    setweight(to_tsvector('english', coalesce(description, '')), 'B') ||
    setweight(to_tsvector('english', coalesce(content_text, '')), 'C')
) STORED
```

- **Weight A** (name): Document name matches rank highest.
- **Weight B** (description): Description matches rank second.
- **Weight C** (content): Extracted file text matches rank third.
- **English dictionary**: Stemming, stop word removal, normalization.
- **GIN index**: `idx_documents_search` enables fast full-text queries.

### 12.3 Search Query

```sql
SELECT id, name, description, category, mime_type, size_bytes,
       visibility, created_by, created_at,
       ts_rank(search_vector, query) AS rank,
       ts_headline('english', coalesce(content_text, ''), query,
                   'StartSel=<mark>, StopSel=</mark>, MaxWords=35, MinWords=15') AS snippet
FROM documents,
     plainto_tsquery('english', $1) AS query
WHERE search_vector @@ query
  AND archived_at IS NULL
  AND is_folder = false                    -- Exclude folders from content search
  AND (visibility = 'shared' OR created_by = $2)
ORDER BY rank DESC
LIMIT $3;
```

### 12.4 Search Features

| Feature | Implementation |
|---|---|
| Stemming | PostgreSQL English dictionary: "contract" matches "contracts", "contracting" |
| Ranking | `ts_rank()` with three-tier weight differentiation (name > description > content) |
| Snippets | `ts_headline()` with `<mark>` highlighting for content search results |
| Visibility filtering | Private documents excluded unless `created_by = current_user` |
| Category filtering | Optional `category` parameter to scope search (e.g., only PDFs) |
| Tenant isolation | Implicit via `search_path` |

### 12.5 Content Text Size Limit

For very large documents (e.g., a 500-page PDF), the extracted `content_text` is truncated to a configurable limit (default: 1MB of text). This prevents the `search_vector` column from becoming excessively large. The truncation is applied at extraction time; the full text is not stored.

---

## 13. Thumbnail Generation

### 13.1 Generation Pipeline

The thumbnail generation behavior creates preview images for supported file types:

| Source Type | Thumbnail Method | Output |
|---|---|---|
| Images (JPEG, PNG, GIF, WebP) | Resize to fit within max dimensions, preserve aspect ratio | JPEG or WebP |
| PDF | Render first page to image | PNG |
| Video (MP4, MOV, WebM) | Extract frame at 1-second mark (or first keyframe) | JPEG |
| Office documents | Defer to Phase 3 (requires LibreOffice headless or similar) | — |

### 13.2 Thumbnail Storage

Generated thumbnails are stored as Document entities within the system `_thumbnails` folder:

- `source = 'system'`
- `is_folder = false`
- Linked to the source document via a `thumbnail_for` relation (not Universal Attachment — this is a direct FK on the thumbnail document: `thumbnail_for_id TEXT REFERENCES documents(id)`)

```sql
-- Additional column on documents table for thumbnails:
thumbnail_for_id TEXT REFERENCES documents(id) ON DELETE SET NULL,
```

When the source document gets a new version, the existing thumbnail is replaced (new version of the thumbnail entity).

### 13.3 Thumbnail Serving

Thumbnails are served through the API with minimal overhead:

- No visibility check beyond tenant isolation (thumbnails inherit the source document's visibility)
- Aggressive caching headers (`Cache-Control: public, max-age=86400`)
- Served as the generated format (JPEG or WebP) regardless of source format

### 13.4 Configuration

| Setting | Default | Description |
|---|---|---|
| Max thumbnail width | 400px | Maximum width for generated thumbnails |
| Max thumbnail height | 400px | Maximum height for generated thumbnails |
| Thumbnail format | WebP | Output format for generated thumbnails |
| Thumbnail quality | 80 | JPEG/WebP quality percentage |

---

## 14. Document Visibility

### 14.1 Visibility Model

Documents follow the Notes-style private-by-default model:

| Level | Behavior |
|---|---|
| `private` (default) | Only the creator can see the document. |
| `shared` | Inherits visibility from linked entities and containing folders. Any user who can see a linked entity or a containing shared folder can see the document. |

### 14.2 Folder Visibility Cascade

When a folder's visibility is set to `shared`, all documents contained in that folder become effectively visible to users who can see the folder — regardless of the individual document's own visibility setting.

The **effective visibility** of a document is computed as:

```
effective_visibility = document.visibility == 'shared'
                    OR EXISTS (
                        SELECT 1 FROM document_folder_members dfm
                        JOIN documents folder ON folder.id = dfm.folder_id
                        WHERE dfm.document_id = document.id
                          AND folder.visibility = 'shared'
                          AND folder.archived_at IS NULL
                    )
```

This means:
- A private document in a shared folder is accessible to users who can see the folder.
- A shared document in a private folder is accessible to users who can see the document's linked entities.
- A private document with no shared folder membership and no shared entity links is visible only to its creator.

### 14.3 Permission Rules

| Action | Who Can Perform |
|---|---|
| View document | Creator, OR any user who can see a linked entity (when shared), OR any user with access to a containing shared folder |
| Download document | Same as view |
| Upload new version | Creator, OR users with "edit" access to at least one linked entity |
| Edit metadata | Creator, OR users with "edit" access to at least one linked entity |
| Change visibility | Creator and workspace admins |
| Archive document | Creator and workspace admins |
| Add to folder | Any user with edit access to the folder |
| Remove from folder | Any user with edit access to the folder |

### 14.4 Visibility Transitions

| Transition | Behavior |
|---|---|
| Private → Shared | The document becomes visible to users who can see linked entities or containing shared folders. A `visibility_changed` event is emitted. |
| Shared → Private | The document becomes hidden from other users (unless in a shared folder). A `visibility_changed` event is emitted. |
| Folder Private → Shared | All documents in the folder gain effective visibility through the folder. Cascade recalculation triggered. |
| Folder Shared → Private | Documents in the folder lose the folder-based visibility path. Documents may still be visible through their own settings or other shared folders. |

---

## 15. Communication Attachment Integration

### 15.1 Design

Email attachments are automatically promoted to Document entities during the email sync pipeline. This replaces the Communications PRD's standalone `communication_attachments` table with a first-class entity model.

### 15.2 Sync Flow

1. Email sync pipeline receives a message with attachments.
2. For each real attachment (excluding inline signature images, tracking pixels, etc. — as determined by the email parsing pipeline from the Communications PRD):
   a. Download the attachment content from the provider.
   b. Compute SHA-256 hash.
   c. Check for existing blob via duplicate detection.
   d. Create a Document entity with `source = 'synced'`, `name` = original filename.
   e. Create the first `document_versions` row.
   f. Link the Document to the Communication via `communication_documents`.
3. Inline signature logos that survive email stripping: if stored, they become Document entities with `source = 'synced'` and `asset_type = 'logo'`. Hash deduplication ensures each unique logo is stored exactly once.

### 15.3 Communication→Document Relation

```sql
CREATE TABLE communication_documents (
    communication_id TEXT NOT NULL,            -- FK → communications(id)
    document_id      TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    version_id       TEXT NOT NULL REFERENCES document_versions(id),  -- Exact version at time of attachment
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),

    PRIMARY KEY (communication_id, document_id)
);

CREATE INDEX idx_cd_communication ON communication_documents (communication_id);
CREATE INDEX idx_cd_document ON communication_documents (document_id);
```

The `version_id` column records which version of the document was attached to the communication. This is critical for the use case: "which version of the brochure was sent in that email."

### 15.4 Cross-PRD Reconciliation

The Communications PRD Section 12 (`communication_attachments` table and related storage strategy) is superseded by this integration. The following changes apply:

- `communication_attachments` table → replaced by `communication_documents` relation table
- `has_attachments` denormalized field on communications → retained (now reflects count of `communication_documents` rows)
- `attachment_count` denormalized field on communications → retained (now reflects count of `communication_documents` rows)
- Storage strategy (Section 12.2) → unified into Documents content-addressable storage
- Recording-transcript relationship (Section 12.3) → call recordings become Document entities with `source = 'synced'`

---

## 16. Profile Asset Integration

### 16.1 Design

Company logos, contact headshots, and company banners are stored as Document entities, replacing the Company Management PRD's `entity_assets` table and content-addressable storage system.

### 16.2 Migration Path

Existing assets in the `entity_assets` table are migrated to Document entities:

1. For each `entity_assets` row:
   a. Create a Document entity with `source = 'profile_asset'`, `asset_type` = the asset's type, `name` = derived from entity name + asset type.
   b. Create the first `document_versions` row pointing to the existing stored file (by hash).
   c. Migrate the blob into the Documents content-addressable storage layout.
   d. Link the Document to the entity via `document_entities`.
2. After migration, the `entity_assets` table is deprecated.

### 16.3 Benefits

- **Version control**: When a company rebrands, the new logo becomes version 2. The old logo is preserved in version history.
- **Unified search**: Logos and headshots are discoverable through the same search and browsing interface as all other files.
- **Deduplication**: Companies sharing the same parent logo (subsidiaries, franchise locations) store the image content once.
- **Consistent permissions**: Profile assets follow the same visibility model as all documents.

### 16.4 Profile Asset Queries

Entity detail pages need fast access to current profile assets. A convenience query:

```sql
SELECT d.id, d.name, d.asset_type, d.content_hash, d.mime_type
FROM documents d
JOIN document_entities de ON de.document_id = d.id
WHERE de.entity_type = $1
  AND de.entity_id = $2
  AND d.asset_type IS NOT NULL
  AND d.archived_at IS NULL
ORDER BY d.asset_type, d.updated_at DESC;
```

The `idx_documents_asset_type` index optimizes this query path.

---

## 17. Upload & Download

### 17.1 Upload Flow

1. Client initiates upload (multipart form data or chunked upload for large files).
2. Server receives the file content and original filename.
3. **Validation**: Check against dangerous file blocklist (see 17.3). No size limit enforced.
4. **Progressive hashing**: Quick hash → candidate check → full hash if needed (Section 10).
5. **Deduplication check**: If full hash matches existing blob, skip storage. Otherwise, store content via `StorageBackend`.
6. **Create/update records**:
   - If this is a new document: create Document entity + first `document_versions` row.
   - If this is a new version of an existing document: create new `document_versions` row, update Document metadata.
7. **Trigger behaviors**: Thumbnail generation, metadata extraction, text extraction (async, non-blocking).
8. **Return response**: Document entity with version info, download URL, and extracted metadata.

### 17.2 Download Flow

1. Client requests download for a document (optionally specifying a version).
2. Server resolves: Document → `current_version_id` (or specified version) → `document_versions` → `content_hash` → `document_blobs` → `storage_path`.
3. **Visibility check**: Verify the requesting user has access.
4. **Serve file**: Stream from `StorageBackend` with appropriate headers:
   - `Content-Type`: from `mime_type`
   - `Content-Disposition: attachment; filename="{original_name}"`
   - `Content-Length`: from `size_bytes`
   - `ETag`: `content_hash` for caching

### 17.3 Dangerous File Blocklist

The following file extensions are blocked from upload:

| Category | Extensions |
|---|---|
| Executables | `.exe`, `.bat`, `.cmd`, `.com`, `.msi`, `.scr`, `.pif` |
| Scripts | `.vbs`, `.vbe`, `.js` (standalone), `.jse`, `.wsf`, `.wsh`, `.ps1`, `.psm1` |
| System | `.sys`, `.dll`, `.drv`, `.cpl` |
| Shortcuts | `.lnk`, `.inf`, `.reg` |

The blocklist is configurable per tenant. Additional MIME type validation is performed alongside extension checking.

### 17.4 Chunked Uploads

For large files, the system supports chunked uploads:

1. Client initiates upload session, specifying total file size and filename.
2. Server returns an upload session ID.
3. Client sends file chunks (configurable chunk size, default 5MB).
4. Server writes chunks to temporary storage.
5. After all chunks received, server assembles the final file, computes hash, and proceeds with the standard upload flow.
6. Upload sessions expire after a configurable timeout (default: 24 hours).

### 17.5 Preview

Document preview uses a lightweight viewer in the client UI:

| File Type | Preview Method |
|---|---|
| Images | Native image display (full resolution, zoomable) |
| PDF | Embedded PDF viewer |
| Video | Native video player |
| Audio | Native audio player |
| Text/code files | Syntax-highlighted text display |
| Office documents | Download prompt (native preview deferred to Phase 3) |

---

## 18. Event Sourcing

### 18.1 Event Table

Per Custom Objects PRD Section 19, the Document object type has a companion event table:

```sql
CREATE TABLE documents_events (
    event_id    TEXT PRIMARY KEY,              -- evt_ prefixed ULID
    record_id   TEXT NOT NULL,                 -- FK → documents(id)
    event_type  TEXT NOT NULL,
    field_slug  TEXT,                          -- Which field changed (NULL for record-level events)
    old_value   TEXT,                          -- Previous value (serialized)
    new_value   TEXT,                          -- New value (serialized)
    metadata    JSONB,                         -- Additional context
    user_id     TEXT,                          -- Who triggered the change
    source      TEXT,                          -- 'api', 'ui', 'sync', 'automation'
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_documents_events_record ON documents_events (record_id, created_at);
CREATE INDEX idx_documents_events_type ON documents_events (event_type);
```

### 18.2 Event Types

| Event Type | Field Slug | Description |
|---|---|---|
| `record_created` | `NULL` | Document was created. `metadata` includes `{"source": "uploaded|synced|profile_asset"}`. |
| `field_updated` | The changed field | A metadata field was updated (name, description, category, custom fields). Standard event sourcing. |
| `version_created` | `NULL` | New version uploaded. `new_value` contains `{"version_id": "ver_...", "version_number": N, "content_hash": "..."}`. |
| `entity_linked` | `NULL` | Document was linked to an entity. `metadata` contains `{"entity_type": "...", "entity_id": "..."}`. |
| `entity_unlinked` | `NULL` | Document was unlinked from an entity. `metadata` contains `{"entity_type": "...", "entity_id": "..."}`. |
| `pin_toggled` | `NULL` | Pin state changed on an entity link. `metadata` contains `{"entity_type": "...", "entity_id": "...", "is_pinned": true/false}`. |
| `folder_added` | `NULL` | Document was added to a folder. `metadata` contains `{"folder_id": "doc_..."}`. |
| `folder_removed` | `NULL` | Document was removed from a folder. `metadata` contains `{"folder_id": "doc_..."}`. |
| `visibility_changed` | `visibility` | Visibility changed. `old_value`/`new_value` contain previous/new visibility. |
| `record_archived` | `NULL` | Document was soft-deleted. |
| `record_unarchived` | `NULL` | Document was restored from archive. |
| `thumbnail_generated` | `NULL` | Thumbnail was successfully generated. `metadata` contains `{"thumbnail_id": "doc_..."}`. |
| `metadata_extracted` | `NULL` | File metadata was extracted. `metadata` contains the extracted fields as JSON. |
| `text_extracted` | `NULL` | Text content was extracted for FTS. `metadata` contains `{"text_length_chars": N}`. |
| `duplicate_detected` | `NULL` | Upload matched existing content. `metadata` contains `{"matched_hash": "...", "existing_blob_refs": N}`. |

---

## 19. Virtual Schema & Data Sources

### 19.1 Virtual Schema Table

The Document object type exposes a virtual schema table for Data Sources queries. Extracted text content is not exposed as a virtual column (use the dedicated FTS search endpoint):

| Virtual Column | Source | Type |
|---|---|---|
| `id` | `documents.id` | Text (prefixed ULID) |
| `name` | `documents.name` | Text |
| `description` | `documents.description` | Text |
| `is_folder` | `documents.is_folder` | Checkbox |
| `visibility` | `documents.visibility` | Select |
| `category` | `documents.category` | Select |
| `source` | `documents.source` | Select |
| `asset_type` | `documents.asset_type` | Select |
| `mime_type` | `documents.mime_type` | Text |
| `file_extension` | `documents.file_extension` | Text |
| `size_bytes` | `documents.size_bytes` | Number |
| `version_count` | `documents.version_count` | Number |
| `content_hash` | `documents.content_hash` | Text |
| `extracted_author` | `documents.extracted_author` | Text |
| `page_count` | `documents.page_count` | Number |
| `width_px` | `documents.width_px` | Number |
| `height_px` | `documents.height_px` | Number |
| `duration_seconds` | `documents.duration_seconds` | Number |
| `has_thumbnail` | `documents.has_thumbnail` | Checkbox |
| `created_by` | `documents.created_by` → `platform.users` | User |
| `updated_by` | `documents.updated_by` → `platform.users` | User |
| `created_at` | `documents.created_at` | Datetime |
| `updated_at` | `documents.updated_at` | Datetime |
| User-added custom fields | As defined | As defined |

### 19.2 Linked Entities Column

The universal attachment relation introduces the "Linked Entities" column type in the Views system (same as Notes and Tasks):

- Displays entities linked to each document as entity chips
- Filter support: `has_link_to_type`, `has_link_to`, `link_count`

### 19.3 Data Source JOINs

```sql
-- Documents linked to contacts
SELECT d.id, d.name, d.category, c.first_name, c.last_name
FROM documents d
JOIN document_entities de ON de.document_id = d.id AND de.entity_type = 'contacts'
JOIN contacts c ON c.id = de.entity_id
WHERE d.archived_at IS NULL
  AND d.is_folder = false
  AND (d.visibility = 'shared' OR d.created_by = $current_user);
```

### 19.4 Folder Contents Query

```sql
-- Documents in a specific folder
SELECT d.id, d.name, d.is_folder, d.category, d.size_bytes, d.updated_at
FROM documents d
JOIN document_folder_members dfm ON dfm.document_id = d.id
WHERE dfm.folder_id = $folder_id
  AND d.archived_at IS NULL
ORDER BY d.is_folder DESC, d.name ASC;
```

---

## 20. API Design

### 20.1 Documents CRUD

| Endpoint | Method | Description |
|---|---|---|
| `/api/v1/documents` | GET | List documents. Supports filters: `entity_type` + `entity_id` (documents for an entity), `folder_id` (folder contents), `is_folder`, `category`, `source`, `created_by`, `visibility`. Paginated. |
| `/api/v1/documents` | POST | Create a document (upload). Multipart form data with file + metadata (name, description, visibility, entity links, folder placement). Returns document with first version. |
| `/api/v1/documents/{id}` | GET | Get a document with current version info and entity links. |
| `/api/v1/documents/{id}` | PATCH | Update document metadata (name, description, visibility, custom fields). |
| `/api/v1/documents/{id}` | DELETE | Soft-delete (archive) the document. |
| `/api/v1/documents/{id}/unarchive` | POST | Restore an archived document. |
| `/api/v1/documents/{id}/download` | GET | Download the current version's file content. |
| `/api/v1/documents/{id}/preview` | GET | Get preview/thumbnail URL. |

### 20.2 Folder Operations

| Endpoint | Method | Description |
|---|---|---|
| `/api/v1/documents/folders` | POST | Create a folder. Body: `name`, `description`, `visibility`, `parent_folder_id` (optional). |
| `/api/v1/documents/{folder_id}/members` | GET | List folder contents. Paginated. Sub-folders first. |
| `/api/v1/documents/{folder_id}/members` | POST | Add a document or sub-folder to a folder. Body: `document_id`. |
| `/api/v1/documents/{folder_id}/members/{document_id}` | DELETE | Remove a document from a folder (does not archive the document). |

### 20.3 Version Management

| Endpoint | Method | Description |
|---|---|---|
| `/api/v1/documents/{id}/versions` | GET | List all versions (id, version_number, name, description, size_bytes, uploaded_by, created_at). Newest first. |
| `/api/v1/documents/{id}/versions` | POST | Upload a new version. Multipart form data with file + optional version name/description. Returns 204 if hash matches current version (no-op). |
| `/api/v1/documents/{id}/versions/{version_id}` | GET | Get a specific version's metadata. |
| `/api/v1/documents/{id}/versions/{version_id}` | PATCH | Update version name/description. |
| `/api/v1/documents/{id}/versions/{version_id}/download` | GET | Download a specific version's file content. |

### 20.4 Entity Linking

| Endpoint | Method | Description |
|---|---|---|
| `/api/v1/documents/{id}/entities` | GET | List all entities linked to a document. |
| `/api/v1/documents/{id}/entities` | POST | Link document to an entity. Body: `entity_type`, `entity_id`. Returns 409 if duplicate. |
| `/api/v1/documents/{id}/entities/{entity_type}/{entity_id}` | DELETE | Unlink document from entity. |
| `/api/v1/documents/{id}/entities/{entity_type}/{entity_id}/pin` | POST | Toggle pin state for this entity link. |

### 20.5 Search

| Endpoint | Method | Description |
|---|---|---|
| `/api/v1/documents/search` | GET | Full-text search. Params: `q` (search text), `category` (optional filter), `limit`. Returns ranked results with content snippets and entity links. Respects visibility. |

### 20.6 Chunked Uploads

| Endpoint | Method | Description |
|---|---|---|
| `/api/v1/documents/uploads` | POST | Initiate chunked upload session. Body: `filename`, `total_size_bytes`, `document_id` (optional, for new version). Returns `upload_session_id`. |
| `/api/v1/documents/uploads/{session_id}` | PATCH | Upload a chunk. Body: binary chunk data. Headers: `Content-Range`. |
| `/api/v1/documents/uploads/{session_id}` | POST | Complete chunked upload. Assembles file, triggers standard upload flow. |
| `/api/v1/documents/uploads/{session_id}` | DELETE | Cancel upload session. Cleans up temporary chunks. |

### 20.7 Pagination

List endpoints use cursor-based pagination with `updated_at` as the cursor field:
- `?limit=20&after={cursor}` for forward pagination
- Response includes `next_cursor` when more results exist

---

## 21. Design Decisions

| Decision | Choice | Rationale |
|---|---|---|
| **Framework position** | System object type (`doc_` prefix) | Full participation in Views, Data Sources, event sourcing, and the Custom Objects framework. Version control, folder hierarchy, and 7 registered behaviors require system entity status. |
| **Entity linking** | Universal attachment relation (`target = *`) | Enables attachment to all entity types (system + custom) without per-type relation definitions. Consistent with Notes and Tasks. |
| **Folders as entities** | `is_folder = true` flag on Document entity | Enables folders to participate in Universal Attachment, event sourcing, Views, and custom fields. Eliminates a separate folder table. |
| **Folder membership** | Many-to-many via `document_folder_members` | A document can exist in multiple folders. This is a link, not a containment relationship. Consistent with how entity linking works. |
| **Version control** | Hash-based, automatic on re-upload with different hash | Eliminates manual "create new version" workflows. Hash comparison is deterministic and requires no user decision. |
| **Content-addressable storage** | SHA-256 hash as content identifier | Automatic deduplication. Integrity verification. Consistent with Company Management PRD asset storage pattern. |
| **Progressive hashing** | Quick hash (first + last 64KB) then full hash | Avoids computing full SHA-256 for every upload. Most files are unique and eliminated by quick hash. |
| **Visibility model** | Private by default, matching Notes | Privacy-first. Consistent with Notes. Folder cascade adds a document-specific extension. |
| **Folder visibility cascade** | Shared folder makes contents accessible | Natural expectation: sharing a folder shares its contents. Effective visibility is computed, not stored. |
| **No size/type restrictions** | Blocklist for dangerous executables only | A document management system should accept any business file. Chunked uploads handle large files. |
| **Communication attachment migration** | Email attachments → Document entities | Unified file model. Enables version tracking across email sends. Eliminates a separate attachment storage system. |
| **Profile asset migration** | Logos/headshots → Document entities | Version control for profile images. Unified storage. Eliminates `entity_assets` table. |
| **Note attachments unchanged** | Inline images remain tightly coupled to Notes | Pasted images are part of the note's content, not standalone documents. Avoids double-indexing and confusing UI ("my screenshot appears in both Notes and Documents"). |
| **Thumbnail as Document entity** | Thumbnails stored in system `_thumbnails` folder | Reuses the same storage infrastructure. System folder hides them from user views. |
| **Storage backend** | Local disk + `StorageBackend` protocol | Minimizes infrastructure for initial deployment. Cloud migration via protocol swap. Reuses Notes protocol. |
| **FTS approach** | PostgreSQL `tsvector`/`tsquery` with three-tier weighting | Name > description > content ranking. Built-in stemming, snippets. No external infrastructure. Consistent with Notes. |
| **No OCR** | Text extraction from embedded text only | OCR is a significant dependency (Tesseract, cloud APIs) with variable quality. Deferred to future phase. |

---

## 22. Phasing & Roadmap

### Phase 1 — Core Documents (MVP)

**Goal:** Document management operational as a system object type with upload, version control, and single-entity attachment.

**Scope:**
- Object type registered in framework (`doc_` prefix, field registry, event sourcing)
- Documents CRUD API
- Single-entity attachment (create document on an entity)
- File upload with hash-based versioning
- Content-addressable storage with deduplication
- Dangerous file blocklist
- Private/shared visibility with private default
- Pinning per entity link
- Entity detail page integration (documents panel on all system entity types)
- Basic metadata extraction (file size, MIME type, extension)

**Not in Phase 1:** Folders, multi-entity linking, chunked uploads, metadata extraction beyond basics, text extraction, FTS, thumbnails, communication attachment integration, profile asset migration, Views/Data Sources integration.

### Phase 2 — Folders, Search & Metadata

**Goal:** Folder organization, full-text search, and rich metadata extraction.

**Scope:**
- Folder creation and nesting
- Many-to-many folder membership
- Multi-entity linking (add/remove entity links on existing documents)
- Universal attachment for custom object types
- Full metadata extraction pipeline (PDF, Office, images, video, audio)
- Text extraction for supported file types
- PostgreSQL FTS with stored generated column
- Global document search endpoint
- Thumbnail generation for images and PDFs
- Chunked uploads for large files
- Folder visibility cascade

### Phase 3 — Integration & Migration

**Goal:** Communication attachment and profile asset migration. Unified file model.

**Scope:**
- Communication attachment promotion (email sync creates Document entities)
- `communication_documents` relation table with version tracking
- Profile asset migration (entity_assets → Documents)
- Communications PRD reconciliation (deprecate `communication_attachments`)
- Company Management PRD reconciliation (deprecate `entity_assets`)
- Video thumbnail generation
- Office document preview (LibreOffice headless)

### Phase 4 — Advanced Features

**Goal:** Cloud storage, graph integration, and enhanced capabilities.

**Scope:**
- Cloud storage backend (S3/GCS) via `StorageBackend` protocol swap
- Neo4j sync for document-entity links (`HAS_DOCUMENT` edges)
- Document virtual schema table in Data Sources
- Document views in Views system (Grid, Gallery)
- Linked Entities column type integration
- OCR support for scanned PDFs and images (Tesseract or cloud API)
- Document templates (pre-configured folder structures for common scenarios)
- Bulk upload and batch operations

---

## 23. Dependencies & Related PRDs

| Dependency | Nature | Details |
|---|---|---|
| **[Custom Objects PRD](custom-objects-prd_v2.md)** | **Structural** | Provides the object type framework, field registry, event sourcing, and tenant schema provisioning that Documents uses. The Universal Attachment Relation extends the relation type model. |
| **[Notes PRD](notes-prd_V3.md)** | **Pattern** | Introduced the Universal Attachment Relation pattern and `StorageBackend` protocol reused by Documents. Note inline attachments remain independent of the Documents system. |
| **[Tasks PRD](tasks-prd_V2.md)** | **Consumer** | Tasks can attach to Documents for file-related action items. Documents can attach to Tasks for deliverable tracking. |
| **[Communications PRD](communications-prd_V1.md)** | **Integration** | Communication attachments migrate to Document entities (Phase 3). The `communication_attachments` table is replaced by `communication_documents`. |
| **[Company Management PRD](company-management-prd_V1.md)** | **Integration** | Profile assets (logos, headshots, banners) migrate to Document entities (Phase 3). The `entity_assets` table is deprecated. |
| **[Permissions & Sharing PRD](permissions-sharing-prd_V2.md)** | **Behavioral** | Defines the entity-level visibility rules that shared documents inherit. The folder cascade model extends the Notes visibility pattern. |
| **[Data Sources PRD](data-sources-prd_V1.md)** | **Integration** | The Document virtual schema table (Phase 4) follows the Data Sources convention. The `doc_` prefix enables automatic entity detection. |
| **[Views & Grid PRD](views-grid-prd_V5.md)** | **Integration** | Document views (Phase 4) use Grid and Gallery view types. The Linked Entities column type is shared with Notes and Tasks. |
| **[Contact Management PRD](contact-management-prd_V5.md)** | **Consumer** | Contact detail pages display linked documents. |
| **[Event Management PRD](events-prd_V3.md)** | **Consumer** | Event detail pages display linked documents. |
| **[Projects PRD](projects-prd_V3.md)** | **Consumer** | Project detail pages display linked documents and folders. |
| **[Conversations PRD](conversations-prd_V4.md)** | **Consumer** | Conversation detail pages display linked documents. |

---

## 24. Open Questions

| # | Question | Context | Impact |
|---|---|---|---|
| 1 | Should folder membership be tracked in the event sourcing table or only in `document_folder_members`? | Currently, `folder_added` and `folder_removed` events are defined. But if folder membership changes frequently (batch reorganization), this could generate high event volume. | Event table size vs. audit completeness trade-off. |
| 2 | How should the system handle file type changes between versions? | A user uploads a Word doc as version 1, then uploads a PDF (exported from Word) as version 2. The category, MIME type, and extension all change. Is this valid? | Version model flexibility vs. semantic consistency. |
| 3 | Should there be a maximum number of folders a single document can belong to? | Unbounded folder membership could create confusing situations (a document appearing in 50 folders). | UX and query performance consideration. |
| 4 | How should Documents interact with a future global search that spans all entity types? | Documents have their own FTS endpoint. A unified search bar would need to federate across Documents, Notes, Communications, and entity fields. | Architecture consideration for future global search feature. |
| 5 | Should the system extract and index text from email body content when promoting email attachments? | The email body is already stored on the Communication record. But indexing it alongside the document could improve discoverability. | Scope boundary between Communications and Documents FTS. |
| 6 | What is the storage quota model? | No file size limits, no type restrictions, and hash-based deduplication all imply potentially unbounded storage growth. Should there be per-tenant storage quotas? | Infrastructure cost and business model consideration. |
| 7 | Should document download/view events be tracked for analytics? | "Who viewed this contract?" is a common compliance requirement. Currently, only mutations are event-sourced. | Privacy vs. audit trail trade-off. May warrant a separate access log rather than event sourcing. |
| 8 | How should the `_thumbnails` system folder interact with the orphan cleanup behavior? | Thumbnails are Document entities but serve a support function. If the source document is archived, should the thumbnail also be archived? | Thumbnail lifecycle management. |

---

## 25. Future Work

### 25.1 Document Templates

Pre-configured folder structures for common scenarios: "New Client Onboarding" (with sub-folders for Contracts, Proposals, Correspondence), "Job Site Documentation" (Photos, Permits, Invoices), or custom templates defined by workspace admins.

### 25.2 OCR Support

Optical character recognition for scanned PDFs and images, enabling full-text search on documents that contain only image-based text. Integration with Tesseract (self-hosted) or cloud OCR APIs (Google Vision, AWS Textract).

### 25.3 Document Approval Workflows

Status-based workflows for document review and approval: Draft → Under Review → Approved → Published. Custom fields on Documents can enable basic status tracking immediately; a dedicated workflow engine is a future enhancement.

### 25.4 Document Sharing via Link

Generate a shareable URL for a document (or a specific version) that can be sent to external parties. The shared view would be read-only, time-limited, and optionally password-protected.

### 25.5 Bulk Operations

Batch upload (drag-and-drop a folder from desktop), batch move/copy between folders, batch entity linking, and batch archival.

### 25.6 Office Document Preview

Server-side rendering of Office documents (Word, Excel, PowerPoint) for in-browser preview without download, using LibreOffice headless or a cloud-based conversion service.

### 25.7 Document Diffing

Visual comparison between two versions of a document. For text-based files (code, markdown, plain text), a standard diff view. For PDFs and images, a side-by-side or overlay comparison.

### 25.8 AI Document Intelligence

AI-powered document analysis: automatic summarization, entity extraction (find company names, dates, amounts in contracts), classification, and content-based recommendations ("documents similar to this one").

---

## 26. Glossary

General platform terms (Entity Bar, Detail Panel, Card-Based Architecture, Attribute Card, etc.) are defined in the **[Master Glossary V3](glossary_V3.md)**. The following terms are specific to this subsystem:

| Term | Definition |
|---|---|
| **Document** | A first-class entity in the CRM representing a file or folder. System object type with `doc_` prefix, version control, metadata extraction, and universal entity attachment. |
| **Folder** | A Document entity with `is_folder = true`. Contains other documents and folders via many-to-many membership. Participates in Universal Attachment like any document. |
| **Version** | A specific revision of a document's file content, stored in `document_versions`. Each version has its own hash, metadata snapshot, and optional name/description. |
| **Blob** | The raw binary content of a file, stored once via content-addressable storage in `document_blobs`. Multiple versions (across documents) can reference the same blob. |
| **Content-Addressable Storage (CAS)** | Storage scheme where the file's SHA-256 hash determines its identity and storage path. Provides automatic deduplication and integrity verification. |
| **Progressive Hashing** | Two-phase hash computation: a quick hash (first + last 64KB) eliminates most non-duplicates, followed by a full SHA-256 only when the quick hash finds candidates. |
| **Universal Attachment Relation** | A relation type where the target side is `*` (any registered object type), enabling documents to link to records of any type without per-type relation definitions. |
| **Visibility Cascade** | The mechanism by which a shared folder makes its contained documents accessible to users who can see the folder, regardless of individual document visibility settings. |
| **Effective Visibility** | The computed accessibility of a document: its own visibility setting combined with any folder-based cascade paths. A document is accessible if it is shared OR in any shared folder. |
| **Communication→Document Relation** | The `communication_documents` table linking email messages to the Document entities representing their attachments, including a `version_id` for precise version tracking. |
| **Profile Asset** | A Document entity with `source = 'profile_asset'` and an `asset_type` (logo, headshot, banner), representing company and contact profile images. |
| **System Folder** | A folder with `source = 'system'` created by the platform for internal use (thumbnails, profile assets). Hidden from default user-facing views. |
| **Orphan Blob** | A `document_blobs` row with `reference_count = 0`, meaning no `document_versions` reference it. Cleaned up by the orphan cleanup behavior. |
| **Linked Entities Column** | A column type in the Views system that displays entities linked to a document through the universal attachment relation, rendered as entity chips with mixed types. |
| **Display Name Field** | The field designated as the record's human-readable title. For Documents, this is `name`. |
