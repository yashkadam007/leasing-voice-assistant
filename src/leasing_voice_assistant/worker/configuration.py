"""Configuration and process setup for the LiveKit worker."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from importlib import import_module
from typing import Any

from leasing_voice_assistant.core.config import Settings, get_settings
from leasing_voice_assistant.providers.errors import ProviderConfigurationError
from leasing_voice_assistant.providers.factory import ProviderFactory


@dataclass(frozen=True)
class TurnDetectionConfig:
    """Low-latency defaults for leasing phone conversations."""

    allow_interruptions: bool = True
    min_endpointing_delay_seconds: float = 0.5
    max_endpointing_delay_seconds: float = 1.0
    min_interruption_duration_seconds: float = 0.5
    min_interruption_words: int = 0


def build_turn_detection_config() -> TurnDetectionConfig:
    """Return centralized turn-taking defaults for the worker runtime."""
    return TurnDetectionConfig()


def build_turn_handling_options(
    agents: Any,
    turn_config: TurnDetectionConfig | None = None,
) -> Any:
    """Return LiveKit turn handling options without deprecated session kwargs."""
    config = turn_config or build_turn_detection_config()
    return agents.TurnHandlingOptions(
        turn_detection=agents.inference.TurnDetector(),
        endpointing={
            "mode": "fixed",
            "min_delay": config.min_endpointing_delay_seconds,
            "max_delay": config.max_endpointing_delay_seconds,
        },
        interruption={
            "enabled": config.allow_interruptions,
            "mode": "adaptive",
            "min_duration": config.min_interruption_duration_seconds,
            "min_words": config.min_interruption_words,
        },
    )


def build_worker_config(settings: Settings | None = None) -> dict[str, str | None]:
    """Return the worker's externally relevant configuration."""
    app_settings = settings or get_settings()
    return {
        "environment": app_settings.app_env,
        "livekit_url": app_settings.livekit_url,
        "stt_provider": app_settings.stt_provider,
        "tts_provider": app_settings.tts_provider,
        "llm_provider": app_settings.llm_provider,
    }


def build_provider_factory(settings: Settings | None = None) -> ProviderFactory:
    """Return the worker provider factory without constructing runtime clients."""
    return ProviderFactory(settings or get_settings())


def validate_livekit_settings(settings: Settings) -> None:
    """Fail fast when starting the real worker without LiveKit credentials."""
    missing = [
        name
        for name, value in (
            ("LIVEKIT_URL", settings.livekit_url),
            ("LIVEKIT_API_KEY", settings.livekit_api_key),
            ("LIVEKIT_API_SECRET", settings.livekit_api_secret),
        )
        if value is None or not value.strip()
    ]
    if missing:
        raise ProviderConfigurationError(
            "livekit",
            "worker",
            "missing required setting " + ", ".join(missing),
        )


def create_worker_options(
    settings: Settings | None = None,
    *,
    entrypoint_fnc: Callable[[Any], Any] | None = None,
) -> Any:
    """Create LiveKit worker options without importing LiveKit at import time."""
    app_settings = settings or get_settings()
    validate_livekit_settings(app_settings)

    try:
        agents = import_module("livekit.agents")
    except ImportError as exc:
        raise ProviderConfigurationError(
            "livekit",
            "worker",
            "missing optional package livekit-agents",
        ) from exc

    if entrypoint_fnc is None:
        from leasing_voice_assistant.worker.main import job_entrypoint

        entrypoint_fnc = job_entrypoint

    return agents.WorkerOptions(
        entrypoint_fnc=entrypoint_fnc,
        ws_url=app_settings.livekit_url,
        api_key=app_settings.livekit_api_key,
        api_secret=app_settings.livekit_api_secret,
        agent_name=app_settings.livekit_agent_name,
        log_level=app_settings.log_level,
    )
