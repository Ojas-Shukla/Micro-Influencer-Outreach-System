
from app.services.filtering.niche_classifier import classify_niche


def test_fitness_channel():
    influencer = {
        "display_name": "Daily Fitness Workouts",
        "bio": "Gym training and muscle building tips."
    }

    result = classify_niche(influencer)

    assert result["classification"] == "fitness"
    assert "fitness" in result["matched_keywords"]


def test_not_fitness_channel():
    influencer = {
        "display_name": "Technology Reviews",
        "bio": "Latest smartphone and laptop reviews."
    }

    result = classify_niche(influencer)

    assert result["classification"] == "not_fitness"


def test_missing_information():
    influencer = {
        "display_name": None,
        "bio": None
    }

    result = classify_niche(influencer)

    assert result["classification"] == "needs_review"


def test_fitness_keyword_in_description():
    influencer = {
        "display_name": "Creator One",
        "bio": "I share strength training and workout routines."
    }

    result = classify_niche(influencer)

    assert result["classification"] == "fitness"
    assert "strength training" in result["matched_keywords"]
    assert "workout" in result["matched_keywords"]


def test_case_insensitive_matching():
    influencer = {
        "display_name": "FITNESS CREATOR",
        "bio": "GYM and WORKOUT videos."
    }

    result = classify_niche(influencer)

    assert result["classification"] == "fitness"


def test_unrelated_word_does_not_match_gym():
    influencer = {
        "display_name": "Gymnastics Academy",
        "bio": "Professional gymnastics tutorials."
    }

    result = classify_niche(influencer)

    assert "gym" not in result["matched_keywords"]
