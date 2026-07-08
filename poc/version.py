"""Application version.

Two identifiers, for two purposes:

- **version** — a human, monotonically increasing release number from the
  ``VERSION`` file at the repo root (e.g. ``10.1``). This is the headline:
  higher = newer, trivial to compare. Bump it on every release (edit
  ``VERSION`` in the same commit).
- **sha** — the git commit the running code is on, for exact forensic
  matching. Read at runtime from the working tree (cached).

Both are shown in Settings → System. ``version`` answers "am I on the
latest?"; ``sha`` answers "is this the exact build you pushed?".
"""

from __future__ import annotations

import subprocess
from functools import lru_cache
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent


def _git(*args: str) -> str | None:
    try:
        out = subprocess.run(
            ["git", "-C", str(_ROOT), *args],
            capture_output=True, text=True, timeout=3,
        )
        if out.returncode == 0:
            return out.stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        pass
    return None


def _read_version_file() -> str:
    version_file = _ROOT / "VERSION"
    try:
        text = version_file.read_text().strip()
        if text:
            return text
    except OSError:
        pass
    return "dev"


@lru_cache(maxsize=1)
def get_version() -> dict:
    """Return {version, sha, short_sha, committed_at, message, sha_source}."""
    version = _read_version_file()
    sha = _git("rev-parse", "HEAD")
    if sha:
        return {
            "version": version,
            "sha": sha,
            "short_sha": sha[:7],
            "committed_at": _git("log", "-1", "--format=%cI"),
            "message": _git("log", "-1", "--format=%s"),
            "sha_source": "git",
        }
    return {
        "version": version,
        "sha": None,
        "short_sha": None,
        "committed_at": None,
        "message": None,
        "sha_source": "unavailable",
    }
