"""Relationship routes — list, search, infer, manual CRUD, type admin."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from ...database import get_connection
from ...relationship_inference import load_relationships
from ...relationship_types import (
    create_relationship_type,
    delete_relationship_type,
    list_relationship_types,
)

router = APIRouter()


def _entity_name_lookup(conn, entity_ids: set[str]) -> dict[str, str]:
    """Look up display names for contact and company entity IDs."""
    if not entity_ids:
        return {}

    names: dict[str, str] = {}
    placeholders = ",".join("?" for _ in entity_ids)
    id_list = list(entity_ids)

    # Contacts
    rows = conn.execute(
        f"""SELECT c.id, c.name, ci.value AS email
            FROM contacts c
            LEFT JOIN contact_identifiers ci ON ci.contact_id = c.id AND ci.type = 'email'
            WHERE c.id IN ({placeholders})""",
        id_list,
    ).fetchall()
    for row in rows:
        names[row["id"]] = row["name"] or row["email"] or row["id"][:8]

    # Companies
    rows = conn.execute(
        f"SELECT id, name FROM companies WHERE id IN ({placeholders})",
        id_list,
    ).fetchall()
    for row in rows:
        names[row["id"]] = row["name"]

    return names


def _get_relationships(
    *,
    contact_id: str = "",
    min_strength: float = 0.0,
    type_id: str = "",
    source: str = "",
):
    rels = load_relationships(
        contact_id=contact_id or None,
        min_strength=min_strength,
        relationship_type_id=type_id or None,
        source=source or None,
    )

    # Build entity name lookup
    eids = set()
    for r in rels:
        eids.add(r.from_entity_id)
        eids.add(r.to_entity_id)

    with get_connection() as conn:
        entity_names = _entity_name_lookup(conn, eids)

        # Get type info
        type_map: dict[str, dict] = {}
        for row in conn.execute("SELECT * FROM relationship_types").fetchall():
            type_map[row["id"]] = dict(row)

    results = []
    for r in rels:
        rt = type_map.get(r.relationship_type_id, {})
        results.append({
            "id": None,  # populated below
            "from_id": r.from_entity_id,
            "from_name": entity_names.get(r.from_entity_id, r.from_entity_id[:8]),
            "from_entity_type": r.from_entity_type,
            "to_id": r.to_entity_id,
            "to_name": entity_names.get(r.to_entity_id, r.to_entity_id[:8]),
            "to_entity_type": r.to_entity_type,
            "type_name": rt.get("name", ""),
            "forward_label": rt.get("forward_label", ""),
            "reverse_label": rt.get("reverse_label", ""),
            "source": r.source,
            "strength": r.strength,
            "shared_conversations": r.shared_conversations,
            "shared_messages": r.shared_messages,
        })

    # Fetch actual IDs for delete support
    with get_connection() as conn:
        for item in results:
            row = conn.execute(
                "SELECT id FROM relationships WHERE from_entity_id = ? AND to_entity_id = ? AND relationship_type_id = ?",
                (item["from_id"], item["to_id"],
                 next((tid for tid, t in type_map.items() if t.get("name") == item["type_name"]), "")),
            ).fetchone()
            if row:
                item["id"] = row["id"]

    return results


@router.get("", response_class=HTMLResponse)
def relationship_list(
    request: Request,
    contact_id: str = "",
    min_strength: float = 0.0,
    type_id: str = "",
    source: str = "",
):
    templates = request.app.state.templates
    rels = _get_relationships(
        contact_id=contact_id,
        min_strength=min_strength,
        type_id=type_id,
        source=source,
    )
    rel_types = list_relationship_types()

    return templates.TemplateResponse(request, "relationships/list.html", {
        "active_nav": "relationships",
        "relationships": rels,
        "contact_id": contact_id,
        "min_strength": min_strength,
        "type_id": type_id,
        "source": source,
        "relationship_types": rel_types,
    })


@router.get("/search", response_class=HTMLResponse)
def relationship_search(
    request: Request,
    contact_id: str = "",
    min_strength: float = 0.0,
    type_id: str = "",
    source: str = "",
):
    templates = request.app.state.templates
    rels = _get_relationships(
        contact_id=contact_id,
        min_strength=min_strength,
        type_id=type_id,
        source=source,
    )

    return templates.TemplateResponse(request, "relationships/_rows.html", {
        "relationships": rels,
    })


@router.post("/infer", response_class=HTMLResponse)
def relationship_infer(request: Request):
    from ...relationship_inference import infer_relationships
    count = infer_relationships()
    return HTMLResponse(f"<p><strong>{count}</strong> relationship(s) inferred.</p>")


@router.post("", response_class=HTMLResponse)
def relationship_create(
    request: Request,
    relationship_type_id: str = Form(...),
    from_entity_id: str = Form(...),
    to_entity_id: str = Form(...),
):
    """Create a manual relationship."""
    now = datetime.now(timezone.utc).isoformat()

    with get_connection() as conn:
        # Look up type to get entity types
        rt = conn.execute(
            "SELECT * FROM relationship_types WHERE id = ?",
            (relationship_type_id,),
        ).fetchone()
        if not rt:
            return HTMLResponse("Relationship type not found", status_code=400)

        conn.execute(
            """INSERT OR IGNORE INTO relationships
               (id, relationship_type_id, from_entity_type, from_entity_id,
                to_entity_type, to_entity_id, source, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, 'manual', ?, ?)""",
            (
                str(uuid.uuid4()),
                relationship_type_id,
                rt["from_entity_type"],
                from_entity_id,
                rt["to_entity_type"],
                to_entity_id,
                now,
                now,
            ),
        )

    if request.headers.get("HX-Request") == "true":
        return HTMLResponse("", headers={"HX-Redirect": "/relationships"})
    return RedirectResponse("/relationships", status_code=303)


@router.delete("/{relationship_id}", response_class=HTMLResponse)
def relationship_delete(request: Request, relationship_id: str):
    """Delete a manual relationship."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT source FROM relationships WHERE id = ?", (relationship_id,)
        ).fetchone()
        if not row:
            return HTMLResponse("Not found", status_code=404)
        if row["source"] != "manual":
            return HTMLResponse("Cannot delete inferred relationships", status_code=400)
        conn.execute("DELETE FROM relationships WHERE id = ?", (relationship_id,))
    return HTMLResponse("")


# ---------------------------------------------------------------------------
# Relationship Types admin
# ---------------------------------------------------------------------------

@router.get("/types", response_class=HTMLResponse)
def relationship_type_list(request: Request):
    templates = request.app.state.templates
    types = list_relationship_types()

    return templates.TemplateResponse(request, "relationships/types.html", {
        "active_nav": "relationships",
        "relationship_types": types,
    })


@router.post("/types", response_class=HTMLResponse)
def relationship_type_create(
    request: Request,
    name: str = Form(...),
    from_entity_type: str = Form("contact"),
    to_entity_type: str = Form("contact"),
    forward_label: str = Form(""),
    reverse_label: str = Form(""),
    description: str = Form(""),
):
    try:
        create_relationship_type(
            name,
            from_entity_type=from_entity_type,
            to_entity_type=to_entity_type,
            forward_label=forward_label,
            reverse_label=reverse_label,
            description=description,
        )
    except ValueError:
        pass

    if request.headers.get("HX-Request") == "true":
        return HTMLResponse("", headers={"HX-Redirect": "/relationships/types"})
    return RedirectResponse("/relationships/types", status_code=303)


@router.delete("/types/{type_id}", response_class=HTMLResponse)
def relationship_type_delete(request: Request, type_id: str):
    try:
        delete_relationship_type(type_id)
    except ValueError as exc:
        return HTMLResponse(str(exc), status_code=400)
    return HTMLResponse("")
