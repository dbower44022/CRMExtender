"""Tests for relationship inference from conversation co-occurrence."""

import json
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from poc.database import init_db, get_connection, _db_path
from poc.models import Relationship
from poc.relationship_inference import (
    _compute_strength,
    _recency_factor,
    infer_relationships,
    load_relationships,
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


def _insert_account(conn, account_id="acct-1"):
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT OR IGNORE INTO email_accounts "
        "(id, provider, email_address, created_at, updated_at) "
        "VALUES (?, 'gmail', 'test@example.com', ?, ?)",
        (account_id, now, now),
    )


def _insert_contact(conn, contact_id, email, name=None):
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT OR IGNORE INTO contacts (id, email, name, source, created_at, updated_at) "
        "VALUES (?, ?, ?, 'test', ?, ?)",
        (contact_id, email.lower(), name or email, now, now),
    )


def _insert_conversation(conn, conv_id, account_id="acct-1"):
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT OR IGNORE INTO conversations "
        "(id, account_id, subject, created_at, updated_at) "
        "VALUES (?, ?, 'Test subject', ?, ?)",
        (conv_id, account_id, now, now),
    )


def _insert_participant(conn, conv_id, email, contact_id, message_count=1,
                        first_seen=None, last_seen=None):
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT OR IGNORE INTO conversation_participants "
        "(conversation_id, email_address, contact_id, message_count, "
        " first_seen_at, last_seen_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (conv_id, email, contact_id, message_count,
         first_seen or now, last_seen or now),
    )


def _seed_scenario(conn, num_contacts=3, num_conversations=3):
    """Seed contacts and conversations with overlapping participants.

    Creates contacts [c-0, c-1, c-2, ...] and conversations [conv-0, conv-1, ...].
    Each conversation includes contact c-i and c-((i+1) % num_contacts),
    so every adjacent pair co-occurs once.
    """
    _insert_account(conn)

    contacts = []
    for i in range(num_contacts):
        cid = f"c-{i}"
        email = f"person{i}@example.com"
        _insert_contact(conn, cid, email, f"Person {i}")
        contacts.append(cid)

    for i in range(num_conversations):
        conv_id = f"conv-{i}"
        _insert_conversation(conn, conv_id)

        c1 = contacts[i % num_contacts]
        c2 = contacts[(i + 1) % num_contacts]
        _insert_participant(conn, conv_id, f"person{i % num_contacts}@example.com", c1, 2)
        _insert_participant(conn, conv_id, f"person{(i + 1) % num_contacts}@example.com", c2, 3)


# ---------------------------------------------------------------------------
# _compute_strength tests
# ---------------------------------------------------------------------------

class TestComputeStrength:

    def test_zero_input(self):
        score = _compute_strength(0, 0, None)
        assert score == pytest.approx(0.03, abs=0.02)

    def test_maximum_input(self):
        recent = datetime.now(timezone.utc).isoformat()
        score = _compute_strength(50, 200, recent, max_conversations=50, max_messages=200)
        assert score == pytest.approx(1.0, abs=0.01)

    def test_moderate_input(self):
        recent = datetime.now(timezone.utc).isoformat()
        score = _compute_strength(5, 20, recent, max_conversations=50, max_messages=200)
        assert 0.2 < score < 0.8

    def test_old_interaction_lowers_score(self):
        old = (datetime.now(timezone.utc) - timedelta(days=400)).isoformat()
        recent = datetime.now(timezone.utc).isoformat()

        score_old = _compute_strength(5, 20, old)
        score_new = _compute_strength(5, 20, recent)
        assert score_new > score_old

    def test_strength_capped_at_one(self):
        recent = datetime.now(timezone.utc).isoformat()
        score = _compute_strength(10000, 10000, recent, max_conversations=2, max_messages=2)
        assert score <= 1.0


# ---------------------------------------------------------------------------
# _recency_factor tests
# ---------------------------------------------------------------------------

class TestRecencyFactor:

    def test_none_returns_minimum(self):
        assert _recency_factor(None) == 0.1

    def test_recent_returns_one(self):
        recent = datetime.now(timezone.utc).isoformat()
        assert _recency_factor(recent) == 1.0

    def test_very_old_returns_minimum(self):
        old = (datetime.now(timezone.utc) - timedelta(days=500)).isoformat()
        assert _recency_factor(old) == pytest.approx(0.1)

    def test_mid_range(self):
        mid = (datetime.now(timezone.utc) - timedelta(days=197)).isoformat()
        factor = _recency_factor(mid)
        assert 0.1 < factor < 1.0


# ---------------------------------------------------------------------------
# Relationship model round-trip
# ---------------------------------------------------------------------------

class TestRelationshipModel:

    def test_to_row_from_row_roundtrip(self):
        rel = Relationship(
            from_contact_id="c-1",
            to_contact_id="c-2",
            strength=0.75,
            shared_conversations=5,
            shared_messages=42,
            last_interaction="2026-02-01T10:00:00+00:00",
            first_interaction="2025-11-15T08:00:00+00:00",
        )

        row = rel.to_row(relationship_id="rel-123")
        assert row["id"] == "rel-123"
        assert row["from_entity_id"] == "c-1"
        assert row["to_entity_id"] == "c-2"
        assert row["relationship_type"] == "KNOWS"

        # Reconstruct
        rebuilt = Relationship.from_row(row)
        assert rebuilt.from_contact_id == "c-1"
        assert rebuilt.to_contact_id == "c-2"
        assert rebuilt.strength == 0.75
        assert rebuilt.shared_conversations == 5
        assert rebuilt.shared_messages == 42
        assert rebuilt.last_interaction == "2026-02-01T10:00:00+00:00"

    def test_defaults(self):
        rel = Relationship(from_contact_id="a", to_contact_id="b")
        assert rel.relationship_type == "KNOWS"
        assert rel.strength == 0.0
        assert rel.shared_conversations == 0


# ---------------------------------------------------------------------------
# infer_relationships integration tests
# ---------------------------------------------------------------------------

class TestInferRelationships:

    def test_basic_inference(self, tmp_db):
        with get_connection() as conn:
            _seed_scenario(conn, num_contacts=3, num_conversations=3)

        count = infer_relationships()
        assert count == 3  # 3 adjacent pairs: (c-0,c-1), (c-1,c-2), (c-0,c-2)

        rels = load_relationships()
        assert len(rels) == 3
        for rel in rels:
            assert rel.strength > 0
            assert rel.shared_conversations >= 1

    def test_no_data_returns_zero(self, tmp_db):
        count = infer_relationships()
        assert count == 0

    def test_upsert_is_idempotent(self, tmp_db):
        with get_connection() as conn:
            _seed_scenario(conn, num_contacts=2, num_conversations=2)

        count1 = infer_relationships()
        count2 = infer_relationships()
        assert count1 == count2

        # Should still only have one unique relationship
        rels = load_relationships()
        assert len(rels) == 1

    def test_filtered_by_contact(self, tmp_db):
        with get_connection() as conn:
            _seed_scenario(conn, num_contacts=4, num_conversations=4)

        infer_relationships()

        # Filter to c-0's relationships
        rels = load_relationships(contact_id="c-0")
        for rel in rels:
            assert "c-0" in (rel.from_contact_id, rel.to_contact_id)

    def test_min_strength_filter(self, tmp_db):
        with get_connection() as conn:
            _seed_scenario(conn, num_contacts=3, num_conversations=3)

        infer_relationships()

        all_rels = load_relationships()
        filtered = load_relationships(min_strength=0.99)
        assert len(filtered) <= len(all_rels)

    def test_null_contact_ids_excluded(self, tmp_db):
        """Participants without contact_id should not generate relationships."""
        with get_connection() as conn:
            _insert_account(conn)
            _insert_contact(conn, "c-1", "a@example.com")
            _insert_conversation(conn, "conv-1")
            _insert_participant(conn, "conv-1", "a@example.com", "c-1")
            # Participant with NULL contact_id
            conn.execute(
                "INSERT INTO conversation_participants "
                "(conversation_id, email_address, contact_id, message_count) "
                "VALUES ('conv-1', 'unknown@example.com', NULL, 1)",
            )

        count = infer_relationships()
        assert count == 0
