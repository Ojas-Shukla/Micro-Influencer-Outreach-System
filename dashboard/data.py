from types import SimpleNamespace
from typing import Any

import httpx

from app.core.config import get_settings


class DashboardAPIError(RuntimeError):
    """The dashboard could not complete its authenticated API request."""


def _request(
    method: str,
    path: str,
    *,
    json: dict[str, Any] | None = None,
    content: bytes | None = None,
    params: dict[str, Any] | None = None,
) -> httpx.Response:
    settings = get_settings()
    token = settings.dashboard_api_token
    if len(token) < 32:
        raise DashboardAPIError(
            "Configure DASHBOARD_API_TOKEN with at least 32 characters "
            "in .env, then restart the API and dashboard."
        )

    try:
        response = httpx.request(
            method,
            f"{settings.api_base_url.rstrip('/')}/{path.lstrip('/')}",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "text/csv" if content is not None else "application/json",
            },
            json=json,
            content=content,
            params=params,
            timeout=30.0,
        )
    except httpx.TimeoutException as exc:
        raise DashboardAPIError("The API request timed out.") from exc
    except httpx.HTTPError as exc:
        raise DashboardAPIError(
            "Could not connect to the API. Start the backend and check API_BASE_URL."
        ) from exc

    if not response.is_success:
        try:
            detail = response.json().get("detail", response.text)
        except ValueError:
            detail = response.text
        raise DashboardAPIError(f"API error ({response.status_code}): {detail}")
    return response


def import_csv_content(content: bytes) -> dict[str, Any]:
    return _request("POST", "/discovery/import-csv", content=content).json()


def discover_youtube(query: str, pages: int) -> dict[str, int]:
    return _request(
        "POST",
        "/discovery/youtube",
        json={"query": query, "pages": pages},
    ).json()


def list_influencers(
    search: str = "",
    platform: str = "All",
) -> list[tuple[SimpleNamespace, dict[str, Any]]]:
    params: dict[str, Any] = {"limit": 500}
    if search.strip():
        params["search"] = search.strip()
    if platform != "All":
        params["platform"] = platform.lower()
    response = _request("GET", "/influencers", params=params)
    return [
        (SimpleNamespace(**item), item["qualification"])
        for item in response.json()
    ]


def list_campaigns() -> list[SimpleNamespace]:
    return [
        SimpleNamespace(**campaign)
        for campaign in _request("GET", "/campaigns").json()
    ]


def create_campaign(name: str, niche: str, description: str) -> int:
    campaign = _request(
        "POST",
        "/campaigns",
        json={
            "name": name.strip(),
            "niche": niche.strip(),
            "description": description.strip() or None,
        },
    ).json()
    return campaign["id"]


def generate_campaign_messages(campaign_id: int) -> list[SimpleNamespace]:
    return [
        SimpleNamespace(**message)
        for message in _request(
            "POST",
            f"/campaigns/{campaign_id}/messages/generate",
        ).json()["messages"]
    ]


def list_campaign_messages(
    campaign_id: int | None = None,
) -> list[tuple[SimpleNamespace, SimpleNamespace]]:
    params = {"campaign_id": campaign_id} if campaign_id is not None else None
    messages = _request("GET", "/messages", params=params).json()
    return [
        (
            SimpleNamespace(**message),
            SimpleNamespace(**message["influencer"]),
        )
        for message in messages
    ]


def update_draft(
    message_id: int,
    subject: str | None,
    body: str,
) -> SimpleNamespace:
    return SimpleNamespace(
        **_request(
            "PATCH",
            f"/messages/{message_id}",
            json={"subject": subject, "body": body},
        ).json()
    )


def approve_message(message_id: int) -> SimpleNamespace:
    return SimpleNamespace(
        **_request("POST", f"/messages/{message_id}/approve").json()
    )


def dry_run_message(message_id: int) -> SimpleNamespace:
    return SimpleNamespace(
        **_request("POST", f"/outreach/{message_id}/dry-run").json()
    )


def send_email(message_id: int) -> SimpleNamespace:
    return SimpleNamespace(
        **_request("POST", f"/outreach/{message_id}/send").json()
    )


def mark_dm_sent(message_id: int) -> SimpleNamespace:
    return SimpleNamespace(
        **_request("POST", f"/outreach/{message_id}/mark-dm-sent").json()
    )


def reconcile_delivery(
    message_id: int,
    *,
    confirmed_not_sent: bool = False,
) -> SimpleNamespace:
    return SimpleNamespace(
        **_request(
            "POST",
            f"/outreach/{message_id}/reconcile",
            json={"confirmed_not_sent": confirmed_not_sent},
        ).json()
    )


def list_outreach_history() -> list[dict[str, Any]]:
    return _request("GET", "/outreach/logs", params={"limit": 500}).json()


def export_influencers_csv() -> bytes:
    return _request("GET", "/exports/influencers").content


def export_outreach_csv() -> bytes:
    return _request("GET", "/exports/outreach").content
