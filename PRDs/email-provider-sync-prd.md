# Email Provider Sync — Channel Sub-PRD

**Version:** 1.0
**Last Updated:** 10-08-26 13:05
**Status:** Approved 10-08-26 by the product owner — not yet implemented
**Parent Documents:** [communication-provider-sync-prd.md] (framework), [mail-client-prd.md] (functional area that consumes this contract)
**Entity Base PRD:** [communication-entity-base-prd.md]
**Referenced Documents:** [outbound-email-prd.md], [email-stripping.md], [mail-client-tdd.md]

> **V1.0 (10-08-26):** Initial draft. This is the "Email Provider Sync PRD" the PRD Index has listed as Planned since 2026-02-23, now scoped for the local-mirror architecture chosen on 10-08-26. It extends the framework adapter interface in [communication-provider-sync-prd.md] §5.1 with mailbox state (labels, flags), write-back actions, attachments, and send, and maps that contract onto Gmail, Microsoft Graph, and IMAP/SMTP.

---

## 1. Overview

### 1.1 Purpose

Define the single contract every email provider adapter implements, so the mail client ([mail-client-prd.md]) and the sync engine never know which provider is behind an account. Define how each supported provider maps onto that contract, including cursors, folder and label semantics, flag semantics, recovery, and rate limits.

### 1.2 Preconditions

- The provider account model from [communication-provider-sync-prd.md] §4 exists (`provider_accounts`, `user_provider_accounts`).
- The Communication record carries mailbox state columns and label tables defined in [mail-client-tdd.md] D-02 and D-03.
- The action outbox exists ([mail-client-tdd.md] D-04).

### 1.3 Non-Goals

- Non-email channels (SMS, voice, video) — their own child PRDs.
- Third-party aggregation services (Nylas, Unipile) — rejected in [communications-prd.md]; direct provider APIs only.
- Email content cleaning rules — [email-stripping.md] remains the specification; the adapter delivers raw parts and the pipeline cleans.

---

## 2. Context

### 2.1 Mailbox state on the Communication record

| Field | Role |
|---|---|
| `provider_message_id`, `provider_thread_id` | Provider identity; UNIQUE per account |
| `header_message_id`, `header_in_reply_to`, `header_references`, `header_reply_to` | RFC 5322 identity and threading; `header_message_id` is the cross-account duplicate key |
| `is_read`, `is_starred` | Mirrored flags; written by sync and by user actions |
| `communication_labels` rows | The message's provider labels or folder membership |
| `provider_metadata` | Provider-specific extras (Gmail `historyId` at fetch, Graph `changeKey`, IMAP `uid` and `uidvalidity`) |
| `attachments` rows | Metadata (name, type, size, provider part id, cid); content fetched on demand |

### 2.2 Provider account fields added

| Field | Role |
|---|---|
| `sync_cursor` | Provider-specific incremental position (existing) |
| `backfill_cursor` | Position of the historical backfill job; NULL when complete |
| `backfill_complete_at` | When the whole mailbox was present |
| `last_error`, `last_error_at` | Surfaced in the folder tree and Accounts settings |
| `capabilities` | JSON set of capability flags the adapter reports (§3.3) |

---

## 3. Adapter Contract

### 3.1 Interface

```
MailProvider
  ├── authenticate(account) → session
  ├── capabilities() → {labels | folders, star, spam, snooze_label, push, server_search, send, drafts}
  ├── list_folders(session) → [Folder(id, name, kind, parent)]
  ├── fetch_initial(session, scope) → [RawMessage], cursor
  ├── fetch_backfill(session, backfill_cursor, batch) → [RawMessage], next_backfill_cursor | None
  ├── fetch_incremental(session, cursor) → Delta(added, deleted, label_changes, flag_changes), new_cursor
  ├── fetch_message(session, provider_message_id) → RawMessage          # full MIME parts on demand
  ├── fetch_attachment(session, provider_message_id, part_id) → bytes
  ├── apply_action(session, Action) → ActionResult                       # one of §3.2
  ├── send(session, OutboundMessage) → provider_message_id, provider_thread_id
  ├── get_sync_status(session) → SyncStatus
  └── revoke(session) → void
```

`RawMessage` carries: provider ids, thread id, the full header map, parsed participants with display names (From, To, Cc, Bcc, Reply-To), date, text and HTML parts, attachment parts (metadata only), provider labels or folder, flags (read, starred), and provider metadata.

### 3.2 Actions

| Action | Payload | Gmail | Microsoft Graph | IMAP |
|---|---|---|---|---|
| `mark_read` / `mark_unread` | message ids | remove/add `UNREAD` | `isRead` patch | `\Seen` flag |
| `star` / `unstar` | message ids | add/remove `STARRED` | `flag.flagStatus` | `\Flagged` |
| `archive` | message ids | remove `INBOX` | move to Archive folder | move to Archive (create if absent) |
| `unarchive` | message ids | add `INBOX` | move to Inbox | move to INBOX |
| `trash` / `untrash` | message ids | add/remove `TRASH` | move to Deleted Items / back | move to Trash / back |
| `spam` / `unspam` | message ids | add/remove `SPAM` | move to Junk / back | move to Junk / back |
| `add_label` / `remove_label` | message ids, label id | modify `labelIds` | category add/remove | copy to folder / remove (IMAP has no multi-label; see §5.3) |
| `move` | message ids, folder id | label swap | move | move |
| `create_label` | name, parent | `labels.create` | `mailFolders` or category create | folder create |
| `snooze` / `unsnooze` | message ids, until | archive + `CRMExtender/Snoozed` label | move to a `CRMExtender/Snoozed` folder | move to a `CRMExtender.Snoozed` folder |

Actions are idempotent: applying `mark_read` to a read message succeeds. An action whose target no longer exists returns `ActionResult.gone` and the outbox marks it done, not failed.

### 3.3 Capability flags

Adapters report what they can do; the mail client hides or adapts affordances accordingly. `labels` (multi-label, Gmail) versus `folders` (single location, Graph and IMAP) changes the label picker to a move picker. `push` enables watch-based sync in Phase 5. `server_search` is reserved; V1 search is local only.

---

## 4. Key Processes

### KP-EPS-01: Initial sync

**Trigger:** Account connected, or full re-sync requested.
1. `list_folders` populates `mailbox_labels` for the account with system kinds mapped (§5).
2. `fetch_initial` pulls the configured window (default `newer_than:90d` equivalent) across all folders, newest first, in batches; each message is normalized and stored with labels and flags.
3. The incremental cursor is stored; `backfill_cursor` is set to the oldest fetched message's position; the account shows "Syncing".
4. The pipeline (participant resolution, conversation formation, triage, summarization) runs as today.

### KP-EPS-02: Incremental sync

**Trigger:** Scheduler tick or "Sync now".
1. `fetch_incremental(cursor)` returns a delta: added messages, deleted ids, label changes, flag changes.
2. Additions are stored; deletions set the Communication to `archived` and remove all labels; label and flag changes update `communication_labels`, `is_read`, `is_starred`.
3. Changes the mirror itself originated (recorded in the outbox as pushed within the last interval) are recognized by message id and action and not re-applied as foreign changes.
4. The new cursor is stored only after the delta is committed.

### KP-EPS-03: Backfill

**Trigger:** Scheduler tick when `backfill_cursor` is not NULL and `mail.backfill_enabled`.
1. `fetch_backfill(backfill_cursor, batch)` returns the next oldest batch.
2. Messages are stored; the pipeline runs with summarization deferred to the Batch API path ([mail-client-prd.md] MAIL-49).
3. The cursor advances per batch; a NULL return marks `backfill_complete_at`.

### KP-EPS-04: Cursor recovery

**Trigger:** The provider rejects the cursor (Gmail 404 on `history.list`, Graph 410 on a delta link, IMAP `UIDVALIDITY` change).
1. The adapter reports `CursorInvalid`.
2. The engine runs a reconciliation: list message ids in each folder since the last successful sync time minus a safety margin; add missing, archive those no longer present at the provider (only for Gmail and Graph, where presence is authoritative; for IMAP a full UID list per folder is compared).
3. A fresh cursor is stored. Nothing is deleted locally during recovery.

### KP-EPS-05: Pushing an action

**Trigger:** Outbox worker finds pending rows for an account.
1. Rows are pushed in creation order; batches where the provider allows (`batchModify` on Gmail).
2. Transient failures (HTTP 429, 5xx, network) back off exponentially; permanent failures (404 label, 403 scope) dead-letter with the provider's message.
3. Successful pushes record the provider's resulting state so the next incremental delta does not echo them.

### KP-EPS-06: Sending

**Trigger:** Undo window elapsed, or scheduled time reached.
1. `send(OutboundMessage)` with In-Reply-To and References from the stored headers of the replied-to message, attachments from Documents.
2. The returned provider ids are stored on the local Communication (created at send time with `source=composed`).
3. The next incremental delta's Sent-folder addition is matched by provider message id and merged, never duplicated.

---

## 5. Provider Mappings

### 5.1 Gmail (Google API)

| Concern | Mapping |
|---|---|
| Authentication | OAuth 2.0; scopes `gmail.modify` (superset of readonly, includes label and flag changes), `gmail.send`, plus existing contacts and calendar readonly |
| Folders | Labels. System labels `INBOX`, `SENT`, `DRAFT`, `SPAM`, `TRASH`, `STARRED`, `UNREAD`, `IMPORTANT`, `CATEGORY_*`; user labels nested by `/` |
| Initial | `threads.list` with the window query, `messages.get` format `full` (parts metadata, no attachment bytes) |
| Incremental | `history.list` with `historyTypes` = `messageAdded`, `messageDeleted`, `labelAdded`, `labelRemoved`; read and starred flags arrive as label changes |
| Backfill | `messages.list` with `before:` paging by epoch |
| Attachments | `messages.attachments.get` by part id; inline parts resolved by `Content-ID` |
| Actions | `messages.batchModify` for label changes; `messages.trash`/`untrash` |
| Send | `messages.send` with `threadId` and raw MIME; drafts via `drafts.create` only if provider-draft sync is enabled (not in V1) |
| Recovery | `history.list` 404 → KP-EPS-04 using `messages.list` `after:` |
| Rate limits | 250 quota units per user per second; keep the existing token-bucket limiter |
| Push (Phase 5) | `users.watch` to a Pub/Sub topic |

**Known risk:** an OAuth client in *testing* publishing status expires refresh tokens after seven days. Confirm the client's status before relying on background sync ([mail-client-prd.md] §9.1).

### 5.2 Microsoft Graph (Microsoft 365 and Outlook.com)

| Concern | Mapping |
|---|---|
| Authentication | OAuth 2.0 with MSAL; scopes `Mail.ReadWrite`, `Mail.Send`, `offline_access`, `User.Read` |
| Folders | `mailFolders` hierarchy; well-known names `inbox`, `sentitems`, `drafts`, `deleteditems`, `junkemail`, `archive`; categories serve as labels |
| Initial | `/me/mailFolders/{id}/messages` with `$filter=receivedDateTime ge …`, `$select` for headers and `internetMessageHeaders` |
| Incremental | `/me/mailFolders/{id}/messages/delta` per folder with stored `deltaLink`s; flag changes arrive as updates |
| Backfill | Same listing with `receivedDateTime lt` paging |
| Attachments | `/messages/{id}/attachments/{id}/$value` |
| Actions | `PATCH` `isRead`, `flag`; `POST …/move`; categories via `PATCH` |
| Send | `/me/sendMail` with MIME or JSON; reply via `/createReply` when threading headers are needed |
| Recovery | `410 Gone` on delta → KP-EPS-04 |
| Rate limits | Per-app throttling with `Retry-After`; honor it |
| Push (Phase 5) | Change notifications (webhook) |

### 5.3 IMAP and SMTP (generic)

| Concern | Mapping |
|---|---|
| Authentication | Username and password or app password; XOAUTH2 where the host supports it; settings detected from the address domain with a user-editable override |
| Folders | Mailboxes via `LIST`; special-use attributes (`\Sent`, `\Drafts`, `\Trash`, `\Junk`, `\Archive`) when advertised, else name heuristics |
| Initial | `UID SEARCH SINCE <date>` per folder, `UID FETCH` with `BODYSTRUCTURE` and headers; bodies fetched on demand |
| Incremental | Per folder: `UID FETCH <last_uid+1>:* (FLAGS)` for additions and `UID FETCH 1:* (FLAGS)` with `CHANGEDSINCE` when `CONDSTORE` is available; deletions detected by UID set comparison |
| Backfill | `UID SEARCH BEFORE <date>` paging |
| Attachments | `UID FETCH BODY[part]` |
| Actions | `STORE` flags; `MOVE` (or `COPY` + `\Deleted` + `EXPUNGE`) |
| Labels | No multi-label; `add_label` is `COPY` to a folder, which the mail client presents as "move" per the `folders` capability |
| Send | SMTP with STARTTLS or implicit TLS; the sent copy is appended to the Sent mailbox with `APPEND` where the server does not do it |
| Recovery | `UIDVALIDITY` change → KP-EPS-04 with full UID comparison for that folder |
| Rate limits | Connection count; one persistent connection per account, IDLE on INBOX when supported |

---

## 6. Cross-Cutting Concerns

- **Idempotent writes** ([product-tdd.md] §11.2): every stored message is keyed on (account, provider message id); every outbox push is keyed on (action, target) within a window.
- **Credentials:** token files remain in V1; encrypted storage is Phase 5 ([mail-client-prd.md] MAIL-51).
- **Audit:** `sync_log` gains per-run counts of additions, deletions, label changes, actions pushed, and backfill progress.
- **Shared accounts:** adapters are unaware of sharing; permissions are enforced above the adapter ([mail-client-prd.md] §6.2).

---

## 7. Task List

```
- [x] EPS-01: MailProvider interface and MailMessage, Delta, Action, ActionResult types (poc/providers/base.py) — v10.6, 10-08-26. The normalized type is `ParsedEmail` extended with the mailbox-state fields (TDD D-15).
- [x] EPS-02: Adapter registry keyed by provider_accounts.provider — v10.6 (`poc/providers/__init__.py`, lazy adapter import)
- [x] EPS-03: GmailProvider implementing every method; sync.py and outbound.py call only the interface — v10.6 (`poc/providers/gmail.py`; `sync_service.py` and `__main__.py` also switched; `migrate_refetch_emails.py` is a retired one-off and still imports the client directly)
- [x] EPS-04: Gmail history processing for labelAdded/labelRemoved; flag mapping to is_read/is_starred — v10.6 **adapter side only**: `fetch_incremental` returns the label and flag changes in the Delta; the engine ignores them until MAIL-10
- [x] EPS-05: Gmail backfill by before: paging with cursor persistence — v10.6 adapter side (`fetch_backfill`, cursor `"<epoch>|<page_token>"`); the resumable job is MAIL-11
- [x] EPS-06: Gmail attachment fetch and Content-ID resolution — v10.6 adapter side (`fetch_attachment`; `_parse_message` captures attachment metadata with `content_id`/`is_inline`); storage and cache are MAIL-15
- [x] EPS-07: Gmail batchModify action pushing; trash/untrash; label creation — v10.6 adapter side (`apply_action`, all §3.2 kinds; 404 → `gone`); the outbox worker is MAIL-14
- [ ] EPS-08: Cursor recovery and reconciliation pass (KP-EPS-04)
- [ ] EPS-09: Echo suppression for self-originated changes (KP-EPS-02 step 3)
- [x] EPS-10: Send through the interface with stored threading headers; sent-copy reconciliation — v10.6 send path (`outbound.send_email` → `provider.send(OutboundMessage)`); sent-copy reconciliation pending with MAIL-36
- [ ] EPS-11: MicrosoftGraphProvider (Phase 3)
- [ ] EPS-12: ImapSmtpProvider with provider detection by domain (Phase 3); populate docs/Public_email_provider_detection.MD
- [ ] EPS-13: Contract test suite every adapter must pass from recorded fixtures
```

---

## 8. Test Plan

| Test ID | Description | Type | Covers |
|---|---|---|---|
| EPS-T01 | Registry resolves the adapter for each provider value; unknown provider raises a clear error | unit | EPS-02 |
| EPS-T02 | GmailProvider normalizes a fixture message into RawMessage with all headers, participants with names, labels, flags, attachment metadata | unit | EPS-03 |
| EPS-T03 | History fixture with label and flag changes produces the expected Delta | unit | EPS-04 |
| EPS-T04 | Backfill advances the cursor and stops with None at mailbox start | unit | EPS-05 |
| EPS-T05 | Attachment fetch returns bytes; cid resolves to the right part | unit | EPS-06 |
| EPS-T06 | Each §3.2 action produces the expected Gmail request; `gone` is returned for a missing message | unit | EPS-07 |
| EPS-T07 | Invalid cursor triggers reconciliation that adds missing and archives absent messages without deleting rows | unit | EPS-08 |
| EPS-T08 | A pushed mark_read is not re-applied as a foreign change in the next delta | unit | EPS-09 |
| EPS-T09 | Send carries In-Reply-To/References; the Sent-folder copy merges by provider message id | unit | EPS-10 |
| EPS-T10 | Contract suite passes for Gmail, Graph, and IMAP adapters | unit | EPS-13 |

---

## 9. Change Log

| Rev | Date (MM-DD-YY HH:MM) | Author | Change |
|---|---|---|---|
| 1.1 | 10-08-26 12:33 | Claude (Claude Code) | Status set to Approved on the product owner's approval. |
| 1.0 | 10-08-26 01:30 | Claude (Claude Code) | Initial draft for approval. |
