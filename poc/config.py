"""Configuration loading from environment variables and defaults."""

from __future__ import annotations

import os
from pathlib import Path

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

# Google API scopes
GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/contacts.readonly",
]

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

# Summarization
MAX_CONVERSATION_CHARS = int(_env("POC_MAX_CONVERSATION_CHARS", "6000"))
