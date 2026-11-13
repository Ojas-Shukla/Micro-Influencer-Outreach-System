import csv
from io import StringIO
from typing import Any

from sqlalchemy import select

from app.db.base import Base
from app.db.models import (
    Campaign,
    Influencer,
    OutreachLog,
    OutreachMessage,
)
from app.db.session import SessionLocal, engine
from app.repositories.influencer_repository import save_influencers
from app.services.discovery.csv_importer import normalize_row
from app.services.discovery.youtube_client import (
    fetch_channel_details,
    normalize_channel,
    search_channels,
)
from app.services.filtering.pipeline import process_influencer
from app.services.llm.generation import (
    approve_outreach_message,
    generate_messages_for_qualified_influencers,
)
from app.services.outreach.service import (
    approve_and_send_email,
    dry_run_outreach_message,
    mark_instagram_dm_sent,
)


def initialize_database() -> None:
    Base.metadata.create_all(bind=engine)


def import_csv_content(content: bytes) -> dict[str, Any]:
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("CSV must use UTF-8 encoding.") from exc

    reader = csv.DictReader(StringIO(text))
    required_columns = {"platform", "username"}
    if not reader.fieldnames or not required_columns.issubset(reader.fieldnames):
        raise ValueError("CSV must contain platform and username columns.")

    valid_records = []
    errors = []
    total_rows = 0
    for row_number, row in enumerate(reader, start=2):
        total_rows += 1
        try:
            valid_records.append(normalize_row(row))
        except ValueError as exc:
            errors.append({"row": row_number, "error": str(exc)})

    with SessionLocal() as db:
        result = save_influencers(db, valid_records)
    return {
        "total_rows": total_rows,
        "imported": result["imported"],
        "duplicates": result["duplicates"],
        "invalid": len(errors),
        "errors": errors,
    }


def discover_youtube(query: str, pages: int) -> dict[str, int]:
    channel_ids = search_channels(query, max_pages=pages)
    channels = fetch_channel_details(channel_ids)
    records = [
        normalized
        for channel in channels
        if (normalized := normalize_channel(channel)) is not None
    ]
    with SessionLocal() as db:
        result = save_influencers(db, records)
    return {
        "channel_ids": len(channel_ids),
        "channel_details": len(channels),
        "imported": result["imported"],
        "duplicates": result["duplicates"],
    }


def list_influencers(
    search: str = "",
    platform: str = "All",
) -> list[tuple[Influencer, dict[str, Any]]]:
    with SessionLocal() as db:
        statement = select(Influencer).order_by(Influencer.id.desc())
        if platform != "All":
            statement = statement.where(Influencer.platform == platform.lower())
        creators = db.scalars(statement).all()
        search_text = search.strip().casefold()
        rows = []
        for creator in creators:
            qualification = process_influencer(creator)
            searchable = " ".join(
                str(value or "")
                for value in (
                    creator.username,
                    creator.display_name,
                    creator.niche,
                    creator.bio,
                )
            ).casefold()
            if search_text and search_text not in searchable:
                continue
            rows.append((creator, qualification))
        return rows


def list_campaigns() -> list[Campaign]:
    with SessionLocal() as db:
        return db.scalars(
            select(Campaign).order_by(Campaign.created_at.desc())
        ).all()


def create_campaign(name: str, niche: str, description: str) -> int:
    campaign = Campaign(
        name=name.strip(),
        niche=niche.strip(),
        description=description.strip() or None,
    )
    with SessionLocal() as db:
        db.add(campaign)
        db.commit()
        db.refresh(campaign)
        return campaign.id


def generate_campaign_messages(campaign_id: int) -> list[OutreachMessage]:
    with SessionLocal() as db:
        campaign = db.get(Campaign, campaign_id)
        if campaign is None:
            raise LookupError("Campaign not found.")
        influencers = db.scalars(select(Influencer)).all()
        qualified = [
            creator
            for creator in influencers
            if process_influencer(creator)["overall_status"] == "accepted"
        ]
        return generate_messages_for_qualified_influencers(
            db,
            campaign,
            qualified,
        )


def list_campaign_messages(
    campaign_id: int | None = None,
) -> list[tuple[OutreachMessage, Influencer]]:
    with SessionLocal() as db:
        statement = (
            select(OutreachMessage, Influencer)
            .join(Influencer, Influencer.id == OutreachMessage.influencer_id)
            .order_by(OutreachMessage.created_at.desc())
        )
        if campaign_id is not None:
            statement = statement.where(
                OutreachMessage.campaign_id == campaign_id
            )
        return list(db.execute(statement).all())


def update_draft(
    message_id: int,
    subject: str | None,
    body: str,
) -> OutreachMessage:
    with SessionLocal() as db:
        message = db.get(OutreachMessage, message_id)
        if message is None:
            raise LookupError("Message not found.")
        if message.status != "draft":
            raise ValueError("Only draft messages can be edited.")
        if not body.strip():
            raise ValueError("Message body cannot be empty.")
        if subject is not None and not subject.strip():
            raise ValueError("Email subject cannot be empty.")
        message.body = body.strip()
        if subject is not None:
            message.subject = subject.strip()
        db.add(
            OutreachLog(
                message_id=message.id,
                event_type="edited",
                details="Message edited in the Streamlit dashboard.",
            )
        )
        db.commit()
        db.refresh(message)
        return message


def approve_message(message_id: int) -> OutreachMessage:
    with SessionLocal() as db:
        return approve_outreach_message(db, message_id)


def dry_run_message(message_id: int) -> OutreachMessage:
    with SessionLocal() as db:
        return dry_run_outreach_message(db, message_id)


def send_email(message_id: int) -> OutreachMessage:
    with SessionLocal() as db:
        return approve_and_send_email(db, message_id)


def mark_dm_sent(message_id: int) -> OutreachMessage:
    with SessionLocal() as db:
        return mark_instagram_dm_sent(db, message_id)


def list_outreach_history() -> list[dict[str, Any]]:
    with SessionLocal() as db:
        rows = db.execute(
            select(OutreachLog, OutreachMessage, Influencer, Campaign)
            .join(OutreachMessage, OutreachMessage.id == OutreachLog.message_id)
            .join(Influencer, Influencer.id == OutreachMessage.influencer_id)
            .join(Campaign, Campaign.id == OutreachMessage.campaign_id)
            .order_by(OutreachLog.created_at.desc(), OutreachLog.id.desc())
        ).all()
        return [
            {
                "timestamp": log.created_at,
                "event": log.event_type,
                "campaign": campaign.name,
                "creator": influencer.display_name or influencer.username,
                "channel": message.channel,
                "message_status": message.status,
                "details": log.details,
                "message_id": message.id,
            }
            for log, message, influencer, campaign in rows
        ]


def influencers_export_rows() -> list[dict[str, Any]]:
    rows = []
    for influencer, qualification in list_influencers():
        rows.append(
            {
                "id": influencer.id,
                "platform": influencer.platform,
                "username": influencer.username,
                "display_name": influencer.display_name,
                "profile_url": influencer.profile_url,
                "niche": influencer.niche,
                "followers_count": influencer.followers_count,
                "engagement_rate": influencer.engagement_rate,
                "email": influencer.email,
                "source": influencer.source,
                "qualification": qualification["overall_status"],
            }
        )
    return rows


def outreach_export_rows() -> list[dict[str, Any]]:
    return list_outreach_history()
