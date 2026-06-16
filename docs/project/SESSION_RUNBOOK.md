# Session Runbook

## Resume Files To Read

Read these files in order at the start of every fresh Codex session:

1. `brief.md`
2. `AGENTS.md`
3. `docs/project/REQUIREMENTS.md`
4. `docs/project/ARCHITECTURE.md`
5. `docs/project/IMPLEMENTATION_PLAN.md`
6. `docs/project/STATUS.md`
7. The ADR for the active milestone, if one exists.

## Identify The Active Milestone

- Use `docs/project/STATUS.md` for the active milestone and exact next action.
- Cross-check `docs/project/IMPLEMENTATION_PLAN.md` for the milestone status, dependencies, scope, acceptance criteria, and validation commands.
- Work only on the next incomplete milestone.
- Do not automatically start the next milestone after completing the current one.

## Inspect Git State

Run:

```sh
git status --short --branch
```

If the command fails because the assignment directory is not a Git repository, record that in `docs/project/STATUS.md` and continue only with non-Git inspection.

If Git is available, inspect the current diff before editing:

```sh
git diff --stat
git diff
```

Do not revert user changes unless the user explicitly requests it.

## Determine Whether An ADR Is Accepted

Before implementation:

- Check the active milestone's `ADR required` field.
- Find the linked ADR in `docs/decisions/README.md`.
- Confirm the ADR status is `Accepted`.
- Confirm the user explicitly accepted the ADR in the current or recorded project context.

If no accepted ADR exists for an implementation milestone, set the milestone to `adr_pending`, ask the user for the ADR template and milestone-specific constraints, and stop before implementation.

## ADR-First Milestone Workflow

1. Read the project source-of-truth files.
2. Select only the next incomplete milestone.
3. Set its status to `adr_pending`.
4. Ask the user to provide the ADR template and any milestone-specific constraints.
5. Create one ADR using that template.
6. Discuss alternatives, trade-offs, risks, and consequences.
7. Wait for explicit user acceptance of the ADR.
8. Mark the ADR `Accepted` and the milestone `ready`.
9. Implement only that milestone.
10. Add or update tests.
11. Run all milestone validation commands.
12. Fix failures before declaring completion.
13. Review the diff for scope creep, security issues, and regressions.
14. Update the plan, status, architecture, requirements traceability, ADR index, and README where applicable.
15. Mark the milestone completed only when every acceptance criterion is evidenced.
16. Stop and provide a concise completion report.
17. Do not start the next milestone without a new user instruction.

## When Documentation And Code Disagree

Use this precedence order:

1. `brief.md`
2. Accepted ADRs
3. `docs/project/REQUIREMENTS.md`
4. `docs/project/ARCHITECTURE.md`
5. `docs/project/IMPLEMENTATION_PLAN.md`
6. `docs/project/STATUS.md`
7. Current code

If the code intentionally changed behavior, update the docs in the same milestone before stopping. If the disagreement affects scope or architecture, pause and resolve it with an ADR or user clarification before continuing.

## Run Existing Validation

- Use milestone-specific validation commands from `docs/project/IMPLEMENTATION_PLAN.md`.
- Use command definitions in `AGENTS.md` or `README.md` once established.
- Do not claim a command passed unless it was actually run.
- If commands are still `TBD`, record that no runnable validation exists yet.

## Update Status Before Stopping

Before ending a meaningful session, update `docs/project/STATUS.md` with:

- Active milestone.
- Completed work.
- Work in progress.
- Validation commands run and results.
- Known failures.
- Blockers and unresolved decisions.
- Files changed.
- Exact next action.
- Dated progress log entry.

## Minimal Resume Prompt

```text
Resume work on this repository. Follow AGENTS.md and docs/project/SESSION_RUNBOOK.md. Read brief.md and the project docs first, inspect current Git state and relevant code, identify the active milestone from docs/project/STATUS.md, and continue only that milestone. Do not start a new milestone without explicit instruction.
```
