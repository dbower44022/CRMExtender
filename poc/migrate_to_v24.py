#!/usr/bin/env python3
"""Migrate the CRMExtender database from v23 to v24.

Mail Client PRD MAIL-09: the ``mail_actions`` outbox table (TDD D-04).
User mail actions (read, star, archive, trash, label, ...) are applied
locally at once and queued here to be pushed to the provider in order,
with retry and a dead-letter state.

Usage:
    python3 -m poc.migrate_to_v24 [--db PATH] [--dry-run]
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
    if not db_path.exists():
        print(f"Error: Database not found at {db_path}")
        sys.exit(1)

    backup_path = db_path.with_suffix(
        f".v23-backup-{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
    )
    print(f"Backing up to {backup_path}...")
    shutil.copy2(str(db_path), str(backup_path))

    if dry_run:
        db_path = backup_path

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    try:
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        if "mail_actions" not in tables:
            print("Step: creating mail_actions table...")
            conn.execute("""
                CREATE TABLE mail_actions (
                    id              TEXT PRIMARY KEY,
                    account_id      TEXT NOT NULL REFERENCES provider_accounts(id) ON DELETE CASCADE,
                    action          TEXT NOT NULL,
                    target_ids      TEXT NOT NULL,
                    label_id        TEXT,
                    payload         TEXT,
                    created_by      TEXT REFERENCES users(id) ON DELETE SET NULL,
                    status          TEXT NOT NULL DEFAULT 'pending'
                                    CHECK (status IN ('pending', 'pushed', 'gone', 'failed', 'discarded')),
                    attempts        INTEGER NOT NULL DEFAULT 0,
                    next_attempt_at TEXT,
                    error           TEXT,
                    pushed_at       TEXT,
                    created_at      TEXT NOT NULL,
                    updated_at      TEXT NOT NULL
                )
            """)
        else:
            print("Step: mail_actions already exists, skipping.")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_mail_actions_queue "
                     "ON mail_actions(account_id, status, created_at)")

        print("Step: bumping schema version to 24...")
        conn.execute("PRAGMA user_version = 24")
        conn.commit()
        print("Migration committed successfully.")
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
