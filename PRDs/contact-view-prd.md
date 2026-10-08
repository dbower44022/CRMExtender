# Contact — View Contact Sub-PRD

**Version:** 1.0
**Last Updated:** 2026-07-10
**Status:** Draft — bespoke Contact Full View + separate Edit page; supersedes the generic RecordDetail for contacts
**Entity Base PRD:** [contact-entity-base-prd.md]
**Referenced Entity PRDs:** [contact-management-prd.md], [contact-identity-resolution-prd.md], [company-entity-base-prd.md], [communication-entity-base-prd.md], [conversation-entity-base-prd.md]
**GUI Documents:** [gui-functional-requirements-prd.md], [gui-preview-card-amendment.md]

> **V1.0 (2026-07-10): Initial draft.** Authored after the product owner rejected inline grid editing as the primary contact-edit surface ("not a key function") and directed a bespoke Contact Full View plus a separate Contact Edit page. Establishes the identifier-lifecycle rules (§3) that also govern the sub-resource API, and specifies which fields the Edit page may touch by quoting the Entity Base PRD's Editable column. Task/test checkboxes are all unchecked — nothing in §7–§8 is built yet, except the identifier-lifecycle enforcement tracked under CM-30…CM-31 in [contact-management-prd.md] (the security tightenings), which this PRD documents but does not own.

---

## 1. Overview

### 1.1 Purpose

Give the Contact — the central entity of the CRM — a first-class detail surface: a **bespoke read view** that assembles the whole person (identity, identifiers, employment, relationships, intelligence, activity, notes) and a **separate Edit page** on its own route for changing what may be changed.

Today a contact is rendered through the *generic* `RecordDetail` component shared with companies, events, and projects (three zones: Identity, Context, Timeline), and edited through the `ManageRecordModal`. Conversations and communications, by contrast, each have a purpose-built full view. This PRD closes that gap for contacts.

### 1.2 Preconditions

- The contact exists and belongs to the caller's customer.
- The Entity Base PRD's field-metadata (§1.4) is authoritative for which fields are editable; this PRD does not re-decide editability, it renders it.
- The identifier-lifecycle rules in §3 hold at the API layer before the Edit page relies on them.

### 1.3 Non-Goals

- Inline editing of contact fields in the data grid. The grid remains read-first; grid cell editing is explicitly **not** the contact-edit surface (product-owner direction, 2026-07-09).
- Bulk editing across many contacts.
- Merge/split (owned by [contact-merge-split-prd.md]) and duplicate review (owned by [contact-identity-resolution-prd.md]); the view *links to* these, it does not implement them.

---

## 2. Context

### 2.1 Relevant Fields

The Edit page (§7) is bound strictly by the Entity Base PRD §1.4 **Editable** column. Reproduced here as the contract for what the Edit page may render as an input:

| Field | Editable | Edit-page treatment |
|---|---|---|
| First Name | Direct | Text input |
| Last Name | Direct | Text input |
| Display Name | Override | Text input; show computed value with a "reset to computed" affordance when overridden |
| Avatar URL | Direct | Text/URL input |
| Lead Source | Direct | Select (fixed vocabulary) |
| Lead Status | Direct | Select (fixed vocabulary) |
| Primary Email | Via Identifiers | **Not an input.** Managed through the Identifiers editor (§7.2) |
| Primary Phone | Via Identifiers | **Not an input.** Managed through the Identifiers editor (§7.2) |
| Job Title | Via Employment | **Not an input.** Managed through the Employment editor (§7.3) |
| Current Company | Via Employment | **Not an input.** Managed through the Employment editor (§7.3) |
| Company Name | Computed | Read-only |
| Engagement Score | Computed | Read-only |
| Intelligence Score | Computed | Read-only |
| ID, Source, Status, Created By/At, Updated At | System | Read-only; never an input |

> **Design principle (methodology §3.2):** editability is explicit — the Edit page must not render an input for any field not marked `Direct` or `Override` above. `Source` and `Status` are `System`; they are read-only here, and the grid's current inline-edit of them is a defect tracked under CM-36 in [contact-management-prd.md].

### 2.2 Relevant Relationships

- **Contact Identifiers** (emails, phones, social handles) — 1-to-many, lifecycle-governed by §3.
- **Employment / Affiliations** (`contact_companies`) — 1-to-many; company link + title/department/role.
- **Addresses** — 1-to-many, lifecycle-governed by §3.
- **Relationships** (contact-to-contact) — from [contact-relationship-intelligence-prd.md].
- **Companies** — via employment.

### 2.3 Cross-Entity Context

The read view aggregates communications, conversations, events, and notes already returned in condensed form by `GET /contacts/{id}` (`identity`/`context`/`timeline`). The bespoke view will require the payload to be **extended** beyond that shape (full identifier list with labels/active-state, full employment history, scores, metadata) — the delta is specified per-card in §6 and captured for the Entity TDD.

---

## 3. Key Processes — Identifier Lifecycle

These rules are product-owner decisions (2026-07-09/10). They govern both the Edit page and the underlying sub-resource API. **CM-30 and CM-31 in [contact-management-prd.md] enforce the API side (the "security tightenings"); this section is the authoritative statement of intent.**

### KP-CONTACT-VIEW-01: An email is never edited

**Trigger:** User wants to correct an email address on a contact.

An email identifier's **value is immutable**. There is no in-place edit for anyone, admin or not — an email is the unique duplicate identifier for a contact (see [contact-identity-resolution-prd.md]). To replace a wrong email: add the correct one, mark the wrong one inactive; an administrator may delete it if genuinely erroneous. The `PUT …/identifiers/{id}` endpoint does not accept a `value` field, by design.

### KP-CONTACT-VIEW-02: Nothing is user-deletable

**Trigger:** User wants to remove an email, phone, address, or employer from a contact.

**Step 1 — Users may not delete** any sub-resource (identifier, phone, address, affiliation). The only user actions are **add** and **mark inactive**.

**Step 2 — Deletion is administrator-only**, reserved for genuinely erroneous rows. Enforced server-side (403 for non-admins) and reflected in the UI (delete controls hidden from non-admins).

### KP-CONTACT-VIEW-03: Value corrections are administrator-only

**Trigger:** A phone number or street address was recorded wrong.

A non-admin may change only the **lifecycle flags** (`is_current`, `is_primary`) on a sub-resource. Correcting a **value** — a phone number, an address line, an identifier label — is an administrator action (403 for non-admins). **Exception:** an affiliation's descriptive fields (title, department, role) remain user-editable; only the employer *company link* is protected (KP-CONTACT-VIEW-06).

### KP-CONTACT-VIEW-04: Mark inactive, with a floor of one active email

**Trigger:** An identifier is stale but should be retained.

**Step 1 — Any identifier may be marked inactive** (`is_current = 0`), rendered muted in both views.

**Step 2 — At least one active email must remain.** The API rejects marking or deleting the last active email. No floor applies to phones, addresses, or employers — a contact may have zero, or only inactive ones. *(Enforcement tracked as CM-34; not yet built.)*

### KP-CONTACT-VIEW-05: An inactive email still resolves duplicates

**Trigger:** Mail arrives from an address a contact no longer uses.

An inactive email **still participates in identity resolution** — "inactive" means "do not send here," not "forget this." An old address must still resolve inbound mail to the right contact. This is the current behavior for emails (`identity_resolution.py` does not filter emails on `is_current`); phones are filtered on `is_current`. The asymmetry is deliberate (an old email rarely changes hands; an old phone number is reassigned to a stranger) and is to be documented in [contact-identity-resolution-prd.md]. *(Open item — see §9.)*

### KP-CONTACT-VIEW-06: Changing employer preserves history

**Trigger:** A contact changes jobs.

"Change company" is **not** an edit of the company link and **not** a delete of the old affiliation. It is: add the new affiliation, then mark the prior one inactive (`is_current = 0`, `is_primary = 0`), preserving the employment history the read view shows as a timeline. *(Enforced in the UI as of the CM-30/31 security tightenings; the old delete-then-add path is removed.)*

### KP-CONTACT-VIEW-07: Deactivating the primary auto-promotes

**Trigger:** The primary email/phone is marked inactive.

Deactivating the identifier currently marked primary **auto-promotes** the next active identifier of that type to primary and clears the flag on the deactivated row, so a contact never has an inactive primary. *(Enforcement tracked as CM-35; not yet built.)*

---

## 4. Contact Preview Card

**Supports processes:** read entry point.

The condensed card shown in the shell's preview panel and in search results. Largely exists today (`ContactPreviewCard`); this PRD only aligns it with the full view's identity treatment (name, avatar, current title @ company, primary email/phone, lead status, engagement score, possible-duplicate badge).

**Tasks:**

- [ ] CTV-01: Align the Contact Preview Card header with the Full View Identity Card (avatar, name, title@company, status, score)
- [ ] CTV-02: Show a "Possible duplicate" badge linking to the review queue when `is_possible_duplicate`

**Tests:**

- [ ] CTV-T01: Preview card renders name, avatar, current title and company, primary email/phone, lead status, engagement score
- [ ] CTV-T02: Possible-duplicate badge appears only when flagged and links to `/app/review`

---

## 5. Full View — Responsive Layout

**Supports processes:** all read.

A bespoke `ContactFullView` replacing the generic `RecordDetail` zones for contacts, mounted at `/app/contacts/:id` when expanded. Two-column responsive layout mirroring the conversation full view: **Identity Card full-width on top**; primary column (activity/timeline, ≥40% width) on the left; CRM sidebar (identifiers, employment, relationships, intelligence, notes, metadata; 280px–60%) on the right, independently scrolled, with a per-record persisted splitter. Cards with no data are suppressed. Below the two-column breakpoint, cards stack in the single-column order of §14 (of the analogous conversation doc).

**Tasks:**

- [ ] CTVL-01: Create `ContactFullView` and route contacts through it instead of the generic `RecordDetail`
- [ ] CTVL-02: Two-column responsive layout with per-record persisted splitter and independent sidebar scroll
- [ ] CTVL-03: Suppress empty cards; define single-column stack order

**Tests:**

- [ ] CTVL-T01: Contacts render `ContactFullView`, not the generic zones
- [ ] CTVL-T02: Below the two-column width, cards stack in the defined order; splitter position persists per contact

---

## 6. Full View — Cards

**Supports processes:** all read. Each card names the payload it needs beyond today's `GET /contacts/{id}` (`identity`/`context`/`timeline`); the delta is for the Entity TDD.

- **6.1 Identity Card** — avatar, first/last/display name, current title @ company, lead status, engagement + intelligence scores, possible-duplicate badge, "Edit" button → Edit page. *Payload: mostly present.*
- **6.2 Identifiers Card** — emails, phones, social handles grouped by type, each with label, primary star, and **active/inactive state** (muted when inactive). Add + mark-inactive inline; delete/value-correction only for admins. *Payload delta: full identifier list with `label`, `is_primary`, `is_current`, `verified`.*
- **6.3 Employment Card** — current and past affiliations as a history (company, title, department, role, date range), current ones first, past ones muted. "Change company" per KP-CONTACT-VIEW-06. *Payload delta: full `contact_companies` history, not just current.*
- **6.4 Addresses Card** — addresses with type and active state. *Payload delta: address list with `is_current`.*
- **6.5 Relationships Card** — contact-to-contact relationships with type and direction. *Payload: present in `context`.*
- **6.6 Intelligence Card** — engagement + intelligence score breakdown and any AI briefing; tinted background. *Payload delta: score components; AI summary if available.*
- **6.7 Activity / Timeline Card** — merged communications, conversations, events (primary column). *Payload: present in `timeline`, may need pagination beyond top-N.*
- **6.8 Notes Card** — attached notes with "+ Add". *Payload: via `EntityNotesCard`.*
- **6.9 Metadata Card** — ID, source, status, created/updated, collapsed by default. *Payload: present.*

**Tasks:**

- [ ] CTVC-01: Identity Card with scores and Edit entry point
- [ ] CTVC-02: Identifiers Card grouped by type, active/inactive state, add + mark-inactive; admin-only delete/correct
- [ ] CTVC-03: Employment Card as current+past history with "Change company" (deactivate + add)
- [ ] CTVC-04: Addresses Card with active state
- [ ] CTVC-05: Relationships Card
- [ ] CTVC-06: Intelligence Card (score breakdown + AI briefing, tinted)
- [ ] CTVC-07: Activity/Timeline Card (communications + conversations + events)
- [ ] CTVC-08: Notes Card
- [ ] CTVC-09: Metadata Card (collapsed)
- [ ] CTVC-10: Extend `GET /contacts/{id}` payload with the per-card deltas above

**Tests:**

- [ ] CTVC-T01: Identifiers Card renders inactive identifiers muted and hides delete from non-admins
- [ ] CTVC-T02: Employment Card shows past employers muted, current first; "Change company" adds new and deactivates old
- [ ] CTVC-T03: Empty cards (no addresses, no relationships) are suppressed
- [ ] CTVC-T04: Metadata Card collapsed by default; scores render read-only

---

## 7. Edit Page

**Supports processes:** KP-CONTACT-VIEW-01…07.

A **separate page** on its own route (not a modal), replacing `ManageRecordModal` as the contact-edit surface. Renders inputs strictly per §2.1.

- **7.1 Core fields** — first name, last name, display name (with reset-to-computed), avatar URL, lead source, lead status. `Direct`/`Override` only.
- **7.2 Identifiers editor** — add; mark inactive; set primary. Value edits and deletes are admin-only (hidden otherwise). Email value is never editable (KP-01). Enforces the one-active-email floor (KP-04).
- **7.3 Employment editor** — edit title/department/role (user-allowed); "Change company" via deactivate + add (KP-06); mark inactive; set primary. Delete admin-only.
- **7.4 Addresses editor** — add; mark inactive; set primary. Value edits and deletes admin-only.
- **7.5 Save & navigation** — save returns to the Full View; unsaved-changes guard.

**Tasks:**

- [ ] CTVE-01: Edit page route + shell; navigate from the Identity Card "Edit" button
- [ ] CTVE-02: Core-fields form honoring the §2.1 Editable contract (no input for non-editable fields)
- [ ] CTVE-03: Identifiers editor (add / mark-inactive / set-primary; admin-only delete + correct; no email value edit)
- [ ] CTVE-04: Employment editor (title/dept/role user-editable; change-company = deactivate+add; admin-only delete)
- [ ] CTVE-05: Addresses editor (add / mark-inactive / set-primary; admin-only delete + correct)
- [ ] CTVE-06: One-active-email floor surfaced in the UI (disable the last active email's deactivate/delete)
- [ ] CTVE-07: Decommission `ManageRecordModal` for contacts once the Edit page reaches parity

**Tests:**

- [ ] CTVE-T01: No input is rendered for Company Name, scores, Source, Status, or other non-editable fields
- [ ] CTVE-T02: Email value has no edit control; add + mark-inactive available; last active email cannot be deactivated
- [ ] CTVE-T03: Non-admin sees no delete or value-correction controls; admin does
- [ ] CTVE-T04: "Change company" deactivates the prior affiliation and adds the new one; no delete occurs

---

## 8. Migration from the Generic Detail

Contacts move off the shared `RecordDetail` (`IdentityZone`/`ContextZone`/`TimelineZone`) and the `ManageRecordModal` onto the bespoke Full View + Edit page. Companies/events/projects keep the generic detail. `RecordDetail` stays for those; the contact branch is redirected to `ContactFullView`.

**Tasks:**

- [ ] CTVM-01: Route the contact branch of `DetailPanel`/`RecordModal`/`GlobalSearchModal` to `ContactFullView`
- [ ] CTVM-02: Remove the contact "Manage" modal entry point once CTVE-07 lands
- [ ] CTVM-03: Update [contact-management-prd.md] CM-08 and CM-39/40 status when this ships

**Tests:**

- [ ] CTVM-T01: Opening a contact from grid, search, and deep link all render `ContactFullView`
- [ ] CTVM-T02: Company/event/project details are unchanged (still generic `RecordDetail`)

---

## 9. Open Items

- **Payload shape (CTVC-10).** The bespoke cards need `GET /contacts/{id}` extended (full identifier list, full employment history, score components, metadata). The exact schema is for the Entity TDD; several cards are blocked on it.
- **Identifier-resolution asymmetry (KP-CONTACT-VIEW-05).** Inactive emails match for dedup; inactive phones do not. Recommended resolution: document the difference in [contact-identity-resolution-prd.md] rather than change behavior. Product-owner confirmation pending.
- **Frontend test harness.** The frontend has zero automated tests; every CTV-* UI story is currently verifiable only by driving the app. Standing up Vitest + Testing Library before CTVE/CTVC work is recommended and would be its own proposal.
- **Avatar UI.** `Avatar URL` is `Direct` but has no UI today; CTVE-02 introduces it. Confirm this is wanted now vs. deferred.

---

## Related Documents

| Document | Relationship |
|---|---|
| [contact-entity-base-prd.md] | Parent entity; authoritative field metadata (§1.4 Editable column) |
| [contact-management-prd.md] | Owns CM-08 (edit) and CM-30…CM-40; the security tightenings enforce §3 |
| [contact-identity-resolution-prd.md] | Owns dedup; KP-CONTACT-VIEW-05 asymmetry to be documented there |
| [contact-merge-split-prd.md] | Merge/split, linked from the view, not implemented here |
| [conversation-view-prd.md] | Structural precedent for a bespoke full view |
| [gui-functional-requirements-prd.md] | Layout, card, and interaction standards |
