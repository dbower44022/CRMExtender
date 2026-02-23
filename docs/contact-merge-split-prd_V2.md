# Contact — Merge & Split Sub-PRD

**Version:** 2.0
**Last Updated:** 2026-02-22
**Status:** Draft
**Entity Base PRD:** [contact-entity-base-prd_V7.md]
**Referenced Entity PRDs:** [Company Management Entity Base PRD](company-management-prd_V1.md), [Communications PRD](communications-prd_V3.md), [Conversations PRD](conversations-prd_V4.md)
**Referenced Action Sub-PRDs:** [Contact Identity Resolution Sub-PRD](contact-identity-resolution-prd_V2.md)

> **V2.0 (2026-02-22):** Added Key Processes section defining end-to-end user experiences for all merge and split scenarios. Restructured functional sections with process linkage.

---

## 1. Overview

### 1.1 Purpose

Merge combines two or more duplicate contact records into a single surviving record, preserving all data and maintaining referential integrity across the system. Split reverses an incorrect merge by restoring the original contact records from event history. Together, these actions ensure data quality while providing a safety net for mistakes.

Merge is triggered either automatically by the identity resolution pipeline (high and medium-confidence matches) or manually by the user when they notice duplicates.

### 1.2 Preconditions

- **Merge:** At least two contact records exist that represent the same person.
- **Split:** A merge has previously been executed and the audit trail (absorbed contact snapshot) is intact.

---

## 2. Context

### 2.1 Relevant Fields

All fields on the contact record are relevant to merge — the surviving contact inherits the best data from all merged records. Key fields requiring conflict resolution: Display Name, First Name, Last Name, Source, and Lead Status.

### 2.2 Relevant Relationships

Merge must transfer and deduplicate across all entity relationships:
- **Contact Identifiers** — All identifiers from absorbed contacts transfer to the survivor, deduplicated by type + value.
- **Employment History** — Employment records transfer, deduplicated by company + start date.
- **Communications** — Communication participant references are re-pointed to the surviving contact.
- **Conversations** — Conversation participant references are re-pointed to the surviving contact.
- **Deals** — Deal stakeholder references are re-pointed.
- **Events** — Event participant references are re-pointed.
- **Groups** — Group memberships transfer, deduplicated.
- **Tags** — Tag assignments transfer, deduplicated.
- **Notes** — Notes transfer to the surviving contact.
- **Documents** — Document attachments transfer.
- **Contact-to-Contact Relationships** — Graph relationship edges are re-pointed, deduplicated, and self-referential relationships removed.
- **Enrichment data** — Enrichment run history transfers; entity scores for absorbed contacts are removed.
- **Visibility/permissions** — User-contact visibility records transfer.

### 2.3 Relevant Lifecycle Transitions

- The absorbed contact transitions to `merged` status.
- The surviving contact remains `active` (or its current status).
- Split transitions the restored contact from `merged` back to `active`.

---

## 3. Key Processes

### KP-1: Manual Merge from List Selection

**Trigger:** The user notices duplicate contacts in the list view and wants to combine them.

**Step 1 — Selection:** The user selects 2 or more contacts via checkboxes in the contact list view. The bulk action bar appears with a "Merge Selected" button.

**Step 2 — Merge preview:** Clicking "Merge Selected" opens the merge preview screen. The user sees side-by-side contact cards for all selected contacts with per-contact counts (emails, phones, employment records, conversations, relationships, etc.). Fields with different values across the contacts are highlighted as conflicts.

**Step 3 — Survivor selection:** The user selects which contact should be the survivor (which ID persists) via radio buttons. The survivor card is visually emphasized.

**Step 4 — Conflict resolution:** For each conflicting field (name, source, etc.), the user selects which value the surviving contact should have via radio buttons. A "Combined Result" summary shows what the merged contact will look like.

**Step 5 — Confirmation:** The user clicks "Confirm Merge." The system executes the merge atomically.

**Step 6 — Redirect:** The user is redirected to the surviving contact's detail page, which now shows the combined data. A success banner confirms "Merged [N] contacts. [Undo]" with a brief undo window.

### KP-2: Merge from Identifier Conflict

**Trigger:** The user is editing a contact and adds an email address that already belongs to another contact.

**Step 1 — Error with merge link:** The system shows an error: "This email belongs to [Name]. [Merge these contacts?]"

**Step 2 — Merge preview:** Clicking "Merge these contacts?" opens the same merge preview screen as KP-1 step 2, pre-populated with the current contact and the conflicting contact.

**Steps 3–6:** Same as KP-1 steps 3–6.

### KP-3: Auto-Merge from Identity Resolution

**Trigger:** The identity resolution pipeline (see Identity Resolution Sub-PRD) determines that incoming data matches an existing contact with high or medium confidence.

**Step 1 — Automatic execution:** The system executes the merge without user interaction. The incoming data is absorbed into the existing contact.

**Step 2a — High confidence (silent):** No user-visible indication. The contact is silently updated.

**Step 2b — Medium confidence (flagged):** The surviving contact receives a "Review Merge" badge. The user discovers this during normal browsing (see Identity Resolution Sub-PRD, KP-7).

### KP-4: Splitting (Undoing) a Merge

**Trigger:** The user discovers that a merge was incorrect and wants to restore the original contacts.

**Step 1 — Merge history:** On the surviving contact's detail page, the user opens the "Merge History" section (accessible from the action bar or an activity timeline entry). This shows a chronological list of all merges involving this contact.

**Step 2 — Select merge to undo:** Each merge entry shows the absorbed contact's name, primary email, merge date, and confidence score (if auto-merged). The user clicks "Undo Merge" on the entry they want to reverse.

**Step 3 — Confirmation:** A dialog explains what will happen: "This will restore [Name] as a separate contact with their original data. Communications created after the merge will remain with [surviving contact name]."

**Step 4 — Split execution:** The system restores the absorbed contact from the audit trail snapshot. The user sees a success message: "Restored [Name] as a separate contact. [View]"

**Step 5 — Navigation:** The user can click "View" to navigate to the restored contact's detail page, or remain on the surviving contact's page.

---

## 4. Merge Entry Points

**Supports processes:** KP-1 (step 1), KP-2 (step 1), KP-3 (step 1).

### 4.1 Requirements

Merge can be initiated from three entry points:

1. **List selection** — User selects 2 or more contacts via checkboxes on the Contact list view, then clicks "Merge Selected."
2. **Identifier conflict** — When adding an email address to a contact that already belongs to another contact, the error message includes a "Merge these contacts?" link.
3. **Identity resolution** — Automatic merge triggered by the resolution pipeline for high and medium-confidence matches (see Identity Resolution Sub-PRD).

All entry points lead to the same merge preview screen (for manual merges) or execute silently (for auto-merges).

**User story:** As a user, I want to manually merge two contacts when I notice duplicates, so I can clean up my data.

**Tasks:**

- [ ] MERGE-01: Implement merge entry point from list view multi-select
- [ ] MERGE-02: Implement merge entry point from identifier conflict error message
- [ ] MERGE-03: Implement merge entry point from identity resolution pipeline (auto-triggered)

**Tests:**

- [ ] MERGE-T01: Selecting 2+ contacts in list view enables "Merge Selected" action
- [ ] MERGE-T02: Adding a conflicting email shows merge link in error message
- [ ] MERGE-T03: High-confidence identity resolution match triggers merge flow

---

## 5. Merge Preview

**Supports processes:** KP-1 (steps 2–4), KP-2 (step 2).

### 5.1 Requirements

Before execution, the user reviews a merge preview showing:

- **Side-by-side contact cards** for all contacts being merged, with per-contact counts of identifiers, employment records, conversations, relationships, events, phones, addresses, emails, and social profiles.
- **Conflict resolution controls** — Radio buttons for fields where the contacts have distinct values (name, source). The user selects which value the surviving contact should have.
- **Survivor designation** — Radio buttons to choose which contact ID persists as the surviving record.
- **Combined totals** — A summary showing the merged result with deduplicated counts.

The preview is non-destructive — no data changes until the user confirms.

### 5.2 UI Specifications

The merge preview is a dedicated screen. Contact cards are displayed side by side (or stacked on mobile). Each card shows the contact's key fields and sub-entity counts. Fields with conflicts are highlighted with a distinct background color. The survivor selection is prominent at the top. The "Combined Result" panel updates dynamically as the user makes conflict resolution choices. A "Confirm Merge" button executes the merge; a "Cancel" button returns to the previous screen.

**Tasks:**

- [ ] MERGE-04: Implement merge preview data assembly (side-by-side comparison with counts)
- [ ] MERGE-05: Implement conflict detection across all fields
- [ ] MERGE-06: Implement merge preview UI with conflict resolution controls and survivor selection
- [ ] MERGE-07: Implement combined/deduplicated total calculation for preview
- [ ] MERGE-08: Implement dynamic "Combined Result" panel

**Tests:**

- [ ] MERGE-T04: Preview correctly identifies conflicting fields between two contacts
- [ ] MERGE-T05: Preview shows accurate sub-entity counts per contact
- [ ] MERGE-T06: Preview combined totals reflect deduplication (e.g., shared email counted once)
- [ ] MERGE-T07: Preview supports 3+ contacts in multi-merge scenario
- [ ] MERGE-T08: Combined Result panel updates when user changes conflict resolution choices

---

## 6. Merge Execution

**Supports processes:** KP-1 (step 5), KP-2 (steps 3–5 via KP-1), KP-3 (step 1).

### 6.1 Requirements

Merge execution processes all absorbed contacts in a single database transaction. For each absorbed contact:

1. Snapshot the absorbed contact and all sub-entities as JSON (audit trail).
2. Transfer and deduplicate identifiers — remove conflicts by type + value, update remaining to surviving contact.
3. Transfer and deduplicate employment records — remove conflicts by company + start date, update remaining to surviving contact.
4. Transfer and deduplicate social profiles — remove conflicts by platform + profile URL, update remaining.
5. Reassign communication participants to the surviving contact.
6. Reassign conversation participants to the surviving contact.
7. Reassign all relationship instances across all Relation Type junction tables where the absorbed contact appears. Deduplicate pairs that become identical after reassignment. Delete self-referential relationships that result from merging two contacts who had a relationship between them.
8. Reassign event participants.
9. Transfer and deduplicate phones (by normalized number), addresses, and emails (by lowercased email).
10. Transfer user-contact visibility records.
11. Transfer enrichment run history; delete entity scores for absorbed contact.
12. Re-point any prior merge audit records that reference the absorbed contact.
13. Delete the absorbed contact record (cascade handles remaining child rows).
14. Write audit record to the merges table.

After all absorbed contacts are processed:

15. Apply the user's chosen field values (name, source) on the surviving contact.
16. **Post-merge domain resolution** — Resolve email domains from all merged identifiers and auto-create missing company affiliations. This handles the common case where two contacts from different companies are merged — both affiliations are preserved.
17. Redirect to the surviving contact's detail page.

**Business rules:**
- The entire merge is atomic — if any step fails, the transaction rolls back and no data changes.
- When a contact has multiple email identifiers after merge, the primary email is selected by `is_primary DESC, created_at ASC`.
- Employment deduplication uses `(company_id, COALESCE(started_at, ''))` — null start dates are treated as equal.

**Performance target:** Merge must be fast enough to handle batch merges during import (> 1,000 contacts per minute throughput).

**Tasks:**

- [ ] MERGE-09: Implement atomic merge transaction with full sub-entity transfer
- [ ] MERGE-10: Implement identifier deduplication during transfer (type + value)
- [ ] MERGE-11: Implement employment record deduplication during transfer (company + start date)
- [ ] MERGE-12: Implement relationship reassignment with deduplication and self-referential cleanup
- [ ] MERGE-13: Implement communication and conversation participant reassignment
- [ ] MERGE-14: Implement post-merge domain resolution for auto-creating missing company affiliations
- [ ] MERGE-15: Implement merge audit record with full absorbed contact snapshot
- [ ] MERGE-16: Implement primary email selection after merge (is_primary DESC, created_at ASC)
- [ ] MERGE-17: Implement success banner with undo link on redirect

**Tests:**

- [ ] MERGE-T09: Merge transfers all identifiers to surviving contact
- [ ] MERGE-T10: Duplicate identifiers (same email on both contacts) are deduplicated, not duplicated
- [ ] MERGE-T11: Employment records are deduplicated by company + start date
- [ ] MERGE-T12: Communication participants re-pointed to surviving contact
- [ ] MERGE-T13: Conversation participants re-pointed to surviving contact
- [ ] MERGE-T14: Relationship self-referential edges removed after merge
- [ ] MERGE-T15: Merge transaction rolls back completely on failure
- [ ] MERGE-T16: Post-merge domain resolution creates missing company affiliations
- [ ] MERGE-T17: Audit record contains complete snapshot of absorbed contact
- [ ] MERGE-T18: Multi-contact merge (3+) processes all absorbed contacts correctly

---

## 7. Split (Undo Merge)

**Supports processes:** KP-4 (full flow).

### 7.1 Requirements

Split reverses a merge by restoring the absorbed contact from the audit trail snapshot. The split operation:

1. Retrieves the absorbed contact snapshot from the merge audit record.
2. Recreates the absorbed contact record from the snapshot.
3. Re-links identifiers, employment records, and other sub-entities that originally belonged to the absorbed contact back to the restored record.
4. Re-points communication and conversation participants that originally belonged to the absorbed contact.
5. Restores graph relationships that were reassigned during merge.
6. Updates the merge audit record to reflect the split.
7. Emits a ContactsSplit event.

**Business rules:**
- Split is only available for merges where the audit snapshot is intact.
- Communications and conversations created after the merge remain linked to the surviving contact — the split only restores pre-merge assignments.
- If data was modified on the surviving contact after the merge (e.g., a transferred identifier was edited), the split uses the current state rather than the snapshot state for that data point.

**User story:** As a user, I want to split a contact that was incorrectly merged, so I can undo a bad merge.

### 7.2 UI Specifications

The merge history is accessible from the surviving contact's detail page via the action bar ("Merge History") or through merge-related entries in the activity timeline. Each merge entry shows the absorbed contact's name, primary email, merge date, and method (manual, auto-high, auto-medium). An "Undo Merge" button opens a confirmation dialog explaining the consequences. After split, a success message with a link to the restored contact appears.

**Tasks:**

- [ ] MERGE-18: Implement split operation (restore absorbed contact from snapshot)
- [ ] MERGE-19: Implement sub-entity re-linking during split (identifiers, employment, etc.)
- [ ] MERGE-20: Implement communication/conversation participant restoration during split
- [ ] MERGE-21: Implement merge history display on contact detail page
- [ ] MERGE-22: Implement undo merge confirmation dialog
- [ ] MERGE-23: Implement success message with link to restored contact

**Tests:**

- [ ] MERGE-T19: Split restores absorbed contact to active status
- [ ] MERGE-T20: Split restores identifiers to the original contact
- [ ] MERGE-T21: Split restores pre-merge communication participant assignments
- [ ] MERGE-T22: Post-merge communications remain linked to surviving contact after split
- [ ] MERGE-T23: Split updates audit record to reflect the undo
- [ ] MERGE-T24: Merge history shows all merges for a contact in chronological order
