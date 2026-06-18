# Leasing Voice Assistant Implementation Plan

## Milestone Overview

The project will be implemented through architecture decision records and milestone-specific implementation passes. Each milestone should get an ADR first, using the Tyree and Akerman decision record structure provided by the project owner. After the ADR is accepted, implementation should follow that ADR.

## ADR Template

Each milestone ADR should use these sections:

- Issue
- Decision
- Status
- Group
- Assumptions
- Constraints
- Positions
- Argument
- Implications
- Related decisions
- Related requirements
- Related artifacts
- Related principles
- Notes

ADR files should live under:

```text
docs/project/adr/
```

Suggested naming:

```text
0001-project-foundation-and-runtime.md
0002-sqlite-domain-model-and-seed-data.md
0003-livekit-sip-call-pipeline.md
```

## Milestone 1: Project Foundation and Runtime Shape

Goal: create a clean Python project skeleton that can support the rest of the system.

Scope:

- `uv` Python project setup
- package layout for FastAPI app and LiveKit worker
- linting and formatting with Ruff
- test setup with Pytest
- environment configuration model
- `.env.example`
- initial README run instructions
- docs/project status discipline

Primary decision topics:

- package layout
- dependency management
- configuration strategy
- whether worker and API live in one repository and one process model

Exit criteria:

- project installs from clean checkout
- lint/test commands exist
- empty FastAPI health endpoint runs
- empty worker entrypoint imports
- status file reflects completion

## Milestone 2: SQLite Domain Model, Repositories, and Seed Data

Goal: create the authoritative local data layer for properties, units, prospects, and interests.

Scope:

- SQLite schema
- SQLAlchemy models or explicit SQL repository layer
- seed data for one or two leasing properties
- repository methods for property search, unit detail lookup, prospect upsert, and interest creation
- focused tests for data behavior

Primary decision topics:

- migration approach for SQLite
- schema shape
- repository boundary
- prospect matching and dedupe rules

Exit criteria:

- database can be initialized locally
- seed data loads deterministically
- tests prove prospect upsert by phone
- tests prove duplicate interest behavior
- tests prove exact unit fact retrieval

## Milestone 3: Knowledge Base Retrieval

Goal: build simple local retrieval for leasing FAQs and property narrative content.

Scope:

- markdown or structured KB source files
- ingestion into local searchable form
- SQLite FTS or lightweight lexical ranker
- retrieval service and `search_knowledge_base` tool implementation
- tests for policy/process questions

Primary decision topics:

- local FTS versus vector retrieval
- minimal document chunking approach
- source metadata needed for grounded answers
- fallback behavior for unknown answers

Exit criteria:

- KB can answer application, deposit, pet, parking, and lease-term questions
- retrieval returns source metadata
- unknown questions return no-match or low-confidence result
- tests cover relevant and irrelevant queries
- vector retrieval and broad search infrastructure are explicitly deferred

## Milestone 4: Provider Adapter Layer

Goal: keep STT, TTS, and LLM provider details out of the LiveKit worker without building unused provider support.

Scope:

- STT provider interface
- TTS provider interface
- LLM provider interface
- Deepgram STT adapter
- Deepgram TTS adapter
- OpenRouter LLM adapter
- provider factory driven by environment variables

Primary decision topics:

- adapter contract
- environment variable naming
- OpenRouter OpenAI-compatible integration
- how little of LiveKit's provider-specific SDK surface to expose

Exit criteria:

- worker can build STT/LLM/TTS through the factory
- default config is Deepgram STT, Deepgram TTS, OpenRouter LLM
- missing credential errors are explicit
- unit tests cover provider selection
- no unused future-provider stubs are required for the submission

## Milestone 5: Leasing Agent Tools and Safety Gate

Goal: implement the agent's tool layer and prospect capture safety logic.

Scope:

- `search_properties`
- `get_unit_details`
- `search_knowledge_base`
- `capture_prospect_interest`
- optional `end_conversation` only if needed for real LiveKit call control
- per-call state model
- confidence and confirmation checks before writes
- tests for tool behavior and rejected writes

Primary decision topics:

- property-resolution confidence scoring
- what counts as confirmed interest
- required prospect fields
- tool return schema

Exit criteria:

- factual property answers come from SQLite tools
- broader policy answers come from KB tool
- capture tool rejects ambiguous/unsafe writes
- capture tool creates or updates prospect when safety passes
- tests cover ambiguous property, missing name, missing phone, and valid capture

## Milestone 6: LiveKit SIP Call Pipeline

Goal: connect the worker to real inbound LiveKit SIP/Twilio calls.

Scope:

- LiveKit worker entrypoint
- SIP metadata parsing
- room/call lifecycle handling
- Deepgram STT/TTS and OpenRouter LLM through adapters
- VAD and turn detection configuration
- inbound call instructions
- local runbook for Twilio and LiveKit SIP setup

Primary decision topics:

- inbound dispatch strategy
- call metadata mapping
- turn detection defaults
- latency versus quality tradeoffs

Exit criteria:

- inbound phone call reaches LiveKit room
- worker joins and speaks
- caller can ask multiple questions
- agent can use tools during a call
- call can end politely

## Milestone 7: End-to-End Grounded Conversation and Prospect Capture

Goal: complete the assignment's core user journey.

Scope:

- final system prompt
- conversation state tuning
- natural short responses
- property clarification flow
- prospect capture flow
- manual call scenarios
- persisted prospect verification

Primary decision topics:

- final prompt constraints
- when to ask for name/email
- whether to capture unit-level or property-level interest
- whether transcript/call event persistence is necessary for the demo or should be deferred

Exit criteria:

- caller asks rent, bedrooms, view, parking, pet policy, and availability
- agent answers from tools without inventing facts
- agent handles unknowns gracefully
- agent registers interest after confirmation
- SQLite shows correct prospect and interest rows
- transcript and tool-event persistence are deferred unless needed to debug the demo call

## Milestone 8: Evaluation, Documentation, and Demo Evidence

Goal: make the repository reviewable and submission-ready.

Scope:

- README completion
- architecture documentation updates
- evaluation documentation
- manual test script
- optional LLM-as-judge design
- real call recording or video artifact
- final cleanup

Primary decision topics:

- evaluation approach
- what call recording or video is used as demo evidence
- what tradeoffs are documented

Exit criteria:

- clean checkout instructions work, including how a reviewer can place a call or talk to the assistant
- required credentials are documented
- test/lint commands pass
- call recording or video is captured for submission
- docs explain architecture, grounding, tools, safety, and future work

## Suggested ADR Order

1. Project foundation and runtime shape.
2. SQLite domain model and seed data.
3. Provider adapter layer.
4. Knowledge retrieval approach.
5. Leasing tools and prospect capture safety gate.
6. LiveKit SIP inbound call pipeline.
7. End-to-end conversation policy.
8. Evaluation and demo evidence.

The order intentionally establishes the project skeleton and data layer before realtime voice integration. This keeps the highest-risk voice work testable against stable local tools.
