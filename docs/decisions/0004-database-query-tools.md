# 0004 Database Query Tools

Issue: M04 needs model-safe database read tools for property search, unit listing, and unit fact lookup before the assistant can answer property questions from grounded evidence. M03 created SQLite persistence and repository methods, but those repository methods are application internals rather than a stable tool contract for orchestration. This issue is being addressed now because M04 is the next incomplete milestone, and M06 property resolution plus M07 grounded answer orchestration depend on structured, bounded database evidence.

Decision: Add a small read-only tool layer over the existing property repository. M04 will define typed request and response dataclasses for three tools: `search_properties`, `list_units`, and `get_unit_facts`. Tool responses will include structured records, normalized evidence items, result counts, and match confidence metadata suitable for later property resolution and answer orchestration. Tools must call repository methods only and must never expose arbitrary SQL, accept raw SQL, or perform prospect writes. M04 will keep the tool implementation deterministic and framework-neutral; integration with an agent SDK, model prompt/tool schemas, KB retrieval, property-resolution state, write tools, and voice transport remain out of scope.

Status: Accepted

Group: agent-tools

Assumptions: The accepted M03 SQLite repository is sufficient as the backing data source for M04. Later milestones may expose these tools to an LLM or agent framework, but M04 can first define an internal, typed Python contract that is easy to test. The seeded dataset is intentionally small, so simple lexical matching and explicit result limits are enough for this milestone. Confidence metadata should be conservative and explainable rather than pretending to be a final semantic resolver. Tool evidence should support later grounded responses without forcing a final natural-language answer format now.

Constraints: M04 must not add write behavior, prospect capture, confirmation gates, KB retrieval, model calls, voice code, or agent orchestration. It must not let callers provide SQL fragments, table names, arbitrary filters, or unbounded result sizes. Result limits must be enforced in the tool layer even if repository methods return more rows. Tool outputs must be structured enough for tests and later orchestration to inspect source records and grounding evidence. Tests must run without credentials or network calls and must use deterministic seed data.

Positions: Position 1: Build a framework-neutral typed Python tool layer over `PropertyRepository`. This keeps M04 focused, reuses M03 persistence, is straightforward to unit test, and leaves model or SDK binding decisions for the orchestration milestone.

Position 2: Expose raw SQLite queries or a generic SQL tool. This is flexible, but it is unsafe for model use, hard to constrain, and unnecessary for the small set of leasing facts required by the assignment.

Position 3: Bind the tools directly to a specific agent framework now. This could speed up later model integration, but it would prematurely couple M04 to an orchestration decision that belongs in M07 and makes deterministic tests more brittle.

Position 4: Extend repository methods directly and skip a separate tool layer. This avoids extra classes, but it mixes storage concerns with model-facing evidence shape, confidence metadata, and result-limit behavior.

Position 5: Implement a semantic search or embedding-backed database search. This may improve fuzzy matching later, but it adds indexing and provider complexity before the MVP has KB retrieval or agent orchestration.

Argument: Position 1 is recommended because it creates the narrow model-facing contract the project needs without overcommitting to a model, SDK, or retrieval strategy. A dedicated tool layer can translate repository records into evidence-rich responses, enforce limits, classify no-match and ambiguous-match states, and keep the storage API clean. The tool contract also gives M06 and M07 stable inputs for property resolution and answer composition.

The main trade-off is that simple lexical matching will not fully solve natural-language ambiguity. That limitation is acceptable because M04 is not the property-resolution milestone. The right behavior for M04 is to return candidates and confidence metadata conservatively, not to guess a single answer when evidence is weak. M06 can then combine those candidates with conversation state and clarification policy.

Tool responses should prefer structured facts over prose. For example, unit facts should include the unit ID, property ID, label, bedrooms, bathrooms, rent, square footage, availability date, view, parking, pet policy, amenities, and status, plus evidence items with source labels such as `database.units.monthly_rent`. This lets M07 produce natural answers while preserving inspectable grounding. No-match responses should be explicit and should not invent fallback facts.

Implications: M04 implementation should add a database tools module, typed DTOs, and focused tests for property search, exact matches, ambiguous matches, no matches, unit listing, result limits, and unit fact evidence. The architecture documentation should describe the new tool boundary as the model-safe read path over persistence. Requirements traceability should record that M04 adds concrete evidence for FR-02, FR-10, NFR-03, and NFR-06, while not yet satisfying full conversation grounding or property resolution. Operational impact is low because no new external services are introduced. Security impact is positive because the design explicitly excludes arbitrary SQL and writes.

Related decisions: ADR 0001 established Python/FastAPI, `uv`, `src/` layout, `pytest`, `ruff`, and `mypy`. ADR 0002 established provider and repository protocols plus deterministic fakes. ADR 0003 established SQLite persistence, seed data, and concrete property repository methods. Later ADRs for property resolution, grounded answer orchestration, safe prospect capture, and observability will depend on or refine the evidence and confidence shapes introduced here.

Related requirements: FR-02 requires factual property and unit answers from the database. FR-05 requires graceful handling of unknown questions, which starts with explicit no-match tool results. FR-10 requires sensible agent tools for database reads, knowledge-base retrieval, and database writes. NFR-03 requires clean, maintainable structure. NFR-06 requires automated verification for core behavior. EVAL-02 evaluates database grounding, and EVAL-03 evaluates agent tool design and safety.

Related artifacts: `brief.md`, `docs/project/IMPLEMENTATION_PLAN.md`, `docs/project/STATUS.md`, `docs/project/ARCHITECTURE.md`, `docs/project/REQUIREMENTS.md`, `docs/decisions/README.md`, `src/leasing_voice_assistant/interfaces.py`, `src/leasing_voice_assistant/persistence.py`, future database tool modules, and future database tool tests.

Related principles: Keep model-facing tools narrow, deterministic, and inspectable. Return structured evidence before natural-language prose. Enforce result limits and no-match behavior in the tool boundary. Do not expose raw SQL to an agent. Do not add writes until the safe prospect capture milestone. Prefer conservative confidence metadata over premature property-resolution guesses.

Notes: Validation approach after acceptance: run `UV_CACHE_DIR=.uv-cache uv run pytest`, `UV_CACHE_DIR=.uv-cache uv run ruff check .`, `UV_CACHE_DIR=.uv-cache uv run ruff format --check .`, and `UV_CACHE_DIR=.uv-cache uv run mypy`. Add focused tests that initialize a temporary SQLite database, create database tools over `SQLitePropertyRepository`, verify seeded property search, enforce result limits, distinguish exact/ambiguous/no-match responses, list units for a property, return complete unit fact evidence, and confirm no prospect writes or raw SQL interfaces were introduced. Review the diff for scope creep into KB retrieval, agent orchestration, voice, or prospect capture.
