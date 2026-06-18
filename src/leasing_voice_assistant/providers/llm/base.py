"""LLM adapter contract."""

from typing import Any, Protocol


class LLMAdapter(Protocol):
    """Constructs an LLM runtime client."""

    provider: str

    def build(self) -> Any:
        """Return the concrete LLM client used by the worker."""
