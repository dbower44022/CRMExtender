"""SQLite connection management, schema initialization, and helpers."""

from __future__ import annotations

import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from . import config

log = logging.getLogger(__name__)

_SCHEMA_SQL = """\
-- Customers (tenant)
CREATE TABLE IF NOT EXISTS customers (
    id         TEXT PRIMARY KEY,
    name       TEXT NOT NULL,
    slug       TEXT NOT NULL UNIQUE,
    is_active  INTEGER DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Users (multi-tenant, authentication-ready)
CREATE TABLE IF NOT EXISTS users (
    id            TEXT PRIMARY KEY,
    customer_id   TEXT NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    email         TEXT NOT NULL,
    name          TEXT,
    role          TEXT DEFAULT 'user' CHECK (role IN ('admin', 'user')),
    is_active     INTEGER DEFAULT 1,
    password_hash TEXT,
    google_sub    TEXT,
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL,
    UNIQUE(customer_id, email)
);

-- Provider accounts and sync state (multi-channel)
CREATE TABLE IF NOT EXISTS provider_accounts (
    id                TEXT PRIMARY KEY,
    customer_id       TEXT REFERENCES customers(id) ON DELETE CASCADE,
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
    id                     TEXT PRIMARY KEY,
    customer_id            TEXT REFERENCES customers(id) ON DELETE CASCADE,
    name                   TEXT NOT NULL,
    domain                 TEXT,
    industry               TEXT,
    description            TEXT,
    website                TEXT,
    stock_symbol           TEXT,
    size_range             TEXT,
    employee_count         INTEGER,
    founded_year           INTEGER,
    revenue_range          TEXT,
    funding_total          TEXT,
    funding_stage          TEXT,
    headquarters_location  TEXT,
    status                 TEXT DEFAULT 'active',
    created_by             TEXT REFERENCES users(id) ON DELETE SET NULL,
    updated_by             TEXT REFERENCES users(id) ON DELETE SET NULL,
    created_at             TEXT NOT NULL,
    updated_at             TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_companies_name ON companies(name);

-- Known contacts (identity resolved via contact_identifiers)
CREATE TABLE IF NOT EXISTS contacts (
    id         TEXT PRIMARY KEY,
    customer_id TEXT REFERENCES customers(id) ON DELETE CASCADE,
    name       TEXT,
    source     TEXT,
    status     TEXT DEFAULT 'active',
    created_by TEXT REFERENCES users(id) ON DELETE SET NULL,
    updated_by TEXT REFERENCES users(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Contact-company affiliation roles (user-editable lookup)
CREATE TABLE IF NOT EXISTS contact_company_roles (
    id          TEXT PRIMARY KEY,
    customer_id TEXT REFERENCES customers(id) ON DELETE CASCADE,
    name        TEXT NOT NULL,
    sort_order  INTEGER NOT NULL DEFAULT 0,
    is_system   INTEGER NOT NULL DEFAULT 0,
    created_by  TEXT REFERENCES users(id) ON DELETE SET NULL,
    updated_by  TEXT REFERENCES users(id) ON DELETE SET NULL,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    UNIQUE(customer_id, name)
);

-- Contact-company affiliations (junction table)
CREATE TABLE IF NOT EXISTS contact_companies (
    id         TEXT PRIMARY KEY,
    contact_id TEXT NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
    company_id TEXT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    role_id    TEXT REFERENCES contact_company_roles(id) ON DELETE SET NULL,
    title      TEXT,
    department TEXT,
    is_primary INTEGER NOT NULL DEFAULT 0,
    is_current INTEGER NOT NULL DEFAULT 1,
    started_at TEXT,
    ended_at   TEXT,
    notes      TEXT,
    source     TEXT NOT NULL DEFAULT 'manual',
    created_by TEXT REFERENCES users(id) ON DELETE SET NULL,
    updated_by TEXT REFERENCES users(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(contact_id, company_id, role_id, started_at)
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
    customer_id TEXT REFERENCES customers(id) ON DELETE CASCADE,
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
    customer_id         TEXT REFERENCES customers(id) ON DELETE CASCADE,
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
    is_archived         INTEGER DEFAULT 0,
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
    customer_id TEXT REFERENCES customers(id) ON DELETE CASCADE,
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

-- Relationship type definitions
CREATE TABLE IF NOT EXISTS relationship_types (
    id               TEXT PRIMARY KEY,
    customer_id      TEXT REFERENCES customers(id) ON DELETE CASCADE,
    name             TEXT NOT NULL UNIQUE,
    from_entity_type TEXT NOT NULL DEFAULT 'contact',
    to_entity_type   TEXT NOT NULL DEFAULT 'contact',
    forward_label    TEXT NOT NULL,
    reverse_label    TEXT NOT NULL,
    is_system        INTEGER NOT NULL DEFAULT 0,
    is_bidirectional INTEGER NOT NULL DEFAULT 0,
    description      TEXT,
    created_by       TEXT REFERENCES users(id) ON DELETE SET NULL,
    updated_by       TEXT REFERENCES users(id) ON DELETE SET NULL,
    created_at       TEXT NOT NULL,
    updated_at       TEXT NOT NULL,
    CHECK (from_entity_type IN ('contact', 'company')),
    CHECK (to_entity_type IN ('contact', 'company'))
);

-- Relationships between entities
CREATE TABLE IF NOT EXISTS relationships (
    id                      TEXT PRIMARY KEY,
    relationship_type_id    TEXT NOT NULL REFERENCES relationship_types(id) ON DELETE RESTRICT,
    from_entity_type        TEXT NOT NULL DEFAULT 'contact',
    from_entity_id          TEXT NOT NULL,
    to_entity_type          TEXT NOT NULL DEFAULT 'contact',
    to_entity_id            TEXT NOT NULL,
    paired_relationship_id  TEXT REFERENCES relationships(id) ON DELETE SET NULL,
    source                  TEXT NOT NULL DEFAULT 'manual',
    properties              TEXT,
    created_by              TEXT REFERENCES users(id) ON DELETE SET NULL,
    updated_by              TEXT REFERENCES users(id) ON DELETE SET NULL,
    created_at              TEXT NOT NULL,
    updated_at              TEXT NOT NULL,
    UNIQUE(from_entity_id, to_entity_id, relationship_type_id)
);

-- Events (calendar items: meetings, birthdays, anniversaries, etc.)
CREATE TABLE IF NOT EXISTS events (
    id                   TEXT PRIMARY KEY,
    title                TEXT NOT NULL,
    description          TEXT,
    event_type           TEXT NOT NULL DEFAULT 'meeting',
    start_date           TEXT,
    start_datetime       TEXT,
    end_date             TEXT,
    end_datetime         TEXT,
    is_all_day           INTEGER DEFAULT 0,
    timezone             TEXT,
    recurrence_rule      TEXT,
    recurrence_type      TEXT DEFAULT 'none',
    recurring_event_id   TEXT REFERENCES events(id) ON DELETE SET NULL,
    location             TEXT,
    provider_event_id    TEXT,
    provider_calendar_id TEXT,
    account_id           TEXT REFERENCES provider_accounts(id) ON DELETE SET NULL,
    source               TEXT DEFAULT 'manual',
    status               TEXT DEFAULT 'confirmed',
    created_by           TEXT REFERENCES users(id) ON DELETE SET NULL,
    updated_by           TEXT REFERENCES users(id) ON DELETE SET NULL,
    created_at           TEXT NOT NULL,
    updated_at           TEXT NOT NULL,
    UNIQUE(account_id, provider_event_id),
    CHECK (event_type IN ('meeting','birthday','anniversary','conference','deadline','other')),
    CHECK (recurrence_type IN ('none','daily','weekly','monthly','yearly')),
    CHECK (status IN ('confirmed','tentative','cancelled'))
);

-- Event participants (contacts or companies linked to an event)
CREATE TABLE IF NOT EXISTS event_participants (
    event_id    TEXT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    entity_type TEXT NOT NULL,
    entity_id   TEXT NOT NULL,
    role        TEXT DEFAULT 'attendee',
    rsvp_status TEXT,
    PRIMARY KEY (event_id, entity_type, entity_id),
    CHECK (entity_type IN ('contact', 'company')),
    CHECK (rsvp_status IS NULL OR rsvp_status IN ('accepted','declined','tentative','needs_action'))
);

-- Event <-> Conversation M:N join
CREATE TABLE IF NOT EXISTS event_conversations (
    event_id        TEXT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    created_at      TEXT NOT NULL,
    PRIMARY KEY (event_id, conversation_id)
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

-- Company identifiers (multi-domain per company)
CREATE TABLE IF NOT EXISTS company_identifiers (
    id          TEXT PRIMARY KEY,
    company_id  TEXT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    type        TEXT NOT NULL DEFAULT 'domain',
    value       TEXT NOT NULL,
    is_primary  INTEGER DEFAULT 0,
    source      TEXT,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    UNIQUE(type, value)
);

-- Company hierarchy (parent/child organizational structure)
CREATE TABLE IF NOT EXISTS company_hierarchy (
    id                TEXT PRIMARY KEY,
    parent_company_id TEXT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    child_company_id  TEXT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    hierarchy_type    TEXT NOT NULL,
    effective_date    TEXT,
    end_date          TEXT,
    metadata          TEXT,
    created_by        TEXT REFERENCES users(id) ON DELETE SET NULL,
    updated_by        TEXT REFERENCES users(id) ON DELETE SET NULL,
    created_at        TEXT NOT NULL,
    updated_at        TEXT NOT NULL,
    CHECK (hierarchy_type IN ('subsidiary', 'division', 'acquisition', 'spinoff')),
    CHECK (parent_company_id != child_company_id)
);

-- Company merges audit log
CREATE TABLE IF NOT EXISTS company_merges (
    id                         TEXT PRIMARY KEY,
    surviving_company_id       TEXT NOT NULL REFERENCES companies(id),
    absorbed_company_id        TEXT NOT NULL,
    absorbed_company_snapshot  TEXT NOT NULL,
    contacts_reassigned        INTEGER DEFAULT 0,
    relationships_reassigned   INTEGER DEFAULT 0,
    events_reassigned          INTEGER DEFAULT 0,
    relationships_deduplicated INTEGER DEFAULT 0,
    merged_by                  TEXT REFERENCES users(id) ON DELETE SET NULL,
    merged_at                  TEXT NOT NULL
);

-- Contact merges audit log
CREATE TABLE IF NOT EXISTS contact_merges (
    id                         TEXT PRIMARY KEY,
    surviving_contact_id       TEXT NOT NULL REFERENCES contacts(id),
    absorbed_contact_id        TEXT NOT NULL,
    absorbed_contact_snapshot  TEXT NOT NULL,
    identifiers_transferred    INTEGER DEFAULT 0,
    affiliations_transferred   INTEGER DEFAULT 0,
    conversations_reassigned   INTEGER DEFAULT 0,
    relationships_reassigned   INTEGER DEFAULT 0,
    events_reassigned          INTEGER DEFAULT 0,
    relationships_deduplicated INTEGER DEFAULT 0,
    merged_by                  TEXT REFERENCES users(id) ON DELETE SET NULL,
    merged_at                  TEXT NOT NULL
);

-- Company social profiles
CREATE TABLE IF NOT EXISTS company_social_profiles (
    id              TEXT PRIMARY KEY,
    company_id      TEXT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    platform        TEXT NOT NULL,
    profile_url     TEXT NOT NULL,
    username        TEXT,
    verified        INTEGER DEFAULT 0,
    follower_count  INTEGER,
    bio             TEXT,
    last_scanned_at TEXT,
    last_post_at    TEXT,
    source          TEXT,
    confidence      REAL,
    status          TEXT DEFAULT 'active',
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL,
    UNIQUE(company_id, platform, profile_url)
);

-- Contact social profiles
CREATE TABLE IF NOT EXISTS contact_social_profiles (
    id                 TEXT PRIMARY KEY,
    contact_id         TEXT NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
    platform           TEXT NOT NULL,
    profile_url        TEXT NOT NULL,
    username           TEXT,
    headline           TEXT,
    connection_degree  INTEGER,
    mutual_connections INTEGER,
    verified           INTEGER DEFAULT 0,
    follower_count     INTEGER,
    bio                TEXT,
    last_scanned_at    TEXT,
    last_post_at       TEXT,
    source             TEXT,
    confidence         REAL,
    status             TEXT DEFAULT 'active',
    created_at         TEXT NOT NULL,
    updated_at         TEXT NOT NULL,
    UNIQUE(contact_id, platform, profile_url)
);

-- Enrichment runs (entity-agnostic)
CREATE TABLE IF NOT EXISTS enrichment_runs (
    id            TEXT PRIMARY KEY,
    entity_type   TEXT NOT NULL,
    entity_id     TEXT NOT NULL,
    provider      TEXT NOT NULL,
    status        TEXT NOT NULL DEFAULT 'pending',
    started_at    TEXT,
    completed_at  TEXT,
    error_message TEXT,
    created_at    TEXT NOT NULL,
    CHECK (entity_type IN ('company', 'contact')),
    CHECK (status IN ('pending', 'running', 'completed', 'failed'))
);

-- Enrichment field values (field-level provenance)
CREATE TABLE IF NOT EXISTS enrichment_field_values (
    id                TEXT PRIMARY KEY,
    enrichment_run_id TEXT NOT NULL REFERENCES enrichment_runs(id) ON DELETE CASCADE,
    field_name        TEXT NOT NULL,
    field_value       TEXT,
    confidence        REAL NOT NULL DEFAULT 0.0,
    is_accepted       INTEGER DEFAULT 0,
    created_at        TEXT NOT NULL
);

-- Entity scores (precomputed intelligence)
CREATE TABLE IF NOT EXISTS entity_scores (
    id           TEXT PRIMARY KEY,
    entity_type  TEXT NOT NULL,
    entity_id    TEXT NOT NULL,
    score_type   TEXT NOT NULL,
    score_value  REAL NOT NULL DEFAULT 0.0,
    factors      TEXT,
    computed_at  TEXT NOT NULL,
    triggered_by TEXT,
    CHECK (entity_type IN ('company', 'contact'))
);

-- Monitoring preferences (per-entity tier)
CREATE TABLE IF NOT EXISTS monitoring_preferences (
    id              TEXT PRIMARY KEY,
    entity_type     TEXT NOT NULL,
    entity_id       TEXT NOT NULL,
    monitoring_tier TEXT NOT NULL DEFAULT 'standard',
    tier_source     TEXT NOT NULL DEFAULT 'default',
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL,
    CHECK (entity_type IN ('company', 'contact')),
    CHECK (monitoring_tier IN ('high', 'standard', 'low', 'none')),
    CHECK (tier_source IN ('manual', 'auto_suggested', 'default')),
    UNIQUE(entity_type, entity_id)
);

-- Entity assets (content-addressable storage)
CREATE TABLE IF NOT EXISTS entity_assets (
    id          TEXT PRIMARY KEY,
    entity_type TEXT NOT NULL,
    entity_id   TEXT NOT NULL,
    asset_type  TEXT NOT NULL,
    hash        TEXT NOT NULL,
    mime_type   TEXT NOT NULL,
    file_ext    TEXT NOT NULL,
    source      TEXT,
    created_at  TEXT NOT NULL,
    CHECK (entity_type IN ('company', 'contact')),
    CHECK (asset_type IN ('logo', 'headshot', 'banner'))
);

-- Addresses (entity-agnostic multi-value)
CREATE TABLE IF NOT EXISTS addresses (
    id           TEXT PRIMARY KEY,
    entity_type  TEXT NOT NULL,
    entity_id    TEXT NOT NULL,
    address_type TEXT NOT NULL DEFAULT 'headquarters',
    street       TEXT,
    city         TEXT,
    state        TEXT,
    postal_code  TEXT,
    country      TEXT,
    is_primary   INTEGER DEFAULT 0,
    source       TEXT,
    confidence   REAL,
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL,
    CHECK (entity_type IN ('company', 'contact'))
);

-- Phone numbers (entity-agnostic multi-value)
CREATE TABLE IF NOT EXISTS phone_numbers (
    id          TEXT PRIMARY KEY,
    entity_type TEXT NOT NULL,
    entity_id   TEXT NOT NULL,
    phone_type  TEXT NOT NULL DEFAULT 'main',
    number      TEXT NOT NULL,
    is_primary  INTEGER DEFAULT 0,
    source      TEXT,
    confidence  REAL,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    CHECK (entity_type IN ('company', 'contact'))
);

-- Email addresses (entity-agnostic multi-value)
CREATE TABLE IF NOT EXISTS email_addresses (
    id          TEXT PRIMARY KEY,
    entity_type TEXT NOT NULL,
    entity_id   TEXT NOT NULL,
    email_type  TEXT NOT NULL DEFAULT 'general',
    address     TEXT NOT NULL,
    is_primary  INTEGER DEFAULT 0,
    source      TEXT,
    confidence  REAL,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    CHECK (entity_type IN ('company', 'contact'))
);

-- Sessions (server-side session store)
CREATE TABLE IF NOT EXISTS sessions (
    id          TEXT PRIMARY KEY,
    user_id     TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    customer_id TEXT NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    created_at  TEXT NOT NULL,
    expires_at  TEXT NOT NULL,
    ip_address  TEXT,
    user_agent  TEXT
);

-- User contacts (per-user contact visibility)
CREATE TABLE IF NOT EXISTS user_contacts (
    id         TEXT PRIMARY KEY,
    user_id    TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    contact_id TEXT NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
    visibility TEXT NOT NULL DEFAULT 'public'
        CHECK (visibility IN ('public', 'private')),
    is_owner   INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(user_id, contact_id)
);

-- User companies (per-user company visibility)
CREATE TABLE IF NOT EXISTS user_companies (
    id         TEXT PRIMARY KEY,
    user_id    TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    company_id TEXT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    visibility TEXT NOT NULL DEFAULT 'public'
        CHECK (visibility IN ('public', 'private')),
    is_owner   INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(user_id, company_id)
);

-- User provider accounts (shared account access)
CREATE TABLE IF NOT EXISTS user_provider_accounts (
    id         TEXT PRIMARY KEY,
    user_id    TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    account_id TEXT NOT NULL REFERENCES provider_accounts(id) ON DELETE CASCADE,
    role       TEXT NOT NULL DEFAULT 'owner'
        CHECK (role IN ('owner', 'shared')),
    created_at TEXT NOT NULL,
    UNIQUE(user_id, account_id)
);

-- Conversation shares (explicit sharing)
CREATE TABLE IF NOT EXISTS conversation_shares (
    id              TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    user_id         TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    shared_by       TEXT REFERENCES users(id) ON DELETE SET NULL,
    created_at      TEXT NOT NULL,
    UNIQUE(conversation_id, user_id)
);

-- Settings (unified key-value, system + user)
CREATE TABLE IF NOT EXISTS settings (
    id                  TEXT PRIMARY KEY,
    customer_id         TEXT NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    user_id             TEXT REFERENCES users(id) ON DELETE CASCADE,
    scope               TEXT NOT NULL CHECK (scope IN ('system', 'user')),
    setting_name        TEXT NOT NULL,
    setting_value       TEXT,
    setting_description TEXT,
    setting_default     TEXT,
    created_at          TEXT NOT NULL,
    updated_at          TEXT NOT NULL
);

-- Notes (entity-agnostic, follows addresses/phone_numbers pattern)
CREATE TABLE IF NOT EXISTS notes (
    id                  TEXT PRIMARY KEY,
    customer_id         TEXT NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    entity_type         TEXT NOT NULL CHECK (entity_type IN ('contact','company','conversation','event','project')),
    entity_id           TEXT NOT NULL,
    title               TEXT,
    is_pinned           INTEGER NOT NULL DEFAULT 0,
    current_revision_id TEXT,
    created_by          TEXT REFERENCES users(id) ON DELETE SET NULL,
    updated_by          TEXT REFERENCES users(id) ON DELETE SET NULL,
    created_at          TEXT NOT NULL,
    updated_at          TEXT NOT NULL
);

-- Note revisions (append-only history)
CREATE TABLE IF NOT EXISTS note_revisions (
    id              TEXT PRIMARY KEY,
    note_id         TEXT NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
    revision_number INTEGER NOT NULL,
    content_json    TEXT,
    content_html    TEXT,
    revised_by      TEXT REFERENCES users(id) ON DELETE SET NULL,
    created_at      TEXT NOT NULL,
    UNIQUE(note_id, revision_number)
);

-- Note attachments (uploaded files)
CREATE TABLE IF NOT EXISTS note_attachments (
    id            TEXT PRIMARY KEY,
    note_id       TEXT REFERENCES notes(id) ON DELETE CASCADE,
    filename      TEXT NOT NULL,
    original_name TEXT NOT NULL,
    mime_type     TEXT NOT NULL,
    size_bytes    INTEGER NOT NULL,
    storage_path  TEXT NOT NULL,
    uploaded_by   TEXT REFERENCES users(id) ON DELETE SET NULL,
    created_at    TEXT NOT NULL
);

-- Note mentions (extracted @mentions/entity links)
CREATE TABLE IF NOT EXISTS note_mentions (
    id           TEXT PRIMARY KEY,
    note_id      TEXT NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
    mention_type TEXT NOT NULL CHECK (mention_type IN ('user','contact','company','conversation','event','project')),
    mentioned_id TEXT NOT NULL,
    created_at   TEXT NOT NULL
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
CREATE INDEX IF NOT EXISTS idx_comm_archived       ON communications(is_archived);

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

-- Contact-company affiliations
CREATE INDEX IF NOT EXISTS idx_cc_contact           ON contact_companies(contact_id);
CREATE INDEX IF NOT EXISTS idx_cc_company           ON contact_companies(company_id);
CREATE INDEX IF NOT EXISTS idx_cc_primary           ON contact_companies(contact_id, is_primary, is_current);

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

-- Events
CREATE INDEX IF NOT EXISTS idx_events_type          ON events(event_type);
CREATE INDEX IF NOT EXISTS idx_events_start_dt      ON events(start_datetime);
CREATE INDEX IF NOT EXISTS idx_events_start_date    ON events(start_date);
CREATE INDEX IF NOT EXISTS idx_events_status        ON events(status);
CREATE INDEX IF NOT EXISTS idx_events_account       ON events(account_id);
CREATE INDEX IF NOT EXISTS idx_events_recurring     ON events(recurring_event_id);
CREATE INDEX IF NOT EXISTS idx_events_source        ON events(source);
CREATE INDEX IF NOT EXISTS idx_events_provider      ON events(account_id, provider_event_id);
CREATE INDEX IF NOT EXISTS idx_ep_entity            ON event_participants(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_ec_conversation      ON event_conversations(conversation_id);

-- Relationships
CREATE INDEX IF NOT EXISTS idx_relationships_from   ON relationships(from_entity_id);
CREATE INDEX IF NOT EXISTS idx_relationships_to     ON relationships(to_entity_id);
CREATE INDEX IF NOT EXISTS idx_relationships_type   ON relationships(relationship_type_id);
CREATE INDEX IF NOT EXISTS idx_relationships_source ON relationships(source);
CREATE INDEX IF NOT EXISTS idx_relationships_paired ON relationships(paired_relationship_id);

-- Company identifiers
CREATE INDEX IF NOT EXISTS idx_coid_company         ON company_identifiers(company_id);
CREATE INDEX IF NOT EXISTS idx_coid_lookup           ON company_identifiers(type, value);

-- Company hierarchy
CREATE INDEX IF NOT EXISTS idx_ch_parent             ON company_hierarchy(parent_company_id);
CREATE INDEX IF NOT EXISTS idx_ch_child              ON company_hierarchy(child_company_id);
CREATE INDEX IF NOT EXISTS idx_ch_type               ON company_hierarchy(hierarchy_type);

-- Company merges
CREATE INDEX IF NOT EXISTS idx_cm_surviving          ON company_merges(surviving_company_id);
CREATE INDEX IF NOT EXISTS idx_cm_absorbed           ON company_merges(absorbed_company_id);

-- Contact merges
CREATE INDEX IF NOT EXISTS idx_ctm_surviving         ON contact_merges(surviving_contact_id);
CREATE INDEX IF NOT EXISTS idx_ctm_absorbed          ON contact_merges(absorbed_contact_id);

-- Contact-company affiliation dedup (NULL-safe; SQLite UNIQUE treats NULLs as distinct)
CREATE UNIQUE INDEX IF NOT EXISTS idx_cc_dedup
    ON contact_companies(contact_id, company_id, COALESCE(role_id, ''), COALESCE(started_at, ''));

-- Company social profiles
CREATE INDEX IF NOT EXISTS idx_csp_company           ON company_social_profiles(company_id);
CREATE INDEX IF NOT EXISTS idx_csp_platform          ON company_social_profiles(platform);

-- Contact social profiles
CREATE INDEX IF NOT EXISTS idx_ctsp_contact          ON contact_social_profiles(contact_id);
CREATE INDEX IF NOT EXISTS idx_ctsp_platform         ON contact_social_profiles(platform);

-- Enrichment
CREATE INDEX IF NOT EXISTS idx_er_entity             ON enrichment_runs(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_er_provider           ON enrichment_runs(provider);
CREATE INDEX IF NOT EXISTS idx_er_status             ON enrichment_runs(status);
CREATE INDEX IF NOT EXISTS idx_efv_run               ON enrichment_field_values(enrichment_run_id);
CREATE INDEX IF NOT EXISTS idx_efv_field             ON enrichment_field_values(field_name, is_accepted);

-- Entity scores
CREATE UNIQUE INDEX IF NOT EXISTS idx_es_entity_score ON entity_scores(entity_type, entity_id, score_type);
CREATE INDEX IF NOT EXISTS idx_es_score              ON entity_scores(score_type, score_value);

-- Entity assets
CREATE INDEX IF NOT EXISTS idx_ea_entity             ON entity_assets(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_ea_hash               ON entity_assets(hash);

-- Addresses, phone numbers, email addresses
CREATE INDEX IF NOT EXISTS idx_addr_entity           ON addresses(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_phone_entity          ON phone_numbers(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_email_entity          ON email_addresses(entity_type, entity_id);

-- Sessions
CREATE INDEX IF NOT EXISTS idx_sessions_user         ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_customer     ON sessions(customer_id);
CREATE INDEX IF NOT EXISTS idx_sessions_expires      ON sessions(expires_at);

-- User contacts / companies / provider accounts
CREATE INDEX IF NOT EXISTS idx_user_contacts_user       ON user_contacts(user_id);
CREATE INDEX IF NOT EXISTS idx_user_contacts_contact    ON user_contacts(contact_id);
CREATE INDEX IF NOT EXISTS idx_user_contacts_visibility ON user_contacts(visibility);
CREATE INDEX IF NOT EXISTS idx_user_companies_user      ON user_companies(user_id);
CREATE INDEX IF NOT EXISTS idx_user_companies_company   ON user_companies(company_id);
CREATE INDEX IF NOT EXISTS idx_user_companies_visibility ON user_companies(visibility);
CREATE INDEX IF NOT EXISTS idx_upa_user                 ON user_provider_accounts(user_id);
CREATE INDEX IF NOT EXISTS idx_upa_account              ON user_provider_accounts(account_id);

-- Conversation shares
CREATE INDEX IF NOT EXISTS idx_cs_conversation       ON conversation_shares(conversation_id);
CREATE INDEX IF NOT EXISTS idx_cs_user               ON conversation_shares(user_id);

-- Settings
CREATE INDEX IF NOT EXISTS idx_settings_customer     ON settings(customer_id);
CREATE INDEX IF NOT EXISTS idx_settings_user         ON settings(user_id);
CREATE INDEX IF NOT EXISTS idx_settings_name         ON settings(setting_name);

-- Notes
CREATE INDEX IF NOT EXISTS idx_notes_entity              ON notes(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_notes_customer            ON notes(customer_id);
CREATE INDEX IF NOT EXISTS idx_notes_pinned              ON notes(entity_type, entity_id, is_pinned DESC, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_note_revisions_note       ON note_revisions(note_id);
CREATE INDEX IF NOT EXISTS idx_note_attachments_note     ON note_attachments(note_id);
CREATE INDEX IF NOT EXISTS idx_note_mentions_note        ON note_mentions(note_id);
CREATE INDEX IF NOT EXISTS idx_note_mentions_target      ON note_mentions(mention_type, mentioned_id);

-- Tenant isolation (customer_id)
CREATE INDEX IF NOT EXISTS idx_users_customer            ON users(customer_id);
CREATE INDEX IF NOT EXISTS idx_provider_accounts_customer ON provider_accounts(customer_id);
CREATE INDEX IF NOT EXISTS idx_contacts_customer         ON contacts(customer_id);
CREATE INDEX IF NOT EXISTS idx_companies_customer        ON companies(customer_id);
CREATE INDEX IF NOT EXISTS idx_conversations_customer    ON conversations(customer_id);
CREATE INDEX IF NOT EXISTS idx_projects_customer         ON projects(customer_id);
CREATE INDEX IF NOT EXISTS idx_tags_customer             ON tags(customer_id);
"""

_SETTINGS_INDEX_SQL = """\
CREATE UNIQUE INDEX IF NOT EXISTS idx_settings_system_unique
    ON settings(customer_id, setting_name) WHERE scope = 'system';
CREATE UNIQUE INDEX IF NOT EXISTS idx_settings_user_unique
    ON settings(customer_id, user_id, setting_name) WHERE scope = 'user';
"""


_SEED_RELATIONSHIP_TYPES_SQL = """\
INSERT OR IGNORE INTO relationship_types
    (id, name, from_entity_type, to_entity_type, forward_label, reverse_label,
     is_system, is_bidirectional, description, created_at, updated_at)
VALUES
    ('rt-knows',      'KNOWS',      'contact', 'contact', 'Knows',             'Knows',            1, 1, 'Auto-inferred co-occurrence',      '{now}', '{now}'),
    ('rt-reports-to', 'REPORTS_TO', 'contact', 'contact', 'Has direct report', 'Reports to',       0, 0, 'Reporting chain',                   '{now}', '{now}'),
    ('rt-works-with', 'WORKS_WITH', 'contact', 'contact', 'Works with',        'Works with',       0, 1, 'Peer / collaborator',               '{now}', '{now}'),
    ('rt-partner',    'PARTNER',    'company', 'company', 'Partners with',     'Partners with',    0, 1, 'Business partnership',              '{now}', '{now}'),
    ('rt-vendor',     'VENDOR',     'company', 'company', 'Is a vendor of',    'Is a client of',   0, 0, 'Vendor / client relationship',      '{now}', '{now}'),
    ('rt-affiliated', 'AFFILIATED_WITH', 'contact', 'company', 'Affiliated with', 'Has affiliate',  0, 0, 'Contact-company affiliation',       '{now}', '{now}'),
    ('rt-parent-of',  'PARENT_OF',       'contact', 'contact', 'Parent of',       'Child of',         0, 0, 'Parent / child',                    '{now}', '{now}'),
    ('rt-spouse-of',  'SPOUSE_OF',       'contact', 'contact', 'Spouse of',       'Spouse of',        0, 1, 'Spousal relationship',              '{now}', '{now}'),
    ('rt-sibling-of', 'SIBLING_OF',      'contact', 'contact', 'Sibling of',      'Sibling of',       0, 1, 'Sibling relationship',              '{now}', '{now}'),
    ('rt-uncle-aunt', 'UNCLE_AUNT_OF',   'contact', 'contact', 'Uncle/Aunt of',   'Nephew/Niece of',  0, 0, 'Uncle-aunt / nephew-niece',         '{now}', '{now}');
"""

_SEED_CONTACT_COMPANY_ROLES = [
    ("ccr-employee", "Employee", 0),
    ("ccr-contractor", "Contractor", 1),
    ("ccr-volunteer", "Volunteer", 2),
    ("ccr-advisor", "Advisor", 3),
    ("ccr-board-member", "Board Member", 4),
    ("ccr-investor", "Investor", 5),
    ("ccr-founder", "Founder", 6),
    ("ccr-intern", "Intern", 7),
]


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
        conn.executescript(_SETTINGS_INDEX_SQL)
        # FTS5 virtual table (separate — CREATE VIRTUAL TABLE doesn't support executescript well)
        conn.execute(
            "CREATE VIRTUAL TABLE IF NOT EXISTS notes_fts USING fts5("
            "note_id UNINDEXED, title, content_text, tokenize='porter unicode61')"
        )
        # Defensive: add is_archived column for existing DBs
        cols = {r[1] for r in conn.execute("PRAGMA table_info(communications)")}
        if "is_archived" not in cols:
            conn.execute(
                "ALTER TABLE communications ADD COLUMN is_archived INTEGER DEFAULT 0"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_comm_archived ON communications(is_archived)"
            )
        now = datetime.now(timezone.utc).isoformat()
        conn.executescript(_SEED_RELATIONSHIP_TYPES_SQL.format(now=now))
        # Seed contact_company_roles for each customer
        cust_rows = conn.execute("SELECT id FROM customers").fetchall()
        for cust in cust_rows:
            for role_id, role_name, sort_order in _SEED_CONTACT_COMPANY_ROLES:
                full_id = f"{role_id}-{cust[0]}"
                conn.execute(
                    "INSERT OR IGNORE INTO contact_company_roles "
                    "(id, customer_id, name, sort_order, is_system, created_at, updated_at) "
                    "VALUES (?, ?, ?, ?, 1, ?, ?)",
                    (full_id, cust[0], role_name, sort_order, now, now),
                )
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
