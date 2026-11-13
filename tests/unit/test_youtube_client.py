import pytest

from app.services.discovery.youtube_client import (
    normalize_channel,
    search_channels,
    fetch_channel_details,
    YouTubeAPIError
)


def test_normalize_channel():
    channel = {
        "id": "UC123456",
        "snippet": {
            "title": "Fitness Creator",
            "description": "Fitness videos",
            "customUrl": "@fitnesscreator",
            "country": "IN"
        },
        "statistics": {
            "subscriberCount": "25000",
            "videoCount": "120"
        }
    }

    result = normalize_channel(channel)

    assert result["platform"] == "youtube"
    assert result["platform_user_id"] == "UC123456"
    assert result["username"] == "fitnesscreator"
    assert result["followers_count"] == 25000
    assert result["posts_count"] == 120
    assert result["email"] is None


def test_normalize_channel_with_hidden_subscribers():
    channel = {
        "id": "UC789",
        "snippet": {
            "title": "Private Stats Creator",
            "description": "",
            "country": "IN"
        },
        "statistics": {
            "videoCount": "20"
        }
    }

    result = normalize_channel(channel)

    assert result["followers_count"] is None
    assert result["posts_count"] == 20


def test_normalize_channel_without_id():
    assert normalize_channel({}) is None


def test_search_channels_empty_query():
    with pytest.raises(ValueError):
        search_channels("")


def test_search_channels_invalid_pages():
    with pytest.raises(ValueError):
        search_channels("fitness", max_pages=6)


def test_fetch_channel_details_empty_ids():
    assert fetch_channel_details([]) == []


def test_search_channels_api_failure(monkeypatch):
    def mock_request(endpoint, params):
        raise YouTubeAPIError("Simulated API error")

    monkeypatch.setattr(
        "app.services.discovery.youtube_client.make_request",
        mock_request
    )

    with pytest.raises(YouTubeAPIError):
        search_channels("fitness creators India")