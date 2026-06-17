from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

EnvironmentName = Literal["local", "test", "development", "production"]
ModelProviderName = Literal["fake", "openai_compatible"]
SpeechToTextProviderName = Literal["fake", "deepgram"]
TextToSpeechProviderName = Literal["fake", "elevenlabs"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="LVA_",
        extra="ignore",
    )

    app_name: str = "Leasing Voice Assistant"
    environment: EnvironmentName = "local"
    model_provider: ModelProviderName = "fake"
    model_name: str = "gpt-4.1-mini"
    model_base_url: str = "https://api.openai.com/v1/chat/completions"
    model_api_key: SecretStr | None = None
    speech_to_text_provider: SpeechToTextProviderName = "fake"
    speech_to_text_model: str = "nova-2"
    speech_to_text_streaming_enabled: bool = True
    speech_to_text_streaming_url: str = "wss://api.deepgram.com/v1/listen"
    speech_to_text_language: str = "en-US"
    speech_to_text_endpointing_ms: int = Field(default=300, gt=0)
    speech_to_text_api_key: SecretStr | None = None
    text_to_speech_provider: TextToSpeechProviderName = "fake"
    text_to_speech_model: str = "eleven_multilingual_v2"
    text_to_speech_voice_id: str = "21m00Tcm4TlvDq8ikWAM"
    text_to_speech_output_format: str = "mp3_44100_128"
    text_to_speech_api_key: SecretStr | None = None
    telephony_account_sid: SecretStr | None = None
    telephony_auth_token: SecretStr | None = None
    telephony_public_base_url: str | None = None
    telephony_inbound_number: str | None = None
    provider_timeout_seconds: float = Field(default=10.0, gt=0)

    @property
    def has_model_credentials(self) -> bool:
        return self.model_api_key is not None

    @property
    def has_speech_to_text_credentials(self) -> bool:
        return self.speech_to_text_api_key is not None

    @property
    def has_text_to_speech_credentials(self) -> bool:
        return self.text_to_speech_api_key is not None

    @property
    def has_telephony_credentials(self) -> bool:
        return self.telephony_account_sid is not None and self.telephony_auth_token is not None


@lru_cache
def get_settings() -> Settings:
    return Settings()
