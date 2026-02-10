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

    return templates.TemplateResponse(request, "dashboard.html", {
        "active_nav": "dashboard",
        "counts": counts,
        "recent_conversations": recent_conversations,
    })
