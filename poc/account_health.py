"""Account health and lifecycle (Mail Client MAIL-38).

``provider_accounts.auth_status`` is ``ok``, ``needs_reauth`` (the saved
sign-in failed to refresh; the owner must reconnect), or ``disconnected``
(the owner disconnected it and kept its mail). The scheduler skips the
last two. Each account run also records its first error, if any, so the
Accounts page can show an error badge.
"""

from __future__ import annotations

import logging
from pathlib import Path

from .models import _now_iso

log = logging.getLogger(__name__)

SKIPPED_STATUSES = ("needs_reauth", "disconnected")


def mark_needs_reauth(conn, account_id: str, reason: str) -> None:
    conn.execute(
        "UPDATE provider_accounts SET auth_status = 'needs_reauth', auth_error = ?, updated_at = ? WHERE id = ?",
        (reason[:500], _now_iso(), account_id),
    )


def clear_auth_status(conn, account_id: str) -> None:
    """After a successful reconnect: the account syncs again."""
    conn.execute(
        "UPDATE provider_accounts SET auth_status = 'ok', auth_error = NULL, is_active = 1, updated_at = ? WHERE id = ?",
        (_now_iso(), account_id),
    )


def record_sync_outcome(conn, account_id: str, errors: list[str] | None) -> None:
    """Keep the first error of the latest run, or clear it when the run was clean."""
    first = (errors or [None])[0]
    if first:
        conn.execute(
            "UPDATE provider_accounts SET last_sync_error = ?, last_sync_error_at = ? WHERE id = ?",
            (str(first)[:500], _now_iso(), account_id),
        )
    else:
        conn.execute(
            "UPDATE provider_accounts SET last_sync_error = NULL, last_sync_error_at = NULL WHERE id = ?",
            (account_id,),
        )


def _remove_token(path: str | None) -> None:
    if not path:
        return
    try:
        Path(path).unlink(missing_ok=True)
    except OSError as exc:
        log.warning("Could not remove token %s: %s", path, exc)


def disconnect_account(conn, account_id: str, *, delete_data: bool) -> dict:
    """Disconnect an account.

    ``delete_data`` false: the saved sign-in is removed, the account goes
    inactive with status ``disconnected``, and every message, conversation,
    and label stays as history. True: the account's messages, conversations,
    calendar events, labels, pending actions, and outbound mail are deleted
    with the account row. Returns counts of what was removed.
    """
    row = conn.execute("SELECT * FROM provider_accounts WHERE id = ?", (account_id,)).fetchone()
    if not row:
        raise LookupError("Account not found")
    acct = dict(row)
    _remove_token(acct.get("auth_token_path"))
    out = {"account_id": account_id, "deleted": delete_data}
    if not delete_data:
        conn.execute(
            "UPDATE provider_accounts SET is_active = 0, auth_status = 'disconnected', auth_error = NULL, "
            "auth_token_path = NULL, sync_cursor = NULL, updated_at = ? WHERE id = ?",
            (_now_iso(), account_id),
        )
        return out

    def count(sql: str) -> int:
        return conn.execute(sql, (account_id,)).fetchone()[0]

    out["communications"] = count("SELECT COUNT(*) FROM communications WHERE account_id = ?")
    out["conversations"] = count("SELECT COUNT(*) FROM conversations WHERE account_id = ?")
    out["events"] = count("SELECT COUNT(*) FROM events WHERE account_id = ?")
    # Order matters for foreign keys: outbound rows point at the account
    # without an ON DELETE action; message-level tables cascade.
    conn.execute(
        "DELETE FROM outbound_email_attachments WHERE outbound_email_id IN "
        "(SELECT id FROM outbound_email_queue WHERE from_account_id = ?)", (account_id,))
    conn.execute("DELETE FROM outbound_email_queue WHERE from_account_id = ?", (account_id,))
    conn.execute("UPDATE email_signatures SET provider_account_id = NULL WHERE provider_account_id = ?", (account_id,))
    conn.execute("DELETE FROM communications WHERE account_id = ?", (account_id,))
    conn.execute("DELETE FROM conversations WHERE account_id = ?", (account_id,))
    conn.execute("DELETE FROM events WHERE account_id = ?", (account_id,))
    conn.execute("DELETE FROM provider_accounts WHERE id = ?", (account_id,))
    return out
