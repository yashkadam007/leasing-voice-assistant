"""Text-to-speech adapter contract."""

from typing import Any, Protocol


class TTSAdapter(Protocol):
    """Constructs a text-to-speech runtime client."""

    provider: str

    def build(self) -> Any:
        """Return the concrete TTS client used by the worker."""
