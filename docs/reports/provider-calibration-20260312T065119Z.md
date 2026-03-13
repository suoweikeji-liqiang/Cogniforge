# DeepSeek Provider Calibration Benchmark

- Generated at: 2026-03-12 06:51:19 UTC
- Purpose: isolate provider effects by testing official DeepSeek and DashScope directly, without OpenRouter routing on the candidate models.
- Raw results: `/Users/asteroida/work/Cogniforge/output/provider-calibration/20260312T065119Z/results.json`

## Weighted Results

| Model | Weighted Quality | Exploration p50 | Exploration p90 | Socratic p50 | Socratic p90 | Path p50 | Native Schema Success | Fallback |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `dashscope/deepseek-v3.2` | 93.83 | 10.383s | 13.879s | 15.638s | 18.966s | 29.597s | 96.0% | 4.0% |
| `deepseek-official/deepseek-chat` | 91.28 | 10.251s | 12.258s | 16.148s | 16.823s | 26.391s | 0.0% | 100.0% |

## Decision

- Best default candidate from this provider-isolated run: `dashscope/deepseek-v3.2`
- Use the weighted table together with latency spread, not only content score, because Cogniforge is a turn-based interactive product.
