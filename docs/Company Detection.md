# Company Detection — Domain-Only Resolution

## Overview

During Google Contact sync, each contact is affiliated with a company
based on their **email domain** — the sole source of truth for company
identity.  The Google Contacts organization name field is ignored because
it's hand-entered, often stale, and sometimes wrong.

**Function:** `_resolve_company_id(conn, email, now, *, customer_id, user_id)`
**Location:** `poc/sync.py`

## Parameters

| Param       | Type               | Description                                      |
|-------------|--------------------|--------------------------------------------------|
| conn        | sqlite3.Connection | Open DB connection (caller manages transaction)  |
| email       | str                | The contact's email address                      |
| now         | str                | ISO timestamp for created_at/updated_at          |
| customer_id | str \| None        | Tenant ID for multi-tenant scoping               |
| user_id     | str \| None        | User who owns the auto-created company           |

**Returns:** `str | None` — company ID, or None for public/no domain.

## Resolution Flow

```
email → extract domain → public? → return None
                       → private → resolve_company_by_domain()
                                   → found? → return existing ID
                                   → not found → auto-create company
                                                 (name=domain, domain=domain)
                                                 → register domain identifier
                                                 → return new ID
```

See `docs/sync_resolve_company_id_flowchart.mmd` for a Mermaid diagram.

### Step 1: Extract and Classify Domain

- Calls `extract_domain(email)` to get e.g. "dbllaw.com" from
  "ahartman@dbllaw.com".
- If no domain (no `@`) or domain is in `PUBLIC_DOMAINS` (gmail.com,
  yahoo.com, etc. — 28 providers), returns `None` immediately.
- Contacts with public-domain emails get **no company affiliation**.

### Step 2: Look Up Existing Company

Calls `resolve_company_by_domain(conn, domain)` which checks:
1. `companies.domain` column for an active company.
2. Fallback: `company_identifiers` JOIN where `type='domain'`.

If found, returns the existing company's ID.

### Step 3: Auto-Create Company

If no company matches the domain:
1. Creates a new company with `name = domain` and `domain = domain`
   (e.g., name "dbllaw.com", domain "dbllaw.com").
2. If `user_id` provided, creates a `user_companies` visibility row.
3. Registers the domain in `company_identifiers` via
   `ensure_domain_identifier()` so future contacts resolve here.

## Batch Website Enrichment

After sync completes, `enrich_new_companies()` finds all companies with
a domain but no completed enrichment run, and scrapes their websites to
discover real names.

**Name extraction sources (in order of confidence):**
1. JSON-LD `Organization.name` (confidence 0.9)
2. `og:site_name` meta tag (confidence 0.8)

**Overwrite guard:** The enrichment pipeline only overwrites the company
name when the current name equals the domain column (i.e., it's still a
placeholder).  Manually-entered or previously-enriched names are preserved.

**Retry logic:** Only `status='completed'` enrichment runs are excluded.
Failed runs are retried on the next sync cycle.

## The Bug This Fixed

**Before (name-based resolution):** Contact "Alan J Hartman" with email
`ahartman@dbllaw.com` had Google org "Ulmer & Berne LLP".  The old
`_resolve_company_id()` matched "Ulmer & Berne LLP" by name and returned
that company — even though Ulmer's domain is `ulmer.com`, not `dbllaw.com`.
The contact was affiliated with the wrong company.

**After (domain-only resolution):** The function ignores the Google org
name entirely.  It extracts domain "dbllaw.com", finds no matching company,
and auto-creates one named "dbllaw.com".  Batch enrichment later scrapes
dbllaw.com to discover the real company name.

## Key Design Decisions

- **Domain is sole truth:** Google org names are untrustworthy.  Two contacts
  at the same company may have "Acme Corp", "Acme Inc", and "ACME" as their
  org names.  Domain matching prevents all three from creating separate companies.

- **Public emails → no affiliation:** A contact with only a gmail.com address
  gets no company link.  This is honest — we don't know where they work.

- **Name = domain as placeholder:** Auto-created companies get a functional but
  ugly name ("dbllaw.com") that serves as a clear signal that enrichment hasn't
  run yet.  The enrichment guard (`name == domain`) precisely targets these
  placeholders without risking real names.

## Entry Points

| Entry Point | Location |
|-------------|----------|
| Contact sync | `poc/sync.py` → `sync_contacts()` |
| Web UI sync | Dashboard "Sync Now" → `poc/web/routes/dashboard.py` |
| CLI batch enrichment | `python -m poc enrich-new-companies` |
| CLI single enrichment | `python -m poc enrich-company COMPANY_ID` |

## Tests

- `tests/test_company_merge.py::TestSyncDuplicateDetection` — 9 tests
  covering domain matching, auto-creation, public domains, dedup, visibility
- `tests/test_enrichment.py::TestNameExtraction` — 4 tests for name
  extraction and overwrite guard
- `tests/test_enrichment.py::TestEnrichNewCompanies` — 3 tests for batch
  enrichment (find, skip completed, retry failed)
- `tests/test_scoping.py::TestSyncScoping` — verifies customer_id scoping
