"""Email quote stripping pipeline.

Uses mail-parser-reply for standard quoted content detection,
plus custom patterns for forwarded messages and mobile signatures.

When an HTML body is available, an HTML-first track uses structural
cues (CSS classes, element IDs) for far more accurate stripping,
falling back to the plain-text pipeline when HTML is absent.
"""

from __future__ import annotations

import logging
import re

from mailparser_reply import EmailReplyParser

log = logging.getLogger(__name__)

# Patterns for content we want to strip
_FORWARDED_HEADER = re.compile(
    r"^-{2,}\s*Forwarded message\s*-{2,}\s*$",
    re.MULTILINE | re.IGNORECASE,
)

_MOBILE_SIGNATURE = re.compile(
    r"^(Sent from my (iPhone|iPad|Galaxy|Android|Pixel|BlackBerry)|"
    r"Get Outlook for (iOS|Android)|"
    r"Sent from Yahoo Mail|"
    r"Sent from Mail for Windows|"
    r"This email was sent from a notification[\-\s]*(?:only\s+)?(?:email\s+)?address)\s*$",
    re.MULTILINE | re.IGNORECASE,
)

# Generic "On ... wrote:" pattern that mail-parser-reply might miss
_ON_WROTE = re.compile(
    r"^On\s+.{10,80}\s+wrote:\s*$",
    re.MULTILINE,
)

# Outlook-style separator
_OUTLOOK_SEPARATOR = re.compile(
    r"^_{10,}\s*$|^-{10,}\s*$|^From:\s+.+\nSent:\s+.+\nTo:\s+.+",
    re.MULTILINE,
)

# Confidentiality/legal disclaimer patterns
_CONFIDENTIAL_NOTICE = re.compile(
    r"^.*("
    r"confidential(?:ity)?\s*(?:notice|and\s+privileged)|"
    r"intended\s+(?:only\s+)?for\s+(?:the\s+)?(?:use\s+of\s+)?(?:the\s+)?(?:individual|person|recipient|addressee)|"
    r"if\s+you\s+(?:are\s+)?not\s+(?:the\s+)?intended\s+(?:recipient|addressee)|"
    r"(?:notify|contact)\s+(?:the\s+)?sender\s+immediately|"
    r"delete\s+(?:this\s+)?(?:email|message|e-mail)|"
    r"(?:disclosure|copying|distribution|dissemination)\s+(?:is\s+)?(?:strictly\s+)?prohibited|"
    r"unauthorized\s+(?:use|access|disclosure|review|distribution)|"
    r"may\s+contain\s+(?:confidential|privileged|proprietary)\s+information|"
    r"this\s+e?-?mail\s+.*(?:is\s+|are\s+)?confidential"
    r").*$",
    re.MULTILINE | re.IGNORECASE,
)

# Environmental message patterns
_ENVIRONMENTAL_MESSAGE = re.compile(
    r"^.*(?:"
    r"please\s+(?:consider|think)\s+(?:about\s+)?(?:the\s+)?environment\s+before\s+printing|"
    r"think\s+before\s+(?:you\s+)?print|"
    r"save\s+(?:a\s+)?tree|"
    r"go\s+green|"
    r"don['']?t\s+print\s+(?:this\s+email)?"
    r").*$",
    re.MULTILINE | re.IGNORECASE,
)

# Valediction patterns indicating start of signature block
_VALEDICTION = re.compile(
    r"^[\s]*(?:"
    r"(?:Best\s+)?Regards?|"
    r"Sincerely|"
    r"(?:Many\s+)?Thanks|"
    r"Thank\s+you|"
    r"Cheers|"
    r"Yours\s+(?:truly|sincerely|faithfully)|"
    r"Kind\s+regards?|"
    r"Warm\s+regards?|"
    r"Best\s+wishes?|"
    r"All\s+the\s+best|"
    r"Take\s+care|"
    r"Respectfully|"
    r"Best"  # Standalone "Best" or "Best,"
    r"),?[\s]*$",
    re.MULTILINE | re.IGNORECASE,
)

# Patterns that indicate signature content (not message content)
_SIGNATURE_CONTENT = re.compile(
    r"(?:"
    r"(?:Tel|Phone|Fax|Mobile|Cell|Direct|Office)\s*[:\.]?\s*[\+\d\(\)\-\s]{7,}|"
    r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}|"
    r"(?:www\.|https?://)|"
    r"(?:Dept\.|Department|University|Corp\.|Corporation|Inc\.|LLC|Ltd\.)|"
    r"(?:Professor|Director|Manager|CEO|CTO|CFO|VP|Vice\s+President|President|Engineer|Analyst|"
    r"Partner|Associate|Advisor|Consultant|Specialist|Coordinator|Administrator|Assistant)|"
    r"(?:CFP|CPA|CFA|MBA|JD|PhD|MD|Esq|PMP|CPWA|ChFC|CLU|RICP|AIF|CAIA)®?"  # Professional credentials
    r")",
    re.IGNORECASE,
)

# Embedded image markers (Outlook/Exchange)
_EMBEDDED_IMAGE = re.compile(
    r"\[cid:[^\]]+\]",
    re.IGNORECASE,
)

# Professional credentials after names
_CREDENTIALS = re.compile(
    r"(?:,?\s*(?:CFP|CPA|CFA|MBA|JD|PhD|MD|Esq|PMP|CPWA|ChFC|CLU|RICP|AIF|CAIA)®?\s*)+",
    re.IGNORECASE,
)

# Social media / promotional link blocks
_SOCIAL_LINKS = re.compile(
    r"^.*(?:"
    r"LinkedIn\s*<|Twitter\s*<|Facebook\s*<|Instagram\s*<|"
    r"Follow\s+(?:us|me)\s+(?:on|at)|"
    r"Connect\s+(?:with\s+(?:us|me)|on\s+LinkedIn)"
    r").*$",
    re.MULTILINE | re.IGNORECASE,
)

# VCard and secure file exchange patterns
_VCARD_PATTERN = re.compile(
    r"^.*(?:"
    r"Download\s+(?:my\s+)?VCard|"
    r"(?:Click\s+Here|request\s+a\s+link)\s*<.*>?\s*to\s+send\s+files\s+securely|"
    r"To\s+request\s+a\s+link\s+to\s+send\s+files\s+securely"
    r").*$",
    re.MULTILINE | re.IGNORECASE,
)

# Awards/Rankings promotional text
_AWARDS_PATTERN = re.compile(
    r"^.*(?:"
    r"Named\s+to\s+(?:the\s+)?\d{4}\s+Forbes|"
    r"Forbes\s+(?:Best|Top|America)|"
    r"Ranking\s+Forbes|"
    r"Source:\s*Forbes"
    r").*$",
    re.MULTILINE | re.IGNORECASE,
)

# Standalone signature start - name line with optional credentials
# Matches lines like "John Smith" or "JOHN SMITH, CPA" or "John Smith, CFP®, MBA"
_NAME_LINE = re.compile(
    r"^[\s]*([A-Z][a-z]+(?:\s+[A-Z]\.?)?(?:\s+[A-Z][a-z]+){1,3})"  # Name pattern
    r"(?:,?\s*(?:CFP|CPA|CFA|MBA|JD|PhD|MD|Esq|PMP|CPWA|ChFC|CLU|RICP|AIF|CAIA)®?\s*)*"  # Optional credentials
    r"[\s]*$",
    re.MULTILINE,
)

# All-caps name line (like "ROBIN BAUM, CPA")
_CAPS_NAME_LINE = re.compile(
    r"^[\s]*[A-Z]{2,}(?:\s+[A-Z]\.?)?(?:\s+[A-Z]{2,}){1,3}"  # All caps name
    r"(?:,?\s*(?:CFP|CPA|CFA|MBA|JD|PhD|MD|Esq|PMP|CPWA|ChFC|CLU|RICP|AIF|CAIA)®?\s*)*"  # Optional credentials
    r"[\s]*$",
    re.MULTILINE,
)


def _unwrap_lines(body: str) -> str:
    """Unwrap hard-wrapped lines from plain text emails.

    Email clients often wrap lines at 70-80 characters. This function joins
    lines that were artificially broken, while preserving intentional breaks
    like paragraph separators and list items.

    Key insight: A line ending with terminal punctuation (. ! ?) followed by
    a line starting with a capital letter indicates a paragraph break, even
    without an empty line between them.
    """
    if not body:
        return body

    lines = body.split('\n')
    result = []
    current_paragraph = []

    for i, line in enumerate(lines):
        stripped = line.rstrip()

        # Empty line = paragraph break
        if not stripped:
            if current_paragraph:
                result.append(' '.join(current_paragraph))
                current_paragraph = []
            result.append('')
            continue

        # Check if this is a special line that shouldn't be joined
        is_special_line = (
            stripped.startswith(('-', '*', '•', '>', '|')) or
            re.match(r'^\d+[\.\)]\s', stripped) or  # Numbered list
            stripped.startswith('--') or  # Signature separator
            re.match(r'^[A-Z][a-z]*:\s', stripped)  # Field: value
        )

        # Check if this line starts a new paragraph
        # A new paragraph starts when:
        # 1. Previous line ended with sentence-ending punctuation, AND
        # 2. This line starts with a capital letter
        starts_new_paragraph = False
        if current_paragraph:
            prev_line = current_paragraph[-1]
            prev_ends_sentence = prev_line and prev_line[-1] in '.!?'
            this_starts_capital = stripped and stripped[0].isupper()
            starts_new_paragraph = prev_ends_sentence and this_starts_capital

        # Flush current paragraph if starting a new one
        if (is_special_line or starts_new_paragraph) and current_paragraph:
            result.append(' '.join(current_paragraph))
            current_paragraph = []

        if is_special_line:
            # Special lines go on their own
            result.append(stripped)
        else:
            # Add to current paragraph
            current_paragraph.append(stripped)

    # Flush any remaining paragraph
    if current_paragraph:
        result.append(' '.join(current_paragraph))

    return '\n'.join(result)


def _strip_signature_block(body: str) -> str:
    """Remove signature block if it follows a valediction."""
    valediction_match = _VALEDICTION.search(body)
    if not valediction_match:
        return body

    # Get content after valediction
    after_valediction = body[valediction_match.end():].strip()
    if not after_valediction:
        return body[:valediction_match.start()].rstrip()

    # Check first ~1000 chars or 15 lines for signature indicators
    check_content = after_valediction[:1000]
    lines_after = after_valediction.split('\n')[:15]

    # If remaining content has signature patterns and is reasonably short, truncate
    # Corporate signatures can be quite long (name, titles, contact info, disclaimers)
    has_signature_markers = _SIGNATURE_CONTENT.search(check_content)
    is_short = len(after_valediction) < 1500 or len(lines_after) <= 15

    # Check for substantive sentences - must have verb-like patterns on a single line
    # Exclude URLs, emails, typical signature lines, and disclaimer sentences
    # Look for sentences with 4+ words ending in punctuation (on same line)
    # Use [^\n] to ensure matching within a single line
    has_sentences = False
    sentence_pattern = re.compile(
        r"^[A-Z][a-z]+(?:[ \t]+\w+){3,}[^\n]*[.!?]\s*$",
        re.MULTILINE
    )
    # Patterns that indicate a signature/disclaimer sentence (not real content)
    signature_sentence_patterns = [
        r"(?:tax|legal).*(?:guidance|advice)",  # "tax or legal guidance"
        r"consult\s+(?:your|a)\s+(?:CPA|attorney|advisor|tax)",
        r"(?:click|book)\s+(?:here|time)\s+(?:to|with)",
        r"please\s+let\s+me\s+know\s+if\s+you\s+have",
        r"thank\s+you\s+(?:for|and)",
        r"as\s+discussed",
        r"nmls\s*#?\d+",
        r"looking\s+forward\s+to",
    ]
    signature_sentence_re = re.compile(
        '|'.join(signature_sentence_patterns),
        re.IGNORECASE
    )

    for sent_match in sentence_pattern.finditer(check_content):
        sentence = sent_match.group(0)
        if not signature_sentence_re.search(sentence):
            has_sentences = True
            break

    if has_signature_markers and is_short and not has_sentences:
        return body[:valediction_match.start()].rstrip()

    return body


def _strip_dash_dash_signature(body: str) -> str:
    """Remove signature blocks preceded by a ``-- `` or ``--`` separator.

    Only truncates when the content after ``--`` looks like a signature:
    short (< 500 chars / <= 10 lines) and contains signature markers or
    starts with a name-like line.  This avoids false positives from ``--``
    used as markdown section dividers.
    """
    match = re.search(r"^--\s*$", body, re.MULTILINE)
    if not match:
        return body

    after = body[match.end():].strip()
    if not after:
        # Trailing -- with nothing after it — just strip it
        return body[:match.start()].rstrip()

    lines_after = after.split('\n')
    is_short = len(after) < 500 and len(lines_after) <= 10

    if not is_short:
        return body

    has_sig_markers = _SIGNATURE_CONTENT.search(after)
    first_line = lines_after[0].strip()
    has_name = bool(_NAME_LINE.match(first_line) or _CAPS_NAME_LINE.match(first_line))

    if has_sig_markers or has_name:
        return body[:match.start()].rstrip()

    return body


def _strip_underscore_signature(body: str) -> str:
    """Remove signature blocks preceded by a short underscore separator.

    Matches lines like ``____`` (2–9 underscores on their own line).
    Does NOT overlap with the Outlook separator (10+ underscores).

    Uses a higher threshold than ``_strip_dash_dash_signature`` because
    short underscores are a more reliable signature signal than ``--``.
    """
    match = re.search(r"^_{2,9}\s*$", body, re.MULTILINE)
    if not match:
        return body

    after = body[match.end():].strip()
    if not after:
        return body[:match.start()].rstrip()

    lines_after = after.split('\n')
    is_short = len(after) < 1500 and len(lines_after) <= 25

    if not is_short:
        return body

    has_sig_markers = _SIGNATURE_CONTENT.search(after)
    first_line = lines_after[0].strip()
    has_name = bool(_NAME_LINE.match(first_line) or _CAPS_NAME_LINE.match(first_line))

    if has_sig_markers or has_name:
        return body[:match.start()].rstrip()

    return body


def _strip_standalone_signature(body: str) -> str:
    """Remove signature blocks that don't follow a standard valediction.

    Detects signatures by looking for patterns like:
    - A name line (possibly with credentials) followed by title/contact info
    - Embedded image markers [cid:...]
    - Social media link blocks
    """
    lines = body.split('\n')

    # Look for signature start indicators
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue

        # Check for embedded image marker - strong signal of signature start
        if _EMBEDDED_IMAGE.search(stripped):
            # Look back for the actual signature start (name line)
            sig_start = i
            for j in range(max(0, i - 3), i):
                prev_line = lines[j].strip()
                if prev_line and (_NAME_LINE.match(prev_line) or _CAPS_NAME_LINE.match(prev_line)):
                    sig_start = j
                    break
            return '\n'.join(lines[:sig_start]).rstrip()

        # Check for all-caps name with credentials (strong signature indicator)
        if _CAPS_NAME_LINE.match(stripped):
            # Verify next few lines look like signature content
            remaining = '\n'.join(lines[i:i+5])
            if _SIGNATURE_CONTENT.search(remaining):
                return '\n'.join(lines[:i]).rstrip()

        # Check for name line followed by title
        name_match = _NAME_LINE.match(stripped)
        if name_match and i < len(lines) - 1:
            next_lines = '\n'.join(lines[i:i+4])
            # Check if followed by title patterns or contact info
            has_title = bool(re.search(
                r"(?:Managing\s+)?Director|Partner|President|"
                r"Vice\s+President|Chief|Officer|Manager|"
                r"Associate|Advisor|Consultant|Administrator",
                next_lines, re.IGNORECASE
            ))
            has_contact = _SIGNATURE_CONTENT.search(next_lines)

            if has_title or has_contact:
                # Make sure there's actual message content before this
                content_before = '\n'.join(lines[:i]).strip()
                if content_before and len(content_before) > 20:
                    return content_before

    return body


def _strip_unsubscribe_footer(body: str) -> str:
    """Remove newsletter unsubscribe footers and everything after them."""
    match = re.search(
        r"^.*unsubscribe.*$",
        body,
        re.MULTILINE | re.IGNORECASE,
    )
    if match:
        body = body[:match.start()].rstrip()
    return body


def _strip_promotional_content(body: str) -> str:
    """Remove promotional signature content like social links, awards, vcard links."""
    # Remove social media link blocks
    match = _SOCIAL_LINKS.search(body)
    if match:
        body = body[:match.start()].rstrip()

    # Remove VCard/secure file patterns
    match = _VCARD_PATTERN.search(body)
    if match:
        body = body[:match.start()].rstrip()

    # Remove awards/rankings promotional text
    match = _AWARDS_PATTERN.search(body)
    if match:
        body = body[:match.start()].rstrip()

    # Remove embedded images that remain
    body = _EMBEDDED_IMAGE.sub('', body)

    return body.rstrip()


def strip_quotes(body: str, body_html: str | None = None) -> str:
    """Remove quoted replies, forwarded headers, and mobile signatures from email body.

    When *body_html* is provided the function uses an HTML-first pipeline
    that leverages structural cues (CSS classes, element IDs) for more
    accurate stripping.  Falls back to the plain-text pipeline when HTML
    is absent or when the HTML track fails.
    """
    if not body or not body.strip():
        return ""

    # ── HTML track ──────────────────────────────────────────────────
    if body_html and body_html.strip():
        try:
            from .html_email_parser import strip_html_quotes

            html_result = strip_html_quotes(body_html)
            if html_result and html_result.strip():
                # Apply lightweight text cleanup only (mobile sigs,
                # disclaimers, line unwrapping, whitespace).  The heavy
                # plain-text steps (mail-parser-reply, forwarded headers,
                # Outlook separators, "On...wrote:") are already handled
                # better by HTML structure.
                text = html_result

                # Mobile signatures
                text = _MOBILE_SIGNATURE.sub("", text).rstrip()

                # Confidentiality notices
                match = _CONFIDENTIAL_NOTICE.search(text)
                if match:
                    text = text[:match.start()].rstrip()

                # Environmental messages
                match = _ENVIRONMENTAL_MESSAGE.search(text)
                if match:
                    text = text[:match.start()].rstrip()

                # Dash-dash and underscore signature separators
                text = _strip_dash_dash_signature(text)
                text = _strip_underscore_signature(text)
                text = _strip_dash_dash_signature(text)  # clean up trailing --

                # Signature/promotional detection (catches sigs without CSS markup)
                text = _strip_signature_block(text)
                text = _strip_standalone_signature(text)
                text = _strip_promotional_content(text)

                # Unsubscribe footers (text-level fallback)
                text = _strip_unsubscribe_footer(text)

                # Unwrap hard-wrapped lines
                text = _unwrap_lines(text)

                # Collapse excessive whitespace
                text = re.sub(r"\n{3,}", "\n\n", text)

                cleaned = text.strip()
                if cleaned:
                    return cleaned
                # HTML track produced empty result after cleanup;
                # fall through to plain-text pipeline.
                log.debug("HTML track produced empty result after cleanup, falling back")
        except Exception as exc:
            log.debug("HTML track failed, falling back to plain text: %s", exc)

    # ── Plain-text track (original pipeline) ────────────────────────
    # Step 1: Use mail-parser-reply for standard quote detection
    try:
        reply_parser = EmailReplyParser()
        cleaned = reply_parser.parse_reply(body)
        if cleaned and cleaned.strip():
            body = cleaned
    except Exception as exc:
        log.debug("mail-parser-reply failed, falling back to regex: %s", exc)

    # Step 2: Remove forwarded message headers and everything after
    match = _FORWARDED_HEADER.search(body)
    if match:
        body = body[:match.start()].rstrip()

    # Step 3: Remove Outlook-style separators and everything after
    match = _OUTLOOK_SEPARATOR.search(body)
    if match:
        body = body[:match.start()].rstrip()

    # Step 4: Remove "On ... wrote:" blocks that may remain
    match = _ON_WROTE.search(body)
    if match:
        body = body[:match.start()].rstrip()

    # Step 5: Strip mobile signatures
    body = _MOBILE_SIGNATURE.sub("", body).rstrip()

    # Step 5.1: Remove confidentiality notices and everything after
    match = _CONFIDENTIAL_NOTICE.search(body)
    if match:
        body = body[:match.start()].rstrip()

    # Step 5.2: Remove environmental messages and everything after
    match = _ENVIRONMENTAL_MESSAGE.search(body)
    if match:
        body = body[:match.start()].rstrip()

    # Step 5.3: Remove signature blocks after valedictions
    body = _strip_signature_block(body)

    # Step 5.35: Remove -- and ____ signature separators
    body = _strip_dash_dash_signature(body)
    body = _strip_underscore_signature(body)
    body = _strip_dash_dash_signature(body)  # clean up trailing --

    # Step 5.4: Remove standalone signatures (without valedictions)
    body = _strip_standalone_signature(body)

    # Step 5.5: Remove promotional content (social links, awards, vcards)
    body = _strip_promotional_content(body)

    # Step 5.6: Remove unsubscribe footers
    body = _strip_unsubscribe_footer(body)

    # Step 6: Unwrap hard-wrapped lines
    body = _unwrap_lines(body)

    # Step 7: Clean up excessive whitespace
    body = re.sub(r"\n{3,}", "\n\n", body)

    return body.strip()
