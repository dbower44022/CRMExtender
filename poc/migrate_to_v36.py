#!/usr/bin/env python3
"""Migrate the CRMExtender database from v35 to v36.

Token accounting and batch summarization (release v10.46, Mail Client
MAIL-49, TDD D-48): three new tables, no existing row changes.

* ``ai_usage`` — one row per Anthropic call or batch result with its token
  counts and the cost estimated from ``poc/ai_pricing.py``.
* ``ai_batches`` / ``ai_batch_items`` — Message Batches submitted for bulk
  summarization and the conversation each request covers.

Usage:
    python3 -m poc.migrate_to_v36 [--db PATH] [--dry-run]
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

_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS ai_usage (
    id                          TEXT PRIMARY KEY,
    occurred_at                 TEXT NOT NULL,
    customer_id                 TEXT,
    purpose                     TEXT NOT NULL,
    mode                        TEXT NOT NULL,
    model                       TEXT NOT NULL,
    conversation_id             TEXT,
    batch_id                    TEXT,
    request_id                  TEXT,
    input_tokens                INTEGER NOT NULL DEFAULT 0,
    output_tokens               INTEGER NOT NULL DEFAULT 0,
    cache_creation_input_tokens INTEGER NOT NULL DEFAULT 0,
    cache_read_input_tokens     INTEGER NOT NULL DEFAULT 0,
    cost_usd                    REAL,
    created_at                  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_ai_usage_occurred ON ai_usage(occurred_at);
CREATE TABLE IF NOT EXISTS ai_batches (
    id               TEXT PRIMARY KEY,
    customer_id      TEXT,
    purpose          TEXT NOT NULL,
    model            TEXT NOT NULL,
    status           TEXT NOT NULL,
    submitted_count  INTEGER NOT NULL DEFAULT 0,
    succeeded        INTEGER NOT NULL DEFAULT 0,
    errored          INTEGER NOT NULL DEFAULT 0,
    expired          INTEGER NOT NULL DEFAULT 0,
    canceled         INTEGER NOT NULL DEFAULT 0,
    created_at       TEXT NOT NULL,
    last_checked_at  TEXT,
    ended_at         TEXT,
    processed_at     TEXT,
    error            TEXT
);
CREATE TABLE IF NOT EXISTS ai_batch_items (
    batch_id        TEXT NOT NULL REFERENCES ai_batches(id) ON DELETE CASCADE,
    custom_id       TEXT NOT NULL,
    conversation_id TEXT NOT NULL,
    result_type     TEXT,
    error           TEXT,
    processed_at    TEXT,
    PRIMARY KEY (batch_id, custom_id)
);
CREATE INDEX IF NOT EXISTS idx_ai_batch_items_conv ON ai_batch_items(conversation_id, processed_at);
"""


def migrate(db_path: Path, *, dry_run: bool = False) -> None:
    if not db_path.exists():
        print(f"Error: Database not found at {db_path}")
        sys.exit(1)

    backup_path = db_path.with_suffix(
        f".v35-backup-{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
    )
    print(f"Backing up to {backup_path}...")
    shutil.copy2(str(db_path), str(backup_path))

    if dry_run:
        db_path = backup_path

    conn = sqlite3.connect(str(db_path), timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    try:
        print("Step: creating ai_usage, ai_batches and ai_batch_items (if missing)...")
        conn.executescript(_TABLES_SQL)
        print("Step: bumping schema version to 36...")
        conn.execute("PRAGMA user_version = 36")
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
