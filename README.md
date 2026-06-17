# Leasing Voice Assistant

A focused MVP voice AI assistant for property leasing. A caller can ask about a
property, get answers grounded in local property data and knowledge-base
documents, and register interest only after the backend has enough confidence to
write the correct prospect record.

The application is built with Python, FastAPI, SQLite, and `uv`. The live-call
path uses Twilio Media Streams, Deepgram streaming STT, an OpenAI-compatible chat
model, and Deepgram TTS. Tests run entirely offline with deterministic fakes.

## What Works

- Local SQLite persistence for properties, units, prospects, and interests.
- Seed data for Lakeview Flats and Cedar Park Townhomes.
- Markdown knowledge-base retrieval for leasing FAQs and property descriptions.
- Deterministic property and unit resolution across conversation turns.
- Backend-gated prospect capture with phone-based prospect upsert.
- Model-driven read-tool orchestration for natural responses from database and
  knowledge-base evidence.
- A local text conversation harness for debugging the same session flow.
- FastAPI health and Twilio webhook/websocket routes.
- Twilio streaming STT turn detection and raw mu-law TTS playback support.
- Offline test coverage for providers, session state, database tools, KB
  retrieval, prospect writes, voice pipeline, and Twilio transport.

## Current Limits

- Live Twilio verification and demo recording are still pending.
- Browser voice is not implemented; Twilio is the selected voice path.
- Session state is in memory.
- Real provider calls require local credentials.
- This is not a CRM, admin UI, authentication system, or broad property catalog.

## Requirements

- Python 3.12+
- `uv`
- Optional for real calls: Twilio account and number, Deepgram API key,
  OpenAI-compatible model API key, and a public HTTPS tunnel or deployment.

## Quick Start

Install dependencies:

```bash
uv sync --all-groups
```

Initialize the local SQLite database:

```bash
PYTHONPATH=src uv run python -c "from leasing_voice_assistant.persistence import initialize_database; initialize_database().close()"
```

Run the API:

```bash
uv run uvicorn --app-dir src leasing_voice_assistant.app:create_app --factory --reload
```

Check the service:

```bash
curl http://127.0.0.1:8000/health
```

Expected response:

```json
{"status":"ok","service":"leasing-voice-assistant"}
```

## Local Text Demo

The text harness uses the same session service and write gate as the voice path,
but avoids telephony and provider credentials.

```bash
PYTHONPATH=src uv run python -m leasing_voice_assistant.text_harness --debug
```

Try a short flow:

```text
How much is the lake-facing unit at Lakeview Flats?
My name is Avery Lee, my phone is 555-123-4567, and I am interested in this.
quit
```

The generated SQLite database lives in `data/runtime/` and is ignored by Git.

## Real Call Setup

Copy `.env.example` to `.env` and configure real providers:

```bash
LVA_MODEL_PROVIDER=openai_compatible
LVA_MODEL_API_KEY=...
LVA_MODEL_BASE_URL=https://api.openai.com/v1/chat/completions
LVA_MODEL_NAME=gpt-4.1-mini

LVA_SPEECH_TO_TEXT_PROVIDER=deepgram
LVA_SPEECH_TO_TEXT_API_KEY=...
LVA_SPEECH_TO_TEXT_STREAMING_ENABLED=true

LVA_TEXT_TO_SPEECH_PROVIDER=deepgram
LVA_TEXT_TO_SPEECH_API_KEY=...
LVA_DEEPGRAM_TEXT_TO_SPEECH_MODEL=aura-2-thalia-en

LVA_TELEPHONY_PUBLIC_BASE_URL=https://your-public-host.example
LVA_TELEPHONY_ACCOUNT_SID=...
LVA_TELEPHONY_AUTH_TOKEN=...
LVA_TELEPHONY_INBOUND_NUMBER=...
```

Expose the FastAPI app over HTTPS, then configure the Twilio number's inbound
voice webhook:

```text
POST https://your-public-host.example/twilio/voice
```

The app returns TwiML that connects Twilio to:

```text
wss://your-public-host.example/twilio/media
```

`LVA_TELEPHONY_AUTH_TOKEN` enables Twilio signature validation for the inbound
voice webhook. Automated tests do not require Twilio credentials, public tunnels,
real phone numbers, or recordings.

## Configuration

Local secrets belong in `.env`, which is ignored by Git. Supported variables are
documented in `.env.example`.

Defaults use fake providers where possible:

- `LVA_MODEL_PROVIDER=fake`
- `LVA_SPEECH_TO_TEXT_PROVIDER=fake`
- `LVA_TEXT_TO_SPEECH_PROVIDER=fake`

Use Deepgram TTS for Twilio playback. ADR 0013 selected Deepgram because it can
return raw 8 kHz mu-law audio for Media Streams; ElevenLabs remains available for
non-Twilio TTS experiments.

## Quality Checks

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy
```

In restricted environments where `uv` cannot write to the default cache, prefix
commands with:

```bash
UV_CACHE_DIR=.uv-cache
```

## Project Layout

```text
src/leasing_voice_assistant/   Application package
tests/                         Offline automated tests
data/seeds/                    Synthetic property seed data
data/kb/                       Markdown knowledge-base documents
data/migrations/               SQLite schema migrations
docs/project/                  Requirements, architecture, status, runbook
docs/decisions/                Architecture decision records
```

Start with these docs for project context:

- `brief.md`
- `docs/project/REQUIREMENTS.md`
- `docs/project/ARCHITECTURE.md`
- `docs/project/IMPLEMENTATION_PLAN.md`
- `docs/project/STATUS.md`

## Validation Status

The latest recorded validation in `docs/project/STATUS.md` passed:

- `UV_CACHE_DIR=.uv-cache uv run pytest`
- `UV_CACHE_DIR=.uv-cache uv run ruff check .`
- `UV_CACHE_DIR=.uv-cache uv run ruff format --check .`
- `UV_CACHE_DIR=.uv-cache uv run mypy`
- Local database initialization
- Scripted text harness flow

Manual Twilio verification and the final demo recording remain open project
tasks.
