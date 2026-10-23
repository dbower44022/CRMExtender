"""Account health (Mail Client MAIL-38): non-interactive credentials,
needs_reauth marking, scheduler skip, sync error badge, disconnect."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from poc import auth
from poc.database import get_connection
from poc.scheduler import SyncScheduler

from tests.test_scheduler import ACCT_A, ACCT_B, CUST_ID, USER_ID, Fakes, _settle, tmp_db  # noqa: F401

_NOW = datetime.now(timezone.utc).isoformat()


@pytest.fixture(autouse=True)
def _interactive_restored():
    before = auth._INTERACTIVE
    yield
    auth.set_interactive(before)


def _account(aid):
    with get_connection() as conn:
        return dict(conn.execute("SELECT * FROM provider_accounts WHERE id = ?", (aid,)).fetchone())


class TestNonInteractiveCredentials:
    def test_missing_token_raises_instead_of_opening_browser(self, tmp_path):
        with pytest.raises(auth.ReauthRequired) as ei:
            auth.get_credentials_for_account(tmp_path / "none.json", interactive=False)
        assert ei.value.reason == "no saved sign-in"

    def test_refresh_failure_raises_in_server_mode(self, tmp_path):
        token = tmp_path / "token.json"
        token.write_text(json.dumps({"token": "t", "refresh_token": "r", "client_id": "c",
                                     "client_secret": "s", "token_uri": "u", "scopes": []}))
        creds = MagicMock(expired=True, refresh_token="r", valid=False)
        creds.refresh.side_effect = RuntimeError("invalid_grant: Token has been expired or revoked.")
        auth.set_interactive(False)
        with patch.object(auth.Credentials, "from_authorized_user_file", return_value=creds), \
             patch.object(auth.InstalledAppFlow, "from_client_secrets_file") as flow:
            with pytest.raises(auth.ReauthRequired) as ei:
                auth.get_credentials_for_account(token)
        assert "invalid_grant" in ei.value.reason
        flow.assert_not_called()

    def test_successful_refresh_is_persisted(self, tmp_path):
        token = tmp_path / "token.json"
        token.write_text("{}")
        creds = MagicMock(expired=True, refresh_token="r", valid=True)
        creds.to_json.return_value = '{"token": "fresh"}'
        with patch.object(auth.Credentials, "from_authorized_user_file", return_value=creds):
            out = auth.get_credentials_for_account(token, interactive=False)
        assert out is creds and token.read_text() == '{"token": "fresh"}'

    def test_web_app_turns_interactive_off(self, tmp_db, monkeypatch):
        auth.set_interactive(True)
        from poc.web.app import create_app
        create_app()
        assert auth._INTERACTIVE is False


class TestSyncMarksAccount:
    def test_sync_account_parks_account_on_reauth(self, tmp_db, monkeypatch):
        from poc.sync_service import sync_account
        monkeypatch.setattr("poc.auth.get_credentials_for_account",
                            lambda p, **k: (_ for _ in ()).throw(auth.ReauthRequired(p, "refresh failed (invalid_grant)")))
        out = sync_account(_account(ACCT_A), customer_id=CUST_ID, user_id=USER_ID, gmail_limiter=None)
        assert out["errors"] and "auth failed" in out["errors"][0]
        a = _account(ACCT_A)
        assert a["auth_status"] == "needs_reauth" and "invalid_grant" in a["auth_error"]

    def test_other_auth_errors_do_not_park(self, tmp_db, monkeypatch):
        from poc.sync_service import sync_account
        monkeypatch.setattr("poc.auth.get_credentials_for_account",
                            lambda p, **k: (_ for _ in ()).throw(RuntimeError("network")))
        sync_account(_account(ACCT_A), customer_id=CUST_ID, user_id=USER_ID, gmail_limiter=None)
        assert _account(ACCT_A)["auth_status"] == "ok"

    def test_send_parks_account_on_reauth(self, tmp_db, monkeypatch):
        from poc.outbound import create_draft, send_email
        monkeypatch.setattr("poc.auth.get_credentials_for_account",
                            lambda p, **k: (_ for _ in ()).throw(auth.ReauthRequired(p, "no saved sign-in")))
        with get_connection() as conn:
            d = create_draft(conn, customer_id=CUST_ID, user_id=USER_ID, from_account_id=ACCT_A,
                             to_addresses=[{"email": "x@y.com"}], subject="s", body_json="{}", body_html="", body_text="")
            r = send_email(conn, queue_id=d["id"], user_id=USER_ID)
        assert r["status"] == "failed"
        assert _account(ACCT_A)["auth_status"] == "needs_reauth"


class TestSchedulerHealth:
    def test_parked_accounts_are_skipped(self, tmp_db, monkeypatch):
        with get_connection() as conn:
            conn.execute("UPDATE provider_accounts SET auth_status = 'needs_reauth' WHERE id = ?", (ACCT_B,))
        fakes = Fakes(monkeypatch)
        s = SyncScheduler(tick_seconds=3600)
        try:
            s.start()
            _settle(s, fakes)
        finally:
            s.stop()
        assert fakes.syncs() == [ACCT_A]
        assert ACCT_B not in s.status()["accounts"]

    def test_run_outcome_is_recorded_and_cleared(self, tmp_db, monkeypatch):
        fakes = Fakes(monkeypatch, fail_account=ACCT_B)
        s = SyncScheduler(tick_seconds=3600)
        try:
            s.start()
            _settle(s, fakes)
        finally:
            s.stop()
        a, b = _account(ACCT_A), _account(ACCT_B)
        assert a["last_sync_error"] is None and a["last_sync_error_at"] is None
        assert b["last_sync_error"] == "boom" and b["last_sync_error_at"]

    def test_reconnect_clears_parked_state(self, tmp_db):
        from poc.account_health import clear_auth_status, mark_needs_reauth
        with get_connection() as conn:
            mark_needs_reauth(conn, ACCT_A, "refresh failed")
            conn.execute("UPDATE provider_accounts SET is_active = 0 WHERE id = ?", (ACCT_A,))
        with get_connection() as conn:
            clear_auth_status(conn, ACCT_A)
        a = _account(ACCT_A)
        assert a["auth_status"] == "ok" and a["auth_error"] is None and a["is_active"] == 1


class TestDisconnectRoute:
    def _client(self, monkeypatch, role="admin", uid=USER_ID):
        monkeypatch.setattr(
            "poc.hierarchy.get_current_user",
            lambda: {"id": uid, "email": "a@s.com", "name": "A", "role": role, "customer_id": CUST_ID},
        )
        from poc.web.app import create_app
        return TestClient(create_app(), raise_server_exceptions=False)

    def _seed_mail(self, aid):
        with get_connection() as conn:
            cid = str(uuid.uuid4())
            conn.execute(
                """INSERT INTO communications (id, account_id, channel, timestamp, original_text, direction, source,
                   sender_address, subject, provider_message_id, provider_thread_id, is_read, is_current, created_at, updated_at)
                   VALUES (?, ?, 'email', ?, 'hi', 'inbound', 'auto_sync', 'x@y.com', 's', ?, 't', 1, 1, ?, ?)""",
                (cid, aid, _NOW, f"pm-{cid}", _NOW, _NOW))
            conn.execute(
                """INSERT INTO conversations (id, customer_id, account_id, title, subject, status, communication_count,
                   message_count, participant_count, first_activity_at, last_activity_at, created_at, updated_at)
                   VALUES (?, ?, ?, 't', 's', 'active', 1, 1, 1, ?, ?, ?, ?)""",
                (str(uuid.uuid4()), CUST_ID, aid, _NOW, _NOW, _NOW, _NOW))
            conn.execute(
                "INSERT INTO mailbox_labels (id, account_id, provider_label_id, name, kind, created_at, updated_at) "
                "VALUES (?, ?, 'INBOX', 'INBOX', 'inbox', ?, ?)", (str(uuid.uuid4()), aid, _NOW, _NOW))
        return cid

    def test_keep_removes_token_and_stops_sync_but_keeps_mail(self, tmp_db, tmp_path, monkeypatch):
        token = tmp_path / "t.json"
        token.write_text("{}")
        with get_connection() as conn:
            conn.execute("UPDATE provider_accounts SET auth_token_path = ? WHERE id = ?", (str(token), ACCT_A))
        cid = self._seed_mail(ACCT_A)
        client = self._client(monkeypatch)
        r = client.delete(f"/api/v1/settings/accounts/{ACCT_A}", params={"mode": "keep"})
        assert r.status_code == 200 and r.json()["deleted"] is False
        a = _account(ACCT_A)
        assert a["is_active"] == 0 and a["auth_status"] == "disconnected" and a["auth_token_path"] is None
        assert not token.exists()
        with get_connection() as conn:
            assert conn.execute("SELECT COUNT(*) FROM communications WHERE id = ?", (cid,)).fetchone()[0] == 1
        # listed with its state; a scheduler would skip it
        listed = {x["id"]: x for x in client.get("/api/v1/settings/accounts").json()}
        assert listed[ACCT_A]["auth_status"] == "disconnected" and listed[ACCT_A]["sync"]["scheduled"] is False

    def test_delete_removes_mail_and_account(self, tmp_db, monkeypatch):
        cid = self._seed_mail(ACCT_A)
        from poc.outbound import create_draft
        with get_connection() as conn:
            create_draft(conn, customer_id=CUST_ID, user_id=USER_ID, from_account_id=ACCT_A,
                         to_addresses=[{"email": "x@y.com"}], subject="s", body_json="{}", body_html="", body_text="")
        client = self._client(monkeypatch)
        r = client.delete(f"/api/v1/settings/accounts/{ACCT_A}", params={"mode": "delete"})
        assert r.status_code == 200
        assert r.json()["communications"] == 1 and r.json()["conversations"] == 1
        with get_connection() as conn:
            assert conn.execute("SELECT COUNT(*) FROM provider_accounts WHERE id = ?", (ACCT_A,)).fetchone()[0] == 0
            assert conn.execute("SELECT COUNT(*) FROM communications WHERE id = ?", (cid,)).fetchone()[0] == 0
            assert conn.execute("SELECT COUNT(*) FROM mailbox_labels WHERE account_id = ?", (ACCT_A,)).fetchone()[0] == 0
            assert conn.execute("SELECT COUNT(*) FROM outbound_email_queue WHERE from_account_id = ?", (ACCT_A,)).fetchone()[0] == 0
            assert conn.execute("SELECT COUNT(*) FROM user_provider_accounts WHERE account_id = ?", (ACCT_A,)).fetchone()[0] == 0
        assert ACCT_B in {x["id"] for x in client.get("/api/v1/settings/accounts").json()}

    def test_disconnect_requires_owner_or_admin(self, tmp_db, monkeypatch):
        with get_connection() as conn:
            conn.execute("INSERT INTO users (id, customer_id, email, name, role, is_active, created_at, updated_at) "
                         "VALUES ('u2', ?, 'u2@s.com', 'U2', 'user', 1, ?, ?)", (CUST_ID, _NOW, _NOW))
            conn.execute("INSERT INTO user_provider_accounts (id, user_id, account_id, role, created_at) "
                         "VALUES (?, 'u2', ?, 'shared', ?)", (str(uuid.uuid4()), ACCT_A, _NOW))
        client = self._client(monkeypatch, role="user", uid="u2")
        assert client.delete(f"/api/v1/settings/accounts/{ACCT_A}").status_code == 403
        assert client.delete(f"/api/v1/settings/accounts/{ACCT_A}", params={"mode": "bogus"}).status_code == 400
        assert client.delete("/api/v1/settings/accounts/nope").status_code == 404
