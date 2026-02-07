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
    config.py                     # Environment-based configuration
    contact_matcher.py            # Contact matching logic
    contacts_client.py            # Google People API client
    conversation_builder.py       # Groups emails into conversations
    database.py                   # SQLite connection and schema
    display.py                    # Rich terminal output
    email_parser.py               # Quote/signature stripping (plain-text track)
    html_email_parser.py          # HTML-aware quote/signature stripping
    gmail_client.py               # Gmail API client
    models.py                     # Core dataclasses
    rate_limiter.py               # Token-bucket rate limiter
    summarizer.py                 # Claude AI summarization
    sync.py                       # Sync orchestration
    triage.py                     # Heuristic junk filtering
    audit_parser.py               # Audit tool: compare old vs new parsing
    migrate_strip_boilerplate.py  # Migration: re-strip stored emails
    migrate_refetch_emails.py     # Migration: re-fetch emails from Gmail
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
