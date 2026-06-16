# Requirements

## Problem Statement

Build a practical voice AI assistant for property leasing. A prospective renter should be able to speak naturally with the assistant, ask questions about a property, receive answers grounded in a property database and a knowledge base, and be safely registered as a prospect for the correct property.

The assignment emphasizes the voice agent experience, grounded tool use, property resolution, safe prospect capture, maintainable architecture, automated verification, clear documentation, and an evaluation methodology.

## Core Functional Requirements

| ID | Requirement | Source |
| --- | --- | --- |
| FR-01 | Support a real, back-and-forth voice-to-voice conversation. | Explicit |
| FR-02 | Answer factual property/unit questions from the database, including rent, bedrooms, view, parking, pet policy, and availability. | Explicit |
| FR-03 | Answer broader leasing questions from the knowledge base, including policies, application process, lease terms, FAQs, and richer descriptions. | Explicit |
| FR-04 | Resolve which property or unit the caller means during the conversation. | Explicit |
| FR-05 | Avoid inventing facts and handle unknown questions gracefully. | Explicit |
| FR-06 | Capture caller identity details needed to register a prospect, including phone number and name. | Explicit |
| FR-07 | Create a new prospect or update an existing prospect matched by phone number. | Explicit |
| FR-08 | Log the prospect's interest in the resolved property or unit. | Explicit |
| FR-09 | Require confidence or confirmation before any prospect write. | Explicit |
| FR-10 | Use sensible agent tools for database reads, knowledge-base retrieval, and database writes. | Explicit |
| FR-11 | Support a real inbound call or a genuinely voice-to-voice browser alternative if telephony setup is blocked. | Explicit |

## Non-Functional Requirements

| ID | Requirement | Source |
| --- | --- | --- |
| NFR-01 | Conversation should sound natural rather than robotic. | Explicit |
| NFR-02 | Two to three seconds of turn latency is acceptable if the conversation remains natural. | Explicit |
| NFR-03 | Code should be clean, maintainable, and structured like a real pull request. | Explicit |
| NFR-04 | Linting and formatting should be set up. | Explicit |
| NFR-05 | The project must run from a clean checkout by following the README. | Explicit |
| NFR-06 | Automated verification should cover core behavior. | Recommendation from evaluation criteria |
| NFR-07 | Provider credentials and secrets must not be committed. | Security expectation |
| NFR-08 | Provider integrations should be testable without real calls. | Recommendation to satisfy maintainability and verification |

## Required Deliverables

| ID | Deliverable | Source |
| --- | --- | --- |
| DEL-01 | A GitHub repository with the working application. | Explicit |
| DEL-02 | README instructions for clean-checkout setup, running, and how to place a call or talk to the assistant. | Explicit |
| DEL-03 | Markdown planning and architecture documentation. | Explicit |
| DEL-04 | Short recording or video of a real call or voice conversation. | Explicit |
| DEL-05 | Documentation of credentials required for providers. | Explicit |

## Evaluation Criteria

| ID | Criterion | Notes |
| --- | --- | --- |
| EVAL-01 | Voice experience | Genuine two-way conversation, acceptable latency, natural voice. |
| EVAL-02 | Knowledge grounding | Accurate database and KB answers, graceful unknown handling. |
| EVAL-03 | Agent design and safety | Tool design, property resolution, write gate, correct capture. |
| EVAL-04 | Architecture and code quality | Audio pipeline, state, clean structure, linting, formatting. |
| EVAL-05 | Documentation | Approach and reasoning are easy to follow. |
| EVAL-06 | Evaluation thinking | Test set or LLM-as-judge methodology over time. |

## Explicit Non-Goals

- Full CRM.
- Authentication.
- Polished admin UI.
- Perfect latency.
- Full telephony edge-case coverage.
- Broad property catalog.
- Barge-in/interruption handling unless time permits.
- Complex leasing workflows beyond registering interest.

## MVP Scope

The MVP should focus on:

- One or two properties handled well.
- Small property/unit/prospect database.
- Small knowledge base with property factsheets and general leasing FAQ.
- Text conversation harness before voice integration.
- Browser-based voice loop if telephony credentials or trial limits block Twilio.
- Safe prospect capture with confirmation before writes.
- Automated tests for deterministic business behavior.
- Clear README and demo recording path.

## Optional Enhancements

These are optional and must not displace the MVP:

- Twilio inbound phone call with media streaming.
- Strands Agents SDK integration.
- LLM-as-judge evaluation.
- Barge-in or interruption handling.
- Embedding-based retrieval if lightweight retrieval is insufficient.
- Richer observability dashboards.

## External Dependencies

- Model provider account and API key.
- Speech-to-text provider account and API key, unless using local/browser transcription.
- Text-to-speech provider account and API key, unless using browser speech synthesis.
- Twilio account, phone number, and media-streaming setup if real telephony is used.
- Public tunnel or deploy target if Twilio must reach local development.
- Demo recording tooling.

## Unclear Or Underspecified Requirements

- The brief says sample listings and knowledge-base content are included, but the repository currently contains only `brief.md`.
- Exact preferred model, STT, TTS, telephony, and storage providers are not specified.
- It is not specified whether the final demo must be a real phone call if browser voice works.
- Recording format and hosting location are not specified.
- Deployment environment is not specified.
- Exact confidence threshold for writes is not specified.

## Assumptions Requiring Validation

- Seed property and KB content may need to be created if no separate data files are provided.
- A browser-based voice loop is acceptable if Twilio setup or credentials are blocked.
- Matching prospects by phone number is sufficient for MVP, with name used for confirmation and display.
- A single local database is acceptable for the assignment MVP.
- Provider interfaces are worth adding because they keep voice/model integrations testable without real calls.

## Requirements Traceability

| Requirement | Milestone(s) | Verification Method |
| --- | --- | --- |
| FR-01 | M10, M11, M15 | Browser or call demo recording; voice integration test where possible. |
| FR-02 | M03, M04, M07, M12 | Unit tests for DB tools; integration conversation scenarios. |
| FR-03 | M05, M07, M12 | KB retrieval tests; grounded answer scenarios. |
| FR-04 | M06, M07, M12 | Property-resolution unit tests; ambiguous-reference scenarios. |
| FR-05 | M04, M05, M07, M13 | Explicit DB and KB no-match tests; unknown-question tests; eval scenarios for hallucination prevention. |
| FR-06 | M08, M09, M11, M12 | Prospect capture tests; manual voice scenario. |
| FR-07 | M03, M08, M12 | Upsert tests using duplicate phone numbers. |
| FR-08 | M03, M08, M12 | Interest logging and idempotency tests. |
| FR-09 | M08, M12, M13 | Confirmation-gate tests for low confidence and garbled input. |
| FR-10 | M04, M05, M07, M13 | DB tool tests; KB retriever tests; tool selection tests; eval trace review. |
| FR-11 | M10, M11, M15 | Browser voice or telephony demo evidence. |
| NFR-01 | M10, M11, M15 | Manual demo review; latency and voice notes. |
| NFR-02 | M10, M14, M15 | Structured timing logs; manual demo review. |
| NFR-03 | M01-M15 | Code review; architecture docs; tests. |
| NFR-04 | M01 | Lint and format commands run. |
| NFR-05 | M15 | Clean-checkout verification. |
| NFR-06 | M01, M04-M14 | Automated test suite results. |
| NFR-07 | M01, M02, M15 | Secret scan by review; ignored env files; README credential docs. |
| NFR-08 | M02, M10-M12 | Fake provider tests; no real-call requirement for CI tests. |
| DEL-01 | M15 | Repository ready for submission. |
| DEL-02 | M01, M15 | README verified from clean checkout. |
| DEL-03 | M00-M15 | Markdown docs updated through milestones. |
| DEL-04 | M15 | Demo recording produced or recording instructions documented. |
| DEL-05 | M02, M11, M15 | Credential list in README and status docs. |

## Current Verification Evidence

- M01 provides the first concrete evidence for NFR-03, NFR-04, NFR-06, NFR-07, DEL-02, and DEL-03: scaffold code, README commands, smoke tests, linting, formatting, type checking, ignored local env files, and documentation updates.
- M02 provides concrete evidence for NFR-03, NFR-06, NFR-07, NFR-08, and DEL-05: Pydantic Settings with optional provider credentials, protocol-based provider boundaries, deterministic fakes, credential-redaction tests, and README credential documentation.
- M03 provides concrete evidence for FR-02, FR-07, FR-08, NFR-03, NFR-05, NFR-06, and NFR-07: SQLite migrations, synthetic property/unit seed data, concrete property and prospect repositories, phone-based prospect upsert tests, idempotent interest logging tests, and ignored generated database files.
- M04 provides concrete evidence for FR-02, FR-05, FR-10, NFR-03, and NFR-06: read-only database query tools, structured evidence records, result limits, exact/ambiguous/no-match property search tests, unit listing tests, and unit fact lookup tests.
- M05 provides concrete evidence for FR-03, FR-05, FR-10, NFR-03, and NFR-06: Markdown KB source files, deterministic lexical retrieval, source-attributed snippets, result and snippet limits, FAQ retrieval tests, property-description retrieval tests, and unknown-query tests.
- M06 provides concrete evidence for FR-04, FR-05, FR-09 preparation, FR-10, EVAL-03, NFR-03, and NFR-06: deterministic property-resolution state, explicit confidence and clarification reasons, write-readiness classification, context reuse, exact property reference tests, unit-hint narrowing tests, ambiguous-property tests, ambiguous-unit tests, no-match tests, and prior-context replacement tests.
- M06 does not yet satisfy voice, confirmation-gated prospect capture, full answer orchestration, or demo-recording requirements; those remain assigned to later milestones.
