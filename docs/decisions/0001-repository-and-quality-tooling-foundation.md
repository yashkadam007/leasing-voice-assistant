# 0001 Repository And Quality Tooling Foundation

Decision record template by Jeff Tyree and Art Akerman

This is the architecture decision description template published in "Architecture Decisions: Demystifying Architecture" by Jeff Tyree and Art Akerman, Capital One Financial.

Issue: M01 needs to establish the repository scaffold, dependency manager, README shell, smoke test, linting, formatting, and type-checking commands before any product behavior is implemented. Later milestones depend on stable commands, predictable source layout, and automated quality checks. This issue is being addressed now because M00 is complete, no application code exists, and the current repository has no executable validation beyond documentation checks.

Decision: Use a Python application scaffold with FastAPI as the eventual web/API framework, `uv` for dependency and command execution, `src/leasing_voice_assistant/` as the package layout, `tests/` for automated tests, `pytest` for tests, `ruff` for linting and formatting, and `mypy` for static type checking. M01 will create only a minimal health/smoke entrypoint and quality-tooling configuration. Runtime provider integrations, database schema, voice transport, agent behavior, and business logic remain out of scope for this milestone.

Status: Accepted

Group: foundation

Assumptions: Python and FastAPI align with the assignment's suggested backend stack and keep future voice, database, and provider integrations straightforward. The local environment can install Python dependencies through `uv`. A small `src/` layout is appropriate for a maintainable pull-request-style repository. The project does not currently need packaging for publication. No provider credentials should be required for M01. The assignment values clean code, linting, formatting, and reproducibility, so quality commands should exist before business behavior is added.

Constraints: M01 must not implement database schema, agent orchestration, knowledge retrieval, prospect capture, voice transport, or real provider adapters. Commands must be truthful and documented only after they exist. The scaffold must avoid secrets and must not require external credentials. The directory is currently not a Git repository, so Git status and diff checks cannot be relied on until repository initialization happens outside or after this decision. The implementation should be small enough to replace if a later accepted ADR supersedes part of the stack.

Positions: Position 1: Python, FastAPI, `uv`, `src/` layout, `pytest`, `ruff`, and `mypy`. This uses the assignment's suggested backend language and framework, gives fast setup and reproducible commands, and creates quality gates with little project-specific complexity.

Position 2: Python, FastAPI, Poetry, `src/` layout, `pytest`, `black`, `isort`, `flake8`, and `mypy`. This is familiar and robust, but it uses more separate tools and configuration for the same M01 outcome.

Position 3: Node.js or TypeScript backend with Express or a similar framework. This could support browser voice work well, but it diverges from the assignment's Python/FastAPI suggestion and may make later Python-oriented agent, audio, and data tooling less direct.

Position 4: Minimal scripts without a web framework yet. This minimizes dependencies now, but it risks churn when the API, browser voice loop, and provider integrations need an application boundary.

Argument: Position 1 is recommended because it establishes a pragmatic foundation with the least avoidable setup. FastAPI is suitable for later HTTP and websocket endpoints while not forcing M01 to expose real product behavior. `uv` provides a modern dependency workflow and fast command execution. `ruff` covers linting and formatting in one tool, reducing configuration and command sprawl. `mypy` creates an early type-checking habit for provider boundaries and business logic that will be added later. The positive trade-off is a compact, coherent baseline; the negative trade-off is that the repository commits to Python tooling before provider and voice ADRs are decided. That risk is acceptable because the assignment already suggests Python/FastAPI and future milestones can supersede the decision if necessary.

Implications: M01 implementation should create a minimal package, a health or smoke function/endpoint, a test proving the scaffold works, a `pyproject.toml` with dependencies and tool configuration, README setup and command instructions, and ignored local environment patterns. Security impact is low because no credentials are introduced; the README should document that secrets belong in environment variables or ignored local files. Testing impact is positive because later milestones will inherit a working `pytest` baseline. Operational impact is limited to local development commands. Latency impact is none for M01 because no voice or model path is implemented. Future milestones should reuse the established command names and source layout unless an ADR explicitly supersedes this decision.

Related decisions: This is the first ADR. It will influence later ADRs for configuration and provider interfaces, persistence, knowledge retrieval, agent orchestration, voice integration, evaluation, and observability.

Related requirements: NFR-03 requires clean, maintainable, structured code. NFR-04 requires linting and formatting. NFR-05 requires the project to run from a clean checkout by following the README. NFR-06 requires automated verification for core behavior. NFR-07 requires credentials and secrets not be committed. DEL-02 requires README setup and run instructions. DEL-03 requires planning and architecture documentation.

Related artifacts: `docs/project/IMPLEMENTATION_PLAN.md`, `docs/project/STATUS.md`, `docs/project/ARCHITECTURE.md`, `docs/project/REQUIREMENTS.md`, `docs/decisions/README.md`, future `README.md`, future `pyproject.toml`, future `src/leasing_voice_assistant/`, and future `tests/`.

Related principles: Keep the MVP focused on the voice assistant rather than infrastructure breadth. Prefer testable provider boundaries and deterministic validation. Do not fabricate commands, credentials, provider behavior, or test results. Avoid committing secrets or real personal data. Follow the ADR-first milestone workflow and implement only one milestone at a time.

Notes: Validation approach after acceptance: run the created setup and quality commands exactly as documented, expected to include tests, linting, formatting check, and type checking. Review the diff for scope creep, accidental secrets, unsafe writes, and documentation drift. M01 acceptance evidence should include passing command output and confirmation that no database, agent, knowledge-base, prospect-capture, or voice behavior was introduced.
