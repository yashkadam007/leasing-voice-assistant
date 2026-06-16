# Leasing Voice Assistant

Focused MVP voice AI assistant for property leasing. The assistant will answer grounded property questions and safely register prospect interest after confirmation.

## Status

M07 establishes the repository scaffold, quality tooling, configuration loading, provider interfaces, deterministic fakes, local SQLite persistence, synthetic seed property data, read-only database query tools, Markdown knowledge-base retrieval, deterministic property-resolution state, and grounded text-turn answer orchestration. Prospect capture gating and voice integration are planned later milestones.

## Requirements

- Python 3.12 or newer
- `uv`

## Setup

```bash
uv sync --all-groups
```

M07 does not require provider credentials for setup, tests, linting, formatting, type checks, local database initialization, knowledge-base retrieval, property resolution, or grounded text-turn orchestration. Configuration accepts optional local provider credentials through `LVA_`-prefixed environment variables.

## Local Database

Initialize or refresh the local SQLite database with migrations and synthetic seed data:

```bash
PYTHONPATH=src uv run python -c "from leasing_voice_assistant.persistence import initialize_database; initialize_database().close()"
```

The generated database lives under `data/runtime/`, which is ignored by Git. Committed seed data lives in `data/seeds/properties.json`.

## Knowledge Base

Committed knowledge-base source documents live in `data/kb/`. The M05 retriever reads Markdown files from that directory, splits them by headings, and returns source-attributed snippets for policy, FAQ, lease-term, and property-description questions.

## Property Resolution

`leasing_voice_assistant.property_resolution.PropertyResolver` tracks property and optional unit context across text turns using deterministic database-tool evidence. It returns explicit resolution state for resolved, probable, ambiguous, and unresolved cases, and marks ambiguous or unresolved context as not write-ready.

## Answer Orchestration

`leasing_voice_assistant.answer_orchestration.AnswerOrchestrator` handles deterministic text turns. It resolves property context, routes structured property/unit questions to database tools, routes policy and FAQ questions to the Markdown knowledge retriever, returns grounded answer text, and exposes route, evidence, fallback reason, and updated resolution state for tests and future logs.

## Run

```bash
uv run uvicorn --app-dir src leasing_voice_assistant.app:create_app --factory --reload
```

Then open `http://127.0.0.1:8000/health`.

## Quality Checks

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy
```

## Local Environment

Use `.env` for local secrets. `.env` files are ignored; `.env.example` documents supported variable names.

Supported variables:

- `LVA_ENVIRONMENT`: `local`, `test`, `development`, or `production`; defaults to `local`.
- `LVA_MODEL_API_KEY`: optional model provider credential for future adapters.
- `LVA_SPEECH_TO_TEXT_API_KEY`: optional STT provider credential for future adapters.
- `LVA_TEXT_TO_SPEECH_API_KEY`: optional TTS provider credential for future adapters.
- `LVA_TELEPHONY_ACCOUNT_SID`: optional telephony account identifier for future adapters.
- `LVA_TELEPHONY_AUTH_TOKEN`: optional telephony auth token for future adapters.
- `LVA_PROVIDER_TIMEOUT_SECONDS`: optional provider timeout; defaults to `10.0`.
