# Event Entity — TDD

**Version:** 1.0
**Last Updated:** 2026-02-23
**Status:** Draft
**Scope:** Entity
**Parent Document:** [event-entity-base-prd.md]
**Product TDD:** [product-tdd.md]

---

## 1. Overview

The Event entity requires entity-specific technical decisions beyond the Product TDD's global defaults. Key areas include: the read model table DDL with temporal and provider indexes, participant junction tables (contacts and companies), conversation linking junction table, the all-participants convenience VIEW, event sourcing, virtual schema, and API design.

---

## 2. Events Read Model Table

### 2.1 Table Definition

```sql
CREATE TABLE events (
    id                  TEXT PRIMARY KEY,        -- evt_ prefixed ULID
    tenant_id           TEXT NOT NULL,
    title               TEXT NOT NULL DEFAULT '(no title)',
    description         TEXT,
    event_type          TEXT NOT NULL DEFAULT 'meeting',
    start_date          DATE,
    start_datetime      TIMESTAMPTZ,
    end_date            DATE,
    end_datetime        TIMESTAMPTZ,
    is_all_day          BOOLEAN NOT NULL DEFAULT false,
    timezone            TEXT,
    recurrence_rule     TEXT,
    recurrence_type     TEXT NOT NULL DEFAULT 'none',
    recurring_event_id  TEXT REFERENCES events(id) ON DELETE SET NULL,
    location            TEXT,
    status              TEXT NOT NULL DEFAULT 'confirmed',
    source              TEXT DEFAULT 'manual',
    provider_event_id   TEXT,
    provider_calendar_id TEXT,
    provider_account_id TEXT REFERENCES provider_accounts(id) ON DELETE SET NULL,

    -- Universal fields
    created_by          TEXT,
    updated_by          TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    archived_at         TIMESTAMPTZ,

    UNIQUE(provider_account_id, provider_event_id)
);
```

### 2.2 Indexes

```sql
CREATE INDEX idx_events_start_dt   ON events (start_datetime);
CREATE INDEX idx_events_start_date ON events (start_date);
CREATE INDEX idx_events_type       ON events (event_type);
CREATE INDEX idx_events_status     ON events (status);
CREATE INDEX idx_events_source     ON events (source);
CREATE INDEX idx_events_provider   ON events (provider_account_id, provider_event_id);
CREATE INDEX idx_events_account    ON events (provider_account_id);
CREATE INDEX idx_events_recurring  ON events (recurring_event_id);
CREATE INDEX idx_events_archived   ON events (archived_at) WHERE archived_at IS NULL;
CREATE INDEX idx_events_tenant     ON events (tenant_id);
```

**Rationale:** Separate start_dt and start_date indexes because all-day and timed events use different columns. Composite provider index supports UPSERT deduplication. Partial archived index for the common active-only query path.

---

## 3. Event→Contact Participation Junction Table

### 3.1 Table Definition

```sql
CREATE TABLE events__contacts_participation (
    id          TEXT PRIMARY KEY,
    source_id   TEXT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    target_id   TEXT NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
    role        TEXT DEFAULT 'attendee',
    rsvp_status TEXT,
    created_by  TEXT,
    updated_by  TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE(source_id, target_id)
);

CREATE INDEX idx_ecp_source ON events__contacts_participation (source_id);
CREATE INDEX idx_ecp_target ON events__contacts_participation (target_id);
```

**Rationale:** UNIQUE prevents duplicate participation. CASCADE from both sides ensures cleanup. Role is free-text to accommodate provider vocabularies without constraint violations during sync.

---

## 4. Event→Company Participation Junction Table

### 4.1 Table Definition

```sql
CREATE TABLE events__companies_participation (
    id          TEXT PRIMARY KEY,
    source_id   TEXT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    target_id   TEXT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    role        TEXT DEFAULT 'host',
    created_by  TEXT,
    updated_by  TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE(source_id, target_id)
);

CREATE INDEX idx_ecmp_source ON events__companies_participation (source_id);
CREATE INDEX idx_ecmp_target ON events__companies_participation (target_id);
```

**Rationale:** No rsvp_status — RSVP is a person-level concept. Company roles typically: host, sponsor, venue.

---

## 5. Event→Conversation Linking Junction Table

### 5.1 Table Definition

```sql
CREATE TABLE events__conversations_link (
    id          TEXT PRIMARY KEY,
    source_id   TEXT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    target_id   TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    created_by  TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE(source_id, target_id)
);

CREATE INDEX idx_ecl_source ON events__conversations_link (source_id);
CREATE INDEX idx_ecl_target ON events__conversations_link (target_id);
```

**Rationale:** No metadata fields — link is a simple association. CASCADE from both sides. Bidirectional indexes for "event's conversations" and "conversation's events" queries.

---

## 6. All-Participants Convenience VIEW

### 6.1 Definition

```sql
CREATE VIEW event_all_participants AS
SELECT
    ecp.source_id   AS event_id,
    'contact'        AS entity_type,
    ecp.target_id    AS entity_id,
    c.first_name || ' ' || c.last_name AS entity_name,
    ecp.role,
    ecp.rsvp_status,
    ecp.created_at
FROM events__contacts_participation ecp
JOIN contacts c ON c.id = ecp.target_id

UNION ALL

SELECT
    ecmp.source_id   AS event_id,
    'company'         AS entity_type,
    ecmp.target_id    AS entity_id,
    cmp.name          AS entity_name,
    ecmp.role,
    NULL              AS rsvp_status,
    ecmp.created_at
FROM events__companies_participation ecmp
JOIN companies cmp ON cmp.id = ecmp.target_id;
```

**Rationale:** Read-only convenience layer for "who's in this meeting?" queries. Used by Event detail page and sync pipeline attendee matching. Does not replace the Relation Type tables.

---

## 7. Event Sourcing

### 7.1 Events Events Table

```sql
CREATE TABLE events_events (
    id          TEXT PRIMARY KEY,
    entity_id   TEXT NOT NULL,
    event_type  TEXT NOT NULL,
    field_name  TEXT,
    old_value   JSONB,
    new_value   JSONB,
    metadata    JSONB,
    actor_id    TEXT,
    actor_type  TEXT,                          -- 'user', 'system', 'sync'
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_events_events_entity ON events_events (entity_id, created_at);
CREATE INDEX idx_events_events_type ON events_events (event_type);
```

### 7.2 Event Types

| Event Type | Description |
|---|---|
| `EventCreated` | New event record created |
| `FieldUpdated` | A field value changed |
| `EventArchived` | Event archived |
| `EventUnarchived` | Event restored |
| `EventSynced` | Event upserted from calendar provider (metadata: provider, calendar ID) |
| `ParticipantAdded` | Contact or company participation created |
| `ParticipantRemoved` | Contact or company participation removed |
| `ConversationLinked` | Conversation linked |
| `ConversationUnlinked` | Conversation unlinked |

---

## 8. Virtual Schema & Data Sources

### 8.1 Virtual Schema

All Event fields from the field registry exposed as virtual columns. The `evt_` prefix enables automatic entity detection in result sets.

### 8.2 Cross-Entity Query Examples

```sql
-- Contacts who attended the most meetings this quarter
SELECT c.first_name, c.last_name, COUNT(*) AS meeting_count
FROM contacts c
JOIN events__contacts_participation ecp ON ecp.target_id = c.id
JOIN events e ON e.id = ecp.source_id
WHERE e.event_type = 'meeting'
  AND e.start_datetime >= '2026-01-01'
GROUP BY c.id, c.first_name, c.last_name
ORDER BY meeting_count DESC;

-- Upcoming events for a specific contact
SELECT e.title, e.event_type, e.start_datetime, e.location
FROM events e
JOIN events__contacts_participation ecp ON ecp.source_id = e.id
WHERE ecp.target_id = $contact_id
  AND e.start_datetime > NOW()
  AND e.archived_at IS NULL
ORDER BY e.start_datetime ASC;

-- Companies hosting conferences
SELECT cmp.name, e.title, e.start_date
FROM companies cmp
JOIN events__companies_participation ecmp ON ecmp.target_id = cmp.id
JOIN events e ON e.id = ecmp.source_id
WHERE e.event_type = 'conference' AND ecmp.role = 'host'
ORDER BY e.start_date DESC;
```

### 8.3 Views Integration

- **Grid View:** Sortable columns for title, type, date, location, status, source.
- **Calendar View:** Month/week/day using start_datetime/start_date.
- **Board View:** Grouped by event_type or status.
- **Timeline View:** Temporal axis using start_datetime.
- **Traversal columns:** "Attendees" via Event→Contact, "Companies" via Event→Company.

---

## 9. API Design

### 9.1 Event Record API

| Endpoint | Method | Description |
|---|---|---|
| `/api/v1/events` | GET | List events (paginated, filterable, sortable) |
| `/api/v1/events` | POST | Create event |
| `/api/v1/events/{id}` | GET | Get event with participants and linked conversations |
| `/api/v1/events/{id}` | PATCH | Update event fields |
| `/api/v1/events/{id}/archive` | POST | Archive |
| `/api/v1/events/{id}/unarchive` | POST | Unarchive |

### 9.2 Participant API

| Endpoint | Method | Description |
|---|---|---|
| `/api/v1/events/{id}/participants` | GET | All participants (uses convenience VIEW) |
| `/api/v1/events/{id}/contacts` | POST | Add contact participant |
| `/api/v1/events/{id}/contacts/{contact_id}` | DELETE | Remove contact participant |
| `/api/v1/events/{id}/companies` | POST | Add company participant |
| `/api/v1/events/{id}/companies/{company_id}` | DELETE | Remove company participant |

### 9.3 Conversation Linking API

| Endpoint | Method | Description |
|---|---|---|
| `/api/v1/events/{id}/conversations` | GET | List linked conversations |
| `/api/v1/events/{id}/conversations` | POST | Link conversation |
| `/api/v1/events/{id}/conversations/{conversation_id}` | DELETE | Unlink conversation |

### 9.4 Sync API

| Endpoint | Method | Description |
|---|---|---|
| `/api/v1/events/sync` | POST | Trigger calendar sync for current user |

---

## 10. Decisions to Be Added by Claude Code

- **RRULE expansion strategy:** Whether to expand RRULEs at query time or pre-compute instances for a rolling window.
- **Cancelled event handling:** Whether sync should auto-archive cancelled events or just set status.
- **Contact stub creation:** Whether unmatched attendee emails should create minimal contact records.
- **Snapshot frequency:** How often to snapshot event records for point-in-time reconstruction performance.
- **Calendar view query optimization:** Indexed date-range queries for month/week/day calendar rendering.
