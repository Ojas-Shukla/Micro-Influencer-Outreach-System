import json
import re
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.campaign import Campaign
from app.db.models.influencer import Influencer
from app.db.models.outreach_log import OutreachLog
from app.db.models.outreach_message import OutreachMessage
from app.services.llm.base import LLMProvider
from app.services.llm.exceptions import MessageValidationError
from app.services.llm.factory import create_llm_provider
from app.services.llm.prompts.prompt_builder import build_prompts

PROMPT_VERSION = "outreach-v1"
WORD_PATTERN = re.compile(r"\b[\w]+(?:['’][\w]+)?\b", re.UNICODE)
NUMBER_PATTERN = re.compile(r"\b\d+(?:[,.]\d+)*%?\b")
PLACEHOLDER_PATTERN = re.compile(
    r"\[[^\]]+\]|\b(?:insert name|creator name|brand name|tbd)\b",
    re.IGNORECASE,
)
NON_PERSONALIZATION_WORDS = {
    "about",
    "after",
    "because",
    "brand",
    "campaign",
    "collaboration",
    "creator",
    "content",
    "could",
    "from",
    "have",
    "into",
    "love",
    "message",
    "would",
    "your",
}


class GeneratedOutreach(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    email_subject: str = Field(min_length=1, max_length=300)
    email_body: str = Field(min_length=1, max_length=3000)
    instagram_dm: str = Field(min_length=1, max_length=1000)


def _value(source: Any, key: str) -> Any:
    if isinstance(source, Mapping):
        return source.get(key)
    return getattr(source, key, None)


def _prompt_context(source: Any, fields: Sequence[str]) -> dict[str, Any]:
    context: dict[str, Any] = {}
    for field in fields:
        value = _value(source, field)
        if value is not None and str(value).strip():
            context[field] = str(value).strip()
    return context


def _word_count(text: str) -> int:
    return len(WORD_PATTERN.findall(text))


def _validate_message_grounding(
    messages: GeneratedOutreach,
    profile_context: dict[str, Any],
    campaign_context: dict[str, Any],
) -> None:
    profile_text = " ".join(
        str(value) for value in profile_context.values()
    )
    campaign_text = " ".join(
        str(value) for value in campaign_context.values()
    )
    allowed_numbers = set(NUMBER_PATTERN.findall(profile_text + campaign_text))
    identity = str(
        profile_context.get("display_name")
        or profile_context.get("username")
        or ""
    )
    identity_terms = {
        token.casefold()
        for token in WORD_PATTERN.findall(identity)
        if len(token) > 1
    }
    profile_fact_text = " ".join(
        str(profile_context[field])
        for field in ("niche", "bio", "location")
        if field in profile_context
    )
    profile_terms = {
        token.casefold()
        for token in WORD_PATTERN.findall(profile_fact_text)
        if len(token) > 3 and token.casefold() not in NON_PERSONALIZATION_WORDS
    }

    if not identity_terms or not profile_terms:
        raise MessageValidationError(
            "A creator name and usable profile evidence are required "
            "for personalized outreach."
        )

    for label, text in (
        ("email subject", messages.email_subject),
        ("email body", messages.email_body),
        ("Instagram DM", messages.instagram_dm),
    ):
        if PLACEHOLDER_PATTERN.search(text):
            raise MessageValidationError(
                f"The generated {label} contains an unresolved placeholder."
            )
        terms = {token.casefold() for token in WORD_PATTERN.findall(text)}
        if not terms.intersection(identity_terms):
            raise MessageValidationError(
                f"The generated {label} does not identify the creator."
            )

    for label, text in (
        ("email body", messages.email_body),
        ("Instagram DM", messages.instagram_dm),
    ):
        terms = {token.casefold() for token in WORD_PATTERN.findall(text)}
        if not terms.intersection(profile_terms):
            raise MessageValidationError(
                f"The generated {label} is not grounded in a supplied "
                "creator profile fact."
            )
        unsupported_numbers = (
            set(NUMBER_PATTERN.findall(text)) - allowed_numbers
        )
        if unsupported_numbers:
            raise MessageValidationError(
                f"The generated {label} contains unsupported numeric claims."
            )


def generate_messages(
    influencer: Any,
    campaign: Any,
    provider: LLMProvider | None = None,
) -> GeneratedOutreach:
    profile_context = _prompt_context(
        influencer,
        (
            "display_name",
            "username",
            "platform",
            "niche",
            "bio",
            "location",
        ),
    )
    campaign_context = _prompt_context(
        campaign,
        ("name", "niche", "description"),
    )
    system_prompt, user_prompt = build_prompts(
        campaign=campaign_context,
        profile=profile_context,
    )
    selected_provider = provider or create_llm_provider()

    try:
        generated = GeneratedOutreach.model_validate_json(
            selected_provider.generate(system_prompt, user_prompt)
        )
    except (ValidationError, TypeError) as exc:
        raise MessageValidationError(
            "The provider response did not match the required JSON schema."
        ) from exc
    except json.JSONDecodeError as exc:
        raise MessageValidationError(
            "The provider response was not valid JSON."
        ) from exc

    email_words = _word_count(generated.email_body)
    if not 60 <= email_words <= 90:
        raise MessageValidationError(
            f"The email body must contain 60-90 words; got {email_words}."
        )

    dm_words = _word_count(generated.instagram_dm)
    if not 15 <= dm_words <= 30:
        raise MessageValidationError(
            f"The Instagram DM must contain 15-30 words; got {dm_words}."
        )

    _validate_message_grounding(
        generated,
        profile_context,
        campaign_context,
    )
    return generated


def generate_messages_for_qualified_influencers(
    db: Session,
    campaign: Campaign,
    influencers: Sequence[Influencer],
    provider: LLMProvider | None = None,
) -> list[OutreachMessage]:
    """Create validated, review-required drafts for already-qualified creators."""
    messages: list[OutreachMessage] = []
    try:
        selected_provider = provider
        for influencer in influencers:
            existing = db.scalars(
                select(OutreachMessage).where(
                    OutreachMessage.campaign_id == campaign.id,
                    OutreachMessage.influencer_id == influencer.id,
                )
            ).all()
            existing_by_channel = {
                message.channel: message for message in existing
            }
            email = existing_by_channel.get("email")
            dm = existing_by_channel.get("instagram_dm")

            new_messages: list[OutreachMessage] = []
            if email is None or dm is None:
                if selected_provider is None:
                    selected_provider = create_llm_provider()
                generated = generate_messages(
                    influencer,
                    campaign,
                    selected_provider,
                )
                if email is None:
                    email = OutreachMessage(
                        influencer_id=influencer.id,
                        campaign_id=campaign.id,
                        channel="email",
                        subject=generated.email_subject,
                        body=generated.email_body,
                        status="draft",
                    )
                    db.add(email)
                    new_messages.append(email)
                if dm is None:
                    dm = OutreachMessage(
                        influencer_id=influencer.id,
                        campaign_id=campaign.id,
                        channel="instagram_dm",
                        body=generated.instagram_dm,
                        status="draft",
                    )
                    db.add(dm)
                    new_messages.append(dm)
                db.flush()
                audit_details = json.dumps(
                    {
                        "provider": type(selected_provider).__name__,
                        "model": getattr(selected_provider, "model", None),
                        "prompt_version": PROMPT_VERSION,
                    },
                    sort_keys=True,
                )
                for message in new_messages:
                    db.add(
                        OutreachLog(
                            message_id=message.id,
                            event_type="generated",
                            details=audit_details,
                        )
                    )

            messages.extend((email, dm))

        db.commit()
        return messages
    except Exception:
        db.rollback()
        raise


def approve_outreach_message(
    db: Session,
    message_id: int,
) -> OutreachMessage:
    message = db.get(OutreachMessage, message_id)
    if message is None:
        raise LookupError(f"Outreach message {message_id} was not found.")
    if message.status == "approved":
        return message
    if message.status != "draft":
        raise ValueError(
            f"Cannot approve an outreach message in '{message.status}' status."
        )

    message.status = "approved"
    message.approved_at = datetime.now(timezone.utc)
    db.add(
        OutreachLog(
            message_id=message.id,
            event_type="approved",
        )
    )
    db.commit()
    db.refresh(message)
    return message
