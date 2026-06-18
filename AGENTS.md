# AGENTS.md

## Project

Leasing voice assistant with a FastAPI control plane and a separate LiveKit worker. Keep the voice agent, grounded property answers, and safe prospect capture as the center of the project.

## Commands

- Setup: `UV_CACHE_DIR=.uv-cache uv sync --all-groups`
- Format: `UV_CACHE_DIR=.uv-cache uv run ruff format .`
- Lint: `UV_CACHE_DIR=.uv-cache uv run ruff check .`
- Test: `UV_CACHE_DIR=.uv-cache uv run pytest`
- API: `UV_CACHE_DIR=.uv-cache uv run uvicorn leasing_voice_assistant.api.main:app --reload`

## Guidelines

- Use the `src/` package layout and keep imports package-based.
- Keep the API and worker as separate runtime entrypoints.
- Do not require provider or telephony credentials for linting, tests, or `/health`.
- Prefer small, milestone-scoped changes that follow the ADRs in `docs/project/adr/`.
- Update `docs/project/STATUS.md` when milestone state changes.
