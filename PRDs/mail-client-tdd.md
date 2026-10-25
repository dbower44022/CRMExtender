# Mail Client — TDD

**Version:** 1.26
**Last Updated:** 10-24-26 18:27
**Status:** Approved 10-08-26 by the product owner — living document; D-01–D-14 approved, D-15–D-47 written back during the build and binding until revised here
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

### D-31 Mail bodies render in an opaque-origin frame; the allow list is per browser for now

**Decision (implements D-08):** Each body zone (new text, quoted text) is sanitized by DOMPurify with a profile that also forbids forms, frames, `meta`, `link`, and `base`, then wrapped in a `srcdoc` document carrying a strict Content Security Policy and rendered in an `<iframe sandbox="allow-scripts">`. The frame has an opaque origin: it cannot read cookies, storage, or the parent page. The only script inside is ours, appended after sanitization, which reports the document height and relays link clicks through `postMessage`; the parent opens `http`, `https`, `mailto`, and `tel` links in a new tab and drops the rest. Remote images and CSS `url()` loads are neutralized until the viewer clicks "Load images" (this message) or "Always from this sender", which is stored in the browser's localStorage. The regex sanitizer stays in use for the Communication full view until that view is retired.

**Rationale:** An all-accounts client reads mail from strangers; the TDD for the old view admitted the regex sanitizer was not a security boundary. `allow-scripts` without `allow-same-origin` is the documented safe pairing: our measuring script runs, but the page is cross-origin to the application. Splitting before sanitizing keeps the quote-splitter's client-markup heuristics intact.

**Alternatives Rejected:** DOMPurify alone in the page — leaks mail CSS into the shell. `allow-same-origin` for direct height measurement — would let the sandboxed document reach the parent if sanitization ever failed.

**Constraints/Tradeoffs:** Height arrives asynchronously, so a frame can flash short before the first report. The allow list does not follow the user across browsers; PRD §3.1 `mail.remote_images` as a server-side user setting is still to do. `cid:` images resolve only once MAIL-26 serves attachments.

**Decided by:** Claude Code, 10-09-26 (MAIL-25).

### D-32 Attachments: metadata at sync, bytes on demand, no retroactive capture

**Decision (implements D-09):** The Gmail parser already yields every attachment part's id, name, type, size, and Content-ID; the sync store upserts those into `attachments` keyed by (message, provider part id). Bytes are fetched through the adapter only when a user opens or downloads the file, written to `data/attachments/<account>/<id>.bin`, and pruned least-recently-used to the `mail_attachment_cache_mb` budget. Inline images resolve through a `cid` route keyed by message id and Content-ID, so the sandboxed frame never needs an attachment id. Served files always carry `X-Content-Type-Options: nosniff`; HTML, SVG, and JavaScript attachments are forced to download. Messages mirrored before this release have no attachment rows because their mail-state backfill used metadata-only fetches, which carry no parts; a full-fetch backfill is a separate, costly job and is deferred until the owner asks for it.

**Rationale:** Storing every attachment up front would multiply the mirror; most are never opened. Keying inline images by Content-ID matches how the HTML references them.

**Alternatives Rejected:** Re-fetching 11,000 messages in full to recover old attachments — hours at the rate limit for files rarely needed.

**Constraints/Tradeoffs:** The first open of any attachment waits on the provider. The cache is per server, not synchronized anywhere. A thread's "has attachments" mark is false for pre-v10.19 mail.

**Decided by:** Claude Code, 10-09-26 (MAIL-15).

### D-33 Action bar semantics: selection beats the open thread; the server owns the optimistic state

**Decision:** The action bar above the thread list acts on the current multi-selection when one exists, otherwise on the open thread. For the open thread every message id is sent (the detail is loaded); for selected-but-unopened threads only the latest message id is known from the list, so the action targets that message. The client sends one request per account, then invalidates every mail query; the server's immediate local write (D-04) is what makes the change appear at once, so the client keeps no shadow state. Mark-read-on-open is a timer in the reading pane keyed by the set of unread message ids; the dwell is the tenant setting `mail_mark_read_dwell_ms`.

**Rationale:** Keeping optimism on the server means the list, counts, and folder tree all agree after one refetch, and a failed push is surfaced from the queue rather than reconstructed client-side.

**Constraints/Tradeoffs:** Acting on an unopened multi-message thread touches only its latest message until MAIL-23's list carries all message ids; a thread-level action endpoint (`thread_ids` → all messages server-side) is the natural fix and is noted for the keyboard work in MAIL-30. The dwell setting is tenant-wide; the PRD wants it per user.

**Decided by:** Claude Code, 10-09-26 (MAIL-27).

### D-34 Keyboard model mechanics

**Decision:** Bindings are registered with react-hotkeys-hook at the mail view level, enabled only in mail mode and never inside form fields. Two-key folder chords are a one-second "g" arm: `s` is star unless it follows `g`, when it is "go to Starred". Action shortcuts target the selection when one exists, else the focused row, else the open thread, and send whole threads to the server (`threads` on `POST /mail/actions`), which expands each to all of its current messages; this replaces the D-33 latest-message compromise for list actions too. After archive, trash, or spam the focus advances to the next row and the reading pane closes if it showed a removed thread, so `j`/`e` runs flow. Esc cascades: shortcut sheet, then open thread, then selection, matching the GUI PRD §23.3 order. Bindings whose feature is not built yet (snooze, label, move, search) show a one-line note rather than doing nothing silently.

**Rationale:** The list and pane keep their own local key handling for movement when focused; the view-level layer is what makes "ten emails in ten keystrokes" work without the list having focus. Whole-thread targets are the only correct semantics for a row that stands for several messages.

**Constraints/Tradeoffs:** The `g` arm is a timer, so a slow second key falls back to the key's plain meaning. Account switch by digit follows the folder tree's order, which is account creation order.

**Decided by:** Claude Code, 10-09-26 (MAIL-30).

### D-35 Frontend test harness (implements D-13)

**Decision:** Vitest with Testing Library in jsdom, run by `npm test` and in CI after lint. Tests live beside their subjects as `*.test.ts(x)` under `src/`; `src/test/setup.ts` provides DOM matchers, a stand-in ResizeObserver, and fixed element heights so TanStack Virtual renders rows; `src/test/utils.tsx` renders inside a fresh QueryClient and stubs `fetch` by URL prefix so components are exercised through their real data hooks. Synthetic key events carry `code` as well as `key`, because react-hotkeys-hook matches on both. The Playwright smoke test from the PRD is deferred until the app can be driven from where the tests run.

**Rationale:** Vitest shares the Vite config, so the harness costs one config block and no second toolchain. Stubbing `fetch` rather than the hooks keeps the tests honest about request shapes (the mark-read test asserts the exact action body).

**Constraints/Tradeoffs:** jsdom has no layout; row virtualization is tested with fixed heights, not real scrolling. Sandboxed frames render as elements but their inner document is not executed.

**Decided by:** Claude Code, 10-09-26 (MAIL-40).

### D-36 Search narrows the folder; saved searches stay per browser for now

**Decision:** The search box sends its query as `q` on the thread list request, so results are the current folder's threads that also match; a query carrying `in:` or `label:` overrides the folder (the parser's `in_` wins over the folder preset). The query is keyed by folder and clears when the folder changes. Saved searches are name/query pairs in the browser's localStorage, shown as chips under the box; promoting them to server-side views in the folder tree (PRD KP-MAIL-05 step 4) is deferred until the views system and mail share a model.

**Rationale:** Narrowing the current folder is what users expect from a box inside a folder; a global search already exists (Ctrl+K). Per-browser saved searches ship the behavior now without a schema change.

**Constraints/Tradeoffs:** Saved searches do not follow the user across browsers. The thread list total shown is the match count within the folder.

**Decided by:** Claude Code, 10-09-26 (MAIL-31).

### D-37 Context column reads the existing contact detail route

**Decision:** The column derives the thread's external participants client-side from the thread detail (senders newest-first, then recipients, excluding the account's own address, at most three) and fetches each known contact through the existing `GET /contacts/{id}` route, which already returns identity, current affiliation, score, and a timeline with conversation summaries. No mail-specific contact endpoint was added. Unknown senders open the existing Add Contact modal; prefilling it with the sender's name and address is a small follow-up once that modal accepts initial values.

**Rationale:** The contact detail route is the one source the Contact Full View will also use (contact-view-prd.md), so the column cannot drift from it. Three cards keep the column readable on a thread with many recipients.

**Constraints/Tradeoffs:** Three contact requests per opened thread, cached a minute. The PRD's "open tasks" line waits for the Task entity.

**Decided by:** Claude Code, 10-09-26 (MAIL-32).

### D-38 Composer: one form, three placements, queued send through the outbox table

**Decision:** One form (`ComposeForm`) serves the docked composer, the inline reply, and a resumed draft; it seeds its state from props once the reply context or draft is known (`ComposeFormLoader`), so it has no pre-fill effects. The store holds up to three composers, each docked or inline; an inline composer is keyed to its thread (`account:thread`) and is drawn by the reading pane while that thread is open and by the dock as a tab otherwise, without the store changing. Undo-send and scheduled send are one mechanism: the draft becomes `queued` with `scheduled_send_at`, the scheduler tick calls `outbound.send_due`, and `/undo` returns a still-queued row to `draft`. Files picked before the draft exists stay in the browser and upload when the draft is first saved; the server stores them under the upload directory and reads them back as MIME parts at send time. The default signature is shown under the editor as read-only and added by the server on send, as it already was, so it is never sent twice.

**Rationale:** One form keeps reply, forward, new, and resume behaving the same. Reusing the outbox row's `queued` status needs no new table and makes a scheduled message visible as a draft that cannot be edited until it is pulled back. Seeding from props follows the React Compiler rule the mail view already keeps.

**Constraints/Tradeoffs:** The undo window is bounded by the scheduler tick (5 s) on top of the setting. A queued message is sent by whichever process runs the scheduler, so with the scheduler disabled nothing goes out until it is enabled. The signature cannot be edited in the composer; that waits for a signature-editing task.

**Decided by:** Claude Code, 10-09-26 (MAIL-33–36).

### D-39 Live updates: an in-process broadcaster streamed as server-sent events, polling kept as fallback

**Decision:** `poc/events.py` is a process-wide broadcaster: publishers (the scheduler's account workers, the post pass, the queued-send step) call `publish(type, **data)` from their threads; each subscriber owns a bounded queue of 256 events and a slow subscriber loses its oldest events rather than blocking a publisher. `GET /mail/events` subscribes, polls its queue four times a second, checks for client disconnect each loop, sends a keep-alive comment after fifteen idle seconds, and withholds events for accounts the caller cannot see; `max_seconds` ends a stream for idle-limited proxies and for tests. The browser opens one EventSource per tab and, on `sync.finished`, `post_pass.finished`, or `outbound.sent`, invalidates every mail query; the 30-second polling of folders, list, and thread stays, so a dropped event or a closed stream costs at most one poll interval. Events carry counts only (`_event_result`), never message content.

**Rationale:** The scheduler already lives in the web server process (D-27), so no message bus is needed; one queue per browser tab is cheap at this scale. Invalidating rather than patching the cache keeps the browser logic to one line and reuses the existing fetches. Gmail push (MAIL-52) will publish through the same broadcaster.

**Alternatives Rejected:** WebSockets — two-way is not needed and the session cookie works unchanged with EventSource. Patching the query cache from event payloads — would duplicate the server's folder and thread logic in the browser.

**Constraints/Tradeoffs:** One stream per tab, each polling an in-memory queue; fine for a handful of tabs. A browser behind a proxy that buffers responses sees nothing until the proxy flushes; `X-Accel-Buffering: no` is set for the common case. Events do not cross processes: a second server process would not see this one's syncs.

**Decided by:** Claude Code, 10-09-26 (MAIL-37).

### D-40 Account health: non-interactive credentials in the server, a parked state the scheduler skips

**Decision:** `auth.get_credentials_for_account` gains an `interactive` switch with a module default; `create_app` turns it off, so inside the web server a token that is missing, unreadable, or fails to refresh raises `ReauthRequired` instead of starting the local-browser consent flow. The CLI keeps the interactive default. `sync_account` and `send_email` catch `ReauthRequired` and set `provider_accounts.auth_status = 'needs_reauth'` with the reason; the scheduler's account query excludes `needs_reauth` and `disconnected`; the web reconnect callback sets the status back to `ok`. Every scheduled run records its first error (or clears it) on the account row, which the Accounts page shows as a Sync error badge. Disconnect has two modes: *keep* removes the token file, blanks the cursor, and marks the row `disconnected` and inactive, leaving every message as history; *delete* removes the account's outbound mail, messages, conversations, calendar events, and the row (labels, actions, sync log, and user links cascade). Attachment cache files are left to the cache's own size pruning. A successful refresh is now written back to the token file, which the old code did not do.

**Rationale:** The interactive flow inside a server thread would hang the worker waiting for a browser nobody sees (§9.1). A status column, not a derived check, lets the page explain *why* an account stopped and lets the scheduler skip it cheaply. Keeping mail on disconnect matches D-22 (deletion archives, never destroys) and is the default the page offers first.

**Alternatives Rejected:** Deactivating the account (`is_active = 0`) on refresh failure — loses the distinction between "the owner paused it" and "it broke", and the page could not offer the right action. Deleting the account's mail by cascade from the account row — the schema sets `account_id` to NULL on communications and conversations, which would orphan them silently.

**Constraints/Tradeoffs:** `GET /settings/system` is administrator-only, so for a non-administrator the browser falls back to the built-in defaults for the mark-read dwell and the undo window. The seven-day refresh-token expiry of a Testing OAuth client, if it ever applies, now shows as Needs reconnect with the provider's reason rather than a hung sync.

**Decided by:** Claude Code, 10-09-26 (MAIL-38).

### D-41 New-mail notifications: the server finds the news, the browser applies the setting

**Decision:** After an account run finishes, the scheduler worker queries the messages stored since the run started that are inbound, unread, current, and in the inbox, and publishes them as one `mail.new` event (count plus up to ten items with sender, subject, snippet, thread id, and a `known_contact` flag from the contact identifiers). A run on an account whose first sync has not completed publishes nothing. The browser reads the account's `mail_notifications` setting (per user, per account, stored as a user-scoped setting `mail_notifications:<account_id>`; default `known_contacts`) and shows up to three pop-ups, then one summary, each with an Open link that deep-links to the thread. The event also invalidates the mail queries, which refreshes the rail badge.

**Rationale:** Deriving "new" from `created_at >= run start` needs no change to the sync engine's return value and is correct for incremental runs. Applying the setting in the browser keeps the event one per run and lets a setting change take effect on the next event without touching the server. Known-contact filtering uses the same identifier lookup as the thread list, so the two never disagree.

**Alternatives Rejected:** One event per message — noisy on a busy inbox and no better for the summary case. Filtering on the server per subscriber — the stream is one per browser tab, not per account setting, and the browser already fetches the account list.

**Constraints/Tradeoffs:** Mail that arrives while the browser is closed is not announced later; the unread badge covers it. The browser fetches the account list on each `mail.new` event (cheap, cached a minute elsewhere). `GET /settings/system` being administrator-only does not affect this path.

**Decided by:** Claude Code, 10-09-26 (MAIL-39).

### D-42 Provider drafts: kept for the Drafts folder, never part of a conversation, deleted when the provider drops them

**Decision:** A message carrying the provider's Drafts label is stored like any other (so the Drafts folder shows drafts begun elsewhere) but is never linked to a conversation, never counted, and never summarized. When the provider reports such a message gone, it is deleted outright instead of archived — the only exception to D-22. A one-time `cleanup-drafts` command unlinked the 12 drafts that earlier code had placed in conversations and deleted the 2 autosave remnants that a sent message in the same thread had superseded within ten minutes; the 14 affected conversations were recounted and queued for a new summary. Older unlabelled outbound rows without such a sibling are left alone, since they may be mail sent and later deleted.

**Rationale:** Gmail autosaves a draft under a new message id every few seconds and discards it on send; the sent message is the history, the draft is not. Storing drafts as activities produced a second "message" in the owner's "Next week demo" conversation (10-09-26), which the summarizer correctly called an incomplete draft of the first. Keeping drafts out of conversations rather than out of the store preserves the Drafts folder.

**Alternatives Rejected (owner's choice, 10-09-26):** Option A — not storing provider drafts at all. Simpler, but a draft started in Gmail on the phone would not appear here.

**Constraints/Tradeoffs:** The draft test is label membership at the moment the deletion is processed, so a draft whose label was stripped by an earlier delta in the same run would archive rather than delete; the next cleanup run would catch it. Draft rows still appear inside the thread when it is opened from a folder, as they do in Gmail.

**Decided by:** Product owner (Option B), implemented by Claude Code, 10-09-26 (v10.31).

### D-43 Historical backfill: one batch per sync run, checkpoint on the account row

**Decision:** The backfill job (MAIL-11) runs inside each account's scheduled sync, after the incremental delta, and fetches one batch (`mail_backfill_batch_size`, default 200, clamped 10–500) through `MailProvider.fetch_backfill`. The checkpoint is `provider_accounts.backfill_cursor`, initialised to `"<oldest stored epoch>|"` on first use; `backfill_done` is set when the adapter returns no next cursor. `mail_backfill_enabled=false` stops the job at the checkpoint. Backfilled messages dedupe by provider message id like any re-seen message, and the new-mail notification ignores mail whose own timestamp is more than a day before the run, so history never pops up as news.

**Rationale:** Running inside the account worker guarantees the same account never syncs and backfills concurrently (D-07) without a second scheduler. A batch per run at the default 120-second interval stores about 6,000 messages an hour, which is slow enough for the Gmail quota and the summarizer's per-pass cap (D-25) and fast enough to finish a 20,000-message mailbox overnight.

**Constraints/Tradeoffs:** Each backfilled thread may create a conversation and so a summary; the owner controls that cost with the enabled switch and `summarize_max_per_sync`. The live setting was shipped **off** on 10-11-26 for that reason. Gmail's `before:` query is exclusive at second resolution, so the boundary message is re-fetched once and deduped.

### D-44 Snooze: a local table drives the folder; the provider label is for other clients

**Decision:** `mail_snoozes` (account, thread, return_at, status) is the source of truth for the Snoozed folder and its count; the `CRMExtender/Snoozed` label exists so Gmail and other clients show the state, and the adapter finds or creates it at push time (D-12). `snooze` and `unsnooze` are ordinary outbox actions: the local effect of `snooze` removes Inbox; of `unsnooze` restores Inbox and marks unread. The scheduler's tick (D-07) runs the return pass: each due row queues `unsnooze` for the thread's current messages and publishes `mail.new` (reason `snooze_returned`, `known_contact=true`) so the existing pop-up path announces it. A second snooze on a thread replaces the first.

**Rationale:** Keeping the folder on a local table makes snooze work instantly and offline from the provider, and avoids a round trip to learn the label id before the thread can leave the inbox. Reusing `mail.new` means no new browser event type for MAIL-39.

**Constraints/Tradeoffs:** Until MAIL-28 there is no picker; the API takes `payload.return_at` (ISO 8601, future). If the provider push of `snooze` dead-letters, the thread is still hidden locally and shown in the outbox's failed list.

### D-45 One HTML body (D-10 delivered in v31)

**Decision:** D-10 shipped in schema v31 instead of v23: `cleaned_html` is NULL unless a cleaning step produced something different from `original_html`; ingest writes `original_html` only; every reader (`mail_threads`, `outbound`, the record and conversation APIs) takes `COALESCE(cleaned_html, original_html)`. The migration nulls the duplicate and VACUUMs the file.

**Rationale:** On 10-11-26 all 11,821 live rows held an identical second copy, 401 MB of 914 MB. Nothing in the code base ever wrote a different `cleaned_html`.

**Constraints/Tradeoffs:** VACUUM needs the database idle and free space equal to the file; the migration skips it when locked and `python -m poc.migrate_to_v31 --vacuum-only` finishes the job after a server stop.

### D-46 Awaiting reply: computed from the mirror, opt-outs stored

**Decision:** The Awaiting reply list (MAIL-47) is a query, not a table: a thread is listed when its newest current message is outbound from the owner, has at least one To or Cc recipient, is older than `mail_awaiting_reply_days` (system setting, default 3, clamped 1–60) but sent within `mail_awaiting_window_days` (default 30, clamped 7–365; on the live database 622 threads were unanswered at three days across eleven years of sent mail, 10-11-26), carries no trash, spam, or draft label, and the thread is not in `mail_awaiting_dismissed`. The folder appears in the unified set and per account with its thread count as the badge. "Nudge" opens the composer as a reply-all to the owner's last message, which the existing reply context addresses to that message's original To and Cc. "Stop waiting" writes the opt-out row; "restore" deletes it.

**Rationale:** Computing on read means a reply clears the entry the moment the sync stores it, with no state to keep in step and nothing for the scheduler to do. Two tunables: how long silence must last, and how far back a sent message can be before silence stops being a reminder.

**Alternatives Rejected:** An AI-drafted nudge body — that is MAIL-48's territory and spends tokens; the plain composer with the quoted message is enough. A per-thread reminder time — snooze already covers "remind me later".

**Constraints/Tradeoffs:** Automated recipients (newsletters, no-reply addresses) the owner writes to will be listed until dismissed; a rule layer can exclude them when MAIL-46 lands. A thread the owner re-sends to is re-listed after the threshold, as intended.

### D-47 Cross-account duplicates: a link table of thread groups, merged only in multi-account views

**Decision:** `mail_thread_links (account_id, thread_id, group_id)` records which provider threads in different accounts are one conversation, keyed on a shared RFC 5322 Message-ID. The store path links a thread whenever one of its Message-IDs already exists in another account; groups merge transitively; migration v33 rebuilt the table from stored mail. A scope of more than one account (the unified folders) groups rows by `COALESCE(link.group_id, account:thread)`, presents one row with every account's chip, counts one copy per Message-ID in the unified badges, opens the account holding the newest message, and sends actions to every member thread. Thread detail merges the group's messages, one per Message-ID, with the requested account's copy winning and each message tagged with its account. A single-account scope ignores the links entirely.

**Rationale:** Connected groups cannot be computed in one SQL pass at read time, and the store path already sees every message once; a small link table is cheaper than rewriting the thread model. Keeping per-account views untouched preserves the one-to-one mirror of each mailbox, which the snooze, awaiting-reply, and outbox code rely on.

**Alternatives Rejected:** Collapsing duplicates at ingest (store one copy) — breaks the mirror: each mailbox's labels, flags, and provider ids differ and must be pushed back separately. Grouping by the first message's id — fails when one account joined the thread late.

**Constraints/Tradeoffs:** Flags shown for a merged row are the winning copy's; reading a message in one mailbox does not mark its twin read in the other until the owner acts on the merged row (the action then covers both). Search results and new-mail pop-ups still work per account. On the live database the rebuild found 33 shared Message-IDs forming 28 groups over 56 threads among the three active accounts (10-12-26); the retired SCORE mailbox's rows carry no Message-ID header (their pre-v23 state was frozen) and so never link.

### D-48 Token accounting is a ledger per call; bulk summarization goes to a Message Batch above a count threshold

**Decision:** Every Anthropic call writes one row to `ai_usage` (time, purpose, mode `live` or `batch`, model, conversation, batch id, request id, the four token counts, and `cost_usd`). The cost is an estimate computed at write time from `poc/ai_pricing.py`, a price table in code that carries its own date (`PRICE_TABLE_DATE`) and is shown beside every figure; an unpriced model stores `NULL` and is counted separately rather than guessed. The summarization pass (`process_conversations`) routes by count: when more settled conversations than `summarize_batch_threshold` are waiting (default 50; 0 disables), all of them are submitted as one Message Batch (`poc/summary_batches.py`) built from the same `build_summary_params` the live call uses, recorded in `ai_batches` / `ai_batch_items`, and left alone by the live pass until the batch is processed. The scheduler polls open batches once a minute; an ended batch's succeeded results go through `apply_summary`, the same store step as a live summary, with usage recorded at the batch discount; errored, expired, canceled or missing items are marked processed without a summary, which returns the conversation to the next live pass.

**Rationale:** The deferred cost decisions (backfill window, re-summarization, the MAIL-46 token budget) all need measured spend, not estimates from prompt size; a ledger per call is the smallest thing that gives it and it also prices the batch path honestly. A count threshold, not conversation age, decides batching because age cannot tell a new account's recent mail from a backfill: both arrive as a burst, and a burst is exactly when a one-hour delay is worth a half-price bill. Sharing the request builder and the store step between the two paths keeps one prompt and one parser.

**Alternatives Rejected:** Reading cost from the Anthropic usage API — needs an admin key and reports by organization, not by conversation. A cost setting the owner edits — stale silently; a dated table in code is at least visibly dated. Batching by conversation age — see rationale. Capping the batch at `summarize_max_per_sync` — the cap bounds a live bill; a batch is half price and asynchronous, so it is bounded only by the API's request limit (10,000 per batch here).

**Constraints/Tradeoffs:** `cost_usd` is an estimate: list prices change and cache pricing is approximated where Anthropic publishes no separate figure. A batched conversation shows no summary for up to an hour (the API's usual turnaround; 24 hours at most). Results are keyed by `custom_id`, never by position. The live pass skips conversations with an open batch item, so a batch that the API never ends holds those conversations until the poll marks it failed; `install-desktop.sh logs` shows the poll's warnings. The ledger grows by one row per summary; at the current volume that is a few thousand rows a year.

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
| 1.26 | 10-24-26 18:27 | Claude (Claude Code) | Write-back for MAIL-49 (v10.46): D-48 — per-call usage ledger with a dated price table; count-threshold routing to Message Batches; shared request builder and store step. |
| 1.25 | 10-12-26 17:28 | Claude (Claude Code) | Write-back for MAIL-44: D-47 (thread groups by shared Message-ID; merged only in multi-account views). |
| 1.24 | 10-11-26 19:32 | Claude (Claude Code) | Write-back for MAIL-47: D-46 (awaiting reply computed on read; opt-outs stored). |
| 1.23 | 10-11-26 14:14 | Claude (Claude Code) | Write-back for Phase 1 close-out (v10.36): D-43 backfill job, D-44 snooze, D-45 one HTML body (D-10 delivered). |
| 1.22 | 10-09-26 12:43 | Claude (Claude Code) | D-42: provider drafts never join conversations; a dropped draft is deleted (exception to D-22). v10.31. |
| 1.21 | 10-09-26 10:07 | Claude (Claude Code) | Write-back for MAIL-39: D-41 (new-mail notifications). |
| 1.20 | 10-09-26 10:06 | Claude (Claude Code) | Write-back for MAIL-38: D-40 (non-interactive credentials, parked accounts, disconnect modes). |
| 1.19 | 10-09-26 09:58 | Claude (Claude Code) | Write-back for MAIL-37: D-39 (in-process broadcaster streamed as server-sent events). |
| 1.18 | 10-09-26 09:50 | Claude (Claude Code) | Write-back for MAIL-33–36: D-38 (one composer form, three placements, queued send through the outbox table). |
| 1.17 | 10-09-26 02:30 | Claude (Claude Code) | Write-back for MAIL-32: D-37 (context column on the contact detail route). |
| 1.16 | 10-09-26 02:25 | Claude (Claude Code) | Write-back for MAIL-31: D-36 (search narrows the folder; per-browser saved searches). |
| 1.15 | 10-09-26 02:20 | Claude (Claude Code) | Write-back for MAIL-40: D-35 (harness choices). |
| 1.14 | 10-09-26 02:15 | Claude (Claude Code) | Write-back for MAIL-30: D-34 (keyboard mechanics, whole-thread targets). |
| 1.13 | 10-09-26 01:05 | Claude (Claude Code) | Write-back for MAIL-27: D-33 (action targets, server-owned optimism, dwell). |
| 1.12 | 10-09-26 01:00 | Claude (Claude Code) | Write-back for MAIL-15: D-32 (metadata at sync, bytes on demand, no retroactive capture). |
| 1.11 | 10-09-26 00:50 | Claude (Claude Code) | Write-back for MAIL-25: D-31 (opaque-origin frames, DOMPurify profile, per-browser allow list). |
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
