"""Dashboard route — overview counts and recent conversations."""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from ...database import get_connection

router = APIRouter()
log = logging.getLogger(__name__)


@router.get("/")
def dashboard(request: Request):
    templates = request.app.state.templates
    user = request.state.user
    cid = request.state.customer_id

    with get_connection() as conn:
        counts = {
            "conversations_total": conn.execute(
                "SELECT COUNT(*) AS c FROM conversations WHERE customer_id = ?",
                (cid,),
            ).fetchone()["c"],
            "conversations_open": conn.execute(
                "SELECT COUNT(*) AS c FROM conversations "
                "WHERE customer_id = ? AND triage_result IS NULL AND dismissed = 0",
                (cid,),
            ).fetchone()["c"],
            "conversations_closed": conn.execute(
                "SELECT COUNT(*) AS c FROM conversations "
                "WHERE customer_id = ? AND dismissed = 1",
                (cid,),
            ).fetchone()["c"],
            "contacts": conn.execute(
                "SELECT COUNT(*) AS c FROM contacts WHERE customer_id = ?",
                (cid,),
            ).fetchone()["c"],
            "companies": conn.execute(
                "SELECT COUNT(*) AS c FROM companies "
                "WHERE customer_id = ? AND status = 'active'",
                (cid,),
            ).fetchone()["c"],
            "projects": conn.execute(
                "SELECT COUNT(*) AS c FROM projects "
                "WHERE customer_id = ? AND status = 'active'",
                (cid,),
            ).fetchone()["c"],
            "topics": conn.execute(
                "SELECT COUNT(*) AS c FROM topics t "
                "JOIN projects p ON p.id = t.project_id "
                "WHERE p.customer_id = ?",
                (cid,),
            ).fetchone()["c"],
            "events": conn.execute(
                "SELECT COUNT(*) AS c FROM events"
            ).fetchone()["c"],
        }

        recent = conn.execute(
            "SELECT * FROM conversations WHERE customer_id = ? "
            "ORDER BY last_activity_at DESC LIMIT 10",
            (cid,),
        ).fetchall()
        recent_conversations = [dict(r) for r in recent]

        top_companies = [dict(r) for r in conn.execute(
            """SELECT c.id, c.name, c.domain, es.score_value AS score
               FROM entity_scores es
               JOIN companies c ON c.id = es.entity_id
               WHERE es.entity_type = 'company'
                 AND es.score_type = 'relationship_strength'
                 AND c.customer_id = ?
               ORDER BY es.score_value DESC
               LIMIT 5""",
            (cid,),
        ).fetchall()]

        top_contacts = [dict(r) for r in conn.execute(
            """SELECT ct.id, ct.name, ci.value AS email,
                      co.name AS company_name, es.score_value AS score
               FROM entity_scores es
               JOIN contacts ct ON ct.id = es.entity_id
               LEFT JOIN contact_identifiers ci
                 ON ci.contact_id = ct.id AND ci.type = 'email'
               LEFT JOIN contact_companies ccx
                 ON ccx.contact_id = ct.id AND ccx.is_primary = 1 AND ccx.is_current = 1
               LEFT JOIN companies co ON co.id = ccx.company_id
               WHERE es.entity_type = 'contact'
                 AND es.score_type = 'relationship_strength'
                 AND ct.customer_id = ?
               ORDER BY es.score_value DESC
               LIMIT 5""",
            (cid,),
        ).fetchall()]

        counts["scored_companies"] = conn.execute(
            """SELECT COUNT(*) AS c FROM entity_scores es
               JOIN companies co ON co.id = es.entity_id
               WHERE es.entity_type = 'company'
                 AND es.score_type = 'relationship_strength'
                 AND co.customer_id = ?""",
            (cid,),
        ).fetchone()["c"]
        counts["scored_contacts"] = conn.execute(
            """SELECT COUNT(*) AS c FROM entity_scores es
               JOIN contacts ct ON ct.id = es.entity_id
               WHERE es.entity_type = 'contact'
                 AND es.score_type = 'relationship_strength'
                 AND ct.customer_id = ?""",
            (cid,),
        ).fetchone()["c"]

    return templates.TemplateResponse(request, "dashboard.html", {
        "active_nav": "dashboard",
        "counts": counts,
        "recent_conversations": recent_conversations,
        "top_companies": top_companies,
        "top_contacts": top_contacts,
    })


@router.post("/sync", response_class=HTMLResponse)
def sync_now(request: Request):
    """Run the full sync pipeline for the current user's accounts."""
    from ...auth import get_credentials_for_account
    from ...gmail_client import get_user_email
    from ...rate_limiter import RateLimiter
    from ...sync import (
        incremental_sync,
        initial_sync,
        process_conversations,
        sync_contacts,
    )
    from ... import config

    user = request.state.user
    uid = user["id"]
    cid = request.state.customer_id

    # Only sync accounts the user has access to
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT pa.* FROM provider_accounts pa
               JOIN user_provider_accounts upa ON upa.account_id = pa.id
               WHERE upa.user_id = ?
               ORDER BY pa.created_at""",
            (uid,),
        ).fetchall()
        accounts = [dict(a) for a in rows]

    if not accounts:
        # Fallback: if no user_provider_accounts rows, use customer's accounts
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM provider_accounts WHERE customer_id = ? ORDER BY created_at",
                (cid,),
            ).fetchall()
            accounts = [dict(a) for a in rows]

    if not accounts:
        return HTMLResponse("No accounts registered.")

    gmail_limiter = RateLimiter(rate=config.GMAIL_RATE_LIMIT)
    claude_limiter = RateLimiter(rate=config.CLAUDE_RATE_LIMIT)

    total_contacts = 0
    total_fetched = 0
    total_triaged = 0
    total_summarized = 0
    errors: list[str] = []

    for account in accounts:
        account_id = account["id"]
        email_addr = account["email_address"]

        token_path = Path(account["auth_token_path"])
        try:
            creds = get_credentials_for_account(token_path)
        except Exception as exc:
            log.warning("Auth failed for %s: %s", email_addr, exc)
            errors.append(f"{email_addr}: auth failed ({exc})")
            continue

        user_email = get_user_email(creds)

        # Sync contacts
        try:
            total_contacts += sync_contacts(
                creds, rate_limiter=gmail_limiter,
                customer_id=cid, user_id=uid,
            )
        except Exception as exc:
            log.warning("Contact sync failed for %s: %s", email_addr, exc)
            errors.append(f"{email_addr}: contact sync failed ({exc})")

        # Sync emails
        try:
            if account["initial_sync_done"]:
                result = incremental_sync(
                    account_id, creds, rate_limiter=gmail_limiter,
                    customer_id=cid, user_id=uid,
                )
                total_fetched += result.get("messages_fetched", 0)
            else:
                result = initial_sync(
                    account_id, creds, rate_limiter=gmail_limiter,
                    customer_id=cid, user_id=uid,
                )
                total_fetched += result.get("messages_fetched", 0)
        except Exception as exc:
            log.warning("Email sync failed for %s: %s", email_addr, exc)
            errors.append(f"{email_addr}: email sync failed ({exc})")

        # Process conversations
        try:
            triaged, summarized, _topics = process_conversations(
                account_id, creds, user_email,
                rate_limiter=gmail_limiter,
                claude_limiter=claude_limiter,
            )
            total_triaged += triaged
            total_summarized += summarized
        except Exception as exc:
            log.warning("Processing failed for %s: %s", email_addr, exc)
            errors.append(f"{email_addr}: processing failed ({exc})")

    parts = [
        f"Synced {len(accounts)} account(s):",
        f"{total_contacts} contacts,",
        f"{total_fetched} emails fetched,",
        f"{total_triaged} triaged,",
        f"{total_summarized} summarized.",
    ]
    summary = " ".join(parts)

    if errors:
        error_html = "<br>".join(f"Error: {e}" for e in errors)
        return HTMLResponse(f"<strong>{summary}</strong><br>{error_html}")

    return HTMLResponse(f"<strong>{summary}</strong>")
