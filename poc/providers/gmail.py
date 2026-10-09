"""Gmail adapter: the MailProvider contract over the Gmail API client.

Mapping per PRDs/email-provider-sync-prd.md §5.1. The adapter delegates
to :mod:`poc.gmail_client` through the module object (never ``from …
import``) so existing tests that patch ``poc.gmail_client.<fn>`` keep
working and so the HTTP layer stays in one place.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from googleapiclient.errors import HttpError

from .. import config, gmail_client
from ..rate_limiter import RateLimiter
from . import register_provider
from .base import (
    Action,
    ActionKind,
    ActionResult,
    ActionStatus,
    Delta,
    Folder,
    FolderKind,
    MailMessage,
    MailProvider,
    OutboundMessage,
    SyncStatus,
)

log = logging.getLogger(__name__)

#: Gmail system label id → folder kind
_SYSTEM_LABEL_KINDS: dict[str, FolderKind] = {
    "INBOX": FolderKind.INBOX,
    "SENT": FolderKind.SENT,
    "DRAFT": FolderKind.DRAFTS,
    "SPAM": FolderKind.SPAM,
    "TRASH": FolderKind.TRASH,
    "STARRED": FolderKind.STARRED,
    "IMPORTANT": FolderKind.IMPORTANT,
}

#: Label applied at the provider while a thread is snoozed (KP-MAIL-06)
SNOOZE_LABEL_NAME = "CRMExtender/Snoozed"


def _status(exc: HttpError) -> int:
    return gmail_client._http_status(exc)


@register_provider
class GmailProvider(MailProvider):
    name = "gmail"

    # --- identity -------------------------------------------------------

    def authenticate(self, account: dict) -> Any:
        from ..auth import get_credentials_for_account

        token_path = account.get("auth_token_path") or str(config.TOKEN_PATH)
        return get_credentials_for_account(Path(token_path))

    def get_user_email(self, session: Any) -> str:
        return gmail_client.get_user_email(session)

    def capabilities(self) -> set[str]:
        return {"labels", "star", "spam", "snooze_label", "push", "send"}

    # --- reading --------------------------------------------------------

    def list_folders(self, session: Any, *, rate_limiter: RateLimiter | None = None) -> list[Folder]:
        folders: list[Folder] = []
        for raw in gmail_client.list_labels(session, rate_limiter=rate_limiter):
            label_id = raw.get("id", "")
            name = raw.get("name", label_id)
            if raw.get("type") == "system":
                if label_id.startswith("CATEGORY_"):
                    kind = FolderKind.CATEGORY
                else:
                    kind = _SYSTEM_LABEL_KINDS.get(label_id, FolderKind.SYSTEM)
            elif name == SNOOZE_LABEL_NAME:
                kind = FolderKind.SNOOZED
            else:
                kind = FolderKind.USER
            parent = name.rsplit("/", 1)[0] if kind is FolderKind.USER and "/" in name else None
            folders.append(Folder(
                id=label_id,
                name=name,
                kind=kind,
                parent_id=parent,
                unread_count=raw.get("messagesUnread"),
                total_count=raw.get("messagesTotal"),
            ))
        return folders

    def fetch_initial(
        self,
        session: Any,
        query: str | None = None,
        *,
        max_threads: int | None = None,
        page_token: str | None = None,
        rate_limiter: RateLimiter | None = None,
    ) -> tuple[list[list[MailMessage]], str | None]:
        return gmail_client.fetch_threads(
            session,
            query=query,
            max_threads=max_threads,
            rate_limiter=rate_limiter,
            page_token=page_token,
        )

    def fetch_backfill(
        self,
        session: Any,
        backfill_cursor: str | None,
        *,
        batch: int = 200,
        rate_limiter: RateLimiter | None = None,
    ) -> tuple[list[MailMessage], str | None]:
        """Backfill pages ``messages.list`` with a ``before:<epoch>`` query.

        The cursor is ``"<epoch>|<page_token>"``: the epoch bounds the
        query, the page token continues within it. The engine starts the
        job with ``"<oldest stored epoch>|"``.
        """
        if not backfill_cursor:
            return [], None
        epoch, _, page_token = backfill_cursor.partition("|")
        query = f"before:{epoch}" if epoch else "in:anywhere"
        ids, next_token = gmail_client.list_message_ids(
            session, query, max_results=batch,
            page_token=page_token or None, rate_limiter=rate_limiter,
        )
        if not ids:
            return [], None
        messages = gmail_client.fetch_messages(session, ids, rate_limiter=rate_limiter)
        next_cursor = f"{epoch}|{next_token}" if next_token else None
        return messages, next_cursor

    def fetch_incremental(
        self,
        session: Any,
        cursor: str,
        *,
        rate_limiter: RateLimiter | None = None,
    ) -> tuple[Delta, str]:
        added, deleted, label_changes = gmail_client.fetch_history(
            session, cursor, rate_limiter=rate_limiter, include_labels=True,
        )
        delta = Delta(added_ids=added, deleted_ids=deleted)
        for change in label_changes:
            added_labels = list(change.get("added", []))
            removed_labels = list(change.get("removed", []))
            delta.label_changes.append((change["id"], added_labels, removed_labels))
            flags: dict[str, bool] = {}
            if "UNREAD" in added_labels:
                flags["is_read"] = False
            elif "UNREAD" in removed_labels:
                flags["is_read"] = True
            if "STARRED" in added_labels:
                flags["is_starred"] = True
            elif "STARRED" in removed_labels:
                flags["is_starred"] = False
            if flags:
                delta.flag_changes.append((change["id"], flags))
        return delta, self.get_cursor(session)

    def get_cursor(self, session: Any) -> str:
        return gmail_client.get_history_id(session)

    def fetch_messages(
        self,
        session: Any,
        message_ids: list[str],
        *,
        rate_limiter: RateLimiter | None = None,
        metadata_only: bool = False,
    ) -> list[MailMessage]:
        return gmail_client.fetch_messages(
            session, message_ids, rate_limiter=rate_limiter, metadata_only=metadata_only,
        )

    def fetch_attachment(
        self,
        session: Any,
        message_id: str,
        attachment_id: str,
        *,
        rate_limiter: RateLimiter | None = None,
    ) -> bytes:
        return gmail_client.fetch_attachment(
            session, message_id, attachment_id, rate_limiter=rate_limiter,
        )

    # --- writing --------------------------------------------------------

    def apply_action(
        self,
        session: Any,
        action: Action,
        *,
        rate_limiter: RateLimiter | None = None,
    ) -> ActionResult:
        """Translate an :class:`Action` into Gmail label operations (§3.2)."""
        try:
            return self._apply(session, action, rate_limiter)
        except HttpError as exc:
            if _status(exc) == 404:
                return ActionResult(ActionStatus.GONE, error=str(exc))
            return ActionResult(ActionStatus.FAILED, error=str(exc))

    def _apply(self, session: Any, action: Action, rate_limiter: RateLimiter | None) -> ActionResult:
        kind = action.kind
        ids = action.message_ids

        def modify(add: list[str] | None = None, remove: list[str] | None = None) -> ActionResult:
            gmail_client.modify_labels(session, ids, add=add, remove=remove, rate_limiter=rate_limiter)
            return ActionResult(ActionStatus.PUSHED)

        if kind is ActionKind.MARK_READ:
            return modify(remove=["UNREAD"])
        if kind is ActionKind.MARK_UNREAD:
            return modify(add=["UNREAD"])
        if kind is ActionKind.STAR:
            return modify(add=["STARRED"])
        if kind is ActionKind.UNSTAR:
            return modify(remove=["STARRED"])
        if kind is ActionKind.ARCHIVE:
            return modify(remove=["INBOX"])
        if kind is ActionKind.UNARCHIVE:
            return modify(add=["INBOX"])
        if kind is ActionKind.SPAM:
            return modify(add=["SPAM"], remove=["INBOX"])
        if kind is ActionKind.UNSPAM:
            return modify(add=["INBOX"], remove=["SPAM"])
        if kind is ActionKind.TRASH:
            gmail_client.trash_messages(session, ids, rate_limiter=rate_limiter)
            return ActionResult(ActionStatus.PUSHED)
        if kind is ActionKind.UNTRASH:
            gmail_client.trash_messages(session, ids, untrash=True, rate_limiter=rate_limiter)
            return ActionResult(ActionStatus.PUSHED)
        if kind is ActionKind.ADD_LABEL:
            if not action.label_id:
                return ActionResult(ActionStatus.FAILED, error="label_id required")
            return modify(add=[action.label_id])
        if kind is ActionKind.REMOVE_LABEL:
            if not action.label_id:
                return ActionResult(ActionStatus.FAILED, error="label_id required")
            return modify(remove=[action.label_id])
        if kind is ActionKind.MOVE:
            # Gmail has no folders: "move" is add the target label and
            # drop the labels listed in payload["from_label_ids"] (or INBOX).
            if not action.label_id:
                return ActionResult(ActionStatus.FAILED, error="label_id required")
            remove = list(action.payload.get("from_label_ids") or ["INBOX"])
            return modify(add=[action.label_id], remove=remove)
        if kind is ActionKind.CREATE_LABEL:
            if not action.name:
                return ActionResult(ActionStatus.FAILED, error="name required")
            full_name = f"{action.parent_id}/{action.name}" if action.parent_id else action.name
            raw = gmail_client.create_label(session, full_name, rate_limiter=rate_limiter)
            folder = Folder(id=raw.get("id", ""), name=raw.get("name", full_name), kind=FolderKind.USER,
                            parent_id=action.parent_id)
            return ActionResult(ActionStatus.PUSHED, created_label=folder)
        if kind is ActionKind.SNOOZE:
            label_id = action.label_id or self._snooze_label_id(session, rate_limiter)
            return modify(add=[label_id], remove=["INBOX"])
        if kind is ActionKind.UNSNOOZE:
            label_id = action.label_id or self._snooze_label_id(session, rate_limiter)
            return modify(add=["INBOX", "UNREAD"], remove=[label_id])
        return ActionResult(ActionStatus.FAILED, error=f"unsupported action {kind}")

    def _snooze_label_id(self, session: Any, rate_limiter: RateLimiter | None) -> str:
        """Find or create the provider-visible snooze label (TDD D-12)."""
        for raw in gmail_client.list_labels(session, rate_limiter=rate_limiter):
            if raw.get("name") == SNOOZE_LABEL_NAME:
                return raw["id"]
        created = gmail_client.create_label(session, SNOOZE_LABEL_NAME, rate_limiter=rate_limiter)
        return created["id"]

    def send(
        self,
        session: Any,
        message: OutboundMessage,
        *,
        rate_limiter: RateLimiter | None = None,
    ) -> tuple[str, str]:
        return gmail_client.send_message(
            session,
            from_email=message.from_email,
            to=message.to,
            subject=message.subject,
            body_html=message.body_html,
            body_text=message.body_text,
            cc=message.cc,
            bcc=message.bcc,
            in_reply_to=message.in_reply_to,
            references=message.references,
            thread_id=message.thread_id,
            attachments=message.attachments,
            rate_limiter=rate_limiter,
        )

    # --- lifecycle ------------------------------------------------------

    def get_sync_status(self, session: Any) -> SyncStatus:
        profile = gmail_client.get_profile(session)
        return SyncStatus(
            email_address=str(profile.get("emailAddress", "")).lower(),
            cursor=str(profile.get("historyId")) if profile.get("historyId") else None,
            messages_total=profile.get("messagesTotal"),
            threads_total=profile.get("threadsTotal"),
        )

    def revoke(self, session: Any) -> None:
        import requests

        token = getattr(session, "token", None)
        if not token:
            return
        try:
            requests.post(
                "https://oauth2.googleapis.com/revoke",
                params={"token": token},
                headers={"content-type": "application/x-www-form-urlencoded"},
                timeout=10,
            )
        except Exception as exc:  # network failure is not fatal on disconnect
            log.warning("Token revoke failed: %s", exc)
