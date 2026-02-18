#!/usr/bin/env python3
"""Migrate the CRMExtender database from v15 to v16.

Adds the Views & Grid system tables: data_sources, views (rebuilt),
view_columns, view_filters. Seeds system data sources and default views.

Usage:
    python3 -m poc.migrate_to_v16 [--db PATH] [--dry-run]
"""

from __future__ import annotations

import argparse
import shutil
import sqlite3
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

DEFAULT_DB = Path("data/crm_extender.db")

# Default columns per entity type (field_key list)
_DEFAULT_COLUMNS = {
    "contact": ["name", "email", "company_name", "score", "source"],
    "company": ["name", "domain", "industry", "score", "status"],
    "conversation": ["title", "status", "message_count", "last_activity_at"],
    "communication": ["channel", "sender", "subject", "timestamp"],
    "event": ["title", "event_type", "start", "location", "status"],
}

_DEFAULT_SORT = {
    "contact": ("name", "asc"),
    "company": ("name", "asc"),
    "conversation": ("last_activity_at", "desc"),
    "communication": ("timestamp", "desc"),
    "event": ("start", "desc"),
}


def migrate(db_path: Path, *, dry_run: bool = False) -> None:
    """Run the full v15 -> v16 migration."""
    if not db_path.exists():
        print(f"Error: Database not found at {db_path}")
        sys.exit(1)

    backup_path = db_path.with_suffix(
        f".v15-backup-{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
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
    now = datetime.now(timezone.utc).isoformat()

    # -------------------------------------------------------------------
    # Step 1: Create data_sources table
    # -------------------------------------------------------------------
    print("\nStep 1: Creating data_sources table...")
    conn.execute("""\
        CREATE TABLE IF NOT EXISTS data_sources (
            id          TEXT PRIMARY KEY,
            customer_id TEXT REFERENCES customers(id),
            entity_type TEXT NOT NULL,
            name        TEXT NOT NULL,
            is_system   INTEGER DEFAULT 0,
            created_by  TEXT,
            created_at  TEXT NOT NULL,
            updated_at  TEXT NOT NULL
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_data_sources_entity "
        "ON data_sources(customer_id, entity_type)"
    )
    print("  data_sources table created.")

    # -------------------------------------------------------------------
    # Step 2: Rebuild views table (drop old simple views table)
    # -------------------------------------------------------------------
    print("\nStep 2: Rebuilding views table...")
    conn.execute("PRAGMA legacy_alter_table = ON")
    conn.execute("DROP TABLE IF EXISTS alerts")  # depends on old views
    conn.execute("DROP TABLE IF EXISTS views")
    conn.execute("PRAGMA legacy_alter_table = OFF")

    conn.execute("""\
        CREATE TABLE views (
            id              TEXT PRIMARY KEY,
            customer_id     TEXT REFERENCES customers(id),
            data_source_id  TEXT NOT NULL REFERENCES data_sources(id),
            name            TEXT NOT NULL,
            view_type       TEXT NOT NULL DEFAULT 'list'
                CHECK(view_type IN ('list')),
            owner_id        TEXT NOT NULL REFERENCES users(id),
            visibility      TEXT DEFAULT 'personal'
                CHECK(visibility IN ('personal', 'shared')),
            is_default      INTEGER DEFAULT 0,
            sort_field       TEXT,
            sort_direction   TEXT DEFAULT 'asc'
                CHECK(sort_direction IN ('asc', 'desc')),
            search_query    TEXT DEFAULT '',
            per_page        INTEGER DEFAULT 50,
            created_at      TEXT NOT NULL,
            updated_at      TEXT NOT NULL
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_views_owner "
        "ON views(owner_id, data_source_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_views_customer "
        "ON views(customer_id, data_source_id)"
    )
    print("  views table rebuilt.")

    # -------------------------------------------------------------------
    # Step 3: Create view_columns table
    # -------------------------------------------------------------------
    print("\nStep 3: Creating view_columns table...")
    conn.execute("""\
        CREATE TABLE IF NOT EXISTS view_columns (
            id             TEXT PRIMARY KEY,
            view_id        TEXT NOT NULL REFERENCES views(id) ON DELETE CASCADE,
            field_key      TEXT NOT NULL,
            position       INTEGER NOT NULL,
            width_px       INTEGER,
            label_override TEXT
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_view_columns_view "
        "ON view_columns(view_id, position)"
    )
    print("  view_columns table created.")

    # -------------------------------------------------------------------
    # Step 4: Create view_filters table
    # -------------------------------------------------------------------
    print("\nStep 4: Creating view_filters table...")
    conn.execute("""\
        CREATE TABLE IF NOT EXISTS view_filters (
            id        TEXT PRIMARY KEY,
            view_id   TEXT NOT NULL REFERENCES views(id) ON DELETE CASCADE,
            field_key TEXT NOT NULL,
            operator  TEXT NOT NULL,
            value     TEXT,
            position  INTEGER NOT NULL
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_view_filters_view "
        "ON view_filters(view_id, position)"
    )
    print("  view_filters table created.")

    # -------------------------------------------------------------------
    # Step 5: Seed system data sources for each customer
    # -------------------------------------------------------------------
    print("\nStep 5: Seeding system data sources...")
    customers = conn.execute("SELECT id FROM customers").fetchall()
    entity_types = ["contact", "company", "conversation", "communication", "event"]
    entity_labels = {
        "contact": "Contacts",
        "company": "Companies",
        "conversation": "Conversations",
        "communication": "Communications",
        "event": "Events",
    }
    ds_count = 0
    for cust in customers:
        cust_id = cust["id"]
        for et in entity_types:
            ds_id = f"ds-{et}-{cust_id}"
            conn.execute(
                "INSERT OR IGNORE INTO data_sources "
                "(id, customer_id, entity_type, name, is_system, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, 1, ?, ?)",
                (ds_id, cust_id, et, entity_labels[et], now, now),
            )
            ds_count += 1
    print(f"  Created {ds_count} system data sources.")

    # -------------------------------------------------------------------
    # Step 6: Create default views for each user
    # -------------------------------------------------------------------
    print("\nStep 6: Creating default views for each user...")
    users = conn.execute("SELECT id, customer_id FROM users").fetchall()
    view_count = 0
    for user in users:
        user_id = user["id"]
        cust_id = user["customer_id"]
        for et in entity_types:
            ds_id = f"ds-{et}-{cust_id}"
            view_id = f"view-{et}-{user_id}"
            sort_field, sort_dir = _DEFAULT_SORT[et]
            conn.execute(
                "INSERT OR IGNORE INTO views "
                "(id, customer_id, data_source_id, name, view_type, owner_id, "
                " visibility, is_default, sort_field, sort_direction, per_page, "
                " created_at, updated_at) "
                "VALUES (?, ?, ?, ?, 'list', ?, 'personal', 1, ?, ?, 50, ?, ?)",
                (view_id, cust_id, ds_id, f"All {entity_labels[et]}",
                 user_id, sort_field, sort_dir, now, now),
            )
            # Insert default columns
            for pos, field_key in enumerate(_DEFAULT_COLUMNS[et]):
                col_id = f"vc-{view_id}-{field_key}"
                conn.execute(
                    "INSERT OR IGNORE INTO view_columns "
                    "(id, view_id, field_key, position) VALUES (?, ?, ?, ?)",
                    (col_id, view_id, field_key, pos),
                )
            view_count += 1
    print(f"  Created {view_count} default views.")

    # -------------------------------------------------------------------
    # Step 7: Bump schema version
    # -------------------------------------------------------------------
    print("\nStep 7: Bumping schema version to 16...")
    conn.execute("PRAGMA user_version = 16")
    print("  Schema version set to 16.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Migrate CRMExtender database from v15 to v16.",
    )
    parser.add_argument(
        "--db", type=Path, default=DEFAULT_DB,
        help=f"Path to database (default: {DEFAULT_DB})",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Run on a backup copy; do not modify production database.",
    )
    args = parser.parse_args()
    migrate(args.db, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
