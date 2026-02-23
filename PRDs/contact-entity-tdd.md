# Contact Entity — TDD

**Version:** 1.0
**Last Updated:** 2026-02-23
**Status:** Draft
**Scope:** Entity
**Parent Document:** [contact-entity-base-prd.md]
**Product TDD:** [product-tdd.md]

---

## 1. Overview

This document captures technical decisions specific to the Contact entity that extend or deviate from the Product TDD defaults. It covers the contacts read model table, the multi-identifier resolution model, denormalization and caching strategies for sortable fields, employment history tracking, entity-agnostic sub-entities, and the event sourcing approach for contacts.

This is a living document. Decisions are recorded as they are made — both by the product/architecture owner and by Claude Code during implementation. When Claude Code makes an implementation decision not covered here, it should add the decision with rationale to the appropriate section.

---

## 2. Contacts Read Model Table

### 2.1 Event-Sourced Entity with Materialized Read Model

**Decision:** Contacts use event sourcing. The `contacts` table is a materialized read model (current-state projection) derived from the event store. All read operations query the `contacts` table. Write operations append events to the event store and synchronously update the materialized view.

**Rationale:** Contacts require event sourcing because: merge/split operations need complete audit trails with the ability to reconstruct absorbed contacts from snapshots; enrichment requires source attribution on every data point with full provenance history; and GDPR compliance requires the ability to reconstruct and hard-purge complete data histories. Per Product TDD Section 3.4.

**Constraints/Tradeoffs:** Write path is more complex (append event → update materialized view) than conventional CRUD. Accepted because the audit and compliance benefits are non-negotiable for a CRM contact model.

### 2.2 Denormalized Display Fields on Contacts Table

**Decision:** The `contacts` table includes denormalized copies of frequently displayed data that would otherwise require JOINs or subqueries: `email_primary`, `phone_primary`, `job_title`, `company_id`, `company_name`.

**Rationale:** The contact list view is the most frequently accessed screen in the application. Every row needs name, email, company, and title. Without denormalization, each row requires JOINs to `contact_identifiers`, `contacts__companies_employment`, and `companies`. At 515+ contacts, this is tolerable; at 10,000+, it degrades the list view.

**Sync rules:**
- `email_primary` — Synced from `contact_identifiers` where `type='email'`, `is_primary=true`. Fallback: earliest active email by `created_at ASC`.
- `phone_primary` — Synced from `contact_identifiers` where `type='phone'`, `is_primary=true`. Fallback: earliest active phone.
- `job_title` and `company_id` — Synced from the most recent `contacts__companies_employment` record where `is_current=true`.
- `company_name` — Synced from `companies.name` via `company_id`.

**Update triggers:** These fields must be updated whenever the source data changes — identifier creation/update/deletion, employment record changes, company name changes. The event handler pipeline is responsible for keeping them in sync.

### 2.3 Caching Strategy for † Sortable Fields

**Decision:** Fields marked with † in the Entity Base PRD (Primary Email, Engagement Score, Intelligence Score) are stored as direct columns on the `contacts` table rather than computed via subqueries at query time.

**Rationale:** The PRD requires these fields to be sortable. Sorting by a correlated subquery evaluates the subquery for every row in the result set before sorting — with 515 contacts, that's 515 subquery executions per sort. The views engine's `_build_order_by()` puts the field's SQL expression directly in the ORDER BY clause, so the only way to make subquery-backed sorts performant is to denormalize the value into a direct column.

**Implementation:**
- `email_primary` — Already denormalized (see 2.2). The views engine registry should use this column directly rather than a correlated subquery for sort operations.
- `engagement_score` — Stored as `REAL DEFAULT 0.0` on the contacts table. Updated by the daily engagement score computation job. Not updated on every event — the job processes communication events from the last 24 hours and recalculates affected contacts.
- `intelligence_score` — Stored as `REAL DEFAULT 0.0` on the contacts table. Updated on enrichment completion, merge completion, and by a daily scheduled job.

**Registry alignment:** The entity field registry entry for these fields should use the direct column reference for SQL expressions, not a subquery. The current registry may use subqueries for some of these — Claude Code should verify and update the registry to use the cached columns.

---

## 3. Contact Identifiers Model

### 3.1 Multi-Identifier Resolution Table

**Decision:** Every way a contact can be identified — email, phone, social handle, alias — is stored in a single `contact_identifiers` table with a `type` discriminator column. This is the primary lookup table for resolving incoming communications to contacts.

**Rationale:** A single polymorphic identifiers table (rather than separate `contact_emails`, `contact_phones`, etc.) provides: one resolution query for any identifier type, uniform lifecycle tracking (active/inactive/unverified), uniform confidence scoring, and extensibility for new identifier types without schema changes.

**Uniqueness constraint:** `UNIQUE(type, value)` — No two contacts can claim the same identifier value within the same type. If a conflict is detected during creation or import, the identity resolution pipeline is triggered.

**Resolution query pattern:**
```sql
SELECT contact_id, confidence, status
FROM contact_identifiers
WHERE type = :type AND LOWER(value) = LOWER(:value);
```

This single query works for email addresses, phone numbers, LinkedIn URLs, or any future identifier type. The `status` column ensures inactive identifiers still resolve for historical communications.

### 3.2 Primary Identifier Selection Logic

**Decision:** When a contact has multiple identifiers of the same type, the primary is selected by: `is_primary DESC, created_at ASC LIMIT 1`. This means: explicit primary designation wins; if no primary is designated, the oldest identifier wins.

**Rationale:** Oldest-first is a safe default because the first identifier discovered is typically the most authoritative (e.g., the email they correspond with most). User can override by setting `is_primary=true` on a different identifier.

**Post-merge behavior:** After a merge combines identifiers from two contacts, the primary selection re-evaluates. If both contacts had a primary email, the surviving contact's primary wins. If only the absorbed contact had a primary, that designation transfers.

---

## 4. Employment History

### 4.1 Temporal Employment Records

**Decision:** Employment is tracked as temporal records in a junction table (`contacts__companies_employment`) with `started_at`, `ended_at`, `is_current`, title, department, and role. A contact can have multiple current positions (e.g., board member at one company, employee at another).

**Rationale:** Employment history is critical for CRM intelligence — knowing where someone worked before, when they changed jobs, and their career trajectory. A simple `company_id` FK on the contact record loses all history. The temporal model enables: employment timeline on the contact detail page, "career movers" detection, alumni network queries, and job change intelligence items.

**Deduplication key:** `(contact_id, company_id, COALESCE(started_at, ''))` — A contact can only have one employment record per company per start date. NULL start dates are treated as equal for deduplication purposes.

### 4.2 Derived Fields from Employment

**Decision:** `job_title`, `company_id`, and `company_name` on the contacts table are derived from the most recent employment record where `is_current=true`. These are denormalized display fields, not the source of truth.

**Rationale:** The contact list view and detail page header need title and company without JOINing to the employment table every time. The employment table remains the source of truth; the denormalized fields are synced by event handlers.

**Edge cases:**
- If a contact has no current employment, `job_title`, `company_id`, and `company_name` are NULL.
- If a contact has multiple current employments, the most recently started one populates the denormalized fields.
- When an employment record is ended (no longer current), the denormalized fields re-derive from the remaining current records.

---

## 5. Entity-Agnostic Sub-Entities

### 5.1 Shared Tables for Emails, Phones, Addresses

**Decision:** `email_addresses`, `phone_numbers`, and `addresses` are entity-agnostic tables using `(entity_type, entity_id)` columns. Both contacts and companies share these tables.

**Rationale:** Emails, phones, and addresses have identical structure regardless of which entity owns them. Separate tables per entity type (contact_emails, company_emails) would duplicate schema and query logic. The polymorphic approach allows a single set of CRUD operations and UI components.

**Alternatives Rejected:**
- Separate per-entity tables — Cleaner FKs but doubles the table count and maintenance burden for no functional benefit.
- Storing directly on the entity — Doesn't support multi-valued fields (a contact has multiple emails).

**Relationship to contact_identifiers:** The `contact_identifiers` table is specifically for identity resolution — it tracks confidence, verification, and lifecycle for the purpose of matching incoming communications to contacts. The `email_addresses` and `phone_numbers` tables are for display and communication purposes. When an email identifier is created, a corresponding `email_addresses` record may also exist. These are kept in sync but serve different purposes.

---

## 6. Display Name Override Mechanism

### 6.1 Computed with User Override

**Decision:** `display_name` is computed as `first_name + ' ' + last_name` by default, but the user can manually override it. A flag (`display_name_override`) tracks whether the current value is computed or user-specified.

**Rationale:** Most contacts should have their display name auto-computed from their name fields. But some contacts are better known by a nickname, shortened name, or alternative representation (e.g., "Sarah C." instead of "Sarah Chen" to disambiguate from another Sarah Chen). The override flag enables a "Reset to computed" action in the UI.

**Behavior on name change:** When `first_name` or `last_name` is updated: if `display_name_override` is false, `display_name` is recomputed. If `display_name_override` is true, `display_name` is left unchanged (the user's override persists).

---

## 7. Contact Status Transitions

### 7.1 Status Transition Enforcement

**Decision:** Contact status transitions are enforced at the application level, not by database constraints. The valid transitions are defined in the Entity Base PRD (Section 3.2) and the application layer validates transitions before applying them.

**Valid transitions:**
- `incomplete` → `active` (enrichment or manual edit provides sufficient data)
- `active` → `archived` (user archives)
- `active` → `merged` (merge operation absorbs this contact)
- `archived` → `active` (user restores)
- `merged` → `active` (split/undo merge restores this contact)

**Rationale:** Database CHECK constraints can't express valid transitions (only valid states). Application-level enforcement is the only option. The event store records every transition with timestamp and trigger, providing a full audit trail.

---

## 8. Phone Number Normalization

### 8.1 E.164 Format with phonenumbers Library

**Decision:** All phone numbers are normalized to E.164 format using the `phonenumbers` Python library. The default country for parsing is configurable via the `default_phone_country` setting (default: US).

**Rationale:** E.164 provides a single canonical representation for any phone number worldwide, eliminating duplicates caused by formatting differences (e.g., "(555) 123-4567" vs "+15551234567" vs "555-123-4567" are all the same number).

**Validation:** Numbers that fail E.164 parsing are still stored (raw format) but flagged as unverified. This prevents data loss from unusual formats while maintaining normalization for the majority of numbers.

---

## 9. Decisions to Be Added by Claude Code

The following areas will require technical decisions during implementation that should be documented here by Claude Code:

- **Index strategy:** Which indexes are needed on the contacts table and contact_identifiers table for the views engine queries, resolution lookups, and sort operations.
- **Event store schema:** The specific event table structure, event types, and event-to-materialized-view projection logic.
- **FTS integration:** How full-text search on contact fields (name, email, company) is implemented (FTS5 virtual table configuration, triggers for keeping the FTS index in sync).
- **Merge snapshot format:** The JSON structure used for absorbed contact snapshots in the merge audit table.
- **Batch operations:** How bulk operations (bulk tag, bulk archive, bulk merge) are implemented for performance.
- **Domain resolution internals:** How `domain_resolver.py` maps email domains to companies, including public domain detection (gmail.com, outlook.com, etc.).
