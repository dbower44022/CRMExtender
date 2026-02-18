# Provider Abstraction PRD

## CRMExtender — Multi-Provider Sync Abstraction Layer

**Version:** 0.1
**Date:** 2026-02-18
**Status:** Preliminary Draft
**Parent Documents:** [CRMExtender PRD v1.1](PRD.md), [Events PRD](events-prd.md)

---

## Table of Contents

1. [Problem Statement](#1-problem-statement)
2. [Goals & Non-Goals](#2-goals--non-goals)
3. [Current State](#3-current-state)
4. [Provider Interface](#4-provider-interface)
5. [Target Providers](#5-target-providers)
6. [Sync Lifecycle](#6-sync-lifecycle)
7. [Data Flow](#7-data-flow)
8. [Schema Considerations](#8-schema-considerations)
9. [Authentication & Credentials](#9-authentication--credentials)
10. [SMS/Messaging Considerations](#10-smsmessaging-considerations)
11. [Phasing & Roadmap](#11-phasing--roadmap)
12. [Open Questions](#12-open-questions)

---

## 1. Problem Statement

CRMExtender currently supports a single email provider (Gmail) with
provider-specific logic embedded directly in the sync pipeline. Gmail API
calls, authentication, message parsing, and delta-sync mechanisms
(`historyId`) are tightly coupled throughout `sync.py` and
`gmail_client.py`.

As the system grows to support additional email providers (Outlook/365,
IMAP), calendar providers, and messaging platforms (SMS via Twilio, etc.),
this tight coupling will lead to:

- **Code duplication** — each provider re-implements sync orchestration,
  dedup, conversation linking, and contact resolution.
- **Inconsistent behavior** — provider-specific quirks handled ad-hoc
  rather than through a common contract.
- **Testing burden** — no way to test sync logic independently of
  provider-specific API calls.

---

## 2. Goals & Non-Goals

### Goals

1. **Common provider interface** — define a contract that all message
   providers implement, abstracting authentication, message fetching, and
   delta-sync cursors behind a uniform API.
2. **Provider-agnostic sync engine** — the core sync orchestration
   (store communications, evaluate conversation rules, link participants,
   resolve contacts/companies) should not know or care which provider
   produced the data.
3. **Multi-provider per account** — a single user may have Gmail, Outlook,
   and Twilio accounts connected simultaneously.
4. **Incremental sync for all providers** — each provider must support a
   cursor-based delta mechanism to avoid re-fetching already-processed
   messages.
5. **SMS/messaging support** — the abstraction must accommodate non-email
   channels where threads, subjects, and participants behave differently.

### Non-Goals

- **Real-time push sync** — webhook/push notification support is future
  work. Initial implementation uses polling.
- **Two-way sync** — sending emails/messages through the CRM is out of
  scope. This covers inbound data ingestion only.
- **Calendar abstraction** — calendar sync (currently Google Calendar)
  will eventually need similar treatment but is out of scope for this PRD.

---

## 3. Current State

### What exists today

| Component | File | Provider-Agnostic? |
|---|---|---|
| Gmail thread/message fetching | `poc/gmail_client.py` | No — Gmail REST API |
| Gmail history (delta sync) | `poc/gmail_client.py` | No — `historyId` specific |
| Google Contacts sync | `poc/contacts_client.py` | No — People API |
| Google Calendar sync | `poc/calendar_client.py` | No — Calendar API |
| Sync orchestration | `poc/sync.py` | Partially — `_store_thread()` is provider-agnostic |
| Communication storage | `poc/sync.py` | Yes — `INSERT OR IGNORE` by `provider_message_id` |
| Conversation rules | `poc/sync.py` | Yes — operates on stored communications |
| Contact/company resolution | `poc/sync.py`, `poc/domain_resolver.py` | Yes |
| Credential storage | Token files on disk | No — Google OAuth specific |
| Rate limiting | `poc/rate_limiter.py` | Yes |

### What's already provider-agnostic

The `_store_thread()` function and everything downstream (conversation
creation rules, participant linking, contact resolution) already operates
on `ParsedEmail` objects — not Gmail API responses. The `ParsedEmail`
model is the natural boundary between provider-specific and
provider-agnostic code.

The `provider_accounts` table already stores `provider_type` and a generic
`sync_cursor` text field that can hold any provider's delta token.

---

## 4. Provider Interface

Each provider must implement a common interface. Preliminary design:

```
MessageProvider (abstract)
├── authenticate(account) → credentials/connection
├── fetch_initial(query, max_items, page_token) → (messages[], new_page_token)
├── fetch_since(cursor) → (messages[], new_cursor)
├── get_cursor() → cursor_string
├── parse_message(raw) → ParsedEmail
└── provider_type → str  ("gmail", "outlook", "imap", "twilio")
```

### Key contracts

- `fetch_since()` returns only messages that changed since the given
  cursor. Each provider maps this to its native delta mechanism.
- All methods return `ParsedEmail` objects (or a compatible superset) so
  the sync engine can process them uniformly.
- Authentication is provider-specific but managed through a common
  credential store.

---

## 5. Target Providers

| Provider | Protocol | Delta Mechanism | Auth | Priority |
|---|---|---|---|---|
| Gmail | REST API (v1) | `historyId` | OAuth 2.0 | Done |
| Outlook/Microsoft 365 | MS Graph API | `deltaLink` tokens | OAuth 2.0 (MSAL) | High |
| Generic IMAP | IMAP4 | `UIDNEXT` / `CONDSTORE HIGHESTMODSEQ` | Username/password or OAuth | Medium |
| Twilio (SMS) | REST API | Webhook or `DateSent` polling | API key | Medium |
| Apple iMessage | Local SQLite DB | File modification time | Local access | Low (macOS only) |
| WhatsApp Business | Cloud API | Webhooks | API token | Future |
| Signal | Unknown | Unknown | Unknown | Future |

---

## 6. Sync Lifecycle

Regardless of provider, the sync lifecycle follows the same pattern:

```
1. Load provider_account (type, credentials, sync_cursor)
2. Instantiate provider by type
3. Authenticate
4. If no sync_cursor → fetch_initial() with configured query/window
   Else → fetch_since(sync_cursor)
5. For each batch of messages:
   a. Pass to _store_thread() (provider-agnostic)
   b. Communications stored, conversations evaluated, participants linked
6. Save new sync_cursor to provider_accounts
7. Log sync result to sync_log
```

Steps 5a–5b are already implemented and provider-agnostic. The refactor
extracts steps 1–4 and 6 into the provider interface.

---

## 7. Data Flow

```
Provider API  →  MessageProvider.fetch_*()  →  ParsedEmail[]
                                                    │
                                                    ▼
                                    Sync Engine (_store_thread)
                                                    │
                              ┌─────────────┬───────┴────────┐
                              ▼             ▼                ▼
                       communications  conversations  contact_resolution
```

---

## 8. Schema Considerations

### Existing schema support

- `provider_accounts.provider_type` — already stores the provider name
- `provider_accounts.sync_cursor` — generic text field, works for any
  cursor type
- `communications.channel` — already supports "email", can add "sms",
  "chat", etc.
- `communications.source` — can store the provider type
- `communications.provider_message_id` — UNIQUE, works for any provider's
  message identifier

### Potential additions

- **Credential storage table** — move from token files on disk to
  encrypted DB storage (or reference a secrets manager)
- **Provider configuration** — provider-specific settings (IMAP host/port,
  API endpoints) need a structured home, possibly in `settings` or a new
  `provider_config` table
- **Channel-specific fields** — SMS messages lack subjects, HTML bodies,
  and threading; may need nullable columns or a separate `sms_metadata`
  table

---

## 9. Authentication & Credentials

| Provider | Auth Method | Credential Storage |
|---|---|---|
| Gmail | OAuth 2.0 | Token file (current), migrate to DB |
| Outlook/365 | OAuth 2.0 (MSAL) | Token in DB |
| IMAP | Password or OAuth | Encrypted in DB |
| Twilio | API Key + Secret | Encrypted in DB |

All OAuth providers should share a common token refresh flow. Non-OAuth
providers need a secure credential storage mechanism (encrypted at rest).

---

## 10. SMS/Messaging Considerations

SMS and chat platforms differ from email in important ways:

- **No subject line** — conversations must be identified by
  participant pair rather than thread ID.
- **No threading** — messages between two parties form a single
  implicit thread.
- **Phone number identity** — participants identified by phone number
  rather than email; contact resolution uses `phone_numbers` table
  instead of `contact_identifiers`.
- **Short messages** — no HTML body, no attachments (in basic SMS).
- **MMS** — multimedia messages include images/video that may need
  attachment storage.
- **Delivery status** — SMS has delivery receipts not present in email.

The `ParsedEmail` model may need to evolve into a more generic
`ParsedMessage` that accommodates both email and messaging semantics.

---

## 11. Phasing & Roadmap

### Phase 1: Refactor (extract provider interface)

- Define `MessageProvider` abstract base class
- Extract `GmailProvider` from existing `gmail_client.py` + `sync.py`
- Refactor `sync.py` to call provider interface instead of Gmail directly
- Rename `ParsedEmail` → `ParsedMessage` (or create compatible superset)
- Zero behavior change — Gmail works exactly as before through the new
  interface
- All existing tests continue to pass

### Phase 2: Microsoft Outlook/365

- Implement `OutlookProvider` using MS Graph API
- OAuth 2.0 flow with MSAL library
- `deltaLink`-based incremental sync
- Web UI: "Connect Outlook" button on Settings > Accounts

### Phase 3: Generic IMAP

- Implement `ImapProvider` using Python `imaplib` or `aioimaplib`
- Support CONDSTORE for efficient incremental sync where available
- Fallback to UID-based tracking for servers without CONDSTORE
- Web UI: IMAP configuration form (host, port, encryption, credentials)

### Phase 4: SMS (Twilio)

- Implement `TwilioProvider` using Twilio REST API
- Phone-number-based contact resolution
- Implicit threading by participant pair
- Webhook endpoint for real-time message receipt (stretch)

### Future phases

- WhatsApp Business API
- Calendar provider abstraction (parallel effort)
- Contact provider abstraction (Google → multi-provider)
- Push/webhook sync for supported providers

---

## 12. Open Questions

1. **ParsedEmail evolution** — should `ParsedEmail` be renamed/expanded,
   or should we create a new `ParsedMessage` base with `ParsedEmail` as
   a subclass?
2. **Credential encryption** — what encryption approach for storing
   non-OAuth credentials (IMAP passwords, API keys) in SQLite?
3. **IMAP server compatibility** — how many IMAP servers actually support
   CONDSTORE? Do we need a UID-only fallback from day one?
4. **SMS threading** — should SMS conversations be modeled as one
   conversation per contact pair, or grouped by time window?
5. **Rate limiting per provider** — current `RateLimiter` is generic;
   each provider has different quotas. Per-provider configuration needed?
6. **Provider health monitoring** — how to detect and handle expired
   tokens, revoked access, or provider outages gracefully?
7. **Migration path** — can existing Gmail accounts be migrated to the
   new provider interface without re-syncing?
8. **Attachments** — MMS images, WhatsApp media — unified attachment
   storage or per-channel?
