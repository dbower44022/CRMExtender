# CRMExtender — PRD Index

**Version:** 11.0
**Last Updated:** 2026-02-23
**Purpose:** Living index of all Product Requirements Documents and Technical Design Documents for CRMExtender. Reference this at the start of any PRD development session for orientation.

> **V11.0 (2026-02-23):** Decomposed Company Management PRD (1,380 lines) into Company Entity Base PRD + 6 Action Sub-PRDs (Domain Resolution, Merge, Hierarchy, Enrichment, Intelligence & Scoring, Social Profiles) + Company Entity TDD. Follows same V2 methodology pattern as Contact entity decomposition: field metadata, Key Processes, embedded task/test plans. Monolithic company-management-prd.md retained as superseded reference.

> **V10.0 (2026-02-23):** Added Product TDD and Contact Entity TDD to status tracking. Added Contact Entity Base PRD and six Contact Action Sub-PRDs as hierarchical children of Contact Management. Updated methodology guide to V2. Added new terms to glossary (V4). Updated template-tdd to V2 (living document approach) and template-product-tdd to V2 (matches actual structure). Migrated all PRD system documents from `docs/` to `PRDs/` at repo root. Removed version suffixes from filenames — Git provides version control. Replaced Retired table and Files to Add/Remove with Git-based version history.

---

## Platform Overview

CRMExtender (also called Contact Intelligence Manager) is a comprehensive CRM platform providing deep relationship intelligence and unified communication tracking. The system targets sales professionals, entrepreneurs, and service providers. Key differentiators include unified multi-channel inbox, AI conversation intelligence, cross-channel conversation stitching, and sophisticated relationship tracking.

**Tech Stack:** Flutter frontend (cross-platform), Python FastAPI backend, PostgreSQL (event-sourced, schema-per-tenant), Neo4j (relationship graph), SQLite (offline read), Meilisearch (search).

---

## PRD & TDD Status Summary

| Document | Version | File | Status | Date |
|---|---|---|---|---|
| **Product Level** | | | | |
| PRD Methodology Guide | 2.0 | `prd-methodology-guide.md` | Updated — Key Processes, field metadata, † convention | 2026-02-23 |
| Product TDD | 1.0 | `product-tdd.md` | Draft — 13 sections, living document | 2026-02-23 |
| GUI Functional Requirements | 2.0 | `gui-functional-requirements-prd.md` | Draft — Terminology standardized | 2026-02-21 |
| Custom Objects | 2.0 | `custom-objects-prd.md` | Draft — Terminology standardized | 2026-02-22 |
| Communications | 3.0 | `communications-prd.md` | Draft — Terminology standardized | 2026-02-22 |
| Conversations | 4.0 | `conversations-prd.md` | Draft — Terminology standardized | 2026-02-22 |
| Contact Management | 5.0 | `contact-management-prd.md` | Draft — Terminology standardized | 2026-02-22 |
| └ Contact Entity Base | 9.0 | `contact-entity-base-prd.md` | Draft — V2 methodology (field metadata, Key Processes) | 2026-02-23 |
| &nbsp;&nbsp;└ Contact Entity TDD | 1.0 | `contact-entity-tdd.md` | Draft — Living document, 9 sections | 2026-02-23 |
| └ Identity Resolution | 2.0 | `contact-identity-resolution-prd.md` | Draft — Key Processes added | 2026-02-23 |
| └ Merge & Split | 2.0 | `contact-merge-split-prd.md` | Draft — Key Processes added | 2026-02-23 |
| └ Import & Export | 2.0 | `contact-import-export-prd.md` | Draft — Key Processes added | 2026-02-23 |
| └ Enrichment | 2.0 | `contact-enrichment-prd.md` | Draft — Key Processes added | 2026-02-23 |
| └ AI Intelligence | 2.0 | `contact-ai-intelligence-prd.md` | Draft — Key Processes added | 2026-02-23 |
| └ Relationship Intelligence | 2.0 | `contact-relationship-intelligence-prd.md` | Draft — Key Processes added | 2026-02-23 |
| Company Management | 1.0 | `company-management-prd.md` | Superseded — decomposed into Entity Base + 6 Sub-PRDs + TDD | 2026-02-23 |
| └ Company Entity Base | 1.0 | `company-entity-base-prd.md` | Draft — V2 methodology (field metadata, Key Processes) | 2026-02-23 |
| &nbsp;&nbsp;└ Company Entity TDD | 1.0 | `company-entity-tdd.md` | Draft — Living document, 9 sections | 2026-02-23 |
| └ Domain Resolution | 1.0 | `company-domain-resolution-prd.md` | Draft — Key Processes, task/test plan | 2026-02-23 |
| └ Duplicate Detection & Merging | 1.0 | `company-merge-prd.md` | Draft — Key Processes, task/test plan | 2026-02-23 |
| └ Company Hierarchy | 1.0 | `company-hierarchy-prd.md` | Draft — Key Processes, task/test plan | 2026-02-23 |
| └ Enrichment Pipeline | 1.0 | `company-enrichment-prd.md` | Draft — Key Processes, task/test plan | 2026-02-23 |
| └ Intelligence & Scoring | 1.0 | `company-intelligence-prd.md` | Draft — Key Processes, task/test plan | 2026-02-23 |
| └ Social Media Profiles | 1.0 | `company-social-profiles-prd.md` | Draft — Key Processes, task/test plan | 2026-02-23 |
| Event Management | 3.0 | `events-prd.md` | Draft — Terminology standardized | 2026-02-22 |
| Notes | 3.0 | `notes-prd.md` | Draft — Terminology standardized | 2026-02-22 |
| Tasks | 2.0 | `tasks-prd.md` | Draft — Terminology standardized | 2026-02-22 |
| Documents | 2.0 | `documents-prd.md` | Draft — Terminology standardized | 2026-02-22 |
| Projects | 3.0 | `projects-prd.md` | Draft — Terminology standardized | 2026-02-22 |
| Outbound Email | 2.0 | `outbound-email-prd.md` | Draft — Terminology standardized | 2026-02-22 |
| Views & Grid | 5.0 | `views-grid-prd.md` | Draft — Terminology standardized | 2026-02-22 |
| Data Sources | 1.0 | `data-sources-prd.md` | Draft — Terminology standardized | 2026-02-22 |
| Permissions & Sharing | 2.0 | `permissions-sharing-prd.md` | Draft — Terminology standardized | 2026-02-22 |
| Adaptive Grid Intelligence | 2.0 | `adaptive-grid-intelligence-prd.md` | Draft — Terminology standardized | 2026-02-22 |
| Master Glossary | 4.0 | `glossary.md` | Active — Key Process, field metadata, † caching terms added | 2026-02-23 |
| Email Parsing & Content Extraction | 1.0 | `email-stripping.md` | Technical spec — Mojibake cleaned | 2026-02-22 |
| Email Provider Sync | — | — | **Planned** — parent (Communications) complete | — |
| SMS/MMS | — | — | **Planned** — parent (Communications) complete | — |
| Voice/VoIP | — | — | **Planned** — parent (Communications) complete | — |
| Video Meetings | — | — | **Planned** — parent (Communications) complete | — |
| AI Learning & Classification | — | — | **Planned** — requirements established in Conversations PRD | — |
| Contact Intelligence | — | — | **Planned** — depends on Contact Mgmt + Communications | — |

### Version History

Document version history is managed by Git. Previous versions of any document can be accessed via `git log --follow PRDs/<filename>`. The version number inside each document's header records the current logical version.

**Notable version milestones:**
- 2026-02-18: Communication & Conversation Intelligence PRD decomposed into Communications + Conversations PRDs
- 2026-02-19: Topic entity eliminated; Projects PRD extracted from Conversations PRD
- 2026-02-21: GUI terminology standardization (V2); Adaptive Grid Intelligence terminology alignment
- 2026-02-22: Full ecosystem terminology alignment across all PRDs; Custom Objects V2; mojibake cleanup
- 2026-02-23: PRD Methodology V2 (Key Processes, field metadata, † caching convention); Product TDD and Contact Entity TDD created; Contact entity decomposed into Entity Base PRD + 6 Action Sub-PRDs; Company entity decomposed into Entity Base PRD + 6 Action Sub-PRDs + TDD; migrated from versioned filenames to Git-based versioning

---

## Completed PRDs

### 1. Custom Objects

**File:** `custom-objects-prd.md`
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

**File:** `communications-prd.md`
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

**File:** `conversations-prd.md`
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

**File:** `contact-management-prd.md`
**Scope:** The foundational entity layer. Defines contacts and companies as living intelligence objects with event-sourced history, multi-identifier identity model, enrichment, OSINT, and relationship intelligence. V5 adds terminology standardization and cross-PRD link alignment.

**Decomposed documents:** The Contact entity is fully decomposed per methodology V2:

| Document | File | Version | Description |
|---|---|---|---|
| Contact Entity Base PRD | `contact-entity-base-prd.md` | 9.0 | Entity definition, field registry with Editable/Sortable/Filterable metadata, relationships, lifecycle, Key Processes, action catalog |
| Contact Entity TDD | `contact-entity-tdd.md` | 1.0 | Read model, identifier model, employment history, display name, status transitions, phone normalization. Living document with Claude Code placeholder section. |
| Identity Resolution Sub-PRD | `contact-identity-resolution-prd.md` | 2.0 | Multi-identifier matching, confidence scoring, Key Processes |
| Merge & Split Sub-PRD | `contact-merge-split-prd.md` | 2.0 | Contact merge/split workflows, audit trails, Key Processes |
| Import & Export Sub-PRD | `contact-import-export-prd.md` | 2.0 | CSV import, Google Contacts sync, export formats, Key Processes |
| Enrichment Sub-PRD | `contact-enrichment-prd.md` | 2.0 | Apollo/Clearbit/PDL adapters, enrichment pipeline, Key Processes |
| AI Intelligence Sub-PRD | `contact-ai-intelligence-prd.md` | 2.0 | AI briefings, tag suggestions, NL search, Key Processes |
| Relationship Intelligence Sub-PRD | `contact-relationship-intelligence-prd.md` | 2.0 | Neo4j graph, relationship scoring, influence mapping, Key Processes |

**Key sections (monolithic PRD):**

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

**Reconciliation status:** Fully reconciled with Custom Objects PRD as of V3/V4. Terminology standardized as of V5. Entity Base PRD V9 applies methodology V2 (field metadata, Key Processes). Six Action Sub-PRDs at V2 with Key Processes. Contact Entity TDD V1 established as living document.

---

### 5. Company Management

**File:** `company-management-prd.md` (superseded — retained as historical reference)
**Scope:** Company as a CRM entity with firmographic data, domain-based resolution, enrichment, hierarchy, scoring, and social media tracking.

> **Note:** The monolithic Company Management PRD (1,380 lines) has been decomposed into an Entity Base PRD, Entity TDD, and six Action Sub-PRDs following the V2 methodology. The original file is retained in the repository for reference; all active development should use the decomposed documents.

**Decomposed documents:** The Company entity is fully decomposed per methodology V2:

| Document | File | Description |
|---|---|---|
| Company Entity Base PRD | `company-entity-base-prd.md` | Entity definition, field registry (with Editable/Sortable/Filterable metadata), relationships, lifecycle, Key Processes, Action Catalog |
| Company Entity TDD | `company-entity-tdd.md` | Read model table DDL, identifiers model, shared tables (addresses, phones, emails), asset storage, event sourcing, Neo4j graph sync, score storage |
| Domain Resolution Sub-PRD | `company-domain-resolution-prd.md` | Domain extraction, normalization, public domain exclusion, auto-creation, contact linking, identifier management |
| Merge Sub-PRD | `company-merge-prd.md` | Domain-based duplicate detection, merge preview, merge execution, entity reassignment, audit trail, split (undo) |
| Hierarchy Sub-PRD | `company-hierarchy-prd.md` | Parent/subsidiary/division/acquisition/spinoff relationships, Relation Type definition, temporal tracking, communication separation |
| Enrichment Sub-PRD | `company-enrichment-prd.md` | Three-tier source architecture (website scraper, Wikidata, paid APIs), provider interface, triggers, run tracking, confidence/conflict resolution, overwrite guard |
| Intelligence & Scoring Sub-PRD | `company-intelligence-prd.md` | Five-factor relationship strength scoring, time decay, factor transparency, derived metrics, intelligence views |
| Social Profiles Sub-PRD | `company-social-profiles-prd.md` | Social media tracking (LinkedIn, Twitter, Facebook, GitHub, Instagram), monitoring tiers, change detection |

---

### 6. Event Management

**File:** `events-prd.md`
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

**File:** `notes-prd.md`
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

**File:** `tasks-prd.md`
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

**File:** `documents-prd.md`
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

**File:** `projects-prd.md`
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

**File:** `views-grid-prd.md`
**Scope:** The primary data interaction layer. Polymorphic, entity-agnostic framework for displaying, filtering, sorting, grouping, and editing any entity type through multiple view types. V5 adds Card-Based Architecture terminology for row expansion and Detail Panel references.

**Key sections:**

- Core concepts (Data Source separation, entity-agnostic rendering)
- View types: List/Grid, Calendar, Timeline, Board/Kanban
- Column system (direct, relation traversal, computed) — extended by [Adaptive Grid Intelligence PRD](adaptive-grid-intelligence-prd.md) for content-aware auto-sizing
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

**File:** `data-sources-prd.md`
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

**File:** `permissions-sharing-prd.md`
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

**File:** `email-stripping.md`
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

**File:** `adaptive-grid-intelligence-prd.md`
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

**File:** `gui-functional-requirements-prd.md`
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

**File:** `outbound-email-prd.md`
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

**Scope:** Gmail, Outlook, IMAP provider adapters; OAuth flows; email sync pipeline (initial, incremental, manual); email parsing & content extraction (dual-track pipeline from `email-stripping.md`); email-specific triage patterns; email threading models per provider.

**Parent:** Communications PRD (now complete — defines the provider adapter interface and common schema)
**Key input:** `email-stripping.md` (technical spec for dual-track parsing pipeline)
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
| **Company Management decomposition** | Company Mgmt, Custom Objects | **Completed** | Company PRD decomposed into Entity Base PRD + 6 Sub-PRDs + TDD. Aligned with Custom Objects framework (prefixed ULIDs, field registry, relation types, event sourcing). V2 methodology applied. |
| **Communications attachment migration** | Communications, Documents | **Queued** | Communications PRD Section 12 (`communication_attachments`) superseded by Documents PRD `communication_documents` relation. Needs Communications V3 update. Phase 3 of Documents roadmap. |
| **Company Management entity_assets migration** | Company Mgmt, Documents | **Addressed** | Company Entity TDD documents content-addressable asset storage (Section 5). Documents PRD migration path deferred to Documents PRD roadmap Phase 3. |
| **Custom Objects PRD Topic removal** | Custom Objects, Conversations V3 | **Queued** | Custom Objects PRD still references `top_` prefix for Topic system object type. Topic needs to be removed from the system object type registry and cross-PRD reconciliation notes. |

### Open Items

| Item | PRDs Involved | Status | Notes |
|---|---|---|---|
| **Alert system ownership** | Conversations, Views, Data Sources | **Needs clarification** | Conversations PRD defines alerts. Views PRD defines view-to-alert promotion. Data Sources PRD defines queries that alerts execute. The alert execution engine's home PRD should be clarified. |

---

## Suggested Development Order

Based on dependency analysis (all entity reconciliation complete):

1. ~~**Company Management V2**~~ — **Completed.** Decomposed into Entity Base PRD + 6 Sub-PRDs + TDD.
2. **Email Provider Sync PRD** — First channel child PRD. Gmail, Outlook, IMAP adapters; dual-track parsing pipeline; email-specific triage. Parent (Communications PRD) is complete.
3. **AI Learning & Classification PRD** — Requirements established by Conversations PRD. Depends on Communications (triage correction signals) and Conversations (assignment correction signals).
4. **SMS/MMS PRD** — Second channel child PRD. Provider selection still open (Twilio vs. OpenPhone).

---

## Project File Management

All PRD system documents live in the `PRDs/` directory at the repository root. Templates live in `PRDs/Templates/`. Non-PRD documentation (guides, architecture notes, AI prompts, diagrams) remains in `docs/`.

Version history is managed by Git. Filenames do not include version numbers — the version is recorded inside each document's header. Previous versions are accessible via Git history.

```
PRDs/
├── prd-index.md                              # This file — navigation hub
├── prd-methodology-guide.md                  # How to write PRDs and TDDs
├── glossary.md                               # Master glossary
├── product-tdd.md                            # Global technology decisions
├── custom-objects-prd.md                     # Entity model foundation
├── gui-functional-requirements-prd.md        # Application shell & navigation
├── contact-management-prd.md                 # Contact Management (monolithic)
├── contact-entity-base-prd.md                # Contact entity definition
├── contact-entity-tdd.md                     # Contact technical decisions
├── contact-identity-resolution-prd.md        # Identity resolution sub-PRD
├── contact-merge-split-prd.md                # Merge & split sub-PRD
├── contact-import-export-prd.md              # Import & export sub-PRD
├── contact-enrichment-prd.md                 # Enrichment sub-PRD
├── contact-ai-intelligence-prd.md            # AI intelligence sub-PRD
├── contact-relationship-intelligence-prd.md  # Relationship intelligence sub-PRD
├── company-management-prd.md                 # Company Management (monolithic, superseded)
├── company-entity-base-prd.md                # Company entity definition
├── company-entity-tdd.md                     # Company technical decisions
├── company-domain-resolution-prd.md          # Domain resolution sub-PRD
├── company-merge-prd.md                      # Duplicate detection & merging sub-PRD
├── company-hierarchy-prd.md                  # Company hierarchy sub-PRD
├── company-enrichment-prd.md                 # Enrichment pipeline sub-PRD
├── company-intelligence-prd.md               # Intelligence & scoring sub-PRD
├── company-social-profiles-prd.md            # Social media profiles sub-PRD
├── communications-prd.md
├── conversations-prd.md
├── events-prd.md
├── notes-prd.md
├── tasks-prd.md
├── documents-prd.md
├── projects-prd.md
├── outbound-email-prd.md
├── views-grid-prd.md
├── data-sources-prd.md
├── permissions-sharing-prd.md
├── adaptive-grid-intelligence-prd.md
├── email-stripping.md                        # Technical spec
└── Templates/
    ├── template-product-prd.md
    ├── template-product-tdd.md
    ├── template-entity-base-prd.md
    ├── template-entity-ui-prd.md
    ├── template-tdd.md
    ├── template-action-sub-prd.md
    ├── template-gui-standards.md
    └── template-prd-index.md
```

---

## Workflow Notes

**PRD Development:** Use dedicated Claude.ai chats (this project) for conceptual PRD development. One chat per PRD for clean context.

**Implementation Planning:** Use Claude Code for implementation plans against the actual codebase. Claude Code reads PRDs and maps concepts to real code.

**Decision Flow:** When Claude Code makes architectural decisions that resolve PRD open questions or affect PRD assumptions, capture them as updates to this index (Cross-PRD Decisions table) or as memory edits.

---

*This index is updated after each PRD development session. It serves as the starting context for any new PRD chat.*
