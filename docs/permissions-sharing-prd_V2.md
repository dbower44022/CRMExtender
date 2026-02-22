# Product Requirements Document: Permissions & Sharing

## CRMExtender — Access Control, Visibility, User Lifecycle & External Sharing

**Version:** 2.0
**Date:** 2026-02-17
**Status:** Draft
**Parent Document:** [CRMExtender PRD v1.1](PRD.md)

> **V2.0 (2026-02-22):**
> Terminology standardization pass: Mojibake encoding cleanup. Cross-PRD links updated to current versions (Custom Objects V2, Views & Grid V5). Master Glossary V3 cross-reference added to glossary section.

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Problem Statement](#2-problem-statement)
3. [Goals & Success Metrics](#3-goals--success-metrics)
4. [User Personas & Stories](#4-user-personas--stories)
5. [Core Concepts & Terminology](#5-core-concepts--terminology)
6. [Role Model](#6-role-model)
7. [Sys Admin Flag](#7-sys-admin-flag)
8. [Record Visibility Model](#8-record-visibility-model)
9. [Sharing Model](#9-sharing-model)
10. [External Sharing](#10-external-sharing)
11. [Integration Permissions](#11-integration-permissions)
12. [User Lifecycle](#12-user-lifecycle)
13. [Impersonation Mode](#13-impersonation-mode)
14. [Query Engine Security Integration](#14-query-engine-security-integration)
15. [Shared Views & Data Sources](#15-shared-views--data-sources)
16. [Audit Logging](#16-audit-logging)
17. [Hard Delete Policy](#17-hard-delete-policy)
18. [Data Model](#18-data-model)
19. [API Design](#19-api-design)
20. [Phasing & Roadmap](#20-phasing--roadmap)
21. [Cross-PRD Reconciliation](#21-cross-prd-reconciliation)
22. [Dependencies & Related PRDs](#22-dependencies--related-prds)
23. [Open Questions](#23-open-questions)
24. [Glossary](#24-glossary)

---

## 1. Executive Summary

The Permissions & Sharing system is the most cross-cutting subsystem in CRMExtender. Every other PRD references it: the Data Sources query engine injects row-level security filters, the Views system enforces shared-view behavior, the Custom Objects framework gates entity type creation behind the Object Creator permission, the Communication subsystem scopes conversations by visibility, and the Contact Management system determines who can see and edit which contacts.

This PRD defines **who can do what, on which data, and how data moves between users and external parties.**

**Core design principles:**

- **Simple role tiers, not permission matrices** — Four fixed roles (Owner, Admin, Member, Viewer) with a Sys Admin flag provide sufficient granularity for teams of 10–30 users without the cognitive overhead of per-entity or per-action permission grids. One role per user, applied globally across all entity types.
- **Visibility as a first-class record attribute** — Every record has an explicit visibility state: private, shared, or public. This is not inferred from ownership or roles — it is a concrete field on the record that users and system defaults control.
- **Consistent model everywhere** — Records, views, data sources, and all other entities use the same private → shared → public visibility model with identical semantics. No special-casing.
- **Sharing definitions, not data** — Sharing a view or data source shares the rendering/query configuration. Each viewer sees only the records they have visibility to. Sharing is always safe.
- **Comprehensive audit trail** — Every permission-related action is logged as an immutable event: role changes, visibility changes, sharing events, impersonation sessions, authentication events, and user lifecycle transitions.
- **Graceful offboarding** — User lifecycle management (active → suspended → deactivated) ensures no data is lost when team members leave. Impersonation mode, ownership transfer, and integration disconnection provide a complete offboarding workflow.

**Relationship to other PRDs:**

- **[Custom Objects PRD](custom-objects-prd_v2.md)** — Provides the Object Creator permission as a discrete grantable capability. Field-level permissions (Phase 4) and record-level access control are defined here. Schema-per-tenant architecture is the multi-tenant isolation foundation.
- **[Data Sources PRD](data-sources-prd_V1.md)** — Row-level security filters are injected by the query engine based on the visibility and sharing rules defined here. Shared data source permissions follow the same model.
- **[Views & Grid PRD](views-grid-prd_V5.md)** — Shared view behavior, fork-on-write for personal overrides, and view-as-alert permissions reference this PRD.
- **[Contact Management PRD](contact-management-prd_V2.md)** — Contact ownership, visibility, and the contact ownership model question (Open Question #1 in that PRD) are resolved here.
- **[Communication PRD](email-conversations-prd.md)** — Conversation access, shared inbox permissions, and communication visibility depend on this PRD.

---

## 2. Problem Statement

### The Access Control Gap

CRMExtender's existing PRDs define rich capabilities — multi-channel communication tracking, AI conversation intelligence, flexible entity modeling, polymorphic views — but they all defer a critical question: **who is allowed to see and do what?**

Without a permissions model:

| Gap | Impact |
|---|---|
| **No record visibility control** | Every user sees every record. Sales reps see each other's private deal notes. Personal contacts mix with company contacts. No way to maintain private working space within a shared platform. |
| **No role differentiation** | A new team member has the same power as the workspace creator. Anyone can delete records, change system settings, connect integrations, or create entity types — including accidentally destructive actions. |
| **No offboarding story** | When a team member leaves, their data, connected accounts, and private records become orphaned. No way to transfer ownership, review private records, or cleanly disconnect their integrations without direct database access. |
| **No external collaboration** | Clients, partners, and external stakeholders cannot view shared data. Users resort to screenshots, manual exports, or third-party tools to share CRM data externally. |
| **No shared-but-safe data access** | The Views and Data Sources PRDs define sharing semantics (shared data sources, shared views) but have no mechanism to enforce row-level security. A shared "All Conversations" view would expose everyone's conversations to everyone, defeating the purpose of the communication intelligence system. |

### What Existing PRDs Have Established

Several PRDs have already made decisions that constrain this PRD's design:

- **Schema-per-tenant isolation** (Custom Objects, Communication) — Tenant boundaries are enforced at the PostgreSQL schema level. This PRD handles access control *within* a tenant.
- **Object Creator permission** (Custom Objects §6.4) — A discrete, grantable permission for entity type creation. This PRD defines how it integrates with the role model.
- **Field-level permissions as Phase 4** (Custom Objects §25) — Explicitly deferred. This PRD acknowledges and preserves that phasing.
- **Shared view fork-on-write** (Views §17.4) — Non-owners of shared views get personal overrides. This PRD does not change that behavior, but defines who can share and what viewers see.
- **Row-level security placeholders** (Data Sources §20.2) — The Data Sources PRD states that queries execute within the requesting user's security context. This PRD defines what that security context contains.
- **RBAC roles mentioned** (Contact Management §19.1) — Owner, Admin, Member, Viewer are referenced. This PRD formalizes them.
- **Universal fields** (Custom Objects §7) — Every record has `created_by` and `updated_by`. This PRD adds `visibility` and `owner_id` to the universal field set.

---

## 3. Goals & Success Metrics

### Primary Goals

1. **Role-based access control** — Four fixed role tiers with clear, predictable capability boundaries. One role per user, applied globally.
2. **Record-level visibility** — Every record has an explicit visibility state (private, shared, public) controllable by the owner and system defaults.
3. **Consistent sharing model** — Records, views, data sources, and all entities use the same visibility and sharing semantics.
4. **Query engine integration** — Row-level security is enforced at the query engine level, ensuring that shared data sources and views respect visibility without application-layer filtering.
5. **User lifecycle management** — Active → Suspended → Deactivated states with clean offboarding: impersonation, ownership transfer, integration disconnection.
6. **External sharing** — Read-only portal and link-based sharing for external contacts with authentication, expiration, and revocation controls.
7. **Comprehensive audit logging** — Every permission-related action is immutably logged.

### Success Metrics

| Metric | Target | Measurement |
|---|---|---|
| Time to understand role capabilities | <5 minutes for new user | User testing: task completion time |
| Incorrect access attempts blocked | >99.9% of unauthorized access filtered by query engine | Instrumented query engine metrics |
| Offboarding completion time | <15 minutes for full user offboarding | Measured from suspend → deactivation with all transfers complete |
| External share adoption | >20% of tenants use external sharing within 60 days | Analytics: external share creation events |
| Audit log completeness | 100% of permission-related actions logged | Integration tests: action → audit event mapping |
| Visibility default satisfaction | >80% of records created with correct visibility without manual override | Analytics: manual visibility change rate within 5 minutes of creation |
| Role assignment correctness | >95% of users keep initial role for 30+ days | Analytics: role change frequency as inverse proxy |

---

## 4. User Personas & Stories

### Personas

| Persona | Role Context | Key Needs |
|---|---|---|
| **Doug — Workspace Owner** | Created the workspace for his multi-city gutter cleaning business. 15 employees across 3 cities. Pays the bill. | Control who can change system settings. Ensure employees see the right data. Offboard departing employees cleanly. Share job details with property managers. |
| **Sarah — Sys Admin** | Office manager. Doug delegated user management to her. Admin role + Sys Admin flag. | Invite/remove team members. Set role levels. Handle day-to-day access requests. Manage shared inboxes. Impersonate suspended users for data recovery. |
| **Mike — Sales Rep (Member)** | Manages his own prospect pipeline. Has personal contacts he doesn't want the team to see. | Keep personal contacts private. Share deal-related contacts with the team. Create custom views for his pipeline. Access shared team views. |
| **Jen — New Hire (Member)** | Just joined the team. Needs access to public records and shared views. | See public contacts and conversations. Access shared team views without configuration. Create her own private working space as she builds her pipeline. |
| **Carlos — Part-Time Viewer** | Part-time bookkeeper who needs to see records but not modify them. | View public contacts and financial data. Export reports. Cannot create or modify records. |
| **Lisa — External Property Manager** | Manages properties that Doug's business services. Not a team member. | View job details and schedules shared with her. Access via portal or shared link. No ability to modify data. |

### User Stories

#### Roles & Access

- **US-P1:** As a workspace owner, I want a simple role system (Owner, Admin, Member, Viewer) so that I can assign appropriate access levels without configuring complex permission matrices.
- **US-P2:** As a workspace owner, I want to designate one or more Sys Admins who can manage users and system settings on my behalf.
- **US-P3:** As a Sys Admin, I want to invite users, assign roles, and deactivate accounts so that I control who has access to the workspace.
- **US-P4:** As an Admin, I want to see and access all records in the workspace regardless of visibility, so that I can manage team data effectively.
- **US-P5:** As a Member, I want to create records, views, data sources, and use all operational features so that I can do my job without waiting for admin approval.
- **US-P6:** As a Viewer, I want read-only access to records I have visibility to, plus the ability to create personal views and data sources, so that I can analyze data without risk of accidental modification.

#### Record Visibility

- **US-P7:** As a user, I want every record I create to follow my default visibility setting (private or public) so that I don't have to set it manually every time.
- **US-P8:** As a user, I want to override the default visibility when creating a record manually, so that I can keep specific records private even when my default is public.
- **US-P9:** As a Sys Admin, I want to set the system-wide default visibility for new records (private or public) so that the team's baseline behavior is appropriate for our business.
- **US-P10:** As a user, I want to override the system default with my own personal default so that my workflow matches my needs.
- **US-P11:** As a user, I want to change a record's visibility from private to public (or vice versa) at any time, so that I can adjust access as situations change.
- **US-P12:** As a user, I want records auto-created by the system (email sync, conversation threading) to follow the system/user default visibility setting, so that automated processes respect my preferences.

#### Sharing

- **US-P13:** As a user, I want to share a private record with specific team members so that they can see it without making it public to everyone.
- **US-P14:** As a user who received a shared record, I want view-only access so that I can reference it without accidentally modifying the owner's data.
- **US-P15:** As a user, I want to share a record with an external contact via an authenticated portal so that clients and partners can view relevant data.
- **US-P16:** As a user, I want to generate a shareable link for a record so that I can share with anyone without requiring them to authenticate.
- **US-P17:** As a user, I want shared links to have configurable expiration dates and the ability to revoke them so that I maintain control over external access.
- **US-P18:** As a user, I want the same sharing model for records, views, and data sources — private, shared, public — so that I don't have to learn different rules for different things.

#### User Lifecycle

- **US-P19:** As a Sys Admin, I want to suspend a user's account immediately so that a departing employee is locked out without losing any data.
- **US-P20:** As a Sys Admin, I want to impersonate a suspended user so that I can review their private records, transfer ownership, and disconnect their integrations.
- **US-P21:** As a Sys Admin, I want to bulk-transfer a user's record ownership to another user or make records public so that data isn't orphaned during offboarding.
- **US-P22:** As a Sys Admin, I want to disconnect a suspended user's personal integrations (email, phone, LinkedIn) so that OAuth tokens are revoked and syncing stops.
- **US-P23:** As a Sys Admin, I want to deactivate a user account after offboarding is complete so that their seat is freed and login is permanently disabled.
- **US-P24:** As a user, I want to see a "Former User: Jane Smith" attribution on records created by deactivated users so that the historical record is preserved.

#### Audit

- **US-P25:** As a Sys Admin, I want a complete audit log of all permission-related actions (role changes, visibility changes, sharing events, impersonation sessions) so that I have full accountability.
- **US-P26:** As a workspace owner, I want impersonation actions to be clearly attributed ("User X acting as User Y") so that there is no ambiguity about who performed what action.

---

## 5. Core Concepts & Terminology

| Term | Definition |
|---|---|
| **Tenant** | The top-level organizational unit. Equivalent to a workspace. One tenant = one team = one PostgreSQL schema. All access control operates within a single tenant. |
| **Role** | One of four fixed tiers (Owner, Admin, Member, Viewer) assigned to each user. Determines capability boundaries. One role per user per tenant, applied globally across all entity types. |
| **Sys Admin** | An additive flag on any user (regardless of role) that grants user management and system settings access. Not a role tier — a capability overlay. |
| **Visibility** | A concrete attribute on every record: `private`, `shared`, or `public`. Determines who can discover and view the record. |
| **Private** | Visible only to the record owner and users with Admin+ role. Other Members and Viewers cannot see the record unless explicitly shared. |
| **Shared** | Private, but with explicit access grants to specific internal users or external contacts. The record does not appear in public queries. |
| **Public** | Visible to all users in the tenant, subject to their role capabilities (e.g., Viewers can see but not edit). |
| **Owner (record)** | The user who created the record, or to whom ownership was transferred. Distinct from the Owner role — a record owner is any user who owns a specific record. |
| **Owner (role)** | The highest role tier. The user responsible for billing and account closure. Functionally identical to Admin for day-to-day operations. Can demote Admins. |
| **Share Grant** | An explicit access grant from a record owner to a specific user (internal) or external contact. Grants view-only access. |
| **Link Share** | An access mechanism using a secret URL. Anyone with the link can view the record without authentication. Subject to expiration and revocation. |
| **External Contact** | A person outside the tenant who has been granted access to specific records via share grants or link shares. Accesses data through a read-only portal or API. |
| **Impersonation** | A Sys Admin capability to act within another user's security context. All actions are logged with dual attribution. |
| **User Lifecycle State** | One of: Active, Suspended, Deactivated. Controls login capability and data accessibility. |
| **Fork-on-Write** | The behavior where modifying a shared view or data source creates a personal copy of the modifications without affecting the shared definition. Defined in Views PRD §17.4. |
| **Security Context** | The combination of user identity, role, Sys Admin flag, tenant ID, and visibility filters that the query engine uses to scope all data access. |
| **Object Creator** | A discrete permission (not a role) that allows a user to create custom entity types. Defined in Custom Objects PRD §6.4. |

---

## 6. Role Model

### 6.1 Role Tiers

CRMExtender uses four fixed role tiers. Every user has exactly one role, assigned at invite time and changeable by Sys Admins. Roles apply globally across all entity types — there is no per-entity-type role assignment.

| Role | Data Access | Record Operations | System Operations |
|---|---|---|---|
| **Owner** | All records (regardless of visibility) | Full CRUD on all records | Billing & subscription management. Account closure. Demote Admins. All Admin capabilities. |
| **Admin** | All records (regardless of visibility) | Full CRUD on all records | Manage integrations. Create/edit/delete data sources (including SQL mode). Object Creator permission by default. All Member capabilities. |
| **Member** | Own private records + shared-with-me records + all public records | Full CRUD on own records. View-only on shared records. Full CRUD on public records (subject to entity-level rules). | Create/edit/delete own views and data sources (including SQL mode). Create records. Export data. Object Creator permission by default. Connect personal integrations. |
| **Viewer** | Own private records + shared-with-me records + all public records | View-only on all visible records. Cannot create, edit, or delete records. | Create personal views and data sources. Export data. |

### 6.2 Role Hierarchy

Roles form a strict hierarchy: Owner > Admin > Member > Viewer. Higher roles inherit all capabilities of lower roles.

```
Owner
  ├── All Admin capabilities
  ├── Billing & subscription management
  ├── Account closure / deletion
  └── Demote Admins

Admin
  ├── All Member capabilities
  ├── See all records (regardless of visibility)
  ├── Full CRUD on all records
  ├── Manage tenant-level integrations (shared inboxes)
  └── Object Creator (by default)

Member
  ├── All Viewer capabilities
  ├── Full CRUD on own records
  ├── Full CRUD on public records
  ├── View-only on shared-with-me records
  ├── Connect personal integrations
  ├── Create/share views and data sources
  └── Object Creator (by default)

Viewer
  ├── View own private + shared + public records
  ├── Create personal views and data sources
  └── Export visible data
```

### 6.3 Role Assignment Rules

- The first user in a tenant is automatically assigned the **Owner** role and the **Sys Admin** flag.
- Only one user can hold the Owner role at a time. Transferring ownership requires the current Owner to explicitly reassign it.
- Sys Admins assign roles to other users at invite time or via role management.
- A Sys Admin cannot assign a role higher than their own role (unless they are also the Owner).
- Role changes take effect immediately and are logged in the audit trail.

### 6.4 Member CRUD on Public Records

Members have full CRUD on public records, but with guardrails:

- **Create:** Members can create new records. Visibility follows their default setting.
- **Read:** Members can read all public records.
- **Update:** Members can edit public records. The `updated_by` field records who made the change. Event sourcing captures the full mutation history.
- **Delete:** Members can archive (soft delete) public records they created. Archiving records created by other users requires Admin role.
- **Rationale:** In a team of 10–30, Members need to collaborate freely on shared data. The event sourcing audit trail provides accountability. Restricting public record editing to owners-only would create bottlenecks.

### 6.5 Object Creator Permission

The Object Creator permission (defined in Custom Objects PRD §6.4) allows creation of custom entity types, which triggers DDL operations. It is:

- Granted to **Admin** and **Member** roles by default.
- **Not** granted to Viewer role.
- Revocable by Sys Admins on a per-user basis (e.g., if a specific Member should not create entity types).
- The only discrete permission in the system that exists outside the role hierarchy. All other capabilities are determined by role tier.

### 6.6 Discrete Permissions Model

Beyond the four role tiers, certain high-impact capabilities are modeled as discrete permissions that Sys Admins can grant or revoke per user, independent of role:

| Permission | Default Grant | Revocable | Description |
|---|---|---|---|
| **Object Creator** | Admin, Member | Yes | Create custom entity types (triggers DDL). |

Future discrete permissions (post-v1) may include: Raw SQL Data Source Author, Integration Manager, Bulk Delete. These are identified as candidates but not defined in this PRD.

---

## 7. Sys Admin Flag

### 7.1 Definition

Sys Admin is an **additive capability flag**, not a role tier. It is layered on top of any role (Owner, Admin, Member, Viewer) and grants two specific powers:

1. **User management** — Invite users, assign roles, change roles, suspend/deactivate accounts, impersonate users.
2. **System settings** — Tenant-wide configuration: default visibility, integration management (tenant-level), system defaults, tenant profile.

### 7.2 Assignment Rules

- The first user in the tenant receives Sys Admin automatically.
- Only existing Sys Admins can grant or revoke the Sys Admin flag on other users.
- Multiple users can hold the Sys Admin flag simultaneously.
- The Sys Admin flag is independent of role — a Member with Sys Admin can manage users but still has Member-level data access (i.e., cannot see other users' private records unless impersonating).
- At least one user in the tenant must have the Sys Admin flag at all times. The system prevents removing the flag from the last Sys Admin.

### 7.3 Sys Admin + Role Interaction

The Sys Admin flag does **not** elevate data access. A Member with Sys Admin sees the same records as a Member without it. The flag only adds user management and system settings capabilities.

Exception: **Impersonation mode** (Section 13) allows a Sys Admin to temporarily operate within another user's security context, which may grant access to records the Sys Admin wouldn't otherwise see in their own context.

| Role + Sys Admin | Data Access | Added Capabilities |
|---|---|---|
| Owner + Sys Admin | All records | User management, system settings |
| Admin + Sys Admin | All records | User management, system settings |
| Member + Sys Admin | Own + shared + public | User management, system settings, impersonation |
| Viewer + Sys Admin | Own + shared + public (view-only) | User management, system settings, impersonation |

---

## 8. Record Visibility Model

### 8.1 Visibility States

Every record in the system has a `visibility` field with one of three values:

| State | Who Can See | Who Can Edit | How It Gets This State |
|---|---|---|---|
| **`private`** | Record owner + Admins/Owner role | Record owner + Admins/Owner role | User creates with private default, or explicitly marks private |
| **`shared`** | Record owner + explicitly shared users + Admins/Owner role | Record owner + Admins/Owner role | Owner shares the private record with specific users |
| **`public`** | All tenant users | Owner + Admins/Owner role + Members (see §6.4) | User creates with public default, or explicitly marks public |

### 8.2 Visibility as a Universal Field

The `visibility` field is added to the set of universal fields defined in Custom Objects PRD §7. Every entity type — system and custom — carries this field on every record.

| Field | Type | Default | Description |
|---|---|---|---|
| `visibility` | TEXT | Determined by defaults cascade | One of: `private`, `shared`, `public` |
| `owner_id` | TEXT | `created_by` at creation time | FK → users. The user who owns this record. Transferable. |

These fields are managed by the framework and cannot be removed or renamed by users, consistent with existing universal fields (`id`, `tenant_id`, `created_at`, `updated_at`, `created_by`, `updated_by`, `archived_at`).

### 8.3 Defaults Cascade

When a record is created (manually or by system automation), its visibility is determined by a cascade:

```
1. Explicit user choice (manual creation only)
       ↓ (if not specified)
2. User-level default setting
       ↓ (if not set)
3. System-level default setting (tenant-wide)
       ↓ (if not set)
4. Platform default: private
```

**System-level default:** Set by Sys Admin in tenant settings. Applies to all users who haven't set their own override. Applies to all system-automated record creation (email sync, conversation threading, enrichment).

**User-level default:** Set by each user in their personal settings. Overrides the system default for records they create.

**Explicit choice:** When creating a record manually, the user can always choose private or public, regardless of defaults.

### 8.4 Visibility Transitions

| From | To | Who Can Do It | Notes |
|---|---|---|---|
| `private` | `public` | Record owner, Admin, Owner | Makes the record visible to everyone in the tenant |
| `private` | `shared` | Record owner, Admin, Owner | Adds specific share grants (Section 9) |
| `public` | `private` | Record owner, Admin, Owner | Removes from public view. Existing share grants are preserved. |
| `shared` | `public` | Record owner, Admin, Owner | Makes the record visible to everyone. Share grants become redundant but are preserved. |
| `shared` | `private` | Record owner, Admin, Owner | Revokes all share grants. Record becomes fully private. |
| `public` | `shared` | Record owner, Admin, Owner | Removes from public view. Owner can then add specific share grants. |

### 8.5 Visibility Conflict Resolution

When the same real-world entity is created independently by two users (e.g., two users import the same contact), the system must resolve the conflict. The general principle: **the more permissive visibility wins.**

- If User A has a private "John Smith" contact, and User B imports and marks "John Smith" as public, the merged/resolved record becomes public.
- The entity resolution system (Contact Management PRD §7) handles the merge. The Permissions system provides the rule: merged records inherit the most permissive visibility of their sources.
- Visibility conflict resolution is logged in the audit trail.

### 8.6 Auto-Created Records

Records created by system processes follow the defaults cascade:

| Creation Trigger | Visibility Source |
|---|---|
| **Email sync** (personal account) | The connected account owner's user default → system default → private |
| **Email sync** (shared inbox) | Always `public` (shared inboxes exist for team visibility) |
| **Conversation auto-creation** | Inherits from the triggering communication's visibility |
| **Contact auto-creation** (from communication participant) | The communication owner's user default → system default → private |
| **AI-inferred relationships** | `private` to the user who triggered the inference, until confirmed |
| **Enrichment data** | Inherits visibility of the enriched record |

---

## 9. Sharing Model

### 9.1 Internal Sharing

A record owner can share a private record with specific internal users. Sharing grants **view-only** access — the shared user can see the record but cannot edit, archive, or change its visibility.

**Share Grant Model:**

| Attribute | Type | Description |
|---|---|---|
| `id` | TEXT | Prefixed ULID: `shg_` prefix |
| `record_id` | TEXT | The record being shared |
| `record_type` | TEXT | Entity type slug (e.g., `contacts`, `conversations`) |
| `grantor_id` | TEXT | FK → users. The user who created the share grant. |
| `grantee_type` | TEXT | `user` or `external_contact` |
| `grantee_id` | TEXT | FK → users (for internal) or external contact identifier |
| `access_level` | TEXT | `view` (only value for v1; future: `edit`, `comment`) |
| `created_at` | TIMESTAMP | When the share was created |
| `expires_at` | TIMESTAMP | Optional expiration. NULL = no expiration. |
| `revoked_at` | TIMESTAMP | NULL if active. Set when revoked. |

### 9.2 Sharing Rules

- Only the record owner and Admin/Owner role can create share grants.
- Shared users get view-only access. They cannot re-share the record with others.
- Revoking a share grant removes the user's access immediately.
- If a record transitions from `shared` → `private`, all share grants are revoked.
- If a record transitions from `shared` → `public`, share grants become redundant but are preserved (in case the record is later made private again).
- Share grants are visible to the record owner and Admins in the record's sharing panel.

### 9.3 Bulk Sharing

Users can share multiple records at once:

- Select multiple records in a view → "Share with..." action.
- All selected records receive the same share grants.
- Each record gets its own share grant record (no batch grant — individual grants for audit trail clarity).

---

## 10. External Sharing

### 10.1 Overview

External sharing extends record visibility outside the tenant to people who are not CRMExtender users. Two mechanisms:

1. **Authenticated sharing** — Share with a specific external contact who accesses via a read-only portal with authentication (email-based magic link or password).
2. **Link sharing** — Generate a secret URL that grants read-only access to anyone who has it, without authentication.

### 10.2 Authenticated External Sharing

An external contact receives a share grant (same model as internal sharing, with `grantee_type = 'external_contact'`). To access the shared data:

1. External contact receives an email notification with a portal link.
2. They authenticate via magic link (emailed one-time code) or a password they set.
3. The portal shows only the records explicitly shared with them.
4. All access is read-only.

**External Contact Registration:**

| Attribute | Type | Description |
|---|---|---|
| `id` | TEXT | Prefixed ULID: `ext_` prefix |
| `tenant_id` | TEXT | Which tenant shared data with them |
| `email` | TEXT | Primary identifier and authentication target |
| `name` | TEXT | Display name |
| `auth_method` | TEXT | `magic_link` or `password` |
| `password_hash` | TEXT | Bcrypt hash (only if auth_method = password) |
| `status` | TEXT | `active`, `disabled` |
| `created_at` | TIMESTAMP | |
| `last_accessed_at` | TIMESTAMP | Last portal access |

### 10.3 Link Sharing

Any record owner or Admin can generate a shareable link for a record.

**Link Share Model:**

| Attribute | Type | Description |
|---|---|---|
| `id` | TEXT | Prefixed ULID: `lsh_` prefix |
| `record_id` | TEXT | The record being shared |
| `record_type` | TEXT | Entity type slug |
| `creator_id` | TEXT | FK → users. Who generated the link. |
| `token` | TEXT | Cryptographically random URL-safe token (256-bit) |
| `access_level` | TEXT | `view` (only value for v1) |
| `expires_at` | TIMESTAMP | Required. No permanent links. Maximum duration configurable by Sys Admin (default: 90 days). |
| `revoked_at` | TIMESTAMP | NULL if active. Set when explicitly revoked. |
| `access_count` | INTEGER | Number of times the link has been accessed |
| `last_accessed_at` | TIMESTAMP | Last access time |
| `created_at` | TIMESTAMP | |

**Link Sharing Rules:**

- Every link share **requires an expiration date**. There are no permanent shareable links.
- Sys Admins configure the maximum allowed link duration (default: 90 days). Users can set shorter durations.
- Links are revocable at any time by the creator or any Admin.
- Each link access is logged (timestamp, IP address, user agent).
- If the underlying record's visibility changes to `private` and all share grants are revoked, link shares are also revoked automatically.
- Link shares use URL format: `https://{tenant}.crmextender.com/shared/{token}`

### 10.4 External Portal

The external portal is a read-only web interface for external contacts and link share recipients.

**Portal capabilities:**

- View shared record details (all public fields on the record).
- View related records only if those related records are also explicitly shared.
- No search, no listing, no discovery — external users see only what's been shared with them.
- No editing, no commenting (v1).
- Responsive design for mobile access.

**Portal security:**

- Authenticated sessions expire after 24 hours of inactivity.
- Link shares are validated on every request (check expiration and revocation).
- Rate limiting on portal endpoints.
- No API key issuance for external contacts in v1.

### 10.5 External API Access

For programmatic external access (e.g., property management software integrating with CRMExtender):

- External contacts with authenticated access can use a read-only API.
- API access requires an API token issued by the tenant (Sys Admin or Admin action).
- API tokens are scoped to the external contact's share grants — only shared records are accessible.
- API tokens have configurable expiration and are revocable.
- Rate-limited independently from internal API access.

---

## 11. Integration Permissions

### 11.1 Personal Integrations

Each user manages their own connected accounts (email, phone, LinkedIn, etc.):

- Users connect and disconnect their own accounts in their settings.
- OAuth tokens are stored per user and are not accessible to other users (including Sys Admins, except via impersonation).
- Data synced from personal integrations follows the user's default visibility setting.
- Sys Admins can see that a user has connected integrations (for troubleshooting) but cannot access the integration credentials directly.

### 11.2 Tenant-Level Integrations (Shared Inboxes)

Shared inboxes and team-level integrations are connected at the tenant level:

- Only Sys Admins can connect, configure, and disconnect tenant-level integrations.
- Shared inbox credentials are stored at the tenant level, not associated with any individual user.
- Communications from shared inboxes are always `public` visibility.
- Multiple shared inboxes can be configured per tenant (e.g., sales@, support@, info@).

### 11.3 Integration Data Model

| Attribute | Type | Description |
|---|---|---|
| `id` | TEXT | Prefixed ULID: `int_` prefix |
| `tenant_id` | TEXT | Owning tenant |
| `owner_type` | TEXT | `user` or `tenant` |
| `owner_id` | TEXT | User ID (for personal) or tenant ID (for tenant-level) |
| `provider` | TEXT | `gmail`, `outlook`, `openphone`, `twilio`, `nylas`, `unipile`, etc. |
| `account_identifier` | TEXT | Email address, phone number, or account handle |
| `credentials_encrypted` | BYTEA | Encrypted OAuth tokens or API keys |
| `status` | TEXT | `active`, `paused`, `error`, `disconnected` |
| `last_sync_at` | TIMESTAMP | Last successful sync |
| `created_at` | TIMESTAMP | |
| `created_by` | TEXT | FK → users. Who connected this integration. |

### 11.4 Shared Inbox Communication Attribution

When a user responds via a shared inbox, the communication record captures both perspectives:

- **`from_address`** — The shared inbox address (what the external recipient sees).
- **`sent_by`** — The actual user who composed and sent the message (internal attribution).
- This dual attribution is critical for performance tracking, workload distribution, and audit purposes.

---

## 12. User Lifecycle

### 12.1 Lifecycle States

| State | Login | Data | Integrations | Visibility in Team |
|---|---|---|---|---|
| **Active** | Yes | Full access per role | Running | Appears in user lists, assignable |
| **Suspended** | No | Preserved, accessible via impersonation | Paused (sync stops, tokens retained) | Appears as "Suspended" in user lists, not assignable |
| **Deactivated** | No | Ownership transferred or made public. Records reference "Former User: {name}" | Disconnected (tokens revoked) | Hidden from active user lists. Appears in admin user management. |

### 12.2 State Transitions

```
Active ──→ Suspended ──→ Deactivated
  ↑            │
  └────────────┘
  (Reactivation)
```

- **Active → Suspended:** Sys Admin action. Immediate effect. Login blocked, integrations paused.
- **Suspended → Active:** Sys Admin action (reactivation). Login restored, integrations resumed.
- **Suspended → Deactivated:** Sys Admin action after offboarding is complete. Irreversible.
- **Active → Deactivated:** Not allowed directly. Must suspend first (forces the offboarding workflow).
- **Deactivated → Any:** Not allowed. Deactivation is permanent. A new user account can be created with the same email if needed.

### 12.3 Offboarding Workflow

When a user departs, the Sys Admin follows this sequence:

**Step 1: Suspend**
- Immediately blocks login.
- Stops all integration syncing (OAuth tokens retained for potential reactivation).
- The suspended user's records, views, data sources, and share grants remain intact.
- Team members who had shared records from this user retain their access.

**Step 2: Review (via Impersonation)**
- Sys Admin enters impersonation mode (Section 13) to see the suspended user's private records.
- Identifies records that need ownership transfer vs. records that can remain orphaned.

**Step 3: Transfer Ownership**
- Sys Admin bulk-transfers record ownership to another user or sets records to `public`.
- Transfer options:
  - **All records → specific user** (common: transfer to the departing user's replacement).
  - **All records → public** (common: small team, everyone should see everything).
  - **Selective transfer** — specific records to specific users.
- Ownership transfer updates `owner_id` and logs the transfer event.

**Step 4: Disconnect Integrations**
- Sys Admin disconnects all personal integrations via impersonation.
- OAuth tokens are revoked with the provider.
- Integration status changes to `disconnected`.

**Step 5: Deactivate**
- Sys Admin confirms deactivation.
- User account state changes to `deactivated`.
- User's seat is freed for new invites.
- All `created_by` and `updated_by` references to this user are preserved but display as "Former User: {name}".
- Any remaining share grants where this user is the grantee are revoked (they can no longer access shared data).

### 12.4 Data Retention After Deactivation

| Data Type | Retention |
|---|---|
| Records the user created | Persist. Ownership transferred during offboarding. |
| Records the user edited | Persist. `updated_by` references preserved. |
| Communications sent/received | Persist in conversation histories. |
| Event history | Persist. Immutable event stream is never modified. |
| Share grants (as grantor) | Revoked if still pointing to deactivated user as owner. Transferred records' share grants persist under new owner. |
| Share grants (as grantee) | Revoked. Deactivated users cannot access data. |
| Personal views & data sources | Archived. Not visible to other users unless they were shared. Recoverable by admin if needed. |
| Integration credentials | Destroyed (tokens revoked, encrypted credentials deleted). |
| User profile | Retained in deactivated state for historical reference. |

---

## 13. Impersonation Mode

### 13.1 Definition

Impersonation allows a Sys Admin to operate within another user's security context. While impersonating, the Sys Admin sees exactly what the target user would see and can perform actions on their behalf.

### 13.2 Access Rules

- Only users with the **Sys Admin** flag can initiate impersonation.
- Any user can be impersonated, regardless of lifecycle state (Active, Suspended, or even Deactivated for forensic purposes).
- Impersonation does not require the target user's password or consent.
- The impersonator's actions are constrained by the **target user's** role and visibility — not the impersonator's own role. (Exception: the impersonator retains Sys Admin-only capabilities like user management.)

### 13.3 Audit Trail

Impersonation is the highest-scrutiny action in the system. Every action during an impersonation session is logged with dual attribution:

| Audit Field | Value |
|---|---|
| `actor_id` | The Sys Admin performing the impersonation |
| `acting_as_id` | The target user being impersonated |
| `action` | The specific action taken |
| `timestamp` | When the action occurred |
| `session_id` | Unique impersonation session identifier |
| `ip_address` | The impersonator's IP address |

**Session logging:**
- Impersonation session start and end times are logged.
- All actions during the session reference the session ID.
- Impersonation sessions have a maximum duration (configurable, default: 1 hour). The session must be explicitly renewed to continue.

### 13.4 UI Indicators

When a Sys Admin is impersonating another user:

- A prominent, non-dismissible banner displays: "Viewing as {User Name} — All actions are logged."
- The banner includes the target user's name, role, and lifecycle state.
- An "End Impersonation" button returns to the Sys Admin's own session.
- The Sys Admin's own identity is preserved in the session — they don't "become" the other user for authentication purposes.

---

## 14. Query Engine Security Integration

### 14.1 Security Context

Every query executed by the Data Sources query engine (Data Sources PRD §15) operates within a security context derived from the requesting user:

```
SecurityContext:
  user_id:       usr_01HX...
  tenant_id:     tenant_abc
  role:          member
  is_sys_admin:  false
  visibility_filter:  [own_private, shared_with_me, public]
```

### 14.2 Row-Level Security Implementation

The query engine injects visibility filters as WHERE clause conditions on every query, before any user-defined filters are applied:

**For Owner/Admin roles:**
```sql
-- No visibility filter. Admins see all records.
SET search_path = tenant_abc, platform;
SELECT * FROM contacts WHERE {user_filters};
```

**For Member/Viewer roles:**
```sql
SET search_path = tenant_abc, platform;
SELECT * FROM contacts
WHERE (
  visibility = 'public'
  OR owner_id = :current_user_id
  OR id IN (
    SELECT record_id FROM share_grants
    WHERE grantee_id = :current_user_id
      AND grantee_type = 'user'
      AND revoked_at IS NULL
      AND (expires_at IS NULL OR expires_at > NOW())
      AND record_type = 'contacts'
  )
)
AND {user_filters};
```

### 14.3 Performance Considerations

The visibility filter adds overhead to every query for Member/Viewer roles. Optimizations:

- **Index on `visibility`** — Every entity table has an index on `(visibility)` for fast public-record filtering.
- **Index on `owner_id`** — Every entity table has an index on `(owner_id)` for fast owner-record filtering.
- **Share grants index** — The `share_grants` table has a composite index on `(grantee_id, grantee_type, record_type, revoked_at)` for fast share-grant lookups.
- **Materialized share set** — For users with many share grants, the query engine can pre-compute a set of shared record IDs and use `IN (...)` with the materialized set rather than a subquery. This is an optimization for Phase 2+.
- **Admin fast path** — Admin/Owner roles skip the visibility filter entirely, avoiding the subquery overhead.

### 14.4 Cross-Entity Query Security

When a data source JOINs across entity types (e.g., Conversations JOIN Contacts), the visibility filter is applied **per entity type** in the JOIN:

```sql
SELECT c.*, ct.name AS contact_name
FROM conversations c
JOIN contacts ct ON c.primary_contact_id = ct.id
WHERE (
  -- Conversation visibility
  c.visibility = 'public'
  OR c.owner_id = :current_user_id
  OR c.id IN (SELECT record_id FROM share_grants WHERE ...)
)
AND (
  -- Contact visibility
  ct.visibility = 'public'
  OR ct.owner_id = :current_user_id
  OR ct.id IN (SELECT record_id FROM share_grants WHERE ...)
)
AND {user_filters};
```

This ensures that a user cannot see a private contact's details by viewing a public conversation that references that contact. The JOINed record is filtered to NULL if the user doesn't have visibility.

### 14.5 Impersonation Context

During impersonation, the security context reflects the **target user**, not the impersonator:

```
SecurityContext:
  user_id:       usr_TARGET...        ← target user
  tenant_id:     tenant_abc
  role:          member               ← target user's role
  is_sys_admin:  false                ← target user's flag
  visibility_filter:  [own_private, shared_with_me, public]
  impersonated_by: usr_ADMIN...       ← for audit only
```

---

## 15. Shared Views & Data Sources

### 15.1 Consistent Visibility Model

Views and Data Sources follow the same private → shared → public visibility model as records:

| Visibility | Who Can See | Who Can Edit |
|---|---|---|
| **Private** | Creator only + Admins/Owner | Creator only |
| **Shared** | Creator + explicitly shared users + Admins/Owner | Creator only |
| **Public** | All tenant users | Creator only |

### 15.2 Interaction with Record-Level Security

**Critical principle:** Sharing a view or data source shares the **configuration**, not the data. Each viewer sees only the records they have visibility to.

Example: A public "All Conversations" data source exists. User A (Admin) sees 500 conversations. User B (Member) sees 200 conversations (their own private + shared + public). Same data source, different results.

### 15.3 View-Specific Behaviors

These behaviors are already defined in the Views PRD §17.4 and remain unchanged:

- **Fork-on-write:** Modifying a shared/public view creates a personal override. The shared view is unchanged for others.
- **Duplication:** Any user can duplicate a shared/public view to create a personal copy.
- **Unshare:** The creator can revert a shared view to private. It disappears from others' view lists, but personal overrides and duplicates are preserved.

### 15.4 Data Source-Specific Behaviors

These behaviors are already defined in the Data Sources PRD §20 and remain unchanged:

- **Shared data source viewers** can create views referencing it but cannot edit the data source definition.
- **Duplication** to create a personal copy is always available.

---

## 16. Audit Logging

### 16.1 Philosophy

CRMExtender's audit philosophy is **log everything**. Every permission-related action produces an immutable audit event. Audit events are stored in a dedicated audit log table, separate from entity event stores, because they span across entity types and concern system-level actions.

### 16.2 Audited Actions

| Category | Events Logged |
|---|---|
| **Authentication** | Login success, login failure, session start, session end, password change, magic link issued |
| **Role changes** | Role assigned, role changed (from → to), Sys Admin flag granted, Sys Admin flag revoked |
| **Visibility changes** | Record visibility changed (from → to), with record ID and entity type |
| **Sharing** | Share grant created, share grant revoked, link share created, link share revoked, link share accessed |
| **Impersonation** | Impersonation session started, impersonation session ended, every action during impersonation |
| **User lifecycle** | User invited, user activated, user suspended, user reactivated, user deactivated, ownership transfer |
| **Integration events** | Integration connected, integration disconnected, integration paused, shared inbox added, shared inbox removed |
| **External access** | External contact created, external portal accessed, external API token issued, external API token revoked |
| **System settings** | Default visibility changed, max link share duration changed, any tenant-level setting changed |
| **Discrete permissions** | Object Creator granted, Object Creator revoked |

### 16.3 Audit Event Data Model

| Attribute | Type | Description |
|---|---|---|
| `id` | TEXT | Prefixed ULID: `aud_` prefix |
| `tenant_id` | TEXT | Which tenant |
| `actor_id` | TEXT | The user who performed the action |
| `acting_as_id` | TEXT | If impersonating: the target user. NULL otherwise. |
| `action` | TEXT | Action identifier (e.g., `role.changed`, `visibility.updated`, `impersonation.started`) |
| `entity_type` | TEXT | Entity type affected (if applicable) |
| `entity_id` | TEXT | Record affected (if applicable) |
| `details` | JSONB | Action-specific structured data (e.g., `{"from_role": "member", "to_role": "admin"}`) |
| `ip_address` | TEXT | Actor's IP address |
| `user_agent` | TEXT | Actor's browser/client identifier |
| `session_id` | TEXT | Impersonation session ID (if applicable) |
| `timestamp` | TIMESTAMP | Event timestamp |

### 16.4 Audit Log Retention

- Audit logs are retained for a minimum of **2 years** (configurable per tenant, can be longer).
- Audit logs are **immutable** — no updates or deletes, even by Sys Admins.
- Audit logs are stored in the `platform` schema (cross-tenant), partitioned by tenant and timestamp for query performance.
- Audit log queries are available to Sys Admins and Owner role via an admin interface and API.

---

## 17. Hard Delete Policy

### 17.1 Soft Delete as Default

CRMExtender uses **soft delete** (archive) as the default for all record deletion. Archived records:

- Set `archived_at` to the current timestamp.
- Are excluded from standard queries (filtered out by default in the query engine).
- Are recoverable by Admin/Owner role.
- Remain in the event store indefinitely.

### 17.2 Hard Delete Exceptions

Hard delete (permanent, irreversible removal from both the read model and event store) is permitted only in two scenarios:

**Scenario 1: Regulatory Compliance**

- GDPR right to erasure, CCPA deletion requests, or other jurisdiction-specific mandates.
- Requires **Sys Admin** action.
- The hard delete itself is logged in the audit trail (the audit log records that a deletion occurred, including what was deleted, but the actual record data is destroyed).
- Triggers cascade review: related records (share grants, link shares, communications referencing the deleted entity) are updated or cleaned up.

**Scenario 2: Unconfirmed Inferred Data**

- AI-generated relationships, auto-detected associations, enrichment data, and other system-inferred records that have **not been confirmed by a user**.
- These records have a `confirmation_status` field: `inferred` (unconfirmed) or `confirmed`.
- `inferred` records can be hard deleted by the system or by the user who triggered the inference.
- Once a user confirms an inferred record (changes status to `confirmed`), it becomes subject to standard soft-delete rules.
- Rationale: Inferred data that was never validated by a human is not "real" data. Allowing hard delete prevents accumulation of AI guesses that may be wrong.

### 17.3 Hard Delete Audit

Even hard deletes are logged in the audit trail:

| Audit Field | Value |
|---|---|
| `action` | `record.hard_deleted` |
| `entity_type` | The entity type |
| `entity_id` | The record ID (preserved in audit even though the record is destroyed) |
| `details` | `{"reason": "gdpr_erasure"}` or `{"reason": "unconfirmed_inferred"}` |
| `actor_id` | Who performed the deletion |

---

## 18. Data Model

### 18.1 Users Table

Stored in the `platform` schema (cross-tenant):

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | TEXT | PK | Prefixed ULID: `usr_` prefix |
| `tenant_id` | TEXT | NOT NULL, FK → tenants | Which tenant this user belongs to |
| `email` | TEXT | NOT NULL, UNIQUE | Login identifier |
| `name` | TEXT | NOT NULL | Display name |
| `role` | TEXT | NOT NULL | One of: `owner`, `admin`, `member`, `viewer` |
| `is_sys_admin` | BOOLEAN | NOT NULL, DEFAULT false | Sys Admin flag |
| `status` | TEXT | NOT NULL, DEFAULT 'active' | One of: `active`, `suspended`, `deactivated` |
| `default_visibility` | TEXT | | User-level default visibility override. NULL = use system default. |
| `avatar_url` | TEXT | | Profile picture URL |
| `invited_by` | TEXT | FK → users | Who invited this user |
| `last_login_at` | TIMESTAMP | | Last successful login |
| `created_at` | TIMESTAMP | NOT NULL | |
| `updated_at` | TIMESTAMP | NOT NULL | |
| `suspended_at` | TIMESTAMP | | When suspended (NULL if not suspended) |
| `deactivated_at` | TIMESTAMP | | When deactivated (NULL if not deactivated) |

### 18.2 Tenant Settings

Stored in the `platform` schema:

| Column | Type | Constraints | Description |
|---|---|---|---|
| `tenant_id` | TEXT | PK, FK → tenants | |
| `default_visibility` | TEXT | NOT NULL, DEFAULT 'private' | System-wide default for new records |
| `max_link_share_duration_days` | INTEGER | NOT NULL, DEFAULT 90 | Maximum expiration for link shares |
| `audit_retention_days` | INTEGER | NOT NULL, DEFAULT 730 | Minimum audit log retention (default 2 years) |
| `allow_external_sharing` | BOOLEAN | NOT NULL, DEFAULT true | Master toggle for external sharing |
| `allow_link_sharing` | BOOLEAN | NOT NULL, DEFAULT true | Master toggle for link shares |
| `updated_at` | TIMESTAMP | NOT NULL | |
| `updated_by` | TEXT | FK → users | |

### 18.3 Share Grants Table

Stored in each tenant schema:

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | TEXT | PK | Prefixed ULID: `shg_` prefix |
| `record_id` | TEXT | NOT NULL | The record being shared |
| `record_type` | TEXT | NOT NULL | Entity type slug |
| `grantor_id` | TEXT | NOT NULL, FK → users | Who created the share |
| `grantee_type` | TEXT | NOT NULL | `user` or `external_contact` |
| `grantee_id` | TEXT | NOT NULL | User ID or external contact ID |
| `access_level` | TEXT | NOT NULL, DEFAULT 'view' | `view` for v1 |
| `created_at` | TIMESTAMP | NOT NULL | |
| `expires_at` | TIMESTAMP | | NULL = no expiration |
| `revoked_at` | TIMESTAMP | | NULL = active |

**Indexes:**
- `(grantee_id, grantee_type, record_type, revoked_at)` — Primary lookup for query engine visibility filter.
- `(record_id, record_type)` — For listing all shares on a specific record.
- `(grantor_id)` — For listing all shares created by a user (useful for offboarding).

### 18.4 Link Shares Table

Stored in each tenant schema:

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | TEXT | PK | Prefixed ULID: `lsh_` prefix |
| `record_id` | TEXT | NOT NULL | The record being shared |
| `record_type` | TEXT | NOT NULL | Entity type slug |
| `creator_id` | TEXT | NOT NULL, FK → users | Who generated the link |
| `token` | TEXT | NOT NULL, UNIQUE | Cryptographic random token |
| `access_level` | TEXT | NOT NULL, DEFAULT 'view' | `view` for v1 |
| `expires_at` | TIMESTAMP | NOT NULL | Required expiration |
| `revoked_at` | TIMESTAMP | | NULL = active |
| `access_count` | INTEGER | NOT NULL, DEFAULT 0 | Times accessed |
| `last_accessed_at` | TIMESTAMP | | |
| `created_at` | TIMESTAMP | NOT NULL | |

**Indexes:**
- `(token)` — UNIQUE. Primary lookup for link access.
- `(record_id, record_type)` — For listing all links on a specific record.
- `(creator_id)` — For offboarding link cleanup.
- `(expires_at)` — For expired link cleanup job.

### 18.5 External Contacts Table

Stored in the `platform` schema:

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | TEXT | PK | Prefixed ULID: `ext_` prefix |
| `tenant_id` | TEXT | NOT NULL, FK → tenants | |
| `email` | TEXT | NOT NULL | UNIQUE per tenant |
| `name` | TEXT | | |
| `auth_method` | TEXT | NOT NULL, DEFAULT 'magic_link' | `magic_link` or `password` |
| `password_hash` | TEXT | | Bcrypt hash |
| `status` | TEXT | NOT NULL, DEFAULT 'active' | `active`, `disabled` |
| `created_at` | TIMESTAMP | NOT NULL | |
| `last_accessed_at` | TIMESTAMP | | |

### 18.6 Integrations Table

Stored in the `platform` schema:

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | TEXT | PK | Prefixed ULID: `int_` prefix |
| `tenant_id` | TEXT | NOT NULL, FK → tenants | |
| `owner_type` | TEXT | NOT NULL | `user` or `tenant` |
| `owner_id` | TEXT | NOT NULL | User ID or tenant ID |
| `provider` | TEXT | NOT NULL | Provider identifier |
| `account_identifier` | TEXT | NOT NULL | Email, phone, handle |
| `credentials_encrypted` | BYTEA | NOT NULL | Encrypted credentials |
| `status` | TEXT | NOT NULL, DEFAULT 'active' | `active`, `paused`, `error`, `disconnected` |
| `last_sync_at` | TIMESTAMP | | |
| `created_at` | TIMESTAMP | NOT NULL | |
| `created_by` | TEXT | NOT NULL, FK → users | |

**Indexes:**
- `(owner_type, owner_id)` — For listing all integrations for a user or tenant.
- `(tenant_id, provider, account_identifier)` — UNIQUE. Prevents duplicate connections.

### 18.7 Audit Log Table

Stored in the `platform` schema, partitioned by tenant and timestamp:

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | TEXT | PK | Prefixed ULID: `aud_` prefix |
| `tenant_id` | TEXT | NOT NULL | Partition key |
| `actor_id` | TEXT | NOT NULL | Who performed the action |
| `acting_as_id` | TEXT | | Impersonation target (NULL if not impersonating) |
| `action` | TEXT | NOT NULL | Dotted action identifier |
| `entity_type` | TEXT | | Affected entity type |
| `entity_id` | TEXT | | Affected record ID |
| `details` | JSONB | | Action-specific data |
| `ip_address` | TEXT | | |
| `user_agent` | TEXT | | |
| `session_id` | TEXT | | Impersonation session ID |
| `timestamp` | TIMESTAMP | NOT NULL | Partition key |

**Partitioning:** By `(tenant_id, timestamp)` with monthly partitions.

**Indexes:**
- `(tenant_id, timestamp)` — Primary query pattern.
- `(tenant_id, actor_id, timestamp)` — "What did user X do?"
- `(tenant_id, entity_type, entity_id, timestamp)` — "What happened to record Y?"
- `(tenant_id, action, timestamp)` — "Show me all role changes."

### 18.8 Discrete Permissions Table

Stored in the `platform` schema:

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | TEXT | PK | Prefixed ULID: `dpm_` prefix |
| `tenant_id` | TEXT | NOT NULL, FK → tenants | |
| `user_id` | TEXT | NOT NULL, FK → users | |
| `permission` | TEXT | NOT NULL | Permission identifier (e.g., `object_creator`) |
| `granted` | BOOLEAN | NOT NULL | `true` = explicitly granted, `false` = explicitly revoked (overrides role default) |
| `granted_by` | TEXT | NOT NULL, FK → users | Who granted/revoked |
| `created_at` | TIMESTAMP | NOT NULL | |
| `updated_at` | TIMESTAMP | NOT NULL | |

**Unique constraint:** `(tenant_id, user_id, permission)` — One record per user per permission.

**Resolution logic:** If a row exists, use its `granted` value. If no row exists, use the role's default grant (e.g., Admin and Member default to `granted = true` for `object_creator`).

---

## 19. API Design

### 19.1 User Management APIs

```
POST   /api/v1/users/invite              Invite a new user (Sys Admin only)
GET    /api/v1/users                      List all users in tenant (Sys Admin only)
GET    /api/v1/users/:id                  Get user details
PATCH  /api/v1/users/:id/role             Change user role (Sys Admin only)
PATCH  /api/v1/users/:id/sys-admin        Grant/revoke Sys Admin flag (Sys Admin only)
POST   /api/v1/users/:id/suspend          Suspend user (Sys Admin only)
POST   /api/v1/users/:id/reactivate       Reactivate suspended user (Sys Admin only)
POST   /api/v1/users/:id/deactivate       Deactivate user (Sys Admin only)
POST   /api/v1/users/:id/impersonate      Start impersonation session (Sys Admin only)
POST   /api/v1/users/impersonate/end      End impersonation session
POST   /api/v1/users/:id/transfer-ownership   Bulk transfer record ownership (Sys Admin only)
```

### 19.2 Visibility & Sharing APIs

```
PATCH  /api/v1/:entity_type/:id/visibility     Change record visibility
POST   /api/v1/:entity_type/:id/share           Create share grant
DELETE /api/v1/:entity_type/:id/share/:grant_id Revoke share grant
GET    /api/v1/:entity_type/:id/shares          List share grants for a record
POST   /api/v1/:entity_type/:id/link-share      Create link share
DELETE /api/v1/:entity_type/:id/link-share/:id  Revoke link share
GET    /api/v1/:entity_type/:id/link-shares     List link shares for a record
```

### 19.3 External Sharing APIs

```
POST   /api/v1/external-contacts            Create external contact
GET    /api/v1/external-contacts             List external contacts
PATCH  /api/v1/external-contacts/:id         Update external contact
DELETE /api/v1/external-contacts/:id         Disable external contact

# External Portal APIs (authenticated by external contact)
GET    /api/v1/portal/shared                 List records shared with me
GET    /api/v1/portal/shared/:token          Access link-shared record
GET    /api/v1/portal/:entity_type/:id       View shared record details
```

### 19.4 Settings APIs

```
GET    /api/v1/settings/permissions          Get tenant permission settings
PATCH  /api/v1/settings/permissions          Update tenant permission settings (Sys Admin only)
GET    /api/v1/settings/user/visibility      Get user's personal default visibility
PATCH  /api/v1/settings/user/visibility      Update personal default visibility
```

### 19.5 Audit APIs

```
GET    /api/v1/audit                         Query audit log (Sys Admin/Owner only)
GET    /api/v1/audit/user/:id                Audit log filtered by actor
GET    /api/v1/audit/record/:entity_type/:id Audit log filtered by record
GET    /api/v1/audit/impersonation           All impersonation sessions
```

### 19.6 Integration Management APIs

```
GET    /api/v1/integrations                  List integrations (own or tenant-level)
POST   /api/v1/integrations/personal         Connect personal integration
DELETE /api/v1/integrations/:id              Disconnect integration
POST   /api/v1/integrations/tenant           Connect tenant-level integration (Sys Admin only)
PATCH  /api/v1/integrations/:id/status       Pause/resume integration
```

### 19.7 Discrete Permissions APIs

```
GET    /api/v1/users/:id/permissions         Get user's effective permissions
PATCH  /api/v1/users/:id/permissions/:perm   Grant/revoke discrete permission (Sys Admin only)
```

---

## 20. Phasing & Roadmap

All phases ship before the first release. Phases represent development order, not release gates.

### Phase 1: Role Tiers + Visibility + User Lifecycle

**Goal:** Core access control — roles, record visibility, system/user defaults, basic user management.

- Users table with role and status fields
- Four fixed role tiers (Owner, Admin, Member, Viewer)
- Sys Admin flag on users
- `visibility` and `owner_id` as universal fields on all entity types
- Visibility defaults cascade (system → user → explicit)
- Tenant settings for default visibility
- User settings for personal default visibility override
- Query engine security injection (visibility WHERE clauses)
- Admin fast path (no visibility filter)
- User invite, role assignment, role change
- User lifecycle states (Active, Suspended, Deactivated)
- Basic audit logging (role changes, visibility changes, authentication events)
- User management admin interface

### Phase 2: Impersonation + External Sharing + Shared Inboxes

**Goal:** Offboarding workflow, external collaboration, tenant-level integrations.

- Impersonation mode with full audit trail
- Impersonation UI (banner, session management, max duration)
- Ownership transfer (individual and bulk)
- Offboarding workflow (suspend → review → transfer → disconnect → deactivate)
- Share grants (internal user sharing)
- Record sharing UI (share panel on record detail)
- External contact registration
- External portal (read-only, authenticated)
- Link sharing with expiration and revocation
- Link share access logging
- Tenant-level integrations (shared inboxes)
- Shared inbox communication attribution (from_address + sent_by)
- Integration management UI and APIs

### Phase 3: Record-Level Sharing + Discrete Permissions

**Goal:** Fine-grained sharing, Object Creator integration, query engine optimization.

- Bulk sharing (multi-select → share)
- Share grant management (list, revoke, modify expiration)
- Visibility conflict resolution (merge to most permissive)
- Object Creator as grantable/revocable discrete permission
- Discrete permissions table and resolution logic
- External API access (API tokens for external contacts)
- Materialized share set optimization for query engine
- Comprehensive audit log viewer (admin interface with filtering, export)
- Audit log retention management and partition cleanup

### Phase 4: Field-Level Permissions

**Goal:** Granular field visibility (referenced in Custom Objects PRD §25 as future scope).

- Field-level read/write permissions per role
- Sensitive field masking in views (e.g., salary field hidden from Member role)
- Field permission inheritance (entity type defaults + per-field overrides)
- Query engine field-level filtering (SELECT clause pruning)
- Field permission UI in entity type settings

---

## 21. Cross-PRD Reconciliation

### 21.1 Custom Objects PRD Updates

| Item | Current State | Required Change |
|---|---|---|
| **Universal fields** | `id`, `tenant_id`, `created_at`, `updated_at`, `created_by`, `updated_by`, `archived_at` | **Add** `visibility` (TEXT, default from cascade) and `owner_id` (TEXT, FK → users, default = `created_by`) |
| **Object Creator permission** | Referenced as discrete permission (§6.4) | **Resolved.** This PRD defines the discrete permissions model and integration with role hierarchy (§6.5, §6.6). |
| **Field-level permissions** | Identified as Phase 4 in Custom Objects PRD §25 | **Confirmed.** Phase 4 of this PRD aligns. |
| **User object type** | `usr_` prefix registered in §6.3 | **Resolved.** Users table defined here (§18.1) with the `usr_` prefix. |

### 21.2 Data Sources PRD Updates

| Item | Current State | Required Change |
|---|---|---|
| **Row-level security** | §20.2 states queries execute in user's security context | **Resolved.** This PRD defines the security context (§14.1) and WHERE clause injection (§14.2). |
| **Shared data source visibility** | §20.1 defines owner/viewer model | **Aligned.** This PRD extends to private/shared/public consistent model (§15.1). Viewer behavior unchanged. |

### 21.3 Views & Grid PRD Updates

| Item | Current State | Required Change |
|---|---|---|
| **Shared view permissions** | §17.4 defines fork-on-write, personal overrides | **No change needed.** This PRD confirms the behavior and adds the visibility model (§15). |
| **View owner** | View data model includes `Owner` attribute | **Aligned.** Owner can change visibility. Fork-on-write behavior confirmed. |

### 21.4 Contact Management PRD Updates

| Item | Current State | Required Change |
|---|---|---|
| **Contact ownership model** | Open Question #1: "Should contacts be owned by individual users, shared across the team, or both?" | **Resolved.** Contacts use the universal visibility model. Each contact has `owner_id` and `visibility`. No separate ownership model needed. |
| **RBAC roles** | §19.1 references Owner, Admin, Member, Viewer | **Resolved.** Formalized in this PRD (§6). |

### 21.5 Communication PRD Updates

| Item | Current State | Required Change |
|---|---|---|
| **Conversation access** | No explicit access model defined | **Resolved.** Conversations use universal visibility model. Shared inbox conversations default to public (§8.6). |
| **Alert permissions** | §18 defines alert system | **Clarification:** Alerts execute within the creating user's security context. Alert results are filtered by the user's visibility. |

---

## 22. Dependencies & Related PRDs

| PRD | Relationship | Dependency Direction |
|---|---|---|
| **Custom Objects PRD** | This PRD adds `visibility` and `owner_id` to the universal field set. Object Creator permission is formalized here. Field-level permissions (Phase 4) are scoped here. | **Bidirectional.** Custom Objects defines the entity model; this PRD adds access control fields and permissions. |
| **Data Sources PRD** | This PRD defines the security context and row-level security that the query engine implements. Shared data source visibility model is confirmed. | **Data Sources depend on Permissions** for query engine security injection. |
| **Views & Grid PRD** | This PRD confirms shared view behavior and adds the consistent visibility model. | **Views depend on Permissions** for shared view access control. |
| **Contact Management PRD** | This PRD resolves the contact ownership model (Open Question #1). | **Contact Management depends on Permissions** for contact visibility rules. |
| **Communication PRD** | This PRD defines conversation access rules, shared inbox permissions, and alert execution context. | **Communication depends on Permissions** for conversation access control. |
| **Events PRD** | Calendar events follow the same universal visibility model. Shared calendar events from shared inboxes default to public. | **Events depend on Permissions** for event access control. |

---

## 23. Open Questions

1. **Owner role transfer ceremony** — What happens if the Owner wants to leave the tenant? Should there be a formal "transfer ownership" flow with confirmation, or can the Owner simply reassign the role and immediately lose billing access?

2. **Viewer + Object Creator** — Should Viewers ever be grantable the Object Creator permission? Creating entity types is a schema-level action that doesn't modify records — it could be argued that it fits within a Viewer's "read + organize" mandate. Current design: no, Viewers cannot receive Object Creator.

3. **Shared inbox assignment rules** — When a message arrives at a shared inbox, how is it assigned to a specific user? Round-robin, manual claim, rule-based routing? This is operational workflow, not permissions, but the permissions model needs to support whatever assignment model is chosen. Deferred to Communication PRD or a future Workflow Automation PRD.

4. **External contact deduplication** — If an external contact is shared with from multiple tenants, do they have separate accounts per tenant or a unified identity? Current design: separate per tenant (simplest, preserves tenant isolation).

5. **Audit log access for non-admins** — Should Members/Viewers be able to see audit events for their own records (e.g., "who viewed my contact")? Or is audit access strictly Sys Admin/Owner? Current design: Sys Admin/Owner only.

6. **Visibility inheritance for child records** — When a Conversation is public but a Communication within it is private, does the Communication appear in the Conversation's timeline for other users? Current design: no, each record is independently filtered. This may create confusing gaps in conversation timelines.

7. **Bulk visibility change** — Should there be a bulk "make all my private contacts public" action? Useful for onboarding or departing users. If so, what safeguards prevent accidental mass visibility changes?

8. **Rate limiting on link shares** — Should there be a per-tenant or per-user limit on the number of active link shares? Prevents abuse and accidental over-sharing. No limit currently defined.

9. **External portal customization** — Should tenants be able to brand the external portal (logo, colors, custom domain)? Nice-to-have but impacts the external sharing experience. Deferred to post-v1.

10. **Shared record editing** — v1 is view-only for shared records. Future versions may support `edit` access level on share grants. What guardrails would be needed? Conflict resolution? Locking?

---

## 24. Glossary

General platform terms (Entity Bar, Detail Panel, Card-Based Architecture, Attribute Card, etc.) are defined in the **[Master Glossary V3](glossary_V3.md)**. The following terms are specific to this subsystem:

| Term | Definition |
|---|---|
| **Tenant** | Top-level organizational unit, equivalent to a workspace. One PostgreSQL schema per tenant. |
| **Role** | Fixed access tier: Owner, Admin, Member, Viewer. One per user, applied globally. |
| **Sys Admin** | Additive flag granting user management and system settings access. Independent of role. |
| **Visibility** | Record attribute: `private`, `shared`, or `public`. Determines discoverability. |
| **Share Grant** | Explicit view-only access grant from record owner to specific user or external contact. |
| **Link Share** | URL-based access mechanism with expiration. No authentication required. |
| **External Contact** | Non-tenant person with portal/API access to explicitly shared records. |
| **Impersonation** | Sys Admin capability to operate in another user's security context. Fully audited. |
| **Security Context** | The user identity, role, flags, and visibility filters applied to every query. |
| **Fork-on-Write** | Modifying a shared view/data source creates a personal copy without affecting the shared original. |
| **Object Creator** | Discrete permission allowing custom entity type creation. Grantable/revocable per user. |
| **Offboarding** | The process of suspending, reviewing, transferring, and deactivating a departing user. |
| **Defaults Cascade** | The resolution order for record visibility: explicit choice → user default → system default → platform default (private). |
| **Hard Delete** | Permanent, irreversible record removal. Limited to regulatory compliance and unconfirmed inferred data. |
| **Soft Delete** | Archive: record marked with `archived_at` timestamp, excluded from queries, recoverable. |
| **Dual Attribution** | Impersonation audit pattern recording both the acting Sys Admin and the target user on every action. |
| **Shared Inbox** | Tenant-level email integration (e.g., sales@, support@) with public visibility for all communications. |
| **Personal Integration** | User-owned connected account (email, phone, LinkedIn). Credentials accessible only to the user. |
| **Tenant-Level Integration** | Organization-owned connected account. Managed by Sys Admins. Communications default to public. |

---

*This document is a living specification. As implementation progresses, sections will be updated to reflect design decisions, scope adjustments, and lessons learned. The phasing roadmap will be synchronized with other PRDs to ensure dependencies are resolved in the correct order.*
