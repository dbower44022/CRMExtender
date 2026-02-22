# CRMExtender — PRD Index

**Last Updated:** 2026-02-16
**Purpose:** Living index of all Product Requirements Documents for CRMExtender. Reference this at the start of any PRD development session for orientation.

---

## Platform Overview

CRMExtender (also called Contact Intelligence Manager) is a comprehensive CRM platform providing deep relationship intelligence and unified communication tracking. The system targets sales professionals, entrepreneurs, and service providers. Key differentiators include unified multi-channel inbox, AI conversation intelligence, cross-channel conversation stitching, and sophisticated relationship tracking.

**Tech Stack:** Flutter frontend (cross-platform), Python FastAPI backend, PostgreSQL (event-sourced), Neo4j (relationship graph), SQLite (offline read), Meilisearch (search).

---

## PRD Status Summary

| PRD | Version | Date | Status | Lines | Chat |
|---|---|---|---|---|---|
| Communication & Conversation Intelligence | 2.0 | 2026-02-07 | Draft — Complete | ~2,800 | Dedicated |
| Contact Management & Intelligence | 1.0 | 2026-02-08 | Draft — Complete | ~4,000 | Dedicated |
| Views & Grid System | 1.1 | 2026-02-16 | Draft — Complete | ~1,600 | Dedicated |
| Data Sources | 1.0 | 2026-02-16 | Draft — Complete | ~1,500 | Dedicated |
| Email Parsing & Content Extraction | — | — | Technical Spec | ~700 | — |
| Custom Objects | — | — | **Not Started** | — | — |
| AI Learning & Classification | — | — | **Not Started** | — | — |
| Permissions & Sharing | — | — | **Not Started** | — | — |
| CRMExtender Platform (Parent) | 1.1 | — | Exists (not in project) | — | — |

---

## Completed PRDs

### 1. Communication & Conversation Intelligence
**File:** `email-conversations-prd.md`
**Scope:** The primary relationship signal layer. Captures communications across email, SMS, phone, video, in-person, and notes. Organizes them into a Project → Topic → Conversation → Communication hierarchy.

**Key sections:**
- Organizational hierarchy (Projects, Topics, Conversations, Communications)
- Unified communication record model across all channels
- Communication segmentation & cross-conversation references
- AI intelligence layer (summarization, status detection, action items)
- Contact association & identity resolution
- Email provider integration (Gmail Tier 1, Outlook Tier 2, IMAP Tier 3)
- Email sync pipeline (initial, incremental, manual)
- Email parsing & content extraction (dual-track: HTML + plain text)
- Triage & intelligent filtering
- Conversation lifecycle & status management (3 independent dimensions)
- Multi-account management
- 4-phase roadmap

**Key decisions made:**
- Direct provider API integration (no Nylas/third-party aggregation)
- Provider adapter pattern normalizes all sources to common Communication schema
- Event sourcing provides audit trails naturally
- iMessage excluded from cross-platform sync (Apple restrictions)
- SMS provider selection still open
- Triage uses heuristic junk detection + known-contact gate

**Open questions:** 12 (SMS provider, speech-to-text service, Slack/Teams model, calendar linking, cross-account merging, attachment storage, and more)

---

### 2. Contact Management & Intelligence
**File:** `contact-management-prd.md`
**Scope:** The foundational entity layer. Defines contacts and companies as living intelligence objects with event-sourced history, multi-identifier identity model, enrichment, OSINT, and relationship intelligence.

**Key sections:**
- Contact data model (materialized view pattern with denormalized fields)
- Company data model
- Identity resolution & entity matching (multi-identifier: email, phone, social)
- Contact lifecycle management (lead status, engagement scoring)
- Contact intelligence & enrichment (Apollo, Clearbit, People Data Labs adapters)
- Relationship intelligence (Neo4j graph, relationship types, influence mapping)
- Behavioral signal tracking (engagement score computation)
- Groups, tags & segmentation
- Contact import & export (CSV, Google Contacts sync)
- AI-powered contact intelligence (briefings, tag suggestions, NL search)
- Event sourcing & temporal history
- API design
- Client-side offline support (SQLite)
- 4-phase roadmap

**Key decisions made:**
- Contacts use UUID v4 (note: Data Sources PRD establishes prefixed IDs — reconciliation needed)
- Employment history tracked as separate table with temporal records
- Intelligence items are discrete sourced data points with confidence scores
- Engagement score is a composite behavioral metric (0.0–1.0)
- Intelligence score measures data completeness (0.0–1.0)
- Google People API for bidirectional contact sync (Phase 1)
- Browser extension for LinkedIn/Twitter capture (Phase 2)

**Open questions:** See PRD Section 23

---

### 3. Views & Grid System
**File:** `views-grid-prd_V2.md` → updated to `views-grid-prd_V3.md`
**Scope:** The primary data interaction layer. Polymorphic, entity-agnostic framework for displaying, filtering, sorting, grouping, and editing any entity type through multiple view types.

**Key sections:**
- Core concepts (Data Source separation, entity-agnostic rendering)
- Data Sources (summary — full spec in Data Sources PRD)
- View types: List/Grid, Calendar, Timeline, Board/Kanban
- Column system (direct, relation traversal, computed)
- Field type registry
- Relation traversal & lookup columns
- Filtering & query builder (compound AND/OR, cross-entity filters)
- Sorting & grouping (multi-level, collapsible, aggregation rows)
- Grid interactions (inline editing, row expansion, bulk actions, keyboard nav)
- Calendar, Board, Timeline view-specific configurations
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
- Inspired by ClickUp multi-view + Attio object model

**Open questions:** 15 (with 7 migrated to Data Sources PRD)

---

### 4. Data Sources
**File:** `data-sources-prd.md` (new, extracted from Views PRD Section 6)
**Scope:** The query abstraction layer. Reusable, named query definitions that sit between physical storage and views, providing cross-entity queries, dual authoring modes, column registries, and preview detection.

**Key sections:**
- Universal entity ID convention (prefixed IDs: `con_`, `cvr_`, `com_`, etc.)
- Data source definition model (ID, query, column registry, preview config, parameters, refresh policy)
- Visual query builder (5-step: entity → joins → columns → filters → sort)
- Raw SQL environment (virtual schema, access rules, validation, parameters)
- Column registry (auto-generated + manual overrides, editability rules)
- Entity detection & preview system (3-layer: auto-detect → inference rules → manual override)
- Data source ↔ view relationship (many-to-one, composition rules)
- Inline editing trace-back (column registry → source entity → API call)
- Query engine (conceptual: responsibilities, execution lifecycle, virtual schema translation, security model, pagination)
- Cache, refresh & invalidation (live/cached/manual policies, cache key composition, deduplication)
- Schema evolution & migration (field changes, entity changes, graceful degradation)
- Data source API (CRUD + execute + batch + validate endpoints)
- Permissions & security (owner/shared access, row-level security, SQL injection prevention)
- System-generated data sources (one per entity type, auto-updated)
- 5 detailed examples (simple → complex CTE)
- 4-phase roadmap

**Key decisions made:**
- Data sources are first-class entities with `dts_` prefix
- Virtual schema is the stable API — physical storage translation is opaque
- Security injected at query engine level (authors cannot bypass)
- Cache key includes user ID (row-level security = different results per user)
- Schema changes degrade gracefully (NULL columns, not failures)
- Query engine translation strategy deferred to implementation (Claude Code)
- Visual builder → SQL "eject" is one-way

**Open questions:** 12 (formula computation, custom entity scope, SQL guardrails, event-driven invalidation, execution quotas, and more)

---

### 5. Email Parsing & Content Extraction
**File:** `email_stripping.md`
**Scope:** Technical specification for the dual-track email parsing pipeline. Covers HTML structural removal and plain-text regex-based extraction.

**Key sections:**
- HTML cleaning pipeline (quote removal, signature detection, disclaimer stripping)
- Plain-text pipeline (reply pattern detection, valediction-based truncation, standalone signature detection)
- Promotional content detection
- Line unwrapping algorithm
- Provider-specific patterns (Gmail, Outlook, Apple Mail)

**Notes:** This is a technical spec, not a conceptual PRD. More appropriate for Claude Code reference than PRD development sessions.

---

## Planned PRDs (Not Yet Started)

### 6. Custom Objects
**Scope:** Entity type definition, field registry, field types, relation model, custom entity creation/management. The object model foundation that everything else builds on.

**Referenced by:** Views & Grid PRD, Data Sources PRD, Communication PRD
**Critical dependency for:** Data Sources (virtual schema composition), Views (field type rendering, column system), Contact Management (entity model alignment)

**Key questions to resolve:**
- How are custom entity fields stored physically? (Dedicated tables vs. JSONB vs. hybrid)
- How does the prefixed entity ID convention apply to custom entities?
- Field type registry: what types are supported and what are their behaviors?
- Relation model: how are relationships between entity types defined and managed?

---

### 7. AI Learning & Classification
**Scope:** How the system learns from user corrections, classification algorithms, embedding/similarity approaches, model training, confidence scoring.

**Referenced by:** Communication PRD (establishes that learning happens), Views PRD (AI fields as queryable columns)
**Depends on:** Communication PRD (correction signals), Contact Management PRD (entity context)

**Key questions to resolve:**
- What ML models power auto-classification of conversations to topics/projects?
- How are user corrections fed back into the model?
- What confidence thresholds trigger auto-assignment vs. human review?
- How is training data managed per tenant?

---

### 8. Permissions & Sharing
**Scope:** Team access controls, role-based permissions, row-level security, shared vs. private data, data visibility rules.

**Referenced by:** Data Sources PRD (row-level security), Views PRD (shared view permissions), Communication PRD (conversation access), Contact Management PRD (contact access)
**Critical dependency for:** Data Sources (query engine security injection), Views (shared view behavior)

**Key questions to resolve:**
- What permission model? (RBAC, ABAC, or hybrid)
- How granular is row-level security? (Entity type level? Record level? Field level?)
- How do shared data sources and views interact with permissions?
- Multi-tenant isolation model (schema-per-tenant confirmed in Communication PRD)

---

## Dependency Map

```
                    ┌─────────────────────┐
                    │  CRMExtender PRD    │
                    │  (Parent v1.1)      │
                    └─────────┬───────────┘
                              │
          ┌───────────────────┼───────────────────┐
          │                   │                   │
          ▼                   ▼                   ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│  Communication   │ │    Contact      │ │  Custom Objects  │
│  & Conversation  │ │  Management &   │ │  (PLANNED)       │
│  Intelligence    │ │  Intelligence   │ │                  │
└────────┬────────┘ └────────┬────────┘ └────────┬────────┘
         │                   │                   │
         │    ┌──────────────┤                   │
         │    │              │                   │
         ▼    ▼              │                   │
┌─────────────────┐          │                   │
│  Data Sources    │◄─────────┼───────────────────┘
│                  │          │
└────────┬────────┘          │
         │                   │
         ▼                   │
┌─────────────────┐          │
│  Views & Grid    │          │
│  System          │          │
└────────┬────────┘          │
         │                   │
         │    ┌──────────────┘
         ▼    ▼
┌─────────────────┐         ┌─────────────────┐
│  Permissions &   │         │  AI Learning &   │
│  Sharing         │         │  Classification  │
│  (PLANNED)       │         │  (PLANNED)       │
└─────────────────┘         └─────────────────┘
```

**Reading the arrows:** An arrow from A to B means "A depends on B" or "A references B."

---

## Cross-PRD Decisions & Reconciliation Items

These are decisions or inconsistencies that span multiple PRDs and need attention:

| Item | PRDs Involved | Status | Notes |
|---|---|---|---|
| **Prefixed entity IDs** | Data Sources, Views, Contact Management | **Needs reconciliation** | Data Sources PRD establishes `con_`, `cvr_`, etc. with ULID. Contact Management PRD uses UUID v4 without prefixes. Need to align Contact Management to the prefixed convention. |
| **Event sourcing read model** | Data Sources, Contact Management, Communication | **Implementation decision** | Contact Management describes "materialized view" pattern. Data Sources defers physical translation to implementation. Communication PRD references event sourcing. The actual read-model strategy needs to be decided in Claude Code. |
| **Custom entity storage** | Data Sources, Custom Objects (planned) | **Blocked on Custom Objects PRD** | Data Sources PRD defines virtual schema parity for custom entities but defers physical storage to implementation. Custom Objects PRD will need to establish the storage model. |
| **Alert system ownership** | Communication, Views, Data Sources | **Needs clarification** | Communication PRD defines alerts. Views PRD defines view-to-alert promotion. Data Sources PRD defines queries that alerts execute. The alert execution engine's home PRD should be clarified. |
| **Permissions model** | All PRDs | **Blocked on Permissions PRD** | Every PRD references permissions but defers to the Permissions PRD. This is the most cross-cutting dependency and should probably be written early. |

---

## Suggested PRD Development Order

Based on dependency analysis, the recommended order for remaining PRDs:

1. **Custom Objects** — Most PRDs depend on the entity model. Unblocks Data Sources virtual schema, Views field registry, and Contact Management entity alignment.
2. **Permissions & Sharing** — Most cross-cutting dependency. Every PRD references it. Unblocks Data Sources security model, Views sharing, and Contact Management access control.
3. **AI Learning & Classification** — Depends on Communication PRD signals and Contact Management context. Can be written once the entity and permission models are stable.

---

## Workflow Notes

**PRD Development:** Use dedicated Claude.ai chats (this project) for conceptual PRD development. One chat per PRD for clean context.

**Implementation Planning:** Use Claude Code for implementation plans against the actual codebase. Claude Code reads PRDs and maps concepts to real code.

**Decision Flow:** When Claude Code makes architectural decisions that resolve PRD open questions or affect PRD assumptions, capture them as updates to this index (Cross-PRD Decisions table) or as memory edits.

---

*This index is updated after each PRD development session. It serves as the starting context for any new PRD chat.*
