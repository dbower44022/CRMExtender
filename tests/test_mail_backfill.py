"""Historical backfill job (MAIL-11; MAIL-T05): resumes from the checkpoint, never duplicates."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from poc.database import get_connection, init_db
from poc.mail_backfill import run_backfill_batch, start_cursor
from poc.models import ParsedEmail
from poc.settings import set_setting
from poc.sync import _store_thread, load_contact_index

_NOW = datetime.now(timezone.utc).isoformat()
CUST_ID = "cust-bf"
USER_ID = "user-bf"
ACCOUNT_ID = "acct-bf"
OWNER = "owner@bf.com"
T0 = datetime(2026, 6, 1, 12, tzinfo=timezone.utc)


@pytest.fixture()
def tmp_db(tmp_path, monkeypatch):
    db_file = tmp_path / "test.db"
    monkeypatch.setattr("poc.config.DB_PATH", db_file)
    init_db(db_file)
    with get_connection() as conn:
        conn.execute("INSERT INTO customers (id, name, slug, is_active, created_at, updated_at) "
                     "VALUES (?, 'BF', 'bf', 1, ?, ?)", (CUST_ID, _NOW, _NOW))
        conn.execute("INSERT INTO users (id, customer_id, email, name, role, is_active, created_at, updated_at) "
                     "VALUES (?, ?, ?, 'U', 'admin', 1, ?, ?)", (USER_ID, CUST_ID, OWNER, _NOW, _NOW))
        conn.execute("INSERT INTO provider_accounts (id, customer_id, provider, email_address, auth_token_path, "
                     "sync_cursor, initial_sync_done, is_active, created_at, updated_at) "
                     "VALUES (?, ?, 'gmail', ?, '/tmp/t.json', 'c', 1, 1, ?, ?)", (ACCOUNT_ID, CUST_ID, OWNER, _NOW, _NOW))
    return db_file


def _msg(i: int, when: datetime, thread: str | None = None) -> ParsedEmail:
    return ParsedEmail(
        message_id=f"pm-{i}", thread_id=thread or f"t-{i}", subject=f"Old {i}",
        sender="A <a@x.com>", sender_email="a@x.com", recipients=[OWNER],
        date=when, body_plain="b", snippet="b", label_ids=["INBOX"], is_read=True,
    )


class FakeProvider:
    """Pages of older mail keyed by cursor; records every cursor asked for."""

    def __init__(self, pages: dict[str, tuple[list, str | None]]):
        self.pages = pages
        self.calls: list[str] = []

    def fetch_backfill(self, session, cursor, *, batch=200, rate_limiter=None):
        self.calls.append(cursor)
        return self.pages[cursor]


def _account() -> dict:
    with get_connection() as conn:
        return dict(conn.execute("SELECT * FROM provider_accounts WHERE id = ?", (ACCOUNT_ID,)).fetchone())


def _count() -> int:
    with get_connection() as conn:
        return conn.execute("SELECT COUNT(*) FROM communications WHERE account_id = ?", (ACCOUNT_ID,)).fetchone()[0]


def test_resumes_from_checkpoint_without_duplicates(tmp_db):
    # Initial sync stored one recent message; the backfill starts before it.
    with get_connection() as conn:
        _store_thread(conn, ACCOUNT_ID, OWNER, [_msg(0, T0)], load_contact_index(),
                      customer_id=CUST_ID, created_by=USER_ID)
        first = start_cursor(conn, ACCOUNT_ID)
    epoch = int(T0.timestamp())
    assert first == f"{epoch}|"

    older = [_msg(i, T0 - timedelta(days=i)) for i in (1, 2, 3)]
    even_older = [_msg(i, T0 - timedelta(days=i)) for i in (3, 4)]  # pm-3 repeats across pages
    provider = FakeProvider({
        first: (older, f"{epoch}|page2"),
        f"{epoch}|page2": (even_older, None),
    })

    r1 = run_backfill_batch(_account(), None, provider, customer_id=CUST_ID, user_id=USER_ID)
    assert r1["status"] == "ran" and r1["fetched"] == 3 and r1["stored"] == 3 and not r1["done"]
    acct = _account()
    assert acct["backfill_cursor"] == f"{epoch}|page2" and acct["backfill_done"] == 0
    assert acct["backfill_messages"] == 3

    # "Interruption": a fresh call reads the checkpoint, not the start.
    r2 = run_backfill_batch(_account(), None, provider, customer_id=CUST_ID, user_id=USER_ID)
    assert provider.calls == [first, f"{epoch}|page2"]
    assert r2["fetched"] == 2 and r2["stored"] == 1 and r2["done"]  # pm-3 already stored
    assert _count() == 1 + 4
    acct = _account()
    assert acct["backfill_done"] == 1 and acct["backfill_messages"] == 4

    # Complete: no provider call at all.
    r3 = run_backfill_batch(_account(), None, provider, customer_id=CUST_ID, user_id=USER_ID)
    assert r3["status"] == "done" and len(provider.calls) == 2


def test_disabled_setting_stops_at_checkpoint(tmp_db):
    with get_connection() as conn:
        _store_thread(conn, ACCOUNT_ID, OWNER, [_msg(0, T0)], load_contact_index(),
                      customer_id=CUST_ID, created_by=USER_ID)
    set_setting(CUST_ID, "mail_backfill_enabled", "false", scope="system")
    provider = FakeProvider({})
    r = run_backfill_batch(_account(), None, provider, customer_id=CUST_ID, user_id=USER_ID)
    assert r["status"] == "disabled" and provider.calls == []


def test_not_ready_before_initial_sync(tmp_db):
    with get_connection() as conn:
        conn.execute("UPDATE provider_accounts SET initial_sync_done = 0 WHERE id = ?", (ACCOUNT_ID,))
    r = run_backfill_batch(_account(), None, FakeProvider({}), customer_id=CUST_ID, user_id=USER_ID)
    assert r["status"] == "not_ready"


def test_batch_size_setting_is_clamped(tmp_db):
    from poc.mail_backfill import backfill_settings
    set_setting(CUST_ID, "mail_backfill_batch_size", "5", scope="system")
    assert backfill_settings(CUST_ID) == (True, 10)
    set_setting(CUST_ID, "mail_backfill_batch_size", "9000", scope="system")
    assert backfill_settings(CUST_ID) == (True, 500)
