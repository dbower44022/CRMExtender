"""MailProvider contract and Gmail adapter tests.

Covers MAIL-T02 (interface satisfied; sync and outbound have no direct
Gmail import), EPS-T01 (registry), EPS-T02 (normalization captures
headers, names, labels, flags, attachments), EPS-T03 (history → Delta),
EPS-T06 (actions → Gmail requests, 404 → gone), and the send delegation.
"""

from __future__ import annotations

import ast
import base64
import inspect
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from poc import gmail_client
from poc.providers import (
    Action,
    ActionKind,
    ActionStatus,
    CursorInvalid,
    FolderKind,
    MailProvider,
    OutboundMessage,
    UnknownProviderError,
    get_provider,
    registered_providers,
)
from poc.providers.gmail import SNOOZE_LABEL_NAME, GmailProvider

POC = Path(__file__).resolve().parent.parent / "poc"


# ---------------------------------------------------------------------------
# Registry and contract (EPS-T01, MAIL-T02)
# ---------------------------------------------------------------------------

class TestRegistry:
    def test_gmail_registered(self):
        assert "gmail" in registered_providers()
        assert isinstance(get_provider("gmail"), GmailProvider)

    def test_lookup_is_case_insensitive_and_cached(self):
        assert get_provider("Gmail") is get_provider("gmail")

    def test_unknown_provider_raises(self):
        with pytest.raises(UnknownProviderError):
            get_provider("pigeon")


class TestContract:
    def test_gmail_provider_implements_every_abstract_method(self):
        abstract = {
            name for name, _ in inspect.getmembers(MailProvider)
            if getattr(getattr(MailProvider, name), "__isabstractmethod__", False)
        }
        assert abstract, "contract has abstract methods"
        assert not inspect.isabstract(GmailProvider)
        for name in abstract:
            impl = getattr(GmailProvider, name)
            assert impl is not getattr(MailProvider, name), f"{name} not overridden"

    @pytest.mark.parametrize("module", ["sync.py", "outbound.py", "sync_service.py", "__main__.py"])
    def test_engine_modules_do_not_import_gmail_client(self, module):
        tree = ast.parse((POC / module).read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module and "gmail_client" in node.module:
                pytest.fail(f"{module} imports gmail_client directly: {ast.dump(node)}")
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert "gmail_client" not in alias.name, f"{module} imports {alias.name}"


# ---------------------------------------------------------------------------
# Normalization (EPS-T02)
# ---------------------------------------------------------------------------

def _b64(s: str) -> str:
    return base64.urlsafe_b64encode(s.encode()).decode()


def _fixture_message() -> dict:
    return {
        "id": "m1",
        "threadId": "t1",
        "snippet": "hello",
        "labelIds": ["INBOX", "UNREAD", "STARRED", "Label_7"],
        "internalDate": "1700000000000",
        "payload": {
            "mimeType": "multipart/mixed",
            "headers": [
                {"name": "From", "value": "Ada Lovelace <ada@example.com>"},
                {"name": "To", "value": "Bob Builder <bob@example.com>, carol@example.com"},
                {"name": "Cc", "value": "Dan <dan@example.com>"},
                {"name": "Bcc", "value": "eve@example.com"},
                {"name": "Reply-To", "value": "Ada Replies <replies@example.com>"},
                {"name": "Subject", "value": "Test"},
                {"name": "Date", "value": "Tue, 14 Nov 2023 22:13:20 +0000"},
                {"name": "Message-ID", "value": "<abc@example.com>"},
                {"name": "In-Reply-To", "value": "<parent@example.com>"},
                {"name": "References", "value": "<root@example.com>\r\n <parent@example.com>"},
            ],
            "parts": [
                {
                    "mimeType": "multipart/alternative",
                    "parts": [
                        {"mimeType": "text/plain", "body": {"data": _b64("plain body")}},
                        {"mimeType": "text/html", "body": {"data": _b64("<p>html body</p>")}},
                    ],
                },
                {
                    "mimeType": "application/pdf",
                    "filename": "deck.pdf",
                    "headers": [{"name": "Content-Disposition", "value": "attachment; filename=deck.pdf"}],
                    "body": {"attachmentId": "att-1", "size": 1234},
                },
                {
                    "mimeType": "image/png",
                    "filename": "logo.png",
                    "headers": [{"name": "Content-ID", "value": "<logo123>"}],
                    "body": {"attachmentId": "att-2", "size": 99},
                },
            ],
        },
    }


class TestNormalization:
    def test_headers_names_labels_flags_attachments(self):
        em = gmail_client._parse_message(_fixture_message())

        assert em.message_id == "m1" and em.thread_id == "t1"
        assert em.sender_email == "ada@example.com"
        assert em.recipients == ["bob@example.com", "carol@example.com"]
        assert em.cc == ["dan@example.com"]
        assert em.bcc == ["eve@example.com"]
        assert em.reply_to == ["replies@example.com"]
        assert em.participant_names == {
            "ada@example.com": "Ada Lovelace",
            "bob@example.com": "Bob Builder",
            "dan@example.com": "Dan",
            "replies@example.com": "Ada Replies",
        }
        assert em.header_message_id == "<abc@example.com>"
        assert em.header_in_reply_to == "<parent@example.com>"
        assert em.header_references == "<root@example.com> <parent@example.com>"
        assert em.label_ids == ["INBOX", "UNREAD", "STARRED", "Label_7"]
        assert em.is_read is False and em.is_starred is True
        assert em.body_plain == "plain body" and em.body_html == "<p>html body</p>"

        assert [a["attachment_id"] for a in em.attachments] == ["att-1", "att-2"]
        pdf, png = em.attachments
        assert pdf["filename"] == "deck.pdf" and pdf["size"] == 1234 and pdf["is_inline"] is False
        assert png["content_id"] == "logo123" and png["is_inline"] is True

    def test_defaults_when_headers_absent(self):
        msg = {"id": "m2", "threadId": "t2", "payload": {"mimeType": "text/plain",
               "headers": [{"name": "From", "value": "x@example.com"}],
               "body": {"data": _b64("hi")}}}
        em = gmail_client._parse_message(msg)
        assert em.is_read is True and em.is_starred is False
        assert em.label_ids == [] and em.attachments == []
        assert em.header_message_id is None and em.participant_names == {}


# ---------------------------------------------------------------------------
# Incremental delta (EPS-T03) and cursor errors
# ---------------------------------------------------------------------------

def _history_service(records: list[dict]):
    service = MagicMock()
    service.users().history().list().execute.return_value = {"history": records}
    service.users().getProfile().execute.return_value = {"historyId": "999", "emailAddress": "me@x.com"}
    return service


class TestIncremental:
    def test_history_maps_to_delta_with_flags(self):
        records = [
            {"messagesAdded": [{"message": {"id": "new1"}}]},
            {"messagesDeleted": [{"message": {"id": "gone1"}}]},
            {"labelsRemoved": [{"message": {"id": "r1"}, "labelIds": ["UNREAD", "INBOX"]}]},
            {"labelsAdded": [{"message": {"id": "r1"}, "labelIds": ["STARRED"]}]},
            {"labelsAdded": [{"message": {"id": "r2"}, "labelIds": ["Label_7"]}]},
        ]
        with patch("poc.gmail_client.build", return_value=_history_service(records)):
            delta, cursor = GmailProvider().fetch_incremental(MagicMock(), "100")

        assert cursor == "999"
        assert delta.added_ids == ["new1"] and delta.deleted_ids == ["gone1"]
        assert ("r1", ["STARRED"], ["UNREAD", "INBOX"]) in delta.label_changes
        assert ("r2", ["Label_7"], []) in delta.label_changes
        assert dict(delta.flag_changes)["r1"] == {"is_read": True, "is_starred": True}
        assert "r2" not in dict(delta.flag_changes)

    def test_expired_cursor_raises_provider_neutral_error(self):
        import httplib2
        from googleapiclient.errors import HttpError

        resp = httplib2.Response({"status": "404"})
        resp.reason = "gone"
        service = MagicMock()
        service.users().history().list().execute.side_effect = HttpError(resp, b"")
        with patch("poc.gmail_client.build", return_value=service):
            with pytest.raises(CursorInvalid):
                GmailProvider().fetch_incremental(MagicMock(), "old")
        assert issubclass(gmail_client.HistoryExpiredError, CursorInvalid)


# ---------------------------------------------------------------------------
# Folders
# ---------------------------------------------------------------------------

class TestFolders:
    def test_list_folders_maps_system_kinds(self):
        labels = [
            {"id": "INBOX", "name": "INBOX", "type": "system", "messagesUnread": 3},
            {"id": "SENT", "name": "SENT", "type": "system"},
            {"id": "CATEGORY_PROMOTIONS", "name": "CATEGORY_PROMOTIONS", "type": "system"},
            {"id": "Label_1", "name": "Clients/Acme", "type": "user"},
            {"id": "Label_2", "name": SNOOZE_LABEL_NAME, "type": "user"},
        ]
        service = MagicMock()
        service.users().labels().list().execute.return_value = {"labels": labels}
        with patch("poc.gmail_client.build", return_value=service):
            folders = {f.id: f for f in GmailProvider().list_folders(MagicMock())}

        assert folders["INBOX"].kind is FolderKind.INBOX and folders["INBOX"].unread_count == 3
        assert folders["SENT"].kind is FolderKind.SENT
        assert folders["CATEGORY_PROMOTIONS"].kind is FolderKind.CATEGORY
        assert folders["Label_1"].kind is FolderKind.USER and folders["Label_1"].parent_id == "Clients"
        assert folders["Label_2"].kind is FolderKind.SNOOZED


# ---------------------------------------------------------------------------
# Actions (EPS-T06)
# ---------------------------------------------------------------------------

class TestActions:
    def _service(self):
        service = MagicMock()
        return service

    def _modify_body(self, service):
        return service.users().messages().batchModify.call_args.kwargs["body"]

    @pytest.mark.parametrize("kind,expected_add,expected_remove", [
        (ActionKind.MARK_READ, None, ["UNREAD"]),
        (ActionKind.MARK_UNREAD, ["UNREAD"], None),
        (ActionKind.STAR, ["STARRED"], None),
        (ActionKind.UNSTAR, None, ["STARRED"]),
        (ActionKind.ARCHIVE, None, ["INBOX"]),
        (ActionKind.UNARCHIVE, ["INBOX"], None),
        (ActionKind.SPAM, ["SPAM"], ["INBOX"]),
        (ActionKind.UNSPAM, ["INBOX"], ["SPAM"]),
    ])
    def test_label_actions_produce_batch_modify(self, kind, expected_add, expected_remove):
        service = self._service()
        with patch("poc.gmail_client.build", return_value=service):
            result = GmailProvider().apply_action(MagicMock(), Action(kind, ["a", "b"]))
        assert result.status is ActionStatus.PUSHED
        body = self._modify_body(service)
        assert body["ids"] == ["a", "b"]
        assert body.get("addLabelIds") == expected_add
        assert body.get("removeLabelIds") == expected_remove

    def test_add_and_remove_label_and_move(self):
        service = self._service()
        with patch("poc.gmail_client.build", return_value=service):
            p = GmailProvider()
            p.apply_action(MagicMock(), Action(ActionKind.ADD_LABEL, ["a"], label_id="L1"))
            assert self._modify_body(service)["addLabelIds"] == ["L1"]
            p.apply_action(MagicMock(), Action(ActionKind.REMOVE_LABEL, ["a"], label_id="L1"))
            assert self._modify_body(service)["removeLabelIds"] == ["L1"]
            p.apply_action(MagicMock(), Action(ActionKind.MOVE, ["a"], label_id="L2",
                                                payload={"from_label_ids": ["L1"]}))
            body = self._modify_body(service)
            assert body["addLabelIds"] == ["L2"] and body["removeLabelIds"] == ["L1"]

    def test_trash_and_untrash(self):
        service = self._service()
        with patch("poc.gmail_client.build", return_value=service):
            p = GmailProvider()
            assert p.apply_action(MagicMock(), Action(ActionKind.TRASH, ["a", "b"])).status is ActionStatus.PUSHED
            assert service.users().messages().trash.call_count == 2
            assert p.apply_action(MagicMock(), Action(ActionKind.UNTRASH, ["a"])).status is ActionStatus.PUSHED
            service.users().messages().untrash.assert_called_once_with(userId="me", id="a")

    def test_create_label_returns_folder(self):
        service = self._service()
        service.users().labels().create().execute.return_value = {"id": "Label_9", "name": "Clients/Acme"}
        with patch("poc.gmail_client.build", return_value=service):
            result = GmailProvider().apply_action(
                MagicMock(), Action(ActionKind.CREATE_LABEL, name="Acme", parent_id="Clients"))
        assert result.status is ActionStatus.PUSHED
        assert result.created_label.id == "Label_9" and result.created_label.parent_id == "Clients"
        assert service.users().labels().create.call_args.kwargs["body"]["name"] == "Clients/Acme"

    def test_snooze_creates_label_when_missing(self):
        service = self._service()
        service.users().labels().list().execute.return_value = {"labels": []}
        service.users().labels().create().execute.return_value = {"id": "Label_S", "name": SNOOZE_LABEL_NAME}
        with patch("poc.gmail_client.build", return_value=service):
            GmailProvider().apply_action(MagicMock(), Action(ActionKind.SNOOZE, ["a"]))
        body = self._modify_body(service)
        assert body["addLabelIds"] == ["Label_S"] and body["removeLabelIds"] == ["INBOX"]

    def test_missing_target_reports_gone(self):
        import httplib2
        from googleapiclient.errors import HttpError

        resp = httplib2.Response({"status": "404"})
        resp.reason = "missing"
        service = self._service()
        service.users().messages().batchModify().execute.side_effect = HttpError(resp, b"")
        with patch("poc.gmail_client.build", return_value=service):
            result = GmailProvider().apply_action(MagicMock(), Action(ActionKind.ARCHIVE, ["zzz"]))
        assert result.status is ActionStatus.GONE

    def test_missing_label_id_fails_without_request(self):
        service = self._service()
        with patch("poc.gmail_client.build", return_value=service):
            result = GmailProvider().apply_action(MagicMock(), Action(ActionKind.ADD_LABEL, ["a"]))
        assert result.status is ActionStatus.FAILED
        service.users().messages().batchModify.assert_not_called()


# ---------------------------------------------------------------------------
# Send and backfill
# ---------------------------------------------------------------------------

class TestSendAndBackfill:
    @patch("poc.gmail_client.send_message", return_value=("mid", "tid"))
    def test_send_delegates_with_threading_headers(self, mock_send):
        creds = MagicMock()
        result = GmailProvider().send(creds, OutboundMessage(
            from_email="me@x.com", to=["a@x.com"], subject="s", body_html="<p>h</p>",
            body_text="h", in_reply_to="<p@x>", references="<r@x> <p@x>", thread_id="tid",
        ))
        assert result == ("mid", "tid")
        kwargs = mock_send.call_args.kwargs
        assert kwargs["in_reply_to"] == "<p@x>" and kwargs["thread_id"] == "tid"
        assert mock_send.call_args.args[0] is creds

    def test_backfill_pages_before_epoch_and_ends_with_none(self):
        service = MagicMock()
        service.users().messages().list().execute.side_effect = [
            {"messages": [{"id": "o1"}], "nextPageToken": "p2"},
            {"messages": []},
        ]
        service.users().messages().get().execute.return_value = {
            "id": "o1", "threadId": "t", "payload": {"headers": [{"name": "From", "value": "a@x.com"}]}}
        with patch("poc.gmail_client.build", return_value=service):
            p = GmailProvider()
            msgs, nxt = p.fetch_backfill(MagicMock(), "1700000000|", batch=50)
            assert [m.message_id for m in msgs] == ["o1"] and nxt == "1700000000|p2"
            assert service.users().messages().list.call_args.kwargs["q"] == "before:1700000000"
            msgs, nxt = p.fetch_backfill(MagicMock(), nxt, batch=50)
            assert msgs == [] and nxt is None
        assert p.fetch_backfill(MagicMock(), None) == ([], None)
