from __future__ import annotations

import json
import urllib.error
import urllib.request
from collections.abc import Sequence
from typing import Any, cast

from pydantic import SecretStr

from leasing_voice_assistant.interfaces import (
    ModelMessage,
    ModelResponse,
    SynthesizedSpeech,
    Transcript,
)


class ProviderConfigurationError(ValueError):
    """Raised when a real provider adapter is selected without required settings."""


class ProviderRequestError(RuntimeError):
    """Raised when a real provider HTTP request fails."""


class OpenAICompatibleModelProvider:
    def __init__(
        self,
        *,
        api_key: SecretStr | str | None,
        model: str = "gpt-4.1-mini",
        base_url: str = "https://api.openai.com/v1/chat/completions",
        timeout_seconds: float = 10.0,
    ) -> None:
        self.api_key = _required_secret(api_key, "model API key")
        self.model = model
        self.base_url = base_url
        self.timeout_seconds = timeout_seconds

    def generate(self, messages: Sequence[ModelMessage]) -> ModelResponse:
        payload = {
            "model": self.model,
            "messages": [
                {"role": message.role, "content": message.content} for message in messages
            ],
            "temperature": 0.2,
        }
        data = _json_request(
            self.base_url,
            api_key=self.api_key,
            payload=payload,
            timeout_seconds=self.timeout_seconds,
        )
        try:
            choices = cast("list[dict[str, Any]]", data["choices"])
            message = cast("dict[str, Any]", choices[0]["message"])
            text = str(message["content"])
        except (KeyError, IndexError, TypeError) as error:
            raise ProviderRequestError("model provider returned an unexpected response") from error
        return ModelResponse(
            text=text, metadata=(("provider", "openai_compatible"), ("model", self.model))
        )


class DeepgramSpeechToTextProvider:
    def __init__(
        self,
        *,
        api_key: SecretStr | str | None,
        model: str = "nova-2",
        base_url: str = "https://api.deepgram.com/v1/listen",
        timeout_seconds: float = 10.0,
    ) -> None:
        self.api_key = _required_secret(api_key, "Deepgram API key")
        self.model = model
        self.base_url = base_url
        self.timeout_seconds = timeout_seconds

    def transcribe(self, audio: bytes, *, content_type: str) -> Transcript:
        url = f"{self.base_url}?model={self.model}&smart_format=true"
        data = _binary_request(
            url,
            api_key=self.api_key,
            body=audio,
            content_type=content_type,
            timeout_seconds=self.timeout_seconds,
        )
        try:
            results = cast("dict[str, Any]", data["results"])
            channels = cast("list[dict[str, Any]]", results["channels"])
            alternatives = cast("list[dict[str, Any]]", channels[0]["alternatives"])
            alternative = alternatives[0]
            text = str(alternative["transcript"])
            confidence = float(alternative["confidence"])
        except (KeyError, IndexError, TypeError, ValueError) as error:
            raise ProviderRequestError("Deepgram returned an unexpected response") from error
        return Transcript(
            text=text,
            confidence=confidence,
            metadata=(("provider", "deepgram"), ("model", self.model)),
        )


class ElevenLabsTextToSpeechProvider:
    def __init__(
        self,
        *,
        api_key: SecretStr | str | None,
        voice_id: str = "21m00Tcm4TlvDq8ikWAM",
        model: str = "eleven_multilingual_v2",
        base_url: str = "https://api.elevenlabs.io/v1/text-to-speech",
        timeout_seconds: float = 10.0,
    ) -> None:
        self.api_key = _required_secret(api_key, "ElevenLabs API key")
        self.voice_id = voice_id
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def synthesize(self, text: str, *, voice: str | None = None) -> SynthesizedSpeech:
        voice_id = voice or self.voice_id
        payload = {"text": text, "model_id": self.model}
        request = urllib.request.Request(
            f"{self.base_url}/{voice_id}",
            data=json.dumps(payload).encode(),
            headers={
                "xi-api-key": self.api_key,
                "content-type": "application/json",
                "accept": "audio/mpeg",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                audio = response.read()
        except urllib.error.URLError as error:
            raise ProviderRequestError("ElevenLabs text-to-speech request failed") from error
        return SynthesizedSpeech(
            audio=audio,
            content_type="audio/mpeg",
            metadata=(("provider", "elevenlabs"), ("voice_id", voice_id), ("model", self.model)),
        )


def _required_secret(value: SecretStr | str | None, label: str) -> str:
    if value is None:
        raise ProviderConfigurationError(f"Missing required {label}")
    secret = value.get_secret_value() if isinstance(value, SecretStr) else value
    if not secret:
        raise ProviderConfigurationError(f"Missing required {label}")
    return secret


def _json_request(
    url: str,
    *,
    api_key: str,
    payload: object,
    timeout_seconds: float,
) -> dict[str, object]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={
            "authorization": f"Bearer {api_key}",
            "content-type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            body = response.read()
    except urllib.error.URLError as error:
        raise ProviderRequestError("model provider request failed") from error
    return _decode_json_object(body)


def _binary_request(
    url: str,
    *,
    api_key: str,
    body: bytes,
    content_type: str,
    timeout_seconds: float,
) -> dict[str, object]:
    request = urllib.request.Request(
        url,
        data=body,
        headers={
            "authorization": f"Token {api_key}",
            "content-type": content_type,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            response_body = response.read()
    except urllib.error.URLError as error:
        raise ProviderRequestError("Deepgram speech-to-text request failed") from error
    return _decode_json_object(response_body)


def _decode_json_object(body: bytes) -> dict[str, object]:
    try:
        data = json.loads(body.decode())
    except json.JSONDecodeError as error:
        raise ProviderRequestError("provider returned non-JSON response") from error
    if not isinstance(data, dict):
        raise ProviderRequestError("provider returned non-object JSON response")
    return data
