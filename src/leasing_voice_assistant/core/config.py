"""Typed runtime configuration."""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables and optional .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Leasing Voice Assistant"
    app_version: str = "0.1.0"
    app_env: str = "local"
    log_level: str = "INFO"

    api_host: str = "127.0.0.1"
    api_port: int = 8000

    database_url: str = "sqlite:///leasing_voice_assistant.db"

    livekit_url: str | None = None
    livekit_api_key: str | None = None
    livekit_api_secret: str | None = None
    livekit_agent_name: str = ""
    voice_metrics_path: str = "metrics/voice_metrics.jsonl"
    grounding_mode: Literal["hybrid", "legacy_tools"] = "hybrid"
    grounding_deadline_ms: int = Field(default=75, ge=1, le=1000)

    stt_provider: Literal["deepgram"] = "deepgram"
    tts_provider: Literal["deepgram"] = "deepgram"
    llm_provider: Literal["openrouter", "openai"] = "openrouter"

    deepgram_api_key: str | None = Field(default=None, repr=False)
    deepgram_stt_model: str = "nova-3"
    deepgram_tts_model: str = "aura-2-thalia-en"

    openrouter_api_key: str | None = Field(default=None, repr=False)
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_model: str = "openai/gpt-4o-mini"

    openai_api_key: str | None = Field(default=None, repr=False)
    openai_model: str = "gpt-4o-mini"


@lru_cache
def get_settings() -> Settings:
    """Return cached process settings."""
    return Settings()
