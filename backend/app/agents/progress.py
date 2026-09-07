"""Progress & Adaptation Agent — Stage 2 implementation.

Monitors learning progress and recommends roadmap adaptations using
IBM Granite based on completion data and student feedback.
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

    logger.warning("ProgressAgent: could not parse Granite response: %s", raw[:300])
    return {}


class ProgressAgent(BaseAgent):
    name = "progress_agent"
    description = (
        "Tracks student progress, detects struggles or acceleration, "
        "and recommends roadmap adjustments."
    )

    async def run(self, inputs: dict) -> dict:
        """Analyse progress and recommend adaptations with IBM Granite.

        Expected inputs:
            student_id (str)
            roadmap_id (str)
            progress_data (list[dict])  — e.g. [{"course": "...", "pct": 75}]
            feedback (str)              — optional free-text feedback

        Returns:
            recommendations (list[str])
            adaptation_summary (str)
            should_adapt (bool)
            granite_used (bool)
        """
        student_id: str = inputs.get("student_id", "")
        roadmap_id: str = inputs.get("roadmap_id", "")
        progress_data: List[Any] = inputs.get("progress_data", [])
        feedback: str = inputs.get("feedback", "")

        # Compute a brief summary of progress for the prompt
        completed = [p for p in progress_data if isinstance(p, dict) and p.get("pct", 0) >= 100]
        in_progress = [p for p in progress_data if isinstance(p, dict) and 0 < p.get("pct", 0) < 100]
        not_started = [p for p in progress_data if isinstance(p, dict) and p.get("pct", 0) == 0]

        feedback_note = f'\nStudent feedback: "{feedback}"' if feedback else ""

        prompt = f"""You are a personalised learning coach.

Analyse a student's learning progress and recommend adaptations:
- Courses completed: {len(completed)} of {len(progress_data)}
- In progress: {json.dumps([p.get("course", "") for p in in_progress])}
- Not started: {json.dumps([p.get("course", "") for p in not_started])}
- Progress data: {json.dumps(progress_data)}{feedback_note}

Respond with ONLY valid JSON (no prose, no markdown fences):
{{
  "recommendations": ["recommendation 1", "recommendation 2"],
  "adaptation_summary": "1-2 sentence summary of what adaptations are suggested and why",
  "should_adapt": true
}}

Rules:
- recommendations: concrete, actionable suggestions (2–4 items)
- should_adapt: true if significant changes to the roadmap are warranted, false otherwise
- adaptation_summary: plain English, concise
"""

        raw, granite_used = await self.granite.generate_safe(
            prompt, max_new_tokens=400, temperature=0.3
        )

        parsed = _parse_response(raw) if granite_used else {}

        return {
            "student_id": student_id,
            "roadmap_id": roadmap_id,
            "recommendations": parsed.get(
                "recommendations", ["Continue with your current roadmap."]
            ),
            "adaptation_summary": parsed.get(
                "adaptation_summary",
                "Progress analysis unavailable — Granite not configured.",
            ),
            "should_adapt": parsed.get("should_adapt", False),
            "granite_used": granite_used,
        }
