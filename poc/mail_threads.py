"""Folders, thread lists, and thread detail for the mail surface (MAIL-16).

Reads only. Everything is computed from the local mirror:

- :func:`folders` — per visible account, the label rows with unread and
  total counts computed from membership (not the provider's counts,
  which can be stale), plus the unified set across accounts.
- :func:`thread_list` — threads in a folder (or matching a search),
  newest activity first, grouped by (account, provider thread id). A
  thread is in a folder when any of its messages is, as at the provider.
- :func:`thread_detail` — every message of one thread, oldest first,
  with bodies, participants (with contact links), labels, attachments,
  and the CRM conversation the thread belongs to.

Folder and search membership share one predicate builder
(:func:`poc.mail_search.predicates`) so the two never disagree.
"""

from __future__ import annotations

import html
import re

from .mail_search import SearchQuery, parse_query, predicates

_ANGLE = re.compile(r"\s*<[^>]*>\s*$")


def _display_name(name: str | None, address: str | None) -> str | None:
    """``sender_name`` historically stored the full ``Name <addr>`` display
    string; return just the name, or None when it is only the address."""
    if not name:
        return None
    n = _ANGLE.sub("", name).strip().strip('"')
    if not n or (address and n.lower() == address.lower()):
        return None
    return n


def _snippet(text: str | None) -> str:
    """Gmail snippets arrive HTML-escaped (``&#39;``); show them plain."""
    return html.unescape(text or "")

#: Folder keys the API accepts, mapped onto SearchQuery.in_ values.
SYSTEM_FOLDERS = {
    "inbox": "inbox", "starred": "starred", "sent": "sent", "drafts": "drafts",
    "archive": "archive", "all": "anywhere", "trash": "trash", "spam": "spam",
    "important": "important", "unread": "unread", "snoozed": "snoozed",
    "awaiting": "awaiting",
}


# ---------------------------------------------------------------------------
# Folders
# ---------------------------------------------------------------------------

def _account_rows(conn, account_ids: list[str]) -> list[dict]:
    if not account_ids:
        return []
    placeholders = ",".join("?" * len(account_ids))
    return [dict(r) for r in conn.execute(
        f"SELECT id, email_address, display_name, provider, is_active, initial_sync_done, last_synced_at, color "
        f"FROM provider_accounts WHERE id IN ({placeholders}) ORDER BY created_at", account_ids)]


def _duplicate_overcount(conn, account_ids: list[str]) -> dict[str, tuple[int, int]]:
    """``{folder_key: (extra_total, extra_unread)}``: how many unified-count
    entries are second copies of a message held in more than one account
    (same Message-ID; MAIL-44). Inbox, sent, drafts by label; starred by flag."""
    placeholders = ",".join("?" * len(account_ids))
    out: dict[str, tuple[int, int]] = {}
    for r in conn.execute(
        f"""SELECT ml.kind,
                   COUNT(*) - COUNT(DISTINCT COALESCE(c.header_message_id, c.id)) AS extra,
                   SUM(CASE WHEN c.is_read = 0 THEN 1 ELSE 0 END)
                     - COUNT(DISTINCT CASE WHEN c.is_read = 0 THEN COALESCE(c.header_message_id, c.id) END) AS extra_unread
            FROM communications c
            JOIN communication_labels cl ON cl.communication_id = c.id
            JOIN mailbox_labels ml ON ml.id = cl.label_id AND ml.kind IN ('inbox', 'sent', 'drafts')
            WHERE c.is_current = 1 AND c.account_id IN ({placeholders})
            GROUP BY ml.kind""", account_ids):
        out[r["kind"]] = (r["extra"] or 0, r["extra_unread"] or 0)
    r = conn.execute(
        f"""SELECT COUNT(*) - COUNT(DISTINCT COALESCE(c.header_message_id, c.id)) AS extra,
                   SUM(CASE WHEN c.is_read = 0 THEN 1 ELSE 0 END)
                     - COUNT(DISTINCT CASE WHEN c.is_read = 0 THEN COALESCE(c.header_message_id, c.id) END) AS extra_unread
            FROM communications c
            WHERE c.is_current = 1 AND c.is_starred = 1 AND c.is_archived = 0 AND c.account_id IN ({placeholders})""",
        account_ids).fetchone()
    if r and r["extra"]:
        out["starred"] = (r["extra"], r["extra_unread"] or 0)
    return out


def folders(conn, *, account_ids: list[str], awaiting_days: int | None = None,
            awaiting_window: int | None = None) -> dict:
    """``{"accounts": [...], "unified": {...}}`` with locally computed counts."""
    accounts = _account_rows(conn, account_ids)
    if not accounts:
        return {"accounts": [], "unified": {}}
    placeholders = ",".join("?" * len(account_ids))

    # Per-label counts over live (non-archived) messages
    counts: dict[str, dict] = {}
    for r in conn.execute(
        f"""SELECT ml.id AS label_id, COUNT(*) AS total, SUM(CASE WHEN c.is_read = 0 THEN 1 ELSE 0 END) AS unread
            FROM mailbox_labels ml
            JOIN communication_labels cl ON cl.label_id = ml.id
            JOIN communications c ON c.id = cl.communication_id AND c.is_current = 1
            WHERE ml.account_id IN ({placeholders})
            GROUP BY ml.id""", account_ids):
        counts[r["label_id"]] = {"total": r["total"], "unread": r["unread"] or 0}

    # Starred and "archive" (no inbox/trash/spam label) per account
    flag_counts: dict[str, dict] = {}
    for r in conn.execute(
        f"""SELECT c.account_id,
                   SUM(CASE WHEN c.is_starred = 1 AND c.is_archived = 0 THEN 1 ELSE 0 END) AS starred,
                   SUM(CASE WHEN c.is_starred = 1 AND c.is_archived = 0 AND c.is_read = 0 THEN 1 ELSE 0 END) AS starred_unread,
                   SUM(CASE WHEN c.is_archived = 0 AND NOT EXISTS (
                        SELECT 1 FROM communication_labels cl JOIN mailbox_labels ml ON ml.id = cl.label_id
                        WHERE cl.communication_id = c.id AND ml.kind IN ('inbox', 'trash', 'spam')) THEN 1 ELSE 0 END) AS archive,
                   SUM(CASE WHEN c.is_archived = 0 AND c.is_read = 0 AND NOT EXISTS (
                        SELECT 1 FROM communication_labels cl JOIN mailbox_labels ml ON ml.id = cl.label_id
                        WHERE cl.communication_id = c.id AND ml.kind IN ('inbox', 'trash', 'spam')) THEN 1 ELSE 0 END) AS archive_unread
            FROM communications c
            WHERE c.channel = 'email' AND c.is_current = 1 AND c.account_id IN ({placeholders})
            GROUP BY c.account_id""", account_ids):
        flag_counts[r["account_id"]] = dict(r)

    label_rows = [dict(r) for r in conn.execute(
        f"SELECT * FROM mailbox_labels WHERE account_id IN ({placeholders}) ORDER BY kind, name", account_ids)]
    from .mail_awaiting import DEFAULT_DAYS, counts as awaiting_counts
    awaiting = awaiting_counts(conn, account_ids, awaiting_days or DEFAULT_DAYS, awaiting_window)
    snooze_counts = {r["account_id"]: r["n"] for r in conn.execute(
        f"SELECT account_id, COUNT(*) AS n FROM mail_snoozes WHERE status = 'snoozed' "
        f"AND account_id IN ({placeholders}) GROUP BY account_id", account_ids)}

    unified = {k: {"total": 0, "unread": 0} for k in ("inbox", "starred", "snoozed", "awaiting", "drafts", "sent", "archive")}
    overcount = _duplicate_overcount(conn, account_ids) if len(account_ids) > 1 else {}
    out_accounts = []
    for acct in accounts:
        fc = flag_counts.get(acct["id"], {})
        system = {
            "starred": {"total": fc.get("starred", 0) or 0, "unread": fc.get("starred_unread", 0) or 0},
            "archive": {"total": fc.get("archive", 0) or 0, "unread": fc.get("archive_unread", 0) or 0},
            "snoozed": {"total": snooze_counts.get(acct["id"], 0), "unread": 0},
            "awaiting": {"total": awaiting.get(acct["id"], 0), "unread": 0},
        }
        labels = []
        for lr in label_rows:
            if lr["account_id"] != acct["id"]:
                continue
            c = counts.get(lr["id"], {"total": 0, "unread": 0})
            entry = {
                "id": lr["id"], "provider_label_id": lr["provider_label_id"], "name": lr["name"],
                "kind": lr["kind"], "parent_id": lr["parent_id"],
                "total": c["total"], "unread": c["unread"],
            }
            labels.append(entry)
            if lr["kind"] in ("inbox", "sent", "drafts", "trash", "spam", "important"):
                system[lr["kind"]] = {"total": c["total"], "unread": c["unread"]}
        for key in ("inbox", "starred", "snoozed", "awaiting", "drafts", "sent", "archive"):
            v = system.get(key, {"total": 0, "unread": 0})
            unified[key]["total"] += v["total"]
            unified[key]["unread"] += v["unread"]
        out_accounts.append({
            "id": acct["id"], "email": acct["email_address"], "display_name": acct["display_name"],
            "color": acct.get("color"),
            "provider": acct["provider"], "is_active": bool(acct["is_active"]),
            "initial_sync_done": bool(acct["initial_sync_done"]), "last_synced_at": acct["last_synced_at"],
            "system": system, "labels": labels,
        })
    # Unified counts: a message held in two accounts counts once (MAIL-44).
    for key, (extra_total, extra_unread) in overcount.items():
        if key in unified:
            unified[key]["total"] = max(0, unified[key]["total"] - extra_total)
            unified[key]["unread"] = max(0, unified[key]["unread"] - extra_unread)
    return {"accounts": out_accounts, "unified": unified}


# ---------------------------------------------------------------------------
# Thread list
# ---------------------------------------------------------------------------

def _query_for(folder: str | None, label_row_id: str | None, q: str | None) -> SearchQuery:
    sq = parse_query(q or "")
    if label_row_id:
        sq.label_row_ids.append(label_row_id)
    elif folder:
        key = folder.lower()
        if key not in SYSTEM_FOLDERS:
            raise ValueError(f"unknown folder {folder!r}")
        if sq.in_ is None:
            sq.in_ = SYSTEM_FOLDERS[key]
    return sq


def thread_list(conn, *, account_ids: list[str], folder: str | None = "inbox",
                label_row_id: str | None = None, q: str | None = None,
                limit: int = 50, offset: int = 0, awaiting_days: int | None = None,
                awaiting_window: int | None = None) -> dict:
    """Threads newest-activity first. ``folder`` is a SYSTEM_FOLDERS key,
    or ``label_row_id`` selects a user label; ``q`` narrows further.
    ``awaiting_days`` / ``awaiting_window`` bound the Awaiting reply folder (MAIL-47)."""
    sq = _query_for(folder, label_row_id, q)
    snoozed_only = sq.in_ == "snoozed"
    awaiting_only = sq.in_ == "awaiting"
    if snoozed_only or awaiting_only:
        # These folders come from local state, not a provider label (MAIL-17, MAIL-47).
        sq.in_ = None
    joins, where, params = predicates(sq, account_ids=account_ids)
    if snoozed_only:
        where.append("EXISTS (SELECT 1 FROM mail_snoozes ms WHERE ms.account_id = c.account_id "
                     "AND ms.thread_id = COALESCE(c.provider_thread_id, c.id) AND ms.status = 'snoozed')")
    if awaiting_only:
        from .mail_awaiting import AWAITING_PREDICATE, DEFAULT_DAYS, bounds
        where.append(f"({AWAITING_PREDICATE})")
        params.extend(bounds(awaiting_days or DEFAULT_DAYS, awaiting_window))
    # In a multi-account scope, threads linked across accounts (same
    # Message-ID; MAIL-44) collapse into one row keyed by their group.
    merged_scope = len(account_ids) > 1
    gkey = ("COALESCE(tl.group_id, c.account_id || ':' || COALESCE(c.provider_thread_id, c.id))"
            if merged_scope else "c.account_id || ':' || COALESCE(c.provider_thread_id, c.id)")
    link_join = ("LEFT JOIN mail_thread_links tl ON tl.account_id = c.account_id "
                 "AND tl.thread_id = COALESCE(c.provider_thread_id, c.id)") if merged_scope else ""
    matched = (f"SELECT c.id, c.account_id, COALESCE(c.provider_thread_id, c.id) AS thread_id, {gkey} AS gkey, "
               f"c.timestamp, c.is_read, c.is_starred FROM communications c {' '.join(joins)} {link_join} "
               f"WHERE {' AND '.join(where)}")
    total = conn.execute(
        f"SELECT COUNT(*) AS n FROM (SELECT DISTINCT gkey FROM ({matched}))", params
    ).fetchone()["n"]
    groups = [dict(r) for r in conn.execute(
        f"""SELECT gkey, MAX(timestamp) AS last_at, COUNT(*) AS matched_count,
                   SUM(CASE WHEN is_read = 0 THEN 1 ELSE 0 END) AS unread_count,
                   MAX(is_starred) AS starred
            FROM ({matched}) GROUP BY gkey
            ORDER BY last_at DESC LIMIT ? OFFSET ?""",
        params + [max(1, min(int(limit), 200)), max(0, int(offset))])]
    from .mail_links import group_members
    for g in groups:
        acct, _, tid = g["gkey"].partition(":")
        if tid and acct in account_ids:
            # an unlinked thread: the key is account:thread
            g["account_id"], g["thread_id"] = acct, tid
            g["members"] = [{"account_id": acct, "thread_id": tid}]
        else:
            rows = [dict(r) for r in conn.execute(
                "SELECT account_id, thread_id FROM mail_thread_links WHERE group_id = ? ORDER BY created_at",
                (g["gkey"],)) if r["account_id"] in account_ids]
            g["members"] = rows or [{"account_id": acct, "thread_id": tid}]
            g["account_id"], g["thread_id"] = g["members"][0]["account_id"], g["members"][0]["thread_id"]
    items = [_thread_summary(conn, g) for g in groups]
    from .mail_snooze import active_snoozes
    snoozes = active_snoozes(conn, account_ids)
    for it in items:
        it["snoozed_until"] = snoozes.get((it["account_id"], it["thread_id"]))
    if awaiting_only:
        from .mail_awaiting import days_waiting
        for it, g in zip(items, groups):
            it["awaiting_since"] = g["last_at"]
            it["awaiting_days"] = days_waiting(g["last_at"])
    return {"total": total, "items": items, "limit": limit, "offset": offset}


def _member_messages(conn, members: list[dict], cols: str) -> list[dict]:
    """Current messages of every member thread, newest first, one copy per
    Message-ID (the first member's copy wins, so the requested account's
    flags and ids are the ones shown)."""
    out: list[dict] = []
    seen: set[str] = set()
    for i, m in enumerate(members):
        for r in conn.execute(
                f"""SELECT {cols}, c.header_message_id, c.account_id FROM communications c
                    WHERE c.account_id = ? AND COALESCE(c.provider_thread_id, c.id) = ? AND c.is_current = 1
                    ORDER BY c.timestamp DESC""", (m["account_id"], m["thread_id"])):
            d = dict(r)
            key = d.get("header_message_id") or f"{d['account_id']}:{d['id']}"
            if key in seen:
                continue
            seen.add(key)
            d["_member"] = i
            out.append(d)
    out.sort(key=lambda d: d["timestamp"] or "", reverse=True)
    return out


def _thread_summary(conn, g: dict) -> dict:
    account_id, thread_id = g["account_id"], g["thread_id"]
    members = g.get("members") or [{"account_id": account_id, "thread_id": thread_id}]
    msgs = _member_messages(
        conn, members,
        "c.id, c.timestamp, c.subject, c.snippet, c.sender_address, c.sender_name, "
        "c.direction, c.is_read, c.is_starred, c.is_archived")
    latest = msgs[0] if msgs else {}
    if latest and len(members) > 1:
        # the row opens the account that holds the newest message
        account_id = latest["account_id"]
        thread_id = next(m["thread_id"] for m in members if m["account_id"] == account_id)
    ids = [m["id"] for m in msgs]
    placeholders = ",".join("?" * len(ids)) if ids else "''"
    labels = sorted({r[0] for r in conn.execute(
        f"SELECT ml.name FROM communication_labels cl JOIN mailbox_labels ml ON ml.id = cl.label_id "
        f"WHERE cl.communication_id IN ({placeholders})", ids)}) if ids else []
    has_attachments = bool(conn.execute(
        f"SELECT 1 FROM attachments WHERE communication_id IN ({placeholders}) LIMIT 1", ids
    ).fetchone()) if ids else False
    acct_row = conn.execute(
        "SELECT email_address, color FROM provider_accounts WHERE id = ?", (account_id,)).fetchone()
    account_email, account_color = acct_row[0], acct_row[1]
    accounts = [dict(r) for r in conn.execute(
        f"SELECT id, email_address AS email, color FROM provider_accounts WHERE id IN "
        f"({','.join('?' * len(members))}) ORDER BY created_at", [m["account_id"] for m in members])]
    # Distinct senders, newest first, as the row's participant line
    seen: list[dict] = []
    for m in msgs:
        key = (m["sender_address"] or "").lower()
        if key and all(p["address"] != key for p in seen):
            seen.append({"address": key, "name": _display_name(m["sender_name"], key),
                         "is_me": key == account_email.lower()})
    return {
        "account_id": account_id, "account_email": account_email, "account_color": account_color, "thread_id": thread_id,
        "subject": latest.get("subject") or "(no subject)", "snippet": _snippet(latest.get("snippet")),
        "last_at": g["last_at"], "message_count": len(msgs), "unread_count": sum(1 for m in msgs if not m["is_read"]),
        "starred": any(m["is_starred"] for m in msgs), "has_attachments": has_attachments,
        "labels": labels, "participants": seen[:4], "latest_message_id": latest.get("id"),
        # Cross-account group (MAIL-44): every account holding this thread, and
        # the (account, thread) pairs an action must cover.
        "accounts": accounts,
        "members": [{"account_id": m["account_id"], "thread_id": m["thread_id"]} for m in members],
    }


# ---------------------------------------------------------------------------
# Thread detail
# ---------------------------------------------------------------------------

def thread_detail(conn, *, account_id: str, thread_id: str, account_ids: list[str] | None = None) -> dict | None:
    """One thread with its messages. When the thread is linked to the same
    conversation in other accounts (MAIL-44), those accounts' messages are
    merged in, one copy per Message-ID, each tagged with its account;
    ``account_ids`` limits the merge to the accounts the caller may see."""
    from .mail_links import group_members
    members = group_members(conn, account_id, thread_id, account_ids=account_ids)
    rows: list[dict] = []
    seen: set[str] = set()
    for m in members:
        for r in conn.execute(
                """SELECT c.*, pa.email_address AS account_email FROM communications c
                   JOIN provider_accounts pa ON pa.id = c.account_id
                   WHERE c.account_id = ? AND COALESCE(c.provider_thread_id, c.id) = ? AND c.is_current = 1
                   ORDER BY c.timestamp ASC""", (m["account_id"], m["thread_id"])):
            d = dict(r)
            key = d.get("header_message_id") or f"{d['account_id']}:{d['id']}"
            if key in seen:
                continue
            seen.add(key)
            rows.append(d)
    rows.sort(key=lambda d: d["timestamp"] or "")
    if not rows:
        return None
    ids = [r["id"] for r in rows]
    placeholders = ",".join("?" * len(ids))

    labels: dict[str, list[dict]] = {}
    for r in conn.execute(
        f"SELECT cl.communication_id, ml.id, ml.name, ml.kind FROM communication_labels cl "
        f"JOIN mailbox_labels ml ON ml.id = cl.label_id WHERE cl.communication_id IN ({placeholders})", ids):
        labels.setdefault(r["communication_id"], []).append({"id": r["id"], "name": r["name"], "kind": r["kind"]})

    parts: dict[str, list[dict]] = {}
    for r in conn.execute(
        f"""SELECT cp.communication_id, cp.address, cp.name, cp.role, cp.contact_id,
                   COALESCE(ct.name, '') AS contact_name
            FROM communication_participants cp LEFT JOIN contacts ct ON ct.id = cp.contact_id
            WHERE cp.communication_id IN ({placeholders}) ORDER BY cp.role, cp.address""", ids):
        parts.setdefault(r["communication_id"], []).append({
            "address": r["address"], "name": r["name"], "role": r["role"],
            "contact_id": r["contact_id"], "contact_name": r["contact_name"] or None,
        })

    atts: dict[str, list[dict]] = {}
    for r in conn.execute(
        f"SELECT id, communication_id, filename, mime_type, size_bytes, content_id, is_inline FROM attachments "
        f"WHERE communication_id IN ({placeholders}) ORDER BY filename", ids):
        atts.setdefault(r["communication_id"], []).append(
            {"id": r["id"], "filename": r["filename"], "mime_type": r["mime_type"], "size_bytes": r["size_bytes"],
             "content_id": r["content_id"], "is_inline": bool(r["is_inline"])})

    # Sender → contact via a current email identifier
    sender_contacts: dict[str, dict] = {}
    senders = sorted({(r["sender_address"] or "").lower() for r in rows if r["sender_address"]})
    if senders:
        sp = ",".join("?" * len(senders))
        for r in conn.execute(
            f"""SELECT ci.value AS address, ct.id, ct.name FROM contact_identifiers ci
                JOIN contacts ct ON ct.id = ci.contact_id
                WHERE ci.type = 'email' AND LOWER(ci.value) IN ({sp})""", senders):
            sender_contacts.setdefault(r["address"].lower(), {"id": r["id"], "name": r["name"]})

    conv = conn.execute(
        f"""SELECT cv.id, cv.title, cv.ai_summary, cv.ai_status FROM conversation_communications cc
            JOIN conversations cv ON cv.id = cc.conversation_id
            WHERE cc.communication_id IN ({placeholders}) ORDER BY cc.created_at LIMIT 1""", ids).fetchone()

    messages = []
    for r in rows:
        sender = (r["sender_address"] or "").lower()
        messages.append({
            "id": r["id"], "timestamp": r["timestamp"], "direction": r["direction"],
            "subject": r["subject"], "snippet": _snippet(r["snippet"]),
            "sender": {"address": r["sender_address"], "name": _display_name(r["sender_name"], r["sender_address"]),
                       "contact_id": (sender_contacts.get(sender) or {}).get("id"),
                       "contact_name": (sender_contacts.get(sender) or {}).get("name"),
                       "is_me": sender == (r["account_email"] or "").lower()},
            "participants": parts.get(r["id"], []),
            "body_html": r.get("cleaned_html") or r.get("original_html") or "",
            "body_text": r.get("original_text") or "",
            "is_read": bool(r["is_read"]), "is_starred": bool(r["is_starred"]),
            "is_archived": bool(r["is_archived"]),
            "labels": labels.get(r["id"], []),
            "attachments": atts.get(r["id"], []),
            "header_message_id": r.get("header_message_id"),
            "provider_message_id": r.get("provider_message_id"),
            "account_id": r["account_id"], "account_email": r["account_email"],
        })

    thread_labels = sorted({l["name"] for ls in labels.values() for l in ls})
    acct_email = conn.execute("SELECT email_address FROM provider_accounts WHERE id = ?", (account_id,)).fetchone()
    accounts = [dict(r) for r in conn.execute(
        f"SELECT id, email_address AS email, color FROM provider_accounts WHERE id IN "
        f"({','.join('?' * len(members))}) ORDER BY created_at", [m["account_id"] for m in members])]
    return {
        "account_id": account_id, "account_email": acct_email[0] if acct_email else rows[0]["account_email"],
        "thread_id": thread_id, "accounts": accounts, "members": members,
        # the thread's subject is the first message's (before any "Re:")
        "subject": next((m["subject"] for m in messages if m["subject"]), "(no subject)"),
        "labels": thread_labels, "message_count": len(messages),
        "unread_count": sum(1 for m in messages if not m["is_read"]),
        "conversation": dict(conv) if conv else None,
        "messages": messages,
    }
