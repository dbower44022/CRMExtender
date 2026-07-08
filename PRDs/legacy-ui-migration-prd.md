# Legacy UI Migration — Functional Area PRD

**Version:** 1.0
**Last Updated:** 2026-07-07
**Status:** COMPLETE — all six phases implemented (Phase 5 decommission 2026-07-08) (T01–T03, T05 UI verified by manual browser testing; T04 automation pending). Phase 2 deliberate improvements over legacy: ownership + parent-match checks on all sub-resource routes; exclusive set-primary for every type; hierarchy self-link/duplicate/cycle protection; contact email normalization; contact delete (new capability — legacy had none). Phase 3 fixes recorded here: attachment orphans adopted via attachment_ids (legacy never linked them, making its cleanup job unsafe); note deletion removes attachment files (legacy leaked them); mentions recorded server-side (legacy editor never set mentionType, so note_mentions was always empty); exact-segment attachment tenant check; FTS/entity-type errors return 400 not 500. The notes card renders with an empty state instead of suppress-when-empty, superseding the pre-creation-era rule. Phase 4 notes: contact import is vCard (path-based), not CSV — UIMIG-44 amended accordingly; manual conversation creation has no legacy equivalent and stays out of scope; per-contact email sync and company enrichment run synchronously (network-bound, UI warns); calendar sync uses the background single-slot pattern. Improvements over legacy recorded in the api_workflows.py docstring: tenant checks on all workflow mutations (legacy had none on assign/archive/delete/project/topic/event), surfaced errors instead of silent swallows, customer-scoped relationship types, impact counts returned, event CHECK pre-validation, hierarchy-free duplicates report retained. Deferred pieces of Phase 4 scope: companies duplicate-checked create flow in AddCompanyModal (check endpoint exists; modal wiring pending) and per-contact sync-email UI (endpoint exists).
**Parent Documents:** [product-tdd.md] §2.3 (Dual UI Architecture), [gui-functional-requirements-prd.md]
**Related:** [prd-index.md]

---

## 1. Scope & Boundaries

### 1.1 Purpose

Execute the deprecation decision recorded in Product TDD §2.3: bring the React SPA (`/app/`) to feature parity with the legacy HTMX/Jinja2 UI (`/` routes), then decommission the legacy UI. The end state is a single, coherent application experience with no accidental transitions between the two UIs.

### 1.2 Actors

- **All users** — every legacy page's capability must be reachable in the SPA (or consciously retired).
- **Admin** — settings/admin surfaces are already in the SPA; admin-only legacy workflows (relationship types, duplicates report) migrate here.

### 1.3 Boundaries

**In scope:** all ~157 legacy routes across 13 domains; URL routing/deep-linking in the SPA; the JSON API endpoints the SPA needs for parity; redirects and template/route deletion at decommission.

**Out of scope:**
- **Auth pages stay server-rendered** (`/login`, `/register`, `/logout`, `/auth/google*`). The SPA depends on them from outside; session/cookie auth is unchanged.
- The Google account-connect OAuth redirect flow (`/settings/accounts/connect`) — a server redirect flow by nature; the SPA links to it.
- Feature redesigns. Parity may simplify a legacy interaction, but new capabilities belong in their entity PRDs.

### 1.4 Related Documents

Inventory sources (2026-07-07 audit): legacy route inventory and React SPA coverage inventory summarized in Section 2 tables. Entity-specific UI behavior remains governed by the entity PRDs (e.g. [conversation-view-prd.md]).

---

## 2. Capabilities (Gap Summary)

State of the world at audit time (2026-07-07):

| Domain | Legacy routes | SPA/API state | Migration weight |
|---|---|---|---|
| Views/Grid | 10 | API ~1:1; SPA grid is richer | None (retire legacy) |
| Settings/Admin/Roles | 24 | API ~1:1; SPA has all 7 tabs | None (retire legacy) |
| Dashboard + Sync | 2 | Missing entirely | Phase 1 |
| Contacts | 30 | Detail/create/merge covered; ~24 sub-resource mutation routes missing | Phase 2 (+4 workflows) |
| Companies | 29 | Detail/create/merge/delete covered; ~20 missing (sub-resources, enrich, hierarchy, duplicates) | Phase 2 (+4 workflows) |
| Conversations | 6 | Rich SPA views; topic assign/unassign + addresses missing | Phase 4 |
| Communications | 7 | Rich SPA views; bulk archive/assign missing | Phase 4 |
| Events | 8 | Grid/detail only; create/delete/sync missing | Phase 4 |
| Projects | 9 | Grid/detail only; create/delete, topics, auto-assign missing | Phase 4 |
| Relationships | 8 | Grid/detail only; create/delete/infer/types missing | Phase 4 |
| Notes | 17 | API has single-note GET only; whole subsystem missing | Phase 3 |
| Auth | 7 | Stays server-rendered | Excluded |

SPA structural gaps (not tied to a domain): no URL routing (refresh/back/deep links inert); legacy escape-hatch links (`IdentityZone` "Open full detail", IconRail Dashboard, grid link templates); `comingSoon()` stubs for delete, bulk actions, import/export, and most "Add X" buttons.

---

## 3. Configuration

None. Migration introduces no new configuration; decommission removes none.

---

## 4. Key Processes

### KP-UIMIG-01: In-App Navigation Contract

Every reference to an entity inside the SPA navigates within the SPA: grid link cells, detail-zone links, full-view association links, global search results. The URL reflects `{entityType, selectedRecord}` as `/app/{entity-plural}[/{id}]`; the SPA parses the URL on boot and on back/forward, and updates it on navigation. Middle-click/new-tab on any entity link yields a working deep link.

### KP-UIMIG-02: Parity-Then-Redirect

A legacy route is retired only after its capability is verified in the SPA (task checked, test passing). At decommission each legacy page route becomes a 308 redirect to its SPA equivalent; legacy action (POST/fragment) routes are deleted with their templates.

---

## 5. Action Catalog

Phased implementation. Each phase is independently shippable.

### Phase 0 — Foundation (approved 2026-07-07)

URL routing + removal of legacy escape hatches. No backend changes.

### Phase 1 — Dashboard & Quick Wins

React dashboard (counts, recent activity, Sync Now) backed by new `GET /api/v1/dashboard` and `POST /api/v1/sync`; wire existing stubs where API exists; IconRail Home icon switches to the SPA dashboard.

### Phase 2 — Entity Editing Parity

Generic sub-resource API (identifiers, phones, emails, addresses, affiliations, hierarchy — uniform add/edit/delete/set-primary across contacts/companies/conversations/events/projects) + editing sections in SPA detail/full views. Score recompute actions.

### Phase 3 — Notes Subsystem

Full notes API (CRUD, pin, revisions, attachments upload/serve, @-mentions, cross-entity linking, search) + SPA notes UI reusing the existing TipTap editor.

### Phase 4 — Workflows

Create forms for events/projects/notes/conversations; topic & conversation assignment; communications bulk archive/assign; projects+topics auto-assign; relationships create/delete/infer + type admin; contacts CSV import and relate wizard; companies enrich/duplicates/resolve-domains/confirm.

### Phase 5 — Decommission

Redirect legacy page routes to SPA equivalents; delete legacy templates and route modules (keep auth + OAuth connect); update Product TDD §2.3 to record completion; final PRD index update.

---

## 6. Cross-Cutting Concerns

### 6.1 Audit & Logging

New API endpoints follow existing api.py logging conventions. No additional audit scope.

### 6.2 Permissions & Access Control

New API endpoints enforce the same customer scoping and role gates as the legacy routes they replace (admin-only: user admin, relationship types, system settings).

### 6.3 Error Handling

SPA mutations surface API errors via the existing toast pattern (sonner). Redirects at decommission preserve deep-linked URLs where a mapping exists; otherwise land on the SPA default view.

---

## 7. Task List

### Phase 0 — Foundation
- [x] UIMIG-01: URL sync — reflect `{entityType, selectedRowId}` as `/app/{plural}[/{id}]` via history API; parse on boot; handle popstate
- [x] UIMIG-02: Deep links — `/app/{plural}/{id}` opens the record (pendingNavigation) after grid load
- [x] UIMIG-03: Grid link cells navigate in-app (href rewritten to `/app/...` for new-tab; click intercepted)
- [x] UIMIG-04: `IdentityZone` "Open full detail" opens the SPA full view instead of the legacy page
- [x] UIMIG-05: Full-view association/children links carry correct URL state
- [x] UIMIG-06: Frontend dist rebuilt and committed in sync

### Phase 1 — Dashboard & Quick Wins
- [x] UIMIG-10: `GET /api/v1/dashboard` (counts, recent conversations, top companies/contacts)
- [x] UIMIG-11: `POST /api/v1/sync` (async trigger + status surface)
- [x] UIMIG-12: SPA Dashboard screen; IconRail Home switches to it
- [x] UIMIG-13: ~~Wire delete row-action where API exists~~ Re-scoped: audit found no entity DELETE endpoints in the JSON API (the inventory's "delete" was the legacy route). Entity deletes move to Phases 2/4 with their APIs.

### Phase 2 — Entity Editing Parity
- [x] UIMIG-20: Generic sub-resource API router (identifiers/phones/emails/addresses/affiliations/hierarchy)
- [x] UIMIG-21: SPA editing sections in RecordDetail zones (add/edit/delete/set-primary)
- [x] UIMIG-22: Score recompute endpoints + UI actions
- [x] UIMIG-23: API tests per sub-resource; parity checklist against legacy routes

### Phase 3 — Notes Subsystem
- [x] UIMIG-30: Notes API — CRUD, pin, revisions, attachments (upload/serve), mentions, entity links, search
- [x] UIMIG-31: SPA notes UI — editor (TipTap), revision history, attachments, mentions, linking
- [x] UIMIG-32: Notes cards in entity views gain create/edit/pin

### Phase 4 — Workflows
- [x] UIMIG-40: Create forms — events, projects, notes, conversations
- [x] UIMIG-41: Topic & conversation assignment (incl. communications bulk assign/archive)
- [x] UIMIG-42: Projects/topics management + auto-assign preview/apply
- [x] UIMIG-43: Relationships — create/delete/infer + relationship-type admin
- [x] UIMIG-44: Contacts CSV import + relate wizard
- [x] UIMIG-45: Companies enrich / duplicates report / resolve-domains / confirm flow

### Phase 5 — Decommission
- [x] UIMIG-50: 308 redirects for legacy page routes → SPA equivalents
- [x] UIMIG-51: Delete legacy templates + route modules (retain auth, OAuth connect)
- [x] UIMIG-52: Product TDD §2.3 updated; PRD index updated; deployment guide reviewed

## 8. Test Plan

- [x] UIMIG-T01: Boot at `/app/conversations/{id}` selects that conversation once rows load
- [x] UIMIG-T02: Back/forward walks navigation history without full reloads
- [x] UIMIG-T03: Grid subject link click stays in SPA; middle-click opens working deep link
- [ ] UIMIG-T04: No `<a>` in the SPA resolves to a legacy page route (automated link audit), excluding auth/OAuth
- [x] UIMIG-T05: Dashboard endpoint returns counts matching legacy dashboard queries
- [x] UIMIG-T06: Sub-resource API round-trip per type (add → edit → set-primary → delete)
- [x] UIMIG-T07: Notes round-trip incl. revision created on edit, attachment upload/download
- [x] UIMIG-T08: Decommission — legacy page URLs 308 to SPA equivalents; action routes return 404
