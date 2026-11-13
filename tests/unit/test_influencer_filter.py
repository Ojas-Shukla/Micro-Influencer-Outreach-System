from app.services.filtering.influencer_filter import filter_influencer

def test_eligible_influencer():
    influencer = {
        "platform": "youtube",
        "followers_count": 25000,
    }

    result = filter_influencer(influencer)

    assert result["eligible"] is True
    assert result["rejection_reasons"] == []

def test_below_minimum_followers():
    influencer = {
        "platform": "youtube",
        "followers_count": 5000,
    }

    result = filter_influencer(influencer)

    assert result["eligible"] is False

def test_above_maximum_followers():
    influencer = {
        "platform": "youtube",
        "followers_count": 150000,
    }

    result = filter_influencer(influencer)

    assert result["eligible"] is False

def test_missing_subscriber_count():
    influencer = {
        "platform": "youtube",
        "followers_count": None,
    }

    result = filter_influencer(influencer)

    assert result["eligible"] is False

def test_wrong_platform():
    influencer = {
        "platform": "instagram",
        "followers_count": 25000,
    }

    result = filter_influencer(influencer)

    assert result["eligible"] is False

def test_rejection_reasons():
    influencer = {
        "platform": "instagram",
        "followers_count": 5000,
    }

    result = filter_influencer(influencer)

    assert result["eligible"] is False
    assert len(result["rejection_reasons"]) == 2