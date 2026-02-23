# Conversation — AI Intelligence & Review Sub-PRD

**Version:** 1.0
**Last Updated:** 2026-02-23
**Status:** Draft
**Entity Base PRD:** [conversation-entity-base-prd.md]
**Referenced Entity PRDs:** [communication-entity-base-prd.md] (Published Summaries as AI input), [communication-triage-prd.md] (triage gates AI processing)

---

## 1. Overview

### 1.1 Purpose

The AI intelligence layer powers three capabilities: classifying and routing communications into conversations, generating conversation-level summaries, and extracting structured intelligence (status, action items, key topics). The review workflow provides human oversight of AI decisions, and user corrections become training signals for continuous improvement.

This sub-PRD defines what the AI does and how users interact with its outputs. The specific algorithms, model selection, and training pipelines are deferred to the AI Learning & Classification PRD (future).

### 1.2 Preconditions

- Communication records exist with Published Summaries (summary_text) available for AI consumption.
- Communications have passed triage (triage_result IS NULL).
- AI API is accessible.

---

## 2. Context

### 2.1 Relevant Fields

| Field | Role in This Action |
|---|---|
| AI Status | Semantic conversation state: open, closed, uncertain. Output of Role 3. |
| AI Summary | 2–4 sentence narrative. Output of Role 2. |
| AI Action Items | JSON-encoded extracted action items. Output of Role 3. |
| AI Key Topics | JSON-encoded topic phrases. Output of Role 3. |
| AI Confidence | Assignment confidence score (0.0–1.0). Output of Role 1. |
| AI Last Processed At | When AI last analyzed this conversation. |

### 2.2 Cross-Entity Context

- **Communication Published Summary Sub-PRD:** AI consumes summary_text from each Communication's Published Summary, not raw content. The Conversation-level AI summary is a higher-order synthesis.
- **Communication Triage Sub-PRD:** Only communications that pass triage are processed by AI. Triage override triggers first-time AI processing.
- **Conversation Formation Sub-PRD:** AI classification (Role 1) determines which conversation a communication belongs to. Formation defines the mechanisms; this sub-PRD defines the classification logic.
- **AI Learning & Classification PRD (future):** Defines how learning is implemented — classification algorithms, embedding/similarity, model training, confidence scoring.

---

## 3. Key Processes

### KP-1: Classify & Route a New Communication

**Trigger:** New communication arrives that has passed triage.

**Step 1 — Candidate identification:** AI identifies candidate conversations based on provider_thread_id (email), participant overlap, temporal proximity, and content similarity.

**Step 2 — Confidence scoring:** AI assigns a confidence score (0.0–1.0) to the best match.

**Step 3a — High confidence (> 0.85):** Communication auto-assigned to the conversation. No user review needed.

**Step 3b — Medium confidence (0.50–0.85):** Communication tentatively assigned but flagged for review.

**Step 3c — Low confidence (< 0.50):** Communication left unassigned. User assignment required.

**Step 4 — Aggregate placement:** AI evaluates whether the conversation should be placed in an existing aggregate. Same confidence model applies.

### KP-2: Summarize a Conversation

**Trigger:** New communication added, communication summary revised, user requests refresh.

**Step 1 — Content assembly:** System assembles the Published Summaries (summary_text) of all communications in the conversation, in chronological order with channel markers.

**Step 2 — AI processing:** AI generates a 2–4 sentence narrative summarizing the conversation's current state. Stored in ai_summary.

**Step 3 — Aggregate fan-out:** If this conversation is a child of any aggregates, parent aggregates are queued for re-summarization.

### KP-3: Extract Intelligence

**Trigger:** Same triggers as KP-2 (co-processed with summarization).

**Step 1 — Status classification:** AI determines ai_status: `open` (unresolved items), `closed` (resolved), `uncertain` (insufficient context). Biased toward `open` for multi-message exchanges.

**Step 2 — Action item extraction:** AI extracts specific tasks with identification of responsible party and deadlines. Stored as JSON in ai_action_items.

**Step 3 — Key topic extraction:** AI produces 2–5 short topic phrases, normalized for cross-conversation aggregation. Stored as JSON in ai_key_topics.

**Step 4 — Confidence and timestamp:** ai_confidence updated (for classification). ai_last_processed_at set.

### KP-4: User Reviews Auto-Assignments

**Trigger:** User opens the review workflow (daily activity).

**Step 1 — Pending items load:** System presents: "14 new communications since yesterday. 11 auto-assigned (review). 3 unassigned (needs your input)."

**Step 2 — Review auto-assignments:** User sees each auto-assigned communication with confidence indicator and target conversation. Accept or correct with minimal clicks.

**Step 3 — Assign unassigned:** User assigns communications that AI couldn't confidently place. Create new conversations if needed.

**Step 4 — Review aggregate placement:** User reviews AI-suggested aggregate placements.

**Step 5 — Identify contacts:** Defers unknown contact identification to Contact Intelligence system.

### KP-5: User Corrects an AI Assignment

**Trigger:** User moves a communication to a different conversation than AI assigned.

**Step 1 — Correction recorded:** System records the correction as a training signal: original assignment, corrected assignment, communication metadata.

**Step 2 — Reassignment executed:** Communication moved per Formation Sub-PRD reassignment logic.

**Step 3 — Learning signal stored:** Correction feeds the learning system for future improvement.

---

## 4. AI Role 1: Classify & Route

**Supports processes:** KP-1

### 4.1 Requirements

For every incoming non-triaged communication, AI determines:

- Which conversation does this belong to? (existing, or create new?)
- Which aggregate conversation should this conversation be placed in? (existing, or suggest new?)
- Confidence score for each assignment.

### 4.2 Confidence Thresholds

| Level | Range | Behavior |
|---|---|---|
| High | > 0.85 | Auto-assigned silently. Green indicator. Review optional. |
| Medium | 0.50 – 0.85 | Tentatively assigned, flagged for review. Yellow indicator. |
| Low | < 0.50 | Left unassigned. Red indicator. User assignment required. |

Thresholds may be adjustable per tenant in the future.

**Tasks:**

- [ ] CINT-01: Implement AI classification pipeline for incoming communications
- [ ] CINT-02: Implement candidate conversation identification (thread, participant, content similarity)
- [ ] CINT-03: Implement confidence scoring for conversation assignment
- [ ] CINT-04: Implement auto-assignment for high-confidence matches
- [ ] CINT-05: Implement flagging for medium-confidence matches
- [ ] CINT-06: Implement aggregate placement suggestion with confidence

**Tests:**

- [ ] CINT-T01: Test high-confidence communication auto-assigns without review flag
- [ ] CINT-T02: Test medium-confidence communication assigns with review flag
- [ ] CINT-T03: Test low-confidence communication remains unassigned
- [ ] CINT-T04: Test confidence score stored on conversation record
- [ ] CINT-T05: Test aggregate placement suggestion generated

---

## 5. AI Role 2: Summarize

**Supports processes:** KP-2

### 5.1 Requirements

Conversation-level summaries synthesize across all Communications' Published Summaries:

- Input: summary_text from each Communication, chronologically ordered with channel markers.
- Output: 2–4 sentence narrative of conversation's current state.
- Stored in ai_summary on the Conversation record.

For aggregate Conversations: summary synthesizes across own Communications PLUS all child Conversation summaries.

### 5.2 Summarization Thresholds

| Content | Summarize? | Rationale |
|---|---|---|
| < 50 words total | No | Insufficient content |
| 50–200 words total | Optional | May benefit in conversation context |
| > 200 words total | Yes | Substantial content benefits from distillation |

Conversation-level summaries are always generated when sufficient total content exists, regardless of individual communication lengths.

### 5.3 Re-Summarization Triggers

| Trigger | Behavior |
|---|---|
| New Communication added | AI refreshes conversation summary |
| Communication Published Summary revised | AI refreshes to incorporate update |
| User requests refresh | Explicit re-summarization |
| Communication reassigned to/from | Both source and target conversations refreshed |
| Child added/removed (aggregate) | Aggregate summary refreshed |
| Child summary changed (aggregate) | Fan-out: aggregate summary refreshed |

**Tasks:**

- [ ] CINT-07: Implement conversation content assembly for AI prompt (chronological, channel-marked)
- [ ] CINT-08: Implement conversation-level AI summarization
- [ ] CINT-09: Implement aggregate summarization (own content + child summaries)
- [ ] CINT-10: Implement re-summarization trigger dispatch
- [ ] CINT-11: Implement AI summary fan-out to parent aggregates

**Tests:**

- [ ] CINT-T06: Test conversation summary generated from Published Summaries
- [ ] CINT-T07: Test aggregate summary includes child conversation summaries
- [ ] CINT-T08: Test re-summarization triggers on new communication
- [ ] CINT-T09: Test fan-out triggers parent aggregate re-summarization
- [ ] CINT-T10: Test summarization skipped for insufficient content

---

## 6. AI Role 3: Extract Intelligence

**Supports processes:** KP-3

### 6.1 Status Classification

AI determines ai_status:

| Value | Meaning | Bias |
|---|---|---|
| `open` | Unresolved items, pending tasks, ongoing discussion | Default for multi-message exchanges between known contacts |
| `closed` | Definitively resolved or finished | Only when conversation has clear resolution markers |
| `uncertain` | Insufficient context | For brief or ambiguous conversations |

Casual sign-offs ("Thanks!") do not close a conversation. Bias toward `open`.

### 6.2 Action Item Extraction

AI extracts specific tasks from conversation content:

```json
[
  {
    "description": "Send revised contract",
    "assignee": "Bob Smith",
    "deadline": "2026-02-21",
    "confidence": 0.9
  },
  {
    "description": "Review comments within 48 hours",
    "assignee": "Me",
    "deadline": null,
    "confidence": 0.85
  }
]
```

### 6.3 Key Topic Extraction

AI produces 2–5 short topic phrases normalized for cross-conversation aggregation:

```json
["liability cap", "contract clause 5", "signing timeline"]
```

**Tasks:**

- [ ] CINT-12: Implement AI status classification (open/closed/uncertain)
- [ ] CINT-13: Implement action item extraction with assignee and deadline
- [ ] CINT-14: Implement key topic extraction with normalization
- [ ] CINT-15: Implement JSON storage for action items and key topics

**Tests:**

- [ ] CINT-T11: Test status classification bias toward open for active conversations
- [ ] CINT-T12: Test action item extraction identifies assignees
- [ ] CINT-T13: Test key topic extraction produces 2–5 normalized phrases
- [ ] CINT-T14: Test casual sign-off does not trigger closed status

---

## 7. AI Error Handling

**Supports processes:** KP-1 through KP-3

### 7.1 Requirements

| Failure | Recovery |
|---|---|
| AI API timeout | Retry with exponential backoff (3 attempts); mark as pending |
| AI API rate limit | Queue and retry after cooldown |
| Malformed AI response | Log raw response; return with error flag |
| AI API unavailable | Conversations remain visible without AI data; queue for processing when API returns |
| Empty conversation content | Skip; display "(no content to analyze)" |

**Tasks:**

- [ ] CINT-16: Implement AI retry with exponential backoff
- [ ] CINT-17: Implement queuing for deferred AI processing
- [ ] CINT-18: Implement graceful degradation when AI unavailable

**Tests:**

- [ ] CINT-T15: Test retry on transient AI failure
- [ ] CINT-T16: Test conversations display without AI data when API unavailable
- [ ] CINT-T17: Test queued items process when API returns

---

## 8. Review Workflow

**Supports processes:** KP-4, KP-5

### 8.1 Requirements

The review workflow must be **extremely efficient** — it is a daily activity that must take seconds, not minutes.

**Review inbox presents:**

- Auto-assigned communications with confidence indicators (green/yellow/red)
- Unassigned communications requiring user input
- AI-suggested aggregate placements
- Unknown contacts pending identification

**Review actions:**

- Accept auto-assignment (one click)
- Correct assignment (select different conversation or create new)
- Batch accept multiple auto-assignments
- Create new conversation from unassigned communications

### 8.2 Confidence Display

| Level | Color | Label |
|---|---|---|
| High (> 0.85) | Green | Assigned silently. Review optional. |
| Medium (0.50 – 0.85) | Yellow | Flagged for review. |
| Low (< 0.50) | Red | Unassigned. Assignment required. |

**Tasks:**

- [ ] CINT-19: Implement review inbox query (pending items sorted by confidence)
- [ ] CINT-20: Implement single-click accept for auto-assignments
- [ ] CINT-21: Implement batch accept for multiple auto-assignments
- [ ] CINT-22: Implement correction flow (reassign with learning signal)
- [ ] CINT-23: Implement review statistics (pending count, correction rate)

**Tests:**

- [ ] CINT-T18: Test review inbox shows all pending items with confidence indicators
- [ ] CINT-T19: Test single-click accept confirms assignment
- [ ] CINT-T20: Test batch accept handles multiple items
- [ ] CINT-T21: Test correction records learning signal
- [ ] CINT-T22: Test review stats reflect current state

---

## 9. Learning from User Corrections

**Supports processes:** KP-5

### 9.1 The Principle

The system learns from every user correction to improve future auto-assignment.

### 9.2 What the System Learns

Over time, the system should:

- Recognize patterns specific to each user's organizational preferences.
- Learn contact-specific routing (e.g., "emails from Bob about invoices go to Accounting").
- Improve confidence thresholds based on correction rates.
- Apply organizational learning across team members where appropriate.

### 9.3 Correction Signal Data Model

Each correction stores: original assignment (conversation_id before), corrected assignment (conversation_id after), communication metadata (channel, participants, subject, content features), user who corrected, and timestamp.

### 9.4 Deferred Details

The details of how learning is implemented — prompt-based context, embedding similarity, fine-tuning, or hybrid — are defined in the AI Learning & Classification PRD (future). This sub-PRD establishes the product requirement: the system learns and improves.

**Tasks:**

- [ ] CINT-24: Implement correction signal recording (before/after/metadata)
- [ ] CINT-25: Implement correction signal storage for future learning pipeline

**Tests:**

- [ ] CINT-T23: Test correction signal captures original and corrected assignments
- [ ] CINT-T24: Test correction signal includes communication metadata
