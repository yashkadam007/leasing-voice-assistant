# Architecture Decision Records

## Purpose

Architecture Decision Records (ADRs) document meaningful technical choices, alternatives considered, trade-offs, risks, consequences, and links to implementation milestones. They keep project reasoning durable across Codex sessions.

## Naming Convention

Use:

```text
NNNN-short-decision-title.md
```

Examples:

- `0001-application-stack-and-tooling.md`
- `0002-provider-interfaces-and-configuration.md`

## Allowed Statuses

- `Proposed`
- `Accepted`
- `Superseded`
- `Rejected`

## Required Workflow

- The user will supply an ADR template when starting a milestone.
- Codex must use the supplied template rather than inventing a conflicting ADR format.
- Implementation cannot begin until the milestone ADR is written and explicitly accepted by the user.
- After explicit acceptance, mark the ADR `Accepted` and mark the milestone `ready`.
- If a decision changes later, create a new ADR that supersedes the old one rather than silently rewriting history.

## Linking Guidance

Each ADR should link to:

- The relevant milestone in `docs/project/IMPLEMENTATION_PLAN.md`.
- Relevant requirements in `docs/project/REQUIREMENTS.md`.
- Code or modules affected by the decision after implementation exists.
- Related ADRs, especially superseded or dependent decisions.

## ADR Index

| ADR | Title | Status | Milestone | Notes |
| --- | --- | --- | --- | --- |
| [0001](0001-repository-and-quality-tooling-foundation.md) | Repository And Quality Tooling Foundation | Accepted | M01 | Defines application scaffold, dependency manager, source layout, and quality commands. |
| [0002](0002-configuration-and-provider-interfaces.md) | Configuration And Provider Interfaces | Accepted | M02 | Defines settings approach, provider protocols, and deterministic fakes. |
| [0003](0003-property-prospect-persistence-and-seed-data.md) | Property Prospect Persistence And Seed Data | Accepted | M03 | Selects local SQLite persistence, migrations, seed data, and interest idempotency approach. |
