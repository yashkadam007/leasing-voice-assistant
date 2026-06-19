import asyncio

from conftest import FakeSession
from leasing_voice_assistant.worker.turn_coordination import GroundingCoordinator


def test_transcribed_caller_activity_invalidates_current_token(fake_session: FakeSession) -> None:
    async def scenario() -> tuple[bool, int]:
        coordinator = GroundingCoordinator(interruption_duration_seconds=10)
        invalidations = 0

        def record_invalidation() -> None:
            nonlocal invalidations
            invalidations += 1

        coordinator.add_invalidation_callback(record_invalidation)
        coordinator.bind(fake_session)
        _epoch, is_cancelled = coordinator.token()
        fake_session.emit("user_state_changed", new_state="speaking")
        fake_session.emit("user_input_transcribed", transcript="hello")
        return is_cancelled(), invalidations

    assert asyncio.run(scenario()) == (True, 1)


def test_false_vad_activity_does_not_invalidate_token(fake_session: FakeSession) -> None:
    async def scenario() -> bool:
        coordinator = GroundingCoordinator(interruption_duration_seconds=10)
        coordinator.bind(fake_session)
        _epoch, is_cancelled = coordinator.token()
        fake_session.emit("user_state_changed", new_state="speaking")
        fake_session.emit("user_state_changed", new_state="listening")
        return is_cancelled()

    assert asyncio.run(scenario()) is False
