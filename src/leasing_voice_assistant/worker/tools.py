"""LiveKit tool adapters for leasing agent domain tools."""

from __future__ import annotations

from collections.abc import Callable
from importlib import import_module

from sqlalchemy.orm import Session

from leasing_voice_assistant.agent import CallState, LeasingAgentTools


class WorkerToolSet:
    """Call-scoped worker tool surface backed by domain leasing tools."""

    def __init__(self, session: Session, state: CallState) -> None:
        self.domain_tools = LeasingAgentTools(session, state)

    def search_properties(self, query: str, limit: int = 5) -> dict:
        """Search property and unit records from caller wording."""
        return self.domain_tools.search_properties(query, limit=limit)

    def get_unit_details(self, unit_id: int) -> dict:
        """Return authoritative facts for a specific unit."""
        return self.domain_tools.get_unit_details(unit_id)

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
        return self.domain_tools.capture_prospect_interest(
            caller_name=caller_name,
            caller_email=caller_email,
            confirmed_interest=confirmed_interest,
            notes=notes,
        )

    def as_callables(self) -> list[Callable[..., dict]]:
        """Return undecorated callables for tests or runtimes without LiveKit installed."""
        return [
            self.search_properties,
            self.get_unit_details,
            self.search_knowledge_base,
            self.capture_prospect_interest,
        ]

    def as_livekit_tools(self) -> list[Callable[..., dict]]:
        """Return LiveKit-decorated tools when the installed SDK exposes a decorator."""
        decorator = _livekit_tool_decorator()
        if decorator is None:
            return self.as_callables()
        return [decorator(tool) for tool in self.as_callables()]


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


def build_worker_tools(session: Session, state: CallState) -> WorkerToolSet:
    """Build the call-scoped worker tool adapter."""
    return WorkerToolSet(session, state)
