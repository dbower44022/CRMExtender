# Conversation — Views & User-Defined Alerts Sub-PRD

**Version:** 1.0
**Last Updated:** 2026-02-23
**Status:** Draft
**Entity Base PRD:** [conversation-entity-base-prd.md]
**Referenced Entity PRDs:** [views-grid-prd.md] (view framework)

---

## 1. Overview

### 1.1 Purpose

This sub-PRD defines how users discover, monitor, and receive notifications about Conversations. Conversation views operate through the Views & Grid PRD framework, with all Conversation fields available for filtering, sorting, and display. User-defined alerts extend views with push triggers — no default alerts ship, preventing alert fatigue.

### 1.2 Preconditions

- Conversation entity is registered with full field registry.
- Views & Grid framework is operational.
- For alerts: notification delivery infrastructure available.

---

## 2. Context

### 2.1 Relevant Fields

All Conversation fields from the field registry are available for view construction:

| Field | Common View Usage |
|---|---|
| is_aggregate | Filter aggregate vs. standard conversations |
| system_status | Filter active/stale/closed |
| ai_status | Filter open/closed/uncertain |
| ai_action_items | Search for specific action items |
| ai_confidence | Filter by assignment confidence |
| last_activity_at | Sort by recency |
| communication_count | Filter by conversation volume |
| Relation Type targets | Filter by associated Project, Company, Contact, Event |

### 2.2 Cross-Entity Context

- **Views & Grid PRD:** Provides the framework for all view operations (filtering, sorting, grouping, inline editing, column configuration). This sub-PRD defines Conversation-specific view patterns.
- **AI Intelligence & Review Sub-PRD:** AI fields (ai_status, ai_summary, ai_action_items, ai_confidence) are primary view/filter targets.
- **Communication Entity Base PRD:** Communication-level views (unassigned items, all communications with a contact) complement conversation-level views.

---

## 3. Key Processes

### KP-1: Creating a Conversation View

**Trigger:** User creates a new view for conversations.

**Step 1 — Column selection:** User selects which fields appear as columns.

**Step 2 — Filter configuration:** User sets filter criteria (system_status, ai_status, entity associations, date ranges, etc.).

**Step 3 — Sort and group:** User configures sort order and optional grouping (by ai_status, by associated project, etc.).

**Step 4 — Save:** View saved with name and visibility (personal or shared).

### KP-2: Turning a View into an Alert

**Trigger:** User clicks "Create Alert" on an existing view.

**Step 1 — Trigger definition:** User specifies what triggers the alert: new results matching the view criteria.

**Step 2 — Frequency:** User selects: Immediate, Hourly, Daily, or Weekly.

**Step 3 — Aggregation:** Individual (one alert per matching result) or Batched (digest of all matches).

**Step 4 — Delivery:** In-app notification, Push notification, Email, SMS, or combination.

**Step 5 — Save:** Alert is active. User receives notifications when results change.

### KP-3: Receiving and Acting on Alerts

**Trigger:** Alert condition met at configured frequency.

**Step 1 — Evaluation:** System evaluates the saved query at the configured frequency.

**Step 2 — Delivery:** If new results found, notification sent via configured delivery method(s).

**Step 3 — User action:** User clicks notification → navigates to the view showing matching results.

---

## 4. Conversation View Patterns

**Supports processes:** KP-1

### 4.1 Example Views

| View | Filter Criteria | Sort | Use Case |
|---|---|---|---|
| My Open Action Items | ai_action_items IS NOT NULL, ai_status = 'open' | last_activity_at DESC | Track outstanding tasks |
| Stale Client Conversations | system_status = 'stale', grouped by contact | last_activity_at ASC | Identify neglected relationships |
| Project X Status | Relation: conversation_projects → Project X, grouped by is_aggregate | last_activity_at DESC | Project oversight |
| Unassigned This Week | communication.conversation_id IS NULL, last 7 days | timestamp DESC | Daily review triage |
| All Comms with Bob | Participant = Bob (derived), all channels | timestamp ASC | Full relationship view |
| Pending Reviews | ai_confidence < 0.85 | ai_confidence ASC | Review workflow |

### 4.2 Shareable Views

Views can be shared with team members. Shared views use the viewer's data permissions — sharing the view definition doesn't grant access to data the viewer wouldn't normally see.

**Tasks:**

- [ ] CVWA-01: Implement conversation view creation with all field registry filters
- [ ] CVWA-02: Implement is_aggregate filter for view construction
- [ ] CVWA-03: Implement Relation Type-based filtering (conversations by project, company, contact)
- [ ] CVWA-04: Implement view sharing with permission-scoped data

**Tests:**

- [ ] CVWA-T01: Test view filters by system_status correctly
- [ ] CVWA-T02: Test view filters by ai_status correctly
- [ ] CVWA-T03: Test view filters by associated project via Relation Type
- [ ] CVWA-T04: Test shared view shows only data viewer has permission to see

---

## 5. User-Defined Alert Architecture

**Supports processes:** KP-2, KP-3

### 5.1 Design Philosophy

**No default alerts.** The system sends zero notifications unless the user explicitly creates them. Users define exactly the alerts they want.

### 5.2 Alert Structure

An alert is a saved query (view) with a trigger, frequency, and delivery method:

```
Saved Query (filter criteria)
  ├── Rendered as a View (pull — user opens on demand)
  └── Attached as an Alert (push — system notifies on change)
        ├── Frequency: Immediate, Hourly, Daily, Weekly
        ├── Aggregation: Individual or Batched (digest)
        └── Delivery: In-app, Push, Email, SMS
```

### 5.3 Alert Examples

| Alert | Query | Frequency | Delivery |
|---|---|---|---|
| New communication from VIP contacts | Communications from contacts tagged "VIP" | Immediate | Push |
| Conversations going stale on Project X | Conversations under Project X, system_status = 'stale' | Daily | Email digest |
| Unassigned items to review | conversation_id IS NULL or ai_confidence < 0.50 | Daily | In-app |
| Any change to Acme Deal | New communication in conversations under Acme Deal project | Immediate | Push |
| Weekly action item summary | All open ai_action_items | Weekly | Email digest |

### 5.4 Frequency & Aggregation

| Combination | Use Case |
|---|---|
| Immediate + Individual | High-priority, low-frequency (VIP communications) |
| Hourly/Daily + Batched | High-frequency monitoring (project activity digest) |
| Weekly + Batched | Oversight and review (action item summary) |

**Tasks:**

- [ ] CVWA-05: Implement alert creation from existing view
- [ ] CVWA-06: Implement alert frequency configuration (immediate, hourly, daily, weekly)
- [ ] CVWA-07: Implement alert aggregation modes (individual, batched digest)
- [ ] CVWA-08: Implement alert delivery methods (in-app, push, email, SMS)
- [ ] CVWA-09: Implement alert evaluation engine (query execution at configured frequency)
- [ ] CVWA-10: Implement alert CRUD API (create, list, update, delete)

**Tests:**

- [ ] CVWA-T05: Test alert triggers on new matching result
- [ ] CVWA-T06: Test immediate frequency delivers without delay
- [ ] CVWA-T07: Test daily frequency batches into digest
- [ ] CVWA-T08: Test alert does not fire when no new results
- [ ] CVWA-T09: Test alert respects user's data permissions
- [ ] CVWA-T10: Test alert delivery to each configured channel
