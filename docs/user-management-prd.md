# User & Customer Management PRD

## CRMExtender — Multi-User & Multi-Tenant Support

**Version:** 1.0
**Date:** 2026-02-10
**Status:** Phase 3 Implemented (route filtering & data scoping)
**Parent Documents:** [CRMExtender PRD v1.1](PRD.md), [Data Layer PRD](data-layer-prd.md)

---

## Table of Contents

1. [Problem Statement](#1-problem-statement)
2. [Goals & Non-Goals](#2-goals--non-goals)
3. [Data Model — New Tables](#3-data-model--new-tables)
4. [Data Model — Modified Tables](#4-data-model--modified-tables)
5. [Data Visibility Rules](#5-data-visibility-rules)
6. [Authentication](#6-authentication)
7. [Roles & Authorization](#7-roles--authorization)
8. [Settings System](#8-settings-system)
9. [Data Layer (Python)](#9-data-layer-python)
10. [Migration Path](#10-migration-path)
11. [CLI Commands](#11-cli-commands)
12. [Test Coverage](#12-test-coverage)
13. [Implementation Phases](#13-implementation-phases)
14. [Design Decisions](#14-design-decisions)
15. [Future Work](#15-future-work)

---

## 1. Problem Statement

CRM Extender is currently a single-user system.  The `users` table
exists but serves only as an FK target for `created_by`/`updated_by`
audit columns (which are never populated).  There is no authentication,
no session management, and all data is globally visible.  The web UI is
completely open.  This creates several problems:

- **No access control** — anyone on the network can view, edit, and
  delete all CRM data.  There is no concept of "my data" vs "shared
  data" vs "private data".
- **No multi-user support** — only one user can exist.  Multiple people
  cannot use the same CRM instance with their own contacts, settings,
  and provider accounts.
- **No tenant isolation** — the schema has no mechanism to partition
  data by organization.  A future SaaS deployment would require a
  full schema redesign.
- **No per-user settings** — timezone, date format, and other
  preferences are global configuration values.  Two users on different
  continents see the same date rendering.
- **No audit trail** — `created_by`/`updated_by` columns exist but are
  never populated because there is no authenticated user context.
- **No provider account sharing** — email accounts are globally
  accessible.  There is no way to say "this Gmail account belongs to
  Alice, and Bob has shared access to it".

---

## 2. Goals & Non-Goals

### Goals

1. **Customer (tenant) model** — introduce a `customers` table that
   partitions all data.  Every entity belongs to exactly one customer.
2. **Multi-user within a customer** — multiple users can share a
   customer with distinct roles (`admin`, `user`), each with their own
   contacts, companies, and provider accounts.
3. **Per-user data visibility** — contacts and companies have explicit
   visibility (`public` or `private`) per user.  Private entities are
   visible only to their owner; public entities are visible to all
   users in the customer.
4. **Provider account ownership** — provider accounts (Gmail, etc.) are
   linked to specific users with `owner` or `shared` roles via a
   junction table.
5. **Conversation visibility** — conversations are visible to users who
   have access to a provider account that produced communications in
   the conversation, or who have been granted explicit shares.
6. **Server-side sessions** — cookie-based sessions backed by a
   `sessions` table with TTL expiry.
7. **Authentication readiness** — the users table supports both Google
   OAuth (`google_sub`) and password-based (`password_hash`) login,
   enabling Phase 2 auth implementation.
8. **Unified settings system** — a `settings` table with system-wide
   and per-user scopes, supporting a cascade resolution order:
   user value > system value > setting default > hardcoded fallback.
9. **Backward-compatible migration** — all existing data is assigned to
   a default customer, and the existing user (if any) becomes an admin
   with full ownership of all contacts, companies, and provider
   accounts.

### Non-Goals

- **Full multi-tenant SaaS** — Phase 1 supports a single customer
  (tenant) with the schema designed for future multi-tenant.  Customer
  management UI, per-customer billing, and cross-customer isolation are
  out of scope.
- ~~**OAuth login flow**~~ — password-based authentication implemented
  in Phase 2.  Google OAuth login remains deferred.
- ~~**Route-level filtering**~~ — implemented in Phase 3.  All web UI
  queries are now scoped by customer and user visibility.
- **RBAC beyond admin/user** — two roles are sufficient for Phase 1.
  Fine-grained permissions (e.g., "can view but not edit companies")
  are future work.
- **Per-customer `contact_identifiers` uniqueness** — the
  `UNIQUE(type, value)` constraint remains global.  Future migration
  will scope to `UNIQUE(type, value, customer_id)`.

---

## 3. Data Model — New Tables

### 3.1 `customers`

The tenant table.  All data ultimately belongs to a customer.

```sql
CREATE TABLE customers (
    id         TEXT PRIMARY KEY,
    name       TEXT NOT NULL,
    slug       TEXT NOT NULL UNIQUE,
    is_active  INTEGER DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
```

The default customer created during migration has ID `cust-default`,
name "Default Organization", and slug "default".

### 3.2 `sessions`

Server-side session store.  Each session maps to one user and one
customer.  Sessions expire after a configurable TTL (default 30 days).

```sql
CREATE TABLE sessions (
    id          TEXT PRIMARY KEY,   -- UUID, stored in cookie
    user_id     TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    customer_id TEXT NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    created_at  TEXT NOT NULL,
    expires_at  TEXT NOT NULL,
    ip_address  TEXT,
    user_agent  TEXT
);
```

### 3.3 `user_contacts`

Per-user contact visibility.  Every contact a user can see has a row
here.  Visibility is either `public` (visible to all customer users)
or `private` (visible only to this user).

```sql
CREATE TABLE user_contacts (
    id         TEXT PRIMARY KEY,
    user_id    TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    contact_id TEXT NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
    visibility TEXT NOT NULL DEFAULT 'public'
        CHECK (visibility IN ('public', 'private')),
    is_owner   INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(user_id, contact_id)
);
```

### 3.4 `user_companies`

Per-user company visibility.  Same pattern as `user_contacts`.

```sql
CREATE TABLE user_companies (
    id         TEXT PRIMARY KEY,
    user_id    TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    company_id TEXT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    visibility TEXT NOT NULL DEFAULT 'public'
        CHECK (visibility IN ('public', 'private')),
    is_owner   INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(user_id, company_id)
);
```

### 3.5 `user_provider_accounts`

Links users to provider accounts (Gmail, etc.) with an explicit role.

```sql
CREATE TABLE user_provider_accounts (
    id         TEXT PRIMARY KEY,
    user_id    TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    account_id TEXT NOT NULL REFERENCES provider_accounts(id) ON DELETE CASCADE,
    role       TEXT NOT NULL DEFAULT 'owner'
        CHECK (role IN ('owner', 'shared')),
    created_at TEXT NOT NULL,
    UNIQUE(user_id, account_id)
);
```

### 3.6 `conversation_shares`

Explicit sharing of conversations with specific users.  A conversation
is visible to a user either through provider account participation
(implicit) or through this table (explicit).

```sql
CREATE TABLE conversation_shares (
    id              TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    user_id         TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    shared_by       TEXT REFERENCES users(id) ON DELETE SET NULL,
    created_at      TEXT NOT NULL,
    UNIQUE(conversation_id, user_id)
);
```

### 3.7 `settings`

Unified key-value settings table supporting both system-wide and
per-user scopes.  Uses partial unique indexes for NULL-safe uniqueness.

```sql
CREATE TABLE settings (
    id                  TEXT PRIMARY KEY,
    customer_id         TEXT NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    user_id             TEXT REFERENCES users(id) ON DELETE CASCADE,
    scope               TEXT NOT NULL CHECK (scope IN ('system', 'user')),
    setting_name        TEXT NOT NULL,
    setting_value       TEXT,
    setting_description TEXT,
    setting_default     TEXT,
    created_at          TEXT NOT NULL,
    updated_at          TEXT NOT NULL
);

-- NULL-safe uniqueness (SQLite partial indexes):
CREATE UNIQUE INDEX idx_settings_system_unique
    ON settings(customer_id, setting_name) WHERE scope = 'system';
CREATE UNIQUE INDEX idx_settings_user_unique
    ON settings(customer_id, user_id, setting_name) WHERE scope = 'user';
```

---

## 4. Data Model — Modified Tables

### 4.1 `users` (recreated)

SQLite cannot `ALTER TABLE ... ADD COLUMN ... NOT NULL` with FK
constraints, so the users table is recreated with new columns.

```sql
CREATE TABLE users (
    id            TEXT PRIMARY KEY,
    customer_id   TEXT NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    email         TEXT NOT NULL,
    name          TEXT,
    role          TEXT DEFAULT 'user' CHECK (role IN ('admin', 'user')),
    is_active     INTEGER DEFAULT 1,
    password_hash TEXT,       -- bcrypt, nullable for Google-only users
    google_sub    TEXT,       -- Google OAuth subject ID
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL,
    UNIQUE(customer_id, email)
);
```

Key changes from v7:
- **`customer_id`** (NOT NULL FK) — every user belongs to exactly one
  customer.
- **`email` uniqueness** scoped to customer instead of global.
- **`role`** values changed: `member` -> `user` (plus `admin`).
- **`password_hash`** — bcrypt hash for password-based login.
- **`google_sub`** — Google OAuth subject ID for SSO login.

### 4.2 `customer_id` on existing tables

Seven tables gain a `customer_id TEXT` column referencing
`customers(id)`:

| Table | Notes |
|-------|-------|
| `provider_accounts` | Nullable during migration, backfilled to `cust-default`. |
| `contacts` | Same. |
| `companies` | Same. |
| `conversations` | Same. |
| `projects` | Same. |
| `tags` | Same. |
| `relationship_types` | Nullable — system seed types keep NULL customer_id. |

Child tables (`contact_identifiers`, `communications`,
`conversation_participants`, `communication_participants`, etc.) do
**not** need `customer_id` — tenant isolation is enforced through their
parent FK.

---

## 5. Data Visibility Rules

### 5.1 Contacts — "All Contacts" vs "My Contacts"

**All Contacts** = contacts where ANY user in the customer has
`visibility = 'public'`, PLUS the current user's own private contacts:

```sql
SELECT c.* FROM contacts c
WHERE c.customer_id = :customer_id
  AND (
    EXISTS (SELECT 1 FROM user_contacts uc
            WHERE uc.contact_id = c.id AND uc.visibility = 'public')
    OR EXISTS (SELECT 1 FROM user_contacts uc
               WHERE uc.contact_id = c.id AND uc.user_id = :user_id)
  )
```

**My Contacts** = contacts where the current user has a `user_contacts`
row (any visibility):

```sql
SELECT c.* FROM contacts c
JOIN user_contacts uc ON uc.contact_id = c.id AND uc.user_id = :user_id
WHERE c.customer_id = :customer_id
```

### 5.2 Companies — same pattern via `user_companies`

### 5.3 Conversations — provider account participation + explicit shares

A user sees a conversation if:
1. They have access to a `provider_account` that produced a
   communication in the conversation (via `user_provider_accounts`), OR
2. The conversation was explicitly shared via `conversation_shares`.

```sql
SELECT conv.* FROM conversations conv
WHERE conv.customer_id = :customer_id
  AND (
    EXISTS (
      SELECT 1 FROM conversation_communications cc
      JOIN communications comm ON comm.id = cc.communication_id
      JOIN user_provider_accounts upa ON upa.account_id = comm.account_id
      WHERE cc.conversation_id = conv.id AND upa.user_id = :user_id
    )
    OR EXISTS (
      SELECT 1 FROM conversation_shares cs
      WHERE cs.conversation_id = conv.id AND cs.user_id = :user_id
    )
  )
```

### 5.4 Contact deduplication across users

`contact_identifiers(type, value)` remains UNIQUE system-wide.  When
User B syncs or adds an email that matches User A's private contact:

- No duplicate contact is created.
- A `user_contacts` row is created linking User B to the existing
  contact.
- If User B's visibility = `'public'`, the contact becomes visible to
  all users in the customer.
- A contact is private ONLY if ALL linked users mark it private.

---

## 6. Authentication

### 6.1 Two login methods

1. **Username/Password** (Implemented) — bcrypt-hashed password stored
   in `users.password_hash`.  Managed via CLI
   (`set-password`, `bootstrap-user --password`).
2. **Google OAuth** (Deferred) — separate from the existing Gmail API
   OAuth.  Uses `openid email profile` scopes for identity only.
   Matches user by `google_sub` or `email` within customer.

### 6.2 Session management

- Server-side `sessions` table with UUID session ID.
- Cookie: `crm_session` (httponly, samesite=lax) = session UUID.
- Default TTL: 30 days (configurable via `SESSION_TTL_HOURS`).
- Session lookup on every request via `AuthMiddleware`.
- Expired sessions are automatically cleaned up on access and via
  `cleanup_expired_sessions()`.

### 6.3 AuthMiddleware (Implemented)

Implementation: `poc/web/middleware.py`

**Auth enabled mode** (`CRM_AUTH_ENABLED=true`, default):
- Static files (`/static/*`) pass through without auth.
- For all other paths, resolves session from `crm_session` cookie.
- `/login` passes through even without a valid session (but still
  resolves the session so the login page can redirect
  already-authenticated users).
- All other paths redirect to `/login` if no valid session exists.
- Valid sessions populate `request.state.user` with id, email, name,
  role, and customer_id.

**Bypass mode** (`CRM_AUTH_ENABLED=false`):
- Injects the first active user from the database as
  `request.state.user`.
- Falls back to a synthetic admin user if no users exist (empty DB).
- All routes are accessible without login.

### 6.4 Auth routes (Implemented)

Implementation: `poc/web/routes/auth_routes.py`

- **`GET /login`** — renders standalone login form; redirects to `/`
  if already authenticated.
- **`POST /login`** — validates email + password, creates session,
  sets `crm_session` cookie, redirects 303 to `/`.  Error messages
  are generic ("Invalid email or password") to prevent email
  enumeration.
- **`POST /logout`** — deletes session, clears cookie, redirects 303
  to `/login`.

### 6.5 Dependencies (Implemented)

Implementation: `poc/web/dependencies.py`

- **`get_current_user(request)`** — returns `request.state.user` or
  raises HTTP 401.
- **`require_admin(request)`** — returns user if `role='admin'` or
  raises HTTP 403.

For use as `Depends()` in admin-only routes (Phase 3+).

### 6.6 Template integration (Implemented)

- **`AuthTemplates`** (in `poc/web/app.py`) — subclass of
  `Jinja2Templates` that auto-injects `request.state.user` as `user`
  into all template contexts.
- **`base.html`** — nav bar shows user name + logout button when
  `user` is set.
- **`login.html`** — standalone page (no base.html nav), PicoCSS
  styled.

### 6.7 Configuration

| Setting | Env variable | Default | Description |
|---------|-------------|---------|-------------|
| Auth enabled | `CRM_AUTH_ENABLED` | `true` | Set to `false` to bypass authentication during development. |
| Session secret | `SESSION_SECRET_KEY` | `change-me-in-production` | Secret key for signing session cookies. |
| Session TTL | `SESSION_TTL_HOURS` | `720` (30 days) | Session expiration in hours. |

---

## 7. Roles & Authorization

| Role | Capabilities |
|------|-------------|
| `admin` | All user capabilities + edit System Settings + manage users (create/deactivate/change roles) + share provider accounts |
| `user` | View/edit own contacts/companies/conversations, manage own settings, sync own provider accounts |

Role enforcement is via a `require_admin()` dependency (Phase 2) that
returns HTTP 403 for non-admin users on protected endpoints.

---

## 8. Settings System

### 8.1 Resolution order

`get_setting(customer_id, name, user_id)` resolves values with a
four-level cascade:

1. **User-specific value** — if set and non-null for this user.
2. **System setting value** — customer-wide default.
3. **Setting default** — from the `setting_default` column.
4. **Hardcoded fallback** — from `settings._HARDCODED_DEFAULTS` dict.

This allows users to override system defaults without requiring every
setting to be explicitly set per-user.

### 8.2 Default system settings

| `setting_name` | `setting_default` | Description |
|---|---|---|
| `default_timezone` | `UTC` | Default timezone for new users. |
| `company_name` | *(customer name)* | Organization display name. |
| `sync_enabled` | `true` | Enable/disable automatic sync. |

### 8.3 Default user settings

| `setting_name` | `setting_default` | Description |
|---|---|---|
| `timezone` | *(inherit system)* | Preferred timezone (IANA). |
| `start_of_week` | `monday` | First day of week. |
| `date_format` | `ISO` | Date display: US, ISO, or EU. |
| `profile_photo` | *(none)* | Profile photo path or URL. |
| `contact_id` | *(none)* | Link to user's own contact record. |

### 8.4 CRM_TIMEZONE transition

The existing `config.CRM_TIMEZONE` global remains as the last-resort
fallback.  Per-user `timezone` settings override it for authenticated
requests.  The `dates.js` script already reads from
`<meta name="crm-timezone">` — future phases inject the per-user
value instead of the global.

---

## 9. Data Layer (Python)

### 9.1 New modules

| File | Role |
|------|------|
| `poc/session.py` | Session CRUD: `create_session`, `get_session`, `delete_session`, `delete_user_sessions`, `cleanup_expired_sessions` |
| `poc/settings.py` | Settings CRUD: `get_setting` (cascade resolution), `set_setting` (upsert), `list_settings`, `seed_default_settings` |
| `poc/access.py` | Tenant-scoped query helpers: `visible_contacts_query`, `my_contacts_query`, `visible_companies_query`, `my_companies_query`, `visible_conversations_query`, plus `get_visible_*`/`get_my_*` convenience functions |
| `poc/migrate_to_v8.py` | Schema migration v7 -> v8 (17 steps, backup, validation, `--dry-run`) |

### 9.2 Phase 2 modules (authentication)

| File | Role |
|------|------|
| `poc/passwords.py` | Password hashing (`hash_password`) and verification (`verify_password`) using bcrypt |
| `poc/web/middleware.py` | `AuthMiddleware` — session cookie validation, bypass mode, user context injection |
| `poc/web/routes/auth_routes.py` | Login/logout routes: `GET/POST /login`, `POST /logout` |
| `poc/web/dependencies.py` | FastAPI dependencies: `get_current_user` (401), `require_admin` (403) |

### 9.3 Modified modules

| File | Changes |
|------|---------|
| `poc/database.py` | Added `customers` table, updated `users` schema, added `customer_id` to 7 tables, added 6 new table CREATE statements, added indexes, added `_SETTINGS_INDEX_SQL` for partial unique indexes |
| `poc/models.py` | Updated `User` dataclass (added `customer_id`, `password_hash`, `google_sub`, changed default role to `'user'`).  Added `Customer`, `Session`, `Setting` dataclasses with `to_row()`/`from_row()` |
| `poc/hierarchy.py` | Updated `bootstrap_user(password=)` to auto-create default customer, set `role='admin'`, and optionally hash a password.  Added `get_user_by_email()`, `set_user_password()`, `_ensure_default_customer()`.  Added `DEFAULT_CUSTOMER_ID = "cust-default"` constant |
| `poc/config.py` | Added `CRM_AUTH_ENABLED`, `SESSION_SECRET_KEY`, `SESSION_TTL_HOURS` |
| `poc/__main__.py` | Added `migrate-to-v8`, `set-password` CLI subcommands; added `--password`/`--set-password` to `bootstrap-user` |
| `poc/web/app.py` | Added `AuthTemplates` subclass (auto-injects user into templates), registered `AuthMiddleware`, included auth router |
| `poc/web/templates/base.html` | Added user name + logout button to nav bar |
| `poc/web/templates/login.html` | New standalone login page |
| `pyproject.toml` | Added `bcrypt>=4.0.0`, `itsdangerous>=2.1.0` dependencies |

### 9.4 Dataclasses

**`Customer`** — `name`, `slug`, `is_active`

**`User`** (updated) — `email`, `customer_id`, `name`, `role` (default
`'user'`), `is_active`, `password_hash`, `google_sub`

**`Session`** — `user_id`, `customer_id`, `expires_at`, `ip_address`,
`user_agent`

**`Setting`** — `customer_id`, `scope`, `setting_name`, `setting_value`,
`user_id`, `setting_description`, `setting_default`

All dataclasses follow the established `to_row()` / `from_row()` pattern.

### 9.5 Session API

```python
from poc.session import (
    create_session,       # (user_id, customer_id, *, ttl_hours, ip_address, user_agent) -> dict
    get_session,          # (session_id) -> dict | None  (joins user data, checks expiry)
    delete_session,       # (session_id) -> bool
    delete_user_sessions, # (user_id) -> int  (count deleted)
    cleanup_expired_sessions,  # () -> int  (count deleted)
)
```

`get_session()` performs three validations:
1. Session exists in DB.
2. Session has not expired (auto-deletes if expired).
3. Associated user is active (`is_active = 1`).

### 9.6 Settings API

```python
from poc.settings import (
    get_setting,            # (customer_id, name, *, user_id) -> str | None
    set_setting,            # (customer_id, name, value, *, scope, user_id, ...) -> dict
    list_settings,          # (customer_id, *, scope, user_id) -> list[dict]
    seed_default_settings,  # (customer_id, *, user_id) -> {"system": int, "user": int}
)
```

### 9.6 Access control API

```python
from poc.access import (
    visible_contacts_query,      # (customer_id, user_id) -> (where_clause, params)
    my_contacts_query,           # (customer_id, user_id) -> (where_clause, params)
    visible_companies_query,     # (customer_id, user_id) -> (where_clause, params)
    my_companies_query,          # (customer_id, user_id) -> (where_clause, params)
    visible_conversations_query, # (customer_id, user_id) -> (where_clause, params)
    get_visible_contacts,        # (conn, customer_id, user_id) -> list[dict]
    get_my_contacts,             # (conn, customer_id, user_id) -> list[dict]
    get_visible_companies,       # (conn, customer_id, user_id) -> list[dict]
    get_my_companies,            # (conn, customer_id, user_id) -> list[dict]
    get_visible_conversations,   # (conn, customer_id, user_id) -> list[dict]
)
```

The query functions return `(WHERE clause, params)` tuples suitable for
embedding in larger queries.  The convenience functions execute the
full query and return lists of dicts.

---

## 10. Migration Path

File: `poc/migrate_to_v8.py`

The migration follows the established pattern: backup, sequential
steps, validation, `--dry-run` support, `--db PATH` override.

### Steps

| Step | Action |
|------|--------|
| 1 | Create `customers` table |
| 2 | Bootstrap default customer (`cust-default`, "Default Organization") |
| 3 | Recreate `users` table with new schema (PRAGMA foreign_keys=OFF, rename old, create new, copy data with `customer_id='cust-default'` and `role='admin'`, drop old) |
| 4 | Add `customer_id` column to `provider_accounts`, `contacts`, `companies`, `conversations`, `projects`, `tags`, `relationship_types` |
| 5 | Backfill all existing rows with `customer_id = 'cust-default'` |
| 6–11 | Create new tables: `sessions`, `user_contacts`, `user_companies`, `user_provider_accounts`, `conversation_shares`, `settings` |
| 12 | Seed `user_provider_accounts` — link existing user to all provider_accounts as `'owner'` |
| 13 | Seed `user_contacts` — link existing user to all contacts as `'public'` + `is_owner=1` |
| 14 | Seed `user_companies` — link existing user to all companies as `'public'` + `is_owner=1` |
| 15 | Seed default settings (system + user) |
| 16 | Create all new indexes |
| 17 | Validate — table existence, column presence, row count integrity, no NULL customer_ids |

### Idempotency

All steps are idempotent:
- `CREATE TABLE IF NOT EXISTS` for new tables.
- `ALTER TABLE ADD COLUMN` skips if column exists.
- `INSERT OR IGNORE` for seed data.
- `UPDATE ... WHERE customer_id IS NULL` for backfill.
- The `users` table recreation checks for `customer_id` column first.

---

## 11. CLI Commands

### `migrate-to-v8`

```bash
python3 -m poc migrate-to-v8 --dry-run          # Preview on a backup copy
python3 -m poc migrate-to-v8                     # Apply to production
python3 -m poc migrate-to-v8 --db /path/to.db    # Target specific database
```

Creates a timestamped backup (`*.v7-backup-YYYYMMDD_HHMMSS.db`) before
making any changes.

### `bootstrap-user`

```bash
python3 -m poc bootstrap-user                     # Create user from first provider account
python3 -m poc bootstrap-user --password secret    # Create user with password
python3 -m poc bootstrap-user --set-password       # Create user, prompt for password
```

Creates the default customer and admin user from the first provider
account.  If the user already exists and `--password` or `--set-password`
is given, updates the password hash.

### `set-password`

```bash
python3 -m poc set-password user@example.com                # Prompt for password
python3 -m poc set-password user@example.com --password pw   # Set directly
```

Sets or updates the login password for an existing user.

---

## 12. Test Coverage

### Phase 1 tests (57 new)

| File | Tests | Coverage |
|------|-------|----------|
| `tests/test_migration_v8.py` | 16 | All migration steps: table creation, user preservation, customer_id backfill, seeding, dry run, idempotency, empty DB, indexes |
| `tests/test_sessions.py` | 12 | Session create, get (valid/expired/inactive user/nonexistent), delete, delete all user sessions, cleanup expired |
| `tests/test_settings.py` | 16 | Set/get system and user settings, upsert, cascade resolution (4 levels), cross-user isolation, null value fallthrough, list/seed |
| `tests/test_access.py` | 13 | Visible vs my contacts/companies, public/private visibility, conversation visibility via provider accounts and explicit shares |

### Phase 2 tests (18 new)

| File | Tests | Coverage |
|------|-------|----------|
| `tests/test_auth.py` | 18 | Passwords (hash/verify, salts), login (success, wrong password, unknown email, no password hash, redirect if authed), logout (clears session), middleware (redirect, static public, valid session, invalid cookie, user in nav), bypass mode (access without login, user context), admin dependency (401/403) |

### Phase 3 tests (24 new)

| File | Tests | Coverage |
|------|-------|----------|
| `tests/test_scoping.py` | 24 | Contact scoping (all/mine, public/private visibility, cross-customer 404), company scoping (all/mine, cross-customer 404), conversation scoping (via account access, via share, cross-customer invisible), dashboard scoping (counts, recent conversations), detail access checks (cross-customer 404), sync scoping (user_contacts/user_companies creation), project scoping (customer_id on create/list) |

Total test suite: **694 tests** (595 pre-existing + 57 Phase 1 + 18
Phase 2 + 24 Phase 3), all passing.

---

## 13. Implementation Phases

### Phase 1: Schema & Data Layer (Implemented)

- v8 migration script with 17 steps
- `customers`, `sessions`, `user_contacts`, `user_companies`,
  `user_provider_accounts`, `conversation_shares`, `settings` tables
- `customer_id` on 7 existing tables
- `User` model updated, `Customer`/`Session`/`Setting` models added
- Session CRUD (`poc/session.py`)
- Settings CRUD with cascade resolution (`poc/settings.py`)
- Tenant-scoped query helpers (`poc/access.py`)
- 57 tests

### Phase 2: Authentication (Implemented)

- `poc/passwords.py` — bcrypt password hashing/verification
- `poc/web/middleware.py` — `AuthMiddleware` (session validation + bypass mode)
- `poc/web/routes/auth_routes.py` — `GET/POST /login`, `POST /logout`
- `poc/web/dependencies.py` — `get_current_user` (401), `require_admin` (403)
- `poc/web/templates/login.html` — standalone login page
- `poc/web/app.py` — `AuthTemplates` subclass, middleware registration
- `poc/web/templates/base.html` — user name + logout button in nav
- `poc/hierarchy.py` — `get_user_by_email()`, `set_user_password()`
- `poc/__main__.py` — `set-password` command, `--password` on `bootstrap-user`
- `CRM_AUTH_ENABLED=false` bypass for development
- 18 tests in `tests/test_auth.py`

### Phase 3: Route Filtering & Data Scoping (Implemented)

- All 7 route files scoped to `customer_id` + user visibility via
  `poc/access.py` query helpers
- "All / My" toggles on Contacts and Companies list pages (query
  param `scope=all|mine`, preserved across search and pagination)
- Conversation filtering via `visible_conversations_query` — checks
  provider account access (`user_provider_accounts`) and explicit
  shares (`conversation_shares`)
- Dashboard counts, top companies/contacts, and recent conversations
  all filtered by `customer_id`
- "Sync Now" filters accounts to user's own via `user_provider_accounts`
- Sync pipeline threads `customer_id` and `user_id` through:
  - `sync_contacts()` creates `user_contacts` row on new contact INSERT
  - `_resolve_company_id()` creates `user_companies` row on auto-create
  - `_store_thread()` includes `customer_id` and `created_by` in
    conversation INSERT
- Detail pages verify `customer_id` matches — returns 404 for
  cross-customer access
- Table alias conventions: `c.` contacts, `co.` companies, `conv.`
  conversations (matching `access.py` WHERE fragments)
- `hierarchy.py` CRUD functions accept optional `customer_id` param
  (`create_company`, `list_companies`, `create_project`, `list_projects`)
- `list_relationship_types()` returns customer-specific + system types
- Events scoped via `account_id` subquery (manual events visible to all)
- 24 tests in `tests/test_scoping.py`

### Phase 4: Settings UI (Planned)

- `/settings/profile` — user profile and preferences
- `/settings/system` — system settings (admin only)
- `/settings/users` — user management (admin only)
- Per-user date format and timezone in web rendering

---

## 14. Design Decisions

### Customer ID as TEXT, not INTEGER

All primary keys in the schema use UUID v4 TEXT.  Switching to INTEGER
AUTO INCREMENT for customers would break the established pattern and
require special-casing in code that generates IDs.

### `customer_id` nullable on existing tables

Adding `NOT NULL` via `ALTER TABLE ADD COLUMN` is not supported in
SQLite.  The column is nullable at the schema level, but the migration
backfills all rows to `cust-default` and validation confirms no NULLs
remain.

### User recreation instead of ALTER

SQLite does not support `ALTER TABLE ... ADD COLUMN ... REFERENCES`.
The `users` table is recreated entirely: old table renamed, new table
created, data copied, old table dropped.  This is the established
SQLite migration pattern (used by Django, Alembic, etc.).

### Partial unique indexes for settings

The `settings` table needs uniqueness that respects NULL `user_id` for
system-scoped settings.  SQLite's `UNIQUE(customer_id, user_id,
setting_name)` treats all NULLs as distinct, so two system settings
with the same name would both succeed.  Partial indexes
(`WHERE scope = 'system'` and `WHERE scope = 'user'`) solve this
cleanly.

### Two-row pattern for visibility

Rather than a single `visibility` column on `contacts` directly,
visibility is stored per-user in `user_contacts`.  This allows:
- Different users to have different visibility for the same contact.
- A contact to be private to one user and public to another.
- The concept of "my contacts" (rows in `user_contacts` for this user).

### Bidirectional role semantics for provider accounts

`user_provider_accounts.role` distinguishes `owner` (the user who
authorized this account) from `shared` (a user granted read access by
the owner or an admin).  This enables future features like "share my
inbox with my assistant".

### Existing user becomes admin

During migration, all existing users receive `role = 'admin'`.  Since
the system previously had no access control, downgrading an existing
user to `'user'` would reduce their capabilities unexpectedly.

---

## 15. Future Work

- **Full multi-tenant** — customer management UI, inter-customer
  isolation validation, per-customer configuration.
- **Per-customer contact uniqueness** — scope
  `contact_identifiers(type, value)` to customer_id.
- **Invitation system** — admin invites new users via email, with
  optional Google OAuth enforcement.
- **API keys** — per-user API keys for programmatic access.
- **Audit log** — record all data mutations with user, timestamp, and
  before/after snapshots.
- **Team workspaces** — sub-customer groupings for departments or
  teams.
- **Data export** — per-user data export for GDPR compliance.
- **Session refresh** — extend TTL on active sessions to avoid
  unnecessary re-authentication.
