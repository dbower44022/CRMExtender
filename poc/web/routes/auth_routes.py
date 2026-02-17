"""Login / logout routes (password + Google OAuth)."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token
from starlette.responses import HTMLResponse

from ... import config
from ...database import get_connection
from ...hierarchy import DEFAULT_CUSTOMER_ID, create_user, get_user_by_email, get_user_by_google_sub, set_google_sub
from ...passwords import verify_password
from ...session import create_session, delete_session
from ...settings import get_setting

log = logging.getLogger(__name__)

router = APIRouter()

_GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"


def _is_registration_enabled() -> bool:
    """Check if self-registration is enabled via system setting."""
    return get_setting(DEFAULT_CUSTOMER_ID, "allow_self_registration") == "true"


@router.get("/login")
async def login_page(request: Request):
    # Already authenticated? Redirect to dashboard.
    user = getattr(request.state, "user", None)
    if user:
        return RedirectResponse("/", status_code=302)

    error = request.query_params.get("error")
    templates = request.app.state.templates
    return templates.TemplateResponse(request, "login.html", {
        "error": error,
        "google_oauth_enabled": bool(config.GOOGLE_OAUTH_CLIENT_ID),
        "registration_enabled": _is_registration_enabled(),
    })


@router.post("/login")
async def login_submit(request: Request):
    templates = request.app.state.templates
    form = await request.form()
    email = form.get("email", "").strip()
    password = form.get("password", "")

    error_msg = "Invalid email or password"

    user = get_user_by_email(email)
    if not user:
        return templates.TemplateResponse(
            request, "login.html", {"error": error_msg, "google_oauth_enabled": bool(config.GOOGLE_OAUTH_CLIENT_ID)}, status_code=401,
        )

    if not user.get("password_hash"):
        return templates.TemplateResponse(
            request, "login.html", {"error": error_msg, "google_oauth_enabled": bool(config.GOOGLE_OAUTH_CLIENT_ID)}, status_code=401,
        )

    if not verify_password(password, user["password_hash"]):
        return templates.TemplateResponse(
            request, "login.html", {"error": error_msg, "google_oauth_enabled": bool(config.GOOGLE_OAUTH_CLIENT_ID)}, status_code=401,
        )

    # Create session
    ip = request.client.host if request.client else ""
    ua = request.headers.get("user-agent", "")
    session = create_session(
        user["id"], user["customer_id"],
        ttl_hours=config.SESSION_TTL_HOURS,
        ip_address=ip,
        user_agent=ua,
    )

    response = RedirectResponse("/", status_code=303)
    response.set_cookie(
        "crm_session",
        session["id"],
        httponly=True,
        samesite="lax",
        max_age=config.SESSION_TTL_HOURS * 3600,
    )
    return response


@router.get("/register")
async def register_page(request: Request):
    if not _is_registration_enabled():
        return RedirectResponse("/login?error=Registration+is+not+enabled", status_code=302)

    user = getattr(request.state, "user", None)
    if user:
        return RedirectResponse("/", status_code=302)

    error = request.query_params.get("error")
    templates = request.app.state.templates
    return templates.TemplateResponse(request, "register.html", {
        "error": error,
        "google_oauth_enabled": bool(config.GOOGLE_OAUTH_CLIENT_ID),
    })


@router.post("/register")
async def register_submit(request: Request):
    if not _is_registration_enabled():
        return RedirectResponse("/login", status_code=302)

    templates = request.app.state.templates
    form = await request.form()
    email = form.get("email", "").strip()
    name = form.get("name", "").strip()
    password = form.get("password", "")
    confirm_password = form.get("confirm_password", "")

    def _error(msg):
        return templates.TemplateResponse(
            request, "register.html",
            {"error": msg, "google_oauth_enabled": bool(config.GOOGLE_OAUTH_CLIENT_ID)},
            status_code=400,
        )

    if not email or not name:
        return _error("Name and email are required")
    if len(password) < 8:
        return _error("Password must be at least 8 characters")
    if password != confirm_password:
        return _error("Passwords do not match")

    try:
        user = create_user(DEFAULT_CUSTOMER_ID, email, name, role="user", password=password)
    except ValueError:
        return _error("An account with this email already exists")

    # Auto-login: create session and redirect to dashboard
    ip = request.client.host if request.client else ""
    ua = request.headers.get("user-agent", "")
    session = create_session(
        user["id"], user["customer_id"],
        ttl_hours=config.SESSION_TTL_HOURS,
        ip_address=ip,
        user_agent=ua,
    )

    response = RedirectResponse("/", status_code=303)
    response.set_cookie(
        "crm_session",
        session["id"],
        httponly=True,
        samesite="lax",
        max_age=config.SESSION_TTL_HOURS * 3600,
    )
    return response


@router.post("/logout")
async def logout(request: Request):
    session_id = request.cookies.get("crm_session")
    if session_id:
        delete_session(session_id)

    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie("crm_session")
    return response


# ---------------------------------------------------------------------------
# Google OAuth
# ---------------------------------------------------------------------------

def _build_redirect_uri(request: Request) -> str:
    """Derive the OAuth callback URL from the current request."""
    base = str(request.base_url).rstrip("/")
    return f"{base}/auth/google/callback"


@router.get("/auth/google")
async def google_auth_initiate(request: Request):
    if not config.GOOGLE_OAUTH_CLIENT_ID:
        return RedirectResponse("/login?error=Google+sign-in+not+configured", status_code=302)

    state = str(uuid.uuid4())
    params = {
        "client_id": config.GOOGLE_OAUTH_CLIENT_ID,
        "redirect_uri": _build_redirect_uri(request),
        "scope": "openid email profile",
        "response_type": "code",
        "state": state,
        "prompt": "select_account",
    }
    url = f"{_GOOGLE_AUTH_URL}?{urlencode(params)}"

    response = RedirectResponse(url, status_code=302)
    response.set_cookie(
        "oauth_state", state,
        httponly=True, samesite="lax", max_age=600,
    )
    return response


@router.get("/auth/google/callback")
async def google_auth_callback(request: Request):
    login_redirect = "/login"

    # Check for error from Google
    error = request.query_params.get("error")
    if error:
        log.warning("Google OAuth error: %s", error)
        return RedirectResponse(f"{login_redirect}?error=Google+sign-in+cancelled", status_code=302)

    # Verify state matches cookie (CSRF protection)
    state = request.query_params.get("state", "")
    cookie_state = request.cookies.get("oauth_state", "")
    if not state or state != cookie_state:
        return RedirectResponse(f"{login_redirect}?error=Invalid+OAuth+state", status_code=302)

    code = request.query_params.get("code", "")
    if not code:
        return RedirectResponse(f"{login_redirect}?error=No+authorization+code", status_code=302)

    # Exchange code for tokens
    redirect_uri = _build_redirect_uri(request)
    try:
        async with httpx.AsyncClient() as client:
            token_resp = await client.post(_GOOGLE_TOKEN_URL, data={
                "code": code,
                "client_id": config.GOOGLE_OAUTH_CLIENT_ID,
                "client_secret": config.GOOGLE_OAUTH_CLIENT_SECRET,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            })
        token_resp.raise_for_status()
        token_data = token_resp.json()
    except Exception:
        log.exception("Google token exchange failed")
        return RedirectResponse(f"{login_redirect}?error=Google+sign-in+failed", status_code=302)

    # Verify and decode the ID token
    raw_id_token = token_data.get("id_token", "")
    if not raw_id_token:
        return RedirectResponse(f"{login_redirect}?error=No+ID+token+from+Google", status_code=302)

    try:
        idinfo = google_id_token.verify_oauth2_token(
            raw_id_token,
            google_requests.Request(),
            config.GOOGLE_OAUTH_CLIENT_ID,
        )
    except Exception:
        log.exception("Google ID token verification failed")
        return RedirectResponse(f"{login_redirect}?error=Google+token+verification+failed", status_code=302)

    google_sub = idinfo.get("sub", "")
    google_email = idinfo.get("email", "")

    if not google_sub or not google_email:
        return RedirectResponse(f"{login_redirect}?error=Incomplete+Google+profile", status_code=302)

    # --- Add-account flow (connect a Google account as provider) ---
    oauth_purpose = request.cookies.get("oauth_purpose", "")
    if oauth_purpose == "add-account":
        return await _handle_add_account(request, token_data, google_email)

    # Look up user: first by google_sub, then by email
    user = get_user_by_google_sub(google_sub)
    linked = False
    if not user:
        user = get_user_by_email(google_email)
        if user:
            # Link Google sub to existing user on first Google login
            set_google_sub(user["id"], google_sub)
            linked = True

    if not user:
        return RedirectResponse(
            f"{login_redirect}?error=No+account+found+for+this+email",
            status_code=302,
        )

    # Create session
    ip = request.client.host if request.client else ""
    ua = request.headers.get("user-agent", "")
    session = create_session(
        user["id"], user["customer_id"],
        ttl_hours=config.SESSION_TTL_HOURS,
        ip_address=ip,
        user_agent=ua,
    )

    response = RedirectResponse("/", status_code=302)
    response.set_cookie(
        "crm_session",
        session["id"],
        httponly=True,
        samesite="lax",
        max_age=config.SESSION_TTL_HOURS * 3600,
    )
    response.delete_cookie("oauth_state")
    return response


async def _handle_add_account(
    request: Request, token_data: dict, google_email: str,
) -> RedirectResponse:
    """Handle the OAuth callback when purpose is add-account."""
    accounts_url = "/settings/accounts"

    user = getattr(request.state, "user", None)
    if not user:
        return RedirectResponse(
            "/login?error=Must+be+logged+in+to+add+account", status_code=302,
        )

    cid = user["customer_id"]
    uid = user["id"]
    now = datetime.now(timezone.utc).isoformat()

    # Check for duplicate provider account
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT id FROM provider_accounts WHERE provider = 'gmail' AND email_address = ?",
            (google_email,),
        ).fetchone()

    if existing:
        response = RedirectResponse(
            f"{accounts_url}?error=Account+{google_email}+is+already+connected",
            status_code=302,
        )
        response.delete_cookie("oauth_state")
        response.delete_cookie("oauth_purpose")
        return response

    # Save token file
    token_path = config.token_path_for_account(google_email)
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_json = {
        "token": token_data.get("access_token"),
        "refresh_token": token_data.get("refresh_token"),
        "token_uri": "https://oauth2.googleapis.com/token",
        "client_id": config.GOOGLE_OAUTH_CLIENT_ID,
        "client_secret": config.GOOGLE_OAUTH_CLIENT_SECRET,
        "scopes": config.GOOGLE_SCOPES,
    }
    token_path.write_text(json.dumps(token_json))

    # Insert provider_accounts row
    account_id = str(uuid.uuid4())
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO provider_accounts
               (id, customer_id, provider, account_type, email_address,
                auth_token_path, is_active, created_at, updated_at)
               VALUES (?, ?, 'gmail', 'email', ?, ?, 1, ?, ?)""",
            (account_id, cid, google_email, str(token_path), now, now),
        )
        # Link to current user
        conn.execute(
            """INSERT INTO user_provider_accounts
               (id, user_id, account_id, role, created_at)
               VALUES (?, ?, ?, 'owner', ?)""",
            (str(uuid.uuid4()), uid, account_id, now),
        )

    response = RedirectResponse(f"{accounts_url}?saved=1", status_code=302)
    response.delete_cookie("oauth_state")
    response.delete_cookie("oauth_purpose")
    return response
