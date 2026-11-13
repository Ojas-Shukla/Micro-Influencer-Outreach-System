from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_env: str = "development"
    database_url: str = "sqlite:///./data/micro_influencer.db"
    youtube_api_key: str = ""

    llm_provider: str = "groq"
    groq_api_key: str = ""
    groq_model: str = ""
    gemini_api_key: str = ""
    gemini_model: str = ""

    email_mode: str = "dry_run"
    allow_real_email_send: bool = False
    gmail_sender: str = ""
    google_oauth_client_secrets: str = ".secrets/google-oauth-client.json"
    gmail_token_file: str = ".secrets/gmail-token.json"

    target_niche: str = "fitness"
    min_followers: int = Field(default=10_000, ge=0)
    max_followers: int = Field(default=100_000, ge=0)

    @property
    def gmail_send_enabled(self) -> bool:
        return (
            self.email_mode == "gmail"
            and self.allow_real_email_send
        )


def get_settings() -> Settings:
    """Load application settings from environment and the local .env file."""
    return Settings()