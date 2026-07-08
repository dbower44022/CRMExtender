"""Workflow JSON API (Legacy UI Migration PRD, Phase 4).

Ports the legacy HTMX workflow routes: relationships (list/create/
delete/infer + type admin), vCard import, per-contact email sync,
company domain resolution / duplicates report / enrichment /
duplicate-checked create. Assignment and project/topic workflows are in
the second section of this module.

Deliberate improvements over legacy, recorded in the PRD:
- ValueErrors surface as 400s (legacy silently swallowed duplicate
  relationship types, duplicate relationships, and company-name
  clashes).
- Relationship types created here are customer-scoped (legacy left
  customer_id NULL, sharing every custom type across tenants).
- resolve-domains exposes dry_run.
- Batch relationship results carry ids, not just display names.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import asdict
from datetime import datetime, timezone

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from ...database import get_connection

router = APIRouter()
log = logging.getLogger(__name__)


def _err(message: str, status: int = 400, **extra) -> JSONResponse:
    return JSONResponse({"error": message, **extra}, status_code=status)


def _uid(request: Request) -> str | None:
    return request.state.user["id"] if request.state.user else None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _entity_names(conn, entity_ids: set[str]) -> dict[str, str]:
    """Batch name lookup across contacts and companies."""
    names: dict[str, str] = {}
    if not entity_ids:
        return names
    marks = ",".join("?" for _ in entity_ids)
    ids = list(entity_ids)
    for row in conn.execute(
        f"SELECT id, name FROM contacts WHERE id IN ({marks})", ids
    ):
        names[row["id"]] = row["name"]
    for row in conn.execute(
        f"SELECT id, name FROM companies WHERE id IN ({marks})", ids
    ):
        names.setdefault(row["id"], row["name"])
    return names


# ---------------------------------------------------------------------------
# Relationships
# ---------------------------------------------------------------------------

@router.get("/relationships")
def relationships_list_api(
    request: Request,
    contact_id: str = "",
    min_strength: float = 0.0,
    type_id: str = "",
    source: str = "",
):
    import json as _json

    from ...relationship_inference import _build_canonical_map

    with get_connection() as conn:
        lookup_id = contact_id or None
        if lookup_id:
            canonical = _build_canonical_map(conn)
            lookup_id = canonical.get(lookup_id, lookup_id)

        clauses = []
        params: list = []
        if lookup_id:
            clauses.append("r.from_entity_id = ?")
            params.append(lookup_id)
        else:
            clauses.append(
                "(r.paired_relationship_id IS NULL OR r.from_entity_id < r.to_entity_id)"
            )
        if type_id:
            clauses.append("r.relationship_type_id = ?")
            params.append(type_id)
        if source:
            clauses.append("r.source = ?")
            params.append(source)

        rows = conn.execute(
            f"""SELECT r.*, rt.name AS type_name,
                       rt.forward_label, rt.reverse_label
                FROM relationships r
                JOIN relationship_types rt ON rt.id = r.relationship_type_id
                WHERE {' AND '.join(clauses)}
                ORDER BY r.updated_at DESC""",
            params,
        ).fetchall()

        ids = {r["from_entity_id"] for r in rows} | {r["to_entity_id"] for r in rows}
        names = _entity_names(conn, ids)

    results = []
    for r in rows:
        props = {}
        if r["properties"]:
            try:
                props = _json.loads(r["properties"])
            except ValueError:
                pass
        strength = float(props.get("strength", 0.0))
        if strength < min_strength:
            continue
        results.append({
            "id": r["id"],
            "from_id": r["from_entity_id"],
            "from_name": names.get(r["from_entity_id"], r["from_entity_id"][:8]),
            "from_entity_type": r["from_entity_type"],
            "to_id": r["to_entity_id"],
            "to_name": names.get(r["to_entity_id"], r["to_entity_id"][:8]),
            "to_entity_type": r["to_entity_type"],
            "type_name": r["type_name"],
            "forward_label": r["forward_label"],
            "reverse_label": r["reverse_label"],
            "source": r["source"],
            "strength": strength,
            "shared_conversations": props.get("shared_conversations", 0),
            "shared_messages": props.get("shared_messages", 0),
        })
    results.sort(key=lambda x: x["strength"], reverse=True)
    return {"relationships": results}


@router.post("/relationships/infer")
def relationships_infer_api(request: Request):
    from ...relationship_inference import infer_relationships

    count = infer_relationships()
    return {"count": count}


def _create_manual_relationship(conn, rt: dict, from_id: str, to_id: str) -> dict:
    """Insert a manual relationship (+ reverse row when bidirectional).
    Caller has verified no duplicate exists."""
    now = _now()
    fwd_id = str(uuid.uuid4())
    conn.execute(
        "INSERT INTO relationships "
        "(id, relationship_type_id, from_entity_type, from_entity_id, "
        " to_entity_type, to_entity_id, source, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, 'manual', ?, ?)",
        (fwd_id, rt["id"], rt["from_entity_type"], from_id,
         rt["to_entity_type"], to_id, now, now),
    )
    if rt["is_bidirectional"]:
        rev_id = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO relationships "
            "(id, relationship_type_id, from_entity_type, from_entity_id, "
            " to_entity_type, to_entity_id, source, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, 'manual', ?, ?)",
            (rev_id, rt["id"], rt["to_entity_type"], to_id,
             rt["from_entity_type"], from_id, now, now),
        )
        conn.execute(
            "UPDATE relationships SET paired_relationship_id = ? WHERE id = ?",
            (rev_id, fwd_id))
        conn.execute(
            "UPDATE relationships SET paired_relationship_id = ? WHERE id = ?",
            (fwd_id, rev_id))
    return {"id": fwd_id}


@router.post("/relationships")
async def relationships_create_api(request: Request):
    """Create manual relationship(s). Accepts a single from_entity_id or a
    batch via from_entity_ids (the legacy relate wizard)."""
    body = await request.json()
    type_id = body.get("relationship_type_id")
    to_id = body.get("to_entity_id")
    from_ids = body.get("from_entity_ids") or (
        [body["from_entity_id"]] if body.get("from_entity_id") else []
    )
    if not type_id or not to_id or not from_ids:
        return _err(
            "relationship_type_id, to_entity_id and from_entity_id(s) are required"
        )

    with get_connection() as conn:
        rt = conn.execute(
            "SELECT * FROM relationship_types WHERE id = ?", (type_id,)
        ).fetchone()
        if not rt:
            return _err("Relationship type not found", 404)
        rt = dict(rt)

        names = _entity_names(conn, set(from_ids) | {to_id})
        results = []
        for from_id in from_ids:
            if from_id == to_id:
                results.append({"from_entity_id": from_id,
                                "status": "skipped",
                                "reason": "Self-relationship"})
                continue
            dup = conn.execute(
                "SELECT id FROM relationships WHERE relationship_type_id = ? "
                "AND ((from_entity_id = ? AND to_entity_id = ?) "
                "  OR (from_entity_id = ? AND to_entity_id = ?))",
                (type_id, from_id, to_id, to_id, from_id),
            ).fetchone()
            if dup:
                results.append({"from_entity_id": from_id,
                                "status": "skipped",
                                "reason": "Already exists",
                                "relationship_id": dup["id"]})
                continue
            try:
                created = _create_manual_relationship(conn, rt, from_id, to_id)
                results.append({"from_entity_id": from_id,
                                "from_name": names.get(from_id),
                                "status": "created",
                                "relationship_id": created["id"]})
            except Exception as exc:  # keep batch going, report per row
                results.append({"from_entity_id": from_id,
                                "status": "error", "reason": str(exc)})

    created_count = sum(1 for r in results if r["status"] == "created")
    return JSONResponse(
        {"results": results, "created": created_count,
         "to_entity_name": names.get(to_id)},
        status_code=201 if created_count else 200,
    )


@router.delete("/relationships/{relationship_id}")
def relationships_delete_api(request: Request, relationship_id: str):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT source, paired_relationship_id FROM relationships WHERE id = ?",
            (relationship_id,),
        ).fetchone()
        if not row:
            return _err("Not found", 404)
        if row["source"] != "manual":
            return _err("Cannot delete inferred relationships")
        conn.execute("DELETE FROM relationships WHERE id = ?", (relationship_id,))
        if row["paired_relationship_id"]:
            conn.execute(
                "DELETE FROM relationships WHERE id = ?",
                (row["paired_relationship_id"],),
            )
    return {"deleted": True}


# ---------------------------------------------------------------------------
# Relationship types
# ---------------------------------------------------------------------------

@router.get("/relationship-types")
def relationship_types_list_api(
    request: Request,
    from_entity_type: str = "",
    to_entity_type: str = "",
):
    from ...relationship_types import list_relationship_types

    return {
        "types": list_relationship_types(
            from_entity_type=from_entity_type or None,
            to_entity_type=to_entity_type or None,
            customer_id=request.state.customer_id,
        )
    }


@router.post("/relationship-types")
async def relationship_types_create_api(request: Request):
    from ...relationship_types import create_relationship_type

    body = await request.json()
    name = (body.get("name") or "").strip()
    if not name:
        return _err("name is required")
    try:
        row = create_relationship_type(
            name,
            body.get("from_entity_type") or "contact",
            body.get("to_entity_type") or "contact",
            (body.get("forward_label") or "").strip(),
            (body.get("reverse_label") or "").strip(),
            is_bidirectional=bool(body.get("is_bidirectional")),
            description=(body.get("description") or "").strip(),
            created_by=_uid(request),
            customer_id=request.state.customer_id,
        )
    except ValueError as exc:
        return _err(str(exc))
    return JSONResponse(row, status_code=201)


@router.delete("/relationship-types/{type_id}")
def relationship_types_delete_api(request: Request, type_id: str):
    from ...relationship_types import delete_relationship_type

    try:
        delete_relationship_type(type_id)
    except ValueError as exc:
        return _err(str(exc))
    return {"deleted": True}


# ---------------------------------------------------------------------------
# vCard import + per-contact email sync
# ---------------------------------------------------------------------------

@router.post("/contacts/import-vcards")
async def contacts_import_api(request: Request):
    from ...vcard_import import import_vcards

    body = await request.json()
    path = (body.get("path") or "").strip()
    if not path:
        return _err("path is required")
    try:
        result = import_vcards(
            path,
            recursive=bool(body.get("recursive")),
            customer_id=request.state.customer_id,
            user_id=_uid(request),
        )
    except (FileNotFoundError, ValueError) as exc:
        return _err(str(exc))
    return asdict(result)


@router.post("/contacts/{contact_id}/sync-email")
async def contact_sync_email_api(request: Request, contact_id: str):
    from ...sync import _VALID_WINDOWS, sync_contact_email

    cid = request.state.customer_id
    with get_connection() as conn:
        row = conn.execute(
            "SELECT customer_id FROM contacts WHERE id = ?", (contact_id,)
        ).fetchone()
    if not row or (row["customer_id"] and row["customer_id"] != cid):
        return _err("Contact not found", 404)

    body = await request.json()
    window = body.get("window") or "90d"
    if window not in _VALID_WINDOWS:
        return _err("Invalid time window")

    # Gmail-bound and potentially slow (minutes for window=all) — the
    # request runs synchronously; the SPA warns and awaits.
    try:
        result = sync_contact_email(
            contact_id, window, customer_id=cid, user_id=_uid(request),
        )
    except Exception as exc:
        log.exception("Per-contact email sync failed")
        return _err(str(exc), 502)
    return result


# ---------------------------------------------------------------------------
# Company operations
# ---------------------------------------------------------------------------

@router.post("/companies/resolve-domains")
async def companies_resolve_domains_api(request: Request):
    from ...domain_resolver import resolve_unlinked_contacts

    body = await request.json() if await request.body() else {}
    result = resolve_unlinked_contacts(dry_run=bool(body.get("dry_run")))
    return asdict(result)


@router.get("/companies/duplicates")
def companies_duplicates_api(request: Request):
    from ...company_merge import detect_all_duplicates

    return {"groups": detect_all_duplicates()}


@router.post("/companies/{company_id}/enrich")
def company_enrich_api(request: Request, company_id: str):
    from ... import website_scraper  # noqa: F401 — registers the provider
    from ...enrichment_pipeline import execute_enrichment

    cid = request.state.customer_id
    with get_connection() as conn:
        row = conn.execute(
            "SELECT customer_id FROM companies WHERE id = ?", (company_id,)
        ).fetchone()
    if not row or (row["customer_id"] and row["customer_id"] != cid):
        return _err("Company not found", 404)

    # Live HTTP scrape of the company website — up to ~10 requests with
    # 10s timeouts; synchronous by design, the SPA shows progress.
    result = execute_enrichment("company", company_id, "website_scraper")
    if result.get("status") == "failed":
        return _err(result.get("error") or "Enrichment failed", 422,
                    run_id=result.get("run_id"))
    return result


@router.post("/companies/check")
async def companies_check_api(request: Request):
    """Pre-create duplicate/link check (phase 1 of the legacy two-step
    create). Returns possible duplicate companies for the domain and
    unlinked contacts whose email matches it."""
    from ...company_merge import PUBLIC_DOMAINS, find_duplicates_for_domain

    body = await request.json()
    domain = (body.get("domain") or "").strip().lower()
    if not domain or domain in PUBLIC_DOMAINS:
        return {"existing_companies": [], "linkable_contacts": []}

    existing = find_duplicates_for_domain(domain)
    with get_connection() as conn:
        contacts = [
            {"id": r["id"], "name": r["name"], "email": r["email"]}
            for r in conn.execute(
                """SELECT c.id, c.name, ci.value AS email
                   FROM contacts c
                   JOIN contact_identifiers ci
                     ON ci.contact_id = c.id AND ci.type = 'email'
                   WHERE ci.value LIKE ? AND c.customer_id = ?
                     AND NOT EXISTS (SELECT 1 FROM contact_companies cc
                                     WHERE cc.contact_id = c.id)
                   GROUP BY c.id""",
                (f"%@{domain}", request.state.customer_id),
            ).fetchall()
        ]
    return {"existing_companies": existing, "linkable_contacts": contacts}


@router.post("/companies/{company_id}/link-domain-contacts")
def company_link_domain_contacts_api(request: Request, company_id: str):
    """Link all unlinked contacts whose email matches the company's domain
    (phase 2 of the legacy confirm flow, decoupled from create)."""
    from ...contact_companies import add_affiliation

    cid = request.state.customer_id
    with get_connection() as conn:
        row = conn.execute(
            "SELECT customer_id, domain FROM companies WHERE id = ?",
            (company_id,),
        ).fetchone()
        if not row or (row["customer_id"] and row["customer_id"] != cid):
            return _err("Company not found", 404)
        domain = (row["domain"] or "").strip().lower()
        if not domain:
            return _err("Company has no domain")
        contacts = conn.execute(
            """SELECT c.id FROM contacts c
               JOIN contact_identifiers ci
                 ON ci.contact_id = c.id AND ci.type = 'email'
               WHERE ci.value LIKE ? AND c.customer_id = ?
                 AND NOT EXISTS (SELECT 1 FROM contact_companies cc
                                 WHERE cc.contact_id = c.id)
               GROUP BY c.id""",
            (f"%@{domain}", cid),
        ).fetchall()

    linked = 0
    for c in contacts:
        add_affiliation(
            c["id"], company_id, is_primary=True, is_current=True,
            source="domain_link", created_by=_uid(request),
        )
        linked += 1
    return {"contacts_linked": linked}


# ===========================================================================
# Assignment, projects/topics, events (Phase 4 second section)
# ===========================================================================

def _owned_conversation(conn, request: Request, conversation_id: str) -> bool:
    row = conn.execute(
        "SELECT customer_id FROM conversations WHERE id = ?", (conversation_id,)
    ).fetchone()
    if not row:
        return False
    return not row["customer_id"] or row["customer_id"] == request.state.customer_id


def _owned_topic(conn, request: Request, topic_id: str) -> bool:
    row = conn.execute(
        """SELECT p.customer_id FROM topics t
           JOIN projects p ON p.id = t.project_id WHERE t.id = ?""",
        (topic_id,),
    ).fetchone()
    if not row:
        return False
    return not row["customer_id"] or row["customer_id"] == request.state.customer_id


def _owned_project(conn, request: Request, project_id: str):
    row = conn.execute(
        "SELECT * FROM projects WHERE id = ?", (project_id,)
    ).fetchone()
    if not row:
        return None
    if row["customer_id"] and row["customer_id"] != request.state.customer_id:
        return None
    return dict(row)


def _communications_owned(conn, request: Request, ids: list[str]) -> list[str]:
    """Return the subset of ids that exist and are tenant-owned
    (NULL account_id counts as owned, matching the view engine)."""
    cid = request.state.customer_id
    owned = []
    for comm_id in ids:
        row = conn.execute(
            """SELECT c.id FROM communications c
               LEFT JOIN provider_accounts pa ON pa.id = c.account_id
               WHERE c.id = ? AND (c.account_id IS NULL OR pa.customer_id = ?)""",
            (comm_id, cid),
        ).fetchone()
        if row:
            owned.append(comm_id)
    return owned


# ---------------------------------------------------------------------------
# Conversation topic assignment
# ---------------------------------------------------------------------------

@router.get("/topics")
def topics_list_api(request: Request, project_id: str = ""):
    cid = request.state.customer_id
    clauses = ["(p.customer_id IS NULL OR p.customer_id = ?)"]
    params: list = [cid]
    if project_id:
        clauses.append("t.project_id = ?")
        params.append(project_id)
    with get_connection() as conn:
        rows = conn.execute(
            f"""SELECT t.id, t.name, t.project_id, p.name AS project_name
                FROM topics t JOIN projects p ON p.id = t.project_id
                WHERE {' AND '.join(clauses)}
                ORDER BY p.name COLLATE NOCASE, t.name COLLATE NOCASE""",
            params,
        ).fetchall()
    return {"topics": [dict(r) for r in rows]}


@router.post("/conversations/{conversation_id}/topic")
async def conversation_topic_assign_api(request: Request, conversation_id: str):
    from ...hierarchy import assign_conversation_to_topic

    body = await request.json()
    topic_id = (body.get("topic_id") or "").strip()
    if not topic_id:
        return _err("topic_id is required")

    with get_connection() as conn:
        if not _owned_conversation(conn, request, conversation_id):
            return _err("Not found", 404)
        if not _owned_topic(conn, request, topic_id):
            return _err("Topic not found")

    try:
        assign_conversation_to_topic(conversation_id, topic_id)
    except ValueError as exc:
        return _err(str(exc))

    with get_connection() as conn:
        topic = conn.execute(
            """SELECT t.id, t.name, t.project_id, p.name AS project_name
               FROM topics t JOIN projects p ON p.id = t.project_id
               WHERE t.id = ?""",
            (topic_id,),
        ).fetchone()
    return {"id": conversation_id, "topic": dict(topic) if topic else None}


@router.delete("/conversations/{conversation_id}/topic")
def conversation_topic_unassign_api(request: Request, conversation_id: str):
    from ...hierarchy import unassign_conversation

    with get_connection() as conn:
        if not _owned_conversation(conn, request, conversation_id):
            return _err("Not found", 404)
    try:
        unassign_conversation(conversation_id)
    except ValueError as exc:
        return _err(str(exc))
    return {"id": conversation_id, "topic": None}


# ---------------------------------------------------------------------------
# Communications bulk actions
# ---------------------------------------------------------------------------

@router.get("/communications/assign-targets")
def communications_assign_targets_api(request: Request, q: str = ""):
    cid = request.state.customer_id
    clauses = ["customer_id = ?", "dismissed = 0"]
    params: list = [cid]
    if q.strip():
        clauses.append("title LIKE ? COLLATE NOCASE")
        params.append(f"%{q.strip()}%")
    with get_connection() as conn:
        rows = conn.execute(
            f"""SELECT id, title, last_activity_at FROM conversations
                WHERE {' AND '.join(clauses)}
                ORDER BY last_activity_at DESC LIMIT 20""",
            params,
        ).fetchall()
    return {"conversations": [dict(r) for r in rows]}


@router.post("/communications/archive")
async def communications_archive_api(request: Request):
    body = await request.json()
    ids = body.get("ids") or []
    if not ids:
        return _err("ids is required")

    now = _now()
    archived = 0
    dismissed = 0
    with get_connection() as conn:
        owned = _communications_owned(conn, request, ids)
        for comm_id in owned:
            conn.execute(
                "UPDATE communications SET is_archived = 1, updated_at = ? "
                "WHERE id = ?", (now, comm_id),
            )
            archived += 1
            conv_ids = [r["conversation_id"] for r in conn.execute(
                "SELECT conversation_id FROM conversation_communications "
                "WHERE communication_id = ?", (comm_id,)).fetchall()]
            conn.execute(
                "DELETE FROM conversation_communications WHERE communication_id = ?",
                (comm_id,),
            )
            for conv_id in conv_ids:
                remaining = conn.execute(
                    "SELECT COUNT(*) AS c FROM conversation_communications "
                    "WHERE conversation_id = ?", (conv_id,)).fetchone()["c"]
                if remaining == 0:
                    conn.execute(
                        "UPDATE conversations SET dismissed = 1, "
                        "dismissed_reason = 'archived', dismissed_at = ? "
                        "WHERE id = ?", (now, conv_id),
                    )
                    dismissed += 1
    return {"archived": archived, "conversations_dismissed": dismissed,
            "skipped": len(ids) - len(owned)}


@router.post("/communications/assign")
async def communications_assign_api(request: Request):
    body = await request.json()
    ids = body.get("ids") or []
    conversation_id = (body.get("conversation_id") or "").strip()
    if not ids or not conversation_id:
        return _err("ids and conversation_id are required")

    now = _now()
    assigned = 0
    skipped = 0
    with get_connection() as conn:
        if not _owned_conversation(conn, request, conversation_id):
            return _err("Conversation not found", 404)
        owned = _communications_owned(conn, request, ids)
        for comm_id in owned:
            cur = conn.execute(
                "INSERT OR IGNORE INTO conversation_communications "
                "(conversation_id, communication_id, assignment_source, "
                " confidence, created_at) VALUES (?, ?, 'manual', 1.0, ?)",
                (conversation_id, comm_id, now),
            )
            if cur.rowcount:
                assigned += 1
            else:
                skipped += 1
    return {"assigned": assigned, "skipped_existing": skipped,
            "skipped_foreign": len(ids) - len(owned)}


@router.post("/communications/delete-conversation")
async def communications_delete_conversation_api(request: Request):
    body = await request.json()
    ids = body.get("ids") or []
    delete_comms = bool(body.get("delete_comms"))
    if not ids:
        return _err("ids is required")

    with get_connection() as conn:
        owned = _communications_owned(conn, request, ids)
        conv_ids: set[str] = set()
        for comm_id in owned:
            for r in conn.execute(
                "SELECT conversation_id FROM conversation_communications "
                "WHERE communication_id = ?", (comm_id,)).fetchall():
                conv_ids.add(r["conversation_id"])
        conv_ids = {
            c for c in conv_ids if _owned_conversation(conn, request, c)
        }
        for conv_id in conv_ids:
            conn.execute("DELETE FROM conversations WHERE id = ?", (conv_id,))
        comms_deleted = 0
        if delete_comms:
            for comm_id in owned:
                conn.execute(
                    "DELETE FROM communications WHERE id = ?", (comm_id,))
                comms_deleted += 1
    return {"conversations_deleted": len(conv_ids),
            "communications_deleted": comms_deleted}


# ---------------------------------------------------------------------------
# Projects & topics
# ---------------------------------------------------------------------------

@router.get("/projects")
def projects_list_api(request: Request):
    from ...hierarchy import get_hierarchy_stats, get_topic_stats

    projects = get_hierarchy_stats(customer_id=request.state.customer_id)
    for p in projects:
        p["topics"] = get_topic_stats(p["id"])
    return {"projects": projects}


@router.post("/projects")
async def projects_create_api(request: Request):
    from ...hierarchy import create_project

    body = await request.json()
    name = (body.get("name") or "").strip()
    if not name:
        return _err("name is required")
    try:
        row = create_project(
            name, description=(body.get("description") or "").strip(),
            created_by=_uid(request), customer_id=request.state.customer_id,
        )
    except ValueError as exc:
        return _err(str(exc), 409)
    return JSONResponse(row, status_code=201)


@router.delete("/projects/{project_id}")
def projects_delete_api(request: Request, project_id: str):
    from ...hierarchy import delete_project

    with get_connection() as conn:
        if not _owned_project(conn, request, project_id):
            return _err("Not found", 404)
    return {"deleted": True, **delete_project(project_id)}


@router.get("/projects/{project_id}/topics")
def project_topics_api(request: Request, project_id: str):
    from ...hierarchy import get_topic_stats

    with get_connection() as conn:
        if not _owned_project(conn, request, project_id):
            return _err("Not found", 404)
    return {"topics": get_topic_stats(project_id)}


@router.post("/projects/{project_id}/topics")
async def project_topic_create_api(request: Request, project_id: str):
    from ...hierarchy import create_topic

    with get_connection() as conn:
        if not _owned_project(conn, request, project_id):
            return _err("Not found", 404)
    body = await request.json()
    name = (body.get("name") or "").strip()
    if not name:
        return _err("name is required")
    try:
        row = create_topic(
            project_id, name,
            description=(body.get("description") or "").strip(),
            created_by=_uid(request),
        )
    except ValueError as exc:
        status = 409 if "already exists" in str(exc) else 400
        return _err(str(exc), status)
    return JSONResponse(row, status_code=201)


@router.delete("/projects/{project_id}/topics/{topic_id}")
def project_topic_delete_api(request: Request, project_id: str, topic_id: str):
    from ...hierarchy import delete_topic

    with get_connection() as conn:
        if not _owned_project(conn, request, project_id):
            return _err("Not found", 404)
        row = conn.execute(
            "SELECT 1 FROM topics WHERE id = ? AND project_id = ?",
            (topic_id, project_id),
        ).fetchone()
        if not row:
            return _err("Not found", 404)
    return {"deleted": True, **delete_topic(topic_id)}


@router.post("/projects/{project_id}/auto-assign/preview")
def auto_assign_preview_api(request: Request, project_id: str):
    from ...auto_assign import find_matching_topics

    with get_connection() as conn:
        if not _owned_project(conn, request, project_id):
            return _err("Not found", 404)
    try:
        report = find_matching_topics(project_id)
    except ValueError as exc:
        return _err(str(exc), 422)
    return asdict(report)


@router.post("/projects/{project_id}/auto-assign/apply")
def auto_assign_apply_api(request: Request, project_id: str):
    from ...auto_assign import apply_assignments, find_matching_topics

    with get_connection() as conn:
        if not _owned_project(conn, request, project_id):
            return _err("Not found", 404)
    # Recomputes rather than replaying the preview — stateless, and the
    # data may have changed since the preview was shown
    try:
        report = find_matching_topics(project_id)
    except ValueError as exc:
        return _err(str(exc), 422)
    count = apply_assignments(report.assignments)
    return {"assigned": count,
            "total_candidates": report.total_candidates,
            "unmatched": report.unmatched}


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------

_EVENT_TYPES = ("meeting", "birthday", "anniversary", "conference",
                "deadline", "other")
_RECURRENCE_TYPES = ("none", "daily", "weekly", "monthly", "yearly")
_EVENT_STATUSES = ("confirmed", "tentative", "cancelled")


@router.post("/events")
async def events_create_api(request: Request):
    body = await request.json()
    title = (body.get("title") or "").strip()
    if not title:
        return _err("title is required")
    event_type = body.get("event_type") or "meeting"
    recurrence = body.get("recurrence_type") or "none"
    status = body.get("status") or "confirmed"
    if event_type not in _EVENT_TYPES:
        return _err("Invalid event_type")
    if recurrence not in _RECURRENCE_TYPES:
        return _err("Invalid recurrence_type")
    if status not in _EVENT_STATUSES:
        return _err("Invalid status")

    now = _now()
    event_id = str(uuid.uuid4())
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO events
               (id, title, event_type, start_date, start_datetime,
                end_date, end_datetime, is_all_day, location, description,
                recurrence_type, status, source, created_by,
                created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'manual', ?, ?, ?)""",
            (event_id, title, event_type,
             (body.get("start_date") or "").strip() or None,
             (body.get("start_datetime") or "").strip() or None,
             (body.get("end_date") or "").strip() or None,
             (body.get("end_datetime") or "").strip() or None,
             1 if body.get("is_all_day") else 0,
             (body.get("location") or "").strip() or None,
             (body.get("description") or "").strip() or None,
             recurrence, status, _uid(request), now, now),
        )
        row = conn.execute(
            "SELECT * FROM events WHERE id = ?", (event_id,)
        ).fetchone()
    return JSONResponse(dict(row), status_code=201)


@router.delete("/events/{event_id}")
def events_delete_api(request: Request, event_id: str):
    cid = request.state.customer_id
    with get_connection() as conn:
        row = conn.execute(
            """SELECT e.source, e.account_id, pa.customer_id AS acct_customer
               FROM events e
               LEFT JOIN provider_accounts pa ON pa.id = e.account_id
               WHERE e.id = ?""",
            (event_id,),
        ).fetchone()
        if not row or (row["account_id"] and row["acct_customer"] != cid):
            return _err("Not found", 404)
        conn.execute("DELETE FROM events WHERE id = ?", (event_id,))
    # Synced events reappear on the next calendar sync (upsert by
    # provider_event_id) — surface the source so the client can warn
    return {"deleted": True, "source": row["source"]}


@router.post("/events/sync")
def events_sync_api(request: Request):
    from ...sync_service import start_background_calendar_sync

    started = start_background_calendar_sync(
        customer_id=request.state.customer_id, user_id=_uid(request) or "",
    )
    if not started:
        return _err("A calendar sync is already running", 409)
    return {"status": "started"}


@router.get("/events/sync/status")
def events_sync_status_api(request: Request):
    from ...sync_service import calendar_sync_status

    return calendar_sync_status()


# ---------------------------------------------------------------------------
# Identity resolution: duplicate scan + review queue
# (Identity Resolution Sub-PRD §7/§9)
# ---------------------------------------------------------------------------

@router.post("/contacts/duplicate-scan")
def contacts_duplicate_scan_api(request: Request):
    """Scan existing contacts pairwise and queue review candidates."""
    from ...identity_resolution import scan_existing_contacts

    return scan_existing_contacts(customer_id=request.state.customer_id)


@router.get("/contacts/review-queue")
def review_queue_list_api(request: Request, sort: str = "confidence"):
    import json as _json

    cid = request.state.customer_id
    order = {
        "confidence": "mc.confidence DESC",
        "date": "mc.created_at DESC",
        "source": "mc.source, mc.confidence DESC",
    }.get(sort, "mc.confidence DESC")

    with get_connection() as conn:
        rows = conn.execute(
            f"""SELECT mc.*, ca.name AS name_a, cb.name AS name_b,
                       (SELECT value FROM contact_identifiers
                        WHERE contact_id = mc.contact_a_id AND type = 'email'
                        LIMIT 1) AS email_a,
                       (SELECT value FROM contact_identifiers
                        WHERE contact_id = mc.contact_b_id AND type = 'email'
                        LIMIT 1) AS email_b
                FROM match_candidates mc
                JOIN contacts ca ON ca.id = mc.contact_a_id
                JOIN contacts cb ON cb.id = mc.contact_b_id
                WHERE mc.status = 'pending'
                  AND (mc.customer_id IS NULL OR mc.customer_id = ?)
                ORDER BY {order}""",
            (cid,),
        ).fetchall()

    candidates = []
    for r in rows:
        d = dict(r)
        try:
            d["signals"] = _json.loads(d["signals"] or "[]")
        except ValueError:
            d["signals"] = []
        candidates.append(d)
    return {"candidates": candidates, "pending_count": len(candidates)}


@router.post("/contacts/review-queue/{candidate_id}/reject")
def review_queue_reject_api(request: Request, candidate_id: str):
    """Not a match — rejected pairs are never re-queued (IDENT-26)."""
    now = _now()
    with get_connection() as conn:
        cur = conn.execute(
            "UPDATE match_candidates SET status = 'rejected', "
            "reviewed_by = ?, reviewed_at = ?, updated_at = ? "
            "WHERE id = ? AND status = 'pending' "
            "AND (customer_id IS NULL OR customer_id = ?)",
            (_uid(request), now, now, candidate_id,
             request.state.customer_id),
        )
        if not cur.rowcount:
            return _err("Not found", 404)
    return {"status": "rejected"}


@router.post("/contacts/review-queue/{candidate_id}/restore")
def review_queue_restore_api(request: Request, candidate_id: str):
    """Undo a rejection (IDENT-28)."""
    now = _now()
    with get_connection() as conn:
        cur = conn.execute(
            "UPDATE match_candidates SET status = 'pending', "
            "reviewed_by = NULL, reviewed_at = NULL, updated_at = ? "
            "WHERE id = ? AND status = 'rejected' "
            "AND (customer_id IS NULL OR customer_id = ?)",
            (now, candidate_id, request.state.customer_id),
        )
        if not cur.rowcount:
            return _err("Not found", 404)
    return {"status": "pending"}


# ---------------------------------------------------------------------------
# Identity resolution thresholds (IDENT-09/10)
# ---------------------------------------------------------------------------

@router.get("/settings/duplicate-thresholds")
def duplicate_thresholds_get_api(request: Request):
    from ...identity_resolution import DEFAULT_THRESHOLDS, get_thresholds

    return {
        "thresholds": get_thresholds(request.state.customer_id),
        "defaults": DEFAULT_THRESHOLDS,
    }


@router.put("/settings/duplicate-thresholds")
async def duplicate_thresholds_set_api(request: Request):
    from ...settings import set_setting

    if request.state.user and request.state.user.get("role") != "admin":
        return _err("Forbidden", 403)
    cid = request.state.customer_id
    body = await request.json()
    for key in ("auto", "flag", "review"):
        if key in body:
            try:
                v = float(body[key])
            except (TypeError, ValueError):
                return _err(f"Invalid value for {key}")
            if not 0.0 <= v <= 1.0:
                return _err(f"{key} must be between 0 and 1")
            set_setting(cid, f"idr_threshold_{key}", str(v),
                        scope="system")
    from ...identity_resolution import get_thresholds
    return {"thresholds": get_thresholds(cid)}
