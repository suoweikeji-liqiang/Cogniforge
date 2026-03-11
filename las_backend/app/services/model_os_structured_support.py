from collections import Counter
from typing import Any, Dict, List, Optional
import re


def clean_json_str(text: str) -> str:
    match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
    if match:
        return match.group(1).strip()

    text = text.strip()
    if not text.startswith("[") and not text.startswith("{"):
        start_idx = -1
        for i, char in enumerate(text):
            if char in ("[", "{"):
                start_idx = i
                break
        if start_idx != -1:
            closing = "]" if text[start_idx] == "[" else "}"
            end_idx = -1
            for i in range(len(text) - 1, -1, -1):
                if text[i] == closing:
                    end_idx = i
                    break
            if end_idx != -1 and end_idx >= start_idx:
                return text[start_idx:end_idx + 1].strip()
    return text


def feedback_structured_schema() -> Dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "correctness": {"type": "string"},
            "misconceptions": {
                "type": "array",
                "items": {"type": "string"},
            },
            "suggestions": {
                "type": "array",
                "items": {"type": "string"},
            },
            "next_question": {"type": "string"},
            "mastery_score": {"type": "number"},
            "dimension_scores": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "accuracy": {"type": "number"},
                    "completeness": {"type": "number"},
                    "transfer": {"type": "number"},
                    "rigor": {"type": "number"},
                },
                "required": ["accuracy", "completeness", "transfer", "rigor"],
            },
            "confidence": {"type": "number"},
            "pass_stage": {"type": "boolean"},
            "decision_reason": {"type": "string"},
        },
        "required": [
            "correctness",
            "misconceptions",
            "suggestions",
            "next_question",
            "mastery_score",
            "dimension_scores",
            "confidence",
            "pass_stage",
            "decision_reason",
        ],
    }


def step_hint_schema() -> Dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "focus": {"type": "string"},
            "next_actions": {
                "type": "array",
                "items": {"type": "string"},
            },
            "starter": {"type": "string"},
        },
        "required": ["focus", "next_actions", "starter"],
    }


def learning_path_schema() -> Dict[str, Any]:
    return {
        "type": "array",
        "items": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "step": {"type": "number"},
                "concept": {"type": "string"},
                "description": {"type": "string"},
                "resources": {
                    "type": "array",
                    "items": {"type": "string"},
                },
            },
            "required": ["step", "concept", "description", "resources"],
        },
    }


def related_concepts_schema(limit: int) -> Dict[str, Any]:
    return {
        "type": "array",
        "items": {"type": "string"},
        "maxItems": max(1, limit),
    }


def model_card_schema() -> Dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "concept_maps": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "nodes": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "id": {"type": "string"},
                                "label": {"type": "string"},
                                "type": {"type": "string"},
                            },
                            "required": ["id", "label", "type"],
                        },
                    },
                    "edges": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "source": {"type": "string"},
                                "target": {"type": "string"},
                                "label": {"type": "string"},
                            },
                            "required": ["source", "target", "label"],
                        },
                    },
                },
                "required": ["nodes", "edges"],
            },
            "core_principles": {
                "type": "array",
                "items": {"type": "string"},
            },
            "examples": {
                "type": "array",
                "items": {"type": "string"},
            },
            "limitations": {
                "type": "array",
                "items": {"type": "string"},
            },
        },
        "required": ["concept_maps", "core_principles", "examples", "limitations"],
    }


def counter_examples_schema() -> Dict[str, Any]:
    return {
        "type": "array",
        "items": {"type": "string"},
    }


def migration_schema() -> Dict[str, Any]:
    return {
        "type": "array",
        "items": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "domain": {"type": "string"},
                "application": {"type": "string"},
                "key_adaptations": {"type": "string"},
            },
            "required": ["domain", "application", "key_adaptations"],
        },
    }


def tokenize_text(text: str) -> List[str]:
    return re.findall(r"[a-zA-Z0-9_]+", text.lower())


def contains_cjk(text: Optional[str]) -> bool:
    if not text:
        return False
    return bool(re.search(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]", text))


def build_language_instruction(*texts: Optional[str], json_mode: bool = False) -> str:
    has_cjk = any(contains_cjk(text) for text in texts)
    if has_cjk:
        base = "Language requirement: Respond in Simplified Chinese."
    else:
        base = "Language requirement: Respond in the same language as the user's input."

    if json_mode:
        return f"{base} Keep JSON keys exactly as requested."
    return base


def normalize_concepts(concepts: List[str], limit: int = 8) -> List[str]:
    normalized: List[str] = []
    seen = set()
    for raw in concepts or []:
        concept = re.sub(r"\s+", " ", str(raw or "")).strip(" \t\r\n,.;:|/-")
        if not concept:
            continue
        if len(concept) > 80:
            concept = concept[:80].rstrip()
        key = concept.casefold()
        if key in seen:
            continue
        seen.add(key)
        normalized.append(concept)
        if len(normalized) >= limit:
            break
    return normalized


def is_low_signal_concept_candidate(concept: Optional[str]) -> bool:
    text = re.sub(r"\s+", " ", str(concept or "")).strip(" \t\r\n,.;:!?\"'()[]{}")
    if not text:
        return True

    lowered = text.casefold()
    if contains_cjk(text):
        compact = re.sub(r"\s+", "", text)
        if compact in {
            "简洁定义",
            "关键区别",
            "具体例子",
            "常见误区",
            "问题陈述",
            "问题背景",
            "问题描述",
            "核心思路",
            "解题思路",
            "总结",
            "结论",
            "提示",
            "回答",
            "答案",
        }:
            return True
        if any(
            compact.endswith(suffix)
            for suffix in ("是什么", "是什么意思", "有哪些", "吗", "么", "呢", "如何", "怎么", "为什么", "为何")
        ):
            return True
        if any(
            compact.startswith(prefix)
            for prefix in ("中的", "关于", "对于", "根据", "通过", "利用", "使用", "用于", "用来", "把", "将", "从", "对", "但")
        ):
            return True
        if len(compact) >= 8 and any(
            marker in compact
            for marker in ("根据", "通过", "用于", "用来", "当前", "过去", "未来", "所有", "可能", "以及", "并且", "从而")
        ):
            return True
        return False

    if lowered in {
        "problem statement",
        "definition",
        "key distinction",
        "example",
        "examples",
        "summary",
        "conclusion",
    }:
        return True
    if lowered.startswith(("what is ", "explain ", "define ", "clarify ", "problem statement")):
        return True
    return False


def filter_low_signal_concepts(concepts: List[str], limit: int = 8) -> List[str]:
    filtered: List[str] = []
    seen = set()
    for raw in concepts or []:
        concept = re.sub(r"\s+", " ", str(raw or "")).strip(" \t\r\n,.;:|/-")
        if not concept or is_low_signal_concept_candidate(concept):
            continue
        if len(concept) > 80:
            concept = concept[:80].rstrip()
        key = concept.casefold()
        if key in seen:
            continue
        seen.add(key)
        filtered.append(concept)
        if len(filtered) >= limit:
            break
    return filtered


def normalize_concept_key(concept: str) -> str:
    base = re.sub(r"\s+", " ", str(concept or "")).strip().casefold()
    if not base:
        return ""
    return re.sub(r"[^\w\u4e00-\u9fff\s-]", "", base).strip()


def normalize_float(value: Any, default: float, min_value: float, max_value: float) -> float:
    try:
        num = float(value)
    except (TypeError, ValueError):
        num = default
    return round(max(min_value, min(max_value, num)), 4)


def normalize_int(value: Any, default: int, min_value: int, max_value: int) -> int:
    try:
        num = int(round(float(value)))
    except (TypeError, ValueError):
        num = default
    return max(min_value, min(max_value, num))


def normalize_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "yes", "y", "1"}:
            return True
        if lowered in {"false", "no", "n", "0"}:
            return False
    return default


def derive_mastery_defaults(correctness: str, misconception_count: int) -> tuple[int, bool]:
    verdict = correctness.strip().lower()
    if any(marker in verdict for marker in ("incorrect", "wrong", "not correct", "错误", "不正确")):
        return 35, False
    if any(marker in verdict for marker in ("partially", "mostly", "部分", "基本正确", "较为正确")):
        return (68 if misconception_count <= 1 else 60), misconception_count == 0
    if any(marker in verdict for marker in ("correct", "正确")):
        return (86 if misconception_count == 0 else 78), misconception_count <= 1
    return 55, False


def normalize_feedback_structured(payload: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    data = payload or {}
    correctness = str(data.get("correctness", "") or "").strip()
    misconceptions = [
        str(item).strip()
        for item in (data.get("misconceptions") or [])
        if str(item).strip()
    ]
    suggestions = [
        str(item).strip()
        for item in (data.get("suggestions") or [])
        if item is not None and str(item).strip()
    ]
    next_question = str(data.get("next_question", "") or "").strip()

    _default_score, _default_pass = derive_mastery_defaults(
        correctness=correctness,
        misconception_count=len(misconceptions),
    )
    mastery_score = normalize_int(data.get("mastery_score"), 0, 0, 100)
    confidence = normalize_float(data.get("confidence"), 0.0, 0.0, 1.0)
    pass_stage = normalize_bool(data.get("pass_stage"), False)

    raw_dimensions = data.get("dimension_scores")
    dimensions: Dict[str, int] = {}
    if isinstance(raw_dimensions, dict):
        for key in ("accuracy", "completeness", "transfer", "rigor"):
            dimensions[key] = normalize_int(raw_dimensions.get(key), mastery_score, 0, 100)
    else:
        dimensions = {
            "accuracy": mastery_score,
            "completeness": mastery_score,
            "transfer": mastery_score,
            "rigor": mastery_score,
        }

    decision_reason = str(data.get("decision_reason", "") or "").strip()
    if not decision_reason:
        decision_reason = (
            f"Mastery score={mastery_score}, confidence={confidence}, misconceptions={len(misconceptions)}"
        )

    return {
        "correctness": correctness,
        "misconceptions": misconceptions,
        "suggestions": suggestions,
        "next_question": next_question,
        "mastery_score": mastery_score,
        "dimension_scores": dimensions,
        "confidence": confidence,
        "pass_stage": pass_stage,
        "decision_reason": decision_reason,
    }


def build_learning_answer_fallback(question: str, step_concept: str, mode: str = "direct") -> str:
    question = str(question or "").strip()
    step_concept = str(step_concept or "this concept").strip()
    has_cjk = contains_cjk(question) or contains_cjk(step_concept)
    if mode == "guided":
        if has_cjk:
            return (
                f"提示：先抓住“{step_concept or '这个概念'}”的核心边界。"
                f"试着围绕“{question or '你的问题'}”举一个具体例子，"
                "再说明一种看起来相近但其实不成立的解释为什么会失败。"
            )
        return (
            f"Hint: focus on the core boundary of '{step_concept}'. "
            f"Try one concrete example for your question ({question or 'your question'}), "
            "then explain why an alternative interpretation would fail."
        )
    if has_cjk:
        return (
            f"一个简洁的起点：先用一句话定义“{step_concept or '这个概念'}”，"
            "再把它和最容易混淆的相近概念区分开，"
            "最后放进一个具体例子里验证它。"
        )
    return (
        f"A concise starting point for '{step_concept}': define it in one sentence, "
        "contrast it with the closest confusing concept, then apply it in one concrete example."
    )


def build_socratic_question_fallback(
    step_concept: str,
    question_kind: str,
    latest_feedback: Optional[Dict[str, Any]] = None,
) -> str:
    concept = str(step_concept or "this concept").strip()
    feedback = latest_feedback or {}
    next_question = str(feedback.get("next_question") or "").strip()
    misconception = ""
    misconceptions = feedback.get("misconceptions") or []
    if misconceptions:
        misconception = str(misconceptions[0] or "").strip()
    has_cjk = contains_cjk(concept) or contains_cjk(next_question) or contains_cjk(misconception)

    if next_question:
        return next_question

    if question_kind == "checkpoint":
        if has_cjk:
            return (
                f"检查题：请用一个具体例子解释“{concept or '这个概念'}”，"
                "再补一个边界情况，说明在什么情况下你的解释会失效。"
            )
        return (
            f"Checkpoint: explain '{concept}' with one concrete example and one boundary case "
            "that would make your explanation fail."
        )

    if misconception:
        if has_cjk:
            return (
                f"追问题：你刚才提到了“{misconception}”。"
                f"请用你自己的话重新解释它和“{concept or '这个概念'}”之间的关系。"
            )
        return (
            f"Probe: you mentioned '{misconception}'. Re-explain how it relates to '{concept}' "
            "in your own words."
        )

    if has_cjk:
        return f"追问题：在继续之前，你会怎样概括“{concept or '这个概念'}”的核心思想？它最容易和什么混淆？"
    return (
        f"Probe: before moving on, what is the core idea of '{concept}', and what is the most likely confusion point?"
    )


def build_socratic_question_prompt(
    problem_title: str,
    problem_description: str,
    step_concept: str,
    step_description: str,
    question_kind: str,
    recent_responses: Optional[List[str]] = None,
    latest_feedback: Optional[Dict[str, Any]] = None,
) -> str:
    recent_block = ""
    if recent_responses:
        recent_block = "\nRecent learner answers:\n" + "\n".join(
            f"- {item}" for item in recent_responses if item
        )
    feedback_block = ""
    if latest_feedback:
        feedback_block = (
            "\nLatest feedback context:"
            f"\n- Correctness: {latest_feedback.get('correctness') or 'N/A'}"
            f"\n- Misconceptions: {'; '.join(latest_feedback.get('misconceptions') or []) or 'N/A'}"
            f"\n- Suggestions: {'; '.join(latest_feedback.get('suggestions') or []) or 'N/A'}"
        )

    language_instruction = build_language_instruction(
        problem_title,
        problem_description,
        step_concept,
        step_description,
        *(recent_responses or []),
    )
    return f"""You are preparing one Socratic learning question.

Problem: {problem_title}
Problem description: {problem_description}
Current step concept: {step_concept}
Current step description: {step_description}
Question kind: {question_kind}
{recent_block}
{feedback_block}

Rules:
1. Return exactly one question.
2. If question kind is probe, ask for clarification or causal explanation.
3. If question kind is checkpoint, ask a stronger evaluation question that can justify progression.
4. Do not answer the question.
5. Keep it concise and concrete.

{language_instruction}"""


def hint_tokens(text: str) -> set[str]:
    tokens = set(re.findall(r"[a-zA-Z0-9_]+|[\u4e00-\u9fff]", (text or "").lower()))
    return {token for token in tokens if token.strip()}


def hint_similarity(left: str, right: str) -> float:
    left_tokens = hint_tokens(left)
    right_tokens = hint_tokens(right)
    if not left_tokens or not right_tokens:
        return 0.0
    inter = left_tokens.intersection(right_tokens)
    union = left_tokens.union(right_tokens)
    if not union:
        return 0.0
    return len(inter) / len(union)


def dedupe_hint_actions(
    actions: List[str],
    previous_texts: Optional[List[str]] = None,
    cjk_context: bool = False,
) -> List[str]:
    cleaned_previous = [str(item).strip() for item in (previous_texts or []) if str(item).strip()]
    output: List[str] = []
    seen_norms = set()

    for raw in actions:
        action = str(raw or "").strip()
        if not action:
            continue
        norm = re.sub(r"\s+", " ", action).strip().casefold()
        if norm in seen_norms:
            continue

        is_repetitive = False
        for previous in cleaned_previous:
            previous_norm = re.sub(r"\s+", " ", previous).strip().casefold()
            if not previous_norm:
                continue
            if norm == previous_norm:
                is_repetitive = True
                break
            if len(norm) >= 8 and (norm in previous_norm or previous_norm in norm):
                is_repetitive = True
                break
            if hint_similarity(norm, previous_norm) >= 0.72:
                is_repetitive = True
                break

        if is_repetitive:
            continue

        seen_norms.add(norm)
        output.append(action)
        if len(output) >= 3:
            break

    if len(output) >= 2:
        return output

    fallback_actions = (
        [
            "先写出你已经确认正确的一点。",
            "再补一个具体例子来检验这一步。",
            "最后写出一个不确定点请求反馈。",
        ]
        if cjk_context
        else [
            "Write one thing you are confident about first.",
            "Add one concrete example to test this step.",
            "List one uncertainty you want feedback on.",
        ]
    )
    for item in fallback_actions:
        norm = re.sub(r"\s+", " ", item).strip().casefold()
        if norm in seen_norms:
            continue
        seen_norms.add(norm)
        output.append(item)
        if len(output) >= 3:
            break

    return output[:3]


def normalize_step_hint_structured(
    parsed: Dict[str, Any],
    *,
    previous_hint_texts: Optional[List[str]] = None,
    cjk_context: bool = False,
) -> Dict[str, Any]:
    actions = parsed.get("next_actions", [])
    if not isinstance(actions, list):
        actions = []
    normalized_actions = [
        str(item).strip()
        for item in actions
        if str(item).strip()
    ][:3]
    deduped_actions = dedupe_hint_actions(
        actions=normalized_actions,
        previous_texts=previous_hint_texts,
        cjk_context=cjk_context,
    )
    return {
        "focus": str(parsed.get("focus", "")).strip(),
        "next_actions": deduped_actions,
        "starter": str(parsed.get("starter", "")).strip(),
    }


def build_fallback_step_hint(
    *,
    step_concept: str,
    previous_hint_texts: Optional[List[str]] = None,
    cjk_context: bool = False,
) -> Dict[str, Any]:
    fallback_focus = (
        f"Focus on clarifying your understanding of '{step_concept}' in this step."
        if not cjk_context
        else f"先聚焦澄清你对“{step_concept}”这一步的理解。"
    )
    fallback_actions = (
        [
            "State what you already understand in 2-3 sentences.",
            "Add one concrete example or mini attempt.",
            "List one uncertainty you want feedback on.",
        ]
        if not cjk_context
        else [
            "先用 2-3 句话写出你已经理解的内容。",
            "补一个具体例子或你的一次尝试。",
            "写出一个最不确定的点，便于获得针对性反馈。",
        ]
    )
    fallback_actions = dedupe_hint_actions(
        actions=fallback_actions,
        previous_texts=previous_hint_texts,
        cjk_context=cjk_context,
    )
    fallback_starter = (
        f"My current understanding of {step_concept} is:"
        if not cjk_context
        else f"我目前对“{step_concept}”的理解是："
    )
    return {
        "focus": fallback_focus,
        "next_actions": fallback_actions,
        "starter": fallback_starter,
    }


def fallback_concepts_from_problem(
    problem_title: str,
    problem_description: str,
    limit: int = 8,
) -> List[str]:
    title_text = str(problem_title or "")
    description_text = str(problem_description or "")
    combined = "\n".join([title_text, description_text])
    candidates: List[str] = []

    if contains_cjk(combined):
        for match in re.finditer(r"([\u4e00-\u9fff]{2,12})(?=（[A-Za-z0-9_+\-/]{1,6}）)", combined):
            candidates.append(match.group(1))

        for match in re.finditer(
            r"(?:^|[\n\r\-•*]\s*|\d+\.\s*)([\u4e00-\u9fff]{2,12})(?:（[A-Za-z0-9_+\-/]{1,6}）)?\s*[:：]",
            combined,
        ):
            candidates.append(match.group(1))

        for line in re.split(r"[\r\n]+", combined):
            compact = re.sub(r"\s+", "", str(line or ""))
            if not compact or not contains_cjk(compact):
                continue
            compact = re.sub(
                r"^(?:Question|Answer|Currentstepconcept|Currentstepdescription)[:：]?",
                "",
                compact,
                flags=re.IGNORECASE,
            )
            compact = re.sub(r"^[A-Za-z0-9_+\-/]+中的", "", compact)
            compact = re.sub(r"(是什么|是什么意思|有哪些|吗|么|呢|如何|怎么|为什么|为何)[?？]?$", "", compact)
            if any(separator in compact for separator in ("、", "和", "及", "与", "，", ",")):
                for part in re.split(r"[、，,]|和|及|与", compact):
                    cleaned_part = re.sub(r"^[A-Za-z0-9_+\-/]+中的", "", part)
                    cleaned_part = re.sub(r"^(中的|关于|对于)", "", cleaned_part)
                    cleaned_part = re.sub(r"(是什么|是什么意思|有哪些|吗|么|呢|如何|怎么|为什么|为何)$", "", cleaned_part)
                    cleaned_part = cleaned_part.strip()
                    if 2 <= len(cleaned_part) <= 12:
                        candidates.append(cleaned_part)

        candidates.extend(re.findall(r"[\u4e00-\u9fff]{2,12}", combined))
    else:
        stop_words = {
            "what", "when", "where", "which", "with", "from", "into", "this", "that",
            "need", "want", "have", "has", "for", "and", "the", "you", "your", "about",
            "understand", "understanding", "learn", "learning", "changes", "change",
            "explain", "question", "problem", "goal", "how", "why", "using", "use",
            "to", "in", "on", "at", "by", "of", "as", "is", "are", "be", "an", "a",
            "i", "we", "me", "my", "our",
        }
        low_signal_single_words = {"false", "true"}
        combined_words = re.findall(r"[A-Za-z][A-Za-z0-9_-]{1,}", combined)
        filtered_words = [word for word in combined_words if word.casefold() not in stop_words]
        word_frequencies = Counter(word.casefold() for word in filtered_words)

        frequent_words: List[str] = []
        seen_frequent = set()
        for word in filtered_words:
            key = word.casefold()
            if word_frequencies[key] < 2 or key in seen_frequent or key in low_signal_single_words:
                continue
            seen_frequent.add(key)
            frequent_words.append(word)

        def _extract_source_candidates(source: str) -> tuple[List[str], List[str]]:
            source_words = re.findall(r"[A-Za-z][A-Za-z0-9_-]{1,}", source)
            phrases: List[str] = []
            singles: List[str] = []
            seen_phrases = set()
            seen_singles = set()

            for first, second in zip(source_words, source_words[1:]):
                if first.casefold() in stop_words or second.casefold() in stop_words:
                    continue
                if second.casefold() in low_signal_single_words:
                    continue
                if first.endswith("s") and not second.endswith("s") and second[0].islower():
                    continue
                phrase = f"{first} {second}"
                key = phrase.casefold()
                if key in seen_phrases:
                    continue
                seen_phrases.add(key)
                phrases.append(phrase)

            for word in source_words:
                key = word.casefold()
                if (
                    key in stop_words
                    or key in seen_singles
                    or key in low_signal_single_words
                    or word_frequencies[key] >= 2
                ):
                    continue
                seen_singles.add(key)
                singles.append(word)

            return phrases, singles

        description_phrases, description_singles = _extract_source_candidates(description_text)
        title_phrases, title_singles = _extract_source_candidates(title_text)
        candidates.extend(frequent_words)
        if frequent_words:
            candidates.extend(description_phrases)
            candidates.extend(description_singles)
            candidates.extend(title_phrases)
            candidates.extend(title_singles)
        else:
            candidates.extend(description_singles)
            candidates.extend(description_phrases)
            candidates.extend(title_singles)
            candidates.extend(title_phrases)

    if not candidates and problem_title:
        candidates.append(problem_title)

    filtered = filter_low_signal_concepts(candidates, limit=limit)
    if filtered:
        return filtered
    return filter_low_signal_concepts([problem_title], limit=max(1, limit))


def build_problem_concepts_local(
    problem_title: str,
    problem_description: str,
    seed_concepts: Optional[List[str]] = None,
    max_concepts: int = 8,
) -> List[str]:
    normalized_limit = max(3, min(max_concepts, 12))
    seed = filter_low_signal_concepts(seed_concepts or [], limit=normalized_limit)
    if len(seed) >= normalized_limit:
        return seed

    inferred = fallback_concepts_from_problem(
        problem_title=problem_title,
        problem_description=problem_description,
        limit=normalized_limit,
    )
    concepts = filter_low_signal_concepts(seed + inferred, limit=normalized_limit)
    if concepts:
        return concepts
    return filter_low_signal_concepts([problem_title], limit=max(1, normalized_limit))


def build_fallback_learning_path(
    problem_title: str,
    problem_description: str,
    existing_knowledge: List[str],
    associated_concepts: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    has_cjk = any(
        contains_cjk(text)
        for text in [problem_title, problem_description, *(existing_knowledge or []), *((associated_concepts or []))]
    )
    knowledge_text = ", ".join(existing_knowledge) if existing_knowledge else ("你当前已有的基础" if has_cjk else "your current foundation")
    title_text = re.sub(r"\s+", " ", str(problem_title or "")).strip()
    description_text = re.sub(r"\s+", " ", str(problem_description or "")).strip()
    problem_context = description_text or title_text or ("当前问题" if has_cjk else "the current problem")
    first_resource = problem_context[:120] or ("已有笔记与前置材料" if has_cjk else "Existing notes and prior project docs")
    focus_concepts = normalize_concepts([*(associated_concepts or []), title_text], limit=3)
    primary_focus = focus_concepts[0] if focus_concepts else (title_text or ("核心概念" if has_cjk else "Core concept"))
    secondary_focus = focus_concepts[1] if len(focus_concepts) > 1 else None
    combined_text = f"{title_text} {description_text}".casefold()
    is_comparison_focus = bool(
        secondary_focus
        and any(marker in combined_text for marker in ["difference between", "compare", "versus", " vs ", "tradeoff", "区别", "对比"])
    )

    if is_comparison_focus:
        if has_cjk:
            step_one_concept = f"比较 {primary_focus} 和 {secondary_focus}"
            step_one_description = (
                f"先说明“{primary_focus}”与“{secondary_focus}”在“{problem_title}”里的关键区别，"
                f"并用{knowledge_text}把这个差异锚定下来。"
            )
            step_two_concept = f"在一个聚焦场景里应用 {primary_focus} 和 {secondary_focus}"
            step_two_description = (
                f"围绕“{problem_title}”走一遍具体场景，解释为什么要在“{primary_focus}”与“{secondary_focus}”之间做取舍，"
                "并记下接下来还不确定的问题。"
            )
        else:
            step_one_concept = f"Compare {primary_focus} and {secondary_focus}"
            step_one_description = (
                f"Explain how {primary_focus} differs from {secondary_focus} for '{problem_title}', "
                f"and anchor the distinction using {knowledge_text}."
            )
            step_two_concept = f"Apply {primary_focus} and {secondary_focus} in one focused scenario"
            step_two_description = (
                f"Work through one concrete scenario from '{problem_title}', justify the tradeoff between "
                f"{primary_focus} and {secondary_focus}, and record the next uncertainty to resolve."
            )
        step_two_resources = [first_resource, primary_focus, secondary_focus]
    else:
        step_one_concept = primary_focus
        if has_cjk:
            step_one_description = (
                f"先解释“{primary_focus}”在“{problem_title}”里的核心含义，"
                f"并用{knowledge_text}把它和当前问题目标连起来。"
            )
            step_two_concept = f"用一个最小例子应用 {primary_focus}"
            step_two_description = (
                f"围绕“{problem_title}”挑一个具体的小例子来应用“{primary_focus}”，"
                "验证结果是否成立，并记下下一步最值得追问的问题。"
            )
        else:
            step_one_description = (
                f"Explain the core idea of {primary_focus} for '{problem_title}', "
                f"and connect it to the problem goal using {knowledge_text}."
            )
            step_two_concept = f"Apply {primary_focus} in a minimal example"
            step_two_description = (
                f"Use one concrete example from '{problem_title}' to apply {primary_focus}, "
                "validate the result, and note the next open question."
            )
        step_two_resources = [first_resource, primary_focus]

    return [
        {
            "step": 1,
            "concept": step_one_concept,
            "description": step_one_description,
            "resources": [first_resource, "问题陈述" if has_cjk else "Problem statement"],
        },
        {
            "step": 2,
            "concept": step_two_concept,
            "description": step_two_description,
            "resources": step_two_resources,
        },
    ]


def normalize_learning_path_payload(payload: Any) -> List[Dict[str, Any]]:
    steps = payload
    if isinstance(payload, dict):
        steps = payload.get("steps", [])
    if not isinstance(steps, list):
        return []

    normalized: List[Dict[str, Any]] = []
    for index, raw_step in enumerate(steps):
        if not isinstance(raw_step, dict):
            continue

        concept = str(raw_step.get("concept", "") or "").strip()
        description = str(raw_step.get("description", "") or "").strip()
        resources_raw = raw_step.get("resources") or []
        if not isinstance(resources_raw, list):
            resources_raw = []
        resources = [
            str(item).strip()
            for item in resources_raw
            if str(item).strip()
        ][:5]

        if not concept and not description:
            continue

        normalized.append(
            {
                "step": normalize_int(raw_step.get("step"), index + 1, 1, 100),
                "concept": concept,
                "description": description,
                "resources": resources,
            }
        )

    return normalized


def normalize_string_items(values: Any, *, limit: int) -> List[str]:
    if not isinstance(values, list):
        return []
    normalized: List[str] = []
    seen = set()
    for raw in values:
        item = str(raw or "").strip()
        if not item:
            continue
        key = item.casefold()
        if key in seen:
            continue
        seen.add(key)
        normalized.append(item)
        if len(normalized) >= limit:
            break
    return normalized


def default_model_card_payload() -> Dict[str, Any]:
    return {
        "concept_maps": {"nodes": [], "edges": []},
        "core_principles": [],
        "examples": [],
        "limitations": [],
    }


def normalize_model_card_payload(payload: Any) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        return default_model_card_payload()

    concept_maps = payload.get("concept_maps")
    nodes_raw = concept_maps.get("nodes", []) if isinstance(concept_maps, dict) else []
    edges_raw = concept_maps.get("edges", []) if isinstance(concept_maps, dict) else []

    nodes: List[Dict[str, str]] = []
    for raw in nodes_raw if isinstance(nodes_raw, list) else []:
        if not isinstance(raw, dict):
            continue
        node_id = str(raw.get("id", "") or "").strip()
        label = str(raw.get("label", "") or "").strip()
        node_type = str(raw.get("type", "") or "").strip()
        if not node_id or not label:
            continue
        nodes.append(
            {
                "id": node_id,
                "label": label,
                "type": node_type or "concept",
            }
        )
        if len(nodes) >= 24:
            break

    edges: List[Dict[str, str]] = []
    for raw in edges_raw if isinstance(edges_raw, list) else []:
        if not isinstance(raw, dict):
            continue
        source = str(raw.get("source", "") or "").strip()
        target = str(raw.get("target", "") or "").strip()
        label = str(raw.get("label", "") or "").strip()
        if not source or not target:
            continue
        edges.append(
            {
                "source": source,
                "target": target,
                "label": label,
            }
        )
        if len(edges) >= 32:
            break

    return {
        "concept_maps": {"nodes": nodes, "edges": edges},
        "core_principles": normalize_string_items(payload.get("core_principles"), limit=8),
        "examples": normalize_string_items(payload.get("examples"), limit=8),
        "limitations": normalize_string_items(payload.get("limitations"), limit=8),
    }


def normalize_migration_payload(payload: Any) -> List[Dict[str, str]]:
    if not isinstance(payload, list):
        return []

    normalized: List[Dict[str, str]] = []
    seen = set()
    for raw in payload:
        if not isinstance(raw, dict):
            continue
        domain = str(raw.get("domain", "") or "").strip()
        application = str(raw.get("application", "") or "").strip()
        key_adaptations = str(raw.get("key_adaptations", "") or "").strip()
        if not domain or not application:
            continue
        dedupe_key = (domain.casefold(), application.casefold(), key_adaptations.casefold())
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        normalized.append(
            {
                "domain": domain,
                "application": application,
                "key_adaptations": key_adaptations,
            }
        )
        if len(normalized) >= 5:
            break

    return normalized


def format_step_hint_text(structured_hint: Dict[str, Any]) -> str:
    focus = str(structured_hint.get("focus", "")).strip()
    actions = structured_hint.get("next_actions") or []
    starter = str(structured_hint.get("starter", "")).strip()

    action_lines = "\n".join(
        f"- {str(item).strip()}" for item in actions if str(item).strip()
    )
    blocks: List[str] = []
    if focus:
        blocks.append(f"Focus:\n{focus}")
    if action_lines:
        blocks.append(f"Next actions:\n{action_lines}")
    if starter:
        blocks.append(f"Starter sentence:\n{starter}")
    return "\n\n".join(blocks).strip()


def format_feedback_text(structured_feedback: Dict[str, Any]) -> str:
    misconceptions = structured_feedback.get("misconceptions", [])
    suggestions = structured_feedback.get("suggestions", [])
    next_question = structured_feedback.get("next_question", "")
    correctness = structured_feedback.get("correctness", "")
    mastery_score = structured_feedback.get("mastery_score", 0)
    confidence = structured_feedback.get("confidence", 0.0)
    pass_stage = structured_feedback.get("pass_stage", False)
    decision_reason = structured_feedback.get("decision_reason", "")

    lines = [
        f"Correctness: {correctness or 'N/A'}",
        f"Mastery Score: {mastery_score}",
        f"Confidence: {confidence}",
        f"Pass Stage: {pass_stage}",
        f"Misconceptions: {' | '.join(misconceptions) if misconceptions else 'None'}",
        f"Suggestions: {' | '.join(suggestions) if suggestions else 'None'}",
        f"Next Question: {next_question or 'None'}",
        f"Decision Reason: {decision_reason or 'None'}",
    ]
    return "\n".join(lines)


def parse_feedback_text(feedback_text: Optional[str]) -> Dict[str, Any]:
    if not feedback_text:
        return normalize_feedback_structured({
            "correctness": "",
            "misconceptions": [],
            "suggestions": [],
            "next_question": "",
        })

    structured = {
        "correctness": "",
        "mastery_score": 0,
        "confidence": 0.0,
        "pass_stage": False,
        "misconceptions": [],
        "suggestions": [],
        "next_question": "",
        "decision_reason": "",
    }

    patterns = {
        "correctness": r"Correctness:\s*(.*)",
        "mastery_score": r"Mastery Score:\s*(.*)",
        "confidence": r"Confidence:\s*(.*)",
        "pass_stage": r"Pass Stage:\s*(.*)",
        "misconceptions": r"Misconceptions:\s*(.*)",
        "suggestions": r"Suggestions:\s*(.*)",
        "next_question": r"Next Question:\s*(.*)",
        "decision_reason": r"Decision Reason:\s*(.*)",
    }

    for key, pattern in patterns.items():
        match = re.search(pattern, feedback_text)
        if not match:
            continue
        value = match.group(1).strip()
        if key in ("misconceptions", "suggestions"):
            structured[key] = [] if value in ("None", "") else [item.strip() for item in value.split("|") if item.strip()]
        elif key == "mastery_score":
            structured[key] = normalize_int(value, 0, 0, 100)
        elif key == "confidence":
            structured[key] = normalize_float(value, 0.0, 0.0, 1.0)
        elif key == "pass_stage":
            structured[key] = normalize_bool(value, False)
        else:
            structured[key] = "" if value in ("None", "N/A") else value

    if (
        not structured["correctness"]
        and not structured["misconceptions"]
        and not structured["suggestions"]
        and not structured["next_question"]
    ):
        structured["suggestions"] = [feedback_text.strip()]

    return normalize_feedback_structured(structured)
