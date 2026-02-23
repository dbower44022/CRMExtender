# Note — Entity Base PRD

**Version:** 1.0
**Last Updated:** 2026-02-23
**Status:** Draft
**Product PRD:** [CRMExtender Product PRD]

---

## 1. Entity Definition

### 1.1 Purpose

Note is the free-form knowledge capture layer of CRMExtender. While structured fields capture typed data and communication intelligence tracks message-level interactions, Notes answer "What did the user observe, decide, or want to remember about this entity?" Notes provide the unstructured counterpart to structured CRM data — meeting observations, strategic context, internal commentary, and shared knowledge that doesn't fit into predefined fields.

Notes are first-class entities with rich text formatting, full revision history, multi-entity attachment, @mentions for cross-referencing, file attachments, and full-text search across the entire workspace.

### 1.2 Design Goals

- **System object type** — Full participation in Views, Data Sources, event sourcing, field registry, permissions. Specialized behaviors (revision management, FTS sync, mention extraction) registered with the framework.
- **Universal attachment** — Notes attach to any entity type (system or custom) through the Universal Attachment Relation pattern. A single note can be linked to multiple entities across different types.
- **Behavior-managed content** — Rich text content stored as JSONB + HTML + plain text, managed by the revision behavior rather than the standard field update pipeline. Preserves append-only revision model.
- **Private by default** — Notes visible only to creator unless explicitly shared. Hard privacy boundary — even admins cannot see other users' private notes.
- **Editor-agnostic** — Content storage contract defined independently of rich text editor choice.

### 1.3 Performance Targets

| Metric | Target |
|---|---|
| Note list load (entity detail, 20 notes) | < 100ms |
| Note save with revision | < 200ms |
| Full-text search (95th percentile) | < 200ms |
| Mention autocomplete | < 100ms |
| Attachment upload (< 10MB) | < 2s |

### 1.4 Core Fields

| Field | Description | Required | Editable | Sortable | Filterable | Valid Values / Rules |
|---|---|---|---|---|---|---|
| ID | Unique identifier. Prefixed ULID with `not_` prefix. | Yes | System | No | Yes | Prefixed ULID |
| Title | Optional note title. When NULL, UI shows truncated content_text preview. | No | Direct | Yes | Yes | Free text |
| Visibility | Access control level. | Yes | Direct | No | Yes | `private`, `shared`. Default: private. |
| Content JSON | Editor-native document format. Source of truth for re-editing. **Behavior-managed, not in field registry.** | Yes | Via revision behavior | No | No | JSONB |
| Content HTML | Pre-rendered HTML. Sanitized before storage. **Behavior-managed.** | Yes | Via revision behavior | No | No | Sanitized HTML |
| Content Text | Plain text extracted from HTML. For FTS and previews. **Behavior-managed.** | Yes | Computed | No | No (use FTS) | Plain text |
| Current Revision ID | Points to latest note_revisions row. | No | System | No | No | Reference to revision |
| Revision Count | Count of content revisions. | No | Computed | Yes | Yes | Positive integer. Default: 1. |
| Status | Record lifecycle. | Yes, defaults to active | System | Yes | Yes | `active`, `archived` |
| Created By | User who created the note. | Yes | System | No | Yes | Reference to User |
| Created At | Record creation timestamp. | Yes | System | Yes | Yes | Timestamp |
| Updated At | Last modification timestamp. | Yes | System | Yes | Yes | Timestamp |

### 1.5 Registered Behaviors

| Behavior | Trigger | Description |
|---|---|---|
| Revision management | On content save | Creates new revision snapshot. Updates current_revision_id and revision_count. See Content & Revisions Sub-PRD. |
| FTS sync | On content save | search_vector auto-updates from title + content_text (stored generated column). |
| Mention extraction | On content save | Extracts @mentions from content_json, syncs to note_mentions table. See Attachments & Mentions Sub-PRD. |
| Orphan attachment cleanup | Scheduled background job | Removes uploaded files not linked to a saved note after 24h. See Attachments & Mentions Sub-PRD. |

---

## 2. Entity Relationships

### 2.1 Any Entity (Universal Attachment)

**Nature:** Many-to-many, via `note_entities` polymorphic junction table
**Ownership:** This entity
**Description:** Notes attach to any registered object type through the Universal Attachment Relation pattern. Junction table uses entity_type + entity_id columns. Includes is_pinned metadata for per-entity-link prioritization. A note must always have at least one entity link (API prevents removing the last link).

### 2.2 Revisions

**Nature:** One-to-many, owned
**Ownership:** This entity
**Description:** Append-only content history in note_revisions. Each revision stores full content_json and content_html snapshots. Current revision tracked by current_revision_id.

### 2.3 Attachments

**Nature:** One-to-many, owned
**Ownership:** This entity
**Description:** Uploaded files in note_attachments. Nullable note_id supports orphan uploads during editing. See Attachments & Mentions Sub-PRD.

### 2.4 Mentions

**Nature:** One-to-many, owned
**Ownership:** This entity
**Description:** Extracted @mentions in note_mentions. Synced on every content save. Enables reverse lookups ("notes mentioning contact X").

### 2.5 Documents

**Nature:** Many-to-many, via Documents universal attachment
**Ownership:** Documents PRD
**Description:** Documents can attach to Notes for supplementary files. Note inline attachments (images pasted into editor) remain tightly coupled to Notes and are NOT Document entities.

---

## 3. Universal Attachment Relation

### 3.1 Pattern

The Universal Attachment Relation was introduced by the Notes PRD and is reused by Documents and Tasks. It enables a source entity type to link to records of any type (`target = *`) through a polymorphic junction table.

| Attribute | Value |
|---|---|
| Relation type slug | `note_entity_attachment` |
| Source | `notes` |
| Target | `*` (any registered object type) |
| Cardinality | Many-to-many |
| Metadata | `is_pinned` (Boolean) |

### 3.2 How It Differs from Standard Relations

| Aspect | Standard Relation | Universal Attachment |
|---|---|---|
| Target | Specific object type | Wildcard (`*`) |
| Junction table | Typed FKs | entity_type + entity_id (polymorphic) |
| Referential integrity | Database FK constraints | Application-level checks |
| Auto-provisioning | Manual/system-defined | Automatic for new custom types |
| Neo4j sync | Typed edge | Generic edge (HAS_NOTE) with entity_type property |

### 3.3 Cascade & Consistency

- **Note deleted:** note_entities rows CASCADE delete (hard delete) or remain (soft delete/archive).
- **Linked entity deleted:** note_entities row retained as stale link. Background job cleans up or flags.
- **Last link removed:** API prevents removing last note_entities row — user must delete the note instead. (Exception: atomic move = remove + add.)
- **Custom object type archived:** Notes linked to archived types retain links. Accessible through other links or global search.

### 3.4 Framework Impact

Extensions required to Custom Objects relation type framework:

1. Relation type validation: accept `target_object_type = '*'` for system-defined types.
2. Junction table schema: `entity_type TEXT` + `entity_id TEXT` polymorphic columns.
3. Views integration: "Linked Entities" column type renders as mixed-type entity chips.
4. Data Sources: Universal attachment JOINs use entity_type filtering.
5. Neo4j sync: `HAS_NOTE` edges with entity_type property.

---

## 4. Visibility

### 4.1 Visibility Model

| Level | Who Can See | Usage |
|---|---|---|
| `private` (default) | Creator only | Personal observations, drafts, sensitive commentary |
| `shared` | Anyone who can see at least one linked entity | Team knowledge, meeting summaries, shared context |

### 4.2 Permission Rules

**Private notes:**
- Only created_by user can view, edit, or delete.
- Excluded from other users' entity note lists, search, API responses.
- Visible in creator's "My Notes" view.
- Admins cannot see other users' private notes (hard privacy boundary).

**Shared notes:**
- Visibility inherits from linked entities via Permissions PRD.
- Multi-entity: user can see note if they can see ANY linked entity (union visibility).
- Edit: creator + users with edit access to at least one linked entity.
- Delete: creator + workspace admins.

### 4.3 Multi-Entity Visibility

When a shared note is linked to entities with different scopes: User A can see Contact X but not Company Y. Note linked to both. User A can see the note (via Contact X). The Company Y link is visible but not clickable.

### 4.4 Transitions

| Transition | Behavior |
|---|---|
| Private → Shared | Note becomes visible to users who can see linked entities. visibility_changed event emitted. |
| Shared → Private | Note hidden from others. visibility_changed event emitted. |

---

## 5. Pinning

### 5.1 Model

Pinning is **per-entity-link**, not per-note. A note attached to both a Contact and a Company can be pinned on the Contact's list without affecting its position on the Company's list.

- `is_pinned` column on note_entities.
- `toggle_pin(note_id, entity_type, entity_id)` flips state for the specific link.
- Pinned notes sort before unpinned (index: idx_ne_pinned).
- `pin_toggled` event emitted.

### 5.2 UI Behavior

- Pin icon on note card (filled when pinned, outlined when unpinned).
- Pinned group at top, sorted by created_at DESC within group.
- Unpinned group below, sorted by updated_at DESC.

---

## 6. Lifecycle

| Status | Description |
|---|---|
| `active` | Normal operating state. Visible in views and search. |
| `archived` | Soft-deleted. All revisions and attachments retained. Excluded from default queries. Recoverable. |

---

## 7. Key Processes

### KP-1: Creating a Note

**Trigger:** User creates note from entity detail page or global "New Note" action.

**Step 1 — Content entry:** User writes in rich text editor. Optional title. Visibility toggle (default: private).

**Step 2 — Attachments:** Images pasted/dropped upload immediately to orphan storage. URLs inserted in content.

**Step 3 — Mentions:** @-triggered autocomplete inserts mention nodes.

**Step 4 — Save:** Client sends content_json + content_html + metadata. Server extracts content_text, sanitizes HTML, creates note + first revision. Links orphan attachments. Extracts mentions.

**Step 5 — Entity link:** Note linked to at least one entity (the context entity).

### KP-2: Editing a Note

**Trigger:** User edits existing note.

**Step 1 — Load:** Editor hydrated from content_json.

**Step 2 — Edit:** User modifies content.

**Step 3 — Save:** If content changed: new revision created (revision_number incremented), note's content fields updated. If only metadata changed (title, visibility): no new revision, standard event sourcing.

### KP-3: Browsing Notes on an Entity

**Trigger:** User views entity detail page, notes panel.

**Step 1 — List loads:** Notes filtered by entity link. Pinned first, then by updated_at.

**Step 2 — Visibility filtering:** Private notes of other users excluded.

**Step 3 — Preview:** Title + truncated content_text preview. Pin icon.

### KP-4: Searching Notes

**Trigger:** User searches from global notes search or entity-scoped search.

**Step 1 — Query:** FTS with tsvector. Title matches weighted higher than content.

**Step 2 — Results:** Ranked list with snippets (highlighted matches). Entity links shown.

**Step 3 — Visibility:** Private notes excluded unless created_by = current user.

### KP-5: Viewing Revision History

**Trigger:** User views revision list from note detail.

**Step 1 — List:** Shows revision number, revised_by, timestamp.

**Step 2 — View revision:** User selects a revision to view its full content_html.

### KP-6: Linking Note to Additional Entities

**Trigger:** User adds entity link from note detail.

**Step 1 — Select entity:** User picks entity type and record.

**Step 2 — Link created:** note_entities row inserted.

**Step 3 — Pin (optional):** User can pin the note on the new entity's list.

---

## 8. Action Catalog

### 8.1 Create Note

**Supports processes:** KP-1
**Trigger:** User creation or future AI generation.
**Outcome:** Note with first revision, entity link(s), attached files, extracted mentions.

### 8.2 Edit Note

**Supports processes:** KP-2
**Trigger:** User edits content or metadata.
**Outcome:** New revision (content change) or event-sourced update (metadata change).

### 8.3 Browse / Search Notes

**Supports processes:** KP-3, KP-4
**Trigger:** User navigation.
**Outcome:** Filtered, ranked note list with visibility enforcement.

### 8.4 View Revision History

**Supports processes:** KP-5
**Trigger:** User views revisions.
**Outcome:** Revision list with viewable full content snapshots.

### 8.5 Link / Unlink Entity

**Supports processes:** KP-6
**Trigger:** User manages entity links.
**Outcome:** Junction table updated. Last-link-removal prevented.

### 8.6 Archive / Restore

**Trigger:** User archives or restores.
**Outcome:** Soft-delete or recovery. Revisions and attachments retained.

### 8.7 Content, Revisions & Sanitization

**Summary:** Behavior-managed content architecture (JSON + HTML + text triple), editor requirements and mention node contract, full-snapshot revision history, content events vs. metadata events coexistence, HTML sanitization with server-side allowlists.
**Sub-PRD:** [note-content-revisions-prd.md]

### 8.8 Attachments, Mentions & Search

**Summary:** File attachment upload with orphan pattern, StorageBackend protocol, orphan cleanup, allowed MIME types. @Mention types, autocomplete, extraction/sync, stale handling. Full-text search with tsvector two-tier weighting, ranked results, snippets.
**Sub-PRD:** [note-attachments-mentions-prd.md]

---

## 9. Open Questions

1. **Universal Attachment in Custom Objects PRD?** Should the pattern be formalized there, or remain documented only here?
2. **Admin override for compliance?** Hard privacy boundary vs. legal discovery needs. Third visibility level or admin escape hatch?
3. **Entity transfer behavior?** Shared notes on transferred entities should stay accessible. Private notes of departing users need review.
4. **Rich text field type for custom objects?** Should content architecture generalize to a rich_text field type?
5. **Global search participation?** Dedicated FTS endpoint vs. federated global search spanning all entity types.
6. **AI-generated note revisions?** Should AI generation be a revision or a distinct source type?
7. **Mention resolution strategy?** Eager (resolve IDs on display, N+1 cost) vs. lazy (cached labels, stale risk)?
8. **Maximum entity links per note?** Unbounded vs. reasonable limit (e.g., 20)?

---

## 10. Design Decisions

### Why system object type?

Full participation in Views, Data Sources, event sourcing, Custom Objects framework. Consistent entity modeling.

### Why Universal Attachment (target = *)?

Enables attachment to all entity types without per-type definitions. No provisioning coupling. Pattern reusable for Tags, Activity Log, Bookmarks, Tasks.

### Why behavior-managed content?

Rich text documents don't map to typed field values. Revision model incompatible with field-level deltas. FTS provides better content discovery than field filters.

### Why both revisions and event sourcing?

Events for metadata audit trail (title, visibility, links, pins). Revisions for full content snapshots. Content events point to revisions rather than storing content inline. Clean separation.

### Why optional title?

Short notes (quick observations) don't need titles. First line of content_text suffices in list display.

### Why JSON + HTML + text triple?

JSON preserves editor state. HTML provides pre-rendered display. Plain text enables FTS. Each serves a distinct purpose.

### Why full snapshots (not diffs)?

Each version independently renderable. Simpler, more reliable. No delta chain corruption risk. Diff display is a view concern.

### Why private by default?

Privacy-first. Users share intentionally. Prevents accidental exposure. Matches user expectation for personal notes.

### Why two visibility levels?

Simple and sufficient. Avoids complexity of granular per-user sharing. Private = creator only. Shared = inherits entity visibility.

### Why editor-agnostic?

Flutter has multiple viable rich text editors. Decoupling preserves flexibility. Content contract is the stable interface.

### Why per-entity-link pinning?

A note on both Contact and Company may be important for the Contact but not the Company. Pinning is contextual to the viewing entity.

### Why prevent last-link removal?

Orphaned notes with no entity links are invisible except through search. Better UX to require explicit delete.

---

## Related Documents

| Document | Relationship |
|---|---|
| [Note Entity TDD](note-entity-tdd.md) | Technical decisions for note implementation |
| [Content, Revisions & Sanitization Sub-PRD](note-content-revisions-prd.md) | Content architecture, revision history, sanitization |
| [Attachments, Mentions & Search Sub-PRD](note-attachments-mentions-prd.md) | File uploads, @mentions, full-text search |
| [Custom Objects PRD](custom-objects-prd.md) | Unified object model |
| [Document Entity Base PRD](document-entity-base-prd.md) | Reuses Universal Attachment pattern |
| [Permissions & Sharing PRD](permissions-sharing-prd.md) | Entity-level visibility rules |
| [Master Glossary](glossary.md) | Term definitions |
