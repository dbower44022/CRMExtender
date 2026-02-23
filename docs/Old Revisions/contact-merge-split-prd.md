# Contact — Merge & Split Sub-PRD

**Version:** 1.0
**Last Updated:** 2026-02-22
**Status:** Draft
**Entity Base PRD:** [contact-entity-base-prd.md]
**Referenced Entity PRDs:** [Company Management Entity Base PRD](company-management-prd_V1.md), [Communications PRD](communications-prd_V3.md), [Conversations PRD](conversations-prd_V4.md)

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
- **Contact-to-Contact Relationships** — Graph relationship edges are re-pointed, deduplicated, and self-referential relationships (created when two contacts who had a relationship between them are merged) are removed.
- **Enrichment data** — Enrichment run history transfers; entity scores for absorbed contacts are removed.
- **Visibility/permissions** — User-contact visibility records transfer.

### 2.3 Relevant Lifecycle Transitions

- The absorbed contact transitions to `merged` status.
- The surviving contact remains `active` (or its current status).
- Split transitions the restored contact from `merged` back to `active`.

---

## 3. Merge Entry Points

### 3.1 Requirements

Merge can be initiated from two entry points:

1. **List selection** — User selects 2 or more contacts via checkboxes on the Contact list view, then clicks "Merge Selected."
2. **Identifier conflict** — When adding an email address to a contact that already belongs to another contact, the error message includes a "Merge these contacts?" link.
3. **Identity resolution** — Automatic merge triggered by the resolution pipeline for high and medium-confidence matches (see Identity Resolution Sub-PRD).

All entry points lead to the same merge preview screen.

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

## 4. Merge Preview

### 4.1 Requirements

Before execution, the user reviews a merge preview showing:

- **Side-by-side contact cards** for all contacts being merged, with per-contact counts of identifiers, employment records, conversations, relationships, events, phones, addresses, emails, and social profiles.
- **Conflict resolution controls** — Radio buttons for fields where the contacts have distinct values (name, source). The user selects which value the surviving contact should have.
- **Survivor designation** — Radio buttons to choose which contact ID persists as the surviving record.
- **Combined totals** — A summary showing the merged result with deduplicated counts.

The preview is non-destructive — no data changes until the user confirms.

### 4.2 UI Specifications

The merge preview is a dedicated screen. Contact cards are displayed side by side (or stacked on mobile). Each card shows the contact's key fields and sub-entity counts. Fields with conflicts are highlighted. The survivor selection is prominent at the top. A "Confirm Merge" button executes the merge; a "Cancel" button returns to the previous screen.

**Tasks:**

- [ ] MERGE-04: Implement merge preview data assembly (side-by-side comparison with counts)
- [ ] MERGE-05: Implement conflict detection across all fields
- [ ] MERGE-06: Implement merge preview UI with conflict resolution controls and survivor selection
- [ ] MERGE-07: Implement combined/deduplicated total calculation for preview

**Tests:**

- [ ] MERGE-T04: Preview correctly identifies conflicting fields between two contacts
- [ ] MERGE-T05: Preview shows accurate sub-entity counts per contact
- [ ] MERGE-T06: Preview combined totals reflect deduplication (e.g., shared email counted once)
- [ ] MERGE-T07: Preview supports 3+ contacts in multi-merge scenario

---

## 5. Merge Execution

### 5.1 Requirements

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

**Performance target:** Import throughput > 1,000 contacts per minute implies merge must be fast enough to handle batch merges during import.

**User story:** As a user, I want all of a merged contact's data (emails, conversations, relationships) to transfer to the surviving record, so I don't lose any information.

**Tasks:**

- [ ] MERGE-08: Implement atomic merge transaction with full sub-entity transfer
- [ ] MERGE-09: Implement identifier deduplication during transfer (type + value)
- [ ] MERGE-10: Implement employment record deduplication during transfer (company + start date)
- [ ] MERGE-11: Implement relationship reassignment with deduplication and self-referential cleanup
- [ ] MERGE-12: Implement communication and conversation participant reassignment
- [ ] MERGE-13: Implement post-merge domain resolution for auto-creating missing company affiliations
- [ ] MERGE-14: Implement merge audit record with full absorbed contact snapshot
- [ ] MERGE-15: Implement primary email selection after merge (is_primary DESC, created_at ASC)

**Tests:**

- [ ] MERGE-T08: Merge transfers all identifiers to surviving contact
- [ ] MERGE-T09: Duplicate identifiers (same email on both contacts) are deduplicated, not duplicated
- [ ] MERGE-T10: Employment records are deduplicated by company + start date
- [ ] MERGE-T11: Communication participants re-pointed to surviving contact
- [ ] MERGE-T12: Conversation participants re-pointed to surviving contact
- [ ] MERGE-T13: Relationship self-referential edges removed after merge
- [ ] MERGE-T14: Merge transaction rolls back completely on failure
- [ ] MERGE-T15: Post-merge domain resolution creates missing company affiliations
- [ ] MERGE-T16: Audit record contains complete snapshot of absorbed contact
- [ ] MERGE-T17: Multi-contact merge (3+) processes all absorbed contacts correctly

---

## 6. Split (Undo Merge)

### 6.1 Requirements

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

### 6.2 UI Specifications

Split is accessed from the surviving contact's detail page via a "Merge History" section that shows all merges involving this contact. Each merge entry has an "Undo Merge" action that opens a confirmation dialog explaining what will be restored.

**Tasks:**

- [ ] MERGE-16: Implement split operation (restore absorbed contact from snapshot)
- [ ] MERGE-17: Implement sub-entity re-linking during split (identifiers, employment, etc.)
- [ ] MERGE-18: Implement communication/conversation participant restoration during split
- [ ] MERGE-19: Implement merge history display on contact detail page
- [ ] MERGE-20: Implement undo merge confirmation UI

**Tests:**

- [ ] MERGE-T18: Split restores absorbed contact to active status
- [ ] MERGE-T19: Split restores identifiers to the original contact
- [ ] MERGE-T20: Split restores pre-merge communication participant assignments
- [ ] MERGE-T21: Post-merge communications remain linked to surviving contact after split
- [ ] MERGE-T22: Split updates audit record to reflect the undo
