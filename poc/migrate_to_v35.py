#!/usr/bin/env python3
"""Migrate the CRMExtender database from v34 to v35.

Conversation timers (release v10.45, Conversation Entity TDD §9.15–9.16):

* ``conversations.done_reason`` (``user`` | ``timer``); existing done rows
  that carry a ``done_by`` are stamped ``user``.
* ``stale_after_days`` / ``closed_after_days`` become per-conversation
  overrides of the system settings. The copies of the old column defaults
  (14 / 30) that every row carried are blanked, so a value left standing is
  a genuine override.

Usage:
    python3 -m poc.migrate_to_v35 [--db PATH] [--dry-run]
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

OLD_STALE_DEFAULT = 14
OLD_CLOSED_DEFAULT = 30


def migrate(db_path: Path, *, dry_run: bool = False) -> None:
    if not db_path.exists():
        print(f"Error: Database not found at {db_path}")
        sys.exit(1)

    backup_path = db_path.with_suffix(
        f".v34-backup-{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
    )
    print(f"Backing up to {backup_path}...")
    shutil.copy2(str(db_path), str(backup_path))

    if dry_run:
        db_path = backup_path

    conn = sqlite3.connect(str(db_path), timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    try:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(conversations)")}
        if "done_reason" in cols:
            print("Step: conversations.done_reason already exists, skipping.")
        else:
            print("Step: adding conversations.done_reason...")
            conn.execute("ALTER TABLE conversations ADD COLUMN done_reason TEXT")
        cur = conn.execute(
            "UPDATE conversations SET done_reason = 'user' "
            "WHERE status = 'done' AND done_by IS NOT NULL AND done_reason IS NULL"
        )
        print(f"Step: stamped done_reason = 'user' on {cur.rowcount} user-closed row(s).")
        cur = conn.execute(
            "UPDATE conversations SET stale_after_days = NULL WHERE stale_after_days = ?",
            (OLD_STALE_DEFAULT,),
        )
        print(f"Step: blanked stale_after_days = {OLD_STALE_DEFAULT} on {cur.rowcount} row(s) (setting applies).")
        cur = conn.execute(
            "UPDATE conversations SET closed_after_days = NULL WHERE closed_after_days = ?",
            (OLD_CLOSED_DEFAULT,),
        )
        print(f"Step: blanked closed_after_days = {OLD_CLOSED_DEFAULT} on {cur.rowcount} row(s) (setting applies).")
        print("Step: bumping schema version to 35...")
        conn.execute("PRAGMA user_version = 35")
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
