# Take-Home Assignment: Leasing Voice AI Assistant

## Overview

Build a voice AI assistant for property leasing. A prospective renter calls in, asks questions about a property, and the assistant answers in a natural, two-way voice conversation, drawing on a property database and a knowledge base. During the call, the assistant works out which property the caller means, and registers the caller as a prospect with their interest in that property.

The focus of this assignment is the voice agent: a real, functional, voice-to-voice conversation that answers grounded questions and captures the prospect. The surrounding data model is kept deliberately small, and example schemas and content are provided so the time goes into the agent, not into modeling the domain.

## Objective

Two capabilities, over a real voice call:

1. **Answer questions.** The caller asks about a property: rent, number of bedrooms, the view (for example lake-facing), parking, the pet policy, availability, and similar. The assistant works out which property is meant, answers factual questions from the property database and broader questions from the knowledge base, and does not invent facts. It handles a question it cannot answer gracefully.
2. **Capture the prospect.** The assistant identifies the property of interest and writes to the database to register a new prospect or update an existing one, matched by phone number and name, recording their interest in that property.

## What to build (core)

- A real two-way voice conversation: the caller speaks, the assistant responds in a natural voice, back and forth, until the caller is done.
- A tool-using agent that works against both the database and the knowledge base:
  - Search and read the database to find the property the caller means and answer factual questions about it (rent, bedrooms, view, parking, availability).
  - Search the knowledge base for everything else: policies, the application process, lease terms, FAQs, and richer descriptions.
  - Write to the database to register or update the prospect (matched by phone number) and log their interest in the property.
- The agent decides which tool to use for a given turn, grounds its answers in what it retrieves, and does not guess.
- A confidence or safety check before any write, so the assistant only records a prospect's interest once it is confident it has the right property and the right caller details, not on a garbled or uncertain turn.

## Suggested components

Use what you are productive in. A reasonable setup, and the one this problem is shaped around:

- Telephony: Twilio (an inbound number with media streaming). A browser-based two-way voice loop is an acceptable alternative if telephony setup is a blocker, as long as the conversation is genuinely voice-to-voice.
- Backend: Python (FastAPI).
- Agent framework: your choice. We build our agents on the Strands Agents SDK (https://strandsagents.com/), so using it here is a plus, though any well-structured approach is fine.

Beyond that, use whatever speech, model, and storage tools you think are best. You choose how to store and retrieve the knowledge base, and how the agent's tools talk to the database, and explain the choices in your documentation.

## Provided data and schemas

These are provided so you can focus on the agent. Adapt field names as needed. The property and prospect data live in a database the agent reads from and writes to through tools; the knowledge base is separate content the agent searches.

**Properties** (a small set of sample listings is included):

```
property:   id, name, address, city
unit:       id, property_id, label, bedrooms, bathrooms, sqft,
            monthly_rent, available_from, view, parking, pet_policy,
            amenities, status (available | leased)
```

**Prospects:**

```
prospect:          id, name, phone, email (optional), created_at
prospect_interest: id, prospect_id, unit_id (or property_id),
                   source (e.g. voice_call), notes, status (new | contacted),
                   created_at
```

**Knowledge base:** a set of documents and FAQ entries is included, for example a fact sheet per property (rent, view, parking, pet policy, lease terms, availability) and a general leasing FAQ (application process, deposits, pet rules). The raw content is provided; how you ingest, store, and retrieve it is your decision.

## Expectations

- **Functional end to end.** We can place a call (or talk to it) and hold a genuine two-way voice conversation that answers questions and registers interest. A short recording of a real call is the clearest evidence; please include one.
- **Natural, not robotic.** A latency of two to three seconds between turns is fine. What matters is that the assistant sounds natural and conversational rather than a flat, robotic monotone, and that it handles ordinary back-and-forth. Handling interruptions or barge-in is a plus, not a requirement.
- **Grounded answers.** Answers come from the database and the knowledge base. The assistant does not hallucinate property facts, and it handles an unknown question gracefully.
- **Safe actions.** A confidence or safety check gates the write, so the assistant does not register the wrong property or a garbled prospect.
- **Code quality and maintainability.** We read the repository as a real pull request. A clean, well-structured codebase that follows sound design principles, with linting and formatting set up, is expected and counts in the evaluation.

## Scope guidance

Keep it simple and focused on the voice agent. This is not a CRM, and it needs no authentication or polished UI. One or two properties handled well, a working call with grounded answers, and a correctly registered prospect is the target. Depth on the conversation and the agent beats breadth of features.

## Deliverables

1. A GitHub repository with the working application, runnable from a clean checkout by following the README, including how to place a call or talk to it and which credentials are needed.
2. Planning and architecture documentation as markdown files in the repository: how you approached it, the call and audio pipeline, the agent's tools and how they read from and write to the database, the knowledge layer and why you chose it, the property-resolution and prospect-capture logic, the confidence or safety check, and key decisions, tradeoffs, and what you would do with more time.
3. A short recording or video of a real call. Voice is hard to judge from code alone, so this matters.

## Evaluation criteria

- **Voice experience:** a genuine, natural two-way conversation; latency handled acceptably; not robotic.
- **Knowledge grounding:** accurate answers grounded in the database and the knowledge base; graceful handling of unknowns; sensible tool use and retrieval.
- **Agent design and safety:** tool design (reading and searching the database, searching the knowledge base, writing back), property resolution, the confidence or safety gate before writing, and correct prospect capture.
- **Architecture and code quality:** the agent and tool design, the audio pipeline, conversation state management, and a clean, maintainable, well-structured codebase with linting and formatting in place.
- **Documentation:** whether the markdown files make the approach and reasoning easy to follow.
- **Evaluation thinking (differentiator):** how you would evaluate this agent's quality over time, for example with an LLM-as-judge or a test set, even if not fully built.

Not evaluated: a full CRM or admin UI, authentication, perfect latency, or handling every edge of telephony. A focused, natural, grounded voice agent that captures the prospect is the goal.

## Ground rules

- AI coding tools are encouraged. The planning markdown files are part of the submission and should reflect genuine reasoning.
- Free-tier or trial accounts for the telephony, speech, and model providers are sufficient. If a credential is a blocker, tell us and we will provide one.
- The project must run from a clean checkout by following the README.

## Submission

Submit a link to the GitHub repository and the call recording. If the repository is private, grant access to the address from which this assignment was sent.

## FAQ

- **Does it have to be a real phone call?** A real inbound call is ideal. A browser-based two-way voice loop is acceptable if telephony is a blocker, as long as the conversation is genuinely voice-to-voice.
- **How many properties do I need to support?** One or two, handled well, is enough.
- **How should I store the knowledge base?** Your choice. Use retrieval with embeddings, a markdown or structured lookup, or anything else, and explain the tradeoff.
- **Do I need to handle existing prospects?** Match by phone number: if the caller is known, update them; if not, create them. Keep it simple.
- **Is two to three seconds of latency acceptable?** Yes, as long as the conversation still feels natural rather than robotic.
