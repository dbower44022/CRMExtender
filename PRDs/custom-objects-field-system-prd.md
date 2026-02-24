# Custom Objects — Field System Sub-PRD

**Version:** 1.0
**Last Updated:** 2026-02-23
**Status:** Draft
**Framework PRD:** [custom-objects-framework-prd.md]

---

## 1. Overview

### 1.1 Purpose

This sub-PRD defines the complete field system: how fields are defined, typed, validated, grouped, converted, and managed through their lifecycle. The field registry is the authoritative source for what data an entity type captures. Every other subsystem — Views, Data Sources, event sourcing — derives its understanding of entity structure from the field registry.

### 1.2 Preconditions

- Object Type framework operational (types can be created and registered).
- DDL Management System operational (field additions trigger ALTER TABLE).
- Schema-per-tenant provisioned.

---

## 2. Field Registry

### 2.1 Field Definition Model

| Attribute | Type | Constraints | Description |
|---|---|---|---|
| `id` | TEXT | PK | `fld_` prefixed ULID. Immutable. |
| `object_type_id` | TEXT | FK → object_types | Entity type this field belongs to |
| `slug` | TEXT | NOT NULL, UNIQUE per object type | Machine name, immutable. Maps to physical column name. |
| `display_name` | TEXT | NOT NULL | User-facing label, renamable. |
| `description` | TEXT | | Optional help text for forms and tooltips |
| `field_type` | TEXT | NOT NULL | Registered field type (see Section 3). Immutable except safe conversions. |
| `field_type_config` | JSONB | | Type-specific configuration |
| `is_required` | BOOLEAN | DEFAULT false | Value must be provided on create/update |
| `default_value` | TEXT | | Default for new records (string, parsed by type) |
| `validation_rules` | JSONB | | Type-specific constraints (see Section 6) |
| `display_order` | INTEGER | NOT NULL | Position in field registry ordering |
| `field_group_id` | TEXT | FK → field_groups | Optional grouping for Detail Panel layout |
| `is_system` | BOOLEAN | DEFAULT false | Core field of system entity type (protected) |
| `is_archived` | BOOLEAN | DEFAULT false | Soft-delete. Hidden from UI, column preserved. |
| `created_at` | TIMESTAMPTZ | NOT NULL | |
| `updated_at` | TIMESTAMPTZ | NOT NULL | |

### 2.2 Slug-to-Column Mapping

The field slug IS the physical column name. This 1:1 mapping eliminates translation overhead:
- Field slug: `service_type` → Column: `service_type`
- Field slug: `price` → Column: `price`

Slugs are validated against PostgreSQL reserved words and generated from the display name (lowercased, spaces to underscores, special chars removed).

### 2.3 Field Ordering

`display_order` determines the default layout sequence in the Detail Panel and the default column order in Grid views. Users can override column order per-view, but `display_order` sets the baseline.

### 2.4 Field Limits

Each object type supports up to **200 user-defined fields** (configurable via `field_limit`). Universal fields (id, tenant_id, etc.) do not count against this limit. Archived fields do not count against the limit.

---

## 3. Field Type System

### 3.1 Phase 1 Field Types

| Field Type | PostgreSQL Type | Description |
|---|---|---|
| `text_single` | TEXT | Single-line text |
| `text_multi` | TEXT | Multi-line text (textarea) |
| `number` | NUMERIC | Numeric with configurable decimal places |
| `currency` | NUMERIC | Numeric with currency code, symbol, decimal places |
| `date` | DATE | Calendar date |
| `datetime` | TIMESTAMPTZ | Date with time and timezone |
| `select` | TEXT | Single-select from defined options |
| `multi_select` | TEXT[] | Multi-select from defined options (PostgreSQL array) |
| `checkbox` | BOOLEAN | True/false toggle |
| `relation` | TEXT | FK to another entity's ID |
| `email` | TEXT | Email with format validation |
| `phone` | TEXT | Phone with E.164 format validation |
| `url` | TEXT | URL with format validation |

### 3.2 Phase 2 Field Types

| Field Type | PostgreSQL Type | Description |
|---|---|---|
| `rating` | INTEGER | Star rating (configurable min/max) |
| `duration` | INTEGER | Duration in seconds |
| `formula` | — (computed) | Calculated from other fields. Read-only. |
| `rollup` | — (computed) | Aggregation across relation. Read-only. |
| `user` | TEXT | FK to platform.users. For "assigned to" style fields. |

### 3.3 Type Configuration Examples

**Number:**
```json
{ "decimal_places": 2, "display_format": "comma_separated" }
```

**Currency:**
```json
{ "currency_code": "USD", "symbol": "$", "decimal_places": 2 }
```

**Select:**
```json
{
  "options": [
    { "slug": "full_clean", "label": "Full Clean", "color": "#3B82F6", "order": 1 },
    { "slug": "partial", "label": "Partial", "color": "#EAB308", "order": 2 },
    { "slug": "repair", "label": "Repair Only", "color": "#EF4444", "order": 3 }
  ]
}
```

**Relation:**
```json
{ "target_object_type_id": "oty_01HX7...", "relation_type_id": "rel_01HX7..." }
```

**Rating:**
```json
{ "min_value": 1, "max_value": 5, "icon": "star" }
```

**Duration:**
```json
{ "display_format": "hh:mm", "input_unit": "minutes" }
```

**Tasks:**

- [ ] COFS-01: Implement field definition model with all attributes
- [ ] COFS-02: Implement slug generation from display name with reserved word validation
- [ ] COFS-03: Implement field_type_config validation per type
- [ ] COFS-04: Implement Phase 1 field types (13 types)
- [ ] COFS-05: Implement Phase 2 field types (5 types)
- [ ] COFS-06: Implement display_order management with reordering

**Tests:**

- [ ] COFS-T01: Test slug uniqueness enforced within object type
- [ ] COFS-T02: Test reserved word rejection in slug generation
- [ ] COFS-T03: Test field_type_config validated per type
- [ ] COFS-T04: Test each Phase 1 field type stores and retrieves correctly
- [ ] COFS-T05: Test display_order maintained on reorder
- [ ] COFS-T06: Test field limit enforced (reject at 200)

---

## 4. Field Type Conversion Matrix

### 4.1 Safe Conversions

Only lossless or minimally-lossy conversions are permitted:

| From → To | Conversion |
|---|---|
| Text → Number | Parse numeric values. Non-numeric → NULL. |
| Text → Email | Validate format. Invalid → NULL. |
| Text → URL | Validate format. Invalid → NULL. |
| Text → Phone | Validate E.164. Invalid → NULL. |
| Number → Text | Stringify. Lossless. |
| Number → Currency | Add currency metadata. Lossless. |
| Currency → Number | Strip currency metadata. Lossless. |
| Date → Datetime | Set time to 00:00:00 UTC. Lossless. |
| Datetime → Date | Truncate time component. Lossy (time lost). |
| Select → Text | Store slug as plain text. Lose option constraints. |
| Checkbox → Text | "true"/"false" strings. |
| Single-line → Multi-line | Lossless. |

Conversions NOT in this matrix are blocked.

### 4.2 Conversion Workflow

1. User selects "Change field type" from field settings
2. System shows only safe target types
3. System scans data: preview of affected records, what changes, what becomes NULL
4. User confirms or cancels
5. On confirm: DDL operation queued, executed, field type config updated, schema version incremented
6. Dependent data sources and views notified of schema change

**Tasks:**

- [ ] COFS-07: Implement conversion matrix (allowed pairs)
- [ ] COFS-08: Implement data preview scan before conversion
- [ ] COFS-09: Implement DDL ALTER COLUMN TYPE execution
- [ ] COFS-10: Implement schema version increment on conversion
- [ ] COFS-11: Implement dependent data source/view notification

**Tests:**

- [ ] COFS-T07: Test allowed conversions succeed with correct data transformation
- [ ] COFS-T08: Test disallowed conversions rejected
- [ ] COFS-T09: Test non-parseable values become NULL on conversion
- [ ] COFS-T10: Test preview accurately reports affected record counts
- [ ] COFS-T11: Test schema version incremented after conversion

---

## 5. Field Groups

Field groups organize fields into logical sections for the Detail Panel. Each renders as an **Attribute Card** in the Card Layout Area. Purely presentational — no storage or query impact.

### 5.1 Definition

| Attribute | Type | Description |
|---|---|---|
| `id` | TEXT, PK | `fgr_` prefixed ULID |
| `object_type_id` | TEXT, FK | Entity type this group belongs to |
| `name` | TEXT, NOT NULL | Display name — becomes Attribute Card header |
| `description` | TEXT | Optional |
| `display_order` | INTEGER | Position among Attribute Cards |
| `is_collapsed_default` | BOOLEAN | Whether Card starts collapsed |

### 5.2 Behavior

- Fields not in any group appear in a default "General" Attribute Card
- Each group renders as a collapsible Attribute Card
- Fields within a group display in their display_order sequence
- Groups reorderable via drag-and-drop
- Empty groups hidden from Detail Panel
- Universal fields appear in system-rendered "Record Info" section

### 5.3 Example

```
── Basic Info ──────────────────────────────
  Name            | Address         | Service Type

── Pricing ─────────────────────────────────
  Price           | Discount        | Final Amount

── Scheduling ──────────────────────────────
  Scheduled Date  | Completed Date  | Duration

── Assignment ──────────────────────────────
  Customer (→Contact) | Property (→Property) | Crew (→Contact[])

── Record Info (system) ────────────────────
  Created: Feb 17, 2026 by Sam  |  Updated: Feb 17, 2026
```

**Tasks:**

- [ ] COFS-12: Implement field group CRUD
- [ ] COFS-13: Implement field-to-group assignment
- [ ] COFS-14: Implement group display_order with drag-and-drop reorder
- [ ] COFS-15: Implement default "General" group for ungrouped fields

**Tests:**

- [ ] COFS-T12: Test field group creation and rendering as Attribute Card
- [ ] COFS-T13: Test field assignment to group
- [ ] COFS-T14: Test ungrouped fields appear in default "General" card
- [ ] COFS-T15: Test empty groups hidden from Detail Panel
- [ ] COFS-T16: Test group reordering persists

---

## 6. Field Validation

Each field type supports type-specific validation constraints beyond inherent type checking. Rules stored in `validation_rules` JSONB, enforced application-side on create/update.

### 6.1 Rules by Field Type

| Field Type | Available Rules |
|---|---|
| Text (single) | `max_length`, `min_length`, `regex_pattern`, `is_unique` |
| Text (multi) | `max_length`, `min_length` |
| Number | `min_value`, `max_value`, `decimal_places` |
| Currency | `min_value`, `max_value` |
| Date | `min_date` (ISO or relative: "today", "+7d"), `max_date` |
| Datetime | `min_date`, `max_date` |
| Select | Implicit: value must match defined option slug |
| Checkbox | None beyond type |
| Relation | Implicit: referenced record must exist, correct entity type |
| Email | `is_unique`. Format validation inherent. |
| Phone | `is_unique`. E.164 validation inherent. |
| URL | None beyond format |
| Rating | `min_value`, `max_value` (integer range) |
| Duration | `min_value`, `max_value` (seconds) |
| User | Implicit: must be active tenant user |

### 6.2 Unique Constraints

When `is_unique` enabled on text, email, or phone: system creates a unique index on that column within the tenant schema. Applies across active AND archived records by default. Optional `is_unique_active_only` scopes to active records.

### 6.3 Required Field Behavior

When `is_required = true`:
- **Create:** Reject without value (unless default_value set)
- **Update:** Reject setting to NULL
- **Bulk import:** Rows missing required field rejected with error
- **Adding required to existing field:** Allowed — constraint applies going forward. Warning shows NULL count.

**Tasks:**

- [ ] COFS-16: Implement validation rule enforcement on create/update
- [ ] COFS-17: Implement unique constraint index creation
- [ ] COFS-18: Implement is_unique_active_only scope option
- [ ] COFS-19: Implement required field enforcement with default_value fallback
- [ ] COFS-20: Implement retroactive required warning (NULL count display)

**Tests:**

- [ ] COFS-T17: Test each validation rule enforced per type
- [ ] COFS-T18: Test unique constraint prevents duplicates
- [ ] COFS-T19: Test is_unique_active_only allows reuse of archived values
- [ ] COFS-T20: Test required field rejects NULL on create
- [ ] COFS-T21: Test required field with default_value applies default
- [ ] COFS-T22: Test adding required to existing field shows NULL count warning

---

## 7. Select & Multi-Select Options

Select fields have an ordered list of options — first-class definitions managed at the field level.

### 7.1 Option Definition

| Attribute | Type | Description |
|---|---|---|
| `slug` | TEXT | Machine name, immutable. Value stored in database. |
| `label` | TEXT | Display name, renamable. |
| `color` | TEXT | Hex color for badge/tag rendering. |
| `order` | INTEGER | Position in list. Determines Board view column order. |
| `is_archived` | BOOLEAN | Soft-delete. Hidden from picker, valid on existing records. |

### 7.2 Option Lifecycle

- **Add:** Immediate. No data migration.
- **Rename (label):** Immediate. Stored slug unchanged.
- **Reorder:** Immediate. Affects Board view columns and dropdown order.
- **Archive:** Removed from picker. Existing records retain value with "archived" indicator.
- **Delete:** Blocked if any records have this value. User must reassign or clear first.

**Tasks:**

- [ ] COFS-21: Implement Select option CRUD (add, rename, reorder, archive)
- [ ] COFS-22: Implement delete-block when records have the option value
- [ ] COFS-23: Implement Multi-Select option management (same lifecycle as Select)
- [ ] COFS-24: Implement archived option indicator in UI

**Tests:**

- [ ] COFS-T23: Test option added and available in picker
- [ ] COFS-T24: Test option rename changes label, slug unchanged
- [ ] COFS-T25: Test archived option hidden from picker, visible on existing records
- [ ] COFS-T26: Test delete blocked when records have the value
- [ ] COFS-T27: Test option reorder reflected in Board view columns

---

## 8. Field Lifecycle

### 8.1 Creation

1. User defines: display name, field type, config, required, default, validation, group
2. System generates slug from display name
3. System validates: slug uniqueness, field limit, valid type config
4. DDL: ALTER TABLE ADD COLUMN {slug} {pg_type}
5. If is_required and no default_value: applies to future records only
6. Schema version incremented
7. Field appears in Views picker, Data Source columns, record forms

### 8.2 Modification

- **Rename (display name):** Immediate. No DDL.
- **Change description:** Immediate. No DDL.
- **Change required flag:** Immediate. Warning if enabling on field with NULLs.
- **Change default value:** Immediate. Future records only.
- **Change validation rules:** Immediate. Future writes only.
- **Change field group:** Immediate. No DDL.
- **Change display order:** Immediate. No DDL.
- **Convert field type:** DDL operation (see Section 4).

### 8.3 Archiving

1. `is_archived` set to true
2. Hidden from: Views field picker, Data Source builder, record forms
3. Physical column and data preserved — no DDL
4. Existing views show warning: "This field is archived"
5. Raw SQL data sources can still query the column
6. Unarchive restores full visibility

System fields (`is_system = true`) cannot be archived.

### 8.4 No Deletion

Field deletion is not supported. Fields can only be archived. This preserves event sourcing integrity — events reference field slugs that must remain meaningful. Archived fields don't count against the 200-field limit.

**Tasks:**

- [ ] COFS-25: Implement field creation with DDL ALTER TABLE ADD COLUMN
- [ ] COFS-26: Implement field modification (rename, description, required, default, validation, group)
- [ ] COFS-27: Implement field archiving (hide from UI, preserve column)
- [ ] COFS-28: Implement field unarchiving
- [ ] COFS-29: Implement schema version increment on field changes
- [ ] COFS-30: Block deletion — archive only

**Tests:**

- [ ] COFS-T28: Test field creation adds physical column
- [ ] COFS-T29: Test field rename updates display name, slug unchanged
- [ ] COFS-T30: Test field archive hides from pickers but preserves data
- [ ] COFS-T31: Test field unarchive restores visibility
- [ ] COFS-T32: Test system field cannot be archived
- [ ] COFS-T33: Test schema version increments on add/archive
- [ ] COFS-T34: Test deletion rejected (archive only)
