# CRMExtender — Product TDD

**Version:** 1.0
**Last Updated:** 2026-02-23
**Status:** Draft

---

## 1. Overview

This document captures the global technology and architecture decisions that apply across the entire CRMExtender system. Entity-specific and action-specific decisions belong in their own TDDs (e.g., Contact Entity TDD, Merge & Split TDD). When an entity TDD is silent on a topic, the decisions in this document apply as defaults.

This is a living document. Decisions are recorded here as they are made — both by the product/architecture owner and by Claude Code during implementation. Each decision includes rationale so that future sessions can understand why a choice was made without re-deriving it.

**Current state:** CRMExtender is in active development with a working system (v17 schema, 56 tables, 1,514 tests, ~260 MB production database). The architecture reflects both intentional decisions and organic evolution during PoC development.

---

## 2. Language & Framework

### 2.1 Backend: Python 3.12 + FastAPI

**Decision:** Python 3.12 with FastAPI as the web framework, served by Uvicorn (ASGI).

**Rationale:** Python provides the richest ecosystem for AI integration (Anthropic SDK), email parsing (BeautifulSoup4, mail-parser-reply, quotequail), and rapid iteration. FastAPI offers async support, automatic OpenAPI docs, and Pydantic validation. Uvicorn is the standard ASGI server for FastAPI.

**Alternatives Rejected:**
- Node.js/TypeScript — Would unify the stack with the frontend, but the Python AI and email parsing ecosystem is significantly more mature.
- Django — Full-featured but heavier than needed. FastAPI's lightweight approach suits the API-first architecture better.

**Constraints/Tradeoffs:** Two-language stack (Python backend, TypeScript frontend) requires developers comfortable in both. Accepted because the benefits of each ecosystem outweigh the cost of context switching.

### 2.2 Frontend: React 19 + TypeScript + Tailwind CSS 4

**Decision:** React 19.2 with TypeScript 5.9, Tailwind CSS 4.2 for styling, Vite 7.3 for builds.

**Rationale:** React provides the component model needed for the complex grid-based UI. TypeScript catches errors at compile time across a large component tree. Tailwind enables the corporate, information-dense aesthetic without custom CSS maintenance. Vite provides fast HMR during development and optimized production builds.

**Key libraries:**

| Library | Purpose |
|---|---|
| Zustand 5.0 | State management (4 stores: navigation, layout, gridDisplay, gridIntelligence) |
| @tanstack/react-query 5.90 | Server state, caching, infinite scroll |
| @tanstack/react-table 8.21 | Headless table engine for the grid |
| @tanstack/react-virtual 3.13 | Row virtualization (10,000+ rows) |
| react-resizable-panels 4.6 | 3-panel layout (action, content, detail) |
| react-hook-form 7.71 | Form state management |
| cmdk 1.1 | Command palette (Ctrl+K) |
| react-hotkeys-hook 5.2 | Keyboard shortcut management |
| lucide-react 0.575 | Icon library |
| sonner 2.0 | Toast notifications |
| date-fns 4.1 | Date formatting and manipulation |

### 2.3 Dual UI Architecture

**Decision:** Two UI frontends are served from the same FastAPI instance: an HTMX/Jinja2 server-rendered UI on `/` routes and a React SPA on `/app/`.

**Rationale:** The HTMX UI was built first during PoC development and provides full CRUD for all entity types. The React SPA was introduced for the adaptive grid intelligence and richer interaction model. Both share the same backend, database, and authentication middleware.

**Constraints/Tradeoffs:** Maintaining two UIs is temporary. The React SPA is the target production UI. The HTMX UI will be deprecated once the React SPA achieves feature parity. During the transition, new features are built in React only.

---

## 3. Data Storage

### 3.1 Database: SQLite (Current) → PostgreSQL (Production Target)

**Decision:** SQLite 3 with WAL mode and FTS5 for current development and single-tenant deployment. PostgreSQL 16+ is the production target for multi-tenant deployment.

**Rationale:** SQLite enables zero-infrastructure development, single-file deployment, and ships with Python. The existing system runs 56 tables, ~260 MB, 1,514 tests on SQLite. PostgreSQL is needed for production due to: schema-per-tenant isolation, JSONB with GIN indexes, partial indexes, materialized views, row-level security, and concurrent write support beyond WAL mode.

**Alternatives Rejected:**
- MongoDB — The data model is highly relational (hierarchy, M:N joins, participant lookups). Document stores add complexity without benefit.
- MySQL/MariaDB — No technical blocker, but PostgreSQL offers superior JSONB, CTE, and schema-per-tenant support.
- Starting on PostgreSQL from day one — Slowed iteration speed. SQLite's zero-setup enabled rapid PoC development.

**Constraints/Tradeoffs:** Schema DDL is written in a compatible subset of both engines. JSON columns use TEXT in SQLite and JSONB in PostgreSQL. Some PostgreSQL-only optimizations (partial indexes, TIMESTAMPTZ, table partitioning, pg_trgm) are deferred until migration. See Section 3.2 for the compatibility strategy.

### 3.2 SQLite / PostgreSQL Compatibility Strategy

**Decision:** All schema DDL uses the intersection of SQLite and PostgreSQL syntax. A thin abstraction layer handles the few syntactic differences. SQLAlchemy Core will be introduced for production to handle dialect abstraction automatically.

**Compatible features used:** CREATE TABLE IF NOT EXISTS, TEXT/INTEGER/REAL types, PRIMARY KEY, FOREIGN KEY with CASCADE/SET NULL, UNIQUE constraints, CHECK constraints, UPSERT (ON CONFLICT), WITH RECURSIVE, CREATE INDEX IF NOT EXISTS.

**SQLite-specific pragmas:** WAL mode (`PRAGMA journal_mode=WAL`), FK enforcement (`PRAGMA foreign_keys=ON`), `PRAGMA legacy_alter_table=ON` before table renames.

**PostgreSQL-only optimizations (deferred):**

| Feature | Benefit | Application |
|---|---|---|
| TIMESTAMPTZ | Native timestamp handling | Replace TEXT date columns |
| JSONB + GIN index | Indexed JSON queries | view query_def, provider_metadata, user_metadata |
| Partial indexes | Smaller, faster indexes | Common filters like `WHERE status = 'active'` |
| Materialized views | Pre-computed aggregates | Dashboard statistics |
| BOOLEAN type | Semantic clarity | Replace INTEGER 0/1 columns |
| Table partitioning | Large table performance | Communications by timestamp |
| Row-level security | Per-user access control | Permissions enforcement |
| pg_trgm + GIN | Fuzzy text search | Contact name search |

### 3.3 Multi-Tenancy: customer_id FK (Current) → Schema-Per-Tenant (Production)

**Decision:** Current implementation uses a `customer_id` foreign key on all data tables with ON DELETE CASCADE for tenant isolation. Production PostgreSQL deployment will use schema-per-tenant isolation.

**Rationale:** customer_id FK is simple and works for single-tenant SQLite deployment. Schema-per-tenant in PostgreSQL provides stronger isolation, independent backups, and eliminates the risk of cross-tenant data leaks from missing WHERE clauses.

**Current state:** Single customer (`cust-default`), single user (admin). All data queries are scoped by customer_id through the access control layer.

### 3.4 Event Sourcing vs. Conventional Tables

**Decision:** Contacts and intelligence entities use event sourcing (append-only event store with materialized read model tables). Conversations and communications use conventional mutable tables.

**Rationale:** Contacts benefit from event sourcing because merge/split operations need full audit trails, enrichment requires source attribution on every data point, and GDPR compliance requires the ability to reconstruct and purge complete data histories. Conversations are read-heavy, update-moderate, and don't require point-in-time reconstruction — conventional tables with `updated_at` timestamps are sufficient.

**Constraints/Tradeoffs:** Two data access patterns coexist in the same database. The event-sourced entities have a write path (append event → update materialized view) and a read path (query materialized view). Conventional entities have standard CRUD. This adds complexity but is justified by the different audit and compliance requirements.

### 3.5 Entity ID Convention: Prefixed ULIDs

**Decision:** All entity IDs are prefixed ULIDs — a type prefix followed by an underscore and a ULID (e.g., `con_01HX7VFBK3...` for contacts, `com_01HX7...` for companies). IDs are immutable after creation.

**Rationale:** Prefixed ULIDs provide: globally unique IDs without coordination, chronological sorting (ULID encodes timestamp), human-readable type identification from the ID alone, and safe use as URL path components. The prefix eliminates accidental cross-entity lookups.

**Alternatives Rejected:**
- UUID v4 — No inherent ordering, no type identification. Prefixed ULIDs are strictly superior for this use case.
- Auto-increment integers — Not globally unique, leak information about record count, and break during merges or cross-tenant operations.

### 3.6 Schema Migration System

**Decision:** Incremental Python migration scripts (`migrate_to_v2.py` through `migrate_to_v17.py`), each standalone and executable. No ORM migration framework (Alembic) yet.

**Rationale:** Python scripts provide full control over complex migrations (data transformations, multi-step DDL, validation). Each migration includes: auto-backup, WAL mode setup, FK enforcement, pre-migration counts, step-by-step execution, post-migration verification, and `--dry-run` / `--db PATH` CLI flags.

**SQLite-specific safeguards:** `PRAGMA legacy_alter_table = ON` before table renames (prevents FK auto-rewrite). COALESCE-based indexes for NULL-safe uniqueness (SQLite treats each NULL as distinct).

**Future:** Alembic will be introduced with the PostgreSQL migration to manage schema changes with upgrade/downgrade paths.

---

## 4. API Design

### 4.1 REST API Convention

**Decision:** JSON REST API under `/api/v1/` prefix. All entity CRUD follows consistent patterns. HTMX routes serve HTML on `/` paths.

**Rationale:** REST provides a predictable, cacheable API surface. The `/api/v1/` prefix enables versioning. JSON responses align with the React SPA's data fetching model (React Query).

**Key endpoint patterns:**
- `GET /api/v1/views/{id}/data?page=&sort=&search=&filters=` — Paginated view data with `has_more`
- `GET /api/v1/{entity-type}/{id}` — Entity detail (identity, context, timeline zones)
- `POST /api/v1/{entity-type}` — Create entity
- `POST /api/v1/cell-edit` — Inline single-cell update with validation
- `GET /api/v1/search?q={query}` — Cross-entity grouped search

### 4.2 Views Engine: Dynamic Query Builder

**Decision:** A centralized views engine dynamically builds SQL queries from view configuration (columns, filters, sort, search, pagination, visibility scoping). All list views for all entity types go through this engine.

**Rationale:** A single query builder eliminates per-entity query duplication, ensures consistent filtering/sorting/pagination behavior, and enables user-defined saved views. The entity registry defines field metadata (SQL expression, type, sortable, filterable, editable) that the engine consumes.

**Query construction pipeline:**
1. SELECT — Dynamic column expressions from FieldDef.sql
2. FROM/JOIN — Entity base_joins + visibility joins
3. WHERE — Visibility scoping + user filters + search + extra conditions
4. GROUP BY — Prevents JOIN explosion (entity_def.group_by)
5. ORDER BY — NULL-last + COLLATE NOCASE + sortable validation
6. LIMIT/OFFSET — Page-based pagination with total count

**Filter operators (13):** `equals`, `not_equals`, `contains`, `not_contains`, `starts_with`, `gt`, `lt`, `gte`, `lte`, `is_before`, `is_after`, `is_empty`, `is_not_empty`.

### 4.3 Entity Registry: Field Metadata

**Decision:** A centralized field registry (`poc/views/registry.py`) defines field metadata for all 8 entity types. Each field declares: label, SQL expression, data type, sortable, filterable, editable, link target, db_column, and select_options.

**Rationale:** The registry is the single source of truth for how fields behave in the UI. The views engine, inline editing, search, and grid intelligence all consume this registry. When the Entity Base PRD declares a field as sortable/filterable/editable, that declaration maps directly to the registry.

**Field data types:** text, number, datetime, select, email, phone, url, hidden.

**Sort performance categories:**

| Category | Sort Cost | Examples |
|---|---|---|
| Direct columns | Negligible (indexed) | name, status, created_at |
| JOIN columns | Negligible (base_joins) | company_name, relationship_type |
| Correlated subqueries | Expensive (N subqueries per sort) | email, phone, address, score, counts |

Fields backed by correlated subqueries are marked `sortable=False` in the registry unless the Entity TDD specifies a caching/denormalization strategy to make them performant. The Entity Base PRD marks these fields with † and the TDD documents the caching approach.

---

## 5. Authentication & Security

### 5.1 Authentication: bcrypt + Google OAuth 2.0

**Decision:** Two authentication methods: password-based (bcrypt hash verification) and Google OAuth 2.0 code flow. A bypass mode (`CRM_AUTH_ENABLED=false`) auto-logs in as the first active user for development.

**Rationale:** Password auth provides a standalone login path. Google OAuth enables SSO and is required for Gmail/Calendar/Contacts sync authorization. Bypass mode eliminates login friction during development.

### 5.2 Session Management: Server-Side Sessions

**Decision:** Server-side sessions stored in the `sessions` database table. Session ID is transmitted via `crm_session` HTTP-only cookie. Default TTL: 720 hours (30 days), configurable via `SESSION_TTL_HOURS`.

**Rationale:** Server-side sessions are simple, secure, and allow server-controlled revocation. HTTP-only cookies prevent XSS-based session theft.

### 5.3 Access Control: Per-Entity Visibility

**Decision:** Per-entity visibility functions return `(WHERE_clause, [params])` tuples that are injected into the views engine query. Different entities have different visibility models.

**Current visibility models:**
- **Contacts/Companies:** Public records + user's own records (via junction tables `user_contacts` / `user_companies`)
- **Conversations/Communications:** Access via provider_account ownership or explicit `conversation_shares`
- **Projects/Relationships/Notes:** Tenant-scoped (all users in customer see all)

**Rationale:** Visibility is enforced at the query level, not the application level. This ensures no data leaks regardless of which API endpoint or UI component accesses the data.

---

## 6. AI Integration

### 6.1 Claude API for AI Features

**Decision:** Anthropic Claude API (via Python SDK, version 0.39+) for all AI features: conversation summarization, contact briefings, natural language search, tag suggestions, and anomaly detection.

**Current model:** `claude-sonnet-4-20250514` (configurable via `POC_CLAUDE_MODEL`).

**Rationale:** Claude provides the reasoning quality needed for nuanced CRM tasks (summarizing multi-party email threads, extracting action items, identifying job changes from enrichment data). Single vendor simplifies API management and prompt engineering.

**Rate limiting:** Token-bucket rate limiter at 2 requests/second (configurable via `POC_CLAUDE_RATE_LIMIT`). Shared across all AI features.

---

## 7. External Integrations

### 7.1 Google Workspace APIs

**Decision:** Google APIs provide the primary data source for the CRM. OAuth 2.0 with per-account token persistence.

| API | Scope | Purpose |
|---|---|---|
| Gmail | gmail.readonly | Email thread sync with incremental history tracking |
| People | contacts.readonly | Contact sync, group membership |
| Calendar | calendar.readonly | Event sync with attendee matching |
| OAuth 2.0 | openid, email, profile | User authentication |

**Token storage:** Per-account tokens at `credentials/token_{email}.json`.

**Rate limiting:** Token-bucket rate limiter at 5 requests/second (configurable via `POC_GMAIL_RATE_LIMIT`). Shared across all Google API calls.

**Sync patterns:**
- **Email:** Incremental via Gmail History API (`history_id` cursor). Configurable history window (30d–all).
- **Calendar:** Incremental via Calendar sync tokens. Handles 410 Gone with full resync. 90-day window for full sync.
- **Contacts:** Full sync via People API with UPSERT matching by email.

### 7.2 Rate Limiting Pattern

**Decision:** Token-bucket rate limiter (`poc/rate_limiter.py`) used for all external API calls. Separate instances for Gmail (5 req/s) and Claude (2 req/s).

**Implementation:** `RateLimiter(rate, burst)` with `acquire()` that blocks until a token is available, sleeping for the calculated deficit time if the bucket is empty.

---

## 8. Frontend Architecture Patterns

### 8.1 Application Shell: 3-Panel Resizable Layout

**Decision:** The React SPA uses a 3-panel layout: Icon Rail (60px) + Action Panel (280px, collapsible) + Content Area (flexible) + Detail Panel (480px, collapsible). Panels are resizable via `react-resizable-panels`. Sizes persist to localStorage.

**Rationale:** The 3-panel layout maximizes information density for a CRM application. The action panel provides view navigation, the content area shows the grid, and the detail panel shows record previews without navigating away from the list.

### 8.2 State Management: Zustand Stores

**Decision:** Four Zustand stores, each with a specific scope and persistence model:

| Store | Key State | Persistence |
|---|---|---|
| navigation | activeEntityType, activeViewId, selectedRowId, sort, search, filters, focusedColumn | Memory |
| layout | panel visibility, panel sizes, searchModalOpen | localStorage |
| gridDisplay | density, fontSize, alternatingRows, gridlines, rowHover | localStorage |
| gridIntelligence | computedLayout, override functions | Memory |

**Rationale:** Zustand is lightweight, TypeScript-friendly, and doesn't require provider wrappers. Separating stores by concern keeps state updates granular and prevents unnecessary re-renders.

### 8.3 Data Fetching: React Query

**Decision:** @tanstack/react-query for all server state. Query hooks per endpoint with configured stale times. Mutations invalidate relevant query caches on success.

**Key stale times:**
- Entity registry: 5 minutes (changes only on deployment)
- View configuration: 30 seconds
- View data (infinite scroll): 15 seconds
- Entity detail: 30 seconds
- Global search: 10 seconds

**Rationale:** React Query provides caching, background refetching, and infinite scroll support out of the box. Stale times are tuned per data type — slowly changing config gets longer caches, frequently changing data gets shorter ones.

### 8.4 Adaptive Grid Intelligence

**Decision:** A 7-layer pipeline computes optimal column layout based on viewport size, content analysis, and column priority:

1. Display Profile — Viewport measurement, tier classification (ultra_wide ≥2400px through minimal <1024px)
2. Content Analysis — Per-column metrics (max/median/p90 width, null ratio, diversity) from first 50 rows
3. Column Priority — Importance classification (Class 0–3)
4. Cell Alignment — L/C/R alignment by content type and width
5. Diversity Demotion — Hide low-value columns (progressive: normal → annotated → collapsed → header_only → hidden)
6. Column Allocation — Distribute available width by priority and content needs
7. Layout Engine — Orchestrate all layers, apply user overrides

**Rationale:** CRM data varies dramatically across entity types and user contexts. Static column widths waste space or truncate content. The intelligence pipeline adapts the grid to the actual data being displayed.

---

## 9. Testing

### 9.1 Testing Framework: pytest

**Decision:** pytest for all backend testing. 1,514 tests across 40+ modules.

**Fixture pattern:** Each test gets a fresh SQLite database via `tmp_db` fixture that initializes the schema, inserts a test customer and user, and monkeypatches the config. `TestClient` wraps the FastAPI app for API tests.

**Coverage areas:** Authentication (bcrypt, Google OAuth, sessions), access control, contact/company merge with dedup, email parsing and sync, calendar sync, views engine (filtering, sorting, pagination), settings cascade, notes CRUD with FTS, vCard import, API endpoints, phone normalization, relationship inference.

---

## 10. Configuration

### 10.1 Environment-Based Configuration

**Decision:** All configuration via environment variables (loaded from `.env` file via python-dotenv) with sensible defaults. No configuration files beyond `.env`.

**Key variables:**

| Variable | Default | Purpose |
|---|---|---|
| POC_DB_PATH | data/crm_extender.db | SQLite database path |
| CRM_AUTH_ENABLED | true | Enable/disable authentication |
| SESSION_SECRET_KEY | — | Session signing key |
| SESSION_TTL_HOURS | 720 | Session lifetime |
| ANTHROPIC_API_KEY | — | Claude API key |
| POC_CLAUDE_MODEL | claude-sonnet-4-20250514 | AI model |
| POC_GMAIL_RATE_LIMIT | 5 | Gmail API req/sec |
| POC_CLAUDE_RATE_LIMIT | 2 | Claude API req/sec |
| POC_GMAIL_MAX_THREADS | 50 | Batch size for email sync |
| CRM_UPLOAD_DIR | — | File upload directory |
| MAX_UPLOAD_SIZE_MB | 10 | Upload size limit |

### 10.2 Settings System: 4-Level Cascade

**Decision:** Application settings use a 4-level cascade: User Setting → System Setting → Setting Default (column) → Hardcoded Fallback.

**Rationale:** Allows per-user customization (e.g., timezone, email history window) with sensible system-level defaults, without requiring every setting to be explicitly configured.

---

## 11. Design Principles

These principles apply globally across all entity TDDs and implementation work. They are not suggestions — they are constraints that Claude Code must follow.

### 11.1 Display Speed is Paramount

The system's value depends on fast, responsive data access. Denormalize wherever it reduces JOIN depth for frequently displayed data. Accept write complexity to achieve read speed.

### 11.2 Idempotent Writes

All sync operations use UPSERT or INSERT-ON-CONFLICT patterns. Safe to re-run at any time. No operation should produce different results on second execution.

### 11.3 Schema Compatibility

DDL must work in both SQLite and PostgreSQL with minimal divergence. PostgreSQL-only features are used only where a SQLite fallback exists (or is explicitly accepted as a migration-time change).

### 11.4 Contacts Are Created Immediately

Unknown identifiers create minimal contact records (`status='incomplete'`) on first encounter. This prevents communications from existing without a contact linkage and ensures the identity resolution pipeline always has a record to work with.

### 11.5 Every Correction Is a Training Signal

User corrections to assignments, triage, and conversation management are captured in dedicated correction tables to feed the AI learning system. No user correction is discarded.

### 11.6 Sort Performance Awareness

Fields in the entity registry must respect the sort performance categories (direct column, JOIN column, correlated subquery). Subquery-backed fields are marked `sortable=False` unless the entity TDD defines a caching strategy. The Entity Base PRD marks fields requiring caching with † in the Sortable column.

### 11.7 Editability Is Explicit

Every field in the Entity Base PRD declares its edit behavior (Direct, Override, Via sub-entity, Computed, System). Claude Code must not make a field editable that the PRD marks as Computed or System, and must route Via sub-entity fields through the appropriate editor rather than inline editing.

---

## 12. Project Structure

```
CRMExtender/
├── poc/                           # Backend package
│   ├── __main__.py                # CLI entry point
│   ├── config.py                  # Configuration
│   ├── database.py                # SQLite schema + connection
│   ├── models.py                  # Data models
│   ├── auth.py                    # Google OAuth flow
│   ├── session.py                 # Session CRUD
│   ├── passwords.py               # bcrypt hashing
│   ├── settings.py                # 4-level cascade
│   ├── hierarchy.py               # User/project/topic CRUD
│   ├── access.py                  # Visibility query builders
│   │
│   ├── sync.py                    # Email sync orchestration
│   ├── gmail_client.py            # Gmail API wrapper
│   ├── contacts_client.py         # Google Contacts API
│   ├── calendar_client.py         # Google Calendar API
│   ├── calendar_sync.py           # Calendar sync logic
│   ├── email_parser.py            # MIME parsing
│   ├── html_email_parser.py       # HTML sanitization
│   ├── conversation_builder.py    # Thread assembly
│   ├── summarizer.py              # Claude AI summarization
│   ├── triage.py                  # Conversation filtering
│   │
│   ├── contacts.py                # Contact CRUD
│   ├── contact_companies.py       # Affiliation management
│   ├── contact_company_roles.py   # Role definitions
│   ├── contact_merge.py           # Contact merge
│   ├── contact_matcher.py         # Email → contact resolution
│   ├── domain_resolver.py         # Email domain → company
│   ├── company_merge.py           # Company merge
│   ├── relationship_inference.py  # Relationship scoring
│   ├── notes.py                   # Notes CRUD + FTS
│   ├── vcard_import.py            # vCard import
│   ├── enrichment_pipeline.py     # Batch enrichment
│   │
│   ├── migrate_to_v2.py … v17.py  # Schema migrations
│   │
│   ├── views/
│   │   ├── registry.py            # Entity field definitions (8 types)
│   │   ├── engine.py              # Dynamic query builder
│   │   ├── crud.py                # View configuration CRUD
│   │   └── layout_overrides.py    # Adaptive grid overrides
│   │
│   └── web/
│       ├── app.py                 # FastAPI app factory
│       ├── middleware.py           # AuthMiddleware
│       ├── dependencies.py        # FastAPI dependencies
│       ├── filters.py             # Jinja2 filters
│       ├── static/                # CSS, JS, images
│       ├── templates/             # Jinja2 (base, entities, settings)
│       └── routes/
│           ├── api.py             # /api/v1/* (JSON)
│           ├── auth_routes.py     # Login, register, OAuth
│           ├── contacts.py        # /contacts (HTMX)
│           ├── companies.py       # /companies (HTMX)
│           ├── conversations.py   # /conversations (HTMX)
│           ├── communications.py  # /communications (HTMX)
│           ├── events.py          # /events (HTMX)
│           ├── projects.py        # /projects (HTMX)
│           ├── relationships.py   # /relationships (HTMX)
│           ├── notes.py           # /notes (HTMX)
│           ├── views.py           # /views (HTMX)
│           ├── dashboard.py       # / (HTMX)
│           └── settings_routes.py # /settings (HTMX)
│
├── frontend/                      # React SPA
│   ├── package.json
│   ├── vite.config.ts             # Base /app/, proxy to :8001
│   ├── tsconfig.json
│   ├── src/
│   │   ├── main.tsx               # React root + QueryClient
│   │   ├── App.tsx                # Root component
│   │   ├── index.css              # Tailwind theme tokens
│   │   ├── api/                   # REST client + query hooks
│   │   ├── components/
│   │   │   ├── shell/             # AppShell, IconRail, panels
│   │   │   ├── grid/              # DataGrid, toolbar, editors, modals
│   │   │   ├── detail/            # RecordDetail, zones
│   │   │   └── search/            # GlobalSearchModal
│   │   ├── hooks/                 # useGridIntelligence, useGridKeyboard
│   │   ├── lib/                   # Layout intelligence (7 modules) + search parser
│   │   ├── stores/                # Zustand (navigation, layout, display, intelligence)
│   │   └── types/                 # TypeScript definitions
│   └── dist/                      # Production build output
│
├── tests/                         # pytest suite (1,514 tests)
├── data/                          # SQLite DB + backups + uploads
├── credentials/                   # OAuth tokens
├── docs/                          # PRDs + design documents
└── pyproject.toml                 # Python dependencies
```

---

## 13. Production Data Profile

Current production data for performance benchmarking and capacity planning:

| Metric | Value |
|---|---|
| Database size | ~260 MB |
| Customers | 1 |
| Users | 1 (admin) |
| Provider accounts | 2 |
| Conversations | 3,409 |
| Contacts | 515 |
| Companies | 166 |
| Tags | 817 |
| Schema version | v17 (56 tables) |
| Test count | 1,514 |
