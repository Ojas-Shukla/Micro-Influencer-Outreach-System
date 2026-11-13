import httpx
import pytest

from app.services.llm.exceptions import (
    LLMConfigurationError,
    LLMProviderError,
)
from app.services.llm.factory import create_llm_provider
from app.services.llm.providers.gemini_provider import GeminiProvider
from app.services.llm.providers.groq_provider import GroqProvider


@pytest.mark.parametrize(
    ("provider", "response_data", "expected_text"),
    [
        (
            GroqProvider("secret", "groq-model"),
            {"choices": [{"message": {"content": '{"ok": true}'}}]},
            '{"ok": true}',
        ),
        (
            GeminiProvider("secret", "gemini-model"),
            {
                "candidates": [
                    {"content": {"parts": [{"text": '{"ok": true}'}]}}
                ]
            },
            '{"ok": true}',
        ),
    ],
)
def test_provider_extracts_generated_content(
    monkeypatch,
    provider,
    response_data,
    expected_text,
):
    def fake_post(url, **kwargs):
        assert kwargs["timeout"] == provider.timeout
        return httpx.Response(200, json=response_data)

    monkeypatch.setattr("httpx.post", fake_post)

    assert provider.generate("system", "user") == expected_text


@pytest.mark.parametrize(
    ("provider_class", "key", "model"),
    [
        (GroqProvider, "", "model"),
        (GroqProvider, "key", ""),
        (GeminiProvider, "", "model"),
        (GeminiProvider, "key", ""),
    ],
)
def test_provider_requires_credentials_and_model(provider_class, key, model):
    with pytest.raises(LLMConfigurationError):
        provider_class(key, model)


@pytest.mark.parametrize(
    ("provider_class", "response"),
    [
        (GroqProvider, httpx.Response(429)),
        (GeminiProvider, httpx.Response(429)),
        (GroqProvider, httpx.Response(200, json={})),
        (GeminiProvider, httpx.Response(200, json={})),
    ],
)
def test_provider_surfaces_rate_limits_and_invalid_responses(
    monkeypatch,
    provider_class,
    response,
):
    monkeypatch.setattr("httpx.post", lambda *args, **kwargs: response)

    with pytest.raises(LLMProviderError):
        provider_class("key", "model").generate("system", "user")


@pytest.mark.parametrize(
    ("provider_name", "key_name", "model_name", "provider_class"),
    [
        ("groq", "GROQ_API_KEY", "GROQ_MODEL", GroqProvider),
        ("gemini", "GEMINI_API_KEY", "GEMINI_MODEL", GeminiProvider),
    ],
)
def test_factory_selects_configured_provider(
    monkeypatch,
    provider_name,
    key_name,
    model_name,
    provider_class,
):
    monkeypatch.setenv("LLM_PROVIDER", provider_name)
    monkeypatch.setenv(key_name, "test-key")
    monkeypatch.setenv(model_name, "test-model")

    assert isinstance(create_llm_provider(), provider_class)


def test_factory_rejects_unknown_provider(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "unknown")

    with pytest.raises(LLMConfigurationError):
        create_llm_provider()
