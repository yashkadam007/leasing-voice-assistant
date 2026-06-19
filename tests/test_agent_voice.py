import asyncio

import pytest
from livekit.agents import ChatContext, ChatMessage, StopResponse

from leasing_voice_assistant.agent.grounding import GroundedTurnContextBuilder
from leasing_voice_assistant.agent.state import CallState
from leasing_voice_assistant.agent.voice import LeasingVoiceAgent
from leasing_voice_assistant.db.seed import seed_database
from leasing_voice_assistant.db.session import (
    create_session_factory,
    create_sqlite_engine,
    initialize_database,
)


class _CancellationSource:
    def __init__(self, *, cancel_after_checks: int | None = None) -> None:
        self._cancel_after_checks = cancel_after_checks

    def token(self):
        checks = 0

        def is_cancelled() -> bool:
            nonlocal checks
            checks += 1
            return self._cancel_after_checks is not None and checks > self._cancel_after_checks

        return 0, is_cancelled


def _agent_and_session(*, coordinator=None):
    engine = create_sqlite_engine("sqlite:///:memory:")
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    session = session_factory()
    seed_database(session)
    session.commit()
    state = CallState()
    coordinator = coordinator or _CancellationSource()
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
    agent, state, _coordinator, session = _agent_and_session(
        coordinator=_CancellationSource(cancel_after_checks=1)
    )
    context = ChatContext()
    message = ChatMessage(role="user", content=["Aurora Heights"], id="turn-2")
    try:
        with pytest.raises(StopResponse):
            asyncio.run(agent.on_user_turn_completed(context, message))
        assert state.current_target is None
        assert context.items == []
    finally:
        session.close()
