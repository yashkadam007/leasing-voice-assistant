# Project Status

## Current State

- **Project state:** M11 Twilio real-call transport implementation is complete with offline webhook and media-stream tests.
- **Date:** 2026-06-17
- **Current branch:** `main`.
- **Active milestone:** M12 Integration and end-to-end tests.
- **Latest completed milestone:** M11 Real call or browser voice integration.
- **Next milestone:** M12 Integration and end-to-end tests.
- **Latest ADR:** `docs/decisions/0011-real-call-twilio-integration.md` (Accepted).

## Completed Work

- M00 documentation foundation completed.
- M01 repository and quality-tooling foundation completed.
- ADR 0001 accepted for Python/FastAPI, `uv`, `src/` layout, `pytest`, `ruff`, and `mypy`.
- Added minimal Python/FastAPI scaffold under `src/leasing_voice_assistant/`.
- Added `/health` smoke endpoint and tests.
- ADR 0002 accepted for Pydantic Settings, protocol interfaces, and deterministic fakes.
- Added `pydantic-settings` to project dependencies and updated `uv.lock`.
- Added `leasing_voice_assistant.config.Settings` with `LVA_`-prefixed optional provider credential fields.
- Added provider and storage protocols in `leasing_voice_assistant.interfaces`.
- Added deterministic fake providers, repositories, and retriever in `leasing_voice_assistant.fakes`.
- Added tests for settings loading, credential redaction, validation failure, and fake behavior.
- Documented supported environment variables in `README.md` and `.env.example`.
- ADR 0003 accepted for SQLite persistence, SQL migrations, JSON seed data, and storage-level interest idempotency.
- Added SQLite migration for `properties`, `units`, `prospects`, and `prospect_interests`.
- Added synthetic seed data for Lakeview Flats and Cedar Park Townhomes.
- Added `leasing_voice_assistant.persistence` with migration setup, seed loading, concrete property and prospect repositories, and phone normalization.
- Extended `UnitRecord` with `sqft` and `available_from` for assignment-relevant unit facts.
- Added persistence tests for schema setup, idempotent seed loading, property/unit reads, phone-based prospect upsert, interest idempotency, and phone normalization.
- Documented local database initialization and ignored generated runtime database files.
- ADR 0004 accepted for framework-neutral, model-safe, read-only database query tools.
- Added `leasing_voice_assistant.database_tools` with typed request/response DTOs, structured evidence items, result limits, property match status, and conservative confidence metadata.
- Added database-tool tests for exact property search, ambiguous search, no-match search, empty-query handling, unit list limits, unit fact evidence, and missing unit behavior.
- ADR 0005 accepted for Markdown knowledge-base source and deterministic lexical retrieval.
- Added Markdown KB source documents for general leasing FAQ, Lakeview Flats, and Cedar Park Townhomes.
- Added `leasing_voice_assistant.knowledge_base` with Markdown ingestion, stable source-section IDs, bounded snippets, deterministic lexical scoring, and source metadata.
- Extended `KnowledgeSnippet` with optional title, section heading, and metadata fields while preserving the existing retriever protocol.
- Added knowledge-base tests for section ingestion, FAQ retrieval, property-description retrieval, source attribution, result and snippet limits, missing directories, and unknown-query behavior.
- ADR 0006 accepted for deterministic property-resolution state.
- Added `leasing_voice_assistant.property_resolution` with explicit resolution state, confidence, candidates, evidence, clarification reasons, and write-readiness classification.
- Added property-resolution tests for exact property references, context reuse, unit-hint narrowing, ambiguous property references, ambiguous unit references, no-match behavior, and replacing prior context with a new explicit property.
- ADR 0007 accepted for deterministic grounded answer orchestration.
- Added `leasing_voice_assistant.answer_orchestration` with text-turn request/result DTOs, database-vs-KB route classification, evidence exposure, fallback reasons, and grounded answer composition.
- Added answer-orchestration tests for DB rent answers, prior-context unit facts, KB application-process answers, unknown fallback behavior, missing-property clarification, ambiguous-property clarification, and DB precedence over KB guidance for structured pet-policy facts.
- ADR 0008 accepted for deterministic safe prospect capture.
- Added `leasing_voice_assistant.prospect_capture` with capture request/result DTOs, capture state, pending confirmation state, explicit write-gate outcomes, conservative identity extraction, interest-intent detection, low-confidence handling, and repository-backed writes.
- Updated `FakeProspectRepository` to normalize phone keys and keep interest writes idempotent for the same prospect, source, and target.
- Added prospect-capture tests for missing name, missing phone, ambiguous property, unclear intent, garbled/low-confidence transcript, explicit confirmation, unit-level interest writes, caller-phone upsert behavior, duplicate interest idempotency, and pending-confirmation invalidation.
- ADR 0009 accepted for a reusable in-memory text conversation session service plus thin CLI harness.
- Added `leasing_voice_assistant.conversation_session` with session state, transcript entries, turn requests/results, safe debug traces, answer-orchestration wiring, and prospect-capture wiring.
- Added `leasing_voice_assistant.text_harness` with a local CLI over the same session service, SQLite repositories, database tools, Markdown KB retriever, and prospect write gate.
- Added conversation-session tests for multi-turn answer context, complete prospect capture, confirmation-required writes, ambiguous-property write blocking, and real harness construction.
- ADR 0010 accepted for a transport-neutral, turn-based voice pipeline with Deepgram-capable STT, constrained model-backed spoken reply composition, and ElevenLabs-capable TTS.
- Added `leasing_voice_assistant.voice_pipeline` with audio input DTOs, voice turn request/result DTOs, transcript confidence propagation, bounded audio payload validation, timing metadata, degradation states, safe debug details, model grounding checks, and session-state preservation.
- Added optional standard-library HTTP provider adapters for OpenAI-compatible chat completions, Deepgram speech-to-text, and ElevenLabs text-to-speech, each failing clearly when credentials are missing.
- Extended settings with explicit fake/real provider selection, model names, base URL, STT model, TTS model, and TTS voice ID fields while preserving fake defaults.
- Updated `.env.example` and README configuration documentation for the new provider settings.
- Extended deterministic fake STT, model, and TTS providers with failure modes for offline coverage.
- Added voice-pipeline tests for a normal spoken property question, low-confidence prospect-interest capture with caller metadata, unsupported model fact rejection, STT fallback, model fallback, TTS degradation, and missing real-provider credentials.
- ADR 0011 accepted for Twilio-first real inbound-call integration over the existing M10 voice pipeline.
- Added `leasing_voice_assistant.twilio_transport` with TwiML generation, call/session state, Twilio media-stream event parsing, bounded audio buffering, stale sequence suppression, malformed payload handling, voice-pipeline invocation, and Twilio-compatible outbound audio frames.
- Added FastAPI Twilio routes: `POST /twilio/voice` and `WS /twilio/media`.
- Extended application construction with provider wiring for fake and real model/STT/TTS providers.
- Added `LVA_TELEPHONY_PUBLIC_BASE_URL`, `LVA_TELEPHONY_INBOUND_NUMBER`, and `LVA_TEXT_TO_SPEECH_OUTPUT_FORMAT` settings.
- Extended the ElevenLabs adapter with output-format support so `ulaw_8000` can be used for Twilio Media Streams playback.
- Added Twilio transport tests for TwiML shape, optional Twilio signature validation, caller metadata propagation, one media-stream turn through the voice pipeline, non-Twilio TTS fallback behavior, malformed/stale/empty media events, bounded buffers, and route-level Twilio webhook/websocket acceptance.
- Updated README, `.env.example`, architecture, requirements traceability, implementation plan, ADR index, and status for M11.

## Work Currently In Progress

- M12 has not started. Per the milestone workflow, do not begin M12 without a new user instruction and accepted ADR.

## Validation Commands Last Run

| Command | Result |
| --- | --- |
| `UV_CACHE_DIR=.uv-cache uv run pytest` | Passed; 77 passed, 1 FastAPI/Starlette `TestClient` deprecation warning. |
| `UV_CACHE_DIR=.uv-cache uv run ruff check .` | Passed; all checks passed. |
| `UV_CACHE_DIR=.uv-cache uv run ruff format --check .` | Passed; 29 files already formatted. |
| `UV_CACHE_DIR=.uv-cache uv run mypy` | Passed; no issues found in 29 source files. |
| `PYTHONPATH=src UV_CACHE_DIR=.uv-cache uv run python -c "from leasing_voice_assistant.persistence import initialize_database; initialize_database().close()"` | Passed; local SQLite database initialized from migrations and seed data. |
| Scripted text harness: `printf 'How much is the lake-facing unit at Lakeview Flats?\nMy name is Avery Lee, my phone is 555-123-4567, and I am interested in this.\nquit\n' \| PYTHONPATH=src UV_CACHE_DIR=.uv-cache uv run python -m leasing_voice_assistant.text_harness --debug` | Passed; returned a grounded unit rent answer, safe debug traces, and a unit-level prospect-interest write acknowledgement. |

## Validation Results

- Automated validation passed: tests, lint, format check, and type check.
- Settings tests confirm local validation works without provider credentials.
- Settings tests confirm secret-like values are redacted from `repr(settings)`.
- Fake provider tests confirm deterministic model, STT, TTS, voice session, repository, prospect, and KB retriever behavior.
- Persistence tests confirm migrations create the schema, seed loading is idempotent, seeded property/unit facts are readable, prospect upsert matches normalized phone numbers, and repeated interest writes do not create duplicates.
- Database-tool tests confirm exact, ambiguous, and no-match property search behavior, empty queries do not return every property, unit list limits are enforced, and unit fact lookups return structured grounding evidence without fallback facts for missing units.
- Knowledge-base tests confirm Markdown sections load with stable source metadata, FAQ and property-description queries retrieve relevant snippets, result and snippet limits are enforced, missing KB directories are safe, and unknown queries return no snippets.
- Property-resolution tests confirm exact references resolve property context, prior context supports follow-up references, unit hints narrow to a unique unit when evidence is sufficient, ambiguous property and unit references require clarification, no-match turns remain unresolved, and new explicit property references replace prior context.
- Answer-orchestration tests confirm rent answers use DB evidence, prior property context can answer a unit-specific follow-up, application-process answers come from KB snippets, unknown questions fall back without invention, missing property context asks for clarification, ambiguous property references ask for clarification, and structured pet-policy facts prefer DB evidence over KB guidance.
- Prospect-capture tests confirm missing identity blocks writes, ambiguous property context blocks writes, unclear intent requires confirmation, garbled or low-confidence transcript markers require confirmation, explicit confirmation writes pending interest, clear intent writes unit-level interest, caller-phone metadata supports existing-prospect upsert, duplicate interest writes remain idempotent, and changed target details invalidate pending confirmation.
- Conversation-session tests confirm text session state preserves multi-turn property context, transcript entries are recorded, debug traces expose answer and capture decisions safely, complete text prospect capture writes unit-level interest, confirmation-required text flows can be completed, ambiguous property writes remain blocked, and the CLI builder uses real local repositories.
- Voice-pipeline tests confirm fake audio input is transcribed, transcript confidence flows into the session write gate, model-backed voice text is synthesized when grounded, unsupported model facts are rejected in favor of the safe session reply, STT failure returns a caller-safe repeat prompt, model failure falls back to the safe session reply, and TTS failure returns assistant text with a degraded result.
- Provider-adapter tests confirm real OpenAI-compatible, Deepgram, and ElevenLabs adapters fail clearly without required credentials and that the ElevenLabs adapter accepts the Twilio-oriented `ulaw_8000` output format.
- Twilio transport tests confirm inbound webhook TwiML includes the media-stream websocket and caller metadata, optional Twilio signature validation rejects missing signatures and accepts valid signatures, media events buffer a bounded turn and call the voice pipeline, caller phone metadata is preserved, Twilio-compatible synthesized audio is returned as outbound media/mark events, non-Twilio TTS audio is not streamed incorrectly, malformed and stale frames are ignored, oversized buffers fail safely, and FastAPI Twilio routes accept mocked webhook/websocket traffic.
- Scripted CLI verification confirms a local text conversation can answer a grounded Lakeview Flats rent question and record Avery Lee's synthetic interest in unit 2B.
- No real provider calls, credentials, embeddings, vector database, browser UI, persistent session storage, CRM workflow, schema migration, committed audio recordings, or real personal data were added.

## Known Failures

- `uv` defaults to `/Users/yash/.cache/uv`, which is outside the sandbox. Use `UV_CACHE_DIR=.uv-cache` in this environment.
- Direct Python snippets for this `src/` layout need `PYTHONPATH=src` unless the project is installed as an editable package.
- `pytest` reports one third-party deprecation warning from FastAPI/Starlette `TestClient` under the resolved dependency set. It does not fail validation.

## Blockers

- None for M11.

## Unresolved Decisions

- Whether to use Strands Agents SDK.
- Demo recording path.

## Assumptions

- One or two properties are sufficient for MVP.
- Twilio real-call integration is the selected M11 direction; browser voice is a fallback only if a later ADR supersedes ADR 0011.
- M03 created synthetic seed data because no separate sample listing files were present in the repository.
- M05 created synthetic KB content because no separate raw knowledge-base files were present in the repository.
- Clean-checkout reproducibility remains a final requirement and should be verified before submission.
- M02 provider protocols may be extended by later accepted ADRs when concrete behavior requires it.
- M08 deterministic identity extraction is intentionally conservative; later model or voice layers may collect details more naturally while preserving the write-gate contract.
- M09 uses in-memory session state only; durable session storage remains out of scope unless later voice or observability milestones require it.
- M10 uses the model only as a constrained spoken-response composer after deterministic session decisions, not as a write gate or source of new property facts.

## External Setup Still Required

- Model provider account and API key when the OpenAI-compatible model adapter is selected.
- Deepgram account and API key when the Deepgram STT adapter is selected.
- ElevenLabs account, API key, and voice selection when the ElevenLabs TTS adapter is selected.
- Twilio account, number, and public tunnel/deployment for real telephony verification.
- Demo recording method.

## Files Changed In Current Milestone

- `docs/decisions/0011-real-call-twilio-integration.md`
- `docs/decisions/README.md`
- `docs/project/ARCHITECTURE.md`
- `docs/project/IMPLEMENTATION_PLAN.md`
- `docs/project/REQUIREMENTS.md`
- `docs/project/STATUS.md`
- `.env.example`
- `README.md`
- `src/leasing_voice_assistant/app.py`
- `src/leasing_voice_assistant/config.py`
- `src/leasing_voice_assistant/provider_adapters.py`
- `src/leasing_voice_assistant/twilio_transport.py`
- `tests/test_config.py`
- `tests/test_provider_adapters.py`
- `tests/test_twilio_transport.py`

## Files Changed In Previous Completed Milestone

- `README.md`
- `docs/decisions/0010-voice-pipeline.md`
- `docs/decisions/README.md`
- `docs/project/ARCHITECTURE.md`
- `docs/project/IMPLEMENTATION_PLAN.md`
- `docs/project/STATUS.md`
- `.env.example`
- `src/leasing_voice_assistant/config.py`
- `src/leasing_voice_assistant/fakes.py`
- `src/leasing_voice_assistant/interfaces.py`
- `src/leasing_voice_assistant/provider_adapters.py`
- `src/leasing_voice_assistant/voice_pipeline.py`
- `tests/test_config.py`
- `tests/test_fakes.py`
- `tests/test_provider_adapters.py`
- `tests/test_voice_pipeline.py`

## Exact Next Action

Create the M12 ADR for integration and end-to-end tests before implementing M12.

## Context Handoff Summary

Fresh sessions should start by reading `brief.md`, `AGENTS.md`, `docs/project/REQUIREMENTS.md`, `docs/project/ARCHITECTURE.md`, `docs/project/IMPLEMENTATION_PLAN.md`, `docs/project/STATUS.md`, `docs/decisions/README.md`, and accepted ADRs 0001 through 0011. M00 through M11 are complete. M12 is the next milestone and needs an ADR before implementation.

## Progress Log

### 2026-06-16

- Read the assignment brief.
- Inspected repository and confirmed it had no app scaffold yet.
- Created the documentation-first execution system requested by the user.
- Validated generated docs and marked M00 complete.

### 2026-06-16 M01 ADR Review

- Recovered project state from repository files.
- Confirmed M00 was the latest completed milestone and M01 was the next incomplete milestone.
- Confirmed M01 depended only on M00, which was complete.
- Confirmed no accepted ADR existed for M01.
- Created ADR 0001 from the supplied template and left it Proposed.
- Updated the implementation plan, status, and ADR index.
- Stopped before implementation pending explicit ADR acceptance.

### 2026-06-16 M01 Implementation

- User explicitly accepted ADR 0001.
- Marked ADR 0001 Accepted and implemented M01 only.
- Added the minimal scaffold, README, quality tooling, smoke tests, and health endpoint.
- Ran setup, tests, lint, format check, type check, and manual health verification.
- Marked M01 complete and set M02 as the next milestone.

### 2026-06-16 M02 ADR Review

- Confirmed M01 is the latest completed milestone and M02 is the next incomplete milestone.
- Confirmed M02 depends only on M01, which is complete.
- Confirmed no accepted ADR existed for M02.
- Created ADR 0002 from the supplied template and left it Proposed.
- Updated the implementation plan, status, and ADR index.
- Stopped before implementation pending explicit ADR acceptance.

### 2026-06-16 M02 Implementation

- User explicitly accepted ADR 0002.
- Marked ADR 0002 Accepted and implemented M02 only.
- Added Pydantic Settings configuration, provider/storage protocols, deterministic fakes, and tests.
- Updated README, `.env.example`, architecture, requirements traceability, implementation plan, ADR index, and status.
- Ran setup, tests, lint, format check, type check, and a secret-oriented diff scan.
- Marked M02 complete and set M03 as the next milestone.

### 2026-06-16 M03 ADR Review

- Confirmed M02 is the latest completed milestone and M03 is the next incomplete milestone.
- Confirmed M03 depends on M01 and M02, which are complete.
- Created ADR 0003 from the established Tyree/Akerman template and left it Proposed.
- Updated the implementation plan, status, and ADR index.
- Stopped before implementation pending explicit ADR acceptance.

### 2026-06-16 M03 Implementation

- User explicitly accepted ADR 0003.
- Marked ADR 0003 Accepted and implemented M03 only.
- Added SQLite schema migration, synthetic property/unit seed data, local database initialization, concrete repositories, and persistence tests.
- Updated README, architecture, requirements traceability, implementation plan, ADR index, and status.
- Ran tests, lint, format check, type check, and local database initialization.
- Marked M03 complete and set M04 as the next milestone.

### 2026-06-16 M04 ADR Review

- Confirmed M03 is the latest completed milestone and M04 is the next incomplete milestone.
- Confirmed M04 depends on M03, which is complete.
- Created ADR 0004 from the established Tyree/Akerman template and left it Proposed.
- Updated the implementation plan, status, and ADR index.
- Stopped before implementation pending explicit ADR acceptance.

### 2026-06-16 M04 Implementation

- User explicitly accepted ADR 0004.
- Marked ADR 0004 Accepted and implemented M04 only.
- Added read-only database query tools with typed DTOs, evidence items, result limits, exact/ambiguous/no-match property search status, and unit fact lookup.
- Added focused database-tool tests for property search, unit listing, unit fact evidence, and no fallback facts for missing units.
- Updated README, architecture, requirements traceability, implementation plan, ADR index, and status.
- Ran tests, lint, format check, and type check.
- Marked M04 complete and set M05 as the next milestone.

### 2026-06-16 M05 ADR Review

- Confirmed M04 is the latest completed milestone and M05 is the next incomplete milestone.
- Confirmed M05 depends on M01 and M02, which are complete.
- Created ADR 0005 from the established Tyree/Akerman template and left it Proposed.
- Updated the implementation plan, status, and ADR index.
- Stopped before implementation pending explicit ADR acceptance.

### 2026-06-16 M05 Implementation

- User explicitly accepted ADR 0005.
- Marked ADR 0005 Accepted and implemented M05 only.
- Added Markdown KB source documents for general leasing FAQ, Lakeview Flats, and Cedar Park Townhomes.
- Added deterministic Markdown ingestion and lexical retrieval with source IDs, titles, headings, bounded snippets, scores, and metadata.
- Added focused knowledge-base tests for retrieval, source attribution, limits, missing directories, and unknown queries.
- Updated README, architecture, requirements traceability, implementation plan, ADR index, and status.
- Ran tests, lint, format check, and type check.
- Marked M05 complete and set M06 as the next milestone.

### 2026-06-16 M06 ADR Review

- Confirmed M05 is the latest completed milestone and M06 is the next incomplete milestone.
- Confirmed M06 depends on M04, which is complete.
- Created ADR 0006 for property-resolution state and left it Proposed.
- Updated the implementation plan, status, and ADR index.
- Stopped before implementation pending explicit ADR acceptance.

### 2026-06-16 M06 Implementation

- User explicitly accepted ADR 0006.
- Marked ADR 0006 Accepted and implemented M06 only.
- Added deterministic property-resolution state and resolver service using existing database query tools.
- Added focused property-resolution tests for exact references, context reuse, unit-hint narrowing, ambiguous references, no-match behavior, and prior-context replacement.
- Updated README, architecture, requirements traceability, implementation plan, ADR index, and status.
- Ran tests, lint, format check, and type check.
- Marked M06 complete and set M07 as the next milestone.

### 2026-06-16 M07 ADR Review

- Confirmed M06 is the latest completed milestone and M07 is the next incomplete milestone.
- Confirmed M07 depends on M04, M05, and M06, which are complete.
- Created ADR 0007 for grounded answer orchestration and left it Proposed.
- Updated the implementation plan, status, and ADR index.
- Stopped before implementation pending explicit ADR acceptance.

### 2026-06-16 M07 Implementation

- User explicitly accepted ADR 0007.
- Marked ADR 0007 Accepted and implemented M07 only.
- Added deterministic grounded answer orchestration using existing database tools, KB retrieval, and property-resolution state.
- Added focused answer-orchestration tests for DB facts, KB answers, unknown fallback, clarification behavior, prior context, and DB precedence.
- Updated README, architecture, requirements traceability, implementation plan, ADR index, and status.
- Ran tests, lint, format check, and type check.
- Marked M07 complete and set M08 as the next milestone.

### 2026-06-16 M08 ADR Review

- Confirmed M07 is the latest completed milestone and M08 is the next incomplete milestone.
- Confirmed M08 depends on M03, M06, and M07, which are complete.
- Created ADR 0008 from the established Tyree/Akerman template and left it Proposed.
- Updated the implementation plan, status, and ADR index.
- Stopped before implementation pending explicit ADR acceptance.

### 2026-06-16 M08 Implementation

- User explicitly accepted ADR 0008.
- Marked ADR 0008 Accepted and implemented M08 only.
- Added deterministic prospect-capture state, write-gate outcomes, pending confirmation handling, conservative identity extraction, interest-intent detection, low-confidence handling, and repository-backed prospect writes.
- Added focused prospect-capture tests for blocked writes, confirmation-required writes, allowed writes, duplicate-safe writes, caller-phone upsert behavior, unit-level interest, and confirmation invalidation.
- Updated README, architecture, requirements traceability, implementation plan, ADR index, and status.
- Ran tests, lint, format check, and type check.
- Marked M08 complete and set M09 as the next milestone.

### 2026-06-16 M09 ADR Review

- Confirmed M08 is the latest completed milestone and M09 is the next incomplete milestone.
- Confirmed M09 depends on M07 and M08, which are complete.
- Created ADR 0009 for the text-based conversation harness and left it Proposed.
- Updated the implementation plan, status, and ADR index.
- Stopped before implementation pending explicit ADR acceptance.

### 2026-06-17 M09 Implementation

- User explicitly accepted ADR 0009.
- Marked ADR 0009 Accepted and implemented M09 only.
- Added reusable in-memory text conversation session state, transcript entries, turn results, and safe debug traces.
- Added local CLI text harness over the same session service, SQLite repositories, database tools, Markdown KB retriever, and prospect-capture write gate.
- Added focused conversation-session tests for multi-turn context, complete capture, confirmation, ambiguous-property blocking, and real harness construction.
- Updated README, architecture, requirements traceability, implementation plan, ADR index, and status.
- Ran tests, lint, format check, type check, and a scripted CLI text conversation.
- Marked M09 complete and set M10 as the next milestone.

### 2026-06-17 M10 ADR Review

- Confirmed M09 is the latest completed milestone and M10 is the next incomplete milestone.
- Confirmed M10 depends on M02 and M09, which are complete.
- Created ADR 0010 for the voice pipeline and left it Proposed.
- Revised ADR 0010 to include model-backed grounded replies plus Deepgram-capable STT and ElevenLabs-capable TTS while deferring Twilio transport to M11.

### 2026-06-17 M10 Implementation

- User explicitly accepted ADR 0010.
- Marked ADR 0010 Accepted and implemented M10 only.
- Added the transport-neutral voice pipeline, constrained model-backed spoken-response composition, timing/degradation metadata, optional provider adapters, provider settings, fake-provider failure modes, and focused tests.
- Ran tests, lint, format check, and type check.
- Marked M10 complete and set M11 as the next milestone.
- Updated the M11 plan to make streaming transport and practical barge-in/interruption handling explicit ADR topics and acceptance criteria.
- Updated the implementation plan, status, and ADR index.

### 2026-06-17 M11 Implementation

- User explicitly accepted ADR 0011.
- Marked ADR 0011 Accepted and implemented M11 only.
- Added Twilio TwiML generation, inbound voice webhook route with optional signature validation, Media Streams websocket route, bounded media buffering, stale/malformed frame handling, caller metadata propagation, and Twilio-compatible outbound media framing.
- Extended provider configuration for Twilio public callback URLs and ElevenLabs `ulaw_8000` output format.
- Added offline Twilio transport tests and updated README, `.env.example`, architecture, requirements traceability, implementation plan, ADR index, and status.
- Ran tests, lint, format check, and type check.
- Marked M11 complete and set M12 as the next milestone.
