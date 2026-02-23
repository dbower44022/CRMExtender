# Company — Entity Base PRD

**Version:** 1.0
**Last Updated:** 2026-02-23
**Status:** Draft
**Product PRD:** [CRMExtender Product PRD]

---

## 1. Entity Definition

### 1.1 Purpose

Company represents an organization that contacts work for, interact with, or belong to. It is the primary firmographic entity in the CRM — the anchor point for employment relationships, domain-based identity resolution, enrichment intelligence, and organizational hierarchy modeling. Companies are living records: auto-created from email domains, progressively enriched from multiple sources, and scored for relationship strength based on communication patterns.

### 1.2 Design Goals

- Companies are discovered automatically from email domains during sync — no manual entry required for initial population.
- Enrichment progressively improves company records from free sources first (website scraping, Wikidata), paid APIs later.
- Relationship strength scoring surfaces which companies matter most based on actual communication behavior.
- Corporate hierarchy models real organizational structures (parent/subsidiary/division/acquisition) with temporal tracking.
- Domain-based identity is the canonical duplicate key — no fuzzy name matching.

### 1.3 Performance Targets

| Metric | Target |
|---|---|
| Company list load (default view, 50 rows) | < 200ms |
| Company detail page load | < 200ms |
| Domain resolution lookup | < 50ms |
| Enrichment trigger (background) | Non-blocking, < 5s to queue |
| Relationship strength sort | < 200ms (via precomputed scores) |

### 1.4 Core Fields

Fields are described conceptually. Data types and storage details are specified in the Company Entity TDD.

**Editable column** declares how (or if) the user can modify each field. This prevents implementation from making computed or system fields editable:

- **Direct** — User edits this field inline on the detail page or edit form.
- **Override** — Field is computed by default but the user can manually override. The UI should indicate when a value is overridden vs. computed (e.g., a small "reset to computed" action).
- **Via [sub-entity]** — The displayed value is a summary of a related record. Editing opens the sub-entity's own editor, not an inline edit on the company card.
- **Computed** — Derived from other data. Not directly editable. The user changes this by modifying the source data it derives from.
- **System** — Set and managed by the system. Never user-editable.

**Sortable / Filterable columns** declare whether the user can sort and filter by each field in list views and grid context menus. Fields marked with † are derived from subqueries; the Entity TDD must implement a caching or denormalization strategy to ensure acceptable sort performance.

| Field | Description | Required | Editable | Sortable | Filterable | Valid Values / Rules |
|---|---|---|---|---|---|---|
| ID | Unique identifier. Prefixed ULID with `cmp_` prefix (e.g., `cmp_01HX8A...`). Immutable after creation. | Yes | System | No | Yes | Prefixed ULID |
| Name | Company display name. Initially set to domain for auto-created companies; enrichment or user edit overwrites. | Yes | Override | Yes | Yes | Free text |
| Primary Domain | The company's primary web domain, denormalized from identifiers. Used for email domain matching and display. | No | Via Identifiers | Yes † | Yes | Valid domain format |
| Industry | Industry classification. | No | Direct | Yes | Yes | Free text |
| Size Range | Employee count range, aligned with LinkedIn's classification. | No | Direct | Yes | Yes | `1-10`, `11-50`, `51-200`, `201-500`, `501-1000`, `1001-5000`, `5001-10000`, `10001+` |
| Employee Count | Raw employee count when known. Size Range is derived from it when available. | No | Direct | Yes | Yes | Positive integer |
| Location | Headquarters location (city, state/country). Denormalized from primary address for display. | No | Via Addresses | Yes | Yes | Free text |
| Description | Brief company description. | No | Direct | No | No | Free text |
| Logo URL | Company logo. May come from enrichment, website scraping, or manual upload. | No | Direct | No | No | Valid URL or asset path |
| Website | Company website URL (may differ from domain). | No | Direct | No | No | Valid URL |
| LinkedIn URL | Company LinkedIn page URL. | No | Direct | No | No | Valid URL |
| Stock Symbol | Stock ticker symbol (e.g., `GOOGL`, `AAPL`). | No | Direct | Yes | Yes | Free text |
| Founded Year | Year the company was founded. | No | Direct | Yes | Yes | Four-digit year |
| Revenue Range | Annual revenue range. | No | Direct | Yes | Yes | Free text |
| Funding Total | Total funding raised. | No | Direct | Yes | Yes | Free text |
| Funding Stage | Latest funding stage. | No | Direct | Yes | Yes | `pre_seed`, `seed`, `series_a`, `series_b`, `series_c`, `series_d_plus`, `ipo`, `private`, `bootstrapped` |
| Relationship Strength | Composite metric reflecting communication patterns between the user and the company's contacts. Precomputed and stored for fast sorting. | No, defaults to 0.0 | Computed | Yes † | Yes | 0.0–1.0 |
| Status | Record lifecycle status. See Lifecycle section. | Yes, defaults to `active` | System | Yes | Yes | `active`, `merged`, `archived` |
| Created By | The user who created the company, or null for auto-created companies. | No | System | No | Yes | Reference to User |
| Created At | When the company was created. | Yes | System | Yes | Yes | Timestamp |
| Updated At | When the company was last modified. | Yes | System | Yes | Yes | Timestamp |

**† Requires caching:** Fields marked with † are derived from subqueries or cross-table computations. The Entity TDD must define a caching or denormalization strategy with triggers or application logic to keep cached values in sync.

### 1.5 Company Identifiers

A company can own multiple domains and other identifiers. The identifier model stores every way a company can be identified, with source tracking. This is the primary mechanism for duplicate detection and email-domain-to-company resolution.

Each identifier has:

| Attribute | Description | Rules |
|---|---|---|
| Type | The kind of identifier. | `domain` (extensible to `duns`, `ein`, `lei` in future) |
| Value | The identifier itself, normalized. | Domains are lowercased, root-extracted, www-stripped. |
| Is Primary | Whether this is the primary identifier for its type. | At most one primary per company per type. |
| Source | How this identifier was discovered. | `email_sync`, `website_scrape`, `manual`, `enrichment`, `merge` |

**Key business rules:**

- A given identifier value (within its type) can only belong to one company. If a second company claims the same domain, the system blocks creation and presents the existing company, offering to merge.
- The primary domain on the company record is kept in sync with the identifiers model automatically.
- Domain resolution is the sole mechanism for company auto-creation — the Google Contacts organization name field is explicitly ignored to avoid misattribution.

### 1.6 Computed / Derived Fields

These fields are derived from other data. None support inline editing on the company card — the user must edit the source data through the appropriate sub-entity editor.

| Field | Description | Editable | Derivation Logic |
|---|---|---|---|
| Name | Company display name | Override | Initially set to domain for auto-created companies. Enrichment overwrites when a real name is discovered (only if current name still equals domain — the "overwrite guard"). User can edit directly at any time, which takes permanent precedence. |
| Primary Domain | Main domain for display | Via Identifiers | Synced from identifier with `type=domain`, `is_primary=true`. |
| Location | Headquarters for display | Via Addresses | Synced from the primary headquarters address. |
| Relationship Strength | Communication-derived score (0.0–1.0) | Computed | Weighted composite of recency, frequency, reciprocity, breadth, and duration of communications with company contacts. Precomputed daily and on communication events. See Company Intelligence & Scoring Sub-PRD for computation details. |

### 1.7 Registered Behaviors

Per Custom Objects PRD, the Company system object type registers these specialized behaviors:

| Behavior | Trigger | Description |
|---|---|---|
| Domain resolution | On creation, on domain change | Resolve company identity from email domain; check for duplicates via identifiers. |
| Firmographic enrichment | On creation, on schedule | Run enrichment providers to populate company fields. |
| Relationship strength scoring | On communication event, daily decay | Compute relationship strength from communication patterns. |
| Hierarchy inference | On enrichment | Detect parent/subsidiary relationships from enrichment data; suggest hierarchy links. |

---

## 2. Entity Relationships

### 2.1 Contacts (Employment)

**Nature:** Many-to-many, temporal
**Ownership:** Defined by Contact Management PRD via the Contact→Company employment Relation Type
**Description:** Contacts are linked to companies through employment records with temporal metadata (start date, end date, is_current flag). A contact can have multiple employment records at the same or different companies. Employment records carry role and department metadata. When a company is resolved from an email domain, contacts with matching email addresses are automatically linked via employment records.

### 2.2 Companies (Hierarchy)

**Nature:** Many-to-many, self-referential, temporal
**Ownership:** Company entity owns this relationship
**Description:** Company-to-company hierarchy models organizational structure: parent/subsidiary, division, acquisition, and spinoff relationships. Supports arbitrary nesting depth, multiple parents (e.g., joint ventures), and temporal tracking with effective/end dates. Each hierarchy relationship carries a type and optional metadata (acquisition amount, deal terms). See Company Hierarchy Sub-PRD for full details.

### 2.3 Communications

**Nature:** Indirect, via contact participants
**Ownership:** Communications PRD
**Description:** Companies are not directly linked to communications. The relationship is derived through contact participants — a communication involves contacts, and contacts have employment records at companies. This means viewing a company's communication history requires traversing contact employment records. Communication patterns feed the relationship strength scoring system.

### 2.4 Conversations

**Nature:** Indirect, via contact participants
**Ownership:** Conversations PRD
**Description:** Same indirect linkage as communications. Conversations group communications into threads, and companies are associated via the contacts involved.

### 2.5 Events

**Nature:** Many-to-many, via event participants
**Ownership:** Events PRD
**Description:** Companies participate in calendar events through the event participants model. A company can be listed as a participant independently of individual contacts.

### 2.6 Tags

**Nature:** Many-to-many
**Ownership:** Shared (entity-agnostic tagging system)
**Description:** Companies can have tags applied for categorization and filtering. Tags are lightweight labels with name, optional color, and source attribution. Tags can be manual, AI-suggested, imported, or rule-based.

### 2.7 Notes

**Nature:** Many-to-many, via universal attachment
**Ownership:** Notes PRD
**Description:** Notes can be attached to company records as supplementary commentary. Follows the universal attachment relation pattern.

### 2.8 Documents

**Nature:** Many-to-many, via universal attachment
**Ownership:** Documents PRD
**Description:** Documents can be attached to company records. Follows the universal attachment relation pattern.

### 2.9 Social Profiles

**Nature:** One-to-many
**Ownership:** Company entity
**Description:** A company can have multiple social media profiles across platforms (LinkedIn, Twitter, Facebook, GitHub, Instagram). Each profile carries verification status, follower metrics, and monitoring configuration. See Company Social Media Profiles Sub-PRD for full details.

---

## 3. Lifecycle

### 3.1 Statuses

| Status | Description |
|---|---|
| `active` | Normal operating state. Visible in all default views and search results. |
| `merged` | This company was absorbed into another company during a merge operation. Soft-deleted from default queries. All associated entities have been reassigned to the surviving company. Data preserved in merge audit trail. |
| `archived` | Manually archived by a user. Excluded from default queries but all data preserved. Recoverable via unarchive. |

### 3.2 Transitions

| From | To | Trigger |
|---|---|---|
| `active` | `archived` | User archives the company |
| `active` | `merged` | Company is absorbed during a merge operation |
| `archived` | `active` | User unarchives the company |

Note: `merged` is a terminal state — merged companies cannot be unarchived. Undoing a merge requires the split operation (see Merge Sub-PRD).

### 3.3 Creation Sources

| Source | Initial Status | Notes |
|---|---|---|
| Email domain resolution | `active` | Auto-created when a non-public email domain is encountered during sync. Name initially set to domain. Enrichment triggered immediately. |
| Manual entry | `active` | User creates via "Add Company" in the UI. |
| Import | `active` | Created from CSV or other bulk import. |
| Enrichment discovery | `active` | A parent/subsidiary company discovered during enrichment of another company. |

### 3.4 Deletion & Data Retention

- Company records are never hard-deleted except through a GDPR/CCPA DSAR workflow (if applicable to company data in the tenant's jurisdiction).
- Archived companies and their full data are retained indefinitely.
- Merged companies are soft-deleted with full snapshots preserved in the merge audit trail.
- Event history is retained indefinitely, with periodic snapshots to bound replay depth.

---

## 4. Key Processes

### KP-1: Auto-Creating a Company from Email Domain

**Trigger:** During email sync or contact sync, the system encounters an email address with a non-public domain that doesn't match any existing company.

**Step 1 — Domain extraction:** System extracts the root domain from the email address (strip www, subdomains, normalize to lowercase).

**Step 2 — Public domain check:** System checks the public domain exclusion list. If the domain is public (gmail.com, etc.), no company is created. Process ends.

**Step 3 — Existing company check:** System looks up the domain in company identifiers. If found, the existing company is returned. Process ends.

**Step 4 — Domain validation:** System validates the domain has a working website. If invalid or parked, the domain is logged for manual review. Process ends.

**Step 5 — Company creation:** System creates a new company with name = domain, registers the domain as the primary identifier, and triggers Tier 1 enrichment (website scraping).

**Step 6 — Contact linking:** System links any contacts with matching email addresses to the new company via employment records (where no existing employment at a different company exists).

### KP-2: Browsing and Finding Companies

**Trigger:** User navigates to the Companies entity in the Entity Bar.

**Step 1 — Default view loads:** The Content Panel displays the user's default company view (or the system default "All Companies" view). Companies load sorted by the view's configured sort order. Grid displays columns per the view's column configuration.

**Step 2 — Filtering:** User applies filters from the Content Tool Bar. Available filters correspond to fields marked Filterable=Yes. Filters apply immediately and the grid updates.

**Step 3 — Sorting:** User clicks a column header to sort. Available sort columns correspond to fields marked Sortable=Yes. Sort applies immediately.

**Step 4 — Searching:** User uses global search or the view's search bar. Company name, domain, industry, and tags are searchable.

**Step 5 — Selection:** User clicks a company row. The Detail Panel opens showing the company's profile in a Docked Window.

### KP-3: Viewing a Company's Full Profile

**Trigger:** User clicks a company row in a view, or navigates to a company from a link elsewhere in the UI.

**Step 1 — Identity Card loads:** Displays company name, logo, primary domain, industry, and quick-action buttons (edit, enrich, archive).

**Step 2 — Attribute Cards load:** Field Groups display the company's data organized by category (Overview, Firmographics, Scores).

**Step 3 — Relation Cards load:** Show employment records (contacts at this company), hierarchy relationships (parent/subsidiary), tags.

**Step 4 — Activity Card loads:** Communication timeline derived from contacts employed at this company. Events where the company is a participant.

**Step 5 — On-demand data:** Social profiles, enrichment history, and graph relationships load on demand when the user scrolls to or expands those cards.

### KP-4: Editing a Company

**Trigger:** User clicks the edit action on a company field or Attribute Card.

**Step 1 — Section-Based Editing:** The relevant Attribute Card enters edit mode. Only one card can be in edit mode at a time.

**Step 2 — Field editing:** User modifies field values. Fields marked as Direct are editable inline. Fields marked as Override show a "reset to computed" action. Fields marked as Via [sub-entity] open the appropriate editor.

**Step 3 — Save:** User saves changes. An event is emitted recording the change with previous value, new value, timestamp, and user.

**Step 4 — Computed field update:** Any computed fields that depend on the edited data are recalculated (e.g., editing a domain triggers re-evaluation of the primary domain display).

### KP-5: Archiving and Restoring a Company

**Trigger:** User selects Archive from the company's action menu.

**Step 1 — Confirmation:** System shows a confirmation dialog: "Archive [Company Name]? The company will be removed from default views but all data will be preserved."

**Step 2 — Archive execution:** Company status set to `archived`. Company removed from default views and search results.

**Step 3 — Restore (if needed):** User navigates to an "Archived Companies" view, selects the company, and clicks Unarchive. Company status restored to `active`.

### KP-6: Managing Tags on a Company

**Trigger:** User adds or removes tags from a company via the tags section of the detail page.

**Step 1 — Tag input:** User types a tag name. Autocomplete suggests existing tags. User can select an existing tag or create a new one inline.

**Step 2 — Tag applied:** Tag is associated with the company. An event is emitted.

**Step 3 — Tag removal:** User clicks the remove action on an existing tag. Tag association is removed.

---

## 5. Action Catalog

### 5.1 Create Company

**Supports processes:** KP-1 (auto-creation flow), KP-2 (manual via "Add Company" button)
**Trigger:** User clicks "Add Company" in the UI, or system auto-creates from domain resolution during sync.
**Inputs:** For manual: company name, optional domain, industry, description. For auto-creation: domain only.
**Outcome:** New company record created with status `active`. If auto-created, name is set to domain and enrichment is triggered. If domain is provided, system checks for duplicates via identifiers.
**Business Rules:** Before creating, the system checks existing identifiers for a matching domain. If found, the existing company is presented instead of creating a duplicate.

### 5.2 Edit Company

**Supports processes:** KP-4 (full flow)
**Trigger:** User modifies any field on the company record via the detail page.
**Inputs:** Updated field values.
**Outcome:** Company record updated. An event is emitted recording the change. User-entered data takes permanent precedence over enrichment data.
**Business Rules:** Editing a domain field triggers duplicate checking. If the new domain already belongs to another company, the system blocks the change and offers to merge.

### 5.3 View Company

**Supports processes:** KP-2 (step 5), KP-3 (full flow)
**Trigger:** User navigates to a company's detail page.
**Inputs:** Company ID.
**Outcome:** Unified detail page displaying profile information, contacts (via employment), hierarchy relationships, communication timeline, social profiles, enrichment status, scores, notes, and tags. Rendered via the Card-Based Architecture per the GUI Standards.
**Business Rules:** Company data loads within 200ms. Intelligence scores and graph relationships may be fetched on demand if not cached.

### 5.4 Archive Company

**Supports processes:** KP-5 (steps 1–2)
**Trigger:** User archives a company from the detail page or list view.
**Inputs:** Company ID, optional reason.
**Outcome:** Company status set to `archived`. Company removed from active lists and search results. All data preserved.
**Business Rules:** Archiving is reversible via unarchive (restores to `active` status).

### 5.5 Tags

**Supports processes:** KP-6 (full flow)
**Trigger:** User adds or removes tags from a company.
**Inputs:** Company ID, tag name (or selection from existing tags).
**Outcome:** Tag applied to or removed from the company.
**Business Rules:** Tags are lightweight labels with name, optional color, and source attribution. Tags are unique by name within a tenant. Same tagging system as contacts.

### 5.6 Domain Resolution & Identifiers

**Summary:** The process by which the system identifies or creates company records from email domains. Covers domain extraction, normalization, public domain exclusion, existing company lookup, auto-creation with placeholder naming, domain validation, and contact-to-company linking. Also manages the multi-domain identifier model that enables duplicate detection and supports future identifier types (DUNS, EIN, LEI).
**Sub-PRD:** [company-domain-resolution-prd.md]

### 5.7 Duplicate Detection & Merging

**Summary:** Domain-based duplicate detection with a merge flow that combines two company records into one surviving record. Includes the merge-vs-hierarchy fork (asking whether related companies are duplicates or hierarchically related), merge preview with side-by-side comparison and conflict resolution, merge execution that reassigns all contacts, events, relations, identifiers, and hierarchy links to the survivor, and a full audit trail with snapshot of the absorbed company. Split (undo merge) reverses a bad merge.
**Sub-PRD:** [company-merge-prd.md]

### 5.8 Company Hierarchy

**Summary:** Models organizational structure between companies: parent/subsidiary, division, acquisition, and spinoff relationships. Implemented as a self-referential Company→Company Relation Type with temporal metadata (effective/end dates). Supports arbitrary nesting depth, multiple parents, and type-specific metadata. Subsidiaries are treated as separate entities for communication purposes — no automatic aggregation across hierarchy levels.
**Sub-PRD:** [company-hierarchy-prd.md]

### 5.9 Enrichment Pipeline

**Summary:** Progressive enrichment of company records from a three-tier source architecture: Tier 1 (owned data — website scraper, email signature parser), Tier 2 (free public APIs — Wikidata, OpenCorporates, SEC EDGAR), Tier 3 (paid APIs — Clearbit, Apollo, Crunchbase). Uses a pluggable provider model with a common interface. Includes enrichment triggering (on creation, on schedule, on demand, retroactive batch), confidence scoring, source priority hierarchy for conflict resolution, the "overwrite guard" for placeholder names, and enrichment run tracking with field-level provenance.
**Sub-PRD:** [company-enrichment-prd.md]

### 5.10 Intelligence & Scoring

**Summary:** Relationship strength scoring computed from communication patterns between the user and a company's contacts. Uses a five-factor weighted model (recency, frequency, reciprocity, breadth, duration) with directionality weighting (outbound > inbound) and time decay. Scores are precomputed and stored for fast sorting and display, with factor breakdowns for transparency. Recalculation is event-driven, daily (time decay), and bulk (after merge/import). Derived metrics include communication volume, last contact date, key contacts, topic distribution, and meeting frequency. Intelligence is surfaced through saved views rather than interruptive alerts.
**Sub-PRD:** [company-intelligence-prd.md]

### 5.11 Social Media Profiles

**Summary:** Tracking of company social media presence across platforms (LinkedIn, Twitter, Facebook, GitHub, Instagram). Profiles are discovered through explicit links found in scraped website data, email signatures, manual entry, or enrichment APIs — never auto-discovered from company names or domains. Each profile carries verification status, follower metrics, and posting activity. Monitoring tiers (high, standard, low, none) control scanning frequency and extraction depth. Change detection surfaces meaningful updates (bio changes, leadership changes) in the company's activity stream.
**Sub-PRD:** [company-social-profiles-prd.md]

---

## 6. Cross-Cutting Concerns

### 6.1 Entity-Agnostic Shared Tables

Companies share platform-wide tables for multi-value data that complements the single-value fields on the read model table:

- **Addresses** — Multiple typed addresses (headquarters, branch, billing, mailing) with source and confidence tracking. The primary headquarters address is denormalized on the company's Location field.
- **Phone Numbers** — Multiple typed phone numbers (main, direct, support, sales, fax) in E.164 format with source tracking.
- **Email Addresses** — Multiple typed email addresses (general, support, sales, billing) with source tracking. These are organizational contact points, distinct from the domain-based identifiers used for resolution.
- **Entity Assets** — Content-addressable storage for logos and banners. SHA-256 hash determines filesystem path for automatic deduplication.

### 6.2 Event Sourcing & Temporal History

All company mutations are stored as immutable events. The system can reconstruct any company's complete state at any point in time. This provides full audit trails, supports merge undo (split), and enables compliance with data subject access requests. Implementation details for the event store are specified in the Company Entity TDD.

### 6.3 Neo4j Graph Sync

Company hierarchy and business relationships are synced to Neo4j for graph queries. This enables queries like "what companies are connected to Acme through shared contacts?" and "show the full corporate hierarchy for Alphabet." Company nodes carry core firmographic data; edges represent hierarchy types, business relationships, and cross-entity connections (Contact→Company employment).

### 6.4 Data Retention

- Company records are never hard-deleted except through a formal data subject deletion workflow.
- Archived companies and their full data are retained indefinitely.
- Merged companies are soft-deleted with full snapshots preserved in the merge audit trail.
- Event history is retained indefinitely, with periodic snapshots to bound replay depth.

---

## 7. Open Questions

1. **Domain validation depth** — When auto-creating companies from email domains, should the system only check for a working website (HTTP 200), or also validate the domain has meaningful content (not a parked domain)?

2. **Multi-domain company merging** — When two companies with different domains are merged and a contact's email domain matches the absorbed company, should the employment record's company_name metadata be updated to the surviving company's name, or preserved as historical?

3. **Hierarchy cycle prevention** — Should cycle detection (A → B → C → A) be enforced at the application level? What is the performance implication for deeply nested hierarchies?

4. **Company record limit per tenant** — Should there be a limit on auto-discovered companies per tenant? The auto-discovery mechanism could create thousands of companies from a large email archive.

5. **Subsidiary communication aggregation** — Should there be an optional "roll up communications" view that aggregates across a hierarchy for reporting purposes?

---

## 8. Design Decisions

### Why root domain as the duplicate key instead of fuzzy name matching?

Fuzzy name matching produces false positives (e.g., "Springfield Insurance" matching "Springfield Consulting") and misses legitimate duplicates with different names ("Google" vs "Alphabet"). Root domain is a precise, globally unique identifier that eliminates both problems.

### Why ignore the Google Contacts organization name?

Google Contacts org names are user-entered text strings with no normalization or authority. A contact at email `ahartman@dbllaw.com` might have org "Ulmer & Berne LLP" — matching by name would link them to the wrong company. Domain-only resolution prevents this class of error.

### Why auto-create companies named after their domain?

The alternative is requiring a real name before creating a record, which blocks contact-to-company linking until enrichment completes. The domain-as-placeholder approach ensures contacts are linked immediately; enrichment improves the name asynchronously. The overwrite guard ensures only placeholder names are replaced by enrichment.

### Why precomputed scores instead of on-demand calculation?

Score computation requires traversing communication participants and employment records — expensive for lists and sorting. Precomputing and storing in a dedicated scores table enables O(1) reads for sort-by-strength views. The tradeoff is eventual consistency (scores may be up to 24h stale for time decay), which is acceptable for relationship intelligence.

### Why views over alerts?

Alerts interrupt the user's current focus and create notification fatigue. Views let users pull intelligence when ready. The same underlying data powers both approaches, so alerts can be added later if demand emerges.

### Why denormalize primary domain and headquarters location?

Both values are displayed on nearly every company list and detail view. Joining to identifiers or addresses on every list query adds unnecessary complexity. The denormalized values are kept in sync automatically. The authoritative data lives in the normalized tables.

### Why entity-agnostic enrichment instead of separate company/contact pipelines?

The enrichment pipeline shares the same patterns for both entity types: trigger evaluation, provider selection, rate limiting, confidence scoring, conflict resolution, and run tracking. A shared architecture avoids duplicating this logic and enables future entity types to inherit enrichment capability automatically.

---

## Related Documents

| Document | Relationship |
|---|---|
| [Company Entity TDD](company-entity-tdd.md) | Technical decisions for company implementation |
| [Company Domain Resolution Sub-PRD](company-domain-resolution-prd.md) | Domain resolution and identifier management |
| [Company Merge Sub-PRD](company-merge-prd.md) | Duplicate detection and merge operations |
| [Company Hierarchy Sub-PRD](company-hierarchy-prd.md) | Corporate hierarchy modeling |
| [Company Enrichment Sub-PRD](company-enrichment-prd.md) | Enrichment pipeline and provider architecture |
| [Company Intelligence & Scoring Sub-PRD](company-intelligence-prd.md) | Relationship strength scoring and derived metrics |
| [Company Social Profiles Sub-PRD](company-social-profiles-prd.md) | Social media profile tracking and monitoring |
| [Contact Entity Base PRD](contact-entity-base-prd.md) | Contact entity — Contact→Company employment relationship |
| [Custom Objects PRD](custom-objects-prd.md) | Unified object model, field registry, and relation framework |
| [Communications PRD](communications-prd.md) | Communication entity — company linkage via contact participants |
| [Events PRD](events-prd.md) | Event entity — company participation |
| [Master Glossary](glossary.md) | Term definitions |
