# Codex Instructions

## Project Purpose

Build a focused MVP voice AI assistant for property leasing. A prospective renter should be able to speak with the assistant, ask grounded questions about a property, and safely register interest in the right property.

`brief.md` is the assignment source. Read it completely before making recommendations or code changes. Do not modify or rewrite `brief.md`.

## Source Of Truth

Use repository files, not chat history, as the durable project record:

- `brief.md`: immutable assignment specification.
- `docs/project/REQUIREMENTS.md`: requirements, scope, assumptions, and traceability.
- `docs/project/ARCHITECTURE.md`: MVP architecture and trade-offs.
- `docs/project/IMPLEMENTATION_PLAN.md`: ordered milestones and acceptance criteria.
- `docs/project/STATUS.md`: live status, next action, validation, and handoff.
- `docs/decisions/README.md`: ADR workflow and index.
- `docs/project/SESSION_RUNBOOK.md`: fresh-session recovery procedure.

Keep this file concise. Link to the detailed project documents instead of duplicating them.

## Mandatory Session Start Checklist

1. Read `brief.md`.
2. Read `AGENTS.md`.
3. Read `docs/project/REQUIREMENTS.md`.
4. Read `docs/project/ARCHITECTURE.md`.
5. Read `docs/project/IMPLEMENTATION_PLAN.md`.
6. Read `docs/project/STATUS.md`.
7. Read the ADR for the active milestone.
8. Inspect the current Git diff and relevant code.
9. Confirm the exact active milestone and its remaining acceptance criteria.

## Expected Repository Layout

The foundation scaffold is defined by ADR 0001.

- `brief.md`: assignment brief; do not edit.
- `AGENTS.md`: instructions for future Codex sessions.
- `docs/project/`: requirements, architecture, implementation plan, status, runbook.
- `docs/decisions/`: ADR workflow and accepted milestone decisions.
- `src/leasing_voice_assistant/`: application package.
- `tests/`: automated tests.
- `data/`: provisional seed data and knowledge-base source location, TBD by ADR.
- `README.md`: clean-checkout setup and current run/validation instructions.

## Implementation Workflow

Use this ADR-first milestone workflow:

1. Read the project source-of-truth files.
2. Select only the next incomplete milestone.
3. Set its status to `adr_pending`.
4. Ask the user to provide the ADR template and any milestone-specific constraints.
5. Create one ADR using that template.
6. Discuss alternatives, trade-offs, risks, and consequences.
7. Wait for explicit user acceptance of the ADR.
8. Mark the ADR `Accepted` and the milestone `ready`.
9. Implement only that milestone.
10. For development/debugging passes, keep edits focused on the requested code path unless the user explicitly asks for tests, docs, or milestone completion work.
11. For milestone completion passes, add/update tests, run validation commands, fix failures, review the diff, update project docs, and mark completion only when every acceptance criterion is evidenced.
12. Stop and provide a concise completion report.
13. Do not start the next milestone without a new user instruction.

Work on only one implementation milestone at a time. After completing a milestone, stop and wait for the user.

## Commands

- Setup: `uv sync --all-groups`
- Run application: `uv run uvicorn --app-dir src leasing_voice_assistant.app:create_app --factory --reload`
- Run tests: `uv run pytest`
- Lint: `uv run ruff check .`
- Format: `uv run ruff format --check .`
- Type check: `uv run mypy`
- Demo/browser voice loop: `TBD`
- Telephony run path: `TBD`

Replace `TBD` only when the corresponding tooling exists in the repository.

## Coding And Testing Expectations

- Optimize for a demonstrable MVP, not breadth.
- Keep provider integrations behind testable interfaces.
- Prefer deterministic tests for property resolution, tool selection, prospect capture, and write safety when the user asks for test coverage or milestone completion.
- Mock telephony, speech, and model providers in automated tests when tests are in scope.
- During live debugging, prioritize the smallest useful code or logging change and avoid adding tests unless requested.
- Use structured logging for call/session events once implementation begins.
- Do not fabricate commands, results, repository state, provider behavior, or validation.

## Security And Secrets

- Never commit credentials, API keys, phone numbers for real users, recordings containing sensitive data, or `.env` files with secrets.
- Document required credentials in `README.md` when tooling exists.
- Use environment variables or ignored local files for secrets.
- Treat telephony, model, speech, and tunneling credentials as explicit setup risks.
- Redact personal data from logs where practical.

## Scope Control

Explicit assignment requirements are tracked in `docs/project/REQUIREMENTS.md`. Recommendations and assumptions must be labeled as such.

Do not add a full CRM, authentication, admin UI, broad property catalog, unrelated analytics, or polished marketing UI. Optional enhancements must not displace the core voice, grounding, and safe capture requirements.

## Documentation Updates

Update project docs when the user asks for documentation work or when marking a milestone complete. During focused debugging/development, do not update docs unless the change itself is documentation-related or the user requests it.

## Milestone Definition Of Done

A milestone is done only when:

- Its required ADR is accepted, unless the plan explicitly says no ADR is required.
- The milestone scope is implemented and unrelated work is avoided.
- Automated tests are added or updated where applicable.
- Required validation commands are run and results are recorded.
- Known failures and risks are documented.
- `docs/project/STATUS.md` and relevant project docs are updated.
- The diff has been reviewed for secrets, scope creep, and regressions.

These definition-of-done requirements apply when explicitly completing a milestone, not to every focused debugging or development pass.

## Context Resumption

For a fresh session, follow `docs/project/SESSION_RUNBOOK.md`. Inspect existing code, current docs, and current status before editing. If documentation and code disagree, resolve the disagreement before implementation and record the outcome in `STATUS.md`.
