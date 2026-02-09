# Relationship Types PRD

## CRMExtender — Typed, Directional Relationship Model

**Version:** 1.0
**Date:** 2026-02-09
**Status:** Implemented (v4 schema)
**Parent Documents:** [CRMExtender PRD v1.1](PRD.md), [Data Layer PRD](data-layer-prd.md)

---

## Table of Contents

1. [Problem Statement](#1-problem-statement)
2. [Goals & Non-Goals](#2-goals--non-goals)
3. [Data Model](#3-data-model)
4. [Seed Types](#4-seed-types)
5. [Inference Engine](#5-inference-engine)
6. [Manual Relationships](#6-manual-relationships)
7. [CRUD API Surface](#7-crud-api-surface)
8. [Web UI](#8-web-ui)
9. [CLI Commands](#9-cli-commands)
10. [Migration Path](#10-migration-path)
11. [Design Decisions](#11-design-decisions)

---

## 1. Problem Statement

Prior to v4, the `relationships` table stored contact-to-contact pairs
with a free-text `relationship_type` column (always `"KNOWS"`).  This
created several problems:

- **No directionality** — "Alice employs Bob" and "Bob works at Alice's
  company" were indistinguishable from "Alice knows Bob".
- **No entity polymorphism** — relationships could only connect contacts,
  not companies to contacts or companies to companies.
- **No type catalog** — free-text strings meant no validation, no labels,
  and no way to enumerate or filter by type.
- **Inference-only** — all relationships were auto-inferred from
  conversation co-occurrence.  Users could not manually assert
  relationships like "reports to" or "partner of".
- **Unsafe re-inference** — running the inference engine deleted *all*
  existing relationships before re-inserting, destroying any manual
  additions.

---

## 2. Goals & Non-Goals

### Goals

1. **First-class relationship type definitions** — a `relationship_types`
   table that catalogs every valid type with directional labels.
2. **Entity polymorphism** — relationships can connect contact-to-contact,
   company-to-contact, or company-to-company, governed by the type
   definition.
3. **Directional labels** — each type carries a `forward_label` and
   `reverse_label` so the UI can display "Alice *employs* Bob" vs "Bob
   *works at* Alice's company".
4. **Source tracking** — every relationship records whether it was
   `inferred` (by the engine) or `manual` (by a user).
5. **Safe re-inference** — the engine deletes only `source='inferred'`
   rows, preserving all manual relationships.
6. **Seed types** — six built-in types ship with every new database,
   covering common CRM relationships.
7. **Custom types** — users can create, update, and delete their own
   relationship types via the web UI.
8. **System type protection** — the KNOWS type (used by inference) is
   marked `is_system=1` and cannot be deleted.

### Non-Goals

- **Graph database integration** — the PRD designs for future Neo4j
  sync but this implementation uses SQLite only.
- **Relationship inference for non-KNOWS types** — inference currently
  only produces KNOWS relationships.  Other types are manual-only.
- **Bulk import** — no CSV/API import of relationships in this version.
- **Relationship strength for manual types** — manual relationships do
  not carry strength scores or co-occurrence metrics.

---

## 3. Data Model

### 3.1 `relationship_types` Table

```sql
CREATE TABLE relationship_types (
    id               TEXT PRIMARY KEY,
    name             TEXT NOT NULL UNIQUE,
    from_entity_type TEXT NOT NULL DEFAULT 'contact',
    to_entity_type   TEXT NOT NULL DEFAULT 'contact',
    forward_label    TEXT NOT NULL,
    reverse_label    TEXT NOT NULL,
    is_system        INTEGER NOT NULL DEFAULT 0,
    description      TEXT,
    created_by       TEXT REFERENCES users(id) ON DELETE SET NULL,
    updated_by       TEXT REFERENCES users(id) ON DELETE SET NULL,
    created_at       TEXT NOT NULL,
    updated_at       TEXT NOT NULL,
    CHECK (from_entity_type IN ('contact', 'company')),
    CHECK (to_entity_type IN ('contact', 'company'))
);
```

Key constraints:
- `name` is UNIQUE — no two types can share the same name.
- `from_entity_type` and `to_entity_type` are restricted to `'contact'`
  or `'company'` via CHECK constraints.
- `is_system` marks types that cannot be deleted (only KNOWS in
  the seed set).

### 3.2 `relationships` Table (v4)

```sql
CREATE TABLE relationships (
    id                   TEXT PRIMARY KEY,
    relationship_type_id TEXT NOT NULL
        REFERENCES relationship_types(id) ON DELETE RESTRICT,
    from_entity_type     TEXT NOT NULL DEFAULT 'contact',
    from_entity_id       TEXT NOT NULL,
    to_entity_type       TEXT NOT NULL DEFAULT 'contact',
    to_entity_id         TEXT NOT NULL,
    source               TEXT NOT NULL DEFAULT 'manual',
    properties           TEXT,           -- JSON blob
    created_by           TEXT REFERENCES users(id) ON DELETE SET NULL,
    updated_by           TEXT REFERENCES users(id) ON DELETE SET NULL,
    created_at           TEXT NOT NULL,
    updated_at           TEXT NOT NULL,
    UNIQUE(from_entity_id, to_entity_id, relationship_type_id)
);
```

Key changes from v3:
- `relationship_type` (free text) replaced by `relationship_type_id` (FK
  to `relationship_types`).
- `ON DELETE RESTRICT` prevents deleting a type that has relationships
  referencing it.
- `source` column (`'inferred'` or `'manual'`) enables selective
  deletion during re-inference.
- `properties` is a JSON blob storing inference metrics (strength,
  shared_conversations, shared_messages, interaction dates).

### 3.3 Indexes

```sql
CREATE INDEX idx_relationships_from   ON relationships(from_entity_id);
CREATE INDEX idx_relationships_to     ON relationships(to_entity_id);
CREATE INDEX idx_relationships_type   ON relationships(relationship_type_id);
CREATE INDEX idx_relationships_source ON relationships(source);
```

### 3.4 Data Models (Python)

**`RelationshipType`** (`poc/models.py`):
- Fields: `name`, `from_entity_type`, `to_entity_type`, `forward_label`,
  `reverse_label`, `is_system`, `description`
- `to_row()` / `from_row()` for DB serialization

**`Relationship`** (`poc/models.py`):
- Fields: `from_entity_id`, `to_entity_id`, `relationship_type_id`,
  `from_entity_type`, `to_entity_type`, `source`, `strength`,
  `shared_conversations`, `shared_messages`, `last_interaction`,
  `first_interaction`
- Backward-compatible property aliases: `from_contact_id`,
  `to_contact_id`
- `properties` JSON contains: `strength`, `shared_conversations`,
  `shared_messages`, `last_interaction`, `first_interaction`

---

## 4. Seed Types

Six relationship types are seeded on database initialization and during
migration.  Their stable IDs are used as constants in the codebase.

| ID | Name | From | To | Forward Label | Reverse Label | System | Description |
|---|---|---|---|---|---|---|---|
| `rt-knows` | KNOWS | contact | contact | Knows | Knows | Yes | Auto-inferred co-occurrence |
| `rt-employee` | EMPLOYEE | company | contact | Employs | Works at | No | Employment relationship |
| `rt-reports-to` | REPORTS_TO | contact | contact | Has direct report | Reports to | No | Reporting chain |
| `rt-works-with` | WORKS_WITH | contact | contact | Works with | Works with | No | Peer / collaborator |
| `rt-partner` | PARTNER | company | company | Partners with | Partners with | No | Business partnership |
| `rt-vendor` | VENDOR | company | company | Is a vendor of | Is a client of | No | Vendor / client relationship |

The KNOWS type is the only system type (`is_system=1`).  It is used
exclusively by the inference engine.  All other seed types are
user-deletable (provided they have no relationships referencing them).

---

## 5. Inference Engine

The inference engine (`poc/relationship_inference.py`) mines
`conversation_participants` for contact co-occurrence and produces
KNOWS relationships.

### 5.1 Algorithm

1. **Co-occurrence query** — joins `conversation_participants` on
   matching `conversation_id` with `contact_a < contact_b` to produce
   unique pairs.  Aggregates `shared_conversations`, `shared_messages`,
   `last_interaction`, and `first_interaction`.

2. **Canonical deduplication** — contacts sharing the same name are
   mapped to a canonical ID (the one with the most participant records).
   This prevents the same real person using multiple email addresses
   from creating duplicate or self-referencing relationships.

3. **Strength scoring** — each pair is scored on a 0.0 - 1.0 scale:
   - 40% conversation co-occurrence (log-scaled)
   - 30% shared message volume (log-scaled)
   - 30% recency of last interaction (linear decay from 1.0 at 30 days
     to 0.1 at 365+ days)

4. **Source-filtered delete** — before upserting new rows, the engine
   runs `DELETE FROM relationships WHERE source = 'inferred'`.  This
   removes only machine-generated relationships, preserving all
   `source='manual'` rows.

5. **Upsert** — each pair is inserted with `ON CONFLICT(from_entity_id,
   to_entity_id, relationship_type_id) DO UPDATE SET properties = ...,
   updated_at = ...`.

### 5.2 Key Constant

```python
KNOWS_TYPE_ID = "rt-knows"
```

All inferred relationships use this type ID.

### 5.3 Load Function

`load_relationships()` supports filtering by:
- `contact_id` — matches either side (resolved to canonical ID)
- `min_strength` — post-query filter on parsed properties
- `relationship_type_id` — filter by type
- `source` — filter by `'inferred'` or `'manual'`

Results are JOINed with `relationship_types` to include type name and
labels.

---

## 6. Manual Relationships

Users can create and delete manual relationships through the web UI.

- **Source** is always `'manual'` for user-created relationships.
- **Entity type matching** — the relationship type's `from_entity_type`
  and `to_entity_type` determine what the "from" and "to" entities
  represent.
- **Delete protection** — only `source='manual'` relationships can be
  deleted through the web UI.  Inferred relationships are managed
  exclusively by the inference engine.
- **No properties** — manual relationships do not carry strength or
  co-occurrence metrics.  The `properties` column is NULL.

---

## 7. CRUD API Surface

### 7.1 Relationship Types (`poc/relationship_types.py`)

| Function | Signature | Description |
|---|---|---|
| `create_relationship_type` | `(name, from_entity_type, to_entity_type, forward_label, reverse_label, *, description, created_by) -> dict` | Create a new type. Raises `ValueError` on duplicate name or invalid entity type. |
| `list_relationship_types` | `(*, from_entity_type, to_entity_type) -> list[dict]` | List types, optionally filtered by entity types. Ordered by name. |
| `get_relationship_type` | `(type_id) -> dict or None` | Get a type by ID. |
| `get_relationship_type_by_name` | `(name) -> dict or None` | Get a type by name. |
| `update_relationship_type` | `(type_id, *, forward_label, reverse_label, description, updated_by) -> dict or None` | Update labels/description. Returns None if not found. |
| `delete_relationship_type` | `(type_id) -> None` | Delete a type. Raises `ValueError` if system type or in use. |

### 7.2 Relationships (`poc/relationship_inference.py`)

| Function | Signature | Description |
|---|---|---|
| `infer_relationships` | `() -> int` | Run full inference pipeline. Returns count of upserted relationships. |
| `load_relationships` | `(*, contact_id, min_strength, relationship_type_id, source) -> list[Relationship]` | Load and filter relationships with type info. |

---

## 8. Web UI

### 8.1 Relationship Browser (`/relationships`)

- **Filters** — type (dropdown of all relationship types), source
  (`inferred` / `manual`), minimum strength slider, contact ID.
- **Results table** — shows from-entity name, directional label,
  to-entity name, type, source, strength, shared conversations/messages.
- **HTMX search** — filters trigger an HTMX request to
  `/relationships/search` which returns a partial `_rows.html` template.
- **Create form** — allows selecting a type, from-entity, and to-entity
  to create a manual relationship.
- **Delete** — manual relationships show a delete button that sends
  `DELETE /relationships/{id}`.  Inferred relationships cannot be
  deleted through the UI.
- **Infer button** — triggers `POST /relationships/infer` to re-run the
  inference engine.

### 8.2 Type Admin (`/relationships/types`)

- **List view** — displays all relationship types with name, entity types,
  labels, system flag, and description.
- **Create form** — name, from_entity_type (contact/company),
  to_entity_type (contact/company), forward_label, reverse_label,
  description.
- **Delete** — non-system types with no relationships can be deleted via
  `DELETE /relationships/types/{id}`.  System types and in-use types
  show an appropriate error.

### 8.3 Routes

| Method | Path | Handler | Description |
|---|---|---|---|
| GET | `/relationships` | `relationship_list` | Main browser page |
| GET | `/relationships/search` | `relationship_search` | HTMX partial (filtered rows) |
| POST | `/relationships/infer` | `relationship_infer` | Trigger inference engine |
| POST | `/relationships` | `relationship_create` | Create manual relationship |
| DELETE | `/relationships/{id}` | `relationship_delete` | Delete manual relationship |
| GET | `/relationships/types` | `relationship_type_list` | Type admin page |
| POST | `/relationships/types` | `relationship_type_create` | Create custom type |
| DELETE | `/relationships/types/{id}` | `relationship_type_delete` | Delete custom type |

---

## 9. CLI Commands

### `list-relationship-types`

```bash
python3 -m poc list-relationship-types
```

Displays a table of all relationship types: name, from/to entity types,
forward/reverse labels, and system flag.

### `infer-relationships`

```bash
python3 -m poc infer-relationships
```

Runs the inference engine.  Deletes existing inferred relationships,
mines conversation co-occurrence, and upserts new KNOWS relationships.
Reports the count of relationships upserted.

### `show-relationships`

```bash
python3 -m poc show-relationships [--contact EMAIL] [--min-strength 0.0-1.0]
```

Displays relationships in a formatted table.  Options:
- `--contact EMAIL` — filter to relationships involving a specific
  contact (resolved via `contact_identifiers`).
- `--min-strength FLOAT` — only show relationships above this strength
  threshold.

### `migrate-to-v4`

```bash
python3 -m poc migrate-to-v4 [--db PATH] [--dry-run]
```

Migrates a v3 database to v4 schema.  See [Migration Path](#10-migration-path).

---

## 10. Migration Path

The v3 to v4 migration (`poc/migrate_to_v4.py`) performs five steps:

1. **Backup** — copies the database to
   `{name}.v3-backup-{timestamp}.db`.

2. **Create `relationship_types`** — creates the table if it does not
   exist.

3. **Seed types** — inserts the six seed types using `INSERT OR IGNORE`.

4. **Rebuild `relationships`** — creates `relationships_new` with the
   v4 schema, copies existing rows mapping `relationship_type='KNOWS'`
   to `relationship_type_id='rt-knows'` and `source='inferred'`, then
   swaps the tables.  If the table already has a `relationship_type_id`
   column, this step is skipped.

5. **Create indexes and validate** — creates four indexes, re-enables
   foreign keys, runs `PRAGMA foreign_key_check`, and verifies row
   counts match pre-migration.

The `--dry-run` flag applies the migration to the backup copy instead
of the production database.

---

## 11. Design Decisions

### Why FK to `relationship_types` instead of free-text enum?

A dedicated table enables the UI to enumerate available types, enforces
referential integrity at the database level, and allows users to define
custom types without code changes.  `ON DELETE RESTRICT` prevents
orphaned relationships.

### Why `source` column instead of separate tables?

A single `relationships` table with a `source` discriminator is simpler
than maintaining parallel `inferred_relationships` and
`manual_relationships` tables.  The discriminator enables the inference
engine to selectively delete its own rows with a single
`DELETE ... WHERE source = 'inferred'`.

### Why stable string IDs for seed types?

Using predictable IDs like `rt-knows` instead of UUIDs allows the
inference engine to reference `KNOWS_TYPE_ID = "rt-knows"` as a constant
without querying the database.  The `INSERT OR IGNORE` seed logic is
idempotent.

### Why `properties` JSON instead of dedicated columns?

Different relationship types may carry different metadata.  Inferred
KNOWS relationships have strength scores and co-occurrence metrics;
manual EMPLOYEE relationships might later have start/end dates.  A JSON
blob provides flexibility without requiring schema changes.

### Why `ON DELETE RESTRICT` on `relationship_type_id`?

Prevents accidentally deleting a type that has active relationships.
The `delete_relationship_type()` function checks for in-use types and
returns a clear error message.
