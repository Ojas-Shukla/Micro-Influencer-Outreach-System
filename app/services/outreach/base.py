from typing import Protocol


class GmailSender(Protocol):
    def send(self, recipient: str, subject: str, body: str) -> str:
        """Send an email and return the Gmail message identifier."""
        ...
