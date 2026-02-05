"""Data models for the Gmail Conversation Aggregation PoC."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
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

    def to_row(self, *, contact_id: str | None = None) -> dict:
        """Serialize to a dict suitable for INSERT into contacts table."""
        now = _now_iso()
        return {
            "id": contact_id or str(uuid.uuid4()),
            "email": self.email.lower(),
            "name": self.name,
            "source": "google_contacts",
            "source_id": self.resource_name,
            "created_at": now,
            "updated_at": now,
        }

    @classmethod
    def from_row(cls, row) -> KnownContact:
        """Construct from a sqlite3.Row or dict."""
        r = dict(row)
        return cls(
            email=r["email"],
            name=r.get("name") or "",
            resource_name=r.get("source_id") or "",
        )


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

    def to_row(
        self,
        *,
        account_id: str,
        conversation_id: str | None = None,
        email_id: str | None = None,
        account_email: str = "",
    ) -> dict:
        """Serialize to a dict suitable for INSERT into emails table."""
        direction = "outbound" if self.sender_email.lower() == account_email.lower() else "inbound"
        return {
            "id": email_id or str(uuid.uuid4()),
            "account_id": account_id,
            "conversation_id": conversation_id,
            "provider_message_id": self.message_id,
            "subject": self.subject,
            "sender_address": self.sender_email,
            "sender_name": self.sender or None,
            "date": self.date.isoformat() if self.date else None,
            "body_text": self.body_plain,
            "body_html": self.body_html,
            "snippet": self.snippet,
            "header_message_id": None,
            "header_references": None,
            "header_in_reply_to": None,
            "direction": direction,
            "is_read": 0,
            "has_attachments": 0,
            "created_at": _now_iso(),
        }

    def recipient_rows(self, email_id: str) -> list[dict]:
        """Return rows for the email_recipients table."""
        rows: list[dict] = []
        for addr in self.recipients:
            rows.append({"email_id": email_id, "address": addr.lower(), "name": None, "role": "to"})
        for addr in self.cc:
            rows.append({"email_id": email_id, "address": addr.lower(), "name": None, "role": "cc"})
        return rows

    @classmethod
    def from_row(cls, row, *, recipients: list[dict] | None = None) -> ParsedEmail:
        """Construct from a sqlite3.Row or dict, optionally with recipient rows."""
        r = dict(row)
        to_addrs = []
        cc_addrs = []
        if recipients:
            for rec in recipients:
                rec = dict(rec)
                if rec["role"] == "to":
                    to_addrs.append(rec["address"])
                elif rec["role"] == "cc":
                    cc_addrs.append(rec["address"])

        date_val = None
        if r.get("date"):
            try:
                date_val = datetime.fromisoformat(r["date"])
            except (ValueError, TypeError):
                pass

        return cls(
            message_id=r["provider_message_id"],
            thread_id="",  # thread_id lives on conversation, not email row
            subject=r.get("subject") or "",
            sender=r.get("sender_name") or r["sender_address"],
            sender_email=r["sender_address"],
            recipients=to_addrs,
            cc=cc_addrs,
            date=date_val,
            body_plain=r.get("body_text") or "",
            body_html=r.get("body_html") or "",
            snippet=r.get("snippet") or "",
        )


@dataclass
class Conversation:
    """A group of emails sharing the same Gmail threadId."""

    thread_id: str
    subject: str
    emails: list[ParsedEmail] = field(default_factory=list)
    participants: list[str] = field(default_factory=list)
    matched_contacts: dict[str, KnownContact] = field(default_factory=dict)
    account_email: str = ""  # which account this belongs to (display-time only)

    @property
    def message_count(self) -> int:
        return len(self.emails)

    @property
    def date_range(self) -> tuple[datetime | None, datetime | None]:
        dates = [e.date for e in self.emails if e.date]
        if not dates:
            return None, None
        return min(dates), max(dates)

    def to_row(
        self,
        *,
        account_id: str,
        conversation_id: str | None = None,
    ) -> dict:
        """Serialize to a dict suitable for INSERT into conversations table."""
        first_dt, last_dt = self.date_range
        now = _now_iso()
        return {
            "id": conversation_id or str(uuid.uuid4()),
            "account_id": account_id,
            "provider_thread_id": self.thread_id,
            "subject": self.subject,
            "status": "active",
            "message_count": self.message_count,
            "first_message_at": first_dt.isoformat() if first_dt else None,
            "last_message_at": last_dt.isoformat() if last_dt else None,
            "ai_summary": None,
            "ai_status": None,
            "ai_action_items": None,
            "ai_topics": None,
            "ai_summarized_at": None,
            "triage_result": None,
            "created_at": now,
            "updated_at": now,
        }

    @classmethod
    def from_row(cls, row, *, emails: list[ParsedEmail] | None = None) -> Conversation:
        """Construct from a sqlite3.Row or dict."""
        r = dict(row)
        return cls(
            thread_id=r.get("provider_thread_id") or r["id"],
            subject=r.get("subject") or "",
            emails=emails or [],
            participants=[],
        )


class FilterReason(Enum):
    NO_KNOWN_CONTACTS = "No known contacts"
    AUTOMATED_SENDER = "Automated sender"
    AUTOMATED_SUBJECT = "Automated subject"
    MARKETING = "Marketing"


# Map triage_result DB strings to FilterReason values
_TRIAGE_REASON_MAP = {
    "no_known_contacts": FilterReason.NO_KNOWN_CONTACTS,
    "automated_sender": FilterReason.AUTOMATED_SENDER,
    "automated_subject": FilterReason.AUTOMATED_SUBJECT,
    "marketing": FilterReason.MARKETING,
}

_FILTER_REASON_TO_DB = {v: k for k, v in _TRIAGE_REASON_MAP.items()}


def filter_reason_to_db(reason: FilterReason) -> str:
    """Convert a FilterReason enum to its database string."""
    return _FILTER_REASON_TO_DB[reason]


def filter_reason_from_db(db_str: str) -> FilterReason:
    """Convert a database triage_result string to a FilterReason enum."""
    return _TRIAGE_REASON_MAP[db_str]


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

    def to_update_dict(self) -> dict:
        """Return a dict of conversation columns to UPDATE with AI results."""
        return {
            "ai_summary": self.summary,
            "ai_status": self.status.value.lower(),
            "ai_action_items": json.dumps(self.action_items) if self.action_items else None,
            "ai_topics": json.dumps(self.key_topics) if self.key_topics else None,
            "ai_summarized_at": _now_iso(),
        }

    @classmethod
    def from_conversation_row(cls, row) -> ConversationSummary | None:
        """Extract summary fields from a conversation row; returns None if not summarized."""
        r = dict(row)
        if not r.get("ai_summarized_at"):
            return None
        status_str = (r.get("ai_status") or "uncertain").upper()
        try:
            status = ConversationStatus(status_str)
        except ValueError:
            status = ConversationStatus.UNCERTAIN
        return cls(
            thread_id=r.get("provider_thread_id") or r["id"],
            status=status,
            summary=r.get("ai_summary") or "",
            action_items=json.loads(r["ai_action_items"]) if r.get("ai_action_items") else [],
            key_topics=json.loads(r["ai_topics"]) if r.get("ai_topics") else [],
        )


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
