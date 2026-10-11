"""Snooze: hide a thread until a chosen time, then bring it back unread
(Mail Client MAIL-17, KP-MAIL-06; TDD D-44).

A snooze is a row in ``mail_snoozes`` plus a queued ``snooze`` action: the
local effect drops the Inbox label at once, the adapter archives the
thread at the provider and applies the ``CRMExtender/Snoozed`` label so
other clients show the state. The scheduler calls :func:`return_due`
every tick; a due snooze queues ``unsnooze`` (Inbox back, unread, label
removed) and publishes a ``mail.new`` event so the browser's new-mail
pop-up announces the return.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from .database import get_connection

log = logging.getLogger(__name__)


class SnoozeError(ValueError):
    """Bad snooze input (missing or past return time)."""


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now().isoformat()


def parse_return_at(value, *, now: datetime | None = None) -> str:
    """Validate a return time: ISO 8601, in the future. Returns UTC ISO text."""
    if not value or not isinstance(value, str):
        raise SnoozeError("return_at required (ISO 8601 date and time)")
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise SnoozeError("return_at must be an ISO 8601 date and time") from exc
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    dt = dt.astimezone(timezone.utc)
    if dt <= (now or _now()):
        raise SnoozeError("return_at must be in the future")
    return dt.isoformat()


def _thread_ids(conn, account_id: str, provider_message_ids: list[str]) -> list[str]:
    if not provider_message_ids:
        return []
    placeholders = ",".join("?" * len(provider_message_ids))
    rows = conn.execute(
        f"SELECT DISTINCT COALESCE(provider_thread_id, id) AS tid FROM communications "
        f"WHERE account_id = ? AND provider_message_id IN ({placeholders})",
        (account_id, *provider_message_ids),
    ).fetchall()
    return [r["tid"] for r in rows]


def record_snooze(conn, account_id: str, provider_message_ids: list[str], return_at: str,
                  created_by: str | None) -> list[str]:
    """Open a snooze for every thread the messages belong to; an earlier
    open snooze on the same thread is replaced. Returns the thread ids."""
    threads = _thread_ids(conn, account_id, provider_message_ids)
    now = _now_iso()
    for tid in threads:
        conn.execute(
            "UPDATE mail_snoozes SET status = 'cancelled', returned_at = ? "
            "WHERE account_id = ? AND thread_id = ? AND status = 'snoozed'", (now, account_id, tid))
        conn.execute(
            "INSERT INTO mail_snoozes (id, account_id, thread_id, return_at, status, created_by, created_at) "
            "VALUES (?, ?, ?, ?, 'snoozed', ?, ?)",
            (str(uuid.uuid4()), account_id, tid, return_at, created_by, now))
    return threads


def clear_snooze(conn, account_id: str, provider_message_ids: list[str], *, status: str = "returned") -> int:
    """Close the open snooze on the messages' threads. Returns rows closed."""
    threads = _thread_ids(conn, account_id, provider_message_ids)
    if not threads:
        return 0
    placeholders = ",".join("?" * len(threads))
    cur = conn.execute(
        f"UPDATE mail_snoozes SET status = ?, returned_at = ? "
        f"WHERE account_id = ? AND thread_id IN ({placeholders}) AND status = 'snoozed'",
        (status, _now_iso(), account_id, *threads))
    return cur.rowcount


def active_snoozes(conn, account_ids: list[str]) -> dict[tuple[str, str], str]:
    """``{(account_id, thread_id): return_at}`` for every open snooze."""
    if not account_ids:
        return {}
    placeholders = ",".join("?" * len(account_ids))
    return {(r["account_id"], r["thread_id"]): r["return_at"] for r in conn.execute(
        f"SELECT account_id, thread_id, return_at FROM mail_snoozes "
        f"WHERE status = 'snoozed' AND account_id IN ({placeholders})", account_ids)}


def return_due(*, now_iso: str | None = None) -> list[dict]:
    """Bring back every snooze whose return time has passed.

    Each returned thread gets an ``unsnooze`` action queued for the
    provider (its local effect restores the Inbox label and marks the
    messages unread) and a ``mail.new`` event. Returns one dict per
    thread: ``{"account_id", "thread_id", "return_at"}``.
    """
    from . import events
    from .mail_actions import MailActionError, enqueue
    from .mail_threads import _display_name, _snippet

    now_iso = now_iso or _now_iso()
    returned: list[dict] = []
    with get_connection() as conn:
        due = [dict(r) for r in conn.execute(
            "SELECT * FROM mail_snoozes WHERE status = 'snoozed' AND return_at <= ? ORDER BY return_at",
            (now_iso,))]
        for row in due:
            msgs = [dict(r) for r in conn.execute(
                """SELECT c.id, c.provider_message_id, c.sender_address, c.sender_name, c.subject,
                          c.snippet, c.timestamp, c.provider_thread_id
                   FROM communications c
                   WHERE c.account_id = ? AND COALESCE(c.provider_thread_id, c.id) = ? AND c.is_current = 1
                   ORDER BY c.timestamp DESC""", (row["account_id"], row["thread_id"]))]
            ids = [m["id"] for m in msgs]
            try:
                if ids:
                    enqueue(conn, account_id=row["account_id"], kind="unsnooze",
                            communication_ids=ids, created_by=row["created_by"])
                else:
                    conn.execute("UPDATE mail_snoozes SET status = 'returned', returned_at = ? WHERE id = ?",
                                 (now_iso, row["id"]))
            except MailActionError as exc:
                log.warning("Snooze return for thread %s failed: %s", row["thread_id"], exc)
                conn.execute("UPDATE mail_snoozes SET status = 'returned', returned_at = ? WHERE id = ?",
                             (now_iso, row["id"]))
                continue
            acct = conn.execute("SELECT email_address FROM provider_accounts WHERE id = ?",
                                (row["account_id"],)).fetchone()
            latest = msgs[0] if msgs else {}
            returned.append({"account_id": row["account_id"], "thread_id": row["thread_id"],
                             "return_at": row["return_at"]})
            if latest:
                events.publish(
                    "mail.new", account_id=row["account_id"], email=acct["email_address"] if acct else None,
                    count=1, reason="snooze_returned",
                    items=[{
                        "communication_id": latest["id"], "thread_id": row["thread_id"],
                        "sender_address": latest["sender_address"],
                        "sender_name": _display_name(latest["sender_name"], latest["sender_address"]),
                        "known_contact": True,
                        "subject": latest["subject"] or "(no subject)",
                        "snippet": "Back from snooze: " + _snippet(latest["snippet"])[:120],
                        "timestamp": latest["timestamp"],
                    }],
                )
    if returned:
        log.info("Snooze return: %d thread(s) back in the inbox", len(returned))
    return returned
