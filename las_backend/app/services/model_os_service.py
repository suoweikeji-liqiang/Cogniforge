from typing import List, Dict, Any, Optional
from app.services.llm_service import llm_service


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
        
        import json
        try:
            model_data = json.loads(result)
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
        
        import json
        try:
            counter_examples = json.loads(result)
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
        
        import json
        try:
            migrations = json.loads(result)
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
3. Includes opportunities for model collision (testing understanding with counter-examples)

Return as JSON array of steps:
[
    {{
        "step": 1,
        "concept": "concept name",
        "description": "what to learn",
        "resources": ["resource 1", "resource 2"]
    }}
]"""
        
        result = await self.llm.generate(prompt)
        
        import json
        try:
            path = json.loads(result)
        except json.JSONDecodeError:
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
        model_id: str,
        action: str,
        previous_version: Optional[str],
        reason: str,
    ) -> Dict[str, Any]:
        return {
            "model_id": model_id,
            "action": action,
            "previous_version": previous_version,
            "reason": reason,
            "timestamp": "current_timestamp"
        }


model_os_service = ModelOSService()
