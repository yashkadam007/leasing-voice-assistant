"""OpenAI LLM adapter."""

from dataclasses import dataclass
from importlib import import_module
from typing import Any

from leasing_voice_assistant.core.config import Settings
from leasing_voice_assistant.providers.errors import (
    ProviderConfigurationError,
    ProviderDependencyError,
)


@dataclass(frozen=True)
class OpenAILLMAdapter:
    """Build a direct OpenAI-backed LLM for the LiveKit worker."""

    settings: Settings
    provider: str = "openai"

    def build(self) -> Any:
        """Return a LiveKit OpenAI LLM client configured for direct OpenAI usage."""
        api_key = self._api_key()
        try:
            openai = import_module("livekit.plugins.openai")
        except ImportError as exc:
            raise ProviderDependencyError(self.provider, "LLM", "livekit-plugins-openai") from exc

        return openai.LLM(
            api_key=api_key,
            model=self.settings.openai_model,
        )

    def _api_key(self) -> str:
        api_key = self.settings.openai_api_key
        if api_key is None or not api_key.strip():
            raise ProviderConfigurationError(
                self.provider,
                "LLM",
                "missing required setting OPENAI_API_KEY",
            )
        return api_key
