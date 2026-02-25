# Communication View — TDD

**Version:** 2.0
**Last Updated:** 2026-02-24
**Status:** As-Built
**Scope:** Feature Implementation
**Parent Document:** [communication-view-prd.md]
**Product TDD:** [product-tdd.md]

---

## 1. Overview

This document captures the technical decisions made during implementation of the Communication Preview Card (PRD Section 4), the Communication Full View (PRD Sections 5–13), and the underlying schema migration that supports HTML email rendering. The implementation spans Phase 32 (Preview Card with plain text), Phase 32b (schema migration + HTML rendering), and Phase 33 (Full View modal with CRM context cards).

Phase 32 delivered a working preview card using the existing `content` column (quote-stripped plain text). Testing with real production email data revealed that plain text does not preserve the original email experience — formatting, structure, and visual hierarchy are lost. Phase 32b restructured the communications schema to separate raw content from display content and added HTML rendering in the preview card. Phase 33 delivered the Full View — a modal overlay with enriched participant data, conversation assignment, provider account info, and all 8 CRM context cards.

This is a living document. Decisions are recorded as they are made.

---

## 2. Communications Schema Migration (v17 → v18)

### 2.1 Column Rename: Clarifying Content Responsibilities

**Decision:** Rename two existing columns to reflect their actual role, and add two new columns for display and search purposes.

| Old Column | New Column | Purpose |
|---|---|---|
| `content` | `original_text` | Plain text body as received from provider, noise included |
| `body_html` | `original_html` | HTML body as received from provider, noise included |
| *(new)* | `cleaned_html` | HTML with noise removed, formatting preserved — **what users see** |
| *(new)* | `search_text` | Plain text with noise removed — what AI and search consume |

**Rationale:** The old schema conflated raw and cleaned content in a single column (`content` was actually the quote-stripped plain text, used for both display and search). The new schema separates four distinct responsibilities: raw text preservation, raw HTML preservation, display-ready HTML, and search-ready text. This separation enables the cleaning pipeline to improve independently of display logic.

**Alternatives Rejected:**

- Keep `content`/`body_html` names and just add `cleaned_html`/`search_text` — Leaves ambiguous names in the schema that future developers would misunderstand. The rename cost is paid once; the clarity benefit is permanent.
- Add a single `display_content` column with a format discriminator — Forces the frontend to handle both HTML and plain text from one field. Separate columns let the API return the right format for each context.

### 2.2 Migration Strategy

**Decision:** Use `ALTER TABLE RENAME COLUMN` (SQLite 3.25+) with `PRAGMA legacy_alter_table = ON` to prevent FK auto-rewrite. New columns added via `ALTER TABLE ADD COLUMN`. Initial population: `cleaned_html = original_html`, `search_text = original_text`.

**Rationale:** Direct column rename is simpler and safer than a full table rebuild. The `legacy_alter_table` pragma is required per the project's established SQLite pitfall documentation — without it, SQLite 3.26+ silently rewrites foreign key references in other tables during rename operations, which has caused production data corruption in this project's history.

**Constraints/Tradeoffs:** The initial population (`cleaned_html = original_html`) means the "cleaned" HTML initially contains all the noise (tracking pixels, boilerplate, quoted replies). A future cleaning pipeline will process these properly. This is acceptable because the raw HTML still renders as a readable email — the noise is visual clutter, not broken content.

### 2.3 Migration Script: `poc/migrate_to_v18.py`

**Decision:** Follow the established migration script pattern (same as `migrate_to_v17.py`): backup first, `--dry-run` support, idempotent step checks, `PRAGMA foreign_keys=OFF` during migration.

**Implementation Details:**

- Each step checks column existence before acting (idempotent re-runs)
- Backup created with timestamped suffix (`.v17-backup-YYYYMMDD_HHMMSS.db`)
- `--dry-run` applies changes to the backup copy, not the production database
- Schema version bumped to 18 via `PRAGMA user_version = 18`

---

## 3. API Backward Compatibility

### 3.1 Pre-Migration Fallback

**Decision:** The communication preview API endpoint uses fallback reads: `comm.get("cleaned_html") or comm.get("body_html")` and `comm.get("search_text") or comm.get("content")`.

**Rationale:** The server code ships before the migration runs on production. SQLite's `SELECT *` returns column names as they exist in the current schema. Before migration, the old column names (`content`, `body_html`) are present; after migration, the new names (`original_text`, `original_html`, `cleaned_html`, `search_text`) are present. The `or` fallback ensures the API works in both states.

**Constraints/Tradeoffs:** This is a transitional pattern. After migration has been run on all environments, the fallback to old column names is dead code. It can be removed in a future cleanup pass but causes no harm if left.

### 3.2 ParsedEmail Model Backward Compatibility

**Decision:** `ParsedEmail.from_row()` reads new column names first with fallback to old names: `r.get("original_text") or r.get("content")` and `r.get("original_html") or r.get("body_html")`.

**Rationale:** Same transitional concern as the API — `from_row()` may be called with rows from either schema version during the migration window. The fallback chain ensures correct behavior regardless of which schema the database is running.

---

## 4. HTML Email Rendering

### 4.1 Rendering Approach: Direct DOM Injection (Not iframe)

**Decision:** Email HTML is sanitized client-side and rendered via React's `dangerouslySetInnerHTML` in a scrollable `<div>`. No iframe is used.

**Rationale:** This decision was reached through iterative testing of three approaches, each of which failed in production:

**Approach 1 — `sandbox=""` iframe (strictest):** The initial implementation used `<iframe srcdoc={html} sandbox="">` which creates a fully isolated origin. This blocked all scripts and forms (good) but also forced every external resource request through individual CORS checks against a `null` origin. Marketing emails with 50+ tracking pixels, external stylesheets, and web fonts each generated a separate CORS error. The sandbox overhead caused 30+ second render times for emails over 150KB (the largest production email is 366KB). Chrome renders the same HTML instantly in a normal page context because there is no per-resource CORS isolation.

**Approach 2 — `sandbox="allow-same-origin"` iframe:** Relaxing the sandbox to share the parent origin eliminated CORS failures but did not fix the speed problem. The iframe still had to construct a separate document context, and inline `<script>` tags in the email HTML generated console errors (`Blocked script execution in 'about:srcdoc'` for every script tag) because `allow-scripts` was deliberately not granted.

**Approach 3 — `sandbox="allow-same-origin allow-scripts"` was not attempted:** Allowing script execution inside untrusted email HTML is a security violation. Email HTML routinely contains tracking scripts, analytics beacons, and event handlers that should never execute in the CRM context.

**Final approach — Direct DOM injection:** Stripping dangerous elements client-side (`<script>` tags, `on*` event handlers, `javascript:` URLs, `@font-face` blocks) and injecting the sanitized HTML directly into the React DOM via `dangerouslySetInnerHTML`. This renders at native DOM speed (identical to Chrome opening the email directly) with no iframe overhead, no CORS isolation, and no console errors.

**Alternatives Rejected:**

- Server-side HTML sanitization — Adds latency to the API response, requires a Python HTML sanitization library, and still requires the client to trust the server's sanitization. Client-side sanitization is sufficient because the content is rendered in a read-only context with no form submission or navigation.
- DOMPurify library — A purpose-built sanitization library would be more thorough but adds a dependency for a problem solved by four regex replacements. The email HTML is already stored server-side (not user-editable in real-time), and the preview card is non-interactive (no forms, no navigation targets). The attack surface is minimal.

**Constraints/Tradeoffs:** Regex-based sanitization is not a complete security boundary. A determined attacker could craft HTML that bypasses the regex patterns (e.g., using HTML entities to encode `on` in event handlers). This is acceptable because: (1) the email content originates from the user's own Gmail account via authenticated sync, not from untrusted public input; (2) the preview card is non-interactive — there are no cookies, tokens, or forms to steal; (3) the `@font-face` stripping eliminates the CORS console noise that motivated the iframe approach in the first place.

### 4.2 Sanitization Rules

**Decision:** Eleven client-side regex sanitization passes before DOM injection. The sanitizer is a shared module at `frontend/src/lib/sanitizeHtml.ts`, imported by both the Preview Card and the Full View Content Card.

| # | Rule | Regex | Purpose |
|---|---|---|---|
| 1 | Strip `<script>` tags | `/<script\b[^]*?<\/script\s*>/gi` | Prevents JavaScript execution |
| 2 | Strip event handlers | `/\s+on\w+\s*=\s*(?:"[^"]*"\|'[^']*'\|[^\s>]*)/gi` | Removes onclick, onerror, onload, etc. |
| 3 | Neutralize javascript: URLs (double-quoted) | `/href\s*=\s*"javascript:[^"]*"/gi` → `href="#"` | Prevents navigation to javascript: protocol |
| 4 | Neutralize javascript: URLs (single-quoted) | `/href\s*=\s*'javascript:[^']*'/gi` → `href='#'` | Same as above, single-quote variant |
| 5 | Strip @font-face blocks | `/@font-face\s*\{[^}]*\}/gi` | Prevents CORS errors from external font loads |
| 6 | Strip `<base>` tags | `/<base\b[^>]*\/?>/gi` | Prevents email base-href from hijacking page URL resolution |
| 7 | Strip `<meta>` tags | `/<meta\b[^>]*\/?>/gi` | Prevents email charset/Content-Type meta from conflicting with page |
| 8 | Strip `<link>` tags | `/<link\b[^>]*\/?>/gi` | Prevents preload/stylesheet CORS errors |
| 9 | Strip cid: URL references | `/\s(?:src\|href)\s*=\s*["']cid:[^"']*["']/gi` | Removes Content-ID scheme (email-client-only, causes ERR_UNKNOWN_URL_SCHEME) |
| 10 | Strip tracking pixels | `/<img\b[^>]*\b(?:width\|height)\s*=\s*["']?1(?:px)?["']?[^>]*\/?>/gi` + hidden-image variant | Removes 1x1 and display:none/visibility:hidden images |
| 11 | Strip known tracking URLs | Pattern matching `/open`, `/track`, `/pixel`, `/beacon`, `.gif?`, spacer/blank/clear/transparent GIF filenames | Removes tracking beacons by URL pattern |

**Rationale:** These rules address the specific threats and noise observed in production email HTML. The rule set grew iteratively as production testing revealed new issues:

- **Rules 1–5** (Phase 32b): Core security (scripts, event handlers, javascript: URLs) and CORS noise (@font-face). These were the original sanitization rules.
- **Rules 7–11** (Phase 32b, incremental): Added after production testing revealed `<meta>` tags conflicting with page-level charset parsing, `<link>` tags causing preload warnings, `cid:` scheme URLs generating ERR_UNKNOWN_URL_SCHEME errors, and tracking pixel images triggering ERR_BLOCKED_BY_CLIENT from ad blockers. Known tracking URL patterns (SendGrid, GoDaddy, Facebook, etc.) were stripped by filename/path heuristics.
- **Rule 6** (Phase 33): Added after discovering that a forwarded email from gradebeam.com contained `<base href="http://www.gradebeam.com/">`. When rendered via `dangerouslySetInnerHTML`, the `<base>` tag injected into the page DOM hijacked the browser's URL resolution for **all** relative paths — causing API fetches (`/api/v1/...`) to resolve against the email's base URL instead of the app's origin. This broke all API calls after viewing that email. The `<base>` tag is the most critical sanitization rule because its effect is not confined to the email's rendering area — it corrupts the entire page's URL resolution.

### 4.3 CSS Injection Strategy

**Decision:** No CSS is injected into the email HTML. The email's own styles render unmodified.

**Rationale:** The initial implementation injected base styles (font-family, font-size, table border-collapse, cell padding, link color, blockquote styling). This caused visual artifacts — specifically, horizontal lines through table-based email layouts caused by `table { border-collapse: collapse }` and `td, th { padding: 4px 8px }` conflicting with the email's inline table styles. HTML emails carry their own complete styling (almost entirely via inline styles and embedded `<style>` blocks). Injecting additional CSS rules fights the email's layout rather than enhancing it.

**Alternatives Rejected:**

- Inject styles with lower specificity (e.g., `:where(body)`) — Still risks conflicts with email styles that use `!important`. The safest approach is no injection.
- Inject styles only for elements without inline styles — Complex to implement correctly, marginal benefit.

### 4.4 @font-face Stripping: Evolution of Approach

**Decision:** Strip `@font-face` blocks via regex before DOM injection. This was the third approach attempted.

**Evolution:**

1. **Content-Security-Policy `font-src 'none'`** — A `<meta http-equiv="Content-Security-Policy" content="font-src 'none'">` tag was added inside the iframe's `<head>`. This successfully blocked font loading but CSP violations still generate console errors (`Refused to load the font '<URL>' because it violates the following Content Security Policy directive: "font-src 'none'"`). One marketing email generated 11 CSP violation messages.

2. **CSP removed, regex added** — Stripping `@font-face` blocks from the HTML before rendering eliminates the font URLs entirely. The browser never sees them, so no fetch is attempted and no error is logged. Emails render with system fallback fonts, which is visually acceptable since the custom fonts are typically brand fonts for marketing emails.

### 4.5 Channel-Specific Rendering

**Decision:** HTML rendering is used only for email-channel communications. All other channels (SMS, phone, video, note) render `search_text` as plain text with `whitespace-pre-wrap`.

**Rationale:** Only email has meaningful HTML content. SMS is plain text by nature. Phone/video transcripts and manual notes are plain text entered by users or generated by transcription services. Rendering these as HTML would add complexity with no benefit.

**Fallback chain for body display:**

1. Email with `cleaned_html` → HTML rendered via `dangerouslySetInnerHTML` with sanitization
2. Non-email with `search_text` → Plain text with `whitespace-pre-wrap`
3. No text content but `snippet` exists → Snippet rendered as italic plain text
4. No content at all → "No content" placeholder

---

## 5. Frontend Architecture — Preview Card

### 5.1 Component Structure

**Decision:** The `CommunicationPreviewCard` component is a single file at `frontend/src/components/detail/CommunicationPreviewCard.tsx` containing:

- `CommunicationPreviewCard` — Main component with channel-aware rendering
- `HtmlBody` — Sanitizes and renders email HTML (imports `sanitizeHtml` from shared module)
- `formatParticipants` — Truncates participant lists at 3 names
- `formatDuration` — Formats seconds to human-readable duration
- `PreviewSkeleton` — Loading state placeholder

The `sanitizeHtml` function was extracted to a shared module at `frontend/src/lib/sanitizeHtml.ts` during Phase 33 so both the Preview Card and the Full View Content Card could use it.

### 5.2 Data Fetching

**Decision:** `useCommunicationPreview` hook in `frontend/src/api/communicationPreview.ts` using `@tanstack/react-query` with 30s stale time and 5-minute GC time.

**Rationale:** The stale time prevents re-fetching when the user rapidly navigates between rows and returns to a previously viewed communication. The GC time keeps recent previews in memory for the browsing session.

### 5.3 TypeScript Types

**Decision:** `CommunicationPreviewData` interface in `frontend/src/types/api.ts` with `cleaned_html: string | null` and `search_text: string | null` replacing the original `content: string | null`.

---

## 6. Codebase Column Rename Scope

### 6.1 Files Modified for Column Rename

The rename from `content`/`body_html` to `original_text`/`original_html` (plus new `cleaned_html`/`search_text`) touched these files:

| File | Change |
|---|---|
| `poc/database.py` | `CREATE TABLE` column definitions |
| `poc/models.py` | `ParsedEmail.to_row()` dict keys, `from_row()` lookups (with fallbacks) |
| `poc/sync.py` | `INSERT INTO communications` SQL column list and parameter bindings |
| `poc/migrate_strip_boilerplate.py` | `SELECT`/`UPDATE` column names |
| `poc/migrate_refetch_emails.py` | `UPDATE` column name |
| `poc/audit_parser.py` | `SELECT` column names and dict key access |
| `poc/web/routes/api.py` | Preview endpoint response keys (with fallbacks) |
| `tests/test_api.py` | `_seed_communication()` INSERT + assertions |
| `tests/test_access.py` | Communication INSERT column name |
| `tests/test_scoping.py` | Communication INSERT column name |

### 6.2 Files NOT Modified (No DB Column References)

These files use `ParsedEmail` dataclass attribute names (`body_plain`, `body_html`) which are Python object attributes, not database column names. They required no changes:

| File | Why No Change |
|---|---|
| `poc/email_parser.py` | `strip_quotes(body, body_html)` — function parameter names |
| `poc/gmail_client.py` | Sets `body_html=` on `ParsedEmail` constructor |
| `poc/conversation_builder.py` | Reads `em.body_plain`, `em.body_html` — dataclass attrs |
| `poc/triage.py` | Reads `msg.body_plain`, `msg.body_html` — dataclass attrs |
| `poc/summarizer.py` | Reads `em.body_plain` — dataclass attr |
| `poc/views/registry.py` | Communication fields use `comm.snippet`, not `content`/`body_html` |

---

## 7. Test Coverage

### 7.1 API Tests — Communication Preview (12 tests)

All tests in `tests/test_api.py::TestCommunicationPreview`:

| Test | Validates |
|---|---|
| `test_preview_not_found` | 404 for nonexistent communication ID |
| `test_preview_email_basic` | Full email preview with all fields including `cleaned_html` and `search_text` |
| `test_preview_participants_grouped_by_role` | Participants sorted into from/to/cc/bcc buckets |
| `test_preview_no_participants` | Empty participant lists when none exist |
| `test_preview_with_attachments` | Attachment metadata returned correctly |
| `test_preview_no_attachments` | Empty attachment list when none exist |
| `test_preview_triage_result` | Non-null triage_result returned |
| `test_preview_triage_null` | Null triage_result returned as null |
| `test_preview_boolean_fields` | `is_read` and `is_archived` returned as booleans |
| `test_preview_sms_channel` | SMS-specific fields (phone_number_from, cleaned_html) |
| `test_preview_null_content` | Null content falls back to snippet |
| `test_preview_phone_with_duration` | Phone-specific fields (duration, phone numbers) |

### 7.2 API Tests — Communication Full View (15 tests)

All tests in `tests/test_api.py::TestCommunicationFullView`:

| Test | Validates |
|---|---|
| `test_full_not_found` | 404 for nonexistent communication ID |
| `test_full_email_basic` | All core fields returned (channel, direction, timestamp, subject, cleaned_html, search_text, source, etc.) |
| `test_full_participants_enriched` | Participants with contact_name, company_name, title populated via JOIN + correlated subqueries |
| `test_full_participants_unresolved` | Null enrichment fields for participants without CRM contact records |
| `test_full_conversation_assigned` | Conversation object returned with id, title, status, communication_count |
| `test_full_conversation_none` | Null conversation when communication is unassigned |
| `test_full_provider_account` | Provider account object (id, provider, email_address) populated from account_id FK |
| `test_full_ai_summary_present` | Non-null ai_summary returned |
| `test_full_ai_summary_null` | Null ai_summary returned as null |
| `test_full_attachments` | Attachment list with id, filename, mime_type, size_bytes |
| `test_full_original_text` | original_text field returned for View Original feature |
| `test_full_provider_ids` | provider_message_id, provider_thread_id, header_message_id all present |
| `test_full_timestamps` | created_at, updated_at fields returned |
| `test_full_notes_empty` | Notes always returned as empty list (note_entities CHECK constraint excludes 'communication') |
| `test_full_triage_result` | triage_result pass-through |

### 7.3 Full Suite Results

1540 tests total. 1538 pass, 2 pre-existing Google mock failures in `test_scoping.py` (unrelated to this feature).

---

## 8. Production Data Observations

### 8.1 Email HTML Size Distribution

Analysis of the production database (3,409 conversations, ~3,500+ communications):

| Size Range | Count Profile | Example Content |
|---|---|---|
| < 10 KB | Most person-to-person emails | Plain correspondence, short replies |
| 10–50 KB | Business emails with formatting | Newsletters, formatted correspondence |
| 50–150 KB | Marketing emails | Receipts, shipping notifications, promotions |
| 150–366 KB | Heavy marketing HTML | "Automated Actions History" (366 KB), Amazon order emails |

The largest email (366 KB) renders instantly with the direct DOM injection approach. The iframe approach took 30+ seconds for the same email.

---

## 9. Communication Full View (Phase 33)

### 9.1 Architecture: Portal-Based Modal

**Decision:** The Full View renders as a fixed-position overlay via React's `createPortal(…, document.body)`. Escape key and backdrop click close the modal.

**Rationale:** The same pattern used by `RecordModal.tsx` for other entity types. A portal-based modal avoids z-index stacking issues within the nested panel layout (react-resizable-panels → DataGrid → modal). The modal is independent of the grid's scroll and panel hierarchy.

**Alternatives Rejected:**

- Route-based navigation (`/app/communications/{id}`) — Would break the grid context. The user expects to return to their exact scroll position and selection state after closing. A modal preserves this naturally.
- Replacing the detail panel content — The detail panel is too narrow for the full reading experience. The PRD specifies a near-full-screen overlay.

### 9.2 Backend: Enriched Full View Endpoint

**Decision:** New `GET /api/v1/communications/{comm_id}/full` endpoint returning all communication fields plus enriched participant data, conversation assignment, provider account info, and notes.

**Implementation Details:**

- **Enriched participants:** `LEFT JOIN contacts` for contact_name, plus two correlated subqueries into `contact_companies` for company_name and title (where `is_primary = 1 AND is_current = 1`).
- **PRAGMA column detection:** The `is_account_owner` column on `communication_participants` was added post-v17 and does not exist in the production database. The endpoint uses `PRAGMA table_info(communication_participants)` at runtime to detect whether the column exists, and conditionally includes it in the SELECT or substitutes `NULL AS is_account_owner`. This avoids a hard migration dependency.
- **Conversation assignment:** `JOIN conversation_communications → conversations` with a correlated subquery for communication_count.
- **Provider account:** Simple lookup from `provider_accounts` by `comm.account_id`.
- **Notes:** Always returns `[]`. The `note_entities` table's CHECK constraint excludes `'communication'` as an entity_type, so no notes can be attached to communications in the current schema.
- **Content fallbacks:** Same pattern as the preview endpoint — `comm.get("cleaned_html") or comm.get("body_html")` and `comm.get("search_text") or comm.get("content")` for pre/post-migration compatibility.

**Rationale:** A separate `/full` endpoint (rather than expanding the existing `/preview` endpoint) keeps the preview response lightweight for rapid grid browsing. The full endpoint adds 4 extra queries (participants with enrichment, conversation, provider account, notes) that would add unnecessary latency to every preview request.

### 9.3 Responsive Layout: Content-Aware Two-Column

**Decision:** The modal evaluates container width and content word count to determine single-column vs two-column layout:

| Condition | Layout |
|---|---|
| Container width < 900px | Single column |
| Container width ≥ 900px AND word count ≤ 150 | Single column |
| Container width ≥ 900px AND word count > 150 | Two column (62%/38% split) |

**Implementation:** A `ResizeObserver` on the modal container tracks width changes. Word count is computed from `data.search_text` using `text.trim().split(/\s+/).filter(Boolean).length`. Two-column layout uses CSS flexbox (`flex-[62]` / `flex-[38]`) with independent `overflow-y: auto` scrolling on each column. The Identity Card always spans full width above both columns.

**Rationale:** Short emails (< 150 words) render naturally in single-column — the user doesn't need CRM cards pinned beside a brief message. Long emails benefit from side-by-side layout so the user can read content without scrolling past it to reach CRM context.

**Thresholds:** 900px and 150 words were taken from the PRD guidelines and confirmed through visual testing with production emails. The 62/38 split slightly favors content width over CRM cards.

### 9.4 Card Component Architecture

**Decision:** Ten new components in `frontend/src/components/fullview/`:

| Component | Purpose | Suppression Rule |
|---|---|---|
| `CommunicationFullView.tsx` | Modal shell with responsive layout | — |
| `IdentityCard.tsx` | Channel icon, direction, source, provider account, timestamp | Never |
| `ContentCard.tsx` | Channel-aware content rendering (email header/body/attachments, SMS, phone, etc.) | Never |
| `ParticipantsCard.tsx` | All participants with role badges, contact links, title+company, "(You)" badge | Suppressed when 0 participants |
| `SummaryCard.tsx` | AI summary with source badge, disabled edit/regenerate buttons | Suppressed when ai_summary is null |
| `ConversationCard.tsx` | Conversation link or "Not assigned" with disabled Assign button | Never |
| `TriageCard.tsx` | Triage result with disabled Override button | Suppressed when triage_result is null |
| `NotesCard.tsx` | Notes list with disabled "+ Add" button | Suppressed when notes array is empty |
| `MetadataCard.tsx` | Source, provider, IDs, timestamps — collapsed by default | Never |
| `FullViewSkeleton.tsx` | Loading skeleton matching modal layout | — |

**Rationale:** Each CRM card is a separate component matching the PRD's card-based architecture. Cards self-suppress when they have no data, keeping the layout clean. The modal shell orchestrates layout without knowing card internals.

### 9.5 Stubbed Actions

**Decision:** Several PRD-specified actions are rendered as disabled buttons with "Coming soon" tooltips:

| Action | Card | Why Stubbed |
|---|---|---|
| Attachment download | ContentCard | Requires storage layer (provider on-demand fetch or object storage) |
| Edit/Regenerate summary | SummaryCard | Requires Published Summary subsystem |
| Assign conversation | ConversationCard | Requires conversation picker UI and assignment API |
| Override triage | TriageCard | Requires triage override API and AI processing queue |
| Add note | NotesCard | Requires note_entities CHECK constraint change for 'communication' |

**Rationale:** Rendering the buttons as disabled signals to the user that the feature exists conceptually and will be available in the future. Hiding them entirely would give no indication that the workflow is planned.

### 9.6 Opening Mechanisms (Three Triggers)

**Decision:** The Full View opens via three triggers, all converging on the same state (`commFullViewId` in DataGrid):

| Trigger | File | Mechanism |
|---|---|---|
| Double-click on communication row | `DataGrid.tsx` | Fast double-click detection → `setCommFullViewId(id)` |
| Enter key on focused row (non-editable cell) | `useGridKeyboard.ts` | Dispatches `grid:openFullView` custom event |
| Maximize button on detail panel | `DetailPanel.tsx` | Dispatches `grid:openFullView` custom event |

**Implementation:** DataGrid listens for the `grid:openFullView` custom event. When received with `activeEntityType === 'communication'`, it sets `commFullViewId`. For other entity types, it opens `RecordModal` instead. The custom event pattern decouples the triggers from DataGrid's state — the keyboard handler and detail panel don't need a ref to DataGrid.

The Maximize button (Maximize2 icon from lucide-react) is conditionally rendered in `DetailPanel.tsx` only when `activeEntityType === 'communication'`.

### 9.7 Content Card: Channel-Specific Rendering

**Decision:** The Content Card uses channel detection to render four distinct layouts:

| Channel | Header | Body | Extra |
|---|---|---|---|
| `email` | Sender name+email, To/CC/BCC recipient lists with contact links | `cleaned_html` via `dangerouslySetInnerHTML` + `sanitizeHtml` | Attachment list, "View Original" expander |
| `sms` | Participant name + phone, direction | `search_text` as `whitespace-pre-wrap` | — |
| `phone`, `video` (recorded) | "Call with [participants]", direction, duration | `search_text` as `whitespace-pre-wrap` | — |
| `phone_manual`, `video_manual`, `in_person`, `note` | "[Type] with [participants]", direction, duration | `search_text` as `whitespace-pre-wrap` | — |

**Participant linking:** Participant names with a non-null `contact_id` render as buttons that navigate to the contact record (`setActiveEntityType('contact')`, `setSelectedRow(contact_id, -1)`) and close the modal. Unresolved participants render as plain text.

**Fallback chain:** Same as the preview card — `cleaned_html` → `search_text` → `snippet` (italic) → "No content" placeholder.

### 9.8 Participants Card: Enriched Data Display

**Decision:** Each participant renders as a row showing: name (linked if resolved), role badge ("Sender", "To", "CC", "BCC", "Participant"), title + company (from primary affiliation), and "(You)" badge for account owner.

**Enrichment source:** The `/full` endpoint performs the enrichment server-side via SQL JOINs. The frontend receives pre-enriched data — no additional API calls needed per participant.

**Rationale:** Server-side enrichment avoids N+1 API calls (one per participant to resolve contact/company). A single SQL query with LEFT JOIN and correlated subqueries returns all enrichment data in one round trip.

### 9.9 Metadata Card: Collapsed by Default

**Decision:** The Metadata Card renders collapsed by default (header only, with chevron toggle). Expanding reveals source, provider, account, provider IDs, and timestamps in a key-value layout.

**Rationale:** Metadata is diagnostic/power-user information. Keeping it collapsed prevents it from taking space away from more frequently useful cards (participants, summary, conversation).

### 9.10 TypeScript Types (Full View)

**Decision:** Four new interfaces in `frontend/src/types/api.ts`:

- `CommunicationFullParticipant` — extends preview participant with `contact_name`, `company_name`, `title`
- `CommunicationConversation` — `id`, `title`, `status`, `communication_count`
- `CommunicationProviderAccount` — `id`, `provider`, `email_address`
- `CommunicationFullData` — all communication fields plus `participants[]`, `attachments[]`, `conversation`, `provider_account`, `notes[]`

### 9.11 Data Fetching (Full View)

**Decision:** `useCommunicationFull` hook in `frontend/src/api/communicationFull.ts` using `@tanstack/react-query` with 30s stale time and 5-minute GC time. Same caching strategy as the preview hook.

---

## 10. Production Compatibility

### 10.1 Schema Divergence Between Test and Production

**Decision:** The test database uses the latest schema (`cleaned_html`, `search_text`, `original_text`, `original_html`) while the production database is on v17 (`content`, `body_html`). Both API endpoints (preview and full) use `.get()` fallbacks to handle either schema transparently.

**Problem discovered:** The `communication_participants` table in the test DB has an `is_account_owner` column that does not exist in the production DB. A naive `SELECT cp.is_account_owner` would fail with `OperationalError` on production.

**Solution:** Runtime column detection via `PRAGMA table_info(communication_participants)`. If `is_account_owner` is present, select it directly. If not, substitute `NULL AS is_account_owner`. The frontend treats null as `false`.

### 10.2 `<base>` Tag Hijacking (Discovered in Production)

**Decision:** Strip `<base>` tags from email HTML in the sanitizer (Rule 6 in Section 4.2).

**Discovery:** A forwarded email from gradebeam.com contained `<base href="http://www.gradebeam.com/">`. When the CommunicationPreviewCard rendered this email's HTML via `dangerouslySetInnerHTML`, the `<base>` tag was injected into the page DOM. Because `<base>` affects the entire document (not just the containing element), all subsequent `fetch()` calls using relative URLs (`/api/v1/...`) resolved against `http://www.gradebeam.com` instead of `http://localhost:8001`. This caused CORS preflight failures for every API call made after viewing that email — including the Full View's own data fetch.

**Impact:** This was the most severe sanitization issue encountered. Unlike other rules that prevent visual noise or console errors, the `<base>` tag actively **breaks the application's ability to communicate with its own backend**. The effect persists until the user refreshes the page (which discards the injected `<base>` tag from the DOM).

**Fix:** A single regex rule strips all `<base>` tags before DOM injection. This is safe because email HTML has no legitimate reason to set a `<base>` tag — the tag is either an artifact of the original web page the email was forwarded from, or a relative-URL workaround in the email's HTML authoring tool.

---

## Related Documents

| Document | Relationship |
|---|---|
| [Communication View PRD](communication-view-prd.md) | Parent PRD — defines Preview Card and Full View specifications |
| [GUI Preview Card Amendment](gui-preview-card-amendment.md) | System-wide Preview Card type definition |
| [Communication Entity TDD](communication-entity-tdd.md) | Entity-level technical decisions (target schema, not PoC schema) |
| [Communication Entity Base PRD](communication-entity-base-prd.md) | Entity definition and key processes |
