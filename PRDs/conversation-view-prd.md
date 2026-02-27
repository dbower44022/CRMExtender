# Conversation — View Conversation Sub-PRD

**Version:** 1.1
**Last Updated:** 2026-02-27
**Status:** Draft
**Entity Base PRD:** [conversation-entity-base-prd.md]
**Referenced Entity PRDs:** [communication-entity-base-prd.md], [communication-published-summary-prd.md], [contact-entity-base-prd.md]
**GUI Documents:** [gui-functional-requirements-prd.md], [gui-preview-card-amendment.md]

---

## 1. Overview

### 1.1 Purpose

This Sub-PRD defines how a Conversation record is displayed when a user views it — both the quick Preview (browsing in the Detail Panel) and the full View (opening the record for deep reading). The primary design goal is a **communication timeline reading experience**: the user should feel like they are reviewing a threaded conversation history, not viewing a CRM record. The CRM intelligence layer (AI summary, participants, entity associations, aggregate children) is layered around the timeline rather than replacing it.

This document implements KP-4 (Viewing a Conversation Timeline) from the Conversation Entity Base PRD and introduces the Conversation-specific rendering for the Preview Card type defined in the GUI Preview Card Amendment.

The document covers both standard Conversations (is_aggregate = false) and aggregate Conversations (is_aggregate = true), which have distinct Preview Card and full View rendering.

### 1.2 Preconditions

- Conversation record exists and is accessible to the current user (per Permissions & Sharing PRD).
- For standard Conversations: at least one Communication exists with a Published Summary.
- For aggregate Conversations: at least one child Conversation or direct Communication exists.
- Participant resolution has run for Communications in the Conversation.

---

## 2. Context

### 2.1 Relevant Fields

| Field | Role in View |
|---|---|
| Subject | Primary heading in Identity Card and Preview Card header. Display name field. |
| Is Aggregate | Determines rendering variant (standard timeline vs. aggregate child list) and type icon. |
| System Status | Displayed in Identity Card and Preview Card header as a status badge. |
| AI Status | Displayed in Identity Card and Preview Card header as a status badge. |
| AI Summary | Rendered in the AI Intelligence Card in full View. |
| AI Action Items | Rendered in the AI Intelligence Card in full View. |
| AI Key Topics | Rendered in the AI Intelligence Card in full View. |
| AI Confidence | Displayed in the AI Intelligence Card in full View. |
| AI Last Processed At | Displayed in the AI Intelligence Card in full View. |
| Communication Count | Displayed in Preview Card header and Identity Card. For aggregates: includes all children's counts recursively. |
| Channel Breakdown | Displayed in Preview Card header as compact channel icons with counts. |
| First Activity At | Available in Metadata Card. |
| Last Activity At | Displayed in Preview Card header. Drives recency context. |
| Stale After Days | Displayed in Metadata Card. Editable threshold. |
| Closed After Days | Displayed in Metadata Card. Editable threshold. |
| Description | Displayed in Identity Card area. Primarily useful for aggregates. |
| Created By | Displayed in Metadata Card. |
| Created At | Displayed in Metadata Card. |
| Updated At | Displayed in Metadata Card. |

### 2.2 Relevant Relationships

- **Communications (Direct)** — FK reference from Communication to Conversation. Rendered as the conversation timeline in the Timeline Card, each Communication represented by its Published Summary.
- **Child Conversations (Membership)** — Many-to-many via junction table. For aggregates: rendered as child entries in the Preview Card and as the Children Card in full View.
- **Projects** — Via system Relation Type `conversation_projects`. Rendered in Entity Associations Card.
- **Companies** — Via system Relation Type `conversation_companies`. Rendered in Entity Associations Card.
- **Contacts (Explicit)** — Via system Relation Type `conversation_contacts`. Rendered in Entity Associations Card, distinguished from derived participants.
- **Events** — Via system Relation Type `conversation_events`. Rendered in Entity Associations Card.
- **Notes** — Via universal attachment. Rendered in Notes Card.
- **Derived Participants** — Union of Communication Participants across all Communications in the Conversation. Rendered in Participants Card.

### 2.3 Cross-Entity Context

- **GUI Preview Card Amendment:** The Preview Card is a system-wide Card Type. This document defines the Conversation-specific rendering for that card, including standard and aggregate variants.
- **GUI Functional Requirements PRD:** The Card-Based Architecture (Section 15), Window Types (Section 14), Display Modes, and Date & Time Display Standards (Section 2.3) define the containers and formatting conventions this view renders into. The dynamic responsive layout logic defined here extends the Card Layout Area behavior for Conversation full Views.
- **Communication Published Summary Sub-PRD:** Defines the Published Summary content rendered in each timeline entry. The Conversation timeline is a sequence of references to Communication Published Summaries.
- **Communication View Sub-PRD:** Defines the Communication full View that users navigate to via "View Original" links on timeline entries.
- **Contact Entity Base PRD:** Participant names in the Participants Card and timeline entries link to Contact records.
- **AI Intelligence & Review Sub-PRD:** Defines AI classification, summarization, and extraction workflows that populate the AI Intelligence Card fields.

---

## 3. Key Processes

### KP-1: Previewing a Conversation (Browsing)

**Trigger:** User focuses a conversation row in the grid (click, arrow-key navigation). The Docked Window or Undocked Window is in Preview Mode.

**Step 1 — Preview Card renders:** The Preview Card replaces any previous content in the Window. Rendering begins immediately on focus change (target: < 200ms). The card presents the most recent conversation activity.

**Step 2 — User scans activity:** The user reads the Preview Card to catch up on recent activity. For standard Conversations, the card shows the most recent Published Summary entries, most-recent-first. For aggregate Conversations, the card shows child Conversations sorted by last activity. The user scrolls through recent activity to decide whether deeper attention is warranted.

**Step 3 — User decides:** The user either moves to the next row (arrow key, click) causing a new Preview Card to render, or opens the full View (double-click, Enter key, or Maximize button) to see the complete timeline with CRM context.

### KP-2: Viewing a Conversation in Full (Deep Reading)

**Trigger:** User opens a conversation in View Mode via double-click on the grid row, Enter key on a focused row, or Maximize button on the Docked Window header. The record opens in a Modal Full Overlay Window, Undocked Window, or the Docked Window transitions to View Mode.

**Step 1 — Layout determined:** The system evaluates the available container width to determine single-column or two-column layout (see Section 5).

**Step 2 — Timeline renders:** The primary content area presents the conversation timeline — chronologically ordered Published Summary entries with channel icons, sender names, timestamps, and summary content. Timeline order follows the user's global preference (oldest-first or newest-first). Each entry links to its full Communication record.

**Step 3 — CRM layer renders:** Beside the timeline (two-column) or below it (single-column), the CRM intelligence cards render: Participants Card, AI Intelligence Card, Entity Associations Card, and conditionally the Children Card (aggregates only), Notes Card, and Metadata Card. Cards with no data are suppressed entirely.

**Step 4 — User interacts:** The user reads the timeline, reviews the CRM context, and may take actions: navigate to a Communication's full record ("View Original"), navigate to a participant's Contact record (Participants Card), edit entity associations (Entity Associations Card), drill into a child Conversation (Children Card), or add a note (Notes Card).

### KP-3: Viewing an Aggregate Conversation in Full

**Trigger:** User opens an aggregate Conversation (is_aggregate = true) in View Mode.

**Step 1 — Layout determined:** Same as KP-2 step 1.

**Step 2 — Children Card renders prominently:** The Children Card lists all child Conversations with their subjects, statuses, communication counts, and last activity dates. Each child is a navigable link to its own Conversation record.

**Step 3 — Direct Communications timeline:** If the aggregate has direct Communications (not belonging to any child), the Timeline Card renders these with the same Published Summary entry format as a standard Conversation.

**Step 4 — AI Intelligence Card:** The aggregate-level AI summary synthesizes across all children and direct Communications. This is a higher-order summary, not a concatenation.

---

## 4. Conversation Preview Card

**Supports processes:** KP-1 (full flow)

### 4.1 Rendering Principle

The Conversation Preview Card is a decision aid optimized for recency scanning. Its primary purpose is to show the user what happened recently in this conversation so they can decide whether to open the full View. The card uses a minimal header to maximize the space available for timeline content.

The Preview Card **always** renders timeline entries most-recent-first, regardless of the user's full View timeline order preference. This is because the Preview Card answers "what happened recently?" — a fundamentally different question from the full View's narrative reading experience.

### 4.2 Standard Conversation Preview

```
┌──────────────────────────────────────────────────┐
│  💬 Lease Negotiation with Acme Corp             │
│     Active · Open · 12 comms · ✉8 💬2 📞2       │
│                                                   │
│ ┌────────────────────────────────────────────────┐│
│ │ 🔵 ✉ Bob Smith → Doug Bower                   ││
│ │         Today, Feb 21 - 10:15 AM               ││
│ │ Confirmed revised clause 5 language is         ││
│ │ acceptable. Will send signed copy by Friday.   ││
│ └────────────────────────────────────────────────┘│
│ ┌────────────────────────────────────────────────┐│
│ │ 🟣 ✉ Jane Lee → Doug Bower, Bob Smith +3      ││
│ │         Today, Feb 21 - 10:02 AM               ││
│ │ Flagged two concerns with liability cap        ││
│ │ wording. Suggested alternative language for    ││
│ │ section 3.                                     ││
│ └────────────────────────────────────────────────┘│
│ ┌────────────────────────────────────────────────┐│
│ │ 🟢 📞 Doug Bower → Bob Smith                   ││
│ │         Today, Feb 21 - 9:45 AM                ││
│ │ Walked through each clause revision. Bob       ││
│ │ agreed on all points except insurance rider.   ││
│ └────────────────────────────────────────────────┘│
│ ┌────────────────────────────────────────────────┐│
│ │ 🟢 ✉ Doug Bower → Bob Smith, Jane Lee          ││
│ │         Yesterday, Feb 20 - 3:00 PM            ││
│ │ Sent revised clause 5 language with updated    ││
│ │ liability cap at $500K per the discussion.     ││
│ └────────────────────────────────────────────────┘│
│                    ⋮                              │
└──────────────────────────────────────────────────┘
```

**Header area (2 lines):**

- **Line 1:** Type icon (💬 for standard) + Conversation subject (bold, prominent)
- **Line 2:** System status badge + AI status badge + communication count + channel breakdown as compact icons with counts (✉8 💬2 📞2)

The header is deliberately minimal — two lines — to maximize the space available for timeline entries.

**Timeline entries:**

Each entry renders as a compact summary card with participant color coding:

- **Identity line:** Colored contact circle + channel icon + sender display name + "→" + recipient name(s) (truncated with "+N" for overflow). Timestamp on a second line, right-aligned or below the names.
- **Summary text:** The Communication's Published Summary (summary_html rendered as text in the preview context), flowing naturally below the identity line

Timeline entries flow from most-recent-first. Content fills all available space — no artificial limit on the number of entries visible. If the conversation has more entries than fit in the available space, the card scrolls.

**Participant color coding:**

Each participant's summary entries receive a **deterministic background color tint** derived from the participant's contact ID. This enables instant visual scanning of who is speaking as the user scrolls through entries.

- A palette of 8–10 distinguishable but subtle background tints is used. Tints must be light enough that summary text remains highly readable.
- The account owner (current user) always receives a **fixed, recognizable tint** (e.g., a consistent light blue) that does not vary by conversation. This lets the user instantly spot their own contributions.
- All other participants receive colors assigned deterministically from their contact ID, ensuring the same person always has the same color across all conversations.
- Adjacent entries from the same participant use the same color. Adjacent entries from different participants use different colors, creating a visual "stripe" pattern that makes speaker changes obvious at a glance.

**No additional sections:** The Preview Card does not include AI intelligence, action items, key topics, participants list, or entity associations. All CRM intelligence lives in the full View.

### 4.3 Aggregate Conversation Preview

```
┌──────────────────────────────────────────────────┐
│  📂 Lease Negotiation                             │
│     Active · Open · 5 conversations               │
│                                                   │
│ ┌────────────────────────────────────────────────┐│
│ │ 💬 With Lawyer (Smith & Associates)            ││
│ │    Active · 8 communications                   ││
│ │    Last: ✉ Jane Smith                          ││
│ │    Today, Feb 21 - 10:15 AM                    ││
│ │    Clause 5 revisions look acceptable...       ││
│ └────────────────────────────────────────────────┘│
│ ┌────────────────────────────────────────────────┐│
│ │ 💬 With Accountant (PKF)                       ││
│ │    Active · 5 communications                   ││
│ │    Last: ✉ Alice Wong                          ││
│ │    Yesterday, Feb 20 - 3:00 PM                 ││
│ │    Tax implications of the proposed structure..││
│ └────────────────────────────────────────────────┘│
│ ┌────────────────────────────────────────────────┐│
│ │ 💬 Internal Discussion                         ││
│ │    Stale · 12 communications                   ││
│ │    Last: ✉ Doug Bower · Feb 12 - 8:00 AM      ││
│ │    Circled back on the insurance rider...      ││
│ └────────────────────────────────────────────────┘│
│                                                   │
│  ── Direct Communications (3) ──────────────────  │
│ ┌────────────────────────────────────────────────┐│
│ │ ✉ Bob Smith · Tue Feb 18 - 9:00 AM            ││
│ │ Initial lease terms proposal for review.       ││
│ └────────────────────────────────────────────────┘│
│                    ⋮                              │
└──────────────────────────────────────────────────┘
```

**Header area (2 lines):**

- **Line 1:** Type icon (📂 for aggregate) + Conversation subject (bold, prominent)
- **Line 2:** System status badge + AI status badge + child conversation count

**Child conversation entries:**

Each child Conversation renders as a compact entry, sorted by last activity descending:

- **Subject line:** Type icon (💬 or 📂 for nested aggregates) + child Conversation subject. Nested aggregates render identically to standard child conversations — no special treatment.
- **Status line:** System status badge + communication count
- **Most recent activity:** Channel icon + sender name + timestamp + summary text from the most recent Communication's Published Summary

**Direct Communications group:**

If the aggregate has direct Communications (communications assigned to the aggregate itself, not to any child), they render as a separate group at the bottom of the Preview Card, below all child conversation entries. The group header reads "Direct Communications (N)" where N is the count.

Direct Communications within this group are sorted by receive date (most recent first) and render using the same compact summary entry format as standard Conversation Preview entries, including participant color coding.

### 4.4 Preview Card Rendering Rules Summary

| Rule | Standard | Aggregate |
|---|---|---|
| **Header** | 2 lines: icon + subject / statuses + count + channels | 2 lines: icon + subject / statuses + child count |
| **Primary content** | Published Summary entries, most-recent-first | Child Conversations sorted by last activity desc |
| **Entry format** | Channel icon + sender + timestamp + summary text | Subject + status + count + most recent summary |
| **Direct Communications** | N/A | Separate group at bottom, sorted by receive date |
| **Color coding** | Background tint per participant | N/A for child entries; applied to Direct Communications entries |
| **Scrolling** | Scrolls if content exceeds available space | Scrolls if content exceeds available space |
| **Truncation** | No artificial truncation | No artificial truncation |
| **Timeline order** | Always most-recent-first | Always most-recent-activity-first |
| **AI intelligence** | Not shown | Not shown |
| **Interactive elements** | None (Preview Card is read-only per GUI Preview Card Amendment) | None |

**Tasks:**

- [ ] CNVP-01: Implement standard Conversation Preview Card with header and timeline entries
- [ ] CNVP-02: Implement aggregate Conversation Preview Card with child conversation entries
- [ ] CNVP-03: Implement aggregate Direct Communications group at bottom
- [ ] CNVP-04: Implement participant color coding system (8–10 palette, deterministic from contact ID)
- [ ] CNVP-05: Implement fixed account owner color tint
- [ ] CNVP-06: Implement Date & Time Display Standards (GUI FR PRD Section 2.3) for all timestamps
- [ ] CNVP-07: Preview Card renders within 200ms of focus change

**Tests:**

- [ ] CNVP-T01: Standard Preview Card shows header with subject, statuses, count, and channel breakdown
- [ ] CNVP-T02: Standard Preview Card shows Published Summary entries most-recent-first
- [ ] CNVP-T03: Each timeline entry shows channel icon, sender name, timestamp, and summary text
- [ ] CNVP-T04: Participant color coding assigns deterministic colors from contact ID
- [ ] CNVP-T05: Account owner entries always use fixed color tint
- [ ] CNVP-T06: Adjacent entries from different participants have visually distinct background tints
- [ ] CNVP-T07: Aggregate Preview Card shows child conversations sorted by last activity descending
- [ ] CNVP-T08: Each child entry shows subject, status, count, and most recent summary
- [ ] CNVP-T09: Aggregate Direct Communications render as separate bottom group
- [ ] CNVP-T10: Nested aggregate children render identically to standard children
- [ ] CNVP-T11: Timestamps format correctly per Date & Time Display Standards (5 tiers)
- [ ] CNVP-T12: Preview Card scrolls when content exceeds available space
- [ ] CNVP-T13: Preview Card shows no AI intelligence, action items, or entity associations

---

## 5. Full View — Responsive Layout

**Supports processes:** KP-2 (step 1), KP-3 (step 1)

### 5.1 Layout Logic

The Conversation full View uses a **content-aware dynamic layout** that determines single-column or two-column arrangement based on container width. Unlike the Communication full View (which uses a two-condition test including CRM card count), the Conversation full View **always activates two-column layout when the container meets the minimum width threshold**. The card-count condition is dropped because the Participants Card — essential reference material while reading a multi-participant conversation — should always be visible alongside the timeline when screen real estate permits.

**Two-column activation:**

Two-column layout activates when the container width is **≥ 700px**. Below this threshold, single-column layout is used.

This applies equally regardless of Window Type:

- **Docked Window** — Container width is the Detail Panel width (determined by the Splitter Bar position).
- **Modal Full Overlay** — Container width is the full Content Panel. On a 4K 27" display this is typically 1400–1800px, so the width condition is almost always met.
- **Undocked Window** — Container width is whatever the user has sized the window to.

### 5.2 Dynamic Column Sizing

When two-column layout is active, the column widths are determined dynamically based on actual CRM card content volume, not a fixed ratio. The right column (CRM layer) claims what it needs, and the left column (timeline) gets the remainder.

**Column constraints:**

| Constraint | Value | Rationale |
|---|---|---|
| Left column (timeline) minimum | 40% of container width | Ensures summary text is readable without excessive line wrapping |
| Right column (CRM) minimum | 280px | Participant names, summary text, entity names need this minimum to not look cramped |
| Right column (CRM) maximum | 60% of container width | Implied by left column minimum; prevents CRM sidebar from dominating |

**Sizing algorithm:**

1. The right column calculates its **ideal width** based on actual content: longest participant name line, AI summary text length, entity association names, action item text, notes content.
2. The right column claims its ideal width, **clamped** between 280px minimum and 60% of container width maximum.
3. The left column (timeline) receives the remaining width.
4. If the container cannot satisfy both the left column 40% minimum and the right column 280px minimum simultaneously, the layout falls back to **single-column**.

**Minimum two-column container width:** The exact minimum depends on the 40% left / 280px right constraint. At 700px: left = 420px (60%), right = 280px (40%). Both constraints are satisfied, and 420px provides readable timeline text.

**Re-evaluation:** The layout re-evaluates whenever the container width changes (Splitter Bar dragged, Undocked Window resized, browser window resized) or when CRM card content changes (e.g., AI summary populates after initial load). The transition between layouts should be smooth — no jarring content reflow.

### 5.3 Single-Column Layout

```
┌──────────────────────────────────────────────────────┐
│  Window Header (Maximize / Undock / Close)             │
├──────────────────────────────────────────────────────┤
│  Identity Card                                         │
├──────────────────────────────────────────────────────┤
│  Timeline Card (Published Summary entries)             │
│  ┌──────────────────────────────────────────────────┐ │
│  │  🔵 ✉ Bob Smith → Doug Bower                    │ │
│  │  Today, Feb 21 - 10:15 AM                        │ │
│  │  Confirmed revised clause 5 language...          │ │
│  │                                                   │ │
│  │  🟣 ✉ Jane Lee → Doug Bower, Bob Smith +3       │ │
│  │  Today, Feb 21 - 10:02 AM                        │ │
│  │  Flagged two concerns with liability cap...      │ │
│  │                                                   │ │
│  │  ⋮ (scrollable)                                  │ │
│  └──────────────────────────────────────────────────┘ │
├──────────────────────────────────────────────────────┤
│  Participants Card                                     │
├──────────────────────────────────────────────────────┤
│  AI Intelligence Card                                  │
├──────────────────────────────────────────────────────┤
│  Entity Associations Card                              │
├──────────────────────────────────────────────────────┤
│  [Children Card — aggregates only]                     │
├──────────────────────────────────────────────────────┤
│  [Notes Card — if notes attached]                      │
├──────────────────────────────────────────────────────┤
│  [Metadata Card — always present, collapsed default]   │
└──────────────────────────────────────────────────────┘
```

In single-column layout, the timeline appears first (below the Identity Card) because the content is always more important than the CRM context. CRM cards follow the timeline in the standard ordering.

### 5.4 Two-Column Layout

```
┌────────────────────────────────────────────────────────────────────┐
│  Window Header (Maximize / Undock / Close)                          │
├────────────────────────────────────────────────────────────────────┤
│  Identity Card (full width)                                         │
├──────────────────────────────┬─────────────────────────────────────┤
│  Timeline Card (dynamic %)   │  Participants Card                   │
│  ┌──────────────────────────┐│  ┌─────────────────────────────────┐│
│  │ 🔵 ✉ Bob Smith → Doug   ││  │  (derived participant list)     ││
│  │ Today, Feb 21 - 10:15 AM││  └─────────────────────────────────┘│
│  │ Confirmed revised...    ││  AI Intelligence Card                │
│  │                          ││  ┌─────────────────────────────────┐│
│  │ 🟣 ✉ Jane Lee → Doug +3 ││  │  (AI summary, action items,    ││
│  │ Today, Feb 21 - 10:02 AM││  │   key topics)                  ││
│  │ Flagged two concerns... ││  └─────────────────────────────────┘│
│  │                          ││  Entity Associations Card            │
│  │ 🟢 📞 Doug → Bob Smith  ││  ┌─────────────────────────────────┐│
│  │ Today, Feb 21 - 9:45 AM ││  │  (projects, companies, etc.)   ││
│  │ Walked through each...  ││  └─────────────────────────────────┘│
│  │                          ││  [Children Card]                     │
│  │  ⋮ (scrollable)         ││  [Notes Card]                        │
│  └──────────────────────────┘│  [Metadata Card]                     │
├──────────────────────────────┴─────────────────────────────────────┤
```

In two-column layout, the left and right columns **scroll independently**. The user can scroll through a long conversation timeline without losing the CRM context visible in the right column.

**Column visual treatment:** The two columns should feel like distinct zones — the conversation timeline (left) and the CRM intelligence sidebar (right). The right column has a subtle background tint and a left border to create a sidebar feel, visually separating CRM context from the timeline reading surface. The left column (Timeline Card) has no background treatment — it should feel like reading a conversation, not like a CRM panel.

### 5.5 User-Adjustable Column Split

The user can **drag a splitter** between the timeline and CRM columns to override the system-calculated width. The override position persists **per-conversation** — if the user adjusts the split for a specific conversation, that position is saved and always used when viewing that conversation again.

**Logic order:**

1. If a stored splitter position exists for this conversation, use it.
2. If no stored position exists, calculate the optimal split from content analysis (Section 5.2 algorithm).
3. Once the user drags the splitter, save the new position against the conversation ID.

The stored position is subject to the same constraints — left column minimum 40%, right column minimum 280px. If a container resize makes the stored position invalid (e.g., the user saved a 70/30 split on a Modal Full Overlay, then views the same conversation in a narrower Docked Window), the system clamps to the nearest valid position.

**Tasks:**

- [ ] CNVL-01: Implement two-column activation at ≥ 700px container width (no card-count condition)
- [ ] CNVL-02: Implement dynamic column sizing (right column claims ideal width, clamped between 280px and 60%)
- [ ] CNVL-03: Implement single-column fallback layout
- [ ] CNVL-04: Implement two-column layout with independent scrolling
- [ ] CNVL-05: Layout re-evaluates on container resize and CRM content changes
- [ ] CNVL-06: Implement CRM column visual treatment (subtle background tint + left border)
- [ ] CNVL-07: Implement user-draggable splitter between timeline and CRM columns
- [ ] CNVL-08: Persist splitter position per-conversation
- [ ] CNVL-09: Load stored splitter position when viewing a conversation with a saved override

**Tests:**

- [ ] CNVL-T01: Container 1200px wide → two-column with dynamic sizing
- [ ] CNVL-T02: Container 500px wide → single-column
- [ ] CNVL-T03: Container 700px wide → two-column (minimum threshold met)
- [ ] CNVL-T04: Container 699px wide → single-column (just under threshold)
- [ ] CNVL-T05: Right column with minimal content (2 participants, no AI) claims narrow width
- [ ] CNVL-T06: Right column with heavy content (20 participants, full AI) claims wider width up to 60%
- [ ] CNVL-T07: Left column never shrinks below 40% of container
- [ ] CNVL-T08: Resizing container transitions smoothly between layouts
- [ ] CNVL-T09: Two-column layout columns scroll independently
- [ ] CNVL-T10: Layout re-evaluates when AI summary populates after initial load
- [ ] CNVL-T11: Two-column layout right column has distinct background tint and left border
- [ ] CNVL-T12: User can drag splitter to adjust column widths
- [ ] CNVL-T13: Dragged splitter position persists for that conversation across sessions
- [ ] CNVL-T14: Conversation with stored splitter position loads with that position
- [ ] CNVL-T15: Conversation without stored splitter position uses dynamic calculation
- [ ] CNVL-T16: Stored position clamps to valid range when container is smaller than original

---

## 6. Full View — Identity Card

**Supports processes:** KP-2 (step 2), KP-3 (step 2)

The Conversation Identity Card renders at the top of the full View, above the Timeline Card and CRM layer. It provides a compact identifying header consistent with the Identity Card pattern used by all entity types.

### 6.1 Conversation Identity Card Rendering

```
┌───────────────────────────────────────────────────────────────┐
│  💬 Lease Negotiation with Acme Corp                          │
│     Active · Open · 12 communications · ✉8 💬2 📞2           │
└───────────────────────────────────────────────────────────────┘
```

**Aggregate variant:**

```
┌───────────────────────────────────────────────────────────────┐
│  📂 Lease Negotiation                                         │
│     Active · Open · 5 conversations · 40 communications       │
└───────────────────────────────────────────────────────────────┘
```

**Fields displayed:**

| Element | Source | Rendering |
|---|---|---|
| Type icon | is_aggregate | 💬 for standard, 📂 for aggregate |
| Subject | subject field | Bold, prominent. Primary heading. |
| System status | system_status | Badge: "Active", "Stale", "Closed" |
| AI status | ai_status | Badge: "Open", "Closed", "Uncertain". Omitted if NULL (AI not yet processed). |
| Communication count | communication_count | "N communications" — for aggregates, this is the recursive rolled-up count. |
| Child count | Derived from membership | Aggregates only: "N conversations" shown before communication count. |
| Channel breakdown | channel_breakdown | Compact channel icons with counts (✉8 💬2 📞2). Omitted if single channel. |
| Description | description field | If non-NULL, rendered as a third line below the status line. Lighter text. |

**Fields deliberately excluded from the Identity Card:**

| Field | Reason | Where it lives instead |
|---|---|---|
| AI Summary | Too long for Identity Card; warrants its own card | AI Intelligence Card |
| AI Action Items | Structured data requiring its own rendering | AI Intelligence Card |
| Participants | Derived list, potentially long | Participants Card |
| Entity associations | Relationship data | Entity Associations Card |
| Stale/closed thresholds | Configuration detail | Metadata Card |

**Tasks:**

- [ ] CNVI-01: Implement Conversation Identity Card with type icon, subject, statuses, and counts
- [ ] CNVI-02: Implement aggregate variant with child count and rolled-up communication count
- [ ] CNVI-03: Implement optional description line
- [ ] CNVI-04: Implement channel breakdown display (suppressed for single-channel conversations)

**Tests:**

- [ ] CNVI-T01: Standard Conversation shows 💬 icon, subject, statuses, communication count, channel breakdown
- [ ] CNVI-T02: Aggregate Conversation shows 📂 icon, subject, statuses, child count, communication count
- [ ] CNVI-T03: AI status badge omitted when ai_status is NULL
- [ ] CNVI-T04: Channel breakdown omitted for single-channel conversations
- [ ] CNVI-T05: Description line renders when non-NULL
- [ ] CNVI-T06: Identity Card renders within Identity Card fixed area (no scrolling)

---

## 7. Full View — Timeline Card

**Supports processes:** KP-2 (step 2, step 4), KP-3 (step 3)

The Timeline Card is the primary content surface in the Conversation full View. It presents the conversation as a chronological sequence of Published Summary entries — the user reads through the conversation history, seeing each communication's distilled contribution.

### 7.1 Timeline Order

The timeline respects a **global user preference** for reading order:

| Setting | Behavior | Use Case |
|---|---|---|
| Oldest-first (default) | First communication at top, most recent at bottom | Reads like a natural narrative |
| Newest-first | Most recent communication at top, oldest at bottom | Jump to latest activity in long conversations |

The preference is stored as a user-level setting (not per-conversation). An **inline toggle button** on the Timeline Card header allows temporary reversal without changing the global preference. The toggle resets when the user navigates away.

### 7.2 Timeline Entry Rendering

Each Communication in the Conversation renders as a summary entry with prominent sender identification and full summary content:

```
┌────────────────────────────────────────────────────────────────┐
│  🔵 ✉ Bob Smith → Doug Bower        Today, Feb 21 - 10:15 AM │
│                                                    [View Original]
│  Confirmed the revised clause 5 language is acceptable after    │
│  consulting with legal. Will send signed copy by Friday.        │
│  Key concern resolved: liability cap at $500K approved.         │
└────────────────────────────────────────────────────────────────┘
```

**Identity line:**

- **Colored contact circle** (left-most element) — filled circle in the sender's deterministic participant color, providing instant visual identification of who is speaking
- **Channel icon** (✉ email, 💬 SMS, 📞 phone, 🎥 video, 👥 in-person)
- **Sender display name** — large, bold font. Clickable link to Contact record if resolved. For directional channels (email, SMS), followed by "→" and the primary recipient display name. For multi-party channels (calls, meetings), followed by "→" and participant names (comma-separated, truncated with "+N" for overflow)
- **Timestamp** (right-aligned) — same-sized font as the sender name, per GUI FR PRD Section 2.3 Date & Time Display Standards
- **"View Original" link** (right-aligned, below timestamp) — navigates to the Communication's full record (Communication View Sub-PRD)

**Summary content:**

- The Communication's Published Summary (summary_html) rendered as formatted HTML preserving bold, italic, links, and lists
- Content flows naturally below the identity line with no artificial truncation
- If the summary is long, the entry expands to accommodate it — the full summary_html is always rendered

**Participant color coding:**

Timeline entries use the same deterministic participant color coding as the Preview Card (Section 4.2). Each entry receives a subtle background tint based on the sender's contact ID, with the account owner always receiving a fixed recognizable tint. This makes speaker changes visually obvious when scanning the timeline.

### 7.3 Timeline Entry — Attachment Indicator

If the Communication has attachments (has_attachments = true), a compact attachment indicator renders below the summary content: paperclip icon followed by the count ("📎 3 attachments"). Attachments are not downloadable from the timeline — the user navigates to the full Communication record for attachment actions.

### 7.4 Timeline Entry — Segment Indicator

If the Communication's presence in this Conversation is via a Segment (the communication's primary conversation is elsewhere, but a portion of its content was segmented into this conversation), a subtle indicator marks the entry: "Segment from [primary conversation subject]" with a navigable link.

### 7.5 Suppression

The Timeline Card is never suppressed — it always renders, even if the Conversation has zero Communications (showing an empty state: "No communications in this conversation yet").

**Tasks:**

- [ ] CNVT-01: Implement Timeline Card with chronological Published Summary entries
- [ ] CNVT-02: Implement user preference for timeline order (oldest-first, newest-first)
- [ ] CNVT-03: Implement inline toggle for temporary order reversal
- [ ] CNVT-04: Implement timeline entry rendering (colored circle, channel icon, sender → recipient, timestamp, summary, View Original)
- [ ] CNVT-05: Implement participant color coding on timeline entries (colored circle + background tint)
- [ ] CNVT-06: Implement attachment indicator on timeline entries
- [ ] CNVT-07: Implement segment indicator with navigation link
- [ ] CNVT-08: Implement empty state for conversations with zero communications
- [ ] CNVT-09: Implement sender name as clickable link to Contact record
- [ ] CNVT-10: Implement sender → recipient display with overflow truncation (+N)

**Tests:**

- [ ] CNVT-T01: Timeline renders entries in oldest-first order when user preference is oldest-first
- [ ] CNVT-T02: Timeline renders entries in newest-first order when user preference is newest-first
- [ ] CNVT-T03: Inline toggle reverses order temporarily without changing global preference
- [ ] CNVT-T04: Toggle resets when navigating away and returning
- [ ] CNVT-T05: Each entry shows colored circle, channel icon, sender → recipient, timestamp, and summary content
- [ ] CNVT-T06: Timestamps follow Date & Time Display Standards (5 tiers)
- [ ] CNVT-T07: "View Original" link navigates to Communication full record
- [ ] CNVT-T08: Participant color coding matches Preview Card colors for the same contacts
- [ ] CNVT-T09: Account owner entries use fixed color tint
- [ ] CNVT-T10: Attachment indicator shows for communications with attachments
- [ ] CNVT-T11: Segment indicator shows with link to primary conversation
- [ ] CNVT-T12: Empty conversation shows appropriate empty state
- [ ] CNVT-T13: Sender name links to Contact record when resolved
- [ ] CNVT-T14: Recipient overflow truncates with "+N" count
- [ ] CNVT-T15: Summary content renders full summary_html with formatting preserved

---

## 8. Full View — Participants Card

**Supports processes:** KP-2 (step 3, step 4)

### 8.1 Purpose

The Participants Card shows all participants in the Conversation — derived from the union of Communication Participants across all Communications. While each timeline entry shows its sender, the Participants Card provides the complete roster: every person involved across the entire conversation, with CRM context (company, title) and a per-participant communication count.

### 8.2 Rendering

```
┌──────────────────────────────────────────────────────┐
│  Participants (8)                                     │
│──────────────────────────────────────────────────────│
│  Doug Bower                    6 communications       │
│  Owner · CRMExtender                       (You)     │
│                                                       │
│  Bob Smith                     5 communications       │
│  VP Engineering · Acme Corp                           │
│                                                       │
│  Jane Lee                      3 communications       │
│  Legal Counsel · Acme Corp                            │
│                                                       │
│  Alice Wong                    2 communications       │
│  CFO · Acme Corp                                      │
│                                                       │
│  +4 Others                                            │
└──────────────────────────────────────────────────────┘
```

| Element | Source | Rendering |
|---|---|---|
| Card header | "Participants" with count in parentheses | Standard card header |
| Name | Contact display name | Clickable link to Contact record (if resolved). Bold. |
| Communication count | Count of Communications in this Conversation where this contact is a participant | Right-aligned on the name line. Provides a sense of each person's involvement level. |
| Title + Company | Contact's current employment | Below the name in lighter text. Omitted if no employment record. |
| Account owner indicator | Derived from current user | "(You)" badge if this participant is the account owner. |
| Color swatch | Participant color from palette | Small color indicator matching the timeline entry background tint for this participant, enabling visual cross-reference. |

**Participant ordering:** Participants are ordered by communication count descending (most active participants first). The account owner is always listed first regardless of count.

**Overflow:** If the conversation has many participants (> 6), the card shows the top participants and a "+N Others" expandable link. Clicking expands to show the full list.

### 8.3 Explicitly Associated Contacts

Contacts linked to the Conversation via the `conversation_contacts` Relation Type (explicit association) who are NOT derived participants are **not shown** in the Participants Card. They appear in the Entity Associations Card (Section 10) under a dedicated "Contacts" group. This separation prevents confusion between people who actually communicated in the conversation and people who are associated for other reasons (e.g., stakeholders, decision-makers, managers who should be informed).

### 8.4 Suppression

The Participants Card is suppressed only if the Conversation has zero Communications AND zero explicit contact associations — which represents a newly created, empty Conversation.

**Tasks:**

- [ ] CNVP-01: Implement Participants Card with derived participant roster
- [ ] CNVP-02: Implement per-participant communication count
- [ ] CNVP-03: Implement participant ordering (account owner first, then by count descending)
- [ ] CNVP-04: Implement overflow with "+N Others" expandable link
- [ ] CNVP-05: Implement color swatch matching timeline entry colors
- [ ] CNVP-06: Implement Contact record navigation from participant name

**Tests:**

- [ ] CNVP-T01: Participants Card shows all derived participants with names, titles, companies
- [ ] CNVP-T02: Communication count per participant is accurate
- [ ] CNVP-T03: Account owner listed first with "(You)" badge
- [ ] CNVP-T04: Participants ordered by communication count descending after account owner
- [ ] CNVP-T05: Overflow at > 6 participants shows "+N Others" link
- [ ] CNVP-T06: Expanding "+N Others" shows full participant list
- [ ] CNVP-T07: Color swatch matches timeline entry background tint
- [ ] CNVP-T08: Explicitly associated contacts do NOT appear in Participants Card (shown in Entity Associations Card)
- [ ] CNVP-T09: Participant names link to Contact records
- [ ] CNVP-T10: Participants Card suppressed for empty Conversation with no associations

---

## 9. Full View — AI Intelligence Card

**Supports processes:** KP-2 (step 3), KP-3 (step 4)

### 9.1 Purpose

The AI Intelligence Card displays the Conversation-level AI analysis: a synthesized summary across all Communications, extracted action items, key topics, and status classification with confidence. This is a higher-order synthesis — the Conversation AI summary consumes the individual Communication Published Summaries as input, producing a narrative of the overall conversation state.

### 9.2 Visual Distinction

The AI Intelligence Card carries the same subtle tinted background and border treatment as the Communication Summary Card — a light tint (e.g., light blue) signaling "this is AI-generated intelligence." This helps the user's eye find the AI analysis quickly among the CRM cards.

### 9.3 Rendering

```
┌──────────────────────────────────────────────────────┐
│  AI Intelligence               🤖 AI Generated  ✏ ↻  │
│──────────────────────────────────────────────────────│
│                                                       │
│  Summary:                                             │
│  Active lease negotiation with Acme Corp. Clause 5    │
│  liability cap agreed at $500K. Insurance rider       │
│  remains under discussion. Bob Smith is primary       │
│  counterparty; Jane Lee handles legal review.         │
│                                                       │
│  Action Items:                                        │
│  · Bob Smith: Send signed contract by Friday          │
│  · Doug Bower: Follow up on insurance clause          │
│  · Jane Lee: Review indemnification section           │
│                                                       │
│  Key Topics:                                          │
│  liability cap · clause 5 · insurance rider ·         │
│  indemnification                                      │
│                                                       │
│  Confidence: 0.92 · Last processed: Today, Feb 21    │
└──────────────────────────────────────────────────────┘
```

| Element | Source | Rendering |
|---|---|---|
| Card header | "AI Intelligence" | Standard card header with tinted background |
| Source badge | — | "🤖 AI Generated" — always AI for conversation-level summaries |
| Edit action | — | Pencil icon (✏). Opens AI summary in rich text editor for manual editing. |
| Regenerate action | — | Refresh icon (↻). Re-triggers AI analysis across all Communications. |
| Summary | ai_summary | Rendered as formatted text. 2–4 sentence narrative of conversation state. |
| Action Items | ai_action_items | Rendered as a **read-only** list with assignee names (clickable links to Contact records) and deadlines if present. Action items are not completable from this card — completion is managed through the Task workflow. |
| Key Topics | ai_key_topics | Rendered as inline tags/chips separated by middot or as a flowing list. |
| Confidence | ai_confidence | Decimal displayed with "Confidence:" label. |
| Last processed | ai_last_processed_at | Timestamp per Date & Time Display Standards. |

### 9.4 Suppression

The AI Intelligence Card is suppressed if all AI fields are NULL (ai_summary, ai_action_items, ai_key_topics all NULL). This occurs for new Conversations that have not yet been processed by AI, or Conversations containing only triaged Communications.

### 9.5 Edit and Regenerate Workflows

**Edit:** Same pattern as Communication Summary Card. Edit icon transitions to rich text editor. Save creates updated ai_summary.

**Regenerate:** Refresh icon re-triggers the Conversation-level AI analysis pipeline. Loading state displays while processing. On completion, all AI fields update.

Both workflows are defined in detail in the AI Intelligence & Review Sub-PRD. This section defines only the UI trigger points.

**Tasks:**

- [ ] CNVA-01: Implement AI Intelligence Card with summary, action items, key topics
- [ ] CNVA-02: Implement AI card visual distinction (tinted background and border)
- [ ] CNVA-03: Implement action item rendering with assignee links
- [ ] CNVA-04: Implement key topics rendering as inline tags
- [ ] CNVA-05: Implement edit action (transition to rich text editor)
- [ ] CNVA-06: Implement regenerate action with loading state
- [ ] CNVA-07: Implement confidence and last processed display

**Tests:**

- [ ] CNVA-T01: AI Intelligence Card renders summary, action items, and key topics
- [ ] CNVA-T02: Card has visually distinct tinted background
- [ ] CNVA-T03: Action item assignee names link to Contact records
- [ ] CNVA-T04: Edit action opens rich text editor with current summary
- [ ] CNVA-T05: Regenerate action triggers AI pipeline and updates card on completion
- [ ] CNVA-T06: Card suppressed when all AI fields are NULL
- [ ] CNVA-T07: Confidence and last processed timestamp display correctly

---

## 10. Full View — Entity Associations Card

**Supports processes:** KP-2 (step 3, step 4)

### 10.1 Purpose

The Entity Associations Card shows all entities linked to this Conversation via Relation Types: Projects, Companies, Contacts (explicit), and Events. This provides the organizational context — which business initiatives, organizations, and events this conversation relates to.

### 10.2 Rendering

```
┌──────────────────────────────────────────────────────┐
│  Associations                              [+ Link]   │
│──────────────────────────────────────────────────────│
│  Projects:                                            │
│  📋 2026 Expansion · Active                           │
│  📋 Legal Review Q1 · Active                          │
│                                                       │
│  Companies:                                           │
│  🏢 Acme Corp                                         │
│  🏢 Smith & Associates LLP                            │
│                                                       │
│  Contacts:                                            │
│  👤 Mike Johnson · Decision Maker                     │
│     Regional VP · Acme Corp                           │
│                                                       │
│  Events:                                              │
│  📅 Lease Review Meeting · Feb 18, 2026               │
└──────────────────────────────────────────────────────┘
```

| Element | Source | Rendering |
|---|---|---|
| Card header | "Associations" with "+ Link" action | Standard card header. "+ Link" opens an entity picker for adding new associations. |
| Projects | `conversation_projects` Relation Type | Project name (clickable link) + status. Grouped under "Projects:" header. |
| Companies | `conversation_companies` Relation Type | Company name (clickable link). Grouped under "Companies:" header. |
| Contacts (explicit) | `conversation_contacts` Relation Type | Contact name (clickable link) + title + company. Grouped under "Contacts:" header. These are contacts explicitly associated with the conversation who are NOT derived participants — stakeholders, decision-makers, managers who should be informed. Shown here rather than in the Participants Card to prevent confusion with people who actually communicated. |
| Events | `conversation_events` Relation Type | Event title (clickable link) + date. Grouped under "Events:" header. |

Each association group is only rendered if it has at least one entry. Empty groups are omitted (no "Projects: None" placeholder).

### 10.3 Suppression

The Entity Associations Card is suppressed when the Conversation has zero Relation Type instances across all association types (no Projects, Companies, explicitly associated Contacts, or Events linked).

**Tasks:**

- [ ] CNVE-01: Implement Entity Associations Card with grouped association types
- [ ] CNVE-02: Implement "+ Link" action with entity picker
- [ ] CNVE-03: Implement entity name navigation links
- [ ] CNVE-04: Implement remove association action (per association)

**Tests:**

- [ ] CNVE-T01: Card renders Projects, Companies, Contacts, and Events in grouped sections
- [ ] CNVE-T02: Empty association groups are omitted
- [ ] CNVE-T03: Entity names link to their respective records
- [ ] CNVE-T04: "+ Link" action opens entity picker for adding associations
- [ ] CNVE-T05: Card suppressed when no associations exist
- [ ] CNVE-T06: Explicit Contact associations show name, title, and company
- [ ] CNVE-T07: Explicit Contact associations do NOT include derived participants (only non-participant contacts)

---

## 11. Full View — Children Card

**Supports processes:** KP-3 (step 2)

### 11.1 Purpose

The Children Card appears only for aggregate Conversations (is_aggregate = true). It lists all child Conversations with navigation links, providing the structural overview of what threads this aggregate organizes.

### 11.2 Rendering

```
┌──────────────────────────────────────────────────────┐
│  Conversations (5)                         [+ Add]    │
│──────────────────────────────────────────────────────│
│  💬 With Lawyer (Smith & Associates)       → Open     │
│     Active · 8 comms · Last: Today, Feb 21           │
│                                                       │
│  💬 With Accountant (PKF)                  → Open     │
│     Active · 5 comms · Last: Yesterday, Feb 20       │
│                                                       │
│  💬 Internal Discussion                    → Open     │
│     Stale · 12 comms · Last: Feb 12                  │
│                                                       │
│  📂 Sub-negotiations                       → Open     │
│     Active · 2 conversations · 15 comms              │
│                                                       │
│  💬 With Insurance Broker                  → Open     │
│     Active · 3 comms · Last: Tue Feb 18              │
└──────────────────────────────────────────────────────┘
```

| Element | Source | Rendering |
|---|---|---|
| Card header | "Conversations" with count and "+ Add" action | "+ Add" opens a conversation picker to add existing conversations as children, or create a new child. |
| Child entries | conversation_members | Type icon (💬 or 📂), subject (clickable), "→ Open" navigation action |
| Child status | system_status, communication_count, last_activity_at | Status badge, communication count, last activity timestamp |
| Child count | For nested aggregates | "N conversations" shown instead of last activity for aggregate children |

**Ordering:** Children are sorted by last_activity_at descending (most recently active first).

### 11.3 Suppression

The Children Card is suppressed for standard Conversations (is_aggregate = false). For aggregate Conversations, it is always rendered even if there are zero children (showing an empty state with the "+ Add" action).

**Tasks:**

- [ ] CNVC-01: Implement Children Card with child conversation entries
- [ ] CNVC-02: Implement "+ Add" action (conversation picker / create new child)
- [ ] CNVC-03: Implement child navigation ("→ Open" link)
- [ ] CNVC-04: Implement remove child action
- [ ] CNVC-05: Implement empty state for aggregates with no children

**Tests:**

- [ ] CNVC-T01: Children Card renders for aggregate Conversations
- [ ] CNVC-T02: Children Card suppressed for standard Conversations
- [ ] CNVC-T03: Children sorted by last_activity_at descending
- [ ] CNVC-T04: Each child shows type icon, subject, status, count, last activity
- [ ] CNVC-T05: Nested aggregate children show child count instead of last activity
- [ ] CNVC-T06: "→ Open" navigates to child Conversation record
- [ ] CNVC-T07: "+ Add" opens conversation picker
- [ ] CNVC-T08: Empty aggregate shows empty state with "+ Add" action

---

## 12. Full View — Notes Card

**Supports processes:** KP-2 (step 3)

### 12.1 Purpose

The Notes Card displays any notes attached to this Conversation. Notes are supplementary commentary — meeting observations, strategic context, action plans, or other information the user wants to capture alongside the conversation record.

### 12.2 Rendering

Same pattern as the Communication Notes Card:

```
┌──────────────────────────────────────────────────────┐
│  Notes (2)                                    [+ Add] │
│──────────────────────────────────────────────────────│
│  Doug Bower · Today, Feb 21 - 4:30 PM                │
│  Bob seemed hesitant about the pricing — follow       │
│  up with a discount offer next week.                  │
│                                                       │
│  Doug Bower · Yesterday, Feb 20 - 9:15 AM            │
│  Confirmed with legal that our counter-proposal       │
│  on clause 5 is acceptable.                           │
└──────────────────────────────────────────────────────┘
```

| Element | Rendering |
|---|---|
| Card header | "Notes" with count in parentheses. "+ Add" action to create a new note attached to this Conversation. |
| Note entries | Author name, timestamp (per Date & Time Display Standards), and note content preview. Each note is clickable to open the full Note record. |

### 12.3 Suppression

The Notes Card is suppressed when no notes are attached to the Conversation.

**Tasks:**

- [ ] CNVN-01: Implement Notes Card rendering with attached note entries
- [ ] CNVN-02: Implement "+ Add" action for creating a new note
- [ ] CNVN-03: Implement note entry click to open full Note record

**Tests:**

- [ ] CNVN-T01: Notes Card renders attached notes with author, timestamp, content preview
- [ ] CNVN-T02: "+ Add" action creates a new note attached to the Conversation
- [ ] CNVN-T03: Note entry click opens full Note record
- [ ] CNVN-T04: Notes Card suppressed when no notes are attached
- [ ] CNVN-T05: Timestamps follow Date & Time Display Standards

---

## 13. Full View — Metadata Card

**Supports processes:** KP-2 (step 3)

### 13.1 Purpose

The Metadata Card displays system information, lifecycle configuration, and event history for the Conversation. This is operational/diagnostic information that most users rarely need but power users and administrators value.

### 13.2 Rendering

```
┌──────────────────────────────────────────────────────┐
│  Metadata                                      ▾      │
│──────────────────────────────────────────────────────│
│  Type               Standard Conversation             │
│  Created By         Doug Bower                        │
│  Created            Feb 21, 2026 - 10:16 AM           │
│  Last Updated       Today, Feb 21 - 4:30 PM           │
│  First Activity     Jan 15 - 9:00 AM                  │
│  Last Activity      Today, Feb 21 - 10:15 AM          │
│  Stale After        14 days                           │
│  Closed After       30 days                           │
│                                                       │
│  ▸ Event History (12 events)                          │
└──────────────────────────────────────────────────────┘
```

| Element | Source | Rendering |
|---|---|---|
| Type | is_aggregate | "Standard Conversation" or "Aggregate Conversation" |
| Created By | created_by | User display name. "System" for auto-formed Conversations. |
| Created / Updated | created_at, updated_at | Timestamps per Date & Time Display Standards |
| First / Last Activity | first_activity_at, last_activity_at | Timestamps per Date & Time Display Standards |
| Stale After | stale_after_days | "N days" — editable |
| Closed After | closed_after_days | "N days" — editable |
| Event History | conversation_events | Collapsible list of event records. Collapsed by default. When expanded, shows event type, timestamp, changed_by, and change details. |

### 13.3 Default State

The Metadata Card renders **collapsed by default** (showing only the header with a collapse/expand toggle). Users who need the information can expand it. This keeps the default view focused on the conversation timeline and CRM intelligence rather than system internals.

### 13.4 Suppression

The Metadata Card is never suppressed — every Conversation has metadata. But its collapsed default state means it occupies minimal space until needed. The collapsed Metadata Card does **not** count toward any card visibility thresholds.

**Tasks:**

- [ ] CNVM-01: Implement Metadata Card with field rendering
- [ ] CNVM-02: Implement collapsed default state
- [ ] CNVM-03: Implement Event History collapsible section
- [ ] CNVM-04: Implement editable stale_after_days and closed_after_days fields

**Tests:**

- [ ] CNVM-T01: Metadata Card renders all fields correctly
- [ ] CNVM-T02: Metadata Card renders collapsed by default
- [ ] CNVM-T03: Event History expands to show event records
- [ ] CNVM-T04: Stale/closed thresholds are editable
- [ ] CNVM-T05: Timestamps follow Date & Time Display Standards

---

## 14. Card Ordering

### 14.1 Default Card Order — Single Column

In single-column layout, cards render in this order (top to bottom):

1. Identity Card
2. Timeline Card
3. Participants Card
4. AI Intelligence Card
5. Entity Associations Card (conditional)
6. Children Card (aggregates only)
7. Notes Card (conditional)
8. Metadata Card (collapsed by default)

### 14.2 Default Card Order — Two Column

In two-column layout:

**Left column (primary — dynamic width, ≥ 40%):**

1. Timeline Card

**Right column (CRM layer — dynamic width, 280px–60%):**

1. Participants Card
2. AI Intelligence Card
3. Entity Associations Card (conditional)
4. Children Card (aggregates only)
5. Notes Card (conditional)
6. Metadata Card (collapsed by default)

The Identity Card spans full width above both columns.

### 14.3 Ordering Rationale

The order prioritizes the most frequently needed information:

- Timeline first (the conversation history is always the primary interest)
- Participants next (who is involved — the CRM context most needed while reading the timeline)
- AI Intelligence next (distilled understanding — summary, action items, key topics)
- Entity Associations next (organizational context — which projects, companies, events)
- Children next (aggregates only — structural overview of sub-conversations)
- Conditional cards follow (notes — only present when relevant)
- Metadata last (rarely needed, collapsed by default)

---

## 15. User Settings

### 15.1 Timeline Order Preference

| Setting | Values | Default | Scope |
|---|---|---|---|
| Timeline order | Oldest-first, Newest-first | Oldest-first | Global user preference |

This setting controls the default timeline order when opening any Conversation in full View. The Preview Card always uses most-recent-first regardless of this setting.

An inline toggle on the Timeline Card header allows temporary reversal per-session without changing the global preference.

---

## Related Documents

| Document | Relationship |
|---|---|
| [Conversation Entity Base PRD](conversation-entity-base-prd.md) | Parent entity PRD. Defines KP-4 which this document implements. |
| [Conversation Entity TDD](conversation-entity-tdd.md) | Technical decisions for conversation data storage and retrieval. |
| [AI Intelligence & Review Sub-PRD](conversation-ai-intelligence-prd.md) | AI classification, summarization, extraction workflows referenced by the AI Intelligence Card. |
| [GUI Functional Requirements PRD](gui-functional-requirements-prd.md) | Card-Based Architecture, Window Types, Display Modes, Date & Time Display Standards. |
| [GUI Preview Card Amendment](gui-preview-card-amendment.md) | System-wide Preview Card type definition. |
| [Communication Entity Base PRD](communication-entity-base-prd.md) | The atomic communication records that compose the conversation timeline. |
| [Communication Published Summary Sub-PRD](communication-published-summary-prd.md) | Summary content rendered in timeline entries. |
| [Communication View Sub-PRD](communication-view-prd.md) | Full Communication record view navigated to via "View Original" links. |
| [Contact Entity Base PRD](contact-entity-base-prd.md) | Contact record navigation from participant and sender links. |
| [Projects PRD](projects-prd.md) | Project entity referenced in Entity Associations Card. |
| [Notes PRD](notes-prd.md) | Note attachment and creation referenced by the Notes Card. |
| [Permissions & Sharing PRD](permissions-sharing-prd.md) | Access control for conversation records. |
| [Master Glossary](glossary.md) | Term definitions. |
