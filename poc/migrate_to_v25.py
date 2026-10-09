#!/usr/bin/env python3
"""Migrate the CRMExtender database from v24 to v25.

Mail Client PRD MAIL-12: the ``communications_fts`` full-text index over
subject, body, and participants, with the triggers that keep it current,
backfilled from every existing communication.

Usage:
    python3 -m poc.migrate_to_v25 [--db PATH] [--dry-run]
"""

from __future__ import annotations

import argparse
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from poc.mail_search import FTS_REBUILD_SQL, FTS_SCHEMA_SQL  # noqa: E402

DEFAULT_DB = Path("data/crm_extender.db")


def migrate(db_path: Path, *, dry_run: bool = False) -> None:
    if not db_path.exists():
        print(f"Error: Database not found at {db_path}")
        sys.exit(1)

    backup_path = db_path.with_suffix(
        f".v24-backup-{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
    )
    print(f"Backing up to {backup_path}...")
    shutil.copy2(str(db_path), str(backup_path))

    if dry_run:
        db_path = backup_path

    conn = sqlite3.connect(str(db_path), timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    try:
        print("Step: creating communications_fts and triggers (if missing)...")
        conn.executescript(FTS_SCHEMA_SQL)
        print("Step: rebuilding the index from existing communications...")
        conn.executescript(FTS_REBUILD_SQL)
        n = conn.execute("SELECT COUNT(*) FROM communications_fts").fetchone()[0]
        print(f"Step: bumping schema version to 25... ({n} rows indexed)")
        conn.execute("PRAGMA user_version = 25")
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
