"""Entity field registry — defines available fields per entity type.

Each entity type declares its main table, JOINs, fields (with SQL
expressions), default columns, sort, and search configuration. The
query engine uses this to build entity-agnostic SELECT statements.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class FieldDef:
    """A single queryable field for an entity type."""

    label: str
    sql: str
    type: str = "text"  # text, number, datetime, select, hidden
    sortable: bool = False
    filterable: bool = False
    link: str | None = None  # URL template, e.g. "/contacts/{id}"


@dataclass(frozen=True)
class EntityDef:
    """Schema definition for one entity type in the views engine."""

    table: str
    alias: str
    label: str
    detail_url: str
    fields: dict[str, FieldDef]
    default_columns: list[str]
    default_sort: tuple[str, str]  # (field_key, "asc"|"desc")
    search_fields: list[str]
    base_joins: list[str] = field(default_factory=list)
    group_by: str | None = None
    search_subquery: str | None = None  # extra subquery for search


ENTITY_TYPES: dict[str, EntityDef] = {
    # -----------------------------------------------------------------
    # Contacts
    # -----------------------------------------------------------------
    "contact": EntityDef(
        table="contacts",
        alias="c",
        label="Contacts",
        detail_url="/contacts/{id}",
        base_joins=[
            "LEFT JOIN contact_companies ccx ON ccx.contact_id = c.id "
            "AND ccx.is_primary = 1 AND ccx.is_current = 1",
            "LEFT JOIN companies co ON co.id = ccx.company_id",
        ],
        group_by="c.id",
        fields={
            "name": FieldDef(
                label="Name",
                sql="c.name",
                type="text",
                sortable=True,
                filterable=True,
                link="/contacts/{id}",
            ),
            "email": FieldDef(
                label="Email",
                sql=(
                    "(SELECT ci2.value FROM contact_identifiers ci2 "
                    "WHERE ci2.contact_id = c.id AND ci2.type = 'email' "
                    "ORDER BY ci2.is_primary DESC, ci2.created_at ASC LIMIT 1)"
                ),
                type="text",
                sortable=True,
                filterable=True,
            ),
            "company_name": FieldDef(
                label="Company",
                sql="co.name",
                type="text",
                sortable=True,
                filterable=True,
                link="/companies/{company_id}",
            ),
            "company_id": FieldDef(
                label="Company ID",
                sql="co.id",
                type="hidden",
            ),
            "phone": FieldDef(
                label="Phone",
                sql=(
                    "(SELECT pn.number FROM phone_numbers pn "
                    "WHERE pn.entity_type = 'contact' AND pn.entity_id = c.id "
                    "AND pn.is_current = 1 ORDER BY pn.created_at ASC LIMIT 1)"
                ),
                type="text",
            ),
            "source": FieldDef(
                label="Source",
                sql="c.source",
                type="text",
                filterable=True,
            ),
            "status": FieldDef(
                label="Status",
                sql="c.status",
                type="text",
                filterable=True,
            ),
            "score": FieldDef(
                label="Score",
                sql=(
                    "(SELECT es.score_value FROM entity_scores es "
                    "WHERE es.entity_type = 'contact' AND es.entity_id = c.id "
                    "AND es.score_type = 'relationship_strength' LIMIT 1)"
                ),
                type="number",
                sortable=True,
            ),
            "created_at": FieldDef(
                label="Created",
                sql="c.created_at",
                type="datetime",
                sortable=True,
            ),
        },
        default_columns=["name", "email", "company_name", "company_id", "score", "source"],
        default_sort=("name", "asc"),
        search_fields=["c.name", "co.name"],
        search_subquery=(
            "(SELECT ci3.value FROM contact_identifiers ci3 "
            "WHERE ci3.contact_id = c.id AND ci3.type = 'email' "
            "AND ci3.value LIKE ? LIMIT 1)"
        ),
    ),

    # -----------------------------------------------------------------
    # Companies
    # -----------------------------------------------------------------
    "company": EntityDef(
        table="companies",
        alias="co",
        label="Companies",
        detail_url="/companies/{id}",
        fields={
            "name": FieldDef(
                label="Name",
                sql="co.name",
                type="text",
                sortable=True,
                filterable=True,
                link="/companies/{id}",
            ),
            "domain": FieldDef(
                label="Domain",
                sql="co.domain",
                type="text",
                sortable=True,
                filterable=True,
            ),
            "industry": FieldDef(
                label="Industry",
                sql="co.industry",
                type="text",
                sortable=True,
                filterable=True,
            ),
            "website": FieldDef(
                label="Website",
                sql="co.website",
                type="text",
            ),
            "status": FieldDef(
                label="Status",
                sql="co.status",
                type="text",
                filterable=True,
            ),
            "size_range": FieldDef(
                label="Size",
                sql="co.size_range",
                type="text",
                filterable=True,
            ),
            "headquarters_location": FieldDef(
                label="HQ Location",
                sql="co.headquarters_location",
                type="text",
            ),
            "score": FieldDef(
                label="Score",
                sql=(
                    "(SELECT es.score_value FROM entity_scores es "
                    "WHERE es.entity_type = 'company' AND es.entity_id = co.id "
                    "AND es.score_type = 'relationship_strength' LIMIT 1)"
                ),
                type="number",
                sortable=True,
            ),
            "created_at": FieldDef(
                label="Created",
                sql="co.created_at",
                type="datetime",
                sortable=True,
            ),
        },
        default_columns=["name", "domain", "industry", "score", "status"],
        default_sort=("name", "asc"),
        search_fields=["co.name", "co.domain"],
    ),

    # -----------------------------------------------------------------
    # Conversations
    # -----------------------------------------------------------------
    "conversation": EntityDef(
        table="conversations",
        alias="conv",
        label="Conversations",
        detail_url="/conversations/{id}",
        base_joins=[
            "LEFT JOIN topics t ON t.id = conv.topic_id",
        ],
        fields={
            "title": FieldDef(
                label="Subject",
                sql="conv.title",
                type="text",
                sortable=True,
                filterable=True,
                link="/conversations/{id}",
            ),
            "status": FieldDef(
                label="Status",
                sql="conv.status",
                type="text",
                filterable=True,
            ),
            "triage_result": FieldDef(
                label="Triage",
                sql="conv.triage_result",
                type="text",
                filterable=True,
            ),
            "account_name": FieldDef(
                label="Account",
                sql=(
                    "(SELECT COALESCE(pa.display_name, pa.email_address, pa.phone_number) "
                    "FROM conversation_communications cc2 "
                    "JOIN communications comm2 ON comm2.id = cc2.communication_id "
                    "JOIN provider_accounts pa ON pa.id = comm2.account_id "
                    "WHERE cc2.conversation_id = conv.id LIMIT 1)"
                ),
                type="text",
            ),
            "initiator": FieldDef(
                label="Initiator",
                sql=(
                    "(SELECT COALESCE(c_init.name, comm_init.sender_name, comm_init.sender_address) "
                    "FROM conversation_communications cc_init "
                    "JOIN communications comm_init ON comm_init.id = cc_init.communication_id "
                    "LEFT JOIN contact_identifiers ci_init "
                    "ON ci_init.type = 'email' AND ci_init.value = comm_init.sender_address "
                    "LEFT JOIN contacts c_init ON c_init.id = ci_init.contact_id "
                    "WHERE cc_init.conversation_id = conv.id "
                    "ORDER BY comm_init.timestamp ASC LIMIT 1)"
                ),
                type="text",
                link="/contacts/{initiator_contact_id}",
            ),
            "initiator_contact_id": FieldDef(
                label="Initiator Contact ID",
                sql=(
                    "(SELECT ci_init2.contact_id "
                    "FROM conversation_communications cc_init2 "
                    "JOIN communications comm_init2 ON comm_init2.id = cc_init2.communication_id "
                    "LEFT JOIN contact_identifiers ci_init2 "
                    "ON ci_init2.type = 'email' AND ci_init2.value = comm_init2.sender_address "
                    "WHERE cc_init2.conversation_id = conv.id "
                    "ORDER BY comm_init2.timestamp ASC LIMIT 1)"
                ),
                type="hidden",
            ),
            "topic_name": FieldDef(
                label="Topic",
                sql="t.name",
                type="text",
                filterable=True,
            ),
            "communication_count": FieldDef(
                label="Comm Count",
                sql="conv.communication_count",
                type="number",
            ),
            "ai_status": FieldDef(
                label="AI Status",
                sql="conv.ai_status",
                type="text",
            ),
            "message_count": FieldDef(
                label="Messages",
                sql="conv.message_count",
                type="number",
                sortable=True,
            ),
            "participant_count": FieldDef(
                label="Participants",
                sql="conv.participant_count",
                type="number",
                sortable=True,
            ),
            "first_activity_at": FieldDef(
                label="First Activity",
                sql="conv.first_activity_at",
                type="datetime",
                sortable=True,
            ),
            "last_activity_at": FieldDef(
                label="Last Activity",
                sql="conv.last_activity_at",
                type="datetime",
                sortable=True,
            ),
            "ai_summary": FieldDef(
                label="AI Summary",
                sql="conv.ai_summary",
                type="text",
            ),
            "created_at": FieldDef(
                label="Created",
                sql="conv.created_at",
                type="datetime",
                sortable=True,
            ),
        },
        default_columns=[
            "title", "initiator", "initiator_contact_id", "ai_status", "status",
            "topic_name", "communication_count", "last_activity_at",
        ],
        default_sort=("last_activity_at", "desc"),
        search_fields=["conv.title"],
    ),

    # -----------------------------------------------------------------
    # Communications
    # -----------------------------------------------------------------
    "communication": EntityDef(
        table="communications",
        alias="comm",
        label="Communications",
        detail_url="/communications/{id}",
        fields={
            "channel": FieldDef(
                label="Type",
                sql="comm.channel",
                type="text",
                filterable=True,
            ),
            "direction": FieldDef(
                label="Direction",
                sql="comm.direction",
                type="text",
                filterable=True,
            ),
            "sender": FieldDef(
                label="From",
                sql="COALESCE(comm.sender_name, comm.sender_address)",
                type="text",
                sortable=True,
                filterable=True,
            ),
            "sender_name": FieldDef(
                label="Sender Name",
                sql="comm.sender_name",
                type="text",
            ),
            "sender_address": FieldDef(
                label="From Address",
                sql="comm.sender_address",
                type="text",
                filterable=True,
            ),
            "to_addresses": FieldDef(
                label="To",
                sql=(
                    "(SELECT GROUP_CONCAT(cp.address, ', ') "
                    "FROM communication_participants cp "
                    "WHERE cp.communication_id = comm.id AND cp.role = 'to')"
                ),
                type="text",
            ),
            "subject": FieldDef(
                label="Subject",
                sql="comm.subject",
                type="text",
                sortable=True,
                filterable=True,
            ),
            "conversation_id": FieldDef(
                label="Conversation ID",
                sql=(
                    "(SELECT cc.conversation_id "
                    "FROM conversation_communications cc "
                    "WHERE cc.communication_id = comm.id LIMIT 1)"
                ),
                type="hidden",
            ),
            "conversation_title": FieldDef(
                label="Conversation",
                sql=(
                    "(SELECT conv.title "
                    "FROM conversations conv "
                    "JOIN conversation_communications cc ON cc.conversation_id = conv.id "
                    "WHERE cc.communication_id = comm.id LIMIT 1)"
                ),
                type="text",
                link="/conversations/{conversation_id}",
            ),
            "snippet": FieldDef(
                label="Preview",
                sql="comm.snippet",
                type="text",
            ),
            "timestamp": FieldDef(
                label="Date",
                sql="comm.timestamp",
                type="datetime",
                sortable=True,
            ),
            "is_read": FieldDef(
                label="Read",
                sql="comm.is_read",
                type="number",
                filterable=True,
            ),
            "created_at": FieldDef(
                label="Created",
                sql="comm.created_at",
                type="datetime",
                sortable=True,
            ),
        },
        default_columns=[
            "channel", "sender_name", "sender_address", "to_addresses",
            "subject", "conversation_id", "conversation_title",
            "timestamp", "direction", "snippet",
        ],
        default_sort=("timestamp", "desc"),
        search_fields=["comm.subject", "comm.sender_address", "comm.sender_name"],
    ),

    # -----------------------------------------------------------------
    # Events
    # -----------------------------------------------------------------
    "event": EntityDef(
        table="events",
        alias="e",
        label="Events",
        detail_url="/events/{id}",
        base_joins=[
            "LEFT JOIN provider_accounts pa ON pa.id = e.account_id",
        ],
        fields={
            "title": FieldDef(
                label="Title",
                sql="e.title",
                type="text",
                sortable=True,
                filterable=True,
                link="/events/{id}",
            ),
            "event_type": FieldDef(
                label="Type",
                sql="e.event_type",
                type="text",
                filterable=True,
            ),
            "start": FieldDef(
                label="Date",
                sql="COALESCE(e.start_datetime, e.start_date)",
                type="datetime",
                sortable=True,
            ),
            "start_datetime": FieldDef(
                label="Start DateTime",
                sql="e.start_datetime",
                type="datetime",
            ),
            "start_date": FieldDef(
                label="Start Date",
                sql="e.start_date",
                type="datetime",
            ),
            "end": FieldDef(
                label="End",
                sql="COALESCE(e.end_datetime, e.end_date)",
                type="datetime",
                sortable=True,
            ),
            "location": FieldDef(
                label="Location",
                sql="e.location",
                type="text",
                filterable=True,
            ),
            "status": FieldDef(
                label="Status",
                sql="e.status",
                type="text",
                filterable=True,
            ),
            "source": FieldDef(
                label="Source",
                sql="e.source",
                type="text",
                filterable=True,
            ),
            "account_name": FieldDef(
                label="Account",
                sql="COALESCE(pa.display_name, pa.email_address)",
                type="text",
            ),
            "provider_calendar_id": FieldDef(
                label="Calendar",
                sql="e.provider_calendar_id",
                type="hidden",
            ),
            "created_at": FieldDef(
                label="Created",
                sql="e.created_at",
                type="datetime",
                sortable=True,
            ),
        },
        default_columns=[
            "title", "event_type", "start", "start_datetime", "start_date",
            "location", "status", "source", "account_name", "provider_calendar_id",
        ],
        default_sort=("start", "desc"),
        search_fields=["e.title", "e.location"],
    ),
}
