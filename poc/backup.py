"""Database backup: a compact, verified copy of the live file (v10.41).

``make_backup`` snapshots the database with ``VACUUM INTO`` — a consistent
read even while the server is writing — into an archive folder as
``crm_extender.<YYYYmmdd_HHMM>.db``, checks the copy's integrity, and
prunes the folder to the newest ``keep`` copies. The archive lives outside
Dropbox on purpose (10-12-26: a Dropbox-synced live database corrupted).
"""

from __future__ import annotations

import logging
import os
import sqlite3
from datetime import datetime
from pathlib import Path

log = logging.getLogger(__name__)

DEFAULT_ARCHIVE_DIR = Path.home() / "db-archive" / "CRMExtender"
DEFAULT_KEEP = 7
PREFIX = "crm_extender."
SUFFIX = ".db"


class BackupError(RuntimeError):
    """The copy could not be made or did not verify."""


def _stamp(now: datetime | None = None) -> str:
    return (now or datetime.now()).strftime("%Y%m%d_%H%M")


def list_backups(archive_dir: Path) -> list[Path]:
    """Timestamped copies in ``archive_dir``, oldest first. Other files are ignored."""
    out = []
    for p in archive_dir.glob(f"{PREFIX}*{SUFFIX}"):
        core = p.name[len(PREFIX):-len(SUFFIX)]
        if len(core) == 13 and core[8] == "_" and core.replace("_", "").isdigit():
            out.append(p)
    return sorted(out)


def prune(archive_dir: Path, keep: int) -> list[Path]:
    """Delete all but the newest ``keep`` timestamped copies. Returns what was removed."""
    removed: list[Path] = []
    if keep < 1:
        return removed
    for p in list_backups(archive_dir)[:-keep]:
        p.unlink()
        removed.append(p)
    return removed


def make_backup(db_path: Path, archive_dir: Path = DEFAULT_ARCHIVE_DIR, *, keep: int = DEFAULT_KEEP,
                now: datetime | None = None) -> dict:
    """Write a verified copy and prune. Returns ``{"path", "bytes", "removed"}``."""
    db_path = Path(db_path)
    if not db_path.exists():
        raise BackupError(f"database not found: {db_path}")
    archive_dir = Path(archive_dir)
    archive_dir.mkdir(parents=True, exist_ok=True)
    target = archive_dir / f"{PREFIX}{_stamp(now)}{SUFFIX}"
    if target.exists():
        target.unlink()
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=30)
    try:
        conn.execute("VACUUM INTO ?", (str(target),))
    except sqlite3.Error as exc:
        raise BackupError(f"copy failed: {exc}") from exc
    finally:
        conn.close()
    check = sqlite3.connect(f"file:{target}?mode=ro", uri=True)
    try:
        verdict = check.execute("PRAGMA integrity_check").fetchone()[0]
    finally:
        check.close()
    if verdict != "ok":
        target.unlink(missing_ok=True)
        raise BackupError(f"copy failed its integrity check: {verdict}")
    removed = prune(archive_dir, keep)
    size = os.path.getsize(target)
    log.info("Backup written: %s (%d MB); %d old copies removed", target, size // 1_000_000, len(removed))
    return {"path": target, "bytes": size, "removed": removed}
