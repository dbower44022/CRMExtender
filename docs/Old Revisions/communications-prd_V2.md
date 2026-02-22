# Product Requirements Document: Communications

## CRMExtender — Multi-Channel Communication Entity, Provider Framework & Unified Processing Pipeline

**Version:** 2.0
**Date:** 2026-02-19
**Status:** Draft — Fully reconciled with Custom Objects PRD
**Parent Document:** [CRMExtender PRD v1.1](PRD.md)

> **V2.0 (2026-02-19):**
> Added the **Published Summary** system. Key additions:
> - New **Published Summary** section (Section 7) defining the content pipeline, per-channel generation rules, rich text storage contract (mirrors Notes content architecture), and full revision control.
> - Summary fields added to the Communication data model: `summary_json`, `summary_html`, `summary_text`, `summary_source`, `current_summary_revision_id`, `summary_revision_count`. All behavior-managed, not in the field registry.
> - New `communication_summary_revisions` table for append-only, full-snapshot revision history.
> - New registered behavior: **Summary generation**.
> - New event types: `summary_generated`, `summary_revised`.
> - The Published Summary is the Communication's contribution to the Conversation timeline. The Conversation references summaries rather than copying content.
>
> **V1.0 (2026-02-18):**
> This document is one of two sibling PRDs extracted from the monolithic Communication & Conversation Intelligence PRD v2.0 (2026-02-07). That document has been decomposed into:
> 
> - **This PRD (Communications)** — The Communication entity as a system object type, the common schema all channels normalize to, the provider adapter framework, contact association, triage filtering, multi-account management, attachments, storage, and the general processing pipeline. This is the foundation that channel-specific child PRDs build on.
> - **[Conversations PRD](conversations-prd_V2.md)** — The Conversation, Topic, and Project entity types, the organizational hierarchy, AI intelligence layer (classify & route, summarize, extract intelligence), conversation lifecycle, cross-channel stitching, segmentation, and the review workflow.
> 
> All content has been reconciled with the [Custom Objects PRD](custom-objects-prd.md) Unified Object Model:
> 
> - Communication is a **system object type** (`is_system = true`, prefix `com_`) in the unified framework. Core fields are protected from deletion; specialized behaviors (channel-specific parsing, triage classification, content extraction) are registered per Custom Objects PRD Section 22.
> - Entity IDs use **prefixed ULIDs** (`com_` prefix, e.g., `com_01HX8A...`) per the platform-wide convention (Data Sources PRD, Custom Objects PRD Section 6).
> - Communication participants are modeled as a **system Relation Type**: Communication→Contact (`communication_participants`), with metadata fields for role (sender, to, cc, bcc) and address. This replaces flat `from_address`/`to_addresses` fields with a structured, queryable participant model.
> - Communication→Conversation assignment is a **FK column** (`conversation_id`) on the communications table, not a Relation Type, because it is strictly many:1 and carries no metadata.
> - `channel` is a **Select field with protected system options**, enabling future user-defined channel types alongside the system values.
> - The communication store uses a **per-entity-type event table** (`communications_events`) per Custom Objects PRD Section 19.
> - `communications` is the dedicated **read model table** within the tenant schema, managed through the object type framework.
> - All SQL uses **PostgreSQL** syntax with `TIMESTAMPTZ` timestamps, replacing any PoC-era SQLite schemas.
> - The PoC implementation details (file paths, test counts) are preserved in [Appendix A](#appendix-a-poc-implementation-reference) for historical reference.

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Problem Statement](#2-problem-statement)
3. [Goals & Success Metrics](#3-goals--success-metrics)
4. [Communication as System Object Type](#4-communication-as-system-object-type)
5. [Data Model](#5-data-model)
6. [Channel Types](#6-channel-types)
7. [Published Summary](#7-published-summary)
8. [Communication Entry Points](#8-communication-entry-points)
9. [Provider Account Framework](#9-provider-account-framework)
10. [Provider Adapter Architecture](#10-provider-adapter-architecture)
11. [Communication Participants & Contact Resolution](#11-communication-participants--contact-resolution)
12. [Triage & Intelligent Filtering](#12-triage--intelligent-filtering)
13. [Attachments](#13-attachments)
14. [Multi-Account Management](#14-multi-account-management)
15. [Event Sourcing & Temporal History](#15-event-sourcing--temporal-history)
16. [Virtual Schema & Data Sources](#16-virtual-schema--data-sources)
17. [Search & Discovery](#17-search--discovery)
18. [Storage & Data Retention](#18-storage--data-retention)
19. [Privacy, Security & Compliance](#19-privacy-security--compliance)
20. [API Design](#20-api-design)
21. [Design Decisions](#21-design-decisions)
22. [Phasing & Roadmap](#22-phasing--roadmap)
23. [Dependencies & Related PRDs](#23-dependencies--related-prds)
24. [Open Questions](#24-open-questions)
25. [Future Work](#25-future-work)
26. [Glossary](#26-glossary)
27. [Appendix A: PoC Implementation Reference](#appendix-a-poc-implementation-reference)

---

## 1. Executive Summary

The Communications subsystem defines the **atomic unit of interaction** in CRMExtender. A Communication is a single email, SMS message, phone call, video meeting, in-person meeting, or user-entered note — any discrete interaction between identified participants that the CRM captures. Every other intelligence layer in the platform — conversation grouping, AI summarization, relationship scoring, engagement analytics — consumes Communications as its raw input.

This PRD defines the Communication entity, the common schema that all channels normalize to, the provider adapter framework that captures communications from external sources, the shared processing pipeline (triage, contact resolution, content extraction) that prepares communications for downstream intelligence, and the **Published Summary** system that defines how each Communication contributes to its parent Conversation's timeline.

**Core principles:**

- **System object type** — Communication is a system object type (`is_system = true`, prefix `com_`) in the Custom Objects unified framework. Core fields are registered in the field registry. Specialized behaviors (channel-specific parsing, triage classification, summary generation) are registered per Custom Objects PRD Section 22. Users can extend Communications with custom fields through the standard field registry.
- **Channel-agnostic common schema** — All communication types (email, SMS, phone, video, in-person, note) normalize to the same entity structure: timestamp, channel, direction, participants, content, attachments, and source metadata. Downstream systems never need to know or care which channel a communication arrived from.
- **Published Summary** — Every Communication produces a rich text summary that is published to its parent Conversation's timeline. The Communication owns the summary; the Conversation references it. AI generates summaries for synced content (emails, transcripts). Users author summaries for manual entries (phone notes, in-person meetings). Short messages (SMS) pass through as-is. Full revision history enables audit trail reconstruction.
- **Provider adapter pattern** — External communication sources (Gmail, Outlook, Twilio, OpenPhone, etc.) are integrated through a uniform adapter interface: authenticate, fetch, normalize, track sync position. Each adapter is a self-contained module; the rest of the platform is provider-agnostic. Channel-specific adapter details are documented in child PRDs.
- **Contact-centric** — Every communication participant must be resolved to a CRM contact via the Contact Intelligence system. Unknown identifiers trigger identity resolution workflows. Pending identification does not block communication processing.
- **Triage before intelligence** — Not every communication warrants AI analysis. A configurable triage pipeline filters automated notifications, marketing emails, and messages from unknown sources before they consume AI resources. Filtered communications are retained with their filter reason visible — nothing is silently discarded.
- **Event-sourced history** — All communication mutations are stored as immutable events in `communications_events`, enabling full audit trails, point-in-time reconstruction, and compliance support.

**Current state:** A functional Gmail-only proof of concept exists with 95+ tests covering the email parsing pipeline, multi-account sync, SQLite persistence, triage filtering, and Claude-powered summarization. See [Appendix A](#appendix-a-poc-implementation-reference) for details.

**Relationship to other PRDs:**

- **[Custom Objects PRD](custom-objects-prd.md)** — The Communication entity type is a **system object type** in the unified framework. Its table structure, field registry, event sourcing, and relation model are governed by the Custom Objects PRD. This PRD defines the Communication-specific behaviors (parsing, triage, content extraction) that are registered with the object type framework.
- **[Conversations PRD](conversations-prd_V2.md)** — Conversations group Communications into coherent threads. The Conversations PRD defines the organizational hierarchy (Projects → Topics → Conversations), AI intelligence layer, conversation lifecycle, and cross-channel stitching. Communications reference their parent Conversation via an FK column.
- **[Contact Management PRD](contact-management-prd_V4.md)** — Communication participants are resolved to Contact records via `contact_identifiers`. Email addresses, phone numbers, and platform handles are matched to unified contact records. Communication frequency feeds relationship strength scoring.
- **[Company Management PRD](company-management-prd.md)** — Email domain extraction during sync triggers company auto-creation. Communications link to companies indirectly through contact participants. Communication patterns feed company relationship scoring.
- **[Event Management PRD](events-prd_V2.md)** — Calendar events link to conversations (which contain communications) through the Event→Conversation Relation Type. Meeting follow-up emails and pre-meeting coordination threads are correlated with their triggering events.
- **[Notes PRD](notes-prd_V2.md)** — Notes are a distinct system object type for free-form knowledge capture. Manually logged phone calls and in-person meetings where the user is the content source create Communication records (channel = `phone_manual` or `in_person`), not Note records. Notes attach *to* entities (including Communications and Conversations) as supplementary commentary; Communications *are* the interaction records.
- **[Data Sources PRD](data-sources-prd.md)** — The Communication virtual schema table is derived from the Communication object type's field registry. The prefixed entity ID convention (`com_`) enables automatic entity detection in data source queries.
- **[Views & Grid PRD](views-grid-prd_V3.md)** — Communication views, filters, sorts, and inline editing operate on fields defined in the Communication field registry.
- **[Permissions & Sharing PRD](permissions-sharing-prd_V1.md)** — Communication record access, provider account management permissions, and integration data visibility follow the standard role-based access model.

**Channel-specific child PRDs:**

| Child PRD                                                    | Scope                                                                                                                                                                                                       |
| ------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **[Email Provider Sync PRD](email-provider-sync-prd_V1.md)** | Gmail, Outlook, and IMAP provider adapters; OAuth flows; email sync pipeline; email parsing & content extraction (dual-track pipeline); email-specific triage patterns; email threading models per provider |
| **SMS/MMS PRD** (future)                                     | SMS provider adapters (Twilio, OpenPhone); message sync; phone number resolution; MMS media handling                                                                                                        |
| **Voice/VoIP PRD** (future)                                  | Call recording integration; transcription pipeline; call metadata capture; provider adapters                                                                                                                |
| **Video Meetings PRD** (future)                              | Zoom/Teams/Meet integration; transcript capture; calendar event correlation; recording management                                                                                                           |

---

## 2. Problem Statement

Professional relationships play out across multiple channels — email, text messages, phone calls, video meetings, and in-person conversations. Yet existing CRM tools treat each channel as an isolated silo, and even within email, they log individual messages rather than understanding the interaction as a structured entity with participants, content, direction, and context.

**The consequences for CRM users:**

| Pain Point                       | Impact                                                                                                                                                                                                          |
| -------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Channel silos**                | An email thread about a deal, a follow-up SMS, and a phone call with the same contact appear as three unrelated entries. The full picture requires manual assembly.                                             |
| **Manual communication logging** | Sales reps spend 20–30 minutes daily copying email content into CRM records. Phone calls and meetings require manual note entry with no structure. Most users give up, leaving CRM data incomplete.             |
| **Noise overwhelms signal**      | Forwarded chains, legal disclaimers, and signature blocks bloat logged content. Finding the actual message requires manual editing.                                                                             |
| **No common schema**             | Each channel has its own data model, making cross-channel queries impossible. "Show me all interactions with Bob last month" requires assembling data from email logs, call logs, and meeting notes separately. |
| **Scattered across accounts**    | Professionals with multiple email accounts and phone numbers have no unified view of their communication landscape.                                                                                             |
| **Blind spots on engagement**    | Without systematic cross-channel capture, managers cannot see which relationships are active, stale, or at risk.                                                                                                |

### Why Existing Solutions Fall Short

- **Native CRM email integrations** (Salesforce, HubSpot) — Log individual emails, not structured communication records. No multi-channel common schema. No content cleaning. Require manual association with contacts/deals.
- **Email aggregation services** (Nylas, Mailgun) — Provide email API abstraction but no intelligence layer. Email only — no SMS, calls, or meetings. Per-mailbox pricing at scale.
- **Communication platforms** (Slack, Teams) — Excellent for real-time collaboration but siloed from CRM data. No cross-channel communication model.

CRMExtender closes this gap by defining a **channel-agnostic Communication entity** that every external source normalizes to, with a pluggable provider framework, systematic contact resolution, and configurable triage filtering.

---

## 3. Goals & Success Metrics

### Goals

1. **Channel-agnostic common schema** — All communication types normalize to a single entity structure with uniform fields for timestamp, participants, content, direction, and channel. Downstream systems consume Communications without channel-specific logic.
2. **Pluggable provider framework** — Adding a new communication source (a new email provider, SMS service, or VoIP integration) requires implementing an adapter module against a defined interface. The rest of the platform remains unchanged.
3. **Zero-noise content** — Channel-specific content extraction (email quote/signature removal, transcript cleanup) produces clean content before any human or AI sees it. Target: >95% accuracy for email.
4. **Contact resolution for all channels** — Every communication participant is resolved to a CRM contact, regardless of identifier type (email address, phone number, platform handle). Target: >95% automatic resolution rate.
5. **Configurable triage** — A multi-layer filtering pipeline separates real human interactions from automated notifications and marketing. Filtered communications are retained, not deleted. Target: >95% precision.
6. **Multi-account unified feed** — Multiple provider accounts (2 email accounts, 1 phone, etc.) produce a single chronological communication feed. Each record is tagged with its source account.
7. **Full audit trail** — Every communication mutation is event-sourced. Provider sync operations are logged with full audit data.

### Success Metrics

| Metric                               | Target                                                            | Measurement                                           |
| ------------------------------------ | ----------------------------------------------------------------- | ----------------------------------------------------- |
| Cross-channel schema coverage        | 100% of supported channels normalize to common schema             | All channel types produce valid Communication records |
| Content cleaning accuracy (email)    | >95% of quotes/signatures/boilerplate removed                     | Human evaluation of 200 sampled cleaned emails        |
| False-positive cleaning rate         | <1% of original authored content incorrectly removed              | Human evaluation of same 200 samples                  |
| Contact resolution rate              | >95% of participants identified automatically                     | DB query: communications with unresolved contacts     |
| Triage precision                     | >95% of filtered communications are genuinely automated/marketing | Human review of 200 triaged items                     |
| Sync latency (email — Gmail/Outlook) | <60 seconds from delivery to CRM availability                     | Instrumented end-to-end measurement                   |
| Sync coverage                        | 100% of inbox emails captured                                     | Audit: compare message counts between provider and DB |
| Provider adapter isolation           | Adding a new provider requires zero changes to core pipeline      | Code review: no core changes for new adapter          |

---

## 4. Communication as System Object Type

### 4.1 Object Type Registration

Communication is registered as a system object type in the Custom Objects framework:

| Attribute               | Value                                                                                                                                                             |
| ----------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `name`                  | Communication                                                                                                                                                     |
| `slug`                  | `communications`                                                                                                                                                  |
| `type_prefix`           | `com_`                                                                                                                                                            |
| `is_system`             | `true`                                                                                                                                                            |
| `display_name_field_id` | → `subject` field (falls back to `body_preview` if subject is NULL)                                                                                               |
| `description`           | An individual interaction — a single email, SMS, phone call, video meeting, in-person meeting, or user-entered note. The atomic unit of the communication system. |

### 4.2 Registered Behaviors

| Behavior                            | Trigger              | Description                                                                                                                                                                                                            |
| ----------------------------------- | -------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Channel-specific content extraction | On sync, on creation | Dispatches to the appropriate channel parser (email dual-track pipeline, transcript cleanup, etc.) to produce `content_clean` from raw content. Defined in channel-specific child PRDs.                                |
| Summary generation                  | On creation, on content update, on manual edit | Dispatches to the channel-specific summary generator to produce the Published Summary (`summary_json`, `summary_html`, `summary_text`) from `content_clean`. Creates a new summary revision. See Section 7. |
| Triage classification               | On sync, on creation | Runs the multi-layer triage pipeline (Section 12) to classify communications as real interactions vs. automated/marketing noise.                                                                                       |
| Participant resolution              | On sync, on creation | Extracts participant identifiers from the communication and triggers the Contact Intelligence system for resolution.                                                                                                   |
| Segmentation                        | On user action       | When a user selects a portion of content and assigns it to a different conversation, creates a Segment record linked to both the original communication and the target conversation. Defined in the Conversations PRD. |

### 4.3 Protected Core Fields

The following fields are `is_system = true` and cannot be archived, deleted, or have their type converted. Users can add custom fields to Communications through the standard field registry.

---

## 5. Data Model

### 5.1 Communication Field Registry

**Universal fields** (present on all object types per Custom Objects PRD Section 7):

| Field       | Column        | Type                  | Description                                        |
| ----------- | ------------- | --------------------- | -------------------------------------------------- |
| ID          | `id`          | TEXT, PK              | Prefixed ULID: `com_01HX8A...`                     |
| Tenant      | `tenant_id`   | TEXT, NOT NULL        | Tenant isolation                                   |
| Created At  | `created_at`  | TIMESTAMPTZ, NOT NULL | Record creation timestamp                          |
| Updated At  | `updated_at`  | TIMESTAMPTZ, NOT NULL | Last modification timestamp                        |
| Created By  | `created_by`  | TEXT, FK → users      | User who created the record (NULL for auto-synced) |
| Updated By  | `updated_by`  | TEXT, FK → users      | User who last modified the record                  |
| Archived At | `archived_at` | TIMESTAMPTZ, NULL     | Soft-delete timestamp                              |

**Core system fields** (`is_system = true`, protected):

| Field               | Column                | Type                           | Required | Description                                                                                                                                                                                             |
| ------------------- | --------------------- | ------------------------------ | -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Channel             | `channel`             | Select                         | YES      | Communication medium. Protected system options: `email`, `sms`, `mms`, `phone_recorded`, `phone_manual`, `video_recorded`, `video_manual`, `in_person`, `note`. Users may add custom options in future. |
| Direction           | `direction`           | Select                         | YES      | `inbound`, `outbound`, `mutual` (calls/meetings).                                                                                                                                                       |
| Timestamp           | `timestamp`           | TIMESTAMPTZ                    | YES      | When the communication occurred. This is the **sequencing key** for all timeline views. For synced communications, this is the provider's send/receive time. For manual entries, user-specified.        |
| Subject             | `subject`             | Text (single-line)             | NO       | Email subject line, meeting title, or user-provided subject. NULL for SMS, most calls. Display name field.                                                                                              |
| Body Preview        | `body_preview`        | Text (single-line)             | NO       | First 200 characters of cleaned content. Used in list views and search results. Auto-generated from `content_clean`.                                                                                    |
| Content Raw         | `content_raw`         | Text (multi-line)              | NO       | Original content as received from the provider or entered by the user. For email: plain-text body. For transcripts: raw transcript text. Not displayed to users directly.                               |
| Content HTML        | `content_html`        | Text (multi-line)              | NO       | Original HTML content (email only). Used by the content extraction pipeline. Not displayed to users directly.                                                                                           |
| Content Clean       | `content_clean`       | Text (multi-line)              | NO       | Processed content with channel-specific noise removed (quoted replies, signatures, boilerplate for email; filler words for transcripts). This is what users see and what AI processes.                  |
| Source              | `source`              | Select                         | YES      | How the communication entered the system: `synced` (auto-captured from provider), `manual` (user-entered), `imported` (bulk import).                                                                    |
| Provider Account ID | `provider_account_id` | Relation (→ provider_accounts) | NO       | The provider account that captured this communication. NULL for manual entries.                                                                                                                         |
| Provider Message ID | `provider_message_id` | Text (single-line)             | NO       | The provider's unique identifier for this message (Gmail message ID, Outlook message ID, etc.). Used for deduplication. UNIQUE constraint per provider account.                                         |
| Provider Thread ID  | `provider_thread_id`  | Text (single-line)             | NO       | The provider's thread/conversation identifier (Gmail `threadId`, Outlook `conversationId`). Used by the Conversations PRD for automatic conversation formation.                                         |
| Conversation ID     | `conversation_id`     | Relation (→ conversations)     | NO       | FK to the parent conversation. NULL for unassigned communications.                                                                                                                                      |
| Triage Result       | `triage_result`       | Select                         | NO       | NULL = passed triage (real interaction). Non-NULL = filtered. Options: `automated_sender`, `automated_subject`, `marketing_content`, `no_known_contacts`, `user_filtered`.                              |
| Triage Reason       | `triage_reason`       | Text (single-line)             | NO       | Human-readable explanation of the triage decision. E.g., "Sender matches pattern: noreply@".                                                                                                            |
| Duration Seconds    | `duration_seconds`    | Number (integer)               | NO       | Duration for calls and meetings. NULL for text-based communications.                                                                                                                                    |
| Has Attachments     | `has_attachments`     | Checkbox                       | NO       | Whether this communication has file attachments. Denormalized for fast filtering.                                                                                                                       |
| Attachment Count    | `attachment_count`    | Number (integer)               | NO       | Count of attached files. Denormalized for display.                                                                                                                                                      |

**Behavior-managed summary fields** (stored as columns on the `communications` table but **not registered in the field registry**, same pattern as Notes content fields per Notes PRD Section 7.1):

| Column                        | Type        | Description                                                                                                                                                                     |
| ----------------------------- | ----------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `summary_json`                | JSONB       | Editor-native rich text document format. Source of truth for re-editing. Same JSON schema as Notes `content_json`. NULL until summary is generated.                             |
| `summary_html`                | TEXT        | Pre-rendered HTML. What the Conversation timeline renders when displaying this Communication's contribution. Generated from `summary_json` on save.                            |
| `summary_text`                | TEXT        | Plain text extracted from `summary_html`. Used for FTS indexing and as input to the Conversation-level AI summary. Generated from `summary_html` on save.                      |
| `summary_source`              | TEXT        | How the summary was created: `ai_generated`, `user_authored`, `pass_through` (body used as-is). Drives UI display (e.g., "AI Summary" badge vs. no badge).                    |
| `current_summary_revision_id` | TEXT        | FK to `communication_summary_revisions`. Points to the active revision. NULL until first summary is created.                                                                   |
| `summary_revision_count`      | INTEGER     | Count of summary revisions. Starts at 1 on first summary creation. Incremented on each revision.                                                                               |

These fields are managed by the Summary generation behavior (Section 7). They are not queryable through standard Data Source filters. Summary content is discoverable through the dedicated FTS search endpoint. See Section 7 for the full Published Summary specification.

### 5.2 Read Model Table

```sql
-- Within tenant schema: tenant_abc.communications
CREATE TABLE communications (
    -- Universal fields
    id              TEXT PRIMARY KEY,        -- com_01HX8A...
    tenant_id       TEXT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by      TEXT REFERENCES platform.users(id),
    updated_by      TEXT REFERENCES platform.users(id),
    archived_at     TIMESTAMPTZ,

    -- Core system fields
    channel         TEXT NOT NULL,           -- Select: email, sms, phone_recorded, etc.
    direction       TEXT NOT NULL,           -- Select: inbound, outbound, mutual
    timestamp       TIMESTAMPTZ NOT NULL,    -- When the communication occurred
    subject         TEXT,                    -- Email subject, meeting title, etc.
    body_preview    TEXT,                    -- First 200 chars of content_clean
    content_raw     TEXT,                    -- Original content as received
    content_html    TEXT,                    -- Original HTML (email only)
    content_clean   TEXT,                    -- Processed content (noise removed)
    source          TEXT NOT NULL,           -- Select: synced, manual, imported
    provider_account_id TEXT,               -- FK → provider_accounts
    provider_message_id TEXT,               -- Provider's unique message ID
    provider_thread_id  TEXT,               -- Provider's thread/conversation ID
    conversation_id TEXT,                   -- FK → conversations
    triage_result   TEXT,                   -- NULL = passed, non-NULL = filtered
    triage_reason   TEXT,                   -- Human-readable triage explanation
    duration_seconds INTEGER,               -- Call/meeting duration
    has_attachments BOOLEAN DEFAULT FALSE,
    attachment_count INTEGER DEFAULT 0,

    -- Behavior-managed summary fields (see Section 7)
    summary_json    JSONB,                  -- Rich text source of truth
    summary_html    TEXT,                   -- Pre-rendered HTML for Conversation timeline
    summary_text    TEXT,                   -- Plain text for FTS and AI consumption
    summary_source  TEXT,                   -- 'ai_generated', 'user_authored', 'pass_through'
    current_summary_revision_id TEXT,       -- FK â†' communication_summary_revisions
    summary_revision_count INTEGER DEFAULT 0,

    -- Deduplication constraint
    CONSTRAINT uq_provider_message UNIQUE (provider_account_id, provider_message_id)
);

-- Indexes
CREATE INDEX idx_comm_timestamp ON communications (timestamp DESC);
CREATE INDEX idx_comm_conversation ON communications (conversation_id) WHERE conversation_id IS NOT NULL;
CREATE INDEX idx_comm_channel ON communications (channel);
CREATE INDEX idx_comm_triage ON communications (triage_result) WHERE triage_result IS NOT NULL;
CREATE INDEX idx_comm_provider_thread ON communications (provider_account_id, provider_thread_id)
    WHERE provider_thread_id IS NOT NULL;
CREATE INDEX idx_comm_archived ON communications (archived_at) WHERE archived_at IS NULL;

-- Summary FTS
CREATE INDEX idx_comm_summary_fts ON communications
    USING GIN (to_tsvector('english', COALESCE(summary_text, '')));
```

#### `communication_summary_revisions` â€" Append-only summary revision history

```sql
CREATE TABLE communication_summary_revisions (
    id                  TEXT PRIMARY KEY,          -- svr_ prefixed ULID
    communication_id    TEXT NOT NULL REFERENCES communications(id) ON DELETE CASCADE,
    revision_number     INTEGER NOT NULL,
    summary_json        JSONB NOT NULL,            -- Full rich text snapshot
    summary_html        TEXT NOT NULL,             -- Pre-rendered HTML snapshot
    summary_text        TEXT NOT NULL,             -- Plain text snapshot
    summary_source      TEXT NOT NULL,             -- 'ai_generated', 'user_authored', 'pass_through'
    revised_by          TEXT,                      -- FK â†' platform.users (NULL for AI-generated)
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (communication_id, revision_number)
);

CREATE INDEX idx_svr_communication ON communication_summary_revisions (communication_id, revision_number DESC);
```

### 5.3 Timestamp as the Universal Sequencing Key

All communications across all channels are sequenced by `timestamp`. This is what enables a unified timeline view:

```
Conversation: Lease Negotiation with Bob
  10:15 AM  [EMAIL]     Bob → Me: Contract draft attached
  10:32 AM  [EMAIL]     Me → Bob: Questions about clause 5
  12:45 PM  [SMS]       Me → Bob: "Hey, did you see my questions?"
   1:02 PM  [SMS]       Bob → Me: "Yes, checking with legal, will reply tonight"
   3:00 PM  [PHONE]     Call with Bob (12 min) — transcript available
   6:30 PM  [EMAIL]     Bob → Me: Revised clause 5 language
```

A single conversation, three channels, one coherent timeline. The Conversations PRD defines how these communications are grouped; this PRD defines the common record structure that makes grouping possible.

---

## 6. Channel Types

### 6.1 System Channel Options

The `channel` Select field has the following protected system options:

| Channel Value    | Display Name             | Source                      | Content Type           | Threading                  | Parsing Needed                          | Child PRD               |
| ---------------- | ------------------------ | --------------------------- | ---------------------- | -------------------------- | --------------------------------------- | ----------------------- |
| `email`          | Email                    | Auto-synced                 | Rich (text + HTML)     | Provider-native thread IDs | Heavy (quotes, signatures, boilerplate) | Email Provider Sync PRD |
| `sms`            | SMS                      | Auto-synced                 | Short text             | None (flat stream)         | Minimal                                 | SMS/MMS PRD             |
| `mms`            | MMS                      | Auto-synced                 | Text + media           | None (flat stream)         | Minimal                                 | SMS/MMS PRD             |
| `phone_recorded` | Phone Call (Recorded)    | Auto-synced + transcription | Transcript (long text) | None                       | Some (filler words, speaker labels)     | Voice/VoIP PRD          |
| `phone_manual`   | Phone Call (Logged)      | Manual entry                | User-written notes     | None                       | None                                    | —                       |
| `video_recorded` | Video Meeting (Recorded) | Auto-synced + transcription | Transcript (long text) | None                       | Some                                    | Video Meetings PRD      |
| `video_manual`   | Video Meeting (Logged)   | Manual entry                | User-written notes     | None                       | None                                    | —                       |
| `in_person`      | In-Person Meeting        | Manual entry                | User-written notes     | None                       | None                                    | —                       |
| `note`           | Note                     | Manual entry                | User-written notes     | None                       | None                                    | —                       |

### 6.2 Content Characteristics by Channel

| Channel          | Content Length               | Content Quality                   | Auto-captured?   | Summary Generation                                          |
| ---------------- | ---------------------------- | --------------------------------- | ---------------- | ----------------------------------------------------------- |
| `email`          | Medium-long (50–5,000 words) | High (structured, detailed)       | Yes              | AI from `content_clean`. Pass-through if <50 words.         |
| `sms` / `mms`    | Very short (1–50 words)      | Low (terse, context-dependent)    | Yes              | Pass-through (`content_clean` used as-is).                  |
| `phone_recorded` | Long (500–10,000 words)      | Medium (conversational, rambling) | Yes (transcript) | AI from transcript. Key points, decisions, action items.    |
| `phone_manual`   | Variable (user-written)      | High (user curates)               | No               | User-authored (user's note IS the summary).                 |
| `video_recorded` | Long                         | Medium (same as phone)            | Yes (transcript) | AI from transcript. Same approach as `phone_recorded`.      |
| `video_manual`   | Variable (user-written)      | High (user curates)               | No               | User-authored (user's note IS the summary).                 |
| `in_person`      | Variable (user-written)      | High (user curates)               | No               | User-authored (user's note IS the summary).                 |
| `note`           | Variable (user-written)      | High (user curates)               | No               | User-authored (user's note IS the summary).                 |

### 6.3 Boundary with the Notes PRD

**Communications** and **Notes** are distinct system object types that serve different purposes:

| Aspect             | Communication                                                         | Note                                                                  |
| ------------------ | --------------------------------------------------------------------- | --------------------------------------------------------------------- |
| **Purpose**        | Record of an interaction that happened                                | Free-form observation, commentary, or knowledge                       |
| **Participants**   | Has identified participants (sender, recipients)                      | Has a single author                                                   |
| **Temporal**       | Tied to a specific moment (the interaction timestamp)                 | Created at a point in time, but about ongoing knowledge               |
| **Content source** | External (synced from provider) or interaction record (what was said) | Internal (what the user thinks, observes, decides)                    |
| **Attachments**    | Interaction artifacts (email attachments, recordings)                 | Supporting documents, images                                          |
| **Example**        | "Phone call with Bob, 15 min — discussed clause 5 revisions"          | "Bob prefers email for formal communications. Don't text before 9am." |

**Manually logged interactions** (unrecorded phone calls, in-person meetings) create Communication records with channel = `phone_manual`, `video_manual`, or `in_person`. The user provides participants, timestamp, and a summary of what was discussed. This is an *interaction record* — it represents something that happened between people.

**Notes** attach *to* entities (including Communications and Conversations) as supplementary commentary. A user might attach a Note to a Communication that says "Bob seemed hesitant about the pricing — follow up with a discount offer." The Note is commentary about the interaction, not the interaction itself.

**Shared content architecture:** Communication Published Summaries (Section 7) and Notes share the same rich text content storage contract: `content_json` / `summary_json` (JSONB, editor-native), `content_html` / `summary_html` (pre-rendered HTML), `content_text` / `summary_text` (plain text for FTS). Both use the same Flutter rich text editor for user authoring and the same revision history model (append-only, full-snapshot, numbered revisions). This ensures a consistent editing experience across the platform.
---

## 7. Published Summary

### 7.1 Concept

Every Communication produces a **Published Summary** — the rich text representation of that Communication's contribution to its parent Conversation's timeline. The Published Summary is what users see when they view a Conversation: an ordered sequence of summary cards, each representing one Communication, each expandable to reveal the full original content.

The Communication **owns** its Published Summary. The Conversation is a presentation container that assembles a timeline by referencing its Communications' summaries — it does not copy, duplicate, or independently store Communication content. This separation of concerns means:

- Updating a Communication's summary automatically updates how it appears in every Conversation that contains it.
- The Conversation-level AI summary is a higher-order synthesis across its Communications' Published Summaries, not a re-analysis of raw content.
- Revision history on summaries provides an audit trail for what information was available when decisions were made.

### 7.2 Content Pipeline

The Published Summary sits at the end of a three-stage content pipeline:

```
Stage 1: content_raw
  Original content as received from the provider or entered by the user.
  Emails: full message with headers. Transcripts: raw transcript. Manual: user input.
  → Preserved for reference. Never displayed directly to users.

Stage 2: content_clean
  Channel-specific noise removal (defined in channel-specific child PRDs):
  - Email: quoted replies, signatures, boilerplate stripped (95+ test pipeline)
  - Transcripts: filler words, speaker label normalization
  - SMS: minimal processing (content is already concise)
  - Manual entries: no processing needed
  → What users see when they expand to view the full original. What AI uses as input.

Stage 3: Published Summary (summary_json / summary_html / summary_text)
  Distilled representation suitable for Conversation timeline display:
  - AI-generated: structured rich text (headings, bullet points, bold decisions)
  - User-authored: rich text written by the user (same editor as Notes)
  - Pass-through: content_clean used as-is when already concise enough
  → What appears in the Conversation timeline. What the Conversation-level AI consumes.
```

### 7.3 Summary Generation Rules by Channel

| Channel | Summary Source | Generation Logic |
|---|---|---|
| `email` (<50 words after cleaning) | `pass_through` | `content_clean` is already concise. Copy directly to summary fields as rich text. |
| `email` (≥50 words after cleaning) | `ai_generated` | AI processes `content_clean` to produce structured rich text: key points, decisions, requests, and action items. |
| `sms` / `mms` | `pass_through` | Message body is inherently short. Copy `content_clean` directly. |
| `phone_recorded` | `ai_generated` | AI processes transcript (`content_clean`) to produce structured rich text: key discussion points, decisions made, action items, and commitments. |
| `phone_manual` | `user_authored` | User writes the summary using the rich text editor during Communication creation. The user's input IS the summary. |
| `video_recorded` | `ai_generated` | Same approach as `phone_recorded`. |
| `video_manual` | `user_authored` | Same approach as `phone_manual`. |
| `in_person` | `user_authored` | Same approach as `phone_manual`. |
| `note` | `user_authored` | Same approach as `phone_manual`. |

### 7.4 Rich Text Storage Contract

The summary storage model mirrors the Notes content architecture (Notes PRD Section 7.2). Three representations of the same content are stored:

| Column | Type | Purpose |
|---|---|---|
| `summary_json` | JSONB | Editor-native document format. Source of truth for re-editing. Same JSON schema as Notes `content_json`. The backend treats this as an opaque JSONB blob. |
| `summary_html` | TEXT | Pre-rendered HTML. Generated by the editor (for user-authored) or by the AI pipeline (for AI-generated). What the Conversation timeline renders. Sanitized before storage (same sanitization as Notes Section 15). |
| `summary_text` | TEXT | Plain text extracted from `summary_html` (all tags stripped). Used for FTS indexing and as input to the Conversation-level AI summary. |

For **AI-generated** summaries, the AI pipeline produces structured HTML directly (headings, lists, bold emphasis for key decisions). This HTML is stored in `summary_html`, a corresponding `summary_json` representation is generated for the editor, and `summary_text` is extracted for FTS.

For **user-authored** summaries, the client sends `summary_json` and `summary_html` from the rich text editor. The server extracts `summary_text` from `summary_html`.

For **pass-through** summaries, `content_clean` is wrapped in minimal HTML tags and stored across all three fields.

### 7.5 AI Summary Structure

When the AI generates a summary, it produces structured rich text rather than flat prose. The output format varies by content but follows general patterns:

**Email summary example:**
```html
<p><strong>Key points:</strong></p>
<ul>
  <li>Proposed liability cap at $500K for clause 5</li>
  <li>Requested 30-day review period instead of 14</li>
</ul>
<p><strong>Action items:</strong></p>
<ul>
  <li>Bob to send revised clause 5 language by Friday</li>
  <li>Review indemnification section (clause 8) next</li>
</ul>
```

**Call/meeting summary example:**
```html
<h3>Key Discussion Points</h3>
<ul>
  <li>Agreed on $500K liability cap — Bob confirmed with legal</li>
  <li>Timeline: signing target moved to March 15</li>
</ul>
<h3>Decisions Made</h3>
<ul>
  <li>Proceed with Option B for the penalty structure</li>
</ul>
<h3>Action Items</h3>
<ul>
  <li><strong>Bob:</strong> Send revised contract by Feb 21</li>
  <li><strong>Me:</strong> Review and return comments within 48 hours</li>
</ul>
```

The specific AI prompt templates and output formats are defined in the AI Learning & Classification PRD (future). This section establishes the requirement: AI summaries are structured rich text, not flat paragraphs.

### 7.6 Revision History

Every summary change — whether AI-generated or user-edited — creates a new revision in `communication_summary_revisions`. The revision model mirrors Notes (Notes PRD Section 8):

- **Append-only**: Revisions are never updated or deleted individually. Removed only via CASCADE when the parent Communication is deleted.
- **Numbered**: `revision_number` starts at 1 and increments per Communication.
- **Unique**: `UNIQUE(communication_id, revision_number)` constraint.
- **Full snapshots**: Each revision stores the complete `summary_json`, `summary_html`, and `summary_text` at that point in time. No diffs.

#### Revision Lifecycle

| Action | Behavior |
|---|---|
| **Initial summary generation** | First revision created (revision_number = 1). Communication's `current_summary_revision_id`, `summary_revision_count`, and summary fields updated. `summary_source` set to `ai_generated`, `user_authored`, or `pass_through`. |
| **User edits AI summary** | New revision created (revision_number incremented). Communication's summary fields updated. `summary_source` changes to `user_authored`. The original AI-generated revision is preserved. |
| **AI re-generates summary** | New revision created. Communication's summary fields updated. `summary_source` set to `ai_generated`. Previous revisions (including user edits) are preserved. |
| **View old revision** | Client requests a specific revision by ID. Server returns the revision's `summary_html` for display. |

#### Audit Trail Use Case

The revision history enables temporal reconstruction of Conversation content. If a decision was made based on a Conversation that included a particular Communication summary, the system can show exactly what that summary said at the time of the decision — even if the summary was later edited or re-generated.

### 7.7 Relationship to the Conversation Timeline

The Conversation timeline assembles an ordered sequence of Communication summary references:

```
Conversation: Lease Negotiation with Bob
  ┌─────────────────────────────────────────────────┐
  │ 10:15 AM [EMAIL] Bob → Me                       │
  │ ┌─ Summary ─────────────────────────────────┐   │
  │ │ Key points:                                │   │
  │ │ • Contract draft attached                  │   │
  │ │ • Requesting review of clause 5 liability  │   │
  │ │                        [View Original ↗]   │   │
  │ └────────────────────────────────────────────┘   │
  ├─────────────────────────────────────────────────┤
  │ 12:45 PM [SMS] Me → Bob                         │
  │ "Hey, did you see my questions?"                 │
  │                        [View Original ↗]         │
  ├─────────────────────────────────────────────────┤
  │ 3:00 PM [PHONE] Call with Bob (12 min)           │
  │ ┌─ Summary ─────────────────────────────────┐   │
  │ │ Key Discussion Points:                     │   │
  │ │ • Agreed on $500K liability cap            │   │
  │ │ Decisions Made:                            │   │
  │ │ • Proceed with Option B penalty structure  │   │
  │ │ Action Items:                              │   │
  │ │ • Bob: Send revised contract by Feb 21     │   │
  │ │                        [View Original ↗]   │   │
  │ └────────────────────────────────────────────┘   │
  └─────────────────────────────────────────────────┘
```

Each card in the timeline is a **reference** to the Communication's Published Summary — not a copy. The "View Original" link navigates to the full Communication record where the user can see `content_clean`, the raw content, attachments, and the full revision history.

Short communications (SMS, brief notes) display their summary inline without an expandable card — the content is already concise enough.

### 7.8 Summary Generation Triggers

| Trigger | Behavior |
|---|---|
| Communication created (auto-synced) | Summary generation behavior fires after content extraction completes. AI-generated or pass-through per channel rules. |
| Communication created (manual entry) | For user-authored channels, the user writes the summary during creation. For channels with transcripts, summary generation fires after transcript is available. |
| `content_clean` updated | Re-processing of content extraction (e.g., improved parsing logic). Summary is re-generated from the updated `content_clean`. Previous summary revisions preserved. |
| User edits summary | User modifies the summary via the rich text editor. New revision created. `summary_source` updated to `user_authored`. |
| User requests AI re-generation | User explicitly asks the AI to re-generate the summary (e.g., after content_clean was updated or to get a fresh perspective). New revision created. |
| Communication passes triage after override | If a previously filtered communication is un-filtered, summary generation fires for the first time. |

### 7.9 Error Handling

| Failure | Recovery |
|---|---|
| AI API timeout | Retry with exponential backoff (3 attempts). Communication remains visible in Conversation timeline with "[Summary pending]" placeholder. |
| AI API rate limit | Queue and retry after cooldown. |
| AI returns malformed output | Log raw response. Fall back to pass-through (use `content_clean` as summary). Flag for review. |
| AI API unavailable | Pass-through mode until API returns. Queue for AI processing when available. |
| Empty `content_clean` | Skip summary generation. Display "[No content]" in Conversation timeline. |

---

## 8. Communication Entry Points

| Channel            | How It Enters the System                                                                                                | Provider Account Required? |
| ------------------ | ----------------------------------------------------------------------------------------------------------------------- | -------------------------- |
| `email`            | Auto-synced from Gmail API, Microsoft Graph API, or IMAP via provider adapter                                           | Yes                        |
| `sms` / `mms`      | Auto-synced from SMS provider API (Twilio, OpenPhone, etc.) via provider adapter                                        | Yes                        |
| `phone_recorded`   | Metadata + recording from VoIP integration; transcript generated via speech-to-text                                     | Yes                        |
| `phone_manual`     | User creates a Communication record via CRM UI: specifies participants, timestamp, duration, and notes                  | No                         |
| `video_recorded`   | Metadata + recording from meeting platform (Zoom, Teams); transcript via speech-to-text                                 | Yes                        |
| `video_manual`     | User creates a Communication record via CRM UI                                                                          | No                         |
| `in_person`        | User creates a Communication record via CRM UI                                                                          | No                         |
| `note`             | User creates a Communication record via CRM UI                                                                          | No                         |
| Calendar-triggered | Scheduled meeting from calendar integration auto-creates a placeholder Communication; user adds notes after the meeting | Via Event Management PRD   |

### 8.1 Manual Entry Workflow

For channels without automatic capture (`phone_manual`, `video_manual`, `in_person`, `note`), the user provides:

| Field        | Required | Description                                            |
| ------------ | -------- | ------------------------------------------------------ |
| Channel      | Yes      | Which type of interaction                              |
| Timestamp    | Yes      | When it occurred (defaults to now)                     |
| Participants | Yes      | Select existing contacts or create new ones            |
| Duration     | No       | For calls/meetings                                     |
| Subject      | No       | Brief title                                            |
| Content      | No       | What was discussed, decided, or observed               |
| Attachments  | No       | Photos, documents, etc.                                |
| Conversation | No       | Assign to an existing conversation or leave unassigned |

The system creates a Communication record with `source = 'manual'` and `provider_account_id = NULL`.

---

## 9. Provider Account Framework

### 9.1 Provider Account Data Model

Provider accounts represent connected external services. The data model is shared across all integration types (email, SMS, calendar, etc.) and is defined in the [Permissions & Sharing PRD](permissions-sharing-prd_V1.md) Section 11.3.

| Attribute               | Type        | Description                                                                           |
| ----------------------- | ----------- | ------------------------------------------------------------------------------------- |
| `id`                    | TEXT        | Prefixed ULID: `int_` prefix                                                          |
| `tenant_id`             | TEXT        | Owning tenant                                                                         |
| `owner_type`            | TEXT        | `user` (personal) or `tenant` (shared inbox)                                          |
| `owner_id`              | TEXT        | User ID or tenant ID                                                                  |
| `provider`              | TEXT        | `gmail`, `outlook`, `imap`, `openphone`, `twilio`, etc.                               |
| `account_identifier`    | TEXT        | Email address, phone number, or account handle                                        |
| `credentials_encrypted` | BYTEA       | Encrypted OAuth tokens or API keys                                                    |
| `status`                | TEXT        | `active`, `paused`, `error`, `disconnected`                                           |
| `last_sync_at`          | TIMESTAMPTZ | Last successful sync                                                                  |
| `sync_cursor`           | TEXT        | Opaque provider-specific sync position marker                                         |
| `sync_cursor_type`      | TEXT        | Cursor format identifier (e.g., `gmail_history_id`, `outlook_delta_link`, `imap_uid`) |
| `created_at`            | TIMESTAMPTZ |                                                                                       |
| `created_by`            | TEXT        | FK → users                                                                            |

### 9.2 Provider Account Operations

| Operation                    | Behavior                                                                                |
| ---------------------------- | --------------------------------------------------------------------------------------- |
| **Connect**                  | OAuth or credential entry → account registered → initial sync begins                    |
| **Disconnect (retain data)** | Stop syncing, revoke provider access, keep existing Communication records               |
| **Disconnect (delete data)** | Stop syncing, revoke access, cascade-delete all Communication records from this account |
| **Re-authenticate**          | Refresh credentials without affecting data                                              |
| **Pause/Resume sync**        | Temporarily stop/resume without affecting credentials or data                           |

### 9.3 Personal vs. Shared Accounts

| Aspect                | Personal Account                  | Shared Account (Tenant-Level)                         |
| --------------------- | --------------------------------- | ----------------------------------------------------- |
| Connected by          | Individual user                   | Sys Admin                                             |
| Credentials scoped to | One user                          | Tenant                                                |
| Data visibility       | User's default visibility setting | Always `public`                                       |
| Examples              | User's Gmail, personal phone      | sales@company.com, support@company.com                |
| Attribution           | `created_by` = account owner      | `created_by` = system; `sent_by` tracks actual sender |

### 9.4 Shared Inbox Attribution

When a user responds via a shared inbox, the Communication record captures both perspectives:

- **`from_address`** (participant metadata) — The shared inbox address (what the external recipient sees)
- **`sent_by`** (communication field) — The actual user who composed and sent the message (internal attribution)

This dual attribution is critical for performance tracking, workload distribution, and audit purposes.

---

## 10. Provider Adapter Architecture

### 10.1 Adapter Interface

Every provider adapter implements a common interface:

```
ProviderAdapter
  ├── authenticate(credentials) → session
  ├── fetch_initial(session, config) → [RawCommunication], cursor
  ├── fetch_incremental(session, cursor) → [RawCommunication], new_cursor
  ├── normalize(raw) → Communication (common schema)
  ├── get_sync_status(session) → SyncStatus
  └── revoke(session) → void
```

### 10.2 Adapter Responsibilities

| Responsibility        | Description                                                                                          |
| --------------------- | ---------------------------------------------------------------------------------------------------- |
| **Authentication**    | Provider-specific OAuth or credential flows                                                          |
| **Fetching**          | Translating sync requests into provider API calls (initial batch, incremental delta, manual trigger) |
| **Normalization**     | Converting provider responses to the common Communication schema (Section 5.1)                       |
| **Cursor management** | Tracking sync position in provider-specific format                                                   |
| **Error handling**    | Translating provider errors into common error types                                                  |
| **Rate limiting**     | Respecting provider-specific rate limits                                                             |

### 10.3 Sync Modes

All provider adapters support three sync modes:

**Initial sync (first connection):** Batch fetch of historical communications matching a configurable scope (e.g., emails from the last 90 days). Performance target: <5 minutes for a typical mailbox (5,000 messages). Safe to restart — deduplication by `provider_message_id`.

**Incremental sync (ongoing):** Fetch only changes since the last sync cursor. Performance target: <5 seconds for typical changes (0–20 new messages). Triggered by webhook/push notification or polling interval.

**Manual sync (user-triggered):** Forces an immediate incremental sync regardless of schedule.

### 10.4 Sync Reliability

| Failure Scenario               | Recovery                                                                                                 |
| ------------------------------ | -------------------------------------------------------------------------------------------------------- |
| Provider API timeout           | Exponential backoff retry (3 attempts)                                                                   |
| Provider rate limit (HTTP 429) | Respect `Retry-After` header                                                                             |
| Invalid sync cursor            | Date-based re-sync from last known timestamp                                                             |
| Partial batch failure          | Skip failed messages, log for retry                                                                      |
| Network interruption           | Retry with backoff; queue for next sync                                                                  |
| Token expiration (HTTP 401)    | Auto-refresh; re-authenticate if refresh fails                                                           |
| Duplicate messages             | `INSERT ... ON CONFLICT DO NOTHING` (UNIQUE constraint on `provider_account_id` + `provider_message_id`) |
| Message deletion at provider   | Mark Communication as archived; recompute conversation metadata                                          |

### 10.5 Sync Audit Trail

Every sync operation is logged:

| Field                            | Description                                    |
| -------------------------------- | ---------------------------------------------- |
| `sync_id`                        | Unique identifier for this sync operation      |
| `provider_account_id`            | Which account was synced                       |
| `sync_type`                      | `initial`, `incremental`, `manual`             |
| `started_at` / `completed_at`    | Timestamps                                     |
| `messages_fetched`               | Total messages retrieved from provider         |
| `messages_stored`                | New Communications created                     |
| `messages_skipped`               | Duplicates or filtered                         |
| `conversations_created`          | New conversations formed                       |
| `conversations_updated`          | Existing conversations with new communications |
| `cursor_before` / `cursor_after` | Sync position markers                          |
| `status`                         | `success`, `partial_failure`, `failed`         |
| `error_details`                  | Error information if applicable                |

---

## 11. Communication Participants & Contact Resolution

### 11.1 Participant Relation Type

Communication participants are modeled as a **system Relation Type** in the Custom Objects framework:

| Attribute                 | Value                                                                  |
| ------------------------- | ---------------------------------------------------------------------- |
| Relation Type Name        | Communication Participants                                             |
| Relation Type Slug        | `communication_participants`                                           |
| Source Object Type        | Communication (`com_`)                                                 |
| Target Object Type        | Contact (`con_`)                                                       |
| Cardinality               | Many-to-many                                                           |
| Directionality            | Bidirectional                                                          |
| `is_system`               | `true`                                                                 |
| Cascade (source archived) | Cascade archive participant links                                      |
| Cascade (target archived) | Nullify (preserve communication, mark participant as archived contact) |

**Metadata fields on the relation instance:**

| Field              | Type     | Description                                                                                        |
| ------------------ | -------- | -------------------------------------------------------------------------------------------------- |
| `role`             | Select   | `sender`, `to`, `cc`, `bcc`, `participant` (for calls/meetings)                                    |
| `address`          | Text     | The identifier used for this participant in this communication (email address, phone number, etc.) |
| `display_name`     | Text     | The display name from the communication header (e.g., "Bob Smith" from email `From:` header)       |
| `is_account_owner` | Checkbox | Whether this participant is the CRM user (the account owner)                                       |

### 11.2 Design Principle

**Every communication participant must be resolved to a CRM contact.** The system actively works to identify all senders and recipients across all channels. Under no circumstance should a conversation be left with permanently unidentified contacts.

### 11.3 Integration with Contact Intelligence System

The Contact Intelligence system (defined in the Contact Management PRD) is the **single source of truth** for identity resolution.

**Communications consumes from Contact Intelligence:**

- "This email address belongs to Bob" → emails associate with Bob's contact record
- "This phone number belongs to Bob" → SMS and calls associate with the same contact
- A unified contact record means communications across all channels are correctly attributed

**Communications contributes to Contact Intelligence:**

- A new email arrives from an unknown address → trigger identity resolution workflow
- An SMS comes from an unknown number → trigger identity resolution workflow
- A user creates a manual communication "meeting with Sarah from Acme" → potential new contact signal
- Every communication with an unrecognized identifier is a **signal** fed back to the Contact Intelligence system

### 11.4 Identifier Types by Channel

| Channel          | Primary Identifier            | Resolution Method                            |
| ---------------- | ----------------------------- | -------------------------------------------- |
| `email`          | Email address                 | Direct lookup in `contact_identifiers`       |
| `sms` / `mms`    | Phone number                  | Phone number lookup in `contact_identifiers` |
| `phone_recorded` | Phone number                  | Phone number lookup                          |
| `phone_manual`   | User-specified                | User selects contact during entry            |
| `video_recorded` | Platform display name + email | Email lookup; name matching as fallback      |
| `video_manual`   | User-specified                | User selects contacts during entry           |
| `in_person`      | User-specified                | User selects contacts during entry           |

### 11.5 Pending Identification State

When a communication arrives with an unrecognized identifier:

1. Communication enters the system normally — it is **not blocked**.
2. A participant relation instance is created with the identifier in the `address` field and a placeholder contact reference.
3. The Contact Intelligence system runs resolution:
   - Check existing contacts for alternate identifiers
   - Check user's contact book (Google Contacts, Outlook, phone)
   - OSINT lookup if enabled (third-party enrichment)
   - Pattern matching (same name, same company domain)
4. **If resolved automatically** → Participant relation updated to point to the identified contact.
5. **If not resolved** → User prompted to identify the contact:
   - Suggestions provided if partial matches exist
   - User can match to existing contact, create new contact, or mark as irrelevant

**Critical principle:** Pending identification does **not** block conversation assignment, AI processing, or user display. The communication flows through the entire pipeline while contact resolution proceeds in parallel.

### 11.6 Cross-Channel Contact Unification

The Contact Intelligence system maintains a unified contact record that links all known identifiers:

```
Contact: Bob Smith (Acme Corp)
  ├── Email: bob.smith@acmecorp.com
  ├── Email: bob@gmail.com (personal)
  ├── Phone: +1-555-0100 (work)
  ├── Phone: +1-555-0199 (mobile)
  ├── Slack: @bsmith
  └── Zoom: "Bob S"
```

This means an email from `bob.smith@acmecorp.com` and an SMS from `+1-555-0199` are both recognized as Bob Smith — enabling the Conversations PRD to maintain cross-channel conversation continuity.

---

## 12. Triage & Intelligent Filtering

### 12.1 Purpose

Not every communication warrants AI analysis. Automated notifications, marketing emails, and messages from unknown sources consume AI resources without providing relationship intelligence. The triage pipeline classifies communications before they enter the intelligence layer.

### 12.2 General Triage Framework

Triage operates as a sequence of filter layers. Each layer can either **pass** (communication continues to next layer) or **filter** (communication is tagged with a `triage_result` and `triage_reason`, and skips AI processing).

```
Communication arrives
    │
    ├── Layer 1: Channel-specific heuristics
    │     (defined in child PRDs — e.g., automated sender patterns for email)
    │     → Pass or filter with reason
    │
    ├── Layer 2: Known-Contact Gate
    │     At least one participant (excluding account owner) must be a known CRM contact
    │     → Pass or filter as 'no_known_contacts'
    │
    ├── Layer 3: User-defined rules (future)
    │     User-configurable allowlists/blocklists
    │     → Pass or filter as 'user_filtered'
    │
    └── Result: triage_result = NULL (passed) or specific filter reason
```

### 12.3 Channel-Specific Heuristics

Each channel has its own heuristic patterns, defined in the respective child PRD:

**Email** (defined in Email Provider Sync PRD):

- Automated sender patterns: `noreply@`, `notification@`, `billing@`, `alerts@` (16 patterns)
- Automated subject patterns: "out of office", "automatic reply", "password reset" (12 patterns)
- Marketing content: body contains "unsubscribe"

**SMS/MMS** (defined in SMS/MMS PRD — future):

- Short code senders (5–6 digit numbers)
- Known marketing patterns

**Other channels:** Manual entries (`phone_manual`, `video_manual`, `in_person`, `note`) bypass triage entirely — if the user entered it, it's real.

### 12.4 Known-Contact Gate

At least one participant (excluding the account owner) must be a known CRM contact. Communications where all participants are unknown are filtered as `no_known_contacts`.

**Rationale:** Communications from entirely unknown senders are unlikely to represent meaningful relationship interactions. However, they are **not deleted** — they are tagged and available for review. If the user later identifies one of the participants, the communication can be un-filtered.

### 12.5 Triage Transparency

Filtered communications are **never deleted**. They remain in the system with:

- `triage_result` set to the filter reason
- `triage_reason` set to a human-readable explanation
- Full content preserved
- Available in "Filtered" views for user review

Users can override any triage decision, which:

1. Sets `triage_result` back to NULL
2. Queues the communication for AI processing
3. Optionally creates a learning signal for the triage system (future: ML-based classification)

### 12.6 Future Enhancements

- ML-based classification learning from user overrides
- User-configurable allowlists/blocklists per provider account
- Category-based rules using provider labels (Gmail categories, Outlook Focused/Other)
- Volume-based detection for high-frequency automated senders

---

## 13. Attachments

### 13.1 Attachment Model

Any communication can have zero or more attached files. Attachments are not a separate object type — they are behavior-managed records associated with Communication records.

| Attribute          | Type        | Description                                                                      |
| ------------------ | ----------- | -------------------------------------------------------------------------------- |
| `id`               | TEXT        | Prefixed ULID: `att_` prefix                                                     |
| `communication_id` | TEXT        | FK → communications                                                              |
| `filename`         | TEXT        | Original filename                                                                |
| `mime_type`        | TEXT        | MIME type (e.g., `application/pdf`, `image/jpeg`)                                |
| `size_bytes`       | BIGINT      | File size                                                                        |
| `storage_key`      | TEXT        | Reference in object storage (S3/MinIO)                                           |
| `source`           | TEXT        | `synced` (from email), `uploaded` (user), `recording` (call/video), `transcript` |
| `created_at`       | TIMESTAMPTZ |                                                                                  |

### 13.2 Storage Strategy

| Attachment Type       | Storage                                                               | Rationale                                  |
| --------------------- | --------------------------------------------------------------------- | ------------------------------------------ |
| Email attachments     | On-demand download from provider (Phase 1); object storage (Phase 2+) | Reduces initial sync time and storage cost |
| Call/video recordings | Object storage                                                        | Provider access may be time-limited        |
| User-uploaded files   | Object storage                                                        | No external provider to download from      |
| Transcripts           | Stored as `content_clean` on the Communication record                 | Text content, not binary                   |

### 13.3 Recording-Transcript Relationship

For recorded calls and video meetings, the **transcript becomes the `content_clean`** of the Communication (for AI processing and search), while the **original recording is an attachment** (for playback and verification).

---

## 14. Multi-Account Management

### 14.1 Unified Feed

Multiple provider accounts produce a single, chronologically sorted communication feed. Each Communication record is tagged with its `provider_account_id`, enabling:

- Unified timeline views (all accounts, all channels)
- Account-filtered views ("only emails from my work Gmail")
- Channel-filtered views ("only SMS")

### 14.2 Cross-Account Considerations

- Same real-world thread via two accounts currently creates separate Communication records. The Conversations PRD handles conversation-level deduplication.
- Future: cross-account merge detection via subject + participants + dates.
- Contact resolution is unified across accounts via the Contact Intelligence system.

---

## 15. Event Sourcing & Temporal History

### 15.1 Event Table

Per Custom Objects PRD Section 19, the Communication entity type has a companion event table:

```sql
-- Within tenant schema: tenant_abc.communications_events
CREATE TABLE communications_events (
    id              TEXT PRIMARY KEY,        -- evt_01HX8B...
    entity_id       TEXT NOT NULL,           -- com_01HX8A... (the Communication record)
    tenant_id       TEXT NOT NULL,
    event_type      TEXT NOT NULL,           -- 'created', 'field_updated', 'archived', etc.
    field_slug      TEXT,                    -- Which field changed (NULL for creation/archival)
    old_value       TEXT,                    -- Previous value (JSON-encoded)
    new_value       TEXT,                    -- New value (JSON-encoded)
    changed_by      TEXT,                    -- FK → users (NULL for system/sync actions)
    changed_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata        JSONB                    -- Additional context (sync_id, provider info, etc.)
);

CREATE INDEX idx_comm_events_entity ON communications_events (entity_id, changed_at);
CREATE INDEX idx_comm_events_type ON communications_events (event_type);
```

### 15.2 Event Types

| Event Type                | Trigger                                      | Description                               |
| ------------------------- | -------------------------------------------- | ----------------------------------------- |
| `created`                 | New communication synced or manually entered | Full record snapshot in `new_value`       |
| `field_updated`           | Any field change                             | Old and new values for the specific field |
| `conversation_assigned`   | Communication assigned to a conversation     | `conversation_id` change                  |
| `conversation_unassigned` | Communication removed from a conversation    | `conversation_id` set to NULL             |
| `triage_overridden`       | User overrides a triage decision             | `triage_result` change                    |
| `participant_added`       | New participant linked                       | Participant details in metadata           |
| `participant_resolved`    | Unknown participant identified               | Contact resolution details                |
| `archived`                | Communication soft-deleted                   |                                           |
| `unarchived`              | Communication restored                       |                                           |
| `summary_generated`       | Summary generation behavior produces initial or re-generated summary | Summary revision ID in metadata. `summary_source` in metadata. |
| `summary_revised`         | User edits a summary                         | New summary revision ID in metadata. Points to the revision rather than storing full content. |

### 15.3 Sync Operation Events

In addition to entity-level events, sync operations are logged separately (Section 9.5) for operational monitoring. The entity-level `created` event on each Communication includes sync metadata (sync_id, provider_account_id) in its `metadata` JSONB field, linking the communication to the sync operation that captured it.

---

## 16. Virtual Schema & Data Sources

### 16.1 Communication Virtual Schema Table

Per Data Sources PRD, the Communication object type's field registry automatically generates a virtual schema table for SQL data sources:

```sql
-- Virtual schema (automatically generated from field registry)
-- Users write SQL queries against this schema
SELECT
    c.id,
    c.channel,
    c.direction,
    c.timestamp,
    c.subject,
    c.body_preview,
    c.content_clean,
    c.source,
    c.conversation_id,
    c.triage_result,
    c.duration_seconds,
    c.has_attachments,
    c.created_at,
    c.updated_at
FROM communications c
WHERE c.archived_at IS NULL;
```

### 16.2 Relation Traversal

Data Source queries can traverse the Communication Participants relation to join Communications with Contacts:

```sql
-- Example: All communications with a specific contact
SELECT c.timestamp, c.channel, c.subject, c.body_preview
FROM communications c
JOIN communication_participants cp ON cp.communication_id = c.id
WHERE cp.contact_id = 'con_01HX7...'
ORDER BY c.timestamp DESC;
```

### 16.3 Entity ID Convention

The `com_` prefix on Communication IDs enables automatic entity type detection in Data Source queries, search results, and deep links throughout the platform.

---

## 17. Search & Discovery

### 17.1 Search Capabilities

| Search Type                    | Scope                                                     |
| ------------------------------ | --------------------------------------------------------- |
| Full-text communication search | `content_clean`, `subject` across all channels            |
| Contact-scoped                 | "All communications with Alice" across all channels       |
| Channel filtering              | "Only emails" or "Only SMS"                               |
| Account filtering              | Specific source accounts                                  |
| Triage filtering               | Passed, filtered, or all                                  |
| Status filtering               | Via conversation assignment (defers to Conversations PRD) |
| Date-range filtering           | Any time period on `timestamp`                            |

### 17.2 Full-Text Search

Communications use PostgreSQL native `tsvector`/`tsquery` for full-text search:

```sql
-- Generated column for full-text search
ALTER TABLE communications ADD COLUMN search_vector tsvector
    GENERATED ALWAYS AS (
        setweight(to_tsvector('english', COALESCE(subject, '')), 'A') ||
        setweight(to_tsvector('english', COALESCE(content_clean, '')), 'B')
    ) STORED;

CREATE INDEX idx_comm_search ON communications USING GIN (search_vector);
```

Subject text is weighted higher ('A') than body content ('B') for relevance ranking.

### 17.3 Search Indexing

Communications are indexed when created, updated, or when `content_clean` is regenerated. The generated column approach means indexing is automatic and synchronous — no async lag.

---

## 18. Storage & Data Retention

### 18.1 What Gets Stored

| Data                              | Format                        | Retention                                       |
| --------------------------------- | ----------------------------- | ----------------------------------------------- |
| Communication record (all fields) | PostgreSQL row                | Configurable (default: indefinite)              |
| `content_html` (email raw HTML)   | TEXT column                   | Same as record                                  |
| `content_clean` (processed text)  | TEXT column                   | Same as record                                  |
| Call/video transcripts            | TEXT in `content_clean`       | Same as record                                  |
| Attachments (files)               | Binary in object storage      | Configurable (default: on-demand from provider) |
| Attachment metadata               | PostgreSQL rows               | Same as record                                  |
| Event history                     | `communications_events` table | Configurable (default: indefinite)              |
| Sync audit logs                   | Separate table                | Configurable (default: 90 days)                 |

### 18.2 Storage Estimates

| Data Type                    | Per Communication | 10,000 Communications |
| ---------------------------- | ----------------- | --------------------- |
| Record fields + metadata     | ~1 KB avg         | ~10 MB                |
| `content_clean` (text)       | ~2 KB avg         | ~20 MB                |
| `content_html` (email only)  | ~8 KB avg         | ~80 MB                |
| Event history                | ~0.5 KB per event | ~5 MB (10K events)    |
| Audio recordings (if stored) | ~1 MB/min         | Highly variable       |

---

## 19. Privacy, Security & Compliance

### 19.1 Data Protection

- **Minimum necessary access** — Read-only scopes for all providers until send capability is needed.
- **Encrypted at rest and in transit** — TLS 1.2+ for all API calls; database encryption in production.
- **Credential isolation** — OAuth tokens and API keys stored encrypted, never in logs.
- **Tenant isolation** — Schema-per-tenant in PostgreSQL per Custom Objects PRD Section 24.

### 19.2 Compliance

| Requirement                            | How Addressed                                                                                         |
| -------------------------------------- | ----------------------------------------------------------------------------------------------------- |
| **GDPR — Access/Deletion/Portability** | Full export via API; cascade deletion (communication + events + attachments); standard export formats |
| **GDPR — Consent**                     | Account connection is explicit consent; AI processing disclosed during setup                          |
| **SOC 2 — Audit trails**               | Sync audit logs, event sourcing, modification tracking                                                |
| **CCPA**                               | Same as GDPR; no sale of communication data                                                           |

### 19.3 AI Data Handling

- Only `content_clean` (processed, truncated content) is sent to AI — not raw HTML, attachments, or full threads.
- AI responses are stored in CRM (on Conversation records, per Conversations PRD), not retained by AI provider.
- Users are informed that content is processed by an external AI service during account connection.

---

## 20. API Design

### 20.1 Communication CRUD API

Per Custom Objects PRD Section 23.4, Communications use the uniform record CRUD pattern:

| Endpoint                                | Method | Description                                                                  |
| --------------------------------------- | ------ | ---------------------------------------------------------------------------- |
| `/api/v1/communications`                | GET    | List communications (paginated, filterable, sortable)                        |
| `/api/v1/communications`                | POST   | Create a manual communication                                                |
| `/api/v1/communications/{id}`           | GET    | Get a single communication with participants                                 |
| `/api/v1/communications/{id}`           | PATCH  | Update communication fields (conversation assignment, triage override, etc.) |
| `/api/v1/communications/{id}/archive`   | POST   | Archive a communication                                                      |
| `/api/v1/communications/{id}/unarchive` | POST   | Unarchive a communication                                                    |
| `/api/v1/communications/{id}/history`   | GET    | Get event history for a communication                                        |

### 20.2 Participant API

| Endpoint                                                | Method | Description                                         |
| ------------------------------------------------------- | ------ | --------------------------------------------------- |
| `/api/v1/communications/{id}/participants`              | GET    | List participants with roles and contact references |
| `/api/v1/communications/{id}/participants`              | POST   | Add a participant (manual communications)           |
| `/api/v1/communications/{id}/participants/{contact_id}` | PATCH  | Update participant metadata (role, etc.)            |

### 20.3 Attachment API

| Endpoint                                           | Method | Description                    |
| -------------------------------------------------- | ------ | ------------------------------ |
| `/api/v1/communications/{id}/attachments`          | GET    | List attachments with metadata |
| `/api/v1/communications/{id}/attachments`          | POST   | Upload an attachment           |
| `/api/v1/communications/{id}/attachments/{att_id}` | GET    | Download attachment content    |
| `/api/v1/communications/{id}/attachments/{att_id}` | DELETE | Remove an attachment           |

### 20.4 Sync API

| Endpoint                   | Method | Description                                               |
| -------------------------- | ------ | --------------------------------------------------------- |
| `/api/v1/sync/trigger`     | POST   | Trigger sync for a specific provider account              |
| `/api/v1/sync/trigger-all` | POST   | Trigger sync for all active accounts for the current user |
| `/api/v1/sync/status`      | GET    | Get sync status for all active accounts                   |
| `/api/v1/sync/audit`       | GET    | Get sync audit log (paginated)                            |

### 20.5 Triage API

| Endpoint                                      | Method | Description                                            |
| --------------------------------------------- | ------ | ------------------------------------------------------ |
| `/api/v1/communications/{id}/triage/override` | POST   | Override a triage decision (un-filter a communication) |
| `/api/v1/communications/triage/stats`         | GET    | Get triage statistics (filtered count by reason)       |

---

## 21. Design Decisions

### Why a system object type instead of a standalone table?

Making Communication a system object type in the Custom Objects framework gives it automatic participation in every platform capability: Views, Data Sources, event sourcing, field registry, permissions, audit trails, and the API surface. A standalone table would require hand-building each integration. The marginal cost of fitting Communications into the framework is low (it already has the right shape — fields, relations, lifecycle), and every future framework enhancement automatically applies.

### Why a participant Relation Type instead of `from_address`/`to_addresses` columns?

The Custom Objects framework's Relation Type model provides structured, queryable participant links. Flat address columns cannot answer "show all communications involving Bob" without parsing concatenated address strings. The Relation Type gives us: JOIN-based queries, metadata per participant (role, display name), bidirectional navigation (Contact → their Communications), and participation in Views and Data Sources.

### Why `conversation_id` as an FK column instead of a Relation Type?

The Communication→Conversation link is strictly many:1 (a communication belongs to at most one conversation), carries no metadata, and is not user-navigable from the Conversation side in the same way as, say, Event→Contact. An FK column is proportional to the complexity and keeps the query path simple. The Conversations PRD defines conversation membership queries that simply filter Communications by `conversation_id`.

### Why separate `content_raw`, `content_html`, and `content_clean`?

Three content fields serve different purposes: `content_raw` preserves the original for debugging and re-processing; `content_html` preserves email HTML for the dual-track parsing pipeline; `content_clean` is the processed output that users see and AI consumes. If parsing logic improves, all communications can be re-processed from `content_raw`/`content_html` without losing the original.

### Why channel-specific child PRDs instead of one monolithic document?

The original Communication & Conversation Intelligence PRD v2.0 was 1,500+ lines covering everything from the organizational hierarchy to Outlook CSS selectors. Email alone has 300+ lines of provider-specific details (Gmail API, Outlook Graph API, IMAP, dual-track parsing pipeline, provider-specific HTML selectors). SMS, voice, and video will each have comparable complexity. Keeping each channel in a dedicated child PRD ensures maintainability and allows each channel to evolve independently.

### Why is `note` a channel type rather than using the Notes system?

The `note` channel type on Communications represents a user-recorded interaction ("I had a phone call with Bob and we discussed X"). It has participants, a timestamp, and represents something that happened. The Notes system (Notes PRD) represents supplementary commentary and knowledge that attaches *to* entities. A user-logged phone call is a Communication; a user's observation "Bob seemed hesitant" is a Note attached to that Communication. Different purposes, different system object types.

### Why does each Communication own its Published Summary instead of letting the Conversation generate summaries?

The Communication is the source of truth for what was said. Making the Communication responsible for producing its own summary means: (a) each channel can produce the most appropriate summary for its content type, (b) the summary is immediately available when the Communication is created, before it's even assigned to a Conversation, (c) updating a summary automatically propagates to every Conversation that references it, and (d) the Conversation-level AI consumes pre-distilled summaries rather than re-processing raw content every time. The Conversation is a presentation container that references summaries, not a content generator.

### Why full revision control on Communication summaries?

Decisions are made based on information available at the time. If a Conversation shows a summary stating "Bob agreed to $500K liability cap" and that summary is later edited, the revision history preserves what the summary said when the lease was signed. Without revision control, post-hoc edits could make it appear that a different set of facts led to the decision. The append-only, full-snapshot model (same pattern as Notes revisions) ensures complete temporal reconstruction at any point.

### Why rich text summaries instead of plain text?

Communication summaries often have natural structure: key points, decisions made, action items, assignments. Plain text flattens this into a wall of text that loses the structure AI or users created. Rich text (same editor and storage contract as Notes) preserves headings, bullet lists, bold emphasis, and other formatting that makes summaries scannable in the Conversation timeline. This also ensures a consistent editing experience across Notes and Communication summaries.

---

## 22. Phasing & Roadmap

### Phase 1: Email Foundation (Current PoC → Production)

**Goal:** Graduate Gmail PoC to production; establish the Communication entity as a system object type.

- Communication read model table with full field registry
- Communication event sourcing (`communications_events`)
- Communication Participants Relation Type
- Provider account framework (personal accounts)
- Gmail provider adapter (production-hardened) — per Email Provider Sync PRD
- Email parsing pipeline (dual-track) — per Email Provider Sync PRD
- Triage filtering (heuristic + known-contact gate)
- Manual communication entry (phone calls, meetings, notes)
- Published Summary generation (pass-through for short content; user-authored for manual entries)
- `communication_summary_revisions` table and revision lifecycle
- Communication CRUD API
- Sync API and audit logging
- Full-text search on communications
- Basic attachment metadata (on-demand download)

### Phase 2: Outlook + SMS Foundation

**Goal:** Second email provider; first non-email channel.

- Outlook provider adapter — per Email Provider Sync PRD
- SMS integration (provider TBD — Twilio or OpenPhone) — per SMS/MMS PRD
- Cross-channel unified feed
- Shared inbox support (tenant-level provider accounts)
- AI-powered Published Summary generation (email summarization, configurable thresholds)
- Summary revision UI (view history, edit AI summaries, re-generate)
- Outlook-specific parsing patterns
- Expanded test suite

### Phase 3: IMAP + Voice + Video

**Goal:** Universal email support; recorded communication integration.

- IMAP provider adapter — per Email Provider Sync PRD
- VoIP integration for recorded calls (transcription pipeline) — per Voice/VoIP PRD
- Video meeting integration (Zoom/Teams transcript capture) — per Video Meetings PRD
- AI-powered transcript summarization (key points, decisions, action items)
- Attachment storage in object storage (S3/MinIO)
- Bulk import capability (`source = 'imported'`)

### Phase 4: Advanced Features

**Goal:** Platform-level communication intelligence infrastructure.

- ML-based triage classification
- User-configurable triage rules
- Cross-account communication deduplication
- Email sending from CRM (elevated OAuth scopes)
- Communication templates
- Attachment full-text indexing

---

## 23. Dependencies & Related PRDs

| PRD                                  | Relationship                                                                                                                                             | Dependency Direction                                                                                                |
| ------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------- |
| **Custom Objects PRD**               | Communication is a system object type. Table structure, field registry, event sourcing, and relation model are governed by the Custom Objects framework. | **Bidirectional.** This PRD defines Communication-specific behaviors; Custom Objects provides the entity framework. |
| **Conversations PRD**                | Conversations group Communications. Communications reference their parent Conversation via `conversation_id`. The Conversation timeline renders Communication Published Summaries by reference.                                            | **Communications is foundational.** Conversations depend on the Communication entity, its common schema, and Published Summaries.         |
| **Contact Management PRD**           | Communication participants are resolved to Contact records via `contact_identifiers`.                                                                    | **Bidirectional.** Communications consume contact resolution and contribute unknown-identifier signals.             |
| **Company Management PRD**           | Email domain extraction triggers company auto-creation.                                                                                                  | **Communications contributes signals** to Company Management.                                                       |
| **Event Management PRD**             | Calendar events correlate with communications via conversations.                                                                                         | **Events depend on Communications** indirectly through the Conversations PRD.                                       |
| **Notes PRD**                        | Notes attach to Communications as supplementary commentary. Communication Published Summaries share the same rich text content architecture and revision model as Notes.                                              | **Notes depend on Communications** as an attachment target. **Shared architecture** for rich text content.                                                         |
| **Email Provider Sync PRD**          | Gmail, Outlook, IMAP adapters; email parsing pipeline; email-specific triage.                                                                            | **Child PRD.** Implements the provider adapter interface and email-specific behaviors defined here.                 |
| **Data Sources PRD**                 | Virtual schema derived from Communication field registry.                                                                                                | **Data Sources depend on Custom Objects** (which governs Communications).                                           |
| **Views & Grid PRD**                 | Communication views operate on fields from the field registry.                                                                                           | **Views depend on Custom Objects** (which governs Communications).                                                  |
| **Permissions & Sharing PRD**        | Provider account management, communication visibility, row-level security.                                                                               | **Communications depend on Permissions** for access control.                                                        |
| **AI Learning & Classification PRD** | AI classification and learning from triage overrides and conversation assignment corrections.                                                            | **AI depends on Communications** for training signals.                                                              |

---

## 24. Open Questions

1. **Attachment storage model** — Store all attachments in object storage (high storage cost, provider-independent) vs. on-demand download from provider (requires continued provider access, zero storage cost)? Phase 1 uses on-demand; Phase 3 plans migration to object storage. Is a hybrid model (store critical, on-demand for bulk) worth the complexity?

2. **Real-time sync infrastructure** — Gmail Pub/Sub and Outlook webhooks need publicly accessible callbacks. Cloud function, dedicated endpoint, or message queue? This affects sync latency for production deployment.

3. **Email sending from CRM** — Should the system support sending (requires elevated OAuth scopes like `gmail.send`, `Mail.Send`)? Adds significant value for workflow automation but increases security surface and compliance complexity.

4. **Shared mailbox support** — How should team/shared mailboxes be handled? Current model (Section 8.3) supports tenant-level provider accounts. Should multiple users be able to connect the same mailbox independently (duplicating data), or should it be a single shared connection?

5. **Communication merge/split operations** — When a user realizes two Communication records represent the same interaction (e.g., same email synced from two accounts), what is the merge workflow? What happens to event history, participants, and conversation assignments?

6. **Opt-out granularity** — Can users exclude specific contacts, channels, or provider accounts from AI processing? What does "exclude" mean operationally — skip triage? Skip summarization? Skip both?

7. **SMS provider selection** — Which SMS integration to pursue first? Twilio (most flexible, per-message pricing), OpenPhone (bundled phone + SMS, simpler integration), or native phone sync (iMessage/Google Messages — platform-specific, complex)?

8. **Speech-to-text service** — Which transcription service for recorded calls and video? Self-hosted (Whisper — no per-minute cost, privacy) vs. cloud (Google, AWS — higher accuracy, per-minute pricing)? Cost and accuracy tradeoffs.

9. **Slack/Teams integration model** — These tools have their own hierarchy (workspaces/teams → channels → threads). Should Slack/Teams messages be Communications? If so, how does their structure map to our channel model? Deferred to separate discussion.

---

## 25. Future Work

- **Multi-language content extraction** — Current email parsing patterns are English-only. Non-English valedictions, disclaimers, and signature markers need localized pattern sets.
- **Attachment content indexing** — Full-text search within attached documents (PDF, DOCX) for "find the communication that had the contract attached."
- **Communication deduplication** — Cross-account detection when the same real-world message is synced from multiple provider accounts.
- **Communication templates** — Pre-defined templates for common manual entries (site visit report, phone call debrief, meeting minutes).
- **Bulk operations** — Archive, assign to conversation, or tag multiple communications at once.
- **Communication analytics** — Volume trends by channel, response time metrics, communication frequency per contact.

---

## 26. Glossary

| Term                       | Definition                                                                                                                                                                                                 |
| -------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Communication**          | An individual interaction — a single email, SMS, phone call, video meeting, in-person meeting, or user-entered note. The atomic unit of the communication system. A system object type with prefix `com_`. |
| **Channel**                | The medium of a communication. A Select field with protected system options: `email`, `sms`, `mms`, `phone_recorded`, `phone_manual`, `video_recorded`, `video_manual`, `in_person`, `note`.               |
| **Provider Account**       | A connected external service (Gmail account, Outlook account, Twilio number, etc.) that the system syncs communications from. Stored in the `provider_accounts` table.                                     |
| **Provider Adapter**       | A module implementing the common adapter interface for a specific provider. Handles authentication, fetching, normalization, cursor management, and error translation.                                     |
| **Sync Cursor**            | An opaque marker tracking the system's sync position in a provider's data stream. Format is provider-specific (Gmail `historyId`, Outlook `deltaLink`, IMAP `UIDVALIDITY:lastUID`).                        |
| **Content Extraction**     | Removing channel-specific noise (quoted replies, signatures, boilerplate for email; filler words for transcripts) to produce clean content for display and AI processing.                                  |
| **Triage**                 | Classifying communications as real human interactions vs. automated/marketing noise. A multi-layer pipeline that tags filtered communications without deleting them.                                       |
| **Known-Contact Gate**     | A triage filter requiring at least one recognized CRM contact among participants (excluding the account owner).                                                                                            |
| **Pending Identification** | State of an unrecognized contact identifier undergoing resolution. Does not block communication processing.                                                                                                |
| **Participant Relation**   | The Communication→Contact Relation Type (`communication_participants`) that models who was involved in each communication, with role and address metadata.                                                 |
| **Common Schema**          | The unified field structure that all channels normalize to: timestamp, channel, direction, participants, content, attachments, source metadata. Defined by the Communication field registry.               |
| **Dual-Track Pipeline**    | The email parsing architecture: HTML-based structural removal with plain-text regex fallback. Defined in the Email Provider Sync PRD.                                                                      |
| **Segment**                | A portion of a communication assigned to a different conversation than the primary. Created by user action. Defined in the Conversations PRD.                                                              |
| **Published Summary**      | The rich text representation of a Communication's contribution to its parent Conversation's timeline. Owned by the Communication. AI-generated for synced content, user-authored for manual entries, pass-through for short messages. Stored as `summary_json`, `summary_html`, `summary_text`. |
| **Summary Revision**       | An append-only, full-snapshot record of a Published Summary at a point in time. Stored in `communication_summary_revisions`. Enables temporal reconstruction of Conversation content for audit purposes. |
| **Summary Source**         | How a Published Summary was created: `ai_generated` (AI distilled from `content_clean`), `user_authored` (user wrote or edited the summary), `pass_through` (`content_clean` used as-is for short content). |

---

## Appendix A: PoC Implementation Reference

The following details describe the proof-of-concept implementation that preceded this PRD. They are preserved for historical reference and to document the functional baseline.

### A.1 PoC Architecture

| Component          | PoC Implementation                                              |
| ------------------ | --------------------------------------------------------------- |
| Database           | SQLite with flat table structure                                |
| Email provider     | Gmail API only                                                  |
| Sync               | `history.list` incremental + `threads.list` initial             |
| Parsing            | `strip_quotes()` dual-track pipeline (see `email_stripping.md`) |
| Triage             | Heuristic junk detection + known-contact gate                   |
| AI                 | Claude-powered summarization                                    |
| Contact resolution | Google Contacts sync → email address lookup                     |

### A.2 PoC File Structure

| File                       | Role                                      |
| -------------------------- | ----------------------------------------- |
| `poc/sync.py`              | Multi-account email sync orchestration    |
| `poc/email_parser.py`      | Plain-text email parsing pipeline         |
| `poc/html_email_parser.py` | HTML-aware email parsing pipeline         |
| `poc/triage.py`            | Triage filtering logic                    |
| `poc/summarize.py`         | Claude-powered conversation summarization |

### A.3 Test Coverage

95 tests across two test files:

- `tests/test_email_parser.py` — 60 tests covering plain-text pipeline and shared cleanup functions
- `tests/test_html_email_parser.py` — 35 tests covering HTML-aware pipeline

See [Email Parsing & Content Extraction](email_stripping.md) for detailed test categories.

### A.4 PoC Metrics

| Metric                                     | Value         |
| ------------------------------------------ | ------------- |
| Emails processed in production audit       | 3,752         |
| Emails with content changes after cleaning | 3,420 (91.2%) |
| Average character reduction                | 58.0%         |
| New empty results from HTML pipeline       | 0             |
| Processing time per email                  | ~1.3ms        |

---

*This document is a living specification. As channel-specific child PRDs are developed and as the Conversations PRD, AI Learning & Classification PRD, and Contact Intelligence PRD evolve, sections will be updated to reflect design decisions, scope adjustments, and lessons learned.*
