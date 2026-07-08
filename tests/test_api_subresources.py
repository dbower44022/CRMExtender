"""Tests for the Phase 2 sub-resource JSON API (Legacy UI Migration PRD)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from poc.database import get_connection, init_db

_NOW = datetime.now(timezone.utc).isoformat()

CUST_ID = "cust-sub-test"
USER_ID = "user-sub-admin"


@pytest.fixture()
def tmp_db(tmp_path, monkeypatch):
    db_file = tmp_path / "test.db"
    monkeypatch.setattr("poc.config.DB_PATH", db_file)
    monkeypatch.setattr("poc.config.CRM_AUTH_ENABLED", False)
    init_db(db_file)

    with get_connection() as conn:
        conn.execute(
            "INSERT INTO customers (id, name, slug, is_active, created_at, updated_at) "
            "VALUES (?, 'Test Org', 'sub', 1, ?, ?)",
            (CUST_ID, _NOW, _NOW),
        )
        conn.execute(
            "INSERT INTO users "
            "(id, customer_id, email, name, role, is_active, created_at, updated_at) "
            "VALUES (?, ?, 'admin@sub.com', 'Admin', 'admin', 1, ?, ?)",
            (USER_ID, CUST_ID, _NOW, _NOW),
        )
    return db_file


@pytest.fixture()
def client(tmp_db, monkeypatch):
    monkeypatch.setattr(
        "poc.hierarchy.get_current_user",
        lambda: {"id": USER_ID, "email": "admin@sub.com", "name": "Admin",
                 "role": "admin", "customer_id": CUST_ID},
    )
    from poc.web.app import create_app
    return TestClient(create_app(), raise_server_exceptions=False)


def _contact(conn, cid="ct-1", name="Test Contact", customer=CUST_ID):
    conn.execute(
        "INSERT INTO contacts (id, customer_id, name, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (cid, customer, name, _NOW, _NOW),
    )
    return cid


def _company(conn, coid="co-1", name="Test Co", customer=CUST_ID):
    conn.execute(
        "INSERT INTO companies (id, customer_id, name, status, created_at, updated_at) "
        "VALUES (?, ?, ?, 'active', ?, ?)",
        (coid, customer, name, _NOW, _NOW),
    )
    return coid


class TestIdentifiers:
    def test_add_email_lowercases_and_lists(self, client, tmp_db):
        with get_connection() as conn:
            _contact(conn)
        r = client.post("/api/v1/contacts/ct-1/identifiers",
                        json={"type": "email", "value": "  Foo@Bar.COM "})
        assert r.status_code == 200
        assert r.json()["value"] == "foo@bar.com"
        subs = client.get("/api/v1/contacts/ct-1/subresources").json()
        assert [i["value"] for i in subs["identifiers"]] == ["foo@bar.com"]

    def test_duplicate_returns_409_with_owner(self, client, tmp_db):
        with get_connection() as conn:
            _contact(conn, "ct-1", "Owner One")
            _contact(conn, "ct-2", "Owner Two")
        client.post("/api/v1/contacts/ct-1/identifiers",
                    json={"value": "dup@x.com"})
        r = client.post("/api/v1/contacts/ct-2/identifiers",
                        json={"value": "dup@x.com"})
        assert r.status_code == 409
        assert r.json()["other_contact_id"] == "ct-1"
        assert r.json()["other_contact_name"] == "Owner One"

    def test_set_primary_is_exclusive(self, client, tmp_db):
        with get_connection() as conn:
            _contact(conn)
        a = client.post("/api/v1/contacts/ct-1/identifiers",
                        json={"value": "a@x.com", "is_primary": True}).json()
        b = client.post("/api/v1/contacts/ct-1/identifiers",
                        json={"value": "b@x.com"}).json()
        client.put(f"/api/v1/contacts/ct-1/identifiers/{b['id']}",
                   json={"is_primary": True})
        subs = client.get("/api/v1/contacts/ct-1/subresources").json()
        primaries = {i["value"]: i["is_primary"] for i in subs["identifiers"]}
        assert primaries == {"a@x.com": 0, "b@x.com": 1}
        assert a["is_primary"] == 1

    def test_delete_requires_matching_parent(self, client, tmp_db):
        with get_connection() as conn:
            _contact(conn, "ct-1")
            _contact(conn, "ct-2")
        row = client.post("/api/v1/contacts/ct-1/identifiers",
                          json={"value": "z@x.com"}).json()
        r = client.delete(f"/api/v1/contacts/ct-2/identifiers/{row['id']}")
        assert r.status_code == 404
        r = client.delete(f"/api/v1/contacts/ct-1/identifiers/{row['id']}")
        assert r.status_code == 200

    def test_other_customer_contact_is_404(self, client, tmp_db):
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO customers (id, name, slug, is_active, created_at, updated_at) "
                "VALUES ('cust-other', 'Other', 'other', 1, ?, ?)", (_NOW, _NOW))
            _contact(conn, "ct-x", "Foreign", customer="cust-other")
        r = client.post("/api/v1/contacts/ct-x/identifiers",
                        json={"value": "n@x.com"})
        assert r.status_code == 404


class TestPhones:
    def test_add_normalizes_and_formats(self, client, tmp_db):
        with get_connection() as conn:
            _contact(conn)
        r = client.post("/api/v1/contacts/ct-1/phones",
                        json={"number": "330-242-1961"})
        assert r.status_code == 200
        assert r.json()["number"] == "+13302421961"
        assert r.json()["display"] == "(330) 242-1961"

    def test_invalid_number_400(self, client, tmp_db):
        with get_connection() as conn:
            _contact(conn)
        r = client.post("/api/v1/contacts/ct-1/phones", json={"number": "abc"})
        assert r.status_code == 400

    def test_duplicate_add_is_idempotent(self, client, tmp_db):
        with get_connection() as conn:
            _contact(conn)
        a = client.post("/api/v1/contacts/ct-1/phones",
                        json={"number": "(330) 242-1961"}).json()
        b = client.post("/api/v1/contacts/ct-1/phones",
                        json={"number": "330.242.1961"}).json()
        assert a["id"] == b["id"]

    def test_set_primary_exclusive_and_delete(self, client, tmp_db):
        with get_connection() as conn:
            _company(conn)
        a = client.post("/api/v1/companies/co-1/phones",
                        json={"number": "330-242-1961"}).json()
        b = client.post("/api/v1/companies/co-1/phones",
                        json={"number": "440-247-4563"}).json()
        client.put(f"/api/v1/companies/co-1/phones/{a['id']}",
                   json={"is_primary": True})
        client.put(f"/api/v1/companies/co-1/phones/{b['id']}",
                   json={"is_primary": True})
        subs = client.get("/api/v1/companies/co-1/subresources").json()
        primaries = {p["id"]: p["is_primary"] for p in subs["phones"]}
        assert primaries[a["id"]] == 0 and primaries[b["id"]] == 1
        assert client.delete(
            f"/api/v1/companies/co-1/phones/{a['id']}").status_code == 200
        subs = client.get("/api/v1/companies/co-1/subresources").json()
        assert len(subs["phones"]) == 1


class TestAddresses:
    def test_blank_address_rejected(self, client, tmp_db):
        with get_connection() as conn:
            _contact(conn)
        r = client.post("/api/v1/contacts/ct-1/addresses", json={})
        assert r.status_code == 400

    def test_add_edit_full_fields(self, client, tmp_db):
        with get_connection() as conn:
            _contact(conn)
        row = client.post("/api/v1/contacts/ct-1/addresses",
                          json={"city": "Chagrin Falls", "state": "OH"}).json()
        r = client.put(f"/api/v1/contacts/ct-1/addresses/{row['id']}",
                       json={"street": "1 Main St", "postal_code": "44022",
                             "country": "US"})
        assert r.json()["street"] == "1 Main St"
        assert r.json()["city"] == "Chagrin Falls"


class TestCompanyEmailsAndIdentifiers:
    def test_email_roundtrip(self, client, tmp_db):
        with get_connection() as conn:
            _company(conn)
        row = client.post("/api/v1/companies/co-1/emails",
                          json={"address": "Info@TestCo.com"}).json()
        assert row["address"] == "info@testco.com"
        client.put(f"/api/v1/companies/co-1/emails/{row['id']}",
                   json={"email_type": "support"})
        subs = client.get("/api/v1/companies/co-1/subresources").json()
        assert subs["emails"][0]["email_type"] == "support"
        assert client.delete(
            f"/api/v1/companies/co-1/emails/{row['id']}").status_code == 200

    def test_identifier_duplicate_409(self, client, tmp_db):
        with get_connection() as conn:
            _company(conn, "co-1", "First Co")
            _company(conn, "co-2", "Second Co")
        client.post("/api/v1/companies/co-1/identifiers",
                    json={"value": "testco.com"})
        r = client.post("/api/v1/companies/co-2/identifiers",
                        json={"value": "TestCo.com"})
        assert r.status_code == 409
        assert r.json()["other_company_name"] == "First Co"


class TestAffiliations:
    def test_add_primary_exclusive(self, client, tmp_db):
        with get_connection() as conn:
            _contact(conn)
            _company(conn, "co-1")
            _company(conn, "co-2", "Other Co")
        a = client.post("/api/v1/contacts/ct-1/affiliations",
                        json={"company_id": "co-1", "title": "CTO",
                              "is_primary": True}).json()
        assert a["is_primary"] == 1
        b = client.post("/api/v1/contacts/ct-1/affiliations",
                        json={"company_id": "co-2", "is_primary": True}).json()
        subs = client.get("/api/v1/contacts/ct-1/subresources").json()
        primaries = {x["company_id"]: x["is_primary"] for x in subs["affiliations"]}
        assert primaries == {"co-1": 0, "co-2": 1}
        assert b["company_name"] == "Other Co"

    def test_update_and_delete(self, client, tmp_db):
        with get_connection() as conn:
            _contact(conn)
            _company(conn)
        row = client.post("/api/v1/contacts/ct-1/affiliations",
                          json={"company_id": "co-1"}).json()
        r = client.put(f"/api/v1/contacts/ct-1/affiliations/{row['id']}",
                       json={"title": "VP Sales"})
        assert r.json()["title"] == "VP Sales"
        assert client.delete(
            f"/api/v1/contacts/ct-1/affiliations/{row['id']}").status_code == 200
        subs = client.get("/api/v1/contacts/ct-1/subresources").json()
        assert subs["affiliations"] == []

    def test_edit_all_fields_roundtrip(self, client, tmp_db):
        """The Manage modal edits title, department, role, and current."""
        with get_connection() as conn:
            _contact(conn)
            _company(conn)
            conn.execute(
                "INSERT INTO contact_company_roles (id, customer_id, name, "
                "sort_order, is_system, created_at, updated_at) "
                "VALUES ('role-x', ?, 'Advisor', 0, 0, ?, ?)",
                (CUST_ID, _NOW, _NOW))
        row = client.post("/api/v1/contacts/ct-1/affiliations",
                          json={"company_id": "co-1", "title": "Analyst"}).json()
        r = client.put(f"/api/v1/contacts/ct-1/affiliations/{row['id']}",
                       json={"title": "Senior Analyst", "department": "Finance",
                             "role_id": "role-x", "is_current": False})
        assert r.status_code == 200
        subs = client.get("/api/v1/contacts/ct-1/subresources").json()
        aff = subs["affiliations"][0]
        assert aff["title"] == "Senior Analyst"
        assert aff["department"] == "Finance"
        assert aff["role_name"] == "Advisor"
        assert aff["is_current"] == 0


class TestHierarchy:
    def _three(self, conn):
        _company(conn, "co-a", "A")
        _company(conn, "co-b", "B")
        _company(conn, "co-c", "C")

    def test_parent_direction_and_listing(self, client, tmp_db):
        with get_connection() as conn:
            self._three(conn)
        r = client.post("/api/v1/companies/co-b/hierarchy",
                        json={"related_company_id": "co-a", "direction": "parent"})
        assert r.status_code == 200
        subs = client.get("/api/v1/companies/co-b/subresources").json()
        assert subs["hierarchy"]["parents"][0]["parent_name"] == "A"

    def test_self_link_422(self, client, tmp_db):
        with get_connection() as conn:
            self._three(conn)
        r = client.post("/api/v1/companies/co-a/hierarchy",
                        json={"related_company_id": "co-a"})
        assert r.status_code == 422

    def test_duplicate_409(self, client, tmp_db):
        with get_connection() as conn:
            self._three(conn)
        client.post("/api/v1/companies/co-b/hierarchy",
                    json={"related_company_id": "co-a"})
        r = client.post("/api/v1/companies/co-b/hierarchy",
                        json={"related_company_id": "co-a"})
        assert r.status_code == 409

    def test_cycle_422(self, client, tmp_db):
        with get_connection() as conn:
            self._three(conn)
        # A is parent of B, B is parent of C — C cannot become parent of A
        client.post("/api/v1/companies/co-b/hierarchy",
                    json={"related_company_id": "co-a", "direction": "parent"})
        client.post("/api/v1/companies/co-c/hierarchy",
                    json={"related_company_id": "co-b", "direction": "parent"})
        r = client.post("/api/v1/companies/co-a/hierarchy",
                        json={"related_company_id": "co-c", "direction": "parent"})
        assert r.status_code == 422

    def test_bad_type_422(self, client, tmp_db):
        with get_connection() as conn:
            self._three(conn)
        r = client.post("/api/v1/companies/co-b/hierarchy",
                        json={"related_company_id": "co-a",
                              "hierarchy_type": "franchise"})
        assert r.status_code == 422


class TestEntityDeletes:
    def test_company_delete_unlinks_and_cleans(self, client, tmp_db):
        with get_connection() as conn:
            _contact(conn)
            _company(conn)
        client.post("/api/v1/contacts/ct-1/affiliations",
                    json={"company_id": "co-1"})
        client.post("/api/v1/companies/co-1/phones",
                    json={"number": "330-242-1961"})
        r = client.delete("/api/v1/companies/co-1")
        assert r.status_code == 200
        assert r.json()["contacts_unlinked"] == 1
        with get_connection() as conn:
            assert conn.execute(
                "SELECT COUNT(*) FROM phone_numbers WHERE entity_id = 'co-1'"
            ).fetchone()[0] == 0
            assert conn.execute(
                "SELECT COUNT(*) FROM contacts WHERE id = 'ct-1'"
            ).fetchone()[0] == 1

    def test_contact_delete(self, client, tmp_db):
        with get_connection() as conn:
            _contact(conn)
        client.post("/api/v1/contacts/ct-1/identifiers", json={"value": "d@x.com"})
        client.post("/api/v1/contacts/ct-1/phones", json={"number": "330-242-1961"})
        r = client.delete("/api/v1/contacts/ct-1")
        assert r.status_code == 200
        with get_connection() as conn:
            for table, where in (
                ("contacts", "id = 'ct-1'"),
                ("contact_identifiers", "contact_id = 'ct-1'"),
                ("phone_numbers", "entity_id = 'ct-1'"),
            ):
                assert conn.execute(
                    f"SELECT COUNT(*) FROM {table} WHERE {where}"
                ).fetchone()[0] == 0


class TestScoreRecompute:
    def test_no_communications_returns_null_score(self, client, tmp_db):
        with get_connection() as conn:
            _contact(conn)
        r = client.post("/api/v1/contacts/ct-1/score")
        assert r.status_code == 200
        assert r.json()["score"] is None


class TestContactCreateAndCheck:
    """Tier 1 contact management (Contact Entity Base PRD KP-1)."""

    def test_rich_create(self, client, tmp_db):
        with get_connection() as conn:
            _company(conn, "co-rich", "Rich Co")
        r = client.post("/api/v1/contacts", json={
            "name": "Rich Contact", "email": "Rich@New.com",
            "phone": "330-242-1961", "company_id": "co-rich",
            "title": "CTO", "social_url": "https://linkedin.com/in/rich"})
        assert r.status_code == 200, r.text
        cid = r.json()["id"]
        subs = client.get(f"/api/v1/contacts/{cid}/subresources").json()
        assert subs["identifiers"][0]["value"] == "rich@new.com"
        assert subs["phones"][0]["number"] == "+13302421961"
        aff = subs["affiliations"][0]
        assert (aff["company_name"], aff["title"], aff["is_primary"]) == (
            "Rich Co", "CTO", 1)
        with get_connection() as conn:
            sp = conn.execute(
                "SELECT platform, profile_url FROM contact_social_profiles "
                "WHERE contact_id = ?", (cid,)).fetchone()
        assert sp["platform"] == "linkedin"

    def test_create_duplicate_email_409(self, client, tmp_db):
        client.post("/api/v1/contacts", json={
            "name": "First", "email": "dup@x.com"})
        r = client.post("/api/v1/contacts", json={
            "name": "Second", "email": "DUP@x.com"})
        assert r.status_code == 409
        assert r.json()["other_contact_name"] == "First"
        # No orphan contact row was created
        with get_connection() as conn:
            n = conn.execute(
                "SELECT COUNT(*) FROM contacts WHERE name = 'Second'"
            ).fetchone()[0]
        assert n == 0

    def test_check_matches_email_phone_name(self, client, tmp_db):
        client.post("/api/v1/contacts", json={
            "name": "Known Person", "email": "known@x.com",
            "phone": "(440) 247-4563"})
        r = client.post("/api/v1/contacts/check", json={
            "name": "known person", "email": "known@x.com",
            "phone": "440.247.4563"})
        matches = r.json()["matches"]
        assert len(matches) == 1
        assert sorted(matches[0]["match_on"]) == ["email", "name", "phone"]
        r = client.post("/api/v1/contacts/check", json={"name": "Nobody"})
        assert r.json()["matches"] == []

    def test_core_field_update(self, client, tmp_db):
        c = client.post("/api/v1/contacts", json={"name": "Rename Me"}).json()
        r = client.put(f"/api/v1/contacts/{c['id']}",
                       json={"name": "Renamed", "status": "archived"})
        assert r.json()["name"] == "Renamed"
        assert r.json()["status"] == "archived"
        assert client.put(f"/api/v1/contacts/{c['id']}",
                          json={"status": "bogus"}).status_code == 400
