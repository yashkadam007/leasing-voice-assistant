# Project Status

## Current Phase

Planning.

## Milestone Status

| Milestone | Status | ADR | Implementation | Notes |
| --- | --- | --- | --- | --- |
| 1. Project Foundation and Runtime Shape | Pending | Not started | Not started | First ADR to create. |
| 2. SQLite Domain Model, Repositories, and Seed Data | Pending | Not started | Not started | Use SQLite as requested. |
| 3. Knowledge Base Retrieval | Pending | Not started | Not started | Start with local FTS/ranker; vector retrieval remains optional. |
| 4. Provider Adapter Layer | Pending | Not started | Not started | Defaults: Deepgram STT, Deepgram TTS, OpenRouter LLM. |
| 5. Leasing Agent Tools and Safety Gate | Pending | Not started | Not started | Must gate prospect writes by confidence and confirmation. |
| 6. LiveKit SIP Call Pipeline | Pending | Not started | Not started | Primary call path is LiveKit SIP/Twilio. |
| 7. End-to-End Grounded Conversation and Prospect Capture | Pending | Not started | Not started | Core assignment journey. |
| 8. Evaluation, Documentation, and Demo Evidence | Pending | Not started | Not started | Includes call recording/video evidence. |

## Decisions Captured

| Decision | Status | Notes |
| --- | --- | --- |
| Use LiveKit Agents as the voice agent framework | Decided | Requested by project owner. |
| Use LiveKit SIP/Twilio for primary telephony | Decided | Browser fallback is optional, not primary. |
| Use SQLite for application data | Decided | Keeps clean-checkout setup simple. |
| Use Deepgram for STT and TTS by default | Decided | Provider adapter layer should keep this swappable. |
| Use OpenRouter for LLM by default | Decided | OpenAI-compatible adapter should make model experiments easy. |
| Use provider adapters for STT/TTS/LLM | Decided | Avoid coupling the worker to concrete providers. |
| Use vector retrieval initially | Not decided | Local FTS/ranker is the current recommendation; vector retrieval can be added later. |

## Open Questions

- Which Deepgram STT model should be the default?
- Which Deepgram TTS voice/model should be the default?
- Which OpenRouter model should be the default for the first implementation?
- Should prospect interest be recorded at `unit_id`, `property_id`, or both?
- Should email capture be attempted during the call or left optional unless the caller offers it?

## Next Action

Create ADR 0001 for Milestone 1: Project Foundation and Runtime Shape, using the Tyree and Akerman decision record template.

