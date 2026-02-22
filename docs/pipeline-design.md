# Email Conversation Pipeline -- Design Document

This document describes how the CRM Extender PoC processes Gmail
conversations, from authentication through final display.  Each section
maps to a pipeline stage and names the exact modules, functions, and
data structures involved.

---

## Pipeline Overview

```
  Step 1          Step 2             Step 3 (loop)                Step 4         Step 5
  ──────          ──────          ─────────────────              ──────          ──────
  Auth     -->   Contacts   -->  Fetch / Build / Triage  -->   Summarize  -->  Display
                                   (repeat until target)
```

The pipeline is orchestrated by `poc/__main__.py : main()`.  Steps 1
and 2 run once.  Step 3 runs in a loop, fetching batches of Gmail
threads and filtering them, until `TARGET_CONVERSATIONS` (default 5)
pass triage or no more threads remain.  Steps 4 and 5 operate on the
accumulated results.

---

## Data Models (`poc/models.py`)

All data flows through a small set of dataclasses defined in
`poc/models.py`.  These are the core structures every other module
reads or writes.

### ParsedEmail

A single email message, parsed from the Gmail API.

| Field          | Type        | Source                             |
| -------------- | ----------- | ---------------------------------- |
| `message_id`   | `str`       | Gmail message ID                   |
| `thread_id`    | `str`       | Gmail thread ID                    |
| `subject`      | `str`       | Decoded `Subject` header           |
| `sender`       | `str`       | Display form, e.g. `"Name <addr>"` |
| `sender_email` | `str`       | Bare address, lowercased           |
| `recipients`   | `list[str]` | `To` addresses                     |
| `cc`           | `list[str]` | `Cc` addresses                     |
| `date`         | `datetime   | None`                              |
| `body_plain`   | `str`       | Plain-text body                    |
| `body_html`    | `str`       | Raw HTML body                      |
| `snippet`      | `str`       | Gmail snippet (preview text)       |

Property `all_participants` returns a deduplicated list of every email
address involved (sender + recipients + cc), lowercased.

### Conversation

A group of emails sharing one Gmail `threadId`.

| Field              | Type                      | Notes                          |
| ------------------ | ------------------------- | ------------------------------ |
| `thread_id`        | `str`                     | Gmail thread ID                |
| `subject`          | `str`                     | From the first email           |
| `emails`           | `list[ParsedEmail]`       | Chronological (ascending)      |
| `participants`     | `list[str]`               | Unique addresses across thread |
| `matched_contacts` | `dict[str, KnownContact]` | Populated by contact matcher   |

Properties: `message_count`, `date_range` (earliest, latest).

### KnownContact

A contact from the Google People API.

| Field           | Type  | Notes                                 |
| --------------- | ----- | ------------------------------------- |
| `email`         | `str` | Lowercased address                    |
| `name`          | `str` | Display name from Google Contacts     |
| `resource_name` | `str` | Google People API resource identifier |

### ConversationSummary

The output of Claude summarization for one conversation.

| Field          | Type                 | Notes                        |
| -------------- | -------------------- | ---------------------------- |
| `thread_id`    | `str`                | Links back to `Conversation` |
| `status`       | `ConversationStatus` | OPEN, CLOSED, or UNCERTAIN   |
| `summary`      | `str`                | 2-4 sentence summary         |
| `action_items` | `list[str]`          | Things someone needs to do   |
| `key_topics`   | `list[str]`          | 2-5 short topic phrases      |
| `error`        | `str                 | None`                        |

### Enums

- **ConversationStatus**: `OPEN`, `CLOSED`, `UNCERTAIN`
- **FilterReason**: `NO_KNOWN_CONTACTS`, `AUTOMATED_SENDER`,
  `AUTOMATED_SUBJECT`, `MARKETING`

### TriageResult

Records why a conversation was filtered: `thread_id`, `subject`,
`reason` (a `FilterReason`).

---

## Step 1: Authentication (`poc/auth.py`)

**Function**: `get_credentials() -> Credentials`

Handles Google OAuth 2.0 with token persistence.

1. Attempts to load a saved token from `credentials/token.json`.
2. If the token exists but is expired, refreshes it via
   `creds.refresh(Request())`.
3. If no valid token is available, checks for
   `credentials/client_secret.json` and runs the OAuth desktop flow
   (`InstalledAppFlow.run_local_server`).
4. Persists the new token for subsequent runs.

The authenticated user's email is retrieved separately by
`gmail_client.get_user_email(creds)`, which calls the Gmail
`users.getProfile` endpoint.

### Scopes

Defined in `config.GOOGLE_SCOPES`:

- `gmail.readonly` -- read email threads
- `contacts.readonly` -- read Google Contacts

---

## Step 2: Contact Fetching & Indexing

### Fetching (`poc/contacts_client.py`)

**Function**: `fetch_contacts(creds, rate_limiter) -> list[KnownContact]`

Pages through the Google People API (`people.connections.list`),
requesting `names` and `emailAddresses` fields.  Each person may have
multiple email addresses; one `KnownContact` is created per address.

### Indexing (`poc/contact_matcher.py`)

**Function**: `build_contact_index(contacts) -> dict[str, KnownContact]`

Builds a case-insensitive `email -> KnownContact` lookup dictionary.
When multiple contacts share an address, the first one wins.

---

## Step 3: Batch Fetch, Build, and Triage (Loop)

This step repeats in a loop.  Each iteration fetches a batch of Gmail
threads, converts them to conversations, enriches them with contact
data, and triages.  Conversations that pass triage accumulate until
`TARGET_CONVERSATIONS` is reached or Gmail runs out of matching threads.

### 3a. Fetch Gmail Threads (`poc/gmail_client.py`)

**Function**: `fetch_threads(creds, query, max_threads, rate_limiter, page_token) -> (threads, next_page_token)`

Two-phase fetch:

1. **List thread IDs** -- pages through `threads.list` using the
   configured query (default `newer_than:7d`) until `max_threads` IDs
   are collected or no more pages remain.
2. **Fetch full thread data** -- for each thread ID, calls
   `threads.get(format="full")` and parses every message.

Each message is parsed by `_parse_message(msg) -> ParsedEmail`:

- Headers are decoded via `_decode_header_value` (RFC 2047).
- Sender is extracted by `_parse_email_address` into display name +
  bare address.
- Recipients and CC are extracted by `_parse_address_list`.
- Date is parsed from the `Date` header, with fallback to Gmail's
  `internalDate` (milliseconds since epoch).
- Body is extracted by `_decode_body`, which walks the MIME payload tree
  recursively, collecting the first `text/plain` and first `text/html`
  part.

**HTML-to-text fallback**: when an email has no `text/plain` part,
`_html_to_text(html) -> str` converts the HTML body.  This uses seven
compiled regex passes:

1. Strip `<style>` and `<script>` blocks and their contents.
2. Strip HTML comments (`<!-- ... -->`).
3. Convert `<br>` tags to newlines.
4. Insert newlines at block-level element boundaries (`<p>`, `<div>`,
   `<tr>`, `<li>`, `<h1>`-`<h6>`, etc.).
5. Strip all remaining HTML tags.
6. Decode HTML entities (`&nbsp;`, `&ndash;`, `&#8212;`, etc.) via
   `html.unescape`.
7. Collapse whitespace: runs of spaces become single spaces (preserving
   newlines), and three-or-more consecutive newlines become two.

Each thread's emails are returned sorted by date ascending.  The
function also returns the Gmail `nextPageToken` so the orchestrator can
continue fetching.

### 3b. Build Conversations (`poc/conversation_builder.py`)

**Function**: `build_conversations(threads) -> list[Conversation]`

For each thread (a `list[ParsedEmail]`):

1. **Strip quoted text** from every email body by calling
   `strip_quotes()` (see below).
2. **Collect participants** by merging `all_participants` across every
   email in the thread, deduplicating by insertion order.
3. **Create a `Conversation`** with the thread ID, subject (from the
   first email), cleaned emails, and participant list.

The resulting conversations are sorted newest-first (by the date of the
last email in each thread).

#### Quote Stripping (`poc/email_parser.py` + `poc/html_email_parser.py`)

**Function**: `strip_quotes(body, body_html=None) -> str`

A dual-track pipeline that removes quoted replies, forwarded blocks,
signatures, and boilerplate.  When an HTML body is available the HTML
track runs first; if it produces an empty result or fails, the
plain-text track handles it.

##### HTML Track (preferred)

Activated when `body_html` is non-empty.  Uses two phases:

**Phase 1 -- HTML structural removal** (`strip_html_quotes()` in
`html_email_parser.py`):

1. **quotequail** -- the quotequail library parses the HTML and
   identifies quoted vs. authored regions.  Only the first authored
   block is kept.
2. **CSS-selector removal** -- BeautifulSoup removes elements matching
   known quote containers (`div.gmail_quote`, `div.yahoo_quoted`,
   `blockquote[type=cite]`, etc.) and signature containers
   (`div.gmail_signature`, `[data-smartmail=gmail_signature]`,
   `div#Signature`).
3. **Signature resilience check** -- if removing signature elements
   empties the result (Gmail sometimes wraps the entire body inside a
   `gmail_signature` div), the HTML is re-parsed with quote removal
   only, preserving the body content.
4. **Cutoff markers** -- Outlook `div#appendonsend` and
   `div#divRplyFwdMsg` elements plus all their following siblings are
   removed.
5. **Outlook border separators** -- elements with inline
   `border-top: solid #E1E1E1` style are detected and everything from
   that element onward is removed.
6. **Unsubscribe footers** -- elements with IDs matching
   `footerUnsubscribe*` and elements containing "unsubscribe" text are
   removed along with all following siblings.
7. **Text extraction** -- `soup.get_text(separator="\n", strip=True)`.

**Phase 2 -- Text-level cleanup** (back in `email_parser.py`):

1. **Mobile signatures** -- regex strips "Sent from my iPhone",
   "Get Outlook for iOS", "Sent from Yahoo Mail", notification-only
   address lines, etc.
2. **Confidentiality notices** -- regex detects "This message contains
   confidential information" and truncates.
3. **Environmental messages** -- regex detects "Please consider the
   environment before printing" and truncates.
4. **Separator-based signature stripping** -- three-pass chain:
   - `_strip_dash_dash_signature()` -- finds `^--\s*$` and truncates
     when remaining content is <500 chars / ≤10 lines and contains
     signature markers or a name line.
   - `_strip_underscore_signature()` -- finds `^_{2,9}$` and truncates
     when remaining content is <1500 chars / ≤25 lines and contains
     signature markers.
   - `_strip_dash_dash_signature()` again -- cleanup pass to catch `--`
     exposed after underscore stripping.
5. **Valediction-based signature detection** -- `_strip_signature_block()`
   finds valedictions (Best regards, Thanks, etc.) followed by name and
   contact lines, truncating the signature block.
6. **Standalone signature detection** -- `_strip_standalone_signature()`
   finds trailing blocks of name/title/phone/email lines without a
   valediction prefix.
7. **Promotional content** -- `_strip_promotional_content()` removes
   trailing social-media links, vCards, awards, and marketing taglines.
8. **Unsubscribe footers** -- text-level fallback finds lines containing
   "unsubscribe" and truncates from that point.
9. **Line unwrapping** -- rejoins hard-wrapped lines (common in
   plain-text conversions of HTML emails).
10. **Whitespace cleanup** -- collapses three-or-more consecutive
    newlines into two.

If the HTML track produces an empty result after all cleanup, the
pipeline falls through to the plain-text track.

##### Plain-Text Track (fallback)

Used when `body_html` is absent or the HTML track fails:

1. **mail-parser-reply** -- the `EmailReplyParser` library detects
   standard quoted-reply blocks.  If it fails (malformed input), the
   function falls back to regex-only cleaning.
2. **Forwarded headers** -- regex matches `-- Forwarded message --` and
   truncates everything after it.
3. **Outlook separators** -- regex matches lines of 10+ underscores or
   dashes, and the `From:/Sent:/To:` block pattern.  Everything after
   is truncated.
4. **"On ... wrote:"** -- regex matches the `On <date> <person> wrote:`
   attribution line and truncates after it.
5. **Mobile signatures** -- same regex as HTML track.
6. **Notification signatures** -- "This email was sent from a
   notification-only address" variants.
7. **Separator-based signatures** -- same three-pass `--`/`____`/`--`
   chain as the HTML track.
8. **Valediction, standalone, promotional detection** -- same functions
   as the HTML track.
9. **Confidentiality and environmental notices** -- same as HTML track.
10. **Unsubscribe footers** -- same text-level removal.
11. **Line unwrapping and whitespace cleanup** -- same as HTML track.

See `docs/email_stripping.md` for exhaustive algorithmic detail on every
detection heuristic, including thresholds, regex patterns, and
false-positive prevention strategies.

### 3c. Match Contacts (`poc/contact_matcher.py`)

**Function**: `match_contacts(conversations, contact_index) -> None`

Mutates conversations in place.  For each participant email in each
conversation, looks it up in the contact index.  Matches are stored in
`conv.matched_contacts` (a dict mapping email address to
`KnownContact`).

### 3d. Triage (`poc/triage.py`)

**Function**: `triage_conversations(conversations, user_email) -> (kept, filtered)`

A two-layer filter that runs entirely on local data (no API calls):

**Layer 1 -- Heuristic junk detection** (checked in order, first match
wins):

| Check                    | Function                | What it catches                                                                                          |
| ------------------------ | ----------------------- | -------------------------------------------------------------------------------------------------------- |
| Automated sender address | `_is_automated_sender`  | `noreply@`, `donotreply@`, `notification@`, `billing@`, `alerts@`, etc. (16 patterns)                    |
| Automated subject line   | `_is_automated_subject` | "out of office", "automatic reply", "delivery status notification", "password reset", etc. (12 patterns) |
| Marketing content        | `_is_marketing`         | Any email body containing "unsubscribe"                                                                  |

**Layer 2 -- Known-contact gate**:

| Check             | Function             | Rule                                                                                      |
| ----------------- | -------------------- | ----------------------------------------------------------------------------------------- |
| Has known contact | `_has_known_contact` | At least one participant (excluding the authenticated user) must be in `matched_contacts` |

Conversations that pass both layers are added to the `kept` list.
Filtered conversations are recorded as `TriageResult` objects with the
reason.

### Loop Control

The orchestrator in `__main__.py` accumulates `kept` conversations
across batches.  After each batch it checks:

- If `len(kept) >= TARGET_CONVERSATIONS` -- stop, trim to target.
- If `next_page_token` is `None` -- Gmail has no more threads, stop.
- Otherwise -- fetch the next batch using the page token.

---

## Step 4: Summarization (`poc/summarizer.py`)

### Entry Point

**Function**: `summarize_all(conversations, user_email, rate_limiter) -> list[ConversationSummary]`

If `ANTHROPIC_API_KEY` is not set, returns placeholder summaries with an
error note.  Otherwise, creates an `anthropic.Anthropic` client and
calls `summarize_conversation` for each conversation sequentially.

### Per-Conversation Summarization

**Function**: `summarize_conversation(conv, client, user_email, rate_limiter) -> ConversationSummary`

1. **Format the thread** via `_format_thread_for_prompt(conv)`.
2. **Build the system prompt** from a template, injecting `user_email`
   and today's date.
3. **Call Claude** (`messages.create`) with `max_tokens=512`.
4. **Parse the JSON response**, handling markdown code fences if present.
5. **Return a `ConversationSummary`**, or an error-state summary on
   failure.

### Thread Formatting for Prompt

**Function**: `_format_thread_for_prompt(conv) -> str`

Each email is formatted as:

```
From: <sender>
Date: <YYYY-MM-DD HH:MM>

<body_plain or snippet or "(no content)">
```

Emails are joined with `---` separators, prefixed by the subject line.

**Truncation strategy** (threshold: `MAX_CONVERSATION_CHARS`, default
6000):

- If the full text fits, use it as-is.
- If 5 or fewer emails, keep all but truncate each body proportionally.
- If more than 5 emails, include the first 2 and last 3, noting the
  number of omitted middle messages.
- Final safety truncation if the result still exceeds the limit.

### System Prompt

The system prompt instructs Claude to:

1. Write a 2-4 sentence summary.
2. Classify the conversation status from the user's perspective:
   - **OPEN** -- unanswered questions, pending tasks, mentioned
     follow-ups, ongoing multi-message exchanges between known contacts.
     Biased toward OPEN: casual sign-offs like "sounds good" or "talk
     soon" do not close a conversation.
   - **CLOSED** -- question fully answered, explicit goodbye with
     nothing outstanding, or one-way notification with no reply expected.
   - **UNCERTAIN** -- not enough context.
3. List action items.
4. List 2-5 key topics.

Response format is JSON:
`{"status", "summary", "action_items", "key_topics"}`.

### Error Handling

- `JSONDecodeError` from Claude's response: returns a summary with the
  error recorded in `error`.
- Any other API exception: same treatment.
- Neither case halts the pipeline; other conversations continue.

---

## Step 5: Display (`poc/display.py`)

### Triage Statistics

**Function**: `display_triage_stats(filtered) -> None`

Prints a table counting filtered conversations by `FilterReason`.

### Main Results

**Function**: `display_results(conversations, summaries) -> None`

1. Builds a lookup from thread ID to summary and conversation.
2. Groups conversations by status (OPEN, CLOSED, UNCERTAIN).
3. Prints a statistics table (total, open, closed, uncertain, errors).
4. For each status group, prints a section header and calls
   `_display_conversation` for each conversation.

### Conversation Panel

**Function**: `_display_conversation(conv, summary, color) -> None`

Renders a Rich `Panel` with a colored border (red=OPEN, green=CLOSED,
yellow=UNCERTAIN) containing:

1. **Summary** -- the Claude-generated summary text.
2. **Participants** -- formatted by `_format_participant`, which shows
   `"Name (email)"` for matched contacts and bare email otherwise.
3. **Message count** and **date range**.
4. **Action items** -- bulleted list.
5. **Key topics** -- comma-separated.
6. **Error note** -- if summarization failed.
7. **Conversation details** -- the full text of every email in
   chronological order.

The conversation details section uses a dim rule divider labeled
"Conversation", then for each email:

- A dim header line: `Mon DD HH:MM  Sender Name`
- The `body_plain` text, indented 2 spaces

Sender names are resolved by `_format_sender_name`, which prefers the
matched contact name, falls back to the name portion of the `sender`
field (before the `<`), then the raw address.

---

## Rate Limiting (`poc/rate_limiter.py`)

**Class**: `RateLimiter(rate, burst)`

A token-bucket rate limiter used by both the Gmail and Claude API call
paths.

- `rate`: tokens per second (Gmail default 5, Claude default 2).
- `burst`: maximum tokens in the bucket (defaults to `max(1, int(rate))`).
- `acquire()`: blocks until a token is available, sleeping for the
  calculated deficit time if the bucket is empty.
- `_refill()`: adds `elapsed * rate` tokens on each call, capped at
  `burst`.

Two instances are created in `main()`: one for Gmail API calls, one for
Claude API calls.  They are passed through the pipeline to every
function that makes external requests.

---

## Configuration (`poc/config.py`)

All settings are loaded from environment variables (via `.env` file)
with sensible defaults.

| Variable                     | Default                    | Purpose                                   |
| ---------------------------- | -------------------------- | ----------------------------------------- |
| `POC_GMAIL_QUERY`            | `newer_than:7d`            | Gmail search query                        |
| `POC_GMAIL_MAX_THREADS`      | `50`                       | Threads per batch                         |
| `POC_TARGET_CONVERSATIONS`   | `5`                        | Keep fetching until this many pass triage |
| `ANTHROPIC_API_KEY`          | *(none)*                   | Required for summarization                |
| `POC_CLAUDE_MODEL`           | `claude-sonnet-4-20250514` | Claude model ID                           |
| `POC_GMAIL_RATE_LIMIT`       | `5.0`                      | Gmail requests/second                     |
| `POC_CLAUDE_RATE_LIMIT`      | `2.0`                      | Claude requests/second                    |
| `POC_MAX_CONVERSATION_CHARS` | `6000`                     | Max chars sent to Claude per conversation |

Credential paths are derived from the project root:

- `credentials/client_secret.json` -- OAuth client secret
- `credentials/token.json` -- persisted OAuth token

---

## Dependencies

From `pyproject.toml` (Python >= 3.10):

| Package                    | Version  | Used by                       |
| -------------------------- | -------- | ----------------------------- |
| `google-api-python-client` | >= 2.100 | Gmail and People API access   |
| `google-auth-oauthlib`     | >= 1.1   | OAuth 2.0 flow                |
| `google-auth-httplib2`     | >= 0.1.1 | Auth HTTP transport           |
| `anthropic`                | >= 0.39  | Claude API client             |
| `rich`                     | >= 13.7  | Terminal display              |
| `mail-parser-reply`        | >= 0.1.2 | Email quote detection         |
| `python-dotenv`            | >= 1.0   | `.env` file loading           |
| `quotequail`               | >= 0.3   | HTML quote region detection   |
| `beautifulsoup4`           | >= 4.12  | HTML DOM parsing/manipulation |
| `lxml`                     | >= 5.0   | HTML parser backend for BS4   |

---

## Module Dependency Map

```
__main__
  |-- auth              (get_credentials)
  |-- gmail_client      (get_user_email, fetch_threads)
  |-- contacts_client   (fetch_contacts)
  |-- contact_matcher   (build_contact_index, match_contacts)
  |-- conversation_builder (build_conversations)
  |     \-- email_parser   (strip_quotes)
  |           \-- html_email_parser (strip_html_quotes)
  |-- triage            (triage_conversations)
  |-- summarizer        (summarize_all)
  |-- hierarchy         (projects, topics, assignment CRUD)
  |-- auto_assign       (bulk topic assignment by tag/title matching)
  |     \-- database    (get_connection)
  |-- relationship_inference (contact co-occurrence analysis)
  |-- display           (display_triage_stats, display_results,
  |                       display_hierarchy, display_auto_assign_report)
  \-- config            (all settings)

database                (init_db, get_connection — used by sync, hierarchy,
                         auto_assign, relationship_inference)
rate_limiter            (used by gmail_client, contacts_client, summarizer)
models                  (used by every module)
```

---

## Bulk Auto-Assign (`poc/auto_assign.py`)

A standalone pipeline that bulk-assigns unassigned conversations to
topics within a project, based on tag name and conversation title
matching.  This is invoked on demand via the `auto-assign` CLI command,
not as part of the main sync pipeline.

### Entry Point

**Function**: `find_matching_topics(project_id, *, include_triaged=False) -> AutoAssignReport`

### Algorithm

1. **Load topics** for the target project from the `topics` table.
2. **Load candidate conversations** — all conversations where
   `topic_id IS NULL`, optionally excluding those with a non-NULL
   `triage_result`.  Tags are loaded via a `LEFT JOIN` on
   `conversation_tags` / `tags` with `GROUP_CONCAT` to collect all tag
   names per conversation in a single query.
3. **Score each conversation** against each topic using
   `_score_conversation(title, tags, topic_name)`:
   - **Tag match: 2 points each** — tag name contains the topic name
     (case-insensitive substring match).
   - **Title match: 1 point** — conversation title contains the topic
     name (case-insensitive substring match).
   - **Score = `2 × matching_tags + (1 if title_matched)`**
4. **Pick the best topic** per conversation — highest score wins.  Ties
   broken alphabetically by topic name.  Minimum score of 1 required.
5. **Return an `AutoAssignReport`** with match details and summary
   statistics.

### Applying Assignments

**Function**: `apply_assignments(assignments) -> int`

Batch-updates `conversations.topic_id` for each matched conversation.
Returns the count of rows updated.  Idempotent — safe to re-run.

### Data Structures

- **`MatchResult`** — single match: `conversation_id`,
  `conversation_title`, `topic_id`, `topic_name`, `score`,
  `matched_tags`, `title_matched`
- **`AutoAssignReport`** — run summary: `project_name`,
  `total_candidates`, `matched`, `unmatched`, `assignments`

### Display

`display.display_auto_assign_report(report, *, dry_run=False)` renders
the report as a Rich table sorted by score, with summary statistics and
a mode indicator (DRY RUN vs. APPLIED).

### Key SQL (candidates query)

```sql
SELECT c.id, c.title, GROUP_CONCAT(t.name, '||') AS tag_names
FROM conversations c
LEFT JOIN conversation_tags ct ON ct.conversation_id = c.id
LEFT JOIN tags t ON t.id = ct.tag_id
WHERE c.topic_id IS NULL
  AND (c.triage_result IS NULL OR :include_triaged)
GROUP BY c.id
```

---

## Error Handling Summary

| Failure                        | Location               | Recovery                                    |
| ------------------------------ | ---------------------- | ------------------------------------------- |
| Missing `client_secret.json`   | `auth.py`              | `FileNotFoundError` with setup instructions |
| Expired/invalid token          | `auth.py`              | Attempts refresh, then re-runs OAuth flow   |
| Contact fetch failure          | `__main__.py`          | Logs warning, continues with empty contacts |
| Gmail thread fetch failure     | `gmail_client.py`      | Logs warning per thread, skips to next      |
| Message parse failure          | `gmail_client.py`      | Logs warning per message, skips it          |
| HTML track failure             | `email_parser.py`      | Falls back to plain-text pipeline           |
| HTML track empty result        | `email_parser.py`      | Falls back to plain-text pipeline           |
| Signature removal empties HTML | `html_email_parser.py` | Re-parses without signature removal         |
| `quotequail` failure           | `html_email_parser.py` | Continues with raw HTML structural removal  |
| `mail-parser-reply` failure    | `email_parser.py`      | Falls back to regex-only quote stripping    |
| Claude API error               | `summarizer.py`        | Returns summary with `error` field set      |
| Claude JSON parse error        | `summarizer.py`        | Returns summary with `error` field set      |
| No API key                     | `summarizer.py`        | Returns placeholder summaries for all       |
| Project not found              | `auto_assign.py`       | `ValueError` with project name              |
| No topics in project           | `auto_assign.py`       | `ValueError` with project name              |
| No matching conversations      | `auto_assign.py`       | Returns report with `matched=0`             |
