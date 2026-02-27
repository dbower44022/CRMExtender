# CRMExtender — PRD Index

**Version:** 20.0
**Last Updated:** 2026-02-27
**Purpose:** Living index of all Product Requirements Documents and Technical Design Documents for CRMExtender. Reference this at the start of any PRD development session for orientation.

> **V20.0 (2026-02-27):** Added Conversation View Sub-PRD (`conversation-view-prd.md`) — Preview Card and full View rendering for standard and aggregate Conversations. Updated Conversation Entity Base PRD action catalog to reference the new sub-PRD.

> **V19.0 (2026-02-23):** Decomposed Custom Objects PRD (1,542 lines) into Framework PRD + 2 Sub-PRDs (Field System, Relation System) + TDD. First framework-level (non-entity) decomposition — subsystem-based rather than entity/action-based.

> **V18.0 (2026-02-23):** Decomposed Projects PRD (850 lines) into Project Entity Base PRD + 1 Action Sub-PRD (Entity Relations & Aggregation) + Project Entity TDD. Follows V2 methodology. Monolithic projects-prd.md retained as superseded reference. **All 9 entity PRDs now decomposed.**

> **V17.0 (2026-02-23):** Decomposed Tasks PRD (1,080 lines) into Task Entity Base PRD + 2 Action Sub-PRDs (Hierarchy/Dependencies/Recurrence, Assignees/Behaviors/AI Intelligence) + Task Entity TDD. Follows V2 methodology. Monolithic tasks-prd.md retained as superseded reference.

> **V16.0 (2026-02-23):** Decomposed Notes PRD (1,200 lines) into Note Entity Base PRD + 2 Action Sub-PRDs (Content/Revisions/Sanitization, Attachments/Mentions/Search) + Note Entity TDD. Follows V2 methodology. Monolithic notes-prd.md retained as superseded reference (includes PoC Appendix).

> **V15.0 (2026-02-23):** Decomposed Events PRD (1,236 lines) into Event Entity Base PRD + 2 Action Sub-PRDs (Participants & Attendance Intelligence, Calendar Sync Pipeline) + Event Entity TDD. Follows V2 methodology. Monolithic events-prd.md retained as superseded reference (includes PoC Appendix).

> **V14.0 (2026-02-23):** Decomposed Documents PRD (1,331 lines) into Document Entity Base PRD + 3 Action Sub-PRDs (Upload/Versioning/Storage, Content Processing Pipeline, Communication & Profile Asset Integration) + Document Entity TDD. Follows V2 methodology. Monolithic documents-prd.md retained as superseded reference.

> **V13.0 (2026-02-23):** Decomposed Conversations PRD (1,171 lines) into Conversation Entity Base PRD + 4 Action Sub-PRDs (Formation & Stitching, AI Intelligence & Review, View Conversation, Views & Alerts) + Conversation Entity TDD. Follows V2 methodology. Monolithic conversations-prd.md retained as superseded reference.

> **V12.0 (2026-02-23):** Decomposed Communications PRD (1,420 lines) into Communication Entity Base PRD + 4 Action Sub-PRDs (Published Summary, Provider & Sync Framework, Participant Resolution, Triage & Filtering) + Communication Entity TDD. Follows V2 methodology: field metadata, Key Processes, embedded task/test plans. Monolithic communications-prd.md retained as superseded reference.

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
| Custom Objects | 2.0 | `custom-objects-prd.md` | Superseded — decomposed into Framework PRD + 2 Sub-PRDs + TDD | 2026-02-23 |
| └ Custom Objects Framework | 1.0 | `custom-objects-framework-prd.md` | Draft — V2 methodology (Key Processes) | 2026-02-23 |
| &nbsp;&nbsp;└ Custom Objects TDD | 1.0 | `custom-objects-tdd.md` | Draft — Living document, 7 sections | 2026-02-23 |
| └ Field System | 1.0 | `custom-objects-field-system-prd.md` | Draft — Key Processes, task/test plan | 2026-02-23 |
| └ Relation System | 1.0 | `custom-objects-relation-system-prd.md` | Draft — Key Processes, task/test plan | 2026-02-23 |
| Communications | 3.0 | `communications-prd.md` | Superseded — decomposed into Entity Base + 4 Sub-PRDs + TDD | 2026-02-23 |
| └ Communication Entity Base | 1.0 | `communication-entity-base-prd.md` | Draft — V2 methodology (field metadata, Key Processes) | 2026-02-23 |
| &nbsp;&nbsp;└ Communication Entity TDD | 1.0 | `communication-entity-tdd.md` | Draft — Living document, 10 sections | 2026-02-23 |
| └ Published Summary | 1.0 | `communication-published-summary-prd.md` | Draft — Key Processes, task/test plan | 2026-02-23 |
| └ Provider & Sync Framework | 1.0 | `communication-provider-sync-prd.md` | Draft — Key Processes, task/test plan | 2026-02-23 |
| └ Participant Resolution | 1.0 | `communication-participant-resolution-prd.md` | Draft — Key Processes, task/test plan | 2026-02-23 |
| └ Triage & Intelligent Filtering | 1.0 | `communication-triage-prd.md` | Draft — Key Processes, task/test plan | 2026-02-23 |
| Conversations | 4.0 | `conversations-prd.md` | Superseded — decomposed into Entity Base + 3 Sub-PRDs + TDD | 2026-02-23 |
| └ Conversation Entity Base | 1.0 | `conversation-entity-base-prd.md` | Draft — V2 methodology (field metadata, Key Processes) | 2026-02-23 |
| &nbsp;&nbsp;└ Conversation Entity TDD | 1.0 | `conversation-entity-tdd.md` | Draft — Living document, 8 sections | 2026-02-23 |
| └ Formation & Stitching | 1.0 | `conversation-formation-prd.md` | Draft — Key Processes, task/test plan | 2026-02-23 |
| └ AI Intelligence & Review | 1.0 | `conversation-ai-intelligence-prd.md` | Draft — Key Processes, task/test plan | 2026-02-23 |
| └ View Conversation | 1.1 | `conversation-view-prd.md` | Draft — Preview Card + full View, task/test plan | 2026-02-27 |
| └ Views & Alerts | 1.0 | `conversation-views-alerts-prd.md` | Draft — Key Processes, task/test plan | 2026-02-23 |
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
| Event Management | 3.0 | `events-prd.md` | Superseded — decomposed into Entity Base + 2 Sub-PRDs + TDD | 2026-02-23 |
| └ Event Entity Base | 1.0 | `event-entity-base-prd.md` | Draft — V2 methodology (field metadata, Key Processes) | 2026-02-23 |
| &nbsp;&nbsp;└ Event Entity TDD | 1.0 | `event-entity-tdd.md` | Draft — Living document, 10 sections | 2026-02-23 |
| └ Participants & Attendance | 1.0 | `event-participants-prd.md` | Draft — Key Processes, task/test plan | 2026-02-23 |
| └ Calendar Sync Pipeline | 1.0 | `event-calendar-sync-prd.md` | Draft — Key Processes, task/test plan | 2026-02-23 |
| Notes | 3.0 | `notes-prd.md` | Superseded — decomposed into Entity Base + 2 Sub-PRDs + TDD | 2026-02-23 |
| └ Note Entity Base | 1.0 | `note-entity-base-prd.md` | Draft — V2 methodology (field metadata, Key Processes) | 2026-02-23 |
| &nbsp;&nbsp;└ Note Entity TDD | 1.0 | `note-entity-tdd.md` | Draft — Living document, 10 sections | 2026-02-23 |
| └ Content, Revisions & Sanitization | 1.0 | `note-content-revisions-prd.md` | Draft — Key Processes, task/test plan | 2026-02-23 |
| └ Attachments, Mentions & Search | 1.0 | `note-attachments-mentions-prd.md` | Draft — Key Processes, task/test plan | 2026-02-23 |
| Tasks | 2.0 | `tasks-prd.md` | Superseded — decomposed into Entity Base + 2 Sub-PRDs + TDD | 2026-02-23 |
| └ Task Entity Base | 1.0 | `task-entity-base-prd.md` | Draft — V2 methodology (field metadata, Key Processes) | 2026-02-23 |
| &nbsp;&nbsp;└ Task Entity TDD | 1.0 | `task-entity-tdd.md` | Draft — Living document, 9 sections | 2026-02-23 |
| └ Hierarchy, Dependencies & Recurrence | 1.0 | `task-hierarchy-dependencies-prd.md` | Draft — Key Processes, task/test plan | 2026-02-23 |
| └ Assignees, Behaviors & AI Intelligence | 1.0 | `task-assignees-ai-prd.md` | Draft — Key Processes, task/test plan | 2026-02-23 |
| Documents | 2.0 | `documents-prd.md` | Superseded — decomposed into Entity Base + 3 Sub-PRDs + TDD | 2026-02-23 |
| └ Document Entity Base | 1.0 | `document-entity-base-prd.md` | Draft — V2 methodology (field metadata, Key Processes) | 2026-02-23 |
| &nbsp;&nbsp;└ Document Entity TDD | 1.0 | `document-entity-tdd.md` | Draft — Living document, 11 sections | 2026-02-23 |
| └ Upload, Versioning & Storage | 1.0 | `document-upload-storage-prd.md` | Draft — Key Processes, task/test plan | 2026-02-23 |
| └ Content Processing Pipeline | 1.0 | `document-content-processing-prd.md` | Draft — Key Processes, task/test plan | 2026-02-23 |
| └ Communication & Asset Integration | 1.0 | `document-integration-prd.md` | Draft — Key Processes, task/test plan | 2026-02-23 |
| Projects | 3.0 | `projects-prd.md` | Superseded — decomposed into Entity Base + 1 Sub-PRD + TDD | 2026-02-23 |
| └ Project Entity Base | 1.0 | `project-entity-base-prd.md` | Draft — V2 methodology (field metadata, Key Processes) | 2026-02-23 |
| &nbsp;&nbsp;└ Project Entity TDD | 1.0 | `project-entity-tdd.md` | Draft — Living document, 7 sections | 2026-02-23 |
| └ Entity Relations & Aggregation | 1.0 | `project-relations-prd.md` | Draft — Key Processes, task/test plan | 2026-02-23 |
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
- 2026-02-23: PRD Methodology V2 (Key Processes, field metadata, † caching convention); Product TDD and Contact Entity TDD created; Contact entity decomposed into Entity Base PRD + 6 Action Sub-PRDs; Company entity decomposed into Entity Base PRD + 6 Action Sub-PRDs + TDD; Communication entity decomposed into Entity Base PRD + 4 Action Sub-PRDs + TDD; Conversation entity decomposed into Entity Base PRD + 3 Action Sub-PRDs + TDD; Document entity decomposed into Entity Base PRD + 3 Action Sub-PRDs + TDD; Event entity decomposed into Entity Base PRD + 2 Action Sub-PRDs + TDD; Note entity decomposed into Entity Base PRD + 2 Action Sub-PRDs + TDD; Task entity decomposed into Entity Base PRD + 2 Action Sub-PRDs + TDD; Project entity decomposed into Entity Base PRD + 1 Action Sub-PRD + TDD; Custom Objects framework decomposed into Framework PRD + 2 Sub-PRDs + TDD; migrated from versioned filenames to Git-based versioning. **All 9 entity PRDs + Custom Objects framework decomposed.**

---

## Completed PRDs

### 1. Custom Objects

**File:** `custom-objects-prd.md` (superseded — retained as historical reference)
**Scope:** The entity model foundation. Defines the Unified Object Model where system entities and user-created entities are instances of the same framework. Covers object type definition, field registry, field type system, relation model, physical storage, DDL management, and event sourcing.

> **Note:** The monolithic Custom Objects PRD (1,542 lines) has been decomposed into a Framework PRD, TDD, and two Sub-PRDs. The original file is retained for reference; all active development should use the decomposed documents.

**Decomposed documents:**

| Document | File | Description |
|---|---|---|
| Custom Objects Framework PRD | `custom-objects-framework-prd.md` | Unified Object Model principles, Object Type Definition Model (attributes, prefix generation, prefix registry, permissions, limits), Universal Fields & Display Name Field, System Entity Specialization (behaviors registry across all 8 system entities, protected core fields, extensibility), Object Type Lifecycle (creation, modification, archiving), Key Processes, Action Catalog |
| Custom Objects TDD | `custom-objects-tdd.md` | Physical storage architecture (dedicated typed tables, index strategy, virtual schema mapping), DDL Management System (operations catalog, execution model, advisory locking, rollback), Event Sourcing generic pattern (event table structure, base event types, write path, point-in-time reconstruction, snapshots, audit trail UI), Schema-Per-Tenant (isolation model, provisioning, search_path), API design (5 groups) |
| Field System Sub-PRD | `custom-objects-field-system-prd.md` | Field registry (definition model, slug-to-column mapping, ordering, limits), Field Type System (13 Phase 1 + 5 Phase 2 types with config examples), Field Type Conversion Matrix (safe conversions, preview workflow), Field Groups (Attribute Card rendering), Field Validation (rules by type, unique constraints, required behavior), Select/Multi-Select Options (lifecycle), Field Lifecycle (creation, modification, archiving — no deletion) |
| Relation System Sub-PRD | `custom-objects-relation-system-prd.md` | Relation Type definitions (cardinality, directionality, cascade), physical implementation (FK vs. junction by cardinality), self-referential relations, cascade behavior (nullify/restrict/cascade_archive), Relation Metadata (supported types, storage for M:M vs. 1:M, views integration, event sourcing), Neo4j Graph Sync (sync model, graph-enabled queries, phasing) |

---

### 2. Communications

**File:** `communications-prd.md` (superseded — retained as historical reference)
**Scope:** The atomic interaction record. Defines Communication as a system object type, the common schema all channels normalize to, the provider adapter framework, contact association, triage filtering, Published Summary architecture, multi-account management, attachments, and storage.

> **Note:** The monolithic Communications PRD (1,420 lines) has been decomposed into an Entity Base PRD, Entity TDD, and four Action Sub-PRDs following the V2 methodology. The original file is retained for reference; all active development should use the decomposed documents.

**Decomposed documents:** The Communication entity is fully decomposed per methodology V2:

| Document | File | Description |
|---|---|---|
| Communication Entity Base PRD | `communication-entity-base-prd.md` | Entity definition, field registry (with Editable/Sortable/Filterable metadata), channel types, relationships, lifecycle, Key Processes, Action Catalog |
| Communication Entity TDD | `communication-entity-tdd.md` | Read model table DDL, summary revisions table, event sourcing, attachment model, sync audit trail, virtual schema, FTS implementation, storage estimates |
| Published Summary Sub-PRD | `communication-published-summary-prd.md` | Three-stage content pipeline, per-channel generation rules, rich text storage contract, AI summary structure, revision history, generation triggers, error handling |
| Provider & Sync Framework Sub-PRD | `communication-provider-sync-prd.md` | Provider account model, adapter interface, sync modes (initial/incremental/manual), sync reliability, personal vs. shared accounts, shared inbox attribution, sync API & audit trail |
| Participant Resolution Sub-PRD | `communication-participant-resolution-prd.md` | Participant Relation Type, contact resolution integration, pending identification, identifier types by channel, cross-channel unification, participant API |
| Triage & Filtering Sub-PRD | `communication-triage-prd.md` | Multi-layer pipeline, channel-specific heuristic framework, known-contact gate, triage transparency, override mechanism, triage API |

****Key decisions made:**

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

| Child PRD               | Scope                                                                                     | Status                    |
| ----------------------- | ----------------------------------------------------------------------------------------- | ------------------------- |
| Email Provider Sync PRD | Gmail, Outlook, IMAP adapters; dual-track parsing; email threading; email-specific triage | Planned — parent complete |
| SMS/MMS PRD | Twilio/OpenPhone adapters; message sync; phone number resolution; MMS media | Planned |
| Voice/VoIP PRD | Call recording integration; transcription pipeline; provider adapters | Planned |
| Video Meetings PRD | Zoom/Teams/Meet integration; transcript capture; recording management | Planned |

---

### 3. Conversations

**File:** `conversations-prd.md` (superseded — retained as historical reference)
**Scope:** The organizational intelligence layer. Defines Conversation (standard and aggregate) as the single system object type, with aggregate Conversations replacing Topics. Flexible hierarchy via Relation Types, AI intelligence layer, conversation timeline referencing Communication Published Summaries, cross-channel stitching, segmentation, review workflow, views, and alerts.

> **Note:** The monolithic Conversations PRD (1,171 lines) has been decomposed into an Entity Base PRD, Entity TDD, and three Action Sub-PRDs following the V2 methodology. The original file is retained for reference; all active development should use the decomposed documents.

**Decomposed documents:**

| Document | File | Description |
|---|---|---|
| Conversation Entity Base PRD | `conversation-entity-base-prd.md` | Entity definition, field registry (with Editable/Sortable/Filterable metadata), aggregate conversations, membership, system Relation Types, lifecycle (3 status dimensions), Key Processes, Action Catalog |
| Conversation Entity TDD | `conversation-entity-tdd.md` | Read model table DDL, conversation_members junction table, segment data model, event sourcing, virtual schema queries, API design (5 API groups) |
| Formation & Stitching Sub-PRD | `conversation-formation-prd.md` | Email thread auto-formation, participant-based defaults, manual assignment, AI-suggested splitting, cross-channel stitching, communication segmentation (split/reference model) |
| AI Intelligence & Review Sub-PRD | `conversation-ai-intelligence-prd.md` | Three AI roles (classify & route, summarize, extract intelligence), confidence scoring, re-summarization triggers, review workflow, learning from user corrections |
| View Conversation Sub-PRD | `conversation-view-prd.md` | Preview Card (standard and aggregate variants, participant color-coded timeline entries, Sender → Recipient format), full View (responsive two-column layout with dynamic column sizing and per-conversation splitter persistence, Timeline Card, Participants Card, AI Intelligence Card with read-only action items, Entity Associations Card, Children Card, Notes Card, Metadata Card) |
| Views & Alerts Sub-PRD | `conversation-views-alerts-prd.md` | Conversation view patterns, shareable views, user-defined alert architecture (no defaults), frequency/aggregation/delivery |

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

**File:** `events-prd.md` (superseded — retained as historical reference, includes PoC Appendix)
**Scope:** Event as a system object type for calendar events, meetings, and temporal relationship intelligence.

> **Note:** The monolithic Events PRD (1,236 lines) has been decomposed into an Entity Base PRD, Entity TDD, and two Action Sub-PRDs following the V2 methodology. The original file is retained for reference (includes PoC Appendix A); all active development should use the decomposed documents.

**Decomposed documents:**

| Document | File | Description |
|---|---|---|
| Event Entity Base PRD | `event-entity-base-prd.md` | Entity definition, field registry (with Editable/Sortable/Filterable metadata), event types (6 system + custom, provider mapping), recurrence model (RRULE + denormalized select), conversation linking Relation Type, registered behaviors, Key Processes, Action Catalog |
| Event Entity TDD | `event-entity-tdd.md` | Read model DDL with temporal/provider indexes, Event→Contact and Event→Company participation junction tables, Event→Conversation junction table, event_all_participants convenience VIEW, event sourcing (9 event types), virtual schema, API design (4 groups) |
| Participants & Attendance Sub-PRD | `event-participants-prd.md` | Two system Relation Types (Contact with role/RSVP, Company with role), attendee resolution via contact_identifiers, RSVP mapping from Google, birthday auto-generation, co-attendance scoring |
| Calendar Sync Pipeline Sub-PRD | `event-calendar-sync-prd.md` | Provider account reuse (same OAuth token), Google Calendar API client, sync orchestration with incremental tokens, UPSERT deduplication, field mapping, calendar selection settings, error handling |

---

### 7. Notes

**File:** `notes-prd.md` (superseded — retained as historical reference, includes PoC Appendix)
**Scope:** Note as a system object type for free-form knowledge capture with rich text, revisions, and universal entity attachment.

> **Note:** The monolithic Notes PRD (1,200 lines) has been decomposed into an Entity Base PRD, Entity TDD, and two Action Sub-PRDs following the V2 methodology. The original file is retained for reference (includes PoC Appendix A); all active development should use the decomposed documents.

**Decomposed documents:**

| Document | File | Description |
|---|---|---|
| Note Entity Base PRD | `note-entity-base-prd.md` | Entity definition, field registry, Universal Attachment Relation pattern (target = *, framework impact), visibility model (private/shared, permission rules, multi-entity union), pinning (per-entity-link), Key Processes, Action Catalog |
| Note Entity TDD | `note-entity-tdd.md` | Read model DDL (with FTS tsvector generated column), note_entities universal attachment junction, note_revisions table, note_attachments table (orphan pattern), note_mentions table, event sourcing (10 event types, content_revised pattern), virtual schema, API design (7 groups) |
| Content, Revisions & Sanitization Sub-PRD | `note-content-revisions-prd.md` | Behavior-managed content architecture (JSON + HTML + text triple), editor requirements and mention node contract, full-snapshot revision history, content events vs. metadata events, HTML sanitization allowlists |
| Attachments, Mentions & Search Sub-PRD | `note-attachments-mentions-prd.md` | File upload with orphan pattern, StorageBackend protocol, storage layout, orphan cleanup, allowed MIME types, @mention types and autocomplete, mention extraction/sync, FTS with tsvector two-tier weighting and ranked results |

---

### 8. Tasks

**File:** `tasks-prd.md` (superseded — retained as historical reference)
**Scope:** Task as a system object type for actionable work items with status workflow, priority, assignees, dependencies, subtask hierarchy, recurrence, and AI action-item extraction.

> **Note:** The monolithic Tasks PRD (1,080 lines) has been decomposed into an Entity Base PRD, Entity TDD, and two Action Sub-PRDs following the V2 methodology. The original file is retained for reference; all active development should use the decomposed documents.

**Decomposed documents:**

| Document | File | Description |
|---|---|---|
| Task Entity Base PRD | `task-entity-base-prd.md` | Entity definition, field registry, status model & categories (4 immutable categories, user-extensible statuses, denormalized status_category, behavioral implications), priority model (fixed 5-level), Universal Attachment (is_primary, standalone allowed), description content architecture (Notes-aligned, no revisions), Key Processes, Action Catalog |
| Task Entity TDD | `task-entity-tdd.md` | Read model DDL with 14 indexes (FTS, status/priority, dates, overdue candidates, hierarchy, recurrence, source), task_entities junction (is_primary), task_user_roles junction (role CHECK, UNIQUE per user+role), task_dependencies junction (circular prevention CHECK), event sourcing (12 event types), virtual schema, API design (6 groups) |
| Hierarchy, Dependencies & Recurrence Sub-PRD | `task-hierarchy-dependencies-prd.md` | Subtask hierarchy (self-referential 1:many, unlimited nesting, count rollup, cascade archive, recursive CTE), task dependencies (blocked_by M:M, circular prevention CTE, warn-but-allow), completion-triggered recurrence (RRULE, generation logic, assignee/attachment copying, cancellation) |
| Assignees, Behaviors & AI Intelligence Sub-PRD | `task-assignees-ai-prd.md` | Task→User relation with assignee/reviewer/watcher roles, overdue detection background job, due date reminder scheduling, AI action-item extraction from Conversations (source tracking, auto-link, assignee inference, priority mapping) |

---

### 9. Documents

**File:** `documents-prd.md` (superseded — retained as historical reference)
**Scope:** Document as a system object type for version-controlled file management with folder organization, metadata extraction, full-text search, and universal entity attachment. Unifies communication attachments, profile assets, and user-uploaded files into a single entity model.

> **Note:** The monolithic Documents PRD (1,331 lines) has been decomposed into an Entity Base PRD, Entity TDD, and three Action Sub-PRDs following the V2 methodology. The original file is retained for reference; all active development should use the decomposed documents.

**Decomposed documents:**

| Document | File | Description |
|---|---|---|
| Document Entity Base PRD | `document-entity-base-prd.md` | Entity definition, field registry (with Editable/Sortable/Filterable metadata), Universal Attachment Relation, folder model (folders as entities, membership, nesting, system folders), visibility (private default, folder cascade), Key Processes, Action Catalog |
| Document Entity TDD | `document-entity-tdd.md` | Read model DDL (with FTS tsvector), document_versions, document_blobs, document_entities junction, document_folder_members junction, communication_documents relation, event sourcing (15 event types), virtual schema, API design (7 groups) |
| Upload, Versioning & Storage Sub-PRD | `document-upload-storage-prd.md` | Upload/download flow, hash-based version control, content-addressable storage (CAS layout, StorageBackend, reference counting), progressive hashing & duplicate detection, chunked uploads, dangerous file blocklist, preview |
| Content Processing Pipeline Sub-PRD | `document-content-processing-prd.md` | Metadata extraction (PDF, Office, images, video, audio), text extraction for FTS, PostgreSQL tsvector with three-tier weighting, search with ranked results and snippets, thumbnail generation and serving |
| Communication & Asset Integration Sub-PRD | `document-integration-prd.md` | Email attachment promotion to Documents during sync, communication_documents version tracking, profile asset migration from entity_assets, cross-PRD reconciliation |

---

### 10. Projects

**File:** `projects-prd.md` (superseded — retained as historical reference)
**Scope:** The central organizational hub. Defines Project as a system object type — the highest-level user-created container that connects Conversations, Events, Notes, Contacts, and Companies into a coherent picture of a business initiative.

> **Note:** The monolithic Projects PRD (850 lines) has been decomposed into an Entity Base PRD, Entity TDD, and one Action Sub-PRD following the V2 methodology. The original file is retained for reference; all active development should use the decomposed documents.

**Decomposed documents:**

| Document | File | Description |
|---|---|---|
| Project Entity Base PRD | `project-entity-base-prd.md` | Entity definition, field registry with denormalized counts (6), user-defined status workflow (configuration model, transition enforcement, status vs. archiving independence), sub-project hierarchy (unlimited depth, cascade archive), flexible hierarchy model (relaxed graph, no inheritance), project creation model, Key Processes, Action Catalog |
| Project Entity TDD | `project-entity-tdd.md` | Read model DDL with 6 indexes, 4 junction tables (conversations, contacts with role/notes, companies with role/notes, events), Notes/Tasks via Universal Attachment, event sourcing (17 event types), virtual schema with cross-entity queries, API design (4 groups) |
| Entity Relations & Aggregation Sub-PRD | `project-relations-prd.md` | 5 system Relation Types (Conversation, Contact with role/notes, Company with role/notes, Event, Note via Universal Attachment), entity aggregation behavior (6 denormalized counts, last_activity_at computation), Custom Object Type relation guidance, derived participant display (explicit vs. derived, promote action) |

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
├── custom-objects-prd.md                     # Custom Objects (monolithic, superseded)
├── custom-objects-framework-prd.md           # Custom Objects framework definition
├── custom-objects-tdd.md                     # Custom Objects technical decisions
├── custom-objects-field-system-prd.md        # Field system sub-PRD
├── custom-objects-relation-system-prd.md     # Relation system sub-PRD
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
├── communications-prd.md                     # Communications (monolithic, superseded)
├── communication-entity-base-prd.md          # Communication entity definition
├── communication-entity-tdd.md               # Communication technical decisions
├── communication-published-summary-prd.md    # Published summary sub-PRD
├── communication-provider-sync-prd.md        # Provider & sync framework sub-PRD
├── communication-participant-resolution-prd.md # Participant resolution sub-PRD
├── communication-triage-prd.md               # Triage & filtering sub-PRD
├── conversations-prd.md                      # Conversations (monolithic, superseded)
├── conversation-entity-base-prd.md           # Conversation entity definition
├── conversation-entity-tdd.md                # Conversation technical decisions
├── conversation-formation-prd.md             # Formation & stitching sub-PRD
├── conversation-ai-intelligence-prd.md       # AI intelligence & review sub-PRD
├── conversation-views-alerts-prd.md          # Views & alerts sub-PRD
├── conversation-view-prd.md                  # View conversation sub-PRD (Preview + full View)
├── events-prd.md                             # Events (monolithic, superseded)
├── event-entity-base-prd.md                  # Event entity definition
├── event-entity-tdd.md                       # Event technical decisions
├── event-participants-prd.md                  # Participants & attendance sub-PRD
├── event-calendar-sync-prd.md                # Calendar sync pipeline sub-PRD
├── notes-prd.md                              # Notes (monolithic, superseded)
├── note-entity-base-prd.md                   # Note entity definition
├── note-entity-tdd.md                        # Note technical decisions
├── note-content-revisions-prd.md             # Content, revisions & sanitization sub-PRD
├── note-attachments-mentions-prd.md          # Attachments, mentions & search sub-PRD
├── tasks-prd.md                              # Tasks (monolithic, superseded)
├── task-entity-base-prd.md                   # Task entity definition
├── task-entity-tdd.md                        # Task technical decisions
├── task-hierarchy-dependencies-prd.md        # Hierarchy, dependencies & recurrence sub-PRD
├── task-assignees-ai-prd.md                  # Assignees, behaviors & AI intelligence sub-PRD
├── documents-prd.md                          # Documents (monolithic, superseded)
├── document-entity-base-prd.md               # Document entity definition
├── document-entity-tdd.md                    # Document technical decisions
├── document-upload-storage-prd.md            # Upload, versioning & storage sub-PRD
├── document-content-processing-prd.md        # Content processing pipeline sub-PRD
├── document-integration-prd.md               # Communication & asset integration sub-PRD
├── projects-prd.md                           # Projects (monolithic, superseded)
├── project-entity-base-prd.md                # Project entity definition
├── project-entity-tdd.md                     # Project technical decisions
├── project-relations-prd.md                  # Entity relations & aggregation sub-PRD
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
