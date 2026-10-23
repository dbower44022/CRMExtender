# Conversation — Entity Base PRD

**Version:** 1.1
**Last Updated:** 10-22-26 22:55
**Status:** Draft — V1.1 adds the user-marked Done state (release v10.44, schema v34)
**Product PRD:** [CRMExtender Product PRD]

> **V1.1 (10-22-26): Done state.** A user can mark a conversation Done so the conversations grid is cleaned of finished threads, and a done conversation returns to active when a new inbound communication joins it. Six decisions approved by the product owner on 10-22-26: (1) Done is a value of System Status, replacing the never-implemented `closed`; (2) only inbound communications reopen, the user's own sends do not; (3) the timed stale and auto-close transitions stay deferred; (4) the grid hides done conversations unless a filter names System Status; (5) Mark Done and Reopen are offered on the row context menu, the Content Tool Bar in bulk mode, the Preview Card, and the full View, with no keyboard key; (6) Done At, Done By, Reopened At and Reopened Reason are recorded, last occurrence only, and every new communication queues a fresh summary. The dismissed fields are untouched (§6.5). Sections changed: 1.4, 6.1, 6.3, 6.4 (new), 6.5 (new), KP-3, KP-7 (new), 8.9–8.11 (new), 12 (new), 13 (new).

---

## 1. Entity Definition

### 1.1 Purpose

Conversation is the organizational layer above Communications. A Conversation groups related communications between specific participants about a specific subject, potentially spanning multiple channels. When `is_aggregate = true`, a Conversation serves as an organizational container that groups child Conversations — replacing the former Topic entity.

Every intelligence layer above the atomic Communication (AI summarization, status classification, action item extraction, engagement visibility) operates at the Conversation level. Communications are raw data; Conversations are structured understanding.

### 1.2 Design Goals

- **Optional, flexible hierarchy** — Every level is optional. Communications can exist unassigned. Conversations can be standalone or nested. The hierarchy helps users organize — it never forces structure.
- **AI-powered auto-organization with human oversight** — The system automatically classifies, routes, and groups Communications. High-confidence assignments happen silently. Low-confidence assignments are flagged for review. Users correct mistakes. The system learns from corrections.
- **Published Summary timeline** — The Conversation timeline assembles ordered references to its Communications' Published Summaries. The Conversation is a presentation container — it does not copy or store Communication content.
- **Cross-channel continuity** — A conversation can span email, SMS, phone, and video. Communications from all channels are sequenced by timestamp into a single coherent timeline.
- **Intelligence-first** — Every substantive conversation has an AI-generated summary, status classification, action items, and topic tags.
- **Entity attachment via Relation Types** — Conversations attach to Projects, Companies, Contacts, Events, and custom objects exclusively through Relation Types, not FK columns. Many-to-many, no inheritance.

### 1.3 Performance Targets

| Metric | Target |
|---|---|
| Conversation list load (default view, 50 rows) | < 200ms |
| Conversation detail page (timeline with summaries) | < 300ms |
| AI classification of incoming communication | < 2s |
| Conversation-level summarization | < 5s |
| Review workflow load (pending items) | < 200ms |

### 1.4 Core Fields

| Field | Description | Required | Editable | Sortable | Filterable | Valid Values / Rules |
|---|---|---|---|---|---|---|
| ID | Unique identifier. Prefixed ULID with `cvr_` prefix. | Yes | System | No | Yes | Prefixed ULID |
| Subject | Derived from email subject, or user-defined. Display name field. | No | Direct | Yes | Yes | Free text |
| Is Aggregate | Whether this is an organizational container for child Conversations. **Immutable after creation.** | Yes | System (set on creation) | No | Yes | Boolean. Default: false. |
| Description | Optional description of scope. Primarily useful for aggregate Conversations. | No | Direct | No | No | Free text |
| System Status | Lifecycle state. `active` until the user marks the conversation Done; returns to `active` when a new inbound communication joins it (§6.4). `stale` is reserved for the deferred timer. | Yes | Override (user marks Done or reopens; §6.4) | Yes | Yes | `active`, `stale`, `done` |
| Done At | When the user marked the conversation Done. Cleared on reopen. | No | System | Yes | Yes | Timestamp |
| Done By | User who marked the conversation Done. Cleared on reopen. | No | System | No | Yes | Reference to User |
| Reopened At | When the conversation last returned from Done to active. | No | System | Yes | Yes | Timestamp |
| Reopened Reason | Why the conversation last reopened. | No | System | No | Yes | `inbound` (a new inbound communication joined), `user` (the user chose Reopen) |
| AI Status | Semantic status from AI analysis. NULL until AI processes. | No | Override | Yes | Yes | `open`, `closed`, `uncertain` |
| AI Summary | AI-generated 2–4 sentence narrative of conversation state. | No | Computed | No | No | AI-generated text |
| AI Action Items | JSON-encoded list of extracted action items with assignee and deadline. | No | Computed | No | Yes (contains search) | JSON array |
| AI Key Topics | JSON-encoded list of 2–5 short topic phrases. | No | Computed | No | Yes (contains search) | JSON array |
| AI Confidence | Confidence score for AI's conversation assignment (0.0–1.0). | No | System | Yes | Yes | Decimal 0.0–1.0 |
| AI Last Processed At | When AI last analyzed this conversation. | No | System | Yes | Yes | Timestamp |
| Communication Count | Denormalized count of communications. For aggregates: includes all children's counts recursively. | No | Computed | Yes | Yes | Non-negative integer |
| Channel Breakdown | JSON-encoded count by channel. For aggregates: merged across direct + children. | No | Computed | No | No | JSON object |
| First Activity At | Timestamp of earliest communication. For aggregates: MIN across direct + children. | No | Computed | Yes | Yes | Timestamp |
| Last Activity At | Timestamp of most recent communication. Drives system_status transitions. For aggregates: MAX across direct + children. | No | Computed | Yes | Yes | Timestamp |
| Stale After Days | Configurable threshold for stale detection. Display-only until the deferred timer task (CONV-DN-09) is built. | No | Direct | No | No | Positive integer. Default: 14. |
| Closed After Days | Configurable threshold for timed close. Display-only until the deferred timer task (CONV-DN-09) is built. | No | Direct | No | No | Positive integer. Default: 30. |
| Status | Record lifecycle. | Yes, defaults to active | System | Yes | Yes | `active`, `archived` |
| Created By | User who created the record (NULL for auto-formed). | No | System | No | Yes | Reference to User |
| Created At | Record creation timestamp. | Yes | System | Yes | Yes | Timestamp |
| Updated At | Last modification timestamp. | Yes | System | Yes | Yes | Timestamp |

### 1.5 Derived Participant List

Conversation participants are **not** stored on the Conversation record. They are derived from the union of Communication Participants across all communications in the conversation. This avoids data duplication and ensures the participant list is always current.

The Conversation↔Contact system Relation Type (Section 2.5) provides explicit supplementary association for contacts who are relevant but never direct communication participants.

### 1.6 Registered Behaviors

| Behavior | Trigger | Description |
|---|---|---|
| AI status detection | On new communication added | AI analyzes conversation content and updates ai_status. See AI Intelligence Sub-PRD. |
| Summarization | On new communication added, on demand | AI generates/refreshes ai_summary, ai_action_items, ai_key_topics. See AI Intelligence Sub-PRD. |
| Action item extraction | On new communication added | AI extracts action items from conversation content. See AI Intelligence Sub-PRD. |
| Aggregate roll-up | On child membership change, on child content change | Denormalized counts and AI summary fan out to parent aggregates. |

---

## 2. Entity Relationships

### 2.1 Communications (Direct)

**Nature:** One-to-many, FK column on Communication
**Ownership:** Communications PRD
**Description:** Communications reference their parent Conversation via `conversation_id` FK. A communication belongs to at most one conversation. The conversation timeline renders Communications' Published Summaries by reference — it does not copy content.

### 2.2 Child Conversations (Membership)

**Nature:** Many-to-many, via `conversation_members` junction table
**Ownership:** This entity
**Description:** Aggregate Conversations (is_aggregate = true) can contain child Conversations (standard or aggregate). A child can belong to multiple parents simultaneously. Unlimited nesting depth with acyclic enforcement.

### 2.3 Projects

**Nature:** Many-to-many, via system Relation Type
**Ownership:** This entity (Relation Type: `conversation_projects`)
**Description:** Conversations associate with Projects. A conversation can be linked to multiple Projects. No inheritance — child conversations do not automatically inherit parent's project links.

### 2.4 Companies

**Nature:** Many-to-many, via system Relation Type
**Ownership:** This entity (Relation Type: `conversation_companies`)
**Description:** Direct company association. Independent of contact-derived company associations.

### 2.5 Contacts (Explicit)

**Nature:** Many-to-many, via system Relation Type
**Ownership:** This entity (Relation Type: `conversation_contacts`)
**Description:** Explicit contact association supplementing the derived participant list. Used for contacts relevant to a conversation who were never direct communication participants (e.g., a manager who should be informed, or a tagged "Decision Maker").

### 2.6 Events

**Nature:** Many-to-many, via system Relation Type
**Ownership:** Events PRD (Relation Type: `conversation_events`)
**Description:** Links Conversations to calendar events. Meeting follow-up emails and pre-meeting coordination threads are correlated with their triggering events.

### 2.7 Notes

**Nature:** Many-to-many, via universal attachment
**Ownership:** Notes PRD
**Description:** Notes attach to Conversations as supplementary commentary (meeting observations, strategic context, action plans).

### 2.8 Segments

**Nature:** One-to-many, behavior-managed
**Ownership:** This entity
**Description:** When a communication spans multiple conversations, a Segment references a portion of text in a target conversation while the full communication stays in its primary conversation. See Conversation Formation Sub-PRD.

---

## 3. Aggregate Conversations

### 3.1 Concept

An Aggregate Conversation (`is_aggregate = true`) serves as an organizational container that groups related child Conversations — the same role previously played by the Topic entity. This follows the Document/Folder precedent from the Documents PRD.

Unlike Document Folders (pure containers), Aggregate Conversations can hold **both** direct Communications AND child Conversations simultaneously. An "Acme Lease Negotiation" aggregate might have its own Communications (general coordination emails) plus child Conversations with specific parties (lawyer, accountant, lessor).

### 3.2 Aggregate vs. Standard

| Aspect | Standard (`is_aggregate = false`) | Aggregate (`is_aggregate = true`) |
|---|---|---|
| Contains Communications | Yes — via conversation_id FK | Yes — can have its own direct Communications |
| Contains child Conversations | No | Yes — via conversation_members junction |
| AI Summary | Synthesizes across its Communications' Published Summaries | Synthesizes across own Communications PLUS all child summaries |
| Communication Count | Count of direct Communications | Direct + sum of all children (recursive) |
| Can be child of an aggregate | Yes | Yes (aggregates can nest) |
| is_aggregate mutability | Immutable | Immutable |

### 3.3 Nesting

Aggregate Conversations can nest within other aggregates to unlimited depth, enabling hierarchical organization. Application-level acyclic enforcement prevents circular references.

### 3.4 Immutability of is_aggregate

The `is_aggregate` flag is immutable after creation. A standard Conversation cannot be converted to an aggregate, and vice versa. This ensures deterministic UI behavior, stable denormalized counts, and reliable API contracts. If a user needs to change, they create a new aggregate and move the original into it as a child.

---

## 4. Conversation Membership

### 4.1 Many-to-Many Model

Child Conversations belong to aggregate Conversations via a many-to-many junction table, mirroring the `document_folder_members` pattern. A single Conversation can belong to multiple aggregates simultaneously.

### 4.2 Membership Rules

| Rule | Enforcement |
|---|---|
| Parent must have is_aggregate = true | Application-level validation on insert |
| Child can be standard or aggregate | No restriction — enables nesting |
| A Conversation can belong to multiple parents | Many-to-many by design |
| No self-membership | CHECK constraint |
| No circular references | Application-level acyclic check |
| No inheritance | Child entity links are independent of parent's |

### 4.3 Acyclic Enforcement

Before inserting a membership row (parent_id, child_id), the system walks the ancestry chain of parent_id to verify that child_id does not appear anywhere in the chain. Same algorithm as Document folder nesting.

### 4.4 Denormalized Counts

Aggregate Conversations maintain denormalized counts including both direct and child Communications:

| Field | Calculation |
|---|---|
| communication_count | Direct Communications + SUM of all children's communication_count (recursive) |
| channel_breakdown | Merged JSON across direct + all children |
| first_activity_at | MIN across direct + all children |
| last_activity_at | MAX across direct + all children |

Updated when: a Communication is added/removed from the aggregate or any child, a child Conversation is added/removed, or a child's counts change (fans out to all parent aggregates).

### 4.5 AI Summary Fan-Out

When a child Conversation's content changes, AI re-summarization fans out to all parent aggregate Conversations. The aggregate's AI summary refreshes to incorporate updated child content.

---

## 5. System Relation Types

### 5.1 Entity Attachment via Relation Types

Conversations attach to other entities exclusively through system Relation Types — no FK columns. This provides universal attachment (any registered object type), many-to-many cardinality, no inheritance, and consistency with the platform-wide Relation Type pattern.

### 5.2 System Relation Type Definitions

| Relation Type | Slug | Source | Target | Cardinality | Notes |
|---|---|---|---|---|---|
| Conversation↔Project | `conversation_projects` | Conversation (`cvr_`) | Project (`prj_`) | Many-to-many | Multiple Projects per Conversation. |
| Conversation↔Company | `conversation_companies` | Conversation (`cvr_`) | Company (`cmp_`) | Many-to-many | Direct company association. |
| Conversation↔Contact | `conversation_contacts` | Conversation (`cvr_`) | Contact (`con_`) | Many-to-many | Explicit association supplementing derived participants. |
| Conversation↔Event | `conversation_events` | Conversation (`cvr_`) | Event (`evt_`) | Many-to-many | Links to calendar events. |

### 5.3 No Inheritance

Entity associations are independent at every level. If aggregate "Lease Negotiation" is associated with Project "2026 Expansion" and Company "Acme Corp", child Conversation "With Lawyer" does NOT inherit those associations. The child has its own, possibly different, entity links (e.g., Company "Smith & Associates LLP"). Users can explicitly add the same associations to children if desired.

---

## 6. Lifecycle

### 6.1 Three Status Dimensions

**System Status (status)** — lifecycle state. User-managed as of V1.1; the timed transitions are deferred:

| Value | Trigger |
|---|---|
| `active` | Default on creation. A `done` or `stale` conversation returns here when a new inbound communication joins it, or when the user chooses Reopen. |
| `stale` | Reserved: no activity for N days (stale_after_days, default: 14). Nothing sets it until the deferred timer task (CONV-DN-09) is built. |
| `done` | The user marks the conversation Done (§6.4). Whether the deferred timer also sets `done` after M days of silence (closed_after_days, default: 30), or needs a value of its own, is decided when CONV-DN-09 is designed. |

Transitions: `active` → `done` by user action. `done` → `active` by user action (Reopen) or by a new inbound communication. A communication the user sends never changes System Status. The V1.0 value name `closed` is renamed `done` so that the word "closed" keeps a single meaning in the product, as an AI Status value.

**AI Status (ai_status)** — Semantic, from AI analysis:

| Value | Meaning |
|---|---|
| `open` | Unresolved items, pending tasks, ongoing discussion |
| `closed` | Definitively resolved or finished |
| `uncertain` | Insufficient context |

Bias toward `open` for multi-message exchanges between known contacts. Casual sign-offs don't close a conversation.

**Triage Status** — Inherited from Communications PRD. Whether the communication(s) passed triage. Orthogonal — determines whether AI analysis happens at all.

### 6.2 Status Independence

The three dimensions are independent: System: active + AI: closed → recent messages, but topic resolved. System: stale + AI: open → no recent activity, but unanswered question pending.

### 6.3 Record Lifecycle

| Status | Description |
|---|---|
| `active` | Normal operating state. Visible in views and search. |
| `archived` | Soft-deleted. Excluded from default queries. Recoverable. |

Implementation note (V1.1): the PoC stores System Status in the single `status` column and has not built archive for conversations, so `archived` is a reserved value. See the Entity TDD §9.4 and §9.8.

### 6.4 Done and Reopen

**Marking Done.** The user marks a conversation Done from the conversations grid (row context menu, on one row or on the selection set), from the Content Tool Bar in bulk mode, from the Preview Card, or from the full View. Mark Done sets System Status to `done`, records Done At and Done By, and clears Reopened At and Reopened Reason. Marking a done conversation Done again changes nothing. Done does not touch AI Status, the AI Summary, triage, or the dismissed fields (§6.5).

**Reopening.** Two things reopen a done conversation. First, the user chooses Reopen on any of the same surfaces: System Status returns to `active`, Reopened At is set, Reopened Reason is `user`, and Done At and Done By are cleared. Second, a new inbound communication joins the conversation, through mail sync or through manual assignment: the same field changes apply with Reopened Reason `inbound`. A communication the user sends, whether composed in the product or synced from the Sent folder, joins the conversation and updates its activity but never reopens it. Provider drafts never join a conversation and so never reopen one.

**Default view.** The conversations grid hides done conversations unless the view's filters, saved or quick, include a condition on System Status. The quick filter row offers Active, Done, and the three AI Status chips, prefixed "AI" so that Done and AI closed cannot be misread as the same thing. A one-line note under the chips says that done conversations are hidden until Done is clicked. The Preview Card and the full View open a done conversation by direct link regardless of the rule.

**Summaries.** Marking Done has no effect on summarization. Any new communication that joins a conversation, inbound or outbound, queues a fresh AI summary whether or not the conversation is done.

**Undo.** Every Mark Done shows a confirmation toast with an Undo link that reopens the conversation with Reopened Reason `user`.

**Timers (deferred).** The V1.0 automatic stale and auto-close transitions are not implemented. Stale After Days and Closed After Days remain display-only. The work is tracked as CONV-DN-09 and needs its own decision on whether a timed close shares the `done` value or gets a value of its own, because a word that means both "I finished this" and "nothing happened lately" cannot be read from the grid.

### 6.5 Dismissed Is a Different State

The dismissed fields mark a conversation that was emptied when every one of its communications was archived from the communications grid. The summarizer and the assign-target picker skip dismissed conversations. Done never reads or writes the dismissed fields, and dismissal never changes System Status. A conversation can be both done and dismissed. Two clean-ups are queued outside this release (CONV-DN-10): hide dismissed conversations in the grid, and recompute counts after a communications-grid archive.

---

## 7. Key Processes

### KP-1: A New Conversation Forms Automatically

**Trigger:** Provider sync delivers a communication with a new provider_thread_id not yet mapped to any conversation.

**Step 1 — Thread check:** System checks if this provider_thread_id maps to an existing conversation. Not found.

**Step 2 — Create conversation:** New Conversation created with subject derived from communication subject. is_aggregate = false. system_status = active.

**Step 3 — Assign communication:** Communication's conversation_id set to the new conversation. Denormalized counts updated.

**Step 4 — AI classification:** AI evaluates whether this conversation should be placed in an existing aggregate. High confidence → auto-assign. Low confidence → flag for review.

### KP-2: User Creates a Conversation Manually

**Trigger:** User initiates conversation creation from UI.

**Step 1 — Type selection:** User chooses standard or aggregate conversation.

**Step 2 — Data entry:** User provides subject (required for aggregates, optional for standard), description (optional), entity associations (optional).

**Step 3 — Creation:** Conversation created. If aggregate, it's ready to receive child conversations and/or direct communications.

### KP-3: Browsing and Finding Conversations

**Trigger:** User navigates to Conversations in the Entity Bar.

**Step 1 — Default view loads:** Grid shows conversations with columns per view configuration. Default sort: last_activity_at descending. Done conversations are hidden unless a saved or quick filter names System Status (§6.4).

**Step 2 — Filtering:** User applies filters: is_aggregate, system_status, ai_status, entity associations, date ranges, channel breakdown. Filters apply immediately.

**Step 3 — Selection:** User clicks a conversation. Detail Panel opens with timeline.

### KP-4: Viewing a Conversation Timeline

**Trigger:** User selects a conversation from list or navigation.

**Step 1 — Timeline loads:** Chronologically ordered sequence of Communication Published Summary cards. Each card shows channel icon, timestamp, participants, and summary content.

**Step 2 — Summary cards:** Each card references the Communication's Published Summary. "View Original" links to the full Communication record.

**Step 3 — AI panel:** AI summary, status, action items, and key topics displayed in a sidebar or header section. Confidence indicator shown.

**Step 4 — Entity associations:** Linked Projects, Companies, Contacts, Events shown in metadata section.

**Step 5 — For aggregates:** Additional section shows child Conversations with their summaries and activity dates.

### KP-5: Managing Aggregate Membership

**Trigger:** User adds or removes a child conversation from an aggregate.

**Step 1 — Add child:** User drags a conversation into an aggregate, or uses "Add to..." action. Acyclic check runs. Membership row created.

**Step 2 — Denormalized counts update:** Parent's communication_count, channel_breakdown, first/last_activity_at recomputed.

**Step 3 — AI fan-out:** Parent's AI summary queued for refresh to incorporate child content.

**Step 4 — Remove child:** User removes a child. Membership row deleted. Counts and AI summary refreshed.

### KP-6: Archiving and Restoring

**Trigger:** User archives from detail page or list view.

**Step 1 — Archive:** Conversation archived_at set. Removed from default views.

**Step 2 — Restore:** User unarchives from archived view. archived_at cleared.

### KP-7: Finishing a Conversation

**Trigger:** The user decides a conversation needs no more attention.

**Step 1 — Mark Done:** From the grid (right-click a row and choose Mark Done, or select several rows and choose Mark Done), from the Preview Card, or from the full View, the user marks the conversation Done. A toast confirms, with an Undo link.

**Step 2 — It leaves the working list:** The grid no longer shows the conversation. The Done quick filter shows it, and the Metadata card shows Done At and Done By.

**Step 3 — Someone replies:** During the next sync a new inbound message joins the conversation. The conversation returns to active and reappears in the grid. The Metadata card shows Reopened At with reason "inbound". A fresh AI summary is queued.

**Step 4 — The user replies:** The user's own reply joins the conversation and updates Last Activity but does not reopen a done conversation.

---

## 8. Action Catalog

### 8.1 Create Conversation

**Supports processes:** KP-1, KP-2
**Trigger:** Auto-formation from provider thread or user manual creation.
**Inputs:** Subject, is_aggregate, description (optional), entity associations (optional).
**Outcome:** New Conversation record. Communications assigned if auto-formed.
**Business Rules:** is_aggregate is immutable after creation.

### 8.2 View Conversation

**Summary:** How a Conversation record is displayed — both the Preview Card (browsing in the Detail Panel) and the full View (deep reading with timeline and CRM intelligence cards). Covers standard and aggregate Conversation variants, responsive two-column layout with dynamic column sizing and per-conversation splitter persistence, participant color-coded timeline with Sender → Recipient format, AI Intelligence Card (read-only action items), Participants Card (derived only), Entity Associations Card (including explicitly linked contacts), Children Card, and user-configurable timeline order.
**Sub-PRD:** [conversation-view-prd.md]

### 8.3 Edit Conversation

**Supports processes:** KP-4
**Trigger:** User modifies subject, description, entity associations, or status thresholds.
**Outcome:** Record updated. Event emitted.

### 8.4 Manage Membership

**Supports processes:** KP-5
**Trigger:** User adds/removes child from aggregate.
**Outcome:** Membership updated. Counts refreshed. AI fan-out queued.
**Business Rules:** Acyclic enforcement. Parent must be aggregate.

### 8.5 Archive Conversation

**Supports processes:** KP-6
**Trigger:** User archives.
**Outcome:** Soft-deleted. Reversible.

### 8.6 Conversation Formation & Stitching

**Summary:** How communications enter conversations — email-based auto-formation via provider thread IDs, participant-based default conversations for SMS/calls, manual creation, AI-suggested splitting, cross-channel stitching mechanisms, and communication segmentation (split/reference model) for multi-topic communications.
**Sub-PRD:** [conversation-formation-prd.md]

### 8.7 AI Intelligence & Review

**Summary:** The AI intelligence layer with three roles: classify & route (assign communications to conversations with confidence scoring), summarize (conversation-level AI summaries from Published Summaries), and extract intelligence (status classification, action items, key topics). The review workflow for user oversight of auto-assignments. Learning from user corrections for continuous improvement.
**Sub-PRD:** [conversation-ai-intelligence-prd.md]

### 8.8 Views & User-Defined Alerts

**Summary:** Conversation views through the Views & Grid framework with example view patterns. User-defined alerts: saved queries with triggers, frequency controls, aggregation modes, and delivery methods. No default alerts — users define exactly what they want.
**Sub-PRD:** [conversation-views-alerts-prd.md]

### 8.9 Mark Done

**Supports processes:** KP-7
**Trigger:** User chooses Mark Done on one conversation or on a selection set.
**Inputs:** One or more conversation identifiers.
**Outcome:** System Status `done`; Done At and Done By recorded; Reopened At and Reopened Reason cleared; Updated At and Updated By set. Conversations that are already done, or belong to another tenant, are skipped and counted.
**Business Rules:** §6.4. Never touches AI Status, triage, or the dismissed fields.

### 8.10 Reopen

**Supports processes:** KP-7
**Trigger:** User chooses Reopen on one conversation or on a selection set, or clicks Undo on the Mark Done toast.
**Inputs:** One or more conversation identifiers.
**Outcome:** System Status `active`; Reopened At set; Reopened Reason `user`; Done At and Done By cleared; Updated At and Updated By set. Conversations that are not done are skipped and counted.
**Business Rules:** §6.4. The automatic reopen on a new inbound communication is a system behavior, not a user action; it is part of the communication-link process and records reason `inbound`.

### 8.11 Grid Actions

Per the Views & Grid PRD §13.4, these lists replace the defaults for the conversation entity.

**Available Actions (single row):** Open in Detail Panel, Open in Full View, Edit, Mark Done or Reopen (whichever applies to the row's System Status), Delete, Copy Link.

**Available Bulk Actions (selection set):** Mark Done (n), Reopen (n), Bulk Edit, Bulk Delete, Bulk Export, Bulk Tag, Bulk Archive, Bulk Merge. Only Mark Done and Reopen are implemented in V1.1; the others remain placeholders. The context menu's bulk items and the Content Tool Bar's bulk buttons offer the same set.

---

## 9. Cross-Cutting Concerns

### 9.1 Organizational Hierarchy

```
Project (defined in Projects PRD)
  └── [via Conversation↔Project Relation Type]
        └── Aggregate Conversation (is_aggregate = true)
              ├── [Direct Communications]
              ├── Child Aggregate (nested, unlimited depth)
              │     └── Child Conversation → Communication → Segment
              └── Child Conversation → Communication
```

Every level is optional. Communications can exist unassigned. Conversations don't need aggregates or entity associations.

### 9.2 Aggregate vs. Standard Distinction

An Aggregate Conversation groups conversations about the same subject but potentially with **different people** (e.g., "Lease Negotiation" containing conversations with lawyer, accountant, and lessor). A standard Conversation groups Communications between a specific set of participants about a specific subject, potentially spanning channels.

---

## 10. Open Questions

1. **Aggregate nesting depth limit** — Should there be a soft warning at depth 4+?
2. **Conversation merge/split** — What happens to AI summaries, action items, and assignments during merge/split?
3. **Cross-account conversation merging** — When two provider accounts participate in the same thread, auto-merge or keep separate?
4. **Calendar-conversation linking** — Should calendar events auto-create placeholder conversations?
5. **Slack/Teams integration** — How do workspace/channel/thread hierarchies map?
6. **AI cost management at scale** — For high-volume tenants, how should AI processing be throttled?
7. **Conversation merge detection** — Should the system proactively suggest merges for related conversations?
8. **Opt-out granularity** — Can users exclude specific conversations, contacts, or channels from AI processing?

---

## 11. Design Decisions

### Why merge Topic into Conversation as an aggregate pattern?

Topic and Conversation were architecturally identical system object types. Topic's sole distinguishing characteristic was grouping Conversations, which parent-child membership provides. The Document/Folder precedent proved that a single entity with a boolean flag is simpler and more flexible. Merging also enables aggregates to hold their own direct Communications — something a separate Topic entity couldn't do.

### Why entity attachment via Relation Types instead of FK columns?

FK columns create rigid single-cardinality associations requiring schema changes for each new entity type. Relation Types provide many-to-many with any registered object type without schema changes. The tradeoff is slightly more complex queries, which is acceptable given the flexibility.

### Why no inheritance of entity associations?

Automatic inheritance would create confusion when children relate to different entities than parents. Explicit, independent associations at every level prevent surprising behavior and give users full control.

### Why many-to-many conversation membership?

A conversation about "Contract Terms" might logically belong to both "Lease Negotiation" and "Legal Review" aggregates. Single-parent restriction would force artificial duplication. The Documents PRD established this pattern.

### Why derived participants instead of a Conversation→Contact Relation Type?

Storing participants would create data duplication requiring reconciliation on every communication add/remove. Deriving from Communications is always current and maintenance-free.

### Why conversation_id FK on Communications instead of a junction table?

A communication belongs to at most one conversation (many:1). Segments handle content spanning conversations. An FK column is simplest for this cardinality.

### Why configurable stale/closed thresholds?

Different conversations have different natural cadences. Per-conversation thresholds let users tune lifecycle detection to their reality.

### Why no default alerts?

Alert fatigue is the #1 reason CRM users disable notifications. Requiring explicit creation ensures every notification is wanted.

---

## Related Documents

| Document | Relationship |
|---|---|
| [Conversation Entity TDD](conversation-entity-tdd.md) | Technical decisions for conversation implementation |
| [Formation & Stitching Sub-PRD](conversation-formation-prd.md) | How communications enter conversations |
| [View Conversation Sub-PRD](conversation-view-prd.md) | Preview Card and full View rendering for standard and aggregate Conversations |
| [AI Intelligence & Review Sub-PRD](conversation-ai-intelligence-prd.md) | AI classification, summarization, extraction, review workflow |
| [Views & Alerts Sub-PRD](conversation-views-alerts-prd.md) | Conversation views and user-defined alerts |
| [Communications Entity Base PRD](communication-entity-base-prd.md) | The atomic communication records conversations group |
| [Communication Published Summary Sub-PRD](communication-published-summary-prd.md) | Summary content rendered in conversation timeline |
| [Projects PRD](projects-prd.md) | Project entity definition |
| [Custom Objects PRD](custom-objects-prd.md) | Unified object model |
| [Master Glossary](glossary.md) | Term definitions |

---

## 12. Done State — Task List and Test Plan (V1.1)

Implementation tracking for §6.4, §6.5, KP-7 and §8.9–8.11. Technical decisions are in the Entity TDD §9.8–9.14.

### 12.1 Tasks

- [x] CONV-DN-01: Schema v34 — `done_at`, `done_by`, `reopened_at`, `reopened_reason` on conversations; fresh-database DDL; migration registered in the migrate command.
- [x] CONV-DN-02: One link helper — a single function links communications to a conversation, recomputes counts and activity timestamps, clears the summary stamp, and reopens on inbound; used by mail sync, outbound send, and manual assignment.
- [x] CONV-DN-03: Mark Done and Reopen endpoints — bulk-capable, tenant-checked, record Done By / Updated By, return done, reopened and skipped counts.
- [x] CONV-DN-04: Grid engine hides `done` unless a filter names System Status; the Status field becomes a select (active, stale, done); Done At and Reopened At are available as columns.
- [x] CONV-DN-05: Quick filters — Active, Done, AI open, AI closed, AI uncertain; one-line hidden-done note.
- [x] CONV-DN-06: Row context menu — Mark Done or Reopen in single-row mode; Mark Done (n) and Reopen (n) in bulk mode. Content Tool Bar bulk mode — Mark Done (n) and Reopen (n).
- [x] CONV-DN-07: Preview Card and full View — Mark Done or Reopen button beside the status badge; Done badge in grey; Metadata card rows for Done At, Done By, Reopened At, Reopened Reason.
- [x] CONV-DN-08: Undo link on the Mark Done toast.
- [ ] CONV-DN-09 (deferred, not in v10.44): Timed stale and auto-close transitions in the scheduler, with the decision on whether a timed close shares the `done` value.
- [ ] CONV-DN-10 (deferred, not in v10.44): Hide dismissed conversations in the grid; recompute counts and activity after a communications-grid archive.

### 12.2 Test Plan

- [x] CONV-DNT-01: Migration v34 adds the four columns, is idempotent when run twice, and sets the schema version.
- [x] CONV-DNT-02: Mark Done sets `done`, Done At, Done By and Updated By; a second Mark Done is a counted no-op.
- [x] CONV-DNT-03: Reopen by the user sets `active`, Reopened Reason `user`, and clears Done At and Done By.
- [x] CONV-DNT-04: Linking an inbound communication to a done conversation reopens it with reason `inbound` and clears the summary stamp.
- [x] CONV-DNT-05: Linking an outbound communication to a done conversation updates counts and activity and leaves it done.
- [x] CONV-DNT-06: Manual assignment recomputes counts and activity timestamps.
- [x] CONV-DNT-07: Grid data omits done rows by default and includes them when a saved or quick filter names System Status.
- [x] CONV-DNT-08: Mark Done and Reopen skip conversations of another tenant and report the skipped count.
- [x] CONV-DNT-09: Preview and full-view payloads carry Done At, Done By name, Reopened At and Reopened Reason.
- [x] CONV-DNT-10: Mark Done leaves AI Status and the dismissed fields unchanged.
- [x] CONV-DNT-11 (front end): the conversation quick-filter definitions contain Active and Done chips on System Status and AI-prefixed chips on AI Status.
- [x] CONV-DNT-12 (front end): the status badge helper renders `done` as "Done" in the grey style and `active` as "Active" in the green style.

---

## 13. Change Log

| Rev | Date (MM-DD-YY HH:MM) | Author | Change |
|---|---|---|---|
| 1.1 | 10-22-26 22:55 | Claude (Claude Code) | Done state: §1.4 fields, §6.1 values and transitions, §6.3 note, §6.4 Done and Reopen, §6.5 dismissed, KP-3 step 1, KP-7, §8.9–8.11, §12 tasks and tests. Six decisions approved by Doug 10-22-26; design session 10-11-26 (`docs/prompts/conversation-done-state-kickoff.md`). |
| 1.0 | 02-23-26 | Doug (Claude.ai) | Original document. |
