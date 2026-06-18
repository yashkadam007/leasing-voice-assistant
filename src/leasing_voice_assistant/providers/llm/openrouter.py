"""OpenRouter LLM adapter."""

from dataclasses import dataclass
from importlib import import_module
from typing import Any

from leasing_voice_assistant.core.config import Settings
from leasing_voice_assistant.providers.errors import (
    ProviderConfigurationError,
    ProviderDependencyError,
)


@dataclass(frozen=True)
class OpenRouterLLMAdapter:
    """Build an OpenRouter-backed LLM for the LiveKit worker."""

    settings: Settings
    provider: str = "openrouter"

    def build(self) -> Any:
        """Return a LiveKit OpenAI-compatible LLM client configured for OpenRouter."""
        api_key = self._api_key()
        try:
            openai = import_module("livekit.plugins.openai")
        except ImportError as exc:
            raise ProviderDependencyError(self.provider, "LLM", "livekit-plugins-openai") from exc

        llm_class = openai.LLM
        if hasattr(llm_class, "with_openrouter"):
            return llm_class.with_openrouter(api_key=api_key, model=self.settings.openrouter_model)

        return llm_class(
            api_key=api_key,
            base_url=self.settings.openrouter_base_url,
            model=self.settings.openrouter_model,
        )

    def _api_key(self) -> str:
        api_key = self.settings.openrouter_api_key
        if api_key is None or not api_key.strip():
            raise ProviderConfigurationError(
                self.provider,
                "LLM",
                "missing required setting OPENROUTER_API_KEY",
            )
        return api_key
