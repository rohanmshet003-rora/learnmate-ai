"""Roadmap Planner Agent — Stage 2 implementation.

Builds a personalised, ordered learning roadmap using IBM Granite,
given the student's goal, skill gaps, experience level, and preferences.
"""

import json
import logging
from typing import Any, Dict, List

from app.agents.base import BaseAgent

logger = logging.getLogger(__name__)

_FALLBACK_COURSES: List[Dict[str, Any]] = []


def _parse_response(raw: str) -> Dict[str, Any]:
    """Extract JSON object from Granite's response text.

    Tries three strategies:
    1. Direct parse of the full response.
    2. Extract the first {...} block.
    3. Build a minimal object from a top-level [...] courses array.
    """
    cleaned = raw.strip()

    # Strip markdown fences if present
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        cleaned = "\n".join(
            l for l in lines if not l.strip().startswith("```")
        ).strip()

    # Strategy 1: direct parse
    try:
        result = json.loads(cleaned)
        if isinstance(result, dict):
            return result
    except json.JSONDecodeError:
        pass

    # Strategy 2: first { ... } block
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            result = json.loads(cleaned[start : end + 1])
            if isinstance(result, dict):
                return result
        except json.JSONDecodeError:
            pass

    # Strategy 3: top-level [ ... ] array treated as courses list
    start = cleaned.find("[")
    end = cleaned.rfind("]")
    if start != -1 and end != -1 and end > start:
        try:
            courses = json.loads(cleaned[start : end + 1])
            if isinstance(courses, list):
                return {"courses": courses}
        except json.JSONDecodeError:
            pass

    logger.warning("RoadmapPlannerAgent: could not parse Granite response: %s", raw[:400])
    return {}


def _normalise_courses(raw_courses: List[Any]) -> List[Dict[str, Any]]:
    """Ensure every course dict has the expected keys with safe defaults."""
    result = []
    for idx, c in enumerate(raw_courses):
        if not isinstance(c, dict):
            continue
        result.append(
            {
                "title": str(c.get("title", f"Course {idx + 1}")),
                "description": str(c.get("description", "")),
                "difficulty": str(c.get("difficulty", "beginner")),
                "estimated_hours": float(c.get("estimated_hours", 5.0)),
                "order_index": int(c.get("order_index", idx)),
            }
        )
    return result


class RoadmapPlannerAgent(BaseAgent):
    name = "roadmap_planner_agent"
    description = (
        "Generates a dynamic, personalised course roadmap based on student "
        "interests, skill gaps, and learning goal."
    )

    async def run(self, inputs: dict) -> dict:
        """Generate a sequenced learning roadmap with IBM Granite.

        Expected inputs:
            student_id (str)
            goal (str)
            skill_gaps (list[str])
            experience_level (str)
            preferences (dict)  — optional: learning_style, hours_per_week, etc.

        Returns:
            roadmap_title (str)
            courses (list[dict])  — ordered course objects
            granite_used (bool)
        """
        student_id: str = inputs.get("student_id", "")
        goal: str = inputs.get("goal", "")
        skill_gaps: List[str] = inputs.get("skill_gaps", [])
        experience_level: str = inputs.get("experience_level", "beginner")
        preferences: Dict[str, Any] = inputs.get("preferences", {})

        prefs_note = ""
        if preferences:
            prefs_note = f"\nStudent preferences: {json.dumps(preferences)}"

        gaps_str = ", ".join(skill_gaps[:8]) if skill_gaps else "general foundations"

        prompt = (
            "You are a curriculum designer. Output ONLY a JSON object with no extra text.\n\n"
            f"Student goal: {goal}\n"
            f"Level: {experience_level}\n"
            f"Skill gaps: {gaps_str}\n"
            f"{prefs_note}\n\n"
            "Output this exact JSON structure and nothing else:\n"
            '{"roadmap_title":"...","courses":['
            '{"title":"...","description":"...","difficulty":"beginner","estimated_hours":10,"order_index":0},'
            '{"title":"...","description":"...","difficulty":"intermediate","estimated_hours":15,"order_index":1}'
            "]}\n\n"
            "Requirements: 4 to 6 courses, ordered beginner to advanced, each addressing a skill gap."
        )

        raw, granite_used = await self.granite.generate_safe(
            prompt, max_new_tokens=600, temperature=0.4
        )

        parsed = _parse_response(raw) if granite_used else {}

        courses = _normalise_courses(parsed.get("courses", []))
        roadmap_title = parsed.get(
            "roadmap_title", f"Learning Roadmap: {goal}"
        )

        return {
            "student_id": student_id,
            "roadmap_title": roadmap_title,
            "courses": courses,
            "granite_used": granite_used,
        }
