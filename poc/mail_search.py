"""Full-text mail search (Mail Client MAIL-12; TDD D-06).

Three parts:

- :data:`FTS_SCHEMA_SQL` — the ``communications_fts`` FTS5 table and the
  triggers that keep it current. Used by ``init_db`` and by the v25
  migration (which also backfills existing rows).
- :func:`parse_query` — turns a mailbox search string with operators
  (``from:``, ``to:``, ``cc:``, ``subject:``, ``has:attachment``,
  ``in:``, ``label:``, ``account:``, ``is:unread|read|starred|unstarred``,
  ``before:``, ``after:``, ``newer_than:``/``older_than:`` and quoted
  phrases) into a :class:`SearchQuery`.
- :func:`build_sql` — the one place that maps a :class:`SearchQuery`
  onto SQL, so a move to another full-text engine changes only this
  function (TDD D-06 constraint).

Trash and spam are excluded unless the query names them (``in:trash``,
``in:spam``, ``in:anywhere``).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

__all__ = ["FTS_SCHEMA_SQL", "SearchQuery", "parse_query", "build_sql", "search"]

# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

#: FTS5 table + triggers. ``comm_id`` is the communications.id; the three
#: indexed columns are the subject, the cleaned body, and every
#: participant address and display name (sender included).
FTS_SCHEMA_SQL = """
CREATE VIRTUAL TABLE IF NOT EXISTS communications_fts USING fts5(
    comm_id UNINDEXED, subject, body, participants,
    tokenize='porter unicode61'
);

CREATE TRIGGER IF NOT EXISTS trg_comm_fts_insert AFTER INSERT ON communications BEGIN
    INSERT INTO communications_fts (comm_id, subject, body, participants)
    VALUES (NEW.id, COALESCE(NEW.subject, ''),
            COALESCE(NEW.search_text, NEW.original_text, ''),
            COALESCE(NEW.sender_address, '') || ' ' || COALESCE(NEW.sender_name, ''));
END;

CREATE TRIGGER IF NOT EXISTS trg_comm_fts_update AFTER UPDATE OF subject, search_text, original_text,
    sender_address, sender_name ON communications BEGIN
    UPDATE communications_fts
       SET subject = COALESCE(NEW.subject, ''),
           body = COALESCE(NEW.search_text, NEW.original_text, ''),
           participants = COALESCE(NEW.sender_address, '') || ' ' || COALESCE(NEW.sender_name, '') || ' ' ||
               COALESCE((SELECT group_concat(address || ' ' || COALESCE(name, ''), ' ')
                         FROM communication_participants WHERE communication_id = NEW.id), '')
     WHERE comm_id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS trg_comm_fts_delete AFTER DELETE ON communications BEGIN
    DELETE FROM communications_fts WHERE comm_id = OLD.id;
END;

CREATE TRIGGER IF NOT EXISTS trg_comm_fts_part_insert AFTER INSERT ON communication_participants BEGIN
    UPDATE communications_fts
       SET participants = COALESCE((SELECT sender_address FROM communications WHERE id = NEW.communication_id), '')
           || ' ' || COALESCE((SELECT sender_name FROM communications WHERE id = NEW.communication_id), '') || ' ' ||
           COALESCE((SELECT group_concat(address || ' ' || COALESCE(name, ''), ' ')
                     FROM communication_participants WHERE communication_id = NEW.communication_id), '')
     WHERE comm_id = NEW.communication_id;
END;

CREATE TRIGGER IF NOT EXISTS trg_comm_fts_part_update AFTER UPDATE ON communication_participants BEGIN
    UPDATE communications_fts
       SET participants = COALESCE((SELECT sender_address FROM communications WHERE id = NEW.communication_id), '')
           || ' ' || COALESCE((SELECT sender_name FROM communications WHERE id = NEW.communication_id), '') || ' ' ||
           COALESCE((SELECT group_concat(address || ' ' || COALESCE(name, ''), ' ')
                     FROM communication_participants WHERE communication_id = NEW.communication_id), '')
     WHERE comm_id = NEW.communication_id;
END;

CREATE TRIGGER IF NOT EXISTS trg_comm_fts_part_delete AFTER DELETE ON communication_participants BEGIN
    UPDATE communications_fts
       SET participants = COALESCE((SELECT sender_address FROM communications WHERE id = OLD.communication_id), '')
           || ' ' || COALESCE((SELECT sender_name FROM communications WHERE id = OLD.communication_id), '') || ' ' ||
           COALESCE((SELECT group_concat(address || ' ' || COALESCE(name, ''), ' ')
                     FROM communication_participants WHERE communication_id = OLD.communication_id), '')
     WHERE comm_id = OLD.communication_id;
END;
"""

#: Rebuild the index from scratch (migration backfill / repair).
FTS_REBUILD_SQL = """
DELETE FROM communications_fts;
INSERT INTO communications_fts (comm_id, subject, body, participants)
SELECT c.id, COALESCE(c.subject, ''), COALESCE(c.search_text, c.original_text, ''),
       COALESCE(c.sender_address, '') || ' ' || COALESCE(c.sender_name, '') || ' ' ||
       COALESCE((SELECT group_concat(p.address || ' ' || COALESCE(p.name, ''), ' ')
                 FROM communication_participants p WHERE p.communication_id = c.id), '')
FROM communications c;
"""


# ---------------------------------------------------------------------------
# Query model and parser
# ---------------------------------------------------------------------------

@dataclass
class SearchQuery:
    terms: list[str] = field(default_factory=list)       # free text (phrases kept quoted)
    from_: list[str] = field(default_factory=list)
    to: list[str] = field(default_factory=list)
    cc: list[str] = field(default_factory=list)
    subject: list[str] = field(default_factory=list)
    has_attachment: bool = False
    in_: str | None = None                               # inbox|sent|drafts|starred|archive|trash|spam|anywhere|<label name>
    labels: list[str] = field(default_factory=list)
    account: str | None = None
    is_unread: bool | None = None
    is_starred: bool | None = None
    before: datetime | None = None
    after: datetime | None = None
    unknown: list[str] = field(default_factory=list)     # operators we did not understand (kept as terms)

    def is_empty(self) -> bool:
        return not any((self.terms, self.from_, self.to, self.cc, self.subject, self.has_attachment,
                        self.in_, self.labels, self.account, self.is_unread is not None,
                        self.is_starred is not None, self.before, self.after))


#: A token is ``op:"quoted phrase"``, ``"quoted phrase"``, or a bare word.
_TOKEN = re.compile(r'([A-Za-z_]+:)?"([^"]*)"|(\S+)')
_OPERATORS = {"from", "to", "cc", "subject", "has", "in", "label", "account", "is",
              "before", "after", "newer_than", "older_than"}


def _parse_date(value: str) -> datetime | None:
    v = value.strip().replace("/", "-")
    for fmt in ("%Y-%m-%d", "%Y-%m", "%Y"):
        try:
            return datetime.strptime(v, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _parse_relative(value: str, now: datetime) -> datetime | None:
    m = re.fullmatch(r"(\d+)([dwmy])", value.strip().lower())
    if not m:
        return None
    n, unit = int(m.group(1)), m.group(2)
    days = {"d": 1, "w": 7, "m": 30, "y": 365}[unit] * n
    return now - timedelta(days=days)


def parse_query(q: str, *, now: datetime | None = None) -> SearchQuery:
    """Parse a mailbox search string. Unknown ``word:value`` tokens are
    treated as free text so a stray colon never hides results."""
    now = now or datetime.now(timezone.utc)
    sq = SearchQuery()
    # (token text, quoted?) — a quoted phrase is never split on its colon
    tokens: list[tuple[str, bool]] = []
    for m in _TOKEN.finditer(q or ""):
        if m.group(2) is not None:
            tokens.append(((m.group(1) or "") + m.group(2), m.group(1) is None))
        else:
            tokens.append((m.group(3), False))

    i = 0
    while i < len(tokens):
        tok, quoted = tokens[i]
        i += 1
        if quoted or ":" not in tok:
            if tok.strip():
                sq.terms.append(tok.strip())
            continue
        op, _, val = tok.partition(":")
        op = op.lower()
        if op not in _OPERATORS:
            sq.terms.append(tok)
            continue
        # operator value may be the next token when written as `from: ada`
        if not val and i < len(tokens):
            val = tokens[i][0]
            i += 1
        val = val.strip().strip('"')
        if not val:
            continue
        if op == "from":
            sq.from_.append(val)
        elif op == "to":
            sq.to.append(val)
        elif op == "cc":
            sq.cc.append(val)
        elif op == "subject":
            sq.subject.append(val)
        elif op == "has":
            if val.lower() in ("attachment", "attachments", "file"):
                sq.has_attachment = True
            else:
                sq.unknown.append(tok)
        elif op == "in":
            sq.in_ = val.lower()
        elif op == "label":
            sq.labels.append(val)
        elif op == "account":
            sq.account = val.lower()
        elif op == "is":
            v = val.lower()
            if v == "unread":
                sq.is_unread = True
            elif v == "read":
                sq.is_unread = False
            elif v == "starred":
                sq.is_starred = True
            elif v == "unstarred":
                sq.is_starred = False
            else:
                sq.unknown.append(tok)
        elif op in ("before", "after"):
            d = _parse_date(val)
            if d is None:
                sq.unknown.append(tok)
            elif op == "before":
                sq.before = d
            else:
                sq.after = d
        elif op == "newer_than":
            d = _parse_relative(val, now)
            if d is None:
                sq.unknown.append(tok)
            else:
                sq.after = d
        elif op == "older_than":
            d = _parse_relative(val, now)
            if d is None:
                sq.unknown.append(tok)
            else:
                sq.before = d
    return sq


# ---------------------------------------------------------------------------
# SQL
# ---------------------------------------------------------------------------

def _fts_term(term: str) -> str:
    """Quote a user term for FTS5 MATCH so punctuation (dots, @) is literal.

    A term ending in ``*`` keeps prefix matching; everything else is a
    phrase. Internal double quotes are doubled per FTS5 rules.
    """
    t = term.strip()
    prefix = t.endswith("*")
    if prefix:
        t = t[:-1]
    t = t.replace('"', '""')
    return f'"{t}"' + ("*" if prefix else "")


_SYSTEM_IN = {
    "inbox": ("kind", "inbox"), "sent": ("kind", "sent"), "drafts": ("kind", "drafts"),
    "draft": ("kind", "drafts"), "trash": ("kind", "trash"), "spam": ("kind", "spam"),
    "important": ("kind", "important"), "snoozed": ("kind", "snoozed"),
}


def build_sql(sq: SearchQuery, *, account_ids: list[str], limit: int = 50, offset: int = 0,
              count: bool = False) -> tuple[str, list]:
    """SQL over ``communications c`` returning matching rows newest first.

    ``account_ids`` scopes the search to what the caller may see. With
    ``count=True`` the statement returns a single ``n`` column.
    """
    where: list[str] = ["c.channel = 'email'", "c.is_current = 1"]
    params: list = []
    joins: list[str] = ["JOIN provider_accounts pa ON pa.id = c.account_id"]

    if account_ids:
        where.append(f"c.account_id IN ({','.join('?' * len(account_ids))})")
        params.extend(account_ids)
    else:
        where.append("0")

    # --- full text ---
    match_parts: list[str] = []
    if sq.terms:
        match_parts.append(" ".join(_fts_term(t) for t in sq.terms))
    for s in sq.subject:
        match_parts.append(f"subject:{_fts_term(s)}")
    if match_parts:
        joins.append("JOIN communications_fts f ON f.comm_id = c.id")
        where.append("communications_fts MATCH ?")
        params.append(" AND ".join(f"({p})" for p in match_parts))

    # --- participants ---
    for addr in sq.from_:
        where.append("(c.sender_address LIKE ? COLLATE NOCASE OR c.sender_name LIKE ? COLLATE NOCASE)")
        params.extend([f"%{addr}%", f"%{addr}%"])
    for role, values in (("to", sq.to), ("cc", sq.cc)):
        for addr in values:
            where.append(
                "EXISTS (SELECT 1 FROM communication_participants p WHERE p.communication_id = c.id "
                "AND p.role = ? AND (p.address LIKE ? COLLATE NOCASE OR p.name LIKE ? COLLATE NOCASE))")
            params.extend([role, f"%{addr}%", f"%{addr}%"])

    # --- flags ---
    if sq.is_unread is True:
        where.append("c.is_read = 0")
    elif sq.is_unread is False:
        where.append("c.is_read = 1")
    if sq.is_starred is True:
        where.append("c.is_starred = 1")
    elif sq.is_starred is False:
        where.append("c.is_starred = 0")
    if sq.has_attachment:
        where.append("EXISTS (SELECT 1 FROM attachments a WHERE a.communication_id = c.id)")

    # --- dates ---
    if sq.after:
        where.append("c.timestamp >= ?")
        params.append(sq.after.isoformat())
    if sq.before:
        where.append("c.timestamp < ?")
        params.append(sq.before.isoformat())

    # --- account ---
    if sq.account:
        where.append("(pa.email_address LIKE ? COLLATE NOCASE OR pa.display_name LIKE ? COLLATE NOCASE)")
        params.extend([f"%{sq.account}%", f"%{sq.account}%"])

    # --- folders and labels ---
    def _label_exists(col: str, value: str) -> None:
        where.append(
            "EXISTS (SELECT 1 FROM communication_labels cl JOIN mailbox_labels ml ON ml.id = cl.label_id "
            f"WHERE cl.communication_id = c.id AND ml.{col} = ? COLLATE NOCASE)")
        params.append(value)

    in_ = sq.in_
    include_trash_spam = in_ in ("trash", "spam", "anywhere", "all")
    if in_ and in_ not in ("anywhere", "all"):
        if in_ == "starred":
            where.append("c.is_starred = 1")
        elif in_ == "unread":
            where.append("c.is_read = 0")
        elif in_ in ("archive", "archived", "allmail", "all_mail"):
            where.append(
                "NOT EXISTS (SELECT 1 FROM communication_labels cl JOIN mailbox_labels ml ON ml.id = cl.label_id "
                "WHERE cl.communication_id = c.id AND ml.kind IN ('inbox', 'trash', 'spam'))")
        elif in_ in _SYSTEM_IN:
            col, val = _SYSTEM_IN[in_]
            _label_exists(col, val)
        else:
            where.append(
                "EXISTS (SELECT 1 FROM communication_labels cl JOIN mailbox_labels ml ON ml.id = cl.label_id "
                "WHERE cl.communication_id = c.id AND (ml.name = ? COLLATE NOCASE OR ml.provider_label_id = ?))")
            params.extend([in_, in_])
    for lab in sq.labels:
        where.append(
            "EXISTS (SELECT 1 FROM communication_labels cl JOIN mailbox_labels ml ON ml.id = cl.label_id "
            "WHERE cl.communication_id = c.id AND (ml.name = ? COLLATE NOCASE OR ml.provider_label_id = ?))")
        params.extend([lab, lab])
    if not include_trash_spam:
        where.append(
            "NOT EXISTS (SELECT 1 FROM communication_labels cl JOIN mailbox_labels ml ON ml.id = cl.label_id "
            "WHERE cl.communication_id = c.id AND ml.kind IN ('trash', 'spam'))")
        where.append("c.is_archived = 0")

    base = f"FROM communications c {' '.join(joins)} WHERE {' AND '.join(where)}"
    if count:
        return f"SELECT COUNT(*) AS n {base}", params
    sql = (
        "SELECT c.id, c.account_id, pa.email_address AS account_email, c.provider_thread_id, "
        "c.subject, c.snippet, c.sender_address, c.sender_name, c.timestamp, c.direction, "
        "c.is_read, c.is_starred, c.is_archived "
        f"{base} ORDER BY c.timestamp DESC LIMIT ? OFFSET ?"
    )
    return sql, params + [max(1, min(int(limit), 500)), max(0, int(offset))]


def search(conn, q: str, *, account_ids: list[str], limit: int = 50, offset: int = 0) -> dict:
    """Run a search; returns ``{"query": ..., "total": n, "items": [...]}``."""
    sq = parse_query(q)
    count_sql, count_params = build_sql(sq, account_ids=account_ids, count=True)
    total = conn.execute(count_sql, count_params).fetchone()["n"]
    sql, params = build_sql(sq, account_ids=account_ids, limit=limit, offset=offset)
    items = [dict(r) for r in conn.execute(sql, params)]
    if items:
        ids = [it["id"] for it in items]
        placeholders = ",".join("?" * len(ids))
        labels: dict[str, list[str]] = {}
        for r in conn.execute(
            f"SELECT cl.communication_id, ml.name FROM communication_labels cl "
            f"JOIN mailbox_labels ml ON ml.id = cl.label_id WHERE cl.communication_id IN ({placeholders})",
            ids,
        ):
            labels.setdefault(r["communication_id"], []).append(r["name"])
        for it in items:
            it["labels"] = sorted(labels.get(it["id"], []))
            it["is_read"] = bool(it["is_read"])
            it["is_starred"] = bool(it["is_starred"])
            it["is_archived"] = bool(it["is_archived"])
    return {
        "query": {
            "terms": sq.terms, "from": sq.from_, "to": sq.to, "cc": sq.cc, "subject": sq.subject,
            "has_attachment": sq.has_attachment, "in": sq.in_, "labels": sq.labels,
            "account": sq.account, "is_unread": sq.is_unread, "is_starred": sq.is_starred,
            "before": sq.before.isoformat() if sq.before else None,
            "after": sq.after.isoformat() if sq.after else None,
            "unknown": sq.unknown,
        },
        "total": total,
        "items": items,
        "limit": limit,
        "offset": offset,
    }
