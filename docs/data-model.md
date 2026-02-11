# Data Model & Database Design

This document describes the persistent data layer that backs the CRM
Extender pipeline.  It covers the SQLite schema (v8, 46 tables), every
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
| `poc/config.py` | `DB_PATH`, `CRM_TIMEZONE`, auth, and session settings |
| `poc/relationship_types.py` | Relationship type CRUD (create, list, get, update, delete) |
| `poc/enrichment_provider.py` | Enrichment provider interface, registry, SourceTier enum |
| `poc/enrichment_pipeline.py` | Enrichment orchestration, conflict resolution, field apply |
| `poc/website_scraper.py` | Website scraper enrichment provider (crawl + extract) |
| `poc/domain_resolver.py` | Domain-to-company resolution (public domain list, bulk backfill) |
| `poc/scoring.py` | Relationship strength scoring (5-factor composite, per-company/contact) |
| `poc/migrate_to_v2.py` | Schema migration: v1 (8-table) to v2 (21-table) |
| `poc/migrate_to_v3.py` | Schema migration: v2 to v3 (companies + audit columns) |
| `poc/migrate_to_v4.py` | Schema migration: v3 to v4 (relationship types FK) |
| `poc/migrate_to_v5.py` | Schema migration: v4 to v5 (bidirectional relationships) |
| `poc/migrate_to_v6.py` | Schema migration: v5 to v6 (events system) |
| `poc/migrate_to_v7.py` | Schema migration: v6 to v7 (company intelligence) |
| `poc/migrate_to_v8.py` | Schema migration: v7 to v8 (multi-user, customers, sessions, settings) |
| `poc/session.py` | Session CRUD (create, get, delete, cleanup) |
| `poc/settings.py` | Settings CRUD with 4-level cascade resolution |
| `poc/access.py` | Tenant-scoped query helpers (visible contacts/companies/conversations) |
| `poc/passwords.py` | Password hashing (`hash_password`) and verification (`verify_password`) using bcrypt |
| `poc/web/middleware.py` | `AuthMiddleware` — session cookie validation, bypass mode, user context injection |
| `poc/web/routes/auth_routes.py` | Login/logout routes: `GET/POST /login`, `POST /logout` |
| `poc/web/dependencies.py` | FastAPI dependencies: `get_current_user` (401), `require_admin` (403) |

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
| v4 | 23 | Relationship types: added `relationship_types` table with FK from `relationships`, seed types (KNOWS, EMPLOYEE, REPORTS_TO, WORKS_WITH, PARTNER, VENDOR) |
| v5 | 23 | Bidirectional relationships: added `is_bidirectional` to `relationship_types`, `paired_relationship_id` to `relationships` |
| v6 | 26 | Events system: added `events`, `event_participants`, `event_conversations` tables for calendar tracking |
| v7 | 39 | Company intelligence: added `company_identifiers`, `company_hierarchy`, `company_merges`, `company_social_profiles`, `contact_social_profiles`, `enrichment_runs`, `enrichment_field_values`, `entity_scores`, `monitoring_preferences`, `entity_assets`, `addresses`, `phone_numbers`, `email_addresses`.  New columns on `companies`: `website`, `stock_symbol`, `size_range`, `employee_count`, `founded_year`, `revenue_range`, `funding_total`, `funding_stage`, `headquarters_location`. |
| v8 | 46 | Multi-user & multi-tenant: added `customers` (tenant table), `sessions`, `user_contacts`, `user_companies`, `user_provider_accounts`, `conversation_shares`, `settings`.  Recreated `users` with `customer_id` FK, `password_hash`, `google_sub`, role values `admin`/`user`.  Added `customer_id` column to `provider_accounts`, `contacts`, `companies`, `conversations`, `projects`, `tags`, `relationship_types`. |

---

## Entity-Relationship Diagram

```
+------------------+
|    customers     |
|  (tenant)        |
|------------------|
| PK id            |
|    name          |
|    slug (UNIQ)   |
|    is_active     |
+--------+---------+
         |
         | FK customer_id
         |
+--------+---------+
|      users       |
|------------------|     +-------------------+
| PK id            |     |    companies      |
| FK customer_id   |     |-------------------|
|    email         |     | PK id             |
|    name          |     | FK customer_id    |
|    role          |     |    name (UNIQ)    |
|    is_active     |     |    domain         |
|    password_hash |     |    industry       |
|    google_sub    |     |    status         |
+--------+---------+     |    created_by ----+---> users
         |               |    updated_by ----+---> users
         | FK created_by +--------+----------+
         | FK updated_by
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
| `relationship_types` | `relationships` | 1:N | `relationship_type_id` | RESTRICT |
| `contacts` | `relationships` (from) | 1:N | `from_entity_id` | *(no FK)* |
| `contacts` | `relationships` (to) | 1:N | `to_entity_id` | *(no FK)* |
| `relationships` | `relationships` (pair) | 1:1 | `paired_relationship_id` | SET NULL |
| `provider_accounts` | `events` | 1:N | `account_id` | SET NULL |
| `events` | `events` (recurring) | 1:N | `recurring_event_id` | SET NULL |
| `events` | `event_participants` | 1:N | `event_id` | CASCADE |
| `events` | `event_conversations` | 1:N | `event_id` | CASCADE |
| `conversations` | `event_conversations` | 1:N | `conversation_id` | CASCADE |
| `companies` | `company_identifiers` | 1:N | `company_id` | CASCADE |
| `companies` | `company_hierarchy` (parent) | 1:N | `parent_company_id` | CASCADE |
| `companies` | `company_hierarchy` (child) | 1:N | `child_company_id` | CASCADE |
| `companies` | `company_social_profiles` | 1:N | `company_id` | CASCADE |
| `contacts` | `contact_social_profiles` | 1:N | `contact_id` | CASCADE |
| `enrichment_runs` | `enrichment_field_values` | 1:N | `enrichment_run_id` | CASCADE |
| `customers` | `users` | 1:N | `customer_id` | CASCADE |
| `customers` | `provider_accounts` | 1:N | `customer_id` | *(nullable)* |
| `customers` | `contacts` | 1:N | `customer_id` | *(nullable)* |
| `customers` | `companies` | 1:N | `customer_id` | *(nullable)* |
| `customers` | `conversations` | 1:N | `customer_id` | *(nullable)* |
| `customers` | `projects` | 1:N | `customer_id` | *(nullable)* |
| `customers` | `tags` | 1:N | `customer_id` | *(nullable)* |
| `customers` | `relationship_types` | 1:N | `customer_id` | *(nullable)* |
| `customers` | `sessions` | 1:N | `customer_id` | CASCADE |
| `customers` | `settings` | 1:N | `customer_id` | CASCADE |
| `users` | `sessions` | 1:N | `user_id` | CASCADE |
| `users` | `user_contacts` | 1:N | `user_id` | CASCADE |
| `users` | `user_companies` | 1:N | `user_id` | CASCADE |
| `users` | `user_provider_accounts` | 1:N | `user_id` | CASCADE |
| `users` | `conversation_shares` | 1:N | `user_id` | CASCADE |
| `users` | `settings` | 1:N | `user_id` | CASCADE |
| `contacts` | `user_contacts` | 1:N | `contact_id` | CASCADE |
| `companies` | `user_companies` | 1:N | `company_id` | CASCADE |
| `provider_accounts` | `user_provider_accounts` | 1:N | `account_id` | CASCADE |
| `conversations` | `conversation_shares` | 1:N | `conversation_id` | CASCADE |

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

### 0. `customers` (tenant)

Top-level tenant table.  All data is scoped to a customer.  Phase 1
creates a single default customer (`cust-default`); full multi-tenant
support is planned for a future release.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | TEXT | **PK** | Stable identifier (e.g. `'cust-default'`). |
| `name` | TEXT | NOT NULL | Organization name. |
| `slug` | TEXT | NOT NULL, **UNIQUE** | URL-safe identifier. |
| `is_active` | INTEGER | DEFAULT 1 | Boolean (0/1). |
| `created_at` | TEXT | NOT NULL | ISO 8601 timestamp. |
| `updated_at` | TEXT | NOT NULL | ISO 8601 timestamp. |

**Populated by:** `migrate_to_v8.py` (seeds default customer),
`hierarchy.bootstrap_user()` (ensures default customer exists).

### 1. `users`

User accounts within a customer (tenant).  FK target for
`created_by`/`updated_by` columns throughout the schema.  Supports
two authentication methods: Google OAuth (`google_sub`) and
username/password (`password_hash`).

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | TEXT | **PK** | UUID v4. |
| `customer_id` | TEXT | NOT NULL, FK -> `customers(id)` | Tenant.  ON DELETE CASCADE. |
| `email` | TEXT | NOT NULL | User's email address. |
| `name` | TEXT | | Display name. |
| `role` | TEXT | DEFAULT `'user'` | CHECK: `'admin'` or `'user'`. |
| `is_active` | INTEGER | DEFAULT 1 | Boolean (0/1). |
| `password_hash` | TEXT | | bcrypt hash.  NULL for Google-only users. |
| `google_sub` | TEXT | | Google OAuth subject ID for login. |
| `created_at` | TEXT | NOT NULL | ISO 8601 timestamp. |
| `updated_at` | TEXT | NOT NULL | ISO 8601 timestamp. |

**Unique constraint:** `(customer_id, email)` -- email uniqueness is
scoped to the customer, not global.

**Populated by:** `hierarchy.bootstrap_user()`, which auto-creates a
user from the first `provider_accounts` email with `role='admin'`
and `customer_id='cust-default'`.

### 2. `companies`

Companies that contacts can be linked to.  Auto-created during contact
sync when a contact has an organization in Google Contacts, or manually
via the CLI.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | TEXT | **PK** | UUID v4. |
| `customer_id` | TEXT | FK -> `customers(id)` | Tenant scope (v8). |
| `name` | TEXT | NOT NULL, **UNIQUE** | Company name.  The unique index `idx_companies_name` enforces no duplicates. |
| `domain` | TEXT | | Company domain (e.g. `'acme.com'`). |
| `industry` | TEXT | | Industry classification. |
| `description` | TEXT | | Free-text description. |
| `website` | TEXT | | Full website URL (v7). |
| `stock_symbol` | TEXT | | Stock ticker symbol (v7). |
| `size_range` | TEXT | | Employee size range, e.g. `'51-200'` (v7). |
| `employee_count` | INTEGER | | Exact employee count (v7). |
| `founded_year` | INTEGER | | Year the company was founded (v7). |
| `revenue_range` | TEXT | | Revenue range, e.g. `'$10M-$50M'` (v7). |
| `funding_total` | TEXT | | Total funding raised (v7). |
| `funding_stage` | TEXT | | Funding stage, e.g. `'Series B'` (v7). |
| `headquarters_location` | TEXT | | HQ location string (v7). |
| `status` | TEXT | DEFAULT `'active'` | Company status. |
| `created_by` | TEXT | FK -> `users(id)` | User who created this record.  ON DELETE SET NULL. |
| `updated_by` | TEXT | FK -> `users(id)` | User who last updated this record.  ON DELETE SET NULL. |
| `created_at` | TEXT | NOT NULL | ISO 8601 timestamp. |
| `updated_at` | TEXT | NOT NULL | ISO 8601 timestamp. |

**Populated by:** `sync._resolve_company_id()` (auto-creates during
contact sync from Google organization names), `hierarchy.create_company()`
(manual creation via CLI).  When a company is created with a non-public
domain, that domain is automatically added to `company_identifiers` via
`ensure_domain_identifier()`.

**Deleted by:** `hierarchy.delete_company()`.  Contacts with
`company_id` pointing to the deleted company get `company_id` SET NULL
via the FK constraint.

### 3. `provider_accounts`

Tracks connected accounts (email, future: phone, chat) and their
synchronization state.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | TEXT | **PK** | UUID v4.  Generated by `sync.register_account()`. |
| `customer_id` | TEXT | FK -> `customers(id)` | Tenant scope (v8). |
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
| `customer_id` | TEXT | FK -> `customers(id)` | Tenant scope (v8). |
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
| `customer_id` | TEXT | FK -> `customers(id)` | Tenant scope (v8). |
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
| `customer_id` | TEXT | FK -> `customers(id)` | Tenant scope (v8). |
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
| `customer_id` | TEXT | FK -> `customers(id)` | Tenant scope (v8). |
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

### 23. `relationship_types`

Defines the vocabulary of relationship types.  Each type specifies entity
types, directional labels, and whether relationships are bidirectional.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | TEXT | **PK** | Stable identifier (e.g., `rt-knows`). |
| `customer_id` | TEXT | FK -> `customers(id)` | Tenant scope (v8).  NULL for system seed types. |
| `name` | TEXT | NOT NULL, **UNIQUE** | Type name (e.g., `KNOWS`). |
| `from_entity_type` | TEXT | NOT NULL, DEFAULT `'contact'` | CHECK: `contact` or `company`. |
| `to_entity_type` | TEXT | NOT NULL, DEFAULT `'contact'` | CHECK: `contact` or `company`. |
| `forward_label` | TEXT | NOT NULL | Label from "from" entity (e.g., "Knows"). |
| `reverse_label` | TEXT | NOT NULL | Label from "to" entity (e.g., "Knows"). |
| `is_system` | INTEGER | NOT NULL, DEFAULT 0 | System types cannot be deleted. |
| `is_bidirectional` | INTEGER | NOT NULL, DEFAULT 0 | Bidirectional types store paired rows. |
| `description` | TEXT | | Free-text description. |
| `created_by` | TEXT | FK -> `users(id)` | ON DELETE SET NULL. |
| `updated_by` | TEXT | FK -> `users(id)` | ON DELETE SET NULL. |
| `created_at` | TEXT | NOT NULL | ISO 8601 timestamp. |
| `updated_at` | TEXT | NOT NULL | ISO 8601 timestamp. |

**Seed data:** 6 default types are inserted on `init_db()`: KNOWS
(system, bidirectional), EMPLOYEE, REPORTS_TO, WORKS_WITH
(bidirectional), PARTNER (bidirectional), VENDOR.

### 24. `events`

Calendar items: meetings, birthdays, anniversaries, conferences,
deadlines, and other calendar events.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | TEXT | **PK** | UUID v4. |
| `title` | TEXT | NOT NULL | Event name/summary. |
| `description` | TEXT | | Extended description. |
| `event_type` | TEXT | NOT NULL, DEFAULT `'meeting'` | CHECK: `meeting`, `birthday`, `anniversary`, `conference`, `deadline`, `other`. |
| `start_date` | TEXT | | ISO 8601 date for all-day events. |
| `start_datetime` | TEXT | | ISO 8601 datetime for timed events. |
| `end_date` | TEXT | | ISO 8601 date for all-day event end. |
| `end_datetime` | TEXT | | ISO 8601 datetime for timed event end. |
| `is_all_day` | INTEGER | DEFAULT 0 | Boolean. |
| `timezone` | TEXT | | IANA timezone identifier. |
| `recurrence_rule` | TEXT | | iCalendar RRULE string. |
| `recurrence_type` | TEXT | DEFAULT `'none'` | CHECK: `none`, `daily`, `weekly`, `monthly`, `yearly`. |
| `recurring_event_id` | TEXT | FK -> `events(id)` | Self-FK for modified instances. ON DELETE SET NULL. |
| `location` | TEXT | | Event location. |
| `provider_event_id` | TEXT | | Provider's native event ID. |
| `provider_calendar_id` | TEXT | | Provider's calendar ID. |
| `account_id` | TEXT | FK -> `provider_accounts(id)` | ON DELETE SET NULL. |
| `source` | TEXT | DEFAULT `'manual'` | Origin: `manual`, `google_calendar`, etc. |
| `status` | TEXT | DEFAULT `'confirmed'` | CHECK: `confirmed`, `tentative`, `cancelled`. |
| `created_by` | TEXT | FK -> `users(id)` | ON DELETE SET NULL. |
| `updated_by` | TEXT | FK -> `users(id)` | ON DELETE SET NULL. |
| `created_at` | TEXT | NOT NULL | ISO 8601 timestamp. |
| `updated_at` | TEXT | NOT NULL | ISO 8601 timestamp. |

**Unique constraint:** `(account_id, provider_event_id)`.

### 25. `event_participants`

Many-to-many join linking events to contacts and companies.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `event_id` | TEXT | NOT NULL, FK -> `events(id)` | ON DELETE CASCADE. |
| `entity_type` | TEXT | NOT NULL | CHECK: `contact` or `company`. |
| `entity_id` | TEXT | NOT NULL | UUID of the contact or company. |
| `role` | TEXT | DEFAULT `'attendee'` | Participant role (free text). |
| `rsvp_status` | TEXT | | CHECK: NULL or `accepted`, `declined`, `tentative`, `needs_action`. |

**Primary key:** `(event_id, entity_type, entity_id)`.

### 26. `event_conversations`

Many-to-many join linking events to conversations.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `event_id` | TEXT | NOT NULL, FK -> `events(id)` | ON DELETE CASCADE. |
| `conversation_id` | TEXT | NOT NULL, FK -> `conversations(id)` | ON DELETE CASCADE. |
| `created_at` | TEXT | NOT NULL | ISO 8601 timestamp. |

**Primary key:** `(event_id, conversation_id)`.

### 27. `company_identifiers`

Multi-domain and multi-identifier support for companies.  Allows a
company to be found by any of its known domains or identifiers.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | TEXT | **PK** | UUID v4. |
| `company_id` | TEXT | NOT NULL, FK -> `companies(id)` | ON DELETE CASCADE. |
| `type` | TEXT | NOT NULL, DEFAULT `'domain'` | Identifier type. |
| `value` | TEXT | NOT NULL | The identifier value. |
| `is_primary` | INTEGER | DEFAULT 0 | Boolean. |
| `source` | TEXT | | Origin of this identifier. |
| `created_at` | TEXT | NOT NULL | ISO 8601 timestamp. |
| `updated_at` | TEXT | NOT NULL | ISO 8601 timestamp. |

**Unique constraint:** `(type, value)`.

### 28. `company_hierarchy`

Parent/child organizational structure between companies.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | TEXT | **PK** | UUID v4. |
| `parent_company_id` | TEXT | NOT NULL, FK -> `companies(id)` | ON DELETE CASCADE. |
| `child_company_id` | TEXT | NOT NULL, FK -> `companies(id)` | ON DELETE CASCADE. |
| `hierarchy_type` | TEXT | NOT NULL | CHECK: `subsidiary`, `division`, `acquisition`, `spinoff`. |
| `effective_date` | TEXT | | When the relationship started. |
| `end_date` | TEXT | | When the relationship ended. |
| `metadata` | TEXT | | JSON blob. |
| `created_by` | TEXT | FK -> `users(id)` | ON DELETE SET NULL. |
| `updated_by` | TEXT | FK -> `users(id)` | ON DELETE SET NULL. |
| `created_at` | TEXT | NOT NULL | ISO 8601 timestamp. |
| `updated_at` | TEXT | NOT NULL | ISO 8601 timestamp. |

**CHECK constraint:** `parent_company_id != child_company_id`.

### 29. `company_merges`

Audit log for company merge operations.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | TEXT | **PK** | UUID v4. |
| `surviving_company_id` | TEXT | NOT NULL, FK -> `companies(id)` | Company that survives the merge. |
| `absorbed_company_id` | TEXT | NOT NULL | Company that was absorbed (may no longer exist). |
| `absorbed_company_snapshot` | TEXT | NOT NULL | JSON snapshot of the absorbed company at merge time. |
| `contacts_reassigned` | INTEGER | DEFAULT 0 | Count of contacts moved. |
| `relationships_reassigned` | INTEGER | DEFAULT 0 | Count of relationships moved. |
| `events_reassigned` | INTEGER | DEFAULT 0 | Count of events moved. |
| `relationships_deduplicated` | INTEGER | DEFAULT 0 | Duplicate relationships removed. |
| `merged_by` | TEXT | FK -> `users(id)` | ON DELETE SET NULL. |
| `merged_at` | TEXT | NOT NULL | ISO 8601 timestamp. |

### 30. `company_social_profiles`

Social media profiles linked to companies.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | TEXT | **PK** | UUID v4. |
| `company_id` | TEXT | NOT NULL, FK -> `companies(id)` | ON DELETE CASCADE. |
| `platform` | TEXT | NOT NULL | Platform name (e.g. `'linkedin'`, `'twitter'`). |
| `profile_url` | TEXT | NOT NULL | Full URL to profile. |
| `username` | TEXT | | Username/handle. |
| `verified` | INTEGER | DEFAULT 0 | Boolean. |
| `follower_count` | INTEGER | | Follower count. |
| `bio` | TEXT | | Profile bio. |
| `last_scanned_at` | TEXT | | Last enrichment scan. |
| `last_post_at` | TEXT | | Last post timestamp. |
| `source` | TEXT | | How discovered. |
| `confidence` | REAL | | Confidence score. |
| `status` | TEXT | DEFAULT `'active'` | Profile status. |
| `created_at` | TEXT | NOT NULL | ISO 8601 timestamp. |
| `updated_at` | TEXT | NOT NULL | ISO 8601 timestamp. |

**Unique constraint:** `(company_id, platform, profile_url)`.

### 31. `contact_social_profiles`

Social media profiles linked to contacts.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | TEXT | **PK** | UUID v4. |
| `contact_id` | TEXT | NOT NULL, FK -> `contacts(id)` | ON DELETE CASCADE. |
| `platform` | TEXT | NOT NULL | Platform name. |
| `profile_url` | TEXT | NOT NULL | Full URL to profile. |
| `username` | TEXT | | Username/handle. |
| `headline` | TEXT | | Profile headline. |
| `connection_degree` | INTEGER | | LinkedIn connection degree. |
| `mutual_connections` | INTEGER | | Mutual connection count. |
| `verified` | INTEGER | DEFAULT 0 | Boolean. |
| `follower_count` | INTEGER | | Follower count. |
| `bio` | TEXT | | Profile bio. |
| `last_scanned_at` | TEXT | | Last enrichment scan. |
| `last_post_at` | TEXT | | Last post timestamp. |
| `source` | TEXT | | How discovered. |
| `confidence` | REAL | | Confidence score. |
| `status` | TEXT | DEFAULT `'active'` | Profile status. |
| `created_at` | TEXT | NOT NULL | ISO 8601 timestamp. |
| `updated_at` | TEXT | NOT NULL | ISO 8601 timestamp. |

**Unique constraint:** `(contact_id, platform, profile_url)`.

### 32. `enrichment_runs`

Tracks each enrichment operation (entity-agnostic).

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | TEXT | **PK** | UUID v4. |
| `entity_type` | TEXT | NOT NULL | CHECK: `company` or `contact`. |
| `entity_id` | TEXT | NOT NULL | UUID of the entity being enriched. |
| `provider` | TEXT | NOT NULL | Provider name (e.g. `'website_scraper'`). |
| `status` | TEXT | NOT NULL, DEFAULT `'pending'` | CHECK: `pending`, `running`, `completed`, `failed`. |
| `started_at` | TEXT | | When the run started. |
| `completed_at` | TEXT | | When the run completed. |
| `error_message` | TEXT | | Error message if failed. |
| `created_at` | TEXT | NOT NULL | ISO 8601 timestamp. |

### 33. `enrichment_field_values`

Field-level provenance for each value discovered during enrichment.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | TEXT | **PK** | UUID v4. |
| `enrichment_run_id` | TEXT | NOT NULL, FK -> `enrichment_runs(id)` | ON DELETE CASCADE. |
| `field_name` | TEXT | NOT NULL | The field this value applies to. |
| `field_value` | TEXT | | The discovered value. |
| `confidence` | REAL | NOT NULL, DEFAULT 0.0 | Confidence score (0.0-1.0). |
| `is_accepted` | INTEGER | DEFAULT 0 | Whether this value was applied. |
| `created_at` | TEXT | NOT NULL | ISO 8601 timestamp. |

### 34. `entity_scores`

Precomputed intelligence scores for entities.  Currently used for
relationship strength scoring (`score_type = 'relationship_strength'`).

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | TEXT | **PK** | UUID v4. |
| `entity_type` | TEXT | NOT NULL | CHECK: `company` or `contact`. |
| `entity_id` | TEXT | NOT NULL | UUID of the entity. |
| `score_type` | TEXT | NOT NULL | Score category (e.g. `'relationship_strength'`). |
| `score_value` | REAL | NOT NULL, DEFAULT 0.0 | Numeric score (0.0–1.0 for relationship strength). |
| `factors` | TEXT | | JSON blob of contributing factors (e.g. `{"recency": 0.85, "frequency": 0.42, ...}`). |
| `computed_at` | TEXT | NOT NULL | When computed. |
| `triggered_by` | TEXT | | What triggered the computation (`'batch'`, `'cli'`, `'web'`, `'manual'`). |

**Unique constraint:** `(entity_type, entity_id, score_type)`.

**Populated by:** `scoring.upsert_entity_score()`, called from
`score_all_companies()`, `score_all_contacts()` (batch), CLI commands,
and web UI refresh buttons.  Uses `INSERT ... ON CONFLICT DO UPDATE`
for idempotent upserts.

### 35. `monitoring_preferences`

Per-entity monitoring tier configuration.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | TEXT | **PK** | UUID v4. |
| `entity_type` | TEXT | NOT NULL | CHECK: `company` or `contact`. |
| `entity_id` | TEXT | NOT NULL | UUID of the entity. |
| `monitoring_tier` | TEXT | NOT NULL, DEFAULT `'standard'` | CHECK: `high`, `standard`, `low`, `none`. |
| `tier_source` | TEXT | NOT NULL, DEFAULT `'default'` | CHECK: `manual`, `auto_suggested`, `default`. |
| `created_at` | TEXT | NOT NULL | ISO 8601 timestamp. |
| `updated_at` | TEXT | NOT NULL | ISO 8601 timestamp. |

**Unique constraint:** `(entity_type, entity_id)`.

### 36. `entity_assets`

Content-addressable storage references for entity assets (logos,
headshots, banners).

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | TEXT | **PK** | UUID v4. |
| `entity_type` | TEXT | NOT NULL | CHECK: `company` or `contact`. |
| `entity_id` | TEXT | NOT NULL | UUID of the entity. |
| `asset_type` | TEXT | NOT NULL | CHECK: `logo`, `headshot`, `banner`. |
| `hash` | TEXT | NOT NULL | Content hash for deduplication. |
| `mime_type` | TEXT | NOT NULL | MIME type of the asset. |
| `file_ext` | TEXT | NOT NULL | File extension. |
| `source` | TEXT | | How the asset was obtained. |
| `created_at` | TEXT | NOT NULL | ISO 8601 timestamp. |

### 37. `addresses`

Entity-agnostic multi-value addresses for companies and contacts.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | TEXT | **PK** | UUID v4. |
| `entity_type` | TEXT | NOT NULL | CHECK: `company` or `contact`. |
| `entity_id` | TEXT | NOT NULL | UUID of the entity. |
| `address_type` | TEXT | NOT NULL, DEFAULT `'headquarters'` | Address category. |
| `street` | TEXT | | Street address. |
| `city` | TEXT | | City. |
| `state` | TEXT | | State/province. |
| `postal_code` | TEXT | | Postal/ZIP code. |
| `country` | TEXT | | Country. |
| `is_primary` | INTEGER | DEFAULT 0 | Boolean. |
| `source` | TEXT | | How discovered. |
| `confidence` | REAL | | Confidence score. |
| `created_at` | TEXT | NOT NULL | ISO 8601 timestamp. |
| `updated_at` | TEXT | NOT NULL | ISO 8601 timestamp. |

### 38. `phone_numbers`

Entity-agnostic multi-value phone numbers for companies and contacts.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | TEXT | **PK** | UUID v4. |
| `entity_type` | TEXT | NOT NULL | CHECK: `company` or `contact`. |
| `entity_id` | TEXT | NOT NULL | UUID of the entity. |
| `phone_type` | TEXT | NOT NULL, DEFAULT `'main'` | Phone category. |
| `number` | TEXT | NOT NULL | Phone number. |
| `is_primary` | INTEGER | DEFAULT 0 | Boolean. |
| `source` | TEXT | | How discovered. |
| `confidence` | REAL | | Confidence score. |
| `created_at` | TEXT | NOT NULL | ISO 8601 timestamp. |
| `updated_at` | TEXT | NOT NULL | ISO 8601 timestamp. |

### 39. `email_addresses`

Entity-agnostic multi-value email addresses for companies and contacts.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | TEXT | **PK** | UUID v4. |
| `entity_type` | TEXT | NOT NULL | CHECK: `company` or `contact`. |
| `entity_id` | TEXT | NOT NULL | UUID of the entity. |
| `email_type` | TEXT | NOT NULL, DEFAULT `'general'` | Email category. |
| `address` | TEXT | NOT NULL | Email address. |
| `is_primary` | INTEGER | DEFAULT 0 | Boolean. |
| `source` | TEXT | | How discovered. |
| `confidence` | REAL | | Confidence score. |
| `created_at` | TEXT | NOT NULL | ISO 8601 timestamp. |
| `updated_at` | TEXT | NOT NULL | ISO 8601 timestamp. |

### 40. `sessions`

Server-side session store for authenticated users.  Session IDs are
stored in signed cookies.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | TEXT | **PK** | UUID v4, stored in the `crm_session` cookie. |
| `user_id` | TEXT | NOT NULL, FK -> `users(id)` | ON DELETE CASCADE. |
| `customer_id` | TEXT | NOT NULL, FK -> `customers(id)` | ON DELETE CASCADE. |
| `created_at` | TEXT | NOT NULL | ISO 8601 timestamp. |
| `expires_at` | TEXT | NOT NULL | ISO 8601 timestamp.  Default TTL: 30 days. |
| `ip_address` | TEXT | | Client IP at session creation. |
| `user_agent` | TEXT | | Client User-Agent at session creation. |

**Populated by:** `session.create_session()`.

**Cleaned up by:** `session.cleanup_expired_sessions()`.

### 41. `user_contacts` (per-user contact visibility)

Junction table linking users to contacts with visibility control.  A
contact is "public" if any user has `visibility = 'public'`; it is
"private" only if all linked users mark it private.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | TEXT | **PK** | UUID v4. |
| `user_id` | TEXT | NOT NULL, FK -> `users(id)` | ON DELETE CASCADE. |
| `contact_id` | TEXT | NOT NULL, FK -> `contacts(id)` | ON DELETE CASCADE. |
| `visibility` | TEXT | NOT NULL, DEFAULT `'public'` | CHECK: `'public'` or `'private'`. |
| `is_owner` | INTEGER | NOT NULL, DEFAULT 0 | Whether this user originally created/imported the contact. |
| `created_at` | TEXT | NOT NULL | ISO 8601 timestamp. |
| `updated_at` | TEXT | NOT NULL | ISO 8601 timestamp. |

**Unique constraint:** `(user_id, contact_id)`.

### 42. `user_companies` (per-user company visibility)

Junction table linking users to companies with visibility control.
Same visibility semantics as `user_contacts`.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | TEXT | **PK** | UUID v4. |
| `user_id` | TEXT | NOT NULL, FK -> `users(id)` | ON DELETE CASCADE. |
| `company_id` | TEXT | NOT NULL, FK -> `companies(id)` | ON DELETE CASCADE. |
| `visibility` | TEXT | NOT NULL, DEFAULT `'public'` | CHECK: `'public'` or `'private'`. |
| `is_owner` | INTEGER | NOT NULL, DEFAULT 0 | Whether this user originally created/imported the company. |
| `created_at` | TEXT | NOT NULL | ISO 8601 timestamp. |
| `updated_at` | TEXT | NOT NULL | ISO 8601 timestamp. |

**Unique constraint:** `(user_id, company_id)`.

### 43. `user_provider_accounts` (shared account access)

Links users to provider accounts.  An account owner can share access
with other users in the same customer.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | TEXT | **PK** | UUID v4. |
| `user_id` | TEXT | NOT NULL, FK -> `users(id)` | ON DELETE CASCADE. |
| `account_id` | TEXT | NOT NULL, FK -> `provider_accounts(id)` | ON DELETE CASCADE. |
| `role` | TEXT | NOT NULL, DEFAULT `'owner'` | CHECK: `'owner'` or `'shared'`. |
| `created_at` | TEXT | NOT NULL | ISO 8601 timestamp. |

**Unique constraint:** `(user_id, account_id)`.

### 44. `conversation_shares` (explicit sharing)

Allows users to explicitly share conversations with other users,
independent of provider account access.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | TEXT | **PK** | UUID v4. |
| `conversation_id` | TEXT | NOT NULL, FK -> `conversations(id)` | ON DELETE CASCADE. |
| `user_id` | TEXT | NOT NULL, FK -> `users(id)` | ON DELETE CASCADE. |
| `shared_by` | TEXT | FK -> `users(id)` | Who shared this conversation.  ON DELETE SET NULL. |
| `created_at` | TEXT | NOT NULL | ISO 8601 timestamp. |

**Unique constraint:** `(conversation_id, user_id)`.

### 45. `settings` (unified key-value)

Unified settings store for both system-wide (admin-editable) and
per-user preferences.  Supports a 4-level cascade resolution:
user-specific value -> system value -> setting_default -> hardcoded fallback.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | TEXT | **PK** | UUID v4. |
| `customer_id` | TEXT | NOT NULL, FK -> `customers(id)` | ON DELETE CASCADE. |
| `user_id` | TEXT | FK -> `users(id)` | NULL for system-scope settings.  ON DELETE CASCADE. |
| `scope` | TEXT | NOT NULL | CHECK: `'system'` or `'user'`. |
| `setting_name` | TEXT | NOT NULL | Setting key (e.g. `'timezone'`, `'date_format'`). |
| `setting_value` | TEXT | | Current value.  NULL means "use default". |
| `setting_description` | TEXT | | Human-readable description. |
| `setting_default` | TEXT | | Default value for this setting. |
| `created_at` | TEXT | NOT NULL | ISO 8601 timestamp. |
| `updated_at` | TEXT | NOT NULL | ISO 8601 timestamp. |

**Unique constraints:** Enforced via partial unique indexes (SQLite
NULL-safe):
- `idx_settings_system_unique` on `(customer_id, setting_name)` WHERE
  `scope = 'system'`
- `idx_settings_user_unique` on `(customer_id, user_id, setting_name)`
  WHERE `scope = 'user'`

**Populated by:** `settings.seed_default_settings()` (called during
migration and bootstrap), `settings.set_setting()` (manual updates).

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
| `idx_relationships_type` | `relationships(relationship_type_id)` | Relationships by type. |
| `idx_relationships_source` | `relationships(source)` | Relationships by source. |
| `idx_relationships_paired` | `relationships(paired_relationship_id)` | Paired row lookup. |

### Events

| Index | Column(s) | Supports |
|-------|-----------|----------|
| `idx_events_type` | `events(event_type)` | Filter by event type. |
| `idx_events_start_dt` | `events(start_datetime)` | Date-range queries for timed events. |
| `idx_events_start_date` | `events(start_date)` | Date-range queries for all-day events. |
| `idx_events_status` | `events(status)` | Filter by status. |
| `idx_events_account` | `events(account_id)` | Events by provider account. |
| `idx_events_recurring` | `events(recurring_event_id)` | Instances of a recurring event. |
| `idx_events_source` | `events(source)` | Filter by source. |
| `idx_events_provider` | `events(account_id, provider_event_id)` | Provider sync dedup lookup. |
| `idx_ep_entity` | `event_participants(entity_type, entity_id)` | Events for a contact/company. |
| `idx_ec_conversation` | `event_conversations(conversation_id)` | Events linked to a conversation. |

### Correction tables

| Index | Column(s) | Supports |
|-------|-----------|----------|
| `idx_ac_communication` | `assignment_corrections(communication_id)` | Corrections for a communication. |
| `idx_tc_communication` | `triage_corrections(communication_id)` | Triage corrections. |
| `idx_tc_sender_domain` | `triage_corrections(sender_domain)` | Domain-based triage patterns. |
| `idx_cc_conversation` | `conversation_corrections(conversation_id)` | Conversation corrections. |

### Company identifiers

| Index | Column(s) | Supports |
|-------|-----------|----------|
| `idx_coid_company` | `company_identifiers(company_id)` | All identifiers for a company. |
| `idx_coid_lookup` | `company_identifiers(type, value)` | Find company by identifier. |

### Company hierarchy

| Index | Column(s) | Supports |
|-------|-----------|----------|
| `idx_ch_parent` | `company_hierarchy(parent_company_id)` | Children of a company. |
| `idx_ch_child` | `company_hierarchy(child_company_id)` | Parents of a company. |
| `idx_ch_type` | `company_hierarchy(hierarchy_type)` | Filter by hierarchy type. |

### Company merges

| Index | Column(s) | Supports |
|-------|-----------|----------|
| `idx_cm_surviving` | `company_merges(surviving_company_id)` | Merge history for a company. |
| `idx_cm_absorbed` | `company_merges(absorbed_company_id)` | Find merges that absorbed a company. |

### Social profiles

| Index | Column(s) | Supports |
|-------|-----------|----------|
| `idx_csp_company` | `company_social_profiles(company_id)` | All social profiles for a company. |
| `idx_csp_platform` | `company_social_profiles(platform)` | Filter by platform. |
| `idx_ctsp_contact` | `contact_social_profiles(contact_id)` | All social profiles for a contact. |
| `idx_ctsp_platform` | `contact_social_profiles(platform)` | Filter by platform. |

### Enrichment

| Index | Column(s) | Supports |
|-------|-----------|----------|
| `idx_er_entity` | `enrichment_runs(entity_type, entity_id)` | Enrichment history for an entity. |
| `idx_er_provider` | `enrichment_runs(provider)` | Filter by provider. |
| `idx_er_status` | `enrichment_runs(status)` | Filter by run status. |
| `idx_efv_run` | `enrichment_field_values(enrichment_run_id)` | All field values for a run. |
| `idx_efv_field` | `enrichment_field_values(field_name, is_accepted)` | Accepted values for a field. |

### Entity scores and assets

| Index | Column(s) | Supports |
|-------|-----------|----------|
| `idx_es_entity_score` | `entity_scores(entity_type, entity_id, score_type)` UNIQUE | Score lookup (also enforces uniqueness). |
| `idx_es_score` | `entity_scores(score_type, score_value)` | Ranking by score type. |
| `idx_ea_entity` | `entity_assets(entity_type, entity_id)` | Assets for an entity. |
| `idx_ea_hash` | `entity_assets(hash)` | Content-addressable dedup. |

### Addresses, phones, emails

| Index | Column(s) | Supports |
|-------|-----------|----------|
| `idx_addr_entity` | `addresses(entity_type, entity_id)` | Addresses for an entity. |
| `idx_phone_entity` | `phone_numbers(entity_type, entity_id)` | Phone numbers for an entity. |
| `idx_email_entity` | `email_addresses(entity_type, entity_id)` | Email addresses for an entity. |

### Multi-user (v8)

| Index | Column(s) | Supports |
|-------|-----------|----------|
| `idx_sessions_user` | `sessions(user_id)` | All sessions for a user. |
| `idx_sessions_expires` | `sessions(expires_at)` | Cleanup of expired sessions. |
| `idx_uc_user` | `user_contacts(user_id)` | Contacts visible to a user. |
| `idx_uc_contact` | `user_contacts(contact_id)` | Users linked to a contact. |
| `idx_uco_user` | `user_companies(user_id)` | Companies visible to a user. |
| `idx_uco_company` | `user_companies(company_id)` | Users linked to a company. |
| `idx_upa_user` | `user_provider_accounts(user_id)` | Provider accounts for a user. |
| `idx_upa_account` | `user_provider_accounts(account_id)` | Users with access to an account. |
| `idx_cs_conversation` | `conversation_shares(conversation_id)` | Users a conversation is shared with. |
| `idx_cs_user` | `conversation_shares(user_id)` | Conversations shared with a user. |
| `idx_settings_customer` | `settings(customer_id)` | Settings for a customer. |
| `idx_settings_user` | `settings(user_id)` | Settings for a user. |
| `idx_settings_system_unique` | `settings(customer_id, setting_name)` WHERE `scope='system'` UNIQUE | System setting dedup. |
| `idx_settings_user_unique` | `settings(customer_id, user_id, setting_name)` WHERE `scope='user'` UNIQUE | User setting dedup. |
| `idx_pa_customer` | `provider_accounts(customer_id)` | Accounts in a tenant. |
| `idx_contacts_customer` | `contacts(customer_id)` | Contacts in a tenant. |
| `idx_companies_customer` | `companies(customer_id)` | Companies in a tenant. |
| `idx_conv_customer` | `conversations(customer_id)` | Conversations in a tenant. |
| `idx_projects_customer` | `projects(customer_id)` | Projects in a tenant. |
| `idx_tags_customer` | `tags(customer_id)` | Tags in a tenant. |

---

## Serialization Layer (`models.py`)

The Python dataclasses include `to_row()` and `from_row()` methods that
handle conversion between in-memory objects and database rows.

### `Customer`

| Method | Direction | Notes |
|--------|-----------|-------|
| `to_row(customer_id=None)` | Object -> `customers` row | Generates UUID if not provided. |
| `from_row(row)` | `customers` row -> Object | Maps name, slug, is_active. |

### `User`

| Method | Direction | Notes |
|--------|-----------|-------|
| `to_row(user_id=None)` | Object -> `users` row | Generates UUID if not provided.  Includes `customer_id`, `password_hash`, `google_sub`. |
| `from_row(row)` | `users` row -> Object | Role defaults to `'user'`.  `is_active` converted from int to bool. |

### `Session`

| Method | Direction | Notes |
|--------|-----------|-------|
| `to_row(session_id=None)` | Object -> `sessions` row | Generates UUID if not provided.  Includes `customer_id`, `expires_at`, `ip_address`, `user_agent`. |
| `from_row(row)` | `sessions` row -> Object | |

### `Setting`

| Method | Direction | Notes |
|--------|-----------|-------|
| `to_row(setting_id=None)` | Object -> `settings` row | Generates UUID if not provided.  Includes `customer_id`, `scope`, `setting_name`, `setting_value`, `user_id`. |
| `from_row(row)` | `settings` row -> Object | |

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

### `Event`

| Method | Direction | Notes |
|--------|-----------|-------|
| `to_row(event_id=None, created_by=None, updated_by=None)` | Object -> `events` row | Generates UUID if not provided.  Empty strings converted to NULL.  Sets `source` and audit columns. |
| `from_row(row)` | `events` row -> Object | Missing keys default to sensible values.  `is_all_day` converted from int to bool. |

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
|      +- Domain fallback (if company_id is still None):
|      |   +- resolve_company_for_email(conn, email)
|      |   |   +- extract domain from email
|      |   |   +- skip if public domain (gmail.com, outlook.com, etc.)
|      |   |   +- SELECT * FROM companies WHERE domain = ?
|      |   |   +- fallback: SELECT via company_identifiers(type='domain')
|      |   +- if found: company_id = matched company ID
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

### Flow 7: Company Enrichment

```
execute_enrichment("company", company_id, provider_name)
|  +- get_provider(provider_name)
|  +- create_enrichment_run(entity_type, entity_id, provider)
|  +- _update_run_status(run_id, "running")
|  +- Load entity: get_company(company_id)
|  +- provider.enrich(entity) -> list[FieldValue]
|  +- _store_field_values(run_id, field_values)
|  |   +- INSERT INTO enrichment_field_values
|  |
|  +- For each field_value with _should_accept(confidence >= 0.7):
|  |   +- Direct fields (description, industry, website, ...):
|  |   |   +- UPDATE companies SET field = value
|  |   +- phone_* fields:
|  |   |   +- Check existing phone_numbers for dedup
|  |   |   +- add_phone_number() if new
|  |   +- email_* fields:
|  |   |   +- Check existing email_addresses for dedup
|  |   |   +- add_email_address() if new
|  |   +- address_* fields:
|  |   |   +- Check existing addresses for dedup
|  |   |   +- add_address() if new
|  |   +- social_* fields:
|  |       +- add_company_social_profile() (upsert via ON CONFLICT)
|  |
|  +- UPDATE enrichment_field_values SET is_accepted=1 WHERE applied
|  +- _update_run_status(run_id, "completed")
|  +- return {run_id, status, fields_discovered, fields_applied}
```

### Flow 8: Domain Resolution (Bulk Backfill)

```
resolve_unlinked_contacts(dry_run=False)
|  +- get_connection()
|  +- SELECT contacts with company_id IS NULL
|  |   JOIN contact_identifiers WHERE type='email'
|  |
|  +- for each unlinked contact:
|  |   +- extract_domain(email)
|  |   +- if is_public_domain(domain): skip (count as public)
|  |   +- resolve_company_by_domain(conn, domain)
|  |   |   +- SELECT * FROM companies WHERE domain = ? AND status='active'
|  |   |   +- fallback: SELECT via company_identifiers(type='domain')
|  |   +- if found and not dry_run:
|  |       +- UPDATE contacts SET company_id = ?, company = ?
|  |
|  +- return DomainResolveResult(checked, linked, skipped_public, skipped_no_match)
```

Available via CLI (`python3 -m poc resolve-domains [--dry-run]`) and
web UI (POST `/companies/resolve-domains`).  The web route returns an
inline HTML summary of results.

### Flow 9: Relationship Strength Scoring

```
compute_company_score(conn, company_id, weights=None)
|  +- Calculate window_start = now - 90 days
|  +- PARTICIPANTS PATH:
|  |   SELECT aggregates FROM contacts
|  |     JOIN contact_identifiers (email)
|  |     JOIN communication_participants (address match)
|  |     JOIN communications
|  |   WHERE contacts.company_id = company_id
|  |   -> total, outbound, inbound, recent_outbound, recent_inbound,
|  |      first_ts, last_ts, distinct_contacts
|  |
|  +- SENDER PATH:
|  |   SELECT aggregates FROM contacts
|  |     JOIN contact_identifiers (email)
|  |     JOIN communications (sender_address match)
|  |   WHERE contacts.company_id = company_id
|  |   -> same aggregates (catches senders not in participants table)
|  |
|  +- _merge_stats(participants_row, sender_row)
|  |   -> sum counts, min/max timestamps, max distinct contacts
|  |
|  +- if total_comms == 0: return None
|  +- Compute 5 factors (each 0.0–1.0):
|  |   +- recency:     linear decay from last_ts (1.0 at day 0, 0.0 at 365+)
|  |   +- frequency:   direction-weighted recent counts, log-scaled vs cap=200
|  |   +- reciprocity: 1.0 - abs(outbound_ratio - 0.5) * 2
|  |   +- breadth:     log-scaled distinct contacts vs cap=15
|  |   +- duration:    span first→last in days, capped at 730 days
|  |
|  +- score = weighted sum (default: 0.35*recency + 0.25*frequency
|  |          + 0.20*reciprocity + 0.12*breadth + 0.08*duration)
|  +- return {"score", "factors", "raw"}

compute_contact_score(conn, contact_id, weights=None)
|  +- Same dual-path approach but per-contact instead of per-company
|  +- breadth = distinct conversations (via conversation_participants)
|     instead of distinct contacts

score_all_companies(triggered_by="batch")
|  +- get_connection()
|  +- SELECT all active companies
|  +- for each company:
|  |   +- compute_company_score(conn, company_id)
|  |   +- if result: upsert_entity_score(conn, "company", ...)
|  +- return {"scored": N, "skipped": M}

upsert_entity_score(conn, entity_type, entity_id, score_type, ...)
|  +- INSERT INTO entity_scores ...
|     ON CONFLICT(entity_type, entity_id, score_type)
|     DO UPDATE SET score_value, factors, computed_at, triggered_by
```

Available via CLI (`python3 -m poc score-companies [--name NAME]`,
`python3 -m poc score-contacts [--contact EMAIL]`) and web UI (POST
`/companies/{id}/score`, POST `/contacts/{id}/score`).  Scores are
displayed in the web UI on three surfaces: the dashboard (top 5
companies and contacts by score), the list views (inline progress bars
with sortable Score column), and the detail pages (sidebar with
expandable factor breakdown).

**Direction weighting:** Outbound communications count at 1.0x weight,
inbound at 0.6x.  This reflects that proactive outreach is a stronger
engagement signal than receiving messages.

**Normalization:** All factors use logarithmic scaling with fixed caps
(frequency_cap=200, breadth_cap=15, duration_cap=730 days) rather than
global-maximum normalization.  This avoids outlier compression and
ensures scores are stable across different dataset sizes.

The website scraper provider (`website_scraper.py`) crawls up to 3
pages per domain (homepage, /about, /contact) and extracts metadata,
social links, and contact information using BeautifulSoup + JSON-LD
parsing.  Conflict resolution uses tier-based precedence (manual >
paid_api > free_api > website_scrape > email_signature > inferred)
with an auto-accept threshold of confidence >= 0.7.

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
| `company_identifiers` | `(type, value)` | Check-then-insert | Existing row reused |
| `company_social_profiles` | `(company_id, platform, profile_url)` | `INSERT ... ON CONFLICT DO UPDATE` | Username/source/confidence refreshed |
| `entity_scores` | `(entity_type, entity_id, score_type)` | `INSERT ... ON CONFLICT DO UPDATE` | Score value, factors, timestamp refreshed |
| `settings` (system) | `(customer_id, setting_name)` WHERE `scope='system'` | `INSERT ... ON CONFLICT DO UPDATE` | Value and description refreshed |
| `settings` (user) | `(customer_id, user_id, setting_name)` WHERE `scope='user'` | `INSERT ... ON CONFLICT DO UPDATE` | Value refreshed |
| `user_contacts` | `(user_id, contact_id)` | Check-then-insert | Existing row reused |
| `user_companies` | `(user_id, company_id)` | Check-then-insert | Existing row reused |
| `user_provider_accounts` | `(user_id, account_id)` | Check-then-insert | Existing row reused |
| `conversation_shares` | `(conversation_id, user_id)` | Check-then-insert | Existing row reused |

---

## Configuration

| Setting | Env variable | Default | Description |
|---------|-------------|---------|-------------|
| `DB_PATH` | `POC_DB_PATH` | `data/crm_extender.db` | Path to the SQLite database file.  Parent directories are created automatically by `init_db()`. |
| `CRM_TIMEZONE` | `CRM_TIMEZONE` | `UTC` | IANA timezone for display-layer date conversion.  All storage remains UTC; this setting only affects web UI rendering via `Intl.DateTimeFormat`.  Invalid values log a warning and fall back to UTC. |
| `CRM_AUTH_ENABLED` | `CRM_AUTH_ENABLED` | `true` | Enable/disable authentication middleware.  Set to `false` during development to bypass login. |
| `SESSION_SECRET_KEY` | `SESSION_SECRET_KEY` | `change-me-in-production` | Secret key for signing session cookies (itsdangerous). |
| `SESSION_TTL_HOURS` | `SESSION_TTL_HOURS` | `720` | Session time-to-live in hours (default: 30 days). |

The database file and its WAL/SHM companions are excluded from version
control via `.gitignore` (`data/` directory).
