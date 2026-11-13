import re

from app.services.filtering.rules import FITNESS_KEYWORDS


def get_value(influencer, field):
    """Support dictionaries and SQLAlchemy model objects."""
    if isinstance(influencer, dict):
        return influencer.get(field)

    return getattr(influencer, field, None)


def classify_niche(influencer):
    """
    Classify a YouTube channel using its title and description.

    Returns:
        fitness, not_fitness, or needs_review
    """

    title = get_value(influencer, "display_name") or ""
    description = get_value(influencer, "bio") or ""

    text = f"{title} {description}".lower().strip()

    # Insufficient information
    if not text:
        return {
            "classification": "needs_review",
            "matched_keywords": [],
            "reason": "Channel title and description are unavailable."
        }

    matched_keywords = []

    for keyword in FITNESS_KEYWORDS:
        pattern = (
            r"(?<!\w)" + re.escape(keyword.lower()) + r"(?!\w)"
        )

        if re.search(pattern, text):
            matched_keywords.append(keyword)

    if matched_keywords:
        return {
            "classification": "fitness",
            "matched_keywords": matched_keywords,
            "reason": "Fitness-related keywords found in channel information."
        }

    return {
        "classification": "not_fitness",
        "matched_keywords": [],
        "reason": "No configured fitness keywords found."
    }
