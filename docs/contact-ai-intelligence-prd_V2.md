# Contact — AI Contact Intelligence Sub-PRD

**Version:** 2.0
**Last Updated:** 2026-02-22
**Status:** Draft
**Entity Base PRD:** [contact-entity-base-prd_V7.md]
**Referenced Entity PRDs:** [Communications PRD](communications-prd_V3.md), [Conversations PRD](conversations-prd_V4.md)

> **V2.0 (2026-02-22):** Added Key Processes section defining end-to-end user experiences for all AI intelligence scenarios. Restructured functional sections with process linkage.

---

## 1. Overview

### 1.1 Purpose

AI Contact Intelligence provides the insight layer that derives meaning from contact data, communication patterns, and external intelligence. These are the features that make CRMExtender proactively intelligent rather than a passive data store — briefing users before meetings, alerting them to engagement drops, suggesting tags and actions, and enabling natural language search across their contact network.

This sub-PRD covers: contact briefings, AI-suggested actions, AI-suggested tags, natural language search, anomaly detection, and behavioral signal tracking including engagement score computation.

### 1.2 Preconditions

- Contact exists with profile data and/or communication history.
- AI service (Claude API) is accessible for briefing generation, NL search, and tag suggestion.
- Communication data exists for behavioral signal computation.

---

## 2. Context

### 2.1 Relevant Fields

| Field | Usage in This Action |
|---|---|
| All contact profile fields | Input for briefing generation |
| Engagement Score | Output of behavioral signal computation |
| Intelligence Score | Input for briefing (data completeness context) |
| Tags | AI suggests new tags; existing tags provide context |
| Lead Status | Context for action suggestions |

### 2.2 Relevant Relationships

- **Communications** — Primary source for behavioral signals. Email frequency, response times, sentiment, thread depth.
- **Conversations** — Cross-channel engagement context for briefings and anomaly detection.
- **Company** — Employment context for briefings and tag suggestions.
- **Contact-to-Contact Relationships** — Mutual connections and introduction context for briefings.
- **Deals** — Deal context for action suggestions (open action items, deal stage changes).
- **Events** — Calendar context for meeting prep briefings.

### 2.3 Relevant Lifecycle Transitions

None directly. AI intelligence features operate on active contacts and do not trigger lifecycle transitions.

---

## 3. Key Processes

### KP-1: Getting Briefed Before a Meeting

**Trigger:** The user has an upcoming meeting with a contact and wants to prepare.

**Step 1 — Pre-meeting notification:** If the user has a calendar event with a contact, the system surfaces an AI-suggested action (see KP-3): "You have a meeting with [Name] tomorrow. [View Briefing]." This appears in the suggestions section on the dashboard or as an in-app notification.

**Step 2 — Navigate to contact:** The user clicks the notification or navigates to the contact's detail page directly.

**Step 3 — Request briefing:** The user clicks "Brief Me" in the action bar. A briefing panel opens with a loading indicator.

**Step 4 — Briefing display:** Within 5 seconds, the AI-generated briefing appears as a concise paragraph covering: who the person is (role, company), the state of the relationship (engagement score, trend), recent interactions (last communication, open items), notable intelligence (job changes, company news), and relevant relationship context (mutual connections, warm intro history).

**Step 5 — Cached result:** If the user revisits the briefing within 24 hours and no new data has arrived, the cached version loads instantly. A "Refresh" button is available to force regeneration.

### KP-2: Discovering Engagement Trends

**Trigger:** The user wants to understand the health of their relationship with a contact.

**Step 1 — Engagement score visibility:** On the contact list view, each contact row shows the engagement score as a visual indicator (colored dot or bar). High engagement contacts are green, declining are amber, low/stale are red.

**Step 2 — Detail page engagement card:** On the contact detail page, the engagement score is displayed with a trend indicator (↑ improving, → stable, ↓ declining) and the score value (0.0–1.0).

**Step 3 — Score breakdown:** Clicking the engagement score opens a breakdown panel showing the five components: frequency (0.30 weight), recency (0.25), reciprocity (0.20), depth (0.15), and channel diversity (0.10). Each shows its current value and contribution.

**Step 4 — Historical trend:** The panel includes a small sparkline chart showing the engagement score over the last 90 days, making trends visible at a glance.

**Step 5 — Behavioral details:** Below the breakdown, the panel shows specific metrics: average response time, response rate, last bidirectional communication date, communication channels used, and the "best time to contact" (mode of historical interaction timestamps).

### KP-3: Receiving and Acting on AI-Suggested Actions

**Trigger:** The daily computation cycle detects conditions that warrant proactive suggestions.

**Step 1 — Suggestion generation:** During the daily engagement score computation, the system evaluates trigger conditions for each contact and generates suggestions where applicable.

**Step 2 — Suggestion visibility:** Suggestions appear in two locations:
- **Contact detail page:** A "Suggestions" section in the intelligence card shows suggestions specific to that contact.
- **Dashboard:** A "Suggested Actions" widget shows the highest-priority suggestions across all contacts.

**Step 3 — Suggestion content:** Each suggestion shows: an icon indicating the type (re-engage, congratulate, prepare, follow up, introduce), the suggestion text (e.g., "You haven't heard from Sarah in 5 weeks. Consider reaching out."), and action buttons relevant to the suggestion type (e.g., "Compose Email," "View Briefing," "Dismiss").

**Step 4 — Acting on a suggestion:** The user clicks an action button. "Compose Email" opens a pre-addressed email draft. "View Briefing" opens the briefing panel. "Dismiss" removes the suggestion.

**Step 5 — Suggestion preferences:** In Settings → AI Intelligence, the user can enable or disable specific suggestion types. Disabled types are not generated.

### KP-4: Reviewing AI-Suggested Tags

**Trigger:** The daily computation cycle identifies tags that may apply to a contact based on patterns.

**Step 1 — Suggested tag appearance:** On the contact detail page, the tags card shows AI-suggested tags alongside existing tags. Suggested tags have a visually distinct style (dashed border, "Suggested" label) and a confidence score.

**Step 2 — Accept:** The user clicks a checkmark on a suggested tag. The tag is promoted to a confirmed tag (source changes to `manual`, confidence to 1.0, dashed border becomes solid). The suggestion is consumed.

**Step 3 — Dismiss:** The user clicks "×" on a suggested tag. The suggestion is permanently dismissed — the same tag will not be re-suggested for this contact.

**Step 4 — Bulk suggestions:** On the dashboard or in a dedicated AI Suggestions view, the user can see all pending tag suggestions across contacts. They can accept or dismiss in bulk.

### KP-5: Searching Contacts with Natural Language

**Trigger:** The user wants to find contacts using a descriptive query rather than structured filters.

**Step 1 — NL search input:** On the contacts list view, the search box accepts natural language. The user types a query like "founders at Series A companies in healthcare" or "people I haven't emailed in 3 months."

**Step 2 — Query interpretation:** The system sends the query to the AI, which translates it into structured filters and/or a graph query. A brief interpretation line appears below the search box: "Searching for: title contains 'founder' AND industry = 'healthcare' AND funding_stage = 'series_a'."

**Step 3 — Results:** The contact list updates to show matching contacts. If the query implied a graph traversal (e.g., "who introduced me to Sarah Chen?"), the results include relationship path information.

**Step 4 — Refinement:** The user can edit the interpreted filters directly (as standard filter chips) or refine their natural language query. The interpretation updates in real-time.

**Step 5 — Fallback:** If the AI cannot parse the query into structured filters, it falls back to full-text search. The interpretation line shows: "Showing full-text search results for: [query]."

### KP-6: Noticing and Investigating Anomalies

**Trigger:** The user sees an attention signal on a contact indicating unusual behavior.

**Step 1 — Attention signal visibility:** On the contact list view, contacts with active anomalies show an attention indicator (e.g., amber alert icon). On the detail page, an attention banner appears at the top.

**Step 2 — Anomaly detail:** Clicking the indicator or banner opens an explanation: "Unusual pattern detected: [Name] typically responds within 24 hours but hasn't responded to your last 3 emails over 2 weeks. This is a significant deviation from baseline." The explanation includes the baseline period, the deviation, and when it was detected.

**Step 3 — Contextual actions:** The anomaly panel suggests relevant actions: "View recent communications," "Check intelligence items for context," "Send a follow-up." These link to the relevant sections.

**Step 4 — Resolve:** The anomaly resolves automatically when the pattern returns to baseline (e.g., the contact responds). The attention signal disappears. The anomaly is recorded in the contact's activity timeline as a historical note.

---

## 4. Contact Briefings

**Supports processes:** KP-1 (steps 3–5).

### 4.1 Requirements

On-demand AI-generated summary synthesizing all available data about a contact. Triggered by the user via "Brief Me" on the contact detail page, or automatically surfaced before a scheduled meeting.

**Input context sent to AI:**
- Contact profile (name, title, company, social profiles)
- Employment history
- Recent communication summary (last 10 conversations, summarized)
- Relationship context (key connections, mutual contacts)
- Intelligence items (last 5 items)
- Engagement metrics (score, trend, responsiveness)

**Output:** A concise one-paragraph briefing that synthesizes the above into actionable context.

**Business rules:**
- Briefings are cached with a 24-hour TTL.
- Cache is invalidated when new communication events or intelligence items are created for the contact.
- Briefing generation completes within 5 seconds.

**Tasks:**

- [ ] AIINT-01: Implement briefing context assembly (profile, history, communications, relationships, intelligence)
- [ ] AIINT-02: Implement AI briefing generation via Claude API
- [ ] AIINT-03: Implement briefing caching with 24-hour TTL
- [ ] AIINT-04: Implement cache invalidation on new communications or intelligence items
- [ ] AIINT-05: Implement "Brief Me" action and briefing panel on contact detail page
- [ ] AIINT-06: Implement automatic pre-meeting briefing suggestion trigger

**Tests:**

- [ ] AIINT-T01: Briefing generates within 5 seconds for a contact with full data
- [ ] AIINT-T02: Briefing includes employment, communication, and intelligence context
- [ ] AIINT-T03: Cached briefing returns instantly on second request
- [ ] AIINT-T04: New communication for contact invalidates cached briefing
- [ ] AIINT-T05: Briefing generates gracefully for contacts with minimal data (just name + email)

---

## 5. AI-Suggested Actions

**Supports processes:** KP-3 (full flow), KP-1 (step 1 pre-meeting notification).

### 5.1 Requirements

The AI proactively suggests actions based on contact analysis:

| Trigger | Suggested Action | Action Buttons |
|---|---|---|
| Engagement declining 30+ days | "You haven't heard from [name] in [N] weeks." | Compose Email, Dismiss |
| Job change detected | "[Name] moved to [company]. Send congrats." | Compose Email, View Intelligence, Dismiss |
| Upcoming meeting | "Meeting with [name] tomorrow." | View Briefing, Dismiss |
| Open action items aging | "[N] open items with [name] from [N] weeks ago." | View Items, Dismiss |
| Warm intro opportunity | "[Name] knows [target] — worked together at [company]." | View Path, Dismiss |
| Stale enrichment data | "[Name]'s profile hasn't been updated in [N] months." | Enrich, Dismiss |

**Business rules:**
- Suggestions are generated during the daily engagement score computation cycle.
- Each suggestion type can be enabled or disabled per user in Settings → AI Intelligence.
- Dismissed suggestions do not reappear.
- Suggestions appear on both the contact detail page and the dashboard.

**Tasks:**

- [ ] AIINT-07: Implement action suggestion engine with trigger detection for all types
- [ ] AIINT-08: Implement suggestion display on contact detail page (intelligence card)
- [ ] AIINT-09: Implement suggestion display on dashboard (Suggested Actions widget)
- [ ] AIINT-10: Implement per-user suggestion type preferences (enable/disable)
- [ ] AIINT-11: Implement suggestion action buttons (Compose Email, View Briefing, etc.)
- [ ] AIINT-12: Implement dismiss action with no-reappear logic

**Tests:**

- [ ] AIINT-T06: Declining engagement (30+ days) triggers re-engagement suggestion
- [ ] AIINT-T07: Detected job change triggers congratulations suggestion
- [ ] AIINT-T08: Upcoming calendar event triggers pre-meeting briefing suggestion
- [ ] AIINT-T09: Disabled suggestion type does not appear for that user
- [ ] AIINT-T10: Dismissed suggestion does not reappear

---

## 6. AI-Suggested Tags

**Supports processes:** KP-4 (full flow).

### 6.1 Requirements

The AI analyzes contacts and suggests tags based on patterns:

- **Communication content analysis** — Topics discussed, terminology used in emails and conversations.
- **Title and role pattern matching** — Identifying decision makers, technical roles, executives.
- **Company industry and size** — Industry tags inferred from company data.
- **Engagement patterns** — Relationship tags like VIP, Dormant, New Connection, Frequent Collaborator.
- **Similarity to tagged contacts** — If a contact's profile closely matches others with a specific tag, suggest that tag.

Suggested tags appear with a distinct visual style and confidence score. Only suggestions above a minimum threshold (configurable, default 0.60) are shown.

**Business rules:**
- Users can define custom tag suggestion rules (e.g., "Tag anyone at companies with 500+ employees as 'Enterprise'").
- Tag suggestions are generated during the daily computation cycle.
- Dismissed suggestions are permanently excluded for that contact-tag pair.

**Tasks:**

- [ ] AIINT-13: Implement AI tag suggestion engine (communication analysis, role matching, engagement patterns)
- [ ] AIINT-14: Implement custom tag suggestion rules (user-defined criteria)
- [ ] AIINT-15: Implement suggested tag display with distinct visual style on contact detail page
- [ ] AIINT-16: Implement accept action (promote to confirmed, source=manual, confidence=1.0)
- [ ] AIINT-17: Implement dismiss action with permanent exclusion
- [ ] AIINT-18: Implement bulk tag suggestion review view

**Tests:**

- [ ] AIINT-T11: Contact with "CEO" title gets "Decision Maker" tag suggestion
- [ ] AIINT-T12: Contact at 1000+ employee company gets "Enterprise" tag from custom rule
- [ ] AIINT-T13: Dismissed tag suggestion does not reappear
- [ ] AIINT-T14: Accepted suggestion changes source to manual and confidence to 1.0
- [ ] AIINT-T15: Suggestions below confidence threshold are not shown

---

## 7. Natural Language Search

**Supports processes:** KP-5 (full flow).

### 7.1 Requirements

Users can search contacts using natural language queries. The AI translates the query into structured filters, full-text search, and/or graph queries.

| Natural Language | Translated To |
|---|---|
| "founders at Series A companies in healthcare" | title contains 'founder' AND industry = 'healthcare' AND funding_stage = 'series_a' |
| "people I haven't emailed in 3 months" | last_communication < 90 days ago AND has_communication = true |
| "VIP contacts at companies with 500+ employees" | tags contains 'VIP' AND company_size in ('501-1000', '1001-5000', '5001+') |
| "who introduced me to Sarah Chen?" | Graph query for INTRODUCED_BY relationships to target contact |

**Business rules:**
- The AI receives the query, contact schema, and available filter fields. It returns structured filter JSON.
- If the query implies graph traversal, the AI generates a graph query.
- Results include a brief interpretation of how the query was parsed.
- Interpreted filters are editable as standard filter chips.
- If unparseable, the system falls back to full-text search with an explanation.

**Tasks:**

- [ ] AIINT-19: Implement NL query parsing via Claude API (query → structured filter JSON)
- [ ] AIINT-20: Implement graph query generation for relationship-based queries
- [ ] AIINT-21: Implement query interpretation display below search box
- [ ] AIINT-22: Implement editable filter chips from interpreted query
- [ ] AIINT-23: Implement fallback to full-text search on unparseable queries

**Tests:**

- [ ] AIINT-T16: "founders in healthcare" translates to title + industry filter
- [ ] AIINT-T17: "people I haven't emailed in 3 months" translates to time-based communication filter
- [ ] AIINT-T18: "who introduced me to [name]" generates graph query
- [ ] AIINT-T19: Unparseable query falls back to full-text search with explanation
- [ ] AIINT-T20: Interpreted filter chips are editable by the user

---

## 8. Behavioral Signal Tracking

**Supports processes:** KP-2 (step 5 behavioral details), KP-6 (step 2 baseline). This section defines the signal sources that power engagement scoring and anomaly detection.

### 8.1 Requirements

Behavioral signals are derived from communication activity, calendar events, and in-app interactions:

| Source | Signals Extracted | Update Frequency |
|---|---|---|
| **Email** | Send/receive frequency, response time, response rate, thread depth, sentiment | On each email sync |
| **Calendar** | Meeting frequency, cancellation rate, duration trends, no-shows | On each calendar sync |
| **Phone/SMS** | Call frequency, call duration, missed calls, response patterns | On each communication sync |
| **In-app activity** | Notes added, profile views, deal stage changes, searches for contact | Real-time event tracking |
| **External** | Form fills, website visits (opt-in tracking pixel) | Webhook/polling |

**Computed engagement metrics:**

| Metric | Description |
|---|---|
| **Engagement score** | Weighted composite (0.0–1.0) of frequency, recency, reciprocity, depth, and channel diversity |
| **Responsiveness index** | Average response time × response rate |
| **Sentiment trend** | Rolling 30-day AI-analyzed sentiment (positive, neutral, negative, declining) |
| **Attention signal** | Statistical deviation from baseline engagement |
| **Best time to contact** | Mode of historical interaction timestamps (day-of-week + hour) |
| **Stale contact alert** | Days since last bidirectional communication exceeds threshold |

**Tasks:**

- [ ] AIINT-24: Implement behavioral signal extraction from email sync events
- [ ] AIINT-25: Implement behavioral signal extraction from calendar events
- [ ] AIINT-26: Implement behavioral signal extraction from phone/SMS communication events
- [ ] AIINT-27: Implement in-app activity signal tracking
- [ ] AIINT-28: Implement "best time to contact" computation

**Tests:**

- [ ] AIINT-T21: Email sync updates frequency and recency signals for affected contacts
- [ ] AIINT-T22: Calendar sync updates meeting frequency signals
- [ ] AIINT-T23: In-app profile view is tracked as a signal
- [ ] AIINT-T24: "Best time to contact" reflects most common interaction hour

---

## 9. Engagement Score Computation

**Supports processes:** KP-2 (steps 2–4).

### 9.1 Requirements

The engagement score (0.0–1.0) is a weighted composite:

| Component | Weight | Description |
|---|---|---|
| Frequency score | 0.30 | Normalized communication count over 90-day window |
| Recency score | 0.25 | Exponential decay from last interaction |
| Reciprocity score | 0.20 | Bidirectional balance (0 = one-sided, 1 = balanced) |
| Depth score | 0.15 | Average thread depth / call duration |
| Channel diversity | 0.10 | Number of distinct channels used (max 1.0 at 3+ channels) |

**Recomputation:** Daily scheduled job processes communication events from the last 24 hours and recalculates engagement scores for affected contacts.

### 9.2 UI Specifications

- **List view indicator:** Colored dot or small bar. Green (≥ 0.6), amber (0.3–0.59), red (< 0.3).
- **Detail page display:** Score value with trend arrow (↑ ↓ →).
- **Breakdown panel:** Clickable score opens panel with five component bars and a 90-day sparkline chart.
- **Historical trend:** Sparkline shows engagement over 90 days.

**Tasks:**

- [ ] AIINT-29: Implement engagement score computation with weighted components
- [ ] AIINT-30: Implement daily scheduled recomputation job
- [ ] AIINT-31: Implement engagement score persistence on contact record
- [ ] AIINT-32: Implement list view engagement indicator (colored dot/bar)
- [ ] AIINT-33: Implement detail page score display with trend arrow
- [ ] AIINT-34: Implement score breakdown panel with component bars and sparkline

**Tests:**

- [ ] AIINT-T25: Contact with daily bidirectional email scores high engagement
- [ ] AIINT-T26: Contact with no communication in 90 days scores near 0.0
- [ ] AIINT-T27: Multi-channel contact (email + phone + meetings) scores higher than single-channel
- [ ] AIINT-T28: Daily job processes only contacts with new communication events
- [ ] AIINT-T29: Engagement score reflects recency decay
- [ ] AIINT-T30: List view colors correctly map to score ranges

---

## 10. Anomaly Detection

**Supports processes:** KP-6 (full flow).

### 10.1 Requirements

The system monitors engagement patterns and alerts on statistical deviations from baseline:

- **Sudden drop** — A contact who normally responds within 24 hours hasn't responded in a week.
- **Sudden spike** — A normally low-engagement contact suddenly sends multiple emails.
- **Sentiment shift** — Communication sentiment shifts from positive to negative.
- **Pattern break** — A contact who met weekly suddenly cancels multiple meetings.

Anomalies are surfaced as attention signals on the contact detail page and list view, with optional notifications.

**Business rules:**
- Baseline behavior requires at least 30 days of communication history to establish.
- Anomaly sensitivity is configurable per tenant.
- Anomalies are computed during the daily engagement score job.
- Anomalies auto-resolve when the pattern returns to baseline. Resolved anomalies appear in the activity timeline as historical notes.

### 10.2 UI Specifications

- **List view:** Amber alert icon on contacts with active anomalies.
- **Detail page:** Attention banner at the top with explanation text and contextual action links.
- **Anomaly panel:** Clickable banner opens detailed explanation with baseline data, deviation specifics, and suggested actions.

**Tasks:**

- [ ] AIINT-35: Implement baseline behavior computation (rolling 90-day window)
- [ ] AIINT-36: Implement deviation detection (response time, frequency, sentiment)
- [ ] AIINT-37: Implement attention signal display on list view and detail page
- [ ] AIINT-38: Implement anomaly detail panel with explanation and suggested actions
- [ ] AIINT-39: Implement auto-resolution when pattern returns to baseline
- [ ] AIINT-40: Implement anomaly notification delivery

**Tests:**

- [ ] AIINT-T31: Contact with established baseline triggers alert on 3x response time increase
- [ ] AIINT-T32: Contact with < 30 days history does not trigger false anomalies
- [ ] AIINT-T33: Sentiment shift from positive to negative triggers alert
- [ ] AIINT-T34: Anomaly sensitivity setting affects detection threshold
- [ ] AIINT-T35: Anomaly auto-resolves when pattern normalizes
- [ ] AIINT-T36: Resolved anomaly appears in activity timeline
