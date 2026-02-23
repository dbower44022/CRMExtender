# Contact — Enrichment Sub-PRD

**Version:** 1.0
**Last Updated:** 2026-02-22
**Status:** Draft
**Entity Base PRD:** [contact-entity-base-prd.md]
**Referenced Entity PRDs:** [Company Management Entity Base PRD](company-management-prd_V1.md)

---

## 1. Overview

### 1.1 Purpose

Enrichment augments contact records with data from external sources — public profile data, firmographic data, social profiles, photos, and contact details. The goal is to transform a bare-bones record (name + email) into a rich intelligence object with verified company affiliation, social presence, photo, phone number, and contextual intelligence. Enrichment is what makes CRMExtender's contacts "living intelligence objects" rather than static address book entries.

The enrichment system also includes OSINT (Open Source Intelligence) monitors for tracking changes to key contacts over time — job changes, funding rounds, news mentions, and other notable events.

### 1.2 Preconditions

- Contact exists with at least one identifier (email, phone, or social profile URL).
- At least one enrichment adapter is configured and accessible.

---

## 2. Context

### 2.1 Relevant Fields

| Field | Usage in This Action |
|---|---|
| All contact identifiers | Input for enrichment adapter selection and lookup |
| First Name / Last Name | Enrichment may populate or update these |
| Job Title | Enrichment populates from external profiles |
| Company (employment record) | Enrichment creates or updates employment records |
| Avatar URL | Enrichment populates from social profiles |
| Social profiles | Enrichment discovers and adds social profile URLs |
| Intelligence Score | Recomputed after enrichment based on data completeness |
| Lead Source | Attribution for enrichment-sourced data |

### 2.2 Relevant Relationships

- **Company** — Enrichment may discover company affiliation and create employment records.
- **Contact Identifiers** — Enrichment may discover new identifiers (additional emails, phone numbers, social profiles).

### 2.3 Relevant Lifecycle Transitions

- Enrichment can transition a contact from `incomplete` to `active` if it populates sufficient data (name + verified identifier).

---

## 3. Enrichment Pipeline

### 3.1 Requirements

The enrichment pipeline is triggered in three ways:
- **Automatic on creation** — When a new contact is created from any source, enrichment runs automatically.
- **Manual on demand** — User clicks "Enrich" on a contact's detail page.
- **Periodic re-enrichment** — OSINT monitors check for changes on monitored contacts at configurable intervals.

The pipeline follows these stages:

1. **Adapter Selection** — Based on available identifiers, adapter priority, cost, and rate limits, the system selects which enrichment adapters to invoke. Free sources are preferred over paid sources. Multiple adapters may be invoked for a single contact.

2. **Adapter Execution** — Each selected adapter performs its lookup and returns data in its native format.

3. **Normalization** — Adapter responses are mapped to a common internal schema. Confidence scores are assigned based on the source's reliability.

4. **Conflict Resolution** — Normalized data is compared against existing contact data. Rules:
   - User-entered data always wins over enrichment data.
   - Higher-confidence data wins over lower-confidence data.
   - Source attribution is preserved on every data point.

5. **Merge** — Non-conflicting data is applied to the contact record. Conflicting data is stored with attribution for user review (on manual enrichment, conflicts are shown as a diff before applying). Events are emitted for all changes.

6. **Intelligence Score Update** — The intelligence score is recomputed based on the updated data completeness.

**User stories:**
- As a user, I want new contacts to be automatically enriched with public data (company, title, social profiles, photo) within minutes of creation.
- As a user, I want to manually trigger enrichment for a specific contact, so I can refresh stale data or fill gaps.
- As a user, I want to see where each piece of contact data came from and how confident the system is.

**Performance target:** Auto-enrichment coverage > 60% of contacts enriched within 24 hours of creation.

**Tasks:**

- [ ] ENRICH-01: Implement enrichment dispatcher with adapter selection logic (priority, cost, rate limits)
- [ ] ENRICH-02: Implement response normalization to common schema
- [ ] ENRICH-03: Implement conflict resolution (user data wins, higher confidence wins)
- [ ] ENRICH-04: Implement data merge with source attribution on every data point
- [ ] ENRICH-05: Implement enrichment trigger on contact creation (automatic)
- [ ] ENRICH-06: Implement manual enrichment trigger from contact detail page
- [ ] ENRICH-07: Implement enrichment diff preview for manual enrichment (show changes before applying)
- [ ] ENRICH-08: Implement event emission for all enrichment-sourced changes

**Tests:**

- [ ] ENRICH-T01: Auto-enrichment triggers within 60 seconds of contact creation
- [ ] ENRICH-T02: Adapter selection prefers free sources over paid sources
- [ ] ENRICH-T03: Multiple adapters invoke correctly for a single contact
- [ ] ENRICH-T04: User-entered data is preserved over conflicting enrichment data
- [ ] ENRICH-T05: Higher-confidence enrichment data wins over lower-confidence data
- [ ] ENRICH-T06: Source attribution is recorded on every enriched data point
- [ ] ENRICH-T07: Manual enrichment shows diff preview before applying
- [ ] ENRICH-T08: Intelligence score updates after enrichment completes

---

## 4. Enrichment Adapters

### 4.1 Requirements

The enrichment system uses a pluggable adapter framework. Each adapter implements a common interface:

- **can_enrich(contact, identifiers)** — Returns whether this adapter can perform a lookup given the available identifiers.
- **enrich(contact, identifiers)** — Performs the lookup and returns normalized results.
- **source_name** — Unique identifier for this adapter (e.g., `enrichment_apollo`).
- **rate_limit** — Maximum requests per time window for this adapter.

**Planned adapters:**

| Adapter | Input | Output | Priority | Cost |
|---|---|---|---|---|
| **Google People API** | OAuth + contact sync | Name, emails, phones, addresses, photos | 0 (free, pre-existing) | Free |
| **Apollo** | Email or domain | Full profile (name, title, company, phone, social, photo) | 1 (primary) | Per-lookup |
| **Clearbit** | Email or domain | Company + person data, firmographics | 2 | Per-lookup |
| **People Data Labs** | Email, phone, or name + company | Person + company data | 3 | Per-lookup |
| **LinkedIn (browser ext.)** | Browser extension capture | Profile, headline, experience, connections | N/A (user-driven) | Free |
| **Email signature parser** | Email body parsing | Name, title, company, phone, address | N/A (passive) | Free |

**Business rules:**
- Adapters are invoked in priority order. If a higher-priority adapter returns sufficient data, lower-priority adapters may be skipped.
- Rate limits are enforced per adapter. If an adapter is rate-limited, it is skipped and retried later.
- New adapters can be added without modifying the pipeline.

**Tasks:**

- [ ] ENRICH-09: Implement pluggable adapter interface
- [ ] ENRICH-10: Implement Apollo adapter
- [ ] ENRICH-11: Implement Clearbit adapter
- [ ] ENRICH-12: Implement People Data Labs adapter
- [ ] ENRICH-13: Implement Google People API adapter (integrated with Google Contacts sync)
- [ ] ENRICH-14: Implement email signature parser adapter
- [ ] ENRICH-15: Implement per-adapter rate limiting

**Tests:**

- [ ] ENRICH-T09: Apollo adapter returns normalized profile data from email input
- [ ] ENRICH-T10: Clearbit adapter returns normalized company + person data
- [ ] ENRICH-T11: Rate-limited adapter is skipped and retried on next cycle
- [ ] ENRICH-T12: New adapter can be registered without pipeline changes
- [ ] ENRICH-T13: Email signature parser extracts name, title, company, phone from signature block

---

## 5. Intelligence Items

### 5.1 Requirements

Intelligence items are discrete pieces of information about a contact or company, sourced from enrichment, OSINT monitoring, or manual entry. Each item represents a notable event or data point:

- Job change detected
- Company funding round
- News mention
- Social media activity
- Technology change at company
- Hiring signal
- Acquisition
- Patent or publication
- Custom user-entered intelligence

Each intelligence item has a source, category, title, optional summary, optional source URL, confidence score, verification status, and optional expiration date (for time-sensitive intelligence like job postings).

Intelligence items appear on the contact's detail page in a dedicated intelligence section, sorted by recency. They feed into AI briefing generation and anomaly detection.

**User story:** As a user, I want to set up monitoring alerts for key contacts, so I'm notified when they change jobs, their company raises funding, or other notable events occur.

**Tasks:**

- [ ] ENRICH-16: Implement intelligence item creation from enrichment and OSINT sources
- [ ] ENRICH-17: Implement manual intelligence item entry
- [ ] ENRICH-18: Implement intelligence item display on contact detail page
- [ ] ENRICH-19: Implement intelligence item verification workflow (user confirms or dismisses)

**Tests:**

- [ ] ENRICH-T14: Enrichment creates intelligence item when job change detected
- [ ] ENRICH-T15: Manual intelligence item can be created with custom category
- [ ] ENRICH-T16: Intelligence items display in reverse chronological order
- [ ] ENRICH-T17: Verified intelligence items show verification badge

---

## 6. OSINT Monitors

### 6.1 Requirements

Users can configure monitoring on specific contacts to watch for changes from public sources. Each monitor specifies:

- Which contact or company to monitor
- Which source to check (LinkedIn, news, SEC filings, domain changes, enrichment refresh)
- Check frequency (hourly, daily, weekly)
- Which alert categories to trigger on (job change, funding round, news mention, etc.)

When a monitor detects a change, it creates an intelligence item and optionally triggers a notification (in-app alert, email, or Slack).

**Business rules:**
- Monitors can be paused or expired.
- Monitor frequency respects source rate limits and terms of service.
- All monitored data comes from publicly available sources only.

**Performance target:** Monitored contacts have data freshness < 7 days since last check.

**Tasks:**

- [ ] ENRICH-20: Implement OSINT monitor configuration (create, pause, expire)
- [ ] ENRICH-21: Implement scheduled monitor execution at configured frequency
- [ ] ENRICH-22: Implement change detection (compare current data against last known state)
- [ ] ENRICH-23: Implement alert creation and notification dispatch on detected changes

**Tests:**

- [ ] ENRICH-T18: Daily monitor executes within 24 hours of last check
- [ ] ENRICH-T19: Monitor detects job title change and creates intelligence item
- [ ] ENRICH-T20: Monitor triggers notification on configured alert category
- [ ] ENRICH-T21: Paused monitor does not execute

---

## 7. Intelligence Score Computation

### 7.1 Requirements

The intelligence score (0.0–1.0) reflects how much the system knows about a contact, weighted by data quality across categories:

| Field Category | Weight | Scoring Rule |
|---|---|---|
| **Name** (first + last) | 0.15 | 0.15 if both present, 0.08 if only one |
| **Email** (verified) | 0.15 | 0.15 if at least one verified email |
| **Phone** (verified) | 0.10 | 0.10 if at least one verified phone |
| **Company** (current) | 0.10 | 0.10 if current employment record exists |
| **Title** (current) | 0.08 | 0.08 if current job title exists |
| **Social profiles** | 0.07 | 0.035 per profile (max 2 counted) |
| **Photo** | 0.05 | 0.05 if avatar URL is set |
| **Address** | 0.05 | 0.05 if at least one address |
| **Employment history** | 0.10 | 0.05 per historical position (max 2) |
| **Enrichment data** | 0.10 | 0.10 if at least one enrichment source |
| **Communication history** | 0.05 | 0.05 if at least one communication linked |

**Total: 1.0.** Score is recomputed on enrichment, identity merge, and on a daily schedule.

**Tasks:**

- [ ] ENRICH-24: Implement intelligence score computation with weighted categories
- [ ] ENRICH-25: Implement score recomputation triggers (enrichment, merge, daily schedule)

**Tests:**

- [ ] ENRICH-T22: Contact with all data populated scores 1.0
- [ ] ENRICH-T23: Contact with only email scores 0.15
- [ ] ENRICH-T24: Score updates after enrichment adds new data
- [ ] ENRICH-T25: Score updates after merge combines data from two contacts
