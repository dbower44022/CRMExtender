"""Historical mailbox backfill (Mail Client MAIL-11; TDD D-43).

The initial sync stores the account's recent window (``backfill_query``,
default ``newer_than:90d``). This job then walks backwards from the oldest
stored message, one batch per sync run, until the provider reports the
mailbox start. The checkpoint lives on ``provider_accounts``
(``backfill_cursor``), so an interrupted job resumes where it stopped and a
re-fetched message is deduplicated by ``provider_message_id`` like any
other re-seen message.

Settings (system scope): ``mail_backfill_enabled`` (default true) and
``mail_backfill_batch_size`` (default 200, clamped 10–500). Disabling stops
the job at its next checkpoint; re-enabling resumes.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from .database import get_connection

log = logging.getLogger(__name__)

DEFAULT_BATCH = 200
MIN_BATCH, MAX_BATCH = 10, 500


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def backfill_settings(customer_id: str | None) -> tuple[bool, int]:
    """``(enabled, batch_size)`` for the customer, with defaults."""
    from .settings import get_setting
    enabled, batch = True, DEFAULT_BATCH
    if customer_id:
        raw = get_setting(customer_id, "mail_backfill_enabled")
        if raw is not None:
            enabled = str(raw).lower() != "false"
        try:
            raw_b = get_setting(customer_id, "mail_backfill_batch_size")
            if raw_b:
                batch = int(raw_b)
        except (TypeError, ValueError):
            batch = DEFAULT_BATCH
    return enabled, max(MIN_BATCH, min(MAX_BATCH, batch))


def start_cursor(conn, account_id: str) -> str | None:
    """``"<oldest stored epoch>|"`` or None when nothing is stored yet."""
    row = conn.execute(
        "SELECT MIN(timestamp) AS ts FROM communications WHERE account_id = ? AND channel = 'email'",
        (account_id,),
    ).fetchone()
    if not row or not row["ts"]:
        return None
    epoch = int(datetime.fromisoformat(row["ts"]).timestamp())
    return f"{epoch}|"


def run_backfill_batch(
    account: dict,
    session,
    provider,
    *,
    customer_id: str | None,
    user_id: str | None,
    rate_limiter=None,
    batch: int | None = None,
) -> dict:
    """Fetch and store one batch of older mail for ``account``.

    Returns ``{"status", "fetched", "stored", "done"}`` where ``status`` is
    ``ran``, ``done`` (already complete), ``disabled``, or ``not_ready``
    (initial sync pending or nothing stored). Never raises for an empty
    batch; provider errors propagate to the caller's error list.
    """
    from .sync import _store_thread, load_contact_index

    enabled, size = backfill_settings(customer_id)
    size = batch or size
    account_id = account["id"]
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM provider_accounts WHERE id = ?", (account_id,)).fetchone()
        row = dict(row) if row else {}
    out = {"status": "ran", "fetched": 0, "stored": 0, "done": bool(row.get("backfill_done"))}
    if not row or not row.get("initial_sync_done"):
        out["status"] = "not_ready"
        return out
    if row.get("backfill_done"):
        out["status"] = "done"
        return out
    if not enabled:
        out["status"] = "disabled"
        return out

    cursor = row.get("backfill_cursor")
    if not cursor:
        with get_connection() as conn:
            cursor = start_cursor(conn, account_id)
        if not cursor:
            out["status"] = "not_ready"
            return out

    messages, next_cursor = provider.fetch_backfill(
        session, cursor, batch=size, rate_limiter=rate_limiter,
    )
    out["fetched"] = len(messages)

    # Group into threads, oldest message first (TDD D-16), and store.
    groups: dict[str, list] = {}
    for m in messages:
        groups.setdefault(m.thread_id or m.message_id, []).append(m)
    contact_index = load_contact_index()
    email_addr = row.get("email_address") or account.get("email_address", "")
    with get_connection() as conn:
        before = conn.execute(
            "SELECT COUNT(*) FROM communications WHERE account_id = ?", (account_id,)).fetchone()[0]
        for thread in groups.values():
            thread.sort(key=lambda m: (m.date or datetime.min.replace(tzinfo=timezone.utc)))
            _store_thread(conn, account_id, email_addr, thread, contact_index,
                          customer_id=customer_id, created_by=user_id)
        after = conn.execute(
            "SELECT COUNT(*) FROM communications WHERE account_id = ?", (account_id,)).fetchone()[0]
        out["stored"] = max(0, after - before)
        done = next_cursor is None
        conn.execute(
            """UPDATE provider_accounts
               SET backfill_cursor = ?, backfill_done = ?,
                   backfill_messages = backfill_messages + ?, backfill_updated_at = ?, updated_at = ?
               WHERE id = ?""",
            (next_cursor if not done else cursor, 1 if done else 0, out["stored"], _now_iso(), _now_iso(), account_id),
        )
    out["done"] = done
    log.info("Backfill %s: fetched %d, stored %d, %s", email_addr, out["fetched"], out["stored"],
             "complete" if done else "checkpoint saved")
    return out
