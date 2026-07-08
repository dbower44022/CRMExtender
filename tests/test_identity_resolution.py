"""Tests for the identity resolution engine and review queue (Tier 3a)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from poc.database import get_connection, init_db
from poc.identity_resolution import (
    combine,
    get_thresholds,
    load_profiles,
    scan_existing_contacts,
    score_pair,
)

_NOW = datetime.now(timezone.utc).isoformat()

CUST_ID = "cust-idr"
USER_ID = "user-idr"


@pytest.fixture()
def tmp_db(tmp_path, monkeypatch):
    db_file = tmp_path / "test.db"
    monkeypatch.setattr("poc.config.DB_PATH", db_file)
    monkeypatch.setattr("poc.config.CRM_AUTH_ENABLED", False)
    init_db(db_file)
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO customers (id, name, slug, is_active, created_at, updated_at) "
            "VALUES (?, 'IDR Org', 'idr', 1, ?, ?)", (CUST_ID, _NOW, _NOW))
        conn.execute(
            "INSERT INTO users "
            "(id, customer_id, email, name, role, is_active, created_at, updated_at) "
            "VALUES (?, ?, 'a@idr.com', 'IDR Admin', 'admin', 1, ?, ?)",
            (USER_ID, CUST_ID, _NOW, _NOW))
    return db_file


def _contact(conn, cid, name, *, email=None, phone=None, company_id=None,
             title=None):
    conn.execute(
        "INSERT INTO contacts (id, customer_id, name, status, created_at, updated_at) "
        "VALUES (?, ?, ?, 'active', ?, ?)", (cid, CUST_ID, name, _NOW, _NOW))
    if email:
        conn.execute(
            "INSERT INTO contact_identifiers (id, contact_id, type, value, "
            "is_primary, is_current, created_at, updated_at) "
            "VALUES (?, ?, 'email', ?, 1, 1, ?, ?)",
            (str(uuid.uuid4()), cid, email, _NOW, _NOW))
    if phone:
        conn.execute(
            "INSERT INTO phone_numbers (id, entity_type, entity_id, phone_type, "
            "number, is_primary, is_current, source, created_at, updated_at) "
            "VALUES (?, 'contact', ?, 'mobile', ?, 1, 1, 'test', ?, ?)",
            (str(uuid.uuid4()), cid, phone, _NOW, _NOW))
    if company_id:
        conn.execute(
            "INSERT INTO contact_companies (id, contact_id, company_id, title, "
            "is_primary, is_current, source, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, 1, 1, 'test', ?, ?)",
            (str(uuid.uuid4()), cid, company_id, title, _NOW, _NOW))


def _company(conn, coid="co-idr", name="IDR Co"):
    conn.execute(
        "INSERT INTO companies (id, customer_id, name, status, created_at, updated_at) "
        "VALUES (?, ?, ?, 'active', ?, ?)", (coid, CUST_ID, name, _NOW, _NOW))


class TestConfidenceMath:
    def test_combination_formula(self):
        # name exact (0.30) + company exact (0.25) + email domain (0.20)
        assert combine([0.30, 0.25, 0.20]) == pytest.approx(0.58, abs=0.001)

    def test_definitive_signal_dominates(self):
        assert combine([1.0, 0.30]) == 1.0

    def test_thresholds_default_and_custom(self, tmp_db):
        from poc.settings import set_setting
        t = get_thresholds(CUST_ID)
        assert t == {"auto": 0.90, "flag": 0.70, "review": 0.40}
        set_setting(CUST_ID, "idr_threshold_review", "0.55")
        assert get_thresholds(CUST_ID)["review"] == 0.55


class TestScoring:
    def _profiles(self):
        return {p.name: p for p in load_profiles(CUST_ID)}

    def test_exact_email_confidence_1(self):
        from poc.identity_resolution import ContactProfile
        empty = frozenset()
        a = ContactProfile("a", "A One", frozenset({"same@x.com"}),
                           empty, empty, empty, empty, empty)
        b = ContactProfile("b", "B Two", frozenset({"same@x.com"}),
                           empty, empty, empty, empty, empty)
        r = score_pair(a, b)
        assert r.confidence == 1.0
        assert any(s.name == "email_exact" for s in r.signals)

    def test_phone_match_095(self, tmp_db):
        with get_connection() as conn:
            _contact(conn, "a", "A One", phone="+13302421961")
            _contact(conn, "b", "B Two", phone="+13302421961")
        p = self._profiles()
        assert score_pair(p["A One"], p["B Two"]).confidence == 0.95

    def test_name_and_company_medium(self, tmp_db):
        with get_connection() as conn:
            _company(conn)
            _contact(conn, "a", "Pat Smith", company_id="co-idr")
            _contact(conn, "b", "Pat Smith", company_id="co-idr")
        p = load_profiles(CUST_ID)
        r = score_pair(p[0], p[1])
        # name exact 0.30 + company exact 0.25 -> 0.475
        assert 0.40 <= r.confidence <= 0.69

    def test_name_only_low(self, tmp_db):
        with get_connection() as conn:
            _contact(conn, "a", "Pat Smith")
            _contact(conn, "b", "Pat Smith")
        p = load_profiles(CUST_ID)
        assert score_pair(p[0], p[1]).confidence == 0.30


class TestScan:
    def test_scan_queues_and_is_idempotent(self, tmp_db):
        with get_connection() as conn:
            _contact(conn, "a", "Dup Person", email="dup@corp.com")
            _contact(conn, "b", "Dup Person", email="dup2@corp.com")
            _contact(conn, "c", "Unrelated Human")
        r1 = scan_existing_contacts(customer_id=CUST_ID)
        assert r1["candidates_created"] == 1
        r2 = scan_existing_contacts(customer_id=CUST_ID)
        assert r2["candidates_created"] == 0

    def test_rejected_pair_not_requeued(self, tmp_db):
        with get_connection() as conn:
            _contact(conn, "a", "Dup Person", email="dup@corp.com")
            _contact(conn, "b", "Dup Person", email="dup2@corp.com")
        scan_existing_contacts(customer_id=CUST_ID)
        with get_connection() as conn:
            conn.execute("UPDATE match_candidates SET status = 'rejected'")
        r = scan_existing_contacts(customer_id=CUST_ID)
        assert r["candidates_created"] == 0


class TestReviewQueueApi:
    @pytest.fixture()
    def client(self, tmp_db, monkeypatch):
        monkeypatch.setattr(
            "poc.hierarchy.get_current_user",
            lambda: {"id": USER_ID, "email": "a@idr.com", "name": "IDR Admin",
                     "role": "admin", "customer_id": CUST_ID})
        from poc.web.app import create_app
        return TestClient(create_app(), raise_server_exceptions=False)

    def _seed_pair(self, client):
        with get_connection() as conn:
            _contact(conn, "a", "Dup Person", email="dup@corp.com")
            _contact(conn, "b", "Dup Person", email="dup2@corp.com")
        return client.post("/api/v1/contacts/duplicate-scan").json()

    def test_scan_and_list(self, client, tmp_db):
        scan = self._seed_pair(client)
        assert scan["candidates_created"] == 1
        queue = client.get("/api/v1/contacts/review-queue").json()
        assert queue["pending_count"] == 1
        cand = queue["candidates"][0]
        assert {cand["name_a"], cand["name_b"]} == {"Dup Person"}
        assert cand["confidence"] > 0.4
        assert any(s["name"] == "name_exact" for s in cand["signals"])

    def test_reject_and_restore(self, client, tmp_db):
        self._seed_pair(client)
        cand = client.get("/api/v1/contacts/review-queue").json()["candidates"][0]
        assert client.post(
            f"/api/v1/contacts/review-queue/{cand['id']}/reject"
        ).json()["status"] == "rejected"
        assert client.get(
            "/api/v1/contacts/review-queue").json()["pending_count"] == 0
        assert client.post(
            f"/api/v1/contacts/review-queue/{cand['id']}/restore"
        ).json()["status"] == "pending"
        assert client.get(
            "/api/v1/contacts/review-queue").json()["pending_count"] == 1

    def test_merge_auto_resolves(self, client, tmp_db):
        self._seed_pair(client)
        assert client.get(
            "/api/v1/contacts/review-queue").json()["pending_count"] == 1
        from poc.contact_merge import merge_contacts
        merge_contacts("a", ["b"], merged_by=USER_ID)
        # FK cascade removed the candidate touching the absorbed contact
        assert client.get(
            "/api/v1/contacts/review-queue").json()["pending_count"] == 0

    def test_merge_leaves_unrelated_candidate(self, client, tmp_db):
        """A survivor's candidate with a third contact stays pending."""
        with get_connection() as conn:
            _contact(conn, "a", "Dup Person", email="dup@corp.com")
            _contact(conn, "b", "Dup Person", email="dup2@corp.com")
            _contact(conn, "c", "Dup Person", email="dup3@corp.com")
        client.post("/api/v1/contacts/duplicate-scan")
        assert client.get(
            "/api/v1/contacts/review-queue").json()["pending_count"] == 3
        from poc.contact_merge import merge_contacts
        merge_contacts("a", ["b"], merged_by=USER_ID)
        # (a,b) and (b,c) gone with b; (a,c) survives
        assert client.get(
            "/api/v1/contacts/review-queue").json()["pending_count"] == 1


class TestRealtimeResolution:
    def test_resolve_new_contact_queues_fuzzy_match(self, tmp_db):
        from poc.identity_resolution import resolve_new_contact
        with get_connection() as conn:
            _company(conn, "co-x", "Acme Corp")
            _contact(conn, "existing", "Pat Q Smith", company_id="co-x",
                     email="pat@personal.com")
            _contact(conn, "newone", "Pat Q Smith", company_id="co-x",
                     email="psmith@work.com")
        r = resolve_new_contact("newone", customer_id=CUST_ID, source="import")
        assert r["candidates_created"] == 1
        with get_connection() as conn:
            row = conn.execute(
                "SELECT status, source FROM match_candidates").fetchone()
        assert row["status"] == "pending"
        assert row["source"] == "import"

    def test_resolve_is_idempotent(self, tmp_db):
        from poc.identity_resolution import resolve_new_contact
        with get_connection() as conn:
            _contact(conn, "existing", "Dup Name", email="a@corp.io")
            _contact(conn, "newone", "Dup Name", email="b@corp.io")
        assert resolve_new_contact(
            "newone", customer_id=CUST_ID, source="import"
        )["candidates_created"] == 1
        assert resolve_new_contact(
            "newone", customer_id=CUST_ID, source="import"
        )["candidates_created"] == 0

    def test_no_candidate_for_unrelated_contact(self, tmp_db):
        from poc.identity_resolution import resolve_new_contact
        with get_connection() as conn:
            _contact(conn, "existing", "Alice Johnson", email="alice@x.com")
            _contact(conn, "newone", "Bob Williams", email="bob@y.com")
        assert resolve_new_contact(
            "newone", customer_id=CUST_ID, source="manual_entry"
        )["candidates_created"] == 0

    def test_pending_contact_ids(self, tmp_db):
        from poc.identity_resolution import (
            pending_candidate_contact_ids, resolve_new_contact)
        with get_connection() as conn:
            _contact(conn, "existing", "Dup Name", email="a@corp.io")
            _contact(conn, "newone", "Dup Name", email="b@corp.io")
        resolve_new_contact("newone", customer_id=CUST_ID, source="import")
        assert pending_candidate_contact_ids(CUST_ID) == {"existing", "newone"}


class TestDuplicateBadgeApi:
    @pytest.fixture()
    def client(self, tmp_db, monkeypatch):
        monkeypatch.setattr(
            "poc.hierarchy.get_current_user",
            lambda: {"id": USER_ID, "email": "a@idr.com", "name": "IDR Admin",
                     "role": "admin", "customer_id": CUST_ID})
        from poc.web.app import create_app
        return TestClient(create_app(), raise_server_exceptions=False)

    def test_manual_create_queues_and_badges(self, client, tmp_db):
        with get_connection() as conn:
            _company(conn, "co-navy", "US Navy")
            _contact(conn, "existing", "Grace Hopper", company_id="co-navy",
                     email="grace@navy.mil")
            conn.execute(
                "INSERT INTO user_contacts (id, user_id, contact_id, "
                "visibility, is_owner, created_at, updated_at) "
                "VALUES ('uc-ex', ?, 'existing', 'public', 1, ?, ?)",
                (USER_ID, _NOW, _NOW))
        # Same name + same company -> 0.30 + 0.25 = 0.475, above review
        r = client.post("/api/v1/contacts", json={
            "first_name": "Grace", "last_name": "Hopper",
            "company_id": "co-navy"})
        new_id = r.json()["id"]
        detail = client.get(f"/api/v1/contacts/{new_id}").json()
        assert detail["identity"]["is_possible_duplicate"] is True
        detail2 = client.get("/api/v1/contacts/existing").json()
        assert detail2["identity"]["is_possible_duplicate"] is True
        assert client.get(
            "/api/v1/contacts/review-queue").json()["pending_count"] == 1
