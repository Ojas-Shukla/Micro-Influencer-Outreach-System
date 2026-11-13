import pytest

from app.core.config import Settings


def test_settings_load_environment_values(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./test.db")
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("EMAIL_MODE", "gmail")
    monkeypatch.setenv("ALLOW_REAL_EMAIL_SEND", "true")
    monkeypatch.setenv("TARGET_NICHE", "fitness")
    monkeypatch.setenv("MIN_FOLLOWERS", "12000")
    monkeypatch.setenv("MAX_FOLLOWERS", "90000")

    settings = Settings(_env_file=None)

    assert settings.database_url == "sqlite:///./test.db"
    assert settings.llm_provider == "gemini"
    assert settings.gemini_api_key == "test-key"
    assert settings.gmail_send_enabled is True
    assert settings.target_niche == "fitness"
    assert settings.min_followers == 12_000
    assert settings.max_followers == 90_000


def test_email_is_disabled_unless_both_settings_enable_gmail():
    assert Settings(
        _env_file=None,
        email_mode="gmail",
        allow_real_email_send=False,
    ).gmail_send_enabled is False
    assert Settings(
        _env_file=None,
        email_mode="dry_run",
        allow_real_email_send=True,
    ).gmail_send_enabled is False
    assert Settings(
        _env_file=None,
        email_mode="gmail",
        allow_real_email_send=True,
    ).gmail_send_enabled is True


def test_settings_keep_safe_default_configuration():
    settings = Settings(_env_file=None)

    assert settings.email_mode == "dry_run"
    assert settings.allow_real_email_send is False
    assert settings.database_url == "sqlite:///./data/micro_influencer.db"
    assert settings.llm_provider == "groq"


def test_dashboard_login_is_required_outside_development_and_for_live_email():
    assert Settings(
        _env_file=None,
        app_env="development",
        email_mode="dry_run",
    ).dashboard_login_required is False
    assert Settings(
        _env_file=None,
        app_env="production",
    ).dashboard_login_required is True


def test_settings_reject_unsupported_niche_and_invalid_follower_range():
    with pytest.raises(ValueError, match="fitness"):
        Settings(_env_file=None, target_niche="beauty")

    with pytest.raises(ValueError, match="MAX_FOLLOWERS"):
        Settings(
            _env_file=None,
            min_followers=100_000,
            max_followers=10_000,
        )
    assert Settings(
        _env_file=None,
        app_env="development",
        email_mode="gmail",
        allow_real_email_send=True,
    ).dashboard_login_required is True
