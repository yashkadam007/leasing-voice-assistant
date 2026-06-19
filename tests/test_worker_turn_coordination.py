import asyncio
from types import SimpleNamespace

from leasing_voice_assistant.worker.turn_coordination import GroundingCoordinator


class _FakeSession:
    def __init__(self) -> None:
        self.handlers = {}

    def on(self, event_name):
        def register(handler):
            self.handlers[event_name] = handler
            return handler

        return register

    def emit(self, event_name, **values) -> None:
        self.handlers[event_name](SimpleNamespace(**values))


def test_transcribed_caller_activity_invalidates_current_token() -> None:
    async def scenario() -> tuple[int, bool, int]:
        session = _FakeSession()
        coordinator = GroundingCoordinator(interruption_duration_seconds=10)
        invalidations = 0

        def record_invalidation() -> None:
            nonlocal invalidations
            invalidations += 1

        coordinator.add_invalidation_callback(record_invalidation)
        coordinator.bind(session)
        _epoch, is_cancelled = coordinator.token()
        session.emit("user_state_changed", new_state="speaking")
        session.emit("user_input_transcribed", transcript="hello")
        return coordinator.epoch, is_cancelled(), invalidations

    assert asyncio.run(scenario()) == (1, True, 1)


def test_false_vad_activity_does_not_advance_epoch() -> None:
    async def scenario() -> int:
        session = _FakeSession()
        coordinator = GroundingCoordinator(interruption_duration_seconds=10)
        coordinator.bind(session)
        session.emit("user_state_changed", new_state="speaking")
        session.emit("user_state_changed", new_state="listening")
        return coordinator.epoch

    assert asyncio.run(scenario()) == 0
