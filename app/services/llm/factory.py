from app.core.config import get_settings
from app.services.llm.base import LLMProvider
from app.services.llm.exceptions import LLMConfigurationError
from app.services.llm.providers.gemini_provider import GeminiProvider
from app.services.llm.providers.groq_provider import GroqProvider


def create_llm_provider() -> LLMProvider:
    settings = get_settings()
    provider = settings.llm_provider.strip().lower()

    if provider == "groq":
        return GroqProvider(
            api_key=settings.groq_api_key,
            model=settings.groq_model,
        )
    if provider == "gemini":
        return GeminiProvider(
            api_key=settings.gemini_api_key,
            model=settings.gemini_model,
        )
    raise LLMConfigurationError(
        "LLM_PROVIDER must be either 'groq' or 'gemini'."
    )