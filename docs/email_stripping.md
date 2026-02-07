# Email Boilerplate Stripping

This document describes how the email parsing pipeline in `poc/email_parser.py` removes quoted replies, forwarded content, signatures, and other boilerplate from email bodies to extract the core message content.

## Overview

The `strip_quotes()` function implements a multi-step pipeline that progressively removes different types of non-essential content from emails. The goal is to extract only the original message content written by the sender, excluding:

- Quoted replies from previous emails
- Forwarded message content
- Mobile device signatures
- Corporate signature blocks
- Legal disclaimers and confidentiality notices
- Environmental printing messages

## Pipeline Steps

### Step 1: Standard Quote Detection

Uses the `mail-parser-reply` library for initial quote removal. This library handles common quoting patterns like:

- Lines prefixed with `>`
- Gmail-style quoted blocks
- Standard reply formatting

```python
reply_parser = EmailReplyParser()
cleaned = reply_parser.parse_reply(body)
```

If the library fails or returns empty content, the original body is preserved for subsequent processing.

### Step 2: Forwarded Message Headers

Removes forwarded message blocks starting with separator lines:

```
-- Forwarded message --
From: someone@example.com
Subject: Original subject
...
```

**Pattern:** `^-{2,}\s*Forwarded message\s*-{2,}\s*$`

Everything from this line onward is truncated.

### Step 3: Outlook-Style Separators

Removes content after Outlook-style separators:

```
__________
From: John Smith
Sent: Monday, January 1, 2024 9:00 AM
To: Jane Doe
```

**Patterns:**
- Lines of 10+ underscores: `^_{10,}\s*$`
- Lines of 10+ dashes: `^-{10,}\s*$`
- From/Sent/To header blocks

### Step 4: "On ... wrote:" Blocks

Catches reply attribution lines that `mail-parser-reply` might miss:

```
On Mon, Jan 1, 2024 at 9:00 AM John Smith wrote:
```

**Pattern:** `^On\s+.{10,80}\s+wrote:\s*$`

### Step 5: Mobile Signatures

Removes common mobile device signatures:

- "Sent from my iPhone"
- "Sent from my iPad"
- "Sent from my Galaxy"
- "Sent from my Android"
- "Sent from my Pixel"
- "Sent from my BlackBerry"
- "Get Outlook for iOS"
- "Get Outlook for Android"
- "Sent from Yahoo Mail"
- "Sent from Mail for Windows"

### Step 5.1: Confidentiality Notices

Removes legal disclaimers and confidentiality notices. When any of these patterns are detected, everything from that line onward is removed:

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

### Step 5.2: Environmental Messages

Removes environmental/printing messages:

- "Please consider the environment before printing this email"
- "Think before you print"
- "Save a tree"
- "Go green"
- "Don't print this email"

### Step 5.3: Signature Block Detection

This step uses a two-phase approach to avoid false positives:

#### Phase 1: Find Valediction

Detects common closing phrases that indicate the start of a signature:

| Valediction | Variations |
|-------------|------------|
| Regards | "Regards,", "Best regards,", "Kind regards,", "Warm regards," |
| Thanks | "Thanks,", "Many thanks,", "Thank you," |
| Sincerely | "Sincerely,", "Yours sincerely," |
| Best | "Best,", "Best wishes,", "All the best," |
| Other | "Cheers,", "Take care,", "Respectfully,", "Yours truly,", "Yours faithfully," |

#### Phase 2: Validate Signature Content

After finding a valediction, the algorithm checks the content that follows. It only removes the signature block if ALL of these conditions are met:

1. **Has signature markers** - Contains patterns typical of signatures:
   - Phone numbers: `Tel: +1 (555) 123-4567`
   - Email addresses: `john.doe@example.com`
   - URLs: `www.example.com` or `https://...`
   - Organization indicators: `Corp.`, `Inc.`, `LLC`, `Ltd.`, `University`, `Department`
   - Job titles: `Director`, `Manager`, `Engineer`, `VP`, `CEO`, `Professor`, etc.

2. **Is short** - The content after the valediction is less than 500 characters or fewer than 10 lines

3. **No substantive sentences** - The content doesn't contain full sentences (4+ words ending in punctuation on a single line)

This two-phase approach prevents false positives where someone writes "Thanks, let me know if you have questions" mid-email.

### Step 6: Line Unwrapping

Plain text emails often have hard line breaks at 70-80 characters due to email client formatting or RFC 2822 compliance. This step joins these artificially broken lines back into natural paragraphs.

**How it works:**
1. Groups consecutive non-empty lines into paragraphs
2. Joins lines within each paragraph with spaces
3. Preserves intentional breaks:
   - Empty lines (paragraph separators)
   - List items (lines starting with `-`, `*`, `•`, or numbers like `1.`)
   - Signature separators (`--`)
   - Field labels (lines matching `Label: value` pattern)

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

### Step 7: Whitespace Cleanup

Collapses excessive blank lines (3+ consecutive newlines) down to double newlines for consistent formatting.

## Example

**Input:**
```
Hi Team,

The quarterly review is scheduled for Tuesday at 2pm.

Best regards,
Jennifer Wilson
Chief Operating Officer
Acme Corporation
Tel: +1 (555) 999-8888
jennifer.wilson@acmecorp.com

CONFIDENTIALITY NOTICE: This e-mail message is for the sole use of
the intended recipient(s) and may contain confidential information.

Please consider the environment before printing this email.

-- Forwarded message --
From: someone@example.com
Subject: Previous discussion
...
```

**Output:**
```
Hi Team,

The quarterly review is scheduled for Tuesday at 2pm.
```

## Pattern Reference

All patterns use the `re.MULTILINE` flag to match `^` and `$` at line boundaries, and `re.IGNORECASE` for case-insensitive matching.

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

## Testing

The test suites cover both pipelines:

**`tests/test_email_parser.py`** — Plain-text pipeline:
- **Regression tests**: Verify existing functionality still works
- **Confidentiality notices**: 10 variations of legal disclaimers
- **Environmental messages**: 4 common patterns
- **Signature blocks**: 6 variations with different markers
- **Edge cases**: 5 tests for false positive prevention
- **Combined boilerplate**: 3 tests with multiple boilerplate types
- **Real-world examples**: 3 comprehensive email samples

**`tests/test_html_email_parser.py`** — HTML-aware pipeline:
- **Gmail quote stripping**: `div.gmail_quote`, `div.gmail_quote_container`, `blockquote.gmail_quote`
- **Gmail signature stripping**: `div.gmail_signature`, `data-smartmail` attribute
- **Outlook quote stripping**: `div#appendonsend`, `div#divRplyFwdMsg`, border-top separator
- **Outlook signature stripping**: `div#Signature`
- **Apple Mail quote stripping**: `blockquote[type=cite]`
- **Yahoo quote stripping**: `div.yahoo_quoted`
- **Fallback behavior**: empty/malformed HTML falls back to plain-text pipeline
- **Text cleanup integration**: mobile sigs and disclaimers in HTML-extracted text

Run tests with:
```bash
pytest tests/ -v
```

## Limitations

1. **Language**: Patterns are English-only. Non-English valedictions and disclaimers won't be detected.

2. **Custom signatures**: Unusual signature formats without standard markers may not be detected.

3. **Inline signatures**: In plain-text mode, if someone signs off mid-email and continues writing, the detection may incorrectly truncate (mitigated by sentence detection). The HTML track avoids this by relying on structural elements.

## HTML-Aware Processing

When an HTML body is available (`body_html` parameter), `strip_quotes()` uses an HTML-first pipeline that leverages structural cues for far more accurate stripping. This is implemented in `poc/html_email_parser.py`.

### HTML Pipeline

```
strip_quotes(body, body_html)
│
├─ HTML available? ──YES──> HTML Track
│                           1. quotequail.quote_html() → remove quoted regions
│                           2. BeautifulSoup: remove structural elements (see below)
│                           3. soup.get_text() → convert to plain text
│                           4. Lightweight text cleanup (mobile sigs, disclaimers,
│                              line unwrapping, whitespace)
│                           5. Return result
│
└─ No HTML ──────> Plain Text Track (existing pipeline, unchanged)
```

### Structural Elements Removed

| Selector | Source | Purpose |
|----------|--------|---------|
| `div.gmail_quote` | Gmail | Quoted reply container |
| `div.gmail_quote_container` | Gmail | Alternate quote container |
| `div.gmail_extra` | Gmail | Extra content after reply |
| `blockquote.gmail_quote` | Gmail | Blockquote-style quote |
| `div.gmail_signature` | Gmail | Signature block |
| `[data-smartmail=gmail_signature]` | Gmail | Smart signature |
| `div.yahoo_quoted` | Yahoo | Quoted content |
| `blockquote[type=cite]` | Apple Mail | Cited content |
| `div#appendonsend` | Outlook | Reply separator |
| `div#divRplyFwdMsg` | Outlook | Reply/forward header |
| `div#Signature` | Outlook | Signature block |
| `border-top:solid #E1E1E1` (style) | Outlook | Horizontal separator |

### Dependencies

- `quotequail>=0.4.0` — HTML quote/reply detection (by Close.io)
- `beautifulsoup4>=4.12.0` — HTML parsing for structural removal
- `lxml>=5.0.0` — Fast HTML parser backend

### Audit Tool

Before running migrations with the new pipeline, use the audit tool to compare results:

```bash
python -m poc.audit_parser [--limit N] [--show-diffs N]
```

This processes all stored emails through both pipelines and reports differences, character reduction, and potential over-stripping.

## Future Improvements

Potential enhancements:

- Multi-language support for valedictions and disclaimers
- Machine learning-based signature detection
- Configurable pattern sets per organization
