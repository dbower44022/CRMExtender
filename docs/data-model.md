# Data Model & Database Design

This document describes the persistent data layer that backs the CRM
Extender pipeline.  It covers the SQLite schema (v3, 22 tables), every
table and column, the relationships between entities, the serialization
layer that maps Python dataclasses to database rows, the indexing
strategy, and the data flows that populate and query the database.

**Implementation files:**

| File | Role |
|------|------|
| `poc/database.py` | Connection management, schema DDL, WAL/FK pragmas |
| `poc/models.py` | Dataclasses with `to_row()` / `from_row()` serialization |
| `poc/sync.py` | Sync orchestration: writes to DB, reads from DB for display |
| `poc/hierarchy.py` | Company/project/topic/assignment CRUD and stats queries |
| `poc/auto_assign.py` | Bulk auto-assign conversations to topics by tag/title matching |
| `poc/contacts_client.py` | Google People API client (names, emails, organizations) |
| `poc/relationship_inference.py` | Contact relationship inference from co-occurrence data |
| `poc/config.py` | `DB_PATH` setting (default `data/crm_extender.db`) |
| `poc/migrate_to_v2.py` | Schema migration: v1 (8-table) to v2 (21-table) |
| `poc/migrate_to_v3.py` | Schema migration: v2 to v3 (companies + audit columns) |

---

## Architecture Overview

```
                         +------------------------------------+
                         |         SQLite Database             |
                         |   data/crm_extender.db (WAL mode)  |
                         +----------------+-------------------+
                                          |
        +------------------+--------------+----------------+------------------+
        |                  |              |                |                  |
  +-----+-----+    +------+------+ +-----+------+  +-----+------+  +-------+--------+
  |  sync.py   |    |relationship_| |models.py   |  | database.py |  | conversation_  |
  |            |    |inference.py | |            |  |             |  |  builder.py    |
  | Writes:    |    |             | | to_row()   |  | init_db()   |  |               |
  |  accounts  |    | Reads:      | | from_row() |  | get_conn()  |  | Reads:        |
  |  contacts  |    |  conv_      | | Enum maps  |  | Schema DDL  |  |  comms        |
  |  companies |    |  partici-   | |            |  | Index DDL   |  |  recipients   |
  |  comms     |    |  pants      | +------------+  +-------------+  |  participants |
  |  convos    |    |  contacts   |                                  +---------------+
  |  tags      |    |             |
  |  sync_log  |    | Writes:     |
  |            |    |  relation-  |
  | Reads:     |    |  ships      |
  |  display   |    +-------------+
  |  processing|
  +------------+
```

The database is the single source of truth after the first sync.
Subsequent runs read state from it (account registration, sync cursors,
existing conversations) and write incremental changes back.  The
in-memory `Conversation` / `ParsedEmail` dataclasses are reconstructed
from DB rows when needed for triage, summarization, or display.

---

## Schema Version History

| Version | Tables | Key changes |
|---------|--------|-------------|
| v1 | 8 | Original email-only schema: `email_accounts`, `emails`, `email_recipients`, `contacts`, `conversations`, `conversation_participants`, `topics`, `conversation_topics`, `sync_log` |
| v2 | 21 | Multi-channel design: renamed tables (`provider_accounts`, `communications`, `communication_participants`, `tags`, `conversation_tags`), added `conversation_communications` M:N join, `contact_identifiers`, `users`, `projects`, organizational `topics`, `attachments`, `views`, `alerts`, correction tables, `relationships` |
| v3 | 22 | Companies + audit tracking: added `companies` table, `company_id` FK on `contacts`, `created_by`/`updated_by` audit columns on `contacts`, `contact_identifiers`, `conversations`, `projects`, `topics`, `companies` |

---

## Entity-Relationship Diagram

```
+------------------+
|      users       |
|------------------|     +-------------------+
| PK id            |     |    companies      |
|    email (UNIQ)  |     |-------------------|
|    name          |     | PK id             |
|    role          |     |    name (UNIQ)    |
|    is_active     |     |    domain         |
+--------+---------+     |    industry       |
         |               |    status         |
         | FK created_by |    created_by ----+---> users
         | FK updated_by |    updated_by ----+---> users
         |               +--------+----------+
         |                        |
         |                        | FK company_id
         |                        |
+--------+---------+     +--------+----------+     +-------------------+
| provider_accounts|     |     contacts      |     | contact_          |
|------------------|     |-------------------|     |   identifiers     |
| PK id            |     | PK id             |     |-------------------|
|    provider      |     |    name           |     | PK id             |
|    email_address |     |    company (text)  |     | FK contact_id     |
|    sync_cursor   |     |    company_id  ---+---->|    type           |
|    ...           |     |    source         |     |    value (UNIQ w/ |
+---------+--------+     |    status         |     |      type)        |
          |               |    created_by ----+---->|    created_by     |
          |               |    updated_by ----+---->|    updated_by     |
          |               +-------------------+     +-------------------+
          |
          | FK account_id
          |
+---------+--------+                     +-------------------+
|  communications  |                     |    projects       |
|------------------|                     |-------------------|
| PK id            |                     | PK id             |
| FK account_id    |                     |    parent_id (FK) |
|    channel       |                     |    name           |
|    timestamp     |                     |    owner_id       |
|    content       |                     |    created_by     |
|    direction     |                     |    updated_by     |
|    sender_address|                     +--------+----------+
|    subject       |                              |
|    provider_     |                              | FK project_id
|     message_id   |                              |
|    provider_     |                     +--------+----------+
|     thread_id    |                     |      topics       |
|    ...           |                     | (organizational)  |
+--+----------+----+                     |-------------------|
   |          |                          | PK id             |
   |          |                          | FK project_id     |
   |          | N                        |    name           |
   |          v                          |    created_by     |
   |  +-------------------+             |    updated_by     |
   |  | communication_    |             +--------+----------+
   |  |   participants    |                      |
   |  |-------------------|                      | FK topic_id
   |  | PK comm_id,       |                      |
   |  |    address, role  |             +--------+----------+
   |  |    contact_id     |             |   conversations   |
   |  +-------------------+             |-------------------|
   |                                    | PK id             |
   |  +-------------------+             | FK topic_id       |
   |  | conversation_     |             |    title          |
   +->|   communications  |------------>|    status         |
      |-------------------|             |    comm_count     |
      | PK conv_id,       |             |    triage_result  |
      |    comm_id        |             |    ai_summary     |
      |    assignment_src |             |    created_by     |
      |    confidence     |             |    updated_by     |
      +-------------------+             +--------+----------+
                                                 |
                         +-----------+-----------+-----------+
                         |           |                       |
                +--------+--+  +----+----------+  +---------+-------+
                | conv_      |  | conv_tags    |  | relationships   |
                | participants|  |-------------|  |-----------------|
                |------------|  | PK conv_id,  |  | PK id           |
                | PK conv_id,|  |    tag_id    |  |    from_entity  |
                |    address |  +----+---------+  |    to_entity    |
                | FK contact |       |            |    type         |
                +------------+       v            |    properties   |
                              +-----------+       +-----------------+
                              |   tags    |
                              |-----------|
                              | PK id     |
                              |    name   |
                              |    source |
                              +-----------+
```

### Relationship Summary

| Parent | Child | Cardinality | FK Column | On Delete |
|--------|-------|-------------|-----------|-----------|
| `users` | `companies` | 1:N | `created_by`, `updated_by` | SET NULL |
| `users` | `contacts` | 1:N | `created_by`, `updated_by` | SET NULL |
| `users` | `contact_identifiers` | 1:N | `created_by`, `updated_by` | SET NULL |
| `users` | `conversations` | 1:N | `created_by`, `updated_by` | SET NULL |
| `users` | `projects` | 1:N | `owner_id`, `created_by`, `updated_by` | SET NULL |
| `users` | `topics` | 1:N | `created_by`, `updated_by` | SET NULL |
| `companies` | `contacts` | 1:N | `company_id` | SET NULL |
| `provider_accounts` | `communications` | 1:N | `account_id` | SET NULL |
| `provider_accounts` | `sync_log` | 1:N | `account_id` | CASCADE |
| `contacts` | `contact_identifiers` | 1:N | `contact_id` | CASCADE |
| `contacts` | `conversation_participants` | 0..1:N | `contact_id` | SET NULL |
| `contacts` | `communication_participants` | 0..1:N | `contact_id` | SET NULL |
| `conversations` | `conversation_communications` | 1:N | `conversation_id` | CASCADE |
| `communications` | `conversation_communications` | 1:N | `communication_id` | CASCADE |
| `conversations` | `conversation_participants` | 1:N | `conversation_id` | CASCADE |
| `conversations` | `conversation_tags` | 1:N | `conversation_id` | CASCADE |
| `tags` | `conversation_tags` | 1:N | `tag_id` | CASCADE |
| `communications` | `communication_participants` | 1:N | `communication_id` | CASCADE |
| `communications` | `attachments` | 1:N | `communication_id` | CASCADE |
| `projects` | `projects` (self) | 1:N | `parent_id` | CASCADE |
| `projects` | `topics` | 1:N | `project_id` | CASCADE |
| `topics` | `conversations` | 1:N | `topic_id` | SET NULL |
| `contacts` | `relationships` (from) | 1:N | `from_entity_id` | *(no FK)* |
| `contacts` | `relationships` (to) | 1:N | `to_entity_id` | *(no FK)* |

---

## Connection Management

`database.py` provides two entry points:

**`init_db(db_path=None)`** -- Creates the database file, parent
directories, all tables (`CREATE TABLE IF NOT EXISTS`), and all indexes.
Called once at startup in `__main__.py`.

**`get_connection(db_path=None)`** -- Context manager that yields a
`sqlite3.Connection` with:

- `journal_mode=WAL` -- Write-Ahead Logging for concurrent reads during
  sync writes.
- `foreign_keys=ON` -- Enforces all `REFERENCES` / `ON DELETE` constraints.
- `row_factory=sqlite3.Row` -- Rows are returned as dict-like objects,
  enabling column access by name.
- Auto-commit on clean exit, rollback on exception.

Both functions default to `config.DB_PATH` (`data/crm_extender.db`),
overridable via the `POC_DB_PATH` environment variable.

---

## Table Reference

### 1. `users`

Minimal user table for ownership and audit tracking.  FK target for
`created_by`/`updated_by` columns throughout the schema.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | TEXT | **PK** | UUID v4. |
| `email` | TEXT | NOT NULL, UNIQUE | User's email address. |
| `name` | TEXT | | Display name. |
| `role` | TEXT | DEFAULT `'member'` | User role (`'member'`, `'admin'`). |
| `is_active` | INTEGER | DEFAULT 1 | Boolean (0/1). |
| `created_at` | TEXT | NOT NULL | ISO 8601 timestamp. |
| `updated_at` | TEXT | NOT NULL | ISO 8601 timestamp. |

**Populated by:** `hierarchy.bootstrap_user()`, which auto-creates a
user from the first `provider_accounts` email.

### 2. `companies`

Companies that contacts can be linked to.  Auto-created during contact
sync when a contact has an organization in Google Contacts, or manually
via the CLI.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | TEXT | **PK** | UUID v4. |
| `name` | TEXT | NOT NULL, **UNIQUE** | Company name.  The unique index `idx_companies_name` enforces no duplicates. |
| `domain` | TEXT | | Company domain (e.g. `'acme.com'`). |
| `industry` | TEXT | | Industry classification. |
| `description` | TEXT | | Free-text description. |
| `status` | TEXT | DEFAULT `'active'` | Company status. |
| `created_by` | TEXT | FK -> `users(id)` | User who created this record.  ON DELETE SET NULL. |
| `updated_by` | TEXT | FK -> `users(id)` | User who last updated this record.  ON DELETE SET NULL. |
| `created_at` | TEXT | NOT NULL | ISO 8601 timestamp. |
| `updated_at` | TEXT | NOT NULL | ISO 8601 timestamp. |

**Populated by:** `sync._resolve_company_id()` (auto-creates during
contact sync from Google organization names), `hierarchy.create_company()`
(manual creation via CLI).

**Deleted by:** `hierarchy.delete_company()`.  Contacts with
`company_id` pointing to the deleted company get `company_id` SET NULL
via the FK constraint.

### 3. `provider_accounts`

Tracks connected accounts (email, future: phone, chat) and their
synchronization state.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | TEXT | **PK** | UUID v4.  Generated by `sync.register_account()`. |
| `provider` | TEXT | NOT NULL | Provider identifier (`'gmail'`; future: `'outlook'`, `'imap'`). |
| `account_type` | TEXT | NOT NULL, DEFAULT `'email'` | Channel type. |
| `email_address` | TEXT | | Account email address, lowercased. |
| `phone_number` | TEXT | | Phone number (future use). |
| `display_name` | TEXT | | Human-readable name. |
| `auth_token_path` | TEXT | | Filesystem path to the OAuth token file. |
| `sync_cursor` | TEXT | | Provider-specific sync position.  For Gmail: `historyId`. |
| `last_synced_at` | TEXT | | ISO 8601 timestamp of last successful sync. |
| `initial_sync_done` | INTEGER | DEFAULT 0 | Boolean (0/1).  Set to 1 after first full sync. |
| `backfill_query` | TEXT | DEFAULT `'newer_than:90d'` | Gmail search query for initial sync. |
| `created_at` | TEXT | NOT NULL | ISO 8601 timestamp. |
| `updated_at` | TEXT | NOT NULL | ISO 8601 timestamp. |

**Unique constraints:** `(provider, email_address)`, `(provider, phone_number)`.

### 4. `contacts`

Known contacts from address books.  Currently populated from Google
People API.  Contacts are global (not per-account).

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | TEXT | **PK** | UUID v4. |
| `name` | TEXT | | Display name from contact source. |
| `company` | TEXT | | Company name as text (backward compat; kept in sync with `company_id`). |
| `company_id` | TEXT | FK -> `companies(id)` | Link to the `companies` table.  ON DELETE SET NULL. |
| `source` | TEXT | | Origin: `'google_contacts'`, `'manual'`, etc. |
| `status` | TEXT | DEFAULT `'active'` | Contact status. |
| `created_by` | TEXT | FK -> `users(id)` | Audit: who created.  ON DELETE SET NULL. |
| `updated_by` | TEXT | FK -> `users(id)` | Audit: who last updated.  ON DELETE SET NULL. |
| `created_at` | TEXT | NOT NULL | ISO 8601 timestamp. |
| `updated_at` | TEXT | NOT NULL | ISO 8601 timestamp. |

**Populated by:** `sync.sync_contacts()`, which fetches from the Google
People API, resolves companies, and performs UPSERT operations keyed on
`contact_identifiers(type, value)`.

### 5. `contact_identifiers`

Maps contacts to their identifiers (email, phone, etc.).  A contact can
have multiple identifiers.  The `(type, value)` unique constraint enables
identity-based UPSERT during sync.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | TEXT | **PK** | UUID v4. |
| `contact_id` | TEXT | NOT NULL, FK -> `contacts(id)` | Parent contact.  ON DELETE CASCADE. |
| `type` | TEXT | NOT NULL | Identifier type: `'email'`, `'phone'`, etc. |
| `value` | TEXT | NOT NULL | The identifier value, normalized (emails lowercased). |
| `label` | TEXT | | Optional label (e.g. `'work'`, `'personal'`). |
| `is_primary` | INTEGER | DEFAULT 0 | Boolean (0/1).  Whether this is the contact's primary identifier. |
| `status` | TEXT | DEFAULT `'active'` | Identifier status. |
| `source` | TEXT | | Origin of this identifier. |
| `verified` | INTEGER | DEFAULT 0 | Boolean (0/1).  Whether this identifier has been verified. |
| `created_by` | TEXT | FK -> `users(id)` | Audit: who created.  ON DELETE SET NULL. |
| `updated_by` | TEXT | FK -> `users(id)` | Audit: who last updated.  ON DELETE SET NULL. |
| `created_at` | TEXT | NOT NULL | ISO 8601 timestamp. |
| `updated_at` | TEXT | NOT NULL | ISO 8601 timestamp. |

**Unique constraint:** `(type, value)`.

### 6. `projects`

Organizational hierarchy using an adjacency-list pattern.  Projects
contain topics, which in turn organize conversations.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | TEXT | **PK** | UUID v4. |
| `parent_id` | TEXT | FK -> `projects(id)` | Parent project for nesting.  ON DELETE CASCADE. |
| `name` | TEXT | NOT NULL | Project name. |
| `description` | TEXT | | Free-text description. |
| `status` | TEXT | DEFAULT `'active'` | Project status. |
| `owner_id` | TEXT | FK -> `users(id)` | Project owner.  ON DELETE SET NULL. |
| `created_by` | TEXT | FK -> `users(id)` | Audit: who created.  ON DELETE SET NULL. |
| `updated_by` | TEXT | FK -> `users(id)` | Audit: who last updated.  ON DELETE SET NULL. |
| `created_at` | TEXT | NOT NULL | ISO 8601 timestamp. |
| `updated_at` | TEXT | NOT NULL | ISO 8601 timestamp. |

### 7. `topics` (organizational)

Groupings within a project.  Conversations are assigned to topics either
manually or via the auto-assign feature.  Distinct from `tags` (which
are AI-extracted keywords).

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | TEXT | **PK** | UUID v4. |
| `project_id` | TEXT | NOT NULL, FK -> `projects(id)` | Parent project.  ON DELETE CASCADE. |
| `name` | TEXT | NOT NULL | Topic name. |
| `description` | TEXT | | Free-text description. |
| `source` | TEXT | DEFAULT `'user'` | How this topic was created. |
| `created_by` | TEXT | FK -> `users(id)` | Audit: who created.  ON DELETE SET NULL. |
| `updated_by` | TEXT | FK -> `users(id)` | Audit: who last updated.  ON DELETE SET NULL. |
| `created_at` | TEXT | NOT NULL | ISO 8601 timestamp. |
| `updated_at` | TEXT | NOT NULL | ISO 8601 timestamp. |

### 8. `conversations`

Account-independent threaded conversations.  The central table that most
queries target.  Holds system metadata, AI analysis fields, triage
results, and organizational assignment.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | TEXT | **PK** | UUID v4. |
| `topic_id` | TEXT | FK -> `topics(id)` | Organizational topic assignment.  ON DELETE SET NULL. |
| `title` | TEXT | | Subject line from the first communication. |
| `status` | TEXT | DEFAULT `'active'` | System status. |
| `communication_count` | INTEGER | DEFAULT 0 | Total communications in this conversation. |
| `participant_count` | INTEGER | DEFAULT 0 | Total unique participants. |
| `first_activity_at` | TEXT | | ISO 8601 timestamp of earliest communication. |
| `last_activity_at` | TEXT | | ISO 8601 timestamp of most recent communication. |
| `ai_summary` | TEXT | | Claude-generated summary.  NULL until summarized. |
| `ai_status` | TEXT | | AI classification: `'open'`, `'closed'`, `'uncertain'`. |
| `ai_action_items` | TEXT | | JSON array of action item strings. |
| `ai_topics` | TEXT | | JSON array of topic strings (raw AI output). |
| `ai_summarized_at` | TEXT | | ISO 8601 timestamp.  Set to NULL when new messages arrive to trigger re-processing. |
| `triage_result` | TEXT | | NULL if passed triage.  Values: `'no_known_contacts'`, `'automated_sender'`, `'automated_subject'`, `'marketing'`. |
| `dismissed` | INTEGER | DEFAULT 0 | Boolean (0/1).  User-dismissed. |
| `dismissed_reason` | TEXT | | Why the conversation was dismissed. |
| `dismissed_at` | TEXT | | When dismissed. |
| `dismissed_by` | TEXT | FK -> `users(id)` | Who dismissed.  ON DELETE SET NULL. |
| `created_by` | TEXT | FK -> `users(id)` | Audit: who created.  ON DELETE SET NULL. |
| `updated_by` | TEXT | FK -> `users(id)` | Audit: who last updated.  ON DELETE SET NULL. |
| `created_at` | TEXT | NOT NULL | ISO 8601 timestamp. |
| `updated_at` | TEXT | NOT NULL | ISO 8601 timestamp. |

**Populated by:** `sync._store_thread()` (INSERT on new thread, UPDATE
on incremental), `sync.process_conversations()` (UPDATE for
`triage_result` and `ai_*` fields).

### 9. `conversation_participants`

Links email addresses to conversations, optionally matching them to
known contacts.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `conversation_id` | TEXT | NOT NULL, FK -> `conversations(id)` | ON DELETE CASCADE. |
| `address` | TEXT | NOT NULL | Participant's address, lowercased. |
| `name` | TEXT | | Display name. |
| `contact_id` | TEXT | FK -> `contacts(id)` | Matched contact.  ON DELETE SET NULL. |
| `communication_count` | INTEGER | DEFAULT 0 | Messages sent by this participant in this conversation. |
| `first_seen_at` | TEXT | | Earliest message timestamp. |
| `last_seen_at` | TEXT | | Most recent message timestamp. |

**Primary key:** `(conversation_id, address)`.

### 10. `communications`

Individual messages (email, future: SMS, call, note).  Provider-normalized.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | TEXT | **PK** | UUID v4. |
| `account_id` | TEXT | FK -> `provider_accounts(id)` | Which account fetched this.  ON DELETE SET NULL. |
| `channel` | TEXT | NOT NULL | Channel type: `'email'`, future `'sms'`, `'call'`, `'note'`. |
| `timestamp` | TEXT | NOT NULL | ISO 8601 timestamp of the message. |
| `content` | TEXT | | Cleaned plain-text body (quotes/signatures stripped). |
| `direction` | TEXT | | `'inbound'` or `'outbound'` relative to the account owner. |
| `source` | TEXT | | How this was created: `'auto_sync'`, `'manual'`. |
| `sender_address` | TEXT | | Sender's address, lowercased. |
| `sender_name` | TEXT | | Sender's display name. |
| `subject` | TEXT | | Message subject line. |
| `body_html` | TEXT | | Raw HTML body (preserved for re-processing). |
| `snippet` | TEXT | | Short preview text from the provider. |
| `provider_message_id` | TEXT | | Provider's native message ID (e.g. Gmail message ID). |
| `provider_thread_id` | TEXT | | Provider's native thread ID. |
| `header_message_id` | TEXT | | RFC 5322 Message-ID header.  For IMAP threading. |
| `header_references` | TEXT | | References header.  For IMAP threading. |
| `header_in_reply_to` | TEXT | | In-Reply-To header.  For IMAP threading. |
| `is_read` | INTEGER | DEFAULT 0 | Boolean. |
| `phone_number_from` | TEXT | | SMS/call: sender phone. |
| `phone_number_to` | TEXT | | SMS/call: recipient phone. |
| `duration_seconds` | INTEGER | | Call duration. |
| `transcript_source` | TEXT | | Call transcript origin. |
| `note_type` | TEXT | | Note classification. |
| `provider_metadata` | TEXT | | JSON blob of provider-specific data. |
| `user_metadata` | TEXT | | JSON blob of user-added data. |
| `previous_revision` | TEXT | FK -> `communications(id)` | Edit chain: previous version.  ON DELETE SET NULL. |
| `next_revision` | TEXT | FK -> `communications(id)` | Edit chain: next version.  ON DELETE SET NULL. |
| `is_current` | INTEGER | DEFAULT 1 | Boolean.  Whether this is the current revision. |
| `ai_summary` | TEXT | | Per-message AI summary. |
| `ai_summarized_at` | TEXT | | When summarized. |
| `triage_result` | TEXT | | Per-message triage result. |
| `created_at` | TEXT | NOT NULL | ISO 8601 timestamp. |
| `updated_at` | TEXT | NOT NULL | ISO 8601 timestamp. |

**Unique constraint:** `(account_id, provider_message_id)`.

### 11. `communication_participants`

To/CC/BCC recipients of each communication.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `communication_id` | TEXT | NOT NULL, FK -> `communications(id)` | ON DELETE CASCADE. |
| `address` | TEXT | NOT NULL | Recipient address, lowercased. |
| `name` | TEXT | | Recipient display name. |
| `contact_id` | TEXT | FK -> `contacts(id)` | Matched contact.  ON DELETE SET NULL. |
| `role` | TEXT | NOT NULL | Recipient type: `'to'`, `'cc'`, `'bcc'`. |

**Primary key:** `(communication_id, address, role)`.

### 12. `conversation_communications`

Many-to-many join between conversations and communications.  Replaces
the direct `conversation_id` FK that existed on v1 emails.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `conversation_id` | TEXT | NOT NULL, FK -> `conversations(id)` | ON DELETE CASCADE. |
| `communication_id` | TEXT | NOT NULL, FK -> `communications(id)` | ON DELETE CASCADE. |
| `display_content` | TEXT | | Optional display-time content override. |
| `is_primary` | INTEGER | DEFAULT 1 | Whether this is the primary conversation for this communication. |
| `assignment_source` | TEXT | NOT NULL, DEFAULT `'sync'` | How assigned: `'sync'`, `'ai'`, `'manual'`. |
| `confidence` | REAL | DEFAULT 1.0 | Assignment confidence score. |
| `reviewed` | INTEGER | DEFAULT 0 | Whether a human has reviewed this assignment. |
| `reviewed_at` | TEXT | | When reviewed. |
| `created_at` | TEXT | NOT NULL | ISO 8601 timestamp. |

**Primary key:** `(conversation_id, communication_id)`.

### 13. `attachments`

File attachments on communications.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | TEXT | **PK** | UUID v4. |
| `communication_id` | TEXT | NOT NULL, FK -> `communications(id)` | ON DELETE CASCADE. |
| `filename` | TEXT | NOT NULL | Original filename. |
| `mime_type` | TEXT | | MIME type. |
| `size_bytes` | INTEGER | | File size. |
| `storage_ref` | TEXT | | Reference to stored file. |
| `source` | TEXT | | Origin. |
| `created_at` | TEXT | NOT NULL | ISO 8601 timestamp. |

### 14. `tags` and `conversation_tags`

AI-extracted keyword phrases.  Distinct from organizational `topics`.

#### `tags`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | TEXT | **PK** | UUID v4. |
| `name` | TEXT | NOT NULL, UNIQUE | Lowercase, trimmed tag string. |
| `source` | TEXT | DEFAULT `'ai'` | How created: `'ai'`, `'manual'`. |
| `created_at` | TEXT | NOT NULL | ISO 8601 timestamp. |

#### `conversation_tags`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `conversation_id` | TEXT | NOT NULL, FK -> `conversations(id)` | ON DELETE CASCADE. |
| `tag_id` | TEXT | NOT NULL, FK -> `tags(id)` | ON DELETE CASCADE. |
| `confidence` | REAL | DEFAULT 1.0 | AI confidence. |
| `source` | TEXT | DEFAULT `'ai'` | Assignment source. |
| `created_at` | TEXT | NOT NULL | ISO 8601 timestamp. |

**Primary key:** `(conversation_id, tag_id)`.

### 15. `views`

User-defined saved queries.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | TEXT | **PK** | UUID v4. |
| `owner_id` | TEXT | FK -> `users(id)` | ON DELETE SET NULL. |
| `name` | TEXT | NOT NULL | View name. |
| `description` | TEXT | | Description. |
| `query_def` | TEXT | NOT NULL | Serialized query definition. |
| `is_shared` | INTEGER | DEFAULT 0 | Whether visible to others. |
| `created_at` | TEXT | NOT NULL | ISO 8601 timestamp. |
| `updated_at` | TEXT | NOT NULL | ISO 8601 timestamp. |

### 16. `alerts`

Notification triggers on views.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | TEXT | **PK** | UUID v4. |
| `view_id` | TEXT | NOT NULL, FK -> `views(id)` | ON DELETE CASCADE. |
| `owner_id` | TEXT | FK -> `users(id)` | ON DELETE SET NULL. |
| `is_active` | INTEGER | DEFAULT 1 | Boolean. |
| `frequency` | TEXT | NOT NULL | How often to check. |
| `aggregation` | TEXT | DEFAULT `'batched'` | Delivery aggregation. |
| `delivery_method` | TEXT | NOT NULL | How to deliver. |
| `last_triggered` | TEXT | | Last trigger timestamp. |
| `created_at` | TEXT | NOT NULL | ISO 8601 timestamp. |
| `updated_at` | TEXT | NOT NULL | ISO 8601 timestamp. |

### 17. `relationships`

Inferred relationships between contacts from conversation co-occurrence.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | TEXT | **PK** | UUID v4. |
| `from_entity_type` | TEXT | NOT NULL, DEFAULT `'contact'` | Source entity type (polymorphic). |
| `from_entity_id` | TEXT | NOT NULL | Source contact ID. |
| `to_entity_type` | TEXT | NOT NULL, DEFAULT `'contact'` | Target entity type. |
| `to_entity_id` | TEXT | NOT NULL | Target contact ID. |
| `relationship_type` | TEXT | NOT NULL, DEFAULT `'KNOWS'` | Relationship kind. |
| `properties` | TEXT | | JSON: `{strength, shared_conversations, shared_messages, last_interaction, first_interaction}`. |
| `created_at` | TEXT | NOT NULL | ISO 8601 timestamp. |
| `updated_at` | TEXT | NOT NULL | ISO 8601 timestamp. |

**Unique constraint:** `(from_entity_id, to_entity_id, relationship_type)`.

### 18. `sync_log`

Audit trail of sync operations.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | TEXT | **PK** | UUID v4. |
| `account_id` | TEXT | NOT NULL, FK -> `provider_accounts(id)` | ON DELETE CASCADE. |
| `sync_type` | TEXT | NOT NULL | `'initial'` or `'incremental'`. |
| `started_at` | TEXT | NOT NULL | ISO 8601. |
| `completed_at` | TEXT | | ISO 8601.  NULL while running. |
| `messages_fetched` | INTEGER | DEFAULT 0 | Total fetched from provider. |
| `messages_stored` | INTEGER | DEFAULT 0 | Net new stored. |
| `conversations_created` | INTEGER | DEFAULT 0 | New conversations. |
| `conversations_updated` | INTEGER | DEFAULT 0 | Updated conversations. |
| `cursor_before` | TEXT | | Sync cursor at start. |
| `cursor_after` | TEXT | | Sync cursor after completion. |
| `status` | TEXT | DEFAULT `'running'` | `'running'`, `'completed'`, `'failed'`.  CHECK constraint. |
| `error` | TEXT | | Error message on failure. |

### 19-22. Correction tables

Four tables for AI learning from user corrections:

- **`assignment_corrections`** -- Records when a communication is moved between conversations.
- **`triage_corrections`** -- Records when a triage result is overridden.
- **`triage_rules`** -- Allow/block rules derived from corrections.
- **`conversation_corrections`** -- Records conversation-level corrections (splits, merges).

---

## Indexes

All use `CREATE INDEX IF NOT EXISTS` for idempotent creation.

### Communications

| Index | Column(s) | Supports |
|-------|-----------|----------|
| `idx_comm_account` | `account_id` | All communications for an account. |
| `idx_comm_channel` | `channel` | Filter by channel type. |
| `idx_comm_timestamp` | `timestamp` | Chronological sorting, date-range filtering. |
| `idx_comm_sender` | `sender_address` | All messages from a sender. |
| `idx_comm_thread` | `provider_thread_id` | Thread lookup during sync. |
| `idx_comm_header_msg_id` | `header_message_id` | IMAP thread reconstruction. |
| `idx_comm_current` | `is_current` | Filter to current revisions. |

### Conversations

| Index | Column(s) | Supports |
|-------|-----------|----------|
| `idx_conv_topic` | `topic_id` | Conversations in a topic. |
| `idx_conv_status` | `status` | Filter by system status. |
| `idx_conv_last_activity` | `last_activity_at` | Sort by recency. |
| `idx_conv_ai_status` | `ai_status` | Filter by AI classification. |
| `idx_conv_triage` | `triage_result` | Filter triaged/untriaged. |
| `idx_conv_needs_processing` | `(triage_result, ai_summarized_at)` | Find conversations needing processing. |
| `idx_conv_dismissed` | `dismissed` | Filter dismissed conversations. |

### Join tables

| Index | Column(s) | Supports |
|-------|-----------|----------|
| `idx_cc_communication` | `conversation_communications(communication_id)` | Reverse lookup: conversation for a communication. |
| `idx_cc_review` | `conversation_communications(assignment_source, reviewed)` | Find unreviewed assignments. |
| `idx_cp_contact` | `conversation_participants(contact_id)` | Conversations involving a contact. |
| `idx_cp_address` | `conversation_participants(address)` | Conversations involving an address. |
| `idx_commpart_address` | `communication_participants(address)` | Messages sent to an address. |
| `idx_commpart_contact` | `communication_participants(contact_id)` | Messages involving a contact. |

### Contact resolution

| Index | Column(s) | Supports |
|-------|-----------|----------|
| `idx_ci_contact` | `contact_identifiers(contact_id)` | All identifiers for a contact. |
| `idx_ci_status` | `contact_identifiers(status)` | Filter active identifiers. |

### Companies

| Index | Column(s) | Supports |
|-------|-----------|----------|
| `idx_companies_name` | `companies(name)` UNIQUE | Company lookup by name (also enforces uniqueness). |
| `idx_companies_domain` | `companies(domain)` | Company lookup by domain. |
| `idx_contacts_company` | `contacts(company_id)` | All contacts at a company. |

### Other tables

| Index | Column(s) | Supports |
|-------|-----------|----------|
| `idx_projects_parent` | `projects(parent_id)` | Child project lookup. |
| `idx_topics_project` | `topics(project_id)` | Topics in a project. |
| `idx_attachments_comm` | `attachments(communication_id)` | Attachments for a communication. |
| `idx_sync_log_account` | `sync_log(account_id)` | Sync history for an account. |
| `idx_views_owner` | `views(owner_id)` | Views owned by a user. |
| `idx_alerts_view` | `alerts(view_id)` | Alerts for a view. |
| `idx_triage_rules_match` | `triage_rules(match_type, match_value)` | Rule lookup. |
| `idx_relationships_from` | `relationships(from_entity_id)` | Relationships from a contact. |
| `idx_relationships_to` | `relationships(to_entity_id)` | Relationships to a contact. |

### Correction tables

| Index | Column(s) | Supports |
|-------|-----------|----------|
| `idx_ac_communication` | `assignment_corrections(communication_id)` | Corrections for a communication. |
| `idx_tc_communication` | `triage_corrections(communication_id)` | Triage corrections. |
| `idx_tc_sender_domain` | `triage_corrections(sender_domain)` | Domain-based triage patterns. |
| `idx_cc_conversation` | `conversation_corrections(conversation_id)` | Conversation corrections. |

---

## Serialization Layer (`models.py`)

The Python dataclasses include `to_row()` and `from_row()` methods that
handle conversion between in-memory objects and database rows.

### `Company`

| Method | Direction | Notes |
|--------|-----------|-------|
| `to_row(company_id=None, created_by=None, updated_by=None)` | Object -> `companies` row | Generates UUID if not provided.  Passes through audit fields. |
| `from_row(row)` | `companies` row -> Object | Maps name, domain, industry, description, status. |

### `KnownContact`

| Method | Direction | Notes |
|--------|-----------|-------|
| `to_row(contact_id=None, company_id=None, created_by=None, updated_by=None)` | Object -> `(contacts, contact_identifiers)` tuple | Returns two dicts.  Lowercases email.  Sets `source='google_contacts'`.  Includes `company_id` and audit columns. |
| `from_row(row, email=None)` | `contacts` JOIN row -> Object | Resolves email from `value` column or explicit kwarg. |

### `ParsedEmail`

| Method | Direction | Notes |
|--------|-----------|-------|
| `to_row(account_id, communication_id=None, account_email='')` | Object -> `communications` row | Computes `direction` from sender vs account email.  Formats `date` as ISO 8601. |
| `recipient_rows(communication_id)` | Object -> `communication_participants` rows | Returns list of dicts, one per To/CC address. |
| `from_row(row, recipients=None)` | `communications` row -> Object | Parses ISO 8601 date.  Splits recipients by role. |

### `Conversation`

| Method | Direction | Notes |
|--------|-----------|-------|
| `to_row(conversation_id=None, created_by=None, updated_by=None)` | Object -> `conversations` row | Computes counts and date range from emails list.  Initializes AI fields to NULL.  Includes audit columns. |
| `from_row(row, emails=None)` | `conversations` row -> Object | Uses row `id` as `thread_id`. |

### `Project`

| Method | Direction | Notes |
|--------|-----------|-------|
| `to_row(project_id=None, created_by=None, updated_by=None)` | Object -> `projects` row | Includes audit columns. |
| `from_row(row)` | `projects` row -> Object | |

### `Topic`

| Method | Direction | Notes |
|--------|-----------|-------|
| `to_row(topic_id=None, created_by=None, updated_by=None)` | Object -> `topics` row | Includes audit columns. |
| `from_row(row)` | `topics` row -> Object | |

### `Relationship`

| Method | Direction | Notes |
|--------|-----------|-------|
| `to_row(relationship_id=None)` | Object -> `relationships` row | Packs metrics into JSON `properties` blob. |
| `from_row(row)` | `relationships` row -> Object | Extracts metrics from JSON. |

### `ConversationSummary`

| Method | Direction | Notes |
|--------|-----------|-------|
| `to_update_dict()` | Object -> partial UPDATE dict | JSON-serializes action_items/topics.  Sets `ai_summarized_at`. |
| `from_conversation_row(row)` | `conversations` row -> Object or None | Returns None if not yet summarized. |

### `FilterReason` mapping

| Enum value | DB string |
|------------|-----------|
| `NO_KNOWN_CONTACTS` | `no_known_contacts` |
| `AUTOMATED_SENDER` | `automated_sender` |
| `AUTOMATED_SUBJECT` | `automated_subject` |
| `MARKETING` | `marketing` |

---

## Data Flows

### Flow 1: Contact Sync (with Company Resolution)

```
sync_contacts(creds)
|  +- contacts_client.fetch_contacts(creds)
|  |   -> list[KnownContact]  (with company from Google organizations)
|  |
|  +- get_connection()
|  +- for each KnownContact:
|      +- _resolve_company_id(conn, kc.company, now)
|      |   +- SELECT id FROM companies WHERE name = ?
|      |   +- if not found: INSERT INTO companies -> new company_id
|      |   +- return company_id (or None if no company)
|      |
|      +- SELECT contact_id FROM contact_identifiers WHERE type='email' AND value=?
|      +- if exists:
|      |   +- UPDATE contacts SET name, company, company_id, updated_at
|      +- if new:
|          +- INSERT INTO contacts (with company, company_id)
|          +- INSERT INTO contact_identifiers
```

### Flow 2: Initial Sync

```
initial_sync(account_id)
|  +- INSERT sync_log (status='running')
|  +- load_contact_index()
|  |
|  +- LOOP (paginated):
|  |   +- fetch_threads() -> list[list[ParsedEmail]]
|  |   +- for each thread:
|  |       +- _store_thread(conn, ...)
|  |           +- strip_quotes() on each email body
|  |           +- INSERT conversations (new thread)
|  |           +- for each email:
|  |           |   +- INSERT OR IGNORE communications
|  |           |   +- INSERT OR IGNORE conversation_communications
|  |           |   +- INSERT OR IGNORE communication_participants
|  |           +- for each participant:
|  |               +- UPSERT conversation_participants
|  |
|  +- get_history_id() -> current historyId
|  +- UPDATE provider_accounts SET sync_cursor, initial_sync_done=1
|  +- UPDATE sync_log (status='completed')
```

### Flow 3: Incremental Sync

```
incremental_sync(account_id)
|  +- SELECT sync_cursor FROM provider_accounts
|  +- INSERT sync_log (cursor_before, status='running')
|  +- load_contact_index()
|  |
|  +- fetch_history(cursor_before) -> (added_ids, deleted_ids)
|  +- PROCESS ADDITIONS:
|  |   +- fetch_messages(added_ids)
|  |   +- Group by thread_id
|  |   +- for each thread: _store_thread(...)
|  |       +- if existing conversation gained new communications:
|  |           UPDATE conversations SET ai_summarized_at=NULL  <- re-summarization trigger
|  |
|  +- PROCESS DELETIONS:
|  |   +- DELETE FROM communications WHERE provider_message_id = ?
|  |   +- UPDATE conversations SET communication_count = recount
|  |
|  +- UPDATE provider_accounts SET sync_cursor=new_historyId
|  +- UPDATE sync_log (status='completed')
```

### Flow 4: Conversation Processing (Triage + Summarize)

```
process_conversations(account_id, user_email)
|  +- load_contact_index()
|  +- SELECT * FROM conversations
|  |   WHERE triage_result IS NULL AND ai_summarized_at IS NULL
|  |
|  +- for each conversation:
|      +- Load communications via conversation_communications JOIN
|      +- Reconstruct Conversation + ParsedEmail objects
|      +- Match participants to contacts
|      |
|      +- triage_conversations([conv], user_email)
|      +- IF FILTERED:
|      |   +- UPDATE conversations SET triage_result = '<reason>'
|      +- IF KEPT:
|          +- summarize_conversation(conv, client)
|          +- UPDATE conversations SET ai_summary, ai_status, ...
|          +- _store_tags(conversation_id, key_topics)
|              +- INSERT tags ON CONFLICT(name) DO NOTHING
|              +- INSERT OR IGNORE conversation_tags
```

### Flow 5: Relationship Inference

```
infer_relationships()
|  +- Build canonical contact map (dedup by name)
|  +- Query co-occurrence from conversation_participants
|  +- For each contact pair:
|  |   +- Compute strength = 0.4*conv_score + 0.3*msg_score + 0.3*recency
|  +- UPSERT relationships ON CONFLICT DO UPDATE
```

### Flow 6: Bulk Auto-Assign

```
auto_assign.find_matching_topics(project_id)
|  +- Load topics for project
|  +- Load unassigned conversations with their tags
|  +- Score each conversation against each topic:
|  |   +- Tag match: 2 pts each (case-insensitive substring)
|  |   +- Title match: 1 pt
|  |   +- Pick highest score (alpha tiebreak)
|  +- return AutoAssignReport

auto_assign.apply_assignments(assignments)
|  +- UPDATE conversations SET topic_id = ? WHERE id = ?
```

---

## UPSERT and Idempotency Patterns

| Table | UNIQUE constraint | Write pattern | Effect on duplicate |
|-------|-------------------|---------------|---------------------|
| `provider_accounts` | `(provider, email_address)` | Check-then-insert | Returns existing ID |
| `companies` | `name` | Check-then-insert in `_resolve_company_id()` | Returns existing ID |
| `conversations` | *(check via communications JOIN)* | Check-then-insert in `_store_thread()` | Updates existing row |
| `communications` | `(account_id, provider_message_id)` | `INSERT OR IGNORE` | Silently skipped |
| `communication_participants` | `(communication_id, address, role)` | `INSERT OR IGNORE` | Silently skipped |
| `contacts` | *(via contact_identifiers)* | Check `contact_identifiers(type, value)` then insert/update | Name/company updated |
| `contact_identifiers` | `(type, value)` | Check-then-insert | Existing row reused |
| `conversation_participants` | `(conversation_id, address)` | `INSERT ... ON CONFLICT DO UPDATE` | Counts/dates refreshed |
| `conversation_communications` | `(conversation_id, communication_id)` | `INSERT OR IGNORE` | Silently skipped |
| `tags` | `name` | `INSERT ... ON CONFLICT(name) DO NOTHING` | Existing row reused |
| `conversation_tags` | `(conversation_id, tag_id)` | `INSERT OR IGNORE` | Silently skipped |
| `relationships` | `(from_entity_id, to_entity_id, relationship_type)` | `INSERT ... ON CONFLICT DO UPDATE` | Properties refreshed |

---

## Configuration

| Setting | Env variable | Default | Description |
|---------|-------------|---------|-------------|
| `DB_PATH` | `POC_DB_PATH` | `data/crm_extender.db` | Path to the SQLite database file.  Parent directories are created automatically by `init_db()`. |

The database file and its WAL/SHM companions are excluded from version
control via `.gitignore` (`data/` directory).
