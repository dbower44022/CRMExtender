"""Mail action outbox (Mail Client MAIL-09 / MAIL-14; TDD D-04).

A user action on mail — mark read, star, archive, trash, label — is
applied to the local mirror immediately so the interface responds at
once, and queued in ``mail_actions`` to be pushed to the provider in
creation order. Pushes retry with exponential backoff; a failure that
cannot succeed on retry, or one that exhausts the attempt budget, is
dead-lettered as ``failed`` and surfaced for the user to retry or
discard. Discarding reverts the local change.

Entry points:

- :func:`enqueue` — apply locally and queue (called by the mail API).
- :func:`push_pending` — the worker for one account (called before each
  account's sync, and by the retry endpoint).
- :func:`retry_action` / :func:`discard_action` — user resolution of a
  dead-lettered row.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from .database import get_connection
from .mail_state import ensure_labels
from .models import _now_iso
from .providers import Action, ActionKind, ActionStatus, MailProvider

log = logging.getLogger(__name__)

#: Attempts before a transient failure is dead-lettered (``mail.action_retry_max``).
DEFAULT_RETRY_MAX = 8
#: First backoff interval; doubles per attempt up to BACKOFF_CAP.
BACKOFF_BASE = timedelta(seconds=30)
BACKOFF_CAP = timedelta(hours=1)

#: Action kinds the outbox accepts from the API. Snooze/unsnooze are
#: MAIL-17 (payload ``return_at``); create_label is applied synchronously by MAIL-29.
ENQUEUEABLE = {
    ActionKind.MARK_READ, ActionKind.MARK_UNREAD,
    ActionKind.STAR, ActionKind.UNSTAR,
    ActionKind.ARCHIVE, ActionKind.UNARCHIVE,
    ActionKind.TRASH, ActionKind.UNTRASH,
    ActionKind.SPAM, ActionKind.UNSPAM,
    ActionKind.ADD_LABEL, ActionKind.REMOVE_LABEL, ActionKind.MOVE,
    ActionKind.SNOOZE, ActionKind.UNSNOOZE,
}

#: Each kind's local effect, as (flag updates, provider labels added, provider labels removed).
_LOCAL_EFFECT: dict[ActionKind, tuple[dict[str, int], list[str], list[str]]] = {
    ActionKind.MARK_READ:   ({"is_read": 1}, [], []),
    ActionKind.MARK_UNREAD: ({"is_read": 0}, [], []),
    ActionKind.STAR:        ({"is_starred": 1}, [], []),
    ActionKind.UNSTAR:      ({"is_starred": 0}, [], []),
    ActionKind.ARCHIVE:     ({}, [], ["INBOX"]),
    ActionKind.UNARCHIVE:   ({}, ["INBOX"], []),
    ActionKind.TRASH:       ({"is_archived": 1}, ["TRASH"], ["INBOX"]),
    ActionKind.UNTRASH:     ({"is_archived": 0}, ["INBOX"], ["TRASH"]),
    ActionKind.SPAM:        ({}, ["SPAM"], ["INBOX"]),
    ActionKind.UNSPAM:      ({}, ["INBOX"], ["SPAM"]),
    # The provider-side snooze label is found or created by the adapter at
    # push time; locally the Snoozed folder is the mail_snoozes table (MAIL-17).
    ActionKind.SNOOZE:      ({}, [], ["INBOX"]),
    ActionKind.UNSNOOZE:    ({"is_read": 0}, ["INBOX"], []),
}

_INVERSE: dict[ActionKind, ActionKind] = {
    ActionKind.MARK_READ: ActionKind.MARK_UNREAD, ActionKind.MARK_UNREAD: ActionKind.MARK_READ,
    ActionKind.STAR: ActionKind.UNSTAR, ActionKind.UNSTAR: ActionKind.STAR,
    ActionKind.ARCHIVE: ActionKind.UNARCHIVE, ActionKind.UNARCHIVE: ActionKind.ARCHIVE,
    ActionKind.TRASH: ActionKind.UNTRASH, ActionKind.UNTRASH: ActionKind.TRASH,
    ActionKind.SPAM: ActionKind.UNSPAM, ActionKind.UNSPAM: ActionKind.SPAM,
    ActionKind.ADD_LABEL: ActionKind.REMOVE_LABEL, ActionKind.REMOVE_LABEL: ActionKind.ADD_LABEL,
    ActionKind.SNOOZE: ActionKind.UNSNOOZE, ActionKind.UNSNOOZE: ActionKind.SNOOZE,
}


class MailActionError(ValueError):
    """Bad enqueue input (unknown kind, no targets, label required)."""


# ---------------------------------------------------------------------------
# Local (optimistic) application
# ---------------------------------------------------------------------------

def _comm_rows(conn, account_id: str, provider_ids: list[str]) -> list[dict]:
    if not provider_ids:
        return []
    placeholders = ",".join("?" * len(provider_ids))
    return [dict(r) for r in conn.execute(
        f"SELECT id, provider_message_id FROM communications "
        f"WHERE account_id = ? AND provider_message_id IN ({placeholders})",
        (account_id, *provider_ids),
    )]


def apply_local(
    conn,
    account_id: str,
    kind: ActionKind,
    provider_ids: list[str],
    *,
    label_id: str | None = None,
    payload: dict | None = None,
) -> int:
    """Apply ``kind`` to the mirror rows for ``provider_ids``. Returns rows touched."""
    flags: dict[str, int] = {}
    add: list[str] = []
    remove: list[str] = []
    if kind in _LOCAL_EFFECT:
        f, a, r = _LOCAL_EFFECT[kind]
        flags, add, remove = dict(f), list(a), list(r)
    elif kind is ActionKind.ADD_LABEL:
        add = [label_id] if label_id else []
    elif kind is ActionKind.REMOVE_LABEL:
        remove = [label_id] if label_id else []
    elif kind is ActionKind.MOVE:
        add = [label_id] if label_id else []
        remove = list((payload or {}).get("from_label_ids") or ["INBOX"])
    else:
        raise MailActionError(f"{kind.value} has no local effect")

    rows = _comm_rows(conn, account_id, provider_ids)
    if not rows:
        return 0
    now = _now_iso()
    mapping = ensure_labels(conn, account_id, add) if add else {}
    for row in rows:
        cid = row["id"]
        if flags:
            sets = ", ".join(f"{k} = ?" for k in flags)
            conn.execute(
                f"UPDATE communications SET {sets}, updated_at = ? WHERE id = ?",
                (*flags.values(), now, cid),
            )
        for lid in add:
            if lid in mapping:
                conn.execute(
                    "INSERT OR IGNORE INTO communication_labels (communication_id, label_id) VALUES (?, ?)",
                    (cid, mapping[lid]),
                )
        if remove:
            placeholders = ",".join("?" * len(remove))
            conn.execute(
                f"""DELETE FROM communication_labels
                    WHERE communication_id = ? AND label_id IN (
                        SELECT id FROM mailbox_labels
                        WHERE account_id = ? AND provider_label_id IN ({placeholders}))""",
                (cid, account_id, *remove),
            )
    return len(rows)


def _inverse(kind: ActionKind, payload: dict | None) -> tuple[ActionKind, dict | None]:
    if kind is ActionKind.MOVE:
        # Undo a move: put the message back where it came from.
        frm = (payload or {}).get("from_label_ids") or ["INBOX"]
        return ActionKind.MOVE, {"from_label_ids": [(payload or {}).get("to_label_id")], "to": frm}
    return _INVERSE[kind], payload


# ---------------------------------------------------------------------------
# Enqueue
# ---------------------------------------------------------------------------

def _row(conn, action_id: str) -> dict | None:
    r = conn.execute("SELECT * FROM mail_actions WHERE id = ?", (action_id,)).fetchone()
    return _decode(dict(r)) if r else None


def _decode(d: dict) -> dict:
    d["target_ids"] = json.loads(d["target_ids"]) if d.get("target_ids") else []
    d["payload"] = json.loads(d["payload"]) if d.get("payload") else None
    return d


def enqueue(
    conn,
    *,
    account_id: str,
    kind: str | ActionKind,
    communication_ids: list[str] | None = None,
    provider_message_ids: list[str] | None = None,
    label_id: str | None = None,
    payload: dict | None = None,
    created_by: str | None = None,
) -> dict:
    """Apply an action locally and queue it for the provider.

    Targets may be given as local communication ids or provider message
    ids; both are resolved to provider ids for the queue row. ``label_id``
    is the *provider* label id (the adapter's vocabulary). Raises
    :class:`MailActionError` on bad input.
    """
    try:
        k = kind if isinstance(kind, ActionKind) else ActionKind(str(kind))
    except ValueError as exc:
        raise MailActionError(f"unknown action {kind!r}") from exc
    if k not in ENQUEUEABLE:
        raise MailActionError(f"{k.value} cannot be queued")
    if k in (ActionKind.ADD_LABEL, ActionKind.REMOVE_LABEL, ActionKind.MOVE) and not label_id:
        raise MailActionError("label_id required")

    targets: list[str] = list(provider_message_ids or [])
    if communication_ids:
        placeholders = ",".join("?" * len(communication_ids))
        for r in conn.execute(
            f"SELECT provider_message_id FROM communications "
            f"WHERE account_id = ? AND id IN ({placeholders}) AND provider_message_id IS NOT NULL",
            (account_id, *communication_ids),
        ):
            targets.append(r["provider_message_id"])
    targets = list(dict.fromkeys(t for t in targets if t))
    if not targets:
        raise MailActionError("no target messages in this account")

    if k is ActionKind.MOVE:
        payload = dict(payload or {})
        payload.setdefault("to_label_id", label_id)
    return_at: str | None = None
    if k is ActionKind.SNOOZE:
        from .mail_snooze import SnoozeError, parse_return_at
        try:
            return_at = parse_return_at((payload or {}).get("return_at"))
        except SnoozeError as exc:
            raise MailActionError(str(exc)) from exc
        payload = dict(payload or {}, return_at=return_at)

    apply_local(conn, account_id, k, targets, label_id=label_id, payload=payload)
    if k is ActionKind.SNOOZE:
        from .mail_snooze import record_snooze
        record_snooze(conn, account_id, targets, return_at, created_by)
    elif k is ActionKind.UNSNOOZE:
        from .mail_snooze import clear_snooze
        clear_snooze(conn, account_id, targets)

    now = _now_iso()
    action_id = str(uuid.uuid4())
    conn.execute(
        """INSERT INTO mail_actions
           (id, account_id, action, target_ids, label_id, payload, created_by,
            status, attempts, next_attempt_at, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', 0, ?, ?, ?)""",
        (action_id, account_id, k.value, json.dumps(targets), label_id,
         json.dumps(payload) if payload else None, created_by, now, now, now),
    )
    return _row(conn, action_id)


# ---------------------------------------------------------------------------
# Worker
# ---------------------------------------------------------------------------

def _backoff(attempts: int) -> timedelta:
    return min(BACKOFF_BASE * (2 ** max(0, attempts - 1)), BACKOFF_CAP)


def push_pending(
    account: dict,
    session: Any,
    provider: MailProvider,
    *,
    retry_max: int | None = None,
    rate_limiter=None,
    now: datetime | None = None,
) -> dict:
    """Push this account's due pending actions in creation order.

    Returns ``{"pushed", "gone", "retried", "failed", "skipped"}``. A
    transient failure schedules the next attempt with backoff; a
    permanent one, or exhausting ``retry_max`` attempts, dead-letters the
    row as ``failed``. Later actions on the same account still run; order
    matters only within one message's history, and a dead-lettered row
    is resolved by the user.
    """
    account_id = account["id"]
    limit = DEFAULT_RETRY_MAX if retry_max is None else max(1, int(retry_max))
    now_dt = now or datetime.now(timezone.utc)
    now_iso = now_dt.isoformat()
    stats = {"pushed": 0, "gone": 0, "retried": 0, "failed": 0, "skipped": 0}

    with get_connection() as conn:
        rows = [_decode(dict(r)) for r in conn.execute(
            "SELECT * FROM mail_actions WHERE account_id = ? AND status = 'pending' "
            "AND (next_attempt_at IS NULL OR next_attempt_at <= ?) ORDER BY created_at",
            (account_id, now_iso),
        )]

    for row in rows:
        action = Action(
            kind=ActionKind(row["action"]),
            message_ids=row["target_ids"],
            label_id=row["label_id"],
            payload=row["payload"] or {},
        )
        try:
            result = provider.apply_action(session, action, rate_limiter=rate_limiter)
        except Exception as exc:  # adapter bug or network layer — treat as transient
            from .providers import ActionResult
            result = ActionResult(ActionStatus.FAILED, error=str(exc))

        attempts = row["attempts"] + 1
        ts = _now_iso()
        with get_connection() as conn:
            if result.status is ActionStatus.PUSHED:
                conn.execute(
                    "UPDATE mail_actions SET status='pushed', attempts=?, error=NULL, "
                    "pushed_at=?, updated_at=? WHERE id=?", (attempts, ts, ts, row["id"]))
                stats["pushed"] += 1
            elif result.status is ActionStatus.GONE:
                conn.execute(
                    "UPDATE mail_actions SET status='gone', attempts=?, error=?, "
                    "pushed_at=?, updated_at=? WHERE id=?", (attempts, result.error, ts, ts, row["id"]))
                stats["gone"] += 1
            elif result.permanent or attempts >= limit:
                conn.execute(
                    "UPDATE mail_actions SET status='failed', attempts=?, error=?, "
                    "updated_at=? WHERE id=?", (attempts, result.error, ts, row["id"]))
                stats["failed"] += 1
                log.warning("Mail action %s dead-lettered after %d attempt(s): %s",
                            row["id"], attempts, result.error)
            else:
                nxt = (now_dt + _backoff(attempts)).isoformat()
                conn.execute(
                    "UPDATE mail_actions SET attempts=?, error=?, next_attempt_at=?, "
                    "updated_at=? WHERE id=?", (attempts, result.error, nxt, ts, row["id"]))
                stats["retried"] += 1

    with get_connection() as conn:
        stats["skipped"] = conn.execute(
            "SELECT COUNT(*) FROM mail_actions WHERE account_id = ? AND status = 'pending' "
            "AND next_attempt_at > ?", (account_id, now_iso)).fetchone()[0]
    return stats


def pending_counts(account_ids: list[str] | None = None) -> dict:
    """``{"pending": n, "failed": n}`` across the given accounts (or all)."""
    with get_connection() as conn:
        if account_ids:
            placeholders = ",".join("?" * len(account_ids))
            rows = conn.execute(
                f"SELECT status, COUNT(*) n FROM mail_actions WHERE account_id IN ({placeholders}) "
                f"AND status IN ('pending','failed') GROUP BY status", tuple(account_ids)).fetchall()
        else:
            rows = conn.execute(
                "SELECT status, COUNT(*) n FROM mail_actions WHERE status IN ('pending','failed') "
                "GROUP BY status").fetchall()
    out = {"pending": 0, "failed": 0}
    for r in rows:
        out[r["status"]] = r["n"]
    return out


# ---------------------------------------------------------------------------
# User resolution of dead-lettered rows
# ---------------------------------------------------------------------------

def retry_action(conn, action_id: str) -> dict | None:
    """Put a failed row back in the queue for the next push."""
    row = _row(conn, action_id)
    if not row or row["status"] not in ("failed", "pending"):
        return row
    now = _now_iso()
    conn.execute(
        "UPDATE mail_actions SET status='pending', attempts=0, next_attempt_at=?, error=NULL, "
        "updated_at=? WHERE id=?", (now, now, action_id))
    return _row(conn, action_id)


def discard_action(conn, action_id: str) -> dict | None:
    """Drop a failed (or still-pending) row and revert its local effect."""
    row = _row(conn, action_id)
    if not row or row["status"] not in ("failed", "pending"):
        return row
    kind = ActionKind(row["action"])
    inv_kind, inv_payload = _inverse(kind, row["payload"])
    label = row["label_id"]
    if kind is ActionKind.MOVE:
        # Reverse: add the origin labels back, remove the destination.
        for origin in (inv_payload or {}).get("to") or ["INBOX"]:
            apply_local(conn, row["account_id"], ActionKind.ADD_LABEL, row["target_ids"], label_id=origin)
        if label:
            apply_local(conn, row["account_id"], ActionKind.REMOVE_LABEL, row["target_ids"], label_id=label)
    else:
        apply_local(conn, row["account_id"], inv_kind, row["target_ids"], label_id=label, payload=inv_payload)
    now = _now_iso()
    conn.execute("UPDATE mail_actions SET status='discarded', updated_at=? WHERE id=?", (now, action_id))
    return _row(conn, action_id)
