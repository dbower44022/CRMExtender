"""Data models for the Gmail Conversation Aggregation PoC."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class ConversationStatus(Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    UNCERTAIN = "UNCERTAIN"


@dataclass
class KnownContact:
    """A contact from Google People API."""

    email: str
    name: str
    resource_name: str = ""

    @property
    def display(self) -> str:
        return self.name if self.name else self.email


@dataclass
class ParsedEmail:
    """A single email message parsed from Gmail API."""

    message_id: str
    thread_id: str
    subject: str
    sender: str
    sender_email: str
    recipients: list[str] = field(default_factory=list)
    cc: list[str] = field(default_factory=list)
    date: datetime | None = None
    body_plain: str = ""
    body_html: str = ""
    snippet: str = ""

    @property
    def all_participants(self) -> list[str]:
        participants = [self.sender_email] + self.recipients + self.cc
        return list(dict.fromkeys(p.lower() for p in participants if p))


@dataclass
class Conversation:
    """A group of emails sharing the same Gmail threadId."""

    thread_id: str
    subject: str
    emails: list[ParsedEmail] = field(default_factory=list)
    participants: list[str] = field(default_factory=list)
    matched_contacts: dict[str, KnownContact] = field(default_factory=dict)

    @property
    def message_count(self) -> int:
        return len(self.emails)

    @property
    def date_range(self) -> tuple[datetime | None, datetime | None]:
        dates = [e.date for e in self.emails if e.date]
        if not dates:
            return None, None
        return min(dates), max(dates)


class FilterReason(Enum):
    NO_KNOWN_CONTACTS = "No known contacts"
    AUTOMATED_SENDER = "Automated sender"
    AUTOMATED_SUBJECT = "Automated subject"
    MARKETING = "Marketing"


@dataclass
class TriageResult:
    """A conversation that was filtered out during triage."""

    thread_id: str
    subject: str
    reason: FilterReason


@dataclass
class ConversationSummary:
    """Claude-generated summary for a conversation."""

    thread_id: str
    status: ConversationStatus
    summary: str
    action_items: list[str] = field(default_factory=list)
    key_topics: list[str] = field(default_factory=list)
    error: str | None = None
