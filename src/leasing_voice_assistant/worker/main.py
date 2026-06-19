"""LiveKit worker entrypoint for inbound SIP calls."""

from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import dataclass
from importlib import import_module
from typing import Any

from leasing_voice_assistant.agent.grounding import GroundedTurnContextBuilder
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
from leasing_voice_assistant.worker.agent import GroundingCoordinator, LeasingVoiceAgent
from leasing_voice_assistant.worker.call_context import build_call_context
from leasing_voice_assistant.worker.metrics import CallMetricsRecorder, JsonlMetricsWriter
from leasing_voice_assistant.worker.prompts import initial_greeting, initial_instructions
from leasing_voice_assistant.worker.tools import build_worker_tools

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TurnDetectionConfig:
    """Low-latency defaults for leasing phone conversations."""

    allow_interruptions: bool = True
    min_endpointing_delay_seconds: float = 0.8
    max_endpointing_delay_seconds: float = 1.5
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
    connected_at = time.monotonic()
    participant = await _wait_for_participant(ctx)
    context = build_call_context(
        room=getattr(ctx, "room", None),
        participant=participant,
    )
    call_metrics = CallMetricsRecorder(
        call_id=context.call_sid or f"call-{uuid.uuid4()}",
        writer=JsonlMetricsWriter(settings.voice_metrics_path),
        connected_at=connected_at,
    )

    with session_scope(session_factory) as db_session:
        state = context.to_call_state()
        tools = build_worker_tools(db_session, state, record_tool=call_metrics.record_tool)
        await _start_agent_session(
            ctx=ctx,
            provider_clients=provider_clients,
            worker_tools=tools,
            state=state,
            db_session=db_session,
            settings=settings,
            call_metrics=call_metrics,
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
    worker_tools: Any,
    state: Any,
    db_session: Any,
    settings: Settings,
    call_metrics: CallMetricsRecorder,
) -> None:
    agents = import_module("livekit.agents")
    session_class = agents.AgentSession

    turn_config = build_turn_detection_config()
    session = session_class(
        stt=provider_clients.stt,
        llm=provider_clients.llm,
        tts=provider_clients.tts,
        turn_handling=build_turn_handling_options(agents, turn_config),
    )
    install_session_logging(session, call_metrics=call_metrics)
    if settings.grounding_mode == "hybrid":
        coordinator = GroundingCoordinator(
            interruption_duration_seconds=turn_config.min_interruption_duration_seconds
        )
        coordinator.bind(session)
        agent = LeasingVoiceAgent(
            instructions=initial_instructions(),
            tools=[worker_tools.capture_as_livekit_tool()],
            builder=GroundedTurnContextBuilder(
                db_session,
                deadline_ms=settings.grounding_deadline_ms,
            ),
            state=state,
            coordinator=coordinator,
            metrics=call_metrics,
        )
    else:
        agent = agents.Agent(
            instructions=initial_instructions(),
            tools=worker_tools.as_livekit_tools(),
        )
    await _maybe_await(session.start(room=ctx.room, agent=agent))
    session.say(initial_greeting(), allow_interruptions=True)


def install_session_logging(
    session: Any,
    *,
    call_metrics: CallMetricsRecorder | None = None,
) -> None:
    """Attach realtime call diagnostics to a LiveKit agent session."""

    @session.on("user_input_transcribed")
    def _on_user_input_transcribed(event: Any) -> None:
        transcript = _clean_log_text(getattr(event, "transcript", ""))
        if not transcript:
            return

        if getattr(event, "is_final", False):
            logger.info(
                "voice_session.stt_final transcript=%r speaker_id=%s language=%s",
                transcript,
                getattr(event, "speaker_id", None),
                getattr(event, "language", None),
            )
        else:
            logger.debug("voice_session.stt_partial transcript=%r", transcript)

    @session.on("conversation_item_added")
    def _on_conversation_item_added(event: Any) -> None:
        item = getattr(event, "item", None)
        if getattr(item, "type", None) != "message":
            return

        role = getattr(item, "role", "unknown")
        text = _message_text(item)
        metrics = _latency_metrics(getattr(item, "metrics", {}))
        if role == "user":
            if call_metrics is not None:
                call_metrics.record_user_message(getattr(item, "metrics", {}))
            logger.info(
                "voice_session.user_turn_committed text=%r metrics=%s",
                text,
                metrics,
            )
        elif role == "assistant":
            if call_metrics is not None:
                call_metrics.record_assistant_message(
                    getattr(item, "metrics", {}),
                    interrupted=bool(getattr(item, "interrupted", False)),
                )
            logger.info(
                "voice_session.assistant_response_committed text=%r interrupted=%s metrics=%s",
                text,
                getattr(item, "interrupted", False),
                metrics,
            )
        else:
            logger.debug("voice_session.message_committed role=%s text=%r", role, text)

    @session.on("speech_created")
    def _on_speech_created(event: Any) -> None:
        logger.info(
            "voice_session.speech_created source=%s user_initiated=%s",
            getattr(event, "source", None),
            getattr(event, "user_initiated", None),
        )

    @session.on("agent_state_changed")
    def _on_agent_state_changed(event: Any) -> None:
        if call_metrics is not None:
            call_metrics.record_agent_state(getattr(event, "new_state", None))
        logger.info(
            "voice_session.agent_state_changed old_state=%s new_state=%s",
            getattr(event, "old_state", None),
            getattr(event, "new_state", None),
        )

    @session.on("agent_false_interruption")
    def _on_agent_false_interruption(event: Any) -> None:
        if call_metrics is not None:
            call_metrics.record_false_interruption()
        logger.info(
            "voice_session.false_interruption resumed=%s",
            getattr(event, "resumed", None),
        )

    @session.on("function_tools_executed")
    def _on_function_tools_executed(event: Any) -> None:
        tool_summaries = []
        for function_call, function_output in event.zipped():
            tool_summaries.append(
                {
                    "name": getattr(function_call, "name", None),
                    "call_id": getattr(function_call, "call_id", None),
                    "output": _tool_output_summary(function_output),
                }
            )
        logger.info("voice_session.function_tools_executed tools=%s", tool_summaries)

    @session.on("metrics_collected")
    def _on_metrics_collected(event: Any) -> None:
        metrics = getattr(event, "metrics", None)
        if call_metrics is not None and getattr(metrics, "type", None) in {
            "llm_metrics",
            "realtime_model_metrics",
        }:
            call_metrics.record_llm_request(metrics)

    @session.on("error")
    def _on_error(event: Any) -> None:
        if call_metrics is not None:
            call_metrics.record_error()
        logger.error(
            "voice_session.error source=%r error=%r",
            getattr(event, "source", None),
            getattr(event, "error", None),
        )

    @session.on("close")
    def _on_close(event: Any) -> None:
        if call_metrics is not None:
            call_metrics.close(
                reason=getattr(event, "reason", None),
                has_error=getattr(event, "error", None) is not None,
            )
        logger.info(
            "voice_session.closed reason=%s error=%r",
            getattr(event, "reason", None),
            getattr(event, "error", None),
        )


def _message_text(message: Any) -> str:
    text_content = getattr(message, "text_content", None)
    if text_content:
        return _clean_log_text(text_content)

    content = getattr(message, "content", [])
    text_parts = [part for part in content if isinstance(part, str)]
    return _clean_log_text(" ".join(text_parts))


def _clean_log_text(value: str, *, max_length: int = 500) -> str:
    text = " ".join(value.split())
    if len(text) <= max_length:
        return text
    return text[: max_length - 3] + "..."


def _latency_metrics(metrics: Any) -> dict[str, Any]:
    if not isinstance(metrics, dict):
        return {}
    keys = [
        "transcription_delay",
        "end_of_turn_delay",
        "llm_node_ttft",
        "tts_node_ttfb",
        "playback_latency",
        "e2e_latency",
    ]
    return {
        key: round(value, 3) for key in keys if isinstance((value := metrics.get(key)), int | float)
    }


def _tool_output_summary(function_output: Any) -> dict[str, Any] | None:
    if function_output is None:
        return None

    summary: dict[str, Any] = {
        "is_error": getattr(function_output, "is_error", None),
    }
    output = getattr(function_output, "output", "")
    try:
        parsed = json.loads(output)
    except (TypeError, json.JSONDecodeError):
        summary["text"] = _clean_log_text(str(output), max_length=200)
        return summary

    if isinstance(parsed, dict):
        for key in ("status", "reasons", "ambiguous"):
            if key in parsed:
                summary[key] = parsed[key]
        return summary

    summary["text"] = _clean_log_text(str(parsed), max_length=200)
    return summary


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
