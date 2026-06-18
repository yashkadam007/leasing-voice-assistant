# Test Conversation Scenarios

This document provides manual conversation scenarios for testing the leasing voice assistant against the assignment brief and the current local data. The goal is to verify a real two-way leasing conversation that answers grounded questions, avoids invented facts, and captures prospect interest only when the safety gate allows it.

## Source Data

Use these files as the expected-answer baseline:

- `brief.md`
- `src/leasing_voice_assistant/db/seed.py`
- `data/knowledge/general_faq.md`
- `data/knowledge/properties/aurora-heights.md`
- `data/knowledge/properties/pine-garden-flats.md`
- `docs/project/adr/0005-leasing-agent-tools-and-safety-gate.md`

## Seed Facts To Verify

### Aurora Heights

Property facts:

- Address: 1250 Market Street, San Francisco, CA
- Description: Transit-friendly apartments with rooftop lounge and in-building fitness
- Pet policy: cats and dogs welcome, up to two pets per home, breed restrictions apply
- Parking: garage parking available for $275 per month
- Application fee: $55
- Security deposit: $750
- Lease terms: 9, 12, and 15 months
- Amenities from knowledge base: rooftop lounge, fitness room, controlled-entry lobby, package lockers, elevator access

Units:

| Unit | Beds | Baths | Rent | Sq Ft | Available | Status | Floor | View | Notes |
| --- | ---: | ---: | ---: | ---: | --- | --- | ---: | --- | --- |
| 4B | 1 | 1.0 | $3,250 | 690 | 2026-07-15 | available | 4 | city | Corner one-bedroom with west-facing windows |
| 8A | 2 | 2.0 | $4,825 | 1,040 | 2026-08-01 | available | 8 | bay | Two-bedroom home with balcony and bay view |
| 2C | 0 | 1.0 | $2,450 | 510 | 2026-07-01 | reserved | 2 | courtyard | Studio with courtyard exposure; currently reserved |

### Pine Garden Flats

Property facts:

- Address: 880 Pine Avenue, Oakland, CA
- Description: Quiet garden-style community near Lake Merritt and local cafes
- Pet policy: one cat or dog allowed per home with monthly pet rent
- Parking: one surface parking space included with each lease
- Application fee: $45
- Security deposit: $500
- Lease terms: 12 months
- Amenities from knowledge base: landscaped courtyards, shared laundry, bike storage, neighborhood dining access

Units:

| Unit | Beds | Baths | Rent | Sq Ft | Available | Status | Floor | View | Notes |
| --- | ---: | ---: | ---: | ---: | --- | --- | ---: | --- | --- |
| 11 | 1 | 1.0 | $2,625 | 735 | 2026-07-20 | available | 1 | garden | Ground-floor one-bedroom with patio |
| 24 | 2 | 1.5 | $3,475 | 960 | 2026-09-05 | available | 2 | tree-lined street | Two-bedroom flat with extra storage |

## General Pass Criteria

The assistant should:

- Keep replies natural and concise enough for voice.
- Use structured database facts for unit rent, bedrooms, bathrooms, square footage, availability, status, view, and parking or policy fields stored on the property.
- Use the knowledge base for application process, deposits, fees, pet policy details, lease terms, amenities, and narrative descriptions.
- Ask a clarifying question when the property or unit is ambiguous.
- Say it does not know or needs leasing-team confirmation when the data does not contain an answer.
- Capture prospect interest only after it has a caller phone number, caller name, a high-confidence unambiguous property or unit, and explicit confirmation of interest.
- Avoid capturing a prospect when the caller only asks questions and has not confirmed interest.

## Scenario 1: Aurora Heights Unit 8A, Successful Capture

Purpose: Verify exact unit facts, knowledge retrieval, natural follow-up, and safe prospect capture.

Preconditions:

- The call metadata includes caller phone number `+14155551212`.
- The database has been seeded with current local seed data.

Conversation:

| Turn | Caller says | Expected assistant behavior |
| ---: | --- | --- |
| 1 | Hi, I am calling about Aurora Heights. | Resolve Aurora Heights as the target property. Briefly acknowledge and ask how it can help. |
| 2 | Do you have any two-bedroom apartments? | Use structured data. Mention unit 8A as a two-bedroom, two-bath available unit. |
| 3 | What is the rent and view for 8A? | Answer: unit 8A is $4,825 per month, 1,040 sq ft, bay view, available 2026-08-01. |
| 4 | Does it have parking? | Answer with Aurora Heights parking: garage parking is available for $275 per month, and availability should be confirmed when selecting a unit. |
| 5 | Are dogs allowed? | Answer from property/KB: cats and dogs are welcome, up to two pets per home, breed restrictions apply; current pet rent or deposit should be confirmed. |
| 6 | Great, I am interested in 8A. | Ask for the caller's name if not already known before capture. |
| 7 | My name is Sam Rivera. | Confirm interest in Aurora Heights unit 8A, then call capture. |
| 8 | Yes, please have someone follow up. | Capture should succeed. Give a brief confirmation that Sam Rivera's interest in Aurora Heights unit 8A was recorded. |

Expected write result:

- Prospect phone: `+14155551212`
- Prospect name: `Sam Rivera`
- Interest target: unit 8A
- Source/status behavior: voice call interest, new/contacted status according to current repository defaults

Failure signals:

- Assistant invents a tour time, specials, income requirement, or pet rent amount.
- Assistant records interest before the caller confirms interest.
- Assistant captures property-level interest when the caller clearly selected unit 8A.

## Scenario 2: Pine Garden Flats, Property-Level Capture

Purpose: Verify property-level resolution and capture when the caller does not choose a specific unit.

Preconditions:

- The call metadata includes caller phone number `+15105553434`.

Conversation:

| Turn | Caller says | Expected assistant behavior |
| ---: | --- | --- |
| 1 | I saw Pine Garden Flats. Can you tell me about it? | Resolve Pine Garden Flats. Summarize from KB: quiet garden-style community in Oakland near Lake Merritt and local cafes. |
| 2 | What amenities are there? | Answer from KB: landscaped courtyards, shared laundry, bike storage, and access to neighborhood dining. |
| 3 | What one-bedrooms are available? | Use structured data. Mention unit 11: one bed, one bath, $2,625, 735 sq ft, available 2026-07-20, garden view. |
| 4 | Is parking included? | Answer: one surface parking space is included with each lease. |
| 5 | I am interested in the property, but not sure which unit yet. | Ask for caller name if missing and confirm property-level interest. |
| 6 | I am Lee Chen. Yes, please note my interest. | Capture property-level interest for Pine Garden Flats. |

Expected write result:

- Prospect phone: `+15105553434`
- Prospect name: `Lee Chen`
- Interest target: Pine Garden Flats property
- No unit interest should be written unless the caller later selects unit 11 or 24.

Failure signals:

- Assistant forces a unit choice when property-level interest is acceptable.
- Assistant records interest for Aurora Heights.
- Assistant says parking has a monthly charge for Pine Garden Flats.

## Scenario 3: Ambiguous Property, Clarification Required

Purpose: Verify that the assistant does not guess when caller wording could match multiple properties or is too vague.

Preconditions:

- The call metadata includes caller phone number `+14155559999`.

Conversation:

| Turn | Caller says | Expected assistant behavior |
| ---: | --- | --- |
| 1 | I want to ask about the apartments. | Ask which community the caller means, because this is ambiguous. |
| 2 | The one with a two-bedroom. | Mention that both communities have two-bedroom options and ask whether they mean Aurora Heights or Pine Garden Flats. |
| 3 | I think the Oakland one. | Resolve Pine Garden Flats. |
| 4 | What is the two-bedroom rent? | Answer unit 24: $3,475 per month, 2 beds, 1.5 baths, 960 sq ft, available 2026-09-05. |
| 5 | Okay, add me as interested. | Ask for caller name and confirm Pine Garden Flats or unit 24 interest before capture. |

Expected behavior:

- No prospect interest should be written until the property ambiguity is resolved, caller name is known, and interest is confirmed.
- If the caller never provides their name, capture should be rejected with missing name behavior and the assistant should ask for the name.

Failure signals:

- Assistant guesses Aurora Heights from vague wording.
- Assistant captures interest after turn 1, 2, or 5 without safe details.

## Scenario 4: Unknown Question, Graceful Refusal

Purpose: Verify the assistant does not invent facts outside the database or knowledge base.

Conversation:

| Turn | Caller says | Expected assistant behavior |
| ---: | --- | --- |
| 1 | Does Aurora Heights have a pool? | Search available property and KB data. Say the available information lists rooftop lounge, fitness room, controlled-entry lobby, package lockers, and elevator access, but does not mention a pool. Offer to have the leasing team confirm. |
| 2 | What school district is it in? | Say the current data does not include school district information. Do not guess. |
| 3 | Can I tour tomorrow at 3 PM? | Say the current data does not include tour scheduling availability. Offer to capture interest or have leasing follow up. |

Expected behavior:

- No invented amenity, school, or appointment information.
- No prospect capture unless caller explicitly asks for follow-up and provides required safe details.

Failure signals:

- Assistant claims there is a pool.
- Assistant names a school district.
- Assistant confirms a tour appointment without scheduling data.

## Scenario 5: Reserved Unit Handling

Purpose: Verify status is respected and the assistant does not present reserved units as available.

Conversation:

| Turn | Caller says | Expected assistant behavior |
| ---: | --- | --- |
| 1 | Tell me about Aurora Heights unit 2C. | Use structured data. State that unit 2C is a studio, one bath, $2,450, 510 sq ft, courtyard view, available date 2026-07-01, but status is reserved. |
| 2 | Can I rent that one? | Explain that it is currently reserved and offer to discuss available units such as 4B or 8A. |
| 3 | What is the cheapest available Aurora unit? | Compare available Aurora units. Answer unit 4B at $3,250 per month. |

Expected behavior:

- Unit 2C is never described as currently available.
- The assistant can still answer factual questions about 2C while making the reserved status clear.

Failure signals:

- Assistant captures interest in unit 2C without warning that it is reserved.
- Assistant says 2C is available because it has an availability date.

## Scenario 6: Missing Phone Metadata Blocks Capture

Purpose: Verify the safety gate blocks writes when caller phone metadata is missing.

Preconditions:

- Start a test call/session without caller phone metadata.

Conversation:

| Turn | Caller says | Expected assistant behavior |
| ---: | --- | --- |
| 1 | I am interested in Aurora Heights unit 8A. | Resolve unit 8A and ask for caller name if missing. |
| 2 | My name is Jordan Patel. Please have someone call me. | Capture attempt should be rejected because phone metadata is missing. Assistant should ask for the best callback number. |
| 3 | It is 415-555-8888. | After collecting the phone number, confirm interest and retry capture if the implementation supports setting caller phone from the conversation. |

Expected behavior:

- No write occurs while `missing_phone` applies.
- Assistant asks only for the missing safe detail, not for all details again.

Failure signals:

- Prospect is written with an empty, fake, or guessed phone number.
- Assistant claims capture succeeded when the capture tool rejected it.

## Scenario 7: Existing Prospect Update, Idempotent Interest

Purpose: Verify repeated calls from the same phone update the prospect rather than duplicating the person, and repeated interest capture is idempotent for the same target.

Preconditions:

- First complete Scenario 1 with phone `+14155551212` and name `Sam Rivera`.
- Start a second call from the same phone number.

Conversation:

| Turn | Caller says | Expected assistant behavior |
| ---: | --- | --- |
| 1 | This is Sam Rivera again. I am still interested in Aurora Heights 8A. | Resolve existing prospect by phone, refresh name if needed, and resolve unit 8A. |
| 2 | Yes, keep me on the list for that unit. | Capture should not create a duplicate prospect or duplicate unit interest. |

Expected write result:

- One prospect record for `+14155551212`.
- One interest row for unit 8A for that prospect.
- Capture result may indicate an existing interest rather than a newly created one.

Failure signals:

- Duplicate prospect rows for the same normalized phone.
- Duplicate interest rows for the same prospect and unit.

## Scenario 8: Cross-Property Policy Differences

Purpose: Verify that property-specific policies are not mixed between Aurora Heights and Pine Garden Flats.

Conversation:

| Turn | Caller says | Expected assistant behavior |
| ---: | --- | --- |
| 1 | Compare parking at Aurora Heights and Pine Garden Flats. | State Aurora Heights offers garage parking for $275/month. State Pine Garden Flats includes one surface parking space with each lease. |
| 2 | Which one allows two pets? | Aurora Heights allows up to two pets per home. Pine Garden Flats allows one cat or dog per home. Mention restrictions or current pet charges should be confirmed. |
| 3 | Which has 12 month leases? | Both: Aurora includes 9, 12, and 15 month terms; Pine offers 12 month terms. |

Expected behavior:

- The assistant keeps property-specific facts separated.
- The assistant does not answer with the general FAQ if a more specific property policy is available.

Failure signals:

- Assistant says Pine Garden Flats parking costs $275/month.
- Assistant says Pine Garden Flats allows two pets.

## Scenario 9: Natural Closing Without Capture

Purpose: Verify the assistant can close politely without writing anything when the caller only asks informational questions.

Conversation:

| Turn | Caller says | Expected assistant behavior |
| ---: | --- | --- |
| 1 | What is the application process? | Answer from general FAQ: apply online after choosing a home or community; application asks for contact, rental history, income info, and consent for screening; leasing specialist follows up if anything is missing. |
| 2 | What are the deposits? | Ask which community if needed, then provide Aurora $750 and Pine $500 if the caller wants both. |
| 3 | Thanks, that is all. | Close politely and briefly. |

Expected behavior:

- No prospect capture occurs.
- Assistant does not pressure for contact details unless caller asks for follow-up or shows interest.

Failure signals:

- Assistant creates a prospect interest from informational questions alone.
- Assistant keeps asking for personal information after the caller ends the conversation.

## Manual Test Checklist

Before the call:

- Seed the database.
- Start the LiveKit worker with provider credentials.
- Confirm SIP metadata includes caller phone number for capture-positive cases.

During the call:

- Ask at least one structured-data question: rent, bedrooms, availability, status, view, parking.
- Ask at least one knowledge-base question: application process, fees, deposits, amenities, pet policy, lease terms.
- Ask at least one unknown question to test graceful fallback.
- Attempt capture only after explicit caller interest.

After the call:

- Verify the assistant did not invent facts.
- Verify the assistant asked clarification questions for ambiguous wording.
- Verify the database contains the expected prospect and interest rows for capture-positive scenarios.
- Verify no write occurred for capture-negative scenarios.
- Record any latency, interruption, or unnatural-response issues for follow-up tuning.

## Suggested Evaluation Notes

For each run, record:

- Scenario name
- Date and tester
- Phone metadata present: yes/no
- Final resolved target
- Whether capture was attempted
- Capture result: captured/rejected/not attempted
- Rejection reason, if any
- Incorrect or invented facts
- Missed clarification opportunities
- Voice quality notes
- Latency notes
- Overall pass/fail
