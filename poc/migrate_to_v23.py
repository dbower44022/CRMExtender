#!/usr/bin/env python3
"""Migrate the CRMExtender database from v22 to v23.

Mail Client PRD MAIL-07 and MAIL-08: mailbox state on the Communication
record and the label tables.

- communications: ``header_reply_to``, ``is_starred``, ``mail_state_synced_at``
- new tables ``mailbox_labels`` and ``communication_labels``

The header, flag, and label values for rows that already exist are
fetched from the provider afterwards by::

    python -m poc backfill-mail-state

because a migration cannot reach the network. Rows whose
``mail_state_synced_at`` is NULL are the ones still waiting.

Usage:
    python3 -m poc.migrate_to_v23 [--db PATH] [--dry-run]
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

_NEW_COLUMNS = (
    ("header_reply_to", "TEXT"),
    ("is_starred", "INTEGER NOT NULL DEFAULT 0"),
    ("mail_state_synced_at", "TEXT"),
)


def migrate(db_path: Path, *, dry_run: bool = False) -> None:
    if not db_path.exists():
        print(f"Error: Database not found at {db_path}")
        sys.exit(1)

    backup_path = db_path.with_suffix(
        f".v22-backup-{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
    )
    print(f"Backing up to {backup_path}...")
    shutil.copy2(str(db_path), str(backup_path))

    if dry_run:
        db_path = backup_path

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    try:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(communications)")}
        for name, decl in _NEW_COLUMNS:
            if name in cols:
                print(f"Step: communications.{name} already exists, skipping.")
                continue
            print(f"Step: adding communications.{name}...")
            conn.execute(f"ALTER TABLE communications ADD COLUMN {name} {decl}")

        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        if "mailbox_labels" not in tables:
            print("Step: creating mailbox_labels table...")
            conn.execute("""
                CREATE TABLE mailbox_labels (
                    id                TEXT PRIMARY KEY,
                    account_id        TEXT NOT NULL REFERENCES provider_accounts(id) ON DELETE CASCADE,
                    provider_label_id TEXT NOT NULL,
                    name              TEXT NOT NULL,
                    kind              TEXT NOT NULL DEFAULT 'user',
                    parent_id         TEXT,
                    unread_count      INTEGER,
                    total_count       INTEGER,
                    created_at        TEXT NOT NULL,
                    updated_at        TEXT NOT NULL,
                    UNIQUE (account_id, provider_label_id)
                )
            """)
        else:
            print("Step: mailbox_labels already exists, skipping.")

        if "communication_labels" not in tables:
            print("Step: creating communication_labels table...")
            conn.execute("""
                CREATE TABLE communication_labels (
                    communication_id TEXT NOT NULL REFERENCES communications(id) ON DELETE CASCADE,
                    label_id         TEXT NOT NULL REFERENCES mailbox_labels(id) ON DELETE CASCADE,
                    PRIMARY KEY (communication_id, label_id)
                )
            """)
        else:
            print("Step: communication_labels already exists, skipping.")

        print("Step: creating indexes...")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_comm_mail_state ON communications(mail_state_synced_at)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_mlabel_account ON mailbox_labels(account_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_clabel_label ON communication_labels(label_id)")

        pending = conn.execute(
            "SELECT COUNT(*) FROM communications "
            "WHERE channel = 'email' AND provider_message_id IS NOT NULL "
            "AND mail_state_synced_at IS NULL"
        ).fetchone()[0]

        print("Step: bumping schema version to 23...")
        conn.execute("PRAGMA user_version = 23")
        conn.commit()
        print("Migration committed successfully.")
        print(f"{pending} email rows await header/label backfill: "
              "run `python -m poc backfill-mail-state`.")
    except Exception:
        conn.rollback()
        print("Migration FAILED — rolled back.")
        raise
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    migrate(args.db, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
