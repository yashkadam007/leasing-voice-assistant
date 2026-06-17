from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Sequence
from importlib import import_module
from typing import Any, cast

from pydantic import SecretStr

from leasing_voice_assistant.interfaces import (
    ModelMessage,
    ModelResponse,
    StreamingTranscriptEvent,
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


class DeepgramLiveStreamingSpeechToTextProvider:
    def __init__(
        self,
        *,
        api_key: SecretStr | str | None,
        model: str = "nova-2",
        websocket_url: str = "wss://api.deepgram.com/v1/listen",
        language: str = "en-US",
        encoding: str = "mulaw",
        sample_rate: int = 8000,
        endpointing: int = 300,
        interim_results: bool = True,
        timeout_seconds: float = 10.0,
    ) -> None:
        self.api_key = _required_secret(api_key, "Deepgram API key")
        self.model = model
        self.websocket_url = websocket_url
        self.language = language
        self.encoding = encoding
        self.sample_rate = sample_rate
        self.endpointing = endpointing
        self.interim_results = interim_results
        self.timeout_seconds = timeout_seconds

    def start_stream(self) -> DeepgramLiveStreamingSpeechToTextSession:
        sync_client = import_module("websockets.sync.client")
        connect = cast("Any", sync_client).connect
        websocket = connect(
            self._url(),
            additional_headers={"Authorization": f"Token {self.api_key}"},
            open_timeout=self.timeout_seconds,
            close_timeout=self.timeout_seconds,
        )
        return DeepgramLiveStreamingSpeechToTextSession(websocket=websocket)

    def _url(self) -> str:
        query = urllib.parse.urlencode(
            {
                "model": self.model,
                "language": self.language,
                "encoding": self.encoding,
                "sample_rate": str(self.sample_rate),
                "channels": "1",
                "interim_results": str(self.interim_results).lower(),
                "endpointing": str(self.endpointing),
                "smart_format": "true",
            }
        )
        return f"{self.websocket_url}?{query}"


class DeepgramLiveStreamingSpeechToTextSession:
    def __init__(self, *, websocket: Any) -> None:
        self.websocket = websocket
        self.closed = False

    def send_audio(self, audio: bytes) -> Sequence[StreamingTranscriptEvent]:
        self.websocket.send(audio)
        return self._drain_events()

    def poll_events(self) -> Sequence[StreamingTranscriptEvent]:
        return self._drain_events()

    def close(self) -> Sequence[StreamingTranscriptEvent]:
        if self.closed:
            return ()
        self.closed = True
        try:
            self.websocket.send(json.dumps({"type": "CloseStream"}))
            events = list(self._drain_events())
        except Exception:
            events = []
        self.websocket.close()
        events.append(StreamingTranscriptEvent(type="session_close"))
        return tuple(events)

    def _drain_events(self) -> tuple[StreamingTranscriptEvent, ...]:
        events: list[StreamingTranscriptEvent] = []
        while True:
            try:
                raw = self.websocket.recv(timeout=0)
            except TimeoutError:
                break
            except Exception as error:
                return (StreamingTranscriptEvent(type="provider_error", message=str(error)),)
            event = parse_deepgram_streaming_message(raw)
            if event is not None:
                events.append(event)
        return tuple(events)


def parse_deepgram_streaming_message(raw: str | bytes) -> StreamingTranscriptEvent | None:
    try:
        data = json.loads(raw.decode() if isinstance(raw, bytes) else raw)
    except json.JSONDecodeError:
        return StreamingTranscriptEvent(type="provider_error", message="invalid_json")
    if not isinstance(data, dict):
        return StreamingTranscriptEvent(type="provider_error", message="non_object_json")
    message_type = data.get("type")
    if message_type == "CloseStream":
        return StreamingTranscriptEvent(type="session_close")
    if message_type not in {None, "Results"}:
        return None

    channel = data.get("channel")
    if not isinstance(channel, dict):
        if data.get("speech_final") is True:
            return StreamingTranscriptEvent(
                type="utterance_complete",
                event_id=str(data.get("request_id") or data.get("channel_index") or ""),
            )
        return None
    alternatives = channel.get("alternatives")
    if not isinstance(alternatives, list) or not alternatives:
        if data.get("speech_final") is True:
            return StreamingTranscriptEvent(
                type="utterance_complete",
                event_id=str(data.get("request_id") or data.get("channel_index") or ""),
            )
        return None
    alternative = alternatives[0]
    if not isinstance(alternative, dict):
        if data.get("speech_final") is True:
            return StreamingTranscriptEvent(
                type="utterance_complete",
                event_id=str(data.get("request_id") or data.get("channel_index") or ""),
            )
        return None
    transcript_text = alternative.get("transcript")
    if not isinstance(transcript_text, str) or not transcript_text.strip():
        if data.get("speech_final") is True:
            return StreamingTranscriptEvent(
                type="utterance_complete",
                event_id=str(data.get("request_id") or data.get("channel_index") or ""),
            )
        return None
    confidence_value = alternative.get("confidence")
    confidence = float(confidence_value) if isinstance(confidence_value, int | float) else None
    transcript = Transcript(
        text=transcript_text.strip(),
        confidence=confidence,
        metadata=(("provider", "deepgram"),),
    )
    if data.get("speech_final") is True:
        return StreamingTranscriptEvent(
            type="utterance_complete",
            transcript=transcript,
            event_id=str(data.get("request_id") or ""),
        )
    return StreamingTranscriptEvent(
        type="final_transcript" if data.get("is_final") is True else "interim_transcript",
        transcript=transcript,
        event_id=str(data.get("request_id") or ""),
    )


class ElevenLabsTextToSpeechProvider:
    def __init__(
        self,
        *,
        api_key: SecretStr | str | None,
        voice_id: str = "21m00Tcm4TlvDq8ikWAM",
        model: str = "eleven_multilingual_v2",
        output_format: str = "mp3_44100_128",
        base_url: str = "https://api.elevenlabs.io/v1/text-to-speech",
        timeout_seconds: float = 10.0,
    ) -> None:
        self.api_key = _required_secret(api_key, "ElevenLabs API key")
        self.voice_id = voice_id
        self.model = model
        self.output_format = output_format
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def synthesize(self, text: str, *, voice: str | None = None) -> SynthesizedSpeech:
        voice_id = voice or self.voice_id
        payload = {"text": text, "model_id": self.model}
        query = urllib.parse.urlencode({"output_format": self.output_format})
        request = urllib.request.Request(
            f"{self.base_url}/{voice_id}?{query}",
            data=json.dumps(payload).encode(),
            headers={
                "xi-api-key": self.api_key,
                "content-type": "application/json",
                "accept": _elevenlabs_accept_header(self.output_format),
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                audio = response.read()
        except urllib.error.URLError as error:
            raise ProviderRequestError(
                _request_error_message("ElevenLabs text-to-speech", error)
            ) from error
        return SynthesizedSpeech(
            audio=audio,
            content_type=_elevenlabs_content_type(self.output_format),
            metadata=(
                ("provider", "elevenlabs"),
                ("voice_id", voice_id),
                ("model", self.model),
                ("output_format", self.output_format),
            ),
        )


class DeepgramTextToSpeechProvider:
    def __init__(
        self,
        *,
        api_key: SecretStr | str | None,
        model: str = "aura-2-thalia-en",
        base_url: str = "https://api.deepgram.com/v1/speak",
        encoding: str = "mulaw",
        container: str = "none",
        sample_rate: int = 8000,
        timeout_seconds: float = 10.0,
    ) -> None:
        self.api_key = _required_secret(api_key, "Deepgram API key")
        self.model = model
        self.base_url = base_url
        self.encoding = encoding
        self.container = container
        self.sample_rate = sample_rate
        self.timeout_seconds = timeout_seconds

    def synthesize(self, text: str, *, voice: str | None = None) -> SynthesizedSpeech:
        model = voice or self.model
        body = json.dumps({"text": text}).encode()
        query = urllib.parse.urlencode(
            {
                "model": model,
                "encoding": self.encoding,
                "container": self.container,
                "sample_rate": str(self.sample_rate),
            }
        )
        url = f"{self.base_url}?{query}"
        request = urllib.request.Request(
            url,
            data=body,
            headers={
                "authorization": f"Token {self.api_key}",
                "content-type": "application/json",
                "accept": "audio/*",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                audio = response.read()
        except urllib.error.URLError as error:
            raise ProviderRequestError(
                _request_error_message("Deepgram text-to-speech", error)
            ) from error
        return SynthesizedSpeech(
            audio=audio,
            content_type=f"audio/x-mulaw;rate={self.sample_rate}",
            metadata=(
                ("provider", "deepgram"),
                ("model", model),
                ("encoding", self.encoding),
                ("container", self.container),
                ("sample_rate", str(self.sample_rate)),
            ),
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
        raise ProviderRequestError(_request_error_message("model provider", error)) from error
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
        message = _request_error_message("Deepgram speech-to-text", error)
        raise ProviderRequestError(message) from error
    return _decode_json_object(response_body)


def _decode_json_object(body: bytes) -> dict[str, object]:
    try:
        data = json.loads(body.decode())
    except json.JSONDecodeError as error:
        raise ProviderRequestError("provider returned non-JSON response") from error
    if not isinstance(data, dict):
        raise ProviderRequestError("provider returned non-object JSON response")
    return data


def _request_error_message(label: str, error: urllib.error.URLError) -> str:
    status = getattr(error, "code", None)
    reason = getattr(error, "reason", None)
    detail = _error_response_body(error)
    pieces = [f"{label} request failed"]
    if status is not None:
        pieces.append(f"status={status}")
    if reason:
        pieces.append(f"reason={reason}")
    if detail:
        pieces.append(f"body={detail}")
    return "; ".join(pieces)


def _error_response_body(error: urllib.error.URLError) -> str | None:
    read = getattr(error, "read", None)
    if not callable(read):
        return None
    try:
        body = read()
    except Exception:
        return None
    if not isinstance(body, bytes) or not body:
        return None
    return " ".join(body.decode(errors="replace").split())[:500]


def _elevenlabs_accept_header(output_format: str) -> str:
    return "audio/basic" if output_format == "ulaw_8000" else "audio/mpeg"


def _elevenlabs_content_type(output_format: str) -> str:
    return "audio/x-mulaw" if output_format == "ulaw_8000" else "audio/mpeg"
