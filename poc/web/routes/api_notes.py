"""Notes JSON API (Legacy UI Migration PRD, Phase 3).

Replaces the legacy HTMX notes routes over the web-independent helpers
in poc/notes.py. Deliberate improvements over legacy, recorded in the
PRD: attachment orphans are adopted via attachment_ids on create/update
(legacy never called link_attachment_to_note); deleting a note removes
its attachment files (legacy leaked them); the attachment tenant check
compares the exact customer path segment; FTS query errors return 400
instead of 500; invalid entity types return 400 instead of 500.

Route-order note: this router is included BEFORE api.py's router so the
literal /notes/* paths here are matched ahead of api.py's
GET /notes/{note_id} detail-panel route (which stays as-is).
"""

from __future__ import annotations

import logging
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse

from ... import config
from ...database import get_connection
from ...html_sanitize import sanitize_note_html
from ...notes import (
    add_note_entity,
    create_note,
    delete_note,
    get_attachment,
    get_note,
    get_note_entities,
    get_notes_for_entity,
    get_recent_notes,
    get_revision,
    get_revisions,
    link_attachment_to_note,
    remove_note_entity,
    search_mentionables,
    search_notes,
    toggle_pin,
    update_note,
)

router = APIRouter()
log = logging.getLogger(__name__)

_ENTITY_NAME_SQL = {
    "contact": "SELECT name FROM contacts WHERE id = ?",
    "company": "SELECT name FROM companies WHERE id = ?",
    "conversation": "SELECT title FROM conversations WHERE id = ?",
    "event": "SELECT title FROM events WHERE id = ?",
    "project": "SELECT name FROM projects WHERE id = ?",
}

_NOTES_SORT_MAP = {
    "name": "title",
    "created": "created_at",
    "updated": "updated_at",
    "author": "author_name",
    "entity": "entity_name",
}


def _err(message: str, status: int = 400, **extra) -> JSONResponse:
    return JSONResponse({"error": message, **extra}, status_code=status)


def _owned_note(request: Request, note_id: str) -> dict | None:
    note = get_note(note_id)
    if not note or note.get("customer_id") != request.state.customer_id:
        return None
    return note


def _uid(request: Request) -> str | None:
    return request.state.user["id"] if request.state.user else None


def _entity_name(conn, entity_type: str, entity_id: str) -> str | None:
    sql = _ENTITY_NAME_SQL.get(entity_type)
    if not sql:
        return None
    row = conn.execute(sql, (entity_id,)).fetchone()
    return row[0] if row else None


def _enrich(note: dict) -> dict:
    """Add author_name and per-entity names to a get_note() dict."""
    with get_connection() as conn:
        if note.get("created_by") and "author_name" not in note:
            row = conn.execute(
                "SELECT name FROM users WHERE id = ?", (note["created_by"],)
            ).fetchone()
            note["author_name"] = row["name"] if row else None
        for ent in note.get("entities", []):
            ent["entity_name"] = _entity_name(
                conn, ent["entity_type"], ent["entity_id"]
            )
    return note


def _adopt_attachments(request: Request, note_id: str, attachment_ids) -> None:
    """Link uploaded (orphan) attachments to the note, tenant-checked."""
    if not attachment_ids:
        return
    for aid in attachment_ids:
        att = get_attachment(aid)
        if not att:
            continue
        if not _attachment_owned(att, request.state.customer_id):
            continue
        link_attachment_to_note(aid, note_id)


def _attachment_owned(att: dict, customer_id: str) -> bool:
    """Exact path-segment tenant check (legacy used a substring test)."""
    try:
        rel = Path(att["storage_path"]).relative_to(config.UPLOAD_DIR)
        return rel.parts[0] == customer_id
    except ValueError:
        return False


def _sort_notes(notes: list[dict], sort: str) -> list[dict]:
    desc = sort.startswith("-")
    key = _NOTES_SORT_MAP.get(sort.lstrip("-"), "updated_at")
    return sorted(notes, key=lambda n: (n.get(key) or ""), reverse=desc)


# ---------------------------------------------------------------------------
# Literal paths — MUST be registered before any /notes/{note_id} pattern
# ---------------------------------------------------------------------------

@router.get("/notes/mentions")
def mentions_api(request: Request, q: str = "", type: str = "user"):
    return search_mentionables(
        q, type, customer_id=request.state.customer_id,
    )


@router.get("/notes/search")
def notes_search_api(request: Request, q: str = "", sort: str = "-updated"):
    cid = request.state.customer_id
    query = q.strip()
    if query:
        try:
            results = search_notes(query, customer_id=cid)
        except sqlite3.OperationalError:
            return _err("Invalid search query", 400)
    else:
        results = get_recent_notes(customer_id=cid)

    with get_connection() as conn:
        for n in results:
            if n.get("entity_type") and n.get("entity_id"):
                n["entity_name"] = _entity_name(
                    conn, n["entity_type"], n["entity_id"]
                )
    return {"q": q, "sort": sort, "results": _sort_notes(results, sort)}


@router.post("/notes/upload")
async def notes_upload_api(request: Request, file: UploadFile):
    from ...notes import create_attachment

    cid = request.state.customer_id
    mime = file.content_type or "application/octet-stream"
    if mime not in config.ALLOWED_UPLOAD_TYPES:
        return _err(f"File type {mime} not allowed")

    data = await file.read()
    if len(data) > config.MAX_UPLOAD_SIZE_MB * 1024 * 1024:
        return _err(f"File exceeds {config.MAX_UPLOAD_SIZE_MB} MB limit")

    ext = Path(file.filename or "").suffix or ".bin"
    safe_name = f"{uuid.uuid4()}{ext}"
    now = datetime.now(timezone.utc)
    dest_dir = Path(config.UPLOAD_DIR) / cid / f"{now.year:04d}" / f"{now.month:02d}"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / safe_name
    dest.write_bytes(data)

    att = create_attachment(
        filename=safe_name,
        original_name=file.filename or safe_name,
        mime_type=mime,
        size_bytes=len(data),
        storage_path=str(dest),
        uploaded_by=_uid(request),
    )
    return {
        "id": att["id"],
        "url": f"/notes/files/{att['id']}/{safe_name}",
        "original_name": att["original_name"],
    }


@router.get("/notes/files/{attachment_id}/{filename}")
def notes_file_api(request: Request, attachment_id: str, filename: str):
    att = get_attachment(attachment_id)
    if not att:
        return _err("Not found", 404)
    if not _attachment_owned(att, request.state.customer_id):
        return _err("Not found", 404)
    path = Path(att["storage_path"])
    if not path.exists():
        return _err("File missing", 404)
    return FileResponse(
        path, media_type=att["mime_type"], filename=att["original_name"],
    )


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

@router.get("/notes")
def notes_list_api(request: Request, entity_type: str = "", entity_id: str = ""):
    if not entity_type or not entity_id:
        return _err("entity_type and entity_id are required")
    notes = get_notes_for_entity(
        entity_type, entity_id, customer_id=request.state.customer_id,
    )
    return {"notes": notes}


@router.post("/notes")
async def notes_create_api(request: Request):
    body = await request.json()
    entity_type = body.get("entity_type")
    entity_id = body.get("entity_id")
    if not entity_type or not entity_id:
        return _err("entity_type and entity_id are required")

    title = (body.get("title") or "").strip() or None
    content_json = body.get("content_json") or None
    content_html = sanitize_note_html(body.get("content_html") or None)

    try:
        note = create_note(
            request.state.customer_id, entity_type, entity_id,
            title=title, content_json=content_json, content_html=content_html,
            created_by=_uid(request),
        )
    except ValueError as exc:
        return _err(str(exc))

    _adopt_attachments(request, note["id"], body.get("attachment_ids"))
    return JSONResponse(_enrich(get_note(note["id"])), status_code=201)


@router.get("/notes/{note_id}/full")
def note_full_api(request: Request, note_id: str):
    note = _owned_note(request, note_id)
    if not note:
        return _err("Not found", 404)
    return _enrich(note)


@router.put("/notes/{note_id}")
async def notes_update_api(request: Request, note_id: str):
    if not _owned_note(request, note_id):
        return _err("Not found", 404)
    body = await request.json()
    title = (body.get("title") or "").strip() or None
    update_note(
        note_id,
        title=title,
        content_json=body.get("content_json") or None,
        content_html=sanitize_note_html(body.get("content_html") or None),
        updated_by=_uid(request),
    )
    _adopt_attachments(request, note_id, body.get("attachment_ids"))
    return _enrich(get_note(note_id))


@router.delete("/notes/{note_id}")
def notes_delete_api(request: Request, note_id: str):
    if not _owned_note(request, note_id):
        return _err("Not found", 404)
    # Remove attachment files before the CASCADE deletes their rows
    # (legacy leaked the files)
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT storage_path FROM note_attachments WHERE note_id = ?",
            (note_id,),
        ).fetchall()
    for r in rows:
        try:
            Path(r["storage_path"]).unlink(missing_ok=True)
        except OSError as exc:
            log.warning("Could not delete attachment file %s: %s",
                        r["storage_path"], exc)
    delete_note(note_id)
    return {"ok": True}


# ---------------------------------------------------------------------------
# Pin, revisions, entity links
# ---------------------------------------------------------------------------

@router.post("/notes/{note_id}/pin")
async def notes_pin_api(request: Request, note_id: str):
    if not _owned_note(request, note_id):
        return _err("Not found", 404)
    body = await request.json() if await request.body() else {}
    entity_type = body.get("entity_type") or None
    entity_id = body.get("entity_id") or None
    note = toggle_pin(note_id, entity_type, entity_id)
    if not note:
        return _err("Not found", 404)
    # Reflect the toggled link's state, not the first link's
    is_pinned = note.get("is_pinned")
    if entity_type and entity_id:
        for ent in note.get("entities", []):
            if ent["entity_type"] == entity_type and ent["entity_id"] == entity_id:
                is_pinned = ent["is_pinned"]
    return {"note": _enrich(note), "is_pinned": bool(is_pinned)}


@router.get("/notes/{note_id}/revisions")
def notes_revisions_api(request: Request, note_id: str):
    note = _owned_note(request, note_id)
    if not note:
        return _err("Not found", 404)
    revisions = get_revisions(note_id)
    # Trim content bodies from the list — each is a full snapshot;
    # the single-revision endpoint serves the content
    trimmed = [
        {k: v for k, v in r.items() if k not in ("content_json", "content_html")}
        for r in revisions
    ]
    return {
        "revisions": trimmed,
        "current_revision_id": note.get("current_revision_id"),
    }


@router.get("/notes/{note_id}/revisions/{revision_id}")
def notes_revision_api(request: Request, note_id: str, revision_id: str):
    if not _owned_note(request, note_id):
        return _err("Not found", 404)
    rev = get_revision(revision_id)
    if not rev or rev["note_id"] != note_id:
        return _err("Not found", 404)
    return rev


@router.post("/notes/{note_id}/entities")
async def notes_entity_add_api(request: Request, note_id: str):
    if not _owned_note(request, note_id):
        return _err("Not found", 404)
    body = await request.json()
    entity_type = body.get("entity_type")
    entity_id = body.get("entity_id")
    if not entity_type or not entity_id:
        return _err("entity_type and entity_id are required")
    try:
        created = add_note_entity(note_id, entity_type, entity_id)
    except ValueError as exc:
        return _err(str(exc))
    return {"created": created, "entities": get_note_entities(note_id)}


@router.delete("/notes/{note_id}/entities/{entity_type}/{entity_id}")
def notes_entity_remove_api(
    request: Request, note_id: str, entity_type: str, entity_id: str,
):
    if not _owned_note(request, note_id):
        return _err("Not found", 404)
    try:
        remove_note_entity(note_id, entity_type, entity_id)
    except ValueError as exc:
        return _err(str(exc), 409)
    return {"entities": get_note_entities(note_id)}
