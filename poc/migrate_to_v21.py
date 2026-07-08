#!/usr/bin/env python3
"""Migrate the CRMExtender database from v20 to v21.

Contact Entity Base PRD field catalog (Tier 2):
- contacts gains first_name, last_name (backfilled by splitting name),
  lead_status (default 'new'), lead_source
- Display name stays in the existing name column; it is treated as
  overridden whenever it differs from "first_name last_name"

Usage:
    python3 -m poc.migrate_to_v21 [--db PATH] [--dry-run]
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


def split_name(name: str | None) -> tuple[str | None, str | None]:
    """Best-effort first/last split. Names that look like raw email
    headers (contain @ or quotes) are left unsplit."""
    if not name:
        return None, None
    name = name.strip()
    if not name or "@" in name or '"' in name:
        return None, None
    tokens = name.split()
    if len(tokens) == 1:
        # Single token sorts as a last name (matches the previous
        # last-word sort heuristic)
        return None, tokens[0]
    return " ".join(tokens[:-1]), tokens[-1]


def migrate(db_path: Path, *, dry_run: bool = False) -> None:
    """Run the full v20 -> v21 migration."""
    if not db_path.exists():
        print(f"Error: Database not found at {db_path}")
        sys.exit(1)

    backup_path = db_path.with_suffix(
        f".v20-backup-{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
    )
    print(f"Backing up to {backup_path}...")
    shutil.copy2(str(db_path), str(backup_path))
    print(f"  Backup created ({backup_path.stat().st_size:,} bytes)")

    if dry_run:
        db_path = backup_path

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=OFF")

    try:
        _run_migration(conn)
        conn.commit()
        print("\nMigration committed successfully.")
    except Exception:
        conn.rollback()
        print("\nMigration FAILED — rolled back.")
        raise
    finally:
        conn.close()

    if dry_run:
        print(f"\nDry run complete. Changes applied to backup: {backup_path}")
        print("Production database was NOT modified.")
    else:
        print(f"\nProduction database migrated. Backup at: {backup_path}")


def _run_migration(conn: sqlite3.Connection) -> None:
    cols = {r[1] for r in conn.execute("PRAGMA table_info(contacts)")}

    for col, ddl in [
        ("first_name", "ALTER TABLE contacts ADD COLUMN first_name TEXT"),
        ("last_name", "ALTER TABLE contacts ADD COLUMN last_name TEXT"),
        ("lead_status",
         "ALTER TABLE contacts ADD COLUMN lead_status TEXT DEFAULT 'new'"),
        ("lead_source", "ALTER TABLE contacts ADD COLUMN lead_source TEXT"),
    ]:
        if col not in cols:
            print(f"Step: adding {col}...")
            conn.execute(ddl)
        else:
            print(f"Step: {col} already exists, skipping.")

    print("\nStep: backfilling first/last name from name...")
    rows = conn.execute(
        "SELECT id, name FROM contacts "
        "WHERE first_name IS NULL AND last_name IS NULL AND name IS NOT NULL"
    ).fetchall()
    updated = 0
    for r in rows:
        first, last = split_name(r["name"])
        if first or last:
            conn.execute(
                "UPDATE contacts SET first_name = ?, last_name = ? WHERE id = ?",
                (first, last, r["id"]),
            )
            updated += 1
    print(f"  {updated} of {len(rows)} contacts split.")

    print("\nStep: bumping schema version to 21...")
    conn.execute("PRAGMA user_version = 21")
    print("  Schema version set to 21.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Migrate CRMExtender database from v20 to v21.",
    )
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    migrate(args.db, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
