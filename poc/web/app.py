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

    templates = Jinja2Templates(directory=_HERE / "templates")
    app.state.templates = templates

    from .routes import (
        companies,
        contacts,
        conversations,
        dashboard,
        events,
        projects,
        relationships,
    )

    app.include_router(dashboard.router)
    app.include_router(conversations.router, prefix="/conversations")
    app.include_router(contacts.router, prefix="/contacts")
    app.include_router(companies.router, prefix="/companies")
    app.include_router(projects.router, prefix="/projects")
    app.include_router(relationships.router, prefix="/relationships")
    app.include_router(events.router, prefix="/events")

    return app
