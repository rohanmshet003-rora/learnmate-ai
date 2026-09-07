"""Student Assessment Agent — Stage 2 implementation.

Evaluates student self-reported skills using IBM Granite to produce a
structured skill profile: detected skills, gaps, recommended level, summary.
"""

import json
import logging
from typing import Any, Dict, List

from app.agents.base import BaseAgent

logger = logging.getLogger(__name__)

_FALLBACK: Dict[str, Any] = {
    "detected_skills": [],
    "skill_gaps": [],
    "recommended_level": "beginner",
    "summary": "Assessment unavailable — Granite not configured.",
}


def _parse_response(raw: str) -> Dict[str, Any]:
    """Extract JSON from Granite's response text.

    Granite may wrap the JSON in markdown fences or add prose before/after.
    We try multiple extraction strategies before giving up.
    """
    # Strategy 1: direct JSON parse
    try:
        return json.loads(raw.strip())
    except json.JSONDecodeError:
        pass

    # Strategy 2: find the first '{' … last '}' block
    start = raw.find("{")
    end = raw.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(raw[start : end + 1])
        except json.JSONDecodeError:
            pass

    logger.warning("AssessmentAgent: could not parse Granite response: %s", raw[:300])
    return {}


class AssessmentAgent(BaseAgent):
    name = "assessment_agent"
    description = (
        "Assesses student skill level from self-reported data and quiz answers. "
        "Identifies strengths, gaps, and recommends an experience level."
    )

    async def run(self, inputs: dict) -> dict:
        """Analyse student skills and goal with IBM Granite.

        Expected inputs:
            student_id (str)
            self_reported_skills (list[str])
            goal (str)
            experience_level (str)  — optional hint from student

        Returns:
            detected_skills (list[str])
            skill_gaps (list[str])
            recommended_level (str)
            summary (str)
            granite_used (bool)
        """
        student_id: str = inputs.get("student_id", "")
        skills: List[str] = inputs.get("self_reported_skills", [])
        goal: str = inputs.get("goal", "")
        experience_level: str = inputs.get("experience_level", "beginner")

        prompt = f"""You are an expert learning assessment AI.

A student has the following self-reported skills: {json.dumps(skills)}
Their learning goal is: "{goal}"
Their self-reported experience level is: "{experience_level}"

Analyse their profile and respond with ONLY valid JSON (no prose, no markdown fences):
{{
  "detected_skills": ["skill1", "skill2"],
  "skill_gaps": ["gap1", "gap2"],
  "recommended_level": "beginner|intermediate|advanced",
  "summary": "2-3 sentence summary of the student's current profile and readiness"
}}

Rules:
- detected_skills: skills from their list that are genuinely relevant to the goal
- skill_gaps: important skills they will need but have not mentioned
- recommended_level: must be exactly one of beginner, intermediate, advanced
- summary: plain English, concise
"""

        raw, granite_used = await self.granite.generate_safe(
            prompt, max_new_tokens=400, temperature=0.3
        )

        parsed = _parse_response(raw) if granite_used else {}

        return {
            "student_id": student_id,
            "detected_skills": parsed.get("detected_skills", skills),
            "skill_gaps": parsed.get("skill_gaps", _FALLBACK["skill_gaps"]),
            "recommended_level": parsed.get(
                "recommended_level", experience_level or "beginner"
            ),
            "summary": parsed.get("summary", _FALLBACK["summary"]),
            "granite_used": granite_used,
        }
