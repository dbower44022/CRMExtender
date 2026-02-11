"""Project and topic routes — hierarchy, CRUD, auto-assign."""

from __future__ import annotations

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from ...database import get_connection
from ...hierarchy import (
    create_project,
    create_topic,
    delete_project,
    delete_topic,
    get_hierarchy_stats,
    get_project,
    get_topic_stats,
)

router = APIRouter()


@router.get("", response_class=HTMLResponse)
def project_list(request: Request):
    templates = request.app.state.templates
    cid = request.state.customer_id
    stats = get_hierarchy_stats(customer_id=cid)

    # Attach topic stats to each project
    for proj in stats:
        proj["topics"] = get_topic_stats(proj["id"])

    return templates.TemplateResponse(request, "projects/list.html", {
        "active_nav": "projects",
        "projects": stats,
    })


@router.post("", response_class=HTMLResponse)
def project_create(
    request: Request,
    name: str = Form(...),
    description: str = Form(""),
):
    user = request.state.user
    cid = request.state.customer_id
    try:
        create_project(
            name=name, description=description,
            customer_id=cid, created_by=user["id"],
        )
    except ValueError:
        pass
    return RedirectResponse("/projects", status_code=303)


@router.delete("/{project_id}", response_class=HTMLResponse)
def project_delete_route(request: Request, project_id: str):
    delete_project(project_id)
    return HTMLResponse("")


@router.get("/{project_id}", response_class=HTMLResponse)
def project_detail(request: Request, project_id: str):
    templates = request.app.state.templates

    project = get_project(project_id)
    if not project:
        return HTMLResponse("Project not found", status_code=404)

    topic_stats = get_topic_stats(project_id)

    return templates.TemplateResponse(request, "projects/detail.html", {
        "active_nav": "projects",
        "project": project,
        "topics": topic_stats,
    })


@router.post("/{project_id}/topics", response_class=HTMLResponse)
def topic_create(
    request: Request,
    project_id: str,
    name: str = Form(...),
    description: str = Form(""),
):
    user = request.state.user
    try:
        create_topic(
            project_id=project_id, name=name, description=description,
            created_by=user["id"],
        )
    except ValueError:
        pass
    return RedirectResponse(f"/projects/{project_id}", status_code=303)


@router.delete("/topics/{topic_id}", response_class=HTMLResponse)
def topic_delete_route(request: Request, topic_id: str):
    delete_topic(topic_id)
    return HTMLResponse("")


@router.post("/{project_id}/auto-assign", response_class=HTMLResponse)
def auto_assign_preview(request: Request, project_id: str):
    """Dry-run auto-assign and return preview partial."""
    from ...auto_assign import find_matching_topics

    templates = request.app.state.templates

    try:
        report = find_matching_topics(project_id)
    except ValueError as exc:
        return HTMLResponse(f"<p>{exc}</p>")

    return templates.TemplateResponse(request, "projects/_assign_preview.html", {
        "report": report,
        "project_id": project_id,
    })


@router.post("/{project_id}/auto-assign/apply", response_class=HTMLResponse)
def auto_assign_apply(request: Request, project_id: str):
    from ...auto_assign import apply_assignments, find_matching_topics

    try:
        report = find_matching_topics(project_id)
        count = apply_assignments(report.assignments)
    except ValueError:
        count = 0

    return HTMLResponse(f"<p><strong>{count}</strong> conversation(s) assigned.</p>")
