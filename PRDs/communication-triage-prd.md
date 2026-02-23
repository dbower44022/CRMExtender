# Communication — Triage & Intelligent Filtering Sub-PRD

**Version:** 1.0
**Last Updated:** 2026-02-23
**Status:** Draft
**Entity Base PRD:** [communication-entity-base-prd.md]
**Referenced Entity PRDs:** [contact-entity-base-prd.md] (known-contact gate)

---

## 1. Overview

### 1.1 Purpose

Not every communication warrants AI analysis. Automated notifications, marketing emails, and messages from unknown sources consume AI resources without providing relationship intelligence. The triage pipeline classifies communications before they enter the intelligence layer, filtering noise while retaining all data for review.

Triage is a multi-layer pipeline: channel-specific heuristics (defined in channel child PRDs) catch automated patterns, a known-contact gate ensures at least one participant is a recognized CRM contact, and future user-defined rules provide custom filtering. Filtered communications are tagged with a reason and retained — nothing is silently discarded. Users can override any triage decision.

### 1.2 Preconditions

- Communication record exists with participant data (at least partially resolved).
- Channel-specific heuristic patterns are registered for the communication's channel.
- Contact records exist in the CRM for the known-contact gate to evaluate.

---

## 2. Context

### 2.1 Relevant Fields

| Field | Role in This Action |
|---|---|
| Triage Result | NULL = passed triage (real interaction). Non-NULL = filtered with specific reason. |
| Triage Reason | Human-readable explanation of the triage decision. |
| Channel | Determines which channel-specific heuristics to apply. |
| Source | Manual entries (`source = 'manual'`) bypass triage entirely. |

### 2.2 Relevant Relationships

- **Communication Participants** — The known-contact gate checks whether at least one participant (excluding the account owner) is a recognized CRM contact.
- **Provider Account** — Account owner identification is needed to exclude the owner from the known-contact gate check.

### 2.3 Cross-Entity Context

- **Contact Entity Base PRD:** The known-contact gate queries contact_identifiers to determine whether participant addresses belong to known contacts.
- **Channel-specific child PRDs:** Each channel defines its own heuristic patterns. Email Provider Sync PRD defines automated sender patterns, subject patterns, and marketing content detection. SMS/MMS PRD (future) defines short code and marketing patterns.
- **AI Learning & Classification PRD (future):** ML-based triage classification that learns from user overrides.
- **Published Summary Sub-PRD:** Summary generation only fires for communications that pass triage. Triage override triggers first-time summary generation.

---

## 3. Key Processes

### KP-1: Triage Classification on Communication Arrival

**Trigger:** New communication created via provider sync or import (manual entries bypass triage).

**Step 1 — Channel-specific heuristics (Layer 1):** System evaluates channel-specific patterns defined in the relevant child PRD. For email: automated sender patterns, automated subject patterns, marketing content detection. For SMS: short code detection, known marketing patterns.

**Step 2 — Known-contact gate (Layer 2):** System checks whether at least one participant (excluding the account owner) is a known CRM contact. If all non-owner participants are unknown, communication is filtered as `no_known_contacts`.

**Step 3 — User-defined rules (Layer 3, future):** User-configurable allowlists/blocklists per provider account. Pass or filter as `user_filtered`.

**Step 4 — Result:** If any layer filters the communication, triage_result is set to the specific filter reason and triage_reason is set to a human-readable explanation. If all layers pass, triage_result remains NULL. Communication proceeds to summary generation and AI processing only if triage_result is NULL.

### KP-2: User Overrides a Triage Decision

**Trigger:** User reviews a filtered communication and determines it is a real interaction.

**Step 1 — Override:** User clicks "Not Filtered" or equivalent action on the communication.

**Step 2 — Clear triage:** triage_result set back to NULL. triage_reason cleared.

**Step 3 — Queue for processing:** Communication queued for summary generation (first-time) and conversation assignment.

**Step 4 — Learning signal (future):** Override recorded as a training signal for ML-based classification.

**Step 5 — Event emitted:** `triage_overridden` event recorded.

### KP-3: Reviewing Filtered Communications

**Trigger:** User navigates to a "Filtered" view to review triage decisions.

**Step 1 — Filtered view:** Grid shows communications where triage_result IS NOT NULL. Columns include triage_result, triage_reason, channel, timestamp, subject, and participants.

**Step 2 — Inspection:** User clicks a filtered communication to view its full content and triage details.

**Step 3 — Action:** User either confirms the filter (no action needed — it remains filtered) or overrides it (KP-2).

---

## 4. Multi-Layer Pipeline

**Supports processes:** KP-1 (all steps)

### 4.1 Requirements

Triage operates as a sequence of filter layers. Each layer can either **pass** (communication continues to next layer) or **filter** (communication is tagged and skips AI processing).

```
Communication arrives
    │
    ├── Layer 1: Channel-specific heuristics
    │     (defined in child PRDs)
    │     → Pass or filter with reason
    │
    ├── Layer 2: Known-Contact Gate
    │     At least one non-owner participant must be a known CRM contact
    │     → Pass or filter as 'no_known_contacts'
    │
    ├── Layer 3: User-defined rules (future)
    │     User-configurable allowlists/blocklists
    │     → Pass or filter as 'user_filtered'
    │
    └── Result: triage_result = NULL (passed) or specific filter reason
```

Layers execute in order. The first layer that filters stops evaluation — the communication is tagged with that layer's reason.

**Tasks:**

- [ ] CTRI-01: Implement triage pipeline orchestrator (sequential layer evaluation)
- [ ] CTRI-02: Implement pipeline bypass for manual entries (source = 'manual')
- [ ] CTRI-03: Implement triage result and reason persistence on communication record

**Tests:**

- [ ] CTRI-T01: Test pipeline processes layers in order
- [ ] CTRI-T02: Test first filtering layer stops further evaluation
- [ ] CTRI-T03: Test manual entries bypass triage entirely
- [ ] CTRI-T04: Test communication passes when all layers pass

---

## 5. Channel-Specific Heuristics (Layer 1)

**Supports processes:** KP-1 (step 1)

### 5.1 Requirements

Each channel has its own heuristic patterns, defined in the respective child PRD. The triage pipeline delegates to a channel-specific heuristic evaluator.

**Email** (defined in Email Provider Sync PRD):

- Automated sender patterns: `noreply@`, `notification@`, `billing@`, `alerts@` (16 patterns)
- Automated subject patterns: "out of office", "automatic reply", "password reset" (12 patterns)
- Marketing content: body contains "unsubscribe"

**SMS/MMS** (defined in SMS/MMS PRD — future):

- Short code senders (5–6 digit numbers)
- Known marketing patterns

**Other channels:** Manual entries (phone_manual, video_manual, in_person, note) bypass triage entirely — if the user entered it, it's real. Recorded channels (phone_recorded, video_recorded) may have channel-specific heuristics defined in their child PRDs.

### 5.2 Heuristic Registration

Each channel child PRD registers its heuristic patterns with the triage pipeline. The pipeline dispatches to the appropriate evaluator based on the communication's channel.

**Tasks:**

- [ ] CTRI-04: Implement heuristic evaluator interface and registration
- [ ] CTRI-05: Implement channel-based dispatch to registered evaluators
- [ ] CTRI-06: Implement email heuristic evaluator with automated sender/subject/marketing patterns

**Tests:**

- [ ] CTRI-T05: Test email automated sender pattern matching (noreply@, etc.)
- [ ] CTRI-T06: Test email automated subject pattern matching
- [ ] CTRI-T07: Test email marketing content detection (unsubscribe keyword)
- [ ] CTRI-T08: Test unknown channels pass Layer 1 by default

---

## 6. Known-Contact Gate (Layer 2)

**Supports processes:** KP-1 (step 2)

### 6.1 Requirements

At least one participant (excluding the account owner) must be a known CRM contact. Communications where all non-owner participants are unknown are filtered as `no_known_contacts`.

**Rationale:** Communications from entirely unknown senders are unlikely to represent meaningful relationship interactions. However, they are **not deleted** — they are tagged and available for review. If the user later identifies one of the participants, the communication can be un-filtered.

### 6.2 Re-Evaluation on Contact Resolution

When a previously unknown participant is resolved to a contact (via the Participant Resolution Sub-PRD), the system should re-evaluate the known-contact gate for any communications that were filtered as `no_known_contacts` and now have a known participant. If the gate would now pass, the communication's triage_result is automatically cleared.

**Tasks:**

- [ ] CTRI-07: Implement known-contact gate evaluation
- [ ] CTRI-08: Implement account owner exclusion from gate check
- [ ] CTRI-09: Implement re-evaluation on contact resolution (auto-unfilter)

**Tests:**

- [ ] CTRI-T09: Test gate passes when at least one non-owner participant is known
- [ ] CTRI-T10: Test gate filters when all non-owner participants are unknown
- [ ] CTRI-T11: Test gate excludes account owner from known-contact check
- [ ] CTRI-T12: Test auto-unfilter when previously unknown participant is resolved

---

## 7. Triage Transparency

**Supports processes:** KP-2 (all steps), KP-3 (all steps)

### 7.1 Requirements

Filtered communications are **never deleted**. They remain in the system with:

- `triage_result` set to the filter reason
- `triage_reason` set to a human-readable explanation
- Full content preserved
- Available in "Filtered" views for user review

Users can override any triage decision, which:

1. Sets `triage_result` back to NULL
2. Queues the communication for AI processing (summary generation)
3. Optionally creates a learning signal for ML-based classification (future)

### 7.2 Triage Result Values

| Value | Source | Description |
|---|---|---|
| `automated_sender` | Layer 1 (email) | Sender matches automated pattern (noreply@, etc.) |
| `automated_subject` | Layer 1 (email) | Subject matches automated pattern (out of office, etc.) |
| `marketing_content` | Layer 1 (email) | Body contains marketing indicators (unsubscribe) |
| `no_known_contacts` | Layer 2 | No recognized CRM contacts among participants |
| `user_filtered` | Layer 3 (future) | User-defined rule triggered |

**Tasks:**

- [ ] CTRI-10: Implement triage override action (clear result, queue for processing)
- [ ] CTRI-11: Implement "Filtered" view with triage result and reason columns
- [ ] CTRI-12: Implement triage override event emission

**Tests:**

- [ ] CTRI-T13: Test override clears triage_result and triage_reason
- [ ] CTRI-T14: Test override queues communication for summary generation
- [ ] CTRI-T15: Test triage_overridden event emitted on override
- [ ] CTRI-T16: Test filtered view shows only communications with non-NULL triage_result

---

## 8. Triage API

**Supports processes:** KP-2 (step 1), KP-3 (step 1)

### 8.1 Requirements

| Endpoint | Method | Description |
|---|---|---|
| `/api/v1/communications/{id}/triage/override` | POST | Override a triage decision (un-filter a communication) |
| `/api/v1/communications/triage/stats` | GET | Get triage statistics (filtered count by reason) |

**Tasks:**

- [ ] CTRI-13: Implement triage API endpoints (override, stats)

**Tests:**

- [ ] CTRI-T17: Test triage override API un-filters communication
- [ ] CTRI-T18: Test triage stats API returns correct counts per reason

---

## 9. Future Enhancements

These enhancements are planned but not part of the initial implementation:

- **ML-based classification** — Learning from user overrides to improve triage accuracy over time.
- **User-configurable allowlists/blocklists** — Per-provider-account rules.
- **Category-based rules** — Using provider labels (Gmail categories, Outlook Focused/Other).
- **Volume-based detection** — Identifying high-frequency automated senders by communication volume patterns.
