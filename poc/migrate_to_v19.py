#!/usr/bin/env python3
"""Migrate the CRMExtender database from v18 to v19.

Adds outbound email infrastructure:
- outbound_email_queue      — draft/send queue for composed emails
- outbound_email_attachments — attachments on outbound emails
- email_signatures          — per-user email signatures
- contact_identifiers gains delivery_status + delivery_status_updated_at
- contacts gains automated_email_opt_out

Usage:
    python3 -m poc.migrate_to_v19 [--db PATH] [--dry-run]
"""

from __future__ import annotations

import argparse
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

DEFAULT_DB = Path("data/crm_extender.db")


def migrate(db_path: Path, *, dry_run: bool = False) -> None:
    """Run the full v18 -> v19 migration."""
    if not db_path.exists():
        print(f"Error: Database not found at {db_path}")
        sys.exit(1)

    backup_path = db_path.with_suffix(
        f".v18-backup-{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
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
    existing_tables = {
        r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
    }

    # -------------------------------------------------------------------
    # Step 1: Create outbound_email_queue table
    # -------------------------------------------------------------------
    if "outbound_email_queue" not in existing_tables:
        print("\nStep 1: Creating outbound_email_queue table...")
        conn.execute("""
            CREATE TABLE outbound_email_queue (
                id                          TEXT PRIMARY KEY,
                customer_id                 TEXT NOT NULL REFERENCES customers(id),
                communication_id            TEXT REFERENCES communications(id),
                from_account_id             TEXT NOT NULL REFERENCES provider_accounts(id),
                to_addresses                TEXT NOT NULL,
                cc_addresses                TEXT,
                bcc_addresses               TEXT,
                subject                     TEXT NOT NULL,
                body_json                   TEXT NOT NULL,
                body_html                   TEXT NOT NULL,
                body_text                   TEXT NOT NULL,
                signature_id                TEXT,
                source_type                 TEXT NOT NULL,
                template_id                 TEXT,
                reply_to_communication_id   TEXT REFERENCES communications(id),
                forward_of_communication_id TEXT REFERENCES communications(id),
                conversation_id             TEXT REFERENCES conversations(id),
                status                      TEXT NOT NULL DEFAULT 'draft',
                scheduled_send_at           TEXT,
                sent_at                     TEXT,
                failure_reason              TEXT,
                retry_count                 INTEGER DEFAULT 0,
                created_at                  TEXT NOT NULL,
                updated_at                  TEXT NOT NULL,
                created_by                  TEXT REFERENCES users(id),
                CHECK (source_type IN ('manual', 'reply', 'forward')),
                CHECK (status IN ('draft', 'queued', 'sending', 'sent', 'failed', 'cancelled'))
            )
        """)
        conn.execute("""
            CREATE INDEX idx_oeq_customer_status
                ON outbound_email_queue(customer_id, status)
        """)
        conn.execute("""
            CREATE INDEX idx_oeq_created_by
                ON outbound_email_queue(created_by, status)
        """)
        print("  Done.")
    else:
        print("\nStep 1: outbound_email_queue already exists, skipping.")

    # -------------------------------------------------------------------
    # Step 2: Create outbound_email_attachments table
    # -------------------------------------------------------------------
    if "outbound_email_attachments" not in existing_tables:
        print("\nStep 2: Creating outbound_email_attachments table...")
        conn.execute("""
            CREATE TABLE outbound_email_attachments (
                id                TEXT PRIMARY KEY,
                outbound_email_id TEXT NOT NULL REFERENCES outbound_email_queue(id) ON DELETE CASCADE,
                filename          TEXT NOT NULL,
                mime_type         TEXT,
                size_bytes        INTEGER,
                storage_ref       TEXT,
                source            TEXT NOT NULL DEFAULT 'user_attached',
                display_order     INTEGER NOT NULL DEFAULT 0,
                created_at        TEXT NOT NULL,
                CHECK (source IN ('user_attached', 'forwarded'))
            )
        """)
        print("  Done.")
    else:
        print("\nStep 2: outbound_email_attachments already exists, skipping.")

    # -------------------------------------------------------------------
    # Step 3: Create email_signatures table
    # -------------------------------------------------------------------
    if "email_signatures" not in existing_tables:
        print("\nStep 3: Creating email_signatures table...")
        conn.execute("""
            CREATE TABLE email_signatures (
                id                  TEXT PRIMARY KEY,
                customer_id         TEXT NOT NULL REFERENCES customers(id),
                user_id             TEXT NOT NULL REFERENCES users(id),
                name                TEXT NOT NULL,
                body_json           TEXT NOT NULL,
                body_html           TEXT NOT NULL,
                provider_account_id TEXT REFERENCES provider_accounts(id),
                is_default          INTEGER NOT NULL DEFAULT 0,
                created_at          TEXT NOT NULL,
                updated_at          TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE INDEX idx_signatures_user
                ON email_signatures(user_id)
        """)
        print("  Done.")
    else:
        print("\nStep 3: email_signatures already exists, skipping.")

    # -------------------------------------------------------------------
    # Step 4: Add delivery_status columns to contact_identifiers
    # -------------------------------------------------------------------
    ci_cols = {r[1] for r in conn.execute("PRAGMA table_info(contact_identifiers)")}

    if "delivery_status" not in ci_cols:
        print("\nStep 4a: Adding delivery_status to contact_identifiers...")
        conn.execute(
            "ALTER TABLE contact_identifiers ADD COLUMN delivery_status TEXT DEFAULT 'unknown'"
        )
        print("  Done.")
    else:
        print("\nStep 4a: delivery_status already exists, skipping.")

    if "delivery_status_updated_at" not in ci_cols:
        print("\nStep 4b: Adding delivery_status_updated_at to contact_identifiers...")
        conn.execute(
            "ALTER TABLE contact_identifiers ADD COLUMN delivery_status_updated_at TEXT"
        )
        print("  Done.")
    else:
        print("\nStep 4b: delivery_status_updated_at already exists, skipping.")

    # -------------------------------------------------------------------
    # Step 5: Add automated_email_opt_out to contacts
    # -------------------------------------------------------------------
    c_cols = {r[1] for r in conn.execute("PRAGMA table_info(contacts)")}

    if "automated_email_opt_out" not in c_cols:
        print("\nStep 5: Adding automated_email_opt_out to contacts...")
        conn.execute(
            "ALTER TABLE contacts ADD COLUMN automated_email_opt_out INTEGER DEFAULT 0"
        )
        print("  Done.")
    else:
        print("\nStep 5: automated_email_opt_out already exists, skipping.")

    # -------------------------------------------------------------------
    # Step 6: Bump schema version
    # -------------------------------------------------------------------
    print("\nStep 6: Bumping schema version to 19...")
    conn.execute("PRAGMA user_version = 19")
    print("  Schema version set to 19.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Migrate CRMExtender database from v18 to v19.",
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
