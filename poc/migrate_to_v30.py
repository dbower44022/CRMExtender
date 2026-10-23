#!/usr/bin/env python3
"""Migrate the CRMExtender database from v29 to v30.

Data repair, no schema change (release v10.35): ``communications.snippet``
rows are HTML-unescaped. Gmail delivers the snippet field HTML-escaped
(``I&#39;ll``, ``&amp;``), and until v10.35 it was stored as received, so the
Conversations preview and grid showed the entity codes. The Gmail parser now
unescapes at ingest; this migration repairs the 4,600-odd rows already stored.

Usage:
    python3 -m poc.migrate_to_v30 [--db PATH] [--dry-run]
"""

from __future__ import annotations

import argparse
import html
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

DEFAULT_DB = Path("data/crm_extender.db")


def _unescape_snippets(conn: sqlite3.Connection) -> int:
    rows = conn.execute(
        "SELECT id, snippet FROM communications WHERE snippet LIKE '%&%'"
    ).fetchall()
    changed = 0
    for cid, snippet in rows:
        plain = html.unescape(snippet)
        if plain != snippet:
            conn.execute("UPDATE communications SET snippet = ? WHERE id = ?", (plain, cid))
            changed += 1
    return changed


def migrate(db_path: Path, *, dry_run: bool = False) -> None:
    if not db_path.exists():
        print(f"Error: Database not found at {db_path}")
        sys.exit(1)

    backup_path = db_path.with_suffix(
        f".v29-backup-{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
    )
    print(f"Backing up to {backup_path}...")
    shutil.copy2(str(db_path), str(backup_path))

    if dry_run:
        db_path = backup_path

    conn = sqlite3.connect(str(db_path), timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    try:
        print("Step: HTML-unescaping communications.snippet...")
        n = _unescape_snippets(conn)
        print(f"  {n} snippet(s) repaired.")
        print("Step: bumping schema version to 30...")
        conn.execute("PRAGMA user_version = 30")
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
