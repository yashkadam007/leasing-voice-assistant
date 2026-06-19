"""LiveKit session coordination for invalidating stale turns."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Protocol


class SessionEventSource(Protocol):
    """Register callbacks for public LiveKit session events."""

    def on(
        self, event_name: str
    ) -> Callable[[Callable[[object], None]], Callable[[object], None]]: ...


class GroundingCoordinator:
    """Track caller activity and invalidate stale grounding operations."""

    def __init__(self, *, interruption_duration_seconds: float = 0.5) -> None:
        self._epoch = 0
        self._caller_speaking = False
        self._activity_confirmed = False
        self._timer: asyncio.TimerHandle | None = None
        self._interruption_duration_seconds = interruption_duration_seconds
        self._invalidation_callbacks: list[Callable[[], None]] = []

    def bind(self, session: SessionEventSource) -> None:
        """Observe only the events needed for cooperative cancellation."""

        @session.on("user_state_changed")
        def _on_user_state_changed(event: object) -> None:
            if str(getattr(event, "new_state", "")) == "speaking":
                self._begin_activity()
            else:
                self._end_activity()

        @session.on("user_input_transcribed")
        def _on_user_input_transcribed(event: object) -> None:
            if str(getattr(event, "transcript", "")).strip():
                self.confirm_activity()

    def token(self) -> tuple[int, Callable[[], bool]]:
        epoch = self._epoch
        return epoch, lambda: self._epoch != epoch

    def confirm_activity(self) -> None:
        """Advance once when VAD activity has transcript evidence."""
        if self._caller_speaking and not self._activity_confirmed:
            self._activity_confirmed = True
            self._epoch += 1
            for callback in self._invalidation_callbacks:
                callback()

    def add_invalidation_callback(self, callback: Callable[[], None]) -> None:
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
