import json
import re
from datetime import datetime, timezone
from email.utils import parseaddr

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import Influencer, OutreachLog, OutreachMessage
from app.services.outreach.base import GmailSender
from app.services.outreach.exceptions import (
    DuplicateOutreachError,
    OutreachConfigurationError,
    OutreachDeliveryError,
    OutreachOutcomeUnknown,
)

EMAIL_PATTERN = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")
REUSABLE_FAILURE_STATUSES = {"approved", "dry_run", "failed"}
APPROVED_DELIVERY_STATUSES = {
    "approved",
    "dry_run",
    "failed",
    "sending",
    "sent",
    "send_unknown",
}


def _message_and_recipient(
    db: Session,
    message_id: int,
) -> tuple[OutreachMessage, str]:
    message = db.get(OutreachMessage, message_id)
    if message is None:
        raise LookupError(f"Outreach message {message_id} was not found.")
    if message.channel != "email":
        raise ValueError("Only approved email messages can use Gmail.")
    if (
        not message.approved_at
        or message.status not in APPROVED_DELIVERY_STATUSES
    ):
        raise ValueError("The email must be approved before delivery.")

    influencer = db.get(Influencer, message.influencer_id)
    recipient = influencer.email.strip() if influencer and influencer.email else ""
    parsed_address = parseaddr(recipient)[1]
    if (
        not recipient
        or parsed_address != recipient
        or not EMAIL_PATTERN.fullmatch(recipient)
    ):
        raise ValueError("The influencer does not have a valid email address.")
    return message, recipient


def _has_prior_delivery_or_uncertain_attempt(
    db: Session,
    message: OutreachMessage,
) -> bool:
    if message.status in {"sending", "sent", "send_unknown"}:
        return True
    prior_attempt = db.scalar(
        select(OutreachLog.id)
        .join(OutreachMessage, OutreachLog.message_id == OutreachMessage.id)
        .where(
            OutreachMessage.campaign_id == message.campaign_id,
            OutreachMessage.influencer_id == message.influencer_id,
            OutreachMessage.channel == message.channel,
            OutreachLog.event_type.in_(("sent", "send_unknown")),
        )
        .limit(1)
    )
    return prior_attempt is not None


def _log_duplicate_block(db: Session, message: OutreachMessage) -> None:
    db.add(
        OutreachLog(
            message_id=message.id,
            event_type="duplicate_blocked",
            details=json.dumps({"channel": message.channel}),
        )
    )
    db.commit()


def dry_run_outreach_message(db: Session, message_id: int) -> OutreachMessage:
    message, recipient = _message_and_recipient(db, message_id)
    prior_dry_run = db.scalar(
        select(OutreachLog.id)
        .where(
            OutreachLog.message_id == message.id,
            OutreachLog.event_type == "dry_run",
        )
        .limit(1)
    )
    if (
        message.status not in REUSABLE_FAILURE_STATUSES
        or prior_dry_run
        or _has_prior_delivery_or_uncertain_attempt(db, message)
    ):
        _log_duplicate_block(db, message)
        raise DuplicateOutreachError(
            "A prior send or unresolved delivery attempt blocks this dry run."
        )

    claim = db.execute(
        update(OutreachMessage)
        .where(
            OutreachMessage.id == message.id,
            OutreachMessage.approved_at.is_not(None),
            OutreachMessage.status.in_(REUSABLE_FAILURE_STATUSES),
        )
        .values(status="dry_run")
    )
    if claim.rowcount != 1:
        db.rollback()
        _log_duplicate_block(db, message)
        raise DuplicateOutreachError(
            "Another delivery operation has already claimed this email."
        )
    db.add(
        OutreachLog(
            message_id=message.id,
            event_type="dry_run",
            details=json.dumps(
                {
                    "recipient": recipient,
                    "attempt": 1,
                    "provider": "dry_run",
                },
                sort_keys=True,
            ),
        )
    )
    db.commit()
    db.refresh(message)
    return message


def _create_gmail_sender() -> GmailSender:
    settings = get_settings()
    if settings.email_mode.strip().lower() != "gmail":
        raise OutreachConfigurationError(
            "Real email is disabled; set EMAIL_MODE=gmail to enable Gmail delivery."
        )
    if not settings.allow_real_email_send:
        raise OutreachConfigurationError(
            "Real email is disabled; explicitly set ALLOW_REAL_EMAIL_SEND=true."
        )

    from app.services.outreach.gmail_sender import GoogleGmailSender

    return GoogleGmailSender(
        sender=settings.gmail_sender,
        token_file=settings.gmail_token_file,
    )


def approve_and_send_email(
    db: Session,
    message_id: int,
    sender: GmailSender | None = None,
) -> OutreachMessage:
    message, recipient = _message_and_recipient(db, message_id)
    if _has_prior_delivery_or_uncertain_attempt(db, message):
        _log_duplicate_block(db, message)
        raise DuplicateOutreachError(
            "A prior send or unresolved delivery attempt blocks this email."
        )

    selected_sender = sender or _create_gmail_sender()
    attempt_count = db.scalar(
        select(func.count(OutreachLog.id))
        .where(
            OutreachLog.message_id == message.id,
            OutreachLog.event_type == "send_started",
        )
    )
    attempt_number = (attempt_count or 0) + 1
    claim = db.execute(
        update(OutreachMessage)
        .where(
            OutreachMessage.id == message.id,
            OutreachMessage.approved_at.is_not(None),
            OutreachMessage.status.in_(REUSABLE_FAILURE_STATUSES),
        )
        .values(status="sending")
    )
    if claim.rowcount != 1:
        db.rollback()
        _log_duplicate_block(db, message)
        raise DuplicateOutreachError(
            "Another delivery attempt has already claimed this email."
        )
    db.add(
        OutreachLog(
            message_id=message.id,
            event_type="send_started",
            details=json.dumps(
                {"recipient": recipient, "attempt": attempt_number},
                sort_keys=True,
            ),
        )
    )
    db.commit()
    db.refresh(message)

    try:
        provider_message_id = selected_sender.send(
            recipient,
            message.subject or "",
            message.body,
        )
    except OutreachDeliveryError as exc:
        message.status = "failed"
        db.add(
            OutreachLog(
                message_id=message.id,
                event_type="send_failed",
                details=json.dumps(
                    {
                        "recipient": recipient,
                        "attempt": attempt_number,
                        "error": str(exc),
                    },
                    sort_keys=True,
                ),
            )
        )
        db.commit()
        raise
    except OutreachOutcomeUnknown as exc:
        message.status = "send_unknown"
        db.add(
            OutreachLog(
                message_id=message.id,
                event_type="send_unknown",
                details=json.dumps(
                    {
                        "recipient": recipient,
                        "attempt": attempt_number,
                        "error": str(exc),
                    },
                    sort_keys=True,
                ),
            )
        )
        db.commit()
        raise
    except OutreachConfigurationError:
        message.status = "failed"
        db.add(
            OutreachLog(
                message_id=message.id,
                event_type="send_failed",
                details=json.dumps(
                    {
                        "recipient": recipient,
                        "attempt": attempt_number,
                        "error": "Gmail configuration is unavailable.",
                    },
                    sort_keys=True,
                ),
            )
        )
        db.commit()
        raise

    message.status = "sent"
    message.sent_at = datetime.now(timezone.utc)
    db.add(
        OutreachLog(
            message_id=message.id,
            event_type="sent",
            details=json.dumps(
                {
                    "recipient": recipient,
                    "attempt": attempt_number,
                    "provider": "gmail",
                    "provider_message_id": provider_message_id,
                },
                sort_keys=True,
            ),
        )
    )
    db.commit()
    db.refresh(message)
    return message


def mark_instagram_dm_sent(
    db: Session,
    message_id: int,
) -> OutreachMessage:
    message = db.get(OutreachMessage, message_id)
    if message is None:
        raise LookupError(f"Outreach message {message_id} was not found.")
    if message.channel != "instagram_dm":
        raise ValueError("Only Instagram DM messages can be marked manually sent.")
    if not message.approved_at:
        raise ValueError("The Instagram DM must be approved before marking sent.")
    if message.status == "sent":
        _log_duplicate_block(db, message)
        raise DuplicateOutreachError(
            "This Instagram DM is already marked as sent."
        )
    if message.status not in {"approved", "failed"}:
        raise ValueError(
            f"Cannot mark an Instagram DM in '{message.status}' status as sent."
        )

    claim = db.execute(
        update(OutreachMessage)
        .where(
            OutreachMessage.id == message.id,
            OutreachMessage.channel == "instagram_dm",
            OutreachMessage.approved_at.is_not(None),
            OutreachMessage.status.in_({"approved", "failed"}),
        )
        .values(status="sent", sent_at=datetime.now(timezone.utc))
    )
    if claim.rowcount != 1:
        db.rollback()
        _log_duplicate_block(db, message)
        raise DuplicateOutreachError(
            "Another operation has already updated this Instagram DM."
        )
    db.add(
        OutreachLog(
            message_id=message.id,
            event_type="manual_dm_sent",
            details=json.dumps({"channel": "instagram_dm"}),
        )
    )
    db.commit()
    db.refresh(message)
    return message
