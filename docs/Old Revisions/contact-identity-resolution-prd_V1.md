# Contact — Identity Resolution & Entity Matching Sub-PRD

**Version:** 1.0
**Last Updated:** 2026-02-22
**Status:** Draft
**Entity Base PRD:** [contact-entity-base-prd.md]
**Referenced Entity PRDs:** [Company Management Entity Base PRD](company-management-prd_V1.md)

---

## 1. Overview

### 1.1 Purpose

A single person may appear in CRMExtender through multiple channels with different identifiers — Google Contacts sync, email sender resolution, LinkedIn browser capture, enrichment APIs, CSV import, and manual entry. Without identity resolution, each appearance creates a separate contact record, fragmenting communication history and intelligence across duplicates.

Identity resolution determines when records from different sources refer to the same real-world person and either merges them automatically or queues them for human review. This is the mechanism that maintains the "unified contact identity" design goal — every person resolves to a single canonical record.

### 1.2 Preconditions

- Contact identifiers model is operational (types, values, lifecycle tracking, confidence scoring).
- At least one data source is producing incoming contact data (email sync, import, enrichment, manual entry).

---

## 2. Context

### 2.1 Relevant Fields

| Field                  | Usage in This Action                             |
| ---------------------- | ------------------------------------------------ |
| Display Name           | Fuzzy matching candidate comparison              |
| First Name / Last Name | Name similarity scoring                          |
| Primary Email          | Exact identifier matching                        |
| Primary Phone          | Exact identifier matching                        |
| Job Title              | Signal for fuzzy match scoring                   |
| Company Name           | Signal for fuzzy match scoring                   |
| Status                 | Determines if contact participates in resolution |
| Lead Source            | Recorded on match candidate records              |

### 2.2 Relevant Relationships

- **Contact Identifiers** — The primary lookup mechanism. Every identifier (email, phone, LinkedIn URL) is checked against existing identifiers for exact matches.
- **Company** — Company affiliation is a matching signal. Shared company domain increases match confidence.

### 2.3 Relevant Lifecycle Transitions

- Identity resolution can trigger creation of new contacts (status `incomplete` for auto-created, `active` for sources with sufficient data).
- High and medium-confidence matches trigger the Merge action, which transitions the absorbed contact to `merged` status.

### 2.4 Cross-Entity Context

The entity resolution pipeline is shared between Contacts and Companies. The same matching infrastructure, confidence scoring, and review queue serve both entity types. Company resolution is detailed in the Company Management PRD; this document covers the contact-specific behavior.

---

## 3. The Identity Problem

### 3.1 Requirements

A single person may appear through multiple channels with varying identifiers:

- Google Contacts: "Sarah Chen" with sarah@acmecorp.com
- Email sender: "Sarah" with sarah.chen@acmecorp.com
- LinkedIn capture: Sarah Chen, VP Engineering at Acme Corp, linkedin.com/in/sarahchen
- Apollo enrichment: Sarah Chen, sarah@acmecorp.com, +1-555-0199
- Manual entry: Sarah Chen, Acme Corp, sarahc@gmail.com

The system must resolve all five appearances to a single contact record with all identifiers preserved, all source attributions maintained, and the highest-quality data from each source combined.

**User stories:**

- As a user, I want the system to automatically detect when two contact records refer to the same person and merge them, so I don't have duplicate records.
- As a user, I want to review suggested merges and approve or reject them, so the system doesn't merge contacts incorrectly.
- As a user, I want to configure the auto-merge confidence threshold, so I can balance automation vs. review volume for my team's data quality needs.

**Tasks:**

- [ ] IDENT-01: Implement identifier extraction from all incoming data sources (email, phone, name, company, title, social URLs)
- [ ] IDENT-02: Implement exact match lookup against contact_identifiers for email, phone, and LinkedIn URL
- [ ] IDENT-03: Implement auto-creation flow for unmatched identifiers (new contact with appropriate status and enrichment trigger)

**Tests:**

- [ ] IDENT-T01: Incoming email with known address resolves to existing contact
- [ ] IDENT-T02: Incoming email with unknown address creates new incomplete contact
- [ ] IDENT-T03: Auto-created contact triggers enrichment pipeline

---

## 4. Matching Strategy

### 4.1 Requirements

Identity resolution uses a **tiered confidence model** with configurable thresholds. The system first attempts exact identifier matching, then falls back to fuzzy matching when exact matches fail.

**Exact match tier:**

| Signal                                      | Default Confidence | Default Action      |
| ------------------------------------------- | ------------------ | ------------------- |
| Email address exact match                   | 1.0                | Auto-merge, no flag |
| LinkedIn profile URL match                  | 1.0                | Auto-merge, no flag |
| Phone number exact match (E.164 normalized) | 0.95               | Auto-merge, no flag |

**Fuzzy match tier:**

| Signal Combination                                   | Default Confidence Range | Default Action              |
| ---------------------------------------------------- | ------------------------ | --------------------------- |
| Name + Company + Title fuzzy match (>90% similarity) | 0.80–0.95                | Auto-merge with review flag |
| Name + Email domain match                            | 0.80–0.90                | Auto-merge with review flag |
| Name + Company fuzzy match (no title)                | 0.60–0.80                | Auto-merge with review flag |
| Name + Location match                                | 0.50–0.70                | Queue for human review      |
| Name-only fuzzy match                                | 0.20–0.50                | Queue for human review      |

**Tasks:**

- [ ] IDENT-04: Implement exact match tier (email, LinkedIn URL, phone)
- [ ] IDENT-05: Implement fuzzy match candidate retrieval (name + company similarity via search)
- [ ] IDENT-06: Return top-N fuzzy match candidates for confidence scoring

**Tests:**

- [ ] IDENT-T04: Exact email match returns confidence 1.0 and triggers auto-merge
- [ ] IDENT-T05: Exact phone match (E.164) returns confidence 0.95
- [ ] IDENT-T06: Fuzzy name + company match returns appropriate confidence range
- [ ] IDENT-T07: Name-only fuzzy match returns low confidence and queues for review

---

## 5. Confidence Scoring

### 5.1 Requirements

Each matching signal contributes a weighted confidence value. The combined confidence across multiple signals is computed using a probabilistic independence formula:

```
confidence = 1 - ((1 - s1) * (1 - s2) * ... * (1 - sN))
```

Where s1...sN are the individual signal confidences. This ensures multiple weak signals can combine to produce a strong match — for example, name + company + location together reach high confidence even though each alone is medium.

**Signal weights:**

| Signal                  | Weight | Notes                                       |
| ----------------------- | ------ | ------------------------------------------- |
| Email exact match       | 1.0    | Definitive identifier                       |
| LinkedIn URL match      | 1.0    | Definitive identifier                       |
| Phone E.164 match       | 0.95   | Very high but not 1.0 (shared phones exist) |
| Name exact match        | 0.30   | Common names reduce this weight             |
| Name fuzzy match (>90%) | 0.20   | Levenshtein + phonetic                      |
| Company exact match     | 0.25   |                                             |
| Company fuzzy match     | 0.15   |                                             |
| Title match             | 0.15   |                                             |
| Email domain match      | 0.20   | Same company domain                         |
| Location match          | 0.10   | Same city/region                            |

**Threshold actions:**

| Combined Confidence | Action                        |
| ------------------- | ----------------------------- |
| ≥ 0.90              | Auto-merge, no flag           |
| 0.70 – 0.89         | Auto-merge with review flag   |
| 0.40 – 0.69         | Queue for human review        |
| < 0.40              | No match — create new contact |

Thresholds are configurable per tenant. Changes apply to future matches only, not retroactively.

**Performance target:** Duplicate contact rate below 2% after entity resolution is active.

**Tasks:**

- [ ] IDENT-07: Implement weighted confidence scoring formula
- [ ] IDENT-08: Implement threshold-based action routing (auto-merge, flag, review queue, no match)
- [ ] IDENT-09: Implement tenant-configurable threshold settings

**Tests:**

- [ ] IDENT-T08: Multiple weak signals combine to produce high confidence (e.g., name + company + location)
- [ ] IDENT-T09: Single definitive signal (email) produces confidence 1.0 regardless of other signals
- [ ] IDENT-T10: Confidence at each threshold boundary triggers correct action
- [ ] IDENT-T11: Custom tenant thresholds override default behavior

---

## 6. Resolution Pipeline

### 6.1 Requirements

The end-to-end pipeline processes incoming data through five stages:

1. **Identifier Extraction** — Extract email, phone, name, company, title, and social URLs from the incoming data regardless of source.

2. **Exact Match Lookup** — Check extracted identifiers against existing contact_identifiers. If an exact match is found, the existing contact is returned. Processing stops here for exact matches.

3. **Fuzzy Match Candidates** — When no exact match is found, search for potential matches using name + company similarity. Return the top-N candidates (configurable, default 10).

4. **Confidence Scoring** — Score each candidate using the weighted signal combination. Apply tenant threshold settings to classify each candidate into auto-merge, auto-merge with flag, human review, or no match.

5. **Action Execution** — For auto-merge candidates, trigger the Merge action (see Merge & Split Sub-PRD). For review candidates, create a match candidate record in the review queue. For no-match results, create a new contact.

**Pipeline must be idempotent** — processing the same incoming data twice should not create duplicates or duplicate merge candidates.

**Match candidate records** track each potential match pair with:

- The two entity IDs being compared
- The combined confidence score
- The individual match signals with their weights and matched values
- Status: pending, approved, rejected, or auto_merged
- Reviewer identity and timestamp if manually reviewed

**Entity resolution accuracy targets:**

- High-confidence auto-merges: > 95% correct
- Medium-confidence auto-merges with flag: > 80% correct
- User correction rate declining to < 10% after 90 days

**Tasks:**

- [ ] IDENT-10: Implement end-to-end resolution pipeline orchestration (5 stages)
- [ ] IDENT-11: Implement match candidate record creation for review queue entries
- [ ] IDENT-12: Ensure pipeline idempotency (no duplicate candidates or contacts on re-processing)
- [ ] IDENT-13: Implement pipeline entry points for each data source (email sync, import, enrichment, manual entry, browser extension)

**Tests:**

- [ ] IDENT-T12: Full pipeline processes incoming email participant and resolves to existing contact
- [ ] IDENT-T13: Full pipeline processes unknown person and creates new contact
- [ ] IDENT-T14: Pipeline creates match candidate record for medium-confidence matches
- [ ] IDENT-T15: Re-processing identical data does not create duplicates
- [ ] IDENT-T16: Pipeline handles concurrent resolution of the same person from two sources

---

## 7. Human Review Queue

### 7.1 Requirements

Match candidates below the auto-merge threshold are queued for human review. The review interface shows:

- Side-by-side contact cards for each candidate pair
- Match signals with individual confidence scores and the values that matched
- Combined confidence score
- One-click approve (triggers merge) or reject actions

**Business rules:**

- Review queue is filtered by tenant
- Queue is sortable by confidence score and creation date
- Rejected candidates are recorded so the same pair is not re-queued
- Approved candidates trigger the standard Merge action

### 7.2 UI Specifications

The review queue is a list view showing pending candidates ranked by confidence (highest first). Each row shows the two contact names, the confidence score, the primary match signals, and approve/reject buttons. Clicking a row expands to the full side-by-side comparison.

**Tasks:**

- [ ] IDENT-14: Implement review queue backend (list, filter, sort pending candidates)
- [ ] IDENT-15: Implement approve action (triggers merge, updates candidate status)
- [ ] IDENT-16: Implement reject action (marks as rejected, prevents re-queuing of same pair)
- [ ] IDENT-17: Implement review queue UI (list view, side-by-side comparison, approve/reject)

**Tests:**

- [ ] IDENT-T17: Review queue lists only pending candidates for current tenant
- [ ] IDENT-T18: Approving a candidate triggers merge and updates status to approved
- [ ] IDENT-T19: Rejecting a candidate prevents the same pair from being re-queued
- [ ] IDENT-T20: Queue sorts correctly by confidence and date
