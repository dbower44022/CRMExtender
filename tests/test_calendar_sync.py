"""Tests for Google Calendar sync.

Covers: event parsing, sync logic, attendee matching,
settings UI, and sync route.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from poc.calendar_client import (
    CalendarScopeError,
    SyncTokenExpiredError,
    _GOOGLE_EVENT_TYPE_MAP,
    _parse_google_event,
)
from poc.calendar_sync import (
    RSVP_MAP,
    _match_attendees,
    _upsert_event,
    sync_all_calendars,
    sync_calendar_events,
)
from poc.database import get_connection, init_db

_NOW = datetime.now(timezone.utc).isoformat()

CUST_ID = "cust-test"
USER_ID = "user-admin"
ACCT_ID = "acct-test"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def tmp_db(tmp_path, monkeypatch):
    """Create a DB with one customer, admin user, and provider account."""
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
        conn.execute(
            "INSERT INTO provider_accounts "
            "(id, customer_id, provider, account_type, email_address, "
            "auth_token_path, created_at, updated_at) "
            "VALUES (?, ?, 'gmail', 'email', 'admin@test.com', '/tmp/fake_token.json', ?, ?)",
            (ACCT_ID, CUST_ID, _NOW, _NOW),
        )
        conn.execute(
            "INSERT INTO user_provider_accounts "
            "(id, user_id, account_id, role, created_at) "
            "VALUES (?, ?, ?, 'owner', ?)",
            (str(uuid.uuid4()), USER_ID, ACCT_ID, _NOW),
        )

    return db_file


@pytest.fixture()
def client(tmp_db, monkeypatch):
    """TestClient authenticated as admin user."""
    monkeypatch.setattr(
        "poc.hierarchy.get_current_user",
        lambda: {"id": USER_ID, "email": "admin@test.com", "name": "Admin User",
                 "role": "admin", "customer_id": CUST_ID},
    )
    from poc.web.app import create_app
    app = create_app()
    return TestClient(app, raise_server_exceptions=False)


def _make_raw_event(
    event_id="evt-1",
    summary="Team Meeting",
    status="confirmed",
    start_dt="2026-02-12T10:00:00-05:00",
    end_dt="2026-02-12T11:00:00-05:00",
    location="Conference Room A",
    attendees=None,
):
    """Build a raw Google Calendar event dict for testing."""
    raw = {
        "id": event_id,
        "summary": summary,
        "status": status,
        "start": {"dateTime": start_dt},
        "end": {"dateTime": end_dt},
        "location": location,
    }
    if attendees:
        raw["attendees"] = attendees
    return raw


def _insert_contact(conn, name, email, customer_id=CUST_ID):
    """Insert a contact with an email identifier."""
    contact_id = str(uuid.uuid4())
    conn.execute(
        "INSERT INTO contacts (id, customer_id, name, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (contact_id, customer_id, name, _NOW, _NOW),
    )
    conn.execute(
        "INSERT INTO contact_identifiers (id, contact_id, type, value, created_at, updated_at) "
        "VALUES (?, ?, 'email', ?, ?, ?)",
        (str(uuid.uuid4()), contact_id, email.lower(), _NOW, _NOW),
    )
    return contact_id


# ===========================================================================
# Calendar client parsing (unit, no DB)
# ===========================================================================

class TestParseGoogleEvent:
    def test_parse_timed_event(self):
        raw = _make_raw_event()
        parsed = _parse_google_event(raw)
        assert parsed["provider_event_id"] == "evt-1"
        assert parsed["title"] == "Team Meeting"
        assert parsed["start_datetime"] == "2026-02-12T10:00:00-05:00"
        assert parsed["end_datetime"] == "2026-02-12T11:00:00-05:00"
        assert parsed["is_all_day"] == 0
        assert parsed["location"] == "Conference Room A"
        assert parsed["event_type"] == "meeting"
        assert parsed["source"] == "google_calendar"

    def test_parse_all_day_event(self):
        raw = {
            "id": "evt-allday",
            "summary": "Company Holiday",
            "status": "confirmed",
            "start": {"date": "2026-12-25"},
            "end": {"date": "2026-12-26"},
        }
        parsed = _parse_google_event(raw)
        assert parsed["is_all_day"] == 1
        assert parsed["start_date"] == "2026-12-25"
        assert parsed["end_date"] == "2026-12-26"
        assert parsed["start_datetime"] is None

    def test_parse_cancelled_event(self):
        raw = _make_raw_event(status="cancelled")
        parsed = _parse_google_event(raw)
        assert parsed["status"] == "cancelled"

    def test_parse_event_no_title(self):
        raw = _make_raw_event()
        del raw["summary"]
        parsed = _parse_google_event(raw)
        assert parsed["title"] == "(no title)"

    def test_parse_attendees(self):
        raw = _make_raw_event(attendees=[
            {"email": "alice@example.com", "displayName": "Alice", "responseStatus": "accepted"},
            {"email": "bob@example.com", "organizer": True, "responseStatus": "accepted"},
        ])
        parsed = _parse_google_event(raw)
        assert len(parsed["attendees"]) == 2
        assert parsed["attendees"][0]["email"] == "alice@example.com"
        assert parsed["attendees"][1]["organizer"] is True

    def test_parse_rsvp_statuses(self):
        for google_status, our_status in RSVP_MAP.items():
            raw = _make_raw_event(attendees=[
                {"email": "x@test.com", "responseStatus": google_status},
            ])
            parsed = _parse_google_event(raw)
            assert parsed["attendees"][0]["responseStatus"] == google_status

    def test_parse_event_no_id_returns_none(self):
        assert _parse_google_event({}) is None

    def test_parse_event_with_description(self):
        raw = _make_raw_event()
        raw["description"] = "Discuss Q1 goals"
        parsed = _parse_google_event(raw)
        assert parsed["description"] == "Discuss Q1 goals"

    def test_parse_birthday_event_type(self):
        """Google eventType='birthday' maps to birthday."""
        raw = _make_raw_event(summary="Jane Doe")
        raw["eventType"] = "birthday"
        parsed = _parse_google_event(raw)
        assert parsed["event_type"] == "birthday"

    def test_parse_birthday_from_title(self):
        """Title containing 'birthday' maps to birthday even without eventType."""
        raw = _make_raw_event(summary="John's Birthday")
        parsed = _parse_google_event(raw)
        assert parsed["event_type"] == "birthday"

    def test_parse_birthday_from_title_case_insensitive(self):
        raw = _make_raw_event(summary="BIRTHDAY PARTY")
        parsed = _parse_google_event(raw)
        assert parsed["event_type"] == "birthday"

    def test_parse_out_of_office_event_type(self):
        raw = _make_raw_event(summary="OOO")
        raw["eventType"] = "outOfOffice"
        parsed = _parse_google_event(raw)
        assert parsed["event_type"] == "other"

    def test_parse_default_event_type_is_meeting(self):
        """Regular events (eventType='default' or missing) stay as meeting."""
        raw = _make_raw_event()
        parsed = _parse_google_event(raw)
        assert parsed["event_type"] == "meeting"

        raw["eventType"] = "default"
        parsed = _parse_google_event(raw)
        assert parsed["event_type"] == "meeting"


# ===========================================================================
# Calendar sync DB tests
# ===========================================================================

class TestUpsertEvent:
    def test_creates_new_event(self, tmp_db):
        event = _parse_google_event(_make_raw_event())
        with get_connection() as conn:
            result = _upsert_event(
                conn, event, ACCT_ID, "primary",
                customer_id=CUST_ID, user_id=USER_ID, now=_NOW,
            )
            assert result == "created"
            row = conn.execute("SELECT * FROM events WHERE provider_event_id = 'evt-1'").fetchone()
            assert row is not None
            assert row["title"] == "Team Meeting"
            assert row["source"] == "google_calendar"
            assert row["account_id"] == ACCT_ID
            assert row["provider_calendar_id"] == "primary"

    def test_updates_existing_event(self, tmp_db):
        event = _parse_google_event(_make_raw_event())
        with get_connection() as conn:
            _upsert_event(
                conn, event, ACCT_ID, "primary",
                customer_id=CUST_ID, user_id=USER_ID, now=_NOW,
            )
            # Update with new title
            event["title"] = "Updated Meeting"
            result = _upsert_event(
                conn, event, ACCT_ID, "primary",
                customer_id=CUST_ID, user_id=USER_ID, now=_NOW,
            )
            assert result == "updated"
            row = conn.execute("SELECT title FROM events WHERE provider_event_id = 'evt-1'").fetchone()
            assert row["title"] == "Updated Meeting"

    def test_event_type_updated_on_resync(self, tmp_db):
        """Upsert updates event_type for existing events."""
        event = _parse_google_event(_make_raw_event())
        assert event["event_type"] == "meeting"
        with get_connection() as conn:
            _upsert_event(
                conn, event, ACCT_ID, "primary",
                customer_id=CUST_ID, user_id=USER_ID, now=_NOW,
            )
            # Simulate re-sync where Google now reports birthday type
            event["event_type"] = "birthday"
            _upsert_event(
                conn, event, ACCT_ID, "primary",
                customer_id=CUST_ID, user_id=USER_ID, now=_NOW,
            )
            row = conn.execute(
                "SELECT event_type FROM events WHERE provider_event_id = 'evt-1'"
            ).fetchone()
            assert row["event_type"] == "birthday"

    def test_cancelled_status_update(self, tmp_db):
        event = _parse_google_event(_make_raw_event())
        with get_connection() as conn:
            _upsert_event(
                conn, event, ACCT_ID, "primary",
                customer_id=CUST_ID, user_id=USER_ID, now=_NOW,
            )
            event["status"] = "cancelled"
            _upsert_event(
                conn, event, ACCT_ID, "primary",
                customer_id=CUST_ID, user_id=USER_ID, now=_NOW,
            )
            row = conn.execute("SELECT status FROM events WHERE provider_event_id = 'evt-1'").fetchone()
            assert row["status"] == "cancelled"


class TestMatchAttendees:
    def test_attendee_matching(self, tmp_db):
        with get_connection() as conn:
            contact_id = _insert_contact(conn, "Alice", "alice@example.com")
            # Insert an event
            event_id = str(uuid.uuid4())
            conn.execute(
                "INSERT INTO events (id, title, event_type, source, created_at, updated_at) "
                "VALUES (?, 'Test Event', 'meeting', 'google_calendar', ?, ?)",
                (event_id, _NOW, _NOW),
            )
            attendees = [
                {"email": "alice@example.com", "organizer": True, "responseStatus": "accepted"},
            ]
            matched = _match_attendees(conn, event_id, attendees, CUST_ID)
            assert matched == 1

            participant = conn.execute(
                "SELECT * FROM event_participants WHERE event_id = ?",
                (event_id,),
            ).fetchone()
            assert participant is not None
            assert participant["entity_id"] == contact_id
            assert participant["role"] == "organizer"
            assert participant["rsvp_status"] == "accepted"

    def test_unmatched_attendee_skipped(self, tmp_db):
        with get_connection() as conn:
            event_id = str(uuid.uuid4())
            conn.execute(
                "INSERT INTO events (id, title, event_type, source, created_at, updated_at) "
                "VALUES (?, 'Test Event', 'meeting', 'google_calendar', ?, ?)",
                (event_id, _NOW, _NOW),
            )
            attendees = [
                {"email": "unknown@nowhere.com", "responseStatus": "accepted"},
            ]
            matched = _match_attendees(conn, event_id, attendees, CUST_ID)
            assert matched == 0

    def test_attendee_rsvp_mapping(self, tmp_db):
        with get_connection() as conn:
            _insert_contact(conn, "Bob", "bob@test.com")
            event_id = str(uuid.uuid4())
            conn.execute(
                "INSERT INTO events (id, title, event_type, source, created_at, updated_at) "
                "VALUES (?, 'RSVP Event', 'meeting', 'google_calendar', ?, ?)",
                (event_id, _NOW, _NOW),
            )
            attendees = [
                {"email": "bob@test.com", "responseStatus": "tentative"},
            ]
            _match_attendees(conn, event_id, attendees, CUST_ID)
            p = conn.execute(
                "SELECT rsvp_status FROM event_participants WHERE event_id = ?",
                (event_id,),
            ).fetchone()
            assert p["rsvp_status"] == "tentative"


class TestSyncCalendarEvents:
    def _mock_fetch_events(self, events, token="new-token"):
        """Create a mock for fetch_events that returns given events."""
        return MagicMock(return_value=(events, token))

    @patch("poc.calendar_sync.fetch_events")
    def test_initial_sync_creates_events(self, mock_fetch, tmp_db):
        raw_events = [
            _parse_google_event(_make_raw_event(event_id="e1", summary="Event 1")),
            _parse_google_event(_make_raw_event(event_id="e2", summary="Event 2")),
        ]
        mock_fetch.return_value = (raw_events, "sync-tok-1")

        result = sync_calendar_events(
            ACCT_ID, MagicMock(), "primary",
            customer_id=CUST_ID, user_id=USER_ID,
        )
        assert result["events_created"] == 2
        assert result["events_updated"] == 0

        # Verify events in DB
        with get_connection() as conn:
            count = conn.execute("SELECT COUNT(*) AS cnt FROM events").fetchone()["cnt"]
            assert count == 2

    @patch("poc.calendar_sync.fetch_events")
    def test_incremental_sync_uses_token(self, mock_fetch, tmp_db):
        """First sync saves token; second sync uses it."""
        raw_events = [_parse_google_event(_make_raw_event(event_id="e1"))]
        mock_fetch.return_value = (raw_events, "tok-1")

        sync_calendar_events(
            ACCT_ID, MagicMock(), "primary",
            customer_id=CUST_ID, user_id=USER_ID,
        )

        # Second sync — should pass sync_token
        raw_events2 = [_parse_google_event(_make_raw_event(event_id="e1", summary="Updated"))]
        mock_fetch.return_value = (raw_events2, "tok-2")

        result = sync_calendar_events(
            ACCT_ID, MagicMock(), "primary",
            customer_id=CUST_ID, user_id=USER_ID,
        )
        assert result["events_updated"] == 1

        # Check that second call used sync_token
        calls = mock_fetch.call_args_list
        assert calls[1][1].get("sync_token") == "tok-1"

    @patch("poc.calendar_sync.fetch_events")
    def test_sync_token_persistence(self, mock_fetch, tmp_db):
        """Verify sync token is saved in settings."""
        from poc.settings import get_setting

        mock_fetch.return_value = ([], "saved-token")
        sync_calendar_events(
            ACCT_ID, MagicMock(), "cal-123",
            customer_id=CUST_ID, user_id=USER_ID,
        )

        token = get_setting(CUST_ID, f"cal_sync_token_{ACCT_ID}_cal-123", user_id=USER_ID)
        assert token == "saved-token"

    @patch("poc.calendar_sync.fetch_events")
    def test_sync_token_expired_falls_back(self, mock_fetch, tmp_db):
        """When sync token returns 410, falls back to full sync."""
        from poc.settings import set_setting

        # Pre-set a sync token
        set_setting(CUST_ID, f"cal_sync_token_{ACCT_ID}_cal-x", "old-token",
                    scope="user", user_id=USER_ID)

        # First call with sync_token raises SyncTokenExpiredError
        # Second call (full sync) succeeds
        events = [_parse_google_event(_make_raw_event())]
        mock_fetch.side_effect = [
            SyncTokenExpiredError("expired"),
            (events, "fresh-token"),
        ]

        result = sync_calendar_events(
            ACCT_ID, MagicMock(), "cal-x",
            customer_id=CUST_ID, user_id=USER_ID,
        )
        assert result["events_created"] == 1
        assert mock_fetch.call_count == 2


class TestSyncAllCalendars:
    @patch("poc.calendar_sync.fetch_events")
    def test_sync_all_calendars(self, mock_fetch, tmp_db):
        from poc.settings import set_setting

        # Select 2 calendars
        cal_key = f"cal_sync_calendars_{ACCT_ID}"
        set_setting(CUST_ID, cal_key, json.dumps(["cal-A", "cal-B"]),
                    scope="user", user_id=USER_ID)

        events_a = [_parse_google_event(_make_raw_event(event_id="a1"))]
        events_b = [_parse_google_event(_make_raw_event(event_id="b1"))]
        mock_fetch.side_effect = [
            (events_a, "tok-a"),
            (events_b, "tok-b"),
        ]

        result = sync_all_calendars(
            ACCT_ID, MagicMock(),
            customer_id=CUST_ID, user_id=USER_ID,
        )
        assert result["calendars_synced"] == 2
        assert result["events_created"] == 2

    def test_sync_no_calendars_selected(self, tmp_db):
        result = sync_all_calendars(
            ACCT_ID, MagicMock(),
            customer_id=CUST_ID, user_id=USER_ID,
        )
        assert result.get("error") == "No calendars selected"


# ===========================================================================
# Settings UI tests
# ===========================================================================

class TestCalendarSettings:
    def test_calendar_settings_page(self, client, tmp_db):
        resp = client.get("/settings/calendars")
        assert resp.status_code == 200
        assert "Calendar Sync" in resp.text
        assert "admin@test.com" in resp.text

    def test_calendar_selection_save(self, client, tmp_db):
        from poc.settings import get_setting

        resp = client.post(
            f"/settings/calendars/{ACCT_ID}/save",
            data={"calendar_ids": ["cal-primary", "cal-work"]},
        )
        assert resp.status_code in (200, 303)

        cal_key = f"cal_sync_calendars_{ACCT_ID}"
        saved = get_setting(CUST_ID, cal_key, user_id=USER_ID)
        assert saved is not None
        ids = json.loads(saved)
        assert "cal-primary" in ids
        assert "cal-work" in ids

    @patch("poc.calendar_client.list_calendars")
    @patch("poc.auth.get_credentials_for_account")
    def test_calendar_fetch(self, mock_creds, mock_list, client, tmp_db):
        mock_creds.return_value = MagicMock()
        mock_list.return_value = [
            {"id": "primary", "summary": "My Calendar", "primary": True,
             "accessRole": "owner", "backgroundColor": "#4285f4"},
        ]
        resp = client.post(f"/settings/calendars/{ACCT_ID}/fetch")
        assert resp.status_code == 200
        assert "My Calendar" in resp.text

    @patch("poc.calendar_client.list_calendars")
    @patch("poc.auth.get_credentials_for_account")
    def test_calendar_fetch_scope_error(self, mock_creds, mock_list, client, tmp_db):
        mock_creds.return_value = MagicMock()
        mock_list.side_effect = CalendarScopeError("Calendar scope not granted.")
        resp = client.post(f"/settings/calendars/{ACCT_ID}/fetch")
        assert resp.status_code == 200
        assert "Calendar scope not granted" in resp.text


# ===========================================================================
# Events sync route tests
# ===========================================================================

class TestEventsSyncRoute:
    def test_sync_button_rendered(self, client, tmp_db):
        resp = client.get("/events")
        assert resp.status_code == 200
        assert "Sync Events" in resp.text
        assert 'hx-post="/events/sync"' in resp.text

    @patch("poc.calendar_sync.sync_all_calendars")
    @patch("poc.auth.get_credentials_for_account")
    def test_sync_events_endpoint(self, mock_creds, mock_sync, client, tmp_db):
        mock_creds.return_value = MagicMock()
        mock_sync.return_value = {
            "events_created": 5,
            "events_updated": 2,
            "attendees_matched": 3,
            "calendars_synced": 1,
            "errors": [],
        }
        resp = client.post("/events/sync")
        assert resp.status_code == 200
        assert "5 events created" in resp.text
        assert "2 updated" in resp.text
        assert "3 attendees matched" in resp.text
        assert resp.headers.get("HX-Trigger") == "refreshEvents"

    def test_sync_no_accounts(self, client, tmp_db):
        # Remove the provider account
        with get_connection() as conn:
            conn.execute("DELETE FROM user_provider_accounts")
            conn.execute("DELETE FROM provider_accounts")
        resp = client.post("/events/sync")
        assert resp.status_code == 200
        assert "No accounts" in resp.text

    @patch("poc.calendar_sync.sync_all_calendars")
    @patch("poc.auth.get_credentials_for_account")
    def test_sync_no_calendars_selected(self, mock_creds, mock_sync, client, tmp_db):
        mock_creds.return_value = MagicMock()
        mock_sync.return_value = {"error": "No calendars selected"}
        resp = client.post("/events/sync")
        assert resp.status_code == 200
        assert "No calendars selected" in resp.text


# ===========================================================================
# Source icon filter tests
# ===========================================================================

class TestSourceIconFilter:
    def test_google_calendar_icon(self):
        from poc.web.filters import source_icon_filter
        result = str(source_icon_filter("google_calendar"))
        assert 'class="source-icon"' in result
        assert "<svg" in result
        assert ">G</text>" in result
        assert 'title="Google Calendar"' in result

    def test_google_calendar_with_account(self):
        from poc.web.filters import source_icon_filter
        result = str(source_icon_filter("google_calendar", account_name="doug@example.com"))
        assert "Google Calendar" in result
        assert "doug@example.com" in result
        assert "\u2014" in result  # em-dash separator

    def test_google_calendar_with_account_and_calendar(self):
        from poc.web.filters import source_icon_filter
        result = str(source_icon_filter(
            "google_calendar", account_name="doug@example.com", calendar_id="work",
        ))
        assert "Google Calendar" in result
        assert "doug@example.com" in result
        assert "work" in result

    def test_google_calendar_primary_calendar_omitted(self):
        from poc.web.filters import source_icon_filter
        result = str(source_icon_filter(
            "google_calendar", account_name="doug@example.com", calendar_id="primary",
        ))
        assert "primary" not in result

    def test_manual_icon(self):
        from poc.web.filters import source_icon_filter
        result = str(source_icon_filter("manual"))
        assert 'class="source-icon"' in result
        assert "<svg" in result
        assert 'title="Manually created"' in result

    def test_none_source_defaults_to_manual(self):
        from poc.web.filters import source_icon_filter
        result = str(source_icon_filter(None))
        assert 'title="Manually created"' in result

    def test_unknown_source_uses_fallback(self):
        from poc.web.filters import source_icon_filter
        result = str(source_icon_filter("outlook_calendar"))
        assert 'class="source-icon"' in result
        assert "<svg" in result
        assert 'title="outlook_calendar"' in result
        # Should NOT have the "G" text (that's google-specific)
        assert ">G</text>" not in result


# ===========================================================================
# Events grid + detail integration tests for source icon
# ===========================================================================

class TestEventsSourceIcon:
    def _insert_synced_event(self, title="Synced Meeting", calendar_id="work-cal"):
        """Insert a google_calendar event linked to the test provider account."""
        event_id = str(uuid.uuid4())
        with get_connection() as conn:
            conn.execute(
                """INSERT INTO events
                   (id, title, event_type, start_datetime, end_datetime,
                    source, account_id, provider_event_id, provider_calendar_id,
                    status, created_at, updated_at)
                   VALUES (?, ?, 'meeting', '2026-02-12T10:00:00Z', '2026-02-12T11:00:00Z',
                           'google_calendar', ?, ?, ?, 'confirmed', ?, ?)""",
                (event_id, title, ACCT_ID, f"gev-{event_id[:8]}", calendar_id, _NOW, _NOW),
            )
        return event_id

    def _insert_manual_event(self, title="Manual Event"):
        event_id = str(uuid.uuid4())
        with get_connection() as conn:
            conn.execute(
                """INSERT INTO events
                   (id, title, event_type, start_datetime, end_datetime,
                    source, status, created_by, created_at, updated_at)
                   VALUES (?, ?, 'meeting', '2026-02-12T14:00:00Z', '2026-02-12T15:00:00Z',
                           'manual', 'confirmed', ?, ?, ?)""",
                (event_id, title, USER_ID, _NOW, _NOW),
            )
        return event_id

    def test_grid_shows_google_icon_with_tooltip(self, client, tmp_db):
        self._insert_synced_event()
        resp = client.get("/events")
        assert resp.status_code == 200
        assert 'class="source-icon"' in resp.text
        assert ">G</text>" in resp.text
        # Tooltip should include account name from provider_accounts
        assert "admin@test.com" in resp.text

    def test_grid_shows_manual_icon(self, client, tmp_db):
        self._insert_manual_event()
        resp = client.get("/events")
        assert resp.status_code == 200
        assert 'title="Manually created"' in resp.text

    def test_detail_shows_google_provenance(self, client, tmp_db):
        event_id = self._insert_synced_event(calendar_id="work-cal")
        resp = client.get(f"/events/{event_id}")
        assert resp.status_code == 200
        assert "Google Calendar" in resp.text
        assert "admin@test.com" in resp.text
        assert "work-cal" in resp.text

    def test_detail_shows_manual_source(self, client, tmp_db):
        event_id = self._insert_manual_event()
        resp = client.get(f"/events/{event_id}")
        assert resp.status_code == 200
        assert "Manually created" in resp.text

    def test_detail_hides_primary_calendar(self, client, tmp_db):
        event_id = self._insert_synced_event(calendar_id="primary")
        resp = client.get(f"/events/{event_id}")
        assert resp.status_code == 200
        assert "Google Calendar" in resp.text
        # "primary" should not appear as calendar label
        assert "Calendar: primary" not in resp.text
