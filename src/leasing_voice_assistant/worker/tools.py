"""LiveKit tool adapters for leasing agent domain tools."""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from functools import wraps
from importlib import import_module
from typing import Any

from sqlalchemy.orm import Session

from leasing_voice_assistant.agent import CallState, LeasingAgentTools


class LiveKitToolAdapter:
    """Adapt call-scoped leasing tools for LiveKit tool registration."""

    def __init__(
        self,
        session: Session,
        state: CallState,
        *,
        record_tool: Callable[..., None] | None = None,
        on_tool_started: Callable[[str], None] | None = None,
    ) -> None:
        self._session = session
        self._domain_tools = LeasingAgentTools(session, state)
        self._record_tool = record_tool
        self._on_tool_started = on_tool_started

    def search_properties(self, query: str, limit: int = 5) -> dict:
        """Search property and unit records from caller wording."""
        return self._domain_tools.search_properties(query, limit=limit)

    def get_unit_details(self, unit_number: str) -> dict:
        """Return authoritative facts for a caller-facing unit number."""
        return self._domain_tools.get_unit_details(unit_number)

    def search_knowledge_base(
        self,
        query: str,
        limit: int = 3,
        property_identifier: str | None = None,
    ) -> dict:
        """Return source-backed policy or FAQ snippets from the local knowledge base."""
        return self._domain_tools.search_knowledge_base(
            query,
            limit=limit,
            property_identifier=property_identifier,
        )

    def capture_prospect_interest(
        self,
        caller_name: str | None = None,
        caller_email: str | None = None,
        confirmed_interest: bool = False,
        notes: str | None = None,
    ) -> dict:
        """Create or update a prospect interest only after the safety gate passes."""
        try:
            result = self._domain_tools.capture_prospect_interest(
                caller_name=caller_name,
                caller_email=caller_email,
                confirmed_interest=confirmed_interest,
                notes=notes,
            )
            # The worker owns the call-scoped transaction boundary for capture writes.
            if result["status"] == "captured":
                self._session.commit()
            return result
        except Exception:
            self._session.rollback()
            raise

    def _legacy_callables(self) -> list[Callable[..., dict]]:
        return [
            self.search_properties,
            self.get_unit_details,
            self.search_knowledge_base,
            self.capture_prospect_interest,
        ]

    def legacy_read_and_capture_tools(self) -> list[Callable[..., Awaitable[dict]]]:
        """Expose the legacy model-facing read and capture tool surface."""
        decorator = _livekit_tool_decorator()
        timed_tools = [
            _async_tool(tool, record_tool=self._record_tool) for tool in self._legacy_callables()
        ]
        if decorator is None:
            return timed_tools
        return [decorator(tool) for tool in timed_tools]

    def capture_tool(self) -> Callable[..., Awaitable[dict]]:
        """Expose only the guarded write tool for hybrid grounding mode."""
        tool = _async_tool(
            self.capture_prospect_interest,
            record_tool=self._record_tool,
            on_tool_started=self._on_tool_started,
        )
        decorator = _livekit_tool_decorator()
        return decorator(tool) if decorator is not None else tool


def _livekit_tool_decorator() -> Callable[[Callable[..., dict]], Callable[..., dict]] | None:
    try:
        agents = import_module("livekit.agents")
    except ImportError:
        return None

    decorator = getattr(agents, "function_tool", None)
    if callable(decorator):
        return decorator

    llm = getattr(agents, "llm", None)
    decorator = getattr(llm, "function_tool", None)
    if callable(decorator):
        return decorator

    return None


def _async_tool(
    tool: Callable[..., dict],
    *,
    record_tool: Callable[..., None] | None = None,
    on_tool_started: Callable[[str], None] | None = None,
) -> Callable[..., Awaitable[dict]]:
    """Adapt sync domain tools for LiveKit SDKs that await function tools."""

    @wraps(tool)
    async def wrapper(*args: Any, **kwargs: Any) -> dict:
        if on_tool_started is not None:
            on_tool_started(tool.__name__)
        started_at = time.monotonic()
        is_error = False
        try:
            return tool(*args, **kwargs)
        except Exception:
            is_error = True
            raise
        finally:
            if record_tool is not None:
                record_tool(
                    tool.__name__,
                    (time.monotonic() - started_at) * 1000,
                    is_error=is_error,
                )

    return wrapper


def build_livekit_tool_adapter(
    session: Session,
    state: CallState,
    *,
    record_tool: Callable[..., None] | None = None,
    on_tool_started: Callable[[str], None] | None = None,
) -> LiveKitToolAdapter:
    """Build the call-scoped LiveKit tool adapter."""
    return LiveKitToolAdapter(
        session,
        state,
        record_tool=record_tool,
        on_tool_started=on_tool_started,
    )
