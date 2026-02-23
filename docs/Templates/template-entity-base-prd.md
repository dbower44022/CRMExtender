# [Entity Name] — Entity Base PRD

**Version:** [X.X]
**Last Updated:** [YYYY-MM-DD]
**Status:** [Draft | Review | Approved]
**Product PRD:** [filename]

---

## 1. Entity Definition

### 1.1 Purpose

[What does this entity represent? What is its role in the system? A clear statement that establishes why this entity exists.]

### 1.2 Core Fields

[Each field with its name, description, whether required or optional, valid values, and any business rules. Describe fields conceptually — no database types or storage details.

**Sortable / Filterable columns:** These declare whether the user can sort and filter by each field in list views. This is a product decision that must be made per field. If a field is marked non-sortable due to performance constraints (e.g., requires correlated subquery), the Entity TDD should document the technical rationale and the path to enabling it (e.g., denormalization, caching). Fields backed by direct columns or JOINs should generally be sortable. Fields backed by subqueries may be marked non-sortable until a caching strategy is implemented.

**Editable column:** Declares how (or if) the user can modify this field. This prevents Claude Code from making computed or system fields editable. Values:

- **Direct** — User edits this field inline on the detail page or edit form.
- **Override** — Field is computed by default but the user can manually override the computed value. The UI should indicate when a value is overridden vs. computed.
- **Via [sub-entity]** — The displayed value is a summary of a related record. Editing opens the sub-entity's own editor (e.g., Primary Email is edited through the identifiers panel, not inline on the contact card).
- **Computed** — Derived from other data. Not directly editable. The user changes this field by modifying the source data it derives from.
- **System** — Set and managed by the system. Never user-editable.]

| Field | Description | Required | Editable | Sortable | Filterable | Valid Values / Rules |
|---|---|---|---|---|---|---|
| | | | | | | |
| | | | | | | |

### 1.3 Computed / Derived Fields

[Fields calculated from other data. For each: what it represents, how the user changes it (if at all), and the business logic for how it's derived. None of these fields should be directly editable on the entity card unless marked as Override.]

| Field | Description | Editable | Derivation Logic |
|---|---|---|---|
| | | | |
| | | | |

---

## 2. Entity Relationships

[How this entity connects to every other entity in the system. Each relationship should be described with enough detail that the reader understands the full picture without reading action sub-PRDs.]

### 2.1 [Related Entity Name]

**Nature:** [One-to-many | Many-to-many | One-to-one | Temporal]
**Ownership:** [Which entity owns the relationship]
**Description:** [Summary of the relationship — detailed enough to understand what it is, how it works conceptually, and why it exists. Include temporal aspects, cardinality details, and any special characteristics.]

### 2.2 [Related Entity Name]

**Nature:** [One-to-many | Many-to-many | One-to-one | Temporal]
**Ownership:** [Which entity owns the relationship]
**Description:** [Summary of the relationship.]

---

## 3. Lifecycle

### 3.1 Statuses

[Every possible state the entity can be in, with a description of what each means.]

| Status | Description |
|---|---|
| | |
| | |

### 3.2 Transitions

[Which statuses can move to which, and what triggers each transition.]

| From | To | Trigger |
|---|---|---|
| | | |
| | | |

### 3.3 Creation Sources

[How instances of this entity enter the system, and what initial status each source produces.]

| Source | Initial Status | Notes |
|---|---|---|
| | | |
| | | |

---

## 4. Key Processes

[Define the end-to-end user experiences for the core entity workflows — the processes that involve the simple actions described in the Action Catalog. Complex actions have their own key processes in their sub-PRDs; this section covers the foundational experiences like creating, browsing, viewing, editing, and managing the entity's lifecycle.

Key processes serve two audiences:
- **Humans:** Understand how users interact with this entity day-to-day before reviewing action details.
- **Claude Code:** Understand the intended user experience for core workflows, preventing assumption-making during implementation.

Each process is assigned an ID (KP-1, KP-2, etc.) that can be referenced by simple actions in the Action Catalog.]

### KP-1: [Process Name]

**Trigger:** [What initiates this scenario.]

**Step 1 — [Step name]:** [What happens. What the user sees or does.]

**Step 2 — [Step name]:** [What happens next. Decision points, feedback, outcomes.]

[Continue with steps as needed.]

### KP-2: [Process Name]

**Trigger:** [What initiates this scenario.]

[Steps...]

---

## 5. Action Catalog

[Complete enumeration of every action that can be performed on this entity. Simple actions are fully described here. Complex actions are summarized with a pointer to their sub-PRD. Simple actions should reference the Key Processes they support.]

### 5.1 [Simple Action Name]

**Supports processes:** [KP IDs, if applicable]
**Trigger:** [What initiates this action.]
**Inputs:** [What information is needed.]
**Outcome:** [What changes as a result.]
**Business Rules:** [Any constraints or conditions.]

### 5.2 [Simple Action Name]

**Supports processes:** [KP IDs, if applicable]
**Trigger:** [What initiates this action.]
**Inputs:** [What information is needed.]
**Outcome:** [What changes as a result.]
**Business Rules:** [Any constraints or conditions.]

### 5.3 [Complex Action Name]

**Summary:** [What this action does and why — detailed enough that the reader understands the full scope without reading the sub-PRD.]
**Sub-PRD:** [filename]

### 5.4 [Complex Action Name]

**Summary:** [What this action does and why.]
**Sub-PRD:** [filename]

---

## 6. Cross-Cutting Concerns

[Business-level concerns that span multiple actions on this entity. Not technical implementation details — those belong in the TDD.]

### 6.1 Compliance Requirements

[GDPR, CCPA, industry-specific regulations that affect this entity's behavior.]

### 6.2 Security Rules

[Access control, data sensitivity, audit requirements specific to this entity.]

### 6.3 Data Retention

[How long data is retained, archival policies, hard deletion rules.]

### 6.4 [Other Constraints]

[Any additional business-level constraints that apply broadly across this entity's actions.]
