# GUI Functional Requirements PRD — Preview Card Amendment

**Version:** 1.0
**Last Updated:** 2026-02-23
**Status:** Draft — Proposed amendment to GUI Functional Requirements PRD
**Parent Document:** [gui-functional-requirements-prd.md]

---

## 1. Purpose

This amendment adds the **Preview Card** as the eleventh Card Type in the Card-Based Architecture (Section 15.5) and updates Preview Mode behavior across Window Types (Section 14) to use it.

The Preview Card addresses a gap in the current architecture: Preview Mode currently renders the same Identity Card + Card Layout Area structure as View Mode, just with less data. In practice, the browsing use case ("do I need to open this?") calls for a fundamentally different presentation — a single, self-contained reading surface optimized for scanning, not a decomposed set of cards optimized for comprehensive display.

---

## 2. Changes to Section 14.3 — Display Modes

**Current definition of Preview Mode:**

> Compact, read-only summary. Enough information to identify the record and scan key attributes without opening it fully.

**Amended definition of Preview Mode:**

> Compact, read-only summary optimized as a decision aid — the user is deciding whether to open the full View. Renders a single **Preview Card** as the sole occupant of the Window. No Identity Card, no Card Layout Area. The Preview Card is a self-contained reading surface with no action buttons, no editing affordances, and no chrome beyond the content itself. Each entity type defines its own Preview Card rendering.

---

## 3. Changes to Section 14.4.1 — Docked Window

**Current text (relevant excerpt):**

> Contains an Identity Card (top) and Card Layout Area below in a single-column stack. Supports Preview Mode (default when arrowing through rows), View Mode, and Edit Mode.

**Amended text:**

> In **Preview Mode** (default when arrowing through rows), the Docked Window renders only the focused record's **Preview Card** — a single, self-contained reading surface with no Identity Card and no Card Layout Area. In **View Mode** and **Edit Mode**, the Docked Window renders the Identity Card (top) and Card Layout Area below in a single-column stack.

---

## 4. Changes to Section 14.4.3 — Undocked Window

The Undocked Window supports Preview Mode. When operating in Preview Mode, the Undocked Window renders only the Preview Card, following the same rule as the Docked Window. The Preview Card adapts to whatever space the Undocked Window provides — a small undocked window shows a compact preview; a large undocked window shows more content without artificial truncation.

---

## 5. Changes to Section 14.4.4 — Floating Unmodal

**Current text (relevant excerpt):**

> Shows the referenced entity in Preview Mode — enough to identify the record and see key attributes. Lightweight: loads only the Identity Card and a minimal set of Attribute Cards.

**Amended text:**

> Shows the referenced entity in Preview Mode via the entity's **Preview Card**. No Identity Card or Attribute Cards — the Preview Card is the sole content. Lightweight and self-contained.

---

## 6. Changes to Section 15.5 — Card Type System

Add the Preview Card as the eleventh Card Type:

| Card Type | Purpose | Content | Example Usage |
|---|---|---|---|
| **Preview Card** | Decision aid for browsing — "do I need to open this?" | Entity-defined, self-contained reading surface. Combines identity, key attributes, and primary content into a single card. Read-only — no action buttons, no editing affordances. | Email: sender + recipients + subject + body preview. Contact: name + company + title + last interaction. Task: title + status + assignee + due date. |

### 6.1 Preview Card Specification

The Preview Card is the sole occupant of any Window operating in Preview Mode. It replaces the Identity Card + Card Layout Area combination used in View Mode and Edit Mode.

**Design principles:**

- **Decision aid, not destination.** The Preview Card helps the user decide whether to open the full View. It answers "do I need to look at this?" and nothing more.
- **Self-contained.** The Preview Card combines identity information, key attributes, and primary content into a single reading surface. There is no separate Identity Card above it.
- **Read-only.** No action buttons, no editing affordances, no interactive controls. Actions are performed on the grid row (context menu, action buttons), not on the Preview Card.
- **Fluid.** The Preview Card fills all available space in its container. Content is never artificially truncated — if the container is large enough to show the full content, it shows the full content. If the content exceeds the available space, the card scrolls.
- **Channel/entity-aware.** Each entity type defines its own Preview Card rendering. A Communication renders differently than a Contact, which renders differently than a Task. Within Communications, different channels may render differently (email vs. SMS vs. phone call).
- **No data duplication with View Mode.** The Preview Card and the View Mode Identity Card may show overlapping information (e.g., both show a contact's name). This is acceptable because they never appear simultaneously — Preview Mode shows only the Preview Card, View Mode shows only the Identity Card + Card Layout Area.

**Rendering rules:**

- Fields are rendered as formatted values, not as labeled input controls (same as Identity Card)
- Empty fields are omitted entirely — no placeholders, no labels without values (same as all cards)
- Related entity fields render as plain text in the Preview Card (not clickable links — the Preview Card is non-interactive)
- Entity-specific PRDs define exactly which fields and content appear in their Preview Card

---

## 7. Changes to Section 15.2 — Window Header

No changes. The Window Header continues to show the Maximize, Undock, and Close buttons. These are container-level controls, not card-level controls, and remain available in Preview Mode.

---

## 8. Summary of Architectural Impact

| Component | Before | After |
|---|---|---|
| Preview Mode in Docked Window | Identity Card + Card Layout Area (compact) | Preview Card only |
| Preview Mode in Undocked Window | Identity Card + Card Layout Area (compact) | Preview Card only |
| Preview Mode in Floating Unmodal | Identity Card + minimal Attribute Cards | Preview Card only |
| View Mode (all Window Types) | Identity Card + Card Layout Area | No change |
| Edit Mode (all Window Types) | Identity Card + Card Layout Area (editable) | No change |
| Card Type count | 10 | 11 |
| Entity PRD responsibility | Define Identity Card fields, Card Layout Area configuration | Also define Preview Card rendering |

---

## Related Documents

| Document | Relationship |
|---|---|
| [GUI Functional Requirements PRD](gui-functional-requirements-prd.md) | Parent document this amendment modifies |
| [Communication — View Communication Sub-PRD](communication-view-prd.md) | First entity-specific implementation of the Preview Card |
| [Master Glossary](glossary.md) | Preview Card term definition should be added |
