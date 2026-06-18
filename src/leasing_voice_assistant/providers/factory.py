"""Provider factory for the LiveKit worker."""

from dataclasses import dataclass
from typing import Any

from leasing_voice_assistant.core.config import Settings, get_settings
from leasing_voice_assistant.providers.errors import ProviderConfigurationError
from leasing_voice_assistant.providers.llm.base import LLMAdapter
from leasing_voice_assistant.providers.llm.openrouter import OpenRouterLLMAdapter
from leasing_voice_assistant.providers.stt.base import STTAdapter
from leasing_voice_assistant.providers.stt.deepgram import DeepgramSTTAdapter
from leasing_voice_assistant.providers.tts.base import TTSAdapter
from leasing_voice_assistant.providers.tts.deepgram import DeepgramTTSAdapter


@dataclass(frozen=True)
class ProviderClients:
    """Concrete runtime clients built for one worker session."""

    stt: Any
    tts: Any
    llm: Any


class ProviderFactory:
    """Select and construct configured STT, TTS, and LLM providers."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def build_stt_adapter(self) -> STTAdapter:
        """Return the selected STT adapter without constructing provider SDK clients."""
        if self.settings.stt_provider == "deepgram":
            return DeepgramSTTAdapter(self.settings)
        raise ProviderConfigurationError(
            str(self.settings.stt_provider), "STT", "unsupported STT_PROVIDER"
        )

    def build_tts_adapter(self) -> TTSAdapter:
        """Return the selected TTS adapter without constructing provider SDK clients."""
        if self.settings.tts_provider == "deepgram":
            return DeepgramTTSAdapter(self.settings)
        raise ProviderConfigurationError(
            str(self.settings.tts_provider), "TTS", "unsupported TTS_PROVIDER"
        )

    def build_llm_adapter(self) -> LLMAdapter:
        """Return the selected LLM adapter without constructing provider SDK clients."""
        if self.settings.llm_provider == "openrouter":
            return OpenRouterLLMAdapter(self.settings)
        raise ProviderConfigurationError(
            str(self.settings.llm_provider), "LLM", "unsupported LLM_PROVIDER"
        )

    def build_stt(self) -> Any:
        """Build the selected STT runtime client."""
        return self.build_stt_adapter().build()

    def build_tts(self) -> Any:
        """Build the selected TTS runtime client."""
        return self.build_tts_adapter().build()

    def build_llm(self) -> Any:
        """Build the selected LLM runtime client."""
        return self.build_llm_adapter().build()

    def build_clients(self) -> ProviderClients:
        """Build all provider runtime clients for the worker."""
        return ProviderClients(
            stt=self.build_stt(),
            tts=self.build_tts(),
            llm=self.build_llm(),
        )
