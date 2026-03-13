# Cogniforge LLM Benchmark Analysis

## Scope

This analysis interprets the corrected benchmark runs generated from:

- `/Users/asteroida/work/Cogniforge/docs/reports/llm-benchmark-openrouter-20260312T051131Z-merged.md`
- `/Users/asteroida/work/Cogniforge/output/llm-benchmarks-merged/20260312T051131Z/results.json`

The benchmark was aligned to Cogniforge's actual workflow requirements:

- Exploration answer quality
- Bilingual concept extraction
- Learning path JSON generation
- Socratic question generation
- Structured feedback generation

Each model was run for 2 rounds per scenario. Judge scoring used `openai/gpt-5.4` on round 1 only.

## Important Correction

The first full run incorrectly treated some provider-side `json_schema` rejections as terminal errors. That was fixed and the affected models were rerun:

- `openai/gpt-4.1-mini`
- `stepfun/step-3.5-flash:free`

This final analysis only uses the merged, corrected result set.

## Recommendation

### Recommended primary model

`google/gemini-3.1-flash-lite-preview`

Reason:

- It is the fastest strong model in the final run.
- It kept `100%` native structured-output success.
- It did not require fallback for the structured tasks that matter most to Cogniforge.
- Its quality score is effectively tied with `openai/gpt-4.1-mini` in practical terms.

Why not blindly choose `openai/gpt-4.1-mini` even though the formula ranked it slightly above?

- The final overall difference is negligible.
- `gpt-4.1-mini` required fallback on `60%` of structured tasks in this benchmark because the provider rejected array-schema requests.
- Cogniforge is not a generic chat app. It is a structured learning product. Native protocol fit matters.
- A model that is slightly worse on abstract aggregate score but materially better on native structured compatibility is the safer production default.

### Recommended secondary model

`openai/gpt-4.1-mini`

Use it if:

- you want a very strong general-purpose fallback for English-heavy traffic
- you can tolerate the structured-output fallback path
- you value slightly stronger feedback quality over native schema compatibility

This model recovered strongly after the benchmark fix and is still a top-tier choice.

### Best English Socratic / analysis model

`deepseek/deepseek-v3.2`

Why it stands out:

- very strong English Socratic questioning
- strong exploration quality
- low cost

Why it is not my default primary recommendation:

- noticeably slower than the top Gemini options
- not clearly better enough to justify the latency tradeoff for the main workspace

### Best Chinese-quality model

`qwen/qwen3.5-flash-02-23`

Why it stands out:

- strongest Chinese concept extraction / Socratic / structured behavior in this run
- excellent overall quality

Why it is not my default primary recommendation:

- too slow for mainline interactive flow
- materially more expensive in benchmark-estimated interaction cost than the stronger practical defaults

### Best free fallback

`arcee-ai/trinity-large-preview:free`

Why:

- much higher quality than `stepfun/step-3.5-flash:free`
- `100%` structured-output success in this benchmark

Tradeoff:

- slower than paid fast models

### Free model to avoid as main fallback

`stepfun/step-3.5-flash:free`

Why:

- native structured output support was effectively absent in this benchmark
- fallback worked, but content quality for structured learning artifacts was still too weak

## Practical Selection Matrix

### If you want one default model now

Choose `google/gemini-3.1-flash-lite-preview`.

### If you want a two-model production setup

Use:

1. `google/gemini-3.1-flash-lite-preview` as the default mainline model
2. `openai/gpt-4.1-mini` as a selective fallback for higher-stakes explanation / feedback turns

### If you want a three-model setup

Use:

1. `google/gemini-3.1-flash-lite-preview` for default traffic
2. `openai/gpt-4.1-mini` for premium fallback or retry
3. `qwen/qwen3.5-flash-02-23` only for Chinese-first premium flows if latency is acceptable

## Models That Look Good But Are Hard To Justify

### `moonshotai/kimi-k2.5`

- quality is good
- latency is too high
- estimated interaction cost is too high

This is difficult to justify for a turn-by-turn learning workspace.

### `minimax/minimax-m2.5`

- good quality
- no fatal protocol issues
- not fast enough to beat Gemini
- not strong enough to beat the slower premium-quality specialists

This ends up in the middle without a clean reason to pick it first.

## Suggested Next Step

Do one production-like A/B after this benchmark:

1. `google/gemini-3.1-flash-lite-preview`
2. `openai/gpt-4.1-mini`
3. optionally `deepseek/deepseek-v3.2`

Measure on real traffic:

- time to first useful turn completion
- concept candidate cleanliness after moderation
- Socratic feedback usefulness
- Chinese localization quality in the live product path

If the live A/B is consistent with this offline benchmark, choose:

- `gemini-3.1-flash-lite-preview` as the primary model
- `gpt-4.1-mini` as the secondary fallback
