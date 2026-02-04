"""Gmail API wrapper: fetch threads and parse messages."""

from __future__ import annotations

import base64
import email.utils
import logging
import re
from datetime import datetime, timezone
from email.header import decode_header

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from . import config
from .models import ParsedEmail
from .rate_limiter import RateLimiter

log = logging.getLogger(__name__)


def _decode_header_value(raw: str) -> str:
    """Decode RFC 2047 encoded header values."""
    if not raw:
        return ""
    parts = decode_header(raw)
    decoded = []
    for content, charset in parts:
        if isinstance(content, bytes):
            decoded.append(content.decode(charset or "utf-8", errors="replace"))
        else:
            decoded.append(content)
    return "".join(decoded)


def _parse_email_address(raw: str) -> tuple[str, str]:
    """Extract (display name, email address) from a header value like 'Name <addr>'."""
    if not raw:
        return "", ""
    name, addr = email.utils.parseaddr(raw)
    return _decode_header_value(name), addr.lower()


def _parse_address_list(raw: str) -> list[str]:
    """Extract email addresses from a comma-separated header value."""
    if not raw:
        return []
    pairs = email.utils.getaddresses([raw])
    return [addr.lower() for _, addr in pairs if addr]


def _get_header(headers: list[dict], name: str) -> str:
    """Get a header value by name from Gmail API headers list."""
    name_lower = name.lower()
    for h in headers:
        if h.get("name", "").lower() == name_lower:
            return h.get("value", "")
    return ""


def _decode_body(payload: dict) -> tuple[str, str]:
    """Recursively extract plain text and HTML body from a Gmail message payload."""
    plain = ""
    html = ""

    mime_type = payload.get("mimeType", "")
    body_data = payload.get("body", {}).get("data", "")

    if body_data:
        decoded = base64.urlsafe_b64decode(body_data).decode("utf-8", errors="replace")
        if mime_type == "text/plain":
            plain = decoded
        elif mime_type == "text/html":
            html = decoded

    for part in payload.get("parts", []):
        p, h = _decode_body(part)
        if p and not plain:
            plain = p
        if h and not html:
            html = h

    return plain, html


def _parse_date(date_str: str) -> datetime | None:
    """Parse an email Date header into a datetime."""
    if not date_str:
        return None
    try:
        parsed = email.utils.parsedate_to_datetime(date_str)
        return parsed.astimezone(timezone.utc)
    except (ValueError, TypeError):
        # Try the Gmail internalDate format (ms since epoch) as fallback
        pass
    return None


def _parse_message(msg: dict) -> ParsedEmail:
    """Parse a Gmail API message resource into a ParsedEmail."""
    payload = msg.get("payload", {})
    headers = payload.get("headers", [])

    sender_name, sender_email = _parse_email_address(_get_header(headers, "From"))
    sender_display = f"{sender_name} <{sender_email}>" if sender_name else sender_email

    date = _parse_date(_get_header(headers, "Date"))
    if not date:
        # Fallback to internalDate (ms since epoch)
        internal_date = msg.get("internalDate")
        if internal_date:
            date = datetime.fromtimestamp(
                int(internal_date) / 1000, tz=timezone.utc
            )

    body_plain, body_html = _decode_body(payload)

    # Strip HTML tags for a plain-text fallback if no plain body
    if not body_plain and body_html:
        body_plain = re.sub(r"<[^>]+>", " ", body_html)
        body_plain = re.sub(r"\s+", " ", body_plain).strip()

    return ParsedEmail(
        message_id=msg.get("id", ""),
        thread_id=msg.get("threadId", ""),
        subject=_decode_header_value(_get_header(headers, "Subject")),
        sender=sender_display,
        sender_email=sender_email,
        recipients=_parse_address_list(_get_header(headers, "To")),
        cc=_parse_address_list(_get_header(headers, "Cc")),
        date=date,
        body_plain=body_plain,
        body_html=body_html,
        snippet=msg.get("snippet", ""),
    )


def get_user_email(creds: Credentials) -> str:
    """Return the authenticated user's email address from the Gmail profile."""
    service = build("gmail", "v1", credentials=creds)
    profile = service.users().getProfile(userId="me").execute()
    return profile["emailAddress"].lower()


def fetch_threads(
    creds: Credentials,
    query: str | None = None,
    max_threads: int | None = None,
    rate_limiter: RateLimiter | None = None,
) -> list[list[ParsedEmail]]:
    """Fetch Gmail threads and return as lists of parsed emails.

    Returns a list of threads, each thread being a list of ParsedEmail
    sorted by date ascending.
    """
    service = build("gmail", "v1", credentials=creds)
    query = query or config.GMAIL_QUERY
    max_threads = max_threads or config.GMAIL_MAX_THREADS

    # Step 1: List thread IDs
    thread_ids: list[str] = []
    page_token: str | None = None

    while len(thread_ids) < max_threads:
        if rate_limiter:
            rate_limiter.acquire()

        result = (
            service.users()
            .threads()
            .list(
                userId="me",
                q=query,
                maxResults=min(100, max_threads - len(thread_ids)),
                pageToken=page_token or "",
            )
            .execute()
        )

        for t in result.get("threads", []):
            thread_ids.append(t["id"])
            if len(thread_ids) >= max_threads:
                break

        page_token = result.get("nextPageToken")
        if not page_token:
            break

    log.info("Found %d threads matching query: %s", len(thread_ids), query)

    # Step 2: Fetch full thread data
    threads: list[list[ParsedEmail]] = []
    for tid in thread_ids:
        try:
            if rate_limiter:
                rate_limiter.acquire()

            thread_data = (
                service.users()
                .threads()
                .get(userId="me", id=tid, format="full")
                .execute()
            )

            emails = []
            for msg in thread_data.get("messages", []):
                try:
                    emails.append(_parse_message(msg))
                except Exception as exc:
                    log.warning("Failed to parse message %s: %s", msg.get("id"), exc)

            # Sort by date ascending
            emails.sort(key=lambda e: e.date or datetime.min.replace(tzinfo=timezone.utc))
            threads.append(emails)

        except Exception as exc:
            log.warning("Failed to fetch thread %s: %s", tid, exc)

    log.info("Fetched %d threads with %d total messages",
             len(threads), sum(len(t) for t in threads))
    return threads
