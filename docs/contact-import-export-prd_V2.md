# Contact — Import & Export Sub-PRD

**Version:** 2.0
**Last Updated:** 2026-02-22
**Status:** Draft
**Entity Base PRD:** [contact-entity-base-prd_V7.md]
**Referenced Entity PRDs:** [Company Management Entity Base PRD](company-management-prd_V1.md)
**Referenced Action Sub-PRDs:** [Contact Identity Resolution Sub-PRD](contact-identity-resolution-prd_V2.md)

> **V2.0 (2026-02-22):** Added Key Processes section defining end-to-end user experiences for all import and export scenarios. Restructured functional sections with process linkage.

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

## 3. Key Processes

### KP-1: CSV File Import

**Trigger:** The user wants to import contacts from a CSV file (CRM export, spreadsheet, etc.).

**Step 1 — Upload:** The user navigates to Contacts → Import and selects "CSV." A file picker opens. The user selects their CSV file.

**Step 2 — Column mapping:** The system parses the CSV headers and presents a mapping interface. Each CSV column is shown with a dropdown to map it to a contact field (first name, last name, email, phone, company, title, tags, or custom fields). The system auto-maps obvious columns (e.g., "Email" → email, "First Name" → first_name). Unmapped columns are highlighted. The user can skip columns they don't want to import.

**Step 3 — Validation and duplicate detection:** After mapping, the system validates all rows (required fields, email format, phone format) and runs each record through the entity resolution pipeline. Parsing errors and validation failures are reported with row numbers. Records are classified as New, Update (exact match to existing contact), or Possible Duplicate (fuzzy match found).

**Step 4 — Import preview:** The user sees a summary: "150 new contacts, 23 updates to existing contacts, 12 possible duplicates, 3 errors." Each category is expandable to see individual records. For Possible Duplicates, each record shows the imported data alongside the potential match with confidence score. The user selects per-duplicate: Merge, Create Anyway, or Skip. Error records can be reviewed and excluded.

**Step 5 — Optional group assignment:** Before confirming, the user can choose to add all imported contacts to a specific group (existing or new).

**Step 6 — Execute:** The user clicks "Import." For large files (1,000+ records), the import runs as a background job with a progress bar. The user can navigate away and return later.

**Step 7 — Import report:** After completion, the user sees a summary: "Created 148, Updated 23, Merged 8, Skipped 7, Errors 2." Errors are listed with details. The report is downloadable and includes an import job ID for audit purposes.

### KP-2: vCard File Import

**Trigger:** The user wants to import contacts from a vCard (.vcf) file from Apple Contacts, Outlook, or another vCard source.

**Step 1 — Upload:** The user navigates to Contacts → Import and selects "vCard." Selects the .vcf file.

**Step 2 — Parsing:** The system parses the vCard file (3.0 or 4.0 format). Multi-contact vCard files are supported. Multi-value fields (multiple emails, phones per contact) are preserved.

**Step 3 — Preview and duplicate detection:** Same as KP-1 steps 3–4, except there is no column mapping step (vCard fields map automatically to contact fields).

**Steps 4–6:** Same as KP-1 steps 5–7.

### KP-3: Google Contacts Initial Sync

**Trigger:** The user wants to connect their Google account and import all Google Contacts.

**Step 1 — Connect account:** The user navigates to Contacts → Import → Google Contacts. Clicks "Connect Google Account." The OAuth flow opens in a popup/redirect.

**Step 2 — Authorization:** The user authorizes CRMExtender to access their Google Contacts (read-only). After authorization, the popup closes and the import screen updates.

**Step 3 — Initial sync:** The system fetches all contacts from the Google People API. A progress indicator shows the sync status. For large accounts, this runs as a background job.

**Step 4 — Duplicate handling:** Each Google contact is matched against existing CRMExtender contacts by email. Matches are updated (UPSERT). Non-matches are created as new contacts. No manual preview step for Google sync — the UPSERT behavior is automatic.

**Step 5 — Sync complete:** The user sees a summary: "Imported 342 contacts (278 new, 64 updated existing)." The user is offered the option to enable ongoing sync.

### KP-4: Google Contacts Ongoing Sync

**Trigger:** The user has enabled ongoing sync after the initial Google Contacts import (KP-3).

**Step 1 — Background polling:** The system polls the Google People API for changes at a configurable interval (default: every 30 minutes). This is invisible to the user.

**Step 2 — Incremental update:** New Google contacts are created. Changed Google contacts are updated. The user does not see notifications for routine sync — changes appear silently in the contact list and detail pages.

**Step 3 — Sync status:** The user can check sync status in Settings → Connected Accounts. Shows last sync time, contact count, and any errors.

### KP-5: Exporting Contacts

**Trigger:** The user wants to export contacts for analysis, migration, or sharing.

**Step 1 — Initiate export:** The user clicks "Export" from the contact list view action bar, from a group's action bar, or from a single contact's detail page.

**Step 2 — Scope selection:** If initiated from the list view, the export scope defaults to the current filter/view. The user can adjust: all contacts, current filter, selected contacts, or a specific group. If initiated from a contact detail page, the scope is that single contact.

**Step 3 — Format selection:** The user selects the export format: CSV, vCard 4.0, or JSON. For CSV, the user can select which fields to include.

**Step 4 — Execute:** The user clicks "Export." For small exports (< 500 contacts), the file downloads immediately. For large exports, a background job runs and the user receives a notification with a download link when complete.

### KP-6: GDPR Full-Record Export

**Trigger:** A user needs to fulfill a data subject access request (DSAR) by providing a complete record of everything the system knows about a specific contact.

**Step 1 — Initiate from contact detail:** The user opens the contact's detail page and selects "Export Full Record" from the action menu.

**Step 2 — Format and scope:** The export includes everything: all profile fields, all identifiers (including inactive), all event history, all communications, all intelligence items, all relationship data, all enrichment data with source attribution. Format is JSON (machine-readable, per GDPR requirements).

**Step 3 — Generation:** The system assembles the complete record. This may take a few seconds for contacts with extensive history. A progress indicator shows the status.

**Step 4 — Download:** The file downloads as `contact_[name]_full_record_[date].json`.

---

## 4. Import Formats

**Supports processes:** KP-1 (step 2), KP-2 (step 2), KP-3 (step 3).

### 4.1 Requirements

The system supports importing contacts from multiple formats:

| Format | Source | Capabilities |
|---|---|---|
| **CSV** | Any CRM, spreadsheet | Column mapping UI. Supports name, email, phone, company, title, tags, custom fields. |
| **vCard 3.0/4.0** | Apple Contacts, Outlook, Google Contacts export | Standard contact interchange. Multi-value fields (multiple emails/phones) supported. |
| **Google Contacts API** | Google account | OAuth-based live sync. Initial import plus ongoing incremental sync. |
| **LinkedIn CSV** | LinkedIn export | Structured export with name, company, title, email, connected date. |

Each format enters the same import pipeline after format-specific parsing.

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

## 5. Import Pipeline

**Supports processes:** KP-1 (steps 3–7), KP-2 (step 3), KP-3 (steps 3–5).

### 5.1 Requirements

All import formats flow through a five-stage pipeline:

**Stage 1 — Parse & Validate:** Parse the source file or API response into a normalized internal format. Validate required fields (at minimum one identifier per record). Normalize values (lowercase emails, E.164 phone numbers, trim whitespace). Report parsing errors with row/record identification for user review.

**Stage 2 — Duplicate Detection:** Run each parsed record through the entity resolution pipeline to check against existing contacts. Classify each record as: New (no match found), Update (exact match — will merge new data into existing contact), or Possible Duplicate (fuzzy match found — requires user decision).

**Stage 3 — Preview & User Confirmation:** Present an import preview showing counts per classification. Each category is expandable. For Possible Duplicates, the user selects handling per record: Merge, Create Anyway, or Skip. User confirms to proceed.

**Stage 4 — Execute Import:** Create new contact records. Merge updates into existing contacts. Process duplicates per user selection. Emit events for all changes. Trigger enrichment for newly created contacts.

**Stage 5 — Import Report:** Summary of created, updated, merged, skipped, and errored records. Error details for failed records. Import job ID for audit trail. Downloadable report.

**Business rules:**
- Large imports (1,000+ records) execute as a background job with progress tracking.
- CSV import includes a column mapping step between parse and validate.
- The pipeline is resumable — if execution fails partway through, it can continue from where it left off.

**Performance target:** Import throughput > 1,000 contacts per minute for CSV and vCard.

**Tasks:**

- [ ] IMPORT-05: Implement Stage 1 — parse and validate with normalized internal format
- [ ] IMPORT-06: Implement Stage 2 — duplicate detection via entity resolution pipeline
- [ ] IMPORT-07: Implement Stage 3 — preview UI showing new/update/duplicate counts with handling selection
- [ ] IMPORT-08: Implement Stage 4 — execute import (create, merge, skip per user selection)
- [ ] IMPORT-09: Implement Stage 5 — import report with summary, error details, and download
- [ ] IMPORT-10: Implement CSV column mapping step with auto-mapping of obvious columns
- [ ] IMPORT-11: Implement background job execution for large imports with progress bar
- [ ] IMPORT-12: Implement optional group assignment before import confirmation

**Tests:**

- [ ] IMPORT-T07: Pipeline correctly classifies records as new, duplicate, or update
- [ ] IMPORT-T08: Preview shows accurate counts for each classification
- [ ] IMPORT-T09: User can select different handling per duplicate (merge, create anyway, skip)
- [ ] IMPORT-T10: Execute stage creates contacts with correct status (active if name present, incomplete otherwise)
- [ ] IMPORT-T11: Execute stage triggers enrichment for new contacts
- [ ] IMPORT-T12: Import report accurately reflects results and is downloadable
- [ ] IMPORT-T13: Large import (5,000 records) executes as background job with progress
- [ ] IMPORT-T14: Partial failure during execution is resumable
- [ ] IMPORT-T15: Import completes within performance target (1,000/min)

---

## 6. Google Contacts Sync

**Supports processes:** KP-3 (full flow), KP-4 (full flow).

### 6.1 Requirements

Google Contacts sync is a special import case with ongoing synchronization:

- **Initial import:** OAuth-based authentication, then full contact list import via Google People API.
- **Incremental sync:** Ongoing polling for changes (new contacts, updated contacts, deleted contacts) at a configurable interval (default 30 minutes).
- **UPSERT behavior:** Incoming Google contacts are matched to existing CRMExtender contacts by email address. Matches are updated; unmatched contacts are created.
- **Sync status:** Visible in Settings → Connected Accounts with last sync time, count, and errors.

**Business rules:**
- Initial implementation is one-way (Google → CRMExtender).
- Deleted Google contacts do not delete CRMExtender contacts. If configured, they may trigger an archive.
- Sync errors are logged and visible in the connected accounts settings.

**Tasks:**

- [ ] IMPORT-13: Implement Google OAuth flow for contacts access
- [ ] IMPORT-14: Implement initial full sync via Google People API
- [ ] IMPORT-15: Implement incremental sync with change detection
- [ ] IMPORT-16: Implement UPSERT matching by email address
- [ ] IMPORT-17: Implement sync status display in connected accounts settings

**Tests:**

- [ ] IMPORT-T16: OAuth flow grants contact read access
- [ ] IMPORT-T17: Initial sync imports all Google contacts
- [ ] IMPORT-T18: Incremental sync detects and imports new Google contacts
- [ ] IMPORT-T19: Incremental sync updates existing CRMExtender contacts on Google-side changes
- [ ] IMPORT-T20: Deleted Google contacts do not delete CRMExtender contacts
- [ ] IMPORT-T21: Sync status shows last sync time and error count

---

## 7. Export

**Supports processes:** KP-5 (full flow), KP-6 (full flow).

### 7.1 Requirements

Export produces contact data in three formats:

| Format | Use Case |
|---|---|
| **CSV** | General export, spreadsheet analysis, migration to another system |
| **vCard 4.0** | Import into address book applications |
| **JSON** | API-based export, data portability, GDPR export |

**Export scoping:** Users can export all contacts (with current filter), a filtered subset, selected contacts, a group's members, or a single contact's full record (GDPR).

**GDPR full-record export** includes: all profile fields, all identifiers (including inactive), complete event history, all communications, intelligence items, relationship data, and enrichment data with source attribution.

**Business rules:**
- Export respects the user's current filter and view configuration for bulk exports.
- Large exports (500+ contacts) execute as a background job with download notification.
- CSV export allows field selection.

**Tasks:**

- [ ] EXPORT-01: Implement CSV export with configurable field selection
- [ ] EXPORT-02: Implement vCard 4.0 export
- [ ] EXPORT-03: Implement JSON export (standard and GDPR full-record)
- [ ] EXPORT-04: Implement export scoping (all, filtered, selected, group, single contact)
- [ ] EXPORT-05: Implement background job execution for large exports with notification

**Tests:**

- [ ] EXPORT-T01: CSV export includes all selected fields
- [ ] EXPORT-T02: vCard export produces valid vCard 4.0 files importable by Apple Contacts
- [ ] EXPORT-T03: JSON full-record export includes event history, identifiers, communications, and intelligence
- [ ] EXPORT-T04: Export respects current filter (only exports matching contacts)
- [ ] EXPORT-T05: Group export includes only group members
- [ ] EXPORT-T06: Large export (10,000 contacts) executes as background job with download link
