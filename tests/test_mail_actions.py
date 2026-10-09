"""Mail action outbox (MAIL-09/14): migration, local apply, worker, retry/discard, API.

Covers MAIL-T08 (ordered push, backoff, dead-letter, retry) and the
permission half of MAIL-T10 (non-owner gets 403 on actions).
"""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from poc.database import get_connection, init_db
from poc.mail_actions import (
    BACKOFF_BASE,
    MailActionError,
    discard_action,
    enqueue,
    pending_counts,
    push_pending,
    retry_action,
)
from poc.mail_state import ensure_labels
from poc.migrate_to_v24 import migrate
from poc.models import ParsedEmail
from poc.providers import ActionKind, ActionResult, ActionStatus
from poc.sync import _store_thread, load_contact_index

_NOW = datetime.now(timezone.utc).isoformat()
CUST_ID = "cust-act"
USER_ID = "user-act"
OTHER_USER = "user-act-other"
ACCOUNT_ID = "acct-act"
OWNER = "owner@act.com"


@pytest.fixture()
def tmp_db(tmp_path, monkeypatch):
    db_file = tmp_path / "test.db"
    monkeypatch.setattr("poc.config.DB_PATH", db_file)
    monkeypatch.setattr("poc.config.CRM_AUTH_ENABLED", False)
    init_db(db_file)
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO customers (id, name, slug, is_active, created_at, updated_at) "
            "VALUES (?, 'Act Org', 'act', 1, ?, ?)", (CUST_ID, _NOW, _NOW))
        for uid, email, role in ((USER_ID, OWNER, "admin"), (OTHER_USER, "other@act.com", "user")):
            conn.execute(
                "INSERT INTO users (id, customer_id, email, name, role, is_active, created_at, updated_at) "
                "VALUES (?, ?, ?, 'U', ?, 1, ?, ?)", (uid, CUST_ID, email, role, _NOW, _NOW))
        conn.execute(
            "INSERT INTO provider_accounts (id, customer_id, provider, email_address, auth_token_path, "
            "sync_cursor, initial_sync_done, is_active, created_at, updated_at) "
            "VALUES (?, ?, 'gmail', ?, '/tmp/t.json', 'c', 1, 1, ?, ?)", (ACCOUNT_ID, CUST_ID, OWNER, _NOW, _NOW))
        conn.execute(
            "INSERT INTO user_provider_accounts (id, user_id, account_id, role, created_at) "
            "VALUES (?, ?, ?, 'owner', ?)", (str(uuid.uuid4()), USER_ID, ACCOUNT_ID, _NOW))
        conn.execute(
            "INSERT INTO user_provider_accounts (id, user_id, account_id, role, created_at) "
            "VALUES (?, ?, ?, 'shared', ?)", (str(uuid.uuid4()), OTHER_USER, ACCOUNT_ID, _NOW))
    return db_file


def _store(label_ids=("INBOX", "UNREAD"), is_read=False, is_starred=False) -> dict:
    em = ParsedEmail(
        message_id=f"pm-{uuid.uuid4().hex[:8]}", thread_id=f"t-{uuid.uuid4().hex[:6]}",
        subject="S", sender="A <a@x.com>", sender_email="a@x.com", recipients=[OWNER],
        date=datetime(2026, 3, 1, tzinfo=timezone.utc), body_plain="b", snippet="b",
        label_ids=list(label_ids), is_read=is_read, is_starred=is_starred,
    )
    with get_connection() as conn:
        _store_thread(conn, ACCOUNT_ID, OWNER, [em], load_contact_index(),
                      customer_id=CUST_ID, created_by=USER_ID)
        row = dict(conn.execute("SELECT * FROM communications WHERE provider_message_id = ?",
                                (em.message_id,)).fetchone())
    return row


def _comm(comm_id: str) -> dict:
    with get_connection() as conn:
        return dict(conn.execute("SELECT * FROM communications WHERE id = ?", (comm_id,)).fetchone())


def _labels(comm_id: str) -> list[str]:
    with get_connection() as conn:
        return sorted(r[0] for r in conn.execute(
            "SELECT ml.provider_label_id FROM communication_labels cl "
            "JOIN mailbox_labels ml ON ml.id = cl.label_id WHERE cl.communication_id = ?", (comm_id,)))


# ---------------------------------------------------------------------------
# Migration
# ---------------------------------------------------------------------------

class TestMigrationV24:
    def _v23_db(self, tmp_path):
        db = tmp_path / "v23.db"
        init_db(db)
        conn = sqlite3.connect(db)
        conn.execute("DROP TABLE mail_actions")
        conn.execute("PRAGMA user_version = 23")
        conn.commit(); conn.close()
        return db

    def test_creates_table_and_is_idempotent(self, tmp_path):
        db = self._v23_db(tmp_path)
        migrate(db); migrate(db)
        conn = sqlite3.connect(db)
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 24
        cols = [r[1] for r in conn.execute("PRAGMA table_info(mail_actions)")]
        assert {"action", "target_ids", "status", "attempts", "next_attempt_at", "error"} <= set(cols)
        fresh = tmp_path / "fresh.db"; init_db(fresh)
        fc = sqlite3.connect(fresh)
        assert [r[1] for r in fc.execute("PRAGMA table_info(mail_actions)")] == cols


# ---------------------------------------------------------------------------
# Enqueue + local effect
# ---------------------------------------------------------------------------

class TestEnqueue:
    def test_archive_applies_locally_and_queues(self, tmp_db):
        row = _store()
        with get_connection() as conn:
            q = enqueue(conn, account_id=ACCOUNT_ID, kind="archive",
                        communication_ids=[row["id"]], created_by=USER_ID)
        assert q["status"] == "pending" and q["target_ids"] == [row["provider_message_id"]]
        assert _labels(row["id"]) == []                       # INBOX gone
        assert _comm(row["id"])["is_archived"] == 0           # CRM archive untouched (§6.4)

    def test_trash_star_read_effects(self, tmp_db):
        row = _store()
        with get_connection() as conn:
            enqueue(conn, account_id=ACCOUNT_ID, kind="mark_read", communication_ids=[row["id"]])
            enqueue(conn, account_id=ACCOUNT_ID, kind="star", communication_ids=[row["id"]])
            enqueue(conn, account_id=ACCOUNT_ID, kind="trash", communication_ids=[row["id"]])
        c = _comm(row["id"])
        assert c["is_read"] == 1 and c["is_starred"] == 1 and c["is_archived"] == 1
        assert _labels(row["id"]) == ["TRASH"]

    def test_label_add_remove_and_move(self, tmp_db):
        row = _store()
        with get_connection() as conn:
            enqueue(conn, account_id=ACCOUNT_ID, kind="add_label",
                    communication_ids=[row["id"]], label_id="Label_7")
        assert _labels(row["id"]) == ["INBOX", "Label_7"]
        with get_connection() as conn:
            enqueue(conn, account_id=ACCOUNT_ID, kind="move",
                    communication_ids=[row["id"]], label_id="Label_9")
        assert _labels(row["id"]) == ["Label_7", "Label_9"]  # moved out of INBOX
        with get_connection() as conn:
            enqueue(conn, account_id=ACCOUNT_ID, kind="remove_label",
                    communication_ids=[row["id"]], label_id="Label_7")
        assert _labels(row["id"]) == ["Label_9"]

    def test_bad_input(self, tmp_db):
        row = _store()
        with get_connection() as conn:
            with pytest.raises(MailActionError):
                enqueue(conn, account_id=ACCOUNT_ID, kind="teleport", communication_ids=[row["id"]])
            with pytest.raises(MailActionError):
                enqueue(conn, account_id=ACCOUNT_ID, kind="add_label", communication_ids=[row["id"]])
            with pytest.raises(MailActionError):
                enqueue(conn, account_id=ACCOUNT_ID, kind="archive", communication_ids=["nope"])
            with pytest.raises(MailActionError):
                enqueue(conn, account_id=ACCOUNT_ID, kind="snooze", communication_ids=[row["id"]])


# ---------------------------------------------------------------------------
# Worker (MAIL-T08)
# ---------------------------------------------------------------------------

def _provider(results):
    p = MagicMock()
    p.apply_action.side_effect = list(results)
    return p


class TestWorker:
    def _queue(self, n):
        rows = [_store() for _ in range(n)]
        ids = []
        with get_connection() as conn:
            for r in rows:
                ids.append(enqueue(conn, account_id=ACCOUNT_ID, kind="archive",
                                   communication_ids=[r["id"]])["id"])
        return ids

    def _status(self, action_id):
        with get_connection() as conn:
            return dict(conn.execute("SELECT * FROM mail_actions WHERE id = ?", (action_id,)).fetchone())

    def test_pushes_in_order_and_records_outcomes(self, tmp_db):
        ids = self._queue(3)
        p = _provider([
            ActionResult(ActionStatus.PUSHED),
            ActionResult(ActionStatus.GONE, error="404"),
            ActionResult(ActionStatus.FAILED, error="403 scope", permanent=True),
        ])
        stats = push_pending({"id": ACCOUNT_ID}, object(), p)
        assert stats == {"pushed": 1, "gone": 1, "retried": 0, "failed": 1, "skipped": 0}
        assert [c.args[1].message_ids for c in p.apply_action.call_args_list] == \
               [self._status(i)["target_ids"] and __import__("json").loads(self._status(i)["target_ids"]) for i in ids]
        assert [self._status(i)["status"] for i in ids] == ["pushed", "gone", "failed"]
        assert self._status(ids[2])["error"] == "403 scope"

    def test_transient_failure_backs_off_then_dead_letters(self, tmp_db):
        (aid,) = self._queue(1)
        # Relative to the clock: enqueue stamps next_attempt_at with real now.
        t0 = datetime.now(timezone.utc) + timedelta(minutes=1)
        p = _provider([ActionResult(ActionStatus.FAILED, error="500")] * 3)

        s1 = push_pending({"id": ACCOUNT_ID}, object(), p, retry_max=3, now=t0)
        assert s1["retried"] == 1
        row = self._status(aid)
        assert row["status"] == "pending" and row["attempts"] == 1
        assert datetime.fromisoformat(row["next_attempt_at"]) == t0 + BACKOFF_BASE

        # Not due yet: skipped, no provider call
        s2 = push_pending({"id": ACCOUNT_ID}, object(), p, retry_max=3, now=t0 + timedelta(seconds=5))
        assert s2 == {"pushed": 0, "gone": 0, "retried": 0, "failed": 0, "skipped": 1}
        assert p.apply_action.call_count == 1

        # Due: second attempt, backoff doubles
        push_pending({"id": ACCOUNT_ID}, object(), p, retry_max=3, now=t0 + timedelta(minutes=1))
        row = self._status(aid)
        assert row["attempts"] == 2
        assert datetime.fromisoformat(row["next_attempt_at"]) == t0 + timedelta(minutes=1) + 2 * BACKOFF_BASE

        # Third attempt exhausts retry_max → dead letter
        push_pending({"id": ACCOUNT_ID}, object(), p, retry_max=3, now=t0 + timedelta(minutes=10))
        assert self._status(aid)["status"] == "failed"
        assert pending_counts([ACCOUNT_ID]) == {"pending": 0, "failed": 1}

    def test_adapter_exception_is_transient(self, tmp_db):
        (aid,) = self._queue(1)
        p = MagicMock(); p.apply_action.side_effect = RuntimeError("socket")
        push_pending({"id": ACCOUNT_ID}, object(), p)
        row = self._status(aid)
        assert row["status"] == "pending" and row["attempts"] == 1 and "socket" in row["error"]


class TestRetryDiscard:
    def test_retry_requeues_failed(self, tmp_db):
        r = _store()
        with get_connection() as conn:
            q = enqueue(conn, account_id=ACCOUNT_ID, kind="star", communication_ids=[r["id"]])
        push_pending({"id": ACCOUNT_ID}, object(),
                     _provider([ActionResult(ActionStatus.FAILED, error="x", permanent=True)]))
        with get_connection() as conn:
            back = retry_action(conn, q["id"])
        assert back["status"] == "pending" and back["attempts"] == 0 and back["error"] is None

    def test_discard_reverts_local_change(self, tmp_db):
        r = _store()
        with get_connection() as conn:
            q = enqueue(conn, account_id=ACCOUNT_ID, kind="trash", communication_ids=[r["id"]])
        assert _labels(r["id"]) == ["TRASH"] and _comm(r["id"])["is_archived"] == 1
        push_pending({"id": ACCOUNT_ID}, object(),
                     _provider([ActionResult(ActionStatus.FAILED, error="x", permanent=True)]))
        with get_connection() as conn:
            gone = discard_action(conn, q["id"])
        assert gone["status"] == "discarded"
        assert _labels(r["id"]) == ["INBOX"] and _comm(r["id"])["is_archived"] == 0

    def test_discard_move_restores_origin(self, tmp_db):
        r = _store()
        with get_connection() as conn:
            q = enqueue(conn, account_id=ACCOUNT_ID, kind="move",
                        communication_ids=[r["id"]], label_id="Label_9")
        assert _labels(r["id"]) == ["Label_9"]
        with get_connection() as conn:
            discard_action(conn, q["id"])
        assert _labels(r["id"]) == ["INBOX"]


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------

def _client(monkeypatch, user_id, role):
    monkeypatch.setattr(
        "poc.hierarchy.get_current_user",
        lambda: {"id": user_id, "email": "x@act.com", "name": "U", "role": role, "customer_id": CUST_ID},
    )
    from poc.web.app import create_app
    return TestClient(create_app(), raise_server_exceptions=False)


class TestApi:
    def test_owner_can_enqueue_list_retry_discard(self, tmp_db, monkeypatch):
        client = _client(monkeypatch, USER_ID, "admin")
        r = _store()
        resp = client.post("/api/v1/mail/actions",
                           json={"action": "archive", "communication_ids": [r["id"]]})
        assert resp.status_code == 201, resp.text
        aid = resp.json()["id"]
        assert _labels(r["id"]) == []

        listing = client.get("/api/v1/mail/actions").json()
        assert listing["counts"] == {"pending": 1, "failed": 0}
        assert listing["items"][0]["id"] == aid

        assert client.post(f"/api/v1/mail/actions/{aid}/retry").status_code == 200
        assert client.post(f"/api/v1/mail/actions/{aid}/discard").json()["status"] == "discarded"
        assert _labels(r["id"]) == ["INBOX"]

    def test_thread_targets_expand_to_every_message(self, tmp_db, monkeypatch):
        client = _client(monkeypatch, USER_ID, "admin")
        a = _store(); b = _store()
        with get_connection() as conn:
            conn.execute("UPDATE communications SET provider_thread_id = 'thr-X' WHERE id IN (?, ?)", (a["id"], b["id"]))
        resp = client.post("/api/v1/mail/actions",
                           json={"action": "mark_read", "threads": [{"account_id": ACCOUNT_ID, "thread_id": "thr-X"}]})
        assert resp.status_code == 201, resp.text
        assert sorted(resp.json()["target_ids"]) == sorted([a["provider_message_id"], b["provider_message_id"]])
        assert _comm(a["id"])["is_read"] == 1 and _comm(b["id"])["is_read"] == 1
        assert client.post("/api/v1/mail/actions",
                           json={"action": "archive", "threads": [{"account_id": ACCOUNT_ID, "thread_id": "nope"}]}).status_code == 404

    def test_shared_user_cannot_act(self, tmp_db, monkeypatch):
        client = _client(monkeypatch, OTHER_USER, "user")
        r = _store()
        resp = client.post("/api/v1/mail/actions",
                           json={"action": "archive", "communication_ids": [r["id"]]})
        assert resp.status_code == 403
        assert _labels(r["id"]) == ["INBOX"]

    def test_bad_action_is_400(self, tmp_db, monkeypatch):
        client = _client(monkeypatch, USER_ID, "admin")
        r = _store()
        assert client.post("/api/v1/mail/actions",
                           json={"action": "fly", "communication_ids": [r["id"]]}).status_code == 400
        assert client.post("/api/v1/mail/actions", json={"action": "archive"}).status_code == 400

    def test_push_endpoint_uses_provider(self, tmp_db, monkeypatch):
        client = _client(monkeypatch, USER_ID, "admin")
        r = _store()
        client.post("/api/v1/mail/actions", json={"action": "star", "communication_ids": [r["id"]]})
        monkeypatch.setattr("poc.auth.get_credentials_for_account", lambda p: object())
        fake = MagicMock(); fake.apply_action.return_value = ActionResult(ActionStatus.PUSHED)
        monkeypatch.setattr("poc.providers.get_provider", lambda name: fake)
        resp = client.post("/api/v1/mail/actions/push")
        assert resp.status_code == 200, resp.text
        assert resp.json()["results"][OWNER]["pushed"] == 1
        assert resp.json()["counts"] == {"pending": 0, "failed": 0}
