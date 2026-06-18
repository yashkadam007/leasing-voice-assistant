# Leasing Voice Assistant

Realtime voice assistant for property leasing calls. A caller can ask grounded questions about seeded apartment communities and units, then register interest once the assistant has enough confidence in the caller and target property or unit.

The project uses a small FastAPI control plane, a separate LiveKit worker for the voice call, SQLite for structured property/prospect data, local markdown knowledge retrieval, Deepgram for STT/TTS, and OpenRouter or OpenAI for the LLM.

## Current capabilities

- Answers exact property and unit questions from SQLite: rent, bedrooms, bathrooms, square footage, availability, view, parking, pet policy, fees, and lease terms.
- Answers broader policy and FAQ questions from local markdown knowledge files in `data/knowledge/`.
- Resolves the caller's target property or unit with deterministic confidence and ambiguity handling.
- Captures prospect interest through a code-enforced safety gate that requires caller phone, caller name, a confident unambiguous target, and explicit interest confirmation.
- Runs local linting, formatting, and tests without LiveKit, Twilio, Deepgram, OpenRouter, or OpenAI credentials.

## Repository map

```text
src/leasing_voice_assistant/
  api/            FastAPI control plane and /health endpoint
  worker/         LiveKit worker, call metadata mapping, voice prompt, tool adapters
  agent/          Call-scoped leasing tools, state, and prospect capture safety gate
  db/             SQLAlchemy models, SQLite setup, seed data
  repositories/   Property and prospect database access
  knowledge/      Local markdown ingestion and lexical retrieval
  providers/      Deepgram/OpenRouter/OpenAI provider adapters
data/knowledge/   Reviewer-readable FAQ and property knowledge source files
docs/project/     Architecture, ADRs, runbook, scenarios, and readiness review
tests/            Unit tests for data, retrieval, tools, providers, API, and worker helpers
```

## Prerequisites

- Python 3.12 or newer
- `uv`
- For real voice calls: LiveKit Cloud, a Twilio voice/SIP setup, Deepgram API key, and either OpenRouter or OpenAI credentials
- Optional for outbound SIP test calls: LiveKit `lk` CLI

## Setup

```sh
uv sync --all-groups
```

Copy the example environment file when running locally:

```sh
cp .env.example .env
```

Tests, linting, formatting checks, and `/health` do not require provider or telephony credentials.

## Environment variables

Required for the real LiveKit worker:

```sh
LIVEKIT_URL=wss://your-project.livekit.cloud
LIVEKIT_API_KEY=...
LIVEKIT_API_SECRET=...
DEEPGRAM_API_KEY=...
OPENROUTER_API_KEY=...
```

Provider defaults:

```sh
STT_PROVIDER=deepgram
TTS_PROVIDER=deepgram
LLM_PROVIDER=openrouter
DEEPGRAM_STT_MODEL=nova-3
DEEPGRAM_TTS_MODEL=aura-2-thalia-en
OPENROUTER_MODEL=openai/gpt-4o-mini
```

To use OpenAI directly instead of OpenRouter:

```sh
LLM_PROVIDER=openai
OPENAI_API_KEY=...
OPENAI_MODEL=gpt-4o-mini
```

See `.env.example` and `docs/project/livekit-twilio-sip-runbook.md` for the full environment list.

`DATABASE_URL` is optional. If unset, the app uses the local default:

```sh
DATABASE_URL=sqlite:///leasing_voice_assistant.db
```

## Seed the database

The worker initializes and seeds the configured SQLite database when a call job starts. To seed manually:

```sh
uv run leasing-voice-seed
```

To reset local seeded data and remove existing prospects/interests:

```sh
uv run leasing-voice-seed --reset
```

Seeded properties:

- Aurora Heights in San Francisco
- Pine Garden Flats in Oakland

The expected facts and manual test conversations are documented in `docs/project/TEST_CONVERSATION_SCENARIOS.md`.

## Run the API

```sh
uv run uvicorn leasing_voice_assistant.api.main:app --reload
```

Health check:

```text
GET /health
```

The FastAPI app is intentionally not in the realtime audio path. It is currently a small control plane and health endpoint.

## Run the voice worker

```sh
uv run leasing-voice-worker
```

The worker connects to LiveKit, waits for assigned room jobs, builds Deepgram STT/TTS and the configured LLM provider, registers the leasing tools, and starts a call-scoped LiveKit agent session.

Missing LiveKit settings fail at worker startup. Missing provider credentials fail when the worker tries to build real call clients.

## Place or simulate a call

Primary path:

1. Configure a LiveKit SIP inbound trunk for a Twilio phone number.
2. Configure a LiveKit inbound dispatch rule that places calls into a room assigned to this worker.
3. Start the worker with the environment variables above.
4. Call the Twilio number.
5. Ask about a seeded property or unit, then ask to be contacted once the property/unit is clear.

Detailed setup is in `docs/project/livekit-twilio-sip-runbook.md`.

For an outbound SIP test call with the LiveKit CLI, create a local `sip-participant.json` payload using your trunk/phone details, then run:

```sh
uv run leasing-voice-test-call
```

To inspect the generated payload without calling LiveKit:

```sh
uv run leasing-voice-test-call --dry-run
```

`sip-participant.json` is intentionally ignored because it may contain account-specific phone/trunk details.

## Verify prospect capture

After a successful call, inspect the SQLite database:

```sh
sqlite3 leasing_voice_assistant.db \
  "select p.id, p.phone_number, p.name, i.property_id, i.unit_id, i.created_at
   from prospects p
   join prospect_interests i on i.prospect_id = p.id
   order by i.created_at desc;"
```

Expected safe capture behavior:

- The assistant does not write a prospect interest without caller phone metadata.
- The assistant asks for the caller's name before capture if it is missing.
- Ambiguous property or unit references are rejected until clarified.
- Repeated captures for the same caller and same property/unit are idempotent.

## Quality checks

```sh
uv run ruff format .
uv run ruff check .
uv run pytest
```

For a non-mutating formatting check:

```sh
uv run ruff format --check .
```

## Architecture summary

```text
Caller
  -> Twilio phone number
  -> LiveKit SIP inbound trunk
  -> LiveKit room
  -> LiveKit Python worker
     -> Deepgram STT
     -> OpenRouter/OpenAI LLM
     -> Leasing tools
        -> SQLite property/prospect database
        -> local markdown knowledge retrieval
     -> Deepgram TTS
  -> caller hears response
```

Exact property and unit facts come from SQLite through `PropertiesRepository`. Policy, process, FAQ, and richer property descriptions come from local markdown files through `KnowledgeBase`. Prospect writes go through `LeasingAgentTools.capture_prospect_interest`, which calls `evaluate_capture_safety` before touching the database.

## Documentation

- `docs/project/ARCHITECTURE.md`: architecture and tradeoffs
- `docs/project/livekit-twilio-sip-runbook.md`: LiveKit/Twilio setup and manual smoke test
- `docs/project/TEST_CONVERSATION_SCENARIOS.md`: manual evaluation scenarios and expected answers
- `docs/project/adr/`: architecture decision records
- `docs/project/SUBMISSION_READINESS_REVIEW.md`: strict submission-readiness review and remaining gaps

## Known limitations and next steps

- Add a tracked `sip-participant.example.json` or make the SIP helper require an explicit template path so the outbound test-call flow is cleaner from a fresh checkout.
- Add a reviewer-facing prospect verification endpoint, or keep the documented SQLite query as the verification path.
- Add an explicit future-evaluation plan, such as an LLM-as-judge rubric over the scenarios in `docs/project/TEST_CONVERSATION_SCENARIOS.md`.
- Consider adding `source` and `status` fields to `prospect_interests` to mirror the brief's sample schema more closely.
