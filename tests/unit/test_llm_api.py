import json
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.models import Campaign, Influencer, OutreachMessage
from app.db.session import get_db
from app.main import app
from app.services.outreach.exceptions import OutreachConfigurationError

VALID_RESPONSE = {
    "email_subject": "Jane, let's talk yoga and collaboration",
    "email_body": (
        "Hi Jane, your thoughtful yoga routines make a strong fit for our "
        "upcoming collaboration. Our campaign would love to explore how your "
        "approach to accessible movement might resonate with your community. "
        "If you are interested, we would be glad to share the brief, discuss "
        "creative ideas together, and learn what kind of partnership feels "
        "authentic to you. There is no assumption about deliverables or terms; "
        "we can shape the conversation around your preferences. Would you be "
        "open to a short introduction next week?"
    ),
    "instagram_dm": (
        "Hi Jane, your yoga routines caught our attention. We're planning a "
        "fitness collaboration and would love to share the idea and hear what "
        "partnership would feel right for you."
    ),
}


class StubProvider:
    model = "test-model"

    def generate(self, system_prompt, user_prompt):
        return json.dumps(VALID_RESPONSE)


class StubGmailSender:
    def __init__(self):
        self.calls = []

    def send(self, recipient, subject, body):
        self.calls.append((recipient, subject, body))
        return "gmail-message-id"


@pytest.fixture
def api_client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    test_session = sessionmaker(bind=engine, class_=Session)

    def override_get_db():
        with test_session() as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db
    with test_session() as db:
        db.add(
            Campaign(
                name="Movement launch",
                niche="fitness",
                description="Accessible movement campaign.",
            )
        )
        db.add_all(
            (
                Influencer(
                    platform="youtube",
                    username="janedoe",
                    display_name="Jane Doe",
                    niche="fitness",
                    bio="Yoga routines and accessible movement",
                    followers_count=25_000,
                ),
                Influencer(
                    platform="youtube",
                    username="unqualified",
                    display_name="Unqualified",
                    bio="Travel videos",
                    followers_count=25_000,
                ),
            )
        )
        db.commit()

    yield TestClient(app), test_session
    app.dependency_overrides.pop(get_db, None)
    Base.metadata.drop_all(engine)
    engine.dispose()


def test_campaign_route_generates_and_approves_only_qualified_drafts(
    api_client,
    monkeypatch,
):
    client, test_session = api_client
    monkeypatch.setattr(
        "app.services.llm.generation.create_llm_provider",
        StubProvider,
    )

    response = client.post("/campaigns/1/messages/generate")

    assert response.status_code == 200
    drafts = response.json()["messages"]
    assert len(drafts) == 2
    assert {draft["channel"] for draft in drafts} == {"email", "instagram_dm"}
    assert all(draft["status"] == "draft" for draft in drafts)
    assert all(draft["influencer_id"] == 1 for draft in drafts)

    approval = client.post(f"/messages/{drafts[0]['id']}/approve")
    assert approval.status_code == 200
    assert approval.json()["status"] == "approved"
    assert approval.json()["approved_at"] is not None

    with test_session() as db:
        assert len(db.scalars(select(OutreachMessage)).all()) == 2


def test_generation_route_reports_missing_campaign(api_client):
    client, _ = api_client

    response = client.post("/campaigns/999/messages/generate")

    assert response.status_code == 404
    assert response.json()["detail"] == "Campaign not found."


def test_generation_route_rejects_unsupported_campaign_niche(api_client):
    client, test_session = api_client
    with test_session() as db:
        db.add(Campaign(name="Beauty launch", niche="beauty"))
        db.commit()

    response = client.post("/campaigns/2/messages/generate")

    assert response.status_code == 400
    assert "fitness" in response.json()["detail"]


def test_dry_run_and_send_routes_require_approval_and_log_outcomes(
    api_client,
    monkeypatch,
):
    client, test_session = api_client
    with test_session() as db:
        influencer = db.get(Influencer, 1)
        influencer.email = "jane@example.com"
        message = OutreachMessage(
            campaign_id=1,
            influencer_id=1,
            channel="email",
            subject="Collaboration invitation",
            body=VALID_RESPONSE["email_body"],
            status="approved",
            approved_at=datetime.now(timezone.utc),
        )
        db.add(message)
        db.commit()
        message_id = message.id

    sender = StubGmailSender()
    monkeypatch.setattr(
        "app.services.outreach.service._create_gmail_sender",
        lambda: sender,
    )

    dry_run = client.post(f"/outreach/{message_id}/dry-run")
    assert dry_run.status_code == 200
    assert dry_run.json()["status"] == "dry_run"
    assert sender.calls == []

    sent = client.post(f"/outreach/{message_id}/send")
    assert sent.status_code == 200
    assert sent.json()["status"] == "sent"
    assert sender.calls[0][0] == "jane@example.com"

    duplicate = client.post(f"/outreach/{message_id}/send")
    assert duplicate.status_code == 409

    logs = client.get("/outreach/logs")
    assert logs.status_code == 200
    assert {log["event_type"] for log in logs.json()} >= {
        "dry_run",
        "send_started",
        "sent",
        "duplicate_blocked",
    }


def test_send_route_reports_disabled_gmail_configuration(
    api_client,
    monkeypatch,
):
    client, test_session = api_client
    with test_session() as db:
        influencer = db.get(Influencer, 1)
        influencer.email = "jane@example.com"
        message = OutreachMessage(
            campaign_id=1,
            influencer_id=1,
            channel="email",
            subject="Invitation",
            body="Hello",
            status="approved",
            approved_at=datetime.now(timezone.utc),
        )
        db.add(message)
        db.commit()
        message_id = message.id

    def disabled_gmail():
        raise OutreachConfigurationError("Real email is disabled.")

    monkeypatch.setattr(
        "app.services.outreach.service._create_gmail_sender",
        disabled_gmail,
    )

    response = client.post(f"/outreach/{message_id}/send")

    assert response.status_code == 503
    assert response.json()["detail"] == "Real email is disabled."
