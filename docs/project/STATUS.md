# Project Status

## Current Phase

Milestones 1 through 6 are complete. The end-to-end grounded conversation path is implemented in code and documented through the architecture, runbook, and readiness notes. The demo call recording/video link is expected to be supplied in the submission email after the final smoke test against the configured telephony/provider accounts.

## Milestone Status

| Milestone | Status | ADR | Implementation | Notes |
| --- | --- | --- | --- | --- |
| 1. Project Foundation and Runtime Shape | Complete | Accepted in `docs/project/adr/0001-project-foundation-and-runtime.md` | Implemented | `uv`, Ruff, Pytest, FastAPI `/health`, settings, and worker import are in place. |
| 2. SQLite Domain Model, Repositories, and Seed Data | Complete | Accepted in `docs/project/adr/0002-sqlite-domain-model-and-seed-data.md` | Implemented | SQLAlchemy models, SQLite setup, deterministic seed data, property/unit reads, prospect upsert, and idempotent interest writes are in place. |
| 3. Knowledge Base Retrieval | Complete | Accepted in `docs/project/adr/0003-knowledge-base-retrieval.md` | Implemented | Local markdown KB, deterministic ingestion, lexical retrieval, source metadata, and no-match behavior are in place. |
| 4. Provider Adapter Layer | Complete | Accepted in `docs/project/adr/0004-provider-adapter-layer.md` | Implemented | Thin provider factory with Deepgram STT/TTS and OpenRouter/OpenAI LLM adapters. |
| 5. Leasing Agent Tools and Safety Gate | Complete | Accepted in `docs/project/adr/0005-leasing-agent-tools-and-safety-gate.md` | Implemented | `search_properties`, `get_unit_details`, `search_knowledge_base`, `capture_prospect_interest`, `CallState`, and deterministic capture safety are in place. |
| 6. LiveKit SIP Call Pipeline | Complete | Accepted in `docs/project/adr/0006-livekit-sip-call-pipeline.md` | Implemented | LiveKit worker, SIP metadata mapping, provider setup, tool adapters, prompt defaults, turn handling, realtime diagnostics, and SIP runbook are in place. |
| 7. End-to-End Grounded Conversation and Prospect Capture | Mostly complete | Covered by previous ADRs and architecture docs | Implemented locally; demo proof link will be sent in email | Expected grounded answers, clarification behavior, safe capture, and verification are documented through the README and architecture docs. |
| 8. Evaluation, Documentation, and Demo Evidence | In progress | Not planned as a separate ADR | Metrics capture implemented; baseline calls and demo link pending | Local JSONL turn/call measurement and summary reporting are implemented alongside the evaluation documentation. |

## Implemented Assignment Requirements

- Real voice-call runtime path through LiveKit SIP/Twilio and a separate LiveKit worker.
- Grounded property and unit answers from SQLite through repository-backed tools.
- Local knowledge retrieval for policy, process, FAQ, and property narrative answers.
- Prospect capture by phone number with idempotent interest creation.
- Code-enforced safety gate before any prospect-interest write.
- Read-only `GET /prospects` endpoint for reviewer verification.
- Credential-free linting, tests, imports, and `/health`.
- Planning and architecture markdown covering approach, audio pipeline, tools, database reads/writes, knowledge choice, property resolution, prospect capture, safety, tradeoffs, and future work.

## Remaining Submission Tasks

- Configure real LiveKit, Twilio, Deepgram, and OpenRouter/OpenAI credentials in the target environment.
- Run the worker and place a real inbound call using `docs/project/livekit-twilio-sip-runbook.md`.
- Add the short demo call/video link to the submission email.
- Verify the captured prospect through `GET /prospects` or the documented SQLite query.
- For outbound SIP testing, copy `sip-participant.example.json` to the ignored
  `sip-participant.json`, fill in account-specific values, and run
  `uv run leasing-voice-test-call --template sip-participant.json`.
- Run final quality checks before submission:

```sh
uv run ruff format --check .
uv run ruff check .
uv run pytest
```

## Decisions Captured

| Decision | Status | Notes |
| --- | --- | --- |
| Use LiveKit Agents as the voice agent framework | Decided | Keeps realtime session handling in the worker and aligns with the assignment preference. |
| Use LiveKit SIP/Twilio for primary telephony | Decided | Browser fallback is optional future work, not the primary path. |
| Keep FastAPI out of the audio path | Decided | API is limited to health and read-only verification. |
| Use SQLite for application data | Decided | Keeps clean-checkout setup simple and reviewable. |
| Use local markdown lexical retrieval for the KB | Decided | Deterministic, credential-free, and adequate for the small corpus. |
| Use Deepgram for STT and TTS by default | Decided | Built behind provider adapters. |
| Use OpenRouter for LLM by default, with OpenAI as an option | Decided | OpenAI-compatible integration keeps model experiments easy. |
| Enforce prospect capture safety inside the tool layer | Decided | Prompt instructions are not trusted as the only write guard. |
| Use phone number as prospect identity key | Decided | Matches the brief and keeps duplicate handling simple. |

## Known Limitations

- Final voice quality and latency still need to be validated from a recorded real call.
- Local latency metrics require representative real calls before they can establish a useful baseline.
- The knowledge layer is lexical, so broad paraphrase coverage is weaker than a vector or hybrid search approach.
- Call transcripts and tool events are logged but not persisted as first-class database records.
- There is no browser-based voice fallback for reviewers without telephony credentials.

## Open Questions

- Should email capture remain opportunistic, or should the assistant ask for it during every successful capture?

## Next Action

Capture at least 20 representative calls with the local metrics recorder, then run
`uv run leasing-voice-metrics` before starting the first latency improvement.
