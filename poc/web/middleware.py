"""Authentication middleware for the CRM Extender web UI."""

from __future__ import annotations

import logging

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import RedirectResponse, Response

from .. import config

log = logging.getLogger(__name__)

# Paths that never require authentication
_PUBLIC_PATHS = ("/login", "/static/")


class AuthMiddleware(BaseHTTPMiddleware):
    """Validate session cookies and populate request.state.user."""

    async def dispatch(self, request: Request, call_next) -> Response:
        if not config.CRM_AUTH_ENABLED:
            return await self._bypass_mode(request, call_next)

        path = request.url.path

        # Static files need no auth at all
        if path.startswith("/static/"):
            request.state.user = None
            request.state.customer_id = None
            return await call_next(request)

        # Try to resolve session from cookie
        from ..session import get_session

        session_id = request.cookies.get("crm_session")
        session = get_session(session_id) if session_id else None

        if session:
            request.state.user = {
                "id": session["user_id"],
                "email": session["email"],
                "name": session["user_name"],
                "role": session["role"],
                "customer_id": session["customer_id"],
            }
            request.state.customer_id = session["customer_id"]
        else:
            request.state.user = None
            request.state.customer_id = None

        # Public paths (login) pass through even without auth
        if path == "/login":
            return await call_next(request)

        # Protected paths require valid session
        if not session:
            response = RedirectResponse("/login", status_code=302)
            if session_id:
                response.delete_cookie("crm_session")
            return response

        return await call_next(request)

    async def _bypass_mode(self, request: Request, call_next) -> Response:
        """CRM_AUTH_ENABLED=false — inject first active user without login."""
        from ..hierarchy import get_current_user

        user = get_current_user()
        if user:
            request.state.user = {
                "id": user["id"],
                "email": user["email"],
                "name": user.get("name") or "",
                "role": user.get("role", "admin"),
                "customer_id": user.get("customer_id", ""),
            }
            request.state.customer_id = user.get("customer_id", "")
        else:
            # Synthetic admin for empty DB (e.g. tests)
            request.state.user = {
                "id": "synthetic-admin",
                "email": "admin@localhost",
                "name": "Admin",
                "role": "admin",
                "customer_id": "",
            }
            request.state.customer_id = ""

        return await call_next(request)
