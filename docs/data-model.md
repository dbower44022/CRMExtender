# Data Model & Database Design

This document describes the persistent data layer that backs the CRM
Extender email pipeline.  It covers the SQLite schema, every table and
column, the relationships between entities, the serialization layer that
maps Python dataclasses to database rows, the indexing strategy, and the
data flows that populate and query the database.

**Implementation files:**

| File | Role |
|------|------|
| `poc/database.py` | Connection management, schema DDL, WAL/FK pragmas |
| `poc/models.py` | Dataclasses with `to_row()` / `from_row()` serialization |
| `poc/sync.py` | Sync orchestration: writes to DB, reads from DB for display |
| `poc/config.py` | `DB_PATH` setting (default `data/crm_extender.db`) |

---

## Architecture Overview

```
                         ┌──────────────────────────────────┐
                         │         SQLite Database           │
                         │   data/crm_extender.db (WAL mode) │
                         └──────────────┬───────────────────┘
                                        │
                ┌───────────────────────┼───────────────────────┐
                │                       │                       │
          ┌─────┴─────┐         ┌──────┴───────┐        ┌─────┴──────┐
          │  sync.py   │         │  models.py   │        │ database.py │
          │            │         │              │        │             │
          │ Writes:    │         │ to_row()     │        │ init_db()   │
          │  accounts  │         │ from_row()   │        │ get_conn()  │
          │  contacts  │         │ Enum maps    │        │ Schema DDL  │
          │  emails    │         │              │        │ Index DDL   │
          │  convos    │         └──────────────┘        └─────────────┘
          │  topics    │
          │  sync_log  │
          │            │
          │ Reads:     │
          │  display   │
          │  processing│
          └────────────┘
```

The database is the single source of truth after the first sync.
Subsequent runs read state from it (account registration, sync cursors,
existing conversations) and write incremental changes back.  The
in-memory `Conversation` / `ParsedEmail` dataclasses are reconstructed
from DB rows when needed for triage, summarization, or display.

---

## Connection Management

`database.py` provides two entry points:

**`init_db(db_path=None)`** — Creates the database file, parent
directories, all tables (`CREATE TABLE IF NOT EXISTS`), and all indexes.
Called once at startup in `__main__.py` Step 0.

**`get_connection(db_path=None)`** — Context manager that yields a
`sqlite3.Connection` with:

- `journal_mode=WAL` — Write-Ahead Logging for concurrent reads during
  sync writes.
- `foreign_keys=ON` — Enforces all `REFERENCES` / `ON DELETE` constraints.
- `row_factory=sqlite3.Row` — Rows are returned as dict-like objects,
  enabling column access by name.
- Auto-commit on clean exit, rollback on exception.

Both functions default to `config.DB_PATH` (`data/crm_extender.db`),
overridable via the `POC_DB_PATH` environment variable.

---

## Entity-Relationship Diagram

```
┌──────────────────┐
│  email_accounts   │
│──────────────────│
│ PK id             │
│    provider       │
│    email_address   │     ┌───────────────────┐
│    sync_cursor     │     │     contacts       │
│    ...             │     │───────────────────│
└────────┬─────────┘     │ PK id              │
         │                │    email (UNIQUE)   │
         │ 1              │    name             │
         │                │    source           │
         ▼ N              │    ...              │
┌──────────────────┐     └─────────┬─────────┘
│  conversations    │              │
│──────────────────│              │ 0..1
│ PK id             │              │
│ FK account_id     │──────────────┼──────────────────────┐
│    provider_      │              │                      │
│     thread_id     │              │                      │
│    subject        │     ┌────────┴──────────┐           │
│    ai_summary     │     │  conversation_    │           │
│    ai_status      │     │   participants    │           │
│    triage_result  │     │──────────────────│           │
│    ...            │     │ PK conv_id, email │           │
└──┬────────┬──────┘     │ FK contact_id     │           │
   │        │             │    message_count   │           │
   │        │             │    first_seen_at   │           │
   │        │             │    last_seen_at    │           │
   │        │             └───────────────────┘           │
   │        │                                              │
   │        │ N                                            │
   │        ▼                                              │
   │  ┌──────────────────┐                                │
   │  │     emails        │                                │
   │  │──────────────────│                                │
   │  │ PK id             │                                │
   │  │ FK account_id     │                                │
   │  │ FK conversation_id│                                │
   │  │    provider_      │                                │
   │  │     message_id    │                                │
   │  │    sender_address │                                │
   │  │    date           │                                │
   │  │    body_text      │                                │
   │  │    direction      │                                │
   │  │    ...            │                                │
   │  └────────┬─────────┘                                │
   │           │ N                                         │
   │           ▼                                           │
   │  ┌──────────────────┐                                │
   │  │ email_recipients  │                                │
   │  │──────────────────│                                │
   │  │ PK email_id,      │                                │
   │  │    address, role   │                                │
   │  │    name            │                                │
   │  └──────────────────┘                                │
   │                                                       │
   │ N (via conversation_topics)                           │
   ▼                                                       │
┌──────────────────┐     ┌───────────────────┐            │
│     topics        │     │ conversation_     │            │
│──────────────────│     │   topics          │            │
│ PK id             │◄────│──────────────────│            │
│    name (UNIQUE)  │     │ PK conv_id,       │            │
│    created_at     │     │    topic_id       │            │
└──────────────────┘     │    confidence      │            │
                          │    source          │            │
                          └───────────────────┘            │
                                                            │
                          ┌───────────────────┐            │
                          │     sync_log       │            │
                          │───────────────────│            │
                          │ PK id              │────────────┘
                          │ FK account_id      │
                          │    sync_type       │
                          │    status          │
                          │    cursor_before   │
                          │    cursor_after    │
                          │    ...             │
                          └───────────────────┘
```

### Relationship Summary

| Parent | Child | Cardinality | FK Column | On Delete |
|--------|-------|-------------|-----------|-----------|
| `email_accounts` | `conversations` | 1:N | `account_id` | CASCADE |
| `email_accounts` | `emails` | 1:N | `account_id` | CASCADE |
| `email_accounts` | `sync_log` | 1:N | `account_id` | CASCADE |
| `conversations` | `emails` | 1:N | `conversation_id` | SET NULL |
| `conversations` | `conversation_participants` | 1:N | `conversation_id` | CASCADE |
| `conversations` | `conversation_topics` | 1:N | `conversation_id` | CASCADE |
| `contacts` | `conversation_participants` | 0..1:N | `contact_id` | SET NULL |
| `topics` | `conversation_topics` | 1:N | `topic_id` | CASCADE |
| `emails` | `email_recipients` | 1:N | `email_id` | CASCADE |

---

## Table Reference

### 1. `email_accounts`

Tracks connected email accounts and their synchronization state.  One
row per provider+address combination.  The pipeline creates an account
row the first time a user authenticates, and updates it after every sync.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | TEXT | **PK** | UUID v4.  Generated by `sync.register_account()`. |
| `provider` | TEXT | NOT NULL | Email provider identifier.  Currently always `'gmail'`.  Designed for future `'outlook'`, `'imap'` values. |
| `email_address` | TEXT | NOT NULL | The account owner's email address, lowercased.  Retrieved from the Gmail profile API (`users.getProfile`). |
| `display_name` | TEXT | | Optional human-readable name.  Currently set to NULL; reserved for future use. |
| `auth_token_path` | TEXT | | Filesystem path to the OAuth token file (e.g. `credentials/token.json`).  Keeps actual tokens out of the database. |
| `sync_cursor` | TEXT | | Provider-specific opaque sync position.  For Gmail this is the `historyId` (a numeric string).  For Outlook it would be a `deltaLink` URL.  For IMAP it would be `UIDVALIDITY:lastUID`.  NULL before initial sync completes. |
| `last_synced_at` | TEXT | | ISO 8601 timestamp of the most recent successful sync completion. |
| `initial_sync_done` | INTEGER | DEFAULT 0 | Boolean flag (0/1).  Set to 1 when the first full sync completes.  The pipeline uses this to decide between initial sync (full fetch) and incremental sync (history-based). |
| `backfill_query` | TEXT | DEFAULT `'newer_than:90d'` | Gmail search query used during initial sync.  Controls how far back the first sync reaches.  Stored per-account so different accounts can have different backfill depths. |
| `created_at` | TEXT | NOT NULL | ISO 8601 timestamp of account registration. |
| `updated_at` | TEXT | NOT NULL | ISO 8601 timestamp of last modification. |

**Unique constraint:** `(provider, email_address)` — prevents duplicate
registration of the same account.

**Populated by:** `sync.register_account()` (INSERT), `sync.initial_sync()` /
`sync.incremental_sync()` (UPDATE of `sync_cursor`, `last_synced_at`,
`initial_sync_done`).

### 2. `conversations`

Groups emails into threaded exchanges.  One row per provider thread per
account.  This is the central table that most queries target — it holds
both the system-level metadata and the AI-generated analysis fields.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | TEXT | **PK** | UUID v4.  Generated when the conversation is first stored. |
| `account_id` | TEXT | NOT NULL, FK → `email_accounts(id)` | Which account this conversation belongs to.  ON DELETE CASCADE. |
| `provider_thread_id` | TEXT | | The provider's native thread identifier.  For Gmail this is the `threadId` from the API.  For Outlook it would be `conversationId`.  NULL for IMAP where threading is reconstructed from Message-ID/References headers. |
| `subject` | TEXT | | Subject line from the first email in the thread.  Defaults to `'(no subject)'` if missing. |
| `status` | TEXT | DEFAULT `'active'` | System-level conversation status based on activity window.  Values: `'active'`, `'stale'`, `'closed'`.  Distinct from `ai_status` which is the AI's semantic classification.  Currently all conversations are set to `'active'` on creation. |
| `message_count` | INTEGER | DEFAULT 0 | Total number of email messages in this conversation.  Updated when new messages arrive during incremental sync.  Recomputed from `SELECT COUNT(*) FROM emails WHERE conversation_id = ?` on update. |
| `first_message_at` | TEXT | | ISO 8601 timestamp of the earliest email in the conversation.  Computed from `MIN(emails.date)`. |
| `last_message_at` | TEXT | | ISO 8601 timestamp of the most recent email.  Computed from `MAX(emails.date)`.  Used for sorting conversations (most recent first) in display and processing queries. |
| `ai_summary` | TEXT | | Claude-generated 2-4 sentence summary of the conversation.  NULL until the summarizer runs.  Written by `sync.process_conversations()` via `ConversationSummary.to_update_dict()`. |
| `ai_status` | TEXT | | AI classification of the conversation state.  Values: `'open'`, `'closed'`, `'uncertain'` (lowercased from Claude's OPEN/CLOSED/UNCERTAIN output).  NULL until summarized. |
| `ai_action_items` | TEXT | | JSON-serialized array of strings, each an action item extracted by Claude.  Example: `'["Follow up with Alice", "Send the report"]'`.  NULL if no action items or not yet summarized.  Serialized via `json.dumps()`, deserialized via `json.loads()`. |
| `ai_topics` | TEXT | | JSON-serialized array of strings, the raw topic list from Claude.  Example: `'["project timeline", "budget review"]'`.  This is the source-of-truth from the AI.  The normalized, queryable version lives in the `topics` / `conversation_topics` tables.  NULL until summarized. |
| `ai_summarized_at` | TEXT | | ISO 8601 timestamp of when the AI summary was last generated.  **Key behavior:** set to NULL when new messages arrive in the conversation (during incremental sync), which marks the conversation for re-processing in the next `process_conversations()` batch. |
| `triage_result` | TEXT | | NULL if the conversation passed triage (i.e. it's a real conversation worth summarizing).  Non-NULL values indicate why it was filtered out.  Values: `'no_known_contacts'`, `'automated_sender'`, `'automated_subject'`, `'marketing'`.  Mapped to/from the `FilterReason` enum via `filter_reason_to_db()` / `filter_reason_from_db()`. |
| `created_at` | TEXT | NOT NULL | ISO 8601 timestamp of conversation creation. |
| `updated_at` | TEXT | NOT NULL | ISO 8601 timestamp of last modification.  Updated on any write: new messages, triage, summarization. |

**Unique constraint:** `(account_id, provider_thread_id)` — one
conversation per provider thread per account.

**Populated by:** `sync._store_thread()` (INSERT on new thread, UPDATE
on incremental), `sync.process_conversations()` (UPDATE for
`triage_result` and `ai_*` fields).

**Design rationale — AI fields on the conversation row:**  There is a
strict 1:1 relationship between a conversation and its AI summary.
Storing the summary fields directly on the conversation row avoids a
JOIN for the most common query pattern: listing conversations with their
summaries.  The tradeoff is wider rows, but the cardinality is low
(hundreds to low thousands of conversations per account).

**Design rationale — per-account conversations:**  If two connected
accounts participate in the same email thread, each account has its own
conversation record.  This avoids the complexity of cross-account
merging.  A future `merged_conversation_id` column could link them.

### 3. `emails`

Individual email messages, provider-normalized.  Every email fetched
from Gmail (or future providers) gets one row here.  The email content
is preserved in full — both the cleaned plain text and the raw HTML —
even though the summarizer only uses the plain text.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | TEXT | **PK** | UUID v4.  Generated at insertion time. |
| `account_id` | TEXT | NOT NULL, FK → `email_accounts(id)` | Which account fetched this email.  ON DELETE CASCADE. |
| `conversation_id` | TEXT | FK → `conversations(id)` | Which conversation this email belongs to.  ON DELETE SET NULL (email survives if conversation is deleted, allowing re-threading). |
| `provider_message_id` | TEXT | NOT NULL | The provider's native message identifier.  For Gmail this is the message `id` from the API (e.g. `'18f3a4b2c1d0e5f6'`).  Used for deduplication and incremental sync lookups. |
| `subject` | TEXT | | The email's Subject header, decoded from RFC 2047 encoding. |
| `sender_address` | TEXT | NOT NULL | The sender's email address, lowercased.  Extracted from the `From` header. |
| `sender_name` | TEXT | | The sender's display name from the `From` header (e.g. `'Alice Smith <alice@example.com>'` → `'Alice Smith'`).  NULL if the From header contains only an address. |
| `date` | TEXT | | ISO 8601 timestamp of the email.  Parsed from the `Date` header, with fallback to Gmail's `internalDate` (milliseconds since epoch, converted to UTC).  Used for chronological sorting within conversations and for computing `conversations.first_message_at` / `last_message_at`. |
| `body_text` | TEXT | | The cleaned plain-text body of the email.  If the original email had only HTML, it is converted via `gmail_client._html_to_text()`.  Quote stripping (`email_parser.strip_quotes()`) is applied before storage, removing forwarded blocks, Outlook separators, "On ... wrote:" attributions, and mobile signatures.  The stored text is the full original (minus quotes) for display; further truncation for summarization happens at prompt-formatting time. |
| `body_html` | TEXT | | The raw HTML body of the email, preserved as-is from the provider.  Not used by the pipeline directly, but stored for potential future use (rich display, re-processing). |
| `snippet` | TEXT | | Short preview text from the Gmail API.  Used as a fallback when `body_text` is empty. |
| `header_message_id` | TEXT | | The RFC 5322 `Message-ID` header.  Currently NULL for Gmail (not extracted yet).  Reserved for IMAP thread reconstruction, where `Message-ID` / `References` / `In-Reply-To` chains are used to build threads from scratch. |
| `header_references` | TEXT | | The `References` header (space-separated list of Message-IDs).  Reserved for IMAP threading. |
| `header_in_reply_to` | TEXT | | The `In-Reply-To` header.  Reserved for IMAP threading. |
| `direction` | TEXT | | Whether the email is inbound or outbound relative to the account owner.  Values: `'inbound'`, `'outbound'`.  Computed by comparing `sender_address` to the account's `email_address`: if they match, it's outbound; otherwise inbound. |
| `is_read` | INTEGER | DEFAULT 0 | Boolean (0/1).  Currently always 0; reserved for future read-state tracking. |
| `has_attachments` | INTEGER | DEFAULT 0 | Boolean (0/1).  Currently always 0; reserved for future attachment detection. |
| `created_at` | TEXT | NOT NULL | ISO 8601 timestamp of when this row was inserted. |

**Unique constraint:** `(account_id, provider_message_id)` — prevents
storing the same message twice for the same account.  This is what makes
sync idempotent: `INSERT OR IGNORE` silently skips duplicates.

**Populated by:** `sync._store_thread()` via `ParsedEmail.to_row()`.
During initial sync, all emails from all fetched threads are inserted.
During incremental sync, only new messages (from `history.list`) are
inserted.

### 4. `email_recipients`

Normalizes the To/CC/BCC recipients of each email into separate rows.
This enables queries like "find all emails sent to alice@example.com"
without parsing delimited strings.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `email_id` | TEXT | NOT NULL, FK → `emails(id)` | Which email this recipient belongs to.  ON DELETE CASCADE. |
| `address` | TEXT | NOT NULL | The recipient's email address, lowercased. |
| `name` | TEXT | | The recipient's display name from the header.  Currently NULL (not yet extracted from address parsing); reserved for future enrichment. |
| `role` | TEXT | NOT NULL | The recipient type.  Values: `'to'`, `'cc'`, `'bcc'`.  Currently only `'to'` and `'cc'` are populated (Gmail API doesn't expose BCC to recipients). |

**Primary key:** `(email_id, address, role)` — composite.  The same
address can appear as both `to` and `cc` on the same email (unusual but
valid per RFC 5322), so `role` is included in the key.

**Populated by:** `sync._store_thread()` via `ParsedEmail.recipient_rows()`.
Uses `INSERT OR IGNORE` for idempotent re-insertion.

### 5. `contacts`

Known contacts from address books or manual entry.  Currently populated
from the Google People API (Google Contacts).  Contacts are global — not
per-account — because the same person may correspond with multiple
connected accounts.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | TEXT | **PK** | UUID v4. |
| `email` | TEXT | NOT NULL, **UNIQUE** | The contact's email address, lowercased.  The UNIQUE constraint enables UPSERT semantics: `INSERT ... ON CONFLICT(email) DO UPDATE`. |
| `name` | TEXT | | Display name from the contact source. |
| `source` | TEXT | | Where this contact came from.  Values: `'google_contacts'`, `'outlook_contacts'`, `'manual'`.  Currently always `'google_contacts'`. |
| `source_id` | TEXT | | The provider's native identifier for this contact.  For Google Contacts this is the People API resource name (e.g. `'people/c1234567890'`).  Enables future two-way sync. |
| `created_at` | TEXT | NOT NULL | ISO 8601 timestamp of first insertion. |
| `updated_at` | TEXT | NOT NULL | ISO 8601 timestamp of last update.  The UPSERT in `sync_contacts()` updates `name`, `source_id`, and `updated_at` on conflict. |

**Populated by:** `sync.sync_contacts()`, which fetches from the Google
People API and performs UPSERT operations.  One contact row per unique
email address, regardless of how many accounts reference that contact.

**Read by:** `sync.load_contact_index()`, which builds the in-memory
`email → KnownContact` lookup used by triage (known-contact gate) and
display (name resolution).

### 6. `conversation_participants`

Links email addresses to conversations, optionally matching them to
known contacts.  Every unique sender/recipient who appears in a
conversation gets a row here, regardless of whether they match a known
contact.  This enables queries like "which conversations involve
alice@example.com?" and "how active is each participant?"

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `conversation_id` | TEXT | NOT NULL, FK → `conversations(id)` | Which conversation.  ON DELETE CASCADE. |
| `email_address` | TEXT | NOT NULL | The participant's email address, lowercased.  Always populated, even without a contact match. |
| `contact_id` | TEXT | FK → `contacts(id)` | The matched contact's ID, if this address appears in the `contacts` table.  NULL if no match.  ON DELETE SET NULL (participant row survives if the contact is deleted). |
| `message_count` | INTEGER | DEFAULT 0 | How many messages this participant sent in this conversation.  Computed from `SELECT COUNT(*) FROM emails WHERE conversation_id = ? AND sender_address = ?`.  Updated on each sync. |
| `first_seen_at` | TEXT | | ISO 8601 timestamp of this participant's earliest message in the conversation.  Computed from `MIN(emails.date)`. |
| `last_seen_at` | TEXT | | ISO 8601 timestamp of this participant's most recent message.  Computed from `MAX(emails.date)`. |

**Primary key:** `(conversation_id, email_address)` — one row per
participant per conversation.

**Populated by:** `sync._store_thread()`.  Uses UPSERT: on conflict
(re-sync), updates `contact_id`, `message_count`, `first_seen_at`, and
`last_seen_at`.  The participant list is derived from
`ParsedEmail.all_participants` across all emails in the thread.

### 7. `topics` and `conversation_topics`

Normalized topic tracking across conversations.  Topics are short
phrases extracted by Claude during summarization (the `key_topics` field
in the AI response).  They are stored in two tables to enable
cross-conversation topic queries.

#### `topics`

The global dictionary of known topics.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | TEXT | **PK** | UUID v4. |
| `name` | TEXT | NOT NULL, **UNIQUE** | The topic string, lowercased and trimmed.  Examples: `'project timeline'`, `'budget review'`, `'hiring'`. |
| `created_at` | TEXT | NOT NULL | ISO 8601 timestamp of first insertion. |

**Populated by:** `sync._store_topics()`.  Uses `INSERT ... ON
CONFLICT(name) DO NOTHING` so existing topics are reused, not
duplicated.

#### `conversation_topics`

The many-to-many join between conversations and topics.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `conversation_id` | TEXT | NOT NULL, FK → `conversations(id)` | ON DELETE CASCADE. |
| `topic_id` | TEXT | NOT NULL, FK → `topics(id)` | ON DELETE CASCADE. |
| `confidence` | REAL | DEFAULT 1.0 | AI confidence score for this topic assignment.  Currently always 1.0; reserved for future confidence-weighted extraction. |
| `source` | TEXT | DEFAULT `'ai'` | How this topic was assigned.  Values: `'ai'`, `'manual'`.  Currently always `'ai'`. |
| `created_at` | TEXT | NOT NULL | ISO 8601 timestamp. |

**Primary key:** `(conversation_id, topic_id)` — one link per
conversation-topic pair.

**Populated by:** `sync._store_topics()`.  Uses `INSERT OR IGNORE` for
idempotent re-insertion.

**Dual storage rationale:** Topics exist in two places:
1. `conversations.ai_topics` — the raw JSON array from Claude, stored as
   a TEXT field directly on the conversation row.  This is the
   source-of-truth AI output.
2. `topics` / `conversation_topics` — the normalized, deduplicated,
   queryable version.  Enables queries like "show all conversations
   about topic X" and "what are the most common topics across all
   conversations?"

The normalized tables are derived from the raw JSON during
`process_conversations()`.

### 8. `sync_log`

Audit trail of sync operations.  One row per sync run (initial or
incremental).  Useful for debugging, monitoring sync health, and
verifying idempotency.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | TEXT | **PK** | UUID v4. |
| `account_id` | TEXT | NOT NULL, FK → `email_accounts(id)` | Which account was synced.  ON DELETE CASCADE. |
| `sync_type` | TEXT | NOT NULL | What kind of sync this was.  Values: `'initial'`, `'incremental'`. |
| `started_at` | TEXT | NOT NULL | ISO 8601 timestamp of when the sync began. |
| `completed_at` | TEXT | | ISO 8601 timestamp of when the sync finished.  NULL while running. |
| `messages_fetched` | INTEGER | DEFAULT 0 | Total messages retrieved from the provider API. |
| `messages_stored` | INTEGER | DEFAULT 0 | Net new messages actually inserted into the DB (not already present).  Lower than `messages_fetched` on re-syncs due to deduplication. |
| `conversations_created` | INTEGER | DEFAULT 0 | Number of new conversation rows inserted. |
| `conversations_updated` | INTEGER | DEFAULT 0 | Number of existing conversation rows updated (new messages arrived). |
| `cursor_before` | TEXT | | The `sync_cursor` value at the start of this sync.  NULL for initial syncs.  For incremental syncs, this is the `historyId` that was used as `startHistoryId`. |
| `cursor_after` | TEXT | | The `sync_cursor` value recorded after the sync completed.  This becomes the `cursor_before` for the next incremental sync. |
| `status` | TEXT | DEFAULT `'running'` | Lifecycle state of this sync run.  Values: `'running'`, `'completed'`, `'failed'`.  Enforced by a CHECK constraint. |
| `error` | TEXT | | Error message if the sync failed.  NULL on success. |

**Populated by:** `sync.initial_sync()` and `sync.incremental_sync()`.
A row is inserted with `status='running'` at the start, then updated to
`'completed'` (with counts and `cursor_after`) or `'failed'` (with
error message) at the end.

---

## Indexes

Twelve indexes support the common query patterns.  All use
`CREATE INDEX IF NOT EXISTS` for idempotent creation.

### Emails table

| Index | Column(s) | Supports |
|-------|-----------|----------|
| `idx_emails_account` | `account_id` | "All emails for account X" — used by every sync and display query. |
| `idx_emails_conversation` | `conversation_id` | "All emails in conversation Y" — the most frequent read pattern (loading a conversation's messages for triage, summarization, and display). |
| `idx_emails_date` | `date` | Chronological sorting and date-range filtering. |
| `idx_emails_sender` | `sender_address` | "All emails from address Z" — participant activity queries. |
| `idx_emails_message_id_hdr` | `header_message_id` | IMAP thread reconstruction: looking up emails by their RFC 5322 Message-ID to build Reference chains. |

### Conversations table

| Index | Column(s) | Supports |
|-------|-----------|----------|
| `idx_conversations_account` | `account_id` | "All conversations for account X" — listing and processing queries. |
| `idx_conversations_status` | `status` | Filtering by system status (`active` / `stale` / `closed`). |
| `idx_conversations_last_msg` | `last_message_at` | Sorting conversations by recency (the default display order). |

### Recipients table

| Index | Column(s) | Supports |
|-------|-----------|----------|
| `idx_recipients_address` | `address` | "Find all emails sent to address Z". |

### Participants table

| Index | Column(s) | Supports |
|-------|-----------|----------|
| `idx_participants_contact` | `contact_id` | "Find all conversations involving contact C". |
| `idx_participants_email` | `email_address` | "Find all conversations involving address Z" (even without a contact match). |

### Sync log table

| Index | Column(s) | Supports |
|-------|-----------|----------|
| `idx_sync_log_account` | `account_id` | "Show sync history for account X". |

---

## Serialization Layer (`models.py`)

The Python dataclasses include `to_row()` and `from_row()` methods that
handle conversion between in-memory objects and database rows.  This
keeps SQL out of the model definitions and centralizes column mapping.

### `KnownContact`

| Method | Direction | Notes |
|--------|-----------|-------|
| `to_row(contact_id=None)` | Object → `contacts` row | Generates UUID if not provided.  Lowercases email.  Sets `source='google_contacts'`. |
| `from_row(row)` | `contacts` row → Object | Maps `email` → `email`, `name` → `name`, `source_id` → `resource_name`. |

### `ParsedEmail`

| Method | Direction | Notes |
|--------|-----------|-------|
| `to_row(account_id, conversation_id, email_id, account_email)` | Object → `emails` row | Computes `direction` by comparing `sender_email` to `account_email`.  Formats `date` as ISO 8601. |
| `recipient_rows(email_id)` | Object → `email_recipients` rows | Returns list of dicts, one per To/CC address. |
| `from_row(row, recipients=None)` | `emails` row + optional `email_recipients` rows → Object | Parses ISO 8601 date back to `datetime`.  Splits recipients by role into `recipients` (to) and `cc` lists. |

### `Conversation`

| Method | Direction | Notes |
|--------|-----------|-------|
| `to_row(account_id, conversation_id)` | Object → `conversations` row | Computes `message_count`, `first_message_at`, `last_message_at` from the emails list.  Initializes all AI fields to NULL. |
| `from_row(row, emails=None)` | `conversations` row → Object | Uses `provider_thread_id` as `thread_id`, falling back to the row `id`. |

### `ConversationSummary`

| Method | Direction | Notes |
|--------|-----------|-------|
| `to_update_dict()` | Object → partial `conversations` UPDATE dict | Lowercases `status` for storage.  JSON-serializes `action_items` and `key_topics`.  Sets `ai_summarized_at` to now. |
| `from_conversation_row(row)` | `conversations` row → Object or None | Returns None if `ai_summarized_at` is NULL (not yet summarized).  Uppercases `ai_status` back to enum.  JSON-deserializes `ai_action_items` and `ai_topics`. |

### `FilterReason` mapping

Two helper functions convert between the Python enum and the database
string representation:

| Function | Direction | Example |
|----------|-----------|---------|
| `filter_reason_to_db(reason)` | `FilterReason.NO_KNOWN_CONTACTS` → `'no_known_contacts'` | Used when writing `triage_result` to conversations. |
| `filter_reason_from_db(db_str)` | `'automated_sender'` → `FilterReason.AUTOMATED_SENDER` | Used when reading `triage_result` for display. |

The mapping:

| Enum value | DB string |
|------------|-----------|
| `NO_KNOWN_CONTACTS` | `no_known_contacts` |
| `AUTOMATED_SENDER` | `automated_sender` |
| `AUTOMATED_SUBJECT` | `automated_subject` |
| `MARKETING` | `marketing` |

---

## Data Flows

### Flow 1: Initial Sync

Triggered on first run (or when `initial_sync_done = 0`).  Fetches all
matching threads from Gmail and populates the database from scratch.

```
register_account()
│  ├─ gmail_client.get_user_email()     → user's email
│  ├─ INSERT email_accounts             → account_id
│  └─ return account_id
│
sync_contacts()
│  ├─ contacts_client.fetch_contacts()  → list[KnownContact]
│  └─ UPSERT contacts                  (ON CONFLICT email DO UPDATE)
│
initial_sync(account_id)
│  ├─ INSERT sync_log (status='running')
│  ├─ load_contact_index()              → dict[email, KnownContact]
│  │
│  ├─ LOOP (paginated):
│  │   ├─ gmail_client.fetch_threads()  → list[list[ParsedEmail]]
│  │   └─ for each thread:
│  │       └─ _store_thread(conn, ...)
│  │           ├─ email_parser.strip_quotes()   (clean bodies)
│  │           ├─ INSERT conversations          (new thread)
│  │           ├─ for each email:
│  │           │   ├─ INSERT OR IGNORE emails
│  │           │   └─ INSERT OR IGNORE email_recipients
│  │           └─ for each participant:
│  │               └─ UPSERT conversation_participants
│  │
│  ├─ gmail_client.get_history_id()     → current historyId
│  ├─ UPDATE email_accounts
│  │   SET sync_cursor=historyId, initial_sync_done=1
│  └─ UPDATE sync_log (status='completed', cursor_after=historyId)
```

### Flow 2: Incremental Sync

Triggered on subsequent runs (when `initial_sync_done = 1`).  Uses the
Gmail History API to fetch only changes since the last sync.

```
incremental_sync(account_id)
│  ├─ SELECT sync_cursor FROM email_accounts  → cursor_before
│  ├─ INSERT sync_log (cursor_before, status='running')
│  ├─ load_contact_index()
│  │
│  ├─ gmail_client.fetch_history(cursor_before)
│  │   → (added_message_ids, deleted_message_ids)
│  │
│  ├─ PROCESS ADDITIONS:
│  │   ├─ gmail_client.fetch_messages(added_ids)  → list[ParsedEmail]
│  │   ├─ Group by thread_id
│  │   └─ for each thread group:
│  │       └─ _store_thread(conn, ...)
│  │           ├─ INSERT conversations (if new thread)
│  │           ├─ INSERT OR IGNORE emails
│  │           ├─ INSERT OR IGNORE email_recipients
│  │           ├─ UPSERT conversation_participants
│  │           └─ if existing conversation gained new emails:
│  │               UPDATE conversations
│  │                 SET message_count=recount, dates=recompute,
│  │                     ai_summarized_at=NULL  ← marks for re-summarization
│  │
│  ├─ PROCESS DELETIONS:
│  │   └─ for each deleted message_id:
│  │       ├─ DELETE FROM emails WHERE provider_message_id = ?
│  │       └─ UPDATE conversations SET message_count = recount
│  │
│  ├─ gmail_client.get_history_id()  → new historyId
│  ├─ UPDATE email_accounts SET sync_cursor=new_historyId
│  └─ UPDATE sync_log (status='completed', cursor_after=new_historyId)
```

**Re-summarization trigger:** When `_store_thread()` detects that an
existing conversation received new messages (`new_email_count > 0`), it
sets `ai_summarized_at = NULL`.  This marks the conversation as needing
re-processing.  The next `process_conversations()` call will pick it up
because it queries for rows where both `triage_result IS NULL` and
`ai_summarized_at IS NULL`.

### Flow 3: Conversation Processing (Triage + Summarize + Topics)

Runs after sync completes.  Processes conversations that have not yet
been triaged or summarized.

```
process_conversations(account_id, user_email)
│  ├─ load_contact_index()
│  │
│  ├─ SELECT * FROM conversations
│  │   WHERE triage_result IS NULL AND ai_summarized_at IS NULL
│  │
│  └─ for each conversation row:
│      ├─ SELECT emails WHERE conversation_id = ?
│      ├─ SELECT email_recipients WHERE email_id IN (...)
│      ├─ Reconstruct Conversation + ParsedEmail objects
│      ├─ Collect participants, match contacts
│      │
│      ├─ triage.triage_conversations([conv], user_email)
│      │   ├─ Layer 1: Check automated sender patterns
│      │   ├─ Layer 1: Check automated subject patterns
│      │   ├─ Layer 1: Check marketing (unsubscribe in body)
│      │   └─ Layer 2: Check known-contact gate
│      │
│      ├─ IF FILTERED:
│      │   └─ UPDATE conversations SET triage_result = '<reason>'
│      │
│      └─ IF KEPT (passed triage):
│          ├─ summarizer.summarize_conversation(conv, claude_client)
│          │   → ConversationSummary (summary, status, action_items, key_topics)
│          │
│          ├─ UPDATE conversations SET
│          │   ai_summary, ai_status, ai_action_items, ai_topics, ai_summarized_at
│          │
│          └─ _store_topics(conversation_id, key_topics)
│              ├─ for each topic string:
│              │   ├─ lowercase, trim
│              │   ├─ INSERT topics ON CONFLICT(name) DO NOTHING
│              │   └─ INSERT OR IGNORE conversation_topics
│              └─ return topic_count
```

### Flow 4: Display (Reading from DB)

After processing, the pipeline loads conversations back from the
database for Rich terminal output.

```
load_conversations_for_display(account_id)
│  ├─ SELECT * FROM conversations WHERE account_id = ? AND triage_result IS NULL
│  │   ORDER BY last_message_at DESC
│  │
│  ├─ for each conversation row:
│  │   ├─ skip if triage_result is set → add to triage_filtered list
│  │   ├─ SELECT * FROM emails WHERE conversation_id = ? ORDER BY date
│  │   ├─ SELECT * FROM email_recipients WHERE email_id = ?  (per email)
│  │   ├─ Reconstruct ParsedEmail objects via from_row()
│  │   ├─ SELECT * FROM conversation_participants WHERE conversation_id = ?
│  │   ├─ for each participant with contact_id:
│  │   │   └─ SELECT * FROM contacts WHERE id = ?
│  │   │       → populate conv.matched_contacts
│  │   ├─ Build Conversation object
│  │   └─ ConversationSummary.from_conversation_row()  → summary or None
│  │
│  ├─ SELECT * FROM conversations WHERE triage_result IS NOT NULL
│  │   → build TriageResult list for display stats
│  │
│  └─ return (conversations, summaries, triage_filtered)
│
display_triage_stats(triage_filtered)   → Rich table of filter reasons
display_results(conversations, summaries) → Rich panels grouped by status
```

---

## UPSERT and Idempotency Patterns

The sync layer is designed to be safe to re-run at any time without
creating duplicates or corrupting data.

| Table | UNIQUE constraint | Write pattern | Effect on duplicate |
|-------|-------------------|---------------|---------------------|
| `email_accounts` | `(provider, email_address)` | Check-then-insert in `register_account()` | Returns existing ID |
| `conversations` | `(account_id, provider_thread_id)` | Check-then-insert in `_store_thread()` | Updates existing row |
| `emails` | `(account_id, provider_message_id)` | `INSERT OR IGNORE` | Silently skipped |
| `email_recipients` | `(email_id, address, role)` | `INSERT OR IGNORE` | Silently skipped |
| `contacts` | `email` | `INSERT ... ON CONFLICT(email) DO UPDATE` | Name/source_id updated |
| `conversation_participants` | `(conversation_id, email_address)` | `INSERT ... ON CONFLICT DO UPDATE` | Counts/dates refreshed |
| `topics` | `name` | `INSERT ... ON CONFLICT(name) DO NOTHING` | Existing row reused |
| `conversation_topics` | `(conversation_id, topic_id)` | `INSERT OR IGNORE` | Silently skipped |

---

## Sync Cursor Mechanics

The `sync_cursor` field on `email_accounts` is an opaque TEXT field
whose interpretation depends on the `provider` value.

| Provider | Cursor format | API used | Meaning |
|----------|---------------|----------|---------|
| `gmail` | Numeric string (e.g. `'12345678'`) | `history.list(startHistoryId=...)` | Gmail's historyId.  A monotonically increasing identifier.  Changes since this ID can be retrieved via the History API. |
| `outlook` *(future)* | URL string | Delta query (`deltaLink`) | Outlook's delta sync token, returned as a URL. |
| `imap` *(future)* | `'UIDVALIDITY:lastUID'` | IMAP `FETCH` with UID range | Compound cursor: UIDVALIDITY detects mailbox rebuild, lastUID marks how far we've synced. |

**Lifecycle:**
1. NULL before initial sync.
2. Set to the current `historyId` when initial sync completes.
3. Used as `startHistoryId` in each incremental sync.
4. Advanced to the new `historyId` after each incremental sync.
5. Recorded in `sync_log.cursor_before` / `cursor_after` for audit.

---

## Conversation Lifecycle States

Conversations have two independent status dimensions:

### System status (`conversations.status`)

Based on activity window and sync state.  Currently all conversations
are created with `'active'`.

| Value | Meaning |
|-------|---------|
| `active` | Conversation has recent activity (within the backfill window). |
| `stale` | No new messages for an extended period.  *(Not yet implemented.)* |
| `closed` | System-determined closed (e.g. all participants left).  *(Not yet implemented.)* |

### AI status (`conversations.ai_status`)

Semantic classification by Claude, from the account owner's perspective.

| Value | Meaning |
|-------|---------|
| `open` | Active conversation: unanswered questions, pending tasks, ongoing discussion.  Claude biases toward this for multi-message threads between known contacts. |
| `closed` | Definitively finished: question fully answered, explicit goodbye, or one-way notification. |
| `uncertain` | Not enough context to determine. |

### Triage status (`conversations.triage_result`)

Whether the conversation was filtered out before summarization.

| Value | Meaning |
|-------|---------|
| NULL | Passed triage — real conversation, eligible for summarization. |
| `no_known_contacts` | No participant (other than the account owner) is a known contact. |
| `automated_sender` | First email's sender matches automated-sender patterns (noreply@, notification@, etc.). |
| `automated_subject` | Subject matches automated-subject patterns (out of office, password reset, etc.). |
| `marketing` | Email body contains "unsubscribe" text. |

---

## Query Patterns

The most common queries the system executes, and which indexes support
them:

| Query | SQL pattern | Indexes used |
|-------|-------------|--------------|
| Find account by provider+email | `WHERE provider = ? AND email_address = ?` | UNIQUE constraint |
| All conversations for an account | `WHERE account_id = ?` | `idx_conversations_account` |
| Conversations needing processing | `WHERE account_id = ? AND triage_result IS NULL AND ai_summarized_at IS NULL` | `idx_conversations_account` |
| Conversations sorted by recency | `ORDER BY last_message_at DESC` | `idx_conversations_last_msg` |
| Emails in a conversation | `WHERE conversation_id = ? ORDER BY date` | `idx_emails_conversation`, `idx_emails_date` |
| Recipients of an email | `WHERE email_id = ?` | PK on `email_recipients` |
| Participants in a conversation | `WHERE conversation_id = ?` | PK on `conversation_participants` |
| Conversations involving a contact | `WHERE contact_id = ?` | `idx_participants_contact` |
| Conversations involving an address | `WHERE email_address = ?` | `idx_participants_email` |
| Emails from a specific sender | `WHERE sender_address = ?` | `idx_emails_sender` |
| Sync history for an account | `WHERE account_id = ?` | `idx_sync_log_account` |
| Email by provider message ID | `WHERE account_id = ? AND provider_message_id = ?` | UNIQUE constraint |
| Find email by RFC Message-ID | `WHERE header_message_id = ?` | `idx_emails_message_id_hdr` |

---

## Configuration

| Setting | Env variable | Default | Description |
|---------|-------------|---------|-------------|
| `DB_PATH` | `POC_DB_PATH` | `data/crm_extender.db` | Path to the SQLite database file.  Parent directories are created automatically by `init_db()`. |

The database file and its WAL/SHM companions are excluded from version
control via `.gitignore` (`data/` directory).
