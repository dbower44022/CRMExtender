"""Tests for Contact Merge feature.

Covers: merge preview, merge execution (identifiers, affiliations,
social profiles, conversations, communications, relationships, events,
phones, addresses, emails, user_contacts, enrichment, scores, audit log),
web routes, identifier duplicate merge link, and edge cases.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from poc.database import get_connection, init_db


_NOW = datetime.now(timezone.utc).isoformat()

CUST_ID = "cust-test"
USER_ID = "user-admin"

_SYSTEM_ROLES = [
    ("ccr-employee", "Employee", 0),
    ("ccr-contractor", "Contractor", 1),
    ("ccr-volunteer", "Volunteer", 2),
    ("ccr-advisor", "Advisor", 3),
    ("ccr-board-member", "Board Member", 4),
    ("ccr-investor", "Investor", 5),
    ("ccr-founder", "Founder", 6),
    ("ccr-intern", "Intern", 7),
]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def tmp_db(tmp_path, monkeypatch):
    db_file = tmp_path / "test.db"
    monkeypatch.setattr("poc.config.DB_PATH", db_file)
    monkeypatch.setattr("poc.config.CRM_AUTH_ENABLED", False)
    init_db(db_file)

    with get_connection() as conn:
        conn.execute(
            "INSERT INTO customers (id, name, slug, is_active, created_at, updated_at) "
            "VALUES (?, 'Test Org', 'test', 1, ?, ?)",
            (CUST_ID, _NOW, _NOW),
        )
        conn.execute(
            "INSERT INTO users "
            "(id, customer_id, email, name, role, is_active, created_at, updated_at) "
            "VALUES (?, ?, 'admin@test.com', 'Admin User', 'admin', 1, ?, ?)",
            (USER_ID, CUST_ID, _NOW, _NOW),
        )
        for role_id, role_name, sort_order in _SYSTEM_ROLES:
            full_id = f"{role_id}-{CUST_ID}"
            conn.execute(
                "INSERT OR IGNORE INTO contact_company_roles "
                "(id, customer_id, name, sort_order, is_system, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, 1, ?, ?)",
                (full_id, CUST_ID, role_name, sort_order, _NOW, _NOW),
            )

    return db_file


@pytest.fixture()
def client(tmp_db, monkeypatch):
    monkeypatch.setattr(
        "poc.hierarchy.get_current_user",
        lambda: {"id": USER_ID, "email": "admin@test.com", "name": "Admin User",
                 "role": "admin", "customer_id": CUST_ID},
    )
    from poc.web.app import create_app
    app = create_app()
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _uid():
    return str(uuid.uuid4())


def _create_contact(name="Alice", source="test", customer_id=CUST_ID):
    cid = _uid()
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO contacts "
            "(id, customer_id, name, source, status, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, 'active', ?, ?)",
            (cid, customer_id, name, source, _NOW, _NOW),
        )
        conn.execute(
            "INSERT INTO user_contacts "
            "(id, user_id, contact_id, visibility, is_owner, created_at, updated_at) "
            "VALUES (?, ?, ?, 'public', 1, ?, ?)",
            (_uid(), USER_ID, cid, _NOW, _NOW),
        )
    return cid


def _add_identifier(contact_id, type="email", value="a@b.com"):
    iid = _uid()
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO contact_identifiers "
            "(id, contact_id, type, value, is_primary, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, 1, ?, ?)",
            (iid, contact_id, type, value, _NOW, _NOW),
        )
    return iid


def _create_company(name="Acme Corp"):
    co_id = _uid()
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO companies "
            "(id, customer_id, name, domain, status, created_at, updated_at) "
            "VALUES (?, ?, ?, 'acme.com', 'active', ?, ?)",
            (co_id, CUST_ID, name, _NOW, _NOW),
        )
    return co_id


def _add_affiliation(contact_id, company_id, role_id=None):
    aid = _uid()
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO contact_companies "
            "(id, contact_id, company_id, role_id, is_primary, is_current, source, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, 1, 1, 'test', ?, ?)",
            (aid, contact_id, company_id, role_id, _NOW, _NOW),
        )
    return aid


def _add_social_profile(contact_id, platform="linkedin", url="https://linkedin.com/in/test"):
    sid = _uid()
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO contact_social_profiles "
            "(id, contact_id, platform, profile_url, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (sid, contact_id, platform, url, _NOW, _NOW),
        )
    return sid


def _create_conversation(title="Test Conv"):
    conv_id = _uid()
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO conversations "
            "(id, customer_id, title, status, created_at, updated_at, last_activity_at) "
            "VALUES (?, ?, ?, 'active', ?, ?, ?)",
            (conv_id, CUST_ID, title, _NOW, _NOW, _NOW),
        )
    return conv_id


def _add_conversation_participant(conv_id, contact_id, address="a@b.com"):
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO conversation_participants "
            "(conversation_id, email_address, address, contact_id, communication_count, first_seen_at, last_seen_at) "
            "VALUES (?, ?, ?, ?, 1, ?, ?)",
            (conv_id, address, address, contact_id, _NOW, _NOW),
        )


def _create_communication(channel="email"):
    comm_id = _uid()
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO communications "
            "(id, channel, direction, timestamp, created_at, updated_at) "
            "VALUES (?, ?, 'inbound', ?, ?, ?)",
            (comm_id, channel, _NOW, _NOW, _NOW),
        )
    return comm_id


def _add_communication_participant(comm_id, contact_id, address="a@b.com", role="from"):
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO communication_participants "
            "(communication_id, address, contact_id, role) "
            "VALUES (?, ?, ?, ?)",
            (comm_id, address, contact_id, role),
        )


def _create_event(title="Test Event"):
    eid = _uid()
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO events "
            "(id, title, event_type, start_datetime, created_at, updated_at) "
            "VALUES (?, ?, 'meeting', ?, ?, ?)",
            (eid, title, _NOW, _NOW, _NOW),
        )
    return eid


def _add_event_participant(event_id, contact_id):
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO event_participants "
            "(event_id, entity_type, entity_id, role) "
            "VALUES (?, 'contact', ?, 'attendee')",
            (event_id, contact_id),
        )


def _add_phone(contact_id, number="+12025551234"):
    pid = _uid()
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO phone_numbers "
            "(id, entity_type, entity_id, number, phone_type, created_at, updated_at) "
            "VALUES (?, 'contact', ?, ?, 'mobile', ?, ?)",
            (pid, contact_id, number, _NOW, _NOW),
        )
    return pid


def _add_address(contact_id, city="NYC"):
    aid = _uid()
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO addresses "
            "(id, entity_type, entity_id, address_type, city, created_at, updated_at) "
            "VALUES (?, 'contact', ?, 'work', ?, ?, ?)",
            (aid, contact_id, city, _NOW, _NOW),
        )
    return aid


def _add_email_address(contact_id, address="test@acme.com"):
    eid = _uid()
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO email_addresses "
            "(id, entity_type, entity_id, address, email_type, created_at, updated_at) "
            "VALUES (?, 'contact', ?, ?, 'general', ?, ?)",
            (eid, contact_id, address, _NOW, _NOW),
        )
    return eid


def _add_relationship(from_id, to_id, type_id="rt-knows"):
    rid = _uid()
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO relationships "
            "(id, relationship_type_id, from_entity_type, from_entity_id, "
            "to_entity_type, to_entity_id, source, created_at, updated_at) "
            "VALUES (?, ?, 'contact', ?, 'contact', ?, 'test', ?, ?)",
            (rid, type_id, from_id, to_id, _NOW, _NOW),
        )
    return rid


# ======================================================================
# Merge Preview
# ======================================================================

class TestContactMergePreview:

    def test_basic_preview(self, tmp_db):
        from poc.contact_merge import get_contact_merge_preview
        c1 = _create_contact("Alice", source="gmail")
        c2 = _create_contact("Bob", source="outlook")
        _add_identifier(c1, "email", "alice@test.com")
        _add_identifier(c2, "email", "bob@test.com")

        preview = get_contact_merge_preview([c1, c2])
        assert len(preview["contacts"]) == 2
        assert preview["contacts"][0]["name"] == "Alice"
        assert preview["contacts"][1]["name"] == "Bob"
        assert preview["totals"]["identifiers"] == 2
        assert preview["totals"]["combined_identifiers"] == 2

    def test_preview_dedup_identifiers(self, tmp_db):
        """When contacts share the same identifier type+value, combined count reflects dedup."""
        from poc.contact_merge import get_contact_merge_preview
        c1 = _create_contact("Alice")
        c2 = _create_contact("Bob")
        # Same type, different value — no dedup
        _add_identifier(c1, "email", "alice@test.com")
        _add_identifier(c2, "email", "bob@test.com")
        # Both have a phone identifier with different values
        _add_identifier(c1, "phone", "+1111")
        _add_identifier(c2, "phone", "+2222")

        preview = get_contact_merge_preview([c1, c2])
        assert preview["totals"]["identifiers"] == 4
        assert preview["totals"]["combined_identifiers"] == 4

    def test_preview_conflicts(self, tmp_db):
        from poc.contact_merge import get_contact_merge_preview
        c1 = _create_contact("Alice", source="gmail")
        c2 = _create_contact("Bob", source="outlook")

        preview = get_contact_merge_preview([c1, c2])
        assert set(preview["conflicts"]["name"]) == {"Alice", "Bob"}
        assert set(preview["conflicts"]["source"]) == {"gmail", "outlook"}

    def test_preview_no_conflict_same_name(self, tmp_db):
        from poc.contact_merge import get_contact_merge_preview
        c1 = _create_contact("Alice", source="gmail")
        c2 = _create_contact("Alice", source="gmail")

        preview = get_contact_merge_preview([c1, c2])
        assert preview["conflicts"]["name"] == ["Alice"]
        assert preview["conflicts"]["source"] == ["gmail"]

    def test_preview_counts(self, tmp_db):
        from poc.contact_merge import get_contact_merge_preview
        c1 = _create_contact("Alice")
        c2 = _create_contact("Bob")
        co = _create_company()
        _add_affiliation(c2, co)
        ev = _create_event()
        _add_event_participant(ev, c2)

        preview = get_contact_merge_preview([c1, c2])
        assert preview["contacts"][1]["affiliation_count"] == 1
        assert preview["contacts"][1]["event_count"] == 1
        assert preview["totals"]["affiliations"] == 1
        assert preview["totals"]["events"] == 1

    def test_preview_too_few_contacts(self, tmp_db):
        from poc.contact_merge import get_contact_merge_preview
        c1 = _create_contact()
        with pytest.raises(ValueError, match="At least two"):
            get_contact_merge_preview([c1])

    def test_preview_nonexistent(self, tmp_db):
        from poc.contact_merge import get_contact_merge_preview
        c1 = _create_contact()
        with pytest.raises(ValueError, match="not found"):
            get_contact_merge_preview([c1, "nonexistent-id"])

    def test_preview_three_contacts(self, tmp_db):
        from poc.contact_merge import get_contact_merge_preview
        c1 = _create_contact("A")
        c2 = _create_contact("B")
        c3 = _create_contact("C")
        _add_identifier(c1, "email", "a@test.com")
        _add_identifier(c2, "email", "b@test.com")
        _add_identifier(c3, "email", "c@test.com")

        preview = get_contact_merge_preview([c1, c2, c3])
        assert len(preview["contacts"]) == 3
        assert preview["totals"]["identifiers"] == 3


# ======================================================================
# Merge Execution
# ======================================================================

class TestContactMergeExecution:

    def test_basic_merge(self, tmp_db):
        from poc.contact_merge import merge_contacts
        c1 = _create_contact("Alice")
        c2 = _create_contact("Bob")

        result = merge_contacts(c1, [c2], merged_by=USER_ID)
        assert result["surviving_id"] == c1
        assert c2 in result["absorbed_ids"]

        with get_connection() as conn:
            assert conn.execute("SELECT * FROM contacts WHERE id = ?", (c2,)).fetchone() is None
            assert conn.execute("SELECT * FROM contacts WHERE id = ?", (c1,)).fetchone() is not None

    def test_identifiers_transferred(self, tmp_db):
        from poc.contact_merge import merge_contacts
        c1 = _create_contact("Alice")
        c2 = _create_contact("Bob")
        _add_identifier(c1, "email", "alice@test.com")
        _add_identifier(c2, "email", "bob@test.com")

        result = merge_contacts(c1, [c2])
        assert result["identifiers_transferred"] == 1

        with get_connection() as conn:
            ids = conn.execute(
                "SELECT * FROM contact_identifiers WHERE contact_id = ?", (c1,)
            ).fetchall()
            values = {r["value"] for r in ids}
            assert "alice@test.com" in values
            assert "bob@test.com" in values

    def test_identifiers_all_transferred(self, tmp_db):
        """Both contacts have different identifiers — all transfer to surviving."""
        from poc.contact_merge import merge_contacts
        c1 = _create_contact("Alice")
        c2 = _create_contact("Bob")
        _add_identifier(c1, "email", "alice@test.com")
        _add_identifier(c2, "phone", "+15551234567")

        result = merge_contacts(c1, [c2])
        assert result["identifiers_transferred"] == 1

        with get_connection() as conn:
            ids = conn.execute(
                "SELECT * FROM contact_identifiers WHERE contact_id = ?", (c1,)
            ).fetchall()
            assert len(ids) == 2

    def test_affiliations_transferred(self, tmp_db):
        from poc.contact_merge import merge_contacts
        c1 = _create_contact("Alice")
        c2 = _create_contact("Bob")
        co = _create_company("Acme")
        _add_affiliation(c2, co)

        result = merge_contacts(c1, [c2])
        assert result["affiliations_transferred"] == 1

        with get_connection() as conn:
            affs = conn.execute(
                "SELECT * FROM contact_companies WHERE contact_id = ?", (c1,)
            ).fetchall()
            assert len(affs) == 1
            assert affs[0]["company_id"] == co

    def test_affiliations_deduplicated(self, tmp_db):
        from poc.contact_merge import merge_contacts
        c1 = _create_contact("Alice")
        c2 = _create_contact("Bob")
        co = _create_company("Acme")
        role_id = f"ccr-employee-{CUST_ID}"
        _add_affiliation(c1, co, role_id=role_id)
        _add_affiliation(c2, co, role_id=role_id)

        result = merge_contacts(c1, [c2])
        assert result["affiliations_transferred"] == 0

        with get_connection() as conn:
            affs = conn.execute(
                "SELECT * FROM contact_companies WHERE contact_id = ?", (c1,)
            ).fetchall()
            assert len(affs) == 1

    def test_social_profiles_transferred(self, tmp_db):
        from poc.contact_merge import merge_contacts
        c1 = _create_contact("Alice")
        c2 = _create_contact("Bob")
        _add_social_profile(c2, "linkedin", "https://linkedin.com/in/bob")

        merge_contacts(c1, [c2])

        with get_connection() as conn:
            profiles = conn.execute(
                "SELECT * FROM contact_social_profiles WHERE contact_id = ?", (c1,)
            ).fetchall()
            assert len(profiles) == 1
            assert profiles[0]["profile_url"] == "https://linkedin.com/in/bob"

    def test_social_profiles_deduplicated(self, tmp_db):
        from poc.contact_merge import merge_contacts
        c1 = _create_contact("Alice")
        c2 = _create_contact("Bob")
        url = "https://linkedin.com/in/same"
        _add_social_profile(c1, "linkedin", url)
        _add_social_profile(c2, "linkedin", url)

        merge_contacts(c1, [c2])

        with get_connection() as conn:
            profiles = conn.execute(
                "SELECT * FROM contact_social_profiles WHERE contact_id = ?", (c1,)
            ).fetchall()
            assert len(profiles) == 1

    def test_conversations_reassigned(self, tmp_db):
        from poc.contact_merge import merge_contacts
        c1 = _create_contact("Alice")
        c2 = _create_contact("Bob")
        conv = _create_conversation()
        _add_conversation_participant(conv, c2, "bob@test.com")

        result = merge_contacts(c1, [c2])
        assert result["conversations_reassigned"] == 1

        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM conversation_participants WHERE conversation_id = ? AND contact_id = ?",
                (conv, c1),
            ).fetchone()
            assert row is not None

    def test_conversations_deduplicated(self, tmp_db):
        from poc.contact_merge import merge_contacts
        c1 = _create_contact("Alice")
        c2 = _create_contact("Bob")
        conv = _create_conversation()
        _add_conversation_participant(conv, c1, "alice@test.com")
        _add_conversation_participant(conv, c2, "bob@test.com")

        result = merge_contacts(c1, [c2])

        with get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM conversation_participants WHERE conversation_id = ? AND contact_id = ?",
                (conv, c1),
            ).fetchall()
            assert len(rows) == 1

    def test_communications_reassigned(self, tmp_db):
        from poc.contact_merge import merge_contacts
        c1 = _create_contact("Alice")
        c2 = _create_contact("Bob")
        comm = _create_communication()
        _add_communication_participant(comm, c2, "bob@test.com", "from")

        merge_contacts(c1, [c2])

        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM communication_participants WHERE communication_id = ? AND contact_id = ?",
                (comm, c1),
            ).fetchone()
            assert row is not None

    def test_relationships_reassigned(self, tmp_db):
        from poc.contact_merge import merge_contacts
        c1 = _create_contact("Alice")
        c2 = _create_contact("Bob")
        c3 = _create_contact("Charlie")
        _add_relationship(c2, c3)

        result = merge_contacts(c1, [c2])
        assert result["relationships_reassigned"] >= 1

        with get_connection() as conn:
            rels = conn.execute(
                "SELECT * FROM relationships WHERE from_entity_id = ? AND to_entity_id = ?",
                (c1, c3),
            ).fetchall()
            assert len(rels) == 1

    def test_relationships_self_referential_deleted(self, tmp_db):
        from poc.contact_merge import merge_contacts
        c1 = _create_contact("Alice")
        c2 = _create_contact("Bob")
        _add_relationship(c1, c2)

        result = merge_contacts(c1, [c2])
        assert result["relationships_deduplicated"] >= 1

        with get_connection() as conn:
            self_rels = conn.execute(
                "SELECT * FROM relationships WHERE from_entity_id = ? AND to_entity_id = ?",
                (c1, c1),
            ).fetchall()
            assert len(self_rels) == 0

    def test_events_reassigned(self, tmp_db):
        from poc.contact_merge import merge_contacts
        c1 = _create_contact("Alice")
        c2 = _create_contact("Bob")
        ev = _create_event()
        _add_event_participant(ev, c2)

        result = merge_contacts(c1, [c2])
        assert result["events_reassigned"] == 1

        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM event_participants WHERE event_id = ? AND entity_id = ?",
                (ev, c1),
            ).fetchone()
            assert row is not None

    def test_events_deduplicated(self, tmp_db):
        from poc.contact_merge import merge_contacts
        c1 = _create_contact("Alice")
        c2 = _create_contact("Bob")
        ev = _create_event()
        _add_event_participant(ev, c1)
        _add_event_participant(ev, c2)

        merge_contacts(c1, [c2])

        with get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM event_participants WHERE event_id = ? AND entity_type = 'contact' AND entity_id = ?",
                (ev, c1),
            ).fetchall()
            assert len(rows) == 1

    def test_phones_transferred(self, tmp_db):
        from poc.contact_merge import merge_contacts
        c1 = _create_contact("Alice")
        c2 = _create_contact("Bob")
        _add_phone(c2, "+15551234567")

        merge_contacts(c1, [c2])

        with get_connection() as conn:
            phones = conn.execute(
                "SELECT * FROM phone_numbers WHERE entity_type='contact' AND entity_id=?",
                (c1,),
            ).fetchall()
            assert len(phones) == 1

    def test_phones_deduplicated(self, tmp_db):
        from poc.contact_merge import merge_contacts
        c1 = _create_contact("Alice")
        c2 = _create_contact("Bob")
        _add_phone(c1, "+15551234567")
        _add_phone(c2, "+15551234567")

        merge_contacts(c1, [c2])

        with get_connection() as conn:
            phones = conn.execute(
                "SELECT * FROM phone_numbers WHERE entity_type='contact' AND entity_id=?",
                (c1,),
            ).fetchall()
            assert len(phones) == 1

    def test_addresses_transferred(self, tmp_db):
        from poc.contact_merge import merge_contacts
        c1 = _create_contact("Alice")
        c2 = _create_contact("Bob")
        _add_address(c2, "Boston")

        merge_contacts(c1, [c2])

        with get_connection() as conn:
            addrs = conn.execute(
                "SELECT * FROM addresses WHERE entity_type='contact' AND entity_id=?",
                (c1,),
            ).fetchall()
            assert len(addrs) == 1
            assert addrs[0]["city"] == "Boston"

    def test_email_addresses_transferred(self, tmp_db):
        from poc.contact_merge import merge_contacts
        c1 = _create_contact("Alice")
        c2 = _create_contact("Bob")
        _add_email_address(c2, "bob@acme.com")

        merge_contacts(c1, [c2])

        with get_connection() as conn:
            emails = conn.execute(
                "SELECT * FROM email_addresses WHERE entity_type='contact' AND entity_id=?",
                (c1,),
            ).fetchall()
            assert len(emails) == 1

    def test_user_contacts_transferred(self, tmp_db):
        from poc.contact_merge import merge_contacts
        c1 = _create_contact("Alice")
        c2 = _create_contact("Bob")

        # Create a second user with visibility to c2 only
        user2 = _uid()
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO users "
                "(id, customer_id, email, name, role, is_active, created_at, updated_at) "
                "VALUES (?, ?, 'user2@test.com', 'User Two', 'user', 1, ?, ?)",
                (user2, CUST_ID, _NOW, _NOW),
            )
            conn.execute(
                "INSERT INTO user_contacts "
                "(id, user_id, contact_id, visibility, is_owner, created_at, updated_at) "
                "VALUES (?, ?, ?, 'public', 0, ?, ?)",
                (_uid(), user2, c2, _NOW, _NOW),
            )

        merge_contacts(c1, [c2])

        with get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM user_contacts WHERE contact_id = ? AND user_id = ?",
                (c1, user2),
            ).fetchall()
            assert len(rows) == 1

    def test_entity_scores_deleted(self, tmp_db):
        from poc.contact_merge import merge_contacts
        c1 = _create_contact("Alice")
        c2 = _create_contact("Bob")
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO entity_scores "
                "(id, entity_type, entity_id, score_type, score_value, computed_at) "
                "VALUES (?, 'contact', ?, 'relationship_strength', 0.5, ?)",
                (_uid(), c2, _NOW),
            )

        merge_contacts(c1, [c2])

        with get_connection() as conn:
            scores = conn.execute(
                "SELECT * FROM entity_scores WHERE entity_type='contact' AND entity_id=?",
                (c2,),
            ).fetchall()
            assert len(scores) == 0

    def test_audit_log(self, tmp_db):
        from poc.contact_merge import merge_contacts
        c1 = _create_contact("Alice")
        c2 = _create_contact("Bob")

        result = merge_contacts(c1, [c2], merged_by=USER_ID)

        with get_connection() as conn:
            audit = conn.execute(
                "SELECT * FROM contact_merges WHERE id = ?", (result["merge_ids"][0],)
            ).fetchone()
            assert audit is not None
            assert audit["surviving_contact_id"] == c1
            assert audit["absorbed_contact_id"] == c2
            assert audit["merged_by"] == USER_ID
            snapshot = json.loads(audit["absorbed_contact_snapshot"])
            assert snapshot["name"] == "Bob"

    def test_chosen_name_applied(self, tmp_db):
        from poc.contact_merge import merge_contacts
        c1 = _create_contact("Alice")
        c2 = _create_contact("Bob")

        merge_contacts(c1, [c2], chosen_name="Bob")

        with get_connection() as conn:
            row = conn.execute("SELECT * FROM contacts WHERE id = ?", (c1,)).fetchone()
            assert row["name"] == "Bob"

    def test_chosen_source_applied(self, tmp_db):
        from poc.contact_merge import merge_contacts
        c1 = _create_contact("Alice", source="gmail")
        c2 = _create_contact("Bob", source="outlook")

        merge_contacts(c1, [c2], chosen_source="outlook")

        with get_connection() as conn:
            row = conn.execute("SELECT * FROM contacts WHERE id = ?", (c1,)).fetchone()
            assert row["source"] == "outlook"

    def test_self_merge_raises(self, tmp_db):
        from poc.contact_merge import merge_contacts
        c1 = _create_contact("Alice")
        with pytest.raises(ValueError, match="itself"):
            merge_contacts(c1, [c1])

    def test_nonexistent_surviving_raises(self, tmp_db):
        from poc.contact_merge import merge_contacts
        c2 = _create_contact("Bob")
        with pytest.raises(ValueError, match="not found"):
            merge_contacts("fake-id", [c2])

    def test_nonexistent_absorbed_raises(self, tmp_db):
        from poc.contact_merge import merge_contacts
        c1 = _create_contact("Alice")
        with pytest.raises(ValueError, match="not found"):
            merge_contacts(c1, ["fake-id"])

    def test_multi_contact_merge(self, tmp_db):
        from poc.contact_merge import merge_contacts
        c1 = _create_contact("Alice")
        c2 = _create_contact("Bob")
        c3 = _create_contact("Charlie")
        _add_identifier(c1, "email", "a@test.com")
        _add_identifier(c2, "email", "b@test.com")
        _add_identifier(c3, "email", "c@test.com")

        result = merge_contacts(c1, [c2, c3], merged_by=USER_ID)
        assert len(result["merge_ids"]) == 2
        assert result["identifiers_transferred"] == 2

        with get_connection() as conn:
            ids = conn.execute(
                "SELECT * FROM contact_identifiers WHERE contact_id = ?", (c1,)
            ).fetchall()
            assert len(ids) == 3

    def test_enrichment_runs_transferred(self, tmp_db):
        from poc.contact_merge import merge_contacts
        c1 = _create_contact("Alice")
        c2 = _create_contact("Bob")
        er_id = _uid()
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO enrichment_runs "
                "(id, entity_type, entity_id, provider, status, created_at) "
                "VALUES (?, 'contact', ?, 'test_provider', 'completed', ?)",
                (er_id, c2, _NOW),
            )

        merge_contacts(c1, [c2])

        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM enrichment_runs WHERE id = ?", (er_id,)
            ).fetchone()
            assert row["entity_id"] == c1

    def test_prior_merge_audit_repointed(self, tmp_db):
        from poc.contact_merge import merge_contacts
        c1 = _create_contact("Alice")
        c2 = _create_contact("Bob")
        c3 = _create_contact("Charlie")

        # First merge c3 into c2
        result1 = merge_contacts(c2, [c3], merged_by=USER_ID)
        # Now merge c2 into c1 — should re-point audit record
        result2 = merge_contacts(c1, [c2], merged_by=USER_ID)

        with get_connection() as conn:
            audit = conn.execute(
                "SELECT * FROM contact_merges WHERE id = ?", (result1["merge_ids"][0],)
            ).fetchone()
            assert audit["surviving_contact_id"] == c1


# ======================================================================
# Web Routes
# ======================================================================

class TestContactMergeWebRoutes:

    def test_merge_page_loads(self, client, tmp_db):
        c1 = _create_contact("Alice")
        c2 = _create_contact("Bob")
        resp = client.get(f"/contacts/merge?ids={c1}&ids={c2}")
        assert resp.status_code == 200
        assert "Alice" in resp.text
        assert "Bob" in resp.text
        assert "Confirm Merge" in resp.text

    def test_merge_page_too_few_redirects(self, client, tmp_db):
        c1 = _create_contact("Alice")
        resp = client.get(f"/contacts/merge?ids={c1}", follow_redirects=False)
        assert resp.status_code == 303

    def test_merge_page_no_ids_redirects(self, client, tmp_db):
        resp = client.get("/contacts/merge", follow_redirects=False)
        assert resp.status_code == 303

    def test_merge_confirm(self, client, tmp_db):
        c1 = _create_contact("Alice")
        c2 = _create_contact("Bob")
        _add_identifier(c1, "email", "alice@test.com")
        _add_identifier(c2, "email", "bob@test.com")

        resp = client.post("/contacts/merge/confirm", data={
            "surviving_id": c1,
            "contact_ids": [c1, c2],
            "chosen_name": "Alice",
        }, follow_redirects=False)
        assert resp.status_code == 303
        assert c1 in str(resp.headers.get("location", ""))

        with get_connection() as conn:
            assert conn.execute("SELECT * FROM contacts WHERE id = ?", (c2,)).fetchone() is None

    def test_merge_confirm_with_name_choice(self, client, tmp_db):
        c1 = _create_contact("Alice")
        c2 = _create_contact("Bob")

        client.post("/contacts/merge/confirm", data={
            "surviving_id": c1,
            "contact_ids": [c1, c2],
            "chosen_name": "Bob",
        }, follow_redirects=False)

        with get_connection() as conn:
            row = conn.execute("SELECT * FROM contacts WHERE id = ?", (c1,)).fetchone()
            assert row["name"] == "Bob"

    def test_merge_three_contacts(self, client, tmp_db):
        c1 = _create_contact("Alice")
        c2 = _create_contact("Bob")
        c3 = _create_contact("Charlie")

        resp = client.get(f"/contacts/merge?ids={c1}&ids={c2}&ids={c3}")
        assert resp.status_code == 200
        assert "Charlie" in resp.text

        resp = client.post("/contacts/merge/confirm", data={
            "surviving_id": c1,
            "contact_ids": [c1, c2, c3],
        }, follow_redirects=False)
        assert resp.status_code == 303

        with get_connection() as conn:
            assert conn.execute("SELECT * FROM contacts WHERE id = ?", (c2,)).fetchone() is None
            assert conn.execute("SELECT * FROM contacts WHERE id = ?", (c3,)).fetchone() is None
            assert conn.execute("SELECT * FROM contacts WHERE id = ?", (c1,)).fetchone() is not None

    def test_identifier_duplicate_shows_merge_link(self, client, tmp_db):
        c1 = _create_contact("Alice")
        c2 = _create_contact("Bob")
        _add_identifier(c2, "email", "shared@test.com")

        resp = client.post(f"/contacts/{c1}/identifiers", data={
            "type": "email",
            "value": "shared@test.com",
        })
        assert resp.status_code == 200
        assert "Merge these contacts?" in resp.text
        assert f"/contacts/merge?ids={c1}" in resp.text

    def test_contacts_list_has_checkboxes(self, client, tmp_db):
        _create_contact("Alice")
        resp = client.get("/contacts")
        assert resp.status_code == 200
        assert 'class="contact-check"' in resp.text
        assert 'id="select-all"' in resp.text
        assert "contact_merge.js" in resp.text

    def test_contacts_list_has_merge_toolbar(self, client, tmp_db):
        resp = client.get("/contacts")
        assert resp.status_code == 200
        assert 'id="merge-toolbar"' in resp.text
        assert "Merge Selected" in resp.text


# ======================================================================
# Edge Cases
# ======================================================================

class TestContactMergeEdgeCases:

    def test_merge_with_no_sub_entities(self, tmp_db):
        from poc.contact_merge import merge_contacts
        c1 = _create_contact("Alice")
        c2 = _create_contact("Bob")

        result = merge_contacts(c1, [c2])
        assert result["identifiers_transferred"] == 0
        assert result["affiliations_transferred"] == 0
        assert result["conversations_reassigned"] == 0
        assert result["relationships_reassigned"] == 0
        assert result["events_reassigned"] == 0

    def test_merge_preserves_surviving_identifiers(self, tmp_db):
        from poc.contact_merge import merge_contacts
        c1 = _create_contact("Alice")
        c2 = _create_contact("Bob")
        _add_identifier(c1, "email", "alice@test.com")

        merge_contacts(c1, [c2])

        with get_connection() as conn:
            ids = conn.execute(
                "SELECT * FROM contact_identifiers WHERE contact_id = ?", (c1,)
            ).fetchall()
            assert len(ids) == 1
            assert ids[0]["value"] == "alice@test.com"
            assert ids[0]["is_primary"] == 1

    def test_merge_transferred_identifiers_not_primary(self, tmp_db):
        from poc.contact_merge import merge_contacts
        c1 = _create_contact("Alice")
        c2 = _create_contact("Bob")
        _add_identifier(c1, "email", "alice@test.com")
        _add_identifier(c2, "email", "bob@test.com")

        merge_contacts(c1, [c2])

        with get_connection() as conn:
            transferred = conn.execute(
                "SELECT * FROM contact_identifiers WHERE contact_id = ? AND value = 'bob@test.com'",
                (c1,),
            ).fetchone()
            assert transferred["is_primary"] == 0

    def test_empty_absorbed_list_raises(self, tmp_db):
        from poc.contact_merge import merge_contacts
        c1 = _create_contact("Alice")
        with pytest.raises(ValueError, match="At least one"):
            merge_contacts(c1, [])

    def test_post_merge_creates_affiliations_from_email_domains(self, tmp_db):
        """After merge, email domains on the surviving contact resolve to companies."""
        from poc.contact_merge import merge_contacts
        c1 = _create_contact("Alice")
        c2 = _create_contact("Alice")
        _add_identifier(c1, "email", "alice@acme.com")
        _add_identifier(c2, "email", "alice@bigco.com")

        # Create two companies with matching domains
        acme_id = _create_company("Acme Corp")
        bigco_id = _uid()
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO companies "
                "(id, customer_id, name, domain, status, created_at, updated_at) "
                "VALUES (?, ?, 'BigCo Inc', 'bigco.com', 'active', ?, ?)",
                (bigco_id, CUST_ID, _NOW, _NOW),
            )

        # c1 already has an affiliation to Acme
        _add_affiliation(c1, acme_id)

        result = merge_contacts(c1, [c2])
        # BigCo affiliation should be auto-created after merge
        assert result["affiliations_created"] == 1

        with get_connection() as conn:
            affs = conn.execute(
                "SELECT cc.*, co.name AS co_name FROM contact_companies cc "
                "JOIN companies co ON co.id = cc.company_id "
                "WHERE cc.contact_id = ?",
                (c1,),
            ).fetchall()
            company_names = {a["co_name"] for a in affs}
            assert "Acme Corp" in company_names
            assert "BigCo Inc" in company_names

    def test_post_merge_skips_existing_affiliations(self, tmp_db):
        """Post-merge domain resolution doesn't duplicate existing affiliations."""
        from poc.contact_merge import merge_contacts
        c1 = _create_contact("Alice")
        c2 = _create_contact("Alice")
        _add_identifier(c1, "email", "alice@acme.com")
        _add_identifier(c2, "email", "alice2@acme.com")

        acme_id = _create_company("Acme Corp")
        _add_affiliation(c1, acme_id)

        # Both emails resolve to Acme — should not create a duplicate
        result = merge_contacts(c1, [c2])
        assert result["affiliations_created"] == 0

    def test_post_merge_skips_public_domains(self, tmp_db):
        """Post-merge domain resolution ignores gmail.com etc."""
        from poc.contact_merge import merge_contacts
        c1 = _create_contact("Alice")
        c2 = _create_contact("Alice")
        _add_identifier(c1, "email", "alice@gmail.com")
        _add_identifier(c2, "email", "alice2@yahoo.com")

        result = merge_contacts(c1, [c2])
        assert result["affiliations_created"] == 0
