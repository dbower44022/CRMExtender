"""Conversation membership and the Done state (Conversation Entity TDD §9.8–9.13).

One function links communications to a conversation for every caller — mail
sync, outbound send, and manual assignment — so the activity roll-up and the
reactivation rule are one rule. Two more mark a conversation Done and reopen
it by user action.

Reactivation (Base PRD §6.4): a ``done`` conversation returns to ``active``
when a newly linked communication is inbound. Outbound never reopens.
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timezone

log = logging.getLogger(__name__)

STATUS_ACTIVE = "active"
STATUS_STALE = "stale"
STATUS_DONE = "done"

DONE_REASON_USER = "user"

REOPEN_INBOUND = "inbound"
REOPEN_USER = "user"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def link_communications(
    conn: sqlite3.Connection,
    conversation_id: str,
    communication_ids: list[str],
    *,
    assignment_source: str,
    reviewed: int | None = 1,
    confidence: float = 1.0,
    now: str | None = None,
) -> dict:
    """Link ``communication_ids`` to ``conversation_id`` and refresh the conversation.

    Inserts the membership rows (INSERT OR IGNORE), recomputes the
    communication count and the first/last activity timestamps from the
    full linked set, clears the summary stamp so the summarizer re-runs,
    and reopens a done conversation when any newly linked communication is
    inbound.

    :returns: ``{"linked": n, "reopened": bool}``.
    """
    now = now or _now_iso()
    linked = 0
    newly_linked: list[str] = []
    for cid in communication_ids:
        cur = conn.execute(
            """INSERT OR IGNORE INTO conversation_communications
               (conversation_id, communication_id, assignment_source, confidence, reviewed, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (conversation_id, cid, assignment_source, confidence, reviewed, now),
        )
        if cur.rowcount:
            linked += 1
            newly_linked.append(cid)

    if not newly_linked:
        return {"linked": 0, "reopened": False}

    stats = conn.execute(
        """SELECT COUNT(*) AS cnt, MIN(c.timestamp) AS first_dt, MAX(c.timestamp) AS last_dt
           FROM communications c
           JOIN conversation_communications cc ON cc.communication_id = c.id
           WHERE cc.conversation_id = ?""",
        (conversation_id,),
    ).fetchone()

    conn.execute(
        """UPDATE conversations
           SET communication_count = ?, first_activity_at = ?, last_activity_at = ?,
               first_message_at = ?, last_message_at = ?,
               ai_summarized_at = NULL, updated_at = ?
           WHERE id = ?""",
        (stats["cnt"], stats["first_dt"], stats["last_dt"],
         stats["first_dt"], stats["last_dt"], now, conversation_id),
    )

    reopened = False
    status_row = conn.execute(
        "SELECT status FROM conversations WHERE id = ?", (conversation_id,)
    ).fetchone()
    if status_row and status_row["status"] == STATUS_STALE:
        # Stale measures silence, so any new communication ends it (TDD §9.18).
        conn.execute(
            "UPDATE conversations SET status = ?, updated_at = ? WHERE id = ?",
            (STATUS_ACTIVE, now, conversation_id),
        )
    elif status_row and status_row["status"] == STATUS_DONE:
        placeholders = ",".join("?" * len(newly_linked))
        inbound = conn.execute(
            f"SELECT 1 FROM communications WHERE id IN ({placeholders}) "
            f"AND direction = 'inbound' LIMIT 1",
            newly_linked,
        ).fetchone()
        if inbound:
            conn.execute(
                """UPDATE conversations
                   SET status = ?, reopened_at = ?, reopened_reason = ?,
                       done_at = NULL, done_by = NULL, done_reason = NULL, updated_at = ?
                   WHERE id = ?""",
                (STATUS_ACTIVE, now, REOPEN_INBOUND, now, conversation_id),
            )
            reopened = True
            log.info("Conversation %s reopened by inbound communication", conversation_id)

    return {"linked": linked, "reopened": reopened}


def mark_done(
    conn: sqlite3.Connection,
    conversation_ids: list[str],
    *,
    user_id: str | None,
    now: str | None = None,
) -> list[str]:
    """Set ``status = 'done'`` on each conversation that is not already done.

    Records ``done_at``/``done_by``, clears the reopen pair, and sets
    ``updated_by``. :returns: the ids of the conversations changed.
    """
    now = now or _now_iso()
    changed: list[str] = []
    for conv_id in conversation_ids:
        cur = conn.execute(
            """UPDATE conversations
               SET status = ?, done_at = ?, done_by = ?, done_reason = ?,
                   reopened_at = NULL, reopened_reason = NULL,
                   updated_at = ?, updated_by = ?
               WHERE id = ? AND (status IS NULL OR status != ?)""",
            (STATUS_DONE, now, user_id, DONE_REASON_USER, now, user_id, conv_id, STATUS_DONE),
        )
        if cur.rowcount:
            changed.append(conv_id)
    return changed


def reopen(
    conn: sqlite3.Connection,
    conversation_ids: list[str],
    *,
    user_id: str | None,
    now: str | None = None,
) -> list[str]:
    """Return each done conversation to ``active`` by user action.

    Records ``reopened_at``/``reopened_reason = 'user'``, clears the done
    pair, and sets ``updated_by``. :returns: the ids changed.
    """
    now = now or _now_iso()
    changed: list[str] = []
    for conv_id in conversation_ids:
        cur = conn.execute(
            """UPDATE conversations
               SET status = ?, reopened_at = ?, reopened_reason = ?,
                   done_at = NULL, done_by = NULL, done_reason = NULL,
                   updated_at = ?, updated_by = ?
               WHERE id = ? AND status = ?""",
            (STATUS_ACTIVE, now, REOPEN_USER, now, user_id, conv_id, STATUS_DONE),
        )
        if cur.rowcount:
            changed.append(conv_id)
    return changed
