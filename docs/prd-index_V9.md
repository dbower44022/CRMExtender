# CRMExtender — PRD Index

**Version:** 9.0
**Last Updated:** 2026-02-22
**Purpose:** Living index of all Product Requirements Documents for CRMExtender. Reference this at the start of any PRD development session for orientation.

---

## Platform Overview

CRMExtender (also called Contact Intelligence Manager) is a comprehensive CRM platform providing deep relationship intelligence and unified communication tracking. The system targets sales professionals, entrepreneurs, and service providers. Key differentiators include unified multi-channel inbox, AI conversation intelligence, cross-channel conversation stitching, and sophisticated relationship tracking.

**Tech Stack:** Flutter frontend (cross-platform), Python FastAPI backend, PostgreSQL (event-sourced, schema-per-tenant), Neo4j (relationship graph), SQLite (offline read), Meilisearch (search).

---

## PRD Status Summary

| PRD | Version | File | Status | Date |
|---|---|---|---|---|
| GUI Functional Requirements | 2.0 | `gui-functional-requirements-prd_V2.md` | Draft — Terminology standardized | 2026-02-21 |
| Custom Objects | 2.0 | `custom-objects-prd_v2.md` | Draft — Terminology standardized | 2026-02-22 |
| Communications | 3.0 | `communications-prd_V3.md` | Draft — Terminology standardized | 2026-02-22 |
| Conversations | 4.0 | `conversations-prd_V4.md` | Draft — Terminology standardized | 2026-02-22 |
| Contact Management | 5.0 | `contact-management-prd_V5.md` | Draft — Terminology standardized | 2026-02-22 |
| Company Management | 1.0 | `company-management-prd_V1.md` | Draft — Terminology standardized; needs V2 Custom Objects reconciliation | 2026-02-22 |
| Event Management | 3.0 | `events-prd_V3.md` | Draft — Terminology standardized | 2026-02-22 |
| Notes | 3.0 | `notes-prd_V3.md` | Draft — Terminology standardized | 2026-02-22 |
| Tasks | 2.0 | `tasks-prd_V2.md` | Draft — Terminology standardized | 2026-02-22 |
| Documents | 2.0 | `documents-prd_V2.md` | Draft — Terminology standardized | 2026-02-22 |
| Projects | 3.0 | `projects-prd_V3.md` | Draft — Terminology standardized | 2026-02-22 |
| Outbound Email | 2.0 | `outbound-email-prd_V2.md` | Draft — Terminology standardized | 2026-02-22 |
| Views & Grid | 5.0 | `views-grid-prd_V5.md` | Draft — Terminology standardized | 2026-02-22 |
| Data Sources | 1.0 | `data-sources-prd_V1.md` | Draft — Terminology standardized | 2026-02-22 |
| Permissions & Sharing | 2.0 | `permissions-sharing-prd_V2.md` | Draft — Terminology standardized | 2026-02-22 |
| Adaptive Grid Intelligence | 2.0 | `adaptive-grid-intelligence-prd_V2.md` | Draft — Terminology standardized | 2026-02-22 |
| Master Glossary | 3.0 | `glossary_V3.md` | Active — 207+ terms | 2026-02-21 |
| Email Parsing & Content Extraction | 1.0 | `email_stripping_V1.md` | Technical spec — Mojibake cleaned | 2026-02-22 |
| Email Provider Sync | — | — | **Planned** — parent (Communications) complete | — |
| SMS/MMS | — | — | **Planned** — parent (Communications) complete | — |
| Voice/VoIP | — | — | **Planned** — parent (Communications) complete | — |
| Video Meetings | — | — | **Planned** — parent (Communications) complete | — |
| AI Learning & Classification | — | — | **Planned** — requirements established in Conversations PRD | — |
| Contact Intelligence | — | — | **Planned** — depends on Contact Mgmt + Communications | — |

### Retired / Superseded Documents

| Document | File | Superseded By | Date |
|---|---|---|---|
| Communication & Conversation Intelligence PRD v2.0 | `email-conversations-prd.md` | `communications-prd_V3.md` + `conversations-prd_V4.md` | 2026-02-18 |
| Conversations PRD V1-V2 | `conversations-prd_V1.md`, `conversations-prd_V2.md` | `conversations-prd_V4.md` | 2026-02-19 |
| Communications PRD V1 | `communications-prd_V1.md` | `communications-prd_V3.md` | 2026-02-19 |
| Projects PRD V1 | `projects-prd_V1.md` | `projects-prd_V3.md` | 2026-02-19 |
| Views & Grid PRD V3-V4 | `views-grid-prd_V3.md`, `views-grid-prd_V4.md` | `views-grid-prd_V5.md` | 2026-02-22 |
| Custom Objects PRD V0-V1 | `custom-objects-prd.md`, `custom-objects-prd_v1.md` | `custom-objects-prd_v2.md` | 2026-02-22 |
| Contact Management PRD V1-V4 | `contact-management-prd_V4.md` | `contact-management-prd_V5.md` | 2026-02-22 |
| Adaptive Grid Intelligence PRD V1 | `adaptive-grid-intelligence-prd_V1.md` | `adaptive-grid-intelligence-prd_V2.md` | 2026-02-21 |
| GUI Functional Requirements PRD V1 | `gui-functional-requirements-prd_V1.md` | `gui-functional-requirements-prd_V2.md` | 2026-02-21 |
| Glossary V1-V2 | `glossary_V1.md`, `glossary_V2.md` | `glossary_V3.md` | 2026-02-21 |
| Communications PRD V2 | `communications-prd_V2.md` | `communications-prd_V3.md` | 2026-02-22 |
| Conversations PRD V3 | `conversations-prd_V3.md` | `conversations-prd_V4.md` | 2026-02-22 |
| Events PRD V2 | `events-prd_V2.md` | `events-prd_V3.md` | 2026-02-22 |
| Notes PRD V2 | `notes-prd_V2.md` | `notes-prd_V3.md` | 2026-02-22 |
| Tasks PRD V1 | `tasks-prd_V1.md` | `tasks-prd_V2.md` | 2026-02-22 |
| Documents PRD V1 | `documents-prd_V1.md` | `documents-prd_V2.md` | 2026-02-22 |
| Projects PRD V2 | `projects-prd_V2.md` | `projects-prd_V3.md` | 2026-02-22 |
| Outbound Email PRD V1 | `outbound-email-prd_V1.md` | `outbound-email-prd_V2.md` | 2026-02-22 |
| Permissions & Sharing PRD V1 | `permissions-sharing-prd_V1.md` | `permissions-sharing-prd_V2.md` | 2026-02-22 |
| PRD Index V1-V8 | `prd-index_V8.md` | `prd-index_V9.md` | 2026-02-22 |

---

## Completed PRDs

### 1. Custom Objects

**File:** `custom-objects-prd_v2.md`
**Scope:** The entity model foundation. Defines the Unified Object Model where system entities (Contact, Conversation, Company, etc.) and user-created entities are instances of the same framework. Covers object type definition, field registry, field type system, relation model, physical storage architecture, DDL management, and event sourcing. V2 adds Card-Based Architecture terminology alignment (Field Groups → Attribute Cards).

**Key sections:**

- Unified Object Model (system and custom entities as instances of the same ObjectType framework)
- Object type definition model (identity, slug, type prefix, schema version, lifecycle)
- Universal fields (id, tenant_id, created_at/by, updated_at/by, archived_at)
- Field registry (field definitions, slugs as column names, ordering, limits)
- Field type system (15 Phase 1 types, 2 Phase 2: Formula, Rollup)
- Field type conversion matrix (safe conversions only, with preview wizard)
- Field groups (rendered as Attribute Cards in the Detail Panel, GUI PRD Section 15.7)
- Field validation (type-specific constraints, required fields, unique constraints)
- Select & multi-select option management
- Relation Types (all three cardinalities, bidirectional/unidirectional, cascade behavior, metadata attributes, self-referential, Neo4j sync flag)
- Physical storage architecture (dedicated typed tables per entity type, DDL management system)
- Event sourcing (per-entity-type event tables, immutable events, point-in-time reconstruction)
- Schema-per-tenant architecture
- System entity specialization (behaviors, protected core fields, extensibility)
- Uniform Record CRUD API and Relation Instance API
- Cross-PRD reconciliation (Contact Management, Data Sources, Views, Communication)
- 4-phase roadmap

**Key decisions made:**

- **Unified Object Model** — system entities are pre-installed object types with `is_system` flag, protected core fields, and registered behaviors. Custom entities are equal citizens at the storage, query, and rendering layers.
- **Dedicated typed tables per entity type** — every entity type gets its own PostgreSQL table with native typed columns. Fields map to columns. DDL at runtime via ALTER TABLE.
- **Schema-per-tenant** — each tenant gets its own PostgreSQL schema with entity tables, event tables, and junction tables.
- **Full event sourcing for all entity types** — per-entity-type event tables. Same audit trail and point-in-time reconstruction for custom and system entities.
- **First-class Relation Types** — all three cardinalities (1:1, 1:many, many:many) from Phase 1. Bidirectional or unidirectional. Self-referential supported. Configurable cascade (nullify default, restrict, cascade archive).
- **Relation metadata** — additional attributes on relationship instances (role, strength, start date, notes).
- **Neo4j graph sync** — optional flag per relation type.
- **Permission-gated entity type creation** — Object Creator permission (not admin-only).
- **50 custom entity types per tenant** limit. **200 fields per entity type** limit.

**Gutter business test cases:** Jobs, Properties, Service Areas, Estimates.

**Open questions:** 12 (DDL timing, reserved words, record limits, field templates, import/export, relation limits, event retention, multi-line storage, offline sync, computed defaults, relation modification, Neo4j selective fields)

---

### 2. Communications

**File:** `communications-prd_V3.md`
**Scope:** The atomic interaction record. Defines Communication as a system object type, the common schema all channels normalize to, the provider adapter framework, contact association, triage filtering, multi-account management, attachments, and storage. Foundation for channel-specific child PRDs. V2 adds Published Summary architecture (Section 7).

> **Extracted from:** Communication & Conversation Intelligence PRD v2.0 (the Communications half of the decomposition).

**Key sections:**

- Communication as system object type (`com_` prefix, full field registry)
- Channel types: `email`, `sms`, `mms`, `phone_recorded`, `phone_manual`, `video_recorded`, `video_manual`, `in_person`, `note`
- Communication entry points (auto-synced vs. manual)
- Provider account framework (personal and shared accounts, shared inbox attribution)
- Provider adapter architecture (interface, sync modes, reliability, audit trail)
- Communication Participants Relation Type (Communication→Contact, many-to-many with role/address metadata)
- Contact resolution integration with Contact Intelligence system
- Triage & intelligent filtering (heuristic layers, known-contact gate, transparency)
- Attachments model (storage strategy, recording-transcript relationship)
- Multi-account management (unified feed, cross-account considerations)
- Event sourcing (`communications_events`)
- Virtual schema & Data Sources integration
- Full-text search (PostgreSQL `tsvector`/`tsquery`)
- Storage & data retention estimates
- Privacy, security & compliance (GDPR, SOC 2, CCPA)
- API design (CRUD, participants, attachments, sync, triage)

**Key decisions made:**

- Direct provider API integration (no Nylas/third-party aggregation)
- Communication Participants as a system Relation Type (replacing flat `from_address`/`to_addresses` columns)
- `conversation_id` as FK column (not Relation Type) — simpler for strict many:1
- Three-tier content model: `content_raw`, `content_html`, `content_clean`
- Published Summary architecture (V2): rich text summaries per channel type, revision history, Conversation timeline renders by reference
- Channel-specific parsing delegated to child PRDs
- `note` channel type is distinct from Notes system object type (interactions vs. commentary)
- Manual logged interactions (unrecorded calls, in-person meetings) are Communications, not Notes
- Provider account framework shared across all integration types

**Channel child PRDs:**

| Child PRD | Scope | Status |
|---|---|---|
| Email Provider Sync PRD | Gmail, Outlook, IMAP adapters; dual-track parsing; email threading; email-specific triage | Planned — parent complete |
| SMS/MMS PRD | Twilio/OpenPhone adapters; message sync; phone number resolution; MMS media | Planned |
| Voice/VoIP PRD | Call recording integration; transcription pipeline; provider adapters | Planned |
| Video Meetings PRD | Zoom/Teams/Meet integration; transcript capture; recording management | Planned |

**Open questions:** 9 (attachment storage, real-time sync infra, email sending, shared mailbox, merge/split, opt-out granularity, SMS provider, speech-to-text, Slack/Teams model)

---

### 3. Conversations

**File:** `conversations-prd_V4.md`
**Scope:** The organizational intelligence layer. Defines Conversation (standard and aggregate) as the single system object type, with aggregate Conversations replacing Topics. Flexible hierarchy via Relation Types, AI intelligence layer (classify & route, summarize, extract), conversation timeline referencing Communication Published Summaries, cross-channel stitching, segmentation, review workflow, views, and alerts. Projects extracted to separate Projects PRD.

> **Extracted from:** Communication & Conversation Intelligence PRD v2.0 (the Conversations half of the decomposition).

**Key sections:**

- Conversation as system object type (`cvr_` prefix, field registry with AI fields, `is_aggregate` flag)
- Aggregate Conversations (replacing Topic entity, `is_aggregate = true`, nesting via `conversation_members`)
- Conversation Membership (many-to-many junction table, acyclic enforcement, denormalized count roll-up)
- System Relation Types (Conversation↔Project, Conversation↔Company, Conversation↔Contact, Conversation↔Event)
- Organizational hierarchy (Aggregate Conversation → Child Conversation → Communication, all optional)
- Conversation formation (email thread auto-creation, participant-based defaults, manual, AI-suggested splitting)
- Multi-channel conversations (cross-channel stitching, channel markers for AI)
- Communication segmentation & split/reference model (segment data model)
- AI intelligence layer (3 roles: classify & route, summarize, extract intelligence)
- Review workflow (confidence-tiered display, efficient daily review UX)
- Learning from user corrections (product requirement; implementation deferred to AI Learning PRD)
- Conversation lifecycle (3 independent status dimensions: system_status, ai_status, triage)
- Conversation views & dashboards (Views framework integration, example views)
- User-defined alerts (no defaults, view→alert architecture, frequency/aggregation/delivery)
- Event sourcing for Conversations (standard and aggregate)
- API design (CRUD for conversations, membership, entity associations, intelligence, review workflow)

**Key decisions made:**

- Single Conversation entity with `is_aggregate` flag (replacing Topic + Conversation as separate types). Projects extracted to separate PRD. — not one hierarchy entity
- Derived participant list (supplemented by explicit Conversation→Contact Relation Type — avoids duplication)
- Optional hierarchy at every level — communications can be unassigned, conversations don't need topics
- Aggregate nesting unlimited with acyclic enforcement; entity associations via Relation Types, not FK columns
- AI biased toward `open` status for multi-message exchanges
- Configurable stale/closed thresholds per conversation (default: 14/30 days)
- No default alerts — user defines all notifications
- Segmentation uses split/reference model (original never modified, segments are cross-references)

**Open questions:** 8 (aggregate nesting depth, conversation merge/split, cross-account merging, calendar linking, Slack/Teams model, AI cost management, merge detection, opt-out granularity)

---

### 4. Contact Management & Intelligence

**File:** `contact-management-prd_V5.md`
**Scope:** The foundational entity layer. Defines contacts and companies as living intelligence objects with event-sourced history, multi-identifier identity model, enrichment, OSINT, and relationship intelligence. V5 adds terminology standardization and cross-PRD link alignment.

**Key sections:**

- Contact as system object type (`con_` prefix, field registry)
- Contact data model (dedicated table managed by object type framework)
- Company data model (`cmp_` prefix)
- Identity resolution & entity matching (multi-identifier: email, phone, social)
- Employment history as system Relation Type (Contact→Company, many-to-many with temporal metadata)
- Contact lifecycle management (lead status, engagement scoring)
- Contact intelligence & enrichment (Apollo, Clearbit, People Data Labs adapters)
- Relationship intelligence (Neo4j graph, relationship types, influence mapping)
- Behavioral signal tracking (engagement score computation)
- Groups, tags & segmentation
- Contact import & export (CSV, Google Contacts sync)
- AI-powered contact intelligence (briefings, tag suggestions, NL search)
- Event sourcing (per-entity-type `contacts_events` table)
- API design
- Client-side offline support (SQLite)
- 4-phase roadmap

**Key decisions made:**

- Contact IDs use `con_` prefixed ULIDs; Company IDs use `cmp_` prefixed ULIDs
- Employment history is a system Relation Type with junction table `contacts__companies_employment`
- Custom fields managed through unified field registry (JSONB column removed)
- `contacts` table is the read model managed by object type framework
- Per-entity-type event tables (`contacts_events`, `companies_events`)
- Intelligence items are discrete sourced data points with confidence scores
- Engagement score is a composite behavioral metric (0.0–1.0)
- Intelligence score measures data completeness (0.0–1.0)
- Google People API for bidirectional contact sync (Phase 1)
- Browser extension for LinkedIn/Twitter capture (Phase 2)

**Reconciliation status:** Fully reconciled with Custom Objects PRD as of V3/V4. Terminology standardized as of V5.

---

### 5. Company Management

**File:** `company-management-prd_V1.md`
**Scope:** Company as a CRM entity with firmographic data, domain-based resolution, and relationship to contacts.

> **Note:** This PRD has been terminology-standardized but has not yet been structurally reconciled with the Custom Objects framework. Needs V2 rewrite similar to Events V2 (prefixed ULIDs, field registry, relation types, event sourcing).

---

### 6. Event Management

**File:** `events-prd_V3.md`
**Scope:** Event as a system object type for calendar events, meetings, and temporal relationship intelligence.

**Key sections:**

- Event as system object type (`evt_` prefix, full field registry)
- Calendar sync via provider account framework (Google Calendar adapter)
- Event↔Contact Relation Type (`event_attendees`)
- Event↔Conversation Relation Type (`event_conversations`)
- Birthday auto-generation behavior
- Recurrence defaulting behavior
- Event sourcing (`events_events`)
- RSVP tracking

**Reconciliation status:** Fully reconciled with Custom Objects PRD as of V2.

---

### 7. Notes

**File:** `notes-prd_V3.md`
**Scope:** Note as a system object type for free-form knowledge capture with rich text, revisions, and universal entity attachment.

**Key sections:**

- Note as system object type (`not_` prefix)
- Universal Attachment Relation pattern (notes attach to any entity type)
- Behavior-managed rich text content (JSONB + HTML, revision history)
- Content architecture (editor-agnostic storage contract)
- Revision history coexisting with event sourcing
- Full-text search (PostgreSQL `tsvector`/`tsquery`)
- File attachments, @mentions, pinning
- Note visibility model (private by default, shared inherits entity permissions)

**Reconciliation status:** Fully reconciled with Custom Objects PRD as of V2.

---

### 8. Tasks

**File:** `tasks-prd_V2.md`
**Scope:** Task as a system object type for actionable work items with status workflow, priority, assignees, dependencies, subtask hierarchy, recurrence, and AI action-item extraction.

**Key sections:**

- Task as system object type (`tsk_` prefix, full field registry)
- Status model with user-extensible statuses mapped to four system categories (`not_started`, `active`, `done`, `cancelled`)
- Fixed priority model (urgent, high, medium, low, none) with sort weights
- Unlimited subtask hierarchy via self-referential `parent_task_id` FK
- Universal Attachment Relation (reuses Notes pattern — tasks attach to any entity type)
- Task→User Relation Type (`task_user_participation`) with role metadata (assignee, reviewer, watcher)
- Task dependencies via self-referential many:many Relation Type (`task_dependencies`) with `blocked_by` semantics
- Rich text descriptions (behavior-managed content, Notes-aligned architecture, no revision tracking)
- Events-aligned recurrence model (completion-triggered instance generation, RRULE support)
- AI action-item extraction behavior (auto-create tasks from Conversation intelligence)
- Due date reminders and overdue detection behaviors
- Event sourcing (`tasks_events`)
- Full-text search (PostgreSQL `tsvector`/`tsquery`)
- 4-phase roadmap (core → full features → AI integration → advanced)

**Key decisions made:**

- **System object type** — 7 registered behaviors require system entity status (custom objects can't have behaviors)
- **Status categories** — user-extensible status labels mapped to immutable system categories that drive behavioral logic
- **Fixed priority** — not user-extensible; consistency and sort ordering matter more than customization
- **Multiple assignees** — Task→User relation type with roles, not single FK
- **Universal Attachment** — reuses Notes pattern; standalone tasks allowed (no required entity link, unlike Notes)
- **Warn-but-allow subtask cascade** — warns on parent completion with open children, does not block or auto-complete
- **Completion-triggered recurrence** — next instance generated when current is completed (not time-triggered like Events)
- **No description revision tracking** — event sourcing captures changes; full revision model deferred unless needed
- **Workspace-visible** — all tasks visible to all members (subject to role-based permissions), unlike Notes' private-by-default model
- **Simple blocking dependencies** — `blocked_by`/`blocks` only; full dependency types (FS/SS/FF/SF) deferred

**Open questions:** 6 (notification subsystem dependency, AI confidence thresholds, recursive rollup scope, due date semantics, subtask ordering, Board View column mapping)

**Reconciliation status:** Fully reconciled with Custom Objects PRD as of V1.

---

### 9. Documents

**File:** `documents-prd_V2.md`
**Scope:** Document as a system object type for version-controlled file management with folder organization, metadata extraction, full-text search, and universal entity attachment. Unifies communication attachments, profile assets, and user-uploaded files into a single entity model.

**Key sections:**

- Document as system object type (`doc_` prefix, full field registry with extracted metadata fields)
- Universal Attachment Relation (reuses Notes pattern -- documents and folders attach to any entity type)
- Folders as Document entities (`is_folder = true`, many-to-many folder membership, nested hierarchy)
- Hash-based version control (SHA-256, automatic on re-upload with different hash, named versions)
- Content-addressable storage (SHA-256 dedup, progressive hashing, reference counting, `document_blobs` table)
- Duplicate detection (progressive hashing: quick hash on first+last 64KB, full hash only if candidates found)
- Metadata extraction behavior (PDF, Office, images/EXIF, video, audio -- auto-populates fields)
- Text extraction and full-text search (PostgreSQL `tsvector`/`tsquery`, three-tier weighting: name > description > content)
- Thumbnail generation behavior (images, PDFs, video -- stored in system `_thumbnails` folder)
- Document visibility model (private by default, folder visibility cascade)
- Communication attachment integration (`communication_documents` relation with version tracking, replaces `communication_attachments`)
- Profile asset integration (logos, headshots, banners as Document entities, replaces `entity_assets`)
- Upload/download (chunked uploads for large files, no size/type restrictions except dangerous file blocklist)
- Event sourcing (`documents_events`)
- 4-phase roadmap (core -> folders/search/metadata -> integration/migration -> cloud/graph/advanced)

**Key decisions made:**

- **System object type** -- 7 registered behaviors require system entity status
- **Folders as entities** -- `is_folder = true` flag on Document, not a separate table. Enables folders in Universal Attachment, Views, event sourcing
- **Many-to-many folder membership** -- documents can exist in multiple folders simultaneously (links, not containment)
- **Hash-based version control** -- automatic, deterministic, no user decision required. Same-hash upload is a no-op
- **Content-addressable storage** -- SHA-256 hash as blob identity. Automatic deduplication across documents and tenants
- **Progressive hashing** -- quick hash eliminates most non-duplicates; full hash only when candidates found
- **Private by default** -- matches Notes visibility model. Folder cascade is a Documents-specific extension
- **Folder visibility cascade** -- shared folder makes contents accessible regardless of individual document visibility
- **No size/type restrictions** -- blocklist for dangerous executables only. Chunked uploads for large files
- **Communication attachments become Documents** -- replaces `communication_attachments` with `communication_documents` (includes version_id for precise tracking)
- **Profile assets become Documents** -- replaces `entity_assets` with Document entities. Adds version control to logos/headshots
- **Note attachments unchanged** -- pasted images are part of note content, not standalone documents
- **Thumbnails as Document entities** -- stored in system `_thumbnails` folder, reuses same storage infrastructure
- **No OCR** -- text extraction from embedded text only. OCR deferred to future phase

**Open questions:** 8 (folder membership event volume, file type changes between versions, max folder count per document, global search federation, email body indexing scope, storage quotas, download/view audit logging, thumbnail lifecycle)

**Reconciliation status:** Fully reconciled with Custom Objects PRD as of V1. Defines cross-PRD reconciliation items for Communications PRD (Section 12 superseded) and Company Management PRD (`entity_assets` deprecated).

---

### 10. Projects

**File:** `projects-prd_V3.md`
**Scope:** The central organizational hub. Defines Project as a system object type — the highest-level user-created container that connects Conversations, Events, Notes, Contacts, and Companies into a coherent picture of a business initiative. Covers sub-project hierarchy, user-defined status workflow, system Relation Types, and explicit entity associations.

> **Extracted from:** Conversations PRD v1.0 (Project was originally co-resident with Topic and Conversation). Reconciled with Conversations PRD V3 (Topic elimination, Relation Type attachment model).

**Key sections:**

- Project as system object type (`prj_` prefix, field registry with user-defined status)
- Sub-project hierarchy (self-referential Relation Type, unlimited nesting, cascade archiving)
- Flexible hierarchy model (Conversations link via Relation Types, aggregate Conversations for grouping)
- System Relation Types (Project↔Conversation, Project↔Contact, Project↔Company, Project↔Event, Project↔Note)
- User-defined status workflow (no system-imposed states, user-configurable Select field)
- Project creation model (proactive vs. reactive vs. AI-suggested)
- Event sourcing (`projects_events`)
- API design (CRUD, relation management, sub-project operations)

**Key decisions made:**

- Central hub, not conversation container — Projects organize all work entities, not just communications
- User-defined workflow — no system-imposed status states or transitions
- Project↔Conversation is many-to-many via Relation Type (no FK columns on Conversations table)
- Aggregate Conversations exist independently of Projects (standalone grouping tool)
- Explicit Contact/Company associations independent of communication participation
- Sub-project depth unlimited with cascade archiving
- System Relation Types ship out of the box for all core entity connections

**Open questions:** 7 (sub-project depth warning, archive cascade, project templates, bulk entity linking, derived participant display, project merge/split, cross-tenant sharing)

---

### 11. Views & Grid System

**File:** `views-grid-prd_V5.md`
**Scope:** The primary data interaction layer. Polymorphic, entity-agnostic framework for displaying, filtering, sorting, grouping, and editing any entity type through multiple view types. V5 adds Card-Based Architecture terminology for row expansion and Detail Panel references.

**Key sections:**

- Core concepts (Data Source separation, entity-agnostic rendering)
- View types: List/Grid, Calendar, Timeline, Board/Kanban
- Column system (direct, relation traversal, computed) — extended by [Adaptive Grid Intelligence PRD](adaptive-grid-intelligence-prd_V2.md) for content-aware auto-sizing
- Field type registry — extended by AGI PRD for format adaptation and content-aware alignment
- Relation traversal & lookup columns
- Filtering & query builder (compound AND/OR, cross-entity filters)
- Sorting & grouping (multi-level, collapsible, aggregation rows)
- Grid interactions (inline editing, row expansion, bulk actions, keyboard nav)
- View persistence & sharing (personal, shared, fork-on-write)
- View-as-alert integration
- Performance & pagination (virtual scrolling, cursor-based)
- 4-phase roadmap

**Key decisions made:**

- Data Source is a separate layer from View (extracted to own PRD)
- Entity-agnostic: custom objects get same view capabilities as system entities
- View-level filters AND with data source filters (cannot remove/override)
- Shared views enforce row-level security (sharing definition ≠ sharing data)
- Board view supports swimlanes (matrix of group-by × status)
- Tree view capability added (hierarchical rendering)

**Alignment with Custom Objects PRD:** Views PRD Section 9 (field type rendering) is the presentation layer counterpart to Custom Objects PRD Section 9 (field type data layer). Relation traversal (Views Section 10) operates on Relation Types defined in Custom Objects PRD Section 14. Row expansion renders the Detail Panel's Card-Based Architecture (GUI PRD Section 15). No reconciliation required.

---

### 12. Data Sources

**File:** `data-sources-prd_V1.md`
**Scope:** The query abstraction layer. Reusable, named query definitions that sit between physical storage and views, providing cross-entity queries, dual authoring modes, column registries, and preview detection.

**Key sections:**

- Universal entity ID convention (prefixed IDs: `con_`, `cvr_`, `com_`, etc.)
- Data source definition model (ID, query, column registry, preview config, parameters, refresh policy)
- Visual query builder (5-step: entity → joins → columns → filters → sort)
- Raw SQL environment (virtual schema, access rules, validation, parameters)
- Column registry (auto-generated + manual overrides, editability rules)
- Entity detection & preview system (3-layer: auto-detect → inference rules → manual override)
- Data source → view relationship (many-to-one, composition rules)
- Inline editing trace-back (column registry → source entity → API call)
- System-generated data sources (auto-created per entity type)
- Performance (cursor pagination, EXPLAIN plan analysis)
- 4-phase roadmap

**Key decisions made:**

- Prefixed entity IDs (`con_`, `cvr_`, `com_`, etc.) with ULID — adopted platform-wide
- Data sources are reusable across multiple views
- Dual authoring: visual query builder for simple, raw SQL for complex
- Virtual schema mirrors physical schema for query simplicity
- Column registry enables inline editing from any joined query
- System-generated data sources auto-created per entity type
- Schema versioning for breaking change detection

**Alignment with Custom Objects PRD:** Virtual schema composition resolved — virtual schema tables = object type slugs, virtual schema columns = field slugs. 1:1 mapping means query engine translation is trivial.

---

### 13. Permissions & Sharing

**File:** `permissions-sharing-prd_V2.md`
**Scope:** Team access controls, role-based permissions, row-level security, shared vs. private data, provider account management, data visibility rules.

**Key sections:**

- Permission model (RBAC with per-object-type granularity)
- Role definitions (Owner, Admin, Member, Read-Only, Custom)
- Object Creator permission (per Custom Objects PRD Section 6.4)
- Row-level security injection into Data Source queries
- Shared view permissions (sharing definition ≠ sharing data)
- Provider account management permissions
- Integration data visibility
- Multi-tenant isolation (schema-per-tenant confirmed)

---

### 14. Email Parsing & Content Extraction

**File:** `email_stripping_V1.md`
**Scope:** Technical specification for the dual-track email parsing pipeline. Covers HTML structural removal and plain-text regex-based extraction.

**Key sections:**

- HTML cleaning pipeline (quote removal, signature detection, disclaimer stripping)
- Plain-text pipeline (reply pattern detection, valediction-based truncation, standalone signature detection)
- Promotional content detection
- Line unwrapping algorithm
- Provider-specific patterns (Gmail, Outlook, Apple Mail)

**Notes:** This is a technical spec, not a conceptual PRD. Companion document to the planned Email Provider Sync PRD. More appropriate for Claude Code reference than PRD development sessions.

---

### 15. Adaptive Grid Intelligence

**File:** `adaptive-grid-intelligence-prd_V2.md`
**Scope:** Intelligent layout engine that automatically optimizes the entire Workspace Layout (grid columns, Detail Panel, Entity Bar) based on display characteristics, data content analysis, and user preferences. Transforms the grid from static, manually-configured layouts into a self-optimizing workspace that adapts to the user's monitor, data, and workflow. V2 adopts standardized GUI terminology (Workspace Layout, Entity Bar, Detail Panel).

**Key sections:**

- Display detection & viewport analysis (display profiles, DPI heuristics, density tier classification)
- Workspace space budget engine (three-zone allocation: Entity Bar, grid, Detail Panel)
- Content analysis engine (per-column metrics: value widths, diversity scores, content type distribution)
- Intelligent column width allocation (weighted distribution, priority-based, content-driven format adaptation)
- Content-aware cell alignment (dynamic by actual values, not static by field type)
- Value diversity analysis & column demotion (4-tier: annotated → collapsed → header-only → hidden)
- Detail Panel intelligence (width and internal density adaptation based on content and preference)
- Entity Bar adaptation (content-aware width)
- Vertical density optimization (auto row density selection based on display + data)
- Auto-configuration lifecycle (triggers on view open + significant resize, then hands-off)
- User override persistence model (proportional storage scoped to User × View × Display Tier)
- View settings extensions (Detail Panel size, auto-density, column auto-sizing, column demotion toggles)
- Column priority hierarchy with sacrifice ordering for constrained displays
- Data model (user_view_layout_overrides table, view configuration extensions)
- 4-phase roadmap (grid-first, extensible to Board/Calendar/Timeline)

**Key decisions made:**

- **Proportional, not absolute** — All overrides stored as percentages, enabling meaningful cross-display translation
- **Anticipate then defer** — Auto-configures on open/resize, then never re-adjusts during the session
- **Content drives layout** — Column widths, alignment, and demotion based on actual data, not field type defaults
- **Unified workspace budget** — Grid, Detail Panel, and Entity Bar participate in a single space allocation
- **User overrides scoped per display tier** — Desktop and laptop can have independent layout preferences for the same view
- **Tiered column demotion** — Gradual (annotated → collapsed → header-only → hidden), never abrupt
- **Client-side content analysis** — All analysis on loaded data, no additional server queries, <50ms budget
- **Grid-only Phase 1** — Patterns designed to extend to Board, Calendar, Timeline in later phases

**Alignment with Views & Grid PRD:** Extends column configuration (Section 8.3), field type display renderers (Section 9.1), and view persistence (Section 17). The Views & Grid PRD V5 includes cross-references to this document. Default column widths in the Views & Grid PRD serve as fallbacks when auto-sizing is disabled.

**Alignment with GUI Functional Requirements PRD:** Extends the Workspace Layout (Section 4), Splitter Bar (Section 4.3), Detail Panel (Section 8), responsive breakpoints (Section 21), and density settings (Section 23.3). Display tiers refine the breakpoint system. Auto-density adds an "auto" mode to the existing compact/standard/comfortable options.

---

### 16. GUI Functional Requirements

**File:** `gui-functional-requirements-prd_V2.md`
**Scope:** The application shell and navigation framework. Defines the Workspace Layout (Entity Bar + Content Area with Splitter Bar + Detail Panel), Application Tool Bar, Content Tool Bar, Card-Based Architecture for Detail Panel rendering, Docked Window system, keyboard navigation, density settings, responsive breakpoints, and cross-platform behavior. V2 is a full structural rewrite establishing standardized terminology adopted across all PRDs.

**Key sections:**

- Workspace Layout (three-zone: Entity Bar, Content Area, Detail Panel with Splitter Bar)
- Application Tool Bar (persistent top-level: workspace selector, global search, user menu, notification center)
- Content Tool Bar (view-contextual: view selector, filter builder, sort controls, bulk actions, new record)
- Entity Bar (left sidebar: entity type navigation, recent items, favorited views)
- Detail Panel (right panel: Card-Based Architecture rendering for selected record)
- Card-Based Architecture (Identity Card + Card Layout Area with Attribute Cards, Relation Cards, Activity Card)
- Attribute Cards (Field Group rendering with section-based editing)
- Relation Cards (linked entity lists per Relation Type)
- Activity Card (chronological entity activity stream)
- Docked Window system (undockable panels for multi-monitor workflows)
- Keyboard navigation framework
- Density settings (compact/standard/comfortable/auto)
- Responsive breakpoints and display adaptation
- Cross-platform behavior (Flutter desktop, web, mobile)

**Key decisions made:**

- **Workspace Layout** replaces prior "four-zone layout" terminology — three named zones with consistent naming across all PRDs
- **Card-Based Architecture** is the universal Detail Panel rendering pattern — all entity types render through Identity Card + Card Layout Area
- **Attribute Cards** are the rendering of Custom Objects Field Groups — each Field Group becomes one collapsible Attribute Card
- **Section-Based Editing** within Attribute Cards replaces prior modal/inline editing patterns
- **Entity Bar** replaces prior "Icon Rail", "Action Panel", "Navigation Sidebar" terminology
- **Docked Window** is the standard term for undockable/floatable panels

**Reconciliation status:** V2 establishes the terminology standard. All PRDs updated to reference V2 terminology.

---

### 17. Outbound Email

**File:** `outbound-email-prd_V2.md`
**Scope:** Compose, send, and track outbound emails. Covers the compose experience, template system, account selection, send pipeline, delivery tracking, click tracking (no open/read tracking), approval workflows for automation-generated emails, and date-triggered automation rules.

**Key sections:**

- Compose experience (panel-based composer, Docked Window support)
- Account selection logic (historical pattern matching per contact)
- Template system (Markdown with merge fields, preview, versioning)
- Send pipeline (queue, retry, failure handling)
- Delivery tracking (bounce detection, status monitoring)
- Click tracking (link wrapping, per-recipient click events; no open/read tracking)
- Automation rules (date-triggered sequences, overlap detection, mandatory approval)
- Conversation linking (explicit from compose context, auto from reply threading)
- API design (compose, send, templates, automation rules, tracking data)

**Key decisions made:**

- **No open/read tracking** — privacy-conscious design; click tracking only
- **Mandatory approval** for automation-generated emails — no fully autonomous sending
- **Overlap detection** — prevents same contact from receiving multiple automated emails on the same day
- **Panel-based composer** within Workspace Layout, with Docked Window for multi-monitor
- **Historical pattern matching** for default account selection per contact

**Open questions:** Referenced in PRD body.

**Reconciliation status:** Link-aligned with all current PRD versions.

---

## Planned PRDs (Not Yet Started)

### Email Provider Sync PRD

**Scope:** Gmail, Outlook, IMAP provider adapters; OAuth flows; email sync pipeline (initial, incremental, manual); email parsing & content extraction (dual-track pipeline from `email_stripping_V1.md`); email-specific triage patterns; email threading models per provider.

**Parent:** Communications PRD (now complete — defines the provider adapter interface and common schema)
**Key input:** `email_stripping_V1.md` (technical spec for dual-track parsing pipeline)
**Dependencies:** Communications PRD (adapter interface), Contact Management PRD (identity resolution), Permissions PRD (provider account management)

**Key questions to resolve:**

- How do Gmail Pub/Sub and Outlook webhook callbacks work in production deployment?
- What is the exact cursor lifecycle for each provider?
- How are provider-specific parsing patterns organized in the code?
- Should email sending be included in V1 or deferred?

---

### AI Learning & Classification PRD

**Scope:** How the system learns from user corrections, classification algorithms, embedding/similarity approaches, model training, confidence scoring.

**Referenced by:** Conversations PRD (establishes that learning happens), Views PRD (AI fields as queryable columns), Custom Objects PRD (auto-classification of custom entity select fields as future Phase 3+)
**Depends on:** Communications PRD (correction signals from triage overrides), Conversations PRD (correction signals from conversation/aggregate Conversation assignment), Contact Management PRD (entity context), Custom Objects PRD (entity type awareness, field type system)

**Key questions to resolve:**

- What ML models power auto-classification of conversations to aggregate Conversations and Projects?
- How are user corrections fed back into the model?
- What confidence thresholds trigger auto-assignment vs. human review?
- How is training data managed per tenant?
- Can auto-classification extend to custom entity select fields? (Custom Objects PRD Phase 3+ consideration)

---

## System Object Type Registry

| Object Type | Prefix | Slug | Defined In | Behaviors |
|---|---|---|---|---|
| Contact | `con_` | `contacts` | Contact Management PRD | Identity resolution, auto-enrichment, engagement scoring, intelligence scoring |
| Company | `cmp_` | `companies` | Company Management PRD | Firmographic enrichment, domain resolution |
| Conversation | `cvr_` | `conversations` | Conversations PRD V3 | AI status detection, summarization, action item extraction. Aggregate roll-up (when `is_aggregate = true`). |
| Communication | `com_` | `communications` | Communications PRD | Channel-specific parsing, triage classification, participant resolution, segmentation |
| Project | `prj_` | `projects` | Projects PRD | Entity aggregation |
| ~~Topic~~ | ~~`top_`~~ | ~~`topics`~~ | ~~Conversations PRD~~ | **Removed in V3** — replaced by aggregate Conversations (`is_aggregate = true` on `cvr_` entity) |
| Event | `evt_` | `events` | Event Management PRD | Attendee resolution, birthday auto-generation, recurrence defaulting |
| Note | `not_` | `notes` | Notes PRD | Revision management, FTS sync, mention extraction, orphan attachment cleanup |
| Task | `tsk_` | `tasks` | Tasks PRD | Status category enforcement, subtask cascade (warn), subtask count sync, recurrence generation, AI action-item extraction, due date reminders, overdue detection |
| Document | `doc_` | `documents` | Documents PRD | Thumbnail generation, metadata extraction, text extraction, duplicate detection, FTS sync, visibility cascade, orphan cleanup |
| Data Source | `dts_` | `data_sources` | Data Sources PRD | — |
| View | `viw_` | `views` | Views & Grid PRD | — |
| User | `usr_` | `users` | Permissions & Sharing PRD | — |
| Segment | `seg_` | `segments` | Contact Management PRD | — |

---

## Dependency Map

```
                    ┌──────────────────────┐
                    │  CRMExtender PRD     │
                    │  (Parent v1.1)       │
                    └──────────┬───────────┘
                               │
         ┌─────────────────────┼─────────────────────┐
         │                     │                     │
         ▼                     ▼                     ▼
┌─────────────────────┐ ┌─────────────────────┐ ┌─────────────────────┐
│  Custom Objects     │ │  Contact            │ │  Permissions &      │
│  ★ FOUNDATION       │ │  Management         │ │  Sharing            │
│                     │ │                     │ │                     │
│  Entity types,      │ │  System entity      │ │  Roles, RBAC,       │
│  field registry,    │ │  types: Contact,    │ │  row-level security,│
│  relations, storage,│ │  Company            │ │  provider accounts  │
│  event sourcing     │ │                     │ │                     │
└────────┬────────────┘ └─────────────────────┘ └─────────────────────┘
         │
    ┌────┴────────────────────────┐
    │                             │
    ▼                             ▼
┌─────────────────────┐  ┌─────────────────────┐
│  Communications     │  │  Conversations      │
│  PRD                │  │  PRD                │
│                     │  │                     │
│  Communication      │──│  Conversation (cvr_)│
│  entity (com_)      │  │  Aggregate Cvr          │
│  Provider adapters  │  │  Project (prj_)     │
│  Triage pipeline    │  │  AI intelligence    │
│  Contact resolution │  │  Hierarchy model    │
│  Attachments        │  │  Review workflow    │
└───────┬─────────────┘  │  Views & alerts     │
        │                └─────────────────────┘
   ┌────┴────────────────────────┐
   │    Channel Child PRDs       │
   ├─────────────────────────────┤
   │ Email Provider Sync (planned)│
   │ SMS/MMS (planned)           │
   │ Voice/VoIP (planned)        │
   │ Video Meetings (planned)    │
   └─────────────────────────────┘

Other system object types:
+----------------+  +----------------+  +----------------+  +----------------+
|  Event Mgmt    |  |  Notes PRD     |  |  Tasks PRD     |  |  Documents PRD |
|  PRD (evt_)    |  |  (not_)        |  |  (tsk_)        |  |  (doc_)        |
+----------------+  +----------------+  +----------------+  +----------------+

Cross-cutting PRDs:
┌──────────────┐  ┌──────────────┐
│  Views &     │  │  Data        │
│  Grid PRD    │  │  Sources PRD │
└──────────────┘  └──────────────┘
```

**Reading the arrows:** An arrow from A to B means "A depends on B" or "A references B."

**★ Custom Objects as foundation:** The Custom Objects PRD defines the entity model that Data Sources, Views, Contact Management, Communications, Conversations, Events, Notes, and Tasks all build upon. All entity types (system and custom) are defined through its framework.

---

## Cross-PRD Decisions & Reconciliation Items

### Resolved Items

| Item | PRDs Involved | Resolution |
|---|---|---|
| **Prefixed entity IDs** | Data Sources, Custom Objects, all entity PRDs | Resolved by Custom Objects PRD Section 6.2–6.3. All entity types use `{prefix}_{ULID}` format. |
| **Event sourcing read model** | Data Sources, Custom Objects, all entity PRDs | Resolved by Custom Objects PRD. Section 17 establishes dedicated typed tables. Section 19 establishes per-entity-type event tables. |
| **Custom entity storage** | Data Sources, Custom Objects | Resolved by Custom Objects PRD. Dedicated typed tables with DDL-at-runtime (Section 17–18). |
| **Virtual schema composition** | Data Sources, Custom Objects | Resolved by Custom Objects PRD. Virtual schema tables = object type slugs. Columns = field slugs. Trivial translation. |
| **Communication decomposition** | Communications PRD, Conversations PRD | Resolved 2026-02-18. Monolithic `email-conversations-prd.md` decomposed into sibling Communications + Conversations PRDs with channel child PRDs under Communications. Updated 2026-02-19: Conversations PRD V3 eliminated Topic entity, extracted Projects PRD. |
| **Notes vs. Communications boundary** | Communications PRD, Notes PRD | Resolved in Communications PRD Section 6.3. Communications are interaction records; Notes are supplementary commentary. Manual logged interactions are Communications. |
| **Conversation participants** | Conversations PRD, Communications PRD | Resolved in Conversations PRD Section 5.5. Derived from Communication Participants (primarily derived, supplemented by explicit Conversation→Contact relation). |

### Completed Reconciliation (PRD updates made)

| Item | PRDs Updated | Completed | Notes |
|---|---|---|---|
| Contact Management `custom_fields` removal | Contact Management V3 | 2026-02-17 | Custom fields via unified field registry |
| Contact entity ID migration to `con_` | Contact Management V2 | 2026-02-17 | Prefixed ULIDs adopted |
| Employment history → Relation Type | Contact Management V3 | 2026-02-17 | Junction table with temporal metadata |
| `contacts_current` → object type table | Contact Management V3 | 2026-02-17 | `contacts` read model managed by framework |
| Events → system object type | Events V2 | 2026-02-17 | Full rewrite from PoC SQLite |
| Notes → system object type | Notes V2 | 2026-02-17 | Universal Attachment Relation pattern |
| Communication entities → system object types | Communications V1, Conversations V1 | 2026-02-18 | Full decomposition + Custom Objects reconciliation |
| Task → system object type | Tasks V1 | 2026-02-18 | Universal Attachment pattern (reuses Notes), status categories, 7 behaviors |
| Document -> system object type | Documents V1 | 2026-02-18 | Universal Attachment pattern, hash-based version control, folder model, 7 behaviors. Defines cross-PRD reconciliation for Communications (attachment migration) and Company Management (entity_assets migration). |
| GUI terminology standardization | GUI V2, AGI V2, Views V5, Custom Objects V2, Contact Mgmt V5, all entity PRDs | 2026-02-21–22 | Full ecosystem alignment: Workspace Layout, Entity Bar, Detail Panel, Card-Based Architecture (Identity Card, Attribute Cards, Relation Cards, Activity Card), Content Tool Bar, Application Tool Bar. Master Glossary V3 cross-referenced from all PRD glossaries. Mojibake encoding corruption cleaned from all files. |

### Queued Reconciliation (requires PRD updates)

| Item | PRDs Involved | Status | Details |
|---|---|---|---|
| **Company Management Custom Objects reconciliation** | Company Mgmt, Custom Objects | **Queued** | Company PRD needs V2 rewrite to align with Custom Objects (prefixed ULIDs, field registry, relation types, event sourcing). Similar scope to Events V2 rewrite. Terminology standardization complete; structural reconciliation remains. |
| **Communications attachment migration** | Communications, Documents | **Queued** | Communications PRD Section 12 (`communication_attachments`) superseded by Documents PRD `communication_documents` relation. Needs Communications V3 update. Phase 3 of Documents roadmap. |
| **Company Management entity_assets migration** | Company Mgmt, Documents | **Queued** | Company Management PRD `entity_assets` table superseded by Documents PRD. Profile assets (logos, headshots, banners) become Document entities. Needs Company Mgmt V2 update. Phase 3 of Documents roadmap. |
| **Custom Objects PRD Topic removal** | Custom Objects, Conversations V3 | **Queued** | Custom Objects PRD still references `top_` prefix for Topic system object type. Topic needs to be removed from the system object type registry and cross-PRD reconciliation notes. |

### Open Items

| Item | PRDs Involved | Status | Notes |
|---|---|---|---|
| **Alert system ownership** | Conversations, Views, Data Sources | **Needs clarification** | Conversations PRD defines alerts. Views PRD defines view-to-alert promotion. Data Sources PRD defines queries that alerts execute. The alert execution engine's home PRD should be clarified. |

---

## Suggested Development Order

Based on dependency analysis (all reconciliation complete except Company Management):

1. **Company Management V2** — Reconcile with Custom Objects framework (prefixed ULIDs, field registry, relation types, event sourcing). Similar effort to Events V2.
2. **Email Provider Sync PRD** — First channel child PRD. Gmail, Outlook, IMAP adapters; dual-track parsing pipeline; email-specific triage. Parent (Communications PRD) is complete.
3. **AI Learning & Classification PRD** — Requirements established by Conversations PRD. Depends on Communications (triage correction signals) and Conversations (assignment correction signals).
4. **SMS/MMS PRD** — Second channel child PRD. Provider selection still open (Twilio vs. OpenPhone).

---

## Project File Management

### Files to Add

| File | Source |
|---|---|
| `gui-functional-requirements-prd_V2.md` | Created 2026-02-21 (full structural rewrite, terminology standard) |
| `adaptive-grid-intelligence-prd_V2.md` | Created 2026-02-21 (terminology alignment) |
| `views-grid-prd_V5.md` | Created 2026-02-22 (terminology alignment) |
| `custom-objects-prd_v2.md` | Created 2026-02-22 (Field Groups → Attribute Cards alignment) |
| `contact-management-prd_V5.md` | Created 2026-02-22 (terminology alignment) |
| `communications-prd_V3.md` | Created 2026-02-22 (mojibake cleanup, link alignment, glossary cross-ref) |
| `conversations-prd_V4.md` | Created 2026-02-22 (mojibake cleanup, link alignment, glossary cross-ref) |
| `events-prd_V3.md` | Created 2026-02-22 (mojibake cleanup, link alignment, Attribute Cards ref, glossary cross-ref) |
| `notes-prd_V3.md` | Created 2026-02-22 (mojibake cleanup, link alignment, glossary cross-ref) |
| `tasks-prd_V2.md` | Created 2026-02-22 (mojibake cleanup, link alignment, Activity Card ref, glossary cross-ref) |
| `documents-prd_V2.md` | Created 2026-02-22 (mojibake cleanup, link alignment, glossary cross-ref) |
| `projects-prd_V3.md` | Created 2026-02-22 (mojibake cleanup, link alignment, glossary cross-ref) |
| `outbound-email-prd_V2.md` | Created 2026-02-22 (link alignment, glossary cross-ref) |
| `permissions-sharing-prd_V2.md` | Created 2026-02-22 (mojibake cleanup, link alignment, glossary cross-ref) |
| `company-management-prd_V1.md` | Created 2026-02-22 (formalized version number, mojibake cleanup, link alignment, glossary cross-ref) |
| `data-sources-prd_V1.md` | Created 2026-02-22 (formalized version number, mojibake cleanup, link alignment, Detail Panel capitalization, glossary cross-ref) |
| `email_stripping_V1.md` | Created 2026-02-22 (formalized version number, mojibake cleanup) |
| `prd-index_V9.md` | This file (replaces V8) |

### Files to Remove

| File | Reason |
|---|---|
| `email-conversations-prd.md` | Superseded by Communications + Conversations PRDs |
| `custom-objects-prd.md` | Superseded by `custom-objects-prd_v2.md` |
| `custom-objects-prd_v1.md` | Superseded by `custom-objects-prd_v2.md` |
| `gui-functional-requirements-prd_V1.md` | Superseded by V2 |
| `adaptive-grid-intelligence-prd_V1.md` | Superseded by V2 |
| `views-grid-prd_V3.md` | Superseded by V5 |
| `views-grid-prd_V4.md` | Superseded by V5 |
| `contact-management-prd_V4.md` | Superseded by V5 |
| `communications-prd_V2.md` | Superseded by V3 |
| `conversations-prd_V3.md` | Superseded by V4 |
| `events-prd_V2.md` | Superseded by V3 |
| `notes-prd_V2.md` | Superseded by V3 |
| `tasks-prd_V1.md` | Superseded by V2 |
| `documents-prd_V1.md` | Superseded by V2 |
| `projects-prd_V2.md` | Superseded by V3 |
| `outbound-email-prd_V1.md` | Superseded by V2 |
| `permissions-sharing-prd_V1.md` | Superseded by V2 |
| `company-management-prd.md` | Superseded by `company-management-prd_V1.md` |
| `data-sources-prd.md` | Superseded by `data-sources-prd_V1.md` |
| `email_stripping.md` | Superseded by `email_stripping_V1.md` |
| `glossary_V1.md` | Superseded by V3 |
| `glossary_V2.md` | Superseded by V3 |
| `prd-index_V3.md` through `prd-index_V8.md` | Superseded by V9 |

---

## Workflow Notes

**PRD Development:** Use dedicated Claude.ai chats (this project) for conceptual PRD development. One chat per PRD for clean context.

**Implementation Planning:** Use Claude Code for implementation plans against the actual codebase. Claude Code reads PRDs and maps concepts to real code.

**Decision Flow:** When Claude Code makes architectural decisions that resolve PRD open questions or affect PRD assumptions, capture them as updates to this index (Cross-PRD Decisions table) or as memory edits.

---

*This index is updated after each PRD development session. It serves as the starting context for any new PRD chat.*
