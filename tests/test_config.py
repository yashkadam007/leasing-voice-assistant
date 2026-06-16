from typing import Any

import pytest
from pydantic import ValidationError

from leasing_voice_assistant.config import Settings


def build_settings(**values: Any) -> Settings:
    return Settings(**{"_env_file": None, **values})


def test_settings_load_without_provider_credentials() -> None:
    settings = build_settings()

    assert settings.environment == "local"
    assert settings.model_provider == "fake"
    assert settings.speech_to_text_provider == "fake"
    assert settings.text_to_speech_provider == "fake"
    assert settings.has_model_credentials is False
    assert settings.has_speech_to_text_credentials is False
    assert settings.has_text_to_speech_credentials is False
    assert settings.has_telephony_credentials is False


def test_settings_read_prefixed_environment_values(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LVA_ENVIRONMENT", "test")
    monkeypatch.setenv("LVA_MODEL_PROVIDER", "openai_compatible")
    monkeypatch.setenv("LVA_MODEL_NAME", "gpt-test")
    monkeypatch.setenv("LVA_MODEL_API_KEY", "secret-model-key")
    monkeypatch.setenv("LVA_SPEECH_TO_TEXT_PROVIDER", "deepgram")
    monkeypatch.setenv("LVA_SPEECH_TO_TEXT_API_KEY", "secret-stt-key")
    monkeypatch.setenv("LVA_TEXT_TO_SPEECH_PROVIDER", "elevenlabs")
    monkeypatch.setenv("LVA_TEXT_TO_SPEECH_VOICE_ID", "voice-test")
    monkeypatch.setenv("LVA_TEXT_TO_SPEECH_API_KEY", "secret-tts-key")
    monkeypatch.setenv("LVA_TELEPHONY_ACCOUNT_SID", "secret-account")
    monkeypatch.setenv("LVA_TELEPHONY_AUTH_TOKEN", "secret-token")

    settings = build_settings()

    assert settings.environment == "test"
    assert settings.model_provider == "openai_compatible"
    assert settings.model_name == "gpt-test"
    assert settings.speech_to_text_provider == "deepgram"
    assert settings.text_to_speech_provider == "elevenlabs"
    assert settings.text_to_speech_voice_id == "voice-test"
    assert settings.has_model_credentials is True
    assert settings.has_speech_to_text_credentials is True
    assert settings.has_text_to_speech_credentials is True
    assert settings.has_telephony_credentials is True
    assert "secret-model-key" not in repr(settings)


def test_settings_reject_invalid_environment() -> None:
    with pytest.raises(ValidationError, match="environment"):
        build_settings(environment="staging")
