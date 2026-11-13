from datetime import datetime

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.models import Campaign, Influencer, OutreachLog
from app.db.session import engine, get_db
from app.services.filtering.pipeline import process_influencer
from app.services.filtering.rules import TARGET_NICHE
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
)

app = FastAPI(
    title="Micro Influencer Outreach API",
    description="AI-powered influencer discovery and outreach system",
    version="1.0.0"
)


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


class GenerationResponse(BaseModel):
    messages: list[MessageResponse]


class OutreachLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    message_id: int
    event_type: str
    details: str | None
    created_at: datetime


@app.on_event("startup")
def create_database_tables():
    Base.metadata.create_all(bind=engine)


@app.get("/")
def home():
    return {
        "message": "Micro Influencer Outreach System",
        "status": "Running"
    }


@app.get("/health")
def health_check():
    return {
        "status": "healthy"
    }


@app.post(
    "/campaigns/{campaign_id}/messages/generate",
    response_model=GenerationResponse,
)
def generate_campaign_messages(
    campaign_id: int,
    db: Session = Depends(get_db),
):
    campaign = db.get(Campaign, campaign_id)
    if campaign is None:
        raise HTTPException(status_code=404, detail="Campaign not found.")
    if campaign.niche.strip().casefold() != TARGET_NICHE.casefold():
        raise HTTPException(
            status_code=400,
            detail=(
                "The active qualification pipeline supports the "
                f"'{TARGET_NICHE}' niche only."
            ),
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


@app.get(
    "/outreach/logs",
    response_model=list[OutreachLogResponse],
)
def list_outreach_logs(
    limit: int = 100,
    db: Session = Depends(get_db),
):
    if not 1 <= limit <= 500:
        raise HTTPException(
            status_code=400,
            detail="limit must be between 1 and 500.",
        )
    return db.scalars(
        select(OutreachLog)
        .order_by(OutreachLog.created_at.desc(), OutreachLog.id.desc())
        .limit(limit)
    ).all()
