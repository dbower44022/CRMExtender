#!/usr/bin/env python3
"""Migrate the CRMExtender database from v6 to v7.

Adds:
- 9 new columns on companies table (website, stock_symbol, size_range,
  employee_count, founded_year, revenue_range, funding_total, funding_stage,
  headquarters_location)
- company_identifiers table (multi-domain per company)
- company_hierarchy table (parent/child organizational structure)
- company_merges table (merge audit log)
- company_social_profiles table
- contact_social_profiles table
- enrichment_runs table (entity-agnostic)
- enrichment_field_values table (field-level provenance)
- entity_scores table (precomputed intelligence)
- monitoring_preferences table (per-entity tier)
- entity_assets table (content-addressable storage)
- addresses table (entity-agnostic multi-value)
- phone_numbers table (entity-agnostic multi-value)
- email_addresses table (entity-agnostic multi-value)
- Seeds company_identifiers from existing companies.domain
- Associated indexes

Usage:
    python3 -m poc.migrate_to_v7 [--db PATH] [--dry-run]
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

_NEW_COLUMNS = [
    "website TEXT",
    "stock_symbol TEXT",
    "size_range TEXT",
    "employee_count INTEGER",
    "founded_year INTEGER",
    "revenue_range TEXT",
    "funding_total TEXT",
    "funding_stage TEXT",
    "headquarters_location TEXT",
]

_COMPANY_IDENTIFIERS_SQL = """\
CREATE TABLE IF NOT EXISTS company_identifiers (
    id          TEXT PRIMARY KEY,
    company_id  TEXT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    type        TEXT NOT NULL DEFAULT 'domain',
    value       TEXT NOT NULL,
    is_primary  INTEGER DEFAULT 0,
    source      TEXT,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    UNIQUE(type, value)
);
"""

_COMPANY_HIERARCHY_SQL = """\
CREATE TABLE IF NOT EXISTS company_hierarchy (
    id                TEXT PRIMARY KEY,
    parent_company_id TEXT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    child_company_id  TEXT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    hierarchy_type    TEXT NOT NULL,
    effective_date    TEXT,
    end_date          TEXT,
    metadata          TEXT,
    created_by        TEXT REFERENCES users(id) ON DELETE SET NULL,
    updated_by        TEXT REFERENCES users(id) ON DELETE SET NULL,
    created_at        TEXT NOT NULL,
    updated_at        TEXT NOT NULL,
    CHECK (hierarchy_type IN ('subsidiary', 'division', 'acquisition', 'spinoff')),
    CHECK (parent_company_id != child_company_id)
);
"""

_COMPANY_MERGES_SQL = """\
CREATE TABLE IF NOT EXISTS company_merges (
    id                         TEXT PRIMARY KEY,
    surviving_company_id       TEXT NOT NULL REFERENCES companies(id),
    absorbed_company_id        TEXT NOT NULL,
    absorbed_company_snapshot  TEXT NOT NULL,
    contacts_reassigned        INTEGER DEFAULT 0,
    relationships_reassigned   INTEGER DEFAULT 0,
    events_reassigned          INTEGER DEFAULT 0,
    relationships_deduplicated INTEGER DEFAULT 0,
    merged_by                  TEXT REFERENCES users(id) ON DELETE SET NULL,
    merged_at                  TEXT NOT NULL
);
"""

_COMPANY_SOCIAL_PROFILES_SQL = """\
CREATE TABLE IF NOT EXISTS company_social_profiles (
    id              TEXT PRIMARY KEY,
    company_id      TEXT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    platform        TEXT NOT NULL,
    profile_url     TEXT NOT NULL,
    username        TEXT,
    verified        INTEGER DEFAULT 0,
    follower_count  INTEGER,
    bio             TEXT,
    last_scanned_at TEXT,
    last_post_at    TEXT,
    source          TEXT,
    confidence      REAL,
    status          TEXT DEFAULT 'active',
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL,
    UNIQUE(company_id, platform, profile_url)
);
"""

_CONTACT_SOCIAL_PROFILES_SQL = """\
CREATE TABLE IF NOT EXISTS contact_social_profiles (
    id                 TEXT PRIMARY KEY,
    contact_id         TEXT NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
    platform           TEXT NOT NULL,
    profile_url        TEXT NOT NULL,
    username           TEXT,
    headline           TEXT,
    connection_degree  INTEGER,
    mutual_connections INTEGER,
    verified           INTEGER DEFAULT 0,
    follower_count     INTEGER,
    bio                TEXT,
    last_scanned_at    TEXT,
    last_post_at       TEXT,
    source             TEXT,
    confidence         REAL,
    status             TEXT DEFAULT 'active',
    created_at         TEXT NOT NULL,
    updated_at         TEXT NOT NULL,
    UNIQUE(contact_id, platform, profile_url)
);
"""

_ENRICHMENT_RUNS_SQL = """\
CREATE TABLE IF NOT EXISTS enrichment_runs (
    id            TEXT PRIMARY KEY,
    entity_type   TEXT NOT NULL,
    entity_id     TEXT NOT NULL,
    provider      TEXT NOT NULL,
    status        TEXT NOT NULL DEFAULT 'pending',
    started_at    TEXT,
    completed_at  TEXT,
    error_message TEXT,
    created_at    TEXT NOT NULL,
    CHECK (entity_type IN ('company', 'contact')),
    CHECK (status IN ('pending', 'running', 'completed', 'failed'))
);
"""

_ENRICHMENT_FIELD_VALUES_SQL = """\
CREATE TABLE IF NOT EXISTS enrichment_field_values (
    id                TEXT PRIMARY KEY,
    enrichment_run_id TEXT NOT NULL REFERENCES enrichment_runs(id) ON DELETE CASCADE,
    field_name        TEXT NOT NULL,
    field_value       TEXT,
    confidence        REAL NOT NULL DEFAULT 0.0,
    is_accepted       INTEGER DEFAULT 0,
    created_at        TEXT NOT NULL
);
"""

_ENTITY_SCORES_SQL = """\
CREATE TABLE IF NOT EXISTS entity_scores (
    id           TEXT PRIMARY KEY,
    entity_type  TEXT NOT NULL,
    entity_id    TEXT NOT NULL,
    score_type   TEXT NOT NULL,
    score_value  REAL NOT NULL DEFAULT 0.0,
    factors      TEXT,
    computed_at  TEXT NOT NULL,
    triggered_by TEXT,
    CHECK (entity_type IN ('company', 'contact'))
);
"""

_MONITORING_PREFERENCES_SQL = """\
CREATE TABLE IF NOT EXISTS monitoring_preferences (
    id              TEXT PRIMARY KEY,
    entity_type     TEXT NOT NULL,
    entity_id       TEXT NOT NULL,
    monitoring_tier TEXT NOT NULL DEFAULT 'standard',
    tier_source     TEXT NOT NULL DEFAULT 'default',
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL,
    CHECK (entity_type IN ('company', 'contact')),
    CHECK (monitoring_tier IN ('high', 'standard', 'low', 'none')),
    CHECK (tier_source IN ('manual', 'auto_suggested', 'default')),
    UNIQUE(entity_type, entity_id)
);
"""

_ENTITY_ASSETS_SQL = """\
CREATE TABLE IF NOT EXISTS entity_assets (
    id          TEXT PRIMARY KEY,
    entity_type TEXT NOT NULL,
    entity_id   TEXT NOT NULL,
    asset_type  TEXT NOT NULL,
    hash        TEXT NOT NULL,
    mime_type   TEXT NOT NULL,
    file_ext    TEXT NOT NULL,
    source      TEXT,
    created_at  TEXT NOT NULL,
    CHECK (entity_type IN ('company', 'contact')),
    CHECK (asset_type IN ('logo', 'headshot', 'banner'))
);
"""

_ADDRESSES_SQL = """\
CREATE TABLE IF NOT EXISTS addresses (
    id           TEXT PRIMARY KEY,
    entity_type  TEXT NOT NULL,
    entity_id    TEXT NOT NULL,
    address_type TEXT NOT NULL DEFAULT 'headquarters',
    street       TEXT,
    city         TEXT,
    state        TEXT,
    postal_code  TEXT,
    country      TEXT,
    is_primary   INTEGER DEFAULT 0,
    source       TEXT,
    confidence   REAL,
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL,
    CHECK (entity_type IN ('company', 'contact'))
);
"""

_PHONE_NUMBERS_SQL = """\
CREATE TABLE IF NOT EXISTS phone_numbers (
    id          TEXT PRIMARY KEY,
    entity_type TEXT NOT NULL,
    entity_id   TEXT NOT NULL,
    phone_type  TEXT NOT NULL DEFAULT 'main',
    number      TEXT NOT NULL,
    is_primary  INTEGER DEFAULT 0,
    source      TEXT,
    confidence  REAL,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    CHECK (entity_type IN ('company', 'contact'))
);
"""

_EMAIL_ADDRESSES_SQL = """\
CREATE TABLE IF NOT EXISTS email_addresses (
    id          TEXT PRIMARY KEY,
    entity_type TEXT NOT NULL,
    entity_id   TEXT NOT NULL,
    email_type  TEXT NOT NULL DEFAULT 'general',
    address     TEXT NOT NULL,
    is_primary  INTEGER DEFAULT 0,
    source      TEXT,
    confidence  REAL,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    CHECK (entity_type IN ('company', 'contact'))
);
"""

_INDEX_SQL = """\
CREATE INDEX IF NOT EXISTS idx_coid_company          ON company_identifiers(company_id);
CREATE INDEX IF NOT EXISTS idx_coid_lookup            ON company_identifiers(type, value);
CREATE INDEX IF NOT EXISTS idx_ch_parent              ON company_hierarchy(parent_company_id);
CREATE INDEX IF NOT EXISTS idx_ch_child               ON company_hierarchy(child_company_id);
CREATE INDEX IF NOT EXISTS idx_ch_type                ON company_hierarchy(hierarchy_type);
CREATE INDEX IF NOT EXISTS idx_cm_surviving           ON company_merges(surviving_company_id);
CREATE INDEX IF NOT EXISTS idx_cm_absorbed            ON company_merges(absorbed_company_id);
CREATE INDEX IF NOT EXISTS idx_csp_company            ON company_social_profiles(company_id);
CREATE INDEX IF NOT EXISTS idx_csp_platform           ON company_social_profiles(platform);
CREATE INDEX IF NOT EXISTS idx_ctsp_contact           ON contact_social_profiles(contact_id);
CREATE INDEX IF NOT EXISTS idx_ctsp_platform          ON contact_social_profiles(platform);
CREATE INDEX IF NOT EXISTS idx_er_entity              ON enrichment_runs(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_er_provider            ON enrichment_runs(provider);
CREATE INDEX IF NOT EXISTS idx_er_status              ON enrichment_runs(status);
CREATE INDEX IF NOT EXISTS idx_efv_run                ON enrichment_field_values(enrichment_run_id);
CREATE INDEX IF NOT EXISTS idx_efv_field              ON enrichment_field_values(field_name, is_accepted);
CREATE UNIQUE INDEX IF NOT EXISTS idx_es_entity_score ON entity_scores(entity_type, entity_id, score_type);
CREATE INDEX IF NOT EXISTS idx_es_score               ON entity_scores(score_type, score_value);
CREATE INDEX IF NOT EXISTS idx_ea_entity              ON entity_assets(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_ea_hash                ON entity_assets(hash);
CREATE INDEX IF NOT EXISTS idx_addr_entity            ON addresses(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_phone_entity           ON phone_numbers(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_email_entity           ON email_addresses(entity_type, entity_id);
"""

_NEW_TABLES = [
    ("company_identifiers", _COMPANY_IDENTIFIERS_SQL),
    ("company_hierarchy", _COMPANY_HIERARCHY_SQL),
    ("company_merges", _COMPANY_MERGES_SQL),
    ("company_social_profiles", _COMPANY_SOCIAL_PROFILES_SQL),
    ("contact_social_profiles", _CONTACT_SOCIAL_PROFILES_SQL),
    ("enrichment_runs", _ENRICHMENT_RUNS_SQL),
    ("enrichment_field_values", _ENRICHMENT_FIELD_VALUES_SQL),
    ("entity_scores", _ENTITY_SCORES_SQL),
    ("monitoring_preferences", _MONITORING_PREFERENCES_SQL),
    ("entity_assets", _ENTITY_ASSETS_SQL),
    ("addresses", _ADDRESSES_SQL),
    ("phone_numbers", _PHONE_NUMBERS_SQL),
    ("email_addresses", _EMAIL_ADDRESSES_SQL),
]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def migrate(db_path: Path, *, dry_run: bool = False) -> None:
    """Run the full v6 -> v7 migration."""
    if not db_path.exists():
        print(f"Error: Database not found at {db_path}")
        sys.exit(1)

    # 1. Backup
    backup_path = db_path.with_suffix(
        f".v6-backup-{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
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
    """Execute all migration steps in order."""
    # Check which tables already exist
    existing_tables = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }

    # -------------------------------------------------------------------
    # Step 1: ALTER companies table — add new columns
    # -------------------------------------------------------------------
    print("\nStep 1: Adding new columns to companies table...")
    existing_cols = {
        row[1]
        for row in conn.execute("PRAGMA table_info(companies)").fetchall()
    }
    added = 0
    for col_def in _NEW_COLUMNS:
        col_name = col_def.split()[0]
        if col_name in existing_cols:
            continue
        try:
            conn.execute(f"ALTER TABLE companies ADD COLUMN {col_def}")
            added += 1
        except sqlite3.OperationalError:
            pass  # Column already exists (idempotent)
    print(f"  Added {added} new column(s) ({len(_NEW_COLUMNS) - added} already existed).")

    # -------------------------------------------------------------------
    # Steps 2-14: Create new tables
    # -------------------------------------------------------------------
    for i, (table_name, table_sql) in enumerate(_NEW_TABLES, start=2):
        print(f"\nStep {i}: Creating {table_name} table...")
        if table_name in existing_tables:
            print("  Table already exists — skipping.")
        else:
            conn.executescript(table_sql)
            print(f"  Created {table_name} table.")

    # -------------------------------------------------------------------
    # Step 15: Create indexes
    # -------------------------------------------------------------------
    print("\nStep 15: Creating indexes...")
    conn.executescript(_INDEX_SQL)
    print("  Indexes created.")

    # -------------------------------------------------------------------
    # Step 16: Seed company_identifiers from existing companies.domain
    # -------------------------------------------------------------------
    print("\nStep 16: Seeding company_identifiers from existing company domains...")
    now = _now_iso()
    rows = conn.execute(
        "SELECT id, domain FROM companies WHERE domain IS NOT NULL AND domain != ''"
    ).fetchall()
    seeded = 0
    for row in rows:
        try:
            conn.execute(
                "INSERT OR IGNORE INTO company_identifiers "
                "(id, company_id, type, value, is_primary, source, created_at, updated_at) "
                "VALUES (?, ?, 'domain', ?, 1, 'migration', ?, ?)",
                (str(uuid.uuid4()), row[0], row[1], now, now),
            )
            if conn.execute("SELECT changes()").fetchone()[0] > 0:
                seeded += 1
        except sqlite3.IntegrityError:
            pass  # Already seeded (idempotent)
    print(f"  Seeded {seeded} identifier(s) from {len(rows)} companies with domains.")

    # -------------------------------------------------------------------
    # Step 17: Validation
    # -------------------------------------------------------------------
    print("\nStep 17: Validation...")
    conn.execute("PRAGMA foreign_keys=ON")

    post_tables = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }

    errors = []
    for table_name, _ in _NEW_TABLES:
        if table_name not in post_tables:
            errors.append(f"Table {table_name} was not created")

    # Verify companies has new columns
    company_cols = {
        row[1]
        for row in conn.execute("PRAGMA table_info(companies)").fetchall()
    }
    expected_new_cols = {
        "website", "stock_symbol", "size_range", "employee_count",
        "founded_year", "revenue_range", "funding_total", "funding_stage",
        "headquarters_location",
    }
    missing_cols = expected_new_cols - company_cols
    if missing_cols:
        errors.append(f"Missing columns on companies: {missing_cols}")

    if errors:
        print("\nVALIDATION ERRORS:")
        for e in errors:
            print(f"  ERROR: {e}")
        raise RuntimeError(
            f"Migration validation failed with {len(errors)} error(s)"
        )
    else:
        print("\nAll validations passed!")


def main():
    parser = argparse.ArgumentParser(
        description="Migrate CRMExtender database from v6 to v7 schema (company intelligence)"
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
