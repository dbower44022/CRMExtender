"""Google OAuth 2.0 flow with token persistence."""

from __future__ import annotations

import json
import logging

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from . import config

log = logging.getLogger(__name__)


def get_credentials() -> Credentials:
    """Return valid Google OAuth credentials, running the auth flow if needed."""
    creds: Credentials | None = None

    # Try loading saved token
    if config.TOKEN_PATH.exists():
        try:
            creds = Credentials.from_authorized_user_file(
                str(config.TOKEN_PATH), config.GOOGLE_SCOPES
            )
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

        # Persist token for next run
        config.CREDENTIALS_DIR.mkdir(parents=True, exist_ok=True)
        config.TOKEN_PATH.write_text(creds.to_json())
        log.info("Token saved to %s", config.TOKEN_PATH)

    return creds
