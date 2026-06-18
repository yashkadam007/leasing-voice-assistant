# ADR 0001: Project Foundation and Runtime Shape

## Issue

Milestone 1 needs a project foundation that can support a real-time leasing voice assistant without adding application scope that is outside the assignment. The repository currently contains planning documents only, so the first implementation pass must establish the Python project shape, runtime boundaries, configuration model, quality checks, and minimal runnable entrypoints for later milestones.

The foundation must support two runtime concerns:

- a small FastAPI control plane for health checks and reviewer-facing setup or verification helpers
- a LiveKit agent worker for the real-time voice conversation

The key decision is how to structure the repository and runtime configuration so later database, knowledge, provider, and SIP milestones can be added cleanly.

## Decision

Use a single Python repository managed by `uv`, with the application package under `src/`. The package will contain both the FastAPI control plane and the LiveKit worker entrypoint. The API and worker will be separate runtime entrypoints but will share configuration, domain services, provider adapters, repositories, and tests.

The initial package layout will be:

```text
src/
  leasing_voice_assistant/
    __init__.py
    api/
      __init__.py
      main.py
    worker/
      __init__.py
      main.py
    core/
      __init__.py
      config.py
tests/
  test_health.py
  test_worker_import.py
```

Use these project conventions:

- `uv` manages the Python version, dependencies, lockfile, and local development environment.
- The project uses a `src/` layout so tests exercise the installed package instead of importing directly from the repository root.
- Ruff provides formatting and linting.
- Pytest provides the test runner.
- Pydantic settings provide typed environment configuration.
- `.env.example` documents required and optional environment variables.
- FastAPI exposes an initial `/health` endpoint.
- The LiveKit worker entrypoint is importable and intentionally minimal until SIP and provider milestones add behavior.
- `docs/project/STATUS.md` remains the milestone progress tracker.

The first implementation should add command-line scripts or documented commands for:

```text
uv sync --all-groups
uv run ruff format .
uv run ruff check .
uv run pytest
uv run uvicorn leasing_voice_assistant.api.main:app --reload
```

## Status

Accepted and implemented.

## Group

Milestone 1: Project Foundation and Runtime Shape.

## Assumptions

- Python is the primary backend language for this assignment.
- The repository should be runnable from a clean checkout by following the README.
- LiveKit Agents, LiveKit SIP/Twilio, SQLite, Deepgram, and OpenRouter remain the planned downstream technologies.
- The FastAPI app is a control plane and reviewer helper, not a full CRM or admin UI.
- The worker and API need shared code but do not need to run in the same process.
- Local development should not require production telephony credentials just to run linting, tests, or the health endpoint.

## Constraints

- The assignment evaluates a working voice agent, grounded answers, safe prospect capture, maintainability, and documentation.
- The project should stay small enough for a take-home review.
- External credentials may be unavailable during early development, so imports and basic tests must work without contacting providers.
- SQLite will be the authoritative application database in later milestones.
- The codebase must have explicit linting, formatting, and test commands.
- Project documentation should make key tradeoffs visible through milestone ADRs.

## Positions

### Position 1: Single Python repository with `src/` package layout and separate API and worker entrypoints

The API and worker live in one package and share common modules. They are launched independently by command, process manager, or developer terminal.

## Argument

Position 1 is the project foundation. It keeps the repository simple for reviewers while preserving a clear runtime boundary between the HTTP control plane and the real-time voice worker. Shared code can evolve naturally as later milestones add domain repositories, provider adapters, knowledge retrieval, and agent tools.

The meaningful choice inside this foundation is the package layout. A `src/` layout is preferred because it prevents tests and ad hoc scripts from accidentally importing modules directly from the repository root. That makes local test behavior closer to a clean installed package and catches packaging mistakes earlier.

The API and worker remain separate entrypoints because they have different runtime lifecycles. FastAPI handles short-lived HTTP requests for health and verification helpers, while the LiveKit worker is a long-running real-time process that will join rooms, manage audio, and coordinate provider clients. Keeping those entrypoints separate makes the later SIP pipeline easier to reason about and test.

`uv`, Ruff, Pytest, and Pydantic settings are pragmatic defaults for a modern Python project: they keep setup reproducible, code style consistent, tests easy to run, and environment access explicit.

## Implications

- Later milestones can add modules under the same package without changing the runtime shape.
- Shared configuration must be careful about optional provider credentials so local tests do not fail when telephony or model credentials are absent.
- The README must distinguish API startup from worker startup.
- Tests should cover importability and configuration behavior early, then expand around repositories and tools in later milestones.
- Deployment remains flexible: the API and worker can later be run as separate processes from the same image or checkout.
- The project will avoid early abstractions for deployment, process supervision, or plugin systems until they are needed.

## Related decisions

- Use LiveKit Agents as the voice agent framework.
- Use LiveKit SIP/Twilio for primary telephony.
- Use SQLite for application data.
- Use Deepgram for STT and TTS by default.
- Use OpenRouter for LLM by default.
- Use provider adapters for STT, TTS, and LLM.

## Related requirements

- Clean checkout setup must be documented.
- Linting and formatting must be available.
- Tests must be available.
- An empty FastAPI health endpoint must run.
- An empty worker entrypoint must import.
- Documentation must explain architecture, key decisions, and tradeoffs.

## Related artifacts

- `brief.md`
- `docs/project/IMPLEMENTATION_PLAN.md`
- `docs/project/ARCHITECTURE.md`
- `docs/project/STATUS.md`
- Future `pyproject.toml`
- Future `.env.example`
- Future `README.md`
- Future `src/leasing_voice_assistant/api/main.py`
- Future `src/leasing_voice_assistant/worker/main.py`
- Future `src/leasing_voice_assistant/core/config.py`

## Related principles

- Keep the voice agent as the center of the project.
- Prefer a small working system over broad unused infrastructure.
- Keep exact facts grounded in structured data and policy answers grounded in retrieval.
- Gate write actions behind explicit confidence and caller confirmation.
- Make local setup and reviewer verification straightforward.
- Keep runtime boundaries clear even inside a single repository.

## Notes

This ADR intentionally does not decide the SQLite schema, knowledge retrieval approach, provider adapter contracts, tool behavior, safety gate details, or SIP call flow. Those decisions belong to later milestone ADRs.
