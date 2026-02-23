# Contact — Entity Base PRD

**Version:** 9.0
**Last Updated:** 2026-02-22
**Status:** Draft
**Product PRD:** [CRMExtender Product PRD]
**Master Glossary:** [glossary.md](glossary.md)

> **V9.0 (2026-02-22):** Added Editable attribute to Core Fields and Computed/Derived Fields tables, defining per-field edit behavior (Direct, Override, Via sub-entity, Computed, System) to prevent Claude Code from making non-editable fields editable.

---

## 1. Entity Definition

### 1.1 Purpose

The Contact is the foundational entity in CRMExtender. Every other subsystem — communications, deals, intelligence, relationship graphs — ultimately resolves back to contacts. A communication has a sender and recipients. A deal has stakeholders. An intelligence item is about a person. The Contact entity answers the question: **"Who is this, and what do we know about them?"**

Unlike traditional CRM contact records that are static address book entries, a CRMExtender Contact is a **living intelligence object** that evolves over time. It is not a snapshot — it is a continuously updated, multi-source, event-sourced record of a person's identity, career, relationships, and engagement with the user.

The Contact is a **system object type** in the unified framework (`is_system = true`), with core fields protected from deletion and specialized behaviors registered per the Custom Objects PRD.

### 1.2 Design Goals

1. **Unified contact identity** — Every person encountered across any channel resolves to a single, canonical contact record via multi-identifier matching.
2. **Continuous intelligence** — Contacts are automatically enriched on creation and continuously monitored for changes. Stale data is detected and flagged.
3. **Temporal history** — Full event-sourced history enables point-in-time reconstruction, employment timelines, and audit compliance.
4. **Relationship modeling** — Contact-to-contact and contact-to-company relationships are modeled as typed, temporal edges with strength scoring.
5. **AI-powered insights** — Every contact has an AI-generated briefing, suggested tags, engagement scoring, and anomaly detection available on demand.
6. **Zero-friction capture** — Contacts are created automatically from email participants, browser extension captures, and enrichment lookups. Manual entry is a last resort, not the default.

### 1.3 Performance Targets

These are entity-wide targets. Action-specific performance targets live in the relevant Action Sub-PRDs.

| Target                                | Value                                                      |
| ------------------------------------- | ---------------------------------------------------------- |
| Contact auto-creation rate            | > 90% of communication participants have matching contacts |
| Contact detail page load              | < 200ms p95                                                |
| Data freshness for monitored contacts | < 7 days since last enrichment check                       |

### 1.4 Core Fields

Fields are described conceptually. Data types and storage details are specified in the Contact Entity TDD.

**Editable column** declares how (or if) the user can modify each field. This prevents implementation from making computed or system fields editable:

- **Direct** — User edits this field inline on the detail page or edit form.
- **Override** — Field is computed by default but the user can manually override. The UI should indicate when a value is overridden vs. computed (e.g., a small "reset to computed" action).
- **Via [sub-entity]** — The displayed value is a summary of a related record. Editing opens the sub-entity's own editor, not an inline edit on the contact card.
- **Computed** — Derived from other data. Not directly editable. The user changes this by modifying the source data it derives from.
- **System** — Set and managed by the system. Never user-editable.

**Sortable / Filterable columns** declare whether the user can sort and filter by each field in list views and grid context menus. Fields marked with † are derived from subqueries; the Entity TDD must implement a caching or denormalization strategy to ensure acceptable sort performance.

| Field              | Description                                                                                                                                 | Required                  | Editable        | Sortable | Filterable | Valid Values / Rules                                                                                                  |
| ------------------ | ------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------- | --------------- | -------- | ---------- | --------------------------------------------------------------------------------------------------------------------- |
| ID                 | Unique identifier. Prefixed ULID with `con_` prefix (e.g., `con_01HX7VFBK3...`). Immutable after creation.                                  | Yes                       | System          | No       | Yes        | Prefixed ULID                                                                                                         |
| First Name         | First name or given name.                                                                                                                   | No                        | Direct          | Yes      | Yes        | Free text                                                                                                             |
| Last Name          | Last name or family name.                                                                                                                   | No                        | Direct          | Yes      | Yes        | Free text                                                                                                             |
| Display Name       | The name shown in all UI contexts. Computed from first + last name unless manually overridden by the user.                                  | Yes                       | Override        | Yes      | Yes        | Free text, auto-computed                                                                                              |
| Primary Email      | The contact's primary email address. Kept in sync with the identifiers model.                                                               | No                        | Via Identifiers | Yes †    | Yes        | Valid email format                                                                                                    |
| Primary Phone      | The contact's primary phone number. Kept in sync with the identifiers model.                                                                | No                        | Via Identifiers | No       | Yes        | E.164 format                                                                                                          |
| Job Title          | Current job title, derived from the most recent current employment record.                                                                  | No                        | Via Employment  | Yes      | Yes        | Free text                                                                                                             |
| Current Company    | Reference to the company the contact currently works for, derived from the most recent current employment record.                           | No                        | Via Employment  | No       | Yes        | Reference to Company entity                                                                                           |
| Company Name       | The current company's name, maintained for display efficiency.                                                                              | No                        | Computed        | Yes      | Yes        | Free text, derived from Company                                                                                       |
| Avatar URL         | Profile photo. May come from enrichment, social profiles, or manual upload.                                                                 | No                        | Direct          | No       | No         | Valid URL                                                                                                             |
| Lead Source        | How this contact first entered the system.                                                                                                  | No                        | Direct          | Yes      | Yes        | `email_sync`, `google_contacts`, `csv_import`, `vcard_import`, `linkedin_capture`, `manual`, `enrichment`, `referral` |
| Lead Status        | Sales lifecycle stage.                                                                                                                      | No, defaults to `new`     | Direct          | Yes      | Yes        | `new`, `contacted`, `qualified`, `nurturing`, `customer`, `lost`, `inactive`                                          |
| Engagement Score   | Composite metric reflecting the health and recency of the relationship. Recomputed periodically from behavioral signals.                    | No, defaults to 0.0       | Computed        | Yes †    | Yes        | 0.0–1.0                                                                                                               |
| Intelligence Score | Data completeness metric reflecting how much the system knows about this contact. Recomputed on enrichment, merge, and on a daily schedule. | No, defaults to 0.0       | Computed        | Yes †    | Yes        | 0.0–1.0                                                                                                               |
| Source             | The first source that created this contact.                                                                                                 | No                        | System          | Yes      | Yes        | Same values as Lead Source                                                                                            |
| Status             | Contact lifecycle status. See Lifecycle section.                                                                                            | Yes, defaults to `active` | System          | Yes      | Yes        | `active`, `incomplete`, `archived`, `merged`                                                                          |
| Created By         | The user who created the contact, or null for auto-created contacts.                                                                        | No                        | System          | No       | Yes        | Reference to User                                                                                                     |
| Created At         | When the contact was created.                                                                                                               | Yes                       | System          | Yes      | Yes        | Timestamp                                                                                                             |
| Updated At         | When the contact was last modified.                                                                                                         | Yes                       | System          | Yes      | Yes        | Timestamp                                                                                                             |

**† Requires caching:** Fields marked with † are derived from subqueries or cross-table computations. The Entity TDD must define a caching or denormalization strategy (e.g., `contacts.primary_email_cache`, `contacts.engagement_score`) with triggers or application logic to keep cached values in sync. Without caching, sorting these fields on large datasets will degrade performance.

### 1.5 Contact Identifiers

A contact is not an email address. A person has multiple emails, phones, social handles, and aliases. The identifier model stores every way a contact can be identified, with lifecycle tracking and confidence scoring. This is the primary mechanism for resolving incoming communications to contacts.

Each identifier has:

| Attribute                | Description                                                               | Rules                                                                                                              |
| ------------------------ | ------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------ |
| Type                     | The kind of identifier.                                                   | `email`, `phone`, `linkedin`, `twitter`, `github`, `slack`, `custom`                                               |
| Value                    | The identifier itself, normalized.                                        | Emails are lowercased and trimmed. Phones are in E.164 format. LinkedIn URLs are canonicalized.                    |
| Label                    | User-facing classification.                                               | `work`, `personal`, `mobile`, `home`, `old`, etc.                                                                  |
| Is Primary               | Whether this is the primary identifier for its type.                      | At most one primary per contact per type.                                                                          |
| Status                   | Lifecycle state of the identifier.                                        | `active`, `inactive`, `unverified`                                                                                 |
| Source                   | How this identifier was discovered.                                       | `google_contacts`, `email_sync`, `linkedin_capture`, `enrichment_apollo`, `enrichment_clearbit`, `manual`, `osint` |
| Confidence               | How confident the system is that this identifier belongs to this contact. | 0.0–1.0. User-entered identifiers have 1.0. Enrichment and auto-detection sources have lower confidence.           |
| Verified                 | Whether the identifier has been confirmed.                                | Confirmed by user, enrichment match, or verified source.                                                           |
| Valid From / Valid Until | Temporal bounds for when this identifier was active.                      | Enables tracking of old email addresses, previous phone numbers, etc. Null Valid Until means still active.         |

**Key business rules:**

- A given identifier value (within its type) can only belong to one contact. If a second contact claims the same email, the system triggers entity resolution to determine whether the contacts should be merged.
- When an identifier becomes inactive (e.g., person leaves a company), it is marked with a Valid Until date but not deleted. Historical communications still resolve through inactive identifiers.
- The primary email and primary phone on the contact record are kept in sync with the identifiers model automatically.

### 1.6 Computed / Derived Fields

These fields are derived from other data. The Editable column indicates how the user changes the underlying data. None of these fields support inline editing on the contact card — the user must edit the source data through the appropriate sub-entity editor, and the computed field updates automatically.

| Field              | Description                          | Editable        | Derivation Logic                                                                                                                                                                                                                  |
| ------------------ | ------------------------------------ | --------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Display Name       | Name shown in UI                     | Override        | Computed from `first_name + ' ' + last_name` unless manually overridden.                                                                                                                                                          |
| Primary Email      | Main email for display               | Via Identifiers | Synced from identifier with `type=email`, `is_primary=true`. If no primary designated, uses the earliest active email.                                                                                                            |
| Primary Phone      | Main phone for display               | Via Identifiers | Synced from identifier with `type=phone`, `is_primary=true`. If no primary designated, uses the earliest active phone.                                                                                                            |
| Job Title          | Current job title                    | Via Employment  | Derived from the most recent employment record where the position is current.                                                                                                                                                     |
| Current Company    | Company reference                    | Via Employment  | Derived from the most recent employment record where the position is current.                                                                                                                                                     |
| Company Name       | Company name for display             | Computed        | Derived from the Current Company's name.                                                                                                                                                                                          |
| Engagement Score   | Relationship health metric (0.0–1.0) | Computed        | Weighted composite of communication frequency, recency, reciprocity, depth, and channel diversity. Recomputed daily. See AI Contact Intelligence Sub-PRD for computation details.                                                 |
| Intelligence Score | Data completeness metric (0.0–1.0)   | Computed        | Weighted scoring based on presence and quality of profile data across categories (name, email, phone, company, social, etc.). Recomputed on enrichment, merge, and daily. See Contact Enrichment Sub-PRD for computation details. |

---

## 2. Entity Relationships

### 2.1 Company

**Nature:** Many-to-many, temporal
**Ownership:** Contact owns the employment relationship
**Description:** A contact's relationship to companies is modeled through employment history. Each employment record captures a position at a company with a title, department, start date, and optional end date. A contact can have multiple positions at the same company over time (left and returned) and can hold simultaneous positions at different companies. The most recent current position determines the contact's displayed company and job title.

Employment records are created from multiple sources: manual entry, email domain resolution (the system infers company affiliation from email domains), enrichment data, LinkedIn capture, and import. Each record carries source attribution and confidence scoring. During contact merge, employment records are deduplicated and consolidated.

The employment relationship is a system Relation Type in the unified framework with temporal metadata.

### 2.2 Communications

**Nature:** Many-to-many
**Ownership:** Communication entity owns the participant relationship
**Description:** Contacts are linked to communications (emails, messages, calls) as participants. Each communication has one or more participants with roles (sender, recipient, CC, BCC, caller, callee). When a communication arrives, the system resolves each participant's identifier (email address, phone number) to a contact record using the identifier model. If no match is found, a new contact is auto-created with `status=incomplete`.

Communication history is the primary source of behavioral signals used to compute engagement scores, responsiveness metrics, and relationship strength.

### 2.3 Conversations

**Nature:** Many-to-many
**Ownership:** Conversation entity owns the participant relationship
**Description:** Conversations are cross-channel, stitched threads that group related communications. A contact participates in a conversation when they appear as a participant in any communication within that conversation. Conversation participation provides higher-level engagement context than individual communications — it captures the full arc of an interaction across email, phone, and meetings.

### 2.4 Deals

**Nature:** Many-to-many
**Ownership:** Deal entity owns the stakeholder relationship
**Description:** Contacts are linked to deals as stakeholders with typed roles — decision maker, influencer, champion, or general participant. A contact can be a stakeholder in multiple deals, and a deal has multiple contact stakeholders. Deal activity appears on the contact's activity timeline.

### 2.5 Groups

**Nature:** Many-to-many
**Ownership:** Group owns the membership relationship
**Description:** Contacts can belong to user-defined groups — flat collections used for organizational purposes such as event attendee lists, advisory boards, deal teams, and conference leads. A contact can belong to multiple groups. Groups can be manual (explicitly managed membership) or smart (membership dynamically computed from a saved filter definition). See the Groups action in the Action Catalog for details.

### 2.6 Tags

**Nature:** Many-to-many
**Ownership:** Shared — tags exist independently and are applied to contacts
**Description:** Lightweight labels applied to contacts for categorization and filtering. Tags can be user-created, imported, rule-based, or AI-suggested. Each tag application carries source attribution and, for AI-suggested tags, a confidence score. AI-suggested tags appear with a "suggested" badge until accepted or dismissed by the user. See the Tags action in the Action Catalog for details.

### 2.7 Notes

**Nature:** One-to-many
**Ownership:** Note entity is attached to the contact via the Universal Attachment pattern
**Description:** Users can add notes to contacts to record context from meetings, calls, or research. Notes support rich text (Markdown) and appear on the contact's activity timeline. Notes are searchable.

### 2.8 Documents

**Nature:** One-to-many
**Ownership:** Document entity is attached to the contact via the Universal Attachment pattern
**Description:** Documents (files, attachments) can be associated with a contact. This includes manually uploaded files and attachments from communications. Documents follow the Document PRD's Universal Attachment pattern.

### 2.9 Events

**Nature:** Many-to-many
**Ownership:** Event entity owns the participant relationship
**Description:** Contacts can be participants in events (meetings, conferences, calls). Event participation is tracked with roles and appears on the contact's activity timeline.

### 2.10 Contact-to-Contact Relationships

**Nature:** Many-to-many, typed, temporal
**Ownership:** Shared — relationships are bidirectional or directional depending on type
**Description:** Contacts have direct relationships with other contacts, modeled as typed edges with temporal bounds, metadata, and strength scoring. Relationship types span hierarchical (reports to, manages), professional (works with, advises, board member), social (knows, introduced by, referred by, mentor), and deal-related (decision maker, influencer, champion) categories.

The `knows` relationship includes a strength score (0.0–1.0) computed from communication patterns, relationship duration, and explicit user-defined connections. Strength decays over time without communication activity.

These relationships power key intelligence features: warm introduction path finding, org chart reconstruction, mutual connection discovery, and key connector identification. See the Relationship Intelligence Sub-PRD for detailed coverage.

---

## 3. Lifecycle

### 3.1 Statuses

| Status       | Description                                                                                                                                               |
| ------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `incomplete` | Auto-created from an unknown identifier. Minimal data — typically just an email address or phone number. Awaiting enrichment or manual completion.        |
| `active`     | Fully identified contact with at least a name and one verified identifier. The standard working state.                                                    |
| `archived`   | User-archived contact. Excluded from active lists and search results, but all data is preserved. Identifiers still resolve for historical communications. |
| `merged`     | Duplicate contact that was absorbed into another record during a merge operation. Soft-deleted — the record is retained for audit purposes.               |

### 3.2 Transitions

| From         | To         | Trigger                                                                                                   |
| ------------ | ---------- | --------------------------------------------------------------------------------------------------------- |
| `incomplete` | `active`   | Enrichment populates sufficient data (name + verified identifier), or user manually completes the record. |
| `active`     | `archived` | User archives the contact.                                                                                |
| `active`     | `merged`   | Contact is identified as a duplicate and absorbed into another contact during merge.                      |
| `archived`   | `active`   | User unarchives the contact.                                                                              |
| `merged`     | `active`   | Split (undo merge) operation restores the original contact from event history.                            |

### 3.3 Creation Sources

| Source             | Trigger                                       | Initial Status                             | Auto-Enrichment        |
| ------------------ | --------------------------------------------- | ------------------------------------------ | ---------------------- |
| `email_sync`       | Unknown email participant during sync         | `incomplete`                               | Yes                    |
| `google_contacts`  | Google People API sync                        | `active`                                   | Yes                    |
| `linkedin_capture` | Browser extension captures LinkedIn profile   | `active`                                   | Optional               |
| `csv_import`       | CSV file upload                               | `active` (if name present) or `incomplete` | Yes                    |
| `vcard_import`     | vCard file upload                             | `active`                                   | Yes                    |
| `manual`           | User creates via UI                           | `active`                                   | Yes                    |
| `enrichment`       | Enrichment discovers a new related contact    | `incomplete`                               | Yes (chain enrichment) |
| `referral`         | User explicitly links a referral relationship | `active`                                   | Yes                    |

### 3.4 Deletion & Data Retention

Contacts are **never hard-deleted** in the normal workflow. The event-sourced model preserves all data for audit and compliance.

**Soft deletion (archive):** Setting status to `archived` hides the contact from active lists. The record, all identifiers, and all history remain in the system. Identifiers continue to resolve for historical communications.

**Hard deletion (GDPR/CCPA):** A dedicated data subject access request (DSAR) workflow:

1. User initiates deletion request with justification.
2. System generates a complete data export for the contact (all events, identifiers, communications, intelligence).
3. After confirmation, the system permanently removes all data for the contact — events, materialized record, identifiers, detail records, intelligence items, graph relationships.
4. Communication participant references are anonymized (contact reference removed, but address preserved for thread integrity).
5. An audit record of the deletion is preserved without any personally identifiable information.

---

## 4. Key Processes

This section defines the end-to-end user experiences for the core Contact entity workflows — the day-to-day interactions that don't fall into complex action sub-PRDs. Complex actions (identity resolution, merge, import, enrichment, AI intelligence, relationship intelligence) define their own key processes in their respective sub-PRDs.

### KP-1: Creating a Contact Manually

**Trigger:** The user clicks "Add Contact" from the contact list view or a global "+" action.

**Step 1 — Creation form:** A creation form opens (modal or dedicated page) with fields: First Name, Last Name, Email, Phone, Company, Job Title, and optional social profile URLs. First Name or Last Name is required. All other fields are optional.

**Step 2 — Inline duplicate detection:** As the user enters identifying information (email, phone, name + company), the system checks for potential matches in real-time. If a match is found, an inline warning appears with options to view the match, merge instead, or create anyway. (Full duplicate detection UX is defined in the Identity Resolution Sub-PRD, KP-2.)

**Step 3 — Save:** The user clicks "Save." The contact is created with status `active` (or `incomplete` if only an identifier was provided). The system triggers auto-enrichment in the background.

**Step 4 — Redirect:** The user is redirected to the new contact's detail page, where they can see the contact record and watch as enrichment populates additional data over the next few minutes.

### KP-2: Browsing and Finding Contacts

**Trigger:** The user navigates to the Contacts section from the main navigation.

**Step 1 — Contact list view:** The user sees a paginated list of contacts displayed in a table/grid. Default sort is by most recently updated. Each row shows: display name, primary email, company name, job title, lead status, engagement score, and any badges (incomplete, possible duplicate, review merge). Contacts with status `archived` or `merged` are not shown by default.

**Step 2 — Filtering:** The user can filter by company, tags, lead status, engagement score range, lead source, and creation date. Filters are combinable with AND logic. A saved filter can be applied as a "view." Active filters are visible as removable chips above the list.

**Step 3 — Searching:** The user can type in a search box for full-text search across name, email, phone, company, title, and tags. Results update as the user types (debounced). Search is typo-tolerant.

**Step 4 — Selection and bulk actions:** The user can select multiple contacts via checkboxes for bulk actions: merge selected, add to group, apply tag, export, archive.

**Step 5 — Navigation to detail:** Clicking a contact row navigates to that contact's detail page (KP-3).

### KP-3: Viewing a Contact's Full Profile

**Trigger:** The user clicks on a contact from the list view, search results, or any link to a contact throughout the system.

**Step 1 — Detail page load:** The contact detail page loads within 200ms. The page is organized using the Card-Based Architecture (per GUI Standards). The header shows the contact's display name, job title, company, avatar, and status. Badges (incomplete, possible duplicate, review merge) are prominent.

**Step 2 — Profile card:** Shows all core fields — name, emails, phones, social profiles, addresses, key dates. Each field shows source attribution on hover (e.g., "From: Apollo enrichment, Confidence: 0.92"). Inline editing is available for all fields.

**Step 3 — Employment history card:** Shows the chronological timeline of positions — company, title, department, dates. Current position is highlighted. Source attribution on each record.

**Step 4 — Activity timeline card:** A unified, chronological feed of all activity related to this contact — communications sent/received, notes added, deal events, tag changes, intelligence items, enrichment updates, merge events. Filterable by activity type.

**Step 5 — Relationships card:** Shows direct relationships with other contacts (who they know, report to, were introduced by). Shows warm intro path availability. Links to the full network visualization (Relationship Intelligence Sub-PRD).

**Step 6 — Intelligence card:** Shows intelligence items (job changes, funding rounds, news mentions), engagement score with trend indicator, intelligence score, and AI briefing (on demand). Links to enrichment details and OSINT monitors.

**Step 7 — Tags and groups card:** Shows applied tags (with source badges for AI-suggested tags) and group memberships.

**Step 8 — Action bar:** Persistent action bar with: Edit, Enrich, Brief Me, Archive, Merge History, Add Note, Add to Group, Add Tag.

### KP-4: Editing a Contact

**Trigger:** The user clicks an editable field on the contact detail page, or clicks "Edit" in the action bar.

**Step 1 — Inline editing:** Fields on the profile card become editable in place. The user modifies a value and clicks away or presses Enter to save. No separate edit screen — editing is inline on the detail page.

**Step 2 — Validation:** The system validates the new value (email format, phone E.164 format, required fields). If validation fails, an inline error message appears below the field.

**Step 3 — Duplicate detection on identifier change:** If the user changes an email or phone to a value that belongs to another contact, the system shows an inline warning with options to view the other contact, merge, or cancel the edit. (See Identity Resolution Sub-PRD, KP-2.)

**Step 4 — Save and audit:** The change is saved immediately. An event is emitted recording the field, old value, new value, timestamp, and user. The Updated At timestamp reflects the change. The activity timeline shows the edit.

### KP-5: Archiving and Restoring a Contact

**Trigger:** The user clicks "Archive" on a contact's detail page or selects contacts in the list view and clicks "Archive Selected."

**Step 1 — Confirmation:** A confirmation dialog asks "Archive [Name]? This will remove them from active lists. Their data will be preserved and identifiers will continue to resolve for historical communications."

**Step 2 — Archive:** The contact's status changes to `archived`. The contact disappears from the default list view. A success message confirms the action with an "Undo" link (available for 10 seconds).

**Step 3 — Finding archived contacts:** The user can see archived contacts by changing the list view filter to include `status=archived`, or by using a dedicated "Archived" view.

**Step 4 — Restoring:** From an archived contact's detail page, the user clicks "Restore." The contact's status returns to `active` and it reappears in the default list view. No confirmation needed for restore.

### KP-6: Managing Tags on a Contact

**Trigger:** The user wants to categorize or label a contact.

**Step 1 — Tag card on detail page:** The tags card shows all currently applied tags as colored chips. AI-suggested tags appear with a "Suggested" badge and a slightly different visual style (e.g., dashed border).

**Step 2 — Adding a tag:** The user clicks "+" on the tag card. A dropdown appears showing existing tags with type-ahead search. The user selects an existing tag or types a new tag name to create one inline.

**Step 3 — Accepting/dismissing AI suggestions:** For AI-suggested tags, the user can click a checkmark to accept (promoting to confirmed, removing the suggested badge) or an "×" to dismiss (removing the suggestion permanently — it will not be re-suggested).

**Step 4 — Removing a tag:** The user clicks "×" on any tag chip to remove it from the contact.

**Step 5 — Bulk tagging from list view:** The user selects multiple contacts in the list view and clicks "Add Tag" to apply a tag to all selected contacts at once.

### KP-7: Managing Groups

**Trigger:** The user wants to organize contacts into collections.

**Step 1 — Adding to a group from detail page:** On the contact's detail page, the groups card shows current memberships. The user clicks "+" to add the contact to a group. A dropdown shows existing groups with type-ahead search. The user selects a group or creates a new one inline.

**Step 2 — Adding to a group from list view:** The user selects multiple contacts and clicks "Add to Group." Same dropdown behavior.

**Step 3 — Browsing groups:** The user navigates to a Groups section from the main navigation. Groups are listed with name, member count, and type (manual or smart). Clicking a group shows its members as a filtered contact list.

**Step 4 — Creating a smart group:** When creating a new group, the user can toggle "Smart Group." This reveals a filter builder (same component as saved views). The user defines filter criteria. Membership is dynamically computed — the user sees a preview of matching contacts before saving.

**Step 5 — Removing from a group:** On the contact detail page, the user clicks "×" on a group chip. From the group's member list, the user can select contacts and click "Remove from Group."

---

## 5. Action Catalog

### 5.1 Create Contact

**Supports processes:** KP-1 (full flow)
**Trigger:** User clicks "Add Contact" in the UI, or system auto-creates from an incoming communication, import, sync, or enrichment discovery.
**Inputs:** At minimum one identifier (email, phone, or social profile). For manual creation: name, optional company, email, phone, social profiles.
**Outcome:** New contact record created. If created manually or from a source with sufficient data, status is `active`. If auto-created from just an identifier, status is `incomplete`. Enrichment is triggered automatically for all creation sources except LinkedIn capture (optional).
**Business Rules:** Before creating, the system checks existing identifiers to avoid duplicates. If a matching identifier is found, the existing contact is returned instead of creating a new one.

### 5.2 Edit Contact

**Supports processes:** KP-4 (full flow)
**Trigger:** User modifies any field on the contact record via the detail page.
**Inputs:** Updated field values.
**Outcome:** Contact record updated. An event is emitted recording the change with the previous value, new value, timestamp, and user. Updated At timestamp reflects the change.
**Business Rules:** All fields except the entity ID are editable. User-entered data always takes precedence over enrichment data. If editing an identifier (email, phone) and the new value conflicts with another contact, the system triggers entity resolution.

### 5.3 View Contact

**Supports processes:** KP-2 (step 5), KP-3 (full flow)
**Trigger:** User navigates to a contact's detail page.
**Inputs:** Contact ID.
**Outcome:** Unified detail page displaying profile information, employment history, communication timeline, relationships, intelligence items, notes, deals, and tags. Rendered via the Card-Based Architecture per the GUI Standards.
**Business Rules:** Contact data loads within 200ms. Intelligence items and graph relationships may be fetched on demand if not cached.

### 5.4 Archive Contact

**Supports processes:** KP-5 (steps 1–2)
**Trigger:** User archives a contact from the detail page or list view.
**Inputs:** Contact ID, optional reason.
**Outcome:** Contact status set to `archived`. Contact removed from active lists and search results. All data preserved. Identifiers continue to resolve for historical communications.
**Business Rules:** Archiving is reversible via unarchive (restores to `active` status).

### 5.5 Delete Contact (GDPR/CCPA Hard Delete)

**Trigger:** User initiates a data subject deletion request.
**Inputs:** Contact ID, deletion justification.
**Outcome:** Complete and permanent removal of all contact data. See Lifecycle section 3.4 for the full DSAR workflow.
**Business Rules:** Requires explicit confirmation. Data export is generated before deletion. Audit record preserved without PII. This action is irreversible.

### 5.6 Tags

**Supports processes:** KP-6 (full flow)

**Trigger:** User adds or removes tags from a contact, or AI suggests a tag.
**Inputs:** Contact ID, tag name (or selection from existing tags).
**Outcome:** Tag applied to or removed from the contact. For AI-suggested tags, tag appears with a "suggested" badge. User can accept (promoting to confirmed) or dismiss.
**Business Rules:** Tags are lightweight labels. Each tag has a name, optional color, and source attribution. A tag can be `manual`, `ai_suggested`, `import`, or `rule`-based. AI-suggested tags carry a confidence score. Users can create new tags inline. Tags are unique by name within a tenant.

### 5.7 Groups

**Supports processes:** KP-7 (full flow)

**Trigger:** User adds or removes a contact from a group, or creates/manages groups.
**Inputs:** Contact ID(s), group ID or new group details.
**Outcome:** Contact added to or removed from a group. Groups can be created, renamed, or deleted.
**Business Rules:** Groups are flat (no hierarchy). A contact can belong to multiple groups. Groups have an owner (the creating user). Manual groups have explicitly managed membership. Smart groups have membership dynamically computed from a saved filter definition (same format as saved views). Smart group membership is recomputed on access or on a configurable schedule.

### 5.8 Identity Resolution & Entity Matching

**Summary:** When data arrives from any source (email sync, enrichment, browser extension, import, manual entry), the system determines whether the incoming data refers to an existing contact or a new person. It uses a tiered approach: exact identifier matching first (email, phone, LinkedIn URL), then fuzzy matching on name and company when exact matches fail. Each potential match is scored using a weighted confidence formula that combines multiple signals. High-confidence matches are auto-merged, medium-confidence matches are auto-merged with a review flag, and low-confidence matches are queued for human review. Tenant-configurable thresholds control the boundaries between these tiers.
**Sub-PRD:** [contact-identity-resolution-prd.md]

### 5.9 Merge & Split

**Summary:** Merge combines two or more duplicate contact records into a single surviving record. The user designates the survivor, and the system transfers all identifiers, employment records, communication history, relationships, events, and detail records to the survivor. Conflicts (differing names, sources) are resolved via a merge preview UI with side-by-side comparison. Post-merge, email domain resolution auto-creates any missing company affiliations. A complete audit trail preserves the absorbed contact's data as a snapshot. Split (undo merge) reverses a bad merge by restoring the original contact records from the event history.
**Sub-PRD:** [contact-merge-split-prd.md]

### 5.10 Contact Import & Export

**Summary:** Import brings contacts into the system from external sources — CSV files, vCard files, Google Contacts sync, and LinkedIn CSV export. Each format goes through a pipeline: parse and validate, run duplicate detection against existing contacts via the entity resolution pipeline, present a preview showing new/update/duplicate classifications, and execute with event emission and enrichment triggering. Export produces contact data in CSV, vCard, or JSON format with configurable scoping (all contacts, filtered subset, group, or single contact's full record including history for GDPR compliance).
**Sub-PRD:** [contact-import-export-prd.md]

### 5.11 Contact Enrichment

**Summary:** Enrichment augments contact records with data from external sources — public profile data, firmographic data, social profiles, photos, and contact details. The system uses a pluggable adapter framework with multiple providers (Apollo, Clearbit, People Data Labs, Google People API, LinkedIn browser extension, email signature parsing). Adapters are selected based on available identifiers, priority, cost, and rate limits. Enrichment is triggered automatically on contact creation, on demand by the user, and periodically for monitored contacts. Each enriched data point carries source attribution and confidence scoring. User-entered data always takes precedence over enrichment data. The enrichment system also includes OSINT monitors for tracking changes to key contacts and companies — job changes, funding rounds, news mentions. The intelligence score (0.0–1.0) is computed from data completeness across weighted categories.
**Sub-PRD:** [contact-enrichment-prd.md]

### 5.12 AI Contact Intelligence

**Summary:** AI-powered features that derive insights from contact data, communication patterns, and external intelligence. Includes: on-demand contact briefings (AI-generated summaries synthesizing all available data about a contact), AI-suggested tags (inferred from communication content, enrichment data, and metadata), natural language search (translating queries like "fintech founders in Boston I haven't talked to in 3 months" into structured filters and graph queries), anomaly detection (alerting on unusual engagement patterns like sudden communication drops or spikes), action recommendations (suggesting follow-ups, introductions, or re-engagement), and behavioral signal tracking (computing engagement metrics from communication frequency, recency, reciprocity, sentiment, and responsiveness). The engagement score (0.0–1.0) is a weighted composite of these behavioral signals.
**Sub-PRD:** [contact-ai-intelligence-prd.md]

### 5.13 Relationship Intelligence

**Summary:** Graph-based intelligence built on the network of relationships between contacts, companies, deals, and events. Contacts and companies exist as nodes with typed, directional, temporal relationship edges spanning hierarchical (reports to, manages), professional (works with, advises, board member, investor), social (knows, introduced by, referred by, mentor), employment (works at), and deal-related (decision maker, influencer, champion) categories. Key intelligence features include: warm introduction path finding (discovering chains of mutual connections to reach a target contact), org chart reconstruction (inferring company organizational structure from relationship data), mutual connection discovery, key connector identification, and relationship strength scoring. Strength is a 0.0–1.0 score on the "knows" relationship that reflects communication patterns, relationship duration, and explicit connections, with decay over inactive periods.
**Sub-PRD:** [contact-relationship-intelligence-prd.md]

---

## 6. Cross-Cutting Concerns

### 6.1 Compliance Requirements

**GDPR:**

- Right of access — Full data export including all events, identifiers, communications, and intelligence.
- Right to rectification — Standard edit flow with event-sourced audit trail.
- Right to erasure — Hard delete workflow (see Action 4.5) with complete data removal and anonymized audit record.
- Right to data portability — JSON and CSV export in machine-readable format.
- Right to object — Contact can be archived to exclude from processing. Enrichment and monitoring can be disabled per contact.
- Consent tracking — Source attribution on all data points. Enrichment sources record consent basis.

**CCPA:**

- Right to know — Same as GDPR right of access.
- Right to delete — Same as GDPR right to erasure.
- Right to opt out — Per-contact enrichment and monitoring opt-out flag.
- Non-discrimination — All contact features available regardless of privacy preference exercise.

### 6.2 OSINT & Enrichment Ethics

- All enrichment sources use publicly available data only.
- Rate limiting respects platform Terms of Service.
- Browser extension only captures data from pages the user actively visits.
- Enrichment can be disabled per tenant or per contact.
- Each enriched data point carries source attribution for transparency.
- No web scraping of private content or login-walled pages.

### 6.3 Temporal History

All contact mutations are stored as immutable events. The system can reconstruct any contact's complete state at any point in time. This provides full audit trails, enables employment timeline visualization, supports compliance with GDPR/CCPA data subject access requests, and powers the split (undo merge) capability. Implementation details for the event store are specified in the Contact Entity TDD.

### 6.4 Data Retention

- Contact records are never hard-deleted except through the GDPR/CCPA DSAR workflow.
- Archived contacts and their full data are retained indefinitely.
- Merged contacts are soft-deleted with full snapshots preserved in the audit trail.
- Event history is retained indefinitely, with periodic snapshots to bound replay depth.

---

## Related Documents

| Document                                                        | Relationship                                                       |
| --------------------------------------------------------------- | ------------------------------------------------------------------ |
| [CRMExtender Product PRD]                                       | Parent product document                                            |
| [Contact Entity UI PRD]                                         | Screen layouts and navigation for contact views                    |
| [Contact Entity TDD]                                            | Technical decisions for contact implementation                     |
| [Contact Identity Resolution Sub-PRD]                           | Detailed identity resolution and entity matching requirements      |
| [Contact Merge & Split Sub-PRD]                                 | Detailed merge and split requirements                              |
| [Contact Import & Export Sub-PRD]                               | Detailed import and export requirements                            |
| [Contact Enrichment Sub-PRD]                                    | Detailed enrichment pipeline and intelligence scoring requirements |
| [Contact AI Intelligence Sub-PRD]                               | Detailed AI-powered intelligence feature requirements              |
| [Contact Relationship Intelligence Sub-PRD]                     | Detailed graph-based relationship intelligence requirements        |
| [Company Management Entity Base PRD](company-management-prd.md) | Company entity — contact-to-company relationship details           |
| [Custom Objects PRD](custom-objects-prd.md)                     | Unified object model, field registry, and relation framework       |
| [Communications PRD](communications-prd.md)                     | Communication entity — participant resolution                      |
| [Conversations PRD](conversations-prd.md)                       | Conversation entity — cross-channel thread stitching               |
| [GUI Standards]                                                 | UI component patterns and design conventions                       |
| [Master Glossary](glossary.md)                                  | Term definitions                                                   |
