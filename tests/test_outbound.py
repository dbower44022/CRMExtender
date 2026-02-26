"""Tests for outbound email: draft CRUD, send flow, compose context, signatures."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from poc.database import get_connection, init_db

_NOW = datetime.now(timezone.utc).isoformat()

CUST_ID = "cust-outbound-test"
USER_ID = "user-outbound-admin"
ACCOUNT_ID = "acct-outbound-test"
ACCOUNT_EMAIL = "user@example.com"


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
            "VALUES (?, ?, 'user@example.com', 'Test User', 'admin', 1, ?, ?)",
            (USER_ID, CUST_ID, _NOW, _NOW),
        )
        conn.execute(
            "INSERT INTO provider_accounts "
            "(id, customer_id, provider, account_type, email_address, "
            "auth_token_path, is_active, created_at, updated_at) "
            "VALUES (?, ?, 'gmail', 'email', ?, '/tmp/token.json', 1, ?, ?)",
            (ACCOUNT_ID, CUST_ID, ACCOUNT_EMAIL, _NOW, _NOW),
        )
        conn.execute(
            "INSERT INTO user_provider_accounts (id, user_id, account_id, role, created_at) "
            "VALUES (?, ?, ?, 'owner', ?)",
            (str(uuid.uuid4()), USER_ID, ACCOUNT_ID, _NOW),
        )
    return db_file


def _seed_communication(conn, *, comm_id=None, subject="Test Subject",
                         sender="alice@other.com", thread_id="thread-1"):
    """Seed a communication for reply/forward testing."""
    cid = comm_id or str(uuid.uuid4())
    conn.execute(
        """INSERT INTO communications
           (id, account_id, channel, timestamp, original_text, original_html,
            cleaned_html, search_text, direction, source,
            sender_address, sender_name, subject, snippet,
            provider_message_id, provider_thread_id,
            header_message_id, header_references,
            is_read, is_current, created_at, updated_at)
           VALUES (?, ?, 'email', ?, 'Hello', '<p>Hello</p>',
                   '<p>Hello</p>', 'Hello', 'inbound', 'auto_sync',
                   ?, 'Alice', ?, 'Hello...',
                   ?, ?, '<msg-123@mail.com>', '<ref-1@mail.com>',
                   1, 1, ?, ?)""",
        (cid, ACCOUNT_ID, _NOW, sender, subject,
         f"gmail-msg-{cid}", thread_id, _NOW, _NOW),
    )
    conn.execute(
        "INSERT INTO communication_participants (communication_id, address, name, role) "
        "VALUES (?, ?, 'Test User', 'to')",
        (cid, ACCOUNT_EMAIL),
    )
    # Link to a conversation
    conv_id = str(uuid.uuid4())
    conn.execute(
        """INSERT INTO conversations
           (id, customer_id, account_id, title, subject, status,
            communication_count, message_count, participant_count,
            first_activity_at, last_activity_at, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, 'active', 1, 1, 2, ?, ?, ?, ?)""",
        (conv_id, CUST_ID, ACCOUNT_ID, subject, subject, _NOW, _NOW, _NOW, _NOW),
    )
    conn.execute(
        """INSERT INTO conversation_communications
           (conversation_id, communication_id, assignment_source, confidence, reviewed, created_at)
           VALUES (?, ?, 'sync', 1.0, 1, ?)""",
        (conv_id, cid, _NOW),
    )
    return cid, conv_id


# ---------------------------------------------------------------------------
# Draft CRUD Tests
# ---------------------------------------------------------------------------

class TestDraftCRUD:
    def test_create_draft(self, tmp_db):
        from poc.outbound import create_draft

        with get_connection() as conn:
            draft = create_draft(
                conn,
                customer_id=CUST_ID,
                user_id=USER_ID,
                from_account_id=ACCOUNT_ID,
                to_addresses=[{"email": "bob@test.com", "name": "Bob"}],
                subject="Test Draft",
                body_json="{}",
                body_html="<p>Hello</p>",
                body_text="Hello",
                source_type="manual",
            )

        assert draft is not None
        assert draft["status"] == "draft"
        assert draft["subject"] == "Test Draft"
        assert draft["to_addresses"] == [{"email": "bob@test.com", "name": "Bob"}]
        assert draft["created_by"] == USER_ID

    def test_create_draft_with_cc_bcc(self, tmp_db):
        from poc.outbound import create_draft

        with get_connection() as conn:
            draft = create_draft(
                conn,
                customer_id=CUST_ID,
                user_id=USER_ID,
                from_account_id=ACCOUNT_ID,
                to_addresses=[{"email": "bob@test.com"}],
                cc_addresses=[{"email": "cc@test.com"}],
                bcc_addresses=[{"email": "bcc@test.com"}],
                subject="CC Test",
                body_json="{}",
                body_html="<p>Hi</p>",
                body_text="Hi",
            )

        assert draft["cc_addresses"] == [{"email": "cc@test.com"}]
        assert draft["bcc_addresses"] == [{"email": "bcc@test.com"}]

    def test_update_draft(self, tmp_db):
        from poc.outbound import create_draft, update_draft

        with get_connection() as conn:
            draft = create_draft(
                conn,
                customer_id=CUST_ID,
                user_id=USER_ID,
                from_account_id=ACCOUNT_ID,
                to_addresses=[{"email": "bob@test.com"}],
                subject="Original",
                body_json="{}",
                body_html="<p>Original</p>",
                body_text="Original",
            )
            updated = update_draft(
                conn,
                draft_id=draft["id"],
                user_id=USER_ID,
                subject="Updated Subject",
                body_html="<p>Updated</p>",
                body_text="Updated",
            )

        assert updated["subject"] == "Updated Subject"
        assert updated["body_html"] == "<p>Updated</p>"

    def test_update_draft_wrong_user(self, tmp_db):
        from poc.outbound import create_draft, update_draft

        with get_connection() as conn:
            draft = create_draft(
                conn,
                customer_id=CUST_ID,
                user_id=USER_ID,
                from_account_id=ACCOUNT_ID,
                to_addresses=[{"email": "bob@test.com"}],
                subject="Test",
                body_json="{}",
                body_html="",
                body_text="",
            )
            result = update_draft(
                conn,
                draft_id=draft["id"],
                user_id="other-user",
                subject="Hacked",
            )

        assert result is None

    def test_list_drafts(self, tmp_db):
        from poc.outbound import create_draft, list_drafts

        with get_connection() as conn:
            for i in range(3):
                create_draft(
                    conn,
                    customer_id=CUST_ID,
                    user_id=USER_ID,
                    from_account_id=ACCOUNT_ID,
                    to_addresses=[{"email": f"test{i}@test.com"}],
                    subject=f"Draft {i}",
                    body_json="{}",
                    body_html="",
                    body_text="",
                )
            drafts = list_drafts(conn, user_id=USER_ID, customer_id=CUST_ID)

        assert len(drafts) == 3

    def test_cancel_draft(self, tmp_db):
        from poc.outbound import cancel_draft, create_draft, get_queue_record

        with get_connection() as conn:
            draft = create_draft(
                conn,
                customer_id=CUST_ID,
                user_id=USER_ID,
                from_account_id=ACCOUNT_ID,
                to_addresses=[{"email": "bob@test.com"}],
                subject="To Cancel",
                body_json="{}",
                body_html="",
                body_text="",
            )
            ok = cancel_draft(conn, queue_id=draft["id"], user_id=USER_ID)
            record = get_queue_record(conn, queue_id=draft["id"])

        assert ok is True
        assert record["status"] == "cancelled"

    def test_cancel_draft_wrong_user(self, tmp_db):
        from poc.outbound import cancel_draft, create_draft

        with get_connection() as conn:
            draft = create_draft(
                conn,
                customer_id=CUST_ID,
                user_id=USER_ID,
                from_account_id=ACCOUNT_ID,
                to_addresses=[{"email": "bob@test.com"}],
                subject="Test",
                body_json="{}",
                body_html="",
                body_text="",
            )
            ok = cancel_draft(conn, queue_id=draft["id"], user_id="other-user")

        assert ok is False

    def test_get_queue_record_not_found(self, tmp_db):
        from poc.outbound import get_queue_record

        with get_connection() as conn:
            result = get_queue_record(conn, queue_id="nonexistent")

        assert result is None


# ---------------------------------------------------------------------------
# Send Flow Tests
# ---------------------------------------------------------------------------

class TestSendFlow:
    @patch("poc.gmail_client.send_message")
    @patch("poc.auth.get_credentials_for_account")
    def test_send_email_creates_communication(self, mock_creds, mock_send, tmp_db):
        from poc.outbound import create_draft, send_email

        mock_creds.return_value = MagicMock()
        mock_send.return_value = ("gmail-msg-123", "gmail-thread-456")

        with get_connection() as conn:
            draft = create_draft(
                conn,
                customer_id=CUST_ID,
                user_id=USER_ID,
                from_account_id=ACCOUNT_ID,
                to_addresses=[{"email": "bob@test.com", "name": "Bob"}],
                subject="Send Test",
                body_json="{}",
                body_html="<p>Hello Bob</p>",
                body_text="Hello Bob",
            )
            result = send_email(conn, queue_id=draft["id"], user_id=USER_ID)

        assert result["status"] == "sent"
        assert result["provider_message_id"] == "gmail-msg-123"
        assert result["communication_id"] is not None

        # Verify communication record
        with get_connection() as conn:
            comm = conn.execute(
                "SELECT * FROM communications WHERE id = ?",
                (result["communication_id"],),
            ).fetchone()
            assert comm is not None
            assert comm["direction"] == "outbound"
            assert comm["source"] == "composed"
            assert comm["subject"] == "Send Test"

            # Verify participants
            parts = conn.execute(
                "SELECT * FROM communication_participants WHERE communication_id = ?",
                (result["communication_id"],),
            ).fetchall()
            assert len(parts) == 1
            assert parts[0]["address"] == "bob@test.com"
            assert parts[0]["role"] == "to"

    @patch("poc.gmail_client.send_message")
    @patch("poc.auth.get_credentials_for_account")
    def test_send_email_with_cc_bcc(self, mock_creds, mock_send, tmp_db):
        from poc.outbound import create_draft, send_email

        mock_creds.return_value = MagicMock()
        mock_send.return_value = ("msg-1", "thread-1")

        with get_connection() as conn:
            draft = create_draft(
                conn,
                customer_id=CUST_ID,
                user_id=USER_ID,
                from_account_id=ACCOUNT_ID,
                to_addresses=[{"email": "to@test.com"}],
                cc_addresses=[{"email": "cc@test.com"}],
                bcc_addresses=[{"email": "bcc@test.com"}],
                subject="CC Test",
                body_json="{}",
                body_html="<p>Hi</p>",
                body_text="Hi",
            )
            result = send_email(conn, queue_id=draft["id"], user_id=USER_ID)

        with get_connection() as conn:
            parts = conn.execute(
                "SELECT * FROM communication_participants WHERE communication_id = ? ORDER BY role",
                (result["communication_id"],),
            ).fetchall()
            roles = {p["role"] for p in parts}
            assert "to" in roles
            assert "cc" in roles
            assert "bcc" in roles

    @patch("poc.gmail_client.send_message")
    @patch("poc.auth.get_credentials_for_account")
    def test_send_failure_marks_failed(self, mock_creds, mock_send, tmp_db):
        from poc.outbound import create_draft, get_queue_record, send_email

        mock_creds.return_value = MagicMock()
        mock_send.side_effect = Exception("Gmail API error")

        with get_connection() as conn:
            draft = create_draft(
                conn,
                customer_id=CUST_ID,
                user_id=USER_ID,
                from_account_id=ACCOUNT_ID,
                to_addresses=[{"email": "bob@test.com"}],
                subject="Fail Test",
                body_json="{}",
                body_html="<p>Hi</p>",
                body_text="Hi",
            )

        with get_connection() as conn:
            result = send_email(conn, queue_id=draft["id"], user_id=USER_ID)

        assert result["status"] == "failed"
        assert "Gmail API error" in result["failure_reason"]

        with get_connection() as conn:
            record = get_queue_record(conn, queue_id=draft["id"])
            assert record["status"] == "failed"
            assert "Gmail API error" in record["failure_reason"]

    def test_send_wrong_status(self, tmp_db):
        from poc.outbound import cancel_draft, create_draft, send_email

        with get_connection() as conn:
            draft = create_draft(
                conn,
                customer_id=CUST_ID,
                user_id=USER_ID,
                from_account_id=ACCOUNT_ID,
                to_addresses=[{"email": "bob@test.com"}],
                subject="Test",
                body_json="{}",
                body_html="",
                body_text="",
            )
            cancel_draft(conn, queue_id=draft["id"], user_id=USER_ID)

        with pytest.raises(ValueError, match="Cannot send"):
            with get_connection() as conn:
                send_email(conn, queue_id=draft["id"], user_id=USER_ID)

    @patch("poc.gmail_client.send_message")
    @patch("poc.auth.get_credentials_for_account")
    def test_send_links_to_conversation(self, mock_creds, mock_send, tmp_db):
        from poc.outbound import create_draft, send_email

        mock_creds.return_value = MagicMock()
        mock_send.return_value = ("msg-conv", "thread-conv")

        with get_connection() as conn:
            comm_id, conv_id = _seed_communication(conn)
            draft = create_draft(
                conn,
                customer_id=CUST_ID,
                user_id=USER_ID,
                from_account_id=ACCOUNT_ID,
                to_addresses=[{"email": "alice@other.com"}],
                subject="Re: Test Subject",
                body_json="{}",
                body_html="<p>Reply</p>",
                body_text="Reply",
                source_type="reply",
                reply_to_communication_id=comm_id,
                conversation_id=conv_id,
            )
            result = send_email(conn, queue_id=draft["id"], user_id=USER_ID)

        # Verify linked to conversation
        with get_connection() as conn:
            cc_row = conn.execute(
                "SELECT * FROM conversation_communications WHERE communication_id = ?",
                (result["communication_id"],),
            ).fetchone()
            assert cc_row is not None
            assert cc_row["conversation_id"] == conv_id

            # Verify conversation count updated
            conv = conn.execute(
                "SELECT communication_count FROM conversations WHERE id = ?",
                (conv_id,),
            ).fetchone()
            assert conv["communication_count"] == 2


# ---------------------------------------------------------------------------
# Compose Context Tests
# ---------------------------------------------------------------------------

class TestComposeContext:
    def test_reply_context(self, tmp_db):
        from poc.outbound import get_compose_context

        with get_connection() as conn:
            comm_id, conv_id = _seed_communication(conn)
            ctx = get_compose_context(
                conn,
                communication_id=comm_id,
                action="reply",
                user_id=USER_ID,
                customer_id=CUST_ID,
            )

        assert ctx["to_addresses"] == [{"email": "alice@other.com", "name": "Alice"}]
        assert ctx["subject"].startswith("Re:")
        assert ctx["conversation_id"] == conv_id
        assert ctx["reply_to_communication_id"] == comm_id
        assert "quoted_html" in ctx

    def test_reply_all_context(self, tmp_db):
        from poc.outbound import get_compose_context

        with get_connection() as conn:
            comm_id, conv_id = _seed_communication(conn)
            # Add a CC participant
            conn.execute(
                "INSERT INTO communication_participants "
                "(communication_id, address, name, role) VALUES (?, ?, 'Carol', 'cc')",
                (comm_id, "carol@test.com"),
            )
            ctx = get_compose_context(
                conn,
                communication_id=comm_id,
                action="reply_all",
                user_id=USER_ID,
                customer_id=CUST_ID,
            )

        # Sender goes to To
        to_emails = [a["email"] for a in ctx["to_addresses"]]
        assert "alice@other.com" in to_emails
        # CC should include carol
        cc_emails = [a["email"] for a in ctx["cc_addresses"]]
        assert "carol@test.com" in cc_emails
        # Account email should NOT be in to or cc
        assert ACCOUNT_EMAIL not in to_emails
        assert ACCOUNT_EMAIL not in cc_emails

    def test_forward_context(self, tmp_db):
        from poc.outbound import get_compose_context

        with get_connection() as conn:
            comm_id, conv_id = _seed_communication(conn)
            ctx = get_compose_context(
                conn,
                communication_id=comm_id,
                action="forward",
                user_id=USER_ID,
                customer_id=CUST_ID,
            )

        assert ctx["to_addresses"] == []
        assert ctx["subject"].startswith("Fwd:")
        assert "Forwarded message" in ctx["quoted_html"]
        assert ctx["source_type"] == "forward"

    def test_reply_to_own_message(self, tmp_db):
        from poc.outbound import get_compose_context

        with get_connection() as conn:
            # Create a communication where sender is the account email
            comm_id, conv_id = _seed_communication(
                conn, sender=ACCOUNT_EMAIL, subject="My message"
            )
            # Add a 'to' participant
            conn.execute(
                "INSERT OR REPLACE INTO communication_participants "
                "(communication_id, address, name, role) VALUES (?, ?, 'Bob', 'to')",
                (comm_id, "bob@test.com"),
            )
            ctx = get_compose_context(
                conn,
                communication_id=comm_id,
                action="reply",
                user_id=USER_ID,
                customer_id=CUST_ID,
            )

        # Should reply to the 'to' recipient, not ourselves
        to_emails = [a["email"] for a in ctx["to_addresses"]]
        assert "bob@test.com" in to_emails
        assert ACCOUNT_EMAIL not in to_emails

    def test_compose_context_not_found(self, tmp_db):
        from poc.outbound import get_compose_context

        with get_connection() as conn:
            ctx = get_compose_context(
                conn,
                communication_id="nonexistent",
                action="reply",
                user_id=USER_ID,
                customer_id=CUST_ID,
            )

        assert "error" in ctx


# ---------------------------------------------------------------------------
# Sending Account Resolution Tests
# ---------------------------------------------------------------------------

class TestSendingAccountResolution:
    def test_resolve_default_account(self, tmp_db):
        from poc.outbound import resolve_sending_account

        with get_connection() as conn:
            result = resolve_sending_account(
                conn, user_id=USER_ID, customer_id=CUST_ID,
            )

        assert result == ACCOUNT_ID

    def test_resolve_reply_account(self, tmp_db):
        from poc.outbound import resolve_sending_account

        with get_connection() as conn:
            comm_id, conv_id = _seed_communication(conn)
            result = resolve_sending_account(
                conn,
                user_id=USER_ID,
                customer_id=CUST_ID,
                reply_to_comm_id=comm_id,
            )

        assert result == ACCOUNT_ID

    def test_resolve_no_accounts(self, tmp_db):
        from poc.outbound import resolve_sending_account

        other_user_id = str(uuid.uuid4())
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO users "
                "(id, customer_id, email, name, role, is_active, created_at, updated_at) "
                "VALUES (?, ?, 'other@test.com', 'Other', 'user', 1, ?, ?)",
                (other_user_id, CUST_ID, _NOW, _NOW),
            )
            result = resolve_sending_account(
                conn, user_id=other_user_id, customer_id=CUST_ID,
            )

        assert result is None


# ---------------------------------------------------------------------------
# Signature Tests
# ---------------------------------------------------------------------------

class TestSignatures:
    def test_create_signature(self, tmp_db):
        from poc.outbound import create_signature

        with get_connection() as conn:
            sig = create_signature(
                conn,
                customer_id=CUST_ID,
                user_id=USER_ID,
                name="Default Sig",
                body_json='{"type":"doc"}',
                body_html="<p>Best regards,<br>Test User</p>",
                is_default=True,
            )

        assert sig["name"] == "Default Sig"
        assert sig["is_default"] == 1

    def test_list_signatures(self, tmp_db):
        from poc.outbound import create_signature, list_signatures

        with get_connection() as conn:
            create_signature(
                conn, customer_id=CUST_ID, user_id=USER_ID,
                name="Sig A", body_json="{}", body_html="<p>A</p>",
            )
            create_signature(
                conn, customer_id=CUST_ID, user_id=USER_ID,
                name="Sig B", body_json="{}", body_html="<p>B</p>",
            )
            sigs = list_signatures(conn, user_id=USER_ID)

        assert len(sigs) == 2

    def test_update_signature(self, tmp_db):
        from poc.outbound import create_signature, update_signature

        with get_connection() as conn:
            sig = create_signature(
                conn, customer_id=CUST_ID, user_id=USER_ID,
                name="Original", body_json="{}", body_html="<p>Old</p>",
            )
            updated = update_signature(
                conn, signature_id=sig["id"], user_id=USER_ID,
                name="Updated", body_html="<p>New</p>",
            )

        assert updated["name"] == "Updated"
        assert updated["body_html"] == "<p>New</p>"

    def test_delete_signature(self, tmp_db):
        from poc.outbound import create_signature, delete_signature, get_signature

        with get_connection() as conn:
            sig = create_signature(
                conn, customer_id=CUST_ID, user_id=USER_ID,
                name="To Delete", body_json="{}", body_html="<p>X</p>",
            )
            ok = delete_signature(conn, signature_id=sig["id"], user_id=USER_ID)
            gone = get_signature(conn, signature_id=sig["id"])

        assert ok is True
        assert gone is None

    def test_default_signature_clears_previous(self, tmp_db):
        from poc.outbound import create_signature, get_signature

        with get_connection() as conn:
            sig1 = create_signature(
                conn, customer_id=CUST_ID, user_id=USER_ID,
                name="Sig 1", body_json="{}", body_html="<p>1</p>",
                is_default=True,
            )
            sig2 = create_signature(
                conn, customer_id=CUST_ID, user_id=USER_ID,
                name="Sig 2", body_json="{}", body_html="<p>2</p>",
                is_default=True,
            )
            # sig1 should no longer be default
            reloaded_1 = get_signature(conn, signature_id=sig1["id"])
            reloaded_2 = get_signature(conn, signature_id=sig2["id"])

        assert reloaded_1["is_default"] == 0
        assert reloaded_2["is_default"] == 1


# ---------------------------------------------------------------------------
# Signature Injection Tests
# ---------------------------------------------------------------------------

class TestSignatureInjection:
    @patch("poc.gmail_client.send_message")
    @patch("poc.auth.get_credentials_for_account")
    def test_explicit_signature_injected(self, mock_creds, mock_send, tmp_db):
        from poc.outbound import create_draft, create_signature, send_email

        mock_creds.return_value = MagicMock()
        mock_send.return_value = ("msg-sig", "thread-sig")

        with get_connection() as conn:
            sig = create_signature(
                conn, customer_id=CUST_ID, user_id=USER_ID,
                name="My Sig", body_json="{}",
                body_html="<p>Regards, Test</p>",
            )
            draft = create_draft(
                conn,
                customer_id=CUST_ID,
                user_id=USER_ID,
                from_account_id=ACCOUNT_ID,
                to_addresses=[{"email": "bob@test.com"}],
                subject="Sig Test",
                body_json="{}",
                body_html="<p>Body</p>",
                body_text="Body",
                signature_id=sig["id"],
            )
            send_email(conn, queue_id=draft["id"], user_id=USER_ID)

        # Check what was sent
        call_args = mock_send.call_args
        assert "Regards, Test" in call_args.kwargs.get("body_html", call_args[0][4] if len(call_args[0]) > 4 else "")

    @patch("poc.gmail_client.send_message")
    @patch("poc.auth.get_credentials_for_account")
    def test_default_signature_used_when_no_explicit(self, mock_creds, mock_send, tmp_db):
        from poc.outbound import create_draft, create_signature, send_email

        mock_creds.return_value = MagicMock()
        mock_send.return_value = ("msg-defsig", "thread-defsig")

        with get_connection() as conn:
            create_signature(
                conn, customer_id=CUST_ID, user_id=USER_ID,
                name="Default", body_json="{}",
                body_html="<p>Default Sig</p>",
                is_default=True,
            )
            draft = create_draft(
                conn,
                customer_id=CUST_ID,
                user_id=USER_ID,
                from_account_id=ACCOUNT_ID,
                to_addresses=[{"email": "bob@test.com"}],
                subject="Default Sig Test",
                body_json="{}",
                body_html="<p>Body</p>",
                body_text="Body",
                # No signature_id — should use default
            )
            send_email(conn, queue_id=draft["id"], user_id=USER_ID)

        call_args = mock_send.call_args
        sent_html = call_args.kwargs.get("body_html", "")
        assert "Default Sig" in sent_html


# ---------------------------------------------------------------------------
# Delivery Status Tests
# ---------------------------------------------------------------------------

class TestDeliveryStatus:
    def test_update_delivery_status(self, tmp_db):
        from poc.outbound import get_delivery_status, update_delivery_status

        email_addr = "bounce@test.com"
        with get_connection() as conn:
            # Create a contact with this email
            cid = str(uuid.uuid4())
            conn.execute(
                "INSERT INTO contacts (id, customer_id, name, source, status, created_at, updated_at) "
                "VALUES (?, ?, 'Bounced', 'test', 'active', ?, ?)",
                (cid, CUST_ID, _NOW, _NOW),
            )
            conn.execute(
                "INSERT INTO contact_identifiers "
                "(id, contact_id, type, value, is_primary, is_current, created_at, updated_at) "
                "VALUES (?, ?, 'email', ?, 1, 1, ?, ?)",
                (str(uuid.uuid4()), cid, email_addr, _NOW, _NOW),
            )

            ok = update_delivery_status(conn, email_address=email_addr, status="bounced")
            assert ok is True

            status = get_delivery_status(conn, email_address=email_addr)
            assert status == "bounced"

    def test_delivery_status_unknown_email(self, tmp_db):
        from poc.outbound import update_delivery_status

        with get_connection() as conn:
            ok = update_delivery_status(
                conn, email_address="nobody@test.com", status="bounced",
            )
            assert ok is False


# ---------------------------------------------------------------------------
# Contact Auto-Creation Tests
# ---------------------------------------------------------------------------

class TestContactAutoCreation:
    @patch("poc.gmail_client.send_message")
    @patch("poc.auth.get_credentials_for_account")
    def test_unknown_recipient_creates_contact(self, mock_creds, mock_send, tmp_db):
        from poc.outbound import create_draft, send_email

        mock_creds.return_value = MagicMock()
        mock_send.return_value = ("msg-auto", "thread-auto")

        unknown_email = "newperson@unknown.com"

        with get_connection() as conn:
            # Verify no contact exists
            existing = conn.execute(
                "SELECT * FROM contact_identifiers WHERE value = ?",
                (unknown_email,),
            ).fetchone()
            assert existing is None

            draft = create_draft(
                conn,
                customer_id=CUST_ID,
                user_id=USER_ID,
                from_account_id=ACCOUNT_ID,
                to_addresses=[{"email": unknown_email, "name": "New Person"}],
                subject="Auto Create Test",
                body_json="{}",
                body_html="<p>Hi</p>",
                body_text="Hi",
            )
            send_email(conn, queue_id=draft["id"], user_id=USER_ID)

        # Verify contact was created
        with get_connection() as conn:
            ident = conn.execute(
                "SELECT * FROM contact_identifiers WHERE value = ?",
                (unknown_email,),
            ).fetchone()
            assert ident is not None

            contact = conn.execute(
                "SELECT * FROM contacts WHERE id = ?",
                (ident["contact_id"],),
            ).fetchone()
            assert contact["source"] == "outbound_email"
            assert contact["name"] == "New Person"

            # Verify visibility row
            uc = conn.execute(
                "SELECT * FROM user_contacts WHERE contact_id = ?",
                (ident["contact_id"],),
            ).fetchone()
            assert uc is not None

    @patch("poc.gmail_client.send_message")
    @patch("poc.auth.get_credentials_for_account")
    def test_known_recipient_linked_not_recreated(self, mock_creds, mock_send, tmp_db):
        from poc.outbound import create_draft, send_email

        mock_creds.return_value = MagicMock()
        mock_send.return_value = ("msg-known", "thread-known")

        known_email = "known@test.com"
        known_contact_id = str(uuid.uuid4())

        with get_connection() as conn:
            conn.execute(
                "INSERT INTO contacts (id, customer_id, name, source, status, created_at, updated_at) "
                "VALUES (?, ?, 'Known Contact', 'test', 'active', ?, ?)",
                (known_contact_id, CUST_ID, _NOW, _NOW),
            )
            conn.execute(
                "INSERT INTO contact_identifiers "
                "(id, contact_id, type, value, is_primary, is_current, created_at, updated_at) "
                "VALUES (?, ?, 'email', ?, 1, 1, ?, ?)",
                (str(uuid.uuid4()), known_contact_id, known_email, _NOW, _NOW),
            )

            draft = create_draft(
                conn,
                customer_id=CUST_ID,
                user_id=USER_ID,
                from_account_id=ACCOUNT_ID,
                to_addresses=[{"email": known_email}],
                subject="Known Test",
                body_json="{}",
                body_html="<p>Hi</p>",
                body_text="Hi",
            )
            result = send_email(conn, queue_id=draft["id"], user_id=USER_ID)

        # Verify no new contact created (still just one)
        with get_connection() as conn:
            count = conn.execute(
                "SELECT COUNT(*) as cnt FROM contact_identifiers WHERE value = ?",
                (known_email,),
            ).fetchone()["cnt"]
            assert count == 1

            # Verify participant linked
            part = conn.execute(
                "SELECT * FROM communication_participants "
                "WHERE communication_id = ? AND address = ?",
                (result["communication_id"], known_email),
            ).fetchone()
            assert part["contact_id"] == known_contact_id


# ---------------------------------------------------------------------------
# Subject Prefix Tests
# ---------------------------------------------------------------------------

class TestSubjectPrefix:
    def test_adds_re_prefix(self):
        from poc.outbound import _prefix_subject
        assert _prefix_subject("Re: ", "Hello") == "Re: Hello"

    def test_no_double_re(self):
        from poc.outbound import _prefix_subject
        assert _prefix_subject("Re: ", "Re: Hello") == "Re: Hello"

    def test_adds_fwd_prefix(self):
        from poc.outbound import _prefix_subject
        assert _prefix_subject("Fwd: ", "Hello") == "Fwd: Hello"

    def test_no_double_fwd(self):
        from poc.outbound import _prefix_subject
        assert _prefix_subject("Fwd: ", "Fwd: Hello") == "Fwd: Hello"

    def test_empty_subject(self):
        from poc.outbound import _prefix_subject
        assert _prefix_subject("Re: ", "") == "Re:"
