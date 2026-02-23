# [Functional Area Name] — Functional Area PRD

**Version:** [X.X]
**Last Updated:** [YYYY-MM-DD]
**Status:** [Draft | Review | Approved]
**Product PRD:** [filename]
**Master Glossary:** [filename]

> **Changelog:** [Brief description of changes in this version.]

---

## 1. Scope & Boundaries

### 1.1 Purpose

[What this functional area is responsible for. One or two paragraphs describing the capability this PRD governs. This is not a feature list — it's the "why this area exists" statement.]

### 1.2 Actors

[Who interacts with this functional area and in what capacity.]

| Actor | Role | Access Level |
|---|---|---|
| | | |
| | | |

### 1.3 Boundaries

**In scope:**
- [Capability or responsibility this PRD owns]
- [Capability or responsibility this PRD owns]

**Out of scope (owned by other PRDs):**
- [Capability] — See [other PRD filename]
- [Capability] — See [other PRD filename]

### 1.4 Related Documents

| Document | Relationship |
|---|---|
| | |
| | |

---

## 2. Capabilities

[High-level catalog of what the system provides in this area. Each capability is described briefly — detailed requirements live in the action catalog (Section 5) or in Action Sub-PRDs. This section is the map; the action catalog and sub-PRDs are the directions.]

### 2.1 [Capability Name]

[Brief description of this capability — what it does, why it exists, who uses it.]

### 2.2 [Capability Name]

[Brief description.]

---

## 3. Configuration

[Settings, parameters, and defaults that govern behavior in this functional area. These are the knobs that administrators turn. Each setting declares its metadata so Claude Code knows exactly how to render and enforce it.]

### 3.1 Configuration Table

| Setting | Description | Type | Default | Scope | Editable By |
|---|---|---|---|---|---|
| | | | | | |
| | | | | | |

**Scope values:** [Define what scopes mean for this area — e.g., `system` (one value for entire tenant), `user` (per-user override), `provider` (per-provider-account).]

**Editable By values:** [Define who can change settings — e.g., `admin`, `user` (own settings only), `system` (set automatically).]

### 3.2 Configuration Rules

[Business rules governing configuration — validation, dependencies between settings, constraints. For example: "Setting X can only be enabled when Setting Y is also enabled."]

---

## 4. Key Processes

[End-to-end user journeys through this functional area's core workflows. Each Key Process has a unique ID, a name, a trigger, and a step-by-step walkthrough of the user experience from start to finish.]

### KP-[AREA]-01: [Process Name]

**Trigger:** [What initiates this process]
**Actor:** [Who performs this process]

**Steps:**
1. [Step description]
2. [Step description]
3. [Step description]

**Outcome:** [What state the system is in when the process completes]

### KP-[AREA]-02: [Process Name]

**Trigger:** [What initiates this process]
**Actor:** [Who performs this process]

**Steps:**
1. [Step description]
2. [Step description]

**Outcome:** [What state the system is in when the process completes]

---

## 5. Action Catalog

[All actions in this functional area. Simple actions are fully described here. Complex actions are summarized with pointers to their Action Sub-PRDs.]

### 5.1 Simple Actions

[Actions that can be fully specified in a few sentences — trigger, inputs, outcome, business rules.]

#### [Action Name]

**Trigger:** [How the action is initiated]
**Inputs:** [What data is required]
**Outcome:** [What changes in the system]
**Business Rules:** [Constraints and validation]
**Supports processes:** [KP-IDs]

#### [Action Name]

**Trigger:** [How the action is initiated]
**Inputs:** [What data is required]
**Outcome:** [What changes in the system]
**Business Rules:** [Constraints and validation]
**Supports processes:** [KP-IDs]

### 5.2 Complex Actions (Sub-PRDs)

[Actions too complex for the action catalog. Each gets its own Action Sub-PRD following the standard template.]

| Action | Sub-PRD | Description |
|---|---|---|
| | | |
| | | |

---

## 6. Cross-Cutting Concerns

### 6.1 Audit & Logging

[What actions in this functional area are audited. What data is captured in audit records. Where audit records are stored.]

### 6.2 Permissions & Access Control

[How access to this functional area's capabilities is controlled. Which roles can perform which actions.]

### 6.3 Error Handling

[Error handling patterns specific to this functional area. How failures are communicated to the user. Recovery strategies.]

---

## 7. Task List

[Implementation tasks for this functional area. Prefixed with an area code and number for tracking.]

```
- [ ] [AREA]-01: [Task description]
- [ ] [AREA]-02: [Task description]
- [ ] [AREA]-03: [Task description]
```

---

## 8. Test Plan

[Test cases for this functional area. Each test maps to a task or business rule.]

| Test ID | Description | Type | Covers |
|---|---|---|---|
| | | | |
| | | | |
