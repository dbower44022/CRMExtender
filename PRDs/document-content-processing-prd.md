# Document — Content Processing Pipeline Sub-PRD

**Version:** 1.0
**Last Updated:** 2026-02-23
**Status:** Draft
**Entity Base PRD:** [document-entity-base-prd.md]
**Referenced Entity PRDs:** [document-upload-storage-prd.md] (triggers processing)

---

## 1. Overview

### 1.1 Purpose

This sub-PRD defines the three post-upload processing behaviors: metadata extraction (reading embedded file properties), text extraction (extracting searchable text content), and thumbnail generation (creating visual previews). All three are triggered asynchronously after upload completes and are non-blocking — upload succeeds even if processing fails.

### 1.2 Preconditions

- Document entity exists with at least one version.
- File content accessible via StorageBackend.
- Processing libraries available (image, PDF, video, Office parsing).

---

## 2. Context

### 2.1 Relevant Fields

| Field | Role in This Action |
|---|---|
| extracted_author | Author from file metadata (PDF, Office). Output of metadata extraction. |
| extracted_title | Title from file metadata. Output of metadata extraction. |
| page_count | Pages from PDFs, Office docs. Output of metadata extraction. |
| width_px, height_px | Dimensions for images, videos. Output of metadata extraction. |
| duration_seconds | Duration for audio, video. Output of metadata extraction. |
| content_text | Extracted plain text for FTS. Output of text extraction. |
| search_vector | Generated tsvector column. Auto-computed from name + description + content_text. |
| has_thumbnail | Whether thumbnail exists. Set by thumbnail generation. |
| metadata_json (on version) | Extended metadata not in dedicated fields. |

### 2.2 Cross-Entity Context

- **Upload & Storage Sub-PRD:** Upload completion triggers all three processing behaviors.
- **Communication Published Summary Sub-PRD:** Communication content_clean feeds AI summarization; Document content_text feeds FTS. Similar pipeline concept, different outputs.

---

## 3. Key Processes

### KP-1: Metadata Extraction

**Trigger:** Upload complete or new version created.

**Step 1 — Format detection:** Identify file type from MIME type and extension.

**Step 2 — Extract:** Read embedded metadata using format-specific parser.

**Step 3 — Populate fields:** Set dedicated fields on Document record and version row. Store extended metadata in version's metadata_json.

**Step 4 — Event:** Emit `metadata_extracted` event with extracted fields.

### KP-2: Text Extraction & FTS Indexing

**Trigger:** Upload complete or new version created.

**Step 1 — Format detection:** Identify if file type supports text extraction.

**Step 2 — Extract text:** Read embedded text content from file.

**Step 3 — Truncate:** If extracted text exceeds size limit (default: 1MB), truncate.

**Step 4 — Store:** Set content_text on Document record. The search_vector generated column auto-updates.

**Step 5 — Event:** Emit `text_extracted` event with text_length_chars.

### KP-3: Thumbnail Generation

**Trigger:** Upload complete or new version created, for supported file types.

**Step 1 — Check support:** Determine if file type supports thumbnail generation.

**Step 2 — Generate:** Create preview image using format-specific method.

**Step 3 — Store:** Create thumbnail as Document entity in system _thumbnails folder with thumbnail_for_id pointing to source document. source = 'system'.

**Step 4 — Update source:** Set has_thumbnail = true on source document.

**Step 5 — Event:** Emit `thumbnail_generated` event with thumbnail_id.

### KP-4: Full-Text Search Query

**Trigger:** User searches documents.

**Step 1 — Parse query:** Convert user search text to tsquery using plainto_tsquery.

**Step 2 — Execute:** Query documents table using search_vector @@ query with visibility filtering.

**Step 3 — Rank:** Order by ts_rank with three-tier weighting (name A > description B > content C).

**Step 4 — Snippets:** Generate ts_headline with <mark> highlighting for content matches.

**Step 5 — Return:** Ranked results with snippets, metadata, and entity links.

---

## 4. Metadata Extraction

**Supports processes:** KP-1

### 4.1 Supported Formats

| File Type | Extracted Fields | Method |
|---|---|---|
| PDF | extracted_author, extracted_title, page_count | PDF metadata dictionary |
| Word (.docx) | extracted_author, extracted_title, page_count | Office Open XML core properties |
| Excel (.xlsx) | extracted_author, extracted_title | Office Open XML core properties |
| PowerPoint (.pptx) | extracted_author, extracted_title, page_count (slides) | Office Open XML core properties |
| Images (JPEG, PNG, TIFF) | width_px, height_px, EXIF data | Image header + EXIF extraction |
| Video (MP4, MOV, WebM) | width_px, height_px, duration_seconds | Container metadata |
| Audio (MP3, WAV, FLAC) | duration_seconds, artist/title | ID3 / container metadata |
| Plain text (.txt, .csv, .md) | — | No metadata (content goes to text extraction) |

### 4.2 Extended Metadata

Metadata not mapping to a dedicated field (EXIF camera model, GPS, Office keywords, custom properties) is stored in version's `metadata_json` JSONB column. Enables future field promotion.

### 4.3 Extraction Failure

If extraction fails (unsupported format, corrupted metadata), the document is created successfully with metadata fields NULL. Failure event logged for diagnostics.

**Tasks:**

- [ ] DCPP-01: Implement PDF metadata extraction (author, title, page_count)
- [ ] DCPP-02: Implement Office document metadata extraction (docx, xlsx, pptx)
- [ ] DCPP-03: Implement image metadata extraction (dimensions, EXIF)
- [ ] DCPP-04: Implement video metadata extraction (dimensions, duration)
- [ ] DCPP-05: Implement audio metadata extraction (duration, ID3 tags)
- [ ] DCPP-06: Implement extended metadata storage in metadata_json
- [ ] DCPP-07: Implement extraction failure handling (graceful degradation)

**Tests:**

- [ ] DCPP-T01: Test PDF metadata populates author, title, page_count
- [ ] DCPP-T02: Test DOCX metadata populates author, title, page_count
- [ ] DCPP-T03: Test JPEG metadata populates dimensions and EXIF in metadata_json
- [ ] DCPP-T04: Test video metadata populates dimensions and duration
- [ ] DCPP-T05: Test extraction failure leaves document intact with NULL fields
- [ ] DCPP-T06: Test metadata_extracted event emitted

---

## 5. Text Extraction & Full-Text Search

**Supports processes:** KP-2, KP-4

### 5.1 Text Extraction Formats

| File Type | Extraction Method |
|---|---|
| PDF | Text layer extraction (no OCR) |
| Word (.docx) | XML text content extraction |
| Excel (.xlsx) | Cell value text extraction |
| PowerPoint (.pptx) | Slide text content extraction |
| Plain text (.txt, .md, .csv) | Direct content |
| HTML (.html) | Tag-stripped text content |
| Code files (.py, .js, .ts, etc.) | Direct content |

### 5.2 Content Text Size Limit

Extracted content_text truncated to configurable limit (default: 1MB) to prevent search_vector from becoming excessively large. Truncation applied at extraction time.

### 5.3 PostgreSQL tsvector Configuration

Three-tier weighted search via stored generated column:

- **Weight A** (name): Document name matches rank highest
- **Weight B** (description): Description matches rank second
- **Weight C** (content_text): Extracted file text matches rank third
- English dictionary: stemming, stop words, normalization
- GIN index for fast queries

### 5.4 Search Features

| Feature | Implementation |
|---|---|
| Stemming | English dictionary: "contract" matches "contracts" |
| Ranking | ts_rank with three-tier weight differentiation |
| Snippets | ts_headline with <mark> highlighting |
| Visibility filtering | Private excluded unless created_by = current_user |
| Category filtering | Optional scope (e.g., only PDFs) |
| Tenant isolation | Implicit via search_path |

**Tasks:**

- [ ] DCPP-08: Implement PDF text extraction (text layer)
- [ ] DCPP-09: Implement Office document text extraction (docx, xlsx, pptx)
- [ ] DCPP-10: Implement plain text / code file extraction
- [ ] DCPP-11: Implement HTML tag stripping for text extraction
- [ ] DCPP-12: Implement content_text size limit truncation
- [ ] DCPP-13: Implement FTS search query with ranking and snippets
- [ ] DCPP-14: Implement FTS visibility filtering

**Tests:**

- [ ] DCPP-T07: Test PDF text extraction populates content_text
- [ ] DCPP-T08: Test DOCX text extraction populates content_text
- [ ] DCPP-T09: Test search_vector auto-updates when content_text changes
- [ ] DCPP-T10: Test FTS query returns ranked results
- [ ] DCPP-T11: Test FTS snippets highlight matching terms
- [ ] DCPP-T12: Test FTS respects visibility (private documents excluded)
- [ ] DCPP-T13: Test content_text truncated at size limit
- [ ] DCPP-T14: Test text_extracted event emitted

---

## 6. Thumbnail Generation

**Supports processes:** KP-3

### 6.1 Supported Types

| Source Type | Method | Output |
|---|---|---|
| Images (JPEG, PNG, GIF, WebP) | Resize to fit max dimensions, preserve aspect ratio | JPEG or WebP |
| PDF | Render first page to image | PNG |
| Video (MP4, MOV, WebM) | Extract frame at 1s mark (or first keyframe) | JPEG |
| Office documents | Deferred (requires LibreOffice headless) | — |

### 6.2 Thumbnail Storage

Thumbnails stored as Document entities in system `_thumbnails` folder:

- source = 'system', is_folder = false
- thumbnail_for_id FK references source document
- When source gets new version, existing thumbnail replaced (new version of thumbnail entity)

### 6.3 Thumbnail Serving

- No visibility check beyond tenant isolation (inherits source visibility)
- Aggressive caching: Cache-Control: public, max-age=86400
- Served as generated format regardless of source format

### 6.4 Configuration

| Setting | Default |
|---|---|
| Max thumbnail width | 400px |
| Max thumbnail height | 400px |
| Output format | WebP |
| Quality | 80% |

**Tasks:**

- [ ] DCPP-15: Implement image thumbnail generation (resize with aspect ratio)
- [ ] DCPP-16: Implement PDF thumbnail generation (first page render)
- [ ] DCPP-17: Implement video thumbnail generation (frame extraction)
- [ ] DCPP-18: Implement thumbnail storage as Document entity in _thumbnails folder
- [ ] DCPP-19: Implement thumbnail serving with caching headers
- [ ] DCPP-20: Implement thumbnail replacement on new version

**Tests:**

- [ ] DCPP-T15: Test image thumbnail generated at correct dimensions
- [ ] DCPP-T16: Test PDF thumbnail renders first page
- [ ] DCPP-T17: Test video thumbnail extracts frame
- [ ] DCPP-T18: Test thumbnail stored as system Document with thumbnail_for_id
- [ ] DCPP-T19: Test thumbnail replaced when source gets new version
- [ ] DCPP-T20: Test thumbnail_generated event emitted
- [ ] DCPP-T21: Test has_thumbnail set to true on source document
