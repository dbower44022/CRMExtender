"""Phone number normalization and formatting utilities."""

from __future__ import annotations

import phonenumbers

from .database import get_connection
from .settings import get_setting


def resolve_country_code(
    entity_type: str,
    entity_id: str,
    *,
    customer_id: str | None = None,
    db_path=None,
) -> str:
    """Resolve the country code for an entity.

    Cascade:
    1. Entity's address country field (primary first)
    2. System setting ``default_phone_country``
    3. Hardcoded fallback ``"US"``
    """
    with get_connection(db_path) as conn:
        row = conn.execute(
            "SELECT country FROM addresses "
            "WHERE entity_type = ? AND entity_id = ? AND country IS NOT NULL "
            "ORDER BY is_primary DESC, created_at ASC LIMIT 1",
            (entity_type, entity_id),
        ).fetchone()
        if row and row["country"]:
            return row["country"]

    if customer_id:
        val = get_setting(customer_id, "default_phone_country", db_path=db_path)
        if val:
            return val

    return "US"


def normalize_phone(raw_number: str, country_code: str = "US") -> str | None:
    """Parse and normalize a phone number to E.164 format.

    Uses ``is_possible_number()`` (lenient — length check only) rather than
    ``is_valid_number()`` to accept toll-free and unassigned area codes.

    Returns ``None`` if the number cannot be parsed at all.
    """
    try:
        parsed = phonenumbers.parse(raw_number, country_code)
    except phonenumbers.NumberParseException:
        return None

    if not phonenumbers.is_possible_number(parsed):
        return None

    return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)


def format_phone(e164_number: str, country_code: str = "US") -> str:
    """Format a phone number for display.

    NATIONAL format when the number matches the display country,
    INTERNATIONAL otherwise.  Returns input as-is if unparseable.
    """
    try:
        parsed = phonenumbers.parse(e164_number, country_code)
    except phonenumbers.NumberParseException:
        return e164_number

    region = phonenumbers.region_code_for_number(parsed)
    if region and region.upper() == country_code.upper():
        return phonenumbers.format_number(
            parsed, phonenumbers.PhoneNumberFormat.NATIONAL
        )
    return phonenumbers.format_number(
        parsed, phonenumbers.PhoneNumberFormat.INTERNATIONAL
    )


def validate_phone(raw_number: str, country_code: str = "US") -> bool:
    """Return True if *raw_number* can be normalized to E.164."""
    return normalize_phone(raw_number, country_code) is not None
