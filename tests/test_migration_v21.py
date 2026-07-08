"""Tests for the v20 -> v21 migration and name-split semantics (Tier 2)."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

import pytest

from poc.database import get_connection, init_db
from poc.migrate_to_v21 import migrate, split_name

_NOW = datetime.now(timezone.utc).isoformat()

CUST_ID = "cust-v21"
USER_ID = "user-v21"


class TestSplitName:
    @pytest.mark.parametrize("name,expected", [
        ("Doug Bower", ("Doug", "Bower")),
        ("Alan J Hartman", ("Alan J", "Hartman")),
        ("Cher", (None, "Cher")),
        ('"Frank Van Waveren" <f@aol.com>', (None, None)),
        ("user@example.com", (None, None)),
        ("", (None, None)),
        (None, (None, None)),
    ])
    def test_cases(self, name, expected):
        assert split_name(name) == expected


class TestMigration:
    def _v20_db(self, tmp_path):
        """Build a latest-schema DB, then strip the v21 columns to
        simulate a v20 database."""
        db = tmp_path / "v20.db"
        init_db(db)
        conn = sqlite3.connect(db)
        for col in ("first_name", "last_name", "lead_status", "lead_source"):
            conn.execute(f"ALTER TABLE contacts DROP COLUMN {col}")
        conn.execute(
            "INSERT INTO contacts (id, name, created_at, updated_at) "
            "VALUES ('ct-a', 'Jane Q Public', ?, ?)", (_NOW, _NOW))
        conn.execute(
            "INSERT INTO contacts (id, name, created_at, updated_at) "
            "VALUES ('ct-b', 'm@dirty.example', ?, ?)", (_NOW, _NOW))
        conn.execute("PRAGMA user_version = 20")
        conn.commit()
        conn.close()
        return db

    def test_migrates_and_backfills(self, tmp_path):
        db = self._v20_db(tmp_path)
        migrate(db)
        conn = sqlite3.connect(db)
        conn.row_factory = sqlite3.Row
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 21
        a = conn.execute(
            "SELECT first_name, last_name, lead_status FROM contacts "
            "WHERE id = 'ct-a'").fetchone()
        assert (a["first_name"], a["last_name"]) == ("Jane Q", "Public")
        assert a["lead_status"] == "new"
        b = conn.execute(
            "SELECT first_name, last_name FROM contacts WHERE id = 'ct-b'"
        ).fetchone()
        assert (b["first_name"], b["last_name"]) == (None, None)
        conn.close()

    def test_idempotent(self, tmp_path):
        db = self._v20_db(tmp_path)
        migrate(db)
        migrate(db)  # second run must be a no-op
        conn = sqlite3.connect(db)
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 21
        conn.close()


@pytest.fixture()
def tmp_db(tmp_path, monkeypatch):
    db_file = tmp_path / "test.db"
    monkeypatch.setattr("poc.config.DB_PATH", db_file)
    monkeypatch.setattr("poc.config.CRM_AUTH_ENABLED", False)
    init_db(db_file)
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO customers (id, name, slug, is_active, created_at, updated_at) "
            "VALUES (?, 'V21 Org', 'v21', 1, ?, ?)", (CUST_ID, _NOW, _NOW))
        conn.execute(
            "INSERT INTO users "
            "(id, customer_id, email, name, role, is_active, created_at, updated_at) "
            "VALUES (?, ?, 'a@v21.com', 'V21 Admin', 'admin', 1, ?, ?)",
            (USER_ID, CUST_ID, _NOW, _NOW))
    return db_file


class TestDisplayNameSemantics:
    def test_create_computes_display_name(self, tmp_db):
        from poc.hierarchy import computed_display_name, create_contact
        assert computed_display_name("Ada", "Lovelace") == "Ada Lovelace"
        c = create_contact("Ada Lovelace", first_name="Ada",
                           last_name="Lovelace", customer_id=CUST_ID)
        assert c["name"] == "Ada Lovelace"

    def test_update_recomputes_unless_overridden(self, tmp_db):
        from poc.hierarchy import create_contact, update_contact
        c = create_contact("Ada Lovelace", first_name="Ada",
                           last_name="Lovelace", customer_id=CUST_ID)
        # Not overridden — last-name change recomputes display name
        row = update_contact(c["id"], last_name="Byron")
        assert row["name"] == "Ada Byron"
        # Explicit override sticks through later first/last edits
        update_contact(c["id"], name="Countess of Lovelace")
        row = update_contact(c["id"], first_name="Augusta")
        assert row["name"] == "Countess of Lovelace"
        assert row["first_name"] == "Augusta"


class TestApiNameSplit:
    @pytest.fixture()
    def client(self, tmp_db, monkeypatch):
        monkeypatch.setattr(
            "poc.hierarchy.get_current_user",
            lambda: {"id": USER_ID, "email": "a@v21.com", "name": "V21 Admin",
                     "role": "admin", "customer_id": CUST_ID})
        from fastapi.testclient import TestClient
        from poc.web.app import create_app
        return TestClient(create_app(), raise_server_exceptions=False)

    def test_create_with_first_last(self, client, tmp_db):
        r = client.post("/api/v1/contacts", json={
            "first_name": "Grace", "last_name": "Hopper"})
        assert r.status_code == 200
        assert r.json()["name"] == "Grace Hopper"
        assert r.json()["lead_status"] == "new"

    def test_create_requires_some_name(self, client, tmp_db):
        assert client.post("/api/v1/contacts", json={}).status_code == 400

    def test_put_lead_status_validated(self, client, tmp_db):
        c = client.post("/api/v1/contacts", json={"name": "Lead Test"}).json()
        r = client.put(f"/api/v1/contacts/{c['id']}",
                       json={"lead_status": "qualified"})
        assert r.json()["lead_status"] == "qualified"
        assert client.put(f"/api/v1/contacts/{c['id']}",
                          json={"lead_status": "hot"}).status_code == 400

    def test_grid_sorts_by_real_last_name(self, client, tmp_db):
        from poc.views.engine import execute_view
        for first, last in [("Ada", "Lovelace"), ("Grace", "Hopper"),
                            ("Alan", "Turing")]:
            # POST /contacts also creates the user_contacts visibility row
            client.post("/api/v1/contacts", json={
                "first_name": first, "last_name": last})
        with get_connection() as conn:
            rows, _ = execute_view(
                conn, entity_type="contact",
                columns=[{"field_key": "name"}, {"field_key": "last_name"}],
                filters=[], sort_field="last_name", sort_direction="asc",
                customer_id=CUST_ID, user_id=USER_ID)
        assert [r["last_name"] for r in rows] == ["Hopper", "Lovelace", "Turing"]
