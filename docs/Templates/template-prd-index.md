# [Product Name] — PRD Index

**Version:** [X.X]
**Last Updated:** [YYYY-MM-DD]
**Purpose:** Living index of all project documents. Reference this at the start of any PRD development session for orientation.

---

## 1. Platform Overview

[Brief product description — what it is, who it's for. No technology stack information — that belongs in the Product TDD.]

---

## 2. Product-Level Documents

| Document | Version | File | Status | Date |
|---|---|---|---|---|
| Product PRD | | | | |
| Product TDD | | | | |
| GUI Standards | | | | |

---

## 3. Entity Document Registry

[Organized hierarchically by entity. Each entity lists its base PRD, UI PRD, TDD (if any), and all action sub-PRDs and action TDDs.]

### 3.1 [Entity Name]

| Document | Version | File | Status | Date |
|---|---|---|---|---|
| Entity Base PRD | | | | |
| Entity UI PRD | | | | |
| Entity TDD | | | | |
| Action: [Name] Sub-PRD | | | | |
| Action: [Name] TDD | | | | |
| Action: [Name] Sub-PRD | | | | |

### 3.2 [Entity Name]

| Document | Version | File | Status | Date |
|---|---|---|---|---|
| Entity Base PRD | | | | |
| Entity UI PRD | | | | |
| Action: [Name] Sub-PRD | | | | |

---

## 4. Retired / Superseded Documents

| Document | File | Superseded By | Date |
|---|---|---|---|
| | | | |

---

## 5. Workflow Notes

**PRD Development:** Use Claude.ai for all requirements and design work. One chat per PRD for clean context. Load this index at the start of every session.

**Implementation:** Use Claude Code for implementation. Direct Claude Code to read a specific document and focus on a specific section. Follow the plan-execute-verify-test cycle.

**Technical Decisions:** When Claude Code encounters implementation decisions, capture them in the appropriate TDD (product, entity, or action level) after discussion and approval.

**High-Level Tracking:** Priority sequencing and cross-entity dependencies are managed in [your project management tool]. Detailed implementation tracking lives in the PRD task lists.

---

*This index is updated after each PRD development session.*
