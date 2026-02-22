# CRMExtender ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â PRD Index

**Version:** 7.0
**Last Updated:** 2026-02-19
**Purpose:** Living index of all Product Requirements Documents for CRMExtender. Reference this at the start of any PRD development session for orientation.

---

## Platform Overview

CRMExtender (also called Contact Intelligence Manager) is a comprehensive CRM platform providing deep relationship intelligence and unified communication tracking. The system targets sales professionals, entrepreneurs, and service providers. Key differentiators include unified multi-channel inbox, AI conversation intelligence, cross-channel conversation stitching, and sophisticated relationship tracking.

**Tech Stack:** Flutter frontend (cross-platform), Python FastAPI backend, PostgreSQL (event-sourced, schema-per-tenant), Neo4j (relationship graph), SQLite (offline read), Meilisearch (search).

---

## PRD Status Summary

| PRD | Version | File | Status | Date |
|---|---|---|---|---|
| Custom Objects | 1.0 | `custom-objects-prd.md` | Draft ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â Foundation PRD | 2026-02-17 |
| Communications | 2.0 | `communications-prd_V2.md` | Draft ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â Reconciled with Custom Objects | 2026-02-19 |
| Conversations | 3.0 | `conversations-prd_V3.md` | Draft ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â Reconciled with Custom Objects | 2026-02-19 |
| Contact Management | 4.0 | `contact-management-prd_V4.md` | Draft ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â Reconciled with Custom Objects | 2026-02-17 |
| Company Management | 1.0 | `company-management-prd.md` | Draft ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â Needs V2 reconciliation | 2026-02-09 |
| Event Management | 2.0 | `events-prd_V2.md` | Draft ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â Reconciled with Custom Objects | 2026-02-17 |
| Notes | 2.0 | `notes-prd_V2.md` | Draft ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â Reconciled with Custom Objects | 2026-02-17 |
| Tasks | 1.0 | `tasks-prd_V1.md` | Draft Ã¢â‚¬â€ Reconciled with Custom Objects | 2026-02-18 |
| Documents | 1.0 | `documents-prd_V1.md` | Draft -- Reconciled with Custom Objects | 2026-02-18 |
| Projects | 2.0 | `projects-prd_V2.md` | Draft -- Reconciled with Custom Objects + Conversations V3 | 2026-02-19 |
| Views & Grid | 3.0 | `views-grid-prd_V3.md` | Draft ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â Complete | 2026-02-15 |
| Data Sources | 1.0 | `data-sources-prd.md` | Draft ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â Complete | 2026-02-14 |
| Permissions & Sharing | 1.0 | `permissions-sharing-prd_V1.md` | Draft ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â Complete | 2026-02-16 |
| Email Parsing & Content Extraction | ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â | `email_stripping.md` | Technical spec | 2026-02-07 |
| Email Provider Sync | ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â | ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â | **Planned** ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â parent (Communications) complete | ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â |
| SMS/MMS | ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â | ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â | **Planned** ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â parent (Communications) complete | ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â |
| Voice/VoIP | ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â | ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â | **Planned** ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â parent (Communications) complete | ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â |
| Video Meetings | ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â | ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â | **Planned** ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â parent (Communications) complete | ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â |
| AI Learning & Classification | ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â | ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â | **Planned** ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â requirements established in Conversations PRD | ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â |
| Contact Intelligence | ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â | ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â | **Planned** ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â depends on Contact Mgmt + Communications | ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â |

### Retired / Superseded Documents

| Document | File | Superseded By | Date |
|---|---|---|---|
| Communication & Conversation Intelligence PRD v2.0 | `email-conversations-prd.md` | `communications-prd_V2.md` + `conversations-prd_V3.md` | 2026-02-18 |
| Conversations PRD V1-V2 | `conversations-prd_V1.md`, `conversations-prd_V2.md` | `conversations-prd_V3.md` | 2026-02-19 |
| Communications PRD V1 | `communications-prd_V1.md` | `communications-prd_V2.md` | 2026-02-19 |
| Projects PRD V1 | `projects-prd_V1.md` | `projects-prd_V2.md` | 2026-02-19 |

---

## Completed PRDs

### 1. Custom Objects

**File:** `custom-objects-prd.md`
**Scope:** The entity model foundation. Defines the Unified Object Model where system entities (Contact, Conversation, Company, etc.) and user-created entities are instances of the same framework. Covers object type definition, field registry, field type system, relation model, physical storage architecture, DDL management, and event sourcing.

**Key sections:**

- Unified Object Model (system and custom entities as instances of the same ObjectType framework)
- Object type definition model (identity, slug, type prefix, schema version, lifecycle)
- Universal fields (id, tenant_id, created_at/by, updated_at/by, archived_at)
- Field registry (field definitions, slugs as column names, ordering, limits)
- Field type system (15 Phase 1 types, 2 Phase 2: Formula, Rollup)
- Field type conversion matrix (safe conversions only, with preview wizard)
- Field groups (detail view layout organization)
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

- **Unified Object Model** ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â system entities are pre-installed object types with `is_system` flag, protected core fields, and registered behaviors. Custom entities are equal citizens at the storage, query, and rendering layers.
- **Dedicated typed tables per entity type** ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â every entity type gets its own PostgreSQL table with native typed columns. Fields map to columns. DDL at runtime via ALTER TABLE.
- **Schema-per-tenant** ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â each tenant gets its own PostgreSQL schema with entity tables, event tables, and junction tables.
- **Full event sourcing for all entity types** ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â per-entity-type event tables. Same audit trail and point-in-time reconstruction for custom and system entities.
- **First-class Relation Types** ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â all three cardinalities (1:1, 1:many, many:many) from Phase 1. Bidirectional or unidirectional. Self-referential supported. Configurable cascade (nullify default, restrict, cascade archive).
- **Relation metadata** ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â additional attributes on relationship instances (role, strength, start date, notes).
- **Neo4j graph sync** ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â optional flag per relation type.
- **Permission-gated entity type creation** ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â Object Creator permission (not admin-only).
- **50 custom entity types per tenant** limit. **200 fields per entity type** limit.

**Gutter business test cases:** Jobs, Properties, Service Areas, Estimates.

**Open questions:** 12 (DDL timing, reserved words, record limits, field templates, import/export, relation limits, event retention, multi-line storage, offline sync, computed defaults, relation modification, Neo4j selective fields)

---

### 2. Communications

**File:** `communications-prd_V2.md`
**Scope:** The atomic interaction record. Defines Communication as a system object type, the common schema all channels normalize to, the provider adapter framework, contact association, triage filtering, multi-account management, attachments, and storage. Foundation for channel-specific child PRDs. V2 adds Published Summary architecture (Section 7).

> **Extracted from:** Communication & Conversation Intelligence PRD v2.0 (the Communications half of the decomposition).

**Key sections:**

- Communication as system object type (`com_` prefix, full field registry)
- Channel types: `email`, `sms`, `mms`, `phone_recorded`, `phone_manual`, `video_recorded`, `video_manual`, `in_person`, `note`
- Communication entry points (auto-synced vs. manual)
- Provider account framework (personal and shared accounts, shared inbox attribution)
- Provider adapter architecture (interface, sync modes, reliability, audit trail)
- Communication Participants Relation Type (CommunicationÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢Contact, many-to-many with role/address metadata)
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
- `conversation_id` as FK column (not Relation Type) ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â simpler for strict many:1
- Three-tier content model: `content_raw`, `content_html`, `content_clean`
- Published Summary architecture (V2): rich text summaries per channel type, revision history, Conversation timeline renders by reference
- Channel-specific parsing delegated to child PRDs
- `note` channel type is distinct from Notes system object type (interactions vs. commentary)
- Manual logged interactions (unrecorded calls, in-person meetings) are Communications, not Notes
- Provider account framework shared across all integration types

**Channel child PRDs:**

| Child PRD | Scope | Status |
|---|---|---|
| Email Provider Sync PRD | Gmail, Outlook, IMAP adapters; dual-track parsing; email threading; email-specific triage | Planned ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â parent complete |
| SMS/MMS PRD | Twilio/OpenPhone adapters; message sync; phone number resolution; MMS media | Planned |
| Voice/VoIP PRD | Call recording integration; transcription pipeline; provider adapters | Planned |
| Video Meetings PRD | Zoom/Teams/Meet integration; transcript capture; recording management | Planned |

**Open questions:** 9 (attachment storage, real-time sync infra, email sending, shared mailbox, merge/split, opt-out granularity, SMS provider, speech-to-text, Slack/Teams model)

---

### 3. Conversations

**File:** `conversations-prd_V3.md`
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
- User-defined alerts (no defaults, viewÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢alert architecture, frequency/aggregation/delivery)
- Event sourcing for Conversations (standard and aggregate)
- API design (CRUD for conversations, membership, entity associations, intelligence, review workflow)

**Key decisions made:**

- Single Conversation entity with `is_aggregate` flag (replacing Topic + Conversation as separate types). Projects extracted to separate PRD. ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â not one hierarchy entity
- Derived participant list (supplemented by explicit ConversationÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢Contact Relation Type ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â avoids duplication)
- Optional hierarchy at every level ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â communications can be unassigned, conversations don't need topics
- Aggregate nesting unlimited with acyclic enforcement; entity associations via Relation Types, not FK columns
- AI biased toward `open` status for multi-message exchanges
- Configurable stale/closed thresholds per conversation (default: 14/30 days)
- No default alerts ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â user defines all notifications
- Segmentation uses split/reference model (original never modified, segments are cross-references)

**Open questions:** 8 (aggregate nesting depth, conversation merge/split, cross-account merging, calendar linking, Slack/Teams model, AI cost management, merge detection, opt-out granularity)

---

### 4. Contact Management & Intelligence

**File:** `contact-management-prd_V4.md`
**Scope:** The foundational entity layer. Defines contacts and companies as living intelligence objects with event-sourced history, multi-identifier identity model, enrichment, OSINT, and relationship intelligence.

**Key sections:**

- Contact as system object type (`con_` prefix, field registry)
- Contact data model (dedicated table managed by object type framework)
- Company data model (`cmp_` prefix)
- Identity resolution & entity matching (multi-identifier: email, phone, social)
- Employment history as system Relation Type (ContactÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢Company, many-to-many with temporal metadata)
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
- Engagement score is a composite behavioral metric (0.0ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Å“1.0)
- Intelligence score measures data completeness (0.0ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Å“1.0)
- Google People API for bidirectional contact sync (Phase 1)
- Browser extension for LinkedIn/Twitter capture (Phase 2)

**Reconciliation status:** Fully reconciled with Custom Objects PRD as of V3/V4.

---

### 5. Company Management

**File:** `company-management-prd.md`
**Scope:** Company as a CRM entity with firmographic data, domain-based resolution, and relationship to contacts.

> **Note:** This PRD has not yet been reconciled with the Custom Objects framework. Needs V2 rewrite similar to Events V2 (prefixed ULIDs, field registry, relation types, event sourcing).

---

### 6. Event Management

**File:** `events-prd_V2.md`
**Scope:** Event as a system object type for calendar events, meetings, and temporal relationship intelligence.

**Key sections:**

- Event as system object type (`evt_` prefix, full field registry)
- Calendar sync via provider account framework (Google Calendar adapter)
- EventÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬ÂContact Relation Type (`event_attendees`)
- EventÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬ÂConversation Relation Type (`event_conversations`)
- Birthday auto-generation behavior
- Recurrence defaulting behavior
- Event sourcing (`events_events`)
- RSVP tracking

**Reconciliation status:** Fully reconciled with Custom Objects PRD as of V2.

---

### 7. Notes

**File:** `notes-prd_V2.md`
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

**File:** `tasks-prd_V1.md`
**Scope:** Task as a system object type for actionable work items with status workflow, priority, assignees, dependencies, subtask hierarchy, recurrence, and AI action-item extraction.

**Key sections:**

- Task as system object type (`tsk_` prefix, full field registry)
- Status model with user-extensible statuses mapped to four system categories (`not_started`, `active`, `done`, `cancelled`)
- Fixed priority model (urgent, high, medium, low, none) with sort weights
- Unlimited subtask hierarchy via self-referential `parent_task_id` FK
- Universal Attachment Relation (reuses Notes pattern Ã¢â‚¬â€ tasks attach to any entity type)
- TaskÃ¢â€ â€™User Relation Type (`task_user_participation`) with role metadata (assignee, reviewer, watcher)
- Task dependencies via self-referential many:many Relation Type (`task_dependencies`) with `blocked_by` semantics
- Rich text descriptions (behavior-managed content, Notes-aligned architecture, no revision tracking)
- Events-aligned recurrence model (completion-triggered instance generation, RRULE support)
- AI action-item extraction behavior (auto-create tasks from Conversation intelligence)
- Due date reminders and overdue detection behaviors
- Event sourcing (`tasks_events`)
- Full-text search (PostgreSQL `tsvector`/`tsquery`)
- 4-phase roadmap (core Ã¢â€ â€™ full features Ã¢â€ â€™ AI integration Ã¢â€ â€™ advanced)

**Key decisions made:**

- **System object type** Ã¢â‚¬â€ 7 registered behaviors require system entity status (custom objects can't have behaviors)
- **Status categories** Ã¢â‚¬â€ user-extensible status labels mapped to immutable system categories that drive behavioral logic
- **Fixed priority** Ã¢â‚¬â€ not user-extensible; consistency and sort ordering matter more than customization
- **Multiple assignees** Ã¢â‚¬â€ TaskÃ¢â€ â€™User relation type with roles, not single FK
- **Universal Attachment** Ã¢â‚¬â€ reuses Notes pattern; standalone tasks allowed (no required entity link, unlike Notes)
- **Warn-but-allow subtask cascade** Ã¢â‚¬â€ warns on parent completion with open children, does not block or auto-complete
- **Completion-triggered recurrence** Ã¢â‚¬â€ next instance generated when current is completed (not time-triggered like Events)
- **No description revision tracking** Ã¢â‚¬â€ event sourcing captures changes; full revision model deferred unless needed
- **Workspace-visible** Ã¢â‚¬â€ all tasks visible to all members (subject to role-based permissions), unlike Notes' private-by-default model
- **Simple blocking dependencies** Ã¢â‚¬â€ `blocked_by`/`blocks` only; full dependency types (FS/SS/FF/SF) deferred

**Open questions:** 6 (notification subsystem dependency, AI confidence thresholds, recursive rollup scope, due date semantics, subtask ordering, Board View column mapping)

**Reconciliation status:** Fully reconciled with Custom Objects PRD as of V1.

---

### 9. Documents

**File:** `documents-prd_V1.md`
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

**File:** `projects-prd_V2.md`
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

**File:** `views-grid-prd_V3.md`
**Scope:** The primary data interaction layer. Polymorphic, entity-agnostic framework for displaying, filtering, sorting, grouping, and editing any entity type through multiple view types.

**Key sections:**

- Core concepts (Data Source separation, entity-agnostic rendering)
- View types: List/Grid, Calendar, Timeline, Board/Kanban
- Column system (direct, relation traversal, computed)
- Field type registry
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
- Shared views enforce row-level security (sharing definition ÃƒÂ¢Ã¢â‚¬Â°Ã‚Â  sharing data)
- Board view supports swimlanes (matrix of group-by ÃƒÆ’Ã¢â‚¬â€ status)
- Tree view capability added (hierarchical rendering)

**Alignment with Custom Objects PRD:** Views PRD Section 9 (field type rendering) is the presentation layer counterpart to Custom Objects PRD Section 9 (field type data layer). Relation traversal (Views Section 10) operates on Relation Types defined in Custom Objects PRD Section 14. No reconciliation required.

---

### 12. Data Sources

**File:** `data-sources-prd.md`
**Scope:** The query abstraction layer. Reusable, named query definitions that sit between physical storage and views, providing cross-entity queries, dual authoring modes, column registries, and preview detection.

**Key sections:**

- Universal entity ID convention (prefixed IDs: `con_`, `cvr_`, `com_`, etc.)
- Data source definition model (ID, query, column registry, preview config, parameters, refresh policy)
- Visual query builder (5-step: entity ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ joins ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ columns ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ filters ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ sort)
- Raw SQL environment (virtual schema, access rules, validation, parameters)
- Column registry (auto-generated + manual overrides, editability rules)
- Entity detection & preview system (3-layer: auto-detect ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ inference rules ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ manual override)
- Data source ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ view relationship (many-to-one, composition rules)
- Inline editing trace-back (column registry ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ source entity ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ API call)
- System-generated data sources (auto-created per entity type)
- Performance (cursor pagination, EXPLAIN plan analysis)
- 4-phase roadmap

**Key decisions made:**

- Prefixed entity IDs (`con_`, `cvr_`, `com_`, etc.) with ULID ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â adopted platform-wide
- Data sources are reusable across multiple views
- Dual authoring: visual query builder for simple, raw SQL for complex
- Virtual schema mirrors physical schema for query simplicity
- Column registry enables inline editing from any joined query
- System-generated data sources auto-created per entity type
- Schema versioning for breaking change detection

**Alignment with Custom Objects PRD:** Virtual schema composition resolved ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â virtual schema tables = object type slugs, virtual schema columns = field slugs. 1:1 mapping means query engine translation is trivial.

---

### 13. Permissions & Sharing

**File:** `permissions-sharing-prd_V1.md`
**Scope:** Team access controls, role-based permissions, row-level security, shared vs. private data, provider account management, data visibility rules.

**Key sections:**

- Permission model (RBAC with per-object-type granularity)
- Role definitions (Owner, Admin, Member, Read-Only, Custom)
- Object Creator permission (per Custom Objects PRD Section 6.4)
- Row-level security injection into Data Source queries
- Shared view permissions (sharing definition ÃƒÂ¢Ã¢â‚¬Â°Ã‚Â  sharing data)
- Provider account management permissions
- Integration data visibility
- Multi-tenant isolation (schema-per-tenant confirmed)

---

### 14. Email Parsing & Content Extraction

**File:** `email_stripping.md`
**Scope:** Technical specification for the dual-track email parsing pipeline. Covers HTML structural removal and plain-text regex-based extraction.

**Key sections:**

- HTML cleaning pipeline (quote removal, signature detection, disclaimer stripping)
- Plain-text pipeline (reply pattern detection, valediction-based truncation, standalone signature detection)
- Promotional content detection
- Line unwrapping algorithm
- Provider-specific patterns (Gmail, Outlook, Apple Mail)

**Notes:** This is a technical spec, not a conceptual PRD. Companion document to the planned Email Provider Sync PRD. More appropriate for Claude Code reference than PRD development sessions.

---

## Planned PRDs (Not Yet Started)

### Email Provider Sync PRD

**Scope:** Gmail, Outlook, IMAP provider adapters; OAuth flows; email sync pipeline (initial, incremental, manual); email parsing & content extraction (dual-track pipeline from `email_stripping.md`); email-specific triage patterns; email threading models per provider.

**Parent:** Communications PRD (now complete ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â defines the provider adapter interface and common schema)
**Key input:** `email_stripping.md` (technical spec for dual-track parsing pipeline)
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
| Data Source | `dts_` | `data_sources` | Data Sources PRD | ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â |
| View | `viw_` | `views` | Views & Grid PRD | ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â |
| User | `usr_` | `users` | Permissions & Sharing PRD | ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â |
| Segment | `seg_` | `segments` | Contact Management PRD | ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â |

---

## Dependency Map

```
                    ÃƒÂ¢Ã¢â‚¬ÂÃ…â€™ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ‚Â
                    ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬Å¡  CRMExtender PRD     ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬Å¡
                    ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬Å¡  (Parent v1.1)       ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬Å¡
                    ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬ÂÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ‚Â¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ‹Å“
                               ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬Å¡
         ÃƒÂ¢Ã¢â‚¬ÂÃ…â€™ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ‚Â¼ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ‚Â
         ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬Å¡                     ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬Å¡                     ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬Å¡
         ÃƒÂ¢Ã¢â‚¬â€œÃ‚Â¼                     ÃƒÂ¢Ã¢â‚¬â€œÃ‚Â¼                     ÃƒÂ¢Ã¢â‚¬â€œÃ‚Â¼
ÃƒÂ¢Ã¢â‚¬ÂÃ…â€™ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ‚Â ÃƒÂ¢Ã¢â‚¬ÂÃ…â€™ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ‚Â ÃƒÂ¢Ã¢â‚¬ÂÃ…â€™ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ‚Â
ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬Å¡  Custom Objects     ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬Å¡ ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬Å¡  Contact            ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬Å¡ ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬Å¡  Permissions &      ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬Å¡
ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬Å¡  ÃƒÂ¢Ã‹Å“Ã¢â‚¬Â¦ FOUNDATION       ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬Å¡ ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬Å¡  Management         ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬Å¡ ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬Å¡  Sharing            ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬Å¡
ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬Å¡                     ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬Å¡ ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬Å¡                     ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬Å¡ ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬Å¡                     ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬Å¡
ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬Å¡  Entity types,      ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬Å¡ ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬Å¡  System entity      ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬Å¡ ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬Å¡  Roles, RBAC,       ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬Å¡
ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬Å¡  field registry,    ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬Å¡ ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬Å¡  types: Contact,    ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬Å¡ ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬Å¡  row-level security,ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬Å¡
ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬Å¡  relations, storage,ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬Å¡ ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬Å¡  Company            ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬Å¡ ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬Å¡  provider accounts  ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬Å¡
ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬Å¡  event sourcing     ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬Å¡ ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬Å¡                     ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬Å¡ ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬Å¡                     ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬Å¡
ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬ÂÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ‚Â¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ‹Å“ ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬ÂÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ‹Å“ ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬ÂÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ‹Å“
         ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬Å¡
    ÃƒÂ¢Ã¢â‚¬ÂÃ…â€™ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ‚Â´ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ‚Â
    ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬Å¡                             ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬Å¡
    ÃƒÂ¢Ã¢â‚¬â€œÃ‚Â¼                             ÃƒÂ¢Ã¢â‚¬â€œÃ‚Â¼
ÃƒÂ¢Ã¢â‚¬ÂÃ…â€™ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ‚Â  ÃƒÂ¢Ã¢â‚¬ÂÃ…â€™ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ‚Â
ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬Å¡  Communications     ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬Å¡  ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬Å¡  Conversations      ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬Å¡
ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬Å¡  PRD                ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬Å¡  ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬Å¡  PRD                ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬Å¡
ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬Å¡                     ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬Å¡  ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬Å¡                     ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬Å¡
ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬Å¡  Communication      ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬Å¡ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬Å¡  Conversation (cvr_)ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬Å¡
ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬Å¡  entity (com_)      ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬Å¡  ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬Å¡  Aggregate Cvr          ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬Å¡
ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬Å¡  Provider adapters  ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬Å¡  ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬Å¡  Project (prj_)     ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬Å¡
ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬Å¡  Triage pipeline    ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬Å¡  ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬Å¡  AI intelligence    ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬Å¡
ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬Å¡  Contact resolution ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬Å¡  ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬Å¡  Hierarchy model    ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬Å¡
ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬Å¡  Attachments        ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬Å¡  ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬Å¡  Review workflow    ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬Å¡
ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬ÂÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ‚Â¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ‹Å“  ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬Å¡  Views & alerts     ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬Å¡
        ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬Å¡                ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬ÂÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ‹Å“
   ÃƒÂ¢Ã¢â‚¬ÂÃ…â€™ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ‚Â´ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ‚Â
   ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬Å¡    Channel Child PRDs       ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬Å¡
   ÃƒÂ¢Ã¢â‚¬ÂÃ…â€œÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ‚Â¤
   ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬Å¡ Email Provider Sync (planned)ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬Å¡
   ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬Å¡ SMS/MMS (planned)           ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬Å¡
   ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬Å¡ Voice/VoIP (planned)        ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬Å¡
   ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬Å¡ Video Meetings (planned)    ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬Å¡
   ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬ÂÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ‹Å“

Other system object types:
+----------------+  +----------------+  +----------------+  +----------------+
|  Event Mgmt    |  |  Notes PRD     |  |  Tasks PRD     |  |  Documents PRD |
|  PRD (evt_)    |  |  (not_)        |  |  (tsk_)        |  |  (doc_)        |
+----------------+  +----------------+  +----------------+  +----------------+

Cross-cutting PRDs:
ÃƒÂ¢Ã¢â‚¬ÂÃ…â€™ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ‚Â  ÃƒÂ¢Ã¢â‚¬ÂÃ…â€™ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ‚Â
ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬Å¡  Views &     ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬Å¡  ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬Å¡  Data        ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬Å¡
ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬Å¡  Grid PRD    ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬Å¡  ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬Å¡  Sources PRD ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬Å¡
ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬ÂÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ‹Å“  ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬ÂÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ‹Å“
```

**Reading the arrows:** An arrow from A to B means "A depends on B" or "A references B."

**ÃƒÂ¢Ã‹Å“Ã¢â‚¬Â¦ Custom Objects as foundation:** The Custom Objects PRD defines the entity model that Data Sources, Views, Contact Management, Communications, Conversations, Events, Notes, and Tasks all build upon. All entity types (system and custom) are defined through its framework.

---

## Cross-PRD Decisions & Reconciliation Items

### Resolved Items

| Item | PRDs Involved | Resolution |
|---|---|---|
| **Prefixed entity IDs** | Data Sources, Custom Objects, all entity PRDs | Resolved by Custom Objects PRD Section 6.2ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Å“6.3. All entity types use `{prefix}_{ULID}` format. |
| **Event sourcing read model** | Data Sources, Custom Objects, all entity PRDs | Resolved by Custom Objects PRD. Section 17 establishes dedicated typed tables. Section 19 establishes per-entity-type event tables. |
| **Custom entity storage** | Data Sources, Custom Objects | Resolved by Custom Objects PRD. Dedicated typed tables with DDL-at-runtime (Section 17ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Å“18). |
| **Virtual schema composition** | Data Sources, Custom Objects | Resolved by Custom Objects PRD. Virtual schema tables = object type slugs. Columns = field slugs. Trivial translation. |
| **Communication decomposition** | Communications PRD, Conversations PRD | Resolved 2026-02-18. Monolithic `email-conversations-prd.md` decomposed into sibling Communications + Conversations PRDs with channel child PRDs under Communications. Updated 2026-02-19: Conversations PRD V3 eliminated Topic entity, extracted Projects PRD. |
| **Notes vs. Communications boundary** | Communications PRD, Notes PRD | Resolved in Communications PRD Section 6.3. Communications are interaction records; Notes are supplementary commentary. Manual logged interactions are Communications. |
| **Conversation participants** | Conversations PRD, Communications PRD | Resolved in Conversations PRD Section 5.5. Derived from Communication Participants (primarily derived, supplemented by explicit ConversationÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢Contact relation). |

### Completed Reconciliation (PRD updates made)

| Item | PRDs Updated | Completed | Notes |
|---|---|---|---|
| Contact Management `custom_fields` removal | Contact Management V3 | 2026-02-17 | Custom fields via unified field registry |
| Contact entity ID migration to `con_` | Contact Management V2 | 2026-02-17 | Prefixed ULIDs adopted |
| Employment history ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ Relation Type | Contact Management V3 | 2026-02-17 | Junction table with temporal metadata |
| `contacts_current` ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ object type table | Contact Management V3 | 2026-02-17 | `contacts` read model managed by framework |
| Events ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ system object type | Events V2 | 2026-02-17 | Full rewrite from PoC SQLite |
| Notes ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ system object type | Notes V2 | 2026-02-17 | Universal Attachment Relation pattern |
| Communication entities ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ system object types | Communications V1, Conversations V1 | 2026-02-18 | Full decomposition + Custom Objects reconciliation |
| Task Ã¢â€ â€™ system object type | Tasks V1 | 2026-02-18 | Universal Attachment pattern (reuses Notes), status categories, 7 behaviors |
| Document -> system object type | Documents V1 | 2026-02-18 | Universal Attachment pattern, hash-based version control, folder model, 7 behaviors. Defines cross-PRD reconciliation for Communications (attachment migration) and Company Management (entity_assets migration). |

### Queued Reconciliation (requires PRD updates)

| Item | PRDs Involved | Status | Details |
|---|---|---|---|
| **Company Management Custom Objects reconciliation** | Company Mgmt, Custom Objects | **Queued** | Company PRD needs V2 rewrite to align with Custom Objects (prefixed ULIDs, field registry, relation types, event sourcing). Similar scope to Events V2 rewrite. |
| **Communications attachment migration** | Communications, Documents | **Queued** | Communications PRD Section 12 (`communication_attachments`) superseded by Documents PRD `communication_documents` relation. Needs Communications V2 update. Phase 3 of Documents roadmap. |
| **Company Management entity_assets migration** | Company Mgmt, Documents | **Queued** | Company Management PRD `entity_assets` table superseded by Documents PRD. Profile assets (logos, headshots, banners) become Document entities. Needs Company Mgmt V2 update. Phase 3 of Documents roadmap. |
| **Custom Objects PRD Topic removal** | Custom Objects, Conversations V3 | **Queued** | Custom Objects PRD still references `top_` prefix for Topic system object type. Topic needs to be removed from the system object type registry and cross-PRD reconciliation notes. |

### Open Items

| Item | PRDs Involved | Status | Notes |
|---|---|---|---|
| **Alert system ownership** | Conversations, Views, Data Sources | **Needs clarification** | Conversations PRD defines alerts. Views PRD defines view-to-alert promotion. Data Sources PRD defines queries that alerts execute. The alert execution engine's home PRD should be clarified. |

---

## Suggested Development Order

Based on dependency analysis (all reconciliation complete except Company Management):

1. **Company Management V2** ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â Reconcile with Custom Objects framework (prefixed ULIDs, field registry, relation types, event sourcing). Similar effort to Events V2.
2. **Email Provider Sync PRD** ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â First channel child PRD. Gmail, Outlook, IMAP adapters; dual-track parsing pipeline; email-specific triage. Parent (Communications PRD) is complete.
3. **AI Learning & Classification PRD** ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â Requirements established by Conversations PRD. Depends on Communications (triage correction signals) and Conversations (assignment correction signals).
4. **SMS/MMS PRD** ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â Second channel child PRD. Provider selection still open (Twilio vs. OpenPhone).

---

## Project File Management

### Files to Add

| File | Source |
|---|---|
| `tasks-prd_V1.md` | Created 2026-02-18 |
| `documents-prd_V1.md` | Created 2026-02-18 |
| `communications-prd_V2.md` | Created 2026-02-19 (Published Summary architecture) |
| `conversations-prd_V3.md` | Created 2026-02-19 (Topic elimination, aggregate Conversations, Relation Types) |
| `projects-prd_V2.md` | Created 2026-02-19 (Reconciled with Conversations V3) |
| `prd-index_V7.md` | This file (replaces V6) |

### Files to Remove

| File | Reason |
|---|---|
| `email-conversations-prd.md` | Superseded by Communications + Conversations PRDs |
| `prd-index_V3.md` | Superseded by V4 |
| `prd-index_V4.md` | Superseded by V5 |
| `prd-index_V7.md` | Superseded by V6 |

---

## Workflow Notes

**PRD Development:** Use dedicated Claude.ai chats (this project) for conceptual PRD development. One chat per PRD for clean context.

**Implementation Planning:** Use Claude Code for implementation plans against the actual codebase. Claude Code reads PRDs and maps concepts to real code.

**Decision Flow:** When Claude Code makes architectural decisions that resolve PRD open questions or affect PRD assumptions, capture them as updates to this index (Cross-PRD Decisions table) or as memory edits.

---

*This index is updated after each PRD development session. It serves as the starting context for any new PRD chat.*
