"""Attachment metadata and the on-demand byte cache (Mail Client MAIL-15; TDD D-09).

- :func:`store_attachment_rows` writes the parts a :class:`ParsedEmail`
  carries into ``attachments`` (upsert on message + provider part id).
- :func:`cached_path` returns the local file for an attachment, fetching
  it through the account's adapter on first request and pruning the
  cache to ``mail_attachment_cache_mb`` by least-recent use.
"""

from __future__ import annotations

import logging
import os
import uuid
from pathlib import Path
from typing import Any

from . import config
from .models import ParsedEmail, _now_iso
from .providers import MailProvider

log = logging.getLogger(__name__)

DEFAULT_CACHE_MB = 2048


def store_attachment_rows(conn, communication_id: str, em: ParsedEmail) -> int:
    """Upsert the message's attachment parts. Returns rows written."""
    now = _now_iso()
    n = 0
    for a in em.attachments or []:
        pid = a.get("attachment_id")
        if not pid:
            continue
        conn.execute(
            """INSERT INTO attachments
               (id, communication_id, filename, mime_type, size_bytes, source, created_at,
                provider_attachment_id, content_id, is_inline)
               VALUES (?, ?, ?, ?, ?, 'provider', ?, ?, ?, ?)
               ON CONFLICT(communication_id, provider_attachment_id) DO UPDATE SET
                   filename = excluded.filename, mime_type = excluded.mime_type,
                   size_bytes = excluded.size_bytes, content_id = excluded.content_id,
                   is_inline = excluded.is_inline""",
            (str(uuid.uuid4()), communication_id,
             a.get("filename") or (f"inline-{a.get('content_id')}" if a.get("content_id") else "attachment"),
             a.get("mime_type"), a.get("size") or None, now,
             pid, a.get("content_id"), 1 if a.get("is_inline") else 0),
        )
        n += 1
    return n


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------

def _cache_root() -> Path:
    root = config.ATTACHMENT_CACHE_DIR
    root.mkdir(parents=True, exist_ok=True)
    return root


def _cache_file(account_id: str, attachment_id: str) -> Path:
    return _cache_root() / account_id / f"{attachment_id}.bin"


def prune_cache(budget_mb: int | None = None) -> int:
    """Delete least-recently-used files until the cache fits the budget. Returns bytes freed."""
    budget = (DEFAULT_CACHE_MB if budget_mb is None else max(1, int(budget_mb))) * 1024 * 1024
    root = _cache_root()
    files = []
    total = 0
    for p in root.rglob("*.bin"):
        try:
            st = p.stat()
        except OSError:
            continue
        files.append((st.st_atime, st.st_size, p))
        total += st.st_size
    freed = 0
    if total <= budget:
        return 0
    for _atime, size, p in sorted(files):
        try:
            p.unlink()
            freed += size
            total -= size
        except OSError:
            continue
        if total <= budget:
            break
    return freed


def cached_path(
    conn,
    attachment: dict,
    *,
    account: dict,
    session: Any,
    provider: MailProvider,
    rate_limiter=None,
    budget_mb: int | None = None,
) -> Path:
    """Return the local file for ``attachment`` (a row dict joined with the
    message's ``provider_message_id``), fetching it on first use."""
    path = _cache_file(account["id"], attachment["id"])
    if path.exists():
        os.utime(path, None)  # refresh recency
        return path
    data = provider.fetch_attachment(
        session, attachment["provider_message_id"], attachment["provider_attachment_id"],
        rate_limiter=rate_limiter,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".part")
    tmp.write_bytes(data)
    tmp.replace(path)
    if attachment.get("size_bytes") != len(data):
        conn.execute("UPDATE attachments SET size_bytes = ? WHERE id = ?", (len(data), attachment["id"]))
    prune_cache(budget_mb)
    return path
