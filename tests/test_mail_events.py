"""Live updates (Mail Client MAIL-37; file renamed from test_events.py, which belongs to calendar events): the in-process broadcaster, the
scheduler's events, and the server-sent-events route."""

from __future__ import annotations

import json
import threading

import pytest
from fastapi.testclient import TestClient

from poc import events
from poc.scheduler import SyncScheduler

from tests.test_scheduler import ACCT_A, ACCT_B, CUST_ID, USER_ID, Fakes, _settle, tmp_db  # noqa: F401


@pytest.fixture(autouse=True)
def _clean_subscribers():
    yield
    with events._lock:
        events._subscribers.clear()


class TestBroadcaster:
    def test_publish_reaches_every_subscriber_and_frames_as_sse(self):
        a, b = events.subscribe(), events.subscribe()
        ev = events.publish("sync.finished", account_id="x", result={"emails_fetched": 2})
        assert a.get_nowait() == ev and b.get_nowait() == ev
        assert ev["type"] == "sync.finished" and ev["account_id"] == "x" and ev["id"] > 0
        frame = events.format_sse(ev)
        assert frame.startswith(f"id: {ev['id']}\nevent: sync.finished\ndata: ")
        assert json.loads(frame.split("data: ", 1)[1].strip()) == ev
        events.unsubscribe(a)
        events.publish("sync.started", account_id="y")
        assert a.empty() and b.get_nowait()["type"] == "sync.started"

    def test_slow_subscriber_drops_oldest_not_publisher(self):
        q = events.subscribe()
        for i in range(events.QUEUE_SIZE + 5):
            events.publish("tick", n=i)
        assert q.qsize() == events.QUEUE_SIZE
        assert q.get_nowait()["n"] == 5           # the first five were dropped


class TestSchedulerEvents:
    def test_sync_and_post_pass_publish_events(self, tmp_db, monkeypatch):
        fakes = Fakes(monkeypatch, fail_account=ACCT_B)
        q = events.subscribe()
        s = SyncScheduler(tick_seconds=3600)
        try:
            s.start()
            _settle(s, fakes)
        finally:
            s.stop()
        got = []
        while not q.empty():
            got.append(q.get_nowait())
        types = [e["type"] for e in got]
        assert types.count("sync.started") == 2 and types.count("sync.finished") == 2
        assert "post_pass.finished" in types
        fin = {e["account_id"]: e for e in got if e["type"] == "sync.finished"}
        assert fin[ACCT_A]["error"] is None and fin[ACCT_A]["result"] == {"emails_fetched": 2, "actions_pushed": 0, "actions_failed": 0, "contacts": 1}
        assert fin[ACCT_B]["error"] == "boom" and fin[ACCT_B]["result"] is None
        post = next(e for e in got if e["type"] == "post_pass.finished")
        assert post["result"] == {"summarized": 3}


class TestRoute:
    def _client(self, monkeypatch):
        monkeypatch.setattr(
            "poc.hierarchy.get_current_user",
            lambda: {"id": USER_ID, "email": "a@s.com", "name": "A", "role": "admin", "customer_id": CUST_ID},
        )
        from poc.web.app import create_app
        return TestClient(create_app(), raise_server_exceptions=False)

    def test_stream_delivers_visible_events_only(self, tmp_db, monkeypatch):
        client = self._client(monkeypatch)

        def publish_soon():
            for _ in range(200):
                if events.subscriber_count():
                    break
                threading.Event().wait(0.01)
            events.publish("sync.finished", account_id="not-mine", result=None)
            events.publish("sync.finished", account_id=ACCT_A, result={"emails_fetched": 1})
            events.publish("post_pass.finished", result={"summarized": 0})

        threading.Thread(target=publish_soon, daemon=True).start()
        # The test client collects the whole body, so the stream is bounded.
        resp = client.get("/api/v1/mail/events", params={"max_seconds": 1.0})
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")
        body = resp.text
        assert body.startswith(": connected")
        frames = [json.loads(line[6:]) for line in body.splitlines() if line.startswith("data: ")]
        assert [f["type"] for f in frames] == ["sync.finished", "post_pass.finished"]
        assert frames[0]["account_id"] == ACCT_A
        assert "not-mine" not in body
        assert events.subscriber_count() == 0
