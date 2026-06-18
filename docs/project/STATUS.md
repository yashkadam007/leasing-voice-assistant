# Project Status

## Current Phase

Milestone 1 implemented. Milestone 2 implemented. Milestone 3 implemented. Milestone 4 implemented. Milestone 5 implemented. Milestone 6 ADR accepted.

## Milestone Status

| Milestone | Status | ADR | Implementation | Notes |
| --- | --- | --- | --- | --- |
| 1. Project Foundation and Runtime Shape | Complete | Accepted in `docs/project/adr/0001-project-foundation-and-runtime.md` | Implemented | `uv sync --all-groups`, Ruff, Pytest, FastAPI `/health`, and worker import verified. |
| 2. SQLite Domain Model, Repositories, and Seed Data | Complete | Accepted in `docs/project/adr/0002-sqlite-domain-model-and-seed-data.md` | Implemented | SQLAlchemy ORM models, SQLite initialization helpers, deterministic seed data, and repository tests are in place. |
| 3. Knowledge Base Retrieval | Complete | Accepted in `docs/project/adr/0003-knowledge-base-retrieval.md` | Implemented | Local markdown KB, deterministic ingestion, lexical retrieval, source metadata, and no-match tests are in place. |
| 4. Provider Adapter Layer | Complete | Accepted in `docs/project/adr/0004-provider-adapter-layer.md` | Implemented | Thin provider factory with Deepgram STT/TTS and OpenRouter LLM adapters. |
| 5. Leasing Agent Tools and Safety Gate | Complete | Accepted in `docs/project/adr/0005-leasing-agent-tools-and-safety-gate.md` | Implemented | Agent tool domain package, call state, deterministic safety gate, structured tool responses, and capture tests are in place. |
| 6. LiveKit SIP Call Pipeline | Pending | Accepted in `docs/project/adr/0006-livekit-sip-call-pipeline.md` | Not started | Primary call path is LiveKit SIP/Twilio. |
| 7. End-to-End Grounded Conversation and Prospect Capture | Pending | Not started | Not started | Core assignment journey. |
| 8. Evaluation, Documentation, and Demo Evidence | Pending | Not started | Not started | Includes call recording/video evidence. |

## Decisions Captured

| Decision | Status | Notes |
| --- | --- | --- |
| Use LiveKit Agents as the voice agent framework | Decided | Requested by project owner. |
| Use LiveKit SIP/Twilio for primary telephony | Decided | Browser fallback is optional, not primary. |
| Use SQLite for application data | Decided | Keeps clean-checkout setup simple. |
| Use Deepgram for STT and TTS by default | Decided | Provider adapter layer should keep this swappable. |
| Use OpenRouter for LLM by default | Decided | OpenAI-compatible adapter should make model experiments easy. |
| Use provider adapters for STT/TTS/LLM | Decided | Avoid coupling the worker to concrete providers. |
| Use local FTS/ranker for initial knowledge retrieval | Decided | Vector retrieval is deferred and can be added later behind the retrieval service boundary. |
| Enforce prospect capture safety inside the agent tool layer | Decided | Prompt guidance is not enough; `capture_prospect_interest` must reject unsafe writes in code. |

## Open Questions

- Should email capture be attempted during the call or left optional unless the caller offers it?

## Next Action

Begin Milestone 6 LiveKit SIP call pipeline implementation planning.
