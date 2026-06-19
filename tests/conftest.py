from collections.abc import Callable, Iterator
from types import SimpleNamespace

import pytest
from sqlalchemy.orm import Session

from leasing_voice_assistant.agent.state import CallState
from leasing_voice_assistant.db.seed import seed_database
from leasing_voice_assistant.db.session import (
    create_session_factory,
    create_sqlite_engine,
    initialize_database,
)


class FakeSession:
    """Minimal public event-registration surface used by worker tests."""

    def __init__(self) -> None:
        self.handlers: dict[str, Callable[[object], None]] = {}

    def on(self, event_name: str) -> Callable[[Callable[[object], None]], Callable[[object], None]]:
        def register(handler: Callable[[object], None]) -> Callable[[object], None]:
            self.handlers[event_name] = handler
            return handler

        return register

    def emit(self, event_name: str, **values: object) -> None:
        self.handlers[event_name](SimpleNamespace(**values))


@pytest.fixture()
def seeded_db_session() -> Iterator[Session]:
    """Provide a transaction-ready in-memory database with canonical seed data."""
    engine = create_sqlite_engine("sqlite:///:memory:")
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        seed_database(session)
        session.commit()
        yield session
    engine.dispose()


@pytest.fixture()
def call_state() -> CallState:
    return CallState()


@pytest.fixture()
def fake_session() -> FakeSession:
    return FakeSession()
