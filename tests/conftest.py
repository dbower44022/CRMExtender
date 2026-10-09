"""Shared pytest configuration.

Speeds up per-test database setup by caching the initialized schema in a
session-scoped template file. init_db() executes the full schema DDL in
autocommit mode (~2s per call, one fsync per statement); copying a
template database brings that to milliseconds. Test modules import
init_db by name, so the patch rebinds that name in every collected test
module as well as poc.database itself, and restores it at session end.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest

import poc.database as _database

_REAL_INIT_DB = _database.init_db


@pytest.fixture(scope="session", autouse=True)
def _template_init_db(tmp_path_factory):
    template = tmp_path_factory.mktemp("schema_template") / "template.db"
    _REAL_INIT_DB(template)

    def fast_init_db(db_path: Path | None = None) -> None:
        # The template only reproduces "fresh file at an explicit path" —
        # fall back to the real initializer for anything else.
        if db_path is None or Path(db_path).exists():
            return _REAL_INIT_DB(db_path)
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(template, db_path)

    patched = [
        mod for mod in list(sys.modules.values())
        if mod is not None and getattr(mod, "init_db", None) is _REAL_INIT_DB
    ]
    for mod in patched:
        mod.init_db = fast_init_db
    yield
    for mod in patched:
        mod.init_db = _REAL_INIT_DB


@pytest.fixture(autouse=True)
def _no_background_scheduler(monkeypatch):
    """The web server starts the per-account sync scheduler in its
    lifespan (MAIL-13). Tests must never spawn it: a TestClient used as a
    context manager would otherwise start timed syncs against the test
    database. Scheduler tests construct SyncScheduler directly."""
    monkeypatch.setattr("poc.config.SCHEDULER_ENABLED", False)


@pytest.fixture(autouse=True)
def _no_network_label_refresh(monkeypatch):
    """The sync orchestrators refresh the mailbox label list from the
    provider before syncing (MAIL-08). That is an HTTP call; tests that
    exercise the orchestrators with mock credentials must not reach the
    network, so the Gmail label listing is stubbed to empty here. A test
    that wants labels patches ``poc.gmail_client.list_labels`` itself."""
    import poc.gmail_client as _gc
    monkeypatch.setattr(_gc, "list_labels", lambda creds, rate_limiter=None: [])
