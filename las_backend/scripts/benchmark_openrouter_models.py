#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
import math
import os
import statistics
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPO_ROOT / "las_backend"
STRUCTURED_SUPPORT_PATH = BACKEND_ROOT / "app" / "services" / "model_os_structured_support.py"
_structured_spec = importlib.util.spec_from_file_location("benchmark_structured_support", STRUCTURED_SUPPORT_PATH)
if _structured_spec is None or _structured_spec.loader is None:
    raise RuntimeError(f"Unable to load structured support module from {STRUCTURED_SUPPORT_PATH}")
structured_support = importlib.util.module_from_spec(_structured_spec)
_structured_spec.loader.exec_module(structured_support)


DEFAULT_MODELS = [
    "qwen/qwen3.5-flash-02-23",
    "deepseek/deepseek-v3.2",
    "minimax/minimax-m2.5",
    "google/gemini-3.1-flash-lite-preview",
    "moonshotai/kimi-k2.5",
    "stepfun/step-3.5-flash:free",
    "arcee-ai/trinity-large-preview:free",
    "openai/gpt-4.1-mini",
    "google/gemini-2.5-flash",
]
DEFAULT_JUDGE_MODEL = "openai/gpt-5.4"


@dataclass
class PromptSpec:
    category: str
    language: str
    title: str
    prompt: str
    temperature: float
    schema: Optional[Dict[str, Any]] = None
    schema_name: Optional[str] = None
    max_tokens: int = 1600
    expected: Optional[Dict[str, Any]] = None


def load_env(path: Path) -> Dict[str, str]:
    env: Dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key.strip()] = value.strip()
    return env


def request_json(
    *,
    url: str,
    payload: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
    timeout: int = 60,
    retries: int = 2,
) -> Dict[str, Any]:
    data = None
    req_headers = {"Content-Type": "application/json"}
    if headers:
        req_headers.update(headers)
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")

    last_error: Optional[str] = None
    for attempt in range(retries + 1):
        try:
            request = urllib.request.Request(url, data=data, headers=req_headers, method="POST" if payload is not None else "GET")
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            last_error = f"HTTP {exc.code}: {body[:800]}"
            if exc.code in {429, 500, 502, 503, 504} and attempt < retries:
                time.sleep(1.5 * (attempt + 1))
                continue
            raise RuntimeError(last_error) from exc
        except Exception as exc:  # pragma: no cover - network/runtime variance
            last_error = str(exc)
            if attempt < retries:
                time.sleep(1.5 * (attempt + 1))
                continue
            raise RuntimeError(last_error) from exc
    raise RuntimeError(last_error or "Unknown request failure")


def fetch_model_catalog(base_url: str, api_key: str) -> Dict[str, Dict[str, Any]]:
    data = request_json(
        url=f"{base_url.rstrip('/')}/models",
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=60,
    )
    return {item.get("id"): item for item in data.get("data", []) if item.get("id")}


def build_context_prompt(prompt: str, current_question: str, retrieval_context: str = "") -> str:
    retrieval_block = f"\nRelevant knowledge:\n{retrieval_context}\n" if retrieval_context else ""
    language_instruction = (
        "Language requirement: Use the current question as the source of truth for language. "
        "Respond in the same language as the current question. "
        "If the current question contains Chinese, respond in Simplified Chinese. "
        "If the current question does not contain Chinese, do not respond in Chinese even if other context does."
    )
    return (
        "Context:\n"
        f"user: {current_question}\n"
        f"{retrieval_block}\n"
        f"Current question: {prompt}\n\n"
        f"{language_instruction}"
    )


def prompt_exploration_en() -> PromptSpec:
    question = "What's the practical difference between precision and recall when tuning a classifier threshold for defect detection?"
    base_prompt = """The learner asked a question during a step-by-step learning flow.

Problem: Improve classifier threshold decisions for software defect detection
Problem description: The learner already knows binary classification basics and wants to tune a threshold for a defect detector used during code review triage.
Current step concept: Precision-recall tradeoff
Current step description: Explain how threshold changes alter false positives, false negatives, and the operational decision.

Answer directly and accurately. Keep structure: 1) concise definition, 2) key distinction, 3) one concrete example, 4) one common pitfall.
"""
    retrieval = """[Model Card] Defect Triage Thresholds
Notes: Lowering the threshold usually increases recall and false positives. Raising the threshold usually improves precision but can hide risky defects.
Examples: Security bug detector, flaky static analysis alert
Counter Examples: Perfect separation is rare in production"""
    return PromptSpec(
        category="exploration_answer",
        language="en",
        title="Exploration Answer EN",
        prompt=build_context_prompt(base_prompt, question, retrieval),
        temperature=0.7,
        expected={
            "keyword_groups": [
                ["precision"],
                ["recall"],
                ["threshold"],
                ["false positive", "false positives"],
                ["false negative", "false negatives"],
                ["example", "for example"],
                ["pitfall", "mistake", "common pitfall"],
            ],
            "structure_groups": [
                ["definition", "means", "is the share", "is about"],
                ["difference", "distinction", "tradeoff"],
                ["example", "for example"],
                ["pitfall", "mistake", "watch out"],
            ],
        },
    )


def prompt_exploration_zh() -> PromptSpec:
    question = "为什么积分项会导致超调？在什么情况下要做抗积分饱和？"
    base_prompt = """The learner asked a question during a step-by-step learning flow.

Problem: 理解 PID 控制中的积分饱和
Problem description: 学习者已经知道比例项和积分项的基本作用，现在要理解积分项为什么会在执行器受限时带来问题。
Current step concept: 积分饱和（integral windup）
Current step description: 解释积分累积、执行器饱和、超调与 anti-windup 的关系。

Use guided style. First give a short hint, then one mini-example, and end with one focused check question.
"""
    retrieval = """[Model Card] PID 控制
Notes: 当执行器达到上限而误差仍持续存在时，积分项会继续累积，解除饱和后容易导致过冲。
Examples: 电机驱动饱和，温控系统加热功率上限
Counter Examples: 执行器没有饱和时，积分项有助于消除稳态误差"""
    return PromptSpec(
        category="exploration_answer",
        language="zh",
        title="Exploration Answer ZH",
        prompt=build_context_prompt(base_prompt, question, retrieval),
        temperature=0.7,
        expected={
            "keyword_groups": [
                ["积分", "积分项"],
                ["超调", "过冲"],
                ["饱和", "执行器饱和"],
                ["抗积分饱和", "anti-windup"],
                ["例子", "例如", "比如"],
                ["问题", "检查题", "追问", "你可以"],
            ],
        },
    )


def prompt_concepts_en() -> PromptSpec:
    title = "Improve classifier threshold decisions for software defect detection"
    description = "Understand precision, recall, threshold tradeoffs, false positives, and false negatives when triaging risky code review alerts."
    language_instruction = structured_support.build_language_instruction(title, description, json_mode=True)
    normalized_limit = 8
    prompt = f"""Extract key learning concepts from the user's question.

Question title: {title}
Question description: {description}

Requirements:
1. Return {normalized_limit} or fewer concrete concepts.
2. Prefer domain concepts, methods, and principles; avoid generic words.
3. Keep each concept short (1-6 words).
4. Do not include numbering or explanations.

Return ONLY a JSON array of strings, e.g.:
["concept A", "concept B"]

{language_instruction}"""
    return PromptSpec(
        category="concept_extraction",
        language="en",
        title="Concept Extraction EN",
        prompt=prompt,
        temperature=0.0,
        schema=structured_support.related_concepts_schema(normalized_limit),
        schema_name="related_concepts",
        expected={
            "keyword_groups": [
                ["precision"],
                ["recall"],
                ["threshold"],
                ["false positives", "false positive"],
                ["false negatives", "false negative"],
                ["defect detection", "classifier threshold", "decision boundary"],
            ],
            "limit": normalized_limit,
        },
    )


def prompt_concepts_zh() -> PromptSpec:
    title = "理解 PID 控制中的积分饱和"
    description = "提取与积分项、执行器饱和、超调、稳态误差、anti-windup 相关的核心学习概念。"
    language_instruction = structured_support.build_language_instruction(title, description, json_mode=True)
    normalized_limit = 8
    prompt = f"""Extract key learning concepts from the user's question.

Question title: {title}
Question description: {description}

Requirements:
1. Return {normalized_limit} or fewer concrete concepts.
2. Prefer domain concepts, methods, and principles; avoid generic words.
3. Keep each concept short (1-6 words).
4. Do not include numbering or explanations.

Return ONLY a JSON array of strings, e.g.:
["concept A", "concept B"]

{language_instruction}"""
    return PromptSpec(
        category="concept_extraction",
        language="zh",
        title="Concept Extraction ZH",
        prompt=prompt,
        temperature=0.0,
        schema=structured_support.related_concepts_schema(normalized_limit),
        schema_name="related_concepts",
        expected={
            "keyword_groups": [
                ["积分饱和", "积分项"],
                ["执行器饱和", "饱和"],
                ["超调", "过冲"],
                ["稳态误差"],
                ["抗积分饱和", "anti-windup"],
            ],
            "limit": normalized_limit,
        },
    )


def prompt_learning_path_en() -> PromptSpec:
    title = "Understand threshold tuning for defect detection classifiers"
    description = (
        "The learner already knows binary classification basics but struggles to choose thresholds for risky code alerts. "
        "They need a path that builds toward deployment decisions."
    )
    language_instruction = structured_support.build_language_instruction(
        title,
        description,
        "binary classification basics",
        "precision, recall",
        json_mode=True,
    )
    prompt = f"""Generate an optimized learning path for:

Problem/Goal: {title}
Description: {description}
User's Existing Knowledge: binary classification basics, confusion matrix
Associated Concepts: precision, recall, threshold, false positives, false negatives

Create a step-by-step learning path that:
1. Builds on existing knowledge
2. Introduces new concepts in logical order
3. Includes opportunities for model collision (testing understanding with counter-examples). These MUST be placed directly inside the "description" field, NEVER as a standalone string.

Return ONLY a valid JSON array of steps exactly matching this format (with NO extra keys or standalone strings):
[
    {{
        "step": 1,
        "concept": "concept name",
        "description": "what to learn, including model collisions if applicable",
        "resources": ["resource 1", "resource 2"]
    }}
]

{language_instruction}"""
    return PromptSpec(
        category="learning_path",
        language="en",
        title="Learning Path EN",
        prompt=prompt,
        temperature=0.0,
        schema=structured_support.learning_path_schema(),
        schema_name="learning_path",
        max_tokens=2200,
        expected={
            "keyword_groups": [
                ["precision", "recall"],
                ["threshold"],
                ["false positive", "false positives"],
                ["false negative", "false negatives"],
                ["deployment", "triage", "decision"],
            ]
        },
    )


def prompt_socratic_question_en() -> PromptSpec:
    prompt = structured_support.build_socratic_question_prompt(
        problem_title="Improve classifier threshold decisions for software defect detection",
        problem_description="The learner needs to justify threshold changes using precision, recall, and operational risk.",
        step_concept="Precision-recall tradeoff",
        step_description="Connect threshold changes to false positives, false negatives, and deployment decisions.",
        question_kind="probe",
        recent_responses=[
            "Lowering the threshold gives more alerts and should improve recall, but I am not fully sure what happens to precision.",
        ],
        latest_feedback={
            "correctness": "partially correct",
            "misconceptions": ["The learner has not explained why precision often drops when recall rises."],
            "suggestions": ["Tie threshold movement to false-positive volume."],
            "next_question": "",
        },
    )
    return PromptSpec(
        category="socratic_question",
        language="en",
        title="Socratic Question EN",
        prompt=prompt,
        temperature=0.7,
        expected={
            "keyword_groups": [
                ["precision"],
                ["recall"],
                ["threshold", "lower the threshold", "raise the threshold"],
                ["why", "how", "what happens"],
            ],
            "question_kind": "probe",
        },
    )


def prompt_socratic_question_zh() -> PromptSpec:
    prompt = structured_support.build_socratic_question_prompt(
        problem_title="理解 PID 控制中的积分饱和",
        problem_description="学习者需要判断什么时候积分项有帮助，什么时候会因为执行器受限而造成过冲。",
        step_concept="积分饱和",
        step_description="解释误差持续存在、积分继续累积、解除饱和后超调之间的因果链。",
        question_kind="checkpoint",
        recent_responses=[
            "我知道积分项会一直累加误差，所以可能造成超调，但我还没有把执行器上限和 anti-windup 联系清楚。",
        ],
        latest_feedback={
            "correctness": "部分正确",
            "misconceptions": ["还没有说明执行器达到上限后，积分项为什么仍会继续累积。"],
            "suggestions": ["用一个具体执行器饱和场景来解释。"],
            "next_question": "",
        },
    )
    return PromptSpec(
        category="socratic_question",
        language="zh",
        title="Socratic Question ZH",
        prompt=prompt,
        temperature=0.7,
        expected={
            "keyword_groups": [
                ["积分饱和", "积分项"],
                ["执行器", "饱和"],
                ["超调", "过冲"],
                ["例子", "场景", "什么时候"],
            ],
            "question_kind": "checkpoint",
        },
    )


def prompt_feedback_en() -> PromptSpec:
    concept = "Precision-recall tradeoff"
    user_response = (
        "Precision is how many bugs we catch, and recall is how many predicted bugs are really bugs. "
        "So if I lower the threshold I think both precision and recall go up because the model sees more positives."
    )
    model_examples = ["precision", "recall", "threshold", "false positives", "false negatives"]
    retrieval_context = """[Model Card] Threshold Tuning
Notes: Recall is the share of actual positives found. Precision is the share of predicted positives that are correct.
Examples: Lower threshold -> more alerts, more recall, often lower precision."""
    language_instruction = structured_support.build_language_instruction(
        user_response,
        concept,
        ", ".join(model_examples),
        retrieval_context,
        json_mode=True,
    )
    prompt = f"""Evaluate the user's understanding and return ONLY valid JSON.

Concept: {concept}
User's Response: {user_response}
Model Examples: {', '.join(model_examples)}

Relevant learner context:
{retrieval_context}

Return this exact JSON shape:
{{
  "correctness": "correct / partially correct / incorrect",
  "misconceptions": ["specific misconception"],
  "suggestions": ["specific suggestion"],
  "next_question": "a challenging follow-up question",
  "mastery_score": 0,
  "dimension_scores": {{"accuracy": 0, "completeness": 0, "transfer": 0, "rigor": 0}},
  "confidence": 0.0,
  "pass_stage": false,
  "decision_reason": "why pass_stage is true/false"
}}

{language_instruction}
"""
    return PromptSpec(
        category="structured_feedback",
        language="en",
        title="Structured Feedback EN",
        prompt=prompt,
        temperature=0.0,
        schema=structured_support.feedback_structured_schema(),
        schema_name="structured_feedback",
        expected={
            "correctness_contains": ["partial", "partially"],
            "must_reference": ["precision", "recall", "false positives", "predicted positives"],
            "pass_stage": False,
            "mastery_range": [35, 75],
        },
    )


def prompt_feedback_zh() -> PromptSpec:
    concept = "积分饱和"
    user_response = (
        "积分项会积累误差，所以一般都会带来稳态误差消除。"
        "如果出现超调，我觉得把积分项直接关掉就行，不一定和执行器饱和有关。"
    )
    model_examples = ["积分项", "执行器饱和", "超调", "抗积分饱和", "稳态误差"]
    retrieval_context = """[Model Card] PID 控制
Notes: 积分项可以消除稳态误差，但在执行器达到上限且误差持续存在时，积分会继续累积并导致解除饱和后的过冲。
Examples: 电机输出打满、温控加热器到达功率上限"""
    language_instruction = structured_support.build_language_instruction(
        user_response,
        concept,
        ", ".join(model_examples),
        retrieval_context,
        json_mode=True,
    )
    prompt = f"""Evaluate the user's understanding and return ONLY valid JSON.

Concept: {concept}
User's Response: {user_response}
Model Examples: {', '.join(model_examples)}

Relevant learner context:
{retrieval_context}

Return this exact JSON shape:
{{
  "correctness": "correct / partially correct / incorrect",
  "misconceptions": ["specific misconception"],
  "suggestions": ["specific suggestion"],
  "next_question": "a challenging follow-up question",
  "mastery_score": 0,
  "dimension_scores": {{"accuracy": 0, "completeness": 0, "transfer": 0, "rigor": 0}},
  "confidence": 0.0,
  "pass_stage": false,
  "decision_reason": "why pass_stage is true/false"
}}

{language_instruction}
"""
    return PromptSpec(
        category="structured_feedback",
        language="zh",
        title="Structured Feedback ZH",
        prompt=prompt,
        temperature=0.0,
        schema=structured_support.feedback_structured_schema(),
        schema_name="structured_feedback",
        expected={
            "correctness_contains": ["部分", "partial"],
            "must_reference": ["执行器", "饱和", "超调", "积分项"],
            "pass_stage": False,
            "mastery_range": [25, 70],
        },
    )


def scenario_specs() -> List[PromptSpec]:
    return [
        prompt_exploration_en(),
        prompt_exploration_zh(),
        prompt_concepts_en(),
        prompt_concepts_zh(),
        prompt_learning_path_en(),
        prompt_socratic_question_en(),
        prompt_socratic_question_zh(),
        prompt_feedback_en(),
        prompt_feedback_zh(),
    ]


def extract_message_text(response: Dict[str, Any]) -> str:
    choices = response.get("choices") or []
    if not choices:
        return ""
    message = choices[0].get("message") or {}
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: List[str] = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(str(item.get("text") or ""))
        return "".join(parts)
    return ""


def call_model(
    *,
    base_url: str,
    api_key: str,
    model: str,
    prompt: str,
    temperature: float,
    max_tokens: int,
    response_format: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if response_format:
        payload["response_format"] = response_format

    started = time.perf_counter()
    body = request_json(
        url=f"{base_url.rstrip('/')}/chat/completions",
        payload=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "HTTP-Referer": "https://github.com/suoweikeji-liqiang/Cogniforge",
            "X-Title": "Cogniforge LLM Benchmark",
        },
        timeout=90,
        retries=1,
    )
    latency_s = time.perf_counter() - started
    return {
        "latency_s": latency_s,
        "response": body,
        "text": extract_message_text(body),
        "usage": body.get("usage") or {},
    }


def parse_structured_output(spec: PromptSpec, raw_text: str) -> Any:
    cleaned = structured_support.clean_json_str(str(raw_text or ""))
    if not cleaned:
        return None
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        return None
    if spec.category == "concept_extraction":
        if isinstance(parsed, dict):
            parsed = parsed.get("concepts", [])
        if not isinstance(parsed, list):
            return None
        return structured_support.filter_low_signal_concepts([str(item) for item in parsed], limit=spec.expected.get("limit", 8))
    if spec.category == "learning_path":
        return structured_support.normalize_learning_path_payload(parsed)
    if spec.category == "structured_feedback":
        if not isinstance(parsed, dict):
            return None
        return structured_support.normalize_feedback_structured(parsed)
    return parsed


def run_candidate_call(base_url: str, api_key: str, model: str, spec: PromptSpec) -> Dict[str, Any]:
    total_latency = 0.0
    total_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    response_format = None
    schema_used = False
    fallback_used = False
    raw_text = ""
    parsed: Any = None
    error = None
    schema_error = None

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
                schema_result = call_model(
                    base_url=base_url,
                    api_key=api_key,
                    model=model,
                    prompt=spec.prompt,
                    temperature=spec.temperature,
                    max_tokens=spec.max_tokens,
                    response_format=response_format,
                )
                total_latency += schema_result["latency_s"]
                add_usage(schema_result["usage"])
                raw_text = schema_result["text"]
                parsed = parse_structured_output(spec, raw_text)
                schema_used = parsed is not None
                if parsed is None:
                    fallback_used = True
            except Exception as exc:  # pragma: no cover - remote runtime variance
                schema_error = str(exc)
                fallback_used = True

        if parsed is None:
            text_result = call_model(
                base_url=base_url,
                api_key=api_key,
                model=model,
                prompt=spec.prompt,
                temperature=spec.temperature,
                max_tokens=spec.max_tokens,
            )
            total_latency += text_result["latency_s"]
            add_usage(text_result["usage"])
            raw_text = text_result["text"]
            if spec.category in {"concept_extraction", "learning_path", "structured_feedback"}:
                parsed = parse_structured_output(spec, raw_text)
            else:
                parsed = str(raw_text or "").strip()
    except Exception as exc:  # pragma: no cover - remote runtime variance
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


def _contains_any(text: str, options: List[str]) -> bool:
    lowered = text.casefold()
    return any(option.casefold() in lowered for option in options)


def _keyword_coverage_score(text: str, keyword_groups: List[List[str]]) -> float:
    if not keyword_groups:
        return 100.0
    hits = sum(1 for group in keyword_groups if _contains_any(text, group))
    return (hits / len(keyword_groups)) * 100.0


def _language_score(expected_language: str, text: str) -> float:
    cjk = structured_support.count_cjk_chars(text)
    if expected_language == "zh":
        return 100.0 if cjk >= 12 else (60.0 if cjk >= 4 else 0.0)
    return 0.0 if cjk >= 8 else (70.0 if cjk > 0 else 100.0)


def evaluate_exploration(spec: PromptSpec, parsed: str) -> Dict[str, Any]:
    text = str(parsed or "").strip()
    keyword_score = _keyword_coverage_score(text, spec.expected["keyword_groups"])
    language_score = _language_score(spec.language, text)
    structure_score = _keyword_coverage_score(text, spec.expected.get("structure_groups", []))
    length_words = len(text.split())
    length_score = 100.0 if (40 <= length_words <= 260 or spec.language == "zh") else 70.0
    question_end = "?" in text or "？" in text
    guided_bonus = 100.0 if (spec.language == "zh" and question_end) or spec.language == "en" else 70.0
    score = 0.35 * keyword_score + 0.2 * language_score + 0.2 * structure_score + 0.15 * length_score + 0.1 * guided_bonus
    return {
        "deterministic_score": round(score, 2),
        "metrics": {
            "keyword_score": round(keyword_score, 2),
            "language_score": round(language_score, 2),
            "structure_score": round(structure_score, 2),
            "length_words": length_words,
        },
    }


def evaluate_concepts(spec: PromptSpec, parsed: Any, schema_used: bool, fallback_used: bool) -> Dict[str, Any]:
    concepts = parsed if isinstance(parsed, list) else []
    joined = " | ".join(concepts)
    keyword_score = _keyword_coverage_score(joined, spec.expected["keyword_groups"])
    language_score = _language_score(spec.language, joined)
    cleaned = structured_support.filter_low_signal_concepts(concepts, limit=len(concepts) or 8)
    cleanliness = 100.0 if len(cleaned) == len(concepts) else max(0.0, 100.0 * (len(cleaned) / max(1, len(concepts))))
    count_score = 100.0 if 3 <= len(concepts) <= spec.expected["limit"] else 60.0 if concepts else 0.0
    schema_score = 100.0 if schema_used else (60.0 if fallback_used and concepts else 0.0)
    score = 0.3 * keyword_score + 0.2 * language_score + 0.2 * cleanliness + 0.15 * count_score + 0.15 * schema_score
    return {
        "deterministic_score": round(score, 2),
        "metrics": {
            "keyword_score": round(keyword_score, 2),
            "language_score": round(language_score, 2),
            "cleanliness": round(cleanliness, 2),
            "count": len(concepts),
            "schema_used": schema_used,
            "fallback_used": fallback_used,
        },
    }


def evaluate_learning_path(spec: PromptSpec, parsed: Any, schema_used: bool, fallback_used: bool) -> Dict[str, Any]:
    steps = parsed if isinstance(parsed, list) else []
    combined = "\n".join(
        f"{step.get('step')}. {step.get('concept')} - {step.get('description')}" for step in steps
    )
    keyword_score = _keyword_coverage_score(combined, spec.expected["keyword_groups"])
    language_score = _language_score(spec.language, combined)
    field_complete = all(step.get("concept") and step.get("description") for step in steps)
    numbering_ok = [step.get("step") for step in steps] == list(range(1, len(steps) + 1)) if steps else False
    completeness = 100.0 if field_complete and numbering_ok else 60.0 if steps else 0.0
    step_count = 100.0 if 3 <= len(steps) <= 6 else 60.0 if steps else 0.0
    collision = 100.0 if _contains_any(combined, ["counter-example", "boundary", "failure", "tradeoff", "误区", "边界"]) else 40.0
    schema_score = 100.0 if schema_used else (60.0 if fallback_used and steps else 0.0)
    score = 0.25 * keyword_score + 0.2 * completeness + 0.15 * step_count + 0.15 * collision + 0.15 * language_score + 0.1 * schema_score
    return {
        "deterministic_score": round(score, 2),
        "metrics": {
            "keyword_score": round(keyword_score, 2),
            "language_score": round(language_score, 2),
            "step_count": len(steps),
            "numbering_ok": numbering_ok,
            "schema_used": schema_used,
            "fallback_used": fallback_used,
        },
    }


def evaluate_socratic_question(spec: PromptSpec, parsed: str) -> Dict[str, Any]:
    text = str(parsed or "").strip()
    language_score = _language_score(spec.language, text)
    keyword_score = _keyword_coverage_score(text, spec.expected["keyword_groups"])
    question_marks = text.count("?") + text.count("？")
    one_question = 100.0 if question_marks == 1 else 60.0 if question_marks >= 1 else 0.0
    concise = 100.0 if len(text.split()) <= 30 and len(text) <= 220 else 70.0
    no_answer_leak = 100.0 if not _contains_any(text, ["because", "therefore", "所以", "因为"]) else 60.0
    if spec.expected.get("question_kind") == "checkpoint":
        kind_score = 100.0 if _contains_any(text, ["example", "boundary", "什么时候", "什么情况下", "具体例子"]) else 60.0
    else:
        kind_score = 100.0 if _contains_any(text, ["why", "how", "what happens", "为什么", "怎么", "如何"]) else 60.0
    score = 0.25 * keyword_score + 0.2 * one_question + 0.2 * kind_score + 0.15 * language_score + 0.1 * concise + 0.1 * no_answer_leak
    return {
        "deterministic_score": round(score, 2),
        "metrics": {
            "keyword_score": round(keyword_score, 2),
            "language_score": round(language_score, 2),
            "question_marks": question_marks,
            "length_chars": len(text),
        },
    }


def evaluate_feedback(spec: PromptSpec, parsed: Any, schema_used: bool, fallback_used: bool) -> Dict[str, Any]:
    payload = parsed if isinstance(parsed, dict) else {}
    correctness = str(payload.get("correctness") or "")
    misconceptions = [str(item) for item in payload.get("misconceptions") or []]
    suggestions = [str(item) for item in payload.get("suggestions") or []]
    next_question = str(payload.get("next_question") or "")
    decision_reason = str(payload.get("decision_reason") or "")
    combined = "\n".join([correctness, *misconceptions, *suggestions, next_question, decision_reason])

    parse_score = 100.0 if payload else 0.0
    language_score = _language_score(spec.language, combined)
    correctness_score = 100.0 if _contains_any(correctness, spec.expected["correctness_contains"]) else 40.0
    reasoning_score = _keyword_coverage_score(combined, [spec.expected["must_reference"]])
    pass_stage = bool(payload.get("pass_stage"))
    pass_score = 100.0 if pass_stage == spec.expected["pass_stage"] else 0.0
    mastery_score = float(payload.get("mastery_score") or 0.0)
    low, high = spec.expected["mastery_range"]
    mastery_band = 100.0 if low <= mastery_score <= high else 40.0
    schema_score = 100.0 if schema_used else (60.0 if fallback_used and payload else 0.0)
    next_question_score = 100.0 if ("?" in next_question or "？" in next_question) else 50.0
    score = (
        0.2 * parse_score
        + 0.15 * correctness_score
        + 0.15 * reasoning_score
        + 0.1 * pass_score
        + 0.1 * mastery_band
        + 0.1 * next_question_score
        + 0.1 * language_score
        + 0.1 * schema_score
    )
    return {
        "deterministic_score": round(score, 2),
        "metrics": {
            "language_score": round(language_score, 2),
            "correctness": correctness,
            "misconception_count": len(misconceptions),
            "suggestion_count": len(suggestions),
            "mastery_score": mastery_score,
            "pass_stage": pass_stage,
            "schema_used": schema_used,
            "fallback_used": fallback_used,
        },
    }


def evaluate_result(spec: PromptSpec, candidate: Dict[str, Any]) -> Dict[str, Any]:
    if candidate.get("error"):
        return {
            "deterministic_score": 0.0,
            "metrics": {"error": candidate["error"]},
        }
    parsed = candidate.get("parsed")
    if spec.category == "exploration_answer":
        return evaluate_exploration(spec, str(parsed or ""))
    if spec.category == "concept_extraction":
        return evaluate_concepts(spec, parsed, candidate["schema_used"], candidate["fallback_used"])
    if spec.category == "learning_path":
        return evaluate_learning_path(spec, parsed, candidate["schema_used"], candidate["fallback_used"])
    if spec.category == "socratic_question":
        return evaluate_socratic_question(spec, str(parsed or ""))
    if spec.category == "structured_feedback":
        return evaluate_feedback(spec, parsed, candidate["schema_used"], candidate["fallback_used"])
    return {"deterministic_score": 0.0, "metrics": {"unsupported_category": spec.category}}


def judge_output(
    *,
    base_url: str,
    api_key: str,
    judge_model: str,
    spec: PromptSpec,
    candidate: Dict[str, Any],
) -> Dict[str, Any]:
    judge_schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "task_fulfillment": {"type": "number"},
            "pedagogical_quality": {"type": "number"},
            "correctness": {"type": "number"},
            "structure_fit": {"type": "number"},
            "language_fit": {"type": "number"},
            "overall": {"type": "number"},
            "strengths": {"type": "array", "items": {"type": "string"}},
            "risks": {"type": "array", "items": {"type": "string"}},
        },
        "required": [
            "task_fulfillment",
            "pedagogical_quality",
            "correctness",
            "structure_fit",
            "language_fit",
            "overall",
            "strengths",
            "risks",
        ],
    }
    candidate_text = json.dumps(candidate.get("parsed"), ensure_ascii=False, indent=2) if candidate.get("parsed") is not None else candidate.get("raw_text", "")
    judge_prompt = f"""You are judging one model output for Cogniforge, a structured learning product.

Task category: {spec.category}
Task title: {spec.title}
Expected language: {spec.language}
Scoring focus:
1. Does the output fit a real learning workflow rather than generic chat?
2. Does it preserve the protocol for this task (Exploration, Socratic, concepts, path, or structured feedback)?
3. Is it pedagogically useful, concrete, and safe to place in the product UI?
4. Is the language correct for the learner context?

Original prompt:
{spec.prompt}

Expected properties:
{json.dumps(spec.expected or {}, ensure_ascii=False, indent=2)}

Model output:
{candidate_text}

Return ONLY valid JSON. Scores task_fulfillment/pedagogical_quality/correctness/structure_fit/language_fit are 0-10. overall is 0-100."""

    result = call_model(
        base_url=base_url,
        api_key=api_key,
        model=judge_model,
        prompt=judge_prompt,
        temperature=0.0,
        max_tokens=900,
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "benchmark_judgement",
                "schema": judge_schema,
                "strict": True,
            },
        },
    )
    parsed = json.loads(structured_support.clean_json_str(result["text"]))
    return {
        "latency_s": round(result["latency_s"], 3),
        "usage": result["usage"],
        "parsed": parsed,
    }


def cost_from_usage(usage: Dict[str, Any], pricing: Dict[str, Any]) -> float:
    prompt_rate = float(pricing.get("prompt") or 0.0)
    completion_rate = float(pricing.get("completion") or 0.0)
    prompt_tokens = float(usage.get("prompt_tokens") or 0.0)
    completion_tokens = float(usage.get("completion_tokens") or 0.0)
    return prompt_tokens * prompt_rate + completion_tokens * completion_rate


def build_report(
    *,
    results: List[Dict[str, Any]],
    models_meta: Dict[str, Dict[str, Any]],
    judge_model: str,
    rounds: int,
    markdown_path: Path,
) -> str:
    model_rows: List[Dict[str, Any]] = []
    by_model: Dict[str, List[Dict[str, Any]]] = {}
    for item in results:
        by_model.setdefault(item["model"], []).append(item)

    latencies = []
    costs = []
    for model, items in by_model.items():
        deterministic_avg = statistics.mean(item["evaluation"]["deterministic_score"] for item in items)
        judge_scores = [
            item["judge"]["parsed"]["overall"]
            for item in items
            if item.get("judge") and isinstance(item["judge"], dict) and item["judge"].get("parsed")
        ]
        judge_avg = statistics.mean(judge_scores) if judge_scores else 0.0
        quality_avg = deterministic_avg * 0.6 + judge_avg * 0.4
        latency_values = [item["candidate"]["latency_s"] for item in items if item["candidate"]["latency_s"] > 0]
        median_latency = statistics.median(latency_values) if latency_values else 999.0
        schema_items = [item for item in items if item["spec"]["schema"]]
        schema_success_rate = (
            sum(1 for item in schema_items if item["candidate"]["schema_used"]) / len(schema_items) * 100.0
            if schema_items else 100.0
        )
        fallback_rate = (
            sum(1 for item in schema_items if item["candidate"]["fallback_used"]) / len(schema_items) * 100.0
            if schema_items else 0.0
        )
        total_usage = {"prompt_tokens": 0, "completion_tokens": 0}
        total_cost = 0.0
        for item in items:
            total_usage["prompt_tokens"] += int(item["candidate"]["usage"].get("prompt_tokens") or 0)
            total_usage["completion_tokens"] += int(item["candidate"]["usage"].get("completion_tokens") or 0)
            total_cost += float(item["candidate"]["estimated_cost"] or 0.0)
        meta = models_meta.get(model) or {}
        pricing = meta.get("pricing") or {}
        exploration_estimate = estimate_turn_cost(items, pricing, categories=["exploration_answer", "concept_extraction"])
        socratic_estimate = estimate_turn_cost(items, pricing, categories=["socratic_question", "structured_feedback", "concept_extraction"])

        row = {
            "model": model,
            "deterministic_avg": round(deterministic_avg, 2),
            "judge_avg": round(judge_avg, 2),
            "quality_avg": round(quality_avg, 2),
            "median_latency": round(median_latency, 3),
            "schema_success_rate": round(schema_success_rate, 1),
            "fallback_rate": round(fallback_rate, 1),
            "benchmark_cost": round(total_cost, 4),
            "exploration_estimate": round(exploration_estimate, 5),
            "socratic_estimate": round(socratic_estimate, 5),
            "strengths": top_notes(items, "strengths"),
            "risks": top_notes(items, "risks"),
        }
        model_rows.append(row)
        latencies.append(median_latency)
        costs.append(max(exploration_estimate + socratic_estimate, 1e-9))

    min_latency = min(latencies)
    max_latency = max(latencies)
    min_cost = min(costs)
    max_cost = max(costs)

    for row in model_rows:
        row["speed_score"] = round(scale_inverse(row["median_latency"], min_latency, max_latency), 2)
        row["cost_score"] = round(scale_inverse(row["exploration_estimate"] + row["socratic_estimate"], min_cost, max_cost), 2)
        row["overall_score"] = round(row["quality_avg"] * 0.7 + row["speed_score"] * 0.25 + row["cost_score"] * 0.05, 2)

    ranked = sorted(model_rows, key=lambda item: item["overall_score"], reverse=True)
    scenario_wins = scenario_leaderboard(results)

    lines: List[str] = []
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    lines.append("# Cogniforge OpenRouter LLM Benchmark Report")
    lines.append("")
    lines.append(f"- Generated at: {generated_at}")
    lines.append(f"- Candidate models tested: {len(ranked)}")
    lines.append(f"- Rounds per scenario: {rounds}")
    lines.append(f"- Judge model: `{judge_model}`")
    lines.append("- Benchmark focus: Cogniforge-specific Exploration, Socratic, concept extraction, learning-path JSON, and structured feedback.")
    lines.append("")
    lines.append("## Executive Summary")
    lines.append("")
    if ranked:
        best = ranked[0]
        lines.append(f"- Primary recommendation: `{best['model']}`")
        lines.append(f"  - Why: highest combined score on quality and latency (`overall={best['overall_score']}`, `quality={best['quality_avg']}`, `median_latency={best['median_latency']}s`).")
        lines.append(f"  - Main strengths: {', '.join(best['strengths']) or 'balanced quality across tasks'}")
        lines.append(f"  - Main risks: {', '.join(best['risks']) or 'no recurring blocker in this run'}")
    fastest = sorted(ranked, key=lambda item: item["median_latency"])[0] if ranked else None
    cheapest = sorted(ranked, key=lambda item: item["exploration_estimate"] + item["socratic_estimate"])[0] if ranked else None
    if fastest:
        lines.append(f"- Fastest viable model: `{fastest['model']}` (`median_latency={fastest['median_latency']}s`, `quality={fastest['quality_avg']}`).")
    if cheapest:
        lines.append(f"- Lowest estimated interaction cost: `{cheapest['model']}` (`exploration≈${cheapest['exploration_estimate']}`, `socratic-cycle≈${cheapest['socratic_estimate']}`).")
    lines.append("")
    lines.append("## Ranking")
    lines.append("")
    lines.append("| Rank | Model | Overall | Quality | Speed | Median Latency (s) | Schema Success | Exploration Est. ($) | Socratic Cycle Est. ($) |")
    lines.append("| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")
    for index, row in enumerate(ranked, start=1):
        lines.append(
            f"| {index} | `{row['model']}` | {row['overall_score']:.2f} | {row['quality_avg']:.2f} | {row['speed_score']:.2f} | {row['median_latency']:.3f} | {row['schema_success_rate']:.1f}% | {row['exploration_estimate']:.5f} | {row['socratic_estimate']:.5f} |"
        )
    lines.append("")
    lines.append("## Scenario Winners")
    lines.append("")
    for scenario_id, winners in scenario_wins.items():
        winner_line = ", ".join(f"`{item['model']}` ({item['score']:.2f})" for item in winners)
        lines.append(f"- `{scenario_id}`: {winner_line}")
    lines.append("")
    lines.append("## Model Notes")
    lines.append("")
    for row in ranked:
        lines.append(f"### `{row['model']}`")
        lines.append(f"- Overall: {row['overall_score']:.2f}")
        lines.append(f"- Quality: {row['quality_avg']:.2f} (deterministic {row['deterministic_avg']:.2f}, judge {row['judge_avg']:.2f})")
        lines.append(f"- Median latency: {row['median_latency']:.3f}s")
        lines.append(f"- Structured-output success: {row['schema_success_rate']:.1f}%")
        lines.append(f"- Fallback rate: {row['fallback_rate']:.1f}%")
        lines.append(f"- Benchmark spend in this run: ${row['benchmark_cost']:.4f}")
        lines.append(f"- Estimated exploration turn cost: ${row['exploration_estimate']:.5f}")
        lines.append(f"- Estimated Socratic cycle cost: ${row['socratic_estimate']:.5f}")
        lines.append(f"- Strengths: {', '.join(row['strengths']) or 'None recorded'}")
        lines.append(f"- Risks: {', '.join(row['risks']) or 'None recorded'}")
        lines.append("")
    lines.append("## Recommendation Logic")
    lines.append("")
    lines.append("- Overall score weighting: quality 70%, speed 25%, price 5%.")
    lines.append("- Quality blends deterministic protocol checks (60%) and one-round judge scoring (40%).")
    lines.append("- Price is intentionally a small factor because this project values answer quality and latency first.")
    lines.append("")
    markdown = "\n".join(lines).strip() + "\n"
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(markdown, encoding="utf-8")
    return markdown


def estimate_turn_cost(items: List[Dict[str, Any]], pricing: Dict[str, Any], categories: List[str]) -> float:
    category_rows = [item for item in items if item["spec"]["category"] in categories]
    if not category_rows:
        return 0.0
    per_category_costs: List[float] = []
    for category in categories:
        subset = [item for item in category_rows if item["spec"]["category"] == category]
        if not subset:
            continue
        per_category_costs.append(statistics.mean(float(item["candidate"]["estimated_cost"] or 0.0) for item in subset))
    return sum(per_category_costs)


def top_notes(items: List[Dict[str, Any]], note_key: str) -> List[str]:
    counts: Dict[str, int] = {}
    for item in items:
        judge = item.get("judge") or {}
        parsed = judge.get("parsed") or {}
        for note in parsed.get(note_key) or []:
            note_text = str(note or "").strip()
            if not note_text:
                continue
            counts[note_text] = counts.get(note_text, 0) + 1
    ranked = sorted(counts.items(), key=lambda pair: (-pair[1], pair[0]))
    return [note for note, _ in ranked[:3]]


def scale_inverse(value: float, min_value: float, max_value: float) -> float:
    if math.isclose(min_value, max_value):
        return 100.0
    ratio = (value - min_value) / (max_value - min_value)
    return max(0.0, 100.0 * (1.0 - ratio))


def scenario_leaderboard(results: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    by_scenario: Dict[str, List[Dict[str, Any]]] = {}
    for item in results:
        by_scenario.setdefault(item["spec"]["title"], []).append(item)
    leaders: Dict[str, List[Dict[str, Any]]] = {}
    for scenario_title, items in by_scenario.items():
        grouped: Dict[str, List[float]] = {}
        for item in items:
            grouped.setdefault(item["model"], []).append(item["evaluation"]["deterministic_score"])
        ranked = sorted(
            [{"model": model, "score": statistics.mean(scores)} for model, scores in grouped.items()],
            key=lambda row: row["score"],
            reverse=True,
        )
        leaders[scenario_title] = ranked[:3]
    return leaders


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark OpenRouter models for Cogniforge workflows.")
    parser.add_argument("--env-file", default=str(REPO_ROOT / "testllm.env"))
    parser.add_argument("--rounds", type=int, default=2)
    parser.add_argument("--judge-model", default=DEFAULT_JUDGE_MODEL)
    parser.add_argument("--skip-judge", action="store_true")
    parser.add_argument("--models", nargs="*", default=DEFAULT_MODELS)
    parser.add_argument("--scenario-filter", nargs="*", default=[])
    parser.add_argument("--output-dir", default=str(REPO_ROOT / "output" / "llm-benchmarks"))
    parser.add_argument("--report-path", default="")
    args = parser.parse_args()

    env = load_env(Path(args.env_file))
    api_key = env.get("API_KEY") or env.get("OPENROUTER_API_KEY")
    base_url = env.get("BASE_URL") or "https://openrouter.ai/api/v1"
    if not api_key:
        raise SystemExit("Missing API_KEY or OPENROUTER_API_KEY in env file.")

    catalog = fetch_model_catalog(base_url, api_key)
    selected_models = [model for model in args.models if model in catalog]
    missing_models = [model for model in args.models if model not in catalog]
    if missing_models:
        print(f"Skipping unavailable models: {', '.join(missing_models)}")
    if not args.skip_judge and args.judge_model not in catalog:
        raise SystemExit(f"Judge model not available on OpenRouter: {args.judge_model}")

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_dir = Path(args.output_dir) / timestamp
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = Path(args.report_path) if args.report_path else (REPO_ROOT / "docs" / "reports" / f"llm-benchmark-openrouter-{timestamp}.md")

    specs = scenario_specs()
    if args.scenario_filter:
        filters = [item.casefold() for item in args.scenario_filter]
        specs = [spec for spec in specs if any(token in spec.title.casefold() or token in spec.category.casefold() for token in filters)]
    if not specs:
        raise SystemExit("No scenarios matched --scenario-filter.")
    results: List[Dict[str, Any]] = []
    total_runs = len(selected_models) * len(specs) * max(1, int(args.rounds))
    current_run = 0

    for model in selected_models:
        print(f"\n=== Model: {model} ===")
        pricing = (catalog.get(model) or {}).get("pricing") or {}
        for round_index in range(1, max(1, int(args.rounds)) + 1):
            for spec in specs:
                current_run += 1
                print(f"[{current_run}/{total_runs}] {model} | round {round_index} | {spec.title}")
                candidate = run_candidate_call(base_url, api_key, model, spec)
                candidate["estimated_cost"] = round(cost_from_usage(candidate["usage"], pricing), 8)
                evaluation = evaluate_result(spec, candidate)
                judge = None
                if round_index == 1 and not candidate.get("error") and not args.skip_judge:
                    try:
                        judge = judge_output(
                            base_url=base_url,
                            api_key=api_key,
                            judge_model=args.judge_model,
                            spec=spec,
                            candidate=candidate,
                        )
                    except Exception as exc:  # pragma: no cover - remote runtime variance
                        judge = {"error": str(exc)}
                results.append(
                    {
                        "model": model,
                        "round": round_index,
                        "spec": {
                            "title": spec.title,
                            "category": spec.category,
                            "language": spec.language,
                            "schema": bool(spec.schema),
                        },
                        "candidate": candidate,
                        "evaluation": evaluation,
                        "judge": judge,
                    }
                )

    raw_path = output_dir / "results.json"
    raw_path.write_text(json.dumps({"results": results}, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown = build_report(
        results=results,
        models_meta=catalog,
        judge_model=args.judge_model,
        rounds=max(1, int(args.rounds)),
        markdown_path=report_path,
    )

    summary_path = output_dir / "summary.txt"
    summary_path.write_text(markdown, encoding="utf-8")
    print("")
    print(f"Raw results: {raw_path}")
    print(f"Report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
