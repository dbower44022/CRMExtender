"""Awaiting-reply tracking (Mail Client MAIL-47; TDD D-46).

A thread is *awaiting a reply* when its newest current message was sent by
the mailbox owner to at least one recipient, at least
``mail_awaiting_reply_days`` days ago (default 3) but within the last
``mail_awaiting_window_days`` (default 30; older silence is not a reminder,
it is history), and nothing has arrived since. The state is computed from the mirror on every read, so a reply
clears it the moment the sync stores the answer. The owner can stop
tracking a thread ("dismiss"); the row in ``mail_awaiting_dismissed`` is
dropped again by "restore".
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

DEFAULT_DAYS = 3
MIN_DAYS, MAX_DAYS = 1, 60
DEFAULT_WINDOW = 30
MIN_WINDOW, MAX_WINDOW = 7, 365

#: Predicate over ``communications c``: c is the owner's last word in its
#: thread, sent to someone, old enough but inside the window, not
#: trashed/spam/draft, and the thread is not dismissed. Bind
#: ``(cutoff_iso, window_iso)`` in that order.
AWAITING_PREDICATE = """
    c.direction = 'outbound' AND c.is_current = 1 AND c.is_archived = 0
    AND c.timestamp <= ? AND c.timestamp >= ?
    AND EXISTS (SELECT 1 FROM communication_participants cp
                WHERE cp.communication_id = c.id AND cp.role IN ('to', 'cc'))
    AND NOT EXISTS (SELECT 1 FROM communications c2
                    WHERE c2.account_id = c.account_id AND c2.is_current = 1
                      AND COALESCE(c2.provider_thread_id, c2.id) = COALESCE(c.provider_thread_id, c.id)
                      AND c2.timestamp > c.timestamp)
    AND NOT EXISTS (SELECT 1 FROM communication_labels cl JOIN mailbox_labels ml ON ml.id = cl.label_id
                    WHERE cl.communication_id = c.id AND ml.kind IN ('trash', 'spam', 'drafts'))
    AND NOT EXISTS (SELECT 1 FROM mail_awaiting_dismissed d
                    WHERE d.account_id = c.account_id
                      AND d.thread_id = COALESCE(c.provider_thread_id, c.id))
"""


def _now() -> datetime:
    return datetime.now(timezone.utc)


def awaiting_days(customer_id: str | None) -> int:
    from .settings import get_setting
    if not customer_id:
        return DEFAULT_DAYS
    try:
        raw = get_setting(customer_id, "mail_awaiting_reply_days")
        val = int(raw) if raw else DEFAULT_DAYS
    except (TypeError, ValueError):
        val = DEFAULT_DAYS
    return max(MIN_DAYS, min(MAX_DAYS, val))


def awaiting_window(customer_id: str | None) -> int:
    from .settings import get_setting
    if not customer_id:
        return DEFAULT_WINDOW
    try:
        raw = get_setting(customer_id, "mail_awaiting_window_days")
        val = int(raw) if raw else DEFAULT_WINDOW
    except (TypeError, ValueError):
        val = DEFAULT_WINDOW
    return max(MIN_WINDOW, min(MAX_WINDOW, val))


def cutoff_iso(days: int, now: datetime | None = None) -> str:
    return ((now or _now()) - timedelta(days=days)).isoformat()


def bounds(days: int, window: int | None = None, now: datetime | None = None) -> tuple[str, str]:
    """``(cutoff_iso, window_iso)``: sent before the first, after the second."""
    w = max(days + 1, window or DEFAULT_WINDOW)
    return cutoff_iso(days, now), cutoff_iso(w, now)


def days_waiting(since_iso: str, now: datetime | None = None) -> int:
    try:
        since = datetime.fromisoformat(since_iso)
    except (TypeError, ValueError):
        return 0
    if since.tzinfo is None:
        since = since.replace(tzinfo=timezone.utc)
    return max(0, int(((now or _now()) - since).total_seconds() // 86400))


def counts(conn, account_ids: list[str], days: int, window: int | None = None,
           now: datetime | None = None) -> dict[str, int]:
    """``{account_id: threads awaiting a reply}``."""
    if not account_ids:
        return {}
    placeholders = ",".join("?" * len(account_ids))
    rows = conn.execute(
        f"""SELECT c.account_id, COUNT(DISTINCT COALESCE(c.provider_thread_id, c.id)) AS n
            FROM communications c
            WHERE c.account_id IN ({placeholders}) AND c.channel = 'email' AND {AWAITING_PREDICATE}
            GROUP BY c.account_id""",
        (*account_ids, *bounds(days, window, now)),
    )
    return {r["account_id"]: r["n"] for r in rows}


def dismiss(conn, account_id: str, thread_id: str, user_id: str | None) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO mail_awaiting_dismissed (account_id, thread_id, dismissed_at, created_by) "
        "VALUES (?, ?, ?, ?)", (account_id, thread_id, _now().isoformat(), user_id))


def restore(conn, account_id: str, thread_id: str) -> int:
    return conn.execute(
        "DELETE FROM mail_awaiting_dismissed WHERE account_id = ? AND thread_id = ?",
        (account_id, thread_id)).rowcount
