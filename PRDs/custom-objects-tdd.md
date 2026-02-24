# Custom Objects — TDD

**Version:** 1.0
**Last Updated:** 2026-02-23
**Status:** Draft
**Scope:** Framework
**Parent Document:** [custom-objects-framework-prd.md]
**Product TDD:** [product-tdd.md]

---

## 1. Overview

The Custom Objects framework requires framework-level technical decisions that go beyond the Product TDD and entity-specific TDDs. Key areas: physical storage architecture with dedicated tables per entity type, the DDL Management System that executes schema changes safely, the generic event sourcing pattern shared by all entities, schema-per-tenant isolation, and the unified API design.

---

## 2. Physical Storage Architecture

### 2.1 Dedicated Tables Per Entity Type

Every entity type — system and custom — gets its own PostgreSQL table with native typed columns:

```sql
-- System entity example
CREATE TABLE tenant_abc.contacts (
    id              TEXT PRIMARY KEY,          -- con_ prefixed ULID
    tenant_id       TEXT NOT NULL,
    -- Core system fields:
    first_name      TEXT,
    last_name       TEXT,
    display_name    TEXT NOT NULL,
    email_primary   TEXT,
    phone_primary   TEXT,
    -- ... additional system fields ...
    -- User-added custom fields:
    favorite_color  TEXT,                      -- Added by tenant
    renewal_date    DATE,                      -- Added by tenant
    -- Universal fields:
    created_by      TEXT NOT NULL,
    updated_by      TEXT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    archived_at     TIMESTAMPTZ
);

-- Custom entity example
CREATE TABLE tenant_abc.jobs (
    id              TEXT PRIMARY KEY,          -- job_ prefixed ULID
    tenant_id       TEXT NOT NULL,
    -- User-defined fields (all added via DDL):
    name            TEXT NOT NULL,             -- Display name field
    service_type    TEXT,
    price           NUMERIC,
    scheduled_date  DATE,
    -- Universal fields:
    created_by      TEXT NOT NULL,
    updated_by      TEXT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    archived_at     TIMESTAMPTZ
);
```

**Rationale:** Dedicated typed tables vs. EAV: maximum query performance, full PostgreSQL type safety, native indexing, simplest virtual-to-physical schema translation. Each entity type table averages 10–50 columns — well within PostgreSQL's comfort zone.

### 2.2 Index Strategy

Every entity type table gets baseline indexes:

```sql
-- Standard indexes (created by DDL system on table creation)
CREATE INDEX idx_{slug}_archived ON {slug} (archived_at) WHERE archived_at IS NULL;
CREATE INDEX idx_{slug}_tenant ON {slug} (tenant_id);
CREATE INDEX idx_{slug}_created ON {slug} (created_at);
CREATE INDEX idx_{slug}_updated ON {slug} (updated_at);
```

Additional indexes created by:
- **Unique constraints:** `is_unique` on a field creates a UNIQUE index
- **Relation FKs:** FK columns get indexed automatically
- **Entity-specific indexes:** System entity TDDs define specialized indexes (FTS, composite, partial)

### 2.3 Virtual Schema Mapping

The Data Sources PRD queries against a virtual schema derived from entity type field registries. The mapping is direct:

| Virtual Schema | Physical |
|---|---|
| Table name | Entity type slug (e.g., `jobs`, `contacts`) |
| Column name | Field slug (e.g., `service_type`, `price`) |
| Column type | PostgreSQL type from field type mapping |
| Available tables | All registered entity types for the tenant |

No translation layer needed — virtual schema IS the physical schema. The query engine validates column references against the field registry and passes SQL through to PostgreSQL.

---

## 3. DDL Management System

### 3.1 Operations Catalog

| Trigger | DDL Operation |
|---|---|
| Create entity type | CREATE TABLE (read model + event table) + baseline indexes |
| Add field | ALTER TABLE ADD COLUMN |
| Convert field type | ALTER TABLE ALTER COLUMN TYPE + data migration |
| Add unique constraint | CREATE UNIQUE INDEX |
| Remove unique constraint | DROP INDEX |
| Create M:M relation | CREATE TABLE (junction) + indexes |
| Add metadata field to relation | ALTER TABLE ADD COLUMN (on junction/instance table) |

### 3.2 Execution Model

1. **Validation:** Check constraints (field limit, slug uniqueness, type compatibility)
2. **Queue:** DDL operation enqueued with tenant_id, object_type_id, operation details
3. **Lock:** Advisory lock on (tenant_id, object_type_id) prevents concurrent DDL on same entity
4. **Execute:** DDL statement runs within a transaction
5. **Update metadata:** Field registry, schema version, relation type definitions updated
6. **Notify:** Dependent systems (Views, Data Sources) notified of schema change
7. **Audit:** DDL operation logged with actor, timestamp, details

### 3.3 Locking Strategy

- **Advisory locks** per (tenant_id, object_type_id) — not table-level locks
- Multiple tenants can DDL concurrently (different schemas)
- Same tenant can DDL different entity types concurrently
- Same entity type: serialized via advisory lock
- PostgreSQL 11+ instant ADD COLUMN: metadata-only operation, no table rewrite for most cases
- Type conversions require table rewrite — heavier operation, should warn user

### 3.4 Rollback

If DDL execution fails:
1. Transaction rolled back — physical schema unchanged
2. Metadata reverted — field registry, schema version unchanged
3. Error returned to user with details
4. Audit log records the failed attempt

---

## 4. Event Sourcing (Generic Pattern)

### 4.1 Event Table Structure

Every entity type has a companion event table following this pattern:

```sql
CREATE TABLE tenant_abc.{slug}_events (
    id              TEXT PRIMARY KEY,
    entity_id       TEXT NOT NULL,              -- FK → {slug}(id)
    event_type      TEXT NOT NULL,
    field_name      TEXT,                        -- NULL for non-field events
    old_value       JSONB,
    new_value       JSONB,
    metadata        JSONB,                       -- Additional context
    actor_id        TEXT,                         -- User or system ID
    actor_type      TEXT,                         -- 'user', 'system', 'ai', 'sync'
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_{slug}_ev_entity ON {slug}_events (entity_id, created_at);
CREATE INDEX idx_{slug}_ev_type ON {slug}_events (event_type);
```

### 4.2 Generic Event Types

All entity types share these base event types (entity-specific types added by their PRDs):

| Event Type | Description |
|---|---|
| `Created` | Record created. new_value = initial field values. |
| `FieldUpdated` | Field value changed. field_name, old_value, new_value. |
| `Archived` | Record soft-deleted. |
| `Unarchived` | Record restored. |
| `RelationLinked` | Relation instance created. metadata: relation_type_id, target_id. |
| `RelationUnlinked` | Relation instance removed. |
| `RelationMetadataUpdated` | Metadata on relation instance changed. |

### 4.3 Write Path

Every record mutation follows this path:

1. **Validate** input against field registry and validation rules
2. **Write event** to `{slug}_events` table (immutable append)
3. **Update read model** in `{slug}` table (current state)
4. Both writes in same transaction — atomic consistency
5. **Dispatch** to behavior handlers (system entities only)
6. **Async** post-commit: Neo4j sync, notification dispatch, cache invalidation

### 4.4 Point-in-Time Reconstruction

To reconstruct a record at a specific timestamp:

```sql
-- Get all events up to the target time
SELECT * FROM {slug}_events
WHERE entity_id = $id AND created_at <= $target_time
ORDER BY created_at ASC;
```

Apply events sequentially from `Created` event forward, applying each `FieldUpdated` to build the record state at that point. For performance, periodic **snapshots** can be stored to avoid full replay:

```sql
-- Snapshot table (optional optimization)
CREATE TABLE tenant_abc.{slug}_snapshots (
    id          TEXT PRIMARY KEY,
    entity_id   TEXT NOT NULL,
    snapshot_at TIMESTAMPTZ NOT NULL,
    record_data JSONB NOT NULL,              -- Full record state at this point
    event_id    TEXT NOT NULL                 -- Last event included in snapshot
);
```

Reconstruction then: find nearest snapshot before target time → apply events after snapshot → return state.

### 4.5 Audit Trail UI

The event history renders as a chronological timeline:

```
Feb 17, 2026 2:30 PM — Sam changed Status
  Estimated → Scheduled

Feb 17, 2026 10:00 AM — Sam set Scheduled Date
  (empty) → Feb 20, 2026

Feb 16, 2026 4:15 PM — Sam updated Price
  $200.00 → $250.00

Feb 16, 2026 3:00 PM — Sam created this Job
  Name: "Smith Residence Gutter Clean"
  Service Type: Full Clean
  Price: $200.00
```

---

## 5. Schema-Per-Tenant Architecture

### 5.1 Tenant Isolation Model

Each tenant gets its own PostgreSQL schema:

```
PostgreSQL Database: crmextender
  ├── Schema: platform                  (shared, cross-tenant)
  │     ├── object_types                (object type registry)
  │     ├── field_definitions           (field registry)
  │     ├── field_groups                (field grouping)
  │     ├── relation_types              (relation registry)
  │     ├── tenants                     (tenant registry)
  │     └── users                       (user registry)
  │
  ├── Schema: tenant_abc                (tenant-specific)
  │     ├── contacts                    (read model)
  │     ├── contacts_events             (event store)
  │     ├── companies                   (read model)
  │     ├── companies_events            (event store)
  │     ├── jobs                        (custom read model)
  │     ├── jobs_events                 (custom event store)
  │     ├── jobs__contacts_crew         (junction table)
  │     └── ...
  │
  ├── Schema: tenant_def                (another tenant)
  │     ├── contacts
  │     ├── contacts_events
  │     └── ... (different custom entities, different fields)
```

### 5.2 Tenant Schema Provisioning

On tenant creation:

1. CREATE SCHEMA tenant_{id}
2. Create system entity tables (contacts, companies, conversations, etc.) with all system fields
3. Create event tables for each system entity
4. Create system junction tables (project_conversations, etc.)
5. Create baseline indexes on all tables
6. Register system Relation Types for the tenant

On custom entity type creation (Section 3.1):

1. CREATE TABLE tenant_{id}.{slug} with universal fields + default name field
2. CREATE TABLE tenant_{id}.{slug}_events
3. Create baseline indexes

### 5.3 Search Path

Application sets `search_path` per request based on authenticated tenant:

```sql
SET search_path TO tenant_abc, platform;
```

This allows unqualified table references in queries (`SELECT * FROM contacts` resolves to `tenant_abc.contacts`) while platform tables (object_types, field_definitions) remain accessible.

---

## 6. API Design

### 6.1 Object Type Management

| Endpoint | Method | Description |
|---|---|---|
| `/api/v1/object-types` | GET | List all object types (system + custom) |
| `/api/v1/object-types` | POST | Create custom object type |
| `/api/v1/object-types/{slug}` | GET | Get definition with full field registry |
| `/api/v1/object-types/{slug}` | PATCH | Update metadata |
| `/api/v1/object-types/{slug}/archive` | POST | Archive custom type |
| `/api/v1/object-types/{slug}/unarchive` | POST | Unarchive |

### 6.2 Field Management

| Endpoint | Method | Description |
|---|---|---|
| `/api/v1/object-types/{slug}/fields` | GET | List all fields |
| `/api/v1/object-types/{slug}/fields` | POST | Add field (triggers DDL) |
| `/api/v1/object-types/{slug}/fields/{field_slug}` | GET | Get field definition |
| `/api/v1/object-types/{slug}/fields/{field_slug}` | PATCH | Update field metadata |
| `/api/v1/object-types/{slug}/fields/{field_slug}/convert` | POST | Convert type (with preview) |
| `/api/v1/object-types/{slug}/fields/{field_slug}/archive` | POST | Archive field |
| `/api/v1/object-types/{slug}/fields/{field_slug}/unarchive` | POST | Unarchive field |

### 6.3 Relation Type Management

| Endpoint | Method | Description |
|---|---|---|
| `/api/v1/relation-types` | GET | List all relation types |
| `/api/v1/relation-types` | POST | Create relation type (triggers DDL) |
| `/api/v1/relation-types/{id}` | GET | Get definition |
| `/api/v1/relation-types/{id}` | PATCH | Update metadata |
| `/api/v1/relation-types/{id}` | DELETE | Delete (removes fields) |

### 6.4 Record CRUD (Uniform Pattern)

| Endpoint | Method | Description |
|---|---|---|
| `/api/v1/{object_type_slug}` | GET | List records (paginated, filterable) |
| `/api/v1/{object_type_slug}` | POST | Create record |
| `/api/v1/{object_type_slug}/{id}` | GET | Get record |
| `/api/v1/{object_type_slug}/{id}` | PATCH | Update fields |
| `/api/v1/{object_type_slug}/{id}/archive` | POST | Archive |
| `/api/v1/{object_type_slug}/{id}/unarchive` | POST | Unarchive |
| `/api/v1/{object_type_slug}/{id}/history` | GET | Event history |
| `/api/v1/{object_type_slug}/{id}/history?at={ts}` | GET | Point-in-time state |

### 6.5 Relation Instance API

| Endpoint | Method | Description |
|---|---|---|
| `/api/v1/{slug}/{id}/relations/{rel_id}` | GET | List related records |
| `/api/v1/{slug}/{id}/relations/{rel_id}` | POST | Link record |
| `/api/v1/{slug}/{id}/relations/{rel_id}/{target_id}` | DELETE | Unlink record |
| `/api/v1/{slug}/{id}/relations/{rel_id}/{target_id}` | PATCH | Update metadata |

---

## 7. Decisions to Be Added by Claude Code

- **Snapshot frequency:** How often to create snapshots for point-in-time reconstruction.
- **DDL queue implementation:** In-database queue vs. message broker (Redis, RabbitMQ).
- **Neo4j sync implementation:** CDC-based, event-driven, or polling.
- **Schema migration versioning:** How to handle platform-level migrations that affect all tenant schemas (e.g., adding a new universal field).
- **Connection pooling per tenant:** Shared pool with search_path switching vs. per-tenant pools.
- **Event compaction:** Whether and how to compact old events into snapshots for storage efficiency.
