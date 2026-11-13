from types import SimpleNamespace

from dashboard import data


class StubResponse:
    def __init__(self, value):
        self.value = value
        self.content = b"exported,csv\n"

    def json(self):
        return self.value


def test_authenticated_request_sends_configured_bearer_token(monkeypatch):
    token = "dashboard-client-test-token-with-32-characters"
    monkeypatch.setenv("DASHBOARD_API_TOKEN", token)
    observed = {}

    class HttpResponse:
        is_success = True
        text = ""
        content = b""

        def json(self):
            return {"status": "healthy"}

    def fake_http_request(method, url, *, headers, **kwargs):
        observed.update(method=method, url=url, headers=headers)
        return HttpResponse()

    monkeypatch.setattr(data.httpx, "request", fake_http_request)

    response = data._request("GET", "/health")

    assert response.json() == {"status": "healthy"}
    assert observed["headers"]["Authorization"] == f"Bearer {token}"


def test_list_influencers_maps_api_profiles_and_qualification(monkeypatch):
    profile = {
        "id": 7,
        "platform": "youtube",
        "username": "fit_jane",
        "display_name": "Jane",
        "followers_count": 25000,
        "qualification": {
            "overall_status": "accepted",
            "filter_reasons": [],
            "niche_reason": "Fitness content",
        },
    }
    calls = []

    def fake_request(method, path, *, params=None, **kwargs):
        calls.append((method, path, params))
        return StubResponse([profile])

    monkeypatch.setattr(data, "_request", fake_request)

    rows = data.list_influencers(search=" jane ", platform="youtube")

    assert len(rows) == 1
    creator, qualification = rows[0]
    assert isinstance(creator, SimpleNamespace)
    assert creator.username == "fit_jane"
    assert qualification["overall_status"] == "accepted"
    assert calls == [
        (
            "GET",
            "/influencers",
            {"limit": 500, "search": "jane", "platform": "youtube"},
        )
    ]


def test_campaign_creation_uses_fitness_api_payload(monkeypatch):
    calls = []

    def fake_request(method, path, *, json=None, **kwargs):
        calls.append((method, path, json))
        return StubResponse({"id": 12})

    monkeypatch.setattr(data, "_request", fake_request)

    campaign_id = data.create_campaign(
        "  Summer Move  ",
        "fitness",
        "  Accessible movement  ",
    )

    assert campaign_id == 12
    assert calls == [
        (
            "POST",
            "/campaigns",
            {
                "name": "Summer Move",
                "niche": "fitness",
                "description": "Accessible movement",
            },
        )
    ]


def test_reconciliation_sends_explicit_confirmation(monkeypatch):
    calls = []

    def fake_request(method, path, *, json=None, **kwargs):
        calls.append((method, path, json))
        return StubResponse({"id": 5, "status": "approved"})

    monkeypatch.setattr(data, "_request", fake_request)

    response = data.reconcile_delivery(5, confirmed_not_sent=True)

    assert response.status == "approved"
    assert calls == [
        (
            "POST",
            "/outreach/5/reconcile",
            {"confirmed_not_sent": True},
        )
    ]
