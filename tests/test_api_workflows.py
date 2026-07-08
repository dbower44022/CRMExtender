"""Tests for the Phase 4 workflow JSON API (Legacy UI Migration PRD)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from poc.database import get_connection, init_db

_NOW = datetime.now(timezone.utc).isoformat()

CUST_ID = "cust-wf-test"
USER_ID = "user-wf-admin"


@pytest.fixture()
def tmp_db(tmp_path, monkeypatch):
    db_file = tmp_path / "test.db"
    monkeypatch.setattr("poc.config.DB_PATH", db_file)
    monkeypatch.setattr("poc.config.CRM_AUTH_ENABLED", False)
    init_db(db_file)

    with get_connection() as conn:
        conn.execute(
            "INSERT INTO customers (id, name, slug, is_active, created_at, updated_at) "
            "VALUES (?, 'WF Org', 'wf', 1, ?, ?)", (CUST_ID, _NOW, _NOW))
        conn.execute(
            "INSERT INTO users "
            "(id, customer_id, email, name, role, is_active, created_at, updated_at) "
            "VALUES (?, ?, 'admin@wf.com', 'WF Admin', 'admin', 1, ?, ?)",
            (USER_ID, CUST_ID, _NOW, _NOW))
        for i in (1, 2, 3):
            conn.execute(
                "INSERT INTO contacts (id, customer_id, name, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (f"ct-{i}", CUST_ID, f"Contact {i}", _NOW, _NOW))
        conn.execute(
            "INSERT INTO companies (id, customer_id, name, domain, status, created_at, updated_at) "
            "VALUES ('co-1', ?, 'WF Co', 'wfco.com', 'active', ?, ?)",
            (CUST_ID, _NOW, _NOW))
    return db_file


@pytest.fixture()
def client(tmp_db, monkeypatch):
    monkeypatch.setattr(
        "poc.hierarchy.get_current_user",
        lambda: {"id": USER_ID, "email": "admin@wf.com", "name": "WF Admin",
                 "role": "admin", "customer_id": CUST_ID})
    from poc.web.app import create_app
    return TestClient(create_app(), raise_server_exceptions=False)


def _conversation(conn, conv_id="conv-1", title="WF Conversation", dismissed=0):
    conn.execute(
        "INSERT INTO conversations (id, customer_id, title, dismissed, "
        "last_activity_at, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (conv_id, CUST_ID, title, dismissed, _NOW, _NOW, _NOW))


def _communication(conn, comm_id="comm-1"):
    conn.execute(
        "INSERT INTO communications (id, channel, timestamp, created_at, updated_at) "
        "VALUES (?, 'email', ?, ?, ?)", (comm_id, _NOW, _NOW, _NOW))


def _link(conn, conv_id, comm_id):
    conn.execute(
        "INSERT INTO conversation_communications "
        "(conversation_id, communication_id, created_at) VALUES (?, ?, ?)",
        (conv_id, comm_id, _NOW))


class TestRelationships:
    def test_create_batch_and_list(self, client, tmp_db):
        r = client.post("/api/v1/relationships", json={
            "relationship_type_id": "rt-knows",
            "to_entity_id": "ct-3",
            "from_entity_ids": ["ct-1", "ct-2", "ct-3"]})
        assert r.status_code == 201
        results = {x["from_entity_id"]: x["status"] for x in r.json()["results"]}
        assert results == {"ct-1": "created", "ct-2": "created",
                           "ct-3": "skipped"}
        listing = client.get("/api/v1/relationships").json()["relationships"]
        assert len(listing) == 2
        assert all(x["id"] for x in listing)

    def test_duplicate_skipped(self, client, tmp_db):
        client.post("/api/v1/relationships", json={
            "relationship_type_id": "rt-knows",
            "to_entity_id": "ct-2", "from_entity_id": "ct-1"})
        r = client.post("/api/v1/relationships", json={
            "relationship_type_id": "rt-knows",
            "to_entity_id": "ct-1", "from_entity_id": "ct-2"})
        assert r.json()["results"][0]["status"] == "skipped"

    def test_delete_manual_only(self, client, tmp_db):
        r = client.post("/api/v1/relationships", json={
            "relationship_type_id": "rt-knows",
            "to_entity_id": "ct-2", "from_entity_id": "ct-1"})
        rel_id = r.json()["results"][0]["relationship_id"]
        assert client.delete(f"/api/v1/relationships/{rel_id}").json()["deleted"]
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO relationships (id, relationship_type_id, "
                "from_entity_id, to_entity_id, source, created_at, updated_at) "
                "VALUES ('rel-inf', 'rt-knows', 'ct-1', 'ct-2', 'inferred', ?, ?)",
                (_NOW, _NOW))
        assert client.delete("/api/v1/relationships/rel-inf").status_code == 400

    def test_infer(self, client, tmp_db):
        with get_connection() as conn:
            _conversation(conn)
            for ct in ("ct-1", "ct-2"):
                conn.execute(
                    "INSERT INTO conversation_participants "
                    "(conversation_id, email_address, address, contact_id) "
                    "VALUES ('conv-1', ?, ?, ?)",
                    (f"{ct}@x.com", f"{ct}@x.com", ct))
        r = client.post("/api/v1/relationships/infer")
        assert r.json()["count"] == 1
        inferred = client.get("/api/v1/relationships?source=inferred").json()
        assert len(inferred["relationships"]) == 1

    def test_type_create_scoped_and_duplicate_400(self, client, tmp_db):
        r = client.post("/api/v1/relationship-types", json={
            "name": "Mentor", "forward_label": "Mentors",
            "reverse_label": "Mentored by"})
        assert r.status_code == 201
        assert r.json()["customer_id"] == CUST_ID
        assert client.post("/api/v1/relationship-types",
                           json={"name": "Mentor"}).status_code == 400
        types = client.get("/api/v1/relationship-types").json()["types"]
        assert any(t["name"] == "Mentor" for t in types)

    def test_type_delete_in_use_400(self, client, tmp_db):
        client.post("/api/v1/relationships", json={
            "relationship_type_id": "rt-knows",
            "to_entity_id": "ct-2", "from_entity_id": "ct-1"})
        r = client.delete("/api/v1/relationship-types/rt-knows")
        assert r.status_code == 400


class TestTopicAssignment:
    def _project_topic(self, client):
        proj = client.post("/api/v1/projects", json={"name": "WF Project"}).json()
        topic = client.post(f"/api/v1/projects/{proj['id']}/topics",
                            json={"name": "WF Topic"}).json()
        return proj, topic

    def test_assign_and_unassign(self, client, tmp_db):
        proj, topic = self._project_topic(client)
        with get_connection() as conn:
            _conversation(conn)
        r = client.post("/api/v1/conversations/conv-1/topic",
                        json={"topic_id": topic["id"]})
        assert r.json()["topic"]["name"] == "WF Topic"
        assert r.json()["topic"]["project_name"] == "WF Project"
        r = client.delete("/api/v1/conversations/conv-1/topic")
        assert r.json()["topic"] is None

    def test_topics_listing(self, client, tmp_db):
        proj, topic = self._project_topic(client)
        topics = client.get("/api/v1/topics").json()["topics"]
        assert [t["name"] for t in topics] == ["WF Topic"]


class TestCommunicationsBulk:
    def test_archive_dismisses_empty_conversations(self, client, tmp_db):
        with get_connection() as conn:
            _conversation(conn)
            _communication(conn, "comm-1")
            _link(conn, "conv-1", "comm-1")
        r = client.post("/api/v1/communications/archive",
                        json={"ids": ["comm-1"]})
        assert r.json() == {"archived": 1, "conversations_dismissed": 1,
                            "skipped": 0}
        with get_connection() as conn:
            conv = conn.execute(
                "SELECT dismissed, dismissed_reason FROM conversations "
                "WHERE id = 'conv-1'").fetchone()
            assert conv["dismissed"] == 1
            assert conv["dismissed_reason"] == "archived"

    def test_assign_and_targets(self, client, tmp_db):
        with get_connection() as conn:
            _conversation(conn, "conv-t", "Target Conversation")
            _communication(conn, "comm-2")
        targets = client.get(
            "/api/v1/communications/assign-targets?q=target").json()
        assert [t["title"] for t in targets["conversations"]] == [
            "Target Conversation"]
        r = client.post("/api/v1/communications/assign",
                        json={"ids": ["comm-2"], "conversation_id": "conv-t"})
        assert r.json()["assigned"] == 1
        # Repeat is idempotent
        r = client.post("/api/v1/communications/assign",
                        json={"ids": ["comm-2"], "conversation_id": "conv-t"})
        assert r.json()["skipped_existing"] == 1

    def test_delete_conversation_with_comms(self, client, tmp_db):
        with get_connection() as conn:
            _conversation(conn, "conv-d")
            _communication(conn, "comm-3")
            _link(conn, "conv-d", "comm-3")
        r = client.post("/api/v1/communications/delete-conversation",
                        json={"ids": ["comm-3"], "delete_comms": True})
        assert r.json() == {"conversations_deleted": 1,
                            "communications_deleted": 1}


class TestProjectsTopics:
    def test_crud_and_impact_counts(self, client, tmp_db):
        proj = client.post("/api/v1/projects", json={"name": "P1"}).json()
        assert client.post("/api/v1/projects",
                           json={"name": "P1"}).status_code == 409
        topic = client.post(f"/api/v1/projects/{proj['id']}/topics",
                            json={"name": "T1"}).json()
        assert client.post(f"/api/v1/projects/{proj['id']}/topics",
                           json={"name": "T1"}).status_code == 409
        with get_connection() as conn:
            _conversation(conn, "conv-p")
            conn.execute("UPDATE conversations SET topic_id = ? WHERE id = 'conv-p'",
                         (topic["id"],))
        r = client.delete(
            f"/api/v1/projects/{proj['id']}/topics/{topic['id']}")
        assert r.json()["conversations_unassigned"] == 1
        listing = client.get("/api/v1/projects").json()["projects"]
        assert listing[0]["topic_count"] == 0
        r = client.delete(f"/api/v1/projects/{proj['id']}")
        assert r.json()["deleted"] is True

    def test_auto_assign_preview_and_apply(self, client, tmp_db):
        proj = client.post("/api/v1/projects", json={"name": "Budget"}).json()
        client.post(f"/api/v1/projects/{proj['id']}/topics",
                    json={"name": "Invoices"})
        with get_connection() as conn:
            _conversation(conn, "conv-a", "Invoices for March")
        preview = client.post(
            f"/api/v1/projects/{proj['id']}/auto-assign/preview").json()
        assert preview["matched"] == 1
        assert preview["assignments"][0]["conversation_id"] == "conv-a"
        applied = client.post(
            f"/api/v1/projects/{proj['id']}/auto-assign/apply").json()
        assert applied["assigned"] == 1
        with get_connection() as conn:
            row = conn.execute(
                "SELECT topic_id FROM conversations WHERE id = 'conv-a'"
            ).fetchone()
            assert row["topic_id"] is not None

    def test_auto_assign_no_topics_422(self, client, tmp_db):
        proj = client.post("/api/v1/projects", json={"name": "Empty"}).json()
        r = client.post(f"/api/v1/projects/{proj['id']}/auto-assign/preview")
        assert r.status_code == 422


class TestEvents:
    def test_create_validates_and_returns_row(self, client, tmp_db):
        r = client.post("/api/v1/events", json={
            "title": "Kickoff", "event_type": "meeting",
            "start_datetime": "2026-08-01T10:00:00+00:00"})
        assert r.status_code == 201
        assert r.json()["source"] == "manual"
        assert client.post("/api/v1/events", json={
            "title": "Bad", "event_type": "party"}).status_code == 400

    def test_delete_reports_source(self, client, tmp_db):
        ev = client.post("/api/v1/events", json={"title": "Temp"}).json()
        r = client.delete(f"/api/v1/events/{ev['id']}")
        assert r.json() == {"deleted": True, "source": "manual"}

    def test_calendar_sync_trigger(self, client, tmp_db, monkeypatch):
        import poc.sync_service as sync_service
        monkeypatch.setattr(
            sync_service, "start_background_calendar_sync", lambda **kw: True)
        assert client.post("/api/v1/events/sync").json() == {"status": "started"}
        monkeypatch.setattr(
            sync_service, "start_background_calendar_sync", lambda **kw: False)
        assert client.post("/api/v1/events/sync").status_code == 409


class TestCompanyOps:
    def test_resolve_domains(self, client, tmp_db):
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO contact_identifiers (id, contact_id, type, value, "
                "is_primary, is_current, created_at, updated_at) "
                "VALUES ('ci-1', 'ct-1', 'email', 'a@wfco.com', 1, 1, ?, ?)",
                (_NOW, _NOW))
        r = client.post("/api/v1/companies/resolve-domains", json={})
        data = r.json()
        assert data["contacts_linked"] == 1
        assert data["details"][0]["company_name"] == "WF Co"

    def test_duplicates_report(self, client, tmp_db):
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO companies (id, customer_id, name, domain, status, "
                "created_at, updated_at) VALUES ('co-2', ?, 'WF Co Two', "
                "'www.wfco.com', 'active', ?, ?)", (CUST_ID, _NOW, _NOW))
        groups = client.get("/api/v1/companies/duplicates").json()["groups"]
        assert len(groups) == 1
        assert groups[0]["domain"] == "wfco.com"
        assert len(groups[0]["companies"]) == 2

    def test_check_and_link_domain_contacts(self, client, tmp_db):
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO contact_identifiers (id, contact_id, type, value, "
                "is_primary, is_current, created_at, updated_at) "
                "VALUES ('ci-2', 'ct-2', 'email', 'b@wfco.com', 1, 1, ?, ?)",
                (_NOW, _NOW))
        check = client.post("/api/v1/companies/check",
                            json={"domain": "wfco.com"}).json()
        assert len(check["existing_companies"]) == 1
        assert check["linkable_contacts"][0]["email"] == "b@wfco.com"
        r = client.post("/api/v1/companies/co-1/link-domain-contacts")
        assert r.json()["contacts_linked"] == 1

    def test_enrich_missing_company_404(self, client, tmp_db):
        assert client.post(
            "/api/v1/companies/nope/enrich").status_code == 404

    def test_enrich_invokes_pipeline(self, client, tmp_db, monkeypatch):
        import poc.enrichment_pipeline as ep
        monkeypatch.setattr(
            ep, "execute_enrichment",
            lambda *a, **kw: {"run_id": "run-1", "status": "completed",
                              "fields_discovered": 3, "fields_applied": 2})
        r = client.post("/api/v1/companies/co-1/enrich")
        assert r.json()["fields_applied"] == 2


class TestVcardImport:
    def test_import_from_path(self, client, tmp_db, tmp_path):
        vcf = tmp_path / "test.vcf"
        vcf.write_text(
            "BEGIN:VCARD\nVERSION:3.0\nFN:Imported Person\n"
            "EMAIL;TYPE=WORK:imported@newco.com\nORG:NewCo\nEND:VCARD\n")
        r = client.post("/api/v1/contacts/import-vcards",
                        json={"path": str(vcf)})
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["contacts_created"] == 1
        assert data["companies_created"] == 1
        assert data["imported_contacts"][0]["name"] == "Imported Person"
        # Re-import dedupes by email
        r = client.post("/api/v1/contacts/import-vcards",
                        json={"path": str(vcf)})
        assert r.json()["contacts_skipped_duplicate"] == 1

    def test_missing_path_errors(self, client, tmp_db):
        assert client.post("/api/v1/contacts/import-vcards",
                           json={"path": "/nope/missing.vcf"}).status_code == 400


class TestContactSyncEmail:
    def test_invalid_window_400(self, client, tmp_db):
        r = client.post("/api/v1/contacts/ct-1/sync-email",
                        json={"window": "5y"})
        assert r.status_code == 400

    def test_sync_invoked(self, client, tmp_db, monkeypatch):
        import poc.sync as sync_mod
        monkeypatch.setattr(
            sync_mod, "sync_contact_email",
            lambda *a, **kw: {"messages_fetched": 4, "messages_new": 4,
                              "conversations_created": 1,
                              "conversations_updated": 0})
        r = client.post("/api/v1/contacts/ct-1/sync-email",
                        json={"window": "90d"})
        assert r.json()["messages_fetched"] == 4
