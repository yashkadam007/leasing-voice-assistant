"""Deepgram speech-to-text adapter."""

from dataclasses import dataclass
from importlib import import_module
from typing import Any

from leasing_voice_assistant.core.config import Settings
from leasing_voice_assistant.providers.errors import (
    ProviderConfigurationError,
    ProviderDependencyError,
)


@dataclass(frozen=True)
class DeepgramSTTAdapter:
    """Build Deepgram STT for the LiveKit worker."""

    settings: Settings
    provider: str = "deepgram"

    def build(self) -> Any:
        """Return a LiveKit Deepgram STT client."""
        api_key = self._api_key()
        try:
            deepgram = import_module("livekit.plugins.deepgram")
        except ImportError as exc:
            raise ProviderDependencyError(self.provider, "STT", "livekit-plugins-deepgram") from exc

        return deepgram.STT(api_key=api_key, model=self.settings.deepgram_stt_model)

    def _api_key(self) -> str:
        api_key = self.settings.deepgram_api_key
        if api_key is None or not api_key.strip():
            raise ProviderConfigurationError(
                self.provider,
                "STT",
                "missing required setting DEEPGRAM_API_KEY",
            )
        return api_key
