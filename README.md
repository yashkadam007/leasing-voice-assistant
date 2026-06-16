# Leasing Voice Assistant

Focused MVP voice AI assistant for property leasing. The assistant will answer grounded property questions and safely register prospect interest after confirmation.

## Status

M03 establishes the repository scaffold, quality tooling, configuration loading, provider interfaces, deterministic fakes, local SQLite persistence, and synthetic seed property data. Database tools, knowledge-base retrieval, agent behavior, prospect capture gating, and voice integration are planned later milestones.

## Requirements

- Python 3.12 or newer
- `uv`

## Setup

```bash
uv sync --all-groups
```

M03 does not require provider credentials for setup, tests, linting, formatting, type checks, or local database initialization. Configuration accepts optional local provider credentials through `LVA_`-prefixed environment variables.

## Local Database

Initialize or refresh the local SQLite database with migrations and synthetic seed data:

```bash
PYTHONPATH=src uv run python -c "from leasing_voice_assistant.persistence import initialize_database; initialize_database().close()"
```

The generated database lives under `data/runtime/`, which is ignored by Git. Committed seed data lives in `data/seeds/properties.json`.

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
