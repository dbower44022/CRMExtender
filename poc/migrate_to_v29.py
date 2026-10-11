#!/usr/bin/env python3
"""Migrate the CRMExtender database from v28 to v29.

Data repair, no schema change (Views & Grid PRD 6.2, release v10.33):

1. ``conversations.customer_id`` is filled where it is NULL, from the owning
   provider account (``conversations.account_id``, else the account of the
   first linked communication). The visibility rule in ``poc.access`` requires
   ``conv.customer_id = ?``, so a NULL row was invisible in every grid even
   though the user owned the mailbox. 560 such rows existed on the live
   database, all created on 2026-03-17.
2. Every existing conversation view gains the ``account_name`` column (placed
   right after ``status`` when that column is present, else appended), so the
   mailbox a conversation came from shows by default for existing users as
   well as new ones.

Usage:
    python3 -m poc.migrate_to_v29 [--db PATH] [--dry-run]
"""

from __future__ import annotations

import argparse
import shutil
import sqlite3
import sys
import uuid
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

DEFAULT_DB = Path("data/crm_extender.db")

_NEW_COLUMN = "account_name"
_ANCHOR_COLUMN = "status"


def _repair_customer_ids(conn: sqlite3.Connection) -> int:
    before = conn.execute(
        "SELECT COUNT(*) FROM conversations WHERE customer_id IS NULL"
    ).fetchone()[0]
    conn.execute(
        """UPDATE conversations SET customer_id = (
               SELECT pa.customer_id FROM provider_accounts pa
               WHERE pa.id = conversations.account_id)
           WHERE customer_id IS NULL AND account_id IS NOT NULL"""
    )
    conn.execute(
        """UPDATE conversations SET customer_id = (
               SELECT pa.customer_id
               FROM conversation_communications cc
               JOIN communications comm ON comm.id = cc.communication_id
               JOIN provider_accounts pa ON pa.id = comm.account_id
               WHERE cc.conversation_id = conversations.id
               ORDER BY comm.timestamp ASC LIMIT 1)
           WHERE customer_id IS NULL"""
    )
    after = conn.execute(
        "SELECT COUNT(*) FROM conversations WHERE customer_id IS NULL"
    ).fetchone()[0]
    return before - after


def _add_account_column_to_views(conn: sqlite3.Connection) -> int:
    views = conn.execute(
        """SELECT v.id FROM views v
           JOIN data_sources ds ON ds.id = v.data_source_id
           WHERE ds.entity_type = 'conversation'
             AND NOT EXISTS (SELECT 1 FROM view_columns vc
                             WHERE vc.view_id = v.id AND vc.field_key = ?)""",
        (_NEW_COLUMN,),
    ).fetchall()
    for (view_id,) in views:
        anchor = conn.execute(
            "SELECT position FROM view_columns WHERE view_id = ? AND field_key = ?",
            (view_id, _ANCHOR_COLUMN),
        ).fetchone()
        if anchor is not None:
            position = anchor[0] + 1
            conn.execute(
                "UPDATE view_columns SET position = position + 1 "
                "WHERE view_id = ? AND position >= ?",
                (view_id, position),
            )
        else:
            row = conn.execute(
                "SELECT COALESCE(MAX(position), -1) + 1 FROM view_columns WHERE view_id = ?",
                (view_id,),
            ).fetchone()
            position = row[0]
        conn.execute(
            "INSERT INTO view_columns (id, view_id, field_key, position) VALUES (?, ?, ?, ?)",
            (str(uuid.uuid4()), view_id, _NEW_COLUMN, position),
        )
    return len(views)


def migrate(db_path: Path, *, dry_run: bool = False) -> None:
    if not db_path.exists():
        print(f"Error: Database not found at {db_path}")
        sys.exit(1)

    backup_path = db_path.with_suffix(
        f".v28-backup-{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
    )
    print(f"Backing up to {backup_path}...")
    shutil.copy2(str(db_path), str(backup_path))

    if dry_run:
        db_path = backup_path

    conn = sqlite3.connect(str(db_path), timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    try:
        print("Step: filling conversations.customer_id where NULL...")
        fixed = _repair_customer_ids(conn)
        print(f"  {fixed} conversation(s) repaired.")
        print(f"Step: adding the {_NEW_COLUMN} column to conversation views...")
        touched = _add_account_column_to_views(conn)
        print(f"  {touched} view(s) updated.")
        print("Step: bumping schema version to 29...")
        conn.execute("PRAGMA user_version = 29")
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
