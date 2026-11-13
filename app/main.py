import csv
from datetime import datetime
from io import StringIO
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import require_dashboard_token
from app.db.base import Base
from app.db.models import (
    Campaign,
    Influencer,
    OutreachLog,
    OutreachMessage,
)
from app.db.session import engine, get_db
from app.repositories.influencer_repository import save_influencers
from app.services.discovery.csv_importer import import_csv_content
from app.services.discovery.youtube_client import (
    YouTubeAPIError,
    fetch_channel_details,
    normalize_channel,
    search_channels,
)
from app.services.filtering.pipeline import process_influencer
from app.services.filtering.rules import MAX_FOLLOWERS, MIN_FOLLOWERS, TARGET_NICHE
from app.services.llm.exceptions import (
    LLMConfigurationError,
    LLMProviderError,
    MessageValidationError,
)
from app.services.llm.generation import (
    approve_outreach_message,
    generate_messages_for_qualified_influencers,
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
    mark_instagram_dm_sent,
    reconcile_delivery,
)

app = FastAPI(
    title="Micro Influencer Outreach API",
    description="Local API for discovery, review, and outreach tracking.",
    version="1.0.0",
)


class CampaignCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    niche: str = Field(min_length=1, max_length=100)
    description: str | None = None


class CampaignResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    niche: str
    description: str | None
    status: str
    created_at: datetime


class DiscoveryRequest(BaseModel):
    query: str = Field(min_length=1, max_length=200)
    pages: int = Field(default=1, ge=1, le=5)


class DiscoveryResponse(BaseModel):
    channel_ids: int
    channel_details: int
    imported: int
    duplicates: int


class InfluencerResponse(BaseModel):
    id: int
    platform: str
    platform_user_id: str | None
    username: str
    display_name: str | None
    profile_url: str | None
    niche: str | None
    bio: str | None
    followers_count: int | None
    following_count: int | None
    posts_count: int | None
    avg_likes: float | None
    avg_comments: float | None
    engagement_rate: float | None
    email: str | None
    location: str | None
    source: str | None
    discovered_at: datetime
    qualification: dict[str, Any]


class InfluencerSummary(BaseModel):
    id: int
    username: str
    display_name: str | None
    email: str | None
    profile_url: str | None


class MessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    influencer_id: int
    campaign_id: int
    channel: str
    subject: str | None
    body: str
    status: str
    created_at: datetime
    approved_at: datetime | None
    sent_at: datetime | None


class MessageWithInfluencerResponse(MessageResponse):
    influencer: InfluencerSummary


class GenerationResponse(BaseModel):
    messages: list[MessageResponse]


class MessageUpdate(BaseModel):
    subject: str | None = Field(default=None, max_length=300)
    body: str = Field(min_length=1, max_length=3000)


class ReconcileRequest(BaseModel):
    confirmed_not_sent: bool = False


class OutreachLogResponse(BaseModel):
    id: int
    message_id: int
    event_type: str
    details: str | None
    created_at: datetime
    campaign: str
    creator: str
    channel: str
    message_status: str


def _csv_response(rows: list[dict[str, Any]], filename: str) -> Response:
    if not rows:
        return Response(
            content="",
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.on_event("startup")
def create_database_tables() -> None:
    Base.metadata.create_all(bind=engine)


@app.get("/")
def home() -> dict[str, str]:
    return {"message": "Micro Influencer Outreach System", "status": "Running"}


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "healthy"}


@app.post(
    "/discovery/import-csv",
    dependencies=[Depends(require_dashboard_token)],
)
async def import_csv(request: Request, db: Session = Depends(get_db)):
    content = await request.body()
    try:
        return import_csv_content(content, db)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post(
    "/discovery/youtube",
    response_model=DiscoveryResponse,
    dependencies=[Depends(require_dashboard_token)],
)
def discover_youtube(
    request: DiscoveryRequest,
    db: Session = Depends(get_db),
):
    try:
        channel_ids = search_channels(request.query, max_pages=request.pages)
        channels = fetch_channel_details(channel_ids)
    except (YouTubeAPIError, ValueError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    influencers = [
        normalized
        for channel in channels
        if (normalized := normalize_channel(channel)) is not None
    ]
    result = save_influencers(db, influencers)
    return DiscoveryResponse(
        channel_ids=len(channel_ids),
        channel_details=len(channels),
        imported=result["imported"],
        duplicates=result["duplicates"],
    )


@app.get(
    "/influencers",
    response_model=list[InfluencerResponse],
    dependencies=[Depends(require_dashboard_token)],
)
def list_influencers(
    search: str = "",
    platform: str | None = None,
    qualification: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    statement = select(Influencer).order_by(Influencer.id.desc())
    if platform:
        statement = statement.where(Influencer.platform == platform.lower())
    influencers = db.scalars(statement.limit(limit)).all()
    query = search.strip().casefold()
    results = []
    for influencer in influencers:
        profile_text = " ".join(
            str(value or "")
            for value in (
                influencer.username,
                influencer.display_name,
                influencer.niche,
                influencer.bio,
            )
        ).casefold()
        if query and query not in profile_text:
            continue
        result = process_influencer(influencer)
        if qualification and result["overall_status"] != qualification:
            continue
        results.append(
            InfluencerResponse(
                id=influencer.id,
                platform=influencer.platform,
                platform_user_id=influencer.platform_user_id,
                username=influencer.username,
                display_name=influencer.display_name,
                profile_url=influencer.profile_url,
                niche=influencer.niche,
                bio=influencer.bio,
                followers_count=influencer.followers_count,
                following_count=influencer.following_count,
                posts_count=influencer.posts_count,
                avg_likes=influencer.avg_likes,
                avg_comments=influencer.avg_comments,
                engagement_rate=influencer.engagement_rate,
                email=influencer.email,
                location=influencer.location,
                source=influencer.source,
                discovered_at=influencer.discovered_at,
                qualification={
                    key: value
                    for key, value in result.items()
                    if key != "profile"
                },
            )
        )
    return results


@app.get(
    "/campaigns",
    response_model=list[CampaignResponse],
    dependencies=[Depends(require_dashboard_token)],
)
def list_campaigns(db: Session = Depends(get_db)):
    return db.scalars(
        select(Campaign).order_by(Campaign.created_at.desc())
    ).all()


@app.post(
    "/campaigns",
    response_model=CampaignResponse,
    status_code=201,
    dependencies=[Depends(require_dashboard_token)],
)
def create_campaign(request: CampaignCreate, db: Session = Depends(get_db)):
    if request.niche.strip().casefold() != TARGET_NICHE.casefold():
        raise HTTPException(
            status_code=400,
            detail=f"Only the '{TARGET_NICHE}' niche is currently supported.",
        )
    campaign = Campaign(
        name=request.name.strip(),
        niche=TARGET_NICHE,
        description=request.description.strip() if request.description else None,
    )
    db.add(campaign)
    db.commit()
    db.refresh(campaign)
    return campaign


@app.get(
    "/messages",
    response_model=list[MessageWithInfluencerResponse],
    dependencies=[Depends(require_dashboard_token)],
)
def list_messages(
    campaign_id: int | None = None,
    db: Session = Depends(get_db),
):
    statement = (
        select(OutreachMessage, Influencer)
        .join(Influencer, Influencer.id == OutreachMessage.influencer_id)
        .order_by(OutreachMessage.created_at.desc())
    )
    if campaign_id is not None:
        statement = statement.where(
            OutreachMessage.campaign_id == campaign_id
        )
    return [
        MessageWithInfluencerResponse(
            **MessageResponse.model_validate(message).model_dump(),
            influencer=InfluencerSummary(
                id=influencer.id,
                username=influencer.username,
                display_name=influencer.display_name,
                email=influencer.email,
                profile_url=influencer.profile_url,
            ),
        )
        for message, influencer in db.execute(statement).all()
    ]


@app.patch(
    "/messages/{message_id}",
    response_model=MessageResponse,
    dependencies=[Depends(require_dashboard_token)],
)
def update_message(
    message_id: int,
    request: MessageUpdate,
    db: Session = Depends(get_db),
):
    message = db.get(OutreachMessage, message_id)
    if message is None:
        raise HTTPException(status_code=404, detail="Message not found.")
    if message.status != "draft":
        raise HTTPException(
            status_code=409,
            detail="Only draft messages can be edited.",
        )
    if message.channel == "email" and not (request.subject or "").strip():
        raise HTTPException(
            status_code=400,
            detail="Email subject cannot be empty.",
        )
    message.body = request.body.strip()
    if message.channel == "email":
        message.subject = (request.subject or "").strip()
    db.add(
        OutreachLog(
            message_id=message.id,
            event_type="edited",
            details="Message edited through the authenticated API.",
        )
    )
    db.commit()
    db.refresh(message)
    return message


@app.post(
    "/campaigns/{campaign_id}/messages/generate",
    response_model=GenerationResponse,
    dependencies=[Depends(require_dashboard_token)],
)
def generate_campaign_messages(
    campaign_id: int,
    db: Session = Depends(get_db),
):
    campaign = db.get(Campaign, campaign_id)
    if campaign is None:
        raise HTTPException(status_code=404, detail="Campaign not found.")
    if campaign.niche.casefold() != TARGET_NICHE.casefold():
        raise HTTPException(
            status_code=400,
            detail=f"Only the '{TARGET_NICHE}' niche is currently supported.",
        )
    qualified = [
        influencer
        for influencer in db.scalars(select(Influencer)).all()
        if process_influencer(influencer)["overall_status"] == "accepted"
    ]
    try:
        messages = generate_messages_for_qualified_influencers(
            db,
            campaign,
            qualified,
        )
    except LLMConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except (LLMProviderError, MessageValidationError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return GenerationResponse(messages=messages)


@app.post(
    "/messages/{message_id}/approve",
    response_model=MessageResponse,
    dependencies=[Depends(require_dashboard_token)],
)
def approve_message(message_id: int, db: Session = Depends(get_db)):
    try:
        return approve_outreach_message(db, message_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post(
    "/outreach/{message_id}/dry-run",
    response_model=MessageResponse,
    dependencies=[Depends(require_dashboard_token)],
)
def dry_run_message(message_id: int, db: Session = Depends(get_db)):
    try:
        return dry_run_outreach_message(db, message_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except DuplicateOutreachError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post(
    "/outreach/{message_id}/send",
    response_model=MessageResponse,
    dependencies=[Depends(require_dashboard_token)],
)
def send_message(message_id: int, db: Session = Depends(get_db)):
    try:
        return approve_and_send_email(db, message_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except DuplicateOutreachError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except OutreachConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except OutreachDeliveryError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except OutreachOutcomeUnknown as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post(
    "/outreach/{message_id}/mark-dm-sent",
    response_model=MessageResponse,
    dependencies=[Depends(require_dashboard_token)],
)
def mark_dm_sent(message_id: int, db: Session = Depends(get_db)):
    try:
        return mark_instagram_dm_sent(db, message_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except DuplicateOutreachError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post(
    "/outreach/{message_id}/reconcile",
    response_model=MessageResponse,
    dependencies=[Depends(require_dashboard_token)],
)
def reconcile_message(
    message_id: int,
    request: ReconcileRequest,
    db: Session = Depends(get_db),
):
    try:
        return reconcile_delivery(
            db,
            message_id,
            confirmed_not_sent=request.confirmed_not_sent,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.get(
    "/outreach/logs",
    response_model=list[OutreachLogResponse],
    dependencies=[Depends(require_dashboard_token)],
)
def list_outreach_logs(
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    rows = db.execute(
        select(OutreachLog, OutreachMessage, Influencer, Campaign)
        .join(OutreachMessage, OutreachMessage.id == OutreachLog.message_id)
        .join(Influencer, Influencer.id == OutreachMessage.influencer_id)
        .join(Campaign, Campaign.id == OutreachMessage.campaign_id)
        .order_by(OutreachLog.created_at.desc(), OutreachLog.id.desc())
        .limit(limit)
    ).all()
    return [
        OutreachLogResponse(
            id=log.id,
            message_id=message.id,
            event_type=log.event_type,
            details=log.details,
            created_at=log.created_at,
            campaign=campaign.name,
            creator=influencer.display_name or influencer.username,
            channel=message.channel,
            message_status=message.status,
        )
        for log, message, influencer, campaign in rows
    ]


@app.get(
    "/exports/influencers",
    dependencies=[Depends(require_dashboard_token)],
)
def export_influencers(db: Session = Depends(get_db)):
    influencers = db.scalars(
        select(Influencer).order_by(Influencer.id)
    ).all()
    rows = []
    for influencer in influencers:
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
                "qualification": process_influencer(influencer)[
                    "overall_status"
                ],
            }
        )
    return _csv_response(rows, "influencers.csv")


@app.get(
    "/exports/outreach",
    dependencies=[Depends(require_dashboard_token)],
)
def export_outreach(db: Session = Depends(get_db)):
    logs = list_outreach_logs(limit=500, db=db)
    rows = [log.model_dump(mode="json") for log in logs]
    return _csv_response(rows, "outreach_history.csv")
