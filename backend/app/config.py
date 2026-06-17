"""Application configuration, loaded from environment variables.

Local development falls back to sane defaults (SQLite, no external keys),
so the full pipeline can run end-to-end without any accounts. Production
values are injected by Railway's secret manager.
"""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Database ---------------------------------------------------------
    # SQLite locally; Railway injects a postgresql:// URL in production.
    database_url: str = "sqlite:///./quantrix.db"

    # --- Gemini (post generation, primary — free tier available) ----------
    gemini_api_key: str = ""
    # gemini-2.0-flash: free tier, fast, more than capable for 5 posts/day
    gemini_model: str = "gemini-flash-lite-latest"

    # --- OpenAI (post generation, secondary fallback) --------------------
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    # --- Anthropic (post generation, kept as fallback) -------------------
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-6"
    # When no key is set we fall back to a deterministic mock generator so
    # the pipeline remains testable offline.
    use_mock_generator: bool = False

    # --- Email digest (Gmail SMTP) ---------------------------------------
    gmail_address: str = ""          # sender Gmail account
    gmail_app_password: str = ""     # 16-char Google App Password
    notification_email: str = "quantrixlabs@gmail.com"  # recipient
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 465             # SSL

    # --- Image providers (all optional; Openverse + Wikimedia need no key) --
    unsplash_access_key: str = ""
    pexels_api_key: str = ""
    pixabay_api_key: str = ""

    # --- App wiring -------------------------------------------------------
    frontend_url: str = "http://localhost:5173"
    # Shared secret guarding the internal /run/pipeline endpoint that the
    # Railway cron job calls. Generate a random value in production.
    cron_secret: str = "dev-local-secret"
    posts_per_run: int = 5
    # Days a topic is considered "recently posted" and should be skipped
    # unless flagged pivotal. History retained ~2 weeks (see retention).
    novelty_window_days: int = 7
    history_retention_days: int = 14

    @property
    def has_gemini(self) -> bool:
        return bool(self.gemini_api_key) and not self.use_mock_generator

    @property
    def has_openai(self) -> bool:
        return bool(self.openai_api_key) and not self.use_mock_generator

    @property
    def has_anthropic(self) -> bool:
        return bool(self.anthropic_api_key) and not self.use_mock_generator

    @property
    def has_email(self) -> bool:
        return bool(self.gmail_address and self.gmail_app_password)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
