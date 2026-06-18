"""Speech-to-text adapter contract."""

from typing import Any, Protocol


class STTAdapter(Protocol):
    """Constructs a speech-to-text runtime client."""

    provider: str

    def build(self) -> Any:
        """Return the concrete STT client used by the worker."""
