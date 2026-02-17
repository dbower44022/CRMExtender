"""Tests for pre-filter conversation creation rules.

Verifies the three rules that determine whether a conversation is created:
  Rule 1 — Single inbound from a known, non-blocked contact → conversation
  Rule 2 — Single outbound to a known contact → conversation; unknown → no
  Rule 3 — Multi-email: user sent or known non-blocked contact → conversation

Also tests retroactive conversation creation (previously-skipped threads)
and the _is_blocked_sender helper.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from poc.database import get_connection, init_db
from poc.models import KnownContact, ParsedEmail, _now_iso
from poc.sync import _is_blocked_sender, _should_create_conversation, _store_thread

_NOW = datetime.now(timezone.utc).isoformat()
CUST_ID = "cust-test"
USER_ID = "user-admin"
ACCOUNT_ID = "acct-test"
ACCOUNT_EMAIL = "me@mycompany.com"


def _uid() -> str:
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

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
            "VALUES (?, ?, ?, 'Admin', 'admin', 1, ?, ?)",
            (USER_ID, CUST_ID, ACCOUNT_EMAIL, _NOW, _NOW),
        )
        conn.execute(
            "INSERT INTO provider_accounts "
            "(id, customer_id, provider, account_type, email_address, created_at, updated_at) "
            "VALUES (?, ?, 'gmail', 'email', ?, ?, ?)",
            (ACCOUNT_ID, CUST_ID, ACCOUNT_EMAIL, _NOW, _NOW),
        )
    return db_file


def _create_contact(name: str, email: str, *, customer_id: str = CUST_ID) -> str:
    """Insert a contact + email identifier and return contact_id."""
    cid = _uid()
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO contacts "
            "(id, customer_id, name, source, status, created_at, updated_at) "
            "VALUES (?, ?, ?, 'test', 'active', ?, ?)",
            (cid, customer_id, name, _NOW, _NOW),
        )
        conn.execute(
            "INSERT INTO contact_identifiers "
            "(id, contact_id, type, value, is_primary, created_at, updated_at) "
            "VALUES (?, ?, 'email', ?, 1, ?, ?)",
            (_uid(), cid, email.lower(), _NOW, _NOW),
        )
        conn.execute(
            "INSERT INTO user_contacts "
            "(id, user_id, contact_id, visibility, is_owner, created_at, updated_at) "
            "VALUES (?, ?, ?, 'public', 1, ?, ?)",
            (_uid(), USER_ID, cid, _NOW, _NOW),
        )
    return cid


def _make_email(
    thread_id: str,
    sender_email: str,
    recipients: list[str],
    *,
    subject: str = "Test subject",
    message_id: str | None = None,
) -> ParsedEmail:
    """Build a ParsedEmail for testing."""
    return ParsedEmail(
        message_id=message_id or _uid(),
        thread_id=thread_id,
        subject=subject,
        sender=sender_email.split("@")[0],
        sender_email=sender_email,
        recipients=recipients,
        date=datetime.now(timezone.utc),
        body_plain="Test body",
    )


def _build_contact_index() -> dict[str, KnownContact]:
    """Build contact index from the test DB (same as sync.load_contact_index)."""
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT c.*, ci.value AS email
               FROM contacts c
               JOIN contact_identifiers ci ON ci.contact_id = c.id
               WHERE ci.type = 'email'"""
        ).fetchall()
    index: dict[str, KnownContact] = {}
    for row in rows:
        r = dict(row)
        email = r["email"].lower()
        index[email] = KnownContact(
            email=email,
            name=r.get("name") or "",
            status=r.get("status") or "active",
        )
    return index


def _count_conversations(conn) -> int:
    return conn.execute("SELECT COUNT(*) as cnt FROM conversations").fetchone()["cnt"]


def _count_communications(conn) -> int:
    return conn.execute("SELECT COUNT(*) as cnt FROM communications").fetchone()["cnt"]


def _count_conv_comms(conn, conv_id: str) -> int:
    return conn.execute(
        "SELECT COUNT(*) as cnt FROM conversation_communications WHERE conversation_id = ?",
        (conv_id,),
    ).fetchone()["cnt"]


# ===================================================================
# _is_blocked_sender tests
# ===================================================================

class TestIsBlockedSender:
    def test_noreply(self):
        assert _is_blocked_sender("noreply@company.com") is True

    def test_no_reply_hyphen(self):
        assert _is_blocked_sender("no-reply@company.com") is True

    def test_notification(self):
        assert _is_blocked_sender("notification@service.com") is True

    def test_notifications(self):
        assert _is_blocked_sender("notifications@service.com") is True

    def test_billing(self):
        assert _is_blocked_sender("billing@company.com") is True

    def test_mailer_daemon(self):
        assert _is_blocked_sender("mailer-daemon@gmail.com") is True

    def test_alerts(self):
        assert _is_blocked_sender("alerts@monitoring.com") is True

    def test_normal_address(self):
        assert _is_blocked_sender("john@company.com") is False

    def test_normal_address_with_name(self):
        assert _is_blocked_sender("jane.doe@example.com") is False

    def test_case_insensitive(self):
        assert _is_blocked_sender("NoReply@Company.com") is True

    def test_donotreply(self):
        assert _is_blocked_sender("donotreply@company.com") is True

    def test_invoice(self):
        assert _is_blocked_sender("invoice@company.com") is True


# ===================================================================
# _should_create_conversation tests (unit-level, no DB)
# ===================================================================

class TestShouldCreateConversation:
    """Unit tests for the rule function using dict-based comm rows."""

    def _row(self, sender, direction, participants=None):
        return {
            "id": _uid(),
            "sender_address": sender,
            "direction": direction,
            "_participants": participants or [],
        }

    def _part(self, address, role="to"):
        return {"address": address, "role": role}

    def _index(self, *emails):
        return {e: KnownContact(email=e, name=e.split("@")[0]) for e in emails}

    def test_empty_list(self):
        assert _should_create_conversation([], ACCOUNT_EMAIL, {}) is False

    # --- Rule 1: Single inbound ---

    def test_rule1_known_contact_inbound(self):
        row = self._row("alice@acme.com", "inbound",
                        [self._part(ACCOUNT_EMAIL)])
        idx = self._index("alice@acme.com")
        assert _should_create_conversation([row], ACCOUNT_EMAIL, idx) is True

    def test_rule1_unknown_sender_inbound(self):
        row = self._row("stranger@unknown.com", "inbound",
                        [self._part(ACCOUNT_EMAIL)])
        assert _should_create_conversation([row], ACCOUNT_EMAIL, {}) is False

    def test_rule1_blocked_sender_even_if_known(self):
        row = self._row("noreply@acme.com", "inbound",
                        [self._part(ACCOUNT_EMAIL)])
        idx = self._index("noreply@acme.com")
        assert _should_create_conversation([row], ACCOUNT_EMAIL, idx) is False

    # --- Rule 2: Single outbound ---

    def test_rule2_outbound_to_known(self):
        row = self._row(ACCOUNT_EMAIL, "outbound",
                        [self._part("alice@acme.com")])
        idx = self._index("alice@acme.com")
        assert _should_create_conversation([row], ACCOUNT_EMAIL, idx) is True

    def test_rule2_outbound_to_unknown(self):
        row = self._row(ACCOUNT_EMAIL, "outbound",
                        [self._part("stranger@unknown.com")])
        assert _should_create_conversation([row], ACCOUNT_EMAIL, {}) is False

    # --- Rule 3: Multi-email ---

    def test_rule3_user_sent_one(self):
        rows = [
            self._row("stranger@unknown.com", "inbound",
                       [self._part(ACCOUNT_EMAIL)]),
            self._row(ACCOUNT_EMAIL, "outbound",
                       [self._part("stranger@unknown.com")]),
        ]
        assert _should_create_conversation(rows, ACCOUNT_EMAIL, {}) is True

    def test_rule3_no_user_no_known(self):
        rows = [
            self._row("a@unknown.com", "inbound",
                       [self._part("b@unknown.com")]),
            self._row("b@unknown.com", "inbound",
                       [self._part("a@unknown.com")]),
        ]
        assert _should_create_conversation(rows, ACCOUNT_EMAIL, {}) is False

    def test_rule3_known_contact_no_user(self):
        rows = [
            self._row("alice@acme.com", "inbound",
                       [self._part("bob@other.com")]),
            self._row("bob@other.com", "inbound",
                       [self._part("alice@acme.com")]),
        ]
        idx = self._index("alice@acme.com")
        assert _should_create_conversation(rows, ACCOUNT_EMAIL, idx) is True

    def test_rule3_blocked_contact_only(self):
        rows = [
            self._row("noreply@acme.com", "inbound",
                       [self._part("billing@other.com")]),
            self._row("billing@other.com", "inbound",
                       [self._part("noreply@acme.com")]),
        ]
        # Both participants are blocked — even if they were in the index
        idx = self._index("noreply@acme.com", "billing@other.com")
        assert _should_create_conversation(rows, ACCOUNT_EMAIL, idx) is False


# ===================================================================
# Integration tests: _store_thread with real DB
# ===================================================================

class TestStoreThreadRule1:
    """Rule 1: Single inbound email."""

    def test_known_contact_creates_conversation(self, tmp_db):
        _create_contact("Alice", "alice@acme.com")
        idx = _build_contact_index()
        thread_id = "thread-r1-known"
        emails = [_make_email(thread_id, "alice@acme.com", [ACCOUNT_EMAIL])]

        with get_connection() as conn:
            created, updated = _store_thread(
                conn, ACCOUNT_ID, ACCOUNT_EMAIL, emails, idx,
                customer_id=CUST_ID, created_by=USER_ID,
            )
            assert created is True
            assert _count_conversations(conn) == 1
            assert _count_communications(conn) == 1

    def test_unknown_sender_no_conversation(self, tmp_db):
        idx = _build_contact_index()  # empty
        thread_id = "thread-r1-unknown"
        emails = [_make_email(thread_id, "stranger@unknown.com", [ACCOUNT_EMAIL])]

        with get_connection() as conn:
            created, updated = _store_thread(
                conn, ACCOUNT_ID, ACCOUNT_EMAIL, emails, idx,
                customer_id=CUST_ID, created_by=USER_ID,
            )
            assert created is False
            assert _count_conversations(conn) == 0
            # Communication is still stored
            assert _count_communications(conn) == 1

    def test_blocked_sender_no_conversation(self, tmp_db):
        # Even if the blocked sender is a "known contact"
        _create_contact("NoReply Bot", "noreply@acme.com")
        idx = _build_contact_index()
        thread_id = "thread-r1-blocked"
        emails = [_make_email(thread_id, "noreply@acme.com", [ACCOUNT_EMAIL])]

        with get_connection() as conn:
            created, updated = _store_thread(
                conn, ACCOUNT_ID, ACCOUNT_EMAIL, emails, idx,
                customer_id=CUST_ID, created_by=USER_ID,
            )
            assert created is False
            assert _count_conversations(conn) == 0
            assert _count_communications(conn) == 1


class TestStoreThreadRule2:
    """Rule 2: Single outbound email."""

    def test_outbound_to_known_creates_conversation(self, tmp_db):
        _create_contact("Bob", "bob@partner.com")
        idx = _build_contact_index()
        thread_id = "thread-r2-known"
        emails = [_make_email(thread_id, ACCOUNT_EMAIL, ["bob@partner.com"])]

        with get_connection() as conn:
            created, updated = _store_thread(
                conn, ACCOUNT_ID, ACCOUNT_EMAIL, emails, idx,
                customer_id=CUST_ID, created_by=USER_ID,
            )
            assert created is True
            assert _count_conversations(conn) == 1

    def test_outbound_to_unknown_no_conversation(self, tmp_db):
        idx = _build_contact_index()  # empty
        thread_id = "thread-r2-unknown"
        emails = [_make_email(thread_id, ACCOUNT_EMAIL, ["stranger@unknown.com"])]

        with get_connection() as conn:
            created, updated = _store_thread(
                conn, ACCOUNT_ID, ACCOUNT_EMAIL, emails, idx,
                customer_id=CUST_ID, created_by=USER_ID,
            )
            assert created is False
            assert _count_conversations(conn) == 0
            assert _count_communications(conn) == 1


class TestStoreThreadRule3:
    """Rule 3: Multi-email threads."""

    def test_user_replied_creates_conversation(self, tmp_db):
        """Unknown sends, user replies → conversation created with both linked."""
        idx = _build_contact_index()  # empty
        thread_id = "thread-r3-reply"

        # First sync: single inbound from unknown → no conversation
        email1 = _make_email(thread_id, "stranger@unknown.com", [ACCOUNT_EMAIL],
                             message_id="msg-1")
        with get_connection() as conn:
            created, _ = _store_thread(
                conn, ACCOUNT_ID, ACCOUNT_EMAIL, [email1], idx,
                customer_id=CUST_ID, created_by=USER_ID,
            )
            assert created is False
            assert _count_conversations(conn) == 0
            assert _count_communications(conn) == 1

        # Second sync: user replies → conversation created retroactively
        email2 = _make_email(thread_id, ACCOUNT_EMAIL, ["stranger@unknown.com"],
                             message_id="msg-2")
        with get_connection() as conn:
            created, _ = _store_thread(
                conn, ACCOUNT_ID, ACCOUNT_EMAIL, [email2], idx,
                customer_id=CUST_ID, created_by=USER_ID,
            )
            assert created is True
            assert _count_conversations(conn) == 1
            assert _count_communications(conn) == 2

            # Both communications should be linked to the conversation
            conv = conn.execute("SELECT id FROM conversations").fetchone()
            linked = _count_conv_comms(conn, conv["id"])
            assert linked == 2

    def test_multi_email_all_unknown_no_user(self, tmp_db):
        """Multi-email thread, no known contacts, user never sent → no conversation."""
        idx = _build_contact_index()
        thread_id = "thread-r3-nope"
        emails = [
            _make_email(thread_id, "a@unknown.com", ["b@unknown.com"],
                        message_id="msg-a"),
            _make_email(thread_id, "b@unknown.com", ["a@unknown.com"],
                        message_id="msg-b"),
        ]

        with get_connection() as conn:
            created, _ = _store_thread(
                conn, ACCOUNT_ID, ACCOUNT_EMAIL, emails, idx,
                customer_id=CUST_ID, created_by=USER_ID,
            )
            assert created is False
            assert _count_conversations(conn) == 0
            assert _count_communications(conn) == 2

    def test_multi_email_known_contact_creates(self, tmp_db):
        """Multi-email thread with a known contact → conversation created."""
        _create_contact("Alice", "alice@acme.com")
        idx = _build_contact_index()
        thread_id = "thread-r3-known"
        emails = [
            _make_email(thread_id, "alice@acme.com", ["bob@other.com"],
                        message_id="msg-alice"),
            _make_email(thread_id, "bob@other.com", ["alice@acme.com"],
                        message_id="msg-bob"),
        ]

        with get_connection() as conn:
            created, _ = _store_thread(
                conn, ACCOUNT_ID, ACCOUNT_EMAIL, emails, idx,
                customer_id=CUST_ID, created_by=USER_ID,
            )
            assert created is True
            assert _count_conversations(conn) == 1
            assert _count_conv_comms(
                conn,
                conn.execute("SELECT id FROM conversations").fetchone()["id"],
            ) == 2


class TestStoreThreadExistingConversation:
    """When a conversation already exists, new communications are added."""

    def test_new_emails_added_to_existing(self, tmp_db):
        _create_contact("Alice", "alice@acme.com")
        idx = _build_contact_index()
        thread_id = "thread-existing"

        # First sync: creates conversation
        email1 = _make_email(thread_id, "alice@acme.com", [ACCOUNT_EMAIL],
                             message_id="msg-existing-1")
        with get_connection() as conn:
            created, _ = _store_thread(
                conn, ACCOUNT_ID, ACCOUNT_EMAIL, [email1], idx,
                customer_id=CUST_ID, created_by=USER_ID,
            )
            assert created is True
            conv_id = conn.execute("SELECT id FROM conversations").fetchone()["id"]

        # Second sync: adds another email to existing conversation
        email2 = _make_email(thread_id, ACCOUNT_EMAIL, ["alice@acme.com"],
                             message_id="msg-existing-2")
        with get_connection() as conn:
            created, updated = _store_thread(
                conn, ACCOUNT_ID, ACCOUNT_EMAIL, [email2], idx,
                customer_id=CUST_ID, created_by=USER_ID,
            )
            assert created is False
            assert updated is True
            assert _count_conversations(conn) == 1
            assert _count_conv_comms(conn, conv_id) == 2

    def test_duplicate_email_not_double_counted(self, tmp_db):
        _create_contact("Alice", "alice@acme.com")
        idx = _build_contact_index()
        thread_id = "thread-dup"
        msg_id = "msg-dup-1"

        email1 = _make_email(thread_id, "alice@acme.com", [ACCOUNT_EMAIL],
                             message_id=msg_id)
        with get_connection() as conn:
            _store_thread(conn, ACCOUNT_ID, ACCOUNT_EMAIL, [email1], idx,
                          customer_id=CUST_ID, created_by=USER_ID)

        # Same email synced again
        email1_dup = _make_email(thread_id, "alice@acme.com", [ACCOUNT_EMAIL],
                                 message_id=msg_id)
        with get_connection() as conn:
            created, updated = _store_thread(
                conn, ACCOUNT_ID, ACCOUNT_EMAIL, [email1_dup], idx,
                customer_id=CUST_ID, created_by=USER_ID,
            )
            # Conversation exists, but no new comms → not updated
            assert created is False
            assert updated is False
            assert _count_communications(conn) == 1


class TestStoreThreadEdgeCases:
    """Edge cases and special scenarios."""

    def test_empty_thread(self, tmp_db):
        idx = _build_contact_index()
        with get_connection() as conn:
            created, updated = _store_thread(
                conn, ACCOUNT_ID, ACCOUNT_EMAIL, [], idx,
                customer_id=CUST_ID, created_by=USER_ID,
            )
            assert created is False
            assert updated is False

    def test_conversation_has_correct_participant_count(self, tmp_db):
        _create_contact("Alice", "alice@acme.com")
        idx = _build_contact_index()
        thread_id = "thread-parts"
        emails = [
            _make_email(thread_id, "alice@acme.com", [ACCOUNT_EMAIL, "cc@other.com"],
                        message_id="msg-p1"),
        ]

        with get_connection() as conn:
            _store_thread(conn, ACCOUNT_ID, ACCOUNT_EMAIL, emails, idx,
                          customer_id=CUST_ID, created_by=USER_ID)
            conv = conn.execute("SELECT * FROM conversations").fetchone()
            assert conv["participant_count"] >= 2  # alice + me (cc may or may not count)

    def test_retroactive_links_all_prior_comms(self, tmp_db):
        """When Rule 3 triggers retroactively, ALL prior thread comms are linked."""
        idx = _build_contact_index()
        thread_id = "thread-retro"

        # Sync 3 inbound emails from unknown in one batch → no conversation
        emails_batch1 = [
            _make_email(thread_id, "stranger@unknown.com", [ACCOUNT_EMAIL],
                        message_id=f"msg-retro-{i}")
            for i in range(3)
        ]
        with get_connection() as conn:
            created, _ = _store_thread(
                conn, ACCOUNT_ID, ACCOUNT_EMAIL, emails_batch1, idx,
                customer_id=CUST_ID, created_by=USER_ID,
            )
            assert created is False
            assert _count_communications(conn) == 3

        # User replies → conversation created with all 4 linked
        reply = _make_email(thread_id, ACCOUNT_EMAIL, ["stranger@unknown.com"],
                            message_id="msg-retro-reply")
        with get_connection() as conn:
            created, _ = _store_thread(
                conn, ACCOUNT_ID, ACCOUNT_EMAIL, [reply], idx,
                customer_id=CUST_ID, created_by=USER_ID,
            )
            assert created is True
            conv_id = conn.execute("SELECT id FROM conversations").fetchone()["id"]
            assert _count_conv_comms(conn, conv_id) == 4

    def test_multi_account_same_thread(self, tmp_db):
        """Same thread synced from two accounts merges into one conversation."""
        _create_contact("Alice", "alice@acme.com")
        idx = _build_contact_index()
        thread_id = "thread-multi-acct"

        # Second account
        acct2_id = _uid()
        acct2_email = "other@mycompany.com"
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO provider_accounts "
                "(id, customer_id, provider, account_type, email_address, created_at, updated_at) "
                "VALUES (?, ?, 'gmail', 'email', ?, ?, ?)",
                (acct2_id, CUST_ID, acct2_email, _NOW, _NOW),
            )

        # Sync from account 1
        email1 = _make_email(thread_id, "alice@acme.com", [ACCOUNT_EMAIL],
                             message_id="msg-ma-1")
        with get_connection() as conn:
            created, _ = _store_thread(
                conn, ACCOUNT_ID, ACCOUNT_EMAIL, [email1], idx,
                customer_id=CUST_ID, created_by=USER_ID,
            )
            assert created is True

        # Sync same message from account 2 (different account_id, same thread)
        email2 = _make_email(thread_id, "alice@acme.com", [acct2_email],
                             message_id="msg-ma-2")
        with get_connection() as conn:
            created, updated = _store_thread(
                conn, acct2_id, acct2_email, [email2], idx,
                customer_id=CUST_ID, created_by=USER_ID,
            )
            # Should merge into existing conversation, not create a new one
            assert created is False
            assert updated is True
            assert _count_conversations(conn) == 1

    def test_communication_stored_even_when_no_conversation(self, tmp_db):
        """Communications are always persisted regardless of conversation rules."""
        idx = _build_contact_index()
        thread_id = "thread-no-conv"
        emails = [
            _make_email(thread_id, "stranger@unknown.com", [ACCOUNT_EMAIL],
                        message_id="msg-nc-1"),
        ]

        with get_connection() as conn:
            _store_thread(conn, ACCOUNT_ID, ACCOUNT_EMAIL, emails, idx,
                          customer_id=CUST_ID, created_by=USER_ID)
            assert _count_conversations(conn) == 0
            assert _count_communications(conn) == 1

            # Verify communication_participants also stored
            parts = conn.execute(
                "SELECT COUNT(*) as cnt FROM communication_participants"
            ).fetchone()["cnt"]
            assert parts >= 1
