# Product Requirements Document: Company Management & Intelligence

## CRMExtender — Company Lifecycle, Domain Resolution, Enrichment & Intelligence

**Version:** 1.0
**Date:** 2026-02-17
**Status:** Draft — Fully reconciled with Custom Objects PRD
**Parent Document:** [CRMExtender PRD v1.1](PRD.md)

> **V1.0 Consolidation (2026-02-17):**
> This document consolidates the Company Detection specification and the Company Intelligence PRD (v1.0, 2026-02-09) into a single authoritative PRD for the Company entity type. All content has been reconciled with the [Custom Objects PRD](custom-objects-prd_v2.md) Unified Object Model:
> - Company is a **system object type** (`is_system = true`, prefix `cmp_`) in the unified framework. Core fields are protected from deletion; specialized behaviors (domain resolution, firmographic enrichment) are registered per Custom Objects PRD Section 22.
> - Entity IDs use **prefixed ULIDs** (`cmp_` prefix, e.g., `cmp_01HX8A...`) per the platform-wide convention (Data Sources PRD, Custom Objects PRD Section 6).
> - The `custom_fields` JSONB column has been **removed**. Custom fields are managed through the **unified field registry** (Custom Objects PRD Section 8).
> - Company hierarchy is modeled as a **system Relation Type** (Company→Company, self-referential, many-to-many with metadata) per Custom Objects PRD Sections 14–15.
> - The event store uses a **per-entity-type event table** (`companies_events`) per Custom Objects PRD Section 19.
> - `companies` is the dedicated **read model table** within the tenant schema, managed through the object type framework.
> - All SQL uses **PostgreSQL** syntax with `TIMESTAMPTZ` timestamps, replacing the PoC-era SQLite schemas.
> - The `Company Data Model` section in the [Contact Management PRD](contact-management-prd_V5.md) (formerly Section 6) has been replaced with a cross-reference to this document.

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Problem Statement](#2-problem-statement)
3. [Goals & Success Metrics](#3-goals--success-metrics)
4. [Company Data Model](#4-company-data-model)
5. [Company Identifiers & Domain Resolution](#5-company-identifiers--domain-resolution)
6. [Duplicate Detection & Merging](#6-duplicate-detection--merging)
7. [Company Hierarchy](#7-company-hierarchy)
8. [Company Enrichment Pipeline](#8-company-enrichment-pipeline)
9. [Company-Level Intelligence & Scoring](#9-company-level-intelligence--scoring)
10. [Social Media Profiles](#10-social-media-profiles)
11. [Asset Storage](#11-asset-storage)
12. [Entity-Agnostic Shared Tables](#12-entity-agnostic-shared-tables)
13. [Company-to-Company Relationships (Neo4j)](#13-company-to-company-relationships-neo4j)
14. [Event Sourcing & Temporal History](#14-event-sourcing--temporal-history)
15. [API Design](#15-api-design)
16. [Current State (PoC Implementation)](#16-current-state-poc-implementation)
17. [Phasing & Roadmap](#17-phasing--roadmap)
18. [Design Decisions](#18-design-decisions)
19. [Dependencies & Related PRDs](#19-dependencies--related-prds)
20. [Open Questions](#20-open-questions)
21. [Future Work](#21-future-work)
22. [Glossary](#22-glossary)

---

## 1. Executive Summary

The Company Management & Intelligence subsystem is the organizational entity layer of CRMExtender. While the Contact Management subsystem answers "Who is this person?", the Company subsystem answers **"What organization do they belong to, and what do we know about it?"** Companies are the structural backbone that groups contacts, contextualizes communications, and enables relationship intelligence at the organizational level.

Unlike traditional CRMs where company records are static address book entries manually created and populated, CRMExtender treats companies as **living intelligence objects** that are automatically discovered from email domains, continuously enriched from multiple data sources, and scored for relationship strength based on communication patterns. The system doesn't just store that a company exists — it knows how it was discovered, when it was last enriched, how strong the relationship is, and where it sits in a corporate hierarchy.

**Core principles:**

- **Domain as canonical identity** — A company's root domain is the single source of truth for deduplication and resolution. Fuzzy name matching is explicitly excluded. Two contacts at the same company may have their Google org field set to "Acme Corp", "Acme Inc", and "ACME" — the system ignores all three and resolves via the shared `acme.com` domain.
- **Auto-discovery from email** — Companies are created automatically when the system encounters a non-public email domain. A contact with `sarah@acmecorp.com` triggers auto-creation of a company record for `acmecorp.com` without any user action.
- **Three-tier enrichment** — Company intelligence is gathered progressively: first from owned data (website scraping, email signatures), then from free public APIs (Wikidata, OpenCorporates), and finally from paid APIs (Clearbit, Apollo, Crunchbase) — all through a pluggable provider architecture shared with contact enrichment.
- **Precomputed relationship intelligence** — Relationship strength scores are computed from communication patterns (recency, frequency, reciprocity, breadth, duration) and stored for instant sorting and display. Users pull intelligence through saved views rather than being interrupted by alerts.
- **Hierarchy modeling** — Parent/subsidiary, division, acquisition, and spinoff relationships are modeled with temporal bounds, enabling corporate structure representation at any depth.
- **Event-sourced history** — All company mutations are stored as immutable events in `companies_events`, enabling full audit trails, point-in-time reconstruction, and compliance support.

**Current state:** The PoC implements domain-based company resolution during Google Contacts sync (`poc/sync.py`), auto-creation of placeholder company records named after their domain, and batch website enrichment that discovers real company names from JSON-LD and Open Graph metadata. This PRD defines the requirements for the full company management system.

**Relationship to other PRDs:**

- **[Custom Objects PRD](custom-objects-prd_v2.md)** — The Company entity type is a **system object type** in the unified framework. Its table structure, field registry, event sourcing, and relation model are governed by the Custom Objects PRD. This PRD defines the Company-specific behaviors (domain resolution, firmographic enrichment, hierarchy management, relationship scoring) that are registered with the object type framework. Custom fields on Companies are managed through the unified field registry, not a JSONB column.
- **[Contact Management PRD](contact-management-prd_V5.md)** — Contacts link to companies through the Contact→Company employment Relation Type (defined in the Contact Management PRD Section 5.5). The Contact PRD's Section 6 is a brief cross-reference to this document for the Company data model, domain resolution, and company-to-company relationships.
- **[Communication & Conversation Intelligence PRD](email-conversations-prd.md)** — Communications are linked to companies indirectly through contact participants. Email domain extraction during sync triggers company auto-creation. The Communication PRD owns conversation and communication entities; this PRD consumes them for relationship scoring.
- **[Data Sources PRD](data-sources-prd_V1.md)** — The Company virtual schema table is derived from the Company object type's field registry. The prefixed entity ID convention (`cmp_`) enables automatic entity detection in data source queries.
- **[Views & Grid PRD](views-grid-prd_V5.md)** — Company views, filters, sorts, and inline editing operate on fields defined in the Company field registry. Precomputed scores enable instant sort-by-relationship-strength on company list views.

---

## 2. Problem Statement

### The Hollow Company Record Problem

Traditional CRM company records are hollow shells. They exist because a user typed a company name, or because an import routine pulled an organization field from a vCard. They have a name and nothing else — no domain, no industry, no enrichment, no intelligence. Worse, the same company appears multiple times under different names because there is no canonical identifier to prevent duplication.

**The consequences for CRM users:**

| Pain Point | Impact |
|---|---|
| **Rampant duplicates** | The same company appears under "Acme Corp", "Acme Corporation", and "ACME" because auto-creation is name-based with no deduplication. Each duplicate has its own contacts, fragmenting relationship history. |
| **Empty records** | Auto-created companies have a name and nothing else. No domain, no address, no industry, no context. Users must manually research and populate every field. |
| **No hierarchy** | Parent/subsidiary relationships (Alphabet → Google → Google Cloud) cannot be represented. All companies are flat peers, losing organizational context critical for enterprise sales and relationship management. |
| **No enrichment** | The system never proactively gathers intelligence about a company. Industry, size, funding, social presence, and contact information must all be entered by hand. |
| **No relationship intelligence** | The data to answer "which companies am I most engaged with?" exists across hundreds of emails and meetings, but no mechanism surfaces it. |
| **Missed company discovery** | Email addresses contain company domains, but the system only creates companies from explicitly entered data, ignoring the richest signal available: the email domain. |
| **No social presence tracking** | Company social media profiles are not tracked, monitored, or linked. Changes in a company's public profile (leadership changes, rebranding, acquisitions) go unnoticed. |
| **Stale data** | Companies merge, rebrand, change addresses, and grow — but the CRM record remains frozen at the moment it was created, silently degrading. |

---

## 3. Goals & Success Metrics

### Primary Goals

1. **Domain-based canonical identity** — Use root domain as the canonical company identifier, supporting multiple domains per company via a `company_identifiers` table. Eliminate name-based duplication entirely.
2. **Auto-discovery from email** — Automatically create and link companies when non-public email domains are encountered during sync, with no user action required.
3. **Three-tier enrichment pipeline** — Automatically gather company intelligence from owned data (website scraping, email signatures), free public APIs (Wikidata, OpenCorporates), and paid APIs (Clearbit, Apollo, Crunchbase), with a pluggable provider architecture shared with contact enrichment.
4. **Hierarchy modeling** — Model parent/subsidiary, division, acquisition, and spinoff relationships with arbitrary nesting depth and temporal tracking.
5. **Company merging** — When duplicates are detected, merge all associated entities (contacts, employment records, relationships, event participants) to the surviving record and soft-delete the absorbed record, with full audit logging.
6. **Precomputed relationship intelligence** — Relationship strength scores calculated from communication patterns, sortable in views, with transparent factor breakdowns.
7. **Social media profile tracking** — Company social profiles with tiered monitoring (high/standard/low/none) and change detection.
8. **Field-level provenance** — Every enriched field carries source attribution, confidence scoring, and timestamp for audit and conflict resolution.

### Non-Goals

- **Fuzzy name matching** — Duplicate detection is strictly domain-based. Name similarity matching (e.g., "Acme Corp" vs "Acme Corporation") produces too many false positives and is excluded from scope.
- **Real-time social media monitoring** — Social profile scanning follows a configurable cadence (weekly/monthly/quarterly), not real-time streaming.
- **Paid API cost controls** — Budget limits, approval workflows, and per-lookup caps for paid enrichment providers are deferred.
- **Trend calculations** — Period-over-period analysis and trend detection formulas are deferred to a future iteration.
- **Contact identity resolution** — The [Contact Management PRD](contact-management-prd_V5.md) covers probabilistic entity matching for contacts. This PRD focuses on company-level deduplication and intelligence.

### Success Metrics

| Metric | Target | Measurement |
|---|---|---|
| Company auto-creation rate | >90% of non-public email domains have matching company records | `SELECT COUNT(DISTINCT domain) FROM company_identifiers / COUNT(DISTINCT email_domain) FROM contacts` |
| Duplicate company rate | <1% after domain-based resolution | Periodic duplicate scan audit |
| Enrichment coverage | >70% of companies have enrichment data within 48 hours of creation | Companies with at least one `completed` enrichment run / total companies |
| Company name placeholder rate | <10% of companies still named after their domain after 7 days | `SELECT COUNT(*) FROM companies WHERE name = domain / total` |
| Relationship score freshness | <24 hours for companies with recent communications | `entity_scores WHERE computed_at > NOW() - INTERVAL '24 hours'` |
| Company detail page load | <200ms p95 | APM monitoring on `/companies/{id}` |
| Merge execution time | <2 seconds p95 | APM monitoring on merge endpoint |

---

## 4. Company Data Model

### 4.1 Company Record — Read Model Table (System Object Type)

> Company is a **system object type** (`is_system = true`, prefix `cmp_`). The `companies` table is its dedicated read model table within the tenant schema, managed through the object type framework. Core fields are marked `is_system = true` and cannot be archived or deleted.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | TEXT | **PK** | Prefixed ULID: `cmp_` prefix (e.g., `cmp_01HX8A...`). Platform-wide convention. |
| `tenant_id` | TEXT | NOT NULL | Tenant identifier. Denormalized from schema context for cross-schema queries. |
| `name` | TEXT | NOT NULL | Company display name. Initially set to domain for auto-created companies; enrichment overwrites when a real name is discovered. **Display name field** for this object type. |
| `domain` | TEXT | UNIQUE | Primary web domain (e.g., `acmecorp.com`). Denormalized from `company_identifiers` where `is_primary = true`. Used for email domain matching and display. |
| `industry` | TEXT | | Industry classification. |
| `size_range` | TEXT | | Employee count range: `1-10`, `11-50`, `51-200`, `201-500`, `501-1000`, `1001-5000`, `5001-10000`, `10001+`. Aligned with LinkedIn's classification. |
| `employee_count` | INTEGER | | Raw employee count when known. When available, `size_range` is derived from it. |
| `location` | TEXT | | Headquarters location (city, state/country). Denormalized from the primary address in the `addresses` table for display. |
| `description` | TEXT | | Brief company description. |
| `logo_url` | TEXT | | Company logo URL (object storage path or external URL). See Section 11 for asset storage. |
| `website` | TEXT | | Company website URL (may differ from domain, e.g., `https://www.acmecorp.com/about`). |
| `linkedin_url` | TEXT | | Company LinkedIn page URL. |
| `stock_symbol` | TEXT | | Stock ticker symbol (e.g., `GOOGL`, `AAPL`). |
| `founded_year` | INTEGER | | Year the company was founded. |
| `revenue_range` | TEXT | | Annual revenue range. |
| `funding_total` | TEXT | | Total funding raised. |
| `funding_stage` | TEXT | | Latest funding stage (see Section 4.3). |
| `status` | TEXT | NOT NULL, DEFAULT `'active'` | Record status: `active`, `merged`, `archived`. |
| `created_at` | TIMESTAMPTZ | NOT NULL | Record creation timestamp. |
| `updated_at` | TIMESTAMPTZ | NOT NULL | Last modification timestamp. |
| `created_by` | TEXT | | User or system process that created this record. |
| `updated_by` | TEXT | | User or system process that last modified this record. |
| `archived_at` | TIMESTAMPTZ | | Timestamp of archival (NULL if active). Universal field per Custom Objects PRD Section 7. |

### 4.2 Employee Count Ranges

Ranges are aligned with LinkedIn's widely-used classification:

| Range | Value |
|---|---|
| 1–10 | `1-10` |
| 11–50 | `11-50` |
| 51–200 | `51-200` |
| 201–500 | `201-500` |
| 501–1,000 | `501-1000` |
| 1,001–5,000 | `1001-5000` |
| 5,001–10,000 | `5001-10000` |
| 10,001+ | `10001+` |

When a raw `employee_count` is available, `size_range` is derived from it. When only a range is available from a provider, `size_range` is stored directly and `employee_count` remains NULL.

### 4.3 Funding Stage Values

| Value | Description |
|---|---|
| `pre_seed` | Pre-seed funding |
| `seed` | Seed round |
| `series_a` | Series A |
| `series_b` | Series B |
| `series_c` | Series C |
| `series_d_plus` | Series D or later |
| `ipo` | Publicly traded |
| `private` | Private, no known funding |
| `bootstrapped` | Self-funded |

### 4.4 Registered Behaviors

Per Custom Objects PRD Section 22, the Company system object type registers the following specialized behaviors:

| Behavior | Trigger | Description |
|---|---|---|
| Domain resolution | On creation, on domain change | Resolve company identity from email domain; check for duplicates via `company_identifiers`. |
| Firmographic enrichment | On creation, on schedule | Run enrichment providers (website scraper, Wikidata, paid APIs) to populate company fields. |
| Relationship strength scoring | On communication event, daily decay | Compute relationship strength from communication patterns; store in `entity_scores`. |
| Hierarchy inference | On enrichment (Wikidata, SEC) | Detect parent/subsidiary relationships from enrichment data; suggest hierarchy links. |

---

## 5. Company Identifiers & Domain Resolution

### 5.1 Company Identifiers Table

Stores multiple domains per company, enabling multi-domain duplicate detection. Mirrors the pattern of `contact_identifiers` for contacts.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | TEXT | **PK** | Prefixed ULID. |
| `company_id` | TEXT | NOT NULL, FK → `companies(id)` ON DELETE CASCADE | Owning company. |
| `type` | TEXT | NOT NULL, DEFAULT `'domain'` | Identifier type. Currently only `domain`; extensible to `duns`, `ein`, `lei`, etc. |
| `value` | TEXT | NOT NULL | The identifier value (e.g., `acmecorp.com`). |
| `is_primary` | BOOLEAN | DEFAULT false | TRUE for the primary identifier of this type. Exactly one primary domain per company. |
| `source` | TEXT | | Discovery source: `email_sync`, `website_scrape`, `manual`, `enrichment`, `merge`. |
| `created_at` | TIMESTAMPTZ | NOT NULL | |
| `updated_at` | TIMESTAMPTZ | NOT NULL | |

**Constraints:**

- `UNIQUE(type, value)` — A domain can belong to at most one company.
- Index on `(company_id)` for listing a company's identifiers.
- Index on `(type, value)` for fast resolution lookups.

The primary domain is denormalized on `companies.domain` for display and fast matching. The authoritative data lives in `company_identifiers`.

### 5.2 Domain Resolution Flow

Domain resolution is the process by which the system identifies or creates a company record from an email address. It is the sole mechanism for company auto-creation — the Google Contacts organization name field is explicitly ignored.

```
email → extract domain → public? → return NULL (no company affiliation)
                       → private → normalize to root domain
                                 → check company_identifiers(type='domain', value=domain)
                                   → found? → return existing company ID
                                   → not found → validate domain has working website
                                                → valid? → auto-create company
                                                          (name=domain, domain=domain)
                                                        → register domain identifier
                                                        → trigger Tier 1 enrichment
                                                        → return new company ID
                                                → invalid? → log for manual review
                                                           → return NULL
```

### 5.3 Domain Normalization

All domains are normalized before resolution:

- Strip `www.` prefix.
- Lowercase all characters.
- Extract root domain from subdomains: `mail.acme.com` → `acme.com`, `support.acme.com` → `acme.com`.
- Strip trailing slashes and paths.

### 5.4 Public Domain Exclusion

Domains belonging to free email providers are never used for company resolution. A contact with only a public-domain email address receives no company affiliation. The exclusion list:

`gmail.com`, `googlemail.com`, `yahoo.com`, `yahoo.co.uk`, `hotmail.com`, `outlook.com`, `live.com`, `msn.com`, `aol.com`, `icloud.com`, `me.com`, `mac.com`, `mail.com`, `protonmail.com`, `pm.me`, `zoho.com`, `yandex.com`, `gmx.com`, `fastmail.com`, `tutanota.com`, `hey.com`, `comcast.net`, `att.net`, `verizon.net`, `sbcglobal.net`, `cox.net`, `charter.net`, `earthlink.net`.

This list is maintained as a system configuration and can be extended by administrators.

### 5.5 Contact Linking

When a company is resolved from a domain, contacts with email addresses matching that domain are linked via the Contact→Company employment Relation Type (defined in [Contact Management PRD](contact-management-prd_V5.md) Section 5.5):

- Create a `contacts__companies_employment` junction row with `is_current = true` and `source = 'email_domain'`.
- Only link contacts that do not already have a current employment record at a different company — do not override existing manual assignments.
- The `company_name` metadata field on the junction row is set to the company's current name at the time of linking.

### 5.6 Resolution Triggers

| Trigger | Timing | Action |
|---|---|---|
| Contact sync (Google Contacts) | During contact import | Extract domain from each contact email; resolve or create company; link contact. |
| Email sync | During communication processing | Extract all domains from sender, recipients (to, cc, bcc); resolve or create companies for non-public domains. |
| Company create/edit | On domain entry | Check `company_identifiers` for existing match; flag duplicate if found. |
| Manual entry | User-initiated | User enters a domain on a company record; system validates and registers. |

---

## 6. Duplicate Detection & Merging

### 6.1 Detection Strategy

The primary domain name is the canonical company duplicate identifier. Detection is strictly domain-based — no fuzzy name matching. A domain can belong to at most one company (enforced by `UNIQUE(type, value)` on `company_identifiers`).

When a duplicate is detected during company creation or editing, the system blocks the operation and presents the user with the existing matching company, offering to merge or cancel.

### 6.2 The Merge-vs-Hierarchy Fork

When a user indicates that two company records are related, the system asks: **"Are these duplicates, or are you establishing a company hierarchy?"**

- **Duplicate** — Proceeds to the merge flow (Section 6.3).
- **Hierarchy** — Proceeds to the hierarchy flow (Section 7), where the user selects parent/child roles, hierarchy type, and effective date.

### 6.3 Merge Preview

`GET /api/v1/companies/merge?ids=X&ids=Y`

- Side-by-side company cards showing: name, domain, industry, employee count, contact count, relationship count, event participant count, identifier count, hierarchy relationships.
- Conflict resolution: radio buttons for each field where both companies have distinct values.
- Radio buttons to designate the surviving company (which `cmp_` ID persists).
- Combined/deduplicated totals showing the merged result.

### 6.4 Merge Execution Flow

`POST /api/v1/companies/merge/confirm`

1. **User designates the survivor** — The surviving company ID persists; the absorbed company is soft-deleted.

2. **Snapshot** — The absorbed company and all sub-entities are serialized as JSON and stored in the `company_merges` audit table.

3. **Entity reassignment** — All entities referencing the absorbed company are reassigned to the surviving company within a single PostgreSQL transaction:

   | Entity | Reassignment |
   |---|---|
   | `contacts__companies_employment` (where `target_id` = absorbed) | UPDATE `target_id` to surviving company ID. Deduplicate: if both companies had the same contact, keep the record with more metadata; delete the other. |
   | `event_participants` (where `entity_type = 'company'` and `entity_id` = absorbed) | UPDATE `entity_id` to surviving company ID. |
   | Relation instances involving the absorbed company (any Relation Type) | UPDATE entity IDs to surviving company. Deduplicate if both companies had the same relationship to a third entity. |

   Conversations and communications are **not** directly reassigned — they are linked to companies indirectly through contact participants. Reassigning employment records carries these associations automatically.

4. **Domain consolidation** — All `company_identifiers` from the absorbed company are reassigned to the surviving company. The surviving company's primary domain is preserved unless it had none (in which case the absorbed company's primary domain is promoted).

5. **Field conflict resolution** — When both companies have values for the same field, the surviving record's non-NULL values take precedence. Empty fields on the surviving record are filled from the absorbed record. Full per-field conflict resolution UI is a later phase (see Section 21).

6. **Hierarchy preservation** — If the absorbed company had hierarchy relationships, those are transferred to the surviving company. If both companies were children of the same parent (with the same hierarchy type), the duplicate hierarchy row is removed.

7. **Soft delete** — The absorbed company record is set to `status = 'merged'`.

8. **Emit event** — A `CompanyMerged` event is written to `companies_events` for the surviving company, recording the merge details.

9. **Audit log** — The merge is recorded in the `company_merges` table.

### 6.5 Company Merges Table

Audit log for company merge operations.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | TEXT | **PK** | Prefixed ULID. |
| `surviving_company_id` | TEXT | NOT NULL, FK → `companies(id)` | The company that persists. |
| `absorbed_company_id` | TEXT | NOT NULL | The company that was absorbed (may be soft-deleted, so no FK constraint). |
| `absorbed_company_snapshot` | JSONB | NOT NULL | Full JSON serialization of the absorbed company record at merge time. |
| `contacts_reassigned` | INTEGER | DEFAULT 0 | Count of employment records reassigned. |
| `relations_reassigned` | INTEGER | DEFAULT 0 | Count of relation instances reassigned. |
| `events_reassigned` | INTEGER | DEFAULT 0 | Count of event participants reassigned. |
| `relations_deduplicated` | INTEGER | DEFAULT 0 | Count of duplicate relations removed. |
| `merged_by` | TEXT | FK → `users(id)` ON DELETE SET NULL | User who initiated the merge. |
| `merged_at` | TIMESTAMPTZ | NOT NULL | Merge timestamp. |

**Indexes:**

- Index on `(surviving_company_id)` for audit trail queries.
- Index on `(absorbed_company_id)` for undo/lookup queries.

---

## 7. Company Hierarchy

### 7.1 Overview

Company hierarchy models organizational structure: parent companies, subsidiaries, divisions, acquisitions, and spinoffs. This is fundamentally different from peer business relationships (PARTNER, VENDOR) — hierarchy is tree-structured, supports arbitrary nesting, requires temporal tracking, and carries type-specific metadata.

### 7.2 System Relation Type Definition

Company hierarchy is implemented as a **system Relation Type** in the Custom Objects framework (self-referential Company→Company relationship):

| Property | Value |
|---|---|
| `slug` | `company_hierarchy` |
| `source_object_type` | `companies` (parent) |
| `target_object_type` | `companies` (child) |
| `cardinality` | `many_to_many` |
| `directionality` | `bidirectional` |
| `source_field_label` | Subsidiaries |
| `target_field_label` | Parent Companies |
| `has_metadata` | `true` |
| `neo4j_sync` | `true` |
| `is_system` | `true` |
| `cascade_behavior` | `nullify` |

### 7.3 Junction Table: `companies__companies_hierarchy`

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | TEXT | **PK** | Relation instance ID (prefixed ULID). |
| `source_id` | TEXT | NOT NULL, FK → `companies(id)` ON DELETE CASCADE | The parent company. |
| `target_id` | TEXT | NOT NULL, FK → `companies(id)` ON DELETE CASCADE | The child company. |
| `hierarchy_type` | TEXT | NOT NULL | `subsidiary`, `division`, `acquisition`, `spinoff`. |
| `effective_date` | DATE | | When the hierarchy relationship began. |
| `end_date` | DATE | | When the hierarchy relationship ended (NULL = still active). |
| `metadata` | JSONB | | Type-specific data (acquisition amount, deal terms, etc.). |
| `created_by` | TEXT | FK → `users(id)` ON DELETE SET NULL | |
| `updated_by` | TEXT | FK → `users(id)` ON DELETE SET NULL | |
| `created_at` | TIMESTAMPTZ | NOT NULL | |
| `updated_at` | TIMESTAMPTZ | NOT NULL | |

**Constraints:**

- `CHECK (hierarchy_type IN ('subsidiary', 'division', 'acquisition', 'spinoff'))`.
- `CHECK (source_id != target_id)` — A company cannot be its own parent.
- Index on `(source_id)` for "list this company's children" queries.
- Index on `(target_id)` for "find this company's parent" queries.
- Index on `(hierarchy_type)` for type-filtered queries.

### 7.4 Hierarchy Types

| Type | Description | Example |
|---|---|---|
| `subsidiary` | Parent company owns or controls a child company | Alphabet → Google |
| `division` | Parent company's internal business unit | Google → Google Cloud |
| `acquisition` | Parent company acquired the child company | Google → YouTube (2006) |
| `spinoff` | Child company was spun off from the parent | eBay → PayPal |

### 7.5 Structural Properties

- **Arbitrary nesting** — Hierarchies can nest to any depth (A → B → C → D).
- **Multiple parents** — A company can have multiple parent relationships (e.g., a joint venture with two parent companies, or a company that was a division of one company and later acquired by another).
- **Temporal** — `effective_date` and `end_date` track when hierarchy relationships begin and end, supporting historical representations (e.g., YouTube was independent until 2006, then acquired by Google).
- **Single directional row** — Each relationship is stored as one row with `source_id` (parent) → `target_id` (child). The bidirectional Relation Type definition means the UI can traverse from either direction.

### 7.6 Display

The UI displays hierarchy as flat sections on the company detail page:

- **Parent Companies** section — Shows the company's parent(s) with hierarchy type and effective date.
- **Subsidiaries** section — Shows child companies with hierarchy type and effective date.

Both sections link to the related company's detail page. Tree or org-chart visualization is deferred to future work (Section 21).

### 7.7 Separate Entities for Communications

Companies in a hierarchy are treated as separate entities for communication purposes. Viewing a parent company does **not** aggregate contacts, conversations, or communications from its subsidiaries. Each company in the hierarchy maintains its own independent communication history and relationship scores.

---

## 8. Company Enrichment Pipeline

### 8.1 Overview

The enrichment pipeline is entity-agnostic — the same architecture serves both companies and contacts. It uses a pluggable provider model where each data source implements a common interface. This section defines the company-specific aspects of the shared enrichment pipeline.

### 8.2 Three-Tier Source Architecture

#### Tier 1: Owned Data (Free, Immediate)

| Provider | Input | Output |
|---|---|---|
| **Website scraper** | Company domain | Description, address, phone, email, social links, structured data (schema.org), company name. |
| **Email signature parser** | Communications in database | Company address, phone, website, social links. |

Tier 1 providers run immediately on domain entry and retroactively over existing communications.

#### Tier 2: Free Public APIs

| Provider | Input | Output |
|---|---|---|
| **Wikidata / Wikipedia** | Company name/domain | Founding date, industry, headquarters, employee count, parent company, description. |
| **OpenCorporates** | Company name/jurisdiction | Corporate registration, status, officers. |
| **SEC EDGAR** | Company name/stock symbol | Filings, revenue, executive info (US public companies only). |

Tier 2 providers run as background batch jobs after initial creation.

#### Tier 3: Paid APIs (Future)

| Provider | Input | Output |
|---|---|---|
| **Clearbit** | Domain | Full company profile, tech stack, employee count, funding. |
| **Apollo** | Domain | Company data, employee directory, contact info. |
| **Crunchbase** | Company name | Funding rounds, investors, acquisitions, leadership. |

Tier 3 providers are integration points designed into the architecture but implemented in a later phase.

### 8.3 Provider Interface

Each enrichment provider implements a common interface:

```python
class EnrichmentProvider:
    name: str                    # e.g., "website_scraper", "wikidata"
    tier: int                    # 1, 2, or 3
    entity_types: list[str]      # ["company"], ["contact"], or ["company", "contact"]
    rate_limit: RateLimit        # Requests per time window
    cost_per_lookup: float       # 0.0 for free providers
    refresh_cadence: timedelta   # Recommended re-enrichment interval

    def enrich(self, entity: dict) -> list[FieldValue]:
        """Returns a list of (field_name, value, confidence) tuples."""
        ...
```

New providers are registered in a provider registry and automatically available to the enrichment pipeline.

### 8.4 Enrichment Triggers

| Trigger | Behavior |
|---|---|
| **Domain entry** (create/edit) | Immediate: Tier 1 website scraping. Background: Tier 2 API lookups. |
| **Email sync** | Auto-create company for new non-public domains with valid websites; trigger Tier 1 enrichment. |
| **Periodic refresh** | Scheduled job re-enriches companies whose data is older than the provider's `refresh_cadence`. |
| **On-demand** | User clicks "Refresh" on a company detail page; runs all applicable providers. |
| **Retroactive batch** | User initiates a scan; runs email signature parsing and Tier 2 lookups across all companies. |

### 8.5 Enrichment Run Tracking

**`enrichment_runs`** — Tracks enrichment process execution for both companies and contacts (entity-agnostic).

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | TEXT | **PK** | Prefixed ULID. |
| `entity_type` | TEXT | NOT NULL | `'company'` or `'contact'`. |
| `entity_id` | TEXT | NOT NULL | ID of the entity being enriched. |
| `provider` | TEXT | NOT NULL | Provider name (e.g., `'website_scraper'`, `'wikidata'`). |
| `status` | TEXT | NOT NULL, DEFAULT `'pending'` | `'pending'`, `'running'`, `'completed'`, `'failed'`. |
| `started_at` | TIMESTAMPTZ | | |
| `completed_at` | TIMESTAMPTZ | | |
| `error_message` | TEXT | | Error details if failed. |
| `created_at` | TIMESTAMPTZ | NOT NULL | |

**Constraints:**

- `CHECK (entity_type IN ('company', 'contact'))`.
- `CHECK (status IN ('pending', 'running', 'completed', 'failed'))`.
- Index on `(entity_type, entity_id)` for listing an entity's enrichment history.
- Index on `(provider)` for provider-level analytics.
- Index on `(status)` for queue processing.

### 8.6 Enrichment Field Values

**`enrichment_field_values`** — Field-level provenance for enrichment results.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | TEXT | **PK** | Prefixed ULID. |
| `enrichment_run_id` | TEXT | NOT NULL, FK → `enrichment_runs(id)` ON DELETE CASCADE | The enrichment run that produced this value. |
| `field_name` | TEXT | NOT NULL | Target field (e.g., `'description'`, `'industry'`). |
| `field_value` | TEXT | | The enriched value. |
| `confidence` | REAL | NOT NULL, DEFAULT 0.0 | Confidence score (0.0–1.0). |
| `is_accepted` | BOOLEAN | DEFAULT false | Whether this value was applied to the entity record. |
| `created_at` | TIMESTAMPTZ | NOT NULL | |

**Indexes:**

- Index on `(enrichment_run_id)`.
- Index on `(field_name, is_accepted)`.

### 8.7 Confidence Thresholds

Each field has a minimum confidence threshold. Values below the threshold are stored in `enrichment_field_values` with `is_accepted = false` and queued for human review. Values at or above the threshold are auto-applied to the entity record. Default thresholds can be adjusted in system settings.

### 8.8 Conflict Resolution

When a new enrichment run returns a value for a field that already has one, the following priority hierarchy determines which value wins:

| Priority | Source | Auto-Override Behavior |
|---|---|---|
| 1 (highest) | `manual` | Never auto-overridden by any source. |
| 2 | `paid_api` | Overrides lower-priority sources. |
| 3 | `free_api` | Overrides lower-priority sources. |
| 4 | `website_scrape` | Overrides lower-priority sources. |
| 5 | `email_signature` | Overrides only inferred. |
| 6 (lowest) | `inferred` | Overridden by any source. |

Rules:

- **Manual always wins** — User-entered data is never auto-overridden.
- **Higher priority overrides lower** — A paid API result replaces a website scrape, but not vice versa.
- **Same priority** — Keep existing value; flag for review.
- **Below confidence threshold** — Stored but not applied regardless of priority.
- **Users can always override** via the UI.

### 8.9 Website Scraping — Name Extraction

When a company domain is first encountered and the company is auto-created with a placeholder name (name = domain), the website scraper attempts to discover the real company name.

**Name extraction sources (in order of confidence):**

| Source | Confidence | Example |
|---|---|---|
| JSON-LD `Organization.name` | 0.9 | `<script type="application/ld+json">{"@type":"Organization","name":"Acme Corp"}` |
| `og:site_name` meta tag | 0.8 | `<meta property="og:site_name" content="Acme Corp">` |

**Overwrite guard:** The enrichment pipeline only overwrites the company name when the current name equals the `domain` column (i.e., it's still a placeholder). Manually-entered or previously-enriched names are preserved. This guard ensures the enrichment pipeline doesn't overwrite a user's intentional name with a scraped value.

**Additional scraping targets:**

- **About Us / About page** — Company description, founding date, mission statement.
- **Contact Us / Contact page** — Addresses, phone numbers, email addresses.
- **Social media links** — LinkedIn, Twitter/X, Facebook, Instagram, GitHub links in headers, footers, or contact pages.
- **Structured data** — schema.org markup (`Organization`, `LocalBusiness`) for machine-readable industry, founding date, logo, address, and social links.
- **Meta tags** — `<meta>` description, Open Graph tags for company description and logo.

The scraper respects `robots.txt` and implements polite crawling with rate limiting and appropriate user-agent identification.

### 8.10 Error Handling

- Failed providers do not block other providers in the same run.
- Failures are recorded in `enrichment_runs.error_message`.
- Transient failures (network timeouts, rate limits) are retried with exponential backoff.
- Persistent failures are logged and the run marked as `'failed'`.
- Failed runs are retried on the next enrichment cycle.

---

## 9. Company-Level Intelligence & Scoring

### 9.1 Overview

Company-level intelligence derives insights from existing communication data and enrichment. It surfaces relationship strength, engagement patterns, and key contacts without requiring users to manually analyze their email history.

### 9.2 Relationship Strength Scoring

A composite score per company computed from communication patterns. The same scoring model applies to contacts (see [Contact Management PRD](contact-management-prd_V5.md) Section 10.2) with company-specific adjustments for the **breadth** factor (number of distinct contacts at the company in active conversations).

**Factors (in priority order):**

| Factor | Description | Default Weight |
|---|---|---|
| Recency | How recently the last communication occurred. | 0.35 |
| Frequency | How often communications occur. | 0.25 |
| Reciprocity | Ratio of inbound to outbound; balanced is best. | 0.20 |
| Breadth | Number of distinct contacts at the company in active conversations. Company-specific factor. | 0.12 |
| Duration | How long the communication relationship has existed. | 0.08 |

**Formula:**

```
score = (w_recency * recency_score)
      + (w_frequency * frequency_score)
      + (w_reciprocity * reciprocity_score)
      + (w_breadth * breadth_score)
      + (w_duration * duration_score)
```

Each factor is normalized to a 0.0–1.0 range before weighting. Weights are automatically normalized to sum to 1.0.

**Directionality weighting:** Outbound (user-initiated) communications carry a 1.0x multiplier; inbound communications carry 0.6x. This reflects that initiating communication is a stronger signal of relationship investment than passively receiving it.

**Time decay:** Scores decay over time. A company emailed daily six months ago but not since scores lower than one emailed weekly in the current month.

**User-editable formula:** Users can adjust factor weights via system settings. The UI presents sliders for each factor weight.

### 9.3 Score Storage

Scores are precomputed and stored in the `entity_scores` table for fast sorting and display.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | TEXT | **PK** | Prefixed ULID. |
| `entity_type` | TEXT | NOT NULL | `'company'` or `'contact'`. |
| `entity_id` | TEXT | NOT NULL | ID of the entity. |
| `score_type` | TEXT | NOT NULL | `'relationship_strength'`, `'communication_trend'`, `'engagement_level'`. |
| `score_value` | REAL | NOT NULL, DEFAULT 0.0 | Numeric value, sortable. |
| `factors` | JSONB | | Breakdown of contributing factors for score transparency. |
| `computed_at` | TIMESTAMPTZ | NOT NULL | |
| `triggered_by` | TEXT | | `'event'`, `'scheduled'`, `'manual'`. |

**Constraints:**

- `UNIQUE (entity_type, entity_id, score_type)` — One score per type per entity. Enables UPSERT on recalculation.
- `CHECK (entity_type IN ('company', 'contact'))`.
- Index on `(score_type, score_value)` for sorted list queries.

### 9.4 Score Transparency

When a user clicks on a relationship strength score, the UI displays the factor breakdown from the `factors` JSON:

```
Relationship Strength: 0.73

  Recency:     0.85 × 0.35 = 0.298
  Frequency:   0.60 × 0.25 = 0.150
  Reciprocity: 0.70 × 0.20 = 0.140
  Breadth:     0.50 × 0.12 = 0.060
  Duration:    1.00 × 0.08 = 0.080

  Last contact: 3 days ago
  Communications (30d): 12 sent, 8 received
  Active contacts at company: 3
  Relationship since: 2024-06-15
```

### 9.5 Score Recalculation

| Trigger | Description |
|---|---|
| **Event-driven** | New communication sent/received involving a company contact → recompute that company's scores. |
| **Time-based** | Scheduled job runs daily to apply time decay across all entities. |
| **Bulk** | After a merge, import, or sync completes → recompute affected entities. |
| **Manual** | User requests recalculation from the UI. |

### 9.6 Derived Metrics

Beyond relationship strength, the following metrics are derivable from existing data:

| Metric | Source | Description |
|---|---|---|
| Communication volume | `communications` + `communication_participants` + employment records | Total communications over time per company. |
| Last contact | Same | Days/months/years since last communication. |
| Key contacts | Same | Top contacts at each company by communication volume and recency. |
| Topic distribution | `conversation_tags` + `conversation_participants` | What topics/tags are associated with conversations involving company contacts. |
| Meeting frequency | `events` + `event_participants` | How often meetings occur with company contacts. |
| Meeting-to-email ratio | `events` + `communications` | High-touch vs. low-touch relationship indicator. |

### 9.7 Relative Time Display

Communication recency is displayed as relative time:

- Less than 30 days: "**X days**"
- Less than 12 months: "**Y months**"
- 12 months or more: "**Z years**"

### 9.8 Views over Alerts

Intelligence is surfaced through **views** (saved smart filters) rather than interruptive alerts. Users pull information when they are ready, rather than being pushed notifications.

Example views:

- "Companies — declining engagement (30-day trend)"
- "Companies — highest relationship strength"
- "New companies — detected this week"
- "Companies — no communication in 90+ days"
- "Key contacts at risk — communication dropped significantly"

Views are stored using the existing views system ([Views & Grid PRD](views-grid-prd_V5.md)). Users can create custom views with their own filter and sort criteria tied to precomputed scores.

---

## 10. Social Media Profiles

### 10.1 Overview

Social media profiles are tracked in a dedicated table for companies. Contact social profiles are defined in the [Contact Management PRD](contact-management-prd_V5.md). The tables are separate because company profiles carry organizational metrics (follower count, posting frequency, verified status) while contact profiles carry professional data (job title, connections, endorsements).

### 10.2 Company Social Profiles Table

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | TEXT | **PK** | Prefixed ULID. |
| `company_id` | TEXT | NOT NULL, FK → `companies(id)` ON DELETE CASCADE | Owning company. |
| `platform` | TEXT | NOT NULL | `linkedin`, `twitter`, `facebook`, `github`, `instagram`. |
| `profile_url` | TEXT | NOT NULL | Full profile URL. |
| `username` | TEXT | | Platform-specific handle or vanity URL slug. |
| `verified` | BOOLEAN | DEFAULT false | Whether the profile is verified/official. |
| `follower_count` | INTEGER | | Last known follower count. |
| `bio` | TEXT | | Profile bio/description. |
| `last_scanned_at` | TIMESTAMPTZ | | Last successful scan timestamp. |
| `last_post_at` | TIMESTAMPTZ | | Timestamp of the most recent post. |
| `source` | TEXT | | Discovery source: `website_scrape`, `email_signature`, `manual`, `enrichment`. |
| `confidence` | REAL | | Source confidence (0.0–1.0). |
| `status` | TEXT | DEFAULT `'active'` | `active`, `archived`, `invalid`. |
| `created_at` | TIMESTAMPTZ | NOT NULL | |
| `updated_at` | TIMESTAMPTZ | NOT NULL | |

**Constraints:**

- `UNIQUE(company_id, platform, profile_url)`.
- Index on `(company_id)`.
- Index on `(platform)`.

### 10.3 Discovery

Social media profiles are discovered through explicit links found in data the system has access to:

| Source | Method |
|---|---|
| Website scraping | Social links in headers, footers, contact pages. |
| Email signature parsing | LinkedIn, Twitter, etc. links in signatures. |
| Manual entry | User adds profiles directly. |
| Enrichment APIs | Paid providers return social URLs. |

Social profiles are **not** auto-discovered from company domains or names. The risk of creating invalid connections to wrong profiles is too high. All discovered profiles must come from explicit links found in scraped or user-provided data.

### 10.4 Monitoring Tiers

Each company is assigned a monitoring tier that controls social media scanning frequency and extraction depth.

| Tier | Scan Cadence | Extraction Depth | Use Case |
|---|---|---|---|
| **High** | Weekly | Full profile, posts, changes | Key clients, strategic partners. |
| **Standard** | Monthly | Profile changes, bio | Active business contacts. |
| **Low** | Quarterly | Employment/leadership changes only | Peripheral companies. |
| **None** | Never | Nothing | Noise, opt-out. |

Configuration is stored in the `monitoring_preferences` table:

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | TEXT | **PK** | Prefixed ULID. |
| `entity_type` | TEXT | NOT NULL | `'company'` or `'contact'`. |
| `entity_id` | TEXT | NOT NULL | ID of the entity. |
| `monitoring_tier` | TEXT | NOT NULL, DEFAULT `'standard'` | `'high'`, `'standard'`, `'low'`, `'none'`. |
| `tier_source` | TEXT | NOT NULL, DEFAULT `'default'` | `'manual'`, `'auto_suggested'`, `'default'`. |
| `created_at` | TIMESTAMPTZ | NOT NULL | |
| `updated_at` | TIMESTAMPTZ | NOT NULL | |

**Constraints:**

- `CHECK (entity_type IN ('company', 'contact'))`.
- `CHECK (monitoring_tier IN ('high', 'standard', 'low', 'none'))`.
- `CHECK (tier_source IN ('manual', 'auto_suggested', 'default'))`.
- `UNIQUE(entity_type, entity_id)`.

### 10.5 Change Detection

Rather than presenting raw profile data, the system surfaces meaningful changes:

- Store previous scan results for comparison.
- Diff each scan against prior values.
- Surface deltas: "Acme Corp updated their LinkedIn bio to mention AI products", "New CEO listed on Acme Corp's LinkedIn page".
- Leadership and position changes are high-priority signals.
- Changes appear in an activity stream on the company detail page.

---

## 11. Asset Storage

### 11.1 Content-Addressable Storage

All graphical assets (logos, banners) are stored as files on the filesystem using content-addressable storage. The file's SHA-256 hash determines its storage path, providing automatic deduplication (the same image scraped twice is stored once).

### 11.2 Directory Structure

The hash is split into two levels of directory sharding to avoid filesystem issues with large numbers of files in a single directory:

```
data/assets/{hash[0:2]}/{hash[2:4]}/{full_hash}.{extension}
```

Example: a PNG logo with hash `ab3def7890...` is stored at:

```
data/assets/ab/3d/ab3def7890abcdef1234567890abcdef1234567890abcdef1234567890abcdef.png
```

### 11.3 Entity Assets Table

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | TEXT | **PK** | Prefixed ULID. |
| `entity_type` | TEXT | NOT NULL | `'company'` or `'contact'`. |
| `entity_id` | TEXT | NOT NULL | ID of the entity. |
| `asset_type` | TEXT | NOT NULL | `'logo'`, `'headshot'`, `'banner'`. |
| `hash` | TEXT | NOT NULL | SHA-256 hash of the file content. |
| `mime_type` | TEXT | NOT NULL | e.g., `image/png`, `image/jpeg`. |
| `file_ext` | TEXT | NOT NULL | e.g., `png`, `jpg`. |
| `source` | TEXT | | Discovery source. |
| `created_at` | TIMESTAMPTZ | NOT NULL | |

**Constraints:**

- `CHECK (entity_type IN ('company', 'contact'))`.
- `CHECK (asset_type IN ('logo', 'headshot', 'banner'))`.
- Index on `(entity_type, entity_id)`.
- Index on `(hash)` for deduplication lookups.

The filesystem path is derived from `hash` and `file_ext` — it is never stored directly. This ensures the path computation logic is centralized and the table remains the single source of truth for which assets exist.

---

## 12. Entity-Agnostic Shared Tables

These platform shared tables provide multi-value storage for any entity type. They complement the single-value fields on the entity type's read model table.

### 12.1 Addresses

Stores multiple addresses for companies and contacts.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | TEXT | **PK** | Prefixed ULID. |
| `entity_type` | TEXT | NOT NULL | `'company'` or `'contact'`. |
| `entity_id` | TEXT | NOT NULL | ID of the entity. |
| `address_type` | TEXT | NOT NULL, DEFAULT `'headquarters'` | `headquarters`, `branch`, `home`, `mailing`, `billing`. |
| `street` | TEXT | | |
| `city` | TEXT | | |
| `state` | TEXT | | |
| `postal_code` | TEXT | | |
| `country` | TEXT | | |
| `is_primary` | BOOLEAN | DEFAULT false | |
| `source` | TEXT | | Discovery source. |
| `confidence` | REAL | | Source confidence (0.0–1.0). |
| `created_at` | TIMESTAMPTZ | NOT NULL | |
| `updated_at` | TIMESTAMPTZ | NOT NULL | |

**Constraints:**

- `CHECK (entity_type IN ('company', 'contact'))`.
- Index on `(entity_type, entity_id)`.

The primary headquarters address is denormalized on `companies.location` for display. The authoritative data lives in this table.

### 12.2 Phone Numbers

Stores multiple phone numbers for companies and contacts.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | TEXT | **PK** | Prefixed ULID. |
| `entity_type` | TEXT | NOT NULL | `'company'` or `'contact'`. |
| `entity_id` | TEXT | NOT NULL | ID of the entity. |
| `phone_type` | TEXT | NOT NULL, DEFAULT `'main'` | `main`, `direct`, `mobile`, `support`, `sales`, `fax`. |
| `number` | TEXT | NOT NULL | Stored in E.164 format when possible. |
| `is_primary` | BOOLEAN | DEFAULT false | |
| `source` | TEXT | | Discovery source. |
| `confidence` | REAL | | Source confidence (0.0–1.0). |
| `created_at` | TIMESTAMPTZ | NOT NULL | |
| `updated_at` | TIMESTAMPTZ | NOT NULL | |

**Constraints:**

- `CHECK (entity_type IN ('company', 'contact'))`.
- Index on `(entity_type, entity_id)`.

### 12.3 Email Addresses

Stores typed, sourced email addresses for companies (general inquiry, support, sales, etc.).

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | TEXT | **PK** | Prefixed ULID. |
| `entity_type` | TEXT | NOT NULL | `'company'` or `'contact'`. |
| `entity_id` | TEXT | NOT NULL | ID of the entity. |
| `email_type` | TEXT | NOT NULL, DEFAULT `'general'` | `general`, `support`, `sales`, `billing`, `personal`, `work`. |
| `address` | TEXT | NOT NULL | The email address. |
| `is_primary` | BOOLEAN | DEFAULT false | |
| `source` | TEXT | | Discovery source. |
| `confidence` | REAL | | Source confidence (0.0–1.0). |
| `created_at` | TIMESTAMPTZ | NOT NULL | |
| `updated_at` | TIMESTAMPTZ | NOT NULL | |

**Constraints:**

- `CHECK (entity_type IN ('company', 'contact'))`.
- Index on `(entity_type, entity_id)`.

**Note:** For contacts, the `contact_identifiers` table continues to serve identity resolution (matching incoming emails to contact records). The `email_addresses` table provides the richer typed/sourced model for display and communication purposes. The two tables may contain overlapping data but serve different functions.

---

## 13. Company-to-Company Relationships (Neo4j)

Company hierarchy and business relationships are synced to Neo4j for graph queries.

**Node type:**

```cypher
(:Company {id, tenant_id, name, industry, domain, size_range, location})
```

**Hierarchy edges** (synced from `companies__companies_hierarchy` junction table):

```cypher
(:Company)-[:SUBSIDIARY_OF]->(:Company)
(:Company)-[:DIVISION_OF]->(:Company)
(:Company)-[:ACQUIRED_BY {date, amount}]->(:Company)
(:Company)-[:SPUN_OFF_FROM {date}]->(:Company)
```

**Business relationship edges** (synced from general Relation Types):

```cypher
(:Company)-[:PARTNER_OF {since, type}]->(:Company)
(:Company)-[:COMPETES_WITH]->(:Company)
(:Company)-[:VENDOR_OF {since}]->(:Company)
(:Company)-[:CLIENT_OF {since}]->(:Company)
```

**Cross-entity edges** (synced from Contact→Company employment):

```cypher
(:Contact)-[:WORKS_AT {role, department, since, until, is_current}]->(:Company)
```

These edges enable graph queries such as "what companies are connected to Acme Corp through shared contacts?", "show me the full corporate hierarchy for Alphabet", and "find the shortest relationship path between my company and a target account".

---

## 14. Event Sourcing & Temporal History

### 14.1 Event Store

Per Custom Objects PRD Section 19, the Company entity type has a dedicated event table: `companies_events`. Every mutation to a company record is stored as an immutable event, enabling full audit trails, point-in-time reconstruction, and compliance support.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | TEXT | **PK** | Event ID (prefixed ULID). |
| `entity_id` | TEXT | NOT NULL | The company this event applies to. |
| `event_type` | TEXT | NOT NULL | See event types below. |
| `field_name` | TEXT | | The field that changed (NULL for non-field events). |
| `old_value` | JSONB | | Previous value (NULL for creation). |
| `new_value` | JSONB | | New value (NULL for deletion). |
| `metadata` | JSONB | | Additional context (merge details, enrichment source, etc.). |
| `actor_id` | TEXT | | User or system process that caused this event. |
| `actor_type` | TEXT | | `'user'`, `'system'`, `'enrichment'`, `'sync'`. |
| `created_at` | TIMESTAMPTZ | NOT NULL | Event timestamp. |

**Event types:**

| Event Type | Description |
|---|---|
| `CompanyCreated` | New company record created. |
| `FieldUpdated` | A field value changed. |
| `CompanyMerged` | This company absorbed another company (metadata includes absorbed company snapshot). |
| `CompanyAbsorbed` | This company was absorbed into another (metadata includes surviving company ID). |
| `CompanyArchived` | Company record archived. |
| `CompanyUnarchived` | Company record restored from archive. |
| `EnrichmentApplied` | Enrichment data applied to company (metadata includes provider, confidence). |
| `HierarchyLinked` | Company added to a hierarchy relationship. |
| `HierarchyUnlinked` | Company removed from a hierarchy relationship. |
| `DomainAdded` | A domain was added to `company_identifiers`. |
| `DomainRemoved` | A domain was removed from `company_identifiers`. |

**Indexes:**

- Index on `(entity_id, created_at)` for per-company event timeline.
- Index on `(event_type)` for event-type queries.

### 14.2 Point-in-Time Reconstruction

The event stream enables reconstructing any company record's state at any historical timestamp by replaying events from creation up to the target timestamp. For performance, periodic snapshots are stored (per Custom Objects PRD Section 19) to avoid replaying the full event stream for records with long histories.

---

## 15. API Design

### 15.1 Company Record API

Company records use the uniform record CRUD pattern defined in Custom Objects PRD Section 23.4:

| Endpoint | Method | Description |
|---|---|---|
| `/api/v1/companies` | GET | List companies (paginated, filterable, sortable). |
| `/api/v1/companies` | POST | Create a company. |
| `/api/v1/companies/{id}` | GET | Get a single company with enrichment status and scores. |
| `/api/v1/companies/{id}` | PATCH | Update company fields. |
| `/api/v1/companies/{id}/archive` | POST | Archive a company. |
| `/api/v1/companies/{id}/unarchive` | POST | Unarchive a company. |
| `/api/v1/companies/{id}/history` | GET | Get event history for a company. |
| `/api/v1/companies/{id}/history?at={timestamp}` | GET | Get company state at a point in time. |

### 15.2 Merge API

| Endpoint | Method | Description |
|---|---|---|
| `/api/v1/companies/merge` | GET | Merge preview (query params: `ids=X&ids=Y`). Returns side-by-side comparison. |
| `/api/v1/companies/merge/confirm` | POST | Execute merge. Body: `{surviving_id, absorbed_ids, field_resolutions}`. |

### 15.3 Hierarchy API

Uses the uniform relation instance API from Custom Objects PRD Section 23.5:

| Endpoint | Method | Description |
|---|---|---|
| `/api/v1/companies/{id}/relations/company_hierarchy` | GET | List hierarchy relationships for a company. |
| `/api/v1/companies/{id}/relations/company_hierarchy` | POST | Add a hierarchy relationship (body: `{target_id, hierarchy_type, effective_date}`). |
| `/api/v1/companies/{id}/relations/company_hierarchy/{target_id}` | PATCH | Update hierarchy metadata. |
| `/api/v1/companies/{id}/relations/company_hierarchy/{target_id}` | DELETE | Remove a hierarchy relationship. |

### 15.4 Enrichment API

| Endpoint | Method | Description |
|---|---|---|
| `/api/v1/companies/{id}/enrich` | POST | Trigger on-demand enrichment for a company. |
| `/api/v1/companies/{id}/enrichment-runs` | GET | List enrichment runs for a company. |
| `/api/v1/companies/{id}/enrichment-runs/{run_id}` | GET | Get enrichment run details with field values. |

### 15.5 Domain / Identifier API

| Endpoint | Method | Description |
|---|---|---|
| `/api/v1/companies/{id}/identifiers` | GET | List all identifiers for a company. |
| `/api/v1/companies/{id}/identifiers` | POST | Add a new identifier (domain). |
| `/api/v1/companies/{id}/identifiers/{identifier_id}` | DELETE | Remove an identifier. |
| `/api/v1/companies/{id}/identifiers/{identifier_id}/set-primary` | POST | Set this identifier as the primary for its type. |

### 15.6 Social Profiles API

| Endpoint | Method | Description |
|---|---|---|
| `/api/v1/companies/{id}/social-profiles` | GET | List social profiles for a company. |
| `/api/v1/companies/{id}/social-profiles` | POST | Add a social profile. |
| `/api/v1/companies/{id}/social-profiles/{profile_id}` | PATCH | Update a social profile. |
| `/api/v1/companies/{id}/social-profiles/{profile_id}` | DELETE | Remove a social profile. |

---

## 16. Current State (PoC Implementation)

### 16.1 What Is Implemented

The PoC (SQLite-based, single-tenant) implements the following company management features:

**Domain-based company resolution** — The `_resolve_company_id()` function in `poc/sync.py` implements the core domain resolution flow: extract domain from email → skip public domains → look up existing company by domain → auto-create if not found. The function is called during Google Contacts sync.

**Company auto-creation** — When a non-public email domain has no matching company, a new company is created with `name = domain` and `domain = domain` (e.g., name "dbllaw.com", domain "dbllaw.com"). The `user_companies` visibility row is created if `user_id` is provided.

**Batch website enrichment** — `enrich_new_companies()` finds all companies with a domain but no completed enrichment run, scrapes their websites, and discovers real names from JSON-LD `Organization.name` (confidence 0.9) and `og:site_name` (confidence 0.8). The overwrite guard ensures only placeholder names (where `name == domain`) are replaced.

**Domain lookup** — `resolve_company_by_domain()` checks both the `companies.domain` column and `company_identifiers` join where `type='domain'`.

### 16.2 What Is Not Yet Implemented

- PostgreSQL migration (still SQLite)
- Prefixed ULIDs (still UUID v4)
- Event sourcing (`companies_events` table)
- Company merge UI and execution flow
- Company hierarchy
- Tier 2 and Tier 3 enrichment providers
- Relationship strength scoring
- Social media profile tracking
- Entity-agnostic shared tables (addresses, phone numbers, email addresses)
- Asset storage
- Neo4j graph sync

### 16.3 PoC Entry Points

| Entry Point | Location |
|---|---|
| Contact sync | `poc/sync.py` → `sync_contacts()` → `_resolve_company_id()` |
| Web UI sync | Dashboard "Sync Now" → `poc/web/routes/dashboard.py` |
| CLI batch enrichment | `python -m poc enrich-new-companies` |
| CLI single enrichment | `python -m poc enrich-company COMPANY_ID` |

### 16.4 PoC Tests

- `tests/test_company_merge.py::TestSyncDuplicateDetection` — 9 tests covering domain matching, auto-creation, public domains, dedup, visibility.
- `tests/test_enrichment.py::TestNameExtraction` — 4 tests for name extraction and overwrite guard.
- `tests/test_enrichment.py::TestEnrichNewCompanies` — 3 tests for batch enrichment (find, skip completed, retry failed).
- `tests/test_scoping.py::TestSyncScoping` — Verifies customer_id scoping.

### 16.5 The Bug This Fixed

**Before (name-based resolution):** Contact "Alan J Hartman" with email `ahartman@dbllaw.com` had Google org "Ulmer & Berne LLP". The old `_resolve_company_id()` matched "Ulmer & Berne LLP" by name and returned that company — even though Ulmer's domain is `ulmer.com`, not `dbllaw.com`. The contact was affiliated with the wrong company.

**After (domain-only resolution):** The function ignores the Google org name entirely. It extracts domain "dbllaw.com", finds no matching company, and auto-creates one named "dbllaw.com". Batch enrichment later scrapes dbllaw.com to discover the real company name.

---

## 17. Phasing & Roadmap

### Phase 1 — Domain Resolution & Enrichment (Current PoC → Production)

**Goal:** Migrate the working PoC domain resolution to PostgreSQL with the unified object model, and expand enrichment.

**Scope:**

- Company as system object type with `cmp_` prefixed ULIDs.
- `companies` read model table with all core fields per Section 4.
- `companies_events` event table.
- `company_identifiers` table with domain resolution.
- Domain resolution during contact sync (port from PoC).
- Tier 1 enrichment: website scraper with name extraction, description, social links.
- `enrichment_runs` and `enrichment_field_values` tables.
- Enrichment conflict resolution (priority hierarchy).
- Company detail page in UI.
- Company list view with basic filtering and sorting.

### Phase 2 — Merging & Hierarchy

**Goal:** Detect and resolve duplicate companies; model corporate structure.

**Scope:**

- Duplicate detection on company create/edit (domain-based).
- Merge preview and execution flow.
- `company_merges` audit table.
- Company hierarchy Relation Type.
- `companies__companies_hierarchy` junction table.
- Hierarchy UI on company detail page (flat sections: Parent Companies, Subsidiaries).
- Merge-vs-hierarchy fork in the UI.

### Phase 3 — Intelligence & Scoring

**Goal:** Surface relationship intelligence from communication data.

**Scope:**

- Relationship strength scoring (5-factor model).
- `entity_scores` table.
- Score recalculation (event-driven + daily decay + bulk).
- Score transparency UI (factor breakdown).
- User-editable scoring weights.
- Derived metrics (communication volume, last contact, key contacts).
- Intelligence views (declining engagement, highest strength, no communication).

### Phase 4 — Social Profiles & Advanced Enrichment

**Goal:** Track company social presence and expand enrichment sources.

**Scope:**

- `company_social_profiles` table.
- `monitoring_preferences` table.
- Social profile discovery (website scraping, email signatures).
- Change detection and activity stream.
- Tier 2 enrichment: Wikidata, OpenCorporates, SEC EDGAR.
- Entity-agnostic shared tables (addresses, phone numbers, email addresses).
- Asset storage (logos).
- Neo4j graph sync for companies and hierarchy.

### Phase 5 — Paid APIs & Advanced Features

**Goal:** Integrate paid enrichment providers and advanced intelligence.

**Scope:**

- Tier 3 enrichment: Clearbit, Apollo, Crunchbase.
- Paid API cost controls and approval workflows.
- Retroactive domain resolution (batch processing existing communications).
- Email signature parser for company intelligence.
- Trend calculations (period-over-period).
- Tree/org-chart visualization for hierarchy.
- Automatic monitoring tier adjustment based on relationship strength.

---

## 18. Design Decisions

### Why root domain as the duplicate key instead of fuzzy name matching?

Fuzzy name matching produces unacceptable false positive rates. "Acme" matches "Acme Corp", "Acme Corporation", and "Acme Industries" — which may be completely different companies. Domain-based matching is deterministic: `acme.com` either matches or it doesn't. Companies can be created without a domain, but domain-based deduplication only activates when a domain is present.

### Why ignore the Google Contacts organization name?

The Google Contacts org name field is hand-entered, often stale, and sometimes wrong. Two contacts at the same company may have "Acme Corp", "Acme Inc", and "ACME" as their org names. Using these for resolution would create three separate company records. Domain matching prevents all three from creating duplicates. The PoC bug (Section 16.5) demonstrated this problem directly.

### Why auto-create companies named after their domain?

Auto-created companies get a functional but recognizable placeholder name ("dbllaw.com") that serves two purposes: it's immediately useful for grouping contacts, and it's a clear signal that enrichment hasn't run yet. The enrichment guard (`name == domain`) precisely targets these placeholders without risking real names.

### Why a Relation Type for hierarchy instead of a separate bespoke table?

The Custom Objects PRD's Relation Type framework supports all the requirements: self-referential relations, many-to-many cardinality, temporal metadata (effective_date, end_date), type-specific metadata (hierarchy_type, acquisition amounts), and Neo4j sync. Using the framework ensures hierarchy relationships participate in the same view system, query engine, and audit trail as all other relationships. The junction table pattern handles arbitrary nesting and multiple parents naturally.

### Why entity-agnostic enrichment instead of separate company/contact pipelines?

The enrichment process is identical for both entity types: trigger → select providers → execute → store results → apply conflict resolution. Duplicating this pipeline would double the code and maintenance burden with no architectural benefit. The providers themselves differ, but the pipeline is shared.

### Why separate social media tables for companies and contacts?

Company social profiles carry organizational metrics (follower count, posting frequency, verified page status) while contact profiles carry professional data (job title, headline, connection degree, mutual connections). These columns diverge significantly and will continue to diverge as enrichment matures. A shared polymorphic table would require nullable columns everywhere and `entity_type` conditionals in every query.

### Why content-addressable asset storage instead of BLOBs in PostgreSQL?

Storing logos and images as BLOBs would inflate database size, slow backups, and degrade query performance. Content-addressable filesystem storage with hash-based deduplication keeps the database lean while automatically deduplicating identical assets. Two-level directory sharding (first two characters, then characters three and four of the hash) distributes files across up to 65,536 directories, preventing any single directory from becoming a bottleneck.

### Why precomputed scores instead of on-demand calculation?

With hundreds of companies and thousands of communications, computing relationship strength at query time for a sorted list would be prohibitively slow. Precomputed scores enable instant `ORDER BY` sorting on any list view. The hybrid recalculation model (event-driven + time-based decay) keeps scores fresh without requiring full recomputation on every page load.

### Why views over alerts?

Alerts interrupt the user's current focus and create notification fatigue. Views let users pull intelligence when they are ready — opening a "declining engagement" view is an intentional action, not an interruption. The same underlying data powers both approaches, so alerts can be added later if demand emerges.

### Why denormalize primary domain and headquarters location?

Both values are displayed on nearly every company list and detail view. Joining to `company_identifiers` or `addresses` on every list query adds unnecessary complexity. The denormalized values are kept in sync by the enrichment pipeline and merge operations. The authoritative data lives in the normalized tables; the denormalized columns are display optimizations.

---

## 19. Dependencies & Related PRDs

| PRD | Relationship | Dependency Direction |
|---|---|---|
| **[Custom Objects PRD](custom-objects-prd_v2.md)** | Company is a system object type. Table structure, field registry, event sourcing, and relation model are governed by Custom Objects. This PRD defines Company-specific behaviors. | **Bidirectional.** Custom Objects provides the entity framework; this PRD defines behaviors. |
| **[Contact Management PRD](contact-management-prd_V5.md)** | Contact→Company employment Relation Type is defined in the Contact PRD. Company data model (Contact PRD Section 6) is a cross-reference to this document. | **Bidirectional.** Contact PRD defines employment; this PRD defines the Company entity. |
| **[Communication & Conversation Intelligence PRD](email-conversations-prd.md)** | Communications are linked to companies through contact participants. Email domain extraction triggers company auto-creation. | **Company depends on Communication** for scoring data. **Communication depends on Company** for domain resolution. |
| **[Data Sources PRD](data-sources-prd_V1.md)** | Company virtual schema table is derived from the Company field registry. `cmp_` prefix enables entity detection. | **Data Sources depend on Company** for entity definitions. |
| **[Views & Grid PRD](views-grid-prd_V5.md)** | Company views, filters, sorts use fields from the Company field registry. Precomputed scores enable sort-by-strength. | **Views depend on Company** for field definitions and scores. |
| **[Permissions & Sharing PRD](permissions-sharing-prd_V2.md)** | Company record access, merge permissions, hierarchy management permissions. | **Company depends on Permissions** for access control. |
| **[Events PRD](events-prd.md)** | Company participates in calendar events via `event_participants`. | **Events depend on Company** as a participant entity type. |

---

## 20. Open Questions

1. **Domain validation depth** — When auto-creating companies from email domains, should the system only check for a working website (HTTP 200), or also validate the domain has meaningful content (not a parked domain or redirect-only page)? The current PoC does not validate at all.

2. **Multi-domain company merging** — When two companies with different domains are merged, both domains are kept. But what if a contact's email domain matches the absorbed company — should the employment record's `company_name` metadata field be updated to the surviving company's name, or preserved as historical?

3. **Hierarchy cycle prevention** — The `CHECK (source_id != target_id)` prevents self-referencing, but does not prevent cycles (A → B → C → A). Should cycle detection be enforced at the application level? If so, what is the performance implication for deeply nested hierarchies?

4. **Enrichment rate limiting across providers** — When multiple Tier 2 providers are called for the same company, should they execute in parallel or sequentially? Parallel is faster but may trigger rate limits on the system's outbound IP.

5. **Score staleness threshold** — How stale can a score be before it's considered unreliable? Should the UI display a "score last updated X hours ago" indicator? Should stale scores be visually distinguished?

6. **Company record limit per tenant** — Should there be a limit on the number of company records per tenant? The auto-discovery mechanism could potentially create thousands of companies from a large email archive.

7. **Subsidiary communication aggregation** — Section 7.7 states subsidiaries are treated as separate entities. Should there be an optional "roll up communications" view that aggregates across a hierarchy for reporting purposes?

---

## 21. Future Work

### 21.1 Field Conflict Resolution UI

Full per-field conflict resolution during company merges, allowing users to pick the correct value from each source or keep both for multi-value fields like addresses.

### 21.2 Trend Calculations

Period-over-period analysis for communication patterns — "engagement with Acme Corp increased 40% month over month." Requires defining baseline calculation methodology and deviation thresholds.

### 21.3 Paid API Cost Controls

Budget limits, per-company lookup caps, and approval workflows before spending on Tier 3 paid enrichment providers.

### 21.4 Tree / Org-Chart Visualization

Visual tree or org-chart rendering of company hierarchies on the company detail page, beyond the current flat "Parent Companies" / "Subsidiaries" list sections.

### 21.5 Automatic Tier Adjustment

Automatically adjust monitoring tiers based on relationship strength score changes, with user confirmation before upgrading or downgrading.

### 21.6 LinkedIn-Specific Integration

Dedicated LinkedIn integration for professional profile monitoring, pending ToS compliance analysis and potential API partnership.

### 21.7 Email Signature Parser

Automated extraction of company intelligence (addresses, phone numbers, titles, social links) from email signatures across existing and incoming communications.

### 21.8 Retroactive Domain Resolution

Batch processing of all existing communications to extract domains and auto-create/link companies retroactively, with a progress UI showing discovery counts and linking results.

---

## 22. Glossary

General platform terms (Entity Bar, Detail Panel, Card-Based Architecture, Attribute Card, etc.) are defined in the **[Master Glossary V3](glossary_V3.md)**. The following terms are specific to this subsystem:

| Term | Definition |
|---|---|
| **Company** | A system object type representing an organization. Identified by domain, enriched from multiple sources, scored for relationship strength. |
| **Domain Resolution** | The process of extracting an email domain and mapping it to a company record, creating one if necessary. |
| **Public Domain** | A free email provider domain (gmail.com, yahoo.com, etc.) that is excluded from company resolution. |
| **Root Domain** | The primary domain after stripping subdomains and prefixes: `mail.acme.com` → `acme.com`. |
| **Placeholder Name** | When a company is auto-created from a domain, it is initially named after the domain (e.g., "acme.com"). Enrichment later discovers the real name. |
| **Overwrite Guard** | The enrichment rule that only replaces a company name when the current name equals the domain (i.e., it's still a placeholder). |
| **Enrichment Run** | A single execution of an enrichment provider against a company or contact. Tracked in `enrichment_runs`. |
| **Field Provenance** | The source, confidence, and timestamp metadata attached to each enriched field value. |
| **Conflict Resolution** | The priority hierarchy that determines which enrichment value wins when multiple sources provide values for the same field. |
| **Relationship Strength** | A composite score (0.0–1.0) computed from communication patterns between the user and a company's contacts. |
| **Time Decay** | The progressive reduction of a relationship strength score when communication ceases. |
| **Monitoring Tier** | The frequency at which a company's social media profiles are scanned for changes: `high`, `standard`, `low`, `none`. |
| **Company Hierarchy** | The parent/subsidiary organizational structure modeled as a self-referential Relation Type with temporal metadata. |
| **Merge** | The process of combining two duplicate company records into one, reassigning all associated entities to the surviving record. |
| **Surviving Company** | The company record that persists after a merge. The absorbed company is soft-deleted. |
| **Content-Addressable Storage** | A file storage scheme where the file's SHA-256 hash determines its filesystem path, enabling automatic deduplication. |

---

## Related PRDs

| Document | Relationship |
|---|---|
| [CRMExtender PRD v1.1](PRD.md) | Parent document defining system architecture, phasing, and all feature areas. |
| [Custom Objects PRD](custom-objects-prd_v2.md) | Company is a system object type managed by this framework. |
| [Contact Management PRD](contact-management-prd_V5.md) | Contact→Company employment relation; Company section cross-references this document. |
| [Communication & Conversation Intelligence PRD](email-conversations-prd.md) | Communications provide the data for company relationship scoring. |
| [Data Sources PRD](data-sources-prd_V1.md) | Company virtual schema for query engine. |
| [Views & Grid PRD](views-grid-prd_V5.md) | Company views consume field registry and precomputed scores. |
| [Permissions & Sharing PRD](permissions-sharing-prd_V2.md) | Access control for company records. |
| [Events PRD](events-prd.md) | Companies participate in calendar events. |
| [Email Parsing & Content Extraction](email_stripping_V1.md) | Email signature parsing provides company enrichment data. |

---

*This document is a living specification. It consolidates the Company Detection specification (domain resolution implementation) and the Company Intelligence PRD (enrichment, hierarchy, scoring) into a single authoritative document, fully reconciled with the Custom Objects PRD Unified Object Model. As implementation progresses, sections will be updated to reflect design decisions, scope adjustments, and lessons learned.*
