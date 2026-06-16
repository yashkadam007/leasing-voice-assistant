# Leasing Voice Assistant

Focused MVP voice AI assistant for property leasing. The assistant will answer grounded property questions and safely register prospect interest after confirmation.

## Status

M10 establishes the repository scaffold, quality tooling, configuration loading, provider interfaces, deterministic fakes, local SQLite persistence, synthetic seed property data, read-only database query tools, Markdown knowledge-base retrieval, deterministic property-resolution state, grounded text-turn answer orchestration, safe prospect-capture write gating, a local text conversation harness, and a transport-neutral voice pipeline with fake STT/model/TTS coverage. Browser or telephony transport integration is planned for later milestones.

## Requirements

- Python 3.12 or newer
- `uv`

## Setup

```bash
uv sync --all-groups
```

M10 does not require provider credentials for setup, tests, linting, formatting, type checks, local database initialization, knowledge-base retrieval, property resolution, grounded text-turn orchestration, prospect capture tests, the local text harness, or fake voice-pipeline tests. Configuration accepts optional local provider credentials through `LVA_`-prefixed environment variables.

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
- `LVA_SPEECH_TO_TEXT_API_KEY`: optional STT provider credential.
- `LVA_TEXT_TO_SPEECH_PROVIDER`: `fake` or `elevenlabs`; defaults to `fake`.
- `LVA_TEXT_TO_SPEECH_MODEL`: ElevenLabs model name; defaults to `eleven_multilingual_v2`.
- `LVA_TEXT_TO_SPEECH_VOICE_ID`: ElevenLabs voice ID for synthesis.
- `LVA_TEXT_TO_SPEECH_API_KEY`: optional TTS provider credential.
- `LVA_TELEPHONY_ACCOUNT_SID`: optional telephony account identifier for future adapters.
- `LVA_TELEPHONY_AUTH_TOKEN`: optional telephony auth token for future adapters.
- `LVA_PROVIDER_TIMEOUT_SECONDS`: optional provider timeout; defaults to `10.0`.
