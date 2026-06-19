import asyncio

import pytest
from livekit.agents import ChatContext, ChatMessage, StopResponse

from leasing_voice_assistant.agent.grounding import GroundedTurnContextBuilder
from leasing_voice_assistant.agent.state import CallState
from leasing_voice_assistant.db.seed import seed_database
from leasing_voice_assistant.db.session import (
    create_session_factory,
    create_sqlite_engine,
    initialize_database,
)
from leasing_voice_assistant.worker.agent import GroundingCoordinator, LeasingVoiceAgent


def _agent_and_session():
    engine = create_sqlite_engine("sqlite:///:memory:")
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    session = session_factory()
    seed_database(session)
    session.commit()
    state = CallState()
    coordinator = GroundingCoordinator()
    agent = LeasingVoiceAgent(
        instructions="test",
        tools=[],
        builder=GroundedTurnContextBuilder(session),
        state=state,
        coordinator=coordinator,
    )
    return agent, state, coordinator, session


def test_agent_injects_developer_grounding_and_applies_transition_once() -> None:
    agent, state, _coordinator, session = _agent_and_session()
    try:
        context = ChatContext()
        message = ChatMessage(role="user", content=["Tell me about Aurora Heights"], id="turn-1")

        asyncio.run(agent.on_user_turn_completed(context, message))
        asyncio.run(agent.on_user_turn_completed(context, message))

        assert len(context.items) == 2
        assert "GROUNDING_DATA_JSON" in context.items[0].text_content
        assert state.current_target is not None
        assert state.current_target.label == "Aurora Heights"
    finally:
        session.close()


def test_agent_discards_stale_grounding_without_state_or_context() -> None:
    agent, state, coordinator, session = _agent_and_session()
    original = agent._builder._checkpoint

    async def cancel_during_checkpoint(is_cancelled, deadline):
        coordinator.epoch += 1
        await original(is_cancelled, deadline)

    agent._builder._checkpoint = cancel_during_checkpoint
    context = ChatContext()
    message = ChatMessage(role="user", content=["Aurora Heights"], id="turn-2")
    try:
        with pytest.raises(StopResponse):
            asyncio.run(agent.on_user_turn_completed(context, message))
        assert state.current_target is None
        assert context.items == []
    finally:
        session.close()


def test_false_vad_activity_does_not_advance_epoch() -> None:
    async def scenario() -> int:
        coordinator = GroundingCoordinator(interruption_duration_seconds=10)
        coordinator._begin_activity()
        coordinator._end_activity()
        return coordinator.epoch

    assert asyncio.run(scenario()) == 0
