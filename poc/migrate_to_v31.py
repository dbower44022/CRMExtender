#!/usr/bin/env python3
"""Migrate the CRMExtender database from v30 to v31.

Mail Client Phase 1 close-out (release v10.36):

* MAIL-11 — ``provider_accounts`` gains the historical-backfill checkpoint:
  ``backfill_cursor``, ``backfill_done``, ``backfill_messages``,
  ``backfill_updated_at``.
* MAIL-17 — new ``mail_snoozes`` table: a thread hidden from the inbox until
  ``return_at``, with the two indexes the scheduler's return pass and the
  Snoozed folder use.
* MAIL-18 / TDD D-10 — ``communications.cleaned_html`` is set NULL wherever
  it equals ``original_html`` (every row on the live database: 401 MB of the
  914 MB file was the second copy). Readers fall back to ``original_html``.
  The file is then compacted with VACUUM unless ``--no-vacuum`` is given;
  VACUUM needs the database to be otherwise idle and free disk space equal
  to the file size, and is safe to rerun later with ``--vacuum-only``.

Usage:
    python3 -m poc.migrate_to_v31 [--db PATH] [--dry-run] [--no-vacuum | --vacuum-only]
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

_ACCOUNT_COLUMNS = (
    ("backfill_cursor", "TEXT"),
    ("backfill_done", "INTEGER NOT NULL DEFAULT 0"),
    ("backfill_messages", "INTEGER NOT NULL DEFAULT 0"),
    ("backfill_updated_at", "TEXT"),
)

_SNOOZES_DDL = """
CREATE TABLE IF NOT EXISTS mail_snoozes (
    id              TEXT PRIMARY KEY,
    account_id      TEXT NOT NULL REFERENCES provider_accounts(id) ON DELETE CASCADE,
    thread_id       TEXT NOT NULL,
    return_at       TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'snoozed'
                    CHECK (status IN ('snoozed', 'returned', 'cancelled')),
    created_by      TEXT REFERENCES users(id) ON DELETE SET NULL,
    created_at      TEXT NOT NULL,
    returned_at     TEXT
);
CREATE INDEX IF NOT EXISTS idx_mail_snoozes_due ON mail_snoozes(status, return_at);
CREATE INDEX IF NOT EXISTS idx_mail_snoozes_thread ON mail_snoozes(account_id, thread_id, status);
"""


def vacuum(db_path: Path) -> bool:
    """Compact the file. Returns False (and says why) when SQLite refuses."""
    conn = sqlite3.connect(str(db_path), timeout=30)
    try:
        before = db_path.stat().st_size
        print("Step: VACUUM (this can take a minute or two on a large file)...")
        conn.execute("VACUUM")
        after = db_path.stat().st_size
        print(f"  {before / 1e6:.0f} MB -> {after / 1e6:.0f} MB")
        return True
    except sqlite3.OperationalError as exc:
        print(f"  VACUUM skipped: {exc}. Stop the server and rerun with --vacuum-only.")
        return False
    finally:
        conn.close()


def migrate(db_path: Path, *, dry_run: bool = False, do_vacuum: bool = True) -> None:
    if not db_path.exists():
        print(f"Error: Database not found at {db_path}")
        sys.exit(1)

    backup_path = db_path.with_suffix(
        f".v30-backup-{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
    )
    print(f"Backing up to {backup_path}...")
    shutil.copy2(str(db_path), str(backup_path))

    if dry_run:
        db_path = backup_path

    conn = sqlite3.connect(str(db_path), timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    try:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(provider_accounts)")}
        for name, decl in _ACCOUNT_COLUMNS:
            if name in cols:
                print(f"Step: provider_accounts.{name} already exists, skipping.")
                continue
            print(f"Step: adding provider_accounts.{name}...")
            conn.execute(f"ALTER TABLE provider_accounts ADD COLUMN {name} {decl}")
        print("Step: creating mail_snoozes (if missing)...")
        conn.executescript(_SNOOZES_DDL)
        print("Step: dropping the duplicate HTML copy (cleaned_html = original_html)...")
        cur = conn.execute(
            "UPDATE communications SET cleaned_html = NULL "
            "WHERE cleaned_html IS NOT NULL AND cleaned_html = original_html"
        )
        print(f"  {cur.rowcount} row(s) now hold one body.")
        print("Step: bumping schema version to 31...")
        conn.execute("PRAGMA user_version = 31")
        conn.commit()
        print("Migration committed successfully.")
    except Exception:
        conn.rollback()
        print("Migration FAILED — rolled back.")
        raise
    finally:
        conn.close()

    if do_vacuum:
        vacuum(db_path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-vacuum", action="store_true", help="skip the VACUUM step")
    parser.add_argument("--vacuum-only", action="store_true", help="only compact an already migrated file")
    args = parser.parse_args()
    if args.vacuum_only:
        vacuum(args.db)
        return
    migrate(args.db, dry_run=args.dry_run, do_vacuum=not args.no_vacuum)


if __name__ == "__main__":
    main()
