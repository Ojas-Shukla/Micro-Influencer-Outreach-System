import pytest

from app.services.filtering import pipeline


@pytest.fixture
def influencer():
    return {
        "display_name": "Fitness Creator",
        "platform": "youtube",
        "subscriber_count": 25000,
        "bio": "Fitness and workout content",
    }


def test_pipeline_accepts_eligible_fitness_profile(
    monkeypatch, influencer
):
    monkeypatch.setattr(
        pipeline,
        "filter_influencer",
        lambda profile: {
            "eligible": True,
            "rejection_reasons": [],
        },
    )

    monkeypatch.setattr(
        pipeline,
        "classify_niche",
        lambda profile: {
            "classification": "fitness",
            "matched_keywords": ["fitness", "workout"],
            "reason": "Fitness keywords detected",
        },
    )

    result = pipeline.process_influencer(influencer)

    assert result["filter_status"] == "passed"
    assert result["niche_status"] == "fitness"
    assert result["overall_status"] == "accepted"
    assert result["manual_review_required"] is False
    assert result["filter_reasons"] == []
    assert "fitness" in result["matched_keywords"]


def test_pipeline_rejects_ineligible_profile(
    monkeypatch, influencer
):
    reasons = ["Follower count below minimum"]

    monkeypatch.setattr(
        pipeline,
        "filter_influencer",
        lambda profile: {
            "eligible": False,
            "rejection_reasons": reasons,
        },
    )

    def classifier_should_not_run(profile):
        pytest.fail("Classifier should not run for rejected profiles")

    monkeypatch.setattr(
        pipeline,
        "classify_niche",
        classifier_should_not_run,
    )

    result = pipeline.process_influencer(influencer)

    assert result["filter_status"] == "failed"
    assert result["filter_reasons"] == reasons
    assert result["niche_status"] == "not_evaluated"
    assert result["overall_status"] == "rejected"


def test_pipeline_rejects_wrong_niche(
    monkeypatch, influencer
):
    monkeypatch.setattr(
        pipeline,
        "filter_influencer",
        lambda profile: {
            "eligible": True,
            "rejection_reasons": [],
        },
    )

    monkeypatch.setattr(
        pipeline,
        "classify_niche",
        lambda profile: {
            "classification": "not_fitness",
            "matched_keywords": ["technology"],
            "reason": "Content is unrelated to fitness",
        },
    )

    result = pipeline.process_influencer(influencer)

    assert result["filter_status"] == "passed"
    assert result["niche_status"] == "not_fitness"
    assert result["overall_status"] == "rejected"
    assert result["manual_review_required"] is False


def test_pipeline_marks_ambiguous_profile_for_review(
    monkeypatch, influencer
):
    monkeypatch.setattr(
        pipeline,
        "filter_influencer",
        lambda profile: {
            "eligible": True,
            "rejection_reasons": [],
        },
    )

    monkeypatch.setattr(
        pipeline,
        "classify_niche",
        lambda profile: {
            "classification": "needs_review",
            "matched_keywords": ["lifestyle"],
            "reason": "Insufficient niche evidence",
        },
    )

    result = pipeline.process_influencer(influencer)

    assert result["overall_status"] == "needs_review"
    assert result["manual_review_required"] is True
    assert result["niche_reason"] == "Insufficient niche evidence"


def test_pipeline_preserves_matched_keywords(
    monkeypatch, influencer
):
    keywords = ["gym", "workout", "nutrition"]

    monkeypatch.setattr(
        pipeline,
        "filter_influencer",
        lambda profile: {
            "eligible": True,
            "rejection_reasons": [],
        },
    )

    monkeypatch.setattr(
        pipeline,
        "classify_niche",
        lambda profile: {
            "classification": "fitness",
            "matched_keywords": keywords,
            "reason": "Multiple fitness keywords detected",
        },
    )

    result = pipeline.process_influencer(influencer)

    assert result["matched_keywords"] == keywords


def test_pipeline_rejects_unknown_classification(
    monkeypatch, influencer
):
    monkeypatch.setattr(
        pipeline,
        "filter_influencer",
        lambda profile: {
            "eligible": True,
            "rejection_reasons": [],
        },
    )

    monkeypatch.setattr(
        pipeline,
        "classify_niche",
        lambda profile: {
            "classification": "unknown_status",
            "matched_keywords": [],
            "reason": "Unknown classification",
        },
    )

    with pytest.raises(ValueError):
        pipeline.process_influencer(influencer)


def test_pipeline_processes_multiple_profiles(
    monkeypatch, influencer
):
    monkeypatch.setattr(
        pipeline,
        "filter_influencer",
        lambda profile: {
            "eligible": True,
            "rejection_reasons": [],
        },
    )

    monkeypatch.setattr(
        pipeline,
        "classify_niche",
        lambda profile: {
            "classification": "fitness",
            "matched_keywords": ["fitness"],
            "reason": "Fitness content detected",
        },
    )

    profiles = [
        influencer,
        {**influencer, "display_name": "Creator Two"},
        {**influencer, "display_name": "Creator Three"},
    ]

    results = pipeline.process_influencers(profiles)

    assert len(results) == 3
    assert all(
        result["overall_status"] == "accepted"
        for result in results
    )
