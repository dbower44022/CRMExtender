# Product Requirements Document: Adaptive Grid Intelligence

## CRMExtender — Display-Aware Layout Engine & Content-Intelligent Grid Optimization

**Version:** 2.0
**Date:** 2026-02-21
**Status:** Draft — Terminology framework update
**Parent Document:** [CRMExtender PRD v1.1](PRD.md)

> **V1.0 (2026-02-20):**
> Initial specification. Defined display-aware layout engine, content-intelligent grid optimization, space budget engine, column width allocation, value diversity analysis, preview panel intelligence, user override persistence model, and phasing roadmap.
>
> **V2.0 (2026-02-21):**
> Terminology alignment with Master Glossary V3 and GUI Functional Requirements PRD V2. Renamed: Icon Rail → Entity Bar, Top Header Bar → Application Tool Bar, Grid Toolbar → Content Tool Bar, Four-Zone Layout → Workspace Layout, Preview Panel → Detail Panel (layout zone). Retitled Section 13 from "Preview Panel Intelligence" to "Detail Panel Intelligence." Retitled Section 14 from "Navigation Sidebar Adaptation" to "Action Panel Adaptation." Updated Section 13.3 internal content adaptation from three-zone model (Identity/Context/Activity Timeline) to Card-Based Architecture (Identity Card + Card Layout Area). Updated Section 7.3 to include Application Status Bar in viewport calculation. Updated all cross-PRD references to GUI PRD V2 section numbers. Replaced local glossary with cross-reference to Master Glossary V3.
>
> This document defines the Adaptive Grid Intelligence system — an intelligent layout engine that automatically optimizes the entire workspace (grid, Detail Panel, Action Panel) based on display characteristics, data content analysis, and user preferences. The system eliminates the need for manual layout configuration by anticipating user needs and adapting the UI to deliver maximum information density on any screen.
>
> This PRD is additive to the [Views & Grid PRD](views-grid-prd_V4.md) and [GUI Functional Requirements PRD](gui-functional-requirements-prd_V2.md). It does not replace any existing specifications — it defines an intelligent optimization layer that operates on top of the existing column system, zone layout, and view persistence model. Where this PRD extends or refines behaviors defined in those PRDs, the changes are called out explicitly in the Cross-PRD Reconciliation section.
>
> **Scope:** Grid/List views only. The design patterns established here are intentionally extensible to Board, Calendar, and Timeline views in future phases.
>
> **Tech stack context:** Flutter frontend (cross-platform: web, macOS, Windows, Linux), Python FastAPI backend, PostgreSQL with schema-per-tenant isolation.

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Problem Statement](#2-problem-statement)
3. [Goals & Success Metrics](#3-goals--success-metrics)
4. [User Personas & Stories](#4-user-personas--stories)
5. [Core Concepts & Terminology](#5-core-concepts--terminology)
6. [Design Philosophy](#6-design-philosophy)
7. [Display Detection & Viewport Analysis](#7-display-detection--viewport-analysis)
8. [Workspace Space Budget Engine](#8-workspace-space-budget-engine)
9. [Content Analysis Engine](#9-content-analysis-engine)
10. [Intelligent Column Width Allocation](#10-intelligent-column-width-allocation)
11. [Content-Aware Cell Alignment](#11-content-aware-cell-alignment)
12. [Value Diversity Analysis & Column Demotion](#12-value-diversity-analysis--column-demotion)
13. [Detail Panel Intelligence](#13-detail-panel-intelligence)
14. [Action Panel Adaptation](#14-action-panel-adaptation)
15. [Vertical Density Optimization](#15-vertical-density-optimization)
16. [Auto-Configuration Lifecycle](#16-auto-configuration-lifecycle)
17. [User Override Persistence Model](#17-user-override-persistence-model)
18. [View Settings Extensions](#18-view-settings-extensions)
19. [Column Priority Hierarchy](#19-column-priority-hierarchy)
20. [Data Model & Storage](#20-data-model--storage)
21. [API Design](#21-api-design)
22. [Performance Considerations](#22-performance-considerations)
23. [Design Decisions](#23-design-decisions)
24. [Cross-PRD Reconciliation](#24-cross-prd-reconciliation)
25. [Phasing & Roadmap](#25-phasing--roadmap)
26. [Dependencies & Related PRDs](#26-dependencies--related-prds)
27. [Open Questions](#27-open-questions)
28. [Future Work](#28-future-work)
29. [Glossary](#29-glossary)

---

## 1. Executive Summary

The Adaptive Grid Intelligence system transforms the CRMExtender grid from a static, manually-configured layout into an intelligent workspace that automatically optimizes itself for the user's display, data, and preferences. The goal is to make every view feel like it was hand-tuned for the user's specific monitor, window size, and the data they're looking at — eliminating the tedious column-resizing and panel-adjusting that plagues every grid-based application.

The system operates at three interconnected levels:

**Display-aware workspace allocation** — The layout engine detects the physical display characteristics (resolution, DPI, effective viewport after navigation and panels) and uses this as the foundation for dividing space among the Workspace Layout zones (Entity Bar, Action Panel, grid, Detail Panel). A 4K 27" monitor with 30 columns of data feels completely different from a 1080p laptop showing 5 columns.

**Content-intelligent column optimization** — Instead of applying static default widths per field type, the system samples the actual data in the current result set and makes per-column decisions about width, alignment, and visibility. A "Messages" column holding single-digit numbers gets 60px. A "Subject" column with 80-character strings gets priority space. A "Status" column where every row says "active" gets demoted to minimal width or collapsed entirely.

**User-learning adaptive defaults** — When a user manually adjusts the layout (widens a column, resizes the Detail Panel, changes row density), the system captures those adjustments as proportional overrides and applies them as constraints in future auto-configurations. The system anticipates on first open; the user refines; the system remembers. No one should ever have to configure the same view twice.

**Core principle:** The system auto-configures when a view is opened and when the display is significantly resized. After configuration, the system steps back and lets the user work without interference. The user always knows better — the system's job is to deliver a great starting point, not to impose its will.

**Relationship to other PRDs:** This PRD extends the column system defined in the [Views & Grid PRD](views-grid-prd_V4.md), the Workspace Layout and responsive breakpoints defined in the [GUI Functional Requirements PRD](gui-functional-requirements-prd_V2.md), and the view persistence model defined in the [Views & Grid PRD, Section 17](views-grid-prd_V4.md#17-view-persistence--sharing).

---

## 2. Problem Statement

Grid-based CRM applications suffer from a universal layout problem: they apply static, field-type-based column widths and fixed panel proportions regardless of the actual data being displayed or the physical display being used. This creates several concrete failures:

**Primary identifier columns are starved.** The most important column in any grid — typically a name or subject — receives the same default width as every other text column. On a Conversations grid, subjects like "Bower - Cashout Refinance" truncate to "Bower - Cashout ..." while less valuable columns consume horizontal space displaying single-digit numbers or repetitive status values.

**Uniform-value columns waste space.** When every row in a "Status" column displays "active," the column delivers zero differentiating information but consumes the same width as if it had diverse values. This is premium screen real estate showing the user nothing they couldn't infer from a single header annotation.

**Detail Panels ignore their content.** The Detail Panel typically receives a fixed percentage of screen width regardless of whether it's displaying a three-line summary or a full conversation timeline. The grid and Detail Panel don't negotiate — the grid starves while the Detail Panel hoards space it isn't using, or vice versa.

**Monitor capability is ignored.** A user with a 4K 27" display at 2x scaling has roughly 1920px of effective horizontal space. A user with the same display at 1.5x scaling has ~2560px. The same user on a 1080p laptop has ~1920px but in a physically smaller viewport with different readability characteristics. Current systems treat all three identically.

**Manual adjustments don't persist intelligently.** Users invest time configuring column widths for their data, then lose those adjustments when they open the view on a different monitor, resize their window, or the system re-renders. The adjustments were stored as absolute pixel values that have no meaning on a different display.

**Vertical space is an afterthought.** Row height is typically a global setting (compact/standard/comfortable) that doesn't adapt to the actual data density. A view with 200 records on a 4K display should show more rows than the same view with 15 records — but both get the same row height.

The net result is that users spend significant time on every session manually configuring layouts that the system should have gotten right from the start. For a product whose core philosophy is information density, this represents a fundamental failure to optimize the most basic resource: screen space.

---

## 3. Goals & Success Metrics

### 3.1 Goals

**G1 — Zero-configuration first open.** A user opening any view for the first time should see a layout optimized for their display and data with no manual adjustments needed.

**G2 — Persistent learning.** A user who adjusts a view's layout should never need to make the same adjustment again, across sessions and display configurations.

**G3 — Display-adaptive.** The same view should feel equally well-configured on a 4K 27" monitor, a 1440p ultrawide, and a 1080p laptop — each receiving a layout optimized for its specific characteristics.

**G4 — Content-intelligent.** Column widths, alignment, and visibility should reflect the actual data in the current result set, not static field-type defaults.

**G5 — Unified workspace optimization.** The grid, Detail Panel, and Action Panel should function as a single intelligent layout, not independent fixed-width panels.

**G6 — Non-intrusive.** After auto-configuration on open/resize, the system does not re-adjust during the session. The user is always in control.

### 3.2 Success Metrics

| Metric | Target | Measurement |
|---|---|---|
| Manual column resize actions per session | <2 (from baseline TBD) | Frontend event tracking |
| Time from view open to first productive interaction | <1.5s (including data load + auto-config) | Performance instrumentation |
| Primary identifier column truncation rate | <10% of visible rows | Content analysis comparison: allocated width vs. content width |
| User override adoption rate | >30% of users store at least one override within 30 days | Override persistence tracking |
| Viewport utilization (horizontal dead space) | <5% of grid area is unused | Layout engine diagnostics |
| Detail Panel content fit | >80% of Detail Panel content visible without scroll on initial load | Content overflow measurement |

---

## 4. User Personas & Stories

### 4.1 Personas

These personas extend the personas defined in the [Views & Grid PRD, Section 4](views-grid-prd_V4.md#4-user-personas--stories) and the [GUI Functional Requirements PRD, Section 3](gui-functional-requirements-prd_V2.md#3-user-personas--stories).

**Power User (Doug)** — Runs a gutter cleaning business across multiple cities. Uses a 4K 27" monitor at 2x scaling. Has dozens of custom views for Conversations, Jobs, Properties, and Contacts. Wants to open any view and immediately see the maximum amount of useful data with zero clicks wasted on layout adjustment. Hates truncated subjects and wasted whitespace.

**Multi-Display User (Sarah)** — Sales rep who uses a 4K external monitor at her desk and a 13" MacBook on the road. Views she configured at her desk should feel equally well-optimized on her laptop — not just scaled down but intelligently re-laid-out, with columns prioritized differently for the smaller viewport.

**New User (Mike)** — Just started using CRMExtender. Has never configured a view. Opens the default Conversations grid and expects it to look professional and useful out of the box, with no configuration knowledge required.

### 4.2 User Stories

#### Display Adaptation

- **US-AGI1:** As a user, I want the grid to automatically optimize its layout for my monitor's resolution and DPI so that I see the maximum useful information without manual adjustment.
- **US-AGI2:** As a user, I want the layout to adapt when I resize my browser window significantly so that columns and panels re-proportion to the new viewport.
- **US-AGI3:** As a user, I want my view to look equally well-optimized when I move from my desktop monitor to my laptop, without needing to reconfigure anything.

#### Content-Aware Columns

- **US-AGI4:** As a user, I want columns that contain short values (single-digit numbers, checkboxes) to be automatically narrow so that more space is available for content-rich columns.
- **US-AGI5:** As a user, I want the primary identifier column (Name, Subject) to receive priority width allocation so that I can actually read the identifying text without truncation.
- **US-AGI6:** As a user, I want columns where every row has the same value to be automatically minimized or collapsed so that they don't waste space displaying non-differentiating information.
- **US-AGI7:** As a user, I want cell alignment (left, center, right) to be automatically chosen based on the actual content in each column so that the data is maximally scannable.

#### Detail Panel

- **US-AGI8:** As a user, I want the Detail Panel width to adapt based on the complexity of the selected record's content so that the panel uses exactly the space it needs.
- **US-AGI9:** As a user, I want to set a Detail Panel preference (None, Small, Medium, Large, Huge) in view settings and have the auto-configuration engine respect that preference.
- **US-AGI10:** As a user, I want the grid and Detail Panel to negotiate space intelligently — if the grid doesn't need much width, the Detail Panel should be wider, and vice versa.

#### Vertical Optimization

- **US-AGI11:** As a user, I want the system to automatically select the optimal row density based on my display DPI and the number of records in the current result set.
- **US-AGI12:** As a user, I want row height to consider the content of visible columns so that a view with multi-value select fields gets slightly taller rows than a view showing only short text and numbers.

#### User Overrides

- **US-AGI13:** As a user, I want my manual column width adjustments to be remembered as proportional preferences so that they apply meaningfully on different displays.
- **US-AGI14:** As a user, I want to be able to reset my overrides and let the system re-calculate from scratch if my data has changed significantly.
- **US-AGI15:** As a user, I want the auto-configuration to respect my overrides as constraints while still optimizing everything else around them.

---

## 5. Core Concepts & Terminology

| Term | Definition |
|---|---|
| **Layout Engine** | The top-level orchestrator that divides the viewport among the Workspace Layout zones (Entity Bar, Action Panel, grid, Detail Panel) based on display analysis, content analysis, and user preferences. Runs on view open and significant resize. |
| **Content Analysis** | A data sampling process that inspects the current result set to determine per-column characteristics: value lengths, value diversity, data type distribution, and content density. Runs on the initial page of loaded records. |
| **Space Budget** | The total available horizontal pixels after subtracting fixed-width elements (Entity Bar, scrollbar, borders). The space budget is divided among flexible zones (Action Panel, grid columns, Detail Panel) by the layout engine. |
| **Column Weight** | A relative importance score assigned to each column by the content analysis engine, based on field type, content characteristics, and user overrides. Columns with higher weights receive proportionally more of the grid's horizontal space. |
| **Column Demotion** | The process of automatically minimizing or collapsing columns that deliver low information value (e.g., uniform values across all rows, empty columns, redundant data). |
| **Value Diversity Score** | A per-column metric measuring how many distinct values appear in the visible result set relative to the total row count. A column where every row says "active" has a diversity score near 0. A column with unique values per row has a diversity score near 1. |
| **Proportional Override** | A user's manual column adjustment stored as a percentage of grid width rather than an absolute pixel value, enabling meaningful translation across different display configurations. |
| **Display Profile** | A snapshot of the current display characteristics: effective viewport dimensions, device pixel ratio, estimated physical DPI, and breakpoint classification. |
| **Auto-Configuration Event** | A trigger that causes the layout engine to run: view open, significant resize (>15% change in either dimension), or explicit user reset. |
| **Significant Resize** | A viewport dimension change exceeding 15% in width or height from the last auto-configuration. Small adjustments (dragging a window edge by 50px) do not trigger recalculation. |

---

## 6. Design Philosophy

The Adaptive Grid Intelligence system follows six principles that guide all design decisions:

**Anticipate, then defer.** The system makes its best prediction when a view opens, then immediately steps back. It never re-adjusts during a session unless the user explicitly triggers it (via resize or reset). The user is always in control; the system's job is to deliver a great starting point.

**Content is king.** Layout decisions are driven by the actual data being displayed, not by metadata about field types. A Number column holding values 1–9 is treated completely differently from a Number column holding values 100,000–999,999. The data tells the system what it needs.

**Proportional, not absolute.** All layout values — column widths, panel proportions, override preferences — are stored and computed as proportions of available space, not absolute pixel values. This ensures layouts translate meaningfully across displays.

**The workspace is one budget.** The grid, Detail Panel, Action Panel, and their contents are all participants in a single space allocation algorithm. When one zone is compact, the freed space is redistributed to zones that need it. No zone operates in isolation.

**User intent outranks algorithm.** When a user makes a manual adjustment, it becomes a constraint that the algorithm works around. The algorithm optimizes the space the user hasn't claimed. User overrides are never overwritten by auto-configuration.

**Progressive intelligence.** The system starts with heuristics (field type defaults, breakpoint-based panel proportions), enhances with data analysis (content sampling, diversity scoring), and refines with user learning (proportional overrides). Each layer adds precision without requiring the previous layers to change.

---

## 7. Display Detection & Viewport Analysis

### 7.1 Display Profile Construction

On every auto-configuration event, the layout engine constructs a Display Profile by querying the runtime environment:

| Property | Source | Purpose |
|---|---|---|
| **Viewport width** | `window.innerWidth` / Flutter `MediaQuery.of(context).size.width` | Total available horizontal pixels |
| **Viewport height** | `window.innerHeight` / Flutter `MediaQuery.of(context).size.height` | Total available vertical pixels |
| **Device pixel ratio (DPR)** | `window.devicePixelRatio` / Flutter `MediaQuery.of(context).devicePixelRatio` | Physical-to-logical pixel ratio. Indicates scaling (1.0 = no scaling, 2.0 = Retina/4K at 2x) |
| **Estimated physical DPI** | Derived: standard assumption of 96 base DPI × DPR, refined by heuristic (see below) | Readability estimate — affects minimum font size and touch target assumptions |
| **Breakpoint classification** | Per GUI Functional Requirements PRD Section 21.2: XL (≥1920), L (1440–1919), M (1024–1439), S (768–1023), XS (<768) | Determines which zones are available for allocation |

### 7.2 Physical DPI Heuristic

Browsers do not reliably expose the physical screen size, so the system estimates using available signals:

1. **DPR × 96 baseline** — Assumes 96 DPI base and multiplies by DPR. This is accurate for most desktop monitors.
2. **Screen resolution hint** — `window.screen.width` / `window.screen.height` provides the monitor's native resolution. When the viewport is maximized, comparing viewport size to screen resolution reveals the OS-level scaling factor.
3. **User-declared monitor profile** (optional) — In Settings → Display Preferences, users can declare their monitor configuration: "4K 27 inch", "1440p 24 inch", "Laptop 13 inch", etc. This provides the most accurate physical DPI and overrides heuristic estimates.

### 7.3 Effective Viewport Calculation

The effective viewport is the space available after subtracting fixed-width UI elements:

```
Effective Width = Viewport Width
                  - Entity Bar Width (60px, fixed per GUI PRD Section 5)
                  - Vertical Scrollbar (if present, ~15px)
                  - Zone border/divider pixels (~4px total)

Effective Height = Viewport Height
                   - Application Tool Bar (48px, fixed per GUI PRD Section 9.4)
                   - Application Status Bar (24–28px, per GUI PRD Section 10)
                   - Content Tool Bar (40px, fixed per GUI PRD Section 11)
                   - Grid Column Headers (~36px)
                   - Grid Footer / Pagination Bar (~32px)
                   - View Tab Bar (if visible, ~36px)
```

The effective viewport is the canvas that the space budget engine divides among the flexible zones: Action Panel, grid columns, and Detail Panel.

### 7.4 Display Tier Classification

Beyond the GUI PRD's breakpoint system (which determines zone visibility), the layout engine classifies the display into density tiers that influence content analysis thresholds:

| Tier | Effective Width | Characteristics | Layout Implications |
|---|---|---|---|
| **Ultra-wide** | ≥2400px | 4K at 1.5x, ultrawide monitors | All zones generous. Detail Panel can be wide. Grid can show many columns at comfortable widths. |
| **Spacious** | 1920–2399px | 4K at 2x, 1440p at 1x | Primary target. Full Workspace Layout with intelligent allocation. |
| **Standard** | 1440–1919px | 1080p at 1x, 4K at 2.5x | Tighter allocation. Action panel may default to collapsed. Column demotion more aggressive. |
| **Constrained** | 1024–1439px | Laptop, tablet landscape | Aggressive optimization. Detail Panel narrows significantly or becomes overlay. Low-value columns hidden. |
| **Minimal** | <1024px | Small laptop, tablet portrait | Single-zone focus. Auto-configuration defers to the GUI PRD's progressive collapse rules. |

---

## 8. Workspace Space Budget Engine

### 8.1 Overview

The Space Budget Engine is the top-level allocator. It takes the effective viewport dimensions and divides horizontal space among the three flexible zones: Action Panel, grid, and Detail Panel. The Entity Bar is fixed-width and excluded from the budget.

The engine operates in two passes:

**Pass 1 — Zone allocation:** Divide the effective width among the Action Panel, grid, and Detail Panel based on display tier, view settings, and user overrides.

**Pass 2 — Within-zone optimization:** The grid zone is subdivided among columns by the Column Width Allocation engine (Section 10). The Detail Panel zone is optimized by the Detail Panel Intelligence engine (Section 13). The Action Panel is optimized by the Action Panel Adaptation engine (Section 14).

### 8.2 Zone Allocation Algorithm

The allocation uses a weighted-percentage model where each zone has a target percentage, a minimum width, and a maximum width. The targets are adjusted based on display tier, view settings, and content signals.

**Base allocation targets (Spacious tier, default settings):**

| Zone | Target % | Min Width | Max Width |
|---|---|---|---|
| Action Panel | 15% | 200px | 400px |
| Grid | 50% | 300px | No max |
| Detail Panel | 35% | 320px | 800px |

**Allocation adjustments by display tier:**

| Tier | Action Panel | Grid | Detail Panel |
|---|---|---|---|
| Ultra-wide | 12% | 48% | 40% |
| Spacious | 15% | 50% | 35% |
| Standard | 0% (collapsed to overlay) | 60% | 40% |
| Constrained | 0% (overlay) | 65% | 35% (or overlay) |
| Minimal | 0% (overlay) | 100% | 0% (overlay) |

**Adjustment by view settings:**

The user's Detail Panel preference (Section 18) modifies the Detail Panel allocation:

| Detail Panel Preference | Detail Panel Adjustment |
|---|---|
| None | 0% — grid takes full width |
| Small | 20% (min 280px) |
| Medium | 35% (default) |
| Large | 45% (max 900px) |
| Huge | 55% (max 1100px) |

**Adjustment by content signals:**

After the content analysis engine runs (Section 9), the zone allocation may be refined:

- If the grid has few columns with compact data, the grid zone shrinks and the Detail Panel gains the freed space.
- If the grid has many columns with wide content, the grid zone grows and the Detail Panel narrows (down to its minimum).
- If the Action Panel contains only a few short view names, it can compact below the base allocation.
- If the Action Panel contains long view names or deep folder trees, it receives additional space on Ultra-wide and Spacious tiers.

### 8.3 Allocation Execution

The allocation is computed in order of priority:

1. **Fixed zones** — Entity Bar (60px), scrollbar, dividers.
2. **User-locked zones** — If the user has manually resized a zone (via splitter drag), that zone's width is converted to a proportional override and treated as a constraint.
3. **Preference-driven zones** — The Detail Panel allocation based on the user's Detail Panel preference setting.
4. **Remaining space** — Allocated to the grid.

The grid zone's allocation then becomes the input to the Column Width Allocation engine.

### 8.4 Splitter Behavior Integration

The existing splitter bar (GUI PRD Section 4.3) continues to function as documented. The Adaptive Grid Intelligence system integrates with it as follows:

- **On auto-configuration:** The splitter position is set by the space budget engine. If the user has a proportional override for the splitter, that override is applied instead.
- **On user drag:** The new splitter position is captured as a proportional override (Section 17) and persisted. The auto-configuration engine does not move the splitter again until the next auto-configuration event.
- **On double-click:** The splitter resets to the auto-configured position (re-runs the space budget engine for the current display), clearing the user's splitter override.

---

## 9. Content Analysis Engine

### 9.1 Overview

The Content Analysis Engine inspects the actual data in the current result set to derive per-column characteristics that drive width allocation, alignment, and demotion decisions. It runs during auto-configuration, after the data for the first page of results has loaded.

### 9.2 Sampling Strategy

The engine analyzes the first page of loaded records (typically 50 records per the Views & Grid PRD Section 19.2). For views with fewer than 50 records, all records are analyzed. The analysis is performed client-side on the loaded data — it does not require additional API calls.

### 9.3 Per-Column Metrics

For each visible column, the engine computes:

| Metric | Description | Used By |
|---|---|---|
| **Max content width** | The rendered pixel width of the longest value in the sample (using the current font and size). Measured via a hidden measurement element or text metrics API. | Column width allocation |
| **Median content width** | The rendered pixel width at the 50th percentile of values. Represents the "typical" value width. | Column width allocation |
| **P90 content width** | The rendered pixel width at the 90th percentile. Represents "most values fit without truncation" width. | Column width allocation, truncation targeting |
| **Min content width** | The rendered pixel width of the shortest value (excluding nulls). | Minimum column width |
| **Value diversity score** | `COUNT(DISTINCT non-null values) / COUNT(non-null values)`. Range 0.0–1.0. | Column demotion |
| **Null ratio** | `COUNT(null values) / COUNT(total rows)`. | Column demotion |
| **Dominant value** | If diversity score < 0.1, the most common value. | Column demotion annotation |
| **Numeric range** | For numeric columns: `[min_value, max_value]`. | Alignment decision |
| **Digit count range** | For numeric columns: `[min_digits, max_digits]` (including decimal separator and currency symbol if applicable). | Alignment decision |
| **Content type distribution** | Percentage of values that are: short text (≤20 chars), medium text (21–60 chars), long text (>60 chars), numeric, empty. | Alignment decision, width allocation |

### 9.4 Analysis Timing

The content analysis runs:

1. **On auto-configuration** — When the view is opened or significantly resized, after the first page of data loads.
2. **On data source change** — When the user switches to a different data source or the data source's filters change significantly (causing a full re-query), the analysis re-runs.

The analysis does **not** re-run on:
- Arrow-key navigation between rows
- Inline edits to individual cells
- Scroll events loading additional pages
- Temporary overlay filter changes (these refine the existing layout, they don't trigger full reanalysis)

### 9.5 Performance Budget

The content analysis must complete within **50ms** on the client. Since it operates on already-loaded data (50 records × ~10 columns = ~500 cells), this is achievable with simple iteration. The text measurement step (computing rendered pixel widths) is the most expensive operation; the engine should batch-measure using a shared hidden DOM/Canvas element rather than measuring each cell individually.

---

## 10. Intelligent Column Width Allocation

### 10.1 Overview

The Column Width Allocation engine takes the grid zone's available width (from the space budget engine) and divides it among the visible columns based on content analysis metrics, field type heuristics, column priority (Section 19), and user overrides.

### 10.2 Allocation Algorithm

The allocation proceeds in stages:

**Stage 1 — Fixed-width columns.** Some columns have a natural maximum width that content analysis cannot exceed. These are allocated first and subtracted from the available budget:

| Column Type | Fixed Width Logic |
|---|---|
| Checkbox | Always 48px (icon + padding) |
| Rating | `max_stars × 20px + padding` (typically 120px for 5-star) |
| Row action menu ("...") | 40px |
| Row selection checkbox | 40px |

**Stage 2 — User override columns.** Columns with user proportional overrides (Section 17) are allocated their overridden percentage of the remaining grid width. These are treated as constraints.

**Stage 3 — Demoted columns.** Columns flagged for demotion by the diversity analysis (Section 12) are allocated their minimal width (typically 60–80px for a collapsed indicator, or 0px if fully hidden).

**Stage 4 — Natural-width columns.** Columns where the P90 content width is less than or equal to a reasonable maximum (e.g., 200px) are allocated their P90 width. These are columns that "fit naturally" — dates, phone numbers, short numeric values — and don't need more space than their content requires.

**Stage 5 — Weighted distribution.** The remaining available width is distributed among the remaining columns (typically text-heavy columns like Name, Subject, Description, Email) proportionally to their column weights.

### 10.3 Column Weight Calculation

Each column's weight is determined by combining its priority class (Section 19) with its content characteristics:

```
Column Weight = Priority Multiplier × Content Need Score
```

**Priority Multiplier** (from Section 19):

| Priority Class | Multiplier |
|---|---|
| Primary identifier (first text column, Name/Subject) | 3.0 |
| High-value differentiating (diverse text columns) | 2.0 |
| Standard columns | 1.0 |
| Low-diversity columns (not yet demoted) | 0.5 |

**Content Need Score:**

```
Content Need Score = (P90 Content Width - Allocated Width So Far) / P90 Content Width
```

This ensures columns that are furthest from showing their content untrimmed receive the most additional space.

### 10.4 Minimum and Maximum Column Widths

| Column Category | Minimum Width | Maximum Width |
|---|---|---|
| Primary identifier | 150px | 50% of grid width |
| Text columns | 80px | 40% of grid width |
| Number/Currency | 50px | 200px |
| Date | 80px | 200px |
| Datetime | 100px | 220px |
| Select (single) | 60px | 250px |
| Select (multi) | 80px | 300px |
| Email | 100px | 300px |
| Phone | 80px | 180px |
| URL | 80px | 300px |
| Relation | 80px | 300px |
| User | 80px | 200px |
| Formula/Rollup | 50px | 250px |
| Duration | 60px | 150px |

### 10.5 Content-Driven Format Adaptation

When the allocated width is smaller than the natural content width, some field types can adapt their display format to fit:

| Field Type | Full Format | Compressed Format | Trigger |
|---|---|---|---|
| Date | "February 15, 2026" | "Feb 15, 2026" → "2/15/26" | Width < 140px → < 100px |
| Datetime | "Feb 15, 2026 3:30 PM" | "2/15/26 3:30p" → "3:30p 2/15" | Width < 180px → < 120px |
| Duration | "2 hours 30 minutes" | "2h 30m" → "2:30" | Width < 140px → < 80px |
| Currency | "$1,234,567.89" | "$1.23M" → "$1M" | Width < 120px → < 80px |
| Number | "1,234,567" | "1.23M" → "1M" | Width < 100px → < 70px |
| Relative time | "3 days ago" | "3d ago" → "3d" | Width < 100px → < 60px |
| Email | "john.smith@longdomain.com" | "john.sm...@longd..." | Width < 180px |
| URL | "https://www.example.com/path/to/page" | "example.com/..." | Width < 160px |

Format adaptation is a display-only transformation — the underlying data value is unchanged.

### 10.6 Horizontal Overflow Handling

If the total of all minimum column widths exceeds the available grid width:

1. Columns are hidden in reverse priority order (lowest priority first) until the remaining columns fit at their minimum widths.
2. Hidden columns are accessible via the existing "Add Column" picker and are annotated as "auto-hidden due to space constraints."
3. The user can always manually show any hidden column, which creates a user override that prevents future auto-hiding of that column.

---

## 11. Content-Aware Cell Alignment

### 11.1 Overview

Cell alignment is determined dynamically based on the actual content in each column, not statically based on field type. The content analysis engine provides the data needed to make intelligent alignment decisions.

### 11.2 Alignment Decision Rules

The alignment engine evaluates columns in the following order, with the first matching rule determining the alignment:

**Rule 1 — User override.** If the user has set an explicit alignment override for this column, use it unconditionally.

**Rule 2 — Numeric alignment by range.**

| Condition | Alignment | Rationale |
|---|---|---|
| All values are single-digit integers (0–9) | Center | Small values look stranded left-aligned; centering improves visual balance in narrow columns. |
| All values are 1–2 digit integers (0–99) | Center | Still compact enough that centering reads well. |
| Values span 3+ digits, or include decimals | Right | Right-alignment stacks digit columns for scanability. Decimal points and thousands separators align visually. |
| Currency, any range | Right | Financial convention; right-alignment enables quick column-scanning of amounts. |
| Mixed numeric and empty | Right (with nulls rendered as centered "—") | Maintain numeric alignment for populated cells. |

**Rule 3 — Temporal alignment by format.**

| Condition | Alignment | Rationale |
|---|---|---|
| Full date/datetime format (≥10 characters, e.g., "Feb 15, 2026") | Left | Long enough that left-alignment reads naturally as text. |
| Compressed date format (<10 characters, e.g., "2/15/26") | Center | Compact values center well in narrow columns. |
| Relative time format (e.g., "3d ago", "2h") | Center | Very compact; centering provides visual balance. |
| Duration in compact format ("2h 30m") | Center | Compact display; centering reads cleanly. |
| Duration in full format ("2 hours 30 minutes") | Left | Long enough for left-alignment. |

**Rule 4 — Categorical alignment.**

| Condition | Alignment | Rationale |
|---|---|---|
| Checkbox / Boolean | Center | Icon/toggle is a fixed small element. |
| Rating (stars) | Center | Star icons are a fixed-width visual element. |
| Select (single) with short values (all ≤12 chars) | Center | Short badges center well within the column. |
| Select (single) with long values (any >12 chars) | Left | Longer labels need left-alignment for readability. |
| Select (multi) | Left | Multiple badges stack left-aligned. |
| User (avatar + name) | Left | Name text drives left-alignment. |

**Rule 5 — Text alignment (default).**

| Condition | Alignment | Rationale |
|---|---|---|
| Median content width ≤ 40% of column width | Center | Values are compact relative to column — centering prevents a left-hugging cluster with empty right space. |
| Median content width > 40% of column width | Left | Standard text reading direction. |

### 11.3 Header Alignment

Column headers follow the same alignment as their cell content. If cells are right-aligned (currency), the header text is also right-aligned. This creates a clean visual column.

### 11.4 Alignment Transitions

When a column's content changes significantly (e.g., after filtering reduces the result set to only single-digit values), alignment is **not** recalculated mid-session. Alignment is only recalculated during auto-configuration events. This prevents jarring visual shifts during normal operation.

---

## 12. Value Diversity Analysis & Column Demotion

### 12.1 Overview

Value Diversity Analysis identifies columns that deliver low or zero differentiating information in the current result set. These columns are candidates for demotion — being minimized, collapsed, or annotated to free horizontal space for more valuable columns.

### 12.2 Diversity Score Calculation

```
Diversity Score = COUNT(DISTINCT non-null values) / COUNT(non-null values)
```

| Diversity Score | Classification | Example |
|---|---|---|
| 0.0 (all same) | Uniform | Status column: every row is "active" |
| 0.01–0.05 | Near-uniform | Status column: 48 "active", 2 "pending" |
| 0.06–0.20 | Low diversity | Priority column: 5 distinct values across 50 rows |
| 0.21–0.50 | Moderate diversity | Category column: 15 distinct values across 50 rows |
| 0.51–1.0 | High diversity | Name column: nearly unique per row |

### 12.3 Demotion Tiers

| Tier | Trigger | Behavior |
|---|---|---|
| **Annotated normal** | Diversity 0.06–0.20 | Column renders normally but receives reduced width allocation (0.5x weight multiplier). |
| **Collapsed indicator** | Diversity 0.01–0.05 | Column collapses to a narrow indicator (60–80px). The column header shows the field name. Cells show a minimal indicator (e.g., a small colored dot for select fields). Hover reveals the full value. |
| **Header-only annotation** | Diversity 0.0 (perfectly uniform) | Column collapses to minimum width. The column header displays the uniform value as an annotation: "Status: active". Cells are empty (the value is communicated once in the header, not repeated per row). Hover on any cell shows the value for confirmation. |
| **Auto-hidden** | Diversity 0.0 AND null ratio > 0.9 | Column is hidden entirely (effectively empty). Available for manual show via column picker. |

### 12.4 Demotion Protection

Certain columns are protected from demotion regardless of diversity score:

- The **primary identifier column** (first text column) is never demoted.
- Columns with **user overrides** (manually resized) are never demoted.
- Columns marked as **pinned** are never demoted to hidden (but may receive collapsed treatment).
- The system's **default columns** for an entity type receive a 1-tier demotion buffer (they are demoted one tier less aggressively than the diversity score suggests).

### 12.5 Demotion Transparency

When a column is demoted, the system provides clear feedback:

- Collapsed columns show a subtle "compressed" icon in the header that the user can click to expand.
- Hidden columns appear in the column picker with a label: "Hidden (all values identical)" or "Hidden (mostly empty)."
- A subtle indicator in the Content Tool Bar shows "3 columns auto-compacted" with a click to expand all.

---

## 13. Detail Panel Intelligence

### 13.1 Overview

The Detail Panel (GUI PRD Section 8) participates in the space budget as an intelligent consumer. Instead of maintaining a fixed width, the panel adapts its width and internal density based on display tier, user preference, and the content of the selected record. The Window Type rendered within the Detail Panel is the Docked Window, which uses the Card-Based Architecture (GUI PRD Section 15) to display record data.

### 13.2 Width Determination

The Detail Panel's width is determined by the space budget engine (Section 8) based on three inputs in priority order:

1. **User preference** — The view-level Detail Panel size setting (None / Small / Medium / Large / Huge) sets the allocation target.
2. **Display tier** — On Constrained and Minimal tiers, the panel may be forced to overlay mode regardless of preference.
3. **Content negotiation** — After the grid's column requirements are assessed, remaining space is redistributed. If the grid has few narrow columns, the panel gets more space. If the grid has many wide columns demanding space, the panel narrows to its minimum.

### 13.3 Internal Content Adaptation

The Detail Panel adapts the Docked Window's internal Card layout based on the allocated width:

| Allocated Width | Internal Behavior |
|---|---|
| ≥600px | Full Card set: Identity Card + Card Layout Area with Attribute Cards, Relation Cards, Activity Card. Activity Card entries show multi-line content previews. Generous vertical spacing. |
| 480–599px | Standard layout (per GUI PRD Section 15). Activity Card entries show single-line content previews. |
| 360–479px | Compact layout. Attribute Cards collapse to show only populated high-priority fields. Activity Card entries show sender + timestamp only, with content on hover. |
| 280–359px | Minimal layout. Identity Card shows name + primary identifier only. Activity Card is a dense list (sender + time, no content preview). Attribute Cards and Relation Cards are suppressed. |
| <280px | Panel converts to overlay mode. Click-to-expand from a narrow indicator strip. |

### 13.4 Activity Card Entry Density

Within the Activity Card, the Detail Panel adapts entry density based on both width and height:

- **Height-aware:** If the viewport height allows showing ≥8 activity entries, the panel uses standard entry height. If fewer than 5 entries fit, the panel switches to compact entry height (tighter padding, single-line content).
- **Width-aware:** Wider panels show more content per entry (full "From" address, longer content preview, explicit timestamps). Narrower panels progressively truncate (short name only, relative time, no content preview).
- **Content-aware:** Activity Card entries for Communications include content previews extracted from the communication's `content_clean` field. The preview length adapts to available width: 120+ chars at full width, 60 chars at standard, sender-only at compact.

---

## 14. Action Panel Adaptation

### 14.1 Overview

The Action Panel (GUI PRD Section 6) adapts its width and content density as part of the unified space budget.

### 14.2 Width Adaptation

| Display Tier | Action Panel Behavior |
|---|---|
| Ultra-wide | Full width (280–400px). View names display in full. Folder trees show full names. |
| Spacious | Standard width (200–280px). Long view names truncate with ellipsis. |
| Standard | Collapsed to overlay by default (per GUI PRD Section 22.3). |
| Constrained | Always overlay. |
| Minimal | Always overlay. |

### 14.3 Content-Aware Width

When the Action Panel is visible (Ultra-wide and Spacious tiers), the space budget engine checks the content:

- If the longest view name or folder path exceeds the allocated width, the panel widens (up to max) if the grid has available space to give.
- If all view names are short (≤15 characters), the panel narrows below the base allocation, giving freed space to the grid.

---

## 15. Vertical Density Optimization

### 15.1 Overview

Vertical space affects information density as critically as horizontal space. The system automatically selects the optimal row density based on display characteristics, result set size, and column content.

### 15.2 Auto-Density Selection

The system selects from three density modes (extending the GUI PRD Section 24.3 density settings):

| Density | Row Height | Padding | Line Height |
|---|---|---|---|
| **Compact** | 32–36px | 4–6px vertical | 1.2 |
| **Standard** | 40–44px | 8–10px vertical | 1.4 |
| **Comfortable** | 48–52px | 12–14px vertical | 1.6 |

**Auto-selection logic:**

| Condition | Selected Density | Rationale |
|---|---|---|
| Display tier Ultra-wide or Spacious AND result set > 50 records | Compact | Power user on large screen with lots of data — maximize visible rows. |
| Display tier Ultra-wide or Spacious AND result set ≤ 50 records | Standard | Enough space to breathe; comfortable scanning. |
| Display tier Standard | Compact | Tighter display needs tighter rows. |
| Display tier Constrained or Minimal | Standard | Smaller screens need touch-friendly rows with sufficient hit targets. |
| Any column contains multi-select with avg >2 selections per cell | +1 tier (e.g., Compact → Standard) | Multi-value cells need vertical room for badge wrapping. |
| User has explicitly set a density preference | Use user preference | User override always wins. |

### 15.3 Rows-Per-Screen Optimization

After density selection, the engine calculates rows visible per screen:

```
Visible Rows = (Effective Height - Fixed Chrome Height) / Row Height
```

If the result set has fewer records than visible rows, the engine does **not** stretch rows to fill the space (this wastes vertical room and looks odd). Instead, the remaining vertical space is available to the Detail Panel's Activity Card, which can expand vertically.

### 15.4 Row Height Content Adaptation

Within a density tier, individual rows may receive slight height adjustments based on content:

- Rows with multi-select values that wrap to 2+ lines receive additional height to prevent badge clipping.
- Rows with multi-line text in expanded view mode receive proportional height.
- Standard rows maintain the tier's base height for visual consistency.

Row height variation is minimized — the goal is a consistent visual rhythm. Only cells with demonstrably clipped content receive additional height, and the increase is limited to 1.5× the base height.

---

## 16. Auto-Configuration Lifecycle

### 16.1 Trigger Events

The auto-configuration engine runs on these events:

| Event | Trigger Condition | Behavior |
|---|---|---|
| **View open** | User navigates to a view (first time or returning) | Full auto-configuration: display detection → space budget → content analysis → column allocation → alignment → demotion. |
| **Significant resize** | Viewport width or height changes by >15% from last configuration | Full re-configuration. User overrides are preserved and applied proportionally to the new dimensions. |
| **Data source change** | User switches the view's data source, or filters change producing a substantially different result set (>50% new records) | Content analysis re-runs. Space budget re-runs if content characteristics changed significantly. |
| **User reset** | User explicitly clicks "Reset Layout" or double-clicks the splitter | Full re-configuration ignoring all user overrides. Overrides are cleared. |
| **Display profile change** | User moves window to a different monitor (detected via DPR change or resolution change) | Full re-configuration. User overrides are applied proportionally. |

### 16.2 Events That Do NOT Trigger Reconfiguration

| Event | Reason |
|---|---|
| Arrow-key row navigation | Would cause jarring re-layout on every keystroke |
| Inline cell edit | Editing one value shouldn't shift the entire layout |
| Scroll (loading more rows) | Additional data may differ but the layout should remain stable |
| Detail panel record update | The panel's content changes but its allocated width doesn't |
| Temporary overlay filter add/remove | Refinement, not wholesale data change |
| Small resize (<15% change) | Prevents continuous recalculation during casual window adjustment |

### 16.3 Configuration Sequence

When an auto-configuration event fires:

```
1. Construct Display Profile (Section 7)
   └── Viewport dimensions, DPR, breakpoint, density tier

2. Load User Overrides (Section 17)
   └── Per-view proportional overrides for this display tier

3. Run Space Budget Engine (Section 8)
   └── Divide effective width among zones
   └── Apply user override constraints

4. Wait for first page of data to load
   └── (If data is already cached, proceed immediately)

5. Run Content Analysis Engine (Section 9)
   └── Compute per-column metrics on loaded data

6. Run Column Width Allocation (Section 10)
   └── Assign widths to all columns within grid zone

7. Run Cell Alignment Engine (Section 11)
   └── Determine alignment for each column

8. Run Value Diversity Analysis (Section 12)
   └── Identify and apply column demotions

9. Run Detail Panel Intelligence (Section 13)
   └── Set internal Card density based on allocated width

10. Run Vertical Density Optimization (Section 15)
    └── Select row density tier

11. Apply Layout
    └── Render all zones, columns, and rows with computed dimensions
```

Steps 1–3 can execute immediately on navigation (before data loads) to show the skeleton screen with approximate zone proportions. Steps 4–11 execute after data arrives and refine the layout. The transition from skeleton to final layout should be seamless — zone proportions may shift slightly but the overall structure is stable.

### 16.4 Configuration Performance Target

The full auto-configuration sequence (steps 1–11, excluding data loading) must complete within **100ms**. The layout should feel instant to the user. No perceptible "re-layout jitter" is acceptable.

---

## 17. User Override Persistence Model

### 17.1 Override Capture

When a user manually adjusts a layout element during a session, the adjustment is captured as a proportional override:

| User Action | Captured Override |
|---|---|
| Drag column width | Column slug → proportional width (% of grid zone width) |
| Drag splitter (grid/Detail Panel) | Splitter position → proportional split (% of flexible zone width) |
| Toggle Action Panel open/closed | Action panel state: open/closed (per existing GUI PRD persistence) |
| Manually show a hidden column | Column slug → "force-visible" flag (prevents auto-hide) |
| Manually hide a visible column | Column slug → "force-hidden" flag (prevents auto-show) |
| Change row density | Density preference: compact/standard/comfortable (or "auto") |
| Set explicit column alignment | Column slug → alignment override: left/center/right (or "auto") |

### 17.2 Proportional Storage

All width-related overrides are stored as percentages, not pixels:

```json
{
  "column_overrides": {
    "subject": { "width_pct": 0.35 },
    "status": { "force_hidden": true },
    "messages": { "width_pct": 0.08, "alignment": "center" }
  },
  "splitter_pct": 0.60,
  "density": "compact"
}
```

This ensures that when the user opens the same view on a different display, the overrides translate proportionally. "Subject at 35% of grid width" is meaningful on any monitor.

### 17.3 Override Scope

Overrides are scoped to:

```
User × View × Display Tier
```

This means a user can have different overrides for the same view on different display tiers. The overrides they set on their 4K desktop don't constrain the layout on their laptop — each display tier gets its own override set.

### 17.4 Override Priority

When the auto-configuration engine encounters a user override:

1. The overridden value is treated as a **fixed constraint** — the engine does not recalculate it.
2. The engine optimizes all **non-overridden** values around the constraints.
3. If overrides conflict (e.g., the user has set 3 columns to 35% each, totaling 105%), the engine scales overrides proportionally to fit.

### 17.5 Override Lifecycle

| Event | Effect on Overrides |
|---|---|
| User modifies a layout element | Override created or updated |
| User clicks "Reset Layout" | All overrides for this view × display tier are deleted |
| User double-clicks splitter | Splitter override deleted; splitter returns to auto-configured position |
| View is deleted | Associated overrides are deleted |
| User switches display tier | Overrides from the current tier are used; if none exist, the engine runs without override constraints |

---

## 18. View Settings Extensions

### 18.1 Overview

The view data model (Views & Grid PRD Section 17.1) is extended with the following settings that the user can configure to influence auto-configuration behavior.

### 18.2 New View Settings

| Setting | Type | Options | Default | Description |
|---|---|---|---|---|
| **Detail Panel size** | Enum | `none`, `small`, `medium`, `large`, `huge` | `medium` | Declares the user's preferred Detail Panel allocation. The auto-configuration engine uses this as a target, adjustable based on content negotiation. |
| **Auto-density** | Boolean | `true`, `false` | `true` | When true, the system selects row density automatically. When false, the user's explicit density choice (compact/standard/comfortable) is always used. |
| **Column auto-sizing** | Boolean | `true`, `false` | `true` | When true, column widths are computed by the content analysis engine. When false, columns use the static field-type defaults from the Views & Grid PRD Section 8.3. |
| **Column demotion** | Boolean | `true`, `false` | `true` | When true, uniform/empty columns are automatically demoted. When false, all columns render at normal width regardless of content. |
| **Primary identifier column** | Field reference | Any text field on the entity | Auto-detected (first text column or entity display name field) | Explicitly designates which column receives primary identifier priority in the allocation algorithm. |

### 18.3 Settings UI

These settings are accessible in the View Configuration section of the Action Panel (GUI PRD Section 6.3) under a "Layout Intelligence" subsection. They are also editable in the "Edit View" workflow.

### 18.4 Shared View Behavior

When a shared view has layout intelligence settings configured by the owner, those settings serve as defaults for all viewers. Each viewer's personal overrides (Section 17) layer on top. A viewer can also override the layout intelligence settings via their personal view override, changing (for example) the Detail Panel size from the shared view's "large" to their preferred "small."

---

## 19. Column Priority Hierarchy

### 19.1 Overview

When the layout engine must make allocation or sacrifice decisions — which columns get more space, which get compressed, which get hidden — it follows a defined priority hierarchy.

### 19.2 Priority Classes

Columns are classified into priority tiers based on their role and content characteristics:

| Priority | Class | Examples | Protection Level |
|---|---|---|---|
| **P0 — Identity** | The primary identifier column for the entity type | Contact Name, Conversation Subject, Company Name | Never demoted. Never hidden. Gets space first. Width floor: 150px. |
| **P1 — User-locked** | Columns with user overrides (manually resized, force-visible) | Any column the user has explicitly adjusted | Never auto-hidden. Allocated at user-specified proportion. |
| **P2 — High-value** | Columns with diversity score >0.5 AND content type is text | Email, Description, custom text fields with diverse values | Compressed before hidden. Width floor: 80px. |
| **P3 — Functional** | Relation columns, user columns, status/select with moderate diversity | Assigned To, Project, Status (when diverse) | Compressed before hidden. Width floor: 60px. |
| **P4 — Temporal** | Date and datetime columns | Created Date, Last Activity, Due Date | Natural fixed width. Compresses via format adaptation (Section 10.5). |
| **P5 — Numeric** | Number, currency, duration columns | Message Count, Price, Duration | Naturally compact. Minimum viable width. |
| **P6 — Low-value** | Columns with diversity score <0.1 | Status (when uniform), Type (when all same) | Aggressively demoted. First to be hidden when space is tight. |
| **P7 — Empty** | Columns with null ratio >0.9 | Custom fields not yet populated | Auto-hidden by default. |

### 19.3 Sacrifice Order (Constrained Displays)

When the viewport cannot accommodate all visible columns at their minimum widths, columns are sacrificed (hidden or collapsed) in reverse priority order:

1. P7 — Empty columns hidden first.
2. P6 — Low-value columns collapsed to indicator or hidden.
3. P5 — Numeric columns compressed to minimum width.
4. P4 — Temporal columns switch to most compressed format.
5. P3 — Functional columns compressed to minimum.
6. P2 — High-value text columns compressed (truncation increases).
7. P1 — User-locked columns are never sacrificed.
8. P0 — Identity column is never sacrificed.

---

## 20. Data Model & Storage

### 20.1 User Display Overrides Table

```sql
CREATE TABLE user_view_layout_overrides (
    id              TEXT PRIMARY KEY,            -- ulo_ prefixed ULID
    user_id         TEXT NOT NULL,               -- FK → platform.users
    view_id         TEXT NOT NULL,               -- FK → views(id)
    display_tier    TEXT NOT NULL,               -- 'ultra_wide', 'spacious', 'standard', 'constrained', 'minimal'

    -- Zone-level overrides
    splitter_pct    NUMERIC,                     -- Grid/Detail Panel split as decimal (0.0–1.0)
    density         TEXT,                        -- 'compact', 'standard', 'comfortable', NULL = auto

    -- Column-level overrides (JSONB for flexibility)
    column_overrides JSONB NOT NULL DEFAULT '{}',
    -- Structure: {
    --   "field_slug": {
    --     "width_pct": 0.35,           -- proportion of grid width
    --     "alignment": "center",        -- explicit alignment override
    --     "force_visible": true,        -- prevent auto-hide
    --     "force_hidden": true          -- prevent auto-show
    --   }
    -- }

    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE (user_id, view_id, display_tier)
);

-- Primary lookup path: user opening a view
CREATE INDEX idx_ulo_user_view ON user_view_layout_overrides (user_id, view_id);
```

### 20.2 View Settings Extensions

The view data model (Views & Grid PRD Section 17.1) is extended with the following attributes in the view's configuration JSONB:

```json
{
  "layout_intelligence": {
    "detail_panel_size": "medium",
    "auto_density": true,
    "column_auto_sizing": true,
    "column_demotion": true,
    "primary_identifier_field": null
  }
}
```

These settings are stored within the existing view configuration structure — no new table is required.

### 20.3 User Display Preferences

In the user profile settings (GUI PRD Section 19.2), a new "Display Preferences" section:

```sql
-- Extension to user_preferences (or equivalent user settings table)
-- Stored as JSONB within the user's preferences:
{
  "display_preferences": {
    "monitor_profile": "4k_27",        -- NULL, '4k_27', '1440p_24', '1080p_24', 'laptop_13', 'laptop_15', 'custom'
    "custom_physical_dpi": null,        -- Only if monitor_profile = 'custom'
    "default_density": "auto",          -- 'auto', 'compact', 'standard', 'comfortable'
    "default_detail_panel_size": "medium"  -- Global default; overridden by per-view settings
  }
}
```

---

## 21. API Design

### 21.1 Layout Override Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/api/v1/views/{view_id}/layout-overrides` | GET | Retrieve the current user's layout overrides for this view across all display tiers. |
| `/api/v1/views/{view_id}/layout-overrides/{display_tier}` | PUT | Create or update layout overrides for a specific display tier. Body: `splitter_pct`, `density`, `column_overrides`. |
| `/api/v1/views/{view_id}/layout-overrides/{display_tier}` | DELETE | Delete layout overrides for a display tier (reset to auto-configuration). |
| `/api/v1/views/{view_id}/layout-overrides` | DELETE | Delete all layout overrides for this view (full reset). |

### 21.2 Layout Override Payload

```json
{
  "display_tier": "spacious",
  "splitter_pct": 0.62,
  "density": "compact",
  "column_overrides": {
    "subject": { "width_pct": 0.35 },
    "status": { "force_hidden": true },
    "last_activity": { "alignment": "center" }
  }
}
```

### 21.3 View Settings Update

Layout intelligence settings are updated via the existing view update endpoint:

```
PUT /api/v1/views/{view_id}
```

With the `layout_intelligence` object in the view configuration payload.

### 21.4 User Display Preferences

```
GET  /api/v1/users/me/preferences/display
PUT  /api/v1/users/me/preferences/display
```

---

## 22. Performance Considerations

### 22.1 Auto-Configuration Timing

| Phase | Target | Notes |
|---|---|---|
| Display profile construction | <5ms | Simple property reads |
| User override loading | <20ms | Single DB query, cached after first load |
| Space budget computation | <5ms | Pure arithmetic |
| Content analysis (50 rows × 10 cols) | <50ms | Client-side iteration + text measurement |
| Column width allocation | <10ms | Weighted distribution algorithm |
| Alignment computation | <5ms | Rule evaluation per column |
| Diversity analysis | <10ms | Distinct count per column |
| Total auto-configuration (excluding data load) | <100ms | Must feel instant |

### 22.2 Text Width Measurement

The content analysis engine needs to measure the rendered pixel width of text values. Approaches:

**Preferred (Flutter):** Use `TextPainter.layout()` with the current font and size to compute the width of each string. Batch measurements by creating a single `TextPainter`, updating its `text` property, and calling `layout()` for each value.

**Alternative (Web):** Use an off-screen `Canvas` element with `measureText()`. Create one `CanvasRenderingContext2D` with the correct font, then measure each string. This is significantly faster than DOM-based measurement.

**Caching:** Text measurements for the current data page are cached in memory. They are invalidated when the data page changes or the font/size changes.

### 22.3 Override Persistence Debouncing

When a user drags a column edge or splitter, the resize events fire continuously. Override persistence is debounced:

- During drag: layout updates are applied in real-time (visual feedback).
- After drag ends: a 500ms debounce timer starts. If no further resize occurs, the override is persisted to the server.
- If the user makes multiple adjustments in quick succession, only the final state is persisted.

---

## 23. Design Decisions

| Decision | Choice | Rationale |
|---|---|---|
| **Proportional vs. absolute storage** | Proportional (percentages) | Enables overrides to translate meaningfully across displays. A user's "Subject at 35%" works on 1080p and 4K. |
| **Override scope: per display tier** | Yes — overrides are scoped to User × View × Display Tier | A user's layout preferences may differ between their desktop and laptop. Scoping per tier enables distinct optimization. |
| **Auto-config timing: on open + significant resize** | On open and >15% resize only | Balances responsiveness with stability. The user is never surprised by mid-session re-layout. |
| **Content analysis on first page only** | Yes — 50-record sample | Provides sufficient signal for statistical analysis while keeping computation within the 50ms budget. Full-dataset analysis would require server-side computation or additional API calls. |
| **Alignment: dynamic by content** | Yes — determined by actual values, not field type alone | A Number column with values 1–5 aligns differently than one with values 10,000–99,999. Static field-type alignment misses this. |
| **Column demotion: tiered approach** | Four tiers (annotated → collapsed → header-only → hidden) | Gradual demotion provides transparency. Users see what happened and can override. Abrupt hiding feels like a bug. |
| **Detail Panel: preference-based with negotiation** | User declares preference (small/medium/large), engine adjusts around it | Combines user intent with intelligent adaptation. The preference is a strong signal, not an absolute constraint. |
| **Vertical density: auto with override** | System selects density, user can lock a preference | Most users want "whatever fits best." Power users can lock compact for maximum rows. |
| **Grid-only scope (Phase 1)** | Grid/list views only | Establishes the pattern. Board (card sizing), Calendar (event density), and Timeline (bar height) can adopt the same principles later. |
| **Client-side content analysis** | All analysis runs client-side on loaded data | No additional server queries. The client has the rendered data; measuring it is trivial. Server-side analysis would add latency and complexity. |
| **Override conflict resolution** | Proportional scaling when overrides exceed 100% | If a user sets 3 columns to 35% each, they get 33.3% each. Silent proportional adjustment is less surprising than error messages. |

---

## 24. Cross-PRD Reconciliation

### 24.1 Views & Grid PRD (views-grid-prd_V4.md)

**Section 8.3 — Column Configuration:**
The "Width" property (described as "Pixel width of the column") is extended. Width is now a computed output of the auto-configuration engine, not solely a user-set value. The auto-configured width serves as the initial value; user drag-resize creates a proportional override. The "Default Width (px)" table in Section 8.3 becomes a fallback used only when `column_auto_sizing = false` in the view's layout intelligence settings.

**Section 8.4 — Column Operations → Resize:**
The "Double-click to auto-fit content" behavior is refined. Double-clicking a column header edge now triggers a single-column re-analysis using the content analysis engine for that column specifically, setting the width to the P90 content width (or the maximum allowed by the column priority and available space). This replaces the simple "auto-fit to widest visible cell" behavior.

**Section 9.1 — Field Types and View Behavior → Display Renderer:**
Display renderers now support format adaptation (Section 10.5). Date renderers produce different output depending on the allocated column width. Number/currency renderers use abbreviation at narrow widths. This is a behavioral extension of the existing renderer framework, not a replacement.

**Section 17.1 — View Data Model:**
The view attributes table gains the `layout_intelligence` configuration object (Section 18.2). This is a non-breaking extension — views without this configuration object use the default values.

**Section 22 — Open Questions, Item 5 (Conditional Formatting):**
This PRD does not address conditional formatting (rule-based cell/row color changes). Conditional formatting is a future PRD that builds on the column system and content analysis capabilities defined here.

### 24.2 GUI Functional Requirements PRD (gui-functional-requirements-prd_V2.md)

**Section 4.2 — Zone Dimensions:**
The "Default Width" column for each zone is now the initial allocation of the space budget engine at the Spacious display tier. The min/max constraints continue to apply. The Detail Panel's default width (480px) becomes the output of the space budget engine for a "Medium" Detail Panel preference at the Spacious tier.

**Section 4.3 — Splitter Bar:**
The "Double-click splitter resets to default proportions" behavior is refined. Double-click now resets to the **auto-configured** proportions (re-runs the space budget engine), which may differ from the static "default proportions" if the content analysis suggests a different split. It also clears the user's splitter override.

**Section 22.2 — Breakpoint Definitions:**
The breakpoint system continues as-is. The Adaptive Grid Intelligence display tiers (Section 7.4) are a refinement of the breakpoint system, adding density tier classification within each breakpoint range. The tier system informs layout engine decisions; the breakpoint system continues to govern zone visibility.

**Section 24.3 — Density Setting:**
The three density levels remain as defined. The Adaptive Grid Intelligence system adds an "auto" mode (selected by default) where the system chooses the density. The user can override to a specific density in view settings or global preferences.

### 24.3 Custom Objects PRD (custom-objects-prd_v1.md)

**Section 9.1 — Field Type System:**
No changes to the field type definitions. The content analysis engine reads field type metadata to apply type-specific heuristics (e.g., knowing a column is "Currency" affects alignment rules), but does not modify the field type system.

### 24.4 Permissions & Sharing PRD (permissions-sharing-prd_V1.md)

**Layout overrides are personal data.** A user's layout overrides are never visible to other users, even on shared views. The overrides are scoped to the user and do not affect the shared view definition.

---

## 25. Phasing & Roadmap

### Phase 1 — Core Intelligence (Target: MVP)

- Display profile construction and display tier classification
- Space budget engine with Workspace Layout zone allocation
- Content analysis engine (width metrics, diversity score)
- Column width allocation with weighted distribution
- Content-aware cell alignment
- Value diversity analysis and column demotion (all 4 tiers)
- User override capture and persistence (proportional model)
- View settings extensions (Detail Panel size, auto-density toggle)
- Auto-configuration lifecycle (open + significant resize triggers)

### Phase 2 — Refinement

- Content-driven format adaptation (date compression, number abbreviation)
- Detail Panel internal content adaptation (density modes based on width)
- Action Panel content-aware width
- User display preferences in settings (monitor profile declaration)
- Column priority hierarchy with sacrifice ordering
- Row density auto-selection with content awareness

### Phase 3 — Learning & Extension

- Cross-display-tier override intelligence (learn from desktop overrides to pre-configure laptop layout)
- View template intelligence (new views inherit layout intelligence from similar existing views)
- Extension of adaptive patterns to Board view (card sizing, column width)
- Extension to Calendar view (event card density, day cell content)
- Extension to Timeline view (bar height, sidebar width)

### Phase 4 — Advanced

- Multi-user layout analytics (identify common override patterns across users to improve defaults)
- AI-assisted layout suggestions ("users with similar data typically prefer X layout")
- Dynamic content analysis on scroll (refine layout based on deeper data sampling without disrupting user)
- Workspace layout presets (save and switch between complete workspace configurations)

---

## 26. Dependencies & Related PRDs

| PRD | Dependency Type | Details |
|---|---|---|
| **[Views & Grid PRD](views-grid-prd_V4.md)** | Foundation | Column system (Section 8), field type registry (Section 9), view persistence (Section 17), performance targets (Section 19). This PRD extends these foundations. |
| **[GUI Functional Requirements PRD](gui-functional-requirements-prd_V2.md)** | Foundation | Workspace Layout (Section 4), Splitter Bar (Section 4.3), Detail Panel (Section 8), responsive breakpoints (Section 22), density settings (Section 24.3). This PRD refines and extends these specifications. |
| **[Custom Objects PRD](custom-objects-prd_v1.md)** | Reference | Field type system (Section 9) informs content analysis heuristics. No modifications to the Custom Objects PRD required. |
| **[Data Sources PRD](data-sources-prd.md)** | Reference | Data source query results feed the content analysis engine. No modifications required. |
| **[Permissions & Sharing PRD](permissions-sharing-prd_V1.md)** | Constraint | Layout overrides are personal data and follow user-scoped visibility rules. |

---

## 27. Open Questions

1. **Server-side content hints** — Should the API provide pre-computed content statistics (e.g., max string length per column, distinct value count per column) in the data source metadata, so the client can begin layout estimation before data loads? This would enable better skeleton screen proportions but adds server-side computation cost.

2. **Multi-monitor detection** — Can the system reliably detect when a window moves between monitors with different DPR/resolution? In Flutter desktop, this is detectable via `window.onMetricsChanged`. In web, it may require polling `window.devicePixelRatio`. If detection is unreliable, the system may need a manual "re-detect display" action.

3. **Shared view layout hints** — When a view owner shares a view, should they be able to attach layout hints (e.g., "this view works best with a large Detail Panel") that influence the auto-configuration for other users? This would be separate from the layout intelligence settings (which apply to the view itself) — it would be advice to the layout engine about the owner's design intent.

4. **Animated layout transitions** — When auto-configuration adjusts column widths and panel proportions, should the changes animate smoothly or snap instantly? Animation feels more polished but adds visual complexity during the critical "view just opened" moment. Snap is faster but can feel jarring if proportions differ significantly from the skeleton screen.

5. **Content analysis on filtered subsets** — When a user applies a filter that dramatically changes the result set (e.g., filtering from 200 records to 5), the content characteristics may change significantly. Should the system re-run content analysis on filter changes, even though Section 16.2 says it doesn't? This could be limited to "significant filter changes" (>50% reduction in result count).

6. **Accessibility considerations** — Do minimum column widths and auto-density selection need special handling for users with accessibility needs (larger fonts, high-contrast mode, screen magnification)? The system should detect OS-level accessibility settings and adjust minimums accordingly.

7. **Offline mode** — In the planned offline/SQLite mode, are layout overrides stored locally and synced, or recalculated each time? Local storage seems correct since overrides are user-facing preferences.

---

## 28. Future Work

- **Conditional formatting** — Rule-based cell and row color/style changes. Will build on the content analysis engine's data inspection capabilities. Deferred to a separate PRD.
- **Dashboard layout intelligence** — Apply similar space-budget and content-aware principles to the future Dashboard system.
- **Print/export layout optimization** — Automatically adjust column widths and content formatting for paper output (PDF, printed pages), where the "display" is a fixed-size page.
- **Collaborative layout awareness** — Show subtle indicators when multiple users are viewing the same shared view, potentially sharing layout insights ("3 users have hidden the Status column on this view").
- **Smart column ordering** — Beyond width optimization, automatically order columns by information value (high-diversity, high-priority columns first).

---

## 29. Glossary

All general UI terms used in this PRD are defined in the **[Master Glossary V3](glossary_V3.md)**. The following terms are specific to the Adaptive Grid Intelligence system:

| Term | Definition |
|---|---|
| **Auto-configuration** | The process of automatically computing and applying optimal layout parameters (column widths, panel proportions, alignment, density) based on display characteristics, content analysis, and user preferences. |
| **Column demotion** | Reducing a column's width allocation or visibility based on low information value (uniform or empty content). |
| **Content analysis** | Client-side inspection of loaded data to determine per-column characteristics (value widths, diversity, types) for layout optimization. |
| **Display profile** | A snapshot of the current display characteristics used as input to the layout engine. |
| **Display tier** | A classification of the effective viewport into one of five categories (ultra-wide, spacious, standard, constrained, minimal) that influences layout thresholds and defaults. |
| **Format adaptation** | The ability of a display renderer to produce different output formats (full, compressed, minimal) based on the allocated column width. |
| **Layout engine** | The orchestrator that coordinates display detection, space budgeting, content analysis, and width allocation to produce an optimized workspace layout. |
| **P90 content width** | The 90th-percentile rendered pixel width of values in a column. Used as the target for "most values fit without truncation." |
| **Proportional override** | A user's layout adjustment stored as a percentage of available space, enabling translation across display configurations. |
| **Sacrifice order** | The priority sequence in which columns are compressed or hidden when the viewport cannot accommodate all columns at their minimum widths. |
| **Significant resize** | A viewport dimension change exceeding 15% from the last auto-configuration, triggering a re-configuration event. |
| **Space budget** | The total available pixels to be divided among flexible Workspace Layout zones (Action Panel, grid, Detail Panel). |
| **Value diversity score** | A per-column metric (0.0–1.0) measuring the ratio of distinct values to total values, indicating how much differentiating information the column provides. |
