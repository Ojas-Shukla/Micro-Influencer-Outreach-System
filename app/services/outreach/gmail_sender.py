import base64
import http.client
from email.message import EmailMessage
from email.utils import parseaddr
from importlib import import_module
import re
from typing import Any

import httplib2
from google.auth.exceptions import GoogleAuthError, TransportError
from googleapiclient.errors import HttpError

from app.services.outreach.base import GmailSender
from app.services.outreach.exceptions import (
    OutreachConfigurationError,
    OutreachDeliveryError,
    OutreachOutcomeUnknown,
)

EMAIL_PATTERN = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")


class GoogleGmailSender:
    def __init__(
        self,
        sender: str,
        token_file: str,
        scopes: tuple[str, ...] = ("https://www.googleapis.com/auth/gmail.send",),
    ) -> None:
        sender_address = sender.strip()
        if (
            parseaddr(sender_address)[1] != sender_address
            or not EMAIL_PATTERN.fullmatch(sender_address)
        ):
            raise OutreachConfigurationError("GMAIL_SENDER must be configured.")
        if not token_file.strip():
            raise OutreachConfigurationError(
                "GMAIL_TOKEN_FILE must point to a completed Gmail OAuth token."
            )
        self.sender = sender
        self.token_file = token_file
        self.scopes = scopes
        self._service: Any | None = None

    def _get_service(self) -> Any:
        if self._service is not None:
            return self._service
        try:
            credentials_module = import_module("google.oauth2.credentials")
            discovery_module = import_module("googleapiclient.discovery")
            credentials = credentials_module.Credentials.from_authorized_user_file(
                self.token_file,
                list(self.scopes),
            )
            if not credentials.valid and not credentials.refresh_token:
                raise OutreachConfigurationError(
                    "Gmail OAuth token is expired and cannot be refreshed."
                )
            self._service = discovery_module.build(
                "gmail",
                "v1",
                credentials=credentials,
                cache_discovery=False,
            )
        except OutreachConfigurationError:
            raise
        except (
            OSError,
            ValueError,
            ImportError,
            KeyError,
            GoogleAuthError,
            httplib2.HttpLib2Error,
            HttpError,
        ) as exc:
            raise OutreachConfigurationError(
                "Gmail OAuth token is missing or invalid; run scripts/gmail_auth.py."
            ) from exc
        return self._service

    def send(self, recipient: str, subject: str, body: str) -> str:
        message = EmailMessage()
        message["To"] = recipient
        message["From"] = self.sender
        message["Subject"] = subject
        message.set_content(body)

        try:
            service = self._get_service()
        except OutreachConfigurationError:
            raise

        encoded = base64.urlsafe_b64encode(message.as_bytes()).decode("ascii")
        request = service.users().messages().send(
            userId="me",
            body={"raw": encoded},
        )
        try:
            result = request.execute()
        except HttpError as exc:
            status = int(exc.resp.status)
            if status >= 500:
                raise OutreachOutcomeUnknown(
                    "Gmail returned a server error; reconcile before retrying."
                ) from exc
            raise OutreachDeliveryError(
                f"Gmail rejected the message (HTTP {status})."
            ) from exc
        except (
            TransportError,
            httplib2.HttpLib2Error,
            http.client.HTTPException,
            OSError,
            TimeoutError,
            ConnectionError,
        ) as exc:
            raise OutreachOutcomeUnknown(
                "Gmail delivery outcome is unknown; reconcile Gmail before retrying."
            ) from exc
        if not isinstance(result, dict):
            raise OutreachOutcomeUnknown(
                "Gmail returned an invalid send response; reconcile before retrying."
            )

        message_id = result.get("id")
        if not isinstance(message_id, str) or not message_id:
            raise OutreachOutcomeUnknown(
                "Gmail accepted the request without a message ID; reconcile before retrying."
            )
        return message_id
