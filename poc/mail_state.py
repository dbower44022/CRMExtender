"""Mailbox state on the Communication record: labels, flags, headers.

Mail Client PRD MAIL-07 and MAIL-08; TDD D-02 (state lives on the
``communications`` row) and D-03 (labels as ``mailbox_labels`` +
``communication_labels``). The provider is authoritative: every function
here overwrites local mailbox state with what the provider reported.

Three entry points:

- :func:`sync_mailbox_labels` — upsert the account's label list from the
  adapter's ``list_folders`` (names, kinds, counts).
- :func:`apply_mail_state` — write one message's headers, flags, and
  label membership (called by the sync store for new and re-seen rows).
- :func:`backfill_mail_state` — refresh rows that predate v23 from the
  provider in batches; resumable because it keys on
  ``mail_state_synced_at IS NULL``.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from .database import get_connection
from .models import ParsedEmail, _now_iso
from .providers import FolderKind, MailProvider

log = logging.getLogger(__name__)

#: Provider label ids whose kind is known before ``list_folders`` has run
#: (so placeholder rows created from a message's label ids are typed).
_PLACEHOLDER_KINDS: dict[str, str] = {
    "INBOX": FolderKind.INBOX.value,
    "SENT": FolderKind.SENT.value,
    "DRAFT": FolderKind.DRAFTS.value,
    "SPAM": FolderKind.SPAM.value,
    "TRASH": FolderKind.TRASH.value,
    "STARRED": FolderKind.STARRED.value,
    "IMPORTANT": FolderKind.IMPORTANT.value,
}

#: Gmail flag labels are mirrored as columns, not membership rows.
_FLAG_LABELS = {"UNREAD", "STARRED"}


# ---------------------------------------------------------------------------
# Labels
# ---------------------------------------------------------------------------

def _placeholder_kind(provider_label_id: str) -> str:
    if provider_label_id in _PLACEHOLDER_KINDS:
        return _PLACEHOLDER_KINDS[provider_label_id]
    if provider_label_id.startswith("CATEGORY_"):
        return FolderKind.CATEGORY.value
    return FolderKind.USER.value


def ensure_labels(conn, account_id: str, provider_label_ids: list[str]) -> dict[str, str]:
    """Return ``{provider_label_id: mailbox_labels.id}`` for the given ids.

    Ids not yet known get a placeholder row named after the id; the next
    :func:`sync_mailbox_labels` replaces the name and kind.
    """
    wanted = [lid for lid in dict.fromkeys(provider_label_ids) if lid and lid not in _FLAG_LABELS]
    if not wanted:
        return {}
    placeholders = ",".join("?" * len(wanted))
    rows = conn.execute(
        f"SELECT id, provider_label_id FROM mailbox_labels "
        f"WHERE account_id = ? AND provider_label_id IN ({placeholders})",
        (account_id, *wanted),
    ).fetchall()
    mapping = {r["provider_label_id"]: r["id"] for r in rows}
    now = _now_iso()
    for lid in wanted:
        if lid in mapping:
            continue
        row_id = str(uuid.uuid4())
        conn.execute(
            """INSERT OR IGNORE INTO mailbox_labels
               (id, account_id, provider_label_id, name, kind, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (row_id, account_id, lid, lid, _placeholder_kind(lid), now, now),
        )
        # OR IGNORE may have lost a race with a concurrent insert — re-read.
        got = conn.execute(
            "SELECT id FROM mailbox_labels WHERE account_id = ? AND provider_label_id = ?",
            (account_id, lid),
        ).fetchone()
        mapping[lid] = got["id"] if got else row_id
    return mapping


def sync_mailbox_labels(conn, account_id: str, folders: list) -> int:
    """Upsert the account's labels from ``MailProvider.list_folders``.

    Returns the number of rows written. Labels no longer reported by the
    provider are left in place (their membership rows disappear as
    messages are re-synced); pruning is MAIL-10's concern.
    """
    now = _now_iso()
    count = 0
    for f in folders:
        kind = f.kind.value if isinstance(f.kind, FolderKind) else str(f.kind)
        conn.execute(
            """INSERT INTO mailbox_labels
               (id, account_id, provider_label_id, name, kind, parent_id,
                unread_count, total_count, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(account_id, provider_label_id) DO UPDATE SET
                   name = excluded.name,
                   kind = excluded.kind,
                   parent_id = excluded.parent_id,
                   unread_count = excluded.unread_count,
                   total_count = excluded.total_count,
                   updated_at = excluded.updated_at""",
            (str(uuid.uuid4()), account_id, f.id, f.name, kind, f.parent_id,
             f.unread_count, f.total_count, now, now),
        )
        count += 1
    return count


def refresh_labels(account: dict, session: Any, provider: MailProvider, *, rate_limiter=None) -> int:
    """Fetch the label list from the provider and upsert it. Never raises."""
    try:
        folders = provider.list_folders(session, rate_limiter=rate_limiter)
    except Exception as exc:  # network boundary — a label refresh must not abort a sync
        log.warning("Label refresh failed for %s: %s", account.get("email_address"), exc)
        return 0
    with get_connection() as conn:
        return sync_mailbox_labels(conn, account["id"], folders)


def set_communication_labels(conn, communication_id: str, label_row_ids: list[str]) -> None:
    """Replace a communication's label membership."""
    conn.execute("DELETE FROM communication_labels WHERE communication_id = ?", (communication_id,))
    conn.executemany(
        "INSERT OR IGNORE INTO communication_labels (communication_id, label_id) VALUES (?, ?)",
        [(communication_id, lid) for lid in dict.fromkeys(label_row_ids)],
    )


# ---------------------------------------------------------------------------
# Per-message state
# ---------------------------------------------------------------------------

def apply_mail_state(conn, communication_id: str, account_id: str, em: ParsedEmail,
                     *, refresh_participants: bool = True) -> None:
    """Write ``em``'s headers, flags, labels, and participant names to the row.

    Bodies are never touched, so this is safe for metadata-only fetches.
    """
    state = em.mail_state()
    now = _now_iso()
    conn.execute(
        """UPDATE communications
           SET header_message_id = COALESCE(?, header_message_id),
               header_references = COALESCE(?, header_references),
               header_in_reply_to = COALESCE(?, header_in_reply_to),
               header_reply_to = COALESCE(?, header_reply_to),
               is_read = ?, is_starred = ?,
               mail_state_synced_at = ?, updated_at = ?
           WHERE id = ?""",
        (state["header_message_id"], state["header_references"],
         state["header_in_reply_to"], state["header_reply_to"],
         state["is_read"], state["is_starred"], now, now, communication_id),
    )

    mapping = ensure_labels(conn, account_id, em.label_ids)
    set_communication_labels(conn, communication_id, [mapping[l] for l in em.label_ids if l in mapping])

    if em.attachments:
        from .mail_attachments import store_attachment_rows
        store_attachment_rows(conn, communication_id, em)

    if refresh_participants:
        for rec in em.recipient_rows(communication_id):
            conn.execute(
                """INSERT INTO communication_participants (communication_id, address, name, role)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(communication_id, address, role) DO UPDATE SET
                       name = COALESCE(excluded.name, communication_participants.name)""",
                (rec["communication_id"], rec["address"], rec["name"], rec["role"]),
            )


# ---------------------------------------------------------------------------
# Incremental deltas (MAIL-10)
# ---------------------------------------------------------------------------

def _comm_id_for(conn, account_id: str, provider_message_id: str) -> str | None:
    row = conn.execute(
        "SELECT id FROM communications WHERE account_id = ? AND provider_message_id = ?",
        (account_id, provider_message_id),
    ).fetchone()
    return row["id"] if row else None


def apply_label_delta(
    conn,
    account_id: str,
    label_changes: list[tuple[str, list[str], list[str]]],
    flag_changes: list[tuple[str, dict[str, bool]]],
) -> dict:
    """Mirror a provider delta's label and flag changes onto stored rows.

    ``label_changes`` is ``[(provider_message_id, added_label_ids,
    removed_label_ids)]``; ``flag_changes`` is ``[(provider_message_id,
    {"is_read": bool, "is_starred": bool})]`` with only the flags that
    changed present. Messages not in the mirror are ignored (they are
    either outside the window or arrived in the same delta with their
    current labels). A ``TRASH`` label arriving sets the Communication's
    CRM status to archived and its removal restores it (TDD D-05).

    Returns ``{"labels_changed", "flags_changed", "trashed", "untrashed",
    "unknown"}``.
    """
    now = _now_iso()
    stats = {"labels_changed": 0, "flags_changed": 0, "trashed": 0, "untrashed": 0, "unknown": 0}

    for pid, added, removed in label_changes:
        comm_id = _comm_id_for(conn, account_id, pid)
        if not comm_id:
            stats["unknown"] += 1
            continue
        add_ids = [l for l in added if l not in _FLAG_LABELS]
        rem_ids = [l for l in removed if l not in _FLAG_LABELS and l not in add_ids]
        if add_ids:
            mapping = ensure_labels(conn, account_id, add_ids)
            conn.executemany(
                "INSERT OR IGNORE INTO communication_labels (communication_id, label_id) VALUES (?, ?)",
                [(comm_id, mapping[l]) for l in add_ids if l in mapping],
            )
        if rem_ids:
            placeholders = ",".join("?" * len(rem_ids))
            conn.execute(
                f"""DELETE FROM communication_labels
                    WHERE communication_id = ? AND label_id IN (
                        SELECT id FROM mailbox_labels
                        WHERE account_id = ? AND provider_label_id IN ({placeholders}))""",
                (comm_id, account_id, *rem_ids),
            )
        if "TRASH" in add_ids:
            conn.execute("UPDATE communications SET is_archived = 1 WHERE id = ?", (comm_id,))
            stats["trashed"] += 1
        elif "TRASH" in rem_ids:
            conn.execute("UPDATE communications SET is_archived = 0 WHERE id = ?", (comm_id,))
            stats["untrashed"] += 1
        conn.execute(
            "UPDATE communications SET mail_state_synced_at = ?, updated_at = ? WHERE id = ?",
            (now, now, comm_id),
        )
        stats["labels_changed"] += 1

    for pid, flags in flag_changes:
        comm_id = _comm_id_for(conn, account_id, pid)
        if not comm_id:
            stats["unknown"] += 1
            continue
        sets, params = [], []
        if "is_read" in flags:
            sets.append("is_read = ?"); params.append(1 if flags["is_read"] else 0)
        if "is_starred" in flags:
            sets.append("is_starred = ?"); params.append(1 if flags["is_starred"] else 0)
        if not sets:
            continue
        sets += ["mail_state_synced_at = ?", "updated_at = ?"]
        params += [now, now, comm_id]
        conn.execute(f"UPDATE communications SET {', '.join(sets)} WHERE id = ?", params)
        stats["flags_changed"] += 1

    return stats


def archive_deleted(conn, account_id: str, provider_message_ids: list[str]) -> int:
    """Provider says these messages are gone for good: archive them locally.

    The Communication row and its conversation links survive (entity-base
    PRD §4.1: provider deletion archives the record); label membership is
    cleared because the message is in no folder any more. Returns the
    number of rows archived.
    """
    now = _now_iso()
    archived = 0
    for pid in provider_message_ids:
        comm_id = _comm_id_for(conn, account_id, pid)
        if not comm_id:
            continue
        conn.execute("DELETE FROM communication_labels WHERE communication_id = ?", (comm_id,))
        conn.execute(
            "UPDATE communications SET is_archived = 1, mail_state_synced_at = ?, updated_at = ? WHERE id = ?",
            (now, now, comm_id),
        )
        archived += 1
    return archived


# ---------------------------------------------------------------------------
# Backfill of pre-v23 rows
# ---------------------------------------------------------------------------

def pending_backfill_count(account_id: str | None = None) -> int:
    with get_connection() as conn:
        if account_id:
            row = conn.execute(
                "SELECT COUNT(*) AS n FROM communications WHERE channel = 'email' "
                "AND provider_message_id IS NOT NULL AND mail_state_synced_at IS NULL "
                "AND account_id = ?", (account_id,)).fetchone()
        else:
            row = conn.execute(
                "SELECT COUNT(*) AS n FROM communications WHERE channel = 'email' "
                "AND provider_message_id IS NOT NULL AND mail_state_synced_at IS NULL").fetchone()
        return int(row["n"])


def backfill_mail_state(
    account: dict,
    session: Any,
    provider: MailProvider,
    *,
    batch_size: int = 100,
    limit: int | None = None,
    rate_limiter=None,
    progress=None,
) -> dict:
    """Refresh headers, flags, labels, and participant names for rows that
    predate v23 (``mail_state_synced_at IS NULL``) in one account.

    Uses metadata-only fetches so bodies are untouched. Rows the provider
    no longer has are stamped as synced with no state change so the job
    does not retry them forever. Resumable: interrupting it loses at most
    one batch. ``progress(done, total)`` is called after each batch.

    Returns ``{"updated", "missing", "remaining"}``.
    """
    account_id = account["id"]
    total = pending_backfill_count(account_id)
    if limit is not None:
        total = min(total, limit)
    updated = missing = done = 0

    while done < total:
        take = min(batch_size, total - done)
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT id, provider_message_id FROM communications "
                "WHERE channel = 'email' AND provider_message_id IS NOT NULL "
                "AND mail_state_synced_at IS NULL AND account_id = ? "
                "ORDER BY timestamp DESC LIMIT ?",
                (account_id, take),
            ).fetchall()
        if not rows:
            break
        by_pid = {r["provider_message_id"]: r["id"] for r in rows}

        fetched = provider.fetch_messages(
            session, list(by_pid), rate_limiter=rate_limiter, metadata_only=True,
        )
        seen: set[str] = set()
        now = _now_iso()
        with get_connection() as conn:
            for em in fetched:
                comm_id = by_pid.get(em.message_id)
                if not comm_id:
                    continue
                apply_mail_state(conn, comm_id, account_id, em)
                seen.add(em.message_id)
                updated += 1
            for pid, comm_id in by_pid.items():
                if pid in seen:
                    continue
                conn.execute(
                    "UPDATE communications SET mail_state_synced_at = ?, updated_at = ? WHERE id = ?",
                    (now, now, comm_id),
                )
                missing += 1
        done += len(rows)
        if progress:
            progress(done, total)

    return {
        "updated": updated,
        "missing": missing,
        "remaining": pending_backfill_count(account_id),
    }
