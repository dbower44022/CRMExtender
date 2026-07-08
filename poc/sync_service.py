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


def run_full_sync(*, customer_id: str, user_id: str) -> dict:
    """Run the sync pipeline synchronously; returns a structured summary."""
    from . import config
    from .auth import get_credentials_for_account
    from .gmail_client import get_user_email
    from .rate_limiter import RateLimiter
    from .sync import (
        incremental_sync,
        initial_sync,
        process_conversations,
        sync_contacts,
    )

    # Only sync accounts the user has access to
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

    result = {
        "accounts": len(accounts),
        "contacts": 0,
        "emails_fetched": 0,
        "triaged": 0,
        "summarized": 0,
        "enriched": 0,
        "duplicate_candidates": 0,
        "errors": [],
    }
    if not accounts:
        result["errors"].append("No accounts registered.")
        return result

    sync_start = _now_iso()

    gmail_limiter = RateLimiter(rate=config.GMAIL_RATE_LIMIT)
    claude_limiter = RateLimiter(rate=config.CLAUDE_RATE_LIMIT)

    for account in accounts:
        account_id = account["id"]
        email_addr = account["email_address"]

        token_path = Path(account["auth_token_path"])
        try:
            creds = get_credentials_for_account(token_path)
        except Exception as exc:
            log.warning("Auth failed for %s: %s", email_addr, exc)
            result["errors"].append(f"{email_addr}: auth failed ({exc})")
            continue

        user_email = get_user_email(creds)

        try:
            result["contacts"] += sync_contacts(
                creds, rate_limiter=gmail_limiter,
                customer_id=customer_id, user_id=user_id,
            )
        except Exception as exc:
            log.warning("Contact sync failed for %s: %s", email_addr, exc)
            result["errors"].append(f"{email_addr}: contact sync failed ({exc})")

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
            result["emails_fetched"] += sync_result.get("messages_fetched", 0)
        except Exception as exc:
            log.warning("Email sync failed for %s: %s", email_addr, exc)
            result["errors"].append(f"{email_addr}: email sync failed ({exc})")

        try:
            triaged, summarized, _topics = process_conversations(
                account_id, creds, user_email,
                rate_limiter=gmail_limiter,
                claude_limiter=claude_limiter,
            )
            result["triaged"] += triaged
            result["summarized"] += summarized
        except Exception as exc:
            log.warning("Processing failed for %s: %s", email_addr, exc)
            result["errors"].append(f"{email_addr}: processing failed ({exc})")

    # Batch-enrich companies that have a domain but no completed enrichment run
    try:
        from .enrichment_pipeline import enrich_new_companies
        enrich_result = enrich_new_companies()
        result["enriched"] = enrich_result.get("enriched", 0)
    except Exception as exc:
        result["errors"].append(f"batch enrichment failed ({exc})")

    # Identity resolution over contacts created during this sync
    # (Identity Resolution Sub-PRD §7 — sync-time entry point). Batched
    # so the co-participant firehose doesn't score inline per contact.
    try:
        from .identity_resolution import resolve_contacts_since
        idr = resolve_contacts_since(
            sync_start, customer_id=customer_id, source="email_sync")
        result["duplicate_candidates"] = idr["candidates_created"]
    except Exception as exc:
        log.warning("Sync-time identity resolution failed: %s", exc)

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
