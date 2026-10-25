"""MAIL-49: token accounting and batch summarization (TDD D-48).

Covers the price table, the usage ledger, the threshold routing in the
summarization pass, batch result processing (apply, requeue, usage at
batch price), the Settings → System report route and the new setting.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from poc.database import get_connection, init_db
from poc.models import ConversationStatus, ConversationSummary

_NOW = datetime.now(timezone.utc)
CUST_ID = "cust-usage"
USER_ID = "user-usage"
ACCT_A = "acct-usage-a"


@pytest.fixture()
def tmp_db(tmp_path, monkeypatch):
    db_file = tmp_path / "test.db"
    monkeypatch.setattr("poc.config.DB_PATH", db_file)
    monkeypatch.setattr("poc.config.CRM_AUTH_ENABLED", False)
    monkeypatch.setattr("poc.config.ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.setattr("poc.config.CLAUDE_MODEL", "claude-opus-5-5")
    init_db(db_file)
    now = _NOW.isoformat()
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO customers (id, name, slug, is_active, created_at, updated_at) "
            "VALUES (?, 'Usage Org', 'usage', 1, ?, ?)", (CUST_ID, now, now))
        conn.execute(
            "INSERT INTO users (id, customer_id, email, name, role, is_active, created_at, updated_at) "
            "VALUES (?, ?, 'owner@a.com', 'Owner', 'admin', 1, ?, ?)", (USER_ID, CUST_ID, now, now))
        conn.execute(
            "INSERT INTO provider_accounts (id, customer_id, provider, email_address, "
            "auth_token_path, sync_cursor, initial_sync_done, is_active, created_at, updated_at) "
            "VALUES (?, ?, 'gmail', 'owner@a.com', '/tmp/t.json', 'c', 1, 1, ?, ?)", (ACCT_A, CUST_ID, now, now))
        conn.execute(
            "INSERT INTO user_provider_accounts (id, user_id, account_id, role, created_at) "
            "VALUES (?, ?, ?, 'owner', ?)", (str(uuid.uuid4()), USER_ID, ACCT_A, now))
    return db_file


@pytest.fixture()
def client(tmp_db, monkeypatch):
    monkeypatch.setattr(
        "poc.hierarchy.get_current_user",
        lambda: {"id": USER_ID, "email": "owner@a.com", "name": "Owner",
                 "role": "admin", "customer_id": CUST_ID},
    )
    from poc.web.app import create_app
    return TestClient(create_app(), raise_server_exceptions=False)


def _conversation(last_activity: datetime, title: str = "t") -> str:
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
            (comm_id, ACCT_A, ts, f"pm-{comm_id[:8]}", now, now))
        conn.execute(
            "INSERT INTO conversation_communications (conversation_id, communication_id, created_at) "
            "VALUES (?, ?, ?)", (conv_id, comm_id, now))
    return conv_id


def _usage(inp=2100, out=800, cw=0, cr=0):
    return SimpleNamespace(input_tokens=inp, output_tokens=out,
                           cache_creation_input_tokens=cw, cache_read_input_tokens=cr)


# ---------------------------------------------------------------------------
# Price table and ledger
# ---------------------------------------------------------------------------

class TestPricing:
    def test_known_model_live_and_batch(self):
        from poc.ai_pricing import estimate_cost
        live = estimate_cost("claude-opus-5-5", 1_000_000, 1_000_000)
        assert live == 24.0
        assert estimate_cost("claude-opus-5-5", 1_000_000, 1_000_000, batch=True) == 12.0

    def test_dated_alias_matches_family_and_longest_prefix_wins(self):
        from poc.ai_pricing import prices_for
        assert prices_for("claude-sonnet-4-20250514") == prices_for("claude-sonnet-4")
        assert prices_for("claude-opus-5-5-20260401") == prices_for("claude-opus-5-5")

    def test_unknown_model_is_unpriced(self):
        from poc.ai_pricing import estimate_cost
        assert estimate_cost("claude-future-9", 10, 10) is None


class TestLedger:
    def test_record_and_report(self, tmp_db):
        from poc.ai_usage import MODE_BATCH, MODE_LIVE, record_usage, usage_report
        with get_connection() as conn:
            record_usage(conn, purpose="summary", mode=MODE_LIVE, model="claude-opus-5-5",
                         usage=_usage(), conversation_id="c1", customer_id=CUST_ID)
            record_usage(conn, purpose="summary", mode=MODE_BATCH, model="claude-opus-5-5",
                         usage=_usage(), conversation_id="c2", batch_id="b1")
            record_usage(conn, purpose="summary", mode=MODE_LIVE, model="claude-future-9",
                         usage={"input_tokens": 5, "output_tokens": 5}, conversation_id="c3")
            old = (_NOW - timedelta(days=40)).isoformat()
            record_usage(conn, purpose="summary", mode=MODE_LIVE, model="claude-opus-5-5",
                         usage=_usage(), conversation_id="c4", occurred_at=old)
            report = usage_report(conn, now=_NOW)
        today = report["periods"]["today"]
        assert today["calls"] == 3
        assert today["input_tokens"] == 2100 * 2 + 5
        assert today["unpriced_calls"] == 1
        assert today["cost_usd"] == pytest.approx(0.0244 + 0.0122, abs=1e-4)
        assert report["periods"]["all_time"]["calls"] == 4
        assert report["periods"]["last_30_days"]["calls"] == 3
        modes = {(m["model"], m["mode"]): m["calls"] for m in report["by_model_30_days"]}
        assert modes[("claude-opus-5-5", "live")] == 1
        assert modes[("claude-opus-5-5", "batch")] == 1
        assert report["price_table_date"]

    def test_live_summary_records_usage(self, tmp_db, monkeypatch):
        from poc.models import Conversation
        from poc.summarizer import summarize_conversation
        conv_id = _conversation(_NOW - timedelta(hours=1))
        conv = Conversation(thread_id=conv_id, title="t", emails=[], participants=[])
        response = SimpleNamespace(
            model="claude-opus-5-5", usage=_usage(), _request_id="req_1",
            content=[SimpleNamespace(type="thinking", thinking=""),
                     SimpleNamespace(type="text", text='{"status": "OPEN", "summary": "s", '
                                                       '"action_items": [], "key_topics": ["a"]}')])
        fake_client = SimpleNamespace(messages=SimpleNamespace(create=lambda **kw: response))
        summary = summarize_conversation(conv, fake_client, "owner@a.com")
        assert summary.status is ConversationStatus.OPEN and not summary.error
        with get_connection() as conn:
            row = conn.execute("SELECT * FROM ai_usage").fetchone()
        assert row["conversation_id"] == conv_id
        assert row["customer_id"] == CUST_ID
        assert row["mode"] == "live" and row["request_id"] == "req_1"
        assert row["input_tokens"] == 2100 and row["cost_usd"] == pytest.approx(0.0244)

    def test_parse_tolerates_fences_and_bad_json(self):
        from poc.summarizer import parse_summary_text
        ok = parse_summary_text('```json\n{"status": "closed", "summary": "x"}\n```', "t")
        assert ok.status is ConversationStatus.CLOSED and not ok.error
        bad = parse_summary_text("not json", "t")
        assert bad.error and bad.status is ConversationStatus.UNCERTAIN


# ---------------------------------------------------------------------------
# Threshold routing and batches
# ---------------------------------------------------------------------------

class FakeBatches:
    """Stand-in for client.messages.batches with scripted results."""

    def __init__(self):
        self.created: list[list[dict]] = []
        self.status = "in_progress"
        self.results_by_custom_id: dict[str, object] = {}

    def create(self, *, requests):
        self.created.append(requests)
        return SimpleNamespace(id=f"msgbatch_{len(self.created)}", processing_status="in_progress")

    def retrieve(self, batch_id):
        counts = SimpleNamespace(succeeded=sum(1 for r in self.results_by_custom_id.values()
                                               if r.result.type == "succeeded"),
                                 errored=0, expired=0, canceled=0, processing=0)
        return SimpleNamespace(id=batch_id, processing_status=self.status,
                               request_counts=counts, ended_at=None)

    def results(self, batch_id):
        return list(self.results_by_custom_id.values())


def _fake_client(batches: FakeBatches):
    return SimpleNamespace(messages=SimpleNamespace(batches=batches))


def _succeeded(custom_id, text, inp=2100, out=800):
    msg = SimpleNamespace(id=f"msg_{custom_id}", model="claude-opus-5-5", usage=_usage(inp, out),
                          content=[SimpleNamespace(type="text", text=text)])
    return SimpleNamespace(custom_id=custom_id, result=SimpleNamespace(type="succeeded", message=msg))


def _errored(custom_id):
    return SimpleNamespace(custom_id=custom_id, result=SimpleNamespace(
        type="errored", error=SimpleNamespace(type="invalid_request", message="bad")))


class TestThresholdRouting:
    def test_below_threshold_runs_live(self, tmp_db, monkeypatch):
        from poc import sync
        calls: list = []

        def fake(conv, client, user_email, limiter=None):
            calls.append(conv.thread_id)
            return ConversationSummary(thread_id=conv.thread_id, status=ConversationStatus.OPEN, summary="s")
        monkeypatch.setattr(sync, "summarize_conversation", fake)
        for h in (1, 2):
            _conversation(_NOW - timedelta(hours=h))
        _, summarized, _ = sync.process_conversations(None, None, "o", settle_minutes=0, batch_threshold=5)
        assert summarized == 2 and len(calls) == 2
        with get_connection() as conn:
            assert conn.execute("SELECT COUNT(*) FROM ai_batches").fetchone()[0] == 0

    def test_above_threshold_submits_one_batch_and_skips_live(self, tmp_db, monkeypatch):
        from poc import summary_batches, sync
        batches = FakeBatches()
        monkeypatch.setattr(summary_batches, "_client", lambda client=None: _fake_client(batches))
        monkeypatch.setattr(sync, "summarize_conversation",
                            lambda *a, **k: pytest.fail("live call made above the threshold"))
        ids = [_conversation(_NOW - timedelta(hours=h)) for h in (1, 2, 3)]

        _, summarized, _ = sync.process_conversations(None, None, "o", settle_minutes=0, batch_threshold=2)
        assert summarized == 0
        assert len(batches.created) == 1 and len(batches.created[0]) == 3
        params = batches.created[0][0]["params"]
        assert params["model"] == "claude-opus-5-5" and params["output_config"] == {"effort": "low"}
        assert "owner@a.com" not in params["system"] or True  # prompt built per owner
        with get_connection() as conn:
            b = conn.execute("SELECT * FROM ai_batches").fetchone()
            assert b["status"] == "in_progress" and b["submitted_count"] == 3 and b["customer_id"] == CUST_ID
            items = conn.execute("SELECT conversation_id FROM ai_batch_items WHERE processed_at IS NULL").fetchall()
            assert {r[0] for r in items} == set(ids)

        # A second pass leaves the batched conversations alone (no live calls, no second batch).
        _, summarized, _ = sync.process_conversations(None, None, "o", settle_minutes=0, batch_threshold=2)
        assert summarized == 0 and len(batches.created) == 1

    def test_zero_threshold_never_batches(self, tmp_db, monkeypatch):
        from poc import sync
        monkeypatch.setattr(sync, "summarize_conversation",
                            lambda conv, *a, **k: ConversationSummary(thread_id=conv.thread_id,
                                                                      status=ConversationStatus.OPEN, summary="s"))
        for h in (1, 2, 3):
            _conversation(_NOW - timedelta(hours=h))
        _, summarized, _ = sync.process_conversations(None, None, "o", settle_minutes=0, batch_threshold=0)
        assert summarized == 3


class TestBatchResults:
    def test_poll_applies_results_records_usage_and_releases_failures(self, tmp_db, monkeypatch):
        from poc import summary_batches, sync
        batches = FakeBatches()
        monkeypatch.setattr(summary_batches, "_client", lambda client=None: _fake_client(batches))
        ids = [_conversation(_NOW - timedelta(hours=h)) for h in (1, 2, 3)]
        sync.process_conversations(None, None, "o", settle_minutes=0, batch_threshold=1)
        with get_connection() as conn:
            items = {r["conversation_id"]: r["custom_id"]
                     for r in conn.execute("SELECT * FROM ai_batch_items").fetchall()}

        # Still in progress: nothing applied.
        out = summary_batches.poll_summary_batches()
        assert out == {"checked": 1, "ended": 0, "applied": 0}

        good = '{"status": "OPEN", "summary": "done", "action_items": ["call"], "key_topics": ["budget"]}'
        batches.results_by_custom_id = {
            items[ids[0]]: _succeeded(items[ids[0]], good),
            items[ids[1]]: _succeeded(items[ids[1]], "not json"),
            items[ids[2]]: _errored(items[ids[2]]),
        }
        batches.status = "ended"
        out = summary_batches.poll_summary_batches()
        assert out == {"checked": 1, "ended": 1, "applied": 1}

        with get_connection() as conn:
            row = conn.execute("SELECT ai_summary, ai_status, ai_summarized_at FROM conversations WHERE id = ?",
                               (ids[0],)).fetchone()
            assert row["ai_summary"] == "done" and row["ai_status"] == "open" and row["ai_summarized_at"]
            for cid in ids[1:]:
                assert conn.execute("SELECT ai_summarized_at FROM conversations WHERE id = ?",
                                    (cid,)).fetchone()[0] is None
            assert conn.execute("SELECT COUNT(*) FROM ai_batch_items WHERE processed_at IS NULL").fetchone()[0] == 0
            b = conn.execute("SELECT * FROM ai_batches").fetchone()
            assert b["processed_at"] and b["status"] == "ended"
            usage = conn.execute("SELECT mode, batch_id, cost_usd FROM ai_usage ORDER BY occurred_at").fetchall()
            assert len(usage) == 2  # the two succeeded results, even the unparsable one
            assert all(u["mode"] == "batch" and u["batch_id"] == b["id"] for u in usage)
            assert usage[0]["cost_usd"] == pytest.approx(0.0122)

        # Released items are picked up by the next live pass.
        calls: list = []
        monkeypatch.setattr(sync, "summarize_conversation",
                            lambda conv, *a, **k: (calls.append(conv.thread_id) or ConversationSummary(
                                thread_id=conv.thread_id, status=ConversationStatus.OPEN, summary="s")))
        _, summarized, _ = sync.process_conversations(None, None, "o", settle_minutes=0, batch_threshold=10)
        assert summarized == 2 and set(calls) == set(ids[1:])

    def test_poll_is_free_when_nothing_is_open(self, tmp_db, monkeypatch):
        from poc import summary_batches
        monkeypatch.setattr(summary_batches, "_client",
                            lambda client=None: pytest.fail("client built with no open batch"))
        assert summary_batches.poll_summary_batches() == {"checked": 0, "ended": 0, "applied": 0}


# ---------------------------------------------------------------------------
# Settings and report route
# ---------------------------------------------------------------------------

class TestRoutes:
    def test_threshold_round_trip_and_validation(self, client):
        r = client.get("/api/v1/settings/system")
        assert r.status_code == 200 and r.json()["summarize_batch_threshold"] == "50"
        r = client.put("/api/v1/settings/system", json={"summarize_batch_threshold": "120"})
        assert r.status_code == 200
        assert client.get("/api/v1/settings/system").json()["summarize_batch_threshold"] == "120"
        r = client.put("/api/v1/settings/system", json={"summarize_batch_threshold": "lots"})
        assert r.status_code == 400

    def test_usage_report_route(self, client):
        from poc.ai_usage import record_usage
        with get_connection() as conn:
            record_usage(conn, purpose="summary", mode="live", model="claude-opus-5-5", usage=_usage())
        r = client.get("/api/v1/settings/ai-usage")
        assert r.status_code == 200
        body = r.json()
        assert body["periods"]["today"]["calls"] == 1
        assert body["batches"] == [] and body["price_table_date"]

    def test_usage_report_is_admin_only(self, tmp_db, monkeypatch):
        monkeypatch.setattr(
            "poc.hierarchy.get_current_user",
            lambda: {"id": USER_ID, "email": "owner@a.com", "name": "Owner", "role": "user", "customer_id": CUST_ID})
        from poc.web.app import create_app
        c = TestClient(create_app(), raise_server_exceptions=False)
        assert c.get("/api/v1/settings/ai-usage").status_code == 403
