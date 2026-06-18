# Leasing Voice Assistant Architecture

## Purpose

This repository implements a focused leasing voice assistant for inbound calls. A prospective renter can ask about seeded properties and units, get answers grounded in local data, and be captured as a prospect only after the assistant has a confident property or unit target, caller identity, and explicit interest confirmation.

The center of the system is the voice worker. FastAPI exists only as a small control plane for health and reviewer verification; it is not in the realtime audio path.

## Approach

The implementation is intentionally small and local-first:

- LiveKit Agents owns the realtime voice session and room lifecycle.
- Twilio routes inbound phone calls into LiveKit SIP.
- Deepgram provides speech-to-text and text-to-speech.
- OpenRouter or OpenAI provides the LLM through a provider adapter.
- SQLite stores authoritative structured leasing data and prospect writes.
- Local markdown files provide policy, FAQ, and narrative knowledge through deterministic lexical retrieval.
- Agent tools are narrow, structured, and testable without voice or provider credentials.

This keeps the assignment focused on the voice agent, grounded answers, property resolution, and safe prospect capture rather than on a CRM, admin UI, or hosted retrieval infrastructure.

## Call And Audio Pipeline

```text
Caller
  -> Twilio phone number
  -> LiveKit SIP inbound trunk
  -> LiveKit room/job
  -> LiveKit Python worker
     -> parse SIP/call metadata into CallState
     -> build Deepgram STT
     -> build OpenRouter/OpenAI LLM
     -> register leasing tools
     -> build Deepgram TTS
     -> run LiveKit AgentSession with turn handling
  -> caller hears the spoken response

FastAPI control plane
  -> GET /health
  -> GET /prospects for read-only demo verification
```

Runtime responsibilities:

- Twilio provides the phone number and SIP routing.
- LiveKit SIP converts the phone call into a LiveKit room participant.
- The worker joins the assigned LiveKit job, waits for the caller participant, and extracts caller metadata such as phone number and call identifiers when available.
- LiveKit AgentSession streams caller audio through STT, sends turns and tool calls through the LLM, and returns assistant text through TTS.
- Turn handling is configured centrally in `worker/main.py` with interruption support and conservative endpointing defaults for short leasing conversations.

FastAPI is deliberately separate. A failed or stopped API should not be part of the audio loop once the worker is handling LiveKit jobs.

## Runtime Components

### LiveKit Worker

The worker is the primary runtime. It:

- validates LiveKit settings when the real worker starts
- creates the SQLite engine and seeds local data at job startup
- builds STT, LLM, and TTS clients through `ProviderFactory`
- converts SIP metadata into `CallState`
- wraps domain tools as LiveKit function tools
- starts a LiveKit `AgentSession` with leasing-specific instructions
- logs transcripts, tool execution summaries, assistant responses, and session lifecycle events

The worker package is under `src/leasing_voice_assistant/worker/`:

- `main.py`: LiveKit entrypoint, provider/session setup, turn handling, and realtime diagnostics.
- `call_context.py`: defensive room and participant metadata extraction.
- `prompts.py`: leasing-specific voice instructions.
- `tools.py`: LiveKit tool adapters around domain tools.

### FastAPI Control Plane

FastAPI stays intentionally small:

- `GET /health` verifies the app can start without provider credentials.
- `GET /prospects` returns recently updated prospects and interests for demo verification.

The API does not dispatch calls, proxy audio, or implement a CRM.

### SQLite Database

SQLite is the source of truth for structured facts and prospect writes. The schema covers:

- `properties`: property name, address, city/state, phone, description, pet policy, parking policy, application fee, security deposit, and lease terms.
- `units`: unit number, bedrooms, bathrooms, rent, square footage, availability date, status, floor, view, and notes.
- `prospects`: normalized caller phone number, name, email, and timestamps.
- `prospect_interests`: idempotent interest in exactly one property or one unit.

The database is accessed through repository classes, not raw SQL in prompts or worker code.

## Agent Tools And Database Flow

The LLM receives four leasing tools through the worker adapter. The actual behavior lives in `LeasingAgentTools`, which keeps it unit-testable outside LiveKit.

### `search_properties`

Purpose: resolve caller wording to a property or unit candidate.

Read path:

```text
LLM tool call
  -> WorkerToolSet.search_properties
  -> LeasingAgentTools.search_properties
  -> PropertiesRepository.search
  -> properties + units tables
```

Behavior:

- Searches property names, address, city, description, unit number, unit status, unit view, and unit notes.
- Normalizes spoken unit phrases such as "unit eight A" to `8A`.
- Scores exact property and unit matches highly.
- Stores the best target in `CallState`.
- Marks multiple candidates as ambiguous so capture remains blocked until clarified.

### `get_unit_details`

Purpose: retrieve authoritative unit facts.

Read path:

```text
LLM tool call
  -> WorkerToolSet.get_unit_details
  -> LeasingAgentTools.get_unit_details
  -> PropertiesRepository.get_units_by_number
  -> units table joined to property
```

Behavior:

- Returns rent, bedrooms, bathrooms, square footage, availability, status, floor, view, notes, and property-level policies.
- Uses current property context to disambiguate duplicate unit numbers when possible.
- Updates `CallState` to a unit target when exactly one unit is resolved.

Exact facts such as rent, bedrooms, availability, parking, pet policy, and status should come from this structured data path.

### `search_knowledge_base`

Purpose: answer policy, process, FAQ, and narrative questions with source-backed snippets.

Read path:

```text
LLM tool call
  -> WorkerToolSet.search_knowledge_base
  -> LeasingAgentTools.search_knowledge_base
  -> KnowledgeBase.search
  -> data/knowledge/*.md chunks
```

Behavior:

- Searches local markdown chunks.
- Returns snippet text plus source path, document title, section, chunk id, and optional property identifier.
- Supports property filtering when the caller's target property is known.
- Returns `no_match` when the score is below threshold so the agent can say the information is not available.

### `capture_prospect_interest`

Purpose: create or update the caller as a prospect and record interest only after safety checks pass.

Write path:

```text
LLM tool call
  -> WorkerToolSet.capture_prospect_interest
  -> LeasingAgentTools.capture_prospect_interest
  -> evaluate_capture_safety
  -> ProspectsRepository.upsert_by_phone
  -> ProspectsRepository.create_interest
  -> prospects + prospect_interests tables
  -> commit in worker adapter
```

Behavior:

- Stores caller name/email in `CallState` when provided.
- Sets confirmed interest only when the tool input says interest was confirmed.
- Rejects unsafe writes before touching the database.
- Upserts prospects by normalized phone number.
- Creates idempotent interest rows for the resolved property or unit.
- Rolls back on exceptions and commits only successful captures.

## Knowledge Layer

The knowledge base uses local markdown files in `data/knowledge/` and deterministic lexical ranking in `KnowledgeBase`.

Why this choice:

- The assignment has a small corpus with one or two properties and a general FAQ.
- Local files are easy for reviewers to inspect.
- Lexical retrieval is deterministic and testable without external services.
- It avoids requiring embedding credentials or a hosted vector database.
- It is sufficient for policy/process questions where terms are predictable.

The tradeoff is semantic recall. A vector index would handle more paraphrases and a larger corpus better. The current boundary makes that a future replacement behind `KnowledgeBase.search` rather than a change to the agent or worker tool contracts.

## Property Resolution Logic

Property resolution is deterministic and conservative:

- Direct property-name matches produce high-confidence property targets.
- Exact unit-number matches produce high-confidence unit targets.
- A single lexical candidate can be used with moderate confidence.
- Multiple candidates are marked ambiguous.
- Ambiguous targets are stored only as provisional state and are not eligible for capture.
- The prompt instructs the assistant to ask short clarification questions when property identity is unclear.

The confidence values are code-level inputs to the safety gate, not just prose guidance for the LLM.

## Prospect Capture Logic

Prospect capture is a two-step conversational flow:

1. Resolve the property or unit from database-backed tools.
2. Capture interest only after the caller provides or confirms required details.

The required details are:

- caller phone number from SIP metadata or equivalent call context
- caller name
- current property or unit target
- target confidence at or above the threshold
- ambiguity resolved
- explicit caller interest or follow-up confirmation

Phone numbers are normalized in `ProspectsRepository.upsert_by_phone`, so repeat calls from the same number update the existing prospect instead of creating duplicates. Interest rows are unique per prospect and property or unit, so repeated capture for the same target is idempotent.

## Confidence And Safety Check

The safety gate is implemented in `evaluate_capture_safety`, not just in the prompt. A write is rejected when any of these conditions apply:

- `missing_phone`
- `missing_name`
- `missing_target`
- `low_confidence`
- `ambiguous_property`
- `needs_confirmation`

The default confidence threshold is `0.8`. Rejections return structured reasons to the LLM so the assistant can ask for the specific missing detail instead of guessing or writing a bad record.

This is the main safety boundary in the project: even if the LLM calls the write tool too early, the code blocks the database write.

## Grounding Rules

The assistant is expected to:

- use SQLite tools for exact property and unit facts
- use knowledge retrieval for policies, leasing process, FAQ answers, and richer descriptions
- keep responses short enough for voice
- say when the available data does not contain an answer
- ask a clarification question when the property or unit is ambiguous
- avoid prospect capture unless the safety gate allows it

## Key Decisions And Tradeoffs

- **LiveKit SIP over direct Twilio media streaming:** LiveKit reduces custom audio transport and turn-taking code. Direct Twilio streaming would give lower-level control but would increase assignment risk.
- **Separate worker and API:** The worker owns realtime calls; FastAPI stays easy to run and credential-free for `/health`.
- **SQLite over hosted database:** SQLite keeps the project runnable from a clean checkout and is enough for seeded demo data. A production deployment would move to Postgres and migrations.
- **Local markdown retrieval over vector search:** Deterministic local retrieval is transparent and credential-free. Vector retrieval is deferred until corpus size or paraphrase coverage requires it.
- **Code-enforced safety over prompt-only safety:** The LLM can guide the conversation, but database writes must be rejected by deterministic code when required details are missing.
- **Provider adapters over direct SDK coupling:** The worker can swap Deepgram/OpenRouter/OpenAI configuration without spreading SDK details through the codebase.
- **No admin UI:** Reviewer verification is handled by `/prospects` and SQLite queries because the brief does not ask for a CRM.

## What I Would Do With More Time

- Capture and include a short real-call recording or video as final demo evidence.
- Add an automated evaluation harness over `docs/project/TEST_CONVERSATION_SCENARIOS.md`, including an LLM-as-judge rubric for grounding, tool choice, safety, and voice concision.
- Persist call transcripts and tool events for post-call review and regression analysis.
- Add explicit `source` and `status` columns to `prospect_interests` to match the brief's sample schema more closely.
- Add migrations, likely Alembic, if the schema starts evolving beyond the assignment.
- Add a browser-based LiveKit voice fallback for reviewers without telephony credentials.
- Move knowledge retrieval to embeddings or hybrid lexical/vector retrieval if the corpus grows.
- Tune voice latency and barge-in settings from real call recordings rather than unit-test assumptions.

## Architectural Influences

The architecture follows the project guidance in `AGENTS.md`:

- keep the voice agent, grounded property answers, and safe prospect capture central
- use a `src/` package layout
- keep API and worker as separate runtime entrypoints
- avoid requiring provider or telephony credentials for linting, tests, or `/health`
- make milestone-scoped decisions through ADRs in `docs/project/adr/`
