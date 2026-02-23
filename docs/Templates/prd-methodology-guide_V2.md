# PRD Methodology Guide

## Using Claude.ai and Claude Code for Large Project Development

**Version:** 2.0
**Purpose:** This guide defines the standard methodology for developing large software projects using Claude.ai for product requirements and design, and Claude Code for implementation. It establishes document types, templates, workflows, and rationale for each decision.

> **V2.0 (2026-02-23):** Added Key Processes as a PRD component (Section 3.5, 3.8). Added field-level metadata requirements — Editable, Sortable, Filterable — for Entity Base PRDs (Section 5.6). Expanded TDD methodology to describe the living document approach where Claude Code writes implementation decisions back into TDDs (Sections 3.2, 3.7, 4.4). Added the † caching convention for subquery-backed sortable fields.

---

## 1. Philosophy

### 1.1 Why This Methodology Exists

Large software projects collapse when product requirements live in a single monolithic document. A single PRD quickly becomes too large for effective human review and too large for Claude Code to hold in context without losing focus. Implementation details get mixed with product requirements. Tracking what's been built versus what's planned becomes guesswork.

This methodology solves these problems by:

- Separating *what* the product does (PRDs) from *how* it's built (TDDs)
- Decomposing requirements into focused, self-contained documents that Claude Code can work from without losing context
- Embedding implementation tracking directly into the requirements documents
- Establishing a consistent plan-execute-verify-test cycle between you and Claude Code

### 1.2 Core Principles

**Separation of What and How.** Product Requirements Documents define what the system does and why. Technical Design Documents define how it's built. This separation keeps PRDs focused on user-facing behavior and business rules, while TDDs capture technology choices with their rationale. Neither contaminates the other.

**Self-Contained Documents.** Each document Claude Code works from should contain enough context to implement from without requiring multiple document loads. Action Sub-PRDs extract relevant context from their parent Entity Base PRD. The instruction to Claude Code is always: "Read this document, focus on this section."

**Hierarchical Decomposition.** Requirements are organized in a hierarchy — product, entity, action — where each level adds detail. Higher levels provide the map; lower levels provide the directions. Someone reading only the Product PRD understands the entire system. Someone reading an Action Sub-PRD understands exactly how to build one piece.

**Living Documents.** PRDs are not static specifications. They include task lists and test plans that track implementation progress. Documents evolve as decisions are made, but changes are always reviewed and approved by the product owner before being written.

**Human Approval.** Claude Code proposes; you decide. All document modifications — task list changes, test plans, technical decisions — are presented for discussion and approval before being written. The PRDs always reflect your decisions, not Claude Code's assumptions.

---

## 2. Document Hierarchy

The methodology uses a three-level hierarchy of documents, with supporting documents at each level.

### 2.1 Product Level

These documents describe the entire product and apply globally.

| Document | Purpose | Contains |
|---|---|---|
| Product PRD | What the product is and why it exists | Vision, competitive landscape, target users, product scope, principles |
| Product TDD | Global technology and deployment decisions | Technology stack, database choices, API patterns, design principles, deployment infrastructure, with rationale. The foundation that all entity and action TDDs inherit from. |
| GUI Standards | Reusable UI patterns and conventions | Design philosophy, color system, typography, spacing, component patterns, layout conventions, interaction behaviors, data display conventions |
| PRD Index | Document registry and navigation | Hierarchical status of all documents, retired document history, workflow notes |

### 2.2 Entity Level

These documents describe a single data entity (Contact, Company, Communication, etc.) and everything users can do with it.

| Document | Purpose | Contains |
|---|---|---|
| Entity Base PRD | Complete description of the entity | Definition, field-level metadata (editable/sortable/filterable), relationships, lifecycle, key processes, action catalog, cross-cutting concerns |
| Entity UI PRD | Screen layouts and navigation for the entity | Screen descriptions, interaction flows, simple action UI, task lists, test plans |
| Entity TDD | Entity-specific technical decisions (only if needed) | Decisions with rationale that deviate from or extend the Product TDD. Starts with your architectural decisions; grows as Claude Code adds implementation decisions. |

### 2.3 Action Level

These documents describe a single complex action or group of related actions on an entity.

| Document | Purpose | Contains |
|---|---|---|
| Action Sub-PRD | Detailed requirements for a complex action | Overview, extracted context, key processes, requirements, UI specs, task lists, test plans |
| Action TDD | Action-specific technical decisions (only if needed) | Decisions with rationale that apply only to this action. Same living document approach — you write initial decisions, Claude Code adds implementation decisions. |

### 2.4 Cross-Entity Workflows

If a workflow genuinely spans multiple entities without a natural owner, it follows the same pattern as an entity — base PRD, sub-PRDs, UI PRD, and TDD as needed. In practice, most workflows have a natural owning entity, and the action sub-PRD simply references other entity base PRDs.

### 2.5 Inheritance

Each level inherits from above. An Action Sub-PRD inherits the product principles, the entity's data model and lifecycle, and any technical decisions from the Product TDD and Entity TDD. The self-containment principle means relevant inherited context is extracted into the document rather than requiring Claude Code to load parent documents.

---

## 3. Document Templates

Each document type has a defined template. Templates provide structure and consistency but are not rigid — the author decides what level of detail is appropriate for each section. The following sections reference the separate template files.

### 3.1 Product PRD

**Template file:** `template-product-prd.md`

The Product PRD is the root document. It answers: what is this product, why does it exist, who is it for, and what does it encompass? Someone reading only this document should understand the entire product at a conceptual level.

**When to create:** Once, at the start of the project. Updated when the product scope changes.

**Key principle:** The Product PRD is lean. It summarizes features and entities — it does not describe them in detail. Detailed requirements live in entity and action PRDs. Business metrics, roadmap, and phasing are separate concerns managed outside the PRD system.

### 3.2 Product TDD

**Template file:** `template-product-tdd.md`

The Product TDD captures global technology decisions that apply across the entire system. It answers: what technologies are we using, and why?

**When to create:** Early in the project, alongside the Product PRD. Updated as major technical decisions are made.

**Key principle:** Every decision includes rationale and rejected alternatives. This prevents revisiting settled decisions and helps Claude Code understand the constraints it's working within. Entity or action-specific technology choices do not belong here — they go in entity or action TDDs.

**The Product TDD as foundation:** The Product TDD establishes the defaults that all entity and action TDDs inherit from. When an entity TDD is silent on a topic, the Product TDD applies. This means the Product TDD should cover: language and framework choices, database strategy, API conventions, authentication patterns, UI architecture patterns, design principles that constrain all implementation, testing patterns, configuration approach, and project structure. Entity TDDs only document decisions that deviate from or extend these defaults.

**Design Principles section:** The Product TDD should include a Design Principles section that captures global constraints Claude Code must follow. These are not suggestions — they are rules. Examples include: "display speed is paramount" (denormalize for read speed), "idempotent writes" (all sync uses UPSERT), "editability is explicit" (Claude Code must not make fields editable unless the PRD says so). These principles save time by preventing Claude Code from making decisions that violate architectural intent.

### 3.3 GUI Standards

**Template file:** `template-gui-standards.md`

The GUI Standards document defines the visual design system and interaction conventions used across the entire product. It is the single source of truth for how the product looks and behaves.

**When to create:** Early in the project, before any entity UI work begins. Updated as new component patterns are established.

**Key principle:** This document has task lists and test plans because building the design system is real implementation work — shared component libraries, color systems, and layout patterns must be built and tested. This document is a strong candidate for becoming a Claude Code skill once the methodology is proven.

### 3.4 PRD Index

**Template file:** `template-prd-index.md`

The PRD Index is the navigation hub for the entire document set. It is the first document read at the start of any session.

**When to create:** Once, at the start of the project. Updated after every PRD session.

**Key principle:** The index is lean. It tracks document status and provides navigation. Cross-PRD decisions belong in TDDs. Priority sequencing and work tracking belong in your project management tool.

### 3.5 Entity Base PRD

**Template file:** `template-entity-base-prd.md`

The Entity Base PRD is the complete map of a single entity. It defines what the entity is, how it relates to other entities, its lifecycle, and everything you can do with it.

**When to create:** One per entity, when the entity is first designed. Updated when new actions are added or the data model changes.

**Key principle:** The Entity Base PRD is the map, not the directions. Someone reading it understands the full scope of the entity without reading any sub-PRDs. Simple actions are fully described in the action catalog. Complex actions are summarized with enough detail to understand what they do, with pointers to their sub-PRDs for implementation detail. No implementation or technology specifics appear here.

**Key Processes:** Between the entity lifecycle and the action catalog, the Entity Base PRD defines Key Processes — end-to-end user journeys through the entity's core workflows. Each Key Process has a unique ID (e.g., KP-CONT-01), a name, a trigger, and a step-by-step walkthrough of the user experience from start to finish. Key Processes tie together multiple simple actions, UI interactions, and system behaviors into coherent workflows. Simple actions in the action catalog reference the Key Process IDs they participate in ("Supports processes: KP-CONT-01, KP-CONT-03"). This creates a two-way link: processes show how actions combine, and actions show which processes they serve.

**Field-Level Metadata:** The Core Fields table in the Entity Base PRD includes three metadata columns beyond the field's description and valid values:

- **Editable** — Declares how (or if) the user can modify the field. Values: `Direct` (inline edit), `Override` (computed with manual override), `Via [sub-entity]` (edit through related record), `Computed` (derived, not editable), `System` (never user-editable). This prevents Claude Code from making non-editable fields editable or routing edits through the wrong UI.
- **Sortable** — Whether the field appears in sort options in list views. Fields backed by correlated subqueries that would be expensive to sort are marked with † and a note that the Entity TDD must define a caching or denormalization strategy. Fields without † are expected to sort at negligible cost (direct columns or JOINs).
- **Filterable** — Whether the field appears in filter options in list views.

These are product decisions, not technical decisions. The PRD declares the intended behavior; the TDD documents how to achieve it performantly.

### 3.6 Entity UI PRD

**Template file:** `template-entity-ui-prd.md`

The Entity UI PRD describes the standard screens and navigation flows for an entity — list views, detail views, and UI for simple actions. It does not cover UI for complex actions that have their own sub-PRDs.

**When to create:** One per entity, after the Entity Base PRD is established. Updated when new screens are added or layouts change.

**Key principle:** Organized by screen, not by feature. Each screen section contains the layout description, interaction behaviors, and associated task lists and test plans. References the GUI Standards for component patterns but does not duplicate them. The level of UI detail is the author's choice — from a sentence for trivial screens to wireframes for critical layouts.

### 3.7 Entity TDD

**Template file:** `template-entity-tdd.md` (uses the same template as Action TDD)

Entity TDDs are optional. They capture technical decisions that apply only to this entity and deviate from or extend the Product TDD.

**When to create:** Only when the entity requires technical decisions not covered by the Product TDD. Many entities will not need one. However, for core entities with complex data models (e.g., contacts with multi-identifier resolution, denormalized display fields, and event sourcing), an Entity TDD is strongly recommended.

**TDD structure:** The Entity TDD mirrors the Product TDD's decision format — each decision has a title, the decision itself, rationale, alternatives rejected, and constraints/tradeoffs. The TDD does not include table schemas, full SQL, or implementation code. It captures decisions and their reasoning, not the implementation details that follow from those decisions.

**Living document approach:** The Entity TDD is written in two phases:

1. **You write the decisions you care about** as the product/architecture owner. These are decisions where you have opinions and Claude Code should not freelance — caching strategies, denormalization choices, algorithm design, data model patterns. Write only what you know needs to be decided. Leave areas where you don't have a strong opinion for Claude Code to resolve.

2. **Claude Code writes its decisions back** during implementation. When Claude Code encounters technical decisions not covered by the TDD — index placement, query patterns, error handling approaches, adapter interfaces — it records those decisions with rationale in the appropriate section of the TDD. This creates a complete record of all technical decisions, not just the ones you anticipated.

The result is a TDD that starts lean (only your architectural decisions) and grows organically as implementation proceeds. Future Claude Code sessions read the TDD and understand the existing codebase without re-deriving decisions or accidentally contradicting them.

**Placeholder section:** The Entity TDD should end with a section titled "Decisions to Be Added by Claude Code" that lists the areas where Claude Code will likely need to make decisions. This serves as a roadmap and a reminder to document those decisions when they're made.

### 3.8 Action Sub-PRD

**Template file:** `template-action-sub-prd.md`

The Action Sub-PRD is the document Claude Code works from most directly. It contains the detailed requirements, UI specifications, task lists, and test plans for a complex action.

**When to create:** One per complex action or group of related actions. Created when the action is too complex to describe fully in the Entity Base PRD's action catalog. Simple actions do not need sub-PRDs.

**Key principle:** Self-contained. The document extracts relevant context from the Entity Base PRD so Claude Code can work from it without loading multiple documents. Requirements are organized into functional sections, each with their own task lists and test plans. The format of requirements (sequential workflow, business rules, or a mix) is the author's choice based on what best fits the action.

**Key Processes in Action Sub-PRDs:** Complex actions define their own Key Processes using the same KP-ID pattern (e.g., KP-MERGE-01). These describe the end-to-end user journeys specific to that action. Functional sections within the Sub-PRD reference which Key Processes they support, creating the same two-way linkage as in the Entity Base PRD. This ensures Claude Code understands not just what to build, but how the pieces fit into complete user experiences.

### 3.9 Action TDD

**Template file:** `template-action-tdd.md` (uses the same template as Entity TDD)

Action TDDs are optional. They capture technical decisions specific to an action, including deployment requirements. They follow the same living document approach as Entity TDDs — you write the decisions you care about, Claude Code writes back the decisions it makes during implementation.

**When to create:** Only when the action requires technology or deployment decisions not covered by the Product TDD or Entity TDD. For example, an Email Import action requiring AWS Lambda would have its own TDD. Simple actions that follow standard patterns typically don't need a TDD. Complex actions with non-obvious algorithm design, transaction semantics, or external service integration benefit from one.

**TDD hierarchy:** When Claude Code works on an action, it reads the Product TDD (platform defaults), the Entity TDD (entity-specific decisions), and the Action TDD (action-specific decisions), in that order. Each level overrides the one above for its specific scope.

---

## 4. The Implementation Workflow

### 4.1 Phase Split: Claude.ai vs. Claude Code

**Claude.ai** is used for thinking, planning, and designing. All PRD creation and refinement happens here. Claude.ai helps you define requirements, identify edge cases, and structure documents. The PRD Index is the starting context for every Claude.ai session.

**Claude Code** is used for building and verifying. Claude Code reads PRDs and TDDs, plans implementation, writes code, and reports status. Claude Code proposes changes to documents but never modifies them without your approval.

### 4.2 The Plan-Execute-Verify-Test Cycle

When you direct Claude Code to implement a section of a PRD, the workflow follows four stages:

**Plan.** Claude Code reads the document section and its task list. It presents a proposed implementation plan, which may include suggested additions or modifications to the task list. You discuss the plan and approve it before any code is written. This is where Claude Code might identify tasks you hadn't thought of or suggest splitting a task that's too large.

**Execute.** Claude Code implements the approved plan, working through the task list. It updates task checkboxes as it completes each item.

**Verify.** After implementation, Claude Code verifies each completed task against the approved plan and reports status. This is a self-check — Claude Code confirms it actually implemented what was planned.

**Test.** Claude Code generates a test plan for the completed section. You review and approve the test plan before it's added to the document. Claude Code then runs the tests and reports results.

### 4.3 Session Management

Claude Code does not maintain state between sessions. At the start of each session:

1. Direct Claude Code to read the relevant document
2. Tell it which section to focus on
3. Claude Code reviews the task list and reports what's done versus remaining
4. You confirm the starting point and direct it to proceed

This prevents Claude Code from losing track of where it is in a larger implementation effort.

### 4.4 Technical Decision Capture

During implementation, Claude Code will make technical decisions not covered by existing TDDs — a library choice, an architectural pattern, a query optimization, an index strategy. The methodology requires that these decisions are captured, not lost.

**The write-back workflow:**

1. **Claude Code encounters a decision point** not covered by the Product TDD or Entity TDD — for example, which indexes to create on a table, how to structure an FTS virtual table, or how to handle a concurrency edge case.
2. **Claude Code implements its chosen approach** and documents the decision in the appropriate TDD using the standard format (decision, rationale, alternatives rejected, constraints/tradeoffs).
3. **You review the additions** during your next TDD review pass. You may approve, modify, or override Claude Code's decisions. The TDD always reflects the final approved state.

**Where decisions go:**
- Platform-wide decisions (e.g., "we use FTS5 for all full-text search") → Product TDD
- Entity-specific decisions (e.g., "the contacts table uses these specific indexes") → Entity TDD
- Action-specific decisions (e.g., "the merge transaction uses this locking strategy") → Action TDD

**Why this matters:** Without write-back, Claude Code's implementation decisions exist only in the code. A future Claude Code session reading the TDD sees gaps and may make different decisions, creating inconsistencies. Write-back ensures the TDD is the authoritative record of both what was intended and what was actually built.

**Detecting PRD-to-implementation gaps:** Claude Code may discover during implementation that a PRD requirement has performance or feasibility implications the PRD didn't account for. For example, a PRD may state "all fields are sortable" when some fields require expensive subqueries to sort. When this happens:

1. Claude Code documents the gap and the technical constraint in the TDD
2. Claude Code proposes a resolution (e.g., mark subquery fields non-sortable, or implement caching)
3. You review and may update the PRD to reflect the corrected product decision
4. The TDD documents the technical rationale for the PRD change

This feedback loop — PRD states intent → Claude Code discovers constraint → TDD captures rationale → PRD is updated — keeps the documents honest and aligned with reality.

### 4.5 High-Level Tracking

The PRD task lists and test plans track detailed implementation status within each document. High-level priorities, sequencing across entities and features, and cross-entity dependencies are tracked in your project management tool (e.g., ClickUp). This avoids duplicating tracking information in two places.

---

## 5. Writing Effective PRDs

### 5.1 Abstraction Level

PRDs describe *what* the system does in terms of user-facing behavior and business rules. They do not specify implementation details. Examples:

**PRD (correct):** "Contact display name is required. It is computed from first name and last name unless manually overridden by the user."

**PRD (too technical):** "display_name TEXT NOT NULL DEFAULT computed via COALESCE(first_name || ' ' || last_name)."

The second example belongs in a TDD if the specific implementation matters.

### 5.2 Action Catalog Granularity

In the Entity Base PRD, simple actions are fully described in the action catalog. An action is "simple" when it can be fully specified in a few sentences — its trigger, inputs, outcome, and business rules. Once an action involves multi-step workflows, conditional logic, interactions with multiple entities, or complex UI, it graduates to its own sub-PRD.

The author makes this call. The methodology provides a structure to capture the information consistently regardless of where the boundary falls.

### 5.3 Task List Granularity

Each task list item should be small enough that Claude Code can implement it in a focused pass and you can verify it clearly, but not so granular that the list becomes unmanageable. Items are prefixed with an entity code and number for tracking:

```
- [ ] CONT-01: Contact list view with sortable columns (name, company, email, phone)
- [ ] CONT-02: Add Contact form with field validation
- [ ] CONT-03: Edit Contact form with pre-populated fields
```

The right granularity will emerge through practice. Start at the level of one discrete behavior or UI element and adjust as you learn.

### 5.4 UI Specifications

The level of UI detail is always the author's choice:

- A sentence for trivial UI ("standard edit form per GUI Standards")
- A written description for moderate complexity (field layout, conditional visibility, navigation flow)
- A wireframe for critical layouts where visual precision matters

The GUI Standards document handles reusable patterns. Entity and action PRDs handle specific screens and workflows.

### 5.5 Cross-Entity References

When an action sub-PRD crosses entity boundaries (e.g., email import touches Communications, Contacts, and Companies), it references the other entity base PRDs by name but extracts the specific context it needs into its own document. This maintains self-containment while acknowledging dependencies.

### 5.6 Field-Level Metadata in Entity Base PRDs

Every field in an Entity Base PRD's Core Fields table must declare three behavioral attributes beyond its description and valid values: **Editable**, **Sortable**, and **Filterable**. These are product decisions that directly control what Claude Code builds.

**Why this matters:** Without explicit field metadata, Claude Code makes assumptions. It may make a computed field editable (e.g., allowing inline editing of a display name that's derived from first + last name). It may add sort options to fields that require expensive subqueries. It may omit filter options for fields that users need to filter by. Each of these is a bug that traces back to an ambiguous PRD.

**The Editable taxonomy:**
- **Direct** — User edits this field inline. Claude Code renders an input or select control.
- **Override** — Computed by default, but user can manually override. Claude Code needs to track whether the current value is computed or overridden, and provide a "reset to computed" action.
- **Via [sub-entity]** — The displayed value summarizes a related record. Clicking it opens the sub-entity's editor, not an inline edit. This is the most common source of Claude Code bugs — it sees a field on the detail page and makes it editable when it should navigate to a different editor.
- **Computed** — Derived from other data. Not editable at all. Claude Code renders it as read-only.
- **System** — Set by the system. Never rendered with any edit affordance.

**The † caching convention for sortable fields:** When a field is marked Sortable but is backed by a correlated subquery (e.g., primary email is resolved from a join on contact_identifiers), the PRD marks it with † and includes a note: "The Entity TDD must define a caching or denormalization strategy." This creates a clear contract:
- The PRD says "users should be able to sort by this field" (product decision)
- The TDD says "we cache this value in column X, kept in sync by Y" (technical decision)
- Claude Code reads both and implements accordingly

Without this convention, Claude Code either makes expensive subquery fields sortable (degrading performance) or silently makes them non-sortable (violating the PRD). The † makes the intent explicit and the responsibility clear.

---

## 6. Evolving the Methodology

This methodology is a starting framework, not a rigid specification. As you use it:

- Adjust task list granularity based on what works with Claude Code
- Add new document types if cross-entity workflows need their own home
- Promote stable reference documents (Product TDD, GUI Standards) to Claude Code skills
- Refine templates based on what information Claude Code actually needs versus what's noise

The structure is designed to be extensible. Any new document type follows the same patterns — self-contained, hierarchically organized, with task lists and test plans where implementation work is tracked.
