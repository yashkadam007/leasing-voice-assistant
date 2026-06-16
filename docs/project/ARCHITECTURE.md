# Architecture

## Summary

The MVP should be a small, testable voice-agent system centered on a leasing conversation. The assistant resolves the property, answers grounded questions from database and knowledge-base tools, and writes prospect interest only after confidence or explicit confirmation.

The brief suggests Python and FastAPI, Twilio for telephony, and Strands Agents SDK as a plus. Those are strong candidates, but final technology choices require ADRs before implementation.

## High-Level Components

```mermaid
flowchart LR
  Caller[Caller] --> Voice[Voice Adapter]
  Voice --> STT[Speech-to-Text Provider]
  STT --> Session[Conversation Session State]
  Session --> Agent[Agent Orchestrator]
  Agent --> DBRead[Database Read Tools]
  Agent --> KB[Knowledge Retriever]
  Agent --> Gate[Confidence and Confirmation Gate]
  Gate --> DBWrite[Prospect Write Tools]
  Agent --> TTS[Text-to-Speech Provider]
  TTS --> Voice
```

Implemented M02 boundaries:

- Settings live in `leasing_voice_assistant.config` and read `LVA_`-prefixed environment variables from the environment or local `.env`.
- Provider and storage contracts live in `leasing_voice_assistant.interfaces`.
- Deterministic local fakes live in `leasing_voice_assistant.fakes` for tests and future offline integration work.

Recommended MVP boundaries:

- Voice adapter: browser voice loop first if telephony is blocked; Twilio adapter later if credentials are available.
- STT/TTS/model providers: abstracted behind interfaces so tests can use deterministic fakes.
- Database: local relational store for properties, units, prospects, and interests.
- Knowledge base: separate document source with retrieval interface.
- Agent orchestration: central turn handler that chooses tools, tracks state, and produces grounded responses.

## Voice And Audio Pipeline

The voice path should support two implementations:

- Browser voice loop: microphone input, speech recognition or streamed audio to backend, spoken assistant responses, and an easy demo path.
- Twilio inbound call: inbound number, media streaming, backend websocket, STT/TTS, and response audio back to the call.

Browser voice is the recommended fallback if Twilio credentials, trial numbers, public tunneling, or latency constraints block real telephony. A real phone call remains ideal evidence if feasible.

## Conversation And Session State

Each conversation should maintain:

- Session or call ID.
- Caller phone number when available.
- Latest transcript turns.
- Resolved property/unit candidate and confidence.
- Caller name, phone, and optional email capture state.
- Prospect-write readiness state.
- Tool evidence used for the latest answer.
- Error and fallback state.

Session state should be serializable enough for tests and logs.

## Agent Orchestration

```mermaid
sequenceDiagram
  participant User
  participant Agent
  participant DB as Database Tools
  participant KB as Knowledge Retriever
  participant Gate as Write Gate

  User->>Agent: Asks question or expresses interest
  Agent->>DB: Search/read property facts when needed
  Agent->>KB: Retrieve leasing policy or descriptive content when needed
  Agent->>Agent: Resolve property and compose grounded response
  alt Prospect write candidate
    Agent->>Gate: Check property confidence and caller details
    Gate-->>Agent: Write allowed or ask for confirmation
    Agent->>DB: Upsert prospect and log interest if allowed
  end
  Agent-->>User: Natural answer or clarification
```

The agent should:

- Route factual property questions to database tools.
- Route policies, FAQs, lease terms, and richer descriptions to KB retrieval.
- Ask clarifying questions for ambiguous property references.
- Refuse or qualify answers when evidence is missing.
- Avoid writes until the property and caller details are clear.

## Database Read Tools

Database tools should expose narrow operations, not raw SQL to the model:

- Search properties by name, address, city, or descriptive hint.
- List matching units and availability.
- Read unit facts such as rent, bedrooms, view, parking, pet policy, and status.
- Return structured results with source labels for grounding.

## Knowledge-Base Retrieval

The KB should cover:

- Property factsheets.
- General leasing FAQ.
- Application process.
- Deposits, lease terms, pet rules, and other policies.

The initial retrieval approach is an ADR decision. A lightweight structured or keyword retrieval system may be enough for one or two properties. Embeddings are an optional upgrade if simple retrieval is unreliable.

## Property Resolution

Property resolution should combine:

- Explicit mentions from the caller.
- Database search results.
- Conversation history.
- Unit details such as bedrooms, view, rent, or availability.
- Confirmation when confidence is low.

Ambiguous references such as "the lake-facing one" or "that two bedroom" must not trigger writes until resolved.

## Prospect Identity Capture

The assistant should capture:

- Phone number, preferably from telephony metadata when available.
- Caller name.
- Optional email only if naturally offered or needed by implementation.

For browser voice, phone number may need to be spoken or manually supplied in the test harness. The assistant should repeat critical details before writing when transcription quality is uncertain.

## Confidence And Confirmation Gate

```mermaid
flowchart TD
  Candidate[Potential prospect write] --> Property{Property/unit resolved?}
  Property -- No --> ClarifyProperty[Ask property clarification]
  Property -- Yes --> Identity{Caller name and phone clear?}
  Identity -- No --> ClarifyIdentity[Ask for missing identity]
  Identity -- Yes --> Intent{Interest intent clear?}
  Intent -- No --> ClarifyIntent[Confirm caller wants interest recorded]
  Intent -- Yes --> Confidence{Transcript confidence acceptable?}
  Confidence -- No --> Repeat[Repeat and ask confirmation]
  Confidence -- Yes --> Write[Upsert prospect and log interest]
```

The gate should prevent:

- Writes from garbled speech.
- Registration before user intent is clear.
- Interest logged against an ambiguous property.
- Duplicate prospect records when phone number matches.
- Duplicate interest rows for the same prospect/unit unless the design explicitly allows history.

## Prospect Upsert And Interest Logging

The MVP should:

- Match existing prospects by phone number.
- Update name if appropriate and safe.
- Create a new prospect if no phone match exists.
- Log interest in the resolved unit or property.
- Make interest creation idempotent for repeated confirmations in the same conversation.

Exact uniqueness rules require an ADR during the safe prospect capture milestone.

## Observability And Structured Logging

Logs should include:

- Session ID.
- Turn number.
- Tool calls and result counts.
- Property-resolution confidence.
- Write-gate decisions.
- Latency timings for STT, model, TTS, and end-to-end turn response.
- Errors and fallback paths.

Logs must avoid secrets and unnecessary personal data.

## Testing Strategy

Use layered verification:

- Unit tests for property resolution, write gate, database tools, KB retrieval, and prospect upsert.
- Integration tests for text conversation scenarios.
- Fake STT/TTS/model providers for deterministic voice pipeline tests.
- Optional contract tests for real provider adapters without making live calls by default.
- End-to-end manual demo for browser voice or telephony.

## Evaluation Strategy

Create a small scenario set covering:

- Known property fact questions.
- KB policy questions.
- Ambiguous property references.
- Unknown questions.
- Caller identity capture.
- Duplicate prospect update.
- Garbled or low-confidence write attempts.
- Conflicting DB and KB facts.
- Stale availability.

An optional LLM-as-judge can score groundedness, helpfulness, and safety, but deterministic assertions should cover core writes and tool behavior first.

## Local Development Flow

Current M01 foundation commands:

1. Install dependencies with `uv sync --all-groups`.
2. Run automated tests with `uv run pytest`.
3. Run linting with `uv run ruff check .`.
4. Run formatting checks with `uv run ruff format --check .`.
5. Run type checks with `uv run mypy`.
6. Run the scaffold app with `uv run uvicorn --app-dir src leasing_voice_assistant.app:create_app --factory --reload`.

Later milestones will add database/KB setup, text conversation harness, browser voice or telephony adapter, and demo recording commands.

## Deployment And Demo Flow

The MVP should support a clean local demo. If Twilio is used, document:

- Required Twilio credentials.
- Phone number setup.
- Public webhook or tunnel.
- Media streaming configuration.
- How to place the call.

If browser voice is used, document:

- Browser permissions.
- Required model/speech credentials.
- How to start the backend and browser client.
- How to record the demo.

## Security And Privacy

- Do not commit credentials.
- Use environment variables or ignored local env files.
- Avoid logging full transcripts when not necessary.
- Redact phone numbers in shared logs where practical.
- Keep demo data synthetic.
- Document all external provider requirements.

## Failure Handling

The assistant should:

- Ask for clarification when property resolution is ambiguous.
- Say it does not know when neither DB nor KB has an answer.
- Prefer database facts over KB facts for current unit availability and rent.
- Surface conflicting facts conservatively.
- Retry or apologize briefly on provider failures.
- Avoid writes if transcription confidence is low.

## Provider Boundaries And Interfaces

Implemented M02 interfaces:

- `ModelProvider`: generate agent decisions/responses.
- `SpeechToTextProvider`: convert audio to transcript with confidence metadata when available.
- `TextToSpeechProvider`: synthesize response audio.
- `VoiceSessionProvider`: browser or telephony session transport.
- `PropertyRepository`: property/unit reads.
- `ProspectRepository`: prospect upsert and interest logging.
- `KnowledgeRetriever`: retrieve KB snippets.

These interfaces should stay small and practical; avoid building a generic framework.

## Important Trade-Offs

- Browser voice is easier to demo reliably; Twilio is closer to the ideal assignment evidence.
- SQLite is simple for clean-checkout local use; Postgres is closer to production but adds setup overhead.
- Lightweight KB retrieval is faster to build; embeddings may improve semantic matching but add provider and indexing complexity.
- Direct agent orchestration is easier to control; Strands may be a plus but adds dependency and learning risk.
- Strict write confirmation improves safety but can make the conversation feel less fluid.

## Alternatives Considered

- Twilio-first implementation: strong real-call evidence, but higher credential and networking risk.
- Browser-first implementation: lower setup risk, still acceptable under the brief if genuinely voice-to-voice.
- Postgres: robust, but unnecessary for one or two properties unless selected for familiarity.
- Embedding vector store: useful for larger KBs, but likely optional for the MVP.
- Full CRM/admin UI: explicitly out of scope.

## Decisions Requiring ADRs

- Application stack, dependency manager, and quality tooling.
- Database/storage choice and migration approach.
- Provider interface shapes and configuration strategy.
- Agent orchestration framework, including whether to use Strands Agents SDK.
- Knowledge-base retrieval approach.
- Property resolution confidence model.
- Prospect write gate and idempotency policy.
- Voice integration path: browser, Twilio, or both.
- Evaluation and observability approach.
