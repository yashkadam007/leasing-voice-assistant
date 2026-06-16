# Leasing Voice Assistant

Focused MVP voice AI assistant for property leasing. The assistant will answer grounded property questions and safely register prospect interest after confirmation.

## Status

M01 establishes the repository scaffold and quality tooling only. Database, knowledge-base retrieval, agent behavior, prospect capture, and voice integration are planned later milestones.

## Requirements

- Python 3.12 or newer
- `uv`

## Setup

```bash
uv sync --all-groups
```

M01 does not require provider credentials. Future milestones will document model, speech, telephony, and storage configuration as those integrations are added.

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

Use `.env` for local secrets when future milestones introduce credentials. `.env` files are ignored; `.env.example` is committed as a placeholder.
