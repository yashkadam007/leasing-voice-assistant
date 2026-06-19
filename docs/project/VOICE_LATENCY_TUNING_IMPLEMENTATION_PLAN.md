# Voice Latency Improvement Plan

## Baseline

- Overall E2E: 3,410 ms p50, 5,916 ms p90
- Tool-turn E2E: 5,251 ms p50
- Non-tool E2E: 2,918 ms p50
- End-of-turn delay: 1,887 ms p50

Full results are in `docs/project/VOICE_EXPERIENCE_IMPROVEMENT_PLAN.md`.

## Ranked Issues

### 1. Tool Orchestration Latency

**Status: Implemented.**

ADR 0007 implements bounded pre-LLM grounding for read turns, exposes only the guarded prospect
capture tool in hybrid mode, and records grounding and LLM phase metrics. Matched-call acceptance
measurement remains pending.

### 2. End-of-Turn Delay

**Status: Implemented.**

This is a small configuration fix in `src/leasing_voice_assistant/worker/main.py`:

```python
min_endpointing_delay_seconds: float = 0.5
max_endpointing_delay_seconds: float = 1.0
```

Update the expected values in `tests/test_worker_import.py`. Re-test hesitations and natural pauses
for premature endpointing.

### 3. Long Tool Responses

**Status: Implemented.**

Tool responses have a 13.11-second median speaking duration. This is a small prompt fix in
`src/leasing_voice_assistant/worker/prompts.py`: require the requested fact plus one useful detail,
then a short follow-up question. Update `tests/test_worker_prompts.py`.

### 4. LLM Latency

**Status: Implemented.**

LLM TTFT is 884 ms p50 and 1,581 ms p95 in the twenty-call baseline. Keep this issue scoped to a
simple direct OpenAI model change: set `OPENAI_MODEL=gpt-4.1-mini` in the deployment environment
while preserving the LiveKit and Deepgram pipeline. The model switch is implemented; its latency
and naturalness effect remains pending matched-call validation and is not claimed as a measured
improvement.

### 5. TTS Startup Latency

Normal TTS startup is several hundred milliseconds. Evaluate provider and model comparisons after
the higher-priority latency work is measured.

### 6. False Interruptions

This is a small configuration fix in `src/leasing_voice_assistant/worker/main.py`:

```python
min_interruption_words: int = 1
```

Update `tests/test_worker_import.py`. Verify that one-word barge-ins such as "wait" and "no" still
work.

### 7. Metrics Classification

The reporter mixes greetings, user-response turns, and assistant continuations. This is a small
reporting fix in `src/leasing_voice_assistant/worker/metrics.py`: classify and summarize these record
types separately, with focused metrics tests.

## Order

1. End-of-turn delay
2. False interruptions
3. Long tool responses
4. Metrics classification
5. Tool orchestration investigation
6. LLM model switch
7. TTS comparison

Run formatting, linting, and tests after every fix. Measure a matched call batch before starting the
next issue so latency changes remain attributable.
