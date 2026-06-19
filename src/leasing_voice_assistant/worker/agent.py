"""Call-scoped LiveKit agent for pre-LLM grounding."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable
from typing import Any

from livekit.agents import Agent, StopResponse

from leasing_voice_assistant.agent.grounding import (
    CallStateSnapshot,
    GroundedTurnContextBuilder,
    GroundingCancelled,
    GroundingOutcome,
)
from leasing_voice_assistant.agent.state import CallState
from leasing_voice_assistant.worker.acknowledgments import AcknowledgmentCoordinator
from leasing_voice_assistant.worker.metrics import CallMetricsRecorder

logger = logging.getLogger(__name__)


class GroundingCoordinator:
    """Track caller activity and invalidate stale grounding operations."""

    def __init__(self, *, interruption_duration_seconds: float = 0.5) -> None:
        self.epoch = 0
        self._caller_speaking = False
        self._activity_confirmed = False
        self._timer: asyncio.TimerHandle | None = None
        self._interruption_duration_seconds = interruption_duration_seconds
        self._invalidation_callbacks: list[Callable[[], None]] = []

    def bind(self, session: Any) -> None:
        """Observe only the events needed for cooperative cancellation."""

        @session.on("user_state_changed")
        def _on_user_state_changed(event: Any) -> None:
            if str(getattr(event, "new_state", "")) == "speaking":
                self._begin_activity()
            else:
                self._end_activity()

        @session.on("user_input_transcribed")
        def _on_user_input_transcribed(event: Any) -> None:
            if str(getattr(event, "transcript", "")).strip():
                self.confirm_activity()

    def token(self) -> tuple[int, Any]:
        epoch = self.epoch
        return epoch, lambda: self.epoch != epoch

    def confirm_activity(self) -> None:
        """Advance once when VAD activity has transcript evidence."""
        if self._caller_speaking and not self._activity_confirmed:
            self._activity_confirmed = True
            self.epoch += 1
            for callback in self._invalidation_callbacks:
                callback()

    def add_invalidation_callback(self, callback: Any) -> None:
        """Run a callback when confirmed caller activity advances the epoch."""
        self._invalidation_callbacks.append(callback)

    def _begin_activity(self) -> None:
        self._caller_speaking = True
        self._activity_confirmed = False
        if self._timer is not None:
            self._timer.cancel()
        loop = asyncio.get_running_loop()
        self._timer = loop.call_later(
            self._interruption_duration_seconds,
            self.confirm_activity,
        )

    def _end_activity(self) -> None:
        self._caller_speaking = False
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None


class LeasingVoiceAgent(Agent):
    """Inject bounded authoritative grounding before each LLM generation."""

    def __init__(
        self,
        *,
        instructions: str,
        tools: list[Any],
        builder: GroundedTurnContextBuilder,
        state: CallState,
        coordinator: GroundingCoordinator,
        metrics: CallMetricsRecorder | None = None,
        acknowledgments: AcknowledgmentCoordinator | None = None,
    ) -> None:
        super().__init__(instructions=instructions, tools=tools)
        self._builder = builder
        self._state = state
        self._coordinator = coordinator
        self._metrics = metrics
        self._acknowledgments = acknowledgments
        self._cache: dict[str, GroundingOutcome] = {}
        self._applied_transitions: set[str] = set()

    async def on_user_turn_completed(self, turn_ctx: Any, new_message: Any) -> None:
        message_id = str(getattr(new_message, "id", "") or id(new_message))
        cached = self._cache.get(message_id)
        if cached is not None:
            self._inject(turn_ctx, cached)
            return

        ack_epoch = self._acknowledgments.begin_turn() if self._acknowledgments else None

        text = _message_text(new_message)
        _epoch, is_cancelled = self._coordinator.token()
        started = time.monotonic()
        cancelled = False
        try:
            outcome = await self._builder.build(
                text,
                CallStateSnapshot.from_state(self._state),
                is_cancelled=is_cancelled,
            )
            if is_cancelled():
                raise GroundingCancelled
            if outcome.should_apply_transition and message_id not in self._applied_transitions:
                self._state.set_target(outcome.target_transition)
                self._applied_transitions.add(message_id)
            if is_cancelled():
                raise GroundingCancelled
            self._cache[message_id] = outcome
            if self._acknowledgments is not None and ack_epoch is not None:
                self._acknowledgments.set_grounding(ack_epoch, outcome)
            self._inject(turn_ctx, outcome)
        except GroundingCancelled as exc:
            cancelled = True
            raise StopResponse() from exc
        except Exception:
            logger.exception("voice_session.grounding_failed")
            outcome = self._builder.unavailable()
            self._cache[message_id] = outcome
            if self._acknowledgments is not None and ack_epoch is not None:
                self._acknowledgments.set_grounding(ack_epoch, outcome)
            self._inject(turn_ctx, outcome)
        finally:
            if self._metrics is not None:
                duration_ms = (time.monotonic() - started) * 1000
                self._metrics.record_grounding(
                    None if cancelled else outcome,
                    duration_ms=duration_ms,
                    cancelled=cancelled,
                )

    def tts_node(self, text: Any, model_settings: Any) -> Any:
        """Route substantive TTS through the optional acknowledgment race."""
        substantive = super().tts_node(text, model_settings)
        if self._acknowledgments is None:
            return substantive
        return self._acknowledgments.wrap_substantive(substantive)

    @staticmethod
    def _inject(turn_ctx: Any, outcome: GroundingOutcome) -> None:
        turn_ctx.add_message(
            role="developer", content=f"GROUNDING_DATA_JSON\n{outcome.serialized()}"
        )


def _message_text(message: Any) -> str:
    text_content = getattr(message, "text_content", None)
    if isinstance(text_content, str):
        return text_content.strip()
    return " ".join(
        part for part in getattr(message, "content", ()) if isinstance(part, str)
    ).strip()
