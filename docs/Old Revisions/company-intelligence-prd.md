# Company Intelligence PRD

## CRMExtender — Company Automation, Enrichment & Intelligence

**Version:** 1.0
**Date:** 2026-02-09
**Status:** Draft
**Parent Documents:** [CRMExtender PRD v1.1](PRD.md), [Contact Management PRD](contact-management-prd.md), [Data Layer PRD](data-layer-prd.md)

---

## Table of Contents

1. [Problem Statement](#1-problem-statement)
2. [Goals & Non-Goals](#2-goals--non-goals)
3. [Duplicate Detection & Merging](#3-duplicate-detection--merging)
4. [Company Hierarchy](#4-company-hierarchy)
5. [Company Enrichment Pipeline](#5-company-enrichment-pipeline)
6. [Company-Level Intelligence](#6-company-level-intelligence)
7. [Social Media Profiles](#7-social-media-profiles)
8. [Domain-to-Company Resolution](#8-domain-to-company-resolution)
9. [Data Model — New Tables](#9-data-model--new-tables)
10. [Data Model — Schema Changes](#10-data-model--schema-changes)
11. [Asset Storage](#11-asset-storage)
12. [Entity-Agnostic Shared Tables](#12-entity-agnostic-shared-tables)
13. [Enrichment Provider Architecture](#13-enrichment-provider-architecture)
14. [Scoring & Formula System](#14-scoring--formula-system)
15. [Migration Path](#15-migration-path)
16. [Design Decisions](#16-design-decisions)
17. [Future Work](#17-future-work)

---

## 1. Problem Statement

CRMExtender's company records are frequently auto-created from import routines such as a Google Contacts organization names during sync, in addition to being
manually created through the web UI.  The automatic import of companies creates several problems:

- **Rampant duplicates** — the same company appears under multiple
  names ("Acme Corp", "Acme Corporation", "ACME") because auto-creation
  is name-based with no deduplication.  There is no canonical identifier
  to prevent this.
- **Empty records** — The google Contacts Organization may have a name and nothing
  else.  No domain, no address, no industry, no context.  Users must
  manually research and populate every field.
- **No hierarchy** — parent/subsidiary relationships (Alphabet →
  Google → Google Cloud) cannot be represented.  All companies are
  flat peers.
- **No enrichment** — the system never proactively gathers intelligence
  about a company.  Industry, size, funding, social presence, and
  contact information must all be entered by hand.
- **No relationship intelligence** — with 512 contacts and thousands of
  communications, the data to answer "which companies am I most engaged
  with?" exists in the database, but no mechanism surfaces it.
- **No social presence** — company social media profiles are not tracked,
  monitored, or linked.
- **Missed company discovery** — email addresses contain company domains,
  but the system only creates companies from Google Contacts
  organization names, ignoring the domain signal entirely during email
  sync.

---

## 2. Goals & Non-Goals

### Goals

1. **Domain-based duplicate detection** — use root domain as the
   canonical company identifier, supporting multiple domains per company
   via a `company_identifiers` table.
2. **Company merging** — when duplicates are found, merge all associated
   entities (contacts, relationships, events) to the surviving record
   and soft-delete the absorbed record.
3. **Company hierarchy** — model parent/subsidiary, division, acquisition,
   and spinoff relationships with arbitrary nesting depth.
4. **Three-tier enrichment pipeline** — automatically gather company
   intelligence from owned data (website scraping, email signatures),
   free public APIs (Wikidata, OpenCorporates), and paid APIs (Clearbit,
   Apollo, Crunchbase), with a pluggable provider architecture.
5. **Entity-agnostic enrichment** — the same enrichment pipeline serves
   both companies and contacts.
6. **Field-level provenance** — every enriched field carries source
   attribution, confidence scoring, and timestamp for audit and conflict
   resolution.
7. **Precomputed relationship intelligence** — relationship strength
   scores calculated from communication patterns, sortable, with
   transparent factor breakdowns.
8. **Social media profile tracking** — separate tables for company and
   contact social profiles with tiered monitoring and change detection.
9. **Domain-to-company resolution** — during email sync, extract all
   domains from sender, recipients, and body, auto-creating companies
   for non-public domains with valid websites.
10. **Expanded company schema** — new fields for website, stock symbol,
    employee count, founded year, funding, revenue, and headquarters
    location.

### Non-Goals

- **Fuzzy name matching** — duplicate detection is strictly domain-based.
  Name similarity matching (e.g., "Acme Corp" vs "Acme Corporation")
  produces too many false positives and is excluded from scope.
- **Real-time social media monitoring** — social profile scanning follows
  a configurable cadence (weekly/monthly/quarterly), not real-time
  streaming.
- **Paid API cost controls** — budget limits, approval workflows, and
  per-lookup caps for paid enrichment providers are deferred.
- **Trend calculations** — period-over-period analysis and trend
  detection formulas are deferred to a future iteration.
- **Contact identity resolution** — the contact-management PRD covers
  probabilistic entity matching for contacts.  This PRD focuses on
  company-level deduplication and intelligence.

---

## 3. Duplicate Detection & Merging

### 3.1 Detection Strategy

The primary domain name is the canonical company duplicate identifier.
Detection is strictly domain-based — no fuzzy name matching.

The entire logic is identified in the file CompanyDetection.MD

**Domain normalization rules:**

- Strip `www.` prefix
- Lowercase all characters
- Extract root domain from subdomains: `mail.acme.com` →
  `acme.com`, `support.acme.com` → `acme.com`
- Strip trailing slashes and paths

**Public domain exclusion:** Domains belonging to free email providers
are never used for company resolution.  The exclusion list includes:
`gmail.com`, `googlemail.com`, `yahoo.com`, `yahoo.co.uk`,
`hotmail.com`, `outlook.com`, `live.com`, `msn.com`, `aol.com`,
`icloud.com`, `me.com`, `mac.com`, `mail.com`, `protonmail.com`,
`pm.me`, `zoho.com`, `yandex.com`, `gmx.com`, `fastmail.com`,
`tutanota.com`, `hey.com`, `comcast.net`, `att.net`, `verizon.net`,
`sbcglobal.net`, `cox.net`, `charter.net`, `earthlink.net`.

### 3.2 Detection Triggers

| Trigger             | Timing            | Action                                                                                 |
| ------------------- | ----------------- | -------------------------------------------------------------------------------------- |
| Company create/edit | On domain entry   | Check `company_identifiers` for existing match; flag if found                          |
| Email sync          | During processing | Extract all domains from sender, recipients, body; check against `company_identifiers` |
| Retroactive scan    | User-initiated    | Batch scan all companies for domain overlap                                            |

When a duplicate is detected during company creation or editing, the
system blocks the operation and presents the user with the existing
matching company, offering to merge or cancel.

### 3.3 The Merge-vs-Hierarchy Fork

When a user indicates that two company records are related, the system
asks: **"Are these duplicates, or are you establishing a company
hierarchy?"**

- **Duplicate** — proceeds to the merge flow (section 3.4).
- **Hierarchy** — proceeds to the hierarchy flow (section 4), where the
  user selects parent/child roles, hierarchy type, and effective date.

### 3.4 Duplicate Merge Flow

1. **User selects surviving record** — the user picks which company
   record is the "primary" that survives the merge.

2. **Entity reassignment** — all entities referencing the absorbed
   company are reassigned to the surviving company:
   
   | Entity                                                                                           | Reassignment                           |
   | ------------------------------------------------------------------------------------------------ | -------------------------------------- |
   | `contacts.company_id`                                                                            | UPDATE to surviving company ID         |
   | `relationships` (where `from_entity_id` or `to_entity_id` = absorbed, `entity_type = 'company'`) | UPDATE entity IDs to surviving company |
   | `event_participants` (where `entity_type = 'company'` and `entity_id` = absorbed)                | UPDATE entity_id to surviving company  |
   
   Conversations and communications are **not** directly reassigned —
   they are linked to companies indirectly through contact participants.
   Reassigning `contacts.company_id` carries these associations
   automatically.

3. **Domain consolidation** — all domains from both the surviving and
   absorbed company are assigned to the surviving company in the
   `company_identifiers` table.  Subdomains found in contact email
   addresses are also automatically associated.

4. **Relationship deduplication** — if both companies had relationships
   to the same third entity (e.g., both had a PARTNER relationship
   with Company C), the duplicate relationships are silently
   deduplicated.  One row is kept, the other removed.

5. **Field conflict resolution** — when both companies have values for
   the same field (industry, description, etc.), the UI will present a
   conflict resolution interface where the user picks the correct value
   per field.  For multi-value fields like addresses, the user can
   choose to keep both.  Full conflict resolution UI is a later phase;
   initially the surviving record's values take precedence, with empty
   fields filled from the absorbed record.

6. **Soft delete** — the absorbed company record is soft-deleted
   (`status = 'merged'`) for historical records.

7. **Audit logging** — the merge is recorded in the `company_merges`
   table with timestamp, user, surviving and absorbed company IDs, and
   a snapshot of what changed.

---

## 4. Company Hierarchy

### 4.1 Overview

Company hierarchy is modeled as a separate data structure from the
relationship types system.  While relationship types (PARTNER, VENDOR)
model peer and directional business relationships, hierarchy models
organizational structure: parent companies, subsidiaries, divisions,
acquisitions, and spinoffs.

### 4.2 Hierarchy Types

| Type          | Description                                     | Example                 |
| ------------- | ----------------------------------------------- | ----------------------- |
| `subsidiary`  | Parent company owns or controls a child company | Alphabet → Google       |
| `division`    | Parent company's internal business unit         | Google → Google Cloud   |
| `acquisition` | Parent company acquired the child company       | Google → YouTube (2006) |
| `spinoff`     | Child company was spun off from the parent      | eBay → PayPal           |

### 4.3 Data Model

The `company_hierarchy` table stores parent→child relationships as
single directional rows:

```sql
CREATE TABLE company_hierarchy (
    id                TEXT PRIMARY KEY,
    parent_company_id TEXT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    child_company_id  TEXT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    hierarchy_type    TEXT NOT NULL,
    effective_date    TEXT,
    end_date          TEXT,
    metadata          TEXT,
    created_by        TEXT REFERENCES users(id) ON DELETE SET NULL,
    updated_by        TEXT REFERENCES users(id) ON DELETE SET NULL,
    created_at        TEXT NOT NULL,
    updated_at        TEXT NOT NULL,
    CHECK (hierarchy_type IN ('subsidiary', 'division', 'acquisition', 'spinoff')),
    CHECK (parent_company_id != child_company_id)
);
```

### 4.4 Structural Properties

- **Arbitrary nesting** — hierarchies can nest to any depth
  (A → B → C → D).
- **Multiple parents** — a company can have multiple parent
  relationships (e.g., a joint venture with two parent companies, or a
  company that was a division of one company and later acquired by
  another).
- **Temporal** — `effective_date` and `end_date` track when hierarchy
  relationships begin and end, supporting historical representations
  (e.g., YouTube was independent until 2006, then acquired by Google).
- **Metadata** — JSON field for type-specific data (acquisition amount,
  deal terms, etc.).
- **Single directional row** — each relationship is stored as one row
  with `parent_company_id` → `child_company_id`.  No paired-row
  pattern.

### 4.5 Display

The UI displays hierarchy as flat sections on the company detail page:

- **Parent Company** section — shows the company's parent(s) with
  hierarchy type and effective date.
- **Subsidiaries** section — shows child companies with hierarchy type
  and effective date.

Both sections link to the related company's detail page.  Tree or
org-chart visualization is deferred to future work.

### 4.6 Separate Entities for Communications

Companies in a hierarchy are treated as separate entities for
communication purposes.  Viewing a parent company does **not** aggregate
contacts, conversations, or communications from its subsidiaries.  Each
company in the hierarchy maintains its own independent communication
history.

---

## 5. Company Enrichment Pipeline

### 5.1 Overview

The enrichment pipeline is entity-agnostic — the same architecture
serves both companies and contacts.  It uses a pluggable provider
model where each data source implements a common interface.

### 5.2 Three-Tier Source Architecture

#### Tier 1: Owned Data (Free, Immediate)

| Provider                   | Input                      | Output                                                                         |
| -------------------------- | -------------------------- | ------------------------------------------------------------------------------ |
| **Website scraper**        | Company domain             | Description, address, phone, email, social links, structured data (schema.org) |
| **Email signature parser** | Communications in database | Company address, phone, website, contact titles, social links                  |

Tier 1 providers run immediately on domain entry and retroactively
over existing communications.

#### Tier 2: Free Public APIs

| Provider                 | Input                     | Output                                                                             |
| ------------------------ | ------------------------- | ---------------------------------------------------------------------------------- |
| **Wikidata / Wikipedia** | Company name/domain       | Founding date, industry, headquarters, employee count, parent company, description |
| **OpenCorporates**       | Company name/jurisdiction | Corporate registration, status, officers                                           |
| **SEC EDGAR**            | Company name/stock symbol | Filings, revenue, executive info (US public companies only)                        |

Tier 2 providers run as background batch jobs after initial creation.

#### Tier 3: Paid APIs (Future)

| Provider       | Input        | Output                                                    |
| -------------- | ------------ | --------------------------------------------------------- |
| **Clearbit**   | Domain       | Full company profile, tech stack, employee count, funding |
| **Apollo**     | Domain       | Company data, employee directory, contact info            |
| **Crunchbase** | Company name | Funding rounds, investors, acquisitions, leadership       |

Tier 3 providers are integration points designed into the architecture
but implemented in a later phase.

### 5.3 Provider Interface

Each enrichment provider implements a common interface:

```python
class EnrichmentProvider:
    name: str                    # e.g., "website_scraper", "wikidata"
    tier: int                    # 1, 2, or 3
    entity_types: list[str]      # ["company"], ["contact"], or ["company", "contact"]
    rate_limit: RateLimit        # requests per time window
    cost_per_lookup: float       # 0.0 for free providers
    refresh_cadence: timedelta   # recommended re-enrichment interval

    def enrich(self, entity: dict) -> list[FieldValue]:
        """Returns a list of (field_name, value, confidence) tuples."""
        ...
```

New providers are registered in a provider registry and automatically
available to the enrichment pipeline.

### 5.4 Enrichment Triggers

| Trigger                        | Behavior                                                                                       |
| ------------------------------ | ---------------------------------------------------------------------------------------------- |
| **Domain entry** (create/edit) | Immediate: Tier 1 website scraping.  Background: Tier 2 API lookups.                           |
| **Email sync**                 | Auto-create company for new non-public domains with valid websites; trigger Tier 1 enrichment. |
| **Periodic refresh**           | Scheduled job re-enriches companies whose data is older than the provider's `refresh_cadence`. |
| **On-demand**                  | User clicks "Refresh" on a company detail page; runs all applicable providers.                 |
| **Retroactive batch**          | User initiates a scan; runs email signature parsing and Tier 2 lookups across all companies.   |

### 5.5 Field-Level Provenance

Every enriched value is tracked with full provenance:

**`enrichment_runs`** — tracks the enrichment process:

| Column          | Description                                             |
| --------------- | ------------------------------------------------------- |
| `id`            | UUID primary key                                        |
| `entity_type`   | `'company'` or `'contact'`                              |
| `entity_id`     | UUID of the entity being enriched                       |
| `provider`      | Provider name (e.g., `'website_scraper'`, `'wikidata'`) |
| `status`        | `'pending'`, `'running'`, `'completed'`, `'failed'`     |
| `started_at`    | ISO 8601 timestamp                                      |
| `completed_at`  | ISO 8601 timestamp                                      |
| `error_message` | Error details if failed                                 |

**`enrichment_field_values`** — tracks individual field results:

| Column              | Description                                         |
| ------------------- | --------------------------------------------------- |
| `id`                | UUID primary key                                    |
| `enrichment_run_id` | FK → `enrichment_runs(id)`                          |
| `field_name`        | Target field (e.g., `'description'`, `'industry'`)  |
| `field_value`       | The enriched value                                  |
| `confidence`        | 0.0–1.0 confidence score                            |
| `is_accepted`       | Whether this value was applied to the entity record |

### 5.6 Confidence Thresholds

Each field has a minimum confidence threshold.  Values below the
threshold are stored in `enrichment_field_values` with
`is_accepted = 0` and queued for human review.  Values at or above
the threshold are auto-applied to the entity record.

Default thresholds can be adjusted in system settings.

### 5.7 Conflict Resolution

When a new enrichment run returns a value for a field that already
has one, the following priority hierarchy determines which value wins:

| Priority    | Source            | Auto-Override Behavior              |
| ----------- | ----------------- | ----------------------------------- |
| 1 (highest) | `manual`          | Never auto-overridden by any source |
| 2           | `paid_api`        | Overrides lower-priority sources    |
| 3           | `free_api`        | Overrides lower-priority sources    |
| 4           | `website_scrape`  | Overrides lower-priority sources    |
| 5           | `email_signature` | Overrides only inferred             |
| 6 (lowest)  | `inferred`        | Overridden by any source            |

Rules:

- **Manual always wins** — user-entered data is never auto-overridden.
- **Higher priority overrides lower** — a paid API result replaces a
  website scrape, but not vice versa.
- **Same priority** — keep existing value; flag for review.
- **Below confidence threshold** — stored but not applied regardless
  of priority.
- **Users can always override** via the UI.

### 5.8 Website Scraping

When a company domain is added, the system scrapes the associated
website looking for:

- **About Us / About page** — company description, founding date,
  mission statement.
- **Contact Us / Contact page** — addresses, phone numbers, email
  addresses.
- **Social media links** — LinkedIn, Twitter/X, Facebook, Instagram,
  GitHub links in headers, footers, or contact pages.
- **Structured data** — schema.org markup (`Organization`, `LocalBusiness`)
  provides machine-readable industry, founding date, logo, address,
  and social links.
- **Meta tags** — `<meta>` description, Open Graph tags for company
  description and logo.

The scraper respects `robots.txt` and implements polite crawling with
rate limiting and appropriate user-agent identification.

---

## 6. Company-Level Intelligence

### 6.1 Overview

Company-level intelligence derives insights from existing communication
data and enrichment.  It surfaces relationship strength, engagement
trends, and key contacts without requiring users to manually analyze
their email history.

### 6.2 Relationship Strength Scoring

A composite score per company (and per contact) computed from
communication patterns:

**Factors (in priority order):**

| Factor      | Description                                                        | Weight  |
| ----------- | ------------------------------------------------------------------ | ------- |
| Recency     | How recently the last communication occurred                       | Highest |
| Frequency   | How often communications occur                                     | High    |
| Reciprocity | Ratio of inbound to outbound; balanced is best                     | Medium  |
| Breadth     | Number of distinct contacts at the company in active conversations | Medium  |
| Duration    | How long the communication relationship has existed                | Lower   |

**Directionality weighting:** Outbound (user-initiated) communications
carry more weight than inbound, reflecting intentional relationship
investment.  Inbound-only communication (e.g., marketing emails, cold
outreach) contributes less to the score.

**Time decay:** Scores decay over time.  A company emailed daily six
months ago but not since scores lower than one emailed weekly in the
current month.

**User-editable formula:** The default formula uses a static weighting.
Users can adjust factor weights via system settings to match their
priorities.

### 6.3 Score Storage

Scores are precomputed and stored in the `entity_scores` table for
fast sorting and display:

| Column         | Description                                                              |
| -------------- | ------------------------------------------------------------------------ |
| `id`           | UUID primary key                                                         |
| `entity_type`  | `'company'` or `'contact'`                                               |
| `entity_id`    | UUID of the entity                                                       |
| `score_type`   | `'relationship_strength'`, `'communication_trend'`, `'engagement_level'` |
| `score_value`  | Numeric value, sortable                                                  |
| `factors`      | JSON breakdown of contributing factors                                   |
| `computed_at`  | ISO 8601 timestamp                                                       |
| `triggered_by` | `'event'`, `'scheduled'`, `'manual'`                                     |

The `factors` JSON enables score transparency — users can click on a
score to see the equation values and how each factor contributed.

### 6.4 Score Recalculation

Scores are recalculated using a hybrid approach:

| Trigger          | Description                                                                                   |
| ---------------- | --------------------------------------------------------------------------------------------- |
| **Event-driven** | New communication sent/received involving a company contact → recompute that company's scores |
| **Time-based**   | Scheduled job runs daily to apply time decay across all entities                              |
| **Bulk**         | After a merge, import, or sync completes → recompute affected entities                        |
| **Manual**       | User requests recalculation from the UI                                                       |

### 6.5 Derived Metrics

Beyond relationship strength, the following metrics are derivable
from existing data:

| Metric                 | Source                                                                  | Description                                                                   |
| ---------------------- | ----------------------------------------------------------------------- | ----------------------------------------------------------------------------- |
| Communication volume   | `communications` + `communication_participants` + `contacts.company_id` | Total communications over time per company                                    |
| Last contact           | Same                                                                    | Days/months/years since last communication                                    |
| Key contacts           | Same                                                                    | Top contacts at each company by communication volume and recency              |
| Topic distribution     | `conversation_tags` + `conversation_participants`                       | What topics/tags are associated with conversations involving company contacts |
| Meeting frequency      | `events` + `event_participants`                                         | How often meetings occur with company contacts                                |
| Meeting-to-email ratio | `events` + `communications`                                             | High-touch vs. low-touch relationship indicator                               |

### 6.6 Relative Time Display

Communication recency is displayed as relative time:

- Less than 30 days: "**X days**"
- Less than 12 months: "**Y months**"
- 12 months or more: "**Z years**"

The display format is independent of the scoring formula, which uses
its own time windows for strength calculation.

### 6.7 Views over Alerts

Intelligence is surfaced through **views** (saved smart filters) rather
than interruptive alerts.  Users pull information when they are ready,
rather than being pushed notifications.

Example views:

- "Companies — declining engagement (30-day trend)"
- "Contacts — no communication in 90+ days"
- "Companies — highest relationship strength"
- "New companies — detected this week"
- "Key contacts at risk — communication dropped significantly"

Views are stored using the existing `views` table.  Users can create
custom views with their own filter and sort criteria tied to
precomputed scores.

---

## 7. Social Media Profiles

### 7.1 Overview

Social media profiles are tracked in separate tables for companies
and contacts because the metadata diverges significantly.  Company
profiles carry organizational metrics (follower count, posting
frequency, verified status) while contact profiles carry professional
data (job title, connections, endorsements).

### 7.2 Discovery

Social media profiles are discovered through:

| Source                  | Method                                          |
| ----------------------- | ----------------------------------------------- |
| Website scraping        | Social links in headers, footers, contact pages |
| Email signature parsing | LinkedIn, Twitter, etc. links in signatures     |
| Manual entry            | User adds profiles directly                     |
| Enrichment APIs         | Paid providers return social URLs               |

Social profiles are **not** auto-discovered from company domains or
contact names.  The risk of creating invalid connections to wrong
profiles is too high.  All discovered profiles must come from explicit
links found in scraped or user-provided data.

### 7.3 Monitoring Tiers

Each entity (contact or company) is assigned a monitoring tier that
controls scanning frequency and extraction depth:

| Tier         | Scan Cadence | Extraction Depth                         | Use Case                                   |
| ------------ | ------------ | ---------------------------------------- | ------------------------------------------ |
| **High**     | Weekly       | Full profile, posts, changes, employment | Family, key clients, close network         |
| **Standard** | Monthly      | Profile changes, employment, bio         | Active business contacts                   |
| **Low**      | Quarterly    | Employment changes only                  | Peripheral contacts, dormant relationships |
| **None**     | Never        | Nothing                                  | Noise contacts, opt-out                    |

- **System default** — stored in system settings (default: `standard`).
- **Per-entity override** — user can set a specific tier for any contact
  or company.
- **Auto-suggestion** — the system can recommend tier upgrades based on
  relationship strength scores (e.g., "Acme Corp is on Low monitoring
  but you've had 15 communications this month — upgrade to High?").
- **No per-platform control** — all platforms are scanned at the same
  tier level.  The UI provides filtering and display preferences so
  users see what matters to them.

Configuration is stored in the `monitoring_preferences` table:

| Column            | Description                                 |
| ----------------- | ------------------------------------------- |
| `entity_type`     | `'company'` or `'contact'`                  |
| `entity_id`       | UUID of the entity                          |
| `monitoring_tier` | `'high'`, `'standard'`, `'low'`, `'none'`   |
| `tier_source`     | `'manual'`, `'auto_suggested'`, `'default'` |
| `created_at`      | ISO 8601 timestamp                          |
| `updated_at`      | ISO 8601 timestamp                          |

### 7.4 Change Detection

Rather than presenting raw profile data, the system surfaces
**meaningful changes**:

- Store previous scan results for comparison
- Diff each scan against prior values
- Surface deltas: "Sarah Chen changed her title from VP Engineering to
  CTO", "Acme Corp updated their LinkedIn bio to mention AI products"
- Employment and position changes are high-priority signals
- Changes appear in an activity stream on the entity detail page

### 7.5 Platform-Specific Extraction

Each social media platform is implemented as a separate scanning
provider with its own extraction rules, rate limits, and Terms of
Service compliance approach:

| Platform      | Key Signals                                    | Notes                                      |
| ------------- | ---------------------------------------------- | ------------------------------------------ |
| **LinkedIn**  | Title, company, position changes, connections  | Richest professional signal; strictest ToS |
| **Twitter/X** | Bio changes, posting activity, follower trends | More public, easier access                 |
| **Facebook**  | Life events, employment                        | Mostly personal, limited API               |
| **GitHub**    | Activity level, repos, contributions           | Relevant for tech contacts                 |
| **Instagram** | Business accounts: branding, activity          | Less professional value                    |

ToS compliance is addressed individually per platform.

### 7.6 Scanning Cadence Configuration

The scanning cadence for each monitoring tier is user-defined with
system defaults:

- System defaults are stored in a system settings table.
- Users can override cadence per contact or company.
- A scheduled background job runs scans based on each entity's tier
  cadence and `last_scanned_at` timestamp.

---

## 8. Domain-to-Company Resolution

### 8.1 Overview

During email sync, the system extracts all email domains from every
communication and uses them to discover and link companies.  This is
a significant upgrade from the current name-only auto-creation from
Google Contacts organization names.

### 8.2 Resolution Flow

1. **Extract all domains** — from sender, all recipients (to, cc, bcc),
   and any email addresses found in the message body.

2. **Filter public domains** — skip any domain in the public domain
   exclusion list (section 3.1).

3. **Normalize to root domain** — strip subdomains to extract the root
   domain: `mail.acme.com` → `acme.com`.

4. **Check `company_identifiers`** — look up the normalized root domain
   in the `company_identifiers` table.

5. **If match found** — link the associated contact to the matched
   company (if not already linked).

6. **If no match** — validate the domain has a working website (HTTP
   check).  If valid:
   
   - Auto-create a company record with the domain as the initial name.
   - Add the domain to `company_identifiers`.
   - Set the domain as the company's primary domain (denormalized on
     `companies.domain`).
   - Trigger Tier 1 enrichment (website scraping) to populate
     description, address, social links, and potentially a better
     company name.
   - Link the associated contact to the new company.

7. **If no valid website** — do not auto-create.  The domain is logged
   for potential manual review.

### 8.3 Contact Linking

When a company is resolved from a domain, contacts with email
addresses matching that domain are linked:

- Set `contacts.company_id` to the resolved company.
- Only link contacts that do not already have a `company_id` assigned
  (do not override existing manual assignments).

---

## 9. Data Model — New Tables

### 9.1 `company_identifiers`

Stores multiple domains per company, enabling multi-domain duplicate
detection.  Mirrors the pattern of `contact_identifiers` but for
companies.

```sql
CREATE TABLE company_identifiers (
    id          TEXT PRIMARY KEY,
    company_id  TEXT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    type        TEXT NOT NULL DEFAULT 'domain',
    value       TEXT NOT NULL,
    is_primary  INTEGER DEFAULT 0,
    source      TEXT,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    UNIQUE(type, value)
);

CREATE INDEX idx_ci_company ON company_identifiers(company_id);
CREATE INDEX idx_ci_lookup  ON company_identifiers(type, value);
```

The primary domain is denormalized on `companies.domain` for display.

### 9.2 `company_hierarchy`

Models parent/child organizational relationships with temporal support.

```sql
CREATE TABLE company_hierarchy (
    id                TEXT PRIMARY KEY,
    parent_company_id TEXT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    child_company_id  TEXT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    hierarchy_type    TEXT NOT NULL,
    effective_date    TEXT,
    end_date          TEXT,
    metadata          TEXT,
    created_by        TEXT REFERENCES users(id) ON DELETE SET NULL,
    updated_by        TEXT REFERENCES users(id) ON DELETE SET NULL,
    created_at        TEXT NOT NULL,
    updated_at        TEXT NOT NULL,
    CHECK (hierarchy_type IN ('subsidiary', 'division', 'acquisition', 'spinoff')),
    CHECK (parent_company_id != child_company_id)
);

CREATE INDEX idx_ch_parent ON company_hierarchy(parent_company_id);
CREATE INDEX idx_ch_child  ON company_hierarchy(child_company_id);
CREATE INDEX idx_ch_type   ON company_hierarchy(hierarchy_type);
```

### 9.3 `company_merges`

Audit log for company merge operations.

```sql
CREATE TABLE company_merges (
    id                   TEXT PRIMARY KEY,
    surviving_company_id TEXT NOT NULL REFERENCES companies(id),
    absorbed_company_id  TEXT NOT NULL,
    absorbed_company_snapshot TEXT NOT NULL,
    contacts_reassigned  INTEGER DEFAULT 0,
    relationships_reassigned INTEGER DEFAULT 0,
    events_reassigned    INTEGER DEFAULT 0,
    relationships_deduplicated INTEGER DEFAULT 0,
    merged_by            TEXT REFERENCES users(id) ON DELETE SET NULL,
    merged_at            TEXT NOT NULL
);

CREATE INDEX idx_cm_surviving ON company_merges(surviving_company_id);
CREATE INDEX idx_cm_absorbed  ON company_merges(absorbed_company_id);
```

The `absorbed_company_snapshot` is a JSON serialization of the full
absorbed company record at the time of merge, enabling audit review
and potential undo.

### 9.4 `company_social_profiles`

Social media profiles for companies with scanning metadata.

```sql
CREATE TABLE company_social_profiles (
    id              TEXT PRIMARY KEY,
    company_id      TEXT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    platform        TEXT NOT NULL,
    profile_url     TEXT NOT NULL,
    username        TEXT,
    verified        INTEGER DEFAULT 0,
    follower_count  INTEGER,
    bio             TEXT,
    last_scanned_at TEXT,
    last_post_at    TEXT,
    source          TEXT,
    confidence      REAL,
    status          TEXT DEFAULT 'active',
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL,
    UNIQUE(company_id, platform, profile_url)
);

CREATE INDEX idx_csp_company  ON company_social_profiles(company_id);
CREATE INDEX idx_csp_platform ON company_social_profiles(platform);
```

### 9.5 `contact_social_profiles`

Social media profiles for contacts with professional metadata.

```sql
CREATE TABLE contact_social_profiles (
    id                TEXT PRIMARY KEY,
    contact_id        TEXT NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
    platform          TEXT NOT NULL,
    profile_url       TEXT NOT NULL,
    username          TEXT,
    headline          TEXT,
    connection_degree INTEGER,
    mutual_connections INTEGER,
    verified          INTEGER DEFAULT 0,
    follower_count    INTEGER,
    bio               TEXT,
    last_scanned_at   TEXT,
    last_post_at      TEXT,
    source            TEXT,
    confidence        REAL,
    status            TEXT DEFAULT 'active',
    created_at        TEXT NOT NULL,
    updated_at        TEXT NOT NULL,
    UNIQUE(contact_id, platform, profile_url)
);

CREATE INDEX idx_ctsp_contact  ON contact_social_profiles(contact_id);
CREATE INDEX idx_ctsp_platform ON contact_social_profiles(platform);
```

### 9.6 `enrichment_runs`

Tracks enrichment process execution for both companies and contacts.

```sql
CREATE TABLE enrichment_runs (
    id            TEXT PRIMARY KEY,
    entity_type   TEXT NOT NULL,
    entity_id     TEXT NOT NULL,
    provider      TEXT NOT NULL,
    status        TEXT NOT NULL DEFAULT 'pending',
    started_at    TEXT,
    completed_at  TEXT,
    error_message TEXT,
    created_at    TEXT NOT NULL,
    CHECK (entity_type IN ('company', 'contact')),
    CHECK (status IN ('pending', 'running', 'completed', 'failed'))
);

CREATE INDEX idx_er_entity   ON enrichment_runs(entity_type, entity_id);
CREATE INDEX idx_er_provider ON enrichment_runs(provider);
CREATE INDEX idx_er_status   ON enrichment_runs(status);
```

### 9.7 `enrichment_field_values`

Field-level provenance for enrichment results.

```sql
CREATE TABLE enrichment_field_values (
    id                TEXT PRIMARY KEY,
    enrichment_run_id TEXT NOT NULL REFERENCES enrichment_runs(id) ON DELETE CASCADE,
    field_name        TEXT NOT NULL,
    field_value       TEXT,
    confidence        REAL NOT NULL DEFAULT 0.0,
    is_accepted       INTEGER DEFAULT 0,
    created_at        TEXT NOT NULL
);

CREATE INDEX idx_efv_run   ON enrichment_field_values(enrichment_run_id);
CREATE INDEX idx_efv_field ON enrichment_field_values(field_name, is_accepted);
```

### 9.8 `entity_scores`

Precomputed intelligence scores for sorting and display.

```sql
CREATE TABLE entity_scores (
    id           TEXT PRIMARY KEY,
    entity_type  TEXT NOT NULL,
    entity_id    TEXT NOT NULL,
    score_type   TEXT NOT NULL,
    score_value  REAL NOT NULL DEFAULT 0.0,
    factors      TEXT,
    computed_at  TEXT NOT NULL,
    triggered_by TEXT,
    CHECK (entity_type IN ('company', 'contact'))
);

CREATE UNIQUE INDEX idx_es_entity_score ON entity_scores(entity_type, entity_id, score_type);
CREATE INDEX idx_es_score ON entity_scores(score_type, score_value);
```

The unique index on `(entity_type, entity_id, score_type)` ensures
one score per type per entity, enabling UPSERT on recalculation.

### 9.9 `monitoring_preferences`

Per-entity monitoring tier configuration.

```sql
CREATE TABLE monitoring_preferences (
    id              TEXT PRIMARY KEY,
    entity_type     TEXT NOT NULL,
    entity_id       TEXT NOT NULL,
    monitoring_tier TEXT NOT NULL DEFAULT 'standard',
    tier_source     TEXT NOT NULL DEFAULT 'default',
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL,
    CHECK (entity_type IN ('company', 'contact')),
    CHECK (monitoring_tier IN ('high', 'standard', 'low', 'none')),
    CHECK (tier_source IN ('manual', 'auto_suggested', 'default')),
    UNIQUE(entity_type, entity_id)
);
```

---

## 10. Data Model — Schema Changes

### 10.1 New Columns on `companies` Table

| Column                  | Type    | Description                                   |
| ----------------------- | ------- | --------------------------------------------- |
| `website`               | TEXT    | Company website URL (distinct from domain)    |
| `stock_symbol`          | TEXT    | Stock ticker symbol (e.g., `GOOGL`, `AAPL`)   |
| `size_range`            | TEXT    | Employee count range (see 10.2)               |
| `employee_count`        | INTEGER | Raw employee count when known                 |
| `founded_year`          | INTEGER | Year the company was founded                  |
| `revenue_range`         | TEXT    | Annual revenue range                          |
| `funding_total`         | TEXT    | Total funding raised                          |
| `funding_stage`         | TEXT    | Latest funding stage                          |
| `headquarters_location` | TEXT    | Denormalized from primary address for display |

```sql
ALTER TABLE companies ADD COLUMN website TEXT;
ALTER TABLE companies ADD COLUMN stock_symbol TEXT;
ALTER TABLE companies ADD COLUMN size_range TEXT;
ALTER TABLE companies ADD COLUMN employee_count INTEGER;
ALTER TABLE companies ADD COLUMN founded_year INTEGER;
ALTER TABLE companies ADD COLUMN revenue_range TEXT;
ALTER TABLE companies ADD COLUMN funding_total TEXT;
ALTER TABLE companies ADD COLUMN funding_stage TEXT;
ALTER TABLE companies ADD COLUMN headquarters_location TEXT;
```

### 10.2 Employee Count Ranges

Ranges are aligned with LinkedIn's widely-used classification:

| Range        | Value        |
| ------------ | ------------ |
| 1–10         | `1-10`       |
| 11–50        | `11-50`      |
| 51–200       | `51-200`     |
| 201–500      | `201-500`    |
| 501–1,000    | `501-1000`   |
| 1,001–5,000  | `1001-5000`  |
| 5,001–10,000 | `5001-10000` |
| 10,001+      | `10001+`     |

When a raw `employee_count` is available, `size_range` is derived
from it.  When only a range is available from a provider, `size_range`
is stored directly and `employee_count` remains NULL.

### 10.3 Funding Stage Values

| Value           | Description               |
| --------------- | ------------------------- |
| `pre_seed`      | Pre-seed funding          |
| `seed`          | Seed round                |
| `series_a`      | Series A                  |
| `series_b`      | Series B                  |
| `series_c`      | Series C                  |
| `series_d_plus` | Series D or later         |
| `ipo`           | Publicly traded           |
| `private`       | Private, no known funding |
| `bootstrapped`  | Self-funded               |

---

## 11. Asset Storage

### 11.1 Content-Addressable Storage

All graphical assets (logos, headshots, banners) are stored as files
on the filesystem using content-addressable storage.  The file's SHA-256
hash determines its storage path, providing automatic deduplication
(the same image scraped twice is stored once).

### 11.2 Directory Structure

The hash is split into two levels of directory sharding to avoid
filesystem issues with large numbers of files in a single directory:

```
data/assets/{hash[0:2]}/{hash[2:4]}/{full_hash}.{extension}
```

Example: a PNG logo with hash `ab3def7890...` is stored at:

```
data/assets/ab/3d/ab3def7890abcdef1234567890abcdef1234567890abcdef1234567890abcdef.png
```

### 11.3 `entity_assets` Table

```sql
CREATE TABLE entity_assets (
    id          TEXT PRIMARY KEY,
    entity_type TEXT NOT NULL,
    entity_id   TEXT NOT NULL,
    asset_type  TEXT NOT NULL,
    hash        TEXT NOT NULL,
    mime_type   TEXT NOT NULL,
    file_ext    TEXT NOT NULL,
    source      TEXT,
    created_at  TEXT NOT NULL,
    CHECK (entity_type IN ('company', 'contact')),
    CHECK (asset_type IN ('logo', 'headshot', 'banner'))
);

CREATE INDEX idx_ea_entity ON entity_assets(entity_type, entity_id);
CREATE INDEX idx_ea_hash   ON entity_assets(hash);
```

The filesystem path is derived from `hash` and `file_ext` — it is
never stored directly.  This ensures the path computation logic is
centralized and the table remains the single source of truth for
which assets exist.

---

## 12. Entity-Agnostic Shared Tables

### 12.1 `addresses`

Stores multiple addresses for companies and contacts.

```sql
CREATE TABLE addresses (
    id           TEXT PRIMARY KEY,
    entity_type  TEXT NOT NULL,
    entity_id    TEXT NOT NULL,
    address_type TEXT NOT NULL DEFAULT 'headquarters',
    street       TEXT,
    city         TEXT,
    state        TEXT,
    postal_code  TEXT,
    country      TEXT,
    is_primary   INTEGER DEFAULT 0,
    source       TEXT,
    confidence   REAL,
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL,
    CHECK (entity_type IN ('company', 'contact'))
);

CREATE INDEX idx_addr_entity ON addresses(entity_type, entity_id);
```

Address types: `headquarters`, `branch`, `home`, `mailing`, `billing`.

### 12.2 `phone_numbers`

Stores multiple phone numbers for companies and contacts.

```sql
CREATE TABLE phone_numbers (
    id          TEXT PRIMARY KEY,
    entity_type TEXT NOT NULL,
    entity_id   TEXT NOT NULL,
    phone_type  TEXT NOT NULL DEFAULT 'main',
    number      TEXT NOT NULL,
    is_primary  INTEGER DEFAULT 0,
    source      TEXT,
    confidence  REAL,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    CHECK (entity_type IN ('company', 'contact'))
);

CREATE INDEX idx_phone_entity ON phone_numbers(entity_type, entity_id);
```

Phone types: `main`, `direct`, `mobile`, `support`, `sales`, `fax`.
Numbers are stored in E.164 format when possible.

### 12.3 `email_addresses`

Stores typed, sourced email addresses for companies and contacts.

```sql
CREATE TABLE email_addresses (
    id          TEXT PRIMARY KEY,
    entity_type TEXT NOT NULL,
    entity_id   TEXT NOT NULL,
    email_type  TEXT NOT NULL DEFAULT 'general',
    address     TEXT NOT NULL,
    is_primary  INTEGER DEFAULT 0,
    source      TEXT,
    confidence  REAL,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    CHECK (entity_type IN ('company', 'contact'))
);

CREATE INDEX idx_email_entity ON email_addresses(entity_type, entity_id);
```

Email types: `general`, `support`, `sales`, `billing`, `personal`,
`work`.

**Note:** For contacts, the `contact_identifiers` table continues to
serve identity resolution (matching incoming emails to contacts).  The
`email_addresses` table provides the richer typed/sourced model for
display and communication purposes.  The two may overlap but serve
different functions.

---

## 13. Enrichment Provider Architecture

### 13.1 Provider Registry

Providers are registered in a central registry that the enrichment
pipeline queries to determine which providers to run for a given
entity type and trigger context.

```python
PROVIDER_REGISTRY = {
    "website_scraper":    WebsiteScraperProvider(),
    "email_signature":    EmailSignatureProvider(),
    "wikidata":           WikidataProvider(),
    "open_corporates":    OpenCorporatesProvider(),
    "sec_edgar":          SecEdgarProvider(),
    "clearbit":           ClearbitProvider(),       # Tier 3 — future
    "apollo":             ApolloProvider(),          # Tier 3 — future
    "crunchbase":         CrunchbaseProvider(),      # Tier 3 — future
}
```

### 13.2 Pipeline Execution

1. **Trigger event** → pipeline determines entity type and context.
2. **Select providers** → filter registry by entity type, tier, and
   availability.
3. **Create enrichment runs** → one `enrichment_runs` row per provider
   per entity.
4. **Execute providers** → each provider returns a list of
   `(field_name, value, confidence)` tuples.
5. **Store field values** → insert into `enrichment_field_values`.
6. **Apply conflict resolution** → compare against existing values
   using priority hierarchy and confidence thresholds.
7. **Update entity record** → accepted values are written to the
   entity table.

### 13.3 Rate Limiting

Each provider declares its own rate limits.  The pipeline respects
these limits using a token bucket or similar algorithm.  Paid providers
have stricter limits to control costs.

### 13.4 Error Handling

- Failed providers do not block other providers in the same run.
- Failures are recorded in `enrichment_runs.error_message`.
- Transient failures (network timeouts, rate limits) are retried with
  exponential backoff.
- Persistent failures are logged and the run marked as `'failed'`.

---

## 14. Scoring & Formula System

### 14.1 Default Formula

The relationship strength score is computed as a weighted combination
of factors:

```
score = (w_recency * recency_score)
      + (w_frequency * frequency_score)
      + (w_reciprocity * reciprocity_score)
      + (w_breadth * breadth_score)
      + (w_duration * duration_score)
```

Each factor is normalized to a 0.0–1.0 range before weighting.

### 14.2 Default Weights

| Factor      | Default Weight | Notes                                                 |
| ----------- | -------------- | ----------------------------------------------------- |
| Recency     | 0.35           | Highest — recent contact matters most                 |
| Frequency   | 0.25           | High — regular engagement signals active relationship |
| Reciprocity | 0.20           | Medium — balanced communication is healthier          |
| Breadth     | 0.12           | Medium — multi-contact relationships are stronger     |
| Duration    | 0.08           | Lower — longevity alone doesn't indicate strength     |

### 14.3 Directionality Multiplier

Within each factor's calculation, outbound (user-initiated)
communications carry a higher multiplier than inbound:

| Direction | Multiplier |
| --------- | ---------- |
| Outbound  | 1.0x       |
| Inbound   | 0.6x       |

This reflects that initiating communication is a stronger signal of
relationship investment than passively receiving it.

### 14.4 User-Editable Weights

Users can adjust factor weights via system settings.  The UI presents
sliders for each factor weight.  Weights are automatically normalized
to sum to 1.0.

### 14.5 Score Transparency

When a user clicks on a relationship strength score, the UI displays
the factor breakdown:

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

---

## 15. Migration Path

### 15.1 v6 to v7

The v6 to v7 migration adds the company intelligence system to an
existing database:

1. **Backup** — copies the database to
   `{name}.v6-backup-{timestamp}.db`.

2. **ALTER `companies` table** — add new columns: `website`,
   `stock_symbol`, `size_range`, `employee_count`, `founded_year`,
   `revenue_range`, `funding_total`, `funding_stage`,
   `headquarters_location`.

3. **Create new tables** — `company_identifiers`, `company_hierarchy`,
   `company_merges`, `company_social_profiles`,
   `contact_social_profiles`, `enrichment_runs`,
   `enrichment_field_values`, `entity_scores`,
   `monitoring_preferences`, `entity_assets`, `addresses`,
   `phone_numbers`, `email_addresses`.

4. **Create indexes** — all indexes defined in section 9.

5. **Seed `company_identifiers`** — for each existing company with a
   non-NULL `domain`, create a corresponding row in
   `company_identifiers` with `type='domain'` and `is_primary=1`.

6. **Validate** — verify all tables exist and have expected columns.

The migration is idempotent — running it twice has no effect.  The
`--dry-run` flag applies the migration to a backup copy instead of
the production database.

### 15.2 Fresh Databases

`init_db()` in `poc/database.py` includes all new tables and indexes
in `_SCHEMA_SQL` and `_INDEX_SQL`, so new databases are created with
company intelligence support from the start.

---

## 16. Design Decisions

### Why root domain as the duplicate key instead of fuzzy name matching?

Fuzzy name matching produces unacceptable false positive rates.
"Acme" matches "Acme Corp", "Acme Corporation", and "Acme Industries"
— which may be completely different companies.  Domain-based matching
is deterministic: `acme.com` either matches or it doesn't.  Companies
can be created without a domain, but domain-based deduplication only
activates when a domain is present.

### Why a separate `company_hierarchy` table instead of using relationship types?

Hierarchy has fundamentally different properties from business
relationships.  It's inherently tree-structured (parent → child), supports
arbitrary nesting, requires temporal tracking (effective/end dates), and
carries type-specific metadata (acquisition amounts).  The relationship
types system (PARTNER, VENDOR) models peer and directional business
relationships with different semantics (bidirectional paired rows,
forward/reverse labels).  Mixing the two would complicate both systems.

### Why entity-agnostic enrichment instead of separate company/contact pipelines?

The enrichment process is identical for both entity types: trigger →
select providers → execute → store results → apply conflict resolution.
Duplicating this pipeline for companies and contacts would double the
code and maintenance burden with no architectural benefit.  The
providers themselves differ, but the pipeline is shared.

### Why separate social media tables for companies and contacts?

Company social profiles carry organizational metrics (follower count,
posting frequency, verified page status) while contact profiles carry
professional data (job title, headline, connection degree, mutual
connections).  These columns diverge significantly and will continue to
diverge as enrichment matures.  A shared polymorphic table would
require nullable columns everywhere and `entity_type` conditionals in
every query.

### Why content-addressable asset storage instead of BLOBs in SQLite?

The production database is already 236 MB.  Storing logos and images
as BLOBs would significantly inflate database size, slow backups, and
degrade query performance.  Content-addressable filesystem storage
with hash-based deduplication keeps the database lean while
automatically deduplicating identical assets.

### Why two-level directory sharding for assets?

Flat directories with thousands of files cause performance degradation
on most filesystems.  Two levels of sharding (first two characters,
then characters three and four of the hash) distributes files across
up to 65,536 directories, preventing any single directory from becoming
a bottleneck.

### Why precomputed scores instead of on-demand calculation?

With hundreds of companies and thousands of communications, computing
relationship strength at query time for a sorted list would be
prohibitively slow.  Precomputed scores enable instant `ORDER BY`
sorting on any list page.  The hybrid recalculation model (event-driven

+ time-based decay) keeps scores fresh without requiring full
  recomputation on every page load.

### Why views over alerts?

Alerts interrupt the user's current focus and create notification
fatigue.  Views let users pull intelligence when they are ready —
opening a "declining engagement" view is an intentional action, not
an interruption.  The same underlying data powers both approaches, so
alerts can be added later if demand emerges.

### Why keep `contact_identifiers` alongside the new `email_addresses` table?

`contact_identifiers` serves identity resolution — matching incoming
emails to existing contact records.  It is optimized for fast lookup
by `(type, value)`.  The new `email_addresses` table serves a different
purpose: typed, sourced, multi-value email storage with confidence
scoring for display and enrichment provenance.  The two tables may
contain overlapping data but serve fundamentally different roles in
the system.

### Why denormalize primary domain and headquarters location?

Both values are displayed on nearly every company list and detail view.
Joining to `company_identifiers` or `addresses` on every list query
adds unnecessary complexity.  The denormalized values are kept in sync
by the enrichment pipeline and merge operations.  The authoritative
data lives in the normalized tables; the denormalized columns are
display optimizations.

---

## 17. Future Work

### 17.1 Field Conflict Resolution UI

Full per-field conflict resolution during company merges, allowing
users to pick the correct value from each source or keep both for
multi-value fields like addresses.

### 17.2 Trend Calculations

Period-over-period analysis for communication patterns — "engagement
with Acme Corp increased 40% month over month."  Requires defining
baseline calculation methodology and deviation thresholds.

### 17.3 Paid API Cost Controls

Budget limits, per-company lookup caps, and approval workflows before
spending on Tier 3 paid enrichment providers.

### 17.4 Tree / Org-Chart Visualization

Visual tree or org-chart rendering of company hierarchies on the
company detail page, beyond the current flat "Parent Company" /
"Subsidiaries" list sections.

### 17.5 Automatic Tier Adjustment

Automatically adjust monitoring tiers based on relationship strength
score changes, with user confirmation before upgrading or downgrading.

### 17.6 LinkedIn-Specific Integration

Dedicated LinkedIn integration for professional profile monitoring,
pending ToS compliance analysis and potential API partnership.

### 17.7 Email Signature Parser

Automated extraction of company intelligence (addresses, phone numbers,
titles, social links) from email signatures across existing and
incoming communications.

### 17.8 Retroactive Domain Resolution

Batch processing of all existing communications to extract domains and
auto-create/link companies retroactively, with a progress UI showing
discovery counts and linking results.
