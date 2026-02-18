"""Settings routes: profile, system settings, user management, accounts, calendars."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from urllib.parse import urlencode

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from ..dependencies import require_admin
from ... import config
from ...database import get_connection
from ...hierarchy import (
    create_user,
    get_user_by_id,
    list_users,
    set_user_password,
    update_user,
)
from ...passwords import verify_password
from ...session import delete_user_sessions
from ...settings import get_setting, set_setting
from ...sync import EMAIL_HISTORY_OPTIONS

log = logging.getLogger(__name__)

router = APIRouter()

COMMON_COUNTRIES = [
    ("US", "United States"),
    ("CA", "Canada"),
    ("GB", "United Kingdom"),
    ("AU", "Australia"),
    ("DE", "Germany"),
    ("FR", "France"),
    ("JP", "Japan"),
    ("BR", "Brazil"),
    ("IN", "India"),
    ("MX", "Mexico"),
    ("NZ", "New Zealand"),
    ("ZA", "South Africa"),
    ("IT", "Italy"),
    ("ES", "Spain"),
    ("NL", "Netherlands"),
    ("SE", "Sweden"),
    ("CH", "Switzerland"),
    ("IE", "Ireland"),
    ("SG", "Singapore"),
    ("HK", "Hong Kong"),
    ("KR", "South Korea"),
    ("CN", "China"),
    ("AE", "United Arab Emirates"),
    ("AR", "Argentina"),
]

COMMON_TIMEZONES = [
    "UTC",
    "US/Eastern", "US/Central", "US/Mountain", "US/Pacific",
    "US/Alaska", "US/Hawaii",
    "Canada/Atlantic", "Canada/Eastern", "Canada/Central",
    "Canada/Mountain", "Canada/Pacific",
    "Europe/London", "Europe/Paris", "Europe/Berlin", "Europe/Rome",
    "Europe/Madrid", "Europe/Amsterdam", "Europe/Stockholm", "Europe/Moscow",
    "Asia/Tokyo", "Asia/Shanghai", "Asia/Hong_Kong", "Asia/Singapore",
    "Asia/Kolkata", "Asia/Dubai", "Asia/Seoul",
    "Australia/Sydney", "Australia/Melbourne", "Australia/Perth",
    "Pacific/Auckland",
    "America/Sao_Paulo", "America/Mexico_City", "America/Argentina/Buenos_Aires",
    "Africa/Johannesburg", "Africa/Cairo",
]


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------

@router.get("/settings/profile")
async def profile_page(request: Request):
    templates = request.app.state.templates
    user = request.state.user
    cid = user["customer_id"]
    uid = user["id"]

    tz = get_setting(cid, "timezone", user_id=uid) or "UTC"
    start_of_week = get_setting(cid, "start_of_week", user_id=uid) or "monday"
    date_format = get_setting(cid, "date_format", user_id=uid) or "ISO"

    return templates.TemplateResponse(request, "settings/profile.html", {
        "active_nav": "settings",
        "settings_tab": "profile",
        "timezones": COMMON_TIMEZONES,
        "current_tz": tz,
        "start_of_week": start_of_week,
        "date_format": date_format,
        "saved": request.query_params.get("saved"),
        "pw_changed": request.query_params.get("pw_changed"),
        "error": request.query_params.get("error"),
    })


@router.post("/settings/profile")
async def profile_save(request: Request):
    user = request.state.user
    cid = user["customer_id"]
    uid = user["id"]
    form = await request.form()

    name = form.get("name", "").strip()
    if name:
        update_user(uid, name=name)

    tz = form.get("timezone", "UTC")
    set_setting(cid, "timezone", tz, scope="user", user_id=uid)

    sow = form.get("start_of_week", "monday")
    set_setting(cid, "start_of_week", sow, scope="user", user_id=uid)

    df = form.get("date_format", "ISO")
    set_setting(cid, "date_format", df, scope="user", user_id=uid)

    return RedirectResponse("/settings/profile?saved=1", status_code=303)


@router.post("/settings/profile/password")
async def profile_password(request: Request):
    user = request.state.user
    form = await request.form()

    current_pw = form.get("current_password", "")
    new_pw = form.get("new_password", "")
    confirm_pw = form.get("confirm_password", "")

    if new_pw != confirm_pw:
        return RedirectResponse(
            "/settings/profile?error=Passwords+do+not+match", status_code=303,
        )

    if len(new_pw) < 8:
        return RedirectResponse(
            "/settings/profile?error=Password+must+be+at+least+8+characters",
            status_code=303,
        )

    # Verify current password (unless no password set yet)
    if user.get("password_hash"):
        if not verify_password(current_pw, user["password_hash"]):
            return RedirectResponse(
                "/settings/profile?error=Current+password+is+incorrect",
                status_code=303,
            )

    set_user_password(user["id"], new_pw)
    return RedirectResponse("/settings/profile?pw_changed=1", status_code=303)


# ---------------------------------------------------------------------------
# System Settings (admin only)
# ---------------------------------------------------------------------------

@router.get("/settings/system")
async def system_page(request: Request):
    require_admin(request)
    templates = request.app.state.templates
    user = request.state.user
    cid = user["customer_id"]

    company_name = get_setting(cid, "company_name") or ""
    default_tz = get_setting(cid, "default_timezone") or "UTC"
    sync_enabled = get_setting(cid, "sync_enabled") or "true"
    default_phone_country = get_setting(cid, "default_phone_country") or "US"
    allow_self_registration = get_setting(cid, "allow_self_registration") or "false"
    email_history_window = get_setting(cid, "email_history_window") or "90d"

    return templates.TemplateResponse(request, "settings/system.html", {
        "active_nav": "settings",
        "settings_tab": "system",
        "timezones": COMMON_TIMEZONES,
        "countries": COMMON_COUNTRIES,
        "company_name": company_name,
        "default_tz": default_tz,
        "sync_enabled": sync_enabled,
        "default_phone_country": default_phone_country,
        "allow_self_registration": allow_self_registration,
        "email_history_window": email_history_window,
        "email_history_options": EMAIL_HISTORY_OPTIONS,
        "saved": request.query_params.get("saved"),
    })


@router.post("/settings/system")
async def system_save(request: Request):
    require_admin(request)
    user = request.state.user
    cid = user["customer_id"]
    form = await request.form()

    company_name = form.get("company_name", "").strip()
    set_setting(cid, "company_name", company_name, scope="system")

    default_tz = form.get("default_timezone", "UTC")
    set_setting(cid, "default_timezone", default_tz, scope="system")

    sync_enabled = "true" if form.get("sync_enabled") else "false"
    set_setting(cid, "sync_enabled", sync_enabled, scope="system")

    allow_self_registration = "true" if form.get("allow_self_registration") else "false"
    set_setting(cid, "allow_self_registration", allow_self_registration, scope="system")

    default_phone_country = form.get("default_phone_country", "US")
    set_setting(cid, "default_phone_country", default_phone_country, scope="system")

    email_history_window = form.get("email_history_window", "90d")
    set_setting(cid, "email_history_window", email_history_window, scope="system")

    return RedirectResponse("/settings/system?saved=1", status_code=303)


# ---------------------------------------------------------------------------
# User Management (admin only)
# ---------------------------------------------------------------------------

@router.get("/settings/users")
async def users_list(request: Request):
    require_admin(request)
    templates = request.app.state.templates
    user = request.state.user
    cid = user["customer_id"]

    users = list_users(cid)
    return templates.TemplateResponse(request, "settings/users.html", {
        "active_nav": "settings",
        "settings_tab": "users",
        "users_list": users,
    })


@router.get("/settings/users/new")
async def user_new_form(request: Request):
    require_admin(request)
    templates = request.app.state.templates
    return templates.TemplateResponse(request, "settings/user_form.html", {
        "active_nav": "settings",
        "settings_tab": "users",
        "mode": "create",
        "edit_user": {},
        "error": request.query_params.get("error"),
    })


@router.post("/settings/users")
async def user_create(request: Request):
    require_admin(request)
    user = request.state.user
    cid = user["customer_id"]
    form = await request.form()

    email = form.get("email", "").strip()
    name = form.get("name", "").strip()
    role = form.get("role", "user")
    password = form.get("password", "")

    if not email:
        return RedirectResponse(
            "/settings/users/new?error=Email+is+required", status_code=303,
        )
    if password and len(password) < 8:
        return RedirectResponse(
            "/settings/users/new?error=Password+must+be+at+least+8+characters",
            status_code=303,
        )

    try:
        create_user(cid, email, name, role, password=password or None)
    except ValueError as exc:
        return RedirectResponse(
            f"/settings/users/new?error={str(exc)}", status_code=303,
        )

    return RedirectResponse("/settings/users", status_code=303)


@router.get("/settings/users/{user_id}/edit")
async def user_edit_form(request: Request, user_id: str):
    require_admin(request)
    templates = request.app.state.templates

    edit_user = get_user_by_id(user_id)
    if not edit_user:
        return RedirectResponse("/settings/users", status_code=303)

    return templates.TemplateResponse(request, "settings/user_form.html", {
        "active_nav": "settings",
        "settings_tab": "users",
        "mode": "edit",
        "edit_user": edit_user,
        "error": request.query_params.get("error"),
    })


@router.post("/settings/users/{user_id}/edit")
async def user_edit_save(request: Request, user_id: str):
    require_admin(request)
    form = await request.form()

    name = form.get("name", "").strip()
    role = form.get("role", "user")

    update_user(user_id, name=name, role=role)
    return RedirectResponse("/settings/users", status_code=303)


@router.post("/settings/users/{user_id}/password")
async def user_set_password(request: Request, user_id: str):
    require_admin(request)
    form = await request.form()

    new_pw = form.get("new_password", "")
    confirm_pw = form.get("confirm_password", "")

    if new_pw != confirm_pw:
        return RedirectResponse(
            f"/settings/users/{user_id}/edit?error=Passwords+do+not+match",
            status_code=303,
        )
    if len(new_pw) < 8:
        return RedirectResponse(
            f"/settings/users/{user_id}/edit?error=Password+must+be+at+least+8+characters",
            status_code=303,
        )

    set_user_password(user_id, new_pw)
    return RedirectResponse("/settings/users", status_code=303)


@router.post("/settings/users/{user_id}/toggle-active")
async def user_toggle_active(request: Request, user_id: str):
    require_admin(request)
    current_user = request.state.user

    if user_id == current_user["id"]:
        return RedirectResponse(
            "/settings/users?error=Cannot+deactivate+yourself", status_code=303,
        )

    target = get_user_by_id(user_id)
    if not target:
        return RedirectResponse("/settings/users", status_code=303)

    new_active = 0 if target["is_active"] else 1
    update_user(user_id, is_active=new_active)

    if not new_active:
        delete_user_sessions(user_id)

    return RedirectResponse("/settings/users", status_code=303)


# ---------------------------------------------------------------------------
# Provider Accounts (all users)
# ---------------------------------------------------------------------------

_GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"


@router.get("/settings/accounts")
async def accounts_page(request: Request):
    templates = request.app.state.templates
    user = request.state.user
    uid = user["id"]
    cid = user["customer_id"]

    with get_connection() as conn:
        rows = conn.execute(
            """SELECT pa.* FROM provider_accounts pa
               JOIN user_provider_accounts upa ON upa.account_id = pa.id
               WHERE upa.user_id = ?
               ORDER BY pa.created_at""",
            (uid,),
        ).fetchall()
        accounts = [dict(r) for r in rows]

    # Fallback: if no user_provider_accounts, use customer's accounts
    if not accounts:
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM provider_accounts WHERE customer_id = ? ORDER BY created_at",
                (cid,),
            ).fetchall()
            accounts = [dict(r) for r in rows]

    return templates.TemplateResponse(request, "settings/accounts.html", {
        "active_nav": "settings",
        "settings_tab": "accounts",
        "accounts": accounts,
        "google_oauth_configured": bool(config.GOOGLE_OAUTH_CLIENT_ID),
        "saved": request.query_params.get("saved"),
        "error": request.query_params.get("error"),
    })


@router.get("/settings/accounts/connect")
async def accounts_connect(request: Request):
    if not config.GOOGLE_OAUTH_CLIENT_ID:
        return RedirectResponse(
            "/settings/accounts?error=Google+OAuth+not+configured", status_code=302,
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
    return response


@router.get("/settings/accounts/{account_id}/edit")
async def account_edit_form(request: Request, account_id: str):
    templates = request.app.state.templates
    user = request.state.user

    with get_connection() as conn:
        account = conn.execute(
            "SELECT * FROM provider_accounts WHERE id = ?",
            (account_id,),
        ).fetchone()

    if not account:
        return RedirectResponse("/settings/accounts", status_code=303)

    return templates.TemplateResponse(request, "settings/account_edit.html", {
        "active_nav": "settings",
        "settings_tab": "accounts",
        "account": dict(account),
        "error": request.query_params.get("error"),
    })


@router.post("/settings/accounts/{account_id}/edit")
async def account_edit_save(request: Request, account_id: str):
    form = await request.form()
    display_name = form.get("display_name", "").strip()
    now = datetime.now(timezone.utc).isoformat()

    with get_connection() as conn:
        conn.execute(
            "UPDATE provider_accounts SET display_name = ?, updated_at = ? WHERE id = ?",
            (display_name or None, now, account_id),
        )

    return RedirectResponse("/settings/accounts?saved=1", status_code=303)


@router.post("/settings/accounts/{account_id}/toggle-active")
async def account_toggle_active(request: Request, account_id: str):
    user = request.state.user
    uid = user["id"]
    now = datetime.now(timezone.utc).isoformat()

    with get_connection() as conn:
        # Verify account belongs to user (or is a customer account)
        account = conn.execute(
            "SELECT * FROM provider_accounts WHERE id = ?",
            (account_id,),
        ).fetchone()
        if not account:
            return RedirectResponse("/settings/accounts", status_code=303)

        new_active = 0 if account["is_active"] else 1
        conn.execute(
            "UPDATE provider_accounts SET is_active = ?, updated_at = ? WHERE id = ?",
            (new_active, now, account_id),
        )

    return RedirectResponse("/settings/accounts?saved=1", status_code=303)


# ---------------------------------------------------------------------------
# Calendar Settings
# ---------------------------------------------------------------------------

@router.get("/settings/calendars")
async def calendars_page(request: Request):
    templates = request.app.state.templates
    user = request.state.user
    uid = user["id"]
    cid = user["customer_id"]

    # Get user's Google provider accounts
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT pa.* FROM provider_accounts pa
               JOIN user_provider_accounts upa ON upa.account_id = pa.id
               WHERE upa.user_id = ? AND pa.provider = 'gmail' AND pa.is_active = 1
               ORDER BY pa.created_at""",
            (uid,),
        ).fetchall()

    accounts = []
    for row in rows:
        account = dict(row)
        cal_key = f"cal_sync_calendars_{account['id']}"
        cal_json = get_setting(cid, cal_key, user_id=uid)
        try:
            account["selected_calendars"] = json.loads(cal_json) if cal_json else []
        except (json.JSONDecodeError, TypeError):
            account["selected_calendars"] = []
        accounts.append(account)

    # Fallback: if no user_provider_accounts, use customer's accounts
    if not accounts:
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM provider_accounts WHERE customer_id = ? AND provider = 'gmail' AND is_active = 1 ORDER BY created_at",
                (cid,),
            ).fetchall()
        for row in rows:
            account = dict(row)
            cal_key = f"cal_sync_calendars_{account['id']}"
            cal_json = get_setting(cid, cal_key, user_id=uid)
            try:
                account["selected_calendars"] = json.loads(cal_json) if cal_json else []
            except (json.JSONDecodeError, TypeError):
                account["selected_calendars"] = []
            accounts.append(account)

    return templates.TemplateResponse(request, "settings/calendars.html", {
        "active_nav": "settings",
        "settings_tab": "calendars",
        "accounts": accounts,
        "saved": request.query_params.get("saved"),
        "error": request.query_params.get("error"),
    })


@router.post("/settings/calendars/{account_id}/fetch", response_class=HTMLResponse)
async def calendars_fetch(request: Request, account_id: str):
    """HTMX partial: load available calendars for an account."""
    from ...auth import get_credentials_for_account
    from ...calendar_client import CalendarScopeError, list_calendars

    templates = request.app.state.templates
    user = request.state.user
    uid = user["id"]
    cid = user["customer_id"]

    with get_connection() as conn:
        account = conn.execute(
            "SELECT * FROM provider_accounts WHERE id = ?",
            (account_id,),
        ).fetchone()

    if not account:
        return HTMLResponse("<p>Account not found.</p>")

    # Load existing selections
    cal_key = f"cal_sync_calendars_{account_id}"
    cal_json = get_setting(cid, cal_key, user_id=uid)
    try:
        selected = set(json.loads(cal_json)) if cal_json else set()
    except (json.JSONDecodeError, TypeError):
        selected = set()

    from pathlib import Path
    token_path = Path(account["auth_token_path"])
    try:
        creds = get_credentials_for_account(token_path)
        calendars = list_calendars(creds)
    except CalendarScopeError as exc:
        return templates.TemplateResponse(request, "settings/_calendar_list.html", {
            "account_id": account_id,
            "calendars": [],
            "selected": selected,
            "error": str(exc),
        })
    except Exception as exc:
        log.warning("Failed to fetch calendars for %s: %s", account_id, exc)
        return templates.TemplateResponse(request, "settings/_calendar_list.html", {
            "account_id": account_id,
            "calendars": [],
            "selected": selected,
            "error": f"Failed to load calendars: {exc}",
        })

    return templates.TemplateResponse(request, "settings/_calendar_list.html", {
        "account_id": account_id,
        "calendars": calendars,
        "selected": selected,
    })


@router.post("/settings/calendars/{account_id}/save")
async def calendars_save(request: Request, account_id: str):
    """Save selected calendar IDs for an account."""
    user = request.state.user
    uid = user["id"]
    cid = user["customer_id"]
    form = await request.form()

    calendar_ids = form.getlist("calendar_ids")
    cal_key = f"cal_sync_calendars_{account_id}"
    set_setting(cid, cal_key, json.dumps(calendar_ids), scope="user", user_id=uid)

    return RedirectResponse("/settings/calendars?saved=1", status_code=303)
