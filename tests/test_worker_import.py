import pytest

from leasing_voice_assistant.core.config import Settings
from leasing_voice_assistant.providers.errors import ProviderConfigurationError
from leasing_voice_assistant.worker.main import (
    build_provider_factory,
    build_turn_detection_config,
    build_turn_handling_options,
    build_worker_config,
    create_worker_options,
    validate_livekit_settings,
)


def settings_for_test(**kwargs) -> Settings:
    return Settings(_env_file=None, **kwargs)


def test_worker_entrypoint_builds_without_provider_credentials() -> None:
    config = build_worker_config(settings_for_test(app_env="test", livekit_url=None))

    assert config == {
        "environment": "test",
        "livekit_url": None,
        "stt_provider": "deepgram",
        "tts_provider": "deepgram",
        "llm_provider": "openrouter",
    }


def test_worker_livekit_validation_is_explicit_but_not_import_time() -> None:
    with pytest.raises(ProviderConfigurationError) as exc_info:
        validate_livekit_settings(
            settings_for_test(
                app_env="test",
                livekit_url=None,
                livekit_api_key=None,
                livekit_api_secret=None,
            )
        )

    assert "LIVEKIT_URL" in str(exc_info.value)
    assert "LIVEKIT_API_KEY" in str(exc_info.value)
    assert "LIVEKIT_API_SECRET" in str(exc_info.value)


def test_worker_provider_factory_builds_without_constructing_clients() -> None:
    factory = build_provider_factory(settings_for_test(app_env="test"))

    assert factory.settings.app_env == "test"


def test_turn_handling_options_use_current_livekit_shape() -> None:
    from livekit import agents

    config = build_turn_detection_config()
    options = build_turn_handling_options(agents, config)

    assert options["endpointing"] == {
        "mode": "fixed",
        "min_delay": 0.5,
        "max_delay": 1.0,
    }
    assert options["interruption"] == {
        "enabled": True,
        "mode": "adaptive",
        "min_duration": 0.5,
        "min_words": 0,
    }
    assert options["turn_detection"].model == "turn-detector-v1-mini"


def test_worker_options_use_default_agent_dispatch_name() -> None:
    options = create_worker_options(
        settings_for_test(
            app_env="test",
            livekit_url="wss://livekit.example.test",
            livekit_api_key="test-key",
            livekit_api_secret="test-secret",
        )
    )

    assert options.agent_name == ""
