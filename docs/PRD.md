# Product Requirements Document: CRMExtender

## Customer Intelligence Management System

**Version:** 1.1
**Date:** 2026-02-03
**Status:** Draft

---

## 1. Executive Summary

CRMExtender is a Customer Intelligence Management (CIM) system that extends traditional CRM capabilities with deep intelligence tracking about contacts. It combines contact and deal management with relationship mapping, behavioral signal analysis, and open-source intelligence (OSINT) enrichment — all powered by AI at the core.

The system is built API-first with a multi-tenant backend, serving three client applications — web, mobile, and desktop — from a single Flutter codebase. All clients support offline read access with queued offline writes, ensuring high-performance operation regardless of network conditions.

Key architectural differentiators:

- **Hybrid event sourcing** for contacts and intelligence entities, enabling full audit trails and point-in-time reconstruction
- **Graph-based relationship modeling** capturing hierarchical, professional, social, and business connections
- **Multi-channel intelligence gathering** from enrichment APIs, browser extension, and manual entry
- **Probabilistic entity resolution** for accurate cross-source record matching
- **True cross-platform deployment** from a single Flutter/Dart codebase

---

## 2. Problem Statement

Existing CRM tools treat contacts as static records — a name, company, and a trail of logged activities. Professionals who depend on relationships (consultants, networkers, sales teams) need to understand the *dynamics* between people: who influences whom, how relationships evolve over time, what public signals indicate about a contact's priorities, and what the optimal moment is to reach out.

Current solutions force users to manually piece this together across LinkedIn, email, news alerts, and memory. CRMExtender closes that gap by making intelligence a first-class data type alongside contacts, companies, and deals.

---

## 3. Target Users

| Persona | Description | Key Needs |
|---|---|---|
| **Networker / Consultant** | Independent professionals managing referral networks and advisory relationships | Relationship strength tracking, warm intro paths, meeting prep briefs |
| **Sales Professional** | Account executives and SDRs managing pipelines | Deal intelligence, stakeholder mapping, engagement scoring, timing signals |
| **General Business User** | Anyone managing professional contacts beyond a simple address book | Organized contacts, interaction history, company intelligence |

**Initial scale:** Small teams of 2-10 users with shared contact pools and collaborative intelligence.

---

## 4. System Architecture

### 4.1 High-Level Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                      Client Layer                             │
│  ┌──────────┐  ┌───────────┐  ┌───────────────────────────┐ │
│  │   Web    │  │  Mobile   │  │  Desktop                  │ │
│  │ Flutter  │  │  Flutter  │  │  Flutter + SQLite cache    │ │
│  └────┬─────┘  └─────┬─────┘  └────────────┬──────────────┘ │
│       └───────────────┼─────────────────────┘                │
│                       │ HTTPS / WebSocket                     │
└───────────────────────┼──────────────────────────────────────┘
                        │
┌───────────────────────┼──────────────────────────────────────┐
│              API Gateway / Auth                               │
│        (Schema-per-tenant routing via JWT)                    │
└───────────────────────┼──────────────────────────────────────┘
                        │
┌───────────────────────┼──────────────────────────────────────┐
│                Backend Services                               │
│  ┌────────────────────┼────────────────────────────────┐     │
│  │          FastAPI Application Core                    │     │
│  │                                                      │     │
│  │  ┌────────────┐ ┌────────────┐ ┌─────────────────┐ │     │
│  │  │  Contact   │ │   Intel    │ │   Pipeline      │ │     │
│  │  │  Service   │ │   Engine   │ │   Service       │ │     │
│  │  └────────────┘ └────────────┘ └─────────────────┘ │     │
│  │  ┌────────────┐ ┌────────────┐ ┌─────────────────┐ │     │
│  │  │   Graph    │ │    AI      │ │   Sync          │ │     │
│  │  │  Service   │ │  Service   │ │   Service       │ │     │
│  │  └────────────┘ └────────────┘ └─────────────────┘ │     │
│  │  ┌────────────┐ ┌────────────┐                      │     │
│  │  │  Entity    │ │   Event    │                      │     │
│  │  │ Resolution │ │   Store    │                      │     │
│  │  └────────────┘ └────────────┘                      │     │
│  └─────────────────────────────────────────────────────┘     │
└───────────────────────┬──────────────────────────────────────┘
                        │
┌───────────────────────┼──────────────────────────────────────┐
│                  Data Layer                                    │
│  ┌─────────────┐ ┌─────────────┐ ┌──────────────────────┐   │
│  │ PostgreSQL  │ │    Neo4j    │ │   Object Storage     │   │
│  │ (event      │ │   (graph)   │ │   (files/media)      │   │
│  │  store +    │ │             │ │                      │   │
│  │  views)     │ │             │ │                      │   │
│  └─────────────┘ └─────────────┘ └──────────────────────┘   │
│  ┌─────────────┐ ┌─────────────┐ ┌──────────────────────┐   │
│  │    Redis    │ │   Celery    │ │    Meilisearch       │   │
│  │   (cache)   │ │   (tasks)   │ │    (search)          │   │
│  └─────────────┘ └─────────────┘ └──────────────────────┘   │
└──────────────────────────────────────────────────────────────┘

Browser Extension (Chrome/Firefox — Plasmo)
  └── Pushes captured intelligence to API
```

### 4.2 Technology Stack

| Layer | Technology | Rationale |
|---|---|---|
| **Backend** | Python 3.12+ / FastAPI | Async-first, strong typing, excellent for API-first design |
| **Client** | Flutter / Dart | Single codebase for web, iOS, Android, macOS, Windows, Linux |
| **State Management** | Riverpod | Compile-safe, testable, well-suited for offline-aware state |
| **Primary DB** | PostgreSQL 16+ | Event sourcing, temporal queries, JSONB, schema-per-tenant isolation |
| **Graph DB** | Neo4j | Relationship traversal, shortest-path queries, influence network mapping |
| **Search** | Meilisearch | Typo-tolerant full-text search, lightweight operations, fast indexing |
| **Cache** | Redis | Session management, API response caching, real-time pub/sub |
| **Task Queue** | Celery + Redis | Background OSINT enrichment, AI processing, data sync jobs |
| **Offline DB** | SQLite / Isar (on-device) | Local read cache and write queue for offline operation |
| **Object Storage** | S3-compatible (MinIO) | Contact photos, file attachments, exported reports |
| **AI/LLM** | Anthropic Claude API | Contact insights, summarization, natural language queries |
| **Browser Extension** | TypeScript / Plasmo | Chrome/Firefox extension for LinkedIn/Twitter intelligence capture |

### 4.3 Hybrid Event Sourcing Architecture

The system uses a hybrid data architecture: **event sourcing for contacts and intelligence entities** (where history and auditability are critical), and **conventional mutable tables for configuration, pipelines, and system data** (where simplicity matters more than history).

**Event-sourced entities:** Contacts, Companies, Intelligence Items, Interactions, Employment records.

**Conventional entities:** Tenants, Users, Pipelines, Tags, Custom Field Definitions, Sync Log.

**Core principles:**
- Events are immutable and append-only — no updates or deletes on the event store.
- Current state is derived by replaying events and maintained as materialized views for fast reads.
- Temporal queries answer questions like "What did we know about John on March 15th?"
- Event sourcing naturally supports compliance audits and data subject access requests (GDPR).

**How it works:**

1. A write operation (e.g., updating a contact's job title) is stored as an event: `ContactTitleChanged { contact_id, old_title, new_title, changed_by, timestamp }`.
2. A materialized view table (`contacts_current`) is updated synchronously to reflect the latest state.
3. Read operations query the materialized view for performance.
4. Historical queries replay the event stream up to a given timestamp.
5. Snapshots are periodically created to avoid replaying long event chains.

### 4.4 Multi-Tenancy Model

The platform implements **schema-per-tenant isolation** in PostgreSQL:

- Each tenant receives a **dedicated PostgreSQL schema** (e.g., `tenant_abc`), providing complete data isolation while sharing infrastructure.
- Tenant context is established at the **API gateway via JWT claims** and propagated through all service calls via a schema search path.
- **Neo4j** uses labeled sub-graphs per tenant (e.g., `:Tenant_abc:Contact`).
- **Meilisearch** uses tenant-prefixed index names for search isolation.
- **Schema migrations** are applied per-tenant using an automated migration runner.
- Per-tenant **backup and restore** is possible without affecting other tenants.
- No subdomain or URL-path tenancy — tenant identity is purely token-based.

### 4.5 Offline & Sync Architecture

All clients (web, mobile, desktop) support **offline read access** with a **queued write** model:

**Read path (offline-capable):**
1. Each client maintains a **local SQLite/Isar database** synchronized from the server, storing materialized views of contacts, companies, relationships, and recent intelligence relevant to that user.
2. **Background sync** pulls delta updates when connectivity is available (configurable interval, default: 30 seconds).
3. **Delta compression** minimizes bandwidth for large contact databases.
4. Sync metadata tracks last-sync timestamps per entity type.

**Write path (queued offline writes):**
1. When online, writes go directly to the API and the local cache is updated on confirmation.
2. When offline, write operations are stored in a **local pending queue** with a "pending" status indicator in the UI.
3. The local cache **does not optimistically apply** queued changes — it continues to reflect the last-known server state.
4. On reconnect, the queue **replays sequentially** against the server API.
5. If a write fails (conflict, validation error), the user is **notified and can resolve manually**.
6. Successfully replayed writes update the local cache via the normal sync path.

**Benefits of this approach:**
- No bidirectional sync engine or conflict resolution logic needed.
- The server remains the single source of truth at all times.
- Event sourcing on the backend handles concurrent writes naturally.
- Users can still capture data while offline (notes, new contacts, updates) without losing work.

---

## 5. Core Features

### 5.1 Contact Management

Standard CRM contact management with intelligence extensions and temporal history tracking.

**Entities:**
- **Contact** — An individual person with profile data, communication preferences, and intelligence metadata. Event-sourced: all changes tracked as immutable events.
- **Company** — An organization with firmographic data. Tracks: name/rebrand history, headquarters changes, industry classification, employee count over time, funding rounds, acquisitions.
- **Group** — User-defined collections of contacts (e.g., "Conference Leads Q1", "Advisory Board").

**Fields per Contact:**
- Identity: name, email(s), phone(s), photo, job title, company, social profiles
- Classification: tags, categories, lead source, lead status
- Custom fields: tenant-configurable typed fields (text, number, date, dropdown, multi-select)
- Intelligence score: system-computed composite score (see Section 5.4)
- Relationship data: linked via Neo4j (see Section 5.3)

**Temporal History Tracking:**
- **Employment timeline** — Full history of positions: title changes, department changes, company moves, with temporal bounds (start/end dates).
- **Contact detail history** — Email, phone, and address changes over time, not just current values.
- **Social profile evolution** — Track when social profiles are added, changed, or removed.
- **Key dates** — Birthday, work anniversary, and custom date milestones.
- **Point-in-time queries** — Reconstruct a contact's full profile as it appeared at any historical date.

**Capabilities:**
- Bulk import/export (CSV, vCard, LinkedIn export)
- Contact merging with field-level conflict resolution
- Activity timeline: unified chronological view of all interactions, intel updates, and notes
- Smart tagging: AI-suggested tags based on interaction content and contact attributes

### 5.2 Entity Resolution

A critical system for accurately matching records across multiple data sources.

When intelligence arrives from different channels (enrichment APIs, browser extension, manual entry, email sync), the system must determine whether two records refer to the same real-world person or company.

**Matching Strategy (probabilistic, tiered by confidence):**

| Confidence | Signal | Action |
|---|---|---|
| **High** | Email address exact match | Auto-merge |
| **High** | LinkedIn profile URL match | Auto-merge |
| **Medium** | Name + Company + Title fuzzy match | Auto-merge with flag |
| **Medium** | Phone number match | Auto-merge with flag |
| **Low** | Name + Location fuzzy match | Queue for human review |

**Capabilities:**
- **Probabilistic scoring** — Each potential match receives a confidence score based on weighted signal combinations.
- **Human review queue** — Low-confidence matches are surfaced to users for manual resolution.
- **Source preservation** — Merged records maintain links to all source records, preserving the ability to split incorrectly merged entities.
- **Merge audit trail** — All merge/split operations are recorded as events, fully reversible.
- **Configurable thresholds** — Tenants can adjust auto-merge confidence thresholds based on their data quality tolerance.

### 5.3 Relationship Intelligence

The differentiating layer — powered by Neo4j.

**Relationship Taxonomy:**

| Category | Relationship Types |
|---|---|
| **Hierarchical** | REPORTS_TO, MANAGES, DOTTED_LINE_TO |
| **Professional** | WORKS_WITH, ADVISES, BOARD_MEMBER_OF, INVESTOR_IN |
| **Social** | KNOWS, INTRODUCED_BY, REFERRED_BY, MENTOR_OF |
| **Company-to-Company** | SUBSIDIARY_OF, ACQUIRED_BY, PARTNER_OF, COMPETES_WITH |
| **Deal/Project** | PARTICIPATES_IN, DECISION_MAKER_FOR, INFLUENCER_ON, CHAMPION_OF |

**Graph Model:**

```
// Hierarchical & Professional
(Contact)-[:REPORTS_TO {since, until}]->(Contact)
(Contact)-[:MANAGES {since, until}]->(Contact)
(Contact)-[:ADVISES {context, since}]->(Contact)
(Contact)-[:BOARD_MEMBER_OF {since, until}]->(Company)
(Contact)-[:INVESTOR_IN {round, amount}]->(Company)

// Social
(Contact)-[:KNOWS {strength, since, context, last_interaction}]->(Contact)
(Contact)-[:INTRODUCED_BY {date, outcome}]->(Contact)
(Contact)-[:REFERRED_BY {date, context}]->(Contact)
(Contact)-[:MENTOR_OF {since, domain}]->(Contact)

// Employment (temporal)
(Contact)-[:WORKS_AT {role, department, since, until, is_current}]->(Company)

// Company-to-Company
(Company)-[:SUBSIDIARY_OF]->(Company)
(Company)-[:ACQUIRED_BY {date, amount}]->(Company)
(Company)-[:PARTNER_OF {since, type}]->(Company)
(Company)-[:COMPETES_WITH]->(Company)

// Deal/Project roles
(Contact)-[:DECISION_MAKER_FOR]->(Deal)
(Contact)-[:INFLUENCER_ON]->(Deal)
(Contact)-[:CHAMPION_OF]->(Deal)

// Other
(Contact)-[:ATTENDED {role}]->(Event)
(Contact)-[:MEMBER_OF]->(Group)
(Contact)-[:HAS_SKILL]->(Skill)
```

**Example Graph Queries:**
- "Who do we know at Company X through existing contacts?" (2-degree path finding)
- "Show me the full reporting chain from this person to the CEO"
- "Which contacts have moved between these 3 companies?"
- "Who introduced me to my best clients?"

**Capabilities:**
- **Relationship strength scoring** — Computed from interaction frequency, recency, reciprocity, and depth. Decays over time without reinforcement.
- **Warm introduction paths** — Find the shortest/strongest path between the current user and a target contact through mutual connections.
- **Influence mapping** — Identify key connectors, gatekeepers, and influencers within a network segment.
- **Org chart reconstruction** — Infer reporting structures from job titles, communication patterns, and explicit user input.
- **Relationship timeline** — Visual history of how a relationship has evolved (strength over time, key events).
- **Network visualization** — Interactive graph UI showing clusters, bridges, and isolated nodes.

### 5.4 Behavioral Signal Tracking

Track and analyze how contacts engage over time.

**Signal Sources:**
- Email (send/receive frequency, response time, sentiment)
- Calendar (meeting frequency, cancellation rate, meeting duration trends)
- In-app activity (notes added, profile views, deal stage changes)
- External integrations (form fills, website visits via tracking pixel — opt-in)

**Computed Metrics:**
- **Engagement score** — Weighted composite of interaction frequency and recency.
- **Responsiveness index** — Average response time and response rate.
- **Sentiment trend** — AI-analyzed sentiment across communications over a rolling window.
- **Attention signal** — Detects when a contact suddenly increases or decreases engagement.
- **Best time to contact** — ML-derived optimal day/time window based on historical response patterns.

### 5.5 OSINT Enrichment

Automated and on-demand public data aggregation from three primary channels.

**Channel 1 — Data Enrichment APIs:**
- Pluggable adapters for third-party enrichment services (Apollo, Clearbit, People Data Labs, ZoomInfo).
- Each adapter normalizes data to a common schema and tags the source for attribution.
- New adapters can be added without modifying core logic.

**Channel 2 — Browser Extension (Phase 2):**
- Chrome and Firefox extension built with Plasmo framework.
- Captures profile data, posts, and activity from LinkedIn, Twitter/X, and other sources while the user browses.
- Data is pushed to the API with full provenance tracking (source URL, capture timestamp, capturing user).
- Runs through the entity resolution pipeline to match captured data to existing records.

**Channel 3 — Manual Entry:**
- Direct user input through the application interface.
- All manual entries tracked with the same audit trail as automated sources.

**Additional Data Sources:**
- News mentions (company and individual name monitoring)
- SEC filings / Companies House (for applicable entities)
- Domain/website changes (technology stack changes, hiring pages)
- Patent and publication databases

**Capabilities:**
- **Auto-enrichment on contact creation** — Background job enriches new contacts within minutes.
- **Continuous monitoring** — Configurable alerts when monitored contacts have notable public events (job change, funding round, news mention).
- **Enrichment confidence scoring** — Each enriched data point carries a confidence score and source attribution.
- **Manual verification workflow** — Users can confirm, reject, or correct enriched data.
- **Rate limiting and compliance** — Respects platform ToS, implements rate limiting, stores only publicly available data.

### 5.6 AI-Powered Intelligence

AI is a core feature, not an add-on.

**Capabilities:**
- **Contact summarization** — One-paragraph briefing on any contact synthesizing all available data (profile, interactions, intel, news).
- **Meeting prep briefs** — Auto-generated briefing documents before scheduled meetings, including recent activity, relationship context, talking points, and potential opportunities.
- **Natural language search** — Query contacts and intelligence using plain language (e.g., "Who do I know at fintech companies in Boston that I haven't spoken to in 3 months?").
- **Relationship suggestions** — "You should connect X and Y because..." based on shared interests, complementary needs, or mutual connections.
- **Email/message drafting** — Context-aware message composition using relationship history and contact preferences.
- **Anomaly detection** — Flag unusual patterns (sudden disengagement, unexpected role changes, conflicting data).
- **Pipeline predictions** — For sales users, predict deal outcomes based on engagement signals and historical patterns.

### 5.7 Pipeline & Deal Management

Lightweight but functional sales pipeline.

**Entities:**
- **Pipeline** — A configurable sequence of stages (e.g., Lead > Qualified > Proposal > Negotiation > Closed).
- **Deal** — An opportunity tied to one or more contacts and a company, with value, probability, and expected close date.

**Capabilities:**
- Multiple pipelines per tenant (sales, partnerships, fundraising, etc.)
- Kanban board view with drag-and-drop stage progression
- Deal activity logging (notes, emails, meetings linked to deals)
- Win/loss analysis with reason tracking
- Revenue forecasting based on pipeline stage probabilities and AI-adjusted confidence

### 5.8 Communication Hub

Centralized interaction tracking.

**Integrations:**
- Email (Gmail, Outlook via OAuth — bi-directional sync)
- Calendar (Google Calendar, Outlook Calendar)
- Phone/SMS logging (manual + integration with VoIP providers)
- Video conferencing (Zoom, Teams — meeting metadata)

**Capabilities:**
- Unified inbox showing contact-relevant communications
- Auto-association of emails/meetings to contacts and deals
- Email open/click tracking (opt-in)
- Communication templates with merge fields
- Scheduled send and follow-up reminders

---

## 6. API Design

### 6.1 API Principles

- RESTful with resource-oriented URLs
- JSON:API specification for response formatting
- OpenAPI 3.1 specification auto-generated from FastAPI
- Versioned via URL path (`/api/v1/`)
- Cursor-based pagination for list endpoints
- Consistent error response format (RFC 7807 Problem Details)

### 6.2 Core Resource Endpoints

```
# Authentication
POST   /api/v1/auth/login
POST   /api/v1/auth/refresh
POST   /api/v1/auth/logout
POST   /api/v1/auth/sso/saml          # SAML 2.0 SSO
POST   /api/v1/auth/sso/oidc          # OpenID Connect SSO

# Contacts
GET    /api/v1/contacts
POST   /api/v1/contacts
GET    /api/v1/contacts/{id}
PATCH  /api/v1/contacts/{id}
DELETE /api/v1/contacts/{id}
GET    /api/v1/contacts/{id}/timeline
GET    /api/v1/contacts/{id}/history?at={timestamp}  # Point-in-time
GET    /api/v1/contacts/{id}/relationships
GET    /api/v1/contacts/{id}/intelligence
GET    /api/v1/contacts/{id}/employment-history
POST   /api/v1/contacts/{id}/enrich
GET    /api/v1/contacts/{id}/briefing

# Entity Resolution
GET    /api/v1/resolution/review-queue
POST   /api/v1/resolution/merge
POST   /api/v1/resolution/split
PATCH  /api/v1/resolution/thresholds

# Companies
GET    /api/v1/companies
POST   /api/v1/companies
GET    /api/v1/companies/{id}
PATCH  /api/v1/companies/{id}
GET    /api/v1/companies/{id}/contacts
GET    /api/v1/companies/{id}/intel
GET    /api/v1/companies/{id}/history?at={timestamp}

# Relationships (Graph)
GET    /api/v1/graph/network/{contact_id}
GET    /api/v1/graph/path/{from_id}/{to_id}
POST   /api/v1/graph/relationships
PATCH  /api/v1/graph/relationships/{id}
GET    /api/v1/graph/influencers
GET    /api/v1/graph/clusters
GET    /api/v1/graph/org-chart/{company_id}

# Intelligence
GET    /api/v1/intel/feed
GET    /api/v1/intel/alerts
POST   /api/v1/intel/search
GET    /api/v1/intel/osint/{contact_id}
POST   /api/v1/intel/capture           # Browser extension endpoint

# Deals / Pipeline
GET    /api/v1/pipelines
POST   /api/v1/pipelines
GET    /api/v1/deals
POST   /api/v1/deals
GET    /api/v1/deals/{id}
PATCH  /api/v1/deals/{id}

# AI
POST   /api/v1/ai/query
POST   /api/v1/ai/summarize
POST   /api/v1/ai/draft-message
GET    /api/v1/ai/suggestions

# Sync (for offline clients)
GET    /api/v1/sync/changes?since={timestamp}
POST   /api/v1/sync/push
GET    /api/v1/sync/status

# Events (event sourcing)
GET    /api/v1/events/{entity_type}/{entity_id}
GET    /api/v1/events/{entity_type}/{entity_id}?at={timestamp}
```

### 6.3 WebSocket Endpoints

```
ws://  /ws/v1/notifications    # Real-time alerts and intel updates
ws://  /ws/v1/sync             # Live sync for online clients
```

### 6.4 Authentication & Authorization

- **Authentication:** OAuth 2.0 + JWT access/refresh tokens with refresh token rotation
- **Social login:** Google, Microsoft (for email integration bootstrap)
- **SSO:** SAML 2.0 and OpenID Connect (OIDC) for enterprise tenants
- **API keys:** For programmatic access, third-party integrations, and browser extension auth
- **RBAC roles:**

| Role | Permissions |
|---|---|
| **Owner** | Full tenant administration, billing, user management |
| **Admin** | User management, pipeline configuration, integration setup |
| **Member** | Full read/write on contacts, deals, and intelligence |
| **Viewer** | Read-only access to contacts and intelligence |

---

## 7. Data Model

### 7.1 PostgreSQL Schema (per-tenant schema)

Each tenant gets a dedicated schema. Shared infrastructure tables (tenants, users) live in a `public` schema.

```sql
-- === PUBLIC SCHEMA (shared) ===

public.tenants (id, name, slug, plan, settings, schema_name, created_at)
public.users (id, tenant_id, email, name, role, preferences,
              sso_provider, sso_subject_id, created_at)

-- === TENANT SCHEMA (per-tenant, e.g., tenant_abc.*) ===

-- Event store (immutable, append-only)
events (id, entity_type, entity_id, event_type, payload,
        actor_id, timestamp, sequence_number)

event_snapshots (id, entity_type, entity_id, state,
                 snapshot_at, event_sequence)

-- Contact management (materialized views from events)
contacts_current (id, first_name, last_name, email_primary,
                  phone_primary, job_title, company_id, avatar_url,
                  lead_source, lead_status, engagement_score,
                  intelligence_score, custom_fields, created_by,
                  created_at, updated_at, synced_at)

companies_current (id, name, domain, industry, size,
                   location, description, logo_url, custom_fields,
                   created_at, updated_at)

-- Contact details (multi-value, temporal)
contact_emails (id, contact_id, email, type, is_primary,
                valid_from, valid_until)
contact_phones (id, contact_id, phone, type, is_primary,
                valid_from, valid_until)
contact_social_profiles (id, contact_id, platform, url, username,
                         valid_from, valid_until)
contact_addresses (id, contact_id, street, city, state,
                   country, postal_code, type,
                   valid_from, valid_until)

-- Employment history (temporal)
employment_history (id, contact_id, company_id, title,
                    department, started_at, ended_at,
                    is_current, source, confidence)

-- Entity resolution
entity_match_candidates (id, entity_type, entity_a_id, entity_b_id,
                         confidence_score, match_signals,
                         status, reviewed_by, reviewed_at,
                         created_at)

entity_source_records (id, entity_type, entity_id,
                       source, source_id, raw_data,
                       captured_at, captured_by)

-- Intelligence
intel_items (id, contact_id, company_id, source,
            category, title, summary, raw_data, confidence,
            verified_by, verified_at, created_at, expires_at)

osint_monitors (id, entity_type, entity_id,
               source, frequency, last_checked, status)

-- Interactions
interactions (id, contact_id, deal_id, type,
             direction, subject, body_preview, sentiment_score,
             occurred_at, created_at)

-- Pipeline (conventional tables, not event-sourced)
pipelines (id, name, stages, is_default, created_at)
deals (id, pipeline_id, stage, title, value,
       probability, expected_close, contact_ids,
       company_id, owner_id, closed_at, close_reason,
       created_at, updated_at)

-- Activity & notes
notes (id, contact_id, deal_id, author_id,
       content, is_ai_generated, created_at, updated_at)

activities (id, entity_type, entity_id, actor_id,
           action, metadata, created_at)

-- Tags
tags (id, name, color, is_ai_suggested)
entity_tags (entity_type, entity_id, tag_id, created_at)

-- Custom fields
custom_field_definitions (id, entity_type, name,
                         field_type, options, required, sort_order)

-- Sync tracking
sync_log (id, user_id, device_id, entity_type,
         entity_id, operation, payload, server_timestamp,
         client_timestamp, status)

write_queue_log (id, user_id, device_id, operation,
                 payload, queued_at, replayed_at,
                 status, error_message)
```

### 7.2 Neo4j Graph Schema

```cypher
// Node types
(:Contact {id, tenant_id, name, engagement_score})
(:Company {id, tenant_id, name, industry})
(:Event {id, tenant_id, name, date})
(:Deal {id, tenant_id, title, stage, value})
(:Group {id, tenant_id, name})
(:Skill {name})
(:Industry {name})

// Hierarchical relationships
(:Contact)-[:REPORTS_TO {since: date, until: date}]->(:Contact)
(:Contact)-[:MANAGES {since: date, until: date}]->(:Contact)
(:Contact)-[:DOTTED_LINE_TO {context: string}]->(:Contact)

// Professional relationships
(:Contact)-[:WORKS_WITH {context: string}]->(:Contact)
(:Contact)-[:ADVISES {since: date, domain: string}]->(:Contact)
(:Contact)-[:BOARD_MEMBER_OF {since: date, until: date}]->(:Company)
(:Contact)-[:INVESTOR_IN {round: string, amount: float}]->(:Company)

// Social relationships
(:Contact)-[:KNOWS {strength: float, since: date, context: string, last_interaction: datetime}]->(:Contact)
(:Contact)-[:INTRODUCED_BY {date: date, outcome: string}]->(:Contact)
(:Contact)-[:REFERRED_BY {date: date, context: string}]->(:Contact)
(:Contact)-[:MENTOR_OF {since: date, domain: string}]->(:Contact)

// Employment (temporal)
(:Contact)-[:WORKS_AT {role: string, department: string, since: date, until: date, is_current: boolean}]->(:Company)

// Company-to-Company
(:Company)-[:SUBSIDIARY_OF]->(:Company)
(:Company)-[:ACQUIRED_BY {date: date, amount: float}]->(:Company)
(:Company)-[:PARTNER_OF {since: date, type: string}]->(:Company)
(:Company)-[:COMPETES_WITH]->(:Company)

// Deal/Project roles
(:Contact)-[:DECISION_MAKER_FOR]->(:Deal)
(:Contact)-[:INFLUENCER_ON]->(:Deal)
(:Contact)-[:CHAMPION_OF]->(:Deal)
(:Contact)-[:PARTICIPATES_IN]->(:Deal)

// Other
(:Contact)-[:ATTENDED {role: string}]->(:Event)
(:Contact)-[:MEMBER_OF]->(:Group)
(:Contact)-[:HAS_SKILL]->(:Skill)
(:Contact)-[:INTERESTED_IN]->(:Industry)
```

---

## 8. Non-Functional Requirements

### 8.1 Performance

| Metric | Target |
|---|---|
| API response time (p95) | < 200ms for reads, < 500ms for writes |
| Graph traversal queries | < 500ms for 3-hop paths |
| Search response time (Meilisearch) | < 50ms |
| Offline-to-online queue replay | < 5 seconds for typical batch |
| Client cold start (desktop) | < 2 seconds to interactive (cached data) |
| AI briefing generation | < 10 seconds |
| Event replay (point-in-time query) | < 1 second with snapshots |

### 8.2 Scalability

- Support 10,000 contacts per tenant at launch
- Support 100 concurrent users per tenant
- Horizontal scaling via stateless API servers behind a load balancer
- Database read replicas for reporting workloads
- Event store partitioned by tenant schema for independent scaling

### 8.3 Security

- All data encrypted in transit (TLS 1.3) and at rest (AES-256)
- Tenant data isolation enforced at database level (schema-per-tenant)
- SSO support (SAML 2.0, OIDC) for enterprise tenants
- OWASP Top 10 compliance
- SOC 2 Type II readiness (design controls from day one)
- GDPR and CCPA data subject rights (export, deletion) — event sourcing naturally supports data subject access requests
- Audit logging of all data access and modifications (inherent in event sourcing for event-sourced entities)
- Secret management via environment variables / vault service
- API rate limiting per tenant and per user
- Browser extension uses dedicated API keys with scoped permissions

### 8.4 Reliability

- 99.9% uptime SLA target
- Automated database backups (daily full, hourly incremental) — per-tenant schema backup supported
- Point-in-time recovery for PostgreSQL
- Health check endpoints for all services
- Graceful degradation: offline clients remain functional for reads and queue writes

### 8.5 Observability

- Structured JSON logging (correlation IDs across requests)
- Metrics: Prometheus-compatible endpoint
- Tracing: OpenTelemetry instrumentation
- Alerting: configurable thresholds on error rates, latency, queue depth

---

## 9. Integration Points

### 9.1 First-Party Integrations (MVP)

| Integration | Type | Purpose |
|---|---|---|
| Gmail | OAuth 2.0 | Email sync, contact enrichment |
| Google Calendar | OAuth 2.0 | Meeting sync, availability |
| Outlook/Exchange | OAuth 2.0 | Email and calendar sync |
| LinkedIn (manual) | CSV import | Bulk contact import from export |

### 9.2 Planned Integrations (Post-MVP)

| Integration | Type | Purpose |
|---|---|---|
| Browser Extension | Plasmo (Chrome/Firefox) | LinkedIn/Twitter intelligence capture (Phase 2) |
| Apollo / Clearbit / PDL | API adapters | Commercial enrichment data (Phase 2) |
| Zoom | OAuth 2.0 | Meeting metadata, recording transcripts |
| Slack | OAuth 2.0 | Notifications, contact lookup slash command |
| Zapier / Make | Webhook | User-configurable automations |
| Twilio | API | SMS/call logging |
| LinkedIn API | OAuth 2.0 | Real-time profile updates (requires partnership) |

### 9.3 Webhook System

- Outbound webhooks for key events (contact created, deal stage changed, intel alert triggered)
- HMAC-SHA256 signed payloads
- Retry with exponential backoff (3 attempts)
- Webhook management via API and UI

---

## 10. Development Phases

### Phase 1 — Foundation (MVP)

**Goal:** Core contact management with event sourcing, basic intelligence, and offline-capable clients.

- Tenant and user management (registration, auth, RBAC, SSO)
- Schema-per-tenant provisioning and migration system
- Event store and materialized view infrastructure
- Contact and company CRUD with custom fields and temporal history
- Basic relationship creation and visualization (Neo4j integration)
- Contact import (CSV, vCard)
- Activity timeline with event-sourced history
- Notes and tagging
- Meilisearch integration for full-text search
- Offline read cache + queued writes for desktop client
- AI contact summarization
- Natural language search
- API documentation (auto-generated OpenAPI)

### Phase 2 — Intelligence Engine

**Goal:** Full intelligence capabilities that differentiate from standard CRMs.

- OSINT enrichment engine with pluggable API adapters (Apollo, Clearbit, PDL)
- **Browser extension** (Chrome/Firefox via Plasmo) for LinkedIn/Twitter capture
- **Entity resolution pipeline** with probabilistic matching and human review queue
- Continuous monitoring with configurable alerts
- Behavioral signal tracking (engagement scoring, responsiveness)
- Relationship strength scoring and decay
- Warm introduction path finding
- Influence mapping and network visualization
- Meeting prep brief generation
- Sentiment analysis on interactions

### Phase 3 — Communication & Pipeline

**Goal:** Replace standalone CRM tools for sales workflows.

- Email integration (Gmail, Outlook bi-directional sync)
- Calendar integration
- Pipeline and deal management (Kanban, forecasting)
- Deal-specific relationship roles (Decision Maker, Influencer, Champion)
- Communication templates
- Email tracking (opens, clicks)
- Win/loss analysis
- AI-powered pipeline predictions

### Phase 4 — Ecosystem & Scale

**Goal:** Platform extensibility and growth features.

- Webhook system
- Zapier / Make integration
- Zoom / Teams integration
- Advanced reporting and dashboards
- Team collaboration features (shared notes, @mentions, assignments)
- Mobile push notifications
- Bulk operations and workflow automation
- White-label / custom branding per tenant

---

## 11. Success Metrics

| Metric | Target (6 months post-launch) |
|---|---|
| Monthly active users per tenant | > 80% of seats |
| Contacts with intelligence data | > 60% auto-enriched |
| AI feature adoption | > 50% of users use AI search or briefings weekly |
| Offline queue replay success rate | > 99.5% |
| Entity resolution auto-merge accuracy | > 95% for high-confidence matches |
| NPS score | > 40 |
| Data freshness (OSINT) | < 24 hours for monitored contacts |

---

## 12. Open Questions

1. **OSINT legal review** — Which data sources require explicit user consent for enrichment? Jurisdiction-specific compliance review needed.
2. **Neo4j hosting** — Self-hosted vs. Neo4j Aura managed service? Cost/ops tradeoff to evaluate.
3. **AI model selection** — Claude as primary, but should we support fallback models for cost optimization on high-volume operations (e.g., tagging)?
4. **Event store retention** — How long to retain raw events before compacting to snapshots? Compliance vs. storage cost tradeoff.
5. **Browser extension store approval** — Chrome Web Store and Firefox Add-ons review process and LinkedIn ToS implications.
6. **Pricing model** — Per-seat, per-contact, or hybrid? Impacts multi-tenancy quotas and rate limiting design.
7. **Note format** — Rich text (better UX) vs. Markdown (portable) vs. plain text (simplest). Impacts search indexing and offline sync payload size.
8. **File attachments** — Full file storage support vs. external link references in MVP. Storage costs and offline sync complexity implications.

---

## 13. Glossary

| Term | Definition |
|---|---|
| **CIM** | Customer Intelligence Management — the system category |
| **Event sourcing** | Data architecture where state changes are stored as immutable events rather than mutable rows |
| **Materialized view** | A precomputed table derived from event replay, used for fast read access |
| **Entity resolution** | The process of determining when records from different sources refer to the same real-world entity |
| **Intel item** | A discrete piece of intelligence about a contact or company |
| **Engagement score** | Numeric score reflecting interaction frequency and recency |
| **Intelligence score** | Composite score reflecting data completeness and relationship value |
| **OSINT** | Open-Source Intelligence — publicly available data |
| **Warm intro path** | A chain of mutual connections between the user and a target contact |
| **Enrichment** | The process of augmenting a contact record with external data |
| **Sync delta** | The set of changes between local and server state since last sync |
| **Write queue** | Local buffer storing offline write operations for replay on reconnect |
| **Schema-per-tenant** | Multi-tenancy model where each tenant gets a dedicated database schema |

---

## 14. Appendix: Technology References

**Backend:**
- FastAPI: https://fastapi.tiangolo.com
- SQLAlchemy (async): https://docs.sqlalchemy.org
- Celery: https://docs.celeryq.dev

**Frontend:**
- Flutter: https://flutter.dev
- Riverpod (state management): https://riverpod.dev
- Isar (local DB): https://isar.dev

**Databases:**
- PostgreSQL: https://postgresql.org
- Neo4j: https://neo4j.com
- Meilisearch: https://meilisearch.com

**Browser Extension:**
- Plasmo: https://plasmo.com

**Enrichment APIs:**
- Apollo: https://apollo.io
- Clearbit: https://clearbit.com
- People Data Labs: https://peopledatalabs.com
