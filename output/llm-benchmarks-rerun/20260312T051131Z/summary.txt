# Cogniforge OpenRouter LLM Benchmark Report

- Generated at: 2026-03-12 05:17:33 UTC
- Candidate models tested: 2
- Rounds per scenario: 2
- Judge model: `openai/gpt-5.4`
- Benchmark focus: Cogniforge-specific Exploration, Socratic, concept extraction, learning-path JSON, and structured feedback.

## Executive Summary

- Primary recommendation: `openai/gpt-4.1-mini`
  - Why: highest combined score on quality and latency (`overall=88.63`, `quality=90.89`, `median_latency=3.003s`).
  - Main strengths: Accurately explains how lowering and raising the threshold affect precision, recall, false positives, and false negatives., Builds logically from prior knowledge (precision/recall, thresholds) toward deployment-oriented threshold decisions., Connects threshold movement to precision in a concrete, pedagogically useful way.
  - Main risks: Could be more concrete about risky code alerts and operational triage workflows earlier in the path., Could be slightly more explicitly tied to code review triage decision-making, though the current example already strongly suggests it., Dimension scores and mastery_score are all 0, which does not fit the expected scoring range and underrepresents the learner's partial understanding.
- Fastest viable model: `openai/gpt-4.1-mini` (`median_latency=3.003s`, `quality=90.89`).
- Lowest estimated interaction cost: `stepfun/step-3.5-flash:free` (`exploration≈$0.0`, `socratic-cycle≈$0.0`).

## Ranking

| Rank | Model | Overall | Quality | Speed | Median Latency (s) | Schema Success | Exploration Est. ($) | Socratic Cycle Est. ($) |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | `openai/gpt-4.1-mini` | 88.63 | 90.89 | 100.01 | 3.003 | 40.0% | 0.00053 | 0.00095 |
| 2 | `stepfun/step-3.5-flash:free` | 46.54 | 59.34 | 0.00 | 11.189 | 0.0% | 0.00000 | 0.00000 |

## Scenario Winners

- `Exploration Answer EN`: `openai/gpt-4.1-mini` (97.50), `stepfun/step-3.5-flash:free` (97.50)
- `Exploration Answer ZH`: `openai/gpt-4.1-mini` (94.17), `stepfun/step-3.5-flash:free` (91.25)
- `Concept Extraction EN`: `openai/gpt-4.1-mini` (94.00), `stepfun/step-3.5-flash:free` (67.00)
- `Concept Extraction ZH`: `openai/gpt-4.1-mini` (94.00), `stepfun/step-3.5-flash:free` (20.00)
- `Learning Path EN`: `openai/gpt-4.1-mini` (87.00), `stepfun/step-3.5-flash:free` (58.50)
- `Socratic Question EN`: `openai/gpt-4.1-mini` (96.88), `stepfun/step-3.5-flash:free` (93.75)
- `Socratic Question ZH`: `openai/gpt-4.1-mini` (77.75), `stepfun/step-3.5-flash:free` (71.50)
- `Structured Feedback EN`: `openai/gpt-4.1-mini` (97.00), `stepfun/step-3.5-flash:free` (35.00)
- `Structured Feedback ZH`: `openai/gpt-4.1-mini` (95.00), `stepfun/step-3.5-flash:free` (25.00)

## Model Notes

### `openai/gpt-4.1-mini`
- Overall: 88.63
- Quality: 90.89 (deterministic 92.59, judge 88.33)
- Median latency: 3.003s
- Structured-output success: 40.0%
- Fallback rate: 60.0%
- Benchmark spend in this run: $0.0081
- Estimated exploration turn cost: $0.00053
- Estimated Socratic cycle cost: $0.00095
- Strengths: Accurately explains how lowering and raising the threshold affect precision, recall, false positives, and false negatives., Builds logically from prior knowledge (precision/recall, thresholds) toward deployment-oriented threshold decisions., Connects threshold movement to precision in a concrete, pedagogically useful way.
- Risks: Could be more concrete about risky code alerts and operational triage workflows earlier in the path., Could be slightly more explicitly tied to code review triage decision-making, though the current example already strongly suggests it., Dimension scores and mastery_score are all 0, which does not fit the expected scoring range and underrepresents the learner's partial understanding.

### `stepfun/step-3.5-flash:free`
- Overall: 46.54
- Quality: 59.34 (deterministic 62.17, judge 55.11)
- Median latency: 11.189s
- Structured-output success: 0.0%
- Fallback rate: 100.0%
- Benchmark spend in this run: $0.0000
- Estimated exploration turn cost: $0.00000
- Estimated Socratic cycle cost: $0.00000
- Strengths: Accurately explains the threshold tradeoff between precision and recall, including effects on false positives and false negatives., Asks exactly one concise Socratic probe question., Builds logically from the learner’s stated prior knowledge toward deployment decisions, matching a real learning workflow.
- Risks: Cannot be placed in a learning workflow because it contains no extractable concepts., Could be slightly more explicit that raising the threshold increases false negatives and lowering it increases false positives in one compact contrast sentence, though this is already implied clearly., Does not follow the required exact JSON shape to completion.

## Recommendation Logic

- Overall score weighting: quality 70%, speed 25%, price 5%.
- Quality blends deterministic protocol checks (60%) and one-round judge scoring (40%).
- Price is intentionally a small factor because this project values answer quality and latency first.
