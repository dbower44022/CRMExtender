"""Login / logout routes."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from starlette.responses import HTMLResponse

from ... import config
from ...hierarchy import get_user_by_email
from ...passwords import verify_password
from ...session import create_session, delete_session

router = APIRouter()


@router.get("/login")
async def login_page(request: Request):
    # Already authenticated? Redirect to dashboard.
    user = getattr(request.state, "user", None)
    if user:
        return RedirectResponse("/", status_code=302)

    templates = request.app.state.templates
    return templates.TemplateResponse(request, "login.html", {"error": None})


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
            request, "login.html", {"error": error_msg}, status_code=401,
        )

    if not user.get("password_hash"):
        return templates.TemplateResponse(
            request, "login.html", {"error": error_msg}, status_code=401,
        )

    if not verify_password(password, user["password_hash"]):
        return templates.TemplateResponse(
            request, "login.html", {"error": error_msg}, status_code=401,
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


@router.post("/logout")
async def logout(request: Request):
    session_id = request.cookies.get("crm_session")
    if session_id:
        delete_session(session_id)

    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie("crm_session")
    return response
