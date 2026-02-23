# [Entity Name] — [Action Name] Sub-PRD

**Version:** [X.X]
**Last Updated:** [YYYY-MM-DD]
**Status:** [Draft | Review | Approved]
**Entity Base PRD:** [filename]
**Entity UI PRD:** [filename] (if applicable)
**Referenced Entity PRDs:** [list any other entity base PRDs this action touches]

---

## 1. Overview

### 1.1 Purpose

[What does this action do? Why does it exist? What problem does it solve for the user?]

### 1.2 Preconditions

[What must be true before this action can be triggered? Required system state, data prerequisites, user permissions.]

---

## 2. Context

[Extracted from the Entity Base PRD and any referenced entity PRDs. Only the information relevant to this action — specific fields, relationships, lifecycle transitions, and business rules. This section makes the document self-contained so Claude Code can work from it without loading parent documents.]

### 2.1 Relevant Fields

[The entity fields this action reads, modifies, or creates.]

### 2.2 Relevant Relationships

[The entity relationships this action affects.]

### 2.3 Relevant Lifecycle Transitions

[The status changes this action triggers.]

### 2.4 Cross-Entity Context

[Context extracted from other entity PRDs that this action references. Describe the specific data, rules, or behaviors from other entities that this action depends on.]

---

## 3. Key Processes

[Define the end-to-end user experiences for each scenario where this action is involved. Each key process describes a complete user journey — from what triggers it, through each step the user takes or observes, to the final outcome. These processes establish the user experience that the functional sections must support.

Key processes serve two audiences:
- **Humans:** Understand the intended experience before reviewing mechanism details.
- **Claude Code:** Understand what the user should see and do at each stage, preventing assumption-making during implementation.

Each process is assigned an ID (KP-1, KP-2, etc.) referenced by functional sections throughout the document.]

### KP-1: [Process Name]

**Trigger:** [What initiates this scenario.]

**Step 1 — [Step name]:** [What happens. What the user sees or does.]

**Step 2 — [Step name]:** [What happens next. Decision points, feedback, outcomes.]

[Continue with steps as needed. Include branching paths where the user experience diverges based on system decisions or user choices.]

### KP-2: [Process Name]

**Trigger:** [What initiates this scenario.]

[Steps...]

### KP-3: [Process Name]

[Additional processes as needed. Cover all distinct scenarios where this action is invoked, including automated triggers, manual triggers, and edge cases where the user encounters this action indirectly.]

---

## 4. [Functional Area Name]

**Supports processes:** [List the KP IDs and specific steps this section implements, e.g., "KP-1 (steps 2–3), KP-3 (step 4)." This linkage ensures Claude Code understands where this mechanism fits in the user journey.]

### 4.1 Requirements

[Detailed requirements for this functional area. Format is the author's choice based on what best fits the action:

- Sequential workflow (step 1, step 2, step 3) for process-oriented actions
- Rules and conditions for validation or business logic
- A mix of both

Requirements should be specific enough for Claude Code to implement and for you to verify. Include edge cases and error handling. Where the key process description provides the user-facing flow, this section adds the mechanism details — business rules, data operations, validation, and error handling that support the process.]

### 4.2 UI Specifications

[UI for this functional area's workflow. Level of detail is the author's choice — from a sentence ("standard edit form per GUI Standards") to wireframes for critical layouts. Include field layouts, conditional visibility, navigation flows, and user feedback.]

**Tasks:**

- [ ] [CODE]-01: [Task description]
- [ ] [CODE]-02: [Task description]
- [ ] [CODE]-03: [Task description]

**Tests:**

- [ ] [CODE]-T01: [Test description]
- [ ] [CODE]-T02: [Test description]
- [ ] [CODE]-T03: [Test description]

---

## 5. [Functional Area Name]

**Supports processes:** [KP IDs and steps]

### 5.1 Requirements

[Detailed requirements for this functional area.]

### 5.2 UI Specifications

[UI for this functional area, if applicable.]

**Tasks:**

- [ ] [CODE]-01: [Task description]
- [ ] [CODE]-02: [Task description]

**Tests:**

- [ ] [CODE]-T01: [Test description]
- [ ] [CODE]-T02: [Test description]

---

## 6. [Additional Functional Areas]

[Add functional area sections as needed following the same pattern. Each section contains its own process linkage, requirements, UI specs (if applicable), task list, and test plan.]
