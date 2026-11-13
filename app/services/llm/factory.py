import os

from dotenv import load_dotenv

from app.services.llm.base import LLMProvider
from app.services.llm.exceptions import LLMConfigurationError
from app.services.llm.providers.gemini_provider import GeminiProvider
from app.services.llm.providers.groq_provider import GroqProvider


def create_llm_provider() -> LLMProvider:
    load_dotenv()
    provider = os.getenv("LLM_PROVIDER", "groq").strip().lower()

    if provider == "groq":
        return GroqProvider(
            api_key=os.getenv("GROQ_API_KEY", ""),
            model=os.getenv("GROQ_MODEL", ""),
        )
    if provider == "gemini":
        return GeminiProvider(
            api_key=os.getenv("GEMINI_API_KEY", ""),
            model=os.getenv("GEMINI_MODEL", ""),
        )
    raise LLMConfigurationError(
        "LLM_PROVIDER must be either 'groq' or 'gemini'."
    )