# Communication — Provider & Sync Framework Sub-PRD

**Version:** 1.0
**Last Updated:** 2026-02-23
**Status:** Draft
**Entity Base PRD:** [communication-entity-base-prd.md]
**Referenced Entity PRDs:** [permissions-sharing-prd.md] (provider account model)

---

## 1. Overview

### 1.1 Purpose

The Provider & Sync Framework is the infrastructure that captures communications from external sources. It defines the provider account model (connected services with encrypted credentials and sync state), the adapter interface that all channel-specific integrations implement, the three sync modes (initial, incremental, manual), and the reliability and audit mechanisms that ensure no data is lost during synchronization.

This framework is the foundation that channel-specific child PRDs (Email Provider Sync, SMS/MMS, Voice/VoIP, Video Meetings) build on. Each child PRD implements the adapter interface for its provider(s).

### 1.2 Preconditions

- User has credentials for at least one external communication provider.
- Provider account table exists in the platform schema.
- The Communication system object type is registered.

---

## 2. Context

### 2.1 Relevant Fields

| Field | Role in This Action |
|---|---|
| Source | Set to `synced` for provider-captured communications. |
| Provider Account ID | Links communication to the account that captured it. |
| Provider Message ID | Provider's unique identifier, used for deduplication. UNIQUE per provider account. |
| Provider Thread ID | Provider's thread identifier, used by Conversations PRD for grouping. |

### 2.2 Relevant Relationships

- **Provider Accounts** — Each communication references its source provider account. Provider accounts hold encrypted credentials, sync cursors, and status.
- **Communication Participants** — Synced communications have participants extracted from provider data (email headers, SMS metadata, call records). Participant resolution is handled by the Participant Resolution Sub-PRD.

### 2.3 Cross-Entity Context

- **Permissions & Sharing PRD:** The provider account data model is defined in Section 11.3. Personal vs. shared account visibility and attribution rules apply.
- **Channel-specific child PRDs:** Each implements the adapter interface for its providers (Gmail, Outlook, IMAP, Twilio, etc.). This sub-PRD defines what they must implement.
- **Company Domain Resolution Sub-PRD:** Email domain extraction during sync triggers company auto-creation.

---

## 3. Key Processes

### KP-1: Connecting a Provider Account

**Trigger:** User navigates to account settings and initiates provider connection.

**Step 1 — Provider selection:** User selects the provider type (Gmail, Outlook, Twilio, etc.).

**Step 2 — Authentication:** System initiates provider-specific auth flow (OAuth for email, API key for SMS providers, etc.). User grants access with minimum necessary scopes.

**Step 3 — Account registration:** Provider account record created with encrypted credentials, status = `active`, sync_cursor = NULL.

**Step 4 — Initial sync begins:** System queues an initial sync job for the new account. User sees "Sync in progress" indicator.

### KP-2: Initial Sync (First Connection)

**Trigger:** Provider account created, or user initiates a full re-sync.

**Step 1 — Historical fetch:** Adapter fetches historical communications matching configurable scope (e.g., emails from last 90 days). Batch fetch with pagination.

**Step 2 — Normalization:** Each raw communication is normalized to the common schema (timestamp, channel, direction, content, participants).

**Step 3 — Deduplication:** Each normalized communication is checked against existing records via provider_account_id + provider_message_id. Duplicates skipped.

**Step 4 — Pipeline processing:** New communications enter the standard pipeline: content extraction → participant resolution → triage → summary generation → conversation assignment.

**Step 5 — Cursor update:** Sync cursor updated to track position. Sync audit log entry created.

**Step 6 — Completion:** Status indicator updates. Summary shows: X messages fetched, Y new, Z skipped.

### KP-3: Incremental Sync (Ongoing)

**Trigger:** Webhook/push notification from provider, or polling interval reached.

**Step 1 — Delta fetch:** Adapter fetches only changes since the last sync cursor. Provider-specific mechanism (Gmail historyId, Outlook deltaLink, IMAP UIDVALIDITY).

**Step 2 — Processing:** Same normalization → deduplication → pipeline as KP-2, but smaller batch.

**Step 3 — Cursor update:** Sync cursor advanced. Audit log entry created.

### KP-4: Manual Sync (User-Triggered)

**Trigger:** User clicks "Sync Now" for a specific account or all accounts.

**Step 1 — Force incremental:** System triggers an immediate incremental sync regardless of schedule.

**Step 2 — Feedback:** User sees real-time progress and result summary.

### KP-5: Disconnecting a Provider Account

**Trigger:** User disconnects a provider account from settings.

**Step 1 — Choice:** System asks: "Retain existing data" or "Delete synced data."

**Step 2a — Retain:** Sync stops. Provider access revoked. Existing Communication records remain. provider_account status set to `disconnected`.

**Step 2b — Delete:** Sync stops. Provider access revoked. All Communication records from this account are cascade-deleted. Events and attachments deleted.

**Step 3 — Credential cleanup:** Encrypted OAuth tokens or API keys are permanently deleted.

### KP-6: Re-Authentication

**Trigger:** Provider returns HTTP 401, or user initiates re-authentication from settings.

**Step 1 — Auth flow:** System initiates the provider-specific re-authentication flow.

**Step 2 — Credential update:** New credentials encrypted and stored. Account status restored to `active`. Sync resumes from last cursor position.

---

## 4. Provider Account Data Model

**Supports processes:** KP-1 (step 3), KP-5 (step 2), KP-6 (step 2)

### 4.1 Requirements

Provider accounts represent connected external services. The data model is shared across all integration types and defined in the Permissions & Sharing PRD Section 11.3.

| Attribute | Type | Description |
|---|---|---|
| `id` | TEXT | Prefixed ULID: `int_` prefix |
| `tenant_id` | TEXT | Owning tenant |
| `owner_type` | TEXT | `user` (personal) or `tenant` (shared inbox) |
| `owner_id` | TEXT | User ID or tenant ID |
| `provider` | TEXT | `gmail`, `outlook`, `imap`, `openphone`, `twilio`, etc. |
| `account_identifier` | TEXT | Email address, phone number, or account handle |
| `credentials_encrypted` | BYTEA | Encrypted OAuth tokens or API keys |
| `status` | TEXT | `active`, `paused`, `error`, `disconnected` |
| `last_sync_at` | TIMESTAMPTZ | Last successful sync |
| `sync_cursor` | TEXT | Opaque provider-specific sync position marker |
| `sync_cursor_type` | TEXT | Cursor format identifier (e.g., `gmail_history_id`, `outlook_delta_link`) |
| `created_at` | TIMESTAMPTZ | |
| `created_by` | TEXT | FK → users |

### 4.2 Account Operations

| Operation | Behavior |
|---|---|
| Connect | OAuth or credential entry → account registered → initial sync begins |
| Disconnect (retain data) | Stop syncing, revoke provider access, keep existing records |
| Disconnect (delete data) | Stop syncing, revoke access, cascade-delete all records from account |
| Re-authenticate | Refresh credentials without affecting data |
| Pause/Resume sync | Temporarily stop/resume without affecting credentials or data |

**Tasks:**

- [ ] CPRO-01: Implement provider account CRUD operations
- [ ] CPRO-02: Implement credential encryption/decryption for storage
- [ ] CPRO-03: Implement account status management (active, paused, error, disconnected)
- [ ] CPRO-04: Implement disconnect with data retention option
- [ ] CPRO-05: Implement disconnect with cascade deletion

**Tests:**

- [ ] CPRO-T01: Test provider account creation with encrypted credentials
- [ ] CPRO-T02: Test disconnect-retain preserves communication records
- [ ] CPRO-T03: Test disconnect-delete cascade removes all account communications
- [ ] CPRO-T04: Test credential encryption round-trip

---

## 5. Provider Adapter Architecture

**Supports processes:** KP-2 (steps 1–2), KP-3 (step 1)

### 5.1 Adapter Interface

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

### 5.2 Adapter Responsibilities

| Responsibility | Description |
|---|---|
| Authentication | Provider-specific OAuth or credential flows |
| Fetching | Translating sync requests into provider API calls (initial batch, incremental delta, manual trigger) |
| Normalization | Converting provider responses to the common Communication schema |
| Cursor management | Tracking sync position in provider-specific format |
| Error handling | Translating provider errors into common error types |
| Rate limiting | Respecting provider-specific rate limits |

**Tasks:**

- [ ] CPRO-06: Define ProviderAdapter base class / interface
- [ ] CPRO-07: Implement adapter registry for provider discovery
- [ ] CPRO-08: Implement normalization contract (RawCommunication → Communication)

**Tests:**

- [ ] CPRO-T05: Test adapter registry discovers registered adapters
- [ ] CPRO-T06: Test normalization produces valid Communication records

---

## 6. Sync Modes & Reliability

**Supports processes:** KP-2 (all steps), KP-3 (all steps), KP-4 (all steps)

### 6.1 Sync Modes

**Initial sync (first connection):** Batch fetch of historical communications matching configurable scope. Performance target: < 5 minutes for a typical mailbox (5,000 messages). Safe to restart — deduplication by provider_message_id.

**Incremental sync (ongoing):** Fetch only changes since last sync cursor. Performance target: < 5 seconds for typical changes (0–20 new messages). Triggered by webhook/push notification or polling interval.

**Manual sync (user-triggered):** Forces an immediate incremental sync regardless of schedule.

### 6.2 Sync Reliability

| Failure Scenario | Recovery |
|---|---|
| Provider API timeout | Exponential backoff retry (3 attempts) |
| Provider rate limit (HTTP 429) | Respect Retry-After header |
| Invalid sync cursor | Date-based re-sync from last known timestamp |
| Partial batch failure | Skip failed messages, log for retry |
| Network interruption | Retry with backoff; queue for next sync |
| Token expiration (HTTP 401) | Auto-refresh; re-authenticate if refresh fails |
| Duplicate messages | INSERT ... ON CONFLICT DO NOTHING (UNIQUE constraint) |
| Message deletion at provider | Mark Communication as archived; recompute conversation metadata |

**Tasks:**

- [ ] CPRO-09: Implement initial sync with configurable scope and pagination
- [ ] CPRO-10: Implement incremental sync with cursor-based delta
- [ ] CPRO-11: Implement manual sync trigger
- [ ] CPRO-12: Implement deduplication via provider_message_id UNIQUE constraint
- [ ] CPRO-13: Implement exponential backoff retry for transient failures
- [ ] CPRO-14: Implement invalid cursor recovery (date-based re-sync)
- [ ] CPRO-15: Implement token auto-refresh and re-authentication flow
- [ ] CPRO-16: Implement provider message deletion detection

**Tests:**

- [ ] CPRO-T07: Test initial sync fetches historical messages in batches
- [ ] CPRO-T08: Test incremental sync fetches only new messages since cursor
- [ ] CPRO-T09: Test deduplication skips already-synced messages
- [ ] CPRO-T10: Test retry with backoff on transient failure
- [ ] CPRO-T11: Test cursor recovery on invalid cursor
- [ ] CPRO-T12: Test token refresh on HTTP 401
- [ ] CPRO-T13: Test provider deletion archives communication

---

## 7. Personal vs. Shared Accounts

**Supports processes:** KP-1 (step 3)

### 7.1 Requirements

| Aspect | Personal Account | Shared Account (Tenant-Level) |
|---|---|---|
| Connected by | Individual user | Sys Admin |
| Credentials scoped to | One user | Tenant |
| Data visibility | User's default visibility setting | Always public |
| Examples | User's Gmail, personal phone | sales@company.com, support@company.com |
| Attribution | created_by = account owner | created_by = system; sent_by tracks actual sender |

### 7.2 Shared Inbox Attribution

When a user responds via a shared inbox, the Communication captures both perspectives:

- **from_address** (participant metadata) — The shared inbox address (what external recipient sees)
- **sent_by** (communication field) — The actual user who composed the message (internal attribution)

This dual attribution is critical for performance tracking, workload distribution, and audit.

**Tasks:**

- [ ] CPRO-17: Implement personal account creation flow
- [ ] CPRO-18: Implement shared account (tenant-level) creation flow
- [ ] CPRO-19: Implement dual attribution for shared inbox responses

**Tests:**

- [ ] CPRO-T14: Test personal account visibility defaults
- [ ] CPRO-T15: Test shared account always-public visibility
- [ ] CPRO-T16: Test dual attribution captures both from_address and sent_by

---

## 8. Sync API & Audit Trail

**Supports processes:** KP-4 (step 1), all KPs (audit)

### 8.1 Sync API

| Endpoint | Method | Description |
|---|---|---|
| `/api/v1/sync/trigger` | POST | Trigger sync for a specific provider account |
| `/api/v1/sync/trigger-all` | POST | Trigger sync for all active accounts for current user |
| `/api/v1/sync/status` | GET | Get sync status for all active accounts |
| `/api/v1/sync/audit` | GET | Get sync audit log (paginated) |

### 8.2 Sync Audit Trail

Every sync operation is logged with: sync_id, provider_account_id, sync_type, timestamps, message counts (fetched, stored, skipped), conversation counts (created, updated), cursor positions, status, and error details. See Communication Entity TDD Section 6 for the table definition.

**Tasks:**

- [ ] CPRO-20: Implement sync API endpoints (trigger, trigger-all, status, audit)
- [ ] CPRO-21: Implement sync audit trail logging
- [ ] CPRO-22: Implement sync status UI (progress, results summary)

**Tests:**

- [ ] CPRO-T17: Test sync trigger API initiates sync for specified account
- [ ] CPRO-T18: Test sync audit log records all sync operations
- [ ] CPRO-T19: Test sync status API returns correct state for all accounts
