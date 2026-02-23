# Contact — Relationship Intelligence Sub-PRD

**Version:** 2.0
**Last Updated:** 2026-02-22
**Status:** Draft
**Entity Base PRD:** [contact-entity-base-prd.md]
**Referenced Entity PRDs:** [Company Management Entity Base PRD](company-management-prd.md), [Communications PRD](communications-prd.md)

> **V2.0 (2026-02-22):** Added Key Processes section defining end-to-end user experiences for all relationship intelligence scenarios. Restructured functional sections with process linkage.

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

## 3. Key Processes

### KP-1: Adding a Relationship Between Contacts

**Trigger:** The user knows that two contacts have a relationship and wants to record it.

**Step 1 — Initiate from detail page:** On a contact's detail page, the relationships card shows existing relationships. The user clicks "Add Relationship."

**Step 2 — Select target contact:** A contact search dropdown appears. The user types to find and select the target contact.

**Step 3 — Select relationship type:** A dropdown shows available relationship types organized by category: Hierarchical (Reports To, Manages, Dotted Line To), Professional (Works With, Advises, Board Member Of, Investor In), Social (Knows, Introduced By, Referred By, Mentor Of). The user selects a type.

**Step 4 — Set direction:** For directional relationships, the UI shows the direction clearly: "[Contact A] reports to [Contact B]." The user can flip the direction with a swap button.

**Step 5 — Set properties:** Based on the relationship type, relevant property fields appear: "Since" date, "Until" date (optional), "Context" text, and any type-specific properties. The user fills in what they know.

**Step 6 — Save:** The user clicks "Save." The relationship appears on both contacts' relationship cards. The corresponding graph edge is created in the graph database.

### KP-2: Finding a Warm Introduction Path

**Trigger:** The user wants to reach a target contact they don't know directly and needs to find mutual connections.

**Step 1 — Initiate:** The user is on a contact's detail page (the target they want to reach). In the relationships card, they click "Find Introduction Path" — or they use natural language search: "how do I reach [Name]?"

**Step 2 — Path computation:** The system searches the graph for paths from the user to the target contact, up to 4 hops. Multiple paths may exist.

**Step 3 — Results display:** Paths are displayed as a visual chain: [You] → [Connector A] → [Connector B] → [Target]. Each hop shows the relationship type and strength. Paths are ranked by combined relationship strength (product of edge strengths along the path).

**Step 4 — Path details:** Clicking on any connector in the path shows their contact card with key details and the specific relationship context (e.g., "You worked with Connector A at Acme Corp from 2020–2023, relationship strength: 0.82").

**Step 5 — Take action:** Each path includes an "Ask for Introduction" button that opens a pre-addressed email draft to the first connector, with a suggested introduction request.

**Step 6 — No path found:** If no path exists within 4 hops, the system shows: "No introduction path found within your network. [Search for mutual connections?]" — which triggers a broader search for any shared context (same industry, same alma mater, same conference).

### KP-3: Exploring a Contact's Network

**Trigger:** The user wants to see who a contact knows and how they're connected.

**Step 1 — Network visualization:** On the contact detail page, the relationships card includes a "View Network" link. Clicking it opens the interactive graph visualization centered on the selected contact.

**Step 2 — Graph display:** The contact appears as the center node. Connected contacts appear around them with labeled edges showing relationship types. Edge thickness reflects relationship strength.

**Step 3 — Navigation:** The user can click any node to see that contact's card, or double-click to recenter the graph on that contact. Zoom and pan controls allow exploration of deeper connections.

**Step 4 — Filtering:** Filter controls above the graph allow the user to show/hide relationship types (e.g., show only "Knows" relationships, or only "Works At" edges). A temporal filter shows only relationships active during a specific period.

**Step 5 — Discovery:** The visualization surfaces patterns not visible in list views — clusters of interconnected contacts, bridge contacts between groups, isolated nodes.

### KP-4: Viewing "Who Do We Know At" a Company

**Trigger:** The user wants to see all contacts at a specific company before a meeting or outreach.

**Step 1 — Initiate:** On a company's detail page, a "Contacts at [Company]" section shows all contacts with current WORKS_AT relationships. Alternatively, the user can ask via NL search: "who do we know at Acme Corp?"

**Step 2 — Results:** Contacts are listed with their roles, relationship strength to the user, engagement score, and last communication date. Sorted by relationship strength (strongest connections first).

**Step 3 — Org chart view (optional):** If hierarchical relationships exist (REPORTS_TO, MANAGES), the user can toggle to an org chart visualization showing the company's known hierarchy reconstructed from contact relationships.

**Step 4 — Gaps:** If the system knows of roles at the company (from enrichment) where no contact exists, these appear as "Unknown" placeholders, suggesting: "No contact found for VP Engineering — [Search] [Enrich]."

### KP-5: Identifying Key Connectors

**Trigger:** The user wants to find the most well-connected people in their network — the hubs who can provide the most introductions.

**Step 1 — Navigate to network insights:** From the main navigation, the user accesses a "Network Insights" section (or via NL search: "who are my best connectors?").

**Step 2 — Key connectors list:** The system shows contacts ranked by connection count and combined relationship strength (degree centrality). Each entry shows the contact's name, number of connections, average relationship strength, and the industries/companies their connections span.

**Step 3 — Connector detail:** Clicking a connector shows their network map (KP-3) and a list of their connections with relationship types and strengths.

**Step 4 — Network clusters:** A "Clusters" tab shows groups of contacts that are more connected to each other than to the rest of the network. Each cluster is labeled with common attributes (e.g., "Acme Corp engineering team," "Series A founders," "MIT alumni").

### KP-6: Tracking How a Relationship Evolves

**Trigger:** The user wants to see how their relationship with a specific contact has changed over time.

**Step 1 — Relationship timeline:** On the contact detail page, the relationships card includes a "Relationship History" link that opens a timeline view.

**Step 2 — Timeline display:** The timeline shows all relationship events chronologically: when the relationship was created, strength changes over time, communication milestones (first email, first meeting, 100th email), relationship type changes, and any introduction provenance.

**Step 3 — Strength trend:** A chart shows the relationship strength score over time, with annotations at key events (e.g., "Strength peaked at 0.91 after weekly meetings in Q3 2025; declined to 0.62 after 3 months of inactivity").

**Step 4 — Compare:** The user can compare the relationship timeline with the engagement score timeline to see correlations between communication activity and relationship health.

---

## 4. Relationship Taxonomy

**Supports processes:** KP-1 (step 3 type selection). This section defines the complete set of relationship types.

### 4.1 Requirements

Relationships between contacts, companies, and other entities are typed, directed edges with properties:

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

Each relationship type maps to a Relation Type in the unified framework with a graph sync flag.

**Tasks:**

- [ ] RELINT-01: Implement relationship taxonomy as Relation Types in the unified framework
- [ ] RELINT-02: Implement graph sync for each relationship type (auto-create/update/delete graph edges)
- [ ] RELINT-03: Implement relationship creation UI with type selection, direction, and properties (per KP-1)
- [ ] RELINT-04: Implement relationship editing and deletion
- [ ] RELINT-05: Implement direction swap control for directional relationships

**Tests:**

- [ ] RELINT-T01: Creating a REPORTS_TO relationship syncs to graph database
- [ ] RELINT-T02: Updating a relationship's temporal bounds updates the graph edge
- [ ] RELINT-T03: Deleting a relationship removes the graph edge
- [ ] RELINT-T04: Employment record creation auto-creates WORKS_AT graph edge
- [ ] RELINT-T05: Direction swap correctly reverses the relationship

---

## 5. Relationship Strength Scoring

**Supports processes:** KP-2 (step 3 path ranking), KP-3 (step 2 edge thickness), KP-4 (step 2 sorting), KP-5 (step 2 ranking), KP-6 (step 3 strength trend).

### 5.1 Requirements

The KNOWS relationship includes a strength property (0.0–1.0) reflecting the depth and recency of the relationship:

| Signal | Weight | Description |
|---|---|---|
| Communication frequency | 0.30 | Emails, calls, meetings in the last 90 days |
| Communication recency | 0.25 | Days since last communication (decays exponentially) |
| Reciprocity | 0.20 | Ratio of bidirectional communication (1.0 = perfectly balanced) |
| Duration | 0.15 | Length of known relationship (capped at 5+ years = max) |
| Explicit connections | 0.10 | User-defined relationships (introductions, referrals) |

**Decay function:** Strength decays by 10% per month of inactivity. A relationship with no communication for 6 months loses approximately 47% of its frequency-weighted score.

**Recomputation:** Daily scheduled job processes communication events from the last 24 hours and adjusts affected relationship edges.

**Tasks:**

- [ ] RELINT-06: Implement relationship strength computation with weighted signals
- [ ] RELINT-07: Implement strength decay function (10% per month of inactivity)
- [ ] RELINT-08: Implement daily strength recomputation job

**Tests:**

- [ ] RELINT-T06: Active relationship with daily communication scores near 1.0
- [ ] RELINT-T07: Relationship with no communication for 6 months shows ~47% decay
- [ ] RELINT-T08: Bidirectional communication scores higher reciprocity than one-sided
- [ ] RELINT-T09: Daily job only recomputes relationships with new communication events

---

## 6. Graph Intelligence Queries

**Supports processes:** KP-2 (steps 2–3 path finding), KP-4 (steps 1–4 company contacts and org chart), KP-5 (steps 2–4 connectors and clusters).

### 6.1 Requirements

The graph enables intelligence queries impossible with tabular data alone:

**Warm introduction path:** Find the shortest chain of mutual connections between the user and a target contact, up to 4 hops. Multiple paths returned, ranked by combined relationship strength (product of edge strengths).

**Strongest path:** Among all shortest paths, find the one with highest combined strength.

**Who do we know at [company]?** Find all contacts with current WORKS_AT at the specified company. Returns contacts with roles and relationship strength to the user.

**Org chart reconstruction:** Reconstruct a company's hierarchy from REPORTS_TO and MANAGES relationships. Supports manual corrections.

**Key connectors:** Contacts with highest degree centrality — the network hubs.

**Mutual connections:** Contacts who know both the user and a target contact.

**Network clusters:** Groups of contacts more connected to each other than to the rest of the network.

**Career movers:** Contacts who changed jobs recently (current vs. historical WORKS_AT).

**Tasks:**

- [ ] RELINT-09: Implement warm introduction path query (shortest path, max 4 hops, strength-ranked)
- [ ] RELINT-10: Implement strongest path query (strength-weighted shortest path)
- [ ] RELINT-11: Implement "who do we know at" company query
- [ ] RELINT-12: Implement org chart reconstruction from hierarchical relationships
- [ ] RELINT-13: Implement key connector identification (degree centrality)
- [ ] RELINT-14: Implement mutual connection discovery
- [ ] RELINT-15: Implement network cluster detection
- [ ] RELINT-16: Implement career mover detection
- [ ] RELINT-17: Implement "Ask for Introduction" draft email from path results

**Tests:**

- [ ] RELINT-T10: Warm intro path finds 2-hop connection through mutual contact
- [ ] RELINT-T11: Strongest path returns the path with highest combined strength
- [ ] RELINT-T12: "Who do we know" returns only contacts with current employment at target company
- [ ] RELINT-T13: Org chart correctly reflects REPORTS_TO hierarchy
- [ ] RELINT-T14: Key connector query returns contacts ordered by connection count
- [ ] RELINT-T15: Mutual connections query returns contacts who know both parties
- [ ] RELINT-T16: Cluster detection groups interconnected contacts correctly
- [ ] RELINT-T17: "Ask for Introduction" generates pre-addressed email draft

---

## 7. Network Visualization

**Supports processes:** KP-3 (full flow), KP-4 (step 3 org chart view), KP-5 (step 3 connector network).

### 7.1 Requirements

Interactive graph visualization centered on a selected contact:

- **Zoom and pan** — Navigate the graph at different levels of detail.
- **Filter by relationship type** — Show only specific edge types.
- **Click-through navigation** — Click a node to view contact card; double-click to recenter.
- **Strength visualization** — Edge thickness reflects relationship strength.
- **Temporal filtering** — Filter to show relationships active during a specific time period.
- **Cluster highlighting** — Network clusters are visually grouped with subtle background shading.

### 7.2 UI Specifications

The network visualization is a dedicated view accessible from the contact detail page. The graph renders with the selected contact centered. Nodes are labeled with contact names and optionally company names. Edges are labeled with relationship type. A sidebar panel shows details about the selected node or edge. Filter controls appear above the graph. The visualization supports both a free-form network layout and a hierarchical org chart layout.

**Tasks:**

- [ ] RELINT-18: Implement graph visualization data assembly (nodes, edges, properties)
- [ ] RELINT-19: Implement interactive graph rendering with zoom, pan, click-through, and recenter
- [ ] RELINT-20: Implement relationship type filtering
- [ ] RELINT-21: Implement strength-based edge thickness visualization
- [ ] RELINT-22: Implement temporal filtering for historical network views
- [ ] RELINT-23: Implement org chart layout mode
- [ ] RELINT-24: Implement cluster highlighting with background shading

**Tests:**

- [ ] RELINT-T18: Visualization renders centered on selected contact
- [ ] RELINT-T19: Filtering by relationship type shows only matching edges
- [ ] RELINT-T20: Click on node shows contact card; double-click recenters graph
- [ ] RELINT-T21: Edge thickness reflects relationship strength
- [ ] RELINT-T22: Temporal filter shows only relationships active during selected period
- [ ] RELINT-T23: Org chart layout displays hierarchical relationships correctly
- [ ] RELINT-T24: Clusters are visually grouped

---

## 8. Relationship History

**Supports processes:** KP-6 (full flow).

### 8.1 Requirements

Users can view the full history of their relationship with a contact, including how it has evolved over time:

- **Relationship events timeline:** Chronological list of all relationship milestones — creation, type changes, strength peaks and valleys, communication milestones (first email, first meeting, Nth email), introduction provenance.
- **Strength trend chart:** Line chart showing relationship strength over the full relationship duration with annotated events.
- **Comparison view:** Side-by-side chart comparing relationship strength with engagement score to show correlations.

### 8.2 UI Specifications

Accessible from the relationships card on the contact detail page via "Relationship History." Opens as a panel or dedicated view showing the timeline on the left and strength chart on the right. Events in the timeline are linked to the corresponding point on the strength chart.

**Tasks:**

- [ ] RELINT-25: Implement relationship event tracking (milestones, changes, communication counts)
- [ ] RELINT-26: Implement relationship history timeline view
- [ ] RELINT-27: Implement relationship strength trend chart with event annotations
- [ ] RELINT-28: Implement strength vs. engagement comparison view

**Tests:**

- [ ] RELINT-T25: Timeline shows relationship creation event
- [ ] RELINT-T26: Timeline shows communication milestones (first email, first meeting)
- [ ] RELINT-T27: Strength trend chart displays correct values over time
- [ ] RELINT-T28: Comparison view shows both strength and engagement aligned on same timeline
