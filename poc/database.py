"""SQLite connection management, schema initialization, and helpers."""

from __future__ import annotations

import logging
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from . import config

log = logging.getLogger(__name__)

_SCHEMA_SQL = """\
-- Users (minimal; FK target for ownership/audit columns)
CREATE TABLE IF NOT EXISTS users (
    id         TEXT PRIMARY KEY,
    email      TEXT NOT NULL UNIQUE,
    name       TEXT,
    role       TEXT DEFAULT 'member',
    is_active  INTEGER DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Provider accounts and sync state (multi-channel)
CREATE TABLE IF NOT EXISTS provider_accounts (
    id                TEXT PRIMARY KEY,
    provider          TEXT NOT NULL,
    account_type      TEXT NOT NULL DEFAULT 'email',
    email_address     TEXT,
    phone_number      TEXT,
    display_name      TEXT,
    auth_token_path   TEXT,
    sync_cursor       TEXT,
    last_synced_at    TEXT,
    initial_sync_done INTEGER DEFAULT 0,
    backfill_query    TEXT DEFAULT 'newer_than:90d',
    created_at        TEXT NOT NULL,
    updated_at        TEXT NOT NULL,
    UNIQUE(provider, email_address),
    UNIQUE(provider, phone_number)
);

-- Companies
CREATE TABLE IF NOT EXISTS companies (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    domain      TEXT,
    industry    TEXT,
    description TEXT,
    status      TEXT DEFAULT 'active',
    created_by  TEXT REFERENCES users(id) ON DELETE SET NULL,
    updated_by  TEXT REFERENCES users(id) ON DELETE SET NULL,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_companies_name ON companies(name);

-- Known contacts (identity resolved via contact_identifiers)
CREATE TABLE IF NOT EXISTS contacts (
    id         TEXT PRIMARY KEY,
    name       TEXT,
    company    TEXT,
    company_id TEXT REFERENCES companies(id) ON DELETE SET NULL,
    source     TEXT,
    status     TEXT DEFAULT 'active',
    created_by TEXT REFERENCES users(id) ON DELETE SET NULL,
    updated_by TEXT REFERENCES users(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Contact identifiers (email, phone, etc.)
CREATE TABLE IF NOT EXISTS contact_identifiers (
    id         TEXT PRIMARY KEY,
    contact_id TEXT NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
    type       TEXT NOT NULL,
    value      TEXT NOT NULL,
    label      TEXT,
    is_primary INTEGER DEFAULT 0,
    status     TEXT DEFAULT 'active',
    source     TEXT,
    verified   INTEGER DEFAULT 0,
    created_by TEXT REFERENCES users(id) ON DELETE SET NULL,
    updated_by TEXT REFERENCES users(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(type, value)
);

-- Projects (organizational hierarchy, adjacency list)
CREATE TABLE IF NOT EXISTS projects (
    id          TEXT PRIMARY KEY,
    parent_id   TEXT REFERENCES projects(id) ON DELETE CASCADE,
    name        TEXT NOT NULL,
    description TEXT,
    status      TEXT DEFAULT 'active',
    owner_id    TEXT REFERENCES users(id) ON DELETE SET NULL,
    created_by  TEXT REFERENCES users(id) ON DELETE SET NULL,
    updated_by  TEXT REFERENCES users(id) ON DELETE SET NULL,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

-- Topics (organizational grouping within a project)
CREATE TABLE IF NOT EXISTS topics (
    id          TEXT PRIMARY KEY,
    project_id  TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    name        TEXT NOT NULL,
    description TEXT,
    source      TEXT DEFAULT 'user',
    created_by  TEXT REFERENCES users(id) ON DELETE SET NULL,
    updated_by  TEXT REFERENCES users(id) ON DELETE SET NULL,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

-- Threaded conversations (account-independent)
CREATE TABLE IF NOT EXISTS conversations (
    id                  TEXT PRIMARY KEY,
    topic_id            TEXT REFERENCES topics(id) ON DELETE SET NULL,
    title               TEXT,
    status              TEXT DEFAULT 'active',
    communication_count INTEGER DEFAULT 0,
    participant_count   INTEGER DEFAULT 0,
    first_activity_at   TEXT,
    last_activity_at    TEXT,
    ai_summary          TEXT,
    ai_status           TEXT,
    ai_action_items     TEXT,
    ai_topics           TEXT,
    ai_summarized_at    TEXT,
    triage_result       TEXT,
    dismissed           INTEGER DEFAULT 0,
    dismissed_reason    TEXT,
    dismissed_at        TEXT,
    dismissed_by        TEXT REFERENCES users(id) ON DELETE SET NULL,
    created_by          TEXT REFERENCES users(id) ON DELETE SET NULL,
    updated_by          TEXT REFERENCES users(id) ON DELETE SET NULL,
    created_at          TEXT NOT NULL,
    updated_at          TEXT NOT NULL
);

-- Conversation participants
CREATE TABLE IF NOT EXISTS conversation_participants (
    conversation_id     TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    address             TEXT NOT NULL,
    name                TEXT,
    contact_id          TEXT REFERENCES contacts(id) ON DELETE SET NULL,
    communication_count INTEGER DEFAULT 0,
    first_seen_at       TEXT,
    last_seen_at        TEXT,
    PRIMARY KEY (conversation_id, address)
);

-- Communications (polymorphic, all channel types)
CREATE TABLE IF NOT EXISTS communications (
    id                  TEXT PRIMARY KEY,
    account_id          TEXT REFERENCES provider_accounts(id) ON DELETE SET NULL,
    channel             TEXT NOT NULL,
    timestamp           TEXT NOT NULL,
    content             TEXT,
    direction           TEXT,
    source              TEXT,
    sender_address      TEXT,
    sender_name         TEXT,
    subject             TEXT,
    body_html           TEXT,
    snippet             TEXT,
    provider_message_id TEXT,
    provider_thread_id  TEXT,
    header_message_id   TEXT,
    header_references   TEXT,
    header_in_reply_to  TEXT,
    is_read             INTEGER DEFAULT 0,
    phone_number_from   TEXT,
    phone_number_to     TEXT,
    duration_seconds    INTEGER,
    transcript_source   TEXT,
    note_type           TEXT,
    provider_metadata   TEXT,
    user_metadata       TEXT,
    previous_revision   TEXT REFERENCES communications(id) ON DELETE SET NULL,
    next_revision       TEXT REFERENCES communications(id) ON DELETE SET NULL,
    is_current          INTEGER DEFAULT 1,
    ai_summary          TEXT,
    ai_summarized_at    TEXT,
    triage_result       TEXT,
    created_at          TEXT NOT NULL,
    updated_at          TEXT NOT NULL,
    UNIQUE(account_id, provider_message_id)
);

-- Communication participants (To/CC/BCC/attendees)
CREATE TABLE IF NOT EXISTS communication_participants (
    communication_id TEXT NOT NULL REFERENCES communications(id) ON DELETE CASCADE,
    address          TEXT NOT NULL,
    name             TEXT,
    contact_id       TEXT REFERENCES contacts(id) ON DELETE SET NULL,
    role             TEXT NOT NULL,
    PRIMARY KEY (communication_id, address, role)
);

-- Conversation ↔ Communication M:N join
CREATE TABLE IF NOT EXISTS conversation_communications (
    conversation_id   TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    communication_id  TEXT NOT NULL REFERENCES communications(id) ON DELETE CASCADE,
    display_content   TEXT,
    is_primary        INTEGER DEFAULT 1,
    assignment_source TEXT NOT NULL DEFAULT 'sync',
    confidence        REAL DEFAULT 1.0,
    reviewed          INTEGER DEFAULT 0,
    reviewed_at       TEXT,
    created_at        TEXT NOT NULL,
    PRIMARY KEY (conversation_id, communication_id)
);

-- Attachments
CREATE TABLE IF NOT EXISTS attachments (
    id               TEXT PRIMARY KEY,
    communication_id TEXT NOT NULL REFERENCES communications(id) ON DELETE CASCADE,
    filename         TEXT NOT NULL,
    mime_type        TEXT,
    size_bytes       INTEGER,
    storage_ref      TEXT,
    source           TEXT,
    created_at       TEXT NOT NULL
);

-- Tags (AI-extracted keyword phrases; distinct from hierarchy topics)
CREATE TABLE IF NOT EXISTS tags (
    id         TEXT PRIMARY KEY,
    name       TEXT NOT NULL UNIQUE,
    source     TEXT DEFAULT 'ai',
    created_at TEXT NOT NULL
);

-- Conversation ↔ Tag M:N join
CREATE TABLE IF NOT EXISTS conversation_tags (
    conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    tag_id          TEXT NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    confidence      REAL DEFAULT 1.0,
    source          TEXT DEFAULT 'ai',
    created_at      TEXT NOT NULL,
    PRIMARY KEY (conversation_id, tag_id)
);

-- Views (user-defined saved queries)
CREATE TABLE IF NOT EXISTS views (
    id          TEXT PRIMARY KEY,
    owner_id    TEXT REFERENCES users(id) ON DELETE SET NULL,
    name        TEXT NOT NULL,
    description TEXT,
    query_def   TEXT NOT NULL,
    is_shared   INTEGER DEFAULT 0,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

-- Alerts (notification triggers on views)
CREATE TABLE IF NOT EXISTS alerts (
    id              TEXT PRIMARY KEY,
    view_id         TEXT NOT NULL REFERENCES views(id) ON DELETE CASCADE,
    owner_id        TEXT REFERENCES users(id) ON DELETE SET NULL,
    is_active       INTEGER DEFAULT 1,
    frequency       TEXT NOT NULL,
    aggregation     TEXT DEFAULT 'batched',
    delivery_method TEXT NOT NULL,
    last_triggered  TEXT,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);

-- Inferred relationships between contacts
CREATE TABLE IF NOT EXISTS relationships (
    id                TEXT PRIMARY KEY,
    from_entity_type  TEXT NOT NULL DEFAULT 'contact',
    from_entity_id    TEXT NOT NULL,
    to_entity_type    TEXT NOT NULL DEFAULT 'contact',
    to_entity_id      TEXT NOT NULL,
    relationship_type TEXT NOT NULL DEFAULT 'KNOWS',
    properties        TEXT,
    created_at        TEXT NOT NULL,
    updated_at        TEXT NOT NULL,
    UNIQUE(from_entity_id, to_entity_id, relationship_type)
);

-- Sync audit log
CREATE TABLE IF NOT EXISTS sync_log (
    id                    TEXT PRIMARY KEY,
    account_id            TEXT NOT NULL REFERENCES provider_accounts(id) ON DELETE CASCADE,
    sync_type             TEXT NOT NULL,
    started_at            TEXT NOT NULL,
    completed_at          TEXT,
    messages_fetched      INTEGER DEFAULT 0,
    messages_stored       INTEGER DEFAULT 0,
    conversations_created INTEGER DEFAULT 0,
    conversations_updated INTEGER DEFAULT 0,
    cursor_before         TEXT,
    cursor_after          TEXT,
    status                TEXT DEFAULT 'running',
    error                 TEXT,
    CONSTRAINT valid_status CHECK (status IN ('running', 'completed', 'failed'))
);

-- Assignment corrections (AI learning)
CREATE TABLE IF NOT EXISTS assignment_corrections (
    id                    TEXT PRIMARY KEY,
    communication_id      TEXT NOT NULL REFERENCES communications(id) ON DELETE CASCADE,
    from_conversation_id  TEXT REFERENCES conversations(id) ON DELETE SET NULL,
    to_conversation_id    TEXT REFERENCES conversations(id) ON DELETE SET NULL,
    correction_type       TEXT NOT NULL,
    original_source       TEXT,
    original_confidence   REAL,
    corrected_by          TEXT REFERENCES users(id) ON DELETE SET NULL,
    created_at            TEXT NOT NULL
);

-- Triage corrections (AI learning)
CREATE TABLE IF NOT EXISTS triage_corrections (
    id               TEXT PRIMARY KEY,
    communication_id TEXT NOT NULL REFERENCES communications(id) ON DELETE CASCADE,
    original_result  TEXT,
    corrected_result TEXT,
    correction_type  TEXT NOT NULL,
    sender_address   TEXT,
    sender_domain    TEXT,
    subject          TEXT,
    corrected_by     TEXT REFERENCES users(id) ON DELETE SET NULL,
    created_at       TEXT NOT NULL
);

-- Triage rules (allow/block)
CREATE TABLE IF NOT EXISTS triage_rules (
    id          TEXT PRIMARY KEY,
    rule_type   TEXT NOT NULL,
    match_type  TEXT NOT NULL,
    match_value TEXT NOT NULL,
    source      TEXT NOT NULL,
    confidence  REAL DEFAULT 1.0,
    user_id     TEXT REFERENCES users(id) ON DELETE SET NULL,
    created_at  TEXT NOT NULL
);

-- Conversation corrections (AI learning)
CREATE TABLE IF NOT EXISTS conversation_corrections (
    id                      TEXT PRIMARY KEY,
    conversation_id         TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    correction_type         TEXT NOT NULL,
    reason                  TEXT,
    details                 TEXT,
    participant_addresses   TEXT,
    subject                 TEXT,
    communication_count     INTEGER,
    corrected_by            TEXT REFERENCES users(id) ON DELETE SET NULL,
    created_at              TEXT NOT NULL
);
"""

_INDEX_SQL = """\
-- Communications
CREATE INDEX IF NOT EXISTS idx_comm_account        ON communications(account_id);
CREATE INDEX IF NOT EXISTS idx_comm_channel        ON communications(channel);
CREATE INDEX IF NOT EXISTS idx_comm_timestamp      ON communications(timestamp);
CREATE INDEX IF NOT EXISTS idx_comm_sender         ON communications(sender_address);
CREATE INDEX IF NOT EXISTS idx_comm_thread         ON communications(provider_thread_id);
CREATE INDEX IF NOT EXISTS idx_comm_header_msg_id  ON communications(header_message_id);
CREATE INDEX IF NOT EXISTS idx_comm_current        ON communications(is_current);

-- Conversations
CREATE INDEX IF NOT EXISTS idx_conv_topic          ON conversations(topic_id);
CREATE INDEX IF NOT EXISTS idx_conv_status         ON conversations(status);
CREATE INDEX IF NOT EXISTS idx_conv_last_activity  ON conversations(last_activity_at);
CREATE INDEX IF NOT EXISTS idx_conv_ai_status      ON conversations(ai_status);
CREATE INDEX IF NOT EXISTS idx_conv_triage         ON conversations(triage_result);
CREATE INDEX IF NOT EXISTS idx_conv_needs_processing ON conversations(triage_result, ai_summarized_at);
CREATE INDEX IF NOT EXISTS idx_conv_dismissed      ON conversations(dismissed);

-- Join tables
CREATE INDEX IF NOT EXISTS idx_cc_communication    ON conversation_communications(communication_id);
CREATE INDEX IF NOT EXISTS idx_cc_review           ON conversation_communications(assignment_source, reviewed);
CREATE INDEX IF NOT EXISTS idx_cp_contact          ON conversation_participants(contact_id);
CREATE INDEX IF NOT EXISTS idx_cp_address          ON conversation_participants(address);
CREATE INDEX IF NOT EXISTS idx_commpart_address    ON communication_participants(address);
CREATE INDEX IF NOT EXISTS idx_commpart_contact    ON communication_participants(contact_id);

-- Contact resolution
CREATE INDEX IF NOT EXISTS idx_ci_contact          ON contact_identifiers(contact_id);
CREATE INDEX IF NOT EXISTS idx_ci_status           ON contact_identifiers(status);

-- Companies
CREATE INDEX IF NOT EXISTS idx_companies_domain    ON companies(domain);
CREATE INDEX IF NOT EXISTS idx_contacts_company    ON contacts(company_id);

-- Other tables
CREATE INDEX IF NOT EXISTS idx_projects_parent     ON projects(parent_id);
CREATE INDEX IF NOT EXISTS idx_topics_project      ON topics(project_id);
CREATE INDEX IF NOT EXISTS idx_attachments_comm    ON attachments(communication_id);
CREATE INDEX IF NOT EXISTS idx_sync_log_account    ON sync_log(account_id);
CREATE INDEX IF NOT EXISTS idx_views_owner         ON views(owner_id);
CREATE INDEX IF NOT EXISTS idx_alerts_view         ON alerts(view_id);
CREATE INDEX IF NOT EXISTS idx_triage_rules_match  ON triage_rules(match_type, match_value);

-- Correction tables
CREATE INDEX IF NOT EXISTS idx_ac_communication    ON assignment_corrections(communication_id);
CREATE INDEX IF NOT EXISTS idx_tc_communication    ON triage_corrections(communication_id);
CREATE INDEX IF NOT EXISTS idx_tc_sender_domain    ON triage_corrections(sender_domain);
CREATE INDEX IF NOT EXISTS idx_cc_conversation     ON conversation_corrections(conversation_id);

-- Relationships
CREATE INDEX IF NOT EXISTS idx_relationships_from  ON relationships(from_entity_id);
CREATE INDEX IF NOT EXISTS idx_relationships_to    ON relationships(to_entity_id);
"""


def _db_path() -> Path:
    return config.DB_PATH


def init_db(db_path: Path | None = None) -> None:
    """Create the database file and initialize all tables and indexes."""
    path = db_path or _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(path))
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        conn.executescript(_SCHEMA_SQL)
        conn.executescript(_INDEX_SQL)
        conn.commit()
        log.info("Database initialized at %s", path)
    finally:
        conn.close()


@contextmanager
def get_connection(db_path: Path | None = None) -> Iterator[sqlite3.Connection]:
    """Context manager yielding a SQLite connection with WAL and FK enforcement.

    Commits on clean exit, rolls back on exception.
    """
    path = db_path or _db_path()
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
