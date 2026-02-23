# Communication — Published Summary Sub-PRD

**Version:** 1.0
**Last Updated:** 2026-02-23
**Status:** Draft
**Entity Base PRD:** [communication-entity-base-prd.md]
**Referenced Entity PRDs:** [conversations-prd.md] (timeline rendering), [notes-prd.md] (shared rich text architecture)

---

## 1. Overview

### 1.1 Purpose

Every Communication produces a Published Summary — the rich text representation of that Communication's contribution to its parent Conversation's timeline. Published Summaries are what users see when viewing a Conversation: ordered summary cards, each representing one Communication, each expandable to the full original content.

The Communication **owns** its Published Summary. The Conversation references summaries — it does not copy or independently store Communication content. This separation means updating a summary automatically updates how it appears in every Conversation, the Conversation-level AI consumes pre-distilled summaries rather than re-processing raw content, and revision history provides an audit trail for decisions.

### 1.2 Preconditions

- Communication record exists with content_clean populated (or user-authored content for manual entries).
- For AI-generated summaries: AI API is accessible.
- Rich text editor is available for user-authored summaries.

---

## 2. Context

### 2.1 Relevant Fields

| Field                       | Role in This Action                                                                |
| --------------------------- | ---------------------------------------------------------------------------------- |
| Content Clean               | Input to AI summary generation. Displayed when user expands to view full original. |
| Summary JSON                | Editor-native rich text document format. Source of truth for re-editing.           |
| Summary HTML                | Pre-rendered HTML rendered in the Conversation timeline.                           |
| Summary Text                | Plain text for FTS indexing and Conversation-level AI input.                       |
| Summary Source              | `ai_generated`, `user_authored`, `pass_through`. Drives UI display (badges).       |
| Current Summary Revision ID | Points to the active revision.                                                     |
| Summary Revision Count      | Tracks how many revisions exist.                                                   |

### 2.2 Relevant Relationships

- **Conversations** — The Conversation timeline assembles an ordered sequence of Communication summary references. Each timeline card is a reference, not a copy.
- **Summary Revisions** — Append-only revision history tracking every summary change.

### 2.3 Cross-Entity Context

- **Notes PRD:** Published Summaries share the same rich text content architecture: JSON (editor-native), HTML (rendered), and plain text (FTS). Same editor, same sanitization, same revision model (append-only, full-snapshot, numbered).
- **Conversations PRD:** The Conversation-level AI summary consumes Communication Published Summaries (summary_text) as input — it is a higher-order synthesis, not a re-analysis of raw content.
- **AI Learning & Classification PRD (future):** Defines the specific AI prompt templates and output formats for summary generation.

---

## 3. Key Processes

### KP-1: AI-Generated Summary for Synced Content

**Trigger:** Communication created via provider sync with content_clean ≥ 50 words (email, recorded call/video transcript).

**Step 1 — Content extraction complete:** Content extraction behavior has produced content_clean from content_raw/content_html.

**Step 2 — AI processing:** AI processes content_clean to produce structured rich text: key points, decisions, requests, and action items.

**Step 3 — Output storage:** AI-produced HTML stored in summary_html. Corresponding summary_json generated for the editor. summary_text extracted (tags stripped). summary_source set to `ai_generated`.

**Step 4 — Revision created:** First revision written to communication_summary_revisions (revision_number = 1). current_summary_revision_id and summary_revision_count updated.

**Step 5 — Event emitted:** `summary_generated` event recorded with revision ID and source in metadata.

### KP-2: Pass-Through Summary for Short Content

**Trigger:** Communication created with content_clean < 50 words (SMS, short emails).

**Step 1 — Pass-through:** content_clean is wrapped in minimal HTML tags and stored across all three summary fields. summary_source set to `pass_through`.

**Step 2 — Revision created:** Same as KP-1 step 4.

### KP-3: User-Authored Summary for Manual Entries

**Trigger:** User creates a manual communication (phone_manual, video_manual, in_person, note).

**Step 1 — User writes content:** User writes the summary using the rich text editor during Communication creation. The user's input IS the summary.

**Step 2 — Storage:** Client sends summary_json and summary_html from the editor. Server extracts summary_text. summary_source set to `user_authored`.

**Step 3 — Revision created:** Same as KP-1 step 4.

### KP-4: User Edits an Existing Summary

**Trigger:** User opens the summary editor on any communication.

**Step 1 — Edit:** User modifies the summary in the rich text editor. Editor loads from summary_json.

**Step 2 — Save:** New revision created (revision_number incremented). Communication summary fields updated. summary_source changes to `user_authored` regardless of previous source.

**Step 3 — Event emitted:** `summary_revised` event recorded with new revision ID.

### KP-5: AI Re-Generation

**Trigger:** User explicitly requests AI to re-generate the summary, or content_clean is updated (e.g., improved parsing logic).

**Step 1 — AI processing:** Same as KP-1 step 2, using current content_clean.

**Step 2 — New revision:** New revision created. Previous revisions (including user edits) are preserved. summary_source set to `ai_generated`.

---

## 4. Content Pipeline

**Supports processes:** KP-1 (step 1), KP-2 (step 1)

### 4.1 Requirements

The Published Summary sits at the end of a three-stage content pipeline:

**Stage 1: content_raw** — Original content as received or entered. Preserved for reference and re-processing. Never displayed directly.

**Stage 2: content_clean** — Channel-specific noise removal (quoted replies, signatures, boilerplate for email; filler words for transcripts; minimal for SMS; none for manual). What users see when expanding to full original. What AI uses as input.

**Stage 3: Published Summary** — Distilled representation for Conversation timeline display. AI-generated (structured rich text), user-authored (rich text from editor), or pass-through (content_clean as-is for short content).

**Tasks:**

- [ ] CSUM-01: Implement three-stage content pipeline coordination
- [ ] CSUM-02: Implement pass-through summary for short content (< 50 words)

**Tests:**

- [ ] CSUM-T01: Test pipeline produces summary from content_clean for long content
- [ ] CSUM-T02: Test pass-through for content under 50 words
- [ ] CSUM-T03: Test pipeline handles empty content_clean gracefully

---

## 5. Summary Generation Rules by Channel

**Supports processes:** KP-1, KP-2, KP-3

### 5.1 Requirements

| Channel                      | Summary Source  | Generation Logic                                                                                 |
| ---------------------------- | --------------- | ------------------------------------------------------------------------------------------------ |
| `email` (< 50 words cleaned) | `pass_through`  | content_clean copied directly to summary fields as rich text.                                    |
| `email` (≥ 50 words cleaned) | `ai_generated`  | AI produces structured rich text: key points, decisions, requests, action items.                 |
| `sms` / `mms`                | `pass_through`  | Message body is inherently short. Copy directly.                                                 |
| `phone_recorded`             | `ai_generated`  | AI processes transcript to produce: key discussion points, decisions, action items, commitments. |
| `phone_manual`               | `user_authored` | User writes summary during creation. User's input IS the summary.                                |
| `video_recorded`             | `ai_generated`  | Same approach as phone_recorded.                                                                 |
| `video_manual`               | `user_authored` | Same as phone_manual.                                                                            |
| `in_person`                  | `user_authored` | Same as phone_manual.                                                                            |
| `note`                       | `user_authored` | Same as phone_manual.                                                                            |

**Tasks:**

- [ ] CSUM-03: Implement channel-based summary source routing
- [ ] CSUM-04: Implement AI summary generation for email (≥ 50 words)
- [ ] CSUM-05: Implement AI summary generation for transcripts (phone_recorded, video_recorded)
- [ ] CSUM-06: Implement user-authored summary flow for manual channels

**Tests:**

- [ ] CSUM-T04: Test each channel routes to correct summary source
- [ ] CSUM-T05: Test 50-word threshold boundary (49 words → pass-through, 50 → AI)
- [ ] CSUM-T06: Test user-authored summary stores all three representations

---

## 6. Rich Text Storage Contract

**Supports processes:** All KPs (storage)

### 6.1 Requirements

The summary storage model mirrors the Notes content architecture (Notes PRD Section 7.2). Three representations:

| Column         | Type  | Purpose                                                                                                                                |
| -------------- | ----- | -------------------------------------------------------------------------------------------------------------------------------------- |
| `summary_json` | JSONB | Editor-native document format. Source of truth for re-editing. Same JSON schema as Notes content_json. Backend treats as opaque JSONB. |
| `summary_html` | TEXT  | Pre-rendered HTML. What the Conversation timeline renders. Sanitized before storage.                                                   |
| `summary_text` | TEXT  | Plain text extracted from summary_html (all tags stripped). FTS indexing and Conversation-level AI input.                              |

**For AI-generated summaries:** AI pipeline produces structured HTML directly. summary_json generated for the editor. summary_text extracted.

**For user-authored summaries:** Client sends summary_json and summary_html from the rich text editor. Server extracts summary_text.

**For pass-through summaries:** content_clean wrapped in minimal HTML tags and stored across all three fields.

**Tasks:**

- [ ] CSUM-07: Implement rich text storage with three-representation model
- [ ] CSUM-08: Implement HTML sanitization for summary content
- [ ] CSUM-09: Implement summary_text extraction from summary_html

**Tests:**

- [ ] CSUM-T07: Test AI-generated summaries populate all three fields
- [ ] CSUM-T08: Test user-authored summaries from editor populate all three fields
- [ ] CSUM-T09: Test pass-through summaries wrap content_clean correctly
- [ ] CSUM-T10: Test HTML sanitization strips dangerous tags

---

## 7. AI Summary Structure

**Supports processes:** KP-1 (step 2)

### 7.1 Requirements

AI summaries produce structured rich text, not flat prose. Output format varies by content but follows general patterns:

**Email summary:** Key points (bulleted list), action items (bulleted list with assignees and deadlines).

**Call/meeting summary:** Key discussion points (bulleted list), decisions made (bulleted list), action items (bulleted list with assignees).

The specific AI prompt templates and output formats are defined in the AI Learning & Classification PRD (future). This section establishes the requirement: AI summaries are structured rich text with headings, lists, and bold emphasis.

**Tasks:**

- [ ] CSUM-10: Implement AI summary prompt for email content
- [ ] CSUM-11: Implement AI summary prompt for transcript content
- [ ] CSUM-12: Implement structured HTML output parsing from AI responses

**Tests:**

- [ ] CSUM-T11: Test AI email summary contains key points and action items
- [ ] CSUM-T12: Test AI transcript summary contains discussion points, decisions, and action items
- [ ] CSUM-T13: Test malformed AI output falls back to pass-through

---

## 8. Revision History

**Supports processes:** KP-4 (step 2), KP-5 (step 2)

### 8.1 Requirements

Every summary change creates a new revision in `communication_summary_revisions`:

- **Append-only:** Revisions are never updated or deleted individually. Only removed via CASCADE when parent Communication is deleted.
- **Numbered:** revision_number starts at 1, increments per Communication.
- **Full snapshots:** Each revision stores complete summary_json, summary_html, and summary_text. No diffs.

**Revision lifecycle:**

| Action                     | Behavior                                                                            |
| -------------------------- | ----------------------------------------------------------------------------------- |
| Initial summary generation | First revision (revision_number = 1). Communication summary fields updated.         |
| User edits AI summary      | New revision. summary_source → `user_authored`. Original AI revision preserved.     |
| AI re-generates            | New revision. summary_source → `ai_generated`. Previous revisions preserved.        |
| View old revision          | Client requests revision by ID. Server returns revision's summary_html for display. |

**Tasks:**

- [ ] CSUM-13: Implement summary revision creation on initial generation
- [ ] CSUM-14: Implement summary revision creation on user edit
- [ ] CSUM-15: Implement summary revision creation on AI re-generation
- [ ] CSUM-16: Implement revision history API (list and view old revisions)

**Tests:**

- [ ] CSUM-T14: Test revision_number increments correctly
- [ ] CSUM-T15: Test user edit creates new revision and updates source to user_authored
- [ ] CSUM-T16: Test AI re-generation preserves previous user-edited revisions
- [ ] CSUM-T17: Test old revision retrieval returns correct snapshot
- [ ] CSUM-T18: Test CASCADE delete removes revisions with parent communication

---

## 9. Summary Generation Triggers

**Supports processes:** KP-1 through KP-5

### 9.1 Requirements

| Trigger                                    | Behavior                                                                                                                            |
| ------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------- |
| Communication created (auto-synced)        | Summary generation fires after content extraction completes. AI or pass-through per channel rules.                                  |
| Communication created (manual entry)       | User writes summary during creation (user-authored channels). Transcript channels fire AI generation after transcript is available. |
| content_clean updated                      | Re-processing of content extraction. Summary re-generated. Previous revisions preserved.                                            |
| User edits summary                         | User modifies via rich text editor. New revision. source → user_authored.                                                           |
| User requests AI re-generation             | Explicit request. New revision. source → ai_generated.                                                                              |
| Communication passes triage after override | If previously filtered, summary generation fires for the first time.                                                                |

### 9.2 Error Handling

| Failure                     | Recovery                                                                                  |
| --------------------------- | ----------------------------------------------------------------------------------------- |
| AI API timeout              | Retry with exponential backoff (3 attempts). "[Summary pending]" placeholder in timeline. |
| AI API rate limit           | Queue and retry after cooldown.                                                           |
| AI returns malformed output | Log raw response. Fall back to pass-through. Flag for review.                             |
| AI API unavailable          | Pass-through mode until API returns. Queue for AI processing when available.              |
| Empty content_clean         | Skip summary generation. "[No content]" in timeline.                                      |

**Tasks:**

- [ ] CSUM-17: Implement summary generation trigger dispatch
- [ ] CSUM-18: Implement "[Summary pending]" placeholder for async generation
- [ ] CSUM-19: Implement AI retry with exponential backoff
- [ ] CSUM-20: Implement pass-through fallback on AI failure
- [ ] CSUM-21: Implement triage-override trigger for first-time summary generation

**Tests:**

- [ ] CSUM-T19: Test trigger fires on communication creation
- [ ] CSUM-T20: Test trigger fires on content_clean update
- [ ] CSUM-T21: Test AI timeout triggers retry and shows placeholder
- [ ] CSUM-T22: Test malformed AI output falls back to pass-through
- [ ] CSUM-T23: Test triage override triggers summary generation
