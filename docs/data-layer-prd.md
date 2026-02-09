# Data Layer & Database Architecture PRD

## CRMExtender — Communication & Conversation Intelligence Data Model

**Version:** 2.0
**Date:** 2026-02-08
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

This document defines the data layer architecture for the CRMExtender Communication & Conversation Intelligence subsystem. It replaces the current 8-table email-only SQLite schema with a 21-table multi-channel design that supports the full organizational hierarchy (Project → Topic → Conversation → Communication), multi-channel communications (email, SMS, phone, video, in-person, notes), AI-powered auto-organization with learning from user corrections, multi-identifier contact resolution, communication version control, and user-defined views and alerts.

**Key architectural decisions:**

- **PostgreSQL** for production; **SQLite** for continued PoC development. The schema is designed for compatibility with both engines.
- **Conventional mutable tables** (not event-sourced) for the conversations subsystem. Event sourcing is reserved for contacts and intelligence entities per the parent PRD.
- **Single polymorphic table** for communications across all channel types, with nullable channel-specific columns.
- **Many-to-many** relationship between conversations and communications, enabling a single communication to appear in multiple conversations with context-specific display content.
- **Adjacency list** pattern for recursive project/sub-project nesting.
- **Strategic denormalization** on the conversations table for display performance (counts, timestamps), with computed data reserved for detail views.
- **Multi-identifier contact model** — contacts resolved via a `contact_identifiers` table supporting email, phone, and any future identifier types with lifecycle tracking.
- **AI assignment tracking** — every conversation-communication link records how it was assigned (sync, AI, user), confidence level, and review status.
- **Three correction tables** for AI learning — assignment corrections, triage corrections, and conversation corrections capture user feedback as training signals.
- **Communication version control** — linked-list revision chain preserving full edit history for user-entered communications.
- **21 tables** total, up from 8 in the current PoC.

---

## 2. Technology Selection & Rationale

### 2.1 Primary Database: PostgreSQL 16+

| Factor | Assessment |
|---|---|
| **Why PostgreSQL** | The parent PRD mandates PostgreSQL for the production data layer. Strong typing, JSONB support, schema-per-tenant isolation, materialized views, `WITH RECURSIVE` for tree queries, and mature migration tooling (Alembic) make it the clear choice. |
| **Event sourcing support** | PostgreSQL handles both the event store (append-only tables) and materialized views (current-state tables) for entities that require it. The conversations subsystem uses conventional tables but coexists in the same database. |
| **Multi-tenancy** | Schema-per-tenant isolation (see Section 15) provides strong data separation without operational complexity of database-per-tenant. |
| **JSONB** | Used for `query_def` in views, `provider_metadata` and `user_metadata` on communications. GIN-indexable for production query performance. |
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
7. **Contacts are created immediately.** Unknown identifiers create minimal contact records on first encounter, preventing zombie communications with no contact linkage.
8. **Every correction is a training signal.** User corrections to assignments, triage, and conversation management are captured in dedicated tables to feed the AI Learning system.

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
| Contact identity model | Multi-identifier table (`contact_identifiers`) | A contact can have multiple emails, phone numbers, and other identifiers; avoids duplicate contacts when the same person is encountered via different channels | Single email column on contacts (breaks with multi-channel; causes duplicate contacts requiring painful merges) |
| Contact creation on unknown identifier | Create immediately with `status='incomplete'` | Prevents zombie communications with no `contact_id`; subsequent communications from the same identifier resolve instantly; Contact Intelligence system enriches asynchronously | Signal-only (no contact record; causes repeated signals and backfill complexity) |
| Communication version control | Linked-list revision chain (`previous_revision` / `next_revision`) | Full edit history for user-entered communications; conversation always points to latest revision; old versions accessible via chain traversal | Overwrite (loses history); separate versions table (adds JOINs to every read) |
| AI assignment tracking | `assignment_source`, `confidence`, `reviewed` on join table | Enables the review workflow ("14 new, 11 auto-assigned, 3 unassigned"); supports learning from corrections; distinguishes sync vs AI vs user assignments | Boolean `is_primary` only (loses assignment provenance; no confidence tracking) |

---

## 4. Entity-Relationship Diagram

```mermaid
erDiagram
    users {
        TEXT id PK
        TEXT email
        TEXT name
        TEXT role
        INTEGER is_active
        TEXT created_at
        TEXT updated_at
    }

    projects {
        TEXT id PK
        TEXT parent_id FK
        TEXT name
        TEXT description
        TEXT status
        TEXT owner_id FK
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
        INTEGER dismissed
        TEXT dismissed_reason
        TEXT dismissed_at
        TEXT dismissed_by FK
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
        TEXT assignment_source
        REAL confidence
        INTEGER reviewed
        TEXT reviewed_at
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
        TEXT provider_metadata
        TEXT user_metadata
        TEXT previous_revision FK
        TEXT next_revision FK
        INTEGER is_current
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
        TEXT name
        TEXT company
        TEXT source
        TEXT status
        TEXT created_at
        TEXT updated_at
    }

    contact_identifiers {
        TEXT id PK
        TEXT contact_id FK
        TEXT type
        TEXT value
        TEXT label
        INTEGER is_primary
        TEXT status
        TEXT source
        INTEGER verified
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
        TEXT owner_id FK
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
        TEXT owner_id FK
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

    assignment_corrections {
        TEXT id PK
        TEXT communication_id FK
        TEXT from_conversation_id FK
        TEXT to_conversation_id FK
        TEXT correction_type
        TEXT original_source
        REAL original_confidence
        TEXT corrected_by FK
        TEXT created_at
    }

    triage_corrections {
        TEXT id PK
        TEXT communication_id FK
        TEXT original_result
        TEXT corrected_result
        TEXT correction_type
        TEXT sender_address
        TEXT sender_domain
        TEXT subject
        TEXT corrected_by FK
        TEXT created_at
    }

    triage_rules {
        TEXT id PK
        TEXT rule_type
        TEXT match_type
        TEXT match_value
        TEXT source
        REAL confidence
        TEXT user_id FK
        TEXT created_at
    }

    conversation_corrections {
        TEXT id PK
        TEXT conversation_id FK
        TEXT correction_type
        TEXT reason
        TEXT details
        TEXT participant_addresses
        TEXT subject
        INTEGER communication_count
        TEXT corrected_by FK
        TEXT created_at
    }

    projects ||--o{ projects : "parent_id (sub-projects)"
    projects ||--o{ topics : "contains"
    users ||--o{ projects : "owns"
    users ||--o{ views : "owns"
    users ||--o{ alerts : "owns"
    topics ||--o{ conversations : "groups"
    conversations ||--o{ conversation_participants : "has"
    conversations ||--o{ conversation_communications : "contains"
    conversations ||--o{ conversation_tags : "tagged"
    conversations ||--o{ conversation_corrections : "corrected"
    communications ||--o{ conversation_communications : "appears in"
    communications ||--o{ communication_participants : "involves"
    communications ||--o{ attachments : "has"
    communications ||--o{ assignment_corrections : "corrected"
    communications ||--o{ triage_corrections : "corrected"
    communications ||--o| communications : "previous_revision"
    communications ||--o| communications : "next_revision"
    provider_accounts ||--o{ communications : "sourced from"
    provider_accounts ||--o{ sync_log : "logged by"
    contacts ||--o{ contact_identifiers : "identified by"
    contacts ||--o{ conversation_participants : "identified as"
    contacts ||--o{ communication_participants : "identified as"
    tags ||--o{ conversation_tags : "applied to"
    views ||--o{ alerts : "triggers"
```

### Relationship Summary

```
users
  ├── projects (owner)
  ├── views (owner)
  └── alerts (owner)

projects (self-referential)
  └── topics
        └── conversations
              ├── conversation_participants ──→ contacts ──→ contact_identifiers
              ├── conversation_communications
              │     └── communications (self-referential: revision chain)
              │           ├── communication_participants ──→ contacts
              │           ├── attachments
              │           └── provider_accounts
              ├── conversation_tags ──→ tags
              └── conversation_corrections

communications
  ├── assignment_corrections
  └── triage_corrections

triage_rules (standalone)

views
  └── alerts

provider_accounts
  └── sync_log
```

---

## 5. Schema Design

### 5.1 `users`

Minimal user table providing FK targets for ownership and audit columns throughout the schema. The full authentication and authorization system is a platform-level concern defined in the parent PRD.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | TEXT | **PK** | UUID v4 |
| `email` | TEXT | NOT NULL, **UNIQUE** | User's email address, lowercased |
| `name` | TEXT | | Display name |
| `role` | TEXT | DEFAULT `'member'` | User role: `admin`, `manager`, `member` |
| `is_active` | INTEGER | DEFAULT 1 | Boolean (0/1). Inactive users cannot log in but their data is preserved. |
| `created_at` | TEXT | NOT NULL | ISO 8601 |
| `updated_at` | TEXT | NOT NULL | ISO 8601 |

**PoC note:** For the single-user PoC, this table may contain one row or be empty. `owner_id` and `corrected_by` columns throughout the schema are nullable and not enforced via FK in the PoC phase.

---

### 5.2 `provider_accounts`

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

### 5.3 `contacts`

Known contacts from address books, manual entry, auto-detection, or identity resolution. Global (not per-account). Contact identity is resolved via the `contact_identifiers` table — the contacts table holds the unified contact record.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | TEXT | **PK** | UUID v4 |
| `name` | TEXT | | Display name |
| `company` | TEXT | | Company or organization name |
| `source` | TEXT | | How this contact was first created: `google_contacts`, `auto_detected`, `manual`, `osint` |
| `status` | TEXT | DEFAULT `'active'` | Contact lifecycle: `active` (enriched, verified), `incomplete` (auto-created from unknown identifier, needs enrichment) |
| `created_at` | TEXT | NOT NULL | ISO 8601 |
| `updated_at` | TEXT | NOT NULL | ISO 8601 |

**No `email` column.** Email addresses (and all other identifiers) live in `contact_identifiers`. This prevents the duplicate-contact problem that arises when the same person is encountered via different identifiers (work email vs personal email vs phone number).

**Auto-detection flow:** When a communication arrives from an unknown identifier:
1. Look up `contact_identifiers` for a match → if found, use existing `contact_id`.
2. If not found → create a new contact with `source='auto_detected'`, `status='incomplete'`.
3. Create a `contact_identifier` row linking the identifier to the new contact.
4. Signal the Contact Intelligence system to enrich the contact.
5. All subsequent communications from the same identifier resolve immediately.

**Contact Intelligence integration:** The Contact Intelligence system (separate PRD) enriches incomplete contacts, merges duplicate contacts discovered across identifiers, and adds additional identifier types. This table provides the minimal structure needed by the conversations subsystem. The CIS will extend it with additional fields.

---

### 5.4 `contact_identifiers`

Maps identifiers (email addresses, phone numbers, social handles, etc.) to contacts. Supports multiple identifiers per contact with type, lifecycle status, and verification state. This is the primary lookup table for resolving incoming communications to contacts.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | TEXT | **PK** | UUID v4 |
| `contact_id` | TEXT | NOT NULL, FK → `contacts(id)` ON DELETE CASCADE | Which contact this identifier belongs to |
| `type` | TEXT | NOT NULL | Identifier type: `email`, `phone`, `slack`, `linkedin`, `twitter`, etc. |
| `value` | TEXT | NOT NULL | The identifier value, normalized. Email: lowercased. Phone: E.164 format. |
| `label` | TEXT | | User-facing label: `work`, `personal`, `mobile`, `old`, etc. |
| `is_primary` | INTEGER | DEFAULT 0 | Boolean. Primary identifier for this type (e.g., primary work email). |
| `status` | TEXT | DEFAULT `'active'` | Identifier lifecycle: `active` (current, valid), `inactive` (no longer in use but still resolves for historical communications), `unverified` (auto-detected, not confirmed) |
| `source` | TEXT | | How this identifier was discovered: `google_contacts`, `auto_detected`, `sms_sync`, `osint`, `manual` |
| `verified` | INTEGER | DEFAULT 0 | Boolean. Confirmed by CIS, user, or source system. |
| `created_at` | TEXT | NOT NULL | ISO 8601 |
| `updated_at` | TEXT | NOT NULL | ISO 8601 |

**Unique constraint:** `UNIQUE(type, value)` — no two contacts can claim the same identifier. If a merge is needed, the Contact Intelligence system handles it.

**Resolution flow:**

```sql
-- Resolve any incoming identifier to a contact
SELECT ci.contact_id
FROM contact_identifiers ci
WHERE ci.type = ? AND ci.value = ?;
```

This single query works for email addresses, phone numbers, Slack handles, or any future identifier type. The `status` column ensures inactive identifiers (old email addresses, changed phone numbers) still resolve correctly for historical communications.

**Example contact with multiple identifiers:**

```
Contact: Sarah Chen (Acme Corp)  [status=active]
├── email: sarah@acmecorp.com         (active, work, primary, verified)
├── email: sarah.chen@oldcompany.com  (inactive, work, verified)
├── email: sarahc@gmail.com           (active, personal, verified)
├── phone: +15550199                  (active, mobile, primary, verified)
└── slack: @sarah.chen                (active, unverified)
```

**Contact merge flow** (handled by Contact Intelligence system):

When two contacts are discovered to be the same person:
1. Pick one `contact_id` as the survivor.
2. Move all identifiers from the duplicate to the survivor: `UPDATE contact_identifiers SET contact_id = ? WHERE contact_id = ?`
3. Update all references: `UPDATE communication_participants SET contact_id = ? WHERE contact_id = ?`
4. Update all references: `UPDATE conversation_participants SET contact_id = ? WHERE contact_id = ?`
5. Delete the duplicate contact (CASCADE cleans up any remaining references).

---

### 5.5 `projects`

Top-level organizational container. Supports recursive nesting via adjacency list (self-referential `parent_id`).

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | TEXT | **PK** | UUID v4 |
| `parent_id` | TEXT | FK → `projects(id)` ON DELETE CASCADE | Parent project for sub-projects. NULL for top-level projects. |
| `name` | TEXT | NOT NULL | User-defined project name |
| `description` | TEXT | | Optional description of purpose and scope |
| `status` | TEXT | DEFAULT `'active'` | Lifecycle state: `active`, `on_hold`, `completed`, `archived` |
| `owner_id` | TEXT | FK → `users(id)` ON DELETE SET NULL | User who created/manages this project |
| `created_at` | TEXT | NOT NULL | ISO 8601 |
| `updated_at` | TEXT | NOT NULL | ISO 8601 |

**Adjacency list pattern:** A sub-project is a row with `parent_id` pointing to its parent. Top-level projects have `parent_id = NULL`. Tree traversal uses `WITH RECURSIVE` CTEs.

**Reparenting:** Moving a sub-project to a different parent is a single-row update: `UPDATE projects SET parent_id = ? WHERE id = ?`. No descendant rows are affected.

**Cascade delete:** Deleting a project deletes all sub-projects, their topics, and the topic-conversation links (conversations themselves survive with `topic_id` set to NULL via SET NULL on the `conversations.topic_id` FK).

---

### 5.6 `topics`

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

### 5.7 `conversations`

The central entity linking communications to the organizational hierarchy. Contains denormalized statistics for fast listing queries, AI-generated intelligence fields, and user dismissal state.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | TEXT | **PK** | UUID v4 |
| `topic_id` | TEXT | FK → `topics(id)` ON DELETE SET NULL | Optional link to organizational hierarchy. NULL for unassigned conversations. |
| `title` | TEXT | | Conversation title. Initially derived from email subject; user-editable. Defaults to `'(untitled)'` if empty. |
| `status` | TEXT | DEFAULT `'active'` | System status (time-based): `active`, `stale`, `closed`. See Section 5.7.1. |
| `communication_count` | INTEGER | DEFAULT 0 | **Denormalized.** Total communications across all channels. Maintained on add/remove. |
| `participant_count` | INTEGER | DEFAULT 0 | **Denormalized.** Distinct participants. Maintained from `conversation_participants`. |
| `first_activity_at` | TEXT | | **Denormalized.** ISO 8601 timestamp of earliest communication. |
| `last_activity_at` | TEXT | | **Denormalized.** ISO 8601 timestamp of most recent communication. Used for recency sorting. |
| `ai_summary` | TEXT | | AI-generated 2-4 sentence summary. NULL until AI processes the conversation. |
| `ai_status` | TEXT | | AI semantic classification: `open`, `closed`, `uncertain`. NULL until AI processes. |
| `ai_action_items` | TEXT | | JSON array of extracted action item strings. NULL if none or not yet processed. |
| `ai_topics` | TEXT | | JSON array of AI-extracted topic tag strings (source-of-truth from AI). Normalized version stored in `tags` / `conversation_tags`. |
| `ai_summarized_at` | TEXT | | ISO 8601 timestamp of last AI processing. Set to NULL when new communications arrive, marking the conversation for re-processing. |
| `triage_result` | TEXT | | Rollup of communication-level triage. NULL if at least one communication passed triage. Non-NULL only when ALL communications are triaged, indicating the dominant filter reason. |
| `dismissed` | INTEGER | DEFAULT 0 | Boolean. User explicitly dismissed this conversation (all communications may be legitimate, but the grouping is not useful). |
| `dismissed_reason` | TEXT | | Why dismissed: `not_a_conversation`, `irrelevant`, `duplicate`, or user-entered text. NULL if not dismissed. |
| `dismissed_at` | TEXT | | ISO 8601 timestamp of dismissal. NULL if not dismissed. |
| `dismissed_by` | TEXT | FK → `users(id)` ON DELETE SET NULL | User who dismissed. NULL if not dismissed. |
| `created_at` | TEXT | NOT NULL | ISO 8601 |
| `updated_at` | TEXT | NOT NULL | ISO 8601 |

#### 5.7.1 Status Dimensions

| Dimension | Column | Values | Source |
|---|---|---|---|
| **System status** | `status` | `active`, `stale`, `closed` | Time-based, automatic. Active → Stale after N days inactivity (configurable, default 14). Stale → Closed after M days (default 30). Any new communication reopens to Active. |
| **AI status** | `ai_status` | `open`, `closed`, `uncertain` | Semantic, from AI analysis. Biased toward `open` for multi-message exchanges. |
| **Triage status** | `triage_result` | NULL (passed) or filter reason string | Rollup from communication-level triage. |
| **Dismissed** | `dismissed` | 0 (active) or 1 (dismissed) | User override. A dismissed conversation contains legitimate communications but the grouping is not useful. Reversible. |

These dimensions are independent and complementary. A conversation can be system-active but AI-closed (recent messages, but the topic was resolved), or system-stale but AI-open (no recent activity, but an unanswered question remains). Dismissal is orthogonal — a dismissed conversation stops appearing in active listings regardless of other statuses.

#### 5.7.2 Dismissal vs. Triage

| Concept | Scope | Who Decides | Meaning |
|---|---|---|---|
| Triage | Per-communication, rolled up to conversation | System (heuristic + AI) | The communication is automated/marketing noise |
| Dismissal | Per-conversation | User | The communications are legitimate, but the conversation grouping is not useful |

#### 5.7.3 Design Rationale: AI Fields on the Conversation Row

AI intelligence fields are stored directly on the conversation row rather than in a separate `conversation_summaries` table. The relationship is strictly 1:1, and the most common query pattern is listing conversations with their summaries. Inlining avoids a JOIN on every listing query. The tradeoff is wider rows, but conversation cardinality is low (hundreds to low thousands per user).

#### 5.7.4 Design Rationale: Denormalized Counts

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
WHERE triage_result IS NULL AND dismissed = 0
ORDER BY last_activity_at DESC;
```

The maintenance cost is a few UPDATE statements when communications are added or removed. This is an acceptable tradeoff for a system where display speed is paramount.

---

### 5.8 `conversation_participants`

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

**Contact resolution:** When a `contact_id` is resolved for an address (either immediately via `contact_identifiers` lookup or later via Contact Intelligence enrichment), all `conversation_participants` rows with that address are updated.

---

### 5.9 `communications`

The atomic unit of the system. A single polymorphic table storing all communication types: email, SMS, phone calls, video meetings, in-person meetings, and user-entered notes. Supports version control for user-edited content via a linked-list revision chain.

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
| **Metadata** | | | |
| `provider_metadata` | TEXT | | JSON. Provider-sourced metadata (Gmail labels, Outlook categories, read receipts, delivery status). Written by sync pipeline only. |
| `user_metadata` | TEXT | | JSON. User-defined tags, labels, and custom attributes. Written by user only. |
| **Version control** | | | |
| `previous_revision` | TEXT | FK → `communications(id)` ON DELETE SET NULL | Previous version of this communication. NULL for original/unedited. |
| `next_revision` | TEXT | FK → `communications(id)` ON DELETE SET NULL | Next version (superseding revision). NULL for current/latest version. |
| `is_current` | INTEGER | DEFAULT 1 | Boolean. 1 = latest revision (displayed in conversations). 0 = superseded by a newer revision. |
| **AI fields** | | | |
| `ai_summary` | TEXT | | Per-communication AI summary. Only generated for long content (>200 words). |
| `ai_summarized_at` | TEXT | | ISO 8601 timestamp of AI processing |
| **Triage** | | | |
| `triage_result` | TEXT | | Per-communication triage. NULL if passed. Non-NULL: filter reason (`automated_sender`, `automated_subject`, `marketing`, `no_known_contacts`). |
| **Timestamps** | | | |
| `created_at` | TEXT | NOT NULL | ISO 8601 |
| `updated_at` | TEXT | NOT NULL | ISO 8601 |

**Unique constraints:**
- `UNIQUE(account_id, provider_message_id)` — prevents duplicate sync of the same message. Only applies when both fields are non-NULL (manually entered communications have no `provider_message_id`).

#### 5.9.1 Version Control (Revision Chain)

User-entered communications (notes, unrecorded call summaries, meeting notes) can be edited. Auto-synced communications (email, SMS) are immutable — their content comes from the provider.

When a user edits a communication:

```
1. INSERT new communication (v2) with:
   - All fields copied from v1
   - content = user's updated text
   - previous_revision = v1.id
   - next_revision = NULL
   - is_current = 1

2. UPDATE old communication (v1):
   - next_revision = v2.id
   - is_current = 0

3. UPDATE conversation_communications:
   - Change communication_id from v1.id to v2.id
   (conversation now points to latest revision)
```

The revision chain: `v1 ──next──→ v2 ──next──→ v3 (is_current=1)`

**Querying revision history:**

```sql
WITH RECURSIVE history AS (
    SELECT * FROM communications WHERE id = ?
    UNION ALL
    SELECT c.* FROM communications c
    JOIN history h ON c.id = h.previous_revision
)
SELECT * FROM history ORDER BY created_at;
```

**Immutability enforcement:** Application-layer only. The `channel` and `source` fields indicate which communications are editable (channel IN ('note', 'in_person') OR source = 'manual').

#### 5.9.2 Metadata Columns

Two JSON columns serve different purposes:

| Column | Written By | Purpose | Examples |
|---|---|---|---|
| `provider_metadata` | Sync pipeline only | Provider-specific data not mapped to dedicated columns | `{"labels": ["Primary", "Important"], "category": "primary", "starred": true}` (Gmail); `{"delivery_status": "delivered"}` (SMS) |
| `user_metadata` | User only | User-defined tags, labels, custom attributes | `{"tags": ["urgent", "follow-up"], "priority": "high", "custom_notes": "Review before Monday"}` |

Both columns use TEXT (SQLite) / JSONB (PostgreSQL) and are queryable via `json_extract()` / JSONB operators.

#### 5.9.3 Column Usage by Channel

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
| `is_current` | Always 1 | Always 1 | Always 1 | Always 1 | Versioned | Versioned |

---

### 5.10 `communication_participants`

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

**Note:** The sender is stored on the `communications` row (`sender_address`, `sender_name`), not in this table. This avoids a JOIN for the most common display pattern.

---

### 5.11 `conversation_communications`

Many-to-many join between conversations and communications. Each row stores the display content, assignment provenance, and review status.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `conversation_id` | TEXT | NOT NULL, FK → `conversations(id)` ON DELETE CASCADE | Which conversation |
| `communication_id` | TEXT | NOT NULL, FK → `communications(id)` ON DELETE CASCADE | Which communication |
| `display_content` | TEXT | | The text to display for this communication in this conversation's context. NULL means display the full `communications.content`. For secondary assignments, contains the user-selected portion. |
| `is_primary` | INTEGER | DEFAULT 1 | 1 = original/automatic assignment. 0 = user explicitly added this communication to the conversation. |
| `assignment_source` | TEXT | NOT NULL DEFAULT `'sync'` | How this assignment was made: `sync` (email threading), `ai` (AI classification), `user` (manual assignment) |
| `confidence` | REAL | DEFAULT 1.0 | AI confidence score for this assignment. 1.0 for sync and user assignments. 0.0-1.0 for AI assignments. |
| `reviewed` | INTEGER | DEFAULT 0 | Boolean. Whether a user has reviewed this assignment. Defaults: `sync` email → 1 (trusted), `ai` → 0 (needs review), non-email `sync` → 0 (needs review), `user` → 1 (inherently reviewed). |
| `reviewed_at` | TEXT | | ISO 8601 timestamp of user review. NULL if not yet reviewed. |
| `created_at` | TEXT | NOT NULL | ISO 8601 |

**Primary key:** `(conversation_id, communication_id)`

**Review workflow queries:**

```sql
-- Auto-assigned, not yet reviewed (for review screen)
SELECT cc.*, c.title, comm.content, comm.channel, comm.sender_name
FROM conversation_communications cc
JOIN conversations c ON c.id = cc.conversation_id
JOIN communications comm ON comm.id = cc.communication_id
WHERE cc.assignment_source IN ('ai', 'sync')
  AND cc.reviewed = 0
ORDER BY comm.timestamp DESC;

-- Unassigned communications (needs user input)
SELECT * FROM communications
WHERE is_current = 1
  AND id NOT IN (SELECT communication_id FROM conversation_communications);
```

**Default `reviewed` values by assignment source and channel:**

| Assignment Source | Channel | Default `reviewed` | Rationale |
|---|---|---|---|
| `sync` | `email` | 1 | Email threading (Gmail `threadId`) is highly reliable |
| `sync` | non-email | 0 | Non-email sync groupings (participant-based) need user review |
| `ai` | any | 0 | AI assignments always need user review |
| `user` | any | 1 | User assignments are inherently reviewed |

---

### 5.12 `attachments`

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

---

### 5.13 `tags`

Normalized AI-extracted topic tags. Distinct from the hierarchy's `topics` table. Tags are short keyword phrases used for cross-conversation discovery and filtering.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | TEXT | **PK** | UUID v4 |
| `name` | TEXT | NOT NULL, **UNIQUE** | Tag string, lowercased and trimmed. |
| `source` | TEXT | DEFAULT `'ai'` | How created: `ai`, `user` |
| `created_at` | TEXT | NOT NULL | ISO 8601 |

**Write pattern:** `INSERT ... ON CONFLICT(name) DO NOTHING` — existing tags are reused, not duplicated.

---

### 5.14 `conversation_tags`

Many-to-many join between conversations and AI-extracted tags.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `conversation_id` | TEXT | NOT NULL, FK → `conversations(id)` ON DELETE CASCADE | Which conversation |
| `tag_id` | TEXT | NOT NULL, FK → `tags(id)` ON DELETE CASCADE | Which tag |
| `confidence` | REAL | DEFAULT 1.0 | AI confidence score. |
| `source` | TEXT | DEFAULT `'ai'` | Assignment source: `ai`, `user` |
| `created_at` | TEXT | NOT NULL | ISO 8601 |

**Primary key:** `(conversation_id, tag_id)`

---

### 5.15 `views`

User-defined saved queries against the data model. The foundation for both dashboards and alerts.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | TEXT | **PK** | UUID v4 |
| `owner_id` | TEXT | FK → `users(id)` ON DELETE SET NULL | User who created the view |
| `name` | TEXT | NOT NULL | User-defined view name |
| `description` | TEXT | | Optional description |
| `query_def` | TEXT | NOT NULL | JSON object defining filters, sorting, grouping, and columns. Interpreted by the backend query builder. |
| `is_shared` | INTEGER | DEFAULT 0 | 0 = private to owner. 1 = visible to team members. |
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

---

### 5.16 `alerts`

User-defined notification triggers attached to views.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | TEXT | **PK** | UUID v4 |
| `view_id` | TEXT | NOT NULL, FK → `views(id)` ON DELETE CASCADE | Which view this alert monitors |
| `owner_id` | TEXT | FK → `users(id)` ON DELETE SET NULL | User who created the alert |
| `is_active` | INTEGER | DEFAULT 1 | Boolean. Alert can be paused without deleting. |
| `frequency` | TEXT | NOT NULL | How often to check: `immediate`, `hourly`, `daily`, `weekly` |
| `aggregation` | TEXT | DEFAULT `'batched'` | How to deliver multiple results: `individual`, `batched` |
| `delivery_method` | TEXT | NOT NULL | How to deliver: `in_app`, `push`, `email`, `sms` |
| `last_triggered` | TEXT | | ISO 8601 timestamp of last alert delivery. |
| `created_at` | TEXT | NOT NULL | ISO 8601 |
| `updated_at` | TEXT | NOT NULL | ISO 8601 |

**No default alerts.** Zero rows exist until the user creates them.

---

### 5.17 `sync_log`

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

### 5.18 `assignment_corrections`

Records user corrections to conversation assignments. When a user moves a communication from one conversation to another, this table captures the correction as a training signal for the AI classification system.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | TEXT | **PK** | UUID v4 |
| `communication_id` | TEXT | NOT NULL, FK → `communications(id)` ON DELETE CASCADE | Which communication was reassigned |
| `from_conversation_id` | TEXT | FK → `conversations(id)` ON DELETE SET NULL | Previous conversation (NULL if communication was unassigned) |
| `to_conversation_id` | TEXT | FK → `conversations(id)` ON DELETE SET NULL | New conversation (NULL if communication was unassigned) |
| `correction_type` | TEXT | NOT NULL | Type of correction: `reassign` (moved between conversations), `assign` (newly assigned from unassigned), `remove` (removed from conversation) |
| `original_source` | TEXT | | What made the original assignment: `sync`, `ai` |
| `original_confidence` | REAL | | What confidence the AI had for the original assignment |
| `corrected_by` | TEXT | FK → `users(id)` ON DELETE SET NULL | User who made the correction |
| `created_at` | TEXT | NOT NULL | ISO 8601 |

**AI Learning queries:**

```sql
-- Which sender/subject patterns does the AI consistently get wrong?
SELECT comm.sender_address, comm.subject, COUNT(*) as correction_count
FROM assignment_corrections ac
JOIN communications comm ON comm.id = ac.communication_id
WHERE ac.original_source = 'ai'
GROUP BY comm.sender_address, comm.subject
ORDER BY correction_count DESC;

-- What confidence threshold produces acceptable accuracy?
SELECT
    CASE WHEN ac.original_confidence >= 0.8 THEN 'high'
         WHEN ac.original_confidence >= 0.5 THEN 'medium'
         ELSE 'low' END as confidence_band,
    COUNT(*) as corrections
FROM assignment_corrections ac
WHERE ac.original_source = 'ai'
GROUP BY confidence_band;
```

---

### 5.19 `triage_corrections`

Records user corrections to triage decisions. Captures both false positives (system filtered a legitimate communication) and false negatives (system missed junk).

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | TEXT | **PK** | UUID v4 |
| `communication_id` | TEXT | NOT NULL, FK → `communications(id)` ON DELETE CASCADE | Which communication had its triage corrected |
| `original_result` | TEXT | | System's original triage decision. NULL = passed triage (system thought it was legitimate). Non-NULL = filter reason. |
| `corrected_result` | TEXT | | User's correction. NULL = legitimate (user says it's not junk). Non-NULL = filter reason (user says it is junk). |
| `correction_type` | TEXT | NOT NULL | `false_positive` (was filtered, should not be) or `false_negative` (was not filtered, should be) |
| `sender_address` | TEXT | | **Denormalized.** Sender's address for pattern learning queries. |
| `sender_domain` | TEXT | | **Denormalized.** Sender's domain (e.g., `acmecorp.com`) for domain-level pattern learning. |
| `subject` | TEXT | | **Denormalized.** Communication subject for pattern learning. |
| `corrected_by` | TEXT | FK → `users(id)` ON DELETE SET NULL | User who made the correction |
| `created_at` | TEXT | NOT NULL | ISO 8601 |

**AI Learning queries:**

```sql
-- Which sender domains does this user consistently mark as legitimate?
SELECT sender_domain, COUNT(*) as override_count
FROM triage_corrections
WHERE correction_type = 'false_positive'
GROUP BY sender_domain
ORDER BY override_count DESC;

-- Which specific senders does this user consistently mark as junk?
SELECT sender_address, COUNT(*) as junk_count
FROM triage_corrections
WHERE correction_type = 'false_negative'
GROUP BY sender_address
ORDER BY junk_count DESC;
```

---

### 5.20 `triage_rules`

Explicit allow/block rules for triage, both user-defined and learned from correction patterns. Evaluated in priority order: user rules > learned rules > heuristic patterns.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | TEXT | **PK** | UUID v4 |
| `rule_type` | TEXT | NOT NULL | `allow` (override triage, mark as legitimate) or `block` (mark as junk) |
| `match_type` | TEXT | NOT NULL | What to match: `sender` (exact address), `domain` (sender domain), `subject_pattern` (subject contains) |
| `match_value` | TEXT | NOT NULL | The match target: `billing@acmecorp.com`, `acmecorp.com`, `invoice` |
| `source` | TEXT | NOT NULL | How the rule was created: `user` (explicit), `learned` (derived from corrections by AI Learning system) |
| `confidence` | REAL | DEFAULT 1.0 | 1.0 for user-created rules. <1.0 for learned rules (based on correction frequency). |
| `user_id` | TEXT | FK → `users(id)` ON DELETE SET NULL | Which user this rule applies to (per-user rules) |
| `created_at` | TEXT | NOT NULL | ISO 8601 |

**Triage evaluation order:**

1. **User rules** (`source = 'user'`, `confidence = 1.0`) — highest priority
2. **Learned rules** (`source = 'learned'`, `confidence < 1.0`) — medium priority
3. **Heuristic patterns** (hardcoded in application) — lowest priority, default

---

### 5.21 `conversation_corrections`

Records user corrections at the conversation level — dismissals, undismissals, merges, splits, and status overrides. Provides training signals for conversation formation logic.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | TEXT | **PK** | UUID v4 |
| `conversation_id` | TEXT | NOT NULL, FK → `conversations(id)` ON DELETE CASCADE | Which conversation was corrected |
| `correction_type` | TEXT | NOT NULL | Type of correction: `dismissed`, `undismissed`, `merged`, `split`, `status_override` |
| `reason` | TEXT | | Why: `not_a_conversation`, `irrelevant`, `duplicate`, or user-entered text |
| `details` | TEXT | | JSON for action-specific context (e.g., merged conversation IDs, split details) |
| `participant_addresses` | TEXT | | **Denormalized.** Comma-separated participant addresses for pattern learning. |
| `subject` | TEXT | | **Denormalized.** Conversation title at time of correction. |
| `communication_count` | INTEGER | | **Denormalized.** Number of communications at time of correction. |
| `corrected_by` | TEXT | FK → `users(id)` ON DELETE SET NULL | User who made the correction |
| `created_at` | TEXT | NOT NULL | ISO 8601 |

**AI Learning queries:**

```sql
-- What types of conversations are consistently dismissed?
SELECT subject, participant_addresses, communication_count, COUNT(*) as dismiss_count
FROM conversation_corrections
WHERE correction_type = 'dismissed'
GROUP BY subject, participant_addresses, communication_count
ORDER BY dismiss_count DESC;
```

---

## 6. Relationships & Referential Integrity

### 6.1 Foreign Key Summary

| Parent | Child | FK Column | Cardinality | On Delete |
|---|---|---|---|---|
| `users` | `projects` | `owner_id` | 1:N | SET NULL |
| `users` | `views` | `owner_id` | 1:N | SET NULL |
| `users` | `alerts` | `owner_id` | 1:N | SET NULL |
| `users` | `conversations` | `dismissed_by` | 1:N | SET NULL |
| `users` | `assignment_corrections` | `corrected_by` | 1:N | SET NULL |
| `users` | `triage_corrections` | `corrected_by` | 1:N | SET NULL |
| `users` | `triage_rules` | `user_id` | 1:N | SET NULL |
| `users` | `conversation_corrections` | `corrected_by` | 1:N | SET NULL |
| `projects` | `projects` | `parent_id` | 1:N (self) | CASCADE |
| `projects` | `topics` | `project_id` | 1:N | CASCADE |
| `topics` | `conversations` | `topic_id` | 1:N | SET NULL |
| `conversations` | `conversation_participants` | `conversation_id` | 1:N | CASCADE |
| `conversations` | `conversation_communications` | `conversation_id` | 1:N | CASCADE |
| `conversations` | `conversation_tags` | `conversation_id` | 1:N | CASCADE |
| `conversations` | `conversation_corrections` | `conversation_id` | 1:N | CASCADE |
| `communications` | `conversation_communications` | `communication_id` | 1:N | CASCADE |
| `communications` | `communication_participants` | `communication_id` | 1:N | CASCADE |
| `communications` | `attachments` | `communication_id` | 1:N | CASCADE |
| `communications` | `communications` | `previous_revision` | 0..1:1 (self) | SET NULL |
| `communications` | `communications` | `next_revision` | 0..1:1 (self) | SET NULL |
| `communications` | `assignment_corrections` | `communication_id` | 1:N | CASCADE |
| `communications` | `triage_corrections` | `communication_id` | 1:N | CASCADE |
| `provider_accounts` | `communications` | `account_id` | 1:N | SET NULL |
| `provider_accounts` | `sync_log` | `account_id` | 1:N | CASCADE |
| `contacts` | `contact_identifiers` | `contact_id` | 1:N | CASCADE |
| `contacts` | `conversation_participants` | `contact_id` | 0..1:N | SET NULL |
| `contacts` | `communication_participants` | `contact_id` | 0..1:N | SET NULL |
| `tags` | `conversation_tags` | `tag_id` | 1:N | CASCADE |
| `views` | `alerts` | `view_id` | 1:N | CASCADE |

### 6.2 Delete Behavior Rationale

| Behavior | Where Used | Why |
|---|---|---|
| **CASCADE** | Parent → child aggregates (project → topics, communication → participants, contact → identifiers, conversation → corrections) | Children are meaningless without parent |
| **SET NULL** | `conversations.topic_id`, `communications.account_id`, `*.contact_id`, `*.owner_id`, `*.corrected_by`, revision chain FKs | Entity survives deletion of its association. A conversation remains even if its topic is deleted. A correction record remains even if the user is deleted. A revision survives even if its predecessor is deleted. |

### 6.3 FK Enforcement

- **SQLite:** `PRAGMA foreign_keys = ON` on every connection.
- **PostgreSQL:** FKs enforced by default. Deferred constraints used where circular dependencies arise (the `previous_revision`/`next_revision` self-references on communications may require deferred FK checks during revision creation).

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
| `idx_comm_current` | `is_current` | Filter to current revisions only |

### 7.2 Conversations Table

| Index | Column(s) | Supports |
|---|---|---|
| `idx_conv_topic` | `topic_id` | "All conversations in topic X" — hierarchy navigation |
| `idx_conv_status` | `status` | Filter by system status (active/stale/closed) |
| `idx_conv_last_activity` | `last_activity_at` | **Primary listing sort** — most recent conversations first |
| `idx_conv_ai_status` | `ai_status` | Filter by AI classification (open/closed/uncertain) |
| `idx_conv_triage` | `triage_result` | Separate triaged from non-triaged conversations |
| `idx_conv_needs_processing` | `triage_result, ai_summarized_at` | Find conversations needing AI processing (both NULL) |
| `idx_conv_dismissed` | `dismissed` | Filter dismissed conversations from listings |

### 7.3 Join Tables

| Index | Column(s) | Supports |
|---|---|---|
| `idx_cc_communication` | `conversation_communications(communication_id)` | "Which conversations contain communication X?" — reverse lookup |
| `idx_cc_review` | `conversation_communications(assignment_source, reviewed)` | Review workflow: find unreviewed auto-assignments |
| `idx_cp_contact` | `conversation_participants(contact_id)` | "All conversations involving contact C" |
| `idx_cp_address` | `conversation_participants(address)` | "All conversations involving address/number X" |
| `idx_commpart_address` | `communication_participants(address)` | "All communications involving address X" |
| `idx_commpart_contact` | `communication_participants(contact_id)` | "All communications involving contact C" |

### 7.4 Contact Resolution

| Index | Column(s) | Supports |
|---|---|---|
| `idx_ci_lookup` | `contact_identifiers(type, value)` | **Primary contact resolution** — resolve any identifier to a contact (UNIQUE constraint serves as index) |
| `idx_ci_contact` | `contact_identifiers(contact_id)` | "All identifiers for contact X" — contact detail view |
| `idx_ci_status` | `contact_identifiers(status)` | Find unverified/inactive identifiers |

### 7.5 Other Tables

| Index | Column(s) | Supports |
|---|---|---|
| `idx_projects_parent` | `projects(parent_id)` | "All sub-projects of project X" — tree navigation |
| `idx_topics_project` | `topics(project_id)` | "All topics in project X" |
| `idx_attachments_comm` | `attachments(communication_id)` | "All attachments for communication X" |
| `idx_sync_log_account` | `sync_log(account_id)` | "Sync history for account X" |
| `idx_views_owner` | `views(owner_id)` | "All views created by user X" |
| `idx_alerts_view` | `alerts(view_id)` | "All alerts on view X" |
| `idx_triage_rules_match` | `triage_rules(match_type, match_value)` | Triage rule evaluation |

### 7.6 Correction Tables

| Index | Column(s) | Supports |
|---|---|---|
| `idx_ac_communication` | `assignment_corrections(communication_id)` | "Correction history for communication X" |
| `idx_tc_communication` | `triage_corrections(communication_id)` | "Triage correction history for communication X" |
| `idx_tc_sender_domain` | `triage_corrections(sender_domain)` | Domain-level pattern learning |
| `idx_cc_conversation` | `conversation_corrections(conversation_id)` | "Correction history for conversation X" |

### 7.7 Indexing Notes

- All indexes use `CREATE INDEX IF NOT EXISTS` for idempotent creation.
- Composite primary keys on join tables serve as implicit indexes on the leading column(s).
- For PostgreSQL production, consider partial indexes where appropriate (e.g., `WHERE triage_result IS NULL AND dismissed = 0` on conversations for the "active conversations" query). These are not available in SQLite, so they are deferred to production optimization.
- Total index count: 33 indexes across 21 tables. Monitor for unused indexes in production via `pg_stat_user_indexes`.

---

## 8. Query Patterns

The most frequently executed queries, their SQL patterns, and which indexes support them.

### 8.1 High-Frequency Queries (Display / Listing)

| Query | SQL Pattern | Indexes |
|---|---|---|
| List active conversations | `SELECT * FROM conversations WHERE triage_result IS NULL AND dismissed = 0 ORDER BY last_activity_at DESC LIMIT ?` | `idx_conv_triage`, `idx_conv_dismissed`, `idx_conv_last_activity` |
| List conversations by AI status | `SELECT * FROM conversations WHERE ai_status = ? AND dismissed = 0 ORDER BY last_activity_at DESC` | `idx_conv_ai_status`, `idx_conv_last_activity` |
| Conversation timeline | `SELECT comm.*, cc.display_content, cc.assignment_source, cc.confidence FROM conversation_communications cc JOIN communications comm ON comm.id = cc.communication_id WHERE cc.conversation_id = ? AND comm.is_current = 1 ORDER BY comm.timestamp` | PK on `conversation_communications`, `idx_comm_timestamp`, `idx_comm_current` |
| Conversation participants | `SELECT * FROM conversation_participants WHERE conversation_id = ?` | PK on `conversation_participants` |
| Resolve identifier to contact | `SELECT contact_id FROM contact_identifiers WHERE type = ? AND value = ?` | `idx_ci_lookup` (UNIQUE) |
| Project hierarchy | `SELECT * FROM projects WHERE parent_id = ?` | `idx_projects_parent` |
| Topics in project | `SELECT * FROM topics WHERE project_id = ?` | `idx_topics_project` |
| Conversations in topic | `SELECT * FROM conversations WHERE topic_id = ? AND dismissed = 0 ORDER BY last_activity_at DESC` | `idx_conv_topic`, `idx_conv_last_activity` |

### 8.2 Medium-Frequency Queries (Processing / Review)

| Query | SQL Pattern | Indexes |
|---|---|---|
| Conversations needing AI | `SELECT * FROM conversations WHERE triage_result IS NULL AND ai_summarized_at IS NULL AND dismissed = 0` | `idx_conv_needs_processing` |
| Unreviewed assignments | `SELECT * FROM conversation_communications WHERE assignment_source IN ('ai','sync') AND reviewed = 0` | `idx_cc_review` |
| Unassigned communications | `SELECT * FROM communications WHERE is_current = 1 AND id NOT IN (SELECT communication_id FROM conversation_communications)` | `idx_comm_current`, `idx_cc_communication` |
| Deduplication check | `SELECT id FROM communications WHERE account_id = ? AND provider_message_id = ?` | UNIQUE constraint |
| Thread grouping | `SELECT * FROM communications WHERE provider_thread_id = ? AND account_id = ?` | `idx_comm_thread` |
| Contact identifiers | `SELECT * FROM contact_identifiers WHERE contact_id = ?` | `idx_ci_contact` |
| All conversations for contact | `SELECT conversation_id FROM conversation_participants WHERE contact_id = ?` | `idx_cp_contact` |
| Triage rule evaluation | `SELECT * FROM triage_rules WHERE match_type = ? AND match_value = ? ORDER BY source` | `idx_triage_rules_match` |

### 8.3 Low-Frequency Queries (Admin / Analytics / Learning)

| Query | SQL Pattern | Indexes |
|---|---|---|
| Full project tree | `WITH RECURSIVE tree AS (...) SELECT * FROM tree` | `idx_projects_parent` |
| Sync history | `SELECT * FROM sync_log WHERE account_id = ? ORDER BY started_at DESC` | `idx_sync_log_account` |
| Tag frequency | `SELECT t.name, COUNT(*) FROM conversation_tags ct JOIN tags t ON t.id = ct.tag_id GROUP BY t.name ORDER BY COUNT(*) DESC` | PK on `conversation_tags` |
| Assignment correction patterns | `SELECT comm.sender_address, COUNT(*) FROM assignment_corrections ac JOIN communications comm ... GROUP BY ...` | `idx_ac_communication` |
| Triage correction patterns | `SELECT sender_domain, COUNT(*) FROM triage_corrections WHERE correction_type = ? GROUP BY sender_domain` | `idx_tc_sender_domain` |
| Communication revision history | `WITH RECURSIVE history AS (...) SELECT * FROM history` | Self-referential FKs |
| Incomplete contacts | `SELECT * FROM contacts WHERE status = 'incomplete'` | (small table, seq scan OK) |

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
| `triage_corrections` | `sender_address`, `sender_domain`, `subject` | Copied from `communications` at correction time | One-time at correction creation |
| `conversation_corrections` | `participant_addresses`, `subject`, `communication_count` | Copied from conversation at correction time | One-time at correction creation |

### 9.2 Consistency Maintenance

Denormalized fields are updated within the same transaction as the operation that changes the source data. When a communication is added to a conversation:

```
BEGIN TRANSACTION
  1. INSERT INTO conversation_communications (...)
  2. UPDATE conversations SET
       communication_count = communication_count + 1,
       last_activity_at = MAX(last_activity_at, new_comm_timestamp),
       first_activity_at = COALESCE(MIN(first_activity_at, new_comm_timestamp), new_comm_timestamp),
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
| **Store synced communication** | INSERT communication + INSERT communication_participants + resolve contacts via contact_identifiers (create if needed) + INSERT/UPDATE conversation_communications + UPDATE conversation denormalized fields + UPSERT conversation_participants | Read Committed |
| **Assign communication to conversation** | INSERT conversation_communications + UPDATE conversation counts/timestamps + UPSERT conversation_participants | Read Committed |
| **Reassign communication (correction)** | DELETE old conversation_communications + INSERT new conversation_communications + UPDATE both conversations' counts/timestamps + INSERT assignment_corrections | Read Committed |
| **Remove communication from conversation** | DELETE conversation_communications + UPDATE conversation counts/timestamps + recompute conversation_participants | Read Committed |
| **Edit communication (new revision)** | INSERT new communication + UPDATE old communication (next_revision, is_current=0) + UPDATE conversation_communications (point to new revision) | Read Committed |
| **AI processing** | UPDATE conversations (ai_summary, ai_status, etc.) + UPSERT tags + INSERT conversation_tags | Read Committed |
| **Triage correction** | UPDATE communications.triage_result + INSERT triage_corrections + optionally INSERT triage_rules | Read Committed |
| **Dismiss conversation** | UPDATE conversations (dismissed, dismissed_reason, etc.) + INSERT conversation_corrections | Read Committed |
| **Contact merge** | UPDATE contact_identifiers + UPDATE communication_participants + UPDATE conversation_participants + DELETE duplicate contact | Read Committed |
| **Create project/topic** | Single row INSERT per entity | Read Committed |
| **Delete project** | CASCADE handles child cleanup in single transaction | Read Committed |

### 10.2 Idempotency Patterns

| Table | Unique Constraint | Write Pattern | Duplicate Behavior |
|---|---|---|---|
| `users` | `email` | Check-then-insert | Returns existing ID |
| `provider_accounts` | `(provider, email_address)` | Check-then-insert | Returns existing ID |
| `communications` | `(account_id, provider_message_id)` | `INSERT OR IGNORE` | Silently skipped |
| `communication_participants` | `(communication_id, address, role)` | `INSERT OR IGNORE` | Silently skipped |
| `conversation_communications` | `(conversation_id, communication_id)` | `INSERT OR IGNORE` | Silently skipped |
| `contacts` | None (UUID PK) | Application-level dedup via `contact_identifiers` | N/A |
| `contact_identifiers` | `(type, value)` | `INSERT OR IGNORE` | Existing identifier reused |
| `conversation_participants` | `(conversation_id, address)` | `INSERT ... ON CONFLICT DO UPDATE` | Counts/dates refreshed |
| `tags` | `name` | `INSERT ... ON CONFLICT DO NOTHING` | Existing tag reused |
| `conversation_tags` | `(conversation_id, tag_id)` | `INSERT OR IGNORE` | Silently skipped |

### 10.3 Concurrency Considerations

**SQLite (PoC):** WAL mode enables concurrent reads during writes. The PoC is single-threaded so write contention is not an issue. `PRAGMA journal_mode=WAL` and `PRAGMA foreign_keys=ON` are set on every connection.

**PostgreSQL (production):** Read Committed isolation is sufficient for all operations. No long-running transactions. Contact merge operations acquire row-level locks on the affected contact and identifier rows. Connection pooling (PgBouncer or application-level) prevents connection exhaustion.

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

**Why not raw SQL forever:** The PoC's raw SQL approach is fine for 8 tables and single-dialect. At 21 tables targeting two dialects, SQLAlchemy Core's `Table` definitions and cross-dialect compilation prevent SQL string divergence.

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
| Contact index | `contacts:{tenant}` | 300s | Invalidate on contact sync or merge |
| Contact resolution | `ci:{type}:{value}` | 600s | Invalidate on identifier add/merge |
| View results | `view:{view_id}:{params_hash}` | 30s | Invalidate on underlying data change |
| Triage rules | `triage:rules:{user}` | 300s | Invalidate on rule CRUD |

**Tier 2: Client-Side Cache (SQLite on Device)**

Per the parent PRD, Flutter clients maintain a local SQLite cache for offline read access. The conversation data model mirrors the server schema (subset of tables: `conversations`, `communications`, `conversation_communications`, `contacts`, `contact_identifiers`). Sync via API pagination with `updated_at` cursors.

**Cache Invalidation Strategy:**

- **Write-through:** On write, update PostgreSQL and invalidate relevant Redis keys in the same operation.
- **Event-driven:** For cross-user invalidation (shared views, team alerts, contact merges), use Redis Pub/Sub to notify connected clients.
- **TTL fallback:** All cached entries have a TTL. Even without explicit invalidation, stale data expires.

---

## 13. Migration Plan

### 13.1 Phase 1: Current PoC → New PoC Schema (SQLite to SQLite)

This is the immediate migration: evolving the current 8-table schema to the new 21-table schema within SQLite.

**Strategy:** Incremental migration with data preservation. The existing `emails` and `conversations` tables contain real data from synced Gmail accounts.

**Steps:**

1. **Create new tables** that don't exist yet: `users`, `projects`, `topics`, `contact_identifiers`, `conversation_communications`, `communication_participants`, `attachments`, `tags`, `conversation_tags`, `views`, `alerts`, `assignment_corrections`, `triage_corrections`, `triage_rules`, `conversation_corrections`.

2. **Rename and extend existing tables:**
   - `email_accounts` → `provider_accounts` (add `account_type`, `phone_number` columns)
   - `emails` → `communications` (add `channel`, `timestamp`, channel-specific columns, `provider_metadata`, `user_metadata`, `previous_revision`, `next_revision`, `is_current`; rename `body_text` → `content`, `date` → `timestamp`)
   - `email_recipients` → `communication_participants` (add `contact_id`, extend `role` values)
   - `contacts` → restructure (remove `email`, `source_id`; add `company`, `status`)

3. **Migrate contact data:**
   - For each row in old `contacts` table, create a corresponding `contact_identifiers` row with `type='email'`, `value=<old email>`, `status='active'`, `verified=1`.

4. **Transform communication data:**
   - Populate `conversation_communications` from existing `communications.conversation_id` (set `display_content = NULL`, `is_primary = 1`, `assignment_source = 'sync'`, `confidence = 1.0`, `reviewed = 1`).
   - Recompute `conversations` denormalized fields from new join table.
   - Set `channel = 'email'` and `is_current = 1` on all existing communications.
   - Copy `conversations.provider_thread_id` to `communications.provider_thread_id`.
   - Add `dismissed = 0` to all conversations.
   - Drop `conversation_id` from `communications` table.
   - Drop `account_id` and `provider_thread_id` from `conversations` table.

5. **Update indexes** to match new schema.

6. **Update application code** (models.py, sync.py, database.py, etc.) to use new table/column names and contact resolution via `contact_identifiers`.

**Rollback:** Backup the SQLite file before migration. Restore on failure.

**Data validation:** Post-migration, verify:
- `COUNT(*)` on `conversation_communications` matches previous non-NULL `conversation_id` count on emails.
- `conversations.communication_count` matches `COUNT(*) FROM conversation_communications`.
- All `communications` have `channel = 'email'` and `is_current = 1`.
- Every old `contacts.email` has a corresponding `contact_identifiers` row.
- No orphaned records.

### 13.2 Phase 2: SQLite → PostgreSQL (Production Deployment)

**Strategy:** Schema translation + data migration. The logical schema is the same; only DDL syntax differs.

**Key differences to handle:**

| Feature | SQLite | PostgreSQL |
|---|---|---|
| UUID generation | Application-side (`uuid.uuid4()`) | Application-side or `gen_random_uuid()` |
| JSON columns | `TEXT` with `json_extract()` | `JSONB` with `->`, `->>`, `@>` operators |
| Boolean | `INTEGER` (0/1) | `BOOLEAN` (or keep INTEGER for compatibility) |
| Date/time | `TEXT` (ISO 8601 strings) | `TIMESTAMPTZ` (native; or keep TEXT for compatibility) |
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
CREATE TABLE communications (
    ...
) PARTITION BY RANGE (timestamp);

CREATE TABLE communications_2026_q1 PARTITION OF communications
    FOR VALUES FROM ('2026-01-01') TO ('2026-04-01');
```

Partitioning is deferred until data volumes justify it (>10M rows in `communications`).

### 14.4 Archive Strategy

Communications older than a configurable retention period can be moved to cold storage:

1. Archive to a separate `communications_archive` table (same schema, minimally indexed).
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
```

**Benefits:** Strong data isolation, tenant-specific indexes and statistics, cross-tenant queries impossible without explicit schema reference, backup/restore per tenant.

**Application enforcement:** Every database connection sets `search_path` to the authenticated tenant's schema before executing queries.

### 15.2 Row-Level Security (Future)

Deferred to the Permissions & Sharing PRD. Within a tenant, row-level security can restrict which users see which conversations based on participant-contact associations.

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
| **Denormalization drift** | Scheduled repair query vs. actual values | Any mismatch |
| **Incomplete contacts** | `SELECT COUNT(*) FROM contacts WHERE status = 'incomplete'` | Sustained growth (CIS not processing) |
| **Unreviewed assignments** | `SELECT COUNT(*) FROM conversation_communications WHERE reviewed = 0` | >100 sustained (user not reviewing) |
| **Correction rate** | Corrections per day / total assignments per day | >20% sustained (AI needs retraining) |

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

**Trade-off:** The polymorphic table has wider rows with NULLs. Extension tables would eliminate NULLs and enforce per-channel structure. We chose polymorphism because: (1) query simplicity — no JOINs for timeline display; (2) the channel set is finite and stable after initial development; (3) the NULL overhead is negligible at expected data volumes; (4) SQLite handles wide tables without performance issues.

### 17.2 M:N Conversations ↔ Communications vs. Segments Table

**Chose:** `conversation_communications` join table with `display_content`.

**Alternative:** Direct FK (`conversation_id` on communications) + separate `segments` table for cross-conversation references.

**Trade-off:** The FK + segments approach is simpler for the common case (one communication, one conversation) but requires a second entity and query path for multi-conversation communications. The M:N join table handles both cases uniformly and scales to any number of conversation associations per communication.

### 17.3 Denormalized Counts vs. Computed Aggregates

**Chose:** Denormalized `communication_count`, `participant_count`, `first_activity_at`, `last_activity_at` on conversations.

**Alternative:** Compute via JOIN + aggregate at query time.

**Trade-off:** Denormalization adds maintenance complexity (update in same transaction, repair mechanism needed). We chose it because display speed is the system's primary performance requirement and the listing query is the most frequent query.

### 17.4 Adjacency List vs. Materialized Path for Projects

**Chose:** Adjacency list (self-referential `parent_id`).

**Alternative:** Materialized path (`path` column storing `/root/child/grandchild`).

**Trade-off:** Materialized path makes "get all descendants" a simple `LIKE` query, but reparenting requires updating all descendant paths. Adjacency list makes reparenting a single-row update. We chose adjacency because project trees are shallow (2-3 levels) and `WITH RECURSIVE` is efficient for small trees.

### 17.5 Conventional Tables vs. Event Sourcing

**Chose:** Conventional mutable tables for the conversations subsystem.

**Alternative:** Event sourcing (append-only event store with materialized views).

**Trade-off:** Event sourcing provides a full audit trail and point-in-time reconstruction. We chose conventional tables because the conversations subsystem is read-heavy and update-moderate, and the parent PRD reserves event sourcing for contacts and intelligence entities where history is critical.

### 17.6 SQLAlchemy Core vs. Full ORM vs. Raw SQL

**Chose:** Raw SQL for PoC, SQLAlchemy Core for production.

**Alternative:** Full SQLAlchemy ORM (declarative models, relationship loading, session management).

**Trade-off:** The full ORM adds complexity, obscures SQL, and risks N+1 queries. SQLAlchemy Core provides type-safe query construction and dialect abstraction without the magic.

### 17.7 Multi-Identifier Contacts vs. Single-Email Contacts

**Chose:** `contact_identifiers` table with type/value pairs, no email column on contacts.

**Alternative:** Single `email` column on contacts (current PoC model).

**Trade-off:** The multi-identifier model adds a table and changes contact lookups from a simple `WHERE email = ?` to a join through `contact_identifiers`. We chose it because: (1) the same person can be encountered via email, phone, Slack, or other channels; (2) a single-email model creates duplicate contacts when the same person is encountered via different identifiers; (3) the merge problem (two contacts discovered to be the same person) is far more painful with single-identifier contacts; (4) the Contact Intelligence system requires multi-identifier support.

### 17.8 Immediate Contact Creation vs. Signal-Only

**Chose:** Create a contact immediately from unknown identifiers with `status='incomplete'`.

**Alternative:** Don't create a contact; just signal the Contact Intelligence system to resolve the identifier.

**Trade-off:** Immediate creation means contacts may exist with minimal information. But: (1) subsequent communications from the same identifier resolve instantly via `contact_identifiers` lookup; (2) without a contact record, every communication from the same unknown address generates a redundant signal; (3) `communication_participants.contact_id` can be populated immediately, avoiding backfill; (4) the `status='incomplete'` flag clearly indicates contacts needing enrichment.

### 17.9 Communication Version Control: Linked-List vs. Versions Table

**Chose:** `previous_revision` / `next_revision` on the communications table (linked-list chain).

**Alternative:** Separate `communication_versions` table.

**Trade-off:** A separate versions table keeps the communications table cleaner but requires a JOIN on every read to check for the latest version. The linked-list approach adds two nullable FK columns but keeps all versions in the same table, and `is_current = 1` provides a simple filter for the common case. The `conversation_communications` join table always points to the current revision, so most queries never touch the revision chain.

### 17.10 Triage: Per-Communication vs. Per-Conversation

**Chose:** Per-communication triage with rollup to conversation.

**Alternative:** Per-conversation triage only (current PoC model).

**Trade-off:** Per-communication triage is more granular — a conversation can contain a mix of legitimate and junk communications. Per-conversation triage is simpler but loses granularity. We chose per-communication because: (1) it enables more precise user corrections; (2) the conversation `triage_result` becomes a rollup (NULL if any communication is legitimate, non-NULL only when all are junk); (3) it aligns with the correction and learning model.

---

## 18. SQLite / PostgreSQL Compatibility

The schema is designed to work in both SQLite (PoC) and PostgreSQL (production) with minimal divergence.

### 18.1 Compatible Features Used

| Feature | SQLite | PostgreSQL | Notes |
|---|---|---|---|
| `CREATE TABLE IF NOT EXISTS` | Yes | Yes | Idempotent schema creation |
| `TEXT` type | Yes | Yes | Used for UUIDs, timestamps, strings, JSON |
| `INTEGER` type | Yes | Yes | Used for counts, booleans |
| `REAL` type | Yes | Yes | Used for confidence scores |
| `PRIMARY KEY` | Yes | Yes | |
| `FOREIGN KEY ... ON DELETE CASCADE/SET NULL` | Yes (with PRAGMA) | Yes (default) | |
| `UNIQUE` constraint | Yes | Yes | |
| `CHECK` constraint | Yes | Yes | |
| `INSERT OR IGNORE` | Yes | Mapped to `ON CONFLICT DO NOTHING` | |
| `INSERT ... ON CONFLICT DO UPDATE` | Yes | Yes | UPSERT syntax is compatible |
| `WITH RECURSIVE` | Yes (3.8.3+) | Yes | Tree traversal, revision history |
| `CREATE INDEX IF NOT EXISTS` | Yes | Yes | |
| `json_extract()` | Yes (built-in) | Via `->>`/`->>` operators | Query syntax differs |
| `WAL mode` | Yes (`PRAGMA journal_mode=WAL`) | N/A (MVCC handles this) | |
| Self-referential FKs | Yes | Yes | Projects, communication revisions |

### 18.2 PostgreSQL-Only Optimizations (Deferred)

| Feature | Benefit | Application |
|---|---|---|
| `TIMESTAMPTZ` | Native timestamp handling | Replace TEXT date columns |
| `JSONB` + GIN index | Indexed JSON queries | `views.query_def`, `provider_metadata`, `user_metadata` |
| Partial indexes | Smaller, faster indexes for common filters | `WHERE triage_result IS NULL AND dismissed = 0`, `WHERE is_current = 1`, `WHERE status = 'incomplete'` |
| Materialized views | Pre-computed aggregates | Dashboard statistics, tag frequency, correction rate |
| `BOOLEAN` type | Semantic clarity | Replace INTEGER 0/1 columns |
| Table partitioning | Large table performance | `communications` by timestamp |
| Row-level security | Per-user data access control | Permissions enforcement |
| `pg_trgm` + GIN | Fuzzy text search | Contact name search, conversation title search |
| Deferred FK constraints | Allow circular inserts | Communication revision chain creation |

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
| **Assignment source** | How a communication was assigned to a conversation: `sync` (email threading), `ai` (AI classification), `user` (manual). Tracked on `conversation_communications`. |
| **Communication** | The atomic unit of the system. A single email, SMS, phone call, video meeting, in-person meeting, or user-entered note. |
| **Contact identifier** | A typed value (email, phone, Slack handle, etc.) that maps to a contact record. Stored in `contact_identifiers`. A contact can have many identifiers. |
| **Conversation** | A logical grouping of related communications between specific participants about a specific subject. Can span channels. Account-independent. |
| **Correction** | A user action that overrides an automatic system decision (assignment, triage, or conversation management). Stored in dedicated correction tables as AI training signals. |
| **Denormalization** | Storing computed/derived data redundantly to avoid JOINs and aggregations on read. Trades write complexity for read speed. |
| **Dismissed** | A conversation state set by the user indicating the grouping is not useful, even if individual communications are legitimate. Orthogonal to triage. |
| **Display content** | The portion of a communication's text shown in a specific conversation's context. Stored on the `conversation_communications` join table. |
| **Idempotent** | An operation that produces the same result regardless of how many times it is executed. All sync operations in this system are idempotent. |
| **Incomplete contact** | A contact auto-created from an unknown identifier, with `status='incomplete'`. Awaiting enrichment by the Contact Intelligence system. |
| **Polymorphic table** | A single table that stores multiple entity types distinguished by a discriminator column (`channel`). |
| **Project** | Top-level organizational container. Supports recursive sub-projects via adjacency list. |
| **Provider account** | A connected data source (Gmail account, Outlook account, SMS provider, etc.) with sync state. |
| **Provider metadata** | JSON column on communications containing provider-specific data (Gmail labels, Outlook categories). Written by sync pipeline only. |
| **Revision chain** | Linked-list of communication versions via `previous_revision` / `next_revision` FK columns. Only the latest revision (`is_current = 1`) is displayed. |
| **Segment** | *Deprecated concept.* Replaced by the M:N `conversation_communications` join table with `display_content`. |
| **Sync cursor** | Opaque marker tracking the system's position in a provider's data stream. Provider-specific format. |
| **Tag** | AI-extracted keyword phrase applied to conversations. Distinct from organizational topics. |
| **Tenant** | An organizational unit (company/team) with its own isolated schema in PostgreSQL. |
| **Topic** | Organizational grouping within a project. Groups conversations about the same subject area with different participants. |
| **Triage rule** | An allow/block rule for triage evaluation, either user-created or learned from corrections. |
| **UPSERT** | INSERT-or-UPDATE operation using `ON CONFLICT` clause. Ensures idempotent writes. |
| **User metadata** | JSON column on communications containing user-defined tags, labels, and custom attributes. Written by user only. |
| **View** | User-defined saved query against the data model. Foundation for both dashboards and alerts. |

---

*This document is a living specification. It will be updated as implementation progresses, as the Conversations PRD evolves, and as production deployment reveals optimization opportunities. Schema changes after initial deployment will be managed via Alembic migrations with upgrade and downgrade paths.*
