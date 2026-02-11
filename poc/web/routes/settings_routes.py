"""Settings routes: profile, system settings, user management."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from ..dependencies import require_admin
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

router = APIRouter()

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

    return templates.TemplateResponse(request, "settings/system.html", {
        "active_nav": "settings",
        "settings_tab": "system",
        "timezones": COMMON_TIMEZONES,
        "company_name": company_name,
        "default_tz": default_tz,
        "sync_enabled": sync_enabled,
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
