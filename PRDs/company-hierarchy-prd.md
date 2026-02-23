# Company — Hierarchy Sub-PRD

**Version:** 1.0
**Last Updated:** 2026-02-23
**Status:** Draft
**Entity Base PRD:** [company-entity-base-prd.md]
**Referenced Entity PRDs:** [custom-objects-prd.md] (Relation Type framework)

---

## 1. Overview

### 1.1 Purpose

Company hierarchy models organizational structure: parent companies, subsidiaries, divisions, acquisitions, and spinoffs. This is fundamentally different from peer business relationships (PARTNER, VENDOR) — hierarchy is tree-structured, supports arbitrary nesting, requires temporal tracking, and carries type-specific metadata.

Hierarchy provides context for understanding corporate relationships — knowing that YouTube is a subsidiary of Alphabet, or that a startup was acquired by a competitor, helps the user interpret communication patterns and navigate organizational structures.

### 1.2 Preconditions

- At least two company records exist.
- User has permission to manage company relationships.
- The `company_hierarchy` system Relation Type is registered.

---

## 2. Context

### 2.1 Relevant Fields

| Field | Role in This Action |
|---|---|
| Name | Displayed in hierarchy views to identify parent/child companies. |
| Status | Only `active` companies can participate in new hierarchy links. Existing links to `archived` companies are preserved but visually marked. |

### 2.2 Relevant Relationships

- **Company→Company Hierarchy** — Self-referential Relation Type with parent (source) and child (target) directionality. Supports multiple hierarchy types and temporal metadata.
- **Contact Employment** — Contacts at child companies are distinct from contacts at parent companies. Hierarchy does not aggregate employment.

### 2.3 Relevant Lifecycle Transitions

- No company lifecycle transitions occur from hierarchy changes. Hierarchy links have their own lifecycle via effective/end dates.

### 2.4 Cross-Entity Context

- **Custom Objects PRD:** Hierarchy is implemented as a system Relation Type using the standard relation instance framework (Section 23.5). Junction table follows the standard metadata pattern.
- **Company Merge Sub-PRD:** The merge-vs-hierarchy fork routes here when the user indicates companies are related (not duplicates).
- **Company Entity TDD:** Neo4j graph sync converts hierarchy rows to typed edges for graph queries.

---

## 3. Key Processes

### KP-1: Establishing a Hierarchy Relationship

**Trigger:** User indicates two companies are related (via the merge-vs-hierarchy fork, or directly from a company detail page's hierarchy section).

**Step 1 — Role selection:** System asks the user to designate which company is the parent and which is the child.

**Step 2 — Type selection:** User selects the hierarchy type: subsidiary, division, acquisition, or spinoff.

**Step 3 — Metadata entry:** User optionally enters effective date, end date (NULL = still active), and type-specific metadata (e.g., acquisition amount for acquisitions).

**Step 4 — Validation:** System validates: no self-reference, optional cycle detection for deep hierarchies.

**Step 5 — Creation:** Junction row created. `HierarchyLinked` events emitted on both companies. Neo4j sync queued.

### KP-2: Viewing Company Hierarchy

**Trigger:** User navigates to a company's detail page.

**Step 1 — Parent Companies section:** Displays the company's parent(s) with hierarchy type, effective date, and link to the parent's detail page.

**Step 2 — Subsidiaries section:** Displays child companies with hierarchy type, effective date, and links.

**Step 3 — Historical relationships:** Relationships with end dates are shown in a collapsed "Historical" subsection, visually distinguished from active relationships.

### KP-3: Ending a Hierarchy Relationship

**Trigger:** User sets an end date on an existing hierarchy link, or removes it entirely.

**Step 1 — Set end date:** User edits the hierarchy relationship and sets an end date. The relationship moves to the "Historical" subsection.

**Step 2 — Remove entirely:** User deletes the hierarchy link. The junction row is removed. `HierarchyUnlinked` events emitted. Neo4j sync queued.

---

## 4. Relation Type Definition

**Supports processes:** KP-1 (step 5), KP-2 (data source), KP-3 (step 2)

### 4.1 Requirements

Company hierarchy is implemented as a system Relation Type in the Custom Objects framework:

| Property | Value |
|---|---|
| `slug` | `company_hierarchy` |
| `source_object_type` | `companies` (parent) |
| `target_object_type` | `companies` (child) |
| `cardinality` | `many_to_many` |
| `directionality` | `bidirectional` |
| `source_field_label` | Subsidiaries |
| `target_field_label` | Parent Companies |
| `has_metadata` | `true` |
| `neo4j_sync` | `true` |
| `is_system` | `true` |
| `cascade_behavior` | `nullify` |

### 4.2 Junction Table: `companies__companies_hierarchy`

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | TEXT | **PK** | Relation instance ID (prefixed ULID). |
| `source_id` | TEXT | NOT NULL, FK → `companies(id)` ON DELETE CASCADE | Parent company. |
| `target_id` | TEXT | NOT NULL, FK → `companies(id)` ON DELETE CASCADE | Child company. |
| `hierarchy_type` | TEXT | NOT NULL | `subsidiary`, `division`, `acquisition`, `spinoff`. |
| `effective_date` | DATE | | When the relationship began. |
| `end_date` | DATE | | When it ended (NULL = still active). |
| `metadata` | JSONB | | Type-specific data (acquisition amount, deal terms, etc.). |
| `created_by` | TEXT | FK → `users(id)` ON DELETE SET NULL | |
| `updated_by` | TEXT | FK → `users(id)` ON DELETE SET NULL | |
| `created_at` | TIMESTAMPTZ | NOT NULL | |
| `updated_at` | TIMESTAMPTZ | NOT NULL | |

**Constraints:**

- `CHECK (hierarchy_type IN ('subsidiary', 'division', 'acquisition', 'spinoff'))`
- `CHECK (source_id != target_id)` — No self-reference.
- Index on `(source_id)` for "list children" queries.
- Index on `(target_id)` for "find parent" queries.
- Index on `(hierarchy_type)` for type-filtered queries.

**Tasks:**

- [ ] CHIE-01: Register company_hierarchy system Relation Type
- [ ] CHIE-02: Create companies__companies_hierarchy junction table with constraints
- [ ] CHIE-03: Implement hierarchy type validation

**Tests:**

- [ ] CHIE-T01: Test self-reference constraint rejects source_id == target_id
- [ ] CHIE-T02: Test hierarchy_type check constraint rejects invalid values
- [ ] CHIE-T03: Test cascade delete removes hierarchy rows when a company is deleted

---

## 5. Hierarchy Types

**Supports processes:** KP-1 (step 2)

### 5.1 Requirements

| Type | Description | Example |
|---|---|---|
| `subsidiary` | Parent company owns or controls a child company. | Alphabet → Google |
| `division` | Parent company's internal business unit. | Google → Google Cloud |
| `acquisition` | Parent company acquired the child company. | Google → YouTube (2006) |
| `spinoff` | Child company was spun off from the parent. | eBay → PayPal |

### 5.2 Structural Properties

- **Arbitrary nesting** — Hierarchies can nest to any depth (A → B → C → D).
- **Multiple parents** — A company can have multiple parent relationships (e.g., a joint venture with two parents, or a company that changed hands).
- **Temporal** — `effective_date` and `end_date` track when relationships begin and end.
- **Single directional row** — Each relationship is stored as one row with `source_id` (parent) → `target_id` (child). The bidirectional Relation Type definition means the UI can traverse from either direction.

**Tasks:**

- [ ] CHIE-04: Implement hierarchy creation with type, dates, and metadata
- [ ] CHIE-05: Implement hierarchy update (edit dates, metadata, type)
- [ ] CHIE-06: Implement hierarchy removal with event emission

**Tests:**

- [ ] CHIE-T04: Test creation of each hierarchy type
- [ ] CHIE-T05: Test arbitrary nesting depth (A → B → C → D)
- [ ] CHIE-T06: Test multiple parents for a single company
- [ ] CHIE-T07: Test temporal tracking with effective and end dates

---

## 6. Display & Communication Separation

**Supports processes:** KP-2 (all steps)

### 6.1 Requirements

**Detail page display:**

- **Parent Companies** section shows the company's parent(s) with hierarchy type and effective date. Each entry links to the parent's detail page.
- **Subsidiaries** section shows child companies with hierarchy type and effective date. Each entry links to the child's detail page.
- Historical relationships (those with end dates in the past) appear in a collapsed "Historical" subsection.

**Communication separation:**

Companies in a hierarchy are treated as separate entities for communication purposes. Viewing a parent company does not aggregate contacts, conversations, or communications from its subsidiaries. Each company in the hierarchy maintains its own independent communication history and relationship scores.

**Rationale:** Automatic aggregation would create misleading communication metrics. A conglomerate's parent company might show artificially high engagement simply because its subsidiaries have active contacts. Users who want aggregated views can create custom views with hierarchy-aware filters in a future iteration.

**Tasks:**

- [ ] CHIE-07: Implement hierarchy display sections on company detail page
- [ ] CHIE-08: Implement historical relationship display with visual distinction
- [ ] CHIE-09: Ensure communication queries exclude hierarchy traversal

**Tests:**

- [ ] CHIE-T08: Test parent companies section displays correctly
- [ ] CHIE-T09: Test subsidiaries section displays correctly
- [ ] CHIE-T10: Test historical relationships are visually distinguished
- [ ] CHIE-T11: Test communication history does not aggregate across hierarchy

---

## 7. Hierarchy API

**Supports processes:** KP-1 (step 5), KP-3 (step 2)

### 7.1 Requirements

Uses the uniform relation instance API from Custom Objects PRD:

| Endpoint | Method | Description |
|---|---|---|
| `/api/v1/companies/{id}/relations/company_hierarchy` | GET | List hierarchy relationships for a company. |
| `/api/v1/companies/{id}/relations/company_hierarchy` | POST | Add a hierarchy relationship. Body: `{target_id, hierarchy_type, effective_date, metadata}`. |
| `/api/v1/companies/{id}/relations/company_hierarchy/{relation_id}` | PATCH | Update hierarchy metadata, dates, or type. |
| `/api/v1/companies/{id}/relations/company_hierarchy/{relation_id}` | DELETE | Remove a hierarchy relationship. |

**Tasks:**

- [ ] CHIE-10: Implement hierarchy API endpoints using relation instance framework
- [ ] CHIE-11: Implement Neo4j sync for hierarchy edge creation/removal
- [ ] CHIE-12: Emit HierarchyLinked/HierarchyUnlinked events

**Tests:**

- [ ] CHIE-T12: Test hierarchy API CRUD operations
- [ ] CHIE-T13: Test Neo4j edge creation on hierarchy link
- [ ] CHIE-T14: Test Neo4j edge removal on hierarchy unlink
- [ ] CHIE-T15: Test events emitted on both companies for hierarchy changes
