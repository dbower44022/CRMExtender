# Note — Content, Revisions & Sanitization Sub-PRD

**Version:** 1.0
**Last Updated:** 2026-02-23
**Status:** Draft
**Entity Base PRD:** [note-entity-base-prd.md]

---

## 1. Overview

### 1.1 Purpose

This sub-PRD defines the content architecture for notes: the behavior-managed content model (JSON + HTML + plain text triple), the editor requirements and mention node contract, the append-only revision history, the coexistence of content events and metadata events, and HTML sanitization. Content is the core of what makes Notes different from other entities — it's deeply nested, variable-length, and managed through a dedicated behavior pipeline rather than the standard field update path.

### 1.2 Preconditions

- Note entity operational with notes table and note_revisions table.
- Rich text editor available in Flutter frontend.
- HTML sanitization library available on backend.

---

## 2. Context

### 2.1 Relevant Fields

| Field | Role in This Action |
|---|---|
| content_json | Editor-native JSONB. Source of truth for re-editing. Behavior-managed. |
| content_html | Pre-rendered sanitized HTML. For display contexts without editor. Behavior-managed. |
| content_text | Plain text extracted from HTML. For FTS and previews. Behavior-managed. |
| current_revision_id | Points to latest revision. Updated on content save. |
| revision_count | Incremented on content save. |

### 2.2 Cross-Entity Context

- **Attachments & Mentions Sub-PRD:** Mention nodes in content_json are extracted on save. File attachment URLs appear in content_html.
- **Document Content Processing Sub-PRD:** Similar content extraction pipeline concept (metadata + text + search), but Documents extract from binary files while Notes extract from user-authored rich text.

---

## 3. Key Processes

### KP-1: Content Save (New Revision)

**Trigger:** User saves note with content changes.

**Step 1 — Receive content:** Client sends content_json (editor-native) and content_html (rendered).

**Step 2 — Sanitize HTML:** Run content_html through server-side sanitizer with allowlists.

**Step 3 — Extract plain text:** Strip all HTML tags from sanitized content_html to produce content_text.

**Step 4 — Create revision:** Insert note_revisions row with revision_number incremented, full content_json and content_html snapshots.

**Step 5 — Update note:** Set content_json, content_html, content_text, current_revision_id, revision_count on the note record.

**Step 6 — Emit event:** content_revised event with revision reference (not full content).

**Step 7 — Trigger behaviors:** FTS search_vector auto-updates (stored generated column). Mention extraction triggered.

### KP-2: Metadata-Only Update

**Trigger:** User changes title, visibility, or custom fields without modifying content.

**Step 1 — Update fields:** Standard field update on note record.

**Step 2 — Emit event:** field_updated event via standard event sourcing.

**Step 3 — No revision:** No new note_revisions row created. revision_count unchanged.

### KP-3: View Revision

**Trigger:** User selects a historical revision to view.

**Step 1 — Fetch revision:** Load specific note_revisions row by revision_id.

**Step 2 — Display:** Render content_html from that revision (read-only). Show revision metadata (number, revised_by, timestamp).

---

## 4. Content Architecture

**Supports processes:** KP-1, KP-2

### 4.1 Content Storage Contract

The content model is editor-agnostic. Three representations of the same content:

| Column | Type | Purpose |
|---|---|---|
| content_json | JSONB | Editor-native document. Source of truth for re-editing. Backend treats as opaque blob. |
| content_html | TEXT | Pre-rendered HTML. For display without editor (notifications, API, exports). Sanitized before storage. |
| content_text | TEXT | Plain text (all tags stripped). For FTS indexing and list previews. |

On save: client sends content_json + content_html. Server extracts content_text from content_html.

### 4.2 Why Behavior-Managed (Not Field Registry)

Content columns are NOT in the field registry because:
- Rich text doesn't map to typed field values (can't use equals/contains/greater_than operators).
- Revision model (full-snapshot append-only) is incompatible with field-level delta tracking.
- FTS with ranking and snippets provides better discovery than field filters.

### 4.3 Editor Requirements

**Required formatting:**
- Inline: bold, italic, strikethrough, code, underline
- Block: paragraphs, headings (H1–H3), bullet lists, ordered lists, blockquotes, code blocks, horizontal rules
- Tables: basic creation and editing
- Links: URL with display text
- Images: inline display with URL source

**Required interactions:**
- Image paste/drop: intercept clipboard/drag, upload to attachment endpoint, insert URL
- @Mention autocomplete: trigger on `@`, search users and entities, insert mention node
- Content sync: on every edit, update content_json and content_html in form state

**Required output:**
- Export content_json in editor's native format (JSONB-serializable)
- Export content_html as sanitizable HTML
- Re-hydrate editor from content_json for editing existing notes

**Graceful degradation:** If editor fails to load, fall back to plain textarea.

### 4.4 Mention Node Contract

Regardless of editor choice, @mention nodes in content_json must include:

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

- `mentionType`: object type slug or `"user"` for workspace users.
- `id`: prefixed ULID (authoritative reference).
- `label`: display name at mention time (may become stale — acceptable).

**Tasks:**

- [ ] NCRS-01: Implement content storage contract (receive JSON + HTML, extract text)
- [ ] NCRS-02: Implement content_text extraction from content_html (HTML-to-text)
- [ ] NCRS-03: Implement editor content_json re-hydration for editing
- [ ] NCRS-04: Implement mention node contract validation on save
- [ ] NCRS-05: Implement graceful editor fallback to plain textarea

**Tests:**

- [ ] NCRS-T01: Test content_json and content_html stored correctly on save
- [ ] NCRS-T02: Test content_text extracted with all HTML tags stripped
- [ ] NCRS-T03: Test editor re-hydration produces editable document
- [ ] NCRS-T04: Test mention nodes in content_json conform to contract

---

## 5. Revision History

**Supports processes:** KP-1, KP-3

### 5.1 Revision Model

Revisions are append-only, numbered, and store full content snapshots (not diffs):

| Action | Behavior |
|---|---|
| Create note | Revision 1 created. current_revision_id and revision_count set. |
| Update content | New revision (number incremented). Note content fields updated. |
| Update metadata only | No new revision. Event sourcing only. |
| View old revision | Specific revision's content_html returned (read-only). |
| Delete note | All revisions CASCADE delete. |

### 5.2 Why Full Snapshots

- Each version independently renderable without reconstructing from delta chain.
- Simpler implementation with no risk of corruption.
- Storage cost acceptable for text content (not binary files).
- Diff display can be layered on as a client-side view concern.

### 5.3 Content Events vs. Metadata Events

| Change Type | Event Sourcing | Revision |
|---|---|---|
| Title changed | field_updated (title, old, new) | No |
| Visibility changed | visibility_changed | No |
| Content edited | content_revised (points to revision) | Yes (new revision) |
| Entity linked | entity_linked | No |
| Pin toggled | pin_toggled | No |

The content_revised event contains revision_id and metadata (content_length, word_count) but NOT the full content, keeping the event table lightweight.

**Tasks:**

- [ ] NCRS-06: Implement revision creation on content save
- [ ] NCRS-07: Implement revision numbering with UNIQUE constraint
- [ ] NCRS-08: Implement current_revision_id and revision_count update
- [ ] NCRS-09: Implement metadata-only update without revision
- [ ] NCRS-10: Implement content_revised event emission (reference, not inline)
- [ ] NCRS-11: Implement revision retrieval by ID for historical viewing

**Tests:**

- [ ] NCRS-T05: Test first save creates revision 1
- [ ] NCRS-T06: Test content change creates new revision with incremented number
- [ ] NCRS-T07: Test title-only change does NOT create revision
- [ ] NCRS-T08: Test content_revised event contains revision reference
- [ ] NCRS-T09: Test historical revision returns correct content_html
- [ ] NCRS-T10: Test revision_count reflects actual revision count
- [ ] NCRS-T11: Test CASCADE delete removes all revisions

---

## 6. Content Sanitization

**Supports processes:** KP-1

### 6.1 Requirements

All content_html sanitized on save before storage to prevent XSS.

### 6.2 Sanitization Library

Server-side HTML sanitizer (e.g., `bleach`, `nh3`, or equivalent). Applied before storage, not on display.

### 6.3 Allowlists

**Allowed tags:** `p`, `br`, `strong`, `em`, `u`, `s`, `code`, `pre`, `blockquote`, `h1`–`h6`, `ul`, `ol`, `li`, `a`, `img`, `table`, `thead`, `tbody`, `tr`, `th`, `td`, `span`, `div`, `hr`, `sub`, `sup`, `mark`

**Allowed attributes:** `href`, `target`, `rel` on `a`; `src`, `alt`, `title`, `width`, `height` on `img`; `class`, `data-*` on `span` (for mention rendering); `colspan`, `rowspan` on `td`/`th`

**Stripped:** All other tags (`script`, `iframe`, `style`, `form`, `object`, `embed`). All event handler attributes (`onclick`, `onerror`, etc.).

**Tasks:**

- [ ] NCRS-12: Implement server-side HTML sanitization with allowlists
- [ ] NCRS-13: Implement dangerous tag stripping (script, iframe, etc.)
- [ ] NCRS-14: Implement event handler attribute stripping

**Tests:**

- [ ] NCRS-T12: Test allowed tags preserved in sanitized output
- [ ] NCRS-T13: Test script tags stripped
- [ ] NCRS-T14: Test onclick attributes stripped
- [ ] NCRS-T15: Test iframe tags stripped
- [ ] NCRS-T16: Test mention span with data-* attributes preserved
