from pydantic import Field, field_validator, model_validator
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
    api_base_url: str = "http://127.0.0.1:8000"
    dashboard_api_token: str = ""
    dashboard_login_password: str = ""
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

    @field_validator("target_niche", mode="before")
    @classmethod
    def enforce_supported_niche(cls, value: str) -> str:
        normalized = str(value).strip().lower()
        if normalized != "fitness":
            raise ValueError(
                "Only the fitness niche is currently implemented."
            )
        return normalized

    @field_validator("llm_provider", "email_mode", mode="before")
    @classmethod
    def normalize_provider_modes(cls, value: str) -> str:
        return str(value).strip().lower()

    @model_validator(mode="after")
    def validate_follower_range(self) -> "Settings":
        if self.max_followers < self.min_followers:
            raise ValueError(
                "MAX_FOLLOWERS must be greater than or equal to MIN_FOLLOWERS."
            )
        return self

    @property
    def gmail_send_enabled(self) -> bool:
        return (
            self.email_mode == "gmail"
            and self.allow_real_email_send
        )

    @property
    def dashboard_login_required(self) -> bool:
        return (
            self.app_env.strip().casefold() != "development"
            or self.gmail_send_enabled
        )


def get_settings() -> Settings:
    """Load application settings from environment and the local .env file."""
    return Settings()