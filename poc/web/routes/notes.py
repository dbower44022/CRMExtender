"""Note routes — CRUD, pins, revisions, file upload, mentions, search."""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, File, Form, Query, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse

from ... import config
from ...database import get_connection
from ...notes import (
    add_note_entity,
    create_attachment,
    create_note,
    delete_note,
    get_attachment,
    get_note,
    get_note_entities,
    get_notes_for_entity,
    get_recent_notes,
    get_revisions,
    get_revision,
    remove_note_entity,
    search_mentionables,
    search_notes,
    toggle_pin,
    update_note,
)

router = APIRouter()


def _is_htmx(request: Request) -> bool:
    return request.headers.get("HX-Request") == "true"


def _sanitize_html(html: str | None) -> str | None:
    """Sanitize HTML content to prevent XSS."""
    if not html:
        return html
    try:
        import bleach
        allowed_tags = [
            "p", "br", "strong", "em", "u", "s", "code", "pre", "blockquote",
            "h1", "h2", "h3", "h4", "h5", "h6",
            "ul", "ol", "li", "a", "img",
            "table", "thead", "tbody", "tr", "th", "td",
            "span", "div", "hr", "sub", "sup", "mark",
        ]
        allowed_attrs = {
            "a": ["href", "target", "rel"],
            "img": ["src", "alt", "title", "width", "height"],
            "span": ["class", "data-type", "data-id", "data-mention-type"],
            "td": ["colspan", "rowspan"],
            "th": ["colspan", "rowspan"],
        }
        return bleach.clean(
            html, tags=allowed_tags, attributes=allowed_attrs, strip=True,
        )
    except ImportError:
        # bleach not installed — pass through (logged at startup)
        return html


# ---------------------------------------------------------------------------
# Entity name resolution (for browser display)
# ---------------------------------------------------------------------------

_ENTITY_NAME_SQL = {
    "contact": "SELECT name FROM contacts WHERE id = ?",
    "company": "SELECT name FROM companies WHERE id = ?",
    "conversation": "SELECT title AS name FROM conversations WHERE id = ?",
    "event": "SELECT title AS name FROM events WHERE id = ?",
    "project": "SELECT name FROM projects WHERE id = ?",
}


def _entity_name(conn, entity_type: str, entity_id: str) -> str:
    """Look up a display name for an entity."""
    sql = _ENTITY_NAME_SQL.get(entity_type)
    if not sql:
        return entity_id
    row = conn.execute(sql, (entity_id,)).fetchone()
    return row["name"] if row and row["name"] else entity_id


def _resolve_entity_names(conn, notes: list[dict]) -> list[dict]:
    """Add entity_name and author_name to each note dict (for list display)."""
    for note in notes:
        et = note.get("entity_type") or ""
        eid = note.get("entity_id") or ""
        note["entity_name"] = _entity_name(conn, et, eid) if et and eid else ""
        # Resolve author name
        if not note.get("author_name") and note.get("created_by"):
            u = conn.execute(
                "SELECT name FROM users WHERE id = ?", (note["created_by"],)
            ).fetchone()
            note["author_name"] = u["name"] if u else None
    return notes


def _resolve_entity_names_for_note(conn, note: dict) -> dict:
    """Add entity_name to each entity in note['entities'] (for viewer)."""
    for entity in note.get("entities", []):
        entity["entity_name"] = _entity_name(
            conn, entity["entity_type"], entity["entity_id"],
        )
    return note


def _entity_url(entity_type: str, entity_id: str) -> str:
    """Build the detail page URL for an entity."""
    if entity_type == "company":
        return f"/companies/{entity_id}"
    return f"/{entity_type}s/{entity_id}"


# ---------------------------------------------------------------------------
# List / Create
# ---------------------------------------------------------------------------

@router.get("", response_class=HTMLResponse)
def notes_list(request: Request, entity_type: str = "", entity_id: str = ""):
    templates = request.app.state.templates
    cid = request.state.customer_id

    notes = get_notes_for_entity(entity_type, entity_id, customer_id=cid) if entity_type and entity_id else []

    return templates.TemplateResponse(request, "notes/_notes.html", {
        "notes": notes,
        "entity_type": entity_type,
        "entity_id": entity_id,
    })


@router.post("", response_class=HTMLResponse)
async def notes_create(request: Request):
    templates = request.app.state.templates
    form = await request.form()
    user = request.state.user
    cid = request.state.customer_id

    entity_type = form.get("entity_type", "")
    entity_id = form.get("entity_id", "")
    title = form.get("title", "").strip() or None
    content_json = form.get("content_json", "").strip() or None
    content_html = form.get("content_html", "").strip() or None
    content_html = _sanitize_html(content_html)

    if not entity_type or not entity_id:
        return HTMLResponse("Missing entity_type or entity_id", status_code=400)

    create_note(
        cid, entity_type, entity_id,
        title=title, content_json=content_json, content_html=content_html,
        created_by=user["id"],
    )

    notes = get_notes_for_entity(entity_type, entity_id, customer_id=cid)
    return templates.TemplateResponse(request, "notes/_notes.html", {
        "notes": notes,
        "entity_type": entity_type,
        "entity_id": entity_id,
    })


# ---------------------------------------------------------------------------
# Browser viewer
# ---------------------------------------------------------------------------

@router.get("/{note_id}/view", response_class=HTMLResponse)
def notes_view(request: Request, note_id: str):
    """Return the viewer partial for the browser right pane."""
    templates = request.app.state.templates
    cid = request.state.customer_id

    note = get_note(note_id)
    if not note or note.get("customer_id") != cid:
        return HTMLResponse("Note not found", status_code=404)

    with get_connection() as conn:
        u = conn.execute(
            "SELECT name FROM users WHERE id = ?", (note["created_by"],)
        ).fetchone()
        note["author_name"] = u["name"] if u else None
        _resolve_entity_names_for_note(conn, note)

    return templates.TemplateResponse(request, "notes/_viewer.html", {
        "note": note,
    })


# ---------------------------------------------------------------------------
# Edit / Update
# ---------------------------------------------------------------------------

@router.get("/{note_id}/edit", response_class=HTMLResponse)
def notes_edit(
    request: Request, note_id: str,
    entity_type: str = "", entity_id: str = "",
    source: str = "",
):
    templates = request.app.state.templates
    cid = request.state.customer_id

    note = get_note(note_id)
    if not note or note.get("customer_id") != cid:
        return HTMLResponse("Note not found", status_code=404)

    # Use query params if provided, else fall back to first entity
    et = entity_type or note.get("entity_type") or ""
    eid = entity_id or note.get("entity_id") or ""

    if source == "browser":
        return templates.TemplateResponse(request, "notes/_viewer_editor.html", {
            "note": note,
        })

    return templates.TemplateResponse(request, "notes/_note_editor.html", {
        "note": note,
        "entity_type": et,
        "entity_id": eid,
    })


@router.put("/{note_id}", response_class=HTMLResponse)
async def notes_update(request: Request, note_id: str, source: str = ""):
    templates = request.app.state.templates
    form = await request.form()
    user = request.state.user
    cid = request.state.customer_id

    note = get_note(note_id)
    if not note or note.get("customer_id") != cid:
        return HTMLResponse("Note not found", status_code=404)

    title = form.get("title", "").strip() or None
    content_json = form.get("content_json", "").strip() or None
    content_html = form.get("content_html", "").strip() or None
    content_html = _sanitize_html(content_html)

    # Entity context from hidden fields (for cancel/redirect back)
    et = form.get("entity_type", "") or note.get("entity_type") or ""
    eid = form.get("entity_id", "") or note.get("entity_id") or ""

    update_note(
        note_id,
        title=title, content_json=content_json, content_html=content_html,
        updated_by=user["id"],
    )

    updated = get_note(note_id)
    if updated:
        with get_connection() as conn:
            u = conn.execute("SELECT name FROM users WHERE id = ?", (updated["created_by"],)).fetchone()
            updated["author_name"] = u["name"] if u else None

    if source == "browser":
        if updated:
            with get_connection() as conn:
                _resolve_entity_names_for_note(conn, updated)
        resp = templates.TemplateResponse(request, "notes/_viewer.html", {
            "note": updated,
        })
        resp.headers["HX-Trigger"] = "noteUpdated"
        return resp

    return templates.TemplateResponse(request, "notes/_note_card.html", {
        "note": updated,
        "entity_type": et,
        "entity_id": eid,
    })


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------

@router.delete("/{note_id}", response_class=HTMLResponse)
def notes_delete(request: Request, note_id: str, source: str = ""):
    cid = request.state.customer_id
    note = get_note(note_id)
    if not note or note.get("customer_id") != cid:
        return HTMLResponse("Note not found", status_code=404)

    delete_note(note_id)

    if source == "browser":
        resp = HTMLResponse(
            '<div class="notes-viewer-empty">Note deleted. Select another note.</div>'
        )
        resp.headers["HX-Trigger"] = "noteDeleted"
        return resp

    return HTMLResponse("")


# ---------------------------------------------------------------------------
# Pin toggle
# ---------------------------------------------------------------------------

@router.post("/{note_id}/pin", response_class=HTMLResponse)
def notes_pin(
    request: Request, note_id: str,
    entity_type: str = "", entity_id: str = "",
    source: str = "",
):
    templates = request.app.state.templates
    cid = request.state.customer_id

    note = get_note(note_id)
    if not note or note.get("customer_id") != cid:
        return HTMLResponse("Note not found", status_code=404)

    # Use query params if provided, else fall back to first entity
    et = entity_type or note.get("entity_type") or ""
    eid = entity_id or note.get("entity_id") or ""

    updated = toggle_pin(note_id, et or None, eid or None)
    if updated:
        with get_connection() as conn:
            u = conn.execute("SELECT name FROM users WHERE id = ?", (updated["created_by"],)).fetchone()
            updated["author_name"] = u["name"] if u else None
        # Override is_pinned with the value for this specific entity
        for e in updated.get("entities", []):
            if e["entity_type"] == et and e["entity_id"] == eid:
                updated["is_pinned"] = e["is_pinned"]
                break

    if source == "browser":
        if updated:
            with get_connection() as conn:
                _resolve_entity_names_for_note(conn, updated)
        resp = templates.TemplateResponse(request, "notes/_viewer.html", {
            "note": updated,
        })
        resp.headers["HX-Trigger"] = "notePinned"
        return resp

    return templates.TemplateResponse(request, "notes/_note_card.html", {
        "note": updated,
        "entity_type": et,
        "entity_id": eid,
    })


# ---------------------------------------------------------------------------
# Revisions
# ---------------------------------------------------------------------------

@router.get("/{note_id}/revisions", response_class=HTMLResponse)
def notes_revisions(request: Request, note_id: str):
    templates = request.app.state.templates
    cid = request.state.customer_id

    note = get_note(note_id)
    if not note or note.get("customer_id") != cid:
        return HTMLResponse("Note not found", status_code=404)

    revisions = get_revisions(note_id)
    return templates.TemplateResponse(request, "notes/_note_revisions.html", {
        "note": note,
        "revisions": revisions,
    })


@router.get("/{note_id}/revisions/{rev_id}", response_class=HTMLResponse)
def notes_revision_detail(request: Request, note_id: str, rev_id: str):
    cid = request.state.customer_id
    note = get_note(note_id)
    if not note or note.get("customer_id") != cid:
        return HTMLResponse("Note not found", status_code=404)

    rev = get_revision(rev_id)
    if not rev or rev["note_id"] != note_id:
        return HTMLResponse("Revision not found", status_code=404)

    return HTMLResponse(rev["content_html"] or "<em>No content</em>")


# ---------------------------------------------------------------------------
# File upload
# ---------------------------------------------------------------------------

@router.post("/upload", response_class=JSONResponse)
async def notes_upload(request: Request, file: UploadFile = File(...)):
    user = request.state.user
    cid = request.state.customer_id

    # Validate MIME type
    mime = file.content_type or "application/octet-stream"
    if mime not in config.ALLOWED_UPLOAD_TYPES:
        return JSONResponse({"error": f"File type {mime} not allowed"}, status_code=400)

    # Read and validate size
    data = await file.read()
    max_bytes = config.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if len(data) > max_bytes:
        return JSONResponse(
            {"error": f"File too large (max {config.MAX_UPLOAD_SIZE_MB} MB)"},
            status_code=400,
        )

    # Build storage path
    now = datetime.now(timezone.utc)
    ext = Path(file.filename or "file").suffix or ".bin"
    safe_name = f"{uuid.uuid4()}{ext}"
    rel_dir = Path(cid) / now.strftime("%Y") / now.strftime("%m")
    storage_dir = config.UPLOAD_DIR / rel_dir
    storage_dir.mkdir(parents=True, exist_ok=True)
    storage_path = storage_dir / safe_name

    # Write file
    storage_path.write_bytes(data)

    # Record in DB (orphan — note_id=NULL until note is saved)
    att = create_attachment(
        filename=safe_name,
        original_name=file.filename or "file",
        mime_type=mime,
        size_bytes=len(data),
        storage_path=str(storage_path),
        uploaded_by=user["id"],
    )

    return JSONResponse({
        "id": att["id"],
        "url": f"/notes/files/{att['id']}/{safe_name}",
        "original_name": att["original_name"],
    })


@router.get("/files/{attachment_id}/{filename}", response_class=FileResponse)
def notes_serve_file(request: Request, attachment_id: str, filename: str):
    cid = request.state.customer_id
    att = get_attachment(attachment_id)
    if not att:
        return HTMLResponse("File not found", status_code=404)

    # Tenant isolation — check storage path contains customer_id
    if cid not in att["storage_path"]:
        return HTMLResponse("File not found", status_code=404)

    path = Path(att["storage_path"])
    if not path.exists():
        return HTMLResponse("File not found", status_code=404)

    return FileResponse(path, media_type=att["mime_type"], filename=att["original_name"])


# ---------------------------------------------------------------------------
# Entity linking
# ---------------------------------------------------------------------------

@router.post("/{note_id}/entities", response_class=HTMLResponse)
async def notes_add_entity(request: Request, note_id: str):
    form = await request.form()
    cid = request.state.customer_id

    note = get_note(note_id)
    if not note or note.get("customer_id") != cid:
        return HTMLResponse("Note not found", status_code=404)

    et = form.get("entity_type", "")
    eid = form.get("entity_id", "")
    if not et or not eid:
        return HTMLResponse("Missing entity_type or entity_id", status_code=400)

    try:
        add_note_entity(note_id, et, eid)
    except ValueError as exc:
        return HTMLResponse(str(exc), status_code=400)

    return HTMLResponse("OK")


@router.delete("/{note_id}/entities/{entity_type}/{entity_id}", response_class=HTMLResponse)
def notes_remove_entity(
    request: Request, note_id: str, entity_type: str, entity_id: str,
):
    cid = request.state.customer_id

    note = get_note(note_id)
    if not note or note.get("customer_id") != cid:
        return HTMLResponse("Note not found", status_code=404)

    try:
        remove_note_entity(note_id, entity_type, entity_id)
    except ValueError as exc:
        return HTMLResponse(str(exc), status_code=400)

    return HTMLResponse("OK")


# ---------------------------------------------------------------------------
# Mentions autocomplete
# ---------------------------------------------------------------------------

@router.get("/mentions", response_class=JSONResponse)
def notes_mentions(request: Request, q: str = "", type: str = "user"):
    cid = request.state.customer_id
    results = search_mentionables(q, type, customer_id=cid)
    return JSONResponse(results)


# ---------------------------------------------------------------------------
# Global search
# ---------------------------------------------------------------------------

_NOTES_SORT_MAP = {
    "name": "title",
    "created": "created_at",
    "updated": "updated_at",
    "author": "author_name",
    "entity": "entity_name",
}


def _sort_notes(notes: list[dict], sort: str) -> list[dict]:
    """Sort notes list in-place using the sort map."""
    desc = sort.startswith("-")
    key = sort.lstrip("-")
    attr = _NOTES_SORT_MAP.get(key, "updated_at")
    return sorted(notes, key=lambda n: (n.get(attr) or "") or "", reverse=desc)


@router.get("/search", response_class=HTMLResponse)
def notes_search(request: Request, q: str = "", sort: str = "-updated"):
    templates = request.app.state.templates
    cid = request.state.customer_id

    if q.strip():
        results = search_notes(q, customer_id=cid)
    else:
        results = get_recent_notes(customer_id=cid)

    with get_connection() as conn:
        _resolve_entity_names(conn, results)

    results = _sort_notes(results, sort)

    return templates.TemplateResponse(request, "notes/search.html", {
        "active_nav": "notes",
        "q": q,
        "sort": sort,
        "results": results,
    })


@router.get("/search/list", response_class=HTMLResponse)
def notes_search_list(request: Request, q: str = "", sort: str = "-updated"):
    """Return the list-items partial for the browser left pane."""
    templates = request.app.state.templates
    cid = request.state.customer_id

    if q.strip():
        results = search_notes(q, customer_id=cid)
    else:
        results = get_recent_notes(customer_id=cid)

    with get_connection() as conn:
        _resolve_entity_names(conn, results)

    results = _sort_notes(results, sort)

    return templates.TemplateResponse(request, "notes/_search_list.html", {
        "results": results,
        "q": q,
        "sort": sort,
    })
