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

    # Step 6: Clean up excessive whitespace
    body = re.sub(r"\n{3,}", "\n\n", body)

    return body.strip()
