from urllib.parse import quote

import httpx

from app.services.llm.base import LLMProvider
from app.services.llm.exceptions import (
    LLMConfigurationError,
    LLMProviderError,
)


class GeminiProvider(LLMProvider):
    endpoint = "https://generativelanguage.googleapis.com/v1beta/models"

    def __init__(self, api_key: str, model: str, timeout: float = 30.0) -> None:
        if not api_key.strip():
            raise LLMConfigurationError("GEMINI_API_KEY is required.")
        if not model.strip():
            raise LLMConfigurationError("GEMINI_MODEL is required.")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        url = (
            f"{self.endpoint}/{quote(self.model, safe='')}:generateContent"
        )
        try:
            response = httpx.post(
                url,
                headers={"x-goog-api-key": self.api_key},
                json={
                    "systemInstruction": {
                        "parts": [{"text": system_prompt}],
                    },
                    "contents": [
                        {
                            "role": "user",
                            "parts": [{"text": user_prompt}],
                        }
                    ],
                    "generationConfig": {
                        "responseMimeType": "application/json",
                        "temperature": 0.4,
                    },
                },
                timeout=self.timeout,
            )
        except httpx.TimeoutException as exc:
            raise LLMProviderError("Gemini request timed out.") from exc
        except httpx.HTTPError as exc:
            raise LLMProviderError("Gemini request failed.") from exc

        if response.status_code == 429:
            raise LLMProviderError("Gemini rate limit exceeded (HTTP 429).")
        if response.status_code in (401, 403):
            raise LLMProviderError(
                f"Gemini authentication failed (HTTP {response.status_code})."
            )
        if not response.is_success:
            raise LLMProviderError(
                f"Gemini request failed (HTTP {response.status_code})."
            )

        try:
            content = response.json()["candidates"][0]["content"]["parts"][0][
                "text"
            ]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise LLMProviderError(
                "Gemini returned an invalid generate-content response."
            ) from exc
        if not isinstance(content, str) or not content.strip():
            raise LLMProviderError("Gemini returned an empty response.")
        return content