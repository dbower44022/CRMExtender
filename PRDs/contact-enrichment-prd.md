# Contact — Enrichment Sub-PRD

**Version:** 2.0
**Last Updated:** 2026-02-22
**Status:** Draft
**Entity Base PRD:** [contact-entity-base-prd.md]
**Referenced Entity PRDs:** [Company Management Entity Base PRD](company-management-prd.md)

> **V2.0 (2026-02-22):** Added Key Processes section defining end-to-end user experiences for all enrichment scenarios. Restructured functional sections with process linkage.

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

## 3. Key Processes

### KP-1: Automatic Enrichment on Contact Creation

**Trigger:** A new contact is created from any source — manual entry, email sync, import, Google Contacts sync, or browser extension capture.

**Step 1 — Background trigger:** Within 60 seconds of contact creation, the enrichment pipeline starts automatically. The user does not initiate this — it happens silently.

**Step 2 — Adapter execution:** The system selects appropriate adapters based on available identifiers and runs them in priority order. Free sources first, then paid sources if needed.

**Step 3 — Silent data merge:** Enriched data is merged into the contact record automatically. No conflicts are shown to the user for auto-enrichment — the system applies conflict resolution rules (user-entered data wins, higher confidence wins). Source attribution is recorded on every data point.

**Step 4 — Profile update:** The contact's detail page progressively fills in over the next few minutes. If the user is viewing the contact, they see fields populate (avatar appears, title fills in, social profiles appear). No page refresh required — updates appear via real-time push or on next page load.

**Step 5 — Status transition:** If the contact was `incomplete` and enrichment provides sufficient data (name + verified identifier), the contact automatically transitions to `active`.

**Step 6 — Intelligence score update:** The intelligence score is recomputed, reflecting the new data completeness.

### KP-2: Manual Enrichment (Refresh)

**Trigger:** The user clicks "Enrich" on a contact's detail page to refresh stale data or fill gaps.

**Step 1 — Initiate:** The user clicks "Enrich" in the action bar. A loading indicator appears on the button.

**Step 2 — Adapter execution:** The system runs all available adapters (regardless of whether they've run before) to get the freshest data.

**Step 3 — Diff preview:** Unlike auto-enrichment, manual enrichment shows the user a diff before applying. A panel slides open showing: fields that would be added (new data), fields that would be updated (existing value → new value with source attribution for both), and fields that conflict with user-entered data (shown but not auto-applied). Each change has a checkbox — all are checked by default.

**Step 4 — User selection:** The user reviews the diff and unchecks any changes they don't want. They can also override the conflict resolution rule and choose to accept enrichment data even for user-entered fields.

**Step 5 — Apply:** The user clicks "Apply Changes." Selected changes are saved. Events are emitted. Intelligence score is recomputed.

**Step 6 — Confirmation:** The panel closes. The contact detail page reflects the updated data. A success message confirms: "Enriched with [N] updates from [source names]."

### KP-3: Browsing Source Attribution

**Trigger:** The user wants to understand where a piece of contact data came from.

**Step 1 — Hover on any field:** On the contact detail page, hovering over any enrichable field shows a tooltip with: the data source (e.g., "Apollo," "Google Contacts," "Manual entry"), the confidence score (e.g., 0.92), when it was last updated, and whether it was user-entered or system-enriched.

**Step 2 — Source history:** Clicking the attribution tooltip expands to show the full history of that field — every value it has had, from which source, with timestamps. This lets the user see how a field has evolved across enrichment cycles.

### KP-4: Setting Up an OSINT Monitor

**Trigger:** The user wants to track changes for a key contact over time.

**Step 1 — Initiate:** On the contact's detail page, the user clicks "Monitor" in the action bar (or navigates to the intelligence card and clicks "Set Up Monitoring").

**Step 2 — Configure monitor:** A configuration panel opens. The user selects:
- **Sources to check:** LinkedIn profile changes, news mentions, SEC filings, domain/company changes, periodic enrichment refresh. Multiple sources can be selected.
- **Check frequency:** Hourly, daily (default), or weekly per source.
- **Alert categories:** Job change, funding round, news mention, acquisition, hiring signal, technology change. The user checks which categories should trigger alerts.
- **Notification method:** In-app notification (default), email digest, Slack (if configured).

**Step 3 — Activate:** The user clicks "Start Monitoring." A confirmation appears: "Monitoring [Name] — checking [sources] [frequency]. You'll be notified of [categories]."

**Step 4 — Ongoing operation:** Monitors run on schedule in the background. The user sees a "Monitored" badge on the contact's detail page. Detected changes appear as intelligence items (KP-5).

**Step 5 — Managing monitors:** The user can pause, resume, edit, or delete monitors from the contact's intelligence card or from a centralized Monitors dashboard (Settings → Monitors) showing all active monitors across all contacts.

### KP-5: Receiving and Acting on Intelligence Items

**Trigger:** An OSINT monitor detects a change, enrichment discovers new information, or the user manually adds intelligence.

**Step 1 — Intelligence item creation:** The system creates an intelligence item with category, title, summary, source URL, confidence, and timestamp. For monitor-detected items, the notification is dispatched per the monitor configuration.

**Step 2 — Notification:** If configured, the user receives a notification: "Job change detected: [Name] is now [Title] at [Company]." The notification links to the contact's detail page.

**Step 3 — Intelligence card on detail page:** The intelligence card shows items in reverse chronological order. Each item shows: category icon, title, summary, source, timestamp, and verification status (unverified, verified, dismissed).

**Step 4 — Verification:** The user can click a checkmark to verify an item (confirming it's accurate) or an "×" to dismiss it (marking it as inaccurate or irrelevant). Verified items show a badge. Dismissed items are hidden (with an option to show dismissed items).

**Step 5 — Manual intelligence entry:** The user can click "Add Intelligence" to manually create an item — entering category, title, summary, and optional source URL. This is useful for information gathered from phone calls, meetings, or other offline sources.

### KP-6: Understanding a Contact's Intelligence Score

**Trigger:** The user sees the intelligence score on a contact's card or detail page and wants to understand it.

**Step 1 — Score display:** The intelligence score (0.0–1.0) is displayed on the contact's detail page header as a visual indicator (e.g., circular progress or bar).

**Step 2 — Score breakdown:** Clicking the score opens a breakdown panel showing each category's contribution: name (0.15), email (0.15), phone (0.10), company (0.10), etc. Filled categories show their weight in green; missing categories show their weight in gray. This immediately tells the user what data is missing.

**Step 3 — Actionable gaps:** Missing categories include action links — e.g., "Phone: missing — [Enrich to find]" or "Social profiles: missing — [Add manually]." These let the user improve the score directly.

---

## 4. Enrichment Pipeline

**Supports processes:** KP-1 (steps 1–6), KP-2 (steps 1–6). This section defines the technical pipeline that powers both automatic and manual enrichment.

### 4.1 Requirements

The enrichment pipeline follows six stages:

1. **Adapter Selection** — Based on available identifiers, adapter priority, cost, and rate limits, the system selects which enrichment adapters to invoke. Free sources are preferred over paid sources. Multiple adapters may be invoked for a single contact.

2. **Adapter Execution** — Each selected adapter performs its lookup and returns data in its native format.

3. **Normalization** — Adapter responses are mapped to a common internal schema. Confidence scores are assigned based on the source's reliability.

4. **Conflict Resolution** — Normalized data is compared against existing contact data. Rules: user-entered data always wins over enrichment data; higher-confidence data wins over lower-confidence data; source attribution is preserved on every data point.

5. **Merge** — For auto-enrichment (KP-1): non-conflicting data is applied silently. For manual enrichment (KP-2): all changes are presented as a diff for user review before applying. Events are emitted for all changes.

6. **Intelligence Score Update** — The intelligence score is recomputed based on updated data completeness.

**Performance target:** Auto-enrichment coverage > 60% of contacts enriched within 24 hours of creation.

**Tasks:**

- [ ] ENRICH-01: Implement enrichment dispatcher with adapter selection logic (priority, cost, rate limits)
- [ ] ENRICH-02: Implement response normalization to common schema
- [ ] ENRICH-03: Implement conflict resolution (user data wins, higher confidence wins)
- [ ] ENRICH-04: Implement data merge with source attribution on every data point
- [ ] ENRICH-05: Implement enrichment trigger on contact creation (automatic, within 60 seconds)
- [ ] ENRICH-06: Implement manual enrichment trigger from contact detail page
- [ ] ENRICH-07: Implement enrichment diff preview panel for manual enrichment
- [ ] ENRICH-08: Implement event emission for all enrichment-sourced changes
- [ ] ENRICH-09: Implement real-time or next-load update of contact detail page during auto-enrichment

**Tests:**

- [ ] ENRICH-T01: Auto-enrichment triggers within 60 seconds of contact creation
- [ ] ENRICH-T02: Adapter selection prefers free sources over paid sources
- [ ] ENRICH-T03: Multiple adapters invoke correctly for a single contact
- [ ] ENRICH-T04: User-entered data is preserved over conflicting enrichment data
- [ ] ENRICH-T05: Higher-confidence enrichment data wins over lower-confidence data
- [ ] ENRICH-T06: Source attribution is recorded on every enriched data point
- [ ] ENRICH-T07: Manual enrichment shows diff preview before applying
- [ ] ENRICH-T08: Intelligence score updates after enrichment completes
- [ ] ENRICH-T09: Contact detail page reflects enriched data without manual refresh

---

## 5. Enrichment Adapters

**Supports processes:** KP-1 (step 2), KP-2 (step 2). This section defines the pluggable adapter framework and each planned adapter.

### 5.1 Requirements

Each adapter implements a common interface:

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

- [ ] ENRICH-10: Implement pluggable adapter interface
- [ ] ENRICH-11: Implement Apollo adapter
- [ ] ENRICH-12: Implement Clearbit adapter
- [ ] ENRICH-13: Implement People Data Labs adapter
- [ ] ENRICH-14: Implement Google People API adapter (integrated with Google Contacts sync)
- [ ] ENRICH-15: Implement email signature parser adapter
- [ ] ENRICH-16: Implement per-adapter rate limiting

**Tests:**

- [ ] ENRICH-T10: Apollo adapter returns normalized profile data from email input
- [ ] ENRICH-T11: Clearbit adapter returns normalized company + person data
- [ ] ENRICH-T12: Rate-limited adapter is skipped and retried on next cycle
- [ ] ENRICH-T13: New adapter can be registered without pipeline changes
- [ ] ENRICH-T14: Email signature parser extracts name, title, company, phone from signature block

---

## 6. Source Attribution

**Supports processes:** KP-3 (full flow). This section defines how users discover the provenance of enriched data.

### 6.1 Requirements

Every enrichable field on a contact record carries source attribution metadata: the source name, confidence score, timestamp of last update, and whether the value was user-entered or system-enriched.

### 6.2 UI Specifications

- **Hover tooltip:** Hovering over any enrichable field shows a tooltip with source, confidence, and last updated date.
- **Click to expand:** Clicking the tooltip shows the full value history for that field — every value, source, confidence, and timestamp in chronological order.
- **Visual indicator:** Fields populated by enrichment show a subtle enrichment source icon (distinct from user-entered fields) so the user can see at a glance which data came from which source.

**Tasks:**

- [ ] ENRICH-17: Implement source attribution metadata storage on all enrichable fields
- [ ] ENRICH-18: Implement hover tooltip with source, confidence, and timestamp
- [ ] ENRICH-19: Implement click-to-expand field value history
- [ ] ENRICH-20: Implement visual indicator distinguishing enrichment vs. user-entered data

**Tests:**

- [ ] ENRICH-T15: Hover on enriched field shows correct source and confidence
- [ ] ENRICH-T16: Field history shows all values in chronological order
- [ ] ENRICH-T17: User-entered fields show different indicator than enriched fields

---

## 7. Intelligence Items

**Supports processes:** KP-5 (full flow). This section defines the intelligence item data model and user interaction.

### 7.1 Requirements

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

Each intelligence item has: source, category, title, optional summary, optional source URL, confidence score, verification status (unverified, verified, dismissed), and optional expiration date.

Intelligence items appear on the contact's detail page in the intelligence card, sorted by recency. They feed into AI briefing generation and anomaly detection.

**Tasks:**

- [ ] ENRICH-21: Implement intelligence item data model and creation
- [ ] ENRICH-22: Implement manual intelligence item entry UI
- [ ] ENRICH-23: Implement intelligence item display on contact detail page (intelligence card)
- [ ] ENRICH-24: Implement verification workflow (verify/dismiss with status badges)
- [ ] ENRICH-25: Implement show/hide dismissed items toggle

**Tests:**

- [ ] ENRICH-T18: Enrichment creates intelligence item when job change detected
- [ ] ENRICH-T19: Manual intelligence item can be created with custom category
- [ ] ENRICH-T20: Intelligence items display in reverse chronological order
- [ ] ENRICH-T21: Verified items show verification badge
- [ ] ENRICH-T22: Dismissed items are hidden by default, visible with toggle

---

## 8. OSINT Monitors

**Supports processes:** KP-4 (full flow), KP-5 (step 1 trigger). This section defines how users configure and manage monitoring for key contacts.

### 8.1 Requirements

Users can configure monitoring on specific contacts to watch for changes from public sources. Each monitor specifies:

- Which contact or company to monitor
- Which sources to check (LinkedIn, news, SEC filings, domain changes, enrichment refresh)
- Check frequency per source (hourly, daily, weekly)
- Alert categories to trigger on (job change, funding round, news mention, etc.)
- Notification method (in-app, email digest, Slack)

When a monitor detects a change, it creates an intelligence item and dispatches a notification per configuration.

**Business rules:**
- Monitors can be paused, resumed, or deleted.
- Monitor frequency respects source rate limits and terms of service.
- All monitored data comes from publicly available sources only.
- Contacts with active monitors show a "Monitored" badge on the detail page.
- A centralized Monitors dashboard (Settings → Monitors) shows all active monitors across all contacts.

**Performance target:** Monitored contacts have data freshness < 7 days since last check.

**Tasks:**

- [ ] ENRICH-26: Implement OSINT monitor configuration UI (source selection, frequency, categories, notifications)
- [ ] ENRICH-27: Implement scheduled monitor execution at configured frequency
- [ ] ENRICH-28: Implement change detection (compare current data against last known state)
- [ ] ENRICH-29: Implement alert creation and notification dispatch on detected changes
- [ ] ENRICH-30: Implement "Monitored" badge on contact detail page
- [ ] ENRICH-31: Implement centralized Monitors dashboard in Settings
- [ ] ENRICH-32: Implement monitor pause/resume/delete actions

**Tests:**

- [ ] ENRICH-T23: Daily monitor executes within 24 hours of last check
- [ ] ENRICH-T24: Monitor detects job title change and creates intelligence item
- [ ] ENRICH-T25: Monitor triggers notification on configured alert category
- [ ] ENRICH-T26: Paused monitor does not execute
- [ ] ENRICH-T27: "Monitored" badge appears on contacts with active monitors
- [ ] ENRICH-T28: Monitors dashboard shows all active monitors with status

---

## 9. Intelligence Score Computation

**Supports processes:** KP-1 (step 6), KP-2 (step 5), KP-6 (full flow). This section defines the intelligence score formula and its user-facing breakdown.

### 9.1 Requirements

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

### 9.2 UI Specifications

- **Score display:** Visual indicator (circular progress or bar) on the contact detail page header.
- **Score breakdown panel:** Clicking the score shows each category with its contribution. Filled categories in green, missing in gray.
- **Actionable gaps:** Missing categories include action links (e.g., "Phone: missing — [Enrich to find]" or "Social profiles: missing — [Add manually]").

**Tasks:**

- [ ] ENRICH-33: Implement intelligence score computation with weighted categories
- [ ] ENRICH-34: Implement score recomputation triggers (enrichment, merge, daily schedule)
- [ ] ENRICH-35: Implement score display indicator on contact detail page
- [ ] ENRICH-36: Implement score breakdown panel with category contributions
- [ ] ENRICH-37: Implement actionable gap links in score breakdown

**Tests:**

- [ ] ENRICH-T29: Contact with all data populated scores 1.0
- [ ] ENRICH-T30: Contact with only email scores 0.15
- [ ] ENRICH-T31: Score updates after enrichment adds new data
- [ ] ENRICH-T32: Score updates after merge combines data from two contacts
- [ ] ENRICH-T33: Score breakdown shows correct category contributions
- [ ] ENRICH-T34: Gap links navigate to correct actions (enrich, add manually)
