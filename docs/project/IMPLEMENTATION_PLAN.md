# Implementation Plan

## Progress Summary

| Milestone | Title | Status | ADR |
| --- | --- | --- | --- |
| M00 | Documentation foundation | completed | Not required |
| M01 | Repository and quality-tooling foundation | completed | [0001](../decisions/0001-repository-and-quality-tooling-foundation.md) |
| M02 | Configuration and provider interfaces | completed | [0002](../decisions/0002-configuration-and-provider-interfaces.md) |
| M03 | Property/prospect persistence and seed data | completed | [0003](../decisions/0003-property-prospect-persistence-and-seed-data.md) |
| M04 | Database query tools | completed | [0004](../decisions/0004-database-query-tools.md) |
| M05 | Knowledge-base ingestion and retrieval | completed | [0005](../decisions/0005-knowledge-base-ingestion-and-retrieval.md) |
| M06 | Property-resolution state | not_started | Required |
| M07 | Grounded answer orchestration | not_started | Required |
| M08 | Safe prospect capture | not_started | Required |
| M09 | Text-based conversation harness | not_started | Required |
| M10 | Voice pipeline | not_started | Required |
| M11 | Real call or browser voice integration | not_started | Required |
| M12 | Integration and end-to-end tests | not_started | Required |
| M13 | Evaluation scenarios | not_started | Required |
| M14 | Observability and failure handling | not_started | Required |
| M15 | Documentation, clean-checkout verification, and demo prep | not_started | Required |

**Next milestone:** M06 Property-resolution state, pending ADR.

## ADR-First Milestone Workflow

1. Read the project source-of-truth files.
2. Select only the next incomplete milestone.
3. Set its status to `adr_pending`.
4. Ask the user to provide the ADR template and any milestone-specific constraints.
5. Create one ADR using that template.
6. Discuss alternatives, trade-offs, risks, and consequences.
7. Wait for explicit user acceptance of the ADR.
8. Mark the ADR `Accepted` and the milestone `ready`.
9. Implement only that milestone.
10. Add or update tests.
11. Run all milestone validation commands.
12. Fix failures before declaring completion.
13. Review the diff for scope creep, security issues, and regressions.
14. Update the plan, status, architecture, requirements traceability, ADR index, and README where applicable.
15. Mark the milestone completed only when every acceptance criterion is evidenced.
16. Stop and provide a concise completion report.
17. Do not start the next milestone without a new user instruction.

## Milestones

### M00 Documentation Foundation

- **Status:** completed
- **Goal:** Create durable project instructions, requirements, architecture, implementation plan, ADR workflow, status, and session runbook.
- **Why now:** Future sessions need repository files as the source of truth before implementation begins.
- **Dependencies:** `brief.md`.
- **ADR required:** No.
- **Decisions to resolve:** None; this milestone documents pending decisions.
- **Scope:** Planning docs only.
- **Non-scope:** Production code, framework initialization, dependency installation, credentials, README implementation instructions.
- **Expected files:** `AGENTS.md`, `docs/project/*.md`, `docs/decisions/README.md`.
- **Implementation tasks:** Read brief, inspect repo, create docs, validate consistency.
- **Automated tests:** Not applicable.
- **Manual verification:** Inspect docs for contradictions, traceability, oversized milestones, vague acceptance criteria, and accidental implementation.
- **Validation commands:** `find . -maxdepth 3 -type f | sort`; `rg "FR-|NFR-|DEL-|Next milestone|ADR" AGENTS.md docs`.
- **Acceptance criteria:** Required docs exist; `brief.md` unchanged; status records actual repo state; no app code created.
- **Expected demo evidence:** None.
- **Rollback/recovery:** Remove generated docs only if restarting planning.
- **Documentation updates:** All created docs; mark M00 completed in `STATUS.md` after verification.
- **Likely risks:** Over-documenting, accidentally deciding architecture before ADRs, missing traceability.

### M01 Repository And Quality-Tooling Foundation

- **Status:** completed
- **Goal:** Establish minimal application scaffold, dependency manager, README shell, tests, linting, formatting, and type-checking commands.
- **Why now:** Every later milestone needs stable commands and project structure.
- **Dependencies:** M00.
- **ADR required:** Yes: [0001 Repository And Quality Tooling Foundation](../decisions/0001-repository-and-quality-tooling-foundation.md), Accepted.
- **Decisions to resolve:** Python/FastAPI confirmation, dependency manager, source layout, test framework, lint/format/type-check tools.
- **Scope:** Minimal runnable skeleton and quality tooling only.
- **Non-scope:** Database schema, agent behavior, voice pipeline, provider integrations.
- **Expected files:** `README.md`, app/source skeleton, test skeleton, project config, ignored local env example.
- **Implementation tasks:** Create scaffold, add health or smoke entrypoint, define commands, document setup.
- **Automated tests:** Smoke test for scaffold.
- **Manual verification:** Run setup/run/test/lint/format/type-check commands.
- **Validation commands:** `uv sync --all-groups`; `uv run pytest`; `uv run ruff check .`; `uv run ruff format --check .`; `uv run mypy`; `uv run uvicorn --app-dir src leasing_voice_assistant.app:create_app --factory --host 127.0.0.1 --port 8000`; `curl -s http://127.0.0.1:8000/health`.
- **Acceptance criteria:** Clean commands exist and pass; README reflects actual commands; no secrets; docs updated. Completed with evidence in `docs/project/STATUS.md`.
- **Expected demo evidence:** Terminal output from smoke commands.
- **Rollback/recovery:** Remove scaffold and config from this milestone if chosen stack changes before later work.
- **Documentation updates:** `AGENTS.md`, `STATUS.md`, `IMPLEMENTATION_PLAN.md`, README, ADR index.
- **Likely risks:** Dependency churn, choosing tools without ADR acceptance, framework overreach.

### M02 Configuration And Provider Interfaces

- **Status:** completed
- **Goal:** Add configuration loading and small provider interfaces for model, STT, TTS, voice transport, storage, and KB retrieval.
- **Why now:** Provider boundaries are needed before business logic and voice integration.
- **Dependencies:** M01.
- **ADR required:** Yes: [0002 Configuration And Provider Interfaces](../decisions/0002-configuration-and-provider-interfaces.md), Accepted.
- **Decisions to resolve:** Config library, env naming, fake provider strategy, interface boundaries.
- **Scope:** Config validation, provider protocols/interfaces, deterministic fake implementations for tests.
- **Non-scope:** Real provider adapters, database schema, agent prompts.
- **Expected files:** Config module, provider interface modules, fake provider tests.
- **Implementation tasks:** Define settings, validate missing secrets clearly, add fake providers, document env variables as TBD or optional.
- **Automated tests:** Config success/failure tests; fake provider tests.
- **Manual verification:** Run tests and inspect secret handling.
- **Validation commands:** `UV_CACHE_DIR=.uv-cache uv sync --all-groups`; `UV_CACHE_DIR=.uv-cache uv run pytest`; `UV_CACHE_DIR=.uv-cache uv run ruff check .`; `UV_CACHE_DIR=.uv-cache uv run ruff format --check .`; `UV_CACHE_DIR=.uv-cache uv run mypy`.
- **Acceptance criteria:** External dependencies are explicit; tests do not need real credentials; provider APIs are small. Completed with evidence in `docs/project/STATUS.md`.
- **Expected demo evidence:** Test output showing fake providers work: 11 tests passed.
- **Rollback/recovery:** Interfaces can be renamed before downstream milestones if ADR supersedes them.
- **Documentation updates:** Architecture, status, README credential section, ADR index.
- **Likely risks:** Over-abstracting or leaking provider-specific assumptions.

### M03 Property/Prospect Persistence And Seed Data

- **Status:** completed
- **Goal:** Implement local persistence for properties, units, prospects, and prospect interests with representative seed data.
- **Why now:** Grounded DB tools need real storage and seed data.
- **Dependencies:** M01, M02.
- **ADR required:** Yes: [0003 Property Prospect Persistence And Seed Data](../decisions/0003-property-prospect-persistence-and-seed-data.md), Accepted.
- **Decisions to resolve:** SQLite vs other store, migration approach, seed-data format, interest uniqueness.
- **Scope:** Schema, seed data for one or two properties, repository methods for persistence.
- **Non-scope:** Agent orchestration, KB retrieval, voice.
- **Expected files:** Database schema/migrations, seed data, repository tests.
- **Implementation tasks:** Create tables, load seeds, implement repository basics, ensure idempotent setup.
- **Automated tests:** Schema setup, seed load, prospect upsert, interest insert/idempotency basics.
- **Manual verification:** Inspect seeded data and run tests.
- **Validation commands:** `UV_CACHE_DIR=.uv-cache uv run pytest`; `UV_CACHE_DIR=.uv-cache uv run ruff check .`; `UV_CACHE_DIR=.uv-cache uv run ruff format --check .`; `UV_CACHE_DIR=.uv-cache uv run mypy`; `PYTHONPATH=src UV_CACHE_DIR=.uv-cache uv run python -c "from leasing_voice_assistant.persistence import initialize_database; initialize_database().close()"`.
- **Acceptance criteria:** Clean checkout can initialize data; sample properties support assignment questions; no real personal data. Completed with evidence in `docs/project/STATUS.md`.
- **Expected demo evidence:** Test output and local DB initialization command.
- **Rollback/recovery:** Reset local generated DB; keep migrations deterministic.
- **Documentation updates:** Requirements traceability, architecture, status, README setup.
- **Likely risks:** Missing provided data, stale availability, duplicate prospects.

### M04 Database Query Tools

- **Status:** completed
- **Goal:** Add model-safe database read tools for property search and unit facts.
- **Why now:** The agent needs grounded DB access before answering property questions.
- **Dependencies:** M03.
- **ADR required:** Yes: [0004 Database Query Tools](../decisions/0004-database-query-tools.md), Accepted.
- **Decisions to resolve:** Tool input/output shapes, result limits, confidence metadata.
- **Scope:** Read-only tools for property/unit search and fact lookup.
- **Non-scope:** KB retrieval, writes, voice.
- **Expected files:** Tool modules and tests.
- **Implementation tasks:** Implement property search, unit list, unit detail reads, structured evidence returns.
- **Automated tests:** Search, exact match, ambiguous match, no match, availability/fact reads.
- **Manual verification:** Run tool calls through tests or a small debug command if established.
- **Validation commands:** `UV_CACHE_DIR=.uv-cache uv run pytest`; `UV_CACHE_DIR=.uv-cache uv run ruff check .`; `UV_CACHE_DIR=.uv-cache uv run ruff format --check .`; `UV_CACHE_DIR=.uv-cache uv run mypy`.
- **Acceptance criteria:** Tools return structured evidence and never expose arbitrary SQL. Completed with evidence in `docs/project/STATUS.md`.
- **Expected demo evidence:** Test cases showing grounded fact retrieval: 27 tests passed, including 7 database-tool tests.
- **Rollback/recovery:** Preserve repository layer; adjust tool DTOs before agent integration if needed.
- **Documentation updates:** Architecture, requirements traceability, status.
- **Likely risks:** Ambiguous property names, stale availability, accidental hallucination from unstructured results.

### M05 Knowledge-Base Ingestion And Retrieval

- **Status:** completed
- **Goal:** Add KB source content and retrieval for policies, FAQs, lease terms, and property descriptions.
- **Why now:** The assistant needs non-database grounding before full answer orchestration.
- **Dependencies:** M01, M02.
- **ADR required:** Yes: [0005 Knowledge Base Ingestion And Retrieval](../decisions/0005-knowledge-base-ingestion-and-retrieval.md), Accepted.
- **Decisions to resolve:** Markdown/JSON source, keyword vs embeddings, citation/source format, indexing step.
- **Scope:** KB content, ingestion/indexing, retrieval interface, tests.
- **Non-scope:** Agent response generation, database writes, voice.
- **Expected files:** KB data files, retriever implementation, retrieval tests.
- **Implementation tasks:** Create/import KB docs, implement retrieval, return snippets with source IDs.
- **Automated tests:** Known FAQ retrieval, property policy retrieval, unknown query behavior.
- **Manual verification:** Query sample KB entries.
- **Validation commands:** `UV_CACHE_DIR=.uv-cache uv run pytest`; `UV_CACHE_DIR=.uv-cache uv run ruff check .`; `UV_CACHE_DIR=.uv-cache uv run ruff format --check .`; `UV_CACHE_DIR=.uv-cache uv run mypy`.
- **Acceptance criteria:** Retrieval gives relevant source snippets and supports graceful unknowns. Completed with evidence in `docs/project/STATUS.md`.
- **Expected demo evidence:** Test output for FAQ and policy queries: 33 tests passed, including 6 knowledge-base tests.
- **Rollback/recovery:** Rebuild generated index from source docs.
- **Documentation updates:** Architecture, status, README data notes.
- **Likely risks:** Conflicting DB/KB facts, overcomplex embeddings, missing source attribution.

### M06 Property-Resolution State

- **Status:** not_started
- **Goal:** Track and update the likely property/unit across conversation turns.
- **Why now:** Property resolution must be reliable before writes and grounded answer orchestration.
- **Dependencies:** M04.
- **ADR required:** Yes.
- **Decisions to resolve:** Confidence representation, ambiguity thresholds, clarification wording policy.
- **Scope:** Resolution state machine or service and tests.
- **Non-scope:** Prospect writes, full agent loop, voice.
- **Expected files:** Resolution module and tests.
- **Implementation tasks:** Resolve from explicit mentions and hints, preserve context, require clarification when ambiguous.
- **Automated tests:** Exact reference, pronoun/context reference, "lake-facing one", ambiguous two-property case, no match.
- **Manual verification:** Review scenario traces.
- **Validation commands:** TBD.
- **Acceptance criteria:** Ambiguous properties do not become write-ready; resolved context survives turns.
- **Expected demo evidence:** Test scenarios.
- **Rollback/recovery:** Tune thresholds without changing storage.
- **Documentation updates:** Architecture, requirements traceability, status.
- **Likely risks:** Ambiguous property references and false confidence.

### M07 Grounded Answer Orchestration

- **Status:** not_started
- **Goal:** Implement text-turn orchestration that chooses DB or KB tools and composes grounded answers.
- **Why now:** This creates the core agent behavior before capture and voice.
- **Dependencies:** M04, M05, M06.
- **ADR required:** Yes.
- **Decisions to resolve:** Agent framework, prompt/tool contract, fallback policy, DB-vs-KB precedence.
- **Scope:** Text input to grounded text response using tools.
- **Non-scope:** Prospect writes, audio, browser/telephony.
- **Expected files:** Agent/orchestrator module, prompts if applicable, tests.
- **Implementation tasks:** Route questions, call tools, cite/track evidence internally, handle unknowns.
- **Automated tests:** Rent from DB, pet policy from DB or KB as designed, FAQ from KB, unknown answer, conflicting fact handling.
- **Manual verification:** Run text turns through harness or tests.
- **Validation commands:** TBD.
- **Acceptance criteria:** Answers are grounded; unknowns are not invented; tool choice is inspectable.
- **Expected demo evidence:** Conversation transcript from text tests.
- **Rollback/recovery:** Prompt and routing can be tuned before voice.
- **Documentation updates:** Architecture, requirements traceability, status.
- **Likely risks:** Hallucination, nondeterministic model behavior, conflicting facts.

### M08 Safe Prospect Capture

- **Status:** not_started
- **Goal:** Safely capture caller identity and register/update prospect interest only after confirmation/confidence checks.
- **Why now:** Prospect writes are central and must be safe before exposing voice.
- **Dependencies:** M03, M06, M07.
- **ADR required:** Yes.
- **Decisions to resolve:** Confirmation policy, phone/name confidence rules, idempotent interest uniqueness, notes format.
- **Scope:** Capture state, write gate, prospect upsert, interest logging.
- **Non-scope:** Audio, Twilio caller ID integration beyond interface fields.
- **Expected files:** Capture/write-gate modules and tests.
- **Implementation tasks:** Collect name/phone, detect interest intent, gate writes, upsert prospect, log interest idempotently.
- **Automated tests:** Missing name, missing phone, ambiguous property, unclear intent, garbled transcript, duplicate phone, duplicate interest.
- **Manual verification:** Text scenarios for safe and blocked writes.
- **Validation commands:** TBD.
- **Acceptance criteria:** No write occurs without resolved property, clear identity, and clear intent or confirmation.
- **Expected demo evidence:** Test traces showing blocked and allowed writes.
- **Rollback/recovery:** Database can be reset from seed; writes should be idempotent.
- **Documentation updates:** Architecture, requirements traceability, status.
- **Likely risks:** Accidental registration, duplicate prospects, writes from transcription errors.

### M09 Text-Based Conversation Harness

- **Status:** not_started
- **Goal:** Provide a CLI or local API text harness for complete conversation testing without voice.
- **Why now:** Text harness makes agent behavior debuggable before audio complexity.
- **Dependencies:** M07, M08.
- **ADR required:** Yes.
- **Decisions to resolve:** CLI vs HTTP harness, transcript output format, debug trace visibility.
- **Scope:** Developer-facing text loop with session state and optional debug traces.
- **Non-scope:** Voice, telephony, polished UI.
- **Expected files:** Harness entrypoint and tests.
- **Implementation tasks:** Start session, accept text turns, show assistant replies, expose tool/write traces safely.
- **Automated tests:** Scripted conversations for answer and capture flows.
- **Manual verification:** Run sample conversation locally.
- **Validation commands:** TBD.
- **Acceptance criteria:** A full prospect-capture conversation can be completed in text with deterministic test coverage.
- **Expected demo evidence:** Saved transcript or command output.
- **Rollback/recovery:** Harness can remain dev-only.
- **Documentation updates:** README, status, implementation plan.
- **Likely risks:** Harness diverging from voice state flow.

### M10 Voice Pipeline

- **Status:** not_started
- **Goal:** Add audio pipeline using STT and TTS providers behind interfaces.
- **Why now:** Voice functionality should build on a tested text agent.
- **Dependencies:** M02, M09.
- **ADR required:** Yes.
- **Decisions to resolve:** STT/TTS providers, streaming vs turn-based audio, transcript confidence handling.
- **Scope:** Convert speech to text, call text agent, synthesize speech response, test with fakes.
- **Non-scope:** Twilio/browser transport polish, real call recording.
- **Expected files:** Audio pipeline modules and tests.
- **Implementation tasks:** Wire STT/TTS providers, preserve confidence metadata, add fake audio tests.
- **Automated tests:** Fake transcript to spoken response, low-confidence transcript blocks writes.
- **Manual verification:** Local audio path if available.
- **Validation commands:** TBD.
- **Acceptance criteria:** Voice pipeline can run without changing agent logic; fake providers cover CI.
- **Expected demo evidence:** Local spoken turn or test trace.
- **Rollback/recovery:** Provider adapters replaceable through interfaces.
- **Documentation updates:** Architecture, README, status.
- **Likely risks:** Latency, transcription errors, provider credentials.

### M11 Real Call Or Browser Voice Integration

- **Status:** not_started
- **Goal:** Expose the voice pipeline through a real inbound call or browser voice loop.
- **Why now:** This satisfies the assignment's core voice-to-voice requirement.
- **Dependencies:** M10.
- **ADR required:** Yes.
- **Decisions to resolve:** Twilio vs browser-first, public tunnel/deploy path, demo recording approach.
- **Scope:** One working voice transport connected to the voice pipeline.
- **Non-scope:** Admin UI, advanced call handling, barge-in unless explicitly chosen.
- **Expected files:** Browser client or Twilio adapter, transport tests where practical.
- **Implementation tasks:** Connect microphone/call audio, return spoken responses, document setup.
- **Automated tests:** Transport unit tests with mocked provider events.
- **Manual verification:** Complete real voice conversation.
- **Validation commands:** TBD.
- **Acceptance criteria:** User can talk to the assistant in voice and receive spoken answers; prospect capture path works.
- **Expected demo evidence:** Short recording or video.
- **Rollback/recovery:** Fall back from Twilio to browser voice if credentials/trial limits block progress.
- **Documentation updates:** README, architecture, status.
- **Likely risks:** Telephony credentials, trial limitations, browser permissions, latency, audio format issues.

### M12 Integration And End-To-End Tests

- **Status:** not_started
- **Goal:** Add integration tests covering complete answer and capture scenarios without real provider calls.
- **Why now:** Core behavior should be regression-tested before final demo polish.
- **Dependencies:** M09, M10, M11.
- **ADR required:** Yes.
- **Decisions to resolve:** Test fixture strategy, transcript format, fake model determinism.
- **Scope:** End-to-end text and fake-voice scenarios.
- **Non-scope:** Real Twilio calls in automated tests.
- **Expected files:** Integration test suite and fixtures.
- **Implementation tasks:** Script scenarios, assert tool usage, grounded answers, and safe writes.
- **Automated tests:** Happy path, unknown question, ambiguity, duplicate prospect, garbled write attempt.
- **Manual verification:** Review test transcripts.
- **Validation commands:** TBD.
- **Acceptance criteria:** E2E tests pass from a clean checkout without real credentials.
- **Expected demo evidence:** Test report and transcripts.
- **Rollback/recovery:** Keep fixtures synthetic and reset database between tests.
- **Documentation updates:** Requirements traceability, README, status.
- **Likely risks:** Nondeterministic model behavior and brittle assertions.

### M13 Evaluation Scenarios

- **Status:** not_started
- **Goal:** Define and optionally automate evaluation scenarios for long-term agent quality.
- **Why now:** Evaluation thinking is a differentiator and should be explicit before final submission.
- **Dependencies:** M12.
- **ADR required:** Yes.
- **Decisions to resolve:** Deterministic rubric vs LLM-as-judge, scoring dimensions, baseline storage.
- **Scope:** Scenario set and evaluation methodology; optional runnable evaluator if time allows.
- **Non-scope:** Large benchmark suite.
- **Expected files:** Eval docs, scenario fixtures, optional scorer tests.
- **Implementation tasks:** Create scenarios for grounding, safety, naturalness, latency, unknowns, and conflicts.
- **Automated tests:** Deterministic scorer tests if implemented.
- **Manual verification:** Run or review scenario outcomes.
- **Validation commands:** TBD.
- **Acceptance criteria:** Evaluation approach is clear and connected to assignment criteria.
- **Expected demo evidence:** Eval scenario table or output.
- **Rollback/recovery:** Keep evaluator optional if time is short.
- **Documentation updates:** Architecture, README, status.
- **Likely risks:** Overbuilding evaluation instead of finishing demo.

### M14 Observability And Failure Handling

- **Status:** not_started
- **Goal:** Add structured logs, latency tracking, and robust fallback behavior.
- **Why now:** Voice demos need diagnosability and graceful failure handling.
- **Dependencies:** M11, M12.
- **ADR required:** Yes.
- **Decisions to resolve:** Log format, PII redaction, latency metrics, error taxonomy.
- **Scope:** Structured logging and failure paths for provider errors, unknowns, conflicts, and low confidence.
- **Non-scope:** Full monitoring stack or dashboard.
- **Expected files:** Logging helpers, failure tests, docs.
- **Implementation tasks:** Log turn events, tool calls, timing, write gate decisions, and sanitized errors.
- **Automated tests:** Redaction, provider failure, no-answer fallback, low-confidence write block.
- **Manual verification:** Inspect logs from sample session.
- **Validation commands:** TBD.
- **Acceptance criteria:** Debugging a failed demo is practical without exposing secrets.
- **Expected demo evidence:** Sanitized sample log excerpt.
- **Rollback/recovery:** Logging can be disabled or reduced via config.
- **Documentation updates:** Architecture, README, status.
- **Likely risks:** Logging personal data or adding noisy logs.

### M15 Documentation, Clean-Checkout Verification, And Demo Recording Preparation

- **Status:** not_started
- **Goal:** Finalize docs, verify clean checkout, and prepare submission/demo evidence.
- **Why now:** The assignment is evaluated by repository usability, docs, and recording evidence.
- **Dependencies:** M01-M14 as completed or explicitly deferred.
- **ADR required:** Yes.
- **Decisions to resolve:** Demo path, recording storage, final deferred-scope notes.
- **Scope:** README, docs, clean-checkout verification, demo script, recording checklist.
- **Non-scope:** New features.
- **Expected files:** README updates, final docs, optional demo transcript/recording reference.
- **Implementation tasks:** Run clean setup, record demo, document credentials, list trade-offs and future work.
- **Automated tests:** Full established test suite.
- **Manual verification:** Fresh checkout setup and voice demo.
- **Validation commands:** TBD.
- **Acceptance criteria:** README works; tests pass; demo evidence exists; known limitations are documented.
- **Expected demo evidence:** Short recording or video of call/browser voice conversation.
- **Rollback/recovery:** If Twilio fails, document browser voice fallback and credential blocker clearly.
- **Documentation updates:** All project docs and status.
- **Likely risks:** Clean-checkout failure, missing credentials, unconvincing recording.
