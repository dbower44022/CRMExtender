# Product Requirements Document: Contact Management & Intelligence

## CRMExtender — Contact Lifecycle, Identity Resolution & Intelligence Subsystem

**Version:** 5.0
**Date:** 2026-02-21
**Status:** Draft
**Parent Document:** [CRMExtender PRD v1.1](PRD.md)

> **V5.0 (2026-02-21):**
> Terminology alignment pass. Updated PRD links: Custom Objects PRD V1 → V2, Views & Grid PRD V3 → V5. Added Card-Based Architecture reference in phasing table. Added Master Glossary V3 cross-reference in glossary. No behavioral changes.
> 
> **V4.0 Company PRD Extraction (2026-02-17):**
> Section 6 (Company Data Model) has been replaced with a concise cross-reference to the new [Company Management & Intelligence PRD](company-management-prd_V1.md), which consolidates the Company Detection specification and Company Intelligence PRD into a single authoritative document for the Company entity type. The full Company data model, domain resolution flow, enrichment pipeline, hierarchy, merging, scoring, and social profile specifications now live in the Company PRD. This document retains a summary Section 6 covering only the Contact↔Company interaction points.

> **V3.0 Reconciliation Complete (2026-02-17):**
> This version completes the reconciliation with the [Custom Objects PRD](custom-objects-prd_v2.md) that V2.0 began. V2.0 added reconciliation callout notes; V3.0 rewrites the body text to fully reflect the Unified Object Model. Changes across V2.0 and V3.0:
> 
> - Contact and Company are **system object types** in the unified framework (`is_system = true`), with core fields protected from deletion and specialized behaviors registered per Custom Objects PRD Section 22.
> - Entity IDs use **prefixed ULIDs** (`con_` for contacts, `cmp_` for companies) per the platform-wide convention (Data Sources PRD, Custom Objects PRD Section 6).
> - The `custom_fields` JSONB column has been **removed** from both `contacts` and `companies`. Custom fields managed through the **unified field registry** (Custom Objects PRD Section 8).
> - Employment history is a **system Relation Type** (Contact→Company, many-to-many) with `has_metadata = true`. Stored as a junction table (`contacts__companies_employment`) per Custom Objects PRD Sections 14–15. *(V3.0: fully rewritten.)*
> - The event store uses **per-entity-type event tables** (`contacts_events`, `companies_events`) per Custom Objects PRD Section 19. *(V3.0: schema and SQL rewritten.)*
> - `contacts` and `companies` are the dedicated **read model tables**, managed through the object type framework. *(V3.0: all stale `contacts_current`/`companies_current` references removed.)*
> - The **merge execution flow** (Section 7.6) reconciled against PRD-defined table names and the Relation Type framework. *(V3.0: PoC-era table names replaced.)*

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Problem Statement](#2-problem-statement)
3. [Goals & Success Metrics](#3-goals--success-metrics)
4. [User Personas & Stories](#4-user-personas--stories)
5. [Contact Data Model](#5-contact-data-model)
6. [Company Data Model](#6-company-data-model)
7. [Identity Resolution & Entity Matching](#7-identity-resolution--entity-matching)
8. [Contact Lifecycle Management](#8-contact-lifecycle-management)
9. [Contact Intelligence & Enrichment](#9-contact-intelligence--enrichment)
10. [Relationship Intelligence](#10-relationship-intelligence)
11. [Behavioral Signal Tracking](#11-behavioral-signal-tracking)
12. [Groups, Tags & Segmentation](#12-groups-tags--segmentation)
13. [Contact Import & Export](#13-contact-import--export)
14. [Search & Discovery](#14-search--discovery)
15. [AI-Powered Contact Intelligence](#15-ai-powered-contact-intelligence)
16. [Event Sourcing & Temporal History](#16-event-sourcing--temporal-history)
17. [API Design](#17-api-design)
18. [Client-Side Offline Support](#18-client-side-offline-support)
19. [Privacy, Security & Compliance](#19-privacy-security--compliance)
20. [Phasing & Roadmap](#20-phasing--roadmap)
21. [Integration Points](#21-integration-points)
22. [Dependencies & Risks](#22-dependencies--risks)
23. [Open Questions](#23-open-questions)
24. [Glossary](#24-glossary)

---

## 1. Executive Summary

The Contact Management & Intelligence subsystem is the foundational entity layer of CRMExtender. Every other subsystem — conversations, deals, intelligence, relationship graphs — ultimately resolves back to contacts and companies. A communication has a sender and recipients. A deal has stakeholders. An intelligence item is about a person or organization. The contact subsystem answers the question: **"Who is this, and what do we know about them?"**

Unlike traditional CRMs that treat contacts as static address book entries, CRMExtender models contacts as **living intelligence objects** that evolve over time. Every field change is an immutable event. Every identifier — email, phone, social handle — has a lifecycle. Every data point carries source attribution and confidence scoring. The system doesn't just store who someone *is now*; it knows who they *were*, how their profile *changed*, and *why*.

**Core principles:**

- **Event-sourced contacts** — All contact and company mutations are stored as immutable events, enabling full audit trails, point-in-time reconstruction, and compliance (GDPR/CCPA data subject access requests).
- **Multi-identifier identity model** — A contact is not an email address. A person has multiple emails, phones, social handles, and aliases. The system resolves all of these to a single unified record.
- **Probabilistic entity resolution** — When data arrives from multiple sources (email sync, Google Contacts, browser extension, enrichment APIs, manual entry), the system determines whether two records refer to the same real-world person using tiered confidence scoring.
- **Intelligence-first** — Contacts are enriched automatically on creation. Behavioral signals, OSINT data, and communication patterns are continuously aggregated. AI generates briefings, suggests tags, and detects anomalies.
- **Temporal awareness** — Employment history, contact details, and relationship strengths are tracked over time with valid-from/valid-until bounds. The system knows that Sarah used to work at Acme Corp and now works at Globex, that her old email still resolves, and that her relationship with your team has strengthened over the last quarter.

**Current state:** The PoC implements a minimal contact model — a `contacts` table with `email`, `name`, `source`, and `source_id` columns populated from the Google People API. Contacts are used for conversation participant matching and triage filtering. This PRD defines the requirements for the full contact management system.

**Relationship to other PRDs:**

- **[Custom Objects PRD](custom-objects-prd_v2.md)** — The Contact and Company entity types are **system object types** in the unified framework. Their table structure, field registry, event sourcing, and relation model are governed by the Custom Objects PRD. This PRD defines the Contact-specific behaviors (identity resolution, enrichment, intelligence scoring, relationship intelligence) that are registered with the object type framework. Custom fields on Contacts and Companies are managed through the unified field registry, not a JSONB column.
- **[Communication & Conversation Intelligence PRD](email-conversations-prd.md)** — Every communication participant resolves to a contact. The conversations subsystem depends on the contact model for participant resolution, but owns its own `conversation_participants` and `communication_participants` tables.
- **[Data Sources PRD](data-sources-prd_V1.md)** — The Contact and Company virtual schema tables are derived from their object type field registries. The prefixed entity ID convention (`con_`, `cmp_`) enables automatic entity detection in data source queries.
- **[Data Layer Architecture PRD](data-layer-prd.md)** — Defines the `contacts` and `contact_identifiers` tables used by the conversations subsystem. This PRD extends the contact model with the full event-sourced schema, intelligence tables, and graph model.
- **[Company Management & Intelligence PRD](company-management-prd_V1.md)** — The Company entity type is fully specified in its own PRD. This document’s Section 6 is a summary cross-reference; the Company PRD is authoritative for the Company data model, domain resolution, enrichment, hierarchy, merging, scoring, and all company-specific behaviors.

---

## 2. Problem Statement

### The Static Contact Problem

Traditional CRM contact records are snapshots: a name, a company, an email, and a trail of manually logged activities. They degrade silently — people change jobs, companies rebrand, phone numbers rotate — and the CRM doesn't notice. The record you're looking at might be months or years out of date, and you have no way to know.

**The consequences for CRM users:**

| Pain Point                    | Impact                                                                                                                                                                                              |
| ----------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Stale data**                | Contacts change jobs, titles, and companies. Without continuous enrichment, records degrade. A sales rep discovers mid-call that their "VP of Engineering" contact left the company six months ago. |
| **Duplicate records**         | The same person entered via email sync, LinkedIn capture, and manual entry creates three separate records. Communication history is fragmented across duplicates.                                   |
| **No identity resolution**    | A contact's work email, personal email, and phone number are treated as three different people. Cross-channel communication threads are disconnected.                                               |
| **Missing context**           | A name and email reveal nothing about a contact's priorities, recent activity, organizational influence, or relationship history. Users must manually research before every interaction.            |
| **No temporal awareness**     | When a contact changes roles, the old role is overwritten. There's no employment timeline, no history of how the relationship evolved, no way to understand career trajectory.                      |
| **Manual data entry**         | Sales reps and networkers spend hours per week entering, updating, and deduplicating contact records. Most give up, leaving CRM data incomplete and unreliable.                                     |
| **Siloed data sources**       | Contact intelligence exists across Google Contacts, LinkedIn, email signatures, enrichment APIs, and manual notes — but no system unifies them with proper attribution and conflict resolution.     |
| **No proactive intelligence** | CRMs don't tell you that a contact just got promoted, their company raised funding, or they've gone silent after months of active engagement. Users must discover these signals manually.           |

### Why Existing Solutions Fall Short

- **Salesforce / HubSpot contacts** — Mutable record model. No event history, no point-in-time queries, no built-in enrichment, no graph-based relationships. Duplicates require third-party dedup tools. Custom field hell.
- **LinkedIn** — Rich profile data but locked behind their platform. No API access for most users. No integration with personal communication history. No custom intelligence.
- **Enrichment-only tools (Apollo, Clearbit, ZoomInfo)** — Provide data snapshots but no lifecycle tracking, no relationship modeling, no communication integration, no AI layer. Must be bolted onto a CRM.
- **Contact management apps (Google Contacts, Apple Contacts)** — Address book utilities. No intelligence, no relationships, no business context. Single-identifier model.
- **Graph-based CRMs (Affinity, Dex)** — Closer to the target, but limited enrichment, no event sourcing, no temporal history, no multi-channel communication integration.

CRMExtender closes this gap by making contacts **living intelligence objects** — event-sourced, multi-identifier, continuously enriched, graph-connected, and AI-analyzed.

---

## 3. Goals & Success Metrics

### Primary Goals

1. **Unified contact identity** — Every person and organization encountered across any channel resolves to a single, canonical contact record via multi-identifier matching.
2. **Continuous intelligence** — Contacts are automatically enriched on creation and continuously monitored for changes. Stale data is detected and flagged.
3. **Temporal history** — Full event-sourced history enables point-in-time reconstruction, employment timelines, and audit compliance.
4. **Relationship modeling** — Contact-to-contact and contact-to-company relationships are modeled in a graph database with typed, temporal edges and strength scoring.
5. **AI-powered insights** — Every contact has an AI-generated briefing, suggested tags, engagement scoring, and anomaly detection available on demand.
6. **Zero-friction capture** — Contacts are created automatically from email participants, browser extension captures, and enrichment lookups. Manual entry is a last resort, not the default.

### Success Metrics

| Metric                                         | Target                                                             | Measurement Method                                                             |
| ---------------------------------------------- | ------------------------------------------------------------------ | ------------------------------------------------------------------------------ |
| Contact auto-creation rate                     | > 90% of communication participants have matching contacts         | `SELECT COUNT(*) FROM communication_participants WHERE contact_id IS NOT NULL` |
| Duplicate contact rate                         | < 2% after entity resolution                                       | Periodic duplicate scan audit                                                  |
| Auto-enrichment coverage                       | > 60% of contacts have enrichment data within 24 hours of creation | `contacts WHERE intelligence_score > 0 / total`                                |
| Entity resolution accuracy (high-confidence)   | > 95% correct auto-merges                                          | Manual sampling of auto-merged records                                         |
| Entity resolution accuracy (medium-confidence) | > 80% correct auto-merges with flag                                | Manual review of flagged merges                                                |
| Data freshness                                 | < 7 days for actively monitored contacts                           | `osint_monitors WHERE last_checked > NOW() - INTERVAL '7 days'`                |
| Point-in-time query response                   | < 500ms p95                                                        | APM monitoring on `/contacts/{id}/history?at=`                                 |
| Contact detail page load                       | < 200ms p95                                                        | APM monitoring on `/contacts/{id}`                                             |
| AI briefing generation                         | < 5 seconds per contact                                            | APM monitoring on `/contacts/{id}/briefing`                                    |
| User correction rate (declining)               | < 10% of auto-merges corrected after 90 days                       | `match_candidates WHERE status = 'rejected'`                                   |
| Import throughput                              | > 1,000 contacts per minute (CSV/vCard)                            | Load testing                                                                   |
| Search latency                                 | < 50ms p95                                                         | Meilisearch metrics                                                            |

---

## 4. User Personas & Stories

### Personas

| Persona                    | Context                                                                                                 | Contact Management Needs                                                                                                |
| -------------------------- | ------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------- |
| **Networker / Consultant** | Manages 500-5,000 contacts across industries. Relies on warm introductions and referral chains.         | Relationship mapping, employment timeline, warm intro paths, meeting prep briefs, stale contact alerts                  |
| **Sales Professional**     | Manages 200-2,000 contacts tied to active deals and pipeline. Needs to understand stakeholder dynamics. | Org chart reconstruction, decision-maker identification, engagement scoring, enrichment on demand, deal-contact linking |
| **General Business User**  | Manages 100-500 professional contacts. Wants an intelligent address book, not a data-entry chore.       | Auto-creation from email, zero-friction capture, basic enrichment, search, import/export                                |

### User Stories

#### Contact Creation & Capture

| ID    | Story                                                                                                                                                      | Acceptance Criteria                                                                                                                           |
| ----- | ---------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------- |
| CM-01 | As a user, I want contacts to be created automatically when I receive or send emails to new people, so I never have to manually enter contacts from email. | Email sync creates `status='incomplete'` contacts for unknown participants within 60 seconds of sync. Contact is linked to the communication. |
| CM-02 | As a user, I want to manually create a contact with name, company, email, and phone, so I can add people I meet at events.                                 | Form with required name, optional company/email/phone/social. Contact saved with `source='manual'`. Enrichment triggered automatically.       |
| CM-03 | As a user, I want to import contacts from a CSV file, so I can migrate from my existing CRM or address book.                                               | CSV upload with column mapping UI. Duplicate detection during import. Preview before commit. Progress indicator for large files.              |
| CM-04 | As a user, I want to import my Google Contacts, so my existing address book is available immediately.                                                      | OAuth-based sync via Google People API. UPSERT on email match. Ongoing incremental sync option.                                               |
| CM-05 | As a user, I want the browser extension to capture contact data from LinkedIn profiles I visit, so I can build my network without copy-pasting.            | Extension captures name, title, company, LinkedIn URL. Data pushed to API. Entity resolution matches to existing contact or creates new.      |
| CM-06 | As a user, I want to import contacts from a vCard file, so I can import from Apple Contacts or other vCard-compatible tools.                               | Standard vCard 3.0/4.0 parsing. Multi-contact vCard files supported. Same dedup/preview flow as CSV.                                          |

#### Contact Viewing & Editing

| ID    | Story                                                                                                                                                                       | Acceptance Criteria                                                                                                                               |
| ----- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| CM-07 | As a user, I want to see a unified contact detail page showing all information about a person — profile, communication history, relationships, intelligence — in one place. | Contact detail page with sections: Profile, Timeline, Relationships, Intelligence, Employment History, Notes, Deals. All data loads within 200ms. |
| CM-08 | As a user, I want to edit any contact field (name, title, company, emails, phones, social profiles), and have the change recorded with an audit trail.                      | Inline editing. Each change emits an event. `updated_at` reflects the change. Previous values visible in history tab.                             |
| CM-09 | As a user, I want to see a contact's full employment history — every company, title, and department they've held — in chronological order.                                  | Employment history timeline component showing positions with start/end dates, sourced from event store and enrichment.                            |
| CM-10 | As a user, I want to see when a contact's details changed (email, phone, title) and what they were before, so I can understand their career trajectory.                     | Point-in-time history view via event replay. "As of" date picker shows the contact's profile at any historical point.                             |
| CM-11 | As a user, I want to add notes to a contact, so I can record context from meetings, calls, or research.                                                                     | Note creation with rich text (Markdown). Notes appear on contact timeline. Notes are searchable via Meilisearch.                                  |

#### Identity Resolution & Deduplication

| ID    | Story                                                                                                                                                     | Acceptance Criteria                                                                                                                                                                                                                                                                                                                                                                                                                |
| ----- | --------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| CM-12 | As a user, I want the system to automatically detect when two contact records refer to the same person and merge them, so I don't have duplicate records. | High-confidence matches (email or LinkedIn URL match) auto-merge. Medium-confidence matches auto-merge with review flag. Low-confidence matches queued for human review.                                                                                                                                                                                                                                                           |
| CM-13 | As a user, I want to review suggested merges and approve or reject them, so the system doesn't merge contacts incorrectly.                                | Review queue UI showing candidate pairs with match signals, confidence score, and side-by-side comparison. Approve/reject actions with one click.                                                                                                                                                                                                                                                                                  |
| CM-14 | As a user, I want to manually merge two contacts when I notice duplicates, so I can clean up my data.                                                     | **Implemented.** Merge UI at `/contacts/merge` with conflict resolution for name and source. All identifiers, affiliations, communications, relationships, events, phones, addresses, emails, and social profiles transfer to the surviving record. Post-merge domain resolution auto-creates missing employment records. Audit trail in `contact_merges` table. Entry points: list checkboxes and identifier-conflict merge link. |
| CM-15 | As a user, I want to split a contact that was incorrectly merged, so I can undo a bad merge.                                                              | Split action restores original records from event history. Communications re-linked to the correct contact. Merge event reversed in audit trail.                                                                                                                                                                                                                                                                                   |
| CM-16 | As a user, I want to configure the auto-merge confidence threshold, so I can balance automation vs. review volume for my team's data quality needs.       | Tenant-level settings for high/medium/low confidence thresholds. Changes apply to future matches only, not retroactive.                                                                                                                                                                                                                                                                                                            |

#### Enrichment & Intelligence

| ID    | Story                                                                                                                                                                                    | Acceptance Criteria                                                                                                                  |
| ----- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| CM-17 | As a user, I want new contacts to be automatically enriched with public data (company, title, social profiles, photo) within minutes of creation.                                        | Background enrichment job fires on contact creation. Enriched fields merged with source attribution. Intelligence score updated.     |
| CM-18 | As a user, I want to manually trigger enrichment for a specific contact, so I can refresh stale data or fill gaps.                                                                       | "Enrich" button on contact detail page. Calls enrichment pipeline on demand. Shows results diff before applying.                     |
| CM-19 | As a user, I want to see where each piece of contact data came from (Google Contacts, LinkedIn, Apollo, manual entry) and how confident the system is.                                   | Source attribution badge on each field. Confidence score (0-1) visible on hover. Fields with conflicting sources show comparison.    |
| CM-20 | As a user, I want to set up monitoring alerts for key contacts, so I'm notified when they change jobs, their company raises funding, or other notable events occur.                      | Per-contact monitoring toggle. Configurable alert types (job change, funding, news). Notification via in-app alert, email, or Slack. |
| CM-21 | As a user, I want an AI-generated one-paragraph briefing on any contact that synthesizes all available data — profile, communication history, relationship context, recent intelligence. | "Brief me" action on contact detail. Claude generates briefing in < 5 seconds. Briefing cached with TTL. Refresh on demand.          |

#### Relationships & Graph

| ID    | Story                                                                                                                                                   | Acceptance Criteria                                                                                                                          |
| ----- | ------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------- |
| CM-22 | As a user, I want to define relationships between contacts (reports to, knows, introduced by, mentor of, etc.), so I can model my professional network. | Relationship creation UI with typed edges. Temporal bounds (since/until). Bidirectional visualization.                                       |
| CM-23 | As a user, I want to see a visual network graph of a contact's relationships — who they know, who they work with, how they connect to my network.       | Interactive graph visualization centered on the selected contact. Zoom, pan, filter by relationship type. Click-through to related contacts. |
| CM-24 | As a user, I want to find the shortest warm introduction path between me and a target contact through mutual connections.                               | Path-finding query via Neo4j. Shows intermediate contacts with relationship strength. Multiple paths ranked by overall strength.             |
| CM-25 | As a user, I want to see the organizational chart for a company reconstructed from contact relationships.                                               | Org chart view filtered by company. Inferred from REPORTS_TO, MANAGES, and WORKS_AT edges. Manual corrections supported.                     |

#### Search, Filtering & Segmentation

| ID    | Story                                                                                                                                 | Acceptance Criteria                                                                                                                |
| ----- | ------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| CM-26 | As a user, I want to search contacts by name, email, company, title, or any field using fuzzy text search.                            | Meilisearch-backed full-text search. Typo-tolerant. Results ranked by relevance. < 50ms response.                                  |
| CM-27 | As a user, I want to filter contacts by company, tag, lead status, engagement score, last contact date, and custom fields.            | Filter panel with AND/OR combinators. Saved filter presets. Contact list updates in real-time as filters change.                   |
| CM-28 | As a user, I want to create contact groups (e.g., "Conference Leads Q1", "Advisory Board") and add/remove contacts from them.         | Group CRUD. Bulk add/remove. Groups visible on contact detail page. Group-level communication templates.                           |
| CM-29 | As a user, I want to use natural language to search my contacts (e.g., "fintech founders in Boston I haven't talked to in 3 months"). | AI-powered NL search via Claude. Query translated to structured filters + Meilisearch + graph traversal. Results with explanation. |

---

## 5. Contact Data Model

### 5.1 Core Entities

The contact subsystem defines three primary entity types:

```
Contact (event-sourced)
  ├── Identity: name, photo, aliases
  ├── Classification: tags, categories, lead source, lead status
  ├── Custom fields: managed through unified field registry (Custom Objects PRD Section 8)
  ├── Computed: engagement_score, intelligence_score
  ├── Identifiers (multi-value, lifecycle-tracked)
  │   ├── Email addresses (work, personal, old)
  │   ├── Phone numbers (mobile, work, home)
  │   ├── Social profiles (LinkedIn, Twitter, GitHub)
  │   └── Any future identifier type
  ├── Employment history (temporal)
  │   └── Company + Title + Department + Start/End
  ├── Contact details (multi-value, temporal)
  │   ├── Addresses (work, home)
  │   └── Key dates (birthday, anniversary)
  ├── Intelligence items
  │   └── Enrichment data, OSINT, manual intel
  ├── Relationships (graph edges)
  │   └── Neo4j: KNOWS, REPORTS_TO, INTRODUCED_BY, etc.
  └── Activity timeline
      └── Communications, notes, deal events, intel updates
```

```
Company (event-sourced)
  ├── Identity: name, domain, logo, industry
  ├── Firmographics: size, location, revenue, funding
  ├── History: name changes, acquisitions, HQ moves
  ├── Employees: contacts with WORKS_AT edges
  └── Intelligence items
```

```
Group (conventional table)
  ├── Name, description, owner
  └── Members: many-to-many with contacts
```

### 5.2 Contact Record — Read Model Table (System Object Type)

> The Contact is a **system object type** in the unified framework (`is_system = true`). The `contacts` table is its dedicated read model table, managed through the object type framework within the tenant schema (e.g., `tenant_abc.contacts`). It is created by tenant schema provisioning, not hand-crafted SQL.

The `contacts` table is the read-optimized materialized view derived from the event store. All read operations query this table. Write operations append events and synchronously update the materialized view.

| Column               | Type | Constraints          | Description                                                                                                                                                                                                                                                 |
| -------------------- | ---- | -------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `id`                 | TEXT | **PK**               | Prefixed ULID: `con_` prefix (e.g., `con_01HX7VFBK3...`). Immutable after creation. Aligned with platform-wide prefixed entity ID convention per Custom Objects PRD Section 6 and Data Sources PRD.                                                         |
| `first_name`         | TEXT |                      | First name or given name                                                                                                                                                                                                                                    |
| `last_name`          | TEXT |                      | Last name or family name                                                                                                                                                                                                                                    |
| `display_name`       | TEXT | NOT NULL             | Computed: `first_name + ' ' + last_name`, or manual override                                                                                                                                                                                                |
| `email_primary`      | TEXT |                      | Denormalized from `contact_emails` for display performance. Kept in sync by event handler.                                                                                                                                                                  |
| `phone_primary`      | TEXT |                      | Denormalized from `contact_phones` for display performance.                                                                                                                                                                                                 |
| `job_title`          | TEXT |                      | Current job title (latest from `contacts__companies_employment` where `is_current=TRUE`)                                                                                                                                                                    |
| `company_id`         | TEXT | FK → `companies(id)` | Current company (latest from `contacts__companies_employment` where `is_current=TRUE`)                                                                                                                                                                      |
| `company_name`       | TEXT |                      | Denormalized company name for display performance (avoids JOIN)                                                                                                                                                                                             |
| `avatar_url`         | TEXT |                      | Profile photo URL (object storage or external)                                                                                                                                                                                                              |
| `lead_source`        | TEXT |                      | How this contact entered the system: `email_sync`, `google_contacts`, `csv_import`, `linkedin_capture`, `manual`, `enrichment`, `referral`                                                                                                                  |
| `lead_status`        | TEXT | DEFAULT `'new'`      | Sales lifecycle stage: `new`, `contacted`, `qualified`, `nurturing`, `customer`, `lost`, `inactive`                                                                                                                                                         |
| `engagement_score`   | REAL | DEFAULT 0.0          | Composite engagement metric (0.0–1.0). Computed from behavioral signals.                                                                                                                                                                                    |
| `intelligence_score` | REAL | DEFAULT 0.0          | Data completeness metric (0.0–1.0). How much we know about this contact.                                                                                                                                                                                    |
| `source`             | TEXT |                      | First source that created this contact                                                                                                                                                                                                                      |
| `status`             | TEXT | DEFAULT `'active'`   | Contact lifecycle: `active`, `incomplete`, `archived`, `merged`                                                                                                                                                                                             |
| ~~`custom_fields`~~  | —    | **REMOVED**          | ~~JSON object of tenant-defined custom field values.~~ **Removed:** Custom fields managed through the unified field registry (Custom Objects PRD Section 8). Each custom field is a typed column on the contacts table, added via `ALTER TABLE ADD COLUMN`. |
| `created_by`         | TEXT | FK → `users(id)`     | User who created the contact (NULL for auto-created)                                                                                                                                                                                                        |
| `created_at`         | TEXT | NOT NULL             | ISO 8601                                                                                                                                                                                                                                                    |
| `updated_at`         | TEXT | NOT NULL             | ISO 8601                                                                                                                                                                                                                                                    |
| `synced_at`          | TEXT |                      | ISO 8601 timestamp of last sync to clients                                                                                                                                                                                                                  |

**Notes:**

- `email_primary` and `phone_primary` are intentionally denormalized. The canonical data lives in `contact_emails` and `contact_phones`. These columns are updated by event handlers to avoid JOINs on list views.
- `company_name` is denormalized from `companies` for the same reason.
- `engagement_score` and `intelligence_score` are recomputed periodically by background jobs, not updated on every event.
- **Unified Object Model alignment:** The `contacts` table is the Contact object type's **dedicated read model table**, managed through the object type framework (Custom Objects PRD Section 17). It is created by tenant schema provisioning within the tenant's PostgreSQL schema (e.g., `tenant_abc.contacts`). Core fields listed above are registered as system fields (`is_system = true`) in the field registry and are protected from deletion. Tenants can add custom fields through the unified field registry, which triggers `ALTER TABLE ADD COLUMN` on this table.

### 5.3 Contact Identifiers

Multi-identifier resolution table. Every way a contact can be identified — email, phone, social handle, alias — is stored here with lifecycle tracking. This is the primary lookup table for resolving incoming communications to contacts.

| Column        | Type    | Constraints                                     | Description                                                                                                                          |
| ------------- | ------- | ----------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| `id`          | TEXT    | **PK**                                          | UUID v4                                                                                                                              |
| `contact_id`  | TEXT    | NOT NULL, FK → `contacts(id)` ON DELETE CASCADE | Which contact this identifier belongs to                                                                                             |
| `type`        | TEXT    | NOT NULL                                        | Identifier type: `email`, `phone`, `linkedin`, `twitter`, `github`, `slack`, `custom`                                                |
| `value`       | TEXT    | NOT NULL                                        | The identifier value, normalized. Email: lowercased, trimmed. Phone: E.164 format. LinkedIn: canonical URL.                          |
| `label`       | TEXT    |                                                 | User-facing label: `work`, `personal`, `mobile`, `home`, `old`, etc.                                                                 |
| `is_primary`  | INTEGER | DEFAULT 0                                       | Boolean. Primary identifier for this type. At most one primary per (contact_id, type).                                               |
| `status`      | TEXT    | DEFAULT `'active'`                              | Lifecycle: `active`, `inactive`, `unverified`                                                                                        |
| `source`      | TEXT    |                                                 | Discovery source: `google_contacts`, `email_sync`, `linkedin_capture`, `enrichment_apollo`, `enrichment_clearbit`, `manual`, `osint` |
| `confidence`  | REAL    | DEFAULT 1.0                                     | Confidence that this identifier belongs to this contact (0.0–1.0). Enrichment and auto-detection sources have < 1.0 confidence.      |
| `verified`    | INTEGER | DEFAULT 0                                       | Boolean. Confirmed by user, enrichment match, or verified source.                                                                    |
| `valid_from`  | TEXT    |                                                 | ISO 8601. When this identifier became active (e.g., when the person started at a new company).                                       |
| `valid_until` | TEXT    |                                                 | ISO 8601. When this identifier became inactive (e.g., when the person left a company). NULL = still active.                          |
| `created_at`  | TEXT    | NOT NULL                                        | ISO 8601                                                                                                                             |
| `updated_at`  | TEXT    | NOT NULL                                        | ISO 8601                                                                                                                             |

**Constraints:**

- `UNIQUE(type, value)` — No two contacts can claim the same identifier. If entity resolution discovers a conflict, it triggers a merge workflow.

**Resolution flow:**

```sql
-- Resolve any incoming identifier to a contact
SELECT contact_id, confidence, status
FROM contact_identifiers
WHERE type = :type AND LOWER(value) = LOWER(:value);
```

This single query works for email addresses, phone numbers, LinkedIn URLs, or any future identifier type. The `status` column ensures inactive identifiers still resolve for historical communications.

**Auto-creation flow** (when identifier not found):

1. Create a new `contacts` row with `source='email_sync'` (or appropriate source), `status='incomplete'`.
2. Create a `contact_identifiers` row linking the identifier.
3. Emit `ContactCreated` and `ContactIdentifierAdded` events.
4. Signal the enrichment pipeline to populate the contact.
5. All subsequent communications from the same identifier resolve instantly.

### 5.4 Contact Detail Tables (Multi-Value, Temporal)

These tables store multi-value contact details with temporal bounds, enabling historical tracking of how contact information has changed over time.

#### `contact_emails`

| Column        | Type    | Constraints                                     | Description                               |
| ------------- | ------- | ----------------------------------------------- | ----------------------------------------- |
| `id`          | TEXT    | **PK**                                          | UUID v4                                   |
| `contact_id`  | TEXT    | NOT NULL, FK → `contacts(id)` ON DELETE CASCADE |                                           |
| `email`       | TEXT    | NOT NULL                                        | Email address, lowercased                 |
| `type`        | TEXT    | DEFAULT `'work'`                                | `work`, `personal`, `other`               |
| `is_primary`  | INTEGER | DEFAULT 0                                       | Boolean. At most one primary per contact. |
| `valid_from`  | TEXT    |                                                 | ISO 8601. NULL = unknown start date.      |
| `valid_until` | TEXT    |                                                 | ISO 8601. NULL = still active.            |

#### `contact_phones`

| Column        | Type    | Constraints                                     | Description                               |
| ------------- | ------- | ----------------------------------------------- | ----------------------------------------- |
| `id`          | TEXT    | **PK**                                          | UUID v4                                   |
| `contact_id`  | TEXT    | NOT NULL, FK → `contacts(id)` ON DELETE CASCADE |                                           |
| `phone`       | TEXT    | NOT NULL                                        | E.164 format                              |
| `type`        | TEXT    | DEFAULT `'mobile'`                              | `mobile`, `work`, `home`, `fax`, `other`  |
| `is_primary`  | INTEGER | DEFAULT 0                                       | Boolean. At most one primary per contact. |
| `valid_from`  | TEXT    |                                                 |                                           |
| `valid_until` | TEXT    |                                                 |                                           |

#### `contact_social_profiles`

| Column        | Type | Constraints                                     | Description                                                       |
| ------------- | ---- | ----------------------------------------------- | ----------------------------------------------------------------- |
| `id`          | TEXT | **PK**                                          | UUID v4                                                           |
| `contact_id`  | TEXT | NOT NULL, FK → `contacts(id)` ON DELETE CASCADE |                                                                   |
| `platform`    | TEXT | NOT NULL                                        | `linkedin`, `twitter`, `github`, `facebook`, `instagram`, `other` |
| `url`         | TEXT |                                                 | Full profile URL                                                  |
| `username`    | TEXT |                                                 | Platform-specific handle                                          |
| `valid_from`  | TEXT |                                                 |                                                                   |
| `valid_until` | TEXT |                                                 |                                                                   |

#### `contact_addresses`

| Column        | Type | Constraints                                     | Description                      |
| ------------- | ---- | ----------------------------------------------- | -------------------------------- |
| `id`          | TEXT | **PK**                                          | UUID v4                          |
| `contact_id`  | TEXT | NOT NULL, FK → `contacts(id)` ON DELETE CASCADE |                                  |
| `street`      | TEXT |                                                 | Street address (line 1 + line 2) |
| `city`        | TEXT |                                                 |                                  |
| `state`       | TEXT |                                                 | State, province, or region       |
| `country`     | TEXT |                                                 | ISO 3166-1 alpha-2 country code  |
| `postal_code` | TEXT |                                                 |                                  |
| `type`        | TEXT | DEFAULT `'work'`                                | `work`, `home`, `other`          |
| `valid_from`  | TEXT |                                                 |                                  |
| `valid_until` | TEXT |                                                 |                                  |

#### `contact_key_dates`

| Column       | Type | Constraints                                     | Description                                           |
| ------------ | ---- | ----------------------------------------------- | ----------------------------------------------------- |
| `id`         | TEXT | **PK**                                          | UUID v4                                               |
| `contact_id` | TEXT | NOT NULL, FK → `contacts(id)` ON DELETE CASCADE |                                                       |
| `type`       | TEXT | NOT NULL                                        | `birthday`, `work_anniversary`, `first_met`, `custom` |
| `date`       | TEXT | NOT NULL                                        | ISO 8601 date (YYYY-MM-DD)                            |
| `label`      | TEXT |                                                 | Custom label (for `type='custom'`)                    |
| `source`     | TEXT |                                                 | How this date was discovered                          |

### 5.5 Employment History (System Relation Type)

Employment history is a **system Relation Type** (Contact→Company) in the unified framework, defined per Custom Objects PRD Sections 14–15. It models the temporal employment relationship between contacts and companies as a many-to-many relation with metadata.

**Relation Type definition:**

| Attribute            | Value           |
| -------------------- | --------------- |
| `name`               | Employment      |
| `source_object_type` | Contact         |
| `target_object_type` | Company         |
| `cardinality`        | `many_to_many`  |
| `directionality`     | `bidirectional` |
| `source_field_label` | Employer        |
| `target_field_label` | Employees       |
| `has_metadata`       | `true`          |
| `neo4j_sync`         | `true`          |
| `neo4j_edge_type`    | `WORKS_AT`      |
| `is_system`          | `true`          |
| `cascade_behavior`   | `nullify`       |

**Junction table:** `contacts__companies_employment`

Temporal employment records linking contacts to companies. Enables career trajectory analysis, org chart reconstruction, and “where did they work before?” queries. Because this is a many-to-many relation with metadata, instances are stored in a dedicated junction table managed by the Relation Type framework (Custom Objects PRD Section 14.2).

| Column         | Type        | Constraints                                       | Description                                                                                                                                                          |
| -------------- | ----------- | ------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `id`           | TEXT        | **PK**                                            | Relation instance ID (prefixed ULID)                                                                                                                                 |
| `source_id`    | TEXT        | NOT NULL, FK → `contacts(id)` ON DELETE CASCADE   | The contact (source entity in the Relation Type)                                                                                                                     |
| `target_id`    | TEXT        | NOT NULL, FK → `companies(id)` ON DELETE SET NULL | The company (target entity). NULL if company not yet in system.                                                                                                      |
| `company_name` | TEXT        | NOT NULL                                          | Company name at time of employment. Denormalized metadata: preserved even if the Company record is renamed or the target is nullified, ensuring historical accuracy. |
| `title`        | TEXT        |                                                   | Job title                                                                                                                                                            |
| `department`   | TEXT        |                                                   | Department or team                                                                                                                                                   |
| `started_at`   | TIMESTAMPTZ |                                                   | NULL = unknown start date.                                                                                                                                           |
| `ended_at`     | TIMESTAMPTZ |                                                   | NULL = still employed.                                                                                                                                               |
| `is_current`   | BOOLEAN     | DEFAULT false                                     | TRUE for current positions. Enforced: at most one `is_current = true` per source_id (contact).                                                                       |
| `source`       | TEXT        |                                                   | Discovery source: `manual`, `linkedin_capture`, `enrichment_apollo`, `email_signature`, `google_contacts`                                                            |
| `confidence`   | REAL        | DEFAULT 1.0                                       | Source confidence (0.0–1.0)                                                                                                                                          |
| `created_at`   | TIMESTAMPTZ | NOT NULL                                          |                                                                                                                                                                      |
| `created_by`   | TEXT        |                                                   | User or system process that created this record                                                                                                                      |

**Constraints:**

- `UNIQUE(source_id, target_id, COALESCE(started_at, ''))` — A contact can have multiple stints at the same company, distinguished by start date. NULL start dates are treated as equal for dedup purposes.
- Index on `(source_id, is_current)` for fast “current employer” lookup.
- Index on `(target_id, is_current)` for fast “current employees at company” lookup.

**Temporal semantics:** Unlike standard many-to-many junction tables where each `(source_id, target_id)` pair appears once, employment allows the same pair to appear multiple times representing separate employment periods (e.g., a boomerang employee). The `started_at` column disambiguates these.

**Neo4j sync:** Each junction row syncs to a `WORKS_AT` edge in Neo4j with properties `{role, department, since, until, is_current}`, enabling graph queries like “who do we know at Company X?” and career trajectory analysis.

---

## 6. Company Data Model

> **Authoritative source:** The Company entity type — its data model, domain resolution, enrichment pipeline, duplicate detection & merging, hierarchy, relationship scoring, social media profiles, and intelligence — is fully specified in the **[Company Management & Intelligence PRD](company-management-prd_V1.md)**.
> 
> This section provides only the summary necessary for understanding Contact↔Company interactions. For the complete Company data model, field registry, API design, and all company-specific behaviors, see the Company PRD.

### 6.1 Company as System Object Type

Company is a **system object type** (`is_system = true`, prefix `cmp_`). The `companies` table is its dedicated read model table within the tenant schema. Key fields include `name`, `domain` (primary web domain, used for email domain matching), `industry`, `size_range`, `location`, `website`, `founded_year`, `revenue_range`, `funding_stage`, and `linkedin_url`. See [Company PRD Section 4](company-management-prd_V1.md#4-company-data-model) for the complete field registry.

### 6.2 Company Domain Resolution (Summary)

Companies are discovered and linked via email domain. The domain resolution flow: extract domain from email → skip public domains (gmail.com, yahoo.com, etc.) → normalize to root domain → look up `company_identifiers` → auto-create company if not found (with name = domain as placeholder) → trigger enrichment to discover real name. The Google Contacts organization name field is ignored entirely — the email domain is the sole source of truth for company identity. See [Company PRD Section 5](company-management-prd_V1.md#5-company-identifiers--domain-resolution) for the complete resolution flow, normalization rules, and public domain exclusion list.

When a company is resolved from a domain, the contact is linked via the Contact→Company employment Relation Type (Section 5.5 of this document).

### 6.3 Company-to-Company Relationships (Neo4j)

Company hierarchy (subsidiary, division, acquisition, spinoff) and business relationships (partner, competitor, vendor, client) are modeled as Relation Types and synced to Neo4j. See [Company PRD Section 7](company-management-prd_V1.md#7-company-hierarchy) for hierarchy and [Company PRD Section 13](company-management-prd_V1.md#13-company-to-company-relationships-neo4j) for Neo4j graph edges.

---

## 7. Identity Resolution & Entity Matching

### 7.1 The Identity Problem

A single person may appear in CRMExtender through multiple channels with different identifiers:

```
Google Contacts:       "Sarah Chen" <sarah@acmecorp.com>
Email sender:          "Sarah" <sarah.chen@acmecorp.com>
LinkedIn capture:      Sarah Chen, VP Engineering at Acme Corp, linkedin.com/in/sarahchen
Apollo enrichment:     Sarah Chen, sarah@acmecorp.com, +1-555-0199
Manual entry:          Sarah Chen, Acme Corp, sarahc@gmail.com
```

Without identity resolution, these create five separate contact records. With it, they merge into one:

```
Contact: Sarah Chen (Acme Corp)  [status=active, intelligence_score=0.85]
├── email: sarah@acmecorp.com         (active, work, primary, verified, google_contacts)
├── email: sarah.chen@acmecorp.com    (active, work, verified, email_sync)
├── email: sarahc@gmail.com           (active, personal, verified, manual)
├── phone: +15550199                  (active, mobile, primary, enrichment_apollo)
├── linkedin: linkedin.com/in/sarahchen  (active, verified, linkedin_capture)
└── Employment: VP Engineering @ Acme Corp (current, enrichment_apollo + linkedin_capture)
```

### 7.2 Matching Strategy

Identity resolution uses a **tiered confidence model** with configurable thresholds:

| Tier       | Signal Combination                                   | Default Confidence | Default Action              |
| ---------- | ---------------------------------------------------- | ------------------ | --------------------------- |
| **Exact**  | Email address exact match                            | 1.0                | Auto-merge, no flag         |
| **Exact**  | LinkedIn profile URL match                           | 1.0                | Auto-merge, no flag         |
| **Exact**  | Phone number exact match (E.164 normalized)          | 0.95               | Auto-merge, no flag         |
| **High**   | Name + Company + Title fuzzy match (>90% similarity) | 0.80–0.95          | Auto-merge with review flag |
| **High**   | Name + Email domain match                            | 0.80–0.90          | Auto-merge with review flag |
| **Medium** | Name + Company fuzzy match (no title)                | 0.60–0.80          | Auto-merge with review flag |
| **Medium** | Name + Location match                                | 0.50–0.70          | Queue for human review      |
| **Low**    | Name-only fuzzy match                                | 0.20–0.50          | Queue for human review      |

**Confidence scoring formula:**

Each signal contributes a weighted confidence value. The combined confidence is computed as:

```
confidence = 1 - ((1 - s1) * (1 - s2) * ... * (1 - sN))
```

Where `s1...sN` are the individual signal confidences. This ensures multiple weak signals can combine to produce a strong match (e.g., name + company + location together reach high confidence even though each alone is medium).

**Signal weights:**

| Signal                  | Weight | Notes                                       |
| ----------------------- | ------ | ------------------------------------------- |
| Email exact match       | 1.0    | Definitive identifier                       |
| LinkedIn URL match      | 1.0    | Definitive identifier                       |
| Phone E.164 match       | 0.95   | Very high but not 1.0 (shared phones exist) |
| Name exact match        | 0.30   | Common names reduce this weight             |
| Name fuzzy match (>90%) | 0.20   | Levenshtein + phonetic                      |
| Company exact match     | 0.25   |                                             |
| Company fuzzy match     | 0.15   |                                             |
| Title match             | 0.15   |                                             |
| Email domain match      | 0.20   | Same company domain                         |
| Location match          | 0.10   | Same city/region                            |

### 7.3 Entity Resolution Pipeline

```
Incoming data (email sync, enrichment, browser extension, manual entry)
  │
  ▼
┌──────────────────────────────────┐
│  1. Identifier Extraction        │
│     Extract email, phone, name,  │
│     company, title, social URLs  │
└──────────────┬───────────────────┘
               │
               ▼
┌──────────────────────────────────┐
│  2. Exact Match Lookup           │
│     Check contact_identifiers    │
│     for email, phone, LinkedIn   │
│     If found → existing contact  │
└──────────────┬───────────────────┘
               │ not found
               ▼
┌──────────────────────────────────┐
│  3. Fuzzy Match Candidates       │
│     Name + Company similarity    │
│     via Meilisearch or trigram   │
│     Returns top-N candidates     │
└──────────────┬───────────────────┘
               │
               ▼
┌──────────────────────────────────┐
│  4. Confidence Scoring           │
│     Score each candidate using   │
│     weighted signal combination  │
│     Apply tenant thresholds      │
└──────────────┬───────────────────┘
               │
     ┌─────────┼──────────┐
     │         │          │
     ▼         ▼          ▼
  ┌──────┐ ┌──────┐ ┌──────────┐
  │ Auto │ │ Auto │ │ Human    │
  │Merge │ │Merge │ │ Review   │
  │      │ │+Flag │ │ Queue    │
  └──┬───┘ └──┬───┘ └──────────┘
     │         │
     ▼         ▼
┌──────────────────────────────────┐
│  5. Merge Execution              │
│     - Pick survivor contact_id   │
│     - Move all identifiers       │
│     - Update participant FKs     │
│     - Emit MergeExecuted event   │
│     - Log in match_candidates    │
└──────────────────────────────────┘
```

### 7.4 Match Candidates Table

| Column             | Type | Constraints         | Description                                                                                                |
| ------------------ | ---- | ------------------- | ---------------------------------------------------------------------------------------------------------- |
| `id`               | TEXT | **PK**              | UUID v4                                                                                                    |
| `entity_type`      | TEXT | NOT NULL            | `contact` or `company`                                                                                     |
| `entity_a_id`      | TEXT | NOT NULL            | First entity in the candidate pair                                                                         |
| `entity_b_id`      | TEXT | NOT NULL            | Second entity in the candidate pair                                                                        |
| `confidence_score` | REAL | NOT NULL            | Combined confidence (0.0–1.0)                                                                              |
| `match_signals`    | TEXT | NOT NULL            | JSON array of signal details: `[{"signal": "email_exact", "weight": 1.0, "value": "sarah@acme.com"}, ...]` |
| `status`           | TEXT | DEFAULT `'pending'` | `pending`, `approved`, `rejected`, `auto_merged`                                                           |
| `reviewed_by`      | TEXT | FK → `users(id)`    | User who reviewed (NULL for auto-merged)                                                                   |
| `reviewed_at`      | TEXT |                     | ISO 8601                                                                                                   |
| `created_at`       | TEXT | NOT NULL            | ISO 8601                                                                                                   |

**Constraints:**

- `UNIQUE(entity_type, entity_a_id, entity_b_id)` — One candidate record per pair.
- Index on `(status)` for the review queue query.

### 7.5 Source Records Table

Preserves the original data from each source before merge. Enables split (undo merge) and source attribution.

| Column        | Type | Constraints      | Description                                                                                             |
| ------------- | ---- | ---------------- | ------------------------------------------------------------------------------------------------------- |
| `id`          | TEXT | **PK**           | UUID v4                                                                                                 |
| `entity_type` | TEXT | NOT NULL         | `contact` or `company`                                                                                  |
| `entity_id`   | TEXT | NOT NULL         | The merged entity this came from                                                                        |
| `source`      | TEXT | NOT NULL         | Source system: `google_contacts`, `email_sync`, `linkedin_capture`, `enrichment_apollo`, `manual`, etc. |
| `source_id`   | TEXT |                  | Source system's native ID (e.g., Google People API `resourceName`)                                      |
| `raw_data`    | TEXT | NOT NULL         | JSON blob of original data as received from the source                                                  |
| `captured_at` | TEXT | NOT NULL         | ISO 8601 timestamp of data capture                                                                      |
| `captured_by` | TEXT | FK → `users(id)` | User who captured (NULL for automated sources)                                                          |

### 7.6 Merge & Split Semantics

> **Implementation status:** Contact merge is fully implemented in `poc/contact_merge.py`.
> Split (undo merge) is not yet implemented.

**Entry points:**

1. **List selection** — Select 2+ contacts via checkboxes on the Contacts list, click "Merge Selected".
2. **Identifier conflict** — When adding an email in the Email Addresses section that belongs to another contact, the error message includes a "Merge these contacts?" link. (The generic Identifiers section has been removed from the contact detail page — email identifiers are managed via the type-specific Email Addresses section, backed by `contact_identifiers` where `type='email'`.)

**Merge preview** (`GET /contacts/merge?ids=X&ids=Y`):

- Side-by-side contact cards with per-contact counts (identifiers, affiliations, conversations, relationships, events, phones, addresses, emails, social profiles).
- Conflict resolution: radio buttons for `name` and `source` when distinct values exist across contacts.
- Radio buttons to designate the surviving contact (which ID persists).
- Combined/deduplicated totals showing the merged result.

**Merge execution** (`POST /contacts/merge/confirm`):

1. User designates the **survivor** contact via radio button selection.
2. All absorbed contacts are processed in a single PostgreSQL transaction.
3. For each absorbed contact:
   a. Snapshot the absorbed contact and all sub-entities as JSON (audit trail).
   b. Transfer and deduplicate `contact_identifiers` (DELETE conflicts by type+value, UPDATE rest).
   c. Transfer and deduplicate `contacts__companies_employment` records (DELETE conflicts by target_id+started_at, UPDATE source_id to surviving contact).
   d. Transfer and deduplicate `contact_social_profiles` (DELETE conflicts by platform+profile_url, UPDATE rest).
   e. Reassign `conversation_participants` (SET contact_id = surviving).
   f. Reassign `communication_participants` (SET contact_id = surviving).
   g. Reassign all relation instances across all Relation Type junction/instance tables where absorbed contact appears as `source_id` or `target_id`. Deduplicate pairs that would become identical after reassignment. Delete self-referential relations that result from merging two contacts who had a relation between them.
   h. Reassign `event_participants` (entity_type='contact').
   i. Transfer and deduplicate `contact_phones` (by normalized number), `contact_addresses`, and `contact_emails` (by lowercased email). UPDATE contact_id to surviving contact; DELETE duplicates.
   j. Transfer `user_contacts` visibility (INSERT OR IGNORE). *(Table owned by Permissions PRD.)*
   k. Transfer `enrichment_runs`, delete `entity_scores` for absorbed. *(Tables owned by Enrichment subsystem; schemas defined at implementation time.)*
   l. Re-point prior `contact_merges` audit records.
   m. DELETE absorbed contact (CASCADE handles remaining child rows).
   n. Write audit record to `contact_merges` table.
4. Apply chosen field values (`name`, `source`) on the surviving contact.
5. **Post-merge domain resolution:** Resolve email domains from all merged identifiers and auto-create missing company affiliations via `domain_resolver`. This handles the common case where two contacts from different companies are merged — both affiliations are preserved.
6. Redirect to the surviving contact's detail page.

**Audit table** (`contact_merges`):

| Column                       | Type    | Description                              |
| ---------------------------- | ------- | ---------------------------------------- |
| `id`                         | TEXT PK | UUID                                     |
| `surviving_contact_id`       | TEXT FK | Contact that persists                    |
| `absorbed_contact_id`        | TEXT    | Contact that was deleted                 |
| `absorbed_contact_snapshot`  | TEXT    | Full JSON snapshot before deletion       |
| `identifiers_transferred`    | INTEGER | Count of identifiers moved               |
| `affiliations_transferred`   | INTEGER | Count of affiliations moved              |
| `conversations_reassigned`   | INTEGER | Count of conversations reassigned        |
| `relationships_reassigned`   | INTEGER | Count of relationships moved             |
| `events_reassigned`          | INTEGER | Count of event participations moved      |
| `relationships_deduplicated` | INTEGER | Count of duplicate relationships removed |
| `merged_by`                  | TEXT FK | User who performed the merge             |
| `merged_at`                  | TEXT    | ISO 8601 timestamp                       |

**Employment dedup during merge:** The merge deduplicates employment records in `contacts__companies_employment` using `(target_id, COALESCE(started_at, ''))` tuple comparison, so NULL start dates are treated as equal. This aligns with the junction table’s `UNIQUE(source_id, target_id, COALESCE(started_at, ''))` constraint. After merge, email domain resolution auto-creates any missing employment affiliations for the surviving contact’s email domains.

**Contact list primary email:** When a contact has multiple email identifiers (common after merges), the contacts list uses a correlated subquery to display the primary email (`ORDER BY is_primary DESC, created_at ASC LIMIT 1`) rather than relying on `GROUP BY` which picks arbitrarily.

**Split execution (undo merge):** Not yet implemented. The `absorbed_contact_snapshot` JSON preserves enough data for future reconstruction.

---

## 8. Contact Lifecycle Management

### 8.1 Contact Statuses

| Status       | Description                                                                                                                    | Transitions                                  |
| ------------ | ------------------------------------------------------------------------------------------------------------------------------ | -------------------------------------------- |
| `incomplete` | Auto-created from an unknown identifier. Minimal data. Awaiting enrichment.                                                    | → `active` (after enrichment or manual edit) |
| `active`     | Fully identified contact with at least name + one verified identifier.                                                         | → `archived`, → `merged`                     |
| `archived`   | User-archived contact. Excluded from active lists but data preserved. Identifiers still resolve for historical communications. | → `active` (unarchive)                       |
| `merged`     | Duplicate contact that was merged into another record. Soft-deleted.                                                           | → `active` (via split/undo merge)            |

### 8.2 Contact Creation Sources

| Source             | Trigger                                       | Initial Status                             | Auto-Enrichment        |
| ------------------ | --------------------------------------------- | ------------------------------------------ | ---------------------- |
| `email_sync`       | Unknown email participant during sync         | `incomplete`                               | Yes                    |
| `google_contacts`  | Google People API sync                        | `active`                                   | Yes                    |
| `linkedin_capture` | Browser extension captures LinkedIn profile   | `active`                                   | Optional               |
| `csv_import`       | CSV file upload                               | `active` (if name present) or `incomplete` | Yes                    |
| `vcard_import`     | vCard file upload                             | `active`                                   | Yes                    |
| `manual`           | User creates via UI                           | `active`                                   | Yes                    |
| `enrichment`       | Enrichment discovers a new related contact    | `incomplete`                               | Yes (chain enrichment) |
| `referral`         | User explicitly links a referral relationship | `active`                                   | Yes                    |

### 8.3 Contact Deletion & Data Retention

Contacts are **never hard-deleted** in the normal workflow. The event-sourced model preserves all data for audit and compliance.

**Soft deletion:** Setting `status='archived'` hides the contact from active lists. The record, all identifiers, and all history remain in the system. Identifiers continue to resolve for historical communications.

**Hard deletion (GDPR/CCPA):** A dedicated data subject access request (DSAR) workflow:

1. User initiates deletion request with justification.
2. System generates a data export for the contact (all events, identifiers, communications, intelligence).
3. After confirmation, the system:
   - Deletes all events for the contact from the event store.
   - Deletes the materialized view row.
   - Deletes all identifiers, detail records, and intelligence items.
   - Anonymizes communication participant references (replaces `contact_id` with NULL, preserves address for thread integrity).
   - Removes the Neo4j graph node and all edges.
4. An audit record of the deletion itself is preserved (without PII).

---

## 9. Contact Intelligence & Enrichment

### 9.1 Enrichment Architecture

```
Contact created / enrichment requested
  │
  ▼
┌──────────────────────────────────┐
│  Enrichment Dispatcher           │
│  (Celery task)                   │
│                                  │
│  Selects adapter based on:       │
│  - Available identifiers         │
│  - Adapter priority/cost         │
│  - Rate limits                   │
└──────────────┬───────────────────┘
               │
     ┌─────────┼──────────┬──────────────┐
     ▼         ▼          ▼              ▼
  ┌──────┐ ┌──────┐ ┌──────────┐ ┌───────────┐
  │Apollo│ │Clear-│ │  People  │ │  Custom   │
  │      │ │ bit  │ │ Data Labs│ │  Adapter  │
  └──┬───┘ └──┬───┘ └────┬─────┘ └─────┬─────┘
     │         │          │             │
     └─────────┼──────────┘─────────────┘
               │
               ▼
┌──────────────────────────────────┐
│  Enrichment Normalizer           │
│  - Maps adapter response to      │
│    common schema                 │
│  - Assigns confidence scores     │
│  - Detects conflicts with        │
│    existing data                 │
└──────────────┬───────────────────┘
               │
               ▼
┌──────────────────────────────────┐
│  Enrichment Merger               │
│  - Higher-confidence data wins   │
│  - User-entered data always wins │
│  - Source attribution preserved  │
│  - Events emitted for all        │
│    changes                       │
└──────────────┬───────────────────┘
               │
               ▼
┌──────────────────────────────────┐
│  Intelligence Score Update       │
│  - Recalculate intelligence_score│
│  - Update contacts table       │
│  - Index in Meilisearch          │
└──────────────────────────────────┘
```

### 9.2 Enrichment Adapters

The enrichment system uses a pluggable adapter pattern. Each adapter normalizes external data to a common schema:

| Adapter                     | Input                         | Output                                                    | Priority               | Cost       |
| --------------------------- | ----------------------------- | --------------------------------------------------------- | ---------------------- | ---------- |
| **Apollo**                  | Email or domain               | Full profile (name, title, company, phone, social, photo) | 1 (primary)            | Per-lookup |
| **Clearbit**                | Email or domain               | Company + person data, firmographics                      | 2                      | Per-lookup |
| **People Data Labs**        | Email, phone, or name+company | Person + company data                                     | 3                      | Per-lookup |
| **Google People API**       | OAuth + contact sync          | Name, emails, phones, addresses, photos                   | 0 (free, pre-existing) | Free       |
| **LinkedIn (browser ext.)** | Browser extension capture     | Profile, headline, experience, connections                | N/A (user-driven)      | Free       |
| **Email signature parser**  | Email body parsing            | Name, title, company, phone, address                      | N/A (passive)          | Free       |

**Adapter interface:**

```python
class EnrichmentAdapter(Protocol):
    """Common interface for all enrichment adapters."""

    def can_enrich(self, contact: ContactCurrent, identifiers: list[ContactIdentifier]) -> bool:
        """Return True if this adapter can enrich given the available identifiers."""
        ...

    def enrich(self, contact: ContactCurrent, identifiers: list[ContactIdentifier]) -> EnrichmentResult:
        """Perform enrichment lookup and return normalized result."""
        ...

    @property
    def source_name(self) -> str:
        """Unique adapter identifier (e.g., 'enrichment_apollo')."""
        ...

    @property
    def rate_limit(self) -> tuple[int, int]:
        """(max_requests, per_seconds) rate limit for this adapter."""
        ...
```

### 9.3 Intelligence Items

Discrete pieces of intelligence about a contact or company, sourced from enrichment, OSINT monitoring, or manual entry.

| Column        | Type | Constraints          | Description                                                                                                                                              |
| ------------- | ---- | -------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `id`          | TEXT | **PK**               | UUID v4                                                                                                                                                  |
| `contact_id`  | TEXT | FK → `contacts(id)`  | Linked contact (NULL if company-level intel)                                                                                                             |
| `company_id`  | TEXT | FK → `companies(id)` | Linked company (NULL if contact-level intel)                                                                                                             |
| `source`      | TEXT | NOT NULL             | Data source: `enrichment_apollo`, `osint_news`, `osint_sec`, `browser_extension`, `manual`, etc.                                                         |
| `category`    | TEXT | NOT NULL             | `job_change`, `funding_round`, `news_mention`, `social_activity`, `technology_change`, `hiring_signal`, `acquisition`, `patent`, `publication`, `custom` |
| `title`       | TEXT | NOT NULL             | Brief headline for the intelligence item                                                                                                                 |
| `summary`     | TEXT |                      | Longer description or context                                                                                                                            |
| `raw_data`    | TEXT |                      | JSON blob of original source data                                                                                                                        |
| `url`         | TEXT |                      | Source URL (news article, SEC filing, etc.)                                                                                                              |
| `confidence`  | REAL | DEFAULT 1.0          | Confidence that this intel is accurate (0.0–1.0)                                                                                                         |
| `verified_by` | TEXT | FK → `users(id)`     | User who verified (NULL if unverified)                                                                                                                   |
| `verified_at` | TEXT |                      | ISO 8601                                                                                                                                                 |
| `expires_at`  | TEXT |                      | ISO 8601. For time-sensitive intel (e.g., a job posting that closes).                                                                                    |
| `created_at`  | TEXT | NOT NULL             | ISO 8601                                                                                                                                                 |

### 9.4 OSINT Monitors

Configurable monitors that periodically check for changes to tracked entities.

| Column         | Type | Constraints        | Description                                                                                     |
| -------------- | ---- | ------------------ | ----------------------------------------------------------------------------------------------- |
| `id`           | TEXT | **PK**             | UUID v4                                                                                         |
| `entity_type`  | TEXT | NOT NULL           | `contact` or `company`                                                                          |
| `entity_id`    | TEXT | NOT NULL           | ID of the monitored contact or company                                                          |
| `source`       | TEXT | NOT NULL           | Which source to monitor: `linkedin`, `news`, `sec`, `domain`, `enrichment`                      |
| `frequency`    | TEXT | DEFAULT `'daily'`  | Check frequency: `hourly`, `daily`, `weekly`                                                    |
| `last_checked` | TEXT |                    | ISO 8601 timestamp of last check                                                                |
| `status`       | TEXT | DEFAULT `'active'` | `active`, `paused`, `expired`                                                                   |
| `alert_types`  | TEXT |                    | JSON array of alert categories to trigger on: `["job_change", "funding_round", "news_mention"]` |
| `created_at`   | TEXT | NOT NULL           | ISO 8601                                                                                        |

### 9.5 Intelligence Score Computation

The intelligence score reflects how much the system knows about a contact, weighted by data quality:

| Field Category            | Weight | Scoring Rule                              |
| ------------------------- | ------ | ----------------------------------------- |
| **Name** (first + last)   | 0.15   | 0.15 if both present, 0.08 if only one    |
| **Email** (verified)      | 0.15   | 0.15 if at least one verified email       |
| **Phone** (verified)      | 0.10   | 0.10 if at least one verified phone       |
| **Company** (current)     | 0.10   | 0.10 if current employment record exists  |
| **Title** (current)       | 0.08   | 0.08 if current job title exists          |
| **Social profiles**       | 0.07   | 0.035 per profile (max 2 counted)         |
| **Photo**                 | 0.05   | 0.05 if avatar_url is set                 |
| **Address**               | 0.05   | 0.05 if at least one address              |
| **Employment history**    | 0.10   | 0.05 per historical position (max 2)      |
| **Enrichment data**       | 0.10   | 0.10 if at least one enrichment source    |
| **Communication history** | 0.05   | 0.05 if at least one communication linked |

**Total: 1.0.** Score recomputed on enrichment, identity merge, and on a scheduled basis (daily).

---

## 10. Relationship Intelligence

### 10.1 Graph Model (Neo4j)

> The relationship taxonomy below maps to the **first-class Relation Type model** established in Custom Objects PRD Section 14. Each relationship category below is defined as a Relation Type with `neo4j_sync = true`, which automatically syncs relation instances to Neo4j as graph edges. The Neo4j edge types, properties, and queries described below remain valid — the change is that the Relation Type framework manages the definition and sync, rather than ad-hoc graph operations.

Contacts and companies exist as nodes in a Neo4j property graph. Relationships are typed, directed edges with temporal bounds and metadata.

**Node types:**

```cypher
(:Contact {id, tenant_id, display_name, company_name, engagement_score})
(:Company {id, tenant_id, name, industry, domain})
(:Deal    {id, tenant_id, title, stage, value})
(:Event   {id, tenant_id, name, date})
(:Group   {id, tenant_id, name})
(:Skill   {name})
(:Industry {name})
```

**Relationship taxonomy:**

| Category         | Edge Type            | Properties                                           | Description                               |
| ---------------- | -------------------- | ---------------------------------------------------- | ----------------------------------------- |
| **Hierarchical** | `REPORTS_TO`         | `since`, `until`                                     | Direct reporting relationship             |
|                  | `MANAGES`            | `since`, `until`                                     | Direct management relationship            |
|                  | `DOTTED_LINE_TO`     | `context`                                            | Indirect reporting / matrix               |
| **Professional** | `WORKS_WITH`         | `context`                                            | Colleague relationship                    |
|                  | `ADVISES`            | `since`, `domain`                                    | Advisory relationship                     |
|                  | `BOARD_MEMBER_OF`    | `since`, `until`                                     | Board membership (Contact→Company)        |
|                  | `INVESTOR_IN`        | `round`, `amount`                                    | Investment relationship (Contact→Company) |
| **Social**       | `KNOWS`              | `strength`, `since`, `context`, `last_interaction`   | General acquaintance                      |
|                  | `INTRODUCED_BY`      | `date`, `outcome`                                    | Introduction provenance                   |
|                  | `REFERRED_BY`        | `date`, `context`                                    | Referral provenance                       |
|                  | `MENTOR_OF`          | `since`, `domain`                                    | Mentorship                                |
| **Employment**   | `WORKS_AT`           | `role`, `department`, `since`, `until`, `is_current` | Employment (Contact→Company)              |
| **Deal**         | `DECISION_MAKER_FOR` |                                                      | Deal stakeholder role                     |
|                  | `INFLUENCER_ON`      |                                                      | Deal stakeholder role                     |
|                  | `CHAMPION_OF`        |                                                      | Deal stakeholder role                     |
|                  | `PARTICIPATES_IN`    |                                                      | General deal involvement                  |
| **Other**        | `ATTENDED`           | `role`                                               | Event attendance                          |
|                  | `MEMBER_OF`          |                                                      | Group membership                          |
|                  | `HAS_SKILL`          |                                                      | Skill tagging                             |
|                  | `INTERESTED_IN`      |                                                      | Industry interest                         |

### 10.2 Relationship Strength Scoring

The `KNOWS` relationship includes a `strength` property (0.0–1.0) that reflects the depth and recency of the relationship:

**Input signals:**

| Signal                  | Weight | Description                                                     |
| ----------------------- | ------ | --------------------------------------------------------------- |
| Communication frequency | 0.30   | Emails, calls, meetings in the last 90 days                     |
| Communication recency   | 0.25   | Days since last communication (decays exponentially)            |
| Reciprocity             | 0.20   | Ratio of bidirectional communication (1.0 = perfectly balanced) |
| Duration                | 0.15   | Length of known relationship (capped at 5+ years = max)         |
| Explicit connections    | 0.10   | User-defined relationships (introductions, referrals)           |

**Decay function:** Strength decays by 10% per month of inactivity. A relationship with no communication for 6 months loses ~47% of its frequency-weighted score. This ensures active relationships surface above dormant ones.

**Recomputation:** Strength scores are recomputed by a daily Celery job that processes communication events from the last 24 hours and adjusts affected relationship edges.

### 10.3 Key Graph Queries

| Query                    | Cypher Pattern                                                                                                   | Use Case                                        |
| ------------------------ | ---------------------------------------------------------------------------------------------------------------- | ----------------------------------------------- |
| **Warm intro path**      | `shortestPath((me)-[:KNOWS*..4]-(target))`                                                                       | Find introduction chain to target contact       |
| **Strongest path**       | `allShortestPaths((me)-[:KNOWS*..3]-(target))` weighted by `strength`                                            | Best introduction chain by relationship quality |
| **Who do we know at X?** | `MATCH (c:Contact)-[:WORKS_AT {is_current: true}]->(co:Company {id: X}) RETURN c`                                | Pre-meeting research                            |
| **Org chart**            | `MATCH (c)-[:REPORTS_TO*]->(top) WHERE (c)-[:WORKS_AT]->(co {id: X}) RETURN c, top`                              | Stakeholder mapping                             |
| **Key connectors**       | `MATCH (c:Contact) WITH c, SIZE([(c)-[:KNOWS]-()                                                                 | 1]) as degree RETURN c ORDER BY degree DESC`    |
| **Mutual connections**   | `MATCH (me)-[:KNOWS]-(mutual)-[:KNOWS]-(target) RETURN mutual`                                                   | Common ground for outreach                      |
| **Career movers**        | `MATCH (c)-[:WORKS_AT {is_current: false}]->(old), (c)-[:WORKS_AT {is_current: true}]->(new) RETURN c, old, new` | Job change detection                            |

---

## 11. Behavioral Signal Tracking

### 11.1 Signal Sources

Behavioral signals are derived from communication activity, calendar events, and in-app interactions:

| Signal Source       | Signals Extracted                                                             | Update Frequency           |
| ------------------- | ----------------------------------------------------------------------------- | -------------------------- |
| **Email**           | Send/receive frequency, response time, response rate, thread depth, sentiment | On each email sync         |
| **Calendar**        | Meeting frequency, cancellation rate, meeting duration trends, no-shows       | On each calendar sync      |
| **Phone/SMS**       | Call frequency, call duration, missed calls, response patterns                | On each communication sync |
| **In-app activity** | Notes added, profile views, deal stage changes, searches for contact          | Real-time event tracking   |
| **External**        | Form fills, website visits (opt-in tracking pixel)                            | Webhook/polling            |

### 11.2 Computed Engagement Metrics

| Metric                   | Formula                                                                       | Description                                           |
| ------------------------ | ----------------------------------------------------------------------------- | ----------------------------------------------------- |
| **Engagement score**     | Weighted composite of frequency, recency, and reciprocity across all channels | Overall relationship health (0.0–1.0)                 |
| **Responsiveness index** | `avg(response_time) * response_rate`                                          | How quickly and reliably the contact responds         |
| **Sentiment trend**      | Rolling 30-day window of AI-analyzed sentiment across communications          | Positive, neutral, negative, or declining             |
| **Attention signal**     | Statistical deviation from baseline engagement                                | Alerts on sudden increases or decreases in engagement |
| **Best time to contact** | Mode of historical interaction timestamps (day-of-week + hour)                | Optimal outreach window                               |
| **Stale contact alert**  | Days since last bidirectional communication exceeds threshold                 | Relationship at risk of going dormant                 |

### 11.3 Engagement Score Computation

```
engagement_score = (
    0.30 * frequency_score +      # Normalized communication count (90-day window)
    0.25 * recency_score +         # Exponential decay from last interaction
    0.20 * reciprocity_score +     # Bidirectional balance (0 = one-sided, 1 = balanced)
    0.15 * depth_score +           # Average thread depth / call duration
    0.10 * channel_diversity       # Number of distinct channels used (max 1.0 at 3+ channels)
)
```

**Recomputation:** Daily Celery job processes the last 24 hours of communication events and recalculates engagement scores for affected contacts. Scores are persisted on `contacts.engagement_score`.

---

## 12. Groups, Tags & Segmentation

### 12.1 Contact Groups

User-defined collections of contacts. Groups are flat (no hierarchy) and serve organizational purposes: event attendee lists, advisory boards, deal teams, conference leads.

| Column        | Type    | Constraints      | Description                                                      |
| ------------- | ------- | ---------------- | ---------------------------------------------------------------- |
| `id`          | TEXT    | **PK**           | UUID v4                                                          |
| `name`        | TEXT    | NOT NULL         | Group name (unique per tenant)                                   |
| `description` | TEXT    |                  | Purpose or context for the group                                 |
| `owner_id`    | TEXT    | FK → `users(id)` | User who created the group                                       |
| `is_smart`    | INTEGER | DEFAULT 0        | Boolean. Smart groups use saved filters (see `query_def`).       |
| `query_def`   | TEXT    |                  | JSON filter definition for smart groups. NULL for manual groups. |
| `created_at`  | TEXT    | NOT NULL         | ISO 8601                                                         |
| `updated_at`  | TEXT    | NOT NULL         | ISO 8601                                                         |

**`group_members` join table:**

| Column       | Type | Constraints                                     | Description |
| ------------ | ---- | ----------------------------------------------- | ----------- |
| `group_id`   | TEXT | NOT NULL, FK → `groups(id)` ON DELETE CASCADE   |             |
| `contact_id` | TEXT | NOT NULL, FK → `contacts(id)` ON DELETE CASCADE |             |
| `added_at`   | TEXT | NOT NULL                                        | ISO 8601    |
| `added_by`   | TEXT | FK → `users(id)`                                |             |

**Constraints:** `PRIMARY KEY (group_id, contact_id)`

**Smart groups:** When `is_smart=1`, the group's membership is dynamically computed from `query_def` — a JSON-serialized filter (same format as saved views). Example:

```json
{
  "filters": [
    {"field": "company_name", "op": "eq", "value": "Acme Corp"},
    {"field": "lead_status", "op": "in", "values": ["qualified", "nurturing"]},
    {"field": "engagement_score", "op": "gte", "value": 0.5}
  ],
  "logic": "AND"
}
```

Smart group membership is recomputed on access or on a schedule (configurable).

### 12.2 Contact Tags

Lightweight labels applied to contacts for categorization and filtering.

| Column            | Type    | Constraints      | Description                                    |
| ----------------- | ------- | ---------------- | ---------------------------------------------- |
| `id`              | TEXT    | **PK**           | UUID v4                                        |
| `name`            | TEXT    | NOT NULL, UNIQUE | Tag name (e.g., "VIP", "Advisor", "Technical") |
| `color`           | TEXT    |                  | Hex color code for UI display                  |
| `is_ai_suggested` | INTEGER | DEFAULT 0        | Boolean. TRUE if the tag was suggested by AI.  |
| `created_at`      | TEXT    | NOT NULL         | ISO 8601                                       |

**`contact_tags` join table:**

| Column       | Type | Constraints                                     | Description                                            |
| ------------ | ---- | ----------------------------------------------- | ------------------------------------------------------ |
| `contact_id` | TEXT | NOT NULL, FK → `contacts(id)` ON DELETE CASCADE |                                                        |
| `tag_id`     | TEXT | NOT NULL, FK → `tags(id)` ON DELETE CASCADE     |                                                        |
| `source`     | TEXT |                                                 | `manual`, `ai_suggested`, `import`, `rule`             |
| `confidence` | REAL | DEFAULT 1.0                                     | For AI-suggested tags, how confident the suggestion is |
| `created_at` | TEXT | NOT NULL                                        | ISO 8601                                               |

**Constraints:** `PRIMARY KEY (contact_id, tag_id)`

### 12.3 AI-Suggested Tags

The AI tagging system analyzes communication content, enrichment data, and contact metadata to suggest tags:

- **Industry tags:** Based on company industry, job title keywords, and communication content.
- **Role tags:** Decision Maker, Technical, Executive, Legal, Finance — inferred from title and communication patterns.
- **Relationship tags:** VIP, Dormant, New Connection, Frequent Collaborator — based on engagement signals.
- **Custom tags:** Users can define tag suggestion rules (e.g., "Tag anyone at companies with 500+ employees as 'Enterprise'").

Suggested tags appear with a "suggested" badge. Users can accept (promoting to `source='manual'` with `confidence=1.0`) or dismiss.

---

## 13. Contact Import & Export

### 13.1 Import Formats

| Format                  | Source                                   | Capabilities                                                                                                                                                                                                                                                                                |
| ----------------------- | ---------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **CSV**                 | Any CRM, spreadsheet                     | Column mapping UI. Supports name, email, phone, company, title, tags, custom fields.                                                                                                                                                                                                        |
| **vCard 3.0/4.0**       | Apple Contacts, Outlook, Google (export) | Standard contact interchange. Multi-value fields (multiple emails/phones) supported. **Implemented** — `poc/vcard_import.py`, web UI at `/contacts/import`, CLI `import-vcards`. Three-tier duplicate detection: email match → normalized phone match → exact name match (customer-scoped). |
| **Google Contacts API** | Google account                           | OAuth-based live sync. Ongoing incremental sync supported.                                                                                                                                                                                                                                  |
| **LinkedIn CSV**        | LinkedIn export                          | Structured export with name, company, title, email, connected date.                                                                                                                                                                                                                         |

### 13.2 Import Pipeline

```
File uploaded / API sync initiated
  │
  ▼
┌──────────────────────────────────┐
│  1. Parse & Validate             │
│     - Parse file format          │
│     - Validate required fields   │
│     - Normalize values           │
│     - Report parsing errors      │
└──────────────┬───────────────────┘
               │
               ▼
┌──────────────────────────────────┐
│  2. Duplicate Detection          │
│     - Check each record against  │
│       existing contacts via      │
│       entity resolution pipeline │
│     - Classify: new, duplicate,  │
│       update                     │
└──────────────┬───────────────────┘
               │
               ▼
┌──────────────────────────────────┐
│  3. Preview & User Confirmation  │
│     - Show import preview:       │
│       N new, N updates, N dupes  │
│     - User selects handling for  │
│       each category              │
│     - User confirms import       │
└──────────────┬───────────────────┘
               │
               ▼
┌──────────────────────────────────┐
│  4. Execute Import               │
│     - Create new contacts        │
│     - Merge updates into existing│
│     - Skip or merge duplicates   │
│     - Emit events for all changes│
│     - Trigger enrichment for new │
└──────────────┬───────────────────┘
               │
               ▼
┌──────────────────────────────────┐
│  5. Import Report                │
│     - Summary: created, updated, │
│       skipped, errored           │
│     - Error details for failed   │
│       records                    │
│     - Import ID for audit trail  │
└──────────────────────────────────┘
```

### 13.3 Export Formats

| Format        | Use Case                                                          |
| ------------- | ----------------------------------------------------------------- |
| **CSV**       | General export, spreadsheet analysis, migration to another system |
| **vCard 4.0** | Import into address book applications                             |
| **JSON**      | API-based export, data portability, GDPR export                   |

**Export scoping:** Users can export all contacts, a filtered subset, a group, or a single contact's full record (including history, for GDPR compliance).

---

## 14. Search & Discovery

### 14.1 Full-Text Search (Meilisearch)

Contacts are indexed in Meilisearch for fast, typo-tolerant search across all fields.

**Indexed fields:**

| Field                | Searchable    | Filterable | Sortable |
| -------------------- | ------------- | ---------- | -------- |
| `display_name`       | Yes (primary) |            | Yes      |
| `email_primary`      | Yes           |            |          |
| `phone_primary`      | Yes           |            |          |
| `company_name`       | Yes           | Yes        | Yes      |
| `job_title`          | Yes           | Yes        |          |
| `lead_status`        |               | Yes        |          |
| `lead_source`        |               | Yes        |          |
| `engagement_score`   |               | Yes        | Yes      |
| `intelligence_score` |               | Yes        | Yes      |
| `tags`               | Yes           | Yes        |          |
| *(custom fields)*    | Yes           |            |          |
| `created_at`         |               | Yes        | Yes      |
| `updated_at`         |               |            | Yes      |

**Performance targets:** < 50ms p95 for any search query.

**Sync strategy:** Contact changes are pushed to Meilisearch asynchronously via Celery task. Maximum index lag: 5 seconds.

### 14.2 Natural Language Search

AI-powered search translates natural language queries into structured filter + search combinations:

**Example queries:**

| Natural Language                                | Translated To                                                                          |
| ----------------------------------------------- | -------------------------------------------------------------------------------------- |
| "founders at Series A companies in healthcare"  | `title CONTAINS 'founder' AND industry = 'healthcare' AND funding_stage = 'series_a'`  |
| "people I haven't emailed in 3 months"          | `last_communication < NOW() - 90 days AND has_communication = true`                    |
| "VIP contacts at companies with 500+ employees" | `tags CONTAINS 'VIP' AND company_size IN ('501-1000', '1001-5000', '5001+')`           |
| "who introduced me to Sarah Chen?"              | Graph query: `MATCH (me)-[r:INTRODUCED_BY]->(s:Contact {name: 'Sarah Chen'}) RETURN r` |

**Implementation:** Claude receives the query, contact schema, and available filter fields. It returns a structured filter JSON that is executed against Meilisearch and/or Neo4j.

---

## 15. AI-Powered Contact Intelligence

### 15.1 Contact Briefing

On-demand AI-generated summary synthesizing all available data about a contact.

**Input context (sent to Claude):**

- Contact profile (name, title, company, social profiles)
- Employment history
- Recent communication summary (last 10 conversations, summarized)
- Relationship context (key connections, mutual contacts)
- Intelligence items (last 5 intel items)
- Engagement metrics (score, trend, responsiveness)

**Output:**

```
Sarah Chen is VP of Engineering at Acme Corp, where she's been since March 2024.
Previously she was Senior Director of Platform Engineering at Globex Inc for 3 years.
You've exchanged 47 emails over the last 6 months — your relationship is active and
strengthening (engagement score: 0.78, up from 0.65 three months ago). She introduced
you to Marcus Rodriguez at TechVentures in January. Your last communication was 3 days
ago about the API integration project. She has 2 open action items pending. Acme Corp
recently closed a $15M Series B, which may affect her engineering team's priorities.
```

**Caching:** Briefings are cached with a 24-hour TTL. Cache is invalidated on new communication events or intelligence items for the contact.

### 15.2 AI-Suggested Actions

Based on contact analysis, the AI suggests proactive actions:

| Trigger                           | Suggested Action                                                                 |
| --------------------------------- | -------------------------------------------------------------------------------- |
| Engagement declining for 30+ days | "You haven't heard from Sarah in 5 weeks. Consider reaching out."                |
| Job change detected               | "Sarah just moved to Globex Inc. Send a congratulations note."                   |
| Upcoming meeting with contact     | "You have a meeting with Sarah tomorrow. Here's a briefing."                     |
| Open action items aging           | "You have 2 open action items with Sarah from 2 weeks ago."                      |
| Warm intro opportunity            | "Sarah knows Marcus Rodriguez at TechVentures — they worked together at Globex." |
| Stale enrichment data             | "Sarah's profile hasn't been updated in 6 months. Re-enrich?"                    |

### 15.3 AI Tag Suggestions

The system analyzes contacts and suggests tags based on patterns:

- Communication content analysis (topics discussed, terminology used)
- Title and role pattern matching
- Company industry and size
- Engagement patterns
- Similarity to other contacts with specific tags

---

## 16. Event Sourcing & Temporal History

### 16.1 Event Store Design

All contact and company mutations are stored as immutable events in append-only, per-entity-type event tables. The read model tables (`contacts`, `companies`) are projections derived from these events. Per Custom Objects PRD Section 19, each entity type has its own event table within the tenant schema (e.g., `tenant_abc.contacts_events`, `tenant_abc.companies_events`).

**Event table structure** (per entity type — e.g., `contacts_events`, `companies_events`):

| Column            | Type        | Constraints      | Description                                           |
| ----------------- | ----------- | ---------------- | ----------------------------------------------------- |
| `id`              | TEXT        | **PK**           | UUID v4                                               |
| `entity_id`       | TEXT        | NOT NULL         | The entity this event belongs to                      |
| `event_type`      | TEXT        | NOT NULL         | Event type (see catalog below)                        |
| `payload`         | JSONB       | NOT NULL         | Event data                                            |
| `actor_id`        | TEXT        | FK → `users(id)` | User who triggered the event (NULL for system events) |
| `timestamp`       | TIMESTAMPTZ | NOT NULL         |                                                       |
| `sequence_number` | INTEGER     | NOT NULL         | Monotonically increasing per entity, for ordering     |

**Constraints:**

- `UNIQUE(entity_id, sequence_number)` — guarantees event ordering per entity.
- Index on `(entity_id, timestamp)` for temporal queries.

### 16.2 Event Catalog

| Event Type                | Payload Fields                                      | Description                       |
| ------------------------- | --------------------------------------------------- | --------------------------------- |
| `ContactCreated`          | `first_name`, `last_name`, `source`, `status`       | New contact created               |
| `ContactUpdated`          | `field`, `old_value`, `new_value`                   | Single field changed              |
| `ContactArchived`         | `reason`                                            | Contact archived                  |
| `ContactUnarchived`       |                                                     | Contact restored from archive     |
| `ContactsMerged`          | `survivor_id`, `duplicate_id`, `match_signals`      | Two contacts merged               |
| `ContactsSplit`           | `original_id`, `new_id`, `identifiers_moved`        | Merge undone                      |
| `ContactDeleted`          | `reason`, `requested_by`                            | GDPR hard delete                  |
| `IdentifierAdded`         | `type`, `value`, `source`, `confidence`             | New identifier linked             |
| `IdentifierRemoved`       | `type`, `value`, `reason`                           | Identifier unlinked               |
| `IdentifierStatusChanged` | `type`, `value`, `old_status`, `new_status`         | Active → inactive, etc.           |
| `EmploymentStarted`       | `company_id`, `company_name`, `title`, `department` | New position                      |
| `EmploymentEnded`         | `company_id`, `ended_at`, `reason`                  | Position ended                    |
| `EmploymentUpdated`       | `company_id`, `field`, `old_value`, `new_value`     | Title/dept change at same company |
| `EnrichmentCompleted`     | `source`, `fields_updated`, `confidence`            | Enrichment data merged            |
| `IntelItemCreated`        | `category`, `title`, `source`                       | New intelligence item             |
| `TagAdded`                | `tag_id`, `tag_name`, `source`                      | Tag applied                       |
| `TagRemoved`              | `tag_id`, `tag_name`                                | Tag removed                       |
| `RelationshipCreated`     | `target_id`, `type`, `properties`                   | Graph edge created                |
| `RelationshipUpdated`     | `target_id`, `type`, `old_props`, `new_props`       | Graph edge modified               |
| `RelationshipRemoved`     | `target_id`, `type`                                 | Graph edge deleted                |
| `NoteAdded`               | `note_id`, `preview`                                | Note linked to contact            |
| `GroupMemberAdded`        | `group_id`, `group_name`                            | Added to group                    |
| `GroupMemberRemoved`      | `group_id`, `group_name`                            | Removed from group                |
| `CompanyCreated`          | `name`, `domain`, `source`                          | New company created               |
| `CompanyUpdated`          | `field`, `old_value`, `new_value`                   | Company field changed             |

### 16.3 Event Snapshots

To avoid replaying long event chains for temporal queries, periodic snapshots capture the full state of an entity. Each entity type’s event table has a corresponding snapshot table (e.g., `contacts_event_snapshots`, `companies_event_snapshots`):

| Column           | Type        | Constraints | Description                                                       |
| ---------------- | ----------- | ----------- | ----------------------------------------------------------------- |
| `id`             | TEXT        | **PK**      | UUID v4                                                           |
| `entity_id`      | TEXT        | NOT NULL    |                                                                   |
| `state`          | JSONB       | NOT NULL    | Full state of the entity at snapshot time                         |
| `snapshot_at`    | TIMESTAMPTZ | NOT NULL    |                                                                   |
| `event_sequence` | INTEGER     | NOT NULL    | The sequence_number of the latest event included in this snapshot |

**Snapshot strategy:** A snapshot is created when an entity accumulates 50+ events since the last snapshot, or daily for entities with 10+ events. Snapshots are created by a Celery background job.

### 16.4 Point-in-Time Queries

To reconstruct a contact's state at a historical date:

```
1. Find the latest snapshot BEFORE the target date.
2. Load the snapshot state.
3. Replay events AFTER the snapshot up to the target date.
4. Return the reconstructed state.
```

```sql
-- Find latest snapshot before target date
SELECT state, event_sequence
FROM contacts_event_snapshots
WHERE entity_id = :contact_id
  AND snapshot_at <= :target_date
ORDER BY snapshot_at DESC LIMIT 1;

-- Replay events after snapshot up to target date
SELECT event_type, payload
FROM contacts_events
WHERE entity_id = :contact_id
  AND sequence_number > :snapshot_sequence
  AND timestamp <= :target_date
ORDER BY sequence_number ASC;
```

**Performance target:** < 500ms p95 for any point-in-time query, assuming snapshots exist within 50 events.

---

## 17. API Design

### 17.1 Contact Endpoints

```
# Contact CRUD
GET    /api/v1/contacts                          # List contacts (paginated, filtered, sorted)
POST   /api/v1/contacts                          # Create contact
GET    /api/v1/contacts/{id}                      # Get contact detail (materialized view)
PATCH  /api/v1/contacts/{id}                      # Update contact fields
DELETE /api/v1/contacts/{id}                      # Soft-delete (archive)

# Contact Intelligence
GET    /api/v1/contacts/{id}/timeline             # Unified activity timeline
GET    /api/v1/contacts/{id}/history?at={iso8601} # Point-in-time reconstruction
GET    /api/v1/contacts/{id}/relationships        # Graph relationships
GET    /api/v1/contacts/{id}/intelligence         # Intelligence items
GET    /api/v1/contacts/{id}/employment-history   # Employment timeline
GET    /api/v1/contacts/{id}/conversations        # Linked conversations
GET    /api/v1/contacts/{id}/deals                # Linked deals
POST   /api/v1/contacts/{id}/enrich               # Trigger enrichment
GET    /api/v1/contacts/{id}/briefing             # AI-generated briefing
POST   /api/v1/contacts/{id}/notes                # Add note
GET    /api/v1/contacts/{id}/events               # Raw event stream (admin/debug)

# Contact Identifiers
GET    /api/v1/contacts/{id}/identifiers          # List all identifiers
POST   /api/v1/contacts/{id}/identifiers          # Add identifier
PATCH  /api/v1/contacts/{id}/identifiers/{iid}    # Update identifier
DELETE /api/v1/contacts/{id}/identifiers/{iid}    # Remove identifier

# Entity Resolution
GET    /api/v1/resolution/review-queue            # Pending merge candidates
POST   /api/v1/resolution/merge                   # Execute merge
POST   /api/v1/resolution/split                   # Undo merge
PATCH  /api/v1/resolution/thresholds              # Configure confidence thresholds

# Companies
GET    /api/v1/companies                          # List companies
POST   /api/v1/companies                          # Create company
GET    /api/v1/companies/{id}                      # Get company detail
PATCH  /api/v1/companies/{id}                      # Update company
GET    /api/v1/companies/{id}/contacts             # Contacts at this company
GET    /api/v1/companies/{id}/intel                # Company intelligence
GET    /api/v1/companies/{id}/history?at={iso8601} # Point-in-time

# Groups
GET    /api/v1/groups                              # List groups
POST   /api/v1/groups                              # Create group
GET    /api/v1/groups/{id}                          # Get group detail
PATCH  /api/v1/groups/{id}                          # Update group
DELETE /api/v1/groups/{id}                          # Delete group
POST   /api/v1/groups/{id}/members                  # Add contacts to group
DELETE /api/v1/groups/{id}/members/{contact_id}      # Remove contact from group

# Tags
GET    /api/v1/tags                                # List tags
POST   /api/v1/tags                                # Create tag
PATCH  /api/v1/tags/{id}                            # Update tag
DELETE /api/v1/tags/{id}                            # Delete tag

# Graph Queries
GET    /api/v1/graph/network/{contact_id}          # Network visualization data
GET    /api/v1/graph/path/{from_id}/{to_id}        # Warm intro path
POST   /api/v1/graph/relationships                  # Create relationship
PATCH  /api/v1/graph/relationships/{id}             # Update relationship
DELETE /api/v1/graph/relationships/{id}             # Delete relationship
GET    /api/v1/graph/influencers                    # Top connectors
GET    /api/v1/graph/clusters                       # Network clusters
GET    /api/v1/graph/org-chart/{company_id}         # Company org chart

# Import / Export
POST   /api/v1/contacts/import                      # Upload CSV/vCard
GET    /api/v1/contacts/import/{job_id}             # Import job status
POST   /api/v1/contacts/export                      # Trigger export
GET    /api/v1/contacts/export/{job_id}             # Download export file

# Search
GET    /api/v1/contacts/search?q={query}            # Full-text search
POST   /api/v1/contacts/search/natural              # Natural language search
```

### 17.2 List Endpoint Filtering

The `GET /api/v1/contacts` endpoint supports rich filtering via query parameters:

| Parameter                   | Type     | Example                                       | Description                                |
| --------------------------- | -------- | --------------------------------------------- | ------------------------------------------ |
| `q`                         | string   | `q=sarah`                                     | Full-text search across all indexed fields |
| `company`                   | string   | `company=Acme Corp`                           | Filter by company name (exact or partial)  |
| `company_id`                | UUID     |                                               | Filter by company ID                       |
| `tag`                       | string[] | `tag=VIP&tag=Advisor`                         | Filter by tags (AND logic)                 |
| `lead_status`               | string[] | `lead_status=qualified&lead_status=nurturing` | Filter by lead status                      |
| `lead_source`               | string   |                                               | Filter by lead source                      |
| `status`                    | string   | `status=active`                               | Filter by contact status                   |
| `engagement_score_min`      | float    | `engagement_score_min=0.5`                    | Minimum engagement score                   |
| `engagement_score_max`      | float    |                                               | Maximum engagement score                   |
| `last_communication_before` | ISO 8601 |                                               | Contacts not communicated with since       |
| `last_communication_after`  | ISO 8601 |                                               | Contacts communicated with since           |
| `created_after`             | ISO 8601 |                                               | Created after date                         |
| `created_before`            | ISO 8601 |                                               | Created before date                        |
| `group_id`                  | UUID     |                                               | Filter by group membership                 |
| `sort`                      | string   | `sort=-engagement_score`                      | Sort field (prefix `-` for descending)     |
| `page[cursor]`              | string   |                                               | Cursor-based pagination                    |
| `page[size]`                | integer  | `page[size]=50`                               | Page size (default 25, max 100)            |

### 17.3 Response Format

All responses follow JSON:API specification:

```json
{
  "data": {
    "type": "contacts",
    "id": "con_01HX7VFBK3NP9QZCH1Y4MWDB2R",
    "attributes": {
      "display_name": "Sarah Chen",
      "first_name": "Sarah",
      "last_name": "Chen",
      "email_primary": "sarah@acmecorp.com",
      "phone_primary": "+15550199",
      "job_title": "VP of Engineering",
      "company_name": "Acme Corp",
      "lead_status": "customer",
      "engagement_score": 0.78,
      "intelligence_score": 0.85,
      "status": "active",
      "created_at": "2025-06-15T10:30:00Z",
      "updated_at": "2026-02-07T14:22:00Z"
    },
    "relationships": {
      "company": { "data": { "type": "companies", "id": "..." } },
      "identifiers": { "data": [{ "type": "contact_identifiers", "id": "..." }] },
      "tags": { "data": [{ "type": "tags", "id": "..." }] },
      "groups": { "data": [{ "type": "groups", "id": "..." }] }
    }
  },
  "included": [ ... ]
}
```

---

## 18. Client-Side Offline Support

### 18.1 Offline Data Model

The Flutter client maintains a local SQLite/Isar database with a subset of contact data for offline access:

**Synced to client:**

- `contacts` — Full contact records for the user's accessible contacts.
- `contact_identifiers` — For local search and communication participant resolution.
- `contacts__companies_employment` — For contact detail display.
- `companies` — Company records referenced by contacts.
- `tags` and `contact_tags` — For filtering.
- `groups` and `group_members` — For group membership display.

**Not synced to client (server-only):**

- Event store — Too large, not needed for display.
- Intelligence items — Fetched on demand via API.
- Graph relationships — Queried live from Neo4j via API.
- Match candidates — Admin/review workflow is server-side only.

### 18.2 Sync Strategy

- **Incremental sync:** Server tracks `synced_at` per entity. Client requests changes since its last sync timestamp. Delta compression for large contact databases.
- **Sync interval:** Configurable, default 30 seconds when online.
- **Conflict resolution:** Server wins. Client write queue replays sequentially on reconnect. Conflicts are surfaced to the user for manual resolution.
- **Initial sync:** Full materialized view download on first connection. For tenants with > 5,000 contacts, paginated with background sync.

### 18.3 Offline Write Queue

When offline, the client queues write operations locally:

- Create contact
- Update contact fields
- Add/remove tags
- Add/remove group members
- Add notes

Queued writes are displayed with a "pending" indicator. On reconnect, the queue replays sequentially against the API.

---

## 19. Privacy, Security & Compliance

### 19.1 Data Protection

| Requirement               | Implementation                                                                                     |
| ------------------------- | -------------------------------------------------------------------------------------------------- |
| **Encryption at rest**    | AES-256 for database storage. S3 server-side encryption for objects.                               |
| **Encryption in transit** | TLS 1.3 for all API communication.                                                                 |
| **PII handling**          | Contact PII (name, email, phone) encrypted at database level. Meilisearch index encrypted at rest. |
| **Access control**        | RBAC (Owner, Admin, Member, Viewer). Contact visibility follows tenant membership.                 |
| **Audit trail**           | Event sourcing provides complete audit trail for all contact mutations.                            |
| **Data minimization**     | Only collect data relevant to CRM purposes. Enrichment respects data collection boundaries.        |

### 19.2 GDPR Compliance

| GDPR Right                    | Implementation                                                                                                             |
| ----------------------------- | -------------------------------------------------------------------------------------------------------------------------- |
| **Right of access**           | Export endpoint provides full contact record including all events, identifiers, communications, and intelligence.          |
| **Right to rectification**    | Standard edit flow with event-sourced audit trail.                                                                         |
| **Right to erasure**          | Hard delete workflow (Section 8.3) with full data removal and audit record.                                                |
| **Right to data portability** | JSON and CSV export in machine-readable format.                                                                            |
| **Right to object**           | Contact status can be set to `archived` to exclude from processing. Enrichment and monitoring can be disabled per contact. |
| **Consent tracking**          | Source attribution on all data points. Enrichment sources record consent basis.                                            |

### 19.3 CCPA Compliance

| CCPA Requirement       | Implementation                                                        |
| ---------------------- | --------------------------------------------------------------------- |
| **Right to know**      | Same as GDPR right of access — full data export.                      |
| **Right to delete**    | Same as GDPR right to erasure — hard delete workflow.                 |
| **Right to opt out**   | Per-contact enrichment and monitoring opt-out flag.                   |
| **Non-discrimination** | Contact features available regardless of privacy preference exercise. |

### 19.4 OSINT & Enrichment Ethics

- All enrichment sources use publicly available data only.
- Rate limiting respects platform Terms of Service.
- Browser extension only captures data from pages the user actively visits.
- Enrichment can be disabled per tenant or per contact.
- Each enriched data point carries source attribution for transparency.
- No web scraping of private content or login-walled pages.

---

## 20. Phasing & Roadmap

### Phase 1 — Foundation (MVP)

**Goal:** Core contact management with event sourcing, basic intelligence, and offline clients.

| Feature                  | Priority | Description                                                                                                    |
| ------------------------ | -------- | -------------------------------------------------------------------------------------------------------------- |
| Contact CRUD             | P0       | Create, read, update, archive contacts via API and UI                                                          |
| Company CRUD             | P0       | Create, read, update companies with domain matching                                                            |
| Multi-identifier model   | P0       | `contact_identifiers` table with type, value, lifecycle                                                        |
| Event store              | P0       | Immutable event log for contacts and companies                                                                 |
| Read model tables        | P0       | `contacts` and `companies` tables (object type read models)                                                    |
| Contact detail tables    | P0       | Emails, phones, addresses, social profiles, key dates                                                          |
| Employment history       | P0       | Temporal employment records with company linking                                                               |
| Contact list view        | P0       | Paginated, sorted, filtered contact list                                                                       |
| Contact detail page      | P0       | Unified detail view with profile, timeline, history (rendered via Card-Based Architecture, GUI PRD Section 15) |
| Full-text search         | P0       | Meilisearch indexing and search                                                                                |
| CSV import               | P0       | File upload, column mapping, dedup, preview, execute                                                           |
| vCard import             | P1       | Parse vCard 3.0/4.0, same pipeline as CSV                                                                      |
| Google Contacts sync     | P0       | OAuth-based import from Google People API                                                                      |
| Tags                     | P1       | Tag CRUD, contact-tag assignment, filter by tag                                                                |
| Groups                   | P1       | Manual groups, membership management                                                                           |
| Notes                    | P1       | Add/edit notes on contacts                                                                                     |
| Export (CSV, vCard)      | P1       | Contact export with field selection                                                                            |
| Offline read cache       | P1       | Client-side SQLite with incremental sync                                                                       |
| Offline write queue      | P1       | Queued writes with replay on reconnect                                                                         |
| Point-in-time queries    | P2       | Event replay for historical state reconstruction                                                               |
| Event snapshots          | P2       | Periodic snapshots for query performance                                                                       |
| AI contact summarization | P1       | Claude-powered contact briefings                                                                               |
| Natural language search  | P2       | AI-translated search queries                                                                                   |

### Phase 2 — Intelligence Engine

**Goal:** Full intelligence capabilities that differentiate from standard CRMs.

| Feature                        | Priority | Description                                                                                                                                                                                                                                                            |
| ------------------------------ | -------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Enrichment engine              | P0       | **Implemented.** Pluggable provider framework (`poc/enrichment_provider.py`, `poc/enrichment_pipeline.py`). Website scraper provider extracts name, description, social profiles, phones, emails from company websites. Batch enrichment via `enrich_new_companies()`. |
| Apollo adapter                 | P0       | First enrichment integration                                                                                                                                                                                                                                           |
| Clearbit adapter               | P1       | Second enrichment integration                                                                                                                                                                                                                                          |
| People Data Labs adapter       | P2       | Third enrichment integration                                                                                                                                                                                                                                           |
| Auto-enrichment on creation    | P0       | **Partially implemented.** Batch website enrichment runs after each sync, enriching companies with domains but no completed enrichment run. Company names are auto-populated from website metadata (JSON-LD, og:site_name).                                            |
| Intelligence score             | P0       | Computed score based on data completeness                                                                                                                                                                                                                              |
| Entity resolution pipeline     | P0       | Tiered matching, confidence scoring, pipeline                                                                                                                                                                                                                          |
| Auto-merge (high confidence)   | P0       | Automatic merge for exact identifier matches                                                                                                                                                                                                                           |
| Auto-merge (medium confidence) | P0       | Merge with review flag                                                                                                                                                                                                                                                 |
| Human review queue             | P0       | UI for reviewing merge candidates                                                                                                                                                                                                                                      |
| Manual merge                   | P1       | **Implemented.** User-initiated merge with conflict resolution (`poc/contact_merge.py`). Multi-contact merge, audit trail, post-merge domain resolution.                                                                                                               |
| Split (undo merge)             | P1       | Reverse a bad merge from event history                                                                                                                                                                                                                                 |
| Configurable thresholds        | P2       | Tenant-level merge confidence settings                                                                                                                                                                                                                                 |
| Browser extension (LinkedIn)   | P1       | Chrome/Firefox extension for LinkedIn capture                                                                                                                                                                                                                          |
| Browser extension (Twitter)    | P2       | Twitter/X profile capture                                                                                                                                                                                                                                              |
| OSINT monitoring               | P1       | Configurable monitors for contact changes                                                                                                                                                                                                                              |
| Intelligence items             | P0       | Intel item storage and display                                                                                                                                                                                                                                         |
| Behavioral signal tracking     | P1       | Engagement scoring, responsiveness, sentiment                                                                                                                                                                                                                          |
| Smart groups                   | P2       | Dynamic group membership from saved filters                                                                                                                                                                                                                            |
| AI tag suggestions             | P2       | Claude-powered tag recommendations                                                                                                                                                                                                                                     |

### Phase 3 — Relationship Intelligence

**Goal:** Graph-powered relationship modeling and analysis.

| Feature                       | Priority | Description                              |
| ----------------------------- | -------- | ---------------------------------------- |
| Neo4j integration             | P0       | Graph database setup, node/edge sync     |
| Relationship CRUD             | P0       | Create, edit, delete typed relationships |
| Relationship visualization    | P0       | Interactive network graph UI             |
| Relationship strength scoring | P1       | Computed strength with decay             |
| Warm introduction paths       | P0       | Shortest/strongest path finding          |
| Org chart reconstruction      | P1       | Company org chart from graph edges       |
| Influence mapping             | P1       | Key connector identification             |
| Network clustering            | P2       | Automatic community detection            |
| Deal stakeholder roles        | P1       | Decision Maker, Influencer, Champion     |
| Meeting prep briefs           | P1       | Pre-meeting briefing generation          |
| AI relationship suggestions   | P2       | "You should connect X and Y"             |
| AI action suggestions         | P2       | Proactive outreach recommendations       |
| Stale contact alerts          | P1       | Notifications for declining engagement   |

### Phase 4 — Scale & Ecosystem

**Goal:** Platform maturity and extensibility.

| Feature                   | Priority | Description                                                                                                                                                                                                                                                                       |
| ------------------------- | -------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Bulk operations           | P0       | Bulk tag, group, archive, export                                                                                                                                                                                                                                                  |
| Workflow automation       | P1       | Trigger-action rules for contacts                                                                                                                                                                                                                                                 |
| Webhook events            | P0       | Contact created, updated, merged webhooks                                                                                                                                                                                                                                         |
| Zapier / Make integration | P1       | Pre-built triggers and actions                                                                                                                                                                                                                                                    |
| Advanced reporting        | P1       | Contact analytics, enrichment coverage, engagement trends                                                                                                                                                                                                                         |
| GDPR tooling              | P0       | Data export, hard delete, consent management UI                                                                                                                                                                                                                                   |
| ~~Custom field builder~~  | ~~P0~~   | ~~Tenant-configurable typed fields~~ **Resolved:** Custom fields managed through unified field registry (Custom Objects PRD Section 8). Standard field management UI for any object type. No separate builder needed — it's the standard field management UI for any object type. |
| LinkedIn CSV import       | P1       | Structured import from LinkedIn export                                                                                                                                                                                                                                            |
| API rate limiting         | P0       | Per-tenant and per-user rate limits                                                                                                                                                                                                                                               |
| Email signature parsing   | P2       | Extract contact details from email signatures                                                                                                                                                                                                                                     |

---

## 21. Integration Points

### 21.1 Internal Subsystem Dependencies

| Subsystem                                     | Direction     | Integration                                                                                 |
| --------------------------------------------- | ------------- | ------------------------------------------------------------------------------------------- |
| **Communication & Conversation Intelligence** | Bidirectional | Conversations resolve participants to contacts. Contact detail pages link to conversations. |
| **Pipeline & Deals**                          | Bidirectional | Deals link to contacts as stakeholders. Contact timeline shows deal activity.               |
| **Event Store**                               | Write         | All contact/company mutations emit events.                                                  |
| **Search (Meilisearch)**                      | Write         | Contact changes pushed to search index.                                                     |
| **Graph (Neo4j)**                             | Bidirectional | Contact nodes and relationship edges. Graph queries for intelligence features.              |
| **AI Service (Claude)**                       | Read          | Briefings, tag suggestions, NL search, action recommendations.                              |
| **Sync Service**                              | Write         | Email sync creates/resolves contacts. Google Contacts sync updates contacts.                |
| **Notification Service**                      | Write         | OSINT alerts, stale contact alerts, engagement signals.                                     |

### 21.2 External Integrations

| Integration                 | Protocol             | Data Flow                            | Phase   |
| --------------------------- | -------------------- | ------------------------------------ | ------- |
| **Google People API**       | OAuth 2.0 + REST     | Bidirectional sync                   | Phase 1 |
| **Apollo**                  | REST API             | Enrichment → contact updates         | Phase 2 |
| **Clearbit**                | REST API             | Enrichment → contact updates         | Phase 2 |
| **People Data Labs**        | REST API             | Enrichment → contact updates         | Phase 2 |
| **LinkedIn (browser ext.)** | Extension → API      | Profile capture → contacts           | Phase 2 |
| **Twitter (browser ext.)**  | Extension → API      | Profile capture → contacts           | Phase 2 |
| **Slack**                   | OAuth 2.0 + Webhooks | Contact lookup slash command, alerts | Phase 4 |
| **Zapier / Make**           | Webhooks + REST      | Trigger/action automation            | Phase 4 |

---

## 22. Dependencies & Risks

### Dependencies

| Dependency                   | Impact                                                     | Mitigation                                                                                                                                     |
| ---------------------------- | ---------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| **PostgreSQL 16+**           | Required for event store, read model tables, typed columns | Well-established technology. Schema-per-tenant architecture (Custom Objects PRD Section 24). DDL-at-runtime for custom fields via ALTER TABLE. |
| **Neo4j**                    | Required for relationship queries and graph visualization  | Can defer graph features to Phase 3 while building contact CRUD in Phase 1.                                                                    |
| **Meilisearch**              | Required for full-text search                              | PostgreSQL `tsvector` provides basic search fallback.                                                                                          |
| **Celery + Redis**           | Required for background enrichment and score computation   | Critical path for enrichment. Can degrade to synchronous enrichment for MVP.                                                                   |
| **Enrichment API providers** | Required for auto-enrichment features                      | Multi-adapter design ensures no single-vendor dependency.                                                                                      |
| **Claude API**               | Required for briefings, NL search, tag suggestions         | Briefings cached. NL search degrades to structured search.                                                                                     |
| **Google People API**        | Required for Google Contacts sync                          | Free tier sufficient for initial scale.                                                                                                        |

### Risks

| Risk                               | Likelihood | Impact | Mitigation                                                                                                                       |
| ---------------------------------- | ---------- | ------ | -------------------------------------------------------------------------------------------------------------------------------- |
| **Enrichment API cost**            | Medium     | High   | Rate limiting, caching, cost-based adapter prioritization. Free sources first (Google, email signature), paid sources on demand. |
| **Entity resolution false merges** | Medium     | High   | Conservative default thresholds. Review queue for medium-confidence matches. Split (undo merge) capability.                      |
| **Event store growth**             | Low        | Medium | Snapshot strategy bounds replay depth. Retention policy compacts old events. PostgreSQL partitioning by timestamp.               |
| **OSINT legal compliance**         | Medium     | High   | Legal review per jurisdiction. Opt-in only for monitoring. Public data only. Terms of Service compliance.                        |
| **LinkedIn ToS**                   | High       | Medium | Browser extension captures only pages the user actively visits. No automated scraping. Clear user disclosure.                    |
| **Meilisearch index lag**          | Low        | Low    | Async indexing with max 5-second lag. Fallback to PostgreSQL search if Meilisearch unavailable.                                  |
| **Graph query performance**        | Medium     | Medium | Neo4j indexes on frequently traversed properties. Query depth limits. Caching for common patterns.                               |

---

## 23. Open Questions

1. **Contact ownership model** — Should contacts be owned by individual users, shared across the team, or both (personal vs. shared pools)? Impacts visibility, editing rights, and dedup scope.

2. ~~**Custom field limits**~~ **Resolved:** 200 user-defined fields per entity type (Custom Objects PRD Section 8.4). Universal fields and archived fields don't count against the limit. PostgreSQL performs well at 200 columns per table for target record volumes.

3. **Enrichment budget management** — Should enrichment API usage have per-tenant monthly budgets? Per-contact caps? How to prioritize enrichment when budget is constrained?

4. **Graph relationship creation** — How much relationship creation should be automated (inferred from communication patterns) vs. manual? Automated inference risks false relationships.

5. **Contact photo storage** — Store photos in object storage or link to external URLs (Gravatar, LinkedIn)? External URLs break if source changes; local storage costs more.

6. **Multi-tenant contact sharing** — For users who belong to multiple tenants, should contacts be shareable across tenants? Impacts data isolation model.

7. **Contact scoring customization** — Should tenants be able to customize engagement and intelligence score weights? Adds complexity but increases relevance per use case.

8. **LinkedIn API partnership** — LinkedIn's API is restricted. Evaluate Voyager API access, LinkedIn Sales Navigator integration, or browser extension only.

9. **Email signature parsing accuracy** — Email signatures contain valuable contact data (name, title, phone, address) but parsing is error-prone. Evaluate ML-based signature parsing vs. regex vs. third-party service.

10. **Historical enrichment** — When enrichment data arrives, should it retroactively update intelligence items and scores for historical periods, or only apply going forward?

---

## 24. Glossary

General UI terms (Entity Bar, Detail Panel, Card-Based Architecture, Attribute Card, etc.) are defined in the **[Master Glossary V3](glossary_V3.md)**. The following terms are specific to Contact Management:

| Term                               | Definition                                                                                                                                                                                                |
| ---------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Contact**                        | A person record in the CRM, uniquely identified by a prefixed ULID (`con_` prefix), with one or more identifiers. Contact is a system object type in the unified framework.                               |
| **Company**                        | An organization record, typically associated with contacts via employment history                                                                                                                         |
| **Identifier**                     | A piece of information that identifies a contact: email address, phone number, social profile URL                                                                                                         |
| **Entity resolution**              | The process of determining when records from different sources refer to the same real-world person or company                                                                                             |
| **Read model** (Materialized view) | A precomputed table derived from event replay, used for fast read access. In the unified model, this is the entity type's dedicated table (e.g., `contacts` table), managed by the object type framework. |
| **Event sourcing**                 | Data architecture where state changes are stored as immutable events rather than mutable rows                                                                                                             |
| **Enrichment**                     | The process of augmenting a contact record with data from external sources                                                                                                                                |
| **Intelligence item**              | A discrete piece of intelligence about a contact or company (job change, funding round, news mention)                                                                                                     |
| **Intelligence score**             | Composite metric (0.0–1.0) reflecting how much the system knows about a contact                                                                                                                           |
| **Engagement score**               | Composite metric (0.0–1.0) reflecting the health and recency of the relationship                                                                                                                          |
| **Warm intro path**                | A chain of mutual connections between the user and a target contact                                                                                                                                       |
| **OSINT**                          | Open-Source Intelligence — publicly available data about people and companies                                                                                                                             |
| **DSAR**                           | Data Subject Access Request — a GDPR right for individuals to request their data                                                                                                                          |
| **E.164**                          | International phone number format: `+{country code}{number}` (e.g., `+15550199`)                                                                                                                          |
| **Survivor**                       | In a merge operation, the contact record that persists and absorbs the duplicate's data                                                                                                                   |
| **Smart group**                    | A contact group whose membership is dynamically computed from a saved filter definition                                                                                                                   |
| **Behavioral signal**              | A data point derived from communication patterns (frequency, recency, sentiment)                                                                                                                          |
| **Stale contact**                  | A contact whose engagement score has fallen below a threshold due to inactivity                                                                                                                           |

---

## Related PRDs

| Document                                                                    | Relationship                                                                                                                                                                                                                                   |
| --------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [CRMExtender PRD v1.1](PRD.md)                                              | Parent document defining system architecture, phasing, and all feature areas                                                                                                                                                                   |
| [Custom Objects PRD](custom-objects-prd_v2.md)                              | Defines the unified object model, field registry, and relation framework that Contact and Company are system instances of. Governs storage architecture, DDL management, event sourcing patterns, and the Employment Relation Type definition. |
| [Communication & Conversation Intelligence PRD](email-conversations-prd.md) | Sibling subsystem that resolves communication participants to contacts                                                                                                                                                                         |
| [Data Sources PRD](data-sources-prd_V1.md)                                  | Query abstraction layer. Contact and Company virtual schema derived from object type field registries. Prefixed entity ID convention.                                                                                                          |
| [Views & Grid PRD](views-grid-prd_V5.md)                                    | Renders Contact and Company data through entity-agnostic views using field type registry.                                                                                                                                                      |
| [Data Layer Architecture PRD](data-layer-prd.md)                            | Defines the database schema for contacts and identifiers used by the conversations subsystem                                                                                                                                                   |
| [Company Management & Intelligence PRD](company-management-prd_V1.md)       | Authoritative source for Company entity type: data model, domain resolution, enrichment, hierarchy, merging, scoring. Contact PRD Section 6 cross-references this document.                                                                    |
