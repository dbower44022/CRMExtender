# Mail Client — TDD

**Version:** 1.0
**Last Updated:** 10-09-26 00:30
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

### D-19 Provider state is authoritative on re-seen messages

**Decision:** When the sync store meets a message it already holds (backfill overlap, re-fetch, or a CRM-composed message now arriving from the provider), it rewrites the row's flags, header ids, label membership, and participant display names from the provider copy, and never touches the stored bodies. `mail_state_synced_at` records when that last happened.

**Rationale:** A mirror has one source of truth for mailbox state. Keeping the first-seen flags would make the local inbox diverge from the provider until MAIL-10's delta handling lands, and bodies are the one thing the provider will not change.

**Decided by:** Claude Code, 10-08-26 (MAIL-07).

### D-20 Flag labels are columns, membership labels are rows

**Decision:** Gmail's `UNREAD` and `STARRED` labels map to `is_read` and `is_starred` columns and never get `communication_labels` rows. Every other label (system, category, user) is a membership row against `mailbox_labels`.

**Rationale:** Read and starred state are per-message flags on every provider, queried on every list; a column is the natural index. Treating them as labels would make "unread count" a join.

**Decided by:** Claude Code, 10-08-26 (MAIL-08).

### D-21 Pre-v23 rows are backfilled by a command, not the migration

**Decision:** The v23 migration adds columns and tables only. A separate `backfill-mail-state` command fetches metadata-only copies in batches and is resumable on `mail_state_synced_at IS NULL`; rows the provider no longer has are stamped so they are not retried.

**Rationale:** A migration must not depend on the network or on valid credentials. At the Gmail rate limit the 5,798 live rows take roughly twenty minutes, which belongs in a progress-reporting command the owner runs when ready.

**Decided by:** Claude Code, 10-08-26 (MAIL-07).

### D-22 Provider deletion archives; it never deletes the local row

**Decision:** A `messageDeleted` history record (or any provider signal that a message is gone for good) sets the Communication to `archived` and clears its label membership. The row, its participants, and its conversation links stay. Before 10-08-26 the engine hard-deleted the row.

**Rationale:** [communication-entity-base-prd.md] §4.1 defines provider deletion as an archive transition, and conversations must not lose messages because the owner emptied Gmail's trash. The 268 rows found missing during the v23 backfill are exactly this case and were preserved.

**Decided by:** Claude Code, 10-08-26 (MAIL-10).

### D-23 Saved tokens are loaded with their granted scopes, not the requested set

**Decision:** `get_credentials_for_account` loads a token file without passing `config.GOOGLE_SCOPES`, so the credential carries the scopes Google granted at consent. `auth.missing_scopes()` compares those against the current request set, and the accounts API reports `needs_reauth` and `missing_scopes`.

**Rationale:** google-auth refuses to refresh a token when the requested scopes exceed the granted ones. Loading with the new set would have turned the scope upgrade into an immediate refresh failure for every existing account and, in this code path, a browser-launching re-authorization from inside the web server. Loading with the granted set keeps old accounts working read-only until the owner reconnects at a time of their choosing.

**Alternatives Rejected:** Forcing re-authorization at startup — blocks sync for every account at once and cannot run headless.

**Decided by:** Claude Code, 10-08-26 (MAIL-06).

### D-24 Reconnect is the connect flow applied to a known address

**Decision:** The web OAuth callback no longer refuses an address that already has a provider account. It overwrites that account's token file with the newly granted scopes (keeping the stored refresh token when Google omits one on repeat consent), reactivates the row, and redirects with `reconnected=1`. The Accounts page's Reconnect link points at the same `/settings/accounts/connect` route.

**Rationale:** One flow, one code path, and the address is taken from Google's verified ID token, so a token can never be stored under a different mailbox than the one signed in — the failure the SCORE account suffered through the CLI flow in 2026-07.

**Constraints/Tradeoffs:** Choosing a different Google account at the consent screen connects that account instead of reconnecting the intended one; the page's title text names the expected address.

**Decided by:** Claude Code, 10-08-26 (MAIL-06).

### D-25 Summarization is one settled, capped pass after all accounts sync

**Decision:** A conversation is summarized only after it has had no new mail for a settle window (default 15 minutes); at most a capped number of conversations (default 500, newest first) are summarized per run, the rest deferred; and the pass runs once after every account has synced, resolving each conversation's owning mailbox for the prompt, instead of once per account inside the sync loop.

**Rationale:** Every new message in a thread resets its summary, so a busy thread was being summarized on each message. On 10-08-26 a 507-conversation backlog ran inside the first account's turn and held up the two newly connected accounts for half an hour. A settle window turns N calls into one; the cap bounds any single run's bill; moving the pass after the loop keeps mail sync independent of summarization time.

**Alternatives Rejected:** A token budget per run (MAIL-46/49) — right long-term control, but needs usage accounting that does not exist yet; the cap is the cheap stand-in. Summarizing in a separate background thread — the scheduler (MAIL-13) will own that; until then one ordered pass is simpler to reason about.

**Constraints/Tradeoffs:** A brand-new thread waits the settle window before its first summary. With the cap, a very large backlog takes several runs to clear.

**Decided by:** Claude Code, 10-08-26 (MAIL-19).

### D-26 Outbox failure classes, discard semantics, and push timing

**Decision:** An adapter marks an `ActionResult` as `permanent` when the provider's answer cannot change on retry (Gmail: any 4xx except 429); the outbox dead-letters those at once and backs off only transient failures (429, 5xx, network, adapter exceptions), doubling from 30 seconds to a one-hour cap until `mail_action_retry_max` (default 8) attempts. A dead-lettered row is resolved by the user: retry re-queues it with attempts reset; discard reverts the local change by applying the inverse action (a move is undone by restoring the origin labels). The worker runs for each account before its delta is fetched, so the provider carries the user's changes before the mirror reads back. Targets are stored as provider message ids, resolved from local ids at enqueue time.

**Rationale:** Retrying a 403 or a malformed request only delays the user's discovery; retrying a 429 is exactly right. Reverting on discard keeps the mirror honest with the provider when a change never landed. Push-before-pull avoids a delta re-applying the pre-action state over an optimistic change.

**Constraints/Tradeoffs:** Echo suppression (EPS-09) is not implemented; a delta that reports the pushed change re-applies it, which is idempotent. A newer local change on the same message could still be overwritten by a stale delta in the window between push and fetch; the scheduler (MAIL-13) narrows that window.

**Decided by:** Claude Code, 10-08-26 (MAIL-14).

### D-27 Scheduler mechanics: one tick, per-account workers, one post pass, manual runs aggregated

**Decision (refines D-07):** A single scheduler thread ticks every five seconds. Each active account is due when its interval has elapsed since its last run *finished* (not started), or when a run was requested; a due account syncs on its own worker thread and an account never has two runs at once. The cross-account pass (summaries, enrichment, identity resolution) runs once, only when no account worker is active and at least one has finished since the last pass. Pause stops timed runs; requests still run. The Dashboard's "Sync Now" becomes a request for every account tracked as one aggregate run, so its existing status contract (`running`, `started_at`, `completed_at`, `result`, `error`) is unchanged and a second Sync Now during a manual run still returns 409. The `sync_enabled` tenant setting already on the System page is the timer switch. The pipeline was split into `sync_account` and `post_sync_pass` so the scheduler and `run_full_sync` share one implementation; `RateLimiter` became thread-safe for the shared Gmail limiter.

**Rationale:** Interval-from-finish keeps a slow account from queueing back-to-back runs. One post pass after all accounts matches D-25. Reusing the manual-run contract avoids touching the Dashboard.

**Alternatives Rejected:** Per-account timers as separate threads — more threads to supervise for no gain at four accounts. Running the post pass inside each account worker — would reintroduce the blocking D-25 removed.

**Constraints/Tradeoffs:** The scheduler lives in the web server process, so a server restart interrupts a running account sync (the next tick restarts it; provider-id upserts absorb the overlap). Scheduled runs attribute created records to the account's first owner. A failed token refresh in a worker still calls the interactive flow inside `get_credentials_for_account`; MAIL-38 owns that fix (§9.1).

**Decided by:** Claude Code, 10-09-26 (MAIL-13).

### D-28 Mail search: a plain FTS5 table kept by triggers, operators resolved in one function

**Decision (refines D-06):** `communications_fts` is a regular (not external-content) FTS5 table with `comm_id`, `subject`, `body`, `participants`, tokenizer `porter unicode61`, maintained by six triggers on `communications` and `communication_participants`. Free text and `subject:` go to `MATCH`; every user term is quoted as a phrase (trailing `*` keeps prefix matching) so punctuation and the words AND, OR, NOT are literal. `from:`, `to:`, `cc:`, `account:` use case-insensitive LIKE on the structured columns; folders and labels resolve through `mailbox_labels`; `in:archive` means "in no inbox, trash, or spam folder"; trash and spam are excluded unless the query names them. `build_sql` is the only function that produces SQL.

**Rationale:** External-content FTS5 keys on rowid, which SQLite does not guarantee stable for a table with a text primary key across VACUUM; a plain table keyed by `comm_id` is safe. Phrase-quoting every term removes the FTS5 syntax surface from user input. Keeping participant operators on structured columns gives exact role semantics (to versus cc) that the index cannot.

**Alternatives Rejected:** `MATCH` with raw user input — a stray quote or colon returns an FTS syntax error. Indexing participants only in the FTS table — loses the to/cc distinction.

**Constraints/Tradeoffs:** Porter stemming makes `subject:meeting` also match "Meet"; acceptable for mail search, and a phrase in quotes is still stemmed. The index roughly doubles text storage (11,508 rows indexed in under three seconds on the live copy). `has:attachment` returns nothing until MAIL-15 stores attachment metadata.

**Decided by:** Claude Code, 10-09-26 (MAIL-12).

### D-29 Thread list: provider thread id, folder membership by any message, counts from the mirror

**Decision:** The mail surface groups by `(account_id, provider_thread_id)`, falling back to the message id when the provider gave none; the RFC References chain is not used for grouping (this settles the first item in §3). A thread appears in a folder when any of its messages carries that label, and the list is ordered by the newest matching message. Folder counts (unread, total) are computed from `communication_labels` and the flag columns on every request rather than read from the provider's label counts, which lag behind the mirror. Folders and search share `mail_search.predicates`, so a folder is a search with `in:` preset and a user label is a search on the label row id. The thread subject is the first message's.

**Rationale:** Gmail's own list behaves this way, so the mirror matches what the user sees elsewhere. Computing counts locally keeps them consistent with the optimistic action effects (D-04). One predicate builder means the folder tree and the search box can never disagree on membership.

**Constraints/Tradeoffs:** Counting on each request is a full scan of membership rows; at the production profile (about 12,000 messages) it is milliseconds, and a cached count table is the escape hatch if that changes. Cross-account duplicates (the same Message-ID in two accounts) show as two threads until MAIL-44.

**Decided by:** Claude Code, 10-09-26 (MAIL-16).

### D-30 The mail surface is a mode of the existing shell, with its own three panes inside the content area

**Decision:** Mail is a fourth special mode of the single-page application beside Dashboard, Review, and Settings: a `mailMode` flag plus `mailAccountId`, `mailFolder`, and `mailThreadId` in the navigation store, mapped to `/app/mail/{account|unified}/{folder}[/{thread}]` by the existing URL-sync hook (a thread change within the same folder replaces history; a folder change pushes). The content panel renders `MailView`, which lays out its own folder tree, thread list, and reading pane; the shell's Action Panel shows a placeholder in mail mode and the Detail Panel is untouched. Folder, thread, and unread data come from the MAIL-16 routes through TanStack Query with 30-second polling for the list and 60-second polling for the rail badge (the D-11 first step).

**Rationale:** The shell's panels are sized for grid-plus-detail; mail needs three panes of its own proportions, so it owns them. Reusing the mode pattern keeps the rail, header, and URL handling consistent with the other surfaces and avoids introducing a router.

**Alternatives Rejected:** Making mail an "entity type" in the grid system — the grid is the wrong shape for threads. Introducing a router library — the hand-written URL sync already covers the needed forms.

**Constraints/Tradeoffs:** A thread id is unique only within an account; the reading pane resolves the account from the loaded list in unified view, so a deep link to a unified thread resolves only once the list containing it has loaded. The Action and Detail panels still take space in mail mode until the user collapses them.

**Decided by:** Claude Code, 10-09-26 (MAIL-21).

### D-18 Adapters call the HTTP client through the module object

**Decision:** `GmailProvider` calls `gmail_client.<function>` via the imported module, never `from gmail_client import <function>`.

**Rationale:** Existing tests patch `poc.gmail_client.<function>`; module-attribute calls keep those patches effective. The HTTP layer stays in one file that owns rate limiting and error mapping.

**Decided by:** Claude Code, 10-08-26 (MAIL-05).

---

## 3. Decisions to Be Added by Claude Code

- ~~**Thread model:**~~ settled by D-29 (provider thread id).
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
| 1.10 | 10-09-26 00:30 | Claude (Claude Code) | Write-back for MAIL-21: D-30 (mail as a shell mode with its own panes; URL mapping; polling). |
| 1.9 | 10-09-26 00:20 | Claude (Claude Code) | Write-back for MAIL-16: D-29 (thread grouping, folder membership, local counts); §3 thread-model item settled. |
| 1.8 | 10-09-26 00:15 | Claude (Claude Code) | Write-back for MAIL-12: D-28 (FTS5 table by triggers, phrase-quoted terms, operator resolution). |
| 1.7 | 10-09-26 00:05 | Claude (Claude Code) | Write-back for MAIL-13: D-27 (scheduler mechanics, manual-run aggregation, pipeline split). |
| 1.6 | 10-08-26 23:55 | Claude (Claude Code) | Write-back for MAIL-09/14: D-26 (outbox failure classes, discard, push-before-pull). |
| 1.5 | 10-08-26 23:40 | Claude (Claude Code) | Write-back for MAIL-19: D-25 (settled, capped, post-loop summarization). |
| 1.4 | 10-08-26 22:10 | Claude (Claude Code) | Write-back for MAIL-10/06: D-22 (deletion archives), D-23 (tokens loaded with granted scopes), D-24 (reconnect = connect). |
| 1.3 | 10-08-26 13:40 | Claude (Claude Code) | Write-back for MAIL-07/08: D-19 (provider authoritative on re-seen rows), D-20 (flags as columns), D-21 (backfill by command). |
| 1.2 | 10-08-26 13:05 | Claude (Claude Code) | Implementation write-back for MAIL-05: D-15 (`ParsedEmail` as the contract type), D-16 (thread-grouped `fetch_initial`), D-17 (cursor read at fetch time), D-18 (module-object calls). |
| 1.1 | 10-08-26 12:33 | Claude (Claude Code) | Status set to Approved on the product owner's approval; D-02–D-14 now binding. |
| 1.0 | 10-08-26 01:30 | Claude (Claude Code) | Initial draft. D-01 records the product owner's architecture choice; D-02–D-14 are proposals for approval. |
