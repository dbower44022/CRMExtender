"""Tests for relationship strength scoring module."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from poc.database import get_connection, init_db
from poc.scoring import (
    DEFAULT_WEIGHTS,
    DURATION_CAP_DAYS,
    FREQUENCY_CAP,
    FREQUENCY_WINDOW_DAYS,
    RECENCY_WINDOW_DAYS,
    SCORE_TYPE,
    _breadth_score,
    _duration_score,
    _frequency_score,
    _recency_score,
    _reciprocity_score,
    compute_company_score,
    compute_contact_score,
    get_entity_score,
    score_all_companies,
    score_all_contacts,
    upsert_entity_score,
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _days_ago(n: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=n)).isoformat()


def _uid() -> str:
    return str(uuid.uuid4())


@pytest.fixture()
def tmp_db(tmp_path, monkeypatch):
    """Create a temporary database and point config at it."""
    db_file = tmp_path / "test.db"
    monkeypatch.setattr("poc.config.DB_PATH", db_file)
    init_db(db_file)
    return db_file


# ---------------------------------------------------------------------------
# Helper functions to seed test data
# ---------------------------------------------------------------------------

def _insert_company(conn, name="Acme Corp", domain="acme.com") -> str:
    cid = _uid()
    now = _now_iso()
    conn.execute(
        """INSERT INTO companies (id, name, domain, status, created_at, updated_at)
           VALUES (?, ?, ?, 'active', ?, ?)""",
        (cid, name, domain, now, now),
    )
    return cid


def _insert_contact(conn, name="Alice", email="alice@acme.com") -> str:
    cid = _uid()
    iid = _uid()
    now = _now_iso()
    conn.execute(
        """INSERT INTO contacts (id, name, status, created_at, updated_at)
           VALUES (?, ?, 'active', ?, ?)""",
        (cid, name, now, now),
    )
    conn.execute(
        """INSERT INTO contact_identifiers (id, contact_id, type, value, created_at, updated_at)
           VALUES (?, ?, 'email', ?, ?, ?)""",
        (iid, cid, email, now, now),
    )
    return cid


def _link_contact_to_company(conn, contact_id, company_id):
    """Create a contact_companies affiliation row."""
    conn.execute(
        """INSERT OR IGNORE INTO contact_companies
           (id, contact_id, company_id, is_primary, is_current, source, created_at, updated_at)
           VALUES (?, ?, ?, 1, 1, 'test', ?, ?)""",
        (_uid(), contact_id, company_id, _now_iso(), _now_iso()),
    )


def _insert_provider_account(conn) -> str:
    aid = _uid()
    now = _now_iso()
    conn.execute(
        """INSERT INTO provider_accounts
               (id, provider, account_type, email_address, created_at, updated_at)
           VALUES (?, 'gmail', 'email', 'me@example.com', ?, ?)""",
        (aid, now, now),
    )
    return aid


def _insert_communication(
    conn, account_id, direction="inbound", sender="alice@acme.com",
    timestamp=None, thread_id=None,
) -> str:
    """Insert a communication and return its ID."""
    comm_id = _uid()
    now = _now_iso()
    ts = timestamp or now
    tid = thread_id or _uid()
    conn.execute(
        """INSERT INTO communications
               (id, account_id, channel, timestamp, direction,
                sender_address, provider_thread_id, provider_message_id,
                created_at, updated_at)
           VALUES (?, ?, 'email', ?, ?, ?, ?, ?, ?, ?)""",
        (comm_id, account_id, ts, direction, sender, tid, _uid(), now, now),
    )
    return comm_id


def _insert_comm_participant(conn, comm_id, address, role="to") -> None:
    conn.execute(
        """INSERT INTO communication_participants (communication_id, address, role)
           VALUES (?, ?, ?)""",
        (comm_id, address, role),
    )


def _insert_conversation(conn, title="Test Convo") -> str:
    conv_id = _uid()
    now = _now_iso()
    conn.execute(
        """INSERT INTO conversations (id, title, status, created_at, updated_at)
           VALUES (?, ?, 'active', ?, ?)""",
        (conv_id, title, now, now),
    )
    return conv_id


def _link_conversation(conn, conv_id, comm_id) -> None:
    now = _now_iso()
    conn.execute(
        """INSERT INTO conversation_communications
               (conversation_id, communication_id, created_at)
           VALUES (?, ?, ?)""",
        (conv_id, comm_id, now),
    )


def _insert_conv_participant(conn, conv_id, address, contact_id=None) -> None:
    now = _now_iso()
    conn.execute(
        """INSERT OR IGNORE INTO conversation_participants
               (conversation_id, address, contact_id, first_seen_at, last_seen_at)
           VALUES (?, ?, ?, ?, ?)""",
        (conv_id, address, contact_id, now, now),
    )


# ===========================================================================
# Unit tests — factor functions
# ===========================================================================

class TestRecencyScore:
    def test_today(self):
        assert _recency_score(0) == 1.0

    def test_half_year(self):
        score = _recency_score(RECENCY_WINDOW_DAYS / 2)
        assert abs(score - 0.5) < 0.01

    def test_one_year(self):
        assert _recency_score(RECENCY_WINDOW_DAYS) == 0.0

    def test_over_one_year(self):
        assert _recency_score(500) == 0.0

    def test_none(self):
        assert _recency_score(None) == 0.0

    def test_negative(self):
        assert _recency_score(-5) == 1.0


class TestFrequencyScore:
    def test_zero(self):
        assert _frequency_score(0, 0) == 0.0

    def test_outbound_only(self):
        score = _frequency_score(10, 0)
        assert 0.0 < score < 1.0

    def test_inbound_only(self):
        score = _frequency_score(0, 10)
        # Should be less than outbound-only due to INBOUND_WEIGHT < OUTBOUND_WEIGHT
        outbound_score = _frequency_score(10, 0)
        assert score < outbound_score

    def test_at_cap(self):
        score = _frequency_score(FREQUENCY_CAP, 0)
        assert abs(score - 1.0) < 0.01

    def test_over_cap(self):
        score = _frequency_score(FREQUENCY_CAP * 2, 0)
        assert score >= 1.0 or abs(score - 1.0) < 0.05


class TestReciprocityScore:
    def test_balanced(self):
        assert abs(_reciprocity_score(50, 50) - 1.0) < 0.01

    def test_all_outbound(self):
        assert _reciprocity_score(100, 0) == 0.0

    def test_all_inbound(self):
        assert _reciprocity_score(0, 100) == 0.0

    def test_slight_skew(self):
        score = _reciprocity_score(60, 40)
        assert 0.5 < score < 1.0

    def test_no_comms(self):
        assert _reciprocity_score(0, 0) == 0.0


class TestBreadthScore:
    def test_zero(self):
        assert _breadth_score(0) == 0.0

    def test_one(self):
        score = _breadth_score(1)
        assert 0.0 < score < 0.5

    def test_at_cap(self):
        score = _breadth_score(15)
        assert abs(score - 1.0) < 0.01

    def test_over_cap(self):
        score = _breadth_score(100)
        assert score >= 1.0 or abs(score - 1.0) < 0.01


class TestDurationScore:
    def test_same_day(self):
        now = _now_iso()
        assert _duration_score(now, now) == 0.0

    def test_one_year(self):
        now = datetime.now(timezone.utc)
        start = (now - timedelta(days=365)).isoformat()
        score = _duration_score(start, now.isoformat())
        assert abs(score - 0.5) < 0.01

    def test_two_years(self):
        now = datetime.now(timezone.utc)
        start = (now - timedelta(days=DURATION_CAP_DAYS)).isoformat()
        score = _duration_score(start, now.isoformat())
        assert abs(score - 1.0) < 0.01

    def test_none_values(self):
        assert _duration_score(None, _now_iso()) == 0.0
        assert _duration_score(_now_iso(), None) == 0.0
        assert _duration_score(None, None) == 0.0

    def test_invalid_format(self):
        assert _duration_score("not-a-date", _now_iso()) == 0.0


# ===========================================================================
# Integration tests — compute functions with seeded DB
# ===========================================================================

class TestComputeCompanyScore:
    def test_no_communications(self, tmp_db):
        with get_connection() as conn:
            cid = _insert_company(conn)
            result = compute_company_score(conn, cid)
        assert result is None

    def test_with_communications(self, tmp_db):
        with get_connection() as conn:
            cid = _insert_company(conn)
            contact_id = _insert_contact(conn, email="alice@acme.com")
            _link_contact_to_company(conn, contact_id, cid)
            aid = _insert_provider_account(conn)

            # Create some inbound and outbound comms
            for i in range(5):
                comm = _insert_communication(
                    conn, aid, direction="inbound",
                    sender="alice@acme.com", timestamp=_days_ago(i),
                )
                _insert_comm_participant(conn, comm, "alice@acme.com", role="from")

            for i in range(3):
                comm = _insert_communication(
                    conn, aid, direction="outbound",
                    sender="me@example.com", timestamp=_days_ago(i),
                )
                _insert_comm_participant(conn, comm, "alice@acme.com", role="to")

            result = compute_company_score(conn, cid)

        assert result is not None
        assert 0.0 < result["score"] <= 1.0
        assert "recency" in result["factors"]
        assert "frequency" in result["factors"]
        assert "reciprocity" in result["factors"]
        assert "breadth" in result["factors"]
        assert "duration" in result["factors"]
        # All factors should be between 0 and 1
        for f, v in result["factors"].items():
            assert 0.0 <= v <= 1.0, f"Factor {f} = {v} out of range"

    def test_multiple_contacts(self, tmp_db):
        """Company with multiple contacts should have higher breadth."""
        with get_connection() as conn:
            cid = _insert_company(conn)
            c1 = _insert_contact(conn, "Alice", email="alice@acme.com")
            _link_contact_to_company(conn, c1, cid)
            c2 = _insert_contact(conn, "Bob", email="bob@acme.com")
            _link_contact_to_company(conn, c2, cid)
            aid = _insert_provider_account(conn)

            comm1 = _insert_communication(
                conn, aid, direction="inbound",
                sender="alice@acme.com", timestamp=_days_ago(1),
            )
            _insert_comm_participant(conn, comm1, "alice@acme.com", role="from")

            comm2 = _insert_communication(
                conn, aid, direction="inbound",
                sender="bob@acme.com", timestamp=_days_ago(2),
            )
            _insert_comm_participant(conn, comm2, "bob@acme.com", role="from")

            result = compute_company_score(conn, cid)

        assert result is not None
        assert result["factors"]["breadth"] > 0

    def test_custom_weights(self, tmp_db):
        """Custom weights should change the final score."""
        with get_connection() as conn:
            cid = _insert_company(conn)
            ct = _insert_contact(conn, email="alice@acme.com")
            _link_contact_to_company(conn, ct, cid)
            aid = _insert_provider_account(conn)

            comm = _insert_communication(
                conn, aid, direction="inbound",
                sender="alice@acme.com", timestamp=_days_ago(0),
            )
            _insert_comm_participant(conn, comm, "alice@acme.com", role="from")

            default_result = compute_company_score(conn, cid)
            recency_only = compute_company_score(
                conn, cid,
                weights={"recency": 1.0, "frequency": 0, "reciprocity": 0,
                         "breadth": 0, "duration": 0},
            )

        assert default_result is not None
        assert recency_only is not None
        # Recency-only should differ from default
        assert recency_only["score"] != default_result["score"]

    def test_old_communications_low_recency(self, tmp_db):
        """Comms from 400 days ago should yield 0 recency."""
        with get_connection() as conn:
            cid = _insert_company(conn)
            ct = _insert_contact(conn, email="alice@acme.com")
            _link_contact_to_company(conn, ct, cid)
            aid = _insert_provider_account(conn)

            comm = _insert_communication(
                conn, aid, direction="inbound",
                sender="alice@acme.com", timestamp=_days_ago(400),
            )
            _insert_comm_participant(conn, comm, "alice@acme.com", role="from")

            result = compute_company_score(conn, cid)

        assert result is not None
        assert result["factors"]["recency"] == 0.0


class TestComputeContactScore:
    def test_no_communications(self, tmp_db):
        with get_connection() as conn:
            cid = _insert_contact(conn, email="bob@example.com")
            result = compute_contact_score(conn, cid)
        assert result is None

    def test_with_communications(self, tmp_db):
        with get_connection() as conn:
            contact_id = _insert_contact(conn, email="bob@example.com")
            aid = _insert_provider_account(conn)

            for i in range(4):
                comm = _insert_communication(
                    conn, aid, direction="inbound",
                    sender="bob@example.com", timestamp=_days_ago(i * 10),
                )
                _insert_comm_participant(conn, comm, "bob@example.com", role="from")

            for i in range(2):
                comm = _insert_communication(
                    conn, aid, direction="outbound",
                    sender="me@example.com", timestamp=_days_ago(i * 5),
                )
                _insert_comm_participant(conn, comm, "bob@example.com", role="to")

            # Create conversations for breadth
            conv1 = _insert_conversation(conn, "Thread 1")
            _link_conversation(conn, conv1, comm)
            _insert_conv_participant(conn, conv1, "bob@example.com", contact_id)

            result = compute_contact_score(conn, contact_id)

        assert result is not None
        assert 0.0 < result["score"] <= 1.0
        for f, v in result["factors"].items():
            assert 0.0 <= v <= 1.0, f"Factor {f} = {v} out of range"

    def test_direction_weighting(self, tmp_db):
        """Outbound comms should contribute more to frequency than inbound."""
        with get_connection() as conn:
            c_out = _insert_contact(conn, "Outbound", email="out@test.com")
            c_in = _insert_contact(conn, "Inbound", email="in@test.com")
            aid = _insert_provider_account(conn)

            # c_out: all outbound to them (participant path only)
            for i in range(5):
                comm = _insert_communication(
                    conn, aid, direction="outbound",
                    sender="me@example.com", timestamp=_days_ago(i),
                )
                _insert_comm_participant(conn, comm, "out@test.com", role="to")

            # c_in: all inbound from them (sender path only — no participant row)
            for i in range(5):
                _insert_communication(
                    conn, aid, direction="inbound",
                    sender="in@test.com", timestamp=_days_ago(i),
                )

            r_out = compute_contact_score(conn, c_out)
            r_in = compute_contact_score(conn, c_in)

        assert r_out is not None and r_in is not None
        # Outbound-weighted frequency should be higher
        assert r_out["factors"]["frequency"] > r_in["factors"]["frequency"]

    def test_breadth_multiple_conversations(self, tmp_db):
        """Contact in multiple conversations should have higher breadth."""
        with get_connection() as conn:
            contact_id = _insert_contact(conn, email="multi@test.com")
            aid = _insert_provider_account(conn)

            for i in range(5):
                comm = _insert_communication(
                    conn, aid, direction="inbound",
                    sender="multi@test.com", timestamp=_days_ago(i),
                )
                _insert_comm_participant(conn, comm, "multi@test.com", role="from")

                conv = _insert_conversation(conn, f"Thread {i}")
                _link_conversation(conn, conv, comm)
                _insert_conv_participant(conn, conv, "multi@test.com", contact_id)

            result = compute_contact_score(conn, contact_id)

        assert result is not None
        assert result["factors"]["breadth"] > 0


# ===========================================================================
# Persistence tests
# ===========================================================================

class TestPersistence:
    def test_upsert_insert(self, tmp_db):
        with get_connection() as conn:
            cid = _insert_company(conn)
            upsert_entity_score(
                conn, "company", cid, SCORE_TYPE, 0.75,
                {"recency": 0.9, "frequency": 0.5},
            )

        result = get_entity_score("company", cid)
        assert result is not None
        assert result["score_value"] == 0.75
        assert result["factors"]["recency"] == 0.9

    def test_upsert_update(self, tmp_db):
        with get_connection() as conn:
            cid = _insert_company(conn)
            upsert_entity_score(
                conn, "company", cid, SCORE_TYPE, 0.50,
                {"recency": 0.5},
            )
        # Now update
        with get_connection() as conn:
            upsert_entity_score(
                conn, "company", cid, SCORE_TYPE, 0.85,
                {"recency": 0.9},
            )

        result = get_entity_score("company", cid)
        assert result is not None
        assert result["score_value"] == 0.85
        assert result["factors"]["recency"] == 0.9

    def test_get_not_found(self, tmp_db):
        result = get_entity_score("company", "nonexistent")
        assert result is None

    def test_get_with_triggered_by(self, tmp_db):
        with get_connection() as conn:
            cid = _insert_company(conn)
            upsert_entity_score(
                conn, "company", cid, SCORE_TYPE, 0.60,
                {"recency": 0.6}, triggered_by="batch",
            )

        result = get_entity_score("company", cid)
        assert result["triggered_by"] == "batch"


# ===========================================================================
# Batch tests
# ===========================================================================

class TestBatch:
    def test_score_all_companies(self, tmp_db):
        with get_connection() as conn:
            cid = _insert_company(conn, "Test Co")
            ct = _insert_contact(conn, email="test@testco.com")
            _link_contact_to_company(conn, ct, cid)
            aid = _insert_provider_account(conn)

            comm = _insert_communication(
                conn, aid, direction="inbound",
                sender="test@testco.com", timestamp=_days_ago(1),
            )
            _insert_comm_participant(conn, comm, "test@testco.com", role="from")

            # Also add a company with no comms
            _insert_company(conn, "Empty Co", domain="empty.com")

        result = score_all_companies()
        assert result["scored"] == 1
        assert result["skipped"] == 1

        # Verify persisted
        score = get_entity_score("company", cid)
        assert score is not None
        assert score["score_value"] > 0

    def test_score_all_contacts(self, tmp_db):
        with get_connection() as conn:
            c1 = _insert_contact(conn, "Active", email="active@test.com")
            c2 = _insert_contact(conn, "Inactive", email="inactive@test.com")
            aid = _insert_provider_account(conn)

            comm = _insert_communication(
                conn, aid, direction="inbound",
                sender="active@test.com", timestamp=_days_ago(1),
            )
            _insert_comm_participant(conn, comm, "active@test.com", role="from")

        result = score_all_contacts()
        assert result["scored"] == 1
        assert result["skipped"] == 1

        score = get_entity_score("contact", c1)
        assert score is not None
        assert score["score_value"] > 0

    def test_batch_updates_existing(self, tmp_db):
        """Running batch twice should update, not duplicate."""
        with get_connection() as conn:
            cid = _insert_company(conn)
            ct = _insert_contact(conn, email="x@acme.com")
            _link_contact_to_company(conn, ct, cid)
            aid = _insert_provider_account(conn)

            comm = _insert_communication(
                conn, aid, direction="inbound",
                sender="x@acme.com", timestamp=_days_ago(1),
            )
            _insert_comm_participant(conn, comm, "x@acme.com", role="from")

        r1 = score_all_companies()
        r2 = score_all_companies()
        assert r1["scored"] == 1
        assert r2["scored"] == 1

        # Should only be one score row
        with get_connection() as conn:
            count = conn.execute(
                "SELECT COUNT(*) AS cnt FROM entity_scores WHERE entity_id = ?",
                (cid,),
            ).fetchone()["cnt"]
        assert count == 1
