import json

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.models import (
    Campaign,
    Influencer,
    OutreachLog,
    OutreachMessage,
)
from app.services.outreach.exceptions import (
    DuplicateOutreachError,
    OutreachConfigurationError,
    OutreachDeliveryError,
    OutreachOutcomeUnknown,
)
from app.services.outreach.service import (
    approve_and_send_email,
    dry_run_outreach_message,
)


class StubSender:
    def __init__(self, result="gmail-message-123", error=None):
        self.result = result
        self.error = error
        self.calls = []

    def send(self, recipient, subject, body):
        self.calls.append((recipient, subject, body))
        if self.error:
            raise self.error
        return self.result


@pytest.fixture
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


@pytest.fixture
def approved_email(db):
    campaign = Campaign(name="Movement launch", niche="fitness")
    influencer = Influencer(
        platform="youtube",
        username="janedoe",
        display_name="Jane Doe",
        email="jane@example.com",
    )
    db.add_all((campaign, influencer))
    db.flush()
    message = OutreachMessage(
        campaign_id=campaign.id,
        influencer_id=influencer.id,
        channel="email",
        subject="Collaboration invitation",
        body="Hi Jane, let's talk about yoga.",
        status="approved",
    )
    from datetime import datetime, timezone

    message.approved_at = datetime.now(timezone.utc)
    db.add(message)
    db.commit()
    return message


def event_count(db, event_type):
    return db.scalar(
        select(func.count()).select_from(OutreachLog).where(
            OutreachLog.event_type == event_type
        )
    )


def test_dry_run_requires_approval_and_records_recipient(
    db,
    approved_email,
):
    result = dry_run_outreach_message(db, approved_email.id)

    assert result.status == "dry_run"
    assert result.sent_at is None
    log = db.scalar(
        select(OutreachLog).where(OutreachLog.event_type == "dry_run")
    )
    assert json.loads(log.details)["recipient"] == "jane@example.com"

    with pytest.raises(DuplicateOutreachError):
        dry_run_outreach_message(db, approved_email.id)
    assert event_count(db, "duplicate_blocked") == 1


def test_dry_run_rejects_draft_and_invalid_recipient(db):
    campaign = Campaign(name="Movement launch", niche="fitness")
    influencer = Influencer(platform="youtube", username="noemail")
    db.add_all((campaign, influencer))
    db.flush()
    draft = OutreachMessage(
        campaign_id=campaign.id,
        influencer_id=influencer.id,
        channel="email",
        body="Draft",
        status="draft",
    )
    db.add(draft)
    db.commit()

    with pytest.raises(ValueError, match="approved"):
        dry_run_outreach_message(db, draft.id)

    draft.status = "approved"
    from datetime import datetime, timezone

    draft.approved_at = datetime.now(timezone.utc)
    db.commit()
    with pytest.raises(ValueError, match="valid email"):
        dry_run_outreach_message(db, draft.id)


def test_gmail_send_is_audited_and_duplicate_retry_is_blocked(
    db,
    approved_email,
):
    sender = StubSender()

    result = approve_and_send_email(db, approved_email.id, sender)

    assert result.status == "sent"
    assert result.sent_at is not None
    assert sender.calls == [
        (
            "jane@example.com",
            "Collaboration invitation",
            "Hi Jane, let's talk about yoga.",
        )
    ]
    log = db.scalar(select(OutreachLog).where(OutreachLog.event_type == "sent"))
    details = json.loads(log.details)
    assert details["provider_message_id"] == "gmail-message-123"
    assert details["recipient"] == "jane@example.com"

    with pytest.raises(DuplicateOutreachError):
        approve_and_send_email(db, approved_email.id, sender)
    assert len(sender.calls) == 1
    assert event_count(db, "duplicate_blocked") == 1


@pytest.mark.parametrize(
    ("error", "status", "event_type"),
    [
        (OutreachDeliveryError("Gmail rejected"), "failed", "send_failed"),
        (
            OutreachOutcomeUnknown("Check Gmail"),
            "send_unknown",
            "send_unknown",
        ),
    ],
)
def test_send_failure_is_logged_and_uncertain_outcomes_cannot_retry(
    db,
    approved_email,
    error,
    status,
    event_type,
):
    sender = StubSender(error=error)

    with pytest.raises(type(error)):
        approve_and_send_email(db, approved_email.id, sender)

    assert approved_email.status == status
    assert event_count(db, event_type) == 1
    if status == "failed":
        retry = StubSender()
        assert approve_and_send_email(db, approved_email.id, retry).status == "sent"
        assert json.loads(
            db.scalar(
                select(OutreachLog).where(
                    OutreachLog.event_type == "sent"
                )
            ).details
        )["attempt"] == 2
    else:
        with pytest.raises(DuplicateOutreachError):
            approve_and_send_email(db, approved_email.id, StubSender())


def test_real_send_fails_closed_when_email_is_not_enabled(
    db,
    approved_email,
    monkeypatch,
):
    monkeypatch.setenv("EMAIL_MODE", "dry_run")
    monkeypatch.setenv("ALLOW_REAL_EMAIL_SEND", "true")

    with pytest.raises(OutreachConfigurationError, match="EMAIL_MODE"):
        approve_and_send_email(db, approved_email.id)

    assert approved_email.status == "approved"
    assert event_count(db, "send_started") == 0


def test_real_send_requires_both_explicit_gates(
    db,
    approved_email,
    monkeypatch,
):
    monkeypatch.setenv("EMAIL_MODE", "gmail")
    monkeypatch.setenv("ALLOW_REAL_EMAIL_SEND", "false")

    with pytest.raises(OutreachConfigurationError, match="ALLOW_REAL_EMAIL_SEND"):
        approve_and_send_email(db, approved_email.id)

    assert event_count(db, "send_started") == 0


def test_instagram_dm_cannot_be_sent_using_gmail(db, approved_email):
    approved_email.channel = "instagram_dm"
    db.commit()

    with pytest.raises(ValueError, match="Only approved email"):
        approve_and_send_email(db, approved_email.id, StubSender())
