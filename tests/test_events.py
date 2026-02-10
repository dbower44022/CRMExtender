"""Tests for the events system (tables, models, migration)."""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone

import pytest

from poc.database import get_connection, init_db
from poc.models import Event


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@pytest.fixture()
def tmp_db(tmp_path, monkeypatch):
    """Create a temporary database and point config at it."""
    db_file = tmp_path / "test.db"
    monkeypatch.setattr("poc.config.DB_PATH", db_file)
    init_db(db_file)
    return db_file


# ---------------------------------------------------------------------------
# Event model: to_row / from_row
# ---------------------------------------------------------------------------

class TestEventModel:
    def test_to_row_defaults(self):
        event = Event(title="Team standup")
        row = event.to_row()
        assert row["title"] == "Team standup"
        assert row["event_type"] == "meeting"
        assert row["is_all_day"] == 0
        assert row["recurrence_type"] == "none"
        assert row["source"] == "manual"
        assert row["status"] == "confirmed"
        assert row["id"]  # UUID generated
        assert row["created_at"]

    def test_to_row_with_explicit_id(self):
        event = Event(title="Lunch")
        row = event.to_row(event_id="evt-123")
        assert row["id"] == "evt-123"

    def test_to_row_birthday(self):
        event = Event(
            title="Alice's Birthday",
            event_type="birthday",
            start_date="2026-03-15",
            is_all_day=True,
            recurrence_type="yearly",
            recurrence_rule="RRULE:FREQ=YEARLY;BYMONTH=3;BYMONTHDAY=15",
        )
        row = event.to_row()
        assert row["event_type"] == "birthday"
        assert row["is_all_day"] == 1
        assert row["start_date"] == "2026-03-15"
        assert row["recurrence_type"] == "yearly"
        assert "FREQ=YEARLY" in row["recurrence_rule"]

    def test_to_row_meeting_with_times(self):
        event = Event(
            title="Sprint Planning",
            start_datetime="2026-02-10T09:00:00-05:00",
            end_datetime="2026-02-10T10:00:00-05:00",
            timezone="America/New_York",
            location="Conference Room A",
        )
        row = event.to_row()
        assert row["start_datetime"] == "2026-02-10T09:00:00-05:00"
        assert row["end_datetime"] == "2026-02-10T10:00:00-05:00"
        assert row["timezone"] == "America/New_York"
        assert row["location"] == "Conference Room A"

    def test_to_row_provider_fields(self):
        event = Event(
            title="Synced Meeting",
            provider_event_id="gcal-abc123",
            provider_calendar_id="primary",
            account_id="acc-1",
            source="google_calendar",
        )
        row = event.to_row()
        assert row["provider_event_id"] == "gcal-abc123"
        assert row["provider_calendar_id"] == "primary"
        assert row["account_id"] == "acc-1"
        assert row["source"] == "google_calendar"

    def test_to_row_audit_fields(self):
        event = Event(title="Audited")
        row = event.to_row(created_by="user-1", updated_by="user-2")
        assert row["created_by"] == "user-1"
        assert row["updated_by"] == "user-2"

    def test_to_row_empty_strings_become_none(self):
        event = Event(title="Minimal")
        row = event.to_row()
        assert row["description"] is None
        assert row["location"] is None
        assert row["timezone"] is None
        assert row["recurrence_rule"] is None
        assert row["provider_event_id"] is None

    def test_from_row_roundtrip(self):
        original = Event(
            title="Roundtrip Test",
            event_type="conference",
            description="A conference",
            start_datetime="2026-06-01T08:00:00Z",
            end_datetime="2026-06-03T17:00:00Z",
            timezone="UTC",
            location="Convention Center",
            source="manual",
            status="confirmed",
        )
        row = original.to_row(event_id="evt-rt")
        restored = Event.from_row(row)
        assert restored.title == original.title
        assert restored.event_type == original.event_type
        assert restored.description == original.description
        assert restored.start_datetime == original.start_datetime
        assert restored.end_datetime == original.end_datetime
        assert restored.timezone == original.timezone
        assert restored.location == original.location

    def test_from_row_missing_fields(self):
        row = {"title": "Sparse", "event_type": "other"}
        event = Event.from_row(row)
        assert event.title == "Sparse"
        assert event.event_type == "other"
        assert event.description == ""
        assert event.recurrence_type == "none"
        assert event.source == "manual"
        assert event.status == "confirmed"

    def test_from_row_is_all_day_bool(self):
        row = {"title": "AllDay", "is_all_day": 1}
        event = Event.from_row(row)
        assert event.is_all_day is True

        row2 = {"title": "NotAllDay", "is_all_day": 0}
        event2 = Event.from_row(row2)
        assert event2.is_all_day is False


# ---------------------------------------------------------------------------
# Schema: tables created by init_db
# ---------------------------------------------------------------------------

class TestEventsSchema:
    def test_events_table_exists(self, tmp_db):
        with get_connection() as conn:
            tables = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
        assert "events" in tables
        assert "event_participants" in tables
        assert "event_conversations" in tables

    def test_events_columns(self, tmp_db):
        with get_connection() as conn:
            cols = {
                row[1]
                for row in conn.execute("PRAGMA table_info(events)").fetchall()
            }
        expected = {
            "id", "title", "description", "event_type",
            "start_date", "start_datetime", "end_date", "end_datetime",
            "is_all_day", "timezone", "recurrence_rule", "recurrence_type",
            "recurring_event_id", "location",
            "provider_event_id", "provider_calendar_id", "account_id",
            "source", "status",
            "created_by", "updated_by", "created_at", "updated_at",
        }
        assert expected.issubset(cols)

    def test_event_participants_columns(self, tmp_db):
        with get_connection() as conn:
            cols = {
                row[1]
                for row in conn.execute(
                    "PRAGMA table_info(event_participants)"
                ).fetchall()
            }
        assert {"event_id", "entity_type", "entity_id", "role", "rsvp_status"} == cols

    def test_event_conversations_columns(self, tmp_db):
        with get_connection() as conn:
            cols = {
                row[1]
                for row in conn.execute(
                    "PRAGMA table_info(event_conversations)"
                ).fetchall()
            }
        assert {"event_id", "conversation_id", "created_at"} == cols


# ---------------------------------------------------------------------------
# Insert / query operations
# ---------------------------------------------------------------------------

class TestEventsInsert:
    def test_insert_event(self, tmp_db):
        event = Event(title="Test Meeting", event_type="meeting")
        row = event.to_row(event_id="evt-1")
        with get_connection() as conn:
            conn.execute(
                """INSERT INTO events
                   (id, title, description, event_type, start_date, start_datetime,
                    end_date, end_datetime, is_all_day, timezone, recurrence_rule,
                    recurrence_type, recurring_event_id, location,
                    provider_event_id, provider_calendar_id, account_id,
                    source, status, created_by, updated_by, created_at, updated_at)
                   VALUES (:id, :title, :description, :event_type, :start_date,
                    :start_datetime, :end_date, :end_datetime, :is_all_day, :timezone,
                    :recurrence_rule, :recurrence_type, :recurring_event_id, :location,
                    :provider_event_id, :provider_calendar_id, :account_id,
                    :source, :status, :created_by, :updated_by, :created_at, :updated_at)""",
                row,
            )
        with get_connection() as conn:
            result = conn.execute("SELECT * FROM events WHERE id = 'evt-1'").fetchone()
        assert result is not None
        assert result["title"] == "Test Meeting"
        assert result["event_type"] == "meeting"

    def test_insert_birthday_event(self, tmp_db):
        event = Event(
            title="Bob's Birthday",
            event_type="birthday",
            start_date="1990-07-20",
            is_all_day=True,
            recurrence_type="yearly",
        )
        row = event.to_row(event_id="evt-bday")
        with get_connection() as conn:
            conn.execute(
                """INSERT INTO events
                   (id, title, description, event_type, start_date, start_datetime,
                    end_date, end_datetime, is_all_day, timezone, recurrence_rule,
                    recurrence_type, recurring_event_id, location,
                    provider_event_id, provider_calendar_id, account_id,
                    source, status, created_by, updated_by, created_at, updated_at)
                   VALUES (:id, :title, :description, :event_type, :start_date,
                    :start_datetime, :end_date, :end_datetime, :is_all_day, :timezone,
                    :recurrence_rule, :recurrence_type, :recurring_event_id, :location,
                    :provider_event_id, :provider_calendar_id, :account_id,
                    :source, :status, :created_by, :updated_by, :created_at, :updated_at)""",
                row,
            )
        with get_connection() as conn:
            result = conn.execute("SELECT * FROM events WHERE id = 'evt-bday'").fetchone()
        assert result["event_type"] == "birthday"
        assert result["is_all_day"] == 1
        assert result["recurrence_type"] == "yearly"

    def test_event_type_check_constraint(self, tmp_db):
        event = Event(title="Bad Type", event_type="invalid")
        row = event.to_row(event_id="evt-bad")
        with pytest.raises(sqlite3.IntegrityError):
            with get_connection() as conn:
                conn.execute(
                    """INSERT INTO events
                       (id, title, description, event_type, start_date, start_datetime,
                        end_date, end_datetime, is_all_day, timezone, recurrence_rule,
                        recurrence_type, recurring_event_id, location,
                        provider_event_id, provider_calendar_id, account_id,
                        source, status, created_by, updated_by, created_at, updated_at)
                       VALUES (:id, :title, :description, :event_type, :start_date,
                        :start_datetime, :end_date, :end_datetime, :is_all_day, :timezone,
                        :recurrence_rule, :recurrence_type, :recurring_event_id, :location,
                        :provider_event_id, :provider_calendar_id, :account_id,
                        :source, :status, :created_by, :updated_by, :created_at, :updated_at)""",
                    row,
                )

    def test_recurrence_type_check_constraint(self, tmp_db):
        event = Event(title="Bad Recur", recurrence_type="biweekly")
        row = event.to_row(event_id="evt-bad2")
        with pytest.raises(sqlite3.IntegrityError):
            with get_connection() as conn:
                conn.execute(
                    """INSERT INTO events
                       (id, title, description, event_type, start_date, start_datetime,
                        end_date, end_datetime, is_all_day, timezone, recurrence_rule,
                        recurrence_type, recurring_event_id, location,
                        provider_event_id, provider_calendar_id, account_id,
                        source, status, created_by, updated_by, created_at, updated_at)
                       VALUES (:id, :title, :description, :event_type, :start_date,
                        :start_datetime, :end_date, :end_datetime, :is_all_day, :timezone,
                        :recurrence_rule, :recurrence_type, :recurring_event_id, :location,
                        :provider_event_id, :provider_calendar_id, :account_id,
                        :source, :status, :created_by, :updated_by, :created_at, :updated_at)""",
                    row,
                )

    def test_status_check_constraint(self, tmp_db):
        event = Event(title="Bad Status", status="deleted")
        row = event.to_row(event_id="evt-bad3")
        with pytest.raises(sqlite3.IntegrityError):
            with get_connection() as conn:
                conn.execute(
                    """INSERT INTO events
                       (id, title, description, event_type, start_date, start_datetime,
                        end_date, end_datetime, is_all_day, timezone, recurrence_rule,
                        recurrence_type, recurring_event_id, location,
                        provider_event_id, provider_calendar_id, account_id,
                        source, status, created_by, updated_by, created_at, updated_at)
                       VALUES (:id, :title, :description, :event_type, :start_date,
                        :start_datetime, :end_date, :end_datetime, :is_all_day, :timezone,
                        :recurrence_rule, :recurrence_type, :recurring_event_id, :location,
                        :provider_event_id, :provider_calendar_id, :account_id,
                        :source, :status, :created_by, :updated_by, :created_at, :updated_at)""",
                    row,
                )

    def test_provider_event_uniqueness(self, tmp_db):
        """UNIQUE(account_id, provider_event_id) prevents duplicate synced events."""
        now = _now_iso()
        # Create a provider account first
        with get_connection() as conn:
            conn.execute(
                """INSERT INTO provider_accounts
                   (id, provider, account_type, email_address, created_at, updated_at)
                   VALUES ('acc-1', 'google', 'calendar', 'test@test.com', ?, ?)""",
                (now, now),
            )
        event1 = Event(
            title="Meeting 1",
            provider_event_id="gcal-123",
            account_id="acc-1",
            source="google_calendar",
        )
        event2 = Event(
            title="Duplicate",
            provider_event_id="gcal-123",
            account_id="acc-1",
            source="google_calendar",
        )
        row1 = event1.to_row(event_id="evt-u1")
        row2 = event2.to_row(event_id="evt-u2")
        with get_connection() as conn:
            conn.execute(
                """INSERT INTO events
                   (id, title, description, event_type, start_date, start_datetime,
                    end_date, end_datetime, is_all_day, timezone, recurrence_rule,
                    recurrence_type, recurring_event_id, location,
                    provider_event_id, provider_calendar_id, account_id,
                    source, status, created_by, updated_by, created_at, updated_at)
                   VALUES (:id, :title, :description, :event_type, :start_date,
                    :start_datetime, :end_date, :end_datetime, :is_all_day, :timezone,
                    :recurrence_rule, :recurrence_type, :recurring_event_id, :location,
                    :provider_event_id, :provider_calendar_id, :account_id,
                    :source, :status, :created_by, :updated_by, :created_at, :updated_at)""",
                row1,
            )
        with pytest.raises(sqlite3.IntegrityError):
            with get_connection() as conn:
                conn.execute(
                    """INSERT INTO events
                       (id, title, description, event_type, start_date, start_datetime,
                        end_date, end_datetime, is_all_day, timezone, recurrence_rule,
                        recurrence_type, recurring_event_id, location,
                        provider_event_id, provider_calendar_id, account_id,
                        source, status, created_by, updated_by, created_at, updated_at)
                       VALUES (:id, :title, :description, :event_type, :start_date,
                        :start_datetime, :end_date, :end_datetime, :is_all_day, :timezone,
                        :recurrence_rule, :recurrence_type, :recurring_event_id, :location,
                        :provider_event_id, :provider_calendar_id, :account_id,
                        :source, :status, :created_by, :updated_by, :created_at, :updated_at)""",
                    row2,
                )


# ---------------------------------------------------------------------------
# Event participants
# ---------------------------------------------------------------------------

def _insert_event(conn, event_id="evt-1", title="Test Event"):
    """Helper to insert a minimal event."""
    now = _now_iso()
    conn.execute(
        """INSERT INTO events (id, title, event_type, source, status,
            recurrence_type, is_all_day, created_at, updated_at)
           VALUES (?, ?, 'meeting', 'manual', 'confirmed', 'none', 0, ?, ?)""",
        (event_id, title, now, now),
    )


def _insert_contact(conn, contact_id="contact-1", name="Alice"):
    """Helper to insert a minimal contact."""
    now = _now_iso()
    conn.execute(
        """INSERT INTO contacts (id, name, source, status, created_at, updated_at)
           VALUES (?, ?, 'test', 'active', ?, ?)""",
        (contact_id, name, now, now),
    )


class TestEventParticipants:
    def test_add_contact_participant(self, tmp_db):
        with get_connection() as conn:
            _insert_event(conn)
            _insert_contact(conn)
            conn.execute(
                """INSERT INTO event_participants (event_id, entity_type, entity_id, role)
                   VALUES ('evt-1', 'contact', 'contact-1', 'attendee')""",
            )
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM event_participants WHERE event_id = 'evt-1'"
            ).fetchall()
        assert len(rows) == 1
        assert rows[0]["entity_type"] == "contact"
        assert rows[0]["role"] == "attendee"

    def test_add_company_participant(self, tmp_db):
        now = _now_iso()
        with get_connection() as conn:
            _insert_event(conn)
            conn.execute(
                """INSERT INTO companies (id, name, status, created_at, updated_at)
                   VALUES ('comp-1', 'Acme Corp', 'active', ?, ?)""",
                (now, now),
            )
            conn.execute(
                """INSERT INTO event_participants (event_id, entity_type, entity_id, role)
                   VALUES ('evt-1', 'company', 'comp-1', 'host')""",
            )
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM event_participants WHERE entity_type = 'company'"
            ).fetchall()
        assert len(rows) == 1
        assert rows[0]["role"] == "host"

    def test_rsvp_status(self, tmp_db):
        with get_connection() as conn:
            _insert_event(conn)
            _insert_contact(conn)
            conn.execute(
                """INSERT INTO event_participants
                   (event_id, entity_type, entity_id, role, rsvp_status)
                   VALUES ('evt-1', 'contact', 'contact-1', 'attendee', 'accepted')""",
            )
        with get_connection() as conn:
            row = conn.execute(
                "SELECT rsvp_status FROM event_participants WHERE entity_id = 'contact-1'"
            ).fetchone()
        assert row["rsvp_status"] == "accepted"

    def test_rsvp_status_check_constraint(self, tmp_db):
        with pytest.raises(sqlite3.IntegrityError):
            with get_connection() as conn:
                _insert_event(conn)
                _insert_contact(conn)
                conn.execute(
                    """INSERT INTO event_participants
                       (event_id, entity_type, entity_id, role, rsvp_status)
                       VALUES ('evt-1', 'contact', 'contact-1', 'attendee', 'maybe')""",
                )

    def test_entity_type_check_constraint(self, tmp_db):
        with pytest.raises(sqlite3.IntegrityError):
            with get_connection() as conn:
                _insert_event(conn)
                conn.execute(
                    """INSERT INTO event_participants
                       (event_id, entity_type, entity_id, role)
                       VALUES ('evt-1', 'project', 'proj-1', 'attendee')""",
                )

    def test_multiple_participants(self, tmp_db):
        with get_connection() as conn:
            _insert_event(conn)
            _insert_contact(conn, "c-1", "Alice")
            _insert_contact(conn, "c-2", "Bob")
            _insert_contact(conn, "c-3", "Carol")
            conn.execute(
                """INSERT INTO event_participants (event_id, entity_type, entity_id, role)
                   VALUES ('evt-1', 'contact', 'c-1', 'organizer')""",
            )
            conn.execute(
                """INSERT INTO event_participants (event_id, entity_type, entity_id, role)
                   VALUES ('evt-1', 'contact', 'c-2', 'attendee')""",
            )
            conn.execute(
                """INSERT INTO event_participants (event_id, entity_type, entity_id, role)
                   VALUES ('evt-1', 'contact', 'c-3', 'attendee')""",
            )
        with get_connection() as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM event_participants WHERE event_id = 'evt-1'"
            ).fetchone()[0]
        assert count == 3

    def test_cascade_delete_event(self, tmp_db):
        """Deleting an event should cascade to participants."""
        with get_connection() as conn:
            _insert_event(conn)
            _insert_contact(conn)
            conn.execute(
                """INSERT INTO event_participants (event_id, entity_type, entity_id, role)
                   VALUES ('evt-1', 'contact', 'contact-1', 'attendee')""",
            )
        with get_connection() as conn:
            conn.execute("DELETE FROM events WHERE id = 'evt-1'")
        with get_connection() as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM event_participants WHERE event_id = 'evt-1'"
            ).fetchone()[0]
        assert count == 0

    def test_honoree_role_for_birthday(self, tmp_db):
        with get_connection() as conn:
            now = _now_iso()
            conn.execute(
                """INSERT INTO events (id, title, event_type, start_date, is_all_day,
                    recurrence_type, source, status, created_at, updated_at)
                   VALUES ('evt-bday', 'Alice Birthday', 'birthday', '1990-03-15', 1,
                    'yearly', 'manual', 'confirmed', ?, ?)""",
                (now, now),
            )
            _insert_contact(conn)
            conn.execute(
                """INSERT INTO event_participants (event_id, entity_type, entity_id, role)
                   VALUES ('evt-bday', 'contact', 'contact-1', 'honoree')""",
            )
        with get_connection() as conn:
            row = conn.execute(
                "SELECT role FROM event_participants WHERE event_id = 'evt-bday'"
            ).fetchone()
        assert row["role"] == "honoree"


# ---------------------------------------------------------------------------
# Event <-> Conversation linking
# ---------------------------------------------------------------------------

def _insert_conversation(conn, conv_id="conv-1", title="Test Conversation"):
    """Helper to insert a minimal conversation."""
    now = _now_iso()
    conn.execute(
        """INSERT INTO conversations (id, title, status, created_at, updated_at)
           VALUES (?, ?, 'active', ?, ?)""",
        (conv_id, title, now, now),
    )


class TestEventConversations:
    def test_link_event_to_conversation(self, tmp_db):
        now = _now_iso()
        with get_connection() as conn:
            _insert_event(conn)
            _insert_conversation(conn)
            conn.execute(
                """INSERT INTO event_conversations (event_id, conversation_id, created_at)
                   VALUES ('evt-1', 'conv-1', ?)""",
                (now,),
            )
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM event_conversations WHERE event_id = 'evt-1'"
            ).fetchall()
        assert len(rows) == 1
        assert rows[0]["conversation_id"] == "conv-1"

    def test_multiple_conversations_per_event(self, tmp_db):
        now = _now_iso()
        with get_connection() as conn:
            _insert_event(conn)
            _insert_conversation(conn, "conv-1")
            _insert_conversation(conn, "conv-2")
            conn.execute(
                """INSERT INTO event_conversations (event_id, conversation_id, created_at)
                   VALUES ('evt-1', 'conv-1', ?)""",
                (now,),
            )
            conn.execute(
                """INSERT INTO event_conversations (event_id, conversation_id, created_at)
                   VALUES ('evt-1', 'conv-2', ?)""",
                (now,),
            )
        with get_connection() as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM event_conversations WHERE event_id = 'evt-1'"
            ).fetchone()[0]
        assert count == 2

    def test_multiple_events_per_conversation(self, tmp_db):
        now = _now_iso()
        with get_connection() as conn:
            _insert_event(conn, "evt-1")
            _insert_event(conn, "evt-2")
            _insert_conversation(conn)
            conn.execute(
                """INSERT INTO event_conversations (event_id, conversation_id, created_at)
                   VALUES ('evt-1', 'conv-1', ?)""",
                (now,),
            )
            conn.execute(
                """INSERT INTO event_conversations (event_id, conversation_id, created_at)
                   VALUES ('evt-2', 'conv-1', ?)""",
                (now,),
            )
        with get_connection() as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM event_conversations WHERE conversation_id = 'conv-1'"
            ).fetchone()[0]
        assert count == 2

    def test_cascade_delete_event_removes_links(self, tmp_db):
        now = _now_iso()
        with get_connection() as conn:
            _insert_event(conn)
            _insert_conversation(conn)
            conn.execute(
                """INSERT INTO event_conversations (event_id, conversation_id, created_at)
                   VALUES ('evt-1', 'conv-1', ?)""",
                (now,),
            )
        with get_connection() as conn:
            conn.execute("DELETE FROM events WHERE id = 'evt-1'")
        with get_connection() as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM event_conversations WHERE event_id = 'evt-1'"
            ).fetchone()[0]
        assert count == 0

    def test_cascade_delete_conversation_removes_links(self, tmp_db):
        now = _now_iso()
        with get_connection() as conn:
            _insert_event(conn)
            _insert_conversation(conn)
            conn.execute(
                """INSERT INTO event_conversations (event_id, conversation_id, created_at)
                   VALUES ('evt-1', 'conv-1', ?)""",
                (now,),
            )
        with get_connection() as conn:
            conn.execute("DELETE FROM conversations WHERE id = 'conv-1'")
        with get_connection() as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM event_conversations WHERE event_id = 'evt-1'"
            ).fetchone()[0]
        assert count == 0


# ---------------------------------------------------------------------------
# Recurring event parent linking
# ---------------------------------------------------------------------------

class TestRecurringEvents:
    def test_recurring_event_parent(self, tmp_db):
        """An instance event can reference its recurring parent."""
        now = _now_iso()
        with get_connection() as conn:
            # Parent recurring event
            conn.execute(
                """INSERT INTO events (id, title, event_type, recurrence_type,
                    recurrence_rule, is_all_day, source, status, created_at, updated_at)
                   VALUES ('evt-parent', 'Weekly Standup', 'meeting', 'weekly',
                    'RRULE:FREQ=WEEKLY;BYDAY=MO', 0, 'manual', 'confirmed', ?, ?)""",
                (now, now),
            )
            # Instance
            conn.execute(
                """INSERT INTO events (id, title, event_type, recurrence_type,
                    recurring_event_id, start_datetime, is_all_day,
                    source, status, created_at, updated_at)
                   VALUES ('evt-inst', 'Weekly Standup', 'meeting', 'none',
                    'evt-parent', '2026-02-10T09:00:00Z', 0,
                    'manual', 'confirmed', ?, ?)""",
                (now, now),
            )
        with get_connection() as conn:
            instance = conn.execute(
                "SELECT recurring_event_id FROM events WHERE id = 'evt-inst'"
            ).fetchone()
        assert instance["recurring_event_id"] == "evt-parent"

    def test_delete_parent_nullifies_instances(self, tmp_db):
        """ON DELETE SET NULL: deleting parent sets recurring_event_id to NULL."""
        now = _now_iso()
        with get_connection() as conn:
            conn.execute(
                """INSERT INTO events (id, title, event_type, recurrence_type,
                    is_all_day, source, status, created_at, updated_at)
                   VALUES ('evt-p', 'Parent', 'meeting', 'weekly',
                    0, 'manual', 'confirmed', ?, ?)""",
                (now, now),
            )
            conn.execute(
                """INSERT INTO events (id, title, event_type, recurrence_type,
                    recurring_event_id, is_all_day, source, status, created_at, updated_at)
                   VALUES ('evt-c', 'Instance', 'meeting', 'none',
                    'evt-p', 0, 'manual', 'confirmed', ?, ?)""",
                (now, now),
            )
        with get_connection() as conn:
            conn.execute("DELETE FROM events WHERE id = 'evt-p'")
        with get_connection() as conn:
            row = conn.execute(
                "SELECT recurring_event_id FROM events WHERE id = 'evt-c'"
            ).fetchone()
        assert row["recurring_event_id"] is None


# ---------------------------------------------------------------------------
# Migration script
# ---------------------------------------------------------------------------

class TestMigration:
    def test_migration_on_fresh_v5_db(self, tmp_path, monkeypatch):
        """Migration should work on a DB that has no events tables yet."""
        from poc.migrate_to_v6 import migrate

        # Create a v5-like DB (init_db now includes events, so create manually)
        db_file = tmp_path / "v5.db"
        monkeypatch.setattr("poc.config.DB_PATH", db_file)
        conn = sqlite3.connect(str(db_file))
        conn.execute("CREATE TABLE IF NOT EXISTS provider_accounts (id TEXT PRIMARY KEY, provider TEXT NOT NULL, account_type TEXT NOT NULL DEFAULT 'email', email_address TEXT, phone_number TEXT, display_name TEXT, auth_token_path TEXT, sync_cursor TEXT, last_synced_at TEXT, initial_sync_done INTEGER DEFAULT 0, backfill_query TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)")
        conn.execute("CREATE TABLE IF NOT EXISTS users (id TEXT PRIMARY KEY, email TEXT NOT NULL UNIQUE, name TEXT, role TEXT DEFAULT 'member', is_active INTEGER DEFAULT 1, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)")
        conn.execute("CREATE TABLE IF NOT EXISTS conversations (id TEXT PRIMARY KEY, topic_id TEXT, title TEXT, status TEXT DEFAULT 'active', created_at TEXT NOT NULL, updated_at TEXT NOT NULL)")
        conn.execute("CREATE TABLE IF NOT EXISTS contacts (id TEXT PRIMARY KEY, name TEXT, company TEXT, source TEXT, status TEXT DEFAULT 'active', created_at TEXT NOT NULL, updated_at TEXT NOT NULL)")
        conn.commit()
        conn.close()

        migrate(db_file, dry_run=False)

        # Verify tables were created
        conn = sqlite3.connect(str(db_file))
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        conn.close()
        assert "events" in tables
        assert "event_participants" in tables
        assert "event_conversations" in tables

    def test_migration_idempotent(self, tmp_path, monkeypatch):
        """Running migration twice should not fail."""
        from poc.migrate_to_v6 import migrate

        db_file = tmp_path / "v5_idem.db"
        monkeypatch.setattr("poc.config.DB_PATH", db_file)
        conn = sqlite3.connect(str(db_file))
        conn.execute("CREATE TABLE IF NOT EXISTS provider_accounts (id TEXT PRIMARY KEY, provider TEXT NOT NULL, account_type TEXT NOT NULL DEFAULT 'email', email_address TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)")
        conn.execute("CREATE TABLE IF NOT EXISTS users (id TEXT PRIMARY KEY, email TEXT NOT NULL UNIQUE, name TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)")
        conn.execute("CREATE TABLE IF NOT EXISTS conversations (id TEXT PRIMARY KEY, title TEXT, status TEXT DEFAULT 'active', created_at TEXT NOT NULL, updated_at TEXT NOT NULL)")
        conn.commit()
        conn.close()

        # Run twice
        migrate(db_file, dry_run=False)
        migrate(db_file, dry_run=False)

        # Should still have correct tables
        conn = sqlite3.connect(str(db_file))
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        conn.close()
        assert "events" in tables

    def test_migration_creates_backup(self, tmp_path, monkeypatch):
        """Migration should create a backup file."""
        from poc.migrate_to_v6 import migrate

        db_file = tmp_path / "v5_backup.db"
        monkeypatch.setattr("poc.config.DB_PATH", db_file)
        conn = sqlite3.connect(str(db_file))
        conn.execute("CREATE TABLE IF NOT EXISTS provider_accounts (id TEXT PRIMARY KEY, provider TEXT NOT NULL, account_type TEXT NOT NULL DEFAULT 'email', email_address TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)")
        conn.execute("CREATE TABLE IF NOT EXISTS users (id TEXT PRIMARY KEY, email TEXT NOT NULL UNIQUE, name TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)")
        conn.execute("CREATE TABLE IF NOT EXISTS conversations (id TEXT PRIMARY KEY, title TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)")
        conn.commit()
        conn.close()

        migrate(db_file, dry_run=False)

        backup_files = list(tmp_path.glob("*.v5-backup-*.db"))
        assert len(backup_files) == 1

    def test_migration_dry_run(self, tmp_path, monkeypatch):
        """Dry run should not modify the original database."""
        from poc.migrate_to_v6 import migrate

        db_file = tmp_path / "v5_dryrun.db"
        monkeypatch.setattr("poc.config.DB_PATH", db_file)
        conn = sqlite3.connect(str(db_file))
        conn.execute("CREATE TABLE IF NOT EXISTS provider_accounts (id TEXT PRIMARY KEY, provider TEXT NOT NULL, account_type TEXT NOT NULL DEFAULT 'email', email_address TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)")
        conn.execute("CREATE TABLE IF NOT EXISTS users (id TEXT PRIMARY KEY, email TEXT NOT NULL UNIQUE, name TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)")
        conn.execute("CREATE TABLE IF NOT EXISTS conversations (id TEXT PRIMARY KEY, title TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)")
        conn.commit()
        conn.close()

        migrate(db_file, dry_run=True)

        # Original should NOT have events table
        conn = sqlite3.connect(str(db_file))
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        conn.close()
        assert "events" not in tables

        # Backup should have events table
        backup_files = list(tmp_path.glob("*.v5-backup-*.db"))
        assert len(backup_files) == 1
        conn = sqlite3.connect(str(backup_files[0]))
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        conn.close()
        assert "events" in tables
