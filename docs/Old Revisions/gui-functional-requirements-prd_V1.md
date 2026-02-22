# Product Requirements Document: GUI Functional Requirements

## CRMExtender — Application Shell, Navigation, Layout Patterns & Interaction Paradigms

**Version:** 1.0
**Date:** 2026-02-19
**Status:** Draft — Initial specification
**Parent Document:** [CRMExtender PRD v1.1](PRD.md)

> **V1.0 (2026-02-19):**
> This document defines the GUI functional requirements for the CRMExtender production application. It establishes the application shell, navigation architecture, layout patterns, detail viewing modes, editing paradigms, and interaction patterns that all entity-specific interfaces plug into. This PRD is the "container" specification — it defines how the application works as a cohesive product, while entity-specific PRDs (Contacts, Companies, Tasks, etc.) define what appears within these containers.
>
> This PRD does not duplicate interaction specifications already defined in entity-specific PRDs. Grid interactions (inline editing, row expansion, bulk actions, keyboard navigation) are defined in the [Views & Grid PRD](views-grid-prd_V3.md). Field type rendering and data layer behavior are defined in the [Custom Objects PRD](custom-objects-prd.md). Filter, sort, and group mechanics are defined in the [Views & Grid PRD](views-grid-prd_V3.md) and [Data Sources PRD](data-sources-prd.md). Rich text editing is defined in the [Notes PRD](notes-prd_V2.md).
>
> **Tech stack context:** Flutter frontend (cross-platform: web, macOS, Windows, Linux), Python FastAPI backend, PostgreSQL with schema-per-tenant isolation. The web deployment runs as a PWA. Native desktop builds via Flutter's desktop embedding.

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Design Philosophy & Core Principles](#2-design-philosophy--core-principles)
3. [User Personas & Stories](#3-user-personas--stories)
4. [Application Shell — Four-Zone Layout](#4-application-shell--four-zone-layout)
5. [Zone 1: Icon Rail](#5-zone-1-icon-rail)
6. [Zone 2: Action Panel](#6-zone-2-action-panel)
7. [Zone 3: Content Area — Grid](#7-zone-3-content-area--grid)
8. [Zone 4: Detail Panel](#8-zone-4-detail-panel)
9. [Top Header Bar](#9-top-header-bar)
10. [Grid Toolbar](#10-grid-toolbar)
11. [Global Search](#11-global-search)
12. [View-Scoped Quick Filter](#12-view-scoped-quick-filter)
13. [Detail View Modes](#13-detail-view-modes)
14. [Record Detail Layout — Universal Template](#14-record-detail-layout--universal-template)
15. [Section-Based Editing](#15-section-based-editing)
16. [View Management — Temporary Overlays & Persistence](#16-view-management--temporary-overlays--persistence)
17. [Home Screen](#17-home-screen)
18. [Settings & Administration](#18-settings--administration)
19. [Empty States & Zero-Data Experience](#19-empty-states--zero-data-experience)
20. [Loading States, Skeleton Screens & Error Handling](#20-loading-states-skeleton-screens--error-handling)
21. [Responsive Breakpoints & Progressive Collapse](#21-responsive-breakpoints--progressive-collapse)
22. [Global Keyboard Shortcuts](#22-global-keyboard-shortcuts)
23. [Theming & Visual Design Tokens](#23-theming--visual-design-tokens)
24. [Design Decisions](#24-design-decisions)
25. [Phasing & Roadmap](#25-phasing--roadmap)
26. [Dependencies & Related PRDs](#26-dependencies--related-prds)
27. [Open Questions](#27-open-questions)
28. [Future Work](#28-future-work)
29. [Glossary](#29-glossary)

---

## 1. Executive Summary

The GUI Functional Requirements PRD defines the **application shell and interaction paradigms** for CRMExtender. While entity-specific PRDs (Contacts, Companies, Tasks, Conversations, etc.) define what data exists and how it behaves, this document defines how the user navigates between entities, views records, edits data, and interacts with the application as a cohesive product.

The core design philosophy is **information-dense, large-screen-optimized productivity**. CRMExtender is built for users with 4K 27" (minimum) displays who need to review, manage, and act on relationship data with minimal clicks. Every pixel earns its place. Empty space is not "clean" — it's wasted opportunity. The UI should enable a user to review 10 emails in 10 keystrokes, see a contact's complete history on a single scrollable surface, and manipulate view configurations without leaving the data.

The application shell uses a **four-zone layout**: an icon rail for entity navigation, an action panel for view management and configuration, a content area for the primary data grid, and a detail panel for record preview — all visible simultaneously on a large screen. This layout maximizes information density while maintaining clear visual hierarchy and intuitive navigation.

**Core principles:**

- **Information density by default** — The UI is optimized for maximum information per square pixel. Compact rendering is the default, not an option users toggle into. Labels, padding, and decorative whitespace are minimized in favor of actual data.
- **Large-screen-first design** — The primary design target is 4K 27" displays at standard scaling. Smaller screens are supported through progressive collapse, not by designing for mobile and scaling up.
- **View-optimized rendering** — Record detail displays are optimized for reading, not editing. Addresses render as compact formatted text, not six labeled input boxes. Edit mode is a deliberate section-level opt-in.
- **Content-proportional space allocation** — UI sections are sized proportional to the data they contain. Sections with no data are suppressed entirely, not shown as empty placeholders. Sections with extensive data expand to fill available space.
- **No data duplication** — A value appears in exactly one place on screen. If the contact's email is in the identity section, it does not repeat in a sidebar.
- **Keyboard-driven productivity** — Arrow keys navigate between records with instant detail panel updates. The view-scoped search provides a lightweight query language. Section editing uses standard keyboard patterns (Escape to cancel, Enter to confirm).
- **Contextual purity** — Each entity workspace is dedicated to that entity's workflow. Cross-cutting concerns (notifications, dashboards, activity feeds) live on the Home screen, not cluttering entity-specific interfaces.

**Relationship to other PRDs:**

- **[Custom Objects PRD](custom-objects-prd.md)** — Defines the entity type framework, field type system, field groups, and relation types that the GUI renders. Field groups (Section 11) define the sections in the record detail layout. The field type system (Section 9) determines rendering and editing behavior.
- **[Views & Grid PRD](views-grid-prd_V3.md)** — Defines all grid-level interactions: inline editing, row expansion, bulk actions, keyboard navigation within the grid, filter/sort/group mechanics, view persistence, and view sharing. This GUI PRD defines the *shell around* the grid; the Views PRD defines behavior *within* the grid.
- **[Data Sources PRD](data-sources-prd.md)** — Defines the query abstraction layer that feeds views. The action panel's view configuration surfaces data source settings; this PRD defines the UI patterns, the Data Sources PRD defines the underlying query model.
- **[Permissions & Sharing PRD](permissions-sharing-prd_V1.md)** — Defines role-based access controls that determine which edit affordances appear (e.g., the pencil icon is hidden on sections the user cannot edit), which action buttons are available, and which views are accessible.
- **[Notes PRD](notes-prd_V2.md)** — Defines the rich text editing model used wherever content editing appears in the GUI (note sections, task descriptions, communication summaries).
- **All entity PRDs** (Contacts, Companies, Events, Tasks, Documents, Projects, Communications, Conversations) — Each entity PRD defines entity-specific behaviors, field layouts, and section content. This GUI PRD defines the universal template those entities render into.

---

## 2. Design Philosophy & Core Principles

### 2.1 Information Density Over Whitespace

The defining characteristic of CRMExtender's UI is information density. Most modern SaaS applications adopt a mobile-first, whitespace-heavy design that wastes screen real estate on large displays. CRMExtender takes the opposite approach: the UI is designed for users with large screens who need maximum data visibility with minimal clicks.

**Anti-patterns to avoid:**

- Empty field placeholders ("Set Name...", "No phone numbers") consuming space when no data exists
- Labels displayed alongside empty values
- Tabs hiding data that could be visible in scrollable sections
- Repeating the same data in multiple UI locations (e.g., sidebar + main area)
- Fixed-height sections that don't adapt to content volume
- Excessive padding and margins between data elements
- Modals and full-page navigations where inline interactions suffice

**Target patterns:**

- Addresses render as compact formatted text (3 lines), not 6 labeled input fields
- Empty sections are entirely suppressed — if a Contact has no Notes, the Notes section header does not appear
- When a Contact has 50 conversations and 0 tasks, the Conversations section expands to fill the space that Tasks would have occupied
- The detail panel, grid, action panel, and icon rail are all visible simultaneously on a large screen
- Arrow-key navigation through records updates the detail panel instantly — reviewing 10 records takes 10 keystrokes

### 2.2 Large-Screen-First Design

The primary design target is a 4K 27" display (3840×2160 native, typically ~1920×1080 at 2× scaling or ~2560×1440 at 1.5× scaling). At these resolutions, the four-zone layout provides ample space for each zone to display meaningful content.

Smaller screens are supported through **progressive collapse** (Section 21) — zones are hidden or overlaid as the viewport shrinks. The design is never degraded from a mobile starting point; it is optimized for large screens and gracefully reduced for smaller ones.

### 2.3 View-Optimized Rendering

The default state of every record display is **view mode**, optimized for reading and scanning. Edit mode is a deliberate, section-level opt-in triggered by a pencil icon. This means:

- Field values are rendered as formatted text, not as input controls
- Compound fields (address, name) are rendered as a single formatted block, not as individual labeled inputs
- Boolean fields render as descriptive text or icons, not as checkboxes
- Relation fields render as clickable entity names, not as dropdown selectors
- Date fields render as formatted dates ("Feb 19, 2026"), not as date pickers

### 2.4 Content-Proportional Space Allocation

UI sections dynamically allocate vertical space based on the volume of data they contain:

- A section with 0 items is suppressed entirely (no header, no "empty" placeholder)
- A section with 1-3 items renders compactly
- A section with 10+ items expands to fill available space, with internal scrolling if needed
- When one section is suppressed, adjacent sections expand to claim the freed space

This ensures the user always sees the maximum amount of actual data, regardless of which sections have content for any given record.

### 2.5 Contextual Purity

Each entity workspace (the combination of action panel + grid + detail panel for a given entity type) is dedicated entirely to that entity type's workflow. Features that span multiple entity types — notifications, dashboards, activity summaries, onboarding — live on the Home screen, which is a dedicated workspace for cross-cutting concerns.

This principle prevents the gradual creep of global features into entity-specific interfaces, which over time creates cluttered, unfocused screens.

---

## 3. User Personas & Stories

### 3.1 Personas

| Persona | Description | Screen Setup | Primary Need |
|---|---|---|---|
| **Power User (Sam)** | Sales professional managing 200+ contacts, 50+ active conversations, daily email triage | 27" 4K primary + 24" secondary | Maximum information density, keyboard-driven workflow, instant record browsing |
| **Business Owner (Doug)** | Service business operator managing crews, jobs, customers across multiple cities | 27" 4K single monitor | Complete relationship visibility, quick context switching between entity types, action-oriented views |
| **Team Lead (Maria)** | Manages a team of 5, reviews shared views, monitors pipeline health | 24" 1440p | Shared views, bulk operations, dashboard summaries |
| **Occasional User (Tom)** | Uses CRM 2-3 times per week for lookups and basic updates | 15" laptop | Simple navigation, clear visual hierarchy, search-first workflow |

### 3.2 User Stories

#### Application Shell & Navigation

- **US-G1:** As a power user, I want all four zones (rail, action panel, grid, detail panel) visible simultaneously so that I never lose context when navigating or previewing records.
- **US-G2:** As a user, I want to click an entity icon on the rail and have the action panel, grid, and detail panel all update to that entity type's context, loading my last-used or default view.
- **US-G3:** As a user, I want the application to remember my layout preferences (splitter positions, panel open/closed states, last-used view per entity type) across sessions.
- **US-G4:** As a user, I want to customize the order and visibility of entity icons on the rail so that my most-used entities are at the top.

#### Detail Panel & Record Browsing

- **US-G5:** As a power user, I want to arrow through rows in the grid and see the detail panel update instantly with each record's complete information, so that reviewing 10 records takes 10 keystrokes.
- **US-G6:** As a user, I want the detail panel to show a single scrollable surface with all record data — identity fields, context/notes, and activity timeline — without tabs, so I can see everything with a scroll.
- **US-G7:** As a user, I want empty sections to be completely hidden from the detail panel so that space is allocated to sections that have data.
- **US-G8:** As a user, I want to drag the splitter bar between the grid and detail panel to allocate more width to either zone, and have the system remember my preference.
- **US-G9:** As a user, I want to expand the detail panel to full takeover mode (covering the grid) for deep work on a single record, and return to the grid+panel layout when done.
- **US-G10:** As a user on a multi-monitor setup, I want to undock the detail panel into a separate window that I can move to my second screen, while the grid remains on the primary screen with arrow-key navigation still controlling the detail window.

#### View Management

- **US-G11:** As a user, I want the action panel to show me the complete configuration of the current view (filters, sort, grouping) so that I always know exactly what data I'm looking at.
- **US-G12:** As a user, I want to make temporary changes to filters, sort, and grouping from the action panel without affecting the saved view definition.
- **US-G13:** As a user, I want a clear visual indicator when I've applied temporary modifications to a view, and a one-click reset to return to the saved state.
- **US-G14:** As a user, I want to save my temporary modifications as a new personal view with a name I choose.
- **US-G15:** As a user, I want an explicit "Edit View" mode that lets me modify an existing view's saved definition, with the ability to save changes as the new version.

#### Search

- **US-G16:** As a user, I want a global search box in the top header bar that finds any record across all entity types, opening results in a self-contained modal that doesn't disturb my current working state.
- **US-G17:** As a user, I want a view-scoped quick filter at the top of the grid that instantly narrows the current view's results as I type.
- **US-G18:** As a power user, I want the quick filter to support field-name syntax (e.g., `city:Cleveland`, `due:tomorrow`, `revenue:>500000`) for targeted filtering without using the full filter builder.

#### Editing

- **US-G19:** As a user, I want to edit a specific section of a record by clicking its pencil icon, without entering a full-record edit mode that disrupts my view of other sections.
- **US-G20:** As a user, I want the detail panel to display record data in a compact, view-optimized format (addresses as formatted text, not input boxes) that maximizes readability.

---

## 4. Application Shell — Four-Zone Layout

### 4.1 Layout Structure

The application shell consists of four primary zones arranged left to right, plus a fixed top header bar:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          Top Header Bar                                 │
├────┬──────────┬─────────────────────────────┬──────────────────────────┤
│    │          │                             │                          │
│ I  │  Action  │         Content Area        │      Detail Panel        │
│ C  │  Panel   │         (Grid / View)       │      (Record Preview)    │
│ O  │          │                             │                          │
│ N  │  View    │   ┌─────────────────────┐   │   ┌──────────────────┐   │
│    │  config, │   │   Grid Toolbar      │   │   │  Zone 1:         │   │
│ R  │  view    │   ├─────────────────────┤   │   │  Identity        │   │
│ A  │  list,   │   │                     │   │   ├──────────────────┤   │
│ I  │  folder  │   │   Data Grid         │   │   │  Zone 2:         │   │
│ L  │  nav     │   │   (rows + columns)  │   │   │  Context/Notes   │   │
│    │          │   │                     │   │   ├──────────────────┤   │
│    │          │   │                     │   │   │  Zone 3:         │   │
│    │          │   │                     │   │   │  Activity        │   │
│    │          │   │                     │   │   │  Timeline        │   │
│    │          │   │                     │   │   │                  │   │
├────┴──────────┴───┴─────────────────────┴───┴───┴──────────────────┴───┤
```

### 4.2 Zone Dimensions (Reference, at 2× scaling on 4K 27")

| Zone | Default Width | Min Width | Max Width | Resizable |
|---|---|---|---|---|
| Icon Rail | 60px | 60px | 60px | No — fixed width |
| Action Panel | 280px | 200px | 400px | Yes — drag right edge |
| Content Area (Grid) | Flexible — fills remaining space | 300px (≈2 columns) | No maximum | Yes — via splitter |
| Detail Panel | 480px | 320px | 800px | Yes — via splitter |

**Total at defaults (2× scaling, 1920px effective width):** 60 + 280 + 620 + 480 = 1440px content + chrome. At 1.5× scaling (2560px effective), the grid gains ~640px of additional width.

### 4.3 Splitter Bar

A draggable splitter bar divides the Content Area (Grid) from the Detail Panel. The user can drag the splitter to allocate width between these two zones:

- **Drag left:** Grid shrinks (down to ~2 visible columns), detail panel widens for more comprehensive record display
- **Drag right:** Grid widens (more columns visible), detail panel narrows to essential fields only
- **Double-click splitter:** Resets to default proportions
- **Splitter position is persisted** per user per entity type — a user may want a narrow grid for email triage (where the detail panel matters most) but a wide grid for a Company pipeline view (where column data matters most)

### 4.4 Zone Visibility States

| State | Rail | Action Panel | Grid | Detail Panel | Trigger |
|---|---|---|---|---|---|
| **Full layout** | Visible | Open | Visible | Open | Default on large screens |
| **Grid focus** | Visible | Collapsed | Full width | Closed | No row selected, action panel toggled off |
| **Detail focus** | Visible | Collapsed | Narrow (1-2 cols) | Wide | Splitter dragged far left |
| **Full takeover** | Visible | Open/collapsed | Hidden | Full content width | User activates full detail mode |
| **Action collapsed** | Visible | Collapsed (0px) | Wider | Open | User toggles action panel off |

---

## 5. Zone 1: Icon Rail

### 5.1 Purpose

The icon rail is the outermost navigation layer. It provides single-click switching between entity type workspaces and access to the Home screen, Settings, Help, and user profile.

### 5.2 Layout

```
┌────┐
│ 🏠 │  Home
│    │
│ 👤 │  Contacts
│ 🏢 │  Companies
│ 💬 │  Conversations
│ ✉️  │  Communications
│ 📅 │  Events
│ 📝 │  Notes
│ ✅ │  Tasks
│ 📄 │  Documents
│ 📁 │  Projects
│────│  ← separator
│ 🔧 │  Jobs (custom)
│ 🏠 │  Properties (custom)
│    │
│    │  (spacer)
│    │
│ ❓ │  Help
│ ⚙️  │  Settings
│ 🧑 │  Account
└────┘
```

### 5.3 Icon Specifications

| Attribute | Value |
|---|---|
| Icon size | 24×24px |
| Label | Small text below icon (10-11px) |
| Item height | ~56px (icon + label + padding) |
| Active indicator | Highlighted background + left accent bar |
| Hover state | Subtle background highlight |
| Selected state | Filled background, accent bar on left edge |

### 5.4 Content Hierarchy

**Top section (fixed):**
- Home — always first, the operational hub for cross-cutting features

**Middle section (entity types):**
- System entities in default order: Contacts, Companies, Conversations, Communications, Events, Notes, Tasks, Documents, Projects
- Separator line
- Custom object types in user-defined order

**Bottom section (pinned to bottom):**
- Help icon
- Settings icon
- Account avatar (user profile, logout, workspace switcher)

### 5.5 Customization

- **Reorder:** Users can drag icons to reorder within the system and custom sections
- **Hide:** Users can hide entity types they don't use (right-click → "Hide from rail"). Hidden items are accessible via Settings → Rail Customization
- **Custom object icons:** When creating a custom object type, the user must provide a name and select an icon from a built-in library or upload a custom icon image

### 5.6 Overflow Behavior

When the entity list exceeds the viewport height (accounting for top and bottom pinned sections), the middle section becomes scrollable with a subtle scroll indicator. The top (Home) and bottom (Help, Settings, Account) sections remain pinned and always visible.

---

## 6. Zone 2: Action Panel

### 6.1 Purpose

The action panel is the **view control center** — it shows the user what they're looking at and provides inline controls to change it. It combines view navigation (switching between saved views), view configuration (current filters, sort, grouping), and entity-specific navigation (folder trees where applicable).

### 6.2 Opening & Closing

- **Open:** Clicking an entity icon on the rail opens the action panel for that entity type. If the action panel is already open for a different entity, it switches context.
- **Close:** Clicking the active rail icon (already selected) toggles the action panel closed. A collapse button at the top of the action panel also closes it.
- **State persistence:** The open/closed state is remembered per session. On app restart, the action panel opens in its last state.

### 6.3 Content Structure

When the action panel opens for an entity type, it displays the following sections top to bottom:

**View Switcher (top):**
- Dropdown or searchable list showing all available views for this entity type
- Grouped: "Personal Views", "Shared Views", "System Defaults"
- The currently active view is highlighted
- Clicking a different view loads it into the grid and updates the configuration section below

**Folder Navigation (conditional):**
- Displayed only for entity types that have folder hierarchies (e.g., Documents)
- Tree view of folders; clicking a folder scopes the grid to that folder's contents
- The view configuration below applies within the selected folder

**View Configuration (main body):**
- Full display of the active view's current settings:
  - **Active filters:** Each filter condition displayed as a readable chip or row (e.g., "Status = Active", "Region = Midwest"). Filters from the saved view definition shown as locked/base; temporary overlay filters shown as removable.
  - **Sort order:** Current sort field(s) and direction(s)
  - **Grouping:** Current group-by field, collapse state
  - **Columns:** List of visible columns (optional — may be deferred to a column picker on the grid itself)
- Each configuration element is interactive — clicking a filter opens an inline editor to modify it (as a temporary overlay), clicking the sort opens a sort picker, etc.

**View Actions (bottom):**
- "Reset" — discard all temporary modifications, return to the saved view state
- "Save View" — save the current state (base + temporary overlay) as a new personal view
- "Edit View" — enter edit mode to modify the existing view definition

### 6.4 Folder Navigation Detail

For entity types with folder hierarchies (e.g., Documents), the action panel displays a folder tree between the view switcher and the view configuration:

- Standard tree with expand/collapse nodes
- Clicking a folder scopes the grid to that folder's contents
- The view's filter/sort/group configuration applies within the folder scope
- A "root" or "All [Entity]" item at the top navigates out of any folder scope
- Folder CRUD (create, rename, move, delete) available via right-click context menu on folder nodes

---

## 7. Zone 3: Content Area — Grid

### 7.1 Purpose

The content area is the primary data display zone. In the standard entity workspace, it renders the active view as a data grid (List/Grid view), Board/Kanban, Calendar, or Timeline — as defined by the [Views & Grid PRD](views-grid-prd_V3.md).

### 7.2 Layout

The content area consists of:

1. **Grid Toolbar** (fixed at top of content area) — see Section 10
2. **View Search Bar** (integrated into the grid toolbar) — see Section 12
3. **Data Grid / View Rendering** (fills remaining space) — governed by the Views & Grid PRD

### 7.3 Row Selection & Detail Panel Sync

When the detail panel is open, clicking a row in the grid or using arrow-key navigation selects that row and instantly updates the detail panel with the selected record's data.

| Interaction | Behavior |
|---|---|
| **Click a row** | Row is selected (highlighted), detail panel updates to show that record |
| **Arrow Up / Arrow Down** | Selection moves to the previous/next row, detail panel updates instantly |
| **No selection** | Detail panel shows an empty state prompt ("Select a record to preview") or closes |
| **Prefetching** | The system prefetches the 2-3 records above and below the current selection so that arrow-key navigation triggers instant detail panel rendering with no loading delay |

### 7.4 View Type Rendering

The content area renders the active view type as defined by the Views & Grid PRD:

- **List/Grid** — tabular rows and columns, the default and most common view type
- **Board/Kanban** — cards in status columns, for pipeline visualization
- **Calendar** — records plotted on a date grid
- **Timeline** — records as horizontal bars across a time axis

All view types support row/card selection that syncs with the detail panel.

---

## 8. Zone 4: Detail Panel

### 8.1 Purpose

The detail panel provides a comprehensive, view-optimized display of the currently selected record. It is the primary way users read and review record data. The panel is designed for rapid browsing — arrow through records in the grid and the detail panel updates instantly with each record's complete information.

### 8.2 Rendering Principles

The detail panel follows all five core design principles (Section 2):

- **No empty fields:** If a field has no value, it does not render. No "Set Name..." placeholders, no "No phone numbers" labels, no empty field rows.
- **No data duplication:** Each value appears exactly once. If the contact's email is in the Identity zone, it does not repeat in a sidebar or summary.
- **Content-proportional space:** Sections are sized to their content. A section with 50 conversations gets significantly more vertical space than a section with 1 company link. Sections with 0 items are fully suppressed.
- **View-optimized display:** Field values render as formatted text, not as input controls. Addresses render as compact multi-line text. Dates render as human-readable strings. Relations render as clickable entity names.
- **Density by default:** Minimal padding, compact typography, no decorative whitespace. Every pixel is used for data.

### 8.3 Panel States

| State | Description |
|---|---|
| **Empty** | No row selected. The panel shows a minimal prompt: "Select a record to preview" or an entity-relevant tip. |
| **Loaded** | A row is selected. The panel displays the three-zone record layout (Section 14). |
| **Loading** | A new row was selected but data is still loading (should be rare due to prefetching). A lightweight skeleton screen preserves the layout. |

---

## 9. Top Header Bar

### 9.1 Purpose

The top header bar is a fixed, full-width bar at the top of the application. It provides location context, global search, and access to application-level functions.

### 9.2 Layout

```
┌─────────────────────────────────────────────────────────────────────────┐
│  Contacts › All Contacts          [     Global Search      ]   ? ⚙ 👤  │
└─────────────────────────────────────────────────────────────────────────┘
 ← Left                              ← Center →                  Right →
```

### 9.3 Content

**Left — Location Breadcrumb:**
- Displays the current entity type name and active view name as a breadcrumb: `Contacts › All Contacts`
- Updates automatically when the user switches entity types or views
- The entity name portion is clickable (returns to the grid if in full detail takeover mode)

**Center — Global Search:**
- A persistent search input field for cross-entity record search and navigation
- See Section 11 for full specification

**Right — Application Controls:**
- **Help icon** — Opens help documentation, contextual to the current screen
- **Settings icon** — Navigates to Settings & Administration (Section 18)
- **Account avatar** — Opens a dropdown menu: user profile, workspace switcher (for multi-tenant users), logout

### 9.4 Dimensions

| Attribute | Value |
|---|---|
| Height | 48px |
| Background | Solid, contrasting with content area |
| Position | Fixed — does not scroll |
| Z-index | Above all content zones |

---

## 10. Grid Toolbar

### 10.1 Purpose

The grid toolbar is a fixed bar at the top of the content area (below the top header bar) that provides multi-select management, view-scoped search, and entity-specific actions. It is the primary action bar for the current grid context.

### 10.2 Layout

```
┌─────────────────────────────────────────────────────────────────┐
│  ☐ ▾  │        [  View search / quick filter  ]    │ [Action 1] [Action 2] [Other ▾] │
└─────────────────────────────────────────────────────────────────┘
 ← Left            ← Center →                            Right →
```

### 10.3 Content — Default State (No Selection)

**Left — Multi-Select Management:**
- Checkbox (master select/deselect toggle)
- Dropdown arrow that opens a menu: Select All, Deselect All, Select All on Page, Invert Selection

**Center — View-Scoped Quick Filter:**
- Text input field for the view-scoped quick filter (Section 12)
- Placeholder text: "Search this view..." or "Filter by field:value..."

**Right — Entity Action Buttons:**
- **Two primary action buttons** — the most common actions for this entity type, displayed as prominent buttons
- **"Other" overflow button** — dropdown menu containing all remaining actions applicable to the entity grid

The two primary action buttons are **entity-specific**. Each entity type defines which two actions are promoted to primary position:

| Entity Type | Action 1 | Action 2 | Other (examples) |
|---|---|---|---|
| Contacts | New Contact | Import | Export, Merge Duplicates, Bulk Edit |
| Companies | New Company | Import | Export, Enrich All, Bulk Edit |
| Communications | New Communication | Sync Now | Export, Bulk Assign |
| Conversations | New Conversation | — | Export, Bulk Merge |
| Events | New Event | Sync Calendars | Export, Bulk Edit |
| Notes | New Note | — | Export, Bulk Tag |
| Tasks | New Task | My Tasks | Export, Bulk Complete, Bulk Assign |
| Documents | Upload | New Folder | Export, Bulk Move |
| Projects | New Project | — | Export, Archive |
| Custom Objects | New [Entity] | Export | Import, Bulk Edit |

### 10.4 Content — Active Selection State

When one or more rows are selected via checkboxes, the toolbar transitions to the **selection context**:

**Left — Selection Info:**
- Selection count with dropdown: "15 selected ▾" — dropdown offers Select All, Deselect All, Select All Matching Records (across all pages), Invert Selection

**Center — View-Scoped Quick Filter:**
- Unchanged — the search remains available during selection

**Right — Bulk Action Buttons:**
- **Two primary bulk action buttons** — the most common bulk operations, displayed with record count: `[Bulk Edit (15)]` `[Bulk Delete (15)]`
- **"Other" overflow button** — dropdown menu containing all remaining bulk actions: Bulk Assign, Bulk Export, Bulk Tag, Bulk Archive, etc.

The transition between default and selection states should be smooth — buttons crossfade or transition without jarring layout shifts. The change in button labels and styling (e.g., different color treatment for destructive actions like Bulk Delete) clearly communicates that the toolbar is now operating on the selection.

**Exiting selection state:** Deselecting all records (via "Deselect All" or unchecking all boxes) returns the toolbar to its default state.

---

## 11. Global Search

### 11.1 Purpose

The global search is a cross-entity record finder that searches across all entity types in the system. It operates as a self-contained modal overlay that does not disturb the user's current working state.

### 11.2 Interaction Model

The global search follows the ClickUp-style self-contained modal pattern:

1. **Activate:** User clicks the search box in the top header bar (or presses a keyboard shortcut — see Section 22)
2. **Search:** A modal overlay opens, centered on screen, with a search input at the top. As the user types, results appear below, grouped by entity type (Contacts, Companies, Conversations, etc.)
3. **Browse results:** User scrolls through results. Each result shows the entity type icon, the record's display name, and 1-2 secondary fields for disambiguation (e.g., email for contacts, industry for companies)
4. **View detail:** Clicking a result replaces the result list with a full detail view of that record inside the modal, following the same three-zone layout (Identity, Context, Timeline) as the docked detail panel
5. **Navigate within modal:** A back button returns from the detail view to the result list. The user can click another result to view a different record.
6. **Close:** Closing the modal (Escape key, click outside, or close button) returns the user to exactly where they were — grid position, selected row, detail panel content, temporary filters — all preserved.

### 11.3 Search Behavior

| Attribute | Behavior |
|---|---|
| **Scope** | All entity types the user has access to |
| **Matching** | Searches across display name fields and secondary identification fields (email, phone, etc.) |
| **Ranking** | Results ranked by relevance; recently accessed records boosted |
| **Grouping** | Results grouped by entity type, with a count per group |
| **Result limit** | Top 5 results per entity type initially; "Show all N results" expander per group |
| **Empty state** | "No matching records found" with suggestion to refine the query |

### 11.4 Modal Dimensions

| Attribute | Value |
|---|---|
| Width | 700-800px (centered) |
| Height | Up to 80% of viewport height |
| Background overlay | Semi-transparent dark scrim |
| Close | Escape key, click outside modal, or X button |

---

## 12. View-Scoped Quick Filter

### 12.1 Purpose

The view-scoped quick filter is a text input embedded in the grid toolbar that narrows the current view's result set in real time. It is the "find within what I'm looking at" tool, as opposed to the global search which is the "find anything anywhere" tool.

### 12.2 Behavior

- The quick filter operates on the **full server-side result set** defined by the current view and its filters — not just the rows currently loaded in the viewport
- Filter results update in real time as the user types (with a reasonable debounce of ~200ms)
- The quick filter acts as an additional AND constraint on top of the view's existing filters — it does not replace them
- Clearing the search box (Backspace to empty, or clicking the clear icon) restores the full view result set
- The quick filter text is **not** persisted as part of the view configuration — it resets when the user switches views or entity types

### 12.3 Query Syntax

**Plain text search:**
- Type any text → matches records where any visible field contains the text
- Example: `Acme` → returns all rows where any field contains "Acme"

**Field-scoped search:**
- Syntax: `field_name:value`
- Example: `city:Cleveland` → matches only the City field
- Example: `status:active` → matches only the Status field
- Field names are case-insensitive and match on the field's display name or slug

**Relative date syntax:**
- Syntax: `date_field:relative_expression`
- Example: `due:tomorrow` → records where the Due Date field is tomorrow
- Example: `created:this week` → records created within the current week
- Example: `created:last month` → records created within the previous calendar month
- Example: `due:next 7 days` → records where Due Date is within the next 7 days
- Example: `modified:yesterday` → records modified yesterday

**Supported relative date expressions:**

| Expression | Resolves To |
|---|---|
| `today` | Current date |
| `tomorrow` | Current date + 1 |
| `yesterday` | Current date − 1 |
| `this week` | Monday through Sunday of current week |
| `last week` | Previous Monday through Sunday |
| `next week` | Following Monday through Sunday |
| `this month` | First through last day of current month |
| `last month` | Previous calendar month |
| `next month` | Following calendar month |
| `last N days` | Today minus N days through today |
| `next N days` | Today through today plus N days |

**Numeric comparison syntax:**
- Syntax: `numeric_field:operator value`
- Example: `revenue:>500000` → records where Revenue exceeds 500,000
- Example: `age:<30` → records where Age is less than 30
- Supported operators: `>`, `<`, `>=`, `<=`, `=`

### 12.4 Autocomplete

As the user types a field name followed by `:`, the system offers autocomplete suggestions:

- After typing `due:` → dropdown suggests relative date options: today, tomorrow, this week, next 7 days, etc.
- After typing `status:` → dropdown suggests the available status values for the current entity type
- After typing `city:` → dropdown suggests city values that exist in the current view's result set
- Field name autocomplete: after typing a few characters before `:`, suggest matching field names

Autocomplete is advisory — the user can accept a suggestion or type freely.

---

## 13. Detail View Modes

### 13.1 Overview

The system supports three distinct detail view modes, allowing users to choose the level of detail and screen allocation that fits their current task:

| Mode | Description | Grid Visible | Use Case |
|---|---|---|---|
| **Docked Panel** | Detail panel shares the content area with the grid, separated by a splitter | Yes | Default — rapid browsing, arrow-key navigation |
| **Full Takeover** | Detail panel expands to fill the entire content area | No | Deep work on a single record, reviewing full history |
| **Undocked Window** | Detail panel pops out into a separate window/panel | Yes (full width) | Multi-monitor setups, maximum width for both grid and detail |

### 13.2 Mode 1: Docked Panel (Default)

- The detail panel occupies the right portion of the content area, separated from the grid by a draggable splitter bar
- Arrow-key navigation in the grid instantly updates the detail panel
- The splitter position is persisted per user per entity type
- The user can drag the splitter to any position between the grid's minimum width (~300px) and the detail panel's minimum width (~320px)
- Double-clicking the splitter resets to the default position

### 13.3 Mode 2: Full Takeover

- Activated by a "Maximize" button/icon on the detail panel header, or by a keyboard shortcut (see Section 22)
- The grid is hidden; the detail panel expands to fill the entire content area (between the icon rail/action panel on the left and the window edge on the right)
- The icon rail and action panel remain visible — the user can still switch entity types or views
- Navigation: a back button or keyboard shortcut returns to the previous grid + panel layout with the same row selected
- The full takeover layout may use additional width for a richer layout — for example, field sections on the left half and activity timeline on the right half, in a two-column arrangement

### 13.4 Mode 3: Undocked Window

The undocked mode separates the detail view into an independent, resizable panel:

**Web/PWA implementation:**
- The detail panel becomes a freely draggable, resizable floating panel within the application viewport
- The grid expands to fill the content area at full width
- The floating panel can be positioned anywhere within the browser window, overlapping the grid as needed
- Arrow-key navigation in the grid still updates the floating detail panel in real time
- A "Re-dock" button or keyboard shortcut snaps the panel back to the docked position

**Native desktop implementation (macOS, Windows, Linux):**
- The detail panel opens as a true OS-level window, managed by the operating system
- The window can be moved to a second monitor
- Arrow-key navigation in the main window's grid updates the detail window in real time
- Window management (minimize, maximize, close) follows OS conventions
- Closing the undocked window returns to the docked panel mode

### 13.5 Mode Switching

| From | To | Trigger |
|---|---|---|
| Docked | Full Takeover | Maximize button on detail panel header, or keyboard shortcut |
| Docked | Undocked | Undock button on detail panel header, or keyboard shortcut |
| Full Takeover | Docked | Back button, Escape key, or keyboard shortcut |
| Full Takeover | Undocked | Undock button |
| Undocked | Docked | Re-dock button, or close the undocked window |
| Undocked | Full Takeover | Maximize button within the undocked window |

---

## 14. Record Detail Layout — Universal Template

### 14.1 Three-Zone Vertical Structure

Every record detail display (in all three modes — docked, full takeover, undocked) follows a universal three-zone vertical structure:

```
┌─────────────────────────────────┐
│  Detail Panel Header            │
│  (entity type icon, display     │
│   name, mode controls)          │
├─────────────────────────────────┤
│                                 │
│  Zone 1: Identity               │
│  Essential identifying fields   │
│  rendered compactly             │
│                                 │
├─────────────────────────────────┤
│                                 │
│  Zone 2: Context                │
│  Description, notes, custom     │
│  field groups                   │
│  (suppressed if empty)          │
│                                 │
├─────────────────────────────────┤
│                                 │
│  Zone 3: Activity Timeline      │
│  Unified chronological stream   │
│  of all interactions            │
│  (fills remaining space)        │
│                                 │
│                                 │
│                                 │
└─────────────────────────────────┘
```

### 14.2 Detail Panel Header

The header bar at the top of the detail panel provides:

- **Entity type icon** — small icon identifying the record type (Contact, Company, Task, etc.)
- **Display name** — the record's primary display name field (e.g., contact name, company name, task title)
- **Mode controls** — buttons for Maximize (full takeover), Undock, and Close
- **Section edit indicator** — if any section is currently in edit mode, a subtle indicator is shown

### 14.3 Zone 1: Identity

The Identity zone displays the essential identifying information for the record. It renders compactly at the top of the panel and is always visible without scrolling.

**Rendering rules:**

- Fields are rendered as formatted values, not as labeled input controls
- Compound fields (address, name components) render as a single formatted block
- Empty fields are omitted entirely — no placeholders, no labels without values
- Related entity fields (e.g., Company on a Contact) render as clickable links
- The specific fields shown depend on the entity type (defined by each entity PRD)

**Example — Contact identity zone:**

```
┌─────────────────────────────────┐
│  Jane Smith                     │
│  VP of Engineering              │
│  Acme Corporation  →            │
│                                 │
│  jane.smith@acme.com            │
│  (216) 555-0142                 │
│  1234 Oak Street, Suite 200     │
│  Cleveland, OH 44139            │
│                                 │
│  Birthday: March 15             │
└─────────────────────────────────┘
```

Note: No "Email:" label before the email (the format is self-evident). No "Phone:" label. The address is 2 lines, not 6 separate fields. "Acme Corporation →" is a clickable link to the Company record. If there were no phone number, that line would simply not appear.

**Example — Task identity zone:**

```
┌─────────────────────────────────┐
│  Follow up on Q1 proposal       │
│  ● High Priority  ◉ Active     │
│  Due: Feb 25, 2026 (6 days)    │
│  Assigned: Jane Smith, Tom Lee  │
│  → Acme Corporation             │
│  → Q1 Renewal (Conversation)    │
└─────────────────────────────────┘
```

### 14.4 Zone 2: Context

The Context zone displays supplementary, descriptive information: the record's description or notes field, and any custom field groups that don't belong in the Identity zone.

**Rendering rules:**

- If the entity has no description and no custom field groups with data, Zone 2 is suppressed entirely — Zone 3 moves up to claim the space
- Rich text descriptions render as formatted HTML (not as editor controls)
- Custom field groups render as collapsible sections, each with a section header and a pencil edit icon
- Field groups follow the Custom Objects PRD Section 11 definitions
- Field groups with no populated fields are suppressed

### 14.5 Zone 3: Activity Timeline

The Activity zone displays a unified, chronological stream of all interactions and transactions related to the record, sorted most recent first.

**Content sources:**

The timeline aggregates items from multiple entity types into a single interleaved stream:

| Item Type | Source | Display |
|---|---|---|
| Emails | Communications (channel = email) | Subject line, sender, date, brief content preview |
| Calls | Communications (channel = phone) | Duration, direction (inbound/outbound), date, participant |
| Meetings | Events linked to this record | Title, date/time, participant count |
| Notes | Notes linked to this record | Title or content preview, author, date |
| Tasks | Tasks linked to this record | Title, status, assignee, due date |
| Conversations | Conversations involving this record | Title, status, last activity date |

**Rendering rules:**

- Each timeline item has a type icon (email, phone, calendar, note, task, chat) for quick visual scanning
- Items are sorted by date, most recent first
- Each item renders as 1-2 compact lines — enough to understand what it is without opening it
- Clicking a timeline item opens it (navigating to the full record or opening it in the global search modal)
- The timeline fills all remaining vertical space below Zones 1 and 2
- If the timeline exceeds the available space, it scrolls independently within its zone
- No filtering or type toggles in the docked panel — for filtered views of activity, use the full detail page (Mode 2)

### 14.6 Full Detail Page Layout (Mode 2: Full Takeover)

When the detail panel is expanded to full takeover mode, the additional width allows for a richer layout:

- **Two-column layout:** Field zones (Identity + Context) on the left half, Activity Timeline on the right half — both visible simultaneously without scrolling
- **Activity filtering:** The timeline in full takeover mode gains type toggle buttons at the top (Emails, Calls, Meetings, Notes, Tasks) allowing the user to filter the stream by activity type
- **Expanded timeline items:** Timeline items can show more content preview (3-4 lines instead of 1-2)
- **Inline activity viewing:** Clicking a timeline item expands it inline to show full content (e.g., full email body) rather than navigating away

---

## 15. Section-Based Editing

### 15.1 Overview

Record editing follows a **section-level granular model**. Each section (field group) in the detail panel has its own edit affordance. Users edit one section at a time without entering a full-record edit mode.

### 15.2 Edit Trigger

Each section header displays a **pencil icon** (right-aligned) when the user has edit permission for that section's fields. Clicking the pencil icon transitions that section from view mode to edit mode.

### 15.3 Edit Mode Behavior

| Aspect | Behavior |
|---|---|
| **Transition** | The section's compact, view-optimized rendering is replaced by editable input fields |
| **Controls** | The pencil icon is replaced by Save (checkmark) and Cancel (X) buttons |
| **Scope** | Only the clicked section enters edit mode; all other sections remain in view mode |
| **Compound fields** | An address that renders as 2 lines in view mode expands to individual fields (Street, City, State, ZIP) in edit mode |
| **Validation** | Field validation rules (from Custom Objects PRD Section 12) are enforced inline with error indicators |
| **Save** | Clicking Save (or pressing Enter on single-field sections) commits changes and transitions back to view mode |
| **Cancel** | Clicking Cancel (or pressing Escape) discards changes and transitions back to view mode |
| **Concurrent editing** | Only one section can be in edit mode at a time. Attempting to edit a second section prompts the user to save or cancel the first. |

### 15.4 Permission Integration

The pencil icon is only rendered for sections where the current user has edit permission (per the Permissions & Sharing PRD). Users with read-only access see the view-optimized rendering with no edit affordances — the UI doesn't tease them with controls they can't use.

### 15.5 Activity Timeline Editing

Zone 3 (Activity Timeline) does not have a section edit mode. Timeline items are read-only in the detail panel. To edit a specific communication, note, or task, the user clicks the timeline item to navigate to that record's own detail view.

---

## 16. View Management — Temporary Overlays & Persistence

### 16.1 Core Model

Saved views are treated as **immutable definitions** during normal use. Users can layer temporary modifications on top of a saved view, but those modifications are session-only and do not persist unless explicitly saved.

### 16.2 Temporary Overlay Behavior

When a user modifies a view's filters, sort, or grouping through the action panel, the modification is applied as a **temporary overlay**:

- The underlying saved view definition is not changed
- The overlay is maintained for the duration of the session (while the user remains on this view)
- Switching to a different view discards the overlay — the original view resets to its saved state when the user returns
- Navigating to a different entity type and back also discards the overlay

### 16.3 Visual Indicators

| State | Visual Treatment |
|---|---|
| **Saved view, no modifications** | View name displayed normally in the action panel and header breadcrumb |
| **Saved view with temporary overlay** | View name shown with a "modified" indicator (e.g., `All Contacts (modified)` or a subtle dot/badge). Temporary filter chips shown in a distinct style (e.g., dashed border) to differentiate from the view's base filters |
| **Reset available** | A "Reset" action is visible in the action panel whenever temporary modifications exist |

### 16.4 Save Workflow

**Save as new view:**
1. User has a view with temporary modifications
2. User clicks "Save View" in the action panel
3. System prompts for a view name
4. A new personal view is created with the base view's configuration plus the overlay modifications baked in
5. The user is switched to the new view

**Edit existing view:**
1. User clicks "Edit View" in the action panel
2. The action panel enters edit mode — configuration fields become fully interactive, and a Save/Cancel toolbar appears
3. If temporary modifications are already active, the system prompts: "You have unsaved changes — save these as the new version of '[View Name]'?"
4. If the user confirms, the temporary modifications become the new saved state
5. If the user declines, they enter edit mode with the original saved state and can make different changes
6. Save commits the updated definition; Cancel discards and returns to browse mode

### 16.5 Shared View Protection

Shared views have additional safeguards:

- Temporary overlays work identically — any user can temporarily modify a shared view without affecting others
- "Edit View" is restricted to the view's owner and users with appropriate permissions
- "Save View" always creates a new personal view (never overwrites the shared definition) unless the user has edit permission on the shared view
- When a shared view is modified by its owner, other users see the updated version on their next load

---

## 17. Home Screen

### 17.1 Purpose

The Home screen is the operational hub for **cross-cutting concerns** — features that span multiple entity types and don't belong in any single entity workspace. It is the default landing screen when the application opens and is always accessible via the Home icon at the top of the rail.

### 17.2 Content (Initial Specification)

The Home screen content is defined at a high level here, with detailed specification deferred to a future Home Screen PRD:

**Notifications Panel:**
- Recent notifications: new communications received, task due dates approaching, @mentions in notes, shared view modifications, provider sync status/errors
- Grouped by time (Today, Yesterday, This Week, Older)
- Each notification links to the relevant record

**Activity Summary:**
- Recent activity across all entity types: records created, modified, communications received
- Filterable by entity type and time range

**Quick Access:**
- Pinned or frequently accessed views across all entity types
- Recent records the user interacted with

**Dashboard Widgets (future):**
- Configurable dashboard with summary metrics, charts, and KPIs
- Pipeline summaries, task completion rates, communication volume trends
- Detailed specification deferred to a Dashboards PRD

### 17.3 Design Principle

The Home screen follows the same information density principles as entity workspaces. Widgets and panels are content-proportional, data-dense, and do not waste space on decorative elements.

---

## 18. Settings & Administration

### 18.1 Access

Settings is accessible via the Settings icon in the top header bar (right side) and via the Settings icon on the icon rail (bottom section).

### 18.2 Settings Scope (High-Level)

| Category | Examples |
|---|---|
| **Profile** | Display name, email, avatar, timezone, date format preferences |
| **Workspace** | Workspace name, branding, member management, billing |
| **Entity Types** | Custom object management (create, edit field groups, manage fields, set icons) |
| **Rail Customization** | Reorder rail items, show/hide entity types, manage custom object icons |
| **Integrations** | Provider account management (email, calendar, phone), API keys, webhook configuration |
| **Permissions** | Role definitions, permission assignments (per Permissions & Sharing PRD) |
| **Data Management** | Import/export, bulk operations, data cleanup tools |
| **Notifications** | Notification preferences (which events trigger notifications, delivery method) |

### 18.3 Layout

Settings uses a standard two-pane layout: navigation list on the left, settings content on the right. This layout replaces the entity workspace (grid + detail panel) but preserves the icon rail and top header bar for consistent navigation.

---

## 19. Empty States & Zero-Data Experience

### 19.1 Principle

Empty states should be helpful and action-oriented, not just decorative. When a section, panel, or view has no data, the empty state should tell the user **why** (is this a new entity with no records? a filter that matched nothing?) and **what to do** (create a record, import data, adjust filters).

### 19.2 Empty State Patterns

| Context | Empty State |
|---|---|
| **Grid with no records (new entity type)** | Centered message: "No [entity] records yet" with prominent Create and Import buttons |
| **Grid with no matching records (filter active)** | "No records match your current filters" with a "Reset Filters" button |
| **Grid with no matching records (quick filter active)** | "No records match '[search text]'" with a "Clear Search" link |
| **Detail panel with no selection** | "Select a record to preview" — minimal, unobtrusive |
| **Detail panel Zone 2 (no context data)** | Zone is suppressed entirely; Zone 3 expands upward |
| **Detail panel Zone 3 (no activity)** | Minimal message: "No activity yet" — no large illustrations or excessive text |
| **Action panel view list (no saved views)** | "No saved views" with a "Create View" action. The system default view is always available. |
| **Home screen notifications (none)** | "You're all caught up" — brief and positive |

### 19.3 Design Guidelines

- Empty states use concise text — one line if possible, two at most
- Action buttons are prominently styled so the user immediately sees what to do
- No large placeholder illustrations or mascot graphics — these waste space and conflict with the density-first philosophy
- Empty states in the detail panel are especially minimal, since the panel may briefly show empty state during rapid arrow-key navigation

---

## 20. Loading States, Skeleton Screens & Error Handling

### 20.1 Loading States

| Context | Loading Pattern |
|---|---|
| **Initial app load** | Full-screen loading indicator with app logo |
| **Entity switch (rail click)** | Grid displays skeleton screen (row outlines) while data loads. Action panel updates immediately (view list is cached). |
| **View switch** | Grid displays skeleton screen. Previous data is cleared immediately to prevent stale data confusion. |
| **Detail panel update (arrow key)** | Instant update if prefetched (target: >95% of cases). Lightweight inline skeleton if not prefetched. Never a full panel reload. |
| **Search results** | Results stream in as available; skeleton rows show expected result count |
| **Section edit save** | Inline saving indicator (subtle spinner on the Save button). Section returns to view mode on completion. |

### 20.2 Skeleton Screens

Skeleton screens (grey placeholder blocks showing the expected layout) are used instead of spinners for content areas. They preserve layout stability and give the user a sense of structure before data arrives.

- Grid skeleton: column headers render immediately (from cached view config), row placeholders appear at the expected row height
- Detail panel skeleton: zone structure (header, identity, context, timeline) renders as placeholders matching the expected layout

### 20.3 Error Handling

| Error Type | Handling |
|---|---|
| **Network error (data load)** | Inline error banner at the top of the affected zone: "Unable to load data. [Retry]" — other zones remain functional |
| **Network error (save)** | Inline error on the section being edited: "Save failed. [Retry]" — data remains in edit mode so the user doesn't lose changes |
| **Permission error** | Inline message: "You don't have permission to [action]" — displayed where the action was attempted |
| **Validation error (edit)** | Inline field-level error indicators (red border + tooltip) per the Views & Grid PRD |
| **Server error (500)** | Inline error banner with retry. Never a full-page error screen unless the entire application is unreachable. |
| **Stale data conflict** | If a save fails because the record was modified by another user, show: "This record was modified by [user] at [time]. [Reload] [Force Save]" |

### 20.4 Error Isolation

Errors in one zone should not affect other zones. If the detail panel fails to load a record, the grid remains fully functional. If a provider sync fails, the notification appears on the Home screen, not as a blocking modal in the entity workspace.

---

## 21. Responsive Breakpoints & Progressive Collapse

### 21.1 Design Approach

CRMExtender is designed large-screen-first and uses **progressive collapse** to adapt to smaller viewports. As the viewport shrinks, zones are hidden or overlaid in a defined sequence.

### 21.2 Breakpoint Definitions

| Breakpoint | Effective Width | Description |
|---|---|---|
| **XL (primary target)** | ≥1920px | Full four-zone layout. All zones visible simultaneously. |
| **L** | 1440–1919px | Four zones visible but tighter. Action panel may default to collapsed. |
| **M** | 1024–1439px | Grid + Detail Panel only. Action panel is an overlay. Rail collapses to icon-only (no labels). |
| **S** | 768–1023px | Single-zone focus. Grid or detail panel, not both. Detail panel is a full takeover or slide-over. |
| **XS** | <768px | Mobile layout. Bottom tab bar replaces rail. Full-screen views. This is a minimal-support tier. |

### 21.3 Progressive Collapse Sequence

As viewport width decreases, zones collapse in this order:

1. **Action panel collapses first** — becomes an overlay drawer (triggered by rail icon click) instead of a persistent panel. Grid gains the freed width.
2. **Detail panel becomes overlay** — instead of sharing content width with the grid, it becomes a slide-over panel or full takeover. Grid takes full content width.
3. **Rail collapses to icon-only** — labels are removed, rail narrows to ~48px. Tooltips appear on hover.
4. **Rail moves to bottom** — at mobile widths, the rail becomes a bottom tab bar with the most-used entity types and a "More" overflow.

### 21.4 Small Screen Accommodations

While the primary design target is large screens, the application remains fully functional at smaller sizes:

- All features are accessible — nothing is removed, only reorganized
- Touch targets are enlarged at smaller breakpoints (minimum 44px)
- The docked detail panel is replaced by a full-screen detail view with a back navigation
- The action panel becomes a modal drawer
- The global search modal scales to full-screen at mobile widths

---

## 22. Global Keyboard Shortcuts

### 22.1 Principle

Keyboard shortcuts are available for the most frequent navigation and action tasks. They complement mouse interaction but are never required — every action is also accessible via click/tap.

### 22.2 Shortcut Definitions

| Shortcut | Action | Context |
|---|---|---|
| **Cmd/Ctrl + K** | Open global search modal | Global — works from any screen |
| **/** | Focus the view-scoped quick filter | When grid is focused |
| **Escape** | Close modal / cancel edit / deselect / close detail panel | Context-dependent cascade |
| **↑ / ↓** | Navigate between grid rows (syncs detail panel) | When grid is focused |
| **Enter** | Open selected record in full detail (takeover mode) | When grid row is focused |
| **Space** | Toggle row expansion / detail panel | When grid row is focused |
| **Cmd/Ctrl + N** | Create new record (current entity type) | Within entity workspace |
| **Cmd/Ctrl + \\** | Toggle action panel open/closed | Global — works from any screen |
| **Cmd/Ctrl + Shift + D** | Toggle detail panel docked/undocked | When detail panel is visible |
| **Cmd/Ctrl + Shift + F** | Toggle detail panel full takeover | When detail panel is visible |
| **Cmd/Ctrl + Shift + \\** | Toggle detail panel open/closed | Within entity workspace |
| **Tab** | Move focus between zones (rail → action panel → grid → detail panel) | Global focus management |

### 22.3 Escape Key Cascade

The Escape key has a context-dependent cascade:

1. If a section is in edit mode → cancel the edit
2. If a modal is open (global search, dialog) → close the modal
3. If the detail panel is in full takeover mode → return to docked panel + grid
4. If text is in the quick filter → clear the quick filter
5. If rows are selected → deselect all
6. If the detail panel is open → close the detail panel

The cascade resolves to the **first matching condition** — pressing Escape once handles one level.

---

## 23. Theming & Visual Design Tokens

### 23.1 Design Token Categories

The visual design system is built on design tokens that ensure consistency across all components. Detailed values are deferred to the implementation phase; this section establishes the categories.

| Category | Examples |
|---|---|
| **Colors** | Primary, secondary, accent, background, surface, text, border, error, warning, success, info |
| **Typography** | Font family (system font stack for performance), heading sizes (H1-H4), body text, caption, monospace |
| **Spacing** | Base unit (4px), consistent padding/margin scale (4, 8, 12, 16, 24, 32, 48) |
| **Border radius** | Small (4px), medium (8px), large (12px) |
| **Elevation** | Flat (grid), raised (action panel, modals), overlay (global search modal) |
| **Iconography** | Monochrome icon set, 24×24 standard size, 16×16 compact size |
| **Density** | Compact row height (32-36px), standard row height (40-44px), comfortable row height (48-52px). Default: compact. |

### 23.2 Dark Mode

Dark mode support is planned but deferred to a future phase. The design token architecture should support theme switching from the start.

### 23.3 Density Setting

Users can choose from three density levels that affect row heights, padding, and spacing:

| Density | Row Height | Padding Scale | Use Case |
|---|---|---|---|
| **Compact** | 32-36px | Tight (4-8px) | Power users with large screens (default) |
| **Standard** | 40-44px | Normal (8-12px) | General use |
| **Comfortable** | 48-52px | Generous (12-16px) | Touch devices, accessibility needs |

The default is Compact, consistent with the information-density design philosophy.

---

## 24. Design Decisions

### 24.1 Why Four-Zone Layout Instead of Traditional Sidebar + Content?

The traditional two-zone layout (sidebar navigation + content area) forces a trade-off: either the navigation is always visible (consuming width) or it's hidden (requiring extra clicks). The four-zone layout gives each concern its own dedicated space — entity switching (rail), view management (action panel), data display (grid), and record detail (detail panel). On a large screen, all four are visible simultaneously. On smaller screens, they progressively collapse without losing functionality.

### 24.2 Why Icon Rail + Action Panel Instead of Full Sidebar?

A full sidebar wide enough for navigation labels, view lists, and configuration would consume 280-350px permanently. The icon rail + action panel hybrid uses only 60px when the action panel is closed, giving the grid maximum width. When the user needs view management, the action panel opens with full configuration controls. This is more space-efficient than a permanent sidebar.

### 24.3 Why Temporary Overlay Instead of Auto-Save View Changes?

Auto-saving every filter/sort modification to the saved view would cause three problems: (1) accidental corruption of carefully configured views, (2) shared views being modified unintentionally by team members, and (3) no way to "try out" a filter adjustment without committing to it. The temporary overlay model lets users explore freely while keeping saved views stable.

### 24.4 Why Section-Based Editing Instead of Full-Record Edit Mode?

Full-record edit mode replaces the entire view-optimized display with input fields, destroying the reading experience and requiring a navigation transition. Section-based editing confines the disruption to one section — the rest of the record remains in its compact, readable state. This is especially important in the docked panel where space is constrained. Full-record edit mode would also conflict with the "one section at a time" simplicity that keeps the interaction predictable.

### 24.5 Why View-Optimized Rendering Instead of Edit-Ready Forms?

Most CRM interactions are reads, not writes. A user might browse 50 records in the detail panel but edit 2. Optimizing for the 96% read case (compact formatted display) and making the 4% write case slightly slower (click pencil, edit, save) is the correct trade-off for productivity. Edit-ready forms (labeled input boxes) waste space on the 96% of interactions that don't need them.

### 24.6 Why Separate Global Search and Quick Filter?

These serve different needs: global search finds any record from any entity type regardless of current context (looking up a Contact while viewing Companies). The quick filter narrows the current view's data set for exploration and analysis (finding all Cleveland companies in the "Active Customers" view). Combining them into a single search bar would create ambiguity about scope and make the common case (filtering the current view) slower.

### 24.7 Why Self-Contained Search Modal Instead of Navigation-Based Search?

Navigation-based search (searching redirects you to a search results page) destroys the user's current working context — grid position, selected row, temporary filters, scroll position. The self-contained modal preserves all of that. The user peeks at a search result, gets the information they need, closes the modal, and is exactly where they left off. This is critical for the "don't lose my place" productivity principle.

### 24.8 Why Contextual Purity — No Notifications in Entity Workspaces?

Notifications (badges, banners, toasts) in entity-specific interfaces create visual noise and attention fragmentation. When a user is triaging 50 emails, a notification about an upcoming meeting in 30 minutes is a distraction, not a feature. By confining notifications to the Home screen, entity workspaces remain focused on their primary task. Users who want to check notifications navigate to Home intentionally.

### 24.9 Why Context-Sensitive Grid Toolbar?

The grid toolbar's transition from entity actions (when no rows are selected) to bulk actions (when rows are selected) eliminates the need for a separate bulk action bar. This reduces visual complexity and ensures the toolbar always shows the most relevant actions for the user's current intent. The pattern is learnable because the position and structure of the buttons remains the same — only the labels and behavior change.

### 24.10 Why Large-Screen-First Instead of Mobile-First?

Mobile-first design produces UIs optimized for constrained viewports — large touch targets, generous whitespace, simplified navigation. These qualities are counterproductive on a 4K 27" display where the user wants to see as much data as possible. CRMExtender's target users are primarily desktop power users who spend hours per day in the application. Designing for their primary device and progressively degrading for smaller screens produces a better outcome for the core audience than designing for mobile and scaling up.

---

## 25. Phasing & Roadmap

### Phase 1: Core Shell & Grid

**Goal:** Deliver the four-zone layout with basic navigation, grid rendering, and docked detail panel.

- Icon rail with system entity navigation
- Action panel with view switcher (list of saved views)
- Content area with grid rendering (List/Grid view type per Views & Grid PRD Phase 1)
- Docked detail panel with three-zone layout (Identity, Context, Timeline)
- View-optimized rendering (no empty fields, content-proportional space)
- Top header bar with breadcrumb and placeholder for global search
- Grid toolbar with entity action buttons and quick filter (plain text search only)
- Row selection synced with detail panel
- Arrow-key navigation with detail panel instant update
- Splitter bar between grid and detail panel
- Basic responsive breakpoints (XL and L)

### Phase 2: View Management & Editing

**Goal:** Full action panel functionality, section-based editing, temporary overlay model.

- Action panel view configuration display (filters, sort, grouping)
- Temporary overlay model with visual indicators
- Save View and Edit View workflows
- Section-based editing with pencil icons
- View-scoped quick filter with field-name syntax and autocomplete
- Context-sensitive grid toolbar (bulk action transition)
- Multi-select management
- Full takeover detail mode
- Responsive breakpoints M and S

### Phase 3: Global Search & Undocked Mode

**Goal:** Cross-entity search, undocked detail windows, keyboard shortcut suite.

- Global search modal (ClickUp-style)
- Search results grouped by entity type
- In-modal detail viewing
- Undocked detail panel (floating window in web)
- Full keyboard shortcut suite
- Skeleton screens and loading state refinements
- Error handling patterns
- Action panel folder navigation (for Document entity type)
- Custom object rail icons (icon picker and upload)

### Phase 4: Native Desktop & Advanced Features

**Goal:** Native desktop enhancements, theming, home screen.

- True OS-level undocked windows (native desktop builds)
- Multi-monitor support with cross-window detail panel sync
- Home screen with notifications panel, activity summary, quick access
- Density settings (compact, standard, comfortable)
- Dark mode support
- Responsive breakpoint XS (mobile)
- Advanced action panel features (reports section, tags section)

---

## 26. Dependencies & Related PRDs

| PRD | Relationship |
|---|---|
| **[Custom Objects PRD](custom-objects-prd.md)** | Defines field groups (detail panel sections), field types (rendering behavior), relation types (clickable links), and entity type framework (rail items). The GUI PRD is the presentation layer for the Custom Objects data model. |
| **[Views & Grid PRD](views-grid-prd_V3.md)** | Defines all grid-level interactions: inline editing, row expansion, bulk actions, keyboard navigation, filter/sort/group mechanics, view persistence, and view sharing. The GUI PRD wraps the grid in the application shell. |
| **[Data Sources PRD](data-sources-prd.md)** | Defines the query abstraction that feeds views. The action panel surfaces data source configuration; the quick filter queries the data source result set. |
| **[Permissions & Sharing PRD](permissions-sharing-prd_V1.md)** | Determines which edit pencil icons appear, which action buttons are available, which views are accessible, and Edit View eligibility. |
| **[Contact Management PRD](contact-management-prd_V4.md)** | Defines Contact-specific identity zone fields, action buttons, and timeline content sources. |
| **[Company Management PRD](company-management-prd.md)** | Defines Company-specific identity zone fields, hierarchy display, and action buttons. |
| **[Communications PRD](communications-prd_V2.md)** | Defines Communication records that populate the activity timeline in detail panels. |
| **[Conversations PRD](conversations-prd_V3.md)** | Defines Conversation records that appear in the activity timeline. |
| **[Events PRD](events-prd_V2.md)** | Defines Event records for timeline display and calendar view integration. |
| **[Notes PRD](notes-prd_V2.md)** | Defines Note records for timeline display and the rich text editing model used in section editing. |
| **[Tasks PRD](tasks-prd_V1.md)** | Defines Task records for timeline display and task-specific grid toolbar actions. |
| **[Documents PRD](documents-prd_V1.md)** | Defines the folder navigation model that the action panel renders for Document entity workspaces. |
| **[Projects PRD](projects-prd_V2.md)** | Defines Project-specific layouts and action buttons. |

---

## 27. Open Questions

1. **Action panel width vs. content** — Should the action panel width be fixed or should it adapt to content? For example, folder trees with deep nesting may need more width than a flat view list. Should the action panel have its own resizable edge?

2. **Prefetch strategy** — The detail panel instant-update requires prefetching adjacent records. What is the optimal prefetch window (±2? ±5? ±10?) and how does this interact with server-side pagination? Should prefetching be adaptive based on navigation speed?

3. **Quick filter server-side vs. client-side** — For small result sets (<1000 records fully loaded), should the quick filter operate client-side for instant response? For larger result sets, server-side filtering with debounce is required. Where is the threshold?

4. **Undocked window communication** — In the web/PWA implementation, should the undocked floating panel communicate with the main grid via local state management (simple but confined to the browser window) or via BroadcastChannel API (enables future cross-tab communication)?

5. **Multiple entity type support in Home screen** — Should the Home screen support configurable dashboard layouts (drag-and-drop widget placement) or a fixed layout? Configurable dashboards are more flexible but significantly more complex.

6. **Detail panel prefetch and memory** — When arrowing quickly through records, how many detail panels should be cached in memory? Caching more means instant back-navigation but higher memory usage.

7. **Quick filter syntax discoverability** — How do users learn the `field:value` syntax? A help tooltip? An inline syntax guide that appears when the filter is focused? A dedicated documentation page?

8. **Splitter position defaults by view type** — Should the default splitter position differ by view type? For Board views, the detail panel might default to narrower since the board itself needs width. For a "Communications" entity, the detail panel might default to wider since email content is the primary focus.

9. **Full takeover mode two-column layout** — At what content width does the two-column layout (fields left, timeline right) activate? And should the user be able to choose between single-column scrollable and two-column side-by-side?

10. **Native desktop multi-window state persistence** — When the user has an undocked detail window on a second monitor and closes the app, should the window positions and sizes be restored on next launch?

---

## 28. Future Work

### 28.1 Dashboards & Analytics

A dedicated Dashboards PRD will define configurable dashboard widgets, chart types, KPIs, and layout management for the Home screen and potentially entity-specific dashboards.

### 28.2 Split Views

The ability to display two grids side by side (e.g., Contacts grid on the left, related Company grid on the right) for cross-entity comparison and drag-to-link operations.

### 28.3 Command Palette

Extending the global search to include executable commands (e.g., "Create Contact", "Open Settings", "Switch to Board View") for full keyboard-driven application control.

### 28.4 Workspace Layouts

Named, saveable workspace layouts that remember the full application state — which entity is active, which view is loaded, splitter positions, detail panel mode, action panel state — enabling instant switching between work contexts (e.g., "Email Triage" layout vs. "Pipeline Review" layout).

### 28.5 Drag-and-Drop Cross-Entity Linking

Dragging a record from one zone (e.g., a Contact from the grid) and dropping it onto a record in another zone (e.g., a Conversation in the detail panel timeline) to create a relation.

### 28.6 Contextual Quick-Create

Creating related records inline from the detail panel — e.g., a "+" button in the Tasks section of a Contact's detail panel that creates a new Task pre-linked to that Contact, without navigating away.

### 28.7 AI-Assisted Search

Natural language queries in the global search: "Show me all contacts I haven't talked to in 30 days" → translates to a filter and opens a view.

### 28.8 Customizable Grid Toolbar Actions

Allowing users to configure which two actions are promoted to the primary slots on the grid toolbar, rather than relying solely on the entity type defaults.

### 28.9 Activity Timeline Inline Expansion

In the docked detail panel, allowing timeline items to expand inline to show full content (email body, note text) without navigating away — bringing the full takeover mode's expanded timeline capability to the docked panel.

---

## 29. Glossary

| Term | Definition |
|---|---|
| **Application Shell** | The outermost UI framework: top header bar, icon rail, action panel, content area, and detail panel. All entity-specific interfaces render within this shell. |
| **Icon Rail** | The narrow vertical bar on the far left (~60px) containing entity type icons for primary navigation. |
| **Action Panel** | The collapsible panel between the icon rail and the content area (~280px) that provides view switching, view configuration, and folder navigation. Also called the "view control center." |
| **Content Area** | The main zone where data views render — grids, boards, calendars, timelines. |
| **Detail Panel** | The right-side panel that displays the selected record's full information in a three-zone layout. |
| **Splitter Bar** | A draggable divider between the content area and detail panel that allows the user to allocate width between them. |
| **Four-Zone Layout** | The application's primary layout pattern: icon rail + action panel + content area + detail panel displayed simultaneously. |
| **Docked Panel** | The default detail view mode where the panel shares the content area with the grid. |
| **Full Takeover** | A detail view mode where the panel expands to fill the entire content area, hiding the grid. |
| **Undocked Window** | A detail view mode where the panel becomes a separate floating panel (web) or OS-level window (native desktop). |
| **Temporary Overlay** | Session-only modifications to a view's filters, sort, or grouping that do not affect the saved view definition. |
| **View-Optimized Rendering** | The default display mode for record data: compact formatted text, no input controls, no empty field placeholders. Optimized for reading. |
| **Section-Based Editing** | The editing model where individual field group sections are toggled into edit mode via pencil icons, rather than entering a full-record edit mode. |
| **Content-Proportional Space** | The layout principle where sections are sized proportional to the data they contain, with empty sections suppressed entirely. |
| **Progressive Collapse** | The responsive design strategy where zones are hidden or overlaid as the viewport shrinks, in a defined sequence. |
| **Quick Filter** | The view-scoped text search in the grid toolbar that narrows the current view's result set in real time. Supports plain text, field-name syntax, relative dates, and numeric comparisons. |
| **Global Search** | The cross-entity search accessible from the top header bar that opens a self-contained modal overlay. |
| **Grid Toolbar** | The fixed bar at the top of the content area containing multi-select management, quick filter, and entity action buttons. |
| **Contextual Purity** | The design principle that each entity workspace is dedicated to that entity's workflow, with cross-cutting concerns confined to the Home screen. |
| **Density Setting** | User preference for row heights and spacing: compact (default), standard, or comfortable. |
| **Identity Zone** | The top section of the record detail layout showing essential identifying fields (name, email, phone, etc.) rendered compactly. |
| **Context Zone** | The middle section of the record detail layout showing descriptions, notes, and custom field groups. Suppressed if empty. |
| **Activity Timeline Zone** | The bottom section of the record detail layout showing a unified chronological stream of all interactions related to the record. |

---

*This document is a living specification. As the Home Screen PRD, Dashboards PRD, and implementation phases progress, sections will be updated to reflect design decisions, scope adjustments, and lessons learned from PoC validation.*
