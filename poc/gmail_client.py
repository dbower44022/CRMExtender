"""Gmail API wrapper: fetch threads, parse messages, and send email."""

from __future__ import annotations

import base64
import email.utils
import html as html_mod
import logging
import re
from datetime import datetime, timezone
from email.header import decode_header
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email import encoders

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from . import config
from .models import ParsedEmail
from .providers.base import CursorInvalid
from .rate_limiter import RateLimiter

log = logging.getLogger(__name__)


def _http_status(exc: HttpError) -> int:
    status = getattr(exc, "status_code", None) or getattr(
        getattr(exc, "resp", None), "status", None
    )
    return int(status or 0)


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


def _parse_address_names(raw: str) -> dict[str, str]:
    """Extract {address: display name} for entries that carry a name."""
    if not raw:
        return {}
    names: dict[str, str] = {}
    for name, addr in email.utils.getaddresses([raw]):
        if addr and name:
            names[addr.lower()] = _decode_header_value(name)
    return names


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


def _collect_attachments(payload: dict) -> list[dict]:
    """Walk the MIME tree and return attachment metadata (no bytes).

    A part counts as an attachment when Gmail gave it an ``attachmentId``
    or a filename. Inline images carry a ``Content-ID`` header, which the
    viewer uses to resolve ``cid:`` references (MAIL-15).
    """
    found: list[dict] = []

    def walk(part: dict) -> None:
        body = part.get("body", {}) or {}
        filename = part.get("filename") or ""
        attachment_id = body.get("attachmentId")
        if attachment_id or filename:
            headers = part.get("headers", []) or []
            content_id = _get_header(headers, "Content-ID").strip("<>") or None
            disposition = _get_header(headers, "Content-Disposition").lower()
            found.append({
                "attachment_id": attachment_id,
                "filename": filename or None,
                "mime_type": part.get("mimeType") or "application/octet-stream",
                "size": int(body.get("size") or 0),
                "content_id": content_id,
                "is_inline": bool(content_id) or disposition.startswith("inline"),
            })
        for child in part.get("parts", []) or []:
            walk(child)

    walk(payload)
    return found


# Patterns for _html_to_text — compiled once at module level
_RE_STYLE_SCRIPT = re.compile(r"<(style|script)[^>]*>.*?</\1>", re.IGNORECASE | re.DOTALL)
_RE_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
_RE_BR = re.compile(r"<br\s*/?>", re.IGNORECASE)
_RE_BLOCK = re.compile(r"</?(?:p|div|tr|li|h[1-6]|blockquote|table|thead|tbody|tfoot)\b[^>]*>", re.IGNORECASE)
_RE_TAG = re.compile(r"<[^>]+>")
_RE_MULTI_SPACE = re.compile(r"[^\S\n]+")
_RE_MULTI_NEWLINE = re.compile(r"\n{3,}")


def _html_to_text(html: str) -> str:
    """Convert HTML to readable plain text using only the standard library."""
    text = html
    # Remove style/script blocks entirely (the main source of CSS noise)
    text = _RE_STYLE_SCRIPT.sub("", text)
    # Remove HTML comments
    text = _RE_COMMENT.sub("", text)
    # Convert <br> to newlines
    text = _RE_BR.sub("\n", text)
    # Insert newlines around block-level elements
    text = _RE_BLOCK.sub("\n", text)
    # Strip remaining tags
    text = _RE_TAG.sub(" ", text)
    # Decode HTML entities (&nbsp; &ndash; &#8212; etc.)
    text = html_mod.unescape(text)
    # Collapse runs of whitespace (but preserve newlines)
    text = _RE_MULTI_SPACE.sub(" ", text)
    # Collapse excessive blank lines to at most one
    text = _RE_MULTI_NEWLINE.sub("\n\n", text)
    # Clean up each line
    text = "\n".join(line.strip() for line in text.splitlines())
    # Strip leading/trailing whitespace
    return text.strip()


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

    # Convert HTML to readable plain text if no plain body available
    if not body_plain and body_html:
        body_plain = _html_to_text(body_html)

    to_raw = _get_header(headers, "To")
    cc_raw = _get_header(headers, "Cc")
    bcc_raw = _get_header(headers, "Bcc")
    reply_to_raw = _get_header(headers, "Reply-To")

    participant_names: dict[str, str] = {}
    if sender_name and sender_email:
        participant_names[sender_email] = sender_name
    for raw in (to_raw, cc_raw, bcc_raw, reply_to_raw):
        participant_names.update(_parse_address_names(raw))

    label_ids = list(msg.get("labelIds", []) or [])

    return ParsedEmail(
        message_id=msg.get("id", ""),
        thread_id=msg.get("threadId", ""),
        subject=_decode_header_value(_get_header(headers, "Subject")),
        sender=sender_display,
        sender_email=sender_email,
        recipients=_parse_address_list(to_raw),
        cc=_parse_address_list(cc_raw),
        date=date,
        body_plain=body_plain,
        body_html=body_html,
        snippet=msg.get("snippet", ""),
        bcc=_parse_address_list(bcc_raw),
        reply_to=_parse_address_list(reply_to_raw),
        participant_names=participant_names,
        header_message_id=_get_header(headers, "Message-ID").strip() or None,
        header_in_reply_to=_get_header(headers, "In-Reply-To").strip() or None,
        header_references=" ".join(_get_header(headers, "References").split()) or None,
        label_ids=label_ids,
        is_read="UNREAD" not in label_ids,
        is_starred="STARRED" in label_ids,
        attachments=_collect_attachments(payload),
    )


def get_user_email(creds: Credentials) -> str:
    """Return the authenticated user's email address from the Gmail profile."""
    service = build("gmail", "v1", credentials=creds, cache_discovery=False)
    profile = service.users().getProfile(userId="me").execute()
    return profile["emailAddress"].lower()


def fetch_threads(
    creds: Credentials,
    query: str | None = None,
    max_threads: int | None = None,
    rate_limiter: RateLimiter | None = None,
    page_token: str | None = None,
) -> tuple[list[list[ParsedEmail]], str | None]:
    """Fetch Gmail threads and return as lists of parsed emails.

    Returns (threads, next_page_token) where threads is a list of threads,
    each thread being a list of ParsedEmail sorted by date ascending.
    The next_page_token can be passed back to continue fetching.
    """
    service = build("gmail", "v1", credentials=creds, cache_discovery=False)
    query = query or config.GMAIL_QUERY
    max_threads = max_threads or config.GMAIL_MAX_THREADS

    # Step 1: List thread IDs
    thread_ids: list[str] = []

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
    return threads, page_token


def get_history_id(creds: Credentials) -> str:
    """Return the current Gmail historyId for the authenticated user."""
    service = build("gmail", "v1", credentials=creds, cache_discovery=False)
    profile = service.users().getProfile(userId="me").execute()
    return str(profile["historyId"])


class HistoryExpiredError(CursorInvalid):
    """The stored Gmail history cursor is too old for the history API.

    Gmail only retains history for a limited period (typically about a
    week) and returns 404 for older historyIds. Callers must backfill by
    query instead of advancing the cursor, or the gap is silently lost.
    Subclasses the provider-neutral :class:`CursorInvalid` so the sync
    engine can catch one type for every provider.
    """


def fetch_history(
    creds: Credentials,
    start_history_id: str,
    rate_limiter: RateLimiter | None = None,
    *,
    include_labels: bool = False,
) -> tuple[list[str], list[str]] | tuple[list[str], list[str], list[dict]]:
    """Fetch Gmail history changes since start_history_id.

    Returns (added_message_ids, deleted_message_ids). With
    ``include_labels=True`` a third element is returned: a list of
    ``{"id", "added": [label ids], "removed": [label ids]}`` dicts, one
    per message whose labels changed (MAIL-10 consumes these).

    Raises HistoryExpiredError when the cursor is too old (Gmail 404),
    and propagates other API errors so the caller aborts without
    advancing its cursor.
    """
    service = build("gmail", "v1", credentials=creds, cache_discovery=False)
    added: list[str] = []
    deleted: list[str] = []
    label_changes: dict[str, dict] = {}
    page_token: str | None = None

    history_types = ["messageAdded", "messageDeleted"]
    if include_labels:
        history_types += ["labelAdded", "labelRemoved"]

    while True:
        if rate_limiter:
            rate_limiter.acquire()

        try:
            params: dict = {
                "userId": "me",
                "startHistoryId": start_history_id,
                "historyTypes": history_types,
            }
            if page_token:
                params["pageToken"] = page_token

            result = service.users().history().list(**params).execute()
        except HttpError as exc:
            if _http_status(exc) == 404:
                raise HistoryExpiredError(
                    f"Gmail history cursor {start_history_id} has expired"
                ) from exc
            log.warning("History fetch failed (historyId=%s): %s", start_history_id, exc)
            raise

        for record in result.get("history", []):
            for msg_added in record.get("messagesAdded", []):
                mid = msg_added.get("message", {}).get("id")
                if mid:
                    added.append(mid)
            for msg_deleted in record.get("messagesDeleted", []):
                mid = msg_deleted.get("message", {}).get("id")
                if mid:
                    deleted.append(mid)
            if include_labels:
                for change in record.get("labelsAdded", []):
                    mid = change.get("message", {}).get("id")
                    if mid:
                        entry = label_changes.setdefault(mid, {"id": mid, "added": [], "removed": []})
                        entry["added"].extend(change.get("labelIds", []))
                for change in record.get("labelsRemoved", []):
                    mid = change.get("message", {}).get("id")
                    if mid:
                        entry = label_changes.setdefault(mid, {"id": mid, "added": [], "removed": []})
                        entry["removed"].extend(change.get("labelIds", []))

        page_token = result.get("nextPageToken")
        if not page_token:
            break

    log.info("History since %s: %d added, %d deleted, %d label changes",
             start_history_id, len(added), len(deleted), len(label_changes))
    if include_labels:
        return added, deleted, list(label_changes.values())
    return added, deleted


def list_labels(creds: Credentials, rate_limiter: RateLimiter | None = None) -> list[dict]:
    """Return the raw Gmail label resources for the mailbox."""
    if rate_limiter:
        rate_limiter.acquire()
    service = build("gmail", "v1", credentials=creds, cache_discovery=False)
    result = service.users().labels().list(userId="me").execute()
    return list(result.get("labels", []))


def list_message_ids(
    creds: Credentials,
    query: str,
    *,
    max_results: int = 200,
    page_token: str | None = None,
    rate_limiter: RateLimiter | None = None,
) -> tuple[list[str], str | None]:
    """One page of message ids matching ``query`` (newest first)."""
    if rate_limiter:
        rate_limiter.acquire()
    service = build("gmail", "v1", credentials=creds, cache_discovery=False)
    params: dict = {"userId": "me", "q": query, "maxResults": max_results}
    if page_token:
        params["pageToken"] = page_token
    result = service.users().messages().list(**params).execute()
    ids = [m["id"] for m in result.get("messages", []) if m.get("id")]
    return ids, result.get("nextPageToken")


def fetch_attachment(
    creds: Credentials,
    message_id: str,
    attachment_id: str,
    rate_limiter: RateLimiter | None = None,
) -> bytes:
    """Return the decoded bytes of one attachment part."""
    if rate_limiter:
        rate_limiter.acquire()
    service = build("gmail", "v1", credentials=creds, cache_discovery=False)
    result = (
        service.users()
        .messages()
        .attachments()
        .get(userId="me", messageId=message_id, id=attachment_id)
        .execute()
    )
    return base64.urlsafe_b64decode(result.get("data", ""))


def modify_labels(
    creds: Credentials,
    message_ids: list[str],
    *,
    add: list[str] | None = None,
    remove: list[str] | None = None,
    rate_limiter: RateLimiter | None = None,
) -> None:
    """Add and/or remove labels on a batch of messages (``batchModify``).

    Raises HttpError on failure; a 404 means at least one target is gone.
    """
    if not message_ids or not (add or remove):
        return
    if rate_limiter:
        rate_limiter.acquire()
    service = build("gmail", "v1", credentials=creds, cache_discovery=False)
    body: dict = {"ids": list(message_ids)}
    if add:
        body["addLabelIds"] = list(add)
    if remove:
        body["removeLabelIds"] = list(remove)
    service.users().messages().batchModify(userId="me", body=body).execute()


def trash_messages(
    creds: Credentials,
    message_ids: list[str],
    *,
    untrash: bool = False,
    rate_limiter: RateLimiter | None = None,
) -> None:
    """Move messages to or out of Trash (one request per message)."""
    service = build("gmail", "v1", credentials=creds, cache_discovery=False)
    for mid in message_ids:
        if rate_limiter:
            rate_limiter.acquire()
        call = service.users().messages()
        (call.untrash if untrash else call.trash)(userId="me", id=mid).execute()


def create_label(
    creds: Credentials,
    name: str,
    rate_limiter: RateLimiter | None = None,
) -> dict:
    """Create a user label; nested labels use ``Parent/Child`` names."""
    if rate_limiter:
        rate_limiter.acquire()
    service = build("gmail", "v1", credentials=creds, cache_discovery=False)
    body = {
        "name": name,
        "labelListVisibility": "labelShow",
        "messageListVisibility": "show",
    }
    return service.users().labels().create(userId="me", body=body).execute()


def get_profile(creds: Credentials) -> dict:
    """Return the raw Gmail profile (emailAddress, historyId, counts)."""
    service = build("gmail", "v1", credentials=creds, cache_discovery=False)
    return service.users().getProfile(userId="me").execute()


def fetch_messages(
    creds: Credentials,
    message_ids: list[str],
    rate_limiter: RateLimiter | None = None,
    *,
    metadata_only: bool = False,
) -> list[ParsedEmail]:
    """Fetch full message data for a list of message IDs.

    Returns parsed emails (skips failures). With ``metadata_only=True``
    the ``metadata`` format is requested: headers, labels, and flags come
    back but bodies and attachment parts do not (used by the mail-state
    backfill, which must not overwrite stored bodies).
    """
    service = build("gmail", "v1", credentials=creds, cache_discovery=False)
    emails: list[ParsedEmail] = []
    fmt = "metadata" if metadata_only else "full"

    for mid in message_ids:
        try:
            if rate_limiter:
                rate_limiter.acquire()

            msg = (
                service.users()
                .messages()
                .get(userId="me", id=mid, format=fmt)
                .execute()
            )
            emails.append(_parse_message(msg))
        except Exception as exc:
            log.warning("Failed to fetch message %s: %s", mid, exc)

    log.info("Fetched %d/%d messages", len(emails), len(message_ids))
    return emails


def send_message(
    creds: Credentials,
    from_email: str,
    to: list[str],
    subject: str,
    body_html: str,
    body_text: str,
    cc: list[str] | None = None,
    bcc: list[str] | None = None,
    in_reply_to: str | None = None,
    references: str | None = None,
    thread_id: str | None = None,
    attachments: list[dict] | None = None,
    rate_limiter: RateLimiter | None = None,
) -> tuple[str, str]:
    """Send an email via Gmail API.

    Returns (provider_message_id, provider_thread_id).

    Each attachment dict should have keys: filename, mime_type, data (bytes).
    """
    if rate_limiter:
        rate_limiter.acquire()

    # Build MIME message
    if attachments:
        msg = MIMEMultipart("mixed")
        alt = MIMEMultipart("alternative")
        alt.attach(MIMEText(body_text, "plain", "utf-8"))
        alt.attach(MIMEText(body_html, "html", "utf-8"))
        msg.attach(alt)
        for att in attachments:
            maintype, subtype = (att.get("mime_type") or "application/octet-stream").split("/", 1)
            part = MIMEBase(maintype, subtype)
            part.set_payload(att["data"])
            encoders.encode_base64(part)
            part.add_header(
                "Content-Disposition", "attachment",
                filename=att.get("filename", "attachment"),
            )
            msg.attach(part)
    else:
        msg = MIMEMultipart("alternative")
        msg.attach(MIMEText(body_text, "plain", "utf-8"))
        msg.attach(MIMEText(body_html, "html", "utf-8"))

    msg["From"] = from_email
    msg["To"] = ", ".join(to)
    if cc:
        msg["Cc"] = ", ".join(cc)
    if bcc:
        msg["Bcc"] = ", ".join(bcc)
    msg["Subject"] = subject

    if in_reply_to:
        msg["In-Reply-To"] = in_reply_to
    if references:
        msg["References"] = references

    # Encode as base64url
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("ascii")

    # Send via Gmail API
    service = build("gmail", "v1", credentials=creds, cache_discovery=False)
    send_body: dict = {"raw": raw}
    if thread_id:
        send_body["threadId"] = thread_id

    result = (
        service.users()
        .messages()
        .send(userId="me", body=send_body)
        .execute()
    )

    provider_msg_id = result.get("id", "")
    provider_thread_id = result.get("threadId", "")
    log.info("Sent message %s in thread %s", provider_msg_id, provider_thread_id)
    return provider_msg_id, provider_thread_id
