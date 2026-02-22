"""Google People API wrapper for fetching known contacts."""

from __future__ import annotations

import logging

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from .models import KnownContact
from .rate_limiter import RateLimiter

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Google → CRM type mappers
# ---------------------------------------------------------------------------

def _map_google_phone_type(google_type: str) -> str:
    """Map a Google People API phone type to CRM phone_type."""
    mapping = {
        "mobile": "mobile",
        "work": "work",
        "home": "home",
        "homeFax": "fax",
        "workFax": "fax",
        "otherFax": "fax",
        "main": "main",
        "pager": "pager",
    }
    return mapping.get(google_type or "", "other")


def _map_google_address_type(google_type: str) -> str:
    """Map a Google People API address type to CRM address_type."""
    mapping = {
        "work": "work",
        "home": "home",
    }
    return mapping.get(google_type or "", "other")


# ---------------------------------------------------------------------------
# Contact groups (labels)
# ---------------------------------------------------------------------------

def fetch_contact_groups(
    creds: Credentials, rate_limiter: RateLimiter | None = None,
) -> dict[str, str]:
    """Fetch user-created contact groups. Returns {resourceName: groupName}.

    System groups (myContacts, starred, etc.) are filtered out.
    """
    service = build("people", "v1", credentials=creds)
    if rate_limiter:
        rate_limiter.acquire()

    result = (
        service.contactGroups()
        .list(pageSize=1000)
        .execute()
    )

    groups: dict[str, str] = {}
    for group in result.get("contactGroups", []):
        # System groups have groupType == "SYSTEM_CONTACT_GROUP"
        if group.get("groupType") == "SYSTEM_CONTACT_GROUP":
            continue
        resource = group.get("resourceName", "")
        name = group.get("name", "")
        if resource and name:
            groups[resource] = name

    log.info("Fetched %d user-created contact groups", len(groups))
    return groups


# ---------------------------------------------------------------------------
# Contact fetching
# ---------------------------------------------------------------------------

def _extract_phones(person: dict) -> list[dict]:
    """Extract phone numbers from a People API person resource."""
    phones = []
    for entry in person.get("phoneNumbers", []):
        number = (entry.get("value") or "").strip()
        if number:
            phones.append({
                "number": number,
                "type": _map_google_phone_type(entry.get("type", "")),
            })
    return phones


def _extract_addresses(person: dict) -> list[dict]:
    """Extract addresses from a People API person resource."""
    addresses = []
    for entry in person.get("addresses", []):
        addr = {
            "type": _map_google_address_type(entry.get("type", "")),
            "street": (entry.get("streetAddress") or "").strip(),
            "city": (entry.get("city") or "").strip(),
            "state": (entry.get("region") or "").strip(),
            "postal_code": (entry.get("postalCode") or "").strip(),
            "country": (entry.get("country") or "").strip(),
        }
        # Only include if at least one substantive field is present
        if any(addr[k] for k in ("street", "city", "state", "postal_code", "country")):
            addresses.append(addr)
    return addresses


def _extract_labels(person: dict, group_map: dict[str, str]) -> list[str]:
    """Extract resolved label names from memberships + group map."""
    labels = []
    for membership in person.get("memberships", []):
        group_ref = membership.get("contactGroupMembership", {}).get(
            "contactGroupResourceName", ""
        )
        if group_ref and group_ref in group_map:
            labels.append(group_map[group_ref])
    return labels


def fetch_contacts(
    creds: Credentials,
    rate_limiter: RateLimiter | None = None,
    *,
    group_map: dict[str, str] | None = None,
) -> list[KnownContact]:
    """Fetch all contacts with email addresses from Google People API."""
    service = build("people", "v1", credentials=creds)
    contacts: list[KnownContact] = []
    page_token: str | None = None

    if group_map is None:
        group_map = {}

    while True:
        if rate_limiter:
            rate_limiter.acquire()

        result = (
            service.people()
            .connections()
            .list(
                resourceName="people/me",
                pageSize=200,
                personFields="names,emailAddresses,organizations,phoneNumbers,addresses,biographies,memberships",
                pageToken=page_token or "",
            )
            .execute()
        )

        for person in result.get("connections", []):
            emails = person.get("emailAddresses", [])
            names = person.get("names", [])
            orgs = person.get("organizations", [])
            bios = person.get("biographies", [])

            name = names[0].get("displayName", "") if names else ""
            resource_name = person.get("resourceName", "")
            company = orgs[0].get("name", "") if orgs else ""
            title = orgs[0].get("title", "") if orgs else ""
            biography = bios[0].get("value", "") if bios else ""

            phones = _extract_phones(person)
            addresses = _extract_addresses(person)
            labels = _extract_labels(person, group_map)

            for email_entry in emails:
                addr = email_entry.get("value", "").strip().lower()
                if addr:
                    contacts.append(
                        KnownContact(
                            email=addr,
                            name=name,
                            resource_name=resource_name,
                            company=company,
                            title=title,
                            phones=phones,
                            addresses=addresses,
                            biography=biography,
                            labels=labels,
                        )
                    )

        page_token = result.get("nextPageToken")
        if not page_token:
            break

    log.info("Fetched %d contacts with email addresses", len(contacts))
    return contacts
