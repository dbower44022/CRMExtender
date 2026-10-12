# Kickoff prompt — Conversation "Done" state

**Last Updated:** 10-11-26 21:13 · Revision 1.0
**Purpose:** Paste the block below as the first message of a new Claude Code session rooted in `CRM_Extender/CRMExtender`. It briefs the session to design, and after approval build, a way to mark conversations done and to reopen them automatically when mail arrives.

---

Operating mode: ARCHITECTURE. Read `/home/doug/.claude/CLAUDE.md` and this repository's `PRDs/prd-methodology-guide.md` before anything else, and confirm which CLAUDE.md you read. You propose; I approve before any code or PRD text changes. Open every reply with the machine time.

## Goal

Give a user a way to mark a conversation **done** so the conversations grid can be cleaned of finished threads, and make a done conversation **reactivate itself** when a new email arrives in it from anyone who is part of that conversation.

## What already exists (verified 10-11-26, schema v32, release v10.39)

- `PRDs/conversation-entity-base-prd.md` §6 already specifies a system status `active | stale | closed` with `stale_after_days` (default 14) and `closed_after_days` (default 30), a manual close by the user, and the rule "any state reopens to `active` when a new communication arrives". The columns exist on `conversations` (`status`, `stale_after_days`, `closed_after_days`). **Nothing implements the transitions or the manual close.** Every one of the 2,174 live conversations has `status = 'active'`.
- A separate **AI status** (`ai_status`: open 1,040 / closed 1,009 / uncertain 125) is set by the summarizer and means "the topic reads as resolved". It is not a user mark and must stay independent (§6.2).
- Unused `dismissed`, `dismissed_reason`, `dismissed_at`, `dismissed_by` columns exist from the triage design. All zero. Decide whether they are the right home for "done" or a different concept to leave alone.
- The conversations grid (`poc/views/registry.py`, entity `conversation`) filters on `status` and `ai_status`; the quick filters in `frontend/src/components/grid/QuickFilters.tsx` are Open / Closed / Uncertain on `ai_status`.
- New communications join a conversation in `poc/sync.py` `_store_thread` (mail sync) and through the outbound path when the user sends. That is where reactivation has to happen.
- The conversation full view's write path (status edits, thresholds) is deferred; see the V1.4 note at the top of `PRDs/conversation-view-prd.md`. The grid has no bulk-edit action for conversations.
- Mail Client threads (`/app/mail`) are a separate surface over communications and are not conversations; snooze and "awaiting reply" live there (`PRDs/mail-client-prd.md`, TDD D-44, D-46). Keep "done" on the conversation entity.

## Decisions to bring me (use the consequential decision template from CLAUDE.md for each)

1. **Name and home.** User-facing "Done" versus the specified `closed` system status, and whether the mark is the existing `status` column, the `dismissed` fields, or something new. Show what the user sees in the grid and the full view under each option.
2. **Reactivation rule.** The specification says any new communication reopens. I asked for "an email from anyone in the conversation". Lay out the difference: the user's own sent message, a newsletter or automated sender already in the thread, a new participant replying into the thread. Recommend one.
3. **Timers.** Whether to implement the specified auto-stale and auto-close now, or ship manual done only and leave the timers as a later task.
4. **Default view.** Whether "All Conversations" hides done conversations, shows them greyed, or shows them unchanged with a Done quick filter.
5. **Where the user does it.** Row context menu, bulk from a selection, the full view, a keyboard key, or some set of these.
6. **Audit.** Whether to record who marked done and when, and when it reopened, and whether reopening should queue a fresh summary.

Present all six in one reply and stop. Do not write code or PRD text until I have answered.

## After approval

Write the amendment into `PRDs/conversation-entity-base-prd.md` (bump version, change log) and the decisions into `PRDs/conversation-entity-tdd.md` §9, add a task list with test IDs, then build the approved list in full: migration (next schema version; register it in `cmd_migrate` and bump `LATEST_VERSION`), backend, grid and view changes, tests (`.venv/bin/python -m pytest tests/`, `npm run lint`, `npx tsc --noEmit`, `npx vitest run`, `npm run build` with `frontend/dist` committed), VERSION bump, one commit per release. Report done versus remaining against the task list. Run any live-database migration only after telling me, with the backup path.
