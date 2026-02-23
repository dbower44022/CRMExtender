# System Administration — Functional Area PRD

**Version:** 1.0
**Last Updated:** 2026-02-23
**Status:** Draft
**Product PRD:** [PRD.md]
**Master Glossary:** [glossary.md]

> **V1.0 (2026-02-23):** Initial draft. Establishes scope, capabilities, configuration, key processes, and action catalog for system administration.

---

## 1. Scope & Boundaries

### 1.1 Purpose

System Administration governs the setup, configuration, and ongoing health of a CRMExtender deployment. It is the functional area that ensures the system is properly configured for its users, connected to external data sources, operating within its defined parameters, and compliant with data governance requirements.

This PRD does not define the data models for Users, Customers, or Provider Accounts — those are entities with their own definitions. This PRD defines the administrative actions performed on those entities and the system-level capabilities that don't belong to any single entity.

### 1.2 Actors

| Actor | Role | Access Level |
|---|---|---|
| System Admin | Manages the deployment: users, tenants, provider accounts, settings, data operations | `admin` role |
| End User | Manages their own settings and connected accounts | `user` role, own-data scope |
| System | Automated processes: sync scheduling, session cleanup, score recomputation, health checks | Internal |

### 1.3 Boundaries

**In scope:**
- User lifecycle management (invite, activate, suspend, deactivate, role assignment)
- Provider account management (connect, configure, pause, reauth, disconnect Google accounts)
- Settings management (system settings, user setting overrides, the 4-level cascade)
- Data operations (backup, restore, GDPR/CCPA data purge, schema migration execution)
- System health monitoring (sync status, error rates, queue health, database metrics)
- Onboarding workflows (first-run setup, initial account connection)

**Out of scope (owned by other PRDs):**
- User entity data model, fields, relationships — See User Entity Base PRD (to be created)
- Customer/Tenant entity data model — See Customer Entity Base PRD (to be created)
- Provider Account entity data model — See [data-sources-prd.md]
- Access control rules and visibility scoping — See [permissions-sharing-prd.md]
- Authentication mechanisms (bcrypt, OAuth flows) — See [user-management-prd.md] Section 6

### 1.4 Related Documents

| Document | Relationship |
|---|---|
| user-management-prd.md | Predecessor document. Contains auth, roles, settings, and data model content that will be decomposed into entity PRDs and this functional area PRD. |
| permissions-sharing-prd.md | Defines the access control model that admin actions must respect. |
| data-sources-prd.md | Defines provider account abstraction and query layer. |
| technical-architecture-prd.md | Documents the as-built system including auth, sessions, settings cascade, CLI commands. |
| product-tdd.md | Platform-level technical decisions governing implementation. |

---

## 2. Capabilities

### 2.1 User Lifecycle Management

Admins create, invite, and manage user accounts within a tenant. Users progress through a lifecycle (invited → active → suspended → deactivated) with role-based permissions. Admins can change roles, reset credentials, and view user activity. End users can update their own profile and preferences.

### 2.2 Provider Account Management

Users connect external data sources (currently Google Workspace accounts) to enable email, calendar, and contact sync. Each provider account has its own OAuth tokens, sync state, and configuration. Admins can view all connected accounts across users. Users manage their own accounts — connecting, pausing, reauthorizing when tokens expire, and disconnecting.

### 2.3 Settings Management

The system provides a 4-level settings cascade (User → System → Setting Default → Hardcoded Fallback) that governs behavior across the application. Admins manage system-level settings. Users manage their own user-level overrides. New settings are registered with metadata defining their type, default, scope, and validation rules.

### 2.4 Data Operations

Operational actions for maintaining the database and ensuring data governance compliance. Includes: manual backup creation, backup restoration, GDPR/CCPA data subject access requests (export + purge), and schema migration execution. These are high-consequence operations with confirmation requirements and audit logging.

### 2.5 System Health Monitoring

Dashboard and alerting for operational health. Includes: sync status per provider account (last sync time, history cursor position, error count), database metrics (size, table counts, index health), background job status (enrichment, score recomputation), and error rate monitoring.

---

## 3. Configuration

### 3.1 Configuration Table

| Setting | Description | Type | Default | Scope | Editable By |
|---|---|---|---|---|---|
| timezone | Display timezone for dates and times | string | UTC | user | user (own), admin (any) |
| email_history_window | How far back to sync email on initial account connection | select | 90d | user | user, admin |
| sync_enabled | Global sync enable/disable | boolean | true | system | admin |
| default_phone_country | Default country code for phone number parsing | string | US | system | admin |
| company_name | Tenant company name, displayed in UI header | string | — | system | admin |
| allow_self_registration | Whether new users can register without an admin invite | boolean | false | system | admin |
| session_ttl_hours | How long login sessions last before requiring re-authentication | integer | 720 | system | admin |
| max_upload_size_mb | Maximum file upload size | integer | 10 | system | admin |
| auth_enabled | Whether authentication is enforced (disable for development only) | boolean | true | system | admin |

**Scope values:**
- `system` — One value for the entire tenant. Set by admin.
- `user` — Per-user override. Set by the user for themselves, or by admin for any user.

**Editable By values:**
- `admin` — Only users with the `admin` role.
- `user` — Any authenticated user (for their own settings only).

### 3.2 Configuration Rules

- `email_history_window` valid values: `30d`, `90d`, `180d`, `365d`, `730d`, `all`. Larger windows increase initial sync time and storage.
- `auth_enabled=false` is a development-only setting. If set, the system auto-logs in as the first active user. This setting should never be false in a multi-user deployment.
- `session_ttl_hours` minimum value: 1. Maximum: 8760 (1 year).
- Changing `default_phone_country` does not retroactively re-normalize existing phone numbers. It only affects new entries.
- Changing `timezone` affects display only — stored timestamps remain in UTC/ISO 8601.

---

## 4. Key Processes

### KP-ADMIN-01: Onboard First User (Initial Setup)

**Trigger:** First launch of a new CRMExtender deployment
**Actor:** System Admin

**Steps:**
1. System detects no users exist and presents the initial setup screen.
2. Admin creates the first user account (username, email, password) with `admin` role.
3. System creates the default customer/tenant record (`cust-default`).
4. Admin is prompted to connect a Google Workspace account.
5. System initiates OAuth flow for Gmail, Calendar, and Contacts scopes.
6. On successful authorization, system creates a provider account and begins initial sync.
7. Admin is shown the sync progress indicator and can proceed to the main application.
8. Initial sync completes in the background. Contacts, conversations, and events populate.

**Outcome:** A functional single-user deployment with one connected Google account and initial data synced.

### KP-ADMIN-02: Invite and Onboard Additional User

**Trigger:** Admin decides to add a user to the system
**Actor:** System Admin

**Steps:**
1. Admin navigates to User Management and clicks "Invite User."
2. Admin enters the new user's email address and assigns a role (`admin` or `user`).
3. System creates a user record with status `invited` and sends an invitation email (or displays a registration link if email is not configured).
4. New user follows the invitation link and sets their password (or authenticates via Google OAuth).
5. User status transitions from `invited` to `active`.
6. User is prompted to connect their Google Workspace account.
7. System initiates OAuth flow and creates a provider account.
8. User's data begins syncing. Visibility rules determine which contacts and conversations they can see.

**Outcome:** New user is active with their own provider account, seeing data appropriate to their access level.

### KP-ADMIN-03: Connect Google Account

**Trigger:** User wants to add a Google Workspace account for sync
**Actor:** End User or System Admin

**Steps:**
1. User navigates to Settings → Connected Accounts and clicks "Add Google Account."
2. System initiates Google OAuth 2.0 flow requesting `gmail.readonly`, `contacts.readonly`, `calendar.readonly` scopes.
3. User authorizes in the Google consent screen.
4. System receives OAuth tokens and stores them as a provider account linked to the user.
5. System begins initial sync: contacts first, then email threads (per `email_history_window` setting), then calendar events.
6. Sync progress is displayed. User can continue using the application while sync runs in the background.
7. After initial sync completes, incremental sync activates (Gmail History API, Calendar sync tokens).

**Outcome:** Provider account is connected and actively syncing. New data flows in automatically.

### KP-ADMIN-04: Reauthorize Expired Google Account

**Trigger:** Google OAuth token refresh fails (user revoked access, token expired, scope changed)
**Actor:** End User or System Admin

**Steps:**
1. System detects token refresh failure during sync attempt.
2. Provider account status changes to `needs_reauth`.
3. User sees a notification in the UI indicating the account needs reauthorization.
4. User clicks the reauthorization prompt, triggering a new OAuth flow.
5. System replaces the stored tokens with fresh ones.
6. Provider account status returns to `active`. Sync resumes from where it left off (history cursor preserved).

**Outcome:** Provider account is reconnected and syncing resumes without data loss.

### KP-ADMIN-05: Execute GDPR Data Purge

**Trigger:** Data subject requests deletion of their personal data
**Actor:** System Admin

**Steps:**
1. Admin navigates to Data Operations → GDPR Requests.
2. Admin searches for the contact to be purged by name or email.
3. System displays all data associated with the contact: profile, identifiers, communications (as participant), conversations, relationships, intelligence items, enrichment data.
4. Admin reviews the data scope and confirms the purge request with a justification note.
5. System generates a data export (JSON) for the admin's records before deletion.
6. System executes the purge:
   a. Deletes all events from the event store for this contact.
   b. Deletes the contact record and all sub-entities (identifiers, employment, addresses, phones, emails, social profiles).
   c. Anonymizes communication participant references (replaces contact_id with NULL, preserves email address for thread integrity).
   d. Removes intelligence items and enrichment data.
   e. Removes relationship graph edges.
7. System writes an audit record of the deletion (without PII) including the admin, timestamp, and justification.

**Outcome:** All personal data for the data subject is purged. Communications remain intact but de-identified. Audit trail preserved.

### KP-ADMIN-06: Manage System Settings

**Trigger:** Admin needs to change a system-level configuration value
**Actor:** System Admin

**Steps:**
1. Admin navigates to Settings → System Settings.
2. System displays all system-scoped settings with their current values, defaults, and descriptions.
3. Admin modifies one or more settings.
4. System validates each change against the setting's type and constraints.
5. On save, system applies changes immediately (no restart required).
6. System logs the setting change in the audit trail (who, when, old value, new value).

**Outcome:** System behavior is updated. Changes take effect immediately for all users.

---

## 5. Action Catalog

### 5.1 Simple Actions

#### Create User

**Trigger:** Admin clicks "Create User" or "Invite User"
**Inputs:** Email address, role (`admin` | `user`), optional: first name, last name
**Outcome:** User record created with status `invited` (if invite flow) or `active` (if direct creation)
**Business Rules:** Email must be unique within the tenant. At least one admin must always exist — the system prevents demoting or deactivating the last admin.
**Supports processes:** KP-ADMIN-02

#### Change User Role

**Trigger:** Admin selects a user and changes their role
**Inputs:** User ID, new role
**Outcome:** User's role is updated. Access control changes take effect on next request.
**Business Rules:** Cannot demote the last admin. Cannot change own role (prevents accidental lockout).
**Supports processes:** KP-ADMIN-02

#### Suspend User

**Trigger:** Admin suspends a user account
**Inputs:** User ID
**Outcome:** User status changes to `suspended`. Active sessions are invalidated. User cannot log in. Data is preserved. Provider accounts are paused.
**Business Rules:** Cannot suspend the last admin. Suspended users' data remains visible to other users per normal visibility rules.
**Supports processes:** —

#### Reactivate User

**Trigger:** Admin reactivates a suspended user
**Inputs:** User ID
**Outcome:** User status changes to `active`. User can log in. Provider accounts resume sync.
**Business Rules:** None.
**Supports processes:** —

#### Deactivate User

**Trigger:** Admin permanently deactivates a user account
**Inputs:** User ID, reassignment target (optional — who inherits the user's data)
**Outcome:** User status changes to `deactivated`. Sessions invalidated. Provider accounts disconnected and tokens deleted. Data optionally reassigned to another user.
**Business Rules:** Cannot deactivate the last admin. Deactivation is permanent — reactivation creates audit complexity and is not supported. If data reassignment is not specified, the deactivated user's data remains visible per normal visibility rules but is unowned.
**Supports processes:** —

#### Pause Provider Account Sync

**Trigger:** User or admin pauses sync on a connected account
**Inputs:** Provider account ID
**Outcome:** Sync is suspended. No new data is fetched. Existing data is preserved. History cursor is preserved so sync can resume without re-fetching.
**Business Rules:** Any user can pause their own accounts. Admins can pause any account.
**Supports processes:** KP-ADMIN-03

#### Resume Provider Account Sync

**Trigger:** User or admin resumes sync on a paused account
**Inputs:** Provider account ID
**Outcome:** Sync resumes from the saved history cursor. Incremental sync picks up where it left off.
**Business Rules:** Same permission model as pause.
**Supports processes:** KP-ADMIN-03

#### Disconnect Provider Account

**Trigger:** User or admin disconnects a Google account
**Inputs:** Provider account ID, confirmation
**Outcome:** OAuth tokens are deleted. Provider account status changes to `disconnected`. No new data is synced. Existing synced data is preserved (conversations, contacts, events remain in the system).
**Business Rules:** Requires confirmation dialog. Any user can disconnect their own accounts. Admins can disconnect any account.
**Supports processes:** KP-ADMIN-03

#### Update System Setting

**Trigger:** Admin changes a system-level setting
**Inputs:** Setting key, new value
**Outcome:** Setting value is stored. Change takes effect immediately.
**Business Rules:** Value must pass type validation and constraint checks. Change is audit-logged.
**Supports processes:** KP-ADMIN-06

#### Update User Setting

**Trigger:** User changes one of their own settings, or admin changes a setting for a specific user
**Inputs:** Setting key, new value, user ID (if admin changing for another user)
**Outcome:** User-level override is stored. Overrides the system-level default for that user.
**Business Rules:** Users can only change settings with `user` scope for themselves. Admins can change any user's settings.
**Supports processes:** KP-ADMIN-06

#### Create Manual Backup

**Trigger:** Admin initiates a manual database backup
**Inputs:** Optional: backup label/description
**Outcome:** SQLite database file is copied to the backups directory with timestamp and label. Backup is registered in the system.
**Business Rules:** Backup is performed with WAL checkpoint to ensure consistency. Backup directory must have sufficient disk space.
**Supports processes:** —

#### Clean Up Expired Sessions

**Trigger:** Admin runs cleanup manually, or system runs on schedule
**Inputs:** None
**Outcome:** Session records past their TTL are deleted from the sessions table.
**Business Rules:** Does not affect currently active sessions whose TTL has not expired.
**Supports processes:** —

### 5.2 Complex Actions (Sub-PRDs)

| Action | Sub-PRD | Description |
|---|---|---|
| GDPR/CCPA Data Purge | admin-gdpr-purge-prd (to be created) | Full data subject deletion with export, anonymization, and audit trail. Multi-step workflow with confirmation gates. |
| Schema Migration Execution | admin-migration-prd (to be created) | Running schema migrations with backup, validation, dry-run, and rollback. High-consequence operation. |
| Bulk Data Import | See [contact-import-export-prd.md] | CSV and vCard import are admin-initiated but owned by the Contact entity's import/export sub-PRD. |

---

## 6. Cross-Cutting Concerns

### 6.1 Audit & Logging

All administrative actions are audit-logged with: the acting user, timestamp, action type, target entity (if applicable), old value, new value, and IP address. Audit logs are append-only and cannot be modified or deleted by any user, including admins.

Audit-logged actions include: user creation/modification/suspension/deactivation, role changes, setting changes, provider account connections/disconnections, backup creation, data purge execution, migration execution.

### 6.2 Permissions & Access Control

| Action Category | Admin | User |
|---|---|---|
| User lifecycle (create, suspend, deactivate) | ✓ | ✗ |
| Change user role | ✓ | ✗ |
| System settings | ✓ | ✗ |
| User settings (own) | ✓ | ✓ |
| User settings (others) | ✓ | ✗ |
| Provider accounts (own) | ✓ | ✓ |
| Provider accounts (others) | ✓ | ✗ |
| Data operations (backup, purge, migrate) | ✓ | ✗ |
| System health monitoring | ✓ | ✗ |

### 6.3 Error Handling

Administrative actions that fail should never leave the system in an inconsistent state. Specific patterns:

- **User lifecycle changes** — Wrapped in database transactions. If session invalidation fails after suspension, the suspension is rolled back.
- **Provider account operations** — OAuth failures during connect/reauth display clear error messages with troubleshooting steps (check Google account permissions, verify scopes, try again).
- **Data purge** — Executed in a single database transaction. If any step fails, the entire purge is rolled back. The export file is generated before the transaction begins.
- **Setting changes** — Validated before save. Invalid values are rejected with specific error messages. The previous value is preserved.

---

## 7. Task List

```
- [ ] ADMIN-01: User list view showing all users with status, role, last login, connected accounts count
- [ ] ADMIN-02: Create/invite user form with role assignment
- [ ] ADMIN-03: User detail view with profile, role, status, connected accounts, activity log
- [ ] ADMIN-04: Suspend/reactivate/deactivate user actions with confirmation dialogs
- [ ] ADMIN-05: Change user role action with last-admin protection
- [ ] ADMIN-06: Provider accounts list view (per-user and admin global view)
- [ ] ADMIN-07: Connect Google account flow with OAuth and sync initiation
- [ ] ADMIN-08: Pause/resume/disconnect provider account actions
- [ ] ADMIN-09: Reauthorization notification and flow for expired tokens
- [ ] ADMIN-10: System settings page with all settings, current values, descriptions
- [ ] ADMIN-11: User settings page (own settings with override indicators)
- [ ] ADMIN-12: Admin override of user settings
- [ ] ADMIN-13: Settings audit trail view
- [ ] ADMIN-14: Manual backup creation from admin UI
- [ ] ADMIN-15: System health dashboard (sync status per account, database metrics, error rates)
- [ ] ADMIN-16: Session cleanup (manual trigger + scheduled)
- [ ] ADMIN-17: Audit log viewer with filtering by action type, user, date range
```

---

## 8. Test Plan

| Test ID | Description | Type | Covers |
|---|---|---|---|
| ADMIN-T01 | Create user with valid email and role, verify record created with correct status | Unit | ADMIN-01, ADMIN-02 |
| ADMIN-T02 | Attempt to create user with duplicate email, verify rejection | Unit | ADMIN-02 |
| ADMIN-T03 | Suspend user, verify sessions invalidated and login blocked | Integration | ADMIN-04 |
| ADMIN-T04 | Attempt to suspend last admin, verify rejection | Unit | ADMIN-04 |
| ADMIN-T05 | Attempt to demote last admin, verify rejection | Unit | ADMIN-05 |
| ADMIN-T06 | Connect Google account via OAuth, verify provider account created and sync starts | Integration | ADMIN-07 |
| ADMIN-T07 | Pause sync, verify no new data fetched, resume and verify sync continues from cursor | Integration | ADMIN-08 |
| ADMIN-T08 | Disconnect account, verify tokens deleted and data preserved | Integration | ADMIN-08 |
| ADMIN-T09 | Simulate token expiry, verify reauth notification appears and flow works | Integration | ADMIN-09 |
| ADMIN-T10 | Update system setting, verify new value takes effect immediately | Unit | ADMIN-10 |
| ADMIN-T11 | Update system setting with invalid value, verify rejection | Unit | ADMIN-10 |
| ADMIN-T12 | Set user-level override, verify it takes precedence over system setting | Unit | ADMIN-11 |
| ADMIN-T13 | Verify 4-level cascade: user → system → default → hardcoded | Unit | ADMIN-11 |
| ADMIN-T14 | Create manual backup, verify file created and registered | Integration | ADMIN-14 |
| ADMIN-T15 | Verify all admin actions produce audit log entries | Integration | ADMIN-17 |
| ADMIN-T16 | Verify non-admin users cannot access admin-only actions | Unit | Cross-cutting |
| ADMIN-T17 | Verify users can manage own provider accounts but not others' | Unit | Cross-cutting |
