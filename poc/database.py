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
-- Email accounts and sync state
CREATE TABLE IF NOT EXISTS email_accounts (
    id                TEXT PRIMARY KEY,
    provider          TEXT NOT NULL,
    email_address     TEXT NOT NULL,
    display_name      TEXT,
    auth_token_path   TEXT,
    sync_cursor       TEXT,
    last_synced_at    TEXT,
    initial_sync_done INTEGER DEFAULT 0,
    backfill_query    TEXT DEFAULT 'newer_than:90d',
    created_at        TEXT NOT NULL,
    updated_at        TEXT NOT NULL,
    UNIQUE(provider, email_address)
);

-- Threaded conversations
CREATE TABLE IF NOT EXISTS conversations (
    id                 TEXT PRIMARY KEY,
    account_id         TEXT NOT NULL REFERENCES email_accounts(id) ON DELETE CASCADE,
    provider_thread_id TEXT,
    subject            TEXT,
    status             TEXT DEFAULT 'active',
    message_count      INTEGER DEFAULT 0,
    first_message_at   TEXT,
    last_message_at    TEXT,
    ai_summary         TEXT,
    ai_status          TEXT,
    ai_action_items    TEXT,
    ai_topics          TEXT,
    ai_summarized_at   TEXT,
    triage_result      TEXT,
    created_at         TEXT NOT NULL,
    updated_at         TEXT NOT NULL,
    UNIQUE(account_id, provider_thread_id)
);

-- Individual email messages
CREATE TABLE IF NOT EXISTS emails (
    id                  TEXT PRIMARY KEY,
    account_id          TEXT NOT NULL REFERENCES email_accounts(id) ON DELETE CASCADE,
    conversation_id     TEXT REFERENCES conversations(id) ON DELETE SET NULL,
    provider_message_id TEXT NOT NULL,
    subject             TEXT,
    sender_address      TEXT NOT NULL,
    sender_name         TEXT,
    date                TEXT,
    body_text           TEXT,
    body_html           TEXT,
    snippet             TEXT,
    header_message_id   TEXT,
    header_references   TEXT,
    header_in_reply_to  TEXT,
    direction           TEXT,
    is_read             INTEGER DEFAULT 0,
    has_attachments     INTEGER DEFAULT 0,
    created_at          TEXT NOT NULL,
    UNIQUE(account_id, provider_message_id)
);

-- Email recipients (To/CC/BCC)
CREATE TABLE IF NOT EXISTS email_recipients (
    email_id TEXT NOT NULL REFERENCES emails(id) ON DELETE CASCADE,
    address  TEXT NOT NULL,
    name     TEXT,
    role     TEXT NOT NULL,
    PRIMARY KEY (email_id, address, role)
);

-- Known contacts
CREATE TABLE IF NOT EXISTS contacts (
    id         TEXT PRIMARY KEY,
    email      TEXT NOT NULL UNIQUE,
    name       TEXT,
    source     TEXT,
    source_id  TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Conversation participants
CREATE TABLE IF NOT EXISTS conversation_participants (
    conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    email_address   TEXT NOT NULL,
    contact_id      TEXT REFERENCES contacts(id) ON DELETE SET NULL,
    message_count   INTEGER DEFAULT 0,
    first_seen_at   TEXT,
    last_seen_at    TEXT,
    PRIMARY KEY (conversation_id, email_address)
);

-- Topics (normalized)
CREATE TABLE IF NOT EXISTS topics (
    id         TEXT PRIMARY KEY,
    name       TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS conversation_topics (
    conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    topic_id        TEXT NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
    confidence      REAL DEFAULT 1.0,
    source          TEXT DEFAULT 'ai',
    created_at      TEXT NOT NULL,
    PRIMARY KEY (conversation_id, topic_id)
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
    account_id            TEXT NOT NULL REFERENCES email_accounts(id) ON DELETE CASCADE,
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
"""

_INDEX_SQL = """\
CREATE INDEX IF NOT EXISTS idx_emails_account        ON emails(account_id);
CREATE INDEX IF NOT EXISTS idx_emails_conversation   ON emails(conversation_id);
CREATE INDEX IF NOT EXISTS idx_emails_date           ON emails(date);
CREATE INDEX IF NOT EXISTS idx_emails_sender         ON emails(sender_address);
CREATE INDEX IF NOT EXISTS idx_emails_message_id_hdr ON emails(header_message_id);

CREATE INDEX IF NOT EXISTS idx_conversations_account  ON conversations(account_id);
CREATE INDEX IF NOT EXISTS idx_conversations_status   ON conversations(status);
CREATE INDEX IF NOT EXISTS idx_conversations_last_msg ON conversations(last_message_at);

CREATE INDEX IF NOT EXISTS idx_recipients_address ON email_recipients(address);

CREATE INDEX IF NOT EXISTS idx_participants_contact ON conversation_participants(contact_id);
CREATE INDEX IF NOT EXISTS idx_participants_email   ON conversation_participants(email_address);

CREATE INDEX IF NOT EXISTS idx_sync_log_account ON sync_log(account_id);

CREATE INDEX IF NOT EXISTS idx_relationships_from ON relationships(from_entity_id);
CREATE INDEX IF NOT EXISTS idx_relationships_to   ON relationships(to_entity_id);
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
