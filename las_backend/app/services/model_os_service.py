from typing import List, Dict, Any, Optional
from app.services.llm_service import llm_service
import json
import re

def _clean_json_str(text: str) -> str:
    # First try to find a markdown block
    match = re.search(r'```(?:json)?\s*(.*?)\s*```', text, re.DOTALL)
    if match:
        return match.group(1).strip()
    
    text = text.strip()
    # Strip any text before the first [ or {
    if not text.startswith('[') and not text.startswith('{'):
        start_idx = -1
        for i, c in enumerate(text):
            if c in ('[', '{'):
                start_idx = i
                break
        if start_idx != -1:
            closing = ']' if text[start_idx] == '[' else '}'
            end_idx = -1
            for i in range(len(text)-1, -1, -1):
                if text[i] == closing:
                    end_idx = i
                    break
            if end_idx != -1 and end_idx >= start_idx:
                return text[start_idx:end_idx+1].strip()
    return text


class ModelOSService:
    def __init__(self):
        self.llm = llm_service
    
    async def create_model_card(
        self,
        user_id: str,
        title: str,
        description: str,
        associated_concepts: List[str],
    ) -> Dict[str, Any]:
        prompt = f"""Based on the following learning content, create a structured cognitive model card:

Title: {title}
Description: {description}
Associated Concepts: {', '.join(associated_concepts)}

Please generate:
1. A concept map with key nodes and relationships
2. Core principles and assumptions
3. Key examples that illustrate the model
4. Potential edge cases or limitations

Return the response as a JSON object with the following structure:
{{
    "concept_maps": {{
        "nodes": [{{"id": "x", "label": "concept name", "type": "concept/principle/example"}}],
        "edges": [{{"source": "x", "target": "y", "label": "relationship"}}]
    }},
    "core_principles": ["principle 1", "principle 2"],
    "examples": ["example 1", "example 2"],
    "limitations": ["limitation 1"]
}}"""
        
        result = await self.llm.generate(prompt)
        
        try:
            model_data = json.loads(_clean_json_str(result))
        except json.JSONDecodeError:
            model_data = {
                "concept_maps": {"nodes": [], "edges": []},
                "core_principles": [],
                "examples": [],
                "limitations": []
            }
        
        return model_data
    
    async def generate_counter_examples(
        self,
        model_title: str,
        model_concepts: List[str],
        user_response: str,
    ) -> List[str]:
        prompt = f"""You are the Contradiction Generation Module in Model OS.

Current Model: {model_title}
Model Concepts: {', '.join(model_concepts)}
User's Response/Understanding: {user_response}

Generate 2-3 counter-examples or challenging questions that:
1. Test the boundaries of the user's understanding
2. Challenge assumptions in the model
3. Highlight potential misunderstandings

Format as a JSON array of strings, each being a counter-example or challenging question."""
        
        result = await self.llm.generate(prompt)
        
        try:
            counter_examples = json.loads(_clean_json_str(result))
        except json.JSONDecodeError:
            counter_examples = []
        
        return counter_examples
    
    async def suggest_migration(
        self,
        model_title: str,
        model_concepts: List[str],
    ) -> List[Dict[str, str]]:
        prompt = f"""You are the Cross-Domain Migration Module in Model OS.

Current Model: {model_title}
Model Concepts: {', '.join(model_concepts)}

Suggest 2-3 other domains where this model could be applied, with brief explanations of how the concepts translate.

Return as JSON array:
[
    {{"domain": "domain name", "application": "how to apply", "key_adaptations": "what to adapt"}}
]"""
        
        result = await self.llm.generate(prompt)
        
        try:
            migrations = json.loads(_clean_json_str(result))
        except json.JSONDecodeError:
            migrations = []
        
        return migrations
    
    async def generate_learning_path(
        self,
        problem_title: str,
        problem_description: str,
        existing_knowledge: List[str],
    ) -> List[Dict[str, Any]]:
        prompt = f"""Generate an optimized learning path for:

Problem/Goal: {problem_title}
Description: {problem_description}
User's Existing Knowledge: {', '.join(existing_knowledge)}

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
]"""
        
        result = await self.llm.generate(prompt)
        
        try:
            path = json.loads(_clean_json_str(result))
        except json.JSONDecodeError as e:
            with open("llm_debug_zh.log", "w", encoding="utf-8") as f:
                f.write(f"JSON ERROR: {e}\\nRAW:\\n{result}\\n---\\n")
            print(f"Failed to parse path json. Error: {e}")
            path = []
        
        return path
    
    async def generate_feedback(
        self,
        user_response: str,
        concept: str,
        model_examples: List[str],
    ) -> str:
        prompt = f"""Provide feedback on the user's understanding:

Concept: {concept}
User's Response: {user_response}
Model Examples: {', '.join(model_examples)}

Analyze the response and provide:
1. Whether the understanding is correct
2. Specific gaps or misconceptions
3. Suggestions for improvement
4. A challenging question to test deeper understanding"""
        
        return await self.llm.generate(prompt)
    
    async def log_evolution(
        self,
        db,
        model_id: str,
        user_id: str,
        action: str,
        reason: str,
        snapshot: Optional[Dict[str, Any]] = None,
        previous_version_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        from app.models.entities.user import EvolutionLog
        log = EvolutionLog(
            model_id=model_id,
            user_id=user_id,
            action_taken=action,
            reason_for_change=reason,
            snapshot=snapshot,
            previous_version_id=previous_version_id,
        )
        db.add(log)
        await db.commit()
        await db.refresh(log)
        return {
            "id": log.id,
            "model_id": model_id,
            "action": action,
            "reason": reason,
        }

    async def generate_evolution_summary(
        self,
        card_title: str,
        old_snapshot: Optional[Dict],
        new_snapshot: Dict,
    ) -> str:
        """AI-generated summary of how a model card evolved."""
        old_desc = str(old_snapshot) if old_snapshot else "Initial creation"
        prompt = f"""Compare two versions of a cognitive model card and summarize the evolution:

Model: {card_title}
Previous state: {old_desc}
Current state: {str(new_snapshot)}

Provide a concise summary (2-3 sentences) of what changed and why it matters for the learner's understanding."""
        return await self.llm.generate(prompt)


model_os_service = ModelOSService()
