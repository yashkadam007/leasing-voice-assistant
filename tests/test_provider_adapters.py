import pytest

from leasing_voice_assistant.provider_adapters import (
    DeepgramLiveStreamingSpeechToTextProvider,
    DeepgramSpeechToTextProvider,
    ElevenLabsTextToSpeechProvider,
    OpenAICompatibleModelProvider,
    ProviderConfigurationError,
    parse_deepgram_streaming_message,
)


def test_real_provider_adapters_fail_clearly_without_credentials() -> None:
    with pytest.raises(ProviderConfigurationError, match="model API key"):
        OpenAICompatibleModelProvider(api_key=None)
    with pytest.raises(ProviderConfigurationError, match="Deepgram API key"):
        DeepgramSpeechToTextProvider(api_key=None)
    with pytest.raises(ProviderConfigurationError, match="Deepgram API key"):
        DeepgramLiveStreamingSpeechToTextProvider(api_key=None)
    with pytest.raises(ProviderConfigurationError, match="ElevenLabs API key"):
        ElevenLabsTextToSpeechProvider(api_key=None)


def test_elevenlabs_adapter_accepts_twilio_mulaw_output_format() -> None:
    provider = ElevenLabsTextToSpeechProvider(
        api_key="secret",
        output_format="ulaw_8000",
    )

    assert provider.output_format == "ulaw_8000"


def test_deepgram_live_adapter_builds_twilio_mulaw_stream_url() -> None:
    provider = DeepgramLiveStreamingSpeechToTextProvider(
        api_key="secret",
        model="nova-3",
        websocket_url="wss://deepgram.example/v1/listen",
        endpointing=250,
    )

    url = provider._url()

    assert url.startswith("wss://deepgram.example/v1/listen?")
    assert "model=nova-3" in url
    assert "encoding=mulaw" in url
    assert "sample_rate=8000" in url
    assert "endpointing=250" in url


def test_parse_deepgram_streaming_final_and_speech_final_events() -> None:
    final = parse_deepgram_streaming_message(
        """
        {
          "type": "Results",
          "is_final": true,
          "speech_final": false,
          "channel": {
            "alternatives": [
              {"transcript": "How much is Lakeview Flats?", "confidence": 0.94}
            ]
          }
        }
        """
    )
    endpoint = parse_deepgram_streaming_message(
        '{"type": "Results", "is_final": true, "speech_final": true, "request_id": "abc"}'
    )

    assert final is not None
    assert final.type == "final_transcript"
    assert final.transcript is not None
    assert final.transcript.text == "How much is Lakeview Flats?"
    assert final.transcript.confidence == 0.94
    assert endpoint is not None
    assert endpoint.type == "utterance_complete"
    assert endpoint.event_id == "abc"


def test_parse_deepgram_streaming_speech_final_can_include_transcript() -> None:
    endpoint = parse_deepgram_streaming_message(
        """
        {
          "type": "Results",
          "is_final": true,
          "speech_final": true,
          "request_id": "abc",
          "channel": {
            "alternatives": [
              {"transcript": "I am interested in Lakeview Flats", "confidence": 0.88}
            ]
          }
        }
        """
    )

    assert endpoint is not None
    assert endpoint.type == "utterance_complete"
    assert endpoint.transcript is not None
    assert endpoint.transcript.text == "I am interested in Lakeview Flats"
    assert endpoint.transcript.confidence == 0.88


def test_parse_deepgram_streaming_ignores_empty_transcripts_and_reports_malformed() -> None:
    empty = parse_deepgram_streaming_message(
        '{"type": "Results", "channel": {"alternatives": [{"transcript": ""}]}}'
    )
    malformed = parse_deepgram_streaming_message("{")

    assert empty is None
    assert malformed is not None
    assert malformed.type == "provider_error"
    assert malformed.message == "invalid_json"
