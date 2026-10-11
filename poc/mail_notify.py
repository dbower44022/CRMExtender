"""New-mail notifications (Mail Client MAIL-39).

After an account's sync run, the inbox messages that arrived during the run
are published as one ``mail.new`` event, each item flagged ``known_contact``
so the browser can apply the per-account ``mail_notifications`` setting
(``all`` | ``known_contacts`` | ``none``, default ``known_contacts``). The
setting is per user and per account (``mail_notifications:<account_id>``).
"""

from __future__ import annotations

from .settings import get_setting, set_setting

MODES = ("all", "known_contacts", "none")
DEFAULT_MODE = "known_contacts"
MAX_ITEMS = 10


def notification_mode(customer_id: str, user_id: str, account_id: str) -> str:
    val = get_setting(customer_id, f"mail_notifications:{account_id}", user_id=user_id)
    return val if val in MODES else DEFAULT_MODE


def set_notification_mode(customer_id: str, user_id: str, account_id: str, mode: str) -> str:
    if mode not in MODES:
        raise ValueError(f"mode must be one of {', '.join(MODES)}")
    set_setting(customer_id, f"mail_notifications:{account_id}", mode, scope="user", user_id=user_id)
    return mode


def new_inbox_messages(conn, account_id: str, since_iso: str, *, limit: int = MAX_ITEMS) -> dict:
    """Unread inbound inbox messages stored for ``account_id`` since ``since_iso``.

    Only mail sent within a day of ``since_iso`` counts: the historical
    backfill (MAIL-11) stores old messages with a fresh ``created_at``, and
    history is not news.

    Returns ``{"count": n, "items": [...]}`` with at most ``limit`` items,
    newest first; each item carries the thread id for a deep link, the
    sender, subject, snippet, and whether the sender is a known contact.
    """
    rows = conn.execute(
        """SELECT c.id, c.provider_thread_id, c.sender_address, c.sender_name, c.subject, c.snippet, c.timestamp
           FROM communications c
           WHERE c.account_id = ? AND c.created_at >= ? AND c.is_current = 1
             AND c.timestamp >= datetime(?, '-1 day')
             AND c.direction = 'inbound' AND c.is_read = 0
             AND EXISTS (SELECT 1 FROM communication_labels cl JOIN mailbox_labels ml ON ml.id = cl.label_id
                         WHERE cl.communication_id = c.id AND ml.kind = 'inbox')
           ORDER BY c.timestamp DESC""",
        (account_id, since_iso, since_iso),
    ).fetchall()
    count = len(rows)
    rows = rows[:limit]
    senders = sorted({(r["sender_address"] or "").lower() for r in rows if r["sender_address"]})
    known: dict[str, str] = {}
    if senders:
        sp = ",".join("?" * len(senders))
        for r in conn.execute(
            f"""SELECT LOWER(ci.value) AS address, ct.name FROM contact_identifiers ci
                JOIN contacts ct ON ct.id = ci.contact_id
                WHERE ci.type = 'email' AND LOWER(ci.value) IN ({sp})""", senders):
            known.setdefault(r["address"], r["name"])
    from .mail_threads import _display_name, _snippet
    items = []
    for r in rows:
        addr = (r["sender_address"] or "").lower()
        items.append({
            "communication_id": r["id"], "thread_id": r["provider_thread_id"],
            "sender_address": r["sender_address"],
            "sender_name": known.get(addr) or _display_name(r["sender_name"], r["sender_address"]),
            "known_contact": addr in known,
            "subject": r["subject"] or "(no subject)", "snippet": _snippet(r["snippet"])[:140],
            "timestamp": r["timestamp"],
        })
    return {"count": count, "items": items}
