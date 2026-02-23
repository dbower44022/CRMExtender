# Contact — Import & Export Sub-PRD

**Version:** 1.0
**Last Updated:** 2026-02-22
**Status:** Draft
**Entity Base PRD:** [contact-entity-base-prd.md]
**Referenced Entity PRDs:** [Company Management Entity Base PRD](company-management-prd_V1.md)

---

## 1. Overview

### 1.1 Purpose

Import brings contacts into the system from external sources — files, APIs, and third-party platforms. Export produces contact data in standard formats for portability, migration, analysis, and compliance (GDPR data subject access requests). Together they ensure users can move data freely into and out of CRMExtender.

### 1.2 Preconditions

- **Import:** User has a file or connected account to import from. Entity resolution pipeline is operational for duplicate detection.
- **Export:** Contacts exist in the system. For GDPR export, the specific contact's full record including event history must be accessible.

---

## 2. Context

### 2.1 Relevant Fields

Import maps external data to contact fields: First Name, Last Name, Display Name, Email, Phone, Company, Job Title, Tags, and any custom fields defined in the field registry. Export includes all contact fields plus related sub-entities depending on export scope.

### 2.2 Relevant Relationships

- **Contact Identifiers** — Import creates identifiers from email, phone, and social data in the source file.
- **Company** — Import triggers domain resolution from email addresses to auto-create company affiliations.
- **Tags** — Import can include tag assignments.
- **Groups** — Imported contacts can be automatically added to a specified group.

### 2.3 Relevant Lifecycle Transitions

- Import creates contacts with status `active` (if name is present) or `incomplete` (if only an identifier is available).
- Import triggers auto-enrichment for newly created contacts.

---

## 3. Import Formats

### 3.1 Requirements

The system supports importing contacts from multiple formats:

| Format | Source | Capabilities |
|---|---|---|
| **CSV** | Any CRM, spreadsheet | Column mapping UI. Supports name, email, phone, company, title, tags, custom fields. |
| **vCard 3.0/4.0** | Apple Contacts, Outlook, Google Contacts export | Standard contact interchange. Multi-value fields (multiple emails/phones) supported. |
| **Google Contacts API** | Google account | OAuth-based live sync. Initial import plus ongoing incremental sync. |
| **LinkedIn CSV** | LinkedIn export | Structured export with name, company, title, email, connected date. |

Each format enters the same import pipeline after format-specific parsing.

**User stories:**
- As a user, I want to import contacts from a CSV file, so I can migrate from my existing CRM or address book.
- As a user, I want to import my Google Contacts, so my existing address book is available immediately.
- As a user, I want to import contacts from a vCard file, so I can import from Apple Contacts or other vCard-compatible tools.

**Tasks:**

- [ ] IMPORT-01: Implement CSV parser with column mapping
- [ ] IMPORT-02: Implement vCard 3.0/4.0 parser (single and multi-contact files)
- [ ] IMPORT-03: Implement Google Contacts API sync (OAuth, initial import, incremental sync)
- [ ] IMPORT-04: Implement LinkedIn CSV parser

**Tests:**

- [ ] IMPORT-T01: CSV with standard columns parses correctly
- [ ] IMPORT-T02: CSV with missing columns handles gracefully (maps only available fields)
- [ ] IMPORT-T03: vCard 3.0 multi-contact file parses all contacts
- [ ] IMPORT-T04: vCard 4.0 with multi-value fields (3 emails, 2 phones) parses correctly
- [ ] IMPORT-T05: Google Contacts OAuth flow completes and imports contacts
- [ ] IMPORT-T06: LinkedIn CSV parses name, company, title, email, and connected date

---

## 4. Import Pipeline

### 4.1 Requirements

All import formats flow through a five-stage pipeline:

**Stage 1 — Parse & Validate:**
- Parse the source file or API response into a normalized internal format.
- Validate required fields (at minimum one identifier per record).
- Normalize values (lowercase emails, E.164 phone numbers, trim whitespace).
- Report parsing errors with row/record identification for user review.

**Stage 2 — Duplicate Detection:**
- Run each parsed record through the entity resolution pipeline to check against existing contacts.
- Classify each record as: new (no match found), duplicate (high-confidence match to existing contact), or update (match found with additional data to merge).

**Stage 3 — Preview & User Confirmation:**
- Present an import preview showing counts: N new contacts, N updates to existing contacts, N duplicates.
- User selects handling for each category — create, merge, skip.
- User confirms to proceed with import.

**Stage 4 — Execute Import:**
- Create new contact records.
- Merge updates into existing contacts.
- Skip or merge duplicates per user selection.
- Emit events for all contact changes.
- Trigger enrichment for newly created contacts.

**Stage 5 — Import Report:**
- Summary: count of created, updated, skipped, and errored records.
- Error details for failed records (parsing errors, validation failures).
- Import job ID for audit trail.

**Business rules:**
- The pipeline is resumable — if execution fails partway through, it can continue from where it left off.
- Large imports (1,000+ records) execute as a background job with progress tracking.
- CSV import includes a column mapping step between parse and validate where the user maps source columns to contact fields.

**Performance target:** Import throughput > 1,000 contacts per minute for CSV and vCard.

**Tasks:**

- [ ] IMPORT-05: Implement Stage 1 — parse and validate with normalized internal format
- [ ] IMPORT-06: Implement Stage 2 — duplicate detection via entity resolution pipeline
- [ ] IMPORT-07: Implement Stage 3 — preview UI showing new/update/duplicate counts with handling selection
- [ ] IMPORT-08: Implement Stage 4 — execute import (create, merge, skip per user selection)
- [ ] IMPORT-09: Implement Stage 5 — import report with summary and error details
- [ ] IMPORT-10: Implement CSV column mapping step between upload and preview
- [ ] IMPORT-11: Implement background job execution for large imports with progress tracking
- [ ] IMPORT-12: Implement import event emission (ContactCreated, ContactUpdated events for all changes)

**Tests:**

- [ ] IMPORT-T07: Pipeline correctly classifies records as new, duplicate, or update
- [ ] IMPORT-T08: Preview shows accurate counts for each classification
- [ ] IMPORT-T09: User can select different handling per category (create, merge, skip)
- [ ] IMPORT-T10: Execute stage creates contacts with correct status (active if name present, incomplete otherwise)
- [ ] IMPORT-T11: Execute stage triggers enrichment for new contacts
- [ ] IMPORT-T12: Import report accurately reflects results
- [ ] IMPORT-T13: Large import (5,000 records) executes as background job with progress
- [ ] IMPORT-T14: Partial failure during execution is resumable
- [ ] IMPORT-T15: Import completes within performance target (1,000/min)

---

## 5. Google Contacts Sync

### 5.1 Requirements

Google Contacts sync is a special import case with ongoing synchronization:

- **Initial import:** OAuth-based authentication, then full contact list import via Google People API.
- **Incremental sync:** Ongoing polling for changes (new contacts, updated contacts, deleted contacts) at a configurable interval.
- **UPSERT behavior:** Incoming Google contacts are matched to existing CRMExtender contacts by email address. Matched contacts are updated; unmatched contacts are created.
- **Bidirectional note:** Initial implementation is one-way (Google → CRMExtender). Future phases may support bidirectional sync.

**User story:** As a user, I want to import my Google Contacts, so my existing address book is available immediately.

**Tasks:**

- [ ] IMPORT-13: Implement Google OAuth flow for contacts access
- [ ] IMPORT-14: Implement initial full sync via Google People API
- [ ] IMPORT-15: Implement incremental sync with change detection
- [ ] IMPORT-16: Implement UPSERT matching by email address

**Tests:**

- [ ] IMPORT-T16: OAuth flow grants contact read access
- [ ] IMPORT-T17: Initial sync imports all Google contacts
- [ ] IMPORT-T18: Incremental sync detects and imports new Google contacts
- [ ] IMPORT-T19: Incremental sync updates existing CRMExtender contacts on Google-side changes
- [ ] IMPORT-T20: Deleted Google contacts do not delete CRMExtender contacts (soft archive only, if configured)

---

## 6. Export

### 6.1 Requirements

Export produces contact data in three formats:

| Format | Use Case |
|---|---|
| **CSV** | General export, spreadsheet analysis, migration to another system |
| **vCard 4.0** | Import into address book applications |
| **JSON** | API-based export, data portability, GDPR export |

**Export scoping:** Users can export:
- All contacts (with current filter applied)
- A filtered subset
- A group's members
- A single contact's full record including all history, identifiers, communications, and intelligence (for GDPR data subject access requests)

**Business rules:**
- Export respects the user's current filter and view configuration for bulk exports.
- GDPR full-record export includes the event history, all identifiers (including inactive), all communications, intelligence items, and relationship data.
- Large exports execute as a background job with a download link when complete.

**User stories:**
- As a user, I want to export my contacts to CSV for analysis in a spreadsheet.
- As a user, I want to export a single contact's complete record for a GDPR data subject access request.

**Tasks:**

- [ ] EXPORT-01: Implement CSV export with configurable field selection
- [ ] EXPORT-02: Implement vCard 4.0 export
- [ ] EXPORT-03: Implement JSON export (standard and GDPR full-record)
- [ ] EXPORT-04: Implement export scoping (all, filtered, group, single contact)
- [ ] EXPORT-05: Implement background job execution for large exports with download link

**Tests:**

- [ ] EXPORT-T01: CSV export includes all selected fields
- [ ] EXPORT-T02: vCard export produces valid vCard 4.0 files importable by Apple Contacts
- [ ] EXPORT-T03: JSON full-record export includes event history, identifiers, communications, and intelligence
- [ ] EXPORT-T04: Export respects current filter (only exports matching contacts)
- [ ] EXPORT-T05: Group export includes only group members
- [ ] EXPORT-T06: Large export (10,000 contacts) executes as background job
