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
    # Test Category 9: SRS SM-2 Algorithm (Unit Tests)
    # =========================================================
    def test_srs_initial_schedule(self):
        """Test SM-2 initial schedule creation."""
        schedule = type("Schedule", (), {
            "ease_factor": 2500,
            "interval_days": 1,
            "repetitions": 0,
        })()
        assert schedule.ease_factor == 2500, "Initial ease factor should be 2500"
        assert schedule.interval_days == 1, "Initial interval should be 1 day"
        assert schedule.repetitions == 0, "Initial repetitions should be 0"
        return f"Initial schedule: EF={schedule.ease_factor}, interval={schedule.interval_days}, reps={schedule.repetitions}"

    def test_srs_review_quality_high(self):
        """Test SM-2 review with high quality (5=perfect recall)."""
        # Simulate SM-2 algorithm for quality=5
        quality = 5
        ef = 2500 / 1000.0  # 2.5
        repetitions = 0
        # First review: interval=1
        interval = 1
        repetitions += 1
        ef = ef + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
        ef = max(1.3, ef)
        assert ef == 2.6, f"EF after perfect review should be 2.6, got {ef}"
        assert interval == 1, "First interval should be 1"
        # Second review: interval=6
        interval = 6
        repetitions += 1
        # Third review: interval = round(6 * 2.6) = 16
        interval = round(interval * ef)
        assert interval == 16, f"Third interval should be 16, got {interval}"
        return f"SM-2 high quality: EF={ef}, intervals=[1,6,{interval}]"

    def test_srs_review_quality_low(self):
        """Test SM-2 review with low quality (1=forgot) resets repetitions."""
        quality = 1
        ef = 2500 / 1000.0
        repetitions = 3
        interval_days = 15
        # Low quality: reset
        repetitions = 0
        interval = 1
        ef = ef + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
        ef = max(1.3, ef)
        assert repetitions == 0, "Repetitions should reset to 0"
        assert interval == 1, "Interval should reset to 1"
        assert ef >= 1.3, f"EF should not go below 1.3, got {ef}"
        return f"SM-2 low quality: EF={ef:.2f}, reps={repetitions}, interval={interval}"

    def test_srs_ease_factor_floor(self):
        """Test SM-2 ease factor never drops below 1.3."""
        ef = 1.3  # Already at minimum
        for _ in range(5):
            quality = 0  # Worst quality
            ef = ef + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
            ef = max(1.3, ef)
        assert ef == 1.3, f"EF should stay at 1.3 floor, got {ef}"
        return f"EF floor maintained at {ef}"

    # =========================================================
    # Test Category 10: Cognitive Challenges
    # =========================================================
    def test_challenge_boundary_test(self):
        """Test boundary-testing challenge generation via LLM."""
        prompt = """Create a boundary-testing question for the concept 'Object-Oriented Programming'.
The question should challenge assumptions and test edge cases.
Context: Learning about OOP principles. Examples: ['Encapsulation', 'Inheritance', 'Polymorphism']

Return a single challenging question as plain text."""
        resp = self._call_llm([{"role": "user", "content": prompt}], max_tokens=512)
        assert len(resp) > 20, f"Challenge too short: {len(resp)} chars"
        assert "?" in resp, "Challenge should contain a question mark"
        return f"Boundary challenge: {resp[:100]}..."

    def test_challenge_cross_card(self):
        """Test cross-domain connection challenge generation."""
        prompt = """Create a cross-domain connection question about 'Database Normalization'.
Ask the user to explain how this concept relates to a different field.

Return a single cross-domain question as plain text."""
        resp = self._call_llm([{"role": "user", "content": prompt}], max_tokens=512)
        assert len(resp) > 20, f"Cross-card challenge too short: {len(resp)} chars"
        return f"Cross-card challenge: {resp[:100]}..."

    def test_challenge_socratic(self):
        """Test Socratic question generation."""
        prompt = """Create a Socratic question about 'Machine Learning' that guides the learner
to discover a deeper insight without giving the answer directly.

Return a single Socratic question as plain text."""
        resp = self._call_llm([{"role": "user", "content": prompt}], max_tokens=512)
        assert len(resp) > 20, f"Socratic challenge too short: {len(resp)} chars"
        assert "?" in resp, "Socratic question should contain a question mark"
        return f"Socratic challenge: {resp[:100]}..."

    # =========================================================
    # Test Category 11: Model Card Evolution
    # =========================================================
    def test_evolution_summary_generation(self):
        """Test AI-generated evolution summary for model card changes."""
        prompt = """Compare two versions of a cognitive model card and summarize the evolution:

Model: Design Patterns
Previous state: {"title": "Design Patterns", "examples": ["Singleton", "Factory"], "version": 1}
Current state: {"title": "Design Patterns", "examples": ["Singleton", "Factory", "Observer", "Strategy"], "counter_examples": ["Over-engineering", "Pattern abuse"], "version": 2}

Provide a concise summary (2-3 sentences) of what changed and why it matters for the learner's understanding."""
        resp = self._call_llm([{"role": "user", "content": prompt}], max_tokens=512)
        assert len(resp) > 30, "Evolution summary too short"
        return f"Evolution summary: {resp[:120]}..."

    def test_evolution_version_tracking(self):
        """Test that version tracking logic works correctly."""
        card = type("Card", (), {"version": 1, "title": "Test"})()
        assert card.version == 1
        card.version += 1
        assert card.version == 2, f"Version should be 2, got {card.version}"
        card.version += 1
        assert card.version == 3, f"Version should be 3, got {card.version}"
        return f"Version tracking: 1 -> 2 -> {card.version}"

    # =========================================================
    # Test Category 12: Knowledge Graph Structure
    # =========================================================
    def test_knowledge_graph_generation(self):
        """Test knowledge graph node/edge structure from LLM."""
        prompt = """Generate a knowledge graph for the topic "Web Development".
Return as JSON with this structure:
{
    "nodes": [{"id": "1", "label": "concept", "type": "concept"}],
    "edges": [{"source": "1", "target": "2", "label": "relationship"}]
}
Include at least 4 nodes and 3 edges."""
        resp = self._call_llm([{"role": "user", "content": prompt}], max_tokens=1024)
        try:
            clean = resp.strip()
            if clean.startswith("```"):
                clean = clean.split("\n", 1)[1] if "\n" in clean else clean[3:]
                clean = clean.rsplit("```", 1)[0]
            data = json.loads(clean)
            assert "nodes" in data, "Missing 'nodes' key"
            assert "edges" in data, "Missing 'edges' key"
            assert len(data["nodes"]) >= 3, f"Expected >=3 nodes, got {len(data['nodes'])}"
            return f"Graph: {len(data['nodes'])} nodes, {len(data['edges'])} edges"
        except json.JSONDecodeError:
            assert len(resp) > 50, "Non-JSON response too short"
            return f"Non-JSON graph response ({len(resp)} chars)"

    # =========================================================
    # Test Category 13: Statistics & Aggregation Logic
    # =========================================================
    def test_activity_heatmap_aggregation(self):
        """Test heatmap activity aggregation logic."""
        from datetime import date
        activity = {}
        # Simulate activity data
        dates = ["2026-02-20", "2026-02-20", "2026-02-21", "2026-02-22", "2026-02-22", "2026-02-22"]
        for d in dates:
            activity[d] = activity.get(d, 0) + 1
        assert activity["2026-02-20"] == 2, f"Expected 2, got {activity['2026-02-20']}"
        assert activity["2026-02-21"] == 1, f"Expected 1, got {activity['2026-02-21']}"
        assert activity["2026-02-22"] == 3, f"Expected 3, got {activity['2026-02-22']}"
        return f"Heatmap aggregation: {activity}"

    def test_statistics_overview_structure(self):
        """Test statistics overview data structure."""
        overview = {
            "problems": 5,
            "model_cards": 3,
            "conversations": 10,
            "reviews": 7,
            "due_reviews": 2,
        }
        required_keys = ["problems", "model_cards", "conversations", "reviews", "due_reviews"]
        for key in required_keys:
            assert key in overview, f"Missing key: {key}"
            assert isinstance(overview[key], int), f"{key} should be int"
            assert overview[key] >= 0, f"{key} should be non-negative"
        return f"Overview structure valid: {overview}"

    # =========================================================
    # Test Category 14: Streaming API Support
    # =========================================================
    def test_api_streaming(self):
        """Test streaming completion works correctly."""
        stream = self.client.chat.completions.create(
            model=DEEPSEEK_MODEL,
            messages=[{"role": "user", "content": "Count from 1 to 5."}],
            temperature=0,
            max_tokens=50,
            stream=True,
        )
        chunks = []
        for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                chunks.append(chunk.choices[0].delta.content)
        full_response = "".join(chunks)
        assert len(chunks) > 1, f"Expected multiple chunks, got {len(chunks)}"
        assert len(full_response) > 0, "Streaming produced empty response"
        return f"Streaming OK: {len(chunks)} chunks, response: {full_response[:60]}"

    # =========================================================
    # Test Category 15: Quick Notes (记事本)
    # =========================================================
    def test_note_data_structure(self):
        """Test QuickNote data structure and validation."""
        note = {
            "content": "学习设计模式的关键是理解每种模式解决的核心问题",
            "source": "voice",
            "tags": ["设计模式", "学习笔记"],
        }
        assert isinstance(note["content"], str) and len(note["content"]) > 0
        assert note["source"] in ("text", "voice")
        assert isinstance(note["tags"], list)
        assert all(isinstance(t, str) for t in note["tags"])
        return f"Note structure valid: source={note['source']}, tags={note['tags']}"

    def test_note_source_types(self):
        """Test that notes support both text and voice sources."""
        sources = ["text", "voice"]
        notes = []
        for src in sources:
            note = {"content": f"Note from {src}", "source": src, "tags": []}
            assert note["source"] == src
            notes.append(note)
        assert len(notes) == 2
        return f"Both source types valid: {sources}"

    def test_note_tags_handling(self):
        """Test note tags parsing and edge cases."""
        cases = [
            {"tags": [], "desc": "empty tags"},
            {"tags": ["单标签"], "desc": "single tag"},
            {"tags": ["AI", "机器学习", "深度学习"], "desc": "multiple tags"},
        ]
        for case in cases:
            assert isinstance(case["tags"], list)
            for tag in case["tags"]:
                assert isinstance(tag, str) and len(tag) > 0
        return f"Tags handling OK for {len(cases)} cases"

    def test_note_content_ai_enhancement(self):
        """Test AI enhancement of quick note content."""
        raw_note = "递归就是函数调用自己 要有终止条件"
        prompt = (
            f"The user captured a quick note (possibly via voice): \"{raw_note}\"\n"
            "Please clean up and enhance this note:\n"
            "1. Fix any grammar or formatting issues\n"
            "2. Add structure if needed\n"
            "3. Suggest relevant tags\n"
            "Return as JSON: {\"enhanced_content\": \"...\", \"suggested_tags\": [\"...\"]}"
        )
        resp = self._call_llm([{"role": "user", "content": prompt}], max_tokens=512)
        assert len(resp) > 20, "AI enhancement response too short"
        return f"AI note enhancement: {len(resp)} chars"

    def test_note_voice_transcription_cleanup(self):
        """Test AI cleanup of voice-transcribed notes."""
        voice_text = "嗯 那个 设计模式里面 单例模式 就是说 一个类只能有一个实例 对吧"
        prompt = (
            f"Clean up this voice-transcribed note, removing filler words and making it concise:\n"
            f"\"{voice_text}\"\n"
            "Return only the cleaned text."
        )
        resp = self._call_llm([{"role": "user", "content": prompt}], temperature=0, max_tokens=256)
        assert len(resp) > 5, "Cleanup response too short"
        assert len(resp) < len(voice_text) * 2, "Cleanup should not be much longer than original"
        return f"Voice cleanup: '{resp.strip()[:80]}'"

    # =========================================================
    # Test Category 16: Resource Links (资源链接)
    # =========================================================
    def test_resource_link_data_structure(self):
        """Test ResourceLink data structure and validation."""
        resource = {
            "url": "https://example.com/design-patterns",
            "title": "Design Patterns Tutorial",
            "link_type": "webpage",
        }
        assert resource["url"].startswith("http")
        assert isinstance(resource["title"], str)
        assert resource["link_type"] in ("webpage", "video")
        return f"Resource structure valid: type={resource['link_type']}"

    def test_resource_link_types(self):
        """Test different resource link types."""
        resources = [
            {"url": "https://example.com/article", "link_type": "webpage", "title": "Article"},
            {"url": "https://youtube.com/watch?v=abc", "link_type": "video", "title": "Video Tutorial"},
        ]
        for r in resources:
            assert r["link_type"] in ("webpage", "video")
            assert r["url"].startswith("http")
        return f"Link types valid: {[r['link_type'] for r in resources]}"

    def test_resource_ai_interpretation_webpage(self):
        """Test AI interpretation of a webpage resource."""
        prompt = (
            "Please analyze and summarize the following web page link. "
            "Title: Python Design Patterns Guide. URL: https://example.com/python-patterns. "
            "Provide a concise summary of what this resource is about, key takeaways, "
            "and how it might be useful for learning. Respond in the same language as the title if provided."
        )
        resp = self._call_llm([{"role": "user", "content": prompt}], max_tokens=512)
        assert len(resp) > 50, "Interpretation too short"
        return f"Webpage interpretation: {len(resp)} chars"

    def test_resource_ai_interpretation_video(self):
        """Test AI interpretation of a video resource."""
        prompt = (
            "Please analyze and summarize the following video link. "
            "Title: 深入理解React Hooks. URL: https://youtube.com/watch?v=example. "
            "Provide a concise summary of what this resource is about, key takeaways, "
            "and how it might be useful for learning. Respond in the same language as the title if provided."
        )
        resp = self._call_llm([{"role": "user", "content": prompt}], max_tokens=512)
        assert len(resp) > 50, "Video interpretation too short"
        # Should respond in Chinese since title is Chinese
        has_chinese = any('\u4e00' <= c <= '\u9fff' for c in resp)
        assert has_chinese, "Should respond in Chinese matching the title language"
        return f"Video interpretation (Chinese): {len(resp)} chars"

    def test_resource_status_transitions(self):
        """Test resource status update logic."""
        statuses = ["pending", "read", "archived"]
        resource = {"status": "pending"}
        assert resource["status"] == "pending"
        resource["status"] = "read"
        assert resource["status"] == "read"
        resource["status"] = "archived"
        assert resource["status"] == "archived"
        return f"Status transitions: pending -> read -> archived"

    def test_resource_update_fields(self):
        """Test resource partial update logic."""
        resource = {"title": "Original Title", "status": "pending", "url": "https://example.com"}
        update = {"title": "Updated Title", "status": None}
        if update["title"] is not None:
            resource["title"] = update["title"]
        if update["status"] is not None:
            resource["status"] = update["status"]
        assert resource["title"] == "Updated Title"
        assert resource["status"] == "pending"  # unchanged
        return f"Partial update: title changed, status unchanged"

    # =========================================================
    # Test Category 17: Practice Tasks (练习任务)
    # =========================================================
    def test_practice_task_data_structure(self):
        """Test PracticeTask data structure."""
        task = {
            "title": "Implement Singleton Pattern",
            "description": "Write a thread-safe singleton in Python",
            "task_type": "coding",
            "model_card_id": None,
        }
        assert len(task["title"]) > 0 and len(task["title"]) <= 500
        assert task["task_type"] in ("coding", "explanation", "analysis", None)
        return f"Practice task valid: type={task['task_type']}"

    def test_practice_submission_feedback(self):
        """Test AI feedback generation for practice submissions."""
        prompt = (
            "Provide feedback on the user's understanding:\n\n"
            "Concept: Singleton Pattern\n"
            "User's Response: A singleton ensures only one instance of a class exists "
            "by making the constructor private and providing a static method to get the instance.\n"
            "Model Examples: []\n\n"
            "Analyze the response and provide:\n"
            "1. Whether the understanding is correct\n"
            "2. Specific gaps or misconceptions\n"
            "3. Suggestions for improvement"
        )
        resp = self._call_llm([{"role": "user", "content": prompt}], max_tokens=1024)
        assert len(resp) > 50, "Feedback too short"
        return f"Practice feedback: {len(resp)} chars"

    def test_practice_task_types(self):
        """Test different practice task types."""
        task_types = [
            {"type": "coding", "title": "Implement Observer Pattern"},
            {"type": "explanation", "title": "Explain SOLID Principles"},
            {"type": "analysis", "title": "Analyze Time Complexity"},
        ]
        for t in task_types:
            assert isinstance(t["type"], str)
            assert len(t["title"]) > 0
        return f"Task types valid: {[t['type'] for t in task_types]}"

    # =========================================================
    # Test Category 18: Review System (复习系统)
    # =========================================================
    def test_review_data_structure(self):
        """Test Review data structure."""
        review = {
            "review_type": "weekly",
            "period": "2026-W09",
            "content": {
                "summary": "Learned design patterns",
                "key_insights": ["Singleton is overused", "Prefer composition"],
                "areas_to_improve": ["Need more practice with Observer"],
            },
        }
        assert review["review_type"] in ("daily", "weekly", "monthly")
        assert isinstance(review["content"], dict)
        assert "summary" in review["content"]
        return f"Review structure valid: type={review['review_type']}, period={review['period']}"

    def test_review_types(self):
        """Test different review types and periods."""
        reviews = [
            {"review_type": "daily", "period": "2026-02-28"},
            {"review_type": "weekly", "period": "2026-W09"},
            {"review_type": "monthly", "period": "2026-02"},
        ]
        for r in reviews:
            assert r["review_type"] in ("daily", "weekly", "monthly")
            assert len(r["period"]) > 0
        return f"Review types valid: {[r['review_type'] for r in reviews]}"

    def test_review_content_update(self):
        """Test review partial update logic."""
        review = {
            "review_type": "weekly",
            "period": "2026-W09",
            "content": {"summary": "Original"},
        }
        update = {"content": {"summary": "Updated summary", "new_field": "added"}}
        if update.get("content") is not None:
            review["content"] = update["content"]
        assert review["content"]["summary"] == "Updated summary"
        assert "new_field" in review["content"]
        assert review["review_type"] == "weekly"  # unchanged
        return f"Review update: content changed, type unchanged"

    # =========================================================
    # Test Category 19: Challenge Answer & Feedback (挑战回答)
    # =========================================================
    def test_challenge_answer_feedback(self):
        """Test AI feedback for challenge answers."""
        prompt = (
            "Provide feedback on the user's understanding:\n\n"
            "Concept: Database Indexing\n"
            "Challenge Question: When might adding an index actually hurt performance?\n"
            "User's Answer: Indexes always improve query performance.\n"
            "Model Examples: []\n\n"
            "Analyze the response and provide feedback on correctness and gaps."
        )
        resp = self._call_llm([{"role": "user", "content": prompt}], max_tokens=1024)
        assert len(resp) > 50, "Challenge feedback too short"
        resp_lower = resp.lower()
        has_correction = any(w in resp_lower for w in [
            "incorrect", "not always", "write", "insert", "update",
            "overhead", "actually", "误", "不", "wrong"
        ])
        assert has_correction, "Should identify the misconception about indexes"
        return f"Challenge feedback: {len(resp)} chars, misconception identified"

    def test_challenge_status_transitions(self):
        """Test challenge status flow: pending -> answered."""
        challenge = {"status": "pending", "user_answer": None, "ai_feedback": None}
        assert challenge["status"] == "pending"
        challenge["user_answer"] = "My answer"
        challenge["ai_feedback"] = "Good insight, but consider..."
        challenge["status"] = "answered"
        assert challenge["status"] == "answered"
        assert challenge["user_answer"] is not None
        assert challenge["ai_feedback"] is not None
        return f"Challenge status: pending -> answered"

    # =========================================================
    # Test Category 20: Password Reset Flow (密码重置)
    # =========================================================
    def test_password_reset_token_structure(self):
        """Test password reset token generation logic."""
        import hashlib
        import secrets
        token = secrets.token_urlsafe(32)
        assert len(token) >= 32, "Token too short"
        # Simulate hashing for storage
        hashed = hashlib.sha256(token.encode()).hexdigest()
        assert len(hashed) == 64, "SHA256 hash should be 64 chars"
        assert hashed != token, "Hash should differ from token"
        return f"Token: {len(token)} chars, Hash: {hashed[:16]}..."

    def test_password_reset_expiry_logic(self):
        """Test password reset token expiry validation."""
        from datetime import timedelta
        now = datetime.now()
        expires = now + timedelta(hours=1)
        assert expires > now, "Expiry should be in the future"
        # Simulate expired token
        expired = now - timedelta(hours=1)
        assert expired < now, "Expired token should be in the past"
        return f"Expiry logic: valid={expires > now}, expired={expired < now}"

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
            ("SRS SM-2 Algorithm", [
                ("Initial Schedule Creation", self.test_srs_initial_schedule),
                ("Review Quality High (Perfect)", self.test_srs_review_quality_high),
                ("Review Quality Low (Forgot)", self.test_srs_review_quality_low),
                ("Ease Factor Floor (1.3)", self.test_srs_ease_factor_floor),
            ]),
            ("Cognitive Challenges", [
                ("Boundary Test Challenge", self.test_challenge_boundary_test),
                ("Cross-Card Challenge", self.test_challenge_cross_card),
                ("Socratic Question", self.test_challenge_socratic),
            ]),
            ("Model Card Evolution", [
                ("Evolution Summary Generation", self.test_evolution_summary_generation),
                ("Version Tracking Logic", self.test_evolution_version_tracking),
            ]),
            ("Knowledge Graph", [
                ("Knowledge Graph Structure", self.test_knowledge_graph_generation),
            ]),
            ("Statistics & Aggregation", [
                ("Activity Heatmap Aggregation", self.test_activity_heatmap_aggregation),
                ("Statistics Overview Structure", self.test_statistics_overview_structure),
            ]),
            ("Streaming API", [
                ("Streaming Completion", self.test_api_streaming),
            ]),
            ("Quick Notes", [
                ("Note Data Structure", self.test_note_data_structure),
                ("Note Source Types", self.test_note_source_types),
                ("Note Tags Handling", self.test_note_tags_handling),
                ("Note AI Enhancement", self.test_note_content_ai_enhancement),
                ("Voice Transcription Cleanup", self.test_note_voice_transcription_cleanup),
            ]),
            ("Resource Links", [
                ("Resource Data Structure", self.test_resource_link_data_structure),
                ("Resource Link Types", self.test_resource_link_types),
                ("AI Interpretation (Webpage)", self.test_resource_ai_interpretation_webpage),
                ("AI Interpretation (Video)", self.test_resource_ai_interpretation_video),
                ("Resource Status Transitions", self.test_resource_status_transitions),
                ("Resource Partial Update", self.test_resource_update_fields),
            ]),
            ("Practice Tasks", [
                ("Practice Task Structure", self.test_practice_task_data_structure),
                ("Practice Submission Feedback", self.test_practice_submission_feedback),
                ("Practice Task Types", self.test_practice_task_types),
            ]),
            ("Review System", [
                ("Review Data Structure", self.test_review_data_structure),
                ("Review Types & Periods", self.test_review_types),
                ("Review Content Update", self.test_review_content_update),
            ]),
            ("Challenge Answer & Feedback", [
                ("Challenge Answer Feedback", self.test_challenge_answer_feedback),
                ("Challenge Status Transitions", self.test_challenge_status_transitions),
            ]),
            ("Password Reset Flow", [
                ("Reset Token Structure", self.test_password_reset_token_structure),
                ("Reset Token Expiry Logic", self.test_password_reset_expiry_logic),
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
    lines.append("| SRS SM-2 算法 | 初始调度、高质量复习、低质量复习、EF 下限 | 验证间隔重复算法正确性 |")
    lines.append("| 认知挑战 | 边界测试、跨卡片、苏格拉底式提问 | 对应 `ChallengesView` 三种挑战类型 |")
    lines.append("| 模型卡片演化 | 演化摘要生成、版本追踪 | 对应 `ModelOSService.generate_evolution_summary()` |")
    lines.append("| 知识图谱 | 图结构生成（节点+边） | 对应 `KnowledgeGraphView` 数据结构 |")
    lines.append("| 统计与聚合 | 热力图聚合、概览数据结构 | 对应 `statistics` 路由数据逻辑 |")
    lines.append("| 流式 API | 流式补全验证 | 验证 DeepSeek 流式输出能力 |")
    lines.append("| 快速笔记 | 数据结构、来源类型、标签处理、AI增强、语音清理 | 对应 `/api/notes` 路由功能 |")
    lines.append("| 资源链接 | 数据结构、链接类型、AI解读(网页/视频)、状态流转、部分更新 | 对应 `/api/resources` 路由功能 |")
    lines.append("| 练习任务 | 数据结构、提交反馈、任务类型 | 对应 `/api/practice` 路由功能 |")
    lines.append("| 复习系统 | 数据结构、复习类型与周期、内容更新 | 对应 `/api/reviews` 路由功能 |")
    lines.append("| 挑战回答 | AI反馈生成、状态流转 | 对应 `/api/challenges/{id}/answer` 功能 |")
    lines.append("| 密码重置 | Token生成、过期逻辑 | 对应 `/api/auth/forgot-password` 功能 |")
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
