import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.models import (
    Campaign,
    Influencer,
    OutreachLog,
    OutreachMessage,
)
from app.services.outreach.exceptions import DuplicateOutreachError
from dashboard import data


@pytest.fixture
def dashboard_db(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    test_session = sessionmaker(bind=engine, class_=Session)
    monkeypatch.setattr(data, "SessionLocal", test_session)
    yield test_session
    Base.metadata.drop_all(engine)
    engine.dispose()


def test_csv_import_reports_imports_duplicates_and_invalid_rows(
    dashboard_db,
):
    report = data.import_csv_content(
        b"platform,username,display_name,bio,followers_count\n"
        b"youtube,janedoe,Jane Doe,Yoga workouts,25000\n"
        b"youtube,janedoe,Jane Doe,Yoga workouts,25000\n"
        b",missing,Missing platform,Yoga,10000\n"
    )

    assert report == {
        "total_rows": 3,
        "imported": 1,
        "duplicates": 1,
        "invalid": 1,
        "errors": [{"row": 4, "error": "Platform is required"}],
    }

    with dashboard_db() as db:
        creators = db.scalars(select(Influencer)).all()
    assert len(creators) == 1
    assert creators[0].username == "janedoe"


@pytest.mark.parametrize(
    ("content", "message"),
    [
        (b"not,csv\n1,2\n", "platform and username"),
        (b"\xff\xfe", "UTF-8"),
    ],
)
def test_csv_import_rejects_bad_files(dashboard_db, content, message):
    with pytest.raises(ValueError, match=message):
        data.import_csv_content(content)


def test_influencer_browser_shows_qualification_and_export(dashboard_db):
    with dashboard_db() as db:
        db.add_all(
            (
                Influencer(
                    platform="youtube",
                    username="janedoe",
                    display_name="Jane Doe",
                    bio="Yoga and fitness workouts",
                    followers_count=25_000,
                ),
                Influencer(
                    platform="instagram",
                    username="traveler",
                    display_name="Travel Creator",
                    bio="Travel videos",
                    followers_count=25_000,
                ),
            )
        )
        db.commit()

    qualified = data.list_influencers(
        search="jane",
        platform="youtube",
    )
    assert len(qualified) == 1
    assert qualified[0][1]["overall_status"] == "accepted"
    exported_usernames = {
        row["username"] for row in data.influencers_export_rows()
    }
    assert exported_usernames == {"janedoe", "traveler"}


def test_manual_dm_sent_is_recorded_and_duplicate_blocked(dashboard_db):
    with dashboard_db() as db:
        campaign = Campaign(name="Fitness launch", niche="fitness")
        influencer = Influencer(
            platform="youtube",
            username="janedoe",
            display_name="Jane Doe",
        )
        db.add_all((campaign, influencer))
        db.flush()
        message = OutreachMessage(
            campaign_id=campaign.id,
            influencer_id=influencer.id,
            channel="instagram_dm",
            body="Hi Jane, your yoga workouts look great.",
            status="approved",
        )
        from datetime import datetime, timezone

        message.approved_at = datetime.now(timezone.utc)
        db.add(message)
        db.commit()
        message_id = message.id

    sent = data.mark_dm_sent(message_id)
    assert sent.status == "sent"

    with pytest.raises(DuplicateOutreachError):
        data.mark_dm_sent(message_id)

    with dashboard_db() as db:
        events = db.scalars(
            select(OutreachLog.event_type).order_by(OutreachLog.id)
        ).all()
    assert events == ["manual_dm_sent", "duplicate_blocked"]


def test_draft_edits_are_logged_and_approved_messages_are_locked(
    dashboard_db,
):
    with dashboard_db() as db:
        campaign = Campaign(name="Fitness launch", niche="fitness")
        influencer = Influencer(platform="youtube", username="janedoe")
        db.add_all((campaign, influencer))
        db.flush()
        message = OutreachMessage(
            campaign_id=campaign.id,
            influencer_id=influencer.id,
            channel="email",
            subject="Original subject",
            body="Original body",
            status="draft",
        )
        db.add(message)
        db.commit()
        message_id = message.id

    updated = data.update_draft(
        message_id,
        "Updated subject",
        "Updated message body",
    )
    assert updated.subject == "Updated subject"
    assert updated.body == "Updated message body"

    with dashboard_db() as db:
        log = db.scalar(
            select(OutreachLog).where(OutreachLog.event_type == "edited")
        )
        db.get(OutreachMessage, message_id).status = "approved"
        db.commit()
    assert log is not None
    with pytest.raises(ValueError, match="Only draft"):
        data.update_draft(message_id, "New subject", "New body")
