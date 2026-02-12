"""Tests for Communications tab UI.

Covers: list page, search/filter, detail modal, bulk archive,
assign to conversation, delete conversation, visibility scoping.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

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
    """Create a DB with one customer, admin user, provider account, and sample data."""
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
            "(id, customer_id, provider, account_type, email_address, created_at, updated_at) "
            "VALUES (?, ?, 'google', 'email', 'admin@test.com', ?, ?)",
            (ACCT_ID, CUST_ID, _NOW, _NOW),
        )
        conn.execute(
            "INSERT INTO user_provider_accounts "
            "(id, user_id, account_id, role, created_at) "
            "VALUES (?, ?, ?, 'owner', ?)",
            (str(uuid.uuid4()), USER_ID, ACCT_ID, _NOW),
        )

    return db_file


def _insert_comm(conn, comm_id=None, subject="Test Subject",
                 channel="email", direction="inbound",
                 sender="sender@test.com", sender_name="Sender",
                 is_archived=0, account_id=ACCT_ID):
    """Insert a communication and return its ID."""
    cid = comm_id or str(uuid.uuid4())
    conn.execute(
        "INSERT INTO communications "
        "(id, account_id, channel, timestamp, subject, sender_address, "
        "sender_name, direction, is_current, is_archived, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?)",
        (cid, account_id, channel, _NOW, subject, sender,
         sender_name, direction, is_archived, _NOW, _NOW),
    )
    return cid


def _insert_conversation(conn, conv_id=None, title="Test Conversation"):
    """Insert a conversation and return its ID."""
    cid = conv_id or str(uuid.uuid4())
    conn.execute(
        "INSERT INTO conversations "
        "(id, customer_id, title, created_at, updated_at, last_activity_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (cid, CUST_ID, title, _NOW, _NOW, _NOW),
    )
    return cid


def _link_comm_to_conv(conn, comm_id, conv_id):
    """Link a communication to a conversation."""
    conn.execute(
        "INSERT INTO conversation_communications "
        "(conversation_id, communication_id, assignment_source, confidence, created_at) "
        "VALUES (?, ?, 'sync', 1.0, ?)",
        (conv_id, comm_id, _NOW),
    )


@pytest.fixture()
def client(tmp_db, monkeypatch):
    """TestClient authenticated as admin user."""
    # Reset module-level schema check flag
    import poc.web.routes.communications as comm_mod
    comm_mod._schema_checked = False

    monkeypatch.setattr(
        "poc.hierarchy.get_current_user",
        lambda: {"id": USER_ID, "email": "admin@test.com", "name": "Admin User",
                 "role": "admin", "customer_id": CUST_ID},
    )
    from poc.web.app import create_app
    app = create_app()
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# List page
# ---------------------------------------------------------------------------

class TestListPage:
    def test_list_page_loads(self, client, tmp_db):
        resp = client.get("/communications")
        assert resp.status_code == 200
        assert "Communications" in resp.text

    def test_list_page_shows_communications(self, client, tmp_db):
        with get_connection() as conn:
            _insert_comm(conn, subject="Hello World Email")
        resp = client.get("/communications")
        assert resp.status_code == 200
        assert "Hello World Email" in resp.text

    def test_list_page_hides_archived(self, client, tmp_db):
        with get_connection() as conn:
            _insert_comm(conn, subject="Visible Email")
            _insert_comm(conn, subject="Archived Email", is_archived=1)
        resp = client.get("/communications")
        assert "Visible Email" in resp.text
        assert "Archived Email" not in resp.text

    def test_list_page_hides_non_current(self, client, tmp_db):
        with get_connection() as conn:
            cid = str(uuid.uuid4())
            conn.execute(
                "INSERT INTO communications "
                "(id, account_id, channel, timestamp, subject, sender_address, "
                "direction, is_current, is_archived, created_at, updated_at) "
                "VALUES (?, ?, 'email', ?, 'Old Revision', 'x@test.com', "
                "'inbound', 0, 0, ?, ?)",
                (cid, ACCT_ID, _NOW, _NOW, _NOW),
            )
        resp = client.get("/communications")
        assert "Old Revision" not in resp.text

    def test_nav_tab_active(self, client, tmp_db):
        resp = client.get("/communications")
        assert 'class="active"' in resp.text
        assert '/communications' in resp.text


# ---------------------------------------------------------------------------
# Search and filters
# ---------------------------------------------------------------------------

class TestSearchFilter:
    def test_search_by_subject(self, client, tmp_db):
        with get_connection() as conn:
            _insert_comm(conn, subject="Important Meeting Notes")
            _insert_comm(conn, subject="Random Newsletter")
        resp = client.get("/communications/search?q=Meeting")
        assert resp.status_code == 200
        assert "Important Meeting Notes" in resp.text
        assert "Random Newsletter" not in resp.text

    def test_search_by_sender(self, client, tmp_db):
        with get_connection() as conn:
            _insert_comm(conn, subject="From Alice", sender="alice@test.com")
            _insert_comm(conn, subject="From Bob", sender="bob@test.com")
        resp = client.get("/communications/search?q=alice")
        assert "From Alice" in resp.text
        assert "From Bob" not in resp.text

    def test_filter_by_channel(self, client, tmp_db):
        with get_connection() as conn:
            _insert_comm(conn, subject="Email Msg", channel="email")
            _insert_comm(conn, subject="Phone Call", channel="phone")
        resp = client.get("/communications/search?channel=email")
        assert "Email Msg" in resp.text
        assert "Phone Call" not in resp.text

    def test_filter_by_direction(self, client, tmp_db):
        with get_connection() as conn:
            _insert_comm(conn, subject="Incoming", direction="inbound")
            _insert_comm(conn, subject="Outgoing", direction="outbound")
        resp = client.get("/communications/search?direction=outbound")
        assert "Outgoing" in resp.text
        assert "Incoming" not in resp.text

    def test_combined_filters(self, client, tmp_db):
        with get_connection() as conn:
            _insert_comm(conn, subject="Email In", channel="email", direction="inbound")
            _insert_comm(conn, subject="Email Out", channel="email", direction="outbound")
            _insert_comm(conn, subject="Phone In", channel="phone", direction="inbound")
        resp = client.get("/communications/search?channel=email&direction=inbound")
        assert "Email In" in resp.text
        assert "Email Out" not in resp.text
        assert "Phone In" not in resp.text


# ---------------------------------------------------------------------------
# Sort
# ---------------------------------------------------------------------------

class TestSort:
    def test_sort_by_subject_asc(self, client, tmp_db):
        with get_connection() as conn:
            _insert_comm(conn, subject="Zebra")
            _insert_comm(conn, subject="Apple")
        resp = client.get("/communications/search?sort=subject")
        assert resp.status_code == 200
        text = resp.text
        apple_pos = text.find("Apple")
        zebra_pos = text.find("Zebra")
        assert apple_pos < zebra_pos

    def test_sort_by_subject_desc(self, client, tmp_db):
        with get_connection() as conn:
            _insert_comm(conn, subject="Zebra")
            _insert_comm(conn, subject="Apple")
        resp = client.get("/communications/search?sort=-subject")
        text = resp.text
        apple_pos = text.find("Apple")
        zebra_pos = text.find("Zebra")
        assert zebra_pos < apple_pos


# ---------------------------------------------------------------------------
# Detail modal
# ---------------------------------------------------------------------------

class TestDetailModal:
    def test_detail_returns_content(self, client, tmp_db):
        with get_connection() as conn:
            cid = _insert_comm(conn, subject="Detail Test Email")
            # Add a recipient
            conn.execute(
                "INSERT INTO communication_participants "
                "(communication_id, address, name, role) VALUES (?, ?, ?, ?)",
                (cid, "recipient@test.com", "Recipient", "to"),
            )
        resp = client.get(f"/communications/{cid}/detail")
        assert resp.status_code == 200
        assert "Detail Test Email" in resp.text
        assert "recipient@test.com" in resp.text

    def test_detail_not_found(self, client, tmp_db):
        resp = client.get("/communications/nonexistent-id/detail")
        assert resp.status_code == 404

    def test_detail_shows_conversation_link(self, client, tmp_db):
        with get_connection() as conn:
            comm_id = _insert_comm(conn, subject="Linked Comm")
            conv_id = _insert_conversation(conn, title="Parent Conversation")
            _link_comm_to_conv(conn, comm_id, conv_id)
        resp = client.get(f"/communications/{comm_id}/detail")
        assert "Parent Conversation" in resp.text
        assert f"/conversations/{conv_id}" in resp.text


# ---------------------------------------------------------------------------
# Bulk archive
# ---------------------------------------------------------------------------

class TestBulkArchive:
    def test_archive_marks_communication(self, client, tmp_db):
        with get_connection() as conn:
            cid = _insert_comm(conn, subject="To Archive")

        resp = client.post(
            "/communications/archive",
            data={"ids": [cid]},
        )
        assert resp.status_code == 200
        # Should no longer appear in results
        assert "To Archive" not in resp.text

        # Verify DB state
        with get_connection() as conn:
            row = conn.execute(
                "SELECT is_archived FROM communications WHERE id = ?", (cid,)
            ).fetchone()
            assert row["is_archived"] == 1

    def test_archive_unlinks_from_conversation(self, client, tmp_db):
        with get_connection() as conn:
            comm_id = _insert_comm(conn, subject="Archive Unlink")
            conv_id = _insert_conversation(conn, title="Conv To Check")
            _link_comm_to_conv(conn, comm_id, conv_id)

        client.post("/communications/archive", data={"ids": [comm_id]})

        with get_connection() as conn:
            link = conn.execute(
                "SELECT COUNT(*) AS cnt FROM conversation_communications "
                "WHERE communication_id = ?",
                (comm_id,),
            ).fetchone()
            assert link["cnt"] == 0

    def test_archive_dismisses_empty_conversation(self, client, tmp_db):
        with get_connection() as conn:
            comm_id = _insert_comm(conn, subject="Only Comm")
            conv_id = _insert_conversation(conn, title="Will Be Empty")
            _link_comm_to_conv(conn, comm_id, conv_id)

        client.post("/communications/archive", data={"ids": [comm_id]})

        with get_connection() as conn:
            conv = conn.execute(
                "SELECT dismissed, dismissed_reason FROM conversations WHERE id = ?",
                (conv_id,),
            ).fetchone()
            assert conv["dismissed"] == 1
            assert conv["dismissed_reason"] == "archived"

    def test_archive_keeps_conversation_with_remaining_comms(self, client, tmp_db):
        with get_connection() as conn:
            comm1 = _insert_comm(conn, subject="Comm 1")
            comm2 = _insert_comm(conn, subject="Comm 2")
            conv_id = _insert_conversation(conn, title="Multi Comm Conv")
            _link_comm_to_conv(conn, comm1, conv_id)
            _link_comm_to_conv(conn, comm2, conv_id)

        # Only archive comm1
        client.post("/communications/archive", data={"ids": [comm1]})

        with get_connection() as conn:
            conv = conn.execute(
                "SELECT dismissed FROM conversations WHERE id = ?", (conv_id,)
            ).fetchone()
            assert conv["dismissed"] == 0


# ---------------------------------------------------------------------------
# Assign to conversation
# ---------------------------------------------------------------------------

class TestAssignToConversation:
    def test_assign_creates_link(self, client, tmp_db):
        with get_connection() as conn:
            comm_id = _insert_comm(conn, subject="To Assign")
            conv_id = _insert_conversation(conn, title="Target Conv")

        resp = client.post(
            "/communications/assign",
            data={"ids": [comm_id], "conversation_id": conv_id},
        )
        assert resp.status_code == 200

        with get_connection() as conn:
            link = conn.execute(
                "SELECT * FROM conversation_communications "
                "WHERE communication_id = ? AND conversation_id = ?",
                (comm_id, conv_id),
            ).fetchone()
            assert link is not None
            assert link["assignment_source"] == "manual"

    def test_assign_ignores_duplicate(self, client, tmp_db):
        with get_connection() as conn:
            comm_id = _insert_comm(conn, subject="Already Linked")
            conv_id = _insert_conversation(conn, title="Existing Conv")
            _link_comm_to_conv(conn, comm_id, conv_id)

        # Should not error
        resp = client.post(
            "/communications/assign",
            data={"ids": [comm_id], "conversation_id": conv_id},
        )
        assert resp.status_code == 200

    def test_conversation_search_returns_results(self, client, tmp_db):
        with get_connection() as conn:
            _insert_conversation(conn, title="Searchable Conversation")

        resp = client.get("/communications/conversations/search?q=Searchable")
        assert resp.status_code == 200
        assert "Searchable Conversation" in resp.text

    def test_conversation_search_empty_query(self, client, tmp_db):
        with get_connection() as conn:
            _insert_conversation(conn, title="Some Conversation")

        resp = client.get("/communications/conversations/search")
        assert resp.status_code == 200
        assert "Some Conversation" in resp.text


# ---------------------------------------------------------------------------
# Delete conversation
# ---------------------------------------------------------------------------

class TestDeleteConversation:
    def test_delete_conversation_only(self, client, tmp_db):
        with get_connection() as conn:
            comm_id = _insert_comm(conn, subject="Keep This Comm")
            conv_id = _insert_conversation(conn, title="Delete This Conv")
            _link_comm_to_conv(conn, comm_id, conv_id)

        resp = client.post(
            "/communications/delete-conversation",
            data={"ids": [comm_id]},
        )
        assert resp.status_code == 200

        with get_connection() as conn:
            conv = conn.execute(
                "SELECT * FROM conversations WHERE id = ?", (conv_id,)
            ).fetchone()
            assert conv is None
            # Communication still exists
            comm = conn.execute(
                "SELECT * FROM communications WHERE id = ?", (comm_id,)
            ).fetchone()
            assert comm is not None

    def test_delete_conversation_and_comms(self, client, tmp_db):
        with get_connection() as conn:
            comm_id = _insert_comm(conn, subject="Delete This Comm Too")
            conv_id = _insert_conversation(conn, title="Delete Conv And Comms")
            _link_comm_to_conv(conn, comm_id, conv_id)

        resp = client.post(
            "/communications/delete-conversation",
            data={"ids": [comm_id], "delete_comms": "true"},
        )
        assert resp.status_code == 200

        with get_connection() as conn:
            conv = conn.execute(
                "SELECT * FROM conversations WHERE id = ?", (conv_id,)
            ).fetchone()
            assert conv is None
            comm = conn.execute(
                "SELECT * FROM communications WHERE id = ?", (comm_id,)
            ).fetchone()
            assert comm is None


# ---------------------------------------------------------------------------
# Visibility / tenant scoping
# ---------------------------------------------------------------------------

class TestVisibility:
    def test_only_shows_comms_for_accessible_accounts(self, client, tmp_db):
        other_acct = str(uuid.uuid4())
        with get_connection() as conn:
            # Create another account the user does NOT have access to
            conn.execute(
                "INSERT INTO provider_accounts "
                "(id, customer_id, provider, account_type, email_address, "
                "created_at, updated_at) "
                "VALUES (?, ?, 'google', 'email', 'other@test.com', ?, ?)",
                (other_acct, CUST_ID, _NOW, _NOW),
            )
            _insert_comm(conn, subject="My Comm", account_id=ACCT_ID)
            _insert_comm(conn, subject="Other Comm", account_id=other_acct)

        resp = client.get("/communications")
        assert "My Comm" in resp.text
        assert "Other Comm" not in resp.text


# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------

class TestPagination:
    def test_pagination_limits_results(self, client, tmp_db):
        with get_connection() as conn:
            for i in range(55):
                _insert_comm(conn, subject=f"Comm {i:03d}")
        resp = client.get("/communications")
        assert resp.status_code == 200
        # Should show pagination nav
        assert "Page 1 of 2" in resp.text

    def test_page_2(self, client, tmp_db):
        with get_connection() as conn:
            for i in range(55):
                _insert_comm(conn, subject=f"Comm {i:03d}")
        resp = client.get("/communications?page=2")
        assert resp.status_code == 200
        assert "Page 2 of 2" in resp.text


# ---------------------------------------------------------------------------
# To-addresses display
# ---------------------------------------------------------------------------

class TestToAddresses:
    def test_to_addresses_shown(self, client, tmp_db):
        with get_connection() as conn:
            comm_id = _insert_comm(conn, subject="With Recipients")
            conn.execute(
                "INSERT INTO communication_participants "
                "(communication_id, address, name, role) VALUES (?, ?, ?, ?)",
                (comm_id, "to-person@test.com", "To Person", "to"),
            )
        resp = client.get("/communications")
        assert "to-person@test.com" in resp.text


# ---------------------------------------------------------------------------
# Schema migration (is_archived column)
# ---------------------------------------------------------------------------

class TestSchemaMigration:
    def test_is_archived_column_exists(self, tmp_db):
        with get_connection() as conn:
            cols = {r[1] for r in conn.execute("PRAGMA table_info(communications)")}
            assert "is_archived" in cols

    def test_is_archived_index_exists(self, tmp_db):
        with get_connection() as conn:
            indexes = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index' "
                "AND tbl_name='communications'"
            ).fetchall()
            index_names = {r["name"] for r in indexes}
            assert "idx_comm_archived" in index_names
