"""Leasing voice agent definition with pre-LLM grounding."""

from __future__ import annotations

import logging
import time
from collections.abc import AsyncIterable, Callable
from typing import Any, Protocol

from livekit.agents import Agent, StopResponse

from leasing_voice_assistant.agent.grounding import (
    CallStateSnapshot,
    GroundedTurnContextBuilder,
    GroundingCancelled,
    GroundingOutcome,
)
from leasing_voice_assistant.agent.state import CallState

logger = logging.getLogger(__name__)


class GroundingCancellationSource(Protocol):
    """Provide a cancellation check for one grounding operation."""

    def token(self) -> tuple[int, Callable[[], bool]]: ...


class GroundingMetricsSink(Protocol):
    """Record content-free grounding timing and outcome metadata."""

    def record_grounding(
        self,
        outcome: Any | None,
        *,
        duration_ms: float,
        cancelled: bool = False,
    ) -> None: ...


class AcknowledgmentHook(Protocol):
    """Coordinate optional speech before the substantive response."""

    def begin_turn(self) -> int: ...

    def set_grounding(self, epoch: int, outcome: GroundingOutcome) -> None: ...

    def wrap_substantive(self, substantive: AsyncIterable[Any]) -> AsyncIterable[Any]: ...


class LeasingVoiceAgent(Agent):
    """Inject bounded authoritative grounding before each LLM generation."""

    def __init__(
        self,
        *,
        instructions: str,
        tools: list[Any],
        builder: GroundedTurnContextBuilder,
        state: CallState,
        coordinator: GroundingCancellationSource,
        metrics: GroundingMetricsSink | None = None,
        acknowledgments: AcknowledgmentHook | None = None,
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

        text = message_text(new_message)
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


def message_text(message: Any) -> str:
    """Return normalized text from a LiveKit-style chat message."""
    text_content = getattr(message, "text_content", None)
    if isinstance(text_content, str):
        return text_content.strip()
    return " ".join(
        part for part in getattr(message, "content", ()) if isinstance(part, str)
    ).strip()
