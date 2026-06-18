# Leasing Voice Assistant

Realtime leasing voice assistant for inbound phone calls. The project currently contains the Milestone 1 foundation: a Python package with a small FastAPI control plane, an importable worker entrypoint, typed configuration, linting, formatting, and tests.

## Setup

```sh
uv sync --all-groups
```

Copy `.env.example` to `.env` for local configuration when needed. The current health endpoint and tests do not require provider credentials.

## Quality Checks

```sh
uv run ruff format .
uv run ruff check .
uv run pytest
```

## Run the API

```sh
uv run uvicorn leasing_voice_assistant.api.main:app --reload
```

The initial control-plane endpoint is:

```text
GET /health
```

## Run the Worker Entrypoint

```sh
uv run leasing-voice-worker
```

The worker is intentionally minimal until the LiveKit SIP and provider milestones add real room, audio, and tool behavior.
