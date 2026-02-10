"""Tests for v7 company intelligence data layer.

Covers: schema (13 new tables, 9 new columns), updated Company model,
new CompanyIdentifier/CompanyHierarchy models, CRUD functions,
CHECK constraints, and migration script.
"""

import json
import shutil
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest

from poc.database import get_connection, init_db
from poc.models import Company, CompanyHierarchy, CompanyIdentifier
from poc.hierarchy import (
    add_company_hierarchy,
    add_company_identifier,
    create_company,
    find_company_by_identifier,
    get_child_companies,
    get_company_identifiers,
    get_parent_companies,
    remove_company_hierarchy,
    remove_company_identifier,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def tmp_db(tmp_path, monkeypatch):
    """Create a temporary database and point config at it."""
    db_file = tmp_path / "test.db"
    monkeypatch.setattr("poc.config.DB_PATH", db_file)
    init_db(db_file)
    return db_file


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _insert_company(conn, company_id="co-1", name="Acme Corp", domain=None, **kwargs):
    now = _now_iso()
    conn.execute(
        "INSERT INTO companies (id, name, domain, industry, description, status, "
        "created_at, updated_at) VALUES (?, ?, ?, ?, ?, 'active', ?, ?)",
        (company_id, name, domain, kwargs.get("industry"), kwargs.get("description"),
         now, now),
    )
    return company_id


def _insert_contact(conn, contact_id="ct-1", name="Alice", company_id=None):
    now = _now_iso()
    conn.execute(
        "INSERT INTO contacts (id, name, company_id, status, created_at, updated_at) "
        "VALUES (?, ?, ?, 'active', ?, ?)",
        (contact_id, name, company_id, now, now),
    )
    return contact_id


# ===========================================================================
# Company Model — Updated Fields
# ===========================================================================

class TestCompanyModelUpdated:

    def test_to_row_new_fields(self):
        c = Company(
            name="Big Co", domain="bigco.com", website="https://bigco.com",
            stock_symbol="BIG", size_range="501-1000", employee_count=750,
            founded_year=2005, revenue_range="$50M-$100M",
            funding_total="$200M", funding_stage="series_c",
            headquarters_location="San Francisco, CA",
        )
        row = c.to_row(company_id="c-1")
        assert row["website"] == "https://bigco.com"
        assert row["stock_symbol"] == "BIG"
        assert row["size_range"] == "501-1000"
        assert row["employee_count"] == 750
        assert row["founded_year"] == 2005
        assert row["revenue_range"] == "$50M-$100M"
        assert row["funding_total"] == "$200M"
        assert row["funding_stage"] == "series_c"
        assert row["headquarters_location"] == "San Francisco, CA"

    def test_to_row_defaults(self):
        c = Company(name="Minimal Corp")
        row = c.to_row(company_id="c-2")
        assert row["website"] is None
        assert row["stock_symbol"] is None
        assert row["size_range"] is None
        assert row["employee_count"] is None
        assert row["founded_year"] is None
        assert row["revenue_range"] is None
        assert row["funding_total"] is None
        assert row["funding_stage"] is None
        assert row["headquarters_location"] is None

    def test_from_row_roundtrip(self):
        c = Company(
            name="Test Co", domain="test.com", industry="Tech",
            website="https://test.com", stock_symbol="TST",
            employee_count=100, founded_year=2010,
            headquarters_location="NYC",
        )
        row = c.to_row(company_id="c-3")
        restored = Company.from_row(row)
        assert restored.name == "Test Co"
        assert restored.website == "https://test.com"
        assert restored.stock_symbol == "TST"
        assert restored.employee_count == 100
        assert restored.founded_year == 2010
        assert restored.headquarters_location == "NYC"

    def test_from_row_missing_new_fields(self):
        """Backward compat: old rows without new columns."""
        old_row = {
            "name": "Old Corp", "domain": "old.com", "industry": "Finance",
            "description": "An old company", "status": "active",
        }
        c = Company.from_row(old_row)
        assert c.name == "Old Corp"
        assert c.website == ""
        assert c.employee_count is None
        assert c.founded_year is None

    def test_employee_count_none(self):
        c = Company(name="No Count")
        assert c.employee_count is None
        row = c.to_row()
        assert row["employee_count"] is None

    def test_founded_year_serialization(self):
        c = Company(name="Founded Co", founded_year=1999)
        row = c.to_row()
        assert row["founded_year"] == 1999
        restored = Company.from_row(row)
        assert restored.founded_year == 1999

    def test_empty_strings_to_none(self):
        c = Company(name="Empty Fields", website="", funding_stage="")
        row = c.to_row()
        assert row["website"] is None
        assert row["funding_stage"] is None

    def test_company_identifier_model(self):
        ci = CompanyIdentifier(
            company_id="co-1", type="domain", value="acme.com",
            is_primary=True, source="manual",
        )
        row = ci.to_row(identifier_id="ci-1")
        assert row["id"] == "ci-1"
        assert row["company_id"] == "co-1"
        assert row["type"] == "domain"
        assert row["value"] == "acme.com"
        assert row["is_primary"] == 1
        assert row["source"] == "manual"

        restored = CompanyIdentifier.from_row(row)
        assert restored.company_id == "co-1"
        assert restored.is_primary is True
        assert restored.source == "manual"

    def test_company_hierarchy_model(self):
        ch = CompanyHierarchy(
            parent_company_id="co-parent",
            child_company_id="co-child",
            hierarchy_type="acquisition",
            effective_date="2020-01-15",
            metadata='{"amount": "$1B"}',
        )
        row = ch.to_row(hierarchy_id="ch-1")
        assert row["id"] == "ch-1"
        assert row["parent_company_id"] == "co-parent"
        assert row["child_company_id"] == "co-child"
        assert row["hierarchy_type"] == "acquisition"
        assert row["effective_date"] == "2020-01-15"
        assert row["metadata"] == '{"amount": "$1B"}'

        restored = CompanyHierarchy.from_row(row)
        assert restored.parent_company_id == "co-parent"
        assert restored.hierarchy_type == "acquisition"
        assert restored.effective_date == "2020-01-15"


# ===========================================================================
# V7 Schema Tests
# ===========================================================================

class TestV7Schema:

    NEW_TABLES = [
        "company_identifiers", "company_hierarchy", "company_merges",
        "company_social_profiles", "contact_social_profiles",
        "enrichment_runs", "enrichment_field_values", "entity_scores",
        "monitoring_preferences", "entity_assets", "addresses",
        "phone_numbers", "email_addresses",
    ]

    def test_new_tables_exist(self, tmp_db):
        with get_connection() as conn:
            tables = {
                row[0] for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
        for table in self.NEW_TABLES:
            assert table in tables, f"Table {table} not found"

    def test_companies_new_columns(self, tmp_db):
        with get_connection() as conn:
            cols = {
                row[1] for row in conn.execute(
                    "PRAGMA table_info(companies)"
                ).fetchall()
            }
        expected = {
            "website", "stock_symbol", "size_range", "employee_count",
            "founded_year", "revenue_range", "funding_total", "funding_stage",
            "headquarters_location",
        }
        assert expected.issubset(cols)

    def test_company_identifiers_columns(self, tmp_db):
        with get_connection() as conn:
            cols = {
                row[1] for row in conn.execute(
                    "PRAGMA table_info(company_identifiers)"
                ).fetchall()
            }
        expected = {"id", "company_id", "type", "value", "is_primary", "source",
                    "created_at", "updated_at"}
        assert expected == cols

    def test_entity_scores_unique_index(self, tmp_db):
        """Verify the UNIQUE constraint on (entity_type, entity_id, score_type)."""
        now = _now_iso()
        with get_connection() as conn:
            _insert_company(conn, "co-score")
            conn.execute(
                "INSERT INTO entity_scores (id, entity_type, entity_id, score_type, "
                "score_value, computed_at) VALUES (?, 'company', 'co-score', "
                "'relationship_strength', 0.75, ?)",
                (str(uuid.uuid4()), now),
            )
        with pytest.raises(sqlite3.IntegrityError):
            with get_connection() as conn:
                conn.execute(
                    "INSERT INTO entity_scores (id, entity_type, entity_id, score_type, "
                    "score_value, computed_at) VALUES (?, 'company', 'co-score', "
                    "'relationship_strength', 0.80, ?)",
                    (str(uuid.uuid4()), now),
                )


# ===========================================================================
# Company Identifiers CRUD
# ===========================================================================

class TestCompanyIdentifiersCRUD:

    def test_add_identifier(self, tmp_db):
        create_company("Acme Corp", domain="acme.com")
        with get_connection() as conn:
            co = conn.execute("SELECT id FROM companies WHERE name = 'Acme Corp'").fetchone()
        # acme.com is auto-added by create_company; add a second domain
        row = add_company_identifier(co["id"], "domain", "acme.co.uk", is_primary=True)
        assert row["type"] == "domain"
        assert row["value"] == "acme.co.uk"
        assert row["is_primary"] == 1

    def test_find_by_identifier(self, tmp_db):
        co = create_company("Find Corp", domain="findcorp.com")
        # domain identifier is auto-added by create_company
        found = find_company_by_identifier("domain", "findcorp.com")
        assert found is not None
        assert found["name"] == "Find Corp"

    def test_find_by_identifier_not_found(self, tmp_db):
        found = find_company_by_identifier("domain", "nonexistent.com")
        assert found is None

    def test_duplicate_identifier_raises(self, tmp_db):
        co = create_company("Dup Corp", domain="dup.com")
        # dup.com is auto-added by create_company; adding it again should raise
        with pytest.raises(sqlite3.IntegrityError):
            add_company_identifier(co["id"], "domain", "dup.com")

    def test_list_identifiers(self, tmp_db):
        co = create_company("Multi Corp")
        add_company_identifier(co["id"], "domain", "multi.com", is_primary=True)
        add_company_identifier(co["id"], "domain", "multi.co.uk")
        ids = get_company_identifiers(co["id"])
        assert len(ids) == 2
        assert ids[0]["is_primary"] == 1  # Primary first due to ORDER BY

    def test_remove_identifier(self, tmp_db):
        co = create_company("Rem Corp")
        row = add_company_identifier(co["id"], "domain", "rem.com")
        remove_company_identifier(row["id"])
        ids = get_company_identifiers(co["id"])
        assert len(ids) == 0

    def test_cascade_on_company_delete(self, tmp_db):
        co = create_company("Gone Corp")
        add_company_identifier(co["id"], "domain", "gone.com")
        with get_connection() as conn:
            conn.execute("DELETE FROM companies WHERE id = ?", (co["id"],))
        with get_connection() as conn:
            count = conn.execute(
                "SELECT COUNT(*) AS cnt FROM company_identifiers WHERE company_id = ?",
                (co["id"],),
            ).fetchone()["cnt"]
        assert count == 0


# ===========================================================================
# Company Hierarchy CRUD
# ===========================================================================

class TestCompanyHierarchyCRUD:

    def test_add_hierarchy(self, tmp_db):
        parent = create_company("Parent Corp")
        child = create_company("Child Corp")
        row = add_company_hierarchy(
            parent["id"], child["id"], "subsidiary",
            effective_date="2020-01-01",
        )
        assert row["parent_company_id"] == parent["id"]
        assert row["child_company_id"] == child["id"]
        assert row["hierarchy_type"] == "subsidiary"

    def test_get_parent_companies(self, tmp_db):
        parent = create_company("Big Parent")
        child = create_company("Small Child")
        add_company_hierarchy(parent["id"], child["id"], "subsidiary")
        parents = get_parent_companies(child["id"])
        assert len(parents) == 1
        assert parents[0]["parent_name"] == "Big Parent"

    def test_get_child_companies(self, tmp_db):
        parent = create_company("Holding Co")
        child1 = create_company("Sub A")
        child2 = create_company("Sub B")
        add_company_hierarchy(parent["id"], child1["id"], "subsidiary")
        add_company_hierarchy(parent["id"], child2["id"], "division")
        children = get_child_companies(parent["id"])
        assert len(children) == 2
        names = {c["child_name"] for c in children}
        assert names == {"Sub A", "Sub B"}

    def test_self_reference_blocked(self, tmp_db):
        co = create_company("Self Corp")
        with pytest.raises(sqlite3.IntegrityError):
            add_company_hierarchy(co["id"], co["id"], "subsidiary")

    def test_hierarchy_type_check(self, tmp_db):
        parent = create_company("Check Parent")
        child = create_company("Check Child")
        with pytest.raises(sqlite3.IntegrityError):
            add_company_hierarchy(parent["id"], child["id"], "invalid_type")

    def test_cascade_on_company_delete(self, tmp_db):
        parent = create_company("Del Parent")
        child = create_company("Del Child")
        add_company_hierarchy(parent["id"], child["id"], "subsidiary")
        with get_connection() as conn:
            conn.execute("DELETE FROM companies WHERE id = ?", (parent["id"],))
        with get_connection() as conn:
            count = conn.execute(
                "SELECT COUNT(*) AS cnt FROM company_hierarchy WHERE parent_company_id = ?",
                (parent["id"],),
            ).fetchone()["cnt"]
        assert count == 0

    def test_remove_hierarchy(self, tmp_db):
        parent = create_company("Rm Parent")
        child = create_company("Rm Child")
        row = add_company_hierarchy(parent["id"], child["id"], "acquisition")
        remove_company_hierarchy(row["id"])
        children = get_child_companies(parent["id"])
        assert len(children) == 0


# ===========================================================================
# CHECK Constraint Tests
# ===========================================================================

class TestCheckConstraints:

    def test_hierarchy_type_constraint(self, tmp_db):
        """Valid types work, invalid type is rejected."""
        parent = create_company("Chk Parent")
        child = create_company("Chk Child")
        for valid in ("subsidiary", "division", "acquisition", "spinoff"):
            row = add_company_hierarchy(parent["id"], child["id"], valid)
            remove_company_hierarchy(row["id"])

    def test_enrichment_entity_type_constraint(self, tmp_db):
        now = _now_iso()
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO enrichment_runs (id, entity_type, entity_id, provider, "
                "status, created_at) VALUES (?, 'company', 'co-1', 'test', 'pending', ?)",
                (str(uuid.uuid4()), now),
            )
        with pytest.raises(sqlite3.IntegrityError):
            with get_connection() as conn:
                conn.execute(
                    "INSERT INTO enrichment_runs (id, entity_type, entity_id, provider, "
                    "status, created_at) VALUES (?, 'invalid', 'co-1', 'test', 'pending', ?)",
                    (str(uuid.uuid4()), now),
                )

    def test_enrichment_status_constraint(self, tmp_db):
        now = _now_iso()
        for status in ("pending", "running", "completed", "failed"):
            with get_connection() as conn:
                conn.execute(
                    "INSERT INTO enrichment_runs (id, entity_type, entity_id, provider, "
                    "status, created_at) VALUES (?, 'company', 'co-1', 'test', ?, ?)",
                    (str(uuid.uuid4()), status, now),
                )
        with pytest.raises(sqlite3.IntegrityError):
            with get_connection() as conn:
                conn.execute(
                    "INSERT INTO enrichment_runs (id, entity_type, entity_id, provider, "
                    "status, created_at) VALUES (?, 'company', 'co-1', 'test', 'bogus', ?)",
                    (str(uuid.uuid4()), now),
                )

    def test_monitoring_tier_constraint(self, tmp_db):
        now = _now_iso()
        for tier in ("high", "standard", "low", "none"):
            with get_connection() as conn:
                conn.execute(
                    "INSERT INTO monitoring_preferences (id, entity_type, entity_id, "
                    "monitoring_tier, tier_source, created_at, updated_at) "
                    "VALUES (?, 'company', ?, ?, 'default', ?, ?)",
                    (str(uuid.uuid4()), str(uuid.uuid4()), tier, now, now),
                )
        with pytest.raises(sqlite3.IntegrityError):
            with get_connection() as conn:
                conn.execute(
                    "INSERT INTO monitoring_preferences (id, entity_type, entity_id, "
                    "monitoring_tier, tier_source, created_at, updated_at) "
                    "VALUES (?, 'company', 'co-x', 'extreme', 'default', ?, ?)",
                    (str(uuid.uuid4()), now, now),
                )

    def test_entity_scores_entity_type(self, tmp_db):
        now = _now_iso()
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO entity_scores (id, entity_type, entity_id, score_type, "
                "score_value, computed_at) VALUES (?, 'contact', 'ct-1', 'test', 0.5, ?)",
                (str(uuid.uuid4()), now),
            )
        with pytest.raises(sqlite3.IntegrityError):
            with get_connection() as conn:
                conn.execute(
                    "INSERT INTO entity_scores (id, entity_type, entity_id, score_type, "
                    "score_value, computed_at) VALUES (?, 'project', 'p-1', 'test', 0.5, ?)",
                    (str(uuid.uuid4()), now),
                )

    def test_asset_type_constraint(self, tmp_db):
        now = _now_iso()
        for atype in ("logo", "headshot", "banner"):
            with get_connection() as conn:
                conn.execute(
                    "INSERT INTO entity_assets (id, entity_type, entity_id, asset_type, "
                    "hash, mime_type, file_ext, created_at) "
                    "VALUES (?, 'company', 'co-1', ?, 'abc123', 'image/png', 'png', ?)",
                    (str(uuid.uuid4()), atype, now),
                )
        with pytest.raises(sqlite3.IntegrityError):
            with get_connection() as conn:
                conn.execute(
                    "INSERT INTO entity_assets (id, entity_type, entity_id, asset_type, "
                    "hash, mime_type, file_ext, created_at) "
                    "VALUES (?, 'company', 'co-1', 'icon', 'abc123', 'image/png', 'png', ?)",
                    (str(uuid.uuid4()), now),
                )


# ===========================================================================
# Basic INSERT Tests for New Tables
# ===========================================================================

class TestInserts:

    def test_company_identifiers_insert(self, tmp_db):
        now = _now_iso()
        with get_connection() as conn:
            _insert_company(conn, "co-ins", "Insert Co", "insert.com")
            conn.execute(
                "INSERT INTO company_identifiers (id, company_id, type, value, "
                "is_primary, created_at, updated_at) VALUES (?, 'co-ins', 'domain', "
                "'insert.com', 1, ?, ?)",
                (str(uuid.uuid4()), now, now),
            )
            row = conn.execute(
                "SELECT * FROM company_identifiers WHERE company_id = 'co-ins'"
            ).fetchone()
        assert row["value"] == "insert.com"

    def test_company_hierarchy_insert(self, tmp_db):
        now = _now_iso()
        with get_connection() as conn:
            _insert_company(conn, "co-p", "Parent")
            _insert_company(conn, "co-c", "Child")
            conn.execute(
                "INSERT INTO company_hierarchy (id, parent_company_id, child_company_id, "
                "hierarchy_type, created_at, updated_at) VALUES (?, 'co-p', 'co-c', "
                "'subsidiary', ?, ?)",
                (str(uuid.uuid4()), now, now),
            )
            row = conn.execute(
                "SELECT * FROM company_hierarchy WHERE parent_company_id = 'co-p'"
            ).fetchone()
        assert row["child_company_id"] == "co-c"

    def test_company_merges_insert(self, tmp_db):
        now = _now_iso()
        with get_connection() as conn:
            _insert_company(conn, "co-surv", "Survivor")
            conn.execute(
                "INSERT INTO company_merges (id, surviving_company_id, absorbed_company_id, "
                "absorbed_company_snapshot, merged_at) VALUES (?, 'co-surv', 'co-gone', "
                "'{\"name\":\"Gone Co\"}', ?)",
                (str(uuid.uuid4()), now),
            )
            row = conn.execute(
                "SELECT * FROM company_merges WHERE surviving_company_id = 'co-surv'"
            ).fetchone()
        assert row["absorbed_company_id"] == "co-gone"
        assert json.loads(row["absorbed_company_snapshot"])["name"] == "Gone Co"

    def test_enrichment_runs_insert(self, tmp_db):
        now = _now_iso()
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO enrichment_runs (id, entity_type, entity_id, provider, "
                "status, created_at) VALUES (?, 'company', 'co-1', 'wikidata', "
                "'completed', ?)",
                (str(uuid.uuid4()), now),
            )
            row = conn.execute(
                "SELECT * FROM enrichment_runs WHERE entity_id = 'co-1'"
            ).fetchone()
        assert row["provider"] == "wikidata"
        assert row["status"] == "completed"

    def test_enrichment_field_values_insert(self, tmp_db):
        now = _now_iso()
        run_id = str(uuid.uuid4())
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO enrichment_runs (id, entity_type, entity_id, provider, "
                "status, created_at) VALUES (?, 'company', 'co-1', 'test', 'completed', ?)",
                (run_id, now),
            )
            conn.execute(
                "INSERT INTO enrichment_field_values (id, enrichment_run_id, field_name, "
                "field_value, confidence, is_accepted, created_at) "
                "VALUES (?, ?, 'industry', 'Technology', 0.95, 1, ?)",
                (str(uuid.uuid4()), run_id, now),
            )
            row = conn.execute(
                "SELECT * FROM enrichment_field_values WHERE enrichment_run_id = ?",
                (run_id,),
            ).fetchone()
        assert row["field_name"] == "industry"
        assert row["confidence"] == 0.95

    def test_entity_scores_insert(self, tmp_db):
        now = _now_iso()
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO entity_scores (id, entity_type, entity_id, score_type, "
                "score_value, factors, computed_at) VALUES (?, 'company', 'co-1', "
                "'relationship_strength', 0.82, '{\"recency\":0.9}', ?)",
                (str(uuid.uuid4()), now),
            )
            row = conn.execute(
                "SELECT * FROM entity_scores WHERE entity_id = 'co-1'"
            ).fetchone()
        assert row["score_value"] == 0.82
        assert json.loads(row["factors"])["recency"] == 0.9

    def test_addresses_insert(self, tmp_db):
        now = _now_iso()
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO addresses (id, entity_type, entity_id, address_type, "
                "city, state, country, is_primary, created_at, updated_at) "
                "VALUES (?, 'company', 'co-1', 'headquarters', 'San Francisco', "
                "'CA', 'US', 1, ?, ?)",
                (str(uuid.uuid4()), now, now),
            )
            row = conn.execute(
                "SELECT * FROM addresses WHERE entity_id = 'co-1'"
            ).fetchone()
        assert row["city"] == "San Francisco"
        assert row["is_primary"] == 1

    def test_phone_numbers_insert(self, tmp_db):
        now = _now_iso()
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO phone_numbers (id, entity_type, entity_id, phone_type, "
                "number, is_primary, created_at, updated_at) "
                "VALUES (?, 'company', 'co-1', 'main', '+14155551234', 1, ?, ?)",
                (str(uuid.uuid4()), now, now),
            )
            row = conn.execute(
                "SELECT * FROM phone_numbers WHERE entity_id = 'co-1'"
            ).fetchone()
        assert row["number"] == "+14155551234"


# ===========================================================================
# Migration Tests
# ===========================================================================

class TestMigration:

    def _create_v6_db(self, path: Path) -> Path:
        """Create a minimal v6 database (without v7 tables/columns)."""
        conn = sqlite3.connect(str(path))
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        now = _now_iso()
        conn.executescript("""
            CREATE TABLE users (
                id TEXT PRIMARY KEY, email TEXT NOT NULL UNIQUE, name TEXT,
                role TEXT DEFAULT 'member', is_active INTEGER DEFAULT 1,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL
            );
            CREATE TABLE provider_accounts (
                id TEXT PRIMARY KEY, provider TEXT NOT NULL,
                account_type TEXT NOT NULL DEFAULT 'email',
                email_address TEXT, phone_number TEXT, display_name TEXT,
                auth_token_path TEXT, sync_cursor TEXT, last_synced_at TEXT,
                initial_sync_done INTEGER DEFAULT 0,
                backfill_query TEXT DEFAULT 'newer_than:90d',
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                UNIQUE(provider, email_address), UNIQUE(provider, phone_number)
            );
            CREATE TABLE companies (
                id TEXT PRIMARY KEY, name TEXT NOT NULL, domain TEXT,
                industry TEXT, description TEXT, status TEXT DEFAULT 'active',
                created_by TEXT REFERENCES users(id) ON DELETE SET NULL,
                updated_by TEXT REFERENCES users(id) ON DELETE SET NULL,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL
            );
            CREATE TABLE contacts (
                id TEXT PRIMARY KEY, name TEXT, company TEXT,
                company_id TEXT REFERENCES companies(id) ON DELETE SET NULL,
                source TEXT, status TEXT DEFAULT 'active',
                created_by TEXT REFERENCES users(id) ON DELETE SET NULL,
                updated_by TEXT REFERENCES users(id) ON DELETE SET NULL,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL
            );
            CREATE TABLE conversations (
                id TEXT PRIMARY KEY, topic_id TEXT, title TEXT,
                status TEXT DEFAULT 'active', created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE events (
                id TEXT PRIMARY KEY, title TEXT NOT NULL,
                event_type TEXT NOT NULL DEFAULT 'meeting',
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL
            );
        """)
        # Insert a couple companies with domain for seeding test
        conn.execute(
            "INSERT INTO companies (id, name, domain, created_at, updated_at) "
            "VALUES ('co-1', 'Acme Corp', 'acme.com', ?, ?)", (now, now),
        )
        conn.execute(
            "INSERT INTO companies (id, name, domain, created_at, updated_at) "
            "VALUES ('co-2', 'Beta Inc', 'beta.io', ?, ?)", (now, now),
        )
        conn.execute(
            "INSERT INTO companies (id, name, created_at, updated_at) "
            "VALUES ('co-3', 'No Domain LLC', ?, ?)", (now, now),
        )
        conn.commit()
        conn.close()
        return path

    def test_migration_on_fresh_v6_db(self, tmp_path):
        from poc.migrate_to_v7 import migrate

        db_path = self._create_v6_db(tmp_path / "v6.db")
        migrate(db_path, dry_run=False)

        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        tables = {
            row[0] for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        for table in [
            "company_identifiers", "company_hierarchy", "company_merges",
            "company_social_profiles", "contact_social_profiles",
            "enrichment_runs", "enrichment_field_values", "entity_scores",
            "monitoring_preferences", "entity_assets", "addresses",
            "phone_numbers", "email_addresses",
        ]:
            assert table in tables, f"Table {table} not found after migration"

        # Verify new columns
        cols = {
            row[1] for row in conn.execute(
                "PRAGMA table_info(companies)"
            ).fetchall()
        }
        assert "website" in cols
        assert "employee_count" in cols
        assert "headquarters_location" in cols
        conn.close()

    def test_migration_idempotent(self, tmp_path):
        from poc.migrate_to_v7 import migrate

        db_path = self._create_v6_db(tmp_path / "v6_idem.db")
        migrate(db_path, dry_run=False)
        # Run again — should not error
        migrate(db_path, dry_run=False)

        conn = sqlite3.connect(str(db_path))
        tables = {
            row[0] for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        assert "company_identifiers" in tables
        conn.close()

    def test_migration_dry_run(self, tmp_path):
        from poc.migrate_to_v7 import migrate

        db_path = self._create_v6_db(tmp_path / "v6_dry.db")
        original_size = db_path.stat().st_size
        migrate(db_path, dry_run=True)

        # Original should be unchanged — no new tables
        conn = sqlite3.connect(str(db_path))
        tables = {
            row[0] for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        assert "company_identifiers" not in tables
        conn.close()

        # But backup should have them
        backups = list(tmp_path.glob("v6_dry.v6-backup-*.db"))
        assert len(backups) >= 1
        backup_conn = sqlite3.connect(str(backups[0]))
        backup_tables = {
            row[0] for row in backup_conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        assert "company_identifiers" in backup_tables
        backup_conn.close()

    def test_migration_seeds_identifiers(self, tmp_path):
        from poc.migrate_to_v7 import migrate

        db_path = self._create_v6_db(tmp_path / "v6_seed.db")
        migrate(db_path, dry_run=False)

        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM company_identifiers ORDER BY value"
        ).fetchall()

        # Should have identifiers for co-1 (acme.com) and co-2 (beta.io)
        # but NOT co-3 (no domain)
        assert len(rows) == 2
        values = {r["value"] for r in rows}
        assert values == {"acme.com", "beta.io"}
        for r in rows:
            assert r["type"] == "domain"
            assert r["is_primary"] == 1
            assert r["source"] == "migration"
        conn.close()
