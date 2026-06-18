"""LiveKit worker entrypoint for inbound SIP calls."""

from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from typing import Any

from leasing_voice_assistant.core.config import Settings, get_settings
from leasing_voice_assistant.db.seed import seed_database
from leasing_voice_assistant.db.session import (
    create_session_factory,
    create_sqlite_engine,
    initialize_database,
    session_scope,
)
from leasing_voice_assistant.providers.errors import ProviderConfigurationError
from leasing_voice_assistant.providers.factory import ProviderFactory
from leasing_voice_assistant.worker.call_context import build_call_context
from leasing_voice_assistant.worker.prompts import initial_instructions
from leasing_voice_assistant.worker.tools import build_worker_tools


@dataclass(frozen=True)
class TurnDetectionConfig:
    """Conservative defaults for leasing phone conversations."""

    allow_interruptions: bool = True
    min_endpointing_delay_seconds: float = 0.7
    max_endpointing_delay_seconds: float = 3.0


def build_turn_detection_config() -> TurnDetectionConfig:
    """Return centralized turn-taking defaults for the worker runtime."""
    return TurnDetectionConfig()


def build_worker_config(settings: Settings | None = None) -> dict[str, str | None]:
    """Return the minimal worker configuration shape used by later milestones."""
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


def create_worker_options(settings: Settings | None = None) -> Any:
    """Create LiveKit worker options without importing LiveKit at module import time."""
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

    worker_options = agents.WorkerOptions
    return worker_options(
        entrypoint_fnc=job_entrypoint,
        ws_url=app_settings.livekit_url,
        api_key=app_settings.livekit_api_key,
        api_secret=app_settings.livekit_api_secret,
        agent_name=app_settings.livekit_agent_name,
        log_level=app_settings.log_level,
    )


async def job_entrypoint(ctx: Any) -> None:
    """Start one call-scoped LiveKit agent session."""
    settings = get_settings()
    provider_clients = build_provider_factory(settings).build_clients()
    engine = create_sqlite_engine(settings.database_url)
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    with session_scope(session_factory) as db_session:
        seed_database(db_session)

    await _maybe_await(ctx.connect())
    participant = await _wait_for_participant(ctx)
    context = build_call_context(
        room=getattr(ctx, "room", None),
        participant=participant,
    )

    with session_scope(session_factory) as db_session:
        state = context.to_call_state()
        tools = build_worker_tools(db_session, state)
        await _start_agent_session(
            ctx=ctx,
            provider_clients=provider_clients,
            tools=tools.as_livekit_tools(),
        )


async def _wait_for_participant(ctx: Any) -> Any | None:
    wait_for_participant = getattr(ctx, "wait_for_participant", None)
    if callable(wait_for_participant):
        return await _maybe_await(wait_for_participant())
    return None


async def _start_agent_session(
    *,
    ctx: Any,
    provider_clients: Any,
    tools: list[Any],
) -> None:
    agents = import_module("livekit.agents")
    agent_class = agents.Agent
    session_class = agents.AgentSession

    turn_config = build_turn_detection_config()
    session = session_class(
        stt=provider_clients.stt,
        llm=provider_clients.llm,
        tts=provider_clients.tts,
        allow_interruptions=turn_config.allow_interruptions,
        min_endpointing_delay=turn_config.min_endpointing_delay_seconds,
        max_endpointing_delay=turn_config.max_endpointing_delay_seconds,
    )
    agent = agent_class(instructions=initial_instructions(), tools=tools)
    await _maybe_await(session.start(room=ctx.room, agent=agent))


async def _maybe_await(value: Any) -> Any:
    if hasattr(value, "__await__"):
        return await value
    return value


def main() -> None:
    """Console-script entrypoint for the LiveKit worker."""
    settings = get_settings()
    options = create_worker_options(settings)
    agents = import_module("livekit.agents")
    cli = agents.cli
    cli.run_app(options)
