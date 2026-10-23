# Conversation Entity — TDD

**Version:** 1.3
**Last Updated:** 10-23-26 01:12
**Status:** Draft — Section 9 extended with the timer decisions (schema v35, release v10.45)
**Scope:** Entity
**Parent Document:** [conversation-entity-base-prd.md]
**Product TDD:** [product-tdd.md]

---

## 1. Overview

The Conversation entity requires entity-specific technical decisions beyond the Product TDD's global defaults. Key areas include: the read model table DDL with indexes, the conversation_members junction table, the segment data model, event sourcing, virtual schema mapping, and API design.

---

## 2. Conversations Read Model Table

### 2.1 Table Definition

```sql
-- Within tenant schema: tenant_abc.conversations
CREATE TABLE conversations (
    -- Universal fields
    id                  TEXT PRIMARY KEY,        -- cvr_01HX8A...
    tenant_id           TEXT NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by          TEXT REFERENCES platform.users(id),
    updated_by          TEXT REFERENCES platform.users(id),
    archived_at         TIMESTAMPTZ,

    -- Core system fields
    subject             TEXT,
    is_aggregate        BOOLEAN NOT NULL DEFAULT FALSE,
    description         TEXT,
    system_status       TEXT NOT NULL DEFAULT 'active',
    ai_status           TEXT,
    ai_summary          TEXT,
    ai_action_items     TEXT,                   -- JSON
    ai_key_topics       TEXT,                   -- JSON
    ai_confidence       NUMERIC(3,2),
    ai_last_processed_at TIMESTAMPTZ,
    communication_count INTEGER DEFAULT 0,
    channel_breakdown   TEXT,                   -- JSON
    first_activity_at   TIMESTAMPTZ,
    last_activity_at    TIMESTAMPTZ,
    stale_after_days    INTEGER DEFAULT 14,
    closed_after_days   INTEGER DEFAULT 30
);
```

### 2.2 Indexes

```sql
CREATE INDEX idx_cvr_aggregate ON conversations (is_aggregate)
    WHERE is_aggregate = TRUE;
CREATE INDEX idx_cvr_system_status ON conversations (system_status);
CREATE INDEX idx_cvr_ai_status ON conversations (ai_status)
    WHERE ai_status IS NOT NULL;
CREATE INDEX idx_cvr_last_activity ON conversations (last_activity_at DESC);
CREATE INDEX idx_cvr_archived ON conversations (archived_at)
    WHERE archived_at IS NULL;
```

**Rationale:** Partial indexes on is_aggregate and ai_status reduce index size. The last_activity DESC index supports the default sort order.

---

## 3. Conversation Members Junction Table

### 3.1 Table Definition

**Decision:** Many-to-many membership between aggregate and child Conversations.

```sql
CREATE TABLE conversation_members (
    parent_conversation_id  TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    child_conversation_id   TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    added_by                TEXT REFERENCES platform.users(id),
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    PRIMARY KEY (parent_conversation_id, child_conversation_id),
    CHECK (parent_conversation_id != child_conversation_id)
);

CREATE INDEX idx_cvr_members_child ON conversation_members (child_conversation_id);
CREATE INDEX idx_cvr_members_parent ON conversation_members (parent_conversation_id);
```

**Rationale:** Composite PK prevents duplicate membership. CHECK constraint prevents self-membership. CASCADE delete cleans up when either conversation is deleted. Bidirectional indexes support both "children of X" and "parents of X" queries. Acyclic enforcement is application-level (ancestry walk before insert).

---

## 4. Segment Data Model

### 4.1 Table Definition

**Decision:** Segments are behavior-managed records for cross-conversation content references.

```sql
CREATE TABLE communication_segments (
    id                      TEXT PRIMARY KEY,       -- seg_ prefixed ULID
    communication_id        TEXT NOT NULL REFERENCES communications(id) ON DELETE CASCADE,
    source_conversation_id  TEXT NOT NULL REFERENCES conversations(id),
    target_conversation_id  TEXT NOT NULL REFERENCES conversations(id),
    content_start           INTEGER NOT NULL,       -- Character offset start
    content_end             INTEGER NOT NULL,       -- Character offset end
    selected_text           TEXT NOT NULL,           -- Denormalized for display
    created_by              TEXT REFERENCES platform.users(id),
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_seg_communication ON communication_segments (communication_id);
CREATE INDEX idx_seg_target ON communication_segments (target_conversation_id);
CREATE INDEX idx_seg_source ON communication_segments (source_conversation_id);
```

**Rationale:** Denormalized `selected_text` avoids re-extracting from content on every render. Character offsets enable highlighting in the source communication. CASCADE from communication ensures segments are cleaned up when the source is deleted.

---

## 5. Event Sourcing

### 5.1 Conversations Events Table

```sql
CREATE TABLE conversations_events (
    id              TEXT PRIMARY KEY,        -- evt_01HX8B...
    entity_id       TEXT NOT NULL,           -- cvr_01HX8A...
    tenant_id       TEXT NOT NULL,
    event_type      TEXT NOT NULL,
    field_slug      TEXT,
    old_value       TEXT,                    -- JSON-encoded
    new_value       TEXT,                    -- JSON-encoded
    changed_by      TEXT,
    changed_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata        JSONB
);

CREATE INDEX idx_cvr_events_entity ON conversations_events (entity_id, changed_at);
CREATE INDEX idx_cvr_events_type ON conversations_events (event_type);
```

### 5.2 Event Types

| Event Type | Trigger | Description |
|---|---|---|
| `created` | New conversation formed (auto or manual) | Full record snapshot in new_value |
| `field_updated` | Any field change | Old and new values for specific field |
| `communication_added` | Communication assigned to this conversation | Communication ID in metadata |
| `communication_removed` | Communication unassigned | Communication ID in metadata |
| `member_added` | Child Conversation added to aggregate | Parent and child IDs in metadata |
| `member_removed` | Child Conversation removed from aggregate | Parent and child IDs in metadata |
| `ai_processed` | AI generated summary/status/action items | AI output snapshot in metadata |
| `status_transition` | system_status changed | Old and new status |
| `merged` | Two conversations merged | Source conversation ID in metadata |
| `archived` | Soft-delete | |
| `unarchived` | Restore | |

---

## 6. Virtual Schema & Data Sources

### 6.1 Virtual Schema Table

Per Data Sources PRD, the Conversation field registry generates a virtual schema:

```sql
SELECT
    c.id, c.subject, c.is_aggregate, c.description,
    c.system_status, c.ai_status, c.ai_summary,
    c.ai_action_items, c.ai_key_topics, c.ai_confidence,
    c.communication_count, c.channel_breakdown,
    c.first_activity_at, c.last_activity_at,
    c.created_at, c.updated_at
FROM conversations c
WHERE c.archived_at IS NULL;
```

### 6.2 Cross-Entity Query Examples

```sql
-- All conversations associated with a specific project
SELECT c.subject, c.ai_status, c.ai_summary, c.is_aggregate
FROM conversations c
JOIN conversation_projects cp ON c.id = cp.conversation_id
WHERE cp.project_id = 'prj_01HX7...'
ORDER BY c.last_activity_at DESC;

-- All child conversations within an aggregate
SELECT child.subject, child.ai_status, child.last_activity_at
FROM conversations child
JOIN conversation_members cm ON child.id = cm.child_conversation_id
WHERE cm.parent_conversation_id = 'cvr_01HX7...'
ORDER BY child.last_activity_at DESC;

-- Derived participant list for a conversation
SELECT DISTINCT cp.contact_id, con.display_name
FROM communications c
JOIN communication_participants cp ON cp.communication_id = c.id
JOIN contacts con ON con.id = cp.contact_id
WHERE c.conversation_id = 'cvr_01HX8A...'
  AND c.archived_at IS NULL;

-- All communications in a project's conversations
SELECT comm.timestamp, comm.channel, comm.subject, comm.body_preview
FROM communications comm
JOIN conversations c ON comm.conversation_id = c.id
JOIN conversation_projects cp ON c.id = cp.conversation_id
WHERE cp.project_id = 'prj_01HX7...'
ORDER BY comm.timestamp DESC;
```

---

## 7. API Design

### 7.1 Conversation CRUD API

| Endpoint | Method | Description |
|---|---|---|
| `/api/v1/conversations` | GET | List conversations (paginated, filterable, sortable) |
| `/api/v1/conversations` | POST | Create a conversation |
| `/api/v1/conversations/{id}` | GET | Get conversation with communications and participants |
| `/api/v1/conversations/{id}` | PATCH | Update conversation fields |
| `/api/v1/conversations/{id}/archive` | POST | Archive a conversation |
| `/api/v1/conversations/{id}/history` | GET | Get event history |

### 7.2 Conversation Intelligence API

| Endpoint | Method | Description |
|---|---|---|
| `/api/v1/conversations/{id}/summarize` | POST | Trigger AI summarization refresh |
| `/api/v1/conversations/{id}/communications` | GET | List communications in chronological timeline |
| `/api/v1/conversations/{id}/participants` | GET | Derived participant list |
| `/api/v1/conversations/{id}/segments` | GET | List segments referencing this conversation |

### 7.3 Conversation Membership API

| Endpoint | Method | Description |
|---|---|---|
| `/api/v1/conversations/{id}/members` | GET | List child Conversations (aggregate only) |
| `/api/v1/conversations/{id}/members` | POST | Add child to aggregate (acyclic check) |
| `/api/v1/conversations/{id}/members/{child_id}` | DELETE | Remove child from aggregate |
| `/api/v1/conversations/{id}/parents` | GET | List aggregates this conversation belongs to |

### 7.4 Conversation Entity Association API

| Endpoint | Method | Description |
|---|---|---|
| `/api/v1/conversations/{id}/relations` | GET | List all entity associations |
| `/api/v1/conversations/{id}/relations/{slug}` | GET | List associations for a specific Relation Type |
| `/api/v1/conversations/{id}/relations/{slug}` | POST | Add an entity association |
| `/api/v1/conversations/{id}/relations/{slug}/{target_id}` | DELETE | Remove an entity association |

### 7.5 Review Workflow API

| Endpoint | Method | Description |
|---|---|---|
| `/api/v1/review/pending` | GET | Get pending items (unassigned + low confidence) |
| `/api/v1/review/assign` | POST | Batch assign communications to conversations |
| `/api/v1/review/stats` | GET | Get review statistics (pending count, correction rate) |

---

## 8. Decisions to Be Added by Claude Code

- **Denormalized count update strategy:** Application-level cascade vs. database trigger for aggregate roll-up computation.
- **Acyclic check performance:** For deeply nested aggregates, whether to cache ancestry or walk on every insert.
- **AI summary fan-out batching:** Whether to batch fan-out re-summarization or process immediately on child change.
- **system_status transition mechanism:** Scheduled job vs. on-access lazy evaluation for stale/closed detection.
- **Segment offset stability:** How character offsets are handled when content_clean is re-processed (offsets may shift).
- **conversation_members vs. Relation Type:** Whether to migrate the junction table to a standard Relation Type in a future refactor.

---

## 9. PoC Implementation Decisions (Schema v20, 2026-07-07; §9.8–9.14 schema v34, 10-22-26; §9.15–9.18 schema v35, 10-23-26)

Write-back from the Conversation View implementation (`docs/conversation_view_implementation.md`, migration `poc/migrate_to_v20.py`). The PoC runs on SQLite; sections 2–7 above describe the target PostgreSQL design and are unchanged. This section records what the PoC actually built and where it diverges, so future sessions implement against reality.

### 9.1 conversation_members (implemented, differs from §3)

**Decision:** `(parent_conversation_id, child_conversation_id, position, created_at)` with composite PK, self-reference CHECK, and a single index on `child_conversation_id` (`idx_cm_child`).

**Rationale:** Parent-side lookups are served by the PK's leading column, so the §3 parent index is unnecessary in SQLite. `position` supports manual child ordering; `added_by` from §3 was dropped — no write endpoint exists yet, so attribution has nothing to record. Revisit when membership mutations land.

### 9.2 Entity associations use generic relationships tables (differs from §6.2)

**Decision:** No dedicated `conversation_projects`-style join tables. Associations ride the existing `relationships`/`relationship_types` tables, with four seeded system types: `CONVERSATION_PROJECT`, `CONVERSATION_COMPANY`, `CONVERSATION_CONTACT`, `CONVERSATION_EVENT` (ids `rt-conv-*`). The v20 migration widened the `relationship_types` CHECK constraints to admit `conversation` as a from-type and `conversation`/`project`/`event` as to-types.

**Rationale:** Reuses the established relationship engine and its UI instead of four new tables; the read path dispatches on `relationship_types.name` (`poc/web/routes/api.py`, association block of `conversation_full_api`). This partially answers §8's "conversation_members vs. Relation Type" question: associations went the Relation Type route; parent/child membership stayed a junction table because ordering (`position`) and aggregate semantics don't fit the relationship model.

### 9.3 Read API is two composite endpoints (differs from §7)

**Decision:** The PoC exposes read-only `GET /api/v1/conversations/{id}/preview` and `GET /api/v1/conversations/{id}/full` composites (plus the legacy `GET /conversations/{id}`), each returning the entire card payload — children, associations, participants, timeline — in one response. The §7 CRUD/membership/segment/history surface is not implemented.

**Rationale:** The view feature only needs reads, and one round-trip per card render beats the chatty per-resource API for the SQLite PoC. `child_count` per child is a correlated subquery on `conversation_members`; each child's `latest_communication` is a per-child `LIMIT 1` query — acceptable at PoC scale, revisit before production.

### 9.4 Column-name and model divergences from §2

Implemented `conversations` uses `status` (not `system_status`), `ai_topics` (not `ai_key_topics`), `ai_summarized_at` (not `ai_last_processed_at`), `customer_id` (not `tenant_id`), `ai_confidence REAL` (not NUMERIC(3,2)); no `archived_at`. It also carries PoC-only columns (`triage_result`, `dismissed*`, `message_count`, `topic_id`, both `title` and `subject`). Communication membership is the `conversation_communications` junction (`is_primary`, `assignment_source`), not a `communications.conversation_id` FK. Naming hazard: the pre-existing `event_conversations` table is calendar-event linkage, unrelated to §5 event sourcing.

### 9.5 HTML column compatibility fallback

**Decision:** `_comm_html_col()` (`poc/web/routes/api.py`) probes `PRAGMA table_info(communications)` per request and selects `cleaned_html` (v18+) or `body_html` (pre-v18) for timeline content.

**Rationale:** Lets one build serve both pre- and post-v18 production databases during rollout; cheap (single PRAGMA on an open connection).

### 9.6 Splitter persistence is client-side

**Decision:** Per-conversation splitter position is stored in browser `localStorage` (`conv-splitter-{id}`), not server-side user settings.

**Constraint:** "Persists across sessions" holds per-browser, not per-account. Migrate to user settings if cross-device continuity is required.

### 9.7 Not implemented (unchanged open items)

Segments (§4), event sourcing (§5), virtual schema (§6.1), the §7 write endpoints other than §9.13, and the §8 decisions on count roll-up, acyclic checking, fan-out batching, and the timed stale/close transitions — the last is deferred as CONV-DN-09 (§9.14); `stale_after_days`/`closed_after_days` remain display-only.

### 9.8 Done is a value of `status` (schema v34)

**Decision:** The user-marked Done state is stored as `status = 'done'` in the existing `conversations.status` column, alongside `active` and the reserved `stale`. The Base PRD V1.0 value name `closed` is retired. Four audit columns are added: `done_at`, `done_by` (user reference), `reopened_at`, `reopened_reason` (`inbound` | `user`). Migration `poc/migrate_to_v34.py`; fresh-database DDL in `poc/database.py`.

**Rationale:** One column, one word, stored and displayed the same. The grid's Status column, the filter builder, saved-view filter values and exports all show the raw value, so a stored `closed` labelled "Done" would leak on every one of those surfaces. "closed" is already the AI Status vocabulary and the triage statistics endpoint already uses "closed" to mean dismissed.

**Alternatives Rejected:** (a) Store `closed`, label it Done — a value-to-label map on every surface, and three meanings of "closed". (b) Reuse the `dismissed*` columns — they already mean "emptied by a communications-grid archive" (`api_workflows.communications_archive_api`), the summarizer and assign picker skip them, and nothing clears them. (c) Separate `done_at`/`done_by` with `status` untouched — a fourth status dimension against the PRD's three.

**Constraints/Tradeoffs:** `closed_after_days` keeps its name; it is display-only and is renamed only if CONV-DN-09 makes it live. The `status` column still does double duty against the Base PRD §1.4, which lists a separate record-lifecycle Status (`active` | `archived`); conversation archive is unbuilt, so `archived` is reserved and the collision is recorded, not resolved.

**Decided by:** Doug, 10-22-26 (decision 1 of the Done-state session).

### 9.9 One link helper, three callers

**Decision:** `poc/conversation_links.py` owns `link_communications(conn, conversation_id, communication_ids, *, assignment_source, reviewed, now)`. It inserts the `conversation_communications` rows (INSERT OR IGNORE), recomputes `communication_count`, `first_activity_at`, `last_activity_at`, `first_message_at`, `last_message_at` from the linked set, clears `ai_summarized_at`, and if the conversation is `done` and any newly linked communication is inbound, sets `status = 'active'`, `reopened_at`, `reopened_reason = 'inbound'` and clears `done_at`/`done_by`. Callers: `sync._store_thread` (existing-conversation branch), `outbound` (composed message), `api_workflows.communications_assign_api` (manual). The same module owns `mark_done(conn, ids, user_id, now)` and `reopen(conn, ids, user_id, now)`.

**Rationale:** Before v10.44 the three join points each did a different subset: sync refreshed counts, activity and the summary stamp; outbound refreshed counts and last activity only; manual assign touched nothing on the conversation. Reactivation needs one rule at all three, and one function is the only way to keep it one rule.

**Constraints/Tradeoffs:** Two behaviors change beyond Done itself. A composed outbound message now clears `ai_summarized_at`, so the user's own sends queue a fresh summary (Base PRD §6.4 "Summaries"). Manual assignment now recomputes counts and activity, which the Base PRD §8.4 of the Communication entity always required. Both are intended.

**Decided by:** Claude Code, 10-22-26; approved as decision 2's mechanism.

### 9.10 Reactivation is inbound-only, read from `communications.direction`

**Decision:** A newly linked communication reopens a done conversation only when `direction = 'inbound'`. Outbound never reopens. No sender-pattern check is applied: an automated sender already in the thread reopens the conversation.

**Rationale:** The value of Done is trust that nothing needing an answer is hidden. A rule that could bury a human reply from a new address (the literal "anyone already in the conversation" reading) breaks that trust once and is never trusted again. Excluding the user's own sends matches how a mail client treats an archived thread. `direction` is populated on every row of the live database (10,581 inbound, 1,535 outbound on 10-22-26).

**Alternatives Rejected:** Any communication reopens (Base PRD V1.0) — the user's courtesy sign-off reopens the conversation they just finished. Known-participant-only — silently ignores a new participant's reply.

**Constraints/Tradeoffs:** Automated confirmations reopen. The mail rule layer (MAIL-46) can exclude them later without touching this rule.

**Decided by:** Doug, 10-22-26 (decision 2).

### 9.11 Default-view exclusion lives in the query engine

**Decision:** `views/engine.execute_view` adds `conv.status != 'done'` for the conversation entity when no filter in the merged list (saved view filters plus quick filters, as assembled by `GET /api/v1/views/{id}/data`) has `field_key == 'status'`. The registry's `status` field becomes a select with options `active`, `stale`, `done`; `done_at` and `reopened_at` are added as optional datetime columns.

**Rationale:** The grid must be cleaned without the user configuring it. A saved filter on the default view would conflict with the Done quick chip (status != done AND status = done → empty) because quick filters are appended, not substituted. The engine already carries one such rule (archived communications), so the pattern exists.

**Constraints/Tradeoffs:** A rule the filter builder does not display. The front end shows a one-line note under the quick chips. Footer counts drop for anyone used to the total.

**Decided by:** Doug, 10-22-26 (decision 4).

### 9.12 Audit is four columns, last occurrence only

**Decision:** `done_at`, `done_by`, `reopened_at`, `reopened_reason` on the conversation row, overwritten on each transition. `updated_by` is also set on Mark Done and Reopen. No event log.

**Rationale:** A reopen the user did not do must be explainable from the Metadata card. Event sourcing (§5) is unbuilt and this feature does not justify starting it.

**Constraints/Tradeoffs:** A conversation done and reopened three times keeps only the latest pair. Full history waits for §5.

**Decided by:** Doug, 10-22-26 (decision 6).

### 9.13 Mark Done and Reopen endpoints

**Decision:** `POST /api/v1/conversations/done` and `POST /api/v1/conversations/reopen`, body `{"ids": [...]}`, in `poc/web/routes/api_workflows.py`. Each checks tenant ownership per id (`_owned_conversation`), applies the transition only where it changes state, and returns `{done|reopened, skipped_unchanged, skipped_foreign}`. Single-row actions send one id. The preview and full payloads gain `done_at`, `done_by_name`, `reopened_at`, `reopened_reason`.

**Rationale:** One bulk-capable endpoint per transition serves the context menu, the toolbar, the cards and the Undo link alike, and matches the existing communications bulk endpoints in shape.

**Decided by:** Claude Code, 10-22-26.

### 9.14 Deferred: dismissed clean-up

**CONV-DN-09 (timers)** was decided on 10-23-26 and built in v10.45; see §9.15–9.18.

**CONV-DN-10 (dismissed):** Hide `dismissed = 1` rows in the grid the way archived communications are hidden, and have `communications_archive_api` recompute counts and activity through §9.9's helper after unlinking. Also note for a future unarchive: the grid archive path deletes the `conversation_communications` row, so restoring membership needs a different record than the Communication Base PRD assumes; the mail client's `is_archived` means trashed or deleted at the provider and keeps the link (Mail Client TDD D-22).

### 9.15 A timed close writes `done`, with `done_reason` (schema v35)

**Decision:** The timer pass sets `status = 'done'`, `done_at`, `done_by = NULL`, `done_reason = 'timer'`. Mark Done sets `done_reason = 'user'`. Reopen clears all four. Migration `poc/migrate_to_v35.py` adds `done_reason` and stamps `user` on existing done rows that carry a `done_by`.

**Rationale:** Everything built for done in v10.44 (engine rule, chips, menus, cards, reopen on inbound, Undo) works unchanged. The two meanings of done are told apart on the record by `done_reason`, and in queries by `done_by IS NULL`.

**Alternatives Rejected:** Stale only (grid never cleans itself). A third hidden value such as `expired` (every done surface would need a second value).

**Decided by:** Doug, 10-23-26 (timer decision 1).

### 9.16 Thresholds are system settings with a per-conversation override

**Decision:** Three system settings in `poc/settings.py` and on the Settings page: `conversation_stale_days` (default 14), `conversation_done_days` (default 30), `conversation_timers_enabled` (default true). The settings API clamps the two day values to 1–365 and raises `conversation_done_days` to `conversation_stale_days` when it is set lower. `conversations.stale_after_days` / `closed_after_days` become overrides: NULL means the setting applies, and the effective value is `COALESCE(row, setting)`. The v35 migration blanks the copies of the old column defaults (14 / 30) that every row carried, so a value left standing is a genuine override; the fresh-database DDL drops the column defaults.

**Rationale:** A threshold nobody can reach is not configurable; before v10.45 the only way to change 30 days was an update across every row. The Base PRD's design decision that conversations have different cadences is kept through the override. Per-conversation editing stays in the deferred full View write path (View Sub-PRD V1.4).

**Constraints/Tradeoffs:** The full payload now carries `stale_after_days_default` and `closed_after_days_default` beside the override columns so the Metadata card can say "(default)". A row whose override happens to equal the old default was blanked by the migration; on the live database every row held exactly 14 / 30, so nothing was lost.

**Decided by:** Doug, 10-23-26 (timer decision 2).

### 9.17 The timer pass: where, how often, and what it touches

**Decision:** `poc/conversation_lifecycle.py` owns `run_lifecycle_pass(now_iso=None)`. `SyncScheduler.tick` calls it beside the snooze-return pass, throttled to once per `LIFECYCLE_INTERVAL_SECONDS` (3,600) per process, with the first run on the first tick after start. The pass selects `status IN ('active', 'stale') AND dismissed = 0` and groups by `customer_id` to read that tenant's settings once. Silence is measured from `MAX(last_activity_at, reopened_at WHERE reopened_reason = 'user')`; rows with no `last_activity_at` are skipped. Transitions: silence ≥ done threshold → `done` (`timer`); else silence ≥ stale threshold → `stale`; else `stale` → `active`. Done rows are never read. The pass returns `{checked, stale, reactivated, done}` and logs when anything moved.

**Rationale:** The tick already carries time-based passes (queued send, snooze return) and runs whether or not mail arrived, which the post-sync pass does not. An hour is far finer than the day-scale thresholds and costs one query over ~2,000 rows. Measuring from a user Reopen is what stops the timer from undoing the user an hour later; measuring from `last_activity_at` alone would.

**Constraints/Tradeoffs:** The pass runs on the scheduler thread, so it must stay cheap; at ten times today's row count it is still a single indexed scan. A second server process would run its own pass; the transitions are idempotent, so that is harmless.

**Decided by:** Claude Code, 10-23-26, announced with the two decisions.

### 9.18 Stale clears on any new communication; done still reopens on inbound only

**Decision:** `link_communications` (§9.9) now also sets `stale → active` whenever it links anything, inbound or outbound, without touching the reopen audit pair. The `done → active` rule of §9.10 is unchanged.

**Rationale:** Stale measures silence, so the user's own message ends it. Done measures the user's intent, so only the other side's message ends it.

**Decided by:** Claude Code, 10-23-26, announced with the two decisions.

---

## 10. Change Log

| Rev | Date (MM-DD-YY HH:MM) | Author | Change |
|---|---|---|---|
| 1.3 | 10-23-26 01:12 | Claude (Claude Code) | §9.14 narrowed to the dismissed clean-up; §9.15–9.18 timer decisions (done_reason, settings with override, hourly pass and silence clock, stale clears on any activity). Schema v35, release v10.45. |
| 1.2 | 10-22-26 22:58 | Claude (Claude Code) | §9.8–9.14: Done state decisions (status value, link helper, inbound-only reactivation, engine exclusion, audit columns, endpoints, deferred items). Schema v34, release v10.44. |
| 1.1 | 07-07-26 | Claude (Claude Code) | §9 PoC implementation write-back, schema v20. |
| 1.0 | 02-23-26 | Doug (Claude.ai) | Original document. |
