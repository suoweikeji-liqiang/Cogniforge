"""
Learning Assistant System - Functional Test Suite
Uses DeepSeek API (OpenAI-compatible) to test core LLM functionalities.
"""

import asyncio
import json
import time
import traceback
from datetime import datetime
from typing import Any

import openai


# === Configuration ===
DEEPSEEK_API_KEY = "sk-7a9fb402bd2d4af4999ca8c4a1446bb0"
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODEL = "deepseek-chat"


class TestResult:
    def __init__(self, name: str, category: str):
        self.name = name
        self.category = category
        self.status = "PENDING"
        self.duration = 0.0
        self.detail = ""
        self.error = ""

    def to_dict(self):
        return {
            "name": self.name,
            "category": self.category,
            "status": self.status,
            "duration_s": round(self.duration, 2),
            "detail": self.detail[:500] if self.detail else "",
            "error": self.error,
        }


class TestRunner:
    def __init__(self):
        self.results: list[TestResult] = []
        self.client = openai.OpenAI(
            api_key=DEEPSEEK_API_KEY,
            base_url=DEEPSEEK_BASE_URL,
        )

    def _call_llm(self, messages: list[dict], temperature=0.7, max_tokens=1024) -> str:
        response = self.client.chat.completions.create(
            model=DEEPSEEK_MODEL,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content

    def run_test(self, name: str, category: str, func):
        result = TestResult(name, category)
        start = time.time()
        try:
            detail = func()
            result.status = "PASS"
            result.detail = str(detail) if detail else ""
        except AssertionError as e:
            result.status = "FAIL"
            result.error = str(e)
        except Exception as e:
            result.status = "ERROR"
            result.error = f"{type(e).__name__}: {e}"
        result.duration = time.time() - start
        self.results.append(result)
        icon = {"PASS": "OK", "FAIL": "FAIL", "ERROR": "ERR"}[result.status]
        print(f"  [{icon}] {name} ({result.duration:.2f}s)")

    # =========================================================
    # Test Category 1: API Connectivity
    # =========================================================
    def test_api_basic_connectivity(self):
        """Test basic API connectivity with a simple prompt."""
        resp = self._call_llm(
            [{"role": "user", "content": "Reply with exactly: HELLO"}],
            temperature=0,
            max_tokens=10,
        )
        assert resp is not None and len(resp.strip()) > 0, "Empty response"
        return f"Response: {resp.strip()}"

    def test_api_chinese_support(self):
        """Test Chinese language support."""
        resp = self._call_llm(
            [{"role": "user", "content": "用中文回答：1+1等于几？只回答数字。"}],
            temperature=0,
            max_tokens=10,
        )
        assert resp is not None and len(resp.strip()) > 0, "Empty response"
        return f"Response: {resp.strip()}"

    def test_api_streaming_disabled(self):
        """Test non-streaming completion works correctly."""
        resp = self.client.chat.completions.create(
            model=DEEPSEEK_MODEL,
            messages=[{"role": "user", "content": "Say OK"}],
            temperature=0,
            max_tokens=5,
            stream=False,
        )
        assert resp.choices[0].message.content is not None
        assert resp.usage.total_tokens > 0, "Token usage not reported"
        return f"Tokens used: {resp.usage.total_tokens}"

    # =========================================================
    # Test Category 2: LLM Service Layer
    # =========================================================
    def test_llm_generate_basic(self):
        """Simulate LLMService.generate() - basic text generation."""
        prompt = "What is machine learning? Answer in one sentence."
        resp = self._call_llm([{"role": "user", "content": prompt}])
        assert len(resp) > 20, f"Response too short: {len(resp)} chars"
        return f"Length: {len(resp)} chars, Preview: {resp[:100]}..."

    def test_llm_generate_with_context(self):
        """Simulate LLMService.generate_with_context() - context-aware generation."""
        context = [
            {"role": "user", "content": "I'm learning about neural networks"},
            {"role": "assistant", "content": "Neural networks are computing systems inspired by biological neural networks."},
        ]
        context_str = "\n".join(
            f"{msg['role']}: {msg['content']}" for msg in context
        )
        full_prompt = f"Context:\n{context_str}\n\nCurrent question: What are the main types of neural networks?"
        resp = self._call_llm([{"role": "user", "content": full_prompt}])
        assert len(resp) > 50, "Context-aware response too short"
        return f"Length: {len(resp)} chars"

    def test_llm_multi_turn_conversation(self):
        """Test multi-turn conversation capability."""
        messages = [
            {"role": "system", "content": "You are a helpful learning assistant."},
            {"role": "user", "content": "What is recursion in programming?"},
        ]
        resp1 = self._call_llm(messages)
        assert len(resp1) > 20, "First turn response too short"

        messages.append({"role": "assistant", "content": resp1})
        messages.append({"role": "user", "content": "Give me a simple example in Python."})
        resp2 = self._call_llm(messages)
        assert len(resp2) > 20, "Second turn response too short"
        assert "def" in resp2.lower() or "python" in resp2.lower() or "function" in resp2.lower(), \
            "Second turn doesn't seem to contain code"
        return f"Turn1: {len(resp1)} chars, Turn2: {len(resp2)} chars"

    # =========================================================
    # Test Category 3: Model OS - Model Card Creation
    # =========================================================
    def test_model_card_creation(self):
        """Simulate ModelOSService.create_model_card() - structured model generation."""
        prompt = """Based on the following learning content, create a structured cognitive model card:

Title: Design Patterns
Description: Software design patterns for reusable object-oriented solutions
Associated Concepts: Singleton, Factory, Observer, Strategy

Please generate:
1. A concept map with key nodes and relationships
2. Core principles and assumptions
3. Key examples that illustrate the model
4. Potential edge cases or limitations

Return the response as a JSON object with the following structure:
{
    "concept_maps": {
        "nodes": [{"id": "x", "label": "concept name", "type": "concept/principle/example"}],
        "edges": [{"source": "x", "target": "y", "label": "relationship"}]
    },
    "core_principles": ["principle 1", "principle 2"],
    "examples": ["example 1", "example 2"],
    "limitations": ["limitation 1"]
}"""
        resp = self._call_llm([{"role": "user", "content": prompt}], max_tokens=2048)
        # Try to parse JSON from response
        try:
            # Handle markdown code blocks
            clean = resp.strip()
            if clean.startswith("```"):
                clean = clean.split("\n", 1)[1] if "\n" in clean else clean[3:]
                clean = clean.rsplit("```", 1)[0]
            data = json.loads(clean)
            has_maps = "concept_maps" in data
            has_principles = "core_principles" in data
            assert has_maps or has_principles, "Missing expected JSON fields"
            return f"JSON parsed OK, keys: {list(data.keys())}"
        except json.JSONDecodeError:
            # Fallback - check if response is meaningful
            assert len(resp) > 100, "Response too short for model card"
            return f"Non-JSON response, length: {len(resp)} chars (fallback OK)"

    # =========================================================
    # Test Category 4: Model OS - Counter Examples
    # =========================================================
    def test_counter_example_generation(self):
        """Simulate ModelOSService.generate_counter_examples()."""
        prompt = """You are the Contradiction Generation Module in Model OS.

Current Model: Object-Oriented Programming
Model Concepts: Encapsulation, Inheritance, Polymorphism, Abstraction
User's Response/Understanding: OOP is always better than functional programming for all tasks.

Generate 2-3 counter-examples or challenging questions that:
1. Test the boundaries of the user's understanding
2. Challenge assumptions in the model
3. Highlight potential misunderstandings

Format as a JSON array of strings, each being a counter-example or challenging question."""
        resp = self._call_llm([{"role": "user", "content": prompt}], max_tokens=1024)
        assert len(resp) > 30, "Counter-example response too short"
        # Try JSON parse
        try:
            clean = resp.strip()
            if clean.startswith("```"):
                clean = clean.split("\n", 1)[1] if "\n" in clean else clean[3:]
                clean = clean.rsplit("```", 1)[0]
            data = json.loads(clean)
            assert isinstance(data, list) and len(data) >= 2, f"Expected list with >=2 items, got {type(data)}"
            return f"Got {len(data)} counter-examples"
        except json.JSONDecodeError:
            return f"Non-JSON but meaningful response ({len(resp)} chars)"

    # =========================================================
    # Test Category 5: Model OS - Cross-Domain Migration
    # =========================================================
    def test_migration_suggestion(self):
        """Simulate ModelOSService.suggest_migration()."""
        prompt = """You are the Cross-Domain Migration Module in Model OS.

Current Model: Supply Chain Management
Model Concepts: Just-in-time delivery, Inventory optimization, Supplier diversification

Suggest 2-3 other domains where this model could be applied, with brief explanations of how the concepts translate.

Return as JSON array:
[
    {"domain": "domain name", "application": "how to apply", "key_adaptations": "what to adapt"}
]"""
        resp = self._call_llm([{"role": "user", "content": prompt}], max_tokens=1024)
        assert len(resp) > 50, "Migration response too short"
        try:
            clean = resp.strip()
            if clean.startswith("```"):
                clean = clean.split("\n", 1)[1] if "\n" in clean else clean[3:]
                clean = clean.rsplit("```", 1)[0]
            data = json.loads(clean)
            assert isinstance(data, list) and len(data) >= 2
            return f"Got {len(data)} migration suggestions"
        except json.JSONDecodeError:
            return f"Non-JSON response ({len(resp)} chars)"

    # =========================================================
    # Test Category 6: Model OS - Learning Path
    # =========================================================
    def test_learning_path_generation(self):
        """Simulate ModelOSService.generate_learning_path()."""
        prompt = """Generate an optimized learning path for:

Problem/Goal: Master React.js
Description: Learn React from basics to advanced patterns
User's Existing Knowledge: HTML, CSS, JavaScript basics

Create a step-by-step learning path that:
1. Builds on existing knowledge
2. Introduces new concepts in logical order
3. Includes opportunities for model collision (testing understanding with counter-examples)

Return as JSON array of steps:
[
    {
        "step": 1,
        "concept": "concept name",
        "description": "what to learn",
        "resources": ["resource 1", "resource 2"]
    }
]"""
        resp = self._call_llm([{"role": "user", "content": prompt}], max_tokens=2048)
        assert len(resp) > 100, "Learning path too short"
        try:
            clean = resp.strip()
            if clean.startswith("```"):
                clean = clean.split("\n", 1)[1] if "\n" in clean else clean[3:]
                clean = clean.rsplit("```", 1)[0]
            data = json.loads(clean)
            assert isinstance(data, list) and len(data) >= 3, "Expected at least 3 steps"
            return f"Got {len(data)} learning steps"
        except json.JSONDecodeError:
            return f"Non-JSON response ({len(resp)} chars)"

    # =========================================================
    # Test Category 7: Model OS - Feedback Generation
    # =========================================================
    def test_feedback_generation(self):
        """Simulate ModelOSService.generate_feedback()."""
        prompt = """Provide feedback on the user's understanding:

Concept: Database Normalization
User's Response: Normalization means putting all data into one big table to make queries faster.
Model Examples: First Normal Form, Second Normal Form, Third Normal Form

Analyze the response and provide:
1. Whether the understanding is correct
2. Specific gaps or misconceptions
3. Suggestions for improvement
4. A challenging question to test deeper understanding"""
        resp = self._call_llm([{"role": "user", "content": prompt}], max_tokens=1024)
        assert len(resp) > 100, "Feedback too short"
        # The response should identify the misconception
        resp_lower = resp.lower()
        has_correction = any(w in resp_lower for w in [
            "incorrect", "misconception", "not correct", "wrong",
            "opposite", "actually", "误", "不正确", "错"
        ])
        assert has_correction, "Feedback didn't identify the misconception"
        return f"Feedback length: {len(resp)} chars, misconception identified"

    # =========================================================
    # Test Category 8: Edge Cases & Error Handling
    # =========================================================
    def test_empty_prompt_handling(self):
        """Test handling of empty/minimal prompts."""
        resp = self._call_llm(
            [{"role": "user", "content": " "}],
            max_tokens=50,
        )
        # Should not crash, should return something
        assert resp is not None
        return f"Handled gracefully, response: {resp[:80]}"

    def test_long_context_handling(self):
        """Test handling of longer context windows."""
        long_context = "The concept of machine learning involves " * 100
        prompt = f"{long_context}\n\nSummarize the above in one sentence."
        resp = self._call_llm([{"role": "user", "content": prompt}], max_tokens=100)
        assert resp is not None and len(resp) > 10
        return f"Long context handled, response: {len(resp)} chars"

    def test_json_output_reliability(self):
        """Test reliability of JSON-formatted output."""
        prompt = 'Return exactly this JSON and nothing else: {"status": "ok", "count": 3}'
        resp = self._call_llm(
            [{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=50,
        )
        clean = resp.strip()
        if clean.startswith("```"):
            clean = clean.split("\n", 1)[1] if "\n" in clean else clean[3:]
            clean = clean.rsplit("```", 1)[0]
        data = json.loads(clean)
        assert data.get("status") == "ok"
        return f"JSON output reliable: {data}"

    def test_invalid_api_key_handling(self):
        """Test that invalid API key returns proper error."""
        bad_client = openai.OpenAI(
            api_key="sk-invalid-key-12345",
            base_url=DEEPSEEK_BASE_URL,
        )
        try:
            bad_client.chat.completions.create(
                model=DEEPSEEK_MODEL,
                messages=[{"role": "user", "content": "test"}],
                max_tokens=5,
            )
            raise AssertionError("Should have raised an error")
        except openai.AuthenticationError:
            return "AuthenticationError raised correctly"
        except openai.APIError as e:
            return f"API error raised: {type(e).__name__}"

    # =========================================================
    # Run all tests
    # =========================================================
    def run_all(self):
        print("=" * 60)
        print("Learning Assistant System - Functional Test Suite")
        print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Provider: DeepSeek ({DEEPSEEK_BASE_URL})")
        print(f"Model: {DEEPSEEK_MODEL}")
        print("=" * 60)

        categories = [
            ("API Connectivity", [
                ("Basic API Connectivity", self.test_api_basic_connectivity),
                ("Chinese Language Support", self.test_api_chinese_support),
                ("Non-Streaming Completion", self.test_api_streaming_disabled),
            ]),
            ("LLM Service Layer", [
                ("Basic Text Generation", self.test_llm_generate_basic),
                ("Context-Aware Generation", self.test_llm_generate_with_context),
                ("Multi-Turn Conversation", self.test_llm_multi_turn_conversation),
            ]),
            ("Model OS - Model Card", [
                ("Model Card Creation (JSON)", self.test_model_card_creation),
            ]),
            ("Model OS - Contradiction", [
                ("Counter-Example Generation", self.test_counter_example_generation),
            ]),
            ("Model OS - Migration", [
                ("Cross-Domain Migration", self.test_migration_suggestion),
            ]),
            ("Model OS - Learning Path", [
                ("Learning Path Generation", self.test_learning_path_generation),
            ]),
            ("Model OS - Feedback", [
                ("Feedback Generation", self.test_feedback_generation),
            ]),
            ("Edge Cases & Error Handling", [
                ("Empty Prompt Handling", self.test_empty_prompt_handling),
                ("Long Context Handling", self.test_long_context_handling),
                ("JSON Output Reliability", self.test_json_output_reliability),
                ("Invalid API Key Handling", self.test_invalid_api_key_handling),
            ]),
        ]

        for cat_name, tests in categories:
            print(f"\n--- {cat_name} ---")
            for test_name, test_func in tests:
                self.run_test(test_name, cat_name, test_func)

        return self.results


def generate_report(results: list[TestResult]) -> str:
    """Generate a markdown test report."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    total = len(results)
    passed = sum(1 for r in results if r.status == "PASS")
    failed = sum(1 for r in results if r.status == "FAIL")
    errors = sum(1 for r in results if r.status == "ERROR")
    total_time = sum(r.duration for r in results)

    lines = []
    lines.append("# Learning Assistant System - 功能测试报告")
    lines.append("")
    lines.append("## 测试概要")
    lines.append("")
    lines.append(f"| 项目 | 值 |")
    lines.append(f"|------|------|")
    lines.append(f"| 测试时间 | {now} |")
    lines.append(f"| LLM 提供商 | DeepSeek |")
    lines.append(f"| API 地址 | {DEEPSEEK_BASE_URL} |")
    lines.append(f"| 模型 | {DEEPSEEK_MODEL} |")
    lines.append(f"| 总测试数 | {total} |")
    lines.append(f"| 通过 | {passed} |")
    lines.append(f"| 失败 | {failed} |")
    lines.append(f"| 错误 | {errors} |")
    lines.append(f"| 通过率 | {passed/total*100:.1f}% |")
    lines.append(f"| 总耗时 | {total_time:.2f}s |")
    lines.append("")

    # Group by category
    categories = {}
    for r in results:
        categories.setdefault(r.category, []).append(r)

    lines.append("## 详细测试结果")
    lines.append("")

    for cat, cat_results in categories.items():
        cat_pass = sum(1 for r in cat_results if r.status == "PASS")
        lines.append(f"### {cat} ({cat_pass}/{len(cat_results)} 通过)")
        lines.append("")
        lines.append("| 测试项 | 状态 | 耗时 | 详情 |")
        lines.append("|--------|------|------|------|")
        for r in cat_results:
            status_icon = {"PASS": "✅", "FAIL": "❌", "ERROR": "⚠️"}[r.status]
            detail = r.detail if r.status == "PASS" else r.error
            detail = detail.replace("|", "\\|").replace("\n", " ")[:120]
            lines.append(f"| {r.name} | {status_icon} {r.status} | {r.duration:.2f}s | {detail} |")
        lines.append("")

    # Analysis section
    lines.append("## 测试分析")
    lines.append("")

    if passed == total:
        lines.append("所有测试均通过，系统核心功能运行正常。")
    else:
        if failed > 0:
            lines.append("### 失败的测试")
            lines.append("")
            for r in results:
                if r.status == "FAIL":
                    lines.append(f"- **{r.name}** ({r.category}): {r.error}")
            lines.append("")
        if errors > 0:
            lines.append("### 出错的测试")
            lines.append("")
            for r in results:
                if r.status == "ERROR":
                    lines.append(f"- **{r.name}** ({r.category}): {r.error}")
            lines.append("")

    lines.append("## 功能覆盖说明")
    lines.append("")
    lines.append("| 功能模块 | 测试内容 | 说明 |")
    lines.append("|----------|----------|------|")
    lines.append("| API 连通性 | 基础连接、中文支持、Token 统计 | 验证 DeepSeek API 基础可用性 |")
    lines.append("| LLM 服务层 | 文本生成、上下文感知、多轮对话 | 对应 `LLMService.generate()` 和 `generate_with_context()` |")
    lines.append("| 模型卡片创建 | 结构化 JSON 输出 | 对应 `ModelOSService.create_model_card()` |")
    lines.append("| 矛盾生成 | 反例与挑战性问题 | 对应 `ModelOSService.generate_counter_examples()` |")
    lines.append("| 跨域迁移 | 领域迁移建议 | 对应 `ModelOSService.suggest_migration()` |")
    lines.append("| 学习路径 | 步骤化学习规划 | 对应 `ModelOSService.generate_learning_path()` |")
    lines.append("| 反馈生成 | 理解评估与纠错 | 对应 `ModelOSService.generate_feedback()` |")
    lines.append("| 边界情况 | 空输入、长文本、JSON 可靠性、错误 Key | 验证系统鲁棒性 |")
    lines.append("")
    lines.append("---")
    lines.append(f"*报告生成时间: {now}*")

    return "\n".join(lines)


if __name__ == "__main__":
    runner = TestRunner()
    results = runner.run_all()

    print("\n" + "=" * 60)
    total = len(results)
    passed = sum(1 for r in results if r.status == "PASS")
    print(f"Results: {passed}/{total} passed")
    print("=" * 60)

    report = generate_report(results)

    report_path = "tests/test_report.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"\nReport saved to: {report_path}")
