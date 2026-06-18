# ADR 0002: SQLite Domain Model, Repositories, and Seed Data

## Issue

Milestone 2 needs the authoritative local data layer for the leasing voice assistant. Later milestones depend on exact, grounded facts about properties, units, prospects, and captured interest, so the project needs a small database model and repository boundary before adding knowledge retrieval, agent tools, and LiveKit call handling.

The data layer must support three core behaviors:

- answer exact property and unit questions from structured data
- identify and update prospects by caller phone number
- record caller interest without creating duplicate interest rows for the same prospect and property or unit

The key decision is how to model this data in SQLite and where to place the repository boundary so agent tools can stay simple, testable, and safe.

## Decision

Use SQLite as the authoritative application database with SQLAlchemy ORM models and a small repository layer under the shared package. Keep schema initialization simple for the take-home scope: create tables from SQLAlchemy metadata and load deterministic seed data through local setup helpers. Defer Alembic-style versioned migrations until schema history becomes necessary.

The initial package layout will add:

```text
src/
  leasing_voice_assistant/
    db/
      __init__.py
      base.py
      models.py
      session.py
      seed.py
    repositories/
      __init__.py
      properties.py
      prospects.py
tests/
  test_repositories.py
```

The schema will include:

- `properties`: leasing communities with name, address, city, state, phone, description, and leasing policy fields that are exact enough for tool answers
- `units`: rentable units tied to a property, with unit number, bedroom count, bathroom count, rent, square footage, availability date, status, floor, view, and unit-level notes
- `prospects`: caller records keyed by normalized phone number, with optional name and email
- `prospect_interests`: captured interest rows tied to a prospect and either a property or a unit

Repository methods should cover the Milestone 2 surface:

- property or unit search by caller-facing text
- exact unit detail lookup
- prospect upsert by phone number
- interest creation with duplicate protection

Seed data should include one or two realistic properties with multiple units and enough variation to test exact fact retrieval, ambiguity, and duplicate interest behavior.

## Status

Accepted for implementation.

## Group

Milestone 2: SQLite Domain Model, Repositories, and Seed Data.

## Assumptions

- SQLite remains the only required application database for the assignment.
- The database is small and local, with one or two seeded leasing properties.
- The voice agent will use structured database tools for exact property and unit facts.
- Broader policy or narrative retrieval belongs to the knowledge base milestone, not this milestone.
- Caller phone number from SIP metadata will be available later, but repository behavior can be tested with plain phone strings now.
- Local tests must not require provider, telephony, or LiveKit credentials.

## Constraints

- Keep the project runnable from a clean checkout.
- Keep the API and worker as separate runtime entrypoints.
- Do not turn the FastAPI control plane into a CRM or admin system.
- Avoid provider calls and external services in data-layer tests.
- Prospect capture must support later safety gates around confirmation, confidence, and ambiguity.
- Exact property facts must be represented as structured data instead of relying on LLM memory.

## Positions

### Position 1: SQLAlchemy ORM with metadata-based SQLite initialization and repository classes

Define SQLAlchemy models for the core tables, initialize SQLite from model metadata, seed deterministic local data, and expose application behavior through repository classes.

## Argument

Position 1 is the project decision. SQLAlchemy ORM gives the codebase typed, discoverable model objects without making the data layer large. It is a good fit for a small SQLite-backed application where tests need to create isolated databases and exercise repository behavior directly.

Metadata-based initialization is enough for this milestone because the schema is new, local, and small. It avoids adding migration ceremony before there is schema history to protect. The decision does not block future migrations: if later milestones need schema evolution, Alembic can be introduced with the ORM models as the source of truth.

Handwritten SQL would also work, but it would push more schema and row-mapping detail into repository code at the same time the project is still establishing its domain model. The ORM keeps the first implementation more readable for reviewers while preserving clear repository boundaries.

Repository classes are the application boundary. Agent tools and API helpers should ask repositories for property facts, prospect upserts, and interest creation instead of reaching into database sessions directly. This keeps later safety logic in the tool layer testable while keeping data invariants close to the database.

Prospects should dedupe by normalized phone number because phone number is the reliable identifier available from inbound telephony. Interests should be protected by uniqueness constraints so repeated confirmations during a call do not create duplicate rows.

## Implications

- Tests can create temporary SQLite databases and seed them without external services.
- Later tools can use repository return values directly for grounded answers.
- Phone normalization becomes part of prospect upsert behavior and must be deterministic.
- Interest creation must be idempotent for the same prospect and target.
- Seed data must be stable enough that tests can assert exact rents, bedrooms, availability, and unit details.
- The project can defer Alembic until schema versioning becomes valuable.
- The FastAPI control plane may expose setup or verification helpers later, but repositories remain the primary data access boundary.

## Related decisions

- Use SQLite for application data.
- Keep the API and worker as separate runtime entrypoints in one Python package.
- Use structured database tools for exact property and unit facts.
- Gate prospect writes later through confidence, confirmation, and ambiguity checks.
- Defer vector retrieval and broad knowledge search infrastructure to later milestones.

## Related requirements

- Database can be initialized locally.
- Seed data loads deterministically.
- Tests prove prospect upsert by phone.
- Tests prove duplicate interest behavior.
- Tests prove exact unit fact retrieval.
- Linting, formatting, tests, and `/health` must not require provider credentials.

## Related artifacts

- `brief.md`
- `docs/project/IMPLEMENTATION_PLAN.md`
- `docs/project/ARCHITECTURE.md`
- `docs/project/STATUS.md`
- `docs/project/adr/0001-project-foundation-and-runtime.md`
- Future `src/leasing_voice_assistant/db/models.py`
- Future `src/leasing_voice_assistant/db/session.py`
- Future `src/leasing_voice_assistant/db/seed.py`
- Future `src/leasing_voice_assistant/repositories/properties.py`
- Future `src/leasing_voice_assistant/repositories/prospects.py`
- Future repository tests

## Related principles

- Keep the voice agent as the center of the project.
- Ground exact facts in structured data.
- Keep write paths safe, explicit, and testable.
- Prefer small milestone-scoped changes over broad infrastructure.
- Make local setup and reviewer verification straightforward.
- Keep the FastAPI control plane minimal.

## Notes

This ADR intentionally does not decide the knowledge-base retrieval design, provider adapter contracts, LiveKit SIP call flow, final agent prompt, or the full prospect capture safety gate. It only establishes the local data foundation those later milestones will use.
