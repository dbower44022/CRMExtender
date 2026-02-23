# Conversation — Formation & Stitching Sub-PRD

**Version:** 1.0
**Last Updated:** 2026-02-23
**Status:** Draft
**Entity Base PRD:** [conversation-entity-base-prd.md]
**Referenced Entity PRDs:** [communication-entity-base-prd.md] (provider thread IDs), [communication-provider-sync-prd.md] (sync pipeline)

---

## 1. Overview

### 1.1 Purpose

This sub-PRD defines how Communications are assigned to Conversations: automatic formation from email thread IDs, participant-based default grouping for non-threaded channels, manual assignment, AI-suggested splitting, and cross-channel stitching. It also covers communication segmentation — the split/reference model for handling multi-topic communications.

Together, these mechanisms answer the question: "How does a communication end up in a conversation?"

### 1.2 Preconditions

- Communication record exists with provider metadata (provider_thread_id, participants, channel, timestamp).
- Conversation entity is registered and operational.
- For AI-assisted operations: AI API accessible.

---

## 2. Context

### 2.1 Relevant Fields

| Field | Role in This Action |
|---|---|
| conversation_id (on Communication) | FK linking a communication to its primary conversation. Set during formation/assignment. |
| provider_thread_id (on Communication) | Provider's thread identifier. Primary key for email-based auto-formation. |
| channel (on Communication) | Determines which formation mechanism applies. |
| timestamp (on Communication) | Universal sequencing key for timeline ordering and temporal proximity. |
| is_aggregate (on Conversation) | Standard conversations receive communications; aggregates group conversations. |
| ai_confidence (on Conversation) | Confidence of AI's assignment. Drives review workflow. |

### 2.2 Cross-Entity Context

- **Communication Published Summary Sub-PRD:** The Conversation timeline renders Published Summaries by reference. Formation assigns communications to conversations; summaries are what appear in the timeline.
- **Communication Participant Resolution Sub-PRD:** Participant data drives participant-based default conversations and cross-channel stitching.
- **AI Intelligence & Review Sub-PRD:** AI classification determines which conversation a communication belongs to. This sub-PRD defines formation; AI Intelligence defines the classification logic.

---

## 3. Key Processes

### KP-1: Email-Based Auto-Formation

**Trigger:** Email arrives via provider sync with a provider_thread_id.

**Step 1 — Thread lookup:** System checks if this provider_thread_id is already mapped to a conversation.

**Step 2a — Existing thread:** If found, communication assigned to the existing conversation. Denormalized counts updated.

**Step 2b — New thread:** If not found, new Conversation created with subject derived from email subject. Communication assigned. AI classification queued.

**Step 3 — Timeline entry:** Communication's Published Summary appears in the conversation timeline at its chronological position.

### KP-2: Participant-Based Default Conversations

**Trigger:** Non-threaded communication arrives (SMS, phone call) with no provider_thread_id.

**Step 1 — Participant set computation:** System identifies the set of non-owner participants (from Communication Participant Resolution).

**Step 2 — Default conversation lookup:** System checks for an existing default conversation matching this participant set and channel.

**Step 3a — Existing default:** If found, communication assigned to the default conversation. This creates catch-all streams like "SMS with Bob" containing all SMS exchanges.

**Step 3b — New default:** If no matching default exists, create one. Subject auto-generated: "SMS with Bob" or "Group SMS with Bob, Alice, and Carol."

**Step 4 — User refinement:** Users can later move specific messages from the default conversation to topic-specific conversations.

### KP-3: Manual Conversation Assignment

**Trigger:** User explicitly assigns a communication to a conversation, or creates a conversation and assigns communications to it.

**Step 1 — User selects conversation:** From existing conversations or creates new.

**Step 2 — Assignment:** Communication's conversation_id updated. If moving from another conversation, old conversation's counts recomputed.

**Step 3 — Event emitted:** `communication_added` event on target conversation. `communication_removed` event on source conversation (if reassignment).

### KP-4: AI-Suggested Splitting

**Trigger:** AI detects that a communication doesn't fit its current conversation (different subject, different context).

**Step 1 — Detection:** During AI processing of a conversation, the AI flags a communication as potentially misplaced.

**Step 2 — Suggestion:** System presents a suggestion to the user: "This message may belong to a different conversation. Create new conversation?"

**Step 3 — User decision:** User accepts (new conversation created, communication moved), rejects (stays in current), or assigns to a different existing conversation.

### KP-5: Cross-Channel Stitching

**Trigger:** Communication arrives on a non-email channel (SMS, phone, video) that may relate to an existing conversation.

**Step 1 — Automatic (email only):** Email thread IDs provide reliable stitching. Handled in KP-1.

**Step 2 — Manual (other channels):** SMS, calls, and meetings are assigned to the default participant-based conversation (KP-2) unless the user assigns them elsewhere.

**Step 3 — AI-assisted (future):** AI may suggest cross-channel assignments based on participant overlap, temporal proximity, and content similarity. Always presented as suggestions.

---

## 4. Email Thread Formation

**Supports processes:** KP-1

### 4.1 Requirements

Email providers supply native thread identifiers:

| Provider | Threading Mechanism | Reliability |
|---|---|---|
| Gmail | threadId — groups by subject and participants | High (occasional false grouping on common subjects) |
| Outlook | conversationId — groups by conversation | High |
| IMAP | Reconstructed from RFC 5322 headers (Message-ID, References, In-Reply-To) with subject-line fallback | Medium (JWZ algorithm) |

An email thread automatically creates a Conversation. The provider_thread_id on Communication records links messages to conversations. Additional threads may be merged into the same conversation by AI or user.

**Tasks:**

- [ ] CFOR-01: Implement provider_thread_id → conversation_id mapping lookup
- [ ] CFOR-02: Implement auto-creation of Conversation from new email thread
- [ ] CFOR-03: Implement subject derivation from first email in thread
- [ ] CFOR-04: Implement thread-to-conversation mapping table/index

**Tests:**

- [ ] CFOR-T01: Test new email thread creates new Conversation with correct subject
- [ ] CFOR-T02: Test subsequent emails in same thread assign to existing Conversation
- [ ] CFOR-T03: Test Gmail threadId mapping
- [ ] CFOR-T04: Test Outlook conversationId mapping
- [ ] CFOR-T05: Test IMAP header-based thread reconstruction

---

## 5. Participant-Based Default Conversations

**Supports processes:** KP-2

### 5.1 Requirements

For channels without native threading (SMS, phone, video), the system creates default participant-based conversations:

- All SMS messages between the same set of participants form a single default conversation.
- Subject auto-generated from participant names and channel.
- Acts as a catch-all stream. Users can move specific messages to topic-specific conversations.
- Phone calls and video meetings follow the same pattern.

**Tasks:**

- [ ] CFOR-05: Implement participant set computation for default conversation matching
- [ ] CFOR-06: Implement default conversation lookup by participant set + channel
- [ ] CFOR-07: Implement auto-subject generation for default conversations
- [ ] CFOR-08: Implement default conversation creation for new participant sets

**Tests:**

- [ ] CFOR-T06: Test SMS between two participants creates "SMS with Bob" conversation
- [ ] CFOR-T07: Test group SMS creates appropriately named default conversation
- [ ] CFOR-T08: Test subsequent SMS between same participants assigns to existing default
- [ ] CFOR-T09: Test phone calls create separate default from SMS (different channel)

---

## 6. Manual Assignment & Reassignment

**Supports processes:** KP-3

### 6.1 Requirements

Users can assign or reassign communications to conversations at any time:

- Assign an unassigned communication to a conversation.
- Move a communication from one conversation to another.
- Create a new conversation and assign communications in one action.
- Batch assignment for multiple communications.

Reassignment updates denormalized counts on both source and target conversations and emits events on both.

**Tasks:**

- [ ] CFOR-09: Implement single communication assignment (set conversation_id)
- [ ] CFOR-10: Implement communication reassignment (move between conversations)
- [ ] CFOR-11: Implement batch assignment for multiple communications
- [ ] CFOR-12: Implement denormalized count recomputation on assignment change

**Tests:**

- [ ] CFOR-T10: Test assign updates conversation_id and target counts
- [ ] CFOR-T11: Test reassignment updates both source and target counts
- [ ] CFOR-T12: Test batch assignment handles multiple communications
- [ ] CFOR-T13: Test events emitted on both conversations during reassignment

---

## 7. Cross-Channel Stitching

**Supports processes:** KP-5

### 7.1 Requirements

A conversation can contain communications from multiple channels, maintained through timestamp sequencing:

- Email threads form the backbone.
- SMS/phone/video between the same participants near the same time may relate to the same conversation.
- Manual assignment is the primary mechanism for non-email stitching.
- AI-assisted stitching (future) will suggest assignments based on participant overlap, temporal proximity, and content similarity.

### 7.2 Multi-Channel Formatting for AI

When AI processes a conversation, the prompt includes channel markers:

```
[EMAIL] From: Bob Smith | Date: 2026-02-07 10:15
[Summary content]
---
[SMS] From: Me → Bob | Date: 2026-02-07 12:45
[Message content]
---
[PHONE] Participants: Me, Bob | Date: 2026-02-07 15:00 (12 min)
[Transcript summary]
```

**Tasks:**

- [ ] CFOR-13: Implement multi-channel timeline assembly (chronological ordering across channels)
- [ ] CFOR-14: Implement channel-marker formatting for AI prompt construction

**Tests:**

- [ ] CFOR-T14: Test timeline correctly interleaves communications from multiple channels
- [ ] CFOR-T15: Test AI prompt includes channel markers and correct chronological order

---

## 8. Communication Segmentation

**Supports processes:** KP-3 (split/reference)

### 8.1 The Problem

A single communication may address multiple topics. An email might discuss a contract revision AND an upcoming offsite — two topics, potentially two conversations.

### 8.2 The Split/Reference Model

**Primary assignment (automatic):** Each communication is assigned to its primary conversation via conversation_id. The full communication lives there.

**Segment creation (user-driven):** User selects a text portion, invokes "Assign selected to different conversation." This creates a Segment — the selected text referenced in the target conversation.

**What the user sees:**

- Primary conversation: full communication with segmented portion highlighted.
- Secondary conversation: segment (selected text) with link back to original.

**What is preserved:**

- Original communication is never modified or moved.
- Segment is a reference, not a copy.
- Both conversations show contextually relevant content.

### 8.3 AI-Assisted Segmentation (Future)

AI could analyze communications at the paragraph level and suggest segments when detecting multi-topic content. Presented as suggestions, never automatic.

**Tasks:**

- [ ] CFOR-15: Implement segment creation (text selection → segment record)
- [ ] CFOR-16: Implement segment display in target conversation timeline
- [ ] CFOR-17: Implement segment highlighting in source communication view
- [ ] CFOR-18: Implement "View Original" link from segment to full communication

**Tests:**

- [ ] CFOR-T16: Test segment creation stores correct offsets and selected_text
- [ ] CFOR-T17: Test segment appears in target conversation timeline
- [ ] CFOR-T18: Test source communication shows segment highlight
- [ ] CFOR-T19: Test segment link navigates to full original communication
- [ ] CFOR-T20: Test segment cascade-deletes when source communication is deleted
