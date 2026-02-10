"""Dashboard route — overview counts and recent conversations."""

from __future__ import annotations

from fastapi import APIRouter, Request

from ...database import get_connection

router = APIRouter()


@router.get("/")
def dashboard(request: Request):
    templates = request.app.state.templates

    with get_connection() as conn:
        counts = {
            "conversations_total": conn.execute(
                "SELECT COUNT(*) AS c FROM conversations"
            ).fetchone()["c"],
            "conversations_open": conn.execute(
                "SELECT COUNT(*) AS c FROM conversations WHERE triage_result IS NULL AND dismissed = 0"
            ).fetchone()["c"],
            "conversations_closed": conn.execute(
                "SELECT COUNT(*) AS c FROM conversations WHERE dismissed = 1"
            ).fetchone()["c"],
            "contacts": conn.execute(
                "SELECT COUNT(*) AS c FROM contacts"
            ).fetchone()["c"],
            "companies": conn.execute(
                "SELECT COUNT(*) AS c FROM companies WHERE status = 'active'"
            ).fetchone()["c"],
            "projects": conn.execute(
                "SELECT COUNT(*) AS c FROM projects WHERE status = 'active'"
            ).fetchone()["c"],
            "topics": conn.execute(
                "SELECT COUNT(*) AS c FROM topics"
            ).fetchone()["c"],
            "events": conn.execute(
                "SELECT COUNT(*) AS c FROM events"
            ).fetchone()["c"],
        }

        recent = conn.execute(
            "SELECT * FROM conversations ORDER BY last_activity_at DESC LIMIT 10"
        ).fetchall()
        recent_conversations = [dict(r) for r in recent]

        top_companies = [dict(r) for r in conn.execute(
            """SELECT c.id, c.name, c.domain, es.score_value AS score
               FROM entity_scores es
               JOIN companies c ON c.id = es.entity_id
               WHERE es.entity_type = 'company'
                 AND es.score_type = 'relationship_strength'
               ORDER BY es.score_value DESC
               LIMIT 5""",
        ).fetchall()]

        top_contacts = [dict(r) for r in conn.execute(
            """SELECT ct.id, ct.name, ci.value AS email,
                      co.name AS company_name, es.score_value AS score
               FROM entity_scores es
               JOIN contacts ct ON ct.id = es.entity_id
               LEFT JOIN contact_identifiers ci
                 ON ci.contact_id = ct.id AND ci.type = 'email'
               LEFT JOIN companies co ON co.id = ct.company_id
               WHERE es.entity_type = 'contact'
                 AND es.score_type = 'relationship_strength'
               ORDER BY es.score_value DESC
               LIMIT 5""",
        ).fetchall()]

        counts["scored_companies"] = conn.execute(
            """SELECT COUNT(*) AS c FROM entity_scores
               WHERE entity_type = 'company' AND score_type = 'relationship_strength'"""
        ).fetchone()["c"]
        counts["scored_contacts"] = conn.execute(
            """SELECT COUNT(*) AS c FROM entity_scores
               WHERE entity_type = 'contact' AND score_type = 'relationship_strength'"""
        ).fetchone()["c"]

    return templates.TemplateResponse(request, "dashboard.html", {
        "active_nav": "dashboard",
        "counts": counts,
        "recent_conversations": recent_conversations,
        "top_companies": top_companies,
        "top_contacts": top_contacts,
    })
