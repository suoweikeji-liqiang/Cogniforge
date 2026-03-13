# DeepSeek Provider Calibration Benchmark

- Generated at: 2026-03-12 07:04:56 UTC
- Purpose: isolate provider effects by testing official DeepSeek and DashScope directly, without OpenRouter routing on the candidate models.
- Raw results: `/Users/asteroida/work/Cogniforge/output/provider-calibration/20260312T070456Z/results.json`

## Weighted Results

| Model | Weighted Quality | Exploration p50 | Exploration p90 | Socratic p50 | Socratic p90 | Path p50 | Native Schema Success | Fallback |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `openrouter/google/gemini-3.1-flash-lite-preview` | 93.17 | 4.919s | 5.205s | 6.886s | 7.293s | 3.604s | 100.0% | 0.0% |

## Decision

- Best default candidate from this provider-isolated run: `openrouter/google/gemini-3.1-flash-lite-preview`
- Use the weighted table together with latency spread, not only content score, because Cogniforge is a turn-based interactive product.
