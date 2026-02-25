# Communication — View Communication Sub-PRD

**Version:** 1.0
**Last Updated:** 2026-02-23
**Status:** Draft
**Entity Base PRD:** [communication-entity-base-prd.md]
**Entity UI PRD:** N/A (this is the first Communication UI specification)
**Referenced Entity PRDs:** [contact-entity-base-prd.md], [conversations-prd.md]
**GUI Documents:** [gui-functional-requirements-prd.md], [gui-preview-card-amendment.md]

---

## 1. Overview

### 1.1 Purpose

This Sub-PRD defines how a Communication record is displayed when a user views it — both the quick Preview (browsing in the Detail Panel) and the full View (opening the record for deep reading). The primary design goal is a **native app reading experience**: email should feel like reading email in Outlook or Gmail, a phone call log should feel like reviewing call notes in a phone app. The CRM intelligence layer (participants, summary, conversation assignment, triage details) is layered around the native content rather than replacing it with a database-record presentation.

This document implements KP-4 (Viewing a Communication's Full Record) from the Entity Base PRD and introduces the Communication-specific rendering for the new Preview Card type defined in the GUI Preview Card Amendment.

### 1.2 Preconditions

- Communication record exists and is accessible to the current user (per Permissions & Sharing PRD).
- Content extraction has completed (cleaned_html is populated, or user-authored content exists for manual entries).
- Participant resolution has run (participant relation instances exist, though some may reference placeholder contacts if resolution is pending).

---

## 2. Context

### 2.1 Relevant Fields

| Field                                      | Role in View                                                                                                                    |
| ------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------- |
| Channel                                    | Determines rendering variant (email, SMS, phone, etc.) and icon display.                                                        |
| Direction                                  | Shown in header area. Drives directional language ("From" / "To" vs. "Participants").                                           |
| Timestamp                                  | Displayed prominently in header. Universal sequencing key.                                                                      |
| Subject                                    | Email subject line or meeting title. Primary heading for email and meeting channels. NULL for SMS, most calls.                  |
| Body Preview                               | First 200 characters of cleaned_html. Used only if cleaned_html is unavailable or for extremely constrained preview contexts. |
| Cleaned HTML                               | HTML content with noise removed but formatting preserved (bold, italic, links, lists). Primary reading content in the Content Card and Preview Card for email. |
| Search Text                                | Plain text with noise removed. No formatting. Used by AI processing and full-text search. Drives word count for layout decisions. |
| Original Text                              | Original unprocessed plain text content. Available via "View Original" expander in full View.                                   |
| Original HTML                              | Original email HTML as received from provider. Not rendered directly to user — used only by content extraction pipeline.        |
| Summary JSON / Summary HTML / Summary Text | Published Summary fields. Rendered in the Summary Card in full View.                                                            |
| Summary Source                             | `ai_generated`, `user_authored`, `pass_through`. Drives badge display on Summary Card.                                          |
| Summary Revision Count                     | Displayed on Summary Card if > 1.                                                                                               |
| Triage Result                              | If non-NULL, the communication was filtered. Drives display of Triage Card.                                                     |
| Triage Reason                              | Human-readable triage explanation. Displayed in Triage Card.                                                                    |
| Duration Seconds                           | Call/meeting duration. Displayed in header for applicable channels.                                                             |
| Has Attachments / Attachment Count         | Drives attachment indicator in Preview and Attachment Card in full View.                                                        |
| Conversation ID                            | FK to parent conversation. Drives Conversation Card in full View.                                                               |
| Provider Account ID                        | Identifies source account. Displayed in Metadata Card.                                                                          |
| Source                                     | `synced`, `manual`, `imported`. Displayed in Metadata Card.                                                                     |

### 2.2 Relevant Relationships

- **Communication Participants** — Relation Type (Communication→Contact) with role, address, display name, is_account_owner metadata. Rendered in the Participants Card and in the Preview Card header.
- **Conversation** — FK reference. Rendered as a navigable link in the Conversation Card.
- **Attachments** — Behavior-managed child records. Rendered in Preview (indicator only) and full View (Attachment Card with download actions).
- **Notes** — Notes attached to this Communication. Rendered in the Notes Card in full View.
- **Summary Revisions** — Append-only revision history. Accessible via revision history action on Summary Card.

### 2.3 Cross-Entity Context

- **GUI Preview Card Amendment:** The Preview Card is a new system-wide Card Type. This document defines the Communication-specific rendering for that card.
- **GUI Functional Requirements PRD:** The Card-Based Architecture (Section 15), Window Types (Section 14), and Display Modes define the containers this view renders into. The content-aware responsive layout logic defined here extends the Card Layout Area behavior for Communication full Views.
- **Conversations PRD:** The Conversation Card displays the parent conversation's title and status, with navigation to open the conversation.
- **Contact Entity Base PRD:** Participant names in the Preview Card and Participants Card link to Contact records.
- **Published Summary Sub-PRD:** Defines summary generation, revision history, and the edit/regenerate actions available on the Summary Card.
- **Triage Sub-PRD:** Defines triage classification and the override workflow triggered from the Triage Card.

---

## 3. Key Processes

### KP-1: Previewing a Communication (Browsing)

**Trigger:** User focuses a communication row in the grid (click, arrow-key navigation). The Docked Window or Undocked Window is in Preview Mode.

**Step 1 — Preview Card renders:** The Preview Card replaces any previous content in the Window. Rendering begins immediately on focus change (target: < 200ms). The card presents a native reading experience appropriate to the communication's channel.

**Step 2 — User scans content:** The user reads the Preview Card to decide whether this communication warrants deeper attention. The card fills all available space — on a large monitor with a wide Detail Panel, a short email may be fully visible without scrolling. On a narrow panel, the card scrolls.

**Step 3 — User decides:** The user either moves to the next row (arrow key, click) causing a new Preview Card to render, or opens the full View (double-click, Enter key, or Maximize button) to see the complete record with CRM context.

### KP-2: Viewing a Communication in Full (Deep Reading)

**Trigger:** User opens a communication in View Mode via double-click on the grid row, Enter key on a focused row, or Maximize button on the Docked Window header. The record opens in a Modal Full Overlay Window, Undocked Window, or the Docked Window transitions to View Mode.

**Step 1 — Layout determined:** The system evaluates the available window width and the communication's content volume to determine single-column or two-column layout (see Section 5).

**Step 2 — Native content renders:** The primary content area presents the communication as a native reading experience — full header (sender, recipients, timestamp, subject), complete cleaned_html body, and attachment list with download actions. This is the Content Card.

**Step 3 — CRM layer renders:** Below the Content Card (single-column) or beside it (two-column), the CRM intelligence cards render: Participants Card, Summary Card, Conversation Card, and conditionally the Triage Card, Notes Card, and Metadata Card. Cards with no data are suppressed entirely.

**Step 4 — User interacts:** The user reads the content, reviews the CRM context, and may take actions: edit the summary (Summary Card), override a triage decision (Triage Card), navigate to the conversation (Conversation Card), navigate to a participant's contact record (Participants Card), or download an attachment (Content Card attachment area).

### KP-3: Viewing a Filtered (Triaged) Communication

**Trigger:** User opens a communication that has a non-NULL triage_result, either from a filtered communications view or from the main grid where triage_result is visible.

**Step 1 — Preview Card renders with triage indicator:** The Preview Card renders normally but includes a visual triage indicator (e.g., a subtle banner or badge) showing the triage classification. This alerts the user that the communication was filtered before they invest time reading.

**Step 2 — Full View includes Triage Card:** If the user opens the full View, the Triage Card renders in the CRM layer showing the triage_result, triage_reason, and an "Override" action button. The Override action queues the communication for AI processing (summary generation, conversation assignment) and clears the triage_result.

---

## 4. Communication Preview Card

**Supports processes:** KP-1 (full flow), KP-3 (step 1)

### 4.1 Rendering Principle

The Communication Preview Card presents the communication as a native reading experience within the scanning/browsing context. It combines what the standard architecture would split into an Identity Card and a Content Card into a single, unified surface. The result should feel like reading a message in a native app's preview pane, not like viewing a CRM record.

### 4.2 Channel-Specific Rendering

Each channel renders its Preview Card differently to match the native reading experience for that communication type.

#### 4.2.1 Email Preview

```
┌─────────────────────────────────────────────┐
│  ✉  Bob Smith                    10:15 AM   │
│     bob.smith@acmecorp.com       Feb 21     │
│                                             │
│  To: **Doug Bower**, Jane Lee +2 Others     │
│  CC: Alice Wong +4 Others                   │
│                                             │
│  Re: Clause 5 revisions                     │
│─────────────────────────────────────────────│
│                                             │
│  Doug, I've reviewed the revised language   │
│  for clause 5 and have a few concerns.      │
│                                             │
│  First, the liability cap at $500K seems    │
│  low given the project scope. I'd suggest   │
│  we revisit...                              │
│                                             │
│  📎 revised_clause5.docx · contract_v3.pdf  │
└─────────────────────────────────────────────┘
```

**Header area:**

The Preview Card header follows the same visual hierarchy and recipient rules as the Content Card header (Section 7.1), adapted for the more compact preview context:

- Channel icon (envelope) and **sender display name** (bold, prominent), right-aligned timestamp
- Sender email address on the second line, smaller and lighter
- Recipient lines follow the same rules as the Content Card: current user’s name **bold and first** in whichever line (To or CC) they appear in, three-name maximum per line, “+X Others” for overflow. Since the Preview Card is non-interactive, the “+X Others” text is not clickable here.
- Timestamp renders as time-only if today, date + time if this year, full date + time if older

**Subject line:**

- Rendered as the most prominent text in the Preview Card — bold heading below the recipient lines, above the content divider
- If NULL (rare for email), the subject line is omitted and the content flows directly below the recipients

**Content area:**

- cleaned_html rendered with formatting preserved, flowing naturally below the subject divider
- Content fills all available space — no artificial truncation. If the email is long and the panel is short, the card scrolls.

**Attachment indicator:**

- If has_attachments is true, a compact attachment line renders at the bottom: paperclip icon followed by filenames (comma-separated). If more than 3 attachments, show first 2 filenames and “+N more”
- Non-interactive in the Preview Card — no download actions. Just awareness that attachments exist.

#### 4.2.2 SMS / MMS Preview

```
┌─────────────────────────────────────────────┐
│  💬  Bob Smith              → Outbound      │
│       Feb 21, 12:45 PM                      │
│                                             │
│  Hey, did you see my questions about        │
│  clause 5?                                  │
└─────────────────────────────────────────────┘
```

**Header area:**

- Channel icon (speech bubble), contact display name, direction indicator (→ Outbound, ← Inbound)
- Timestamp on second line

**Content area:**

- cleaned_html rendered as plain text. SMS messages are short enough that the full content typically fits without scrolling.

**No subject line, no attachment indicator** (unless MMS with media — in which case a media indicator renders similarly to the email attachment indicator).

#### 4.2.3 Phone Call (Recorded) Preview

```
┌─────────────────────────────────────────────┐
│  📞  Bob Smith               ← Inbound     │
│       Feb 21, 3:00 PM · 12 min             │
│                                             │
│  Discussion covered the revised clause 5    │
│  language. Bob confirmed the liability cap  │
│  at $500K is acceptable after consulting    │
│  with legal. Timeline for signing moved...  │
└─────────────────────────────────────────────┘
```

**Header area:**

- Channel icon (phone), contact display name, direction indicator
- Timestamp and duration (formatted as "Xh Ym" or "X min")

**Content area:**

- cleaned_html (the processed transcript) rendered as plain text, filling available space.

#### 4.2.4 Phone Call (Manual) / Video Meeting (Manual) / In-Person Meeting Preview

```
┌─────────────────────────────────────────────┐
│  📞  Bob Smith, Jane Lee     ↔ Meeting      │
│       Feb 21, 1:00 PM · 45 min             │
│                                             │
│  Lease Negotiation Check-in                 │
│─────────────────────────────────────────────│
│                                             │
│  Discussed the outstanding issues on        │
│  clauses 5 and 8. Bob confirmed legal       │
│  has approved the revised cap...            │
└─────────────────────────────────────────────┘
```

**Header area:**

- Channel icon (phone, video camera, or people icon as appropriate), participant display names (comma-separated, truncated with count if many), direction shows "↔ Meeting" for mutual
- Timestamp and duration (if provided)

**Subject line:**

- If subject is provided, rendered as heading above content divider. Otherwise omitted.

**Content area:**

- cleaned_html (the user's notes) rendered as plain text.

#### 4.2.5 Video Meeting (Recorded) Preview

Same structure as Phone Call (Recorded) with video camera icon.

#### 4.2.6 Note Channel Preview

```
┌─────────────────────────────────────────────┐
│  📝  Bob Smith, Jane Lee                    │
│       Feb 21, 4:30 PM                       │
│                                             │
│  Quick sync on project status               │
│─────────────────────────────────────────────│
│                                             │
│  Bob mentioned they're reconsidering the    │
│  timeline for the west campus expansion...  │
└─────────────────────────────────────────────┘
```

Same structure as manual entries. Note icon. No duration. Subject and content as provided by the user.

### 4.3 Triage Indicator

If the communication has a non-NULL triage_result, a triage indicator renders at the very top of the Preview Card, above the header:

```
┌─────────────────────────────────────────────┐
│  ⚠ Filtered: No known contacts             │
│─────────────────────────────────────────────│
│  ✉  noreply@service.com        10:15 AM    │
│     To: Doug Bower               Feb 21     │
│  ...                                        │
└─────────────────────────────────────────────┘
```

The indicator is a single line showing the triage_result in human-readable form. It does not include an override action — the Preview Card is non-interactive. Override is available on the grid row's context menu or in the full View's Triage Card.

### 4.4 Preview Card Rendering Rules Summary

| Rule                        | Behavior                                                                                                                                                |
| --------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Fills available space**   | Content is never artificially truncated. The card uses all vertical space provided by the Window. If content exceeds available space, the card scrolls. |
| **Non-interactive**         | No action buttons, no clickable links, no editing affordances. The card is a pure reading surface.                                                      |
| **Empty field suppression** | If a field has no value (e.g., no subject on an SMS), that element is omitted entirely. No labels without values.                                       |
| **Participant truncation**  | If the participant list exceeds available width, truncate with count ("+N others").                                                                     |
| **Timestamp formatting**    | Today: time only. This year: "Mon DD, HH:MM AM/PM". Older: "Mon DD, YYYY HH:MM AM/PM".                                                                  |
| **Triage indicator**        | Shown at top of card when triage_result is non-NULL.                                                                                                    |
| **Channel icon**            | Always present at top-left of header. Provides instant visual identification of communication type.                                                     |

**Tasks:**

- [ ] CVPV-01: Implement Preview Card container (sole occupant of Docked/Undocked Window in Preview Mode, scrollable, fills available space)
- [ ] CVPV-02: Implement email channel Preview Card rendering (header, subject, content, attachment indicator)
- [ ] CVPV-03: Implement SMS/MMS channel Preview Card rendering
- [ ] CVPV-04: Implement phone call (recorded) channel Preview Card rendering
- [ ] CVPV-05: Implement manual entry channels Preview Card rendering (phone_manual, video_manual, in_person, note)
- [ ] CVPV-06: Implement video call (recorded) channel Preview Card rendering
- [ ] CVPV-07: Implement triage indicator overlay on Preview Card
- [ ] CVPV-08: Implement participant list truncation logic
- [ ] CVPV-09: Implement timestamp formatting rules

**Tests:**

- [ ] CVPV-T01: Preview Card renders email with all fields populated (sender, recipients, CC, subject, body, attachments)
- [ ] CVPV-T02: Preview Card renders email with NULL subject (subject line omitted, content flows below header)
- [ ] CVPV-T03: Preview Card renders SMS with short body (no scrolling needed)
- [ ] CVPV-T04: Preview Card renders phone call with duration and transcript
- [ ] CVPV-T05: Preview Card renders manual entry with user-authored content
- [ ] CVPV-T06: Preview Card renders triaged communication with triage indicator
- [ ] CVPV-T07: Preview Card truncates participant list when exceeding available width
- [ ] CVPV-T08: Preview Card fills available space without artificial truncation
- [ ] CVPV-T09: Preview Card scrolls when content exceeds available space
- [ ] CVPV-T10: Preview Card has no interactive elements (no buttons, no clickable links)
- [ ] CVPV-T11: Preview Card timestamp formats correctly for today, this year, and older dates
- [ ] CVPV-T12: Arrow-key navigation updates Preview Card within 200ms

---

## 5. Full View — Responsive Layout

**Supports processes:** KP-2 (step 1)

### 5.1 Layout Logic

The Communication full View uses a **content-aware responsive layout** that determines whether to arrange the Content Card and CRM layer cards in a single column (content above, CRM below) or two columns (content on the left, CRM on the right).

**Decision inputs:**

| Input           | How Measured                                                                                            |
| --------------- | ------------------------------------------------------------------------------------------------------- |
| Available width | The rendering width of the Window (Modal Full Overlay, Undocked Window, or Docked Window in View Mode). |
| Content volume  | Word count of cleaned_html.                                                                            |

**Decision rules:**

| Condition                                                                | Layout                                                                                                                                                                                 |
| ------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Available width < two-column minimum threshold                           | Single column. Always.                                                                                                                                                                 |
| Available width ≥ threshold AND content volume ≤ short content threshold | Single column. Content is short enough that it flows naturally above the CRM cards without requiring the user to scroll past a wall of text.                                           |
| Available width ≥ threshold AND content volume > short content threshold | Two column. Content in the left column (wider), CRM cards stacked in the right column (narrower). This prevents the user from having to scroll past long content to reach CRM context. |

**Two-column split:** When two-column layout is active, the Content Card occupies approximately 60-65% of the available width and the CRM card column occupies the remaining 35-40%. These proportions are initial defaults — exact values should be tuned during implementation to feel balanced across typical email lengths.

**Threshold calibration:** The exact thresholds (minimum width for two-column, word count for "short" content) are implementation details to be determined during development and tuned based on visual testing. As a starting point:

- Two-column minimum width: ~900px (the point where both columns can render comfortably)
- Short content threshold: ~150 words (the point where single-column layout would push CRM cards below the fold on a typical display)

These are guideline values, not specifications. The goal is that the user perceives the layout as "right" every time.

### 5.2 Single-Column Layout

```
┌──────────────────────────────────────────────────────┐
│  Window Header (Maximize / Undock / Close)            │
├──────────────────────────────────────────────────────┤
│  Identity Card                                        │
├──────────────────────────────────────────────────────┤
│  Content Card (native reading experience)             │
│  ┌──────────────────────────────────────────────────┐│
│  │  Header (sender, recipients, timestamp)          ││
│  │  Subject                                         ││
│  │  ────────────────────────────────────────────    ││
│  │  Body (cleaned_html)                            ││
│  │  Attachments (with download actions)             ││
│  └──────────────────────────────────────────────────┘│
├──────────────────────────────────────────────────────┤
│  Participants Card                                    │
├──────────────────────────────────────────────────────┤
│  Summary Card                                         │
├──────────────────────────────────────────────────────┤
│  Conversation Card                                    │
├──────────────────────────────────────────────────────┤
│  [Triage Card — if triage_result non-NULL]            │
├──────────────────────────────────────────────────────┤
│  [Notes Card — if notes attached]                     │
├──────────────────────────────────────────────────────┤
│  [Metadata Card — always present but collapsible]     │
└──────────────────────────────────────────────────────┘
```

### 5.3 Two-Column Layout

```
┌────────────────────────────────────────────────────────────────────┐
│  Window Header (Maximize / Undock / Close)                          │
├────────────────────────────────────────────────────────────────────┤
│  Identity Card (full width)                                         │
├────────────────────────────┬───────────────────────────────────────┤
│  Content Card (~60-65%)    │  Participants Card                     │
│  ┌────────────────────────┐│  ┌───────────────────────────────────┐│
│  │  Header                ││  │  (participant list)               ││
│  │  Subject               ││  └───────────────────────────────────┘│
│  │  ──────────────────    ││  Summary Card                         │
│  │  Body                  ││  ┌───────────────────────────────────┐│
│  │  (cleaned_html)       ││  │  (published summary)              ││
│  │                        ││  └───────────────────────────────────┘│
│  │                        ││  Conversation Card                    │
│  │                        ││  ┌───────────────────────────────────┐│
│  │                        ││  │  (conversation link)              ││
│  │  Attachments           ││  └───────────────────────────────────┘│
│  └────────────────────────┘│  [Triage Card]                        │
│                            │  [Notes Card]                          │
│                            │  [Metadata Card]                       │
├────────────────────────────┴───────────────────────────────────────┤
```

In two-column layout, the left and right columns scroll independently. The user can scroll through a long email body without losing the CRM context visible in the right column.

**Tasks:**

- [ ] CVLY-01: Implement content-aware layout decision logic (width threshold + word count threshold)
- [ ] CVLY-02: Implement single-column layout for full View
- [ ] CVLY-03: Implement two-column layout with independent scrolling
- [ ] CVLY-04: Layout re-evaluates on window resize (e.g., Undocked Window resized, Splitter Bar dragged)

**Tests:**

- [ ] CVLY-T01: Short email in wide window renders single-column
- [ ] CVLY-T02: Long email in wide window renders two-column
- [ ] CVLY-T03: Long email in narrow window renders single-column
- [ ] CVLY-T04: Resizing window from wide to narrow transitions from two-column to single-column
- [ ] CVLY-T05: Two-column layout columns scroll independently
- [ ] CVLY-T06: Short SMS in any width renders single-column

---

## 6. Full View — Identity Card

**Supports processes:** KP-2 (step 2)

The Communication Identity Card renders at the top of the full View, above the Content Card and CRM layer. It provides a compact identifying header consistent with the Identity Card pattern used by all entity types.

### 6.1 Communication Identity Card Rendering

The Identity Card for a Communication is minimal — it establishes *what* this record is without duplicating the detailed header that appears inside the Content Card.

```
┌─────────────────────────────────────────────────────┐
│  ✉ Email · Inbound · Synced           Feb 21, 2026  │
│  from Work Gmail (doug@company.com)      10:15 AM   │
└─────────────────────────────────────────────────────┘
```

**Fields displayed:**

| Element              | Source                                   | Rendering                                                                         |
| -------------------- | ---------------------------------------- | --------------------------------------------------------------------------------- |
| Channel icon + label | channel field                            | Icon and human-readable channel name (e.g., "✉ Email", "📞 Phone Call", "💬 SMS") |
| Direction            | direction field                          | "Inbound", "Outbound", or "Meeting"                                               |
| Source               | source field                             | "Synced", "Manual", or "Imported"                                                 |
| Provider account     | provider_account_id → account_identifier | Account display name or email address. Omitted for manual entries.                |
| Timestamp            | timestamp field                          | Full date and time, right-aligned                                                 |

The Identity Card does **not** show the subject, sender, recipients, or content — those belong in the Content Card where they form the natural reading experience. The Identity Card answers "what kind of record is this and where did it come from?"

**Tasks:**

- [ ] CVID-01: Implement Communication Identity Card rendering per channel
- [ ] CVID-02: Identity Card omits provider account for manual entries

**Tests:**

- [ ] CVID-T01: Synced email Identity Card shows channel, direction, source, provider account, timestamp
- [ ] CVID-T02: Manual phone call Identity Card omits provider account
- [ ] CVID-T03: Identity Card renders within Identity Card fixed area (no scrolling)

---

## 7. Full View — Content Card

**Supports processes:** KP-2 (step 2), KP-3 (step 2)

The Content Card is the primary reading surface in the full View. It presents the communication as a native reading experience — the user should feel like they are reading the communication in its original context, not viewing a CRM record.

### 7.1 Email Content Card

```
┌──────────────────────────────────────────────────────────────────┐
│                                                                   │
│  Bob Smith                                     Aug 25, 2017      │
│  bob.smith@acmecorp.com                           6:51 AM        │
│                                                                   │
│  To: **Doug Bower**, Jane Lee, Tom Clark +2 Others                │
│  CC: Alice Wong, Dan White +4 Others                              │
│                                                                   │
│  RE: new owner of hanger                                          │
│──────────────────────────────────────────────────────────────────│
│                                                                   │
│  Your guy.                                                        │
│                                                                   │
│  I am on my way home and will call you when I get back in the US. │
│                                                                   │
│  Doug                                                             │
│                                                                   │
│──────────────────────────────────────────────────────────────────│
│  📎 Attachments (2)                                               │
│  ┌──────────────────────────────────────────────────────────────┐│
│  │  📄 revised_clause5.docx         42 KB  ⬇                   ││
│  │  📄 contract_v3.pdf             128 KB  ⬇                   ││
│  └──────────────────────────────────────────────────────────────┘│
│──────────────────────────────────────────────────────────────────│
│  ▸ View Original                                                  │
└──────────────────────────────────────────────────────────────────┘
```

**Header section — Visual hierarchy:**

The header establishes who, to whom, and what in the first two seconds. Three tiers of prominence:

1. **Sender name** — Largest, boldest text in the header. The user’s first anchor point. Reads as the answer to “who sent this?”
2. **Subject line** — Largest, boldest text on the entire card (rendered as a heading below the recipient lines). The answer to “what is this about?”
3. **Sender email, recipients, timestamp** — Clearly readable but subordinate. Supporting context, not primary focus.

**Header section — Sender (left side):**

- **Sender display name** on the first line — large, bold, high contrast. This is the most prominent element in the header area after the subject line. If the sender is unresolved (no CRM contact), the email address renders in the name position instead.
- **Sender email address** on the second line — smaller, lighter weight. Provides the specific address for disambiguation.
- Sender name is a clickable link to the Contact record if resolved.

**Header section — Timestamp (right side):**

- Right-aligned on the same line as the sender name.
- Date on the first line, time on the second line (matching the sender name / sender email two-line structure).
- Timestamp formatting: Today → time only. This year → “Mon DD” + time. Older → “Mon DD, YYYY” + time.

**Header section — Recipients:**

Recipients use a compact format that answers three questions instantly: “Was I in the To or CC?”, “Who else was involved?”, and “How many people?”

Rules for the **To:** line:

1. If the current user is a To recipient, their name appears **first and bold** — visually distinct from other names.
2. After the current user (if present), remaining To recipients are listed alphabetically by last name.
3. Show a maximum of **three names** per line (including the current user if present).
4. If more To recipients exist beyond three, show **“+X Others”** as a clickable link that navigates to the Participants Card.

Rules for the **CC:** line:

1. CC line is only shown if CC recipients exist.
2. If the current user is a CC recipient (and not in To), their name appears **first and bold** on the CC line.
3. Same three-name maximum and “+X Others” link as the To line.
4. If no CC recipients exist, the CC line is omitted entirely.

Rules for **BCC:**

- BCC recipients are treated identically to single-recipient CC for display purposes. The BCC line is only visible to the sender/account owner.

**Outbound emails:**

- The current user’s name appears in the From line (as sender). No bolding in the To/CC lines since the user is not a recipient.

**Recipient name rendering:**

- Resolved contacts: display name rendered as a clickable link to the Contact record.
- Unresolved participants: email address rendered as plain text with a subtle “unresolved” indicator.
- The current user’s name is always **bold** regardless of resolved/unresolved status.

**Subject line:**

- Rendered as the **largest, boldest text on the entire Content Card** — a clear heading below the recipient lines, above the content divider.
- Prominent enough that the user’s eye goes to it naturally as the answer to “what is this about?”
- If NULL (rare for email), the subject line is omitted and the content flows directly below the recipients.

**Body:**

- cleaned_html rendered as formatted text. The original paragraph structure is preserved.
- If the email contained HTML formatting (bold, italic, links, lists), cleaned_html should preserve this structure where the extraction pipeline retains it. Simple formatting renders natively; complex HTML layouts are flattened to readable text.

**Attachment area:**

- If has_attachments is true, an attachment section renders below the body, separated by a divider.
- Each attachment renders as a row: file type icon, filename, file size, and a download action button (⬇).
- Attachment rows are interactive — clicking the download button initiates the download (on-demand from provider in Phase 1, from object storage in Phase 2+).

**View Original expander:**

- A collapsible section at the bottom of the Content Card. Collapsed by default.
- When expanded, shows original_text — the original, unprocessed content including quoted replies, signatures, and boilerplate that the content extraction pipeline removed.
- Purpose: debugging and verification. Users can confirm that content extraction didn't remove important content.

### 7.2 SMS / MMS Content Card

```
┌──────────────────────────────────────────────────────┐
│  Bob Smith · (216) 555-0142          → Outbound      │
│                                                       │
│  Hey, did you see my questions about clause 5?        │
└──────────────────────────────────────────────────────┘
```

Minimal header: participant name + phone number, direction. Body is cleaned_html. No subject line. No "View Original" expander (cleaned_html = original_text for SMS). MMS with media attachments shows the attachment area.

### 7.3 Phone Call (Recorded) Content Card

```
┌──────────────────────────────────────────────────────┐
│  Call with Bob Smith                  ← Inbound      │
│  Duration: 12 min                                     │
│──────────────────────────────────────────────────────│
│                                                       │
│  [Transcript]                                         │
│                                                       │
│  Bob: So I've talked to legal about the liability     │
│  cap and they're comfortable with $500K.              │
│                                                       │
│  Doug: Great. And what about the timeline?            │
│                                                       │
│  Bob: We're thinking March 15 for signing now...      │
│                                                       │
│──────────────────────────────────────────────────────│
│  🎧 Recording                              ▶ Play    │
└──────────────────────────────────────────────────────┘
```

Header: "Call with [participants]", direction, duration. Body: cleaned_html (processed transcript) with speaker labels if available. Recording: if an audio recording attachment exists, a playback control renders at the bottom.

### 7.4 Phone Call (Manual) / Video Meeting (Manual) / In-Person Meeting Content Card

```
┌──────────────────────────────────────────────────────┐
│  Meeting with Bob Smith, Jane Lee     ↔ Meeting      │
│  Duration: 45 min                                     │
│                                                       │
│  Lease Negotiation Check-in                           │
│──────────────────────────────────────────────────────│
│                                                       │
│  Discussed the outstanding issues on clauses 5        │
│  and 8. Bob confirmed legal has approved the          │
│  revised liability cap...                             │
│──────────────────────────────────────────────────────│
│  📎 Attachments (1)                                   │
│  ┌──────────────────────────────────────────────────┐│
│  │  📄 meeting_notes.pdf            85 KB  ⬇       ││
│  └──────────────────────────────────────────────────┘│
└──────────────────────────────────────────────────────┘
```

Header: "[Channel type] with [participants]", direction (usually "↔ Meeting"), duration if provided. Subject if provided. Body: cleaned_html (the user's notes). Attachments if any.

### 7.5 Video Meeting (Recorded) Content Card

Same structure as Phone Call (Recorded) with video icon and video playback control instead of audio playback.

### 7.6 Content Card Rendering Rules

| Rule                      | Behavior                                                                                                                                                                                                                       |
| ------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Participant links**     | Resolved contacts are clickable links navigating to the Contact record. Unresolved participants render as plain text with a subtle indicator.                                                                                  |
| **Fills available space** | No artificial truncation. Content flows to its natural length. Card scrolls if content exceeds available space (in single-column layout, the whole view scrolls; in two-column layout, the left column scrolls independently). |
| **View Original**         | Available only for channels where cleaned_html differs from original_text (primarily email). Collapsed by default.                                                                                                              |
| **Attachment actions**    | Download button on each attachment. Playback controls for audio/video recordings. These are the only interactive elements in the Content Card.                                                                                 |

**Tasks:**

- [ ] CVCC-01: Implement email Content Card header visual hierarchy (sender name prominent, subject boldest, supporting context subordinate)
- [ ] CVCC-02: Implement sender display (name bold on line 1, email smaller on line 2, timestamp right-aligned)
- [ ] CVCC-03: Implement recipient line logic (current user bold and first, alphabetical remaining, three-name cap, "+X Others" link)
- [ ] CVCC-04: Implement CC line display with same rules as To line
- [ ] CVCC-05: Implement subject line as largest/boldest text on Content Card
- [ ] CVCC-06: Implement email Content Card body rendering (cleaned_html with formatting preserved)
- [ ] CVCC-07: Implement SMS/MMS Content Card rendering
- [ ] CVCC-08: Implement recorded call Content Card rendering (transcript + playback)
- [ ] CVCC-09: Implement manual entry Content Card rendering (phone_manual, video_manual, in_person, note)
- [ ] CVCC-10: Implement recorded video Content Card rendering (transcript + video playback)
- [ ] CVCC-11: Implement participant name linking to Contact records
- [ ] CVCC-12: Implement View Original expander for email
- [ ] CVCC-13: Implement attachment download action
- [ ] CVCC-14: Implement audio/video playback controls
- [ ] CVCC-15: Implement "+X Others" link navigation to Participants Card

**Tests:**

- [ ] CVCC-T01: Sender name renders large and bold; sender email renders smaller below
- [ ] CVCC-T02: Timestamp renders right-aligned opposite sender name
- [ ] CVCC-T03: Inbound email — current user appears bold and first in To line when user is a To recipient
- [ ] CVCC-T04: Inbound email — current user appears bold and first in CC line when user is CC only
- [ ] CVCC-T05: To line with 5 recipients shows 3 names + "+2 Others" link
- [ ] CVCC-T06: CC line omitted when no CC recipients exist
- [ ] CVCC-T07: Outbound email — current user in From, no bolding in To/CC lines
- [ ] CVCC-T08: "+X Others" link navigates to Participants Card
- [ ] CVCC-T09: Remaining recipients (after current user) sorted alphabetically by last name
- [ ] CVCC-T10: Subject line renders as largest/boldest text on the card
- [ ] CVCC-T11: Resolved participant names render as clickable links
- [ ] CVCC-T12: Unresolved participant names render as plain text with indicator
- [ ] CVCC-T13: BCC line visible only to sender/account owner
- [ ] CVCC-T14: View Original expander shows original_text when expanded
- [ ] CVCC-T15: View Original expander is collapsed by default
- [ ] CVCC-T16: Attachment download action initiates file download
- [ ] CVCC-T17: Audio recording shows playback controls
- [ ] CVCC-T18: SMS Content Card omits subject and View Original
- [ ] CVCC-T19: Manual entry Content Card renders user-authored notes
- [ ] CVCC-T20: Content Card with no attachments omits attachment area entirely
- [ ] CVCC-T21: Single To recipient, no CC — To line shows one name, CC line omitted

---

## 8. Full View — Participants Card

**Supports processes:** KP-2 (step 3)

### 8.1 Purpose

The Participants Card shows all participants in the communication with their roles, resolution status, and links to their Contact records. While the Content Card header shows participants in the context of the communication (From/To/CC), the Participants Card provides the CRM perspective — who are these people, what company are they from, and what is their relationship to the user.

### 8.2 Rendering

Each participant renders as a compact row:

```
┌──────────────────────────────────────────────────────┐
│  Participants                                         │
│──────────────────────────────────────────────────────│
│  Bob Smith              Sender                        │
│  VP Engineering · Acme Corp                           │
│                                                       │
│  Doug Bower             To           (You)            │
│  Owner · CRMExtender                                  │
│                                                       │
│  Jane Lee               CC                            │
│  Legal Counsel · Acme Corp                            │
└──────────────────────────────────────────────────────┘
```

| Element                 | Source                                                           | Rendering                                                                                        |
| ----------------------- | ---------------------------------------------------------------- | ------------------------------------------------------------------------------------------------ |
| Name                    | Contact display name (or participant display_name if unresolved) | Clickable link to Contact record (if resolved). Plain text with unresolved indicator if pending. |
| Role                    | Participant relation metadata: role                              | "Sender", "To", "CC", "BCC", "Participant" — right-aligned on the name line                      |
| Title + Company         | Contact's current employment                                     | Rendered below the name in lighter text. Omitted if the contact has no employment record.        |
| Account owner indicator | is_account_owner flag                                            | "(You)" badge if this participant is the account owner                                           |

### 8.3 Suppression

The Participants Card is suppressed (hidden) only if the communication has zero participant relations — which should not occur under normal operation but may exist for edge cases during data migration or import.

**Tasks:**

- [ ] CVPT-01: Implement Participants Card with per-participant rows
- [ ] CVPT-02: Implement Contact record navigation from participant name
- [ ] CVPT-03: Implement unresolved participant indicator
- [ ] CVPT-04: Implement account owner "(You)" badge

**Tests:**

- [ ] CVPT-T01: Participants Card shows all participants with correct roles
- [ ] CVPT-T02: Resolved participant names link to Contact records
- [ ] CVPT-T03: Unresolved participants show indicator
- [ ] CVPT-T04: Account owner participant shows "(You)" badge
- [ ] CVPT-T05: Participant title and company displayed from employment record
- [ ] CVPT-T06: Participants Card suppressed when no participant relations exist

---

## 9. Full View — Summary Card

**Supports processes:** KP-2 (step 3, step 4)

### 9.1 Purpose

The Summary Card displays the Communication's Published Summary — the distilled representation of the communication's content. This is what appears in the Conversation timeline and what the Conversation-level AI consumes.

### 9.2 Rendering

```
┌──────────────────────────────────────────────────────┐
│  Summary                    🤖 AI Generated    ✏ ↻   │
│──────────────────────────────────────────────────────│
│                                                       │
│  Key points:                                          │
│  • Proposed liability cap at $500K for clause 5       │
│  • Requested 30-day review period instead of 14       │
│                                                       │
│  Action items:                                        │
│  • Bob to send revised clause 5 language by Friday    │
│  • Review indemnification section (clause 8) next     │
│                                                       │
│  Rev 2 of 2 · Last updated Feb 21 by AI              │
└──────────────────────────────────────────────────────┘
```

| Element           | Source                                            | Rendering                                                                                                                                                       |
| ----------------- | ------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Card header       | "Summary"                                         | Standard card header                                                                                                                                            |
| Source badge      | summary_source                                    | "🤖 AI Generated", "✍ User Authored", or "📋 Pass-through" — right of header                                                                                    |
| Edit action       | —                                                 | Pencil icon (✏). Opens the summary in the rich text editor for user editing. Creates a new summary revision on save.                                            |
| Regenerate action | —                                                 | Refresh icon (↻). Available only for AI-generated and pass-through summaries. Re-runs AI summary generation from cleaned_html. Creates a new summary revision. |
| Summary content   | summary_html                                      | Rendered as rich text (headings, lists, bold). The HTML as produced by the AI or the user's editor.                                                             |
| Revision info     | summary_revision_count, current revision metadata | "Rev N of N · Last updated [date] by [AI or username]". Clicking opens revision history (future: revision comparison view).                                     |

### 9.3 Suppression

The Summary Card is suppressed if all summary fields are NULL (summary_json, summary_html, summary_text all NULL). This can occur if summary generation has not yet run or if the communication was triaged before summary generation.

### 9.4 Edit and Regenerate Workflows

**Edit:** Clicking the edit icon transitions the Summary Card to Edit Mode — the summary_html is replaced by the rich text editor loaded with summary_json. Save creates a new summary revision with summary_source = 'user_authored'. Cancel discards changes.

**Regenerate:** Clicking the regenerate icon triggers the AI summary generation pipeline. A brief loading state displays while AI processes. On completion, the Summary Card updates with the new AI-generated summary and a new revision is created with summary_source = 'ai_generated'. The previous summary is preserved in revision history.

Both workflows are defined in detail in the Published Summary Sub-PRD. This section defines only the UI trigger points.

**Tasks:**

- [ ] CVSU-01: Implement Summary Card rendering with rich text content
- [ ] CVSU-02: Implement source badge display
- [ ] CVSU-03: Implement edit action (transition to rich text editor)
- [ ] CVSU-04: Implement regenerate action with loading state
- [ ] CVSU-05: Implement revision info display

**Tests:**

- [ ] CVSU-T01: Summary Card renders AI-generated summary with correct badge
- [ ] CVSU-T02: Summary Card renders user-authored summary with correct badge
- [ ] CVSU-T03: Summary Card renders pass-through summary with correct badge
- [ ] CVSU-T04: Edit action opens rich text editor with current summary
- [ ] CVSU-T05: Regenerate action triggers AI pipeline and updates card on completion
- [ ] CVSU-T06: Summary Card suppressed when all summary fields are NULL
- [ ] CVSU-T07: Revision info displays correct count and last update metadata

---

## 10. Full View — Conversation Card

**Supports processes:** KP-2 (step 3, step 4)

### 10.1 Purpose

The Conversation Card shows which conversation this communication belongs to, enabling quick navigation to the parent conversation.

### 10.2 Rendering

```
┌──────────────────────────────────────────────────────┐
│  Conversation                                         │
│──────────────────────────────────────────────────────│
│  📂 Lease Negotiation with Acme Corp    → Open       │
│     Active · 12 communications · Last: Feb 21        │
└──────────────────────────────────────────────────────┘
```

**If assigned to a conversation:**

| Element             | Rendering                                                                     |
| ------------------- | ----------------------------------------------------------------------------- |
| Conversation title  | Clickable link navigating to the Conversation record                          |
| Status              | Conversation's current status                                                 |
| Communication count | Number of communications in the conversation                                  |
| Last activity       | Timestamp of the most recent communication in the conversation                |
| Open action         | Navigates to the Conversation entity workspace with this conversation focused |

**If unassigned (conversation_id is NULL):**

```
┌──────────────────────────────────────────────────────┐
│  Conversation                                         │
│──────────────────────────────────────────────────────│
│  Not assigned to a conversation          [Assign]     │
└──────────────────────────────────────────────────────┘
```

The Assign action opens a conversation picker — the user can select an existing conversation or create a new one. Assigning sets the conversation_id FK and emits a `conversation_assigned` event.

### 10.3 Suppression

The Conversation Card is **never suppressed** — it always renders, either showing the assigned conversation or the "Not assigned" state with the Assign action. This ensures the user always has visibility into whether the communication has been organized.

**Tasks:**

- [ ] CVCV-01: Implement Conversation Card with assigned conversation display
- [ ] CVCV-02: Implement unassigned state with Assign action
- [ ] CVCV-03: Implement conversation picker for assignment
- [ ] CVCV-04: Implement navigation to Conversation record

**Tests:**

- [ ] CVCV-T01: Assigned communication shows conversation title, status, count, last activity
- [ ] CVCV-T02: Unassigned communication shows "Not assigned" with Assign action
- [ ] CVCV-T03: Assign action opens conversation picker
- [ ] CVCV-T04: Assigning a conversation updates the card and emits event
- [ ] CVCV-T05: Conversation title link navigates to Conversation record

---

## 11. Full View — Triage Card

**Supports processes:** KP-3 (step 2)

### 11.1 Purpose

The Triage Card explains why a communication was filtered by the triage pipeline and provides an override action. It only appears for communications with a non-NULL triage_result.

### 11.2 Rendering

```
┌──────────────────────────────────────────────────────┐
│  ⚠ Filtered by Triage                                │
│──────────────────────────────────────────────────────│
│  Classification: No known contacts                    │
│  Reason: None of the participants in this email       │
│  are recognized CRM contacts.                         │
│                                                       │
│  [Override — Mark as Real]                             │
└──────────────────────────────────────────────────────┘
```

| Element         | Source        | Rendering                                                                                                                                                         |
| --------------- | ------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Classification  | triage_result | Human-readable triage category                                                                                                                                    |
| Reason          | triage_reason | Explanation of why the communication was filtered                                                                                                                 |
| Override action | —             | Button that clears triage_result, queues the communication for AI processing (summary generation, conversation assignment), and emits a `triage_overridden` event |

### 11.3 Suppression

The Triage Card is suppressed when triage_result is NULL (the communication passed triage or triage has not run). It is also suppressed after a successful override — once the triage is cleared, the card disappears and the Summary Card and Conversation Card populate as AI processing completes.

**Tasks:**

- [ ] CVTR-01: Implement Triage Card rendering
- [ ] CVTR-02: Implement Override action with event emission
- [ ] CVTR-03: Triage Card suppressed after successful override

**Tests:**

- [ ] CVTR-T01: Triage Card renders for filtered communication with classification and reason
- [ ] CVTR-T02: Override action clears triage_result and queues AI processing
- [ ] CVTR-T03: Triage Card suppressed when triage_result is NULL
- [ ] CVTR-T04: Triage Card suppressed after override completes

---

## 12. Full View — Notes Card

**Supports processes:** KP-2 (step 3)

### 12.1 Purpose

The Notes Card displays any notes attached to this communication. Notes are supplementary commentary about the interaction — observations, follow-up reminders, or context that the user wants to capture alongside the communication record.

### 12.2 Rendering

Each attached note renders as a compact entry:

```
┌──────────────────────────────────────────────────────┐
│  Notes (2)                                    [+ Add] │
│──────────────────────────────────────────────────────│
│  Doug Bower · Feb 21, 4:30 PM                         │
│  Bob seemed hesitant about the pricing — follow       │
│  up with a discount offer next week.                  │
│                                                       │
│  Doug Bower · Feb 22, 9:15 AM                         │
│  Confirmed with legal that our counter-proposal       │
│  on clause 5 is acceptable.                           │
└──────────────────────────────────────────────────────┘
```

| Element      | Rendering                                                                                                                                  |
| ------------ | ------------------------------------------------------------------------------------------------------------------------------------------ |
| Card header  | "Notes" with count in parentheses. "+ Add" action to create a new note attached to this communication.                                     |
| Note entries | Author name, timestamp, and note content (content_text or a preview of content_html). Each note is clickable to open the full Note record. |

### 12.3 Suppression

The Notes Card is suppressed when no notes are attached to the communication.

**Tasks:**

- [ ] CVNO-01: Implement Notes Card rendering with attached note entries
- [ ] CVNO-02: Implement "+ Add" action for creating a new note
- [ ] CVNO-03: Implement note entry click to open full Note record

**Tests:**

- [ ] CVNO-T01: Notes Card renders attached notes with author, timestamp, content preview
- [ ] CVNO-T02: "+ Add" action creates a new note attached to the communication
- [ ] CVNO-T03: Note entry click opens full Note record
- [ ] CVNO-T04: Notes Card suppressed when no notes are attached

---

## 13. Full View — Metadata Card

**Supports processes:** KP-2 (step 3)

### 13.1 Purpose

The Metadata Card displays system and provider information about the communication — how it entered the system, which account captured it, sync details, and event history. This is operational/diagnostic information that most users rarely need but power users and administrators value.

### 13.2 Rendering

```
┌──────────────────────────────────────────────────────┐
│  Metadata                                      ▾      │
│──────────────────────────────────────────────────────│
│  Source              Synced                            │
│  Provider            Gmail                             │
│  Account             doug@company.com                  │
│  Provider Message ID  18d4a3f2e1b...                  │
│  Provider Thread ID   18d4a3f2e1a...                  │
│  Created             Feb 21, 2026 10:16 AM             │
│  Last Updated        Feb 21, 2026 10:16 AM             │
│                                                       │
│  ▸ Event History (4 events)                           │
└──────────────────────────────────────────────────────┘
```

| Element           | Source                                  | Rendering                                                                                                                            |
| ----------------- | --------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| Source            | source field                            | "Synced", "Manual", "Imported"                                                                                                       |
| Provider          | provider_account → provider             | Provider name. Omitted for manual entries.                                                                                           |
| Account           | provider_account → account_identifier   | Account email/number. Omitted for manual entries.                                                                                    |
| Provider IDs      | provider_message_id, provider_thread_id | Raw provider identifiers. Omitted for manual entries.                                                                                |
| Created / Updated | created_at, updated_at                  | Timestamps                                                                                                                           |
| Event History     | communications_events                   | Collapsible list of event records. Collapsed by default. When expanded, shows event type, timestamp, changed_by, and change details. |

### 13.3 Default State

The Metadata Card renders **collapsed by default** (showing only the header with a collapse/expand toggle). Users who need the information can expand it. This keeps the default view focused on the communication content and CRM intelligence rather than system internals.

### 13.4 Suppression

The Metadata Card is never suppressed — every communication has metadata. But its collapsed default state means it occupies minimal space until needed.

**Tasks:**

- [ ] CVMD-01: Implement Metadata Card with field rendering
- [ ] CVMD-02: Implement collapsed default state
- [ ] CVMD-03: Implement Event History collapsible section

**Tests:**

- [ ] CVMD-T01: Metadata Card renders all fields for synced communication
- [ ] CVMD-T02: Metadata Card omits provider fields for manual communication
- [ ] CVMD-T03: Metadata Card renders collapsed by default
- [ ] CVMD-T04: Event History expands to show event records

---

## 14. Card Ordering

### 14.1 Default Card Order — Single Column

In single-column layout, cards render in this order (top to bottom):

1. Identity Card
2. Content Card
3. Participants Card
4. Summary Card
5. Conversation Card
6. Triage Card (conditional)
7. Notes Card (conditional)
8. Metadata Card (collapsed by default)

### 14.2 Default Card Order — Two Column

In two-column layout:

**Left column (primary — ~60-65% width):**

1. Content Card

**Right column (CRM layer — ~35-40% width):**

1. Participants Card
2. Summary Card
3. Conversation Card
4. Triage Card (conditional)
5. Notes Card (conditional)
6. Metadata Card (collapsed by default)

The Identity Card spans full width above both columns.

### 14.3 Ordering Rationale

The order prioritizes the most frequently needed information:

- Content first (the communication itself is always the primary interest)
- Participants next (who was involved)
- Summary next (distilled intelligence)
- Conversation next (organizational context)
- Conditional cards follow (triage, notes — only present when relevant)
- Metadata last (rarely needed, collapsed by default)

---

## Related Documents

| Document                                                                      | Relationship                                                                         |
| ----------------------------------------------------------------------------- | ------------------------------------------------------------------------------------ |
| [Communication Entity Base PRD](communication-entity-base-prd.md)             | Parent entity PRD. Defines KP-4 which this document implements.                      |
| [Communication Entity TDD](communication-entity-tdd.md)                       | Technical decisions for communication data storage and retrieval.                    |
| [GUI Functional Requirements PRD](gui-functional-requirements-prd.md)         | Card-Based Architecture, Window Types, Display Modes.                                |
| [GUI Preview Card Amendment](gui-preview-card-amendment.md)                   | System-wide Preview Card type definition.                                            |
| [Published Summary Sub-PRD](communication-published-summary-prd.md)           | Summary generation, edit, and regenerate workflows referenced by the Summary Card.   |
| [Participant Resolution Sub-PRD](communication-participant-resolution-prd.md) | Participant Relation Type and resolution status referenced by the Participants Card. |
| [Triage Sub-PRD](communication-triage-prd.md)                                 | Triage classification and override workflow referenced by the Triage Card.           |
| [Conversations PRD](conversations-prd.md)                                     | Conversation assignment and navigation referenced by the Conversation Card.          |
| [Notes PRD](notes-prd.md)                                                     | Note attachment and creation referenced by the Notes Card.                           |
| [Contact Entity Base PRD](contact-entity-base-prd.md)                         | Contact record navigation from participant links.                                    |
