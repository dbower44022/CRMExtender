# Email Boilerplate Stripping

This document describes how the email parsing pipeline removes quoted replies, forwarded content, signatures, and other boilerplate from email bodies to extract the core message content.

**Implementation files:**

| File | Role |
|------|------|
| `poc/email_parser.py` | Main entry point (`strip_quotes()`), text-level patterns and stripping functions |
| `poc/html_email_parser.py` | HTML-aware stripping engine (`strip_html_quotes()`) |

---

## Architecture Overview

The system uses a **dual-track architecture**: an HTML-first track that leverages structural cues (CSS classes, element IDs, DOM hierarchy) for high-accuracy stripping, with a plain-text fallback track for emails without HTML bodies.

Both tracks share a common set of text-level cleanup functions for signature detection, disclaimer removal, and footer stripping.

```
strip_quotes(body, body_html)
│
├─ HTML available? ──YES──> HTML Track
│                           1. quotequail: semantic quote detection
│                           2. BeautifulSoup: structural element removal
│                              a. Quote selectors (gmail_quote, yahoo_quoted, etc.)
│                              b. Signature selectors (gmail_signature, #Signature)
│                                 ↳ Resilience: if removal empties result, re-parse
│                                    without signature removal
│                              c. Cutoff markers (#appendonsend, #divRplyFwdMsg)
│                              d. Outlook border-top separators
│                              e. Unsubscribe footer elements
│                           3. soup.get_text() → convert to plain text
│                           4. Text-level cleanup (shared with plain-text track):
│                              - Mobile/notification signatures
│                              - Confidentiality notices
│                              - Environmental messages
│                              - Dash-dash (--) signature separators
│                              - Underscore (____) signature separators
│                              - Valediction-based signature blocks
│                              - Standalone signature detection
│                              - Promotional content (social links, awards, vcards)
│                              - Unsubscribe footers (text-level fallback)
│                              - Line unwrapping
│                              - Whitespace normalization
│                           5. Return result (or fall through if empty)
│
└─ No HTML ──────> Plain-Text Track
                    1. mail-parser-reply: standard quote detection
                    2. Forwarded message headers
                    3. Outlook-style separators (10+ underscores/dashes)
                    4. "On ... wrote:" attribution lines
                    5–7. Same text-level cleanup as HTML track step 4
                    8. Line unwrapping
                    9. Whitespace normalization
```

---

## HTML Track (`poc/html_email_parser.py`)

### Step 1: Semantic Quote Detection (quotequail)

The `quotequail` library analyzes the HTML structure to identify quoted regions semantically. It returns a list of `(is_reply, html_chunk)` tuples where `is_reply=True` indicates author-written content.

```python
parts = quotequail.quote_html(html)
# [(True, '<div>My reply</div>'), (False, '<blockquote>Quoted text</blockquote>')]
```

Only the first reply block is kept. If quotequail fails or returns nothing, the raw HTML is used as-is.

### Step 2: Structural Element Removal (BeautifulSoup)

After quotequail processing, BeautifulSoup parses the HTML and removes elements by CSS selector. Elements are processed in this order:

#### 2a. Quoted Content Containers

These elements are always removed entirely via `el.decompose()`:

| Selector | Client | Purpose |
|----------|--------|---------|
| `div.gmail_quote` | Gmail | Primary quoted reply container |
| `div.gmail_quote_container` | Gmail | Alternate quote container |
| `div.gmail_extra` | Gmail | Extra content after reply |
| `blockquote.gmail_quote` | Gmail | Blockquote-style quote |
| `div.yahoo_quoted` | Yahoo | Quoted content |
| `blockquote[type=cite]` | Apple Mail | Cited content |

#### 2b. Signature Containers (with Resilience Check)

Signature elements are removed, but with a critical safety check: some email clients (notably Gmail) wrap the **entire message body** inside a `gmail_signature` div. When this happens, removing the signature element would empty the result entirely.

**Detection algorithm:**

1. Collect all elements matching signature selectors.
2. Remove them all via `decompose()`.
3. Check if any text remains: `soup.get_text(strip=True)`.
4. If the result is empty, **re-parse** the HTML from scratch and only remove quote selectors (not signatures). The signature content is then left for text-level cleanup functions (valediction detection, underscore separator handling, etc.) to strip the actual signature while preserving the message body.

| Selector | Client | Purpose |
|----------|--------|---------|
| `div.gmail_signature` | Gmail | Signature block |
| `[data-smartmail=gmail_signature]` | Gmail | Smart signature attribute |
| `div#Signature` | Outlook | Signature block |

**Why this matters:** In production data, approximately 10% of emails from certain Gmail senders had their entire body wrapped inside a signature div. Without this resilience check, those emails would produce empty results and fall through to the plain-text fallback, losing the benefits of HTML-structural quote removal.

#### 2c. Cutoff Markers (Sibling Removal)

These elements act as **separators** — the element itself AND all following siblings in the DOM tree are removed. This is different from quote/signature removal which only removes the matched element and its children.

| Selector | Client | Purpose |
|----------|--------|---------|
| `div#appendonsend` | Outlook | Reply insertion point |
| `div#divRplyFwdMsg` | Outlook | Reply/forward header |

**Algorithm:** For each matched element, iterate `el.find_next_siblings()`, decompose each sibling, then decompose the marker element itself.

#### 2d. Outlook Border-Top Separators

Outlook uses inline CSS to create horizontal separator lines between the reply and quoted content:

```html
<div style="border-top:solid #E1E1E1 1.0pt; padding:3.0pt 0in 0in 0in">
```

**Detection:** Regex `border-top\s*:\s*solid\s+#E1E1E1` is matched against the `style` attribute of every element. The first match and all following siblings are removed.

#### 2e. Unsubscribe Footer Removal

Newsletter and marketing email footers are removed using two strategies:

**Strategy 1 — ID-based:** Elements with IDs matching the regex `^footerUnsubscribe` (case-insensitive) are found. The matched element and all following siblings are removed.

**Strategy 2 — Text-based:** Elements containing the word "unsubscribe" in their text content are found. The algorithm walks up the DOM tree (up to 5 levels) to find a block-level container (`div`, `td`, `p`, `tr`, `table`), then removes that container and all following siblings. Only the first match is processed — this prevents over-stripping when "unsubscribe" appears in message body content before the actual footer.

**Safety guard:** If the walk-up reaches the `<body>` element, the removal is skipped to avoid stripping the entire document.

### Step 3: Text Extraction

The cleaned DOM is converted to plain text via `soup.get_text(separator="\n", strip=True)`, which joins text nodes with newlines and strips whitespace from each node.

---

## Text-Level Cleanup (Shared by Both Tracks)

After the HTML track extracts plain text (or in the plain-text track after quote/separator removal), a series of text-level cleanup functions run. These are defined in `poc/email_parser.py` and called in order.

### Mobile and Notification Signatures

**Function:** `_MOBILE_SIGNATURE` regex, applied via `re.sub()`

Removes device-generated and notification signatures. The pattern matches these on their own line (case-insensitive):

| Pattern | Example |
|---------|---------|
| `Sent from my <device>` | "Sent from my iPhone", "Sent from my Galaxy" |
| `Get Outlook for <platform>` | "Get Outlook for iOS", "Get Outlook for Android" |
| `Sent from Yahoo Mail` | "Sent from Yahoo Mail" |
| `Sent from Mail for Windows` | "Sent from Mail for Windows" |
| `This email was sent from a notification...address` | "This email was sent from a notification-only address", "This email was sent from a notification email address", "This email was sent from a notification-only email address" |

**Regex:** `^(Sent from my (iPhone|iPad|Galaxy|Android|Pixel|BlackBerry)|Get Outlook for (iOS|Android)|Sent from Yahoo Mail|Sent from Mail for Windows|This email was sent from a notification[\-\s]*(?:only\s+)?(?:email\s+)?address)\s*$`

**Supported devices:** iPhone, iPad, Galaxy, Android, Pixel, BlackBerry

### Confidentiality Notices

**Pattern:** `_CONFIDENTIAL_NOTICE` regex

When any of these patterns are detected on a line, **everything from that line onward** is truncated. This is a "find-and-truncate" approach — once a disclaimer starts, nothing after it is real message content.

| Pattern | Example |
|---------|---------|
| `confidential notice` | "CONFIDENTIAL NOTICE: This email..." |
| `confidential and privileged` | "This message is confidential and privileged" |
| `intended for` + recipient | "This email is intended only for the addressee" |
| `if you are not the intended` | "If you are not the intended recipient..." |
| `notify the sender` | "Please notify the sender immediately" |
| `delete this email` | "Please delete this email and any copies" |
| `disclosure prohibited` | "Unauthorized disclosure is strictly prohibited" |
| `unauthorized use` | "Unauthorized use of this information..." |
| `may contain confidential` | "This email may contain confidential information" |
| `this email is confidential` | "This e-mail and any attachments are confidential" |

### Environmental Messages

**Pattern:** `_ENVIRONMENTAL_MESSAGE` regex

Same truncation behavior as confidentiality notices.

| Pattern | Example |
|---------|---------|
| `consider the environment` | "Please consider the environment before printing this email" |
| `think before you print` | "Think before you print" |
| `save a tree` | "Save a tree - don't print this email" |
| `go green` | "Go green - avoid printing" |
| `don't print` | "Don't print this email" |

### Dash-Dash Signature Separator (`--`)

**Function:** `_strip_dash_dash_signature(body)`

The `--` separator (from RFC 3676 `-- \n` convention) is commonly used to delimit signatures in plain-text email. However, `--` can also appear as a markdown section divider or decorative element, so naive truncation would cause false positives.

**Detection algorithm:**

1. Find the first line matching `^--\s*$` (two dashes, optional trailing whitespace, on its own line).
2. If nothing follows the `--`, strip it as a trailing separator.
3. If content follows, apply **heuristic validation**:
   - **Length check:** Content after `--` must be < 500 characters AND <= 10 lines. If longer, it's likely real content (a section break), not a signature. Skip.
   - **Signature marker check:** The content after `--` is scanned for signature indicators (phone numbers, email addresses, URLs, job titles, organization names, professional credentials).
   - **Name line check:** The first non-empty line after `--` is checked against the name-line patterns (`_NAME_LINE` for mixed-case names like "John Smith", `_CAPS_NAME_LINE` for all-caps names like "ROBIN BAUM, CPA").
4. If the content is short AND has signature markers or starts with a name, truncate everything from `--` onward.
5. Otherwise, preserve the `--` and content (it's a section divider).

**Why the conservative thresholds:** In production data, `--` followed by >10 lines of content was always a section divider, never a signature. The 500-char / 10-line threshold was tuned against 3,752 emails with zero false positives.

### Underscore Signature Separator (`____`)

**Function:** `_strip_underscore_signature(body)`

Some email clients (notably Gmail when composing with signature templates) use a line of 2-9 underscores as a signature separator. This is distinct from the Outlook separator which uses 10+ underscores.

**Detection algorithm:**

1. Find the first line matching `^_{2,9}\s*$` (2 to 9 underscores on their own line).
2. If nothing follows, strip the separator.
3. If content follows, apply heuristic validation:
   - **Length check:** Content must be < 1,500 characters AND <= 25 lines. This is **more generous** than the `--` handler because short underscore lines are a more reliable signature signal — they rarely appear as section dividers in message body text.
   - **Signature marker check:** Same as `--` handler (phone, email, URL, title, credentials).
   - **Name line check:** Same as `--` handler.
4. If the content is short AND has signature markers or starts with a name, truncate.

**Non-overlapping with Outlook separators:** The regex `_{2,9}` specifically avoids matching lines of 10+ underscores, which are handled by the Outlook separator pattern (`_OUTLOOK_SEPARATOR`). This prevents double-processing.

**Chained execution:** The `--` and `____` handlers are designed to work together. Some signatures use both separators:

```
Best, Sharon

--

____

Sharon Rose
SCORE Cleveland Co-Chair
Email:sharon.rose@scorevolunteer.org
```

In this case:
1. `_strip_dash_dash_signature` runs first but skips because the content after `--` (which includes `____` and the full signature) exceeds the 500-char threshold.
2. `_strip_underscore_signature` runs and finds `____` with signature markers after it — truncates from `____` onward.
3. `_strip_dash_dash_signature` runs **a second time** to clean up the now-trailing `--` (which has nothing after it).

This produces the clean result: `"Best, Sharon"`.

### Valediction-Based Signature Block Detection

**Function:** `_strip_signature_block(body)`

Detects corporate signature blocks that follow a standard valediction (closing phrase). Uses a two-phase approach to avoid false positives.

#### Phase 1: Find Valediction

Scans for common closing phrases on their own line:

| Valediction | Variations |
|-------------|------------|
| Regards | "Regards,", "Best regards,", "Kind regards,", "Warm regards," |
| Thanks | "Thanks,", "Many thanks,", "Thank you," |
| Sincerely | "Sincerely,", "Yours sincerely,", "Yours faithfully," |
| Best | "Best,", "Best wishes,", "All the best," |
| Other | "Cheers,", "Take care,", "Respectfully,", "Yours truly," |

**Regex:** Matches these at the start of a line with optional leading whitespace and optional trailing comma. The valediction must be on its own line — "Thanks, let me know" mid-sentence will NOT match.

#### Phase 2: Validate Signature Content

After finding a valediction, the algorithm checks the content that follows to determine if it's a signature or continuation of the message. The signature is only removed if ALL of these conditions are met:

1. **Has signature markers** — The content contains at least one of:
   - Phone numbers with labels: `Tel: +1 (555) 123-4567`, `Mobile: 555-1234`
   - Email addresses: `john.doe@example.com`
   - URLs: `www.example.com`, `https://...`
   - Organization names: `Corp.`, `Inc.`, `LLC`, `Ltd.`, `University`, `Department`
   - Job titles: `Director`, `Manager`, `Engineer`, `VP`, `CEO`, `Professor`, `Partner`, `Advisor`, `Consultant`, `Specialist`, `Coordinator`, `Administrator`, `Assistant`
   - Professional credentials: `CFP`, `CPA`, `CFA`, `MBA`, `JD`, `PhD`, `MD`, `Esq`, `PMP`, `CPWA`, `ChFC`, `CLU`, `RICP`, `AIF`, `CAIA`

2. **Is reasonably short** — The content after the valediction is < 1,500 characters OR <= 15 lines. Corporate signatures with name + title + multiple phone numbers + disclaimer can be quite long.

3. **No substantive sentences** — The content doesn't contain full sentences (4+ words starting with a capital letter and ending with `.` `!` `?` on a single line). However, certain sentence patterns that commonly appear in signatures are excluded from this check:
   - "Tax or legal guidance" disclaimers
   - "Consult your CPA/attorney/advisor"
   - "Click here to..." / "Book time with..."
   - "Please let me know if you have..."
   - "Thank you for..."
   - "As discussed..."
   - NMLS identifiers
   - "Looking forward to..."

**Why the sentence check matters:** Without it, a valediction like "Regards," followed by a follow-up paragraph ("Actually, one more thing — can you send me the updated schedule?") would be incorrectly truncated. The sentence detection catches this and preserves the content.

### Standalone Signature Detection

**Function:** `_strip_standalone_signature(body)`

Detects signatures that appear WITHOUT a standard valediction. This handles cases like:

```
Please review the attached.

ROBIN BAUM, CPA
Director of Finance
Phone: 555-000-1111
```

**Detection algorithm** (scans lines top-to-bottom, first match wins):

1. **Embedded image markers** (`[cid:...]`): These are strong signature indicators (company logos, headshot images). When found, the algorithm looks back up to 3 lines for a name line and truncates from there.

2. **All-caps name with credentials** (e.g., `ROBIN BAUM, CPA`): Matches `_CAPS_NAME_LINE` pattern. If the next 5 lines contain signature markers (phone, email, URL, title), truncates from the name line.

3. **Mixed-case name followed by title** (e.g., `John Smith\nDirector of Operations`): Matches `_NAME_LINE` pattern. If the next 4 lines contain a job title keyword or signature markers, truncates from the name line. Requires at least 20 characters of message content before the name to avoid stripping emails that are entirely a name/contact block.

**Name line patterns:**

| Pattern | Regex | Example |
|---------|-------|---------|
| Mixed-case name | `^[A-Z][a-z]+(\s+[A-Z]\.?)?(\s+[A-Z][a-z]+){1,3}$` | "John Smith", "Jane A. Doe", "John Michael Smith" |
| All-caps name | `^[A-Z]{2,}(\s+[A-Z]\.?)?(\s+[A-Z]{2,}){1,3}$` | "JOHN SMITH", "ROBIN BAUM" |
| With credentials | Appended: `(,?\s*(CFP|CPA|...)®?\s*)*` | "John Smith, CFP", "ROBIN BAUM, CPA" |

### Promotional Content Detection

**Function:** `_strip_promotional_content(body)`

Removes promotional content commonly found at the end of signatures. Each pattern triggers truncation from that point onward.

| Pattern | What It Catches | Example |
|---------|----------------|---------|
| `_SOCIAL_LINKS` | Social media link blocks | "Follow us on LinkedIn \<url\>", "Connect with me on LinkedIn" |
| `_VCARD_PATTERN` | VCard download and secure file links | "Download my VCard", "Click Here to send files securely" |
| `_AWARDS_PATTERN` | Industry award/ranking mentions | "Named to the 2024 Forbes Best-In-State", "Source: Forbes" |
| `_EMBEDDED_IMAGE` | Remaining embedded image markers | `[cid:image001.png@...]` |

### Unsubscribe Footer (Text-Level)

**Function:** `_strip_unsubscribe_footer(body)`

A text-level fallback for newsletter footers that weren't caught by the HTML-level handler. Finds the first line containing the word "unsubscribe" (case-insensitive) and truncates everything from that line onward.

**Regex:** `^.*unsubscribe.*$` with `re.MULTILINE | re.IGNORECASE`

This is intentionally aggressive because any email containing "unsubscribe" in its footer is almost certainly a newsletter/marketing email where the footer content is not valuable.

### Line Unwrapping

**Function:** `_unwrap_lines(body)`

Plain-text emails often have hard line breaks at 70-80 characters due to email client formatting or RFC 2822 compliance. This function joins artificially broken lines back into natural paragraphs.

**Algorithm:**

1. Groups consecutive non-empty lines into paragraphs.
2. Joins lines within each paragraph with spaces.
3. Preserves intentional breaks:
   - Empty lines (paragraph separators)
   - List items (lines starting with `-`, `*`, `\u2022`, or numbers like `1.`)
   - Signature separators (`--`)
   - Field labels (lines matching `Label: value` pattern)
4. Detects paragraph boundaries at sentence endings: a line ending with `.` `!` `?` followed by a line starting with a capital letter is treated as a paragraph break even without an empty line between them.

**Before:**
```
As many of you know, we have had the privilege of serving the SCORE
Cleveland chapter for the past five years for Sharon and fifteen years for
Anita. During that time, we worked side by side with you to build a chapter
grounded in collaboration, mutual respect, and a shared commitment.
```

**After:**
```
As many of you know, we have had the privilege of serving the SCORE Cleveland chapter for the past five years for Sharon and fifteen years for Anita. During that time, we worked side by side with you to build a chapter grounded in collaboration, mutual respect, and a shared commitment.
```

### Whitespace Normalization

Collapses 3+ consecutive newlines down to 2 for consistent formatting: `re.sub(r"\n{3,}", "\n\n", text)`

---

## Plain-Text Track (Fallback)

When no HTML body is available (or the HTML track produces an empty result), the plain-text track runs. It includes additional steps that the HTML track handles structurally:

### Step 1: Standard Quote Detection (mail-parser-reply)

The `EmailReplyParser` library detects standard quoted-reply blocks (lines prefixed with `>`, Gmail-style formatting, etc.). If it fails, the original body is preserved.

### Step 2: Forwarded Message Headers

Removes content after forwarded message separator lines.

**Pattern:** `^-{2,}\s*Forwarded message\s*-{2,}\s*$`

### Step 3: Outlook-Style Separators

Removes content after Outlook-style separators:

| Pattern | Example |
|---------|---------|
| `^_{10,}\s*$` | `__________` (10+ underscores) |
| `^-{10,}\s*$` | `----------` (10+ dashes) |
| `From:/Sent:/To:` block | `From: John Smith\nSent: Monday...\nTo: Jane Doe` |

### Step 4: "On ... wrote:" Attribution

Catches reply attribution lines that mail-parser-reply might miss.

**Pattern:** `^On\s+.{10,80}\s+wrote:\s*$`

### Steps 5-9: Shared Text-Level Cleanup

Same functions as the HTML track text cleanup (mobile signatures through whitespace normalization), described above.

---

## Complete Processing Example

**Input email:**
```
Hi Team,

The quarterly review is scheduled for Tuesday at 2pm.

Best regards,
Jennifer Wilson
Chief Operating Officer
Acme Corporation
Tel: +1 (555) 999-8888
jennifer.wilson@acmecorp.com

____

Jennifer Wilson
SCORE Cleveland Co-Chair
Email:jennifer.wilson@scorevolunteer.org

CONFIDENTIALITY NOTICE: This e-mail message is for the sole use of
the intended recipient(s) and may contain confidential information.

Please consider the environment before printing this email.

-- Forwarded message --
From: someone@example.com
Subject: Previous discussion
...
```

**Processing steps (HTML track):**

1. quotequail removes quoted regions
2. BeautifulSoup removes structural quotes/signatures
3. Text extraction produces the remaining content
4. Confidentiality notice detection truncates from "CONFIDENTIALITY NOTICE" onward (but valediction handler runs first)
5. Valediction handler finds "Best regards," + signature markers (Tel, email, title) → truncates from "Best regards,"
6. Result: only the message body remains

**Output:**
```
Hi Team,

The quarterly review is scheduled for Tuesday at 2pm.
```

---

## Pattern Reference

All patterns use `re.MULTILINE` to match `^` and `$` at line boundaries, and `re.IGNORECASE` for case-insensitive matching (except `_NAME_LINE` which is case-sensitive by design to detect proper name capitalization).

### Key Regex Components

| Component | Meaning |
|-----------|---------|
| `^` | Start of line (with MULTILINE) |
| `$` | End of line (with MULTILINE) |
| `\s` | Whitespace (space, tab, newline) |
| `[ \t]` | Space or tab only (not newline) |
| `(?:...)` | Non-capturing group |
| `(?:...\|...)` | Alternation (OR) |
| `.*` | Any characters (greedy) |
| `.+` | One or more characters |
| `\w+` | Word characters |

---

## Testing

95 tests across two test files:

**`tests/test_email_parser.py`** (60 tests) — Plain-text pipeline and shared functions:

| Category | Count | What's Tested |
|----------|-------|---------------|
| Regression / basic | 6 | Empty input, unchanged text, forwarded messages, mobile sigs, whitespace |
| Confidentiality notices | 10 | 10 variations of legal disclaimers |
| Environmental messages | 4 | Common "don't print" patterns |
| Valediction signatures | 6 | Phone, email, title, URL, sincerely, thank you |
| Signature edge cases | 5 | Mid-email valedictions, follow-up content, long content |
| Combined boilerplate | 3 | Multiple boilerplate types in one email |
| Line unwrapping | 6 | Hard-wrapped paragraphs, lists, dash-dash, multi-paragraph |
| Real-world examples | 3 | Corporate emails, simple professional, forwarded with disclaimer |
| Notification signatures | 3 | "Sent from a notification-only address" variants |
| Dash-dash signatures | 6 | Name, contact info, full sig, long content, markdown divider, trailing |
| Underscore signatures | 5 | Name, full sig, contact info, long non-sig, `--` then `____` combo |
| Unsubscribe footers | 3 | Plain, with trailing content, case-insensitive |

**`tests/test_html_email_parser.py`** (35 tests) — HTML-aware pipeline:

| Category | Count | What's Tested |
|----------|-------|---------------|
| Gmail quote stripping | 4 | `gmail_quote`, `gmail_quote_container`, `gmail_extra`, `blockquote.gmail_quote` |
| Gmail signature stripping | 2 | `gmail_signature`, `data-smartmail` |
| Outlook quote stripping | 3 | `#appendonsend`, `#divRplyFwdMsg`, border-top separator |
| Outlook signature stripping | 1 | `div#Signature` |
| Apple Mail quotes | 1 | `blockquote[type=cite]` |
| Yahoo quotes | 1 | `div.yahoo_quoted` |
| Fallback behavior | 4 | Empty HTML, None HTML, whitespace-only, HTML producing empty text |
| Text cleanup integration | 3 | Mobile sigs, confidentiality, environmental in HTML-extracted text |
| Full integration | 3 | HTML preferred, Gmail full email, backward compatibility |
| HTML unsubscribe footers | 4 | ID-based, text-in-div, table cell, paragraph |
| HTML track signature detection | 6 | Valediction in HTML, standalone name, promotional, dash-dash, underscore, unsubscribe |
| Body-inside-signature resilience | 3 | Body inside `gmail_signature`, normal sig still removed, `data-smartmail` wrapping |

Run tests with:
```bash
python3 -m pytest tests/ -v
```

---

## Audit Tool

Before running migrations with updated stripping logic, use the audit tool to compare results:

```bash
python3 -m poc.audit_parser [--limit N] [--show-diffs N]
```

This processes all stored emails through both the old (text-only) and new (HTML-aware) pipelines and reports:

- Total emails processed
- Number/percentage of results that changed
- Character reduction percentage
- Empty results (potential over-stripping)
- Top N most-changed emails with unified diffs

### Migration Tool

Once audit results are satisfactory, apply the updated stripping to all stored emails:

```bash
python3 -m poc.migrate_strip_boilerplate
```

This re-processes every email's `body_text` through `strip_quotes()` with the `body_html` parameter for HTML-aware stripping. **Back up the database before running** — the migration overwrites `body_text` in place.

---

## Dependencies

| Package | Version | Used By |
|---------|---------|---------|
| `mail-parser-reply` | >= 0.1.2 | Plain-text quote detection |
| `quotequail` | >= 0.4.0 | HTML quote/reply detection |
| `beautifulsoup4` | >= 4.12.0 | HTML parsing for structural removal |
| `lxml` | >= 5.0.0 | Fast HTML parser backend |

---

## Performance

Measured against a production dataset of 3,752 emails:

| Metric | Value |
|--------|-------|
| Emails with changes | 3,420 (91.2%) |
| Average character reduction | 58.0% |
| New empty results introduced | 0 |
| Processing time (full audit) | ~5 seconds |

---

## Limitations

1. **Language**: All patterns are English-only. Non-English valedictions, disclaimers, and signature markers are not detected.

2. **Custom separators**: Unusual signature formats without standard markers (no phone, no email, no title, no credentials) may not be detected. The system requires at least one signature indicator for validation.

3. **Image-only emails**: Emails where the entire message is an embedded image (e.g., holiday greeting cards) will produce empty results because there is no text content to preserve.

4. **Idempotency gap**: Running `strip_quotes()` a second time on already-processed text may produce slightly different results (~3.7% of emails) due to line unwrapping interacting differently with previously processed text. This is cosmetic, not a loss of content.

---

## Future Improvements

- Multi-language support for valedictions and disclaimers
- Machine learning-based signature detection
- Configurable pattern sets per organization
- Attachment-aware processing (detect image-only emails)
