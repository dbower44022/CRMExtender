"""FastAPI dependencies for authentication."""

from __future__ import annotations

from fastapi import HTTPException, Request


def get_current_user(request: Request) -> dict:
    """Return the authenticated user or raise 401."""
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


def require_admin(request: Request) -> dict:
    """Return the authenticated user if admin, else raise 403."""
    user = get_current_user(request)
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user
