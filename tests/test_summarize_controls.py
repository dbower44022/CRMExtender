"""MAIL-19: summarization cost controls (settle window, per-run cap,
owner lookup, and the single pass after all accounts)."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from poc.database import get_connection, init_db
from poc.models import ConversationSummary, ConversationStatus

_NOW = datetime.now(timezone.utc)
CUST_ID = "cust-sum"
USER_ID = "user-sum"
ACCT_A = "acct-sum-a"
ACCT_B = "acct-sum-b"


@pytest.fixture()
def tmp_db(tmp_path, monkeypatch):
    db_file = tmp_path / "test.db"
    monkeypatch.setattr("poc.config.DB_PATH", db_file)
    monkeypatch.setattr("poc.config.CRM_AUTH_ENABLED", False)
    monkeypatch.setattr("poc.config.ANTHROPIC_API_KEY", "sk-test")
    init_db(db_file)
    now = _NOW.isoformat()
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO customers (id, name, slug, is_active, created_at, updated_at) "
            "VALUES (?, 'Sum Org', 'sum', 1, ?, ?)", (CUST_ID, now, now))
        conn.execute(
            "INSERT INTO users (id, customer_id, email, name, role, is_active, created_at, updated_at) "
            "VALUES (?, ?, 'owner@a.com', 'Owner', 'admin', 1, ?, ?)", (USER_ID, CUST_ID, now, now))
        for acct, email in ((ACCT_A, "owner@a.com"), (ACCT_B, "owner@b.com")):
            conn.execute(
                "INSERT INTO provider_accounts (id, customer_id, provider, email_address, "
                "auth_token_path, sync_cursor, initial_sync_done, is_active, created_at, updated_at) "
                "VALUES (?, ?, 'gmail', ?, '/tmp/t.json', 'c', 1, 1, ?, ?)", (acct, CUST_ID, email, now, now))
            conn.execute(
                "INSERT INTO user_provider_accounts (id, user_id, account_id, role, created_at) "
                "VALUES (?, ?, ?, 'owner', ?)", (str(uuid.uuid4()), USER_ID, acct, now))
    return db_file


def _conversation(account_id: str, last_activity: datetime, title: str) -> str:
    conv_id = str(uuid.uuid4())
    comm_id = str(uuid.uuid4())
    now = _NOW.isoformat()
    ts = last_activity.isoformat()
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO conversations (id, customer_id, title, status, last_activity_at, "
            "dismissed, created_at, updated_at) VALUES (?, ?, ?, 'active', ?, 0, ?, ?)",
            (conv_id, CUST_ID, title, ts, now, now))
        conn.execute(
            "INSERT INTO communications (id, account_id, channel, timestamp, original_text, "
            "sender_address, provider_message_id, provider_thread_id, created_at, updated_at) "
            "VALUES (?, ?, 'email', ?, 'body', 'x@example.com', ?, 'thr', ?, ?)",
            (comm_id, account_id, ts, f"pm-{comm_id[:8]}", now, now))
        conn.execute(
            "INSERT INTO conversation_communications (conversation_id, communication_id, created_at) "
            "VALUES (?, ?, ?)", (conv_id, comm_id, now))
    return conv_id


def _fake_summarizer(calls: list):
    def fake(conv, client, user_email, limiter=None):
        calls.append((conv.thread_id, user_email))
        return ConversationSummary(thread_id=conv.thread_id, status=ConversationStatus.UNCERTAIN,
                                   summary="s", action_items=[], key_topics=[])
    return fake


class TestProcessConversations:
    def test_settle_window_skips_active_threads(self, tmp_db, monkeypatch):
        from poc import sync
        calls: list = []
        monkeypatch.setattr(sync, "summarize_conversation", _fake_summarizer(calls))
        quiet = _conversation(ACCT_A, _NOW - timedelta(minutes=30), "quiet")
        active = _conversation(ACCT_A, _NOW - timedelta(minutes=2), "active")

        _, summarized, _ = sync.process_conversations(None, None, "owner@a.com", settle_minutes=15)
        assert summarized == 1
        assert [c[0] for c in calls] == [quiet]
        with get_connection() as conn:
            assert conn.execute("SELECT ai_summarized_at FROM conversations WHERE id = ?",
                                (active,)).fetchone()[0] is None

    def test_zero_settle_summarizes_everything(self, tmp_db, monkeypatch):
        from poc import sync
        calls: list = []
        monkeypatch.setattr(sync, "summarize_conversation", _fake_summarizer(calls))
        _conversation(ACCT_A, _NOW - timedelta(seconds=5), "fresh")
        _, summarized, _ = sync.process_conversations(None, None, "o", settle_minutes=0)
        assert summarized == 1

    def test_cap_defers_oldest_to_next_run(self, tmp_db, monkeypatch):
        from poc import sync
        calls: list = []
        monkeypatch.setattr(sync, "summarize_conversation", _fake_summarizer(calls))
        ids = [_conversation(ACCT_A, _NOW - timedelta(hours=h), f"c{h}") for h in (1, 2, 3)]

        _, summarized, _ = sync.process_conversations(None, None, "o", settle_minutes=0, max_per_run=2)
        assert summarized == 2
        assert [c[0] for c in calls] == ids[:2]          # newest first
        _, summarized, _ = sync.process_conversations(None, None, "o", settle_minutes=0, max_per_run=2)
        assert summarized == 1                           # the deferred one

    def test_owner_email_resolved_per_conversation(self, tmp_db, monkeypatch):
        from poc import sync
        calls: list = []
        monkeypatch.setattr(sync, "summarize_conversation", _fake_summarizer(calls))
        a = _conversation(ACCT_A, _NOW - timedelta(hours=1), "a")
        b = _conversation(ACCT_B, _NOW - timedelta(hours=2), "b")
        sync.process_conversations(None, None, None, settle_minutes=0)
        assert dict(calls) == {a: "owner@a.com", b: "owner@b.com"}


class TestOrchestratorOrder:
    def test_run_full_sync_summarizes_once_after_all_accounts(self, tmp_db, monkeypatch):
        """Summarization must not run between accounts (MAIL-19)."""
        from poc import sync, sync_service
        events: list = []

        monkeypatch.setattr("poc.auth.get_credentials_for_account", lambda p: object())
        monkeypatch.setattr("poc.gmail_client.get_user_email", lambda c: "x")
        monkeypatch.setattr(sync, "sync_contacts", lambda *a, **k: 0)
        monkeypatch.setattr(sync, "incremental_sync",
                            lambda account_id, *a, **k: events.append(("sync", account_id)) or {"messages_fetched": 0})
        monkeypatch.setattr(sync, "process_conversations",
                            lambda *a, **k: events.append(("summarize", k.get("max_per_run"))) or (0, 0, 0))
        monkeypatch.setattr("poc.enrichment_pipeline.enrich_new_companies", lambda: {"enriched": 0})
        monkeypatch.setattr("poc.identity_resolution.resolve_contacts_since",
                            lambda *a, **k: {"candidates_created": 0})

        sync_service.run_full_sync(customer_id=CUST_ID, user_id=USER_ID)

        assert events == [("sync", ACCT_A), ("sync", ACCT_B), ("summarize", 500)]
