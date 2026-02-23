# Company Entity — TDD

**Version:** 1.0
**Last Updated:** 2026-02-23
**Status:** Draft
**Scope:** Entity
**Parent Document:** [company-entity-base-prd.md]
**Product TDD:** [product-tdd.md]

---

## 1. Overview

The Company entity requires entity-specific technical decisions beyond the Product TDD's global defaults. Key areas include: the read model table DDL, the company identifiers model, entity-agnostic shared tables (addresses, phone numbers, email addresses), asset storage, event sourcing, Neo4j graph sync, and score storage.

This is a living document. Decisions are recorded here as they are made — both by the product/architecture owner and by Claude Code during implementation. When Claude Code makes an implementation decision not covered here, it should add the decision with rationale to the appropriate section.

---

## 2. Companies Read Model Table

### 2.1 Table Definition

**Decision:** The `companies` table is the dedicated read model for the Company system object type, managed through the Custom Objects framework. Core fields are `is_system = true` and cannot be archived or deleted.

**Column Definitions:**

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | TEXT | **PK** | Prefixed ULID: `cmp_` prefix. |
| `tenant_id` | TEXT | NOT NULL | Tenant identifier. Denormalized from schema context for cross-schema queries. |
| `name` | TEXT | NOT NULL | Company display name. |
| `domain` | TEXT | UNIQUE | Primary domain, denormalized from `company_identifiers` where `is_primary = true`. |
| `industry` | TEXT | | Industry classification. |
| `size_range` | TEXT | | Employee count range. |
| `employee_count` | INTEGER | | Raw employee count when known. |
| `location` | TEXT | | Headquarters location, denormalized from primary address. |
| `description` | TEXT | | Brief description. |
| `logo_url` | TEXT | | Logo URL or asset storage path. |
| `website` | TEXT | | Company website URL. |
| `linkedin_url` | TEXT | | LinkedIn page URL. |
| `stock_symbol` | TEXT | | Ticker symbol. |
| `founded_year` | INTEGER | | Year founded. |
| `revenue_range` | TEXT | | Annual revenue range. |
| `funding_total` | TEXT | | Total funding raised. |
| `funding_stage` | TEXT | | Latest funding stage. |
| `status` | TEXT | NOT NULL, DEFAULT `'active'` | `active`, `merged`, `archived`. |
| `created_at` | TIMESTAMPTZ | NOT NULL | |
| `updated_at` | TIMESTAMPTZ | NOT NULL | |
| `created_by` | TEXT | | User or system process. |
| `updated_by` | TEXT | | User or system process. |
| `archived_at` | TIMESTAMPTZ | | NULL if active. |

**Rationale:** Flat read model with denormalized fields (domain, location) for display performance. Authoritative data for multi-value fields lives in normalized tables (company_identifiers, addresses).

**Constraints:**

- `CHECK (status IN ('active', 'merged', 'archived'))`
- `CHECK (funding_stage IN ('pre_seed', 'seed', 'series_a', 'series_b', 'series_c', 'series_d_plus', 'ipo', 'private', 'bootstrapped'))` when not NULL

---

## 3. Company Identifiers Model

### 3.1 Table Definition

**Decision:** Multi-domain identifier model mirroring `contact_identifiers` pattern. Currently `domain` only; schema extensible to `duns`, `ein`, `lei`.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | TEXT | **PK** | Prefixed ULID. |
| `company_id` | TEXT | NOT NULL, FK → `companies(id)` ON DELETE CASCADE | Owning company. |
| `type` | TEXT | NOT NULL, DEFAULT `'domain'` | Identifier type. |
| `value` | TEXT | NOT NULL | The identifier value. |
| `is_primary` | BOOLEAN | DEFAULT false | At most one primary per type per company. |
| `source` | TEXT | | Discovery source. |
| `created_at` | TIMESTAMPTZ | NOT NULL | |
| `updated_at` | TIMESTAMPTZ | NOT NULL | |

**Constraints:**

- `UNIQUE(type, value)` — A domain can belong to at most one company.
- Index on `(company_id)` for listing a company's identifiers.
- Index on `(type, value)` for fast resolution lookups.

**Rationale:** The unique constraint on `(type, value)` enforces the business rule that each domain belongs to exactly one company, which is the foundation of domain-based duplicate detection.

---

## 4. Entity-Agnostic Shared Tables

### 4.1 Addresses

**Decision:** Entity-agnostic `addresses` table for companies and contacts with typed, sourced, multi-value storage.

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
| `confidence` | REAL | | 0.0–1.0. |
| `created_at` | TIMESTAMPTZ | NOT NULL | |
| `updated_at` | TIMESTAMPTZ | NOT NULL | |

**Constraints:** `CHECK (entity_type IN ('company', 'contact'))`. Index on `(entity_type, entity_id)`.

**Rationale:** Entity-agnostic design avoids separate address tables per entity type. The primary headquarters address is denormalized on `companies.location` for display performance.

### 4.2 Phone Numbers

**Decision:** Entity-agnostic `phone_numbers` table.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | TEXT | **PK** | Prefixed ULID. |
| `entity_type` | TEXT | NOT NULL | `'company'` or `'contact'`. |
| `entity_id` | TEXT | NOT NULL | ID of the entity. |
| `phone_type` | TEXT | NOT NULL, DEFAULT `'main'` | `main`, `direct`, `mobile`, `support`, `sales`, `fax`. |
| `number` | TEXT | NOT NULL | E.164 format when possible. |
| `is_primary` | BOOLEAN | DEFAULT false | |
| `source` | TEXT | | |
| `confidence` | REAL | | |
| `created_at` | TIMESTAMPTZ | NOT NULL | |
| `updated_at` | TIMESTAMPTZ | NOT NULL | |

**Constraints:** `CHECK (entity_type IN ('company', 'contact'))`. Index on `(entity_type, entity_id)`.

### 4.3 Email Addresses

**Decision:** Entity-agnostic `email_addresses` table for organizational contact points. Distinct from `contact_identifiers` (which serves identity resolution).

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | TEXT | **PK** | Prefixed ULID. |
| `entity_type` | TEXT | NOT NULL | `'company'` or `'contact'`. |
| `entity_id` | TEXT | NOT NULL | ID of the entity. |
| `email_type` | TEXT | NOT NULL, DEFAULT `'general'` | `general`, `support`, `sales`, `billing`, `personal`, `work`. |
| `address` | TEXT | NOT NULL | The email address. |
| `is_primary` | BOOLEAN | DEFAULT false | |
| `source` | TEXT | | |
| `confidence` | REAL | | |
| `created_at` | TIMESTAMPTZ | NOT NULL | |
| `updated_at` | TIMESTAMPTZ | NOT NULL | |

**Constraints:** `CHECK (entity_type IN ('company', 'contact'))`. Index on `(entity_type, entity_id)`.

**Rationale:** For contacts, `contact_identifiers` handles identity resolution (matching incoming emails to contacts). `email_addresses` provides the richer typed/sourced model for display and communication purposes. The two tables may contain overlapping data but serve different functions.

---

## 5. Asset Storage

### 5.1 Content-Addressable Storage

**Decision:** All graphical assets (logos, banners, headshots) are stored as files on the filesystem using content-addressable storage. The file's SHA-256 hash determines its storage path.

**Directory structure:**
```
data/assets/{hash[0:2]}/{hash[2:4]}/{full_hash}.{extension}
```

**Rationale:** SHA-256 hashing provides automatic deduplication (same image scraped twice is stored once). Two-level directory sharding avoids filesystem issues with large numbers of files in a single directory.

### 5.2 Entity Assets Table

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | TEXT | **PK** | Prefixed ULID. |
| `entity_type` | TEXT | NOT NULL | `'company'` or `'contact'`. |
| `entity_id` | TEXT | NOT NULL | |
| `asset_type` | TEXT | NOT NULL | `'logo'`, `'headshot'`, `'banner'`. |
| `hash` | TEXT | NOT NULL | SHA-256 hash. |
| `mime_type` | TEXT | NOT NULL | e.g., `image/png`. |
| `file_ext` | TEXT | NOT NULL | e.g., `png`. |
| `source` | TEXT | | Discovery source. |
| `created_at` | TIMESTAMPTZ | NOT NULL | |

**Constraints:** Index on `(entity_type, entity_id)`. Index on `(hash)` for deduplication. The filesystem path is derived from `hash` and `file_ext` — never stored directly.

**Alternatives Rejected:**
- BLOBs in PostgreSQL — Increases database size, complicates backups, and limits CDN options.

---

## 6. Event Sourcing

### 6.1 Companies Events Table

**Decision:** Per Custom Objects PRD, the Company entity type has a dedicated event table: `companies_events`. Every mutation is stored as an immutable event.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | TEXT | **PK** | Event ID (prefixed ULID). |
| `entity_id` | TEXT | NOT NULL | Company ID. |
| `event_type` | TEXT | NOT NULL | See event types below. |
| `field_name` | TEXT | | Field that changed (NULL for non-field events). |
| `old_value` | JSONB | | Previous value. |
| `new_value` | JSONB | | New value. |
| `metadata` | JSONB | | Additional context. |
| `actor_id` | TEXT | | User or system process. |
| `actor_type` | TEXT | | `'user'`, `'system'`, `'enrichment'`, `'sync'`. |
| `created_at` | TIMESTAMPTZ | NOT NULL | Event timestamp. |

**Event Types:**

| Event Type | Description |
|---|---|
| `CompanyCreated` | New company record created. |
| `FieldUpdated` | A field value changed. |
| `CompanyMerged` | This company absorbed another (metadata: absorbed snapshot). |
| `CompanyAbsorbed` | This company was absorbed (metadata: surviving ID). |
| `CompanyArchived` | Company archived. |
| `CompanyUnarchived` | Company restored. |
| `EnrichmentApplied` | Enrichment data applied (metadata: provider, confidence). |
| `HierarchyLinked` | Hierarchy relationship added. |
| `HierarchyUnlinked` | Hierarchy relationship removed. |
| `DomainAdded` | Domain added to identifiers. |
| `DomainRemoved` | Domain removed from identifiers. |

**Indexes:** `(entity_id, created_at)` for per-company timeline. `(event_type)` for type queries.

---

## 7. Neo4j Graph Sync

### 7.1 Company Node

**Decision:** Company records are synced to Neo4j as Company nodes for graph queries.

```cypher
(:Company {id, tenant_id, name, industry, domain, size_range, location})
```

### 7.2 Edge Types

Hierarchy edges (from `companies__companies_hierarchy`):

```cypher
(:Company)-[:SUBSIDIARY_OF]->(:Company)
(:Company)-[:DIVISION_OF]->(:Company)
(:Company)-[:ACQUIRED_BY {date, amount}]->(:Company)
(:Company)-[:SPUN_OFF_FROM {date}]->(:Company)
```

Business relationship edges (from general Relation Types):

```cypher
(:Company)-[:PARTNER_OF {since, type}]->(:Company)
(:Company)-[:COMPETES_WITH]->(:Company)
(:Company)-[:VENDOR_OF {since}]->(:Company)
(:Company)-[:CLIENT_OF {since}]->(:Company)
```

Cross-entity edges (from Contact→Company employment):

```cypher
(:Contact)-[:WORKS_AT {role, department, since, until, is_current}]->(:Company)
```

**Rationale:** Graph queries enable relationship traversal that SQL cannot efficiently express — e.g., "find the shortest relationship path between my company and a target account," "what companies are connected through shared contacts."

---

## 8. Score Storage

### 8.1 Entity Scores Table

**Decision:** Precomputed scores stored in the entity-agnostic `entity_scores` table for fast sorting and display.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | TEXT | **PK** | Prefixed ULID. |
| `entity_type` | TEXT | NOT NULL | `'company'` or `'contact'`. |
| `entity_id` | TEXT | NOT NULL | |
| `score_type` | TEXT | NOT NULL | `'relationship_strength'`, `'communication_trend'`, `'engagement_level'`. |
| `score_value` | REAL | NOT NULL, DEFAULT 0.0 | Numeric value, sortable. |
| `factors` | JSONB | | Factor breakdown for transparency. |
| `computed_at` | TIMESTAMPTZ | NOT NULL | |
| `triggered_by` | TEXT | | `'event'`, `'scheduled'`, `'manual'`. |

**Constraints:**

- `UNIQUE (entity_type, entity_id, score_type)` — One score per type per entity. Enables UPSERT.
- `CHECK (entity_type IN ('company', 'contact'))`.
- Index on `(score_type, score_value)` for sorted list queries.

**Rationale:** Precomputed scores avoid expensive traversals on every list query. The UPSERT-friendly unique constraint ensures clean score replacement on recalculation.

---

## 9. Decisions to Be Added by Claude Code

The following areas will require technical decisions during implementation that should be documented here by Claude Code:

- **Domain denormalization sync mechanism:** How the `companies.domain` column stays in sync with `company_identifiers`. Application-level trigger, database trigger, or scheduled reconciliation.
- **Location denormalization sync mechanism:** How `companies.location` stays in sync with the primary address in the `addresses` table.
- **Relationship strength caching:** How the precomputed relationship_strength score is denormalized onto the companies read model for sort performance (the † field in the Base PRD).
- **Index strategy for company list queries:** Which indexes are needed on `companies` for the most common filter/sort combinations.
- **Migration strategy from PoC:** How existing SQLite data (UUID v4 IDs, no event sourcing, no prefixed ULIDs) migrates to the target schema.
- **Point-in-time reconstruction performance:** Snapshot interval and storage strategy for bounding event replay depth.
- **Neo4j sync mechanism:** Whether sync is event-driven, change-data-capture, or scheduled batch. How to handle initial backfill.
