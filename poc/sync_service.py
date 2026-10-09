"""Full sync pipeline shared by the legacy dashboard route and the JSON API.

Runs contact sync, email sync (initial or incremental), conversation
processing, and batch company enrichment for every active provider
account a user can access. Also tracks a single in-process background
run for the API's async trigger.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from pathlib import Path

from .database import get_connection

log = logging.getLogger(__name__)


def _accounts_for(customer_id: str, user_id: str | None) -> list[dict]:
    """Active accounts the user can access, or the customer's when unmapped."""
    accounts: list[dict] = []
    if user_id:
        with get_connection() as conn:
            rows = conn.execute(
                """SELECT pa.* FROM provider_accounts pa
                   JOIN user_provider_accounts upa ON upa.account_id = pa.id
                   WHERE upa.user_id = ? AND pa.is_active = 1
                   ORDER BY pa.created_at""",
                (user_id,),
            ).fetchall()
            accounts = [dict(a) for a in rows]
    if not accounts:
        # Fallback: if no user_provider_accounts rows, use customer's accounts
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM provider_accounts WHERE customer_id = ? AND is_active = 1 ORDER BY created_at",
                (customer_id,),
            ).fetchall()
            accounts = [dict(a) for a in rows]
    return accounts


def _empty_result(n_accounts: int = 0) -> dict:
    return {
        "accounts": n_accounts,
        "contacts": 0,
        "emails_fetched": 0,
        "actions_pushed": 0,
        "actions_failed": 0,
        "triaged": 0,
        "summarized": 0,
        "enriched": 0,
        "duplicate_candidates": 0,
        "errors": [],
    }


def _mark_reauth_if_needed(account_id: str, exc: Exception) -> None:
    """A refresh failure in non-interactive mode parks the account (MAIL-38)."""
    from .auth import ReauthRequired
    if not isinstance(exc, ReauthRequired):
        return
    from .account_health import mark_needs_reauth
    try:
        with get_connection() as conn:
            mark_needs_reauth(conn, account_id, exc.reason)
    except Exception:
        log.exception("Could not mark account %s needs_reauth", account_id)


def sync_account(
    account: dict,
    *,
    customer_id: str,
    user_id: str | None,
    gmail_limiter,
) -> dict:
    """Sync one provider account: labels, queued actions, contacts, mail.

    Returns ``{"contacts", "emails_fetched", "actions_pushed",
    "actions_failed", "errors": [...]}``. Never raises for a provider or
    auth problem; those land in ``errors``. The scheduler (MAIL-13) runs
    this per account on its own thread; ``run_full_sync`` runs it in a
    loop. Summarization is not here — see :func:`post_sync_pass`.
    """
    from .auth import get_credentials_for_account
    from .providers import get_provider
    from .sync import incremental_sync, initial_sync, sync_contacts

    out = {"contacts": 0, "emails_fetched": 0, "actions_pushed": 0,
           "actions_failed": 0, "errors": []}
    account_id = account["id"]
    email_addr = account["email_address"]

    token_path = Path(account["auth_token_path"] or "")
    try:
        creds = get_credentials_for_account(token_path)
    except Exception as exc:
        log.warning("Auth failed for %s: %s", email_addr, exc)
        out["errors"].append(f"{email_addr}: auth failed ({exc})")
        _mark_reauth_if_needed(account_id, exc)
        return out

    provider = get_provider(account.get("provider") or "gmail")
    try:
        provider.get_user_email(creds)
    except Exception as exc:
        log.warning("Provider rejected credentials for %s: %s", email_addr, exc)
        out["errors"].append(f"{email_addr}: provider rejected credentials ({exc})")
        return out

    # Label list first so membership rows written by the sync below
    # point at named, typed labels rather than placeholders (MAIL-08).
    from .mail_state import refresh_labels
    refresh_labels(account, creds, provider, rate_limiter=gmail_limiter)

    # Push the user's queued actions before pulling the delta (MAIL-14),
    # so the provider reflects them and the delta does not undo them.
    try:
        from .mail_actions import push_pending
        from .settings import get_setting
        retry_max = get_setting(customer_id, "mail_action_retry_max")
        pushed = push_pending(
            account, creds, provider,
            retry_max=int(retry_max) if retry_max else None,
            rate_limiter=gmail_limiter,
        )
        out["actions_pushed"] += pushed["pushed"]
        out["actions_failed"] += pushed["failed"]
    except Exception as exc:
        log.warning("Action push failed for %s: %s", email_addr, exc)
        out["errors"].append(f"{email_addr}: action push failed ({exc})")

    try:
        out["contacts"] += sync_contacts(
            creds, rate_limiter=gmail_limiter,
            customer_id=customer_id, user_id=user_id,
        )
    except Exception as exc:
        log.warning("Contact sync failed for %s: %s", email_addr, exc)
        out["errors"].append(f"{email_addr}: contact sync failed ({exc})")

    try:
        if account["initial_sync_done"]:
            sync_result = incremental_sync(
                account_id, creds, rate_limiter=gmail_limiter,
                customer_id=customer_id, user_id=user_id,
            )
        else:
            sync_result = initial_sync(
                account_id, creds, rate_limiter=gmail_limiter,
                customer_id=customer_id, user_id=user_id,
            )
        out["emails_fetched"] += sync_result.get("messages_fetched", 0)
    except Exception as exc:
        log.warning("Email sync failed for %s: %s", email_addr, exc)
        out["errors"].append(f"{email_addr}: email sync failed ({exc})")

    return out


def post_sync_pass(
    *,
    customer_id: str,
    since_iso: str,
    gmail_limiter=None,
    claude_limiter=None,
) -> dict:
    """The cross-account tail of a sync: summarization (MAIL-19), company
    enrichment, and identity resolution over contacts created since
    ``since_iso``. Returns ``{"triaged", "summarized", "enriched",
    "duplicate_candidates", "errors": [...]}``.
    """
    from . import config
    from .rate_limiter import RateLimiter
    from .sync import process_conversations

    out = {"triaged": 0, "summarized": 0, "enriched": 0, "duplicate_candidates": 0, "errors": []}
    gmail_limiter = gmail_limiter or RateLimiter(rate=config.GMAIL_RATE_LIMIT)
    claude_limiter = claude_limiter or RateLimiter(rate=config.CLAUDE_RATE_LIMIT)

    # Summarize once, after every account has synced (MAIL-19): running it
    # inside the loop let one account's backlog block the next account's
    # sync for the length of the summarization pass.
    try:
        from .settings import get_setting
        settle = get_setting(customer_id, "summarize_settle_minutes")
        cap = get_setting(customer_id, "summarize_max_per_sync")
        triaged, summarized, _topics = process_conversations(
            None, None, None,
            rate_limiter=gmail_limiter,
            claude_limiter=claude_limiter,
            settle_minutes=int(settle) if settle else None,
            max_per_run=int(cap) if cap else None,
        )
        out["triaged"] += triaged
        out["summarized"] += summarized
    except Exception as exc:
        log.warning("Summarization failed: %s", exc)
        out["errors"].append(f"summarization failed ({exc})")

    # Batch-enrich companies that have a domain but no completed enrichment run
    try:
        from .enrichment_pipeline import enrich_new_companies
        enrich_result = enrich_new_companies()
        out["enriched"] = enrich_result.get("enriched", 0)
    except Exception as exc:
        out["errors"].append(f"batch enrichment failed ({exc})")

    # Identity resolution over contacts created during this sync
    # (Identity Resolution Sub-PRD §7 — sync-time entry point). Batched
    # so the co-participant firehose doesn't score inline per contact.
    try:
        from .identity_resolution import resolve_contacts_since
        idr = resolve_contacts_since(
            since_iso, customer_id=customer_id, source="email_sync")
        out["duplicate_candidates"] = idr["candidates_created"]
    except Exception as exc:
        log.warning("Sync-time identity resolution failed: %s", exc)

    return out


def merge_results(target: dict, part: dict) -> dict:
    """Add a sync_account / post_sync_pass result into a full-run summary."""
    for key, val in part.items():
        if key == "errors":
            target.setdefault("errors", []).extend(val)
        elif isinstance(val, (int, float)):
            target[key] = target.get(key, 0) + val
    return target


def run_full_sync(*, customer_id: str, user_id: str) -> dict:
    """Run the sync pipeline synchronously; returns a structured summary.

    Every account the user can access is synced in order, then the
    cross-account pass runs once. The scheduler (MAIL-13) uses the same
    two building blocks with accounts on their own threads.
    """
    from . import config
    from .rate_limiter import RateLimiter

    accounts = _accounts_for(customer_id, user_id)
    result = _empty_result(len(accounts))
    if not accounts:
        result["errors"].append("No accounts registered.")
        return result

    sync_start = _now_iso()
    gmail_limiter = RateLimiter(rate=config.GMAIL_RATE_LIMIT)
    claude_limiter = RateLimiter(rate=config.CLAUDE_RATE_LIMIT)

    for account in accounts:
        merge_results(result, sync_account(
            account, customer_id=customer_id, user_id=user_id, gmail_limiter=gmail_limiter,
        ))

    merge_results(result, post_sync_pass(
        customer_id=customer_id, since_iso=sync_start,
        gmail_limiter=gmail_limiter, claude_limiter=claude_limiter,
    ))
    return result


# ---------------------------------------------------------------------------
# Background run tracking (single in-process run at a time)
# ---------------------------------------------------------------------------

_state_lock = threading.Lock()
_state: dict = {"running": False, "started_at": None, "completed_at": None,
                "result": None, "error": None}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def start_background_sync(*, customer_id: str, user_id: str) -> bool:
    """Start a background sync. Returns False if one is already running."""
    with _state_lock:
        if _state["running"]:
            return False
        _state.update(running=True, started_at=_now_iso(),
                      completed_at=None, result=None, error=None)

    def _run() -> None:
        try:
            result = run_full_sync(customer_id=customer_id, user_id=user_id)
            with _state_lock:
                _state.update(running=False, completed_at=_now_iso(),
                              result=result)
        except Exception as exc:  # keep status consistent on crash
            log.exception("Background sync failed")
            with _state_lock:
                _state.update(running=False, completed_at=_now_iso(),
                              error=str(exc))

    threading.Thread(target=_run, name="crm-sync", daemon=True).start()
    return True


def sync_status() -> dict:
    with _state_lock:
        return dict(_state)


# ---------------------------------------------------------------------------
# Calendar sync (same single-slot background pattern as the email sync)
# ---------------------------------------------------------------------------

def run_calendar_sync(*, customer_id: str, user_id: str) -> dict:
    """Sync calendar events for every active account the user can access."""
    from . import config
    from .auth import get_credentials_for_account
    from .calendar_client import CalendarScopeError
    from .calendar_sync import sync_all_calendars
    from .rate_limiter import RateLimiter

    with get_connection() as conn:
        rows = conn.execute(
            """SELECT pa.* FROM provider_accounts pa
               JOIN user_provider_accounts upa ON upa.account_id = pa.id
               WHERE upa.user_id = ? AND pa.is_active = 1
               ORDER BY pa.created_at""",
            (user_id,),
        ).fetchall()
        accounts = [dict(a) for a in rows]

    if not accounts:
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM provider_accounts WHERE customer_id = ? AND is_active = 1 ORDER BY created_at",
                (customer_id,),
            ).fetchall()
            accounts = [dict(a) for a in rows]

    result = {
        "accounts": len(accounts),
        "events_created": 0,
        "events_updated": 0,
        "attendees_matched": 0,
        "errors": [],
    }
    if not accounts:
        result["errors"].append("No accounts registered.")
        return result

    rate_limiter = RateLimiter(rate=config.GMAIL_RATE_LIMIT)
    for account in accounts:
        email_addr = account["email_address"]
        token_path = Path(account["auth_token_path"])
        try:
            creds = get_credentials_for_account(token_path)
        except Exception as exc:
            log.warning("Auth failed for %s: %s", email_addr, exc)
            result["errors"].append(f"{email_addr}: auth failed ({exc})")
            continue
        try:
            acct_result = sync_all_calendars(
                account["id"], creds,
                rate_limiter=rate_limiter,
                customer_id=customer_id,
                user_id=user_id,
            )
        except CalendarScopeError as exc:
            result["errors"].append(f"{email_addr}: {exc}")
            continue
        except Exception as exc:
            log.warning("Calendar sync failed for %s: %s", email_addr, exc)
            result["errors"].append(f"{email_addr}: sync failed ({exc})")
            continue
        if acct_result.get("error"):
            result["errors"].append(f"{email_addr}: {acct_result['error']}")
            continue
        result["events_created"] += acct_result.get("events_created", 0)
        result["events_updated"] += acct_result.get("events_updated", 0)
        result["attendees_matched"] += acct_result.get("attendees_matched", 0)

    return result


_cal_state_lock = threading.Lock()
_cal_state: dict = {"running": False, "started_at": None, "completed_at": None,
                    "result": None, "error": None}


def start_background_calendar_sync(*, customer_id: str, user_id: str) -> bool:
    """Start a background calendar sync. False if one is already running."""
    with _cal_state_lock:
        if _cal_state["running"]:
            return False
        _cal_state.update(running=True, started_at=_now_iso(),
                          completed_at=None, result=None, error=None)

    def _run() -> None:
        try:
            result = run_calendar_sync(customer_id=customer_id, user_id=user_id)
            with _cal_state_lock:
                _cal_state.update(running=False, completed_at=_now_iso(),
                                  result=result)
        except Exception as exc:
            log.exception("Background calendar sync failed")
            with _cal_state_lock:
                _cal_state.update(running=False, completed_at=_now_iso(),
                                  error=str(exc))

    threading.Thread(target=_run, name="crm-calendar-sync", daemon=True).start()
    return True


def calendar_sync_status() -> dict:
    with _cal_state_lock:
        return dict(_cal_state)
