"""Regression tests for expired Gmail history cursors.

An expired cursor (Gmail 404) must trigger a query backfill from the
last stored message — never a silent cursor advance that discards the
gap. Transient history errors must abort without moving the cursor.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from poc.database import get_connection, init_db
from poc.gmail_client import HistoryExpiredError
from poc.models import ParsedEmail

_NOW = datetime.now(timezone.utc).isoformat()

CUST_ID = "cust-backfill-test"
USER_ID = "user-backfill-test"
ACCOUNT_ID = "acct-backfill-test"


@pytest.fixture()
def tmp_db(tmp_path, monkeypatch):
    db_file = tmp_path / "test.db"
    monkeypatch.setattr("poc.config.DB_PATH", db_file)
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
            "VALUES (?, ?, 'admin@test.com', 'Admin', 'admin', 1, ?, ?)",
            (USER_ID, CUST_ID, _NOW, _NOW),
        )
        conn.execute(
            "INSERT INTO provider_accounts "
            "(id, customer_id, provider, email_address, sync_cursor, "
            " initial_sync_done, created_at, updated_at) "
            "VALUES (?, ?, 'gmail', 'owner@test.com', 'stale-cursor', 1, ?, ?)",
            (ACCOUNT_ID, CUST_ID, _NOW, _NOW),
        )
    return db_file


def _email(subject: str, ts: datetime) -> ParsedEmail:
    return ParsedEmail(
        message_id=f"msg-{uuid.uuid4().hex[:8]}",
        thread_id=f"thr-{uuid.uuid4().hex[:8]}",
        subject=subject,
        sender="Sender <sender@example.com>",
        sender_email="sender@example.com",
        recipients=["owner@test.com"],
        date=ts,
        body_plain="hello",
        snippet="hello",
    )


def _cursor() -> str:
    with get_connection() as conn:
        return conn.execute(
            "SELECT sync_cursor FROM provider_accounts WHERE id = ?",
            (ACCOUNT_ID,),
        ).fetchone()["sync_cursor"]


def _last_sync_status() -> str:
    with get_connection() as conn:
        return conn.execute(
            "SELECT status FROM sync_log WHERE account_id = ? "
            "ORDER BY started_at DESC LIMIT 1",
            (ACCOUNT_ID,),
        ).fetchone()["status"]


class TestExpiredCursorBackfill:
    def test_expired_cursor_backfills_by_query(self, tmp_db):
        """404 on history must re-fetch threads by query, then advance."""
        from poc.sync import incremental_sync

        gap_email = _email("Missed during the gap", datetime.now(timezone.utc))
        with patch("poc.sync.fetch_history", side_effect=HistoryExpiredError("expired")), \
             patch("poc.sync.fetch_threads",
                   return_value=([[gap_email]], None)) as mock_threads, \
             patch("poc.sync.get_history_id", return_value="fresh-cursor"):
            result = incremental_sync(
                ACCOUNT_ID, MagicMock(),
                customer_id=CUST_ID, user_id=USER_ID,
            )

        assert result["sync_mode"] == "backfill"
        assert result["messages_stored"] == 1
        assert _cursor() == "fresh-cursor"
        assert _last_sync_status() == "completed"

        with get_connection() as conn:
            stored = conn.execute(
                "SELECT COUNT(*) AS c FROM communications WHERE account_id = ?",
                (ACCOUNT_ID,),
            ).fetchone()["c"]
        assert stored == 1
        # No stored messages yet, so the backfill must use the account's
        # backfill query, not an after: epoch derived from nothing.
        query = mock_threads.call_args.kwargs["query"]
        assert query == "newer_than:90d"

    def test_backfill_query_starts_at_last_stored_message(self, tmp_db):
        """With stored mail, backfill queries after: the newest message."""
        from poc.sync import _store_thread, incremental_sync
        from poc.sync import load_contact_index

        last = datetime(2026, 3, 17, 21, 44, 16, tzinfo=timezone.utc)
        with get_connection() as conn:
            _store_thread(
                conn, ACCOUNT_ID, "owner@test.com",
                [_email("Old mail", last)], load_contact_index(),
                customer_id=CUST_ID, created_by=USER_ID,
            )

        with patch("poc.sync.fetch_history", side_effect=HistoryExpiredError("expired")), \
             patch("poc.sync.fetch_threads", return_value=([], None)) as mock_threads, \
             patch("poc.sync.get_history_id", return_value="fresh-cursor"):
            incremental_sync(
                ACCOUNT_ID, MagicMock(),
                customer_id=CUST_ID, user_id=USER_ID,
            )

        query = mock_threads.call_args.kwargs["query"]
        assert query.startswith("after:")
        # One-day overlap before the newest stored message.
        assert int(query.split(":")[1]) == int(last.timestamp()) - 86400

    def test_transient_history_error_keeps_cursor(self, tmp_db):
        """Non-404 failures abort the sync without advancing the cursor."""
        from poc.sync import incremental_sync

        with patch("poc.sync.fetch_history", side_effect=RuntimeError("boom")), \
             patch("poc.sync.get_history_id", return_value="fresh-cursor"):
            with pytest.raises(RuntimeError):
                incremental_sync(
                    ACCOUNT_ID, MagicMock(),
                    customer_id=CUST_ID, user_id=USER_ID,
                )

        assert _cursor() == "stale-cursor"
        assert _last_sync_status() == "failed"


class TestFetchHistoryErrorMapping:
    def _http_error(self, status: int):
        import httplib2
        from googleapiclient.errors import HttpError

        resp = httplib2.Response({"status": str(status)})
        resp.reason = "error"
        return HttpError(resp, b"error")

    def _service_raising(self, exc):
        service = MagicMock()
        service.users().history().list().execute.side_effect = exc
        return service

    def test_404_maps_to_history_expired(self):
        from poc.gmail_client import fetch_history

        with patch("poc.gmail_client.build",
                   return_value=self._service_raising(self._http_error(404))):
            with pytest.raises(HistoryExpiredError):
                fetch_history(MagicMock(), "old-cursor")

    def test_other_http_errors_propagate(self):
        from googleapiclient.errors import HttpError
        from poc.gmail_client import fetch_history

        with patch("poc.gmail_client.build",
                   return_value=self._service_raising(self._http_error(500))):
            with pytest.raises(HttpError):
                fetch_history(MagicMock(), "old-cursor")
