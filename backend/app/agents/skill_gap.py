"""Skill Gap Analysis Agent — Stage 2 implementation.

Compares current skills against goal requirements using IBM Granite to
identify missing skills and return a prioritised list.
"""

import json
import logging
from typing import Any, Dict, List

from app.agents.base import BaseAgent

logger = logging.getLogger(__name__)


def _parse_response(raw: str) -> Dict[str, Any]:
    """Extract JSON from Granite's response text."""
    try:
        return json.loads(raw.strip())
    except json.JSONDecodeError:
        pass

    start = raw.find("{")
    end = raw.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(raw[start : end + 1])
        except json.JSONDecodeError:
            pass

    logger.warning("SkillGapAgent: could not parse Granite response: %s", raw[:300])
    return {}


class SkillGapAgent(BaseAgent):
    name = "skill_gap_agent"
    description = (
        "Compares a student's current skills against the skills required "
        "for their learning goal and identifies gaps to fill."
    )

    async def run(self, inputs: dict) -> dict:
        """Identify skill gaps with IBM Granite.

        Expected inputs:
            student_id (str)
            current_skills (list[str])
            goal (str)

        Returns:
            gaps (list[str])           — skills the student is missing
            priority_skills (list[str])— top 3-5 skills to learn first
            explanation (str)          — brief rationale
            granite_used (bool)
        """
        student_id: str = inputs.get("student_id", "")
        current_skills: List[str] = inputs.get("current_skills", [])
        goal: str = inputs.get("goal", "")

        prompt = f"""You are an expert learning advisor.

A student wants to achieve: "{goal}"
Their current skills are: {json.dumps(current_skills)}

Identify what skills they are missing and respond with ONLY valid JSON (no prose, no markdown fences):
{{
  "gaps": ["missing_skill_1", "missing_skill_2"],
  "priority_skills": ["most_important_skill", "second_most_important"],
  "explanation": "1-2 sentence explanation of the skill gap analysis"
}}

Rules:
- gaps: skills required for the goal that are absent from current_skills
- priority_skills: subset of gaps ordered by importance (most critical first, max 5)
- explanation: plain English, concise
"""

        raw, granite_used = await self.granite.generate_safe(
            prompt, max_new_tokens=350, temperature=0.3
        )

        parsed = _parse_response(raw) if granite_used else {}

        return {
            "student_id": student_id,
            "gaps": parsed.get("gaps", []),
            "priority_skills": parsed.get("priority_skills", []),
            "explanation": parsed.get(
                "explanation",
                "Skill gap analysis unavailable — Granite not configured.",
            ),
            "granite_used": granite_used,
        }
