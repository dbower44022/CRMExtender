# Product Requirements Document: Conversations

## CRMExtender — Organizational Hierarchy, AI Intelligence & Conversation Lifecycle

**Version:** 1.0
**Date:** 2026-02-18
**Status:** Draft — Fully reconciled with Custom Objects PRD
**Parent Document:** [CRMExtender PRD v1.1](PRD.md)

> **V1.0 (2026-02-18):**
> This document is one of two sibling PRDs extracted from the monolithic Communication & Conversation Intelligence PRD v2.0 (2026-02-07). That document has been decomposed into:
> 
> - **[Communications PRD](communications-prd_V1.md)** — The Communication entity, common schema, provider adapter framework, contact association, triage filtering, multi-account management, attachments, and storage. The foundation that channel-specific child PRDs build on.
> - **This PRD (Conversations)** — The Conversation, Topic, and Project entity types, the organizational hierarchy, AI intelligence layer (classify & route, summarize, extract intelligence), conversation lifecycle, cross-channel stitching, communication segmentation, the review workflow, conversation views, and user-defined alerts.
> 
> All content has been reconciled with the [Custom Objects PRD](custom-objects-prd.md) Unified Object Model:
> 
> - Conversation is a **system object type** (`is_system = true`, prefix `cvr_`) with registered behaviors for AI status detection, summarization, and action item extraction.
> - Topic is a **system object type** (`is_system = true`, prefix `top_`) with registered behavior for conversation aggregation.
> - Project is a **system object type** (`is_system = true`, prefix `prj_`) with registered behavior for topic aggregation. Sub-projects use a self-referential Relation Type.
> - Entity IDs use **prefixed ULIDs** per the platform-wide convention.
> - Conversation→Communication membership is a **FK column** (`conversation_id`) on the `communications` table (defined in the Communications PRD).
> - Conversation→Contact participation is derived from Communication Participants — no separate Conversation→Contact relation is needed.
> - Topic→Project and Conversation→Topic assignments are **FK columns** on their respective tables.
> - Sub-project hierarchy uses a **self-referential Relation Type** on Project (parent_project→child_project).
> - `ai_status` and `system_status` are **Select fields** on the Conversation field registry.
> - All entity stores use **per-entity-type event tables** per Custom Objects PRD Section 19.
> - All SQL uses **PostgreSQL** syntax with `TIMESTAMPTZ` timestamps and schema-per-tenant isolation.

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Problem Statement](#2-problem-statement)
3. [Goals & Success Metrics](#3-goals--success-metrics)
4. [User Personas & Stories](#4-user-personas--stories)
5. [Conversation as System Object Type](#5-conversation-as-system-object-type)
6. [Topic as System Object Type](#6-topic-as-system-object-type)
7. [Project as System Object Type](#7-project-as-system-object-type)
8. [Organizational Hierarchy](#8-organizational-hierarchy)
9. [Conversation Formation](#9-conversation-formation)
10. [Multi-Channel Conversations](#10-multi-channel-conversations)
11. [Communication Segmentation & Cross-Conversation References](#11-communication-segmentation--cross-conversation-references)
12. [AI Intelligence Layer](#12-ai-intelligence-layer)
13. [The Review Workflow](#13-the-review-workflow)
14. [Learning from User Corrections](#14-learning-from-user-corrections)
15. [Conversation Lifecycle & Status Management](#15-conversation-lifecycle--status-management)
16. [Conversation Views & Dashboards](#16-conversation-views--dashboards)
17. [User-Defined Alerts](#17-user-defined-alerts)
18. [Event Sourcing & Temporal History](#18-event-sourcing--temporal-history)
19. [Virtual Schema & Data Sources](#19-virtual-schema--data-sources)
20. [API Design](#20-api-design)
21. [Design Decisions](#21-design-decisions)
22. [Phasing & Roadmap](#22-phasing--roadmap)
23. [Dependencies & Related PRDs](#23-dependencies--related-prds)
24. [Open Questions](#24-open-questions)
25. [Future Work](#25-future-work)
26. [Glossary](#26-glossary)

---

## 1. Executive Summary

The Conversations subsystem is the tool used to aggregate, organize, and summarize electronic and analog Conversations between various Contacts.  Conversations may be standalone, or organized into topics and associated with any Primary Object in the system (Project, Company, Event, Task, Etc).  The primary goal of the Conversation system is to make it easy for the user to review all forms of electronic communications that are relavent to their need. While the Communications PRD defines the atomic interaction record, this PRD defines how those records are grouped, organized, and enriched with AI-generated intelligence to reflect how professionals actually think about their work.

When a Communication is received, the system will process the Communication to determine the recipients, and if it is related to previous, existing Conversations.  It will then summarize the content of the communication and add the new content to an existing Conversation, or create a new Conversation.  The Conversation will be presented in a manner that they can quickly understand the progress of the entire conversation quickly and easily without having to filter through unimportant or redundant information.  Because all communications are preserved, a user can review the actual Communications that were used to create the Summary Conversation.

Conversations can be organized into a flexible`, optional` hierarchy: ** **Topics** contain **Conversations** and additional Sub Topics, and Conversations contain **Communications**. A lease negotiation project might have a "Legal Review" topic containing conversations with a lawyer and an accountant, alongside an "Inspections" topic with a conversation involving a contractor. Every level is optional — communications can exist unassigned, conversations don't require topics.

The AI intelligence layer serves three roles: **classify & route** incoming communications into conversations and topics, **summarize** conversation content across all channels, and **extract intelligence** (status, action items, key topics). Auto-organization happens silently when confidence is high and is flagged for user review when confidence is low, creating a human-in-the-loop learning system that improves over time.

**Core principles:**

- **Three system object types** — Conversation (`cvr_`), and Topic (`top_`)  are system object types in the Custom Objects unified framework. Each has its own field registry, event sourcing, and relation model. Users can extend any of them with custom fields.
- **Optional, flexible hierarchy** — The hierarchy is a tool, not a requirement. Every level is optional. Communications can exist unassigned. Conversations can be related to any object (Project, Company, etc). The hierarchy helps users organize and relate conversation— it never forces structure.
- **AI-powered auto-organization with human oversight** — The system automatically classifies, routes, and groups communications. High-confidence assignments happen silently. Low-confidence assignments are flagged for review. Users correct mistakes. The system learns from corrections.
- **Cross-channel continuity** — A conversation can span email, SMS, phone, and video. Communications from all channels are sequenced by timestamp into a single coherent timeline. Email thread IDs provide automatic stitching; other channels use participant-based defaults with AI and user refinement.
- **Intelligence-first** — Every conversation of sufficient substance has an AI-generated summary, status classification, action items, and topic tags. Content is cleaned of noise (by the Communications PRD pipeline) before AI processing.
- **Event-sourced history** — All mutations to Conversations, Topics, and Projects are stored as immutable events, enabling full audit trails and point-in-time reconstruction.

**Relationship to other PRDs:**

- **[Custom Objects PRD](custom-objects-prd.md)** — Conversation, Topic, and Project are system object types. Table structures, field registries, event sourcing, and relation models are governed by the Custom Objects framework. This PRD defines the entity-specific behaviors registered with the framework.
- **[Communications PRD](communications-prd_V1.md)** — Communications are the atomic records that Conversations group. The Communications PRD defines the Communication entity, common schema, provider adapters, triage, and contact resolution. Communications reference their parent Conversation via `conversation_id`.
- **[Contact Management PRD](contact-management-prd_V4.md)** — Conversation participants are derived from Communication Participants. Communication frequency within conversations feeds relationship strength scoring.
- **[Event Management PRD](events-prd_V2.md)** — Events link to Conversations through the Event→Conversation Relation Type (`event_conversations`). Meeting follow-up emails and pre-meeting coordination threads are correlated with their triggering events.
- **[Notes PRD](notes-prd_V2.md)** — Notes attach to Conversations as supplementary commentary (meeting observations, strategic context). Notes use the Universal Attachment Relation pattern.
- **[Data Sources PRD](data-sources-prd.md)** — Virtual schema tables for Conversation, Topic, and Project are derived from their field registries.
- **[Views & Grid PRD](views-grid-prd_V3.md)** — Conversation, Topic, and Project views, filters, sorts, and inline editing operate on fields from the respective field registries.
- **[Permissions & Sharing PRD](permissions-sharing-prd_V1.md)** — Conversation, Topic, and Project record access follow the standard role-based access model.
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

1. **Flexible organizational hierarchy** — Topics, SubTopics and Conversations provide optional structure. Users organize as much or as little as they want.
2. **Automatic conversation formation** — Email threads auto-create conversations via provider thread IDs. SMS and calls form participant-based default conversations. AI suggests refinements.
3. **AI auto-organization** — The system automatically classifies communications into conversations and suggests topic/project assignments, with configurable confidence thresholds.
4. **Conversation intelligence** — Every substantive conversation has an AI-generated summary, status classification, action items, and topic tags.
5. **Cross-channel stitching** — A conversation can contain communications from multiple channels, presented as a single chronological timeline.
6. **Human-in-the-loop learning** — Users review and correct auto-assignments. The system learns from corrections to improve future accuracy.
7. **User-empowered visibility** — Users define their own views and alerts against conversation data, rather than relying on a prescriptive dashboard.

### Success Metrics

| Metric                                | Target                                                                    | Measurement                                                    |
| ------------------------------------- | ------------------------------------------------------------------------- | -------------------------------------------------------------- |
| Conversation auto-assignment accuracy | >85% of communications assigned to the correct conversation               | User correction rate as inverse proxy                          |
| Topic auto-assignment accuracy        | >75% of conversations assigned to the correct topic                       | User correction rate as inverse proxy                          |
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

- **US-1:** As a user, I want to create projects to organize my work so that all related topics, conversations, and communications are grouped together.
- **US-2:** As a user, I want to create sub-projects within a project so that I can organize complex initiatives with multiple workstreams.
- **US-3:** As a user, I want to create topics within a project so that conversations about distinct aspects of the project are separated.
- **US-4:** As a user, I want the system to automatically create new conversations when it detects communications that don't fit any existing conversation.
- **US-5:** As a user, I want the system to automatically suggest topic assignments for new conversations based on their content.
- **US-6:** As a user, I want to move conversations between topics and projects when the system's auto-assignment is wrong.
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
| `description`           | A logical grouping of related communications between specific participants about a specific subject. Can span multiple channels. |

### 5.2 Registered Behaviors

| Behavior                     | Source PRD | Trigger                               |
| ---------------------------- | ---------- | ------------------------------------- |
| AI status detection          | This PRD   | On new communication added            |
| Summarization                | This PRD   | On new communication added, on demand |
| Action item extraction       | This PRD   | On new communication added            |
| Topic aggregation (on Topic) | This PRD   | On conversation assignment change     |

### 5.3 Conversation Field Registry

**Universal fields** (per Custom Objects PRD Section 7): `id`, `tenant_id`, `created_at`, `updated_at`, `created_by`, `updated_by`, `archived_at`.

**Core system fields** (`is_system = true`, protected):

| Field                | Column                 | Type                | Required | Description                                                                          |
| -------------------- | ---------------------- | ------------------- | -------- | ------------------------------------------------------------------------------------ |
| Subject              | `subject`              | Text (single-line)  | NO       | Derived from email subject, or user-defined. Display name field.                     |
| Topic ID             | `topic_id`             | Relation (→ topics) | NO       | FK to parent topic. NULL for unassigned conversations.                               |
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
    topic_id            TEXT,                   -- FK → topics
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
CREATE INDEX idx_cvr_topic ON conversations (topic_id) WHERE topic_id IS NOT NULL;
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

## 6. Topic as System Object Type

### 6.1 Object Type Registration

| Attribute               | Value                                                                                                                                                                       |
| ----------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `name`                  | Topic                                                                                                                                                                       |
| `slug`                  | `topics`                                                                                                                                                                    |
| `type_prefix`           | `top_`                                                                                                                                                                      |
| `is_system`             | `true`                                                                                                                                                                      |
| `display_name_field_id` | → `name` field                                                                                                                                                              |
| `description`           | An organizational grouping within a project that represents a distinct subject area. Contains one or more conversations with different participants about the same subject. |

### 6.2 Topic Field Registry

**Universal fields** (standard set).

**Core system fields:**

| Field              | Column               | Type                  | Required | Description                                                                 |
| ------------------ | -------------------- | --------------------- | -------- | --------------------------------------------------------------------------- |
| Name               | `name`               | Text (single-line)    | YES      | Topic name. Display name field.                                             |
| Description        | `description`        | Text (multi-line)     | NO       | Optional description of the topic's scope.                                  |
| Project ID         | `project_id`         | Relation (→ projects) | YES      | FK to parent project. Topics must belong to a project.                      |
| Conversation Count | `conversation_count` | Number (integer)      | NO       | Denormalized count. Updated by the conversation aggregation behavior.       |
| Last Activity At   | `last_activity_at`   | Datetime              | NO       | Most recent communication timestamp across all conversations in this topic. |

### 6.3 Topic–Conversation Relationship

Topics group related conversations within a project. A topic represents a subject area; conversations represent exchanges with different participants about that subject.

```
Topic: Lease Negotiation
  ├── Conversation with lawyer (3 emails, 1 phone call)
  ├── Conversation with accountant (2 emails)
  └── Conversation with lessor (5 emails, 1 in-person meeting)
```

Three different conversations, three different sets of people, all about lease negotiation.

---

## 7. Project as System Object Type

### 7.1 Object Type Registration

| Attribute               | Value                                                                                                                                          |
| ----------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| `name`                  | Project                                                                                                                                        |
| `slug`                  | `projects`                                                                                                                                     |
| `type_prefix`           | `prj_`                                                                                                                                         |
| `is_system`             | `true`                                                                                                                                         |
| `display_name_field_id` | → `name` field                                                                                                                                 |
| `description`           | The highest-level organizational container representing a business initiative, engagement, or deal. Contains topics and optional sub-projects. |

### 7.2 Project Field Registry

**Universal fields** (standard set).

**Core system fields:**

| Field             | Column              | Type                  | Required | Description                                                               |
| ----------------- | ------------------- | --------------------- | -------- | ------------------------------------------------------------------------- |
| Name              | `name`              | Text (single-line)    | YES      | Project name. Display name field.                                         |
| Description       | `description`       | Text (multi-line)     | NO       | Optional description of the project's purpose and scope.                  |
| Status            | `status`            | Select                | YES      | `active`, `on_hold`, `completed`, `archived`. Default: `active`.          |
| Owner ID          | `owner_id`          | Relation (→ users)    | NO       | The user who manages the project.                                         |
| Parent Project ID | `parent_project_id` | Relation (→ projects) | NO       | Self-referential FK for sub-project nesting. NULL for top-level projects. |
| Topic Count       | `topic_count`       | Number (integer)      | NO       | Denormalized count.                                                       |
| Last Activity At  | `last_activity_at`  | Datetime              | NO       | Most recent communication timestamp across all topics and conversations.  |

### 7.3 Sub-Project Relation Type

Sub-projects use a **self-referential Relation Type** on the Project object type:

| Attribute                 | Value                                  |
| ------------------------- | -------------------------------------- |
| Relation Type Name        | Project Hierarchy                      |
| Relation Type Slug        | `project_hierarchy`                    |
| Source Object Type        | Project (`prj_`)                       |
| Target Object Type        | Project (`prj_`)                       |
| Cardinality               | One-to-many (parent has many children) |
| Directionality            | Bidirectional                          |
| `is_system`               | `true`                                 |
| Cascade (source archived) | Cascade archive children               |

Implementation: The `parent_project_id` FK column on the `projects` table. No junction table needed for 1:many.

```
Project: 2026 Expansion
  ├── Sub-project: NYC Office
  │     ├── Topic: Real Estate
  │     ├── Topic: Hiring
  │     └── Topic: Regulatory
  ├── Sub-project: London Office
  │     ├── Topic: Real Estate
  │     └── Topic: Visa Sponsorship
  └── Sub-project: Infrastructure
        ├── Topic: Cloud Migration
        └── Topic: Security Audit
```

### 7.4 Project Creation Model

- **Proactive** — User creates a project before any communications occur, in anticipation of future work. May pre-define topics. Example: "Office Relocation" project created with topics "Lease Negotiation", "Moving Logistics", "IT Setup" before any emails are exchanged.
- **Reactive** — User creates a project in response to an incoming communication that introduces a new initiative.

Projects are **almost always user-created**. They represent an intentional decision to organize work around an initiative. AI may suggest creating a project, but the user confirms.

---

## 8. Organizational Hierarchy

### 8.1 The Hierarchy Model

```
Project
  └── Sub-project (optional, recursive)
        └── Topic
              └── Conversation
                    └── Communication (defined in Communications PRD)
                          └── Segment (when split across conversations)
```

**Every level is optional.** Communications can exist unassigned. Conversations don't need to belong to a topic or project. The hierarchy exists to help users organize their work — it is never forced.

### 8.2 Hierarchy Rules

| Entity        | Must belong to a parent?             | Can exist independently?                                                  |
| ------------- | ------------------------------------ | ------------------------------------------------------------------------- |
| Communication | No — can be unassigned               | Yes — marketing emails, unknown senders, one-offs                         |
| Conversation  | No — doesn't need a topic or project | Yes — an ongoing exchange with a colleague that isn't part of any project |
| Topic         | Yes — must belong to a project       | No — topics exist within projects                                         |
| Project       | No — top-level entity                | Yes — always independent                                                  |

### 8.3 Topic vs. Conversation Distinction

A **Topic** groups conversations that are about the same subject but with **different people**. Under a "Lease Negotiation" topic, there might be a conversation with the lawyer, one with the accountant, and one with the lessor.

A **Conversation** groups communications between a **specific set of participants** about a specific subject, potentially spanning multiple channels.

---

## 9. Conversation Formation

### 9.1 Email-Based Conversations (Automatic)

Email providers supply native thread identifiers that automatically group related messages:

| Provider | Threading Mechanism                                                                                                     | Reliability                                         |
| -------- | ----------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------- |
| Gmail    | `threadId` — groups by subject and participants                                                                         | High (occasional false grouping on common subjects) |
| Outlook  | `conversationId` — groups by conversation                                                                               | High                                                |
| IMAP     | Reconstructed from RFC 5322 headers (`Message-ID`, `References`, `In-Reply-To`), with subject-line matching as fallback | Medium (JWZ algorithm, inherently less reliable)    |

An email thread automatically creates a Conversation. The `provider_thread_id` on Communication records (Communications PRD Section 5.1) links messages to conversations. Additional email threads may be merged into the same conversation by the AI or user if they are determined to be part of the same exchange.

### 9.1.1 Email Content Summary Creation

The Communications PRD defines how each email will be summarized to eliminate redundant (Original Text in Reply), or unnecessary information (Email Signature) from the email so that the conversation contains the Only the relavent content.  The Communications Summary will be added to the Conversation along with a link to the original Communication so a user can navigate to the communications to review the original content if necessary.

### 9.2 Participant-Based Conversations (SMS, Calls)

For channels without native threading (SMS, phone calls), the system creates **default participant-based conversations**:

- All SMS messages between the same set of participants form a single default conversation: "SMS with Bob" or "Group SMS with Bob, Alice, and Carol."
- This is a catch-all stream containing all SMS exchanges with that participant set, regardless of topic.
- Users can select specific messages from this default conversation and assign them to topic-specific conversations.

### 9.3 Manually Created Conversations

Users can create conversations explicitly and assign communications to them. This is the primary model for:

- Organizing phone call and meeting notes into topic-specific conversations.
- Pulling SMS messages out of the default participant-based conversation.
- Creating a conversation around communications from multiple channels.

### 9.4 AI-Suggested Splitting

When the AI detects a communication doesn't fit the current conversation (different subject, different context), it may suggest creating a new conversation. This is presented as a suggestion for user confirmation, never automatic.

---

## 10. Multi-Channel Conversations

### 10.1 Cross-Channel Continuity

A conversation can contain communications from multiple channels. The system maintains continuity through timestamp sequencing (Communications PRD Section 5.3):

- An email thread forms the backbone of a conversation.
- An SMS sent 30 minutes after the last email, between the same participants, is likely part of the same conversation.
- A phone call note logged by the user and assigned to the conversation appears in the timeline at the correct chronological position.

### 10.2 Stitching Mechanisms

**Automatic stitching (email only):** Email thread IDs provide reliable automatic conversation assignment. This is handled during sync by the email provider adapter.

**Manual stitching (other channels):** SMS, calls, and meetings must be assigned to conversations by the user (or by AI with user review) because there is no reliable automatic mechanism to determine which conversation they belong to.

**AI-assisted stitching (future):** The AI may suggest cross-channel assignments based on participant overlap, temporal proximity, and content similarity. These are always presented as suggestions for user confirmation.

### 10.3 Multi-Channel Formatting for AI

When the AI processes a conversation for summarization, the prompt includes channel markers so the AI understands the communication type:

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

## 11. Communication Segmentation & Cross-Conversation References

### 11.1 The Problem

A single communication may address multiple topics. An email might say: "Attached is the contract you asked about. Also, are we still on for the team offsite planning?" — that's two topics, potentially two conversations.

### 11.2 The Solution: Split/Reference Model

**Primary assignment (automatic):** Each communication is automatically assigned to its primary conversation (via email thread ID, participant matching, or AI classification). The full communication lives in the primary conversation.

**Segment creation (user-driven):** When a user identifies that a communication spans two conversations, they select a portion of the text. They invoke an "Assign selected to different conversation" action. This creates a **Segment** — the selected text assigned to the target conversation. The original communication now has references in both conversations.

**What the user sees:**

- In the primary conversation: the full communication, with the segmented portion highlighted or annotated.
- In the secondary conversation: the segment (selected text), with a link back to the full original communication.

**What is preserved:**

- The original communication is never modified or moved.
- The segment is an additional reference, not a copy.
- Both conversations show contextually relevant content.

### 11.3 Segment Data Model

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

### 11.4 Future: AI-Assisted Segmentation

The AI could analyze communications at the paragraph level and suggest segments when it detects that a communication addresses multiple conversations or topics. This would be presented as a suggestion for user confirmation, not automatic. Deferred to the AI Learning & Classification PRD.

---

## 12. AI Intelligence Layer

### 12.1 AI Roles

The AI serves three distinct functions:

#### Role 1: Classify & Route

For every incoming communication, the AI attempts to determine:

- **Which conversation does this belong to?** (existing conversation, or create a new one?)
- **Which topic does this conversation belong to?** (existing topic, or suggest a new one?)
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

### 12.2 Summarization Thresholds

Not all communications warrant AI summarization:

| Content Length                           | Summarize? | Rationale                                           |
| ---------------------------------------- | ---------- | --------------------------------------------------- |
| <50 words (short SMS, brief note)        | No         | The content itself is already concise enough        |
| 50–200 words (typical email)             | Optional   | May benefit from summary in conversation context    |
| >200 words (long email, call transcript) | Yes        | Substantial content that benefits from distillation |

Conversation-level summaries are always generated when the conversation has sufficient total content, regardless of individual communication lengths.

### 12.3 Re-Summarization Triggers

Conversation summaries are automatically refreshed when:

- A new communication is added to the conversation (any channel).
- A user explicitly requests a refresh.
- A communication is reassigned to or from the conversation.

### 12.4 AI Error Handling

| Failure                    | Recovery                                                                              |
| -------------------------- | ------------------------------------------------------------------------------------- |
| AI API timeout             | Retry with exponential backoff (3 attempts); mark as pending                          |
| AI API rate limit          | Queue and retry after cooldown                                                        |
| Malformed AI response      | Return with error flag; log raw response                                              |
| AI API unavailable         | Conversations remain visible without summaries; queue for processing when API returns |
| Empty conversation content | Skip summarization; display "(no content to analyze)"                                 |

---

## 13. The Review Workflow

### 13.1 Purpose

Auto-organization is only useful if users can efficiently review and correct it. The system presents:

> "14 new communications since yesterday. 11 auto-assigned (review). 3 unassigned (needs your input)."

### 13.2 Review Actions

The review workflow allows users to:

- See all auto-assignments with confidence indicators
- Accept or correct conversation assignment with minimal clicks
- Accept or correct topic/project assignment
- Identify unknown contacts (defers to Contact Intelligence system)
- Create new conversations, topics, or projects as needed

The UI must be **extremely efficient** for this workflow — it is a daily activity that must take seconds, not minutes.

### 13.3 Confidence Display

| Confidence Level   | Display                              | User Action         |
| ------------------ | ------------------------------------ | ------------------- |
| High (>0.85)       | Green indicator, assigned silently   | Review optional     |
| Medium (0.50–0.85) | Yellow indicator, flagged for review | Review recommended  |
| Low (<0.50)        | Red indicator, left unassigned       | Assignment required |

---

## 14. Learning from User Corrections

### 14.1 The Principle

**The system learns from every user correction to improve future auto-assignment.**

When a user corrects an assignment (moves a communication to a different conversation, reassigns a topic, etc.), that correction becomes a training signal.

### 14.2 What the System Learns

Over time, the system should:

- Recognize patterns specific to each user's organizational preferences
- Learn contact-specific routing (e.g., "emails from Bob about invoices go to Accounting")
- Improve confidence thresholds based on correction rates
- Apply organizational learning across team members where appropriate

### 14.3 Deferred Details

**The details of how learning is implemented — prompt-based context, embedding similarity, fine-tuning, or hybrid approaches — are defined in the AI Learning & Classification PRD (Section 23: Related PRDs).** This PRD establishes the product requirement: the system learns from corrections and improves over time.

---

## 15. Conversation Lifecycle & Status Management

### 15.1 Three Status Dimensions

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

### 15.2 Status Independence

The three dimensions are independent and complementary:

- **System: active** + **AI: closed** → Recent messages, but the topic was resolved
- **System: stale** + **AI: open** → No recent activity, but the last message asked an unanswered question
- **Triage** is orthogonal — determines whether AI analysis happens at all

---

## 16. Conversation Views & Dashboards

### 16.1 View Framework Integration

Conversation views operate through the Views & Grid PRD framework. All Conversation, Topic, and Project fields from their field registries are available for filtering, sorting, grouping, and display.

### 16.2 Example Views

| View                         | Description                                                                               |
| ---------------------------- | ----------------------------------------------------------------------------------------- |
| "My Open Action Items"       | All `ai_action_items` across all conversations where `ai_status = 'open'`, sorted by date |
| "Stale Client Conversations" | Conversations with `system_status = 'stale'`, grouped by contact                          |
| "Project X Status"           | All conversations under Project X, grouped by topic, sorted by `last_activity_at`         |
| "Unassigned This Week"       | Communications from the last 7 days with `conversation_id IS NULL`                        |
| "All Comms with Bob"         | Communications where Bob is a participant, across all channels, chronological             |
| "Pending Reviews"            | Auto-assigned communications with low `ai_confidence` scores                              |

### 16.3 Shareable Views

Views can be shared with team members. A manager creates a "Team Open Action Items" view, and everyone on the team can use it. Shared views use the viewer's data permissions — sharing the view definition doesn't grant access to data the viewer wouldn't otherwise see.

### 16.4 Views as the Foundation for Alerts

Views and alerts share the same underlying architecture. An alert is a view with a trigger attached (Section 17).

---

## 17. User-Defined Alerts

### 17.1 Design Philosophy

**No default alerts.** The system sends zero notifications unless the user explicitly creates them. Users define exactly the alerts they want — no more, no less.

### 17.2 Alert Architecture

An alert is a **saved query** (view) with a **trigger**, **frequency**, and **delivery method**:

```
Saved Query (filter criteria against the data model)
  ├── Rendered as a View (pull — user opens it on demand)
  └── Attached as an Alert (push — system notifies when results change)
        ├── Frequency: Immediate, Hourly, Daily, Weekly
        ├── Aggregation: Individual (one alert per result) or Batched (digest)
        └── Delivery: In-app notification, Push notification, Email, SMS
```

### 17.3 Alert Examples

| Alert                                    | Query                                                                 | Frequency | Delivery          |
| ---------------------------------------- | --------------------------------------------------------------------- | --------- | ----------------- |
| "New communication from VIP contacts"    | Communications from contacts tagged "VIP"                             | Immediate | Push notification |
| "Conversations going stale on Project X" | Conversations under Project X with `system_status = 'stale'`          | Daily     | Email digest      |
| "Unassigned items to review"             | Communications with `conversation_id IS NULL` or low `ai_confidence`  | Daily     | In-app            |
| "Any change to the Acme Deal"            | Any new communication in any conversation under the Acme Deal project | Immediate | Push notification |
| "Weekly action item summary"             | All open `ai_action_items` across all conversations                   | Weekly    | Email digest      |

### 17.4 Frequency & Aggregation

- **Immediate + Individual:** Every matching event triggers a notification. For high-priority, low-frequency alerts.
- **Hourly/Daily + Batched:** Matching events are collected and delivered as a digest. For high-frequency monitoring.
- **Weekly + Batched:** Summary report. For oversight and review patterns.

---

## 18. Event Sourcing & Temporal History

### 18.1 Event Tables

Per Custom Objects PRD Section 19, each entity type has a companion event table:

- `conversations_events` — All mutations to Conversation records
- `topics_events` — All mutations to Topic records
- `projects_events` — All mutations to Project records

Event table schema follows the standard pattern from Custom Objects PRD (same structure as `communications_events` in the Communications PRD Section 14.1).

### 18.2 Key Event Types

**Conversation events:**

| Event Type                | Trigger                                           | Description                        |
| ------------------------- | ------------------------------------------------- | ---------------------------------- |
| `created`                 | New conversation formed (auto or manual)          | Full record snapshot               |
| `communication_added`     | Communication assigned to this conversation       | Communication ID in metadata       |
| `communication_removed`   | Communication unassigned from this conversation   | Communication ID in metadata       |
| `topic_assigned`          | Conversation assigned to a topic                  | `topic_id` change                  |
| `ai_processed`            | AI generated summary/status/action items          | AI output snapshot                 |
| `status_transition`       | `system_status` changed (active → stale → closed) | Old and new status                 |
| `merged`                  | Two conversations merged                          | Source conversation ID in metadata |
| `archived` / `unarchived` | Soft-delete or restore                            |                                    |

**Topic and Project events** follow similar patterns for their respective field changes.

---

## 19. Virtual Schema & Data Sources

### 19.1 Virtual Schema Tables

Per Data Sources PRD, each object type's field registry generates a virtual schema table:

- `conversations` — All conversation fields
- `topics` — All topic fields
- `projects` — All project fields

### 19.2 Cross-Entity Queries

Data Source queries can traverse the hierarchy:

```sql
-- All conversations in a specific project, with their topics
SELECT c.subject, c.ai_status, c.ai_summary, t.name AS topic_name
FROM conversations c
LEFT JOIN topics t ON c.topic_id = t.id
WHERE t.project_id = 'prj_01HX7...'
ORDER BY c.last_activity_at DESC;
```

```sql
-- All communications in a project's conversations
SELECT comm.timestamp, comm.channel, comm.subject, comm.body_preview
FROM communications comm
JOIN conversations c ON comm.conversation_id = c.id
JOIN topics t ON c.topic_id = t.id
WHERE t.project_id = 'prj_01HX7...'
ORDER BY comm.timestamp DESC;
```

---

## 20. API Design

### 20.1 Conversation CRUD API

| Endpoint                             | Method | Description                                                  |
| ------------------------------------ | ------ | ------------------------------------------------------------ |
| `/api/v1/conversations`              | GET    | List conversations (paginated, filterable, sortable)         |
| `/api/v1/conversations`              | POST   | Create a conversation                                        |
| `/api/v1/conversations/{id}`         | GET    | Get conversation with communications and participants        |
| `/api/v1/conversations/{id}`         | PATCH  | Update conversation fields (subject, topic assignment, etc.) |
| `/api/v1/conversations/{id}/archive` | POST   | Archive a conversation                                       |
| `/api/v1/conversations/{id}/history` | GET    | Get event history                                            |

### 20.2 Conversation Intelligence API

| Endpoint                                    | Method | Description                                                       |
| ------------------------------------------- | ------ | ----------------------------------------------------------------- |
| `/api/v1/conversations/{id}/summarize`      | POST   | Trigger AI summarization refresh                                  |
| `/api/v1/conversations/{id}/communications` | GET    | List communications in this conversation (chronological timeline) |
| `/api/v1/conversations/{id}/participants`   | GET    | Derived participant list                                          |
| `/api/v1/conversations/{id}/segments`       | GET    | List segments referencing this conversation                       |

### 20.3 Topic CRUD API

| Endpoint                      | Method | Description                         |
| ----------------------------- | ------ | ----------------------------------- |
| `/api/v1/topics`              | GET    | List topics (filterable by project) |
| `/api/v1/topics`              | POST   | Create a topic within a project     |
| `/api/v1/topics/{id}`         | GET    | Get topic with conversations        |
| `/api/v1/topics/{id}`         | PATCH  | Update topic fields                 |
| `/api/v1/topics/{id}/archive` | POST   | Archive a topic                     |

### 20.4 Project CRUD API

| Endpoint                             | Method | Description                                 |
| ------------------------------------ | ------ | ------------------------------------------- |
| `/api/v1/projects`                   | GET    | List projects (filterable by status, owner) |
| `/api/v1/projects`                   | POST   | Create a project                            |
| `/api/v1/projects/{id}`              | GET    | Get project with topics and sub-projects    |
| `/api/v1/projects/{id}`              | PATCH  | Update project fields                       |
| `/api/v1/projects/{id}/archive`      | POST   | Archive a project                           |
| `/api/v1/projects/{id}/sub-projects` | GET    | List child projects                         |

### 20.5 Review Workflow API

| Endpoint                 | Method | Description                                                |
| ------------------------ | ------ | ---------------------------------------------------------- |
| `/api/v1/review/pending` | GET    | Get pending items for review (unassigned + low confidence) |
| `/api/v1/review/assign`  | POST   | Batch assign communications to conversations               |
| `/api/v1/review/stats`   | GET    | Get review statistics (pending count, correction rate)     |

---

## 21. Design Decisions

### Why three separate system object types instead of one hierarchy entity?

Conversations, Topics, and Projects have different field registries, different behaviors, different lifecycle patterns, and different access patterns. Conversations have AI intelligence fields; Topics are lightweight groupings; Projects have status, ownership, and sub-project nesting. Making each a system object type gives them independent field registries, independent event sourcing, and independent extension points (users can add custom fields to Projects without affecting Conversations).

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

## 22. Phasing & Roadmap

### Phase 1: Hierarchy & Email Conversations (with Communications PRD Phase 1)

**Goal:** Establish the three entity types and email-based conversation auto-formation.

- Conversation, Topic, Project as system object types with field registries
- Event sourcing for all three entity types
- Sub-project hierarchy (self-referential relation)
- Email thread → Conversation auto-formation (via `provider_thread_id`)
- Manual conversation creation and communication assignment
- Project / Topic CRUD
- AI summarization adapted for conversation model
- Basic conversation views and filtering
- Conversation API endpoints

### Phase 2: AI Auto-Organization + Cross-Channel (with Communications PRD Phase 2)

**Goal:** AI-powered classification and cross-channel conversation support.

- AI classification and routing for conversation assignment
- User review workflow for auto-assignments
- Confidence scoring and display
- Cross-channel conversation timeline (email + SMS sequenced)
- Participant-based default conversations for SMS
- Topic auto-assignment suggestions

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

## 23. Dependencies & Related PRDs

| PRD                                           | Relationship                                                                                                       | Dependency Direction                                                                                    |
| --------------------------------------------- | ------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------- |
| **Custom Objects PRD**                        | Conversation, Topic, and Project are system object types.                                                          | **Bidirectional.** This PRD defines behaviors; Custom Objects provides the framework.                   |
| **Communications PRD**                        | Communications are the atomic records Conversations group. `conversation_id` FK lives on the Communication entity. | **Conversations depend on Communications** as the foundational data layer.                              |
| **Contact Management PRD**                    | Conversation participants derived from Communication Participants.                                                 | **Bidirectional.** Conversations consume contact data; conversation patterns feed relationship scoring. |
| **Event Management PRD**                      | Events link to Conversations via Event→Conversation Relation Type.                                                 | **Events depend on Conversations** for meeting correlation.                                             |
| **Notes PRD**                                 | Notes attach to Conversations, Topics, and Projects.                                                               | **Notes depend on Conversations** as attachment targets.                                                |
| **Email Provider Sync PRD**                   | Email threading logic creates and populates Conversations.                                                         | **Email Sync contributes to Conversations** through `provider_thread_id`.                               |
| **Data Sources PRD**                          | Virtual schema for Conversations, Topics, and Projects.                                                            | **Data Sources depend on Custom Objects** (which governs these entities).                               |
| **Views & Grid PRD**                          | Conversation views and filters.                                                                                    | **Views depend on Custom Objects** (which governs these entities).                                      |
| **Permissions & Sharing PRD**                 | Access control on conversations, topics, and projects.                                                             | **Conversations depend on Permissions.**                                                                |
| **AI Learning & Classification PRD** (future) | How the system learns from user corrections; classification algorithms; confidence scoring.                        | **This PRD establishes the requirement; AI PRD defines implementation.**                                |

---

## 24. Open Questions

1. **Sub-project depth limit** — Should recursive sub-project nesting have a maximum depth? Current decision: unlimited. Should we add a soft warning at depth 4+?

2. **Conversation merge/split operations** — When a user merges two conversations or splits one, what happens to AI summaries, action items, and topic assignments? Re-process entirely or patch incrementally?

3. **Cross-account conversation merging** — When two provider accounts participate in the same real-world conversation (e.g., user has both work and personal email in the same thread), auto-merge or keep separate? Confidence threshold?

4. **Calendar-conversation linking** — Should calendar events auto-create placeholder conversations? What's the heuristic for matching meetings to conversations? The Events PRD defines Event→Conversation linking, but the trigger logic needs definition.

5. **Slack/Teams integration model** — These tools have their own hierarchy (workspaces/teams → channels → threads). How should their structure map to our Projects → Topics → Conversations model? Deferred to separate discussion.

6. **AI cost management at scale** — For high-volume tenants (thousands of new communications daily), how should AI processing be throttled? Model tiering? Summarization thresholds? Configurable processing depth?

7. **Conversation merge detection** — Should the system proactively detect conversations that might be related (same participants, similar subjects, temporal proximity) and suggest merges?

8. **Opt-out granularity** — Can users exclude specific conversations, contacts, or entire channels from AI processing? What does "exclude" mean operationally?

---

## 25. Future Work

- **Conversation analytics** — Response time metrics, communication frequency per conversation, engagement trend lines.
- **Conversation templates** — Pre-defined project/topic structures for common workflows (deal pipeline, onboarding, project management).
- **Advanced AI classification** — Embedding-based similarity for conversation assignment, moving beyond keyword/participant matching.
- **Sentiment analysis** — Emotional tone tracking at the conversation level with per-communication trends.
- **AI-assisted paragraph-level segmentation** — AI suggests segments when it detects multi-topic communications.
- **Graph-based conversation discovery** — Using Neo4j relationships to surface conversations related to entities the user is viewing.
- **Real-time collaboration** — Multiple users viewing and annotating the same conversation simultaneously.

---

## 26. Glossary

| Term                        | Definition                                                                                                                                                                                                           |
| --------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Conversation**            | A logical grouping of related communications between specific participants about a specific subject. Can span multiple channels. A system object type with prefix `cvr_`.                                            |
| **Topic**                   | An organizational grouping within a project that represents a distinct subject area. Contains one or more conversations with different participants about the same subject. A system object type with prefix `top_`. |
| **Project**                 | The highest-level organizational container representing a business initiative, engagement, or deal. Contains topics and optional sub-projects. A system object type with prefix `prj_`.                              |
| **Sub-project**             | A child project nested within a parent project via the self-referential Project Hierarchy Relation Type. Same structure as a project.                                                                                |
| **Segment**                 | A portion of a communication assigned to a different conversation than the primary. Created by user selection. Stored as a behavior-managed record.                                                                  |
| **Auto-organization**       | AI-driven classification and routing of communications into conversations, topics, and projects, with user review and correction.                                                                                    |
| **Confidence Score**        | A 0.0–1.0 value indicating the AI's certainty about a conversation or topic assignment. Drives the review workflow.                                                                                                  |
| **System Status**           | Time-based conversation lifecycle state: `active`, `stale`, `closed`. Managed automatically based on `last_activity_at` and configurable thresholds.                                                                 |
| **AI Status**               | Semantic conversation state from AI analysis: `open`, `closed`, `uncertain`.                                                                                                                                         |
| **Review Workflow**         | The daily process where users review auto-assigned communications, accept or correct assignments, and identify unknown contacts.                                                                                     |
| **Cross-Channel Stitching** | The mechanism for maintaining conversation continuity when communications span multiple channels (email, SMS, phone, etc.).                                                                                          |
| **Split/Reference Model**   | The approach for handling communications that span multiple conversations: primary assignment + segments with cross-references.                                                                                      |

---

*This document is a living specification. As the AI Learning & Classification PRD is developed and as channel-specific child PRDs evolve, sections will be updated to reflect design decisions, scope adjustments, and lessons learned.*
