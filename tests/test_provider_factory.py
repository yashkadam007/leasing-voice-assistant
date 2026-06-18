import sys
from types import ModuleType

import pytest

from leasing_voice_assistant.core.config import Settings
from leasing_voice_assistant.providers.errors import (
    ProviderConfigurationError,
    ProviderDependencyError,
)
from leasing_voice_assistant.providers.factory import ProviderFactory
from leasing_voice_assistant.providers.llm.openrouter import OpenRouterLLMAdapter
from leasing_voice_assistant.providers.stt import deepgram as stt_deepgram
from leasing_voice_assistant.providers.stt.deepgram import DeepgramSTTAdapter
from leasing_voice_assistant.providers.tts.deepgram import DeepgramTTSAdapter
from leasing_voice_assistant.worker.main import build_provider_factory


def settings_for_test(**kwargs) -> Settings:
    return Settings(_env_file=None, **kwargs)


def test_factory_selects_default_adapters_without_credentials() -> None:
    factory = ProviderFactory(settings_for_test(app_env="test"))

    assert isinstance(factory.build_stt_adapter(), DeepgramSTTAdapter)
    assert isinstance(factory.build_tts_adapter(), DeepgramTTSAdapter)
    assert isinstance(factory.build_llm_adapter(), OpenRouterLLMAdapter)


@pytest.mark.parametrize(
    ("component", "build_method", "provider", "setting"),
    [
        ("STT", "build_stt", "deepgram", "DEEPGRAM_API_KEY"),
        ("TTS", "build_tts", "deepgram", "DEEPGRAM_API_KEY"),
        ("LLM", "build_llm", "openrouter", "OPENROUTER_API_KEY"),
    ],
)
def test_factory_reports_missing_credentials(
    component: str, build_method: str, provider: str, setting: str
) -> None:
    factory = ProviderFactory(
        settings_for_test(
            app_env="test",
            deepgram_api_key=None,
            openrouter_api_key=None,
        )
    )

    with pytest.raises(ProviderConfigurationError) as exc_info:
        getattr(factory, build_method)()

    message = str(exc_info.value)
    assert component in message
    assert provider in message
    assert setting in message


def test_factory_reports_missing_provider_sdk(monkeypatch) -> None:
    def raise_import_error(_module_name: str) -> ModuleType:
        raise ImportError("module missing")

    monkeypatch.setattr(stt_deepgram, "import_module", raise_import_error)
    factory = ProviderFactory(
        settings_for_test(
            app_env="test",
            deepgram_api_key="dg-test",
        )
    )

    with pytest.raises(ProviderDependencyError) as exc_info:
        factory.build_stt()

    assert "deepgram STT" in str(exc_info.value)
    assert "livekit-plugins-deepgram" in str(exc_info.value)


def test_factory_builds_deepgram_clients_with_configured_models(monkeypatch) -> None:
    deepgram = ModuleType("livekit.plugins.deepgram")

    class STT:
        def __init__(self, **kwargs) -> None:
            self.kwargs = kwargs

    class TTS:
        def __init__(self, **kwargs) -> None:
            self.kwargs = kwargs

    deepgram.STT = STT
    deepgram.TTS = TTS
    monkeypatch.setitem(sys.modules, "livekit.plugins.deepgram", deepgram)

    factory = ProviderFactory(
        settings_for_test(
            app_env="test",
            deepgram_api_key="dg-test",
            deepgram_stt_model="nova-test",
            deepgram_tts_model="aura-test",
        )
    )

    assert factory.build_stt().kwargs == {"api_key": "dg-test", "model": "nova-test"}
    assert factory.build_tts().kwargs == {"api_key": "dg-test", "model": "aura-test"}


def test_factory_builds_openrouter_llm_with_configured_model(monkeypatch) -> None:
    openai = ModuleType("livekit.plugins.openai")

    class LLM:
        @classmethod
        def with_openrouter(cls, **kwargs) -> dict[str, object]:
            return {"provider": "openrouter", "kwargs": kwargs}

    openai.LLM = LLM
    monkeypatch.setitem(sys.modules, "livekit.plugins.openai", openai)

    factory = ProviderFactory(
        settings_for_test(
            app_env="test",
            openrouter_api_key="or-test",
            openrouter_model="openrouter/test-model",
        )
    )

    assert factory.build_llm() == {
        "provider": "openrouter",
        "kwargs": {"api_key": "or-test", "model": "openrouter/test-model"},
    }


def test_worker_exposes_provider_factory_without_constructing_clients() -> None:
    factory = build_provider_factory(settings_for_test(app_env="test"))

    assert factory.settings.app_env == "test"
    assert isinstance(factory.build_stt_adapter(), DeepgramSTTAdapter)
