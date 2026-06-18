# ADR 0003: Knowledge Base Retrieval

## Issue

Milestone 3 needs a local retrieval path for leasing policy, process, and narrative property content. The voice assistant already has a SQLite domain model for exact property and unit facts, but later agent tools need a separate way to answer broader questions such as application requirements, deposits, pets, parking, lease terms, amenities, and general property descriptions without relying on model memory.

The knowledge base must support three core behaviors:

- answer common leasing FAQ and policy questions from local source content
- return source metadata so the agent can keep answers grounded
- produce a clear no-match or low-confidence result for irrelevant or unsupported questions

The key decision is whether to introduce vector retrieval now or keep milestone 3 focused on local files, deterministic ingestion, and lexical retrieval that is easy to test from a clean checkout.

## Decision

Use local markdown or structured text source files as the knowledge-base authority and ingest them into a small local searchable index backed by SQLite FTS or a lightweight lexical ranker. Keep vector retrieval explicitly out of the initial implementation.

The initial package layout will add:

```text
src/
  leasing_voice_assistant/
    knowledge/
      __init__.py
      ingest.py
      models.py
      retrieval.py
data/
  knowledge/
    general_faq.md
    properties/
      ...
tests/
  test_knowledge_retrieval.py
```

Knowledge source files should contain compact, reviewer-readable content for:

- application process
- deposits and fees
- pet policy
- parking policy
- lease terms
- general property narrative and amenities

Ingestion should split source files into small chunks with stable metadata:

- source path
- document title or section
- property identifier when content is property-specific
- chunk identifier
- source text

Retrieval should return structured results with score, text, and metadata. The eventual `search_knowledge_base` agent tool should use this service rather than reading files directly. Unknown or irrelevant questions should return an empty or low-confidence result instead of forcing an answer.

## Status

Accepted for implementation.

## Group

Milestone 3: Knowledge Base Retrieval.

## Assumptions

- The initial knowledge base is small enough for local lexical retrieval.
- Exact property and unit facts remain in SQLite structured tables and repositories.
- The knowledge base is for policy, process, FAQ, and narrative content, not prospect capture.
- Reviewers should be able to inspect source files directly.
- Local tests must not require provider, telephony, embedding, or hosted search credentials.
- The first implementation can rebuild the knowledge index deterministically during setup or tests.

## Constraints

- Keep the project runnable from a clean checkout.
- Keep the API and worker as separate runtime entrypoints.
- Do not require vector database infrastructure or embedding provider credentials.
- Retrieval behavior must be deterministic enough for focused tests.
- Results must include source metadata for grounded answers.
- Unknown answers must be represented explicitly so the agent can avoid guessing.
- The knowledge implementation should remain small enough to support the voice agent rather than becoming a document platform.

## Positions

### Position 1: Local source files with SQLite FTS or a lightweight lexical ranker

Store KB authority in local markdown or structured text files, ingest stable chunks into a local searchable form, rank with SQLite FTS or simple lexical scoring, and return structured source-backed results.

### Position 2: Vector retrieval with embeddings and a vector store

Generate embeddings for chunks and retrieve semantically similar content from a local or hosted vector index.

## Argument

Position 1 is the project decision. The knowledge base for this assignment is intentionally small and domain-specific, so local lexical retrieval is sufficient for the first working voice agent. It keeps setup simple, avoids embedding credentials, and produces deterministic behavior that can be tested without network access.

SQLite FTS is a natural fit because the project already uses SQLite as its local data foundation. If FTS integration is too much ceremony for the first pass, a lightweight lexical ranker over ingested chunks is also acceptable as long as it returns stable scores and source metadata. The important boundary is the retrieval service and eventual tool contract, not the specific ranking implementation.

Vector retrieval would be reasonable for a larger or messier corpus, but it adds provider selection, embedding costs, index lifecycle, test brittleness, and failure modes that do not help the core milestone. The assignment values a working voice agent with grounded answers more than broad retrieval infrastructure. Deferring vector retrieval keeps attention on the call experience and safe tool behavior.

The chunking strategy should be deliberately simple. Section-level chunks from markdown headings are easier for reviewers to inspect and easier for tests to assert against than aggressive token-based splitting. Each result should carry enough metadata for the agent to cite or summarize the source internally and to decide whether a retrieved answer is relevant enough to use.

Unknown behavior is part of the design. The retrieval service should allow the agent to say that a policy is not available in the knowledge base instead of stretching unrelated content into an answer.

## Implications

- KB content can be reviewed and edited as plain files.
- Tests can seed or ingest local KB content without external services.
- The voice agent can separate exact facts from structured repositories and broader policies from KB retrieval.
- Retrieval quality depends on concise source content, section titles, and predictable terminology.
- The first ranker may miss semantic matches that embeddings would catch; test content and agent prompts should use natural leasing language to reduce this risk.
- Vector retrieval remains an additive future enhancement behind the same retrieval service boundary.
- Source metadata must be preserved from ingestion through tool response.

## Related decisions

- Use SQLite for application data.
- Use structured database tools for exact property and unit facts.
- Use local retrieval for broader policy and narrative answers.
- Defer vector retrieval and embedding providers until the local voice agent is working.
- Keep provider credentials optional for linting, tests, and local health checks.
- Keep agent tools narrow and source-backed.

## Related requirements

- KB can answer application, deposit, pet, parking, and lease-term questions.
- Retrieval returns source metadata.
- Unknown questions return no-match or low-confidence results.
- Tests cover relevant and irrelevant queries.
- Vector retrieval and broad search infrastructure are explicitly deferred.
- The eventual `search_knowledge_base` tool uses the retrieval service instead of direct file access.

## Related artifacts

- `brief.md`
- `docs/project/IMPLEMENTATION_PLAN.md`
- `docs/project/ARCHITECTURE.md`
- `docs/project/STATUS.md`
- `docs/project/adr/0001-project-foundation-and-runtime.md`
- `docs/project/adr/0002-sqlite-domain-model-and-seed-data.md`
- Future `data/knowledge/`
- Future `src/leasing_voice_assistant/knowledge/ingest.py`
- Future `src/leasing_voice_assistant/knowledge/retrieval.py`
- Future `tests/test_knowledge_retrieval.py`
- Future `search_knowledge_base` agent tool

## Related principles

- Keep the voice agent as the center of the project.
- Ground exact facts in structured data.
- Ground policy and narrative answers in retrievable source content.
- Prefer small milestone-scoped changes over broad infrastructure.
- Make local setup and reviewer verification straightforward.
- Say when information is unavailable instead of inventing facts.

## Notes

This ADR intentionally does not implement the final agent tool layer, provider adapters, LiveKit SIP call flow, prospect capture safety gate, or vector retrieval. It establishes the local knowledge retrieval boundary that those later milestones can use.
