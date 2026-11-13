import base64
from email import message_from_bytes
from email.policy import default

import pytest
import httplib2
from googleapiclient.errors import HttpError

from app.services.outreach.exceptions import (
    OutreachConfigurationError,
    OutreachDeliveryError,
    OutreachOutcomeUnknown,
)
from app.services.outreach.gmail_sender import GoogleGmailSender


class Request:
    def __init__(self, result=None, error=None):
        self.result = result or {"id": "message-id"}
        self.error = error
        self.kwargs = None

    def execute(self):
        if self.error:
            raise self.error
        return self.result


class FakeGmailService:
    def __init__(self, request):
        self.request = request

    def users(self):
        return self

    def messages(self):
        return self

    def send(self, **kwargs):
        self.request.kwargs = kwargs
        return self.request


def test_gmail_sender_builds_mime_message_and_returns_provider_id(monkeypatch):
    request = Request()
    sender = GoogleGmailSender("brand@example.com", "token.json")
    monkeypatch.setattr(sender, "_get_service", lambda: FakeGmailService(request))

    message_id = sender.send(
        "creator@example.com",
        "Collaboration",
        "Hello creator",
    )

    raw = request.kwargs["body"]["raw"]
    message = message_from_bytes(
        base64.urlsafe_b64decode(raw),
        policy=default,
    )
    assert message_id == "message-id"
    assert request.kwargs["userId"] == "me"
    assert message["To"] == "creator@example.com"
    assert message["From"] == "brand@example.com"
    assert message["Subject"] == "Collaboration"
    assert message.get_content() == "Hello creator\n"


def test_gmail_sender_classifies_rejected_and_uncertain_requests(monkeypatch):
    sender = GoogleGmailSender("brand@example.com", "token.json")
    monkeypatch.setattr(
        sender,
        "_get_service",
        lambda: FakeGmailService(
            Request(
                error=HttpError(
                    httplib2.Response({"status": "403"}),
                    b"Forbidden",
                )
            )
        ),
    )
    with pytest.raises(OutreachDeliveryError, match="403"):
        sender.send("creator@example.com", "Subject", "Body")

    monkeypatch.setattr(
        sender,
        "_get_service",
        lambda: FakeGmailService(Request(error=TimeoutError())),
    )
    with pytest.raises(OutreachOutcomeUnknown):
        sender.send("creator@example.com", "Subject", "Body")


def test_gmail_sender_rejects_invalid_oauth_configuration():
    with pytest.raises(OutreachConfigurationError):
        GoogleGmailSender("", "token.json")
    with pytest.raises(OutreachConfigurationError):
        GoogleGmailSender("brand@example.com", "")
