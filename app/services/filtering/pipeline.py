from collections.abc import Mapping
from typing import Any, Dict, List

from app.services.filtering.influencer_filter import filter_influencer
from app.services.filtering.niche_classifier import classify_niche


def _profile_to_dict(influencer: Any) -> Dict[str, Any]:
    """
    Convert an influencer dictionary or model into a dictionary.
    The original profile is not modified.
    """
    if isinstance(influencer, Mapping):
        return dict(influencer)

    if hasattr(influencer, "model_dump"):
        return influencer.model_dump()

    if hasattr(influencer, "dict"):
        return influencer.dict()

    if hasattr(influencer, "__dict__"):
        return vars(influencer).copy()

    raise TypeError(
        "Influencer must be a dictionary or a supported model object."
    )


def process_influencer(influencer: Any) -> Dict[str, Any]:
    """
    Run follower filtering and niche classification as one pipeline.

    Outcomes:
        accepted: Passes follower filtering and matches target niche.
        rejected: Fails follower filtering or does not match target niche.
        needs_review: Requires manual niche verification.
    """

    profile = _profile_to_dict(influencer)

    # Default pipeline result
    result = {
        "profile": profile,
        "filter_status": "failed",
        "filter_reasons": [],
        "niche_status": "not_evaluated",
        "niche_reason": None,
        "matched_keywords": [],
        "manual_review_required": False,
        "overall_status": "rejected",
    }

    # STEP 1: Follower and platform filtering
    filter_result = filter_influencer(influencer)

    if not filter_result["eligible"]:
        result["filter_status"] = "failed"
        result["filter_reasons"] = list(
            filter_result.get("rejection_reasons", [])
        )

        # Do not classify profiles that fail eligibility checks.
        return result

    result["filter_status"] = "passed"

    # STEP 2: Niche classification
    niche_result = classify_niche(influencer)

    classification = niche_result["classification"]

    result["niche_status"] = classification
    result["niche_reason"] = niche_result.get("reason")
    result["matched_keywords"] = list(
        niche_result.get("matched_keywords", [])
    )

    # STEP 3: Determine final pipeline outcome
    if classification == "fitness":
        result["overall_status"] = "accepted"

    elif classification == "not_fitness":
        result["overall_status"] = "rejected"

    elif classification == "needs_review":
        result["overall_status"] = "needs_review"
        result["manual_review_required"] = True

    else:
        raise ValueError(
            f"Unexpected niche classification: {classification}"
        )

    return result


def process_influencers(
    influencers: List[Any],
) -> List[Dict[str, Any]]:
    """
    Process multiple influencer profiles through the same pipeline.

    Every input profile receives an output record.
    """
    return [
        process_influencer(influencer)
        for influencer in influencers
    ]
