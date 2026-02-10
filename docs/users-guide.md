# User's Guide

This guide covers day-to-day usage of the CRM Extender email pipeline:
setup, account management, running syncs, and understanding the output.

---

## Prerequisites

Before running the pipeline you need two things in the `credentials/`
directory:

1. **`credentials/client_secret.json`** -- OAuth 2.0 client secret
   downloaded from Google Cloud Console (APIs & Services > Credentials >
   OAuth 2.0 Client IDs > Download JSON).

2. **`.env` file** in the project root (copy from `.env.example`):

   ```
   ANTHROPIC_API_KEY=sk-ant-...
   ```

   The API key is required for AI-powered conversation summarization.
   Without it the pipeline still runs but only performs triage (junk
   filtering) -- no summaries, action items, or topic extraction.

---

## Quick Start

```bash
# 1. Add your first Gmail account
python -m poc add-account

# 2. Run the pipeline (sync + process + display)
python -m poc
```

On first run the OAuth flow opens a browser window.  Sign in with the
Google account you want to connect and grant read-only access to Gmail
and Contacts.

---

## CLI Commands

The pipeline is invoked as `python -m poc` with optional subcommands.

### `run` (default)

```bash
python -m poc
python -m poc run
```

Processes **all registered accounts** in sequence:

1. Authenticates each account (loads saved token, refreshes if expired).
2. Syncs contacts from Google People API.
3. Runs an initial or incremental email sync depending on whether the
   account has been synced before.
4. Triages conversations (filters out automated/marketing mail).
5. Summarizes remaining conversations with Claude (if API key is set).
6. Displays a merged view of all conversations across all accounts.

If any single account fails (auth error, sync error, etc.) the pipeline
logs a warning and continues to the next account.  One bad account never
aborts the entire run.

When multiple accounts are present, each conversation panel includes an
account badge showing which email address it belongs to, and the stats
header lists all active accounts.

### `add-account`

```bash
python -m poc add-account
```

Adds a new Gmail account interactively:

1. Opens a browser for the Google OAuth consent screen.
2. After authorization, determines the account email address.
3. Registers the account in the database.
4. Syncs contacts.
5. Runs an initial email sync.

The OAuth token is saved as `credentials/token_<email>.json` (with `@`
and `.` replaced by `_at_` and `_`).  For example:

```
credentials/token_doug_at_example_com.json
```

If the account is already registered the command prints a message and
exits without making changes.

### `list-accounts`

```bash
python -m poc list-accounts
```

Displays a table of all registered accounts:

| Column         | Description                              |
|----------------|------------------------------------------|
| Email          | The Gmail address                        |
| Provider       | Always `gmail` for now                   |
| Last Synced    | Timestamp of the most recent sync        |
| Initial Sync   | Whether the first full sync has completed|
| Conversations  | Total conversation count for the account |

### `auto-assign`

```bash
python -m poc auto-assign PROJECT [--dry-run] [--include-triaged]
```

Bulk-assigns unassigned conversations to topics within a project based
on tag and title matching.  This is the primary tool for populating the
organizational hierarchy after creating projects and topics.

**Matching algorithm:**

For each unassigned conversation (`topic_id IS NULL`), the system scores
it against every topic in the project:

| Match type | Points | Condition |
|------------|--------|-----------|
| Tag match  | 2 each | Conversation tag name contains the topic name (case-insensitive substring) |
| Title match| 1      | Conversation title contains the topic name (case-insensitive substring) |

The conversation is assigned to the highest-scoring topic.  Ties are
broken alphabetically by topic name.  A minimum score of 1 is required
(at least one match).

**Example:** Topic "Tax", conversation with tags ["tax strategy",
"tax filing"] and title "Tax planning" scores 2x2 + 1 = 5.

**Flags:**

| Flag | Description |
|------|-------------|
| `--dry-run` | Preview assignments without applying them.  Shows a table of what would be assigned. |
| `--include-triaged` | Also consider conversations that were triaged out (marketing, automated).  By default these are excluded. |

**Example workflow:**

```bash
# 1. Create a project and topics
python -m poc create-project "Finance"
python -m poc create-topic "Finance" "Tax"
python -m poc create-topic "Finance" "Budget"
python -m poc create-topic "Finance" "Insurance"

# 2. Preview what would be assigned
python -m poc auto-assign "Finance" --dry-run

# 3. Apply the assignments
python -m poc auto-assign "Finance"

# 4. Verify
python -m poc show-hierarchy
```

### `remove-account`

```bash
python -m poc remove-account user@example.com
```

Removes the specified account and **all associated data**:

- Conversations, emails, recipients, participants, topics, and sync
  log entries are cascade-deleted from the database.
- The account's OAuth token file is deleted from disk.

This is irreversible.  Re-adding the same address later starts fresh
with a new initial sync.

### Organizational Hierarchy Commands

These commands manage the project/topic hierarchy for organizing
conversations.

```bash
# User setup (auto-creates from first provider account)
python -m poc bootstrap-user

# Companies
python -m poc create-company "Company Name" [--domain example.com] [--industry Tech] [--description "..."]
python -m poc list-companies
python -m poc delete-company "Company Name"

# Projects
python -m poc create-project "Project Name" [--parent "Parent"] [--description "..."]
python -m poc list-projects
python -m poc show-project "Project Name"
python -m poc delete-project "Project Name"

# Topics
python -m poc create-topic "Project Name" "Topic Name" [--description "..."]
python -m poc list-topics "Project Name"
python -m poc delete-topic "Project Name" "Topic Name"

# Manual assignment
python -m poc assign-topic CONVERSATION_ID "Project Name" "Topic Name"
python -m poc unassign-topic CONVERSATION_ID

# Bulk assignment
python -m poc auto-assign "Project Name" [--dry-run] [--include-triaged]

# View hierarchy
python -m poc show-hierarchy
```

Companies track the organizations your contacts belong to.  During
contact sync, company records are auto-created from Google Contacts
organization data.  You can also manage them manually:

- `create-company` — register a company with optional domain and industry
- `list-companies` — display all companies sorted alphabetically
- `delete-company` — remove a company (unlinks any associated contacts)

The typical workflow is:

1. `bootstrap-user` — create a user record from your provider account
2. `create-company` — (optional) pre-create companies before sync
3. `create-project` — create one or more projects
4. `create-topic` — add topics to each project
5. `auto-assign` — bulk-assign conversations by tag/title matching
6. `show-hierarchy` — review the result

### `enrich-company`

```bash
python3 -m poc enrich-company COMPANY_ID [--provider website_scraper]
```

Enriches a company record by scraping its website for metadata.  Requires
the company to have a `domain` or `website` set.

The scraper crawls up to three pages (homepage, /about, /contact) and
extracts:

- **Meta tags** — description from `<meta>` and Open Graph tags
- **Schema.org JSON-LD** — description, founding date, employee count,
  address, social links
- **Social profiles** — LinkedIn, Twitter/X, Facebook, Instagram, YouTube,
  GitHub
- **Contact info** — phone numbers, email addresses

Discovered fields are stored in the `enrichment_runs` / `enrichment_field_values`
audit trail, then applied to the company record if confidence >= 0.7.  Existing
values at a higher trust tier (e.g., manual edits) are not overwritten.

**Flags:**

| Flag | Description |
|------|-------------|
| `--provider NAME` | Provider to use (default: `website_scraper`).  Currently the only available provider. |

### `serve`

```bash
python3 -m poc serve [--host 127.0.0.1] [--port 8000]
```

Launches the web UI (FastAPI + HTMX + PicoCSS).  The web UI provides
a browser-based interface for all CRM data:

- **Dashboard** — overview counts (conversations, contacts, companies,
  projects, topics, events) and recent conversations.
- **Conversations** — browse, search, filter by status/topic, view
  detail with messages and participants.
- **Contacts** — search by name/email/company, view detail with
  conversations and relationships.
- **Companies** — create, search, delete, view contacts and
  relationships.  Domain-based contact linking on creation.
  Enrich button on company detail fetches metadata from the
  company's website.
- **Projects / Topics** — create projects and topics, auto-assign
  conversations by tag/title matching.
- **Relationships** — browse inferred and manual relationships, run
  inference, manage relationship types.
- **Events** — browse, search, filter by type, create events, view
  detail with participants and linked conversations.

---

## Pipeline Stages

Each `run` executes five stages per account.  Understanding what each
stage does helps interpret the output.

### Stage 1 -- Authentication

Loads the saved OAuth token for the account.  If the token has expired
it is refreshed automatically.  If the token is missing or invalid a
browser-based OAuth flow is launched.

### Stage 2 -- Contact Sync

Fetches your Google Contacts via the People API and stores them in a
shared `contacts` table.  These contacts are used later to identify
which conversation participants are people you know (vs. unknown
addresses).  Contacts are global -- shared across all accounts.

### Stage 3 -- Email Sync

**Initial sync** (first run for an account): fetches Gmail threads
matching the configured query (default: `newer_than:7d`), stores every
message and builds conversation records.

**Incremental sync** (subsequent runs): uses Gmail's `historyId` cursor
to fetch only messages added or deleted since the last sync.  This is
fast and avoids re-downloading everything.

### Stage 3a -- Email Body Cleanup

Before triage, each email body is stripped of quoted replies, forwarded
blocks, signatures, and boilerplate.  This uses a dual-track architecture:

1. **HTML track** (preferred) -- when an HTML body is available,
   structural elements (Gmail quote divs, Outlook separators, signature
   containers) are removed at the DOM level using BeautifulSoup and
   quotequail, then text-level cleanup handles anything that leaked
   through.
2. **Plain-text track** (fallback) -- when HTML is absent or the HTML
   track fails, a regex-based pipeline handles quote detection,
   forwarded headers, Outlook separators, and attribution lines.

Both tracks share a common set of text-level cleanups:

- Mobile/app signatures ("Sent from my iPhone", etc.)
- Separator-based signatures (`--` and `____` patterns)
- Valediction-based signatures (Best regards + name/contact block)
- Standalone signatures (name/title/phone without a valediction)
- Promotional content (social links, vCards, awards)
- Newsletter unsubscribe footers
- Confidentiality and environmental notices
- Hard-wrapped line rejoining

For full algorithmic detail, see `docs/email_stripping.md`.

### Stage 4 -- Processing (Triage + Summarization)

Conversations that have not yet been processed go through two steps:

1. **Triage** -- heuristic filters remove junk:
   - No known contacts among participants
   - Automated sender patterns (noreply, mailer-daemon, etc.)
   - Automated subject patterns (receipts, confirmations, etc.)
   - Marketing content indicators

2. **Summarization** -- conversations that pass triage are sent to
   Claude, which returns:
   - A status assessment: **OPEN** (needs action), **CLOSED**
     (resolved), or **UNCERTAIN**
   - A plain-English summary
   - Action items (if any)
   - Key topics

### Stage 5 -- Display

All conversations from all accounts are merged into a single view,
sorted by status:

- **OPEN** conversations (red) -- shown first, these need attention
- **CLOSED** conversations (green) -- resolved, shown for reference
- **UNCERTAIN** conversations (yellow) -- ambiguous status

Each conversation panel shows:

- Status badge and subject line
- Account badge (when multiple accounts are registered)
- Summary text
- Participants (with contact names resolved where possible)
- Message count and date range
- Action items
- Key topics
- Full conversation text (each message with timestamp and sender)

A triage summary table shows how many threads were filtered and why.

---

## Configuration

All settings are loaded from environment variables.  Place them in the
`.env` file in the project root.

| Variable                     | Default                    | Description                                     |
|------------------------------|----------------------------|-------------------------------------------------|
| `ANTHROPIC_API_KEY`          | *(none)*                   | Required for summarization                      |
| `POC_GMAIL_QUERY`            | `newer_than:7d`            | Gmail search query for initial sync             |
| `POC_GMAIL_MAX_THREADS`      | `50`                       | Max threads fetched per batch                   |
| `POC_TARGET_CONVERSATIONS`   | `5`                        | Target number of conversations passing triage   |
| `POC_CLAUDE_MODEL`           | `claude-sonnet-4-20250514` | Claude model used for summarization             |
| `POC_GMAIL_RATE_LIMIT`       | `5`                        | Gmail API requests per second                   |
| `POC_CLAUDE_RATE_LIMIT`      | `2`                        | Claude API requests per second                  |
| `POC_MAX_CONVERSATION_CHARS` | `6000`                     | Max conversation characters sent to Claude      |
| `POC_DB_PATH`                | `data/crm_extender.db`     | SQLite database location                        |

---

## File Layout

```
CRMExtender/
  credentials/
    client_secret.json            # OAuth client secret (you provide)
    token_<email>.json            # Per-account OAuth tokens (auto-created)
  data/
    crm_extender.db               # SQLite database (auto-created)
  poc/
    __main__.py                   # CLI entry point and subcommands
    auth.py                       # OAuth flow and token management
    auto_assign.py                # Bulk auto-assign conversations to topics
    config.py                     # Environment-based configuration
    contact_matcher.py            # Contact matching logic
    contacts_client.py            # Google People API client
    conversation_builder.py       # Groups emails into conversations
    database.py                   # SQLite connection and schema
    display.py                    # Rich terminal output
    email_parser.py               # Quote/signature stripping (plain-text track)
    html_email_parser.py          # HTML-aware quote/signature stripping
    gmail_client.py               # Gmail API client
    enrichment_provider.py        # Enrichment provider interface and registry
    enrichment_pipeline.py        # Enrichment orchestration and conflict resolution
    hierarchy.py                  # Company/project/topic/assignment data access
    models.py                     # Core dataclasses
    rate_limiter.py               # Token-bucket rate limiter
    relationship_inference.py     # Contact relationship inference
    relationship_types.py         # Relationship type CRUD
    summarizer.py                 # Claude AI summarization
    sync.py                       # Sync orchestration
    triage.py                     # Heuristic junk filtering
    website_scraper.py            # Website scraper enrichment provider
    audit_parser.py               # Audit tool: compare old vs new parsing
    migrate_strip_boilerplate.py  # Migration: re-strip stored emails
    migrate_refetch_emails.py     # Migration: re-fetch emails from Gmail
    migrate_to_v2.py              # Migration: v1 to v2 schema
    migrate_to_v3.py              # Migration: v2 to v3 schema (companies + audit)
    migrate_to_v4.py              # Migration: v3 to v4 (relationship types)
    migrate_to_v5.py              # Migration: v4 to v5 (bidirectional relationships)
    migrate_to_v6.py              # Migration: v5 to v6 (events)
    migrate_to_v7.py              # Migration: v6 to v7 (company intelligence)
    web/                          # Web UI (FastAPI + HTMX)
      app.py                      # Application factory
      routes/                     # Route modules
        dashboard.py              # Dashboard route
        conversations.py          # Conversation routes
        contacts.py               # Contact routes
        companies.py              # Company routes
        projects.py               # Project/topic routes
        relationships.py          # Relationship routes
        events.py                 # Event routes
      templates/                  # Jinja2 templates
      static/                     # CSS and static assets
  .env                            # Environment variables (you create)
  .env.example                    # Template for .env
```

---

## Multi-Account Workflows

### Adding a second account

```bash
python -m poc add-account
# Browser opens -- sign in with a different Google account
# Initial sync runs automatically
```

### Viewing all accounts

```bash
python -m poc list-accounts
```

```
       Registered Accounts
┌──────────────────────┬──────────┬─────────────────────┬──────────────┬───────────────┐
│ Email                │ Provider │ Last Synced          │ Initial Sync │ Conversations │
├──────────────────────┼──────────┼─────────────────────┼──────────────┼───────────────┤
│ doug@example.com     │ gmail    │ 2026-02-05 14:30:00 │     Yes      │            12 │
│ work@company.com     │ gmail    │ 2026-02-05 14:30:15 │     Yes      │             8 │
└──────────────────────┴──────────┴─────────────────────┴──────────────┴───────────────┘
```

### Running with multiple accounts

```bash
python -m poc run
```

Output processes each account in sequence, then shows a merged display:

```
Found 2 account(s).

--- doug@example.com ---
  Synced 142 contacts.
  Incremental sync: 3 fetched, 3 stored, 1 new, 1 updated.
  2 triaged out, 1 summarized, 3 topics extracted.

--- work@company.com ---
  Synced 89 contacts.
  Incremental sync: 5 fetched, 5 stored, 2 new, 0 updated.
  1 triaged out, 2 summarized, 4 topics extracted.

──── Gmail Conversation Summary ────

Accounts:       doug@example.com, work@company.com
Total:          5
Open:           2
Closed:         2
Uncertain:      1
```

Each conversation panel title includes the account email in parentheses
when multiple accounts are active.

### Removing an account

```bash
python -m poc remove-account work@company.com
```

This deletes all data for that account.  Subsequent runs process only
the remaining accounts.  With a single account left, account badges are
no longer shown in the display.

---

## Migration from Single-Account Setup

If you were using the pipeline before multi-account support was added,
your existing setup migrates automatically:

1. The old `credentials/token.json` is detected on the next run.
2. The pipeline determines the email address from the token, copies it
   to `credentials/token_<email>.json`, and updates the database to
   point to the new path.
3. The old `credentials/token.json` is left in place (not deleted).
4. No manual steps are required.

---

## Maintenance Tools

### Audit Parser

Compares the current parsing pipeline against stored email bodies to
identify improvements or regressions without modifying data.

```bash
python3 -m poc.audit_parser
```

Reports:
- Total emails processed
- Number and percentage where the new pipeline produces different output
- Average character reduction percentage
- Count of emails where the new pipeline produces an empty result

Use `--show-diffs N` to display side-by-side differences for the first
N changed emails (useful for spot-checking).

### Migration: Re-strip Boilerplate

After updating the parsing pipeline, re-processes all stored email
bodies through the new pipeline and updates the database in place.

```bash
python3 -m poc.migrate_strip_boilerplate
```

This is safe to run multiple times -- it always re-processes from the
original `body_text` and `body_html` fields stored at sync time.
**Back up the database before running** (copy `data/crm_extender.db`).

### Migration: Re-fetch Emails

Re-downloads email bodies from Gmail for all stored emails.  Useful if
the original sync missed HTML bodies or if the Gmail API format changed.

```bash
python3 -m poc.migrate_refetch_emails
```

Requires valid OAuth tokens for the relevant accounts.

### Migration: v1 to v2 Schema

Migrates the database from the original 8-table email-only schema to the
21-table multi-channel design.  See `poc/migrate_to_v2.py` for details.

```bash
python3 -m poc.migrate_to_v2 --dry-run   # Preview on a backup copy
python3 -m poc.migrate_to_v2              # Apply to production
```

### Migration: v2 to v3 Schema

Adds the `companies` table, `company_id` foreign key on contacts, and
`created_by`/`updated_by` audit columns on contacts, contact_identifiers,
conversations, projects, and topics.  Backfills company records from
existing `contacts.company` values.

```bash
python3 -m poc.migrate_to_v3 --dry-run   # Preview on a backup copy
python3 -m poc.migrate_to_v3              # Apply to production
```

### Migration: v3 to v4 Schema

Adds the `relationship_types` table with a foreign key from `relationships`,
and seeds 6 default types (KNOWS, EMPLOYEE, REPORTS_TO, WORKS_WITH, PARTNER,
VENDOR).

```bash
python3 -m poc.migrate_to_v4 --dry-run
python3 -m poc.migrate_to_v4
```

### Migration: v4 to v5 Schema

Adds `is_bidirectional` to `relationship_types` and
`paired_relationship_id` to `relationships` for bidirectional relationship
support.

```bash
python3 -m poc.migrate_to_v5 --dry-run
python3 -m poc.migrate_to_v5
```

### Migration: v5 to v6 Schema

Adds the events system: `events`, `event_participants`, and
`event_conversations` tables for calendar tracking.

```bash
python3 -m poc.migrate_to_v6 --dry-run
python3 -m poc.migrate_to_v6
```

### Migration: v6 to v7 Schema

Adds company intelligence tables: `company_identifiers`,
`company_hierarchy`, `company_merges`, `company_social_profiles`,
`contact_social_profiles`, `enrichment_runs`, `enrichment_field_values`,
`entity_scores`, `monitoring_preferences`, `entity_assets`, `addresses`,
`phone_numbers`, `email_addresses`.  Also adds new columns to
`companies` (website, stock_symbol, size_range, employee_count,
founded_year, revenue_range, funding_total, funding_stage,
headquarters_location).

```bash
python3 -m poc.migrate_to_v7 --dry-run
python3 -m poc.migrate_to_v7
```

All migration scripts create a timestamped backup before making changes
and support `--db PATH` to target a specific database file.

---

## Troubleshooting

### "OAuth client secret not found"

Download `client_secret.json` from Google Cloud Console and place it in
the `credentials/` directory.  See
[Google's guide](https://developers.google.com/identity/protocols/oauth2)
for creating OAuth credentials.

### "No accounts registered"

Run `python -m poc add-account` before running `python -m poc`.

### Authentication fails for one account

The pipeline logs a warning and continues processing other accounts.
Check that the token file exists and that the Google account still has
the app authorized.  Re-running `add-account` with the same email will
refresh the token.

### Triage filters everything out

All conversations were classified as automated or marketing mail.  Try
widening the time window:

```
POC_GMAIL_QUERY=newer_than:30d
```

Or increase the thread batch size:

```
POC_GMAIL_MAX_THREADS=100
```

### Summaries missing (triage only)

Set `ANTHROPIC_API_KEY` in your `.env` file.  Without it the pipeline
runs triage but skips AI summarization.

### Incremental sync finds nothing

Gmail's history API only reports changes since the last sync cursor.
If no new mail arrived since the previous run, this is expected.
