"""Legacy path compatibility (Legacy UI Migration PRD, Phase 5).

The HTMX/Jinja UI is decommissioned. This module keeps the three things
the SPA still depends on at legacy paths, plus permanent redirects from
old page URLs into the SPA:

1. GET /settings/accounts/connect — Google OAuth account-connect
   redirect flow (moved verbatim from the deleted settings_routes.py;
   the callback lives on in auth_routes.py).
2. GET /notes/files/{attachment_id}/{filename} — attachment serving;
   stored note HTML embeds this path.
3. 308 redirects: entity pages -> /app/{plural}[/{id}], dashboard -> the
   SPA dashboard, everything settings-ish -> /app/. Legacy POST/fragment
   action routes are gone (404) — the SPA uses /api/v1.
"""

from __future__ import annotations

import uuid
from urllib.parse import urlencode

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from ... import config

router = APIRouter()

_GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"


# ---------------------------------------------------------------------------
# Kept flows
# ---------------------------------------------------------------------------

@router.get("/settings/accounts/connect")
async def accounts_connect(request: Request):
    if not config.GOOGLE_OAUTH_CLIENT_ID:
        return RedirectResponse(
            "/app/?error=Google+OAuth+not+configured", status_code=302,
        )

    user = getattr(request.state, "user", None)
    if not user:
        return RedirectResponse("/login", status_code=302)

    state = str(uuid.uuid4())
    scopes = config.GOOGLE_SCOPES + ["openid", "email"]
    base = str(request.base_url).rstrip("/")
    redirect_uri = f"{base}/auth/google/callback"

    params = {
        "client_id": config.GOOGLE_OAUTH_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "scope": " ".join(scopes),
        "response_type": "code",
        "state": state,
        "access_type": "offline",
        "prompt": "consent",
    }
    url = f"{_GOOGLE_AUTH_URL}?{urlencode(params)}"

    response = RedirectResponse(url, status_code=302)
    response.set_cookie(
        "oauth_state", state,
        httponly=True, samesite="lax", max_age=600,
    )
    response.set_cookie(
        "oauth_purpose", "add-account",
        httponly=True, samesite="lax", max_age=600,
    )
    # The SPA is the only UI now — always return to it after connecting
    response.set_cookie(
        "oauth_return_to", "/app/",
        httponly=True, samesite="lax", max_age=600,
    )
    return response


@router.get("/notes/files/{attachment_id}/{filename}")
def legacy_notes_file(request: Request, attachment_id: str, filename: str):
    from .api_notes import notes_file_api

    return notes_file_api(request, attachment_id, filename)


# ---------------------------------------------------------------------------
# Redirects into the SPA
# ---------------------------------------------------------------------------

_ENTITY_PATHS = (
    "contacts", "companies", "conversations", "communications",
    "events", "projects", "relationships",
)


@router.get("/")
def legacy_root(request: Request):
    return RedirectResponse("/app/dashboard", status_code=308)


def _entity_redirects(plural: str) -> None:
    @router.get(f"/{plural}", name=f"legacy_{plural}_list")
    def _list(request: Request):
        return RedirectResponse(f"/app/{plural}", status_code=308)

    @router.get(f"/{plural}/{{entity_id}}", name=f"legacy_{plural}_detail")
    def _detail(request: Request, entity_id: str):
        return RedirectResponse(f"/app/{plural}/{entity_id}", status_code=308)


for _plural in _ENTITY_PATHS:
    _entity_redirects(_plural)


@router.get("/notes/search")
def legacy_notes_search(request: Request):
    return RedirectResponse("/app/notes", status_code=308)


@router.get("/views")
@router.get("/views/{view_id}")
def legacy_views(request: Request, view_id: str = ""):
    return RedirectResponse("/app/", status_code=308)


@router.get("/settings/{rest_of_path:path}")
def legacy_settings(request: Request, rest_of_path: str):
    return RedirectResponse("/app/", status_code=308)
