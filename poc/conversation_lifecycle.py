"""Timed conversation lifecycle (Conversation Base PRD §6.4 Timers; TDD §9.15–9.17).

One pass, run hourly by the scheduler and once at start, moves ``active``
and ``stale`` conversations by their silence:

* silence past the done threshold  → ``done`` (``done_reason = 'timer'``)
* silence past the stale threshold → ``stale``
* a ``stale`` conversation with fresh activity → ``active``

Silence is measured from the later of ``last_activity_at`` and a user
Reopen, so a conversation the user reopens is not closed again on the
next pass. ``done`` conversations are never read; dismissed ones are
skipped. Thresholds are the system settings ``conversation_stale_days``
and ``conversation_done_days``; a conversation's own ``stale_after_days``
or ``closed_after_days`` overrides them when set.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from .conversation_links import REOPEN_USER, STATUS_ACTIVE, STATUS_DONE
from .database import get_connection

log = logging.getLogger(__name__)

STATUS_STALE = "stale"
DONE_REASON_TIMER = "timer"

DEFAULT_STALE_DAYS = 14
DEFAULT_DONE_DAYS = 30
MIN_DAYS = 1
MAX_DAYS = 365


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def clamp_days(value, default: int) -> int:
    """Whole days between MIN_DAYS and MAX_DAYS; ``default`` when unusable."""
    try:
        val = int(value) if value not in (None, "") else default
    except (TypeError, ValueError):
        val = default
    return max(MIN_DAYS, min(MAX_DAYS, val))


def thresholds_for(customer_id: str | None) -> dict:
    """Effective tenant thresholds: ``{"stale_days", "done_days", "enabled"}``.

    The done threshold is never below the stale threshold.
    """
    stale = DEFAULT_STALE_DAYS
    done = DEFAULT_DONE_DAYS
    enabled = True
    if customer_id:
        from .settings import get_setting
        stale = clamp_days(get_setting(customer_id, "conversation_stale_days"), DEFAULT_STALE_DAYS)
        done = clamp_days(get_setting(customer_id, "conversation_done_days"), DEFAULT_DONE_DAYS)
        raw = get_setting(customer_id, "conversation_timers_enabled")
        enabled = str(raw or "true").lower() in ("true", "1", "yes")
    return {"stale_days": stale, "done_days": max(done, stale), "enabled": enabled}


def run_lifecycle_pass(*, now_iso: str | None = None) -> dict:
    """Apply the timed transitions once. Returns the counts moved."""
    now = _parse(now_iso) or datetime.now(timezone.utc)
    now_iso = now.isoformat()
    stats = {"checked": 0, "stale": 0, "reactivated": 0, "done": 0}
    cache: dict[str | None, dict] = {}

    with get_connection() as conn:
        rows = conn.execute(
            """SELECT id, customer_id, status, last_activity_at, reopened_at, reopened_reason,
                      stale_after_days, closed_after_days
               FROM conversations
               WHERE status IN (?, ?) AND COALESCE(dismissed, 0) = 0""",
            (STATUS_ACTIVE, STATUS_STALE),
        ).fetchall()

        for r in rows:
            cid = r["customer_id"]
            if cid not in cache:
                cache[cid] = thresholds_for(cid)
            th = cache[cid]
            if not th["enabled"]:
                continue
            last = _parse(r["last_activity_at"])
            if last is None:
                continue
            stats["checked"] += 1
            if r["reopened_reason"] == REOPEN_USER:
                reopened = _parse(r["reopened_at"])
                if reopened and reopened > last:
                    last = reopened
            silence = now - last
            stale_days = clamp_days(r["stale_after_days"], th["stale_days"])
            done_days = max(clamp_days(r["closed_after_days"], th["done_days"]), stale_days)

            if silence >= timedelta(days=done_days):
                conn.execute(
                    """UPDATE conversations
                       SET status = ?, done_at = ?, done_by = NULL, done_reason = ?,
                           reopened_at = NULL, reopened_reason = NULL, updated_at = ?
                       WHERE id = ?""",
                    (STATUS_DONE, now_iso, DONE_REASON_TIMER, now_iso, r["id"]),
                )
                stats["done"] += 1
            elif silence >= timedelta(days=stale_days):
                if r["status"] != STATUS_STALE:
                    conn.execute(
                        "UPDATE conversations SET status = ?, updated_at = ? WHERE id = ?",
                        (STATUS_STALE, now_iso, r["id"]),
                    )
                    stats["stale"] += 1
            elif r["status"] == STATUS_STALE:
                conn.execute(
                    "UPDATE conversations SET status = ?, updated_at = ? WHERE id = ?",
                    (STATUS_ACTIVE, now_iso, r["id"]),
                )
                stats["reactivated"] += 1

    if stats["stale"] or stats["reactivated"] or stats["done"]:
        log.info(
            "Conversation lifecycle pass: %d stale, %d reactivated, %d done (of %d checked)",
            stats["stale"], stats["reactivated"], stats["done"], stats["checked"],
        )
    return stats
