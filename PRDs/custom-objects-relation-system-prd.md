# Custom Objects — Relation System Sub-PRD

**Version:** 1.0
**Last Updated:** 2026-02-23
**Status:** Draft
**Framework PRD:** [custom-objects-framework-prd.md]

---

## 1. Overview

### 1.1 Purpose

This sub-PRD defines the relation system: how connections between entity types are defined, stored, traversed, and synced to Neo4j. Relation Types are first-class objects with cardinality, directionality, cascade behavior, optional metadata attributes, and optional graph database sync. They work between any combination of entity types, including self-referential.

### 1.2 Preconditions

- Object Type framework operational with entity types registered.
- DDL Management System operational (junction tables, FK columns).
- Field registry operational (relation fields created on entity types).
- Neo4j available (for graph sync — can be deferred to later phase).

---

## 2. Relation Type Definition Model

### 2.1 Attributes

| Attribute | Type | Description |
|---|---|---|
| `id` | TEXT, PK | `rel_` prefixed ULID |
| `tenant_id` | TEXT | Owning tenant |
| `name` | TEXT | Human-readable name (e.g., "Employment", "Assignment") |
| `description` | TEXT | Optional description |
| `source_object_type_id` | TEXT, FK | The "from" entity type |
| `target_object_type_id` | TEXT, FK | The "to" entity type (can equal source for self-referential) |
| `cardinality` | TEXT | `one_to_one`, `one_to_many`, `many_to_many` |
| `directionality` | TEXT | `bidirectional` or `unidirectional` |
| `source_field_label` | TEXT | Display name on source entity (e.g., "Customer") |
| `target_field_label` | TEXT | Display name on target entity. Required if bidirectional; NULL if unidirectional. |
| `cascade_behavior` | TEXT | `nullify` (default), `restrict`, `cascade_archive` |
| `has_metadata` | BOOLEAN | Whether relation instances carry additional attributes |
| `metadata_fields` | JSONB | If has_metadata, field definitions for metadata |
| `neo4j_sync` | BOOLEAN, DEFAULT false | Whether instances sync to Neo4j as edges |
| `neo4j_edge_type` | TEXT | Neo4j edge type label (e.g., "WORKS_AT", "REPORTS_TO") |
| `is_system` | BOOLEAN | Core platform relation |
| `created_at` | TIMESTAMPTZ | |
| `updated_at` | TIMESTAMPTZ | |

---

## 3. Cardinality & Physical Implementation

### 3.1 Storage Patterns

| Cardinality | Source Side | Target Side | Physical Storage |
|---|---|---|---|
| One-to-one | Relation (single) field | Inverse single field (if bidirectional) | FK column on source table, UNIQUE constraint |
| One-to-many | Relation (single) on "many" side | Relation (multi) inverse on "one" side | FK column on "many" side table |
| Many-to-many | Relation (multi) field | Relation (multi) inverse (if bidirectional) | Junction table: `{source_slug}__{target_slug}` |

### 3.2 Junction Table Structure

```sql
CREATE TABLE tenant_abc.jobs__contacts_crew (
    id          TEXT PRIMARY KEY,       -- rel instance ID for metadata
    source_id   TEXT NOT NULL,          -- FK → jobs(id)
    target_id   TEXT NOT NULL,          -- FK → contacts(id)
    -- Metadata columns (if has_metadata = true):
    role        TEXT,
    assigned_date DATE,
    notes       TEXT,
    -- Universal:
    created_at  TIMESTAMPTZ NOT NULL,
    created_by  TEXT,
    UNIQUE (source_id, target_id)
);
```

**Tasks:**

- [ ] CORS-01: Implement Relation Type definition model with all attributes
- [ ] CORS-02: Implement one-to-one physical storage (FK + UNIQUE)
- [ ] CORS-03: Implement one-to-many physical storage (FK column)
- [ ] CORS-04: Implement many-to-many physical storage (junction table)
- [ ] CORS-05: Implement junction table DDL generation with naming convention

**Tests:**

- [ ] CORS-T01: Test one-to-one creates FK column with UNIQUE constraint
- [ ] CORS-T02: Test one-to-many creates FK column without UNIQUE
- [ ] CORS-T03: Test many-to-many creates junction table
- [ ] CORS-T04: Test junction table UNIQUE prevents duplicate links
- [ ] CORS-T05: Test junction table naming follows convention

---

## 4. Directionality

### 4.1 Bidirectional

- Relation field created on BOTH source and target entity types
- Source field shows target records; target field shows source records
- Both fields navigable in views (relation traversal works either direction)
- Data Sources can JOIN from either side
- Deleting the relation type removes both fields

### 4.2 Unidirectional

- Relation field created ONLY on source entity type
- Target has no auto-created inverse field
- Views traverse only source → target
- Data Sources JOIN only source → target
- Use case: Communication references Conversation (Conversation handles its own display via Activity Card)

**Tasks:**

- [ ] CORS-06: Implement bidirectional relation field creation (both sides)
- [ ] CORS-07: Implement unidirectional relation field creation (source only)
- [ ] CORS-08: Implement relation type deletion (removes fields from both sides)

**Tests:**

- [ ] CORS-T06: Test bidirectional creates fields on both entity types
- [ ] CORS-T07: Test unidirectional creates field on source only
- [ ] CORS-T08: Test relation type deletion removes all associated fields

---

## 5. Self-Referential Relations

When source_object_type_id equals target_object_type_id, the relation is self-referential. Both labels must be provided and distinct (to differentiate sides on the same entity's detail view).

### 5.1 Example: Contact Reporting Structure

```
Relation Type: "Reporting Structure"
  Source: Contact          Target: Contact
  Cardinality: many_to_one
  Directionality: bidirectional
  Source Label: "Reports To"      (shows the manager — single)
  Target Label: "Direct Reports"  (shows subordinates — multi)
  Neo4j Sync: true
  Neo4j Edge Type: "REPORTS_TO"
```

On a Contact's Detail Panel:
- "Reports To" — single Contact (the manager)
- "Direct Reports" — multiple Contacts (subordinates)

Other self-referential examples: Project hierarchy (parent/children), Task subtasks (parent/subtasks), Company subsidiaries (parent/subsidiaries).

**Tasks:**

- [ ] CORS-09: Implement self-referential relation type validation
- [ ] CORS-10: Implement distinct label enforcement for self-referential

**Tests:**

- [ ] CORS-T09: Test self-referential relation creates both fields on same entity
- [ ] CORS-T10: Test self-referential requires distinct source/target labels
- [ ] CORS-T11: Test self-referential FK or junction works correctly

---

## 6. Cascade Behavior

| Behavior | When target archived... | Use Case |
|---|---|---|
| **Nullify** (default) | Source relation field set to NULL. Junction rows soft-deleted. | Contact archived → Jobs' "Customer" field becomes empty |
| **Restrict** | Archive blocked with error listing referencing records. | Cannot archive Property with active Jobs |
| **Cascade archive** | All referencing source records also archived. | Archive Company → archive subsidiary Companies |

**Tasks:**

- [ ] CORS-11: Implement nullify cascade (clear FK, soft-delete junction rows)
- [ ] CORS-12: Implement restrict cascade (block with referencing record list)
- [ ] CORS-13: Implement cascade_archive (recursive archive of referencing records)

**Tests:**

- [ ] CORS-T12: Test nullify clears FK on source when target archived
- [ ] CORS-T13: Test nullify soft-deletes junction rows when target archived
- [ ] CORS-T14: Test restrict blocks archive when referencing records exist
- [ ] CORS-T15: Test cascade_archive archives all referencing records
- [ ] CORS-T16: Test cascade_archive works recursively (chain archive)

---

## 7. Relation Metadata

When `has_metadata = true`, each relationship instance carries additional attributes beyond the link.

### 7.1 Supported Metadata Field Types

| Type | Rationale |
|---|---|
| Text (single-line) | Labels, notes |
| Text (multi-line) | Longer descriptions |
| Number | Scores, ratings |
| Currency | Financial attributes |
| Date | Start/end dates |
| Datetime | Precise timestamps |
| Select (single) | Roles, categories |
| Checkbox | Flags |
| Rating | Strength scores |
| Duration | Time measurements |

Relation, Formula, Rollup, and User fields NOT supported as metadata (prevents recursive complexity).

### 7.2 Storage

**Many-to-many:** Metadata columns on the junction table. Adding a metadata field triggers ALTER TABLE ADD COLUMN on junction.

**One-to-one / One-to-many with metadata:** Companion `relation_instances` table:

```sql
CREATE TABLE tenant_abc.rel_job_customer_instances (
    id          TEXT PRIMARY KEY,
    source_id   TEXT NOT NULL,       -- FK → jobs(id)
    target_id   TEXT NOT NULL,       -- FK → contacts(id)
    -- Metadata columns:
    referral_source TEXT,
    satisfaction_rating INTEGER,
    -- Universal:
    created_at  TIMESTAMPTZ NOT NULL,
    created_by  TEXT,
    UNIQUE (source_id)               -- enforces 1:many cardinality
);
```

FK column on source table retained for query performance (basic traversal doesn't need instance table).

### 7.3 Metadata in Views

Relation metadata fields accessible as lookup columns in views:

```
Add Column
├── Direct Fields
│     ├── Name, Price, ...
└── Related Entity Fields
      └── Customer (→Contact)
            ├── Contact Name, Email, ...
            └── [Relation Metadata]
                  ├── Referral Source
                  └── Satisfaction Rating
```

### 7.4 Event Sourcing for Metadata

Metadata changes recorded in the source entity's event table with event_type = `RelationMetadataUpdated`. Metadata includes: relation_type_id, target_id, field_name, old_value, new_value.

**Tasks:**

- [ ] CORS-14: Implement metadata field definitions on relation types
- [ ] CORS-15: Implement metadata columns on junction tables (M:M)
- [ ] CORS-16: Implement companion instance tables for 1:1/1:M with metadata
- [ ] CORS-17: Implement metadata field ALTER TABLE ADD COLUMN on junction/instance
- [ ] CORS-18: Implement metadata in Views as lookup columns
- [ ] CORS-19: Implement RelationMetadataUpdated event sourcing

**Tests:**

- [ ] CORS-T17: Test metadata columns added to junction table
- [ ] CORS-T18: Test companion instance table created for 1:M with metadata
- [ ] CORS-T19: Test metadata values stored and retrieved correctly
- [ ] CORS-T20: Test metadata changes emit RelationMetadataUpdated events
- [ ] CORS-T21: Test metadata accessible as lookup columns in Views

---

## 8. Neo4j Graph Sync

### 8.1 Sync Model

When `neo4j_sync = true` on a Relation Type, relation instances are synced to Neo4j as graph edges:

- **Nodes:** Entity records synced as Neo4j nodes. Node label = entity type slug. Properties = display name + configurable field subset.
- **Edges:** Relation instances synced as Neo4j edges. Edge type = `neo4j_edge_type`. Properties = metadata fields (if any).
- **Sync trigger:** On relation instance create/update/delete, async sync to Neo4j.
- **Consistency:** Eventual consistency. PostgreSQL is source of truth. Neo4j is a read-optimized projection.

### 8.2 Graph-Enabled Queries

Neo4j enables queries not practical in SQL:
- "Find all contacts within 3 degrees of separation from Contact X"
- "Find shortest path between Company A and Company B through shared contacts"
- "Find all entities connected to Project X through any relation chain"
- Relationship intelligence scoring based on graph centrality, cluster detection

### 8.3 Phasing

- **Phase 2:** Neo4j sync for system Relation Types (Contact→Company, Project→Contact, etc.)
- **Phase 3:** Neo4j sync for custom Relation Types. Graph-enabled queries in Data Sources.

**Tasks:**

- [ ] CORS-20: Implement Neo4j node sync for entity records
- [ ] CORS-21: Implement Neo4j edge sync for relation instances
- [ ] CORS-22: Implement async sync trigger on relation create/update/delete
- [ ] CORS-23: Implement configurable field subset for node properties
- [ ] CORS-24: Implement graph-enabled query interface

**Tests:**

- [ ] CORS-T22: Test relation instance creates Neo4j edge
- [ ] CORS-T23: Test relation deletion removes Neo4j edge
- [ ] CORS-T24: Test metadata fields sync as edge properties
- [ ] CORS-T25: Test async sync handles high-volume creates
- [ ] CORS-T26: Test multi-hop graph query returns correct paths
