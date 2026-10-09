# Mail Client — Functional Area PRD

**Version:** 1.0
**Last Updated:** 10-09-26 12:57
**Status:** Approved 10-08-26 by the product owner — Phase 0 in progress (MAIL-01, MAIL-04 done); nothing in Phases 1–5 is built
**Product PRD:** [PRD.md] (docs/), [product-tdd.md]
**Master Glossary:** [glossary.md]
**Parent Documents:** [communication-entity-base-prd.md], [communication-provider-sync-prd.md], [outbound-email-prd.md], [gui-functional-requirements-prd.md]
**Child Documents:** [email-provider-sync-prd.md] (adapter contract and provider mappings), [mail-client-tdd.md] (technical decisions)

> **V1.0 (10-08-26):** Initial draft. Written after the 10-08-26 project review that found CRMExtender to be a mail *watcher* (selective import, read-only Gmail scope, no inbox, no write-back) rather than a mail *client*. The product owner chose the **local mirror with write-back** architecture on 10-08-26 (recorded as decision D-01 in [mail-client-tdd.md]). This document defines the mail-client experience that architecture enables. Phase plan in §5.3.

---

## 1. Scope & Boundaries

### 1.1 Purpose

Make CRMExtender the one interface through which the product owner reads, triages, searches, and answers mail for every email account they own. Today the application imports a window of mail from Gmail to feed contact and conversation intelligence; the user still lives in the provider's own client. This functional area turns the imported mail into a complete, two-way mirror of each mailbox and puts a purpose-built mail surface on top of it, so the provider's client is no longer needed for daily work.

What makes this worth building instead of using an existing mail client: every message is read beside the relationship context CRMExtender already holds — the contact, the company, the conversation history, the open tasks, and the AI summary. That context is the product; the mail client is how it reaches the user every day.

### 1.2 Actors

| Actor | Role | Access Level |
|---|---|---|
| Mailbox owner (user) | Reads, triages, searches, replies, composes in their own connected accounts | Full mail actions on accounts they own; read on accounts shared with them |
| Administrator | Manages provider connections for the tenant, sync settings, retention | All of the above plus account connect/disconnect for any user, sync configuration |
| Sync service (system) | Mirrors mailboxes, applies queued actions, indexes content | System |

### 1.3 Boundaries

**In scope:**
- A unified inbox across all connected accounts and a per-account inbox.
- Folder and label navigation: Inbox, Starred, Snoozed, Sent, Drafts, Archive (All Mail), Spam, Trash, and the provider's user labels or folders.
- Read and unread state, starring, archiving, trashing, spam marking, labeling and moving, snoozing, and marking unread, with every action pushed back to the provider.
- A message list in email form (sender, subject, snippet, date, account, attachment and star indicators, unread weight) and a thread reading pane.
- Full-text search over mail with mailbox search operators.
- Attachment viewing, download, and upload.
- Compose, reply, reply-all, forward, drafts, signatures, undo-send, and scheduled send, as specified in [outbound-email-prd.md] and brought into the mail surface.
- Background synchronization on a schedule, with per-account health visible in the user interface.
- A keyboard model for the whole surface.
- Notifications of new mail inside the application.

**Out of scope (owned by other PRDs):**
- The adapter contract and each provider's mapping — [email-provider-sync-prd.md].
- The provider account model, connect and disconnect, credentials, sync audit trail — [communication-provider-sync-prd.md].
- Conversation formation, summaries, and the Conversation view — [conversation-formation-prd.md], [conversation-view-prd.md].
- Noise filtering of what receives AI processing — [communication-triage-prd.md]. The mail client shows all mail; triage decides what is summarized.
- Templates, automation rules, click tracking, bounce handling — [outbound-email-prd.md].
- Calendar and contacts synchronization — [event-calendar-sync-prd.md].
- Desktop (operating-system) notifications and a phone layout — deferred to the hardening phase, see §5.3.

### 1.4 Related Documents

| Document | Relationship |
|---|---|
| [communication-entity-base-prd.md] | The Communication record every message in the mirror is stored as. This PRD adds mailbox state (labels, flags) to that record. |
| [communication-provider-sync-prd.md] | Provider account lifecycle and the sync framework this area extends with write-back. |
| [email-provider-sync-prd.md] | Child document: adapter contract, Gmail, Microsoft Graph, and IMAP mappings. |
| [outbound-email-prd.md] | Compose and send requirements; this PRD places them in the mail surface. |
| [communication-view-prd.md] | The existing Communication full view. The reading pane in §2.3 supersedes it for mail; the full view remains for the grid. |
| [gui-functional-requirements-prd.md] | Shell, panels, keyboard principles (§23), "ten emails in ten keystrokes" goal. |
| [mail-client-tdd.md] | Technical decisions, including the local-mirror decision D-01. |

---

## 2. Capabilities

### 2.1 Mailbox mirror

Every message in every folder of every connected account is stored locally, with its provider labels or folders, read and starred flags, full header set (Message-ID, In-Reply-To, References, Reply-To, Bcc, recipient display names), and attachment metadata. The mirror is kept current by scheduled incremental synchronization that processes additions, deletions, and label and flag changes. Historical mail beyond the initial window is backfilled in the background until the whole mailbox is present.

### 2.2 Inbox and folders

A **Mail** surface, reached from the icon rail, shows a folder tree per account and a unified set at the top (Unified Inbox, Starred, Snoozed, Drafts, Sent). Each folder shows an unread count. Selecting a folder shows its messages as threads, newest first. The unified inbox merges the inboxes of all accounts and shows an account chip on each row.

### 2.3 Reading

Selecting a thread opens a reading pane. Older messages in the thread are collapsed to one line each; the newest unread message is expanded. Each message shows sender, recipients, date, account, attachments, and body. The body is rendered inside an isolated frame; remote images are blocked by default and can be loaded per message or allowed per sender. Quoted text is collapsed. Opening a thread marks its unread messages read after a short dwell, and the change is pushed to the provider.

### 2.4 Actions

Archive, trash, spam, star, mark unread, label or move, and snooze act on the selected thread or on a multi-selection. Each action takes effect in the user interface at once and is queued for the provider; a failed push is retried and surfaced if it keeps failing. Snooze hides a thread until a chosen time and returns it to the inbox as unread.

### 2.5 Search

A search box over the whole mirror with operators: `from:`, `to:`, `cc:`, `subject:`, `has:attachment`, `in:<folder>`, `label:`, `account:`, `is:unread`, `is:starred`, `before:`, `after:`, and free text matched against subject and body. Results are threads in the same list form as a folder. Search runs locally and returns in under half a second for the production data profile.

### 2.6 Compose and send

Compose opens as a docked panel that can be minimized, not a blocking modal. Reply and reply-all open inline at the bottom of the thread. Attachments can be added by drag or picker and are stored as Documents. The account's default signature is inserted. Drafts save automatically and appear in the Drafts folder, where they can be resumed. Send has a ten-second undo window and an optional scheduled time. Sent messages appear in the Sent folder immediately and are reconciled with the provider's copy on the next sync.

### 2.7 Synchronization and health

Each account synchronizes on an interval in the background. The Accounts settings page and the mail surface's folder tree show, per account, the last successful sync, whether a sync is running, and any error (expired credentials, rate limiting, provider outage) with the action needed. A per-account "Sync now" exists alongside the global one.

### 2.8 Relationship context

Beside the reading pane, a context column shows what CRMExtender knows about the thread's external participants: contact card, company, relationship score, last interaction, open tasks, and the conversation summary if one exists. This is the capability no provider's client can offer and is the reason the user reads mail here.

### 2.9 Keyboard model

The whole surface is operable from the keyboard. The bindings extend [gui-functional-requirements-prd.md] §23 and are listed in §5.1 under "Keyboard navigation".

### 2.10 Notifications

New mail arriving in an inbox folder raises an in-application notification (toast and unread badge on the Mail rail icon). Notification scope is configurable per account (all inbox mail, mail from known contacts only, or none).

---

## 3. Configuration

### 3.1 Configuration Table

| Setting | Description | Type | Default | Scope | Editable By |
|---|---|---|---|---|---|
| `mail.sync_interval_seconds` | Interval between incremental syncs per account (shipped as setting key `mail_sync_interval_seconds`; per-provider override not yet implemented) | integer | 120 | system, provider | admin |
| `mail.backfill_enabled` | Whether historical backfill beyond the initial window runs | boolean | true | provider | admin |
| `mail.backfill_batch_size` | Messages fetched per backfill batch | integer | 200 | system | admin |
| `mail.mark_read_dwell_ms` | Time a thread must be open before it is marked read; 0 disables auto mark-read (shipped as system setting `mail_mark_read_dwell_ms`; per-user scope deferred) | integer | 1500 | user | user |
| `mail.remote_images` | `block`, `allow_known_contacts`, `allow_all` | enum | `block` | user | user |
| `mail.notifications` | `all`, `known_contacts`, `none` | enum | `known_contacts` | user, provider | user |
| `mail.undo_send_seconds` | Undo-send window | integer | 10 | user | user |
| `mail.default_account_id` | Account used for new compose when no context resolves one | text | first active account | user | user |
| `mail.unified_inbox_accounts` | Accounts included in the unified inbox | list | all active | user | user |
| `mail.attachment_cache_mb` | Disk budget for the local attachment cache | integer | 2048 | system | admin |
| `mail.action_retry_max` | Attempts before a queued provider action is marked failed | integer | 8 | system | admin |
| `summarize_settle_minutes` | Minutes a thread must be quiet before it is summarized; 0 summarizes on every sync (added 10-08-26, MAIL-19) | integer | 15 | system | admin |
| `summarize_max_per_sync` | Conversations summarized per sync run, newest first; 0 means unlimited (added 10-08-26, MAIL-19) | integer | 500 | system | admin |

**Scope values:** `system` (one value for the tenant), `provider` (per provider account, overriding system), `user` (per-user preference).

**Editable By values:** `admin`, `user` (own settings only).

### 3.2 Configuration Rules

- `mail.sync_interval_seconds` is never below 60; the provider's rate limits are respected regardless of the value.
- `mail.mark_read_dwell_ms` of 0 means read state changes only by explicit action.
- Disabling `mail.backfill_enabled` stops the backfill job at its next checkpoint; re-enabling resumes from the checkpoint.
- Settings follow the four-level cascade in [product-tdd.md] §10.2.

---

## 4. Key Processes

### KP-MAIL-01: Morning triage of the unified inbox

**Trigger:** User opens the Mail surface.
**Actor:** Mailbox owner.

**Steps:**
1. The Unified Inbox is selected; threads are listed newest first with unread weight and account chips. Unread counts show on every folder.
2. The user moves down the list with `j` and `k`. The reading pane follows the selection and shows the newest unread message expanded with the relationship context column beside it.
3. For each thread the user presses one key: `e` archive, `#` trash, `s` star, `z` snooze (a picker opens), `l` label, `r` reply, `u` mark unread. The thread leaves the list where appropriate and the selection advances.
4. Every action is applied locally at once and queued to the provider. The status bar shows "n actions pending" until the queue drains.
5. Opening a thread marks it read after the dwell time.

**Outcome:** The inbox holds only threads the user chose to leave. Every provider's mailbox shows the same state within one sync interval.

### KP-MAIL-02: Reading a thread with context

**Trigger:** User selects a thread.
**Actor:** Mailbox owner.

**Steps:**
1. The reading pane shows the thread's messages, older ones collapsed to a sender-and-snippet line, the newest unread expanded.
2. Each expanded message renders in an isolated frame with remote images blocked. A banner offers "Load images" and "Always load from this sender".
3. Attachments list with name, size, and type. Clicking previews an image or PDF inline; download fetches the file from the provider if not cached.
4. The context column shows the external participants' contact cards, company, relationship score, last interaction, open tasks, and conversation summary. Unknown senders show a "Create contact" affordance.
5. Pressing `o` on a collapsed message expands it; `Shift+o` expands all.

**Outcome:** The user has read the thread and seen the relationship context without leaving the surface.

### KP-MAIL-03: Replying inline

**Trigger:** User presses `r`, `a`, or `f` on a thread, or clicks Reply on a message.
**Actor:** Mailbox owner.

**Steps:**
1. A composer opens inline at the bottom of the thread, addressed per the action (reply, reply-all, forward), from the account the thread belongs to, with the default signature inserted and quoted content collapsed below the cursor.
2. The user writes, optionally adds attachments, and presses `Cmd/Ctrl+Enter` to send.
3. The message moves to the Sent folder at once with a ten-second "Undo" toast. If the user clicks Undo, the composer reopens with the content.
4. After the window the message is sent through the account's adapter with In-Reply-To and References headers set from the stored headers of the message replied to.
5. The next sync reconciles the provider's sent copy with the local record by provider message id.

**Outcome:** The reply is in the provider's Sent folder, threaded correctly, and in the local mirror once.

### KP-MAIL-04: Composing a new message

**Trigger:** User presses `c` or clicks Compose.
**Actor:** Mailbox owner.

**Steps:**
1. A docked composer opens. The From account defaults to `mail.default_account_id` or, when opened from a contact or conversation, to the account resolved by [outbound-email-prd.md] §9.
2. Recipients autocomplete from contacts and from addresses seen in the mirror.
3. The draft saves every thirty seconds and on blur, and appears in the Drafts folder.
4. The composer can be minimized to a bar at the bottom of the shell and restored; up to three composers may be open.
5. Send follows KP-MAIL-03 steps 3–5. Schedule send stores the time and the sync service sends at that time.

**Outcome:** The message is sent or scheduled; the draft is removed from Drafts.

### KP-MAIL-05: Searching all mail

**Trigger:** User presses `/` in the Mail surface or types in the mail search box.
**Actor:** Mailbox owner.

**Steps:**
1. The user types free text and operators (§2.5). Operator tokens are highlighted as they are recognized.
2. Results list threads across all accounts (or the account in `account:`), newest first, with matched terms highlighted in snippets.
3. Selecting a result opens it in the reading pane; the folder tree shows which folder the thread is in.
4. The search can be saved as a view in the folder tree.

**Outcome:** The user finds mail from any account in one place without the provider's search.

### KP-MAIL-06: Snoozing and returning

**Trigger:** User presses `z` on a thread.
**Actor:** Mailbox owner; sync service for the return.

**Steps:**
1. A picker offers later today, tomorrow, this weekend, next week, and a custom date and time.
2. The thread leaves the inbox and appears in the Snoozed folder with its return time. At the provider the thread is archived and a `CRMExtender/Snoozed` label is applied so the state is visible in other clients.
3. At the return time the sync service moves the thread back to the inbox, removes the label, and marks it unread. A notification fires.

**Outcome:** The thread is back in the inbox at the chosen time in every client.

### KP-MAIL-07: Background synchronization and health

**Trigger:** Timer (`mail.sync_interval_seconds`) per account, or "Sync now".
**Actor:** Sync service.

**Steps:**
1. For each active account, the adapter fetches changes since the stored cursor: new messages, deletions, label additions and removals, flag changes.
2. Changes apply to the mirror. New inbox messages raise notifications per `mail.notifications`.
3. Queued actions for the account are pushed in order. Permanent failures are marked and surfaced.
4. The backfill job, if enabled and not complete, fetches the next batch of historical mail.
5. Per-account status (last success, running, error) updates in the folder tree and in Accounts settings.
6. If the cursor is invalid, the adapter recovers per [email-provider-sync-prd.md] §4.4 and the user is not interrupted.

**Outcome:** Every mirror is within one interval of the provider; every user action has reached the provider or is visibly pending or failed.

### KP-MAIL-08: Connecting an account for mail

**Trigger:** User clicks Connect account in Settings → Accounts.
**Actor:** Mailbox owner or administrator.

**Steps:**
1. The user picks the provider: Google, Microsoft, or Other (IMAP and SMTP).
2. Google and Microsoft run their consent flows requesting read, modify, and send scopes. IMAP asks for server, port, credentials, and detects common providers from the address domain.
3. The account registers active with an empty cursor; initial sync begins with the configured window; backfill is queued.
4. The folder tree shows the account with a "Syncing" indicator and growing counts.

**Outcome:** The account is mirrored and usable in the unified inbox.

---

## 5. Action Catalog

### 5.1 Simple Actions

#### Mark read / mark unread
**Trigger:** Dwell on open thread (read), key `u` or menu (unread), or `Shift+i`/`Shift+u`.
**Inputs:** Thread or selected messages.
**Outcome:** `is_read` updated locally; a `mark_read`/`mark_unread` action queued to the provider. Unread counts update.
**Business Rules:** Dwell is per `mail.mark_read_dwell_ms`. Marking a thread unread marks only its newest message unread.
**Supports processes:** KP-MAIL-01, KP-MAIL-02.

#### Archive
**Trigger:** Key `e` or button.
**Inputs:** Selected threads.
**Outcome:** Inbox label removed locally and at the provider. The thread remains in All Mail. The Communication's own `is_archived` flag (CRM soft delete) is **not** changed; see §6.4.
**Business Rules:** Archiving from a search result or label view removes only the Inbox label.
**Supports processes:** KP-MAIL-01.

#### Trash and Spam
**Trigger:** Key `#` (trash), `!` (spam), or button.
**Inputs:** Selected threads.
**Outcome:** Provider trash or spam state applied; the thread leaves all folders except Trash or Spam. Conversation membership is unchanged. Restore is available from those folders for the provider's retention period.
**Business Rules:** Trashed messages are hidden from search unless `in:trash` is given. Permanent deletion is not offered in V1.
**Supports processes:** KP-MAIL-01.

#### Star
**Trigger:** Key `s` or star icon.
**Outcome:** Starred flag toggled locally and at the provider.
**Supports processes:** KP-MAIL-01.

#### Label or move
**Trigger:** Key `l` (label picker) or `v` (move picker).
**Inputs:** Selected threads, one or more labels or a destination folder.
**Outcome:** Labels added or removed; for folder-based providers, the message moves. New labels can be created from the picker and are created at the provider.
**Business Rules:** System folders cannot be deleted or renamed from CRMExtender in V1.
**Supports processes:** KP-MAIL-01.

#### Snooze
See KP-MAIL-06.

#### Select and bulk act
**Trigger:** `x` toggles selection; `Shift+click` ranges; `Cmd/Ctrl+a` selects the visible list.
**Outcome:** Any simple action applies to the selection and queues one provider action per message.
**Business Rules:** Bulk actions over 200 messages show a confirmation with the count.

#### Keyboard navigation
| Key | Action | Context |
|---|---|---|
| `j` / `k` | Next / previous thread | List or reading pane |
| `Enter` / `o` | Open thread / expand message | List / reading pane |
| `Esc` | Close reading pane, then clear selection, per [gui-functional-requirements-prd.md] §23.3 | Mail surface |
| `e` | Archive | Thread selected |
| `#` | Trash | Thread selected |
| `!` | Report spam | Thread selected |
| `s` | Star | Thread selected |
| `u` | Mark unread | Thread selected |
| `z` | Snooze | Thread selected |
| `l` / `v` | Label / move | Thread selected |
| `r` / `a` / `f` | Reply / reply all / forward | Thread open |
| `c` | Compose | Mail surface |
| `/` | Focus search | Mail surface |
| `g i`, `g s`, `g t`, `g d`, `g a` | Go to Inbox, Starred, Sent, Drafts, All Mail | Mail surface |
| `1`–`9` | Switch to account n's inbox; `0` unified | Mail surface |
| `Cmd/Ctrl+Enter` | Send | Composer |
| `?` | Show shortcut sheet | Mail surface |

These do not conflict with the global bindings in [gui-functional-requirements-prd.md] §23.2; `Cmd/Ctrl+K` remains global search over entities.

#### Load remote images
**Trigger:** Banner button on a message.
**Outcome:** Images load for this message; "Always from this sender" records the sender in the user's allow list.
**Supports processes:** KP-MAIL-02.

#### Download or preview attachment
**Trigger:** Click on an attachment row.
**Outcome:** The file is fetched from the provider through the adapter if not cached, cached on disk, and streamed to the browser. Images and PDFs preview inline.
**Supports processes:** KP-MAIL-02.

#### Sync now (account)
**Trigger:** Button on the account's folder-tree header or in Accounts settings.
**Outcome:** An incremental sync runs for that account only, respecting the single-run-per-account rule.
**Supports processes:** KP-MAIL-07.

### 5.2 Complex Actions (Sub-PRDs)

| Action | Sub-PRD | Description |
|---|---|---|
| Provider adapters and sync engine | [email-provider-sync-prd.md] | Adapter contract, Gmail, Microsoft Graph, IMAP/SMTP mappings, cursors, action outbox, backfill, attachments |
| Compose, send, drafts, signatures, scheduled send, undo-send | [outbound-email-prd.md] | Already specified; this PRD adds the inline and docked composer placement (§2.6) and the Sent/Drafts folder presentation |
| Relationship context column | [contact-view-prd.md], [conversation-view-prd.md] | Reuses contact and conversation cards; no new data |

### 5.3 Delivery Phases

Each phase ships as a release with a VERSION bump, task checkboxes updated in this document, and implementation decisions written to [mail-client-tdd.md].

| Phase | Name | Scope | Tasks |
|---|---|---|---|
| 0 | Close the ledger | Commit stranded 2026-07-10 work; re-authorize the deactivated account; rotate the Anthropic key; approve this PRD, the child PRD, and the TDD | MAIL-01–04 |
| 1 | Mail store foundation | Adapter interface with Gmail behind it; `gmail.modify` scope; full headers, labels, flags, attachment metadata; label tables; action outbox; label-change sync; full-mailbox backfill; FTS5 search; per-account scheduler; attachment cache | MAIL-05–20 |
| 2 | Mail surface | `/app/mail` with folder tree, message list, reading pane, context column; all actions; keyboard model; isolated rendering; composer upgrades; live updates; per-account health; first frontend test harness | MAIL-21–40 |
| 3 | Every account | Connect the remaining Google accounts (cbmentors.org, case.edu); cross-account duplicate handling. Microsoft Graph and IMAP/SMTP adapters deferred until a non-Google account appears (§9.2) | MAIL-41–45 |
| 4 | CRM-only intelligence | Priority inbox; awaiting-reply reminders; AI reply drafts; summarization cost controls | MAIL-46–50 |
| 5 | Hardening | Encrypted credentials; Gmail push; desktop notifications; phone layout | MAIL-51–55 |

---

## 6. Cross-Cutting Concerns

### 6.1 Audit & Logging

Every queued provider action is a row in the action outbox with who, what, when, attempts, and final result; rows are retained ninety days. Sync runs continue to log to `sync_log` with per-account counts of additions, deletions, label changes, and actions pushed.

### 6.2 Permissions & Access Control

Mail actions on an account require the `owner` role on that provider account in `user_provider_accounts`; `shared` grants read and search only. Administrators may connect, disconnect, and configure any account but do not gain mail actions on accounts they do not own. Remote-image allow lists and notification settings are per user.

### 6.3 Error Handling

- A provider action that fails transiently is retried with exponential backoff up to `mail.action_retry_max`; the user interface shows a pending count. A permanent failure (for example a label deleted at the provider) is surfaced as a toast with "Retry" and "Discard", and the local state is reverted on discard.
- Expired or revoked credentials put the account in `error` with a "Reconnect" affordance; the mirror stays readable.
- Provider rate limiting pauses the account's sync and resumes after the provider's advised delay.
- An invalid cursor triggers the adapter's recovery path and a reconciliation pass; nothing is deleted locally on recovery.

### 6.4 Relationship to the Communication lifecycle

[communication-entity-base-prd.md] §4 defines `active`/`archived` as a CRM soft delete. Mail archive (removing the Inbox label) is a different concept and does not touch that status. Trashing at the provider sets the Communication to `archived` per the existing rule that provider deletion archives the record. See [mail-client-tdd.md] D-05.

---

## 7. Task List

```
Phase 0 — Close the ledger
- [x] MAIL-01: Commit the 2026-07-10 working-tree changes (CM-30/31/32, contact-view-prd.md, index V24.0) as a release after tests pass — v10.5 (ae941d6), 10-08-26
- [x] MAIL-02: ~~Re-authorize douglas.bower@scorevolunteer.org into the correct mailbox and reactivate it~~ — **moot 10-08-26**: the mailbox has been closed. Row left inactive; its 1,314 communications stay as history with their pre-v23 state stamped as final.
- [ ] MAIL-03: Rotate the Anthropic API key; remove the stray Google client secret from the parent folder
- [x] MAIL-04: Product owner approves mail-client-prd.md, email-provider-sync-prd.md, mail-client-tdd.md; PRD index updated — approved 10-08-26

Phase 1 — Mail store foundation
- [x] MAIL-05: Define the MailProvider interface (email-provider-sync-prd.md §3) and move gmail_client.py behind a GmailProvider — v10.6, 10-08-26 (`poc/providers/`; tests in `tests/test_providers.py`)
- [x] MAIL-06: Add gmail.modify to the requested scopes; re-authorization flow in Settings → Accounts with a clear "needs reconnect" state — v10.8, 10-08-26. Tokens are loaded with their own granted scopes so old accounts keep working read-only (TDD D-23); the accounts list reports `needs_reauth`/`missing_scopes`; "Reconnect" reuses the web connect flow, which now replaces the token of a known address and reactivates it instead of refusing a duplicate (TDD D-24). **Both live accounts show Needs reconnect until the owner reconnects them.**
- [x] MAIL-07: Schema v23 — header columns populated (Message-ID, In-Reply-To, References, Reply-To), bcc participants, recipient display names, is_starred, provider label ids; backfill from the provider for existing rows — v10.7, 10-08-26 (`poc/migrate_to_v23.py`, `poc/mail_state.py`; backfill is the `backfill-mail-state` command, **not yet run against the live database**)
- [x] MAIL-08: Schema v23 — mailbox_labels and communication_labels tables; system folder mapping per provider — v10.7, 10-08-26 (label list refreshed from the adapter before each orchestrated sync; placeholder rows typed from system ids)
- [x] MAIL-09: Schema v23 — mail_actions outbox table (action, target, payload, attempts, status, error) — shipped as **schema v24**, v10.12, 10-08-26 (`poc/migrate_to_v24.py`; v23 had already shipped without it)
- [x] MAIL-10: Incremental sync processes labelAdded/labelRemoved and flag changes; is_read mirrors the provider — v10.8, 10-08-26 (`mail_state.apply_label_delta`; TRASH arriving archives the Communication per §6.4; provider deletions now archive instead of hard-deleting, TDD D-22)
- [ ] MAIL-11: Resumable full-mailbox backfill job with checkpoint and batch size setting
- [x] MAIL-12: Schema v24 — communications_fts (FTS5) over subject, search_text, participant names and addresses; query parser for the §2.5 operators — shipped as **schema v25**, v10.14, 10-09-26 (`poc/mail_search.py`: index + triggers, `parse_query`, `build_sql`, `search`; `GET /mail/search?q=`; global search now reaches bodies and participants. Operators: from, to, cc, subject, has:attachment, in:<folder|label>, label, account, is:unread|read|starred|unstarred, before, after, newer_than, older_than, quoted phrases. Trash and spam hidden unless named. TDD D-28)
- [x] MAIL-13: Per-account background scheduler (interval setting, one run per account, global pause) — v10.13, 10-09-26 (`poc/scheduler.py`, started by the web server lifespan unless `CRM_SCHEDULER_ENABLED=false`; setting `mail_sync_interval_seconds`, floor 60, on Settings → System; `sync_enabled=false` stops timers but not Sync Now; `POST /sync/pause|resume` admin-only; `POST /settings/accounts/{id}/sync` per-account sync now; `GET /sync/status` carries a `scheduler` block. TDD D-27)
- [x] MAIL-14: Action outbox worker: ordered push per account, backoff, dead-letter, API to list and retry — v10.12, 10-08-26 (`poc/mail_actions.py`; routes in new `poc/web/routes/api_mail.py`: `POST /mail/actions`, `GET /mail/actions`, `POST /mail/actions/{id}/retry|discard`, `POST /mail/actions/push`; the worker also runs before each account's sync in `run_full_sync`. Until MAIL-13 there is no timer, so pushes happen on Sync Now or the push endpoint. Setting key is `mail_action_retry_max` (TDD D-26)
- [x] MAIL-15: Attachment metadata captured on sync; attachment fetch-on-demand with disk cache and cid: serving — v10.19, 10-09-26 (schema v26 adds `provider_attachment_id`, `content_id`, `is_inline`; `poc/mail_attachments.py` upserts parts at sync and on re-seen messages, fetches bytes through the adapter on first request into `data/attachments/` with least-recently-used pruning to `mail_attachment_cache_mb`; `GET /mail/attachments/{id}[?download=1]` and `GET /mail/attachments/cid/{message}/{cid}`; HTML/SVG/JS attachments always download. **Messages stored before v10.19 have no attachment rows**; a full-fetch backfill is deferred, see TDD D-32)
- [x] MAIL-16: Mail API: folders with counts, thread list per folder/account/unified, thread detail, actions, search, per-account sync and status — v10.15, 10-09-26 (`poc/mail_threads.py`; `GET /mail/folders`, `GET /mail/threads?folder|label_id&account_id&q`, `GET /mail/threads/{account}/{thread}`; actions MAIL-14, search MAIL-12, per-account sync MAIL-13. Counts computed locally; folder and search share one predicate builder. Snoozed folder is empty until MAIL-17; Drafts shows provider drafts until MAIL-35. TDD D-29)
- [ ] MAIL-17: Snooze: local return-time table, provider label CRMExtender/Snoozed, scheduler return pass
- [ ] MAIL-18: Drop the duplicate HTML copy (cleaned_html == original_html) during v23 migration; store one body plus derived text
- [x] MAIL-19: Summarization trigger changed from per-message to per-thread settle window (cost control) — v10.11, 10-08-26. Settle window (`summarize_settle_minutes`, default 15) and per-run cap (`summarize_max_per_sync`, default 500, newest first) in Settings → System; summarization runs once after all accounts have synced instead of inside the account loop (TDD D-25)
- [ ] MAIL-20: Tests for MAIL-05–19 (see §8)

Phase 2 — Mail surface
- [x] MAIL-21: /app/mail route, rail icon with unread badge, URL forms /app/mail/{account|unified}/{folder}[/{thread}] — v10.16, 10-09-26 (`stores/navigation.ts` mail state, `lib/appRoutes.ts` mail paths, `hooks/useUrlSync.ts`, `components/mail/MailView.tsx`, rail Inbox icon with unified-inbox unread badge refreshed each minute. TDD D-30)
- [x] MAIL-22: Folder tree with unified set, per-account sections, unread counts, sync status per account — v10.16 (`components/mail/FolderTree.tsx`: unified Inbox/Starred/Snoozed/Drafts/Sent, per account Inbox/Starred/Sent/Drafts/Archive/Spam/Trash plus user labels, counts from `/mail/folders`, spinner while an account syncs and a warning mark on its last error)
- [x] MAIL-23: Thread list in email rows with virtualization, selection model, account chips, attachment and star indicators — v10.17, 10-09-26 (`components/mail/ThreadList.tsx`: virtualized rows, offset paging as the user nears the end, selection with checkbox / `x` / Shift-click ranges / Ctrl+A, `j` `k` `Enter` `o` movement, unread weight, account chip in the unified view, star and attachment marks; selection is keyed by folder so changing folder clears it) **10-09-26, v10.27:** the list and the reading pane are split by a draggable bar (list 22–75 % of the width, default 38 %), remembered per browser. **v10.28:** each account can be given a label colour on Settings → Accounts (nine presets or a custom colour); the account chip on each row and the account heading in the folder tree take that colour.
- [x] MAIL-24: Reading pane with collapsed older messages, expand/collapse, quoted-text collapse — v10.17, 10-09-26 (`components/mail/ReadingPane.tsx`: unread messages and the last one expanded, others collapsed to sender/snippet/date lines, click or `Shift+O` to expand, quoted text folded behind a `· · ·` toggle using the splitter shared with the Communication view, `lib/emailZones.ts`). Per-message reply arrives with MAIL-33
- [x] MAIL-25: Isolated message rendering: DOMPurify + sandboxed iframe + content security policy; remote-image blocking with per-sender allow list — v10.18, 10-09-26 (`lib/mailRender.ts`, `components/mail/MessageFrame.tsx`: DOMPurify profile forbidding forms/frames/meta, remote `img` and CSS `url()` neutralized until "Load images" or "Always from this sender", srcdoc with a strict CSP in an `allow-scripts`-only sandbox (opaque origin), height and link clicks relayed by postMessage, links open in a new tab. The allow list is per browser (localStorage) in V1; a per-user server setting is deferred. TDD D-31)
- [x] MAIL-26: Attachment preview (image, PDF) and download — v10.19, 10-09-26 (chips in the reading pane open images, PDFs, and text in a new tab and download everything else; a download button on every chip; inline `cid:` images render inside the message frame; inline parts are kept out of the chip row)
- [x] MAIL-27: Actions wired to the outbox API with optimistic updates and pending/failed indicators — v10.19, 10-09-26 (`components/mail/ActionBar.tsx` over the thread list: archive, trash, spam, star/unstar, mark read/unread for the selection or the open thread; opening a thread marks it read after `mail_mark_read_dwell_ms` (new system setting, default 1500, 0 disables); the bar shows pending and failed queue counts, with retry and discard-and-revert for failed rows. Keyboard bindings for these arrive with MAIL-30)
- [ ] MAIL-28: Snooze picker and Snoozed folder
- [ ] MAIL-29: Label/move picker with label creation
- [x] MAIL-30: Keyboard model (§5.1) via react-hotkeys-hook; shortcut sheet on ? — v10.20, 10-09-26 (`hooks/useMailShortcuts.ts`, `components/mail/ShortcutSheet.tsx`: j/k/Enter/o/x/Esc, e/#/!/s/u, r/a/f/c, g-then-i/s/t/d/Shift+A, 0–9 account switch, ? sheet; inert bindings z, l/v, / show a note until MAIL-17/29/31. Actions now target whole threads: `POST /mail/actions` accepts `threads` and expands to every message server-side, closing the D-33 gap)
- [x] MAIL-31: Mail search box with operator highlighting, results list, saved searches — v10.22, 10-09-26 (`components/mail/SearchBox.tsx`, `lib/mailSearchUi.ts`: `/` focuses, Enter runs, Esc clears, operator chips as hints, highlighted operator tokens, results in the same thread list narrowed to the current folder (an `in:` in the query overrides the folder); saved searches are per browser in V1, not folder-tree views. TDD D-36)
- [x] MAIL-32: Relationship context column (contact, company, score, last interaction, tasks, summary; create-contact affordance) — v10.23, 10-09-26 (`components/mail/ContextColumn.tsx`, `lib/mailParticipants.ts`: the thread's CRM conversation title, status, and summary on top; one card per external participant (senders first, up to three) with name, title, company, relationship score, two most recent conversations with summaries, and an Open contact link; unknown senders get Create contact, which opens the existing contact modal without prefill. Tasks are omitted: the PoC has no task entity yet. TDD D-37)
- [x] MAIL-33: Inline reply/reply-all/forward composer at thread bottom — v10.24, 10-09-26 (`components/compose/InlineReply.tsx` at the end of the reading pane: Reply / Reply all / Forward row, or the composer for that thread; each expanded message has its own Reply / Reply all / Forward; `r` / `a` / `f` open inline for the last message. One inline composer per thread; leaving the thread shows it as a tab in the dock, reopening the thread brings it back. TDD D-38)
- [x] MAIL-34: Docked, minimizable compose (up to three) replacing the modal — v10.24, 10-09-26 (`components/compose/ComposeDock.tsx` bottom-right; each composer minimizes to a title tab; a fourth is refused with a message. The centered modal is removed; the Compose button, the Communication view's reply buttons, and `c` all open a docked composer. `Esc` in a docked composer minimizes it; `Ctrl+Enter` sends. Shared form in `ComposeForm.tsx`. TDD D-38)
- [x] MAIL-35: Compose: attachment upload, signature insertion, drafts folder and resume, undo-send, scheduled send — v10.24, 10-09-26 (attachments by picker or drag-and-drop, stored under `data/uploads/outbound/<draft>/` and sent as MIME parts: `GET/POST/DELETE /outbound-emails/{id}/attachments`; the account's default signature shown under the editor and added on send; Drafts folder lists drafts written here above the provider's drafts, click to resume, trash to delete; Send holds the message for `mail_undo_send_seconds` (default 10) as `queued` with an Undo bar, and the scheduler sends queued mail whose time has passed; Schedule send offers quick slots or a date-time; `POST /outbound-emails/{id}/send` takes `undo`, `delay_seconds` or `scheduled_send_at`, `POST /outbound-emails/{id}/undo` returns it to draft. TDD D-38)
- [x] MAIL-36: Sent folder populated immediately on send; reconciliation on sync — v10.24, 10-09-26 (the composed Communication is labelled SENT, marked read, and given the provider's thread id as soon as the adapter returns; the next sync matches the provider's copy by provider message id, as before)
- [x] MAIL-37: Live updates: polling of folder counts and current list; then server-sent events from the scheduler — v10.25, 10-09-26 (polling of folder counts, the open list, and the open thread every 30 s was in place since MAIL-21/23; `GET /mail/events` now streams `sync.started`, `sync.finished`, `post_pass.finished`, `outbound.sent` from `poc/events.py`, published by the scheduler's workers; `hooks/useMailEvents.ts` refreshes every mail query when a sync or post pass finishes or a queued message goes out, and the folder tree shows Live / Polling with the last event time and a spinner per account while it syncs. Polling stays as the fallback. TDD D-39)
- [x] MAIL-38: Accounts settings: per-account sync now, reconnect, disconnect (keep or delete), error badge, sync interval — v10.26, 10-09-26 (`components/settings/AccountsSettings.tsx`: per-row state — Active / Inactive / Needs reconnect / Sync error / Disconnected — with last sync, next due, and Sync now; Reconnect; Disconnect with an in-page choice between keeping the mail as history and deleting the account with its mail (`DELETE /settings/accounts/{id}?mode=keep|delete`, owner or administrator); administrators set the sync interval on the same page. Schema v27 (`poc/migrate_to_v27.py`, live database migrated 10-09-26 10:00): `provider_accounts.auth_status`, `auth_error`, `last_sync_error`, `last_sync_error_at`. **The §9.1 rule is in:** `create_app` puts `auth` in non-interactive mode, a missing or unrefreshable token raises `ReauthRequired`, the sync and the sender mark the account `needs_reauth`, the scheduler skips it, and the web reconnect clears it. TDD D-40)
- [x] MAIL-39: In-application notifications for new inbox mail per mail.notifications — v10.26, 10-09-26 (after each account run the scheduler publishes one `mail.new` event with the unread inbound inbox messages stored during the run — at most ten listed, with the count — each flagged `known_contact`; a first sync publishes nothing. `poc/mail_notify.py`. The browser shows a pop-up per message up to three, then one summary, each with an Open link to the thread, under the per-user, per-account setting `mail_notifications:<account>` — All inbox mail / Known contacts only / None, default Known contacts — set in the Notify column of Settings → Accounts (`PUT /settings/accounts/{id}/notifications`). The rail badge refreshes from the same event. Desktop notifications stay MAIL-53. TDD D-41)
- [x] MAIL-40: Frontend test harness (Vitest + Testing Library) with tests for list, reading pane, actions, keyboard; one Playwright smoke test — v10.21, 10-09-26 (`npm test` = Vitest in jsdom, `src/test/setup.ts` + `src/test/utils.tsx`; 19 tests: sanitizer and frame document, mail routes and quote splitter, thread list rows/keys/selection, keyboard bindings and g-chords, reading pane collapse/expand/attachments and mark-read dwell; CI runs `npm test` after lint. **The Playwright smoke test is deferred**: the owner's machine is the only place the app can be driven end to end tonight)

Phase 3 — Every account
- [x] MAIL-41: Product owner supplies the account inventory (provider per address) — 10-08-26, four Google Workspace accounts, table in §9.2
- [ ] MAIL-42: Microsoft Graph provider (OAuth, delta queries, folders, flags, send) — DEFERRED until a non-Google account is added (§9.2)
- [ ] MAIL-43: IMAP/SMTP provider (IDLE or polling, folders, flags, UIDVALIDITY handling, SMTP send) with provider detection by domain — DEFERRED until a non-Google account is added (§9.2)
- [ ] MAIL-41a: Connect doug.bower@cbmentors.org and dwb80@case.edu (after MAIL-06, so they are authorized with the modify scope once)
- [ ] MAIL-44: Cross-account duplicate detection (same Message-ID in two accounts) with a single thread presentation
- [ ] MAIL-45: Tests per provider against recorded fixtures

Phase 4 — CRM-only intelligence
- [ ] MAIL-46: Priority inbox: rule layer (known contact, direct address, owner replied) then AI classifier with per-sync token budget
- [ ] MAIL-47: Awaiting-reply tracking from sent mail without an answer; reminder list and nudge action
- [ ] MAIL-48: AI reply draft from conversation summary and thread, inserted into the composer for review
- [ ] MAIL-49: Batch API use for backfill summarization; token accounting visible in Settings → System
- [ ] MAIL-50: Tests for MAIL-46–49

Phase 5 — Hardening
- [ ] MAIL-51: Encrypted credential storage replacing token files
- [ ] MAIL-52: Gmail push (watch + Pub/Sub) replacing polling for Gmail accounts
- [ ] MAIL-53: Desktop notifications via the browser Notification API
- [ ] MAIL-54: Phone-width layout for list and reading pane
- [ ] MAIL-55: Split poc/web/routes/api.py so mail routes live in their own module from the start
```

---

## 8. Test Plan

| Test ID | Description | Type | Covers |
|---|---|---|---|
| MAIL-T01 | Full test suite green before the Phase 0 commit | regression | MAIL-01 |
| MAIL-T02 | GmailProvider satisfies the MailProvider interface; sync.py has no direct gmail_client import | unit | MAIL-05 |
| MAIL-T03 | v23 migration populates headers, labels, flags for existing rows from fixture messages; idempotent | migration | MAIL-07, MAIL-08 |
| MAIL-T04 | Incremental sync applies labelAdded/labelRemoved and read/star flag changes from a recorded history fixture | unit | MAIL-10 |
| MAIL-T05 | Backfill resumes from checkpoint after interruption; no duplicates | unit | MAIL-11 |
| MAIL-T06 | FTS query parser maps every §2.5 operator to the expected SQL; free text matches body | unit | MAIL-12 |
| MAIL-T07 | Scheduler runs one sync per account, never two concurrently, honors pause | unit | MAIL-13 |
| MAIL-T08 | Outbox pushes in order, retries with backoff, dead-letters after max attempts, retry endpoint re-queues | unit | MAIL-14 |
| MAIL-T09 | Attachment fetch caches on first request and serves from cache on second; cid: resolves | unit | MAIL-15 |
| MAIL-T10 | Mail API: unified inbox merges accounts; folder counts match rows; actions create outbox rows; non-owner gets 403 on actions | api | MAIL-16, §6.2 |
| MAIL-T11 | Snooze hides, labels at provider, returns unread at due time | unit | MAIL-17 |
| MAIL-T12 | Reply to a synced message carries In-Reply-To and References from stored headers | unit | MAIL-07, MAIL-33 |
| MAIL-T13 | Mail archive leaves Communication status `active`; provider trash sets `archived` | unit | §6.4 |
| MAIL-T14 | Thread list renders rows, unread weight, account chips; j/k moves selection; e archives optimistically and shows pending | frontend | MAIL-23, MAIL-27, MAIL-30 |
| MAIL-T15 | Message iframe blocks remote images by default; Load images loads them; sanitizer strips scripts and event handlers | frontend | MAIL-25 |
| MAIL-T16 | Inline reply composer opens addressed correctly for reply, reply-all, forward; signature inserted | frontend | MAIL-33, MAIL-35 |
| MAIL-T17 | Undo-send within the window cancels and reopens the composer | frontend | MAIL-35 |
| MAIL-T18 | Playwright smoke: open Mail, select thread, archive, search, compose and discard, against a copied database | end-to-end | MAIL-40 |
| MAIL-T19 | Microsoft Graph provider passes the same contract tests as Gmail from recorded fixtures | unit | MAIL-42 |
| MAIL-T20 | IMAP provider handles UIDVALIDITY change by re-sync without data loss | unit | MAIL-43 |
| MAIL-T21 | Same Message-ID in two accounts shows as one thread with both account chips | unit | MAIL-44 |
| MAIL-T22 | Priority classifier stays within the token budget per sync and degrades to rules when exhausted | unit | MAIL-46 |

---

## 9. Open Questions

1. ~~**Google OAuth client publishing status.**~~ **Resolved 10-08-26.** The client (project `strong-land-268114`, desktop-application type) is **Testing** / **External**, with the four inventory addresses as test users (4 of the 100-user lifetime cap). Decision: **stay in Testing.** Publishing to production with `gmail.modify` (a restricted scope) requires Google verification plus a third-party security assessment, out of proportion for a single-owner tool; switching the user type to Internal would admit only dougbower.com Workspace users and lock out cbmentors.org and case.edu. Cost accepted: the unverified-app interstitial on every connect, and Google's documented seven-day refresh-token expiry for External Testing clients. Empirically that expiry has not applied here: the SCORE token issued 2026-02-26 synced until 2026-07-07 without re-authorization. If it ever does apply, the symptom is a token refresh failure; MAIL-38 must surface that as a Needs reconnect state rather than let `get_credentials_for_account` fall into its interactive browser flow inside the web server.
2. ~~**Account inventory.**~~ **Resolved 10-08-26** (MAIL-41). All four accounts are Google Workspace mailboxes, so no non-Google adapter is needed until a new account appears. Provider identification by mail exchanger lookup on 10-08-26, except case.edu, which sits behind a university gateway and was confirmed by the owner as read in Gmail.

   | Address | Provider | Role | Unified inbox | Size |
   |---|---|---|---|---|
   | doug@dougbower.com | Google Workspace (own domain) | primary | yes | 11 years; 4,484 rows in the 90-day mirror |
   | douglas.bower@scorevolunteer.org | Google Workspace | **closed** (mailbox shut down, owner 10-08-26) | no | 1,314 rows kept as history; row inactive; no reconnect possible |
   | doug.bower@cbmentors.org | Google Workspace | secondary | yes | ~200 messages |
   | dwb80@case.edu | Google Workspace for Education (university tenant) | secondary | yes | ~100 messages; the tenant may block third-party OAuth sign-in, to be found out at connect time |

   Consequence: Phase 3's Microsoft Graph and IMAP/SMTP adapters (MAIL-42, MAIL-43) are deferred until a non-Google account is added; MAIL-44 (cross-account duplicates) and MAIL-45 stay, and connecting the two new accounts becomes the Phase 3 work.
3. **Permanent deletion.** Not offered in V1; decide whether Trash emptying is needed.
4. **Shared accounts.** Mail actions on `shared` accounts are read-only in V1; revisit if a shared inbox is connected.

---

## 10. Change Log

| Rev | Date (MM-DD-YY HH:MM) | Author | Change |
|---|---|---|---|
| 1.29 | 10-09-26 12:57 | Claude (Claude Code) | v10.32: the shell's record preview panel collapses in mail mode (it showed an empty "Select a record to preview" column beside the reading pane); its empty state gains a close button. |
| 1.28 | 10-09-26 12:43 | Claude (Claude Code) | v10.31: provider drafts are kept out of conversations and deleted when the provider drops them (TDD D-42); one-time cleanup run on the live database. |
| 1.27 | 10-09-26 11:23 | Claude (Claude Code) | v10.28: per-account label colour (schema v28, live-migrated) on the account chip in the unified list and the folder tree; picker on Settings → Accounts (owner's request, 10-09-26). |
| 1.26 | 10-09-26 11:20 | Claude (Claude Code) | v10.27: draggable splitter between the message list and the reading pane, width remembered per browser (owner's request on first look, 10-09-26). |
| 1.25 | 10-09-26 10:07 | Claude (Claude Code) | MAIL-39 checked off (v10.26, same release as MAIL-38): new-mail pop-ups per account setting. |
| 1.24 | 10-09-26 10:06 | Claude (Claude Code) | MAIL-38 checked off (v10.26): accounts page, needs_reauth on refresh failure, disconnect keep/delete, schema v27. |
| 1.23 | 10-09-26 09:58 | Claude (Claude Code) | MAIL-37 checked off (v10.25): server-sent events from the scheduler. |
| 1.22 | 10-09-26 09:50 | Claude (Claude Code) | MAIL-33, 34, 35, 36 checked off (v10.24): inline reply, docked composers, attachments, signature, local drafts, undo and scheduled send, immediate Sent. |
| 1.21 | 10-09-26 02:30 | Claude (Claude Code) | MAIL-32 checked off (v10.23). |
| 1.20 | 10-09-26 02:25 | Claude (Claude Code) | MAIL-31 checked off (v10.22). |
| 1.19 | 10-09-26 02:20 | Claude (Claude Code) | MAIL-40 checked off (v10.21), Playwright smoke deferred. |
| 1.18 | 10-09-26 02:15 | Claude (Claude Code) | MAIL-30 checked off (v10.20); thread-level action targets. |
| 1.17 | 10-09-26 01:05 | Claude (Claude Code) | MAIL-27 checked off (v10.19); `mail_mark_read_dwell_ms` added as the shipped key for §3.1 `mail.mark_read_dwell_ms`. |
| 1.16 | 10-09-26 01:00 | Claude (Claude Code) | MAIL-15 and MAIL-26 checked off (v10.19). |
| 1.15 | 10-09-26 00:50 | Claude (Claude Code) | MAIL-25 checked off (v10.18). |
| 1.14 | 10-09-26 00:45 | Claude (Claude Code) | MAIL-23 and MAIL-24 checked off (v10.17). |
| 1.13 | 10-09-26 00:30 | Claude (Claude Code) | Phase 2 begins: MAIL-21 and MAIL-22 checked off, MAIL-23 and MAIL-24 first cuts noted (v10.16). |
| 1.12 | 10-09-26 00:20 | Claude (Claude Code) | MAIL-16 checked off (v10.15); Phase 1 backend now complete except MAIL-11, MAIL-15, MAIL-17, MAIL-18, MAIL-20. |
| 1.11 | 10-09-26 00:15 | Claude (Claude Code) | MAIL-12 checked off (v10.14). |
| 1.10 | 10-09-26 00:05 | Claude (Claude Code) | MAIL-13 checked off (v10.13); interval setting key noted in §3.1. |
| 1.9 | 10-08-26 23:55 | Claude (Claude Code) | MAIL-09 and MAIL-14 checked off (v10.12). |
| 1.8 | 10-08-26 23:40 | Claude (Claude Code) | MAIL-19 checked off (v10.11); two summarization settings added to §3.1. |
| 1.7 | 10-08-26 22:52 | Claude (Claude Code) | §9.1 resolved: OAuth client stays in Testing/External; MAIL-38 gains the refresh-failure rule. |
| 1.6 | 10-08-26 22:20 | Claude (Claude Code) | SCORE mailbox closed: inventory row marked closed, MAIL-02 moot. Web-connected accounts now take the tenant history window as their initial-sync query (v10.9). |
| 1.5 | 10-08-26 22:10 | Claude (Claude Code) | MAIL-10 and MAIL-06 checked off (v10.8). |
| 1.4 | 10-08-26 21:45 | Claude (Claude Code) | Account inventory recorded (§9.2); MAIL-41 closed; MAIL-42/43 deferred; MAIL-41a added; Phase 3 scope restated. |
| 1.3 | 10-08-26 13:40 | Claude (Claude Code) | MAIL-07 and MAIL-08 checked off (v10.7). |
| 1.2 | 10-08-26 13:05 | Claude (Claude Code) | MAIL-05 checked off (v10.6). |
| 1.1 | 10-08-26 12:33 | Claude (Claude Code) | Status set to Approved on the product owner's approval; MAIL-01 and MAIL-04 checked off. |
| 1.0 | 10-08-26 01:30 | Claude (Claude Code) | Initial draft for approval, from the 10-08-26 project review and the owner's choice of the local-mirror architecture. |
