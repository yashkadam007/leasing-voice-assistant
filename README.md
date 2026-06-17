# Leasing Voice Assistant

Focused MVP voice AI assistant for property leasing. The assistant will answer grounded property questions and safely register prospect interest after confirmation.

## Status

M11.1 establishes the repository scaffold, quality tooling, configuration loading, provider interfaces, deterministic fakes, local SQLite persistence, synthetic seed property data, read-only database query tools, Markdown knowledge-base retrieval, deterministic property-resolution state, grounded text-turn answer orchestration, safe prospect-capture write gating, a local text conversation harness, a transport-neutral voice pipeline, Twilio inbound-call routes, and Deepgram-style streaming STT turn detection with offline media-stream coverage.

## Requirements

- Python 3.12 or newer
- `uv`

## Setup

```bash
uv sync --all-groups
```

M11.1 does not require provider credentials for setup, tests, linting, formatting, type checks, local database initialization, knowledge-base retrieval, property resolution, grounded text-turn orchestration, prospect capture tests, the local text harness, fake voice-pipeline tests, or mocked Twilio/streaming-STT transport tests. Real inbound calls require Twilio plus model, Deepgram streaming STT, and TTS credentials.

## Local Database

Initialize or refresh the local SQLite database with migrations and synthetic seed data:

```bash
PYTHONPATH=src uv run python -c "from leasing_voice_assistant.persistence import initialize_database; initialize_database().close()"
```

The generated database lives under `data/runtime/`, which is ignored by Git. Committed seed data lives in `data/seeds/properties.json`.

## Knowledge Base

Committed knowledge-base source documents live in `data/kb/`. The M05 retriever reads Markdown files from that directory, splits them by headings, and returns source-attributed snippets for policy, FAQ, lease-term, and property-description questions.

## Property Resolution

`leasing_voice_assistant.property_resolution.PropertyResolver` tracks property and optional unit context across text turns using deterministic database-tool evidence. It returns explicit resolution state for resolved, probable, ambiguous, and unresolved cases, and marks ambiguous or unresolved context as not write-ready.

## Answer Orchestration

`leasing_voice_assistant.answer_orchestration.AnswerOrchestrator` handles deterministic text turns. It resolves property context, routes structured property/unit questions to database tools, routes policy and FAQ questions to the Markdown knowledge retriever, returns grounded answer text, and exposes route, evidence, fallback reason, and updated resolution state for tests and future logs.

## Prospect Capture

`leasing_voice_assistant.prospect_capture.ProspectCaptureService` gates prospect writes. It requires write-ready property or unit resolution, plausible caller name and phone, and clear interest intent or explicit confirmation before calling the prospect repository. Blocked and confirmation-required outcomes are returned as structured results for future conversation harnesses.

## Text Conversation Harness

Run a local text conversation against the same session service later voice integrations will use:

```bash
PYTHONPATH=src uv run python -m leasing_voice_assistant.text_harness --debug
```

The harness initializes the local SQLite database, reads the Markdown knowledge base, preserves session state across turns, and can print safe debug traces for answer routing, evidence counts, property resolution, and prospect write-gate outcomes.

## Voice Pipeline

`leasing_voice_assistant.voice_pipeline.VoicePipeline` is the M10 transport-neutral audio path. It accepts bounded audio bytes and content type, transcribes speech through a `SpeechToTextProvider`, calls the same conversation session service used by the text harness, asks a `ModelProvider` to rewrite the safe grounded reply for spoken delivery, validates that model text does not introduce unsupported numbers or unrelated facts, and synthesizes speech through a `TextToSpeechProvider`.

Automated tests use deterministic fake providers and do not call external services. Optional standard-library HTTP adapters live in `leasing_voice_assistant.provider_adapters` for OpenAI-compatible chat completions, Deepgram STT, and ElevenLabs TTS; they fail clearly when selected without credentials.

## Twilio Call Integration

M11/M11.1 add Twilio-facing FastAPI routes:

- `POST /twilio/voice`: answers an inbound Twilio voice webhook with TwiML, says a short greeting, and connects a Twilio Media Stream websocket.
- `WS /twilio/media`: accepts Twilio media-stream events, forwards inbound mu-law audio to streaming STT, accumulates finalized transcript segments until endpointing marks the utterance complete, calls the shared transcript-to-response voice pipeline, preserves call session state, and streams assistant audio back when TTS returns Twilio-compatible mu-law audio.

If `LVA_TELEPHONY_AUTH_TOKEN` is configured, `POST /twilio/voice` validates the `X-Twilio-Signature` header before returning TwiML.

Run the app:

```bash
uv run uvicorn --app-dir src leasing_voice_assistant.app:create_app --factory --host 127.0.0.1 --port 8000
```

For a real call, expose the app with a public HTTPS tunnel or deployment, then set:

```bash
LVA_TELEPHONY_PUBLIC_BASE_URL=https://your-public-host.example
LVA_MODEL_PROVIDER=openai_compatible
LVA_MODEL_API_KEY=...
LVA_SPEECH_TO_TEXT_PROVIDER=deepgram
LVA_SPEECH_TO_TEXT_API_KEY=...
LVA_SPEECH_TO_TEXT_STREAMING_ENABLED=true
LVA_TEXT_TO_SPEECH_PROVIDER=elevenlabs
LVA_TEXT_TO_SPEECH_API_KEY=...
LVA_TEXT_TO_SPEECH_OUTPUT_FORMAT=ulaw_8000
```

Configure the Twilio number's inbound voice webhook to:

```text
POST https://your-public-host.example/twilio/voice
```

The websocket URL is generated as `wss://your-public-host.example/twilio/media`. Automated tests mock Twilio webhook and media events; CI does not require Twilio credentials, public tunnels, real phone numbers, or recordings.

Streaming STT endpointing, not Twilio's stream `stop` event, is the primary caller turn boundary. The older stop-buffer path remains available only when streaming STT is disabled for diagnostics.

## Run

```bash
uv run uvicorn --app-dir src leasing_voice_assistant.app:create_app --factory --reload
```

Then open `http://127.0.0.1:8000/health`.

## Quality Checks

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy
```

## Local Environment

Use `.env` for local secrets. `.env` files are ignored; `.env.example` documents supported variable names.

Supported variables:

- `LVA_ENVIRONMENT`: `local`, `test`, `development`, or `production`; defaults to `local`.
- `LVA_MODEL_PROVIDER`: `fake` or `openai_compatible`; defaults to `fake`.
- `LVA_MODEL_NAME`: model name for the OpenAI-compatible adapter; defaults to `gpt-4.1-mini`.
- `LVA_MODEL_BASE_URL`: chat-completions endpoint for the OpenAI-compatible adapter.
- `LVA_MODEL_API_KEY`: optional model provider credential.
- `LVA_SPEECH_TO_TEXT_PROVIDER`: `fake` or `deepgram`; defaults to `fake`.
- `LVA_SPEECH_TO_TEXT_MODEL`: Deepgram model name; defaults to `nova-2`.
- `LVA_SPEECH_TO_TEXT_STREAMING_ENABLED`: enables streaming STT endpointing for Twilio; defaults to `true`.
- `LVA_SPEECH_TO_TEXT_STREAMING_URL`: Deepgram live websocket URL; defaults to `wss://api.deepgram.com/v1/listen`.
- `LVA_SPEECH_TO_TEXT_LANGUAGE`: Deepgram language code; defaults to `en-US`.
- `LVA_SPEECH_TO_TEXT_ENDPOINTING_MS`: Deepgram endpointing value in milliseconds; defaults to `300`.
- `LVA_SPEECH_TO_TEXT_API_KEY`: optional STT provider credential.
- `LVA_TEXT_TO_SPEECH_PROVIDER`: `fake` or `elevenlabs`; defaults to `fake`.
- `LVA_TEXT_TO_SPEECH_MODEL`: ElevenLabs model name; defaults to `eleven_multilingual_v2`.
- `LVA_TEXT_TO_SPEECH_VOICE_ID`: ElevenLabs voice ID for synthesis.
- `LVA_TEXT_TO_SPEECH_OUTPUT_FORMAT`: ElevenLabs output format; defaults to `mp3_44100_128`. Use `ulaw_8000` for Twilio Media Streams playback.
- `LVA_TEXT_TO_SPEECH_API_KEY`: optional TTS provider credential.
- `LVA_TELEPHONY_ACCOUNT_SID`: optional Twilio account identifier.
- `LVA_TELEPHONY_AUTH_TOKEN`: optional Twilio auth token.
- `LVA_TELEPHONY_PUBLIC_BASE_URL`: public HTTPS base URL used to generate Twilio websocket callback URLs.
- `LVA_TELEPHONY_INBOUND_NUMBER`: optional Twilio inbound phone number documentation field.
- `LVA_PROVIDER_TIMEOUT_SECONDS`: optional provider timeout; defaults to `10.0`.
