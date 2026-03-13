# Cogniforge Shortlist A/B Benchmark

## Scope

This second-round benchmark focused only on the 3 realistic finalists:

- `google/gemini-3.1-flash-lite-preview`
- `openai/gpt-4.1-mini`
- `deepseek/deepseek-v3.2`

Run settings:

- 5 rounds per scenario
- scenarios aligned to Cogniforge's actual learning protocol
- analysis weighted by turn type rather than equal-weighting all scenarios

Source artifacts:

- Raw results: `/Users/asteroida/work/Cogniforge/output/llm-benchmarks-shortlist/20260312T053300Z/results.json`
- Machine report: `/Users/asteroida/work/Cogniforge/docs/reports/llm-benchmark-openrouter-20260312T053300Z.md`

## Traffic-Weighted Method

To get closer to real product traffic, I treated the benchmark as 3 product-level workloads:

1. `exploration turn`
   - 75% exploration answer quality
   - 25% concept extraction quality
2. `socratic cycle`
   - 30% Socratic question quality
   - 50% structured feedback quality
   - 20% concept extraction quality
3. `learning path`
   - 100% learning-path generation quality

Overall workflow weighting:

- 45% exploration turn
- 45% Socratic cycle
- 10% learning path

Latency was analyzed at turn level:

- exploration turn latency = `exploration answer + concept extraction`
- Socratic cycle latency = `socratic question + structured feedback + concept extraction`
- learning path latency = `learning path`

## Results

| Model | Weighted Quality | Exploration p50 | Exploration p90 | Socratic p50 | Socratic p90 | Path p50 | Native Schema Success | Fallback Rate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `deepseek/deepseek-v3.2` | 94.72 | 14.040s | 22.291s | 21.447s | 30.247s | 26.569s | 96% | 4% |
| `openai/gpt-4.1-mini` | 93.93 | 5.662s | 6.709s | 8.601s | 10.265s | 14.595s | 40% | 60% |
| `google/gemini-3.1-flash-lite-preview` | 93.01 | 4.217s | 4.508s | 5.739s | 6.620s | 3.223s | 100% | 0% |

## Interpretation

### `deepseek/deepseek-v3.2`

What it does well:

- strongest weighted content quality in this shortlist
- very strong English exploration and Socratic behavior
- native structured behavior is mostly fine

Why it is not the default choice:

- too slow for the main ProblemDetail loop
- Socratic cycle p50 above 21 seconds is not acceptable for the default teacher-student interaction
- even if quality is highest, the latency gap is too large

Conclusion:

- do not use as the main default model
- keep only if you later want a selective premium route for slower, higher-quality reasoning

### `openai/gpt-4.1-mini`

What it does well:

- very strong weighted quality
- best shortlist performance on structured feedback and strong bilingual Socratic behavior
- latency is still workable for a primary or premium fallback role

What blocks it from becoming the default:

- native schema compatibility is weak in this setup
- `60%` of structured tasks required fallback
- the product can tolerate fallback, but Cogniforge is a structured learning system, so this is real engineering friction

Conclusion:

- excellent secondary model
- strong fallback for higher-quality explanations and evaluations
- viable primary only if you are willing to accept the schema/fallback complexity

### `google/gemini-3.1-flash-lite-preview`

What it does well:

- fastest model in the shortlist by a wide margin
- very low p50/p90 spread, which matters for turn-by-turn learning flow
- `100%` native schema success
- quality remains close enough to `gpt-4.1-mini` that the speed/stability advantage wins

Main weakness:

- Socratic quality, especially Chinese Socratic, is not as strong as the best alternative
- structured feedback is good enough, but not the strongest in the shortlist

Conclusion:

- best default mainline model for Cogniforge right now

## Final Recommendation

### Primary model

`google/gemini-3.1-flash-lite-preview`

Reason:

- best balance of quality, latency, and native protocol fit
- safest choice for the main ProblemDetail workflow

### Secondary fallback

`openai/gpt-4.1-mini`

Reason:

- better pedagogical quality in several evaluation-heavy tasks
- still fast enough to serve as a premium fallback
- should not be the first default while schema compatibility remains fallback-heavy

### Do not use as default

`deepseek/deepseek-v3.2`

Reason:

- quality is high
- latency is too slow for the main interactive loop

## Routing Strategy Suggestion

If you want to operationalize this result directly, the cleanest next step is:

1. default all mainline requests to `google/gemini-3.1-flash-lite-preview`
2. retry or escalate selected turns to `openai/gpt-4.1-mini`
3. do not put `deepseek/deepseek-v3.2` on the default user path unless you explicitly design a slower premium mode
