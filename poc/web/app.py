"""FastAPI application factory for the CRM Extender web UI."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

import logging

from .. import config
from ..database import init_db

_HERE = Path(__file__).resolve().parent
log = logging.getLogger(__name__)


class AuthTemplates(Jinja2Templates):
    """Jinja2Templates subclass that auto-injects request.state.user."""

    def TemplateResponse(self, request, name, context=None, **kwargs):
        if context is None:
            context = {}
        context.setdefault("request", request)
        user = getattr(getattr(request, "state", None), "user", None)
        context.setdefault("user", user)
        # Per-user timezone override
        if user and user.get("customer_id") and user.get("id"):
            from ..settings import get_setting
            tz = get_setting(user["customer_id"], "timezone", user_id=user["id"])
            if tz:
                context["CRM_TIMEZONE"] = tz
        return super().TemplateResponse(request, name, context, **kwargs)


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        init_db()
    except Exception as exc:
        log.warning("init_db had issues (may need migration): %s", exc)
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="CRM Extender", lifespan=lifespan)

    app.mount(
        "/static",
        StaticFiles(directory=_HERE / "static"),
        name="static",
    )

    templates = AuthTemplates(directory=_HERE / "templates")

    from .filters import register_filters
    register_filters(templates)
    templates.env.globals["CRM_TIMEZONE"] = config.CRM_TIMEZONE

    app.state.templates = templates

    # Auth middleware
    from .middleware import AuthMiddleware
    app.add_middleware(AuthMiddleware)

    from .routes import (
        auth_routes,
        companies,
        contacts,
        conversations,
        dashboard,
        events,
        projects,
        relationships,
        settings_routes,
    )

    app.include_router(auth_routes.router)
    app.include_router(dashboard.router)
    app.include_router(conversations.router, prefix="/conversations")
    app.include_router(contacts.router, prefix="/contacts")
    app.include_router(companies.router, prefix="/companies")
    app.include_router(projects.router, prefix="/projects")
    app.include_router(relationships.router, prefix="/relationships")
    app.include_router(events.router, prefix="/events")
    app.include_router(settings_routes.router)

    return app
