"""Dashboard route — overview counts and recent conversations."""

from __future__ import annotations

import logging

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
    from ...sync_service import run_full_sync

    user = request.state.user
    result = run_full_sync(
        customer_id=request.state.customer_id, user_id=user["id"],
    )

    if result["accounts"] == 0:
        return HTMLResponse("No accounts registered.")

    parts = [
        f"Synced {result['accounts']} account(s):",
        f"{result['contacts']} contacts,",
        f"{result['emails_fetched']} emails fetched,",
        f"{result['triaged']} triaged,",
        f"{result['summarized']} summarized.",
    ]
    if result["enriched"]:
        parts.append(f"{result['enriched']} companies enriched.")
    summary = " ".join(parts)

    if result["errors"]:
        error_html = "<br>".join(f"Error: {e}" for e in result["errors"])
        return HTMLResponse(f"<strong>{summary}</strong><br>{error_html}")

    return HTMLResponse(f"<strong>{summary}</strong>")
