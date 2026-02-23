# Company — Enrichment Pipeline Sub-PRD

**Version:** 1.0
**Last Updated:** 2026-02-23
**Status:** Draft
**Entity Base PRD:** [company-entity-base-prd.md]
**Referenced Entity PRDs:** [contact-enrichment-prd.md] (shared enrichment architecture)

---

## 1. Overview

### 1.1 Purpose

The enrichment pipeline progressively improves company records with data from external sources. It transforms a bare record (often just a domain name) into a rich firmographic profile with description, industry, employee count, addresses, social links, and funding information. The pipeline uses a pluggable provider model with a three-tier source architecture: owned data (free, immediate), free public APIs (background batch), and paid APIs (future, cost-controlled).

The enrichment pipeline is entity-agnostic — the same architecture serves both companies and contacts. This sub-PRD defines the company-specific aspects of the shared pipeline.

### 1.2 Preconditions

- Company record exists with at least a domain.
- Enrichment provider registry is populated with at least one active provider.
- Enrichment run tracking tables exist.

---

## 2. Context

### 2.1 Relevant Fields

All company fields are potential enrichment targets. The most commonly enriched fields:

| Field | Enrichment Sources |
|---|---|
| Name | Website scraper (JSON-LD, og:site_name). Replaces domain placeholder only. |
| Description | Website scraper (about page, meta description). Wikidata. |
| Industry | Wikidata. Paid APIs. |
| Size Range / Employee Count | Wikidata. Paid APIs. |
| Location | Website scraper (contact page, structured data). |
| Founded Year | Wikidata. SEC EDGAR. |
| Revenue Range | SEC EDGAR. Paid APIs. |
| Funding Stage / Funding Total | Paid APIs (Crunchbase). |
| Logo URL | Website scraper (favicon, Open Graph image). |
| Social Links | Website scraper (header/footer links). Email signature parser. |

### 2.2 Relevant Relationships

- **Company Identifiers** — Domain is the primary input for enrichment providers.
- **Social Profiles** — Social links discovered during enrichment are registered in the social profiles table (see Social Profiles Sub-PRD).
- **Addresses** — Address data discovered during enrichment populates the entity-agnostic addresses table.

### 2.3 Relevant Lifecycle Transitions

- Enrichment does not change company lifecycle status. It modifies field values on `active` companies.

### 2.4 Cross-Entity Context

- **Contact Enrichment Sub-PRD:** The enrichment pipeline shares architecture (provider interface, run tracking, field value storage, conflict resolution) with contact enrichment. Company-specific aspects include the overwrite guard, domain-based provider selection, and firmographic-focused providers.

---

## 3. Key Processes

### KP-1: Automatic Enrichment on Company Creation

**Trigger:** A new company is auto-created via domain resolution.

**Step 1 — Queue Tier 1:** System queues website scraping for the company's domain as a background job.

**Step 2 — Website scrape execution:** Scraper fetches the company's homepage and key pages (About, Contact). Extracts structured data, meta tags, social links, contact information.

**Step 3 — Name extraction:** If the company name is still a placeholder (name == domain), the scraper attempts to discover the real name from JSON-LD Organization.name (confidence 0.9) or og:site_name (confidence 0.8). The overwrite guard ensures only placeholder names are replaced.

**Step 4 — Field application:** Enriched values above confidence thresholds are applied to the company record. Values below threshold are stored but not applied (queued for review).

**Step 5 — Queue Tier 2:** After Tier 1 completes, system queues Tier 2 providers (Wikidata, OpenCorporates, SEC EDGAR) as background batch jobs.

### KP-2: On-Demand Enrichment

**Trigger:** User clicks "Refresh" or "Enrich" on a company detail page.

**Step 1 — Run all applicable providers:** System runs Tier 1, Tier 2, and (if configured) Tier 3 providers for the company.

**Step 2 — Progress indicator:** UI shows enrichment in progress with per-provider status.

**Step 3 — Results display:** Updated fields are highlighted. New data points show source attribution.

### KP-3: Scheduled Re-Enrichment

**Trigger:** Scheduled job identifies companies whose enrichment data is older than the provider's refresh cadence.

**Step 1 — Identify stale companies:** Query enrichment_runs for companies that haven't been enriched within each provider's `refresh_cadence`.

**Step 2 — Queue batch:** Queue enrichment for each stale company, respecting rate limits and cost budgets.

**Step 3 — Background execution:** Providers run and update field values using the standard conflict resolution hierarchy.

### KP-4: Retroactive Batch Enrichment

**Trigger:** User initiates a scan to enrich all companies, or system runs email signature parsing across existing communications.

**Step 1 — Scope selection:** User can choose: all companies, companies missing specific fields, or companies created before a certain date.

**Step 2 — Batch execution:** System processes companies in batches, respecting rate limits. Progress bar shows completion percentage.

**Step 3 — Results summary:** Report shows how many companies were updated, which fields were enriched, and how many values were below confidence threshold.

---

## 4. Three-Tier Source Architecture

**Supports processes:** KP-1 (steps 1–5), KP-2 (step 1)

### 4.1 Requirements

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

**Tasks:**

- [ ] CENR-01: Implement website scraper provider (homepage, about page, contact page)
- [ ] CENR-02: Implement email signature parser provider
- [ ] CENR-03: Implement Wikidata provider
- [ ] CENR-04: Implement OpenCorporates provider
- [ ] CENR-05: Implement SEC EDGAR provider
- [ ] CENR-06: Design Tier 3 provider interface stubs (Clearbit, Apollo, Crunchbase)

**Tests:**

- [ ] CENR-T01: Test website scraper extracts name, description, social links, addresses
- [ ] CENR-T02: Test email signature parser extracts company data from signatures
- [ ] CENR-T03: Test Wikidata provider returns firmographic data for known companies
- [ ] CENR-T04: Test providers handle failures gracefully (timeout, rate limit, 404)

---

## 5. Provider Interface

**Supports processes:** All KPs

### 5.1 Requirements

Each enrichment provider implements a common interface:

```python
class EnrichmentProvider:
    name: str                    # e.g., "website_scraper", "wikidata"
    tier: int                    # 1, 2, or 3
    entity_types: list[str]      # ["company"], ["contact"], or both
    rate_limit: RateLimit        # Requests per time window
    cost_per_lookup: float       # 0.0 for free providers
    refresh_cadence: timedelta   # Recommended re-enrichment interval

    def enrich(self, entity: dict) -> list[FieldValue]:
        """Returns a list of (field_name, value, confidence) tuples."""
        ...
```

New providers are registered in a provider registry and automatically available to the enrichment pipeline.

**Tasks:**

- [ ] CENR-07: Implement EnrichmentProvider base class and registry
- [ ] CENR-08: Implement provider selection logic (based on entity type, available identifiers, tier)

**Tests:**

- [ ] CENR-T05: Test provider registry discovers and lists all registered providers
- [ ] CENR-T06: Test provider selection filters by entity type and available identifiers

---

## 6. Enrichment Triggers

**Supports processes:** KP-1 (step 1), KP-2 (step 1), KP-3 (step 1), KP-4 (step 1)

### 6.1 Requirements

| Trigger | Behavior |
|---|---|
| **Domain entry** (create/edit) | Immediate: Tier 1 website scraping. Background: Tier 2 API lookups. |
| **Email sync** | Auto-create company for new non-public domains; trigger Tier 1 enrichment. |
| **Periodic refresh** | Scheduled job re-enriches companies older than provider's `refresh_cadence`. |
| **On-demand** | User clicks "Refresh"; runs all applicable providers. |
| **Retroactive batch** | User initiates scan; runs email signature parsing and Tier 2 lookups across all companies. |

**Tasks:**

- [ ] CENR-09: Implement enrichment trigger on company creation
- [ ] CENR-10: Implement scheduled re-enrichment job
- [ ] CENR-11: Implement on-demand enrichment API endpoint
- [ ] CENR-12: Implement retroactive batch enrichment with progress tracking

**Tests:**

- [ ] CENR-T07: Test enrichment triggers on company auto-creation
- [ ] CENR-T08: Test scheduled job identifies and queues stale companies
- [ ] CENR-T09: Test on-demand enrichment runs all applicable providers
- [ ] CENR-T10: Test batch enrichment respects rate limits

---

## 7. Enrichment Run Tracking

**Supports processes:** All KPs (tracking)

### 7.1 Requirements

**`enrichment_runs`** table (entity-agnostic):

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | TEXT | **PK** | Prefixed ULID. |
| `entity_type` | TEXT | NOT NULL | `'company'` or `'contact'`. |
| `entity_id` | TEXT | NOT NULL | ID of entity being enriched. |
| `provider` | TEXT | NOT NULL | Provider name. |
| `status` | TEXT | NOT NULL, DEFAULT `'pending'` | `'pending'`, `'running'`, `'completed'`, `'failed'`. |
| `started_at` | TIMESTAMPTZ | | |
| `completed_at` | TIMESTAMPTZ | | |
| `error_message` | TEXT | | Error details if failed. |
| `created_at` | TIMESTAMPTZ | NOT NULL | |

**`enrichment_field_values`** table — field-level provenance:

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | TEXT | **PK** | Prefixed ULID. |
| `enrichment_run_id` | TEXT | NOT NULL, FK → `enrichment_runs(id)` ON DELETE CASCADE | |
| `field_name` | TEXT | NOT NULL | Target field. |
| `field_value` | TEXT | | The enriched value. |
| `confidence` | REAL | NOT NULL, DEFAULT 0.0 | 0.0–1.0. |
| `is_accepted` | BOOLEAN | DEFAULT false | Whether applied to entity record. |
| `created_at` | TIMESTAMPTZ | NOT NULL | |

**Tasks:**

- [ ] CENR-13: Create enrichment_runs table
- [ ] CENR-14: Create enrichment_field_values table
- [ ] CENR-15: Implement run lifecycle (pending → running → completed/failed)

**Tests:**

- [ ] CENR-T11: Test enrichment run tracking records all provider executions
- [ ] CENR-T12: Test field values are recorded with confidence and acceptance status

---

## 8. Confidence & Conflict Resolution

**Supports processes:** KP-1 (step 4), KP-2 (step 3)

### 8.1 Confidence Thresholds

Each field has a minimum confidence threshold. Values below threshold are stored in `enrichment_field_values` with `is_accepted = false` and queued for human review. Values at or above threshold are auto-applied. Default thresholds can be adjusted in system settings.

### 8.2 Conflict Resolution Priority

When a new enrichment run returns a value for a field that already has one:

| Priority | Source | Auto-Override Behavior |
|---|---|---|
| 1 (highest) | `manual` | Never auto-overridden. |
| 2 | `paid_api` | Overrides lower-priority sources. |
| 3 | `free_api` | Overrides lower-priority sources. |
| 4 | `website_scrape` | Overrides lower-priority sources. |
| 5 | `email_signature` | Overrides only inferred. |
| 6 (lowest) | `inferred` | Overridden by any source. |

**Rules:**

- Manual always wins — user-entered data is never auto-overridden.
- Higher priority overrides lower, but not vice versa.
- Same priority — keep existing value; flag for review.
- Below confidence threshold — stored but not applied regardless of priority.
- Users can always override via the UI.

### 8.3 Website Scraping — Name Extraction

When a company domain is first encountered and the company is auto-created with a placeholder name (name = domain), the website scraper attempts to discover the real company name.

**Name extraction sources (in order of confidence):**

| Source | Confidence |
|---|---|
| JSON-LD `Organization.name` | 0.9 |
| `og:site_name` meta tag | 0.8 |

**Overwrite guard:** The enrichment pipeline only overwrites the company name when the current name equals the `domain` column (placeholder). Manually-entered or previously-enriched names are preserved.

**Additional scraping targets:**

- About/About Us page — description, founding date, mission statement.
- Contact/Contact Us page — addresses, phone numbers, email addresses.
- Social media links — LinkedIn, Twitter/X, Facebook, Instagram, GitHub from headers, footers, contact pages.
- Structured data — schema.org markup for machine-readable firmographic data.
- Meta tags — description, Open Graph tags for company description and logo.

The scraper respects `robots.txt` and implements polite crawling with rate limiting and appropriate user-agent identification.

**Tasks:**

- [ ] CENR-16: Implement confidence threshold checking on field application
- [ ] CENR-17: Implement conflict resolution priority hierarchy
- [ ] CENR-18: Implement the overwrite guard for placeholder company names
- [ ] CENR-19: Implement name extraction from JSON-LD and og:site_name
- [ ] CENR-20: Implement polite website scraping with robots.txt compliance

**Tests:**

- [ ] CENR-T13: Test manual values are never overridden by enrichment
- [ ] CENR-T14: Test higher-priority sources override lower-priority
- [ ] CENR-T15: Test same-priority values flag for review
- [ ] CENR-T16: Test overwrite guard only replaces placeholder names
- [ ] CENR-T17: Test overwrite guard preserves manually-entered names
- [ ] CENR-T18: Test name extraction from JSON-LD Organization.name
- [ ] CENR-T19: Test name extraction from og:site_name meta tag
- [ ] CENR-T20: Test below-threshold values stored but not applied

---

## 9. Error Handling

**Supports processes:** All KPs

### 9.1 Requirements

- Failed providers do not block other providers in the same run.
- Failures are recorded in `enrichment_runs.error_message`.
- Transient failures (network timeouts, rate limits) are retried with exponential backoff.
- Persistent failures are logged and the run marked as `'failed'`.
- Failed runs are retried on the next enrichment cycle.

**Tasks:**

- [ ] CENR-21: Implement per-provider error isolation
- [ ] CENR-22: Implement exponential backoff retry for transient failures

**Tests:**

- [ ] CENR-T21: Test one provider failure doesn't block others
- [ ] CENR-T22: Test transient failures trigger retry with backoff
- [ ] CENR-T23: Test persistent failures mark run as failed

---

## 10. Enrichment API

**Supports processes:** KP-2 (step 1), KP-4 (step 1)

### 10.1 Requirements

| Endpoint | Method | Description |
|---|---|---|
| `/api/v1/companies/{id}/enrich` | POST | Trigger on-demand enrichment. |
| `/api/v1/companies/{id}/enrichment-runs` | GET | List enrichment runs for a company. |
| `/api/v1/companies/{id}/enrichment-runs/{run_id}` | GET | Get run details with field values. |

**Tasks:**

- [ ] CENR-23: Implement enrichment API endpoints
- [ ] CENR-24: Implement enrichment status display on company detail page

**Tests:**

- [ ] CENR-T24: Test on-demand enrichment API triggers providers
- [ ] CENR-T25: Test enrichment run history API returns correct data
