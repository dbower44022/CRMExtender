"""Queued send (undo window, scheduled send), outbound attachments, and
immediate Sent-folder membership (Mail Client MAIL-35 / MAIL-36)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from poc.database import get_connection

from tests.test_outbound import ACCOUNT_ID, CUST_ID, USER_ID, tmp_db  # noqa: F401


def _draft(conn, **kw):
    from poc.outbound import create_draft
    base = dict(customer_id=CUST_ID, user_id=USER_ID, from_account_id=ACCOUNT_ID,
                to_addresses=[{"email": "bob@test.com", "name": "Bob"}], subject="Queued",
                body_json="{}", body_html="<p>Hi</p>", body_text="Hi")
    base.update(kw)
    return create_draft(conn, **base)


def _status(queue_id):
    with get_connection() as conn:
        return conn.execute("SELECT status, scheduled_send_at FROM outbound_email_queue WHERE id = ?",
                            (queue_id,)).fetchone()


class TestQueuedSend:
    def test_queue_then_undo_returns_to_draft(self, tmp_db):
        from poc.outbound import queue_send, undo_send
        when = (datetime.now(timezone.utc) + timedelta(seconds=10)).isoformat()
        with get_connection() as conn:
            d = _draft(conn)
            r = queue_send(conn, queue_id=d["id"], user_id=USER_ID, send_at=when)
        assert r["status"] == "queued"
        row = _status(d["id"])
        assert row["status"] == "queued" and row["scheduled_send_at"] == when
        with get_connection() as conn:
            assert undo_send(conn, queue_id=d["id"], user_id=USER_ID) is True
        row = _status(d["id"])
        assert row["status"] == "draft" and row["scheduled_send_at"] is None

    @patch("poc.gmail_client.send_message")
    @patch("poc.auth.get_credentials_for_account")
    def test_send_due_sends_only_past_due(self, mock_creds, mock_send, tmp_db):
        from poc.outbound import queue_send, send_due, undo_send
        mock_creds.return_value = MagicMock()
        mock_send.return_value = ("gm-1", "gt-1")
        now = datetime.now(timezone.utc)
        with get_connection() as conn:
            due = _draft(conn, subject="Due")
            later = _draft(conn, subject="Later")
            queue_send(conn, queue_id=due["id"], user_id=USER_ID, send_at=(now - timedelta(seconds=1)).isoformat())
            queue_send(conn, queue_id=later["id"], user_id=USER_ID, send_at=(now + timedelta(hours=1)).isoformat())
        with get_connection() as conn:
            results = send_due(conn, now_iso=now.isoformat())
        assert [r["queue_id"] for r in results] == [due["id"]]
        assert results[0]["status"] == "sent"
        assert _status(due["id"])["status"] == "sent"
        assert _status(later["id"])["status"] == "queued"
        # Too late to undo the one that went out
        with get_connection() as conn:
            assert undo_send(conn, queue_id=due["id"], user_id=USER_ID) is False
        assert mock_send.call_count == 1

    @patch("poc.gmail_client.send_message")
    @patch("poc.auth.get_credentials_for_account")
    def test_send_due_failure_does_not_block_others(self, mock_creds, mock_send, tmp_db):
        from poc.outbound import queue_send, send_due
        mock_creds.return_value = MagicMock()
        mock_send.side_effect = [RuntimeError("boom"), ("gm-2", "gt-2")]
        past = (datetime.now(timezone.utc) - timedelta(minutes=2))
        with get_connection() as conn:
            a = _draft(conn, subject="A")
            b = _draft(conn, subject="B")
            queue_send(conn, queue_id=a["id"], user_id=USER_ID, send_at=past.isoformat())
            queue_send(conn, queue_id=b["id"], user_id=USER_ID, send_at=(past + timedelta(seconds=1)).isoformat())
        with get_connection() as conn:
            results = send_due(conn)
        by_id = {r["queue_id"]: r["status"] for r in results}
        assert by_id[a["id"]] == "failed"
        assert by_id[b["id"]] == "sent"
        assert _status(a["id"])["status"] == "failed"

    def test_queue_rejects_other_user(self, tmp_db):
        import pytest
        from poc.outbound import queue_send
        with get_connection() as conn:
            d = _draft(conn)
            with pytest.raises(ValueError):
                queue_send(conn, queue_id=d["id"], user_id="someone-else", send_at="2030-01-01T00:00:00+00:00")


class TestOutboundAttachments:
    def test_add_list_remove(self, tmp_db, tmp_path, monkeypatch):
        from poc.outbound import add_attachment, list_attachments, remove_attachment
        monkeypatch.setattr("poc.config.UPLOAD_DIR", tmp_path / "uploads")
        with get_connection() as conn:
            d = _draft(conn)
            a = add_attachment(conn, queue_id=d["id"], user_id=USER_ID, filename="notes.txt",
                               mime_type="text/plain", data=b"hello")
            b = add_attachment(conn, queue_id=d["id"], user_id=USER_ID, filename="../evil name?.pdf",
                               mime_type="application/pdf", data=b"%PDF")
        assert a["size_bytes"] == 5
        assert "/" not in b["filename"] and "?" not in b["filename"]
        with get_connection() as conn:
            rows = list_attachments(conn, queue_id=d["id"])
            assert [r["filename"] for r in rows] == ["notes.txt", b["filename"]]
            assert remove_attachment(conn, queue_id=d["id"], user_id=USER_ID, attachment_id=a["id"]) is True
            assert remove_attachment(conn, queue_id=d["id"], user_id=USER_ID, attachment_id=a["id"]) is False
            assert [r["id"] for r in list_attachments(conn, queue_id=d["id"])] == [b["id"]]
        files = list((tmp_path / "uploads" / "outbound" / d["id"]).iterdir())
        assert len(files) == 1

    @patch("poc.gmail_client.send_message")
    @patch("poc.auth.get_credentials_for_account")
    def test_send_passes_attachments_to_adapter(self, mock_creds, mock_send, tmp_db, tmp_path, monkeypatch):
        from poc.outbound import add_attachment, send_email
        monkeypatch.setattr("poc.config.UPLOAD_DIR", tmp_path / "uploads")
        mock_creds.return_value = MagicMock()
        mock_send.return_value = ("gm-3", "gt-3")
        with get_connection() as conn:
            d = _draft(conn)
            add_attachment(conn, queue_id=d["id"], user_id=USER_ID, filename="a.txt", mime_type="text/plain", data=b"A")
            r = send_email(conn, queue_id=d["id"], user_id=USER_ID)
        assert r["status"] == "sent"
        sent = mock_send.call_args.kwargs["attachments"]
        assert sent == [{"filename": "a.txt", "mime_type": "text/plain", "data": b"A"}]

    @patch("poc.gmail_client.send_message")
    @patch("poc.auth.get_credentials_for_account")
    def test_send_without_attachments_passes_none(self, mock_creds, mock_send, tmp_db):
        from poc.outbound import send_email
        mock_creds.return_value = MagicMock()
        mock_send.return_value = ("gm-4", "gt-4")
        with get_connection() as conn:
            d = _draft(conn)
            send_email(conn, queue_id=d["id"], user_id=USER_ID)
        assert mock_send.call_args.kwargs["attachments"] is None


class TestSentFolderMembership:
    @patch("poc.gmail_client.send_message")
    @patch("poc.auth.get_credentials_for_account")
    def test_sent_message_is_labelled_sent_and_read(self, mock_creds, mock_send, tmp_db):
        from poc.outbound import send_email
        mock_creds.return_value = MagicMock()
        mock_send.return_value = ("gm-5", "gt-5")
        with get_connection() as conn:
            d = _draft(conn)
            r = send_email(conn, queue_id=d["id"], user_id=USER_ID)
        with get_connection() as conn:
            labels = conn.execute(
                "SELECT ml.provider_label_id FROM communication_labels cl "
                "JOIN mailbox_labels ml ON ml.id = cl.label_id WHERE cl.communication_id = ?",
                (r["communication_id"],)).fetchall()
            comm = conn.execute("SELECT is_read, mail_state_synced_at, provider_thread_id FROM communications WHERE id = ?",
                                (r["communication_id"],)).fetchone()
        assert [x["provider_label_id"] for x in labels] == ["SENT"]
        assert comm["is_read"] == 1
        assert comm["mail_state_synced_at"] is not None
        assert comm["provider_thread_id"] == "gt-5"
