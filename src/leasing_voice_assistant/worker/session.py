"""Call-scoped LiveKit agent session composition."""

from __future__ import annotations

from importlib import import_module
from typing import Any

from leasing_voice_assistant.agent.grounding import GroundedTurnContextBuilder
from leasing_voice_assistant.agent.prompts import initial_greeting, initial_instructions
from leasing_voice_assistant.agent.voice import LeasingVoiceAgent
from leasing_voice_assistant.core.config import Settings
from leasing_voice_assistant.worker.acknowledgments import (
    AcknowledgmentCoordinator,
    deepgram_synthesizer,
)
from leasing_voice_assistant.worker.configuration import (
    build_turn_detection_config,
    build_turn_handling_options,
)
from leasing_voice_assistant.worker.metrics import CallMetricsRecorder
from leasing_voice_assistant.worker.session_logging import install_session_logging
from leasing_voice_assistant.worker.tools import build_livekit_tool_adapter
from leasing_voice_assistant.worker.turn_coordination import GroundingCoordinator


async def start_agent_session(
    *,
    ctx: Any,
    provider_clients: Any,
    state: Any,
    db_session: Any,
    settings: Settings,
    call_metrics: CallMetricsRecorder,
) -> None:
    """Construct and run one call-scoped LiveKit agent session."""
    agents = import_module("livekit.agents")
    turn_config = build_turn_detection_config()
    session = agents.AgentSession(
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
        acknowledgments = None
        if settings.acknowledgment_mode == "enabled":
            acknowledgments = AcknowledgmentCoordinator(
                synthesize=deepgram_synthesizer(provider_clients.tts),
                metrics=call_metrics,
                delay_seconds=settings.acknowledgment_delay_ms / 1000,
                call_limit=settings.acknowledgment_call_limit,
            )
            acknowledgments.bind(session)
            coordinator.add_invalidation_callback(acknowledgments.invalidate_current)
        tool_adapter = build_livekit_tool_adapter(
            db_session,
            state,
            record_tool=call_metrics.record_tool,
            on_tool_started=(
                lambda name: (
                    acknowledgments.set_capture_intent()
                    if acknowledgments is not None and name == "capture_prospect_interest"
                    else None
                )
            ),
        )
        agent = LeasingVoiceAgent(
            instructions=initial_instructions(),
            tools=[tool_adapter.capture_tool()],
            builder=GroundedTurnContextBuilder(
                db_session,
                deadline_ms=settings.grounding_deadline_ms,
            ),
            state=state,
            coordinator=coordinator,
            metrics=call_metrics,
            acknowledgments=acknowledgments,
        )
    else:
        tool_adapter = build_livekit_tool_adapter(
            db_session,
            state,
            record_tool=call_metrics.record_tool,
        )
        agent = agents.Agent(
            instructions=initial_instructions(),
            tools=tool_adapter.legacy_read_and_capture_tools(),
        )
    await maybe_await(session.start(room=ctx.room, agent=agent))
    session.say(initial_greeting(), allow_interruptions=True)


async def maybe_await(value: Any) -> Any:
    if hasattr(value, "__await__"):
        return await value
    return value
