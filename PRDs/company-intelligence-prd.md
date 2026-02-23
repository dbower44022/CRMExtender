# Company — Intelligence & Scoring Sub-PRD

**Version:** 1.0
**Last Updated:** 2026-02-23
**Status:** Draft
**Entity Base PRD:** [company-entity-base-prd.md]
**Referenced Entity PRDs:** [communications-prd.md] (communication data), [contact-entity-base-prd.md] (employment linkage), [events-prd.md] (meeting data)

---

## 1. Overview

### 1.1 Purpose

Intelligence & scoring surfaces which companies matter most to the user based on actual communication behavior. Rather than static labels or manual rankings, the system computes relationship strength from communication patterns — recency, frequency, reciprocity, breadth (how many contacts at the company), and duration. Scores are precomputed for fast sorting and display, with full factor breakdowns for transparency.

Intelligence is surfaced through saved views (smart filters) rather than interruptive alerts, letting users pull information when they are ready.

### 1.2 Preconditions

- Company records exist with linked contacts (via employment).
- Communications are tracked in the system.
- The entity_scores table exists.

---

## 2. Context

### 2.1 Relevant Fields

| Field | Role in This Action |
|---|---|
| Relationship Strength | The primary output — a 0.0–1.0 score stored on the company record for sort/filter. |
| Name, Domain | Used in intelligence view labels and score transparency display. |

### 2.2 Relevant Relationships

- **Contact Employment** — Relationship strength is computed from communication patterns with contacts employed at the company. The employment relationship is the bridge between companies and communications.
- **Communications** — Communication records (with participants) provide the raw data: who communicated, when, in what direction, through which channel.
- **Events** — Calendar events with company contacts feed the meeting frequency and meeting-to-email ratio metrics.

### 2.3 Relevant Lifecycle Transitions

- No lifecycle transitions. Scoring is a continuous background process that updates field values.

### 2.4 Cross-Entity Context

- **Communications PRD:** Communication participant records identify which contacts were involved in each communication. Direction (sent/received) is available for directionality weighting.
- **Contact Entity Base PRD:** Employment records connect contacts to companies with temporal metadata (is_current, start/end dates). Only current employees are counted for breadth scoring.
- **Events PRD:** Event participants with company affiliation feed meeting metrics.
- **Company Entity TDD:** Precomputed scores are stored in the `entity_scores` table. The Relationship Strength field on the companies read model table is a denormalized cache (marked † in the Base PRD).

---

## 3. Key Processes

### KP-1: Viewing Relationship Strength

**Trigger:** User navigates to a company list view sorted by relationship strength, or views a company detail page.

**Step 1 — Score display:** The relationship strength score (0.0–1.0) is displayed as a visual indicator (progress bar, color-coded badge, or numeric value) in list views and on the detail page.

**Step 2 — Factor breakdown:** User clicks or hovers on the score. A tooltip or expandable panel shows the factor breakdown:

```
Relationship Strength: 0.73

  Recency:     0.85 × 0.35 = 0.298
  Frequency:   0.60 × 0.25 = 0.150
  Reciprocity: 0.70 × 0.20 = 0.140
  Breadth:     0.50 × 0.12 = 0.060
  Duration:    1.00 × 0.08 = 0.080

  Last contact: 3 days ago
  Communications (30d): 12 sent, 8 received
  Active contacts at company: 3
  Relationship since: 2024-06-15
```

### KP-2: Using Intelligence Views

**Trigger:** User navigates to a pre-built intelligence view or creates a custom view using score-based filters.

**Step 1 — Select view:** User selects from intelligence views:
- "Companies — declining engagement (30-day trend)"
- "Companies — highest relationship strength"
- "New companies — detected this week"
- "Companies — no communication in 90+ days"
- "Key contacts at risk — communication dropped significantly"

**Step 2 — View loads:** Grid displays companies matching the view's filter criteria, sorted by the relevant score. Standard view interactions (further filtering, sorting, column customization) apply.

### KP-3: Adjusting Scoring Weights

**Trigger:** User navigates to scoring settings.

**Step 1 — View current weights:** System displays the five factor weights with sliders.

**Step 2 — Adjust weights:** User moves sliders. Weights auto-normalize to sum to 1.0.

**Step 3 — Preview impact:** System shows a preview of how the top 10 companies would re-rank under the new weights.

**Step 4 — Apply:** User confirms. System queues bulk score recalculation.

---

## 4. Relationship Strength Scoring Model

**Supports processes:** KP-1 (data source), KP-3 (configuration)

### 4.1 Requirements

**Five-Factor Model:**

| Factor | Weight (Default) | Measures | Data Source |
|---|---|---|---|
| Recency | 0.35 | How recently the user communicated with company contacts. | Most recent communication timestamp. |
| Frequency | 0.25 | How often communications occur. | Communication count over a rolling 90-day window. |
| Reciprocity | 0.20 | Whether communication is bidirectional. | Ratio of inbound vs. outbound communications. |
| Breadth | 0.12 | How many contacts at the company the user interacts with. | Count of distinct contacts with communications in rolling window. |
| Duration | 0.08 | How long the relationship has existed. | Time since first communication with any company contact. |

**Formula:**

```
score = (w_recency × recency_score)
      + (w_frequency × frequency_score)
      + (w_reciprocity × reciprocity_score)
      + (w_breadth × breadth_score)
      + (w_duration × duration_score)
```

Each factor is normalized to 0.0–1.0 before weighting. Weights auto-normalize to sum to 1.0.

**Directionality weighting:** Outbound (user-initiated) communications carry 1.0× multiplier; inbound carry 0.6×. Initiating communication is a stronger signal of relationship investment.

**Time decay:** Scores decay over time. A company emailed daily six months ago but not since scores lower than one emailed weekly in the current month.

**User-editable formula:** Users can adjust factor weights via system settings. The UI presents sliders for each weight.

**Tasks:**

- [ ] CINT-01: Implement five-factor scoring model with normalization
- [ ] CINT-02: Implement directionality weighting (outbound 1.0×, inbound 0.6×)
- [ ] CINT-03: Implement time decay function
- [ ] CINT-04: Implement user-configurable weight sliders with auto-normalization
- [ ] CINT-05: Implement score preview for weight changes

**Tests:**

- [ ] CINT-T01: Test score computation with known inputs produces expected output
- [ ] CINT-T02: Test weights auto-normalize to sum to 1.0
- [ ] CINT-T03: Test directionality weighting (outbound weighted higher)
- [ ] CINT-T04: Test time decay reduces scores for inactive relationships
- [ ] CINT-T05: Test score is 0.0 for companies with no communication history

---

## 5. Score Recalculation

**Supports processes:** KP-1 (data freshness), KP-3 (step 4)

### 5.1 Requirements

| Trigger | Description |
|---|---|
| **Event-driven** | New communication sent/received involving a company contact → recompute that company's scores. |
| **Time-based** | Scheduled job runs daily to apply time decay across all entities. |
| **Bulk** | After a merge, import, or sync completes → recompute affected entities. |
| **Manual** | User requests recalculation from the UI. |
| **Weight change** | User adjusts scoring weights → queue bulk recalculation for all companies. |

Scores are stored in the `entity_scores` table (see Company Entity TDD, Section 8). The UPSERT-friendly unique constraint ensures clean score replacement.

**Tasks:**

- [ ] CINT-06: Implement event-driven score recalculation on new communications
- [ ] CINT-07: Implement daily time-decay scheduled job
- [ ] CINT-08: Implement bulk recalculation after merge/import/sync
- [ ] CINT-09: Implement manual recalculation API endpoint

**Tests:**

- [ ] CINT-T06: Test score updates on new communication
- [ ] CINT-T07: Test daily decay reduces scores for all companies proportionally
- [ ] CINT-T08: Test bulk recalculation after merge updates surviving company's score
- [ ] CINT-T09: Test manual recalculation endpoint triggers recomputation

---

## 6. Score Transparency

**Supports processes:** KP-1 (step 2)

### 6.1 Requirements

The `factors` JSONB column in `entity_scores` stores the factor breakdown for transparency:

```json
{
  "recency": {"raw": 0.85, "weight": 0.35, "weighted": 0.298},
  "frequency": {"raw": 0.60, "weight": 0.25, "weighted": 0.150},
  "reciprocity": {"raw": 0.70, "weight": 0.20, "weighted": 0.140},
  "breadth": {"raw": 0.50, "weight": 0.12, "weighted": 0.060},
  "duration": {"raw": 1.00, "weight": 0.08, "weighted": 0.080},
  "summary": {
    "last_contact_at": "2026-02-20T14:30:00Z",
    "communications_30d_sent": 12,
    "communications_30d_received": 8,
    "active_contacts": 3,
    "relationship_since": "2024-06-15"
  }
}
```

**Tasks:**

- [ ] CINT-10: Store factor breakdown in entity_scores.factors JSONB
- [ ] CINT-11: Implement score transparency UI (expandable factor breakdown)

**Tests:**

- [ ] CINT-T10: Test factors JSONB contains all five factor breakdowns
- [ ] CINT-T11: Test summary stats are accurate (last contact, 30d counts, active contacts)

---

## 7. Derived Metrics

**Supports processes:** KP-2 (view data)

### 7.1 Requirements

Beyond relationship strength, these metrics are derivable from existing data:

| Metric | Source | Description |
|---|---|---|
| Communication volume | Communications + participants + employment | Total communications over time per company. |
| Last contact | Same | Time since last communication. |
| Key contacts | Same | Top contacts at each company by communication volume and recency. |
| Topic distribution | Conversation tags + participants | Topics/tags associated with company conversations. |
| Meeting frequency | Events + participants | How often meetings occur with company contacts. |
| Meeting-to-email ratio | Events + communications | High-touch vs. low-touch relationship indicator. |

### 7.2 Relative Time Display

Communication recency is displayed as relative time:

- Less than 30 days: "**X days**"
- Less than 12 months: "**Y months**"
- 12 months or more: "**Z years**"

**Tasks:**

- [ ] CINT-12: Implement derived metric computation (volume, last contact, key contacts)
- [ ] CINT-13: Implement topic distribution aggregation
- [ ] CINT-14: Implement meeting frequency and meeting-to-email ratio
- [ ] CINT-15: Implement relative time display formatting

**Tests:**

- [ ] CINT-T12: Test communication volume aggregation is correct
- [ ] CINT-T13: Test key contacts ranking reflects actual communication patterns
- [ ] CINT-T14: Test relative time formatting for days, months, years

---

## 8. Intelligence Views

**Supports processes:** KP-2 (all steps)

### 8.1 Requirements

Intelligence is surfaced through views (saved smart filters) rather than interruptive alerts:

| View Name | Filter Criteria |
|---|---|
| Companies — declining engagement | Relationship strength dropped >20% in 30 days |
| Companies — highest relationship strength | Top N by score, sorted descending |
| New companies — detected this week | Created in last 7 days |
| Companies — no communication in 90+ days | Last contact date > 90 days ago |
| Companies — strong & growing | Score > 0.6 AND 30-day trend positive |

Views are stored using the existing views system (Views & Grid PRD). Users can create custom views with their own filter and sort criteria tied to precomputed scores.

**Tasks:**

- [ ] CINT-16: Create default intelligence view definitions
- [ ] CINT-17: Implement score-based filter operators (>, <, trending up/down)
- [ ] CINT-18: Implement 30-day trend computation for trend-based views

**Tests:**

- [ ] CINT-T15: Test declining engagement view returns correct companies
- [ ] CINT-T16: Test no-communication view uses last contact date correctly
- [ ] CINT-T17: Test custom views with score-based filters work end-to-end
