# Leasing Voice Assistant Implementation Plan

## Planning Approach

The project was built as a sequence of small milestones, each captured by an ADR before or alongside implementation. The goal was to reduce risk in the order that matters for the assignment:

1. Establish a runnable Python project with separate API and worker entrypoints.
2. Build the local data model before the agent so property facts and prospect writes have a stable contract.
3. Add local knowledge retrieval for policy and FAQ answers.
4. Hide provider SDK details behind adapters.
5. Implement the agent tools and safety gate outside LiveKit so they can be tested deterministically.
6. Connect the tested tool layer to the LiveKit SIP voice worker.
7. Document the end-to-end verification path, tradeoffs, and external demo evidence plan.

This order keeps the voice agent central while avoiding a common failure mode: wiring telephony first and then discovering that grounding, state, and safe writes are hard to test.

## Milestone Summary

| Milestone | Result | Main Artifacts |
| --- | --- | --- |
| 1. Project Foundation and Runtime Shape | Complete | `pyproject.toml`, `src/` layout, FastAPI `/health`, worker import, Ruff, Pytest |
| 2. SQLite Domain Model, Repositories, and Seed Data | Complete | SQLAlchemy models, repositories, `leasing-voice-seed`, deterministic seeded properties |
| 3. Knowledge Base Retrieval | Complete | Markdown KB files, ingestion, lexical ranking, source metadata |
| 4. Provider Adapter Layer | Complete | Deepgram STT/TTS adapters, OpenRouter/OpenAI LLM adapters, provider factory |
| 5. Leasing Agent Tools and Safety Gate | Complete | `LeasingAgentTools`, `CallState`, `evaluate_capture_safety`, capture tests |
| 6. LiveKit SIP Call Pipeline | Complete | LiveKit worker entrypoint, SIP metadata parsing, tool adapters, runbook |
| 7. End-to-End Grounded Conversation and Prospect Capture | Implemented locally; real-call recording link will be sent in email | prompt, tool flow, `/prospects` verification |
| 8. Evaluation, Documentation, and Demo Evidence | Documentation updated; demo link handled in submission email | architecture docs, README, readiness review |

## Milestone 1: Project Foundation and Runtime Shape

Goal: create a clean Python project skeleton that can support a FastAPI control plane and separate LiveKit worker.

Implemented:

- `uv` Python project setup
- `src/leasing_voice_assistant/` package layout
- Ruff formatting and linting
- Pytest setup
- settings model for environment variables
- FastAPI `/health`
- importable worker entrypoint

Exit criteria met:

- project installs from a clean checkout
- lint and test commands exist
- `/health` runs without provider credentials
- worker module imports without provider credentials

ADR: `docs/project/adr/0001-project-foundation-and-runtime.md`

## Milestone 2: SQLite Domain Model, Repositories, and Seed Data

Goal: create the authoritative local data layer for properties, units, prospects, and interests.

Implemented:

- SQLAlchemy models for properties, units, prospects, and prospect interests
- SQLite initialization helpers
- deterministic seed data for Aurora Heights and Pine Garden Flats
- `PropertiesRepository` for property/unit reads
- `ProspectsRepository` for phone-based prospect upsert and idempotent interest creation
- repository tests for search, exact facts, upsert, and duplicate-interest behavior

Important decisions:

- SQLite is enough for the assignment and keeps setup local.
- Repositories keep database details out of prompts and worker orchestration.
- Interest rows target exactly one property or one unit.
- Prospect matching is by normalized phone number.

ADR: `docs/project/adr/0002-sqlite-domain-model-and-seed-data.md`

## Milestone 3: Knowledge Base Retrieval

Goal: answer policy, process, FAQ, and richer property-description questions from source-backed local content.

Implemented:

- markdown source files under `data/knowledge/`
- deterministic ingestion into chunks
- lexical retrieval with token normalization, synonym handling, phrase bonuses, and source metadata
- no-match behavior for unsupported questions
- retrieval tests for relevant and irrelevant queries

Important decisions:

- Local markdown keeps the knowledge layer reviewer-readable.
- Lexical retrieval is deterministic and credential-free.
- Vector retrieval is deferred because the corpus is small and the core evaluation is the voice-agent flow.

ADR: `docs/project/adr/0003-knowledge-base-retrieval.md`

## Milestone 4: Provider Adapter Layer

Goal: keep STT, TTS, and LLM provider construction out of the worker.

Implemented:

- provider interfaces
- Deepgram STT adapter
- Deepgram TTS adapter
- OpenRouter LLM adapter
- OpenAI LLM adapter
- provider factory selected by environment variables
- missing-credential errors that do not affect local tests or imports

Important decisions:

- Default STT/TTS provider is Deepgram.
- Default LLM provider is OpenRouter.
- OpenAI is available as a direct alternative.
- The abstraction is intentionally thin; it exists to isolate SDK construction, not to build a provider marketplace.

ADR: `docs/project/adr/0004-provider-adapter-layer.md`

## Milestone 5: Leasing Agent Tools and Safety Gate

Goal: implement the domain tool layer that the LLM can call during a voice conversation.

Implemented tools:

- `search_properties`
- `get_unit_details`
- `search_knowledge_base`
- `capture_prospect_interest`

Tool read/write behavior:

- Property and unit search reads through `PropertiesRepository`.
- Exact unit facts read from SQLite.
- Policy and FAQ answers read from `KnowledgeBase`.
- Prospect capture writes through `ProspectsRepository` only after `evaluate_capture_safety` allows it.

Safety gate requirements:

- caller phone number is present
- caller name is present
- a property or unit target is resolved
- confidence is at least `0.8`
- ambiguity is resolved
- caller explicitly confirmed interest

Rejected writes return structured reasons such as `missing_phone`, `missing_name`, `missing_target`, `low_confidence`, `ambiguous_property`, and `needs_confirmation`.

ADR: `docs/project/adr/0005-leasing-agent-tools-and-safety-gate.md`

## Milestone 6: LiveKit SIP Call Pipeline

Goal: connect the tested domain tool layer to a real voice worker.

Implemented:

- LiveKit worker entrypoint
- LiveKit credential validation when starting the real worker
- call metadata extraction into `CallState`
- provider client construction through `ProviderFactory`
- call-scoped tool wrappers for LiveKit function tools
- turn handling defaults with interruption support
- realtime session diagnostics for transcripts, assistant responses, tool execution, errors, and close events
- LiveKit/Twilio SIP runbook

Important decisions:

- LiveKit owns room, participant, audio, and realtime session lifecycle.
- FastAPI is not in the audio path.
- Missing phone metadata should block capture through the safety gate rather than crash the call.
- A hangup tool is deferred until there is a concrete LiveKit call-control action worth exposing.

ADR: `docs/project/adr/0006-livekit-sip-call-pipeline.md`

## Milestone 7: End-to-End Grounded Conversation and Prospect Capture

Goal: complete the assignment's core conversation loop.

Implemented:

- leasing-specific system prompt in `agent/prompts.py`
- property clarification flow through `search_properties` and `CallState`
- exact unit fact flow through `get_unit_details`
- FAQ/policy flow through `search_knowledge_base`
- safe capture flow through `capture_prospect_interest`
- read-only `/prospects` endpoint for verification

Expected successful journey:

1. Caller identifies Aurora Heights, Pine Garden Flats, or a unit.
2. Assistant resolves the target with a tool call.
3. Caller asks exact fact questions; assistant answers from SQLite.
4. Caller asks policy or FAQ questions; assistant answers from KB snippets.
5. Caller asks to be contacted or says they are interested.
6. Assistant asks for missing name or confirmation if needed.
7. Capture tool writes the prospect and interest only after the safety gate passes.
8. Reviewer verifies the row through `GET /prospects` or SQLite.

Remaining for submission email:

- add the demo call recording/video link
- use a short call script that covers a structured fact, a policy answer, an unknown question, and safe capture
- verify the final database row after the recorded call

## Milestone 8: Evaluation, Documentation, and Demo Evidence

Goal: make the repository reviewable as a take-home submission.

Implemented:

- README run instructions
- architecture documentation
- LiveKit/Twilio runbook
- readiness review document
- automated unit tests for repositories, retrieval, tools, provider factory, API, and worker helpers

Recommended final evaluation before submission:

- `uv run ruff format --check .`
- `uv run ruff check .`
- `uv run pytest`
- one real or simulated voice call covering property resolution, grounded answers, unknown handling, and safe capture
- verify `/prospects` contains the expected prospect and target

Future evaluation plan:

- Convert manual call scripts into a regression dataset.
- Add an LLM-as-judge rubric for factual grounding, correct tool use, unsupported-question handling, capture safety, and voice brevity.
- Persist transcripts and tool events so recorded failures can become regression tests.
- Track latency from final user transcript to first assistant audio for voice quality tuning.

## Key Tradeoffs

- **Local-first data over hosted infrastructure:** Faster reviewer setup and fewer credentials, at the cost of production-grade scaling.
- **Lexical KB retrieval over vector search:** Deterministic and transparent for a tiny corpus, weaker for broad paraphrases.
- **Code safety gate over prompt-only safety:** Slightly more implementation work, but it prevents premature or ambiguous database writes.
- **LiveKit SIP over direct Twilio media streaming:** Less custom audio plumbing, at the cost of depending on LiveKit's worker and SIP model.
- **Minimal API over CRM features:** Keeps scope aligned with the brief and avoids building unrelated admin workflows.

## What I Would Do With More Time

- Add transcript and tool-event persistence.
- Add Langfuse tracing for LLM calls, tool calls, retrieval results, capture rejections, and latency metrics.
- Add an LLM-as-judge regression harness around fixed call transcripts.
- Add a browser voice fallback for reviewers who cannot configure telephony.
- Move to Postgres and hybrid lexical/vector retrieval for a larger property portfolio.
- Tune endpointing, interruption behavior, and response length from real call metrics.
