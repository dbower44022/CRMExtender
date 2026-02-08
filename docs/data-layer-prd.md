# Data Layer & Database Architecture PRD

## CRMExtender — Communication & Conversation Intelligence Data Model

**Version:** 1.0
**Date:** 2026-02-07
**Status:** Draft
**Parent Documents:** [Communication & Conversation Intelligence PRD](email-conversations-prd.md), [CRMExtender PRD v1.1](PRD.md)

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Technology Selection & Rationale](#2-technology-selection--rationale)
3. [Design Principles & Key Decisions](#3-design-principles--key-decisions)
4. [Entity-Relationship Diagram](#4-entity-relationship-diagram)
5. [Schema Design](#5-schema-design)
6. [Relationships & Referential Integrity](#6-relationships--referential-integrity)
7. [Indexing Strategy](#7-indexing-strategy)
8. [Query Patterns](#8-query-patterns)
9. [Denormalization Strategy](#9-denormalization-strategy)
10. [Transaction Design & Consistency](#10-transaction-design--consistency)
11. [Serialization & ORM Integration](#11-serialization--orm-integration)
12. [Caching Architecture](#12-caching-architecture)
13. [Migration Plan](#13-migration-plan)
14. [Scaling Strategy](#14-scaling-strategy)
15. [Security & Tenant Isolation](#15-security--tenant-isolation)
16. [Monitoring & Observability](#16-monitoring--observability)
17. [Trade-offs & Alternatives Considered](#17-trade-offs--alternatives-considered)
18. [SQLite / PostgreSQL Compatibility](#18-sqlite--postgresql-compatibility)
19. [Glossary](#19-glossary)

---

## 1. Executive Summary

This document defines the data layer architecture for the CRMExtender Communication & Conversation Intelligence subsystem. It replaces the current 8-table email-only SQLite schema with a 15-table multi-channel design that supports the full organizational hierarchy (Project → Topic → Conversation → Communication), multi-channel communications (email, SMS, phone, video, in-person, notes), and user-defined views and alerts.

**Key architectural decisions:**

- **PostgreSQL** for production; **SQLite** for continued PoC development. The schema is designed for compatibility with both engines.
- **Conventional mutable tables** (not event-sourced) for the conversations subsystem. Event sourcing is reserved for contacts and intelligence entities per the parent PRD.
- **Single polymorphic table** for communications across all channel types, with nullable channel-specific columns.
- **Many-to-many** relationship between conversations and communications, enabling a single communication to appear in multiple conversations with context-specific display content.
- **Adjacency list** pattern for recursive project/sub-project nesting.
- **Strategic denormalization** on the conversations table for display performance (counts, timestamps), with computed data reserved for detail views.
- **15 tables** total, up from 8 in the current PoC.

---

## 2. Technology Selection & Rationale

### 2.1 Primary Database: PostgreSQL 16+

| Factor | Assessment |
|---|---|
| **Why PostgreSQL** | The parent PRD mandates PostgreSQL for the production data layer. Strong typing, JSONB support, schema-per-tenant isolation, materialized views, `WITH RECURSIVE` for tree queries, and mature migration tooling (Alembic) make it the clear choice. |
| **Event sourcing support** | PostgreSQL handles both the event store (append-only tables) and materialized views (current-state tables) for entities that require it. The conversations subsystem uses conventional tables but coexists in the same database. |
| **Multi-tenancy** | Schema-per-tenant isolation (see Section 15) provides strong data separation without operational complexity of database-per-tenant. |
| **JSONB** | Used for `query_def` in views and `channel_metadata` flexibility if ever needed. GIN-indexable for production query performance. |
| **Full-text search** | PostgreSQL `tsvector` provides basic full-text search. Meilisearch (per parent PRD) handles the primary search workload. |

### 2.2 PoC Database: SQLite

| Factor | Assessment |
|---|---|
| **Why SQLite for PoC** | Zero infrastructure. Single file. Ships with Python. Fast iteration. The existing PoC runs on SQLite with 95 passing tests. |
| **Compatibility constraints** | The schema avoids PostgreSQL-only features (JSONB operators, array types, partial indexes with expressions). JSON columns use TEXT in SQLite and JSONB in PostgreSQL. `WITH RECURSIVE` is supported by both. |
| **Migration path** | Schema DDL is written in a compatible subset. The migration from SQLite to PostgreSQL is a data-level migration, not a schema redesign. See Section 13. |

### 2.3 Alternatives Considered

| Alternative | Why Not |
|---|---|
| **MongoDB** | The data model is highly relational (hierarchy, M:N joins, participant lookups). Document stores add complexity for these access patterns without meaningful benefit. |
| **MySQL/MariaDB** | No technical blocker, but PostgreSQL is already mandated by the parent PRD and offers superior JSONB, CTE, and schema-per-tenant support. |
| **Event sourcing for conversations** | Conversations are read-heavy, update-moderate, and don't require point-in-time reconstruction. The audit trail benefit doesn't justify the complexity. Conventional tables with `updated_at` timestamps are sufficient. |

---

## 3. Design Principles & Key Decisions

### 3.1 Principles

1. **Display speed is paramount.** The system's value depends on fast, responsive data access. Denormalize wherever it reduces JOIN depth for frequently displayed data.
2. **Communications are channel-agnostic.** A single table stores all communication types. Channel-specific fields are nullable columns, not separate tables.
3. **Conversations are account-independent.** The account (data source) lives on the communication, not the conversation. A conversation can contain communications from multiple accounts and channels.
4. **The hierarchy is optional.** Communications can exist unassigned. Conversations don't need topics or projects. The hierarchy helps users organize — it is never forced.
5. **Schema compatibility.** DDL must work in both SQLite and PostgreSQL with minimal divergence. PostgreSQL-only features are used only where a SQLite fallback exists.
6. **Idempotent writes.** All sync operations use UPSERT or INSERT-ON-CONFLICT patterns. Safe to re-run at any time.

### 3.2 Key Design Decisions

| Decision | Choice | Rationale | Alternatives Considered |
|---|---|---|---|
| Communication table structure | Single polymorphic table | Query simplicity; no JOINs for timeline display; channel set is finite and stable after initial development | Extension tables per channel (cleaner normalization but adds JOINs); JSON metadata column (PostgreSQL-friendly but awkward in SQLite) |
| Conversation ↔ Communication relationship | Many-to-many via join table with `display_content` | A communication can belong to multiple conversations; each conversation shows the relevant portion of the text; eliminates separate segments table | Direct FK on communications (limits to one conversation); separate segments table (adds complexity) |
| Project hierarchy | Adjacency list (self-referential `parent_id`) | Simple; reparenting is one-row update; tree depth is shallow (2-3 levels); `WITH RECURSIVE` handles rare full-tree queries | Materialized path (faster descendant queries but requires subtree updates on reparent); closure table (over-engineered for shallow trees) |
| AI topic tags vs. organizational topics | Renamed to `tags` / `conversation_tags` | Avoids naming collision with hierarchy `topics` table; AI-extracted tags and user-created organizational topics serve different purposes | Shared table with a `type` column (confusing semantics); prefixed names like `ai_topics` (verbose) |
| Denormalized counts on conversations | `communication_count`, `participant_count`, `first_activity_at`, `last_activity_at` | Eliminates JOINs + aggregates for the most common query: listing conversations sorted by recency with counts | Computed at query time (always accurate but slower for listings) |
| Sender on communications row | Keep `sender_address` and `sender_name` on the communications table | Sender is displayed on every communication; avoids JOIN to participants table for the most common read | Sender only in participants table (normalized but adds a JOIN to every display query) |
| Conversation account ownership | Account-independent; account lives on communications | Conversations span channels and accounts; a conversation can include a Gmail email, an SMS, and a manual note | Account FK on conversations (current model; breaks when conversations span sources) |
| Sourcing model | Conventional mutable tables | Read-heavy workload; no requirement for point-in-time reconstruction; simpler implementation and querying | Event sourcing (full audit trail but excessive complexity for this subsystem) |

---

## 4. Entity-Relationship Diagram

```mermaid
erDiagram
    projects {
        TEXT id PK
        TEXT parent_id FK
        TEXT name
        TEXT description
        TEXT status
        TEXT owner_id
        TEXT created_at
        TEXT updated_at
    }

    topics {
        TEXT id PK
        TEXT project_id FK
        TEXT name
        TEXT description
        TEXT source
        TEXT created_at
        TEXT updated_at
    }

    conversations {
        TEXT id PK
        TEXT topic_id FK
        TEXT title
        TEXT status
        INTEGER communication_count
        INTEGER participant_count
        TEXT first_activity_at
        TEXT last_activity_at
        TEXT ai_summary
        TEXT ai_status
        TEXT ai_action_items
        TEXT ai_topics
        TEXT ai_summarized_at
        TEXT triage_result
        TEXT created_at
        TEXT updated_at
    }

    conversation_participants {
        TEXT conversation_id PK_FK
        TEXT address PK
        TEXT name
        TEXT contact_id FK
        INTEGER communication_count
        TEXT first_seen_at
        TEXT last_seen_at
    }

    conversation_communications {
        TEXT conversation_id PK_FK
        TEXT communication_id PK_FK
        TEXT display_content
        INTEGER is_primary
        TEXT created_at
    }

    communications {
        TEXT id PK
        TEXT account_id FK
        TEXT channel
        TEXT timestamp
        TEXT content
        TEXT direction
        TEXT source
        TEXT sender_address
        TEXT sender_name
        TEXT subject
        TEXT body_html
        TEXT snippet
        TEXT provider_message_id
        TEXT provider_thread_id
        TEXT header_message_id
        TEXT header_references
        TEXT header_in_reply_to
        INTEGER is_read
        TEXT phone_number_from
        TEXT phone_number_to
        INTEGER duration_seconds
        TEXT transcript_source
        TEXT note_type
        TEXT ai_summary
        TEXT ai_summarized_at
        TEXT triage_result
        TEXT created_at
        TEXT updated_at
    }

    communication_participants {
        TEXT communication_id PK_FK
        TEXT address PK
        TEXT role PK
        TEXT name
        TEXT contact_id FK
    }

    attachments {
        TEXT id PK
        TEXT communication_id FK
        TEXT filename
        TEXT mime_type
        INTEGER size_bytes
        TEXT storage_ref
        TEXT source
        TEXT created_at
    }

    contacts {
        TEXT id PK
        TEXT email
        TEXT name
        TEXT source
        TEXT source_id
        TEXT created_at
        TEXT updated_at
    }

    provider_accounts {
        TEXT id PK
        TEXT provider
        TEXT account_type
        TEXT email_address
        TEXT phone_number
        TEXT display_name
        TEXT auth_token_path
        TEXT sync_cursor
        TEXT last_synced_at
        INTEGER initial_sync_done
        TEXT backfill_query
        TEXT created_at
        TEXT updated_at
    }

    tags {
        TEXT id PK
        TEXT name
        TEXT source
        TEXT created_at
    }

    conversation_tags {
        TEXT conversation_id PK_FK
        TEXT tag_id PK_FK
        REAL confidence
        TEXT source
        TEXT created_at
    }

    views {
        TEXT id PK
        TEXT owner_id
        TEXT name
        TEXT description
        TEXT query_def
        INTEGER is_shared
        TEXT created_at
        TEXT updated_at
    }

    alerts {
        TEXT id PK
        TEXT view_id FK
        TEXT owner_id
        INTEGER is_active
        TEXT frequency
        TEXT aggregation
        TEXT delivery_method
        TEXT last_triggered
        TEXT created_at
        TEXT updated_at
    }

    sync_log {
        TEXT id PK
        TEXT account_id FK
        TEXT sync_type
        TEXT started_at
        TEXT completed_at
        INTEGER messages_fetched
        INTEGER messages_stored
        INTEGER conversations_created
        INTEGER conversations_updated
        TEXT cursor_before
        TEXT cursor_after
        TEXT status
        TEXT error
    }

    projects ||--o{ projects : "parent_id (sub-projects)"
    projects ||--o{ topics : "contains"
    topics ||--o{ conversations : "groups"
    conversations ||--o{ conversation_participants : "has"
    conversations ||--o{ conversation_communications : "contains"
    conversations ||--o{ conversation_tags : "tagged"
    communications ||--o{ conversation_communications : "appears in"
    communications ||--o{ communication_participants : "involves"
    communications ||--o{ attachments : "has"
    provider_accounts ||--o{ communications : "sourced from"
    provider_accounts ||--o{ sync_log : "logged by"
    contacts ||--o{ conversation_participants : "identified as"
    contacts ||--o{ communication_participants : "identified as"
    tags ||--o{ conversation_tags : "applied to"
    views ||--o{ alerts : "triggers"
```

### Relationship Summary

```
projects (self-referential)
  └── topics
        └── conversations
              ├── conversation_participants ──→ contacts
              ├── conversation_communications
              │     └── communications
              │           ├── communication_participants ──→ contacts
              │           ├── attachments
              │           └── provider_accounts
              └── conversation_tags ──→ tags

views
  └── alerts

provider_accounts
  └── sync_log
```

---

## 5. Schema Design

### 5.1 `provider_accounts`

Tracks connected data sources and their synchronization state. Replaces the current `email_accounts` table to support multi-channel providers.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | TEXT | **PK** | UUID v4 |
| `provider` | TEXT | NOT NULL | Provider identifier: `gmail`, `outlook`, `imap`, `sms_twilio`, `voip_ringcentral`, etc. |
| `account_type` | TEXT | NOT NULL | Channel category: `email`, `sms`, `voip`, `video` |
| `email_address` | TEXT | | Account email (NULL for non-email providers) |
| `phone_number` | TEXT | | Account phone number (NULL for non-phone providers) |
| `display_name` | TEXT | | Human-readable account label |
| `auth_token_path` | TEXT | | Filesystem path to OAuth token or credential file |
| `sync_cursor` | TEXT | | Provider-specific opaque sync position. Gmail: `historyId`. Outlook: `deltaLink`. IMAP: `UIDVALIDITY:lastUID`. |
| `last_synced_at` | TEXT | | ISO 8601 timestamp of most recent successful sync |
| `initial_sync_done` | INTEGER | DEFAULT 0 | Boolean (0/1). Set to 1 when first full sync completes. |
| `backfill_query` | TEXT | | Provider-specific query for initial sync scope. Gmail: `newer_than:90d`. |
| `created_at` | TEXT | NOT NULL | ISO 8601 |
| `updated_at` | TEXT | NOT NULL | ISO 8601 |

**Constraints:**
- `UNIQUE(provider, email_address)` — prevents duplicate registration of the same email account.
- `UNIQUE(provider, phone_number)` — prevents duplicate registration of the same phone account.

**Sync cursor lifecycle:** NULL → set on initial sync completion → advanced on each incremental sync → recorded in `sync_log.cursor_before` / `cursor_after` for audit.

---

### 5.2 `contacts`

Known contacts from address books, manual entry, or identity resolution. Global (not per-account). Unchanged from the current schema; the Contact Intelligence system (separate PRD) will extend this table.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | TEXT | **PK** | UUID v4 |
| `email` | TEXT | NOT NULL, **UNIQUE** | Primary email address, lowercased |
| `name` | TEXT | | Display name |
| `source` | TEXT | | Origin: `google_contacts`, `outlook_contacts`, `manual`, `osint` |
| `source_id` | TEXT | | Provider's native identifier (e.g., Google People API resource name) |
| `created_at` | TEXT | NOT NULL | ISO 8601 |
| `updated_at` | TEXT | NOT NULL | ISO 8601 |

**Write pattern:** `INSERT ... ON CONFLICT(email) DO UPDATE` — UPSERT semantics for idempotent sync.

**Future:** The Contact Intelligence PRD will extend this with multi-identifier support (multiple emails, phone numbers per contact), enrichment fields, and confidence scores.

---

### 5.3 `projects`

Top-level organizational container. Supports recursive nesting via adjacency list (self-referential `parent_id`).

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | TEXT | **PK** | UUID v4 |
| `parent_id` | TEXT | FK → `projects(id)` ON DELETE CASCADE | Parent project for sub-projects. NULL for top-level projects. |
| `name` | TEXT | NOT NULL | User-defined project name |
| `description` | TEXT | | Optional description of purpose and scope |
| `status` | TEXT | DEFAULT `'active'` | Lifecycle state: `active`, `on_hold`, `completed`, `archived` |
| `owner_id` | TEXT | | User who created/manages this project |
| `created_at` | TEXT | NOT NULL | ISO 8601 |
| `updated_at` | TEXT | NOT NULL | ISO 8601 |

**Adjacency list pattern:** A sub-project is a row with `parent_id` pointing to its parent. Top-level projects have `parent_id = NULL`. Tree traversal uses `WITH RECURSIVE` CTEs.

**Reparenting:** Moving a sub-project to a different parent is a single-row update: `UPDATE projects SET parent_id = ? WHERE id = ?`. No descendant rows are affected.

**Cascade delete:** Deleting a project deletes all sub-projects, their topics, and the topic-conversation links (conversations themselves survive with `topic_id` set to NULL via SET NULL on the `conversations.topic_id` FK).

---

### 5.4 `topics`

Organizational grouping within a project. Groups conversations about the same subject area with different participants.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | TEXT | **PK** | UUID v4 |
| `project_id` | TEXT | NOT NULL, FK → `projects(id)` ON DELETE CASCADE | Parent project or sub-project |
| `name` | TEXT | NOT NULL | User-defined or AI-suggested topic name |
| `description` | TEXT | | Optional description |
| `source` | TEXT | DEFAULT `'user'` | How created: `user`, `ai_suggested` |
| `created_at` | TEXT | NOT NULL | ISO 8601 |
| `updated_at` | TEXT | NOT NULL | ISO 8601 |

**Key distinction from tags:** Topics are organizational containers in the hierarchy. Tags are AI-extracted keyword phrases. A topic named "Lease Negotiation" contains conversations; a tag named "lease negotiation" is a label on conversations. They serve different purposes and live in separate tables.

---

### 5.5 `conversations`

The central entity linking communications to the organizational hierarchy. Contains denormalized statistics for fast listing queries and AI-generated intelligence fields.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | TEXT | **PK** | UUID v4 |
| `topic_id` | TEXT | FK → `topics(id)` ON DELETE SET NULL | Optional link to organizational hierarchy. NULL for unassigned conversations. |
| `title` | TEXT | | Conversation title. Initially derived from email subject; user-editable. Defaults to `'(untitled)'` if empty. |
| `status` | TEXT | DEFAULT `'active'` | System status (time-based): `active`, `stale`, `closed`. See Section 5.5.1. |
| `communication_count` | INTEGER | DEFAULT 0 | **Denormalized.** Total communications across all channels. Maintained on add/remove. |
| `participant_count` | INTEGER | DEFAULT 0 | **Denormalized.** Distinct participants. Maintained from `conversation_participants`. |
| `first_activity_at` | TEXT | | **Denormalized.** ISO 8601 timestamp of earliest communication. |
| `last_activity_at` | TEXT | | **Denormalized.** ISO 8601 timestamp of most recent communication. Used for recency sorting. |
| `ai_summary` | TEXT | | AI-generated 2-4 sentence summary. NULL until AI processes the conversation. |
| `ai_status` | TEXT | | AI semantic classification: `open`, `closed`, `uncertain`. NULL until AI processes. |
| `ai_action_items` | TEXT | | JSON array of extracted action item strings. NULL if none or not yet processed. |
| `ai_topics` | TEXT | | JSON array of AI-extracted topic tag strings (source-of-truth from AI). Normalized version stored in `tags` / `conversation_tags`. |
| `ai_summarized_at` | TEXT | | ISO 8601 timestamp of last AI processing. Set to NULL when new communications arrive, marking the conversation for re-processing. |
| `triage_result` | TEXT | | NULL if passed triage. Non-NULL values indicate filter reason: `no_known_contacts`, `automated_sender`, `automated_subject`, `marketing`. |
| `created_at` | TEXT | NOT NULL | ISO 8601 |
| `updated_at` | TEXT | NOT NULL | ISO 8601 |

#### 5.5.1 Three Independent Status Dimensions

| Dimension | Column | Values | Source |
|---|---|---|---|
| **System status** | `status` | `active`, `stale`, `closed` | Time-based, automatic. Active → Stale after N days inactivity (configurable, default 14). Stale → Closed after M days (default 30). Any new communication reopens to Active. |
| **AI status** | `ai_status` | `open`, `closed`, `uncertain` | Semantic, from AI analysis. Biased toward `open` for multi-message exchanges. |
| **Triage status** | `triage_result` | NULL (passed) or filter reason string | Whether the conversation was filtered before AI processing. |

These dimensions are independent and complementary. A conversation can be system-active but AI-closed (recent messages, but the topic was resolved), or system-stale but AI-open (no recent activity, but an unanswered question remains).

#### 5.5.2 Design Rationale: AI Fields on the Conversation Row

AI intelligence fields are stored directly on the conversation row rather than in a separate `conversation_summaries` table. The relationship is strictly 1:1, and the most common query pattern is listing conversations with their summaries. Inlining avoids a JOIN on every listing query. The tradeoff is wider rows, but conversation cardinality is low (hundreds to low thousands per user).

#### 5.5.3 Design Rationale: Denormalized Counts

`communication_count`, `participant_count`, `first_activity_at`, and `last_activity_at` are denormalized from the join tables. Without denormalization, every conversation listing query would require:

```sql
SELECT c.*,
    COUNT(cc.communication_id),
    MIN(comm.timestamp),
    MAX(comm.timestamp)
FROM conversations c
LEFT JOIN conversation_communications cc ON cc.conversation_id = c.id
LEFT JOIN communications comm ON comm.id = cc.communication_id
GROUP BY c.id
ORDER BY MAX(comm.timestamp) DESC;
```

With denormalization, the listing query is:

```sql
SELECT * FROM conversations
WHERE triage_result IS NULL
ORDER BY last_activity_at DESC;
```

The maintenance cost is a few UPDATE statements when communications are added or removed. This is an acceptable tradeoff for a system where display speed is paramount.

---

### 5.6 `conversation_participants`

Denormalized summary of participants per conversation. Maintained when communications are added to or removed from a conversation.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `conversation_id` | TEXT | NOT NULL, FK → `conversations(id)` ON DELETE CASCADE | Which conversation |
| `address` | TEXT | NOT NULL | Participant identifier (email address, phone number), lowercased |
| `name` | TEXT | | Display name if known |
| `contact_id` | TEXT | FK → `contacts(id)` ON DELETE SET NULL | Matched CRM contact, if resolved. NULL if unresolved. |
| `communication_count` | INTEGER | DEFAULT 0 | How many communications this participant sent/created in this conversation |
| `first_seen_at` | TEXT | | ISO 8601 timestamp of this participant's earliest communication |
| `last_seen_at` | TEXT | | ISO 8601 timestamp of most recent communication |

**Primary key:** `(conversation_id, address)`

**Write pattern:** UPSERT on conflict — when a new communication is added to a conversation, each participant is upserted with updated counts and timestamps.

---

### 5.7 `communications`

The atomic unit of the system. A single polymorphic table storing all communication types: email, SMS, phone calls, video meetings, in-person meetings, and user-entered notes.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | TEXT | **PK** | UUID v4 |
| `account_id` | TEXT | FK → `provider_accounts(id)` ON DELETE SET NULL | Which provider account sourced this communication. NULL for manually entered communications (notes, unrecorded calls). |
| `channel` | TEXT | NOT NULL | Communication type: `email`, `sms`, `phone`, `video`, `in_person`, `note` |
| `timestamp` | TEXT | NOT NULL | ISO 8601. When the communication occurred. Universal sequencing key across all channels. |
| `content` | TEXT | | Cleaned text content. Email: stripped body. SMS: message text. Phone/video: transcript. Notes: user-written text. |
| `direction` | TEXT | | `inbound`, `outbound`, `mutual` (for calls/meetings), NULL (for notes) |
| `source` | TEXT | | How it entered the system: `auto_sync`, `manual`, `transcription` |
| `sender_address` | TEXT | | Sender's identifier (email address or phone number), lowercased |
| `sender_name` | TEXT | | Sender's display name |
| **Email-specific** | | | *NULL for non-email channels* |
| `subject` | TEXT | | Email subject line (RFC 2047 decoded) |
| `body_html` | TEXT | | Raw HTML body preserved for re-processing and rich display |
| `snippet` | TEXT | | Short preview text from provider API |
| `provider_message_id` | TEXT | | Provider's native message identifier (Gmail message ID, etc.) |
| `provider_thread_id` | TEXT | | Provider's native thread identifier (Gmail `threadId`, Outlook `conversationId`) |
| `header_message_id` | TEXT | | RFC 5322 `Message-ID` header. Used for IMAP thread reconstruction. |
| `header_references` | TEXT | | RFC 5322 `References` header (space-separated Message-IDs) |
| `header_in_reply_to` | TEXT | | RFC 5322 `In-Reply-To` header |
| `is_read` | INTEGER | DEFAULT 0 | Boolean. Email read state from provider. |
| **SMS-specific** | | | *NULL for non-SMS channels* |
| `phone_number_from` | TEXT | | Sender's phone number |
| `phone_number_to` | TEXT | | Recipient's phone number (1:1 SMS). For group SMS, additional recipients in `communication_participants`. |
| **Call/Video-specific** | | | *NULL for non-call channels* |
| `duration_seconds` | INTEGER | | Call or meeting duration |
| `transcript_source` | TEXT | | Transcription service: `whisper`, `google_stt`, `aws_transcribe`, etc. |
| **Note-specific** | | | *NULL for non-note channels* |
| `note_type` | TEXT | | Subcategory: `phone_call` (unrecorded), `in_person`, `video` (unrecorded), `general` |
| **AI fields** | | | |
| `ai_summary` | TEXT | | Per-communication AI summary. Only generated for long content (>200 words). |
| `ai_summarized_at` | TEXT | | ISO 8601 timestamp of AI processing |
| **Triage** | | | |
| `triage_result` | TEXT | | NULL if passed. Non-NULL: filter reason. |
| **Timestamps** | | | |
| `created_at` | TEXT | NOT NULL | ISO 8601 |
| `updated_at` | TEXT | NOT NULL | ISO 8601 |

**Unique constraints:**
- `UNIQUE(account_id, provider_message_id)` — prevents duplicate sync of the same message. Only applies when both fields are non-NULL (manually entered communications have no `provider_message_id`).

**Column usage by channel:**

| Column | Email | SMS | Phone | Video | In-Person | Note |
|---|---|---|---|---|---|---|
| `channel` | `email` | `sms` | `phone` | `video` | `in_person` | `note` |
| `content` | Cleaned body | Message text | Transcript | Transcript | User notes | User notes |
| `sender_address` | Email addr | Phone # | Phone # | Email | N/A | N/A |
| `subject` | Yes | — | — | — | — | — |
| `body_html` | Yes | — | — | — | — | — |
| `provider_message_id` | Yes | Maybe | — | — | — | — |
| `provider_thread_id` | Yes | — | — | — | — | — |
| `header_*` | Yes | — | — | — | — | — |
| `phone_number_*` | — | Yes | Yes | — | — | — |
| `duration_seconds` | — | — | Yes | Yes | — | — |
| `transcript_source` | — | — | Maybe | Maybe | — | — |
| `note_type` | — | — | — | — | — | Yes |

---

### 5.8 `communication_participants`

Participants in a communication beyond the sender. Generalizes the current `email_recipients` table to support all channel types.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `communication_id` | TEXT | NOT NULL, FK → `communications(id)` ON DELETE CASCADE | Which communication |
| `address` | TEXT | NOT NULL | Participant identifier (email, phone number), lowercased |
| `name` | TEXT | | Display name if known |
| `contact_id` | TEXT | FK → `contacts(id)` ON DELETE SET NULL | Matched CRM contact |
| `role` | TEXT | NOT NULL | Participant role: `to`, `cc`, `bcc`, `attendee`, `participant` |

**Primary key:** `(communication_id, address, role)`

**Role mapping by channel:**

| Channel | Applicable Roles |
|---|---|
| Email | `to`, `cc`, `bcc` |
| SMS | `to`, `participant` (group SMS) |
| Phone call | `participant` |
| Video meeting | `attendee` |
| In-person meeting | `attendee` |
| Note | `participant` (people referenced in the note) |

**Note:** The sender is stored on the `communications` row (`sender_address`, `sender_name`), not in this table. This avoids a JOIN for the most common display pattern. The sender can optionally be included here with a `sender` role for "list all participants" queries, though this is an application-level decision.

---

### 5.9 `conversation_communications`

Many-to-many join between conversations and communications. Each row stores the display content — the portion of the communication's text relevant to that conversation's context.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `conversation_id` | TEXT | NOT NULL, FK → `conversations(id)` ON DELETE CASCADE | Which conversation |
| `communication_id` | TEXT | NOT NULL, FK → `communications(id)` ON DELETE CASCADE | Which communication |
| `display_content` | TEXT | | The text to display for this communication in this conversation's context. For the primary conversation, this is typically the full cleaned content. For secondary conversations, this is the user-selected portion. NULL means display the full `communications.content`. |
| `is_primary` | INTEGER | DEFAULT 1 | 1 = original/automatic assignment. 0 = user explicitly added this communication to the conversation. |
| `created_at` | TEXT | NOT NULL | ISO 8601 |

**Primary key:** `(conversation_id, communication_id)`

**Design rationale:** This table eliminates the need for a separate segments entity. When a communication spans two conversations:

1. The communication exists once in the `communications` table with full content.
2. Row 1 in `conversation_communications`: `(convo_A, comm_123, full_text, is_primary=1)` — the original assignment.
3. Row 2 in `conversation_communications`: `(convo_B, comm_123, selected_portion, is_primary=0)` — user-selected text assigned to a second conversation.

The `display_content` column is what the UI renders. If NULL, the application falls back to `communications.content`. This allows the common case (full content displayed) to avoid data duplication while still supporting partial content display for secondary assignments.

**Scalability:** A communication can belong to any number of conversations. Each relationship is one row. No structural limit.

---

### 5.10 `attachments`

Files attached to any communication. Recordings, documents, images, email attachments.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | TEXT | **PK** | UUID v4 |
| `communication_id` | TEXT | NOT NULL, FK → `communications(id)` ON DELETE CASCADE | Parent communication |
| `filename` | TEXT | NOT NULL | Original filename |
| `mime_type` | TEXT | | MIME type (e.g., `audio/mpeg`, `application/pdf`, `image/jpeg`) |
| `size_bytes` | INTEGER | | File size |
| `storage_ref` | TEXT | | Path or URL in object storage (S3/MinIO for production, local filesystem for PoC) |
| `source` | TEXT | | How the attachment entered: `email_sync`, `upload`, `recording`, `transcript_export` |
| `created_at` | TEXT | NOT NULL | ISO 8601 |

**For recorded calls:** The transcript becomes `communications.content`; the audio file becomes an attachment with `source = 'recording'`.

**For email attachments:** Metadata synced from the email provider. Binary content stored in object storage (on-demand download from provider is an alternative; see open questions in the Conversations PRD).

---

### 5.11 `tags`

Normalized AI-extracted topic tags. Distinct from the hierarchy's `topics` table. Tags are short keyword phrases used for cross-conversation discovery and filtering.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | TEXT | **PK** | UUID v4 |
| `name` | TEXT | NOT NULL, **UNIQUE** | Tag string, lowercased and trimmed. Examples: `project timeline`, `budget review`, `hiring`. |
| `source` | TEXT | DEFAULT `'ai'` | How created: `ai` (extracted by AI), `user` (manually applied) |
| `created_at` | TEXT | NOT NULL | ISO 8601 |

**Write pattern:** `INSERT ... ON CONFLICT(name) DO NOTHING` — existing tags are reused, not duplicated.

---

### 5.12 `conversation_tags`

Many-to-many join between conversations and AI-extracted tags.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `conversation_id` | TEXT | NOT NULL, FK → `conversations(id)` ON DELETE CASCADE | Which conversation |
| `tag_id` | TEXT | NOT NULL, FK → `tags(id)` ON DELETE CASCADE | Which tag |
| `confidence` | REAL | DEFAULT 1.0 | AI confidence score. Currently always 1.0; reserved for future weighted extraction. |
| `source` | TEXT | DEFAULT `'ai'` | Assignment source: `ai`, `user` |
| `created_at` | TEXT | NOT NULL | ISO 8601 |

**Primary key:** `(conversation_id, tag_id)`

**Dual storage rationale:** Tags exist in two places: (1) `conversations.ai_topics` as the raw JSON array from the AI (source of truth), and (2) `tags` / `conversation_tags` as the normalized, queryable version. The normalized tables are derived from the raw JSON during conversation processing, enabling queries like "show all conversations tagged with 'budget review'."

---

### 5.13 `views`

User-defined saved queries against the data model. The foundation for both dashboards and alerts.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | TEXT | **PK** | UUID v4 |
| `owner_id` | TEXT | | User who created the view |
| `name` | TEXT | NOT NULL | User-defined view name (e.g., "My Open Action Items") |
| `description` | TEXT | | Optional description of what the view shows |
| `query_def` | TEXT | NOT NULL | JSON object defining filters, sorting, grouping, and columns. Interpreted by the backend query builder. |
| `is_shared` | INTEGER | DEFAULT 0 | 0 = private to owner. 1 = visible to team members. Shared views use the viewer's data permissions. |
| `created_at` | TEXT | NOT NULL | ISO 8601 |
| `updated_at` | TEXT | NOT NULL | ISO 8601 |

**`query_def` structure:**

```json
{
    "entity": "conversations",
    "filters": [
        {"field": "ai_status", "op": "eq", "value": "open"},
        {"field": "last_activity_at", "op": "older_than", "value": "14d"}
    ],
    "sort": [{"field": "last_activity_at", "dir": "desc"}],
    "group_by": "topic",
    "columns": ["title", "participant_count", "last_activity_at", "ai_summary"]
}
```

The `query_def` is a declarative specification. The backend translates it to SQL, applying tenant isolation and permission filters. Users never write raw SQL.

---

### 5.14 `alerts`

User-defined notification triggers attached to views.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | TEXT | **PK** | UUID v4 |
| `view_id` | TEXT | NOT NULL, FK → `views(id)` ON DELETE CASCADE | Which view this alert monitors |
| `owner_id` | TEXT | | User who created the alert |
| `is_active` | INTEGER | DEFAULT 1 | Boolean. Alert can be paused without deleting. |
| `frequency` | TEXT | NOT NULL | How often to check: `immediate`, `hourly`, `daily`, `weekly` |
| `aggregation` | TEXT | DEFAULT `'batched'` | How to deliver multiple results: `individual` (one alert per result), `batched` (digest) |
| `delivery_method` | TEXT | NOT NULL | How to deliver: `in_app`, `push`, `email`, `sms` |
| `last_triggered` | TEXT | | ISO 8601 timestamp of last alert delivery. Used to determine "new results since last check." |
| `created_at` | TEXT | NOT NULL | ISO 8601 |
| `updated_at` | TEXT | NOT NULL | ISO 8601 |

**No default alerts.** Zero rows exist until the user creates them.

**Alert execution:** A background job periodically runs each active alert's underlying view query, compares results to `last_triggered` timestamp, and delivers notifications for new results using the configured frequency, aggregation, and delivery method.

---

### 5.15 `sync_log`

Audit trail of sync operations. One row per sync run per provider account.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | TEXT | **PK** | UUID v4 |
| `account_id` | TEXT | NOT NULL, FK → `provider_accounts(id)` ON DELETE CASCADE | Which provider account |
| `sync_type` | TEXT | NOT NULL | `initial`, `incremental`, `manual` |
| `started_at` | TEXT | NOT NULL | ISO 8601 |
| `completed_at` | TEXT | | ISO 8601. NULL while running. |
| `messages_fetched` | INTEGER | DEFAULT 0 | Communications retrieved from provider |
| `messages_stored` | INTEGER | DEFAULT 0 | Net new communications inserted |
| `conversations_created` | INTEGER | DEFAULT 0 | New conversations created |
| `conversations_updated` | INTEGER | DEFAULT 0 | Existing conversations updated |
| `cursor_before` | TEXT | | Sync cursor at start |
| `cursor_after` | TEXT | | Sync cursor at end |
| `status` | TEXT | DEFAULT `'running'` | `running`, `completed`, `failed` |
| `error` | TEXT | | Error message on failure |

**Constraint:** `CHECK (status IN ('running', 'completed', 'failed'))`

---

## 6. Relationships & Referential Integrity

### 6.1 Foreign Key Summary

| Parent | Child | FK Column | Cardinality | On Delete |
|---|---|---|---|---|
| `projects` | `projects` | `parent_id` | 1:N (self) | CASCADE |
| `projects` | `topics` | `project_id` | 1:N | CASCADE |
| `topics` | `conversations` | `topic_id` | 1:N | SET NULL |
| `conversations` | `conversation_participants` | `conversation_id` | 1:N | CASCADE |
| `conversations` | `conversation_communications` | `conversation_id` | 1:N | CASCADE |
| `conversations` | `conversation_tags` | `conversation_id` | 1:N | CASCADE |
| `communications` | `conversation_communications` | `communication_id` | 1:N | CASCADE |
| `communications` | `communication_participants` | `communication_id` | 1:N | CASCADE |
| `communications` | `attachments` | `communication_id` | 1:N | CASCADE |
| `provider_accounts` | `communications` | `account_id` | 1:N | SET NULL |
| `provider_accounts` | `sync_log` | `account_id` | 1:N | CASCADE |
| `contacts` | `conversation_participants` | `contact_id` | 0..1:N | SET NULL |
| `contacts` | `communication_participants` | `contact_id` | 0..1:N | SET NULL |
| `tags` | `conversation_tags` | `tag_id` | 1:N | CASCADE |
| `views` | `alerts` | `view_id` | 1:N | CASCADE |

### 6.2 Delete Behavior Rationale

| Behavior | Where Used | Why |
|---|---|---|
| **CASCADE** | Parent → child aggregates (project → topics, communication → participants, conversation → tags) | Children are meaningless without parent |
| **SET NULL** | `conversations.topic_id`, `communications.account_id`, `*.contact_id` | Entity survives deletion of its association. A conversation remains even if its topic is deleted. A communication remains even if its provider account is disconnected. A participant row remains even if the contact record is deleted. |

### 6.3 FK Enforcement

- **SQLite:** `PRAGMA foreign_keys = ON` on every connection (already implemented in current PoC).
- **PostgreSQL:** FKs enforced by default. Deferred constraints used where circular dependencies arise (none in current schema).

---

## 7. Indexing Strategy

Indexes are designed around the dominant query patterns identified in Section 8. Each index has a specific purpose tied to a frequently executed query.

### 7.1 Communications Table

| Index | Column(s) | Supports |
|---|---|---|
| `idx_comm_account` | `account_id` | "All communications from provider account X" — sync queries |
| `idx_comm_channel` | `channel` | "All emails" / "All SMS" — channel-filtered views |
| `idx_comm_timestamp` | `timestamp` | Chronological sorting; date-range filtering |
| `idx_comm_sender` | `sender_address` | "All communications from address/number X" |
| `idx_comm_provider_msg` | `account_id, provider_message_id` | Deduplication during sync (UNIQUE constraint serves as index) |
| `idx_comm_thread` | `provider_thread_id` | Email thread grouping during sync |
| `idx_comm_header_msg_id` | `header_message_id` | IMAP thread reconstruction via Message-ID chains |

### 7.2 Conversations Table

| Index | Column(s) | Supports |
|---|---|---|
| `idx_conv_topic` | `topic_id` | "All conversations in topic X" — hierarchy navigation |
| `idx_conv_status` | `status` | Filter by system status (active/stale/closed) |
| `idx_conv_last_activity` | `last_activity_at` | **Primary listing sort** — most recent conversations first |
| `idx_conv_ai_status` | `ai_status` | Filter by AI classification (open/closed/uncertain) |
| `idx_conv_triage` | `triage_result` | Separate triaged from non-triaged conversations |
| `idx_conv_needs_processing` | `triage_result, ai_summarized_at` | Find conversations needing AI processing (both NULL) |

### 7.3 Join Tables

| Index | Column(s) | Supports |
|---|---|---|
| `idx_cc_communication` | `conversation_communications(communication_id)` | "Which conversations contain communication X?" — reverse lookup |
| `idx_cp_contact` | `conversation_participants(contact_id)` | "All conversations involving contact C" |
| `idx_cp_address` | `conversation_participants(address)` | "All conversations involving address/number X" |
| `idx_commpart_address` | `communication_participants(address)` | "All communications involving address X" |
| `idx_commpart_contact` | `communication_participants(contact_id)` | "All communications involving contact C" |

### 7.4 Other Tables

| Index | Column(s) | Supports |
|---|---|---|
| `idx_projects_parent` | `projects(parent_id)` | "All sub-projects of project X" — tree navigation |
| `idx_topics_project` | `topics(project_id)` | "All topics in project X" |
| `idx_attachments_comm` | `attachments(communication_id)` | "All attachments for communication X" |
| `idx_sync_log_account` | `sync_log(account_id)` | "Sync history for account X" |
| `idx_views_owner` | `views(owner_id)` | "All views created by user X" |
| `idx_alerts_view` | `alerts(view_id)` | "All alerts on view X" |

### 7.5 Indexing Notes

- All indexes use `CREATE INDEX IF NOT EXISTS` for idempotent creation.
- Composite primary keys on join tables serve as implicit indexes on the leading column(s).
- For PostgreSQL production, consider partial indexes where appropriate (e.g., `WHERE triage_result IS NULL` on conversations for the "active conversations" query). These are not available in SQLite, so they are deferred to production optimization.
- Index count (24 indexes across 15 tables) is moderate. Monitor for unused indexes in production via `pg_stat_user_indexes`.

---

## 8. Query Patterns

The most frequently executed queries, their SQL patterns, and which indexes support them.

### 8.1 High-Frequency Queries (Display / Listing)

| Query | SQL Pattern | Indexes |
|---|---|---|
| List conversations by recency | `SELECT * FROM conversations WHERE triage_result IS NULL ORDER BY last_activity_at DESC LIMIT ?` | `idx_conv_triage`, `idx_conv_last_activity` |
| List conversations by status | `SELECT * FROM conversations WHERE ai_status = ? ORDER BY last_activity_at DESC` | `idx_conv_ai_status`, `idx_conv_last_activity` |
| Conversation timeline | `SELECT comm.*, cc.display_content FROM conversation_communications cc JOIN communications comm ON comm.id = cc.communication_id WHERE cc.conversation_id = ? ORDER BY comm.timestamp` | PK on `conversation_communications`, `idx_comm_timestamp` |
| Conversation participants | `SELECT * FROM conversation_participants WHERE conversation_id = ?` | PK on `conversation_participants` |
| Project hierarchy | `SELECT * FROM projects WHERE parent_id = ?` | `idx_projects_parent` |
| Topics in project | `SELECT * FROM topics WHERE project_id = ?` | `idx_topics_project` |
| Conversations in topic | `SELECT * FROM conversations WHERE topic_id = ? ORDER BY last_activity_at DESC` | `idx_conv_topic`, `idx_conv_last_activity` |

### 8.2 Medium-Frequency Queries (Processing / Sync)

| Query | SQL Pattern | Indexes |
|---|---|---|
| Conversations needing AI | `SELECT * FROM conversations WHERE triage_result IS NULL AND ai_summarized_at IS NULL` | `idx_conv_needs_processing` |
| Deduplication check | `SELECT id FROM communications WHERE account_id = ? AND provider_message_id = ?` | UNIQUE constraint |
| Thread grouping | `SELECT * FROM communications WHERE provider_thread_id = ? AND account_id = ?` | `idx_comm_thread` |
| Contact lookup | `SELECT * FROM contacts WHERE email = ?` | UNIQUE on `email` |
| All conversations for contact | `SELECT cp.conversation_id FROM conversation_participants cp WHERE cp.contact_id = ?` | `idx_cp_contact` |

### 8.3 Low-Frequency Queries (Admin / Analytics)

| Query | SQL Pattern | Indexes |
|---|---|---|
| Full project tree | `WITH RECURSIVE tree AS (...) SELECT * FROM tree` | `idx_projects_parent` |
| Sync history | `SELECT * FROM sync_log WHERE account_id = ? ORDER BY started_at DESC` | `idx_sync_log_account` |
| Unassigned communications | `SELECT * FROM communications WHERE id NOT IN (SELECT communication_id FROM conversation_communications)` | `idx_cc_communication` |
| Tag frequency | `SELECT t.name, COUNT(*) FROM conversation_tags ct JOIN tags t ON t.id = ct.tag_id GROUP BY t.name ORDER BY COUNT(*) DESC` | PK on `conversation_tags` |

---

## 9. Denormalization Strategy

### 9.1 Denormalized Fields

| Table | Field | Source of Truth | Maintenance Trigger |
|---|---|---|---|
| `conversations` | `communication_count` | `COUNT(*) FROM conversation_communications WHERE conversation_id = ?` | Communication added to or removed from conversation |
| `conversations` | `participant_count` | `COUNT(*) FROM conversation_participants WHERE conversation_id = ?` | Participant added to or removed from conversation |
| `conversations` | `first_activity_at` | `MIN(comm.timestamp) FROM conversation_communications cc JOIN communications comm ...` | Communication added or removed |
| `conversations` | `last_activity_at` | `MAX(comm.timestamp) FROM conversation_communications cc JOIN communications comm ...` | Communication added or removed |
| `conversation_participants` | `communication_count` | Count of communications where this participant is sender | Communication added or removed |
| `conversation_participants` | `first_seen_at` / `last_seen_at` | MIN/MAX timestamps | Communication added or removed |

### 9.2 Consistency Maintenance

Denormalized fields are updated within the same transaction as the operation that changes the source data. When a communication is added to a conversation:

```
BEGIN TRANSACTION
  1. INSERT INTO conversation_communications (...)
  2. UPDATE conversations SET
       communication_count = communication_count + 1,
       last_activity_at = MAX(last_activity_at, new_comm_timestamp),
       first_activity_at = MIN(first_activity_at, new_comm_timestamp),
       updated_at = now()
     WHERE id = ?
  3. UPSERT conversation_participants (update counts, timestamps)
  4. UPDATE conversations SET participant_count = (SELECT COUNT(*) ...)
COMMIT
```

If any step fails, the entire transaction rolls back, keeping denormalized data consistent with source data.

### 9.3 Repair Mechanism

A maintenance function can recompute all denormalized fields from source data:

```sql
UPDATE conversations SET
    communication_count = (
        SELECT COUNT(*) FROM conversation_communications
        WHERE conversation_id = conversations.id
    ),
    participant_count = (
        SELECT COUNT(*) FROM conversation_participants
        WHERE conversation_id = conversations.id
    ),
    first_activity_at = (
        SELECT MIN(comm.timestamp)
        FROM conversation_communications cc
        JOIN communications comm ON comm.id = cc.communication_id
        WHERE cc.conversation_id = conversations.id
    ),
    last_activity_at = (
        SELECT MAX(comm.timestamp)
        FROM conversation_communications cc
        JOIN communications comm ON comm.id = cc.communication_id
        WHERE cc.conversation_id = conversations.id
    );
```

This runs as a scheduled maintenance task or on-demand repair. Not needed during normal operation.

---

## 10. Transaction Design & Consistency

### 10.1 Transaction Boundaries

| Operation | Transaction Scope | Isolation |
|---|---|---|
| **Store synced communication** | Single transaction: INSERT communication + INSERT communication_participants + INSERT/UPDATE conversation_communications + UPDATE conversation denormalized fields + UPSERT conversation_participants | Read Committed |
| **Assign communication to conversation** | Single transaction: INSERT conversation_communications + UPDATE conversation counts/timestamps + UPSERT conversation_participants | Read Committed |
| **Remove communication from conversation** | Single transaction: DELETE conversation_communications + UPDATE conversation counts/timestamps + recompute conversation_participants | Read Committed |
| **AI processing** | Single transaction: UPDATE conversations (ai_summary, ai_status, etc.) + UPSERT tags + INSERT conversation_tags | Read Committed |
| **Create project/topic** | Single row INSERT per entity | Read Committed |
| **Delete project** | CASCADE handles child cleanup in single transaction | Read Committed |

### 10.2 Idempotency Patterns

| Table | Unique Constraint | Write Pattern | Duplicate Behavior |
|---|---|---|---|
| `provider_accounts` | `(provider, email_address)` | Check-then-insert | Returns existing ID |
| `communications` | `(account_id, provider_message_id)` | `INSERT OR IGNORE` | Silently skipped |
| `communication_participants` | `(communication_id, address, role)` | `INSERT OR IGNORE` | Silently skipped |
| `conversation_communications` | `(conversation_id, communication_id)` | `INSERT OR IGNORE` | Silently skipped |
| `contacts` | `email` | `INSERT ... ON CONFLICT DO UPDATE` | Name/source updated |
| `conversation_participants` | `(conversation_id, address)` | `INSERT ... ON CONFLICT DO UPDATE` | Counts/dates refreshed |
| `tags` | `name` | `INSERT ... ON CONFLICT DO NOTHING` | Existing tag reused |
| `conversation_tags` | `(conversation_id, tag_id)` | `INSERT OR IGNORE` | Silently skipped |

### 10.3 Concurrency Considerations

**SQLite (PoC):** WAL mode enables concurrent reads during writes. The PoC is single-threaded so write contention is not an issue. `PRAGMA journal_mode=WAL` and `PRAGMA foreign_keys=ON` are set on every connection.

**PostgreSQL (production):** Read Committed isolation is sufficient for all operations. No long-running transactions. No cross-table consistency requirements that would demand Serializable isolation. Connection pooling (PgBouncer or application-level) prevents connection exhaustion.

---

## 11. Serialization & ORM Integration

### 11.1 Current Approach (PoC)

The PoC uses **raw SQL with Python dataclasses** and manual `to_row()` / `from_row()` methods. This approach is simple, transparent, and has zero dependencies beyond `sqlite3`.

### 11.2 Recommended Approach (Production)

**SQLAlchemy Core** (not ORM) with **Alembic** for migrations.

| Component | Choice | Rationale |
|---|---|---|
| **Query layer** | SQLAlchemy Core (Table + select/insert) | Type-safe query construction without the weight of the full ORM. Compatible with both SQLite and PostgreSQL via dialect system. Avoids N+1 problems inherent in ORM lazy loading. |
| **Migration tool** | Alembic | Industry standard for SQLAlchemy. Version-controlled migrations. Auto-generates diffs. Supports both upgrade and downgrade. |
| **Data classes** | Python dataclasses (keep existing) | Continue using `to_row()` / `from_row()` patterns. SQLAlchemy Core returns `Row` objects compatible with dict-like access. |

**Why not full SQLAlchemy ORM:** The data access patterns are well-defined (see Section 8). The ORM's relationship loading, identity map, and session management add complexity without benefit for this workload. Core gives type-safe SQL construction and dialect abstraction without the magic.

**Why not raw SQL forever:** The PoC's raw SQL approach is fine for 8 tables and single-dialect. At 15 tables targeting two dialects, SQLAlchemy Core's `Table` definitions and cross-dialect compilation prevent SQL string divergence.

### 11.3 Migration Path

1. **Phase 1 (PoC):** Continue with raw SQL and dataclasses. Add new tables to `database.py` schema DDL.
2. **Phase 2 (Pre-production):** Introduce SQLAlchemy Core `Table` definitions alongside raw SQL. Migrate queries incrementally.
3. **Phase 3 (Production):** Full SQLAlchemy Core with Alembic migrations. Raw SQL eliminated.

---

## 12. Caching Architecture

### 12.1 PoC: No Caching

The SQLite PoC does not require a caching layer. SQLite's page cache and the small data volumes make direct queries fast enough.

### 12.2 Production: Two-Tier Caching

```
┌─────────────┐     ┌──────────────┐     ┌──────────────┐
│   Client     │────→│   Redis      │────→│  PostgreSQL  │
│   (Flutter)  │     │   (cache)    │     │  (source)    │
└─────────────┘     └──────────────┘     └──────────────┘
```

**Tier 1: Application-Level Cache (Redis)**

| Cache Target | Key Pattern | TTL | Invalidation |
|---|---|---|---|
| Conversation listings | `conv:list:{user}:{filters_hash}` | 60s | Invalidate on any conversation update for the user |
| Conversation detail | `conv:{id}` | 300s | Invalidate on communication add/remove |
| Project tree | `project:tree:{user}` | 600s | Invalidate on project/topic CRUD |
| Contact index | `contacts:{tenant}` | 300s | Invalidate on contact sync |
| View results | `view:{view_id}:{params_hash}` | 30s | Invalidate on underlying data change |

**Tier 2: Client-Side Cache (SQLite on Device)**

Per the parent PRD, Flutter clients maintain a local SQLite cache for offline read access. The conversation data model mirrors the server schema (subset of tables: `conversations`, `communications`, `conversation_communications`, `contacts`). Sync via API pagination with `updated_at` cursors.

**Cache Invalidation Strategy:**

- **Write-through:** On write, update PostgreSQL and invalidate relevant Redis keys in the same operation.
- **Event-driven:** For cross-user invalidation (shared views, team alerts), use Redis Pub/Sub to notify connected clients.
- **TTL fallback:** All cached entries have a TTL. Even without explicit invalidation, stale data expires.

---

## 13. Migration Plan

### 13.1 Phase 1: Current PoC → New PoC Schema (SQLite to SQLite)

This is the immediate migration: evolving the current 8-table schema to the new 15-table schema within SQLite.

**Strategy:** Incremental migration with data preservation. The existing `emails` and `conversations` tables contain real data from synced Gmail accounts.

**Steps:**

1. **Create new tables** that don't exist yet: `projects`, `topics`, `conversation_communications`, `communication_participants`, `attachments`, `tags`, `conversation_tags`, `views`, `alerts`.

2. **Rename and extend existing tables:**
   - `email_accounts` → `provider_accounts` (add `account_type`, `phone_number` columns)
   - `emails` → `communications` (add `channel`, `timestamp`, channel-specific columns; rename `body_text` → `content`, `date` → `timestamp`)
   - `email_recipients` → `communication_participants` (add `contact_id`, extend `role` values)

3. **Transform data:**
   - Populate `conversation_communications` from existing `communications.conversation_id` (set `display_content = NULL`, `is_primary = 1`).
   - Recompute `conversations` denormalized fields from new join table.
   - Set `channel = 'email'` on all existing communications.
   - Copy `conversations.provider_thread_id` to `communications.provider_thread_id`.
   - Drop `conversation_id` from `communications` table.
   - Drop `account_id` and `provider_thread_id` from `conversations` table.

4. **Update indexes** to match new schema.

5. **Update application code** (models.py, sync.py, database.py, etc.) to use new table/column names.

**Rollback:** Backup the SQLite file before migration. Restore on failure.

**Data validation:** Post-migration, verify:
- `COUNT(*)` on `conversation_communications` matches previous non-NULL `conversation_id` count on emails.
- `conversations.communication_count` matches `COUNT(*) FROM conversation_communications`.
- All `communications` have `channel = 'email'`.
- No orphaned records (communications without conversation links that previously had them).

### 13.2 Phase 2: SQLite → PostgreSQL (Production Deployment)

**Strategy:** Schema translation + data migration. The logical schema is the same; only DDL syntax differs.

**Key differences to handle:**

| Feature | SQLite | PostgreSQL |
|---|---|---|
| UUID generation | Application-side (`uuid.uuid4()`) | Application-side or `gen_random_uuid()` |
| JSON columns | `TEXT` with `json_extract()` | `JSONB` with `->`, `->>`, `@>` operators |
| Boolean | `INTEGER` (0/1) | `BOOLEAN` (or keep INTEGER for compatibility) |
| Date/time | `TEXT` (ISO 8601 strings) | `TIMESTAMPTZ` (native; or keep TEXT for compatibility) |
| Auto-increment | Not used (UUIDs) | Not needed |
| Partial indexes | Not supported | Available for optimization |
| UPSERT syntax | `INSERT OR IGNORE` / `ON CONFLICT DO UPDATE` | `ON CONFLICT DO NOTHING` / `DO UPDATE` (same syntax) |

**Migration tool:** `pgloader` for bulk data transfer, or custom Python script using SQLAlchemy Core for dialect abstraction.

**Steps:**
1. Create PostgreSQL schema (production DDL with type upgrades: TIMESTAMPTZ, BOOLEAN, JSONB).
2. Create tenant schema (`CREATE SCHEMA tenant_xxx`).
3. Export SQLite data as CSV or use pgloader.
4. Load into PostgreSQL with data type conversion.
5. Validate row counts and referential integrity.
6. Switch application connection string.

**Zero-downtime considerations:** For a production deployment with existing users, a parallel-run strategy is recommended: write to both SQLite and PostgreSQL during a transition window, read from PostgreSQL, validate consistency, then cut over.

### 13.3 Phase 3: Ongoing Schema Evolution (Alembic)

Once on PostgreSQL with SQLAlchemy Core, all schema changes go through Alembic migrations:

```
alembic/
├── env.py
├── versions/
│   ├── 001_initial_schema.py
│   ├── 002_add_sms_fields.py
│   └── ...
└── alembic.ini
```

Each migration has `upgrade()` and `downgrade()` functions. Migrations are version-controlled and applied in sequence.

---

## 14. Scaling Strategy

### 14.1 Scale Targets

| Dimension | PoC | Year 1 Production | Year 3 Production |
|---|---|---|---|
| Users | 1 | 10-50 | 100-500 |
| Communications per user | 5,000 | 50,000 | 200,000 |
| Conversations per user | 500 | 5,000 | 20,000 |
| Total communications | 5,000 | 500K-2.5M | 20M-100M |
| Provider accounts per user | 1-2 | 2-5 | 3-10 |
| Concurrent users | 1 | 10-20 | 50-100 |

### 14.2 PostgreSQL Scaling Path

**Year 1 (single instance):**
- Single PostgreSQL instance handles all tenants.
- Schema-per-tenant isolation.
- Connection pooling via PgBouncer (max 20 connections per tenant).
- Read replicas not needed at this scale.

**Year 2-3 (read scaling):**
- Read replica for analytics, view execution, and search indexing.
- Primary handles writes and real-time reads.
- Connection routing: writes → primary, view/alert queries → replica.

**If needed (write scaling):**
- Table partitioning on `communications` by `timestamp` (range partitioning by month/quarter). This is the largest table by far.
- Partition pruning enables efficient date-range queries without scanning the full table.

### 14.3 Partitioning Strategy (Future)

The `communications` table is the primary candidate for partitioning:

```sql
-- PostgreSQL native partitioning
CREATE TABLE communications (
    ...
) PARTITION BY RANGE (timestamp);

CREATE TABLE communications_2026_q1 PARTITION OF communications
    FOR VALUES FROM ('2026-01-01') TO ('2026-04-01');
CREATE TABLE communications_2026_q2 PARTITION OF communications
    FOR VALUES FROM ('2026-04-01') TO ('2026-07-01');
```

Partitioning is deferred until data volumes justify it (>10M rows in `communications`). The schema is designed to be partition-friendly: `timestamp` is NOT NULL and is the primary sort/filter column.

### 14.4 Archive Strategy

Communications older than a configurable retention period can be moved to cold storage:

1. Archive to a separate `communications_archive` table (same schema, unindexed or minimally indexed).
2. Remove from the primary table and update conversation denormalized counts.
3. Archived communications remain searchable via Meilisearch (search index retained).
4. On-demand retrieval from archive if user navigates to historical conversations.

---

## 15. Security & Tenant Isolation

### 15.1 Multi-Tenancy: Schema-Per-Tenant

Per the parent PRD, PostgreSQL uses schema-per-tenant isolation:

```sql
CREATE SCHEMA tenant_acme;
SET search_path TO tenant_acme;
-- All tables created within tenant schema
```

**Benefits:**
- Strong data isolation without database-per-tenant overhead.
- Tenant-specific indexes and statistics.
- Cross-tenant queries impossible without explicit schema reference.
- Backup/restore per tenant.

**Application enforcement:** Every database connection sets `search_path` to the authenticated tenant's schema before executing queries. The API gateway extracts tenant from JWT and passes it to the data layer.

### 15.2 Row-Level Security (Future)

Within a tenant, row-level security can restrict which users see which conversations:

```sql
-- PostgreSQL RLS policy (future)
ALTER TABLE conversations ENABLE ROW LEVEL SECURITY;
CREATE POLICY user_conversations ON conversations
    USING (id IN (
        SELECT cp.conversation_id
        FROM conversation_participants cp
        WHERE cp.contact_id IN (
            SELECT contact_id FROM user_visible_contacts
            WHERE user_id = current_setting('app.current_user_id')
        )
    ));
```

This is deferred to the Permissions & Sharing PRD.

### 15.3 Credential Security

| Credential Type | Storage | Access |
|---|---|---|
| OAuth tokens | Filesystem (per-account token files) | Referenced by path in `provider_accounts.auth_token_path` |
| Database connection strings | Environment variables | Never in code or database |
| API keys (Claude, etc.) | Environment variables or secrets manager | Application-level only |

**Principle:** No credentials are stored in the database. Token file paths are stored, not token contents.

### 15.4 Data Protection

- **Encryption at rest:** PostgreSQL Transparent Data Encryption (TDE) or filesystem-level encryption.
- **Encryption in transit:** TLS 1.2+ for all database connections and API calls.
- **PII handling:** Communication content and contact data are PII. Subject to GDPR access/deletion/portability requests. CASCADE deletes ensure complete removal.

---

## 16. Monitoring & Observability

### 16.1 PoC Monitoring

The PoC uses Python logging (`logging` module) with structured log messages for sync operations, AI processing, and errors. No external monitoring infrastructure.

### 16.2 Production Monitoring

| Metric | Source | Alert Threshold |
|---|---|---|
| **Query latency (p95)** | Application instrumentation | >200ms for listing queries |
| **Sync duration** | `sync_log` table | >5 minutes for incremental sync |
| **Sync failures** | `sync_log.status = 'failed'` | Any failure |
| **Connection pool utilization** | PgBouncer metrics | >80% sustained |
| **Table sizes** | `pg_stat_user_tables` | `communications` >50M rows (partitioning trigger) |
| **Index usage** | `pg_stat_user_indexes` | `idx_scans = 0` after 30 days (unused index) |
| **Dead tuples** | `pg_stat_user_tables.n_dead_tup` | >20% of `n_live_tup` (autovacuum issue) |
| **Cache hit ratio** | `pg_stat_database.blks_hit / (blks_hit + blks_read)` | <95% (insufficient shared_buffers) |
| **Replication lag** | `pg_stat_replication` | >10 seconds |
| **Denormalization drift** | Scheduled repair query vs. actual values | Any mismatch (bug in maintenance logic) |

### 16.3 Recommended Tooling

| Tool | Purpose |
|---|---|
| **Prometheus + Grafana** | Metrics collection and dashboarding |
| **pg_stat_statements** | Query-level performance tracking |
| **Application logging** | Structured JSON logs via Python `logging` |
| **Sentry** | Error tracking and alerting |
| **Alembic history** | Schema version tracking |

---

## 17. Trade-offs & Alternatives Considered

### 17.1 Polymorphic Communications vs. Extension Tables

**Chose:** Single polymorphic table with nullable channel-specific columns.

**Alternative:** Base `communications` table + per-channel extension tables (`email_details`, `sms_details`, `call_details`).

**Trade-off:** The polymorphic table has wider rows with NULLs (~12 nullable columns per non-email channel). Extension tables would eliminate NULLs and enforce per-channel structure. We chose polymorphism because: (1) query simplicity — no JOINs for timeline display; (2) the channel set is finite and stable after initial development; (3) the NULL overhead is negligible at expected data volumes; (4) SQLite handles wide tables without performance issues.

### 17.2 M:N Conversations ↔ Communications vs. Segments Table

**Chose:** `conversation_communications` join table with `display_content`.

**Alternative:** Direct FK (`conversation_id` on communications) + separate `segments` table for cross-conversation references.

**Trade-off:** The FK + segments approach is simpler for the common case (one communication, one conversation) but requires a second entity and query path for multi-conversation communications. The M:N join table handles both cases uniformly. The `display_content` column on the join table replaces the segments table entirely, reducing entity count and query complexity.

### 17.3 Denormalized Counts vs. Computed Aggregates

**Chose:** Denormalized `communication_count`, `participant_count`, `first_activity_at`, `last_activity_at` on conversations.

**Alternative:** Compute via JOIN + aggregate at query time.

**Trade-off:** Denormalization adds maintenance complexity (update in same transaction, repair mechanism needed). We chose it because: (1) display speed is the system's primary performance requirement; (2) the listing query is the most frequent query; (3) the maintenance cost is bounded (a few UPDATEs per communication add/remove); (4) transactional updates prevent drift under normal operation.

### 17.4 Adjacency List vs. Materialized Path for Projects

**Chose:** Adjacency list (self-referential `parent_id`).

**Alternative:** Materialized path (`path` column storing `/root/child/grandchild`).

**Trade-off:** Materialized path makes "get all descendants" a simple `LIKE` query, but reparenting requires updating all descendant paths. Adjacency list makes reparenting a single-row update, but "get all descendants" requires `WITH RECURSIVE`. We chose adjacency because: (1) project trees are shallow (2-3 levels); (2) reparenting should be cheap; (3) `WITH RECURSIVE` is efficient for small trees and supported by both SQLite and PostgreSQL.

### 17.5 Conventional Tables vs. Event Sourcing

**Chose:** Conventional mutable tables for the conversations subsystem.

**Alternative:** Event sourcing (append-only event store with materialized views).

**Trade-off:** Event sourcing provides a full audit trail and point-in-time reconstruction. We chose conventional tables because: (1) the conversations subsystem is read-heavy and update-moderate; (2) there is no product requirement for point-in-time reconstruction of conversations; (3) `updated_at` timestamps provide sufficient change tracking; (4) conventional tables are simpler to query, index, and maintain; (5) the parent PRD reserves event sourcing for contacts and intelligence entities where history is critical.

### 17.6 SQLAlchemy Core vs. Full ORM vs. Raw SQL

**Chose:** Raw SQL for PoC, SQLAlchemy Core for production.

**Alternative:** Full SQLAlchemy ORM (declarative models, relationship loading, session management).

**Trade-off:** The full ORM provides convenience features (lazy loading, identity map, cascades in Python) but adds complexity, obscures SQL, and risks N+1 queries. SQLAlchemy Core provides type-safe query construction and dialect abstraction without the magic. For well-defined access patterns (Section 8), Core is sufficient and more predictable.

---

## 18. SQLite / PostgreSQL Compatibility

The schema is designed to work in both SQLite (PoC) and PostgreSQL (production) with minimal divergence.

### 18.1 Compatible Features Used

| Feature | SQLite | PostgreSQL | Notes |
|---|---|---|---|
| `CREATE TABLE IF NOT EXISTS` | Yes | Yes | Idempotent schema creation |
| `TEXT` type | Yes | Yes | Used for UUIDs, timestamps, strings |
| `INTEGER` type | Yes | Yes | Used for counts, booleans |
| `REAL` type | Yes | Yes | Used for confidence scores |
| `PRIMARY KEY` | Yes | Yes | |
| `FOREIGN KEY ... ON DELETE CASCADE/SET NULL` | Yes (with PRAGMA) | Yes (default) | |
| `UNIQUE` constraint | Yes | Yes | |
| `CHECK` constraint | Yes | Yes | |
| `INSERT OR IGNORE` | Yes | Mapped to `ON CONFLICT DO NOTHING` | |
| `INSERT ... ON CONFLICT DO UPDATE` | Yes | Yes | UPSERT syntax is compatible |
| `WITH RECURSIVE` | Yes (3.8.3+) | Yes | Tree traversal |
| `CREATE INDEX IF NOT EXISTS` | Yes | Yes | |
| `json_extract()` | Yes (built-in) | Via `->>`/`->>` operators | Query syntax differs |
| `WAL mode` | Yes (`PRAGMA journal_mode=WAL`) | N/A (MVCC handles this) | |

### 18.2 PostgreSQL-Only Optimizations (Deferred)

These features are available in PostgreSQL but not SQLite. They will be added during the SQLite → PostgreSQL migration:

| Feature | Benefit | Application |
|---|---|---|
| `TIMESTAMPTZ` | Native timestamp handling | Replace TEXT date columns |
| `JSONB` + GIN index | Indexed JSON queries | `views.query_def`, potential `channel_metadata` |
| Partial indexes | Smaller, faster indexes for common filters | `WHERE triage_result IS NULL` on conversations |
| Materialized views | Pre-computed aggregates | Dashboard statistics, tag frequency |
| `BOOLEAN` type | Semantic clarity | Replace INTEGER 0/1 columns |
| Table partitioning | Large table performance | `communications` by timestamp |
| Row-level security | Per-user data access control | Permissions enforcement |
| `pg_trgm` + GIN | Fuzzy text search | Contact name search, conversation title search |

### 18.3 Abstraction Strategy

For the PoC, a thin compatibility layer handles the few syntactic differences:

```python
# Pseudo-code
if dialect == 'sqlite':
    json_field = f"json_extract({column}, '$.{path}')"
elif dialect == 'postgresql':
    json_field = f"{column}->>'{path}'"
```

When SQLAlchemy Core is introduced (Phase 2), dialect abstraction is handled by the library automatically.

---

## 19. Glossary

| Term | Definition |
|---|---|
| **Adjacency list** | Tree storage pattern where each row has a `parent_id` pointing to its parent row in the same table. |
| **Communication** | The atomic unit of the system. A single email, SMS, phone call, video meeting, in-person meeting, or user-entered note. |
| **Conversation** | A logical grouping of related communications between specific participants about a specific subject. Can span channels. Account-independent. |
| **Denormalization** | Storing computed/derived data redundantly to avoid JOINs and aggregations on read. Trades write complexity for read speed. |
| **Display content** | The portion of a communication's text shown in a specific conversation's context. Stored on the `conversation_communications` join table. |
| **Idempotent** | An operation that produces the same result regardless of how many times it is executed. All sync operations in this system are idempotent. |
| **Polymorphic table** | A single table that stores multiple entity types distinguished by a discriminator column (`channel`). |
| **Project** | Top-level organizational container. Supports recursive sub-projects via adjacency list. |
| **Provider account** | A connected data source (Gmail account, Outlook account, SMS provider, etc.) with sync state. |
| **Provider adapter** | Application-layer module that normalizes a provider's API to the common communication schema. |
| **Segment** | *Deprecated concept.* Replaced by the M:N `conversation_communications` join table with `display_content`. |
| **Sync cursor** | Opaque marker tracking the system's position in a provider's data stream. Provider-specific format. |
| **Tag** | AI-extracted keyword phrase applied to conversations. Distinct from organizational topics. |
| **Tenant** | An organizational unit (company/team) with its own isolated schema in PostgreSQL. |
| **Topic** | Organizational grouping within a project. Groups conversations about the same subject area with different participants. |
| **UPSERT** | INSERT-or-UPDATE operation using `ON CONFLICT` clause. Ensures idempotent writes. |
| **View** | User-defined saved query against the data model. Foundation for both dashboards and alerts. |

---

*This document is a living specification. It will be updated as implementation progresses, as the Conversations PRD evolves, and as production deployment reveals optimization opportunities. Schema changes after initial deployment will be managed via Alembic migrations with upgrade and downgrade paths.*
