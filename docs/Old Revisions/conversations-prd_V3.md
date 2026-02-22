# Product Requirements Document: Conversations

## CRMExtender — Organizational Hierarchy, AI Intelligence & Conversation Lifecycle

**Version:** 2.0
**Date:** 2026-02-19
**Status:** Draft — Fully reconciled with Custom Objects PRD
**Parent Document:** [CRMExtender PRD v1.1](PRD.md)

> **V2.0 (2026-02-19):**
> Major architectural restructuring:
> - **Topic eliminated as a separate system object type.** Topic's role absorbed into Conversation via `is_aggregate` flag. The `top_` prefix is retired. Aggregate Conversations group child Conversations the same way Document Folders group Documents.
> - **Conversation membership is many-to-many** via `conversation_members` junction table, mirroring the Documents `document_folder_members` pattern. A child Conversation can belong to multiple aggregate Conversations simultaneously. Aggregate Conversations can hold both direct Communications AND child Conversations.
> - **Conversations attach to any entity via Relation Types** — no FK columns. `topic_id` and `project_id` removed from the Conversations table. System Relation Types (Conversation↔Project, Conversation↔Company, Conversation↔Contact, Conversation↔Event) ship out of the box. No inheritance — entity links are independent of parent aggregate links.
> - **Project extracted to its own PRD.** Project definition, field registry, sub-project hierarchy, and all Project-specific content moved to the [Projects PRD](projects-prd_V1.md).
> - **Conversation timeline references Published Summaries** from the [Communications PRD](communications-prd_V2.md) Section 7. The Conversation is a presentation container that assembles summary references — it does not copy or store Communication content.
> - **AI classification updated** to suggest aggregate Conversation placement (replacing Topic assignment).
> - **Sub-Conversation nesting is unlimited** with application-level acyclic enforcement, same pattern as Document folder nesting.
>
> **V1.0 (2026-02-18):**
> This document is one of two sibling PRDs extracted from the monolithic Communication & Conversation Intelligence PRD v2.0 (2026-02-07). That document has been decomposed into:
> 
> - **[Communications PRD](communications-prd_V1.md)** — The Communication entity, common schema, provider adapter framework, contact association, triage filtering, multi-account management, attachments, and storage. The foundation that channel-specific child PRDs build on.
> - **This PRD (Conversations)** — The Conversation, Topic, and Project entity types, the organizational hierarchy, AI intelligence layer (classify & route, summarize, extract intelligence), conversation lifecycle, cross-channel stitching, communication segmentation, the review workflow, conversation views, and user-defined alerts.
> 
> All content has been reconciled with the [Custom Objects PRD](custom-objects-prd.md) Unified Object Model:
> 
> - Conversation is a **system object type** (`is_system = true`, prefix `cvr_`) with registered behaviors for AI status detection, summarization, action item extraction, and summary generation. Conversations with `is_aggregate = true` serve as organizational containers (replacing the former Topic entity).
> - Project is defined in the [Projects PRD](projects-prd_V1.md) as a separate system object type (`prj_`). This PRD defines Conversation-side behaviors; the Projects PRD defines Project-specific content.
> - Entity IDs use **prefixed ULIDs** per the platform-wide convention.
> - Conversation→Communication membership is a **FK column** (`conversation_id`) on the `communications` table (defined in the Communications PRD).
> - Conversation→Contact participation is derived from Communication Participants — no separate Conversation→Contact relation is needed.
> - Topic→Project and Conversation→Topic assignments are **FK columns** on their respective tables.
> - Sub-project hierarchy uses a **self-referential Relation Type** on Project (parent_project→child_project).
> - `ai_status` and `system_status` are **Select fields** on the Conversation field registry. `is_aggregate` is a **Checkbox field** (immutable after creation).
> - All entity stores use **per-entity-type event tables** per Custom Objects PRD Section 19.
> - All SQL uses **PostgreSQL** syntax with `TIMESTAMPTZ` timestamps and schema-per-tenant isolation.

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Problem Statement](#2-problem-statement)
3. [Goals & Success Metrics](#3-goals--success-metrics)
4. [User Personas & Stories](#4-user-personas--stories)
5. [Conversation as System Object Type](#5-conversation-as-system-object-type)
6. [Aggregate Conversations](#6-aggregate-conversations)
7. [Conversation Membership](#7-conversation-membership)
8. [System Relation Types](#8-system-relation-types)
9. [Organizational Hierarchy](#9-organizational-hierarchy)
10. [Conversation Formation](#10-conversation-formation)
11. [Multi-Channel Conversations](#11-multi-channel-conversations)
12. [Communication Segmentation & Cross-Conversation References](#12-communication-segmentation--cross-conversation-references)
13. [AI Intelligence Layer](#13-ai-intelligence-layer)
14. [The Review Workflow](#14-the-review-workflow)
15. [Learning from User Corrections](#15-learning-from-user-corrections)
16. [Conversation Lifecycle & Status Management](#16-conversation-lifecycle--status-management)
17. [Conversation Views & Dashboards](#17-conversation-views--dashboards)
18. [User-Defined Alerts](#18-user-defined-alerts)
19. [Event Sourcing & Temporal History](#19-event-sourcing--temporal-history)
20. [Virtual Schema & Data Sources](#20-virtual-schema--data-sources)
21. [API Design](#21-api-design)
22. [Design Decisions](#22-design-decisions)
23. [Phasing & Roadmap](#23-phasing--roadmap)
24. [Dependencies & Related PRDs](#24-dependencies--related-prds)
25. [Open Questions](#25-open-questions)
26. [Future Work](#26-future-work)
27. [Glossary](#27-glossary)

---

## 1. Executive Summary

The Conversations subsystem aggregates, organizes, and summarizes electronic and analog Conversations between various Contacts. Conversations may be standalone, or organized into aggregate Conversations and associated with any entity in the system (Project, Company, Event, Task, custom objects) via Relation Types. The primary goal is to make it easy for users to review all forms of electronic communications relevant to their need. While the Communications PRD defines the atomic interaction record and its Published Summary, this PRD defines how those records are grouped, organized, and enriched with AI-generated intelligence to reflect how professionals actually think about their work.

When a Communication is received, the system processes it to determine the recipients and whether it is related to previous, existing Conversations. The Communication's Published Summary (Communications PRD Section 7) is what appears in the Conversation timeline — a rich text distillation that eliminates redundant or unnecessary information. Because all Communications are preserved, a user can navigate from any summary to the original Communication to review the full content.

Conversations can be organized into a flexible, optional hierarchy: **Aggregate Conversations** group related child Conversations (and can hold their own direct Communications), while **Projects** (defined in the Projects PRD) provide higher-level business context via Relation Types. A lease negotiation project might have a "Legal Review" aggregate conversation containing conversations with a lawyer and an accountant, alongside an "Inspections" aggregate conversation with conversations involving contractors. Every level is optional — Communications can exist unassigned, Conversations don't require aggregate parents or Project associations.

The AI intelligence layer serves three roles: **classify & route** incoming Communications into Conversations and suggest aggregate Conversation placement, **summarize** Conversation content across all channels, and **extract intelligence** (status, action items, key topics). Auto-organization happens silently when confidence is high and is flagged for user review when confidence is low, creating a human-in-the-loop learning system that improves over time.

**Core principles:**

- **Conversation as the unified entity** — Conversation (`cvr_`) is the single system object type in this PRD, in the Custom Objects unified framework. Conversations with `is_aggregate = true` serve as organizational containers (replacing the former Topic entity). The `top_` prefix is retired. Projects are defined in the Projects PRD as a separate entity. Users can extend Conversations with custom fields.
- **Optional, flexible hierarchy** — The hierarchy is a tool, not a requirement. Every level is optional. Communications can exist unassigned. Conversations can be standalone or nested within aggregate Conversations. Conversations attach to any entity (Project, Company, Contact, Event, custom objects) via Relation Types, not FK columns. The hierarchy helps users organize— it never forces structure.
- **AI-powered auto-organization with human oversight** — The system automatically classifies, routes, and groups Communications. High-confidence assignments happen silently. Low-confidence assignments are flagged for review. Users correct mistakes. The system learns from corrections. AI suggests aggregate Conversation placement with the same confidence/review model.
- **Published Summary timeline** — The Conversation timeline assembles an ordered sequence of references to its Communications' Published Summaries (Communications PRD Section 7). The Conversation is a presentation container — it does not copy or store Communication content. Each summary card is expandable to the full original Communication.
- **Cross-channel continuity** — A conversation can span email, SMS, phone, and video. Communications from all channels are sequenced by timestamp into a single coherent timeline. Email thread IDs provide automatic stitching; other channels use participant-based defaults with AI and user refinement.
- **Intelligence-first** — Every conversation of sufficient substance has an AI-generated summary, status classification, action items, and topic tags. Content is cleaned of noise (by the Communications PRD pipeline) before AI processing.
- **Event-sourced history** — All mutations to Conversations are stored as immutable events, enabling full audit trails and point-in-time reconstruction.

**Relationship to other PRDs:**

- **[Custom Objects PRD](custom-objects-prd.md)** — Conversation is a system object type. Table structure, field registry, event sourcing, and relation model are governed by the Custom Objects framework. This PRD defines the Conversation-specific behaviors registered with the framework.
- **[Communications PRD](communications-prd_V2.md)** — Communications are the atomic records that Conversations group. The Communications PRD defines the Communication entity, common schema, provider adapters, triage, contact resolution, and the Published Summary system (Section 7). Communications reference their parent Conversation via `conversation_id`. The Conversation timeline renders Communication Published Summaries by reference.
- **[Projects PRD](projects-prd_V1.md)** — Projects are defined as a separate system object type (`prj_`). Conversations associate with Projects via the Conversation↔Project system Relation Type. The Projects PRD defines Project-specific content (field registry, sub-project hierarchy, lifecycle).
- **[Contact Management PRD](contact-management-prd_V4.md)** — Conversation participants are derived from Communication Participants. Communication frequency within conversations feeds relationship strength scoring.
- **[Event Management PRD](events-prd_V2.md)** — Events link to Conversations through the Event→Conversation Relation Type (`event_conversations`). Meeting follow-up emails and pre-meeting coordination threads are correlated with their triggering events.
- **[Notes PRD](notes-prd_V2.md)** — Notes attach to Conversations as supplementary commentary (meeting observations, strategic context). Notes use the Universal Attachment Relation pattern. Communication Published Summaries share the same rich text content architecture as Notes.
- **[Data Sources PRD](data-sources-prd.md)** — Virtual schema tables for Conversation are derived from the field registry.
- **[Views & Grid PRD](views-grid-prd_V3.md)** — Conversation views, filters, sorts, and inline editing operate on fields from the Conversation field registry.
- **[Permissions & Sharing PRD](permissions-sharing-prd_V1.md)** — Conversation record access follows the standard role-based access model.
- **[AI Learning & Classification PRD](ai-learning-prd.md)** (future) — This PRD establishes that the system learns from corrections; the AI PRD defines how (classification algorithms, embedding/similarity approaches, model training, confidence scoring).

---

## 2. Problem Statement

Even when individual communications are captured perfectly (the Communications PRD's job), users still face organizational challenges:

| Pain Point                      | Impact                                                                                                                                                                               |
| ------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **No thread context**           | Individual messages are logged without conversation context. A 15-message negotiation thread appears as 15 disconnected entries.                                                     |
| **No organizational structure** | CRM tools provide no way to group conversations by project or topic. A complex deal with legal, financial, and technical workstreams appears as a flat list.                         |
| **No cross-channel continuity** | An email thread, a follow-up SMS, and a phone call about the same topic appear as three unrelated items.                                                                             |
| **No proactive intelligence**   | Communication content is rich with signals — pending action items, open questions, sentiment shifts — but extracting them requires reading every thread and listening to every call. |
| **Manual organization burden**  | Without auto-organization, users must manually categorize every communication. Most give up, leaving data unstructured.                                                              |
| **No engagement visibility**    | Without systematic conversation-level analysis, managers cannot see which relationships are active, stale, or at risk.                                                               |

The Conversations subsystem addresses this by providing a flexible organizational hierarchy, AI-powered auto-organization with human oversight, and conversation-level intelligence that surfaces what matters without requiring users to read every message.

---

## 3. Goals & Success Metrics

### Goals

1. **Flexible organizational hierarchy** — Aggregate Conversations and nested child Conversations provide optional structure. Conversations associate with any entity (Project, Company, etc.) via Relation Types. Users organize as much or as little as they want.
2. **Automatic conversation formation** — Email threads auto-create conversations via provider thread IDs. SMS and calls form participant-based default conversations. AI suggests refinements.
3. **AI auto-organization** — The system automatically classifies Communications into Conversations and suggests aggregate Conversation placement, with configurable confidence thresholds.
4. **Conversation intelligence** — Every substantive conversation has an AI-generated summary, status classification, action items, and topic tags.
5. **Cross-channel stitching** — A conversation can contain communications from multiple channels, presented as a single chronological timeline.
6. **Human-in-the-loop learning** — Users review and correct auto-assignments. The system learns from corrections to improve future accuracy.
7. **User-empowered visibility** — Users define their own views and alerts against conversation data, rather than relying on a prescriptive dashboard.

### Success Metrics

| Metric                                | Target                                                                    | Measurement                                                    |
| ------------------------------------- | ------------------------------------------------------------------------- | -------------------------------------------------------------- |
| Conversation auto-assignment accuracy | >85% of communications assigned to the correct conversation               | User correction rate as inverse proxy                          |
| Aggregate placement accuracy           | >75% of conversations placed in the correct aggregate conversation                       | User correction rate as inverse proxy                          |
| AI summarization coverage             | 100% of non-triaged, substantive conversations summarized                 | DB query: eligible conversations with `ai_summary IS NOT NULL` |
| Action item extraction recall         | >80% of genuine action items captured                                     | Human evaluation of 100 conversation summaries                 |
| Cross-channel stitching accuracy      | >90% of related cross-channel communications in the same conversation     | Human evaluation of 100 multi-channel conversations            |
| User correction rate (declining)      | <10% of auto-assignments corrected after 90 days of use                   | Analytics: correction actions / total assignments              |
| User adoption                         | >70% of users connect at least one communication source within first week | Analytics: account connection rate                             |

---

## 4. User Personas & Stories

### Personas

| Persona                | Communication Context                                                                                   | Key Needs                                                                                                                                          |
| ---------------------- | ------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Alex — Sales Rep**   | 2 email accounts, texts clients from mobile. 80+ emails/day, 20+ SMS/day. 30 active deal conversations. | See which deals have unanswered communications across all channels. Get summaries of long threads before calls. Link conversations to deals.       |
| **Maria — Consultant** | 1 Gmail account. Frequent phone calls with clients. 40+ emails/day. 50+ client relationships.           | Track which relationships are going stale. Surface action items from emails AND call notes. Prep for meetings with full conversation history.      |
| **Jordan — Team Lead** | 1 work Outlook + shared team inbox. Team uses SMS for quick coordination. 100+ emails/day.              | Unified view of team's client conversations. Identify conversations requiring escalation. Weekly summary of open action items across all projects. |

### User Stories

#### Hierarchy & Organization

- **US-1:** As a user, I want to create projects to organize my work so that all related conversations and communications are grouped together.
- **US-2:** As a user, I want to create sub-projects within a project so that I can organize complex initiatives with multiple workstreams.
- **US-3:** As a user, I want to create aggregate conversations so that related conversations about distinct aspects of a subject are grouped together.
- **US-4:** As a user, I want to group related conversations under named aggregate conversations.
- **US-5:** As a user, I want to associate conversations with any entity — Projects, Companies, Contacts, Events — via Relation Types.
- **US-6:** As a user, I want the AI to suggest which aggregate conversation a new conversation might belong to.
- **US-7:** As a user, I want conversations and communications to be allowed to exist unassigned — not everything belongs to a project.

#### Intelligence & AI

- **US-8:** As a user, I want AI-generated summaries for conversations that have substantive content.
- **US-9:** As a user, I want the system to extract action items from conversations across all communication types.
- **US-10:** As a user, I want conversations classified by status (Open, Closed, Uncertain) so I can visually scan for threads needing attention.
- **US-11:** As a user, I want the system to learn from my corrections when I reassign communications to different conversations.

#### Cross-Channel

- **US-12:** As a user, I want to see a unified timeline for a conversation that interleaves emails, SMS, call notes, and meeting notes chronologically.
- **US-13:** As a user, I want to select a portion of a communication and assign it to a different conversation when a single email covers multiple topics.

#### Views & Alerts

- **US-14:** As a user, I want to create custom views that show me exactly the conversation data I care about, filtered and sorted my way.
- **US-15:** As a user, I want to share views with my team.
- **US-16:** As a user, I want to turn any view into an alert that notifies me when new results appear, with configurable frequency.
- **US-17:** As a user, I want no default alerts — I define only the notifications I actually want.

---

## 5. Conversation as System Object Type

### 5.1 Object Type Registration

| Attribute               | Value                                                                                                                            |
| ----------------------- | -------------------------------------------------------------------------------------------------------------------------------- |
| `name`                  | Conversation                                                                                                                     |
| `slug`                  | `conversations`                                                                                                                  |
| `type_prefix`           | `cvr_`                                                                                                                           |
| `is_system`             | `true`                                                                                                                           |
| `display_name_field_id` | → `subject` field                                                                                                                |
| `description`           | A logical grouping of related communications between specific participants about a specific subject. Can span multiple channels. When `is_aggregate = true`, serves as an organizational container for child Conversations. |

### 5.2 Registered Behaviors

| Behavior                     | Source PRD | Trigger                               |
| ---------------------------- | ---------- | ------------------------------------- |
| AI status detection          | This PRD   | On new communication added            |
| Summarization                | This PRD   | On new communication added, on demand |
| Action item extraction       | This PRD   | On new communication added            |
| Aggregate roll-up            | This PRD   | On child conversation membership change, on child content change |

### 5.3 Conversation Field Registry

**Universal fields** (per Custom Objects PRD Section 7): `id`, `tenant_id`, `created_at`, `updated_at`, `created_by`, `updated_by`, `archived_at`.

**Core system fields** (`is_system = true`, protected):

| Field                | Column                 | Type                | Required | Description                                                                          |
| -------------------- | ---------------------- | ------------------- | -------- | ------------------------------------------------------------------------------------ |
| Subject              | `subject`              | Text (single-line)  | NO       | Derived from email subject, or user-defined. Display name field.                     |
| Is Aggregate         | `is_aggregate`         | Checkbox            | YES      | `true` = organizational container for child Conversations. `false` = standard. **Immutable after creation.** Default: `false`. |
| Description          | `description`          | Text (multi-line)   | NO       | Optional description of the Conversation's scope. Primarily useful for aggregate Conversations. |
| System Status        | `system_status`        | Select              | YES      | Time-based, auto-managed: `active`, `stale`, `closed`. Default: `active`.            |
| AI Status            | `ai_status`            | Select              | NO       | Semantic, from AI analysis: `open`, `closed`, `uncertain`. NULL until AI processes.  |
| AI Summary           | `ai_summary`           | Text (multi-line)   | NO       | AI-generated 2–4 sentence narrative of conversation state.                           |
| AI Action Items      | `ai_action_items`      | Text (multi-line)   | NO       | JSON-encoded list of extracted action items with assignee and deadline.              |
| AI Key Topics        | `ai_key_topics`        | Text (multi-line)   | NO       | JSON-encoded list of 2–5 short topic phrases.                                        |
| AI Confidence        | `ai_confidence`        | Number (decimal)    | NO       | Confidence score for the AI's conversation assignment (0.0–1.0).                     |
| AI Last Processed At | `ai_last_processed_at` | Datetime            | NO       | When AI last analyzed this conversation.                                             |
| Communication Count  | `communication_count`  | Number (integer)    | NO       | Denormalized count of communications. Updated on add/remove.                         |
| Channel Breakdown    | `channel_breakdown`    | Text (single-line)  | NO       | JSON-encoded count by channel (e.g., `{"email": 5, "sms": 2, "phone_recorded": 1}`). |
| First Activity At    | `first_activity_at`    | Datetime            | NO       | Timestamp of the earliest communication.                                             |
| Last Activity At     | `last_activity_at`     | Datetime            | NO       | Timestamp of the most recent communication. Drives `system_status` transitions.      |
| Stale After Days     | `stale_after_days`     | Number (integer)    | NO       | Configurable threshold for stale detection. Default: 14.                             |
| Closed After Days    | `closed_after_days`    | Number (integer)    | NO       | Configurable threshold for auto-close. Default: 30.                                  |

### 5.4 Read Model Table

```sql
-- Within tenant schema: tenant_abc.conversations
CREATE TABLE conversations (
    -- Universal fields
    id                  TEXT PRIMARY KEY,        -- cvr_01HX8A...
    tenant_id           TEXT NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by          TEXT REFERENCES platform.users(id),
    updated_by          TEXT REFERENCES platform.users(id),
    archived_at         TIMESTAMPTZ,

    -- Core system fields
    subject             TEXT,
    is_aggregate        BOOLEAN NOT NULL DEFAULT FALSE,  -- Immutable after creation
    description         TEXT,
    system_status       TEXT NOT NULL DEFAULT 'active',
    ai_status           TEXT,
    ai_summary          TEXT,
    ai_action_items     TEXT,                   -- JSON
    ai_key_topics       TEXT,                   -- JSON
    ai_confidence       NUMERIC(3,2),
    ai_last_processed_at TIMESTAMPTZ,
    communication_count INTEGER DEFAULT 0,
    channel_breakdown   TEXT,                   -- JSON
    first_activity_at   TIMESTAMPTZ,
    last_activity_at    TIMESTAMPTZ,
    stale_after_days    INTEGER DEFAULT 14,
    closed_after_days   INTEGER DEFAULT 30
);

-- Indexes
CREATE INDEX idx_cvr_aggregate ON conversations (is_aggregate) WHERE is_aggregate = TRUE;
CREATE INDEX idx_cvr_system_status ON conversations (system_status);
CREATE INDEX idx_cvr_ai_status ON conversations (ai_status) WHERE ai_status IS NOT NULL;
CREATE INDEX idx_cvr_last_activity ON conversations (last_activity_at DESC);
CREATE INDEX idx_cvr_archived ON conversations (archived_at) WHERE archived_at IS NULL;
```

### 5.5 Derived Participant List

Conversation participants are **not** stored on the Conversation record. They are derived from the union of Communication Participants across all communications in the conversation:

```sql
-- "Who is involved in this conversation?"
SELECT DISTINCT cp.contact_id, con.display_name
FROM communications c
JOIN communication_participants cp ON cp.communication_id = c.id
JOIN contacts con ON con.id = cp.contact_id
WHERE c.conversation_id = 'cvr_01HX8A...'
  AND c.archived_at IS NULL;
```

This avoids data duplication and ensures the participant list is always current as communications are added or removed.

---

## 6. Aggregate Conversations

### 6.1 Concept

An **Aggregate Conversation** is a Conversation with `is_aggregate = true`. It serves as an organizational container that groups related child Conversations — the same role previously played by the Topic entity. This follows the Document/Folder precedent from the Documents PRD, where folders are Documents with `is_folder = true`.

Unlike Document Folders (which are pure containers that cannot hold file content), Aggregate Conversations can hold **both** direct Communications AND child Conversations simultaneously. An "Acme Lease Negotiation" aggregate might have its own Communications (general coordination emails about the deal) plus child Conversations with specific parties (lawyer, accountant, lessor).

### 6.2 Aggregate vs. Standard Conversation

| Aspect | Standard Conversation (`is_aggregate = false`) | Aggregate Conversation (`is_aggregate = true`) |
|---|---|---|
| Contains Communications | Yes — via `conversation_id` FK on Communications | Yes — can have its own direct Communications |
| Contains child Conversations | No | Yes — via `conversation_members` junction table |
| AI Summary | Synthesizes across its Communications' Published Summaries | Synthesizes across its own Communications PLUS all child Conversation summaries |
| Communication Count | Count of direct Communications | Direct Communications + sum of all children's Communications |
| Can be a child of an aggregate | Yes | Yes (aggregates can nest inside other aggregates) |
| `is_aggregate` mutability | Immutable | Immutable |

### 6.3 Aggregate Conversation Example

```
Aggregate Conversation: Lease Negotiation (is_aggregate = true)
  ├── [Direct Communications]
  │     ├── Email: General timeline discussion with team
  │     └── Note: Internal strategy notes
  ├── Conversation with Lawyer (3 emails, 1 phone call)
  ├── Conversation with Accountant (2 emails)
  └── Conversation with Lessor (5 emails, 1 in-person meeting)
```

Three child Conversations with different participants about the same subject, plus the aggregate's own Communications about general coordination. The aggregate's AI summary synthesizes everything — "The lease negotiation is progressing. Legal has approved the liability cap at $500K. Accounting has flagged a tax implication. The lessor has agreed to a March 15 signing target."

### 6.4 Nesting

Aggregate Conversations can nest within other aggregate Conversations, enabling unlimited hierarchical depth — the same pattern as Document folders. This replaces the former Topic → Sub-Topic concept.

```
Aggregate: 2026 Expansion
  ├── Aggregate: NYC Office
  │     ├── Aggregate: Lease Negotiation
  │     │     ├── Conversation with Lawyer
  │     │     ├── Conversation with Accountant
  │     │     └── Conversation with Lessor
  │     ├── Aggregate: Hiring
  │     │     ├── Conversation with Recruiter
  │     │     └── Conversation with HR Consultant
  │     └── Conversation: General NYC coordination
  └── Aggregate: London Office
        ├── Aggregate: Lease Negotiation
        └── Aggregate: Visa Sponsorship
```

Application-level acyclic enforcement prevents circular references (see Section 7.4).

### 6.5 Immutability of `is_aggregate`

The `is_aggregate` flag is **immutable after creation**. A standard Conversation cannot be converted to an aggregate, and vice versa. This ensures:

- UI behavior is deterministic (aggregate views render child Conversation cards; standard views render Communication summaries).
- Denormalized counts and AI summaries don't need to handle structural changes.
- API consumers can rely on the entity type being stable.

If a user realizes a standard Conversation should be an aggregate, they create a new aggregate Conversation and move the original into it as a child.

---

## 7. Conversation Membership

### 7.1 Many-to-Many Model

Child Conversations belong to aggregate Conversations via a **many-to-many** junction table, mirroring the `document_folder_members` pattern from the Documents PRD. A single Conversation can belong to multiple aggregate Conversations simultaneously.

### 7.2 Junction Table

```sql
CREATE TABLE conversation_members (
    parent_conversation_id  TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    child_conversation_id   TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    added_by                TEXT REFERENCES platform.users(id),
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    PRIMARY KEY (parent_conversation_id, child_conversation_id)
);

CREATE INDEX idx_cvr_members_child ON conversation_members (child_conversation_id);
CREATE INDEX idx_cvr_members_parent ON conversation_members (parent_conversation_id);
```

### 7.3 Membership Rules

| Rule | Enforcement |
|---|---|
| Parent must have `is_aggregate = true` | CHECK constraint or application-level validation on insert |
| Child can be standard or aggregate | No restriction — enables nesting |
| A Conversation can belong to multiple parents | Many-to-many by design |
| No self-membership | CHECK constraint: `parent_conversation_id != child_conversation_id` |
| No circular references | Application-level acyclic check (Section 7.4) |
| Membership does not imply inheritance | Child entity links are independent of parent's entity links |

### 7.4 Acyclic Enforcement

Before inserting a membership row `(parent_id, child_id)`, the system walks the ancestry chain of `parent_id` to verify that `child_id` does not appear anywhere in the chain. This prevents circular references:

```
To add child C to parent P:
  1. Walk P's ancestry: P → P's parents → P's grandparents → ...
  2. If C appears anywhere in the chain, REJECT (would create cycle)
  3. Otherwise, INSERT the membership row
```

This is the same algorithm used for Document folder nesting (Documents PRD Section 7.4).

### 7.5 Denormalized Counts

Aggregate Conversations maintain denormalized counts that include both direct and child Communications:

| Field | Calculation |
|---|---|
| `communication_count` | Direct Communications + SUM of all children's `communication_count` (recursive) |
| `channel_breakdown` | Merged JSON across direct + all children |
| `first_activity_at` | MIN across direct + all children |
| `last_activity_at` | MAX across direct + all children |

These are updated when:
- A Communication is added/removed from the aggregate or any child.
- A child Conversation is added/removed from the aggregate.
- A child's counts change (fans out to all parent aggregates).

### 7.6 AI Summary Fan-Out

When a child Conversation's content changes (new Communication added, summary revised), the AI re-summarization fans out to all parent aggregate Conversations. The aggregate's AI summary is refreshed to incorporate the updated child content.

---

## 8. System Relation Types

### 8.1 Entity Attachment via Relation Types

Conversations attach to other entities exclusively through **system Relation Types**, not FK columns. There are no `topic_id`, `project_id`, `company_id`, or similar FK columns on the Conversations table. This approach provides:

- **Universal attachment** — Conversations can associate with any registered object type, including custom objects, without schema changes.
- **Many-to-many** — A single Conversation can be associated with multiple Projects, Companies, or Contacts simultaneously.
- **No inheritance** — A child Conversation's entity links are independent of its parent aggregate's links. If an aggregate Conversation is associated with Project X, its children do NOT automatically inherit that association.
- **Consistency** — Same Relation Type pattern used throughout the platform (Contact↔Company, Event↔Conversation, etc.).

### 8.2 System Relation Type Definitions

The following system Relation Types ship out of the box:

| Relation Type | Slug | Source | Target | Cardinality | Notes |
|---|---|---|---|---|---|
| Conversation↔Project | `conversation_projects` | Conversation (`cvr_`) | Project (`prj_`) | Many-to-many | A Conversation can be associated with multiple Projects. |
| Conversation↔Company | `conversation_companies` | Conversation (`cvr_`) | Company (`cmp_`) | Many-to-many | Direct company association. |
| Conversation↔Contact | `conversation_contacts` | Conversation (`cvr_`) | Contact (`con_`) | Many-to-many | Explicit contact association (supplementing derived participants). |
| Conversation↔Event | `conversation_events` | Conversation (`cvr_`) | Event (`evt_`) | Many-to-many | Links Conversations to calendar events. Mirrors the Event Management PRD's Event→Conversation relation. |

Additional Relation Types for custom object types can be created by users through the standard Custom Objects framework.

### 8.3 Derived vs. Explicit Contact Association

Conversation participants are **derived** from the union of Communication Participants (Section 5.5). The Conversation↔Contact Relation Type provides **explicit** association for cases where the derived list is insufficient:

- A Contact is relevant to a Conversation but was never a direct participant on any Communication (e.g., a manager who should be kept informed).
- A Conversation is manually created before any Communications exist, and the user wants to link it to specific Contacts.
- A Contact's role in the Conversation is different from their role as a Communication participant (e.g., tagged as "Decision Maker" via relation metadata).

### 8.4 No Inheritance

Entity associations are **independent** at every level of the hierarchy. If an aggregate Conversation "Lease Negotiation" is associated with Project "2026 Expansion" and Company "Acme Corp":

- Child Conversation "With Lawyer" does NOT automatically inherit the Project or Company association.
- The child can have its own, different entity associations (e.g., associated with Company "Smith & Associates LLP" for the law firm).
- Users can explicitly add the same associations to children if desired.

This prevents confusion when a child Conversation naturally relates to different entities than its parent.

---

## 9. Organizational Hierarchy

### 9.1 The Hierarchy Model

```
Project (defined in Projects PRD)
  └── [via Conversation↔Project Relation Type]
        └── Aggregate Conversation (is_aggregate = true)
              ├── [Direct Communications]
              ├── Child Aggregate Conversation (nested, unlimited depth)
              │     └── Child Conversation
              │           └── Communication (defined in Communications PRD)
              │                 └── Segment (when split across conversations)
              └── Child Conversation
                    └── Communication
```

**Every level is optional.** Communications can exist unassigned. Conversations don't need to belong to an aggregate or have any entity associations. The hierarchy exists to help users organize their work — it is never forced.

### 9.2 Hierarchy Rules

| Entity | Must belong to a parent? | Can exist independently? |
|---|---|---|
| Communication | No — can be unassigned | Yes — marketing emails, unknown senders, one-offs |
| Conversation (standard) | No — doesn't need an aggregate parent or entity links | Yes — an ongoing exchange with a colleague that isn't part of any organized group |
| Conversation (aggregate) | No — doesn't need a parent aggregate or entity links | Yes — a top-level organizational container |
| Project | No — top-level entity (defined in Projects PRD) | Yes — always independent |

### 9.3 Aggregate Conversation vs. Conversation Distinction

An **Aggregate Conversation** groups conversations that are about the same subject but potentially with **different people**. Under a "Lease Negotiation" aggregate, there might be a conversation with the lawyer, one with the accountant, and one with the lessor.

A **standard Conversation** groups Communications between a **specific set of participants** about a specific subject, potentially spanning multiple channels.

This mirrors the former Topic/Conversation distinction, but with the aggregate Conversation being a first-class Conversation that can hold its own Communications.

## 10. Conversation Formation

### 10.1 Email-Based Conversations (Automatic)

Email providers supply native thread identifiers that automatically group related messages:

| Provider | Threading Mechanism                                                                                                     | Reliability                                         |
| -------- | ----------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------- |
| Gmail    | `threadId` — groups by subject and participants                                                                         | High (occasional false grouping on common subjects) |
| Outlook  | `conversationId` — groups by conversation                                                                               | High                                                |
| IMAP     | Reconstructed from RFC 5322 headers (`Message-ID`, `References`, `In-Reply-To`), with subject-line matching as fallback | Medium (JWZ algorithm, inherently less reliable)    |

An email thread automatically creates a Conversation. The `provider_thread_id` on Communication records (Communications PRD Section 5.1) links messages to conversations. Additional email threads may be merged into the same conversation by the AI or user if they are determined to be part of the same exchange.

### 10.1.1 Published Summary in the Conversation Timeline

Each Communication produces a **Published Summary** (Communications PRD Section 7) — a rich text representation that eliminates redundant or unnecessary information (quoted reply chains, email signatures, boilerplate). The Conversation timeline renders these summaries as an ordered sequence of reference cards. Each card shows the Communication's Published Summary and provides a link to the original Communication for full content review.

The Communication owns its summary; the Conversation references it. This means:
- Updating a Communication's Published Summary automatically updates how it appears in every Conversation that contains it.
- The Conversation-level `ai_summary` is a higher-order synthesis across its Communications' Published Summaries, not a re-analysis of raw content.
- Summary revision history (Communications PRD Section 7.6) enables audit trail reconstruction of what information was visible when decisions were made.

### 10.2 Participant-Based Conversations (SMS, Calls)

For channels without native threading (SMS, phone calls), the system creates **default participant-based conversations**:

- All SMS messages between the same set of participants form a single default conversation: "SMS with Bob" or "Group SMS with Bob, Alice, and Carol."
- This is a catch-all stream containing all SMS exchanges with that participant set, regardless of topic.
- Users can select specific messages from this default conversation and assign them to topic-specific conversations.

### 10.3 Manually Created Conversations

Users can create conversations explicitly and assign communications to them. This is the primary model for:

- Organizing phone call and meeting notes into topic-specific conversations.
- Pulling SMS messages out of the default participant-based conversation.
- Creating a conversation around communications from multiple channels.

### 10.4 AI-Suggested Splitting

When the AI detects a communication doesn't fit the current conversation (different subject, different context), it may suggest creating a new conversation. This is presented as a suggestion for user confirmation, never automatic.

---

## 11. Multi-Channel Conversations

### 11.1 Cross-Channel Continuity

A conversation can contain communications from multiple channels. The system maintains continuity through timestamp sequencing (Communications PRD Section 5.3):

- An email thread forms the backbone of a conversation.
- An SMS sent 30 minutes after the last email, between the same participants, is likely part of the same conversation.
- A phone call note logged by the user and assigned to the conversation appears in the timeline at the correct chronological position.

### 11.2 Stitching Mechanisms

**Automatic stitching (email only):** Email thread IDs provide reliable automatic conversation assignment. This is handled during sync by the email provider adapter.

**Manual stitching (other channels):** SMS, calls, and meetings must be assigned to conversations by the user (or by AI with user review) because there is no reliable automatic mechanism to determine which conversation they belong to.

**AI-assisted stitching (future):** The AI may suggest cross-channel assignments based on participant overlap, temporal proximity, and content similarity. These are always presented as suggestions for user confirmation.

### 11.3 Multi-Channel Formatting for AI

When the AI processes a Conversation for summarization, it consumes the Published Summaries of each Communication (Communications PRD Section 7). The prompt includes channel markers so the AI understands the communication type:

```
Subject: Lease Negotiation — Clause 5

[EMAIL] From: Bob Smith
Date: 2026-02-07 10:15
Contract draft attached. Please review clause 5 regarding liability caps.

---

[SMS] From: Me → Bob Smith
Date: 2026-02-07 12:45
Hey, did you see my questions?

---

[PHONE] Participants: Me, Bob Smith
Date: 2026-02-07 15:00 (12 min)
[Transcript]: Discussed clause 5 revisions. Bob agreed to cap liability at $500K.

---

[EMAIL] From: Bob Smith
Date: 2026-02-07 18:30
Here's the revised clause 5 with the $500K liability cap we discussed.
```

---

## 12. Communication Segmentation & Cross-Conversation References

### 12.1 The Problem

A single communication may address multiple topics. An email might say: "Attached is the contract you asked about. Also, are we still on for the team offsite planning?" — that's two topics, potentially two conversations.

### 12.2 The Solution: Split/Reference Model

**Primary assignment (automatic):** Each communication is automatically assigned to its primary conversation (via email thread ID, participant matching, or AI classification). The full communication lives in the primary conversation.

**Segment creation (user-driven):** When a user identifies that a communication spans two conversations, they select a portion of the text. They invoke an "Assign selected to different conversation" action. This creates a **Segment** — the selected text assigned to the target conversation. The original communication now has references in both conversations.

**What the user sees:**

- In the primary conversation: the full communication, with the segmented portion highlighted or annotated.
- In the secondary conversation: the segment (selected text), with a link back to the full original communication.

**What is preserved:**

- The original communication is never modified or moved.
- The segment is an additional reference, not a copy.
- Both conversations show contextually relevant content.

### 12.3 Segment Data Model

Segments are behavior-managed records, not a separate object type:

| Attribute                | Type        | Description                                                  |
| ------------------------ | ----------- | ------------------------------------------------------------ |
| `id`                     | TEXT        | Prefixed ULID: `seg_` prefix                                 |
| `communication_id`       | TEXT        | FK → communications (the source communication)               |
| `source_conversation_id` | TEXT        | FK → conversations (where the communication primarily lives) |
| `target_conversation_id` | TEXT        | FK → conversations (where the segment is referenced)         |
| `content_start`          | INTEGER     | Character offset of selected text start                      |
| `content_end`            | INTEGER     | Character offset of selected text end                        |
| `selected_text`          | TEXT        | The extracted text (denormalized for display)                |
| `created_by`             | TEXT        | FK → users                                                   |
| `created_at`             | TIMESTAMPTZ |                                                              |

### 12.4 Future: AI-Assisted Segmentation

The AI could analyze communications at the paragraph level and suggest segments when it detects that a communication addresses multiple conversations or topics. This would be presented as a suggestion for user confirmation, not automatic. Deferred to the AI Learning & Classification PRD.

---

## 13. AI Intelligence Layer

### 13.1 AI Roles

The AI serves three distinct functions:

#### Role 1: Classify & Route

For every incoming communication, the AI attempts to determine:

- **Which conversation does this belong to?** (existing conversation, or create a new one?)
- **Which aggregate conversation should this conversation be placed in?** (existing aggregate, or suggest a new one?)
- **Confidence score** for each assignment

High-confidence assignments happen silently. Low-confidence assignments are flagged for user review.

#### Role 2: Summarize

For communications and conversations with substantive content:

- **Communication-level summary** — For long communications only (lengthy emails, call transcripts). Short communications (a 4-word SMS, a brief note) are not summarized — the content IS the summary.
- **Conversation-level summary** — Synthesizes across all communications in the conversation, regardless of channel. Updated when new communications arrive. Produces a 2–4 sentence narrative of the conversation's current state. Stored in `ai_summary` on the Conversation record.

#### Role 3: Extract Intelligence

At the conversation level:

- **Status classification** (`ai_status`) — `open` (unresolved items), `closed` (resolved), `uncertain` (insufficient context). Biased toward `open` for multi-message exchanges between known contacts.
- **Action items** (`ai_action_items`) — Specific tasks mentioned in the conversation, with identification of who is responsible and any deadlines.
- **Key topics** (`ai_key_topics`) — 2–5 short topic phrases, normalized for cross-conversation aggregation.
- **Sentiment score** (future) — Emotional tone tracking with per-communication trends.

### 13.2 Summarization Thresholds

Not all communications warrant AI summarization:

| Content Length                           | Summarize? | Rationale                                           |
| ---------------------------------------- | ---------- | --------------------------------------------------- |
| <50 words (short SMS, brief note)        | No         | The content itself is already concise enough        |
| 50–200 words (typical email)             | Optional   | May benefit from summary in conversation context    |
| >200 words (long email, call transcript) | Yes        | Substantial content that benefits from distillation |

Conversation-level summaries are always generated when the conversation has sufficient total content, regardless of individual communication lengths.

### 13.3 Re-Summarization Triggers

Conversation summaries are automatically refreshed when:

- A new Communication is added to the Conversation (any channel).
- A Communication's Published Summary is revised (summary revision created).
- A user explicitly requests a refresh.
- A Communication is reassigned to or from the Conversation.
- For aggregate Conversations: a child Conversation is added/removed, or a child's summary changes (fan-out per Section 7.6).

### 13.4 AI Error Handling

| Failure                    | Recovery                                                                              |
| -------------------------- | ------------------------------------------------------------------------------------- |
| AI API timeout             | Retry with exponential backoff (3 attempts); mark as pending                          |
| AI API rate limit          | Queue and retry after cooldown                                                        |
| Malformed AI response      | Return with error flag; log raw response                                              |
| AI API unavailable         | Conversations remain visible without summaries; queue for processing when API returns |
| Empty conversation content | Skip summarization; display "(no content to analyze)"                                 |

---

## 14. The Review Workflow

### 14.1 Purpose

Auto-organization is only useful if users can efficiently review and correct it. The system presents:

> "14 new communications since yesterday. 11 auto-assigned (review). 3 unassigned (needs your input)."

### 14.2 Review Actions

The review workflow allows users to:

- See all auto-assignments with confidence indicators
- Accept or correct conversation assignment with minimal clicks
- Accept or correct aggregate Conversation placement
- Identify unknown contacts (defers to Contact Intelligence system)
- Create new Conversations or aggregate Conversations as needed

The UI must be **extremely efficient** for this workflow — it is a daily activity that must take seconds, not minutes.

### 14.3 Confidence Display

| Confidence Level   | Display                              | User Action         |
| ------------------ | ------------------------------------ | ------------------- |
| High (>0.85)       | Green indicator, assigned silently   | Review optional     |
| Medium (0.50–0.85) | Yellow indicator, flagged for review | Review recommended  |
| Low (<0.50)        | Red indicator, left unassigned       | Assignment required |

---

## 15. Learning from User Corrections

### 15.1 The Principle

**The system learns from every user correction to improve future auto-assignment.**

When a user corrects an assignment (moves a communication to a different conversation, reassigns a topic, etc.), that correction becomes a training signal.

### 15.2 What the System Learns

Over time, the system should:

- Recognize patterns specific to each user's organizational preferences
- Learn contact-specific routing (e.g., "emails from Bob about invoices go to Accounting")
- Improve confidence thresholds based on correction rates
- Apply organizational learning across team members where appropriate

### 15.3 Deferred Details

**The details of how learning is implemented — prompt-based context, embedding similarity, fine-tuning, or hybrid approaches — are defined in the AI Learning & Classification PRD (Section 23: Related PRDs).** This PRD establishes the product requirement: the system learns from corrections and improves over time.

---

## 16. Conversation Lifecycle & Status Management

### 16.1 Three Status Dimensions

#### System Status (`system_status`)

Time-based, managed automatically:

| Value    | Trigger                                                                                          |
| -------- | ------------------------------------------------------------------------------------------------ |
| `active` | New communication within the activity window                                                     |
| `stale`  | No activity for N days (configurable via `stale_after_days`, default: 14)                        |
| `closed` | No activity for M days (configurable via `closed_after_days`, default: 30), or user manual close |

**Transitions:** `active` ↔ `stale` ↔ `closed` — any state reopens to `active` when a new communication arrives.

#### AI Status (`ai_status`)

Semantic, from AI analysis:

| Value       | Meaning                                             |
| ----------- | --------------------------------------------------- |
| `open`      | Unresolved items, pending tasks, ongoing discussion |
| `closed`    | Definitively resolved or finished                   |
| `uncertain` | Insufficient context                                |

**Bias:** Toward `open` for multi-message exchanges between known contacts. Casual sign-offs ("Thanks!") don't close a conversation.

#### Triage Status

Inherited from the Communications PRD. Whether the communication(s) in the conversation were filtered. This is orthogonal — determines whether AI analysis happens at all.

### 16.2 Status Independence

The three dimensions are independent and complementary:

- **System: active** + **AI: closed** → Recent messages, but the topic was resolved
- **System: stale** + **AI: open** → No recent activity, but the last message asked an unanswered question
- **Triage** is orthogonal — determines whether AI analysis happens at all

---

## 17. Conversation Views & Dashboards

### 17.1 View Framework Integration

Conversation views operate through the Views & Grid PRD framework. All Conversation fields from the field registry are available for filtering, sorting, grouping, and display. Views can filter by `is_aggregate` to show only aggregate or standard Conversations.

### 17.2 Example Views

| View                         | Description                                                                               |
| ---------------------------- | ----------------------------------------------------------------------------------------- |
| "My Open Action Items"       | All `ai_action_items` across all conversations where `ai_status = 'open'`, sorted by date |
| "Stale Client Conversations" | Conversations with `system_status = 'stale'`, grouped by contact                          |
| "Project X Status"           | All Conversations associated with Project X (via Relation Type), grouped by aggregate, sorted by `last_activity_at` |
| "Unassigned This Week"       | Communications from the last 7 days with `conversation_id IS NULL`                        |
| "All Comms with Bob"         | Communications where Bob is a participant, across all channels, chronological             |
| "Pending Reviews"            | Auto-assigned communications with low `ai_confidence` scores                              |

### 17.3 Shareable Views

Views can be shared with team members. A manager creates a "Team Open Action Items" view, and everyone on the team can use it. Shared views use the viewer's data permissions — sharing the view definition doesn't grant access to data the viewer wouldn't otherwise see.

### 17.4 Views as the Foundation for Alerts

Views and alerts share the same underlying architecture. An alert is a view with a trigger attached (Section 17).

---

## 18. User-Defined Alerts

### 18.1 Design Philosophy

**No default alerts.** The system sends zero notifications unless the user explicitly creates them. Users define exactly the alerts they want — no more, no less.

### 18.2 Alert Architecture

An alert is a **saved query** (view) with a **trigger**, **frequency**, and **delivery method**:

```
Saved Query (filter criteria against the data model)
  ├── Rendered as a View (pull — user opens it on demand)
  └── Attached as an Alert (push — system notifies when results change)
        ├── Frequency: Immediate, Hourly, Daily, Weekly
        ├── Aggregation: Individual (one alert per result) or Batched (digest)
        └── Delivery: In-app notification, Push notification, Email, SMS
```

### 18.3 Alert Examples

| Alert                                    | Query                                                                 | Frequency | Delivery          |
| ---------------------------------------- | --------------------------------------------------------------------- | --------- | ----------------- |
| "New communication from VIP contacts"    | Communications from contacts tagged "VIP"                             | Immediate | Push notification |
| "Conversations going stale on Project X" | Conversations under Project X with `system_status = 'stale'`          | Daily     | Email digest      |
| "Unassigned items to review"             | Communications with `conversation_id IS NULL` or low `ai_confidence`  | Daily     | In-app            |
| "Any change to the Acme Deal"            | Any new communication in any conversation under the Acme Deal project | Immediate | Push notification |
| "Weekly action item summary"             | All open `ai_action_items` across all conversations                   | Weekly    | Email digest      |

### 18.4 Frequency & Aggregation

- **Immediate + Individual:** Every matching event triggers a notification. For high-priority, low-frequency alerts.
- **Hourly/Daily + Batched:** Matching events are collected and delivered as a digest. For high-frequency monitoring.
- **Weekly + Batched:** Summary report. For oversight and review patterns.

---

## 19. Event Sourcing & Temporal History

### 19.1 Event Tables

Per Custom Objects PRD Section 19, each entity type has a companion event table:

- `conversations_events` — All mutations to Conversation records

Event table schema follows the standard pattern from Custom Objects PRD (same structure as `communications_events` in the Communications PRD Section 15.1).

### 19.2 Key Event Types

**Conversation events:**

| Event Type                | Trigger                                           | Description                        |
| ------------------------- | ------------------------------------------------- | ---------------------------------- |
| `created`                 | New conversation formed (auto or manual)          | Full record snapshot               |
| `communication_added`     | Communication assigned to this conversation       | Communication ID in metadata       |
| `communication_removed`   | Communication unassigned from this conversation   | Communication ID in metadata       |
| `member_added`            | Child Conversation added to aggregate             | Parent and child IDs in metadata   |
| `ai_processed`            | AI generated summary/status/action items          | AI output snapshot                 |
| `status_transition`       | `system_status` changed (active → stale → closed) | Old and new status                 |
| `merged`                  | Two conversations merged                          | Source conversation ID in metadata |
| `archived` / `unarchived` | Soft-delete or restore                            |                                    |

| `member_removed`          | Child Conversation removed from aggregate         | Parent and child IDs in metadata   |

Aggregate Conversation events additionally include fan-out triggers when child content changes (see Section 7.6).

---

## 20. Virtual Schema & Data Sources

### 20.1 Virtual Schema Tables

Per Data Sources PRD, each object type's field registry generates a virtual schema table:

- `conversations` — All conversation fields

### 20.2 Cross-Entity Queries

Data Source queries can traverse the hierarchy:

```sql
-- All conversations associated with a specific project (via Relation Type)
SELECT c.subject, c.ai_status, c.ai_summary, c.is_aggregate
FROM conversations c
JOIN conversation_projects cp ON c.id = cp.conversation_id
WHERE cp.project_id = 'prj_01HX7...'
ORDER BY c.last_activity_at DESC;
```

```sql
-- All child conversations within an aggregate
SELECT child.subject, child.ai_status, child.last_activity_at
FROM conversations child
JOIN conversation_members cm ON child.id = cm.child_conversation_id
WHERE cm.parent_conversation_id = 'cvr_01HX7...'
ORDER BY child.last_activity_at DESC;
```

```sql
-- All communications in a project's conversations (via Relation Type)
SELECT comm.timestamp, comm.channel, comm.subject, comm.body_preview
FROM communications comm
JOIN conversations c ON comm.conversation_id = c.id
JOIN conversation_projects cp ON c.id = cp.conversation_id
WHERE cp.project_id = 'prj_01HX7...'
ORDER BY comm.timestamp DESC;
```

---

## 21. API Design

### 21.1 Conversation CRUD API

| Endpoint                             | Method | Description                                                  |
| ------------------------------------ | ------ | ------------------------------------------------------------ |
| `/api/v1/conversations`              | GET    | List conversations (paginated, filterable, sortable)         |
| `/api/v1/conversations`              | POST   | Create a conversation                                        |
| `/api/v1/conversations/{id}`         | GET    | Get conversation with communications and participants        |
| `/api/v1/conversations/{id}`         | PATCH  | Update conversation fields (subject, entity associations, etc.) |
| `/api/v1/conversations/{id}/archive` | POST   | Archive a conversation                                       |
| `/api/v1/conversations/{id}/history` | GET    | Get event history                                            |

### 21.2 Conversation Intelligence API

| Endpoint                                    | Method | Description                                                       |
| ------------------------------------------- | ------ | ----------------------------------------------------------------- |
| `/api/v1/conversations/{id}/summarize`      | POST   | Trigger AI summarization refresh                                  |
| `/api/v1/conversations/{id}/communications` | GET    | List communications in this conversation (chronological timeline) |
| `/api/v1/conversations/{id}/participants`   | GET    | Derived participant list                                          |
| `/api/v1/conversations/{id}/segments`       | GET    | List segments referencing this conversation                       |

### 21.3 Conversation Membership API

| Endpoint                                          | Method | Description                                                       |
| ------------------------------------------------- | ------ | ----------------------------------------------------------------- |
| `/api/v1/conversations/{id}/members`              | GET    | List child Conversations (aggregate only)                         |
| `/api/v1/conversations/{id}/members`              | POST   | Add a child Conversation to this aggregate (acyclic check)        |
| `/api/v1/conversations/{id}/members/{child_id}`   | DELETE | Remove a child Conversation from this aggregate                   |
| `/api/v1/conversations/{id}/parents`              | GET    | List aggregate Conversations this Conversation belongs to         |

### 21.4 Conversation Entity Association API

| Endpoint                                                | Method | Description                                                  |
| ------------------------------------------------------- | ------ | ------------------------------------------------------------ |
| `/api/v1/conversations/{id}/relations`                  | GET    | List all entity associations (Projects, Companies, etc.)     |
| `/api/v1/conversations/{id}/relations/{relation_slug}`  | GET    | List associations for a specific Relation Type               |
| `/api/v1/conversations/{id}/relations/{relation_slug}`  | POST   | Add an entity association                                    |
| `/api/v1/conversations/{id}/relations/{relation_slug}/{target_id}` | DELETE | Remove an entity association               |

### 21.5 Review Workflow API

| Endpoint                 | Method | Description                                                |
| ------------------------ | ------ | ---------------------------------------------------------- |
| `/api/v1/review/pending` | GET    | Get pending items for review (unassigned + low confidence) |
| `/api/v1/review/assign`  | POST   | Batch assign communications to conversations               |
| `/api/v1/review/stats`   | GET    | Get review statistics (pending count, correction rate)     |

---

## 22. Design Decisions

### Why merge Topic into Conversation as an aggregate pattern?

Topic and Conversation were architecturally identical — both were system object types with field registries, event sourcing, and relation models. Topic's sole distinguishing characteristic was grouping Conversations, which is exactly what a parent-child relationship provides. The Document/Folder precedent from the Documents PRD proved that a single entity with a boolean flag (`is_folder` / `is_aggregate`) is simpler, more flexible, and requires less framework surface area. Merging also enables aggregate Conversations to hold their own direct Communications alongside child Conversations — something a separate Topic entity could not do.

### Why entity attachment via Relation Types instead of FK columns?

FK columns (`topic_id`, `project_id`) create rigid, single-cardinality associations that require schema changes for each new entity type. Relation Types provide many-to-many associations with any registered object type (including future custom objects) without schema changes. A Conversation can be associated with multiple Projects, Companies, and Contacts simultaneously. The tradeoff is slightly more complex queries (JOIN through junction tables), which is acceptable given the flexibility gained.

### Why no inheritance of entity associations?

If a child Conversation automatically inherited its parent aggregate's entity associations, it would create confusion when children naturally relate to different entities. A "Lease Negotiation" aggregate associated with "Acme Corp" might have a child "With Lawyer" that should be associated with "Smith & Associates LLP", not Acme. Explicit, independent associations at every level prevent surprising behavior and give users full control.

### Why many-to-many conversation membership?

A Conversation about "Contract Terms" might logically belong to both a "Lease Negotiation" aggregate and a "Legal Review" aggregate. Restricting to single-parent membership would force artificial duplication. The Documents PRD established this pattern with `document_folder_members`, and the acyclic enforcement algorithm is well-understood.

### Why derived participants instead of a Conversation→Contact Relation Type?

Storing participants on the Conversation would create data duplication — every time a Communication is added to or removed from a conversation, the participant list would need reconciliation. Deriving participants from Communications is always current and requires no maintenance. The tradeoff is a JOIN-based query instead of a direct lookup, which is acceptable given the communication count per conversation is typically small (<100).

### Why `conversation_id` FK on Communications instead of a junction table?

A communication belongs to at most one conversation (many:1). The split/reference model (Section 11) handles the case where content spans conversations via Segments, but the Communication record itself has a single primary conversation. An FK column is the simplest and most performant representation.

### Why configurable stale/closed thresholds per conversation?

Different conversations have different natural cadences. A weekly status meeting conversation going 8 days without activity is normal. A fast-moving negotiation going 3 days is a concern. Per-conversation thresholds (with sensible defaults) let users tune lifecycle detection to match their reality.

### Why no default alerts?

Alert fatigue is the #1 reason CRM users disable notifications and stop engaging. By requiring explicit alert creation, the system ensures every notification is one the user actively wants. The UI makes alert creation easy (turn any view into an alert with one click), but the system never assumes it knows what the user wants to be notified about.

### Why sub-project depth is unlimited?

The self-referential Relation Type on Project naturally supports any depth. In practice, users rarely go beyond 2–3 levels. Adding an artificial depth limit would require enforcement logic without meaningful benefit. If a user wants "Expansion → NYC → Legal → Contract Review", that's their organizational choice.

---

## 23. Phasing & Roadmap

### Phase 1: Hierarchy & Email Conversations (with Communications PRD Phase 1)

**Goal:** Establish the Conversation entity (standard and aggregate) and email-based conversation auto-formation.

- Conversation as system object type with field registry (including `is_aggregate` flag)
- `conversation_members` junction table for aggregate membership
- System Relation Types (Conversation↔Project, Conversation↔Company, Conversation↔Contact, Conversation↔Event)
- Event sourcing for Conversations
- Email thread → Conversation auto-formation (via `provider_thread_id`)
- Manual conversation creation and communication assignment
- Conversation timeline rendering from Communication Published Summaries
- AI summarization consuming Published Summaries
- Basic conversation views and filtering
- Conversation API endpoints

### Phase 2: AI Auto-Organization + Cross-Channel (with Communications PRD Phase 2)

**Goal:** AI-powered classification and cross-channel conversation support.

- AI classification and routing for conversation assignment
- User review workflow for auto-assignments
- Confidence scoring and display
- Cross-channel conversation timeline (email + SMS sequenced)
- Participant-based default conversations for SMS
- Aggregate Conversation placement suggestions

### Phase 3: Intelligence + Learning (with Communications PRD Phase 3)

**Goal:** Full conversation intelligence and learning from corrections.

- Communication segmentation (split/reference model)
- AI learning from user corrections (initial implementation)
- Sentiment analysis at conversation level
- Automated lifecycle state transitions (stale/closed)
- Action item tracking and status management
- Advanced conversation views

### Phase 4: Alerts + Advanced Features

**Goal:** User-defined alerts and platform-level conversation intelligence.

- User-defined alerts (view → alert with trigger/frequency/delivery)
- Alert frequency and aggregation controls
- Conversation analytics dashboard
- Cross-account conversation deduplication (with Communications PRD)
- AI-assisted paragraph-level segmentation
- Shareable views for conversations

---

## 24. Dependencies & Related PRDs

| PRD                                           | Relationship                                                                                                       | Dependency Direction                                                                                    |
| --------------------------------------------- | ------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------- |
| **Custom Objects PRD**                        | Conversation is a system object type. Aggregate Conversations use the same framework.                              | **Bidirectional.** This PRD defines behaviors; Custom Objects provides the framework.                   |
| **Communications PRD**                        | Communications are the atomic records Conversations group. `conversation_id` FK lives on the Communication entity. Communication Published Summaries are rendered in the Conversation timeline. | **Conversations depend on Communications** as the foundational data layer and summary source.           |
| **Projects PRD**                              | Projects associate with Conversations via the Conversation↔Project system Relation Type.                           | **Projects PRD defines the Project entity;** this PRD defines Conversation-side behaviors.              |
| **Contact Management PRD**                    | Conversation participants derived from Communication Participants. Explicit Conversation↔Contact Relation Type supplements derivation. | **Bidirectional.** Conversations consume contact data; conversation patterns feed relationship scoring. |
| **Event Management PRD**                      | Events link to Conversations via Event→Conversation Relation Type.                                                 | **Events depend on Conversations** for meeting correlation.                                             |
| **Notes PRD**                                 | Notes attach to Conversations (standard and aggregate). Communication Published Summaries share the same rich text content architecture. | **Notes depend on Conversations** as attachment targets. **Shared architecture** for rich text.         |
| **Email Provider Sync PRD**                   | Email threading logic creates and populates Conversations.                                                         | **Email Sync contributes to Conversations** through `provider_thread_id`.                               |
| **Documents PRD**                             | Established the folder-as-document pattern (`is_folder`) and many-to-many membership (`document_folder_members`) that Aggregate Conversations mirror. | **Architectural precedent.** No runtime dependency.                                                     |
| **Data Sources PRD**                          | Virtual schema for Conversations.                                                                                  | **Data Sources depend on Custom Objects** (which governs Conversations).                                |
| **Views & Grid PRD**                          | Conversation views and filters.                                                                                    | **Views depend on Custom Objects** (which governs Conversations).                                       |
| **Permissions & Sharing PRD**                 | Access control on Conversations (standard and aggregate).                                                          | **Conversations depend on Permissions.**                                                                |
| **AI Learning & Classification PRD** (future) | How the system learns from user corrections; classification algorithms; confidence scoring.                        | **This PRD establishes the requirement; AI PRD defines implementation.**                                |

---

## 25. Open Questions

1. **Aggregate nesting depth limit** — Should recursive sub-project nesting have a maximum depth? Current decision: unlimited. Should we add a soft warning at depth 4+?

2. **Conversation merge/split operations** — When a user merges two conversations or splits one, what happens to AI summaries, action items, and topic assignments? Re-process entirely or patch incrementally?

3. **Cross-account conversation merging** — When two provider accounts participate in the same real-world conversation (e.g., user has both work and personal email in the same thread), auto-merge or keep separate? Confidence threshold?

4. **Calendar-conversation linking** — Should calendar events auto-create placeholder conversations? What's the heuristic for matching meetings to conversations? The Events PRD defines Event→Conversation linking, but the trigger logic needs definition.

5. **Slack/Teams integration model** — These tools have their own hierarchy (workspaces/teams → channels → threads). How should their structure map to our Projects → Topics → Conversations model? Deferred to separate discussion.

6. **AI cost management at scale** — For high-volume tenants (thousands of new communications daily), how should AI processing be throttled? Model tiering? Summarization thresholds? Configurable processing depth?

7. **Conversation merge detection** — Should the system proactively detect conversations that might be related (same participants, similar subjects, temporal proximity) and suggest merges?

8. **Opt-out granularity** — Can users exclude specific conversations, contacts, or entire channels from AI processing? What does "exclude" mean operationally?

---

## 26. Future Work

- **Conversation analytics** — Response time metrics, communication frequency per conversation, engagement trend lines.
- **Conversation templates** — Pre-defined project/topic structures for common workflows (deal pipeline, onboarding, project management).
- **Advanced AI classification** — Embedding-based similarity for conversation assignment, moving beyond keyword/participant matching.
- **Sentiment analysis** — Emotional tone tracking at the conversation level with per-communication trends.
- **AI-assisted paragraph-level segmentation** — AI suggests segments when it detects multi-topic communications.
- **Graph-based conversation discovery** — Using Neo4j relationships to surface conversations related to entities the user is viewing.
- **Real-time collaboration** — Multiple users viewing and annotating the same conversation simultaneously.

---

## 27. Glossary

| Term                        | Definition                                                                                                                                                                                                           |
| --------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Conversation**            | A logical grouping of related communications between specific participants about a specific subject. Can span multiple channels. When `is_aggregate = true`, serves as an organizational container for child Conversations. A system object type with prefix `cvr_`. |
| **Aggregate Conversation**  | A Conversation with `is_aggregate = true`. Serves as an organizational container that groups related child Conversations and can hold its own direct Communications. Replaces the former Topic entity. Nesting is unlimited with acyclic enforcement. |
| **Conversation Membership** | The many-to-many relationship between aggregate and child Conversations, stored in the `conversation_members` junction table. A child can belong to multiple aggregates simultaneously. |
| **Published Summary**       | The rich text representation of a Communication's contribution to a Conversation's timeline. Defined in the Communications PRD Section 7. The Conversation references Published Summaries; it does not copy or store Communication content. |
| **System Relation Type**    | A platform-provided Relation Type that ships out of the box. Conversation↔Project, Conversation↔Company, Conversation↔Contact, and Conversation↔Event are system Relation Types for entity attachment. |
| **Segment**                 | A portion of a Communication assigned to a different Conversation than the primary. Created by user selection. Stored as a behavior-managed record. |
| **Auto-organization**       | AI-driven classification and routing of Communications into Conversations and suggestion of aggregate Conversation placement, with user review and correction. |
| **Confidence Score**        | A 0.0–1.0 value indicating the AI's certainty about a Conversation or aggregate Conversation assignment. Drives the review workflow. |
| **System Status**           | Time-based Conversation lifecycle state: `active`, `stale`, `closed`. Managed automatically based on `last_activity_at` and configurable thresholds. |
| **AI Status**               | Semantic Conversation state from AI analysis: `open`, `closed`, `uncertain`. |
| **Review Workflow**         | The daily process where users review auto-assigned Communications, accept or correct assignments, and identify unknown contacts. |
| **Cross-Channel Stitching** | The mechanism for maintaining Conversation continuity when Communications span multiple channels (email, SMS, phone, etc.). |
| **Split/Reference Model**   | The approach for handling Communications that span multiple Conversations: primary assignment + segments with cross-references. |

---

*This document is a living specification. As the AI Learning & Classification PRD is developed and as channel-specific child PRDs evolve, sections will be updated to reflect design decisions, scope adjustments, and lessons learned.*
