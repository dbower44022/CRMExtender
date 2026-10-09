"""Mail API — the routes the mail surface talks to.

Started with the action outbox (Mail Client MAIL-14); the folder, thread,
and search routes of MAIL-16 join this module so mail stays out of the
3,600-line api.py (MAIL-55).

Permission model (mail-client-prd.md §6.2): mail actions require the
``owner`` role on the account in ``user_provider_accounts``; ``shared``
grants read only. Administrators get no mail actions on accounts they
do not own.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from ...database import get_connection
from ...mail_actions import (
    MailActionError,
    discard_action,
    enqueue,
    pending_counts,
    push_pending,
    retry_action,
)

router = APIRouter()


def _err(message: str, status: int = 400) -> JSONResponse:
    return JSONResponse({"error": message}, status_code=status)


def _account_role(request: Request, account_id: str) -> str | None:
    """'owner' / 'shared' for the caller on this account, else None."""
    uid = request.state.user["id"]
    cid = request.state.customer_id
    with get_connection() as conn:
        row = conn.execute(
            """SELECT upa.role FROM user_provider_accounts upa
               JOIN provider_accounts pa ON pa.id = upa.account_id
               WHERE upa.user_id = ? AND upa.account_id = ? AND pa.customer_id = ?""",
            (uid, account_id, cid),
        ).fetchone()
    return row["role"] if row else None


def _visible_account_ids(request: Request) -> list[str]:
    uid = request.state.user["id"]
    with get_connection() as conn:
        return [r["account_id"] for r in conn.execute(
            "SELECT account_id FROM user_provider_accounts WHERE user_id = ?", (uid,))]


def _account_for_communications(conn, communication_ids: list[str]) -> str | None:
    """The single account the given communications belong to, or None if mixed/empty."""
    if not communication_ids:
        return None
    placeholders = ",".join("?" * len(communication_ids))
    rows = conn.execute(
        f"SELECT DISTINCT account_id FROM communications WHERE id IN ({placeholders})",
        tuple(communication_ids),
    ).fetchall()
    return rows[0]["account_id"] if len(rows) == 1 else None


# ---------------------------------------------------------------------------
# Folders and threads (MAIL-16)
# ---------------------------------------------------------------------------

def _scope(request: Request, account_id: str | None) -> list[str]:
    """Visible accounts, narrowed to one when ``account_id`` is given (not 'unified')."""
    accounts = _visible_account_ids(request)
    if account_id and account_id != "unified":
        accounts = [a for a in accounts if a == account_id]
    return accounts


@router.get("/mail/folders")
def mail_folders(request: Request):
    """Per-account folder tree with locally computed unread/total counts, plus
    the unified set. Scheduler state per account is attached when running."""
    from ...mail_threads import folders
    from ...scheduler import get_scheduler

    with get_connection() as conn:
        out = folders(conn, account_ids=_visible_account_ids(request))
    sched = get_scheduler()
    st = sched.status()["accounts"] if (sched is not None and sched.running) else {}
    for a in out["accounts"]:
        s = st.get(a["id"])
        a["sync"] = ({"running": s["running"], "last_finished": s["last_finished"],
                      "next_due_at": s["next_due_at"], "last_error": s["last_error"]} if s else None)
    return out


@router.get("/mail/threads")
def mail_threads(request: Request, folder: str = "inbox", account_id: str | None = None,
                 label_id: str | None = None, q: str | None = None, limit: int = 50, offset: int = 0):
    """Threads in a folder (``inbox``, ``starred``, ``sent``, ``drafts``,
    ``archive``, ``all``, ``trash``, ``spam``, ``important``, ``unread``) or
    under a user label (``label_id`` = mailbox_labels.id), newest first.
    ``account_id`` narrows to one account; omitted or ``unified`` means all."""
    from ...mail_threads import thread_list

    accounts = _scope(request, account_id)
    with get_connection() as conn:
        try:
            return thread_list(conn, account_ids=accounts, folder=None if label_id else folder,
                               label_row_id=label_id, q=q, limit=limit, offset=offset)
        except ValueError as exc:
            return _err(str(exc))


@router.get("/mail/threads/{account_id}/{thread_id}")
def mail_thread_detail(request: Request, account_id: str, thread_id: str):
    """Every message of one thread, oldest first, with bodies, participants,
    labels, attachments, and the CRM conversation it belongs to."""
    from ...mail_threads import thread_detail

    if account_id not in _visible_account_ids(request):
        return _err("Not found", 404)
    with get_connection() as conn:
        out = thread_detail(conn, account_id=account_id, thread_id=thread_id)
    return out if out else _err("Not found", 404)


# ---------------------------------------------------------------------------
# Attachments (MAIL-15 / MAIL-26)
# ---------------------------------------------------------------------------

def _attachment_row(conn, where: str, params: tuple) -> dict | None:
    row = conn.execute(
        f"""SELECT a.*, c.provider_message_id, c.account_id
            FROM attachments a JOIN communications c ON c.id = a.communication_id
            WHERE {where}""", params).fetchone()
    return dict(row) if row else None


def _serve_attachment(request: Request, row: dict, *, download: bool):
    from pathlib import Path

    from fastapi.responses import FileResponse

    from ... import config
    from ...auth import get_credentials_for_account
    from ...mail_attachments import cached_path
    from ...providers import get_provider
    from ...rate_limiter import RateLimiter
    from ...settings import get_setting

    if row["account_id"] not in _visible_account_ids(request):
        return _err("Not found", 404)
    if not row.get("provider_attachment_id") or not row.get("provider_message_id"):
        return _err("This attachment has no provider reference; it predates attachment capture", 409)
    with get_connection() as conn:
        account = conn.execute("SELECT * FROM provider_accounts WHERE id = ?", (row["account_id"],)).fetchone()
        account = dict(account)
        try:
            creds = get_credentials_for_account(Path(account["auth_token_path"]))
            provider = get_provider(account.get("provider") or "gmail")
            budget = get_setting(request.state.customer_id, "mail_attachment_cache_mb")
            path = cached_path(
                conn, row, account=account, session=creds, provider=provider,
                rate_limiter=RateLimiter(rate=config.GMAIL_RATE_LIMIT),
                budget_mb=int(budget) if budget else None,
            )
        except Exception as exc:
            return _err(f"Could not fetch attachment: {exc}", 502)
    media = row.get("mime_type") or "application/octet-stream"
    # Never let a browser execute a served attachment as a page.
    if media.lower() in ("text/html", "application/xhtml+xml", "image/svg+xml", "application/javascript"):
        download = True
    headers = {"X-Content-Type-Options": "nosniff", "Cache-Control": "private, max-age=3600"}
    disposition = "attachment" if download else "inline"
    # FileResponse only emits Content-Disposition when a filename is given;
    # pass it for both forms so the browser always has the real name.
    return FileResponse(
        str(path), media_type=media, filename=row["filename"],
        headers=headers, content_disposition_type=disposition,
    )


@router.get("/mail/attachments/{attachment_id}")
def mail_attachment(request: Request, attachment_id: str, download: int = 0):
    """Stream one attachment, fetching it from the provider on first use.
    ``?download=1`` forces a download; images and PDFs otherwise display inline."""
    with get_connection() as conn:
        row = _attachment_row(conn, "a.id = ?", (attachment_id,))
    if not row:
        return _err("Not found", 404)
    return _serve_attachment(request, row, download=bool(download))


@router.get("/mail/attachments/cid/{communication_id}/{content_id}")
def mail_attachment_cid(request: Request, communication_id: str, content_id: str):
    """Resolve an inline ``cid:`` image reference for the message frame."""
    with get_connection() as conn:
        row = _attachment_row(conn, "a.communication_id = ? AND a.content_id = ?", (communication_id, content_id))
    if not row:
        return _err("Not found", 404)
    return _serve_attachment(request, row, download=False)


# ---------------------------------------------------------------------------
# Search (MAIL-12)
# ---------------------------------------------------------------------------

@router.get("/mail/search")
def mail_search(request: Request, q: str = "", limit: int = 50, offset: int = 0):
    """Full-text mail search with mailbox operators over the caller's accounts.

    Operators: from:, to:, cc:, subject:, has:attachment, in:<folder|label>,
    label:, account:, is:unread|read|starred|unstarred, before:/after:
    (YYYY-MM-DD), newer_than:/older_than: (7d, 2w, 3m, 1y). Quoted phrases
    are matched exactly. Trash and spam are excluded unless named.
    """
    from ...mail_search import search

    accounts = _visible_account_ids(request)
    with get_connection() as conn:
        return search(conn, q or "", account_ids=accounts, limit=limit, offset=offset)


# ---------------------------------------------------------------------------
# Actions
# ---------------------------------------------------------------------------

@router.post("/mail/actions")
async def mail_action_create(request: Request):
    """Apply a mail action locally and queue it for the provider.

    Body: ``{"action": "archive", "communication_ids": [...], "label_id"?: str,
    "payload"?: {...}, "account_id"?: str}``. The account is inferred from
    the communications when omitted; all targets must be in one account.
    """
    try:
        body = await request.json()
    except Exception:
        return _err("Invalid JSON")
    comm_ids = [c for c in (body.get("communication_ids") or []) if isinstance(c, str)]
    if not comm_ids:
        return _err("communication_ids required")
    with get_connection() as conn:
        account_id = body.get("account_id") or _account_for_communications(conn, comm_ids)
    if not account_id:
        return _err("targets must belong to one account")
    if _account_role(request, account_id) != "owner":
        return _err("Only the account owner can act on its mail", 403)

    with get_connection() as conn:
        try:
            row = enqueue(
                conn,
                account_id=account_id,
                kind=body.get("action", ""),
                communication_ids=comm_ids,
                label_id=body.get("label_id"),
                payload=body.get("payload") or None,
                created_by=request.state.user["id"],
            )
        except MailActionError as exc:
            return _err(str(exc))
    return JSONResponse(row, status_code=201)


@router.get("/mail/actions")
def mail_actions_list(request: Request, status: str | None = None, account_id: str | None = None,
                      limit: int = 100):
    """Queue rows for the caller's accounts, newest first."""
    accounts = _visible_account_ids(request)
    if account_id:
        accounts = [a for a in accounts if a == account_id]
    if not accounts:
        return {"items": [], "counts": {"pending": 0, "failed": 0}}
    placeholders = ",".join("?" * len(accounts))
    where = f"account_id IN ({placeholders})"
    params: list = list(accounts)
    if status:
        where += " AND status = ?"
        params.append(status)
    with get_connection() as conn:
        rows = conn.execute(
            f"SELECT * FROM mail_actions WHERE {where} ORDER BY created_at DESC LIMIT ?",
            (*params, max(1, min(int(limit), 500))),
        ).fetchall()
    from ...mail_actions import _decode
    return {"items": [_decode(dict(r)) for r in rows], "counts": pending_counts(accounts)}


@router.post("/mail/actions/{action_id}/retry")
def mail_action_retry(request: Request, action_id: str):
    with get_connection() as conn:
        row = conn.execute("SELECT account_id FROM mail_actions WHERE id = ?", (action_id,)).fetchone()
    if not row:
        return _err("Not found", 404)
    if _account_role(request, row["account_id"]) != "owner":
        return _err("Only the account owner can act on its mail", 403)
    with get_connection() as conn:
        return retry_action(conn, action_id)


@router.post("/mail/actions/{action_id}/discard")
def mail_action_discard(request: Request, action_id: str):
    with get_connection() as conn:
        row = conn.execute("SELECT account_id FROM mail_actions WHERE id = ?", (action_id,)).fetchone()
    if not row:
        return _err("Not found", 404)
    if _account_role(request, row["account_id"]) != "owner":
        return _err("Only the account owner can act on its mail", 403)
    with get_connection() as conn:
        return discard_action(conn, action_id)


@router.post("/mail/actions/push")
def mail_actions_push(request: Request, account_id: str | None = None):
    """Push due pending actions now, for one account or all the caller owns."""
    from pathlib import Path

    from ... import config
    from ...auth import get_credentials_for_account
    from ...providers import get_provider
    from ...rate_limiter import RateLimiter
    from ...settings import get_setting

    uid = request.state.user["id"]
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT pa.* FROM provider_accounts pa
               JOIN user_provider_accounts upa ON upa.account_id = pa.id
               WHERE upa.user_id = ? AND upa.role = 'owner' AND pa.is_active = 1""",
            (uid,),
        ).fetchall()
    accounts = [dict(r) for r in rows if not account_id or r["id"] == account_id]
    if not accounts:
        return _err("No owned active account matches", 404)

    retry_max = get_setting(request.state.customer_id, "mail_action_retry_max")
    limiter = RateLimiter(rate=config.GMAIL_RATE_LIMIT)
    results = {}
    for account in accounts:
        try:
            creds = get_credentials_for_account(Path(account["auth_token_path"]))
            provider = get_provider(account.get("provider") or "gmail")
            results[account["email_address"]] = push_pending(
                account, creds, provider,
                retry_max=int(retry_max) if retry_max else None, rate_limiter=limiter,
            )
        except Exception as exc:
            results[account["email_address"]] = {"error": str(exc)}
    return {"results": results, "counts": pending_counts([a["id"] for a in accounts])}
