import httpx

from app.services.llm.base import LLMProvider
from app.services.llm.exceptions import (
    LLMConfigurationError,
    LLMProviderError,
)


class GroqProvider(LLMProvider):
    endpoint = "https://api.groq.com/openai/v1/chat/completions"

    def __init__(self, api_key: str, model: str, timeout: float = 30.0) -> None:
        if not api_key.strip():
            raise LLMConfigurationError("GROQ_API_KEY is required.")
        if not model.strip():
            raise LLMConfigurationError("GROQ_MODEL is required.")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        try:
            response = httpx.post(
                self.endpoint,
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": self.model,
                    "temperature": 0.4,
                    "response_format": {"type": "json_object"},
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                },
                timeout=self.timeout,
            )
        except httpx.TimeoutException as exc:
            raise LLMProviderError("Groq request timed out.") from exc
        except httpx.HTTPError as exc:
            raise LLMProviderError("Groq request failed.") from exc

        if response.status_code == 429:
            raise LLMProviderError("Groq rate limit exceeded (HTTP 429).")
        if response.status_code in (401, 403):
            raise LLMProviderError(
                f"Groq authentication failed (HTTP {response.status_code})."
            )
        if not response.is_success:
            raise LLMProviderError(
                f"Groq request failed (HTTP {response.status_code})."
            )

        try:
            content = response.json()["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise LLMProviderError(
                "Groq returned an invalid chat-completion response."
            ) from exc
        if not isinstance(content, str) or not content.strip():
            raise LLMProviderError("Groq returned an empty response.")
        return content