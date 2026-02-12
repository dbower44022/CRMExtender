#!/usr/bin/env python3
"""Migrate the CRMExtender database from v8 to v9.

Normalizes phone numbers to E.164 format, deduplicates, and seeds
the ``default_phone_country`` system setting.

Usage:
    python3 -m poc.migrate_to_v9 [--db PATH] [--dry-run]
"""

from __future__ import annotations

import argparse
import shutil
import sqlite3
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

DEFAULT_CUSTOMER_ID = "cust-default"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def migrate(db_path: Path, *, dry_run: bool = False) -> None:
    """Run the full v8 -> v9 migration."""
    if not db_path.exists():
        print(f"Error: Database not found at {db_path}")
        sys.exit(1)

    # 1. Backup
    backup_path = db_path.with_suffix(
        f".v8-backup-{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
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


def _resolve_country_for_entity(conn, entity_type, entity_id):
    """Look up country from entity's address (primary first)."""
    row = conn.execute(
        "SELECT country FROM addresses "
        "WHERE entity_type = ? AND entity_id = ? AND country IS NOT NULL "
        "ORDER BY is_primary DESC, created_at ASC LIMIT 1",
        (entity_type, entity_id),
    ).fetchone()
    if row and row["country"]:
        return row["country"]
    return "US"


def _run_migration(conn: sqlite3.Connection) -> None:
    """Execute all migration steps in order."""
    import phonenumbers

    now = _now_iso()

    # -------------------------------------------------------------------
    # Step 1: Normalize phone numbers to E.164
    # -------------------------------------------------------------------
    print("\nStep 1: Normalizing phone numbers to E.164...")
    phones = conn.execute(
        "SELECT id, entity_type, entity_id, number FROM phone_numbers"
    ).fetchall()
    print(f"  Found {len(phones)} phone number(s) to process.")

    normalized_count = 0
    failed_count = 0
    unchanged_count = 0
    for phone in phones:
        country = _resolve_country_for_entity(
            conn, phone["entity_type"], phone["entity_id"]
        )
        try:
            parsed = phonenumbers.parse(phone["number"], country)
        except phonenumbers.NumberParseException:
            print(f"  WARNING: Cannot parse '{phone['number']}' "
                  f"(id={phone['id']}) — leaving as-is")
            failed_count += 1
            continue

        if not phonenumbers.is_possible_number(parsed):
            print(f"  WARNING: Not a possible number '{phone['number']}' "
                  f"(id={phone['id']}) — leaving as-is")
            failed_count += 1
            continue

        e164 = phonenumbers.format_number(
            parsed, phonenumbers.PhoneNumberFormat.E164
        )
        if e164 != phone["number"]:
            conn.execute(
                "UPDATE phone_numbers SET number = ?, updated_at = ? WHERE id = ?",
                (e164, now, phone["id"]),
            )
            print(f"  Normalized: '{phone['number']}' -> '{e164}'")
            normalized_count += 1
        else:
            unchanged_count += 1

    print(f"  Results: {normalized_count} normalized, "
          f"{unchanged_count} already E.164, {failed_count} failed")

    # -------------------------------------------------------------------
    # Step 2: Deduplicate phone numbers
    # -------------------------------------------------------------------
    print("\nStep 2: Deduplicating phone numbers...")
    dupes = conn.execute(
        """SELECT id, entity_type, entity_id, number, created_at,
                  ROW_NUMBER() OVER (
                      PARTITION BY entity_type, entity_id, number
                      ORDER BY created_at
                  ) AS rn
           FROM phone_numbers"""
    ).fetchall()

    dedup_count = 0
    for row in dupes:
        if row["rn"] > 1:
            conn.execute("DELETE FROM phone_numbers WHERE id = ?", (row["id"],))
            print(f"  Removed duplicate: '{row['number']}' for "
                  f"{row['entity_type']}/{row['entity_id']}")
            dedup_count += 1

    remaining = conn.execute(
        "SELECT COUNT(*) AS cnt FROM phone_numbers"
    ).fetchone()["cnt"]
    print(f"  Removed {dedup_count} duplicate(s). {remaining} phone(s) remaining.")

    # -------------------------------------------------------------------
    # Step 3: Seed default_phone_country setting
    # -------------------------------------------------------------------
    print("\nStep 3: Seeding default_phone_country setting...")
    customers = conn.execute("SELECT id FROM customers").fetchall()
    seeded = 0
    for cust in customers:
        existing = conn.execute(
            "SELECT id FROM settings "
            "WHERE customer_id = ? AND scope = 'system' "
            "AND setting_name = 'default_phone_country'",
            (cust["id"],),
        ).fetchone()
        if not existing:
            conn.execute(
                "INSERT INTO settings "
                "(id, customer_id, user_id, scope, setting_name, setting_value, "
                "setting_description, setting_default, created_at, updated_at) "
                "VALUES (?, ?, NULL, 'system', 'default_phone_country', 'US', "
                "'Default country for phone numbers', 'US', ?, ?)",
                (str(uuid.uuid4()), cust["id"], now, now),
            )
            seeded += 1
            print(f"  Seeded for customer {cust['id']}")
        else:
            print(f"  Already exists for customer {cust['id']} — skipping")
    print(f"  Seeded {seeded} customer(s).")

    # -------------------------------------------------------------------
    # Step 4: Update schema version
    # -------------------------------------------------------------------
    print("\nStep 4: Updating schema version to 9...")
    conn.execute(
        "UPDATE settings SET setting_value = '9', updated_at = ? "
        "WHERE setting_name = 'schema_version'",
        (now,),
    )
    # If no schema_version row exists, the update affects 0 rows — that's fine.
    print("  Done.")


def main():
    parser = argparse.ArgumentParser(
        description="Migrate CRMExtender database from v8 to v9 schema "
                    "(phone normalization)"
    )
    parser.add_argument(
        "--db", type=Path,
        help="Path to the SQLite database file",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Apply migration to a backup copy instead of the real database",
    )
    args = parser.parse_args()

    if args.db:
        db_path = args.db
    else:
        from poc import config
        db_path = config.DB_PATH

    migrate(db_path, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
