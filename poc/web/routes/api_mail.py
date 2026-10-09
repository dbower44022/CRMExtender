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
