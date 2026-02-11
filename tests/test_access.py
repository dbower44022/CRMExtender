"""Tests for the access control / data visibility module."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from poc.access import (
    get_my_companies,
    get_my_contacts,
    get_visible_companies,
    get_visible_contacts,
    get_visible_conversations,
)
from poc.database import get_connection, init_db

_NOW = datetime.now(timezone.utc).isoformat()


@pytest.fixture()
def tmp_db(tmp_path, monkeypatch):
    """Create a temporary database with multi-user test data."""
    db_file = tmp_path / "test.db"
    monkeypatch.setattr("poc.config.DB_PATH", db_file)
    init_db(db_file)

    with get_connection(db_file) as conn:
        # Customer
        conn.execute(
            "INSERT INTO customers (id, name, slug, is_active, created_at, updated_at) "
            "VALUES ('cust-1', 'Test Org', 'test', 1, ?, ?)",
            (_NOW, _NOW),
        )

        # Users
        for uid, email in [("user-1", "user1@test.com"), ("user-2", "user2@test.com")]:
            conn.execute(
                "INSERT INTO users "
                "(id, customer_id, email, name, role, is_active, created_at, updated_at) "
                "VALUES (?, 'cust-1', ?, ?, 'user', 1, ?, ?)",
                (uid, email, email.split("@")[0], _NOW, _NOW),
            )

        # Provider account
        conn.execute(
            "INSERT INTO provider_accounts "
            "(id, customer_id, provider, account_type, email_address, created_at, updated_at) "
            "VALUES ('acct-1', 'cust-1', 'gmail', 'email', 'user1@test.com', ?, ?)",
            (_NOW, _NOW),
        )
        conn.execute(
            "INSERT INTO user_provider_accounts (id, user_id, account_id, role, created_at) "
            "VALUES (?, 'user-1', 'acct-1', 'owner', ?)",
            (str(uuid.uuid4()), _NOW),
        )

        # Contacts
        for cid in ["c-public", "c-private-u1", "c-private-u2"]:
            conn.execute(
                "INSERT INTO contacts "
                "(id, customer_id, name, source, status, created_at, updated_at) "
                "VALUES (?, 'cust-1', ?, 'manual', 'active', ?, ?)",
                (cid, f"Contact {cid}", _NOW, _NOW),
            )

        # user_contacts
        conn.execute(
            "INSERT INTO user_contacts "
            "(id, user_id, contact_id, visibility, is_owner, created_at, updated_at) "
            "VALUES (?, 'user-1', 'c-public', 'public', 1, ?, ?)",
            (str(uuid.uuid4()), _NOW, _NOW),
        )
        conn.execute(
            "INSERT INTO user_contacts "
            "(id, user_id, contact_id, visibility, is_owner, created_at, updated_at) "
            "VALUES (?, 'user-1', 'c-private-u1', 'private', 1, ?, ?)",
            (str(uuid.uuid4()), _NOW, _NOW),
        )
        conn.execute(
            "INSERT INTO user_contacts "
            "(id, user_id, contact_id, visibility, is_owner, created_at, updated_at) "
            "VALUES (?, 'user-2', 'c-private-u2', 'private', 1, ?, ?)",
            (str(uuid.uuid4()), _NOW, _NOW),
        )

        # Companies
        for coid in ["co-public", "co-private-u1"]:
            conn.execute(
                "INSERT INTO companies "
                "(id, customer_id, name, status, created_at, updated_at) "
                "VALUES (?, 'cust-1', ?, 'active', ?, ?)",
                (coid, f"Company {coid}", _NOW, _NOW),
            )

        conn.execute(
            "INSERT INTO user_companies "
            "(id, user_id, company_id, visibility, is_owner, created_at, updated_at) "
            "VALUES (?, 'user-1', 'co-public', 'public', 1, ?, ?)",
            (str(uuid.uuid4()), _NOW, _NOW),
        )
        conn.execute(
            "INSERT INTO user_companies "
            "(id, user_id, company_id, visibility, is_owner, created_at, updated_at) "
            "VALUES (?, 'user-1', 'co-private-u1', 'private', 1, ?, ?)",
            (str(uuid.uuid4()), _NOW, _NOW),
        )

        # Conversations
        conn.execute(
            "INSERT INTO conversations "
            "(id, customer_id, title, status, communication_count, participant_count, "
            "created_at, updated_at) "
            "VALUES ('conv-1', 'cust-1', 'Shared conv', 'active', 1, 1, ?, ?)",
            (_NOW, _NOW),
        )
        conn.execute(
            "INSERT INTO conversations "
            "(id, customer_id, title, status, communication_count, participant_count, "
            "created_at, updated_at) "
            "VALUES ('conv-shared', 'cust-1', 'Explicitly shared', 'active', 0, 0, ?, ?)",
            (_NOW, _NOW),
        )

        # Communication linked to conv-1 via acct-1
        conn.execute(
            "INSERT INTO communications "
            "(id, account_id, channel, timestamp, content, sender_address, "
            "created_at, updated_at) "
            "VALUES ('comm-1', 'acct-1', 'email', ?, 'Hello', 'user1@test.com', ?, ?)",
            (_NOW, _NOW, _NOW),
        )
        conn.execute(
            "INSERT INTO conversation_communications "
            "(conversation_id, communication_id, created_at) "
            "VALUES ('conv-1', 'comm-1', ?)",
            (_NOW,),
        )

        # Share conv-shared with user-2
        conn.execute(
            "INSERT INTO conversation_shares "
            "(id, conversation_id, user_id, shared_by, created_at) "
            "VALUES (?, 'conv-shared', 'user-2', 'user-1', ?)",
            (str(uuid.uuid4()), _NOW),
        )

    return db_file


class TestVisibleContacts:
    def test_user1_sees_public_and_own_private(self, tmp_db):
        with get_connection(tmp_db) as conn:
            contacts = get_visible_contacts(conn, "cust-1", "user-1")
        names = {c["name"] for c in contacts}
        assert "Contact c-public" in names
        assert "Contact c-private-u1" in names
        assert "Contact c-private-u2" not in names

    def test_user2_sees_public_and_own_private(self, tmp_db):
        with get_connection(tmp_db) as conn:
            contacts = get_visible_contacts(conn, "cust-1", "user-2")
        names = {c["name"] for c in contacts}
        assert "Contact c-public" in names
        assert "Contact c-private-u2" in names
        assert "Contact c-private-u1" not in names


class TestMyContacts:
    def test_user1_my_contacts(self, tmp_db):
        with get_connection(tmp_db) as conn:
            contacts = get_my_contacts(conn, "cust-1", "user-1")
        names = {c["name"] for c in contacts}
        assert "Contact c-public" in names
        assert "Contact c-private-u1" in names
        assert len(contacts) == 2

    def test_user2_my_contacts(self, tmp_db):
        with get_connection(tmp_db) as conn:
            contacts = get_my_contacts(conn, "cust-1", "user-2")
        assert len(contacts) == 1
        assert contacts[0]["name"] == "Contact c-private-u2"


class TestVisibleCompanies:
    def test_user1_sees_public_and_private(self, tmp_db):
        with get_connection(tmp_db) as conn:
            companies = get_visible_companies(conn, "cust-1", "user-1")
        names = {c["name"] for c in companies}
        assert "Company co-public" in names
        assert "Company co-private-u1" in names

    def test_user2_sees_only_public(self, tmp_db):
        with get_connection(tmp_db) as conn:
            companies = get_visible_companies(conn, "cust-1", "user-2")
        names = {c["name"] for c in companies}
        assert "Company co-public" in names
        assert "Company co-private-u1" not in names


class TestMyCompanies:
    def test_user1_my_companies(self, tmp_db):
        with get_connection(tmp_db) as conn:
            companies = get_my_companies(conn, "cust-1", "user-1")
        assert len(companies) == 2

    def test_user2_has_no_companies(self, tmp_db):
        with get_connection(tmp_db) as conn:
            companies = get_my_companies(conn, "cust-1", "user-2")
        assert len(companies) == 0


class TestVisibleConversations:
    def test_user1_sees_conv_via_provider_account(self, tmp_db):
        with get_connection(tmp_db) as conn:
            convs = get_visible_conversations(conn, "cust-1", "user-1")
        ids = {c["id"] for c in convs}
        assert "conv-1" in ids

    def test_user2_sees_shared_conversation(self, tmp_db):
        with get_connection(tmp_db) as conn:
            convs = get_visible_conversations(conn, "cust-1", "user-2")
        ids = {c["id"] for c in convs}
        assert "conv-shared" in ids
        assert "conv-1" not in ids

    def test_user1_does_not_see_unshared_conv(self, tmp_db):
        with get_connection(tmp_db) as conn:
            convs = get_visible_conversations(conn, "cust-1", "user-1")
        ids = {c["id"] for c in convs}
        assert "conv-shared" not in ids
