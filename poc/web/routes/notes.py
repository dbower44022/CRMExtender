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
    create_attachment,
    create_note,
    delete_note,
    get_attachment,
    get_note,
    get_notes_for_entity,
    get_recent_notes,
    get_revisions,
    get_revision,
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
# Edit / Update
# ---------------------------------------------------------------------------

@router.get("/{note_id}/edit", response_class=HTMLResponse)
def notes_edit(request: Request, note_id: str):
    templates = request.app.state.templates
    cid = request.state.customer_id

    note = get_note(note_id)
    if not note or note.get("customer_id") != cid:
        return HTMLResponse("Note not found", status_code=404)

    return templates.TemplateResponse(request, "notes/_note_editor.html", {
        "note": note,
        "entity_type": note["entity_type"],
        "entity_id": note["entity_id"],
    })


@router.put("/{note_id}", response_class=HTMLResponse)
async def notes_update(request: Request, note_id: str):
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

    return templates.TemplateResponse(request, "notes/_note_card.html", {
        "note": updated,
        "entity_type": note["entity_type"],
        "entity_id": note["entity_id"],
    })


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------

@router.delete("/{note_id}", response_class=HTMLResponse)
def notes_delete(request: Request, note_id: str):
    cid = request.state.customer_id
    note = get_note(note_id)
    if not note or note.get("customer_id") != cid:
        return HTMLResponse("Note not found", status_code=404)

    delete_note(note_id)
    return HTMLResponse("")


# ---------------------------------------------------------------------------
# Pin toggle
# ---------------------------------------------------------------------------

@router.post("/{note_id}/pin", response_class=HTMLResponse)
def notes_pin(request: Request, note_id: str):
    templates = request.app.state.templates
    cid = request.state.customer_id

    note = get_note(note_id)
    if not note or note.get("customer_id") != cid:
        return HTMLResponse("Note not found", status_code=404)

    updated = toggle_pin(note_id)
    if updated:
        with get_connection() as conn:
            u = conn.execute("SELECT name FROM users WHERE id = ?", (updated["created_by"],)).fetchone()
            updated["author_name"] = u["name"] if u else None

    return templates.TemplateResponse(request, "notes/_note_card.html", {
        "note": updated,
        "entity_type": note["entity_type"],
        "entity_id": note["entity_id"],
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

@router.get("/search", response_class=HTMLResponse)
def notes_search(request: Request, q: str = ""):
    templates = request.app.state.templates
    cid = request.state.customer_id

    if q.strip():
        results = search_notes(q, customer_id=cid)
    else:
        results = get_recent_notes(customer_id=cid)

    return templates.TemplateResponse(request, "notes/search.html", {
        "active_nav": "notes",
        "q": q,
        "results": results,
    })
