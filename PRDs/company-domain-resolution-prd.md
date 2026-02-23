# Company — Domain Resolution & Identifiers Sub-PRD

**Version:** 1.0
**Last Updated:** 2026-02-23
**Status:** Draft
**Entity Base PRD:** [company-entity-base-prd.md]
**Referenced Entity PRDs:** [contact-entity-base-prd.md] (employment linking), [communications-prd.md] (email sync triggers)

---

## 1. Overview

### 1.1 Purpose

Domain resolution is the sole mechanism for automatic company creation. When the system encounters an email address during sync, it extracts the domain, determines whether a company record exists for that domain, and either returns the existing company or creates a new one. This process links the CRM's contact and communication layers to the company entity without requiring manual data entry.

The identifier model supports multiple domains per company, enabling multi-domain duplicate detection and future extensibility to non-domain identifier types (DUNS, EIN, LEI).

### 1.2 Preconditions

- Email sync or contact sync is configured and running.
- Public domain exclusion list is populated in system configuration.
- The Company system object type is registered with domain resolution as a behavior.

---

## 2. Context

### 2.1 Relevant Fields

| Field | Role in This Action |
|---|---|
| Name | Set to domain on auto-creation (placeholder). Enrichment or user edit overwrites later. |
| Primary Domain | Denormalized from company_identifiers. Updated when primary identifier changes. |
| Status | Set to `active` on creation. |

### 2.2 Relevant Relationships

- **Contact→Company Employment** — After a company is resolved or created, contacts with matching email domains are linked via employment records. Only contacts without an existing current employment at a different company are linked.
- **Company Identifiers** — Each company owns one or more domain identifiers. A domain can belong to at most one company (enforced by unique constraint).

### 2.3 Relevant Lifecycle Transitions

- Domain resolution creates companies in `active` status. No lifecycle transitions occur during resolution itself.

### 2.4 Cross-Entity Context

- **Contact Management PRD:** Employment records use the Contact→Company employment Relation Type with `source = 'email_domain'` and `is_current = true`.
- **Communications PRD:** Email sync extracts all domains from sender, recipients (to, cc, bcc) and triggers domain resolution for each non-public domain.

---

## 3. Key Processes

### KP-1: Automatic Domain Resolution During Sync

**Trigger:** Email sync or contact sync encounters an email address.

**Step 1 — Domain extraction:** Extract root domain from the email address. Normalize: strip `www.` prefix, lowercase, extract root from subdomains (`mail.acme.com` → `acme.com`), strip trailing slashes and paths.

**Step 2 — Public domain check:** Check the domain against the public domain exclusion list. If public, return NULL (no company affiliation). Process ends.

**Step 3 — Existing company lookup:** Query `company_identifiers` for `(type='domain', value=normalized_domain)`. If found, return the existing company ID. Process ends.

**Step 4 — Domain validation:** Validate the domain has a working website. If invalid or parked, log for manual review and return NULL. Process ends.

**Step 5 — Auto-create company:** Create a new company record with `name = domain`, `domain = domain`, `status = 'active'`. Register the domain as the primary identifier in `company_identifiers`.

**Step 6 — Trigger enrichment:** Queue Tier 1 enrichment (website scraping) for the new company.

**Step 7 — Contact linking:** Find contacts with email addresses matching the domain who don't already have a current employment record at a different company. Create employment records with `source = 'email_domain'`, `is_current = true`.

### KP-2: Manual Domain Entry

**Trigger:** User enters a domain on a company record via the detail page or creation form.

**Step 1 — Normalize domain:** Apply the same normalization rules as KP-1 step 1.

**Step 2 — Duplicate check:** Query `company_identifiers` for an existing match. If found, present the existing company to the user and offer to merge or cancel. Process branches.

**Step 3a — No duplicate:** Register the domain as an identifier. If the company has no primary domain, set this as primary. Trigger enrichment.

**Step 3b — Duplicate found:** System presents the merge-vs-hierarchy fork. User decides whether these are duplicates (→ merge flow) or hierarchically related (→ hierarchy flow). See Merge Sub-PRD and Hierarchy Sub-PRD.

### KP-3: Managing Company Identifiers

**Trigger:** User navigates to a company's identifier management section.

**Step 1 — View identifiers:** List all identifiers for the company with type, value, primary status, and source.

**Step 2 — Add identifier:** User enters a new domain. System normalizes and checks for duplicates (same as KP-2).

**Step 3 — Set primary:** User designates a different identifier as primary. The denormalized `companies.domain` column is updated.

**Step 4 — Remove identifier:** User removes a non-primary identifier. If attempting to remove the primary, system requires designating another identifier as primary first (or confirms removal of the last identifier).

---

## 4. Domain Normalization

**Supports processes:** KP-1 (step 1), KP-2 (step 1)

### 4.1 Requirements

All domains are normalized before resolution or storage:

1. Strip `www.` prefix.
2. Lowercase all characters.
3. Extract root domain from subdomains: `mail.acme.com` → `acme.com`, `support.acme.com` → `acme.com`.
4. Strip trailing slashes and paths.
5. Strip protocol prefix if present (`https://acme.com` → `acme.com`).

**Edge cases:**

- Country-code second-level domains are preserved: `acme.co.uk` → `acme.co.uk`, not `co.uk`.
- IP addresses are not valid company domains and should be rejected.
- Internationalized domain names (IDN) should be stored in their normalized Unicode form.

**Tasks:**

- [ ] CDOM-01: Implement domain normalization function with country-code TLD handling
- [ ] CDOM-02: Implement public domain exclusion list check
- [ ] CDOM-03: Implement domain validation (HTTP check for working website)

**Tests:**

- [ ] CDOM-T01: Test normalization strips www, lowercases, extracts root domain
- [ ] CDOM-T02: Test country-code TLDs are preserved (co.uk, com.au, co.jp)
- [ ] CDOM-T03: Test public domain list correctly identifies free email providers
- [ ] CDOM-T04: Test domain validation rejects invalid/parked domains

---

## 5. Public Domain Exclusion

**Supports processes:** KP-1 (step 2)

### 5.1 Requirements

Domains belonging to free email providers are never used for company resolution. A contact with only a public-domain email address receives no company affiliation.

**Default exclusion list:**

`gmail.com`, `googlemail.com`, `yahoo.com`, `yahoo.co.uk`, `hotmail.com`, `outlook.com`, `live.com`, `msn.com`, `aol.com`, `icloud.com`, `me.com`, `mac.com`, `mail.com`, `protonmail.com`, `pm.me`, `zoho.com`, `yandex.com`, `gmx.com`, `fastmail.com`, `tutanota.com`, `hey.com`, `comcast.net`, `att.net`, `verizon.net`, `sbcglobal.net`, `cox.net`, `charter.net`, `earthlink.net`.

The list is maintained as system configuration and can be extended by administrators.

**Tasks:**

- [ ] CDOM-04: Implement configurable public domain exclusion list
- [ ] CDOM-05: Admin UI for managing public domain list

**Tests:**

- [ ] CDOM-T05: Test all default public domains are excluded
- [ ] CDOM-T06: Test admin-added domains are excluded
- [ ] CDOM-T07: Test private domains pass through exclusion check

---

## 6. Resolution & Auto-Creation

**Supports processes:** KP-1 (steps 3–7)

### 6.1 Requirements

**Resolution flow:**

1. Look up domain in `company_identifiers` where `type='domain'` and `value=normalized_domain`.
2. If found: return the existing company ID.
3. If not found: validate domain, auto-create company, register identifier, trigger enrichment, link contacts.

**Auto-creation rules:**

- Company name is set to the domain string (placeholder). The enrichment pipeline's overwrite guard will replace this when a real name is discovered.
- Primary domain identifier is registered immediately.
- Status is set to `active`.
- Tier 1 enrichment (website scraping) is triggered as a background job.

**Contact linking rules:**

- Find contacts with email addresses matching the domain.
- Only link contacts that do not already have a current employment record at a different company.
- Create employment junction records with `source = 'email_domain'`, `is_current = true`.
- Set the `company_name` metadata field on the junction row to the company's current name.

**Resolution triggers:**

| Trigger | Timing | Action |
|---|---|---|
| Contact sync (Google Contacts) | During import | Extract domain from each email; resolve or create; link contact. |
| Email sync | During processing | Extract all domains from sender and recipients; resolve or create for non-public domains. |
| Company create/edit | On domain entry | Check identifiers for existing match; flag duplicate if found. |
| Manual entry | User-initiated | User enters domain; system validates and registers. |

**Tasks:**

- [ ] CDOM-06: Implement domain resolution function (lookup → create → link)
- [ ] CDOM-07: Integrate domain resolution into email sync pipeline
- [ ] CDOM-08: Integrate domain resolution into Google Contacts sync
- [ ] CDOM-09: Implement contact-to-company auto-linking on company creation
- [ ] CDOM-10: Emit CompanyCreated and DomainAdded events on auto-creation

**Tests:**

- [ ] CDOM-T08: Test resolution returns existing company for known domain
- [ ] CDOM-T09: Test resolution auto-creates company for unknown private domain
- [ ] CDOM-T10: Test resolution returns NULL for public domain
- [ ] CDOM-T11: Test contact linking creates employment records with correct source
- [ ] CDOM-T12: Test contact linking skips contacts with existing employment at another company
- [ ] CDOM-T13: Test domain uniqueness constraint prevents duplicate registration
- [ ] CDOM-T14: Test enrichment is triggered on auto-creation

---

## 7. Identifier Management API

**Supports processes:** KP-2 (all steps), KP-3 (all steps)

### 7.1 Requirements

| Endpoint | Method | Description |
|---|---|---|
| `/api/v1/companies/{id}/identifiers` | GET | List all identifiers for a company. |
| `/api/v1/companies/{id}/identifiers` | POST | Add a new identifier. Validates uniqueness, normalizes domain. |
| `/api/v1/companies/{id}/identifiers/{identifier_id}` | DELETE | Remove an identifier. Cannot remove the last/only identifier without confirmation. |
| `/api/v1/companies/{id}/identifiers/{identifier_id}/set-primary` | POST | Set this identifier as primary for its type. Updates denormalized `companies.domain`. |

**Tasks:**

- [ ] CDOM-11: Implement identifier CRUD API endpoints
- [ ] CDOM-12: Implement primary identifier designation with denormalization sync
- [ ] CDOM-13: Implement duplicate detection on identifier creation

**Tests:**

- [ ] CDOM-T15: Test identifier API CRUD operations
- [ ] CDOM-T16: Test setting primary updates companies.domain
- [ ] CDOM-T17: Test adding duplicate domain returns error with existing company reference
