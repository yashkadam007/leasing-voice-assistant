"""Call-scoped contextual acknowledgment coordination."""

from __future__ import annotations

import asyncio
import contextlib
import time
from collections.abc import AsyncIterable, AsyncIterator, Callable
from dataclasses import dataclass
from typing import Any, Literal

from leasing_voice_assistant.agent.grounding import GroundingOutcome
from leasing_voice_assistant.worker.metrics import CallMetricsRecorder

AcknowledgmentClass = Literal["capture", "comparison", "policy", "property_search"]


@dataclass(frozen=True)
class AcknowledgmentPhrase:
    phrase_id: str
    text: str


PHRASE_CATALOG: dict[AcknowledgmentClass, tuple[AcknowledgmentPhrase, ...]] = {
    "capture": (
        AcknowledgmentPhrase("capture-1", "One moment while I note that."),
        AcknowledgmentPhrase("capture-2", "Let me note that for you."),
        AcknowledgmentPhrase("capture-3", "I'll take a moment to record that."),
    ),
    "comparison": (
        AcknowledgmentPhrase("comparison-1", "Let me compare those details."),
        AcknowledgmentPhrase("comparison-2", "I'll check those options side by side."),
        AcknowledgmentPhrase("comparison-3", "Let me review those details together."),
    ),
    "policy": (
        AcknowledgmentPhrase("policy-1", "Let me check that property information."),
        AcknowledgmentPhrase("policy-2", "I'll review that property policy."),
        AcknowledgmentPhrase("policy-3", "Let me look into those property details."),
    ),
    "property_search": (
        AcknowledgmentPhrase("property-search-1", "Let me check the available options."),
        AcknowledgmentPhrase("property-search-2", "I'll look through the available units."),
        AcknowledgmentPhrase("property-search-3", "Let me review the matching options."),
    ),
}


def classify_grounding(
    outcome: GroundingOutcome, *, capture_intent: bool = False
) -> AcknowledgmentClass | None:
    """Select the highest-precedence eligible read class."""
    if capture_intent:
        return "capture"
    payload = outcome.payload
    statuses = set(payload.get("statuses", ()))
    if statuses != {"matched"}:
        return None
    query = payload.get("query")
    if not isinstance(query, dict):
        return None
    if query.get("comparison_requested") or query.get("compound_question"):
        return "comparison"
    if query.get("policy_topics"):
        return "policy"
    if (
        any(query.get(key) for key in ("property_terms", "location_terms", "unit_numbers"))
        or query.get("bedroom_count") is not None
        or query.get("minimum_rent_cents") is not None
        or query.get("maximum_rent_cents") is not None
        or query.get("availability_requested") is True
    ):
        return "property_search"
    return None


@dataclass
class _Turn:
    epoch: int
    committed_at: float
    acknowledgment_class: AcknowledgmentClass | None = None
    eligible: bool = False
    scheduled: bool = False
    started: bool = False
    invalidated: bool = False
    outcome_recorded: bool = False
    phrase: AcknowledgmentPhrase | None = None


class AcknowledgmentCoordinator:
    """Race a delayed curated acknowledgment against substantive first audio."""

    def __init__(
        self,
        *,
        synthesize: Callable[[str], AsyncIterable[Any]],
        metrics: CallMetricsRecorder | None = None,
        delay_seconds: float = 0.75,
        call_limit: int = 2,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._synthesize = synthesize
        self._metrics = metrics
        self._delay_seconds = delay_seconds
        self._call_limit = call_limit
        self._clock = clock
        self._epoch = 0
        self._current: _Turn | None = None
        self._used_count = 0
        self._last_used_epoch: int | None = None
        self._phrase_history: dict[AcknowledgmentClass, list[str]] = {
            key: [] for key in PHRASE_CATALOG
        }
        self._caller_speaking = False
        self._assistant_speaking = False

    def bind(self, session: Any) -> None:
        """Track public LiveKit speaking lifecycle for start-time suppression."""

        @session.on("user_state_changed")
        def _on_user_state_changed(event: Any) -> None:
            self._caller_speaking = str(getattr(event, "new_state", "")) == "speaking"

        @session.on("agent_state_changed")
        def _on_agent_state_changed(event: Any) -> None:
            self._assistant_speaking = str(getattr(event, "new_state", "")) == "speaking"

    def begin_turn(self) -> int:
        """Start timing a newly committed caller turn."""
        if self._current is not None and not self._current.outcome_recorded:
            self._finish(self._current, "cancelled")
        self._epoch += 1
        self._current = _Turn(epoch=self._epoch, committed_at=self._clock())
        return self._epoch

    def set_grounding(self, epoch: int, outcome: GroundingOutcome) -> None:
        turn = self._turn(epoch)
        if turn is None:
            return
        selected = classify_grounding(outcome)
        turn.acknowledgment_class = selected
        turn.eligible = selected is not None
        self._record_eligibility(turn)

    def set_capture_intent(self) -> None:
        """Apply highest-precedence capture intent when the guarded tool is selected."""
        turn = self._current
        if turn is None or turn.invalidated or turn.started:
            return
        turn.acknowledgment_class = "capture"
        turn.eligible = True
        self._record_eligibility(turn)

    def invalidate_current(self) -> None:
        """Invalidate stale speech after confirmed caller activity."""
        turn = self._current
        if turn is None or turn.invalidated:
            return
        turn.invalidated = True
        if turn.started:
            self._finish(turn, "interrupted")
        elif turn.scheduled:
            self._finish(turn, "cancelled")

    async def wrap_substantive(
        self, substantive: AsyncIterable[Any], *, epoch: int | None = None
    ) -> AsyncIterator[Any]:
        """Yield one non-overlapping audio stream with an optional delayed prefix."""
        turn = self._turn(epoch or self._epoch)
        substantive_iterator = substantive.__aiter__()
        first_substantive = asyncio.create_task(
            _first_frame_with_time(substantive_iterator, self._clock)
        )
        if turn is None or not self._can_schedule(turn):
            first, _ready_at = await first_substantive
            if first is not None:
                yield first
            async for frame in substantive_iterator:
                yield frame
            return

        turn.scheduled = True
        phrase = self._select_phrase(turn.acknowledgment_class)
        turn.phrase = phrase
        self._record(turn, acknowledgment_scheduled=True, acknowledgment_phrase_id=phrase.phrase_id)
        acknowledgment = asyncio.create_task(self._first_acknowledgment_frame(turn, phrase))
        try:
            done, _ = await asyncio.wait(
                {first_substantive, acknowledgment}, return_when=asyncio.FIRST_COMPLETED
            )
            if first_substantive in done:
                first, ready_at = first_substantive.result()
                await self._cancel(acknowledgment)
                if first is None:
                    # A tool-only LLM phase has no substantive audio. Preserve the
                    # turn so guarded capture can select the post-tool acknowledgment.
                    turn.scheduled = False
                    turn.phrase = None
                    return
                self._record_substantive_ready(turn, ready_at)
                self._finish(turn, "cancelled")
                self._record_substantive_start(turn)
                yield first
                async for frame in substantive_iterator:
                    yield frame
                return

            first_ack, ack_iterator = acknowledgment.result()
            if (
                first_ack is None
                or turn.invalidated
                or self._caller_speaking
                or self._assistant_speaking
            ):
                self._finish(turn, "suppressed")
                first, ready_at = await first_substantive
                self._record_substantive_ready(turn, ready_at)
                if first is not None:
                    self._record_substantive_start(turn)
                    yield first
                async for frame in substantive_iterator:
                    yield frame
                return

            self._mark_started(turn)
            acknowledgment_duration = _frame_duration_ms(first_ack)
            yield first_ack
            async for frame in ack_iterator:
                acknowledgment_duration += _frame_duration_ms(frame)
                yield frame
            ack_ended_at = self._clock()
            self._record(turn, acknowledgment_duration_ms=round(acknowledgment_duration))

            first, ready_at = await first_substantive
            self._record_substantive_ready(turn, ready_at)
            if first is not None:
                self._record_substantive_start(turn, acknowledgment_ended_at=ack_ended_at)
                yield first
            async for frame in substantive_iterator:
                yield frame
            self._finish(turn, "interrupted" if turn.invalidated else "completed")
        except asyncio.CancelledError:
            await self._cancel(acknowledgment)
            self._finish(turn, "interrupted" if turn.started else "cancelled")
            raise
        except Exception:
            await self._cancel(acknowledgment)
            self._finish(turn, "error")
            if first_substantive.done() and first_substantive.exception() is not None:
                raise first_substantive.exception() from None
            if not first_substantive.done():
                first, _ready_at = await first_substantive
                if first is not None:
                    yield first
            async for frame in substantive_iterator:
                yield frame

    async def _first_acknowledgment_frame(
        self, turn: _Turn, phrase: AcknowledgmentPhrase
    ) -> tuple[Any | None, AsyncIterator[Any]]:
        remaining = turn.committed_at + self._delay_seconds - self._clock()
        if remaining > 0:
            await asyncio.sleep(remaining)
        if turn.invalidated or self._caller_speaking or self._assistant_speaking:
            return None, _empty_audio()
        iterator = self._synthesize(phrase.text).__aiter__()
        return await anext(iterator, None), iterator

    def _can_schedule(self, turn: _Turn) -> bool:
        if turn.outcome_recorded or turn.scheduled:
            return False
        if turn.invalidated:
            self._finish(turn, "cancelled")
            return False
        if not turn.eligible or turn.acknowledgment_class is None:
            return False
        if self._used_count >= self._call_limit:
            self._finish(turn, "suppressed")
            return False
        if self._last_used_epoch == turn.epoch - 1:
            self._finish(turn, "suppressed")
            return False
        return True

    def _select_phrase(self, selected: AcknowledgmentClass | None) -> AcknowledgmentPhrase:
        assert selected is not None
        catalog = PHRASE_CATALOG[selected]
        used = self._phrase_history[selected]
        return next((phrase for phrase in catalog if phrase.phrase_id not in used), catalog[0])

    def _mark_started(self, turn: _Turn) -> None:
        turn.started = True
        self._used_count += 1
        self._last_used_epoch = turn.epoch
        assert turn.acknowledgment_class is not None and turn.phrase is not None
        self._phrase_history[turn.acknowledgment_class].append(turn.phrase.phrase_id)
        self._record(
            turn,
            acknowledgment_started=True,
            acknowledgment_start_ms=round((self._clock() - turn.committed_at) * 1000),
            perceived_response_ms=round((self._clock() - turn.committed_at) * 1000),
        )

    def _record_substantive_ready(self, turn: _Turn, ready_at: float) -> None:
        self._record(
            turn,
            substantive_audio_ready_ms=round((ready_at - turn.committed_at) * 1000),
        )

    def _record_substantive_start(
        self, turn: _Turn, *, acknowledgment_ended_at: float | None = None
    ) -> None:
        elapsed = round((self._clock() - turn.committed_at) * 1000)
        values: dict[str, Any] = {"substantive_audio_start_ms": elapsed}
        if not turn.started:
            values["perceived_response_ms"] = elapsed
        if acknowledgment_ended_at is not None:
            values["acknowledgment_to_substantive_gap_ms"] = round(
                (self._clock() - acknowledgment_ended_at) * 1000
            )
        self._record(turn, **values)

    def _record_eligibility(self, turn: _Turn) -> None:
        self._record(
            turn,
            acknowledgment_eligible=turn.eligible,
            acknowledgment_class=turn.acknowledgment_class,
        )

    def _finish(self, turn: _Turn, outcome: str) -> None:
        if turn.outcome_recorded:
            return
        turn.outcome_recorded = True
        self._record(turn, acknowledgment_outcome=outcome)

    def _record(self, turn: _Turn, **values: Any) -> None:
        if self._metrics is not None:
            self._metrics.record_acknowledgment(turn.epoch, **values)

    def _turn(self, epoch: int) -> _Turn | None:
        turn = self._current
        return turn if turn is not None and turn.epoch == epoch else None

    @staticmethod
    async def _cancel(task: asyncio.Task[Any]) -> None:
        if task.done():
            with contextlib.suppress(asyncio.CancelledError, Exception):
                task.result()
            return
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await task


async def _empty_audio() -> AsyncIterator[Any]:
    if False:
        yield None


async def _first_frame_with_time(
    iterator: AsyncIterator[Any], clock: Callable[[], float]
) -> tuple[Any | None, float]:
    frame = await anext(iterator, None)
    return frame, clock()


def _frame_duration_ms(frame: Any) -> float:
    duration = getattr(frame, "duration", 0.0)
    return float(duration) * 1000 if isinstance(duration, int | float) else 0.0


def deepgram_synthesizer(tts: Any) -> Callable[[str], AsyncIterable[Any]]:
    """Adapt the provider's public one-shot synthesis stream to audio frames."""

    async def synthesize(text: str) -> AsyncIterator[Any]:
        async with tts.synthesize(text) as stream:
            async for event in stream:
                yield event.frame

    return synthesize
