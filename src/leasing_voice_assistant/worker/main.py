"""LiveKit worker entrypoint for inbound SIP calls."""

from __future__ import annotations

import time
import uuid
from importlib import import_module
from typing import Any

from leasing_voice_assistant.core.config import get_settings
from leasing_voice_assistant.db.seed import seed_database
from leasing_voice_assistant.db.session import (
    create_session_factory,
    create_sqlite_engine,
    initialize_database,
    session_scope,
)
from leasing_voice_assistant.worker.call_context import build_call_context
from leasing_voice_assistant.worker.configuration import (
    build_provider_factory,
    create_worker_options,
)
from leasing_voice_assistant.worker.metrics import CallMetricsRecorder, JsonlMetricsWriter
from leasing_voice_assistant.worker.session import maybe_await, start_agent_session


async def job_entrypoint(ctx: Any) -> None:
    """Start one call-scoped LiveKit agent session."""
    settings = get_settings()
    provider_clients = build_provider_factory(settings).build_clients()
    engine = create_sqlite_engine(settings.database_url)
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    with session_scope(session_factory) as db_session:
        seed_database(db_session)

    await maybe_await(ctx.connect())
    connected_at = time.monotonic()
    wait_for_participant = getattr(ctx, "wait_for_participant", None)
    participant = (
        await maybe_await(wait_for_participant()) if callable(wait_for_participant) else None
    )
    context = build_call_context(
        room=getattr(ctx, "room", None),
        participant=participant,
    )
    call_metrics = CallMetricsRecorder(
        call_id=context.call_sid or f"call-{uuid.uuid4()}",
        writer=JsonlMetricsWriter(settings.voice_metrics_path),
        connected_at=connected_at,
    )

    with session_scope(session_factory) as db_session:
        await start_agent_session(
            ctx=ctx,
            provider_clients=provider_clients,
            state=context.to_call_state(),
            db_session=db_session,
            settings=settings,
            call_metrics=call_metrics,
        )


def main() -> None:
    """Console-script entrypoint for the LiveKit worker."""
    settings = get_settings()
    options = create_worker_options(settings, entrypoint_fnc=job_entrypoint)
    agents = import_module("livekit.agents")
    agents.cli.run_app(options)
