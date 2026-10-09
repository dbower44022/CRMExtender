"""MailProvider contract — the one interface every email provider adapter implements.

Specified in PRDs/email-provider-sync-prd.md §3. The sync engine
(poc/sync.py), the outbound path (poc/outbound.py), and the mail API
talk only to this interface; nothing above the adapter layer knows
whether an account is Gmail, Microsoft Graph, or IMAP.

The normalized message type is :class:`poc.models.ParsedEmail`, re-exported
here as ``MailMessage`` (Mail Client TDD D-15). ``ParsedEmail`` carries the
full header set, participants with display names, labels, flags, and
attachment metadata; the storage of those fields is MAIL-07.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from ..models import ParsedEmail as MailMessage
from ..rate_limiter import RateLimiter

__all__ = [
    "Action",
    "ActionKind",
    "ActionResult",
    "ActionStatus",
    "CursorInvalid",
    "Delta",
    "Folder",
    "FolderKind",
    "MailMessage",
    "MailProvider",
    "OutboundMessage",
    "ProviderError",
    "SyncStatus",
]


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

class ProviderError(Exception):
    """Base class for errors an adapter raises on behalf of its provider."""


class CursorInvalid(ProviderError):
    """The stored incremental cursor is no longer accepted by the provider.

    Gmail returns 404 on an expired historyId, Microsoft Graph returns 410
    on a stale delta link, IMAP signals it with a UIDVALIDITY change. The
    engine responds with the recovery pass in KP-EPS-04; nothing is
    deleted locally.
    """


# ---------------------------------------------------------------------------
# Folders and labels
# ---------------------------------------------------------------------------

class FolderKind(str, Enum):
    INBOX = "inbox"
    SENT = "sent"
    DRAFTS = "drafts"
    SPAM = "spam"
    TRASH = "trash"
    ARCHIVE = "archive"
    STARRED = "starred"
    SNOOZED = "snoozed"
    IMPORTANT = "important"
    CATEGORY = "category"
    USER = "user"
    SYSTEM = "system"


@dataclass
class Folder:
    """A provider label (Gmail) or folder (Graph, IMAP)."""

    id: str
    name: str
    kind: FolderKind = FolderKind.USER
    parent_id: str | None = None
    unread_count: int | None = None
    total_count: int | None = None


# ---------------------------------------------------------------------------
# Incremental delta
# ---------------------------------------------------------------------------

@dataclass
class Delta:
    """Changes at the provider since a cursor.

    ``label_changes`` holds ``(message_id, added_label_ids, removed_label_ids)``;
    ``flag_changes`` holds ``(message_id, {"is_read": bool, "is_starred": bool})``
    with only the flags that changed present.
    """

    added_ids: list[str] = field(default_factory=list)
    deleted_ids: list[str] = field(default_factory=list)
    label_changes: list[tuple[str, list[str], list[str]]] = field(default_factory=list)
    flag_changes: list[tuple[str, dict[str, bool]]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Actions (write-back)
# ---------------------------------------------------------------------------

class ActionKind(str, Enum):
    MARK_READ = "mark_read"
    MARK_UNREAD = "mark_unread"
    STAR = "star"
    UNSTAR = "unstar"
    ARCHIVE = "archive"
    UNARCHIVE = "unarchive"
    TRASH = "trash"
    UNTRASH = "untrash"
    SPAM = "spam"
    UNSPAM = "unspam"
    ADD_LABEL = "add_label"
    REMOVE_LABEL = "remove_label"
    MOVE = "move"
    CREATE_LABEL = "create_label"
    SNOOZE = "snooze"
    UNSNOOZE = "unsnooze"


class ActionStatus(str, Enum):
    PUSHED = "pushed"
    GONE = "gone"      # target no longer exists at the provider; treated as done
    FAILED = "failed"


@dataclass
class Action:
    """One write-back operation against a provider.

    ``message_ids`` are provider message ids. ``label_id`` is the provider
    label or folder id for label and move actions; ``name`` and
    ``parent_id`` serve ``CREATE_LABEL``.
    """

    kind: ActionKind
    message_ids: list[str] = field(default_factory=list)
    label_id: str | None = None
    name: str | None = None
    parent_id: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class ActionResult:
    status: ActionStatus
    error: str | None = None
    created_label: Folder | None = None
    #: True when retrying cannot help (bad request, forbidden, missing scope);
    #: the outbox dead-letters such a failure at once instead of backing off.
    permanent: bool = False


# ---------------------------------------------------------------------------
# Sending
# ---------------------------------------------------------------------------

@dataclass
class OutboundMessage:
    """What the outbound path hands to ``send``.

    Each attachment dict has keys ``filename``, ``mime_type``, ``data`` (bytes).
    """

    from_email: str
    to: list[str]
    subject: str
    body_html: str
    body_text: str
    cc: list[str] | None = None
    bcc: list[str] | None = None
    in_reply_to: str | None = None
    references: str | None = None
    thread_id: str | None = None
    attachments: list[dict] | None = None


@dataclass
class SyncStatus:
    email_address: str
    cursor: str | None
    messages_total: int | None = None
    threads_total: int | None = None


# ---------------------------------------------------------------------------
# The contract
# ---------------------------------------------------------------------------

class MailProvider(abc.ABC):
    """Every email provider adapter implements this interface.

    ``session`` is whatever ``authenticate`` returns for the provider
    (Google credentials for Gmail, an MSAL token for Graph, an IMAP
    connection pair for IMAP). The engine passes it back unchanged.
    """

    #: Value of ``provider_accounts.provider`` this adapter serves.
    name: str = ""

    # --- identity -------------------------------------------------------

    @abc.abstractmethod
    def authenticate(self, account: dict) -> Any:
        """Return a session for the given ``provider_accounts`` row."""

    @abc.abstractmethod
    def get_user_email(self, session: Any) -> str:
        """Return the authenticated mailbox address, lower-cased."""

    @abc.abstractmethod
    def capabilities(self) -> set[str]:
        """Capability flags per email-provider-sync-prd.md §3.3."""

    # --- reading --------------------------------------------------------

    @abc.abstractmethod
    def list_folders(self, session: Any, *, rate_limiter: RateLimiter | None = None) -> list[Folder]:
        """All labels or folders of the mailbox with system kinds mapped."""

    @abc.abstractmethod
    def fetch_initial(
        self,
        session: Any,
        query: str | None = None,
        *,
        max_threads: int | None = None,
        page_token: str | None = None,
        rate_limiter: RateLimiter | None = None,
    ) -> tuple[list[list[MailMessage]], str | None]:
        """Fetch a page of threads matching ``query``.

        Returns ``(threads, next_page_token)``. Threads are lists of
        messages sorted by date ascending (Mail Client TDD D-16).
        """

    @abc.abstractmethod
    def fetch_backfill(
        self,
        session: Any,
        backfill_cursor: str | None,
        *,
        batch: int = 200,
        rate_limiter: RateLimiter | None = None,
    ) -> tuple[list[MailMessage], str | None]:
        """Fetch the next oldest batch of historical mail.

        Returns ``(messages, next_backfill_cursor)``; ``None`` as the next
        cursor means the mailbox start has been reached.
        """

    @abc.abstractmethod
    def fetch_incremental(
        self,
        session: Any,
        cursor: str,
        *,
        rate_limiter: RateLimiter | None = None,
    ) -> tuple[Delta, str]:
        """Changes since ``cursor``. Raises :class:`CursorInvalid` when stale."""

    @abc.abstractmethod
    def get_cursor(self, session: Any) -> str:
        """The provider's current incremental position (stored after a sync)."""

    @abc.abstractmethod
    def fetch_messages(
        self,
        session: Any,
        message_ids: list[str],
        *,
        rate_limiter: RateLimiter | None = None,
        metadata_only: bool = False,
    ) -> list[MailMessage]:
        """Messages for the given provider ids; failures are skipped.

        ``metadata_only`` returns headers, labels, and flags without
        bodies or attachment parts, for refreshing mailbox state cheaply.
        """

    @abc.abstractmethod
    def fetch_attachment(
        self,
        session: Any,
        message_id: str,
        attachment_id: str,
        *,
        rate_limiter: RateLimiter | None = None,
    ) -> bytes:
        """Raw bytes of one attachment part."""

    # --- writing --------------------------------------------------------

    @abc.abstractmethod
    def apply_action(
        self,
        session: Any,
        action: Action,
        *,
        rate_limiter: RateLimiter | None = None,
    ) -> ActionResult:
        """Push one write-back action. Idempotent; see §3.2."""

    @abc.abstractmethod
    def send(
        self,
        session: Any,
        message: OutboundMessage,
        *,
        rate_limiter: RateLimiter | None = None,
    ) -> tuple[str, str]:
        """Send; returns ``(provider_message_id, provider_thread_id)``."""

    # --- lifecycle ------------------------------------------------------

    @abc.abstractmethod
    def get_sync_status(self, session: Any) -> SyncStatus:
        """Mailbox-level status for the Accounts page."""

    @abc.abstractmethod
    def revoke(self, session: Any) -> None:
        """Revoke the provider credential on disconnect."""
