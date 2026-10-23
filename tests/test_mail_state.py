"""Mailbox state storage (MAIL-07) and label tables (MAIL-08).

Covers MAIL-T03 (store path writes headers, flags, labels, bcc, names),
the provider-authoritative refresh of already-stored rows, label upsert
from ``list_folders``, the pre-v23 backfill job, and the reply path now
carrying In-Reply-To from stored headers (MAIL-T12, backend half).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from poc.database import get_connection, init_db
from poc.mail_state import (
    backfill_mail_state,
    ensure_labels,
    pending_backfill_count,
    refresh_labels,
    sync_mailbox_labels,
)
from poc.models import ParsedEmail
from poc.providers import Folder, FolderKind
from poc.sync import _store_thread, load_contact_index

_NOW = datetime.now(timezone.utc).isoformat()
CUST_ID = "cust-ms"
USER_ID = "user-ms"
ACCOUNT_ID = "acct-ms"
OWNER = "owner@test.com"


@pytest.fixture()
def tmp_db(tmp_path, monkeypatch):
    db_file = tmp_path / "test.db"
    monkeypatch.setattr("poc.config.DB_PATH", db_file)
    monkeypatch.setattr("poc.config.CRM_AUTH_ENABLED", False)
    init_db(db_file)
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO customers (id, name, slug, is_active, created_at, updated_at) "
            "VALUES (?, 'MS Org', 'ms', 1, ?, ?)", (CUST_ID, _NOW, _NOW))
        conn.execute(
            "INSERT INTO users (id, customer_id, email, name, role, is_active, created_at, updated_at) "
            "VALUES (?, ?, ?, 'Owner', 'admin', 1, ?, ?)", (USER_ID, CUST_ID, OWNER, _NOW, _NOW))
        conn.execute(
            "INSERT INTO provider_accounts (id, customer_id, provider, email_address, "
            "auth_token_path, sync_cursor, initial_sync_done, backfill_query, is_active, "
            "created_at, updated_at) VALUES (?, ?, 'gmail', ?, '/tmp/t.json', 'c', 1, "
            "'newer_than:90d', 1, ?, ?)", (ACCOUNT_ID, CUST_ID, OWNER, _NOW, _NOW))
    return db_file


def _email(**over) -> ParsedEmail:
    base = dict(
        message_id=f"msg-{uuid.uuid4().hex[:8]}",
        thread_id=f"thr-{uuid.uuid4().hex[:8]}",
        subject="Hello",
        sender="Ada <ada@example.com>",
        sender_email="ada@example.com",
        recipients=[OWNER, "bob@example.com"],
        cc=["dan@example.com"],
        bcc=["eve@example.com"],
        reply_to=["replies@example.com"],
        participant_names={"ada@example.com": "Ada", "bob@example.com": "Bob Builder"},
        date=datetime(2026, 3, 1, tzinfo=timezone.utc),
        body_plain="hello",
        body_html="<p>hello</p>",
        snippet="hello",
        header_message_id="<abc@example.com>",
        header_in_reply_to="<parent@example.com>",
        header_references="<root@example.com> <parent@example.com>",
        label_ids=["INBOX", "UNREAD", "Label_7"],
        is_read=False,
        is_starred=False,
    )
    base.update(over)
    return ParsedEmail(**base)


def _comm(conn, pid):
    return dict(conn.execute(
        "SELECT * FROM communications WHERE provider_message_id = ?", (pid,)).fetchone())


def _labels_of(conn, comm_id):
    return sorted(r[0] for r in conn.execute(
        "SELECT ml.provider_label_id FROM communication_labels cl "
        "JOIN mailbox_labels ml ON ml.id = cl.label_id WHERE cl.communication_id = ?",
        (comm_id,)))


class TestStorePath:
    def test_new_message_stores_headers_flags_labels_participants(self, tmp_db):
        em = _email()
        with get_connection() as conn:
            _store_thread(conn, ACCOUNT_ID, OWNER, [em], load_contact_index(),
                          customer_id=CUST_ID, created_by=USER_ID)
            row = _comm(conn, em.message_id)
            assert row["header_message_id"] == "<abc@example.com>"
            assert row["header_in_reply_to"] == "<parent@example.com>"
            assert row["header_references"] == "<root@example.com> <parent@example.com>"
            assert row["header_reply_to"] == "replies@example.com"
            assert row["is_read"] == 0 and row["is_starred"] == 0
            assert row["mail_state_synced_at"] is not None

            # UNREAD is a flag, not a membership row; the other two are rows
            assert _labels_of(conn, row["id"]) == ["INBOX", "Label_7"]
            kinds = dict(conn.execute(
                "SELECT provider_label_id, kind FROM mailbox_labels WHERE account_id = ?",
                (ACCOUNT_ID,)))
            assert kinds == {"INBOX": "inbox", "Label_7": "user"}

            parts = {(r["role"], r["address"]): r["name"] for r in conn.execute(
                "SELECT role, address, name FROM communication_participants WHERE communication_id = ?",
                (row["id"],))}
            assert parts[("to", "bob@example.com")] == "Bob Builder"
            assert parts[("to", OWNER)] is None
            assert ("bcc", "eve@example.com") in parts
            assert ("cc", "dan@example.com") in parts

    def test_reseen_message_refreshes_state_but_not_body(self, tmp_db):
        em = _email()
        with get_connection() as conn:
            _store_thread(conn, ACCOUNT_ID, OWNER, [em], load_contact_index(),
                          customer_id=CUST_ID, created_by=USER_ID)
        # Provider now says: read, starred, archived (no INBOX), new name for bob
        again = _email(message_id=em.message_id, thread_id=em.thread_id,
                       is_read=True, is_starred=True, label_ids=["STARRED", "Label_7"],
                       body_plain="DIFFERENT", body_html="<p>DIFFERENT</p>",
                       participant_names={"bob@example.com": "Robert"})
        with get_connection() as conn:
            _store_thread(conn, ACCOUNT_ID, OWNER, [again], load_contact_index(),
                          customer_id=CUST_ID, created_by=USER_ID)
            row = _comm(conn, em.message_id)
            assert row["is_read"] == 1 and row["is_starred"] == 1
            assert row["original_text"] == "hello"          # body untouched
            assert _labels_of(conn, row["id"]) == ["Label_7"]
            name = conn.execute(
                "SELECT name FROM communication_participants WHERE communication_id = ? "
                "AND address = 'bob@example.com' AND role = 'to'", (row["id"],)).fetchone()[0]
            assert name == "Robert"
            assert conn.execute("SELECT COUNT(*) FROM communications").fetchone()[0] == 1

    def test_from_row_round_trips_new_fields(self, tmp_db):
        em = _email()
        with get_connection() as conn:
            _store_thread(conn, ACCOUNT_ID, OWNER, [em], load_contact_index(),
                          customer_id=CUST_ID, created_by=USER_ID)
            row = _comm(conn, em.message_id)
            recs = [dict(r) for r in conn.execute(
                "SELECT * FROM communication_participants WHERE communication_id = ?", (row["id"],))]
        back = ParsedEmail.from_row(row, recipients=recs)
        assert back.bcc == ["eve@example.com"]
        assert back.reply_to == ["replies@example.com"]
        assert back.header_in_reply_to == "<parent@example.com>"
        assert back.is_read is False
        assert back.participant_names["bob@example.com"] == "Bob Builder"


class TestLabels:
    def test_sync_mailbox_labels_upserts_names_and_counts(self, tmp_db):
        with get_connection() as conn:
            mapping = ensure_labels(conn, ACCOUNT_ID, ["Label_7", "INBOX", "UNREAD"])
            assert set(mapping) == {"Label_7", "INBOX"}          # flag label skipped
            placeholder = conn.execute(
                "SELECT name, kind FROM mailbox_labels WHERE provider_label_id = 'Label_7'").fetchone()
            assert tuple(placeholder) == ("Label_7", "user")

            n = sync_mailbox_labels(conn, ACCOUNT_ID, [
                Folder("Label_7", "Clients/Acme", FolderKind.USER, parent_id="Clients"),
                Folder("INBOX", "INBOX", FolderKind.INBOX, unread_count=4, total_count=40),
                Folder("SENT", "SENT", FolderKind.SENT),
            ])
            assert n == 3
            rows = {r["provider_label_id"]: dict(r) for r in conn.execute(
                "SELECT * FROM mailbox_labels WHERE account_id = ?", (ACCOUNT_ID,))}
            assert rows["Label_7"]["name"] == "Clients/Acme" and rows["Label_7"]["parent_id"] == "Clients"
            assert rows["Label_7"]["id"] == mapping["Label_7"]       # same row, not a duplicate
            assert rows["INBOX"]["unread_count"] == 4 and rows["SENT"]["kind"] == "sent"

    def test_refresh_labels_swallows_provider_errors(self, tmp_db):
        provider = MagicMock()
        provider.list_folders.side_effect = RuntimeError("offline")
        assert refresh_labels({"id": ACCOUNT_ID, "email_address": OWNER}, object(), provider) == 0

    def test_refresh_labels_writes_rows(self, tmp_db):
        provider = MagicMock()
        provider.list_folders.return_value = [Folder("INBOX", "INBOX", FolderKind.INBOX)]
        assert refresh_labels({"id": ACCOUNT_ID, "email_address": OWNER}, object(), provider) == 1


class TestBackfill:
    def _legacy_rows(self, n):
        """Rows as they exist after the migration: no headers, flags 0, unsynced."""
        pids = []
        with get_connection() as conn:
            for i in range(n):
                pid = f"legacy-{i}"
                pids.append(pid)
                conn.execute(
                    "INSERT INTO communications (id, account_id, channel, timestamp, original_text, "
                    "sender_address, provider_message_id, provider_thread_id, is_read, created_at, updated_at) "
                    "VALUES (?, ?, 'email', ?, 'old body', 'ada@example.com', ?, 'thr', 0, ?, ?)",
                    (str(uuid.uuid4()), ACCOUNT_ID, _NOW, pid, _NOW, _NOW))
        return pids

    def test_backfill_updates_state_marks_missing_and_is_resumable(self, tmp_db):
        pids = self._legacy_rows(5)
        assert pending_backfill_count(ACCOUNT_ID) == 5

        def fake_fetch(session, ids, *, rate_limiter=None, metadata_only=False):
            assert metadata_only is True
            # legacy-3 is gone at the provider
            return [_email(message_id=pid, is_read=True, label_ids=["SENT"],
                           body_plain="", body_html="")
                    for pid in ids if pid != "legacy-3"]

        provider = MagicMock()
        provider.fetch_messages.side_effect = fake_fetch
        account = {"id": ACCOUNT_ID, "email_address": OWNER}

        first = backfill_mail_state(account, object(), provider, batch_size=2, limit=3)
        assert first["updated"] == 3 and first["missing"] == 0 and first["remaining"] == 2

        progress = []
        second = backfill_mail_state(account, object(), provider, batch_size=10,
                                     progress=lambda d, t: progress.append((d, t)))
        assert second == {"updated": 1, "missing": 1, "remaining": 0}
        assert progress == [(2, 2)]

        with get_connection() as conn:
            done = _comm(conn, pids[0])
            assert done["is_read"] == 1 and done["header_message_id"] == "<abc@example.com>"
            assert done["original_text"] == "old body"
            assert _labels_of(conn, done["id"]) == ["SENT"]
            gone = _comm(conn, "legacy-3")
            assert gone["mail_state_synced_at"] is not None and gone["header_message_id"] is None
        assert pending_backfill_count(ACCOUNT_ID) == 0


class TestLabelDelta:
    """MAIL-10: the engine mirrors label and flag deltas (MAIL-T04)."""

    def _stored(self, **over):
        em = _email(**over)
        with get_connection() as conn:
            _store_thread(conn, ACCOUNT_ID, OWNER, [em], load_contact_index(),
                          customer_id=CUST_ID, created_by=USER_ID)
        return em

    def test_delta_updates_labels_flags_and_trash(self, tmp_db):
        from poc.mail_state import apply_label_delta

        em = self._stored()                      # INBOX, UNREAD, Label_7; unread, unstarred
        other = self._stored(label_ids=["INBOX"], is_read=True)
        with get_connection() as conn:
            stats = apply_label_delta(
                conn, ACCOUNT_ID,
                label_changes=[
                    (em.message_id, ["STARRED", "Label_9"], ["INBOX", "UNREAD"]),
                    (other.message_id, ["TRASH"], ["INBOX"]),
                    ("not-stored", ["INBOX"], []),
                ],
                flag_changes=[
                    (em.message_id, {"is_read": True, "is_starred": True}),
                    ("not-stored", {"is_read": True}),
                ],
            )
            assert stats == {"labels_changed": 2, "flags_changed": 1, "trashed": 1,
                             "untrashed": 0, "unknown": 2}
            row = _comm(conn, em.message_id)
            assert row["is_read"] == 1 and row["is_starred"] == 1 and row["is_archived"] == 0
            assert _labels_of(conn, row["id"]) == ["Label_7", "Label_9"]   # INBOX gone, STARRED is a flag
            trashed = _comm(conn, other.message_id)
            assert trashed["is_archived"] == 1
            assert _labels_of(conn, trashed["id"]) == ["TRASH"]

            # Restoring from Trash un-archives
            apply_label_delta(conn, ACCOUNT_ID, [(other.message_id, ["INBOX"], ["TRASH"])], [])
            assert _comm(conn, other.message_id)["is_archived"] == 0
            assert _labels_of(conn, _comm(conn, other.message_id)["id"]) == ["INBOX"]

    def test_provider_deletion_archives_and_keeps_conversation(self, tmp_db):
        from poc.mail_state import archive_deleted

        em = self._stored()
        with get_connection() as conn:
            before = conn.execute("SELECT COUNT(*) FROM conversation_communications").fetchone()[0]
            assert archive_deleted(conn, ACCOUNT_ID, [em.message_id, "never-stored"]) == 1
            row = _comm(conn, em.message_id)
            assert row["is_archived"] == 1
            assert _labels_of(conn, row["id"]) == []
            assert conn.execute("SELECT COUNT(*) FROM communications").fetchone()[0] == 1
            assert conn.execute("SELECT COUNT(*) FROM conversation_communications").fetchone()[0] == before

    def _conversation_for(self, conn, comm_id: str) -> str:
        """Seed a conversation holding one communication (rules bypassed)."""
        conv_id = f"conv-{uuid.uuid4().hex[:8]}"
        now = "2026-03-01T00:00:00+00:00"
        conn.execute(
            """INSERT INTO conversations (id, customer_id, account_id, title, subject, status, communication_count,
               message_count, participant_count, first_activity_at, last_activity_at, created_at, updated_at)
               VALUES (?, ?, ?, 't', 's', 'active', 1, 1, 1, ?, ?, ?, ?)""",
            (conv_id, CUST_ID, ACCOUNT_ID, now, now, now, now))
        conn.execute(
            "INSERT INTO conversation_communications (conversation_id, communication_id, assignment_source, confidence, reviewed, created_at) "
            "VALUES (?, ?, 'sync', 1.0, 1, ?)", (conv_id, comm_id, now))
        return conv_id

    def _link_count(self, conn, conv_id: str) -> int:
        return conn.execute("SELECT COUNT(*) FROM conversation_communications WHERE conversation_id = ?", (conv_id,)).fetchone()[0]

    def test_provider_draft_is_stored_but_not_linked_and_deleted_when_dropped(self, tmp_db):
        """D-42: a Gmail draft shows in Drafts, never joins a conversation,
        and is removed (not archived) when the provider drops it."""
        from poc.mail_state import archive_deleted, is_provider_draft

        sent = self._stored(label_ids=["SENT"], is_read=True)
        with get_connection() as conn:
            conv_id = self._conversation_for(conn, _comm(conn, sent.message_id)["id"])
        draft = self._stored(message_id="draft-1", thread_id=sent.thread_id, label_ids=["DRAFT"], is_read=True)
        with get_connection() as conn:
            drow = _comm(conn, draft.message_id)
            assert is_provider_draft(conn, drow["id"]) is True
            assert _labels_of(conn, drow["id"]) == ["DRAFT"]
            assert self._link_count(conn, conv_id) == 1                 # the draft was not linked
            assert archive_deleted(conn, ACCOUNT_ID, [draft.message_id]) == 0   # removed, not archived
            assert conn.execute("SELECT COUNT(*) FROM communications WHERE provider_message_id = ?",
                                (draft.message_id,)).fetchone()[0] == 0
            assert _comm(conn, sent.message_id)["is_archived"] == 0

    def test_cleanup_provider_drafts_repairs_old_rows(self, tmp_db):
        from datetime import timedelta

        from poc.mail_state import cleanup_provider_drafts

        sent = self._stored(label_ids=["SENT"], is_read=True)
        draft = self._stored(message_id="old-draft", thread_id=sent.thread_id, label_ids=["DRAFT"], is_read=True)
        with get_connection() as conn:
            sent_id = _comm(conn, sent.message_id)["id"]
            conv_id = self._conversation_for(conn, sent_id)
            # (1) a draft linked to the conversation by the old code
            conn.execute("INSERT INTO conversation_communications (conversation_id, communication_id, assignment_source, confidence, reviewed, created_at) "
                         "VALUES (?, ?, 'sync', 1.0, 1, ?)", (conv_id, _comm(conn, draft.message_id)["id"], "2026-01-01T00:00:00+00:00"))
            # (2) an autosave remnant: outbound, no labels, 90 s before the sent message
            earlier = (sent.date - timedelta(seconds=90)).isoformat()
            conn.execute(
                """INSERT INTO communications (id, account_id, channel, timestamp, original_text, direction, source, sender_address,
                   subject, provider_message_id, provider_thread_id, is_read, is_current, mail_state_synced_at, created_at, updated_at)
                   VALUES ('remnant', ?, 'email', ?, 'Mo, why', 'outbound', 'auto_sync', ?, 's', 'pm-remnant', ?, 1, 1, ?, ?, ?)""",
                (ACCOUNT_ID, earlier, OWNER, sent.thread_id, earlier, earlier, earlier))
            conn.execute("INSERT INTO conversation_communications (conversation_id, communication_id, assignment_source, confidence, reviewed, created_at) "
                         "VALUES (?, 'remnant', 'sync', 1.0, 1, ?)", (conv_id, earlier))
            # (3) an old deleted sent message an hour before: genuine history, stays
            old = (sent.date - timedelta(hours=1)).isoformat()
            conn.execute(
                """INSERT INTO communications (id, account_id, channel, timestamp, original_text, direction, source, sender_address,
                   subject, provider_message_id, provider_thread_id, is_read, is_current, mail_state_synced_at, created_at, updated_at)
                   VALUES ('history', ?, 'email', ?, 'earlier note', 'outbound', 'auto_sync', ?, 's', 'pm-history', ?, 1, 1, ?, ?, ?)""",
                (ACCOUNT_ID, old, OWNER, sent.thread_id, old, old, old))
            conn.execute("INSERT INTO conversation_communications (conversation_id, communication_id, assignment_source, confidence, reviewed, created_at) "
                         "VALUES (?, 'history', 'sync', 1.0, 1, ?)", (conv_id, old))
            conn.execute("UPDATE conversations SET communication_count = 4, ai_summarized_at = '2026-01-01T00:00:00+00:00' WHERE id = ?", (conv_id,))
        with get_connection() as conn:
            stats = cleanup_provider_drafts(conn)
        assert stats == {"drafts_unlinked": 1, "remnants_deleted": 1, "conversations_recounted": 1}
        with get_connection() as conn:
            assert conn.execute("SELECT COUNT(*) FROM communications WHERE id = 'remnant'").fetchone()[0] == 0
            assert conn.execute("SELECT COUNT(*) FROM communications WHERE id = 'history'").fetchone()[0] == 1
            assert _comm(conn, draft.message_id) is not None                      # the draft itself stays in Drafts
            conv = conn.execute("SELECT communication_count, ai_summarized_at FROM conversations WHERE id = ?", (conv_id,)).fetchone()
            assert conv["communication_count"] == 2 and conv["ai_summarized_at"] is None
            linked = {r[0] for r in conn.execute("SELECT communication_id FROM conversation_communications WHERE conversation_id = ?", (conv_id,))}
            assert linked == {sent_id, "history"}

    def test_incremental_sync_applies_delta_end_to_end(self, tmp_db):
        """A recorded history page with label changes flows through
        incremental_sync into the mirror; deletions archive."""
        from unittest.mock import patch
        from poc.sync import incremental_sync

        em = self._stored()
        gone = self._stored(label_ids=["INBOX"], is_read=True)
        history = (
            [], [gone.message_id],
            [{"id": em.message_id, "added": ["STARRED"], "removed": ["UNREAD", "INBOX"]}],
        )
        with patch("poc.gmail_client.fetch_history", return_value=history), \
             patch("poc.gmail_client.get_history_id", return_value="h-2"):
            result = incremental_sync(ACCOUNT_ID, object(), customer_id=CUST_ID, user_id=USER_ID)

        assert result["labels_changed"] == 1 and result["flags_changed"] == 1
        assert result["messages_archived"] == 1 and result["history_id"] == "h-2"
        with get_connection() as conn:
            row = _comm(conn, em.message_id)
            assert row["is_read"] == 1 and row["is_starred"] == 1
            assert _labels_of(conn, row["id"]) == ["Label_7"]
            assert _comm(conn, gone.message_id)["is_archived"] == 1
            assert conn.execute(
                "SELECT sync_cursor FROM provider_accounts WHERE id = ?", (ACCOUNT_ID,)
            ).fetchone()[0] == "h-2"


class TestReplyThreading:
    def test_reply_to_synced_message_carries_in_reply_to(self, tmp_db, monkeypatch):
        """MAIL-T12 (backend): once headers are stored, the compose context
        for a reply exposes In-Reply-To and References."""
        from poc.outbound import get_compose_context

        em = _email()
        with get_connection() as conn:
            _store_thread(conn, ACCOUNT_ID, OWNER, [em], load_contact_index(),
                          customer_id=CUST_ID, created_by=USER_ID)
            row = _comm(conn, em.message_id)
            ctx = get_compose_context(conn, action="reply", communication_id=row["id"],
                                      user_id=USER_ID, customer_id=CUST_ID)
        assert ctx["in_reply_to"] == "<abc@example.com>"
        assert ctx["references"] == "<root@example.com> <parent@example.com>"
