# Project Status

## Current State

- **Project state:** M04 database query tools is complete.
- **Date:** 2026-06-16
- **Current branch:** `main`.
- **Active milestone:** None; M04 is complete.
- **Latest completed milestone:** M04 Database query tools.
- **Next milestone:** M05 Knowledge-base ingestion and retrieval, pending ADR.
- **Latest ADR:** `docs/decisions/0004-database-query-tools.md` (Accepted).

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

## Work Currently In Progress

- None. Stop before M05 until the user asks to proceed with the next ADR-first milestone.

## Validation Commands Last Run

| Command | Result |
| --- | --- |
| `UV_CACHE_DIR=.uv-cache uv run pytest` | Passed; 27 passed, 1 FastAPI/Starlette `TestClient` deprecation warning. |
| `UV_CACHE_DIR=.uv-cache uv run ruff check .` | Passed; all checks passed. |
| `UV_CACHE_DIR=.uv-cache uv run ruff format --check .` | Passed; 12 files already formatted. |
| `UV_CACHE_DIR=.uv-cache uv run mypy` | Passed; no issues found in 12 source files. |
| `PYTHONPATH=src UV_CACHE_DIR=.uv-cache uv run python -c "from leasing_voice_assistant.persistence import initialize_database; initialize_database().close()"` | Passed; local SQLite database initialized from migrations and seed data. |

## Validation Results

- Automated validation passed: tests, lint, format check, and type check.
- Settings tests confirm local validation works without provider credentials.
- Settings tests confirm secret-like values are redacted from `repr(settings)`.
- Fake provider tests confirm deterministic model, STT, TTS, voice session, repository, prospect, and KB retriever behavior.
- Persistence tests confirm migrations create the schema, seed loading is idempotent, seeded property/unit facts are readable, prospect upsert matches normalized phone numbers, and repeated interest writes do not create duplicates.
- Database-tool tests confirm exact, ambiguous, and no-match property search behavior, empty queries do not return every property, unit list limits are enforced, and unit fact lookups return structured grounding evidence without fallback facts for missing units.
- No real provider calls, credentials, knowledge-base retrieval implementation, agent prompts, prospect capture gate, or voice pipeline were added.

## Known Failures

- `uv` defaults to `/Users/yash/.cache/uv`, which is outside the sandbox. Use `UV_CACHE_DIR=.uv-cache` in this environment.
- Direct Python snippets for this `src/` layout need `PYTHONPATH=src` unless the project is installed as an editable package.
- `pytest` reports one third-party deprecation warning from FastAPI/Starlette `TestClient` under the resolved dependency set. It does not fail validation.

## Blockers

- None for M04.

## Unresolved Decisions

- Whether to use Strands Agents SDK.
- Whether to prioritize Twilio or browser voice for the first working voice demo.
- Knowledge-base retrieval approach.
- Real model, STT, and TTS providers.
- Write confirmation and confidence policy.
- Demo recording path.

## Assumptions

- One or two properties are sufficient for MVP.
- Browser-based voice is acceptable if telephony credentials or trial setup block Twilio.
- M03 created synthetic seed data because no separate sample listing files were present in the repository.
- Clean-checkout reproducibility remains a final requirement and should be verified before submission.
- M02 provider protocols may be extended by later accepted ADRs when concrete behavior requires it.

## External Setup Still Required

- Model provider account and API key when a real model adapter is selected.
- STT provider account and API key unless using browser/local transcription.
- TTS provider account and API key unless using browser speech synthesis.
- Twilio account, number, and public tunnel/deployment if real telephony is chosen.
- Demo recording method.

## Files Changed In Current Milestone

- `README.md`
- `docs/decisions/0004-database-query-tools.md`
- `docs/decisions/README.md`
- `docs/project/ARCHITECTURE.md`
- `docs/project/IMPLEMENTATION_PLAN.md`
- `docs/project/REQUIREMENTS.md`
- `docs/project/STATUS.md`
- `src/leasing_voice_assistant/database_tools.py`
- `tests/test_database_tools.py`

## Files Changed In Latest Completed Milestone

- `README.md`
- `docs/decisions/0004-database-query-tools.md`
- `docs/decisions/README.md`
- `docs/project/ARCHITECTURE.md`
- `docs/project/IMPLEMENTATION_PLAN.md`
- `docs/project/REQUIREMENTS.md`
- `docs/project/STATUS.md`
- `src/leasing_voice_assistant/database_tools.py`
- `tests/test_database_tools.py`

## Exact Next Action

Start M05 only after user instruction: create an ADR for knowledge-base ingestion and retrieval, discuss trade-offs, wait for explicit acceptance, then implement only M05.

## Context Handoff Summary

Fresh sessions should start by reading `brief.md`, `AGENTS.md`, `docs/project/REQUIREMENTS.md`, `docs/project/ARCHITECTURE.md`, `docs/project/IMPLEMENTATION_PLAN.md`, `docs/project/STATUS.md`, `docs/decisions/README.md`, and accepted ADRs 0001 through 0004. M00, M01, M02, M03, and M04 are complete. M05 is the next milestone and must begin with an ADR.

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
