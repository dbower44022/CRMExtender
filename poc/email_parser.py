"""Email quote stripping pipeline.

Uses mail-parser-reply for standard quoted content detection,
plus custom patterns for forwarded messages and mobile signatures.
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
    r"Sent from Mail for Windows)\s*$",
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
    r"Respectfully"
    r"),?[\s]*$",
    re.MULTILINE | re.IGNORECASE,
)

# Patterns that indicate signature content (not message content)
_SIGNATURE_CONTENT = re.compile(
    r"(?:"
    r"(?:Tel|Phone|Fax|Mobile|Cell)\s*[:\.]?\s*[\+\d\(\)\-\s]{7,}|"
    r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}|"
    r"(?:www\.|https?://)|"
    r"(?:Dept\.|Department|University|Corp\.|Corporation|Inc\.|LLC|Ltd\.)|"
    r"(?:Professor|Director|Manager|CEO|CTO|CFO|VP|Vice\s+President|President|Engineer|Analyst)"
    r")",
    re.IGNORECASE,
)


def _strip_signature_block(body: str) -> str:
    """Remove signature block if it follows a valediction."""
    match = _VALEDICTION.search(body)
    if not match:
        return body

    # Get content after valediction
    after_valediction = body[match.end():].strip()
    if not after_valediction:
        return body[:match.start()].rstrip()

    # Check first ~500 chars or 10 lines for signature indicators
    check_content = after_valediction[:500]
    lines_after = after_valediction.split('\n')[:10]

    # If remaining content has signature patterns and is short, truncate
    has_signature_markers = _SIGNATURE_CONTENT.search(check_content)
    is_short = len(after_valediction) < 500 or len(lines_after) < 10

    # Check for substantive sentences - must have verb-like patterns on a single line
    # Exclude URLs, emails, and typical signature lines
    # Look for sentences with 4+ words ending in punctuation (on same line)
    # Use [^\n] to ensure matching within a single line
    has_sentences = bool(re.search(
        r"^[A-Z][a-z]+(?:[ \t]+\w+){3,}[^\n]*[.!?]\s*$",
        check_content,
        re.MULTILINE
    ))

    if has_signature_markers and is_short and not has_sentences:
        return body[:match.start()].rstrip()

    return body


def strip_quotes(body: str) -> str:
    """Remove quoted replies, forwarded headers, and mobile signatures from email body."""
    if not body or not body.strip():
        return ""

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

    # Step 6: Clean up excessive whitespace
    body = re.sub(r"\n{3,}", "\n\n", body)

    return body.strip()
