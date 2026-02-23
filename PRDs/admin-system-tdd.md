# System Administration — TDD

**Version:** 1.0
**Last Updated:** 2026-02-23
**Status:** Draft
**Scope:** Functional Area
**Parent Document:** [admin-system-prd.md]
**Product TDD:** [product-tdd.md]

---

## 1. Overview

This document captures technical decisions specific to the System Administration functional area that extend or deviate from the Product TDD defaults. It covers the settings cascade engine, authentication and session model, user lifecycle management, provider account management, the dual API surface, calendar sync configuration, contact-company roles, and the React settings UI architecture.

System Administration spans multiple entities (users, provider accounts, settings, sessions) and multiple UI surfaces (HTMX settings pages, React settings tab, JSON API). The decisions here govern the cross-cutting patterns for managing these entities rather than the entity data models themselves.

This is a living document. Decisions are recorded as they are made — both by the product/architecture owner and by Claude Code during implementation. When Claude Code makes an implementation decision not covered here, it should add the decision with rationale to the appropriate section.

---

## 2. Settings Cascade Engine

### 2.1 4-Level Resolution Cascade

**Decision:** Settings resolve through a 4-level cascade: (1) user-specific value → (2) system setting value → (3) setting default column → (4) hardcoded fallback dictionary. Resolution is implemented in `poc/settings.py:get_setting()`.

**Rationale:** The 4-level cascade enables per-user customization (timezone, date format) with system-wide defaults (company name, phone country) while guaranteeing that every setting always returns a value. The `setting_default` column on the settings table allows administrators to declare defaults without code changes, while the hardcoded dictionary ensures the system functions even with an empty database.

**Alternatives Rejected:**

- Single-level key-value store — No per-user overrides, forcing all users to share the same configuration.
- JSON configuration file — No runtime editability, no per-user scope, requires server restart.
- Separate tables for system vs. user settings — Duplicates schema and CRUD logic for the same conceptual data.

**Constraints/Tradeoffs:** The cascade is evaluated on every `get_setting()` call with up to 3 database queries (user row, system row, user default fallback). For hot-path settings, callers should cache the resolved value within a request lifecycle rather than calling `get_setting()` repeatedly.

### 2.2 Key-Value Storage in settings Table

**Decision:** All settings are stored in a single `settings` table with columns: `id, customer_id, user_id, scope, setting_name, setting_value, setting_description, setting_default, created_at, updated_at`. The `scope` column is CHECK-constrained to `'system'` or `'user'`.

**Rationale:** A single table with a scope discriminator provides one CRUD layer for both system and user settings. System settings have `user_id = NULL` and `scope = 'system'`. User settings have a non-null `user_id` and `scope = 'user'`. This means the same `set_setting()` function handles both scopes with a scope parameter.

**Alternatives Rejected:**

- Typed columns per setting (one column per setting on a user/customer table) — Schema changes for every new setting, cannot add settings at runtime.
- EAV with type coercion — Over-engineering for ~10 settings. All values stored as TEXT is sufficient; callers handle type interpretation.

**Constraints/Tradeoffs:** All values are stored as TEXT strings. Boolean settings store `"true"/"false"`, integers store their string representation. Callers must parse values to the appropriate type. No type validation is enforced at the storage layer.

### 2.3 Upsert Semantics for set_setting()

**Decision:** `set_setting()` implements manual upsert: it first queries for an existing row (by customer_id + scope + setting_name + optional user_id), then executes UPDATE if found or INSERT if not. New rows receive a UUID v4 identifier.

**Rationale:** Manual upsert was chosen over SQL `ON CONFLICT` because the unique key for system vs. user settings differs (system keys by customer_id + scope + name; user keys add user_id). A single `ON CONFLICT` clause cannot express both uniqueness models cleanly in SQLite.

**Alternatives Rejected:**

- `INSERT OR REPLACE` — Deletes and re-inserts, losing the original `created_at` timestamp and triggering FK cascade actions.
- `ON CONFLICT DO UPDATE` — Would require a composite unique index that handles the NULL user_id case, which SQLite treats as always-distinct (see SQLite pitfall in MEMORY.md).

**Constraints/Tradeoffs:** Two queries per write (SELECT + INSERT/UPDATE) within a single connection context manager. Acceptable for settings writes, which are infrequent (~1/minute at peak).

### 2.4 Hardcoded Fallback Dictionary

**Decision:** `_HARDCODED_DEFAULTS` in `poc/settings.py` provides last-resort values for known settings: `default_timezone`, `company_name`, `sync_enabled`, `timezone`, `start_of_week`, `date_format`, `default_phone_country`, `allow_self_registration`, `email_history_window`.

**Rationale:** The hardcoded dictionary ensures the application can start and function correctly even with a completely empty settings table (fresh install, test fixtures). Without it, `get_setting()` would return `None` for unconfigured settings, forcing every caller to handle the null case.

**Constraints/Tradeoffs:** Adding a new setting requires updating both the hardcoded dictionary and the `seed_default_settings()` function. If they diverge, the cascade produces different values depending on whether seed has run. This is acceptable because both are in the same file and reviewed together.

---

## 3. Authentication & Session Model

### 3.1 Dual Authentication: bcrypt + Google OAuth 2.0

**Decision:** Two authentication methods coexist: password-based login (bcrypt hash stored in `users.password_hash`) and Google OAuth 2.0 code flow (Google subject ID stored in `users.google_sub`). A user can have either or both authentication methods enabled.

**Rationale:** Password auth provides a standalone login path for environments without Google Workspace. Google OAuth enables SSO and is required because the same OAuth flow is used to authorize Gmail/Calendar/Contacts API access. Supporting both means users can log in via password even if their Google token expires.

**Alternatives Rejected:**

- OAuth-only — Locks out users without Google accounts and prevents standalone deployments.
- Password-only — Requires a separate OAuth flow just for provider account connection, duplicating the Google consent screen experience.

**Constraints/Tradeoffs:** The auto-link behavior on first Google login (`set_google_sub()` called when email matches an existing user) means a user cannot unlink their Google account without a database edit. This is acceptable for the current single-tenant deployment.

### 3.2 Server-Side Sessions with Cookie Transport

**Decision:** Sessions are stored in the `sessions` database table with columns: `id, user_id, customer_id, created_at, expires_at, ip_address, user_agent`. The session ID is transmitted via an HTTP-only `crm_session` cookie. Default TTL: 720 hours (30 days).

**Rationale:** Server-side sessions enable server-controlled revocation (deactivate user → delete their sessions). HTTP-only cookies prevent XSS-based session theft. The 30-day TTL balances security with user convenience for a CRM that users access daily.

**Alternatives Rejected:**

- JWT tokens — Cannot be revoked server-side without a blocklist, which reintroduces server-side state. JWTs also leak user data in the payload.
- Redis-backed sessions — Adds an infrastructure dependency for a single-tenant SQLite deployment.

**Constraints/Tradeoffs:** Every authenticated request queries the sessions table (JOIN to users for role/active status). For the current ~1 concurrent user, this is negligible. At scale, session caching or a dedicated session store would be needed.

### 3.3 Session Validation with Lazy Expiry Cleanup

**Decision:** `get_session()` validates sessions by: (1) looking up the session row with a JOIN to users, (2) checking `expires_at` against current UTC time, (3) checking `user.is_active`. Expired sessions are deleted on access (lazy cleanup). A separate `cleanup_expired_sessions()` function provides batch cleanup.

**Rationale:** Lazy cleanup on read means no background scheduler is needed. When a session is accessed after expiry, it's deleted immediately. The batch cleanup function exists for administrative housekeeping but is not required for correctness.

**Alternatives Rejected:**

- Background cron job for session cleanup — Adds operational complexity. Lazy cleanup handles the common case (user returns after expiry).
- Session renewal on access (sliding window) — Would extend sessions indefinitely for active users, which is a security concern if a session cookie is compromised.

**Constraints/Tradeoffs:** Expired sessions accumulate in the database until accessed or manually cleaned. With ~1 user creating ~1 session per month, this produces negligible table growth.

### 3.4 Auth Bypass Mode for Development

**Decision:** When `CRM_AUTH_ENABLED=false` (environment variable), the `AuthMiddleware._bypass_mode()` method injects the first active user from the database into `request.state.user` without requiring login. If no users exist (empty database), a synthetic admin (`id='synthetic-admin'`, `email='admin@localhost'`) is injected.

**Rationale:** Bypass mode eliminates login friction during development and enables the test suite to run without authentication setup. The synthetic admin fallback ensures the middleware never produces a null user in bypass mode, which would crash downstream route handlers.

**Alternatives Rejected:**

- Test-only middleware replacement — Would diverge the test and production code paths, potentially missing auth bugs.
- Environment-based auto-login with a specific test user — More complex and requires the test user to exist in the database.

**Constraints/Tradeoffs:** Bypass mode is a security risk if accidentally enabled in production. The PRD notes this explicitly. The setting is environment-variable-controlled (not database-stored) so it cannot be toggled at runtime.

### 3.5 Middleware Response Dispatch: 401 JSON vs. 302 Redirect

**Decision:** The `AuthMiddleware` returns different responses for unauthenticated requests based on the URL path: `/api/*` paths receive a `401 JSON {"error": "Authentication required"}` response; all other paths receive a `302 redirect to /login`.

**Rationale:** The React SPA at `/app/` fetches data via `/api/v1/*` endpoints using React Query. A 302 redirect to an HTML login page would break JSON parsing in the SPA. The 401 JSON response allows the SPA to detect the auth failure and redirect to the login page client-side (or show a re-login prompt). HTMX pages at `/` paths expect browser-native redirect behavior.

**Alternatives Rejected:**

- Unified 401 for all paths — Would break the HTMX UI, which relies on browser following the redirect.
- Separate middleware for API vs. HTML — Unnecessary complexity when a single path check in one middleware handles both.

**Constraints/Tradeoffs:** The path-based dispatch is simple but inflexible. If a non-API path ever needs JSON auth errors (e.g., HTMX endpoints returning JSON), the dispatch logic would need to check `Accept` headers instead. Currently not needed.

### 3.6 Sensitive Field Stripping

**Decision:** All API endpoints that return user or provider account objects strip sensitive fields before responding: `password_hash`, `google_sub`, `auth_token_path`, `refresh_token`. Stripping is done inline at each endpoint (dict pop/comprehension), not via a centralized serializer.

**Rationale:** Prevents accidental exposure of credentials or tokens in API responses. Inline stripping at each endpoint ensures the developer must consciously decide which fields to include rather than relying on a global filter that might not catch new sensitive fields.

**Alternatives Rejected:**

- Pydantic response models with field exclusion — Would add type-safe serialization but requires maintaining parallel model classes for every response shape. Over-engineering for the current endpoint count.
- Database-level column exclusion (SELECT only safe columns) — Brittle when JOIN shapes change. Easier to SELECT * and strip in Python.

**Constraints/Tradeoffs:** Each endpoint independently strips fields, which risks inconsistency if a new endpoint forgets. Acceptable because all settings endpoints are in a single file (`api.py`) and follow the same pattern.

---

## 4. User Lifecycle Management

### 4.1 User CRUD in poc/hierarchy.py

**Decision:** User CRUD functions (`create_user`, `update_user`, `list_users`, `get_user_by_id`, `get_user_by_email`, `get_user_by_google_sub`) are implemented in `poc/hierarchy.py` alongside project and topic CRUD.

**Rationale:** During PoC development, `hierarchy.py` became the module for all "organizational" CRUD (users, projects, topics). Separating users into a dedicated `poc/users.py` module was considered but deferred because the functions are small and co-locating them with the bootstrap flow keeps the import graph simpler.

**Constraints/Tradeoffs:** The module is growing. If user lifecycle management expands significantly (invite flow, suspension, data reassignment), a dedicated module should be extracted.

### 4.2 Two-Role Model: admin / user

**Decision:** Users have a `role` column with two values: `admin` and `user`. Role is stored directly on the users table, not in a separate roles or permissions table. Admin checks are performed inline at each API endpoint: `if request.state.user["role"] != "admin": return JSONResponse({"error": "Forbidden"}, 403)`.

**Rationale:** Two roles are sufficient for the current single-tenant deployment. A full RBAC system with permission matrices would be premature. Inline admin checks are explicit and easy to audit — searching for `"role"] != "admin"` finds every admin-gated endpoint.

**Alternatives Rejected:**

- Role-based access control with permissions table — Over-engineering for 2 roles. Would add JOINs to every request for permission checks.
- Decorator-based auth (`@require_admin`) — Cleaner but hides the auth logic. Inline checks are more visible during code review.

**Constraints/Tradeoffs:** Adding a third role (e.g., `viewer`) would require updating every inline check. At that point, a decorator or middleware-based approach should be adopted.

### 4.3 Self-Deactivation Prevention

**Decision:** The `POST /api/v1/settings/users/{user_id}/toggle-active` endpoint prevents a user from deactivating themselves by comparing `user_id` against `request.state.user["id"]`. Returns `400 {"error": "Cannot deactivate yourself"}`.

**Rationale:** Self-deactivation would lock the admin out of their own account. Since there's no recovery mechanism without database access, this is a safety guard.

**Constraints/Tradeoffs:** An admin can still change their own role to `user`, potentially losing admin access. Last-admin protection (see 4.4) mitigates this.

### 4.4 Session Invalidation on Deactivation

**Decision:** When a user is deactivated (`is_active` toggled to 0), all their sessions are immediately deleted via `delete_user_sessions(user_id)`. This is performed in the same API handler as the `update_user()` call.

**Rationale:** Deactivated users should lose access immediately, not at their next session expiry (up to 30 days later). Deleting sessions ensures the next request from any of their devices fails authentication.

**Alternatives Rejected:**

- Rely on `get_session()` active check — `get_session()` already checks `user.is_active`, but this still allows the session row to exist in the table. Explicit deletion is cleaner and provides an immediate signal.

**Constraints/Tradeoffs:** No notification is sent to the deactivated user's active sessions. Their next request simply fails with a login redirect or 401.

### 4.5 Whitelist-Based Field Updates

**Decision:** `update_user()` accepts keyword arguments but only applies fields from an explicit whitelist: `name`, `role`, `is_active`. Other fields are silently ignored.

**Rationale:** Prevents accidental or malicious modification of protected fields like `email`, `password_hash`, `google_sub`, or `customer_id` through the general update function. Password changes go through the dedicated `set_user_password()` function. Email changes are not currently supported.

**Constraints/Tradeoffs:** Silently ignoring unknown fields means typos in field names don't produce errors. Acceptable because all callers are internal API handlers, not external consumers.

---

## 5. Provider Account Management

### 5.1 OAuth Connect Flow with Cookie-Based State

**Decision:** The Google OAuth connect flow uses three cookies to manage state across the redirect: `oauth_state` (CSRF protection), `oauth_purpose` (discriminator: `"add-account"` vs. login), and `oauth_return_to` (return URL after completion, e.g., `/app/`).

**Rationale:** The OAuth flow involves a redirect to Google and back, which loses all in-memory state. Cookies survive the redirect round-trip and are scoped to the same domain. Using three single-purpose cookies is simpler than encoding a JSON payload into one cookie.

**Alternatives Rejected:**

- Server-side state in sessions table — Would require the user to already be authenticated, which doesn't work for the login flow.
- State parameter encoding (pack purpose + return URL into the OAuth state param) — State param is validated as an exact match against the cookie; packing additional data into it complicates validation.

**Constraints/Tradeoffs:** Cookies are deleted after the callback processes them. If the callback fails partway through, stale cookies may persist until they expire or the user clears them. This is cosmetic — the next flow generates fresh cookies.

### 5.2 SPA Redirect After Account Connection

**Decision:** After a successful account connection, the OAuth callback redirects to either `/app/?connected=1` (if `oauth_return_to` cookie indicates the React SPA) or `/settings/accounts?saved=1` (for the HTMX UI). The `?connected=1` / `?saved=1` query parameter triggers a success banner in the respective UI.

**Rationale:** The OAuth callback is a server-side route that must redirect the browser after completing. The return URL cookie ensures the user returns to whichever UI they started from. The query parameter is the simplest way to signal success across the redirect boundary.

**Constraints/Tradeoffs:** The query parameter persists in the URL bar. Both UIs clear it from the URL after displaying the banner (React via `window.history.replaceState`, HTMX via JavaScript).

### 5.3 Soft-Delete via is_active Flag

**Decision:** Provider accounts use `is_active INTEGER DEFAULT 1` for soft-delete. Toggling `is_active` to 0 pauses sync without deleting data or OAuth tokens. All sync queries filter `WHERE is_active = 1`.

**Rationale:** Hard-deleting a provider account would orphan all conversations, communications, and events sourced from it. Soft-delete preserves the data lineage while stopping new sync. Tokens are preserved so the account can be reactivated without re-authorization.

**Alternatives Rejected:**

- Separate `status` enum (active/paused/disconnected/revoked) — Over-engineering for the current needs. A boolean toggle covers pause/resume; disconnection (token deletion) is a separate operation not yet implemented.

**Constraints/Tradeoffs:** Inactive accounts still count in storage metrics and appear in admin views (with an inactive indicator). This is intentional — admins need visibility into paused accounts.

### 5.4 User-Scoped Visibility via Junction Table

**Decision:** The `user_provider_accounts` junction table links users to provider accounts with a `role` column (currently always `"owner"`). Account listing endpoints query this junction table to show users only their own accounts. Fallback: if no junction rows exist for a user, the endpoint returns all customer-scoped accounts.

**Rationale:** The junction table enables future multi-user account sharing (e.g., a shared mailbox) by adding rows with different roles. The fallback ensures backward compatibility with accounts created before the junction table existed (pre-Phase 3).

**Alternatives Rejected:**

- Direct `user_id` FK on provider_accounts — Would limit each account to one user, preventing shared mailbox scenarios.

**Constraints/Tradeoffs:** The fallback logic means a user with no junction rows sees all customer accounts, which is permissive. This is acceptable for single-user deployment and will be tightened when multi-user is actively used.

---

## 6. Dual API Surface

### 6.1 HTMX HTML Routes + JSON API Endpoints

**Decision:** System administration is served through two parallel API surfaces: HTMX/Jinja2 routes at `/settings/*` (in `settings_routes.py`) and JSON API endpoints at `/api/v1/settings/*` (in `api.py`). Both surfaces share the same backend CRUD functions (`poc/settings.py`, `poc/hierarchy.py`, `poc/contact_company_roles.py`).

**Rationale:** The HTMX routes were built first during PoC development and remain the primary admin UI. The JSON API endpoints were added for the React SPA settings tab. Both must coexist during the transition period because the React SPA does not yet have feature parity with the HTMX UI (e.g., the React SPA cannot initiate the OAuth connect flow directly — it redirects to the HTMX route).

**Alternatives Rejected:**

- API-first with HTMX consuming JSON — Would require HTMX to parse JSON and render client-side, losing the server-rendered simplicity that makes HTMX effective.
- React-only settings — The OAuth connect flow requires server-side redirects that the SPA cannot handle natively. A hybrid approach is necessary.

**Constraints/Tradeoffs:** Two route files contain similar endpoint logic for the same operations. This duplication is temporary and acceptable — the HTMX routes will be deprecated once the React SPA achieves feature parity.

### 6.2 JSON API Endpoint Catalog (21 endpoints)

**Decision:** The JSON API provides 21 endpoints across 6 domains:

| Domain         | Endpoints                                                                                                                              | Admin-Only                          |
| -------------- | -------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------- |
| Profile        | GET/PUT `/settings/profile`, PUT `/settings/password`                                                                                  | No                                  |
| System         | GET/PUT `/settings/system`                                                                                                             | Yes                                 |
| Users          | GET/POST `/settings/users`, PUT `/settings/users/{id}`, PUT `/settings/users/{id}/password`, POST `/settings/users/{id}/toggle-active` | Yes                                 |
| Accounts       | GET `/settings/accounts`, PUT `/settings/accounts/{id}`, POST `/settings/accounts/{id}/toggle-active`                                  | No                                  |
| Calendars      | GET `/settings/calendars`, POST `/settings/calendars/{id}/fetch`, PUT `/settings/calendars/{id}`                                       | No                                  |
| Roles          | GET/POST `/settings/roles`, PUT/DELETE `/settings/roles/{id}`                                                                          | Create/Update/Delete: Yes; List: No |
| Reference Data | GET `/settings/reference-data`                                                                                                         | No                                  |

**Rationale:** Grouping by domain rather than by HTTP method makes the API discoverable and aligns with the React settings tab structure (one tab per domain). The toggle-active pattern uses POST (not DELETE or PATCH) because it's a state transition, not a deletion or partial update.

**Constraints/Tradeoffs:** The 21 endpoints are all in a single file (`api.py`), which is large. Extracting into separate route modules (e.g., `api_settings.py`) would improve organization but adds import complexity. Deferred.

### 6.3 Admin Gating Pattern

**Decision:** Admin-only endpoints use an inline guard at the top of the handler: `if request.state.user["role"] != "admin": return JSONResponse({"error": "Forbidden"}, status_code=403)`. This pattern is repeated identically in 8 endpoints.

**Rationale:** Inline guards are explicit, grep-able, and require no framework support. Every admin-only endpoint visibly declares its access requirement in the first 2 lines.

**Alternatives Rejected:**

- FastAPI dependency injection (`Depends(require_admin)`) — Would be cleaner but requires defining a dependency function and doesn't work with the plain function handlers used in this file.
- Decorator pattern (`@admin_required`) — Hides the auth check from the function body. Inline is more visible during code review.

**Constraints/Tradeoffs:** The repeated pattern is verbose. If the role model expands beyond two roles, a centralized guard function should replace the inline checks.

---

## 7. Calendar Sync Configuration

### 7.1 Rich Calendar Entry Format with Backward Compatibility

**Decision:** Selected calendars are stored as a JSON array of objects in the settings table under the key `cal_sync_calendars_{account_id}`. The rich format stores `[{"id": "cal-id", "summary": "Calendar Name"}, ...]`. Legacy format (plain array of calendar ID strings `["cal-id-1", "cal-id-2"]`) is normalized to rich format on read.

**Rationale:** The rich format preserves the human-readable calendar name alongside the ID, so the UI can display calendar names without re-fetching from Google. Backward compatibility with the plain array format prevents data loss for settings saved before the rich format was introduced.

**Alternatives Rejected:**

- Dedicated `calendar_selections` table — Over-engineering for ~5 calendar selections per account. The settings table with JSON values is sufficient.
- Store only IDs, fetch names from Google on every page load — Would fail when Google credentials are expired, showing raw IDs instead of names.

**Constraints/Tradeoffs:** JSON stored as TEXT in SQLite means no indexed queries on calendar selections. This is acceptable because calendar settings are only read for the settings UI and sync orchestration, both of which load the full JSON.

### 7.2 Per-User Per-Account Calendar Storage

**Decision:** Calendar selections are stored as user-scoped settings: `set_setting(customer_id, f"cal_sync_calendars_{account_id}", json_value, scope="user", user_id=user_id)`. Each user independently selects which calendars to sync for each of their connected accounts.

**Rationale:** Different users may want to sync different calendars from the same Google account (if account sharing is enabled). User-scoped storage enables this. Even for single-user deployment, user-scoping is the correct default because it fits the settings cascade model.

**Constraints/Tradeoffs:** The setting key includes the account_id, creating a dynamic key pattern (`cal_sync_calendars_*`). This means `list_settings()` cannot filter by a static key name — callers must pattern-match or know the account IDs in advance.

### 7.3 Sync Token Storage

**Decision:** Calendar sync tokens are stored as user-scoped settings: `cal_sync_token_{account_id}_{calendar_id}`. If a sync token expires (Google returns 410 Gone), the system falls back to a full re-sync with a 90-day lookback window (`_time_min_for_backfill()`).

**Rationale:** Sync tokens enable incremental sync (only fetching changed events since last sync). Storing them in the settings table alongside calendar selections keeps all calendar configuration in one place. The 90-day fallback window limits the re-sync cost when tokens expire.

**Constraints/Tradeoffs:** Token expiry triggers a full re-sync which can be slow for calendars with many events. The 90-day window mitigates this but means events older than 90 days are not recovered on re-sync.

---

## 8. Contact-Company Roles

### 8.1 System vs. Custom Roles with is_system Flag

**Decision:** The `contact_company_roles` table uses an `is_system` INTEGER flag (0 or 1) to distinguish between the 8 seeded system roles and custom roles created by admins. System roles cannot be modified or deleted. Custom roles can be created, renamed, reordered, and deleted.

**Rationale:** System roles provide a consistent baseline vocabulary (Employee, Contractor, Volunteer, Advisor, Board Member, Investor, Founder, Intern) that all tenants share. Custom roles allow tenants to extend this vocabulary for their domain. The `is_system` guard prevents accidental corruption of the baseline roles.

**Alternatives Rejected:**

- Enum-based roles (no table, hardcoded in application) — Cannot be extended by admins at runtime.
- Separate tables for system and custom roles — Complicates the foreign key from `contact_companies.role_id` which needs to reference both.

**Constraints/Tradeoffs:** The 8 system roles are seeded during schema creation. If a tenant needs to hide a system role from their UI, they currently cannot — `is_system` roles are always listed. A future `is_hidden` flag could address this.

### 8.2 Deletion Guards: In-Use Check + System Role Check

**Decision:** `delete_role()` enforces two guards before deletion: (1) system roles cannot be deleted (`is_system` check), (2) roles in use by any `contact_companies` affiliation cannot be deleted (referential integrity check via COUNT query). Both guards raise `ValueError` with descriptive messages.

**Rationale:** Deleting an in-use role would either violate FK constraints (if ON DELETE RESTRICT) or silently null out affiliation roles (if ON DELETE SET NULL). Neither outcome is acceptable. The explicit count check provides a user-friendly error message: "Cannot delete: role is used by N affiliation(s)."

**Constraints/Tradeoffs:** The in-use check is a point-in-time count. A concurrent request could create an affiliation with the role between the check and the delete. This is acceptable because: (a) the system is single-tenant with ~1 concurrent user, and (b) the FK constraint provides a database-level backstop.

### 8.3 Multi-Tenant Uniqueness: UNIQUE(customer_id, name)

**Decision:** Role names are unique within a customer, enforced by a check-before-insert pattern in `create_role()`. The function queries for an existing role with the same `(customer_id, name)` and raises `ValueError` on conflict.

**Rationale:** Two customers should be able to independently define a role named "Consultant" without conflict. Within a single customer, duplicate role names would confuse the affiliation UI dropdown.

**Alternatives Rejected:**

- Database-level UNIQUE constraint on `(customer_id, name)` — Would work but produces a less user-friendly error (SQLite IntegrityError vs. a descriptive ValueError).

**Constraints/Tradeoffs:** The check-before-insert pattern has a TOCTOU race condition. A database-level unique index should be added as a backstop. Currently the single-user concurrency model makes this a theoretical rather than practical concern.

---

## 9. React Settings UI Architecture

### 9.1 Zustand Settings Mode Toggle

**Decision:** The navigation Zustand store manages settings state with: `settingsMode: boolean` (true = in settings, false = in grid views), `settingsTab: string` (active tab key), and three actions: `openSettings()`, `closeSettings()`, `setSettingsTab(tab)`. Switching entity types (via `setActiveEntityType()`) automatically exits settings mode.

**Rationale:** Settings mode is orthogonal to the entity/view navigation state. A simple boolean toggle is sufficient because the user is either viewing entity data or managing settings — never both simultaneously. Auto-exiting settings when switching entities prevents the confusing state of having settings open while the icon rail indicates a different entity.

**Alternatives Rejected:**

- URL-based routing (`/app/settings/profile`) — Would require a full router (react-router), which the SPA currently avoids in favor of Zustand state.
- Modal/drawer overlay — Settings UI is complex enough (6 tabs, forms, tables) that a modal would feel cramped. A full content area replacement is appropriate.

**Constraints/Tradeoffs:** Settings state is in-memory (not persisted to localStorage or URL). Refreshing the page exits settings mode. This is acceptable behavior — settings is a destination the user navigates to intentionally.

### 9.2 Component Map Routing

**Decision:** `ContentArea.tsx` uses a `SETTINGS_COMPONENTS` record mapping tab keys to React components: `{profile: ProfileSettings, system: SystemSettings, users: UsersSettings, accounts: AccountsSettings, calendars: CalendarsSettings, roles: RolesSettings}`. When `settingsMode` is true, it renders the component for `settingsTab`, falling back to `ProfileSettings` for unknown keys.

**Rationale:** A static component map is simpler than a router and provides compile-time verification that all tab keys map to real components. The fallback to ProfileSettings ensures the UI never renders an empty content area for an invalid tab key.

**Alternatives Rejected:**

- Switch statement — Works but is less maintainable as tabs are added.
- Dynamic import (`React.lazy`) — Over-engineering for 6 small components that are already bundled.

**Constraints/Tradeoffs:** All 6 settings components are imported eagerly in `ContentArea.tsx`, adding to the initial bundle size. Acceptable because the components are small (forms and tables, no heavy dependencies).

### 9.3 Settings Tab Configuration with adminOnly Filter

**Decision:** `ActionPanel.tsx` defines `SETTINGS_TABS` as an array of objects: `{key, label, icon, adminOnly}`. The panel filters tabs based on the current user's role — non-admin users see only Profile, Accounts, and Calendars. Admin users see all 6 tabs, grouped visually: personal (Profile, Accounts, Calendars) and admin (System, Roles, Users).

**Rationale:** Client-side filtering provides immediate UI feedback (non-admin users never see admin tabs). Server-side enforcement via the 403 admin check (Section 6.3) prevents privilege escalation even if a user manipulates the client state.

**Alternatives Rejected:**

- Fetch tabs from server — Unnecessary round-trip for a static list of 6 items.
- Single flat list without grouping — Loses the visual distinction between personal and admin settings.

**Constraints/Tradeoffs:** The tab list is duplicated between `SETTINGS_TABS` (ActionPanel) and `SETTINGS_COMPONENTS` (ContentArea). Adding a new tab requires updating both. This could be unified into a single configuration object, but the separation keeps each component focused.

### 9.4 React Query Hooks: 20 Hooks Across 6 Domains

**Decision:** `frontend/src/api/settings.ts` exports 20 React Query hooks organized by domain: Profile (3: `useProfile`, `useUpdateProfile`, `useChangePassword`), Users (5: `useUsers`, `useCreateUser`, `useUpdateUser`, `useSetUserPassword`, `useToggleUserActive`), Accounts (3: `useAccounts`, `useUpdateAccount`, `useToggleAccount`), Calendars (3: `useCalendars`, `useFetchCalendars`, `useSaveCalendars`), Roles (4: `useRoles`, `useCreateRole`, `useUpdateRole`, `useDeleteRole`), Reference Data (1: `useReferenceData`), plus a shared `settingsApi` fetch wrapper.

**Rationale:** One hook per endpoint follows the React Query convention and provides granular cache management. Each mutation hook invalidates only the relevant query keys on success, preventing unnecessary refetches.

**Key cache invalidation patterns:**

- User mutations invalidate `['settings', 'users']`
- Account toggle invalidates both `['settings', 'accounts']` and `['settings', 'calendars']` (account status affects calendar availability)
- Role mutations invalidate both `['settings', 'roles']` and `['settings', 'reference-data']` (reference data includes the roles list)
- Profile update invalidates `['settings', 'profile']`

**Alternatives Rejected:**

- Generic CRUD hook factory — Would reduce boilerplate but obscure the per-endpoint invalidation logic, which varies by domain.
- Global cache invalidation on any settings mutation — Would cause unnecessary refetches across all settings tabs.

**Constraints/Tradeoffs:** 20 hooks in a single file is manageable but approaching the threshold where splitting by domain (e.g., `settings-profile.ts`, `settings-users.ts`) would improve maintainability. Deferred.

### 9.5 Reference Data Aggregation Endpoint

**Decision:** `GET /api/v1/settings/reference-data` returns a single JSON object aggregating: timezones (from `COMMON_TIMEZONES`), countries (from `COMMON_COUNTRIES`), email history options (from sync module `EMAIL_HISTORY_OPTIONS`), roles (from database), and `google_oauth_configured` boolean (from `config.GOOGLE_OAUTH_CLIENT_ID`). Stale time: 5 minutes.

**Rationale:** Settings forms need dropdown options (timezone, country, email history) that rarely change. Aggregating them into one endpoint eliminates 4+ separate requests on settings page load. The 5-minute stale time means the data is fetched once and shared across all settings tabs within a session.

**Alternatives Rejected:**

- Inline hardcoded options in React — Would duplicate the timezone/country lists between server and client, and prevent runtime additions.
- Separate endpoint per reference type — More round-trips for data that's always needed together.

**Constraints/Tradeoffs:** The endpoint returns all reference data regardless of which settings tab the user is viewing. The payload is small (~5 KB), so the over-fetching is negligible compared to the round-trip cost of multiple requests.

---

## 10. Decisions to Be Added

The following areas will require technical decisions during implementation that should be documented here:

- **Audit Logging:** The PRD requires all administrative actions to be audit-logged with acting user, timestamp, action type, target entity, old/new values, and IP address. No audit logging infrastructure exists yet. Decisions needed: audit table schema, what gets logged, retention policy, query/viewer UI.
- **Session TTL Enforcement:** The PRD defines `session_ttl_hours` as a configurable system setting (default 720). Currently, TTL is hardcoded at 720 in `create_session()`. Decisions needed: read TTL from settings on session creation, handle TTL changes for existing sessions.
- **Setting Type Validation:** The PRD defines setting types (string, boolean, integer, select) with constraints. Currently, all values are stored as unvalidated TEXT. Decisions needed: validation layer (at storage or API level), setting metadata schema.
- **Data Operations (Backup/Restore/Purge):** The PRD defines manual backup creation, backup restoration, and GDPR data purge as admin capabilities. None are implemented in the web UI. Decisions needed: backup directory management, restore safety checks, purge scope and anonymization rules.
- **System Health Dashboard:** The PRD defines sync status, error rates, database metrics, and background job monitoring. No health endpoints exist. Decisions needed: which metrics to collect, storage strategy (ephemeral vs. persisted), alerting thresholds.
- **User Invitation Flow:** The PRD describes an invite → active lifecycle. Currently, `create_user()` creates users directly as active. Decisions needed: invitation token generation, email delivery, registration completion flow.
- **Last-Admin Protection:** The PRD requires preventing demotion or deactivation of the last admin. Currently, only self-deactivation is prevented. Decisions needed: count-based guard on role change and deactivation, error messaging.
