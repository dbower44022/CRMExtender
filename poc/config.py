"""Configuration loading from environment variables and defaults."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

# Load .env from project root
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_PROJECT_ROOT / ".env")


def _env(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


# Paths
CREDENTIALS_DIR = _PROJECT_ROOT / "credentials"
CLIENT_SECRET_PATH = CREDENTIALS_DIR / "client_secret.json"
TOKEN_PATH = CREDENTIALS_DIR / "token.json"


def token_path_for_account(email: str) -> Path:
    """Return the token file path for a specific account."""
    safe = email.replace("@", "_at_").replace(".", "_")
    return CREDENTIALS_DIR / f"token_{safe}.json"


# Google API scopes
GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/contacts.readonly",
    "https://www.googleapis.com/auth/calendar.readonly",
]

# Calendar sync
CALENDAR_SYNC_DAYS = 90

# Gmail query defaults
GMAIL_QUERY = _env("POC_GMAIL_QUERY", "newer_than:7d")
GMAIL_MAX_THREADS = int(_env("POC_GMAIL_MAX_THREADS", "50"))

# Anthropic
ANTHROPIC_API_KEY = _env("ANTHROPIC_API_KEY")
CLAUDE_MODEL = _env("POC_CLAUDE_MODEL", "claude-sonnet-4-20250514")

# Conversation target — keep fetching batches until this many pass triage
TARGET_CONVERSATIONS = int(_env("POC_TARGET_CONVERSATIONS", "5"))

# Rate limiting (requests per second)
GMAIL_RATE_LIMIT = float(_env("POC_GMAIL_RATE_LIMIT", "5"))
CLAUDE_RATE_LIMIT = float(_env("POC_CLAUDE_RATE_LIMIT", "2"))

# Database
DB_PATH = Path(_env("POC_DB_PATH", "") or str(_PROJECT_ROOT / "data" / "crm_extender.db"))

# Timezone for display (all storage remains UTC)
_tz_name = _env("CRM_TIMEZONE", "UTC")
try:
    ZoneInfo(_tz_name)
    CRM_TIMEZONE = _tz_name
except (KeyError, Exception):
    logging.getLogger(__name__).warning(
        "Invalid CRM_TIMEZONE %r, falling back to UTC", _tz_name,
    )
    CRM_TIMEZONE = "UTC"

# Authentication
CRM_AUTH_ENABLED = _env("CRM_AUTH_ENABLED", "true").lower() in ("true", "1", "yes")
SESSION_SECRET_KEY = _env("SESSION_SECRET_KEY", "change-me-in-production")
SESSION_TTL_HOURS = int(_env("SESSION_TTL_HOURS", "720"))

# Google OAuth (for web login)
def _load_google_oauth_config() -> tuple[str, str]:
    """Load client_id and client_secret from client_secret.json."""
    if CLIENT_SECRET_PATH.exists():
        import json
        data = json.loads(CLIENT_SECRET_PATH.read_text())
        installed = data.get("installed", {})
        return installed.get("client_id", ""), installed.get("client_secret", "")
    return "", ""

GOOGLE_OAUTH_CLIENT_ID, GOOGLE_OAUTH_CLIENT_SECRET = _load_google_oauth_config()

# Summarization
MAX_CONVERSATION_CHARS = int(_env("POC_MAX_CONVERSATION_CHARS", "6000"))

# File uploads (notes attachments)
UPLOAD_DIR = Path(_env("CRM_UPLOAD_DIR", "") or str(_PROJECT_ROOT / "data" / "uploads"))
MAX_UPLOAD_SIZE_MB = int(_env("CRM_MAX_UPLOAD_SIZE_MB", "10"))
ALLOWED_UPLOAD_TYPES = {
    "image/jpeg", "image/png", "image/gif", "image/webp", "image/svg+xml",
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "text/plain", "text/csv",
}
