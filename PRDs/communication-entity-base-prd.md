# Communication — Entity Base PRD

**Version:** 1.0
**Last Updated:** 2026-02-23
**Status:** Draft
**Product PRD:** [CRMExtender Product PRD]

---

## 1. Entity Definition

### 1.1 Purpose

Communication is the atomic unit of interaction in CRMExtender — a single email, SMS message, phone call, video meeting, in-person meeting, or user-entered note. Every intelligence layer in the platform (conversation grouping, AI summarization, relationship scoring, engagement analytics) consumes Communications as raw input.

Communications normalize all interaction types to a channel-agnostic common schema: timestamp, channel, direction, participants, content, attachments, and source metadata. Downstream systems never need to know which channel a communication arrived from.

### 1.2 Design Goals

- **Channel-agnostic common schema** — All communication types normalize to the same entity structure. Cross-channel queries ("show me all interactions with Bob last month") work without assembling data from separate systems.
- **Provider adapter pattern** — External communication sources (Gmail, Outlook, Twilio, etc.) integrate through a uniform adapter interface. The rest of the platform is provider-agnostic. Channel-specific details live in child PRDs.
- **Published Summary** — Every Communication produces a rich text summary published to its parent Conversation's timeline. The Communication owns the summary; the Conversation references it by reference, not copy.
- **Contact-centric** — Every participant must be resolved to a CRM contact. Unknown identifiers trigger identity resolution workflows. Pending identification does not block processing.
- **Triage before intelligence** — A configurable pipeline filters automated notifications, marketing emails, and unknown-source messages before they consume AI resources. Filtered communications are retained and reviewable — nothing is silently discarded.
- **Event-sourced history** — All mutations are stored as immutable events for audit trails, point-in-time reconstruction, and compliance.

### 1.3 Performance Targets

| Metric                                          | Target  |
| ----------------------------------------------- | ------- |
| Communication list load (default view, 50 rows) | < 200ms |
| Communication detail page load                  | < 200ms |
| Incremental sync (0–20 new messages)            | < 5s    |
| Initial sync (5,000 messages)                   | < 5 min |
| Full-text search response                       | < 300ms |

### 1.4 Core Fields

Fields are described conceptually. Data types and storage details are specified in the Communication Entity TDD.

**Editable column** declares how (or if) the user can modify each field:

- **Direct** — User edits this field inline on the detail page or edit form.
- **Override** — Field is computed by default but the user can manually override.
- **Via [sub-entity]** — The displayed value summarizes a related record. Editing opens the sub-entity's editor.
- **Computed** — Derived from other data. Not directly editable.
- **System** — Set and managed by the system. Never user-editable.

| Field               | Description                                                                                                                                             | Required                | Editable                              | Sortable | Filterable | Valid Values / Rules                                                                                           |
| ------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------- | ------------------------------------- | -------- | ---------- | -------------------------------------------------------------------------------------------------------------- |
| ID                  | Unique identifier. Prefixed ULID with `com_` prefix. Immutable.                                                                                         | Yes                     | System                                | No       | Yes        | Prefixed ULID                                                                                                  |
| Channel             | Communication medium. Protected system options.                                                                                                         | Yes                     | System (set on creation)              | Yes      | Yes        | `email`, `sms`, `mms`, `phone_recorded`, `phone_manual`, `video_recorded`, `video_manual`, `in_person`, `note` |
| Direction           | Whether the user sent, received, or mutually participated.                                                                                              | Yes                     | System (set on creation)              | Yes      | Yes        | `inbound`, `outbound`, `mutual`                                                                                |
| Timestamp           | When the communication occurred. Universal sequencing key for all timeline views. For synced: provider's send/receive time. For manual: user-specified. | Yes                     | Direct (manual entries only)          | Yes      | Yes        | Timestamp                                                                                                      |
| Subject             | Email subject line, meeting title, or user-provided subject. Display name field. NULL for SMS, most calls.                                              | No                      | Direct                                | Yes      | Yes        | Free text                                                                                                      |
| Body Preview        | First 200 characters of cleaned content. Used in list views and search results.                                                                         | No                      | Computed                              | No       | No         | Auto-generated from search_text                                                                              |
| Original Text   | Original plain text content as received from provider or entered by user. Includes quoted replies, signatures, boilerplate. Preserved for re-processing. Not displayed directly. | No | System | No | No | Preserved for re-processing |
| Original HTML   | Original HTML content as received from provider. Email channel only. Includes all formatting, quoted replies, signatures, boilerplate. Preserved for re-processing. | No | System | No | No | Email channel only |
| Cleaned HTML    | HTML content with channel-specific noise removed (quoted replies, signatures, boilerplate stripped) but formatting preserved (bold, italic, links, lists). What users see when reading the communication. | No | Computed | No | No | Output of content extraction pipeline |
| Search Text     | Plain text content with channel-specific noise removed. No formatting. What AI processes and full-text search indexes. | No | Computed | No | No | Derived from cleaned_html (tags stripped) |
| Source              | How the communication entered the system.                                                                                                               | Yes                     | System                                | Yes      | Yes        | `synced`, `manual`, `imported`                                                                                 |
| Provider Account ID | The provider account that captured this communication.                                                                                                  | No                      | System                                | No       | Yes        | FK to provider_accounts. NULL for manual entries.                                                              |
| Provider Message ID | Provider's unique message identifier. Used for deduplication.                                                                                           | No                      | System                                | No       | No         | UNIQUE per provider account                                                                                    |
| Provider Thread ID  | Provider's thread/conversation identifier. Used for automatic conversation formation.                                                                   | No                      | System                                | No       | No         | Provider-specific format                                                                                       |
| Conversation ID     | FK to parent conversation. NULL for unassigned communications.                                                                                          | No                      | Direct                                | No       | Yes        | FK to conversations                                                                                            |
| Triage Result       | NULL = passed triage. Non-NULL = filtered with reason.                                                                                                  | No                      | Override (via triage override action) | Yes      | Yes        | `automated_sender`, `automated_subject`, `marketing_content`, `no_known_contacts`, `user_filtered`             |
| Triage Reason       | Human-readable explanation of the triage decision.                                                                                                      | No                      | System                                | No       | No         | Free text                                                                                                      |
| Duration Seconds    | Duration for calls and meetings. NULL for text-based communications.                                                                                    | No                      | Direct (manual entries only)          | Yes      | Yes        | Positive integer                                                                                               |
| Has Attachments     | Whether this communication has file attachments. Denormalized for fast filtering.                                                                       | No                      | System                                | No       | Yes        | Boolean                                                                                                        |
| Attachment Count    | Count of attached files. Denormalized for display.                                                                                                      | No                      | System                                | No       | No         | Non-negative integer                                                                                           |
| Status              | Record lifecycle status. Active or archived.                                                                                                            | Yes, defaults to active | System                                | Yes      | Yes        | `active`, `archived`                                                                                           |
| Created By          | User who created the record (NULL for auto-synced).                                                                                                     | No                      | System                                | No       | Yes        | Reference to User                                                                                              |
| Created At          | Record creation timestamp.                                                                                                                              | Yes                     | System                                | Yes      | Yes        | Timestamp                                                                                                      |
| Updated At          | Last modification timestamp.                                                                                                                            | Yes                     | System                                | Yes      | Yes        | Timestamp                                                                                                      |

### 1.5 Behavior-Managed Summary Fields

These fields are stored on the communications table but **not registered in the field registry** (same pattern as Notes content fields). They are managed by the Summary generation behavior and described in the Published Summary Sub-PRD.

| Field                       | Description                                                                   |
| --------------------------- | ----------------------------------------------------------------------------- |
| Summary JSON                | Editor-native rich text document format. Source of truth for re-editing.      |
| Summary HTML                | Pre-rendered HTML. What the Conversation timeline renders.                    |
| Summary Text                | Plain text for FTS indexing and AI consumption.                               |
| Summary Source              | How the summary was created: `ai_generated`, `user_authored`, `pass_through`. |
| Current Summary Revision ID | FK to the active summary revision.                                            |
| Summary Revision Count      | Count of summary revisions.                                                   |

### 1.6 Computed / Derived Fields

| Field            | Description                             | Editable | Derivation Logic                                                                                    |
| ---------------- | --------------------------------------- | -------- | --------------------------------------------------------------------------------------------------- |
| Body Preview     | First 200 characters of cleaned content | Computed | Auto-truncated from search_text on save.                                                          |
| Cleaned HTML | Noise-removed HTML content with formatting preserved | Computed | Output of channel-specific content extraction behavior. Re-derivable from original_text/original_html. |
| Search Text  | Noise-removed plain text for AI and search | Computed | Derived from cleaned_html by stripping all HTML tags. |
| Has Attachments  | Whether attachments exist               | Computed | Denormalized from attachment count > 0.                                                             |
| Attachment Count | Number of attachments                   | Computed | Count of attachment records for this communication.                                                 |

### 1.7 Registered Behaviors

Per Custom Objects PRD, the Communication system object type registers these specialized behaviors:

| Behavior                            | Trigger                                        | Description                                                                                                                     |
| ----------------------------------- | ---------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------- |
| Channel-specific content extraction | On sync, on creation                           | Dispatches to the appropriate channel parser to produce cleaned_html (noise removed, formatting preserved) and search_text (plain text for AI and search) from original content. Defined in channel-specific child PRDs. |
| Summary generation                  | On creation, on content update, on manual edit | Produces the Published Summary from search_text. Creates a new summary revision. See Published Summary Sub-PRD.               |
| Triage classification               | On sync, on creation                           | Runs the multi-layer triage pipeline to classify communications as real interactions vs. automated noise. See Triage Sub-PRD.   |
| Participant resolution              | On sync, on creation                           | Extracts participant identifiers and triggers Contact Intelligence for resolution. See Participant Resolution Sub-PRD.          |
| Segmentation                        | On user action                                 | User selects a content portion and assigns it to a different conversation. Defined in the Conversations PRD.                    |

---

## 2. Entity Relationships

### 2.1 Contacts (Participants)

**Nature:** Many-to-many, via system Relation Type
**Ownership:** Communication entity (Relation Type: `communication_participants`)
**Description:** Every communication has one or more participants. Each participant link carries metadata: role (sender, to, cc, bcc, participant), address (the identifier used in this communication), display name, and an account-owner flag. Participants are resolved to Contact records via the Contact Intelligence system. See Participant Resolution Sub-PRD.

### 2.2 Conversations

**Nature:** Many-to-one, FK column
**Ownership:** Conversations PRD
**Description:** A communication belongs to at most one conversation via the `conversation_id` FK. NULL for unassigned communications. The conversation groups related communications into coherent threads. This is an FK column rather than a Relation Type because it is strictly many:1 and carries no metadata.

### 2.3 Attachments

**Nature:** One-to-many, behavior-managed
**Ownership:** Communication entity
**Description:** A communication can have zero or more attached files. Attachments are behavior-managed records (not a separate object type) with filename, MIME type, size, and storage reference. Storage strategy varies by source: on-demand download from provider (Phase 1), object storage (Phase 2+). Call/video recordings are attachments; their transcripts become cleaned_html and search_text.

### 2.4 Events

**Nature:** Indirect, via conversations
**Ownership:** Events PRD
**Description:** Calendar events link to conversations (which contain communications) through the Event→Conversation Relation Type. Meeting follow-up emails and pre-meeting coordination threads are correlated with their triggering events.

### 2.5 Notes

**Nature:** Many-to-many, via universal attachment
**Ownership:** Notes PRD
**Description:** Notes attach to Communication records as supplementary commentary. A note on a communication represents an observation about the interaction (e.g., "Bob seemed hesitant about pricing"), not the interaction itself.

### 2.6 Companies

**Nature:** Indirect, via contact participants
**Ownership:** Company Management PRD
**Description:** Communications link to companies through contact participants — a communication involves contacts, and contacts have employment records at companies. Email domain extraction during sync also triggers company auto-creation via the Company Domain Resolution Sub-PRD.

---

## 3. Channel Types

### 3.1 System Channel Options

The `channel` field has protected system options:

| Channel          | Display Name             | Source                      | Content Type       | Threading           | Parsing | Child PRD               |
| ---------------- | ------------------------ | --------------------------- | ------------------ | ------------------- | ------- | ----------------------- |
| `email`          | Email                    | Auto-synced                 | Rich (text + HTML) | Provider thread IDs | Heavy   | Email Provider Sync PRD |
| `sms`            | SMS                      | Auto-synced                 | Short text         | None                | Minimal | SMS/MMS PRD             |
| `mms`            | MMS                      | Auto-synced                 | Text + media       | None                | Minimal | SMS/MMS PRD             |
| `phone_recorded` | Phone Call (Recorded)    | Auto-synced + transcription | Transcript         | None                | Some    | Voice/VoIP PRD          |
| `phone_manual`   | Phone Call (Logged)      | Manual entry                | User-written notes | None                | None    | —                       |
| `video_recorded` | Video Meeting (Recorded) | Auto-synced + transcription | Transcript         | None                | Some    | Video Meetings PRD      |
| `video_manual`   | Video Meeting (Logged)   | Manual entry                | User-written notes | None                | None    | —                       |
| `in_person`      | In-Person Meeting        | Manual entry                | User-written notes | None                | None    | —                       |
| `note`           | Note                     | Manual entry                | User-written notes | None                | None    | —                       |

### 3.2 Boundary with the Notes PRD

Communications and Notes are distinct system object types:

- **Communications** record interactions that happened — they have participants, timestamps, and represent exchanges between people.
- **Notes** capture observations, commentary, and knowledge — they have a single author and attach *to* entities as supplementary commentary.

Manually logged interactions (unrecorded phone calls, in-person meetings) create Communication records. The user provides participants, timestamp, and what was discussed. This is an interaction record. A Note attached to that Communication might say "Bob seemed hesitant — follow up with a discount offer." The Note is commentary about the interaction, not the interaction itself.

---

## 4. Lifecycle

### 4.1 Statuses

| Status     | Description                                                                                                                                                          |
| ---------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `active`   | Normal operating state. Visible in views and search. May have a triage_result that filters it from default intelligence processing, but the record itself is active. |
| `archived` | Soft-deleted. Excluded from default queries. All data preserved. Recoverable via unarchive.                                                                          |

### 4.2 Transitions

| From       | To         | Trigger                                                   |
| ---------- | ---------- | --------------------------------------------------------- |
| `active`   | `archived` | User archives, or message deleted at provider during sync |
| `archived` | `active`   | User unarchives                                           |

### 4.3 Creation Sources

| Source             | Initial Status | Notes                                                                                   |
| ------------------ | -------------- | --------------------------------------------------------------------------------------- |
| Provider sync      | `active`       | Auto-captured from Gmail, Outlook, SMS provider, etc. Triage pipeline runs immediately. |
| Manual entry       | `active`       | User creates via UI. Triage is bypassed — user-entered content is always real.          |
| Import             | `active`       | Bulk import from CSV or migration. Triage may run depending on import configuration.    |
| Calendar-triggered | `active`       | Scheduled meeting from calendar auto-creates a placeholder; user adds notes after.      |

---

## 5. Key Processes

### KP-1: Communication Arrives via Provider Sync

**Trigger:** Incremental sync detects a new communication at the provider (email, SMS, etc.).

**Step 1 — Fetch & normalize:** Provider adapter fetches the raw communication and normalizes it to the common schema (timestamp, channel, direction, original_text, original_html, provider_message_id, provider_thread_id).

**Step 2 — Deduplication:** System checks provider_account_id + provider_message_id. If duplicate, skip. If new, create Communication record with `source = 'synced'`.

**Step 3 — Content extraction:** Channel-specific content extraction behavior fires, producing cleaned_html and search_text from original_text/original_html. Body_preview auto-generated.

**Step 4 — Participant resolution:** Participant identifiers are extracted and submitted to Contact Intelligence for resolution. Participant relation instances created (may reference placeholder contacts until resolution completes).

**Step 5 — Triage classification:** Triage pipeline evaluates the communication. If filtered, triage_result and triage_reason are set. Communication is retained but excluded from AI processing.

**Step 6 — Summary generation:** If triage passed, the Published Summary behavior fires. AI-generated for long content, pass-through for short content.

**Step 7 — Conversation assignment:** The Conversations PRD's auto-assignment logic runs, grouping the communication into an existing or new conversation based on provider_thread_id, participants, and timing.

### KP-2: User Creates a Manual Communication

**Trigger:** User clicks "Log Communication" or equivalent action in the UI.

**Step 1 — Channel selection:** User selects the channel type (phone_manual, video_manual, in_person, note).

**Step 2 — Data entry:** User provides: participants (select existing contacts or create new), timestamp (defaults to now), duration (optional), subject (optional), content (what was discussed), attachments (optional), conversation assignment (optional).

**Step 3 — Record creation:** Communication created with `source = 'manual'`, `provider_account_id = NULL`. Triage is bypassed entirely.

**Step 4 — Summary:** For user-authored channels, the user's content IS the Published Summary. Summary revision created immediately.

### KP-3: Browsing and Finding Communications

**Trigger:** User navigates to the Communications entity in the Entity Bar or views a conversation timeline.

**Step 1 — Default view loads:** Content Panel displays the user's default communication view. Grid shows columns per view configuration. Communications sorted by timestamp descending.

**Step 2 — Filtering:** User applies filters (channel, direction, triage status, date range, contact, conversation, account). Filters apply immediately.

**Step 3 — Searching:** Full-text search across subject and search_text. Subject weighted higher for relevance.

**Step 4 — Selection:** User clicks a communication row. Detail Panel opens showing full content, participants, attachments, and summary.

### KP-4: Viewing a Communication's Full Record

**Trigger:** User clicks a communication in a view or conversation timeline.

**Step 1 — Identity Card loads:** Channel icon, timestamp, direction, subject, and participant summary.

**Step 2 — Content display:** cleaned_html displayed as the primary content with formatting preserved. "View Original" expander shows original_text for debugging.

**Step 3 — Published Summary:** Summary card shows the current summary with source badge (AI-generated, user-authored, pass-through). Edit and re-generate actions available.

**Step 4 — Participants:** List of participants with roles, contact links, and resolution status.

**Step 5 — Attachments:** File list with download actions. Recordings show playback controls.

**Step 6 — Metadata:** Provider account, sync details, triage decision (if filtered), conversation assignment, event history.

### KP-5: Archiving and Restoring a Communication

**Trigger:** User archives from detail page or list view, or message deleted at provider during sync.

**Step 1 — Archive:** Communication status set to `archived`. Removed from default views. Conversation metadata recomputed if the communication was assigned.

**Step 2 — Restore:** User navigates to archived communications view, selects the record, and unarchives. Status restored to `active`. Conversation membership restored.

---

## 6. Action Catalog

### 6.1 Create Communication (Manual)

**Supports processes:** KP-2 (full flow)
**Trigger:** User initiates manual communication entry.
**Inputs:** Channel, participants, timestamp, duration (optional), subject (optional), content (optional), attachments (optional), conversation (optional).
**Outcome:** New Communication record with source = `manual`. Summary created from user content. Participants linked.
**Business Rules:** Manual channels bypass triage. At least one participant (besides the user) is required.

### 6.2 View Communication

**Supports processes:** KP-3 (step 4), KP-4 (full flow)
**Trigger:** User navigates to a communication's detail page.
**Inputs:** Communication ID.
**Outcome:** Full record displayed: content, participants, attachments, summary, metadata.
**Business Rules:** Renders within 200ms. Filtered communications are viewable with triage reason displayed.

### 6.3 Edit Communication

**Supports processes:** KP-4
**Trigger:** User modifies fields on a manual communication or edits conversation assignment.
**Inputs:** Updated field values.
**Outcome:** Record updated. Event emitted.
**Business Rules:** Synced communications have limited editability (conversation assignment, triage override). Manual communications are fully editable.

### 6.4 Archive Communication

**Supports processes:** KP-5 (step 1)
**Trigger:** User archives, or provider sync detects deletion.
**Inputs:** Communication ID, optional reason.
**Outcome:** Status set to `archived`. Removed from active lists. Conversation metadata recomputed.
**Business Rules:** Reversible via unarchive.

### 6.5 Attachments

**Supports processes:** KP-4 (step 5)
**Trigger:** Synced with communication, or user uploads on manual entry.
**Inputs:** File data, metadata (filename, MIME type, size).
**Outcome:** Attachment record created. Storage reference set per storage strategy (on-demand or object storage).
**Business Rules:** Recordings and transcripts are related — transcript becomes cleaned_html and search_text, recording becomes attachment.

### 6.6 Published Summary

**Summary:** Every Communication produces a rich text summary published to its parent Conversation's timeline. AI-generated for synced long-form content (emails, transcripts), user-authored for manual entries, pass-through for short messages. Full revision history enables audit trail reconstruction. Four-stage content pipeline: original_text/original_html → cleaned_html → search_text → Published Summary.
**Sub-PRD:** [communication-published-summary-prd.md]

### 6.7 Provider & Sync Framework

**Summary:** External communication sources integrate through a uniform provider adapter interface: authenticate, fetch, normalize, track sync position. Provider accounts represent connected services with encrypted credentials, sync cursors, and status management. Supports initial sync (historical batch), incremental sync (delta), and manual sync. Personal and shared (tenant-level) accounts with dual attribution for shared inboxes. Sync reliability with retry, deduplication, and audit logging.
**Sub-PRD:** [communication-provider-sync-prd.md]

### 6.8 Participant Resolution

**Summary:** Communication participants are modeled as a system Relation Type (Communication→Contact) with metadata for role, address, display name, and account-owner flag. Every participant must be resolved to a CRM contact via the Contact Intelligence system. Unrecognized identifiers trigger resolution workflows. Pending identification does not block processing. Cross-channel contact unification enables a single contact's communications to be viewed across all channels.
**Sub-PRD:** [communication-participant-resolution-prd.md]

### 6.9 Triage & Intelligent Filtering

**Summary:** Multi-layer pipeline classifying communications as real interactions vs. automated/marketing noise before AI processing. Layer 1: channel-specific heuristics (automated sender patterns, subject patterns, marketing content detection — defined in channel child PRDs). Layer 2: known-contact gate (at least one non-owner participant must be a known CRM contact). Layer 3: user-defined rules (future). Filtered communications are tagged with reason and retained — never deleted. Users can override any triage decision, which queues the communication for AI processing.
**Sub-PRD:** [communication-triage-prd.md]

---

## 7. Cross-Cutting Concerns

### 7.1 Multi-Account Management

Multiple provider accounts produce a single, chronologically sorted communication feed. Each Communication is tagged with its provider_account_id, enabling unified timeline views (all accounts, all channels), account-filtered views, and channel-filtered views. Same real-world thread synced via two accounts currently creates separate records; conversation-level deduplication is handled by the Conversations PRD.

### 7.2 Timestamp as the Universal Sequencing Key

All communications across all channels are sequenced by `timestamp`. This enables a unified timeline: emails, SMS, phone calls, and meetings from the same conversation appear in chronological order regardless of channel. The Conversations PRD defines grouping; this entity provides the sequencing foundation.

### 7.3 Privacy, Security & Compliance

- **Minimum necessary access** — Read-only OAuth scopes for all providers until send capability is needed.
- **Encrypted at rest and in transit** — TLS 1.2+ for all API calls; database encryption in production.
- **Credential isolation** — OAuth tokens and API keys stored encrypted, never in logs.
- **Tenant isolation** — Schema-per-tenant in PostgreSQL per Custom Objects PRD.
- **GDPR** — Full export via API; cascade deletion (communication + events + attachments); standard export formats.
- **AI data handling** — Only search_text is sent to AI, not raw HTML, attachments, or full threads. AI responses stored in CRM, not retained by AI provider.

### 7.4 Data Retention

- Communication records retained indefinitely by default (configurable per tenant).
- Event history retained indefinitely with periodic snapshots.
- Sync audit logs retained 90 days by default.
- Attachments: on-demand from provider (Phase 1), object storage (Phase 2+).

---

## 8. Open Questions

1. **Attachment storage model** — Store all in object storage (high cost, provider-independent) vs. on-demand download (requires continued provider access)? Hybrid model worth the complexity?

2. **Real-time sync infrastructure** — Gmail Pub/Sub and Outlook webhooks need public callbacks. Cloud function, dedicated endpoint, or message queue?

3. **Email sending from CRM** — Support sending (elevated OAuth scopes)? Adds workflow value but increases security surface.

4. **Communication merge/split** — When the same interaction is synced from two accounts, what is the merge workflow?

5. **Opt-out granularity** — Can users exclude specific contacts, channels, or accounts from AI processing? What does "exclude" mean operationally?

6. **Slack/Teams integration model** — How do workspace/channel/thread hierarchies map to our channel model?

---

## 9. Design Decisions

### Why a system object type instead of a standalone table?

Making Communication a system object type gives it automatic participation in Views, Data Sources, event sourcing, field registry, permissions, audit trails, and the API surface. A standalone table would require hand-building each integration. The cost of fitting Communications into the framework is low and every framework enhancement automatically applies.

### Why a participant Relation Type instead of from_address/to_addresses columns?

Flat address columns cannot answer "show all communications involving Bob" without parsing concatenated strings. The Relation Type provides JOIN-based queries, per-participant metadata, bidirectional navigation, and participation in Views and Data Sources.

### Why conversation_id as an FK column instead of a Relation Type?

The Communication→Conversation link is strictly many:1, carries no metadata, and is not navigable from the Conversation side in the same way as Event→Contact. An FK column is proportional to the complexity.

### Why separate original_text, original_html, cleaned_html, and search_text?

Four content fields serve distinct purposes: original_text and original_html preserve the originals for re-processing if the extraction pipeline improves. cleaned_html is the noise-removed HTML with formatting preserved — bold, italic, links, lists all intact — for native reading in the UI. search_text is the plain text extraction of cleaned_html (all tags stripped) for AI processing and full-text search indexing. The cleaning pipeline produces cleaned_html first, then derives search_text from it by stripping tags.

### Why channel-specific child PRDs instead of one monolithic document?

Email alone has 300+ lines of provider-specific details. SMS, voice, and video will each have comparable complexity. Dedicated child PRDs ensure maintainability and independent evolution.

### Why is "note" a channel type rather than using the Notes system?

The `note` channel type represents a user-recorded interaction with participants and a timestamp. Notes PRD represents supplementary commentary and knowledge that attaches to entities. Different purposes, different object types.

### Why does each Communication own its Published Summary?

The Communication is the source of truth for what was said. Communication-owned summaries mean: each channel produces the most appropriate summary, the summary is available before conversation assignment, updating propagates automatically, and conversations consume pre-distilled summaries rather than re-processing raw content.

### Why rich text summaries instead of plain text?

Summaries have natural structure: key points, decisions, action items. Plain text loses this. Rich text (same editor and storage as Notes) preserves formatting and ensures a consistent editing experience.

---

## Related Documents

| Document                                                                      | Relationship                                                             |
| ----------------------------------------------------------------------------- | ------------------------------------------------------------------------ |
| [Communication Entity TDD](communication-entity-tdd.md)                       | Technical decisions for communication implementation                     |
| [Published Summary Sub-PRD](communication-published-summary-prd.md)           | Summary generation, revision history, content pipeline                   |
| [Provider & Sync Framework Sub-PRD](communication-provider-sync-prd.md)       | Provider accounts, adapter architecture, sync modes                      |
| [Participant Resolution Sub-PRD](communication-participant-resolution-prd.md) | Participant Relation Type, contact resolution, cross-channel unification |
| [Triage Sub-PRD](communication-triage-prd.md)                                 | Intelligent filtering pipeline                                           |
| [Conversations PRD](conversations-prd.md)                                     | Conversation grouping, timeline rendering, AI intelligence               |
| [Contact Entity Base PRD](contact-entity-base-prd.md)                         | Contact identity resolution, employment linkage                          |
| [Company Entity Base PRD](company-entity-base-prd.md)                         | Domain extraction triggers company creation                              |
| [Custom Objects PRD](custom-objects-prd.md)                                   | Unified object model, field registry, relation framework                 |
| [Email Provider Sync PRD](email-provider-sync-prd.md)                         | Gmail, Outlook, IMAP adapters and email-specific parsing                 |
| [Notes PRD](notes-prd.md)                                                     | Shared rich text content architecture                                    |
| [Master Glossary](glossary.md)                                                | Term definitions                                                         |

### Channel-Specific Child PRDs

| Child PRD                                             | Scope                                                                 |
| ----------------------------------------------------- | --------------------------------------------------------------------- |
| [Email Provider Sync PRD](email-provider-sync-prd.md) | Gmail, Outlook, IMAP adapters; email parsing; email-specific triage   |
| SMS/MMS PRD (future)                                  | SMS provider adapters; phone number resolution; MMS media             |
| Voice/VoIP PRD (future)                               | Call recording; transcription pipeline; call metadata                 |
| Video Meetings PRD (future)                           | Zoom/Teams/Meet integration; transcript capture; recording management |
