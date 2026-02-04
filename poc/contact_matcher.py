"""Match email participants against known Google Contacts."""

from __future__ import annotations

import logging

from .models import Conversation, KnownContact

log = logging.getLogger(__name__)


def build_contact_index(contacts: list[KnownContact]) -> dict[str, KnownContact]:
    """Build a case-insensitive email-to-contact lookup dict.

    When multiple contacts share an email, the first one wins.
    """
    index: dict[str, KnownContact] = {}
    for contact in contacts:
        key = contact.email.lower()
        if key not in index:
            index[key] = contact
    return index


def match_contacts(
    conversations: list[Conversation],
    contact_index: dict[str, KnownContact],
) -> None:
    """Enrich conversations with matched contacts (mutates in place)."""
    total_matched = 0
    for conv in conversations:
        for participant in conv.participants:
            key = participant.lower()
            if key in contact_index:
                conv.matched_contacts[key] = contact_index[key]
                total_matched += 1

    log.info(
        "Matched %d participant-contact pairs across %d conversations",
        total_matched,
        len(conversations),
    )
