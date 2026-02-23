# Document — Communication & Profile Asset Integration Sub-PRD

**Version:** 1.0
**Last Updated:** 2026-02-23
**Status:** Draft
**Entity Base PRD:** [document-entity-base-prd.md]
**Referenced Entity PRDs:** [communication-entity-base-prd.md] (attachment source), [communication-provider-sync-prd.md] (sync pipeline), [company-entity-base-prd.md] (profile assets)

---

## 1. Overview

### 1.1 Purpose

This sub-PRD defines two cross-PRD migrations that unify file storage into the Document entity model: email attachment promotion (communication attachments become Document entities during sync) and profile asset migration (logos, headshots, and banners move from entity_assets to Document entities). Both eliminate separate storage systems in favor of the unified, version-controlled, searchable Document model.

### 1.2 Preconditions

- Document entity and upload pipeline operational.
- Content-addressable storage and deduplication operational.
- Email sync pipeline delivering attachments (Communication Provider & Sync Framework).
- Existing entity_assets table with profile assets (Company Management PRD).

---

## 2. Context

### 2.1 Relevant Fields

| Field | Role in This Action |
|---|---|
| source | `synced` for email attachments, `profile_asset` for migrated assets |
| asset_type | `logo`, `headshot`, `banner` for profile assets. NULL for email attachments. |
| content_hash | Deduplication key — identical attachments across emails stored once |

### 2.2 Cross-PRD Reconciliation

This integration supersedes:

- **Communications PRD** Section 12 (`communication_attachments` table) → replaced by `communication_documents` relation table
- **Communications PRD** `has_attachments` and `attachment_count` denormalized fields → retained, now reflect communication_documents row count
- **Communications PRD** storage strategy → unified into Documents CAS
- **Company Management PRD** `entity_assets` table → deprecated after migration
- **Company Management PRD** asset storage → unified into Documents CAS

---

## 3. Key Processes

### KP-1: Email Attachment Promotion During Sync

**Trigger:** Email sync pipeline receives a message with attachments.

**Step 1 — Attachment identification:** For each real attachment (excluding inline signature images, tracking pixels, and boilerplate per email parsing pipeline):

**Step 2 — Download:** Download attachment content from email provider.

**Step 3 — Hash and deduplicate:** Compute SHA-256. Check document_blobs for existing content. If match, link to existing blob.

**Step 4 — Create Document:** Create Document entity with source = 'synced', name = original filename. Create first document_versions row.

**Step 5 — Link to Communication:** Insert row in communication_documents with document_id, communication_id, and version_id (recording exact version at time of attachment).

**Step 6 — Inline logos:** Signature logos that survive email stripping become Documents with source = 'synced', asset_type = 'logo'. Deduplication ensures each unique logo stored once.

### KP-2: Profile Asset Migration

**Trigger:** One-time migration job (Phase 3 deployment).

**Step 1 — Enumerate assets:** For each row in entity_assets table:

**Step 2 — Create Document:** Document entity with source = 'profile_asset', asset_type = the asset's type, name = entity name + asset type.

**Step 3 — Version creation:** First document_versions row pointing to existing stored file (by hash).

**Step 4 — Migrate blob:** Move content into Documents CAS layout. Create/update document_blobs entry.

**Step 5 — Link to entity:** Insert row in document_entities linking the Document to the original entity (company or contact).

**Step 6 — Deprecate source:** After all assets migrated, mark entity_assets table as deprecated.

### KP-3: Querying Communication Attachments

**Trigger:** User views a communication's attachments.

**Step 1 — Query:** Join communication_documents → documents to list attachments. Include version info for "which version was attached."

**Step 2 — Display:** Show document name, type icon, size, and download link. Each attachment links to its Document entity for full version history and entity links.

### KP-4: Querying Profile Assets

**Trigger:** Entity detail page loads and needs profile images.

**Step 1 — Query:** Join document_entities → documents where asset_type IS NOT NULL for the entity.

**Step 2 — Display:** Serve current version of logo/headshot/banner. Version history available for rebrand tracking.

---

## 4. Communication Attachment Integration

**Supports processes:** KP-1, KP-3

### 4.1 Sync Flow Detail

The email sync pipeline (Communication Provider & Sync Framework Sub-PRD) produces normalized Communication records. For each communication with attachments:

1. Provider adapter downloads attachment binary content.
2. Attachment metadata captured: original_filename, content_type, size.
3. Document upload pipeline invoked (same as user upload but with source = 'synced').
4. communication_documents row created with version_id snapshot.

### 4.2 Version Tracking on Communications

The `version_id` column in communication_documents records the exact version at time of attachment. This enables the core use case: "version 3 of the brochure was current when attached to the email sent to John Smith on January 15th."

If the same document is attached to a later email after a new version is uploaded, the new communication_documents row captures the newer version_id.

### 4.3 Deduplication Benefits

Email threads often include the same attachment repeatedly (each reply forwards the attachment). SHA-256 deduplication ensures the content is stored once. Each communication_documents row links to the same blob through its version, but tracks which communication referenced it.

**Tasks:**

- [ ] DINT-01: Implement attachment download from email provider during sync
- [ ] DINT-02: Implement Document entity creation with source = 'synced'
- [ ] DINT-03: Implement communication_documents link with version_id
- [ ] DINT-04: Implement inline logo detection and Document creation with asset_type = 'logo'
- [ ] DINT-05: Implement attachment deduplication across email threads
- [ ] DINT-06: Implement communication attachment query (list attachments for a communication)
- [ ] DINT-07: Implement attachment count denormalization on Communication record

**Tests:**

- [ ] DINT-T01: Test email attachment creates Document entity with source = 'synced'
- [ ] DINT-T02: Test communication_documents records correct version_id
- [ ] DINT-T03: Test duplicate attachment across thread replies stored once (single blob)
- [ ] DINT-T04: Test inline logo creates Document with asset_type = 'logo'
- [ ] DINT-T05: Test attachment query returns all documents for a communication
- [ ] DINT-T06: Test attachment_count on Communication reflects communication_documents count
- [ ] DINT-T07: Test excluded attachments (tracking pixels, inline images) not promoted

---

## 5. Profile Asset Migration

**Supports processes:** KP-2, KP-4

### 5.1 Migration Requirements

- All existing entity_assets rows migrate to Document entities.
- Hash-based content is moved into Documents CAS layout.
- Entity links created via document_entities.
- entity_assets table deprecated after complete migration.
- Migration is idempotent (re-runnable without duplicates).

### 5.2 Benefits of Migration

| Benefit | Description |
|---|---|
| Version control | Company rebrand → logo v2. Old logo preserved in history. |
| Unified search | Logos/headshots discoverable through same interface as all files. |
| Deduplication | Subsidiaries sharing parent logo store content once. |
| Consistent permissions | Profile assets follow standard visibility model. |

### 5.3 Profile Asset Queries

Entity detail pages use optimized queries with `idx_documents_asset_type` index for fast profile asset retrieval by entity.

**Tasks:**

- [ ] DINT-08: Implement entity_assets → Document migration script
- [ ] DINT-09: Implement idempotent migration (hash-based duplicate check)
- [ ] DINT-10: Implement document_entities links for migrated assets
- [ ] DINT-11: Implement profile asset query for entity detail pages
- [ ] DINT-12: Implement entity_assets deprecation flag

**Tests:**

- [ ] DINT-T08: Test migration creates Document entity for each asset
- [ ] DINT-T09: Test migration is idempotent (re-run produces no duplicates)
- [ ] DINT-T10: Test migrated asset linked to original entity via document_entities
- [ ] DINT-T11: Test profile asset query returns correct assets for entity
- [ ] DINT-T12: Test version history available for migrated assets
