# Document — Upload, Versioning & Storage Sub-PRD

**Version:** 1.0
**Last Updated:** 2026-02-23
**Status:** Draft
**Entity Base PRD:** [document-entity-base-prd.md]

---

## 1. Overview

### 1.1 Purpose

This sub-PRD defines the core file handling pipeline: how files enter the system (upload and chunked upload), how versions are managed (hash-based automatic versioning), how content is stored and deduplicated (content-addressable storage with reference counting), and how files are served (download and preview). It also covers the dangerous file blocklist and integrity verification.

### 1.2 Preconditions

- Document entity is registered and operational.
- StorageBackend implementation available.

---

## 2. Context

### 2.1 Relevant Fields

| Field | Role in This Action |
|---|---|
| content_hash | SHA-256 of current version. Key for deduplication and version change detection. |
| current_version_id | Points to latest version row. Updated on new version. |
| version_count | Incremented on new version. |
| size_bytes | Size of current version content. |
| mime_type | MIME type from current version. |
| file_extension | Extension from current version filename. |

### 2.2 Cross-Entity Context

- **Content Processing Sub-PRD:** Metadata extraction, text extraction, and thumbnail generation are triggered after upload completes. This sub-PRD defines the upload; Content Processing defines post-upload behaviors.
- **Integration Sub-PRD:** Email attachment sync and profile asset migration use the same upload pipeline.

---

## 3. Key Processes

### KP-1: Standard Upload (New Document)

**Trigger:** User uploads a file or API call with multipart form data.

**Step 1 — Blocklist validation:** Check file extension and MIME type against dangerous file blocklist. Reject if blocked.

**Step 2 — Progressive hashing:** Compute quick hash (first 64KB + last 64KB). Check for candidates in document_blobs. If candidate found, compute full SHA-256. If no candidate, compute full SHA-256.

**Step 3 — Deduplication check:** If full hash matches existing blob, increment blob's reference_count and skip storage. Otherwise, store content via StorageBackend.

**Step 4 — Record creation:** Create Document entity. Create first document_versions row (version_number = 1). Set document's current_version_id, content_hash, size_bytes, mime_type, file_extension.

**Step 5 — Queue behaviors:** Thumbnail generation, metadata extraction, text extraction dispatched asynchronously.

### KP-2: Re-Upload (New Version)

**Trigger:** User uploads a file to an existing document.

**Step 1 — Hash computation:** Same progressive hashing as KP-1.

**Step 2a — Same hash:** Content identical to current version. Return 204 No Content. No new version created.

**Step 2b — Different hash:** Content changed. Proceed with deduplication check and storage.

**Step 3 — Version creation:** Create new document_versions row (version_number incremented). Update document's current_version_id, version_count, content_hash, and file property fields.

**Step 4 — Queue behaviors:** Re-trigger thumbnail, metadata, and text extraction for new version content.

### KP-3: Download

**Trigger:** User or API requests file download.

**Step 1 — Resolve path:** Document → current_version_id (or specified version_id) → document_versions → content_hash → document_blobs → storage_path.

**Step 2 — Visibility check:** Verify requesting user has access (per Entity Base PRD permission rules).

**Step 3 — Serve file:** Stream from StorageBackend with headers: Content-Type (mime_type), Content-Disposition (attachment; filename), Content-Length (size_bytes), ETag (content_hash).

### KP-4: Chunked Upload

**Trigger:** Client initiates chunked upload for large files.

**Step 1 — Session creation:** Client sends filename, total_size_bytes, optional document_id. Server returns upload_session_id.

**Step 2 — Chunk upload:** Client sends chunks with Content-Range headers. Server writes to temporary storage.

**Step 3 — Completion:** Client signals completion. Server assembles final file, computes hash, proceeds with standard upload flow (KP-1 or KP-2).

**Step 4 — Expiry:** Incomplete sessions expire after configurable timeout (default: 24 hours). Temporary chunks cleaned up.

---

## 4. Version Control

**Supports processes:** KP-1, KP-2

### 4.1 Requirements

Versions are append-only, numbered, and store full content references (no diffs):

| Action | Behavior |
|---|---|
| Initial upload | Version 1 created. Document metadata set. |
| Re-upload (different hash) | New version. Document metadata updated to match. |
| Re-upload (same hash) | No-op (204). |
| Update version metadata | name/description on version row updated without new version. |
| View old version | Client requests specific version_id → download from that version's blob. |
| Archive document | All versions retained. Blobs persist. |

### 4.2 Version Metadata Snapshots

Each version stores its own metadata (author, page_count, dimensions, etc.). Document record always reflects current version. This enables "v1 had 12 pages, v2 has 15."

**Tasks:**

- [ ] DUPS-01: Implement version creation on upload with hash change detection
- [ ] DUPS-02: Implement same-hash no-op (204 response)
- [ ] DUPS-03: Implement version numbering with UNIQUE constraint
- [ ] DUPS-04: Implement document metadata update on new version
- [ ] DUPS-05: Implement version metadata snapshot (per-version extracted fields)
- [ ] DUPS-06: Implement version name/description update without new version

**Tests:**

- [ ] DUPS-T01: Test first upload creates version 1
- [ ] DUPS-T02: Test re-upload with different hash creates version 2
- [ ] DUPS-T03: Test re-upload with same hash returns 204, no new version
- [ ] DUPS-T04: Test document metadata reflects current version
- [ ] DUPS-T05: Test version metadata snapshot is independent of document record
- [ ] DUPS-T06: Test version name/description update does not create new version

---

## 5. Content-Addressable Storage

**Supports processes:** KP-1, KP-2, KP-3

### 5.1 Storage Layout

```
{storage_root}/
  {tenant_id}/
    {hash[0:2]}/
      {hash[2:4]}/
        {full_hash}.{extension}
```

Two-level directory sharding by hash prefix prevents single-directory scaling issues. Tenant isolation via directory nesting.

### 5.2 StorageBackend Protocol

Reuses protocol from Notes PRD:

```python
class StorageBackend(Protocol):
    async def store(tenant_id, filename, data) -> str   # Returns storage_path
    async def retrieve(storage_path) -> bytes
    async def delete(storage_path) -> None
    def get_url(storage_path) -> str
```

Initial: LocalStorageBackend. Future: S3StorageBackend via protocol swap.

### 5.3 Reference Counting

`reference_count` on document_blobs tracks version references. Decremented on version deletion (CASCADE). Orphan cleanup removes blobs with count = 0.

### 5.4 Integrity Verification

On retrieval, optionally re-hash stored content and compare to content_hash. Enabled by default for downloads, disabled for thumbnail serving (performance).

**Tasks:**

- [ ] DUPS-07: Implement StorageBackend (LocalStorageBackend)
- [ ] DUPS-08: Implement content-addressable storage layout with hash sharding
- [ ] DUPS-09: Implement reference counting (increment on version create, decrement on delete)
- [ ] DUPS-10: Implement orphan cleanup background job
- [ ] DUPS-11: Implement integrity verification on download

**Tests:**

- [ ] DUPS-T07: Test file stored at correct hash-based path
- [ ] DUPS-T08: Test reference count incremented when new version references existing blob
- [ ] DUPS-T09: Test reference count decremented on version CASCADE delete
- [ ] DUPS-T10: Test orphan cleanup removes blobs with reference_count = 0
- [ ] DUPS-T11: Test integrity verification detects corrupted content

---

## 6. Progressive Hashing & Duplicate Detection

**Supports processes:** KP-1, KP-2

### 6.1 Progressive Hashing

To avoid computing full SHA-256 for every upload:

1. **Quick hash:** Hash the first 64KB + last 64KB of the file.
2. **Candidate check:** Query document_blobs for matching quick hashes. If no candidates → file is unique. Compute full SHA-256 and store.
3. **Full hash:** If candidates found, compute full SHA-256. If full hash matches → deduplicate. If not → new unique content.

### 6.2 User Notification

When a duplicate is detected, the system silently links to existing content. A subtle notification: "An identical copy of this file already exists." No action required — upload completes normally.

### 6.3 Cross-Document Deduplication

Deduplication is at the content level. Two documents with different names, entity links, and folders can share the same blob if content is identical. Each maintains its own metadata and relationships.

**Tasks:**

- [ ] DUPS-12: Implement progressive hashing (quick hash → candidate → full hash)
- [ ] DUPS-13: Implement duplicate detection (link to existing blob)
- [ ] DUPS-14: Implement duplicate notification to client

**Tests:**

- [ ] DUPS-T12: Test quick hash eliminates non-duplicates
- [ ] DUPS-T13: Test full hash confirms true duplicates
- [ ] DUPS-T14: Test duplicate links to existing blob, increments reference_count
- [ ] DUPS-T15: Test duplicate notification returned to client

---

## 7. Upload & Download Flow

**Supports processes:** KP-1, KP-2, KP-3, KP-4

### 7.1 Dangerous File Blocklist

| Category | Extensions |
|---|---|
| Executables | .exe, .bat, .cmd, .com, .msi, .scr, .pif |
| Scripts | .vbs, .vbe, .js (standalone), .jse, .wsf, .wsh, .ps1, .psm1 |
| System | .sys, .dll, .drv, .cpl |
| Shortcuts | .lnk, .inf, .reg |

Configurable per tenant. MIME type validation alongside extension checking.

### 7.2 Chunked Upload Requirements

- Configurable chunk size (default: 5MB)
- Upload sessions expire after configurable timeout (default: 24 hours)
- Chunks stored in temporary location until completion
- On completion: assemble, hash, proceed with standard flow

### 7.3 Preview

| File Type | Preview Method |
|---|---|
| Images | Native image display (full resolution, zoomable) |
| PDF | Embedded PDF viewer |
| Video | Native video player |
| Audio | Native audio player |
| Text/code | Syntax-highlighted text display |
| Office | Download prompt (deferred) |

**Tasks:**

- [ ] DUPS-15: Implement upload flow with blocklist validation
- [ ] DUPS-16: Implement download flow with visibility check and streaming
- [ ] DUPS-17: Implement chunked upload session management
- [ ] DUPS-18: Implement chunk assembly and hash computation
- [ ] DUPS-19: Implement upload session expiry and cleanup
- [ ] DUPS-20: Implement file preview routing by type

**Tests:**

- [ ] DUPS-T16: Test blocklisted extension rejected
- [ ] DUPS-T17: Test blocklisted MIME type rejected
- [ ] DUPS-T18: Test download serves correct content with headers
- [ ] DUPS-T19: Test download respects visibility (private not accessible by others)
- [ ] DUPS-T20: Test chunked upload assembles correctly
- [ ] DUPS-T21: Test expired upload session cleaned up
- [ ] DUPS-T22: Test preview URL returns appropriate format
