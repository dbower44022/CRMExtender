# Contact — AI Contact Intelligence Sub-PRD

**Version:** 1.0
**Last Updated:** 2026-02-22
**Status:** Draft
**Entity Base PRD:** [contact-entity-base-prd.md]
**Referenced Entity PRDs:** [Communications PRD](communications-prd_V3.md), [Conversations PRD](conversations-prd_V4.md)

---

## 1. Overview

### 1.1 Purpose

AI Contact Intelligence provides insight layer features that derive meaning from contact data, communication patterns, and external intelligence. These are the features that make CRMExtender proactively intelligent rather than a passive data store — briefing users before meetings, alerting them to engagement drops, suggesting tags and actions, and enabling natural language search across their contact network.

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

## 3. Contact Briefings

### 3.1 Requirements

On-demand AI-generated summary synthesizing all available data about a contact. Triggered by the user via a "Brief Me" action on the contact detail page, or automatically before a scheduled meeting.

**Input context sent to AI:**
- Contact profile (name, title, company, social profiles)
- Employment history
- Recent communication summary (last 10 conversations, summarized)
- Relationship context (key connections, mutual contacts)
- Intelligence items (last 5 items)
- Engagement metrics (score, trend, responsiveness)

**Output:** A concise one-paragraph briefing that synthesizes the above into actionable context. The briefing should cover who the person is, their current role and company, the state of the user's relationship with them, recent interactions, any notable intelligence items, and relevant context for an upcoming interaction.

**Business rules:**
- Briefings are cached with a 24-hour TTL.
- Cache is invalidated when new communication events or intelligence items are created for the contact.
- User can manually refresh a briefing on demand.
- Briefing generation completes within 5 seconds.

**User story:** As a user, I want an AI-generated one-paragraph briefing on any contact that synthesizes all available data — profile, communication history, relationship context, recent intelligence.

**Tasks:**

- [ ] AIINT-01: Implement briefing context assembly (profile, history, communications, relationships, intelligence)
- [ ] AIINT-02: Implement AI briefing generation via Claude API
- [ ] AIINT-03: Implement briefing caching with 24-hour TTL
- [ ] AIINT-04: Implement cache invalidation on new communications or intelligence items
- [ ] AIINT-05: Implement "Brief Me" action on contact detail page
- [ ] AIINT-06: Implement automatic pre-meeting briefing trigger

**Tests:**

- [ ] AIINT-T01: Briefing generates within 5 seconds for a contact with full data
- [ ] AIINT-T02: Briefing includes employment, communication, and intelligence context
- [ ] AIINT-T03: Cached briefing returns instantly on second request
- [ ] AIINT-T04: New communication for contact invalidates cached briefing
- [ ] AIINT-T05: Briefing generates gracefully for contacts with minimal data (just name + email)

---

## 4. AI-Suggested Actions

### 4.1 Requirements

Based on contact analysis, the AI proactively suggests actions the user should consider:

| Trigger | Suggested Action |
|---|---|
| Engagement declining for 30+ days | "You haven't heard from [name] in [N] weeks. Consider reaching out." |
| Job change detected | "[Name] just moved to [company]. Send a congratulations note." |
| Upcoming meeting with contact | "You have a meeting with [name] tomorrow. Here's a briefing." |
| Open action items aging | "You have [N] open action items with [name] from [N] weeks ago." |
| Warm intro opportunity detected | "[Name] knows [target] at [company] — they worked together at [previous company]." |
| Stale enrichment data | "[Name]'s profile hasn't been updated in [N] months. Re-enrich?" |

**Business rules:**
- Suggestions are non-intrusive — displayed in a suggestions section on the contact detail page and optionally as in-app notifications.
- Each suggestion type can be enabled or disabled per user.
- Suggestions are generated during the daily engagement score computation cycle, not in real-time.

**Tasks:**

- [ ] AIINT-07: Implement action suggestion engine with trigger detection
- [ ] AIINT-08: Implement suggestion display on contact detail page
- [ ] AIINT-09: Implement per-user suggestion type preferences (enable/disable)
- [ ] AIINT-10: Implement notification delivery for high-priority suggestions

**Tests:**

- [ ] AIINT-T06: Declining engagement (30+ days no communication) triggers re-engagement suggestion
- [ ] AIINT-T07: Detected job change triggers congratulations suggestion
- [ ] AIINT-T08: Upcoming calendar event with contact triggers pre-meeting briefing suggestion
- [ ] AIINT-T09: Disabled suggestion type does not appear for that user

---

## 5. AI-Suggested Tags

### 5.1 Requirements

The AI analyzes contacts and suggests tags based on patterns across multiple data sources:

- **Communication content analysis** — Topics discussed, terminology used in emails and conversations.
- **Title and role pattern matching** — Identifying decision makers, technical roles, executives, legal, finance.
- **Company industry and size** — Industry tags inferred from company data (e.g., "Enterprise" for companies with 500+ employees).
- **Engagement patterns** — Relationship tags like VIP, Dormant, New Connection, Frequent Collaborator based on engagement signals.
- **Similarity to tagged contacts** — If a contact's profile closely matches others with a specific tag, suggest that tag.

Suggested tags appear with a "suggested" badge and confidence score. Users can accept (promoting to `source=manual` with `confidence=1.0`) or dismiss. Dismissed suggestions are not re-suggested.

**Business rules:**
- Users can define custom tag suggestion rules (e.g., "Tag anyone at companies with 500+ employees as 'Enterprise'").
- Tag suggestions are generated during the daily computation cycle.
- Each suggestion carries a confidence score; only suggestions above a minimum threshold (configurable, default 0.60) are shown.

**User story:** As a user, I want the system to suggest relevant tags for my contacts based on their profile and our interaction patterns.

**Tasks:**

- [ ] AIINT-11: Implement AI tag suggestion engine (communication analysis, role matching, engagement patterns)
- [ ] AIINT-12: Implement custom tag suggestion rules (user-defined criteria)
- [ ] AIINT-13: Implement suggested tag display with accept/dismiss actions
- [ ] AIINT-14: Implement dismissed suggestion tracking (do not re-suggest)

**Tests:**

- [ ] AIINT-T10: Contact with "CEO" title gets "Decision Maker" tag suggestion
- [ ] AIINT-T11: Contact at 1000+ employee company gets "Enterprise" tag from custom rule
- [ ] AIINT-T12: Dismissed tag suggestion does not reappear
- [ ] AIINT-T13: Accepted suggestion changes source to manual and confidence to 1.0

---

## 6. Natural Language Search

### 6.1 Requirements

Users can search contacts using natural language queries. The AI translates the query into a combination of structured filters, full-text search, and graph queries:

| Natural Language | Translated To |
|---|---|
| "founders at Series A companies in healthcare" | title contains 'founder' AND industry = 'healthcare' AND funding_stage = 'series_a' |
| "people I haven't emailed in 3 months" | last_communication < 90 days ago AND has_communication = true |
| "VIP contacts at companies with 500+ employees" | tags contains 'VIP' AND company_size in ('501-1000', '1001-5000', '5001+') |
| "who introduced me to Sarah Chen?" | Graph query for INTRODUCED_BY relationships to target contact |

**Business rules:**
- The AI receives the query, the contact schema, and the available filter fields. It returns a structured filter JSON.
- If the query implies a graph traversal (introductions, connections, paths), the AI generates a graph query.
- Results include a brief explanation of how the query was interpreted.
- If the AI cannot interpret the query, it falls back to full-text search.

**User story:** As a user, I want to use natural language to search my contacts, so I can find people based on relationships and patterns, not just fields.

**Tasks:**

- [ ] AIINT-15: Implement NL query parsing via Claude API (query → structured filter JSON)
- [ ] AIINT-16: Implement graph query generation for relationship-based queries
- [ ] AIINT-17: Implement query interpretation explanation in results
- [ ] AIINT-18: Implement fallback to full-text search on unparseable queries

**Tests:**

- [ ] AIINT-T14: "founders in healthcare" translates to title + industry filter
- [ ] AIINT-T15: "people I haven't emailed in 3 months" translates to time-based communication filter
- [ ] AIINT-T16: "who introduced me to [name]" generates graph query
- [ ] AIINT-T17: Unparseable query falls back to full-text search

---

## 7. Behavioral Signal Tracking

### 7.1 Requirements

Behavioral signals are derived from communication activity, calendar events, and in-app interactions. They power the engagement score and feed into AI features (briefings, action suggestions, anomaly detection).

**Signal sources:**

| Source | Signals Extracted | Update Frequency |
|---|---|---|
| **Email** | Send/receive frequency, response time, response rate, thread depth, sentiment | On each email sync |
| **Calendar** | Meeting frequency, cancellation rate, meeting duration trends, no-shows | On each calendar sync |
| **Phone/SMS** | Call frequency, call duration, missed calls, response patterns | On each communication sync |
| **In-app activity** | Notes added, profile views, deal stage changes, searches for contact | Real-time event tracking |
| **External** | Form fills, website visits (opt-in tracking pixel) | Webhook/polling |

**Computed engagement metrics:**

| Metric | Description |
|---|---|
| **Engagement score** | Weighted composite of frequency, recency, reciprocity, depth, and channel diversity (0.0–1.0) |
| **Responsiveness index** | Average response time × response rate — how quickly and reliably the contact responds |
| **Sentiment trend** | Rolling 30-day window of AI-analyzed sentiment across communications (positive, neutral, negative, declining) |
| **Attention signal** | Statistical deviation from baseline engagement — alerts on sudden increases or decreases |
| **Best time to contact** | Mode of historical interaction timestamps (day-of-week + hour) — optimal outreach window |
| **Stale contact alert** | Days since last bidirectional communication exceeds threshold — relationship at risk |

**Tasks:**

- [ ] AIINT-19: Implement behavioral signal extraction from email sync events
- [ ] AIINT-20: Implement behavioral signal extraction from calendar events
- [ ] AIINT-21: Implement behavioral signal extraction from phone/SMS communication events
- [ ] AIINT-22: Implement in-app activity signal tracking

**Tests:**

- [ ] AIINT-T18: Email sync updates frequency and recency signals for affected contacts
- [ ] AIINT-T19: Calendar sync updates meeting frequency signals
- [ ] AIINT-T20: In-app profile view is tracked as a signal

---

## 8. Engagement Score Computation

### 8.1 Requirements

The engagement score (0.0–1.0) is a weighted composite reflecting the health and recency of the relationship:

| Component | Weight | Description |
|---|---|---|
| Frequency score | 0.30 | Normalized communication count over 90-day window |
| Recency score | 0.25 | Exponential decay from last interaction |
| Reciprocity score | 0.20 | Bidirectional balance (0 = one-sided, 1 = balanced) |
| Depth score | 0.15 | Average thread depth / call duration |
| Channel diversity | 0.10 | Number of distinct channels used (max 1.0 at 3+ channels) |

**Recomputation:** Daily scheduled job processes the last 24 hours of communication events and recalculates engagement scores for affected contacts. Scores are persisted on the contact record.

**Tasks:**

- [ ] AIINT-23: Implement engagement score computation with weighted components
- [ ] AIINT-24: Implement daily scheduled recomputation job
- [ ] AIINT-25: Implement engagement score persistence on contact record

**Tests:**

- [ ] AIINT-T21: Contact with daily bidirectional email scores high engagement
- [ ] AIINT-T22: Contact with no communication in 90 days scores near 0.0
- [ ] AIINT-T23: Multi-channel contact (email + phone + meetings) scores higher than single-channel
- [ ] AIINT-T24: Daily job processes only contacts with new communication events
- [ ] AIINT-T25: Engagement score reflects recency decay (recent interactions weighted higher)

---

## 9. Anomaly Detection

### 9.1 Requirements

The system monitors engagement patterns and alerts on statistical deviations from baseline behavior:

- **Sudden drop** — A contact who normally responds within 24 hours hasn't responded in a week.
- **Sudden spike** — A normally low-engagement contact suddenly sends multiple emails.
- **Sentiment shift** — Communication sentiment shifts from positive to negative over a rolling window.
- **Pattern break** — A contact who met weekly suddenly cancels multiple meetings.

Anomalies are surfaced as attention signals on the contact detail page and optionally as notifications.

**Business rules:**
- Baseline behavior requires at least 30 days of communication history to establish.
- Anomaly sensitivity is configurable per tenant.
- Anomalies are computed during the daily engagement score job.

**Tasks:**

- [ ] AIINT-26: Implement baseline behavior computation (rolling 90-day window)
- [ ] AIINT-27: Implement deviation detection (response time, frequency, sentiment)
- [ ] AIINT-28: Implement attention signal display on contact detail page
- [ ] AIINT-29: Implement anomaly notification delivery

**Tests:**

- [ ] AIINT-T26: Contact with established baseline triggers alert on 3x response time increase
- [ ] AIINT-T27: Contact with < 30 days history does not trigger false anomalies
- [ ] AIINT-T28: Sentiment shift from positive to negative triggers alert
- [ ] AIINT-T29: Anomaly sensitivity setting affects detection threshold
