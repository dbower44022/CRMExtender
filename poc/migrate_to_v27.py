#!/usr/bin/env python3
"""Migrate the CRMExtender database from v26 to v27.

Mail Client PRD MAIL-38: account health on ``provider_accounts`` —
``auth_status`` (ok | needs_reauth | disconnected), ``auth_error``,
``last_sync_error``, ``last_sync_error_at``. A failed token refresh in the
web server marks the account needs_reauth instead of opening a browser.

Usage:
    python3 -m poc.migrate_to_v27 [--db PATH] [--dry-run]
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
    ("auth_status", "TEXT NOT NULL DEFAULT 'ok'"),
    ("auth_error", "TEXT"),
    ("last_sync_error", "TEXT"),
    ("last_sync_error_at", "TEXT"),
)


def migrate(db_path: Path, *, dry_run: bool = False) -> None:
    if not db_path.exists():
        print(f"Error: Database not found at {db_path}")
        sys.exit(1)

    backup_path = db_path.with_suffix(
        f".v26-backup-{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
    )
    print(f"Backing up to {backup_path}...")
    shutil.copy2(str(db_path), str(backup_path))

    if dry_run:
        db_path = backup_path

    conn = sqlite3.connect(str(db_path), timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    try:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(provider_accounts)")}
        for name, decl in _NEW_COLUMNS:
            if name in cols:
                print(f"Step: provider_accounts.{name} already exists, skipping.")
                continue
            print(f"Step: adding provider_accounts.{name}...")
            conn.execute(f"ALTER TABLE provider_accounts ADD COLUMN {name} {decl}")
        print("Step: bumping schema version to 27...")
        conn.execute("PRAGMA user_version = 27")
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
