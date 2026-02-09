"""Relationship routes — list, search, infer."""

from __future__ import annotations

import json

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from ...database import get_connection
from ...relationship_inference import load_relationships

router = APIRouter()


def _get_relationships(*, contact_id: str = "", min_strength: float = 0.0):
    rels = load_relationships(
        contact_id=contact_id or None,
        min_strength=min_strength,
    )

    # Build contact name lookup
    cids = set()
    for r in rels:
        cids.add(r.from_contact_id)
        cids.add(r.to_contact_id)

    contact_names: dict[str, str] = {}
    if cids:
        placeholders = ",".join("?" for _ in cids)
        with get_connection() as conn:
            rows = conn.execute(
                f"""SELECT c.id, c.name, ci.value AS email
                    FROM contacts c
                    LEFT JOIN contact_identifiers ci ON ci.contact_id = c.id AND ci.type = 'email'
                    WHERE c.id IN ({placeholders})""",
                list(cids),
            ).fetchall()
        for row in rows:
            contact_names[row["id"]] = row["name"] or row["email"] or row["id"][:8]

    results = []
    for r in rels:
        results.append({
            "from_id": r.from_contact_id,
            "from_name": contact_names.get(r.from_contact_id, r.from_contact_id[:8]),
            "to_id": r.to_contact_id,
            "to_name": contact_names.get(r.to_contact_id, r.to_contact_id[:8]),
            "strength": r.strength,
            "shared_conversations": r.shared_conversations,
            "shared_messages": r.shared_messages,
        })
    return results


@router.get("", response_class=HTMLResponse)
def relationship_list(request: Request, contact_id: str = "", min_strength: float = 0.0):
    templates = request.app.state.templates
    rels = _get_relationships(contact_id=contact_id, min_strength=min_strength)

    return templates.TemplateResponse(request, "relationships/list.html", {
        "active_nav": "relationships",
        "relationships": rels,
        "contact_id": contact_id,
        "min_strength": min_strength,
    })


@router.get("/search", response_class=HTMLResponse)
def relationship_search(request: Request, contact_id: str = "", min_strength: float = 0.0):
    templates = request.app.state.templates
    rels = _get_relationships(contact_id=contact_id, min_strength=min_strength)

    return templates.TemplateResponse(request, "relationships/_rows.html", {
        "relationships": rels,
    })


@router.post("/infer", response_class=HTMLResponse)
def relationship_infer(request: Request):
    from ...relationship_inference import infer_relationships
    count = infer_relationships()
    return HTMLResponse(f"<p><strong>{count}</strong> relationship(s) inferred.</p>")
