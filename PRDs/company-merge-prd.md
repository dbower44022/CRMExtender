# Company — Duplicate Detection & Merging Sub-PRD

**Version:** 1.0
**Last Updated:** 2026-02-23
**Status:** Draft
**Entity Base PRD:** [company-entity-base-prd.md]
**Referenced Entity PRDs:** [contact-entity-base-prd.md] (employment reassignment), [company-hierarchy-prd.md] (merge-vs-hierarchy fork)

---

## 1. Overview

### 1.1 Purpose

Duplicate companies arise naturally as the system auto-creates records from different email domains that belong to the same organization (e.g., `acme.com` and `acmecorp.com`). The merge flow combines two duplicate company records into a single surviving record, reassigning all associated entities — contacts, events, relations, identifiers, and hierarchy links — to the survivor. A full audit trail preserves the absorbed company's data for compliance and undo capability.

### 1.2 Preconditions

- At least two company records exist that the user believes are duplicates.
- User has permission to merge company records.
- The companies are both in `active` status (cannot merge archived or already-merged companies).

---

## 2. Context

### 2.1 Relevant Fields

| Field | Role in This Action |
|---|---|
| Name | Conflict resolution — user picks which name survives. |
| Primary Domain | Both companies' domains are consolidated under the survivor. |
| Status | Absorbed company set to `merged`. Surviving company remains `active`. |
| All other fields | Subject to conflict resolution when both companies have values. |

### 2.2 Relevant Relationships

- **Contact Employment** — Employment records referencing the absorbed company are reassigned to the survivor. Duplicates (same contact at both companies) are deduplicated.
- **Event Participants** — Event participation records referencing the absorbed company are reassigned.
- **Relation Instances** — All relation instances (any Relation Type) involving the absorbed company are reassigned. Duplicates are removed.
- **Company Identifiers** — All identifiers from the absorbed company are transferred to the survivor.
- **Hierarchy** — If the absorbed company had hierarchy relationships, those transfer to the survivor.

### 2.3 Relevant Lifecycle Transitions

| From | To | Trigger |
|---|---|---|
| `active` | `merged` | Company is absorbed during merge |

### 2.4 Cross-Entity Context

- **Contact Management PRD:** Employment junction rows (`contacts__companies_employment`) need `target_id` updated. When both companies had the same contact, keep the record with more metadata.
- **Events PRD:** `event_participants` where `entity_type = 'company'` and `entity_id` = absorbed need `entity_id` updated.
- **Company Hierarchy Sub-PRD:** The merge-vs-hierarchy fork asks whether two related companies are duplicates or hierarchically related before proceeding.

---

## 3. Key Processes

### KP-1: Duplicate Detection During Company Creation

**Trigger:** User creates a company or enters a domain that matches an existing company.

**Step 1 — Domain check:** System checks `company_identifiers` for the entered domain. Match found.

**Step 2 — Block creation:** System blocks the duplicate creation and presents the existing company record.

**Step 3 — User decision:** System offers "View existing company", "Merge with existing", or "Cancel". If the user believes these are different companies that happen to share infrastructure, they can cancel and investigate further.

### KP-2: User-Initiated Merge

**Trigger:** User selects two company records and initiates a merge from the UI (e.g., multi-select in list view, or "Merge" action on a company detail page).

**Step 1 — Merge-vs-hierarchy fork:** System asks "Are these duplicates, or are you establishing a company hierarchy?" If hierarchy, redirect to Hierarchy Sub-PRD flow. If duplicates, continue.

**Step 2 — Merge preview:** System displays side-by-side company cards showing name, domain, industry, employee count, contact count, relationship count, event participant count, identifier count, and hierarchy relationships.

**Step 3 — Survivor designation:** User selects which company ID persists (the survivor).

**Step 4 — Conflict resolution:** For fields where both companies have distinct values, user picks which value the merged record should carry (radio buttons per field).

**Step 5 — Confirmation:** System shows combined/deduplicated totals and asks for final confirmation.

**Step 6 — Execution:** System executes the merge in a single transaction. Success message displayed with summary of reassignment counts.

### KP-3: Merge Undo (Split)

**Trigger:** User discovers a bad merge and initiates a split from the surviving company's merge history.

**Step 1 — Locate merge:** User views the company's merge history. Each merge entry shows date, absorbed company name, and initiating user.

**Step 2 — Initiate split:** User selects a merge to undo. System shows what will be reversed.

**Step 3 — Execution:** System restores the absorbed company from the snapshot in the merge audit table, reassigns entities back to the original company, and removes the `merged` status from the restored record.

---

## 4. Duplicate Detection

**Supports processes:** KP-1 (all steps)

### 4.1 Requirements

The primary domain name is the canonical company duplicate identifier. Detection is strictly domain-based — no fuzzy name matching. A domain can belong to at most one company (enforced by the unique constraint on `company_identifiers`).

**Detection points:**

- Company creation (manual or auto): check domain against existing identifiers.
- Domain addition to existing company: check domain against other companies' identifiers.
- Company edit (domain field change): check new domain value.

When a duplicate is detected, the system blocks the operation and presents the existing matching company with merge/cancel options.

**Tasks:**

- [ ] CMRG-01: Implement duplicate detection on company creation
- [ ] CMRG-02: Implement duplicate detection on domain addition
- [ ] CMRG-03: Implement duplicate detection UI (block + present existing company)

**Tests:**

- [ ] CMRG-T01: Test duplicate detection blocks creation when domain matches
- [ ] CMRG-T02: Test duplicate detection fires on domain edit
- [ ] CMRG-T03: Test UI presents existing company with merge/cancel options

---

## 5. Merge Preview

**Supports processes:** KP-2 (steps 2–4)

### 5.1 Requirements

`GET /api/v1/companies/merge?ids=X&ids=Y`

The merge preview returns:

- Side-by-side company cards showing: name, domain, industry, employee count, contact count, relationship count, event participant count, identifier count, hierarchy relationships.
- Conflict detection: fields where both companies have distinct non-NULL values.
- Combined/deduplicated totals showing what the merged result would look like.

### 5.2 UI Specifications

- Two company cards side by side.
- Radio buttons to designate the surviving company (which `cmp_` ID persists).
- Radio buttons for each conflicting field to select the winning value.
- Summary footer showing combined totals: total contacts, total identifiers, total relations.

**Tasks:**

- [ ] CMRG-04: Implement merge preview API endpoint
- [ ] CMRG-05: Implement merge preview UI with side-by-side cards
- [ ] CMRG-06: Implement conflict detection and radio button resolution

**Tests:**

- [ ] CMRG-T04: Test merge preview returns correct counts for both companies
- [ ] CMRG-T05: Test conflict detection identifies all fields with divergent values
- [ ] CMRG-T06: Test preview handles companies with no conflicts gracefully

---

## 6. Merge Execution

**Supports processes:** KP-2 (steps 5–6)

### 6.1 Requirements

`POST /api/v1/companies/merge/confirm`

Body: `{surviving_id, absorbed_ids, field_resolutions}`

Execution is performed within a single PostgreSQL transaction:

1. **Snapshot** — Serialize the absorbed company and all sub-entities as JSON. Store in the `company_merges` audit table.

2. **Entity reassignment:**

   | Entity | Reassignment Rule |
   |---|---|
   | `contacts__companies_employment` (where `target_id` = absorbed) | UPDATE `target_id` to surviving company ID. Deduplicate: if both companies had the same contact, keep the record with more metadata; delete the other. |
   | `event_participants` (where `entity_type = 'company'` and `entity_id` = absorbed) | UPDATE `entity_id` to surviving company ID. |
   | Relation instances involving the absorbed company | UPDATE entity IDs to surviving company. Deduplicate if both companies had the same relationship to a third entity. |

   Conversations and communications are not directly reassigned — they link to companies indirectly through contact participants. Reassigning employment records carries these associations automatically.

3. **Domain consolidation** — All `company_identifiers` from the absorbed company are reassigned to the surviving company. The surviving company's primary domain is preserved unless it had none.

4. **Field conflict resolution** — Apply the user's field_resolutions choices. Surviving record's non-NULL values take precedence for unresolved fields. Empty fields on the surviving record are filled from the absorbed record.

5. **Hierarchy preservation** — Hierarchy relationships from the absorbed company transfer to the surviving company. Duplicate hierarchy rows are removed.

6. **Soft delete** — Set absorbed company `status = 'merged'`.

7. **Emit events** — Write `CompanyMerged` event to surviving company's event stream. Write `CompanyAbsorbed` event to absorbed company's event stream.

8. **Score recalculation** — Queue relationship strength recalculation for the surviving company.

### 6.2 Company Merges Audit Table

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | TEXT | **PK** | Prefixed ULID. |
| `surviving_company_id` | TEXT | NOT NULL, FK → `companies(id)` | Company that persists. |
| `absorbed_company_id` | TEXT | NOT NULL | Company that was absorbed. |
| `absorbed_company_snapshot` | JSONB | NOT NULL | Full JSON serialization at merge time. |
| `contacts_reassigned` | INTEGER | DEFAULT 0 | Employment records reassigned. |
| `relations_reassigned` | INTEGER | DEFAULT 0 | Relation instances reassigned. |
| `events_reassigned` | INTEGER | DEFAULT 0 | Event participants reassigned. |
| `relations_deduplicated` | INTEGER | DEFAULT 0 | Duplicate relations removed. |
| `merged_by` | TEXT | FK → `users(id)` ON DELETE SET NULL | Initiating user. |
| `merged_at` | TIMESTAMPTZ | NOT NULL | |

**Indexes:** `(surviving_company_id)` for audit trail. `(absorbed_company_id)` for undo/lookup.

**Tasks:**

- [ ] CMRG-07: Implement merge execution within single transaction
- [ ] CMRG-08: Implement absorbed company snapshot serialization
- [ ] CMRG-09: Implement employment record reassignment with deduplication
- [ ] CMRG-10: Implement event participant reassignment
- [ ] CMRG-11: Implement relation instance reassignment with deduplication
- [ ] CMRG-12: Implement domain consolidation
- [ ] CMRG-13: Implement hierarchy preservation during merge
- [ ] CMRG-14: Implement company_merges audit table and recording
- [ ] CMRG-15: Emit CompanyMerged and CompanyAbsorbed events
- [ ] CMRG-16: Queue score recalculation post-merge

**Tests:**

- [ ] CMRG-T07: Test merge reassigns all employment records to survivor
- [ ] CMRG-T08: Test merge deduplicates employment records for same contact at both companies
- [ ] CMRG-T09: Test merge reassigns event participants
- [ ] CMRG-T10: Test merge consolidates all domains under survivor
- [ ] CMRG-T11: Test merge preserves surviving company's primary domain
- [ ] CMRG-T12: Test merge transfers hierarchy relationships
- [ ] CMRG-T13: Test absorbed company status set to 'merged'
- [ ] CMRG-T14: Test snapshot contains complete absorbed company data
- [ ] CMRG-T15: Test merge is atomic (all-or-nothing transaction)
- [ ] CMRG-T16: Test merge events are emitted for both companies

---

## 7. Split (Undo Merge)

**Supports processes:** KP-3 (all steps)

### 7.1 Requirements

Split reverses a bad merge by restoring the absorbed company from the snapshot stored in `company_merges`:

1. Restore the absorbed company record from the JSONB snapshot.
2. Set the restored company's status to `active`.
3. Reassign entities back to the restored company based on the snapshot data.
4. Remove the merge audit record (or mark it as reversed).
5. Emit events on both companies.

**Limitations:** Split only works if the surviving company has not undergone further merges that would complicate entity reassignment. The system warns the user if cascading changes have occurred.

**Tasks:**

- [ ] CMRG-17: Implement split (undo merge) from snapshot
- [ ] CMRG-18: Implement cascading change detection for split safety
- [ ] CMRG-19: Split UI with merge history and undo action

**Tests:**

- [ ] CMRG-T17: Test split restores absorbed company from snapshot
- [ ] CMRG-T18: Test split reassigns entities back to restored company
- [ ] CMRG-T19: Test split warns when cascading changes detected
