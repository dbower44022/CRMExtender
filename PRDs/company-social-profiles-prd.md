# Company — Social Media Profiles Sub-PRD

**Version:** 1.0
**Last Updated:** 2026-02-23
**Status:** Draft
**Entity Base PRD:** [company-entity-base-prd.md]
**Referenced Entity PRDs:** [company-enrichment-prd.md] (profile discovery via enrichment)

---

## 1. Overview

### 1.1 Purpose

Social media profile tracking gives users visibility into a company's public presence across LinkedIn, Twitter/X, Facebook, GitHub, and Instagram. Profiles are discovered through explicit links found in website scraping, email signatures, manual entry, or enrichment APIs — never auto-discovered from company names or domains (too high a risk of false matches). Monitoring tiers control how frequently profiles are scanned for changes, and change detection surfaces meaningful updates in the company's activity stream.

### 1.2 Preconditions

- Company record exists.
- At least one social profile link has been discovered or entered.
- Monitoring preferences are configured (defaults to `standard` tier).

---

## 2. Context

### 2.1 Relevant Fields

| Field | Role in This Action |
|---|---|
| LinkedIn URL | Convenience field on the company record. Kept in sync with the LinkedIn entry in the social profiles table. |
| Name, Domain | Used for display in profile discovery and change notifications. |

### 2.2 Relevant Relationships

- **Company Social Profiles** — One-to-many: a company can have multiple profiles across platforms.
- **Monitoring Preferences** — One-to-one: each company has a monitoring tier that controls scan frequency.

### 2.3 Relevant Lifecycle Transitions

- No company lifecycle transitions. Social profiles have their own status: `active`, `archived`, `invalid`.

### 2.4 Cross-Entity Context

- **Company Enrichment Sub-PRD:** Website scraping and email signature parsing discover social profile links as a side effect of enrichment. Discovered links are registered in the social profiles table.
- **Contact Entity Base PRD:** Contact social profiles use a separate table because contact profiles carry different metadata (job title, connections, endorsements) than company profiles (follower count, posting frequency, verified status).

---

## 3. Key Processes

### KP-1: Social Profile Discovery

**Trigger:** Enrichment pipeline discovers social media links during website scraping or email signature parsing.

**Step 1 — Link extraction:** Enrichment provider finds social media URLs in website headers, footers, contact pages, email signatures, or structured data.

**Step 2 — Platform identification:** System identifies the platform from the URL pattern (linkedin.com, twitter.com, etc.) and extracts the username or vanity slug.

**Step 3 — Duplicate check:** System checks if this profile URL already exists for the company. If so, updates the existing record's metadata. If not, creates a new social profile record.

**Step 4 — Confidence assignment:** Source confidence is assigned based on discovery method (website scrape: 0.8, email signature: 0.7, enrichment API: 0.9, manual: 1.0).

### KP-2: Manual Profile Management

**Trigger:** User adds, edits, or removes a social profile from the company detail page.

**Step 1 — Add profile:** User enters a social media URL. System auto-detects platform and extracts username. Profile created with source = `manual`, confidence = 1.0.

**Step 2 — Edit profile:** User updates URL or metadata. Change is recorded.

**Step 3 — Remove profile:** User removes a profile. Status set to `archived` (soft delete) or hard deleted based on source.

### KP-3: Social Profile Monitoring

**Trigger:** Scheduled scan job runs based on the company's monitoring tier.

**Step 1 — Tier check:** System identifies companies due for scanning based on their monitoring tier and last scan timestamp.

**Step 2 — Profile scan:** For each due profile, system fetches the profile page and extracts current data (follower count, bio, verified status, last post date).

**Step 3 — Change detection:** System compares current data against the previous scan. Meaningful changes are identified.

**Step 4 — Change surfacing:** Detected changes appear in the company's activity stream on the detail page (e.g., "Acme Corp updated their LinkedIn bio to mention AI products").

---

## 4. Social Profiles Data Model

**Supports processes:** KP-1 (step 3), KP-2 (all steps), KP-3 (step 2)

### 4.1 Company Social Profiles Table

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | TEXT | **PK** | Prefixed ULID. |
| `company_id` | TEXT | NOT NULL, FK → `companies(id)` ON DELETE CASCADE | Owning company. |
| `platform` | TEXT | NOT NULL | `linkedin`, `twitter`, `facebook`, `github`, `instagram`. |
| `profile_url` | TEXT | NOT NULL | Full profile URL. |
| `username` | TEXT | | Platform-specific handle or vanity URL slug. |
| `verified` | BOOLEAN | DEFAULT false | Whether profile is verified/official. |
| `follower_count` | INTEGER | | Last known follower count. |
| `bio` | TEXT | | Profile bio/description. |
| `last_scanned_at` | TIMESTAMPTZ | | Last successful scan timestamp. |
| `last_post_at` | TIMESTAMPTZ | | Most recent post timestamp. |
| `source` | TEXT | | `website_scrape`, `email_signature`, `manual`, `enrichment`. |
| `confidence` | REAL | | 0.0–1.0. |
| `status` | TEXT | DEFAULT `'active'` | `active`, `archived`, `invalid`. |
| `created_at` | TIMESTAMPTZ | NOT NULL | |
| `updated_at` | TIMESTAMPTZ | NOT NULL | |

**Constraints:**

- `UNIQUE(company_id, platform, profile_url)` — No duplicate profile entries.
- Index on `(company_id)` for listing a company's profiles.
- Index on `(platform)` for platform-level queries.

### 4.2 Discovery Rules

Social profiles are not auto-discovered from company domains or names. All discovered profiles must come from explicit links found in scraped or user-provided data:

| Source | Method | Confidence |
|---|---|---|
| Website scraping | Social links in headers, footers, contact pages. | 0.8 |
| Email signature parsing | LinkedIn, Twitter, etc. links in signatures. | 0.7 |
| Manual entry | User adds profiles directly. | 1.0 |
| Enrichment APIs | Paid providers return social URLs. | 0.9 |

**Rationale:** Auto-discovering profiles from company names risks creating false associations (e.g., matching "Springfield Insurance" to "Springfield" on LinkedIn). Requiring explicit link discovery eliminates this class of error.

**Tasks:**

- [ ] CSOC-01: Create company_social_profiles table
- [ ] CSOC-02: Implement profile creation with platform auto-detection from URL
- [ ] CSOC-03: Implement duplicate detection on profile URL
- [ ] CSOC-04: Integrate social link discovery into website scraper enrichment provider
- [ ] CSOC-05: Integrate social link discovery into email signature parser

**Tests:**

- [ ] CSOC-T01: Test profile creation with platform auto-detection
- [ ] CSOC-T02: Test duplicate detection prevents duplicate profile URLs
- [ ] CSOC-T03: Test website scraper discovers social links from page content
- [ ] CSOC-T04: Test confidence assignment per discovery source

---

## 5. Monitoring Tiers

**Supports processes:** KP-3 (step 1)

### 5.1 Requirements

| Tier | Scan Cadence | Extraction Depth | Use Case |
|---|---|---|---|
| **High** | Weekly | Full profile, posts, changes | Key clients, strategic partners. |
| **Standard** | Monthly | Profile changes, bio | Active business contacts. |
| **Low** | Quarterly | Employment/leadership changes only | Peripheral companies. |
| **None** | Never | Nothing | Noise, opt-out. |

### 5.2 Monitoring Preferences Table

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
- `UNIQUE(entity_type, entity_id)` — One preference per entity.

**Tasks:**

- [ ] CSOC-06: Create monitoring_preferences table
- [ ] CSOC-07: Implement monitoring tier assignment (default standard)
- [ ] CSOC-08: Implement scheduled scan job respecting tier cadences
- [ ] CSOC-09: UI for user to adjust a company's monitoring tier

**Tests:**

- [ ] CSOC-T05: Test default tier assignment on company creation
- [ ] CSOC-T06: Test scan job correctly identifies companies due for scanning per tier
- [ ] CSOC-T07: Test tier "none" companies are never scanned
- [ ] CSOC-T08: Test manual tier override persists

---

## 6. Change Detection

**Supports processes:** KP-3 (steps 3–4)

### 6.1 Requirements

Rather than presenting raw profile data, the system surfaces meaningful changes:

- Store previous scan results for comparison.
- Diff each scan against prior values.
- Surface deltas as activity stream entries on the company detail page.
- Leadership and position changes are high-priority signals.

**Example change notifications:**

- "Acme Corp updated their LinkedIn bio to mention AI products"
- "New CEO listed on Acme Corp's LinkedIn page"
- "Acme Corp's Twitter follower count increased by 15% this month"
- "Acme Corp's GitHub now shows 12 public repositories (was 8)"

**Tasks:**

- [ ] CSOC-10: Implement profile scan result storage for diffing
- [ ] CSOC-11: Implement change detection algorithm (diff previous vs. current)
- [ ] CSOC-12: Implement change notification entries in company activity stream
- [ ] CSOC-13: Implement priority classification (leadership changes = high priority)

**Tests:**

- [ ] CSOC-T09: Test change detection identifies bio text changes
- [ ] CSOC-T10: Test change detection identifies follower count changes
- [ ] CSOC-T11: Test leadership changes are flagged as high priority
- [ ] CSOC-T12: Test no-change scans produce no activity stream entries

---

## 7. Social Profiles API

**Supports processes:** KP-2 (all steps)

### 7.1 Requirements

| Endpoint | Method | Description |
|---|---|---|
| `/api/v1/companies/{id}/social-profiles` | GET | List social profiles for a company. |
| `/api/v1/companies/{id}/social-profiles` | POST | Add a social profile. |
| `/api/v1/companies/{id}/social-profiles/{profile_id}` | PATCH | Update a social profile. |
| `/api/v1/companies/{id}/social-profiles/{profile_id}` | DELETE | Remove a social profile. |

**Tasks:**

- [ ] CSOC-14: Implement social profiles CRUD API endpoints
- [ ] CSOC-15: Implement social profiles display section on company detail page

**Tests:**

- [ ] CSOC-T13: Test social profiles API CRUD operations
- [ ] CSOC-T14: Test profile display on company detail page shows all active profiles
