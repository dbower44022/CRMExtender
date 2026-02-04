"""Google People API wrapper for fetching known contacts."""

from __future__ import annotations

import logging

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from .models import KnownContact
from .rate_limiter import RateLimiter

log = logging.getLogger(__name__)


def fetch_contacts(
    creds: Credentials, rate_limiter: RateLimiter | None = None
) -> list[KnownContact]:
    """Fetch all contacts with email addresses from Google People API."""
    service = build("people", "v1", credentials=creds)
    contacts: list[KnownContact] = []
    page_token: str | None = None

    while True:
        if rate_limiter:
            rate_limiter.acquire()

        result = (
            service.people()
            .connections()
            .list(
                resourceName="people/me",
                pageSize=200,
                personFields="names,emailAddresses",
                pageToken=page_token or "",
            )
            .execute()
        )

        for person in result.get("connections", []):
            emails = person.get("emailAddresses", [])
            names = person.get("names", [])
            name = names[0].get("displayName", "") if names else ""
            resource_name = person.get("resourceName", "")

            for email_entry in emails:
                addr = email_entry.get("value", "").strip().lower()
                if addr:
                    contacts.append(
                        KnownContact(
                            email=addr,
                            name=name,
                            resource_name=resource_name,
                        )
                    )

        page_token = result.get("nextPageToken")
        if not page_token:
            break

    log.info("Fetched %d contacts with email addresses", len(contacts))
    return contacts
