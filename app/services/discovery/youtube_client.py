import httpx

from app.core.config import get_settings

BASE_URL = "https://www.googleapis.com/youtube/v3"


class YouTubeAPIError(Exception):
    """Raised when the YouTube API request fails."""


def get_api_key():
    api_key = get_settings().youtube_api_key

    if not api_key:
        raise YouTubeAPIError(
            "YOUTUBE_API_KEY is missing. Check your .env file."
        )

    return api_key


def make_request(endpoint: str, params: dict):
    params["key"] = get_api_key()

    try:
        response = httpx.get(
            f"{BASE_URL}/{endpoint}",
            params=params,
            timeout=20.0
        )

        if response.status_code == 403:
            raise YouTubeAPIError(
                "YouTube API returned 403. Check API enablement, "
                "key restrictions, and quota."
            )

        if response.status_code == 429:
            raise YouTubeAPIError(
                "YouTube API rate limit reached. Try again later."
            )

        response.raise_for_status()
        return response.json()

    except httpx.TimeoutException as exc:
        raise YouTubeAPIError("YouTube API request timed out.") from exc

    except httpx.HTTPStatusError as exc:
        raise YouTubeAPIError(
            f"YouTube API HTTP error: {exc.response.status_code}"
        ) from exc

    except httpx.RequestError as exc:
        raise YouTubeAPIError(
            "Could not connect to YouTube API."
        ) from exc


def search_channels(query: str, max_pages: int = 1):
    if not query.strip():
        raise ValueError("Search query cannot be empty.")

    if not 1 <= max_pages <= 5:
        raise ValueError("max_pages must be between 1 and 5.")

    channel_ids = []
    next_page_token = None

    for _ in range(max_pages):
        params = {
            "part": "snippet",
            "type": "channel",
            "q": query,
            "maxResults": 50,
            "order": "relevance"
        }

        if next_page_token:
            params["pageToken"] = next_page_token

        data = make_request("search", params)

        for item in data.get("items", []):
            channel_id = item.get("id", {}).get("channelId")

            if channel_id and channel_id not in channel_ids:
                channel_ids.append(channel_id)

        next_page_token = data.get("nextPageToken")

        if not next_page_token:
            break

    return channel_ids


def fetch_channel_details(channel_ids: list[str]):
    if not channel_ids:
        return []

    # The channels.list endpoint accepts up to 50 IDs per request.
    all_channels = []

    for start in range(0, len(channel_ids), 50):
        batch = channel_ids[start:start + 50]

        params = {
            "part": "snippet,statistics",
            "id": ",".join(batch),
            "maxResults": 50
        }

        data = make_request("channels", params)
        all_channels.extend(data.get("items", []))

    return all_channels


def normalize_channel(channel: dict):
    channel_id = channel.get("id")

    if not channel_id:
        return None

    snippet = channel.get("snippet", {})
    statistics = channel.get("statistics", {})

    custom_url = snippet.get("customUrl")
    username = custom_url.lstrip("@") if custom_url else channel_id

    return {
        "platform": "youtube",
        "platform_user_id": channel_id,
        "username": username,
        "display_name": snippet.get("title"),
        "profile_url": f"https://www.youtube.com/channel/{channel_id}",
        "niche": None,
        "bio": snippet.get("description"),
        "followers_count": (
            int(statistics["subscriberCount"])
            if statistics.get("subscriberCount") is not None
            else None
        ),
        "following_count": None,
        "posts_count": (
            int(statistics["videoCount"])
            if statistics.get("videoCount") is not None
            else None
        ),
        "avg_likes": None,
        "avg_comments": None,
        "engagement_rate": None,
        "email": None,
        "location": snippet.get("country"),
        "is_verified": False,
        "source": "youtube_data_api_v3"
    }