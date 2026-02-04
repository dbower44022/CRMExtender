"""Group parsed emails by Gmail threadId into Conversations."""

from __future__ import annotations

import logging
from datetime import timezone

from .email_parser import strip_quotes
from .models import Conversation, ParsedEmail

log = logging.getLogger(__name__)


def build_conversations(threads: list[list[ParsedEmail]]) -> list[Conversation]:
    """Convert raw thread groups into Conversation objects.

    Each thread (list of ParsedEmail) becomes one Conversation with:
    - stripped email bodies
    - deduplicated participant list
    - sorted emails (by date ascending)
    """
    conversations: list[Conversation] = []

    for emails in threads:
        if not emails:
            continue

        thread_id = emails[0].thread_id
        subject = emails[0].subject or "(no subject)"

        # Strip quotes from each email body
        for em in emails:
            em.body_plain = strip_quotes(em.body_plain)

        # Collect unique participants across all emails in the thread
        all_participants: dict[str, None] = {}
        for em in emails:
            for p in em.all_participants:
                all_participants[p] = None

        conversations.append(
            Conversation(
                thread_id=thread_id,
                subject=subject,
                emails=emails,
                participants=list(all_participants.keys()),
            )
        )

    # Sort conversations by most recent message date (newest first)
    conversations.sort(
        key=lambda c: c.emails[-1].date
        if c.emails and c.emails[-1].date
        else __import__("datetime").datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )

    log.info("Built %d conversations from %d threads", len(conversations), len(threads))
    return conversations
