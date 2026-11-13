from app.services.filtering.rules import (
    MIN_FOLLOWERS,
    MAX_FOLLOWERS,
    TARGET_PLATFORM,
    TARGET_NICHE
)


def get_value(influencer, field):
    """Support both dictionaries and SQLAlchemy model objects."""
    if isinstance(influencer, dict):
        return influencer.get(field)

    return getattr(influencer, field, None)


def filter_influencer(influencer):
    """
    Check whether an influencer meets basic eligibility criteria.

    Returns eligibility status and rejection reasons.
    """
    rejection_reasons = []

    # 1. Platform validation
    platform = get_value(influencer, "platform")

    if platform != TARGET_PLATFORM:
        rejection_reasons.append("Platform does not match")

    # 2. Subscriber count validation
    followers = get_value(influencer, "followers_count")

    if followers is None:
        rejection_reasons.append("Subscriber count unavailable")

    else:
        if followers < MIN_FOLLOWERS:
            rejection_reasons.append(
                f"Below minimum subscriber count ({MIN_FOLLOWERS})"
            )

        if followers > MAX_FOLLOWERS:
            rejection_reasons.append(
                f"Above maximum subscriber count ({MAX_FOLLOWERS})"
            )

    return {
        "eligible": len(rejection_reasons) == 0,
        "rejection_reasons": rejection_reasons,
    }
