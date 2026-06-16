import pytest

from leasing_voice_assistant.provider_adapters import (
    DeepgramSpeechToTextProvider,
    ElevenLabsTextToSpeechProvider,
    OpenAICompatibleModelProvider,
    ProviderConfigurationError,
)


def test_real_provider_adapters_fail_clearly_without_credentials() -> None:
    with pytest.raises(ProviderConfigurationError, match="model API key"):
        OpenAICompatibleModelProvider(api_key=None)
    with pytest.raises(ProviderConfigurationError, match="Deepgram API key"):
        DeepgramSpeechToTextProvider(api_key=None)
    with pytest.raises(ProviderConfigurationError, match="ElevenLabs API key"):
        ElevenLabsTextToSpeechProvider(api_key=None)
