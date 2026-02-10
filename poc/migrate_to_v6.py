#!/usr/bin/env python3
"""Migrate the CRMExtender database from v5 to v6.

Adds:
- events table (calendar items: meetings, birthdays, anniversaries, etc.)
- event_participants table (contacts/companies linked to events)
- event_conversations table (events linked to conversations)
- Associated indexes

Usage:
    python3 -m poc.migrate_to_v6 [--db PATH] [--dry-run]
"""

from __future__ import annotations

import argparse
import shutil
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

_EVENTS_TABLE_SQL = """\
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
"""

_EVENT_PARTICIPANTS_TABLE_SQL = """\
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
"""

_EVENT_CONVERSATIONS_TABLE_SQL = """\
CREATE TABLE IF NOT EXISTS event_conversations (
    event_id        TEXT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    created_at      TEXT NOT NULL,
    PRIMARY KEY (event_id, conversation_id)
);
"""

_INDEX_SQL = """\
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
"""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def migrate(db_path: Path, *, dry_run: bool = False) -> None:
    """Run the full v5 -> v6 migration."""
    if not db_path.exists():
        print(f"Error: Database not found at {db_path}")
        sys.exit(1)

    # 1. Backup
    backup_path = db_path.with_suffix(
        f".v5-backup-{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
    )
    print(f"Backing up to {backup_path}...")
    shutil.copy2(str(db_path), str(backup_path))
    print(f"  Backup created ({backup_path.stat().st_size:,} bytes)")

    if dry_run:
        db_path = backup_path

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=OFF")

    try:
        _run_migration(conn)
        conn.commit()
        print("\nMigration committed successfully.")
    except Exception:
        conn.rollback()
        print("\nMigration FAILED — rolled back.")
        raise
    finally:
        conn.close()

    if dry_run:
        print(f"\nDry run complete. Changes applied to backup: {backup_path}")
        print("Production database was NOT modified.")
    else:
        print(f"\nProduction database migrated. Backup at: {backup_path}")


def _run_migration(conn: sqlite3.Connection) -> None:
    """Execute all migration steps in order."""
    # Check which tables already exist
    existing_tables = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }

    # -------------------------------------------------------------------
    # Step 1: Create events table
    # -------------------------------------------------------------------
    print("\nStep 1: Creating events table...")
    if "events" in existing_tables:
        print("  Table already exists — skipping.")
    else:
        conn.executescript(_EVENTS_TABLE_SQL)
        print("  Created events table.")

    # -------------------------------------------------------------------
    # Step 2: Create event_participants table
    # -------------------------------------------------------------------
    print("\nStep 2: Creating event_participants table...")
    if "event_participants" in existing_tables:
        print("  Table already exists — skipping.")
    else:
        conn.executescript(_EVENT_PARTICIPANTS_TABLE_SQL)
        print("  Created event_participants table.")

    # -------------------------------------------------------------------
    # Step 3: Create event_conversations table
    # -------------------------------------------------------------------
    print("\nStep 3: Creating event_conversations table...")
    if "event_conversations" in existing_tables:
        print("  Table already exists — skipping.")
    else:
        conn.executescript(_EVENT_CONVERSATIONS_TABLE_SQL)
        print("  Created event_conversations table.")

    # -------------------------------------------------------------------
    # Step 4: Create indexes
    # -------------------------------------------------------------------
    print("\nStep 4: Creating indexes...")
    conn.executescript(_INDEX_SQL)
    print("  Indexes created.")

    # -------------------------------------------------------------------
    # Step 5: Validation
    # -------------------------------------------------------------------
    print("\nStep 5: Validation...")
    conn.execute("PRAGMA foreign_keys=ON")

    # Verify all three tables exist
    post_tables = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }

    errors = []
    for table in ("events", "event_participants", "event_conversations"):
        if table not in post_tables:
            errors.append(f"Table {table} was not created")

    # Verify key columns on events table
    event_cols = {
        row[1]
        for row in conn.execute("PRAGMA table_info(events)").fetchall()
    }
    expected_cols = {
        "id", "title", "event_type", "start_date", "start_datetime",
        "end_date", "end_datetime", "is_all_day", "recurrence_rule",
        "recurrence_type", "provider_event_id", "account_id", "source",
        "status", "created_at", "updated_at",
    }
    missing_cols = expected_cols - event_cols
    if missing_cols:
        errors.append(f"Missing columns on events: {missing_cols}")

    if errors:
        print("\nVALIDATION ERRORS:")
        for e in errors:
            print(f"  ERROR: {e}")
        raise RuntimeError(
            f"Migration validation failed with {len(errors)} error(s)"
        )
    else:
        print("\nAll validations passed!")


def main():
    parser = argparse.ArgumentParser(
        description="Migrate CRMExtender database from v5 to v6 schema (events)"
    )
    parser.add_argument(
        "--db", type=Path,
        help="Path to the SQLite database file",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Apply migration to a backup copy instead of the real database",
    )
    args = parser.parse_args()

    if args.db:
        db_path = args.db
    else:
        from poc import config
        db_path = config.DB_PATH

    migrate(db_path, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
