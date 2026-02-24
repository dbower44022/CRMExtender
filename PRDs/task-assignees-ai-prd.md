# Task — Assignees, Behaviors & AI Intelligence Sub-PRD

**Version:** 1.0
**Last Updated:** 2026-02-23
**Status:** Draft
**Entity Base PRD:** [task-entity-base-prd.md]
**Referenced Entity PRDs:** [conversation-entity-base-prd.md] (AI extraction source), [conversation-ai-intelligence-prd.md] (intelligence pipeline)

---

## 1. Overview

### 1.1 Purpose

This sub-PRD defines the people side of tasks and the automated behaviors that keep tasks actionable: the Task→User relation type with assignee/reviewer/watcher roles, the overdue detection background job, due date reminder scheduling, and AI action-item extraction from Conversations. These features share the theme of "who does the work, when is it due, and how do tasks get created automatically."

### 1.2 Preconditions

- Task entity operational with status category enforcement.
- task_user_roles junction table provisioned.
- Conversation intelligence pipeline operational (for AI extraction).
- Background job infrastructure available (for overdue detection).

---

## 2. Context

### 2.1 Relevant Fields

| Field | Role in This Action |
|---|---|
| due_date | Drives overdue detection and reminder scheduling. |
| is_overdue | Managed by background job. Set when due_date past and status open. |
| status_category | Overdue applies only to not_started/active. Cleared on done/cancelled. |
| source | Tracks origin: manual, ai_extracted, recurrence_generated, api. |
| completed_at | Cleared overdue on completion. |

### 2.2 Cross-Entity Context

- **Conversation AI Intelligence Sub-PRD:** Intelligence pipeline extracts action items from communications. This sub-PRD defines how those extractions become Task records.
- **Hierarchy Sub-PRD:** Recurrence generation copies assignees from completed instance.

---

## 3. Key Processes

### KP-1: Assigning Users to a Task

**Trigger:** User adds participants from task detail page or during creation.

**Step 1 — Select user:** User searches workspace members.

**Step 2 — Select role:** assignee (default), reviewer, or watcher.

**Step 3 — Create relation:** task_user_roles row inserted.

**Step 4 — Notification:** (Pending Notifications PRD) Assignee/reviewer notified of assignment.

### KP-2: Overdue Detection

**Trigger:** Periodic background job (configurable frequency, default: every 15 minutes).

**Step 1 — Find candidates:** Query tasks WHERE due_date < NOW() AND status_category IN ('not_started', 'active') AND is_overdue = false AND archived_at IS NULL.

**Step 2 — Set overdue:** UPDATE is_overdue = true on candidates.

**Step 3 — Clear resolved:** Query tasks WHERE is_overdue = true AND (status_category IN ('done', 'cancelled') OR due_date >= NOW() OR archived_at IS NOT NULL). UPDATE is_overdue = false.

**Step 4 — Notify:** (Pending Notifications PRD) Notify assignees of newly overdue tasks.

### KP-3: Due Date Reminder Scheduling

**Trigger:** Task created with due_date, or due_date changed.

**Step 1 — Clear existing reminders:** Remove any scheduled reminder events for this task.

**Step 2 — Schedule new reminders:** Create reminder events at configurable intervals before due_date (default: 24 hours before, 1 hour before).

**Step 3 — Fire reminder:** When reminder time arrives, notify assignees.

**Step 4 — Clear on completion:** If task completed or due_date removed, cancel scheduled reminders.

### KP-4: AI Action-Item Extraction

**Trigger:** Conversation intelligence pipeline extracts action items from communications.

**Step 1 — Receive extraction:** Intelligence pipeline provides action text, optional assignee hint, optional urgency signal.

**Step 2 — Create task:** New task with title from action text, source = 'ai_extracted', status = default (to_do).

**Step 3 — Link to conversation:** Create task_entities row linking to originating Conversation.

**Step 4 — Infer assignee:** If extraction includes participant reference, attempt to match to workspace user. Add as assignee if matched.

**Step 5 — Await review:** AI-extracted tasks are surfaced for user review/confirmation. No special draft state — they appear as normal tasks with source = 'ai_extracted' filterable in views.

---

## 4. Task→User Relation Type (Assignees)

**Supports processes:** KP-1

### 4.1 Relation Type Definition

| Property | Value |
|---|---|
| Slug | `task_user_participation` |
| Source | `tasks` |
| Target | `users` |
| Cardinality | Many-to-many |
| Directionality | Bidirectional |
| Source Field Label | Assignees |
| Target Field Label | Tasks |
| Has Metadata | true (role) |
| Neo4j Sync | true |
| Cascade | CASCADE (delete task → remove links) |

### 4.2 Role Definitions

| Role | Description | Notification Triggers |
|---|---|---|
| `assignee` | Responsible for completing the task. Multiple allowed. | Task creation, status changes, due date changes, comments. |
| `reviewer` | Responsible for review/approval before done. | Status transitions to review, completion. |
| `watcher` | Observes progress without responsibility. | Status changes, completion. |

### 4.3 Uniqueness Rules

- UNIQUE per (task_id, user_id, role): a user holds each role once per task.
- Multiple roles per user allowed: same user can be assignee + reviewer (separate rows).
- Multiple assignees per task allowed: collaborative work.

**Tasks:**

- [ ] TABI-01: Implement task_user_participation relation type registration
- [ ] TABI-02: Implement assignee add with role selection
- [ ] TABI-03: Implement assignee remove by user + role
- [ ] TABI-04: Implement "my tasks" query (tasks assigned to current user)
- [ ] TABI-05: Implement role-based filtering in task views

**Tests:**

- [ ] TABI-T01: Test assignee added with default role = 'assignee'
- [ ] TABI-T02: Test user can hold multiple roles on same task
- [ ] TABI-T03: Test duplicate role assignment rejected (UNIQUE constraint)
- [ ] TABI-T04: Test CASCADE removes assignments when task deleted
- [ ] TABI-T05: Test "my tasks" returns tasks where user is assignee

---

## 5. Overdue Detection

**Supports processes:** KP-2

### 5.1 Requirements

Background job detects overdue tasks and maintains the `is_overdue` flag:

- **Set overdue:** due_date < NOW() AND status_category IN ('not_started', 'active') AND archived_at IS NULL.
- **Clear overdue:** Task completed (→ done), cancelled, archived, or due_date extended past NOW().
- **Index:** `idx_tasks_overdue_candidates` supports efficient candidate queries.
- **Frequency:** Configurable (default: every 15 minutes).

### 5.2 Overdue in Status Transitions

| Transition | is_overdue |
|---|---|
| Any → done | Clear (false) |
| Any → cancelled | Clear (false) |
| done → active (reopened) | Re-evaluate based on due_date |
| due_date extended past NOW() | Clear (false) |

**Tasks:**

- [ ] TABI-06: Implement overdue detection background job
- [ ] TABI-07: Implement is_overdue flag set on overdue candidates
- [ ] TABI-08: Implement is_overdue flag clear on completion/cancellation/archive
- [ ] TABI-09: Implement is_overdue clear on due_date extension
- [ ] TABI-10: Implement overdue re-evaluation on task reopen

**Tests:**

- [ ] TABI-T06: Test overdue flag set when due_date past and status open
- [ ] TABI-T07: Test overdue flag NOT set when status = done
- [ ] TABI-T08: Test overdue flag cleared on completion
- [ ] TABI-T09: Test overdue flag cleared on due_date extension
- [ ] TABI-T10: Test overdue flag cleared on archive
- [ ] TABI-T11: Test overdue re-evaluation on reopen with past due_date

---

## 6. Due Date Reminder Scheduling

**Supports processes:** KP-3

### 6.1 Requirements

When a task has a due_date, schedule reminder notifications:

- Default intervals: 24 hours before, 1 hour before.
- Clear reminders when: task completed, due_date removed, due_date changed (reschedule).
- Recipients: all users with assignee or reviewer role.
- Depends on Notifications subsystem (PRD pending).

### 6.2 Minimal Contract

Until the Notifications PRD exists, reminders are modeled as scheduled events:

| Field | Value |
|---|---|
| task_id | Reference to task |
| reminder_time | TIMESTAMPTZ when reminder should fire |
| status | `pending`, `sent`, `cancelled` |

**Tasks:**

- [ ] TABI-11: Implement reminder scheduling on task create with due_date
- [ ] TABI-12: Implement reminder rescheduling on due_date change
- [ ] TABI-13: Implement reminder cancellation on completion/due_date removal
- [ ] TABI-14: Implement reminder recipient resolution (assignees + reviewers)

**Tests:**

- [ ] TABI-T12: Test reminders scheduled at correct intervals before due_date
- [ ] TABI-T13: Test reminders rescheduled when due_date changes
- [ ] TABI-T14: Test reminders cancelled on task completion
- [ ] TABI-T15: Test reminders cancelled when due_date removed

---

## 7. AI Action-Item Extraction

**Supports processes:** KP-4

### 7.1 Requirements

The Conversation intelligence pipeline can auto-create tasks from extracted action items:

- **Source tracking:** `source = 'ai_extracted'` distinguishes from manual tasks.
- **Auto-link:** Task linked to originating Conversation via task_entities.
- **Assignee inference:** If extraction references a participant, attempt match to workspace user. Add as assignee if matched. If not matched, skip (don't create stub users).
- **Review workflow:** No special draft state. AI-extracted tasks appear as normal tasks filterable by source = 'ai_extracted'. Users can edit, reassign, or archive.

### 7.2 Extraction Input Contract

From Conversation intelligence pipeline:

| Field | Type | Description |
|---|---|---|
| action_text | Text | Extracted action item text → becomes task title |
| conversation_id | Text | Originating conversation → entity attachment |
| participant_hint | Text (optional) | Name or email of implied assignee |
| urgency_signal | Text (optional) | Urgency indicator → maps to priority |
| communication_id | Text (optional) | Specific communication containing the action item |

### 7.3 Priority Mapping

| Urgency Signal | Task Priority |
|---|---|
| `high` or `urgent` | `high` |
| `medium` | `medium` |
| None or unrecognized | `none` (default) |

AI never sets `urgent` priority — only users set that level.

**Tasks:**

- [ ] TABI-15: Implement AI task creation from extraction input
- [ ] TABI-16: Implement source = 'ai_extracted' tracking
- [ ] TABI-17: Implement auto-link to originating conversation
- [ ] TABI-18: Implement assignee inference from participant hint
- [ ] TABI-19: Implement priority mapping from urgency signal
- [ ] TABI-20: Implement AI-extracted task filtering in views

**Tests:**

- [ ] TABI-T16: Test AI extraction creates task with correct title
- [ ] TABI-T17: Test AI task linked to originating conversation
- [ ] TABI-T18: Test assignee inference matches workspace user
- [ ] TABI-T19: Test unmatched participant hint skipped (no stub user)
- [ ] TABI-T20: Test urgency signal maps to correct priority
- [ ] TABI-T21: Test AI never sets priority = 'urgent'
- [ ] TABI-T22: Test source = 'ai_extracted' filterable in views
