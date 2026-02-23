# Conversation — Entity Base PRD

**Version:** 1.0
**Last Updated:** 2026-02-23
**Status:** Draft
**Product PRD:** [CRMExtender Product PRD]

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
| System Status | Time-based, auto-managed lifecycle state. | Yes | Override (user can manually close) | Yes | Yes | `active`, `stale`, `closed` |
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
| Stale After Days | Configurable threshold for stale detection. | No | Direct | No | No | Positive integer. Default: 14. |
| Closed After Days | Configurable threshold for auto-close. | No | Direct | No | No | Positive integer. Default: 30. |
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

**System Status (system_status)** — Time-based, auto-managed:

| Value | Trigger |
|---|---|
| `active` | New communication within the activity window |
| `stale` | No activity for N days (configurable via stale_after_days, default: 14) |
| `closed` | No activity for M days (configurable via closed_after_days, default: 30), or user manual close |

Transitions: active ↔ stale ↔ closed — any state reopens to `active` when a new communication arrives.

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

**Step 1 — Default view loads:** Grid shows conversations with columns per view configuration. Default sort: last_activity_at descending.

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

---

## 8. Action Catalog

### 8.1 Create Conversation

**Supports processes:** KP-1, KP-2
**Trigger:** Auto-formation from provider thread or user manual creation.
**Inputs:** Subject, is_aggregate, description (optional), entity associations (optional).
**Outcome:** New Conversation record. Communications assigned if auto-formed.
**Business Rules:** is_aggregate is immutable after creation.

### 8.2 View Conversation

**Supports processes:** KP-3, KP-4
**Trigger:** User navigates to conversation detail.
**Outcome:** Timeline with Published Summary cards, AI panel, entity associations.

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
| [AI Intelligence & Review Sub-PRD](conversation-ai-intelligence-prd.md) | AI classification, summarization, extraction, review workflow |
| [Views & Alerts Sub-PRD](conversation-views-alerts-prd.md) | Conversation views and user-defined alerts |
| [Communications Entity Base PRD](communication-entity-base-prd.md) | The atomic communication records conversations group |
| [Communication Published Summary Sub-PRD](communication-published-summary-prd.md) | Summary content rendered in conversation timeline |
| [Projects PRD](projects-prd.md) | Project entity definition |
| [Custom Objects PRD](custom-objects-prd.md) | Unified object model |
| [Master Glossary](glossary.md) | Term definitions |
