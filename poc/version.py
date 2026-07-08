"""Application version — the git commit the running code is on.

The commit SHA is the release identity: each push is CI-verified, so
matching the SHA shown here against the pushed commit confirms you are
running the exact released version. Read at runtime from the working
tree (cached); falls back to a committed VERSION file, then "unknown"
when neither git nor the file is available (e.g. a stripped container).
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


@lru_cache(maxsize=1)
def get_version() -> dict:
    """Return {sha, short_sha, committed_at, message, source}."""
    sha = _git("rev-parse", "HEAD")
    if sha:
        return {
            "sha": sha,
            "short_sha": sha[:7],
            "committed_at": _git("log", "-1", "--format=%cI"),
            "message": _git("log", "-1", "--format=%s"),
            "source": "git",
        }

    version_file = _ROOT / "VERSION"
    if version_file.exists():
        text = version_file.read_text().strip()
        return {
            "sha": text,
            "short_sha": text[:7],
            "committed_at": None,
            "message": None,
            "source": "file",
        }

    return {
        "sha": "unknown",
        "short_sha": "unknown",
        "committed_at": None,
        "message": None,
        "source": "unknown",
    }
