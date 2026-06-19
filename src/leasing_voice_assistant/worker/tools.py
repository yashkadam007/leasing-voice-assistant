"""LiveKit tool adapters for leasing agent domain tools."""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from functools import wraps
from importlib import import_module
from typing import Any

from sqlalchemy.orm import Session

from leasing_voice_assistant.agent import CallState, LeasingAgentTools


class WorkerToolSet:
    """Call-scoped worker tool surface backed by domain leasing tools."""

    def __init__(
        self,
        session: Session,
        state: CallState,
        *,
        record_tool: Callable[..., None] | None = None,
    ) -> None:
        self.session = session
        self.domain_tools = LeasingAgentTools(session, state)
        self.record_tool = record_tool

    def search_properties(self, query: str, limit: int = 5) -> dict:
        """Search property and unit records from caller wording."""
        return self.domain_tools.search_properties(query, limit=limit)

    def get_unit_details(self, unit_number: str) -> dict:
        """Return authoritative facts for a caller-facing unit number."""
        return self.domain_tools.get_unit_details(unit_number)

    def search_knowledge_base(
        self,
        query: str,
        limit: int = 3,
        property_identifier: str | None = None,
    ) -> dict:
        """Return source-backed policy or FAQ snippets from the local knowledge base."""
        return self.domain_tools.search_knowledge_base(
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
            result = self.domain_tools.capture_prospect_interest(
                caller_name=caller_name,
                caller_email=caller_email,
                confirmed_interest=confirmed_interest,
                notes=notes,
            )
            if result["status"] == "captured":
                self.session.commit()
            return result
        except Exception:
            self.session.rollback()
            raise

    def as_callables(self) -> list[Callable[..., dict]]:
        """Return undecorated callables for tests or runtimes without LiveKit installed."""
        return [
            self.search_properties,
            self.get_unit_details,
            self.search_knowledge_base,
            self.capture_prospect_interest,
        ]

    def as_livekit_tools(self) -> list[Callable[..., Awaitable[dict]]]:
        """Return LiveKit-decorated tools when the installed SDK exposes a decorator."""
        decorator = _livekit_tool_decorator()
        timed_tools = [
            _async_tool(tool, record_tool=self.record_tool) for tool in self.as_callables()
        ]
        if decorator is None:
            return timed_tools
        return [decorator(tool) for tool in timed_tools]

    def capture_as_livekit_tool(self) -> Callable[..., Awaitable[dict]]:
        """Return only the guarded write tool for hybrid grounding mode."""
        tool = _async_tool(self.capture_prospect_interest, record_tool=self.record_tool)
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
) -> Callable[..., Awaitable[dict]]:
    """Adapt sync domain tools for LiveKit SDKs that await function tools."""

    @wraps(tool)
    async def wrapper(*args: Any, **kwargs: Any) -> dict:
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


def build_worker_tools(
    session: Session,
    state: CallState,
    *,
    record_tool: Callable[..., None] | None = None,
) -> WorkerToolSet:
    """Build the call-scoped worker tool adapter."""
    return WorkerToolSet(session, state, record_tool=record_tool)
