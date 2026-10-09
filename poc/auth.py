"""Google OAuth 2.0 flow with token persistence."""

from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from . import config
from .database import get_connection
from .gmail_client import get_user_email

log = logging.getLogger(__name__)


#: Scopes that satisfy a required scope without being spelled the same.
_SCOPE_SUPERSETS = {
    "https://www.googleapis.com/auth/gmail.readonly": {
        "https://www.googleapis.com/auth/gmail.modify",
        "https://mail.google.com/",
    },
    "https://www.googleapis.com/auth/gmail.modify": {"https://mail.google.com/"},
    "https://www.googleapis.com/auth/gmail.send": {"https://mail.google.com/"},
}


def token_scopes(token_path: Path) -> list[str]:
    """The scopes recorded in a saved token file ([] if unreadable or absent)."""
    try:
        data = json.loads(Path(token_path).read_text())
    except (OSError, json.JSONDecodeError, ValueError):
        return []
    scopes = data.get("scopes") or []
    if isinstance(scopes, str):
        scopes = scopes.split()
    return [s for s in scopes if isinstance(s, str)]


def missing_scopes(token_path: Path, required: list[str] | None = None) -> list[str]:
    """Scopes in ``required`` (default ``config.GOOGLE_SCOPES``) that the
    saved token does not grant. Non-empty means the account needs to be
    reconnected before write-back can work (Mail Client MAIL-06).
    """
    granted = set(token_scopes(token_path))
    missing: list[str] = []
    for scope in required or config.GOOGLE_SCOPES:
        if scope in granted or granted & _SCOPE_SUPERSETS.get(scope, set()):
            continue
        missing.append(scope)
    return missing


def get_credentials_for_account(token_path: Path) -> Credentials:
    """Return valid Google OAuth credentials for a specific account token path.

    Handles load/refresh/re-authorize cycle and persists the token.
    Also performs one-time migration if token_path is the old generic path.

    The saved token is loaded with the scopes *it* was granted, not the
    scopes the application now requests: google-auth refuses to refresh
    when requested scopes exceed granted ones, which would turn every
    scope upgrade into a forced re-authorization. Accounts whose token
    lacks a current scope are reported by :func:`missing_scopes` and keep
    working within their old grant until reconnected (TDD D-23).
    """
    creds: Credentials | None = None

    # Try loading saved token
    if token_path.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(token_path))
        except (json.JSONDecodeError, ValueError) as exc:
            log.warning("Saved token is invalid, re-authenticating: %s", exc)
            creds = None

    # Refresh or re-authorize
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
        except Exception:
            log.warning("Token refresh failed, re-authenticating")
            creds = None

    if not creds or not creds.valid:
        if not config.CLIENT_SECRET_PATH.exists():
            raise FileNotFoundError(
                f"OAuth client secret not found at {config.CLIENT_SECRET_PATH}. "
                "Download it from Google Cloud Console → Credentials → "
                "OAuth 2.0 Client IDs → Download JSON, then save it as "
                f"{config.CLIENT_SECRET_PATH}"
            )
        flow = InstalledAppFlow.from_client_secrets_file(
            str(config.CLIENT_SECRET_PATH), config.GOOGLE_SCOPES
        )
        creds = flow.run_local_server(port=0)

        # Persist token
        config.CREDENTIALS_DIR.mkdir(parents=True, exist_ok=True)
        token_path.write_text(creds.to_json())
        log.info("Token saved to %s", token_path)

    # Migration: if this is the old generic token.json, copy to per-account path
    if token_path == config.TOKEN_PATH:
        try:
            email = get_user_email(creds)
            new_path = config.token_path_for_account(email)
            if not new_path.exists():
                shutil.copy2(str(token_path), str(new_path))
                log.info("Migrated token to %s", new_path)
            # Update DB row to point to new path
            with get_connection() as conn:
                conn.execute(
                    "UPDATE provider_accounts SET auth_token_path = ? WHERE auth_token_path = ?",
                    (str(new_path), str(token_path)),
                )
        except Exception as exc:
            log.warning("Token migration failed (non-fatal): %s", exc)

    return creds


def add_account_interactive() -> tuple[Credentials, str, Path]:
    """Run the OAuth flow for a new account.

    Always forces a new authorization (ignores existing tokens).
    Returns (credentials, email, token_path).
    """
    if not config.CLIENT_SECRET_PATH.exists():
        raise FileNotFoundError(
            f"OAuth client secret not found at {config.CLIENT_SECRET_PATH}. "
            "Download it from Google Cloud Console → Credentials → "
            "OAuth 2.0 Client IDs → Download JSON, then save it as "
            f"{config.CLIENT_SECRET_PATH}"
        )

    flow = InstalledAppFlow.from_client_secrets_file(
        str(config.CLIENT_SECRET_PATH), config.GOOGLE_SCOPES
    )
    creds = flow.run_local_server(port=0)

    email = get_user_email(creds)
    token_path = config.token_path_for_account(email)

    # Save token
    config.CREDENTIALS_DIR.mkdir(parents=True, exist_ok=True)
    token_path.write_text(creds.to_json())
    log.info("Token saved to %s", token_path)

    return creds, email, token_path


def reauthorize_account(email: str) -> Credentials:
    """Delete existing token and re-authorize with updated scopes."""
    token_path = config.token_path_for_account(email)

    if token_path.exists():
        token_path.unlink()
        log.info("Deleted existing token at %s", token_path)

    if not config.CLIENT_SECRET_PATH.exists():
        raise FileNotFoundError(
            f"OAuth client secret not found at {config.CLIENT_SECRET_PATH}."
        )

    flow = InstalledAppFlow.from_client_secrets_file(
        str(config.CLIENT_SECRET_PATH), config.GOOGLE_SCOPES
    )
    creds = flow.run_local_server(port=0)

    config.CREDENTIALS_DIR.mkdir(parents=True, exist_ok=True)
    token_path.write_text(creds.to_json())
    log.info("New token saved to %s", token_path)

    return creds


def get_credentials() -> Credentials:
    """Return valid Google OAuth credentials (backward-compat wrapper)."""
    return get_credentials_for_account(config.TOKEN_PATH)
