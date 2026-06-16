# 0002 Configuration And Provider Interfaces

Decision record template by Jeff Tyree and Art Akerman

This is the architecture decision description template published in "Architecture Decisions: Demystifying Architecture" by Jeff Tyree and Art Akerman, Capital One Financial.

Issue: M02 needs to introduce configuration loading and narrow provider interfaces before database, knowledge-base, model, speech, or voice work begins. The project will depend on external providers for model generation, speech-to-text, text-to-speech, and possibly telephony, but tests must not require real credentials or live provider calls. This issue is being addressed now because M01 has established the Python/FastAPI scaffold and quality commands, and all later behavior milestones need stable configuration and testable boundaries.

Decision: Add a small configuration module using Pydantic Settings (`pydantic-settings`) and define Python `Protocol`-based interfaces for provider and storage boundaries. M02 will include settings for environment selection and optional provider credentials, but missing external credentials must not break local tests. Provider interfaces will cover `ModelProvider`, `SpeechToTextProvider`, `TextToSpeechProvider`, `VoiceSessionProvider`, `PropertyRepository`, `ProspectRepository`, and `KnowledgeRetriever`. M02 will also add deterministic fake implementations for tests. Real provider adapters, persistence schema, agent prompts, database tools, voice transport, and business logic remain out of scope.

Status: Accepted

Group: integration

Assumptions: The accepted M01 stack remains Python/FastAPI with `uv`, `src/` layout, `pytest`, `ruff`, and `mypy`. The MVP will need provider credentials later, but early tests and local development should run without them. Pydantic is already installed through FastAPI, and Pydantic Settings is a small, conventional addition for environment-based configuration. Python protocols are sufficient for structural typing and avoid adding a dependency injection framework. Fake providers are the right default for deterministic unit tests at architectural boundaries. Exact real provider selections can remain open for later ADRs.

Constraints: M02 must not select or implement real model, STT, TTS, telephony, database, or knowledge-retrieval providers. It must not introduce live network calls in tests. It must not require secrets for `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .`, or `uv run mypy`. Configuration must avoid committing credentials and should read local secrets from environment variables or ignored `.env` files only. Interfaces must stay small enough to support the assignment MVP rather than a generic framework.

Positions: Position 1: Use Pydantic Settings plus Python `Protocol` interfaces and deterministic fakes. This aligns with the existing FastAPI/Pydantic stack, validates configuration explicitly, keeps provider contracts typed, and avoids live external dependencies in tests.

Position 2: Use plain `os.environ` reads and abstract base classes. This avoids adding a dependency, but it spreads validation logic and creates more boilerplate for interface definitions.

Position 3: Use a dependency injection container and provider-specific clients now. This may scale for a larger service, but it adds framework overhead and prematurely commits to providers before the relevant ADRs.

Position 4: Delay interfaces until each feature milestone. This minimizes M02 work, but it would force later milestones to invent boundary shapes independently and make deterministic testing harder.

Argument: Position 1 is recommended because it gives the project a clean boundary layer with low implementation cost. Pydantic Settings provides explicit environment variable parsing and clear validation errors while fitting the existing dependency stack. Protocols keep the contracts lightweight and easy to fake without inheritance-heavy design. Deterministic fakes support the assignment's requirement for maintainable, testable provider integrations without requiring credentials or external services in CI/local validation. The trade-off is that M02 introduces interface names before all downstream details are known; that risk is acceptable because the protocols can stay minimal and be extended by later ADRs when concrete behavior is implemented.

Implications: M02 implementation should add a settings module, a provider interface module, fake provider classes, and focused tests for configuration success/failure and fake behavior. Security impact is positive because required and optional credentials become explicit and local secrets remain outside committed files. Testing impact is positive because later milestones can mock model, speech, voice, repository, and KB boundaries consistently. Operational impact is limited to documenting environment variables and `.env` usage. Latency impact is none for M02 because no real provider calls or voice pipeline are implemented. Future milestones should conform to these protocols or explicitly supersede ADR 0002 before changing boundary shapes.

Related decisions: ADR 0001 established Python/FastAPI, `uv`, `src/` layout, `pytest`, `ruff`, and `mypy`. Later ADRs for persistence, knowledge retrieval, agent orchestration, safe prospect capture, voice pipeline, browser or telephony integration, evaluation, and observability will depend on or refine these boundaries.

Related requirements: FR-10 requires sensible agent tools for database reads, knowledge-base retrieval, and database writes. NFR-03 requires clean, maintainable, structured code. NFR-06 requires automated verification for core behavior. NFR-07 requires provider credentials and secrets not be committed. NFR-08 requires provider integrations to be testable without real calls. DEL-05 requires documentation of credentials required for providers.

Related artifacts: `docs/project/IMPLEMENTATION_PLAN.md`, `docs/project/STATUS.md`, `docs/project/ARCHITECTURE.md`, `docs/project/REQUIREMENTS.md`, `docs/decisions/README.md`, `README.md`, future `src/leasing_voice_assistant/config.py`, future provider interface modules, and future fake provider tests.

Related principles: Keep external integrations behind testable interfaces. Prefer deterministic tests and local fakes at architectural boundaries. Do not require external credentials for automated validation. Do not commit secrets or real personal data. Keep interfaces narrow and driven by assignment requirements. Do not implement later milestone behavior while creating foundation boundaries.

Notes: Validation approach after acceptance: run `uv sync --all-groups` if dependencies change, then `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .`, and `uv run mypy`. Add tests showing settings load without real credentials, secret-like values are not hard-coded, missing required local-only settings fail clearly when introduced, and fake providers return deterministic results. Review the diff for scope creep, accidental provider calls, committed secrets, weak error handling, and documentation drift.
