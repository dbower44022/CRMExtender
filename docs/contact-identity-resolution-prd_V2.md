# Contact — Identity Resolution & Entity Matching Sub-PRD

**Version:** 2.0
**Last Updated:** 2026-02-22
**Status:** Draft
**Entity Base PRD:** [contact-entity-base-prd_V6.md]
**Referenced Entity PRDs:** [Company Management Entity Base PRD](company-management-prd_V1.md)
**Referenced Action Sub-PRDs:** [Contact Merge & Split Sub-PRD](contact-merge-split-prd_V1.md)

> **V2.0 (2026-02-22):** Added Key Processes section defining end-to-end user experiences for all resolution scenarios. Restructured functional sections with process linkage. Enhanced UI specifications for inline warnings, review queue, and flagged merge indicators.

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

| Field | Usage in This Action |
|---|---|
| Display Name | Fuzzy matching candidate comparison |
| First Name / Last Name | Name similarity scoring |
| Primary Email | Exact identifier matching |
| Primary Phone | Exact identifier matching |
| Job Title | Signal for fuzzy match scoring |
| Company Name | Signal for fuzzy match scoring |
| Status | Determines if contact participates in resolution |
| Lead Source | Recorded on match candidate records |

### 2.2 Relevant Relationships

- **Contact Identifiers** — The primary lookup mechanism. Every identifier (email, phone, LinkedIn URL) is checked against existing identifiers for exact matches.
- **Company** — Company affiliation is a matching signal. Shared company domain increases match confidence.

### 2.3 Relevant Lifecycle Transitions

- Identity resolution can trigger creation of new contacts (status `incomplete` for auto-created, `active` for sources with sufficient data).
- High and medium-confidence matches trigger the Merge action, which transitions the absorbed contact to `merged` status.

### 2.4 Cross-Entity Context

The entity resolution pipeline is shared between Contacts and Companies. The same matching infrastructure, confidence scoring, and review queue serve both entity types. Company resolution is detailed in the Company Management PRD; this document covers the contact-specific behavior.

---

## 3. Key Processes

This section defines the end-to-end user experience for each scenario where identity resolution is involved. The functional sections that follow (Sections 4–9) provide the mechanisms that support these processes. Each process is referenced by ID (KP-1, KP-2, etc.) throughout the document.

### KP-1: Email Sync Resolution

**Trigger:** An incoming or outgoing email is synced, and one or more participants (sender, recipient, CC) have identifiers not yet in the system.

**Step 1 — Identifier extraction:** The system extracts the email address and display name from the email participant.

**Step 2 — Exact match:** The system checks the email address against existing contact identifiers. If found, the communication is linked to the existing contact. The user sees nothing — resolution is silent on exact match. Process ends.

**Step 3 — Fuzzy match (no exact match):** The system searches for contacts with a similar name and/or matching email domain. Candidates are scored.

**Step 4a — High-confidence match (≥ 0.90):** The system auto-merges the new data into the existing contact. The user sees nothing immediately. The existing contact's data is silently updated with any new information from the email (e.g., a new email address is added as an identifier). Process ends.

**Step 4b — Medium-confidence match (0.70–0.89):** The system auto-merges the new data into the existing contact but flags the merge for review. The existing contact appears in the standard contact list as normal, but with a **"Review Merge" indicator** (small badge) visible on the contact card in list view and on the contact detail page. The user can click the indicator to review the merge and undo it if incorrect. The match also appears in the Review Queue (KP-6).

**Step 4c — Low-confidence match (0.40–0.69):** The system creates a new contact with status `incomplete` and queues the match candidate for human review. The new contact **is visible in the standard contact list** with an `incomplete` status indicator, so the user can see and work with it immediately. A **"Possible Duplicate" badge** appears on both the new contact and the existing candidate, linking to the review comparison. The match also appears in the Review Queue (KP-6).

**Step 4d — No match (< 0.40):** The system creates a new contact with status `incomplete`. The contact is visible in the standard list with the `incomplete` indicator. Auto-enrichment triggers to populate the record. Process ends.

### KP-2: Manual Creation with Duplicate Detection

**Trigger:** The user clicks "Add Contact" and enters contact details.

**Step 1 — Inline checking:** As the user enters identifying information (email, phone, name + company), the system checks for potential matches in real-time. If a potential match is found, an inline warning appears below the field: "This may be the same person as [Name] at [Company]. [View] [Merge Instead] [Create Anyway]."

**Step 2a — User selects "View":** The system shows a side-by-side comparison of the entered data and the existing contact. The user can then choose to merge or continue creating.

**Step 2b — User selects "Merge Instead":** The system redirects to the merge preview screen (see Merge & Split Sub-PRD) with the existing contact and the entered data pre-populated.

**Step 2c — User selects "Create Anyway":** The system creates the new contact. If the match confidence was in the medium or low range, a match candidate record is created for the Review Queue. The new contact appears in the standard list with a "Possible Duplicate" badge.

**Step 3 — No matches found:** The system creates the contact normally. Auto-enrichment triggers. Process ends.

### KP-3: Import with Duplicate Detection

**Trigger:** The user uploads a CSV, vCard, or LinkedIn CSV file for import.

**Step 1 — Parse and validate:** The system parses the file and validates records. Any parsing errors are reported. (See Import & Export Sub-PRD for details.)

**Step 2 — Duplicate detection:** Each parsed record is run through the resolution pipeline. Records are classified as: **New** (no match), **Update** (exact match — will merge new data into existing contact), or **Possible Duplicate** (fuzzy match found — requires user decision).

**Step 3 — Import preview:** The user sees a summary: "N new contacts, N updates to existing, N possible duplicates." Each category is expandable.

- **New records:** Listed with a green "Create" indicator. User can exclude individual records.
- **Update records:** Listed with a blue "Update" indicator showing the existing contact and what fields will be added/changed. User can exclude individual records.
- **Possible duplicates:** Listed with an orange "Review" indicator. Each shows the imported record alongside the potential match with the confidence score and matching signals. For each, the user selects: **Merge** (combine with existing), **Create Anyway** (import as a new contact), or **Skip** (do not import).

**Step 4 — Execute:** The system processes all records per the user's selections. New contacts are created. Updates are merged. "Create Anyway" records are imported as new contacts with a "Possible Duplicate" badge and a match candidate queued for the Review Queue. Skipped records are not imported.

**Step 5 — Import report:** Summary of created, updated, skipped, and errored records. (See Import & Export Sub-PRD for details.)

### KP-4: Browser Extension Capture

**Trigger:** The user visits a LinkedIn profile (or other supported platform) and the browser extension captures contact data.

**Step 1 — Data push:** The extension sends the captured data (name, title, company, LinkedIn URL, etc.) to the API.

**Step 2 — Exact match on LinkedIn URL:** If the LinkedIn URL matches an existing contact's identifier, the existing contact is updated with any new information. The extension shows a brief confirmation: "Matched to existing contact: [Name]." Process ends.

**Step 3 — Fuzzy match:** If no exact match, the system runs fuzzy matching. Results follow the same confidence tiers as KP-1 (steps 4a–4d). The extension shows the result: "New contact created: [Name]" or "Matched to existing contact: [Name] (review recommended)."

### KP-5: Enrichment Discovery

**Trigger:** An enrichment adapter returns data that links two existing contacts who were not previously identified as potential duplicates (e.g., enrichment discovers that Contact A and Contact B share a phone number).

**Step 1 — Conflict detection:** During enrichment merge, the system detects that an enriched identifier already belongs to another contact.

**Step 2 — Match candidate creation:** The system creates a match candidate record linking the two contacts, with the enrichment-discovered signal and confidence score.

**Step 3 — User visibility:** The match appears in the Review Queue (KP-6). Both contacts receive a "Possible Duplicate" badge. The contacts remain separate and fully functional in the standard list until the user resolves the match.

### KP-6: Review Queue Workflow

**Trigger:** The user navigates to the Review Queue (accessible from the main navigation, with a badge count of pending items).

**Step 1 — Queue list:** The user sees a list of pending match candidates, sorted by confidence score (highest first). Each row shows: the two contact names and primary emails, the confidence score, the primary matching signals (e.g., "Email domain match, Name fuzzy match 92%"), and the source that triggered the match (email sync, import, enrichment, etc.). A count badge on the navigation item shows pending items.

**Step 2 — Expand details:** Clicking a row expands to a side-by-side comparison showing full contact cards for both contacts, all matching signals with individual confidence scores, and the combined confidence score.

**Step 3a — Approve:** The user clicks "Merge." This triggers the standard merge flow (see Merge & Split Sub-PRD) — the user is taken to the merge preview screen to select the survivor and resolve conflicts. After merge, the candidate status updates to `approved`.

**Step 3b — Reject:** The user clicks "Not a Match." The candidate status updates to `rejected`. The "Possible Duplicate" badge is removed from both contacts. The same pair will not be re-queued by future resolution runs.

**Step 3c — Defer:** The user can skip the candidate without acting. It remains in the queue as `pending`.

### KP-7: Living with Flagged Merges

**Trigger:** The user encounters a contact in the standard list or detail view that was auto-merged with a review flag (from KP-1 step 4b or similar).

**Step 1 — Badge visibility:** The contact card in the list view and the contact detail page show a small "Review Merge" badge. This badge is distinct from the "Possible Duplicate" badge — it indicates a merge has already happened but should be verified.

**Step 2 — Badge click:** Clicking the badge opens a panel showing the merge details: which contacts were merged, what data was combined, when the merge occurred, and the confidence score that triggered it.

**Step 3a — Confirm:** The user clicks "Looks Good." The review flag is removed. The badge disappears.

**Step 3b — Undo:** The user clicks "Undo Merge." This triggers the split flow (see Merge & Split Sub-PRD) to restore the original contacts.

---

## 4. The Identity Problem

**Supports processes:** All (KP-1 through KP-7). This section defines the fundamental challenge that all key processes address.

### 4.1 Requirements

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

## 5. Matching Strategy

**Supports processes:** KP-1 (steps 3–4), KP-2 (step 1), KP-3 (step 2), KP-4 (steps 2–3), KP-5 (step 1). This section defines how the system determines whether an incoming record matches an existing contact, and the tiered confidence model that drives the user experience in each process.

### 5.1 Requirements

Identity resolution uses a **tiered confidence model** with configurable thresholds. The system first attempts exact identifier matching, then falls back to fuzzy matching when exact matches fail.

**Exact match tier:**

| Signal | Default Confidence | Default Action |
|---|---|---|
| Email address exact match | 1.0 | Auto-merge, no flag |
| LinkedIn profile URL match | 1.0 | Auto-merge, no flag |
| Phone number exact match (E.164 normalized) | 0.95 | Auto-merge, no flag |

**Fuzzy match tier:**

| Signal Combination | Default Confidence Range | Default Action |
|---|---|---|
| Name + Company + Title fuzzy match (>90% similarity) | 0.80–0.95 | Auto-merge with review flag |
| Name + Email domain match | 0.80–0.90 | Auto-merge with review flag |
| Name + Company fuzzy match (no title) | 0.60–0.80 | Auto-merge with review flag |
| Name + Location match | 0.50–0.70 | Queue for human review |
| Name-only fuzzy match | 0.20–0.50 | Queue for human review |

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

## 6. Confidence Scoring

**Supports processes:** KP-1 (step 4 tier classification), KP-2 (step 1 inline warning threshold), KP-3 (step 2 duplicate classification), KP-4 (step 3), KP-5 (step 2). The confidence score determines which user experience branch is followed in each key process — silent merge, flagged merge, review queue, or new contact creation.

### 6.1 Requirements

Each matching signal contributes a weighted confidence value. The combined confidence across multiple signals is computed using a probabilistic independence formula:

```
confidence = 1 - ((1 - s1) * (1 - s2) * ... * (1 - sN))
```

Where s1...sN are the individual signal confidences. This ensures multiple weak signals can combine to produce a strong match — for example, name + company + location together reach high confidence even though each alone is medium.

**Signal weights:**

| Signal | Weight | Notes |
|---|---|---|
| Email exact match | 1.0 | Definitive identifier |
| LinkedIn URL match | 1.0 | Definitive identifier |
| Phone E.164 match | 0.95 | Very high but not 1.0 (shared phones exist) |
| Name exact match | 0.30 | Common names reduce this weight |
| Name fuzzy match (>90%) | 0.20 | Levenshtein + phonetic |
| Company exact match | 0.25 | |
| Company fuzzy match | 0.15 | |
| Title match | 0.15 | |
| Email domain match | 0.20 | Same company domain |
| Location match | 0.10 | Same city/region |

**Threshold actions:**

| Combined Confidence | Action | User Experience |
|---|---|---|
| ≥ 0.90 | Auto-merge, no flag | Silent — user sees nothing (KP-1/4a) |
| 0.70 – 0.89 | Auto-merge with review flag | "Review Merge" badge on contact (KP-7) |
| 0.40 – 0.69 | Queue for human review | "Possible Duplicate" badge on both contacts; appears in Review Queue (KP-6) |
| < 0.40 | No match — create new contact | Contact created normally, no badges |

Thresholds are configurable per tenant. Changes apply to future matches only, not retroactively.

**Performance target:** Duplicate contact rate below 2% after entity resolution is active.

**Tasks:**

- [ ] IDENT-07: Implement weighted confidence scoring formula
- [ ] IDENT-08: Implement threshold-based action routing (auto-merge, flag, review queue, no match)
- [ ] IDENT-09: Implement tenant-configurable threshold settings
- [ ] IDENT-10: Implement threshold configuration UI in tenant settings

**Tests:**

- [ ] IDENT-T08: Multiple weak signals combine to produce high confidence (e.g., name + company + location)
- [ ] IDENT-T09: Single definitive signal (email) produces confidence 1.0 regardless of other signals
- [ ] IDENT-T10: Confidence at each threshold boundary triggers correct action
- [ ] IDENT-T11: Custom tenant thresholds override default behavior

---

## 7. Resolution Pipeline

**Supports processes:** KP-1 (full flow), KP-3 (step 2), KP-4 (steps 2–3), KP-5 (steps 1–2). This section defines the technical pipeline that all resolution scenarios flow through. Each key process enters the pipeline at the Identifier Extraction stage and exits at the Action Execution stage, where the confidence tier determines the user experience branch.

### 7.1 Requirements

The end-to-end pipeline processes incoming data through five stages:

1. **Identifier Extraction** — Extract email, phone, name, company, title, and social URLs from the incoming data regardless of source.

2. **Exact Match Lookup** — Check extracted identifiers against existing contact_identifiers. If an exact match is found, the existing contact is returned. Processing stops here for exact matches.

3. **Fuzzy Match Candidates** — When no exact match is found, search for potential matches using name + company similarity. Return the top-N candidates (configurable, default 10).

4. **Confidence Scoring** — Score each candidate using the weighted signal combination. Apply tenant threshold settings to classify each candidate into auto-merge, auto-merge with flag, human review, or no match.

5. **Action Execution** — Based on the confidence tier:
   - **Auto-merge (≥ 0.90):** Trigger the Merge action silently (see Merge & Split Sub-PRD). No user-visible indicators.
   - **Auto-merge with flag (0.70–0.89):** Trigger the Merge action and create a review flag on the surviving contact. "Review Merge" badge appears per KP-7.
   - **Human review (0.40–0.69):** Create a new contact and a match candidate record. "Possible Duplicate" badges appear on both contacts per KP-1 step 4c. Match appears in Review Queue per KP-6.
   - **No match (< 0.40):** Create a new contact with no badges.

**Pipeline must be idempotent** — processing the same incoming data twice should not create duplicates or duplicate merge candidates.

**Match candidate records** track each potential match pair with:
- The two entity IDs being compared
- The combined confidence score
- The individual match signals with their weights and matched values
- Status: `pending`, `approved`, `rejected`, or `auto_merged`
- Reviewer identity and timestamp if manually reviewed
- Source that triggered the match (email_sync, import, enrichment, manual_entry, browser_extension)

**Entity resolution accuracy targets:**
- High-confidence auto-merges: > 95% correct
- Medium-confidence auto-merges with flag: > 80% correct
- User correction rate declining to < 10% after 90 days

**Tasks:**

- [ ] IDENT-11: Implement end-to-end resolution pipeline orchestration (5 stages)
- [ ] IDENT-12: Implement match candidate record creation for review queue entries
- [ ] IDENT-13: Ensure pipeline idempotency (no duplicate candidates or contacts on re-processing)
- [ ] IDENT-14: Implement pipeline entry points for each data source (email sync, import, enrichment, manual entry, browser extension)
- [ ] IDENT-15: Implement "Possible Duplicate" badge on contacts with pending match candidates
- [ ] IDENT-16: Implement "Review Merge" badge on contacts with flagged auto-merges

**Tests:**

- [ ] IDENT-T12: Full pipeline processes incoming email participant and resolves to existing contact
- [ ] IDENT-T13: Full pipeline processes unknown person and creates new contact
- [ ] IDENT-T14: Pipeline creates match candidate record for medium-confidence matches
- [ ] IDENT-T15: Re-processing identical data does not create duplicates
- [ ] IDENT-T16: Pipeline handles concurrent resolution of the same person from two sources
- [ ] IDENT-T17: "Possible Duplicate" badge appears on contacts with pending match candidates
- [ ] IDENT-T18: "Review Merge" badge appears on contacts with flagged auto-merges
- [ ] IDENT-T19: Badges are removed when match candidate is resolved (approved or rejected)

---

## 8. Inline Duplicate Detection

**Supports processes:** KP-2 (steps 1–2). This section defines the real-time duplicate detection that occurs during manual contact creation, providing immediate feedback before the contact is saved.

### 8.1 Requirements

When a user is creating a new contact, the system checks for potential duplicates in real-time as identifying fields are entered:

- **On email entry:** After the user enters an email address and moves to the next field, the system checks for an exact email match and fuzzy matches by name + domain.
- **On phone entry:** After the user enters a phone number, the system checks for an exact phone match.
- **On name + company entry:** After both name and company fields have values, the system checks for fuzzy name + company matches.

If one or more potential matches are found, an inline warning appears below the triggering field:

> ⚠️ This may be the same person as **[Name]** at **[Company]** (confidence: [score]). [View Comparison] [Merge Instead] [Create Anyway]

If multiple potential matches are found, the warning lists them with individual confidence scores.

**Business rules:**
- Inline checking is debounced (300ms delay after the user stops typing) to avoid excessive API calls.
- Only active and incomplete contacts are eligible as match candidates (not archived or merged).
- The warning does not block contact creation — the user can always choose "Create Anyway."
- If the user selects "Create Anyway" for a medium or low-confidence match, a match candidate record is created for the Review Queue and a "Possible Duplicate" badge is applied.

### 8.2 UI Specifications

The inline warning appears as a dismissible banner below the field that triggered the match. It is styled as an informational alert (not an error) so it doesn't alarm the user. The "View Comparison" link opens a modal with side-by-side cards. "Merge Instead" navigates to the merge preview. "Create Anyway" dismisses the warning and allows the save to proceed.

**Tasks:**

- [ ] IDENT-17: Implement real-time duplicate detection API for contact creation form
- [ ] IDENT-18: Implement debounced field-level checking (email, phone, name+company)
- [ ] IDENT-19: Implement inline warning UI with View/Merge/Create actions
- [ ] IDENT-20: Implement side-by-side comparison modal from inline warning

**Tests:**

- [ ] IDENT-T20: Entering a known email shows inline duplicate warning
- [ ] IDENT-T21: Entering a known phone shows inline duplicate warning
- [ ] IDENT-T22: Entering matching name + company shows inline fuzzy match warning
- [ ] IDENT-T23: "Create Anyway" on medium-confidence match creates match candidate for Review Queue
- [ ] IDENT-T24: "Merge Instead" redirects to merge preview with pre-populated data
- [ ] IDENT-T25: No warning shown when entered data has no matches
- [ ] IDENT-T26: Inline check is debounced (no API call on every keystroke)

---

## 9. Human Review Queue

**Supports processes:** KP-6 (full flow), KP-1 (step 4c destination), KP-3 (step 4 destination for "Create Anyway"), KP-5 (step 3 destination). This is the central location where users resolve match candidates that were not confident enough for auto-merge.

### 9.1 Requirements

Match candidates with confidence between 0.40 and 0.69 (or created by "Create Anyway" actions in other processes) are queued for human review.

**Queue navigation entry point:** The Review Queue is accessible from the main navigation. A badge on the navigation item shows the count of pending candidates. If the count is zero, the badge is hidden.

**Queue list view:** Pending candidates are listed, sorted by confidence score (highest first) by default. The list is also sortable by creation date and source. Each row shows:
- The two contact names and primary email addresses
- The combined confidence score
- The primary matching signals in plain language (e.g., "Name 92% similar, same email domain")
- The source that triggered the match (e.g., "Email sync," "CSV import," "Enrichment")
- Approve and Reject action buttons

**Detail expansion:** Clicking a row expands to a full side-by-side comparison showing:
- Complete contact cards for both contacts with all available data
- All matching signals with individual confidence scores and the specific values that matched
- The combined confidence score and the formula breakdown
- A timeline showing when each contact was created and what data sources contributed

**Actions:**
- **Approve (Merge):** Redirects to the merge preview screen (see Merge & Split Sub-PRD) with the two contacts pre-loaded. After merge completes, the candidate status updates to `approved` and "Possible Duplicate" badges are removed.
- **Reject (Not a Match):** Marks the candidate as `rejected`. Removes "Possible Duplicate" badges from both contacts. The same pair will not be re-queued by future resolution runs.
- **Defer (Skip):** The candidate remains `pending` in the queue. No badges are changed.

**Business rules:**
- Review queue is scoped to the current tenant.
- Rejected pairs are permanently excluded from re-queuing (stored as rejected match candidates).
- When one contact in a pair is merged with a different contact (outside the review queue), the pending candidate is automatically resolved and removed from the queue.

### 9.2 UI Specifications

The review queue uses the standard list view component. The expand/collapse detail view uses the same side-by-side card layout as the merge preview. Action buttons are prominent and color-coded: green for Approve, red for Reject. An "Undo" option appears briefly after rejection in case of accidental clicks.

**Tasks:**

- [ ] IDENT-21: Implement review queue backend (list, filter, sort pending candidates)
- [ ] IDENT-22: Implement review queue navigation entry point with pending count badge
- [ ] IDENT-23: Implement review queue list view with confidence, signals, and source display
- [ ] IDENT-24: Implement expandable detail view with side-by-side comparison
- [ ] IDENT-25: Implement approve action (redirects to merge preview, updates candidate status)
- [ ] IDENT-26: Implement reject action (marks as rejected, removes badges, prevents re-queuing)
- [ ] IDENT-27: Implement auto-resolution of candidates when one contact is merged elsewhere
- [ ] IDENT-28: Implement undo option after rejection

**Tests:**

- [ ] IDENT-T27: Review queue lists only pending candidates for current tenant
- [ ] IDENT-T28: Navigation badge shows correct count of pending candidates
- [ ] IDENT-T29: Queue sorts by confidence score (default) and by date
- [ ] IDENT-T30: Expanding a row shows full side-by-side comparison with all signals
- [ ] IDENT-T31: Approving a candidate redirects to merge preview and updates status to approved
- [ ] IDENT-T32: Rejecting a candidate removes "Possible Duplicate" badges from both contacts
- [ ] IDENT-T33: Rejecting a candidate prevents the same pair from being re-queued
- [ ] IDENT-T34: Pending candidate auto-resolves when one contact is merged with a different contact
- [ ] IDENT-T35: Undo after rejection restores candidate to pending status

---

## 10. Flagged Merge Review

**Supports processes:** KP-7 (full flow). This section defines how users discover and act on auto-merges that were flagged for review — merges the system was confident enough to execute but not certain enough to leave unreviewed.

### 10.1 Requirements

When a merge is executed with a review flag (confidence 0.70–0.89), the surviving contact receives a "Review Merge" indicator. This is distinct from the "Possible Duplicate" indicator — it means a merge has already happened and the user should verify it was correct.

**Badge placement:** The "Review Merge" badge appears:
- On the contact card in any list view (small icon/badge near the contact name)
- On the contact detail page (prominent banner at the top of the page)

**Badge interaction (detail page):** Clicking the banner or badge on the detail page opens a panel showing:
- Which contacts were merged (names, primary emails)
- When the merge occurred
- The confidence score and matching signals that triggered it
- What data was combined from the absorbed contact
- Two actions: "Looks Good" and "Undo Merge"

**Actions:**
- **Looks Good:** Removes the review flag and the badge. The merge is confirmed.
- **Undo Merge:** Triggers the split flow (see Merge & Split Sub-PRD) to restore the absorbed contact as a separate record.

**Business rules:**
- Flagged merges also appear in the Review Queue as a separate "Flagged Merges" tab, so users can review them in bulk.
- If a flagged merge is not reviewed within 30 days, the flag is auto-confirmed (the badge is removed), under the assumption that if the user hasn't noticed a problem in 30 days, the merge was correct.
- The 30-day auto-confirmation period is configurable per tenant.

**Tasks:**

- [ ] IDENT-29: Implement "Review Merge" badge on contact cards in list views
- [ ] IDENT-30: Implement "Review Merge" banner on contact detail page
- [ ] IDENT-31: Implement merge details panel (merged contacts, signals, data combined)
- [ ] IDENT-32: Implement "Looks Good" action (remove review flag and badge)
- [ ] IDENT-33: Implement "Undo Merge" action (triggers split flow)
- [ ] IDENT-34: Implement "Flagged Merges" tab in Review Queue
- [ ] IDENT-35: Implement 30-day auto-confirmation for unreviewed flagged merges

**Tests:**

- [ ] IDENT-T36: Flagged auto-merge shows "Review Merge" badge in list view
- [ ] IDENT-T37: Flagged auto-merge shows banner on contact detail page
- [ ] IDENT-T38: Merge details panel shows correct merged contacts, signals, and timeline
- [ ] IDENT-T39: "Looks Good" removes the badge and review flag
- [ ] IDENT-T40: "Undo Merge" triggers split and restores original contacts
- [ ] IDENT-T41: Flagged merges appear in Review Queue "Flagged Merges" tab
- [ ] IDENT-T42: Unreviewed flagged merge auto-confirms after 30 days
- [ ] IDENT-T43: Auto-confirmation period respects tenant configuration
