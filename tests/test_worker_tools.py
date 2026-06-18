import asyncio
import inspect

from sqlalchemy import select

from leasing_voice_assistant.db.models import Prospect
from leasing_voice_assistant.db.seed import seed_database
from leasing_voice_assistant.db.session import (
    create_session_factory,
    create_sqlite_engine,
    initialize_database,
)
from leasing_voice_assistant.worker.call_context import build_call_context
from leasing_voice_assistant.worker.tools import build_worker_tools


def test_worker_tools_preserve_missing_phone_capture_rejection() -> None:
    engine = create_sqlite_engine("sqlite:///:memory:")
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        seed_database(session)
        session.commit()

        state = build_call_context().to_call_state()
        tools = build_worker_tools(session, state)
        tools.search_properties("Aurora Heights")

        result = tools.capture_prospect_interest(
            caller_name="Sam Rivera",
            confirmed_interest=True,
        )

        assert result["status"] == "rejected"
        assert "missing_phone" in result["reasons"]
        assert session.scalars(select(Prospect)).all() == []


def test_livekit_tools_are_awaitable_and_preserve_signature() -> None:
    engine = create_sqlite_engine("sqlite:///:memory:")
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        seed_database(session)
        session.commit()

        state = build_call_context().to_call_state()
        tools = build_worker_tools(session, state)
        livekit_tools = tools.as_livekit_tools()
        search_properties = livekit_tools[0]

        assert inspect.signature(search_properties).parameters.keys() == {"query", "limit"}

        result = asyncio.run(search_properties(query="Aurora Heights"))

        assert result["status"] == "matched"
