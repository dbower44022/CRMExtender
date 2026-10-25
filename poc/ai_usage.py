"""Token accounting for Anthropic calls (Mail Client MAIL-49, TDD D-48).

Every live call and every batch result is recorded in ``ai_usage`` with its
token counts and the cost estimated by :mod:`poc.ai_pricing`. The report
behind Settings → System aggregates that ledger for today, the last 30
days and all time, by model and by mode (live or batch), and lists the
batches still open.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from . import config
from .ai_pricing import PRICE_TABLE_DATE, estimate_cost

log = logging.getLogger(__name__)

MODE_LIVE = "live"
MODE_BATCH = "batch"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _usage_field(usage, name: str) -> int:
    """Read a token count from an SDK ``Usage`` object or a plain dict."""
    if usage is None:
        return 0
    if isinstance(usage, dict):
        val = usage.get(name)
    else:
        val = getattr(usage, name, None)
    try:
        return int(val or 0)
    except (TypeError, ValueError):
        return 0


def record_usage(
    conn,
    *,
    purpose: str,
    mode: str,
    model: str,
    usage,
    conversation_id: str | None = None,
    batch_id: str | None = None,
    request_id: str | None = None,
    customer_id: str | None = None,
    occurred_at: str | None = None,
) -> str:
    """Insert one ledger row and return its id. ``usage`` is the response's
    ``usage`` object (or a dict with the same field names)."""
    input_tokens = _usage_field(usage, "input_tokens")
    output_tokens = _usage_field(usage, "output_tokens")
    cache_w = _usage_field(usage, "cache_creation_input_tokens")
    cache_r = _usage_field(usage, "cache_read_input_tokens")
    cost = estimate_cost(model, input_tokens, output_tokens, cache_w, cache_r,
                         batch=(mode == MODE_BATCH))
    row_id = str(uuid.uuid4())
    now = _now_iso()
    conn.execute(
        """INSERT INTO ai_usage
           (id, occurred_at, customer_id, purpose, mode, model, conversation_id, batch_id,
            request_id, input_tokens, output_tokens, cache_creation_input_tokens,
            cache_read_input_tokens, cost_usd, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (row_id, occurred_at or now, customer_id, purpose, mode, model, conversation_id,
         batch_id, request_id, input_tokens, output_tokens, cache_w, cache_r, cost, now),
    )
    return row_id


_EMPTY = {"calls": 0, "input_tokens": 0, "output_tokens": 0,
          "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0,
          "cost_usd": 0.0, "unpriced_calls": 0}

_SUM_SQL = (
    "COUNT(*), COALESCE(SUM(input_tokens), 0), COALESCE(SUM(output_tokens), 0), "
    "COALESCE(SUM(cache_creation_input_tokens), 0), COALESCE(SUM(cache_read_input_tokens), 0), "
    "COALESCE(SUM(cost_usd), 0), SUM(CASE WHEN cost_usd IS NULL THEN 1 ELSE 0 END)"
)


def _totals(row) -> dict:
    if not row:
        return dict(_EMPTY)
    return {
        "calls": int(row[0] or 0),
        "input_tokens": int(row[1] or 0),
        "output_tokens": int(row[2] or 0),
        "cache_creation_input_tokens": int(row[3] or 0),
        "cache_read_input_tokens": int(row[4] or 0),
        "cost_usd": round(float(row[5] or 0.0), 4),
        "unpriced_calls": int(row[6] or 0),
    }


def _local_day_start(now: datetime) -> datetime:
    """Midnight of the current day in the display timezone, as UTC."""
    try:
        tz = ZoneInfo(config.CRM_TIMEZONE)
    except Exception:
        tz = timezone.utc
    local = now.astimezone(tz)
    start = local.replace(hour=0, minute=0, second=0, microsecond=0)
    return start.astimezone(timezone.utc)


def usage_report(conn, *, now: datetime | None = None) -> dict:
    """Aggregate the ledger for Settings → System."""
    now = now or datetime.now(timezone.utc)
    today_start = _local_day_start(now).isoformat()
    month_start = (now - timedelta(days=30)).isoformat()

    periods = {}
    for key, since in (("today", today_start), ("last_30_days", month_start), ("all_time", None)):
        if since:
            row = conn.execute(f"SELECT {_SUM_SQL} FROM ai_usage WHERE occurred_at >= ?", (since,)).fetchone()
        else:
            row = conn.execute(f"SELECT {_SUM_SQL} FROM ai_usage").fetchone()
        periods[key] = _totals(row)

    by_model = []
    for r in conn.execute(
        f"SELECT model, mode, {_SUM_SQL} FROM ai_usage WHERE occurred_at >= ? "
        "GROUP BY model, mode ORDER BY model, mode", (month_start,)
    ).fetchall():
        entry = _totals(tuple(r)[2:])
        entry.update(model=r[0], mode=r[1])
        by_model.append(entry)

    batches = []
    for r in conn.execute(
        """SELECT id, purpose, model, status, submitted_count, succeeded, errored, expired, canceled,
                  created_at, last_checked_at, ended_at, processed_at, error
           FROM ai_batches
           WHERE processed_at IS NULL OR created_at >= ?
           ORDER BY created_at DESC LIMIT 20""", (month_start,)
    ).fetchall():
        batches.append({
            "id": r[0], "purpose": r[1], "model": r[2], "status": r[3],
            "submitted_count": r[4], "succeeded": r[5], "errored": r[6], "expired": r[7],
            "canceled": r[8], "created_at": r[9], "last_checked_at": r[10], "ended_at": r[11],
            "processed_at": r[12], "error": r[13],
        })

    return {
        "price_table_date": PRICE_TABLE_DATE,
        "model": config.CLAUDE_MODEL,
        "generated_at": now.isoformat(),
        "periods": periods,
        "by_model_30_days": by_model,
        "batches": batches,
    }
