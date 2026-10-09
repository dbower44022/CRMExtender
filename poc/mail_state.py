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
