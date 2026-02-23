# CRM Extender — Technical Architecture PRD

> **Version:** 1.0 | **Date:** 2026-02-23 | **Schema Version:** v17 | **Test Count:** 1,514

---

## 1. System Overview

CRM Extender is a multi-tenant CRM platform that aggregates email, calendar, and contact data from Google Workspace into a unified conversation-centric model. It provides AI-powered summarization, contact identity resolution, relationship inference, and an adaptive grid-based UI for exploring and managing CRM data.

**Key Capabilities:**
- Gmail thread sync with incremental history tracking
- Google Calendar event sync with attendee matching
- Google Contacts sync with vCard import
- AI conversation summarization and triage (Claude API)
- Contact identity resolution and merge
- Multi-company affiliations with temporal tracking
- Adaptive grid intelligence with responsive column layout
- Full-text search across all entity types
- Notes system with revision history and multi-entity linking

---

## 2. Technology Stack

### 2.1 Backend

| Component | Technology | Version |
|-----------|-----------|---------|
| Language | Python | 3.12 |
| Web Framework | FastAPI | 0.115+ |
| ASGI Server | Uvicorn | 0.30+ |
| Database | SQLite 3 | Built-in (WAL mode, FTS5) |
| Templating | Jinja2 | 3.1 |
| Authentication | bcrypt + Google OAuth 2.0 | — |
| AI | Anthropic Claude API | 0.39+ |
| Email Parsing | BeautifulSoup4 + mail-parser-reply + quotequail | — |
| Phone Normalization | phonenumbers | 8.13+ |
| vCard Import | vobject | 0.9.6 |
| HTML Sanitization | bleach | 6.0 |

### 2.2 Frontend

| Component | Technology | Version |
|-----------|-----------|---------|
| Framework | React | 19.2 |
| Language | TypeScript | 5.9 |
| Build Tool | Vite | 7.3 |
| Styling | Tailwind CSS | 4.2 |
| State Management | Zustand | 5.0 |
| Data Fetching | @tanstack/react-query | 5.90 |
| Table Engine | @tanstack/react-table | 8.21 |
| Virtualization | @tanstack/react-virtual | 3.13 |
| Layout Panels | react-resizable-panels | 4.6 |
| Icons | lucide-react | 0.575 |
| Toasts | sonner | 2.0 |
| Date Utilities | date-fns | 4.1 |
| Forms | react-hook-form | 7.71 |
| Command Palette | cmdk | 1.1 |
| Keyboard Shortcuts | react-hotkeys-hook | 5.2 |

### 2.3 Google API Integration

| API | Scope | Purpose |
|-----|-------|---------|
| Gmail | gmail.readonly | Email thread sync, history tracking |
| People | contacts.readonly | Contact sync, group membership |
| Calendar | calendar.readonly | Event sync, attendee matching |
| OAuth 2.0 | openid, email, profile | User authentication |

---

## 3. Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    React SPA (/app/)                        │
│  ┌──────────┐  ┌───────────┐  ┌──────────┐  ┌───────────┐ │
│  │ Zustand   │  │ React     │  │ Grid     │  │ Search    │ │
│  │ Stores    │  │ Query     │  │ Intel    │  │ Parser    │ │
│  └─────┬────┘  └─────┬─────┘  └────┬─────┘  └─────┬─────┘ │
│        └──────────────┼─────────────┼──────────────┘       │
│                       │ /api/v1/*   │                       │
├───────────────────────┼─────────────┼───────────────────────┤
│                    FastAPI Backend                           │
│  ┌──────────┐  ┌─────┴─────┐  ┌────┴─────┐  ┌───────────┐ │
│  │ Auth     │  │ REST API  │  │ Views    │  │ HTMX      │ │
│  │ Middle-  │  │ Routes    │  │ Engine   │  │ Routes    │ │
│  │ ware     │  │ (JSON)    │  │          │  │ (HTML)    │ │
│  └────┬─────┘  └─────┬─────┘  └────┬─────┘  └─────┬─────┘ │
│       │              │              │               │       │
│  ┌────┴──────────────┴──────────────┴───────────────┴────┐  │
│  │              SQLite Database (WAL + FTS5)              │  │
│  │         56 tables · v17 schema · ~260 MB prod         │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                             │
│  ┌──────────┐  ┌───────────┐  ┌──────────┐  ┌───────────┐ │
│  │ Gmail    │  │ Calendar  │  │ Contacts │  │ Claude    │ │
│  │ Sync     │  │ Sync      │  │ Sync     │  │ AI        │ │
│  └──────────┘  └───────────┘  └──────────┘  └───────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### 3.1 Dual UI Architecture

The application serves two UIs from the same FastAPI instance:

1. **HTMX Web UI** (`/` routes) — Server-rendered Jinja2 templates with HTMX for progressive enhancement. Uses PicoCSS for styling. Full CRUD for all entity types.

2. **React SPA** (`/app/` route) — Modern single-page application served from `frontend/dist/`. Vite dev server on port 5173 proxies `/api/*` to FastAPI on port 8001 during development. Production builds are served by FastAPI with SPA fallback to `index.html`.

Both share the same backend, database, and authentication middleware.

---

## 4. Database Architecture

### 4.1 Overview

- **Engine:** SQLite 3.26+ with WAL mode, FK enforcement, FTS5
- **Schema Version:** v17 (56 tables)
- **Migration System:** 16 incremental Python scripts (`migrate_to_v2.py` through `migrate_to_v17.py`)
- **Multi-Tenancy:** `customer_id` FK on all data tables with ON DELETE CASCADE

### 4.2 Entity Model

```
customers ─┬── users ──── sessions
            │
            ├── contacts ──┬── contact_identifiers (email, phone, external ID)
            │              ├── contact_companies ──── contact_company_roles
            │              ├── contact_merges
            │              ├── email_addresses ┐
            │              ├── phone_numbers   ├── entity-agnostic sub-entities
            │              ├── addresses       ┘
            │              └── contact_social_profiles
            │
            ├── companies ─┬── company_identifiers
            │              ├── company_hierarchy
            │              ├── company_merges
            │              ├── company_social_profiles
            │              └── email_addresses / phone_numbers / addresses
            │
            ├── conversations ─┬── conversation_communications ── communications
            │                  ├── conversation_participants
            │                  ├── conversation_tags
            │                  └── conversation_shares
            │
            ├── communications ── communication_participants
            │
            ├── events ── event_participants
            │
            ├── projects ── topics
            │
            ├── relationships ── relationship_types
            │
            ├── notes ─┬── note_revisions
            │          ├── note_entities (multi-entity junction)
            │          ├── note_mentions
            │          ├── note_attachments
            │          └── notes_fts (FTS5 virtual table)
            │
            ├── views ─┬── view_columns
            │          ├── view_filters
            │          └── user_view_layout_overrides
            │
            ├── settings (4-level cascade)
            │
            ├── tags
            │
            └── enrichment_runs ── enrichment_field_values
                entity_scores
```

### 4.3 Key Schema Design Patterns

| Pattern | Description | Example |
|---------|-------------|---------|
| **Entity-Agnostic Sub-Entities** | Shared tables use `(entity_type, entity_id)` columns | `email_addresses`, `phone_numbers`, `addresses` |
| **Temporal Soft-Delete** | `is_current` flag + `started_at`/`ended_at` timestamps | `contact_identifiers`, `contact_companies` |
| **NULL-Safe Uniqueness** | COALESCE-based unique indexes for nullable columns | `idx_cc_dedup` on `contact_companies` |
| **Audit Trail** | `created_by`/`updated_by` user tracking | `contacts`, `conversations`, `notes` |
| **Append-Only Revisions** | Revision chain with incrementing numbers | `note_revisions`, `communication.previous_revision` |
| **Cascading FK Delete** | ON DELETE CASCADE for tenant cleanup | All `customer_id` foreign keys |
| **Case-Insensitive Sort** | `COLLATE NOCASE` on all text ORDER BY | Views engine, all hardcoded queries |

### 4.4 Migration System

Each migration is a standalone executable Python script following a consistent pattern:

1. Auto-backup: `db_path.v{N}-backup-{timestamp}.db`
2. Connection setup: WAL mode + FK enforcement
3. Pre-migration validation counts
4. Step-by-step DDL/DML execution
5. Post-migration verification
6. `--dry-run` and `--db PATH` CLI flags

**SQLite-specific safeguards:**
- `PRAGMA legacy_alter_table = ON` before any table renames (prevents FK auto-rewrite)
- COALESCE-based indexes for NULL-safe uniqueness (SQLite treats each NULL as distinct)
- WAL mode for concurrent read access during writes

---

## 5. Backend Architecture

### 5.1 Application Entry Points

| Entry Point | Command | Purpose |
|-------------|---------|---------|
| CLI | `python3 -m poc` | Sync, account management, batch operations |
| Web Server | `python3 -m poc serve [--port 8001]` | FastAPI web UI + REST API |

**CLI Subcommands:** `run` (sync all), `serve`, `add-account`, `list-accounts`, `remove-account`, `reauth`, `infer-relationships`, `auto-assign`, `resolve-domains`, `merge-companies`, `import-vcards`, `enrich-new-companies`

### 5.2 FastAPI Application

**App Factory:** `poc/web/app.py`
- Lifespan: `init_db()` on startup
- Static files: `/static/` from `poc/web/static/`
- Templates: Jinja2 from `poc/web/templates/`
- SPA: `/app/` serves `frontend/dist/` with fallback to `index.html`

**Middleware Stack:**
- `AuthMiddleware` — Session validation, auth bypass mode, Google OAuth
- Public paths: `/login`, `/register`, `/auth/google`, `/static/`, `/app/assets/`
- API auth: Returns 401 JSON for `/api/` paths; HTML routes redirect to `/login`

### 5.3 REST API Endpoints (`/api/v1/`)

**Entity Registry & Health:**
- `GET /health` — Status check
- `GET /entity-types` — Serialized registry (8 entity types with field definitions)

**Views CRUD:**
- `GET /views?entity_type={type}` — List views for entity type
- `GET /views/{id}` — View configuration (columns, filters, sort)
- `GET /views/{id}/data?page=&sort=&search=&filters=` — Paginated view data with `has_more`
- `POST /views` — Create view
- `PUT /views/{id}` — Update view settings
- `PUT /views/{id}/columns` — Update column order, widths, labels
- `PUT /views/{id}/filters` — Update saved filters
- `DELETE /views/{id}` — Delete view
- `POST /views/{id}/duplicate` — Duplicate view

**Layout Overrides (Adaptive Grid):**
- `GET /views/{id}/layout-overrides` — List per-user overrides
- `PUT /views/{id}/layout-overrides/{tier}` — Upsert override
- `DELETE /views/{id}/layout-overrides[/{tier}]` — Delete override(s)

**Entity CRUD:**
- `POST /contacts`, `POST /companies` — Create entities
- `GET /{entity-type}/{id}` — Entity detail (identity, context, timeline zones)

**Merge Operations:**
- `POST /contacts/merge-preview`, `POST /contacts/merge`
- `POST /companies/merge-preview`, `POST /companies/merge`

**Inline Editing:**
- `POST /cell-edit` — Update single cell with editable/select validation

**Search:**
- `GET /search?q={query}` — Cross-entity grouped search

### 5.4 Views Engine

**Location:** `poc/views/engine.py`

The views engine dynamically builds SQL queries from view configuration:

```
execute_view(entity_type, columns, filters, sort, search, pagination, visibility)
    │
    ├── 1. SELECT: Dynamic column expressions from FieldDef.sql
    ├── 2. FROM/JOIN: Entity base_joins + visibility joins
    ├── 3. WHERE: Visibility scoping + user filters + search + extra conditions
    ├── 4. GROUP BY: Prevents JOIN explosion (entity_def.group_by)
    ├── 5. ORDER BY: NULL-last + COLLATE NOCASE + sortable validation
    └── 6. LIMIT/OFFSET: Page-based pagination with total count
```

**Filter Operators (13):** `equals`, `not_equals`, `contains`, `not_contains`, `starts_with`, `gt`, `lt`, `gte`, `lte`, `is_before`, `is_after`, `is_empty`, `is_not_empty`

### 5.5 Entity Registry

**Location:** `poc/views/registry.py`

Defines 8 entity types with field metadata:

| Entity | Fields | Editable Fields | Search Fields |
|--------|--------|-----------------|---------------|
| Contact | 15 | name, source, status | name, company_name, email |
| Company | 21 | name, domain, industry, website, status, size_range, headquarters_location | name, domain, industry |
| Conversation | 22 | — | title, ai_summary |
| Communication | 24 | — | subject, sender_name, sender_address |
| Event | 18 | — | title, location |
| Project | 9 | — | name |
| Relationship | 13 | — | from_entity_name, to_entity_name |
| Note | 10 | — | title (+ FTS5) |

**Field Properties:** label, sql, type (text/number/datetime/select/hidden), sortable, filterable, link, editable, db_column, select_options

**Query Patterns:**
- Direct columns: Simple table column references (fast sort/filter)
- JOIN columns: References via base_joins (fast sort/filter)
- Correlated subqueries: Per-row subqueries for primary email, phone, address, counts (expensive sort)

### 5.6 Access Control

**Location:** `poc/access.py`

Per-entity visibility functions return `(WHERE_clause, [params])` tuples:

- **Contacts/Companies:** Public records + user's own records (via `user_contacts`/`user_companies` junction tables)
- **Conversations:** Access via provider_account ownership or explicit `conversation_shares`
- **Communications:** Access via provider_account ownership
- **Projects/Relationships/Notes:** Tenant-scoped (all users in customer see all)

Optional "mine" scope provides tighter filtering to user-owned records only.

---

## 6. Frontend Architecture

### 6.1 Application Shell

The React SPA uses a 3-panel resizable layout:

```
┌──────────────────────────────────────────────────────────┐
│                    TopHeaderBar (48px)                    │
├────┬─────────────┬──────────────────────┬────────────────┤
│    │             │                      │                │
│ I  │  Action     │    Content Area      │   Detail       │
│ c  │  Panel      │  ┌────────────────┐  │   Panel        │
│ o  │  (Views)    │  │  GridToolbar   │  │  (Record       │
│ n  │             │  ├────────────────┤  │   Preview)     │
│    │  - Personal │  │                │  │                │
│ R  │  - Shared   │  │   DataGrid     │  │  - Identity    │
│ a  │             │  │  (Virtualized  │  │  - Context     │
│ i  │             │  │   Infinite     │  │  - Timeline    │
│ l  │             │  │   Scroll)      │  │                │
│    │             │  │                │  │                │
│(60)│   (280px)   │  └────────────────┘  │   (480px)      │
├────┴─────────────┴──────────────────────┴────────────────┤
│                   Status Bar                              │
└──────────────────────────────────────────────────────────┘
```

**Layout powered by** `react-resizable-panels` v4 with localStorage persistence.

### 6.2 State Management (Zustand)

| Store | Key State | Persistence |
|-------|-----------|-------------|
| `navigation` | activeEntityType, activeViewId, selectedRowId, sort, search, quickFilters, searchFilters, focusedColumn, selection sets | Memory |
| `layout` | actionPanelVisible, detailPanelVisible, panel sizes, searchModalOpen | localStorage (`crm-layout`) |
| `gridDisplay` | density, fontSize, alternatingRows, gridlines, rowHover | localStorage (`crm-grid-display`) |
| `gridIntelligence` | computedLayout, saveAlignmentOverride function ref | Memory |

### 6.3 Data Fetching (React Query)

| Hook | Endpoint | Stale Time | Features |
|------|----------|------------|----------|
| `useEntityRegistry()` | `/entity-types` | 5 min | Field definitions, cached 30 min |
| `useViews(entityType)` | `/views` | 30s | Views list for entity |
| `useViewConfig(viewId)` | `/views/{id}` | 30s | Columns, filters, sort |
| `useInfiniteViewData()` | `/views/{id}/data` | 15s | Infinite scroll, `has_more` pagination |
| `useEntityDetail()` | `/{type}/{id}` | 30s | Identity/context/timeline zones |
| `useGlobalSearch()` | `/search` | 10s | Cross-entity grouped results |
| `useLayoutOverrides()` | `/views/{id}/layout-overrides` | 30s | Per-tier layout config |

**Mutation hooks** for view CRUD, cell editing, contact/company creation, and merge operations invalidate relevant query caches on success.

### 6.4 Grid System

**DataGrid Component** (~930 lines) — The core data display:

1. **TanStack React Table** — Headless table with dynamic column definitions
2. **TanStack React Virtual** — Virtualizes 10,000+ rows (34-50px row height)
3. **Infinite Scroll** — `useInfiniteQuery` with page-based loading and `has_more` signal
4. **Grid Intelligence** — 7-layer adaptive layout engine

**Selection Model:**
- Single click: Select row, show detail panel
- Shift+Click: Range selection
- Ctrl/Cmd+Click: Toggle multi-select
- Ctrl+A: Select all loaded rows
- Checkbox column for visual multi-select

**Inline Editing:**
- Double-click or `E` key on editable cells
- Text input or select dropdown based on field type
- Tab/Shift+Tab navigates between editable cells
- Enter/Blur saves, Escape cancels
- Green/red flash animation feedback

**Context Menus:**
- Row right-click: Entity-specific actions
- Column header click: Sort, filter, hide
- Toolbar menu: Bulk operations, export, merge

### 6.5 Adaptive Grid Intelligence

A 7-layer pipeline that computes optimal column layout:

```
Viewport → Display Profile → Content Analysis → Column Priority
    → Cell Alignment → Diversity Demotion → Column Allocation → Layout
```

| Layer | Module | Purpose |
|-------|--------|---------|
| 1 | `displayProfile.ts` | Viewport measurement, display tier classification |
| 2 | `contentAnalysis.ts` | Per-column metrics (max/median/p90 width, null ratio, diversity) |
| 3 | `columnPriority.ts` | Importance classification (Class 0-3) |
| 4 | `cellAlignment.ts` | L/C/R alignment by content type and width |
| 5 | `diversityDemotion.ts` | Hide low-value columns (normal → annotated → collapsed → header_only → hidden) |
| 6 | `columnAllocation.ts` | Distribute available width by priority and content needs |
| 7 | `layoutEngine.ts` | Orchestrate all layers, apply user overrides |

**Display Tiers:** ultra_wide (>=2400px), spacious (>=1920px), standard (>=1440px), constrained (>=1024px), minimal (<1024px)

**Content analysis** uses Canvas `measureText()` on the first 50 rows for stable width estimation.

### 6.6 Search System

**Global Search Modal** (Ctrl+K):
- Cross-entity grouped results from `/api/v1/search`
- Keyboard navigation: Arrow keys, Enter to select, Escape to close
- Result click navigates to entity type and selects row

**View-Scoped Search** (toolbar input):
- `searchParser.ts` parses field:value syntax into QuickFilter objects
- Supports: `status:active`, `revenue:>500000`, `created:this week`, `city:"New York"`
- Relative date resolution: today, yesterday, this/last/next week/month, last N days
- Autocomplete dropdown for field names, select options, and date keywords
- Free text passes through as backend LIKE search; field filters sent as structured JSON

### 6.7 Keyboard Navigation

| Key | Action |
|-----|--------|
| Arrow Down / `j` | Next row (shows detail) |
| Arrow Up / `k` | Previous row |
| Arrow Left / `h` | Previous column |
| Arrow Right / `l` | Next column |
| Space | Toggle row selection |
| `e` | Enter edit mode on focused cell |
| Tab / Shift+Tab | Next/prev editable cell |
| Enter | Save edit |
| Escape | Cancel edit |
| Ctrl+A | Select all loaded rows |
| Ctrl+K | Open global search |
| Page Down/Up | Jump 10 rows |

---

## 7. Sync Subsystems

### 7.1 Email Sync

**Flow:**
```
Register Account → fetch_threads() → parse MIME → store communications
    → build conversations → match contacts → resolve companies → AI summarize
```

- **Incremental sync** via Gmail History API (`history_id` cursor)
- **Rate limiting:** Configurable requests/sec (default 5)
- **Email history window:** 30d, 90d, 180d, 365d, 730d, or all
- **Company resolution:** Extract domain from sender email → look up or auto-create company → link affiliation
- **Public domain detection:** gmail.com, outlook.com, etc. skip company creation

### 7.2 Calendar Sync

**Flow:**
```
list_calendars() → fetch_events(sync_token) → parse events → match attendees → store
```

- **Incremental sync** via Calendar sync tokens (handles 410 Gone → full resync)
- **90-day window** for full sync
- **Attendee matching:** RSVP status tracking (accepted/declined/tentative)
- **Recurrence support:** RRULE parsing, recurring_event_id linking

### 7.3 Contact Sync

- Google People API for contact data
- vCard import for bulk contact creation
- Identity resolution via `contact_identifiers(type, value)` lookups
- Phone normalization to E.164 format via `phonenumbers` library

---

## 8. Authentication & Sessions

### 8.1 Auth Methods

| Method | Flow |
|--------|------|
| Password | bcrypt hash verification → create session |
| Google OAuth | OAuth 2.0 code flow → verify ID token → match by email or google_sub → create session |
| Bypass Mode | `CRM_AUTH_ENABLED=false` → auto-login as first active user |

### 8.2 Sessions

- Server-side sessions stored in `sessions` table
- Cookie: `crm_session` (HTTP-only)
- TTL: 720 hours (configurable via `SESSION_TTL_HOURS`)
- Cleanup: `cleanup_expired_sessions()` removes stale rows

### 8.3 Multi-Tenant Model

- `customers` table provides tenant isolation
- Default customer: `cust-default`
- User roles: `admin`, `user`
- All data queries scoped by `customer_id`

---

## 9. Settings System

**4-Level Cascade:**
```
User Setting (user_id + scope='user')
    → System Setting (scope='system')
        → Setting Default (setting_default column)
            → Hardcoded Fallback (_HARDCODED_DEFAULTS)
```

**Key Settings:**

| Setting | Type | Default | Scope |
|---------|------|---------|-------|
| timezone | string | UTC | user |
| email_history_window | string | 90d | user |
| company_name | string | — | system |
| sync_enabled | boolean | true | system |
| default_phone_country | string | US | system |
| allow_self_registration | boolean | false | system |

---

## 10. Configuration

### 10.1 Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `POC_DB_PATH` | `data/crm_extender.db` | SQLite database path |
| `CRM_AUTH_ENABLED` | `true` | Enable/disable authentication |
| `CRM_TIMEZONE` | `UTC` | Default display timezone |
| `SESSION_SECRET_KEY` | — | Session signing key |
| `SESSION_TTL_HOURS` | `720` | Session lifetime |
| `ANTHROPIC_API_KEY` | — | Claude API key |
| `POC_CLAUDE_MODEL` | `claude-sonnet-4-20250514` | AI model for summarization |
| `POC_GMAIL_QUERY` | `newer_than:7d` | Default Gmail sync query |
| `POC_GMAIL_MAX_THREADS` | `50` | Batch size for email sync |
| `POC_GMAIL_RATE_LIMIT` | `5` | Gmail API requests/sec |
| `POC_CLAUDE_RATE_LIMIT` | `2` | Claude API requests/sec |
| `CRM_UPLOAD_DIR` | — | File upload directory |
| `MAX_UPLOAD_SIZE_MB` | `10` | Upload size limit |

### 10.2 Google OAuth Setup

- Requires `credentials/client_secret.json` (Google Cloud Console)
- Per-account tokens stored at `credentials/token_{email}.json`
- Scopes: `gmail.readonly`, `contacts.readonly`, `calendar.readonly`

---

## 11. Testing

### 11.1 Framework

- **Framework:** pytest
- **Total Tests:** 1,514 (2 pre-existing Google mock failures)
- **Test Modules:** 40+

### 11.2 Fixture Pattern

```python
@pytest.fixture()
def tmp_db(tmp_path, monkeypatch):
    db_file = tmp_path / "test.db"
    monkeypatch.setattr("poc.config.DB_PATH", db_file)
    monkeypatch.setattr("poc.config.CRM_AUTH_ENABLED", False)
    init_db(db_file)
    # Insert test customer + user + visibility rows
    return db_file

@pytest.fixture()
def client(tmp_db, monkeypatch):
    monkeypatch.setattr("poc.hierarchy.get_current_user", lambda: {...})
    return TestClient(create_app(), raise_server_exceptions=False)
```

### 11.3 Test Coverage

- Authentication (bcrypt, Google OAuth, sessions)
- Access control and visibility scoping
- Contact/company merge with dedup
- Email parsing and sync
- Calendar sync with attendee matching
- Views engine: filtering, sorting, pagination
- Settings cascade
- Notes CRUD with FTS
- vCard import
- API endpoints (54 tests in `test_api.py`)
- Phone normalization
- Relationship inference

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
│   ├── migrate_to_v2.py … v17.py # Schema migrations
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
│           ├── contacts.py        # /contacts
│           ├── companies.py       # /companies
│           ├── conversations.py   # /conversations
│           ├── communications.py  # /communications
│           ├── events.py          # /events
│           ├── projects.py        # /projects
│           ├── relationships.py   # /relationships
│           ├── notes.py           # /notes
│           ├── views.py           # /views
│           ├── dashboard.py       # /
│           └── settings_routes.py # /settings
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
├── docs/                          # PRDs + user guide
└── pyproject.toml                 # Python dependencies
```

---

## 13. Performance Considerations

### 13.1 Frontend

| Optimization | Implementation |
|-------------|----------------|
| Row virtualization | @tanstack/react-virtual (10k+ rows) |
| Infinite scroll | Page-based lazy loading with `has_more` |
| Query caching | React Query with 15-30s stale times |
| Memoization | `useMemo`/`useCallback` on expensive computations |
| Intelligence sampling | Content analysis on first 50 rows only |
| Debouncing | Search (300ms), resize (250ms), column save (500ms) |
| Lazy detail loading | Detail panel fetches only on row selection |
| State persistence | localStorage for layout + display settings |

### 13.2 Backend

| Optimization | Implementation |
|-------------|----------------|
| WAL mode | Concurrent reads during writes |
| Compound indexes | Customer scoping + FK lookups on all tables |
| GROUP BY | Prevents JOIN explosion for multi-valued relations |
| NULL-last sorting | `ORDER BY (expr) IS NULL, expr COLLATE NOCASE` |
| Correlated subquery isolation | Primary email/phone as subqueries (avoids aggregation) |
| FTS5 external content | Full-text search without data duplication |
| Incremental sync | Gmail History API + Calendar sync tokens |

### 13.3 Sort Performance by Field Category

| Category | Example Fields | Sort Cost |
|----------|---------------|-----------|
| Direct columns | name, status, created_at | Negligible (indexed) |
| JOIN columns | company_name, relationship_type | Negligible (base_joins) |
| Correlated subqueries | email, phone, address, score, counts | Expensive (N subqueries) |

Subquery-backed fields are marked `sortable=False` to prevent per-row subquery evaluation during ORDER BY.

---

## 14. Production Data Profile

| Metric | Value |
|--------|-------|
| Database size | ~260 MB |
| Customers | 1 |
| Users | 1 (admin) |
| Provider accounts | 2 |
| Conversations | 3,409 |
| Contacts | 515 |
| Companies | 166 |
| Tags | 817 |
| Schema version | v17 |
| Migration backups | v1 through v14 |
