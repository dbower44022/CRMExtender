"""Triage step — filter junk/non-conversation emails before summarization.

Two-layer filter (fast, free — no API calls):
  1. Heuristic junk detection (automated senders, subjects, marketing)
  2. Known-contact gate (drop threads with zero known-contact participants,
     excluding the authenticated user themselves)
"""

from __future__ import annotations

import logging
import re

from .models import Conversation, FilterReason, TriageResult

log = logging.getLogger(__name__)

# --- Layer 1: Heuristic patterns ---

AUTOMATED_SENDER_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in (
        r"^no-?reply",              # noreply@, no-reply@, no-reply-xxx@
        r"^do-?not-?reply",         # donotreply@, do-not-reply@
        r"^mailer-daemon@",
        r"^postmaster@",
        r"^notification(s|only)?@",
        r"^notify@",
        r"^auto-?confirm@",
        r"^automated@",
        r"^bounces?@",
        r"^account[_-]?(update|alert|confirm|security|info)@",
        r"^myaccount@",
        r"^renewals?@",
        r"^recommendations?@",
        r"^invoice",                # invoice@, invoice+statements@, etc.
        r"^billing@",
        r"^receipts?@",
        r"^alerts?@",
    )
]

_AUTOMATED_SUBJECT_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in (
        r"^out of office",
        r"^automatic reply",
        r"^auto-?reply",
        r"delivery status notification",
        r"^undeliverable:",
        r"^returned mail:",
        r"^mail delivery",
        r"^unsubscribe",
        r"^confirm your (email|subscription|account)",
        r"^verify your (email|account)",
        r"^reset your password",
        r"^password reset",
    )
]

_UNSUBSCRIBE_PATTERN = re.compile(r"unsubscribe", re.IGNORECASE)


def _is_automated_sender(addr: str) -> bool:
    addr = addr.lower().strip()
    return any(pat.search(addr) for pat in AUTOMATED_SENDER_PATTERNS)


def _is_automated_subject(subject: str) -> bool:
    return any(pat.search(subject) for pat in _AUTOMATED_SUBJECT_PATTERNS)


def _is_marketing(emails: list) -> bool:
    """Check if thread body content contains unsubscribe indicators."""
    for msg in emails:
        text = msg.body_plain or msg.body_html or ""
        if _UNSUBSCRIBE_PATTERN.search(text):
            return True
    return False


def _has_known_contact(conversation: Conversation, user_email: str) -> bool:
    """Check if any participant *other than the user* is a known contact."""
    for email in conversation.matched_contacts:
        if email != user_email:
            return True
    return False


def triage_conversations(
    conversations: list[Conversation],
    user_email: str,
) -> tuple[list[Conversation], list[TriageResult]]:
    """Filter conversations through heuristic junk detection and contact gate.

    Returns (kept, filtered) where only *kept* should proceed to summarization.
    """
    user_email = user_email.lower()
    kept: list[Conversation] = []
    filtered: list[TriageResult] = []

    for conv in conversations:
        reason = _classify(conv, user_email)
        if reason is None:
            kept.append(conv)
        else:
            filtered.append(
                TriageResult(
                    thread_id=conv.thread_id,
                    subject=conv.subject,
                    reason=reason,
                )
            )
            log.debug("Filtered thread %s (%s): %s", conv.thread_id, reason.value, conv.subject)

    log.info(
        "Triage: %d kept, %d filtered out of %d total",
        len(kept),
        len(filtered),
        len(conversations),
    )
    return kept, filtered


def _classify(conv: Conversation, user_email: str) -> FilterReason | None:
    """Return a FilterReason if the conversation should be filtered, else None.

    Checks are ordered so the most specific heuristic fires first.
    """
    # Layer 1: Heuristic junk detection
    first_email = conv.emails[0] if conv.emails else None

    if first_email and _is_automated_sender(first_email.sender_email):
        return FilterReason.AUTOMATED_SENDER

    if _is_automated_subject(conv.subject):
        return FilterReason.AUTOMATED_SUBJECT

    if _is_marketing(conv.emails):
        return FilterReason.MARKETING

    # Layer 2: Known-contact gate (excludes the user's own email)
    if not _has_known_contact(conv, user_email):
        return FilterReason.NO_KNOWN_CONTACTS

    return None
