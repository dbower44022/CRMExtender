"""Bulk summarization through the Message Batches API (Mail Client MAIL-49, TDD D-48).

When the post-sync pass finds more settled conversations than
``summarize_batch_threshold`` allows, it hands them to
:func:`submit_summary_batch`: one request per conversation, built by the
same :func:`poc.summarizer.build_summary_params` the live call uses, sent
as one batch at half price. The batch and its items are recorded in
``ai_batches`` / ``ai_batch_items`` so the live pass leaves those
conversations alone while the batch is open.

The scheduler calls :func:`poll_summary_batches` once a minute. A batch
that has ended is read back; each succeeded result is stored through
:func:`poc.sync.apply_summary` (the same step as a live summary) and its
usage recorded at batch pricing. Errored, expired and canceled items are
marked processed without a summary, which releases the conversation to
the next live pass.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from . import config
from .ai_usage import MODE_BATCH, record_usage
from .database import get_connection

log = logging.getLogger(__name__)

PURPOSE_SUMMARY = "summary"
#: Upper bound per batch, well under the API's 100,000-request limit.
MAX_REQUESTS_PER_BATCH = 10_000


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _client(client=None):
    if client is not None:
        return client
    import anthropic

    return anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)


def submit_summary_batch(items, *, customer_id: str | None = None, client=None) -> str | None:
    """Submit one Message Batch for ``items`` = [(conversation_id, Conversation, owner_email)].

    Returns the provider batch id, or ``None`` when there was nothing to send.
    """
    from .summarizer import build_summary_params

    items = list(items)[:MAX_REQUESTS_PER_BATCH]
    if not items:
        return None

    requests = []
    custom_ids: list[tuple[str, str]] = []
    for conv_id, conv, owner_email in items:
        custom_id = f"conv-{uuid.uuid4().hex}"
        requests.append({"custom_id": custom_id, "params": build_summary_params(conv, owner_email)})
        custom_ids.append((custom_id, conv_id))

    batch = _client(client).messages.batches.create(requests=requests)
    batch_id = batch.id
    now = _now_iso()
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO ai_batches (id, customer_id, purpose, model, status, submitted_count, created_at)
               VALUES (?, ?, ?, ?, 'in_progress', ?, ?)""",
            (batch_id, customer_id, PURPOSE_SUMMARY, config.CLAUDE_MODEL, len(custom_ids), now),
        )
        conn.executemany(
            "INSERT INTO ai_batch_items (batch_id, custom_id, conversation_id) VALUES (?, ?, ?)",
            [(batch_id, cid, conv_id) for cid, conv_id in custom_ids],
        )
    log.info("Submitted summary batch %s with %d conversation(s)", batch_id, len(custom_ids))
    return batch_id


def open_batches() -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM ai_batches WHERE processed_at IS NULL AND status != 'failed' ORDER BY created_at"
        ).fetchall()
    return [dict(r) for r in rows]


def poll_summary_batches(*, client=None, now_iso: str | None = None) -> dict:
    """Check every open batch; apply the results of those that have ended.

    Returns ``{"checked": n, "ended": n, "applied": n}``. Cheap when no
    batch is open: one SELECT and no network call.
    """
    out = {"checked": 0, "ended": 0, "applied": 0}
    pending = open_batches()
    if not pending:
        return out
    if not config.ANTHROPIC_API_KEY:
        return out
    now = now_iso or _now_iso()
    cl = _client(client)
    for b in pending:
        out["checked"] += 1
        try:
            remote = cl.messages.batches.retrieve(b["id"])
        except Exception as exc:
            log.warning("Could not retrieve batch %s: %s", b["id"], exc)
            with get_connection() as conn:
                conn.execute("UPDATE ai_batches SET last_checked_at = ?, error = ? WHERE id = ?",
                             (now, str(exc)[:500], b["id"]))
            continue
        counts = getattr(remote, "request_counts", None)
        with get_connection() as conn:
            conn.execute(
                """UPDATE ai_batches SET last_checked_at = ?, status = ?, succeeded = ?, errored = ?,
                          expired = ?, canceled = ?, ended_at = ?
                   WHERE id = ?""",
                (now, remote.processing_status,
                 getattr(counts, "succeeded", 0) or 0, getattr(counts, "errored", 0) or 0,
                 getattr(counts, "expired", 0) or 0, getattr(counts, "canceled", 0) or 0,
                 _iso(getattr(remote, "ended_at", None)), b["id"]),
            )
        if remote.processing_status != "ended":
            continue
        out["ended"] += 1
        try:
            out["applied"] += _apply_batch_results(b, cl, now)
        except Exception as exc:
            log.exception("Applying results of batch %s failed", b["id"])
            with get_connection() as conn:
                conn.execute("UPDATE ai_batches SET status = 'failed', error = ? WHERE id = ?",
                             (str(exc)[:500], b["id"]))
    return out


def _iso(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _apply_batch_results(batch: dict, cl, now: str) -> int:
    """Store every result of an ended batch. Returns summaries applied."""
    from .summarizer import parse_summary_text, response_text
    from .sync import apply_summary

    with get_connection() as conn:
        items = {r["custom_id"]: dict(r) for r in conn.execute(
            "SELECT * FROM ai_batch_items WHERE batch_id = ?", (batch["id"],)).fetchall()}

    applied = 0
    seen: set[str] = set()
    for result in cl.messages.batches.results(batch["id"]):
        item = items.get(result.custom_id)
        if item is None:
            continue
        seen.add(result.custom_id)
        conv_id = item["conversation_id"]
        rtype = result.result.type
        error: str | None = None
        if rtype == "succeeded":
            msg = result.result.message
            with get_connection() as conn:
                record_usage(
                    conn, purpose=PURPOSE_SUMMARY, mode=MODE_BATCH,
                    model=getattr(msg, "model", None) or batch["model"],
                    usage=getattr(msg, "usage", None),
                    conversation_id=conv_id, batch_id=batch["id"],
                    request_id=getattr(msg, "id", None), customer_id=batch.get("customer_id"),
                )
            summary = parse_summary_text(response_text(msg.content), conv_id)
            if summary.error:
                error = summary.error
            else:
                apply_summary(conv_id, summary)
                applied += 1
        elif rtype == "errored":
            err = getattr(result.result, "error", None)
            error = str(getattr(err, "message", None) or getattr(err, "type", None) or err)[:500]
        else:
            error = rtype
        with get_connection() as conn:
            conn.execute(
                "UPDATE ai_batch_items SET result_type = ?, error = ?, processed_at = ? "
                "WHERE batch_id = ? AND custom_id = ?",
                (rtype, error, now, batch["id"], result.custom_id),
            )

    # Requests the results stream never mentioned are released as well.
    missing = set(items) - seen
    with get_connection() as conn:
        if missing:
            conn.executemany(
                "UPDATE ai_batch_items SET result_type = 'missing', processed_at = ? "
                "WHERE batch_id = ? AND custom_id = ?",
                [(now, batch["id"], cid) for cid in missing],
            )
        conn.execute("UPDATE ai_batches SET processed_at = ?, status = 'ended' WHERE id = ?",
                     (now, batch["id"]))
    log.info("Batch %s: %d summar%s applied, %d item(s) released to the live pass",
             batch["id"], applied, "y" if applied == 1 else "ies", len(items) - applied)
    return applied
