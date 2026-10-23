"""Cross-account thread links (Mail Client MAIL-44; TDD D-47).

The same message often lands in two of the owner's mailboxes (a thread
sent to both addresses, a forward, a shared alias). Its RFC 5322
Message-ID is identical in both, so the two provider threads are the
same conversation. ``mail_thread_links`` records which (account, thread)
pairs belong to one *group*; the unified views present a group as a
single thread with one chip per account, while per-account views are
unchanged. Groups are maintained at store time and rebuilt by migration
v33 for existing rows.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def thread_key(account_id: str, thread_id: str) -> str:
    return f"{account_id}:{thread_id}"


def _groups_for(conn, keys: list[tuple[str, str]]) -> dict[tuple[str, str], str]:
    out: dict[tuple[str, str], str] = {}
    for acct, tid in keys:
        row = conn.execute(
            "SELECT group_id FROM mail_thread_links WHERE account_id = ? AND thread_id = ?", (acct, tid)).fetchone()
        if row:
            out[(acct, tid)] = row["group_id"]
    return out


def _merge(conn, keys: list[tuple[str, str]]) -> str | None:
    """Put every key in one group (the oldest existing group wins). Returns the group id."""
    keys = list(dict.fromkeys(keys))
    if len(keys) < 2:
        return None
    existing = _groups_for(conn, keys)
    group_ids = sorted(set(existing.values()))
    group_id = group_ids[0] if group_ids else str(uuid.uuid4())
    for other in group_ids[1:]:
        conn.execute("UPDATE mail_thread_links SET group_id = ? WHERE group_id = ?", (group_id, other))
    now = _now_iso()
    for acct, tid in keys:
        if (acct, tid) not in existing:
            conn.execute(
                "INSERT OR IGNORE INTO mail_thread_links (account_id, thread_id, group_id, created_at) VALUES (?, ?, ?, ?)",
                (acct, tid, group_id, now))
    return group_id


def link_thread(conn, account_id: str, thread_id: str, header_message_ids: list[str]) -> str | None:
    """Link (account, thread) with every other account's thread that holds one
    of ``header_message_ids``. Returns the group id, or None when the thread
    is alone."""
    ids = [h for h in dict.fromkeys(header_message_ids) if h]
    if not ids:
        return None
    placeholders = ",".join("?" * len(ids))
    rows = conn.execute(
        f"""SELECT DISTINCT c.account_id, COALESCE(c.provider_thread_id, c.id) AS tid
            FROM communications c
            WHERE c.header_message_id IN ({placeholders}) AND c.is_current = 1 AND c.account_id <> ?""",
        (*ids, account_id)).fetchall()
    others = [(r["account_id"], r["tid"]) for r in rows]
    if not others:
        return _groups_for(conn, [(account_id, thread_id)]).get((account_id, thread_id))
    return _merge(conn, [(account_id, thread_id), *others])


def group_members(conn, account_id: str, thread_id: str, *, account_ids: list[str] | None = None) -> list[dict]:
    """``[{"account_id", "thread_id"}, ...]`` for the thread's group, the thread
    itself first; limited to ``account_ids`` when given."""
    row = conn.execute(
        "SELECT group_id FROM mail_thread_links WHERE account_id = ? AND thread_id = ?", (account_id, thread_id)).fetchone()
    members = [{"account_id": account_id, "thread_id": thread_id}]
    if row:
        for r in conn.execute(
                "SELECT account_id, thread_id FROM mail_thread_links WHERE group_id = ? ORDER BY created_at",
                (row["group_id"],)):
            if (r["account_id"], r["thread_id"]) != (account_id, thread_id):
                members.append({"account_id": r["account_id"], "thread_id": r["thread_id"]})
    if account_ids is not None:
        allowed = set(account_ids)
        members = [m for m in members if m["account_id"] in allowed]
    return members


def rebuild_links(conn) -> dict:
    """Recompute every group from scratch (migration v33 and repair). Returns counts."""
    conn.execute("DELETE FROM mail_thread_links")
    rows = conn.execute(
        """SELECT header_message_id, account_id, COALESCE(provider_thread_id, id) AS tid
           FROM communications
           WHERE is_current = 1 AND header_message_id IS NOT NULL AND header_message_id IN (
               SELECT header_message_id FROM communications
               WHERE is_current = 1 AND header_message_id IS NOT NULL
               GROUP BY header_message_id HAVING COUNT(DISTINCT account_id) > 1)
           ORDER BY header_message_id""").fetchall()
    by_id: dict[str, list[tuple[str, str]]] = {}
    for r in rows:
        by_id.setdefault(r["header_message_id"], []).append((r["account_id"], r["tid"]))
    merged = 0
    for keys in by_id.values():
        if _merge(conn, keys):
            merged += 1
    groups = conn.execute("SELECT COUNT(DISTINCT group_id) FROM mail_thread_links").fetchone()[0]
    threads = conn.execute("SELECT COUNT(*) FROM mail_thread_links").fetchone()[0]
    return {"message_ids": len(by_id), "groups": groups, "threads": threads}
