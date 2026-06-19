# Leasing Voice Assistant

Realtime voice assistant for property leasing calls. A caller can ask grounded questions about seeded apartment communities and units, then register interest once the assistant has enough confidence in the caller and target property or unit.

The project uses a small FastAPI control plane, a separate LiveKit worker for the voice call, SQLite for structured property/prospect data, local markdown knowledge retrieval, Deepgram for STT/TTS, and OpenRouter or OpenAI for the LLM.

The implementation is scoped to the assignment: a real voice-to-voice leasing conversation, grounded property answers, conservative property resolution, and safe prospect capture. It is not a CRM or admin product.

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
docs/project/     Architecture, ADRs, runbook, status, and readiness review
tests/            Unit tests for data, retrieval, tools, providers, API, and worker helpers
```

## Prerequisites

- Python 3.12 or newer
- `uv`
- For real voice calls: LiveKit Cloud, a Twilio voice/SIP setup, Deepgram API key, and either OpenRouter or OpenAI credentials
- Optional for outbound SIP test calls: LiveKit `lk` CLI. This is only needed if you want your machine to initiate a SIP test call instead of calling the Twilio number directly.

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

Contextual latency acknowledgments are implemented as a disabled-by-default experiment. Enable
them only for a measured call batch:

```sh
ACKNOWLEDGMENT_MODE=enabled
ACKNOWLEDGMENT_DELAY_MS=750
ACKNOWLEDGMENT_CALL_LIMIT=2
```

The acknowledgment timer starts after caller-turn commitment. Acknowledgment metrics remain
separate from substantive end-to-end response latency.

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

The expected seeded facts are visible in `src/leasing_voice_assistant/db/seed.py` and `data/knowledge/`.

## Run the API

```sh
uv run uvicorn leasing_voice_assistant.api.main:app --reload
```

Health check:

```text
GET /health
```

Prospect capture verification:

```text
GET /prospects
```

The FastAPI app is intentionally not in the realtime audio path. It is a small control plane for health checks and read-only reviewer verification.

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

For an outbound SIP test call initiated from your machine, install and authenticate the LiveKit `lk` CLI, then copy the tracked example and fill in your trunk/phone details:

```sh
cp sip-participant.example.json sip-participant.json
```

To initiate the call directly with LiveKit CLI:

```sh
lk sip participant create sip-participant.json
```

The repository also includes a helper that reads a SIP participant template, generates a unique room and participant identity, and then calls the same LiveKit CLI command:

```sh
uv run leasing-voice-test-call --template sip-participant.json
```

To inspect the generated payload from a clean checkout without calling LiveKit:

```sh
uv run leasing-voice-test-call --dry-run
```

`sip-participant.json` is intentionally ignored because it may contain account-specific phone/trunk details. The tracked `sip-participant.example.json` uses placeholders only.

## Verify prospect capture

After a successful call, inspect captured prospects and interests through the API:

```sh
curl http://127.0.0.1:8000/prospects
```

Or inspect the SQLite database directly:

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

## How the assistant works

The call pipeline is:

```text
Caller
  -> Twilio phone number
  -> LiveKit SIP inbound trunk
  -> LiveKit room
  -> LiveKit Python worker
     -> Deepgram STT
     -> OpenRouter/OpenAI LLM
     -> leasing tools
        -> SQLite property/prospect database
        -> local markdown knowledge retrieval
     -> Deepgram TTS
  -> caller hears response
```

The worker parses SIP metadata into call state, including caller phone number when LiveKit/Twilio provides it. The LLM can call a small tool surface:

- `search_properties`: resolves caller wording to a property or unit candidate and stores the current target.
- `get_unit_details`: reads exact unit facts such as rent, bedrooms, availability, status, view, and square footage from SQLite.
- `search_knowledge_base`: retrieves policy, FAQ, and property narrative snippets from markdown files with source metadata.
- `capture_prospect_interest`: upserts the prospect and writes a property or unit interest only after the code safety gate allows it.

The safety gate rejects capture when phone number, name, target, confidence, ambiguity resolution, or explicit interest confirmation is missing. This guard runs in code before database writes, so the assistant cannot create a prospect interest just because the prompt asks it to.

## Architecture and planning

The planning docs are part of the submission:

- `docs/project/ARCHITECTURE.md`: approach, call/audio pipeline, tool/database flows, knowledge choice, property resolution, prospect capture, safety checks, evaluation thinking, tradeoffs, and future work
- `docs/project/IMPLEMENTATION_PLAN.md`: milestone plan, what was implemented, submission email notes, and evaluation plan
- `docs/project/STATUS.md`: current milestone status, decisions, known limitations, and next action
- `docs/project/adr/`: detailed architecture decision records

In short: exact structured facts come from SQLite through repositories; broader policy and leasing-process answers come from the local markdown knowledge layer; prospect capture is the only write tool and is blocked by deterministic safety checks.

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

## Documentation

- `docs/project/ARCHITECTURE.md`: architecture and tradeoffs
- `docs/project/IMPLEMENTATION_PLAN.md`: planning approach, milestones, and future evaluation
- `docs/project/STATUS.md`: current status, remaining submission tasks, and known limitations
- `docs/project/livekit-twilio-sip-runbook.md`: LiveKit/Twilio setup and manual smoke test
- `docs/project/adr/`: architecture decision records
- `docs/project/SUBMISSION_READINESS_REVIEW.md`: strict submission-readiness review and remaining gaps

## Known limitations and next steps

- Add transcript and tool-event persistence for review and regression analysis.
- Add Langfuse tracing for LLM calls, tool calls, retrieval results, capture rejections, and latency metrics.
- Add an automated evaluation harness, such as an LLM-as-judge rubric over fixed call transcripts and expected tool/write outcomes.
- Improve email capture normalization so spoken addresses like `jack sparrow at the rate gmail dot com` are converted into usable email addresses.
