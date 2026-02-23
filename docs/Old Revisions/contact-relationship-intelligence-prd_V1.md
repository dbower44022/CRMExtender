# Contact — Relationship Intelligence Sub-PRD

**Version:** 1.0
**Last Updated:** 2026-02-22
**Status:** Draft
**Entity Base PRD:** [contact-entity-base-prd.md]
**Referenced Entity PRDs:** [Company Management Entity Base PRD](company-management-prd_V1.md), [Communications PRD](communications-prd_V3.md)

---

## 1. Overview

### 1.1 Purpose

Relationship Intelligence models the network of connections between contacts, companies, deals, and events as a graph with typed, directed, temporal edges. It goes beyond simple "who knows who" to answer questions like: "What's the best introduction path to this prospect?", "Who are the key connectors in my network?", "What does this company's org chart look like?", and "How has my relationship with this contact evolved?"

This is the feature set that most differentiates CRMExtender from traditional CRMs that treat contacts as isolated records rather than nodes in a network.

### 1.2 Preconditions

- Contacts exist in the system with sufficient data for relationship creation.
- Graph database is operational for relationship storage and traversal queries.
- Communication data exists for automated relationship strength computation.

---

## 2. Context

### 2.1 Relevant Fields

| Field | Usage in This Action |
|---|---|
| Display Name | Graph node labels and query results |
| Company Name | Node property for graph filtering |
| Engagement Score | Input for relationship strength computation |
| Job Title | Context for org chart reconstruction |

### 2.2 Relevant Relationships

This sub-PRD defines and manages all Contact-to-Contact relationships. It also covers the graph representation of:
- **Company** — Contacts linked to companies via WORKS_AT edges for org chart and "who do we know at X?" queries.
- **Deals** — Contacts linked to deals via stakeholder edges (decision maker, influencer, champion).
- **Events** — Contacts linked to events via attendance edges.
- **Groups** — Contacts linked to groups via membership edges.

### 2.3 Relevant Lifecycle Transitions

- When a contact is merged, graph relationships are transferred to the surviving contact, deduplicated, and self-referential edges removed (covered in Merge & Split Sub-PRD).
- When a contact is hard-deleted (GDPR), all graph relationships are removed.

---

## 3. Relationship Taxonomy

### 3.1 Requirements

Relationships between contacts, companies, and other entities are typed, directed edges with properties. The relationship taxonomy is organized into categories:

**Hierarchical relationships:**

| Edge Type | Direction | Properties | Description |
|---|---|---|---|
| REPORTS_TO | Contact → Contact | since, until | Direct reporting relationship |
| MANAGES | Contact → Contact | since, until | Direct management relationship |
| DOTTED_LINE_TO | Contact → Contact | context | Indirect reporting / matrix |

**Professional relationships:**

| Edge Type | Direction | Properties | Description |
|---|---|---|---|
| WORKS_WITH | Contact ↔ Contact | context | Colleague relationship |
| ADVISES | Contact → Contact | since, domain | Advisory relationship |
| BOARD_MEMBER_OF | Contact → Company | since, until | Board membership |
| INVESTOR_IN | Contact → Company | round, amount | Investment relationship |

**Social relationships:**

| Edge Type | Direction | Properties | Description |
|---|---|---|---|
| KNOWS | Contact ↔ Contact | strength, since, context, last_interaction | General acquaintance |
| INTRODUCED_BY | Contact → Contact | date, outcome | Introduction provenance |
| REFERRED_BY | Contact → Contact | date, context | Referral provenance |
| MENTOR_OF | Contact → Contact | since, domain | Mentorship |

**Employment relationships:**

| Edge Type | Direction | Properties | Description |
|---|---|---|---|
| WORKS_AT | Contact → Company | role, department, since, until, is_current | Employment (synced from employment records) |

**Deal relationships:**

| Edge Type | Direction | Properties | Description |
|---|---|---|---|
| DECISION_MAKER_FOR | Contact → Deal | | Deal stakeholder role |
| INFLUENCER_ON | Contact → Deal | | Deal stakeholder role |
| CHAMPION_OF | Contact → Deal | | Deal stakeholder role |
| PARTICIPATES_IN | Contact → Deal | | General deal involvement |

**Other relationships:**

| Edge Type | Direction | Properties | Description |
|---|---|---|---|
| ATTENDED | Contact → Event | role | Event attendance |
| MEMBER_OF | Contact → Group | | Group membership |
| HAS_SKILL | Contact → Skill | | Skill tagging |
| INTERESTED_IN | Contact → Industry | | Industry interest |

Each relationship type maps to a Relation Type in the unified framework (Custom Objects PRD) with a graph sync flag that automatically maintains the corresponding graph edge.

**User story:** As a user, I want to define relationships between contacts (reports to, knows, introduced by, mentor of, etc.), so I can model my professional network.

**Tasks:**

- [ ] RELINT-01: Implement relationship taxonomy as Relation Types in the unified framework
- [ ] RELINT-02: Implement graph sync for each relationship type (auto-create/update/delete graph edges)
- [ ] RELINT-03: Implement relationship creation UI with type selection, direction, and temporal bounds
- [ ] RELINT-04: Implement relationship editing and deletion

**Tests:**

- [ ] RELINT-T01: Creating a REPORTS_TO relationship syncs to graph database
- [ ] RELINT-T02: Updating a relationship's temporal bounds updates the graph edge
- [ ] RELINT-T03: Deleting a relationship removes the graph edge
- [ ] RELINT-T04: Employment record creation auto-creates WORKS_AT graph edge

---

## 4. Relationship Strength Scoring

### 4.1 Requirements

The KNOWS relationship includes a strength property (0.0–1.0) reflecting the depth and recency of the relationship between two contacts.

**Input signals:**

| Signal | Weight | Description |
|---|---|---|
| Communication frequency | 0.30 | Emails, calls, meetings in the last 90 days |
| Communication recency | 0.25 | Days since last communication (decays exponentially) |
| Reciprocity | 0.20 | Ratio of bidirectional communication (1.0 = perfectly balanced) |
| Duration | 0.15 | Length of known relationship (capped at 5+ years = max) |
| Explicit connections | 0.10 | User-defined relationships (introductions, referrals) |

**Decay function:** Strength decays by 10% per month of inactivity. A relationship with no communication for 6 months loses approximately 47% of its frequency-weighted score. This ensures active relationships surface above dormant ones.

**Recomputation:** Strength scores are recomputed daily. The job processes communication events from the last 24 hours and adjusts affected relationship edges.

**Tasks:**

- [ ] RELINT-05: Implement relationship strength computation with weighted signals
- [ ] RELINT-06: Implement strength decay function (10% per month of inactivity)
- [ ] RELINT-07: Implement daily strength recomputation job

**Tests:**

- [ ] RELINT-T05: Active relationship with daily communication scores near 1.0
- [ ] RELINT-T06: Relationship with no communication for 6 months shows ~47% decay
- [ ] RELINT-T07: Bidirectional communication scores higher reciprocity than one-sided
- [ ] RELINT-T08: Daily job only recomputes relationships with new communication events

---

## 5. Graph Intelligence Queries

### 5.1 Requirements

The graph enables key intelligence queries that are impossible with tabular data alone:

**Warm introduction path:**
Find the shortest chain of mutual connections between the user and a target contact, traversing up to 4 hops. Multiple paths are returned, ranked by overall relationship strength (product of edge strengths along the path).

**Strongest path:**
Among all shortest paths between two contacts, find the one with the highest combined relationship strength. This identifies the best introduction route, not just any route.

**Who do we know at [company]?**
Find all contacts with a current WORKS_AT relationship to the specified company. Returns contacts with their roles and relationship strength to the user.

**Org chart reconstruction:**
Reconstruct a company's organizational hierarchy from REPORTS_TO and MANAGES relationships among contacts at that company. Supports manual corrections where automated inference is wrong.

**Key connectors:**
Identify contacts with the highest number of strong relationships — the hubs in the user's network who can provide the most introductions.

**Mutual connections:**
Find contacts who know both the user and a target contact — common ground for outreach.

**Career movers:**
Detect contacts who have changed jobs recently by comparing current and historical WORKS_AT relationships.

**User stories:**
- As a user, I want to find the shortest warm introduction path between me and a target contact through mutual connections.
- As a user, I want to see a visual network graph of a contact's relationships.
- As a user, I want to see the organizational chart for a company reconstructed from contact relationships.

**Tasks:**

- [ ] RELINT-08: Implement warm introduction path query (shortest path, max 4 hops)
- [ ] RELINT-09: Implement strongest path query (strength-weighted shortest path)
- [ ] RELINT-10: Implement "who do we know at" company query
- [ ] RELINT-11: Implement org chart reconstruction from hierarchical relationships
- [ ] RELINT-12: Implement key connector identification (degree centrality)
- [ ] RELINT-13: Implement mutual connection discovery
- [ ] RELINT-14: Implement career mover detection

**Tests:**

- [ ] RELINT-T09: Warm intro path finds 2-hop connection through mutual contact
- [ ] RELINT-T10: Strongest path returns the path with highest combined strength
- [ ] RELINT-T11: "Who do we know" returns only contacts with current employment at target company
- [ ] RELINT-T12: Org chart correctly reflects REPORTS_TO hierarchy
- [ ] RELINT-T13: Key connector query returns contacts ordered by relationship count
- [ ] RELINT-T14: Mutual connections query returns contacts who know both parties
- [ ] RELINT-T15: Career mover detection identifies contacts with recent company changes

---

## 6. Network Visualization

### 6.1 Requirements

Users can view an interactive graph visualization of a contact's network, centered on the selected contact. The visualization supports:

- **Zoom and pan** — Navigate the graph at different levels of detail.
- **Filter by relationship type** — Show only specific edge types (e.g., only KNOWS, or only WORKS_AT).
- **Click-through navigation** — Click a node to navigate to that contact's detail page or recenter the graph on that contact.
- **Strength visualization** — Edge thickness or color reflects relationship strength.
- **Temporal filtering** — Filter to show relationships active during a specific time period.

### 6.2 UI Specifications

The network visualization is a dedicated view accessible from the contact detail page. The graph renders with the selected contact centered. Nodes are labeled with contact names and optionally company names. Edges are labeled with relationship type. A sidebar panel shows details about the selected node or edge. Filter controls appear above the graph.

The level of visual detail is intentionally left flexible for implementation — the key requirement is that the visualization accurately represents the graph data and supports the interactions listed above.

**Tasks:**

- [ ] RELINT-15: Implement graph visualization data assembly (nodes, edges, properties)
- [ ] RELINT-16: Implement interactive graph rendering with zoom, pan, and click-through
- [ ] RELINT-17: Implement relationship type filtering
- [ ] RELINT-18: Implement strength-based edge visualization (thickness or color)
- [ ] RELINT-19: Implement temporal filtering for historical network views

**Tests:**

- [ ] RELINT-T16: Visualization renders centered on selected contact
- [ ] RELINT-T17: Filtering by relationship type shows only matching edges
- [ ] RELINT-T18: Click on node navigates to contact detail page
- [ ] RELINT-T19: Edge thickness reflects relationship strength
- [ ] RELINT-T20: Temporal filter shows only relationships active during selected period
