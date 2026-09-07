"""Assessment endpoint — delegates to AssessmentAgent."""

from fastapi import APIRouter, HTTPException
from app.schemas.roadmap import AssessmentRequest, AssessmentResult
from app.agents.assessment import AssessmentAgent

router = APIRouter(prefix="/assessment", tags=["assessment"])
_agent = AssessmentAgent()


@router.post("", response_model=AssessmentResult)
async def run_assessment(payload: AssessmentRequest) -> AssessmentResult:
    if not payload.student_id:
        raise HTTPException(status_code=400, detail="student_id is required.")

    result = await _agent.run(payload.model_dump())
    return AssessmentResult(
        student_id=payload.student_id,
        detected_skills=result.get("detected_skills", []),
        skill_gaps=result.get("skill_gaps", []),
        recommended_level=result.get("recommended_level", "beginner"),
        summary=result.get("message", ""),
        granite_used=result.get("granite_used", False),
    )
