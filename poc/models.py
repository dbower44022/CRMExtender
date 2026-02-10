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
    company: str = ""
    status: str = "active"

    @property
    def display(self) -> str:
        return self.name if self.name else self.email

    def to_row(
        self,
        *,
        contact_id: str | None = None,
        company_id: str | None = None,
        created_by: str | None = None,
        updated_by: str | None = None,
    ) -> tuple[dict, dict]:
        """Serialize to (contact_dict, identifier_dict) for INSERT.

        Returns a tuple of two dicts: one for the contacts table and one for
        the contact_identifiers table.
        """
        now = _now_iso()
        cid = contact_id or str(uuid.uuid4())
        contact = {
            "id": cid,
            "name": self.name,
            "company": self.company,
            "company_id": company_id,
            "source": "google_contacts",
            "status": self.status,
            "created_by": created_by,
            "updated_by": updated_by,
            "created_at": now,
            "updated_at": now,
        }
        identifier = {
            "id": str(uuid.uuid4()),
            "contact_id": cid,
            "type": "email",
            "value": self.email.lower(),
            "label": None,
            "is_primary": 1,
            "status": "active",
            "source": "google_contacts",
            "verified": 1,
            "created_by": created_by,
            "updated_by": updated_by,
            "created_at": now,
            "updated_at": now,
        }
        return contact, identifier

    @classmethod
    def from_row(cls, row, *, email: str | None = None) -> KnownContact:
        """Construct from a sqlite3.Row or dict.

        If the row is a JOIN with contact_identifiers, the email comes from
        the 'value' column. Otherwise pass it explicitly via the email kwarg.
        """
        r = dict(row)
        resolved_email = email or r.get("value") or r.get("email") or ""
        return cls(
            email=resolved_email,
            name=r.get("name") or "",
            resource_name=r.get("resource_name") or "",
            company=r.get("company") or "",
            status=r.get("status") or "active",
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
        communication_id: str | None = None,
        account_email: str = "",
    ) -> dict:
        """Serialize to a dict suitable for INSERT into communications table."""
        now = _now_iso()
        direction = "outbound" if self.sender_email.lower() == account_email.lower() else "inbound"
        return {
            "id": communication_id or str(uuid.uuid4()),
            "account_id": account_id,
            "channel": "email",
            "timestamp": self.date.isoformat() if self.date else now,
            "content": self.body_plain,
            "direction": direction,
            "source": "auto_sync",
            "sender_address": self.sender_email,
            "sender_name": self.sender or None,
            "subject": self.subject,
            "body_html": self.body_html,
            "snippet": self.snippet,
            "provider_message_id": self.message_id,
            "provider_thread_id": self.thread_id,
            "header_message_id": None,
            "header_references": None,
            "header_in_reply_to": None,
            "is_read": 0,
            "is_current": 1,
            "created_at": now,
            "updated_at": now,
        }

    def recipient_rows(self, communication_id: str) -> list[dict]:
        """Return rows for the communication_participants table."""
        rows: list[dict] = []
        for addr in self.recipients:
            rows.append({"communication_id": communication_id, "address": addr.lower(), "name": None, "role": "to"})
        for addr in self.cc:
            rows.append({"communication_id": communication_id, "address": addr.lower(), "name": None, "role": "cc"})
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
        raw_date = r.get("timestamp") or r.get("date")
        if raw_date:
            try:
                date_val = datetime.fromisoformat(raw_date)
            except (ValueError, TypeError):
                pass

        return cls(
            message_id=r["provider_message_id"],
            thread_id=r.get("provider_thread_id") or "",
            subject=r.get("subject") or "",
            sender=r.get("sender_name") or r["sender_address"],
            sender_email=r["sender_address"],
            recipients=to_addrs,
            cc=cc_addrs,
            date=date_val,
            body_plain=r.get("content") or r.get("body_text") or "",
            body_html=r.get("body_html") or "",
            snippet=r.get("snippet") or "",
        )


@dataclass
class Conversation:
    """A group of communications sharing the same thread/conversation."""

    thread_id: str
    title: str
    emails: list[ParsedEmail] = field(default_factory=list)
    participants: list[str] = field(default_factory=list)
    matched_contacts: dict[str, KnownContact] = field(default_factory=dict)
    account_email: str = ""  # which account this belongs to (display-time only)

    @property
    def subject(self) -> str:
        """Backward-compatible alias for title."""
        return self.title

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
        conversation_id: str | None = None,
        created_by: str | None = None,
        updated_by: str | None = None,
    ) -> dict:
        """Serialize to a dict suitable for INSERT into conversations table."""
        first_dt, last_dt = self.date_range
        now = _now_iso()
        return {
            "id": conversation_id or str(uuid.uuid4()),
            "topic_id": None,
            "title": self.title,
            "status": "active",
            "communication_count": self.message_count,
            "participant_count": len(self.participants),
            "first_activity_at": first_dt.isoformat() if first_dt else None,
            "last_activity_at": last_dt.isoformat() if last_dt else None,
            "ai_summary": None,
            "ai_status": None,
            "ai_action_items": None,
            "ai_topics": None,
            "ai_summarized_at": None,
            "triage_result": None,
            "dismissed": 0,
            "created_by": created_by,
            "updated_by": updated_by,
            "created_at": now,
            "updated_at": now,
        }

    @classmethod
    def from_row(cls, row, *, emails: list[ParsedEmail] | None = None) -> Conversation:
        """Construct from a sqlite3.Row or dict."""
        r = dict(row)
        return cls(
            thread_id=r["id"],
            title=r.get("title") or r.get("subject") or "",
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
            thread_id=r["id"],
            status=status,
            summary=r.get("ai_summary") or "",
            action_items=json.loads(r["ai_action_items"]) if r.get("ai_action_items") else [],
            key_topics=json.loads(r["ai_topics"]) if r.get("ai_topics") else [],
        )


@dataclass
class RelationshipType:
    """A relationship type definition."""

    name: str
    from_entity_type: str = "contact"
    to_entity_type: str = "contact"
    forward_label: str = ""
    reverse_label: str = ""
    is_system: bool = False
    is_bidirectional: bool = False
    description: str = ""

    def to_row(
        self,
        *,
        type_id: str | None = None,
        created_by: str | None = None,
        updated_by: str | None = None,
    ) -> dict:
        now = _now_iso()
        return {
            "id": type_id or str(uuid.uuid4()),
            "name": self.name,
            "from_entity_type": self.from_entity_type,
            "to_entity_type": self.to_entity_type,
            "forward_label": self.forward_label,
            "reverse_label": self.reverse_label,
            "is_system": 1 if self.is_system else 0,
            "is_bidirectional": 1 if self.is_bidirectional else 0,
            "description": self.description or None,
            "created_by": created_by,
            "updated_by": updated_by,
            "created_at": now,
            "updated_at": now,
        }

    @classmethod
    def from_row(cls, row) -> RelationshipType:
        r = dict(row)
        return cls(
            name=r["name"],
            from_entity_type=r.get("from_entity_type") or "contact",
            to_entity_type=r.get("to_entity_type") or "contact",
            forward_label=r.get("forward_label") or "",
            reverse_label=r.get("reverse_label") or "",
            is_system=bool(r.get("is_system", 0)),
            is_bidirectional=bool(r.get("is_bidirectional", 0)),
            description=r.get("description") or "",
        )


@dataclass
class Relationship:
    """A relationship between two entities."""

    from_entity_id: str
    to_entity_id: str
    relationship_type_id: str = "rt-knows"
    from_entity_type: str = "contact"
    to_entity_type: str = "contact"
    paired_relationship_id: str | None = None
    source: str = "inferred"
    strength: float = 0.0
    shared_conversations: int = 0
    shared_messages: int = 0
    last_interaction: str | None = None
    first_interaction: str | None = None

    # Backward-compatible aliases
    @property
    def from_contact_id(self) -> str:
        return self.from_entity_id

    @property
    def to_contact_id(self) -> str:
        return self.to_entity_id

    def to_row(
        self,
        *,
        relationship_id: str | None = None,
        created_by: str | None = None,
        updated_by: str | None = None,
    ) -> dict:
        """Serialize to a dict suitable for INSERT into relationships table."""
        now = _now_iso()
        properties = json.dumps({
            "strength": self.strength,
            "shared_conversations": self.shared_conversations,
            "shared_messages": self.shared_messages,
            "last_interaction": self.last_interaction,
            "first_interaction": self.first_interaction,
        })
        return {
            "id": relationship_id or str(uuid.uuid4()),
            "relationship_type_id": self.relationship_type_id,
            "from_entity_type": self.from_entity_type,
            "from_entity_id": self.from_entity_id,
            "to_entity_type": self.to_entity_type,
            "to_entity_id": self.to_entity_id,
            "paired_relationship_id": self.paired_relationship_id,
            "source": self.source,
            "properties": properties,
            "created_by": created_by,
            "updated_by": updated_by,
            "created_at": now,
            "updated_at": now,
        }

    @classmethod
    def from_row(cls, row) -> Relationship:
        """Construct from a sqlite3.Row or dict."""
        r = dict(row)
        props = json.loads(r.get("properties") or "{}")
        return cls(
            from_entity_id=r["from_entity_id"],
            to_entity_id=r["to_entity_id"],
            relationship_type_id=r.get("relationship_type_id", "rt-knows"),
            from_entity_type=r.get("from_entity_type", "contact"),
            to_entity_type=r.get("to_entity_type", "contact"),
            paired_relationship_id=r.get("paired_relationship_id"),
            source=r.get("source", "inferred"),
            strength=props.get("strength", 0.0),
            shared_conversations=props.get("shared_conversations", 0),
            shared_messages=props.get("shared_messages", 0),
            last_interaction=props.get("last_interaction"),
            first_interaction=props.get("first_interaction"),
        )


@dataclass
class User:
    """A CRM user (owner of projects, dismisser of conversations)."""

    email: str
    name: str = ""
    role: str = "member"
    is_active: bool = True

    def to_row(self, *, user_id: str | None = None) -> dict:
        now = _now_iso()
        return {
            "id": user_id or str(uuid.uuid4()),
            "email": self.email,
            "name": self.name or None,
            "role": self.role,
            "is_active": 1 if self.is_active else 0,
            "created_at": now,
            "updated_at": now,
        }

    @classmethod
    def from_row(cls, row) -> User:
        r = dict(row)
        return cls(
            email=r["email"],
            name=r.get("name") or "",
            role=r.get("role") or "member",
            is_active=bool(r.get("is_active", 1)),
        )


@dataclass
class Project:
    """An organizational project that contains topics."""

    name: str
    description: str = ""
    parent_id: str | None = None
    owner_id: str | None = None
    status: str = "active"

    def to_row(
        self,
        *,
        project_id: str | None = None,
        created_by: str | None = None,
        updated_by: str | None = None,
    ) -> dict:
        now = _now_iso()
        return {
            "id": project_id or str(uuid.uuid4()),
            "parent_id": self.parent_id,
            "name": self.name,
            "description": self.description or None,
            "status": self.status,
            "owner_id": self.owner_id,
            "created_by": created_by,
            "updated_by": updated_by,
            "created_at": now,
            "updated_at": now,
        }

    @classmethod
    def from_row(cls, row) -> Project:
        r = dict(row)
        return cls(
            name=r["name"],
            description=r.get("description") or "",
            parent_id=r.get("parent_id"),
            owner_id=r.get("owner_id"),
            status=r.get("status") or "active",
        )


@dataclass
class Topic:
    """An organizational topic within a project."""

    project_id: str
    name: str
    description: str = ""
    source: str = "user"

    def to_row(
        self,
        *,
        topic_id: str | None = None,
        created_by: str | None = None,
        updated_by: str | None = None,
    ) -> dict:
        now = _now_iso()
        return {
            "id": topic_id or str(uuid.uuid4()),
            "project_id": self.project_id,
            "name": self.name,
            "description": self.description or None,
            "source": self.source,
            "created_by": created_by,
            "updated_by": updated_by,
            "created_at": now,
            "updated_at": now,
        }

    @classmethod
    def from_row(cls, row) -> Topic:
        r = dict(row)
        return cls(
            project_id=r["project_id"],
            name=r["name"],
            description=r.get("description") or "",
            source=r.get("source") or "user",
        )


@dataclass
class Company:
    """A company that contacts can be linked to."""

    name: str
    domain: str = ""
    industry: str = ""
    description: str = ""
    website: str = ""
    stock_symbol: str = ""
    size_range: str = ""
    employee_count: int | None = None
    founded_year: int | None = None
    revenue_range: str = ""
    funding_total: str = ""
    funding_stage: str = ""
    headquarters_location: str = ""
    status: str = "active"

    def to_row(
        self,
        *,
        company_id: str | None = None,
        created_by: str | None = None,
        updated_by: str | None = None,
    ) -> dict:
        now = _now_iso()
        return {
            "id": company_id or str(uuid.uuid4()),
            "name": self.name,
            "domain": self.domain or None,
            "industry": self.industry or None,
            "description": self.description or None,
            "website": self.website or None,
            "stock_symbol": self.stock_symbol or None,
            "size_range": self.size_range or None,
            "employee_count": self.employee_count,
            "founded_year": self.founded_year,
            "revenue_range": self.revenue_range or None,
            "funding_total": self.funding_total or None,
            "funding_stage": self.funding_stage or None,
            "headquarters_location": self.headquarters_location or None,
            "status": self.status,
            "created_by": created_by,
            "updated_by": updated_by,
            "created_at": now,
            "updated_at": now,
        }

    @classmethod
    def from_row(cls, row) -> Company:
        r = dict(row)
        return cls(
            name=r["name"],
            domain=r.get("domain") or "",
            industry=r.get("industry") or "",
            description=r.get("description") or "",
            website=r.get("website") or "",
            stock_symbol=r.get("stock_symbol") or "",
            size_range=r.get("size_range") or "",
            employee_count=r.get("employee_count"),
            founded_year=r.get("founded_year"),
            revenue_range=r.get("revenue_range") or "",
            funding_total=r.get("funding_total") or "",
            funding_stage=r.get("funding_stage") or "",
            headquarters_location=r.get("headquarters_location") or "",
            status=r.get("status") or "active",
        )


@dataclass
class CompanyIdentifier:
    """A company identifier (domain, etc.)."""

    company_id: str
    type: str = "domain"
    value: str = ""
    is_primary: bool = False
    source: str = ""

    def to_row(self, *, identifier_id: str | None = None) -> dict:
        now = _now_iso()
        return {
            "id": identifier_id or str(uuid.uuid4()),
            "company_id": self.company_id,
            "type": self.type,
            "value": self.value,
            "is_primary": 1 if self.is_primary else 0,
            "source": self.source or None,
            "created_at": now,
            "updated_at": now,
        }

    @classmethod
    def from_row(cls, row) -> CompanyIdentifier:
        r = dict(row)
        return cls(
            company_id=r["company_id"],
            type=r.get("type") or "domain",
            value=r.get("value") or "",
            is_primary=bool(r.get("is_primary", 0)),
            source=r.get("source") or "",
        )


@dataclass
class CompanyHierarchy:
    """A parent/child organizational relationship between companies."""

    parent_company_id: str
    child_company_id: str
    hierarchy_type: str = "subsidiary"
    effective_date: str = ""
    end_date: str = ""
    metadata: str = ""

    def to_row(
        self,
        *,
        hierarchy_id: str | None = None,
        created_by: str | None = None,
        updated_by: str | None = None,
    ) -> dict:
        now = _now_iso()
        return {
            "id": hierarchy_id or str(uuid.uuid4()),
            "parent_company_id": self.parent_company_id,
            "child_company_id": self.child_company_id,
            "hierarchy_type": self.hierarchy_type,
            "effective_date": self.effective_date or None,
            "end_date": self.end_date or None,
            "metadata": self.metadata or None,
            "created_by": created_by,
            "updated_by": updated_by,
            "created_at": now,
            "updated_at": now,
        }

    @classmethod
    def from_row(cls, row) -> CompanyHierarchy:
        r = dict(row)
        return cls(
            parent_company_id=r["parent_company_id"],
            child_company_id=r["child_company_id"],
            hierarchy_type=r.get("hierarchy_type") or "subsidiary",
            effective_date=r.get("effective_date") or "",
            end_date=r.get("end_date") or "",
            metadata=r.get("metadata") or "",
        )


@dataclass
class Event:
    """A calendar event (meeting, birthday, anniversary, etc.)."""

    title: str
    event_type: str = "meeting"
    description: str = ""
    start_date: str = ""
    start_datetime: str = ""
    end_date: str = ""
    end_datetime: str = ""
    is_all_day: bool = False
    timezone: str = ""
    recurrence_rule: str = ""
    recurrence_type: str = "none"
    recurring_event_id: str | None = None
    location: str = ""
    provider_event_id: str = ""
    provider_calendar_id: str = ""
    account_id: str | None = None
    source: str = "manual"
    status: str = "confirmed"

    def to_row(
        self,
        *,
        event_id: str | None = None,
        created_by: str | None = None,
        updated_by: str | None = None,
    ) -> dict:
        now = _now_iso()
        return {
            "id": event_id or str(uuid.uuid4()),
            "title": self.title,
            "description": self.description or None,
            "event_type": self.event_type,
            "start_date": self.start_date or None,
            "start_datetime": self.start_datetime or None,
            "end_date": self.end_date or None,
            "end_datetime": self.end_datetime or None,
            "is_all_day": 1 if self.is_all_day else 0,
            "timezone": self.timezone or None,
            "recurrence_rule": self.recurrence_rule or None,
            "recurrence_type": self.recurrence_type,
            "recurring_event_id": self.recurring_event_id,
            "location": self.location or None,
            "provider_event_id": self.provider_event_id or None,
            "provider_calendar_id": self.provider_calendar_id or None,
            "account_id": self.account_id,
            "source": self.source,
            "status": self.status,
            "created_by": created_by,
            "updated_by": updated_by,
            "created_at": now,
            "updated_at": now,
        }

    @classmethod
    def from_row(cls, row) -> Event:
        r = dict(row)
        return cls(
            title=r.get("title") or "",
            event_type=r.get("event_type") or "meeting",
            description=r.get("description") or "",
            start_date=r.get("start_date") or "",
            start_datetime=r.get("start_datetime") or "",
            end_date=r.get("end_date") or "",
            end_datetime=r.get("end_datetime") or "",
            is_all_day=bool(r.get("is_all_day", 0)),
            timezone=r.get("timezone") or "",
            recurrence_rule=r.get("recurrence_rule") or "",
            recurrence_type=r.get("recurrence_type") or "none",
            recurring_event_id=r.get("recurring_event_id"),
            location=r.get("location") or "",
            provider_event_id=r.get("provider_event_id") or "",
            provider_calendar_id=r.get("provider_calendar_id") or "",
            account_id=r.get("account_id"),
            source=r.get("source") or "manual",
            status=r.get("status") or "confirmed",
        )


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
