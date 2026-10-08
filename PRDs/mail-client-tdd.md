# Mail Client — TDD

**Version:** 1.0
**Last Updated:** 10-08-26 13:05
**Status:** Approved 10-08-26 by the product owner — living document; D-01–D-14 are binding until revised here
**Scope:** Functional Area
**Parent Document:** [mail-client-prd.md]
**Product TDD:** [product-tdd.md]

---

## 1. Overview

Technical decisions for the Mail Client functional area and its child [email-provider-sync-prd.md] that are not covered by the Product TDD. This is a living document: decisions are recorded as they are made, by the product owner and by Claude Code during implementation.

---

## 2. Architecture

### D-01 Local mirror with write-back

**Decision:** CRMExtender stores a complete local copy of every connected mailbox (all folders, labels, flags, headers, attachment metadata) and pushes every user action back to the provider through a queued outbox. All reading, listing, counting, and searching is served from the local store.

**Rationale:** The conversation, participant, and identity layers already require local copies of mail. A mirror adds mailbox state to records the system already stores. A thin client would add a second architecture (live provider queries) beside the first and make a unified inbox a fan-out of remote calls.

**Alternatives Rejected:**
- Thin client over provider APIs — every list and search round-trips; IMAP providers make it slow; offline impossible; two code paths.
- Hybrid (mirror headers, fetch bodies live) — bodies are already stored for the pipeline; the saving is small and the complexity is not.

**Constraints/Tradeoffs:** A real sync engine (label and flag deltas, deletions, recovery), larger storage, the `gmail.modify` scope and re-authorization of every account, and a reconciliation path for mirror drift.

**Decided by:** product owner, 10-08-26.

### D-02 Mailbox state on the existing Communication row

**Decision:** Flags (`is_read`, new `is_starred`) and the RFC header columns stay on `communications`. No separate "message" table.

**Rationale:** The Communication record is the system object the rest of the product references; a parallel table would duplicate identity and force joins in every view.

**Alternatives Rejected:** A `mail_messages` table keyed to communications — cleaner separation, but every grid, conversation, and search path would need the join.

### D-03 Labels as two tables

**Decision:** `mailbox_labels` (per account: provider label id, name, kind ∈ {inbox, sent, drafts, spam, trash, archive, starred, snoozed, user, category}, parent, unread and total counts) and `communication_labels` (communication id, label id). Folder-based providers map a message's folder to exactly one `communication_labels` row of kind user or system.

**Rationale:** One model serves both label providers (Gmail) and folder providers (Graph, IMAP). Counts live on the label row and are maintained by the sync engine and outbox, so the folder tree never counts rows on render ([product-tdd.md] §11.1, display speed).

**Constraints/Tradeoffs:** Counts can drift; a nightly recount reconciles them.

### D-04 Action outbox

**Decision:** `mail_actions` (id, account id, action, target ids JSON, payload JSON, created by, created at, attempts, next attempt at, status ∈ {pending, pushed, failed, gone}, error). A worker per account pushes in creation order. Local state changes at enqueue time (optimistic); on `failed` the user chooses retry or discard, and discard reverts the local change.

**Rationale:** Users expect instant response; providers are slow and sometimes down. The outbox also gives an audit trail and echo suppression for the next incremental delta.

**Alternatives Rejected:** Synchronous push on every action — a 400 ms round trip per keystroke defeats "ten emails in ten keystrokes".

### D-05 Mail archive versus Communication archive

**Decision:** Mail archive removes the inbox label only. The Communication's `is_archived` (CRM soft delete) changes only when the provider deletes or trashes the message.

**Rationale:** The two words collide but mean different things; conflating them would make archiving an inbox hide the message from conversations.

### D-06 Full-text search with SQLite FTS5

**Decision:** `communications_fts` (external-content FTS5 over `subject`, `search_text`, and a participants text column), with triggers keeping it current. A query parser turns the operators in [mail-client-prd.md] §2.5 into a `MATCH` plus structured `WHERE` clauses on labels, flags, account, and dates.

**Rationale:** FTS5 is already in use for notes; it meets the half-second target at the production profile. Server-side provider search is deferred (capability flag reserved).

**Constraints/Tradeoffs:** The PostgreSQL target ([product-tdd.md] §3.1) will need `tsvector`; the query parser's output is kept behind one function so only the storage layer changes.

### D-07 Scheduler in-process, one worker per account

**Decision:** A scheduler thread inside the FastAPI process ticks every `mail.sync_interval_seconds` and dispatches one sync per active account, never two for the same account, replacing the single global sync slot. "Sync now" enqueues an immediate tick for one account.

**Rationale:** The deployment is one container; an external job runner would add infrastructure for a single-user system. Per-account workers stop one slow account from blocking the others.

**Alternatives Rejected:** Celery or APScheduler with a broker — more moving parts than the deployment warrants now. Gmail push — Phase 5, needs a public endpoint.

### D-08 Message rendering isolation

**Decision:** Bodies are sanitized with DOMPurify (replacing the regex sanitizer) and rendered inside a sandboxed `<iframe>` with `sandbox="allow-same-origin"` omitted (opaque origin), a `Content-Security-Policy` of `default-src 'none'; img-src data: blob: <app-origin>; style-src 'unsafe-inline'`, and remote image URLs rewritten to a placeholder until the user loads them. Inline `cid:` images are served from the attachment cache under the application origin.

**Rationale:** The current sanitizer and direct injection are documented as "not a complete security boundary" ([communications-view-tdd.md] §4.1). An all-accounts client reads mail from strangers; mail CSS must not leak into the shell.

**Constraints/Tradeoffs:** Iframe height must be measured and set; link clicks are intercepted and opened in a new tab.

### D-09 Attachment cache

**Decision:** Attachment bytes are fetched on first request and cached on disk under `data/attachments/{account}/{message}/{part}` with a least-recently-used eviction at `mail.attachment_cache_mb`. Outbound attachments are Documents and are read from Document storage.

**Rationale:** Storing every attachment up front would multiply the mirror's size; most are never opened.

### D-10 Drop the duplicate HTML copy

**Decision:** During the v23 migration, `cleaned_html` rows equal to `original_html` are set NULL, and the view layer falls back to `original_html` when `cleaned_html` is NULL.

**Rationale:** The production database is 510 MB for 5,798 messages largely because HTML is stored twice. A full mirror of several mailboxes cannot afford that.

### D-11 Live updates

**Decision:** Phase 2 uses TanStack Query polling of folder counts and the open list every 30 seconds while the Mail surface is visible. A server-sent events endpoint fed by the scheduler replaces polling once stable.

**Rationale:** Polling ships in a day; server-sent events need connection management in the shell and are better added once the data shape is settled.

### D-12 Snooze as a provider-visible label

**Decision:** Snooze archives the thread and applies a `CRMExtender/Snoozed` label (or folder) at the provider; the return time lives locally in `mail_snoozes`. The scheduler returns due threads.

**Rationale:** Other clients see the state; nothing is lost if CRMExtender is down past the due time — the thread returns on the next tick.

### D-13 Frontend test harness

**Decision:** Vitest with Testing Library for component tests, introduced with the first Mail components; one Playwright smoke test against a copied database. The CI frontend job adds `npm test`.

**Rationale:** The frontend has zero tests today; a mail client with keyboard-driven actions and optimistic updates is where that becomes unsafe.

### D-14 Scopes and re-authorization

**Decision:** `gmail.readonly` is replaced by `gmail.modify` in the requested scopes. Accounts whose stored token lacks the scope are marked `needs_reauth` at startup and shown with a Reconnect affordance; sync continues read-only until reconnected.

**Rationale:** Write-back needs modify; a forced re-auth at startup would block the user.

---

### D-15 The normalized message type is `ParsedEmail`, extended

**Decision:** The provider contract's message type (`MailMessage` in `poc/providers/base.py`) is the existing `poc.models.ParsedEmail` dataclass, extended with defaulted fields for Bcc, Reply-To, participant display names, the RFC header ids, provider label ids, read and starred flags, and attachment metadata. No separate `RawMessage` class.

**Rationale:** Every pipeline stage (`_store_thread`, conversation formation, participant rows, tests) already consumes `ParsedEmail`. Adding fields with defaults changes nothing downstream today and gives MAIL-07 the data it needs to store. A second type would have forced a conversion at the adapter boundary and a rewrite of the storage path in the same change as the interface.

**Alternatives Rejected:** A new `RawMessage` plus `normalize()` step — cleaner naming, but doubles the types the engine touches for no behavioral gain.

**Decided by:** Claude Code, 10-08-26 (MAIL-05).

### D-16 `fetch_initial` returns threads, not messages

**Decision:** `fetch_initial` returns `(threads, next_page_token)` where each thread is a date-ascending list of messages, matching what `_store_thread` consumes. `fetch_backfill` and `fetch_messages` return flat message lists.

**Rationale:** Conversation formation is thread-driven; the engine's initial and recovery paths already loop over threads. The sub-PRD's §3.1 sketch shows a flat list; the signature in `base.py` is authoritative.

**Decided by:** Claude Code, 10-08-26 (MAIL-05).

### D-17 Incremental cursor is the position the delta was fetched at

**Decision:** `fetch_incremental` returns the provider's cursor as read at fetch time, and the engine stores that value after processing. The previous code read a fresh history id after processing, which could skip changes that arrived while the run was storing messages.

**Rationale:** A cursor must never move past changes that have not been applied. Reading it before processing makes an in-flight change show up in the next delta instead of being lost. The cost is that the next run re-sees messages this run already stored; the provider-message-id upsert absorbs that.

**Decided by:** Claude Code, 10-08-26 (MAIL-05).

### D-18 Adapters call the HTTP client through the module object

**Decision:** `GmailProvider` calls `gmail_client.<function>` via the imported module, never `from gmail_client import <function>`.

**Rationale:** Existing tests patch `poc.gmail_client.<function>`; module-attribute calls keep those patches effective. The HTTP layer stays in one file that owns rate limiting and error mapping.

**Decided by:** Claude Code, 10-08-26 (MAIL-05).

---

## 3. Decisions to Be Added by Claude Code

- **Thread model:** whether the mail surface groups by provider thread id or by RFC References chain; the two disagree on Gmail occasionally. Decide once the backfill data is in.
- **Unified inbox ordering across accounts:** last-activity time versus newest-message time, and how to break ties.
- **Outbox batching:** batch size per provider and whether to coalesce opposite actions (star then unstar) before push.
- **IMAP connection lifecycle:** persistent IDLE versus polling per folder, decided when a real IMAP account is available.
- **Server-sent events transport:** endpoint shape, reconnection, and whether the scheduler publishes per-account or per-user events.
- **Token encryption at rest (Phase 5):** key management for a single-container deployment.
- **PostgreSQL FTS migration path:** when the storage move happens.

---

## 4. Change Log

| Rev | Date (MM-DD-YY HH:MM) | Author | Change |
|---|---|---|---|
| 1.2 | 10-08-26 13:05 | Claude (Claude Code) | Implementation write-back for MAIL-05: D-15 (`ParsedEmail` as the contract type), D-16 (thread-grouped `fetch_initial`), D-17 (cursor read at fetch time), D-18 (module-object calls). |
| 1.1 | 10-08-26 12:33 | Claude (Claude Code) | Status set to Approved on the product owner's approval; D-02–D-14 now binding. |
| 1.0 | 10-08-26 01:30 | Claude (Claude Code) | Initial draft. D-01 records the product owner's architecture choice; D-02–D-14 are proposals for approval. |
