# Conversation View Implementation

**PRD:** `PRDs/conversation-view-prd.md` (v1.3)
**Date:** 2026-03-16 to 2026-03-17
**Tests:** 217 API tests passing (`tests/test_api.py`)

---

## Overview

Full implementation of the Conversation View feature across 7 phases, delivering:
- Conversation preview card (standard + aggregate)
- Responsive full view with draggable two-column layout
- Identity, timeline, participants, AI intelligence, associations, children, notes, and metadata cards
- Participant color coding system
- Database schema migration (v19 → v20)
- 20 new API tests covering all new fields, children, and associations

---

## Phase 1: API Foundation + Participant Color System

### Database Migration — v19 → v20

**File:** `poc/migrate_to_v20.py`

5 steps:
1. **ALTER TABLE conversations** — adds `is_aggregate INTEGER NOT NULL DEFAULT 0`, `description TEXT`, `stale_after_days INTEGER DEFAULT 14`, `closed_after_days INTEGER DEFAULT 30`, `ai_confidence REAL`
2. **CREATE TABLE conversation_members** — junction table for aggregate parent-child relationships (`parent_id`, `child_id`, `position`, `added_at`)
3. **Rebuild relationship_types** — expands CHECK constraints on `from_entity_type` to include `'conversation'` and `to_entity_type` to include `'conversation'`, `'project'`, `'event'`. Uses `PRAGMA legacy_alter_table = ON` to prevent FK auto-rewrite.
4. **Seed system relationship types** — `rt-conv-project`, `rt-conv-company`, `rt-conv-contact`, `rt-conv-event` with labels like "Related Project", "Related Company", etc.
5. **PRAGMA user_version = 20**

**File:** `poc/database.py` — Schema definitions updated to match v20.

### API Endpoints

**File:** `poc/web/routes/api.py`

- **GET `/api/v1/conversations/{id}/preview`** — Extended with `is_aggregate`, `description`, `children[]` (for aggregates: JOIN conversation_members → conversations with latest_communication subquery)
- **GET `/api/v1/conversations/{id}/full`** — Extended with `is_aggregate`, `description`, `ai_confidence`, `stale_after_days`, `closed_after_days`, `children[]`, `associations{projects, companies, contacts, events}`. Associations query joins `relationships` → `relationship_types` then does per-type lookups.

### TypeScript Types

**File:** `frontend/src/types/api.ts`

New interfaces:
- `ConversationChildPreview` — id, title, status, is_aggregate, communication_count, child_count, last_activity_at, latest_communication
- `ConversationAssociations` — projects[], companies[], contacts[], events[] (each with relationship_id + entity fields)
- Extended `ConversationPreviewData` — added is_aggregate, description, children
- Extended `ConversationFullData` — added is_aggregate, description, ai_confidence, stale_after_days, closed_after_days, children, associations

### React Query Hooks

- **`frontend/src/api/conversationPreview.ts`** — `useConversationPreview(id)` hook fetching from `/conversations/{id}/preview` with 30s stale time
- **`frontend/src/api/conversationFull.ts`** — `useConversationFull(id)` hook fetching from `/conversations/{id}/full` with 30s stale time

### Participant Color System

**File:** `frontend/src/lib/participantColors.ts`

- `buildParticipantColorMap()` — deterministic color assignment from participant addresses
- 10-hue palette (0, 30, 60, 120, 160, 200, 260, 290, 320, 45) with collision avoidance
- Account owner gets fixed hue 220 (blue) via `OWNER_HUE`
- Returns `ParticipantColorMap` with methods: `getHue()`, `getCircleStyle()`, `getRowTint()`, `isAccountOwner()`
- Circle style: saturated background with white text
- Row tint: very faint pastel background for timeline entries

### Shared Utilities

- **`frontend/src/lib/channelIcons.ts`** — Maps channels (email, sms, phone, video, in_person, note) to Lucide icons and display labels
- **`frontend/src/lib/formatTimestamp.ts`** — 5-tier contextual formatting: Today HH:MM, Yesterday HH:MM, day-of-week HH:MM (2-6 days), Mon DD (this year), Mon DD YYYY (older). Also `formatPreviewTimestamp()` for compact preview display.
- **`frontend/src/lib/sanitizeHtml.ts`** — Strips scripts, event handlers, `javascript:` URLs, tracking pixels, `cid:` references from email HTML for safe `dangerouslySetInnerHTML` rendering
- **`frontend/src/components/shared/ChannelBreakdown.tsx`** — Inline component showing channel icon + count pairs for multi-channel conversations

### Tests

**File:** `tests/test_api.py`

- `_seed_conversation()` extended with params: `ai_confidence`, `is_aggregate`, `description`, `stale_after_days`, `closed_after_days`
- **TestConversationViewNewFields** (10 tests) — is_aggregate true/false on preview/full, description, ai_confidence, stale/closed defaults and custom values
- **TestConversationChildren** (4 tests) — aggregate with children preview/full, standard no children, nested aggregate child_count
- **TestConversationAssociations** (6 tests) — empty, project, company, contact, event, multiple types

---

## Phase 2: Preview Card — Standard Conversations

**File:** `frontend/src/components/detail/ConversationPreviewCard.tsx`

- Type icon: `MessageSquare` for standard, `FolderOpen` for aggregate
- Header: title, status badge, description (if present)
- Stats line: communication count, participant count, channel breakdown (suppressed for single-channel)
- AI summary section with "AI Generated" badge (suppressed when null)
- Timeline-first design: recent communications rendered with participant color tinting
- Each timeline entry shows: colored sender circle, channel icon, sender → recipient, timestamp, content (cleaned_html or snippet)
- Attachment indicator with count
- No artificial truncation (no line-clamp)

---

## Phase 3: Preview Card — Aggregate Conversations

**File:** `frontend/src/components/detail/ConversationPreviewCard.tsx` (extended)

- Aggregate header shows child count instead of communication count
- `AggregatePreviewContent` component renders child conversation entries
- `ChildConversationEntry` subcomponent: type icon, title link, status badge, message count, latest communication preview
- "Direct Communications" group at bottom for messages directly on the aggregate
- Click-through navigation to child conversations via navigation store

---

## Phase 4: Full View Layout + Identity Card

### Responsive Two-Column Layout

**File:** `frontend/src/components/fullview/ConversationFullView.tsx`

- `ResizeObserver` tracks container width for responsive breakpoints
- Two-column layout when container ≥ 700px wide and constraints satisfiable:
  - Left column: Timeline (independently scrollable, flex-1)
  - Right column: CRM sidebar cards (independently scrollable, fixed width)
- `clampRightWidth(desired, containerWidth)`: enforces right min 280px, right max 60%, left min 40%. Returns `null` if constraints unsatisfiable → falls back to single-column.
- Draggable splitter with visual feedback (hover/active states)
- Per-conversation splitter width persisted to `localStorage` (`conv-splitter-{id}`)
- Single-column fallback: timeline first, then CRM cards below

### Identity Card

**File:** `frontend/src/components/fullview/ConversationIdentityCard.tsx`

- Line 1: Type icon (MessageSquare/FolderOpen) + subject as primary heading
- Line 2: Status badge (with color map including stale), AI status badge, child count (aggregates), communication count, channel breakdown (suppressed for single-channel)
- Line 3: Optional description in lighter text
- `STATUS_COLORS` map: active/open → green, stale → amber, closed → gray, archived → gray
- `AI_STATUS_COLORS` map: open → green, closed → gray, uncertain → amber

---

## Phase 5: Timeline Card

**File:** `frontend/src/components/fullview/ConversationTimelineCard.tsx`

- Sort toggle: ascending (oldest first) / descending (newest first) via `ArrowUpDown` button
- Auto-scroll to bottom (most recent message) when ascending on load
- `TimelineEntry` as `forwardRef` component for keyboard navigation refs
- Entry rendering: colored contact circle, channel icon, sender name (clickable link if contact resolved), → recipient suffix with +N overflow, timestamp
- Content: `cleaned_html` always rendered via `sanitizeHtml()` + `dangerouslySetInnerHTML` (no expand/collapse). Falls back to snippet, then "No content" italic.
- Attachment indicator with count, "secondary" badge for non-primary communications
- Row background tinting via participant color map
- Keyboard navigation: ArrowUp/ArrowDown between entries, Enter to open communication, focus ring on selected entry
- `entryRefs` Map for scroll-into-view on keyboard nav
- Double-click opens communication in full view

---

## Phase 6: Participants Card + AI Intelligence Card

### Participants Card

**File:** `frontend/src/components/fullview/ConversationParticipantsCard.tsx`

- Header with participant count
- Each participant: colored circle (matching timeline), name (clickable link if contact resolved), email address
- Communication count and last seen timestamp per participant
- Company name and title from contact data (when available)
- Account owner badge for the primary email account
- Sorted: account owner first, then by communication_count descending

### AI Intelligence Card

**File:** `frontend/src/components/fullview/ConversationSummaryCard.tsx`

- Blue-tinted card (`bg-blue-50`, `border-blue-200`)
- Header: Bot icon + "AI Intelligence" title + "AI Generated" badge
- Disabled Edit and Regenerate action buttons (coming soon)
- Summary section with label
- Action items: parsed from newline-separated text, rendered as checkbox-style list (read-only)
- Key topics: parsed from comma-separated text, rendered as rounded chips
- Footer: confidence score (2 decimal places) + "Last processed" timestamp
- Suppressed when all AI fields (ai_summary, ai_action_items, ai_topics) are NULL

---

## Phase 7: Entity Associations, Children, Notes, Metadata Cards

### Entity Associations Card

**File:** `frontend/src/components/fullview/ConversationAssociationsCard.tsx`

- Header with Link2 icon + "Associations" title + disabled "+ Link" button
- 4 entity groups (each suppressed if empty):
  - **Projects** (Briefcase icon): name link + status badge
  - **Companies** (Building2 icon): name link
  - **Contacts** (User icon): name link + title/company subtitle
  - **Events** (Calendar icon): title link + start_datetime
- All entity links navigate via `setActiveEntityType` + `setSelectedRow`
- Entire card suppressed when `totalCount === 0`

### Children Card

**File:** `frontend/src/components/fullview/ConversationChildrenCard.tsx`

- Header with child count + disabled "+ Add" button
- Only rendered for aggregate conversations (`data.is_aggregate`)
- Children sorted by `last_activity_at` descending (most recent first)
- Each child: type icon (FolderOpen/MessageSquare), title link, status badge, message count, sub-conversation count, last activity timestamp
- Click navigates to child conversation

### Notes Card Update

**File:** `frontend/src/components/fullview/ConversationNotesCard.tsx`

- Changed: suppressed (returns `null`) when `notes.length === 0` instead of showing "No notes yet" empty state
- Existing behavior preserved: pinned indicator, title, content preview, timestamp

### Metadata Card Update

**File:** `frontend/src/components/fullview/ConversationMetadataCard.tsx`

- Added: **Type** field — "Standard Conversation" or "Aggregate Conversation"
- Added: **Stale After** field — `{stale_after_days} days` (shown when non-null)
- Added: **Auto-Close After** field — `{closed_after_days} days` (shown when non-null)
- Existing fields preserved: First/Last Activity, Provider, Account, Topic, Project, Created/Updated timestamps, Created/Updated by, Conversation ID

### Full View Card Wiring

**File:** `frontend/src/components/fullview/ConversationFullView.tsx`

CRM sidebar card order (PRD Section 14.2):
1. Participants
2. AI Intelligence (Summary)
3. **Entity Associations** *(new)*
4. **Children** *(new, aggregate only)*
5. Project
6. Events
7. Tags
8. Triage (conditional)
9. Notes
10. Metadata

---

## Supporting Cards (created in earlier phases, unchanged in Phase 7)

- **ConversationProjectCard.tsx** — Displays topic/project assignment with folder icon
- **ConversationEventsCard.tsx** — Lists linked events with calendar icons and navigation
- **ConversationTagsCard.tsx** — Tag chips with AI source badges
- **TriageCard.tsx** — Amber alert card for triage classification/reason

---

## File Summary

### New Files (17)

| File | Purpose |
|------|---------|
| `poc/migrate_to_v20.py` | Database migration v19 → v20 |
| `frontend/src/api/conversationPreview.ts` | Preview data React Query hook |
| `frontend/src/api/conversationFull.ts` | Full data React Query hook |
| `frontend/src/lib/channelIcons.ts` | Channel → icon/label mapping |
| `frontend/src/lib/participantColors.ts` | Deterministic participant color system |
| `frontend/src/lib/formatTimestamp.ts` | Contextual timestamp formatting |
| `frontend/src/components/shared/ChannelBreakdown.tsx` | Inline channel count display |
| `frontend/src/components/detail/ConversationPreviewCard.tsx` | Preview card (standard + aggregate) |
| `frontend/src/components/fullview/ConversationFullView.tsx` | Full view layout + card orchestration |
| `frontend/src/components/fullview/ConversationIdentityCard.tsx` | Identity/header card |
| `frontend/src/components/fullview/ConversationTimelineCard.tsx` | Timeline with keyboard nav |
| `frontend/src/components/fullview/ConversationParticipantsCard.tsx` | Participants with color coding |
| `frontend/src/components/fullview/ConversationSummaryCard.tsx` | AI Intelligence card |
| `frontend/src/components/fullview/ConversationAssociationsCard.tsx` | Entity associations card |
| `frontend/src/components/fullview/ConversationChildrenCard.tsx` | Aggregate children card |
| `frontend/src/components/fullview/ConversationEventsCard.tsx` | Events list card |
| `frontend/src/components/fullview/ConversationProjectCard.tsx` | Project/topic card |

### Modified Files (7)

| File | Changes |
|------|---------|
| `poc/database.py` | Schema updated for v20 (conversations columns, conversation_members, relationship_types CHECK) |
| `poc/web/routes/api.py` | Preview + full endpoints extended with children, associations, new fields |
| `frontend/src/types/api.ts` | New interfaces for children, associations, extended preview/full data |
| `frontend/src/components/fullview/ConversationNotesCard.tsx` | Suppress when empty |
| `frontend/src/components/fullview/ConversationMetadataCard.tsx` | Added Type, Stale After, Auto-Close After fields |
| `frontend/src/components/shell/DetailPanel.tsx` | Wired ConversationPreviewCard into detail panel |
| `tests/test_api.py` | 20 new tests (new fields, children, associations) |

---

## Key Design Decisions

1. **No expand/collapse on timeline HTML** — cleaned_html always rendered in full; no truncation or "View Original" toggle
2. **Participant colors are deterministic** — same participant always gets the same color across sessions via address hashing
3. **clampRightWidth returns null** — when both min-right (280px) and min-left (40%) constraints can't be satisfied simultaneously, triggers single-column fallback rather than violating either constraint
4. **Cards self-suppress** — each card returns `null` when it has no data (associations empty, no notes, all AI fields null), keeping the sidebar clean
5. **Keyboard navigation via forwardRef** — timeline entries use a ref Map for scroll-into-view, with ArrowUp/Down/Enter handlers on the container
6. **Per-conversation splitter persistence** — localStorage keyed by conversation ID so each conversation remembers its layout
