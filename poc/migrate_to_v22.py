#!/usr/bin/env python3
"""Migrate the CRMExtender database from v21 to v22.

Identity Resolution Sub-PRD: adds the match_candidates table for the
duplicate review queue.

Usage:
    python3 -m poc.migrate_to_v22 [--db PATH] [--dry-run]
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
        f".v21-backup-{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
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
        if "match_candidates" not in tables:
            print("Step: creating match_candidates table...")
            conn.execute("""
                CREATE TABLE match_candidates (
                    id           TEXT PRIMARY KEY,
                    customer_id  TEXT REFERENCES customers(id) ON DELETE CASCADE,
                    contact_a_id TEXT NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
                    contact_b_id TEXT NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
                    confidence   REAL NOT NULL,
                    signals      TEXT,
                    status       TEXT NOT NULL DEFAULT 'pending'
                                 CHECK (status IN ('pending', 'approved', 'rejected', 'auto_merged')),
                    source       TEXT,
                    reviewed_by  TEXT REFERENCES users(id) ON DELETE SET NULL,
                    reviewed_at  TEXT,
                    created_at   TEXT NOT NULL,
                    updated_at   TEXT NOT NULL,
                    CHECK (contact_a_id < contact_b_id),
                    UNIQUE (contact_a_id, contact_b_id)
                )
            """)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_mc_status "
                "ON match_candidates(status, confidence)")
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_mc_contacts "
                "ON match_candidates(contact_a_id, contact_b_id)")
        else:
            print("Step: match_candidates already exists, skipping.")

        print("Step: bumping schema version to 22...")
        conn.execute("PRAGMA user_version = 22")
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
