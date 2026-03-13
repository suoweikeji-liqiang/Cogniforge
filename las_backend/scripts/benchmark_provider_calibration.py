#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
import statistics
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / "las_backend" / "scripts" / "benchmark_openrouter_models.py"
_spec = importlib.util.spec_from_file_location("provider_calibration_benchmark_base", MODULE_PATH)
if _spec is None or _spec.loader is None:
    raise RuntimeError(f"Unable to load benchmark module from {MODULE_PATH}")
bench = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = bench
_spec.loader.exec_module(bench)


@dataclass
class Candidate:
    key: str
    label: str
    base_url: str
    api_key: str
    model: str
    extra_payload: Dict[str, Any] = field(default_factory=dict)


def request_json(url: str, payload: Dict[str, Any], api_key: str, timeout: int = 90) -> Dict[str, Any]:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/suoweikeji-liqiang/Cogniforge",
            "X-Title": "Cogniforge Provider Calibration",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def call_candidate(candidate: Candidate, prompt: str, temperature: float, max_tokens: int, response_format: Dict[str, Any] | None) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "model": candidate.model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if response_format:
        payload["response_format"] = response_format
    payload.update(candidate.extra_payload)

    started = time.perf_counter()
    body = request_json(f"{candidate.base_url.rstrip('/')}/chat/completions", payload, candidate.api_key)
    latency = time.perf_counter() - started
    text = bench.extract_message_text(body)
    return {
        "latency_s": round(latency, 3),
        "response": body,
        "text": text,
        "usage": body.get("usage") or {},
    }


def run_candidate_call(candidate: Candidate, spec) -> Dict[str, Any]:
    total_latency = 0.0
    total_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    schema_used = False
    fallback_used = False
    schema_error = None
    error = None
    raw_text = ""
    parsed: Any = None

    def add_usage(usage: Dict[str, Any]):
        for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
            total_usage[key] += int(usage.get(key) or 0)

    try:
        if spec.schema and spec.schema_name:
            response_format = {
                "type": "json_schema",
                "json_schema": {
                    "name": spec.schema_name,
                    "schema": spec.schema,
                    "strict": True,
                },
            }
            try:
                result = call_candidate(candidate, spec.prompt, spec.temperature, spec.max_tokens, response_format)
                total_latency += result["latency_s"]
                add_usage(result["usage"])
                raw_text = result["text"]
                parsed = bench.parse_structured_output(spec, raw_text)
                schema_used = parsed is not None
                if parsed is None:
                    fallback_used = True
            except Exception as exc:
                schema_error = str(exc)
                fallback_used = True

        if parsed is None:
            result = call_candidate(candidate, spec.prompt, spec.temperature, spec.max_tokens, None)
            total_latency += result["latency_s"]
            add_usage(result["usage"])
            raw_text = result["text"]
            if spec.category in {"concept_extraction", "learning_path", "structured_feedback"}:
                parsed = bench.parse_structured_output(spec, raw_text)
            else:
                parsed = str(raw_text or "").strip()
    except Exception as exc:
        error = str(exc)

    return {
        "raw_text": raw_text,
        "parsed": parsed,
        "latency_s": round(total_latency, 3),
        "usage": total_usage,
        "schema_used": schema_used,
        "fallback_used": fallback_used,
        "schema_error": schema_error,
        "error": error,
    }


def p50(values: List[float]) -> float:
    return statistics.median(values) if values else 0.0


def p90(values: List[float]) -> float:
    if not values:
        return 0.0
    values = sorted(values)
    idx = max(0, min(len(values) - 1, int((len(values) - 1) * 0.9)))
    return values[idx]


def build_weighted_summary(results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    models = sorted({row["model"] for row in results})
    summary: List[Dict[str, Any]] = []
    for model in models:
        rows = [row for row in results if row["model"] == model]

        def avg(title: str) -> float:
            vals = [row["evaluation"]["deterministic_score"] for row in rows if row["spec"]["title"] == title]
            return statistics.mean(vals)

        def lats(title: str) -> List[float]:
            return [row["candidate"]["latency_s"] for row in rows if row["spec"]["title"] == title]

        exploration_quality = 0.75 * statistics.mean([avg("Exploration Answer EN"), avg("Exploration Answer ZH")]) + 0.25 * statistics.mean([avg("Concept Extraction EN"), avg("Concept Extraction ZH")])
        socratic_quality = 0.30 * statistics.mean([avg("Socratic Question EN"), avg("Socratic Question ZH")]) + 0.50 * statistics.mean([avg("Structured Feedback EN"), avg("Structured Feedback ZH")]) + 0.20 * statistics.mean([avg("Concept Extraction EN"), avg("Concept Extraction ZH")])
        path_quality = avg("Learning Path EN")
        overall_quality = 0.45 * exploration_quality + 0.45 * socratic_quality + 0.10 * path_quality

        exploration_turn = [a + b for a, b in zip(lats("Exploration Answer EN"), lats("Concept Extraction EN"))] + [a + b for a, b in zip(lats("Exploration Answer ZH"), lats("Concept Extraction ZH"))]
        socratic_cycle = [a + b + c for a, b, c in zip(lats("Socratic Question EN"), lats("Structured Feedback EN"), lats("Concept Extraction EN"))] + [a + b + c for a, b, c in zip(lats("Socratic Question ZH"), lats("Structured Feedback ZH"), lats("Concept Extraction ZH"))]
        path_lats = lats("Learning Path EN")

        schema_rows = [row for row in rows if row["spec"]["schema"]]
        schema_success = sum(1 for row in schema_rows if row["candidate"]["schema_used"]) / len(schema_rows) * 100.0
        fallback_rate = sum(1 for row in schema_rows if row["candidate"]["fallback_used"]) / len(schema_rows) * 100.0

        summary.append(
            {
                "model": model,
                "overall_quality_weighted": round(overall_quality, 2),
                "exploration_quality": round(exploration_quality, 2),
                "socratic_quality": round(socratic_quality, 2),
                "path_quality": round(path_quality, 2),
                "exploration_p50_s": round(p50(exploration_turn), 3),
                "exploration_p90_s": round(p90(exploration_turn), 3),
                "socratic_p50_s": round(p50(socratic_cycle), 3),
                "socratic_p90_s": round(p90(socratic_cycle), 3),
                "path_p50_s": round(p50(path_lats), 3),
                "schema_success_pct": round(schema_success, 1),
                "fallback_pct": round(fallback_rate, 1),
            }
        )
    return sorted(summary, key=lambda row: row["overall_quality_weighted"], reverse=True)


def write_report(report_path: Path, summary: List[Dict[str, Any]], raw_path: Path):
    lines = [
        "# DeepSeek Provider Calibration Benchmark",
        "",
        f"- Generated at: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}",
        "- Purpose: isolate provider effects by testing official DeepSeek and DashScope directly, without OpenRouter routing on the candidate models.",
        f"- Raw results: `{raw_path}`",
        "",
        "## Weighted Results",
        "",
        "| Model | Weighted Quality | Exploration p50 | Exploration p90 | Socratic p50 | Socratic p90 | Path p50 | Native Schema Success | Fallback |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in summary:
        lines.append(
            f"| `{row['model']}` | {row['overall_quality_weighted']:.2f} | {row['exploration_p50_s']:.3f}s | {row['exploration_p90_s']:.3f}s | {row['socratic_p50_s']:.3f}s | {row['socratic_p90_s']:.3f}s | {row['path_p50_s']:.3f}s | {row['schema_success_pct']:.1f}% | {row['fallback_pct']:.1f}% |"
        )
    lines.extend(
        [
            "",
            "## Decision",
            "",
            f"- Best default candidate from this provider-isolated run: `{summary[0]['model']}`" if summary else "- No results",
            "- Use the weighted table together with latency spread, not only content score, because Cogniforge is a turn-based interactive product.",
        ]
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Provider-isolated benchmark for DeepSeek/Qwen candidates.")
    parser.add_argument("--candidates", nargs="*", default=[])
    args = parser.parse_args()

    provider_env = bench.load_env(REPO_ROOT / "tesdeepseek.env")
    judge_env = bench.load_env(REPO_ROOT / "testllm.env")
    judge_key = judge_env.get("API_KEY") or judge_env.get("OPENROUTER_API_KEY")
    judge_base = judge_env.get("BASE_URL") or "https://openrouter.ai/api/v1"

    candidates = [
        Candidate(
            key="deepseek-official/deepseek-chat",
            label="DeepSeek Official",
            base_url="https://api.deepseek.com",
            api_key=provider_env["DEEPSEEK_API_KEY"],
            model="deepseek-chat",
        ),
        Candidate(
            key="dashscope/deepseek-v3.2",
            label="DashScope DeepSeek",
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            api_key=provider_env["QWEN_API_KEY"],
            model="deepseek-v3.2",
            extra_payload={"enable_thinking": False},
        ),
        Candidate(
            key="dashscope/qwen3.5-plus",
            label="DashScope Qwen",
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            api_key=provider_env["QWEN_API_KEY"],
            model="qwen3.5-plus",
        ),
        Candidate(
            key="openrouter/google/gemini-3.1-flash-lite-preview",
            label="OpenRouter Gemini 3.1 Flash Lite Preview",
            base_url=judge_env.get("BASE_URL") or "https://openrouter.ai/api/v1",
            api_key=judge_key,
            model="google/gemini-3.1-flash-lite-preview",
        ),
    ]
    if args.candidates:
        selected = set(args.candidates)
        candidates = [candidate for candidate in candidates if candidate.key in selected]
        if not candidates:
            raise SystemExit("No candidates matched --candidates.")

    specs = bench.scenario_specs()
    rounds = 5
    results: List[Dict[str, Any]] = []
    total = len(candidates) * len(specs) * rounds
    current = 0

    for candidate in candidates:
        print(f"\n=== Candidate: {candidate.key} ===")
        for round_index in range(1, rounds + 1):
            for spec in specs:
                current += 1
                print(f"[{current}/{total}] {candidate.key} | round {round_index} | {spec.title}")
                candidate_result = run_candidate_call(candidate, spec)
                evaluation = bench.evaluate_result(spec, candidate_result)
                judge = None
                if round_index == 1 and not candidate_result.get("error"):
                    try:
                        judge = bench.judge_output(
                            base_url=judge_base,
                            api_key=judge_key,
                            judge_model="openai/gpt-5.4",
                            spec=spec,
                            candidate=candidate_result,
                        )
                    except Exception as exc:
                        judge = {"error": str(exc)}
                results.append(
                    {
                        "model": candidate.key,
                        "round": round_index,
                        "spec": {
                            "title": spec.title,
                            "category": spec.category,
                            "language": spec.language,
                            "schema": bool(spec.schema),
                        },
                        "candidate": candidate_result,
                        "evaluation": evaluation,
                        "judge": judge,
                    }
                )

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_dir = REPO_ROOT / "output" / "provider-calibration" / timestamp
    output_dir.mkdir(parents=True, exist_ok=True)
    raw_path = output_dir / "results.json"
    raw_path.write_text(json.dumps({"results": results}, ensure_ascii=False, indent=2), encoding="utf-8")

    summary = build_weighted_summary(results)
    report_path = REPO_ROOT / "docs" / "reports" / f"provider-calibration-{timestamp}.md"
    write_report(report_path, summary, raw_path)

    print("")
    print(f"Raw results: {raw_path}")
    print(f"Report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
